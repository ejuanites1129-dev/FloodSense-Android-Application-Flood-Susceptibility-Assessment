
from django.contrib import admin
from django.test import SimpleTestCase

from .models import GuidanceItem


class GuidanceItemDefinitionTests(SimpleTestCase):
    def test_dss_guidance_is_registered_in_admin(self):
        self.assertTrue(admin.site.is_registered(GuidanceItem))

    def test_guidance_categories_do_not_claim_forecasting(self):
        codes = {value for value, _label in GuidanceItem.Category.choices}

        self.assertNotIn("FORECAST", codes)
        self.assertNotIn("EVACUATION_ORDER", codes)
