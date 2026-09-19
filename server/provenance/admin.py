from django.contrib import admin

from .models import DataSource


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
        "source_type",
        "status",
        "is_publicly_releasable",
        "updated_at",
    )
    list_filter = ("source_type", "status", "is_publicly_releasable")
    search_fields = ("name", "organization", "coverage_description")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("reviewed_by",)

    fieldsets = (
        (
            "Source identity",
            {"fields": ("name", "organization", "custodian", "source_type", "version")},
        ),
        (
            "Coverage",
            {
                "fields": (
                    "coverage_description",
                    "record_period_start",
                    "record_period_end",
                    "received_or_created_on",
                )
            },
        ),
        (
            "Governance",
            {
                "fields": (
                    "permitted_use",
                    "status",
                    "reviewed_by",
                    "reviewed_on",
                    "is_publicly_releasable",
                )
            },
        ),
        (
            "Documentation",
            {
                "fields": (
                    "processing_notes",
                    "limitations",
                    "citation_url",
                    "notes",
                )
            },
        ),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )
