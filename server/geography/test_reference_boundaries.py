from io import StringIO

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from provenance.models import DataSource, PublicationStatus

from .constants import (
    BACOOR_REFERENCE_LIMITATION,
    BACOOR_REFERENCE_SOURCE_NAME,
    BACOOR_REFERENCE_WARNING,
)
from .models import AreaFact, GeographicArea


def rectangle():
    polygon = Polygon(
        ((120, 14), (120, 14.01), (120.01, 14.01), (120.01, 14), (120, 14)),
        srid=4326,
    )
    return MultiPolygon(polygon, srid=4326)


class BacoorBoundaryImportTests(TestCase):
    def _import(self):
        stdout = StringIO()
        call_command("import_bacoor_boundaries", stdout=stdout)
        return stdout.getvalue()

    def test_import_creates_pending_reference_source_city_and_47_barangays(self):
        output = self._import()

        source = DataSource.objects.get(name=BACOOR_REFERENCE_SOURCE_NAME)
        self.assertEqual(source.status, PublicationStatus.PENDING_VALIDATION)
        self.assertEqual(source.source_type, DataSource.SourceType.AGENCY_DATASET)
        self.assertTrue(source.is_publicly_releasable)
        self.assertEqual(source.geographic_areas.count(), 48)
        self.assertEqual(
            source.geographic_areas.filter(
                area_type=GeographicArea.AreaType.BARANGAY
            ).count(),
            47,
        )
        self.assertTrue(
            source.geographic_areas.filter(
                code="PSGC_0402103000", area_type=GeographicArea.AreaType.CITY
            ).exists()
        )
        self.assertFalse(AreaFact.objects.filter(area__source=source).exists())
        self.assertIn("DERIVED ADMINISTRATIVE REFERENCE - NOT CITY-VERIFIED", output)

    def test_import_is_idempotent_and_preserves_area_ids(self):
        self._import()
        before = dict(
            GeographicArea.objects.filter(source__name=BACOOR_REFERENCE_SOURCE_NAME)
            .values_list("code", "id")
        )

        self._import()

        after = dict(
            GeographicArea.objects.filter(source__name=BACOOR_REFERENCE_SOURCE_NAME)
            .values_list("code", "id")
        )
        self.assertEqual(after, before)

    def test_import_refuses_to_take_code_owned_by_another_source(self):
        other = DataSource.objects.create(
            name="Conflicting source",
            source_type=DataSource.SourceType.OTHER,
            status=PublicationStatus.PENDING_VALIDATION,
        )
        GeographicArea.objects.create(
            code="PSGC_0402103000",
            name="Conflict",
            area_type=GeographicArea.AreaType.CITY,
            geometry=rectangle(),
            source=other,
            status=PublicationStatus.PENDING_VALIDATION,
            is_enabled=True,
        )

        with self.assertRaises(CommandError):
            self._import()

        self.assertFalse(
            DataSource.objects.filter(name=BACOOR_REFERENCE_SOURCE_NAME).exists()
        )


class ReferenceBoundaryApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("import_bacoor_boundaries", stdout=StringIO())

    def test_endpoint_returns_exactly_47_neutral_barangay_features(self):
        response = self.client.get(reverse("geography:reference-boundary-collection"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["type"], "FeatureCollection")
        self.assertEqual(payload["layer_kind"], "ADMINISTRATIVE_REFERENCE")
        self.assertEqual(payload["data_status"], "PENDING_VALIDATION")
        self.assertEqual(
            payload["warnings"],
            [BACOOR_REFERENCE_WARNING, BACOOR_REFERENCE_LIMITATION],
        )
        self.assertEqual(len(payload["features"]), 47)
        self.assertEqual(
            {feature["properties"]["area_type"] for feature in payload["features"]},
            {GeographicArea.AreaType.BARANGAY},
        )
        self.assertNotIn("susceptibility", payload["features"][0]["properties"])

    def test_endpoint_excludes_unrelated_pending_barangay(self):
        source = DataSource.objects.create(
            name="Unrelated pending source",
            source_type=DataSource.SourceType.OTHER,
            status=PublicationStatus.PENDING_VALIDATION,
            is_publicly_releasable=True,
        )
        GeographicArea.objects.create(
            code="UNRELATED_REFERENCE_AREA",
            name="Unrelated",
            area_type=GeographicArea.AreaType.BARANGAY,
            geometry=rectangle(),
            source=source,
            status=PublicationStatus.PENDING_VALIDATION,
            is_enabled=True,
        )

        response = self.client.get(reverse("geography:reference-boundary-collection"))

        codes = {
            feature["properties"]["code"] for feature in response.json()["features"]
        }
        self.assertNotIn("UNRELATED_REFERENCE_AREA", codes)
