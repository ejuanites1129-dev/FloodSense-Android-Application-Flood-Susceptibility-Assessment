"""Spatial services for temporary FloodSense map interactions."""

import re
from dataclasses import dataclass
from math import isfinite
from typing import Any

from django.conf import settings
from django.contrib.gis.db.models.functions import IsEmpty, IsValid
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from provenance import policies
from provenance.models import DataSource, PublicationStatus

from .constants import (
    BACOOR_CITY_CODE,
    BACOOR_REFERENCE_BARANGAY_COUNT,
    BACOOR_REFERENCE_SOURCE_NAME,
)
from .models import (
    BarangaySusceptibilitySummary,
    FloodSusceptibilityDataset,
    GeographicArea,
)
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


def active_consultation_dataset() -> FloodSusceptibilityDataset | None:
    """Return one complete provisional dataset or fail closed.

    A partially imported or accidentally approved dataset must never replace
    the neutral demonstration zones. The import command activates only after
    all 47 current barangays have been validated and stored.
    """

    if not settings.DEBUG or not settings.ENABLE_PROVISIONAL_MGB_PREVIEW:
        return None

    datasets = list(
        FloodSusceptibilityDataset.objects.select_related("source")
        .filter(
            is_active_for_consultation=True,
            status=PublicationStatus.PENDING_VALIDATION,
            source__source_type=DataSource.SourceType.AGENCY_DATASET,
            source__status=PublicationStatus.PENDING_VALIDATION,
        )
        .order_by("id")[:2]
    )
    if len(datasets) != 1:
        return None
    dataset = datasets[0]
    if dataset.barangay_summaries.count() != BACOOR_REFERENCE_BARANGAY_COUNT:
        return None
    eligible_ids = set(eligible_bacoor_reference_barangays().values_list("id", flat=True))
    summary_ids = set(dataset.barangay_summaries.values_list("area_id", flat=True))
    if eligible_ids != summary_ids or len(summary_ids) != BACOOR_REFERENCE_BARANGAY_COUNT:
        return None
    return dataset


def consultation_assessment_areas():
    """Return the 47 current barangays with the active summary prefetched."""

    dataset = active_consultation_dataset()
    if dataset is None:
        return GeographicArea.objects.none()
    summaries = BarangaySusceptibilitySummary.objects.filter(dataset=dataset).select_related(
        "dataset", "dataset__source"
    )
    return (
        eligible_bacoor_reference_barangays()
        .filter(susceptibility_summaries__dataset=dataset)
        .prefetch_related(
            Prefetch(
                "susceptibility_summaries",
                queryset=summaries,
                to_attr="active_consultation_summaries",
            )
        )
        .distinct()
    )


def active_consultation_summary_for_area(
    area: GeographicArea,
) -> BarangaySusceptibilitySummary | None:
    """Return the current summary for one eligible barangay, if available."""

    prefetched = getattr(area, "active_consultation_summaries", None)
    if prefetched is not None:
        return prefetched[0] if len(prefetched) == 1 else None
    dataset = active_consultation_dataset()
    if dataset is None:
        return None
    try:
        return BarangaySusceptibilitySummary.objects.select_related(
            "dataset", "dataset__source"
        ).get(dataset=dataset, area=area)
    except BarangaySusceptibilitySummary.DoesNotExist:
        return None


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
    eligible_areas = GeographicArea.objects.select_related("source").filter(is_enabled=True)
    consultation_dataset = None
    if normalized_mode == policies.DEMONSTRATION_MODE:
        consultation_dataset = active_consultation_dataset()
        eligible_areas = (
            consultation_assessment_areas()
            if consultation_dataset is not None
            else policies.permitted_records(
                eligible_areas.filter(area_type=GeographicArea.AreaType.DEMO_ZONE),
                normalized_mode,
            )
        )
    else:
        eligible_areas = policies.permitted_records(eligible_areas, normalized_mode)
    matches = list(eligible_areas.filter(geometry__covers=point).order_by("name", "id"))

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
        "data_status": (
            PublicationStatus.PENDING_VALIDATION
            if consultation_dataset is not None
            else policies.data_status_for_mode(normalized_mode)
        ),
        "warnings": _point_resolution_warnings(normalized_mode, consultation_dataset),
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
    identities = list(
        barangays.annotate(
            geometry_is_empty=IsEmpty("geometry"),
            geometry_is_valid=IsValid("geometry"),
        ).values_list("code", "name", "geometry_is_empty", "geometry_is_valid")
    )
    public_codes = [public_psgc_code(code) for code, *_ in identities]
    normalized_names = [name.strip().casefold() for _, name, *_ in identities]
    if (
        len(identities) != BACOOR_REFERENCE_BARANGAY_COUNT
        or any(
            public_code is None or not name.strip() or geometry_is_empty or not geometry_is_valid
            for public_code, (_, name, geometry_is_empty, geometry_is_valid) in zip(
                public_codes, identities, strict=True
            )
        )
        or len(set(public_codes)) != BACOOR_REFERENCE_BARANGAY_COUNT
        or len(set(normalized_names)) != BACOOR_REFERENCE_BARANGAY_COUNT
    ):
        return BarangayResolutionResult(BarangayResolutionState.UNAVAILABLE)

    city_rows = list(
        GeographicArea.objects.filter(
            code=BACOOR_CITY_CODE,
            area_type=GeographicArea.AreaType.CITY,
            is_enabled=True,
            status=PublicationStatus.PENDING_VALIDATION,
            source=source,
        )
        .annotate(
            geometry_is_empty=IsEmpty("geometry"),
            geometry_is_valid=IsValid("geometry"),
        )
        .values_list("id", "geometry_is_empty", "geometry_is_valid")[:2]
    )
    if len(city_rows) != 1 or city_rows[0][1] or not city_rows[0][2]:
        return BarangayResolutionResult(BarangayResolutionState.UNAVAILABLE)
    city_id = city_rows[0][0]

    matches = list(
        barangays.filter(geometry__covers=point).values_list("code", "name").order_by("code", "id")
    )
    matched_identities = _normalized_barangay_matches(matches)
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
        return BarangayResolutionResult(BarangayResolutionState.AMBIGUOUS_BOUNDARY)

    if GeographicArea.objects.filter(
        id=city_id,
        geometry__covers=point,
    ).exists():
        # A City-covered point that is not covered by a current barangay is an
        # apparent data gap; it must not be mislabeled as outside Bacoor.
        return BarangayResolutionResult(BarangayResolutionState.UNAVAILABLE)
    return BarangayResolutionResult(BarangayResolutionState.OUTSIDE_BACOOR)


def public_psgc_code(area_code: str) -> str | None:
    """Return the stable public PSGC identity for a controlled area code.

    Keeping this geography-owned avoids treating a database row id or a
    mutable barangay label as a cross-stream domain identifier.
    """

    match = re.fullmatch(r"PSGC_(\d{10})", area_code)
    return match.group(1) if match else None


def _normalized_barangay_matches(
    matches: list[tuple[str, str]],
) -> set[tuple[str | None, str]]:
    """Collapse repeated geometry matches for one stable barangay identity."""

    return {(public_psgc_code(code), name.strip()) for code, name in matches}


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
        raise PointResolutionInputError({field_name: "Enter a valid numeric coordinate."})
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise PointResolutionInputError({field_name: "Enter a valid numeric coordinate."}) from None
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


def _point_resolution_warnings(
    mode: str,
    dataset: FloodSusceptibilityDataset | None,
) -> list[str]:
    warnings = list(policies.warnings_for_mode(mode))
    if dataset is None:
        return warnings
    from .constants import (  # Local import keeps the public constants grouped.
        MGB_COVERAGE_LIMITATION,
        MGB_DERIVATION_LIMITATION,
        MGB_PROVISIONAL_WARNING,
    )

    return [
        *warnings,
        MGB_PROVISIONAL_WARNING,
        MGB_DERIVATION_LIMITATION,
        MGB_COVERAGE_LIMITATION,
    ]
