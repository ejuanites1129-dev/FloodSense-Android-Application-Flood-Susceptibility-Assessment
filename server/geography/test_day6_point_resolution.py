from unittest.mock import patch

from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import TestCase
from django.urls import reverse
from provenance.models import DataSource, PublicationStatus
from provenance.policies import DEMONSTRATION_WARNING

from .models import GeographicArea
from .services import PointResolutionInputError, resolve_area_for_point


def rectangle(west=120.0, south=14.0, size=0.01):
    polygon = Polygon(
        (
            (west, south),
            (west, south + size),
            (west + size, south + size),
            (west + size, south),
            (west, south),
        ),
        srid=4326,
    )
    return MultiPolygon(polygon, srid=4326)


class Day6PointResolutionTests(TestCase):
    def setUp(self):
        self.source = DataSource.objects.create(
            name="DEMONSTRATION DATA—NOT OFFICIAL",
            source_type=DataSource.SourceType.DEMONSTRATION,
            status=PublicationStatus.DEMONSTRATION,
            permitted_use="Fictional Day 6 point-resolution tests only.",
        )
        self.area = self._area()

    def _area(self, **overrides):
        values = {
            "code": "DEMO_ZONE_A",
            "name": "Demo Zone A",
            "area_type": GeographicArea.AreaType.DEMO_ZONE,
            "geometry": rectangle(),
            "source": self.source,
            "status": PublicationStatus.DEMONSTRATION,
            "is_enabled": True,
        }
        values.update(overrides)
        return GeographicArea.objects.create(**values)

    def _post(self, **overrides):
        payload = {
            "mode": "demonstration",
            "latitude": 14.005,
            "longitude": 120.005,
        }
        payload.update(overrides)
        return self.client.post(
            reverse("geography:resolve-point"),
            payload,
            content_type="application/json",
        )

    def test_inside_point_returns_resolved_safe_area_fields_and_warnings(self):
        response = self._post()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["resolution_state"], "RESOLVED")
        self.assertEqual(
            payload["area"],
            {
                "id": self.area.id,
                "code": "DEMO_ZONE_A",
                "name": "Demo Zone A",
                "area_type": "DEMO_ZONE",
                "data_status": "DEMONSTRATION",
            },
        )
        self.assertEqual(payload["warnings"][0], DEMONSTRATION_WARNING)
        self.assertNotIn("geometry", payload["area"])

    def test_point_is_constructed_in_longitude_latitude_order(self):
        with patch("geography.services.Point", wraps=Point) as point_factory:
            result = resolve_area_for_point(
                latitude=14.005,
                longitude=120.005,
                mode="demonstration",
            )

        point_factory.assert_called_once_with(120.005, 14.005, srid=4326)
        self.assertEqual(result["resolution_state"], "RESOLVED")

    def test_boundary_point_is_covered(self):
        response = self._post(latitude=14.0, longitude=120.0)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["resolution_state"], "RESOLVED")

    def test_outside_point_returns_neutral_outcome(self):
        response = self._post(latitude=13.0, longitude=119.0)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["resolution_state"], "OUTSIDE_SUPPORTED_AREA")
        self.assertIsNone(response.json()["area"])

    def test_overlapping_eligible_areas_are_ambiguous(self):
        self._area(code="DEMO_ZONE_B", name="Demo Zone B")

        response = self._post()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["resolution_state"], "AMBIGUOUS_AREA")
        self.assertIsNone(response.json()["area"])

    def test_disabled_area_is_ignored(self):
        self.area.is_enabled = False
        self.area.save(update_fields=("is_enabled",))

        response = self._post()

        self.assertEqual(response.json()["resolution_state"], "OUTSIDE_SUPPORTED_AREA")

    def test_ineligible_statuses_and_official_records_are_excluded(self):
        self.area.delete()
        for index, status in enumerate(
            (
                PublicationStatus.PENDING_VALIDATION,
                PublicationStatus.RESTRICTED,
                PublicationStatus.RETIRED,
            ),
            start=1,
        ):
            self._area(
                code=f"DEMO_INELIGIBLE_{index}",
                name=f"Ineligible demonstration area {index}",
                status=status,
            )
        approved_source = DataSource.objects.create(
            name="Approved point test source",
            source_type=DataSource.SourceType.AGENCY_DATASET,
            status=PublicationStatus.APPROVED,
            is_publicly_releasable=True,
        )
        self._area(
            code="OFFICIAL_TEST_AREA",
            name="Approved test area",
            source=approved_source,
            status=PublicationStatus.APPROVED,
        )

        response = self._post()

        self.assertEqual(response.json()["resolution_state"], "OUTSIDE_SUPPORTED_AREA")

    def test_invalid_and_missing_coordinates_return_http_400(self):
        cases = (
            ({"latitude": 91}, "latitude"),
            ({"longitude": 181}, "longitude"),
            ({"latitude": "not-a-number"}, "latitude"),
        )
        for changes, field in cases:
            with self.subTest(changes=changes):
                response = self._post(**changes)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())

        response = self.client.post(
            reverse("geography:resolve-point"),
            {"mode": "demonstration", "latitude": 14.005},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("longitude", response.json())

    def test_invalid_mode_is_rejected_by_service_and_api(self):
        with self.assertRaises(PointResolutionInputError):
            resolve_area_for_point(latitude=14, longitude=120, mode="invalid")

        response = self._post(mode="invalid")
        self.assertEqual(response.status_code, 400)
        self.assertIn("mode", response.json())

    def test_coordinate_is_not_persisted(self):
        area_count = GeographicArea.objects.count()
        source_count = DataSource.objects.count()

        self._post()

        self.assertEqual(GeographicArea.objects.count(), area_count)
        self.assertEqual(DataSource.objects.count(), source_count)
