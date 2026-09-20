import json

from django.contrib.gis.geos import MultiPolygon
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .serializers import BarangayResolutionState
from .test_day2_barangay_resolver import BarangayResolverTestData, rectangle


class BarangayResolverDay6PerformanceTests(BarangayResolverTestData, TestCase):
    def setUp(self):
        self.url = reverse("geography:resolve-barangay")

    def measured_post(self, payload):
        with CaptureQueriesContext(connection) as captured:
            response = self.client.post(
                self.url,
                data=json.dumps(payload),
                content_type="application/json",
            )
        return response, captured.captured_queries

    def assert_bounded_response(self, response, queries, *, state, count):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["resolution_state"], state)
        self.assertEqual(len(queries), count)
        self.assertTrue(
            all(query["sql"].lstrip().upper().startswith("SELECT") for query in queries)
        )
        self.assertLess(len(response.content), 1024)
        self.assertNotIn(b"geometry", response.content)

    def test_resolved_request_uses_four_selects_and_small_payload(self):
        self.make_ready_layer()

        response, queries = self.measured_post({"latitude": 0.25, "longitude": 0.25})

        self.assert_bounded_response(
            response,
            queries,
            state=BarangayResolutionState.RESOLVED,
            count=4,
        )

    def test_outside_request_adds_only_the_bounded_city_coverage_select(self):
        self.make_ready_layer()

        response, queries = self.measured_post({"latitude": 30, "longitude": 30})

        self.assert_bounded_response(
            response,
            queries,
            state=BarangayResolutionState.OUTSIDE_BACOOR,
            count=5,
        )

    def test_ambiguous_request_remains_four_selects(self):
        overlap = MultiPolygon(rectangle(0, 0, 1), srid=4326)
        self.make_ready_layer(target_geometry=overlap, second_geometry=overlap)

        response, queries = self.measured_post({"latitude": 0.5, "longitude": 0.5})

        self.assert_bounded_response(
            response,
            queries,
            state=BarangayResolutionState.AMBIGUOUS_BOUNDARY,
            count=4,
        )

    def test_unavailable_layer_fails_closed_after_one_select(self):
        response, queries = self.measured_post({"latitude": 0.25, "longitude": 0.25})

        self.assert_bounded_response(
            response,
            queries,
            state=BarangayResolutionState.UNAVAILABLE,
            count=1,
        )

    def test_invalid_input_performs_no_database_query(self):
        response, queries = self.measured_post({"latitude": 91, "longitude": 0})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(queries, [])
        self.assertLess(len(response.content), 1024)
