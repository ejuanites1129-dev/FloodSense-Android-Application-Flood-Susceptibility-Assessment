"""Create the fictional, repeatable data required by the Day 6 demonstration."""

from decimal import Decimal

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from dss.models import GuidanceItem
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

# These rectangles are synthetic display geometry, not Bacoor barangay boundaries.
ZONES = (
    ("DEMO_ZONE_A", "Demo Zone A", 1, 120.000, 14.000),
    ("DEMO_ZONE_B", "Demo Zone B", 2, 120.012, 14.000),
    ("DEMO_ZONE_C", "Demo Zone C", 3, 120.000, 14.012),
    ("DEMO_ZONE_D", "Demo Zone D", 4, 120.012, 14.012),
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


class Command(BaseCommand):
    help = "Create or refresh clearly labeled fictional FloodSense demonstration data."

    @transaction.atomic
    def handle(self, *args, **options):
        source = self._source()
        levels = self._levels(source)
        self._scenario_options(source)
        areas = self._areas(source)
        ruleset = self._ruleset(source)
        self._rules(source, levels, ruleset)
        self._guidance(source, levels)

        self.stdout.write(self.style.WARNING(DEMONSTRATION_WARNING))
        self.stdout.write(
            self.style.SUCCESS(
                f"Prepared {len(areas)} fictional zones and the Day 6 demonstration knowledge base."
            )
        )

    def _source(self) -> DataSource:
        matches = list(DataSource.objects.filter(name=SOURCE_NAME).order_by("id"))
        if len(matches) > 1:
            raise CommandError(
                f"Multiple data sources use the reserved name {SOURCE_NAME!r}."
            )
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
            "Four synthetic map rectangles used only for the FloodSense demonstration."
        )
        source.permitted_use = "Fictional local development and automated testing only."
        source.status = PublicationStatus.DEMONSTRATION
        source.is_publicly_releasable = False
        source.notes = (
            "Seed-owned Day 6 data. Shapes, ranks, rules, and guidance are not official."
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
            level.definition = (
                f"Fictional {label} classification used only to exercise FloodSense."
            )
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
        for code, name, baseline, west, south in ZONES:
            area = self._demo_record(
                GeographicArea,
                {"code": code},
                f"geographic area {code}",
                source=source,
            )
            polygon = Polygon(
                (
                    (west, south),
                    (west, south + 0.01),
                    (west + 0.01, south + 0.01),
                    (west + 0.01, south),
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
    ) -> None:
        for order, (level_code, title, instruction) in enumerate(GUIDANCE, start=1):
            matches = list(
                GuidanceItem.objects.filter(
                    source=source,
                    susceptibility_level=levels[level_code],
                ).order_by("id")
            )
            if len(matches) > 1:
                raise CommandError(
                    f"Multiple seed-owned guidance rows exist for {level_code}."
                )
            item = matches[0] if matches else GuidanceItem(title=title)
            item.susceptibility_level = levels[level_code]
            item.title = title
            item.instruction = instruction
            item.category = GuidanceItem.Category.PREPARE
            item.display_order = order * 10
            item.source = source
            item.status = PublicationStatus.DEMONSTRATION
            item.is_enabled = True
            item.full_clean()
            item.save()

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
