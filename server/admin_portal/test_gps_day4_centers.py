"""Day 4 center governance, accessibility, audit, and duplicate-review tests."""

from datetime import date, timedelta
from pathlib import Path

import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from evacuation.models import EvacuationCenter
from evacuation.workflow import transition_center
from geography.models import GeographicArea
from provenance.models import DataSource, PublicationStatus

from .forms import EvacuationCenterForm


@pytest.fixture
def center_admin_records(db):
    source = DataSource.objects.create(
        name="SYNTHETIC CENTER SOURCE - TESTS ONLY",
        organization="Synthetic test organization",
        custodian="Synthetic records unit",
        source_type=DataSource.SourceType.AGENCY_DATASET,
        status=PublicationStatus.APPROVED,
        is_publicly_releasable=True,
        version="synthetic-v1",
        permitted_use="Automated tests only.",
        processing_notes="Synthetic processing note.",
        limitations="Not operational data.",
    )
    area = GeographicArea.objects.create(
        code="SYNTHETIC_DAY4_AREA",
        name="SYNTHETIC DAY 4 AREA",
        area_type=GeographicArea.AreaType.BARANGAY,
        geometry=MultiPolygon(Polygon.from_bbox((0, 0, 1, 1)), srid=4326),
        source=source,
        status=PublicationStatus.PENDING_VALIDATION,
        is_enabled=True,
    )
    staff = get_user_model().objects.create_user(
        email="synthetic-day4-admin@example.test", is_staff=True
    )
    staff.user_permissions.set(
        Permission.objects.filter(
            content_type__app_label="evacuation",
            codename__in=(
                "view_evacuationcenter",
                "add_evacuationcenter",
                "change_evacuationcenter",
                "verify_evacuationcenter",
                "deactivate_evacuationcenter",
            ),
        )
    )
    return source, area, staff


def form_data(source, area, **overrides):
    data = {
        "name": "SYNTHETIC DAY 4 CENTER - NOT REAL",
        "address": "Synthetic test address",
        "geographic_area": area.pk,
        "latitude": "0.250000",
        "longitude": "0.750000",
        "contact_information": "",
        "source": source.pk,
        "publication_status": PublicationStatus.PENDING_VALIDATION,
        "notes": "Synthetic internal note.",
        "limitations": "Synthetic public limitation.",
    }
    data.update(overrides)
    return data


def create_center(source, area, **overrides):
    values = {
        "name": "SYNTHETIC EXISTING CENTER - NOT REAL",
        "address": "Synthetic existing address",
        "geographic_area": area,
        "latitude": "0.250000",
        "longitude": "0.750000",
        "source": source,
        "publication_status": PublicationStatus.PENDING_VALIDATION,
        "verification_status": EvacuationCenter.VerificationStatus.DRAFT,
        "limitations": "Synthetic limitation.",
    }
    values.update(overrides)
    return EvacuationCenter.objects.create(**values)


def test_duplicate_name_and_coordinate_warn_without_merging(center_admin_records):
    source, area, _ = center_admin_records
    existing = create_center(
        source,
        area,
        name="  SYNTHETIC DAY 4 CENTER - NOT REAL  ",
    )
    form = EvacuationCenterForm(form_data(source, area))
    assert not form.is_valid()
    assert len(form.duplicate_warnings) == 1
    assert form.duplicate_warnings[0]["reasons"] == (
        "same normalized name",
        "same exact coordinates",
    )
    assert EvacuationCenter.objects.filter(pk=existing.pk).exists()

    confirmed = EvacuationCenterForm(form_data(source, area, duplicate_review_confirmed="on"))
    assert confirmed.is_valid(), confirmed.errors
    confirmed.save()
    assert EvacuationCenter.objects.count() == 2


def test_obvious_nonduplicate_needs_no_acknowledgement(center_admin_records):
    source, area, _ = center_admin_records
    create_center(source, area)
    form = EvacuationCenterForm(
        form_data(
            source,
            area,
            name="SYNTHETIC DISTINCT CENTER - NOT REAL",
            latitude="0.500000",
            longitude="0.500000",
        )
    )
    assert form.is_valid(), form.errors
    assert form.duplicate_warnings == []


@pytest.mark.parametrize(
    "field,value,error_fragment",
    [
        ("name", "", "required"),
        ("address", "", "required"),
        ("latitude", "NaN", "number"),
        ("longitude", "Infinity", "number"),
        ("latitude", "90.000001", "less than or equal"),
        ("longitude", "-180.000001", "greater than or equal"),
        ("limitations", "bad\x01text", "control characters"),
    ],
)
def test_server_side_center_field_validation(center_admin_records, field, value, error_fragment):
    source, area, _ = center_admin_records
    form = EvacuationCenterForm(form_data(source, area, **{field: value}))
    assert not form.is_valid()
    assert error_fragment.lower() in " ".join(form.errors[field]).lower()


def test_invalid_source_identifier_is_a_field_error_not_a_server_error(
    client, center_admin_records
):
    source, area, staff = center_admin_records
    client.force_login(staff)
    data = form_data(source, area)
    data["source"] = "not-a-database-identifier"
    response = client.post(
        reverse("admin_portal:evacuation-center-create"),
        data,
    )
    assert response.status_code == 200
    assert b"Select a valid choice" in response.content


def test_map_alternative_and_provenance_are_server_rendered(client, center_admin_records):
    source, area, staff = center_admin_records
    center = create_center(source, area)
    client.force_login(staff)
    response = client.get(reverse("admin_portal:evacuation-center-detail", args=(center.pk,)))
    text = response.content.decode()
    assert response.status_code == 200
    for expected in (
        'tabindex="0"',
        'role="status"',
        "JavaScript is unavailable",
        "OpenStreetMap contributors",
        "does not verify the center",
        "Source organization",
        "Source custodian",
        "Source version",
        "Permitted use",
        "Source processing notes",
        "not live occupancy",
    ):
        assert expected in text

    script = (
        Path(__file__).parent / "static" / "admin_portal" / "js" / "center_map.js"
    ).read_text()
    assert "data-center-map-status" in script
    assert "Map preview unavailable" in script
    assert "does not verify the center or route safety" in script


def test_sensitive_transition_shows_result_and_visibility_effect(client, center_admin_records):
    source, area, staff = center_admin_records
    center = create_center(
        source,
        area,
        verification_status=EvacuationCenter.VerificationStatus.IN_REVIEW,
    )
    client.force_login(staff)
    response = client.get(
        reverse(
            "admin_portal:evacuation-center-transition",
            args=(center.pk, "verify"),
        )
    )
    text = response.content.decode()
    assert "Requested state change" in text
    assert "Resulting state" in text and "Verified" in text
    assert "Resident visibility effect" in text
    assert center.name in text


def test_verify_rechecks_source_and_rejects_future_date(client, center_admin_records):
    source, area, staff = center_admin_records
    center = create_center(
        source,
        area,
        verification_status=EvacuationCenter.VerificationStatus.IN_REVIEW,
    )
    client.force_login(staff)
    url = reverse("admin_portal:evacuation-center-transition", args=(center.pk, "verify"))
    future = timezone.localdate() + timedelta(days=1)
    response = client.post(
        url,
        {
            "expected_status": EvacuationCenter.VerificationStatus.IN_REVIEW,
            "verified_on": future.isoformat(),
            "confirm": "on",
        },
    )
    assert response.status_code == 200
    assert b"cannot be in the future" in response.content

    source.status = PublicationStatus.RESTRICTED
    source.save(update_fields=("status",))
    response = client.post(
        url,
        {
            "expected_status": EvacuationCenter.VerificationStatus.IN_REVIEW,
            "verified_on": timezone.localdate().isoformat(),
            "confirm": "on",
        },
    )
    assert response.status_code == 409
    center.refresh_from_db()
    assert center.verification_status == EvacuationCenter.VerificationStatus.IN_REVIEW


def test_direct_workflow_call_rejects_future_date(center_admin_records):
    source, area, staff = center_admin_records
    center = create_center(
        source,
        area,
        verification_status=EvacuationCenter.VerificationStatus.IN_REVIEW,
    )
    with pytest.raises(ValidationError, match="cannot be in the future"):
        transition_center(
            center_id=center.pk,
            action="verify",
            actor=staff,
            expected_status=EvacuationCenter.VerificationStatus.IN_REVIEW,
            verified_on=timezone.localdate() + timedelta(days=1),
        )


def test_edit_audit_names_changed_fields_without_values(client, center_admin_records):
    source, area, staff = center_admin_records
    center = create_center(source, area)
    client.force_login(staff)
    response = client.post(
        reverse("admin_portal:evacuation-center-edit", args=(center.pk,)),
        form_data(
            source,
            area,
            name=center.name,
            address="PRIVATE SYNTHETIC CHANGED VALUE",
            latitude=str(center.latitude),
            longitude=str(center.longitude),
            limitations=center.limitations,
        ),
    )
    assert response.status_code == 302
    entry = LogEntry.objects.get(object_id=str(center.pk))
    assert "Changed fields: address" in entry.change_message
    assert "PRIVATE SYNTHETIC CHANGED VALUE" not in entry.change_message


def test_staff_without_transition_permission_cannot_craft_post(client, center_admin_records):
    source, area, _ = center_admin_records
    center = create_center(
        source,
        area,
        verification_status=EvacuationCenter.VerificationStatus.IN_REVIEW,
    )
    viewer = get_user_model().objects.create_user(
        email="synthetic-day4-viewer@example.test", is_staff=True
    )
    viewer.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="evacuation",
            codename="view_evacuationcenter",
        )
    )
    client.force_login(viewer)
    response = client.post(
        reverse(
            "admin_portal:evacuation-center-transition",
            args=(center.pk, "verify"),
        ),
        {
            "expected_status": EvacuationCenter.VerificationStatus.IN_REVIEW,
            "verified_on": date.today().isoformat(),
            "confirm": "on",
        },
    )
    assert response.status_code == 403
    center.refresh_from_db()
    assert center.verification_status == EvacuationCenter.VerificationStatus.IN_REVIEW
