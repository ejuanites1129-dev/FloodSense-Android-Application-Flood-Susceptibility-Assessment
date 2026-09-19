
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from expert.models import SusceptibilityLevel
from provenance.models import DataSource, PublicationStatus


class GuidanceItem(models.Model):
    """Reviewed preparedness guidance returned by the DSS."""

    class WorkflowStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        IN_REVIEW = "IN_REVIEW", "In review"
        APPROVED = "APPROVED", "Approved"
        PUBLISHED = "PUBLISHED", "Published"

    class Category(models.TextChoices):
        PREPARE = "PREPARE", "Prepare"
        MONITOR = "MONITOR", "Monitor official information"
        PROTECT = "PROTECT", "Protect people and belongings"
        OFFICIAL_INSTRUCTIONS = (
            "OFFICIAL_INSTRUCTIONS",
            "Follow authorized official instructions",
        )

    susceptibility_level = models.ForeignKey(
        SusceptibilityLevel,
        on_delete=models.PROTECT,
        related_name="guidance_items",
    )
    title = models.CharField(max_length=160)
    instruction = models.TextField()
    category = models.CharField(max_length=30, choices=Category.choices)
    display_order = models.PositiveSmallIntegerField(default=0)
    source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="guidance_items",
    )
    attribution = models.TextField(
        blank=True,
        help_text="Public-facing credit or attribution required by the source.",
    )
    status = models.CharField(
        max_length=30,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DEMONSTRATION,
    )
    workflow_status = models.CharField(
        max_length=20,
        choices=WorkflowStatus.choices,
        default=WorkflowStatus.DRAFT,
    )
    is_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("susceptibility_level__display_order", "display_order", "id")
        permissions = (
            ("approve_guidanceitem", "Can approve preparedness guidance"),
            ("publish_guidanceitem", "Can publish preparedness guidance"),
        )
        constraints = (
            models.CheckConstraint(
                condition=(
                    Q(is_enabled=False)
                    | Q(workflow_status="PUBLISHED")
                ),
                name="guidance_enabled_only_when_published",
            ),
        )

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}
        if self.is_enabled and self.workflow_status != self.WorkflowStatus.PUBLISHED:
            errors["is_enabled"] = "Only published guidance can be enabled."

        if self.workflow_status == self.WorkflowStatus.PUBLISHED:
            if not self.is_enabled:
                errors["is_enabled"] = "Published guidance must be enabled."
            if self.status == PublicationStatus.DEMONSTRATION:
                if self.source_id and (
                    self.source.status != PublicationStatus.DEMONSTRATION
                    or self.source.source_type != DataSource.SourceType.DEMONSTRATION
                ):
                    errors["source"] = (
                        "Published demonstration guidance requires a demonstration source."
                    )
                if self.susceptibility_level_id and (
                    self.susceptibility_level.status
                    != PublicationStatus.DEMONSTRATION
                    or not self.susceptibility_level.is_enabled
                    or self.susceptibility_level.source.status
                    != PublicationStatus.DEMONSTRATION
                    or self.susceptibility_level.source.source_type
                    != DataSource.SourceType.DEMONSTRATION
                ):
                    errors["susceptibility_level"] = (
                        "Published demonstration guidance requires an enabled "
                        "demonstration classification."
                    )
            elif self.status == PublicationStatus.APPROVED:
                if self.source_id and (
                    self.source.status != PublicationStatus.APPROVED
                    or not self.source.is_publicly_releasable
                    or self.source.source_type == DataSource.SourceType.DEMONSTRATION
                ):
                    errors["source"] = (
                        "Published approved guidance requires an approved, publicly "
                        "releasable, non-demonstration source."
                    )
                if self.susceptibility_level_id and (
                    self.susceptibility_level.status != PublicationStatus.APPROVED
                    or not self.susceptibility_level.is_enabled
                    or self.susceptibility_level.source.status
                    != PublicationStatus.APPROVED
                    or not self.susceptibility_level.source.is_publicly_releasable
                    or self.susceptibility_level.source.source_type
                    == DataSource.SourceType.DEMONSTRATION
                ):
                    errors["susceptibility_level"] = (
                        "Published approved guidance requires an enabled approved "
                        "classification."
                    )
            else:
                errors["status"] = (
                    "Only demonstration or approved content can be published."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.susceptibility_level}: {self.title}"
