from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.db.models.signals import m2m_changed, post_delete, pre_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from expert.models import SusceptibilityLevel
from provenance.models import DataSource, PublicationStatus

LINKED_GUIDANCE_FIELDS = (
    "susceptibility_level_id",
    "title",
    "instruction",
    "category",
    "display_order",
    "source_id",
    "attribution",
)


def _locked_guidance_flows(guidance_ids):
    return list(
        DSSFlowVersion.objects.select_for_update()
        .filter(outcomes__guidance_item_id__in=guidance_ids)
        .order_by("pk")
    )


def _guard_linked_guidance_change(instance):
    if not instance.pk:
        return []
    flows = _locked_guidance_flows([instance.pk])
    if any(flow.workflow_status != "DRAFT" for flow in flows):
        original = type(instance).objects.get(pk=instance.pk)
        if any(
            getattr(original, field) != getattr(instance, field) for field in LINKED_GUIDANCE_FIELDS
        ):
            raise ValidationError(
                "Guidance linked to an in-review, published or retired DSS flow is frozen. "
                "Create a new guidance record and a new draft flow version to revise its content."
            )
    return flows


class GuidanceQuerySet(models.QuerySet):
    def bulk_create(self, objs, **kwargs):
        if kwargs.get("update_conflicts"):
            raise ValidationError("Guidance conflict updates require validated instance saves.")
        return super().bulk_create(objs, **kwargs)

    @transaction.atomic
    def update(self, **kwargs):
        protected = set(LINKED_GUIDANCE_FIELDS) | {"source", "susceptibility_level"}
        flows = _locked_guidance_flows(self.values_list("pk", flat=True))
        if protected.intersection(kwargs):
            if any(flow.workflow_status != "DRAFT" for flow in flows):
                raise ValidationError("Guidance linked to reviewed DSS flow content is frozen.")
        result = super().update(**kwargs)
        _touch_dss_flows(flow.pk for flow in flows)
        return result


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

    objects = GuidanceQuerySet.as_manager()

    @transaction.atomic
    def save(self, *args, **kwargs):
        flows = _guard_linked_guidance_change(self)
        result = super().save(*args, **kwargs)
        _touch_dss_flows(flow.pk for flow in flows)
        return result

    class Meta:
        ordering = ("susceptibility_level__display_order", "display_order", "id")
        permissions = (
            ("approve_guidanceitem", "Can approve preparedness guidance"),
            ("publish_guidanceitem", "Can publish preparedness guidance"),
        )
        constraints = (
            models.CheckConstraint(
                condition=(Q(is_enabled=False) | Q(workflow_status="PUBLISHED")),
                name="guidance_enabled_only_when_published",
            ),
        )

    def clean(self) -> None:
        super().clean()
        with transaction.atomic():
            _guard_linked_guidance_change(self)
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
                    self.susceptibility_level.status != PublicationStatus.DEMONSTRATION
                    or not self.susceptibility_level.is_enabled
                    or self.susceptibility_level.source.status != PublicationStatus.DEMONSTRATION
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
                    or self.susceptibility_level.source.status != PublicationStatus.APPROVED
                    or not self.susceptibility_level.source.is_publicly_releasable
                    or self.susceptibility_level.source.source_type
                    == DataSource.SourceType.DEMONSTRATION
                ):
                    errors["susceptibility_level"] = (
                        "Published approved guidance requires an enabled approved classification."
                    )
            else:
                errors["status"] = "Only demonstration or approved content can be published."

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.susceptibility_level}: {self.title}"


FROZEN_DSS_STATES = ("PUBLISHED", "RETIRED")


class DSSQuerySet(models.QuerySet):
    """Bulk writes must obey the same append-only boundary as normal saves."""

    def _assert_editable(self):
        path = (
            "workflow_status"
            if self.model.__name__ == "DSSFlowVersion"
            else (
                "question__flow__workflow_status"
                if self.model.__name__ == "DSSOption"
                else "flow__workflow_status"
            )
        )
        if self.filter(**{f"{path}__in": FROZEN_DSS_STATES}).exists():
            raise ValidationError("Published and retired DSS versions are append-only.")
        if self.filter(**{path: "IN_REVIEW"}).exists():
            raise ValidationError("Only draft DSS content can be edited.")

    @transaction.atomic
    def delete(self):
        flow_path = (
            "pk"
            if self.model.__name__ == "DSSFlowVersion"
            else ("question__flow_id" if self.model.__name__ == "DSSOption" else "flow_id")
        )
        list(
            DSSFlowVersion.objects.select_for_update()
            .filter(pk__in=self.values_list(flow_path, flat=True))
            .order_by("pk")
        )
        self._assert_editable()
        return super().delete()

    @transaction.atomic
    def update(self, **kwargs):
        flow_path = (
            "pk"
            if self.model.__name__ == "DSSFlowVersion"
            else ("question__flow_id" if self.model.__name__ == "DSSOption" else "flow_id")
        )
        flow_ids = set(self.values_list(flow_path, flat=True))
        relationship_fields = {
            name
            for field in self.model._meta.local_fields
            if field.many_to_one
            for name in (field.name, field.attname)
        }
        for field in ("flow", "flow_id", "question", "question_id"):
            if field in kwargs:
                target = kwargs[field]
                target_id = getattr(target, "pk", target)
                flow_ids.add(
                    target_id
                    if field.startswith("flow")
                    else DSSQuestion.objects.get(pk=target_id).flow_id
                )
        list(DSSFlowVersion.objects.select_for_update().filter(pk__in=flow_ids).order_by("pk"))
        self._assert_editable()
        if self.model.__name__ == "DSSFlowVersion" and "workflow_status" in kwargs:
            raise ValidationError("Use the DSS workflow service for status transitions.")
        if relationship_fields.intersection(kwargs):
            for instance in self:
                for field, value in kwargs.items():
                    setattr(instance, field, value)
                instance.full_clean(validate_unique=False, validate_constraints=False)
        changed = super().update(**kwargs)
        if self.model.__name__ != "DSSFlowVersion":
            _touch_dss_flows(flow_ids)
        return changed

    @transaction.atomic
    def bulk_create(self, objs, **kwargs):
        if kwargs.get("update_conflicts"):
            raise ValidationError("DSS conflict updates require validated instance saves.")
        objs = list(objs)
        flow_ids = set()
        for obj in objs:
            if isinstance(obj, DSSFlowVersion):
                if obj.workflow_status != DSSFlowVersion.WorkflowStatus.DRAFT:
                    raise ValidationError("Bulk-created flows must begin as drafts.")
            elif isinstance(obj, DSSOption):
                flow_ids.add(DSSQuestion.objects.get(pk=obj.question_id).flow_id)
            else:
                flow_ids.add(obj.flow_id)
        list(DSSFlowVersion.objects.select_for_update().filter(pk__in=flow_ids).order_by("pk"))
        for obj in objs:
            obj.full_clean(validate_unique=False, validate_constraints=False)
        created = super().bulk_create(objs, **kwargs)
        _touch_dss_flows(flow_ids)
        return created


def _assert_flow_editable(flow_id):
    if (
        flow_id
        and DSSFlowVersion.objects.filter(
            pk=flow_id, workflow_status__in=FROZEN_DSS_STATES
        ).exists()
    ):
        raise ValidationError("Published and retired DSS versions are append-only.")
    if flow_id and DSSFlowVersion.objects.filter(pk=flow_id, workflow_status="IN_REVIEW").exists():
        raise ValidationError("Only draft DSS graph content and associations can be edited.")


def _touch_dss_flows(flow_ids):
    """A graph write changes the pack revision token even through technical Admin."""
    flows = DSSFlowVersion.objects.filter(pk__in=flow_ids, workflow_status="DRAFT")
    # Internal metadata update: the caller already holds the parent lock and validated the edit.
    models.QuerySet.update(flows, updated_at=timezone.now())


def _assert_child_editable(instance):
    """Check both parents so moving a frozen node into a draft is not a bypass."""
    if isinstance(instance, DSSOption):
        flow_id = DSSQuestion.objects.get(pk=instance.question_id).flow_id
    else:
        flow_id = instance.flow_id
    _assert_flow_editable(flow_id)
    if instance.pk:
        original = type(instance).objects.filter(pk=instance.pk).first()
        if original:
            original_flow = (
                original.question.flow_id if isinstance(original, DSSOption) else original.flow_id
            )
            _assert_flow_editable(original_flow)


class DSSLockedModel(models.Model):
    """Serialize ordinary graph edits with publication's parent-row lock."""

    class Meta:
        abstract = True

    @transaction.atomic
    def save(self, *args, **kwargs):
        if isinstance(self, DSSFlowVersion):
            flow_ids = {self.pk} if self.pk else set()
        elif isinstance(self, DSSOption):
            flow_ids = {DSSQuestion.objects.get(pk=self.question_id).flow_id}
            if self.pk:
                original = type(self).objects.filter(pk=self.pk).first()
                if original:
                    flow_ids.add(original.question.flow_id)
        else:
            flow_ids = {self.flow_id}
            if self.pk:
                original = type(self).objects.filter(pk=self.pk).first()
                if original:
                    flow_ids.add(original.flow_id)
        list(DSSFlowVersion.objects.select_for_update().filter(pk__in=flow_ids).order_by("pk"))
        result = super().save(*args, **kwargs)
        if not isinstance(self, DSSFlowVersion):
            _touch_dss_flows(flow_ids)
        return result

    @transaction.atomic
    def delete(self, *args, **kwargs):
        flow_id = (
            self.pk
            if isinstance(self, DSSFlowVersion)
            else (self.question.flow_id if isinstance(self, DSSOption) else self.flow_id)
        )
        list(DSSFlowVersion.objects.select_for_update().filter(pk=flow_id))
        if isinstance(self, DSSFlowVersion):
            _assert_flow_editable(flow_id)
        else:
            _assert_child_editable(self)
        return super().delete(*args, **kwargs)


class DSSFlowVersion(DSSLockedModel):
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
    reviewed_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    source_locator = models.CharField(max_length=300, blank=True)
    attribution = models.TextField(blank=True)
    limitations = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = DSSQuerySet.as_manager()

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
        if self.effective_date and self.expires_on and self.expires_on < self.effective_date:
            errors["expires_on"] = "Expiry cannot precede the effective date."
        if self.workflow_status == self.WorkflowStatus.PUBLISHED:
            if self.data_status != expected_status:
                errors["data_status"] = "Published flow status must match its operating mode."
            if not self.published_at:
                errors["published_at"] = "Published flows need a publication time."
            if not self.effective_date:
                errors["effective_date"] = "Published flows need an effective date."
            if self.source_id:
                if self.operating_mode == self.OperatingMode.DEMONSTRATION and (
                    self.source.status != PublicationStatus.DEMONSTRATION
                    or self.source.source_type != DataSource.SourceType.DEMONSTRATION
                ):
                    errors["source"] = "Demonstration flows require a demonstration source."
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
            if original.workflow_status == self.WorkflowStatus.IN_REVIEW:
                fields = (
                    "code",
                    "title",
                    "version",
                    "operating_mode",
                    "source_id",
                    "data_status",
                    "effective_date",
                    "reviewed_on",
                    "expires_on",
                    "source_locator",
                    "attribution",
                    "limitations",
                )
                changed = [
                    field for field in fields if getattr(original, field) != getattr(self, field)
                ]
                if self.workflow_status == self.WorkflowStatus.PUBLISHED:
                    changed = [field for field in changed if field != "reviewed_on"]
                if changed:
                    raise ValidationError(
                        "Return the reviewed flow to draft before editing metadata."
                    )
            if original.workflow_status in FROZEN_DSS_STATES:
                protected = (
                    "code",
                    "title",
                    "version",
                    "operating_mode",
                    "source_id",
                    "data_status",
                    "effective_date",
                    "reviewed_on",
                    "expires_on",
                    "source_locator",
                    "attribution",
                    "limitations",
                    "published_at",
                )
                if any(getattr(original, field) != getattr(self, field) for field in protected):
                    raise ValidationError("Published DSS flow versions are append-only.")
                allowed = {original.workflow_status}
                if original.workflow_status == self.WorkflowStatus.PUBLISHED:
                    allowed.add(self.WorkflowStatus.RETIRED)
                if self.workflow_status not in allowed:
                    raise ValidationError("A published DSS flow may only be retired.")

    def __str__(self) -> str:
        return f"{self.title} v{self.version} ({self.get_operating_mode_display()})"


class DSSQuestion(DSSLockedModel):
    objects = DSSQuerySet.as_manager()

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
        if self.flow_id:
            _assert_child_editable(self)
            if self.pk and (
                self.incoming_options.exclude(question__flow_id=self.flow_id).exists()
                or self.options.exclude(
                    Q(next_question__flow_id=self.flow_id) | Q(outcome__flow_id=self.flow_id)
                ).exists()
            ):
                raise ValidationError({"flow": "Moving this question would cross flow versions."})


class DSSOutcome(DSSLockedModel):
    objects = DSSQuerySet.as_manager()
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
        on_delete=models.PROTECT,
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
            raise ValidationError({"guidance_item": "Related guidance must use the same source."})
        if self.flow_id:
            _assert_child_editable(self)
            if self.pk and (
                self.incoming_options.exclude(question__flow_id=self.flow_id).exists()
                or self.content_blocks.exclude(flow_id=self.flow_id).exists()
            ):
                raise ValidationError({"flow": "Moving this outcome would cross flow versions."})

    def __str__(self) -> str:
        return f"{self.flow}: {self.title}"


class DSSOption(DSSLockedModel):
    objects = DSSQuerySet.as_manager()
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
            errors["next_question"] = "Choose exactly one next question or structured outcome."
        if (
            self.next_question_id
            and self.question_id
            and self.next_question.flow_id != self.question.flow_id
        ):
            errors["next_question"] = "Branches cannot cross flow versions."
        if self.outcome_id and self.question_id and self.outcome.flow_id != self.question.flow_id:
            errors["outcome"] = "Outcomes cannot cross flow versions."
        if errors:
            raise ValidationError(errors)
        if self.question_id:
            _assert_child_editable(self)

    def __str__(self) -> str:
        return f"{self.question.code}: {self.label}"


class DSSContentBlock(DSSLockedModel):
    """One ordered, sourced educational block in the canonical Prepare pack."""

    class Phase(models.TextChoices):
        BEFORE = "BEFORE", "Before a flood"
        DURING = "DURING", "During a flood — educational reference"
        AFTER = "AFTER", "After a flood — educational reference"
        ALWAYS = "ALWAYS", "General preparedness"

    class ContentType(models.TextChoices):
        HOUSEHOLD_ACTION = "HOUSEHOLD_ACTION", "Household action"
        SCENARIO_EXPLANATION = "SCENARIO_EXPLANATION", "Scenario explanation"
        OFFICIAL_CHANNEL = "OFFICIAL_CHANNEL", "Official information channel"
        MONITORING_REFERENCE = "MONITORING_REFERENCE", "Monitoring reference"
        AUTHORITY_ACTIVITY = "AUTHORITY_ACTIVITY", "Authority activity"
        RISK_REFERENCE = "RISK_REFERENCE", "Risk-knowledge reference"

    class Audience(models.TextChoices):
        RESIDENT = "RESIDENT", "Resident"
        HOUSEHOLD_SUPPORT = "HOUSEHOLD_SUPPORT", "Household support"
        PUBLIC_REFERENCE = "PUBLIC_REFERENCE", "Public educational reference"
        STAFF_ONLY = "STAFF_ONLY", "Staff only — not public guidance"

    class ReferenceStage(models.TextChoices):
        GREEN = "GREEN", "Green board reference — no susceptibility mapping"
        YELLOW = "YELLOW", "Yellow board reference — no susceptibility mapping"
        ORANGE = "ORANGE", "Orange board reference — no susceptibility mapping"
        RED = "RED", "Red board reference — no susceptibility mapping"

    flow = models.ForeignKey(
        DSSFlowVersion, on_delete=models.CASCADE, related_name="content_blocks"
    )
    outcome = models.ForeignKey(
        DSSOutcome, null=True, blank=True, on_delete=models.CASCADE, related_name="content_blocks"
    )
    phase = models.CharField(max_length=10, choices=Phase.choices, default=Phase.BEFORE)
    content_type = models.CharField(max_length=30, choices=ContentType.choices)
    audience = models.CharField(max_length=30, choices=Audience.choices, default=Audience.RESIDENT)
    reference_stage = models.CharField(max_length=10, choices=ReferenceStage.choices, blank=True)
    title = models.CharField(max_length=180)
    body = models.TextField()
    display_order = models.PositiveSmallIntegerField(default=0)
    source = models.ForeignKey(DataSource, on_delete=models.PROTECT, related_name="dss_blocks")
    data_status = models.CharField(
        max_length=30,
        choices=PublicationStatus.choices,
        default=PublicationStatus.PENDING_VALIDATION,
    )
    source_locator = models.CharField(max_length=300, blank=True)
    attribution = models.TextField(blank=True)
    limitations = models.TextField(blank=True)
    effective_date = models.DateField(null=True, blank=True)
    reviewed_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    public_url = models.URLField(blank=True)
    url_verified_on = models.DateField(null=True, blank=True)

    objects = DSSQuerySet.as_manager()

    class Meta:
        ordering = ("display_order", "id")
        constraints = (
            models.CheckConstraint(
                condition=Q(reference_stage="") | Q(audience="STAFF_ONLY"),
                name="dss_board_stage_staff_only",
            ),
        )

    def clean(self):
        super().clean()
        errors = {}
        if self.outcome_id and self.flow_id and self.outcome.flow_id != self.flow_id:
            errors["outcome"] = "Content and outcome must belong to the same flow version."
        if self.reference_stage and self.audience != self.Audience.STAFF_ONLY:
            errors["reference_stage"] = "Board stages remain staff-only pending a reviewed mapping."
        if self.effective_date and self.expires_on and self.expires_on < self.effective_date:
            errors["expires_on"] = "Expiry cannot precede the effective date."
        if self.public_url:
            if self.content_type != self.ContentType.OFFICIAL_CHANNEL:
                errors["public_url"] = "Only an official-channel block can carry a public link."
            elif not self.public_url.lower().startswith("https://"):
                errors["public_url"] = "Public channel links must use HTTPS."
            elif not self.url_verified_on:
                errors["url_verified_on"] = "Record the verification date before adding a link."
            elif not self.source_id or not self.source.reviewed_on:
                errors["source"] = "Public channel links require a reviewed source."
        if self.url_verified_on and not self.public_url:
            errors["url_verified_on"] = "A link verification date requires a channel URL."
        if errors:
            raise ValidationError(errors)
        if self.flow_id:
            _assert_child_editable(self)

    def __str__(self):
        return f"{self.flow}: {self.title}"


@receiver(pre_save, sender=DSSFlowVersion)
def guard_dss_flow_save(sender, instance, raw=False, **kwargs):
    if not raw:
        instance.clean()
        if instance.pk and instance.workflow_status == DSSFlowVersion.WorkflowStatus.PUBLISHED:
            previous = DSSFlowVersion.objects.get(pk=instance.pk)
            if previous.workflow_status != DSSFlowVersion.WorkflowStatus.PUBLISHED:
                from .services import validate_dss_flow

                validate_dss_flow(instance)


@receiver(pre_save, sender=DSSQuestion)
@receiver(pre_save, sender=DSSOutcome)
@receiver(pre_save, sender=DSSOption)
@receiver(pre_save, sender=DSSContentBlock)
def guard_dss_child_save(sender, instance, raw=False, **kwargs):
    if not raw:
        instance.clean()


@receiver(pre_delete, sender=DSSFlowVersion)
@receiver(pre_delete, sender=DSSQuestion)
@receiver(pre_delete, sender=DSSOutcome)
@receiver(pre_delete, sender=DSSOption)
@receiver(pre_delete, sender=DSSContentBlock)
def guard_dss_delete(sender, instance, **kwargs):
    flow_id = (
        instance.pk
        if isinstance(instance, DSSFlowVersion)
        else (instance.question.flow_id if isinstance(instance, DSSOption) else instance.flow_id)
    )
    list(DSSFlowVersion.objects.select_for_update().filter(pk=flow_id))
    if isinstance(instance, DSSFlowVersion):
        _assert_flow_editable(instance.pk)
    else:
        _assert_child_editable(instance)


@receiver(m2m_changed, sender=DSSFlowVersion.susceptibility_levels.through)
def guard_dss_levels(sender, instance, action, reverse, pk_set, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        flow_ids = getattr(instance, "_dss_changed_flow_ids", [])
        _touch_dss_flows(flow_ids)
        return
    if action not in {"pre_add", "pre_remove", "pre_clear"}:
        return
    if reverse:
        flows = (
            DSSFlowVersion.objects.filter(pk__in=pk_set)
            if pk_set is not None
            else (instance.dss_flows.all())
        )
        list(flows.select_for_update().order_by("pk"))
        instance._dss_changed_flow_ids = list(flows.values_list("pk", flat=True))
        if flows.filter(workflow_status__in=FROZEN_DSS_STATES).exists():
            raise ValidationError("Published and retired DSS associations are append-only.")
        if flows.filter(workflow_status="IN_REVIEW").exists():
            raise ValidationError("Only draft DSS associations can be edited.")
    else:
        list(DSSFlowVersion.objects.select_for_update().filter(pk=instance.pk))
        _assert_flow_editable(instance.pk)
        instance._dss_changed_flow_ids = [instance.pk]


@receiver(post_delete, sender=DSSQuestion)
@receiver(post_delete, sender=DSSOutcome)
@receiver(post_delete, sender=DSSOption)
@receiver(post_delete, sender=DSSContentBlock)
def touch_deleted_dss_child(sender, instance, **kwargs):
    flow_id = instance.question.flow_id if isinstance(instance, DSSOption) else instance.flow_id
    _touch_dss_flows([flow_id])


def _lock_dss_associations(flow_ids):
    flow_ids = set(flow_ids)
    list(DSSFlowVersion.objects.select_for_update().filter(pk__in=flow_ids).order_by("pk"))
    for flow_id in flow_ids:
        _assert_flow_editable(flow_id)
    return flow_ids


class DSSAssociationQuerySet(models.QuerySet):
    """Guard direct writes to Django's existing implicit association table."""

    @transaction.atomic
    def bulk_create(self, objs, **kwargs):
        if kwargs.get("update_conflicts"):
            raise ValidationError("DSS association conflict updates require validated saves.")
        objs = list(objs)
        flow_ids = _lock_dss_associations(obj.dssflowversion_id for obj in objs)
        for obj in objs:
            obj.full_clean(validate_unique=False, validate_constraints=False)
        result = super().bulk_create(objs, **kwargs)
        _touch_dss_flows(flow_ids)
        return result

    @transaction.atomic
    def update(self, **kwargs):
        flow_ids = set(self.values_list("dssflowversion_id", flat=True))
        for field in ("dssflowversion", "dssflowversion_id"):
            if field in kwargs:
                target = kwargs[field]
                flow_ids.add(getattr(target, "pk", target))
        flow_ids = _lock_dss_associations(flow_ids)
        for obj in self:
            for field, value in kwargs.items():
                setattr(obj, field, value)
            obj.full_clean(validate_unique=False, validate_constraints=False)
        result = super().update(**kwargs)
        _touch_dss_flows(flow_ids)
        return result

    @transaction.atomic
    def bulk_update(self, objs, fields, **kwargs):
        # Association fields are few; validated instance saves avoid expression-based bypasses.
        objs = list(objs)
        if any(obj.pk is None for obj in objs):
            raise ValueError("All bulk_update() objects must have a primary key set.")
        stored = self.filter(pk__in=[obj.pk for obj in objs])
        flow_ids = set(stored.values_list("dssflowversion_id", flat=True))
        flow_ids.update(obj.dssflowversion_id for obj in objs)
        _lock_dss_associations(flow_ids)
        for obj in objs:
            obj.full_clean(validate_unique=False, validate_constraints=False)
        existing_ids = set(stored.values_list("pk", flat=True))
        for obj in objs:
            if obj.pk in existing_ids:
                obj.save(update_fields=fields)
        return len(existing_ids)

    @transaction.atomic
    def delete(self):
        flow_ids = _lock_dss_associations(self.values_list("dssflowversion_id", flat=True))
        result = super().delete()
        _touch_dss_flows(flow_ids)
        return result


@transaction.atomic
def _save_dss_association(instance, *args, **kwargs):
    through = type(instance)
    flow_ids = {instance.dssflowversion_id}
    if instance.pk:
        original = through.objects.filter(pk=instance.pk).first()
        if original:
            flow_ids.add(original.dssflowversion_id)
    flow_ids = _lock_dss_associations(flow_ids)
    instance.full_clean()
    result = models.Model.save(instance, *args, **kwargs)
    _touch_dss_flows(flow_ids)
    return result


@transaction.atomic
def _delete_dss_association(instance, *args, **kwargs):
    original = type(instance).objects.filter(pk=instance.pk).first()
    flow_ids = _lock_dss_associations(
        [instance.dssflowversion_id, original.dssflowversion_id]
        if original
        else [instance.dssflowversion_id]
    )
    result = models.Model.delete(instance, *args, **kwargs)
    _touch_dss_flows(flow_ids)
    return result


def _install_dss_association_guard():
    """Implicit through models skip save/delete signals, including normal create().

    Replace only this table's runtime managers and instance writes. Its columns,
    table name, migration state and existing rows remain unchanged. Raw SQL stays
    outside the ORM boundary, as for the other application publication guards.
    """
    through = DSSFlowVersion.susceptibility_levels.through
    through._meta.local_managers.clear()
    through.add_to_class("objects", DSSAssociationQuerySet.as_manager())
    through._meta.default_manager_name = "objects"
    through._meta.base_manager_name = "objects"
    through._meta._expire_cache()
    through.save = _save_dss_association
    through.delete = _delete_dss_association


_install_dss_association_guard()


@receiver(pre_delete, sender=SusceptibilityLevel)
def guard_dss_level_cascade(sender, instance, **kwargs):
    # Django's cascade collector can delete an implicit through table without its manager.
    flow_ids = _lock_dss_associations(instance.dss_flows.values_list("pk", flat=True))
    instance._dss_changed_flow_ids = flow_ids


@receiver(post_delete, sender=SusceptibilityLevel)
def touch_dss_level_cascade(sender, instance, **kwargs):
    _touch_dss_flows(getattr(instance, "_dss_changed_flow_ids", []))
