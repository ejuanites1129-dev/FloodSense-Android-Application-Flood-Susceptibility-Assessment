"""Synthetic records in the isolated PostGIS test DB; never operational data."""

import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID

import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.contrib.sessions.models import Session
from django.db import DatabaseError, connection
from django.test.utils import CaptureQueriesContext
from geography.constants import (
    BACOOR_CITY_CODE,
    BACOOR_REFERENCE_LIMITATION,
    BACOOR_REFERENCE_SOURCE_NAME,
    BACOOR_REFERENCE_WARNING,
)
from geography.models import GeographicArea
from provenance.models import DataSource, PublicationStatus
from rest_framework.exceptions import ValidationError

from .contracts import CENTER_LIMITATION, DISTANCE_WARNING, EMPTY_DISTANCE_WARNING, EMPTY_WARNING
from .models import EvacuationCenter
from .serializers import NearestCenterResponseSerializer
from .services import (
    _distance_expression,
    _public_center,
    find_nearest_eligible_centers,
    ready_reference_barangays,
)


def box(left=0, bottom=0, right=1, top=1):
    return MultiPolygon(Polygon.from_bbox((left, bottom, right, top)), srid=4326)


@pytest.fixture
def layer(db):
    source = DataSource.objects.create(
        name=BACOOR_REFERENCE_SOURCE_NAME,
        organization="SYNTHETIC reference custodian - tests only",
        source_type=DataSource.SourceType.AGENCY_DATASET,
        status=PublicationStatus.PENDING_VALIDATION,
        is_publicly_releasable=True,
    )
    city = GeographicArea.objects.create(
        code=BACOOR_CITY_CODE,
        name="SYNTHETIC CITY GEOMETRY - NOT REAL",
        area_type=GeographicArea.AreaType.CITY,
        geometry=box(right=47),
        source=source,
        status=PublicationStatus.PENDING_VALIDATION,
        is_enabled=True,
    )
    areas = GeographicArea.objects.bulk_create(
        [
            GeographicArea(
                code=f"PSGC_{index:010d}",
                name=f"SYNTHETIC BARANGAY {index}",
                area_type=GeographicArea.AreaType.BARANGAY,
                geometry=box(left=index, right=index + 1),
                source=source,
                status=PublicationStatus.PENDING_VALIDATION,
                is_enabled=True,
            )
            for index in range(47)
        ]
    )
    return source, city, areas


@pytest.fixture
def center_factory(layer):
    source = DataSource.objects.create(
        name="SYNTHETIC FACILITY SOURCE - NOT OPERATIONAL",
        organization="Synthetic public attribution",
        source_type=DataSource.SourceType.AGENCY_DATASET,
        status=PublicationStatus.APPROVED,
        is_publicly_releasable=True,
        limitations="Synthetic public source limitation.",
        notes="PRIVATE SOURCE SENTINEL",
        permitted_use="PRIVATE PERMITTED USE SENTINEL",
    )

    def create(**overrides):
        values = {
            "name": "SYNTHETIC CENTER - NOT A REAL FACILITY",
            "address": "Synthetic test address",
            "source": source,
            "geographic_area": layer[2][0],
            "latitude": 0,
            "longitude": 0,
            "verification_status": EvacuationCenter.VerificationStatus.VERIFIED,
            "publication_status": PublicationStatus.APPROVED,
            "verified_on": date(2026, 9, 19),
            "notes": "PRIVATE CENTER SENTINEL",
            "contact_information": "PRIVATE CONTACT SENTINEL",
            "capacity": 123,
        }
        values.update(overrides)
        return EvacuationCenter.objects.create(**values)

    return create


def lookup(**overrides):
    return find_nearest_eligible_centers(**{"latitude": 0, "longitude": 0, **overrides})


def assert_empty(result):
    assert result == {
        "centers": [],
        "distance_method": "APPROXIMATE_STRAIGHT_LINE",
        "warnings": [EMPTY_WARNING, EMPTY_DISTANCE_WARNING],
    }


def test_complete_reference_has_47_safe_identities(layer):
    identities = ready_reference_barangays()
    assert len(identities) == 47
    assert identities[layer[2][0].pk] == {"psgc_code": "0000000000", "name": "SYNTHETIC BARANGAY 0"}


@pytest.mark.parametrize(
    "damage",
    [
        "missing_source",
        "duplicate_source",
        "non_public_source",
        "restricted_source",
        "wrong_source_type",
        "missing_city",
        "disabled_city",
        "wrong_city_status",
        "wrong_city_source",
        "invalid_city",
        "empty_city",
        "missing_barangay",
        "extra_barangay",
        "duplicate_name",
        "blank_name",
        "invalid_code",
        "non_ascii_code",
        "disabled_area",
        "wrong_area_status",
        "wrong_area_type",
        "wrong_area_source",
        "invalid_geometry",
        "empty_geometry",
        "outside_city",
    ],
)
def test_reference_readiness_fails_closed(layer, center_factory, damage):
    center_factory()
    source, city, areas = layer
    area = areas[1]
    invalid = MultiPolygon(Polygon(((0, 0), (1, 1), (1, 0), (0, 1), (0, 0))), srid=4326)
    if damage == "missing_source":
        source.name = "UNRELATED SYNTHETIC SOURCE"
        source.save()
    elif damage == "duplicate_source":
        source.pk = None
        source.save()
    elif damage in {"non_public_source", "restricted_source", "wrong_source_type"}:
        values = {
            "non_public_source": {"is_publicly_releasable": False},
            "restricted_source": {"status": PublicationStatus.RESTRICTED},
            "wrong_source_type": {"source_type": DataSource.SourceType.DEMONSTRATION},
        }[damage]
        DataSource.objects.filter(pk=source.pk).update(**values)
    elif damage == "missing_city":
        city.delete()
    elif damage in {
        "disabled_city",
        "wrong_city_status",
        "wrong_city_source",
        "invalid_city",
        "empty_city",
    }:
        values = {
            "disabled_city": {"is_enabled": False},
            "wrong_city_status": {"status": PublicationStatus.APPROVED},
            "wrong_city_source": {"source": EvacuationCenter.objects.first().source},
            "invalid_city": {"geometry": invalid},
            "empty_city": {"geometry": MultiPolygon(srid=4326)},
        }[damage]
        GeographicArea.objects.filter(pk=city.pk).update(**values)
    elif damage == "missing_barangay":
        area.delete()
    elif damage == "extra_barangay":
        area.pk = None
        area.code = "PSGC_9999999999"
        area.save()
    else:
        values = {
            "duplicate_name": {"name": f" {areas[0].name.lower()} "},
            "blank_name": {"name": " \t"},
            "invalid_code": {"code": "unrelated"},
            "non_ascii_code": {"code": "PSGC_٠٠٠٠٠٠٠٠٠٠"},
            "disabled_area": {"is_enabled": False},
            "wrong_area_status": {"status": PublicationStatus.APPROVED},
            "wrong_area_type": {"area_type": GeographicArea.AreaType.DEMO_ZONE},
            "wrong_area_source": {"source": EvacuationCenter.objects.first().source},
            "invalid_geometry": {"geometry": invalid},
            "empty_geometry": {"geometry": MultiPolygon(srid=4326)},
            "outside_city": {"geometry": box(left=48, right=49)},
        }[damage]
        GeographicArea.objects.filter(pk=area.pk).update(**values)
    assert_empty(lookup())


def test_unrelated_reference_records_do_not_enter_ready_layer(layer, center_factory):
    center = center_factory()
    unrelated = GeographicArea.objects.create(
        code="PSGC_9999999999",
        name="SYNTHETIC UNRELATED AREA",
        geometry=box(),
        area_type=GeographicArea.AreaType.BARANGAY,
        source=center.source,
        status=PublicationStatus.PENDING_VALIDATION,
        is_enabled=True,
    )
    assert unrelated.pk not in ready_reference_barangays()
    center_factory(geographic_area=unrelated)
    assert len(lookup()["centers"]) == 1


@pytest.mark.parametrize("status", ["DRAFT", "IN_REVIEW", "INACTIVE"])
def test_unverified_states_are_excluded(center_factory, status):
    center_factory(verification_status=status)
    assert_empty(lookup())


@pytest.mark.parametrize("status", ["DEMONSTRATION", "PENDING_VALIDATION", "RESTRICTED", "RETIRED"])
def test_unapproved_center_publication_is_excluded(center_factory, status):
    center_factory(publication_status=status)
    assert_empty(lookup())


@pytest.mark.parametrize(
    "field,value",
    [
        ("verified_on", None),
        ("name", " \t"),
        ("address", "\n"),
        ("name", "invalid\x01text"),
        ("limitations", "invalid\x01limitation"),
        ("geographic_area", None),
        ("latitude", 91),
        ("latitude", -91),
        ("longitude", 181),
        ("longitude", -181),
    ],
)
def test_malformed_or_missing_public_center_fields_are_excluded(center_factory, field, value):
    center_factory(**{field: value})
    assert_empty(lookup())


@pytest.mark.parametrize("field", ["latitude", "longitude"])
def test_stored_nan_coordinates_are_excluded(center_factory, field):
    center = center_factory()
    # Django's DecimalField rejects NaN before saving. Simulate malformed legacy
    # data directly in this isolated test transaction to exercise the SQL guard.
    statements = {
        "latitude": "UPDATE evacuation_evacuationcenter SET latitude = %s WHERE id = %s",
        "longitude": "UPDATE evacuation_evacuationcenter SET longitude = %s WHERE id = %s",
    }
    with connection.cursor() as cursor:
        cursor.execute(statements[field], [Decimal("NaN"), center.pk])
        assert cursor.rowcount == 1
    center.refresh_from_db()
    assert getattr(center, field).is_nan()
    assert_empty(lookup())


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "DEMONSTRATION"},
        {"status": "PENDING_VALIDATION"},
        {"status": "RESTRICTED"},
        {"status": "RETIRED"},
        {"is_publicly_releasable": False},
        {"source_type": "DEMONSTRATION"},
        {"organization": " \n"},
        {"organization": "invalid\x01text"},
        {"limitations": "invalid\x01limitation"},
    ],
)
def test_source_gates_are_rechecked_after_verification(center_factory, changes):
    center = center_factory()
    assert len(lookup()["centers"]) == 1
    DataSource.objects.filter(pk=center.source_id).update(**changes)
    assert_empty(lookup())


@pytest.mark.parametrize("kind", ["city", "demo", "disabled", "unrelated"])
def test_unsupported_center_associations_are_excluded(layer, center_factory, kind):
    center = center_factory()
    if kind == "city":
        area = layer[1]
    elif kind == "disabled":
        area = layer[2][0]
        GeographicArea.objects.filter(pk=area.pk).update(is_enabled=False)
    else:
        area = GeographicArea.objects.create(
            code=f"synthetic-{kind}",
            name=f"SYNTHETIC {kind}",
            geometry=box(),
            area_type="DEMO_ZONE" if kind == "demo" else "BARANGAY",
            source=center.source,
            status=PublicationStatus.PENDING_VALIDATION,
            is_enabled=True,
        )
    center.geographic_area = area
    center.save()
    assert_empty(lookup())


def test_source_and_center_state_are_not_cached(center_factory):
    center = center_factory()
    first = lookup()
    center.verification_status = "INACTIVE"
    center.save()
    assert_empty(lookup())
    center.verification_status = "VERIFIED"
    center.save()
    assert lookup() == first


def test_zero_distance_and_wire_mapping(center_factory):
    center = center_factory()
    result = lookup()
    serializer = NearestCenterResponseSerializer(data=result)
    assert serializer.is_valid(), serializer.errors
    assert result["warnings"] == [DISTANCE_WARNING]
    output = result["centers"][0]
    assert output["public_identifier"] == str(center.public_id)
    assert output["public_identifier"] != str(center.pk)
    assert output["approximate_distance"] == 0
    assert output["distance_unit"] == "meters"
    assert output["verified_on"] == "2026-09-19"
    assert "PRIVATE" not in json.dumps(result)
    assert set(output) == {
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
    }


@pytest.mark.parametrize("latitude,longitude,meters", [(1, 0, 110574.4), (0, 1, 111319.5)])
def test_wgs84_spheroid_known_equatorial_pairs(center_factory, latitude, longitude, meters):
    # WGS84 equatorial meridian/parallel distances; 0.2 m tolerance includes wire rounding.
    center_factory(latitude=latitude, longitude=longitude)
    assert lookup()["centers"][0]["approximate_distance"] == pytest.approx(meters, abs=0.2)


def test_nearest_first_then_uuid_for_exact_ties(center_factory):
    far = center_factory(longitude=2, public_id=UUID(int=1))
    near_later_uuid = center_factory(longitude=1, public_id=UUID(int=3))
    near_first_uuid = center_factory(longitude=1, public_id=UUID(int=2))
    result = lookup()
    assert [item["public_identifier"] for item in result["centers"]] == [
        str(near_first_uuid.public_id),
        str(near_later_uuid.public_id),
        str(far.public_id),
    ]
    assert lookup() == result


def test_rounding_does_not_change_full_precision_order(center_factory):
    # Both distances display as 1.1 m; the closer meridian point must win even
    # though its UUID sorts after the equatorial longitude point's UUID.
    far = center_factory(longitude=Decimal("0.000010"), public_id=UUID(int=1))
    near = center_factory(latitude=Decimal("0.000010"), public_id=UUID(int=2))
    centers = lookup(limit=2)["centers"]
    assert [row["approximate_distance"] for row in centers] == [1.1, 1.1]
    assert [row["public_identifier"] for row in centers] == [
        str(near.public_id),
        str(far.public_id),
    ]
    assert lookup(limit=1)["centers"][0]["public_identifier"] == str(near.public_id)


@pytest.mark.parametrize("limit", [1, 3, 10])
def test_limit_follows_all_public_validation(center_factory, limit):
    for _ in range(12):
        center_factory(name=" ")
    for index in range(12):
        center_factory(longitude=index + 1)
    assert len(lookup(limit=limit)["centers"]) == limit
    assert len(lookup()["centers"]) == 3


def test_limit_refills_after_invalid_optional_caveat(center_factory):
    center_factory(limitations="invalid\x01caveat")
    good = center_factory(longitude=1)
    assert lookup(limit=1)["centers"][0]["public_identifier"] == str(good.public_id)


def test_limitations_are_ordered_trimmed_and_deduplicated(center_factory):
    center = center_factory(limitations="  Synthetic public source limitation. \n")
    output = lookup()["centers"][0]
    assert output["limitations"] == [
        CENTER_LIMITATION,
        BACOOR_REFERENCE_WARNING,
        BACOOR_REFERENCE_LIMITATION,
        "Synthetic public source limitation.",
    ]
    center.limitations = f" {CENTER_LIMITATION} "
    center.save()
    assert lookup()["centers"][0]["limitations"] == output["limitations"]


def test_empty_inventory_and_all_unsafe_rows_are_truthful(layer, center_factory):
    assert_empty(lookup())
    center_factory(name=" ")
    assert_empty(lookup())


def test_lookup_is_select_only_preserves_rows_and_does_not_log_input(center_factory, caplog):
    center_factory()
    models = (EvacuationCenter, DataSource, GeographicArea, LogEntry, Session)
    before = [list(model.objects.order_by("pk").values()) for model in models]
    with CaptureQueriesContext(connection) as queries:
        for _ in range(2):
            result = lookup(latitude=14.123456789, longitude=120.987654321)
    assert len(queries) == 8
    assert all(query["sql"].lstrip().upper().startswith("SELECT") for query in queries)
    after = [list(model.objects.order_by("pk").values()) for model in models]
    assert before == after
    assert "14.123456789" not in json.dumps(result)
    assert "120.987654321" not in json.dumps(result)
    assert not [record for record in caplog.records if record.name.startswith("evacuation")]


def test_query_count_and_projection_do_not_grow_with_candidates(center_factory):
    center_factory()
    with CaptureQueriesContext(connection) as small:
        lookup()
    for _ in range(30):
        center_factory()
    with CaptureQueriesContext(connection) as large:
        lookup(limit=10)
    assert len(small) == len(large) == 4
    sql = large[-1]["sql"]
    for forbidden in ("contact_information", "capacity", '"notes"', "permitted_use", "reviewed_by"):
        assert forbidden not in sql


@pytest.mark.parametrize(
    "inputs",
    [
        {"latitude": True},
        {"longitude": "0"},
        {"latitude": float("nan")},
        {"longitude": 181},
        {"limit": 0},
        {"limit": 11},
        {"limit": 3.0},
    ],
)
def test_service_input_validation_precedes_database_access(inputs):
    # Unmarked tests cannot access the DB. Bad internal callers are rejected too.
    with pytest.raises(ValidationError):
        lookup(**inputs)


@pytest.mark.parametrize("identifier", [None, "123", "not-a-uuid"])
def test_public_mapping_rejects_impossible_legacy_uuid_values(identifier):
    # The final DB schema rejects these values; retain a fail-closed mapping guard.
    row = {
        "public_id": identifier,
        "name": "SYNTHETIC",
        "address": "Synthetic address",
        "latitude": 0,
        "longitude": 0,
        "distance_meters": 0,
        "verified_on": date(2026, 9, 19),
        "source__organization": "Synthetic",
        "limitations": "",
        "source__limitations": "",
    }
    assert _public_center(row, {"psgc_code": "0000000000", "name": "Synthetic"}) is None


def test_database_failure_propagates_instead_of_becoming_empty():
    with patch(
        "evacuation.services.ready_reference_barangays",
        side_effect=DatabaseError("Synthetic failure"),
    ):
        with pytest.raises(DatabaseError, match="Synthetic failure"):
            lookup()


def test_distance_sql_uses_bound_parameters_and_guards_point_construction():
    query = EvacuationCenter.objects.all().query
    expression = _distance_expression(latitude=14.123456789, longitude=120.987654321)
    sql, parameters = query.get_compiler(connection=connection).compile(
        expression.resolve_expression(query)
    )
    assert "CASE WHEN" in sql and "ST_Distance" in sql and "ST_MakePoint" in sql
    assert "geography" in sql
    assert "14.123456789" not in sql and "120.987654321" not in sql
    assert parameters.index(120.987654321) < parameters.index(14.123456789)
    assert True in parameters
