from django.contrib.admin.models import CHANGE, LogEntry
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import LegalDocumentVersion, OnboardingVersion


def _log(actor, item, message):
    LogEntry.objects.log_actions(
        user_id=actor.pk,
        queryset=[item],
        action_flag=CHANGE,
        change_message=message,
        single_object=True,
    )


@transaction.atomic
def submit_legal_for_review(*, document_id: int, actor) -> LegalDocumentVersion:
    if not actor.has_perm("accounts.change_legaldocumentversion"):
        raise PermissionDenied
    document = LegalDocumentVersion.objects.select_for_update().get(pk=document_id)
    if document.status != LegalDocumentVersion.Status.DRAFT:
        raise ValidationError("Only a draft legal version can be submitted.")
    if not document.sections.exists():
        raise ValidationError("A legal version needs at least one section.")
    document.status = LegalDocumentVersion.Status.REVIEW
    document.save(update_fields=("status", "updated_at"))
    _log(actor, document, "Submitted legal document version for review.")
    return document


@transaction.atomic
def publish_legal(*, document_id: int, actor) -> LegalDocumentVersion:
    if not actor.has_perm("accounts.publish_legaldocumentversion"):
        raise PermissionDenied
    document = (
        LegalDocumentVersion.objects.select_for_update()
        .prefetch_related("sections")
        .get(pk=document_id)
    )
    if document.status != LegalDocumentVersion.Status.REVIEW:
        raise ValidationError("Only an in-review legal version can be published.")
    if not document.sections.exists():
        raise ValidationError("A legal version needs at least one section.")
    LegalDocumentVersion.objects.filter(
        document_type=document.document_type,
        status=LegalDocumentVersion.Status.PUBLISHED,
    ).exclude(pk=document.pk).update(status=LegalDocumentVersion.Status.RETIRED)
    document.status = LegalDocumentVersion.Status.PUBLISHED
    document.published_at = timezone.now()
    document.reviewed_by = actor
    document.full_clean()
    document.save(
        update_fields=("status", "published_at", "reviewed_by", "updated_at")
    )
    _log(actor, document, "Published reviewed legal document version.")
    return document


@transaction.atomic
def publish_onboarding(*, version_id: int, actor) -> OnboardingVersion:
    if not actor.has_perm("accounts.publish_onboardingversion"):
        raise PermissionDenied
    version = OnboardingVersion.objects.select_for_update().get(pk=version_id)
    if version.status != OnboardingVersion.Status.DRAFT:
        raise ValidationError("Only draft onboarding can be published.")
    OnboardingVersion.objects.filter(status=OnboardingVersion.Status.PUBLISHED).exclude(
        pk=version.pk
    ).update(status=OnboardingVersion.Status.RETIRED)
    version.status = OnboardingVersion.Status.PUBLISHED
    version.published_at = timezone.now()
    version.full_clean()
    version.save(update_fields=("status", "published_at"))
    _log(actor, version, "Published resident onboarding version.")
    return version
