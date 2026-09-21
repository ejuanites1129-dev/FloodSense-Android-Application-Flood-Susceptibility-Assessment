from django.apps import apps
from django.conf import settings


def test_simplejwt_refresh_rotation_uses_the_official_blacklist_app():
    assert apps.is_installed("rest_framework_simplejwt.token_blacklist")
    assert settings.SIMPLE_JWT["ROTATE_REFRESH_TOKENS"] is True
    assert settings.SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"] is True
