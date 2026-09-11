
from django.db import models
from expert.models import SusceptibilityLevel
from provenance.models import DataSource, PublicationStatus


class GuidanceItem(models.Model):
    """Reviewed preparedness guidance returned by the DSS."""

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
    status = models.CharField(
        max_length=30,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DEMONSTRATION,
    )
    is_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("susceptibility_level__display_order", "display_order", "id")

    def __str__(self) -> str:
        return f"{self.susceptibility_level}: {self.title}"
