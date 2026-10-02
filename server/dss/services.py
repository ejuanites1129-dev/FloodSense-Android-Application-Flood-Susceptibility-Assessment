"""Database-driven preparedness-guidance selection for FloodSense."""

from copy import deepcopy
from typing import Any

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from expert.models import SusceptibilityLevel
from provenance.models import DataSource, PublicationStatus
from provenance.policies import normalize_operating_mode, permitted_records, record_is_permitted

from .models import DSSContentBlock, DSSFlowVersion, DSSOption, DSSQuestion, GuidanceItem


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


def _serialize_guidance_item(item: GuidanceItem, *, expanded=False) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "instruction": item.instruction,
        "category": item.category,
        "display_order": item.display_order,
        "data_status": item.status,
        "attribution": item.attribution,
        "source": (
            _serialize_public_source(item.source)
            if expanded
            else {
                "id": item.source_id,
                "name": item.source.name,
                "organization": item.source.organization,
            }
        ),
    }


class DSSFlowValidationError(ValidationError):
    """Raised when a structured DSS graph is incomplete or unsafe to publish."""


def validate_dss_flow(flow: DSSFlowVersion) -> None:
    questions = list(flow.questions.prefetch_related("options__next_question", "options__outcome"))
    starts = [question for question in questions if question.is_start]
    errors: list[str] = []
    try:
        flow.clean_fields()
    except ValidationError as error:
        errors.extend(error.messages)
    if flow.effective_date and flow.expires_on and flow.expires_on < flow.effective_date:
        errors.append("Flow expiry cannot precede its effective date.")
    expected_status = (
        PublicationStatus.DEMONSTRATION
        if flow.operating_mode == DSSFlowVersion.OperatingMode.DEMONSTRATION
        else PublicationStatus.APPROVED
    )
    if flow.data_status != expected_status or not _source_is_eligible(
        flow.source, flow.operating_mode
    ):
        errors.append("The flow status/source is not eligible for its operating mode.")
    levels = list(flow.susceptibility_levels.select_related("source"))
    if not levels:
        errors.append("Select at least one applicable susceptibility level.")
    for level in levels:
        if not level.is_enabled or not record_is_permitted(level, flow.operating_mode):
            errors.append(f"Susceptibility level '{level.code}' is not eligible in this mode.")
    if len(starts) != 1:
        errors.append("A flow must contain exactly one start question.")
    question_ids = {question.pk for question in questions}
    outcome_ids = set(flow.outcomes.values_list("pk", flat=True))
    if not outcome_ids:
        errors.append("A flow must contain at least one outcome.")
    adjacency: dict[int, list[int]] = {question.pk: [] for question in questions}
    reachable_outcomes: set[int] = set()
    for question in questions:
        try:
            question.clean_fields()
        except ValidationError as error:
            errors.extend(error.messages)
        options = list(question.options.all())
        if not options:
            errors.append(f"Question '{question.code}' has no options.")
        for option in options:
            try:
                option.clean_fields()
            except ValidationError as error:
                errors.extend(error.messages)
            destinations = int(option.next_question_id is not None) + int(
                option.outcome_id is not None
            )
            if destinations != 1:
                errors.append(f"Option '{question.code}.{option.code}' must have one destination.")
            elif option.next_question_id is not None:
                if option.next_question_id not in question_ids:
                    errors.append(f"Option '{question.code}.{option.code}' crosses flow versions.")
                else:
                    adjacency[question.pk].append(option.next_question_id)
            elif option.outcome_id not in outcome_ids:
                errors.append(f"Option '{question.code}.{option.code}' crosses flow versions.")

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
        unreachable = [question.code for question in questions if question.pk not in visited]
        if unreachable:
            errors.append(f"Unreachable questions: {', '.join(sorted(unreachable))}.")
    if outcome_ids and not reachable_outcomes:
        errors.append("No structured outcome is reachable from the start question.")
    unreachable_outcomes = outcome_ids - reachable_outcomes
    if unreachable_outcomes:
        names = flow.outcomes.filter(pk__in=unreachable_outcomes).values_list("code", flat=True)
        errors.append(f"Unreachable outcomes: {', '.join(sorted(names))}.")
    for outcome in flow.outcomes.select_related("source", "guidance_item__source"):
        try:
            outcome.clean_fields()
        except ValidationError as error:
            errors.extend(error.messages)
        if outcome.source_id != flow.source_id or not _source_is_eligible(
            outcome.source, flow.operating_mode
        ):
            errors.append(f"Outcome '{outcome.code}' has ineligible provenance.")
        if outcome.guidance_item_id:
            item = outcome.guidance_item
            if (
                item.source_id != outcome.source_id
                or not item.is_enabled
                or item.workflow_status != GuidanceItem.WorkflowStatus.PUBLISHED
                or not record_is_permitted(item, flow.operating_mode)
                or item.susceptibility_level_id not in {level.pk for level in levels}
            ):
                errors.append(f"Outcome '{outcome.code}' links ineligible assessment guidance.")
    for block in flow.content_blocks.select_related("source", "outcome"):
        try:
            block.clean_fields()
        except ValidationError as error:
            errors.extend(error.messages)
        if block.outcome_id and block.outcome_id not in outcome_ids:
            errors.append(f"Content '{block.title}' crosses flow versions.")
        if block.reference_stage and block.audience != DSSContentBlock.Audience.STAFF_ONLY:
            errors.append("Board-stage references must remain staff-only.")
        if block.effective_date and block.expires_on and block.expires_on < block.effective_date:
            errors.append(f"Content '{block.title}' has an invalid effective/expiry range.")
        if block.public_url and not _channel_link_is_verified(block):
            errors.append(f"Content '{block.title}' has an unverified official-channel link.")
        if block.audience != DSSContentBlock.Audience.STAFF_ONLY and (
            block.data_status != expected_status
            or not _source_is_eligible(block.source, flow.operating_mode)
        ):
            errors.append(f"Public content '{block.title}' is not eligible in this mode.")
    if errors:
        raise DSSFlowValidationError({"flow": errors})


def _source_is_eligible(source: DataSource, mode: str) -> bool:
    if mode == DSSFlowVersion.OperatingMode.DEMONSTRATION:
        return (
            source.status == PublicationStatus.DEMONSTRATION
            and source.source_type == DataSource.SourceType.DEMONSTRATION
        )
    return (
        source.status == PublicationStatus.APPROVED
        and source.source_type != DataSource.SourceType.DEMONSTRATION
        and source.is_publicly_releasable
        and source.reviewed_on is not None
        and source.reviewed_on <= timezone.localdate()
    )


def select_dss_flow(
    *, susceptibility_code: str, mode: str, code: str = "preparedness"
) -> DSSFlowVersion:
    try:
        normalized_mode = normalize_operating_mode(mode)
    except ValueError as error:
        raise GuidanceSelectionError({"mode": str(error)}) from None
    expected_status = "DEMONSTRATION" if normalized_mode == "DEMONSTRATION" else "APPROVED"
    try:
        flow = DSSFlowVersion.objects.select_related("source").get(
            code=code,
            operating_mode=normalized_mode,
            workflow_status=DSSFlowVersion.WorkflowStatus.PUBLISHED,
            data_status=expected_status,
        )
    except (DSSFlowVersion.DoesNotExist, DSSFlowVersion.MultipleObjectsReturned) as error:
        raise GuidanceSelectionError(
            {"flow": "No published structured guidance flow is available."}
        ) from error
    today = timezone.localdate()
    if (
        not flow.effective_date
        or flow.effective_date > today
        or (flow.expires_on and flow.expires_on < today)
    ):
        raise GuidanceSelectionError(
            {"flow": "The published flow is not effective or has expired."}
        )
    if not flow.susceptibility_levels.filter(
        code=str(susceptibility_code).strip().upper()
    ).exists():
        raise GuidanceSelectionError({"flow": "No flow applies to this susceptibility level."})
    try:
        validate_dss_flow(flow)
    except ValidationError as error:
        raise GuidanceSelectionError(
            {"flow": "Published guidance is unavailable because its validation is no longer valid."}
        ) from error
    return flow


def serialize_dss_question(flow: DSSFlowVersion, question: DSSQuestion) -> dict[str, Any]:
    count = flow.questions.count()
    position = (
        list(flow.questions.order_by("display_order", "id").values_list("pk", flat=True)).index(
            question.pk
        )
        + 1
    )
    return {
        "contract_version": 2,
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
        "content_blocks": _serialize_content_blocks(flow),
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
        "contract_version": 2,
        "kind": "outcome",
        "flow": _serialize_flow(flow),
        "outcome": {
            "code": outcome.code,
            "title": outcome.title,
            "instruction": outcome.instruction,
            "category": outcome.category,
            "warning": outcome.warning,
            "source": _serialize_public_source(outcome.source),
            "guidance": (
                [_serialize_guidance_item(outcome.guidance_item, expanded=True)]
                if outcome.guidance_item_id
                else []
            ),
        },
        "content_blocks": _serialize_content_blocks(flow, outcome=outcome),
    }


def _serialize_flow(flow: DSSFlowVersion) -> dict[str, Any]:
    return {
        "code": flow.code,
        "version": flow.version,
        "title": flow.title,
        "operating_mode": flow.operating_mode,
        "data_status": flow.data_status,
        "source": _serialize_public_source(flow.source),
        "effective_date": _date(flow.effective_date),
        "reviewed_on": _date(flow.reviewed_on),
        "expires_on": _date(flow.expires_on),
        "source_locator": flow.source_locator,
        "attribution": flow.attribution,
        "limitations": flow.limitations,
        "warning": (
            "This is a hypothetical, scenario-based preparedness assessment. "
            "It is not a current flood warning, forecast, water-level observation, "
            "safety guarantee, or evacuation order. Follow PAGASA, Bacoor DRRMO, "
            "your barangay, and emergency services for official instructions."
        ),
    }


def _date(value):
    return value.isoformat() if value else None


def _serialize_public_source(source: DataSource) -> dict[str, Any]:
    """Explicit whitelist; private interviews, contacts, review identity and notes stay private."""
    return {
        "id": source.pk,
        "name": source.name,
        "organization": source.organization,
        "custodian": source.custodian,
        "version": source.version,
        "date": _date(source.received_or_created_on),
        "reviewed_on": _date(source.reviewed_on),
        "data_status": source.status,
        "limitations": source.limitations,
        "citation_url": (
            source.citation_url
            if source.citation_url.lower().startswith("https://")
            and source.is_publicly_releasable
            and source.reviewed_on
            and source.status == PublicationStatus.APPROVED
            else None
        ),
    }


def _channel_link_is_verified(block: DSSContentBlock) -> bool:
    return (
        block.content_type == DSSContentBlock.ContentType.OFFICIAL_CHANNEL
        and block.public_url.lower().startswith("https://")
        and block.url_verified_on is not None
        and block.url_verified_on <= timezone.localdate()
        and block.source.reviewed_on is not None
        and block.source.reviewed_on <= timezone.localdate()
        and block.source.status == PublicationStatus.APPROVED
        and block.source.is_publicly_releasable
        and block.source.source_type != DataSource.SourceType.DEMONSTRATION
    )


def _serialize_block(block: DSSContentBlock, *, preview=False) -> dict[str, Any]:
    return {
        "id": block.pk,
        "outcome_code": block.outcome.code if block.outcome_id else None,
        "title": block.title,
        "body": block.body,
        "phase": block.phase,
        "content_type": block.content_type,
        "audience": block.audience,
        "display_order": block.display_order,
        "data_status": block.data_status,
        "source": _serialize_public_source(block.source),
        "source_locator": block.source_locator,
        "attribution": block.attribution,
        "limitations": block.limitations,
        "effective_date": _date(block.effective_date),
        "reviewed_on": _date(block.reviewed_on),
        "expires_on": _date(block.expires_on),
        "public_url": block.public_url if _channel_link_is_verified(block) else None,
        "url_verified_on": _date(block.url_verified_on)
        if _channel_link_is_verified(block)
        else None,
        **({"reference_stage": block.reference_stage} if preview else {}),
    }


def _serialize_content_blocks(flow, *, outcome=None, preview=False, include_staff_only=False):
    blocks = flow.content_blocks.select_related("source", "outcome")
    if not include_staff_only:
        blocks = blocks.exclude(audience=DSSContentBlock.Audience.STAFF_ONLY)
    if not preview:
        blocks = (
            blocks.filter(Q(outcome__isnull=True) | Q(outcome=outcome))
            if outcome
            else (blocks.filter(outcome__isnull=True))
        )
        today = timezone.localdate()
        blocks = blocks.filter(
            Q(effective_date__isnull=True) | Q(effective_date__lte=today),
            Q(expires_on__isnull=True) | Q(expires_on__gte=today),
        )
        expected = (
            PublicationStatus.DEMONSTRATION
            if flow.operating_mode == DSSFlowVersion.OperatingMode.DEMONSTRATION
            else PublicationStatus.APPROVED
        )
        blocks = [
            block
            for block in blocks
            if block.data_status == expected
            and _source_is_eligible(block.source, flow.operating_mode)
        ]
    return [_serialize_block(block, preview=preview) for block in blocks]


def serialize_dss_preview(flow, *, include_staff_only=False) -> dict[str, Any]:
    """Staff preview of the actual graph/content contract; never a public selection bypass."""
    questions = []
    for question in flow.questions.prefetch_related("options__next_question", "options__outcome"):
        serialized = serialize_dss_question(flow, question)["question"]
        serialized["display_order"] = question.display_order
        serialized["is_start"] = question.is_start
        serialized["options"] = [
            {
                "code": option.code,
                "label": option.label,
                "supporting_text": option.supporting_text,
                "next_question_code": option.next_question.code
                if option.next_question_id
                else None,
                "outcome_code": option.outcome.code if option.outcome_id else None,
            }
            for option in question.options.all()
        ]
        questions.append(serialized)
    return {
        "contract_version": 2,
        "preview": True,
        "history_persisted": False,
        "flow": _serialize_flow(flow),
        "questions": questions,
        "outcomes": [
            {
                "code": outcome.code,
                "title": outcome.title,
                "instruction": outcome.instruction,
                "category": outcome.category,
                "warning": outcome.warning,
                "source": _serialize_public_source(outcome.source),
                "guidance": (
                    [_serialize_guidance_item(outcome.guidance_item, expanded=True)]
                    if outcome.guidance_item_id
                    else []
                ),
            }
            for outcome in flow.outcomes.select_related("source", "guidance_item__source")
        ],
        "content_blocks": _serialize_content_blocks(
            flow, preview=True, include_staff_only=include_staff_only
        ),
    }
