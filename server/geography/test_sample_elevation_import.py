"""Synthetic reports verify inactive sample storage, never production imports."""

import copy
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import connections
from django.test import TestCase, override_settings
from expert.services import _assemble_area_facts, evaluate_assessment
from provenance.models import DataSource, PublicationStatus
from provenance.policies import permitted_records

from .models import AreaFact, GeographicArea
from .sample_elevation_import import (
    SCHEMA,
    SOURCE_PREFIX,
    SampleElevationImportError,
    geometry_sha256,
    persist_sample_summary,
    report_version_sha256,
)


@override_settings(DEBUG=True, GIS_ENABLED=True, ENABLE_PROVISIONAL_MGB_PREVIEW=False)
class SampleElevationImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0, stdout=StringIO())

    def setUp(self):
        self.report = {
            "schema": SCHEMA,
            "generated_on": "2026-10-09",
            "raster": {
                "sha256": "a" * 64,
                "filename": "synthetic-sample.tif",
                "srid": 32651,
                "width": 100,
                "height": 100,
                "unit": "m",
                "unit_basis": "Synthetic test-only metre assumption, not provider verification.",
                "vertical_datum": "UNVERIFIED",
                "pixel_scale": [30.0, -30.0],
                "origin": [270000.0, 1600000.0],
                "scale": 1,
                "offset": 0,
                "nodata": -9999,
            },
            "boundaries": {"sha256": "b" * 64, "filename": "synthetic-boundaries.geojson"},
            "limitations": [
                "Synthetic test-only sample; not LiPAD, official data, or susceptibility.",
                "Vertical datum and original rights unverified. "
                "Cell count coverage is not area coverage.",
            ],
            "areas": [
                {
                    "code": area.code,
                    "name": area.name,
                    "geometry_sha256": geometry_sha256(area.geometry),
                    "cell_count": 100,
                    "valid_cell_count": 80,
                    "coverage_percent": 80,
                    "minimum": -2,
                    "mean": 0,
                    "maximum": 10,
                }
                for area in GeographicArea.objects.filter(
                    area_type=GeographicArea.AreaType.BARANGAY
                ).order_by("code")
            ],
        }
        self._rehash()

    def _rehash(self):
        self.report["version_sha256"] = report_version_sha256(self.report)

    def _persist(self):
        return persist_sample_summary(self.report)

    def _assert_rejected_without_write(self):
        source_count, fact_count = DataSource.objects.count(), AreaFact.objects.count()
        with self.assertRaises(SampleElevationImportError):
            self._persist()
        self.assertEqual(DataSource.objects.count(), source_count)
        self.assertEqual(AreaFact.objects.count(), fact_count)

    def test_complete_pending_disabled_immutable_idempotent_storage(self):
        before = list(GeographicArea.objects.values("id", "code", "name", "status", "is_enabled"))
        result = self._persist()
        source = DataSource.objects.get(pk=result["source_id"])
        self.assertTrue(result["created"])
        self.assertEqual(result["fact_count"], 47 * 6)
        self.assertEqual(source.name, SOURCE_PREFIX + self.report["version_sha256"][:16])
        self.assertEqual(source.source_type, DataSource.SourceType.OTHER)
        self.assertEqual(source.status, PublicationStatus.PENDING_VALIDATION)
        self.assertFalse(source.is_publicly_releasable)
        self.assertIsNone(source.reviewed_by_id)
        self.assertFalse(
            source.area_facts.exclude(status=PublicationStatus.PENDING_VALIDATION).exists()
        )
        self.assertFalse(source.area_facts.filter(is_enabled=True).exists())
        self.assertEqual(
            source.area_facts.get(
                area__code=self.report["areas"][0]["code"], fact_key="sample_elevation_min"
            ).numeric_value,
            -2,
        )
        provenance = source.processing_notes
        identities = set(source.area_facts.values_list("id", flat=True))
        self.report["generated_on"] = "2026-10-10"
        replay = self._persist()
        self.assertFalse(replay["created"])
        self.assertEqual(replay["source_id"], source.id)
        source.refresh_from_db()
        self.assertEqual(source.processing_notes, provenance)
        self.assertEqual(source.received_or_created_on.isoformat(), "2026-10-09")
        self.assertEqual(set(source.area_facts.values_list("id", flat=True)), identities)
        self.assertEqual(
            list(GeographicArea.objects.values("id", "code", "name", "status", "is_enabled")),
            before,
        )

    def test_no_valid_cells_do_not_create_zero_terrain_facts(self):
        row = self.report["areas"][0]
        row.update(valid_cell_count=0, coverage_percent=0, minimum=None, mean=None, maximum=None)
        self._rehash()
        result = self._persist()
        facts = AreaFact.objects.filter(source_id=result["source_id"], area__code=row["code"])
        self.assertEqual(result["fact_count"], 47 * 6 - 3)
        self.assertEqual(
            set(facts.values_list("fact_key", flat=True)),
            {
                "sample_elevation_valid_cell_count",
                "sample_elevation_cell_count",
                "sample_elevation_coverage_percent",
            },
        )

    def test_pending_sample_is_excluded_in_both_modes_and_baseline_unchanged(self):
        previous_baselines = list(
            AreaFact.objects.filter(fact_key="zone_baseline_rank").values(
                "id", "numeric_value", "source_id", "status", "is_enabled"
            )
        )
        previous = evaluate_assessment(
            area_identifier="DEMO_ZONE_A",
            intensity_code="DEMO_HEAVY",
            duration_code="DEMO_6_HOURS",
            mode="DEMONSTRATION",
        )
        result = self._persist()
        area = GeographicArea.objects.get(code=self.report["areas"][0]["code"])
        for mode in ("DEMONSTRATION", "OFFICIAL"):
            self.assertEqual(_assemble_area_facts(area, mode), ({}, set()))
            self.assertFalse(
                permitted_records(
                    AreaFact.objects.filter(source_id=result["source_id"]), mode
                ).exists()
            )
        self.assertEqual(
            evaluate_assessment(
                area_identifier="DEMO_ZONE_A",
                intensity_code="DEMO_HEAVY",
                duration_code="DEMO_6_HOURS",
                mode="DEMONSTRATION",
            ),
            previous,
        )
        self.assertEqual(
            previous_baselines,
            list(
                AreaFact.objects.filter(fact_key="zone_baseline_rank").values(
                    "id", "numeric_value", "source_id", "status", "is_enabled"
                )
            ),
        )

    def test_report_hash_binds_stats_and_metadata_not_generation_date(self):
        changed = copy.deepcopy(self.report)
        changed["generated_on"] = "2027-01-01"
        self.assertEqual(report_version_sha256(changed), self.report["version_sha256"])
        self.report["areas"][0]["mean"] = 1
        self._assert_rejected_without_write()

    def test_rejects_missing_duplicate_and_unknown_barangay_identities(self):
        original = copy.deepcopy(self.report)
        for mutation in ("missing", "duplicate", "unknown"):
            with self.subTest(mutation=mutation):
                self.report = copy.deepcopy(original)
                if mutation == "missing":
                    self.report["areas"].pop()
                elif mutation == "duplicate":
                    self.report["areas"][-1] = copy.deepcopy(self.report["areas"][0])
                else:
                    self.report["areas"][0]["code"] = "NOT_BACOOR"
                self._rehash()
                self._assert_rejected_without_write()

    def test_rejects_changed_boundary_name_geometry_or_status(self):
        for field, value in (("name", "Wrong name"), ("geometry_sha256", "d" * 64)):
            original = copy.deepcopy(self.report)
            with self.subTest(field=field):
                self.report["areas"][0][field] = value
                self._rehash()
                self._assert_rejected_without_write()
            self.report = original
        area = GeographicArea.objects.get(code=self.report["areas"][0]["code"])
        area.is_enabled = False
        area.save(update_fields=("is_enabled",))
        self._assert_rejected_without_write()

    def test_rejects_bad_counts_coverage_statistics_units_datum_and_paths(self):
        original = copy.deepcopy(self.report)
        cases = (
            ("area", "cell_count", -1),
            ("area", "valid_cell_count", 101),
            ("area", "coverage_percent", 81),
            ("area", "mean", 100),
            ("area", "minimum", "NaN"),
            ("area", "maximum", "Infinity"),
            ("area", "mean", None),
            ("area", "cell_count", True),
            ("raster", "unit", "cm"),
            ("raster", "unit_basis", ""),
            ("raster", "vertical_datum", "Mean sea level"),
            ("raster", "filename", "C:/private/terrain.tif"),
            ("raster", "pixel_scale", [0, -30]),
        )
        for section, field, value in cases:
            with self.subTest(section=section, field=field, value=value):
                self.report = copy.deepcopy(original)
                target = self.report["areas"][0] if section == "area" else self.report[section]
                target[field] = value
                self._rehash()
                self._assert_rejected_without_write()

    def test_rejects_zero_substitution_for_no_valid_cells(self):
        self.report["areas"][0].update(valid_cell_count=0, coverage_percent=0)
        self._rehash()
        self._assert_rejected_without_write()

    def test_rejects_modified_source_without_overwriting_it(self):
        result = self._persist()
        source = DataSource.objects.get(pk=result["source_id"])
        for field, value in (
            ("status", PublicationStatus.APPROVED),
            ("notes", "Edited"),
            ("is_publicly_releasable", True),
        ):
            with self.subTest(field=field):
                original = getattr(source, field)
                setattr(source, field, value)
                source.save(update_fields=(field,))
                self._assert_rejected_without_write()
                source.refresh_from_db()
                self.assertEqual(getattr(source, field), value)
                setattr(source, field, original)
                source.save(update_fields=(field,))

    def test_rejects_modified_missing_or_duplicate_facts(self):
        result = self._persist()
        fact = AreaFact.objects.filter(source_id=result["source_id"]).first()
        for field, value in (("numeric_value", 999), ("unit", "cm"), ("is_enabled", True)):
            with self.subTest(field=field):
                original = getattr(fact, field)
                setattr(fact, field, value)
                fact.save(update_fields=(field,))
                self._assert_rejected_without_write()
                setattr(fact, field, original)
                fact.save(update_fields=(field,))
        AreaFact.objects.create(
            source_id=result["source_id"],
            area=fact.area,
            fact_key=fact.fact_key,
            numeric_value=fact.numeric_value,
            unit=fact.unit,
            status=PublicationStatus.PENDING_VALIDATION,
        )
        self._assert_rejected_without_write()

    def test_requires_debug_and_actual_loopback_postgis_connection(self):
        with override_settings(DEBUG=False):
            self._assert_rejected_without_write()
        database = connections["default"].settings_dict
        for engine, host in (
            (database["ENGINE"], "db.example.org"),
            (database["ENGINE"], "192.168.1.10"),
            ("django.db.backends.sqlite3", "localhost"),
            (database["ENGINE"], ""),
        ):
            with (
                self.subTest(engine=engine, host=host),
                patch.dict(database, {"ENGINE": engine, "HOST": host}),
                self.assertRaises(SampleElevationImportError),
            ):
                self._persist()

    def test_unexpected_source_identity_refuses_takeover(self):
        DataSource.objects.create(
            name=SOURCE_PREFIX + self.report["version_sha256"][:16],
            source_type=DataSource.SourceType.AGENCY_DATASET,
            status=PublicationStatus.APPROVED,
            version="other-owner",
        )
        self._assert_rejected_without_write()

    def test_new_version_preserves_previous_version_and_unrelated_facts(self):
        first = self._persist()
        previous_ids = set(
            AreaFact.objects.filter(source_id=first["source_id"]).values_list("id", flat=True)
        )
        self.report["areas"][0]["mean"] = 1
        self._rehash()
        second = self._persist()
        self.assertNotEqual(first["source_id"], second["source_id"])
        self.assertEqual(
            set(AreaFact.objects.filter(source_id=first["source_id"]).values_list("id", flat=True)),
            previous_ids,
        )
        self.assertEqual(AreaFact.objects.filter(fact_key="zone_baseline_rank").count(), 4)

    def test_missing_fact_and_unexpected_source_owned_records_are_rejected(self):
        result = self._persist()
        fact = AreaFact.objects.filter(source_id=result["source_id"]).first()
        fact.delete()
        self._assert_rejected_without_write()

    def test_source_cannot_be_reused_for_geographic_records(self):
        result = self._persist()
        area = GeographicArea.objects.get(code=self.report["areas"][0]["code"])
        GeographicArea.objects.create(
            code="SYNTHETIC_TEST_UNEXPECTED_SAMPLE_OWNER",
            name="Synthetic test-only area",
            area_type=GeographicArea.AreaType.OTHER,
            geometry=area.geometry,
            source_id=result["source_id"],
            status=PublicationStatus.PENDING_VALIDATION,
        )
        self._assert_rejected_without_write()

    def test_failure_creating_facts_rolls_back_source_and_all_facts(self):
        original_save = AreaFact.save
        calls = 0

        def fail_second_save(fact, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise SampleElevationImportError("Synthetic write failure")
            return original_save(fact, *args, **kwargs)

        with patch.object(AreaFact, "save", fail_second_save):
            self._assert_rejected_without_write()
