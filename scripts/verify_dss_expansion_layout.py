"""Optional browser QA against pytest's isolated database and live server.

Requires local QA-only Playwright; uses an installed Chrome executable.
Run explicitly with pytest, not against the developer application database.
"""

import os
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from dss.models import DSSContentBlock, DSSFlowVersion, DSSOption, DSSOutcome, DSSQuestion
from expert.models import SusceptibilityLevel
from provenance.models import DataSource

pw = pytest.importorskip("playwright.sync_api")
OUTPUT = Path(__file__).resolve().parents[1] / "tmp" / "dss-expansion-qa"


@pytest.mark.django_db(transaction=True)
def test_structured_dss_responsive_preview(live_server, settings):
    settings.WHITENOISE_USE_FINDERS = True
    get_user_model().objects.create_user(
        email="dss-layout@example.com",
        password="Isolated-QA-password",
        display_name="DSS QA",
        is_staff=True,
        is_superuser=True,
    )
    source = DataSource.objects.create(
        name="Synthetic public-safe provenance " + "Long source title " * 8,
        organization="Synthetic QA organization",
        source_type="DEMONSTRATION",
        status="DEMONSTRATION",
        limitations="Synthetic demonstration for interface testing only.",
    )
    level = SusceptibilityLevel.objects.create(
        code="HIGH",
        label="High",
        display_order=3,
        definition="Synthetic",
        source=source,
        status="DEMONSTRATION",
        map_color="#CC0000",
        is_enabled=True,
    )
    flow = DSSFlowVersion.objects.create(
        code="preparedness",
        version="qa-1",
        title="Household preparedness review",
        operating_mode="DEMONSTRATION",
        data_status="DEMONSTRATION",
        source=source,
        effective_date=timezone.localdate(),
        limitations="Pending expert validation — demonstration only.",
        attribution="Synthetic QA content, not BDRRMO authored.",
    )
    flow.susceptibility_levels.add(level)
    question = DSSQuestion.objects.create(
        flow=flow,
        code="support",
        prompt="Has your household discussed support needs?",
        explanatory_text="Discuss the plan with a trusted helper.",
        is_start=True,
    )
    outcome = DSSOutcome.objects.create(
        flow=flow,
        code="plan",
        title="Review your household plan",
        instruction="Use this synthetic checklist to review readiness.",
        source=source,
        category="PREPARE",
    )
    DSSOption.objects.create(
        question=question, code="yes", label="Review household checklist", outcome=outcome
    )
    for order, phase, kind, title in (
        (1, "BEFORE", "HOUSEHOLD_ACTION", "Supplies and documents"),
        (2, "DURING", "HOUSEHOLD_ACTION", "Educational reference during a flood"),
        (3, "AFTER", "HOUSEHOLD_ACTION", "Educational reference after a flood"),
        (4, "ALWAYS", "MONITORING_REFERENCE", "What responders may observe"),
        (5, "ALWAYS", "AUTHORITY_ACTIVITY", "Authority coordination reference"),
    ):
        DSSContentBlock.objects.create(
            flow=flow,
            title=title,
            body="Synthetic long-text reference. " * 12,
            phase=phase,
            content_type=kind,
            audience="RESIDENT",
            display_order=order,
            source=source,
            data_status="DEMONSTRATION",
            limitations="No current condition is implied.",
        )
    empty = DSSFlowVersion.objects.create(
        code="qa-empty",
        version="1",
        title="Incomplete QA draft",
        operating_mode="DEMONSTRATION",
        data_status="DEMONSTRATION",
        source=source,
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with pw.sync_playwright() as p:
        executable = os.getenv(
            "FLOODSENSE_QA_BROWSER", r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        )
        browser = p.chromium.launch(executable_path=executable, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(live_server.url + "/management/login/")
        page.get_by_label("Work email").fill("dss-layout@example.com")
        page.get_by_label("Password", exact=True).fill("Isolated-QA-password")
        page.locator("button[type=submit]").click()
        pw.expect(page).to_have_url(live_server.url + "/management/")
        for width in (1440, 390, 360):
            page.set_viewport_size({"width": width, "height": 900})
            for route, label in (
                ("flows/", "inventory"),
                (f"flows/{flow.pk}/", "detail"),
                (f"flows/{flow.pk}/edit/", "editor"),
                (f"flows/{flow.pk}/preview/", "preview"),
            ):
                page.goto(live_server.url + "/management/dss-content/" + route)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                    width,
                    label,
                )
                if label == "preview":
                    pw.expect(page.locator("#dss-resident-preview h2")).to_have_text(flow.title)
                    page.get_by_role(
                        "button", name="Review household checklist", exact=True
                    ).click()
                    pw.expect(page.locator("#dss-resident-preview")).to_contain_text(outcome.title)
                    page.locator("#dss-resident-preview details summary").click()
                    pw.expect(page.locator("#dss-resident-preview")).to_contain_text(
                        "FloodSense does not monitor these sources live."
                    )
                    page.get_by_role("button", name="Back", exact=True).click()
                    pw.expect(
                        page.get_by_role("button", name="Review household checklist", exact=True)
                    ).to_be_visible()
                    page.get_by_role("button", name="Restart", exact=True).click()
                    if width == 360:
                        page.locator("html").evaluate("el => el.style.fontSize='150%'")
                        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(path=str(OUTPUT / f"portal-{label}-{width}.png"), full_page=True)
            page.goto(live_server.url + "/management/dss-content/flows/new/")
            page.get_by_label("Title", exact=True).fill("Preserved input on error")
            page.get_by_role("button", name="Save draft", exact=True).click()
            pw.expect(page.get_by_label("Title", exact=True)).to_have_value(
                "Preserved input on error"
            )
            pw.expect(page.locator(".field-error").first).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.goto(live_server.url + f"/management/dss-content/flows/{flow.pk}/preview/")
        page.get_by_role("button", name="Review household checklist", exact=True).focus()
        page.keyboard.press("Enter")
        pw.expect(page.locator("#dss-resident-preview")).to_contain_text(outcome.title)
        page.get_by_role("button", name="Restart", exact=True).focus()
        page.keyboard.press("Enter")
        pw.expect(
            page.get_by_role("button", name="Review household checklist", exact=True)
        ).to_be_visible()
        page.goto(live_server.url + "/management/dss-content/flows/?q=missing-qa-record")
        pw.expect(page.locator("main")).to_contain_text("No structured flows are available")
        page.screenshot(path=str(OUTPUT / "portal-empty-360.png"), full_page=True)
        page.goto(live_server.url + f"/management/dss-content/flows/{empty.pk}/preview/")
        pw.expect(page.locator("#dss-resident-preview")).to_contain_text(
            "No start question is available"
        )
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(OUTPUT / "portal-incomplete-360.png"), full_page=True)
        assert not page_errors, page_errors
        browser.close()
