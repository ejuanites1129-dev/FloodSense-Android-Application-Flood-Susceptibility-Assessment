"""Database-driven preparedness-guidance selection for FloodSense."""

from copy import deepcopy
from typing import Any

from django.core.exceptions import ValidationError
from expert.models import SusceptibilityLevel
from provenance.policies import normalize_operating_mode, permitted_records

from .models import DSSFlowVersion, DSSOption, DSSQuestion, GuidanceItem


class GuidanceSelectionError(ValidationError):
    """Raised when a requested guidance classification is invalid or ineligible."""


def select_guidance(assessment_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Select guidance for a completed assessment without changing that assessment."""

    assessment_snapshot = deepcopy(assessment_result)
    if assessment_result.get("assessment_state") != "CLASSIFIED":
        return []

    susceptibility = assessment_result.get("susceptibility") or {}
    scenario = assessment_result.get("scenario") or {}
    susceptibility_code = susceptibility.get("code")
    mode = assessment_result.get("operating_mode")
    if not all(
        (
            susceptibility_code,
            mode,
            scenario.get("rainfall_intensity_code"),
            scenario.get("rainfall_duration_code"),
        )
    ):
        return []

    try:
        guidance = select_guidance_for_level(
            susceptibility_code=susceptibility_code,
            mode=mode,
        )
    except GuidanceSelectionError:
        guidance = []
    if assessment_result != assessment_snapshot:
        raise RuntimeError("DSS guidance selection must not modify the assessment result.")
    return guidance


def select_guidance_for_level(
    *,
    susceptibility_code: str,
    mode: str,
) -> list[dict[str, Any]]:
    """Return enabled, mode-permitted guidance in administrator-defined order."""

    try:
        normalized_mode = normalize_operating_mode(mode)
    except ValueError as error:
        raise GuidanceSelectionError({"mode": str(error)}) from None

    levels = permitted_records(
        SusceptibilityLevel.objects.select_related("source").filter(
            code=str(susceptibility_code).strip().upper(),
            is_enabled=True,
        ),
        normalized_mode,
    )
    level = levels.first()
    if level is None:
        raise GuidanceSelectionError(
            {
                "susceptibility_level": (
                    "The selected susceptibility level is unavailable in this mode."
                )
            }
        )

    guidance_items = permitted_records(
        GuidanceItem.objects.select_related("source").filter(
            susceptibility_level=level,
            is_enabled=True,
            workflow_status=GuidanceItem.WorkflowStatus.PUBLISHED,
        ),
        normalized_mode,
    ).order_by("display_order", "id")

    return [_serialize_guidance_item(item) for item in guidance_items]


def _serialize_guidance_item(item: GuidanceItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "instruction": item.instruction,
        "category": item.category,
        "display_order": item.display_order,
        "data_status": item.status,
        "attribution": item.attribution,
        "source": {
            "id": item.source_id,
            "name": item.source.name,
            "organization": item.source.organization,
        },
    }


class DSSFlowValidationError(ValidationError):
    """Raised when a structured DSS graph is incomplete or unsafe to publish."""


def validate_dss_flow(flow: DSSFlowVersion) -> None:
    questions = list(
        flow.questions.prefetch_related("options__next_question", "options__outcome")
    )
    starts = [question for question in questions if question.is_start]
    errors: list[str] = []
    if len(starts) != 1:
        errors.append("A flow must contain exactly one start question.")
    question_ids = {question.pk for question in questions}
    outcome_ids = set(flow.outcomes.values_list("pk", flat=True))
    if not outcome_ids:
        errors.append("A flow must contain at least one outcome.")
    adjacency: dict[int, list[int]] = {question.pk: [] for question in questions}
    reachable_outcomes: set[int] = set()
    for question in questions:
        options = list(question.options.all())
        if not options:
            errors.append(f"Question '{question.code}' has no options.")
        for option in options:
            destinations = int(option.next_question_id is not None) + int(
                option.outcome_id is not None
            )
            if destinations != 1:
                errors.append(
                    f"Option '{question.code}.{option.code}' must have one destination."
                )
            elif option.next_question_id is not None:
                if option.next_question_id not in question_ids:
                    errors.append(
                        f"Option '{question.code}.{option.code}' crosses flow versions."
                    )
                else:
                    adjacency[question.pk].append(option.next_question_id)
            elif option.outcome_id not in outcome_ids:
                errors.append(
                    f"Option '{question.code}.{option.code}' crosses flow versions."
                )

    visited: set[int] = set()
    active: set[int] = set()

    def visit(question_id: int) -> None:
        if question_id in active:
            errors.append("The question graph contains a cycle.")
            return
        if question_id in visited:
            return
        active.add(question_id)
        question = next(item for item in questions if item.pk == question_id)
        for option in question.options.all():
            if option.outcome_id in outcome_ids:
                reachable_outcomes.add(option.outcome_id)
            elif option.next_question_id in question_ids:
                visit(option.next_question_id)
        active.remove(question_id)
        visited.add(question_id)

    if len(starts) == 1:
        visit(starts[0].pk)
        unreachable = [
            question.code for question in questions if question.pk not in visited
        ]
        if unreachable:
            errors.append(f"Unreachable questions: {', '.join(sorted(unreachable))}.")
    if outcome_ids and not reachable_outcomes:
        errors.append("No structured outcome is reachable from the start question.")
    if errors:
        raise DSSFlowValidationError({"flow": errors})


def select_dss_flow(*, susceptibility_code: str, mode: str) -> DSSFlowVersion:
    normalized_mode = normalize_operating_mode(mode)
    expected_status = (
        "DEMONSTRATION" if normalized_mode == "DEMONSTRATION" else "APPROVED"
    )
    flow = (
        DSSFlowVersion.objects.select_related("source")
        .prefetch_related("susceptibility_levels")
        .filter(
            operating_mode=normalized_mode,
            workflow_status=DSSFlowVersion.WorkflowStatus.PUBLISHED,
            data_status=expected_status,
            susceptibility_levels__code=str(susceptibility_code).strip().upper(),
        )
        .first()
    )
    if flow is None:
        raise GuidanceSelectionError(
            {"flow": "No published structured guidance flow is available."}
        )
    source = flow.source
    if normalized_mode == "DEMONSTRATION":
        permitted = (
            source.status == "DEMONSTRATION"
            and source.source_type == "DEMONSTRATION"
        )
    else:
        permitted = (
            source.status == "APPROVED"
            and source.source_type != "DEMONSTRATION"
            and source.is_publicly_releasable
        )
    if not permitted:
        raise GuidanceSelectionError(
            {"flow": "The flow source is not eligible for this operating mode."}
        )
    return flow


def serialize_dss_question(
    flow: DSSFlowVersion, question: DSSQuestion
) -> dict[str, Any]:
    count = flow.questions.count()
    position = list(
        flow.questions.order_by("display_order", "id").values_list("pk", flat=True)
    ).index(question.pk) + 1
    return {
        "kind": "question",
        "flow": _serialize_flow(flow),
        "question": {
            "code": question.code,
            "prompt": question.prompt,
            "explanatory_text": question.explanatory_text,
            "question_type": question.question_type,
            "options": [
                {
                    "code": option.code,
                    "label": option.label,
                    "supporting_text": option.supporting_text,
                }
                for option in question.options.all()
            ],
        },
        "progress": {"position": position, "question_count": count},
    }


def answer_dss_question(
    *, flow: DSSFlowVersion, question_code: str, option_code: str
) -> dict[str, Any]:
    try:
        option = DSSOption.objects.select_related(
            "question", "next_question", "outcome", "outcome__source"
        ).get(
            question__flow=flow,
            question__code=question_code,
            code=option_code,
        )
    except DSSOption.DoesNotExist as error:
        raise GuidanceSelectionError(
            {"option_code": "Choose a valid option for the current question."}
        ) from error
    if option.next_question_id:
        return serialize_dss_question(flow, option.next_question)
    outcome = option.outcome
    return {
        "kind": "outcome",
        "flow": _serialize_flow(flow),
        "outcome": {
            "code": outcome.code,
            "title": outcome.title,
            "instruction": outcome.instruction,
            "category": outcome.category,
            "warning": outcome.warning,
            "source": {
                "id": outcome.source_id,
                "name": outcome.source.name,
                "organization": outcome.source.organization,
            },
        },
    }


def _serialize_flow(flow: DSSFlowVersion) -> dict[str, Any]:
    return {
        "code": flow.code,
        "version": flow.version,
        "title": flow.title,
        "operating_mode": flow.operating_mode,
        "data_status": flow.data_status,
        "source": {
            "id": flow.source_id,
            "name": flow.source.name,
            "organization": flow.source.organization,
        },
        "warning": (
            "This deterministic guidance does not change the susceptibility result "
            "and is not an evacuation order."
        ),
    }
