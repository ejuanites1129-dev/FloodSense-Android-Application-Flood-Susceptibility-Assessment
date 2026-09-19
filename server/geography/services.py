"""Spatial services for temporary FloodSense map interactions."""

import re
from dataclasses import dataclass
from math import isfinite
from typing import Any

from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from provenance import policies
from provenance.models import DataSource, PublicationStatus

from .constants import (
    BACOOR_CITY_CODE,
    BACOOR_REFERENCE_BARANGAY_COUNT,
    BACOOR_REFERENCE_SOURCE_NAME,
)
from .models import GeographicArea
from .serializers import BarangayResolutionState


class PointResolutionInputError(ValidationError):
    """Raised when a coordinate or operating mode cannot be resolved safely."""


@dataclass(frozen=True)
class BarangayResolutionResult:
    """Stable internal result for one no-write administrative lookup."""

    state: str
    barangay_psgc_code: str | None = None
    barangay_name: str | None = None

    @property
    def barangay(self) -> dict[str, str] | None:
        if self.state != BarangayResolutionState.RESOLVED:
            return None
        if self.barangay_psgc_code is None or self.barangay_name is None:
            return None
        return {
            "psgc_code": self.barangay_psgc_code,
            "name": self.barangay_name,
        }


def eligible_bacoor_reference_barangays():
    """Return only the controlled pending-validation Bacoor reference rows.

    This selector is the Day 1 eligibility foundation. It deliberately performs
    no spatial lookup and does not decide whether the layer is complete.
    """

    return GeographicArea.objects.select_related("source").filter(
        area_type=GeographicArea.AreaType.BARANGAY,
        is_enabled=True,
        status=PublicationStatus.PENDING_VALIDATION,
        source__name=BACOOR_REFERENCE_SOURCE_NAME,
        source__source_type=DataSource.SourceType.AGENCY_DATASET,
        source__status=PublicationStatus.PENDING_VALIDATION,
        source__is_publicly_releasable=True,
    )


def resolve_area_for_point(
    *,
    latitude: float,
    longitude: float,
    mode: str,
) -> dict[str, Any]:
    """Resolve one non-persisted WGS 84 point against permitted stored areas."""

    normalized_mode = _normalize_mode(mode)
    validated_latitude = _validate_coordinate(
        latitude,
        field_name="latitude",
        minimum=-90,
        maximum=90,
    )
    validated_longitude = _validate_coordinate(
        longitude,
        field_name="longitude",
        minimum=-180,
        maximum=180,
    )

    # GeoJSON and PostGIS use x/y = longitude/latitude for EPSG:4326.
    point = Point(validated_longitude, validated_latitude, srid=4326)
    eligible_areas = GeographicArea.objects.select_related("source").filter(
        is_enabled=True
    )
    if normalized_mode == policies.DEMONSTRATION_MODE:
        eligible_areas = eligible_areas.filter(
            area_type=GeographicArea.AreaType.DEMO_ZONE
        )
    matches = list(
        policies.permitted_records(eligible_areas, normalized_mode)
        .filter(geometry__covers=point)
        .order_by("name", "id")
    )

    if len(matches) == 1:
        state = "RESOLVED"
        area = _serialize_resolved_area(matches[0])
    elif matches:
        state = "AMBIGUOUS_AREA"
        area = None
    else:
        state = "OUTSIDE_SUPPORTED_AREA"
        area = None

    return {
        "resolution_state": state,
        "coordinate": {
            "latitude": validated_latitude,
            "longitude": validated_longitude,
        },
        "area": area,
        "operating_mode": normalized_mode,
        "data_status": policies.data_status_for_mode(normalized_mode),
        "warnings": policies.warnings_for_mode(normalized_mode),
    }


def resolve_bacoor_barangay(
    *,
    latitude: float,
    longitude: float,
) -> BarangayResolutionResult:
    """Resolve one WGS 84 point against the controlled 47-barangay layer.

    The function performs SELECT queries only. It deliberately fails closed
    when the reserved source, City row, barangay count, or stable identities do
    not match the Day 1 contract.
    """

    # GeoDjango/PostGIS EPSG:4326 point order is x/y = longitude/latitude.
    point = Point(longitude, latitude, srid=4326)
    sources = list(
        DataSource.objects.filter(
            name=BACOOR_REFERENCE_SOURCE_NAME,
            source_type=DataSource.SourceType.AGENCY_DATASET,
            status=PublicationStatus.PENDING_VALIDATION,
            is_publicly_releasable=True,
        ).order_by("id")[:2]
    )
    if len(sources) != 1:
        return BarangayResolutionResult(BarangayResolutionState.UNAVAILABLE)

    source = sources[0]
    barangays = eligible_bacoor_reference_barangays().filter(source=source)
    identities = list(barangays.values_list("code", "name"))
    if len(identities) != BACOOR_REFERENCE_BARANGAY_COUNT or any(
        _public_psgc_code(code) is None or not name.strip()
        for code, name in identities
    ):
        return BarangayResolutionResult(BarangayResolutionState.UNAVAILABLE)

    cities = GeographicArea.objects.filter(
        code=BACOOR_CITY_CODE,
        area_type=GeographicArea.AreaType.CITY,
        is_enabled=True,
        status=PublicationStatus.PENDING_VALIDATION,
        source=source,
    )
    if cities.count() != 1:
        return BarangayResolutionResult(BarangayResolutionState.UNAVAILABLE)

    matches = list(
        barangays.filter(geometry__covers=point)
        .values_list("code", "name")
        .order_by("code", "id")
    )
    matched_identities = {
        (_public_psgc_code(code), name) for code, name in matches
    }
    if len(matched_identities) == 1:
        psgc_code, name = matched_identities.pop()
        if psgc_code is None:
            return BarangayResolutionResult(BarangayResolutionState.UNAVAILABLE)
        return BarangayResolutionResult(
            BarangayResolutionState.RESOLVED,
            barangay_psgc_code=psgc_code,
            barangay_name=name,
        )
    if matched_identities:
        return BarangayResolutionResult(
            BarangayResolutionState.AMBIGUOUS_BOUNDARY
        )

    if cities.filter(geometry__covers=point).exists():
        # A City-covered point that is not covered by a current barangay is an
        # apparent data gap; it must not be mislabeled as outside Bacoor.
        return BarangayResolutionResult(BarangayResolutionState.UNAVAILABLE)
    return BarangayResolutionResult(BarangayResolutionState.OUTSIDE_BACOOR)


def _public_psgc_code(area_code: str) -> str | None:
    match = re.fullmatch(r"PSGC_(\d{10})", area_code)
    return match.group(1) if match else None


def _normalize_mode(mode: str) -> str:
    try:
        return policies.normalize_operating_mode(mode)
    except ValueError as error:
        raise PointResolutionInputError({"mode": str(error)}) from None


def _validate_coordinate(
    value: float,
    *,
    field_name: str,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, bool):
        raise PointResolutionInputError(
            {field_name: "Enter a valid numeric coordinate."}
        )
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise PointResolutionInputError(
            {field_name: "Enter a valid numeric coordinate."}
        ) from None
    if not isfinite(parsed) or not minimum <= parsed <= maximum:
        raise PointResolutionInputError(
            {field_name: f"Ensure this value is between {minimum} and {maximum}."}
        )
    return parsed


def _serialize_resolved_area(area: GeographicArea) -> dict[str, Any]:
    return {
        "id": area.id,
        "code": area.code,
        "name": area.name,
        "area_type": area.area_type,
        "data_status": area.status,
    }
