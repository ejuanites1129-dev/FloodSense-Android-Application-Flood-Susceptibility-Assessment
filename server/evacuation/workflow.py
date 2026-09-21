from dataclasses import dataclass
from datetime import date

from django.contrib.admin.models import CHANGE, LogEntry
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from provenance.models import PublicationStatus

from .models import EvacuationCenter


@dataclass(frozen=True)
class CenterTransition:
    action: str
    label: str
    source_status: str
    target_status: str
    permission: str
    confirmation: str
    resident_visibility_effect: str

    @property
    def target_label(self) -> str:
        return EvacuationCenter.VerificationStatus(self.target_status).label


TRANSITIONS = {
    item.action: item
    for item in (
        CenterTransition(
            "submit",
            "Submit for review",
            EvacuationCenter.VerificationStatus.DRAFT,
            EvacuationCenter.VerificationStatus.IN_REVIEW,
            "evacuation.change_evacuationcenter",
            "The record will become read-only while its source and location are reviewed.",
            "The record remains excluded from resident nearest-center results.",
        ),
        CenterTransition(
            "return-draft",
            "Return to draft",
            EvacuationCenter.VerificationStatus.IN_REVIEW,
            EvacuationCenter.VerificationStatus.DRAFT,
            "evacuation.change_evacuationcenter",
            "The record will leave the review queue and become editable.",
            "The record remains excluded from resident nearest-center results.",
        ),
        CenterTransition(
            "verify",
            "Verify center",
            EvacuationCenter.VerificationStatus.IN_REVIEW,
            EvacuationCenter.VerificationStatus.VERIFIED,
            "evacuation.verify_evacuationcenter",
            "Verification confirms the record against its approved source; it does "
            "not issue an evacuation order.",
            "The record can appear to residents only when every current center, source, "
            "public-field, and geographic-identity eligibility gate also passes.",
        ),
        CenterTransition(
            "deactivate",
            "Mark inactive",
            EvacuationCenter.VerificationStatus.VERIFIED,
            EvacuationCenter.VerificationStatus.INACTIVE,
            "evacuation.deactivate_evacuationcenter",
            "The center will be marked inactive and must not be treated as currently available.",
            "The record is removed from resident nearest-center results on the next request.",
        ),
        CenterTransition(
            "reactivate-review",
            "Return to review",
            EvacuationCenter.VerificationStatus.INACTIVE,
            EvacuationCenter.VerificationStatus.IN_REVIEW,
            "evacuation.change_evacuationcenter",
            "The inactive record will require fresh verification before it can be active again.",
            "The record remains excluded from resident nearest-center results until reverified.",
        ),
    )
}


def available_transitions(center: EvacuationCenter, actor) -> list[CenterTransition]:
    return [
        item
        for item in TRANSITIONS.values()
        if item.source_status == center.verification_status and actor.has_perm(item.permission)
    ]


def log_center_action(*, actor, center, message, action_flag=CHANGE) -> None:
    LogEntry.objects.log_actions(
        user_id=actor.pk,
        queryset=[center],
        action_flag=action_flag,
        change_message=message,
        single_object=True,
    )


@transaction.atomic
def transition_center(
    *,
    center_id: int,
    action: str,
    actor,
    expected_status: str,
    verified_on: date | None = None,
    capacity: int | None = None,
) -> EvacuationCenter:
    transition = TRANSITIONS.get(action)
    if transition is None:
        raise ValidationError("Unknown verification action.")
    if not actor.has_perm(transition.permission):
        raise PermissionDenied
    center = EvacuationCenter.objects.select_for_update().select_related("source").get(pk=center_id)
    if center.verification_status != expected_status:
        raise ValidationError(
            "This center changed after the confirmation page opened. Review it and try again."
        )
    if center.verification_status != transition.source_status:
        raise ValidationError("This action is not valid from the current state.")
    if action == "verify" and verified_on and verified_on > timezone.localdate():
        raise ValidationError("The verification date cannot be in the future.")

    previous = center.get_verification_status_display()
    center.verification_status = transition.target_status
    if action == "verify":
        center.verified_on = verified_on
        center.capacity = capacity
        center.publication_status = PublicationStatus.APPROVED
    elif action == "deactivate":
        center.publication_status = PublicationStatus.RETIRED
    elif action in {"reactivate-review", "return-draft"}:
        center.verified_on = None
        center.capacity = None
        center.publication_status = PublicationStatus.PENDING_VALIDATION
    center.full_clean()
    center.save()
    log_center_action(
        actor=actor,
        center=center,
        message=(
            f"Center verification changed from {previous} to "
            f"{center.get_verification_status_display()} through the management portal."
        ),
    )
    return center
