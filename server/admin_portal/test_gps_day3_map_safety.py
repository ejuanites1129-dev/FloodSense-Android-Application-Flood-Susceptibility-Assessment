"""Day 3 map/public-data regressions using synthetic isolated-database rows."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.urls import reverse
from geography.constants import BACOOR_REFERENCE_SOURCE_NAME
from geography.models import GeographicArea
from provenance.models import DataSource

from .test_dashboard import DashboardHTML


@pytest.fixture
def map_records(db):
    reference = DataSource.objects.create(
        name=BACOOR_REFERENCE_SOURCE_NAME,
        organization="Synthetic custodian",
        source_type="AGENCY_DATASET",
        status="PENDING_VALIDATION",
        is_publicly_releasable=True,
    )
    geometry = MultiPolygon(Polygon.from_bbox((0, 0, 1, 1)), srid=4326)
    area = GeographicArea.objects.create(
        code="PSGC_0000000000",
        name="SYNTHETIC administrative area",
        area_type="BARANGAY",
        geometry=geometry,
        source=reference,
        status="PENDING_VALIDATION",
        is_enabled=True,
    )
    provisional = DataSource.objects.create(
        name="SYNTHETIC MGB-LIKE SOURCE - NO REAL DATA",
        organization="Synthetic custodian",
        source_type="AGENCY_DATASET",
        status="PENDING_VALIDATION",
        is_publicly_releasable=True,
    )
    GeographicArea.objects.create(
        code="SYNTHETIC_PROVISIONAL",
        name="PRIVATE_PROVISIONAL_SENTINEL",
        area_type="OTHER",
        geometry=geometry,
        source=provisional,
        status="PENDING_VALIDATION",
        is_enabled=True,
    )
    staff = get_user_model().objects.create_user(
        email="synthetic-map-day3@example.test",
        display_name="Synthetic reviewer",
        is_staff=True,
    )
    return area, staff


def test_map_attribution_neutrality_and_unavailable_layers_are_server_rendered(client, map_records):
    area, staff = map_records
    client.force_login(staff)
    response = client.get(reverse("admin_portal:map-data"))
    assert response.status_code == 200
    html = DashboardHTML(response)
    assert html.select("a", href="https://www.openstreetmap.org/copyright")
    text = response.content.decode()
    for notice in (
        "OpenStreetMap is visual context only",
        "No data are published.",
        "not City-verified",
        "Not real Bacoor classifications.",
        "not been approved for operational or resident publication",
        "A geographic record marked Approved alone does not establish a susceptibility layer.",
    ):
        assert notice in text
    for layer in ("mgb", "approved"):
        assert "disabled" in html.select("input", id=f"layer-{layer}")[0]["attrs"]
    assert "PRIVATE_PROVISIONAL_SENTINEL" not in text
    assert set(response.context["map_data"]["payload"]["layers"]) == {
        "administrative",
        "demonstration",
    }
    feature = response.context["map_data"]["payload"]["layers"]["administrative"]["features"][0]
    assert feature["id"] == str(area.pk)
    assert set(feature["properties"]) == {"record_id", "name", "code", "area_type", "layer_kind"}


def test_no_script_selection_and_keyboard_alternative_keep_long_warnings(
    client, map_records, monkeypatch
):
    area, staff = map_records
    warning = ("SYNTHETIC long limitation. " * 40).strip()
    monkeypatch.setattr("admin_portal.services.map_data.BACOOR_REFERENCE_LIMITATION", warning)
    client.force_login(staff)
    response = client.get(reverse("admin_portal:map-data"), {"area": area.pk})
    html = DashboardHTML(response)
    assert html.select("noscript")
    assert html.select("form", id="area-selection-form", method="get")
    button = html.select("button", name="area", value=str(area.pk))[0]
    assert button["attrs"]["aria-pressed"] == "true"
    assert html.select("div", id="geographic-map", tabindex="0")
    assert html.select("p", id="map-keyboard-help")
    assert response.context["map_data"]["selected"]["id"] == str(area.pk)
    assert warning in response.content.decode()
    assert "area list and details independently" in response.content.decode()


def test_provisional_nonreference_geometry_never_enters_resident_collections(client, map_records):
    # Public APIs are read-only dependencies; no geography implementation changes.
    for route in (
        "/api/v1/geography/areas/?mode=official",
        "/api/v1/geography/reference-boundaries/",
    ):
        response = client.get(route)
        assert response.status_code == 200
        assert "PRIVATE_PROVISIONAL_SENTINEL" not in json.dumps(response.json())
