"""Read-only administrative reporting; never an assessment of flood conditions."""

from dss.models import GuidanceItem

from .dashboard import get_dashboard_summary

REPORT_MODULES = (
    (
        "geographic_areas",
        "map-data",
        "Geographic areas",
        None,
        "Pending-validation administrative records supported by Map data, including disabled "
        "records. Other geographic records are outside this review workload.",
    ),
    (
        "data_sources",
        "sources-content",
        "Data sources",
        "provenance.view_datasource",
        "Sources with Pending validation status, regardless of public-release permission.",
    ),
    (
        "guidance_items",
        "dss-content",
        "DSS guidance",
        "dss.view_guidanceitem",
        "Items with Pending validation status or In review workflow state; each item counts once.",
    ),
    (
        "scenario_options",
        "rainfall-references",
        "Scenario references",
        "expert.view_scenariooption",
        "Options with Pending validation status, including disabled options.",
    ),
    (
        "evacuation_centers",
        "evacuation-centers",
        "Evacuation centers",
        "evacuation.view_evacuationcenter",
        "Centers in the explicit In review verification state.",
    ),
)


def get_report_summary(*, user):
    snapshot = get_dashboard_summary(user=user, include_activity=False)
    reviews = {row["section_slug"]: row for row in snapshot["review_attention"]["modules"]}
    modules = []
    for key, slug, label, permission, definition in REPORT_MODULES:
        allowed = permission is None or user.has_perm(permission)
        module = {"key": key, "slug": slug, "label": label, "allowed": allowed}
        if allowed:
            summary = snapshot[key]
            module.update(summary=summary, review=reviews[slug], definition=definition)
            if key == "guidance_items":
                module["workflows"] = [
                    {"label": label, "count": summary[f"workflow_{value}"]}
                    for value, label in GuidanceItem.WorkflowStatus.choices
                ]
        modules.append(module)
    visible = [module for module in modules if module["allowed"]]
    return {
        "modules": modules,
        "visible_modules": len(visible),
        "restricted_modules": len(modules) - len(visible),
        "total": sum(module["summary"]["total"] for module in visible),
        "review_total": sum(module["review"]["count"] for module in visible),
    }
