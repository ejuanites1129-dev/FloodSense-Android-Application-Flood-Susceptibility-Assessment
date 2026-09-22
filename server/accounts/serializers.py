from __future__ import annotations

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from expert.models import ScenarioOption
from geography.models import GeographicArea
from rest_framework import serializers

from .models import ResidentPreference, User, resident_username_validator
from .services import normalize_email, normalize_username


class RegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=3, max_length=30)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_username(self, value: str) -> str:
        value = normalize_username(value)
        try:
            resident_username_validator(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
        if "@" in value or User.objects.filter(
            resident_username__iexact=value
        ).exists():
            raise serializers.ValidationError("This username is unavailable.")
        return value

    def validate_email(self, value: str) -> str:
        value = normalize_email(value)
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("This email address is unavailable.")
        return value

    def validate(self, attrs):
        candidate = User(
            email=attrs.get("email", ""),
            resident_username=attrs.get("username"),
            display_name=attrs.get("username", ""),
        )
        try:
            password_validation.validate_password(attrs["password"], candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from error
        return attrs


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    remember_me = serializers.BooleanField(default=False)


class TokenSerializer(serializers.Serializer):
    refresh = serializers.CharField(trim_whitespace=False)


class EmailTokenSerializer(serializers.Serializer):
    token = serializers.CharField(trim_whitespace=False, max_length=200)


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=200)
    token = serializers.CharField(max_length=200, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_current_password(self, value: str) -> str:
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("The current password is incorrect.")
        return value

    def validate_new_password(self, value: str) -> str:
        try:
            password_validation.validate_password(value, self.context["request"].user)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
        return value


class AccountPatchSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=3, max_length=30)

    def validate_username(self, value: str) -> str:
        value = normalize_username(value)
        try:
            resident_username_validator(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
        query = User.objects.filter(resident_username__iexact=value).exclude(
            pk=self.context["request"].user.pk
        )
        if query.exists():
            raise serializers.ValidationError("This username is unavailable.")
        return value


class PreferenceSerializer(serializers.Serializer):
    home_barangay_id = serializers.IntegerField(allow_null=True, required=False)
    default_rainfall_intensity_id = serializers.IntegerField(
        allow_null=True, required=False
    )
    default_rainfall_duration_id = serializers.IntegerField(
        allow_null=True, required=False
    )
    high_contrast = serializers.BooleanField(required=False)
    reduce_motion = serializers.BooleanField(required=False)

    def validate_home_barangay_id(self, value):
        if value is None:
            return None
        try:
            return GeographicArea.objects.get(
                pk=value,
                area_type=GeographicArea.AreaType.BARANGAY,
                is_enabled=True,
            )
        except GeographicArea.DoesNotExist as error:
            raise serializers.ValidationError(
                "Choose an available barangay."
            ) from error

    def _scenario(self, value, category):
        if value is None:
            return None
        try:
            return ScenarioOption.objects.get(
                pk=value, category=category, is_enabled=True
            )
        except ScenarioOption.DoesNotExist as error:
            raise serializers.ValidationError(
                "Choose an available scenario option."
            ) from error

    def validate_default_rainfall_intensity_id(self, value):
        return self._scenario(value, ScenarioOption.Category.INTENSITY)

    def validate_default_rainfall_duration_id(self, value):
        return self._scenario(value, ScenarioOption.Category.DURATION)


def serialize_preferences(preference: ResidentPreference) -> dict[str, object]:
    return {
        "home_barangay": _related(preference.home_barangay),
        "default_rainfall_intensity": _related(
            preference.default_rainfall_intensity
        ),
        "default_rainfall_duration": _related(preference.default_rainfall_duration),
        "high_contrast": preference.high_contrast,
        "reduce_motion": preference.reduce_motion,
        "updated_at": preference.updated_at,
        "stores_precise_coordinates": False,
    }


def _related(value) -> dict[str, object] | None:
    if value is None:
        return None
    return {"id": value.pk, "code": value.code, "label": str(value)}
