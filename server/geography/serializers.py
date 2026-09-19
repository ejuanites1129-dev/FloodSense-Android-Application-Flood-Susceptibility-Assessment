"""Input and response contracts for public geography API requests."""

from decimal import Decimal
from math import isfinite

from core.serializers import OperatingModeQuerySerializer
from rest_framework import serializers

from .constants import BACOOR_REFERENCE_LIMITATION, BACOOR_REFERENCE_WARNING

RESOLVER_PATH = "/api/v1/geography/resolve-barangay/"
RESOLVER_ALLOWED_METHODS = ("POST", "OPTIONS")
RESOLVER_CONTENT_TYPE = "application/json"
RESOLVER_COORDINATE_DECIMAL_PLACES = 5


class BarangayResolutionState:
    RESOLVED = "RESOLVED"
    OUTSIDE_BACOOR = "OUTSIDE_BACOOR"
    AMBIGUOUS_BOUNDARY = "AMBIGUOUS_BOUNDARY"
    UNAVAILABLE = "UNAVAILABLE"

    values = (
        RESOLVED,
        OUTSIDE_BACOOR,
        AMBIGUOUS_BOUNDARY,
        UNAVAILABLE,
    )


class FiniteJsonFloatField(serializers.FloatField):
    """Accept a finite JSON number rather than coercing strings or booleans."""

    default_error_messages = {
        "invalid": "Enter a JSON number.",
        "not_finite": "Enter a finite number.",
    }

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, (int, float, Decimal)):
            self.fail("invalid")
        value = super().to_internal_value(data)
        if not isfinite(value):
            self.fail("not_finite")
        return value


class PointResolutionRequestSerializer(OperatingModeQuerySerializer):
    """Validate one temporary WGS 84 coordinate."""

    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)


class BarangayResolutionRequestSerializer(serializers.Serializer):
    """Validate one temporary WGS 84 coordinate for the proposed resolver."""

    latitude = FiniteJsonFloatField(min_value=-90, max_value=90)
    longitude = FiniteJsonFloatField(min_value=-180, max_value=180)


class ResolutionCoordinateSerializer(serializers.Serializer):
    latitude = FiniteJsonFloatField(min_value=-90, max_value=90)
    longitude = FiniteJsonFloatField(min_value=-180, max_value=180)
    precision_decimal_places = serializers.IntegerField(
        min_value=RESOLVER_COORDINATE_DECIMAL_PLACES,
        max_value=RESOLVER_COORDINATE_DECIMAL_PLACES,
    )


class PublicBarangayIdentitySerializer(serializers.Serializer):
    psgc_code = serializers.RegexField(r"^\d{10}$")
    name = serializers.CharField(max_length=160, trim_whitespace=True)


class BoundaryReferenceStatusSerializer(serializers.Serializer):
    layer_kind = serializers.ChoiceField(("ADMINISTRATIVE_REFERENCE",))
    data_status = serializers.ChoiceField(("PENDING_VALIDATION",))
    source_status = serializers.ChoiceField(("PENDING_VALIDATION",))
    city_verified = serializers.BooleanField()

    def validate_city_verified(self, value):
        if value:
            raise serializers.ValidationError(
                "The controlled reference layer is not City-verified."
            )
        return value


class BarangayResolutionResponseSerializer(serializers.Serializer):
    """Allowlist and validate every proposed resolver response field."""

    resolution_state = serializers.ChoiceField(BarangayResolutionState.values)
    coordinate = ResolutionCoordinateSerializer()
    barangay = PublicBarangayIdentitySerializer(allow_null=True)
    boundary = BoundaryReferenceStatusSerializer()
    limitations = serializers.ListField(
        child=serializers.CharField(trim_whitespace=True),
        allow_empty=False,
    )

    def validate(self, attrs):
        is_resolved = attrs["resolution_state"] == BarangayResolutionState.RESOLVED
        if is_resolved != (attrs["barangay"] is not None):
            raise serializers.ValidationError(
                {"barangay": "Only RESOLVED responses may contain a barangay."}
            )
        required_limitations = {
            BACOOR_REFERENCE_WARNING,
            BACOOR_REFERENCE_LIMITATION,
        }
        if not required_limitations.issubset(attrs["limitations"]):
            raise serializers.ValidationError(
                {"limitations": "Required boundary limitations are missing."}
            )
        return attrs


def make_barangay_resolution_response(
    *,
    state: str,
    latitude: float,
    longitude: float,
    barangay: dict | None = None,
) -> dict:
    """Build one schema-validated, allowlisted response without any database write."""

    payload = {
        "resolution_state": state,
        "coordinate": {
            "latitude": round(latitude, RESOLVER_COORDINATE_DECIMAL_PLACES),
            "longitude": round(longitude, RESOLVER_COORDINATE_DECIMAL_PLACES),
            "precision_decimal_places": RESOLVER_COORDINATE_DECIMAL_PLACES,
        },
        "barangay": barangay,
        "boundary": {
            "layer_kind": "ADMINISTRATIVE_REFERENCE",
            "data_status": "PENDING_VALIDATION",
            "source_status": "PENDING_VALIDATION",
            "city_verified": False,
        },
        "limitations": [BACOOR_REFERENCE_WARNING, BACOOR_REFERENCE_LIMITATION],
    }
    serializer = BarangayResolutionResponseSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)
