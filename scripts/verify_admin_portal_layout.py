"""Optional browser acceptance checks. Run explicitly with pytest and Playwright installed.

Uses only pytest's isolated database and live_server. Screenshots go to tmp/portal-layout-qa.
Set FLOODSENSE_QA_BROWSER to a Chromium executable if bundled browsers are unavailable.
"""

import os
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon
from geography.models import GeographicArea
from provenance.models import DataSource

pw = pytest.importorskip("playwright.sync_api")
OUTPUT = Path(__file__).resolve().parents[1] / "tmp" / "portal-layout-qa"


def login(page, url):
    page.goto(url + "/management/login/")
    page.get_by_label("Work email").fill("layout-qa@example.com")
    page.get_by_label("Password", exact=True).fill("Isolated-layout-QA-2026")
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
        pw.expect(page.locator(".dashboard-metrics .metric-card")).to_have_count(5)
        assert page.locator("#review-attention").count() == 0
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
        plain.get_by_role("link", name="Reports", exact=True).click()
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
