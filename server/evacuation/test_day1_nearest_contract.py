"""Synthetic, in-memory wire fixtures: no center records or DB access authorized."""

import json
from copy import deepcopy
from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from django.urls import resolve
from geography.constants import BACOOR_REFERENCE_LIMITATION, BACOOR_REFERENCE_WARNING
from rest_framework.renderers import JSONRenderer

from .contracts import (
    CENTER_LIMITATION,
    DISTANCE_METHOD,
    DISTANCE_WARNING,
    EMPTY_DISTANCE_WARNING,
    EMPTY_WARNING,
    NEAREST_CENTER_PATH,
)
from .serializers import (
    CenterBarangaySerializer,
    NearestCenterRequestSerializer,
    NearestCenterResponseSerializer,
    PublicCenterSerializer,
)


@pytest.fixture
def center():
    return {
        "public_identifier": "a95e27e1-7fb0-4c41-871c-f8e13b2534b8",
        "name": "SYNTHETIC CONTRACT CENTER - NOT A REAL FACILITY",
        "address": "Fictional test address",
        "barangay": {"psgc_code": "0000000000", "name": "Synthetic contract barangay"},
        "latitude": 14.4629,
        "longitude": 120.9647,
        "approximate_distance": 842.6,
        "distance_unit": "meters",
        "verified_on": "2026-09-19",
        "source_attribution": "Synthetic test organization",
        "limitations": [
            CENTER_LIMITATION,
            BACOOR_REFERENCE_WARNING,
            BACOOR_REFERENCE_LIMITATION,
        ],
    }


def envelope(centers):
    return {
        "centers": centers,
        "distance_method": DISTANCE_METHOD,
        "warnings": [DISTANCE_WARNING] if centers else [EMPTY_WARNING, EMPTY_DISTANCE_WARNING],
    }


@pytest.mark.parametrize("point", [(0, 0), (-90, -180), (90, 180), (14.4629, 120.9647)])
def test_request_accepts_wgs84_numbers_and_default_limit(point):
    serializer = NearestCenterRequestSerializer(
        data=dict(zip(("latitude", "longitude"), point, strict=True))
    )
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["limit"] == 3


@pytest.mark.parametrize("field", ["latitude", "longitude"])
@pytest.mark.parametrize(
    "value",
    [
        None,
        "14.4629",
        True,
        False,
        float("nan"),
        float("inf"),
        -float("inf"),
        [],
        {},
        Decimal("14.46"),
        10**400,
    ],
    ids=[
        "null",
        "string",
        "true",
        "false",
        "nan",
        "inf",
        "negative-inf",
        "list",
        "object",
        "decimal-not-json",
        "overflow",
    ],
)
def test_request_rejects_non_json_or_non_finite_numbers(field, value):
    serializer = NearestCenterRequestSerializer(data={"latitude": 0, "longitude": 0, field: value})
    assert not serializer.is_valid()
    assert field in serializer.errors


@pytest.mark.parametrize(
    "field,value",
    [("latitude", -90.001), ("latitude", 90.001), ("longitude", -180.001), ("longitude", 180.001)],
)
def test_request_rejects_out_of_range(field, value):
    serializer = NearestCenterRequestSerializer(data={"latitude": 0, "longitude": 0, field: value})
    assert not serializer.is_valid()
    assert field in serializer.errors


@pytest.mark.parametrize("field", ["latitude", "longitude"])
def test_request_requires_both_coordinates(field):
    payload = {"latitude": 0, "longitude": 0}
    del payload[field]
    serializer = NearestCenterRequestSerializer(data=payload)
    assert not serializer.is_valid()
    assert serializer.errors[field] == ["This field is required."]


@pytest.mark.parametrize("value", [0, -1, 11, 3.5, 3.0, "3", True, False, None, [], {}])
def test_request_rejects_invalid_limits(value):
    serializer = NearestCenterRequestSerializer(
        data={"latitude": 0, "longitude": 0, "limit": value}
    )
    assert not serializer.is_valid()
    assert "limit" in serializer.errors


@pytest.mark.parametrize("limit", [1, 3, 10])
def test_request_accepts_bounded_integer_limits(limit):
    serializer = NearestCenterRequestSerializer(
        data={"latitude": 0, "longitude": 0, "limit": limit}
    )
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["limit"] == limit


@pytest.mark.parametrize("payload", [None, [], "coordinate", 14])
def test_request_requires_object(payload):
    serializer = NearestCenterRequestSerializer(data=payload)
    assert not serializer.is_valid()


def test_unknown_keys_and_validation_errors_do_not_reflect_input():
    serializer = NearestCenterRequestSerializer(
        data={"latitude": 14.123456789, "longitude": 120.987654321, "14.123456789": "private"}
    )
    assert not serializer.is_valid()
    assert serializer.errors == {"non_field_errors": ["Unknown fields are not allowed."]}
    serializer = NearestCenterRequestSerializer(data={"latitude": "14.123456789", "longitude": 181})
    assert not serializer.is_valid()
    assert serializer.errors["latitude"] == ["Enter a JSON number."]
    assert "14.123456789" not in str(serializer.errors)
    assert "181" not in str(serializer.errors)


def test_response_round_trips_real_json_without_writes(center):
    # pytest-django blocks DB access: these tests must remain database-independent.
    payload = envelope([center])
    serializer = NearestCenterResponseSerializer(data=payload)
    assert serializer.is_valid(), serializer.errors
    assert json.loads(JSONRenderer().render(serializer.data)) == payload


@pytest.mark.parametrize(
    "field",
    [
        "public_identifier",
        "name",
        "address",
        "barangay",
        "latitude",
        "longitude",
        "approximate_distance",
        "distance_unit",
        "verified_on",
        "source_attribution",
        "limitations",
    ],
)
@pytest.mark.parametrize("missing", [True, False], ids=["missing", "null"])
def test_all_center_fields_are_required_and_non_null(center, field, missing):
    if missing:
        del center[field]
    else:
        center[field] = None
    serializer = PublicCenterSerializer(data=center)
    assert not serializer.is_valid()
    assert field in serializer.errors


@pytest.mark.parametrize(
    "field,value",
    [
        ("public_identifier", "123"),
        ("public_identifier", 1),
        ("public_identifier", "a95e27e17fb04c41871cf8e13b2534b8"),
        ("public_identifier", UUID("a95e27e1-7fb0-4c41-871c-f8e13b2534b8")),
        ("name", " "),
        ("address", ""),
        ("source_attribution", "\t"),
        ("source_attribution", 42),
        ("name", "private\x01text"),
        ("latitude", -91),
        ("longitude", 181),
        ("latitude", True),
        ("longitude", "120"),
        ("latitude", float("nan")),
        ("longitude", float("inf")),
        ("approximate_distance", -0.01),
        ("approximate_distance", float("nan")),
        ("approximate_distance", float("inf")),
        ("approximate_distance", True),
        ("approximate_distance", "842.6"),
        ("distance_unit", "kilometers"),
        ("verified_on", "2026-02-30"),
        ("verified_on", "2026-9-19"),
        ("verified_on", "2026-09-19T00:00:00Z"),
        ("verified_on", date(2026, 9, 19)),
        ("limitations", []),
        ("limitations", "Safe"),
        ("limitations", [" "]),
        ("limitations", [42]),
        ("limitations", [{"notes": "private"}]),
    ],
)
def test_response_rejects_malformed_public_values(center, field, value):
    center[field] = value
    serializer = PublicCenterSerializer(data=center)
    assert not serializer.is_valid()
    assert field in serializer.errors


@pytest.mark.parametrize(
    "psgc",
    [
        1234567890,
        "123",
        "PSGC_0000000000",
        "00000000000",
        "0000000000\n",
        " 0000000000",
        "٠٠٠٠٠٠٠٠٠٠",
        None,
    ],
)
def test_barangay_code_is_exactly_ten_ascii_digits(center, psgc):
    center["barangay"]["psgc_code"] = psgc
    serializer = PublicCenterSerializer(data=center)
    assert not serializer.is_valid()
    assert "barangay" in serializer.errors


@pytest.mark.parametrize("field", ["psgc_code", "name"])
def test_barangay_fields_are_required(center, field):
    del center["barangay"][field]
    serializer = PublicCenterSerializer(data=center)
    assert not serializer.is_valid()


@pytest.mark.parametrize("location", ["envelope", "center", "barangay"])
@pytest.mark.parametrize(
    "private_field",
    [
        "id",
        "contact_information",
        "capacity",
        "notes",
        "permitted_use",
        "reviewed_by",
        "change_message",
        "request_coordinate",
        "susceptibility",
        "expert_rules",
    ],
)
def test_private_fields_are_not_in_schema_and_are_rejected(center, location, private_field):
    for schema in (
        NearestCenterResponseSerializer,
        PublicCenterSerializer,
        CenterBarangaySerializer,
    ):
        assert private_field not in schema().fields
    payload = envelope([center])
    target = {"envelope": payload, "center": center, "barangay": center["barangay"]}[location]
    target[private_field] = "PRIVATE SENTINEL"
    serializer = NearestCenterResponseSerializer(data=payload)
    assert not serializer.is_valid()
    assert "PRIVATE SENTINEL" not in str(serializer.errors)


def test_empty_results_have_exact_success_envelope():
    serializer = NearestCenterResponseSerializer(data=envelope([]))
    assert serializer.is_valid(), serializer.errors
    assert serializer.data == {
        "centers": [],
        "distance_method": "APPROXIMATE_STRAIGHT_LINE",
        "warnings": [
            "No eligible verified evacuation centers are currently available for this location.",
            "Distances, when available, are approximate straight-line measurements "
            "and are not route-safety recommendations.",
        ],
    }


@pytest.mark.parametrize("field", ["centers", "distance_method", "warnings"])
def test_envelope_fields_are_required(field):
    payload = envelope([])
    del payload[field]
    serializer = NearestCenterResponseSerializer(data=payload)
    assert not serializer.is_valid()


@pytest.mark.parametrize("centers_present", [False, True])
def test_result_warnings_are_mandatory_and_exact(center, centers_present):
    payload = envelope([center] if centers_present else [])
    payload["warnings"] = ["A safe route is available."]
    serializer = NearestCenterResponseSerializer(data=payload)
    assert not serializer.is_valid()


def test_envelope_rejects_wrong_method_duplicate_ids_and_excess_results(center):
    payload = envelope([center])
    payload["distance_method"] = "ROAD_DISTANCE"
    assert not NearestCenterResponseSerializer(data=payload).is_valid()
    assert not NearestCenterResponseSerializer(data=envelope([center, center])).is_valid()
    centers = []
    for index in range(11):
        item = deepcopy(center)
        item["public_identifier"] = str(UUID(int=index + 1))
        centers.append(item)
    assert NearestCenterResponseSerializer(data=envelope(centers[:10])).is_valid()
    assert not NearestCenterResponseSerializer(data=envelope(centers)).is_valid()


def test_zero_distance_and_literal_text_are_valid(center):
    center["approximate_distance"] = 0
    center["name"] = '<script>alert("synthetic")</script>'
    serializer = PublicCenterSerializer(data=center)
    assert serializer.is_valid(), serializer.errors
    # Consumers must escape/render as text; schema validation is not an HTML sanitizer.
    assert serializer.data["name"] == center["name"]


def test_day3_registers_the_frozen_endpoint_path():
    # Day 3 intentionally replaces the historical route-absence assertion.
    assert resolve(NEAREST_CENTER_PATH).view_name == "evacuation:nearest-centers"
