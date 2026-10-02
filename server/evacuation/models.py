import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from geography.models import GeographicArea
from provenance.models import DataSource, PublicationStatus


class EvacuationCenter(models.Model):
    """A source-backed center record managed separately from resident output."""

    class VerificationStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        IN_REVIEW = "IN_REVIEW", "In review"
        VERIFIED = "VERIFIED", "Verified"
        INACTIVE = "INACTIVE", "Inactive"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=180)
    address = models.TextField()
    geographic_area = models.ForeignKey(
        GeographicArea,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="evacuation_centers",
        help_text="Choose the supported barangay or geographic area when known.",
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=(MinValueValidator(-90), MaxValueValidator(90)),
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=(MinValueValidator(-180), MaxValueValidator(180)),
    )
    contact_information = models.CharField(
        max_length=240,
        blank=True,
        help_text="Add only contact details authorized for this administrative record.",
    )
    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Enter only a documented and currently verified capacity.",
    )
    source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="evacuation_centers",
    )
    publication_status = models.CharField(
        max_length=30,
        choices=PublicationStatus.choices,
        default=PublicationStatus.PENDING_VALIDATION,
    )
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.DRAFT,
    )
    verified_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    limitations = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")
        permissions = (
            ("verify_evacuationcenter", "Can verify evacuation center"),
            ("deactivate_evacuationcenter", "Can deactivate evacuation center"),
        )

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}
        if self.verification_status == self.VerificationStatus.VERIFIED:
            if not self.verified_on:
                errors["verified_on"] = "A verified center requires a verification date."
            if self.source_id and self.source.status != PublicationStatus.APPROVED:
                errors["source"] = (
                    f"A verified center requires an approved source. '{self.source.name}' is "
                    f"{self.source.get_status_display()}. Keep a draft, review the source "
                    "metadata inline, or submit source and center together."
                )
            if self.source_id and not self.source.organization.strip():
                errors["source"] = (
                    "A verified center requires a source with a responsible organization."
                )
        if (
            self.capacity is not None
            and self.verification_status != self.VerificationStatus.VERIFIED
        ):
            errors["capacity"] = "Capacity may be recorded only after verification."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return self.name


class CenterImportBatch(models.Model):
    """Staff-only reviewed staging, never a second resident center datastore."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    source = models.ForeignKey(DataSource, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    filename = models.CharField(max_length=180)  # basename only; uploaded bytes are not retained
    source_revision = models.DateTimeField()
    rows = models.JSONField(default=list)
    shared_limitations = models.TextField(blank=True)
    row_count = models.PositiveIntegerField()
    valid_count = models.PositiveIntegerField()
    invalid_count = models.PositiveIntegerField()
    imported_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    imported_at = models.DateTimeField(null=True, blank=True)
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="imported_center_batches",
    )

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(row_count=models.F("valid_count") + models.F("invalid_count")),
                name="center_batch_counts_match",
            )
        ]

    def __str__(self):
        return f"Center batch {self.public_id} ({self.row_count} rows)"
