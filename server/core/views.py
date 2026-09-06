from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Return a database-independent service readiness response."""

    return Response(
        {
            "status": "ok",
            "service": "FloodSense API",
            "data_status": "provisional_only",
            "message": (
                "No official Bacoor susceptibility classifications are published."
            ),
        }
    )

