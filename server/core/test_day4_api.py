from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase
from django.urls import reverse
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
from provenance.policies import DEMONSTRATION_WARNING, NON_AUTHORITY_WARNING


class Day4PublicApiTests(TestCase):
    def setUp(self):
        self.source = DataSource.objects.create(
            name="DEMONSTRATION DATA—NOT OFFICIAL",
            source_type=DataSource.SourceType.DEMONSTRATION,
            status=PublicationStatus.DEMONSTRATION,
            permitted_use="Fictional Day 4 integration tests only.",
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
        AreaFact.objects.create(
            area=self.area,
            fact_key="zone_baseline_rank",
            numeric_value=Decimal("1"),
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            is_enabled=True,
        )
        self.intensity = self._create_option(
            category=ScenarioOption.Category.INTENSITY,
            code="DEMO_LIGHT",
            label="Light",
            value="1",
            display_order=10,
        )
        self.duration = self._create_option(
            category=ScenarioOption.Category.DURATION,
            code="DEMO_1_HOUR",
            label="1 hour",
            value="1",
            display_order=10,
        )
        self.level = SusceptibilityLevel.objects.create(
            code=SusceptibilityLevel.Code.LOW,
            label="Low",
            display_order=1,
            map_color="#4CAF50",
            definition="Fictional demonstration classification.",
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            is_enabled=True,
        )
        self.ruleset = RuleSet.objects.create(
            name="Demonstration Rules",
            version="1.0",
            mode=RuleSet.Mode.DEMONSTRATION,
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            is_active=True,
            change_summary="Fictional Day 4 integration-test rules.",
        )
        self.rule = ExpertRule.objects.create(
            code="DEMO-RULE-100",
            ruleset=self.ruleset,
            result_level=self.level,
            priority=100,
            rationale="Fictional Low demonstration rationale.",
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            is_enabled=True,
        )
        ExpertRuleCondition.objects.create(
            rule=self.rule,
            condition_type=ExpertRuleCondition.ConditionType.INTENSITY_RANK,
            operator=ExpertRuleCondition.Operator.GREATER_THAN_OR_EQUAL,
            expected_number=Decimal("1"),
        )
        self.guidance = GuidanceItem.objects.create(
            susceptibility_level=self.level,
            title="Review basic supplies",
            instruction="Review household supplies and monitor official information.",
            category=GuidanceItem.Category.PREPARE,
            display_order=10,
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            workflow_status=GuidanceItem.WorkflowStatus.PUBLISHED,
            is_enabled=True,
        )

    def _create_option(self, *, category, code, label, value, display_order):
        return ScenarioOption.objects.create(
            category=category,
            code=code,
            label=label,
            derived_value=Decimal(value),
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            display_order=display_order,
            is_enabled=True,
        )

    def _assessment_payload(self):
        return {
            "mode": "demonstration",
            "geographic_area_id": self.area.id,
            "rainfall_intensity_code": self.intensity.code,
            "rainfall_duration_code": self.duration.code,
        }

    def test_assessment_options_are_public_ordered_and_mode_filtered(self):
        earlier = self._create_option(
            category=ScenarioOption.Category.INTENSITY,
            code="DEMO_EARLIER",
            label="Earlier option",
            value="2",
            display_order=1,
        )
        disabled = self._create_option(
            category=ScenarioOption.Category.INTENSITY,
            code="DEMO_DISABLED",
            label="Disabled option",
            value="3",
            display_order=0,
        )
        disabled.is_enabled = False
        disabled.save(update_fields=("is_enabled",))
        pending = self._create_option(
            category=ScenarioOption.Category.INTENSITY,
            code="DEMO_PENDING",
            label="Pending option",
            value="4",
            display_order=0,
        )
        pending.status = PublicationStatus.PENDING_VALIDATION
        pending.save(update_fields=("status",))
        approved_source = DataSource.objects.create(
            name="Approved public test source",
            source_type=DataSource.SourceType.AGENCY_DATASET,
            status=PublicationStatus.APPROVED,
            is_publicly_releasable=True,
        )
        official = ScenarioOption.objects.create(
            category=ScenarioOption.Category.INTENSITY,
            code="OFFICIAL_TEST_INTENSITY",
            label="Approved test intensity",
            derived_value=Decimal("1"),
            source=approved_source,
            status=PublicationStatus.APPROVED,
            display_order=1,
            is_enabled=True,
        )

        response = self.client.get(
            reverse("expert:assessment-options"),
            {"mode": "DEMONSTRATION"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            [option["code"] for option in payload["intensity_options"]],
            [earlier.code, self.intensity.code],
        )
        self.assertEqual(
            [option["code"] for option in payload["duration_options"]],
            [self.duration.code],
        )
        self.assertEqual(payload["operating_mode"], "DEMONSTRATION")
        self.assertEqual(
            payload["warnings"],
            [DEMONSTRATION_WARNING, NON_AUTHORITY_WARNING],
        )

        official_response = self.client.get(
            reverse("expert:assessment-options"),
            {"mode": "official"},
        )
        self.assertEqual(official_response.status_code, 200)
        self.assertEqual(
            [
                option["code"]
                for option in official_response.json()["intensity_options"]
            ],
            [official.code],
        )
        self.assertEqual(
            official_response.json()["warnings"],
            [NON_AUTHORITY_WARNING],
        )

    def test_geography_endpoint_returns_only_permitted_demo_zones_as_geojson(self):
        other_polygon = Polygon(((2, 2), (2, 3), (3, 3), (3, 2), (2, 2)))
        GeographicArea.objects.create(
            code="REAL_LOOKING_AREA",
            name="Non-demonstration area type",
            area_type=GeographicArea.AreaType.BARANGAY,
            geometry=MultiPolygon(other_polygon, srid=4326),
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            is_enabled=True,
        )
        GeographicArea.objects.create(
            code="DEMO_DISABLED_ZONE",
            name="Disabled Demo Zone",
            area_type=GeographicArea.AreaType.DEMO_ZONE,
            geometry=MultiPolygon(other_polygon, srid=4326),
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            is_enabled=False,
        )

        response = self.client.get(
            reverse("geography:area-collection"),
            {"mode": "demonstration"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["type"], "FeatureCollection")
        self.assertEqual(len(payload["features"]), 1)
        feature = payload["features"][0]
        self.assertEqual(feature["geometry"]["type"], "MultiPolygon")
        self.assertEqual(feature["properties"]["code"], "DEMO_ZONE_A")
        self.assertEqual(feature["properties"]["data_status"], "DEMONSTRATION")
        self.assertEqual(feature["properties"]["source"]["name"], self.source.name)

    def test_assessment_endpoint_returns_expert_result_and_applicable_guidance(self):
        response = self.client.post(
            reverse("expert:evaluate"),
            self._assessment_payload(),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["assessment_state"], "CLASSIFIED")
        self.assertEqual(payload["susceptibility"]["code"], "LOW")
        self.assertEqual(payload["matched_rule_codes"], ["DEMO-RULE-100"])
        self.assertEqual(payload["guidance"][0]["id"], self.guidance.id)
        self.assertEqual(payload["guidance"][0]["instruction"], self.guidance.instruction)
        self.assertEqual(payload["data_status"], "DEMONSTRATION")
        self.assertEqual(payload["warnings"][0], DEMONSTRATION_WARNING)

    def test_unclassified_assessment_omits_class_dependent_guidance(self):
        self.rule.is_enabled = False
        self.rule.save(update_fields=("is_enabled",))

        response = self.client.post(
            reverse("expert:evaluate"),
            self._assessment_payload(),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["assessment_state"], "INSUFFICIENT_DATA")
        self.assertIsNone(payload["susceptibility"])
        self.assertEqual(payload["guidance"], [])

    def test_guidance_workflow_changes_never_change_the_classification(self):
        before = self.client.post(
            reverse("expert:evaluate"),
            self._assessment_payload(),
            content_type="application/json",
        ).json()

        self.guidance.workflow_status = GuidanceItem.WorkflowStatus.APPROVED
        self.guidance.is_enabled = False
        self.guidance.save(update_fields=("workflow_status", "is_enabled"))
        after = self.client.post(
            reverse("expert:evaluate"),
            self._assessment_payload(),
            content_type="application/json",
        ).json()

        self.assertEqual(after["guidance"], [])
        for field in (
            "assessment_state",
            "susceptibility",
            "matched_rule_codes",
            "facts",
            "scenario",
        ):
            self.assertEqual(after[field], before[field])

    def test_invalid_assessment_inputs_return_field_specific_400_response(self):
        payload = {**self._assessment_payload(), "rainfall_intensity_code": "UNKNOWN"}

        response = self.client.post(
            reverse("expert:evaluate"),
            payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("intensity_code", response.json())

    def test_demonstration_assessment_rejects_non_demo_zone_area_type(self):
        polygon = Polygon(((2, 2), (2, 3), (3, 3), (3, 2), (2, 2)))
        area = GeographicArea.objects.create(
            code="NON_DEMO_AREA_TYPE",
            name="Area that is not a demonstration zone",
            area_type=GeographicArea.AreaType.BARANGAY,
            geometry=MultiPolygon(polygon, srid=4326),
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            is_enabled=True,
        )
        payload = {**self._assessment_payload(), "geographic_area_id": area.id}

        response = self.client.post(
            reverse("expert:evaluate"),
            payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("area_identifier", response.json())

    def test_guidance_endpoint_returns_only_requested_level_guidance(self):
        response = self.client.get(
            reverse("dss:guidance-collection"),
            {"mode": "demonstration", "susceptibility_level": "LOW"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["susceptibility_level"], "LOW")
        self.assertEqual([item["id"] for item in payload["guidance"]], [self.guidance.id])
        self.assertEqual(payload["warnings"][0], DEMONSTRATION_WARNING)

    def test_admin_guidance_edit_is_visible_in_next_assessment_response(self):
        user = get_user_model().objects.create_superuser(
            email="day4-admin@example.test",
            password="local-test-password",
        )
        self.client.force_login(user)
        changed_instruction = "Changed in Admin for the Day 4 integration test."
        admin_response = self.client.post(
            reverse("admin:dss_guidanceitem_change", args=(self.guidance.id,)),
            {
                "susceptibility_level": self.level.id,
                "title": self.guidance.title,
                "instruction": changed_instruction,
                "category": self.guidance.category,
                "display_order": self.guidance.display_order,
                "source": self.source.id,
                "status": self.guidance.status,
                "is_enabled": "on",
                "_save": "Save",
            },
        )
        self.assertEqual(admin_response.status_code, 302)
        self.client.logout()

        api_response = self.client.post(
            reverse("expert:evaluate"),
            self._assessment_payload(),
            content_type="application/json",
        )

        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(
            api_response.json()["guidance"][0]["instruction"],
            changed_instruction,
        )

    def test_invalid_operating_mode_is_rejected(self):
        response = self.client.get(
            reverse("expert:assessment-options"),
            {"mode": "unsupported"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("mode", response.json())
