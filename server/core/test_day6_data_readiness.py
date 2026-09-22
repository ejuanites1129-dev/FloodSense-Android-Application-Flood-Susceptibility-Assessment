import hashlib
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase

from .tabular_dataset_validation import (
    TabularDatasetValidationError,
    validate_tabular_dataset,
)

CENTER_METADATA = {
    "dataset_name": "Synthetic center validation fixture",
    "custodian": "Synthetic test custodian",
    "license": "Test-only terms",
    "usage_restrictions": "Testing only",
    "public_release_status": "Not for release",
    "geographic_coverage": "Synthetic coordinate plane",
    "version": "test-1",
    "crs": "EPSG:4326",
    "coordinate_fields": ["latitude", "longitude"],
    "known_limitations": "Fictional records",
    "declared_validation_status": "Synthetic fixture only",
}


class TabularDatasetValidationTests(SimpleTestCase):
    def write(self, directory: str, name: str, content: str) -> Path:
        path = Path(directory) / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_center_report_is_deterministic_read_only_and_preserves_unknowns(self):
        content = (
            "center_id,name,address,latitude,longitude\n"
            "fixture-1,Synthetic Alpha,Test address,14.4000,120.9000\n"
            "fixture-2,Synthetic Beta,Test address,14.5000,121.0000\n"
        )
        with TemporaryDirectory() as directory:
            path = self.write(directory, "synthetic-centers.csv", content)
            before = path.read_bytes()

            report = validate_tabular_dataset(
                path,
                dataset_kind="evacuation_centers",
                metadata=CENTER_METADATA,
                required_fields=("center_id", "name", "address", "latitude", "longitude"),
                identity_fields=("center_id",),
                latitude_field="latitude",
                longitude_field="longitude",
                expected_row_count=2,
            )

            self.assertEqual(path.read_bytes(), before)
        self.assertEqual(report["mode"], "READ_ONLY_VALIDATION")
        self.assertEqual(report["file"]["sha256"], hashlib.sha256(before).hexdigest().upper())
        self.assertEqual(report["structure"]["row_count"], 2)
        self.assertEqual(report["metadata"]["organization"], "unknown")
        self.assertEqual(report["metadata_provenance"]["organization"], "MISSING")
        self.assertEqual(report["metadata_provenance"]["custodian"], "USER_SUPPLIED")
        self.assertEqual(report["file"]["fact_provenance"]["sha256"], "VERIFIED_BY_TOOL")
        self.assertEqual(report["inferred_metadata_fields"], [])
        self.assertEqual(report["result"]["status"], "PASS")
        self.assertEqual(report["result"]["import_effect"], "NONE")
        self.assertEqual(report["result"]["approval_effect"], "NONE")
        self.assertEqual(report["result"]["activation_effect"], "NONE")

    def test_quality_issues_are_counts_and_do_not_disclose_record_values(self):
        restricted_marker = "RESTRICTED-IDENTIFIER-DO-NOT-REPORT"
        content = (
            "center_id,name,latitude,longitude\n"
            f"{restricted_marker},Synthetic Alpha,91,not-a-coordinate\n"
            f"{restricted_marker},,14.4,120.9,extra-value\n"
        )
        with TemporaryDirectory() as directory:
            report = validate_tabular_dataset(
                self.write(directory, "candidate.csv", content),
                dataset_kind="evacuation_centers",
                metadata={},
                required_fields=("center_id", "name", "address"),
                identity_fields=("center_id",),
                latitude_field="latitude",
                longitude_field="longitude",
                expected_row_count=3,
            )

        self.assertEqual(report["result"]["status"], "ISSUES_FOUND")
        self.assertEqual(report["quality"]["duplicate_identity_counts"], {"center_id": 1})
        self.assertEqual(
            report["quality"]["coordinate_quality"]["latitude"]["out_of_range_count"], 1
        )
        self.assertEqual(report["quality"]["coordinate_quality"]["longitude"]["invalid_count"], 1)
        self.assertEqual(report["structure"]["malformed_row_count"], 1)
        self.assertNotIn(restricted_marker, str(report))
        self.assertNotIn("extra-value", str(report))

    def test_restricted_metadata_is_redacted_and_provisional_status_is_explicit(self):
        private_license = "PRIVATE-LICENSE-TEXT-DO-NOT-REPORT"
        with TemporaryDirectory() as directory:
            report = validate_tabular_dataset(
                self.write(directory, "candidate.csv", "id,name\nfixture,Example\n"),
                dataset_kind="generic",
                metadata={"license": private_license, "public_release_status": "Not approved"},
                metadata_classifications={
                    "license": "RESTRICTED",
                    "public_release_status": "PROVISIONAL",
                },
            )

        self.assertEqual(report["metadata"]["license"], "restricted")
        self.assertEqual(report["metadata_provenance"]["license"], "REDACTED_RESTRICTED")
        self.assertEqual(report["metadata_classification"]["license"], "RESTRICTED")
        self.assertEqual(report["metadata_classification"]["public_release_status"], "PROVISIONAL")
        self.assertNotIn(private_license, str(report))

    def test_rainfall_metadata_and_missing_values_are_reported_without_schema_assumptions(self):
        metadata = {
            "dataset_name": "Synthetic rainfall fixture",
            "custodian": "Synthetic test custodian",
            "license": "Test-only terms",
            "usage_restrictions": "Testing only",
            "public_release_status": "Not for release",
            "geographic_coverage": "Synthetic area",
            "temporal_coverage": "Synthetic period",
            "version": "test-1",
            "units": "millimetres per hour",
            "period_of_record": "Synthetic dates",
            "time_resolution": "Synthetic intervals",
            "missing_values": "Blank cells",
            "known_limitations": "Fictional values",
            "declared_validation_status": "Synthetic fixture only",
        }
        with TemporaryDirectory() as directory:
            report = validate_tabular_dataset(
                self.write(directory, "synthetic-rainfall.tsv", "station\tvalue\nfixture\t\n"),
                dataset_kind="rainfall_reference",
                metadata=metadata,
                required_fields=("station", "value"),
            )

        self.assertEqual(report["file"]["format"], "TSV")
        self.assertEqual(report["quality"]["missing_value_counts"]["value"], 1)
        self.assertTrue(
            any("Required field 'value'" in issue for issue in report["result"]["issues"])
        )

    def test_command_outputs_json_and_can_fail_on_issues(self):
        content = "center_id,name,address,latitude,longitude\nfixture-1,Alpha,A,14,120\n"
        with TemporaryDirectory() as directory:
            data_path = self.write(directory, "centers.csv", content)
            metadata_path = Path(directory) / "metadata.json"
            metadata_path.write_text(
                json.dumps(
                    {
                        "metadata": CENTER_METADATA,
                        "classifications": {"public_release_status": "PROVISIONAL"},
                    }
                ),
                encoding="utf-8",
            )
            stdout = StringIO()
            call_command(
                "validate_tabular_dataset",
                data_path,
                dataset_kind="evacuation_centers",
                metadata=metadata_path,
                required_field=["center_id", "name", "address", "latitude", "longitude"],
                identity_field=["center_id"],
                latitude_field="latitude",
                longitude_field="longitude",
                expected_row_count=1,
                stdout=stdout,
            )
            output = json.loads(stdout.getvalue())
            self.assertEqual(output["result"]["status"], "PASS")
            self.assertEqual(
                output["metadata_classification"]["public_release_status"], "PROVISIONAL"
            )

            with self.assertRaisesMessage(CommandError, "found one or more issues"):
                call_command(
                    "validate_tabular_dataset",
                    data_path,
                    dataset_kind="evacuation_centers",
                    expected_row_count=2,
                    fail_on_issues=True,
                    stdout=StringIO(),
                )

    def test_missing_and_unsupported_inputs_fail_without_disclosing_directories(self):
        with TemporaryDirectory() as directory:
            missing = Path(directory) / "restricted-candidate.csv"
            with self.assertRaisesMessage(
                TabularDatasetValidationError, "restricted-candidate.csv"
            ) as error:
                validate_tabular_dataset(missing, dataset_kind="generic")
            self.assertNotIn(str(Path(directory).resolve()), str(error.exception))

            unsupported = self.write(directory, "candidate.xlsx", "not a spreadsheet")
            with self.assertRaisesMessage(TabularDatasetValidationError, ".csv or .tsv"):
                validate_tabular_dataset(unsupported, dataset_kind="generic")
