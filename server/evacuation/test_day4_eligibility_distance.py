"""Day 4 current-state eligibility and distance regressions using synthetic data."""

from decimal import Decimal
from uuid import UUID

import pytest
from provenance.models import PublicationStatus

from .contracts import EMPTY_DISTANCE_WARNING, EMPTY_WARNING
from .models import EvacuationCenter
from .services import find_nearest_eligible_centers
from .test_day2_nearest_service import center_factory as center_factory
from .test_day2_nearest_service import layer as layer


def lookup(latitude=0, longitude=0, limit=3):
    return find_nearest_eligible_centers(latitude=latitude, longitude=longitude, limit=limit)


def assert_empty(result):
    assert result == {
        "centers": [],
        "distance_method": "APPROXIMATE_STRAIGHT_LINE",
        "warnings": [EMPTY_WARNING, EMPTY_DISTANCE_WARNING],
    }


@pytest.mark.parametrize(
    "target,changes",
    [
        ("center", {"verification_status": EvacuationCenter.VerificationStatus.DRAFT}),
        ("center", {"verification_status": EvacuationCenter.VerificationStatus.IN_REVIEW}),
        ("center", {"verification_status": EvacuationCenter.VerificationStatus.INACTIVE}),
        ("center", {"publication_status": PublicationStatus.PENDING_VALIDATION}),
        ("center", {"publication_status": PublicationStatus.RESTRICTED}),
        ("center", {"publication_status": PublicationStatus.RETIRED}),
        ("center", {"verified_on": None}),
        ("source", {"status": PublicationStatus.PENDING_VALIDATION}),
        ("source", {"status": PublicationStatus.RESTRICTED}),
        ("source", {"status": PublicationStatus.RETIRED}),
        ("source", {"is_publicly_releasable": False}),
    ],
)
def test_every_request_rechecks_current_center_and_source_state(center_factory, target, changes):
    center = center_factory()
    assert len(lookup()["centers"]) == 1
    model = center if target == "center" else center.source
    type(model).objects.filter(pk=model.pk).update(**changes)
    assert_empty(lookup())


def test_newly_eligible_record_appears_on_next_request_without_restart(center_factory):
    center = center_factory(
        verification_status=EvacuationCenter.VerificationStatus.IN_REVIEW,
        publication_status=PublicationStatus.PENDING_VALIDATION,
        verified_on=None,
        capacity=None,
    )
    assert_empty(lookup())
    EvacuationCenter.objects.filter(pk=center.pk).update(
        verification_status=EvacuationCenter.VerificationStatus.VERIFIED,
        publication_status=PublicationStatus.APPROVED,
        verified_on="2026-09-19",
    )
    assert [row["public_identifier"] for row in lookup()["centers"]] == [str(center.public_id)]


def test_required_source_and_coordinates_are_structurally_non_nullable():
    for field_name in ("source", "latitude", "longitude"):
        field = EvacuationCenter._meta.get_field(field_name)
        assert field.null is False
        assert field.blank is False


def test_eligible_centers_in_different_barangays_keep_their_own_identity(layer, center_factory):
    first = center_factory(geographic_area=layer[2][0], longitude=Decimal("0"))
    second = center_factory(geographic_area=layer[2][1], longitude=Decimal("1"))
    result = lookup(limit=2)["centers"]
    assert [row["public_identifier"] for row in result] == [
        str(first.public_id),
        str(second.public_id),
    ]
    assert [row["barangay"]["psgc_code"] for row in result] == [
        "0000000000",
        "0000000001",
    ]


@pytest.mark.parametrize(
    "user_point",
    [
        (Decimal("0.500000"), Decimal("0.500000")),  # synthetic city interior
        (Decimal("0.500000"), Decimal("47.000001")),  # just outside synthetic city
        (Decimal("0.000001"), Decimal("0.999999")),  # boundary/coastal analogue
        (Decimal("-0.000001"), Decimal("1.000001")),
    ],
)
def test_valid_points_inside_outside_and_adjacent_use_same_stable_geodetic_policy(
    center_factory, user_point
):
    first = center_factory(
        latitude=Decimal("0.000000"),
        longitude=Decimal("0.000000"),
        public_id=UUID(int=1),
    )
    second = center_factory(
        latitude=Decimal("0.000000"),
        longitude=Decimal("1.000000"),
        public_id=UUID(int=2),
    )
    latitude, longitude = user_point
    result = lookup(latitude=float(latitude), longitude=float(longitude), limit=2)
    assert len(result["centers"]) == 2
    assert result == lookup(latitude=float(latitude), longitude=float(longitude), limit=2)
    identifiers = {row["public_identifier"] for row in result["centers"]}
    assert identifiers == {str(first.public_id), str(second.public_id)}
    assert all(row["distance_unit"] == "meters" for row in result["centers"])


def test_sub_meter_full_precision_order_survives_same_display_rounding(center_factory):
    farther = center_factory(longitude=Decimal("0.000009"), public_id=UUID(int=1))
    nearer = center_factory(latitude=Decimal("0.000009"), public_id=UUID(int=2))
    result = lookup(limit=2)["centers"]
    assert [row["approximate_distance"] for row in result] == [1.0, 1.0]
    assert [row["public_identifier"] for row in result] == [
        str(nearer.public_id),
        str(farther.public_id),
    ]
