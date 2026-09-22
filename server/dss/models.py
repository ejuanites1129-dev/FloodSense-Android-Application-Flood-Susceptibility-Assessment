
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


class DSSFlowVersion(models.Model):
    class OperatingMode(models.TextChoices):
        DEMONSTRATION = "DEMONSTRATION", "Demonstration"
        OFFICIAL = "OFFICIAL", "Approved/official"

    class WorkflowStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        IN_REVIEW = "IN_REVIEW", "In review"
        PUBLISHED = "PUBLISHED", "Published"
        RETIRED = "RETIRED", "Retired"

    code = models.SlugField(max_length=80)
    title = models.CharField(max_length=160)
    version = models.CharField(max_length=40)
    operating_mode = models.CharField(max_length=20, choices=OperatingMode.choices)
    susceptibility_levels = models.ManyToManyField(
        SusceptibilityLevel,
        related_name="dss_flows",
    )
    workflow_status = models.CharField(
        max_length=20,
        choices=WorkflowStatus.choices,
        default=WorkflowStatus.DRAFT,
    )
    source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="dss_flows",
    )
    data_status = models.CharField(
        max_length=30,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DEMONSTRATION,
    )
    effective_date = models.DateField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code", "-effective_date", "-id")
        permissions = (
            ("review_dssflowversion", "Can review structured DSS flow versions"),
            ("publish_dssflowversion", "Can publish structured DSS flow versions"),
        )
        constraints = (
            models.UniqueConstraint(
                fields=("code", "version"),
                name="unique_dss_flow_code_version",
            ),
            models.UniqueConstraint(
                fields=("code", "operating_mode"),
                condition=Q(workflow_status="PUBLISHED"),
                name="one_published_dss_flow_per_code_mode",
            ),
        )

    def clean(self) -> None:
        super().clean()
        errors = {}
        expected_status = {
            self.OperatingMode.DEMONSTRATION: PublicationStatus.DEMONSTRATION,
            self.OperatingMode.OFFICIAL: PublicationStatus.APPROVED,
        }.get(self.operating_mode)
        if self.workflow_status == self.WorkflowStatus.PUBLISHED:
            if self.data_status != expected_status:
                errors["data_status"] = (
                    "Published flow status must match its operating mode."
                )
            if not self.published_at:
                errors["published_at"] = "Published flows need a publication time."
            if not self.effective_date:
                errors["effective_date"] = "Published flows need an effective date."
            if self.source_id:
                if self.operating_mode == self.OperatingMode.DEMONSTRATION and (
                    self.source.status != PublicationStatus.DEMONSTRATION
                    or self.source.source_type != DataSource.SourceType.DEMONSTRATION
                ):
                    errors["source"] = (
                        "Demonstration flows require a demonstration source."
                    )
                if self.operating_mode == self.OperatingMode.OFFICIAL and (
                    self.source.status != PublicationStatus.APPROVED
                    or not self.source.is_publicly_releasable
                    or self.source.source_type == DataSource.SourceType.DEMONSTRATION
                ):
                    errors["source"] = (
                        "Official flows require an approved, publicly releasable source."
                    )
        if errors:
            raise ValidationError(errors)
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            if original.workflow_status == self.WorkflowStatus.PUBLISHED:
                protected = (
                    "code",
                    "title",
                    "version",
                    "operating_mode",
                    "source_id",
                    "data_status",
                    "effective_date",
                )
                if any(
                    getattr(original, field) != getattr(self, field)
                    for field in protected
                ):
                    raise ValidationError("Published DSS flow versions are append-only.")
                if self.workflow_status not in {
                    self.WorkflowStatus.PUBLISHED,
                    self.WorkflowStatus.RETIRED,
                }:
                    raise ValidationError("A published DSS flow may only be retired.")

    def __str__(self) -> str:
        return f"{self.title} v{self.version} ({self.get_operating_mode_display()})"


class DSSQuestion(models.Model):
    class QuestionType(models.TextChoices):
        SINGLE_CHOICE = "SINGLE_CHOICE", "Single choice"

    flow = models.ForeignKey(
        DSSFlowVersion,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    code = models.SlugField(max_length=80)
    prompt = models.CharField(max_length=300)
    explanatory_text = models.TextField(blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    question_type = models.CharField(
        max_length=30,
        choices=QuestionType.choices,
        default=QuestionType.SINGLE_CHOICE,
    )
    is_start = models.BooleanField(default=False)

    class Meta:
        ordering = ("flow", "display_order", "id")
        constraints = (
            models.UniqueConstraint(
                fields=("flow", "code"),
                name="unique_dss_question_code_per_flow",
            ),
            models.UniqueConstraint(
                fields=("flow",),
                condition=Q(is_start=True),
                name="one_dss_start_question_per_flow",
            ),
        )

    def __str__(self) -> str:
        return f"{self.flow}: {self.prompt}"

    def clean(self) -> None:
        super().clean()
        if self.flow_id and self.flow.workflow_status == DSSFlowVersion.WorkflowStatus.PUBLISHED:
            if not self.pk:
                raise ValidationError("Published DSS flow versions are append-only.")
            original = type(self).objects.get(pk=self.pk)
            protected = (
                "flow_id",
                "code",
                "prompt",
                "explanatory_text",
                "display_order",
                "question_type",
                "is_start",
            )
            if any(
                getattr(original, field) != getattr(self, field)
                for field in protected
            ):
                raise ValidationError("Published DSS flow versions are append-only.")


class DSSOutcome(models.Model):
    flow = models.ForeignKey(
        DSSFlowVersion,
        on_delete=models.CASCADE,
        related_name="outcomes",
    )
    code = models.SlugField(max_length=80)
    title = models.CharField(max_length=180)
    instruction = models.TextField()
    category = models.CharField(max_length=40, choices=GuidanceItem.Category.choices)
    source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="dss_outcomes",
    )
    warning = models.TextField(
        default=(
            "Preparedness guidance is not an evacuation order. Follow official "
            "authorities and emergency services."
        )
    )
    guidance_item = models.ForeignKey(
        GuidanceItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="structured_outcomes",
    )

    class Meta:
        ordering = ("flow", "code")
        constraints = (
            models.UniqueConstraint(
                fields=("flow", "code"),
                name="unique_dss_outcome_code_per_flow",
            ),
        )

    def clean(self) -> None:
        super().clean()
        if self.source_id and self.flow_id and self.source_id != self.flow.source_id:
            raise ValidationError(
                {"source": "Outcome provenance must match the versioned flow source."}
            )
        if self.guidance_item_id and self.guidance_item.source_id != self.source_id:
            raise ValidationError(
                {"guidance_item": "Related guidance must use the same source."}
            )
        if self.flow_id and self.flow.workflow_status == DSSFlowVersion.WorkflowStatus.PUBLISHED:
            if not self.pk:
                raise ValidationError("Published DSS flow versions are append-only.")
            original = type(self).objects.get(pk=self.pk)
            protected = (
                "flow_id",
                "code",
                "title",
                "instruction",
                "category",
                "source_id",
                "warning",
                "guidance_item_id",
            )
            if any(
                getattr(original, field) != getattr(self, field)
                for field in protected
            ):
                raise ValidationError("Published DSS flow versions are append-only.")

    def __str__(self) -> str:
        return f"{self.flow}: {self.title}"


class DSSOption(models.Model):
    question = models.ForeignKey(
        DSSQuestion,
        on_delete=models.CASCADE,
        related_name="options",
    )
    code = models.SlugField(max_length=80)
    label = models.CharField(max_length=200)
    supporting_text = models.TextField(blank=True)
    next_question = models.ForeignKey(
        DSSQuestion,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="incoming_options",
    )
    outcome = models.ForeignKey(
        DSSOutcome,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="incoming_options",
    )
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("question", "display_order", "id")
        constraints = (
            models.UniqueConstraint(
                fields=("question", "code"),
                name="unique_dss_option_code_per_question",
            ),
            models.CheckConstraint(
                condition=(
                    (Q(next_question__isnull=False) & Q(outcome__isnull=True))
                    | (Q(next_question__isnull=True) & Q(outcome__isnull=False))
                ),
                name="dss_option_has_exactly_one_destination",
            ),
        )

    def clean(self) -> None:
        super().clean()
        errors = {}
        if (self.next_question is None) == (self.outcome is None):
            errors["next_question"] = (
                "Choose exactly one next question or structured outcome."
            )
        if (
            self.next_question_id
            and self.question_id
            and self.next_question.flow_id != self.question.flow_id
        ):
            errors["next_question"] = "Branches cannot cross flow versions."
        if (
            self.outcome_id
            and self.question_id
            and self.outcome.flow_id != self.question.flow_id
        ):
            errors["outcome"] = "Outcomes cannot cross flow versions."
        if errors:
            raise ValidationError(errors)
        if (
            self.question_id
            and self.question.flow.workflow_status
            == DSSFlowVersion.WorkflowStatus.PUBLISHED
        ):
            if not self.pk:
                raise ValidationError("Published DSS flow versions are append-only.")
            original = type(self).objects.get(pk=self.pk)
            protected = (
                "question_id",
                "code",
                "label",
                "supporting_text",
                "next_question_id",
                "outcome_id",
                "display_order",
            )
            if any(
                getattr(original, field) != getattr(self, field)
                for field in protected
            ):
                raise ValidationError("Published DSS flow versions are append-only.")

    def __str__(self) -> str:
        return f"{self.question.code}: {self.label}"
