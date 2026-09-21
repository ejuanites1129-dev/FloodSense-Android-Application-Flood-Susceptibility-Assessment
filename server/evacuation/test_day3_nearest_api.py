"""HTTP boundary and synthetic PostGIS integration; no operational fixtures."""

import json
from io import BytesIO
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from django.apps import apps
from django.core.cache import cache
from django.core.handlers.asgi import ASGIRequest
from django.db import DatabaseError, connection
from django.test.utils import CaptureQueriesContext
from django.urls import Resolver404, resolve, reverse
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from .contracts import (
    DISTANCE_METHOD,
    DISTANCE_WARNING,
    EMPTY_DISTANCE_WARNING,
    EMPTY_WARNING,
    INTERNAL_ERROR_DETAIL,
    MALFORMED_JSON_DETAIL,
    METHOD_NOT_ALLOWED_DETAIL,
    NEAREST_CENTER_MAX_REQUEST_BYTES,
    NEAREST_CENTER_PATH,
    REQUEST_TOO_LARGE_DETAIL,
    THROTTLED_DETAIL,
    UNSUPPORTED_MEDIA_DETAIL,
)
from .serializers import NearestCenterResponseSerializer
from .services import find_nearest_eligible_centers
from .test_day2_nearest_service import center_factory as center_factory
from .test_day2_nearest_service import layer as layer
from .views import NearestCenterView

EMPTY = {
    "centers": [],
    "distance_method": DISTANCE_METHOD,
    "warnings": [EMPTY_WARNING, EMPTY_DISTANCE_WARNING],
}
POINT = {"latitude": 14.123456789, "longitude": 120.987654321}


@pytest.fixture(autouse=True)
def isolated_throttle_cache(settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": f"nearest-http-tests-{uuid4()}",
        }
    }
    # Independent of this developer's deployment override; test the frozen default.
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {"nearest_centers": "30/min"},
    }
    yield
    cache.clear()


@pytest.fixture
def client():
    return APIClient(enforce_csrf_checks=True)


@pytest.fixture
def lookup():
    with patch("evacuation.views.find_nearest_eligible_centers", return_value=EMPTY) as mock:
        yield mock


def post(client, payload=None, **headers):
    return client.post(
        NEAREST_CENTER_PATH,
        data=json.dumps(POINT if payload is None else payload),
        content_type="application/json",
        **headers,
    )


def assert_headers(response):
    assert response["Content-Type"] == "application/json"
    assert response["Cache-Control"] == "no-store"
    assert response["Pragma"] == "no-cache"
    assert set(response["Allow"].replace(" ", "").split(",")) == {"POST", "OPTIONS"}
    assert not response.cookies
    assert "Location" not in response


def assert_error(response, status, detail):
    assert_headers(response)
    assert response.status_code == status
    assert response.json() == {"detail": detail}


def test_only_exact_nearest_route_is_exposed():
    assert reverse("evacuation:nearest-centers") == NEAREST_CENTER_PATH
    assert resolve(NEAREST_CENTER_PATH).func.view_class is NearestCenterView
    for path in ("", "1/", "search/", "nearest.json"):
        with pytest.raises(Resolver404):
            resolve("/api/v1/evacuation-centers/" + path)


@pytest.mark.parametrize("authorization", [None, "Bearer broken-token", "Basic invalid"])
def test_public_csrf_free_access_ignores_authorization(client, lookup, authorization):
    headers = {"HTTP_AUTHORIZATION": authorization} if authorization else {}
    response = post(client, **headers)
    assert response.status_code == 200
    assert_headers(response)
    assert response.json() == EMPTY
    lookup.assert_called_once_with(**POINT, limit=3)


def test_public_lookup_never_invokes_susceptibility_inference(client, lookup):
    with patch("expert.services.evaluate_assessment") as inference:
        response = post(client)
    assert response.status_code == 200
    lookup.assert_called_once_with(**POINT, limit=3)
    inference.assert_not_called()


@pytest.mark.parametrize("accept", ["application/json", "text/html", "*/*", "application/xml"])
def test_json_only_even_in_debug_and_with_format_preferences(client, lookup, settings, accept):
    settings.DEBUG = True
    response = client.post(
        NEAREST_CENTER_PATH + "?format=api",
        data=json.dumps(POINT),
        content_type="application/json",
        HTTP_ACCEPT=accept,
    )
    assert response.status_code == 200
    assert_headers(response)
    assert b"<html" not in response.content
    lookup.assert_called_once()


@pytest.mark.parametrize("method", ["GET", "HEAD", "PUT", "PATCH", "DELETE", "TRACE"])
def test_unsupported_methods_do_not_parse_throttle_or_lookup(client, lookup, method):
    with patch("evacuation.views.LimitedJSONParser.parse") as parse:
        with patch("evacuation.throttles.NearestCenterThrottle.allow_request") as throttle:
            response = client.generic(method, NEAREST_CENTER_PATH, b"invalid", "text/plain")
    assert_headers(response)
    assert response.status_code == 405
    if method == "HEAD":
        assert response.content == b""  # HTTP removes the body, not the status/headers.
    else:
        assert response.json() == {"detail": METHOD_NOT_ALLOWED_DETAIL}
    lookup.assert_not_called()
    parse.assert_not_called()
    throttle.assert_not_called()


def test_options_has_json_metadata_and_no_lookup_or_throttle(client, lookup):
    with patch("evacuation.throttles.NearestCenterThrottle.allow_request") as throttle:
        response = client.options(NEAREST_CENTER_PATH)
    assert response.status_code == 200
    assert_headers(response)
    assert response.json()["renders"] == ["application/json"]
    assert response.json()["parses"] == ["application/json"]
    lookup.assert_not_called()
    throttle.assert_not_called()


@pytest.mark.parametrize("media", ["application/json", "application/json; charset=utf-8"])
def test_json_media_types(client, lookup, media):
    response = client.generic("POST", NEAREST_CENTER_PATH, json.dumps(POINT), media)
    assert response.status_code == 200
    assert_headers(response)
    lookup.assert_called_once()


@pytest.mark.parametrize(
    "media",
    [
        "application/x-www-form-urlencoded",
        "multipart/form-data; boundary=abc",
        "text/plain",
        "application/xml",
        "",
        "application/vnd.example+json",
    ],
)
@pytest.mark.parametrize("body", [b"", b"PRIVATE_BODY_SENTINEL"])
def test_unsupported_or_missing_media_is_safe_even_for_empty_body(client, lookup, media, body):
    response = client.generic("POST", NEAREST_CENTER_PATH, body, media)
    assert_error(response, 415, UNSUPPORTED_MEDIA_DETAIL)
    lookup.assert_not_called()


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b'{"latitude": 14.123456789,',
        b"PRIVATE_BODY_SENTINEL",
        b"\xff",
        b'{"latitude": NaN, "longitude": 0}',
        b'{"latitude": Infinity, "longitude": 0}',
        b'{"latitude": 0, "longitude": -Infinity}',
        b'{"latitude": 0, "latitude": 1, "longitude": 0}',
        b'{"latitude": 0, "longitude": 0, "metadata": {"a": 1, "a": 2}}',
    ],
)
def test_malformed_json_has_no_fragments(client, lookup, body):
    response = client.generic("POST", NEAREST_CENTER_PATH, body, "application/json")
    assert_error(response, 400, MALFORMED_JSON_DETAIL)
    lookup.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"latitude": 0},
        {"longitude": 0},
        {"latitude": None, "longitude": 0},
        {"latitude": 0, "longitude": None},
        {"latitude": "14.123456789", "longitude": 0},
        {"latitude": 0, "longitude": "120.987654321"},
        {"latitude": True, "longitude": 0},
        {"latitude": 0, "longitude": False},
        {"latitude": -91, "longitude": 0},
        {"latitude": 91, "longitude": 0},
        {"latitude": 0, "longitude": -181},
        {"latitude": 0, "longitude": 181},
        {**POINT, "limit": 0},
        {**POINT, "limit": 11},
        {**POINT, "limit": 3.0},
        {**POINT, "limit": True},
        {**POINT, "limit": None},
        {**POINT, "limit": "3"},
        [],
        "PRIVATE_BODY_SENTINEL",
        123,
    ],
)
def test_field_validation_precedes_service_and_does_not_reflect_input(client, lookup, payload):
    response = post(client, payload)
    assert response.status_code == 400
    assert_headers(response)
    for value in (b"14.123456789", b"120.987654321", b"PRIVATE_BODY_SENTINEL"):
        assert value not in response.content
    lookup.assert_not_called()


def test_unknown_fields_have_exact_frozen_error(client, lookup):
    response = post(client, {**POINT, "PRIVATE_KEY_SENTINEL": "PRIVATE_BODY_SENTINEL"})
    assert response.status_code == 400
    assert_headers(response)
    assert response.json() == {"non_field_errors": ["Unknown fields are not allowed."]}
    lookup.assert_not_called()


@pytest.mark.parametrize("limit", [1, 3, 10])
def test_requested_limit_is_passed_exactly(client, lookup, limit):
    response = post(client, {**POINT, "limit": limit})
    assert response.status_code == 200
    lookup.assert_called_once_with(**POINT, limit=limit)


def test_query_headers_and_cookies_cannot_supply_coordinates(client, lookup):
    client.cookies["latitude"] = "14.123456789"
    response = client.post(
        NEAREST_CENTER_PATH + "?latitude=14.123456789&longitude=120.987654321",
        data="{}",
        content_type="application/json",
        HTTP_LATITUDE="14.123456789",
        HTTP_LONGITUDE="120.987654321",
    )
    assert response.status_code == 400
    assert set(response.json()) == {"latitude", "longitude"}
    assert_headers(response)
    lookup.assert_not_called()


@pytest.mark.parametrize("size", [1023, 1024, 1025])
def test_actual_byte_boundary(client, lookup, size):
    body = json.dumps(POINT).encode()
    response = client.generic(
        "POST", NEAREST_CENTER_PATH, body.ljust(size, b" "), "application/json"
    )
    if size <= NEAREST_CENTER_MAX_REQUEST_BYTES:
        assert response.status_code == 200
        assert_headers(response)
        lookup.assert_called_once()
    else:
        assert_error(response, 413, REQUEST_TOO_LARGE_DETAIL)
        lookup.assert_not_called()


def test_declared_oversize_rejects_before_reading_or_parsing(client, lookup):
    with patch("evacuation.views.LimitedJSONParser.parse") as parse:
        response = post(client, CONTENT_LENGTH="999999")
    assert_error(response, 413, REQUEST_TOO_LARGE_DETAIL)
    parse.assert_not_called()
    lookup.assert_not_called()


@pytest.mark.parametrize("declared", [None, "0", "1"])
@pytest.mark.parametrize("oversized", [False, True])
def test_asgi_actual_stream_checked_independently_of_declared_length(lookup, declared, oversized):
    body = json.dumps(POINT).encode()
    if oversized:
        body += b" " * 2048
    stream = BytesIO(body)
    headers = [(b"content-type", b"application/json")]
    if declared is not None:
        headers.append((b"content-length", declared.encode()))
    request = ASGIRequest(
        {
            "type": "http",
            "method": "POST",
            "path": NEAREST_CENTER_PATH,
            "headers": headers,
            "client": ("127.0.0.1", 12345),
        },
        stream,
    )
    response = NearestCenterView.as_view()(request)
    response.render()
    assert_headers(response)
    if oversized:
        assert response.status_code == 413
        assert response.data == {"detail": REQUEST_TOO_LARGE_DETAIL}
        assert stream.tell() == 1025
        lookup.assert_not_called()
    else:
        assert response.status_code == 200
        lookup.assert_called_once_with(**POINT, limit=3)


@pytest.mark.parametrize(
    "exception",
    [
        DatabaseError("PRIVATE SQL table coordinate 14.123456789"),
        RuntimeError("PRIVATE stack C:/internal/path 120.987654321"),
        ValidationError({"PRIVATE": "Broken internal response invariant"}),
    ],
)
def test_service_failure_is_generic_500_without_exception_logging(
    client, lookup, caplog, settings, exception
):
    settings.DEBUG = True
    lookup.side_effect = exception
    response = post(client)
    assert_error(response, 500, INTERNAL_ERROR_DETAIL)
    assert "PRIVATE" not in caplog.text
    assert "14.123456789" not in caplog.text
    assert "120.987654321" not in caplog.text
    assert not [r for r in caplog.records if r.name.startswith("evacuation")]


def test_default_throttle_31st_request_and_retry_after(client, lookup):
    for _ in range(30):
        assert post(client).status_code == 200
    response = post(client)
    assert_error(response, 429, THROTTLED_DETAIL)
    assert 1 <= int(response["Retry-After"]) <= 60
    assert lookup.call_count == 30
    assert client.options(NEAREST_CENTER_PATH).status_code == 200
    assert client.get(NEAREST_CENTER_PATH).status_code == 405
    assert post(client, REMOTE_ADDR="127.0.0.2").status_code == 200


def test_throttle_override_and_forwarded_headers_cannot_bypass_or_store_location(
    client, lookup, settings
):
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {"nearest_centers": "1/min"},
    }
    with patch.object(cache, "set", wraps=cache.set) as save:
        assert post(client, HTTP_X_FORWARDED_FOR="PRIVATE_BODY_SENTINEL").status_code == 200
        response = post(client, {"latitude": 0, "longitude": 0}, HTTP_X_FORWARDED_FOR="other")
    assert_error(response, 429, THROTTLED_DETAIL)
    assert lookup.call_count == 1
    key, timestamps, ttl = save.call_args.args
    assert key == "throttle_nearest_centers_127.0.0.1"
    assert ttl == 60
    assert len(timestamps) == 1 and isinstance(timestamps[0], float)
    assert "14.123456789" not in repr(save.call_args)
    assert "PRIVATE_BODY_SENTINEL" not in repr(save.call_args)


def test_throttle_window_expires(client, lookup, settings):
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {"nearest_centers": "1/min"},
    }
    with patch("evacuation.throttles.NearestCenterThrottle.timer", return_value=1000):
        assert post(client).status_code == 200
        assert post(client).status_code == 429
    with patch("evacuation.throttles.NearestCenterThrottle.timer", return_value=1061):
        assert post(client).status_code == 200


def test_real_populated_http_preserves_service_order_and_safe_projection(client, center_factory):
    center_factory(longitude=2, public_id=UUID(int=1))
    center_factory(longitude=1, public_id=UUID(int=3))
    center_factory(longitude=1, public_id=UUID(int=2))
    # An ineligible nearer row must never enter public output.
    center_factory(name="PRIVATE DRAFT", verification_status="DRAFT")
    point = {"latitude": 0, "longitude": 0}
    expected = find_nearest_eligible_centers(**point)
    response = post(client, point)
    assert response.status_code == 200
    assert_headers(response)
    assert response.json() == expected
    assert [row["public_identifier"] for row in response.json()["centers"]] == [
        str(UUID(int=i)) for i in (2, 3, 1)
    ]
    assert response.json()["warnings"] == [DISTANCE_WARNING]
    serializer = NearestCenterResponseSerializer(data=response.json())
    assert serializer.is_valid(), serializer.errors
    assert b"PRIVATE" not in response.content
    for center in response.json()["centers"]:
        assert set(center) == {
            "public_identifier",
            "name",
            "address",
            "barangay",
            "latitude",
            "longitude",
            "approximate_distance",
            "distance_unit",
            "verified_on",
            "source_attribution",
            "limitations",
        }
        assert center["barangay"]["psgc_code"] == "0000000000"
        assert isinstance(center["approximate_distance"], float)


@pytest.mark.django_db
def test_real_empty_database_and_ready_empty_inventory(client):
    response = post(client)
    assert response.status_code == 200
    assert response.json() == EMPTY
    assert_headers(response)


def test_real_ready_empty_inventory(client, layer):
    response = post(client)
    assert response.status_code == 200
    assert response.json() == EMPTY
    assert_headers(response)


def snapshot_database():
    return {
        model._meta.label: list(model.objects.order_by(model._meta.pk.name).values())
        for model in apps.get_models()
    }


def test_repeated_http_is_select_only_no_sessions_audit_or_other_writes(
    client, center_factory, caplog
):
    center_factory()
    before = snapshot_database()
    with CaptureQueriesContext(connection) as queries:
        responses = [post(client) for _ in range(2)]
    assert all(response.status_code == 200 for response in responses)
    assert len(queries) == 8
    assert all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries)
    assert snapshot_database() == before
    for response in responses:
        assert_headers(response)
        assert b"14.123456789" not in response.content
        assert b"120.987654321" not in response.content
    assert not [r for r in caplog.records if r.name.startswith("evacuation")]


def test_endpoint_query_count_stable_and_ten_center_cap(client, center_factory):
    center_factory()
    with CaptureQueriesContext(connection) as small:
        assert post(client).status_code == 200
    for index in range(20):
        center_factory(longitude=index + 1)
    with CaptureQueriesContext(connection) as large:
        response = post(client, {**POINT, "limit": 10})
    assert len(small) == len(large) == 4
    assert len(response.json()["centers"]) == 10
    # Representative fixture size, not a universal text-byte bound.
    assert len(response.content) < 16000


def test_rejections_and_options_have_no_database_queries_or_writes(client, center_factory, lookup):
    center_factory()
    before = snapshot_database()
    with CaptureQueriesContext(connection) as queries:
        assert client.get(NEAREST_CENTER_PATH).status_code == 405
        assert client.options(NEAREST_CENTER_PATH).status_code == 200
        assert post(client, {}).status_code == 400
        assert client.generic("POST", NEAREST_CENTER_PATH, b"bad", "text/plain").status_code == 415
        assert (
            client.generic("POST", NEAREST_CENTER_PATH, b"bad", "application/json").status_code
            == 400
        )
        assert post(client, CONTENT_LENGTH="2048").status_code == 413
    assert len(queries) == 0
    assert snapshot_database() == before
    lookup.assert_not_called()
