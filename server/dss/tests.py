
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from expert.models import SusceptibilityLevel
from provenance.models import DataSource, PublicationStatus

from .models import GuidanceItem


class GuidanceItemDefinitionTests(SimpleTestCase):
    def test_dss_guidance_is_registered_in_admin(self):
        self.assertTrue(admin.site.is_registered(GuidanceItem))

    def test_guidance_categories_do_not_claim_forecasting(self):
        codes = {value for value, _label in GuidanceItem.Category.choices}

        self.assertNotIn("FORECAST", codes)
        self.assertNotIn("EVACUATION_ORDER", codes)


class GuidanceItemValidationTests(TestCase):
    def setUp(self):
        self.source = DataSource.objects.create(
            name="TEST DEMONSTRATION SOURCE - NOT OFFICIAL",
            source_type=DataSource.SourceType.DEMONSTRATION,
            status=PublicationStatus.DEMONSTRATION,
        )
        self.level = SusceptibilityLevel.objects.create(
            code=SusceptibilityLevel.Code.LOW,
            label="Low",
            display_order=1,
            map_color="#2E9E5B",
            definition="Test-only classification vocabulary.",
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            is_enabled=True,
        )

    def _item(self, **overrides):
        values = {
            "susceptibility_level": self.level,
            "title": "Test guidance",
            "instruction": "Test-only preparedness guidance.",
            "category": GuidanceItem.Category.PREPARE,
            "source": self.source,
            "status": PublicationStatus.DEMONSTRATION,
        }
        values.update(overrides)
        return GuidanceItem(**values)

    def test_enabled_draft_is_invalid(self):
        with self.assertRaises(ValidationError) as raised:
            self._item(is_enabled=True).full_clean()

        self.assertIn("is_enabled", raised.exception.message_dict)

    def test_published_content_requires_eligible_status_source_and_level(self):
        item = self._item(
            workflow_status=GuidanceItem.WorkflowStatus.PUBLISHED,
            is_enabled=True,
        )
        item.full_clean()

        item.status = PublicationStatus.PENDING_VALIDATION
        with self.assertRaises(ValidationError) as raised:
            item.full_clean()
        self.assertIn("status", raised.exception.message_dict)

        item.status = PublicationStatus.DEMONSTRATION
        self.source.status = PublicationStatus.RESTRICTED
        with self.assertRaises(ValidationError) as raised:
            item.full_clean()
        self.assertIn("source", raised.exception.message_dict)
