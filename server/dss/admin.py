
from django.contrib import admin

from .models import GuidanceItem


@admin.register(GuidanceItem)
class GuidanceItemAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "susceptibility_level",
        "category",
        "display_order",
        "status",
        "is_enabled",
    )
    list_filter = ("susceptibility_level", "category", "status", "is_enabled")
    search_fields = ("title", "instruction")
    autocomplete_fields = ("susceptibility_level", "source")
    list_select_related = ("susceptibility_level", "source")
    readonly_fields = ("created_at", "updated_at")
