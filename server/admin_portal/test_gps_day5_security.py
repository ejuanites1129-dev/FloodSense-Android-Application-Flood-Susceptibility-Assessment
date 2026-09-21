"""Day 5 security, transaction, and production-configuration regressions."""

import os
import subprocess
import sys
from unittest.mock import patch

import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.urls import reverse
from evacuation.models import EvacuationCenter
from evacuation.workflow import transition_center
from geography.models import GeographicArea
from provenance.models import DataSource, PublicationStatus
from provenance.workflow import transition_source


@pytest.fixture
def day5_records(db):
    source = DataSource.objects.create(
        name="SYNTHETIC DAY 5 SOURCE - NOT OFFICIAL",
        organization="Synthetic test organization",
        custodian="Synthetic test custodian",
        source_type=DataSource.SourceType.AGENCY_DATASET,
        coverage_description="Synthetic test coverage.",
        permitted_use="Automated tests only.",
        limitations="Not operational data.",
        status=PublicationStatus.PENDING_VALIDATION,
    )
    area = GeographicArea.objects.create(
        code="SYNTHETIC_DAY5_AREA",
        name="SYNTHETIC DAY 5 AREA",
        area_type=GeographicArea.AreaType.BARANGAY,
        geometry=MultiPolygon(Polygon.from_bbox((0, 0, 1, 1)), srid=4326),
        source=source,
        status=PublicationStatus.PENDING_VALIDATION,
        is_enabled=True,
    )
    center = EvacuationCenter.objects.create(
        name="SYNTHETIC DAY 5 CENTER - NOT REAL",
        address="Synthetic address",
        geographic_area=area,
        latitude="0.25",
        longitude="0.75",
        source=source,
        publication_status=PublicationStatus.PENDING_VALIDATION,
        verification_status=EvacuationCenter.VerificationStatus.DRAFT,
        limitations="Synthetic limitation.",
    )
    actor = get_user_model().objects.create_user(
        email="synthetic-day5-admin@example.test", is_staff=True
    )
    actor.user_permissions.set(
        Permission.objects.filter(
            content_type__app_label__in=("evacuation", "provenance"),
            codename__in=(
                "view_evacuationcenter",
                "add_evacuationcenter",
                "change_evacuationcenter",
                "view_datasource",
                "change_datasource",
                "approve_datasource",
            ),
        )
    )
    return source, area, center, actor


def _center_form_data(source, area, **changes):
    values = {
        "name": "SYNTHETIC CRAFTED CENTER - NOT REAL",
        "address": "Synthetic crafted address",
        "geographic_area": area.pk,
        "latitude": "0.40",
        "longitude": "0.60",
        "contact_information": "PRIVATE-CONTACT-SENTINEL",
        "source": source.pk,
        "publication_status": PublicationStatus.PENDING_VALIDATION,
        "notes": "PRIVATE-NOTE-SENTINEL",
        "limitations": "Synthetic public limitation.",
        "duplicate_review_confirmed": "on",
    }
    values.update(changes)
    return values


def test_center_create_ignores_excluded_mass_assignment_and_requires_csrf(day5_records):
    source, area, _, actor = day5_records
    from django.test import Client

    client = Client(enforce_csrf_checks=True)
    client.force_login(actor)
    url = reverse("admin_portal:evacuation-center-create")
    data = _center_form_data(
        source,
        area,
        verification_status=EvacuationCenter.VerificationStatus.VERIFIED,
        verified_on="2026-01-01",
        capacity="999",
        created_at="2000-01-01T00:00:00Z",
    )
    assert client.post(url, data).status_code == 403
    assert not EvacuationCenter.objects.filter(name=data["name"]).exists()

    get_response = client.get(url)
    token = get_response.cookies["csrftoken"].value
    response = client.post(url, data, HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 302
    center = EvacuationCenter.objects.get(name=data["name"])
    assert center.verification_status == EvacuationCenter.VerificationStatus.DRAFT
    assert center.verified_on is None
    assert center.capacity is None
    assert LogEntry.objects.filter(object_id=str(center.pk)).count() == 1


def test_center_create_and_audit_are_atomic(day5_records, client):
    source, area, _, actor = day5_records
    client.force_login(actor)
    with patch("admin_portal.views.log_center_action", side_effect=RuntimeError("audit failed")):
        with pytest.raises(RuntimeError, match="audit failed"):
            client.post(
                reverse("admin_portal:evacuation-center-create"),
                _center_form_data(source, area),
            )
    assert not EvacuationCenter.objects.filter(
        name="SYNTHETIC CRAFTED CENTER - NOT REAL"
    ).exists()


def test_sensitive_workflows_roll_back_when_audit_fails(day5_records):
    source, _, center, actor = day5_records
    with patch("evacuation.workflow.log_center_action", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            transition_center(
                center_id=center.pk,
                action="submit",
                actor=actor,
                expected_status=EvacuationCenter.VerificationStatus.DRAFT,
            )
    center.refresh_from_db()
    assert center.verification_status == EvacuationCenter.VerificationStatus.DRAFT

    with patch("provenance.workflow.log_source_action", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            transition_source(
                source_id=source.pk,
                action="approve",
                actor=actor,
                expected_status=PublicationStatus.PENDING_VALIDATION,
                expected_public=False,
            )
    source.refresh_from_db()
    assert source.status == PublicationStatus.PENDING_VALIDATION
    assert source.reviewed_by_id is None
    assert LogEntry.objects.count() == 0


def test_deleted_center_and_source_during_confirmed_transition_are_not_found(
    day5_records, client
):
    source, _, center, actor = day5_records
    client.force_login(actor)
    with patch(
        "admin_portal.views.transition_center",
        side_effect=EvacuationCenter.DoesNotExist,
    ):
        response = client.post(
            reverse("admin_portal:evacuation-center-transition", args=(center.pk, "submit")),
            {"expected_status": "DRAFT", "confirm": "on"},
        )
    assert response.status_code == 404

    with patch("admin_portal.views.transition_source", side_effect=DataSource.DoesNotExist):
        response = client.post(
            reverse("admin_portal:data-source-transition", args=(source.pk, "approve")),
            {
                "expected_status": PublicationStatus.PENDING_VALIDATION,
                "expected_public": "False",
                "confirm": "on",
            },
        )
    assert response.status_code == 404


def test_production_rejects_development_secret_key():
    environment = os.environ.copy()
    environment.update(
        {
            "DJANGO_DEBUG": "false",
            "DJANGO_SECRET_KEY": "development-only-change-before-deployment",
        }
    )
    result = subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=os.path.dirname(os.path.dirname(__file__)),
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    combined = result.stdout + result.stderr
    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false" in combined
