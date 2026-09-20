from django.test import TestCase
from evacuation.models import EvacuationCenter

from .models import GeographicArea
from .serializers import BarangayResolutionState
from .services import public_psgc_code, resolve_bacoor_barangay
from .test_day2_barangay_resolver import (
    BarangayResolverTestData,
    multipolygon,
    rectangle,
)


class MunicipalBoundaryIntegrationTests(BarangayResolverTestData, TestCase):
    def test_point_just_inside_city_boundary_resolves_only_when_covered(self):
        self.make_ready_layer(
            target_geometry=multipolygon(rectangle(-1, 4, 1)),
        )

        result = resolve_bacoor_barangay(
            latitude=4.5,
            longitude=-0.999999,
        )

        self.assertEqual(result.state, BarangayResolutionState.RESOLVED)
        self.assertEqual(result.barangay_psgc_code, "0000000001")

    def test_point_just_outside_city_boundary_is_not_reassigned(self):
        self.make_ready_layer(
            target_geometry=multipolygon(rectangle(-1, 4, 1)),
        )

        result = resolve_bacoor_barangay(
            latitude=4.5,
            longitude=-1.000001,
        )

        self.assertEqual(result.state, BarangayResolutionState.OUTSIDE_BACOOR)
        self.assertIsNone(result.barangay)

    def test_exact_municipal_boundary_without_barangay_coverage_fails_closed(self):
        self.make_ready_layer()

        result = resolve_bacoor_barangay(latitude=5, longitude=-1)

        self.assertEqual(result.state, BarangayResolutionState.UNAVAILABLE)
        self.assertIsNone(result.barangay)

    def test_coastal_or_water_gap_inside_city_is_not_arbitrarily_assigned(self):
        self.make_ready_layer()

        result = resolve_bacoor_barangay(latitude=10.5, longitude=0)

        self.assertEqual(result.state, BarangayResolutionState.UNAVAILABLE)
        self.assertIsNone(result.barangay)

    def test_distinct_barangays_on_shared_boundary_remain_ambiguous(self):
        self.make_ready_layer(
            target_geometry=multipolygon(rectangle(0, 0, 1)),
            second_geometry=multipolygon(rectangle(1, 0, 1)),
        )

        result = resolve_bacoor_barangay(latitude=0.5, longitude=1)

        self.assertEqual(
            result.state,
            BarangayResolutionState.AMBIGUOUS_BOUNDARY,
        )
        self.assertIsNone(result.barangay)


class CenterBarangayIdentityCompatibilityTests(BarangayResolverTestData, TestCase):
    def test_center_relation_and_resolver_share_stable_psgc_identity(self):
        source, area = self.make_ready_layer()
        center = EvacuationCenter.objects.create(
            name="Synthetic test-only center",
            address="Synthetic test address",
            geographic_area=area,
            latitude=0.499999,
            longitude=0.499999,
            source=source,
        )

        resolved = resolve_bacoor_barangay(latitude=0.499999, longitude=0.499999)

        self.assertEqual(resolved.state, BarangayResolutionState.RESOLVED)
        self.assertEqual(
            resolved.barangay_psgc_code,
            public_psgc_code(center.geographic_area.code),
        )
        self.assertNotEqual(resolved.barangay_psgc_code, str(area.pk))

    def test_mutable_or_historical_label_does_not_replace_stable_identity(self):
        source, area = self.make_ready_layer()
        center = EvacuationCenter.objects.create(
            name="Synthetic test-only center",
            address="Synthetic test address",
            geographic_area=area,
            latitude=0.25,
            longitude=0.25,
            source=source,
        )
        stable_identity = public_psgc_code(area.code)
        area.name = "Synthetic historical label"
        area.save(update_fields=("name",))

        center.refresh_from_db()

        self.assertEqual(
            public_psgc_code(center.geographic_area.code),
            stable_identity,
        )
        self.assertEqual(center.geographic_area.name, "Synthetic historical label")

    def test_center_near_municipal_boundary_does_not_change_user_resolution(self):
        source, area = self.make_ready_layer()
        EvacuationCenter.objects.create(
            name="Synthetic outside-edge center",
            address="Synthetic test address",
            geographic_area=area,
            latitude=4.5,
            longitude=-1.000001,
            source=source,
        )

        result = resolve_bacoor_barangay(latitude=4.5, longitude=-1.000001)

        self.assertEqual(result.state, BarangayResolutionState.OUTSIDE_BACOOR)
        self.assertIsNone(result.barangay)

    def test_center_coordinate_near_shared_boundary_uses_neutral_resolver_result(self):
        source, area = self.make_ready_layer(
            target_geometry=multipolygon(rectangle(0, 0, 1)),
            second_geometry=multipolygon(rectangle(1, 0, 1)),
        )
        center = EvacuationCenter.objects.create(
            name="Synthetic boundary center",
            address="Synthetic test address",
            geographic_area=area,
            latitude=0.5,
            longitude=1,
            source=source,
        )

        result = resolve_bacoor_barangay(
            latitude=float(center.latitude),
            longitude=float(center.longitude),
        )

        self.assertEqual(
            result.state,
            BarangayResolutionState.AMBIGUOUS_BOUNDARY,
        )
        self.assertIsNone(result.barangay)

    def test_absent_controlled_layer_returns_no_identity_and_writes_nothing(self):
        before = {
            "areas": GeographicArea.objects.count(),
            "centers": EvacuationCenter.objects.count(),
        }

        result = resolve_bacoor_barangay(latitude=0, longitude=0)

        self.assertEqual(result.state, BarangayResolutionState.UNAVAILABLE)
        self.assertEqual(GeographicArea.objects.count(), before["areas"])
        self.assertEqual(EvacuationCenter.objects.count(), before["centers"])

    def test_resolver_result_contains_no_susceptibility_or_center_payload(self):
        self.make_ready_layer()

        result = resolve_bacoor_barangay(latitude=0.25, longitude=0.25)

        self.assertFalse(hasattr(result, "susceptibility"))
        self.assertFalse(hasattr(result, "centers"))
        self.assertEqual(
            set(result.barangay or {}),
            {"psgc_code", "name"},
        )
