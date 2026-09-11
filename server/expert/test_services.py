from decimal import Decimal

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.exceptions import ValidationError
from django.test import TestCase
from geography.models import AreaFact, GeographicArea
from provenance.models import DataSource, PublicationStatus

from .models import (
    ExpertRule,
    ExpertRuleCondition,
    RuleSet,
    ScenarioOption,
    SusceptibilityLevel,
)
from .services import (
    DEMONSTRATION_WARNING,
    NON_AUTHORITY_WARNING,
    AssessmentInputError,
    evaluate_assessment,
)


class InferenceServiceTests(TestCase):
    def setUp(self):
        self.source = DataSource.objects.create(
            name="DEMONSTRATION DATA—NOT OFFICIAL",
            source_type=DataSource.SourceType.DEMONSTRATION,
            status=PublicationStatus.DEMONSTRATION,
            permitted_use="Automated testing with fictional records only.",
        )
        polygon = Polygon(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0)))
        self.area = GeographicArea.objects.create(
            code="DEMO_ZONE_A",
            name="Demo Zone A",
            area_type=GeographicArea.AreaType.DEMO_ZONE,
            geometry=MultiPolygon(polygon, srid=4326),
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            is_enabled=True,
        )
        self.baseline = AreaFact.objects.create(
            area=self.area,
            fact_key="zone_baseline_rank",
            numeric_value=Decimal("1"),
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            is_enabled=True,
        )
        self.intensities = {
            "light": self._create_option("DEMO_LIGHT", "Light", "1", "INTENSITY"),
            "moderate": self._create_option(
                "DEMO_MODERATE", "Moderate", "2", "INTENSITY"
            ),
            "heavy": self._create_option("DEMO_HEAVY", "Heavy", "3", "INTENSITY"),
            "intense": self._create_option(
                "DEMO_INTENSE", "Intense", "4", "INTENSITY"
            ),
        }
        self.durations = {
            "one": self._create_option("DEMO_1_HOUR", "1 hour", "1", "DURATION"),
            "three": self._create_option(
                "DEMO_3_HOURS", "3 hours", "3", "DURATION"
            ),
            "six": self._create_option("DEMO_6_HOURS", "6 hours", "6", "DURATION"),
        }
        self.levels = {
            code: SusceptibilityLevel.objects.create(
                code=code,
                label=label,
                display_order=display_order,
                map_color=color,
                definition="Fictional demonstration classification.",
                source=self.source,
                status=PublicationStatus.DEMONSTRATION,
                is_enabled=True,
            )
            for code, label, display_order, color in (
                ("LOW", "Low", 1, "#4CAF50"),
                ("MODERATE", "Moderate", 2, "#F4C542"),
                ("HIGH", "High", 3, "#FF9800"),
                ("VERY_HIGH", "Very High", 4, "#D32F2F"),
            )
        }
        self.ruleset = RuleSet.objects.create(
            name="Demonstration Rules",
            version="1.0",
            mode=RuleSet.Mode.DEMONSTRATION,
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            is_active=True,
            change_summary="Fictional rules for automated tests.",
        )
        self._install_demonstration_rule_table()

    def _create_option(self, code, label, derived_value, category):
        return ScenarioOption.objects.create(
            category=category,
            code=code,
            label=label,
            derived_value=Decimal(derived_value),
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            display_order=99,
            is_enabled=True,
        )

    def _create_rule(
        self,
        *,
        code,
        level="LOW",
        priority=100,
        scope=None,
        enabled=True,
        source=None,
        status=PublicationStatus.DEMONSTRATION,
        conditions=(),
    ):
        rule = ExpertRule.objects.create(
            code=code,
            ruleset=self.ruleset,
            geographic_scope=scope,
            result_level=self.levels[level],
            priority=priority,
            rationale=f"Stored rationale for {code} using fictional facts.",
            source=source or self.source,
            status=status,
            is_enabled=enabled,
        )
        for display_order, condition_values in enumerate(conditions):
            ExpertRuleCondition.objects.create(
                rule=rule,
                display_order=display_order,
                **condition_values,
            )
        return rule

    def _create_threshold_rule(
        self,
        code,
        level,
        priority,
        intensity_rank,
        duration_hours,
        baseline_rank,
        scope=None,
    ):
        return self._create_rule(
            code=code,
            level=level,
            priority=priority,
            scope=scope,
            conditions=(
                {
                    "condition_type": ExpertRuleCondition.ConditionType.INTENSITY_RANK,
                    "operator": ExpertRuleCondition.Operator.GREATER_THAN_OR_EQUAL,
                    "expected_number": Decimal(str(intensity_rank)),
                },
                {
                    "condition_type": ExpertRuleCondition.ConditionType.DURATION_HOURS,
                    "operator": ExpertRuleCondition.Operator.GREATER_THAN_OR_EQUAL,
                    "expected_number": Decimal(str(duration_hours)),
                },
                {
                    "condition_type": ExpertRuleCondition.ConditionType.AREA_FACT_NUMBER,
                    "operator": ExpertRuleCondition.Operator.GREATER_THAN_OR_EQUAL,
                    "fact_key": "zone_baseline_rank",
                    "expected_number": Decimal(str(baseline_rank)),
                },
            ),
        )

    def _install_demonstration_rule_table(self):
        self._create_threshold_rule(
            "DEMO-RULE-400", "VERY_HIGH", 400, 4, 6, 3
        )
        self._create_threshold_rule("DEMO-RULE-300", "HIGH", 300, 3, 3, 2)
        self._create_threshold_rule("DEMO-RULE-200", "MODERATE", 200, 2, 1, 1)
        self._create_threshold_rule("DEMO-RULE-100", "LOW", 100, 1, 1, 1)

    def _evaluate(self, intensity="DEMO_LIGHT", duration="DEMO_1_HOUR", area=None):
        return evaluate_assessment(
            area_identifier=area or self.area.pk,
            intensity_code=intensity,
            duration_code=duration,
            mode="demonstration",
        )

    def _disable_all_rules(self):
        ExpertRule.objects.update(is_enabled=False)

    def test_low_result(self):
        result = self._evaluate()

        self.assertEqual(result["assessment_state"], "CLASSIFIED")
        self.assertEqual(result["susceptibility"]["code"], "LOW")
        self.assertEqual(result["matched_rule_codes"], ["DEMO-RULE-100"])

    def test_moderate_result(self):
        result = self._evaluate(intensity="DEMO_MODERATE")

        self.assertEqual(result["susceptibility"]["code"], "MODERATE")

    def test_high_result(self):
        self.baseline.numeric_value = Decimal("2")
        self.baseline.save(update_fields=("numeric_value",))

        result = self._evaluate(intensity="DEMO_HEAVY", duration="DEMO_3_HOURS")

        self.assertEqual(result["susceptibility"]["code"], "HIGH")

    def test_very_high_result(self):
        self.baseline.numeric_value = Decimal("3")
        self.baseline.save(update_fields=("numeric_value",))

        result = self._evaluate(intensity="DEMO_INTENSE", duration="DEMO_6_HOURS")

        self.assertEqual(result["susceptibility"]["code"], "VERY_HIGH")

    def test_no_matching_rule_returns_insufficient_data(self):
        self._disable_all_rules()
        self._create_rule(
            code="NO-MATCH",
            conditions=(
                {
                    "condition_type": ExpertRuleCondition.ConditionType.INTENSITY_RANK,
                    "operator": ExpertRuleCondition.Operator.GREATER_THAN,
                    "expected_number": Decimal("5"),
                },
            ),
        )

        result = self._evaluate()

        self.assertEqual(result["assessment_state"], "INSUFFICIENT_DATA")
        self.assertIsNone(result["susceptibility"])

    def test_unknown_intensity_option_is_rejected(self):
        with self.assertRaises(AssessmentInputError) as error:
            self._evaluate(intensity="UNKNOWN_INTENSITY")

        self.assertIn("intensity_code", error.exception.message_dict)

    def test_unknown_duration_option_is_rejected(self):
        with self.assertRaises(AssessmentInputError) as error:
            self._evaluate(duration="UNKNOWN_DURATION")

        self.assertIn("duration_code", error.exception.message_dict)

    def test_wrong_scenario_option_category_is_rejected(self):
        with self.assertRaises(AssessmentInputError) as error:
            self._evaluate(intensity="DEMO_1_HOUR")

        self.assertIn("wrong category", str(error.exception).lower())

    def test_disabled_area_and_scenario_options_are_rejected(self):
        self.area.is_enabled = False
        self.area.save(update_fields=("is_enabled",))
        with self.assertRaises(AssessmentInputError):
            self._evaluate()

        self.area.is_enabled = True
        self.area.save(update_fields=("is_enabled",))
        self.intensities["light"].is_enabled = False
        self.intensities["light"].save(update_fields=("is_enabled",))
        with self.assertRaises(AssessmentInputError):
            self._evaluate()

    def test_no_active_ruleset_returns_insufficient_data(self):
        self.ruleset.is_active = False
        self.ruleset.save(update_fields=("is_active",))

        result = self._evaluate()

        self.assertEqual(result["assessment_state"], "INSUFFICIENT_DATA")
        self.assertIsNone(result["ruleset"])

    def test_missing_zone_baseline_rank_returns_insufficient_data(self):
        self.baseline.delete()

        result = self._evaluate()

        self.assertEqual(result["assessment_state"], "INSUFFICIENT_DATA")
        self.assertIn("zone_baseline_rank", result["explanation"]["summary"])

    def test_missing_numeric_scenario_value_returns_insufficient_data(self):
        for option, expected_fact in (
            (self.intensities["light"], "rainfall_intensity_rank"),
            (self.durations["one"], "rainfall_duration_hours"),
        ):
            with self.subTest(expected_fact=expected_fact):
                original_value = option.derived_value
                option.derived_value = None
                option.save(update_fields=("derived_value",))

                result = self._evaluate()

                self.assertEqual(result["assessment_state"], "INSUFFICIENT_DATA")
                self.assertIn(expected_fact, result["explanation"]["summary"])
                option.derived_value = original_value
                option.save(update_fields=("derived_value",))

    def test_inactive_rules_are_ignored(self):
        self._disable_all_rules()
        self._create_rule(
            code="ACTIVE-LOW",
            level="LOW",
            priority=1,
            conditions=(self._matching_intensity_condition(),),
        )
        self._create_rule(
            code="DISABLED-HIGH",
            level="HIGH",
            priority=999,
            enabled=False,
            conditions=(self._matching_intensity_condition(),),
        )

        result = self._evaluate()

        self.assertEqual(result["susceptibility"]["code"], "LOW")
        self.assertEqual(result["matched_rule_codes"], ["ACTIVE-LOW"])

    def test_disabled_conditions_are_ignored(self):
        self._disable_all_rules()
        rule = self._create_rule(
            code="DISABLED-CONDITION",
            level="MODERATE",
            conditions=(self._matching_intensity_condition(),),
        )
        ExpertRuleCondition.objects.create(
            rule=rule,
            condition_type=ExpertRuleCondition.ConditionType.INTENSITY_RANK,
            operator=ExpertRuleCondition.Operator.GREATER_THAN,
            expected_number=Decimal("99"),
            is_enabled=False,
        )

        result = self._evaluate()

        self.assertEqual(result["susceptibility"]["code"], "MODERATE")

    def test_rule_with_no_enabled_conditions_does_not_match(self):
        self._disable_all_rules()
        self._create_rule(code="EMPTY-RULE", level="VERY_HIGH", priority=999)

        result = self._evaluate()

        self.assertEqual(result["assessment_state"], "INSUFFICIENT_DATA")

    def test_higher_priority_matching_rule_wins(self):
        self._disable_all_rules()
        self._create_rule(
            code="LOW-PRIORITY",
            level="LOW",
            priority=1,
            conditions=(self._matching_intensity_condition(),),
        )
        self._create_rule(
            code="HIGH-PRIORITY",
            level="HIGH",
            priority=2,
            conditions=(self._matching_intensity_condition(),),
        )

        result = self._evaluate()

        self.assertEqual(result["susceptibility"]["code"], "HIGH")
        self.assertEqual(result["matched_rule_codes"], ["HIGH-PRIORITY"])

    def test_area_specific_rule_outranks_global_rule(self):
        self._disable_all_rules()
        self._create_rule(
            code="GLOBAL-HIGH",
            level="HIGH",
            priority=999,
            conditions=(self._matching_intensity_condition(),),
        )
        self._create_rule(
            code="AREA-MODERATE",
            level="MODERATE",
            priority=1,
            scope=self.area,
            conditions=(self._matching_intensity_condition(),),
        )

        result = self._evaluate()

        self.assertEqual(result["susceptibility"]["code"], "MODERATE")
        self.assertEqual(result["matched_rule_codes"], ["AREA-MODERATE"])

    def test_rule_scoped_to_another_area_is_ineligible(self):
        self._disable_all_rules()
        other_polygon = Polygon(((2, 2), (2, 3), (3, 3), (3, 2), (2, 2)))
        other_area = GeographicArea.objects.create(
            code="DEMO_ZONE_B",
            name="Demo Zone B",
            area_type=GeographicArea.AreaType.DEMO_ZONE,
            geometry=MultiPolygon(other_polygon, srid=4326),
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            is_enabled=True,
        )
        self._create_rule(
            code="GLOBAL-LOW",
            level="LOW",
            priority=1,
            conditions=(self._matching_intensity_condition(),),
        )
        self._create_rule(
            code="OTHER-AREA-HIGH",
            level="HIGH",
            priority=999,
            scope=other_area,
            conditions=(self._matching_intensity_condition(),),
        )

        result = self._evaluate()

        self.assertEqual(result["susceptibility"]["code"], "LOW")
        self.assertEqual(result["matched_rule_codes"], ["GLOBAL-LOW"])

    def test_equally_ranked_conflicting_rules_return_uncertain(self):
        self._disable_all_rules()
        for code, level in (("TIE-LOW", "LOW"), ("TIE-HIGH", "HIGH")):
            self._create_rule(
                code=code,
                level=level,
                priority=50,
                conditions=(self._matching_intensity_condition(),),
            )

        result = self._evaluate()

        self.assertEqual(result["assessment_state"], "UNCERTAIN")
        self.assertIsNone(result["susceptibility"])
        self.assertEqual(result["matched_rule_codes"], ["TIE-HIGH", "TIE-LOW"])

    def test_equally_ranked_same_result_reports_every_supporting_rule(self):
        self._disable_all_rules()
        for code in ("SUPPORT-A", "SUPPORT-B"):
            self._create_rule(
                code=code,
                level="LOW",
                priority=50,
                conditions=(self._matching_intensity_condition(),),
            )

        result = self._evaluate()

        self.assertEqual(result["assessment_state"], "CLASSIFIED")
        self.assertEqual(result["susceptibility"]["code"], "LOW")
        self.assertEqual(result["matched_rule_codes"], ["SUPPORT-A", "SUPPORT-B"])

    def test_demonstration_and_official_records_are_not_mixed(self):
        approved_source = DataSource.objects.create(
            name="Approved test source",
            source_type=DataSource.SourceType.AGENCY_DATASET,
            status=PublicationStatus.APPROVED,
            is_publicly_releasable=True,
        )
        AreaFact.objects.create(
            area=self.area,
            fact_key="zone_baseline_rank",
            numeric_value=Decimal("4"),
            source=approved_source,
            status=PublicationStatus.APPROVED,
            is_enabled=True,
        )
        self._create_rule(
            code="OFFICIAL-RULE-IN-DEMO-SET",
            level="VERY_HIGH",
            priority=999,
            source=approved_source,
            status=PublicationStatus.APPROVED,
            conditions=(self._matching_intensity_condition(),),
        )

        result = self._evaluate()

        self.assertEqual(result["susceptibility"]["code"], "LOW")
        self.assertNotIn("OFFICIAL-RULE-IN-DEMO-SET", result["matched_rule_codes"])

        official_option = ScenarioOption.objects.create(
            category=ScenarioOption.Category.INTENSITY,
            code="OFFICIAL_INTENSITY",
            label="Approved option for separation test",
            derived_value=Decimal("1"),
            source=approved_source,
            status=PublicationStatus.APPROVED,
            is_enabled=True,
        )
        with self.assertRaises(AssessmentInputError):
            self._evaluate(intensity=official_option.code)

    def test_all_supported_numeric_operators(self):
        operator_cases = (
            (ExpertRuleCondition.Operator.EQUALS, "1"),
            (ExpertRuleCondition.Operator.GREATER_THAN, "0"),
            (ExpertRuleCondition.Operator.GREATER_THAN_OR_EQUAL, "1"),
            (ExpertRuleCondition.Operator.LESS_THAN, "2"),
            (ExpertRuleCondition.Operator.LESS_THAN_OR_EQUAL, "1"),
        )
        for operator, expected in operator_cases:
            with self.subTest(operator=operator):
                ExpertRule.objects.all().delete()
                self._create_rule(
                    code=f"OPERATOR-{operator}",
                    conditions=(
                        {
                            "condition_type": (
                                ExpertRuleCondition.ConditionType.INTENSITY_RANK
                            ),
                            "operator": operator,
                            "expected_number": Decimal(expected),
                        },
                    ),
                )

                result = self._evaluate()

                self.assertEqual(result["assessment_state"], "CLASSIFIED")

    def test_exact_options_and_text_area_fact_conditions_are_supported(self):
        self._disable_all_rules()
        AreaFact.objects.create(
            area=self.area,
            fact_key="demo_surface_type",
            text_value="fictional-clay",
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            is_enabled=True,
        )
        self._create_rule(
            code="EXACT-AND-TEXT",
            level="MODERATE",
            conditions=(
                {
                    "condition_type": ExpertRuleCondition.ConditionType.INTENSITY_OPTION,
                    "operator": ExpertRuleCondition.Operator.EQUALS,
                    "scenario_option": self.intensities["light"],
                },
                {
                    "condition_type": ExpertRuleCondition.ConditionType.DURATION_OPTION,
                    "operator": ExpertRuleCondition.Operator.EQUALS,
                    "scenario_option": self.durations["one"],
                },
                {
                    "condition_type": ExpertRuleCondition.ConditionType.AREA_FACT_TEXT,
                    "operator": ExpertRuleCondition.Operator.EQUALS,
                    "fact_key": "demo_surface_type",
                    "expected_text": "fictional-clay",
                },
            ),
        )

        result = self._evaluate()

        self.assertEqual(result["susceptibility"]["code"], "MODERATE")

    def test_invalid_derived_condition_field_combinations_raise_validation_errors(self):
        rule = ExpertRule.objects.first()
        for condition_type in (
            ExpertRuleCondition.ConditionType.INTENSITY_RANK,
            ExpertRuleCondition.ConditionType.DURATION_HOURS,
        ):
            with self.subTest(condition_type=condition_type):
                condition = ExpertRuleCondition(
                    rule=rule,
                    condition_type=condition_type,
                    operator=ExpertRuleCondition.Operator.GREATER_THAN_OR_EQUAL,
                    scenario_option=self.intensities["light"],
                    fact_key="zone_baseline_rank",
                    expected_text="invalid",
                    expected_number=Decimal("1"),
                )

                with self.assertRaises(ValidationError) as error:
                    condition.full_clean()

                self.assertIn("scenario_option", error.exception.message_dict)
                self.assertIn("fact_key", error.exception.message_dict)
                self.assertIn("expected_text", error.exception.message_dict)

        missing_number = ExpertRuleCondition(
            rule=rule,
            condition_type=ExpertRuleCondition.ConditionType.INTENSITY_RANK,
            operator=ExpertRuleCondition.Operator.EQUALS,
        )
        with self.assertRaises(ValidationError) as error:
            missing_number.full_clean()
        self.assertIn("expected_number", error.exception.message_dict)

    def test_explanation_contains_facts_ruleset_rules_rationales_and_warnings(self):
        result = self._evaluate()
        explanation = result["explanation"]

        self.assertIn("zone_baseline_rank=1", explanation["facts_used"])
        self.assertEqual(explanation["matched_rule_codes"], ["DEMO-RULE-100"])
        self.assertEqual(explanation["ruleset"], "Demonstration Rules v1.0")
        self.assertIn("Stored rationale for DEMO-RULE-100", explanation["rule_rationales"][0])
        self.assertEqual(
            explanation["warnings"],
            [DEMONSTRATION_WARNING, NON_AUTHORITY_WARNING],
        )

    def test_changing_stored_area_fact_changes_result_without_python_changes(self):
        initial = self._evaluate(
            intensity="DEMO_INTENSE",
            duration="DEMO_6_HOURS",
        )
        self.baseline.numeric_value = Decimal("3")
        self.baseline.save(update_fields=("numeric_value",))

        changed = self._evaluate(
            intensity="DEMO_INTENSE",
            duration="DEMO_6_HOURS",
        )

        self.assertEqual(initial["susceptibility"]["code"], "MODERATE")
        self.assertEqual(changed["susceptibility"]["code"], "VERY_HIGH")

    def test_derived_value_not_display_order_drives_numeric_fact(self):
        self.intensities["light"].display_order = 500
        self.intensities["light"].save(update_fields=("display_order",))

        result = self._evaluate()

        self.assertEqual(result["facts"]["rainfall_intensity_rank"], 1)
        self.assertEqual(result["susceptibility"]["code"], "LOW")

    def test_area_code_can_be_used_as_identifier(self):
        result = self._evaluate(area=self.area.code)

        self.assertEqual(result["area"]["code"], "DEMO_ZONE_A")

    def _matching_intensity_condition(self):
        return {
            "condition_type": ExpertRuleCondition.ConditionType.INTENSITY_RANK,
            "operator": ExpertRuleCondition.Operator.EQUALS,
            "expected_number": Decimal("1"),
        }
