"""Focused Day 2 presentation checks, with separate database permission tests."""

from datetime import date
from html.parser import HTMLParser
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import reverse
from evacuation.models import EvacuationCenter
from evacuation.workflow import TRANSITIONS
from geography.models import GeographicArea
from provenance.models import DataSource

from .forms import EvacuationCenterFilterForm, EvacuationCenterForm, EvacuationTransitionForm
from .views import _portal_context


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def synthetic_center():
    source = DataSource(
        pk=1,
        name="SYNTHETIC PUBLIC SOURCE",
        organization="Synthetic custodian",
        source_type="AGENCY_DATASET",
        status="APPROVED",
        is_publicly_releasable=False,
    )
    area = GeographicArea(pk=1, code="PSGC_0000000000", name="SYNTHETIC BARANGAY")
    center = EvacuationCenter(
        pk=1,
        source=source,
        geographic_area=area,
        name="SYNTHETIC CENTER - NOT A REAL FACILITY",
        address="Synthetic address",
        latitude=0,
        longitude=0,
        verified_on=date(2026, 9, 19),
    )
    center.portal_transitions = []
    return center


def render_center_page(template, **values):
    request = RequestFactory().get("/management/evacuation-centers/")
    request.user = get_user_model()(
        display_name="Synthetic reviewer",
        email="synthetic@example.test",
        is_staff=True,
        is_superuser=True,
        is_active=True,
    )
    context = _portal_context(request, active_section="evacuation-centers")
    context.update(
        center=synthetic_center(),
        can_change=True,
        can_add=True,
        openlayers_root="/missing-map-library",
    )
    context.update(values)
    return render_to_string(f"admin_portal/{template}", context, request=request)


def no_query_form(data=None):
    form = EvacuationCenterForm(data)
    form.fields["source"].queryset = DataSource.objects.none()
    form.fields["geographic_area"].queryset = GeographicArea.objects.none()
    return form


def test_public_id_is_text_only_and_long_content_is_escaped():
    center = synthetic_center()
    center.name = '<script>alert("SYNTHETIC")</script>'
    center.address = "UNBROKENSYNTHETIC" * 40
    html = render_center_page("evacuation_center_detail.html", center=center)
    assert str(center.public_id) in html
    assert "&lt;script&gt;" in html and '<script>alert("SYNTHETIC")</script>' not in html
    assert center.address in html
    assert not any(
        attrs.get("name") in {"public_id", "public_identifier"}
        for tag, attrs in Elements(html).tags
        if tag in {"input", "select", "textarea"}
    )
    assert "not an authorization token" in html
    assert "Source publicly releasable" in html
    assert "Boundary association identifies an administrative area" in html


@pytest.mark.parametrize(
    "template",
    [
        "evacuation_center_detail.html",
        "evacuation_center_list.html",
        "evacuation_center_form.html",
        "evacuation_transition_confirm.html",
    ],
)
def test_center_pages_have_safety_copy_landmark_and_skip_link(template):
    html = render_center_page(
        template,
        filters=EvacuationCenterFilterForm(),
        center_page=Paginator([], 25).get_page(1),
        form=no_query_form()
        if "form.html" in template
        else EvacuationTransitionForm(action="verify"),
        form_mode="create",
        transition=TRANSITIONS["verify"],
    )
    assert "Verified does not mean currently open" in html
    assert "does not guarantee space or live capacity" in html
    assert "Verification alone does not make a record eligible" in html
    assert "not road distance or a safety recommendation" in html
    elements = Elements(html).tags
    assert any(tag == "main" and attrs.get("id") == "main-content" for tag, attrs in elements)
    assert any(tag == "a" and attrs.get("href") == "#main-content" for tag, attrs in elements)
    assert any(tag == "h1" for tag, _ in elements)
    assert "admin_portal/css/no_script.css" in html


def test_invalid_draft_has_linked_summary_and_inline_error_ids():
    form = no_query_form({"latitude": "91", "longitude": "0"})
    assert not form.is_valid()
    html = render_center_page("evacuation_center_form.html", form=form, form_mode="create")
    tags = Elements(html).tags
    assert "Review the form errors" in html
    assert any(tag == "a" and attrs.get("href") == "#id_latitude" for tag, attrs in tags)
    assert any(attrs.get("id") == "id_latitude_error" for _, attrs in tags)
    assert any(
        tag == "input" and attrs.get("id") == "id_latitude" and attrs.get("aria-invalid") == "true"
        for tag, attrs in tags
    )
    controls = [
        attrs
        for tag, attrs in tags
        if tag in {"input", "select", "textarea"} and attrs.get("type") != "hidden"
    ]
    labels = {attrs.get("for") for tag, attrs in tags if tag == "label"}
    assert all(control.get("id") in labels for control in controls)
    assert "public_id" not in form.fields
    assert "public_identifier" not in form.fields
    assert "verify the coordinates independently" in html


def test_verification_errors_and_capacity_help_are_associated():
    form = EvacuationTransitionForm({"expected_status": "IN_REVIEW"}, action="verify")
    assert not form.is_valid()
    html = render_center_page(
        "evacuation_transition_confirm.html", form=form, transition=TRANSITIONS["verify"]
    )
    tags = Elements(html).tags
    assert any(attrs.get("id") == "id_capacity_helptext" for _, attrs in tags)
    assert any(attrs.get("id") == "id_confirm_error" for _, attrs in tags)
    assert "Review the form errors" in html


def test_empty_center_list_does_not_claim_no_facilities_exist():
    html = render_center_page(
        "evacuation_center_list.html",
        filters=EvacuationCenterFilterForm(),
        center_page=Paginator([], 25).get_page(1),
    )
    assert "No evacuation centers match this view" in html
    assert "No records are generated automatically" in html
    assert "exposed through a resident API by this module" in html


def test_keyboard_focus_and_narrow_long_text_styles_are_present():
    root = Path(__file__).parent / "static" / "admin_portal" / "css"
    operations = (root / "operations.css").read_text()
    shell = (root / "admin_portal.css").read_text()
    assert ":is(input, select, textarea, a, button):focus-visible" in operations
    assert "overflow-wrap: anywhere" in operations
    assert ".public-identifier" in operations
    assert "@media (max-width: 420px)" in operations
    assert ".skip-link:focus" in shell
    assert "visibility: hidden" in shell and "visibility: visible" in shell
    no_script = (root / "no_script.css").read_text()
    assert "position: static" in no_script and "visibility: visible" in no_script


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["anonymous", "nonstaff", "staff_without_permission"])
def test_center_pages_remain_permission_protected(client, role):
    if role != "anonymous":
        user = get_user_model().objects.create_user(
            email="synthetic-access@example.test",
            password=None,
            is_staff=role == "staff_without_permission",
        )
        client.force_login(user)
    for name, args in (
        ("evacuation-centers", ()),
        ("evacuation-center-create", ()),
        ("evacuation-center-detail", (999,)),
        ("evacuation-center-edit", (999,)),
        ("evacuation-center-transition", (999, "verify")),
    ):
        response = client.get(reverse(f"admin_portal:{name}", args=args))
        assert response.status_code == (302 if role == "anonymous" else 403)


@pytest.mark.django_db
def test_authorized_staff_sees_read_only_parameters_and_filtered_empty_state(client):
    staff = get_user_model().objects.create_user(
        email="synthetic-reader@example.test", password=None, is_staff=True
    )
    staff.user_permissions.set(
        Permission.objects.filter(codename__in=["view_scenariooption", "view_evacuationcenter"])
    )
    client.force_login(staff)
    settings = client.get(reverse("admin_portal:settings"))
    rainfall = client.get(reverse("admin_portal:rainfall-references"))
    assert settings.status_code == rainfall.status_code == 200
    assert b"Read-only foundation" in settings.content
    assert b"Parameter changes await governance approval" in settings.content
    assert "Scenario inputs—not live rainfall" in rainfall.content.decode()
    assert b"Create rainfall" not in rainfall.content and b"Edit rainfall" not in rainfall.content
    assert client.post(reverse("admin_portal:settings")).status_code == 405
    assert client.post(reverse("admin_portal:rainfall-references")).status_code == 405
    response = client.get(reverse("admin_portal:evacuation-centers"), {"q": "SYNTHETIC NO MATCH"})
    assert b"clear filters" in response.content
    assert b"does not mean no facilities exist" in response.content
