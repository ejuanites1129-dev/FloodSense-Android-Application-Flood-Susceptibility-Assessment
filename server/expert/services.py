"""Deterministic, database-driven FloodSense inference service."""

from decimal import Decimal
from operator import eq, ge, gt, le, lt
from typing import Any

from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Q
from geography.models import GeographicArea
from provenance import policies

from .models import (
    ExpertRule,
    ExpertRuleCondition,
    RuleSet,
    ScenarioOption,
    SusceptibilityLevel,
)

DEMONSTRATION_WARNING = policies.DEMONSTRATION_WARNING
NON_AUTHORITY_WARNING = policies.NON_AUTHORITY_WARNING

_NUMERIC_COMPARATORS = {
    ExpertRuleCondition.Operator.EQUALS: eq,
    ExpertRuleCondition.Operator.GREATER_THAN: gt,
    ExpertRuleCondition.Operator.GREATER_THAN_OR_EQUAL: ge,
    ExpertRuleCondition.Operator.LESS_THAN: lt,
    ExpertRuleCondition.Operator.LESS_THAN_OR_EQUAL: le,
}


class AssessmentInputError(ValidationError):
    """Raised when a caller selects an unknown, disabled, or ineligible record."""


def evaluate_assessment(
    *,
    area_identifier: int | str,
    intensity_code: str,
    duration_code: str,
    mode: str,
) -> dict[str, Any]:
    """Evaluate one stored scenario without invoking the DSS or persisting a result."""

    normalized_mode = _normalize_mode(mode)
    area = _get_area(area_identifier, normalized_mode)
    intensity = _get_scenario_option(
        code=intensity_code,
        category=ScenarioOption.Category.INTENSITY,
        field_name="intensity_code",
        mode=normalized_mode,
    )
    duration = _get_scenario_option(
        code=duration_code,
        category=ScenarioOption.Category.DURATION,
        field_name="duration_code",
        mode=normalized_mode,
    )

    base_facts: dict[str, str | Decimal | None] = {
        "zone_code": area.code,
        "rainfall_intensity_code": intensity.code,
        "rainfall_intensity_rank": intensity.derived_value,
        "rainfall_duration_code": duration.code,
        "rainfall_duration_hours": duration.derived_value,
    }

    ruleset, ruleset_problem = _select_ruleset(normalized_mode)
    if ruleset is None:
        return _result(
            state="INSUFFICIENT_DATA",
            area=area,
            intensity=intensity,
            duration=duration,
            facts=base_facts,
            ruleset=None,
            mode=normalized_mode,
            summary=ruleset_problem,
        )

    area_facts, conflicting_fact_keys = _assemble_area_facts(area, normalized_mode)
    # Request-derived facts stay authoritative if an area-fact key collides with one.
    facts = {**area_facts, **base_facts}

    missing_facts: list[str] = []
    if intensity.derived_value is None:
        missing_facts.append("rainfall_intensity_rank")
    if duration.derived_value is None:
        missing_facts.append("rainfall_duration_hours")
    if (
        "zone_baseline_rank" in conflicting_fact_keys
        or not isinstance(area_facts.get("zone_baseline_rank"), Decimal)
    ):
        missing_facts.append("zone_baseline_rank")
    if missing_facts:
        missing_list = ", ".join(missing_facts)
        return _result(
            state="INSUFFICIENT_DATA",
            area=area,
            intensity=intensity,
            duration=duration,
            facts=facts,
            ruleset=ruleset,
            mode=normalized_mode,
            summary=f"Required stored facts are unavailable or ambiguous: {missing_list}.",
        )

    matching_rules = [
        rule
        for rule in _eligible_rules(ruleset, area, normalized_mode)
        if _rule_matches(
            rule=rule,
            intensity=intensity,
            duration=duration,
            facts=facts,
            area_facts=area_facts,
        )
    ]
    if not matching_rules:
        return _result(
            state="INSUFFICIENT_DATA",
            area=area,
            intensity=intensity,
            duration=duration,
            facts=facts,
            ruleset=ruleset,
            mode=normalized_mode,
            summary="No eligible stored rule matched every enabled condition.",
        )

    top_rank = max(_rule_rank(rule, area) for rule in matching_rules)
    top_rules = sorted(
        (rule for rule in matching_rules if _rule_rank(rule, area) == top_rank),
        key=lambda rule: rule.code,
    )
    conclusion_codes = {rule.result_level.code for rule in top_rules}
    rule_codes = [rule.code for rule in top_rules]

    if len(conclusion_codes) > 1:
        return _result(
            state="UNCERTAIN",
            area=area,
            intensity=intensity,
            duration=duration,
            facts=facts,
            ruleset=ruleset,
            mode=normalized_mode,
            matched_rules=top_rules,
            summary=(
                "Equally specific, equally prioritized rules conflict: "
                f"{', '.join(rule_codes)}."
            ),
        )

    level = top_rules[0].result_level
    return _result(
        state="CLASSIFIED",
        area=area,
        intensity=intensity,
        duration=duration,
        facts=facts,
        ruleset=ruleset,
        mode=normalized_mode,
        matched_rules=top_rules,
        level=level,
        summary=(
            f"Stored rule{'s' if len(top_rules) > 1 else ''} "
            f"{', '.join(rule_codes)} matched all enabled conditions."
        ),
    )


def evaluate_map_scenario(
    *,
    intensity_code: str,
    duration_code: str,
    mode: str,
) -> dict[str, Any]:
    """Evaluate every eligible area through the existing inference service."""

    normalized_mode = _normalize_mode(mode)
    intensity = _get_scenario_option(
        code=intensity_code,
        category=ScenarioOption.Category.INTENSITY,
        field_name="intensity_code",
        mode=normalized_mode,
    )
    duration = _get_scenario_option(
        code=duration_code,
        category=ScenarioOption.Category.DURATION,
        field_name="duration_code",
        mode=normalized_mode,
    )

    areas = GeographicArea.objects.select_related("source").filter(is_enabled=True)
    if normalized_mode == policies.DEMONSTRATION_MODE:
        areas = areas.filter(area_type=GeographicArea.AreaType.DEMO_ZONE)
    areas = policies.permitted_records(areas, normalized_mode).order_by("name", "id")

    results = []
    for area in areas:
        assessment = evaluate_assessment(
            area_identifier=area.id,
            intensity_code=intensity.code,
            duration_code=duration.code,
            mode=normalized_mode,
        )
        results.append(
            {
                "area": assessment["area"],
                "assessment_state": assessment["assessment_state"],
                "susceptibility": assessment["susceptibility"],
                "matched_rule_codes": assessment["matched_rule_codes"],
                "ruleset": assessment["ruleset"],
                "summary": assessment["explanation"]["summary"],
            }
        )

    return {
        "scenario": {
            "rainfall_intensity_code": intensity.code,
            "rainfall_duration_code": duration.code,
        },
        "results": results,
        "operating_mode": normalized_mode,
        "data_status": policies.data_status_for_mode(normalized_mode),
        "warnings": policies.warnings_for_mode(normalized_mode),
    }


def _normalize_mode(mode: str) -> str:
    try:
        return policies.normalize_operating_mode(mode)
    except ValueError:
        valid_modes = {value for value, _label in RuleSet.Mode.choices}
        raise AssessmentInputError(
            {"mode": f"Choose one of: {', '.join(sorted(valid_modes))}."}
        ) from None


def _get_area(area_identifier: int | str, mode: str) -> GeographicArea:
    lookup = {"pk": area_identifier} if isinstance(area_identifier, int) else {
        "code": area_identifier
    }
    try:
        area = GeographicArea.objects.select_related("source").get(**lookup)
    except GeographicArea.DoesNotExist:
        raise AssessmentInputError(
            {"area_identifier": "The selected geographic area does not exist."}
        ) from None

    if not area.is_enabled:
        raise AssessmentInputError(
            {"area_identifier": "The selected geographic area is disabled."}
        )
    if (
        mode == RuleSet.Mode.DEMONSTRATION
        and area.area_type != GeographicArea.AreaType.DEMO_ZONE
    ):
        raise AssessmentInputError(
            {
                "area_identifier": (
                    "Demonstration assessments require a neutral demonstration zone."
                )
            }
        )
    if not policies.record_is_permitted(area, mode):
        raise AssessmentInputError(
            {"area_identifier": "The selected geographic area is not permitted in this mode."}
        )
    return area


def _get_scenario_option(
    *,
    code: str,
    category: str,
    field_name: str,
    mode: str,
) -> ScenarioOption:
    try:
        option = ScenarioOption.objects.select_related("source").get(code=code)
    except ScenarioOption.DoesNotExist:
        raise AssessmentInputError(
            {field_name: "The selected scenario option does not exist."}
        ) from None

    if option.category != category:
        raise AssessmentInputError(
            {field_name: "The selected scenario option has the wrong category."}
        )
    if not option.is_enabled:
        raise AssessmentInputError({field_name: "The selected scenario option is disabled."})
    if not policies.record_is_permitted(option, mode):
        raise AssessmentInputError(
            {field_name: "The selected scenario option is not permitted in this mode."}
        )
    return option


def _select_ruleset(mode: str) -> tuple[RuleSet | None, str]:
    active_rulesets = list(
        RuleSet.objects.select_related("source").filter(mode=mode, is_active=True)
    )
    usable_rulesets = [
        ruleset
        for ruleset in active_rulesets
        if policies.record_is_permitted(ruleset, mode)
    ]
    if len(usable_rulesets) == 1:
        return usable_rulesets[0], ""
    if not active_rulesets:
        return None, "No active ruleset is configured for the requested mode."
    if not usable_rulesets:
        return None, "The active ruleset is not permitted for the requested mode."
    return None, "Multiple usable active rulesets are configured for the requested mode."


def _assemble_area_facts(
    area: GeographicArea,
    mode: str,
) -> tuple[dict[str, str | Decimal], set[str]]:
    values: dict[str, str | Decimal] = {}
    conflicting_keys: set[str] = set()
    area_fact_records = area.facts.select_related("source").filter(is_enabled=True)

    for area_fact in area_fact_records:
        if not policies.record_is_permitted(area_fact, mode):
            continue
        value: str | Decimal = (
            area_fact.numeric_value
            if area_fact.numeric_value is not None
            else area_fact.text_value
        )
        existing = values.get(area_fact.fact_key)
        if existing is not None and existing != value:
            conflicting_keys.add(area_fact.fact_key)
            values.pop(area_fact.fact_key, None)
        elif area_fact.fact_key not in conflicting_keys:
            values[area_fact.fact_key] = value

    return values, conflicting_keys


def _eligible_rules(
    ruleset: RuleSet,
    area: GeographicArea,
    mode: str,
) -> list[ExpertRule]:
    enabled_conditions = ExpertRuleCondition.objects.filter(is_enabled=True).select_related(
        "scenario_option"
    )
    candidate_rules = (
        ExpertRule.objects.filter(ruleset=ruleset, is_enabled=True)
        .filter(Q(geographic_scope__isnull=True) | Q(geographic_scope=area))
        .select_related(
            "source",
            "geographic_scope",
            "result_level",
            "result_level__source",
        )
        .prefetch_related(
            Prefetch(
                "conditions",
                queryset=enabled_conditions,
                to_attr="enabled_conditions_for_inference",
            )
        )
    )
    return [
        rule
        for rule in candidate_rules
        if policies.record_is_permitted(rule, mode)
        and rule.result_level.is_enabled
        and policies.record_is_permitted(rule.result_level, mode)
    ]


def _rule_matches(
    *,
    rule: ExpertRule,
    intensity: ScenarioOption,
    duration: ScenarioOption,
    facts: dict[str, str | Decimal | None],
    area_facts: dict[str, str | Decimal],
) -> bool:
    conditions = rule.enabled_conditions_for_inference
    if not conditions:
        return False
    return all(
        _condition_matches(
            condition=condition,
            intensity=intensity,
            duration=duration,
            facts=facts,
            area_facts=area_facts,
        )
        for condition in conditions
    )


def _condition_matches(
    *,
    condition: ExpertRuleCondition,
    intensity: ScenarioOption,
    duration: ScenarioOption,
    facts: dict[str, str | Decimal | None],
    area_facts: dict[str, str | Decimal],
) -> bool:
    condition_type = condition.condition_type
    if condition_type == ExpertRuleCondition.ConditionType.INTENSITY_OPTION:
        return (
            condition.operator == ExpertRuleCondition.Operator.EQUALS
            and condition.scenario_option_id == intensity.id
        )
    if condition_type == ExpertRuleCondition.ConditionType.DURATION_OPTION:
        return (
            condition.operator == ExpertRuleCondition.Operator.EQUALS
            and condition.scenario_option_id == duration.id
        )
    if condition_type == ExpertRuleCondition.ConditionType.AREA_FACT_TEXT:
        actual_text = area_facts.get(condition.fact_key)
        return (
            condition.operator == ExpertRuleCondition.Operator.EQUALS
            and isinstance(actual_text, str)
            and actual_text == condition.expected_text
        )
    if condition_type == ExpertRuleCondition.ConditionType.AREA_FACT_NUMBER:
        return _numeric_condition_matches(
            area_facts.get(condition.fact_key),
            condition.expected_number,
            condition.operator,
        )
    if condition_type == ExpertRuleCondition.ConditionType.INTENSITY_RANK:
        return _numeric_condition_matches(
            facts.get("rainfall_intensity_rank"),
            condition.expected_number,
            condition.operator,
        )
    if condition_type == ExpertRuleCondition.ConditionType.DURATION_HOURS:
        return _numeric_condition_matches(
            facts.get("rainfall_duration_hours"),
            condition.expected_number,
            condition.operator,
        )
    return False


def _numeric_condition_matches(
    actual: str | Decimal | None,
    expected: Decimal | None,
    operator_code: str,
) -> bool:
    comparator = _NUMERIC_COMPARATORS.get(operator_code)
    if not isinstance(actual, Decimal) or expected is None or comparator is None:
        return False
    return comparator(actual, expected)


def _rule_rank(rule: ExpertRule, area: GeographicArea) -> tuple[int, int]:
    geographic_specificity = int(rule.geographic_scope_id == area.id)
    return geographic_specificity, rule.priority


def _result(
    *,
    state: str,
    area: GeographicArea,
    intensity: ScenarioOption,
    duration: ScenarioOption,
    facts: dict[str, str | Decimal | None],
    ruleset: RuleSet | None,
    mode: str,
    summary: str,
    matched_rules: list[ExpertRule] | None = None,
    level: SusceptibilityLevel | None = None,
) -> dict[str, Any]:
    matched_rules = matched_rules or []
    rule_codes = [rule.code for rule in matched_rules]
    warnings = policies.warnings_for_mode(mode)
    serialized_facts = {key: _serialize_fact(value) for key, value in facts.items()}
    facts_used = [f"{key}={value}" for key, value in serialized_facts.items()]
    ruleset_payload = (
        {"name": ruleset.name, "version": ruleset.version} if ruleset else None
    )
    rationale = [rule.rationale for rule in matched_rules]
    explanation_parts = [summary]
    if rationale:
        explanation_parts.append(f"Stored rationale: {' | '.join(rationale)}")
    explanation_parts.append(f"Facts used: {', '.join(facts_used)}.")
    human_readable_summary = " ".join(explanation_parts)

    return {
        "assessment_state": state,
        "susceptibility": (
            {
                "code": level.code,
                "label": level.label,
                "map_color": level.map_color,
            }
            if level is not None
            else None
        ),
        "area": {"id": area.id, "code": area.code, "name": area.name},
        "scenario": {
            "rainfall_intensity_code": intensity.code,
            "rainfall_duration_code": duration.code,
        },
        "facts": serialized_facts,
        "matched_rule_codes": rule_codes,
        "explanation": {
            "summary": human_readable_summary,
            "matched_rule_codes": rule_codes,
            "facts_used": facts_used,
            "rule_rationales": rationale,
            "ruleset": (
                f"{ruleset.name} v{ruleset.version}" if ruleset is not None else None
            ),
            "warnings": warnings,
        },
        "ruleset": ruleset_payload,
        "operating_mode": mode,
        "data_status": policies.data_status_for_mode(mode),
        "warnings": warnings,
    }


def _serialize_fact(value: str | Decimal | None) -> str | int | float | None:
    if not isinstance(value, Decimal):
        return value
    if value == value.to_integral_value():
        return int(value)
    return float(value)
