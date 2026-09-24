from decimal import Decimal

from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q
from provenance.models import DataSource, PublicationStatus


class GeographicArea(models.Model):
    """A supported spatial area used by map display and rule evaluation."""

    class AreaType(models.TextChoices):
        DEMO_ZONE = "DEMO_ZONE", "Demonstration zone"
        CITY = "CITY", "City"
        BARANGAY = "BARANGAY", "Barangay"
        OTHER = "OTHER", "Other"

    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    area_type = models.CharField(max_length=20, choices=AreaType.choices)
    geometry = models.MultiPolygonField(srid=4326)
    source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="geographic_areas",
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
        ordering = ("name", "id")

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class AreaFact(models.Model):
    """A typed, source-backed fact about a geographic area."""

    area = models.ForeignKey(
        GeographicArea,
        on_delete=models.CASCADE,
        related_name="facts",
    )
    fact_key = models.SlugField(max_length=100)
    text_value = models.CharField(max_length=200, blank=True)
    numeric_value = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
    )
    unit = models.CharField(max_length=40, blank=True)
    source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="area_facts",
    )
    status = models.CharField(
        max_length=30,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DEMONSTRATION,
    )
    effective_on = models.DateField(null=True, blank=True)
    is_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("area__name", "fact_key", "id")
        constraints = (
            models.CheckConstraint(
                condition=(
                    (Q(text_value="") & Q(numeric_value__isnull=False))
                    | (~Q(text_value="") & Q(numeric_value__isnull=True))
                ),
                name="area_fact_has_exactly_one_value",
            ),
        )

    def clean(self) -> None:
        super().clean()
        has_text = bool(self.text_value.strip())
        has_number = self.numeric_value is not None
        if has_text == has_number:
            raise ValidationError("Provide exactly one value: text_value or numeric_value.")

    def __str__(self) -> str:
        value = self.text_value or self.numeric_value
        return f"{self.area}: {self.fact_key}={value}"


class FloodSusceptibilityDataset(models.Model):
    """One immutable, source-backed susceptibility-processing version.

    Activating a dataset only makes it available to the explicitly
    demonstration/consultation workflow. It does not approve the source or
    turn a derived barangay summary into an official City classification.
    """

    class AggregationMethod(models.TextChoices):
        DOMINANT_MAPPED_AREA = (
            "DOMINANT_MAPPED_AREA",
            "Largest mapped LF/MF/HF/VHF area share",
        )

    code = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    version = models.CharField(max_length=100)
    source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="flood_susceptibility_datasets",
    )
    source_field = models.CharField(max_length=80, default="FloodSusc")
    source_accessed_on = models.DateField()
    generated_at = models.DateTimeField()
    aggregation_method = models.CharField(
        max_length=40,
        choices=AggregationMethod.choices,
        default=AggregationMethod.DOMINANT_MAPPED_AREA,
    )
    summary_sha256 = models.CharField(max_length=64)
    validation_sha256 = models.CharField(max_length=64)
    status = models.CharField(
        max_length=30,
        choices=PublicationStatus.choices,
        default=PublicationStatus.PENDING_VALIDATION,
    )
    is_active_for_consultation = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-generated_at", "id")
        constraints = (
            models.UniqueConstraint(
                fields=("is_active_for_consultation",),
                condition=Q(is_active_for_consultation=True),
                name="one_active_consultation_susceptibility_dataset",
            ),
        )

    def clean(self) -> None:
        super().clean()
        if self.is_active_for_consultation and self.status != PublicationStatus.PENDING_VALIDATION:
            raise ValidationError(
                {
                    "status": (
                        "The consultation preview must remain pending validation; "
                        "approval uses a separately reviewed workflow."
                    )
                }
            )

    def __str__(self) -> str:
        return f"{self.name} ({self.version})"


class BarangaySusceptibilitySummary(models.Model):
    """Auditable MGB area composition and its provisional dominant class."""

    class MgbClass(models.TextChoices):
        LOW = "LF", "Low"
        MODERATE = "MF", "Moderate"
        HIGH = "HF", "High"
        VERY_HIGH = "VHF", "Very High"

    dataset = models.ForeignKey(
        FloodSusceptibilityDataset,
        on_delete=models.CASCADE,
        related_name="barangay_summaries",
    )
    area = models.ForeignKey(
        GeographicArea,
        on_delete=models.PROTECT,
        related_name="susceptibility_summaries",
    )
    barangay_area_sqm = models.DecimalField(max_digits=16, decimal_places=3)
    lf_area_sqm = models.DecimalField(max_digits=16, decimal_places=3)
    lf_percent = models.DecimalField(max_digits=7, decimal_places=4)
    mf_area_sqm = models.DecimalField(max_digits=16, decimal_places=3)
    mf_percent = models.DecimalField(max_digits=7, decimal_places=4)
    hf_area_sqm = models.DecimalField(max_digits=16, decimal_places=3)
    hf_percent = models.DecimalField(max_digits=7, decimal_places=4)
    vhf_area_sqm = models.DecimalField(max_digits=16, decimal_places=3)
    vhf_percent = models.DecimalField(max_digits=7, decimal_places=4)
    conflict_area_sqm = models.DecimalField(max_digits=16, decimal_places=3)
    conflict_percent = models.DecimalField(max_digits=7, decimal_places=4)
    unmapped_area_sqm = models.DecimalField(max_digits=16, decimal_places=3)
    unmapped_percent = models.DecimalField(max_digits=7, decimal_places=4)
    partition_percent_total = models.DecimalField(max_digits=7, decimal_places=4)
    dominant_class = models.CharField(
        max_length=4,
        choices=MgbClass.choices,
        null=True,
        blank=True,
    )
    dominant_percent = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
    )
    baseline_rank = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("area__name", "id")
        constraints = (
            models.UniqueConstraint(
                fields=("dataset", "area"),
                name="unique_barangay_summary_per_dataset",
            ),
        )

    @property
    def mapped_percent(self):
        return self.lf_percent + self.mf_percent + self.hf_percent + self.vhf_percent

    @property
    def dominant_label(self) -> str | None:
        if self.dominant_class is None:
            return None
        return self.MgbClass(self.dominant_class).label

    def consultation_facts(self) -> dict:
        return {
            "zone_baseline_rank": (
                Decimal(self.baseline_rank) if self.baseline_rank is not None else None
            ),
            "mgb_dominant_mapped_class": self.dominant_class,
            "mgb_dominant_mapped_percent": self.dominant_percent,
            "mgb_mapped_percent": self.mapped_percent,
            "mgb_unmapped_percent": self.unmapped_percent,
            "mgb_conflict_percent": self.conflict_percent,
            "mgb_dataset_version": self.dataset.version,
        }

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}
        if self.area_id and self.area.area_type != GeographicArea.AreaType.BARANGAY:
            errors["area"] = "A susceptibility summary must reference a barangay."

        percentages = {
            self.MgbClass.LOW: self.lf_percent,
            self.MgbClass.MODERATE: self.mf_percent,
            self.MgbClass.HIGH: self.hf_percent,
            self.MgbClass.VERY_HIGH: self.vhf_percent,
        }
        all_percentages = [
            *percentages.values(),
            self.conflict_percent,
            self.unmapped_percent,
        ]
        if any(value < 0 or value > 100 for value in all_percentages):
            errors["partition_percent_total"] = "Every percentage must be between 0 and 100."
        if abs(self.partition_percent_total - 100) > 0.01:
            errors["partition_percent_total"] = (
                "The class, conflict, and unmapped partition must total 100%."
            )

        maximum = max(percentages.values())
        winners = [code for code, value in percentages.items() if value == maximum]
        if maximum == 0 or len(winners) != 1:
            if self.dominant_class is not None or self.baseline_rank is not None:
                errors["dominant_class"] = (
                    "No dominant class may be assigned when mapped coverage is zero "
                    "or the largest class is tied."
                )
            if self.dominant_percent is not None:
                errors["dominant_percent"] = (
                    "No dominant percentage may be assigned without one dominant class."
                )
        else:
            expected_class = winners[0]
            expected_rank = {
                self.MgbClass.LOW: 1,
                self.MgbClass.MODERATE: 2,
                self.MgbClass.HIGH: 3,
                self.MgbClass.VERY_HIGH: 4,
            }[expected_class]
            if self.dominant_class != expected_class:
                errors["dominant_class"] = (
                    "The dominant class must be the unique largest mapped area share."
                )
            if self.dominant_percent != maximum:
                errors["dominant_percent"] = (
                    "The dominant percentage must equal the dominant class share."
                )
            if self.baseline_rank != expected_rank:
                errors["baseline_rank"] = "The baseline rank must follow LF=1, MF=2, HF=3, VHF=4."

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        label = self.dominant_label or "No mapped dominant class"
        return f"{self.area.name}: {label} ({self.dataset.version})"
