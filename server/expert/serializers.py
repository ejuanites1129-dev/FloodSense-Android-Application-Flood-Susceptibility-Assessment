"""Input validation for Expert System API requests."""

from core.serializers import OperatingModeQuerySerializer
from rest_framework import serializers


class AssessmentRequestSerializer(OperatingModeQuerySerializer):
    geographic_area_id = serializers.IntegerField(min_value=1)
    rainfall_intensity_code = serializers.SlugField(max_length=80)
    rainfall_duration_code = serializers.SlugField(max_length=80)


class MapAssessmentRequestSerializer(OperatingModeQuerySerializer):
    rainfall_intensity_code = serializers.SlugField(max_length=80)
    rainfall_duration_code = serializers.SlugField(max_length=80)
