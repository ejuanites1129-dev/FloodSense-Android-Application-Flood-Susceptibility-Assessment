
"""Public API views for assessment inputs and deterministic evaluation."""

from decimal import Decimal

from core.serializers import OperatingModeQuerySerializer
from dss.services import select_guidance
from provenance.policies import (
    data_status_for_mode,
    permitted_records,
    warnings_for_mode,
)
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import ScenarioOption
from .serializers import AssessmentRequestSerializer, MapAssessmentRequestSerializer
from .services import AssessmentInputError, evaluate_assessment, evaluate_map_scenario


@api_view(["GET"])
@permission_classes([AllowAny])
def assessment_options(request):
    """Return enabled rainfall options permitted for the requested mode."""

    serializer = OperatingModeQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    mode = serializer.validated_data["mode"]
    options = permitted_records(
        ScenarioOption.objects.select_related("source").filter(is_enabled=True),
        mode,
    ).order_by("category", "display_order", "label", "id")

    serialized_options = [_serialize_scenario_option(option) for option in options]
    return Response(
        {
            "intensity_options": [
                option
                for option in serialized_options
                if option["category"] == ScenarioOption.Category.INTENSITY
            ],
            "duration_options": [
                option
                for option in serialized_options
                if option["category"] == ScenarioOption.Category.DURATION
            ],
            "operating_mode": mode,
            "data_status": data_status_for_mode(mode),
            "warnings": warnings_for_mode(mode),
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def evaluate(request):
    """Evaluate a scenario and append DSS guidance only when classified."""

    serializer = AssessmentRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    inputs = serializer.validated_data
    try:
        result = evaluate_assessment(
            area_identifier=inputs["geographic_area_id"],
            intensity_code=inputs["rainfall_intensity_code"],
            duration_code=inputs["rainfall_duration_code"],
            mode=inputs["mode"],
        )
    except AssessmentInputError as error:
        detail = getattr(error, "message_dict", {"non_field_errors": error.messages})
        raise serializers.ValidationError(detail) from error

    return Response({**result, "guidance": select_guidance(result)})


@api_view(["POST"])
@permission_classes([AllowAny])
def evaluate_map(request):
    """Return lightweight Expert System results for every eligible map area."""

    serializer = MapAssessmentRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    inputs = serializer.validated_data
    try:
        result = evaluate_map_scenario(
            intensity_code=inputs["rainfall_intensity_code"],
            duration_code=inputs["rainfall_duration_code"],
            mode=inputs["mode"],
        )
    except AssessmentInputError as error:
        detail = getattr(error, "message_dict", {"non_field_errors": error.messages})
        raise serializers.ValidationError(detail) from error
    return Response(result)


def _serialize_scenario_option(option: ScenarioOption) -> dict:
    return {
        "id": option.id,
        "category": option.category,
        "code": option.code,
        "label": option.label,
        "derived_value": _serialize_decimal(option.derived_value),
        "unit": option.unit,
        "display_order": option.display_order,
        "data_status": option.status,
    }


def _serialize_decimal(value: Decimal | None) -> int | float | None:
    if value is None:
        return None
    if value == value.to_integral_value():
        return int(value)
    return float(value)
