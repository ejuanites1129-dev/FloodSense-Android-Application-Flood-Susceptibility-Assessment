"""Synthetic preview in an isolated test DB; never fabricated facility approval."""

from datetime import date

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from provenance.models import DataSource, PublicationStatus
from rest_framework.test import APIClient

from . import test_day2_nearest_service as reference_fixtures
from .local_preview import LOCAL_PREVIEW_WARNING
from .models import EvacuationCenter

pytestmark = pytest.mark.django_db
URL = "/api/v1/evacuation-centers/local-preview/nearest/"
layer = reference_fixtures.layer


@pytest.fixture
def preview_settings(settings):
    settings.DEBUG = True
    settings.ENABLE_LOCAL_CENTER_PREVIEW = True
    cache.clear()


@pytest.fixture
def demonstration_center(layer):
    source = DataSource.objects.create(
        name="LOCAL TEST SOURCE - NOT OFFICIAL",
        organization="Synthetic test attribution",
        source_type="DEMONSTRATION",
        status="DEMONSTRATION",
        is_publicly_releasable=False,
        notes="PRIVATE SOURCE SENTINEL",
        limitations="Test display only.",
    )
    center = EvacuationCenter.objects.create(
        name="LOCAL TEST - NOT A REAL FACILITY",
        address="Fictional test address",
        source=source,
        geographic_area=layer[2][0],
        latitude=0.5,
        longitude=0.5,
        verification_status="DRAFT",
        publication_status="DEMONSTRATION",
        notes="PRIVATE CENTER SENTINEL",
        contact_information="PRIVATE CONTACT SENTINEL",
        limitations="Do not travel to this synthetic marker.",
    )
    center.full_clean()
    return center


def post(**kwargs):
    return APIClient().post(
        URL,
        {"latitude": 0.5, "longitude": 0.5},
        format="json",
        HTTP_HOST="127.0.0.1",
        **kwargs,
    )


@pytest.mark.parametrize(
    "gate", ["disabled", "production", "remote_database", "remote_client", "remote_host"]
)
def test_preview_fails_closed_outside_explicit_local_session(preview_settings, settings, gate):
    kwargs = {}
    if gate == "disabled":
        settings.ENABLE_LOCAL_CENTER_PREVIEW = False
    elif gate == "production":
        settings.DEBUG = False
    elif gate == "remote_database":
        settings.DATABASES = {
            "default": {**settings.DATABASES["default"], "HOST": "database.example.test"}
        }
    elif gate == "remote_client":
        kwargs["REMOTE_ADDR"] = "192.0.2.10"
    elif gate == "remote_host":
        settings.ALLOWED_HOSTS = ["testserver"]
        response = APIClient().post(URL, {}, format="json", HTTP_HOST="testserver")
        assert response.status_code == 404
        return
    with CaptureQueriesContext(connection) as queries:
        response = post(**kwargs)
    assert response.status_code == 404
    assert len(queries) == 0
    assert response["Cache-Control"] == "no-store"


def test_preview_reads_demo_draft_without_promoting_or_exposing_private_fields(
    preview_settings,
    demonstration_center,
):
    with CaptureQueriesContext(connection) as queries:
        response = post()
    assert response.status_code == 200
    payload = response.json()
    center = payload["centers"][0]
    assert payload["data_status"] == center["data_status"] == "DEMONSTRATION"
    assert center["verified_on"] is None
    assert center["approximate_distance"] == 0
    assert center["public_identifier"] == str(demonstration_center.public_id)
    assert center["limitations"][0] == payload["warnings"][0] == LOCAL_PREVIEW_WARNING
    assert "PRIVATE" not in response.content.decode()
    assert all(query["sql"].lstrip().startswith("SELECT") for query in queries)
    demonstration_center.refresh_from_db()
    assert demonstration_center.verification_status == "DRAFT"
    assert demonstration_center.publication_status == "DEMONSTRATION"
    assert demonstration_center.verified_on is demonstration_center.capacity is None

    public = APIClient().post(
        "/api/v1/evacuation-centers/nearest/",
        {"latitude": 0.5, "longitude": 0.5},
        format="json",
        HTTP_HOST="127.0.0.1",
    )
    assert public.status_code == 200
    assert public.json()["centers"] == []
    assert "data_status" not in public.json()
    assert public["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "Unlabeled imaginary facility"},
        {"publication_status": PublicationStatus.APPROVED},
        {"verification_status": "VERIFIED"},
        {"verification_status": "INACTIVE"},
        {"verified_on": date(2026, 10, 4)},
        {"capacity": 100},
        {"latitude": 91},
        {"latitude": 5},  # outside the recorded barangay
        {"geographic_area": None},
    ],
)
def test_preview_excludes_unsafe_or_non_demonstration_centers(
    preview_settings,
    demonstration_center,
    overrides,
):
    EvacuationCenter.objects.filter(pk=demonstration_center.pk).update(**overrides)
    response = post()
    assert response.status_code == 200
    assert response.json()["centers"] == []
    assert response.json()["warnings"][0] == LOCAL_PREVIEW_WARNING


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": PublicationStatus.RESTRICTED},
        {"status": PublicationStatus.APPROVED},
        {"source_type": DataSource.SourceType.AGENCY_DATASET},
        {"is_publicly_releasable": True},
    ],
)
def test_preview_excludes_restricted_or_real_facility_sources(
    preview_settings,
    demonstration_center,
    overrides,
):
    DataSource.objects.filter(pk=demonstration_center.source_id).update(**overrides)
    assert post().json()["centers"] == []
