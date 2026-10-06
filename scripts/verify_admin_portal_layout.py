"""Optional browser acceptance checks. Run explicitly with pytest and Playwright installed.

Uses only pytest's isolated database and live_server. Screenshots go to tmp/portal-layout-qa.
Set FLOODSENSE_QA_BROWSER to a Chromium executable if bundled browsers are unavailable.
"""

import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.urls import reverse
from evacuation.models import EvacuationCenter
from geography.models import GeographicArea
from provenance.models import DataSource

pw = pytest.importorskip("playwright.sync_api")
OUTPUT = Path(__file__).resolve().parents[1] / "tmp" / "portal-layout-qa"


def login(
    page, url, email="layout-qa@example.com", password="Isolated-layout-QA-2026"
):
    page.goto(url + "/management/login/")
    page.get_by_label("Work email").fill(email)
    page.get_by_label("Password", exact=True).fill(password)
    page.locator("button[type=submit]").click()
    pw.expect(page).to_have_url(url + "/management/")


def no_overflow(page):
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), page.url


def settled(page):
    page.wait_for_function("""() => {
        const sidebar = document.querySelector('.sidebar').getBoundingClientRect();
        const main = document.querySelector('.portal-main').getBoundingClientRect();
        const width = document.body.classList.contains('sidebar-collapsed') ? 72 : 250;
        return innerWidth <= 760 || (Math.abs(sidebar.right - main.left) < 1
            && Math.abs(sidebar.width - width) < 1);
    }""")


@pytest.mark.django_db(transaction=True)
def test_portal_layout_browser(live_server, settings):
    settings.FLOODSENSE_MAP_PROVIDER = "osm"
    get_user_model().objects.create_user(
        email="layout-qa@example.com",
        display_name="Isolated QA Maintainer",
        password="Isolated-layout-QA-2026",
        is_staff=True,
        is_superuser=True,
    )
    source = DataSource.objects.create(
        name="Synthetic QA source", source_type="DEMONSTRATION", status="DEMONSTRATION"
    )
    for index in range(2):
        GeographicArea.objects.create(
            code=f"QA-{index}",
            name="Synthetic area " + str(index) + (" LongName" * 15 if index else ""),
            area_type="DEMO_ZONE",
            source=source,
            status="DEMONSTRATION",
            is_enabled=True,
            geometry=MultiPolygon(
                Polygon.from_bbox((120.95 + index * 0.01, 14.41, 120.955 + index * 0.01, 14.415)),
                srid=4326,
            ),
        )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with pw.sync_playwright() as p:
        executable = os.environ.get("FLOODSENSE_QA_BROWSER")
        browser = p.chromium.launch(**({"executable_path": executable} if executable else {}))
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # Expose real provider state only in the QA browser, never in shipped code.
        def instrument(route):
            response = route.fetch()
            prefix = (
                "if(window.ol){const Original=ol.Map;ol.Map=class extends Original{"
                "constructor(options){super(options);window.qaMap=this;}};}\n"
            )
            route.fulfill(response=response, body=prefix + response.text())

        page.route("**/admin_portal/js/map_data.js", instrument)
        login(page, live_server.url)
        # Compare the previous text symbols with SVGs using identical synthetic data.
        # The baseline is reconstructed in the QA DOM, not an older application build.
        original_symbols = ["▦", "▤", "◇", "?", "≈", "⌂", "○", "▤"]
        for width in [1440, 768, 390]:
            page.set_viewport_size({"width": width, "height": 1000})
            page.reload()
            if width <= 760:
                page.locator("[data-menu-toggle]").click()
            settled(page)
            page.wait_for_function("""() => {
                const icons = [...document.querySelectorAll('.sidebar .portal-icon img')];
                return icons.length === 10 && icons.every(img =>
                    img.complete && img.naturalWidth === 24);
            }""")
            for icon in page.locator(".nav-link__icon .portal-icon").all():
                assert icon.bounding_box()["width"] == 20
                assert icon.bounding_box()["height"] == 20
                assert icon.evaluate(
                    "el => getComputedStyle(el).backgroundColor === getComputedStyle(el).color"
                )
            no_overflow(page)
            page.screenshot(path=str(OUTPUT / f"icons-{width}-after.png"), full_page=True)
            page.evaluate("""symbols => {
                document.querySelectorAll('.nav-link__icon').forEach((el, i) => {
                    el.textContent = symbols[i];
                });
            }""", original_symbols)
            page.screenshot(path=str(OUTPUT / f"icons-{width}-before.png"), full_page=True)
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.reload()
        pw.expect(page.locator(".portal-attribution")).to_have_count(0)
        pw.expect(page.locator('img[src*="/icons/lordicon/"]')).to_have_count(0)
        page.evaluate("window.scrollTo(0,0)")
        pw.expect(page.locator(".overview-cards .metric-card")).to_have_count(5)
        pw.expect(page.locator("#attention-heading")).to_have_text("Needs attention")
        pw.expect(page.locator("#snapshot-mode")).to_have_value("OFFICIAL")
        page.locator("#snapshot-mode").select_option("DEMONSTRATION")
        page.get_by_role("button", name="Update snapshot").click()
        pw.expect(page.locator("#snapshot-mode")).to_have_value("DEMONSTRATION")
        pw.expect(page.locator(".portal-notice")).to_contain_text("Demonstration data—not official")
        assert page.locator("#review-attention").count() == 0
        page.screenshot(path=str(OUTPUT / "overview-1440-demonstration.png"), full_page=True)
        nav = page.locator("#sidebar-navigation")
        toggle = page.locator("[data-sidebar-toggle]")
        assert page.locator(".topbar").count() == 0
        profile = page.locator("[data-account-toggle]")
        pw.expect(profile.locator(".account-summary__name")).to_be_visible()
        pw.expect(profile.locator(".system-state")).to_be_visible()
        assert profile.bounding_box()["y"] > 900
        assert page.locator(".portal-main").bounding_box()["y"] == 0
        for compact in [False, True]:
            if compact:
                toggle.click()
                settled(page)
                pw.expect(profile.locator(".account-summary")).to_be_hidden()
                profile.hover()
                assert profile.evaluate("el => getComputedStyle(el, '::after').opacity") == "1"
                assert "Isolated QA Maintainer" in profile.evaluate(
                    "el => getComputedStyle(el, '::after').content"
                )
            profile.click()
            panel = page.locator("[data-account-menu]")
            pw.expect(panel).to_be_visible()
            for icon in panel.locator(".portal-icon").all():
                assert icon.bounding_box()["width"] == 20
                assert icon.bounding_box()["height"] == 20
                assert icon.evaluate(
                    "el => getComputedStyle(el).backgroundColor === getComputedStyle(el).color"
                )
            pw.expect(page.get_by_role("menuitem", name="Settings")).to_be_focused()
            assert (
                panel.bounding_box()["y"] + panel.bounding_box()["height"]
                <= profile.bounding_box()["y"]
            )
            no_overflow(page)
            page.screenshot(
                path=str(OUTPUT / f"profile-{'collapsed' if compact else 'expanded'}.png"),
                animations="disabled",
            )
            page.keyboard.press("ArrowDown")
            pw.expect(page.get_by_role("menuitem", name="Sign out")).to_be_focused()
            page.keyboard.press("Escape")
            pw.expect(profile).to_be_focused()
            pw.expect(panel).to_be_hidden()
        page.locator(".sidebar__brand-area").hover()
        toggle.click()
        # A mouse collapse must not reveal the control merely because it retains focus.
        toggle.click()
        page.mouse.move(700, 400)
        pw.expect(nav).to_be_visible()
        pw.expect(page.locator("body")).to_have_class("portal-page sidebar-collapsed")
        pw.expect(toggle).to_have_css("opacity", "0")
        pw.expect(page.locator(".sidebar__brand")).to_have_css("opacity", "1")
        page.wait_for_function(
            "getComputedStyle(document.querySelector('[data-sidebar-toggle]'), "
            "'::after').opacity === '0'"
        )
        page.locator(".sidebar__brand-area").hover()
        pw.expect(toggle).to_have_css("opacity", "1")
        toggle.click()
        # Keyboard shortcut, repeat suppression, focus transfer and hidden links.
        nav.get_by_role("link", name="Reports").focus()
        page.keyboard.down("Control")
        page.keyboard.down("b")
        pw.expect(nav).to_be_visible()
        pw.expect(page.locator("body")).to_have_class("portal-page sidebar-collapsed")
        pw.expect(nav.get_by_role("link", name="Reports")).to_be_focused()
        page.keyboard.down("b")
        pw.expect(nav).to_be_visible()
        pw.expect(page.locator("body")).to_have_class("portal-page sidebar-collapsed")
        page.keyboard.up("b")
        page.keyboard.up("Control")
        assert nav.locator("a").first.evaluate(
            "el => {el.focus(); return document.activeElement === el;}"
        )
        links = [
            (link.get_attribute("aria-label"), link.get_attribute("href"))
            for link in nav.locator("a").all()
        ]
        for name, href in links:
            link = nav.get_by_role("link", name=name, exact=True)
            pw.expect(link.locator(".nav-link__label")).to_be_hidden()
            pw.expect(link.locator(".nav-link__icon")).to_be_visible()
            link.hover()
            assert link.evaluate("el => getComputedStyle(el, '::after').opacity") == "1"
            assert link.evaluate("el => getComputedStyle(el, '::after').content") == f'"{name}"'
            link.click()
            pw.expect(page).to_have_url(live_server.url + href)
            pw.expect(page.locator(".portal-attribution")).to_have_count(0)
            pw.expect(nav.get_by_role("link", name=name, exact=True)).to_have_attribute(
                "aria-current", "page"
            )
            pw.expect(page.locator("body")).to_have_class("portal-page sidebar-collapsed")
        page.goto(live_server.url + "/management/")
        nav.get_by_role("link", name="Reports", exact=True).hover()
        page.screenshot(path=str(OUTPUT / "sidebar-navigation-tooltip.png"), animations="disabled")
        page.locator("h1").click()
        page.mouse.move(700, 400)
        pw.expect(toggle).to_have_css("opacity", "0")
        page.locator(".sidebar__brand-area").hover()
        pw.expect(toggle).to_have_css("opacity", "1")
        pw.expect(page.locator(".sidebar__brand")).to_have_css("opacity", "0")
        pw.expect(toggle).to_have_attribute("data-sidebar-tooltip", "Open sidebar")
        assert toggle.inner_text() == ""
        assert toggle.evaluate("el => getComputedStyle(el, '::after').position") == "fixed"
        brand_box = page.locator(".sidebar__brand").bounding_box()
        toggle_box = toggle.bounding_box()
        assert abs(brand_box["x"] - toggle_box["x"]) < 1
        assert abs(brand_box["y"] - toggle_box["y"]) < 1
        page.screenshot(path=str(OUTPUT / "sidebar-hover.png"), animations="disabled")
        page.mouse.move(700, 400)
        page.keyboard.press("Tab")
        page.locator(".sidebar__brand").focus()
        pw.expect(toggle).to_have_css("opacity", "1")
        page.keyboard.press("Tab")
        pw.expect(toggle).to_be_focused()
        page.keyboard.press("Enter")
        pw.expect(nav).to_be_visible()
        for shortcut in ["Control+Shift+b", "Control+Alt+b", "Control+Meta+b"]:
            page.keyboard.press(shortcut)
            pw.expect(nav).to_be_visible()
        # Editor exemptions are exercised with temporary QA inputs.
        for markup in [
            "<input>",
            "<textarea></textarea>",
            '<div contenteditable="true">Editor</div>',
            '<div role="textbox" tabindex="0">Editor</div>',
        ]:
            page.evaluate(
                '(markup) => {const host=document.createElement("div"); host.id="qa-editor"; '
                "host.innerHTML=markup; document.body.append(host);host.firstChild.focus();}",
                markup,
            )
            page.keyboard.press("Control+b")
            pw.expect(nav).to_be_visible()
            page.locator("#qa-editor").evaluate("el => el.remove()")
        # Desktop and tablet: each page in both persisted states.
        for width in [1440, 1024, 768]:
            page.set_viewport_size({"width": width, "height": 1000})
            for route, label in [
                ("", "overview"),
                ("reports/", "reports"),
                ("map-data/", "geography"),
            ]:
                page.goto(live_server.url + "/management/" + route)
                if route == "map-data/":
                    pw.expect(page.locator("#geographic-map canvas")).to_be_visible(timeout=30000)
                for collapsed in [False, True]:
                    if (
                        page.locator("body").evaluate(
                            'el => el.classList.contains("sidebar-collapsed")'
                        )
                        != collapsed
                    ):
                        page.locator(".sidebar__brand-area").hover()
                        toggle.click()
                    settled(page)
                    no_overflow(page)
                    page.screenshot(
                        path=str(
                            OUTPUT
                            / f"{label}-{width}-{'collapsed' if collapsed else 'expanded'}.png"
                        ),
                        full_page=True,
                        animations="disabled",
                    )
                page.reload()
                pw.expect(nav).to_be_visible()
                pw.expect(page.locator("body")).to_have_class("portal-page sidebar-collapsed")
        # Real map resize preserves view and data selection; list search and keyboard selection.
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.locator("#area-search").fill("QA-1")
        pw.expect(page.locator("[data-record-id]:visible")).to_have_count(1)
        page.locator("[data-record-id]:visible").focus()
        page.keyboard.press("Enter")
        pw.expect(page.locator("#detail-heading")).to_contain_text("Synthetic area 1")
        page.locator("#area-search").fill("")
        page.locator("#layer-demonstration").uncheck()
        before = page.evaluate(
            "({zoom:qaMap.getView().getZoom(), center:qaMap.getView().getCenter(), "
            'selected:document.querySelector("#record-details").dataset.selectedId})'
        )
        page.locator(".sidebar__brand-area").hover()
        toggle.click()
        settled(page)
        page.wait_for_function(
            "Math.abs(qaMap.getSize()[0] - "
            'document.querySelector("#geographic-map").clientWidth) < 2'
        )
        after = page.evaluate(
            "({zoom:qaMap.getView().getZoom(), center:qaMap.getView().getCenter(), "
            'selected:document.querySelector("#record-details").dataset.selectedId})'
        )
        assert before == after
        page.set_viewport_size({"width": 1100, "height": 900})
        page.wait_for_function(
            "Math.abs(qaMap.getSize()[0] - "
            'document.querySelector("#geographic-map").clientWidth) < 2'
        )
        assert page.evaluate("qaMap.getView().getZoom()") == before["zoom"]
        assert page.evaluate("qaMap.getView().getCenter()") == before["center"]
        pw.expect(page.locator("#layer-demonstration")).not_to_be_checked()
        page.locator("#layer-demonstration").check()
        pw.expect(page.locator("#layer-mgb")).to_be_disabled()
        pw.expect(page.locator("#layer-approved")).to_be_disabled()
        # Reduced motion and mobile drawer, scrim, Escape, focus loop.
        page.emulate_media(reduced_motion="reduce")
        assert (
            float(
                toggle.evaluate(
                    "el => parseFloat(getComputedStyle("
                    'document.querySelector(".sidebar")).transitionDuration)'
                )
            )
            < 0.01
        )
        for width in [390, 320]:
            page.set_viewport_size({"width": width, "height": 844})
            for route, label in [
                ("", "overview"),
                ("reports/", "reports"),
                ("map-data/", "geography"),
            ]:
                page.goto(live_server.url + "/management/" + route)
                no_overflow(page)
                page.screenshot(
                    path=str(OUTPUT / f"{label}-{width}-drawer-closed.png"),
                    full_page=True,
                    animations="disabled",
                )
                page.keyboard.press("Control+b")
                pw.expect(page.locator(".sidebar")).to_have_class("sidebar sidebar--open")
                pw.expect(toggle).to_be_focused()
                assert not page.locator("body").evaluate(
                    'el => el.classList.contains("sidebar-collapsed")'
                )
                page.screenshot(
                    path=str(OUTPUT / f"{label}-{width}-drawer-open.png"),
                    full_page=True,
                    animations="disabled",
                )
                page.locator("[data-account-toggle]").focus()
                page.keyboard.press("Tab")
                pw.expect(page.locator(".sidebar__brand")).to_be_focused()
                page.keyboard.press("Escape")
                pw.expect(page.locator("[data-menu-toggle]")).to_be_focused()
                assert page.locator(".sidebar").evaluate("el => el.inert")
                page.locator("[data-menu-toggle]").click()
                page.locator("[data-menu-scrim]").click(position={"x": width - 10, "y": 400})
                pw.expect(page.locator("[data-menu-toggle]")).to_have_attribute(
                    "aria-expanded", "false"
                )
        page.set_viewport_size({"width": 1440, "height": 1000})
        settled(page)
        pw.expect(nav).to_be_visible()  # Mobile drawer did not overwrite desktop preference.
        page.set_viewport_size({"width": 390, "height": 844})
        # Account menu now belongs to the mobile drawer.
        page.locator("[data-menu-toggle]").click()
        page.locator("[data-account-toggle]").click()
        page.keyboard.press("Escape")
        pw.expect(page.locator("[data-account-toggle]")).to_be_focused()
        page.locator("[data-account-toggle]").click()
        page.get_by_role("menuitem", name="Settings").click()
        pw.expect(page.locator("h1")).to_have_text("Settings")
        page.locator("[data-menu-toggle]").click()
        page.locator("[data-account-toggle]").click()
        page.get_by_role("menuitem", name="Sign out").click()
        pw.expect(page).to_have_url(live_server.url + "/management/login/")
        # Touch at desktop width exposes the expand button without hover.
        touch = browser.new_context(viewport={"width": 1024, "height": 900}, has_touch=True)
        touch_page = touch.new_page()
        login(touch_page, live_server.url)
        touch_page.locator("[data-sidebar-toggle]").tap()
        touch_page.locator("h1").tap()
        pw.expect(touch_page.locator("[data-sidebar-toggle]")).to_have_css("opacity", "1")
        touch_page.locator("[data-sidebar-toggle]").tap()
        pw.expect(touch_page.locator("#sidebar-navigation")).to_be_visible()
        # Storage failure still permits toggles.
        broken = browser.new_context(viewport={"width": 1440, "height": 1000})
        broken.add_init_script(
            'Object.defineProperty(window,"localStorage",{get(){throw new Error("blocked");}})'
        )
        broken_page = broken.new_page()
        login(broken_page, live_server.url)
        broken_page.locator("[data-sidebar-toggle]").click()
        pw.expect(broken_page.locator("#sidebar-navigation")).to_be_visible()
        pw.expect(broken_page.locator("body")).to_have_class("portal-page sidebar-collapsed")
        # Server-rendered navigation, profile menu and record selection without JS.
        noscript = browser.new_context(
            java_script_enabled=False, viewport={"width": 390, "height": 844}
        )
        plain = noscript.new_page()
        login(plain, live_server.url)
        pw.expect(plain.locator(".overview-card")).to_have_count(5)
        plain.locator("#snapshot-mode").select_option("DEMONSTRATION")
        plain.get_by_role("button", name="Update snapshot").click()
        pw.expect(plain.locator("#snapshot-mode")).to_have_value("DEMONSTRATION")
        no_overflow(plain)
        plain.get_by_role("link", name="Reports", exact=True).click()
        pw.expect(plain.locator(".portal-icon img")).to_have_count(10)
        pw.expect(plain.locator(".portal-attribution")).to_have_count(0)
        pw.expect(plain.locator("h1")).to_have_text("Reports")
        plain.get_by_role("menuitem", name="Settings").click()
        pw.expect(plain.locator("h1")).to_have_text("Settings")
        plain.get_by_role("link", name="Map data", exact=True).click()
        plain.locator("[data-record-id]").last.click()
        pw.expect(plain.locator("#detail-heading")).to_contain_text("Synthetic area 1")
        no_overflow(plain)
        plain.evaluate("window.scrollTo(0,0)")
        plain.screenshot(
            path=str(OUTPUT / "geography-390-no-script.png"), full_page=True, animations="disabled"
        )
        plain.set_viewport_size({"width": 320, "height": 844})
        no_overflow(plain)
        # A failed enhanced provider still activates the existing OpenLayers fallback.
        settings.FLOODSENSE_MAP_PROVIDER = "mapbox"
        settings.MAPBOX_ACCESS_TOKEN = "pk.synthetic-qa-token"
        fallback = touch.new_page()
        fallback.route("**/mapbox-gl.js", lambda route: route.abort())
        fallback.goto(live_server.url + "/management/map-data/")
        pw.expect(fallback.locator("#geographic-map canvas")).to_be_visible(timeout=30000)
        pw.expect(fallback.locator("#map-status")).to_contain_text("standard map is active")
        # If both map libraries are unavailable, search/list/details still work.
        unavailable = touch.new_page()
        unavailable.route("**/mapbox-gl.js", lambda route: route.abort())
        unavailable.route("**/dist/ol.js", lambda route: route.abort())
        unavailable.goto(live_server.url + "/management/map-data/")
        unavailable.locator("#area-search").fill("QA-1")
        unavailable.locator("[data-record-id]:visible").click()
        pw.expect(unavailable.locator("#detail-heading")).to_contain_text("Synthetic area 1")
        assert not errors, errors
        browser.close()


@pytest.mark.django_db(transaction=True)
def test_center_form_browser(live_server, settings):
    settings.DEBUG = True
    settings.ENABLE_LOCAL_TESTING = True
    settings.FLOODSENSE_MAP_PROVIDER = "osm"
    get_user_model().objects.create_user(
        email="layout-qa@example.com",
        display_name="Isolated QA Maintainer",
        password="Isolated-layout-QA-2026",
        is_staff=True,
        is_superuser=True,
    )
    source = DataSource.objects.create(
        name="Synthetic center form evidence—not official",
        source_type="OTHER",
        status="PENDING_VALIDATION",
    )
    area = GeographicArea.objects.create(
        code="CENTER-FORM-QA",
        name="Synthetic area—not official",
        area_type="DEMO_ZONE",
        source=source,
        status="DEMONSTRATION",
        is_enabled=True,
        geometry=MultiPolygon(Polygon.from_bbox((0, 0, 1, 1)), srid=4326),
    )
    url = live_server.url + reverse("admin_portal:evacuation-center-create")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with pw.sync_playwright() as p:
        executable = os.environ.get("FLOODSENSE_QA_BROWSER")
        browser = p.chromium.launch(**({"executable_path": executable} if executable else {}))
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        # Exercise form usability even when external map assets cannot load.
        context.route("https://**", lambda route: route.abort())
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        login(page, live_server.url)
        for width in [1440, 1024, 768, 390, 320]:
            page.set_viewport_size({"width": width, "height": 1000})
            page.goto(url)
            if width > 760 and "sidebar-collapsed" in page.locator("body").get_attribute("class"):
                page.locator(".sidebar__brand-area").hover()
                page.locator("[data-sidebar-toggle]").click()
                settled(page)
            form = page.locator(".center-form")
            pw.expect(page.locator("#id_geographic_area_search")).to_have_count(0)
            pw.expect(page.locator("#id_geographic_area")).to_have_attribute(
                "title", "Choose available barangay"
            )
            pw.expect(page.locator("#id_geographic_area option").first).to_have_text(
                "Choose available barangay"
            )
            pw.expect(form.locator("legend")).to_have_text([
                "Center details", "Location", "Source and status",
                "Notes and limitations", "Review and save",
            ])
            latitude = page.locator("#id_latitude")
            longitude = page.locator("#id_longitude")
            page.locator("#id_name").fill("Synthetic center form fixture")
            page.locator("#id_address").fill("Synthetic address—not a real facility")
            latitude.fill("0.5")
            longitude.fill("0.5")
            page.locator("#id_source").select_option(str(source.pk))
            page.locator("#id_geographic_area").select_option(str(area.pk))
            page.locator("#id_notes").fill("Synthetic staff notes")
            pw.expect(page.locator("[data-center-map-status]")).to_contain_text(
                "latitude 0.5, longitude 0.5"
            )
            if width == 1440 and page.locator("[data-center-map] button").count():
                page.locator("[data-center-map] button").first.click()
                pw.expect(page).to_have_url(url)
            assert latitude.bounding_box()["height"] == 46
            assert longitude.bounding_box()["height"] == 46
            if width > 900:
                assert latitude.bounding_box()["y"] == longitude.bounding_box()["y"]
            else:
                assert latitude.bounding_box()["y"] < longitude.bounding_box()["y"]
            extra = page.locator(".center-form__additional-actions")
            assert extra.get_attribute("open") is None
            extra.locator("summary").focus()
            page.keyboard.press("Space")
            pw.expect(page.locator("#id_verified_on")).to_be_visible()
            pw.expect(page.locator("#id_capacity")).to_be_visible()
            for control in form.locator("input:not([type=hidden]), select").all():
                assert control.bounding_box()["height"] == (
                    20 if control.get_attribute("type") == "checkbox" else 46
                )
            page.locator('label[for="id_confirm"]').click()
            pw.expect(page.locator("#id_confirm")).to_be_checked()
            page.locator("#id_confirm").uncheck()
            page.locator('label[for="id_temporary_data"]').click()
            pw.expect(page.locator("#id_temporary_data")).to_be_checked()
            page.locator("#id_temporary_data").uncheck()
            no_overflow(page)
            form.screenshot(
                path=str(OUTPUT / f"center-form-{width}-expanded.png"),
                animations="disabled",
            )
            if width == 390:
                # Cropped captures can include fixed elements outside the viewport.
                assert page.locator(".skip-link").evaluate(
                    "el => el.getBoundingClientRect().bottom <= 0"
                )
                form.locator("fieldset").first.screenshot(
                    path=str(OUTPUT / "center-form-details-390.png"), animations="disabled",
                    style=".skip-link:not(:focus) { visibility: hidden; }",
                )
                form.locator(".center-form__section--last").screenshot(
                    path=str(OUTPUT / "center-form-actions-390.png"), animations="disabled",
                    style=".skip-link:not(:focus) { visibility: hidden; }",
                )
            if width > 760:
                page.locator("[data-sidebar-toggle]").click()
                settled(page)
                no_overflow(page)
                form.screenshot(
                    path=str(OUTPUT / f"center-form-{width}-collapsed.png"),
                    animations="disabled",
                )

        page.set_viewport_size({"width": 1440, "height": 1000})
        # Filtering a source list must preserve its selected value.
        page.locator("#id_source_search").fill("no other choice should match")
        pw.expect(page.locator("#id_source")).to_have_value(str(source.pk))
        page.locator("#id_source_search").fill("")
        page.locator("[data-inline-source-new]").click()
        pw.expect(page.locator("[data-source-dialog]")).to_be_visible()
        pw.expect(page.locator("[data-inline-source-form]")).to_be_visible()
        page.locator("[data-source-close]").click()
        pw.expect(page.locator("#id_name")).to_have_value("Synthetic center form fixture")

        # Failed submission retains values and links its summary to the invalid input.
        page.locator("#id_latitude").fill("91")
        page.get_by_role("button", name="Save draft", exact=True).click()
        pw.expect(page.locator(".form-error-summary")).to_be_visible()
        pw.expect(page.locator("#id_name")).to_have_value("Synthetic center form fixture")
        pw.expect(page.locator("#id_notes")).to_have_value("Synthetic staff notes")
        pw.expect(page.locator("#id_latitude")).to_have_attribute("aria-invalid", "true")
        page.locator('.form-error-summary a[href="#id_latitude"]').click()
        pw.expect(page.locator("#id_latitude")).to_be_focused()

        # Errors inside the disclosure reopen it automatically.
        page.locator("#id_latitude").fill("0.5")
        page.locator(".center-form__additional-actions summary").click()
        page.locator("#id_capacity").fill("0")
        page.get_by_role("button", name="Save draft", exact=True).click()
        pw.expect(page.locator("#id_capacity")).to_be_visible()
        pw.expect(page.locator("#id_capacity_error")).to_be_visible()
        no_overflow(page)
        page.locator(".center-form").screenshot(
            path=str(OUTPUT / "center-form-errors.png"), animations="disabled"
        )
        page.locator("#id_capacity").fill("")
        page.get_by_role("button", name="Save draft", exact=True).click()
        pw.expect(page).to_have_url(re.compile(r"/management/evacuation-centers/\d+/(?:#.*)?$"))
        center_id = int(urlsplit(page.url).path.rstrip("/").rsplit("/", 1)[1])

        # Editing preserves the existing hidden concurrency values and save behavior.
        page.goto(
            live_server.url + reverse("admin_portal:evacuation-center-edit", args=[center_id])
        )
        assert page.locator("#id_expected_updated_at").input_value()
        assert page.locator("#id_expected_source_updated_at").input_value()
        page.locator("#id_name").fill("Synthetic edited form fixture")
        page.get_by_role("button", name="Save draft", exact=True).click()
        pw.expect(page.locator("h1")).to_have_text("Synthetic edited form fixture")

        # Duplicate review remains an explicit labeled checkbox, without silent saving.
        page.goto(url)
        page.locator("#id_name").fill("Synthetic edited form fixture")
        page.locator("#id_address").fill("Synthetic duplicate candidate")
        page.locator("#id_latitude").fill("0.5")
        page.locator("#id_longitude").fill("0.5")
        page.get_by_role("button", name="Save draft", exact=True).click()
        pw.expect(page.locator("#duplicate-review-heading")).to_be_visible()
        page.locator('label[for="id_duplicate_review_confirmed"]').click()
        pw.expect(page.locator("#id_duplicate_review_confirmed")).to_be_checked()

        # Native disclosure, required controls and add-another work without JavaScript.
        plain_context = browser.new_context(
            java_script_enabled=False, viewport={"width": 390, "height": 844}
        )
        plain_context.route("https://**", lambda route: route.abort())
        plain = plain_context.new_page()
        login(plain, live_server.url)
        plain.goto(url)
        pw.expect(plain.locator("#id_source_search")).to_have_count(0)
        pw.expect(plain.locator("#id_geographic_area_search")).to_have_count(0)
        pw.expect(plain.locator("#id_geographic_area option").first).to_have_text(
            "Choose available barangay"
        )
        plain.locator(".center-form__additional-actions summary").click()
        pw.expect(plain.locator("#id_verified_on")).to_be_visible()
        plain.locator("#id_name").fill("Synthetic no-script center")
        plain.locator("#id_address").fill("Synthetic address")
        plain.locator("#id_latitude").fill("0.6")
        plain.locator("#id_longitude").fill("0.6")
        plain.locator("#id_source").select_option(str(source.pk))
        plain.locator("#id_geographic_area").select_option(str(area.pk))
        no_overflow(plain)
        plain.locator(".center-form").screenshot(
            path=str(OUTPUT / "center-form-390-no-script.png"), animations="disabled"
        )
        plain.get_by_role("button", name="Save and add another", exact=True).click()
        pw.expect(plain).to_have_url(url)
        pw.expect(plain.locator("#id_name")).to_have_value("")
        pw.expect(plain.locator("#id_source")).to_have_value(str(source.pk))
        assert not errors, errors
        browser.close()
    # Inspect persistence after Playwright's event loop has stopped.
    assert EvacuationCenter.objects.count() == 2
    center = EvacuationCenter.objects.get(pk=center_id)
    assert center.name == "Synthetic edited form fixture"
    assert center.verification_status == "DRAFT" and center.capacity is None


@pytest.mark.django_db(transaction=True)
def test_source_form_browser(live_server, settings):
    settings.DEBUG = True
    settings.ENABLE_LOCAL_TESTING = True
    get_user_model().objects.create_user(
        email="layout-qa@example.com",
        display_name="Isolated QA Maintainer",
        password="Isolated-layout-QA-2026",
        is_staff=True,
        is_superuser=True,
    )
    editor = get_user_model().objects.create_user(
        email="source-editor-qa@example.com",
        password="Isolated-layout-QA-2026",
        is_staff=True,
    )
    editor.user_permissions.set(Permission.objects.filter(
        content_type__app_label="provenance",
        codename__in=["add_datasource", "change_datasource", "view_datasource"],
    ))
    url = live_server.url + reverse("admin_portal:data-source-create")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    values = {
        "name": "Synthetic source form fixture—not official",
        "organization": "Isolated synthetic QA office",
        "custodian": "Synthetic records role",
        "citation_url": "https://example.test/synthetic-source",
        "coverage_description": "Synthetic QA records only",
        "record_period_start": "2026-01-01",
        "record_period_end": "2026-02-01",
        "received_or_created_on": "2026-02-02",
        "version": "QA-1",
        "permitted_use": "Isolated QA only",
        "limitations": "Synthetic evidence. No agency endorsement or operational use.",
        "processing_notes": "No official dataset was processed.",
        "notes": "Synthetic staff notes",
    }

    def fill_metadata(page):
        for name, value in values.items():
            page.locator(f"#id_{name}").fill(value)
        page.locator("#id_source_type").select_option("OTHER")

    with pw.sync_playwright() as p:
        executable = os.environ.get("FLOODSENSE_QA_BROWSER")
        browser = p.chromium.launch(**({"executable_path": executable} if executable else {}))
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        context.route("https://**", lambda route: route.abort())
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        login(page, live_server.url)
        for width in [1440, 1024, 768, 390, 320]:
            page.set_viewport_size({"width": width, "height": 1000})
            page.goto(url)
            if width > 760 and "sidebar-collapsed" in page.locator("body").get_attribute("class"):
                page.locator(".sidebar__brand-area").hover()
                page.locator("[data-sidebar-toggle]").click()
                settled(page)
            form = page.locator(".source-form")
            pw.expect(form.locator("legend")).to_have_text([
                "Source details", "Coverage and version", "Use and limitations",
                "Processing and notes", "Review and save",
            ])
            fill_metadata(page)
            assert form.locator("textarea").count() == 5
            for left, right in [
                ("name", "source_type"), ("organization", "custodian"),
                ("record_period_start", "record_period_end"),
                ("received_or_created_on", "version"),
            ]:
                first = page.locator(f"#id_{left}").bounding_box()
                second = page.locator(f"#id_{right}").bounding_box()
                assert first["height"] == second["height"] == 46
                assert first["y"] == second["y"] if width > 900 else first["y"] < second["y"]
            no_overflow(page)
            approval = page.locator(".source-form__approval")
            assert approval.get_attribute("open") is None
            if width in [1440, 390]:
                form.screenshot(
                    path=str(OUTPUT / f"source-form-{width}-expanded.png"),
                    animations="disabled",
                    style=".skip-link:not(:focus) { visibility: hidden; }",
                )
            approval.locator("summary").focus()
            page.keyboard.press("Space")
            pw.expect(page.locator("#id_confirm")).to_be_visible()
            for control in form.locator("input:not([type=hidden]), select").all():
                assert control.bounding_box()["height"] == (
                    20 if control.get_attribute("type") == "checkbox" else 46
                )
            page.locator('label[for="id_confirm"]').click()
            pw.expect(page.locator("#id_confirm")).to_be_checked()
            page.locator("#id_confirm").uncheck()
            page.locator('label[for="id_temporary_data"]').click()
            pw.expect(page.locator("#id_temporary_data")).to_be_checked()
            page.locator("#id_temporary_data").uncheck()
            if width > 760:
                page.locator("[data-sidebar-toggle]").click()
                settled(page)
                no_overflow(page)

        # Inline errors retain entered data and connect the summary to invalid controls.
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.locator("#id_record_period_end").fill("2025-12-31")
        page.locator("#id_citation_url").fill("invalid-url")
        page.get_by_role("button", name="Save for review", exact=True).click()
        pw.expect(page.locator(".form-error-summary")).to_be_visible()
        pw.expect(page.locator("#id_record_period_end")).to_have_attribute("aria-invalid", "true")
        pw.expect(page.locator("#id_record_period_end_error")).to_be_visible()
        pw.expect(page.locator("#id_notes")).to_have_value(values["notes"])
        page.locator('.form-error-summary a[href="#id_record_period_end"]').click()
        pw.expect(page.locator("#id_record_period_end")).to_be_focused()
        ids = page.locator(".source-form [id]").evaluate_all("els => els.map(el => el.id)")
        assert len(ids) == len(set(ids))

        # Approval failures reopen the native disclosure and do not silently save.
        page.locator("#id_record_period_end").fill(values["record_period_end"])
        page.locator("#id_citation_url").fill(values["citation_url"])
        page.locator(".source-form__approval summary").click()
        page.locator('button[value="approve"]').click()
        pw.expect(page.locator(".form-error-summary")).to_contain_text("Confirm metadata approval")
        pw.expect(page.locator("#id_confirm")).to_be_visible()
        page.locator("#id_confirm").check()
        page.locator("#id_permitted_use").fill("")
        page.locator('button[value="approve"]').click()
        pw.expect(page.locator(".form-error-summary")).to_contain_text(
            "Approval requires complete metadata"
        )
        page.locator(".source-form").screenshot(
            path=str(OUTPUT / "source-form-approval-error.png"), animations="disabled"
        )
        page.locator("#id_permitted_use").fill(values["permitted_use"])
        page.get_by_role("button", name="Save for review", exact=True).click()
        pw.expect(page).to_have_url(re.compile(r"/management/sources-content/\d+/(?:#.*)?$"))
        source_id = int(urlsplit(page.url).path.rstrip("/").rsplit("/", 1)[1])

        # Editing retains the hidden concurrency token. Approval alone does not release.
        page.goto(live_server.url + reverse("admin_portal:data-source-edit", args=[source_id]))
        assert page.locator("#id_expected_updated_at").input_value()
        pw.expect(page.locator("#id_notes")).to_have_value(values["notes"])
        page.locator("#id_name").fill("Synthetic edited source fixture—not official")
        page.locator(".source-form__approval summary").click()
        page.locator("#id_confirm").check()
        page.locator('button[value="approve"]').click()
        pw.expect(page).to_have_url(re.compile(r"/management/sources-content/\d+/(?:#.*)?$"))

        # Public release remains an explicit, separate action.
        page.goto(url)
        fill_metadata(page)
        page.locator("#id_name").fill("Synthetic releasable QA source—not official")
        page.locator(".source-form__approval summary").click()
        page.locator("#id_confirm").check()
        page.locator('button[value="approve-publish"]').click()
        pw.expect(page).to_have_url(re.compile(r"/management/sources-content/\d+/$"))

        # Without JavaScript, native disclosure and add-another still submit normally.
        plain_context = browser.new_context(
            java_script_enabled=False, viewport={"width": 390, "height": 844}
        )
        plain = plain_context.new_page()
        login(plain, live_server.url)
        plain.goto(url)
        plain.locator(".source-form__approval summary").click()
        pw.expect(plain.locator("#id_confirm")).to_be_visible()
        plain.locator("#id_name").fill("Synthetic no-script source—not official")
        plain.locator("#id_source_type").select_option("OTHER")
        no_overflow(plain)
        plain.get_by_role("button", name="Save and add another", exact=True).click()
        pw.expect(plain).to_have_url(url)
        pw.expect(plain.locator("#id_name")).to_have_value("")

        # An ordinary metadata editor sees routine saves, without empty approval controls.
        limited = browser.new_context(viewport={"width": 390, "height": 844}).new_page()
        login(limited, live_server.url, email="source-editor-qa@example.com")
        limited.goto(url)
        pw.expect(limited.locator(".source-form__approval")).to_have_count(0)
        pw.expect(limited.locator("#id_confirm")).to_have_count(0)
        pw.expect(limited.get_by_role("button", name="Save for review", exact=True)).to_be_visible()
        no_overflow(limited)
        assert not errors, errors
        browser.close()
    assert DataSource.objects.count() == 3
    source = DataSource.objects.get(pk=source_id)
    assert source.name == "Synthetic edited source fixture—not official"
    assert source.status == "APPROVED" and not source.is_publicly_releasable
    released = DataSource.objects.get(name="Synthetic releasable QA source—not official")
    assert released.status == "APPROVED" and released.is_publicly_releasable
    draft = DataSource.objects.get(name="Synthetic no-script source—not official")
    assert draft.status == "PENDING_VALIDATION" and not draft.is_publicly_releasable
