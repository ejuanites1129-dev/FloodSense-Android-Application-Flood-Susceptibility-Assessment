
from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import AreaFact, GeographicArea
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
