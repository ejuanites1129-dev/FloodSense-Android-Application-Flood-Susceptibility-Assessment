"""Create the repeatable local data required by the FloodSense demonstration."""

from datetime import date
from decimal import Decimal

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from dss.models import (
    DSSFlowVersion,
    DSSOption,
    DSSOutcome,
    DSSQuestion,
    GuidanceItem,
)
from dss.services import validate_dss_flow
from expert.models import (
    ExpertRule,
    ExpertRuleCondition,
    RuleSet,
    ScenarioOption,
    SusceptibilityLevel,
)
from geography.models import AreaFact, GeographicArea
from provenance.models import DataSource, PublicationStatus
from provenance.policies import DEMONSTRATION_WARNING

SOURCE_NAME = "DEMONSTRATION DATA—NOT OFFICIAL"
RULESET_NAME = "Demonstration Rules"
RULESET_VERSION = "1.0"
DSS_FLOW_CODE = "preparedness"
DSS_FLOW_VERSION = "presentation-1"
DSS_FLOW_TITLE = "Household Preparedness Check"
DSS_FLOW_EFFECTIVE_DATE = date(2026, 9, 24)
DSS_OUTCOME_WARNING = (
    "Use this as a planning checklist. Follow PAGASA, Bacoor DRRMO, emergency "
    "services, and other authorized authorities for official instructions."
)

LEVELS = (
    ("LOW", "Low", 1, "#2E9E5B"),
    ("MODERATE", "Moderate", 2, "#E8B923"),
    ("HIGH", "High", 3, "#E2691B"),
    ("VERY_HIGH", "Very High", 4, "#C0392B"),
)

INTENSITIES = (
    ("DEMO_LIGHT", "Light", 1),
    ("DEMO_MODERATE", "Moderate", 2),
    ("DEMO_HEAVY", "Heavy", 3),
    ("DEMO_INTENSE", "Intense", 4),
    ("DEMO_TORRENTIAL", "Torrential", 5),
)

DURATIONS = (
    ("DEMO_1_HOUR", "1 hour", 1),
    ("DEMO_3_HOURS", "3 hours", 3),
    ("DEMO_6_HOURS", "6 hours", 6),
    ("DEMO_12_HOURS", "12 hours", 12),
    ("DEMO_24_HOURS", "24 hours", 24),
)

# These rectangles are synthetic display geometry placed inside Bacoor so the
# mobile client can demonstrate scenario overlays on one map. They remain
# separate DEMO_ZONE records and are not barangay or MGB susceptibility data.
ZONES = (
    ("DEMO_ZONE_A", "Demo Zone A", 1, 120.932, 14.447, 0.008),
    ("DEMO_ZONE_B", "Demo Zone B", 2, 120.963, 14.438, 0.006),
    ("DEMO_ZONE_C", "Demo Zone C", 3, 120.961, 14.406, 0.006),
    ("DEMO_ZONE_D", "Demo Zone D", 4, 120.985, 14.376, 0.008),
)

RULES = (
    ("DEMO-RULE-100", "LOW", 100, 1, 1, 1),
    ("DEMO-RULE-200", "MODERATE", 200, 2, 1, 1),
    ("DEMO-RULE-300", "HIGH", 300, 3, 3, 2),
    ("DEMO-RULE-400", "VERY_HIGH", 400, 4, 6, 3),
)

GUIDANCE = (
    (
        "LOW",
        "Review basic preparedness supplies",
        "Maintain basic readiness and continue monitoring authorized official information.",
    ),
    (
        "MODERATE",
        "Review the household preparedness plan",
        "Review supplies, household plans, and the needs of vulnerable household members.",
    ),
    (
        "HIGH",
        "Prepare essential items",
        (
            "Prepare essential items and documents and monitor authorized official "
            "instructions closely."
        ),
    ),
    (
        "VERY_HIGH",
        "Prioritize readiness",
        "Be ready to act promptly and follow instructions issued by authorized authorities.",
    ),
)

DSS_QUESTIONS = (
    (
        "support-needs",
        "Does anyone in your household need additional assistance during preparation?",
        (
            "Consider children, older adults, persons with disabilities, and anyone "
            "who may need help with communication, medication, or mobility."
        ),
        10,
        True,
    ),
    (
        "support-plan",
        "Is a trusted person assigned to provide that assistance?",
        "Choose the answer that best matches your household plan right now.",
        20,
        False,
    ),
    (
        "essential-items",
        "Are essential supplies and important documents ready and accessible?",
        (
            "Think about water, food, medicines, lighting, communication, identification, "
            "and important records appropriate to your household."
        ),
        30,
        False,
    ),
    (
        "communication-plan",
        "Does your household have a communication and meeting plan?",
        (
            "A simple plan can identify who to contact, where household members should "
            "meet, and how everyone will receive official information."
        ),
        40,
        False,
    ),
)

DSS_OUTCOMES = (
    (
        "arrange-support",
        "Arrange household support",
        (
            "Identify a trusted person who can assist household members with mobility, "
            "communication, medicines, or other essential needs. Share the plan and keep "
            "important contact details accessible."
        ),
        "MODERATE",
    ),
    (
        "prepare-essentials",
        "Prepare essential items",
        (
            "Gather the supplies, medicines, identification, important documents, and "
            "communication items your household may need. Keep them together in an "
            "accessible place and review them regularly."
        ),
        "HIGH",
    ),
    (
        "make-communication-plan",
        "Create a household communication plan",
        (
            "Agree on important contacts and a meeting point, keep phones or other "
            "communication devices ready, and make sure every household member "
            "understands the plan."
        ),
        "MODERATE",
    ),
    (
        "maintain-readiness",
        "Maintain household readiness",
        (
            "Keep essential items accessible, review the needs of every household member, "
            "and continue checking information from authorized official sources."
        ),
        "LOW",
    ),
)

DSS_OPTIONS = (
    (
        "support-needs",
        "yes",
        "Yes",
        "Continue to check whether support has been arranged.",
        "question",
        "support-plan",
        10,
    ),
    (
        "support-needs",
        "no",
        "No",
        "Continue with the household readiness checklist.",
        "question",
        "essential-items",
        20,
    ),
    (
        "support-plan",
        "yes",
        "Yes, support is arranged",
        "Continue with the household readiness checklist.",
        "question",
        "essential-items",
        10,
    ),
    (
        "support-plan",
        "no",
        "No, support still needs to be arranged",
        "Show the most immediate preparedness action.",
        "outcome",
        "arrange-support",
        20,
    ),
    (
        "essential-items",
        "yes",
        "Yes, they are ready",
        "Continue to the household communication plan.",
        "question",
        "communication-plan",
        10,
    ),
    (
        "essential-items",
        "no",
        "No, some items are not ready",
        "Show the most immediate preparedness action.",
        "outcome",
        "prepare-essentials",
        20,
    ),
    (
        "communication-plan",
        "yes",
        "Yes, the plan is understood",
        "Review how to maintain household readiness.",
        "outcome",
        "maintain-readiness",
        10,
    ),
    (
        "communication-plan",
        "no",
        "No, a plan is still needed",
        "Show the most immediate preparedness action.",
        "outcome",
        "make-communication-plan",
        20,
    ),
)


class Command(BaseCommand):
    help = (
        "Create or refresh clearly labeled fictional demonstration data and the "
        "pending-validation Bacoor administrative reference layer."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        source = self._source()
        levels = self._levels(source)
        self._scenario_options(source)
        areas = self._areas(source)
        ruleset = self._ruleset(source)
        self._rules(source, levels, ruleset)
        guidance = self._guidance(source, levels)
        self._structured_dss_flow(source, levels, guidance)

        # Keep the neutral administrative reference layer reproducible for every
        # teammate without duplicating its validation and ownership safeguards.
        call_command("import_bacoor_boundaries", stdout=self.stdout)

        self.stdout.write(self.style.WARNING(DEMONSTRATION_WARNING))
        self.stdout.write(
            self.style.SUCCESS(
                f"Prepared {len(areas)} fictional zones, the demonstration knowledge "
                "base, the presentation preparedness flow, and the Bacoor "
                "administrative reference layer."
            )
        )

    def _source(self) -> DataSource:
        matches = list(DataSource.objects.filter(name=SOURCE_NAME).order_by("id"))
        if len(matches) > 1:
            raise CommandError(f"Multiple data sources use the reserved name {SOURCE_NAME!r}.")
        if matches:
            source = matches[0]
            if (
                source.source_type != DataSource.SourceType.DEMONSTRATION
                or source.status != PublicationStatus.DEMONSTRATION
            ):
                raise CommandError(
                    "The reserved demonstration source name belongs to a non-demonstration record."
                )
        else:
            source = DataSource(name=SOURCE_NAME)

        source.organization = "FloodSense research prototype"
        source.source_type = DataSource.SourceType.DEMONSTRATION
        source.coverage_description = (
            "Four synthetic scenario sectors inside the Bacoor map extent, used only "
            "for the FloodSense demonstration."
        )
        source.permitted_use = "Fictional local development and automated testing only."
        source.status = PublicationStatus.DEMONSTRATION
        source.is_publicly_releasable = False
        source.notes = (
            "Seed-owned scenario data. Sectors are not barangays or MGB polygons; "
            "shapes, ranks, rules, and guidance are not official."
        )
        source.save()
        return source

    def _levels(self, source: DataSource) -> dict[str, SusceptibilityLevel]:
        levels = {}
        for code, label, order, color in LEVELS:
            level = self._demo_record(
                SusceptibilityLevel,
                {"code": code},
                f"susceptibility level {code}",
                source=source,
            )
            level.label = label
            level.display_order = order
            level.map_color = color
            level.definition = f"Fictional {label} classification used only to exercise FloodSense."
            level.source = source
            level.status = PublicationStatus.DEMONSTRATION
            level.is_enabled = True
            level.full_clean()
            level.save()
            levels[code] = level
        return levels

    def _scenario_options(self, source: DataSource) -> None:
        for order, (code, label, value) in enumerate(INTENSITIES, start=1):
            self._save_option(
                source=source,
                code=code,
                label=label,
                value=value,
                order=order,
                category=ScenarioOption.Category.INTENSITY,
                unit="",
            )
        for order, (code, label, value) in enumerate(DURATIONS, start=1):
            self._save_option(
                source=source,
                code=code,
                label=label,
                value=value,
                order=order,
                category=ScenarioOption.Category.DURATION,
                unit="hours",
            )

    def _save_option(
        self,
        *,
        source: DataSource,
        code: str,
        label: str,
        value: int,
        order: int,
        category: str,
        unit: str,
    ) -> None:
        option = self._demo_record(
            ScenarioOption,
            {"code": code},
            f"scenario option {code}",
            source=source,
        )
        option.category = category
        option.label = label
        option.minimum_value = None
        option.maximum_value = None
        option.derived_value = Decimal(value)
        option.unit = unit
        option.source = source
        option.status = PublicationStatus.DEMONSTRATION
        option.display_order = order
        option.is_enabled = True
        option.full_clean()
        option.save()

    def _areas(self, source: DataSource) -> dict[str, GeographicArea]:
        areas = {}
        for code, name, baseline, west, south, size in ZONES:
            area = self._demo_record(
                GeographicArea,
                {"code": code},
                f"geographic area {code}",
                source=source,
            )
            polygon = Polygon(
                (
                    (west, south),
                    (west, south + size),
                    (west + size, south + size),
                    (west + size, south),
                    (west, south),
                ),
                srid=4326,
            )
            area.name = name
            area.area_type = GeographicArea.AreaType.DEMO_ZONE
            area.geometry = MultiPolygon(polygon, srid=4326)
            area.source = source
            area.status = PublicationStatus.DEMONSTRATION
            area.is_enabled = True
            area.full_clean()
            area.save()
            self._baseline_fact(area, source, baseline)
            areas[code] = area
        return areas

    def _baseline_fact(
        self,
        area: GeographicArea,
        source: DataSource,
        baseline: int,
    ) -> None:
        facts = list(
            AreaFact.objects.filter(
                area=area,
                fact_key="zone_baseline_rank",
                source=source,
            ).order_by("id")
        )
        if len(facts) > 1:
            raise CommandError(f"Multiple seed-owned baseline facts exist for {area.code}.")
        fact = facts[0] if facts else AreaFact(area=area, fact_key="zone_baseline_rank")
        fact.text_value = ""
        fact.numeric_value = Decimal(baseline)
        fact.unit = "demonstration rank"
        fact.source = source
        fact.status = PublicationStatus.DEMONSTRATION
        fact.is_enabled = True
        fact.full_clean()
        fact.save()

    def _ruleset(self, source: DataSource) -> RuleSet:
        ruleset = self._demo_record(
            RuleSet,
            {"name": RULESET_NAME, "version": RULESET_VERSION},
            f"ruleset {RULESET_NAME} v{RULESET_VERSION}",
            source=source,
        )
        competing = RuleSet.objects.filter(
            mode=RuleSet.Mode.DEMONSTRATION,
            is_active=True,
        )
        if ruleset.pk:
            competing = competing.exclude(pk=ruleset.pk)
        if competing.exists():
            raise CommandError(
                "Another demonstration ruleset is active. Disable it explicitly before seeding."
            )
        ruleset.mode = RuleSet.Mode.DEMONSTRATION
        ruleset.source = source
        ruleset.status = PublicationStatus.DEMONSTRATION
        ruleset.is_active = True
        ruleset.change_summary = (
            "Fictional Day 6 rules for repeatable map and inference demonstrations."
        )
        ruleset.full_clean()
        ruleset.save()
        return ruleset

    def _rules(
        self,
        source: DataSource,
        levels: dict[str, SusceptibilityLevel],
        ruleset: RuleSet,
    ) -> None:
        reserved_codes = {values[0] for values in RULES}
        unexpected_codes = list(
            ruleset.rules.exclude(code__in=reserved_codes).values_list(
                "code",
                flat=True,
            )
        )
        if unexpected_codes:
            raise CommandError(
                "The reserved demonstration ruleset contains non-seed rules: "
                f"{', '.join(sorted(unexpected_codes))}."
            )
        for code, level_code, priority, intensity, duration, baseline in RULES:
            matches = list(ruleset.rules.filter(code=code).order_by("id"))
            if len(matches) > 1:
                raise CommandError(f"Multiple rules use reserved code {code}.")
            rule = matches[0] if matches else ExpertRule(code=code, ruleset=ruleset)
            if rule.pk:
                self._require_seed_owned(rule, f"expert rule {code}", source)
            rule.geographic_scope = None
            rule.result_level = levels[level_code]
            rule.priority = priority
            rule.rationale = (
                f"Fictional demonstration rule {code} matched its stored intensity, "
                "duration, and zone-baseline conditions."
            )
            rule.source = source
            rule.status = PublicationStatus.DEMONSTRATION
            rule.is_enabled = True
            rule.full_clean()
            rule.save()
            rule.conditions.all().delete()
            condition_values = (
                (ExpertRuleCondition.ConditionType.INTENSITY_RANK, "", intensity),
                (ExpertRuleCondition.ConditionType.DURATION_HOURS, "", duration),
                (
                    ExpertRuleCondition.ConditionType.AREA_FACT_NUMBER,
                    "zone_baseline_rank",
                    baseline,
                ),
            )
            for order, (condition_type, fact_key, expected) in enumerate(
                condition_values,
                start=1,
            ):
                condition = ExpertRuleCondition(
                    rule=rule,
                    condition_type=condition_type,
                    operator=ExpertRuleCondition.Operator.GREATER_THAN_OR_EQUAL,
                    fact_key=fact_key,
                    expected_number=Decimal(expected),
                    display_order=order,
                    is_enabled=True,
                )
                condition.full_clean()
                condition.save()

    def _guidance(
        self,
        source: DataSource,
        levels: dict[str, SusceptibilityLevel],
    ) -> dict[str, GuidanceItem]:
        guidance = {}
        for order, (level_code, title, instruction) in enumerate(GUIDANCE, start=1):
            matches = list(
                GuidanceItem.objects.filter(
                    source=source,
                    susceptibility_level=levels[level_code],
                ).order_by("id")
            )
            if len(matches) > 1:
                raise CommandError(f"Multiple seed-owned guidance rows exist for {level_code}.")
            item = matches[0] if matches else GuidanceItem(title=title)
            item.susceptibility_level = levels[level_code]
            item.title = title
            item.instruction = instruction
            item.category = GuidanceItem.Category.PREPARE
            item.display_order = order * 10
            item.source = source
            item.attribution = "FloodSense fictional demonstration content"
            item.status = PublicationStatus.DEMONSTRATION
            item.workflow_status = GuidanceItem.WorkflowStatus.PUBLISHED
            item.is_enabled = True
            item.full_clean()
            item.save()
            guidance[level_code] = item
        return guidance

    def _structured_dss_flow(
        self,
        source: DataSource,
        levels: dict[str, SusceptibilityLevel],
        guidance: dict[str, GuidanceItem],
    ) -> DSSFlowVersion:
        matches = list(
            DSSFlowVersion.objects.filter(
                code=DSS_FLOW_CODE,
                version=DSS_FLOW_VERSION,
            ).select_related("source")
        )
        if len(matches) > 1:
            raise CommandError("Multiple flows use the reserved preparedness identity.")
        if matches:
            flow = matches[0]
            self._validate_existing_dss_flow(flow, source, levels)
            return flow

        competing = DSSFlowVersion.objects.filter(
            code=DSS_FLOW_CODE,
            operating_mode=DSSFlowVersion.OperatingMode.DEMONSTRATION,
            workflow_status=DSSFlowVersion.WorkflowStatus.PUBLISHED,
        )
        if competing.exists():
            raise CommandError(
                "Another demonstration preparedness flow is published. Retire it "
                "explicitly before seeding this presentation flow."
            )

        flow = DSSFlowVersion(
            code=DSS_FLOW_CODE,
            title=DSS_FLOW_TITLE,
            version=DSS_FLOW_VERSION,
            operating_mode=DSSFlowVersion.OperatingMode.DEMONSTRATION,
            workflow_status=DSSFlowVersion.WorkflowStatus.DRAFT,
            source=source,
            data_status=PublicationStatus.DEMONSTRATION,
            effective_date=DSS_FLOW_EFFECTIVE_DATE,
        )
        flow.full_clean()
        flow.save()
        flow.susceptibility_levels.set(levels.values())

        outcomes = {}
        for code, title, instruction, guidance_level in DSS_OUTCOMES:
            outcome = DSSOutcome(
                flow=flow,
                code=code,
                title=title,
                instruction=instruction,
                category=GuidanceItem.Category.PREPARE,
                source=source,
                warning=DSS_OUTCOME_WARNING,
                guidance_item=guidance[guidance_level],
            )
            outcome.full_clean()
            outcome.save()
            outcomes[code] = outcome

        questions = {}
        for code, prompt, explanation, order, is_start in DSS_QUESTIONS:
            question = DSSQuestion(
                flow=flow,
                code=code,
                prompt=prompt,
                explanatory_text=explanation,
                display_order=order,
                is_start=is_start,
            )
            question.full_clean()
            question.save()
            questions[code] = question

        for (
            question_code,
            code,
            label,
            supporting_text,
            destination_kind,
            destination_code,
            order,
        ) in DSS_OPTIONS:
            option = DSSOption(
                question=questions[question_code],
                code=code,
                label=label,
                supporting_text=supporting_text,
                next_question=(
                    questions[destination_code]
                    if destination_kind == "question"
                    else None
                ),
                outcome=(
                    outcomes[destination_code]
                    if destination_kind == "outcome"
                    else None
                ),
                display_order=order,
            )
            option.full_clean()
            option.save()

        validate_dss_flow(flow)
        flow.workflow_status = DSSFlowVersion.WorkflowStatus.PUBLISHED
        flow.published_at = timezone.now()
        flow.full_clean()
        flow.save(update_fields=("workflow_status", "published_at", "updated_at"))
        return flow

    def _validate_existing_dss_flow(
        self,
        flow: DSSFlowVersion,
        source: DataSource,
        levels: dict[str, SusceptibilityLevel],
    ) -> None:
        expected_level_codes = set(levels)
        actual_level_codes = set(
            flow.susceptibility_levels.values_list("code", flat=True)
        )
        expected_question_codes = {values[0] for values in DSS_QUESTIONS}
        actual_question_codes = set(flow.questions.values_list("code", flat=True))
        expected_outcome_codes = {values[0] for values in DSS_OUTCOMES}
        actual_outcome_codes = set(flow.outcomes.values_list("code", flat=True))
        expected_option_count = len(DSS_OPTIONS)
        actual_option_count = DSSOption.objects.filter(question__flow=flow).count()
        if (
            flow.source_id != source.id
            or flow.title != DSS_FLOW_TITLE
            or flow.operating_mode != DSSFlowVersion.OperatingMode.DEMONSTRATION
            or flow.data_status != PublicationStatus.DEMONSTRATION
            or flow.workflow_status != DSSFlowVersion.WorkflowStatus.PUBLISHED
            or flow.effective_date != DSS_FLOW_EFFECTIVE_DATE
            or actual_level_codes != expected_level_codes
            or actual_question_codes != expected_question_codes
            or actual_outcome_codes != expected_outcome_codes
            or actual_option_count != expected_option_count
        ):
            raise CommandError(
                "The reserved published preparedness flow differs from the seed-owned "
                "presentation version. Published flow history will not be overwritten."
            )
        validate_dss_flow(flow)

    def _demo_record(
        self,
        model,
        lookup: dict,
        label: str,
        *,
        source: DataSource,
    ):
        matches = list(model.objects.filter(**lookup).select_related("source"))
        if len(matches) > 1:
            raise CommandError(f"Multiple records use the reserved {label} identity.")
        if matches:
            self._require_seed_owned(matches[0], label, source)
            return matches[0]
        return model(**lookup)

    def _require_seed_owned(
        self,
        record,
        label: str,
        source: DataSource,
    ) -> None:
        if (
            record.status != PublicationStatus.DEMONSTRATION
            or record.source.status != PublicationStatus.DEMONSTRATION
            or record.source.source_type != DataSource.SourceType.DEMONSTRATION
            or record.source_id != source.id
        ):
            raise CommandError(
                f"The reserved {label} identity is not owned by this demonstration seed."
            )
