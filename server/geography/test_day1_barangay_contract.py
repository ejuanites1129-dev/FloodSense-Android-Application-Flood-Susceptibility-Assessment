from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from provenance.models import DataSource, PublicationStatus
from rest_framework.exceptions import ValidationError

from .constants import (
    BACOOR_REFERENCE_BARANGAY_COUNT,
    BACOOR_REFERENCE_LIMITATION,
    BACOOR_REFERENCE_SOURCE_NAME,
    BACOOR_REFERENCE_WARNING,
)
from .models import GeographicArea
from .serializers import (
    RESOLVER_ALLOWED_METHODS,
    RESOLVER_CONTENT_TYPE,
    RESOLVER_COORDINATE_DECIMAL_PLACES,
    RESOLVER_PATH,
    BarangayResolutionRequestSerializer,
    BarangayResolutionState,
    make_barangay_resolution_response,
)
from .services import eligible_bacoor_reference_barangays


class BarangayResolutionRequestContractTests(SimpleTestCase):
    def test_contract_transport_is_post_only_json_at_versioned_path(self):
        self.assertEqual(RESOLVER_PATH, "/api/v1/geography/resolve-barangay/")
        self.assertEqual(RESOLVER_ALLOWED_METHODS, ("POST", "OPTIONS"))
        self.assertEqual(RESOLVER_CONTENT_TYPE, "application/json")

    def test_valid_coordinate_is_accepted(self):
        serializer = BarangayResolutionRequestSerializer(
            data={"latitude": 14.41, "longitude": 120.97}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["latitude"], 14.41)
        self.assertEqual(serializer.validated_data["longitude"], 120.97)

    def test_missing_null_wrong_type_and_non_numeric_values_are_rejected(self):
        cases = (
            ({"longitude": 120.97}, "latitude"),
            ({"latitude": None, "longitude": 120.97}, "latitude"),
            ({"latitude": True, "longitude": 120.97}, "latitude"),
            ({"latitude": "14.41", "longitude": 120.97}, "latitude"),
            ({"latitude": "not-a-number", "longitude": 120.97}, "latitude"),
        )
        for data, field in cases:
            with self.subTest(data=data):
                serializer = BarangayResolutionRequestSerializer(data=data)
                self.assertFalse(serializer.is_valid())
                self.assertEqual(set(serializer.errors), {field})
                self.assertIsInstance(serializer.errors[field], list)

    def test_nan_and_infinity_are_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                serializer = BarangayResolutionRequestSerializer(
                    data={"latitude": value, "longitude": 120.97}
                )
                self.assertFalse(serializer.is_valid())
                self.assertEqual(
                    [str(error) for error in serializer.errors["latitude"]],
                    ["Enter a finite number."],
                )

    def test_legal_coordinate_ranges_are_enforced(self):
        cases = (
            ({"latitude": -90.01, "longitude": 120}, "latitude"),
            ({"latitude": 90.01, "longitude": 120}, "latitude"),
            ({"latitude": 14, "longitude": -180.01}, "longitude"),
            ({"latitude": 14, "longitude": 180.01}, "longitude"),
        )
        for data, field in cases:
            with self.subTest(data=data):
                serializer = BarangayResolutionRequestSerializer(data=data)
                self.assertFalse(serializer.is_valid())
                self.assertEqual(set(serializer.errors), {field})


class BarangayResolutionResponseContractTests(SimpleTestCase):
    def test_resolved_response_is_allowlisted_and_reduces_coordinate_precision(self):
        response = make_barangay_resolution_response(
            state=BarangayResolutionState.RESOLVED,
            latitude=14.41234567,
            longitude=120.97654321,
            barangay={"psgc_code": "0000000000", "name": "Synthetic Barangay"},
        )

        self.assertEqual(
            set(response),
            {"resolution_state", "coordinate", "barangay", "boundary", "limitations"},
        )
        self.assertEqual(response["coordinate"]["latitude"], 14.41235)
        self.assertEqual(response["coordinate"]["longitude"], 120.97654)
        self.assertEqual(
            response["coordinate"]["precision_decimal_places"],
            RESOLVER_COORDINATE_DECIMAL_PLACES,
        )
        self.assertEqual(set(response["barangay"]), {"psgc_code", "name"})
        self.assertNotIn("geometry", response)
        self.assertNotIn("susceptibility", response)
        self.assertFalse(response["boundary"]["city_verified"])

    def test_all_neutral_states_return_no_forced_barangay(self):
        for state in (
            BarangayResolutionState.OUTSIDE_BACOOR,
            BarangayResolutionState.AMBIGUOUS_BOUNDARY,
            BarangayResolutionState.UNAVAILABLE,
        ):
            with self.subTest(state=state):
                response = make_barangay_resolution_response(
                    state=state,
                    latitude=14.4,
                    longitude=120.9,
                )
                self.assertIsNone(response["barangay"])
                self.assertEqual(response["resolution_state"], state)
                self.assertEqual(
                    response["limitations"],
                    [BACOOR_REFERENCE_WARNING, BACOOR_REFERENCE_LIMITATION],
                )

    def test_resolved_requires_barangay_and_neutral_states_forbid_one(self):
        with self.assertRaises(ValidationError):
            make_barangay_resolution_response(
                state=BarangayResolutionState.RESOLVED,
                latitude=14.4,
                longitude=120.9,
            )
        with self.assertRaises(ValidationError):
            make_barangay_resolution_response(
                state=BarangayResolutionState.OUTSIDE_BACOOR,
                latitude=14.4,
                longitude=120.9,
                barangay={"psgc_code": "0000000000", "name": "Synthetic Barangay"},
            )

    def test_contract_builder_performs_no_database_access(self):
        # SimpleTestCase rejects database access, so successful construction is
        # executable proof that the Day 1 builder performs no read or write.
        make_barangay_resolution_response(
            state=BarangayResolutionState.RESOLVED,
            latitude=14.4,
            longitude=120.9,
            barangay={"psgc_code": "0000000000", "name": "Synthetic Barangay"},
        )


class EligibleBacoorBoundarySelectorTests(SimpleTestCase):
    @patch("geography.services.GeographicArea.objects")
    def test_selector_encodes_every_controlled_layer_filter(self, manager):
        selected = MagicMock(name="eligible-queryset")
        manager.select_related.return_value.filter.return_value = selected

        result = eligible_bacoor_reference_barangays()

        self.assertIs(result, selected)
        manager.select_related.assert_called_once_with("source")
        manager.select_related.return_value.filter.assert_called_once_with(
            area_type=GeographicArea.AreaType.BARANGAY,
            is_enabled=True,
            status=PublicationStatus.PENDING_VALIDATION,
            source__name=BACOOR_REFERENCE_SOURCE_NAME,
            source__source_type=DataSource.SourceType.AGENCY_DATASET,
            source__status=PublicationStatus.PENDING_VALIDATION,
            source__is_publicly_releasable=True,
        )
        self.assertEqual(BACOOR_REFERENCE_BARANGAY_COUNT, 47)
