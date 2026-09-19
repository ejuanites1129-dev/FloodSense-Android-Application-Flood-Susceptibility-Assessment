"""Validated, permission-checked preparedness-guidance workflow transitions."""

from dataclasses import dataclass

from django.contrib.admin.models import CHANGE, LogEntry
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import GuidanceItem


@dataclass(frozen=True)
class Transition:
    action: str
    label: str
    source_status: str
    target_status: str
    permission: str
    confirmation: str


TRANSITIONS = {
    transition.action: transition
    for transition in (
        Transition(
            action="submit",
            label="Submit for review",
            source_status=GuidanceItem.WorkflowStatus.DRAFT,
            target_status=GuidanceItem.WorkflowStatus.IN_REVIEW,
            permission="dss.change_guidanceitem",
            confirmation="Editors cannot change this item while it is in review.",
        ),
        Transition(
            action="return-draft",
            label="Return to draft",
            source_status=GuidanceItem.WorkflowStatus.IN_REVIEW,
            target_status=GuidanceItem.WorkflowStatus.DRAFT,
            permission="dss.change_guidanceitem",
            confirmation="The item will leave the review queue and become editable.",
        ),
        Transition(
            action="approve",
            label="Approve guidance",
            source_status=GuidanceItem.WorkflowStatus.IN_REVIEW,
            target_status=GuidanceItem.WorkflowStatus.APPROVED,
            permission="dss.approve_guidanceitem",
            confirmation=(
                "Approval records review completion but does not publish this item."
            ),
        ),
        Transition(
            action="revise",
            label="Return approved item to draft",
            source_status=GuidanceItem.WorkflowStatus.APPROVED,
            target_status=GuidanceItem.WorkflowStatus.DRAFT,
            permission="dss.change_guidanceitem",
            confirmation="The approval state will be removed before editing.",
        ),
        Transition(
            action="publish",
            label="Publish guidance",
            source_status=GuidanceItem.WorkflowStatus.APPROVED,
            target_status=GuidanceItem.WorkflowStatus.PUBLISHED,
            permission="dss.publish_guidanceitem",
            confirmation=(
                "Eligible content will become available to resident-facing DSS "
                "responses for its associated result."
            ),
        ),
        Transition(
            action="unpublish",
            label="Unpublish guidance",
            source_status=GuidanceItem.WorkflowStatus.PUBLISHED,
            target_status=GuidanceItem.WorkflowStatus.APPROVED,
            permission="dss.publish_guidanceitem",
            confirmation=(
                "The item will stop appearing in new resident-facing DSS responses."
            ),
        ),
    )
}


def available_transitions(item: GuidanceItem, actor) -> list[Transition]:
    return [
        transition
        for transition in TRANSITIONS.values()
        if transition.source_status == item.workflow_status
        and actor.has_perm(transition.permission)
    ]


def log_guidance_action(
    *, actor, item: GuidanceItem, message: str, action_flag: int = CHANGE
) -> None:
    LogEntry.objects.log_actions(
        user_id=actor.pk,
        queryset=[item],
        action_flag=action_flag,
        change_message=message,
        single_object=True,
    )


@transaction.atomic
def transition_guidance(
    *, item_id: int, action: str, actor, expected_status: str
) -> GuidanceItem:
    transition = TRANSITIONS.get(action)
    if transition is None:
        raise ValidationError("Unknown workflow action.")
    if not actor.has_perm(transition.permission):
        raise PermissionDenied

    item = (
        GuidanceItem.objects.select_for_update()
        .select_related("source", "susceptibility_level")
        .get(pk=item_id)
    )
    if item.workflow_status != expected_status:
        raise ValidationError(
            "This guidance item changed after the confirmation page was opened. "
            "Review its current state and try again."
        )
    if item.workflow_status != transition.source_status:
        raise ValidationError("This workflow action is not valid from the current state.")

    previous_label = item.get_workflow_status_display()
    item.workflow_status = transition.target_status
    item.is_enabled = transition.target_status == GuidanceItem.WorkflowStatus.PUBLISHED
    item.full_clean()
    item.save(update_fields=("workflow_status", "is_enabled", "updated_at"))
    log_guidance_action(
        actor=actor,
        item=item,
        message=(
            f"Guidance workflow changed from {previous_label} to "
            f"{item.get_workflow_status_display()} through the management portal."
        ),
    )
    return item
