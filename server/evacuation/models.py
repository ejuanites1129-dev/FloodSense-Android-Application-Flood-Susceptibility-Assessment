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
                errors["source"] = "A verified center requires an approved source."
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
