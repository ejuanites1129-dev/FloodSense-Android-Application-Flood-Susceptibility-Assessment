"""Executable wire contracts only; eligibility and distance remain later work.

Validate a wire-shaped mapping with ``data=...`` and ``is_valid()`` before
using ``.data``. These are deliberately not ModelSerializers and do not accept
model instances as proof of public eligibility.
"""

import re
from collections.abc import Mapping
from math import isfinite

from geography.constants import BACOOR_REFERENCE_LIMITATION, BACOOR_REFERENCE_WARNING
from rest_framework import serializers

from .contracts import (
    CENTER_LIMITATION,
    DEFAULT_LIMIT,
    DISTANCE_METHOD,
    DISTANCE_UNIT,
    DISTANCE_WARNING,
    EMPTY_DISTANCE_WARNING,
    EMPTY_WARNING,
    MAX_LIMIT,
    MIN_LIMIT,
)


class StrictObjectSerializer(serializers.Serializer):
    """Reject unknown keys without reflecting user-controlled keys or values."""

    def to_internal_value(self, data):
        if isinstance(data, Mapping) and set(data) - set(self.fields):
            raise serializers.ValidationError(
                {"non_field_errors": ["Unknown fields are not allowed."]}
            )
        return super().to_internal_value(data)


class FiniteJsonNumberField(serializers.FloatField):
    default_error_messages = {
        "invalid": "Enter a JSON number.",
        "not_finite": "Enter a finite number.",
    }

    def to_internal_value(self, data):
        if type(data) not in (int, float):
            self.fail("invalid")
        value = super().to_internal_value(data)
        if not isfinite(value):
            self.fail("not_finite")
        return value


class JsonIntegerField(serializers.IntegerField):
    default_error_messages = {"invalid": "Enter a JSON integer."}

    def to_internal_value(self, data):
        if type(data) is not int:
            self.fail("invalid")
        return super().to_internal_value(data)


class PublicTextField(serializers.CharField):
    """Nonempty literal text, never HTML; content still requires release review."""

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        if any(ord(char) < 32 and char not in "\n\t\r" for char in data):
            self.fail("invalid")
        return super().to_internal_value(data)


class PublicUUIDField(serializers.UUIDField):
    def to_internal_value(self, data):
        if (
            not isinstance(data, str)
            or re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", data)
            is None
        ):
            self.fail("invalid")
        return super().to_internal_value(data)


class ISODateField(serializers.DateField):
    def to_internal_value(self, data):
        if not isinstance(data, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", data) is None:
            self.fail("invalid", format="YYYY-MM-DD")
        return super().to_internal_value(data)


class NearestCenterRequestSerializer(StrictObjectSerializer):
    latitude = FiniteJsonNumberField(min_value=-90, max_value=90)
    longitude = FiniteJsonNumberField(min_value=-180, max_value=180)
    limit = JsonIntegerField(default=DEFAULT_LIMIT, min_value=MIN_LIMIT, max_value=MAX_LIMIT)


class CenterBarangaySerializer(StrictObjectSerializer):
    psgc_code = PublicTextField(trim_whitespace=False)
    name = PublicTextField(max_length=160)

    def validate_psgc_code(self, value):
        if re.fullmatch(r"[0-9]{10}", value) is None:
            raise serializers.ValidationError("Enter a ten-digit PSGC string.")
        return value


class PublicCenterSerializer(StrictObjectSerializer):
    public_identifier = PublicUUIDField()
    name = PublicTextField(max_length=180)
    address = PublicTextField()
    barangay = CenterBarangaySerializer()
    latitude = FiniteJsonNumberField(min_value=-90, max_value=90)
    longitude = FiniteJsonNumberField(min_value=-180, max_value=180)
    approximate_distance = FiniteJsonNumberField(min_value=0)
    distance_unit = serializers.ChoiceField((DISTANCE_UNIT,))
    verified_on = ISODateField(format="iso-8601", input_formats=("iso-8601",))
    source_attribution = PublicTextField(max_length=200)
    limitations = serializers.ListField(child=PublicTextField(), allow_empty=False)

    def validate_limitations(self, value):
        required = {CENTER_LIMITATION, BACOOR_REFERENCE_WARNING, BACOOR_REFERENCE_LIMITATION}
        if not required.issubset(value):
            raise serializers.ValidationError("Required public limitations are missing.")
        return value


class NearestCenterResponseSerializer(StrictObjectSerializer):
    centers = serializers.ListField(child=PublicCenterSerializer(), max_length=MAX_LIMIT)
    distance_method = serializers.ChoiceField((DISTANCE_METHOD,))
    warnings = serializers.ListField(child=PublicTextField(), allow_empty=False)

    def validate(self, attrs):
        expected = (
            [DISTANCE_WARNING] if attrs["centers"] else [EMPTY_WARNING, EMPTY_DISTANCE_WARNING]
        )
        if attrs["warnings"] != expected:
            raise serializers.ValidationError({"warnings": "Use the frozen result warning text."})
        identifiers = [center["public_identifier"] for center in attrs["centers"]]
        if len(identifiers) != len(set(identifiers)):
            raise serializers.ValidationError({"centers": "Public identifiers must be unique."})
        return attrs
