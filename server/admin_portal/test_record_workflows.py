"""Synthetic records only; all imports target pytest's isolated database."""

import csv
import io
from datetime import timedelta

import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from evacuation.imports import HEADERS, import_batch, read_upload, stage_batch, validate_rows
from evacuation.models import CenterImportBatch, EvacuationCenter
from geography.models import GeographicArea
from provenance.models import DataSource
from provenance.workflow import transition_source

from .bulk_workflows import execute_bulk, preview_bulk
from .operations_views import FastCenterForm, resident_checklist
from .record_workflows import save_center

pytestmark = pytest.mark.django_db


@pytest.fixture
def records():
    actor = get_user_model().objects.create_user(email="batch-tests@example.test", is_staff=True)
    actor.user_permissions.set(
        Permission.objects.filter(content_type__app_label__in=("evacuation", "provenance", "dss"))
    )
    source = DataSource.objects.create(
        name="SYNTHETIC batch source—not official",
        organization="Synthetic office",
        custodian="Synthetic records unit",
        coverage_description="Test coverage only",
        source_type="AGENCY_DATASET",
        status="PENDING_VALIDATION",
        permitted_use="Tests only",
        limitations="Synthetic records. Not operational facilities.",
    )
    area = GeographicArea.objects.create(
        code="SYNTHETIC_AREA",
        name="Synthetic area",
        area_type="BARANGAY",
        geometry=MultiPolygon(Polygon.from_bbox((0, 0, 1, 1)), srid=4326),
        source=source,
        status="PENDING_VALIDATION",
        is_enabled=True,
    )
    return actor, source, area


def payload(source, **extra):
    return {
        "name": "SYNTHETIC center",
        "address": "Synthetic test address",
        "latitude": "0.5",
        "longitude": "0.5",
        "source": str(source.pk),
        "publication_status": "PENDING_VALIDATION",
        "expected_source_updated_at": source.updated_at.isoformat(),
        **extra,
    }


def csv_upload(rows, name="synthetic.csv"):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(HEADERS)
    writer.writerows(rows)
    return SimpleUploadedFile(name, stream.getvalue().encode("utf-8"))


def approve(source, actor):
    return transition_source(
        source_id=source.pk,
        action="approve",
        actor=actor,
        expected_status="PENDING_VALIDATION",
        expected_public=False,
    )


def test_pending_source_saves_draft_but_atomic_verify_rolls_back(client, records):
    actor, source, _ = records
    client.force_login(actor)
    url = reverse("admin_portal:evacuation-center-create")
    response = client.post(
        url,
        payload(
            source, save_action="verify", confirm="on", verified_on=timezone.localdate().isoformat()
        ),
    )
    assert response.status_code == 409
    assert b"Keep a draft" in response.content
    assert b"SYNTHETIC center" in response.content  # entered values preserved
    assert not EvacuationCenter.objects.exists()
    assert not LogEntry.objects.exists()
    response = client.post(url, payload(source))
    assert response.status_code == 302
    assert EvacuationCenter.objects.get().verification_status == "DRAFT"


def test_save_submit_both_is_single_request_and_audited(client, records):
    actor, source, _ = records
    client.force_login(actor)
    response = client.post(
        reverse("admin_portal:evacuation-center-create"), payload(source, save_action="submit-both")
    )
    assert response.status_code == 302
    assert EvacuationCenter.objects.get().verification_status == "IN_REVIEW"
    source.refresh_from_db()
    assert source.status == "PENDING_VALIDATION"
    assert not source.is_publicly_releasable
    assert LogEntry.objects.count() == 3


def test_approve_source_and_verify_center_uses_normal_transitions(client, records):
    actor, source, _ = records
    client.force_login(actor)
    response = client.post(
        reverse("admin_portal:evacuation-center-create"),
        payload(
            source,
            save_action="approve-verify",
            confirm="on",
            verified_on=timezone.localdate().isoformat(),
        ),
    )
    assert response.status_code == 302
    center = EvacuationCenter.objects.get()
    source.refresh_from_db()
    assert source.status == "APPROVED" and not source.is_publicly_releasable
    assert center.verification_status == "VERIFIED" and center.capacity is None
    assert not dict(resident_checklist(center))["All current API gates and safe public fields"]
    assert LogEntry.objects.count() == 4


def test_failed_combined_source_approval_leaves_no_center_or_audit(client, records):
    actor, source, _ = records
    source.custodian = ""
    source.save()
    client.force_login(actor)
    response = client.post(
        reverse("admin_portal:evacuation-center-create"),
        payload(
            source,
            save_action="approve-verify",
            confirm="on",
            verified_on=timezone.localdate().isoformat(),
        ),
    )
    assert response.status_code == 409
    source.refresh_from_db()
    assert source.status == "PENDING_VALIDATION"
    assert not EvacuationCenter.objects.exists() and not LogEntry.objects.exists()


def test_combined_permission_denied_even_if_staff(client, records):
    _, source, _ = records
    editor = get_user_model().objects.create_user(email="editor@example.test", is_staff=True)
    editor.user_permissions.set(
        Permission.objects.filter(codename__in=("add_evacuationcenter", "change_evacuationcenter"))
    )
    client.force_login(editor)
    response = client.post(
        reverse("admin_portal:evacuation-center-create"),
        payload(
            source,
            save_action="approve-verify",
            confirm="on",
            verified_on=timezone.localdate().isoformat(),
        ),
    )
    assert response.status_code == 403
    assert not EvacuationCenter.objects.exists()


def test_save_add_another_reuses_metadata_not_identity_or_capacity(client, records):
    actor, source, area = records
    client.force_login(actor)
    response = client.post(
        reverse("admin_portal:evacuation-center-create"),
        payload(
            source,
            save_action="add-another",
            geographic_area=area.pk,
            limitations="Synthetic session limitation",
        ),
    )
    assert response.status_code == 302
    next_page = client.get(response.url)
    form = next_page.context["form"]
    assert form.initial["source"] == source.pk
    assert form.initial["geographic_area"] == area.pk
    assert not form["name"].value() and not form["capacity"].value()


def test_inline_source_creation_and_error_responses(client, records):
    actor, _, _ = records
    client.force_login(actor)
    url = reverse("admin_portal:source-inline-create")
    assert "html" in client.get(url).json()
    data = {"inline-name": "Synthetic inline source", "inline-source_type": "OTHER"}
    response = client.post(url, data)
    assert response.status_code == 200 and response.json()["state"] == "Pending validation"
    assert not response.json()["public"]
    failed = client.post(url, {**data, "save_action": "approve", "inline-confirm": "on"})
    assert failed.status_code == 409
    assert "Synthetic inline source" in failed.json()["html"]
    assert DataSource.objects.filter(name="Synthetic inline source").count() == 1


def test_stale_draft_save_cannot_overwrite_changed_record(records):
    actor, source, _ = records
    center = EvacuationCenter.objects.create(
        name="Old synthetic", address="Synthetic", latitude="0.5", longitude="0.5", source=source
    )
    old = center.updated_at
    center.address = "Newer value"
    center.save()
    form = FastCenterForm(
        payload(source, name=center.name, expected_updated_at=old.isoformat()), instance=center
    )
    assert form.is_valid()
    with pytest.raises(ValidationError, match="changed"):
        save_center(form=form, actor=actor, expected=old)
    center.refresh_from_db()
    assert center.address == "Newer value"


def test_import_validates_every_row_and_records_rejections_without_center_mutations(records):
    actor, source, area = records
    batch = stage_batch(
        upload=csv_upload(
            [
                ["Synthetic A", "A", area.code, "0.2", "0.2", ""],
                ["Synthetic B", "B", area.code, "999", "0.3", ""],
                ["Synthetic C", "C", "UNKNOWN", "0.4", "0.4", ""],
                ["Synthetic D", "D", area.code, "2", "2", ""],
                [],
            ],
            "C:\\private\\synthetic.csv",
        ),
        source=source,
        actor=actor,
        shared_limitations="Synthetic shared limits",
    )
    assert not EvacuationCenter.objects.exists()
    assert batch.filename == "synthetic.csv" and batch.row_count == 5
    assert batch.valid_count == 1 and batch.invalid_count == 4
    assert all(row["errors"] for row in batch.rows[1:])
    import_batch(batch_id=batch.pk, actor=actor)
    assert EvacuationCenter.objects.count() == 1
    center = EvacuationCenter.objects.get()
    assert center.verification_status == "DRAFT" and center.capacity is None
    assert center.limitations == "Synthetic shared limits"
    with pytest.raises(ValidationError, match="already imported"):
        import_batch(batch_id=batch.pk, actor=actor)


@pytest.mark.parametrize(
    "rows",
    [
        [["Name", "A", "", "0.2", "0.2", ""], [" name ", "B", "", "0.3", "0.3", ""]],
        [["A", "A", "", "0.2", "0.2", ""], ["B", "B", "", "0.200", "0.2000", ""]],
    ],
)
def test_all_duplicate_candidates_are_rejected_not_silently_merged(records, rows):
    _, source, _ = records
    result = validate_rows(rows, source)
    assert all(any("duplicate" in e for e in row["errors"]) for row in result)


def test_stale_import_rolls_back_every_valid_row(records):
    actor, source, _ = records
    batch = stage_batch(
        upload=csv_upload([["A", "A", "", "0.2", "0.2", ""], ["B", "B", "", "0.3", "0.3", ""]]),
        source=source,
        actor=actor,
    )
    source.limitations = "Changed after preview"
    source.save()
    with pytest.raises(ValidationError, match="Source metadata changed"):
        import_batch(batch_id=batch.pk, actor=actor)
    assert not EvacuationCenter.objects.exists()
    batch.refresh_from_db()
    assert batch.imported_count == 0 and batch.imported_at is None


def test_excel_literals_formulas_and_exact_headers(records):
    from zipfile import ZipFile

    from openpyxl import Workbook

    actor, source, _ = records
    workbook = Workbook()
    workbook.active.append(HEADERS)
    workbook.active.append(["Synthetic Excel A", "A", "", 0.25, 0.25, ""])
    workbook.active.append(['=HYPERLINK("https://example.test")', "B", "", 0.4, 0.4, ""])
    buffer = io.BytesIO()
    workbook.save(buffer)
    batch = stage_batch(
        upload=SimpleUploadedFile("synthetic.xlsx", buffer.getvalue()), source=source, actor=actor
    )
    assert batch.valid_count == 1 and batch.invalid_count == 1
    assert any("Formulas" in e for e in batch.rows[1]["errors"])
    with pytest.raises(ValidationError, match="Headers"):
        read_upload(SimpleUploadedFile("bad.csv", b"unexpected,headers\nA,B"))
    with pytest.raises(ValidationError):
        read_upload(SimpleUploadedFile("bad.xlsx", b"not a zip archive"))
    malformed = io.BytesIO()
    with ZipFile(io.BytesIO(buffer.getvalue())) as original, ZipFile(malformed, "w") as corrupt:
        for member in original.infolist():
            content = (
                b"<broken"
                if member.filename == "xl/workbook.xml"
                else original.read(member.filename)
            )
            corrupt.writestr(member.filename, content)
    with pytest.raises(ValidationError, match="could not be read"):
        read_upload(SimpleUploadedFile("malformed.xlsx", malformed.getvalue()))


def test_bulk_preview_has_no_persistent_mutation_and_reports_ineligible(records):
    actor, source, _ = records
    approved = approve(source, actor)
    first = EvacuationCenter.objects.create(
        name="A",
        address="A",
        latitude=0.2,
        longitude=0.2,
        source=approved,
        verification_status="IN_REVIEW",
    )
    other = EvacuationCenter.objects.create(
        name="B", address="B", latitude=0.3, longitude=0.3, source=approved
    )
    before_logs = LogEntry.objects.count()
    preview = preview_bulk(
        module="centers",
        ids=[first.pk, other.pk],
        action="verify",
        actor=actor,
        verified_on=timezone.localdate(),
    )
    assert len(preview["eligible"]) == len(preview["rejected"]) == 1
    first.refresh_from_db()
    assert first.verification_status == "IN_REVIEW" and LogEntry.objects.count() == before_logs
    assert execute_bulk(token=preview["token"], actor=actor) == (1, 1)
    first.refresh_from_db()
    other.refresh_from_db()
    assert first.verification_status == "VERIFIED" and first.capacity is None
    assert other.verification_status == "DRAFT"


def test_bulk_stale_or_permission_revocation_rolls_back_all(records):
    actor, source, _ = records
    centers = [
        EvacuationCenter.objects.create(
            name=str(n), address="Synthetic", latitude=0.2, longitude=0.2, source=source
        )
        for n in range(2)
    ]
    preview = preview_bulk(
        module="centers", ids=[c.pk for c in centers], action="submit", actor=actor
    )
    centers[-1].notes = "Changed after preview"
    centers[-1].save()
    with pytest.raises(ValidationError, match="changed"):
        execute_bulk(token=preview["token"], actor=actor)
    assert all(c.verification_status == "DRAFT" for c in EvacuationCenter.objects.all())
    preview = preview_bulk(
        module="centers", ids=[c.pk for c in centers], action="submit", actor=actor
    )
    actor.user_permissions.remove(Permission.objects.get(codename="change_evacuationcenter"))
    actor = get_user_model().objects.get(pk=actor.pk)  # invalidate permission cache
    with pytest.raises(PermissionDenied):
        execute_bulk(token=preview["token"], actor=actor)
    assert all(c.verification_status == "DRAFT" for c in EvacuationCenter.objects.all())


def test_import_hundreds_then_one_source_review_and_bulk_verification(records):
    actor, source, _ = records
    count = 200
    batch = stage_batch(
        upload=csv_upload(
            [
                [f"Synthetic {n}", "Test", "", f"{0.1 + n / 1000:.6f}", "0.2", ""]
                for n in range(count)
            ]
        ),
        source=source,
        actor=actor,
    )
    assert batch.valid_count == count
    import_batch(batch_id=batch.pk, actor=actor)
    ids = list(EvacuationCenter.objects.values_list("pk", flat=True))
    submit = preview_bulk(module="centers", ids=ids, action="submit", actor=actor)
    assert execute_bulk(token=submit["token"], actor=actor) == (count, 0)
    approve(source, actor)
    verify = preview_bulk(
        module="centers", ids=ids, action="verify", actor=actor, verified_on=timezone.localdate()
    )
    assert execute_bulk(token=verify["token"], actor=actor) == (count, 0)
    assert (
        EvacuationCenter.objects.filter(
            verification_status="VERIFIED", capacity__isnull=True
        ).count()
        == count
    )
    assert all(
        not dict(resident_checklist(c))["Supported geographic identity"]
        for c in EvacuationCenter.objects.all()[:2]
    )


def test_report_formula_safety_and_import_permission(client, records):
    actor, source, _ = records
    batch = stage_batch(
        upload=csv_upload([["=BAD()", "A", "", "0.2", "0.2", ""]]), source=source, actor=actor
    )
    client.force_login(actor)
    response = client.get(reverse("admin_portal:center-import-errors", args=[batch.pk]))
    assert "'=BAD()" in response.content.decode()
    viewer = get_user_model().objects.create_user(email="only-view@example.test", is_staff=True)
    viewer.user_permissions.add(Permission.objects.get(codename="view_evacuationcenter"))
    client.force_login(viewer)
    assert (
        client.post(
            reverse("admin_portal:center-import-detail", args=[batch.pk]), {"confirm": "on"}
        ).status_code
        == 403
    )
    assert not EvacuationCenter.objects.exists()


def test_review_queue_select_all_matching_and_explicit_batch_confirm(client, records):
    actor, source, _ = records
    EvacuationCenter.objects.create(
        name="One", address="Synthetic", latitude=0.2, longitude=0.2, source=source
    )
    client.force_login(actor)
    url = reverse("admin_portal:review-queue", args=["centers"])
    preview = client.post(url, {"all_matching": "on", "action": "submit"})
    assert preview.status_code == 200
    token = preview.context["preview"]["token"]
    assert client.post(url, {"token": token}).status_code == 409
    assert client.post(url, {"token": token, "confirm": "on"}).status_code == 302
    assert EvacuationCenter.objects.get().verification_status == "IN_REVIEW"
    assert client.post(url, {"token": token + "tampered", "confirm": "on"}).status_code == 409
    assert (
        client.post(
            url, {"batch": "invalid", "all_matching": "on", "action": "return-draft"}
        ).status_code
        == 409
    )
    assert EvacuationCenter.objects.get().verification_status == "IN_REVIEW"


def test_future_date_unknown_capacity_and_malformed_rows_are_not_defaults(records):
    actor, source, _ = records
    form = FastCenterForm(
        payload(source, verified_on=(timezone.localdate() + timedelta(days=1)).isoformat())
    )
    assert not form.is_valid()
    result = validate_rows([["A", "A", "", "NaN", "0.2", ""], ["B", "B"]], source)
    assert all(r["errors"] for r in result)
    assert not CenterImportBatch.objects.exists()
