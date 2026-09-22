from django.conf import settings
from django.test import Client


def test_browser_api_cors_is_explicit_and_scoped():
    assert "corsheaders" in settings.INSTALLED_APPS
    assert "corsheaders.middleware.CorsMiddleware" in settings.MIDDLEWARE
    assert settings.CORS_URLS_REGEX == r"^/api/.*$"
    assert settings.CORS_ALLOWED_ORIGINS
    assert "*" not in settings.CORS_ALLOWED_ORIGINS


def test_configured_web_origin_can_preflight_api_but_not_admin_pages():
    origin = settings.CORS_ALLOWED_ORIGINS[0]
    client = Client()
    api_response = client.options(
        "/api/v1/assessment-options/",
        HTTP_ORIGIN=origin,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
    )
    assert api_response.headers["access-control-allow-origin"] == origin

    admin_response = client.options(
        "/management/login/",
        HTTP_ORIGIN=origin,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
    )
    assert "access-control-allow-origin" not in admin_response.headers
