"""Review compatibility uses isolated synthetic fixtures, never application rows."""

from io import StringIO

import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from evacuation.catalog import find_map_centers
from evacuation.services import find_nearest_eligible_centers, ready_reference_barangays
from evacuation.test_day2_nearest_service import center_factory as center_factory
from evacuation.test_day2_nearest_service import layer as layer
from provenance.models import DataSource
from provenance.workflow import available_transitions, transition_source

from .boundaries import annotate_boundary_source_identity, is_bacoor_boundary_source
from .constants import BACOOR_CITY_CODE, BACOOR_REFERENCE_SOURCE_NAME
from .models import AreaFact, GeographicArea


@pytest.mark.parametrize("source_status", ["PENDING_VALIDATION", "APPROVED"])
@pytest.mark.parametrize("area_status", ["pending", "approved", "mixed"])
def test_rename_and_review_preserve_map_resolver_and_centers(
    client, layer, center_factory, source_status, area_status
):
    source, city, areas = layer
    source.name = "Synthetic renamed administrative boundaries"
    source.status = source_status
    source.save()
    if area_status == "approved":
        GeographicArea.objects.filter(source=source).update(status="APPROVED")
    elif area_status == "mixed":
        GeographicArea.objects.filter(pk=areas[0].pk).update(status="APPROVED")
    first = center_factory(latitude=0.5, longitude=0.5)
    second = center_factory(geographic_area=areas[1], latitude=0.5, longitude=1.5)
    # An unrelated source with the old label is not a competing identity or fallback.
    DataSource.objects.create(
        name=BACOOR_REFERENCE_SOURCE_NAME,
        source_type="AGENCY_DATASET",
        status="APPROVED",
        is_publicly_releasable=True,
    )
    before = (
        DataSource.objects.count(),
        GeographicArea.objects.count(),
        AreaFact.objects.count(),
        LogEntry.objects.count(),
    )
    with CaptureQueriesContext(connection) as queries:
        assert len(ready_reference_barangays()) == 47
        payload = client.get(reverse("geography:reference-boundary-collection")).json()
        assert len(payload["features"]) == 47
        assert payload["data_status"] == (
            "APPROVED" if area_status == "approved" else "PENDING_VALIDATION"
        )
        assert payload["susceptibility_dataset"] is None
        response = client.post(
            reverse("geography:resolve-barangay"),
            {"latitude": 0.5, "longitude": 0.5},
            content_type="application/json",
        )
        resolved = response.json()
        assert resolved["resolution_state"] == "RESOLVED"
        assert resolved["boundary"]["source_status"] == source_status
        assert resolved["boundary"]["data_status"] == (
            "PENDING_VALIDATION" if area_status == "pending" else "APPROVED"
        )
        assert resolved["boundary"]["city_verified"] is False
        catalog = find_map_centers(latitude=0.5, longitude=0.5)
        nearest = find_nearest_eligible_centers(latitude=0.5, longitude=0.5)
        assert {r["public_identifier"] for r in catalog["centers"]} == {
            str(first.public_id),
            str(second.public_id),
        }
        assert nearest["centers"][0]["public_identifier"] == str(first.public_id)
    assert not any(
        q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        for q in queries.captured_queries
    )
    assert before == (
        DataSource.objects.count(),
        GeographicArea.objects.count(),
        AreaFact.objects.count(),
        LogEntry.objects.count(),
    )


def test_approved_renamed_boundary_cannot_verify_a_facility(layer, center_factory):
    source = layer[0]
    source.name = "Synthetic renamed boundaries"
    source.status = "APPROVED"
    source.save()
    center = center_factory(source=source, latitude=0.5, longitude=0.5)
    with pytest.raises(ValidationError, match="not facility evidence"):
        center.full_clean()
    assert find_map_centers(latitude=0.5, longitude=0.5)["centers"] == []


def test_boundary_approval_is_permission_checked_audited_and_does_not_approve_rows(layer):
    source = layer[0]
    source.name = "Synthetic renamed boundaries"
    source.custodian = "Synthetic test custodian"
    source.coverage_description = "Synthetic geometry"
    source.permitted_use = "Isolated tests only"
    source.limitations = "Not real operational information"
    source.save()
    ordinary = get_user_model().objects.create_user(
        email="boundary-viewer@example.com", is_staff=True
    )
    reviewer = get_user_model().objects.create_superuser(
        email="boundary-reviewer@example.com", password="test-only"
    )
    assert not available_transitions(source, ordinary)
    assert "approve-boundary" in {t.action for t in available_transitions(source, reviewer)}
    with pytest.raises(PermissionDenied):
        transition_source(
            source_id=source.pk,
            action="approve-boundary",
            actor=ordinary,
            expected_status="PENDING_VALIDATION",
            expected_public=True,
        )
    transition_source(
        source_id=source.pk,
        action="approve-boundary",
        actor=reviewer,
        expected_status="PENDING_VALIDATION",
        expected_public=True,
    )
    source.refresh_from_db()
    assert source.status == "APPROVED" and source.is_publicly_releasable
    assert source.reviewed_by_id == reviewer.pk and source.reviewed_on is not None
    assert source.geographic_areas.filter(status="PENDING_VALIDATION").count() == 48
    assert LogEntry.objects.count() == 1
    assert len(ready_reference_barangays()) == 47


@pytest.mark.django_db
def test_reimport_preserves_renamed_approved_source_rows_and_metadata():
    call_command("import_bacoor_boundaries", stdout=StringIO())
    source = GeographicArea.objects.get(code=BACOOR_CITY_CODE).source
    source.name = "Reviewed synthetic test copy of boundary metadata"
    source.status = "APPROVED"
    source.notes = "Owner metadata sentinel"
    source.permitted_use = "Owner permitted-use sentinel"
    source.save()
    source.geographic_areas.update(status="APPROVED")
    before = list(source.geographic_areas.order_by("pk").values_list("pk", "status", "updated_at"))
    call_command("import_bacoor_boundaries", stdout=StringIO())
    source.refresh_from_db()
    assert DataSource.objects.count() == 1
    assert source.name == "Reviewed synthetic test copy of boundary metadata"
    assert source.status == "APPROVED" and source.notes == "Owner metadata sentinel"
    assert source.permitted_use == "Owner permitted-use sentinel"
    assert before == list(
        source.geographic_areas.order_by("pk").values_list("pk", "status", "updated_at")
    )
    area = source.geographic_areas.filter(area_type="BARANGAY").first()
    area.name = "Owner changed reviewed geometry metadata"
    area.save()
    with pytest.raises(CommandError, match="reviewed geometry"):
        call_command("import_bacoor_boundaries", stdout=StringIO())
    assert DataSource.objects.count() == 1


def test_source_list_resolves_renamed_identity_without_per_row_queries(layer):
    source = layer[0]
    source.name = "Synthetic renamed source-list boundaries"
    source.save()
    DataSource.objects.bulk_create(
        [DataSource(name=f"Synthetic unrelated source {index}") for index in range(20)]
    )
    reviewer = get_user_model()(is_active=True, is_staff=True, is_superuser=True)
    with CaptureQueriesContext(connection) as queries:
        rows = list(annotate_boundary_source_identity(DataSource.objects.order_by("pk")))
        for row in rows:
            assert is_bacoor_boundary_source(row) == (row.pk == source.pk)
            actions = {t.action for t in available_transitions(row, reviewer)}
            assert ("approve-boundary" in actions) == (row.pk == source.pk)
    assert len(queries) == 1


@pytest.mark.parametrize("action", ["save", "approve", "approve-publish"])
def test_portal_boundary_metadata_edit_preserves_release_and_existing_rows(client, layer, action):
    source = layer[0]
    reviewer = get_user_model().objects.create_superuser(
        email="boundary-editor@example.test", password="test-only"
    )
    client.force_login(reviewer)
    original_ids = list(source.geographic_areas.order_by("pk").values_list("pk", flat=True))
    response = client.post(
        reverse("admin_portal:data-source-edit", args=[source.pk]),
        {
            "name": "Synthetic owner-renamed mapping boundaries",
            "organization": source.organization,
            "custodian": "Synthetic test custodian",
            "source_type": "AGENCY_DATASET",
            "coverage_description": "Synthetic geometry only",
            "permitted_use": "Isolated tests only",
            "limitations": "Not City or facility evidence",
            "expected_updated_at": source.updated_at.isoformat(),
            "save_action": action,
            "confirm": "on",
        },
    )
    assert response.status_code == 302, response.content.decode()
    source.refresh_from_db()
    assert source.name == "Synthetic owner-renamed mapping boundaries"
    assert source.is_publicly_releasable
    assert source.status == ("PENDING_VALIDATION" if action == "save" else "APPROVED")
    assert DataSource.objects.count() == 1
    assert original_ids == list(
        source.geographic_areas.order_by("pk").values_list("pk", flat=True)
    )
    assert source.geographic_areas.filter(status="PENDING_VALIDATION").count() == 48
    assert len(ready_reference_barangays()) == 47
