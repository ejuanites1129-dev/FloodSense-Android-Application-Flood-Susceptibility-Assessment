"""Spatial services for temporary FloodSense map interactions."""

from math import isfinite
from typing import Any

from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from provenance import policies
from provenance.models import DataSource, PublicationStatus

from .constants import BACOOR_REFERENCE_SOURCE_NAME
from .models import GeographicArea


class PointResolutionInputError(ValidationError):
    """Raised when a coordinate or operating mode cannot be resolved safely."""


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
