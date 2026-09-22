from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from .managers import UserManager

resident_username_validator = RegexValidator(
    regex=r"^[A-Za-z][A-Za-z0-9_.-]{2,29}$",
    message=(
        "Use 3-30 characters, beginning with a letter, and only letters, "
        "numbers, periods, underscores, or hyphens."
    ),
)


class User(AbstractUser):
    """FloodSense user with email as the Django login identifier."""

    username = None
    email = models.EmailField(unique=True, verbose_name="Email address")
    resident_username = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        validators=(resident_username_validator,),
        help_text=(
            "Normalized resident handle. Existing staff accounts may leave this blank."
        ),
    )
    display_name = models.CharField(max_length=150)
    home_barangay = models.CharField(max_length=150, blank=True)
    disclaimer_version_accepted = models.CharField(max_length=50, blank=True)
    disclaimer_accepted_at = models.DateTimeField(null=True, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta(AbstractUser.Meta):
        constraints = (
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_user_email_ci_unique",
            ),
            models.UniqueConstraint(
                Lower("resident_username"),
                condition=Q(resident_username__isnull=False),
                name="accounts_user_resident_username_ci_unique",
            ),
        )

    def clean(self) -> None:
        super().clean()
        self.email = User.objects.normalize_email(self.email).strip().lower()
        if self.resident_username:
            self.resident_username = self.resident_username.strip().lower()

    def save(self, *args, **kwargs):
        self.email = User.objects.normalize_email(self.email).strip().lower()
        if self.resident_username:
            self.resident_username = self.resident_username.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.email


class ExternalIdentity(models.Model):
    class Provider(models.TextChoices):
        GOOGLE = "GOOGLE", "Google"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="external_identities",
    )
    provider = models.CharField(max_length=20, choices=Provider.choices)
    provider_subject = models.CharField(max_length=255)
    last_verified_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("provider", "provider_subject"),
                name="unique_external_provider_subject",
            ),
            models.UniqueConstraint(
                fields=("user", "provider"),
                name="one_external_identity_per_provider_per_user",
            ),
        )

    def __str__(self) -> str:
        return f"{self.get_provider_display()} identity for {self.user}"


class EmailVerificationChallenge(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_verification_challenges",
    )
    token_digest = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Email verification challenge for user {self.user_id}"


class LegalDocumentVersion(models.Model):
    class DocumentType(models.TextChoices):
        TERMS = "TERMS", "Terms of Use"
        PRIVACY = "PRIVACY", "Privacy Policy"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        REVIEW = "REVIEW", "In review"
        PUBLISHED = "PUBLISHED", "Published"
        RETIRED = "RETIRED", "Retired"

    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    version = models.CharField(max_length=40)
    title = models.CharField(max_length=200)
    summary = models.TextField()
    effective_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    requires_acceptance = models.BooleanField(default=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_legal_documents",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_legal_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("document_type", "-effective_date", "-id")
        permissions = (
            ("review_legaldocumentversion", "Can review legal document versions"),
            ("publish_legaldocumentversion", "Can publish legal document versions"),
        )
        constraints = (
            models.UniqueConstraint(
                fields=("document_type", "version"),
                name="unique_legal_document_type_version",
            ),
            models.UniqueConstraint(
                fields=("document_type",),
                condition=Q(status="PUBLISHED"),
                name="one_published_legal_document_per_type",
            ),
        )

    def clean(self) -> None:
        super().clean()
        if self.status == self.Status.PUBLISHED:
            if not self.effective_date:
                raise ValidationError(
                    {"effective_date": "Published legal text needs an effective date."}
                )
            if not self.published_at:
                raise ValidationError(
                    {"published_at": "Published legal text needs a publication time."}
                )
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            protected = (
                "document_type",
                "version",
                "title",
                "summary",
                "effective_date",
                "requires_acceptance",
            )
            immutable = (
                original.status == self.Status.PUBLISHED
                or LegalAcceptance.objects.filter(document_version=self).exists()
            )
            if immutable and any(
                getattr(original, field) != getattr(self, field) for field in protected
            ):
                raise ValidationError(
                    "A legal version that has been accepted cannot have its text identity changed."
                )
            if original.status == self.Status.PUBLISHED and self.status not in {
                self.Status.PUBLISHED,
                self.Status.RETIRED,
            }:
                raise ValidationError("A published legal version may only be retired.")

    def __str__(self) -> str:
        return f"{self.get_document_type_display()} v{self.version}"


class LegalDocumentSection(models.Model):
    document_version = models.ForeignKey(
        LegalDocumentVersion,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    section_key = models.SlugField(max_length=80)
    title = models.CharField(max_length=200)
    short_summary = models.CharField(max_length=300)
    body = models.TextField()
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("display_order", "id")
        constraints = (
            models.UniqueConstraint(
                fields=("document_version", "section_key"),
                name="unique_legal_section_key_per_version",
            ),
            models.UniqueConstraint(
                fields=("document_version", "display_order"),
                name="unique_legal_section_order_per_version",
            ),
        )

    def clean(self) -> None:
        super().clean()
        if self.document_version_id and (
            self.document_version.status == LegalDocumentVersion.Status.PUBLISHED
            or LegalAcceptance.objects.filter(
                document_version_id=self.document_version_id
            ).exists()
        ):
            if not self.pk:
                raise ValidationError("Published or accepted legal text is append-only.")
            original = type(self).objects.get(pk=self.pk)
            protected = (
                "section_key",
                "title",
                "short_summary",
                "body",
                "display_order",
            )
            if any(getattr(original, field) != getattr(self, field) for field in protected):
                raise ValidationError("Published or accepted legal text is append-only.")

    def __str__(self) -> str:
        return f"{self.document_version}: {self.title}"


class LegalAcceptance(models.Model):
    class Source(models.TextChoices):
        ANDROID = "ANDROID", "Android application"
        WEB = "WEB", "Web application"
        MIGRATION = "MIGRATION", "Legacy migration"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="legal_acceptances",
    )
    document_version = models.ForeignKey(
        LegalDocumentVersion,
        on_delete=models.PROTECT,
        related_name="acceptances",
    )
    accepted_at = models.DateTimeField(auto_now_add=True)
    acceptance_source = models.CharField(max_length=20, choices=Source.choices)
    application_version = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ("-accepted_at",)
        constraints = (
            models.UniqueConstraint(
                fields=("user", "document_version"),
                name="unique_legal_acceptance_per_user_version",
            ),
        )

    def __str__(self) -> str:
        return f"{self.user} accepted {self.document_version}"


class OnboardingVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        RETIRED = "RETIRED", "Retired"

    version = models.CharField(max_length=40, unique=True)
    title = models.CharField(max_length=160, default="FloodSense onboarding")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-published_at", "-id")
        permissions = (
            ("publish_onboardingversion", "Can publish onboarding versions"),
        )
        constraints = (
            models.UniqueConstraint(
                fields=("status",),
                condition=Q(status="PUBLISHED"),
                name="one_published_onboarding_version",
            ),
        )

    def clean(self) -> None:
        super().clean()
        if self.status == self.Status.PUBLISHED and not self.published_at:
            raise ValidationError(
                {"published_at": "Published onboarding needs a publication time."}
            )
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            if original.status == self.Status.PUBLISHED:
                if (original.version, original.title) != (self.version, self.title):
                    raise ValidationError("Published onboarding is append-only.")
                if self.status not in {self.Status.PUBLISHED, self.Status.RETIRED}:
                    raise ValidationError("Published onboarding may only be retired.")

    def __str__(self) -> str:
        return f"{self.title} v{self.version}"


class OnboardingAcknowledgement(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="onboarding_acknowledgements",
    )
    onboarding_version = models.ForeignKey(
        OnboardingVersion,
        on_delete=models.PROTECT,
        related_name="acknowledgements",
    )
    acknowledged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("user", "onboarding_version"),
                name="unique_onboarding_acknowledgement",
            ),
        )

    def __str__(self) -> str:
        return f"{self.user} acknowledged {self.onboarding_version}"


class ResidentPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="resident_preferences",
    )
    home_barangay = models.ForeignKey(
        "geography.GeographicArea",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resident_preferences",
        limit_choices_to={"area_type": "BARANGAY"},
    )
    default_rainfall_intensity = models.ForeignKey(
        "expert.ScenarioOption",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resident_intensity_preferences",
    )
    default_rainfall_duration = models.ForeignKey(
        "expert.ScenarioOption",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resident_duration_preferences",
    )
    high_contrast = models.BooleanField(default=False)
    reduce_motion = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}
        if self.home_barangay_id and self.home_barangay.area_type != "BARANGAY":
            errors["home_barangay"] = "Choose a barangay record."
        if (
            self.default_rainfall_intensity_id
            and self.default_rainfall_intensity.category != "INTENSITY"
        ):
            errors["default_rainfall_intensity"] = "Choose a rainfall intensity."
        if (
            self.default_rainfall_duration_id
            and self.default_rainfall_duration.category != "DURATION"
        ):
            errors["default_rainfall_duration"] = "Choose a rainfall duration."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"Preferences for {self.user}"


class AccountDeletionRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Scheduled for deletion"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="deletion_requests",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("user",),
                condition=Q(status="PENDING"),
                name="one_pending_account_deletion_request",
            ),
        )

    def __str__(self) -> str:
        return f"Account deletion for {self.user} ({self.status})"
