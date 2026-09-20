"""Report technical properties of a candidate GeoJSON file without importing it."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from geography.dataset_validation import (
    DatasetValidationError,
    validate_geojson_dataset,
)


class Command(BaseCommand):
    help = (
        "Validate and report one candidate GeoJSON file without importing, "
        "approving, activating, or publishing it."
    )

    def add_arguments(self, parser):
        parser.add_argument("path", type=Path)
        parser.add_argument("--identity-field", action="append", default=[])
        parser.add_argument("--expected-geometry-type", action="append", default=[])
        parser.add_argument("--expected-feature-count", type=int)
        parser.add_argument("--expected-crs")
        parser.add_argument(
            "--fail-on-issues",
            action="store_true",
            help="Return a command error after printing a report containing issues.",
        )

    def handle(self, *args, **options):
        try:
            report = validate_geojson_dataset(
                options["path"],
                identity_fields=options["identity_field"],
                expected_geometry_types=options["expected_geometry_type"],
                expected_feature_count=options["expected_feature_count"],
                expected_crs=options["expected_crs"],
            )
        except DatasetValidationError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
        if options["fail_on_issues"] and report["result"]["issues"]:
            raise CommandError("Dataset validation found one or more issues.")
