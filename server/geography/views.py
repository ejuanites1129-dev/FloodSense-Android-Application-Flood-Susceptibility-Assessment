"""Public GeoJSON views for supported FloodSense areas."""

import json

from core.serializers import OperatingModeQuerySerializer
from provenance.models import DataSource, PublicationStatus
from provenance.policies import (
    DEMONSTRATION_MODE,
    data_status_for_mode,
    permitted_records,
    warnings_for_mode,
)
from rest_framework import serializers
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from .constants import (
    BACOOR_REFERENCE_LIMITATION,
    BACOOR_REFERENCE_SOURCE_NAME,
    BACOOR_REFERENCE_WARNING,
    MGB_COVERAGE_LIMITATION,
    MGB_DERIVATION_LIMITATION,
    MGB_PROVISIONAL_WARNING,
)
from .models import GeographicArea
from .serializers import (
    RESOLVER_MAX_REQUEST_BYTES,
    BarangayResolutionRequestSerializer,
    PointResolutionRequestSerializer,
    make_barangay_resolution_response,
)
from .services import (
    PointResolutionInputError,
    active_consultation_dataset,
    active_consultation_summary_for_area,
    consultation_assessment_areas,
    resolve_area_for_point,
    resolve_bacoor_barangay,
)


@api_view(["GET"])
@permission_classes([AllowAny])
def area_collection(request):
    """Return enabled, mode-permitted area polygons as a GeoJSON collection."""

    serializer = OperatingModeQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    mode = serializer.validated_data["mode"]
    areas = GeographicArea.objects.select_related("source").filter(is_enabled=True)
    dataset = None
    if mode == DEMONSTRATION_MODE:
        dataset = active_consultation_dataset()
        if dataset is not None:
            areas = consultation_assessment_areas()
        else:
            areas = permitted_records(
                areas.filter(area_type=GeographicArea.AreaType.DEMO_ZONE), mode
            )
    else:
        areas = permitted_records(areas, mode)
    areas = areas.order_by("name", "id")

    return Response(
        {
            "type": "FeatureCollection",
            "features": [
                _serialize_area_feature(area, susceptibility_dataset=dataset) for area in areas
            ],
            "operating_mode": mode,
            "data_status": (
                PublicationStatus.PENDING_VALIDATION
                if dataset is not None
                else data_status_for_mode(mode)
            ),
            "susceptibility_dataset": _serialize_dataset(dataset),
            "warnings": _warnings_for_dataset(mode, dataset),
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def reference_boundary_collection(request):
    """Return current Bacoor barangays and any active provisional summaries."""

    dataset = active_consultation_dataset()
    if dataset is not None:
        areas = consultation_assessment_areas().order_by("name", "id")
    else:
        areas = (
            GeographicArea.objects.select_related("source")
            .filter(
                area_type=GeographicArea.AreaType.BARANGAY,
                is_enabled=True,
                status=PublicationStatus.PENDING_VALIDATION,
                source__name=BACOOR_REFERENCE_SOURCE_NAME,
                source__source_type=DataSource.SourceType.AGENCY_DATASET,
                source__status=PublicationStatus.PENDING_VALIDATION,
                source__is_publicly_releasable=True,
            )
            .order_by("name", "id")
        )
    return Response(
        {
            "type": "FeatureCollection",
            "features": [
                _serialize_area_feature(area, susceptibility_dataset=dataset) for area in areas
            ],
            "layer_kind": "ADMINISTRATIVE_REFERENCE",
            "data_status": PublicationStatus.PENDING_VALIDATION,
            "susceptibility_dataset": _serialize_dataset(dataset),
            "warnings": [
                BACOOR_REFERENCE_WARNING,
                BACOOR_REFERENCE_LIMITATION,
                *(
                    [
                        MGB_PROVISIONAL_WARNING,
                        MGB_DERIVATION_LIMITATION,
                        MGB_COVERAGE_LIMITATION,
                    ]
                    if dataset is not None
                    else []
                ),
            ],
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def resolve_point(request):
    """Resolve a temporary coordinate without saving it."""

    serializer = PointResolutionRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    inputs = serializer.validated_data
    try:
        result = resolve_area_for_point(
            latitude=inputs["latitude"],
            longitude=inputs["longitude"],
            mode=inputs["mode"],
        )
    except PointResolutionInputError as error:
        detail = getattr(error, "message_dict", {"non_field_errors": error.messages})
        raise serializers.ValidationError(detail) from error
    return Response(result)


@api_view(["POST"])
@parser_classes([JSONParser])
@permission_classes([AllowAny])
def resolve_barangay(request):
    """Resolve one temporary coordinate against the controlled Bacoor layer."""

    if _request_content_length(request) > RESOLVER_MAX_REQUEST_BYTES:
        return Response(
            {"detail": "The resolver request is too large."},
            status=HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )
    serializer = BarangayResolutionRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    inputs = serializer.validated_data
    try:
        result = resolve_bacoor_barangay(
            latitude=inputs["latitude"],
            longitude=inputs["longitude"],
        )
        payload = make_barangay_resolution_response(
            state=result.state,
            latitude=inputs["latitude"],
            longitude=inputs["longitude"],
            barangay=result.barangay,
        )
    except Exception:  # noqa: BLE001 - public response must not expose internals
        return Response(
            {"detail": "The resolver is temporarily unavailable."},
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return Response(payload)


def _request_content_length(request) -> int:
    """Return a safe declared body size without reading or logging the body."""

    try:
        return max(0, int(request.META.get("CONTENT_LENGTH") or 0))
    except (TypeError, ValueError):
        return RESOLVER_MAX_REQUEST_BYTES + 1


def _serialize_area_feature(
    area: GeographicArea,
    *,
    susceptibility_dataset=None,
) -> dict:
    summary = (
        active_consultation_summary_for_area(area) if susceptibility_dataset is not None else None
    )
    return {
        "type": "Feature",
        "id": area.id,
        "geometry": json.loads(area.geometry.geojson),
        "properties": {
            "id": area.id,
            "code": area.code,
            "name": area.name,
            "area_type": area.area_type,
            "data_status": area.status,
            "updated_at": area.updated_at.isoformat(),
            "susceptibility_summary": _serialize_summary(summary),
            "source": {
                "id": area.source_id,
                "name": area.source.name,
                "organization": area.source.organization,
                "status": area.source.status,
            },
        },
    }


def _serialize_summary(summary) -> dict | None:
    if summary is None:
        return None
    return {
        "method": summary.dataset.aggregation_method,
        "data_status": summary.dataset.status,
        "dataset_version": summary.dataset.version,
        "dominant_class_code": summary.dominant_class,
        "dominant_class_label": summary.dominant_label,
        "dominant_percent": _serialize_decimal(summary.dominant_percent),
        "mapped_percent": _serialize_decimal(summary.mapped_percent),
        "unmapped_percent": _serialize_decimal(summary.unmapped_percent),
        "conflict_percent": _serialize_decimal(summary.conflict_percent),
    }


def _serialize_dataset(dataset) -> dict | None:
    if dataset is None:
        return None
    return {
        "code": dataset.code,
        "name": dataset.name,
        "version": dataset.version,
        "source": dataset.source.name,
        "source_accessed_on": dataset.source_accessed_on.isoformat(),
        "map_date": None,
        "aggregation_method": dataset.aggregation_method,
        "data_status": dataset.status,
        "is_official_bacoor_assessment": False,
    }


def _serialize_decimal(value):
    if value is None:
        return None
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _warnings_for_dataset(mode: str, dataset) -> list[str]:
    warnings = list(warnings_for_mode(mode))
    if dataset is not None:
        warnings.extend(
            [
                MGB_PROVISIONAL_WARNING,
                MGB_DERIVATION_LIMITATION,
                MGB_COVERAGE_LIMITATION,
            ]
        )
    return warnings
