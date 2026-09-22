from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    EmailVerificationChallenge,
    LegalAcceptance,
    LegalDocumentVersion,
    OnboardingAcknowledgement,
    OnboardingVersion,
    ResidentPreference,
    User,
)


def normalize_email(value: str) -> str:
    return User.objects.normalize_email(value.strip()).lower()


def normalize_username(value: str) -> str:
    return value.strip().lower()


def token_pair_for_user(user: User) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def _digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


@transaction.atomic
def issue_email_verification(user: User) -> None:
    EmailVerificationChallenge.objects.filter(user=user, used_at__isnull=True).delete()
    raw_token = secrets.token_urlsafe(32)
    EmailVerificationChallenge.objects.create(
        user=user,
        token_digest=_digest(raw_token),
        expires_at=timezone.now()
        + timedelta(hours=settings.EMAIL_VERIFICATION_EXPIRY_HOURS),
    )
    query = urlencode({"token": raw_token})
    link = f"{settings.RESIDENT_APP_PUBLIC_URL.rstrip('/')}/verify-email?{query}"
    send_mail(
        subject="Verify your FloodSense email address",
        message=(
            "Open this one-time link to verify your FloodSense email address. "
            f"It expires in {settings.EMAIL_VERIFICATION_EXPIRY_HOURS} hours.\n\n"
            f"{link}\n\nIf you did not create this account, ignore this message."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


@transaction.atomic
def consume_email_verification(raw_token: str) -> User | None:
    try:
        challenge = (
            EmailVerificationChallenge.objects.select_for_update()
            .select_related("user")
            .get(token_digest=_digest(raw_token), used_at__isnull=True)
        )
    except EmailVerificationChallenge.DoesNotExist:
        return None
    now = timezone.now()
    if challenge.expires_at <= now:
        return None
    challenge.used_at = now
    challenge.save(update_fields=("used_at",))
    challenge.user.email_verified_at = now
    challenge.user.save(update_fields=("email_verified_at",))
    return challenge.user


def issue_password_reset(user: User) -> None:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    query = urlencode({"uid": uid, "token": token})
    link = f"{settings.RESIDENT_APP_PUBLIC_URL.rstrip('/')}/reset-password?{query}"
    send_mail(
        subject="Reset your FloodSense password",
        message=(
            "Open this one-time FloodSense password reset link. It expires according "
            "to the configured security policy.\n\n"
            f"{link}\n\nIf you did not request this, ignore this message."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def current_published_legal_documents():
    return LegalDocumentVersion.objects.filter(
        status=LegalDocumentVersion.Status.PUBLISHED
    ).prefetch_related("sections")


def setup_status_for(user: User) -> dict[str, object]:
    legal = list(current_published_legal_documents())
    configured_types = {document.document_type for document in legal}
    legal_configured = configured_types == {
        LegalDocumentVersion.DocumentType.TERMS,
        LegalDocumentVersion.DocumentType.PRIVACY,
    }
    required = [document for document in legal if document.requires_acceptance]
    accepted_ids = set(
        LegalAcceptance.objects.filter(user=user).values_list(
            "document_version_id", flat=True
        )
    )
    missing = [document for document in required if document.pk not in accepted_ids]
    onboarding = OnboardingVersion.objects.filter(
        status=OnboardingVersion.Status.PUBLISHED
    ).first()
    onboarding_pending = bool(
        onboarding
        and not OnboardingAcknowledgement.objects.filter(
            user=user, onboarding_version=onboarding
        ).exists()
    )
    setup_configured = legal_configured and onboarding is not None
    if user.email_verified_at is None:
        stage = "awaiting_email_verification"
    elif not setup_configured:
        stage = "configuration_required"
    elif missing:
        stage = "awaiting_legal_acceptance"
    elif onboarding_pending:
        stage = "awaiting_onboarding"
    else:
        stage = "authenticated_ready"
    return {
        "stage": stage,
        "email_verified": user.email_verified_at is not None,
        "missing_legal_document_ids": [document.pk for document in missing],
        "onboarding_version": onboarding.version if onboarding else None,
        "onboarding_pending": onboarding_pending,
        "setup_configured": setup_configured,
        "missing_configuration": [
            *([] if LegalDocumentVersion.DocumentType.TERMS in configured_types else ["TERMS"]),
            *([] if LegalDocumentVersion.DocumentType.PRIVACY in configured_types else ["PRIVACY"]),
            *([] if onboarding else ["ONBOARDING"]),
        ],
    }


def serialize_user(user: User) -> dict[str, object]:
    identities = list(user.external_identities.values_list("provider", flat=True))
    return {
        "id": user.pk,
        "username": user.resident_username,
        "email": user.email,
        "email_verified": user.email_verified_at is not None,
        "display_name": user.display_name,
        "password_login_available": user.has_usable_password(),
        "linked_providers": identities,
    }


def get_or_create_preferences(user: User) -> ResidentPreference:
    preference, _created = ResidentPreference.objects.get_or_create(user=user)
    return preference
