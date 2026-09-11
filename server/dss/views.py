
"""Public DSS API views."""

from core.serializers import OperatingModeQuerySerializer
from expert.models import SusceptibilityLevel
from provenance.policies import data_status_for_mode, warnings_for_mode
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .services import GuidanceSelectionError, select_guidance_for_level


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
