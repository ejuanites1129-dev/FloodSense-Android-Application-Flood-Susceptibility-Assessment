"""Request serializers shared by the versioned FloodSense API."""

from provenance.policies import normalize_operating_mode
from rest_framework import serializers


class OperatingModeQuerySerializer(serializers.Serializer):
    """Validate and normalize a public API operating-mode query parameter."""

    mode = serializers.CharField(default="demonstration", trim_whitespace=True)

    def validate_mode(self, value: str) -> str:
        try:
            return normalize_operating_mode(value)
        except ValueError as error:
            raise serializers.ValidationError(str(error)) from error
