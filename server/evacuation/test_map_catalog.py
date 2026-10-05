"""Synthetic catalog fixtures in an isolated PostGIS test database only."""

from datetime import date
from uuid import UUID

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from provenance.models import DataSource, PublicationStatus
from rest_framework.test import APIClient

from . import test_day2_nearest_service as reference_fixtures
from .catalog import (
    EMPTY_MAP_WARNING,
    LOCAL_EMPTY_MAP_WARNING,
    MAP_INPUT_ERROR,
    MAP_INTERNAL_ERROR,
    MAP_LIMIT_WARNING,
    MAP_MAX_CENTERS,
    MAP_NEARBY_CENTERS,
    MAP_NEARBY_LIMIT_WARNING,
    MAP_WARNING,
    LocalMapResponseSerializer,
    MapCenterResponseSerializer,
)
from .local_preview import LOCAL_PREVIEW_WARNING
from .models import EvacuationCenter

pytestmark = pytest.mark.django_db
layer = reference_fixtures.layer
center_factory = reference_fixtures.center_factory
URL = "/api/v1/evacuation-centers/map/"
PUBLIC_FIELDS = {
    "public_identifier",
    "name",
    "address",
    "barangay",
    "latitude",
    "longitude",
    "verified_on",
    "source_attribution",
    "limitations",
}


@pytest.fixture(autouse=True)
def regular_settings(settings):
    settings.ENABLE_LOCAL_TESTING = False
    settings.ENABLE_LOCAL_CENTER_PREVIEW = False
    settings.ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
    cache.clear()


@pytest.fixture
def testing_settings(settings):
    settings.DEBUG = True
    settings.ENABLE_LOCAL_TESTING = True


@pytest.fixture
def temporary_center(layer):
    reviewer = get_user_model().objects.create_user(email="synthetic-reviewer@example.test")
    source = DataSource.objects.create(
        name="Synthetic temporary source",
        organization="Synthetic local test attribution",
        source_type=DataSource.SourceType.DEMONSTRATION,
        status=PublicationStatus.DEMONSTRATION,
        is_publicly_releasable=False,
        reviewed_by=reviewer,
        reviewed_on=date(2026, 10, 5),
        notes="PRIVATE TEMP SOURCE SENTINEL",
    )
    return EvacuationCenter.objects.create(
        name="Synthetic temporary center, no legacy naming requirement",
        address="Synthetic local test address",
        geographic_area=layer[2][0],
        latitude=0.5,
        longitude=0.5,
        source=source,
        publication_status=PublicationStatus.DEMONSTRATION,
        verification_status=EvacuationCenter.VerificationStatus.VERIFIED,
        verified_on=None,
        capacity=None,
        contact_information="PRIVATE TEMP CONTACT SENTINEL",
    )


def get(**kwargs):
    return APIClient().get(URL, HTTP_HOST="127.0.0.1", **kwargs)


def assert_empty(response, *, temporary=False):
    assert response.status_code == 200
    expected = {
        "centers": [],
        "warnings": [EMPTY_MAP_WARNING, MAP_WARNING],
        "has_more": False,
    }
    if temporary:
        expected["data_status"] = "DEMONSTRATION"
        expected["warnings"] = [LOCAL_PREVIEW_WARNING, LOCAL_EMPTY_MAP_WARNING, MAP_WARNING]
    assert response.json() == expected


def test_catalog_has_allowlisted_public_records_without_location_or_database_writes(center_factory):
    center = center_factory(latitude=0.5, longitude=0.5)
    # Public discovery needs no valid JWT, including when stale auth is attached.
    with CaptureQueriesContext(connection) as queries:
        response = get(HTTP_AUTHORIZATION="Bearer stale-token")
    assert response.status_code == 200
    result = response.json()
    assert set(result) == {"centers", "warnings", "has_more"}
    assert result["warnings"] == [MAP_WARNING]
    assert result["has_more"] is False
    row = result["centers"][0]
    assert set(row) == PUBLIC_FIELDS
    assert set(row["barangay"]) == {"psgc_code", "name"}
    assert row["public_identifier"] == str(center.public_id)
    assert row["verified_on"] == "2026-09-19"
    assert "PRIVATE" not in response.content.decode()
    assert "distance" not in row
    assert not any(
        query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        for query in queries
    )
    assert len(queries) <= 6
    assert response["Cache-Control"] == "no-store"
    assert response["Pragma"] == "no-cache"
    assert response["Allow"] == "GET, POST, OPTIONS"
    schema = MapCenterResponseSerializer(data=result)
    assert schema.is_valid(), schema.errors


@pytest.mark.parametrize("method", ["put", "patch", "delete", "head", "trace"])
def test_only_get_post_and_metadata_are_supported(method):
    with CaptureQueriesContext(connection) as queries:
        response = getattr(APIClient(), method)(URL, HTTP_HOST="127.0.0.1")
    assert response.status_code == 405
    assert len(queries) == 0
    assert response["Allow"] == "GET, POST, OPTIONS"
    assert response["Cache-Control"] == "no-store"


def test_options_metadata_never_queries_or_requests_location():
    with CaptureQueriesContext(connection) as queries:
        response = APIClient().options(URL, HTTP_HOST="127.0.0.1")
    assert response.status_code == 200
    assert len(queries) == 0
    assert response["Allow"] == "GET, POST, OPTIONS"
    assert response["Cache-Control"] == "no-store"


@pytest.mark.parametrize("input_kind", ["query", "body"])
def test_catalog_rejects_inputs_without_echoing_or_querying(input_kind):
    with CaptureQueriesContext(connection) as queries:
        client = APIClient()
        if input_kind == "query":
            response = client.get(URL + "?latitude=12.345678&longitude=123.456789")
        else:
            response = client.generic("GET", URL, b'{"latitude":12.345678}', "application/json")
    assert response.status_code == 400
    assert response.json() == {"detail": MAP_INPUT_ERROR}
    assert "12.345678" not in response.content.decode()
    assert len(queries) == 0
    assert response["Cache-Control"] == "no-store"


def test_honest_empty_without_reference_or_eligible_records():
    assert_empty(get())


@pytest.mark.parametrize(
    "changes",
    [
        {"verification_status": "DRAFT"},
        {"verification_status": "IN_REVIEW"},
        {"verification_status": "INACTIVE"},
        {"publication_status": "PENDING_VALIDATION"},
        {"publication_status": "DEMONSTRATION"},
        {"publication_status": "RESTRICTED"},
        {"verified_on": None},
        {"geographic_area": None},
        {"latitude": 91},
        {"longitude": 181},
        {"latitude": 2},  # outside the assigned supported barangay
        {"name": ""},
        {"address": ""},
        {"limitations": "bad\x01limitation"},
    ],
)
def test_rechecks_center_eligibility_and_public_shape_on_each_call(center_factory, changes):
    center = center_factory(latitude=0.5, longitude=0.5)
    assert len(get().json()["centers"]) == 1
    EvacuationCenter.objects.filter(pk=center.pk).update(**changes)
    assert_empty(get())


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "PENDING_VALIDATION"},
        {"status": "RESTRICTED"},
        {"status": "RETIRED"},
        {"is_publicly_releasable": False},
        {"source_type": "DEMONSTRATION"},
        {"organization": ""},
        {"limitations": "bad\x01restriction"},
    ],
)
def test_source_revocation_and_malformed_public_metadata_are_excluded(center_factory, changes):
    center = center_factory(latitude=0.5, longitude=0.5)
    assert len(get().json()["centers"]) == 1
    DataSource.objects.filter(pk=center.source_id).update(**changes)
    assert_empty(get())


@pytest.mark.parametrize("damage", ["missing_barangay", "disabled", "outside_city", "bad_status"])
def test_complete_reference_integrity_is_required(layer, center_factory, damage):
    center_factory(latitude=0.5, longitude=0.5)
    area = layer[2][-1]
    if damage == "missing_barangay":
        area.delete()
    elif damage == "disabled":
        area.is_enabled = False
        area.save()
    elif damage == "outside_city":
        area.geometry = reference_fixtures.box(left=99, right=100)
        area.save()
    else:
        area.status = PublicationStatus.RETIRED
        area.save()
    assert_empty(get())


def test_polygon_holes_exclude_centers(layer, center_factory):
    from django.contrib.gis.geos import MultiPolygon, Polygon

    area = layer[2][0]
    area.geometry = MultiPolygon(
        Polygon(
            ((0, 0), (1, 0), (1, 1), (0, 1), (0, 0)),
            ((0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6), (0.4, 0.4)),
        ),
        srid=4326,
    )
    area.save()
    center_factory(latitude=0.5, longitude=0.5)
    assert_empty(get())


def test_local_approved_records_use_same_catalog_but_never_mix_with_genuine_records(
    testing_settings, temporary_center, center_factory, settings
):
    center_factory(latitude=0.5, longitude=0.5)
    result = get().json()
    assert set(result) == {"data_status", "centers", "warnings", "has_more"}
    assert result["data_status"] == "DEMONSTRATION"
    assert len(result["centers"]) == 1
    row = result["centers"][0]
    assert set(row) == PUBLIC_FIELDS | {"data_status"}
    assert row["public_identifier"] == str(temporary_center.public_id)
    assert row["data_status"] == "DEMONSTRATION"
    assert row["verified_on"] is None
    assert result["warnings"] == [LOCAL_PREVIEW_WARNING, MAP_WARNING]
    assert row["limitations"][0] == LOCAL_PREVIEW_WARNING
    schema = LocalMapResponseSerializer(data=result, context={"require_test_name": False})
    assert schema.is_valid(), schema.errors
    settings.ENABLE_LOCAL_TESTING = False
    genuine = get().json()
    assert "data_status" not in genuine
    assert len(genuine["centers"]) == 1
    assert genuine["centers"][0]["public_identifier"] != str(temporary_center.public_id)


@pytest.mark.parametrize(
    "gate", ["disabled", "production", "remote_database", "remote_client", "remote_host", "legacy"]
)
def test_temporary_catalog_never_leaks_outside_local_testing(
    testing_settings, temporary_center, settings, gate
):
    kwargs = {}
    if gate == "disabled":
        settings.ENABLE_LOCAL_TESTING = False
    elif gate == "production":
        settings.DEBUG = False
    elif gate == "remote_database":
        settings.DATABASES = {
            "default": {**settings.DATABASES["default"], "HOST": "database.example.test"}
        }
    elif gate == "remote_client":
        kwargs["REMOTE_ADDR"] = "192.0.2.10"
    elif gate == "remote_host":
        response = APIClient().get(URL, HTTP_HOST="testserver")
        assert_empty(response)
        return
    else:
        settings.ENABLE_LOCAL_TESTING = False
        settings.ENABLE_LOCAL_CENTER_PREVIEW = True
    assert_empty(get(**kwargs))


@pytest.mark.parametrize(
    "changes",
    [
        {"verification_status": "DRAFT"},
        {"verification_status": "IN_REVIEW"},
        {"verification_status": "INACTIVE"},
        {"publication_status": "APPROVED"},
        {"verified_on": date(2026, 10, 5)},
        {"capacity": 50},
        {"latitude": 2},
    ],
)
def test_unapproved_or_unsafe_temporary_records_excluded(
    testing_settings, temporary_center, changes
):
    EvacuationCenter.objects.filter(pk=temporary_center.pk).update(**changes)
    assert_empty(get(), temporary=True)


@pytest.mark.parametrize(
    "changes",
    [
        {"reviewed_on": None},
        {"reviewed_by": None},
        {"status": "RESTRICTED"},
        {"status": "APPROVED"},
        {"is_publicly_releasable": True},
    ],
)
def test_temporary_source_approval_rechecked(testing_settings, temporary_center, changes):
    DataSource.objects.filter(pk=temporary_center.source_id).update(**changes)
    assert_empty(get(), temporary=True)


def test_safe_candidates_count_toward_limit_and_stable_uuid_order(center_factory):
    template = center_factory(latitude=0.5, longitude=0.5)
    values = {
        field.attname: getattr(template, field.attname)
        for field in EvacuationCenter._meta.concrete_fields
        if field.name not in {"id", "public_id"}
    }
    template.delete()
    EvacuationCenter.objects.bulk_create(
        [
            EvacuationCenter(
                **{**values, "name": "" if index == 1 else f"SYNTHETIC center {index}"},
                public_id=UUID(int=index),
            )
            for index in range(1, MAP_MAX_CENTERS + 3)
        ]
    )
    result = get().json()
    assert len(result["centers"]) == MAP_MAX_CENTERS
    assert result["has_more"] is True
    assert result["warnings"] == [MAP_WARNING, MAP_LIMIT_WARNING]
    identifiers = [row["public_identifier"] for row in result["centers"]]
    assert identifiers == [str(UUID(int=index)) for index in range(2, MAP_MAX_CENTERS + 2)]
    EvacuationCenter.objects.filter(public_id=UUID(int=MAP_MAX_CENTERS + 2)).delete()
    assert get().json()["has_more"] is False


def test_database_failure_is_generic_non_reflecting_and_not_cached(monkeypatch):
    def fail(**kwargs):
        raise RuntimeError("PRIVATE DATABASE AND COORDINATE SENTINEL")

    monkeypatch.setattr("evacuation.catalog.find_map_centers", fail)
    response = get()
    assert response.status_code == 500
    assert response.json() == {"detail": MAP_INTERNAL_ERROR}
    assert "PRIVATE" not in response.content.decode()
    assert response["Cache-Control"] == "no-store"


def test_catalog_requests_are_rate_bounded_and_options_do_not_consume_quota():
    for _ in range(30):
        assert get().status_code == 200
    assert APIClient().options(URL).status_code == 200
    response = get()
    assert response.status_code == 429
    assert response["Cache-Control"] == "no-store"
    assert response["Allow"] == "GET, POST, OPTIONS"


@pytest.mark.parametrize("field", ["private_notes", "approximate_distance", "distance_method"])
def test_catalog_envelope_rejects_unknown_fields(field):
    result = get().json()
    result[field] = "not allowed"
    assert not MapCenterResponseSerializer(data=result).is_valid()


@pytest.mark.parametrize("value", ["false", 0, 1, None])
def test_has_more_requires_boolean(value):
    result = get().json()
    result["has_more"] = value
    assert not MapCenterResponseSerializer(data=result).is_valid()


def nearby(latitude=0.5, longitude=0.5, **kwargs):
    return APIClient().post(
        URL,
        {"latitude": latitude, "longitude": longitude},
        format="json",
        HTTP_HOST="127.0.0.1",
        **kwargs,
    )


def test_nearby_map_ranks_all_candidates_and_keeps_only_nearest_25(center_factory):
    # UUID order deliberately puts the farthest records first.
    records = [
        center_factory(latitude=0.5, longitude=0.1 + index * 0.02, public_id=UUID(int=index + 1))
        for index in range(30)
    ]
    with CaptureQueriesContext(connection) as queries:
        response = nearby(longitude=0.69)
    assert response.status_code == 200
    result = response.json()
    assert len(result["centers"]) == MAP_NEARBY_CENTERS
    assert result["has_more"] is True
    assert result["warnings"] == [MAP_WARNING, MAP_NEARBY_LIMIT_WARNING]
    returned = [row["public_identifier"] for row in result["centers"]]
    assert returned == [str(row.public_id) for row in reversed(records[5:])]
    assert set(result["centers"][0]) == PUBLIC_FIELDS
    assert "PRIVATE" not in response.content.decode()
    assert response["Cache-Control"] == "no-store"
    assert response["Allow"] == "GET, POST, OPTIONS"
    assert not any(
        q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries
    )
    schema = MapCenterResponseSerializer(data=result, context={"nearby": True})
    assert schema.is_valid(), schema.errors
    assert len(queries) <= 6
    # Moving the pin, not changing the viewport, selects the opposite end.
    moved = nearby(longitude=0.1).json()
    assert [row["public_identifier"] for row in moved["centers"]] == [
        str(row.public_id) for row in records[:25]
    ]


def test_nearby_map_validates_before_cap_and_breaks_distance_ties_by_uuid(center_factory):
    records = [
        center_factory(latitude=0.5, longitude=0.5, public_id=UUID(int=index + 1))
        for index in range(27)
    ]
    EvacuationCenter.objects.filter(pk=records[0].pk).update(name="")
    result = nearby().json()
    assert result["has_more"] is True
    assert [row["public_identifier"] for row in result["centers"]] == [
        str(row.public_id) for row in records[1:26]
    ]
    records[-1].delete()
    assert nearby().json()["has_more"] is False


@pytest.mark.parametrize(
    "inputs",
    [
        {},
        {"latitude": True, "longitude": 0.5},
        {"latitude": "0.5", "longitude": 0.5},
        {"latitude": 91, "longitude": 0.5},
        {"latitude": 0.5, "longitude": 181},
        {"latitude": None, "longitude": 0.5},
        {"latitude": 0.5, "longitude": 0.5, "limit": 26},
    ],
)
def test_nearby_invalid_input_never_runs_spatial_queries(inputs):
    with CaptureQueriesContext(connection) as queries:
        response = APIClient().post(URL, inputs, format="json", HTTP_HOST="127.0.0.1")
    assert response.status_code == 400
    assert len(queries) == 0
    assert response["Cache-Control"] == "no-store"


def test_nearby_rejects_coordinate_query_string_without_echoing():
    with CaptureQueriesContext(connection) as queries:
        response = APIClient().post(
            URL + "?latitude=12.345678", {"latitude": 0.5, "longitude": 0.5}, format="json"
        )
    assert response.status_code == 400
    assert len(queries) == 0
    assert "12.345678" not in response.content.decode()


def test_nearby_rechecks_eligibility_and_does_not_mix_local_data(
    testing_settings, temporary_center, center_factory, settings
):
    genuine = center_factory(latitude=0.5, longitude=0.5)
    response = nearby()
    assert response.status_code == 200
    result = response.json()
    assert result["data_status"] == "DEMONSTRATION"
    assert [row["public_identifier"] for row in result["centers"]] == [
        str(temporary_center.public_id)
    ]
    DataSource.objects.filter(pk=temporary_center.source_id).update(reviewed_on=None)
    assert_empty(nearby(), temporary=True)
    settings.ENABLE_LOCAL_TESTING = False
    assert nearby().json()["centers"][0]["public_identifier"] == str(genuine.public_id)
    EvacuationCenter.objects.filter(pk=genuine.pk).update(verification_status="IN_REVIEW")
    assert_empty(nearby())


def test_nearby_response_rejects_26_rows_even_without_truncation(center_factory):
    center_factory(latitude=0.5, longitude=0.5)
    result = nearby().json()
    result["centers"] = [
        {**result["centers"][0], "public_identifier": str(UUID(int=index + 1))}
        for index in range(26)
    ]
    assert not MapCenterResponseSerializer(data=result, context={"nearby": True}).is_valid()
