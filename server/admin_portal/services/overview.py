"""Permission-aware availability snapshot; SELECT-only and never an assessment."""

from accounts.models import LegalDocumentVersion, OnboardingVersion
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from dss.models import DSSFlowVersion, GuidanceItem
from dss.services import GuidanceSelectionError, select_dss_flow
from evacuation.models import CenterImportBatch, EvacuationCenter
from evacuation.services import (
    _public_center,
    eligible_center_candidates,
    ready_reference_barangays,
)
from expert.models import RuleSet, ScenarioOption, SusceptibilityLevel
from geography.boundaries import bacoor_boundary_source_ids
from geography.constants import BACOOR_REFERENCE_BARANGAY_COUNT
from geography.services import eligible_bacoor_reference_barangays
from provenance.models import DataSource, PublicationStatus
from provenance.policies import OFFICIAL_MODE, normalize_operating_mode, permitted_records

from .dashboard import ACTIVITY_MODULE_LABELS, _recent_activity
from .settings_data import _active_version_states

MODE_LABELS = {"OFFICIAL": "Approved-source mode", "DEMONSTRATION": "Demonstration only"}


def _link(route, label, *, args=None, query=""):
    return {"text": label, "url": reverse(f"admin_portal:{route}", args=args) + query}


def _card(key, title, *, allowed=True, icon=None):
    return {
        "key": key,
        "title": title,
        "allowed": allowed,
        "icon": icon or key,
        "lines": [],
        "links": [],
    }


def _queue(label, count, reason, module, state):
    return {
        "label": label,
        "count": count,
        "kind": "Workflow queue",
        "reason": reason,
        **_link("review-queue", "Review queue", args=[module], query=f"?state={state}"),
    }


def _prepare_availability(mode):
    # The resident endpoint selects the default preparedness code. Inspect that
    # same version, then delegate dates, provenance and graph gates to its resolver.
    published = (
        DSSFlowVersion.objects.filter(
            code="preparedness", operating_mode=mode, workflow_status="PUBLISHED"
        )
        .values_list("pk", flat=True)
        .first()
    )
    result = {"available": False, "published": published is not None}
    if published is None:
        return {**result, "reason": "No published Prepare flow is configured for this mode."}
    level = (
        SusceptibilityLevel.objects.filter(dss_flows=published)
        .order_by("pk")
        .values_list("code", flat=True)
        .first()
    )
    if level is None:
        return {**result, "reason": "The published Prepare flow has no applicable level."}
    try:
        flow = select_dss_flow(susceptibility_code=level, mode=mode)
    except GuidanceSelectionError as error:
        # Resolver errors contain safe availability explanations, not raw content.
        return {**result, "reason": error.message_dict["flow"][0]}
    return {
        "available": True,
        "published": True,
        "title": flow.title,
        "version": flow.version,
        "levels": list(
            flow.susceptibility_levels.order_by("display_order", "pk").values_list(
                "code", flat=True
            )
        ),
        "link": _link("dss-flow-detail", "View Prepare version", args=[flow.pk]),
    }


def _assessment_metadata(mode, references):
    active = RuleSet.objects.filter(mode=mode, is_active=True)
    count = active.count()
    versions = list(
        permitted_records(active, mode).values("name", "version", "mode", "status", "effective_on")
    )
    state = next(
        row for row in _active_version_states({mode: count}, versions) if row["mode"] == mode
    )
    missing = []
    if state["state"] != "available":
        missing.append("usable active knowledge-set metadata")
    if references is None:
        return {
            "label": "Assessment configuration checks limited",
            "reason": "Scenario references are restricted. Full availability was not checked.",
            **_link("settings", "Read-only Settings", query="#parameters"),
        }
    if not references["usable_intensity"] or not references["usable_duration"]:
        missing.append("eligible intensity and duration references with stored input values")
    return {
        "label": "Assessment configuration incomplete"
        if missing
        else "Assessment metadata present",
        "reason": (
            "Missing "
            + "; ".join(missing)
            + ". Individual scenarios can still return Insufficient Data."
            if missing
            else "Metadata are present; some scenarios can still return Insufficient Data."
        ),
        **_link("settings", "Read-only Settings", query="#parameters"),
    }


def _setup_configuration():
    # Same publication-existence checks as accounts.services.setup_status_for;
    # no resident identities, acceptances, bypasses or document bodies are read.
    legal = set(
        LegalDocumentVersion.objects.filter(status="PUBLISHED").values_list(
            "document_type", flat=True
        )
    )
    missing = [
        label for kind, label in [("TERMS", "Terms"), ("PRIVACY", "Privacy")] if kind not in legal
    ]
    if legal != {"TERMS", "PRIVACY"} and not missing:
        missing.append("valid Terms/Privacy configuration")
    if not OnboardingVersion.objects.filter(status="PUBLISHED").exists():
        missing.append("onboarding")
    if not missing:
        return None
    return {
        "label": "Resident setup content incomplete",
        "reason": "Published " + ", ".join(missing) + " content is missing. "
        "An authorized technical maintainer must configure it for normal resident setup.",
    }


def _activity(user):
    if not user.has_perm("admin.view_logentry"):
        return None
    labels = {
        **ACTIVITY_MODULE_LABELS,
        ("dss", "dssflowversion"): "Prepare flows",
        ("dss", "dssquestion"): "Prepare questions",
        ("dss", "dssoption"): "Prepare options",
        ("dss", "dssoutcome"): "Prepare outcomes",
        ("dss", "dsscontentblock"): "Prepare content",
    }
    allowed = {
        key: label
        for key, label in labels.items()
        if key == ("geography", "geographicarea") or user.has_perm(f"{key[0]}.view_{key[1]}")
    }
    return _recent_activity(allowed)[:3] if allowed else []


def get_overview_snapshot(*, user, mode=OFFICIAL_MODE):
    mode = normalize_operating_mode(mode)
    cards, queues, problems, configuration = [], [], [], []
    identities = ready_reference_barangays()
    coverage = (
        eligible_bacoor_reference_barangays()
        .filter(source_id__in=bacoor_boundary_source_ids())
        .count()
    )
    card = _card("map-data", "Map data")
    card.update(
        metric=f"{coverage} / {BACOOR_REFERENCE_BARANGAY_COUNT}",
        metric_label="eligible barangay boundary records",
        lines=[
            "Complete reference layer available" if identities else "Reference layer unavailable"
        ],
        note="Administrative coverage does not assign flood susceptibility.",
        links=[_link("map-data", "View map data")],
    )
    cards.append(card)

    references = None
    card = _card(
        "rainfall-references",
        "Scenario references",
        allowed=user.has_perm("expert.view_scenariooption"),
    )
    if card["allowed"]:
        options = permitted_records(ScenarioOption.objects.filter(is_enabled=True), mode)
        references = options.aggregate(
            intensity=Count("pk", filter=Q(category="INTENSITY")),
            duration=Count("pk", filter=Q(category="DURATION")),
            usable_intensity=Count(
                "pk", filter=Q(category="INTENSITY", derived_value__isnull=False)
            ),
            usable_duration=Count("pk", filter=Q(category="DURATION", derived_value__isnull=False)),
        )
        card.update(
            metric=references["intensity"] + references["duration"],
            metric_label="enabled, source-permitted options",
            lines=[
                f"{references['intensity']} intensity · {references['duration']} duration",
                MODE_LABELS[mode],
            ],
            note="Hypothetical inputs; eligible options can still lack facts needed for a result.",
            links=[_link("rainfall-references", "View references")],
        )
    cards.append(card)

    guidance_allowed = user.has_perm("dss.view_guidanceitem")
    flows_allowed = user.has_perm("dss.view_dssflowversion")
    card = _card("dss-content", "DSS content", allowed=guidance_allowed or flows_allowed)
    if card["allowed"]:
        card["note"] = "Assessment guidance and structured Prepare flows are separate content."
        if guidance_allowed:
            levels = permitted_records(SusceptibilityLevel.objects.filter(is_enabled=True), mode)
            guidance = permitted_records(
                GuidanceItem.objects.filter(
                    is_enabled=True, workflow_status="PUBLISHED", susceptibility_level__in=levels
                ),
                mode,
            ).count()
            card.update(metric=guidance, metric_label="eligible assessment guidance items")
            card["links"].append(_link("dss-content", "View assessment guidance"))
            review = GuidanceItem.objects.filter(workflow_status="IN_REVIEW").count()
            queues.append(
                _queue(
                    "Assessment guidance awaiting review",
                    review,
                    "Explicit In review items; drafts are excluded.",
                    "guidance",
                    "IN_REVIEW",
                )
            )
        else:
            card["lines"].append("Assessment guidance: access restricted")
        if flows_allowed:
            prepare = _prepare_availability(mode)
            card["prepare"] = prepare
            if not guidance_allowed:
                card.update(
                    metric="Available" if prepare["available"] else "Unavailable",
                    metric_label="structured Prepare flow",
                )
            card["links"].append(_link("dss-flow-list", "View Prepare flows"))
            review = DSSFlowVersion.objects.filter(workflow_status="IN_REVIEW").count()
            queues.insert(
                0,
                _queue(
                    "Prepare flows awaiting review",
                    review,
                    "Versioned flows explicitly submitted for review.",
                    "flows",
                    "IN_REVIEW",
                ),
            )
            if prepare["published"] and not prepare["available"]:
                problems.append(
                    {
                        "label": "Published Prepare flow unavailable",
                        "kind": "Availability problem",
                        "reason": MODE_LABELS[mode] + ": " + prepare["reason"],
                        **_link("dss-flow-list", "Review Prepare flows", query="?q=preparedness"),
                    }
                )
        else:
            card["lines"].append("Structured Prepare flows: access restricted")
    cards.append(card)

    card = _card(
        "evacuation-centers",
        "Evacuation centers",
        allowed=user.has_perm("evacuation.view_evacuationcenter"),
    )
    if card["allowed"]:
        totals = EvacuationCenter.objects.aggregate(
            stored=Count("pk"),
            verified=Count("pk", filter=Q(verification_status="VERIFIED")),
            review=Count("pk", filter=Q(verification_status="IN_REVIEW")),
        )
        eligible = 0
        if identities:
            for row in eligible_center_candidates(identities).iterator(chunk_size=500):
                row["distance_meters"] = 0.0  # Schema check only; no distance is displayed.
                eligible += _public_center(row, identities[row["geographic_area_id"]]) is not None
        card.update(
            metric=eligible,
            metric_label="eligible for normal resident display",
            lines=[f"{totals['stored']} stored · {totals['verified']} verified"],
            note="Excludes temporary tests; no claim about opening, occupancy or route safety.",
            links=[_link("evacuation-centers", "View centers")],
        )
        queues.insert(
            1,
            _queue(
                "Centers awaiting verification review",
                totals["review"],
                "Only centers in the explicit In review verification state.",
                "centers",
                "IN_REVIEW",
            ),
        )
        if user.has_perm("evacuation.add_evacuationcenter"):
            staged = CenterImportBatch.objects.filter(imported_at__isnull=True, valid_count__gt=0)
            count = staged.count()
            batch = staged.order_by("created_at", "pk").values_list("pk", flat=True).first()
            if batch is not None:
                queues.append(
                    {
                        "label": "Staged center imports awaiting confirmation",
                        "count": count,
                        "unit": "batch",
                        "kind": "Workflow queue",
                        "reason": "Review the oldest staged batch. "
                        "Completed imports and historical rejected rows are excluded.",
                        **_link("center-import-detail", "Review oldest batch", args=[batch]),
                    }
                )
    cards.append(card)

    card = _card(
        "sources-content", "Data sources", allowed=user.has_perm("provenance.view_datasource")
    )
    if card["allowed"]:
        sources = DataSource.objects.aggregate(
            stored=Count("pk"),
            public=Count(
                "pk",
                filter=Q(status=PublicationStatus.APPROVED, is_publicly_releasable=True)
                & ~Q(source_type=DataSource.SourceType.DEMONSTRATION),
            ),
            review=Count("pk", filter=Q(status=PublicationStatus.PENDING_VALIDATION)),
        )
        card.update(
            metric=sources["public"],
            metric_label="approved, publicly releasable sources",
            lines=[f"{sources['stored']} stored source{'s' if sources['stored'] != 1 else ''}"],
            note="Dependent records must pass their own eligibility checks.",
            links=[_link("sources-content", "View sources")],
        )
        queues.append(
            _queue(
                "Source metadata awaiting review",
                sources["review"],
                "Pending metadata review; deliberately restricted data are excluded.",
                "sources",
                "PENDING_VALIDATION",
            )
        )
    cards.append(card)

    if user.has_perm("expert.view_ruleset"):
        configuration.append(_assessment_metadata(mode, references))
    setup = _setup_configuration()
    if setup:
        configuration.append(setup)

    actions = []
    if user.has_perm("evacuation.view_evacuationcenter") and user.has_perm(
        "evacuation.add_evacuationcenter"
    ):
        actions.append(_link("evacuation-center-create", "Create center draft"))
        actions.append(_link("center-import", "Import center records"))
    if guidance_allowed and user.has_perm("dss.add_guidanceitem"):
        actions.insert(1, _link("guidance-create", "Create guidance draft"))
    elif flows_allowed and user.has_perm("dss.add_dssflowversion"):
        actions.insert(1, _link("dss-flow-create", "Create Prepare draft"))
    return {
        "mode": mode,
        "mode_label": MODE_LABELS[mode],
        "generated_at": timezone.now(),
        "cards": cards,
        "configuration": configuration,
        "attention": (problems + [row for row in queues if row["count"]])[:5],
        "recent_activity": _activity(user),
        "quick_actions": actions[:3],
        "show_activity": user.has_perm("admin.view_logentry"),
    }
