from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import (
    AccountDeletionRequest,
    ExternalIdentity,
    LegalAcceptance,
    LegalDocumentVersion,
    OnboardingAcknowledgement,
    OnboardingVersion,
    User,
    resident_username_validator,
)
from .serializers import (
    AccountPatchSerializer,
    ChangePasswordSerializer,
    EmailSerializer,
    EmailTokenSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PreferenceSerializer,
    RegistrationSerializer,
    TokenSerializer,
    serialize_preferences,
)
from .services import (
    consume_email_verification,
    get_or_create_preferences,
    issue_email_verification,
    issue_password_reset,
    normalize_email,
    serialize_user,
    setup_status_for,
    token_pair_for_user,
)
from .throttles import (
    GoogleAuthThrottle,
    GoogleLinkThrottle,
    LoginThrottle,
    PasswordResetThrottle,
    RegistrationThrottle,
    TokenRefreshThrottle,
    VerificationThrottle,
)

GENERIC_LOGIN_ERROR = "We couldn't sign you in with those credentials."
GENERIC_RESET_RESPONSE = (
    "If that email address belongs to an eligible account, reset instructions "
    "have been sent."
)


def _cancel_scheduled_deletion(user: User) -> bool:
    """Treat a successful sign-in as cancellation during the grace period."""
    return bool(
        AccountDeletionRequest.objects.filter(
            user=user,
            status=AccountDeletionRequest.Status.PENDING,
        ).update(
            status=AccountDeletionRequest.Status.CANCELLED,
            resolved_at=timezone.now(),
        )
    )


class ResidentTokenRefreshView(TokenRefreshView):
    permission_classes = (AllowAny,)
    throttle_classes = (TokenRefreshThrottle,)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([RegistrationThrottle])
def register(request):
    serializer = RegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                email=data["email"],
                password=data["password"],
                resident_username=data["username"],
                display_name=data["username"],
            )
            issue_email_verification(user)
    except IntegrityError:
        raise serializers.ValidationError(
            {"detail": "The username or email address is unavailable."}
        ) from None
    return Response(
        {
            "detail": "Account created. Check your email to verify the account.",
            "email_verification_required": True,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    identifier = serializer.validated_data["identifier"].strip()
    user = User.objects.filter(
        Q(email__iexact=identifier) | Q(resident_username__iexact=identifier)
    ).first()
    authenticated = None
    if user is not None:
        authenticated = authenticate(
            request=request,
            email=user.email,
            password=serializer.validated_data["password"],
        )
    if authenticated is None or not authenticated.is_active:
        return Response(
            {"detail": GENERIC_LOGIN_ERROR}, status=status.HTTP_401_UNAUTHORIZED
        )
    if authenticated.email_verified_at is None:
        return Response(
            {
                "detail": "Email verification is required before sign in.",
                "email_verification_required": True,
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    deletion_cancelled = _cancel_scheduled_deletion(authenticated)
    return Response(
        {
            **token_pair_for_user(authenticated),
            "remember_me": serializer.validated_data["remember_me"],
            "user": serialize_user(authenticated),
            "setup": setup_status_for(authenticated),
            "scheduled_deletion_cancelled": deletion_cancelled,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    serializer = TokenSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        RefreshToken(serializer.validated_data["refresh"]).blacklist()
    except TokenError:
        return Response(
            {"detail": "The session is already invalid or expired."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([VerificationThrottle])
def verify_email(request):
    serializer = EmailTokenSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = consume_email_verification(serializer.validated_data["token"])
    if user is None:
        return Response(
            {"detail": "This verification link is invalid or expired."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response({"detail": "Email address verified. You may now sign in."})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([VerificationThrottle])
def resend_verification(request):
    serializer = EmailSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = User.objects.filter(
        email__iexact=normalize_email(serializer.validated_data["email"]),
        is_active=True,
        email_verified_at__isnull=True,
    ).first()
    if user:
        issue_email_verification(user)
    return Response(
        {
            "detail": (
                "If that email address belongs to an unverified account, a new "
                "verification message has been sent."
            )
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetThrottle])
def password_reset_request(request):
    serializer = EmailSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = User.objects.filter(
        email__iexact=normalize_email(serializer.validated_data["email"]),
        is_active=True,
    ).first()
    if user and user.has_usable_password():
        issue_password_reset(user)
    return Response({"detail": GENERIC_RESET_RESPONSE})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetThrottle])
def password_reset_confirm(request):
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        user_id = force_str(urlsafe_base64_decode(data["uid"]))
        user = User.objects.get(pk=user_id, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user is None or not default_token_generator.check_token(user, data["token"]):
        return Response(
            {"detail": "This password reset link is invalid or expired."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        password_validation.validate_password(data["new_password"], user)
    except DjangoValidationError as error:
        raise serializers.ValidationError(
            {"new_password": error.messages}
        ) from error
    user.set_password(data["new_password"])
    user.save(update_fields=("password",))
    return Response({"detail": "Password changed. You may now sign in."})


def _verified_google_claims(raw_token: str) -> dict[str, object]:
    audience = settings.GOOGLE_OAUTH_WEB_CLIENT_ID
    if not audience:
        raise RuntimeError("Google sign-in is not configured.")
    claims = google_id_token.verify_oauth2_token(
        raw_token,
        google_requests.Request(),
        audience=audience,
    )
    if (
        not claims.get("sub")
        or not claims.get("email")
        or not claims.get("email_verified")
    ):
        raise ValueError("Google account is missing verified identity claims.")
    return claims


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([GoogleAuthThrottle])
def google_auth(request):
    raw_token = str(request.data.get("id_token", ""))
    username = str(request.data.get("username", "")).strip()
    if not raw_token:
        raise serializers.ValidationError({"id_token": "This field is required."})
    try:
        claims = _verified_google_claims(raw_token)
    except RuntimeError as error:
        return Response(
            {"detail": str(error), "code": "google_not_configured"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except (ValueError, TypeError):
        return Response(
            {"detail": "Google authentication could not be verified."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    subject = str(claims["sub"])
    email = normalize_email(str(claims.get("email", "")))
    identity = ExternalIdentity.objects.select_related("user").filter(
        provider=ExternalIdentity.Provider.GOOGLE,
        provider_subject=subject,
    ).first()
    if identity:
        if not identity.user.is_active:
            return Response(
                {"detail": "Google authentication could not be verified."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        identity.last_verified_email = email
        identity.save(update_fields=("last_verified_email",))
        deletion_cancelled = _cancel_scheduled_deletion(identity.user)
        return Response(
            {
                **token_pair_for_user(identity.user),
                "user": serialize_user(identity.user),
                "setup": setup_status_for(identity.user),
                "scheduled_deletion_cancelled": deletion_cancelled,
            }
        )
    if User.objects.filter(email__iexact=email).exists():
        return Response(
            {
                "detail": (
                    "An account already uses this email address. Sign in with its "
                    "password and link Google from Account."
                ),
                "code": "secure_link_required",
            },
            status=status.HTTP_409_CONFLICT,
        )
    if not username:
        return Response(
            {
                "detail": "Choose a resident username to finish setup.",
                "code": "username_required",
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    normalized_username = username.strip().lower()
    try:
        resident_username_validator(normalized_username)
    except DjangoValidationError as error:
        raise serializers.ValidationError({"username": error.messages}) from error
    if User.objects.filter(resident_username__iexact=normalized_username).exists():
        raise serializers.ValidationError(
            {"username": "This username is unavailable."}
        )
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                password=None,
                resident_username=normalized_username,
                display_name=normalized_username,
                email_verified_at=timezone.now(),
            )
            ExternalIdentity.objects.create(
                user=user,
                provider=ExternalIdentity.Provider.GOOGLE,
                provider_subject=subject,
                last_verified_email=email,
            )
    except IntegrityError:
        raise serializers.ValidationError(
            {"detail": "The username or email address is unavailable."}
        ) from None
    return Response(
        {
            **token_pair_for_user(user),
            "user": serialize_user(user),
            "setup": setup_status_for(user),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def setup_status(request):
    return Response(setup_status_for(request.user))


def _serialize_legal(document: LegalDocumentVersion) -> dict[str, object]:
    return {
        "id": document.pk,
        "document_type": document.document_type,
        "version": document.version,
        "title": document.title,
        "summary": document.summary,
        "effective_date": document.effective_date,
        "status": document.status,
        "requires_acceptance": (
            document.requires_acceptance
            and document.status == LegalDocumentVersion.Status.PUBLISHED
        ),
        "prototype_draft": document.status != LegalDocumentVersion.Status.PUBLISHED,
        "review_notice": (
            "Prototype draft requiring adviser, institutional, and qualified "
            "privacy/legal review before deployment. This is not legal advice."
        ),
        "sections": [
            {
                "key": section.section_key,
                "title": section.title,
                "summary": section.short_summary,
                "body": section.body,
                "display_order": section.display_order,
            }
            for section in document.sections.all()
        ],
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def legal_document(request, document_type):
    document_type = document_type.upper()
    if document_type not in LegalDocumentVersion.DocumentType.values:
        raise serializers.ValidationError({"document_type": "Unknown legal document."})
    query = LegalDocumentVersion.objects.filter(
        document_type=document_type
    ).prefetch_related("sections")
    document = query.filter(status=LegalDocumentVersion.Status.PUBLISHED).first()
    if document is None:
        document = query.filter(status=LegalDocumentVersion.Status.DRAFT).first()
    if document is None:
        return Response(
            {"detail": "This legal document is not configured."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response(_serialize_legal(document))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def required_legal_documents(request):
    documents = LegalDocumentVersion.objects.filter(
        status=LegalDocumentVersion.Status.PUBLISHED,
        requires_acceptance=True,
    ).prefetch_related("sections")
    accepted_ids = set(
        LegalAcceptance.objects.filter(user=request.user).values_list(
            "document_version_id", flat=True
        )
    )
    return Response(
        {
            "documents": [
                _serialize_legal(document)
                for document in documents
                if document.pk not in accepted_ids
            ]
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def accept_legal_documents(request):
    ids = request.data.get("document_version_ids")
    if not isinstance(ids, list) or not ids:
        raise serializers.ValidationError(
            {"document_version_ids": "Select the required document versions."}
        )
    required = list(
        LegalDocumentVersion.objects.filter(
            status=LegalDocumentVersion.Status.PUBLISHED,
            requires_acceptance=True,
        )
    )
    if set(ids) != {document.pk for document in required}:
        raise serializers.ValidationError(
            {"document_version_ids": "Accept every currently required version."}
        )
    with transaction.atomic():
        for document in required:
            LegalAcceptance.objects.get_or_create(
                user=request.user,
                document_version=document,
                defaults={
                    "acceptance_source": LegalAcceptance.Source.ANDROID,
                    "application_version": str(
                        request.data.get("application_version", "")
                    )[:40],
                },
            )
    return Response(setup_status_for(request.user))


ONBOARDING_STEPS = (
    (
        "What FloodSense does",
        "FloodSense offers scenario-based flood susceptibility decision support.",
    ),
    (
        "Hypothetical rainfall scenario",
        "Choose rainfall intensity and duration. These choices do not represent "
        "live weather.",
    ),
    (
        "Location",
        "GPS is foreground and user initiated. The map pin is temporary, and "
        "manual selection remains available.",
    ),
    (
        "Map and susceptibility",
        "Low, Moderate, High, Very High, and insufficient-data results depend on "
        "source-backed information with limitations.",
    ),
    (
        "Decision support",
        "Preparedness guidance supports awareness and never changes the Expert "
        "System classification.",
    ),
    (
        "Evacuation centers",
        "Nearest uses available geographic data; it does not prove road safety, "
        "access, capacity, or operating status.",
    ),
    (
        "Official information and emergencies",
        "Follow PAGASA, MGB, Bacoor CDRRMO/LGU, barangay officials, and emergency "
        "services. FloodSense is not an emergency-response substitute.",
    ),
)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def current_onboarding(request):
    version = OnboardingVersion.objects.filter(
        status=OnboardingVersion.Status.PUBLISHED
    ).first()
    if version is None:
        version = OnboardingVersion.objects.filter(
            status=OnboardingVersion.Status.DRAFT
        ).first()
    if version is None:
        return Response(
            {"detail": "Onboarding is not configured."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response(
        {
            "id": version.pk,
            "version": version.version,
            "title": version.title,
            "status": version.status,
            "prototype_draft": version.status != OnboardingVersion.Status.PUBLISHED,
            "steps": [
                {"number": index, "title": title, "body": body}
                for index, (title, body) in enumerate(ONBOARDING_STEPS, start=1)
            ],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def acknowledge_onboarding(request):
    version = OnboardingVersion.objects.filter(
        status=OnboardingVersion.Status.PUBLISHED
    ).first()
    if version is None:
        return Response(
            {"detail": "No approved onboarding version is available."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if request.data.get("version") != version.version:
        raise serializers.ValidationError(
            {"version": "Acknowledge the current onboarding version."}
        )
    OnboardingAcknowledgement.objects.get_or_create(
        user=request.user, onboarding_version=version
    )
    return Response(setup_status_for(request.user))


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def account_me(request):
    if request.method == "PATCH":
        serializer = AccountPatchSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        request.user.resident_username = serializer.validated_data["username"]
        request.user.display_name = serializer.validated_data["username"]
        try:
            request.user.save(update_fields=("resident_username", "display_name"))
        except IntegrityError:
            raise serializers.ValidationError(
                {"username": "This username is unavailable."}
            ) from None
    return Response(serialize_user(request.user))


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def account_preferences(request):
    preference = get_or_create_preferences(request.user)
    if request.method == "PATCH":
        serializer = PreferenceSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        mapping = {
            "home_barangay_id": "home_barangay",
            "default_rainfall_intensity_id": "default_rainfall_intensity",
            "default_rainfall_duration_id": "default_rainfall_duration",
            "high_contrast": "high_contrast",
            "reduce_motion": "reduce_motion",
        }
        for source, target in mapping.items():
            if source in serializer.validated_data:
                setattr(preference, target, serializer.validated_data[source])
        preference.full_clean()
        preference.save()
    return Response(serialize_preferences(preference))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    if not request.user.has_usable_password():
        return Response(
            {"detail": "This account does not currently use a password."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    serializer = ChangePasswordSerializer(
        data=request.data, context={"request": request}
    )
    serializer.is_valid(raise_exception=True)
    request.user.set_password(serializer.validated_data["new_password"])
    request.user.save(update_fields=("password",))
    return Response({"detail": "Password changed. Sign in again on other sessions."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def schedule_deletion(request):
    if request.user.is_staff or request.user.is_superuser:
        return Response(
            {"detail": "Staff accounts cannot be deleted from the resident app."},
            status=status.HTTP_403_FORBIDDEN,
        )
    delete_on = timezone.now() + timedelta(
        days=settings.ACCOUNT_DELETION_GRACE_DAYS
    )
    deletion_request, created = AccountDeletionRequest.objects.get_or_create(
        user=request.user,
        status=AccountDeletionRequest.Status.PENDING,
        defaults={"scheduled_for": delete_on},
    )
    if deletion_request.scheduled_for is None:
        deletion_request.scheduled_for = delete_on
        deletion_request.save(update_fields=("scheduled_for",))
    return Response(
        {
            "id": deletion_request.pk,
            "status": deletion_request.status,
            "scheduled_for": deletion_request.scheduled_for,
            "grace_days": settings.ACCOUNT_DELETION_GRACE_DAYS,
            "detail": (
                "Account deletion is scheduled. Signing in before the deletion "
                "date cancels it automatically."
            ),
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_deletion(request):
    cancelled = _cancel_scheduled_deletion(request.user)
    return Response(
        {
            "cancelled": cancelled,
            "detail": (
                "Scheduled account deletion was cancelled."
                if cancelled
                else "No scheduled account deletion was found."
            ),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([GoogleLinkThrottle])
def link_google(request):
    password = str(request.data.get("password", ""))
    if not request.user.has_usable_password() or not request.user.check_password(password):
        return Response(
            {"detail": "Secure password reauthentication failed."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    try:
        claims = _verified_google_claims(str(request.data.get("id_token", "")))
    except RuntimeError as error:
        return Response(
            {"detail": str(error), "code": "google_not_configured"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except (ValueError, TypeError):
        return Response(
            {"detail": "Google authentication could not be verified."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    try:
        ExternalIdentity.objects.create(
            user=request.user,
            provider=ExternalIdentity.Provider.GOOGLE,
            provider_subject=str(claims["sub"]),
            last_verified_email=normalize_email(str(claims.get("email", ""))),
        )
    except IntegrityError:
        return Response(
            {"detail": "That Google identity is already linked."},
            status=status.HTTP_409_CONFLICT,
        )
    return Response(serialize_user(request.user))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unlink_google(request):
    identity = ExternalIdentity.objects.filter(
        user=request.user, provider=ExternalIdentity.Provider.GOOGLE
    ).first()
    if identity is None:
        return Response(status=status.HTTP_204_NO_CONTENT)
    if not request.user.has_usable_password():
        return Response(
            {"detail": "Set a password before unlinking your only sign-in method."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not request.user.check_password(str(request.data.get("password", ""))):
        return Response(
            {"detail": "Secure password reauthentication failed."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    identity.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
