
from decimal import Decimal

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .admin import GeographicAreaAdmin
from .models import AreaFact, GeographicArea
from .widgets import OPENLAYERS_VERSION, FloodSenseOSMWidget


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

    def test_geographic_area_admin_uses_policy_compatible_osm_widget(self):
        model_admin = GeographicAreaAdmin(GeographicArea, admin.site)
        geometry_field = GeographicArea._meta.get_field("geometry")
        form_field = model_admin.formfield_for_dbfield(geometry_field, request=None)
        widget = form_field.widget
        javascript_urls = tuple(widget.media._js)
        stylesheet_urls = tuple(widget.media._css["all"])

        self.assertIs(model_admin.gis_widget, FloodSenseOSMWidget)
        self.assertIsInstance(widget, FloodSenseOSMWidget)
        self.assertIn(f"ol@v{OPENLAYERS_VERSION}/dist/ol.js", javascript_urls[0])
        self.assertIn(f"ol@v{OPENLAYERS_VERSION}/ol.css", stylesheet_urls[0])
        self.assertNotIn("ol@v7.2.2", " ".join((*javascript_urls, *stylesheet_urls)))
