
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError

from .flow_workflow import publish_dss_flow, submit_dss_flow
from .models import DSSFlowVersion, DSSOption, DSSOutcome, DSSQuestion, GuidanceItem


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


class DSSQuestionInline(admin.TabularInline):
    model = DSSQuestion
    extra = 0
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return obj is None or obj.workflow_status == DSSFlowVersion.WorkflowStatus.DRAFT

    def has_change_permission(self, request, obj=None):
        return obj is None or obj.workflow_status == DSSFlowVersion.WorkflowStatus.DRAFT

    def has_delete_permission(self, request, obj=None):
        return obj is None or obj.workflow_status == DSSFlowVersion.WorkflowStatus.DRAFT


@admin.register(DSSFlowVersion)
class DSSFlowVersionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "version",
        "operating_mode",
        "data_status",
        "workflow_status",
    )
    list_filter = ("operating_mode", "data_status", "workflow_status")
    search_fields = ("code", "title", "version")
    autocomplete_fields = ("source", "susceptibility_levels")
    inlines = (DSSQuestionInline,)
    readonly_fields = ("workflow_status", "published_at", "created_at", "updated_at")
    actions = ("submit_for_review", "publish_reviewed")

    @admin.action(description="Submit selected DSS draft for review")
    def submit_for_review(self, request, queryset):
        for flow in queryset:
            try:
                submit_dss_flow(flow_id=flow.pk, actor=request.user)
            except (PermissionDenied, ValidationError) as error:
                self.message_user(request, str(error), level="ERROR")

    @admin.action(description="Publish selected reviewed DSS flow")
    def publish_reviewed(self, request, queryset):
        for flow in queryset:
            try:
                publish_dss_flow(flow_id=flow.pk, actor=request.user)
            except (PermissionDenied, ValidationError) as error:
                self.message_user(request, str(error), level="ERROR")


class DSSOptionInline(admin.TabularInline):
    model = DSSOption
    fk_name = "question"
    extra = 0

    def has_add_permission(self, request, obj=None):
        return obj is None or obj.flow.workflow_status == DSSFlowVersion.WorkflowStatus.DRAFT

    def has_change_permission(self, request, obj=None):
        return obj is None or obj.flow.workflow_status == DSSFlowVersion.WorkflowStatus.DRAFT

    def has_delete_permission(self, request, obj=None):
        return obj is None or obj.flow.workflow_status == DSSFlowVersion.WorkflowStatus.DRAFT


@admin.register(DSSQuestion)
class DSSQuestionAdmin(admin.ModelAdmin):
    list_display = ("prompt", "flow", "display_order", "is_start")
    list_filter = ("flow__workflow_status", "is_start")
    search_fields = ("code", "prompt")
    inlines = (DSSOptionInline,)

    def has_change_permission(self, request, obj=None):
        allowed = super().has_change_permission(request, obj)
        return allowed and (
            obj is None
            or obj.flow.workflow_status == DSSFlowVersion.WorkflowStatus.DRAFT
        )

    def has_delete_permission(self, request, obj=None):
        allowed = super().has_delete_permission(request, obj)
        return allowed and (
            obj is None
            or obj.flow.workflow_status == DSSFlowVersion.WorkflowStatus.DRAFT
        )


@admin.register(DSSOutcome)
class DSSOutcomeAdmin(admin.ModelAdmin):
    list_display = ("title", "flow", "category")
    list_filter = ("flow__workflow_status", "category")
    search_fields = ("code", "title", "instruction")
    autocomplete_fields = ("flow", "source", "guidance_item")

    def has_change_permission(self, request, obj=None):
        allowed = super().has_change_permission(request, obj)
        return allowed and (
            obj is None
            or obj.flow.workflow_status == DSSFlowVersion.WorkflowStatus.DRAFT
        )

    def has_delete_permission(self, request, obj=None):
        allowed = super().has_delete_permission(request, obj)
        return allowed and (
            obj is None
            or obj.flow.workflow_status == DSSFlowVersion.WorkflowStatus.DRAFT
        )
