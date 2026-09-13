from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from geography.models import GeographicArea
from provenance.models import PublicationStatus
from provenance.policies import DEMONSTRATION_WARNING

from .models import ExpertRule, ScenarioOption, SusceptibilityLevel
from .services import evaluate_assessment


class Day6MapAssessmentApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=StringIO())

    def _post(self, *, intensity="DEMO_HEAVY", duration="DEMO_6_HOURS"):
        return self.client.post(
            reverse("expert:evaluate-map"),
            {
                "mode": "demonstration",
                "rainfall_intensity_code": intensity,
                "rainfall_duration_code": duration,
            },
            content_type="application/json",
        )

    def test_returns_one_existing_engine_result_per_area_in_stable_order(self):
        with patch(
            "expert.services.evaluate_assessment",
            wraps=evaluate_assessment,
        ) as evaluator:
            response = self._post()

        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual(evaluator.call_count, 4)
        self.assertEqual(
            [item["area"]["code"] for item in results],
            ["DEMO_ZONE_A", "DEMO_ZONE_B", "DEMO_ZONE_C", "DEMO_ZONE_D"],
        )

    def test_stored_level_colors_are_returned_for_all_four_classes(self):
        expected = {
            level.code: level.map_color
            for level in SusceptibilityLevel.objects.order_by("display_order")
        }
        scenarios = (
            ("DEMO_LIGHT", "DEMO_1_HOUR", "LOW"),
            ("DEMO_MODERATE", "DEMO_1_HOUR", "MODERATE"),
            ("DEMO_HEAVY", "DEMO_3_HOURS", "HIGH"),
            ("DEMO_INTENSE", "DEMO_6_HOURS", "VERY_HIGH"),
        )
        observed = {}
        for intensity, duration, desired_code in scenarios:
            response = self._post(intensity=intensity, duration=duration)
            for item in response.json()["results"]:
                susceptibility = item["susceptibility"]
                if susceptibility and susceptibility["code"] == desired_code:
                    observed[desired_code] = susceptibility["map_color"]
                    break

        self.assertEqual(observed, expected)

    def test_limitation_results_have_no_fabricated_class_or_color(self):
        ExpertRule.objects.update(is_enabled=False)

        response = self._post()

        for item in response.json()["results"]:
            self.assertEqual(item["assessment_state"], "INSUFFICIENT_DATA")
            self.assertIsNone(item["susceptibility"])
            self.assertIn("No eligible stored rule", item["summary"])

    def test_changing_intensity_changes_appropriate_polygon_results(self):
        low = self._post(intensity="DEMO_LIGHT", duration="DEMO_6_HOURS").json()
        intense = self._post(
            intensity="DEMO_INTENSE",
            duration="DEMO_6_HOURS",
        ).json()

        self.assertEqual(
            [item["susceptibility"]["code"] for item in low["results"]],
            ["LOW", "LOW", "LOW", "LOW"],
        )
        self.assertEqual(
            [item["susceptibility"]["code"] for item in intense["results"]],
            ["MODERATE", "HIGH", "VERY_HIGH", "VERY_HIGH"],
        )

    def test_changing_duration_changes_appropriate_polygon_results(self):
        short = self._post(duration="DEMO_1_HOUR").json()
        longer = self._post(duration="DEMO_3_HOURS").json()

        self.assertEqual(
            [item["susceptibility"]["code"] for item in short["results"]],
            ["MODERATE", "MODERATE", "MODERATE", "MODERATE"],
        )
        self.assertEqual(
            [item["susceptibility"]["code"] for item in longer["results"]],
            ["MODERATE", "HIGH", "HIGH", "HIGH"],
        )

    def test_disabled_and_incompatible_areas_are_excluded(self):
        GeographicArea.objects.filter(code="DEMO_ZONE_A").update(is_enabled=False)
        GeographicArea.objects.filter(code="DEMO_ZONE_B").update(
            status=PublicationStatus.PENDING_VALIDATION
        )
        area = GeographicArea.objects.get(code="DEMO_ZONE_C")
        area.pk = None
        area.code = "NON_DEMO_AREA_TYPE"
        area.name = "Non-demonstration area type"
        area.area_type = GeographicArea.AreaType.BARANGAY
        area.save()

        response = self._post()

        self.assertEqual(
            [item["area"]["code"] for item in response.json()["results"]],
            ["DEMO_ZONE_C", "DEMO_ZONE_D"],
        )

    def test_invalid_and_wrong_category_options_return_400(self):
        invalid = self._post(intensity="UNKNOWN")
        wrong_category = self._post(intensity="DEMO_6_HOURS")

        self.assertEqual(invalid.status_code, 400)
        self.assertIn("intensity_code", invalid.json())
        self.assertEqual(wrong_category.status_code, 400)
        self.assertIn("intensity_code", wrong_category.json())

    def test_map_result_never_contains_dss_guidance(self):
        response = self._post()

        self.assertNotIn("guidance", response.json())
        for item in response.json()["results"]:
            self.assertNotIn("guidance", item)

    def test_response_contains_scenario_status_ruleset_and_warnings(self):
        response = self._post()
        payload = response.json()

        self.assertEqual(
            payload["scenario"],
            {
                "rainfall_intensity_code": "DEMO_HEAVY",
                "rainfall_duration_code": "DEMO_6_HOURS",
            },
        )
        self.assertEqual(payload["data_status"], "DEMONSTRATION")
        self.assertEqual(payload["warnings"][0], DEMONSTRATION_WARNING)
        self.assertEqual(payload["results"][0]["ruleset"]["version"], "1.0")
        self.assertTrue(payload["results"][0]["matched_rule_codes"])

    def test_stored_color_change_appears_on_next_map_request(self):
        level = SusceptibilityLevel.objects.get(code="MODERATE")
        level.map_color = "#123456"
        level.save(update_fields=("map_color",))

        response = self._post(duration="DEMO_1_HOUR")

        self.assertEqual(
            {item["susceptibility"]["map_color"] for item in response.json()["results"]},
            {"#123456"},
        )

    def test_existing_single_area_endpoint_remains_unchanged(self):
        area = GeographicArea.objects.get(code="DEMO_ZONE_D")
        response = self.client.post(
            reverse("expert:evaluate"),
            {
                "mode": "demonstration",
                "geographic_area_id": area.id,
                "rainfall_intensity_code": "DEMO_INTENSE",
                "rainfall_duration_code": "DEMO_6_HOURS",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["assessment_state"], "CLASSIFIED")
        self.assertEqual(response.json()["susceptibility"]["code"], "VERY_HIGH")
        self.assertIn("guidance", response.json())

    def test_disabled_scenario_option_is_rejected(self):
        ScenarioOption.objects.filter(code="DEMO_HEAVY").update(is_enabled=False)

        response = self._post()

        self.assertEqual(response.status_code, 400)
        self.assertIn("intensity_code", response.json())
