"""Optional map-provider configuration and secret-safety regressions."""

from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .map_config import get_map_client_config


class MapClientConfigTests(SimpleTestCase):
    def test_map_palette_has_one_shared_css_source(self):
        static_root = Path(__file__).parent / "static" / "admin_portal"
        css = (static_root / "css" / "admin_portal.css").read_text(
            encoding="utf-8"
        )
        script = (static_root / "js" / "map_data.js").read_text(encoding="utf-8")
        expected = {
            "--map-low": "#2e9e5b",
            "--map-moderate": "#e8b923",
            "--map-high": "#e2691b",
            "--map-very-high": "#c0392b",
            "--map-limitation": "#8791a1",
        }
        for variable, color in expected.items():
            self.assertIn(f"{variable}: {color};", css)
        self.assertIn('cssColor("--map-selection"', script)
        self.assertIn('cssColor("--map-boundary-fill"', script)

    @override_settings(
        FLOODSENSE_MAP_PROVIDER="auto",
        MAPBOX_ACCESS_TOKEN="",
        FLOODSENSE_MAP_3D=False,
    )
    def test_missing_token_keeps_osm(self):
        config = get_map_client_config()
        self.assertEqual(config["provider"], "osm")
        self.assertFalse(config["mapbox_enabled"])
        self.assertEqual(config["mapbox_public_token"], "")

    @override_settings(
        FLOODSENSE_MAP_PROVIDER="mapbox",
        MAPBOX_ACCESS_TOKEN="sk.must-never-reach-a-browser",
    )
    def test_secret_token_is_rejected_for_client_rendering(self):
        config = get_map_client_config()
        self.assertEqual(config["provider"], "osm")
        self.assertEqual(config["mapbox_public_token"], "")

    @override_settings(
        FLOODSENSE_MAP_PROVIDER="auto",
        MAPBOX_ACCESS_TOKEN="pk.public-test-token",
        FLOODSENSE_MAP_3D=True,
        MAPBOX_GL_JS_ROOT="https://api.mapbox.com/mapbox-gl-js/v3.30.0",
    )
    def test_public_token_enables_pinned_mapbox_client(self):
        config = get_map_client_config()
        self.assertEqual(config["provider"], "mapbox")
        self.assertTrue(config["mapbox_enabled"])
        self.assertTrue(config["allow_3d"])
        self.assertEqual(config["mapbox_public_token"], "pk.public-test-token")
        self.assertEqual(
            config["mapbox_js_url"],
            "https://api.mapbox.com/mapbox-gl-js/v3.30.0/mapbox-gl.js",
        )


class MapProviderTemplateTests(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            email="map-provider-admin@example.test",
            is_staff=True,
        )
        self.client.force_login(staff)
        self.url = reverse("admin_portal:map-data")

    @override_settings(
        FLOODSENSE_MAP_PROVIDER="mapbox",
        MAPBOX_ACCESS_TOKEN="pk.public-template-token",
        FLOODSENSE_MAP_3D=True,
        MAPBOX_GL_JS_ROOT="https://api.mapbox.com/mapbox-gl-js/v3.30.0",
    )
    def test_mapbox_assets_public_config_and_opt_in_3d_control_are_rendered(self):
        response = self.client.get(self.url)
        self.assertContains(response, "mapbox-gl-js/v3.30.0/mapbox-gl.js")
        self.assertContains(response, "pk.public-template-token")
        self.assertContains(response, 'id="toggle-perspective"')
        self.assertContains(response, "No susceptibility classifications are plotted")
        for label in (
            "Low",
            "Moderate",
            "High",
            "Very high",
            "Uncertain / insufficient data",
        ):
            self.assertContains(response, label)

    @override_settings(
        FLOODSENSE_MAP_PROVIDER="mapbox",
        MAPBOX_ACCESS_TOKEN="sk.private-template-sentinel",
        FLOODSENSE_MAP_3D=True,
    )
    def test_secret_token_never_enters_html_and_osm_remains_available(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, "sk.private-template-sentinel")
        self.assertNotContains(response, "mapbox-gl.js")
        self.assertContains(response, "OpenStreetMap is visual context only")
        self.assertContains(response, 'data-map-provider="osm"')

    @override_settings(
        FLOODSENSE_MAP_PROVIDER="osm",
        MAPBOX_ACCESS_TOKEN="pk.unused-public-token",
    )
    def test_explicit_osm_does_not_render_unused_token(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, "pk.unused-public-token")
        self.assertNotContains(response, "mapbox-gl.js")
