
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class PublicationStatus(models.TextChoices):
    """Review state shared by source-backed FloodSense records."""

    DEMONSTRATION = "DEMONSTRATION", "Demonstration data—not official"
    PENDING_VALIDATION = "PENDING_VALIDATION", "Pending validation"
    APPROVED = "APPROVED", "Approved"
    RESTRICTED = "RESTRICTED", "Restricted"
    RETIRED = "RETIRED", "Retired"


class DataSource(models.Model):
    """Provenance and permitted-use information for a source of system data."""

    class SourceType(models.TextChoices):
        DEMONSTRATION = "DEMONSTRATION", "Demonstration/synthetic"
        AGENCY_DATASET = "AGENCY_DATASET", "Government/agency dataset"
        INTERVIEW = "INTERVIEW", "Interview or expert consultation"
        PUBLICATION = "PUBLICATION", "Publication or official guidance"
        OTHER = "OTHER", "Other"

    name = models.CharField(max_length=200)
    organization = models.CharField(max_length=200, blank=True)
    custodian = models.CharField(
        max_length=200,
        blank=True,
        help_text="Office or role responsible for maintaining this source.",
    )
    source_type = models.CharField(max_length=30, choices=SourceType.choices)
    coverage_description = models.TextField(blank=True)
    record_period_start = models.DateField(null=True, blank=True)
    record_period_end = models.DateField(null=True, blank=True)
    received_or_created_on = models.DateField(null=True, blank=True)
    version = models.CharField(max_length=80, blank=True)
    permitted_use = models.TextField(blank=True)
    processing_notes = models.TextField(blank=True)
    limitations = models.TextField(blank=True)
    citation_url = models.URLField(blank=True)
    status = models.CharField(
        max_length=30,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DEMONSTRATION,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_data_sources",
    )
    reviewed_on = models.DateField(null=True, blank=True)
    is_publicly_releasable = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")
        permissions = (
            ("approve_datasource", "Can approve data source metadata"),
            ("publish_datasource", "Can publish data source metadata"),
            ("restrict_datasource", "Can restrict data source metadata"),
        )

    def clean(self) -> None:
        super().clean()
        if (
            self.record_period_start
            and self.record_period_end
            and self.record_period_start > self.record_period_end
        ):
            raise ValidationError(
                {"record_period_end": "The coverage end date cannot precede its start."}
            )

    def __str__(self) -> str:
        return self.name
