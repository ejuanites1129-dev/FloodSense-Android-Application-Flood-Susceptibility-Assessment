"""Database summaries, without scientific evaluation or publication decisions."""

from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.db.models import Count, Q
from dss.models import GuidanceItem
from expert.models import ScenarioOption
from geography.models import GeographicArea
from provenance.models import DataSource, PublicationStatus


def _record_summary(model, *, include_enabled=False, extra_counts=None):
    """Count all rows and each persisted status together in one SQL aggregate."""

    status_choices = model._meta.get_field("status").choices
    counts = {
        "total": Count("pk"),
        **{
            f"status_{value}": Count("pk", filter=Q(status=value))
            for value, _label in status_choices
        },
        **(extra_counts or {}),
    }
    if include_enabled:
        counts["enabled"] = Count("pk", filter=Q(is_enabled=True))
    summary = model.objects.aggregate(**counts)
    summary["status_counts"] = {
        value: summary.pop(f"status_{value}") for value, _label in status_choices
    }
    summary["statuses"] = [
        {"value": value, "label": label, "count": summary["status_counts"][value]}
        for value, label in status_choices
    ]
    return summary


def _recent_activity():
    """Read only safe fields from the limited technical Admin event source."""

    module_labels = {
        ("geography", "geographicarea"): "Geographic areas",
        ("provenance", "datasource"): "Data sources",
        ("dss", "guidanceitem"): "DSS guidance",
        ("expert", "scenariooption"): "Scenario options",
    }
    action_labels = {ADDITION: "Added", CHANGE: "Changed", DELETION: "Deleted"}
    relevant_models = Q()
    for app_label, model_name in module_labels:
        relevant_models |= Q(
            content_type__app_label=app_label, content_type__model=model_name
        )

    # Joining by metadata avoids ContentType.get_for_model(), which may write
    # when its cached content type is missing. No object text or change payload
    # is selected, and actor/content-type joins avoid per-event lookups.
    entries = (
        LogEntry.objects.filter(relevant_models, action_flag__in=action_labels)
        .order_by("-action_time", "-pk")
        .values(
            "action_flag",
            "content_type__app_label",
            "content_type__model",
            "user__display_name",
            "user_id",
            "action_time",
        )[:5]
    )
    return [
        {
            "action": action_labels[entry["action_flag"]],
            "module": module_labels[
                (entry["content_type__app_label"], entry["content_type__model"])
            ],
            "actor": entry["user__display_name"].strip() or f"Account #{entry['user_id']}",
            "timestamp": entry["action_time"],
        }
        for entry in entries
    ]


def get_dashboard_summary():
    """Return a read-only snapshot using four aggregates and one activity query.

    Enabled and approved are independent counts. These summaries do not assert
    resident-facing eligibility, source approval, or geographic susceptibility.
    """

    geographic_areas = _record_summary(
        GeographicArea,
        include_enabled=True,
        extra_counts={
            f"area_type_{value}": Count("pk", filter=Q(area_type=value))
            for value, _label in GeographicArea.AreaType.choices
        },
    )
    geographic_areas["area_types"] = [
        {"value": value, "label": label, "count": geographic_areas.pop(f"area_type_{value}")}
        for value, label in GeographicArea.AreaType.choices
    ]
    data_sources = _record_summary(
        DataSource,
        extra_counts={
            "approved_public": Count(
                "pk", filter=Q(status=PublicationStatus.APPROVED, is_publicly_releasable=True)
            ),
        },
    )
    guidance_items = _record_summary(GuidanceItem, include_enabled=True)
    scenario_options = _record_summary(
        ScenarioOption,
        include_enabled=True,
        extra_counts={
            "enabled_intensity": Count(
                "pk", filter=Q(is_enabled=True, category=ScenarioOption.Category.INTENSITY)
            ),
            "enabled_duration": Count(
                "pk", filter=Q(is_enabled=True, category=ScenarioOption.Category.DURATION)
            ),
        },
    )

    review_modules = [
        {
            "label": label,
            "section_slug": section_slug,
            "count": summary["status_counts"][PublicationStatus.PENDING_VALIDATION],
        }
        for label, section_slug, summary in (
            ("Geographic areas", "map-data", geographic_areas),
            ("Data sources", "sources-content", data_sources),
            ("DSS guidance", "dss-content", guidance_items),
            ("Scenario options", "assessment-parameters", scenario_options),
        )
    ]
    return {
        "geographic_areas": geographic_areas,
        "data_sources": data_sources,
        "guidance_items": guidance_items,
        "scenario_options": scenario_options,
        "review_attention": {
            "total": sum(module["count"] for module in review_modules),
            "modules": review_modules,
        },
        "recent_activity": _recent_activity(),
        "activity_is_complete_audit": False,
    }
