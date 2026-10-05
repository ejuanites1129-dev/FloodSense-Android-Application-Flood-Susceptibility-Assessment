"""One opt-in local environment; no alternate database or persistent test registry."""

from urllib.parse import urlsplit

from django.conf import settings


def local_testing_enabled(request=None):
    database = settings.DATABASES["default"]
    enabled = bool(
        settings.DEBUG
        and settings.ENABLE_LOCAL_TESTING
        and database.get("HOST") in {"localhost", "127.0.0.1", "::1"}
        and database.get("ENGINE") == "django.contrib.gis.db.backends.postgis"
    )
    if request is None or not enabled:
        return enabled
    return request.META.get("REMOTE_ADDR") in {"127.0.0.1", "::1"} and urlsplit(
        "http://" + request.get_host()
    ).hostname in {"localhost", "127.0.0.1", "::1"}
