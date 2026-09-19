from dataclasses import dataclass

from django.contrib.admin.models import CHANGE, LogEntry
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import DataSource, PublicationStatus


@dataclass(frozen=True)
class SourceTransition:
    action: str
    label: str
    source_status: str
    target_status: str
    source_public: bool
    target_public: bool
    permission: str
    confirmation: str


TRANSITIONS = {
    item.action: item
    for item in (
        SourceTransition(
            "approve",
            "Approve metadata",
            PublicationStatus.PENDING_VALIDATION,
            PublicationStatus.APPROVED,
            False,
            False,
            "provenance.approve_datasource",
            "Approval records completed metadata review but does not release the source publicly.",
        ),
        SourceTransition(
            "return-review",
            "Return to review",
            PublicationStatus.APPROVED,
            PublicationStatus.PENDING_VALIDATION,
            False,
            False,
            "provenance.change_datasource",
            "The approval will be removed and the metadata will become editable.",
        ),
        SourceTransition(
            "publish",
            "Mark publicly releasable",
            PublicationStatus.APPROVED,
            PublicationStatus.APPROVED,
            False,
            True,
            "provenance.publish_datasource",
            "The source metadata will be eligible for public-facing use under its "
            "recorded restrictions.",
        ),
        SourceTransition(
            "unpublish",
            "Remove public release",
            PublicationStatus.APPROVED,
            PublicationStatus.APPROVED,
            True,
            False,
            "provenance.publish_datasource",
            "The source will no longer be marked publicly releasable.",
        ),
        SourceTransition(
            "restrict",
            "Restrict source",
            PublicationStatus.APPROVED,
            PublicationStatus.RESTRICTED,
            False,
            False,
            "provenance.restrict_datasource",
            "The source will be restricted and unavailable to approved public-data queries.",
        ),
        SourceTransition(
            "restrict-published",
            "Restrict source",
            PublicationStatus.APPROVED,
            PublicationStatus.RESTRICTED,
            True,
            False,
            "provenance.restrict_datasource",
            "Public release will be removed and the source will be restricted.",
        ),
    )
}


def available_transitions(source: DataSource, actor) -> list[SourceTransition]:
    return [
        item
        for item in TRANSITIONS.values()
        if item.source_status == source.status
        and item.source_public == source.is_publicly_releasable
        and actor.has_perm(item.permission)
    ]


def log_source_action(*, actor, source, message, action_flag=CHANGE) -> None:
    LogEntry.objects.log_actions(
        user_id=actor.pk,
        queryset=[source],
        action_flag=action_flag,
        change_message=message,
        single_object=True,
    )


@transaction.atomic
def transition_source(
    *, source_id: int, action: str, actor, expected_status: str, expected_public: bool
) -> DataSource:
    transition = TRANSITIONS.get(action)
    if transition is None:
        raise ValidationError("Unknown source workflow action.")
    if not actor.has_perm(transition.permission):
        raise PermissionDenied
    source = DataSource.objects.select_for_update().get(pk=source_id)
    if source.status != expected_status or source.is_publicly_releasable != expected_public:
        raise ValidationError(
            "This source changed after the confirmation page opened. Review it and try again."
        )
    if (
        source.status != transition.source_status
        or source.is_publicly_releasable != transition.source_public
    ):
        raise ValidationError("This action is not valid from the current state.")
    if action == "approve":
        missing = [
            label
            for value, label in (
                (source.organization, "organization"),
                (source.custodian, "custodian"),
                (source.coverage_description, "coverage"),
                (source.permitted_use, "license or permitted use"),
                (source.limitations, "limitations"),
            )
            if not value.strip()
        ]
        if missing:
            raise ValidationError(
                "Approval requires complete metadata: " + ", ".join(missing) + "."
            )
        if source.source_type == DataSource.SourceType.DEMONSTRATION:
            raise ValidationError(
                "Demonstration sources must remain visibly labeled as demonstration data."
            )

    previous = source.get_status_display()
    source.status = transition.target_status
    source.is_publicly_releasable = transition.target_public
    if action == "approve":
        source.reviewed_by = actor
        source.reviewed_on = timezone.localdate()
    elif action == "return-review":
        source.reviewed_by = None
        source.reviewed_on = None
    source.full_clean()
    source.save()
    log_source_action(
        actor=actor,
        source=source,
        message=(
            f"Source workflow changed from {previous} to {source.get_status_display()}; "
            f"public release is {'enabled' if source.is_publicly_releasable else 'disabled'}."
        ),
    )
    return source
