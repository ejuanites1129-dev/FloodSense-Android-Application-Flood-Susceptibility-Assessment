import json
from io import StringIO
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.management import call_command
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from provenance.models import DataSource

from .constants import (
    BACOOR_CITY_CODE,
    BACOOR_REFERENCE_BARANGAY_COUNT,
    BACOOR_REFERENCE_SOURCE_NAME,
    BACOOR_REFERENCE_SOURCE_VERSION,
)
from .models import AreaFact, GeographicArea
from .serializers import BarangayResolutionState
from .services import (
    BarangayResolutionResult,
    _normalized_barangay_matches,
    eligible_bacoor_reference_barangays,
    public_psgc_code,
    resolve_bacoor_barangay,
)
from .test_day2_barangay_resolver import BarangayResolverTestData


class ControlledBoundaryCoverageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("import_bacoor_boundaries", stdout=StringIO())

    def test_every_current_barangay_surface_point_resolves_to_its_psgc_identity(self):
        barangays = list(eligible_bacoor_reference_barangays().order_by("code"))
        self.assertEqual(len(barangays), BACOOR_REFERENCE_BARANGAY_COUNT)

        for barangay in barangays:
            with self.subTest(code=barangay.code, name=barangay.name):
                point = barangay.geometry.point_on_surface
                result = resolve_bacoor_barangay(
                    latitude=point.y,
                    longitude=point.x,
                )
                self.assertEqual(result.state, BarangayResolutionState.RESOLVED)
                self.assertEqual(result.barangay_psgc_code, barangay.code.removeprefix("PSGC_"))
                self.assertEqual(result.barangay_name, barangay.name)

    def test_imported_current_identities_and_source_version_are_unique(self):
        source = DataSource.objects.get(name=BACOOR_REFERENCE_SOURCE_NAME)
        identities = list(
            eligible_bacoor_reference_barangays().values_list("code", "name")
        )

        self.assertEqual(source.version, BACOOR_REFERENCE_SOURCE_VERSION)
        self.assertEqual(len({code for code, _ in identities}), 47)
        self.assertEqual(len({name.casefold() for _, name in identities}), 47)
        self.assertTrue(all(code.startswith("PSGC_") for code, _ in identities))

    def test_geometry_field_has_spatial_index_and_query_plan_uses_database_filter(self):
        field = GeographicArea._meta.get_field("geometry")
        self.assertTrue(field.spatial_index)
        barangay = eligible_bacoor_reference_barangays().first()
        point = barangay.geometry.point_on_surface
        plan = eligible_bacoor_reference_barangays().filter(
            geometry__covers=point
        ).explain()

        self.assertIn("geography_geographicarea", plan)
        self.assertIn("st_covers", plan.lower())

    def test_coastal_point_outside_city_is_not_assigned(self):
        city = GeographicArea.objects.get(code=BACOOR_CITY_CODE)
        west, south, east, north = city.geometry.extent
        result = resolve_bacoor_barangay(
            latitude=(south + north) / 2,
            longitude=west - 0.01,
        )

        self.assertEqual(result.state, BarangayResolutionState.OUTSIDE_BACOOR)


class ResolverPerformanceAndSeparationTests(BarangayResolverTestData, TestCase):
    def setUp(self):
        self.url = reverse("geography:resolve-barangay")

    def post(self, latitude=0.25, longitude=0.25):
        return self.client.post(
            self.url,
            data=json.dumps({"latitude": latitude, "longitude": longitude}),
            content_type="application/json",
        )

    @patch("expert.services.evaluate_assessment")
    @patch("expert.services.evaluate_map_scenario")
    def test_request_has_bounded_queries_no_writes_and_no_inference(
        self,
        evaluate_map,
        evaluate_detail,
    ):
        self.make_ready_layer()
        before = {
            "sources": DataSource.objects.count(),
            "areas": GeographicArea.objects.count(),
            "facts": AreaFact.objects.count(),
            "audit": LogEntry.objects.count(),
        }

        with CaptureQueriesContext(connection) as captured:
            response = self.post()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(captured), 4)
        self.assertFalse(
            any(
                query["sql"].lstrip().upper().startswith(
                    ("INSERT", "UPDATE", "DELETE")
                )
                for query in captured.captured_queries
            )
        )
        self.assertEqual(DataSource.objects.count(), before["sources"])
        self.assertEqual(GeographicArea.objects.count(), before["areas"])
        self.assertEqual(AreaFact.objects.count(), before["facts"])
        self.assertEqual(LogEntry.objects.count(), before["audit"])
        evaluate_detail.assert_not_called()
        evaluate_map.assert_not_called()

    def test_each_state_response_is_small_and_allowlisted(self):
        states = (
            BarangayResolutionState.RESOLVED,
            BarangayResolutionState.OUTSIDE_BACOOR,
            BarangayResolutionState.AMBIGUOUS_BOUNDARY,
            BarangayResolutionState.UNAVAILABLE,
        )
        for state in states:
            result = BarangayResolutionResult(
                state,
                barangay_psgc_code="0402103004"
                if state == BarangayResolutionState.RESOLVED
                else None,
                barangay_name="Bayanan"
                if state == BarangayResolutionState.RESOLVED
                else None,
            )
            with self.subTest(state=state), patch(
                "geography.views.resolve_bacoor_barangay",
                return_value=result,
            ):
                response = self.post(latitude=14.4, longitude=120.9)
                self.assertEqual(response.status_code, 200)
                self.assertLess(len(response.content), 1024)
                self.assertEqual(
                    set(response.json()),
                    {
                        "resolution_state",
                        "coordinate",
                        "barangay",
                        "boundary",
                        "limitations",
                    },
                )
                self.assertNotIn(b"geometry", response.content)
                self.assertNotIn(b"classification", response.content)


class MatchNormalizationTests(SimpleTestCase):
    def test_public_identity_accepts_only_the_controlled_psgc_code_shape(self):
        self.assertEqual(public_psgc_code("PSGC_0402103004"), "0402103004")
        self.assertIsNone(public_psgc_code("0402103004"))
        self.assertIsNone(public_psgc_code("PSGC_historical-name"))

    def test_repeated_rows_for_one_stable_identity_do_not_create_ambiguity(self):
        matches = [
            ("PSGC_0402103004", "Bayanan"),
            ("PSGC_0402103004", "Bayanan"),
        ]

        self.assertEqual(
            _normalized_barangay_matches(matches),
            {("0402103004", "Bayanan")},
        )

    def test_distinct_stable_identities_remain_ambiguous(self):
        matches = [
            ("PSGC_0402103004", "Bayanan"),
            ("PSGC_0402103007", "Dulong Bayan"),
        ]

        self.assertEqual(len(_normalized_barangay_matches(matches)), 2)


class InvalidGeometryReadinessTests(BarangayResolverTestData, TestCase):
    def test_empty_barangay_geometry_fails_closed_before_lookup(self):
        _, target = self.make_ready_layer()
        target.geometry = MultiPolygon(srid=4326)
        target.save(update_fields=("geometry",))

        self.assertEqual(
            resolve_bacoor_barangay(latitude=0.25, longitude=0.25).state,
            BarangayResolutionState.UNAVAILABLE,
        )

    def test_invalid_barangay_geometry_fails_closed_before_lookup(self):
        _, target = self.make_ready_layer()
        invalid = Polygon(
            ((0, 0), (1, 1), (1, 0), (0, 1), (0, 0)),
            srid=4326,
        )
        self.assertFalse(invalid.valid)
        target.geometry = MultiPolygon(invalid, srid=4326)
        target.save(update_fields=("geometry",))

        self.assertEqual(
            resolve_bacoor_barangay(latitude=0.25, longitude=0.25).state,
            BarangayResolutionState.UNAVAILABLE,
        )
