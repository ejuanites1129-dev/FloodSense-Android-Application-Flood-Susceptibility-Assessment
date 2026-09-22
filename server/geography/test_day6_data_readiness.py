import hashlib
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase

from .dataset_validation import DatasetValidationError, validate_geojson_dataset


def feature(identifier, coordinates, *, geometry_type="Polygon"):
    return {
        "type": "Feature",
        "properties": {"public_id": identifier},
        "geometry": {"type": geometry_type, "coordinates": coordinates},
    }


def polygon(west=0):
    return [
        [
            [west, 0],
            [west + 1, 0],
            [west + 1, 1],
            [west, 1],
            [west, 0],
        ]
    ]


class GeographicDatasetValidationTests(SimpleTestCase):
    def write_dataset(self, directory: str, payload: dict) -> Path:
        path = Path(directory) / "synthetic.geojson"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_valid_report_is_deterministic_read_only_and_preserves_unknowns(self):
        payload = {
            "type": "FeatureCollection",
            "name": "Synthetic validation fixture",
            "bbox": [0, 0, 2, 1],
            "metadata": {"crs": "EPSG:4326", "source": "Synthetic test only"},
            "features": [feature("A", polygon()), feature("B", polygon(1))],
        }
        with TemporaryDirectory() as directory:
            path = self.write_dataset(directory, payload)
            before = path.read_bytes()

            report = validate_geojson_dataset(
                path,
                identity_fields=("public_id",),
                expected_geometry_types=("Polygon",),
                expected_feature_count=2,
                expected_crs="EPSG:4326",
            )

            self.assertEqual(path.read_bytes(), before)
        self.assertEqual(report["mode"], "READ_ONLY_VALIDATION")
        self.assertEqual(report["file"]["sha256"], hashlib.sha256(before).hexdigest().upper())
        self.assertEqual(report["structure"]["feature_count"], 2)
        self.assertEqual(report["structure"]["geometry_types"], {"Polygon": 2})
        self.assertEqual(report["quality"]["property_fields"], ["public_id"])
        self.assertEqual(report["quality"]["missing_property_counts"], {"public_id": 0})
        self.assertEqual(report["metadata"]["license"], "unknown")
        self.assertEqual(report["metadata_provenance"]["source"], "DATASET_DECLARED")
        self.assertEqual(report["metadata_provenance"]["license"], "MISSING")
        self.assertEqual(report["file"]["fact_provenance"]["sha256"], "VERIFIED_BY_TOOL")
        self.assertEqual(report["inferred_metadata_fields"], [])
        self.assertEqual(report["result"]["status"], "PASS")
        self.assertEqual(report["result"]["approval_effect"], "NONE")

    def test_missing_duplicate_null_empty_and_invalid_values_are_reported(self):
        payload = {
            "type": "FeatureCollection",
            "features": [
                feature("duplicate", polygon()),
                feature("duplicate", polygon(1)),
                feature("", polygon(2)),
                {"type": "Feature", "properties": {}, "geometry": None},
                feature(
                    "invalid",
                    [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]],
                ),
            ],
        }
        with TemporaryDirectory() as directory:
            report = validate_geojson_dataset(
                self.write_dataset(directory, payload),
                identity_fields=("public_id",),
                expected_geometry_types=("MultiPolygon",),
                expected_feature_count=47,
                expected_crs="EPSG:4326",
            )

        self.assertEqual(report["result"]["status"], "ISSUES_FOUND")
        self.assertEqual(report["quality"]["missing_identity_counts"], {"public_id": 2})
        self.assertEqual(
            report["quality"]["duplicate_identity_counts"],
            {"public_id": 1},
        )
        self.assertEqual(report["quality"]["null_geometry_count"], 1)
        self.assertEqual(report["quality"]["invalid_geometry_count"], 1)
        self.assertEqual(report["quality"]["missing_property_counts"]["public_id"], 2)
        self.assertTrue(
            any("Unexpected geometry types" in item for item in report["result"]["issues"])
        )
        self.assertTrue(any("unknown" in item for item in report["result"]["issues"]))

    def test_command_outputs_json_and_can_fail_on_reported_issues(self):
        payload = {
            "type": "FeatureCollection",
            "features": [feature("A", polygon())],
        }
        with TemporaryDirectory() as directory:
            path = self.write_dataset(directory, payload)
            stdout = StringIO()
            call_command(
                "validate_geographic_dataset",
                path,
                identity_field=["public_id"],
                expected_geometry_type=["Polygon"],
                expected_feature_count=1,
                stdout=stdout,
            )
            report = json.loads(stdout.getvalue())
            self.assertEqual(report["result"]["status"], "PASS")

            with self.assertRaisesMessage(CommandError, "found one or more issues"):
                call_command(
                    "validate_geographic_dataset",
                    path,
                    expected_feature_count=2,
                    fail_on_issues=True,
                    stdout=StringIO(),
                )

    def test_missing_or_non_geojson_input_fails_without_database_access(self):
        with TemporaryDirectory() as directory:
            missing_path = Path(directory) / "missing.geojson"
            with self.assertRaisesMessage(DatasetValidationError, "missing.geojson") as error:
                validate_geojson_dataset(missing_path)
            self.assertNotIn(str(Path(directory).resolve()), str(error.exception))
            path = Path(directory) / "invalid.geojson"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesMessage(
                DatasetValidationError, "Expected a GeoJSON FeatureCollection"
            ):
                validate_geojson_dataset(path)
