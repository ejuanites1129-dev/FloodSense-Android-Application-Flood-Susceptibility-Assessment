"""Inspect a local terrain sample; optionally stage disabled local research facts."""

import csv
import json
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from geography.sample_elevation import inspect_sample
from geography.sample_elevation_import import persist_sample_summary


class Command(BaseCommand):
    help = "Describe a provisional GeoTIFF; --apply-local stages inactive pending facts only."

    def add_arguments(self, parser):
        parser.add_argument("--raster", type=Path, required=True)
        parser.add_argument(
            "--boundaries",
            type=Path,
            default=(
                Path(settings.BASE_DIR).parent
                / "research_data/administrative_boundaries/processed/"
                "bacoor_barangay_boundaries.geojson"
            ),
        )
        parser.add_argument(
            "--output-directory",
            type=Path,
            default=(Path(settings.BASE_DIR).parent / "tmp/elevation-sample"),
        )
        parser.add_argument("--assume-metres", action="store_true")
        parser.add_argument("--apply-local", action="store_true")

    def handle(self, *args, **options):
        try:
            report = inspect_sample(
                options["raster"], options["boundaries"], assume_metres=options["assume_metres"]
            )
        except Exception as error:
            raise CommandError(f"Sample inspection failed: {error}") from error
        directory = options["output_directory"].resolve() / report["version_sha256"][:16]
        report_path = directory / "terrain_report.json"
        # Versioned reports are never silently replaced. The timestamp alone is not content.
        if report_path.exists():
            existing = json.loads(report_path.read_text(encoding="utf-8"))
            if {k: v for k, v in existing.items() if k != "generated_on"} != {
                k: v for k, v in report.items() if k != "generated_on"
            }:
                raise CommandError("Existing versioned report differs; refusing overwrite.")
            report = existing
        else:
            directory.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                encoding="utf-8",
            )
        table_path = directory / "barangay_terrain_summary.csv"
        labels = {
            "data_status": "PENDING_VALIDATION",
            "elevation_unit": "m",
            "vertical_datum": "UNVERIFIED",
            "assessment_input": "NO",
            "sample_version": report["version_sha256"],
        }
        table = StringIO(newline="")
        writer = csv.DictWriter(table, fieldnames=[*report["areas"][0], *labels])
        writer.writeheader()
        writer.writerows({**area, **labels} for area in report["areas"])
        if table_path.exists():
            with table_path.open("r", newline="", encoding="utf-8-sig") as stream:
                if stream.read() != table.getvalue():
                    raise CommandError("Existing versioned table differs; refusing overwrite.")
        else:
            with table_path.open("w", newline="", encoding="utf-8-sig") as stream:
                stream.write(table.getvalue())
        self.stdout.write(report["limitations"][0])
        self.stdout.write(
            f"Raster: {report['raster']['width']} x {report['raster']['height']}; "
            f"EPSG:{report['raster']['srid']}; metres; vertical datum UNVERIFIED."
        )
        covered = sum(area["valid_cell_count"] > 0 for area in report["areas"])
        self.stdout.write(f"Barangays with valid sample cells: {covered}/47.")
        self.stdout.write(f"Report: {report_path}\nTable: {table_path}")
        if options["apply_local"]:
            try:
                result = persist_sample_summary(report)
            except Exception as error:
                raise CommandError(f"No sample import completed: {error}") from error
            self.stdout.write(f"Local staging: {result}")
        else:
            self.stdout.write(
                "INSPECTION ONLY: database unchanged. --apply-local stages "
                "pending, disabled sample facts on loopback development PostGIS."
            )
        self.stdout.write("Susceptibility logic, scenario values, colors and rules are unchanged.")
