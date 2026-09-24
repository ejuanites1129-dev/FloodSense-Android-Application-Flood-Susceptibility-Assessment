import csv
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from provenance.models import DataSource, PublicationStatus

from geography.constants import (
    MGB_PROVISIONAL_WARNING,
    MGB_SUSCEPTIBILITY_SOURCE_NAME,
    MGB_SUSCEPTIBILITY_SOURCE_URL,
)
from geography.models import (
    BarangaySusceptibilitySummary,
    FloodSusceptibilityDataset,
    GeographicArea,
)


class ProvisionalMgbFixtureMixin:
    columns = (
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
    )

    def setUp(self):
        super().setUp()
        call_command("seed_demo", verbosity=0, stdout=StringIO())
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.summary_path = Path(self.temporary_directory.name) / "summary.csv"
        self.report_path = Path(self.temporary_directory.name) / "report.json"
        self._write_files()

    def _write_files(self):
        areas = GeographicArea.objects.filter(area_type=GeographicArea.AreaType.BARANGAY).order_by(
            "name"
        )
        with self.summary_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=self.columns)
            writer.writeheader()
            for index, area in enumerate(areas):
                psgc = area.code.removeprefix("PSGC_")
                if index == 0:
                    shares = ("0", "0", "0", "0", "0", "100")
                elif index == 1:
                    shares = ("25", "0", "50", "0", "0", "25")
                else:
                    shares = ("60", "0", "0", "0", "0", "40")
                lf, mf, hf, vhf, conflict, unmapped = shares
                writer.writerow(
                    {
                        "psgc_10_digit": psgc,
                        "barangay_name": area.name,
                        "barangay_area_sqm": "100.000",
                        "lf_area_sqm": f"{DecimalString(lf)}",
                        "lf_percent": lf,
                        "mf_area_sqm": f"{DecimalString(mf)}",
                        "mf_percent": mf,
                        "hf_area_sqm": f"{DecimalString(hf)}",
                        "hf_percent": hf,
                        "vhf_area_sqm": f"{DecimalString(vhf)}",
                        "vhf_percent": vhf,
                        "conflict_area_sqm": f"{DecimalString(conflict)}",
                        "conflict_percent": conflict,
                        "unmapped_area_sqm": f"{DecimalString(unmapped)}",
                        "unmapped_percent": unmapped,
                        "partition_percent_total": "100",
                    }
                )
        self.report_path.write_text(
            json.dumps(
                {
                    "status": "PROVISIONAL_NOT_APPROVED",
                    "generated_at": "2026-09-16T14:24:25+00:00",
                    "crs": "EPSG:4326",
                    "source_url": MGB_SUSCEPTIBILITY_SOURCE_URL,
                    "warning": "Synthetic test report for provisional-import tests.",
                    "barangay_summary": {"feature_count": 47},
                }
            ),
            encoding="utf-8",
        )

    def _import(self):
        output = StringIO()
        call_command(
            "import_mgb_susceptibility",
            summary_path=self.summary_path,
            validation_report=self.report_path,
            activate_consultation_preview=True,
            stdout=output,
        )
        return output.getvalue()


def DecimalString(value: str) -> str:
    return f"{float(value):.3f}"


@override_settings(ENABLE_PROVISIONAL_MGB_PREVIEW=True)
class MgbSusceptibilityImportTests(ProvisionalMgbFixtureMixin, TestCase):
    def test_import_is_complete_versioned_provisional_and_idempotent(self):
        output = self._import()

        self.assertIn(MGB_PROVISIONAL_WARNING, output)
        source = DataSource.objects.get(name=MGB_SUSCEPTIBILITY_SOURCE_NAME)
        dataset = FloodSusceptibilityDataset.objects.get()
        self.assertEqual(source.source_type, DataSource.SourceType.AGENCY_DATASET)
        self.assertEqual(source.status, PublicationStatus.PENDING_VALIDATION)
        self.assertFalse(source.is_publicly_releasable)
        self.assertEqual(dataset.status, PublicationStatus.PENDING_VALIDATION)
        self.assertTrue(dataset.is_active_for_consultation)
        self.assertEqual(dataset.barangay_summaries.count(), 47)

        summaries = list(dataset.barangay_summaries.order_by("area__name"))
        self.assertIsNone(summaries[0].dominant_class)
        self.assertIsNone(summaries[0].baseline_rank)
        self.assertEqual(
            summaries[1].dominant_class,
            BarangaySusceptibilitySummary.MgbClass.HIGH,
        )
        self.assertEqual(summaries[1].baseline_rank, 3)
        ids_before = set(dataset.barangay_summaries.values_list("id", flat=True))

        self._import()

        self.assertEqual(FloodSusceptibilityDataset.objects.count(), 1)
        self.assertEqual(DataSource.objects.filter(name=MGB_SUSCEPTIBILITY_SOURCE_NAME).count(), 1)
        self.assertEqual(
            set(dataset.barangay_summaries.values_list("id", flat=True)),
            ids_before,
        )


@override_settings(ENABLE_PROVISIONAL_MGB_PREVIEW=True)
class MgbConsultationApiTests(ProvisionalMgbFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self._import()

    def test_unified_map_uses_barangays_and_exposes_provisional_summary(self):
        response = self.client.get(
            reverse("geography:area-collection"),
            {"mode": "demonstration"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["features"]), 47)
        self.assertEqual(payload["data_status"], PublicationStatus.PENDING_VALIDATION)
        self.assertIn(MGB_PROVISIONAL_WARNING, payload["warnings"])
        self.assertTrue(
            all(
                feature["properties"]["area_type"] == GeographicArea.AreaType.BARANGAY
                for feature in payload["features"]
            )
        )
        self.assertTrue(
            all(
                feature["properties"]["susceptibility_summary"] is not None
                for feature in payload["features"]
            )
        )

    @override_settings(ENABLE_PROVISIONAL_MGB_PREVIEW=False)
    def test_preview_setting_fails_closed_to_neutral_demo_zones(self):
        response = self.client.get(
            reverse("geography:area-collection"),
            {"mode": "demonstration"},
        )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload["features"]), 4)
        self.assertTrue(
            all(
                feature["properties"]["area_type"]
                == GeographicArea.AreaType.DEMO_ZONE
                for feature in payload["features"]
            )
        )
        self.assertIsNone(payload["susceptibility_dataset"])

    def test_assessment_uses_derived_baseline_and_preserves_zero_coverage(self):
        summaries = list(
            BarangaySusceptibilitySummary.objects.select_related("area").order_by("area__name")
        )
        unmapped = summaries[0]
        high = summaries[1]
        scenario = {
            "mode": "demonstration",
            "rainfall_intensity_code": "DEMO_HEAVY",
            "rainfall_duration_code": "DEMO_6_HOURS",
        }

        high_response = self.client.post(
            reverse("expert:evaluate"),
            {**scenario, "geographic_area_id": high.area_id},
            content_type="application/json",
        )
        unmapped_response = self.client.post(
            reverse("expert:evaluate"),
            {**scenario, "geographic_area_id": unmapped.area_id},
            content_type="application/json",
        )

        self.assertEqual(high_response.status_code, 200)
        high_payload = high_response.json()
        self.assertEqual(high_payload["assessment_state"], "CLASSIFIED")
        self.assertEqual(high_payload["susceptibility"]["code"], "HIGH")
        self.assertEqual(high_payload["facts"]["zone_baseline_rank"], 3)
        self.assertEqual(high_payload["facts"]["mgb_dominant_mapped_class"], "HF")
        self.assertIn(MGB_PROVISIONAL_WARNING, high_payload["warnings"])

        self.assertEqual(unmapped_response.status_code, 200)
        self.assertEqual(
            unmapped_response.json()["assessment_state"],
            "INSUFFICIENT_DATA",
        )
        self.assertIsNone(unmapped_response.json()["susceptibility"])
