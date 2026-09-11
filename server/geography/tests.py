
from decimal import Decimal

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .models import AreaFact, GeographicArea


class AreaFactDefinitionTests(SimpleTestCase):
    def test_area_fact_requires_exactly_one_typed_value(self):
        empty_fact = AreaFact(fact_key="demo-key")
        conflicting_fact = AreaFact(
            fact_key="demo-key",
            text_value="demo",
            numeric_value=Decimal("1.0000"),
        )

        with self.assertRaises(ValidationError):
            empty_fact.clean()
        with self.assertRaises(ValidationError):
            conflicting_fact.clean()

    def test_geography_models_are_registered_in_admin(self):
        self.assertTrue(admin.site.is_registered(GeographicArea))
        self.assertTrue(admin.site.is_registered(AreaFact))
