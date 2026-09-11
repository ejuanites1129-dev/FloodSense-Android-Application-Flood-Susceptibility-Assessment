
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q
from geography.models import GeographicArea
from provenance.models import DataSource, PublicationStatus


class ScenarioOption(models.Model):
    """A controlled rainfall intensity or duration choice."""

    class Category(models.TextChoices):
        INTENSITY = "INTENSITY", "Rainfall intensity"
        DURATION = "DURATION", "Rainfall duration"

    category = models.CharField(max_length=20, choices=Category.choices)
    code = models.SlugField(max_length=80, unique=True)
    label = models.CharField(max_length=120)
    minimum_value = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
    )
    maximum_value = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
    )
    unit = models.CharField(max_length=40, blank=True)
    source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="scenario_options",
    )
    status = models.CharField(
        max_length=30,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DEMONSTRATION,
    )
    display_order = models.PositiveSmallIntegerField(default=0)
    is_enabled = models.BooleanField(default=False)

    class Meta:
        ordering = ("category", "display_order", "label")
        constraints = (
            models.CheckConstraint(
                condition=(
                    Q(minimum_value__isnull=True)
                    | Q(maximum_value__isnull=True)
                    | Q(minimum_value__lte=F("maximum_value"))
                ),
                name="scenario_minimum_not_above_maximum",
            ),
        )

    def clean(self) -> None:
        super().clean()
        if (
            self.minimum_value is not None
            and self.maximum_value is not None
            and self.minimum_value > self.maximum_value
        ):
            raise ValidationError("minimum_value cannot exceed maximum_value.")

    def __str__(self) -> str:
        return self.label


class SusceptibilityLevel(models.Model):
    """The controlled four-level FloodSense classification vocabulary."""

    class Code(models.TextChoices):
        LOW = "LOW", "Low"
        MODERATE = "MODERATE", "Moderate"
        HIGH = "HIGH", "High"
        VERY_HIGH = "VERY_HIGH", "Very High"

    code = models.CharField(max_length=20, choices=Code.choices, unique=True)
    label = models.CharField(max_length=80)
    display_order = models.PositiveSmallIntegerField(unique=True)
    map_color = models.CharField(
        max_length=7,
        validators=(
            RegexValidator(
                regex=r"^#[0-9A-Fa-f]{6}$",
                message="Use a six-digit hexadecimal color such as #F4C542.",
            ),
        ),
    )
    definition = models.TextField()
    source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="susceptibility_levels",
    )
    status = models.CharField(
        max_length=30,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DEMONSTRATION,
    )
    is_enabled = models.BooleanField(default=False)

    class Meta:
        ordering = ("display_order",)

    def __str__(self) -> str:
        return self.label


class RuleSet(models.Model):
    """A versioned collection of deterministic Expert System rules."""

    class Mode(models.TextChoices):
        DEMONSTRATION = "DEMONSTRATION", "Demonstration"
        OFFICIAL = "OFFICIAL", "Approved/official"

    name = models.CharField(max_length=160)
    version = models.CharField(max_length=40)
    mode = models.CharField(max_length=20, choices=Mode.choices)
    effective_on = models.DateField(null=True, blank=True)
    source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="rule_sets",
    )
    status = models.CharField(
        max_length=30,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DEMONSTRATION,
    )
    is_active = models.BooleanField(default=False)
    change_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "version")
        constraints = (
            models.UniqueConstraint(
                fields=("name", "version"),
                name="unique_ruleset_name_and_version",
            ),
            models.UniqueConstraint(
                fields=("mode",),
                condition=Q(is_active=True),
                name="one_active_ruleset_per_mode",
            ),
        )

    def clean(self) -> None:
        super().clean()
        expected_status = {
            self.Mode.DEMONSTRATION: PublicationStatus.DEMONSTRATION,
            self.Mode.OFFICIAL: PublicationStatus.APPROVED,
        }.get(self.mode)
        if self.is_active and self.status != expected_status:
            raise ValidationError(
                {"status": "An active ruleset must have the status required by its mode."}
            )

    def __str__(self) -> str:
        return f"{self.name} v{self.version}"


class ExpertRule(models.Model):
    """An IF–THEN rule whose conclusion is one susceptibility level."""

    code = models.SlugField(max_length=80)
    ruleset = models.ForeignKey(
        RuleSet,
        on_delete=models.CASCADE,
        related_name="rules",
    )
    geographic_scope = models.ForeignKey(
        GeographicArea,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="expert_rules",
    )
    result_level = models.ForeignKey(
        SusceptibilityLevel,
        on_delete=models.PROTECT,
        related_name="rules",
    )
    priority = models.PositiveIntegerField(default=100)
    rationale = models.TextField()
    source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="expert_rules",
    )
    status = models.CharField(
        max_length=30,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DEMONSTRATION,
    )
    is_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("ruleset", "-priority", "code")
        constraints = (
            models.UniqueConstraint(
                fields=("ruleset", "code"),
                name="unique_rule_code_per_ruleset",
            ),
        )

    def __str__(self) -> str:
        return f"{self.code} → {self.result_level}"


class ExpertRuleCondition(models.Model):
    """One controlled condition; every enabled condition must match."""

    class ConditionType(models.TextChoices):
        INTENSITY_OPTION = "INTENSITY_OPTION", "Intensity option equals"
        DURATION_OPTION = "DURATION_OPTION", "Duration option equals"
        AREA_FACT_TEXT = "AREA_FACT_TEXT", "Area text fact"
        AREA_FACT_NUMBER = "AREA_FACT_NUMBER", "Area numeric fact"

    class Operator(models.TextChoices):
        EQUALS = "EQ", "Equals"
        GREATER_THAN = "GT", "Greater than"
        GREATER_THAN_OR_EQUAL = "GTE", "Greater than or equal"
        LESS_THAN = "LT", "Less than"
        LESS_THAN_OR_EQUAL = "LTE", "Less than or equal"

    rule = models.ForeignKey(
        ExpertRule,
        on_delete=models.CASCADE,
        related_name="conditions",
    )
    condition_type = models.CharField(max_length=30, choices=ConditionType.choices)
    operator = models.CharField(
        max_length=5,
        choices=Operator.choices,
        default=Operator.EQUALS,
    )
    scenario_option = models.ForeignKey(
        ScenarioOption,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rule_conditions",
    )
    fact_key = models.SlugField(max_length=100, blank=True)
    expected_text = models.CharField(max_length=200, blank=True)
    expected_number = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
    )
    display_order = models.PositiveSmallIntegerField(default=0)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ("rule", "display_order", "id")

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}

        if self.condition_type in {
            self.ConditionType.INTENSITY_OPTION,
            self.ConditionType.DURATION_OPTION,
        }:
            expected_category = (
                ScenarioOption.Category.INTENSITY
                if self.condition_type == self.ConditionType.INTENSITY_OPTION
                else ScenarioOption.Category.DURATION
            )
            if self.scenario_option is None:
                errors["scenario_option"] = "This condition requires a scenario option."
            elif self.scenario_option.category != expected_category:
                errors["scenario_option"] = "The scenario option category does not match."
            if self.operator != self.Operator.EQUALS:
                errors["operator"] = "Scenario options support only the equals operator."
            if self.fact_key or self.expected_text or self.expected_number is not None:
                errors["fact_key"] = "Scenario conditions cannot also contain area-fact values."

        elif self.condition_type == self.ConditionType.AREA_FACT_TEXT:
            if not self.fact_key:
                errors["fact_key"] = "A text area-fact condition requires a fact key."
            if not self.expected_text:
                errors["expected_text"] = "A text area-fact condition requires text."
            if self.operator != self.Operator.EQUALS:
                errors["operator"] = "Text area facts support only the equals operator."
            if self.scenario_option is not None or self.expected_number is not None:
                errors["scenario_option"] = "Use only text fields for this condition."

        elif self.condition_type == self.ConditionType.AREA_FACT_NUMBER:
            if not self.fact_key:
                errors["fact_key"] = "A numeric area-fact condition requires a fact key."
            if self.expected_number is None:
                errors["expected_number"] = "A numeric area-fact condition requires a number."
            if self.scenario_option is not None or self.expected_text:
                errors["scenario_option"] = "Use only numeric fields for this condition."

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.rule.code}: {self.get_condition_type_display()}"
