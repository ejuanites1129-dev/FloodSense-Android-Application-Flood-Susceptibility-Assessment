"""Shared decorative rendering and static asset safety checks."""

from pathlib import Path
from xml.etree import ElementTree

from django.contrib.staticfiles import finders
from django.template import Context, Template
from django.test import SimpleTestCase

from .templatetags.portal_icons import PORTAL_ICONS


class PortalIconTests(SimpleTestCase):
    def test_approved_assets_are_local_passive_svg_exports(self):
        for slug, icon in PORTAL_ICONS.items():
            with self.subTest(slug=slug):
                asset = f"admin_portal/icons/lucide/{icon}.svg"
                path = finders.find(asset)
                self.assertIsNotNone(path)
                root = ElementTree.fromstring(Path(path).read_bytes())
                self.assertEqual(root.attrib["viewBox"], "0 0 24 24")
                for element in root.iter():
                    self.assertIn(
                        element.tag.split("}")[-1], {"svg", "path", "circle", "rect", "line"}
                    )
                    self.assertFalse(any(key.startswith("on") for key in element.attrib))
                rendered = Template(
                    "{% load portal_icons %}{% portal_icon slug %}"
                ).render(Context({"slug": slug}))
                self.assertIn(asset, rendered)
                self.assertIn('aria-hidden="true"', rendered)
                self.assertIn('alt=""', rendered)
                self.assertNotIn("tabindex", rendered)

    def test_unknown_icon_uses_escaped_original_symbol(self):
        rendered = Template(
            "{% load portal_icons %}{% portal_icon slug fallback %}"
        ).render(Context({"slug": "unknown", "fallback": "<original>"}))
        self.assertIn("&lt;original&gt;", rendered)
        self.assertNotIn("<img", rendered)
