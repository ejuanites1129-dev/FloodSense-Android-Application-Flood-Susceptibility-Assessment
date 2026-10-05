from dataclasses import dataclass

from core.local_testing import local_testing_enabled
from django.contrib.admin.models import CHANGE, LogEntry
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from geography.boundaries import is_bacoor_boundary_source

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

TRANSITIONS.update(
    {
        "approve-boundary": SourceTransition(
            "approve-boundary",
            "Approve boundary metadata",
            PublicationStatus.PENDING_VALIDATION,
            PublicationStatus.APPROVED,
            True,
            True,
            "provenance.approve_datasource",
            "Record internal administrative-boundary review and retain existing geometry release. "
            "This is not City endorsement, flood-data approval or facility verification.",
        ),
        "return-boundary-review": SourceTransition(
            "return-boundary-review",
            "Return boundary metadata to review",
            PublicationStatus.APPROVED,
            PublicationStatus.PENDING_VALIDATION,
            True,
            True,
            "provenance.change_datasource",
            "Remove internal metadata approval while retaining existing boundary release. "
            "Flood-data and facility approval remain separate.",
        ),
        "approve-test": SourceTransition(
            "approve-test",
            "Approve for local testing",
            PublicationStatus.DEMONSTRATION,
            PublicationStatus.DEMONSTRATION,
            False,
            False,
            "provenance.approve_datasource",
            "Record local test metadata review only. This does not approve agency evidence "
            "or enable public release.",
        ),
        "return-test-review": SourceTransition(
            "return-test-review",
            "Return temporary source to review",
            PublicationStatus.DEMONSTRATION,
            PublicationStatus.DEMONSTRATION,
            False,
            False,
            "provenance.change_datasource",
            "Remove local test approval. Test centers will be withheld on their next refresh.",
        ),
    }
)


def available_transitions(source: DataSource, actor) -> list[SourceTransition]:
    boundary = is_bacoor_boundary_source(source)
    return [
        item
        for item in TRANSITIONS.values()
        if item.source_status == source.status
        and item.source_public == source.is_publicly_releasable
        and actor.has_perm(item.permission)
        and (item.action not in {"approve-boundary", "return-boundary-review"} or boundary)
        and (
            item.action not in {"approve-test", "return-test-review"}
            or local_testing_enabled()
            and source.is_temporary
            and source.test_approved == (item.action == "return-test-review")
        )
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
    *,
    source_id: int,
    action: str,
    actor,
    expected_status: str,
    expected_public: bool,
    expected_updated_at=None,
) -> DataSource:
    transition = TRANSITIONS.get(action)
    if transition is None:
        raise ValidationError("Unknown source workflow action.")
    if not actor.has_perm(transition.permission):
        raise PermissionDenied
    source = DataSource.objects.select_for_update().get(pk=source_id)
    if action in {"approve-boundary", "return-boundary-review"} and not is_bacoor_boundary_source(
        source
    ):
        raise ValidationError(
            "This action is only for the controlled administrative-boundary source."
        )
    if action in {"approve-test", "return-test-review"}:
        if not local_testing_enabled() or not source.is_temporary:
            raise ValidationError("Temporary source actions require the local testing environment.")
        if source.test_approved != (action == "return-test-review"):
            raise ValidationError(
                "The temporary source review state changed. Refresh and try again."
            )
    if expected_updated_at is not None:
        from core.record_workflow import require_fresh

        require_fresh(source, expected_updated_at)
    if source.status != expected_status or source.is_publicly_releasable != expected_public:
        raise ValidationError(
            "This source changed after the confirmation page opened. Review it and try again."
        )
    if (
        source.status != transition.source_status
        or source.is_publicly_releasable != transition.source_public
    ):
        raise ValidationError("This action is not valid from the current state.")
    if action in {"approve", "approve-test", "approve-boundary"}:
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
        if action != "approve-test" and source.source_type == DataSource.SourceType.DEMONSTRATION:
            raise ValidationError(
                "Demonstration sources must remain visibly labeled as demonstration data."
            )

    previous = source.get_status_display()
    source.status = transition.target_status
    source.is_publicly_releasable = transition.target_public
    if action in {"approve", "approve-test", "approve-boundary"}:
        source.reviewed_by = actor
        source.reviewed_on = timezone.localdate()
    elif action in {"return-review", "return-test-review", "return-boundary-review"}:
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
