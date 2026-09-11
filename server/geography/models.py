
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
            raise ValidationError(
                "Provide exactly one value: text_value or numeric_value."
            )

    def __str__(self) -> str:
        value = self.text_value or self.numeric_value
        return f"{self.area}: {self.fact_key}={value}"
