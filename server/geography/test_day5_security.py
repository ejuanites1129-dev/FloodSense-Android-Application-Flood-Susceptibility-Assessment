import json
from unittest.mock import patch

from accounts.models import User
from django.contrib.admin.models import LogEntry
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from dss.models import GuidanceItem
from evacuation.models import EvacuationCenter
from expert.models import (
    ExpertRule,
    ExpertRuleCondition,
    RuleSet,
    ScenarioOption,
    SusceptibilityLevel,
)
from provenance.models import DataSource

from .models import AreaFact, GeographicArea
from .serializers import RESOLVER_MAX_REQUEST_BYTES
from .test_day2_barangay_resolver import BarangayResolverTestData


class BarangayResolverDay5SecurityTests(BarangayResolverTestData, TestCase):
    def setUp(self):
        self.url = reverse("geography:resolve-barangay")

    def post_json(self, payload, *, client=None):
        return (client or self.client).post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def business_counts(self):
        return {
            "users": User.objects.count(),
            "sources": DataSource.objects.count(),
            "areas": GeographicArea.objects.count(),
            "area_facts": AreaFact.objects.count(),
            "scenario_options": ScenarioOption.objects.count(),
            "levels": SusceptibilityLevel.objects.count(),
            "rule_sets": RuleSet.objects.count(),
            "rules": ExpertRule.objects.count(),
            "conditions": ExpertRuleCondition.objects.count(),
            "guidance": GuidanceItem.objects.count(),
            "centers": EvacuationCenter.objects.count(),
            "audit": LogEntry.objects.count(),
        }

    def test_complete_invalid_input_matrix_is_safe_and_does_not_echo_values(self):
        cases = (
            {},
            {"latitude": 14},
            {"longitude": 120},
            {"latitude": None, "longitude": 120},
            {"latitude": 14, "longitude": None},
            {"latitude": "14.12345", "longitude": 120},
            {"latitude": 14, "longitude": "120.98765"},
            {"latitude": True, "longitude": 120},
            {"latitude": -90.00001, "longitude": 120},
            {"latitude": 90.00001, "longitude": 120},
            {"latitude": 14, "longitude": -180.00001},
            {"latitude": 14, "longitude": 180.00001},
        )
        for payload in cases:
            with self.subTest(payload=payload):
                response = self.post_json(payload)
                content = response.content.decode()
                self.assertEqual(response.status_code, 400)
                self.assertNotIn("14.12345", content)
                self.assertNotIn("120.98765", content)
                self.assertNotIn("geography_geographicarea", content)
                self.assertNotIn("Traceback", content)

    def test_non_finite_empty_malformed_and_non_object_json_are_safe(self):
        bodies = (
            "",
            "{}",
            "[]",
            '{"latitude": NaN, "longitude": 120.98765}',
            '{"latitude": -Infinity, "longitude": 120.98765}',
            '{"latitude": 14.12345, "longitude": Infinity}',
            '{"latitude": 14.12345,',
        )
        for body in bodies:
            with self.subTest(body=body):
                response = self.client.post(
                    self.url,
                    data=body,
                    content_type="application/json",
                )
                content = response.content.decode()
                self.assertEqual(response.status_code, 400)
                self.assertNotIn("14.12345", content)
                self.assertNotIn("120.98765", content)
                self.assertNotIn("Traceback", content)

    def test_declared_oversized_body_is_rejected_before_lookup_or_echo(self):
        self.make_ready_layer()
        payload = {
            "latitude": 14.12345,
            "longitude": 120.98765,
            "ignored": "x" * RESOLVER_MAX_REQUEST_BYTES,
        }

        with patch("geography.views.resolve_bacoor_barangay") as resolver:
            response = self.post_json(payload)

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json(), {"detail": "The resolver request is too large."})
        self.assertNotIn("14.12345", response.content.decode())
        self.assertNotIn("120.98765", response.content.decode())
        resolver.assert_not_called()

    def test_unknown_fields_are_ignored_but_cannot_influence_allowlisted_output(self):
        self.make_ready_layer()

        response = self.post_json(
            {
                "latitude": 0.25,
                "longitude": 0.25,
                "susceptibility": "VERY_HIGH",
                "raw_geometry": "<script>alert(1)</script>",
                "internal_notes": "restricted",
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json()),
            {"resolution_state", "coordinate", "barangay", "boundary", "limitations"},
        )
        self.assertNotIn(b"VERY_HIGH", response.content)
        self.assertNotIn(b"raw_geometry", response.content)
        self.assertNotIn(b"internal_notes", response.content)

    @patch("dss.services.select_guidance")
    @patch("expert.services.evaluate_map_scenario")
    @patch("expert.services.evaluate_assessment")
    def test_repeated_public_lookups_are_select_only_and_call_no_inference(
        self,
        evaluate_assessment,
        evaluate_map,
        select_guidance,
    ):
        self.make_ready_layer()
        before = self.business_counts()

        with CaptureQueriesContext(connection) as captured:
            responses = [self.post_json({"latitude": 0.25, "longitude": 0.25}) for _ in range(3)]

        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertEqual(self.business_counts(), before)
        mutating_queries = [
            query["sql"]
            for query in captured.captured_queries
            if query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]
        self.assertEqual(mutating_queries, [])
        evaluate_assessment.assert_not_called()
        evaluate_map.assert_not_called()
        select_guidance.assert_not_called()

    def test_public_permission_and_csrf_scope_match_read_only_mobile_lookup(self):
        self.make_ready_layer()
        csrf_enforcing_client = Client(enforce_csrf_checks=True)

        response = self.post_json(
            {"latitude": 0.25, "longitude": 0.25},
            client=csrf_enforcing_client,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["resolution_state"], "RESOLVED")

    def test_content_type_methods_and_small_response_remain_bounded(self):
        self.make_ready_layer()

        unsupported = self.client.post(
            self.url,
            data="latitude=0.25&longitude=0.25",
            content_type="text/plain",
        )
        self.assertEqual(unsupported.status_code, 415)
        for method in ("get", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.url)
                self.assertEqual(response.status_code, 405)

        response = self.post_json({"latitude": 0.25, "longitude": 0.25})
        self.assertEqual(response.status_code, 200)
        self.assertLess(len(response.content), RESOLVER_MAX_REQUEST_BYTES)
        self.assertEqual(response["Content-Type"], "application/json")
