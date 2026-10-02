"""Canonical, locked, permission-checked structured content workflow."""

from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import DSSContentBlock, DSSFlowVersion, DSSOption, DSSOutcome, DSSQuestion
from .services import validate_dss_flow


def _permission(actor, permission):
    if not actor.is_active or not actor.is_staff or not actor.has_perm(permission):
        raise PermissionDenied


def _current_flow(flow_id, expected_updated_at):
    flow = DSSFlowVersion.objects.select_for_update().select_related("source").get(pk=flow_id)
    if expected_updated_at is not None:
        expected = (
            parse_datetime(expected_updated_at)
            if isinstance(expected_updated_at, str)
            else expected_updated_at
        )
        if expected != flow.updated_at:
            raise ValidationError(
                "This flow changed after the page was opened. "
                "Review its current state and try again."
            )
    return flow


def _log(flow, actor, message, action=CHANGE):
    LogEntry.objects.log_actions(
        user_id=actor.pk,
        queryset=[flow],
        action_flag=action,
        change_message=message,
        single_object=True,
    )


@transaction.atomic
def submit_dss_flow(*, flow_id: int, actor, expected_updated_at=None) -> DSSFlowVersion:
    _permission(actor, "dss.review_dssflowversion")
    flow = _current_flow(flow_id, expected_updated_at)
    if flow.workflow_status != DSSFlowVersion.WorkflowStatus.DRAFT:
        raise ValidationError("Only a draft DSS flow can be submitted for review.")
    validate_dss_flow(flow)
    flow.workflow_status = DSSFlowVersion.WorkflowStatus.IN_REVIEW
    flow.full_clean()
    flow.save(update_fields=("workflow_status", "updated_at"))
    _log(flow, actor, "Submitted structured DSS flow version for review.")
    return flow


@transaction.atomic
def publish_dss_flow(*, flow_id: int, actor, expected_updated_at=None) -> DSSFlowVersion:
    _permission(actor, "dss.publish_dssflowversion")
    flow = _current_flow(flow_id, expected_updated_at)
    if flow.workflow_status != DSSFlowVersion.WorkflowStatus.IN_REVIEW:
        raise ValidationError("Only an in-review flow can be published.")
    validate_dss_flow(flow)
    if (
        DSSFlowVersion.objects.filter(
            code=flow.code,
            operating_mode=flow.operating_mode,
            workflow_status=DSSFlowVersion.WorkflowStatus.PUBLISHED,
        )
        .exclude(pk=flow.pk)
        .exists()
    ):
        raise ValidationError(
            "A version of this flow is already published. Retire it explicitly before publication."
        )
    flow.workflow_status = DSSFlowVersion.WorkflowStatus.PUBLISHED
    flow.published_at = timezone.now()
    flow.reviewed_on = timezone.localdate()
    flow.full_clean()
    flow.save(update_fields=("workflow_status", "published_at", "reviewed_on", "updated_at"))
    _log(flow, actor, "Published validated structured DSS flow version.")
    return flow


@transaction.atomic
def return_dss_flow_to_draft(*, flow_id: int, actor, expected_updated_at=None) -> DSSFlowVersion:
    _permission(actor, "dss.review_dssflowversion")
    flow = _current_flow(flow_id, expected_updated_at)
    if flow.workflow_status != DSSFlowVersion.WorkflowStatus.IN_REVIEW:
        raise ValidationError("Only an in-review DSS flow may return to draft.")
    flow.workflow_status = DSSFlowVersion.WorkflowStatus.DRAFT
    flow.save(update_fields=("workflow_status", "updated_at"))
    _log(flow, actor, "Returned structured DSS flow version to draft for revision.")
    return flow


@transaction.atomic
def retire_dss_flow(*, flow_id: int, actor, expected_updated_at=None) -> DSSFlowVersion:
    _permission(actor, "dss.publish_dssflowversion")
    flow = _current_flow(flow_id, expected_updated_at)
    if flow.workflow_status != DSSFlowVersion.WorkflowStatus.PUBLISHED:
        raise ValidationError("Only a published DSS version can be retired.")
    flow.workflow_status = DSSFlowVersion.WorkflowStatus.RETIRED
    flow.full_clean()
    flow.save(update_fields=("workflow_status", "updated_at"))
    _log(flow, actor, "Retired structured DSS flow version; preserved its publication history.")
    return flow


def _copy_fields(instance, excluded):
    return {
        field.attname: getattr(instance, field.attname)
        for field in instance._meta.local_fields
        if not field.primary_key
        and field.name not in excluded
        and not getattr(field, "auto_now", False)
        and not getattr(field, "auto_now_add", False)
    }


@transaction.atomic
def clone_dss_flow(
    *, flow_id: int, version: str, actor, expected_updated_at=None
) -> DSSFlowVersion:
    _permission(actor, "dss.add_dssflowversion")
    _permission(actor, "dss.change_dssflowversion")
    original = _current_flow(flow_id, expected_updated_at)
    clone = DSSFlowVersion(
        **_copy_fields(original, {"version", "workflow_status", "published_at", "reviewed_on"}),
        version=version,
        workflow_status=DSSFlowVersion.WorkflowStatus.DRAFT,
        published_at=None,
        reviewed_on=None,
    )
    clone.full_clean()
    clone.save()
    clone.susceptibility_levels.set(original.susceptibility_levels.all())
    questions = {}
    outcomes = {}
    for question in original.questions.all():
        questions[question.pk] = DSSQuestion.objects.create(
            **_copy_fields(question, {"flow"}), flow=clone
        )
    for outcome in original.outcomes.all():
        outcomes[outcome.pk] = DSSOutcome.objects.create(
            **_copy_fields(outcome, {"flow"}), flow=clone
        )
    for option in DSSOption.objects.filter(question__flow=original):
        DSSOption.objects.create(
            **_copy_fields(option, {"question", "next_question", "outcome"}),
            question=questions[option.question_id],
            next_question=questions.get(option.next_question_id),
            outcome=outcomes.get(option.outcome_id),
        )
    for block in original.content_blocks.all():
        DSSContentBlock.objects.create(
            **_copy_fields(block, {"flow", "outcome"}),
            flow=clone,
            outcome=outcomes.get(block.outcome_id),
        )
    _log(
        clone,
        actor,
        f"Created draft version from structured DSS flow #{original.pk}; original preserved.",
        ADDITION,
    )
    return clone
