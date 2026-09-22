"""Report technical properties of a candidate CSV/TSV without importing it."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.tabular_dataset_validation import (
    KIND_METADATA_FIELDS,
    MAX_DATASET_BYTES,
    TabularDatasetValidationError,
    validate_tabular_dataset,
)


class Command(BaseCommand):
    help = (
        "Validate and report one candidate center or rainfall table without "
        "importing, approving, activating, or publishing it."
    )

    def add_arguments(self, parser):
        parser.add_argument("path", type=Path)
        parser.add_argument("--dataset-kind", choices=KIND_METADATA_FIELDS, required=True)
        parser.add_argument("--metadata", type=Path)
        parser.add_argument("--required-field", action="append", default=[])
        parser.add_argument("--identity-field", action="append", default=[])
        parser.add_argument("--latitude-field")
        parser.add_argument("--longitude-field")
        parser.add_argument("--expected-row-count", type=int)
        parser.add_argument(
            "--fail-on-issues",
            action="store_true",
            help="Return a command error after printing a report containing issues.",
        )

    def handle(self, *args, **options):
        metadata, classifications = self._read_metadata(options["metadata"])
        try:
            report = validate_tabular_dataset(
                options["path"],
                dataset_kind=options["dataset_kind"],
                metadata=metadata,
                metadata_classifications=classifications,
                required_fields=options["required_field"],
                identity_fields=options["identity_field"],
                latitude_field=options["latitude_field"],
                longitude_field=options["longitude_field"],
                expected_row_count=options["expected_row_count"],
            )
        except TabularDatasetValidationError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
        if options["fail_on_issues"] and report["result"]["issues"]:
            raise CommandError("Dataset validation found one or more issues.")

    @staticmethod
    def _read_metadata(path: Path | None):
        if path is None:
            return {}, {}
        candidate = path.resolve()
        if not candidate.is_file():
            raise CommandError(f"Metadata file was not found: {candidate.name}")
        try:
            raw = candidate.read_bytes()
        except OSError as error:
            raise CommandError(f"Metadata file could not be read: {candidate.name}.") from error
        if len(raw) > min(MAX_DATASET_BYTES, 1024 * 1024):
            raise CommandError("Metadata file exceeds the 1048576-byte limit.")
        try:
            payload = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CommandError("Metadata file is not valid UTF-8 JSON.") from error
        if not isinstance(payload, dict):
            raise CommandError("Metadata JSON must be an object.")
        if "metadata" not in payload and "classifications" not in payload:
            return payload, {}
        metadata = payload.get("metadata", {})
        classifications = payload.get("classifications", {})
        if not isinstance(metadata, dict) or not isinstance(classifications, dict):
            raise CommandError(
                "Metadata envelope fields 'metadata' and 'classifications' must be objects."
            )
        return metadata, classifications
