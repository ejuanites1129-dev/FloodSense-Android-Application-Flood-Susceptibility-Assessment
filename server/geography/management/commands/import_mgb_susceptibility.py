"""Import a reviewed local MGB area-summary snapshot for consultation preview."""

import csv
import hashlib
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from provenance.models import DataSource, PublicationStatus

from geography.constants import (
    BACOOR_REFERENCE_BARANGAY_COUNT,
    BACOOR_REFERENCE_SOURCE_NAME,
    MGB_PROVISIONAL_WARNING,
    MGB_SUSCEPTIBILITY_SOURCE_NAME,
    MGB_SUSCEPTIBILITY_SOURCE_URL,
)
from geography.models import (
    BarangaySusceptibilitySummary,
    FloodSusceptibilityDataset,
    GeographicArea,
)

EXPECTED_COLUMNS = {
    "psgc_10_digit",
    "barangay_name",
    "barangay_area_sqm",
    "lf_area_sqm",
    "lf_percent",
    "mf_area_sqm",
    "mf_percent",
    "hf_area_sqm",
    "hf_percent",
    "vhf_area_sqm",
    "vhf_percent",
    "conflict_area_sqm",
    "conflict_percent",
    "unmapped_area_sqm",
    "unmapped_percent",
    "partition_percent_total",
}
CLASS_FIELDS = {
    BarangaySusceptibilitySummary.MgbClass.LOW: "lf_percent",
    BarangaySusceptibilitySummary.MgbClass.MODERATE: "mf_percent",
    BarangaySusceptibilitySummary.MgbClass.HIGH: "hf_percent",
    BarangaySusceptibilitySummary.MgbClass.VERY_HIGH: "vhf_percent",
}
CLASS_RANKS = {
    BarangaySusceptibilitySummary.MgbClass.LOW: 1,
    BarangaySusceptibilitySummary.MgbClass.MODERATE: 2,
    BarangaySusceptibilitySummary.MgbClass.HIGH: 3,
    BarangaySusceptibilitySummary.MgbClass.VERY_HIGH: 4,
}


class Command(BaseCommand):
    help = (
        "Import the local provisional DENR-MGB barangay area-composition table. "
        "The command never marks the data approved or publicly releasable."
    )

    def add_arguments(self, parser):
        repository_root = Path(__file__).resolve().parents[4]
        processed = (
            repository_root
            / "research_data"
            / "provisional"
            / "mgb_flood_susceptibility"
            / "processed"
        )
        parser.add_argument(
            "--summary-path",
            type=Path,
            default=processed / "barangay_susceptibility_area_summary.csv",
        )
        parser.add_argument(
            "--validation-report",
            type=Path,
            default=processed / "validation_report.json",
        )
        parser.add_argument(
            "--activate-consultation-preview",
            action="store_true",
            help=(
                "Use this version in the local scenario-based consultation flow. "
                "This is not an approval or production-publication action."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["activate_consultation_preview"] and (
            not settings.DEBUG or not settings.ENABLE_PROVISIONAL_MGB_PREVIEW
        ):
            raise CommandError(
                "Activation requires DJANGO_DEBUG and the explicit local "
                "FLOODSENSE_ENABLE_PROVISIONAL_MGB_PREVIEW setting."
            )
        summary_path = options["summary_path"].resolve()
        report_path = options["validation_report"].resolve()
        summary_bytes = self._read_file(summary_path, "summary CSV")
        report_bytes = self._read_file(report_path, "validation report")
        report = self._parse_report(report_bytes)
        rows = self._parse_rows(summary_bytes)
        self._validate_report(report, rows)

        source = self._source(report)
        summary_hash = hashlib.sha256(summary_bytes).hexdigest().upper()
        report_hash = hashlib.sha256(report_bytes).hexdigest().upper()
        generated_at = self._generated_at(report["generated_at"])
        version = f"{generated_at.date().isoformat()}-{summary_hash[:12].lower()}"
        code = f"mgb-bacoor-{generated_at:%Y%m%d}-{summary_hash[:12].lower()}"

        dataset, created = FloodSusceptibilityDataset.objects.get_or_create(
            code=code,
            defaults={
                "name": "MGB Bacoor provisional barangay susceptibility summary",
                "version": version,
                "source": source,
                "source_accessed_on": datetime.strptime("2026-09-16", "%Y-%m-%d").date(),
                "generated_at": generated_at,
                "summary_sha256": summary_hash,
                "validation_sha256": report_hash,
            },
        )
        if not created and dataset.source_id != source.id:
            raise CommandError("The dataset identity is owned by a different source.")

        dataset.name = "MGB Bacoor provisional barangay susceptibility summary"
        dataset.version = version
        dataset.source = source
        dataset.source_field = "FloodSusc"
        dataset.source_accessed_on = datetime.strptime("2026-09-16", "%Y-%m-%d").date()
        dataset.generated_at = generated_at
        dataset.aggregation_method = (
            FloodSusceptibilityDataset.AggregationMethod.DOMINANT_MAPPED_AREA
        )
        dataset.summary_sha256 = summary_hash
        dataset.validation_sha256 = report_hash
        dataset.status = PublicationStatus.PENDING_VALIDATION
        dataset.is_active_for_consultation = False
        dataset.notes = (
            "Local consultation preview only. Map date/version, scale, methodology, "
            "class definitions, attribution, and redistribution terms still require "
            "verification. The dominant class is derived by FloodSense."
        )
        dataset.full_clean()
        dataset.save()

        areas = self._areas_by_psgc()
        expected_area_ids = set()
        classifiable = 0
        for row in rows:
            psgc = row["psgc_10_digit"]
            area = areas.get(psgc)
            if area is None:
                raise CommandError(f"No controlled Bacoor barangay uses PSGC {psgc}.")
            if area.name.strip().casefold() != row["barangay_name"].strip().casefold():
                raise CommandError(
                    f"Barangay name mismatch for PSGC {psgc}: "
                    f"{row['barangay_name']!r} != {area.name!r}."
                )
            values = self._decimal_values(row, psgc)
            dominant_class, dominant_percent, baseline_rank = self._dominant(values)
            expected_area_ids.add(area.id)
            classifiable += int(dominant_class is not None)
            summary, _ = BarangaySusceptibilitySummary.objects.get_or_create(
                dataset=dataset,
                area=area,
                defaults=values,
            )
            for field, value in values.items():
                setattr(summary, field, value)
            summary.dominant_class = dominant_class
            summary.dominant_percent = dominant_percent
            summary.baseline_rank = baseline_rank
            summary.full_clean()
            summary.save()

        unexpected = dataset.barangay_summaries.exclude(area_id__in=expected_area_ids).exists()
        if unexpected:
            raise CommandError("The existing dataset contains summaries absent from this snapshot.")
        if dataset.barangay_summaries.count() != BACOOR_REFERENCE_BARANGAY_COUNT:
            raise CommandError("The import did not produce exactly 47 barangay summaries.")

        if options["activate_consultation_preview"]:
            FloodSusceptibilityDataset.objects.filter(is_active_for_consultation=True).exclude(
                pk=dataset.pk
            ).update(is_active_for_consultation=False)
            dataset.is_active_for_consultation = True
            dataset.full_clean()
            dataset.save(update_fields=("is_active_for_consultation", "updated_at"))

        action = "Activated" if dataset.is_active_for_consultation else "Imported"
        self.stdout.write(self.style.WARNING(MGB_PROVISIONAL_WARNING))
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} provisional version {dataset.version}: "
                f"{len(rows)} summaries, {classifiable} with a unique mapped dominant "
                f"class and {len(rows) - classifiable} without one."
            )
        )

    def _read_file(self, path: Path, label: str) -> bytes:
        try:
            return path.read_bytes()
        except OSError as error:
            raise CommandError(f"Unable to read {label} at {path}: {error}") from error

    def _parse_report(self, content: bytes) -> dict:
        try:
            report = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CommandError("The validation report is not valid UTF-8 JSON.") from error
        if not isinstance(report, dict):
            raise CommandError("The validation report must be a JSON object.")
        return report

    def _parse_rows(self, content: bytes) -> list[dict[str, str]]:
        try:
            reader = csv.DictReader(StringIO(content.decode("utf-8-sig")))
            if set(reader.fieldnames or ()) != EXPECTED_COLUMNS:
                raise CommandError("The susceptibility summary columns do not match.")
            rows = list(reader)
        except UnicodeDecodeError as error:
            raise CommandError("The summary CSV is not valid UTF-8.") from error
        psgc_codes = [row["psgc_10_digit"] for row in rows]
        if len(rows) != BACOOR_REFERENCE_BARANGAY_COUNT:
            raise CommandError("The summary CSV must contain exactly 47 rows.")
        if len(set(psgc_codes)) != len(psgc_codes):
            raise CommandError("The summary CSV contains duplicate PSGC codes.")
        if any(len(code) != 10 or not code.isdigit() for code in psgc_codes):
            raise CommandError("Every summary row must use a 10-digit PSGC code.")
        return rows

    def _validate_report(self, report: dict, rows: list[dict[str, str]]) -> None:
        if report.get("status") != "PROVISIONAL_NOT_APPROVED":
            raise CommandError("The report must remain PROVISIONAL_NOT_APPROVED.")
        if report.get("source_url") != MGB_SUSCEPTIBILITY_SOURCE_URL:
            raise CommandError("The validation report source URL is unexpected.")
        if report.get("crs") != "EPSG:4326":
            raise CommandError("Only the reviewed EPSG:4326 output is supported.")
        count = report.get("barangay_summary", {}).get("feature_count")
        if count != len(rows):
            raise CommandError("The report and summary barangay counts do not match.")
        self._generated_at(report.get("generated_at"))

    def _generated_at(self, value) -> datetime:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as error:
            raise CommandError("The report generated_at value is invalid.") from error
        if timezone.is_naive(parsed):
            raise CommandError("The report generated_at value must include a timezone.")
        return parsed

    def _source(self, report: dict) -> DataSource:
        matches = list(DataSource.objects.filter(name=MGB_SUSCEPTIBILITY_SOURCE_NAME))
        if len(matches) > 1:
            raise CommandError("Multiple records use the reserved MGB source name.")
        source = matches[0] if matches else DataSource(name=MGB_SUSCEPTIBILITY_SOURCE_NAME)
        if source.pk and source.source_type != DataSource.SourceType.AGENCY_DATASET:
            raise CommandError("The reserved MGB source name has an incompatible type.")
        source.organization = "DENR - Mines and Geosciences Bureau"
        source.source_type = DataSource.SourceType.AGENCY_DATASET
        source.coverage_description = (
            "Bacoor-clipped provisional extract summarized against the 47 current "
            "barangay reference polygons."
        )
        source.received_or_created_on = self._generated_at(report["generated_at"]).date()
        source.version = "Provisional ArcGIS snapshot accessed 2026-09-16"
        source.permitted_use = (
            "Local thesis consultation preview only; attribution and redistribution "
            "conditions require confirmation before publication or deployment."
        )
        source.processing_notes = (
            "Cross-class overlaps are CONFLICT; uncovered City area is UNMAPPED. "
            "No conflict is silently resolved to a susceptibility class."
        )
        source.limitations = str(report.get("warning", ""))
        source.citation_url = MGB_SUSCEPTIBILITY_SOURCE_URL
        source.status = PublicationStatus.PENDING_VALIDATION
        source.is_publicly_releasable = False
        source.notes = "Imported only by the controlled provisional MGB command."
        source.full_clean()
        source.save()
        return source

    def _areas_by_psgc(self) -> dict[str, GeographicArea]:
        areas = list(
            GeographicArea.objects.select_related("source").filter(
                area_type=GeographicArea.AreaType.BARANGAY,
                is_enabled=True,
                status=PublicationStatus.PENDING_VALIDATION,
                source__name=BACOOR_REFERENCE_SOURCE_NAME,
            )
        )
        if len(areas) != BACOOR_REFERENCE_BARANGAY_COUNT:
            raise CommandError("Import the controlled 47-barangay Bacoor boundary layer first.")
        result = {}
        for area in areas:
            prefix = "PSGC_"
            if not area.code.startswith(prefix):
                raise CommandError(f"Unexpected barangay code {area.code!r}.")
            result[area.code[len(prefix) :]] = area
        if len(result) != BACOOR_REFERENCE_BARANGAY_COUNT:
            raise CommandError("The controlled barangay layer has duplicate PSGC identities.")
        return result

    def _decimal_values(self, row: dict[str, str], psgc: str) -> dict[str, Decimal]:
        fields = EXPECTED_COLUMNS - {"psgc_10_digit", "barangay_name"}
        try:
            values = {field: Decimal(row[field]) for field in fields}
        except (InvalidOperation, TypeError) as error:
            raise CommandError(f"Invalid numeric value for PSGC {psgc}.") from error
        if any(value < 0 for value in values.values()):
            raise CommandError(f"Negative area or percentage for PSGC {psgc}.")
        calculated = sum(
            values[field]
            for field in (
                "lf_percent",
                "mf_percent",
                "hf_percent",
                "vhf_percent",
                "conflict_percent",
                "unmapped_percent",
            )
        )
        if abs(calculated - values["partition_percent_total"]) > Decimal("0.01"):
            raise CommandError(f"Partition percentages do not reconcile for PSGC {psgc}.")
        return values

    def _dominant(
        self,
        values: dict[str, Decimal],
    ) -> tuple[str | None, Decimal | None, int | None]:
        shares = {code: values[field] for code, field in CLASS_FIELDS.items()}
        maximum = max(shares.values())
        winners = [code for code, value in shares.items() if value == maximum]
        if maximum == 0 or len(winners) != 1:
            return None, None, None
        winner = winners[0]
        return winner, maximum, CLASS_RANKS[winner]
