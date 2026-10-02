"""Optional real-browser QA on an isolated pytest live server and synthetic data."""

import os
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from evacuation.imports import stage_batch
from evacuation.models import EvacuationCenter
from provenance.models import DataSource

pw = pytest.importorskip("playwright.sync_api")
OUTPUT = Path(__file__).resolve().parents[1] / "tmp" / "record-workflow-qa"


@pytest.mark.django_db(transaction=True)
def test_responsive_entry_inline_source_review_and_import(live_server, settings):
    settings.WHITENOISE_USE_FINDERS = True
    settings.MAPBOX_ACCESS_TOKEN = ""
    actor = get_user_model().objects.create_user(
        email="synthetic-layout@example.test",
        password="Isolated-QA-password",
        display_name="Synthetic workflow QA",
        is_staff=True,
        is_superuser=True,
    )
    source = DataSource.objects.create(
        name="Synthetic long source " * 8,
        organization="Synthetic QA organization",
        custodian="Synthetic QA unit",
        coverage_description="Synthetic tests only",
        source_type="OTHER",
        status="PENDING_VALIDATION",
        permitted_use="Tests only",
        limitations="Synthetic limitations, not operational data. " * 8,
    )
    center = EvacuationCenter.objects.create(
        name="Synthetic center " * 8,
        address="Synthetic long address. " * 8,
        latitude="0.3",
        longitude="0.2",
        source=source,
        limitations="Synthetic center limitations. " * 8,
    )
    batch = stage_batch(
        upload=SimpleUploadedFile(
            "synthetic.csv",
            b"name,address,area_code,latitude,longitude,limitations\n"
            b"Synthetic A,A,,0.41,0.21,\nSynthetic B,B,,999,0.3,\n",
        ),
        source=source,
        actor=actor,
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with pw.sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=os.getenv(
                "FLOODSENSE_QA_BROWSER", r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            ),
            headless=True,
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(live_server.url + "/management/login/")
        page.get_by_label("Work email").fill(actor.email)
        page.get_by_label("Password", exact=True).fill("Isolated-QA-password")
        page.locator("button[type=submit]").click()
        for width in (1440, 390, 320):
            page.set_viewport_size({"width": width, "height": 900})
            for route, label in (
                ("evacuation-centers/", "centers"),
                ("evacuation-centers/new/", "center-form"),
                (f"evacuation-centers/{center.pk}/", "center-detail"),
                ("sources-content/new/", "source-form"),
                (f"sources-content/{source.pk}/", "source-detail"),
                ("review/centers/", "review"),
                ("evacuation-centers/import/", "upload"),
                (f"evacuation-centers/import/{batch.pk}/", "import-preview"),
            ):
                page.goto(live_server.url + "/management/" + route)
                if label == "import-preview":
                    page.locator("[data-batch-map] canvas").first.wait_for(state="visible")
                    canvas_box = page.locator("[data-batch-map] canvas").first.bounding_box()
                    assert canvas_box["height"] > 0
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                    width,
                    label,
                )
                page.screenshot(path=str(OUTPUT / f"{label}-{width}.png"), full_page=True)
            page.goto(live_server.url + "/management/evacuation-centers/new/")
            draft_name = f"Synthetic unsaved form value {width}"
            page.get_by_label("Name", exact=True).fill(draft_name)
            page.get_by_role("button", name="Create source here", exact=True).focus()
            page.keyboard.press("Enter")
            dialog = page.get_by_role("dialog")
            pw.expect(dialog).to_be_visible()
            dialog.get_by_label("Name", exact=True).fill("Synthetic inline source")
            dialog.get_by_label("Citation url", exact=True).fill("not-a-valid-url")
            dialog.get_by_role("button", name="Save for review", exact=True).click()
            pw.expect(dialog.get_by_label("Name", exact=True)).to_have_value(
                "Synthetic inline source"
            )
            pw.expect(dialog.locator(".field-error").first).to_be_visible()
            dialog.get_by_label("Source type", exact=True).select_option("OTHER")
            dialog.get_by_label("Citation url", exact=True).fill("")
            page.screenshot(path=str(OUTPUT / f"inline-source-{width}.png"), full_page=True)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            dialog.get_by_role("button", name="Save for review", exact=True).click()
            pw.expect(dialog).not_to_be_visible()
            pw.expect(page.locator("#id_name")).to_have_value(draft_name)
            pw.expect(page.locator("#id_source option:checked")).to_have_text(
                "Synthetic inline source"
            )
            page.get_by_label("Address", exact=True).fill("Synthetic address")
            page.get_by_label("Latitude", exact=True).fill("0.3")
            page.get_by_label("Longitude", exact=True).fill(str(width / 10000))
            page.get_by_label("Publication status", exact=True).select_option("PENDING_VALIDATION")
            page.get_by_role("button", name="Save and submit for review", exact=True).click()
            pw.expect(page.locator("main")).to_contain_text("In review")
            # One editor page, one submit click: no intermediate confirmation page.
            page.goto(live_server.url + "/management/review/centers/")
            page.get_by_label(
                "Select all matching records, not just checked rows (maximum 1,000)"
            ).check()
            page.get_by_label("Bulk action", exact=True).select_option("submit")
            page.get_by_role(
                "button", name="Validate selection and preview batch", exact=True
            ).click()
            pw.expect(page.locator("main")).to_contain_text("ineligible")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(OUTPUT / f"batch-confirm-{width}.png"), full_page=True)
        assert not page_errors, page_errors
        page.goto(live_server.url + f"/management/evacuation-centers/import/{batch.pk}/")
        page.locator('input[name="confirm"]').check()
        page.get_by_role("button", name="Import 1 unverified drafts", exact=True).click()
        pw.expect(page.locator("main")).to_contain_text("Imported 1 drafts")
        pw.expect(page.locator("main")).to_contain_text("1 invalid rows were NOT imported")
        browser.close()
