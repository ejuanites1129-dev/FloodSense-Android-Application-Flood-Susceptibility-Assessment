"""Read-only, allowlisted Settings context; never an inference configuration API."""

from django.db.models import Count, Q
from expert.models import RuleSet, ScenarioOption
from provenance.models import DataSource, PublicationStatus
from provenance.policies import permitted_records, record_is_permitted

SOURCE_FIELDS = (
    "source__name",
    "source__organization",
    "source__source_type",
    "source__status",
    "source__is_publicly_releasable",
)
REVIEWABLE_STATUSES = (
    PublicationStatus.DEMONSTRATION,
    PublicationStatus.PENDING_VALIDATION,
    PublicationStatus.APPROVED,
)


def _source_summary(source):
    return {
        "name": source.name,
        "organization": source.organization,
        "type": source.get_source_type_display(),
        "status": source.get_status_display(),
        "publicly_releasable": source.is_publicly_releasable,
    }


def _active_version_states(counts, permitted_versions):
    """Fail closed on inconsistencies, including legacy multiple-active records."""
    states = []
    for mode, label in RuleSet.Mode.choices:
        candidates = [item for item in permitted_versions if item["mode"] == mode]
        count = counts.get(mode, 0)
        state = {"mode": mode, "label": label, "state": "empty", "record": None}
        if count or candidates:
            state["state"] = "unavailable"
            if count == 1 and len(candidates) == 1:
                candidate = candidates[0]
                if candidate["name"].strip() and candidate["version"].strip():
                    state.update(state="available", record=candidate)
        states.append(state)
    return states


def _inventory_group(option):
    # Any explicit demo marker keeps an inconsistent record out of official data.
    if (
        option.status == PublicationStatus.DEMONSTRATION
        or option.source.status == PublicationStatus.DEMONSTRATION
        or option.source.source_type == DataSource.SourceType.DEMONSTRATION
    ):
        return "demonstration"
    if record_is_permitted(option, RuleSet.Mode.OFFICIAL):
        return "approved"
    return "pending"


def get_settings_data(*, query="", category=""):
    """Three queries regardless of inventory size, with no raw rules or private notes."""
    active = RuleSet.objects.filter(is_active=True)
    counts = dict(
        active.order_by().values("mode").annotate(total=Count("pk")).values_list("mode", "total")
    )
    permitted = (
        (
            permitted_records(active.filter(mode=RuleSet.Mode.DEMONSTRATION), "DEMONSTRATION")
            | permitted_records(active.filter(mode=RuleSet.Mode.OFFICIAL), "OFFICIAL")
        )
        .select_related("source")
        .only("name", "version", "mode", "status", "effective_on", "is_active", *SOURCE_FIELDS)
    )
    versions = [
        {
            "name": item.name,
            "version": item.version,
            "mode": item.mode,
            "status": item.get_status_display(),
            "effective_on": item.effective_on,
            "is_active": item.is_active,
            "source": _source_summary(item.source),
        }
        for item in permitted
    ]

    options = (
        ScenarioOption.objects.filter(
            status__in=REVIEWABLE_STATUSES,
            source__status__in=REVIEWABLE_STATUSES,
        )
        .filter(
            Q(source__is_publicly_releasable=True)
            | Q(
                status=PublicationStatus.DEMONSTRATION,
                source__status=PublicationStatus.DEMONSTRATION,
                source__source_type=DataSource.SourceType.DEMONSTRATION,
            )
        )
        .select_related("source")
        .only(
            "label",
            "code",
            "category",
            "minimum_value",
            "maximum_value",
            "derived_value",
            "unit",
            "status",
            "is_enabled",
            "display_order",
            *SOURCE_FIELDS,
        )
        .order_by("category", "display_order", "label", "pk")
    )
    groups = {
        "demonstration": {
            "key": "demonstration",
            "label": "Demonstration only",
            "description": "Fictional references, not official Bacoor information.",
        },
        "approved": {
            "key": "approved",
            "label": "Approved source-backed references",
            "description": "Approval for data use is not authorization for editing.",
        },
        "pending": {
            "key": "pending",
            "label": "Pending or inconsistent references",
            "description": "These records are not eligible for official assessment use.",
        },
    }
    for group in groups.values():
        group.update(total=0, records=[])
    query = query.casefold()
    for option in options:
        group = groups[_inventory_group(option)]
        group["total"] += 1
        if category and category != option.category:
            continue
        if query and query not in option.label.casefold() and query not in option.code.casefold():
            continue
        eligible = next(
            (label for mode, label in RuleSet.Mode.choices if record_is_permitted(option, mode)),
            "Not eligible under the current source policy",
        )
        group["records"].append(
            {
                "label": option.label,
                "code": option.code,
                "category": option.get_category_display(),
                "minimum": option.minimum_value,
                "maximum": option.maximum_value,
                "derived_value": option.derived_value,
                "unit": option.unit,
                "status": option.get_status_display(),
                "enabled": option.is_enabled,
                "display_order": option.display_order,
                "source": _source_summary(option.source),
                "eligible_mode": eligible,
            }
        )
    return {
        "active_versions": _active_version_states(counts, versions),
        "unknown_active_mode": any(mode not in RuleSet.Mode.values for mode in counts),
        "groups": list(groups.values()),
        "total": sum(group["total"] for group in groups.values()),
        "matching": sum(len(group["records"]) for group in groups.values()),
    }
