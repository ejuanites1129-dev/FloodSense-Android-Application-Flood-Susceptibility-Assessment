from django.contrib import admin

from .models import CenterImportBatch, EvacuationCenter


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


@admin.register(CenterImportBatch)
class CenterImportBatchAdmin(admin.ModelAdmin):
    """Technical review of tracked batches; never bypass the reviewed importer."""

    list_display = (
        "public_id",
        "filename",
        "source",
        "actor",
        "row_count",
        "valid_count",
        "invalid_count",
        "imported_count",
        "imported_at",
    )
    readonly_fields = tuple(field.name for field in CenterImportBatch._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
