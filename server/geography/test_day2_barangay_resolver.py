import json
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from provenance.models import DataSource, PublicationStatus

from .constants import BACOOR_CITY_CODE, BACOOR_REFERENCE_SOURCE_NAME
from .models import GeographicArea
from .serializers import BarangayResolutionState
from .services import resolve_bacoor_barangay


def rectangle(west: float, south: float, size: float = 0.5) -> Polygon:
    return Polygon(
        (
            (west, south),
            (west, south + size),
            (west + size, south + size),
            (west + size, south),
            (west, south),
        ),
        srid=4326,
    )


def multipolygon(*polygons: Polygon) -> MultiPolygon:
    return MultiPolygon(*polygons, srid=4326)


class BarangayResolverTestData:
    def make_source(self, **overrides) -> DataSource:
        values = {
            "name": BACOOR_REFERENCE_SOURCE_NAME,
            "source_type": DataSource.SourceType.AGENCY_DATASET,
            "status": PublicationStatus.PENDING_VALIDATION,
            "is_publicly_releasable": True,
        }
        values.update(overrides)
        return DataSource.objects.create(**values)

    def make_area(self, *, source: DataSource, **overrides) -> GeographicArea:
        values = {
            "code": "PSGC_0000000001",
            "name": "Synthetic Barangay 1",
            "area_type": GeographicArea.AreaType.BARANGAY,
            "geometry": multipolygon(rectangle(0, 0)),
            "source": source,
            "status": PublicationStatus.PENDING_VALIDATION,
            "is_enabled": True,
        }
        values.update(overrides)
        return GeographicArea.objects.create(**values)

    def make_ready_layer(
        self,
        *,
        target_geometry: MultiPolygon | None = None,
        second_geometry: MultiPolygon | None = None,
    ) -> tuple[DataSource, GeographicArea]:
        source = self.make_source()
        self.make_area(
            source=source,
            code=BACOOR_CITY_CODE,
            name="Synthetic Bacoor test boundary",
            area_type=GeographicArea.AreaType.CITY,
            geometry=multipolygon(rectangle(-1, -1, 12)),
        )
        target = self.make_area(
            source=source,
            geometry=target_geometry or multipolygon(rectangle(0, 0)),
        )
        for index in range(2, 48):
            geometry = (
                second_geometry
                if index == 2 and second_geometry is not None
                else multipolygon(
                    rectangle(
                        2 + ((index - 2) % 10) * 0.7,
                        2 + ((index - 2) // 10) * 0.7,
                        0.25,
                    )
                )
            )
            self.make_area(
                source=source,
                code=f"PSGC_{index:010d}",
                name=f"Synthetic Barangay {index}",
                geometry=geometry,
            )
        return source, target


class BarangayResolutionServiceTests(BarangayResolverTestData, TestCase):
    def test_inside_point_resolves_stable_safe_identity(self):
        self.make_ready_layer()

        result = resolve_bacoor_barangay(latitude=0.25, longitude=0.25)

        self.assertEqual(result.state, BarangayResolutionState.RESOLVED)
        self.assertEqual(
            result.barangay,
            {"psgc_code": "0000000001", "name": "Synthetic Barangay 1"},
        )

    def test_point_uses_longitude_latitude_order_and_srid_4326(self):
        self.make_ready_layer()

        with patch("geography.services.Point", wraps=Point) as point_factory:
            result = resolve_bacoor_barangay(latitude=0.25, longitude=0.4)

        point_factory.assert_called_once_with(0.4, 0.25, srid=4326)
        self.assertEqual(result.state, BarangayResolutionState.RESOLVED)

    def test_point_outside_city_is_outside_bacoor(self):
        self.make_ready_layer()

        result = resolve_bacoor_barangay(latitude=30, longitude=30)

        self.assertEqual(result.state, BarangayResolutionState.OUTSIDE_BACOOR)
        self.assertIsNone(result.barangay)

    def test_shared_boundary_returns_ambiguous_instead_of_arbitrary_match(self):
        self.make_ready_layer(
            target_geometry=multipolygon(rectangle(0, 0, 1)),
            second_geometry=multipolygon(rectangle(1, 0, 1)),
        )

        result = resolve_bacoor_barangay(latitude=0.5, longitude=1)

        self.assertEqual(result.state, BarangayResolutionState.AMBIGUOUS_BOUNDARY)
        self.assertIsNone(result.barangay)

    def test_shared_vertex_returns_ambiguous_instead_of_arbitrary_match(self):
        self.make_ready_layer(
            target_geometry=multipolygon(rectangle(0, 0, 1)),
            second_geometry=multipolygon(rectangle(1, 1, 1)),
        )

        result = resolve_bacoor_barangay(latitude=1, longitude=1)

        self.assertEqual(result.state, BarangayResolutionState.AMBIGUOUS_BOUNDARY)

    def test_point_just_outside_city_is_outside_bacoor(self):
        self.make_ready_layer()

        result = resolve_bacoor_barangay(latitude=5, longitude=11.000001)

        self.assertEqual(result.state, BarangayResolutionState.OUTSIDE_BACOOR)

    def test_overlapping_polygons_return_ambiguous(self):
        overlapping = multipolygon(rectangle(0, 0, 1))
        self.make_ready_layer(
            target_geometry=overlapping,
            second_geometry=overlapping,
        )

        result = resolve_bacoor_barangay(latitude=0.5, longitude=0.5)

        self.assertEqual(result.state, BarangayResolutionState.AMBIGUOUS_BOUNDARY)

    def test_polygon_hole_is_not_assigned_to_surrounding_barangay(self):
        shell = rectangle(0, 0, 2).coords[0]
        hole = rectangle(0.75, 0.75, 0.5).coords[0]
        polygon_with_hole = Polygon(shell, hole, srid=4326)
        self.make_ready_layer(
            target_geometry=multipolygon(polygon_with_hole),
        )

        result = resolve_bacoor_barangay(latitude=1, longitude=1)

        self.assertEqual(result.state, BarangayResolutionState.UNAVAILABLE)

    def test_multipolygon_component_resolves(self):
        self.make_ready_layer(
            target_geometry=multipolygon(
                rectangle(0, 0),
                rectangle(8, 8),
            ),
        )

        result = resolve_bacoor_barangay(latitude=8.25, longitude=8.25)

        self.assertEqual(result.state, BarangayResolutionState.RESOLVED)

    def test_city_covered_gap_is_unavailable(self):
        self.make_ready_layer()

        result = resolve_bacoor_barangay(latitude=10, longitude=10)

        self.assertEqual(result.state, BarangayResolutionState.UNAVAILABLE)

    def test_missing_or_incomplete_controlled_layer_is_unavailable(self):
        self.assertEqual(
            resolve_bacoor_barangay(latitude=0, longitude=0).state,
            BarangayResolutionState.UNAVAILABLE,
        )
        source = self.make_source()
        self.make_area(
            source=source,
            code=BACOOR_CITY_CODE,
            area_type=GeographicArea.AreaType.CITY,
        )
        for index in range(1, 47):
            self.make_area(
                source=source,
                code=f"PSGC_{index:010d}",
                name=f"Synthetic Barangay {index}",
            )

        self.assertEqual(
            resolve_bacoor_barangay(latitude=0.25, longitude=0.25).state,
            BarangayResolutionState.UNAVAILABLE,
        )

    def test_ineligible_and_unrelated_layers_are_not_fallbacks(self):
        unrelated = self.make_source(
            name="Unrelated approved synthetic layer",
            status=PublicationStatus.APPROVED,
        )
        for index in range(1, 48):
            self.make_area(
                source=unrelated,
                code=f"PSGC_{index:010d}",
                name=f"Unrelated Barangay {index}",
                status=PublicationStatus.APPROVED,
            )

        result = resolve_bacoor_barangay(latitude=0.25, longitude=0.25)

        self.assertEqual(result.state, BarangayResolutionState.UNAVAILABLE)

    def test_disabled_row_does_not_complete_the_controlled_layer(self):
        source, target = self.make_ready_layer()
        target.is_enabled = False
        target.save(update_fields=("is_enabled",))

        result = resolve_bacoor_barangay(latitude=0.25, longitude=0.25)

        self.assertEqual(result.state, BarangayResolutionState.UNAVAILABLE)
        self.assertEqual(source.status, PublicationStatus.PENDING_VALIDATION)


class BarangayResolutionApiTests(BarangayResolverTestData, TestCase):
    def setUp(self):
        self.url = reverse("geography:resolve-barangay")

    def post_json(self, payload: dict):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_post_returns_allowlisted_pending_validation_response(self):
        self.make_ready_layer()

        response = self.post_json(
            {"latitude": 0.250006, "longitude": 0.250006, "ignored": "safe"}
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            set(payload),
            {"resolution_state", "coordinate", "barangay", "boundary", "limitations"},
        )
        self.assertEqual(payload["resolution_state"], "RESOLVED")
        self.assertEqual(payload["coordinate"]["latitude"], 0.25001)
        self.assertEqual(payload["barangay"]["psgc_code"], "0000000001")
        self.assertEqual(payload["boundary"]["data_status"], "PENDING_VALIDATION")
        self.assertFalse(payload["boundary"]["city_verified"])
        self.assertNotIn("geometry", payload)
        self.assertNotIn("susceptibility", payload)
        self.assertNotIn("classification", payload)

    def test_invalid_coordinates_return_400_without_echoing_values(self):
        cases = (
            {},
            {"latitude": None, "longitude": 120},
            {"latitude": "14.4", "longitude": 120},
            {"latitude": True, "longitude": 120},
            {"latitude": 91, "longitude": 120},
            {"latitude": 14, "longitude": 181},
        )
        for payload in cases:
            with self.subTest(payload=payload):
                response = self.post_json(payload)
                self.assertEqual(response.status_code, 400)
                self.assertNotIn("181", response.content.decode())

    def test_non_finite_and_malformed_json_are_rejected(self):
        for body in (
            '{"latitude": NaN, "longitude": 120}',
            '{"latitude": Infinity, "longitude": 120}',
            '{"latitude": 14,',
        ):
            with self.subTest(body=body):
                response = self.client.post(
                    self.url,
                    data=body,
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)
                self.assertNotIn("120", response.content.decode())

    def test_non_json_media_type_is_rejected(self):
        response = self.client.post(
            self.url,
            data="latitude=14&longitude=120",
            content_type="text/plain",
        )

        self.assertEqual(response.status_code, 415)

    @patch("geography.views.resolve_bacoor_barangay")
    def test_unsupported_methods_do_not_perform_lookup(self, resolver):
        for method in ("get", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = self.client.generic(
                    method.upper(),
                    self.url,
                    data=json.dumps({"latitude": 0.25, "longitude": 0.25}),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 405)
                self.assertIn("POST", response.headers["Allow"])
        resolver.assert_not_called()

    @patch("geography.views.resolve_bacoor_barangay")
    def test_options_advertises_post_without_performing_lookup(self, resolver):
        response = self.client.options(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("POST", response.headers["Allow"])
        self.assertIn("OPTIONS", response.headers["Allow"])
        resolver.assert_not_called()

    def test_lookup_executes_selects_only_and_creates_no_audit_history(self):
        self.make_ready_layer()
        before = {
            "sources": DataSource.objects.count(),
            "areas": GeographicArea.objects.count(),
            "audit": LogEntry.objects.count(),
        }

        with CaptureQueriesContext(connection) as captured:
            response = self.post_json({"latitude": 0.25, "longitude": 0.25})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(DataSource.objects.count(), before["sources"])
        self.assertEqual(GeographicArea.objects.count(), before["areas"])
        self.assertEqual(LogEntry.objects.count(), before["audit"])
        mutating = [
            query["sql"]
            for query in captured.captured_queries
            if query["sql"].lstrip().upper().startswith(
                ("INSERT", "UPDATE", "DELETE")
            )
        ]
        self.assertEqual(mutating, [])

    @patch("geography.views.resolve_bacoor_barangay", side_effect=RuntimeError)
    def test_unexpected_failure_is_safe_and_does_not_echo_coordinate(
        self,
        _resolver,
    ):
        response = self.post_json({"latitude": 14.12345, "longitude": 120.98765})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {"detail": "The resolver is temporarily unavailable."},
        )
        self.assertNotIn("14.12345", response.content.decode())
