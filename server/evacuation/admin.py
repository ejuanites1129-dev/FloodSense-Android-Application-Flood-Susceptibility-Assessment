from django.contrib import admin

from .models import EvacuationCenter


@admin.register(EvacuationCenter)
class EvacuationCenterAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "geographic_area",
        "verification_status",
        "publication_status",
        "verified_on",
    )
    list_filter = ("verification_status", "publication_status")
    search_fields = ("name", "address", "source__name")
    autocomplete_fields = ("geographic_area", "source")
    readonly_fields = ("public_id", "created_at", "updated_at")
