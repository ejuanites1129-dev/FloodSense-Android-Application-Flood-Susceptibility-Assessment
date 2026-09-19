from copy import deepcopy

from django.test import TestCase
from expert.models import SusceptibilityLevel
from provenance.models import DataSource, PublicationStatus

from .models import GuidanceItem
from .services import GuidanceSelectionError, select_guidance, select_guidance_for_level


class GuidanceSelectionServiceTests(TestCase):
    def setUp(self):
        self.source = DataSource.objects.create(
            name="DEMONSTRATION DATA—NOT OFFICIAL",
            source_type=DataSource.SourceType.DEMONSTRATION,
            status=PublicationStatus.DEMONSTRATION,
            permitted_use="Fictional automated-test guidance only.",
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
        self.second = self._create_guidance(
            title="Second demonstration action",
            instruction="Continue monitoring official information.",
            display_order=20,
        )
        self.first = self._create_guidance(
            title="First demonstration action",
            instruction="Review basic household supplies.",
            display_order=10,
        )
        self.assessment = {
            "assessment_state": "CLASSIFIED",
            "susceptibility": {"code": "LOW", "label": "Low"},
            "scenario": {
                "rainfall_intensity_code": "DEMO_LIGHT",
                "rainfall_duration_code": "DEMO_1_HOUR",
            },
            "operating_mode": "DEMONSTRATION",
        }

    def _create_guidance(self, **overrides):
        values = {
            "susceptibility_level": self.level,
            "title": "Demonstration guidance",
            "instruction": "Demonstration preparedness instruction.",
            "category": GuidanceItem.Category.PREPARE,
            "display_order": 0,
            "source": self.source,
            "status": PublicationStatus.DEMONSTRATION,
            "workflow_status": GuidanceItem.WorkflowStatus.PUBLISHED,
            "is_enabled": True,
        }
        values.update(overrides)
        return GuidanceItem.objects.create(**values)

    def test_selects_enabled_guidance_in_admin_order_without_mutating_assessment(self):
        original_assessment = deepcopy(self.assessment)

        guidance = select_guidance(self.assessment)

        self.assertEqual(
            [item["id"] for item in guidance],
            [self.first.id, self.second.id],
        )
        self.assertEqual(self.assessment, original_assessment)
        self.assertEqual(guidance[0]["data_status"], "DEMONSTRATION")
        self.assertEqual(guidance[0]["source"]["name"], self.source.name)

    def test_nonclassified_or_incomplete_assessment_returns_no_guidance(self):
        for state in ("UNCERTAIN", "INSUFFICIENT_DATA"):
            with self.subTest(state=state):
                result = {**self.assessment, "assessment_state": state}
                self.assertEqual(select_guidance(result), [])

        missing_scenario = {**self.assessment, "scenario": {}}
        self.assertEqual(select_guidance(missing_scenario), [])

    def test_disabled_pending_and_other_level_guidance_are_excluded(self):
        self._create_guidance(title="Disabled", is_enabled=False)
        self._create_guidance(
            title="Pending",
            status=PublicationStatus.PENDING_VALIDATION,
        )
        other_level = SusceptibilityLevel.objects.create(
            code=SusceptibilityLevel.Code.MODERATE,
            label="Moderate",
            display_order=2,
            map_color="#F4C542",
            definition="Fictional demonstration classification.",
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            is_enabled=True,
        )
        GuidanceItem.objects.create(
            susceptibility_level=other_level,
            title="Other level",
            instruction="Not applicable to Low.",
            category=GuidanceItem.Category.MONITOR,
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            workflow_status=GuidanceItem.WorkflowStatus.PUBLISHED,
            is_enabled=True,
        )

        guidance = select_guidance(self.assessment)

        self.assertEqual(
            [item["title"] for item in guidance],
            [self.first.title, self.second.title],
        )

    def test_level_must_be_enabled_and_permitted_for_mode(self):
        self.level.is_enabled = False
        self.level.save(update_fields=("is_enabled",))

        with self.assertRaises(GuidanceSelectionError):
            select_guidance_for_level(
                susceptibility_code="LOW",
                mode="demonstration",
            )

        self.assertEqual(select_guidance(self.assessment), [])

    def test_only_explicitly_published_guidance_is_selected(self):
        self.first.workflow_status = GuidanceItem.WorkflowStatus.APPROVED
        self.first.is_enabled = False
        self.first.save(update_fields=("workflow_status", "is_enabled"))

        guidance = select_guidance(self.assessment)

        self.assertEqual([item["id"] for item in guidance], [self.second.id])

    def test_demonstration_and_official_guidance_are_not_mixed(self):
        approved_source = DataSource.objects.create(
            name="Approved public test guidance source",
            source_type=DataSource.SourceType.PUBLICATION,
            status=PublicationStatus.APPROVED,
            is_publicly_releasable=True,
        )
        official_level = SusceptibilityLevel.objects.create(
            code=SusceptibilityLevel.Code.HIGH,
            label="High",
            display_order=3,
            map_color="#FF9800",
            definition="Approved test-only classification vocabulary.",
            source=approved_source,
            status=PublicationStatus.APPROVED,
            is_enabled=True,
        )
        official_guidance = GuidanceItem.objects.create(
            susceptibility_level=official_level,
            title="Approved test guidance",
            instruction="Follow validated preparedness information.",
            category=GuidanceItem.Category.MONITOR,
            source=approved_source,
            status=PublicationStatus.APPROVED,
            workflow_status=GuidanceItem.WorkflowStatus.PUBLISHED,
            is_enabled=True,
        )

        selected = select_guidance_for_level(
            susceptibility_code="HIGH",
            mode="official",
        )

        self.assertEqual([item["id"] for item in selected], [official_guidance.id])
        with self.assertRaises(GuidanceSelectionError):
            select_guidance_for_level(
                susceptibility_code="HIGH",
                mode="demonstration",
            )
