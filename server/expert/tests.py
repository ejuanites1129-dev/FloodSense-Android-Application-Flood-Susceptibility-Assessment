
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from provenance.models import PublicationStatus

from .models import (
    ExpertRule,
    ExpertRuleCondition,
    RuleSet,
    ScenarioOption,
    SusceptibilityLevel,
)


class ExpertModelDefinitionTests(SimpleTestCase):
    def test_only_four_susceptibility_codes_exist(self):
        self.assertEqual(
            {value for value, _label in SusceptibilityLevel.Code.choices},
            {"LOW", "MODERATE", "HIGH", "VERY_HIGH"},
        )

    def test_active_demonstration_ruleset_requires_demonstration_status(self):
        ruleset = RuleSet(
            name="Demo",
            version="1",
            mode=RuleSet.Mode.DEMONSTRATION,
            status=PublicationStatus.APPROVED,
            is_active=True,
        )

        with self.assertRaises(ValidationError):
            ruleset.clean()

    def test_intensity_condition_rejects_duration_option(self):
        duration = ScenarioOption(
            category=ScenarioOption.Category.DURATION,
            code="demo-short",
            label="Demo short",
        )
        condition = ExpertRuleCondition(
            condition_type=ExpertRuleCondition.ConditionType.INTENSITY_OPTION,
            operator=ExpertRuleCondition.Operator.EQUALS,
            scenario_option=duration,
        )

        with self.assertRaises(ValidationError):
            condition.clean()

    def test_expert_models_are_registered_in_admin(self):
        for model in (
            ScenarioOption,
            SusceptibilityLevel,
            RuleSet,
            ExpertRule,
            ExpertRuleCondition,
        ):
            with self.subTest(model=model.__name__):
                self.assertTrue(admin.site.is_registered(model))
