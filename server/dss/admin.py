from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError

from .flow_workflow import (
    publish_dss_flow,
    retire_dss_flow,
    return_dss_flow_to_draft,
    submit_dss_flow,
)
from .models import (
    LINKED_GUIDANCE_FIELDS,
    DSSContentBlock,
    DSSFlowVersion,
    DSSOption,
    DSSOutcome,
    DSSQuestion,
    GuidanceItem,
)


def _flow_is_draft(obj):
    """Check stored state; a cached parent may predate review or publication."""
    if obj is None:
        return True
    if isinstance(obj, DSSFlowVersion):
        return DSSFlowVersion.objects.filter(pk=obj.pk, workflow_status="DRAFT").exists()
    path = (
        "question__flow__workflow_status" if isinstance(obj, DSSOption) else "flow__workflow_status"
    )
    return type(obj).objects.filter(pk=obj.pk, **{path: "DRAFT"}).exists()


@admin.register(GuidanceItem)
class GuidanceItemAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "susceptibility_level",
        "category",
        "display_order",
        "status",
        "workflow_status",
        "is_enabled",
    )
    list_filter = (
        "susceptibility_level",
        "category",
        "status",
        "workflow_status",
        "is_enabled",
    )
    search_fields = ("title", "instruction")
    autocomplete_fields = ("susceptibility_level", "source")
    list_select_related = ("susceptibility_level", "source")
    readonly_fields = ("workflow_status", "is_enabled", "created_at", "updated_at")

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj and obj.structured_outcomes.exclude(flow__workflow_status="DRAFT").exists():
            return fields + tuple(field.removesuffix("_id") for field in LINKED_GUIDANCE_FIELDS)
        return fields


class DSSDraftInline(admin.TabularInline):
    extra = 0
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return super().has_add_permission(request, obj) and (_flow_is_draft(obj))

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (_flow_is_draft(obj))

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (_flow_is_draft(obj))


class DSSQuestionInline(DSSDraftInline):
    model = DSSQuestion


class DSSOutcomeInline(DSSDraftInline):
    model = DSSOutcome
    autocomplete_fields = ("source", "guidance_item")


class DSSContentBlockInline(DSSDraftInline):
    model = DSSContentBlock
    autocomplete_fields = ("source",)


@admin.register(DSSFlowVersion)
class DSSFlowVersionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "version",
        "operating_mode",
        "data_status",
        "workflow_status",
        "source",
        "effective_date",
    )
    list_filter = ("operating_mode", "data_status", "workflow_status")
    search_fields = ("code", "title", "version")
    autocomplete_fields = ("source", "susceptibility_levels")
    inlines = (DSSQuestionInline, DSSOutcomeInline, DSSContentBlockInline)
    readonly_fields = ("workflow_status", "published_at", "created_at", "updated_at")
    actions = ("submit_for_review", "return_to_draft", "publish_reviewed", "retire_published")

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (_flow_is_draft(obj))

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (_flow_is_draft(obj))

    def has_review_permission(self, request):
        return request.user.has_perm("dss.review_dssflowversion")

    def has_publish_permission(self, request):
        return request.user.has_perm("dss.publish_dssflowversion")

    @admin.action(description="Submit selected DSS draft for review", permissions=("review",))
    def submit_for_review(self, request, queryset):
        for flow in queryset:
            try:
                submit_dss_flow(
                    flow_id=flow.pk, actor=request.user, expected_updated_at=flow.updated_at
                )
            except (PermissionDenied, ValidationError) as error:
                self.message_user(request, str(error), level="ERROR")

    @admin.action(description="Publish selected reviewed DSS flow", permissions=("publish",))
    def publish_reviewed(self, request, queryset):
        for flow in queryset:
            try:
                publish_dss_flow(
                    flow_id=flow.pk, actor=request.user, expected_updated_at=flow.updated_at
                )
            except (PermissionDenied, ValidationError) as error:
                self.message_user(request, str(error), level="ERROR")

    @admin.action(
        description="Return selected in-review DSS flow to draft", permissions=("review",)
    )
    def return_to_draft(self, request, queryset):
        for flow in queryset:
            try:
                return_dss_flow_to_draft(
                    flow_id=flow.pk, actor=request.user, expected_updated_at=flow.updated_at
                )
            except (PermissionDenied, ValidationError) as error:
                self.message_user(request, str(error), level="ERROR")

    @admin.action(description="Retire selected published DSS version", permissions=("publish",))
    def retire_published(self, request, queryset):
        for flow in queryset:
            try:
                retire_dss_flow(
                    flow_id=flow.pk, actor=request.user, expected_updated_at=flow.updated_at
                )
            except (PermissionDenied, ValidationError) as error:
                self.message_user(request, str(error), level="ERROR")

    def delete_queryset(self, request, queryset):
        if queryset.exclude(workflow_status=DSSFlowVersion.WorkflowStatus.DRAFT).exists():
            raise PermissionDenied("Only draft DSS records may be deleted.")
        super().delete_queryset(request, queryset)

    def save_related(self, request, form, formsets, change):
        from django.db import transaction

        with transaction.atomic():
            flow = DSSFlowVersion.objects.select_for_update().get(pk=form.instance.pk)
            if flow.workflow_status != DSSFlowVersion.WorkflowStatus.DRAFT:
                raise PermissionDenied("Only draft DSS records may be edited.")
            super().save_related(request, form, formsets, change)


class DSSOptionInline(admin.TabularInline):
    model = DSSOption
    fk_name = "question"
    extra = 0

    def has_add_permission(self, request, obj=None):
        return super().has_add_permission(request, obj) and (_flow_is_draft(obj))

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (_flow_is_draft(obj))

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (_flow_is_draft(obj))


@admin.register(DSSQuestion)
class DSSQuestionAdmin(admin.ModelAdmin):
    list_display = ("prompt", "flow", "display_order", "is_start")
    list_filter = ("flow__workflow_status", "is_start")
    search_fields = ("code", "prompt")
    inlines = (DSSOptionInline,)

    def has_change_permission(self, request, obj=None):
        allowed = super().has_change_permission(request, obj)
        return allowed and (_flow_is_draft(obj))

    def has_delete_permission(self, request, obj=None):
        allowed = super().has_delete_permission(request, obj)
        return allowed and (_flow_is_draft(obj))


@admin.register(DSSOutcome)
class DSSOutcomeAdmin(admin.ModelAdmin):
    list_display = ("title", "flow", "category")
    list_filter = ("flow__workflow_status", "category")
    search_fields = ("code", "title", "instruction")
    autocomplete_fields = ("flow", "source", "guidance_item")

    def has_change_permission(self, request, obj=None):
        allowed = super().has_change_permission(request, obj)
        return allowed and (_flow_is_draft(obj))

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (_flow_is_draft(obj))


@admin.register(DSSContentBlock)
class DSSContentBlockAdmin(admin.ModelAdmin):
    list_display = ("title", "flow", "phase", "content_type", "audience", "data_status", "source")
    list_filter = ("flow__workflow_status", "phase", "content_type", "audience", "data_status")
    search_fields = ("title", "body", "source_locator")
    autocomplete_fields = ("flow", "outcome", "source")

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (_flow_is_draft(obj))

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (_flow_is_draft(obj))


@admin.register(DSSOption)
class DSSOptionAdmin(admin.ModelAdmin):
    list_display = ("label", "question", "next_question", "outcome", "display_order")
    list_filter = ("question__flow__workflow_status",)
    search_fields = ("code", "label")
    autocomplete_fields = ("question", "next_question", "outcome")

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (_flow_is_draft(obj))

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (_flow_is_draft(obj))
