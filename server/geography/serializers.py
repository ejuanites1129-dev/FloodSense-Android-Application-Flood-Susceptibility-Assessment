"""Input validation for public geography API requests."""

from core.serializers import OperatingModeQuerySerializer
from rest_framework import serializers


class PointResolutionRequestSerializer(OperatingModeQuerySerializer):
    """Validate one temporary WGS 84 coordinate."""

    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
