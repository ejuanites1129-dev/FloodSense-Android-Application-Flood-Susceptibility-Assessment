
"""Public GeoJSON views for supported FloodSense areas."""

import json

from core.serializers import OperatingModeQuerySerializer
from provenance.policies import (
    DEMONSTRATION_MODE,
    data_status_for_mode,
    permitted_records,
    warnings_for_mode,
)
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import GeographicArea
from .serializers import PointResolutionRequestSerializer
from .services import PointResolutionInputError, resolve_area_for_point


@api_view(["GET"])
@permission_classes([AllowAny])
def area_collection(request):
    """Return enabled, mode-permitted area polygons as a GeoJSON collection."""

    serializer = OperatingModeQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    mode = serializer.validated_data["mode"]
    areas = GeographicArea.objects.select_related("source").filter(is_enabled=True)
    if mode == DEMONSTRATION_MODE:
        areas = areas.filter(area_type=GeographicArea.AreaType.DEMO_ZONE)
    areas = permitted_records(areas, mode).order_by("name", "id")

    return Response(
        {
            "type": "FeatureCollection",
            "features": [_serialize_area_feature(area) for area in areas],
            "operating_mode": mode,
            "data_status": data_status_for_mode(mode),
            "warnings": warnings_for_mode(mode),
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


def _serialize_area_feature(area: GeographicArea) -> dict:
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
            "source": {
                "id": area.source_id,
                "name": area.source.name,
                "organization": area.source.organization,
                "status": area.source.status,
            },
        },
    }
