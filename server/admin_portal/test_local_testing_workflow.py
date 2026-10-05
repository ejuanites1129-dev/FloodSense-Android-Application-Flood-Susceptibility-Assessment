"""End-to-end temporary records in existing tables, isolated pytest PostGIS only."""

import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from evacuation import test_day2_nearest_service as reference_fixtures
from evacuation.models import EvacuationCenter
from evacuation.services import find_nearest_eligible_centers
from provenance.models import DataSource
from provenance.workflow import transition_source
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db
layer = reference_fixtures.layer
center_factory = reference_fixtures.center_factory


@pytest.fixture
def local_session(settings, client):
    settings.DEBUG = True
    settings.ENABLE_LOCAL_TESTING = True
    actor = get_user_model().objects.create_user(email="local-workflow@example.test", is_staff=True)
    actor.user_permissions.set(
        Permission.objects.filter(content_type__app_label__in=("evacuation", "provenance"))
    )
    client.force_login(actor)
    return actor


def create_source(client):
    response = client.post(
        reverse("admin_portal:data-source-create"),
        {
            "name": "Temporary training source",
            "organization": "Research team test",
            "custodian": "Local developer",
            "coverage_description": "Synthetic location fixtures",
            "source_type": "OTHER",
            "temporary_data": "on",
            "permitted_use": "Local tests only",
            "limitations": "Not agency evidence",
            "confirm": "on",
            "save_action": "approve",
        },
        HTTP_HOST="127.0.0.1",
    )
    assert response.status_code == 302, response.content.decode()
    return DataSource.objects.get(name="Temporary training source")


def create_center(client, source, layer):
    response = client.post(
        reverse("admin_portal:evacuation-center-create"),
        {
            "name": "Temporary training location",
            "address": "Fictional test address",
            "latitude": "0.5",
            "longitude": "0.5",
            "geographic_area": layer[2][0].pk,
            "source": source.pk,
            "publication_status": "PENDING_VALIDATION",
            "temporary_data": "on",
            "save_action": "verify",
            "confirm": "on",
        },
        HTTP_HOST="127.0.0.1",
    )
    assert response.status_code == 302, response.content.decode()
    return EvacuationCenter.objects.get(name="Temporary training location")


def lookup(**kwargs):
    return APIClient().post(
        "/api/v1/evacuation-centers/nearest/",
        {"latitude": 0.5, "longitude": 0.5},
        format="json",
        HTTP_HOST="127.0.0.1",
        **kwargs,
    )


def test_normal_forms_to_normal_api_temporary_approval_and_disable(
    local_session, client, layer, settings
):
    source = create_source(client)
    center = create_center(client, source, layer)
    assert source.source_type == source.status == "DEMONSTRATION"
    assert source.test_approved and not source.is_publicly_releasable
    assert center.verification_status == "VERIFIED"
    assert center.publication_status == "DEMONSTRATION"
    assert center.verified_on is center.capacity is None
    assert "local testing" in center.get_verification_status_display()
    page = client.get(
        reverse("admin_portal:data-source-detail", args=[source.pk]), HTTP_HOST="127.0.0.1"
    )
    assert page.status_code == 200
    assert b"Local testing \xe2\x80\x94 temporary data" not in page.content
    # Removing the global banner does not remove per-record temporary labels.
    assert center.get_publication_status_display() == "Demonstration data\u2014not official"
    assert (
        DataSource.objects.count() == 2
    )  # only fixture boundary source + explicitly entered source
    assert EvacuationCenter.objects.count() == 1
    center.full_clean()
    with CaptureQueriesContext(connection) as queries:
        response = lookup()
    assert response.status_code == 200
    assert len(response.json()["centers"]) == 1
    assert response.json()["data_status"] == "DEMONSTRATION"
    assert response.json()["centers"][0]["verified_on"] is None
    assert all(q["sql"].lstrip().startswith("SELECT") for q in queries)
    assert find_nearest_eligible_centers(latitude=0.5, longitude=0.5)["centers"] == []
    settings.ENABLE_LOCAL_TESTING = False
    assert lookup().json()["centers"] == []
    assert "data_status" not in lookup().json()
    assert (
        client.get(
            reverse("admin_portal:remove-temporary-center", args=[center.pk]), HTTP_HOST="127.0.0.1"
        ).status_code
        == 403
    )
    assert (
        LogEntry.objects.filter(content_type__app_label__in=["provenance", "evacuation"]).count()
        == 5
    )


@pytest.mark.parametrize("gate", ["production", "remote_client", "remote_host", "remote_database"])
def test_main_api_never_exposes_tests_outside_local_session(
    local_session, client, layer, settings, gate
):
    source = create_source(client)
    create_center(client, source, layer)
    extra = {}
    if gate == "production":
        settings.DEBUG = False
    elif gate == "remote_client":
        extra["REMOTE_ADDR"] = "192.0.2.10"
    elif gate == "remote_database":
        settings.DATABASES = {
            "default": {**settings.DATABASES["default"], "HOST": "remote.invalid"}
        }
    else:
        settings.ALLOWED_HOSTS = ["testserver"]
        response = APIClient().post(
            "/api/v1/evacuation-centers/nearest/",
            {"latitude": 0.5, "longitude": 0.5},
            format="json",
        )
        assert "data_status" not in response.json()
        assert response.json()["centers"] == []
        return
    response = lookup(**extra)
    assert "data_status" not in response.json()
    assert response.json()["centers"] == []


def test_test_and_actual_centers_not_mixed(local_session, client, layer, center_factory):
    real = center_factory()
    source = create_source(client)
    center = create_center(client, source, layer)
    assert [r["public_identifier"] for r in lookup().json()["centers"]] == [str(center.public_id)]
    ordinary = lookup(REMOTE_ADDR="192.0.2.1")
    assert [r["public_identifier"] for r in ordinary.json()["centers"]] == [str(real.public_id)]


def test_boundary_source_is_not_facility_evidence(local_session, client, layer):
    form = client.get(
        reverse("admin_portal:evacuation-center-create"), HTTP_HOST="127.0.0.1"
    ).context["form"]
    assert not form.fields["source"].queryset.filter(pk=layer[0].pk).exists()
    with pytest.raises(ValidationError):
        transition_source(
            source_id=layer[0].pk,
            actor=local_session,
            action="approve",
            expected_status="PENDING_VALIDATION",
            expected_public=True,
        )
    layer[0].refresh_from_db()
    assert layer[0].status == "PENDING_VALIDATION" and layer[0].is_publicly_releasable
    assert (
        client.get(
            reverse("admin_portal:data-source-edit", args=[layer[0].pk]), HTTP_HOST="127.0.0.1"
        ).status_code
        == 200
    )


def test_return_review_withholds_test_and_edit_is_atomic(local_session, client, layer):
    source = create_source(client)
    center = create_center(client, source, layer)
    response = client.post(
        reverse("admin_portal:data-source-transition", args=[source.pk, "return-test-review"]),
        {
            "expected_status": source.status,
            "expected_public": "false",
            "confirm": "on",
            "expected_updated_at": source.updated_at.isoformat(),
        },
        HTTP_HOST="127.0.0.1",
    )
    assert response.status_code == 302
    assert lookup().json()["centers"] == []
    source.refresh_from_db()
    assert not source.test_approved
    center.refresh_from_db()
    assert center.verification_status == "VERIFIED"  # no rewriting of child records


def test_cleanup_single_record_permissions_protection_and_staleness(local_session, client, layer):
    source = create_source(client)
    center = create_center(client, source, layer)
    source_url = reverse("admin_portal:remove-temporary-source", args=[source.pk])
    center_url = reverse("admin_portal:remove-temporary-center", args=[center.pk])
    assert client.get(center_url, HTTP_HOST="127.0.0.1").status_code == 200
    assert EvacuationCenter.objects.filter(pk=center.pk).exists()
    assert (
        client.post(
            source_url,
            {"confirm": "on", "expected_updated_at": source.updated_at.isoformat()},
            HTTP_HOST="127.0.0.1",
        ).status_code
        == 409
    )
    stale = center.updated_at.isoformat()
    center.notes = "Updated during confirmation"
    center.save()
    assert (
        client.post(
            center_url, {"confirm": "on", "expected_updated_at": stale}, HTTP_HOST="127.0.0.1"
        ).status_code
        == 409
    )
    assert (
        client.post(
            center_url,
            {"confirm": "on", "expected_updated_at": center.updated_at.isoformat()},
            HTTP_HOST="127.0.0.1",
        ).status_code
        == 302
    )
    assert not EvacuationCenter.objects.filter(pk=center.pk).exists()
    assert (
        client.post(
            source_url,
            {"confirm": "on", "expected_updated_at": source.updated_at.isoformat()},
            HTTP_HOST="127.0.0.1",
        ).status_code
        == 302
    )
    assert not DataSource.objects.filter(pk=source.pk).exists()
    assert DataSource.objects.filter(pk=layer[0].pk).exists()
    assert LogEntry.objects.filter(action_flag=3).count() == 2


def test_cleanup_cannot_delete_genuine_or_use_remote_host(local_session, client, layer):
    assert (
        client.get(
            reverse("admin_portal:remove-temporary-source", args=[layer[0].pk]),
            HTTP_HOST="127.0.0.1",
        ).status_code
        == 403
    )
    source = create_source(client)
    assert (
        client.get(
            reverse("admin_portal:remove-temporary-source", args=[source.pk]),
            HTTP_HOST="127.0.0.1",
            REMOTE_ADDR="192.0.2.1",
        ).status_code
        == 403
    )
    local_session.user_permissions.clear()
    assert (
        client.post(
            reverse("admin_portal:data-source-transition", args=[source.pk, "approve-test"]),
            {"confirm": "on", "expected_status": "DEMONSTRATION"},
            HTTP_HOST="127.0.0.1",
        ).status_code
        == 403
    )


@pytest.mark.parametrize("source_withdrawn", [False, True])
def test_approved_temporary_center_can_be_edited_and_reapproved(
    local_session,
    client,
    layer,
    source_withdrawn,
):
    source = create_source(client)
    center = create_center(client, source, layer)
    if source_withdrawn:
        source = transition_source(
            source_id=source.pk,
            action="return-test-review",
            actor=local_session,
            expected_status=source.status,
            expected_public=False,
        )
    response = client.post(
        reverse("admin_portal:evacuation-center-edit", args=[center.pk]),
        {
            "name": center.name,
            "address": "Changed temporary address",
            "latitude": center.latitude,
            "longitude": center.longitude,
            "source": source.pk,
            "geographic_area": center.geographic_area_id,
            "temporary_data": "on",
            "publication_status": "DEMONSTRATION",
            "save_action": "approve-verify" if source_withdrawn else "verify",
            "expected_source_updated_at": source.updated_at.isoformat(),
            "confirm": "on",
            "expected_updated_at": center.updated_at.isoformat(),
        },
        HTTP_HOST="127.0.0.1",
    )
    assert response.status_code == 302, response.content.decode()
    center.refresh_from_db()
    assert center.address == "Changed temporary address"
    assert center.is_temporary and center.verification_status == "VERIFIED"
    assert lookup().json()["centers"][0]["address"] == center.address
    assert EvacuationCenter.objects.count() == 1


def test_local_approval_never_claims_public_release(local_session, client, layer):
    source = create_source(client)
    for action in ("approve", "publish"):
        with pytest.raises(ValidationError):
            transition_source(
                source_id=source.pk,
                actor=local_session,
                action=action,
                expected_status=source.status,
                expected_public=False,
            )
    source.refresh_from_db()
    assert source.is_temporary and not source.is_publicly_releasable
    response = client.post(
        reverse("admin_portal:data-source-edit", args=[source.pk]),
        {
            "name": source.name,
            "organization": source.organization,
            "custodian": source.custodian,
            "coverage_description": source.coverage_description,
            "source_type": "DEMONSTRATION",
            "temporary_data": "on",
            "permitted_use": source.permitted_use,
            "limitations": source.limitations,
            "expected_updated_at": source.updated_at.isoformat(),
            "save_action": "approve-publish",
            "confirm": "on",
        },
        HTTP_HOST="127.0.0.1",
    )
    assert response.status_code == 409
    source.refresh_from_db()
    assert source.test_approved and not source.is_publicly_releasable


def test_mode_off_forms_hide_temporary_controls(local_session, client, settings, layer):
    settings.ENABLE_LOCAL_TESTING = False
    for name in ("data-source-create", "evacuation-center-create"):
        form = client.get(reverse("admin_portal:" + name), HTTP_HOST="127.0.0.1").context["form"]
        assert "temporary_data" not in form.fields


def test_deferred_source_display_does_not_fetch_review_fields(local_session, client):
    source = create_source(client)
    inventory_row = DataSource.objects.only("source_type", "status", "is_publicly_releasable").get(
        pk=source.pk
    )
    with CaptureQueriesContext(connection) as queries:
        assert "not official" in inventory_row.get_status_display()
    assert not queries


def test_cleanup_requires_delete_permission_confirmation_and_csrf(local_session, client):
    from django.test import Client

    source = create_source(client)
    url = reverse("admin_portal:remove-temporary-source", args=[source.pk])
    payload = {"expected_updated_at": source.updated_at.isoformat(), "confirm": "on"}
    secure_client = Client(enforce_csrf_checks=True)
    secure_client.force_login(local_session)
    assert secure_client.post(url, payload, HTTP_HOST="127.0.0.1").status_code == 403
    assert (
        client.post(
            url, {"expected_updated_at": source.updated_at.isoformat()}, HTTP_HOST="127.0.0.1"
        ).status_code
        == 200
    )
    local_session.user_permissions.clear()
    assert client.post(url, payload, HTTP_HOST="127.0.0.1").status_code == 403
    assert DataSource.objects.filter(pk=source.pk).exists()
