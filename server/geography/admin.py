from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import (
    AreaFact,
    BarangaySusceptibilitySummary,
    FloodSusceptibilityDataset,
    GeographicArea,
)
from .widgets import FloodSenseOSMWidget


class AreaFactInline(admin.TabularInline):
    model = AreaFact
    extra = 0
    fields = (
        "fact_key",
        "text_value",
        "numeric_value",
        "unit",
        "source",
        "status",
        "is_enabled",
    )


@admin.register(GeographicArea)
class GeographicAreaAdmin(GISModelAdmin):
    gis_widget = FloodSenseOSMWidget
    list_display = ("name", "code", "area_type", "status", "is_enabled", "source")
    list_filter = ("area_type", "status", "is_enabled")
    search_fields = ("name", "code")
    autocomplete_fields = ("source",)
    list_select_related = ("source",)
    inlines = (AreaFactInline,)


@admin.register(AreaFact)
class AreaFactAdmin(admin.ModelAdmin):
    list_display = (
        "fact_key",
        "area",
        "display_value",
        "unit",
        "status",
        "is_enabled",
    )
    list_filter = ("status", "is_enabled", "fact_key")
    search_fields = ("fact_key", "text_value", "area__name", "area__code")
    autocomplete_fields = ("area", "source")
    list_select_related = ("area", "source")

    @admin.display(description="Value")
    def display_value(self, obj: AreaFact):
        return obj.text_value or obj.numeric_value


@admin.register(FloodSusceptibilityDataset)
class FloodSusceptibilityDatasetAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "version",
        "status",
        "is_active_for_consultation",
        "source_accessed_on",
    )
    list_filter = ("status", "is_active_for_consultation", "aggregation_method")
    search_fields = ("name", "version", "code", "source__name")
    list_select_related = ("source",)
    readonly_fields = tuple(field.name for field in FloodSusceptibilityDataset._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BarangaySusceptibilitySummary)
class BarangaySusceptibilitySummaryAdmin(admin.ModelAdmin):
    list_display = (
        "area",
        "dominant_class",
        "dominant_percent",
        "mapped_percent_display",
        "unmapped_percent",
        "dataset",
    )
    list_filter = ("dominant_class", "dataset")
    search_fields = ("area__name", "area__code", "dataset__version")
    list_select_related = ("area", "dataset")
    readonly_fields = tuple(field.name for field in BarangaySusceptibilitySummary._meta.fields)

    @admin.display(description="Mapped %")
    def mapped_percent_display(self, obj: BarangaySusceptibilitySummary):
        return obj.mapped_percent

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
