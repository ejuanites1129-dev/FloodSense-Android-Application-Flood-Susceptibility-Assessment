"""Atomic conveniences over the existing permission-checked state machines.

No staff flag establishes data validity. A combined action either completes all
normal transitions and audit entries, or rolls back the entire save.
"""

from core.local_testing import local_testing_enabled
from core.record_workflow import center_write_lock, require_fresh, require_permission
from django.contrib.admin.models import ADDITION
from django.core.exceptions import ValidationError
from django.db import transaction
from evacuation.models import EvacuationCenter
from evacuation.workflow import log_center_action, transition_center
from geography.boundaries import is_bacoor_boundary_source
from provenance.models import DataSource, PublicationStatus
from provenance.workflow import log_source_action, transition_source


@transaction.atomic
def save_source(*, form, actor, action="save", expected=None):
    require_permission(actor, f"provenance.{'change' if form.instance.pk else 'add'}_datasource")
    if action not in {"save", "add-another", "approve", "approve-publish"}:
        raise ValidationError("Unknown source save action.")
    created = not form.instance.pk
    if not created:
        locked = DataSource.objects.select_for_update().get(pk=form.instance.pk)
        require_fresh(locked, expected)
        if locked.status != PublicationStatus.PENDING_VALIDATION and not (
            locked.is_temporary and local_testing_enabled()
        ):
            raise ValidationError("Only pending source metadata can be edited.")
    source = form.save(commit=False)
    temporary = source.source_type == DataSource.SourceType.DEMONSTRATION
    if not created and locked.is_temporary != temporary:
        raise ValidationError("Do not convert between temporary and genuine provenance.")
    if temporary and (not local_testing_enabled() or not form.allow_temporary):
        raise ValidationError("Temporary source entry requires local testing mode.")
    if temporary and action == "approve-publish":
        raise ValidationError(
            "Temporary sources cannot be released publicly. Choose local test approval instead."
        )
    source.status = (
        PublicationStatus.DEMONSTRATION if temporary else PublicationStatus.PENDING_VALIDATION
    )
    boundary = not created and is_bacoor_boundary_source(locked)
    source.is_publicly_releasable = locked.is_publicly_releasable if boundary else False
    if temporary:
        source.reviewed_by = None
        source.reviewed_on = None
    source.full_clean()
    source.save()
    log_source_action(
        actor=actor,
        source=source,
        action_flag=ADDITION if created else 2,
        message="Saved pending source metadata through the management portal.",
    )
    if action in {"approve", "approve-publish"}:
        source = transition_source(
            source_id=source.pk,
            action="approve-test"
            if temporary
            else "approve-boundary"
            if boundary and source.is_publicly_releasable
            else "approve",
            actor=actor,
            expected_status=source.status,
            expected_public=source.is_publicly_releasable,
        )
    if action == "approve-publish" and not source.is_publicly_releasable:
        source = transition_source(
            source_id=source.pk,
            action="publish",
            actor=actor,
            expected_status=source.status,
            expected_public=False,
        )
    return source


@transaction.atomic
def save_center(*, form, actor, action="save", expected=None, verified_on=None, capacity=None):
    require_permission(
        actor, f"evacuation.{'change' if form.instance.pk else 'add'}_evacuationcenter"
    )
    if action not in {
        "save",
        "add-another",
        "submit",
        "submit-both",
        "verify",
        "approve-verify",
        "verify-release",
    }:
        raise ValidationError("Unknown center save action.")
    center_write_lock()
    source = DataSource.objects.select_for_update().get(pk=form.cleaned_data["source"].pk)
    if is_bacoor_boundary_source(source):
        raise ValidationError(
            "Choose facility evidence, not the reserved administrative boundary source."
        )
    temporary = source.is_temporary
    if temporary and (not local_testing_enabled() or not form.allow_temporary):
        raise ValidationError("Temporary records require local testing mode.")
    if temporary and action == "verify-release":
        raise ValidationError("Temporary records cannot receive public release.")
    if action in {"approve-verify", "verify-release"}:
        require_fresh(source, form.cleaned_data.get("expected_source_updated_at"))
    created = not form.instance.pk
    if not created:
        locked = EvacuationCenter.objects.select_for_update().get(pk=form.instance.pk)
        require_fresh(locked, expected)
        if locked.is_temporary != temporary:
            raise ValidationError("Do not convert between temporary and genuine facilities.")
        if locked.verification_status != "DRAFT" and not (
            locked.is_temporary and local_testing_enabled()
        ):
            raise ValidationError("Only draft centers can be edited.")
    # Re-run duplicate/source validation after the write lock, not just on POST bind.
    form.full_clean()
    if not form.is_valid():
        raise ValidationError("Correct the draft fields before saving.")
    center = form.save(commit=False)
    center.source = source
    center.verification_status = "DRAFT"
    center.full_clean()
    center.save()
    log_center_action(
        actor=actor,
        center=center,
        action_flag=ADDITION if created else 2,
        message=(
            "Saved evacuation-center draft through the management portal."
            if created
            else "Evacuation-center draft edited. Changed fields: "
            + ", ".join(name for name in form.changed_data if name in form._meta.fields)
            + "."
        ),
    )
    if action == "submit-both":
        require_permission(actor, "provenance.change_datasource")
        if source.status != PublicationStatus.PENDING_VALIDATION and not temporary:
            raise ValidationError(
                "Submit both requires a pending source. Approved sources need no resubmission."
            )
        log_source_action(
            actor=actor,
            source=source,
            message="Requested review of pending source with a center submission.",
        )
    if action == "approve-verify" and not (temporary and source.test_approved):
        source = transition_source(
            source_id=source.pk,
            action="approve-test" if temporary else "approve",
            actor=actor,
            expected_status=source.status,
            expected_public=source.is_publicly_releasable,
        )
    if action not in {"save", "add-another"}:
        center = transition_center(
            center_id=center.pk, action="submit", actor=actor, expected_status="DRAFT"
        )
    if action in {"verify", "approve-verify", "verify-release"}:
        if not temporary and not verified_on:
            raise ValidationError(
                "Supply the documented verification date. Capacity may stay blank."
            )
        center = transition_center(
            center_id=center.pk,
            action="approve-test" if temporary else "verify",
            actor=actor,
            expected_status="IN_REVIEW",
            verified_on=verified_on,
            capacity=capacity,
        )
    if action == "verify-release":
        # Explicit release convenience; never silently grant release with verification.
        require_permission(actor, "provenance.publish_datasource")
        if not source.is_publicly_releasable:
            transition_source(
                source_id=source.pk,
                action="publish",
                actor=actor,
                expected_status=source.status,
                expected_public=False,
            )
    return center
