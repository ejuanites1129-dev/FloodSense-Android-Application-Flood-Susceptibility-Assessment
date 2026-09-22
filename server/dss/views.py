
"""Public DSS API views."""

from core.serializers import OperatingModeQuerySerializer
from expert.models import SusceptibilityLevel
from provenance.policies import data_status_for_mode, warnings_for_mode
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import DSSFlowVersion
from .services import (
    GuidanceSelectionError,
    answer_dss_question,
    select_dss_flow,
    select_guidance_for_level,
    serialize_dss_question,
)


class GuidanceQuerySerializer(OperatingModeQuerySerializer):
    susceptibility_level = serializers.ChoiceField(
        choices=tuple(code for code, _label in SusceptibilityLevel.Code.choices)
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def guidance_collection(request):
    """Return applicable guidance for a controlled susceptibility level."""

    serializer = GuidanceQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    mode = serializer.validated_data["mode"]
    try:
        guidance = select_guidance_for_level(
            susceptibility_code=serializer.validated_data["susceptibility_level"],
            mode=mode,
        )
    except GuidanceSelectionError as error:
        detail = getattr(error, "message_dict", {"non_field_errors": error.messages})
        raise serializers.ValidationError(detail) from error

    return Response(
        {
            "susceptibility_level": serializer.validated_data[
                "susceptibility_level"
            ],
            "guidance": guidance,
            "operating_mode": mode,
            "data_status": data_status_for_mode(mode),
            "warnings": warnings_for_mode(mode),
        }
    )


class FlowContextSerializer(OperatingModeQuerySerializer):
    susceptibility_level = serializers.ChoiceField(
        choices=tuple(code for code, _label in SusceptibilityLevel.Code.choices)
    )


class FlowAnswerSerializer(FlowContextSerializer):
    question_code = serializers.SlugField(max_length=80)
    option_code = serializers.SlugField(max_length=80)


@api_view(["GET"])
@permission_classes([AllowAny])
def flow_start(request):
    serializer = FlowContextSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        flow = select_dss_flow(
            susceptibility_code=data["susceptibility_level"], mode=data["mode"]
        )
        question = flow.questions.prefetch_related("options").get(is_start=True)
    except GuidanceSelectionError as error:
        detail = getattr(error, "message_dict", {"flow": error.messages})
        raise serializers.ValidationError(detail) from error
    response = serialize_dss_question(flow, question)
    response["assessment_context"] = {
        "susceptibility_level": data["susceptibility_level"],
        "operating_mode": data["mode"],
    }
    response["history_persisted"] = False
    return Response(response)


@api_view(["POST"])
@permission_classes([AllowAny])
def flow_answer(request, code, version):
    serializer = FlowAnswerSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        selected = select_dss_flow(
            susceptibility_code=data["susceptibility_level"], mode=data["mode"]
        )
        if selected.code != code or selected.version != version:
            raise GuidanceSelectionError(
                {"flow": "This flow is not current for the assessment context."}
            )
        flow = DSSFlowVersion.objects.select_related("source").get(pk=selected.pk)
        response = answer_dss_question(
            flow=flow,
            question_code=data["question_code"],
            option_code=data["option_code"],
        )
    except GuidanceSelectionError as error:
        detail = getattr(error, "message_dict", {"flow": error.messages})
        raise serializers.ValidationError(detail) from error
    response["assessment_context"] = {
        "susceptibility_level": data["susceptibility_level"],
        "operating_mode": data["mode"],
    }
    response["history_persisted"] = False
    return Response(response)
