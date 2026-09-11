
from django.contrib import admin

from .models import (
    ExpertRule,
    ExpertRuleCondition,
    RuleSet,
    ScenarioOption,
    SusceptibilityLevel,
)


@admin.register(ScenarioOption)
class ScenarioOptionAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "code",
        "category",
        "derived_value",
        "status",
        "is_enabled",
        "source",
    )
    list_filter = ("category", "status", "is_enabled")
    search_fields = ("label", "code")
    autocomplete_fields = ("source",)
    list_select_related = ("source",)


@admin.register(SusceptibilityLevel)
class SusceptibilityLevelAdmin(admin.ModelAdmin):
    list_display = ("label", "code", "display_order", "map_color", "status", "is_enabled")
    list_filter = ("status", "is_enabled")
    search_fields = ("label", "code", "definition")
    autocomplete_fields = ("source",)
    list_select_related = ("source",)


@admin.register(RuleSet)
class RuleSetAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "mode", "status", "is_active", "updated_at")
    list_filter = ("mode", "status", "is_active")
    search_fields = ("name", "version", "change_summary")
    autocomplete_fields = ("source",)
    list_select_related = ("source",)
    readonly_fields = ("created_at", "updated_at")


class ExpertRuleConditionInline(admin.TabularInline):
    model = ExpertRuleCondition
    extra = 0


@admin.register(ExpertRule)
class ExpertRuleAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "ruleset",
        "geographic_scope",
        "result_level",
        "priority",
        "status",
        "is_enabled",
    )
    list_filter = ("ruleset", "result_level", "status", "is_enabled")
    search_fields = ("code", "rationale", "geographic_scope__name")
    autocomplete_fields = ("ruleset", "geographic_scope", "result_level", "source")
    list_select_related = ("ruleset", "geographic_scope", "result_level", "source")
    inlines = (ExpertRuleConditionInline,)


@admin.register(ExpertRuleCondition)
class ExpertRuleConditionAdmin(admin.ModelAdmin):
    list_display = (
        "rule",
        "condition_type",
        "operator",
        "display_order",
        "is_enabled",
    )
    list_filter = ("condition_type", "operator", "is_enabled")
    search_fields = ("rule__code", "fact_key", "expected_text")
    autocomplete_fields = ("rule", "scenario_option")
    list_select_related = ("rule", "scenario_option")
