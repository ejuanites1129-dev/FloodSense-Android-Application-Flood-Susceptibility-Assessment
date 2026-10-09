"""Synthetic terrain fixtures, never actual agency data or susceptibility rules."""

import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.gis.gdal import GDALRaster
from django.contrib.gis.geos import Polygon
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from .sample_elevation import (
    band_calibration,
    file_sha256,
    inspect_sample,
    summarize_polygon,
    valid_value,
)


class SampleElevationStatisticsTests(SimpleTestCase):
    def summarize(self, polygon=None, **kwargs):
        return summarize_polygon(
            polygon or Polygon.from_bbox((0, 0, 2, 2)),
            values=kwargs.pop("values", [-1, 0, -9999, 2]),
            width=2,
            height=2,
            origin=(0, 2),
            pixel_scale=(1, -1),
            nodata=-9999,
            **kwargs,
        )

    def test_negative_zero_and_missing_are_distinct(self):
        stats = self.summarize()
        self.assertEqual(stats["cell_count"], 4)
        self.assertEqual(stats["valid_cell_count"], 3)
        self.assertEqual(stats["coverage_percent"], 75)
        self.assertEqual(stats["minimum"], -1)
        self.assertEqual(stats["mean"], 0.3333)
        self.assertEqual(stats["maximum"], 2)

    def test_nodata_excluded_before_scale_and_offset(self):
        stats = self.summarize(scale=2, offset=10)
        self.assertEqual(stats["minimum"], 8)
        self.assertEqual(stats["mean"], 10.6667)
        self.assertEqual(stats["maximum"], 14)
        self.assertEqual(stats["valid_cell_count"], 3)

    def test_outside_raster_is_in_coverage_denominator_not_zero_height(self):
        stats = self.summarize(Polygon.from_bbox((0, 0, 4, 2)))
        self.assertEqual(stats["cell_count"], 8)
        self.assertEqual(stats["coverage_percent"], 37.5)
        self.assertEqual(stats["mean"], 0.3333)
        missing = self.summarize(Polygon.from_bbox((10, 10, 12, 12)))
        self.assertEqual(missing["valid_cell_count"], 0)
        self.assertIsNone(missing["mean"])
        self.assertIsNone(missing["minimum"])

    def test_polygon_holes_are_not_sampled(self):
        geometry = Polygon(
            ((0, 0), (2, 0), (2, 2), (0, 2), (0, 0)),
            ((0.1, 1.1), (0.9, 1.1), (0.9, 1.9), (0.1, 1.9), (0.1, 1.1)),
        )
        stats = self.summarize(geometry)
        self.assertEqual(stats["cell_count"], 3)
        self.assertEqual(stats["valid_cell_count"], 2)
        self.assertEqual(stats["minimum"], 0)

    def test_nonfinite_values_and_nan_nodata_are_not_valid(self):
        self.assertIsNone(valid_value(float("nan"), nodata=float("nan")))
        self.assertIsNone(valid_value(float("inf"), nodata=-9999))
        self.assertEqual(valid_value(0, nodata=-9999), 0)

    def test_boundary_grid_limits_reject_unbounded_processing(self):
        with self.assertRaisesMessage(ValueError, "too large"):
            self.summarize(Polygon.from_bbox((0, 0, 10000, 10000)))


class SampleElevationRasterTests(SimpleTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.raster_path = self.root / "synthetic.tif"
        self.boundary_path = self.root / "boundaries.geojson"
        raster = GDALRaster(
            {
                "driver": "GTiff",
                "name": str(self.raster_path),
                "width": 2,
                "height": 2,
                "srid": 4326,
                "origin": [120, 15],
                "scale": [0.01, -0.01],
                "datatype": 6,
                "bands": [{"data": [-1, 0, -9999, 2], "nodata_value": -9999}],
            }
        )
        del raster
        features = []
        for index in range(1, 48):
            geometry = Polygon.from_bbox((120, 14.98, 120.02, 15))
            features.append(
                {
                    "type": "Feature",
                    "geometry": json.loads(geometry.geojson),
                    "properties": {
                        "psgc_10_digit": f"0402103{index:03d}",
                        "adm4_name": f"Synthetic area {index}",
                    },
                }
            )
        self.boundary_path.write_text(
            json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8"
        )

    def test_untagged_units_require_explicit_sample_assumption(self):
        with self.assertRaisesMessage(ValueError, "Metre band units"):
            inspect_sample(self.raster_path, self.boundary_path)
        report = inspect_sample(self.raster_path, self.boundary_path, assume_metres=True)
        self.assertIn("Operator-assumed", report["raster"]["unit_basis"])
        self.assertEqual(report["raster"]["vertical_datum"], "UNVERIFIED")
        self.assertEqual(len(report["areas"]), 47)

    def test_inspection_preserves_originals_and_deterministic_version(self):
        before = file_sha256(self.raster_path), file_sha256(self.boundary_path)
        first = inspect_sample(self.raster_path, self.boundary_path, assume_metres=True)
        second = inspect_sample(self.raster_path, self.boundary_path, assume_metres=True)
        self.assertEqual(first["version_sha256"], second["version_sha256"])
        self.assertEqual(before, (file_sha256(self.raster_path), file_sha256(self.boundary_path)))
        self.assertNotIn(str(self.root), json.dumps(first))

    def test_foreign_units_are_not_overridden_by_assume_metres(self):
        with patch("geography.sample_elevation.band_calibration", return_value=("ft", 1, 0)):
            with self.assertRaisesMessage(ValueError, "Metre band units"):
                inspect_sample(self.raster_path, self.boundary_path, assume_metres=True)

    def test_native_band_metadata_defaults_are_readable(self):
        raster = GDALRaster(str(self.raster_path), write=False)
        self.assertEqual(band_calibration(raster.bands[0]), ("", 1, 0))

    def test_float32_nonrepresentable_nodata_does_not_become_valid(self):
        raster = GDALRaster(str(self.raster_path), write=True)
        raster.bands[0].nodata_value = 0.1
        raster.bands[0].data([0.1, 0, 0.1, 2])
        del raster
        report = inspect_sample(self.raster_path, self.boundary_path, assume_metres=True)
        self.assertEqual(report["areas"][0]["valid_cell_count"], 2)
        self.assertEqual(report["areas"][0]["mean"], 1)

    def test_disguised_vrt_is_rejected_before_gdal_opens_it(self):
        path = self.root / "disguised.tif"
        path.write_text('<VRTDataset rasterXSize="2" rasterYSize="2"/>', encoding="utf-8")
        with patch("geography.sample_elevation.GDALRaster") as opener:
            with self.assertRaisesMessage(ValueError, "TIFF header"):
                inspect_sample(path, self.boundary_path)
            opener.assert_not_called()

    def test_explicit_validity_masks_fail_closed(self):
        from ctypes import c_int, c_void_p

        from django.contrib.gis.gdal.libgdal import function

        raster = GDALRaster(str(self.raster_path), write=True)
        function("GDALCreateMaskBand", [c_void_p, c_int], c_int)(raster.bands[0]._ptr, 2)
        del raster
        with self.assertRaises(ValueError):
            inspect_sample(self.raster_path, self.boundary_path, assume_metres=True)

    def test_command_is_read_only_and_rejects_edited_table(self):
        output = StringIO()
        options = {
            "raster": self.raster_path,
            "boundaries": self.boundary_path,
            "assume_metres": True,
            "output_directory": self.root / "output",
        }
        call_command("inspect_elevation_sample", stdout=output, **options)
        self.assertIn("database unchanged", output.getvalue())
        table_path = next((self.root / "output").rglob("*.csv"))
        self.assertIn("PENDING_VALIDATION", table_path.read_text(encoding="utf-8-sig"))
        call_command("inspect_elevation_sample", stdout=StringIO(), **options)
        table_path.write_text("edited", encoding="utf-8-sig")
        with self.assertRaisesMessage(CommandError, "table differs"):
            call_command("inspect_elevation_sample", stdout=StringIO(), **options)

    def test_projected_raster_transforms_geojson_without_interpolation(self):
        geometry = Polygon.from_bbox((120, 14.98, 120.02, 15))
        geometry.srid = 4326
        projected = geometry.transform(32651, clone=True)
        xmin, ymin, xmax, ymax = projected.extent
        raster = GDALRaster(
            {
                "driver": "GTiff",
                "name": str(self.root / "projected.tif"),
                "width": 2,
                "height": 2,
                "srid": 32651,
                "origin": [xmin, ymax],
                "scale": [(xmax - xmin) / 2, -(ymax - ymin) / 2],
                "datatype": 6,
                "bands": [{"data": [-1, 0, -9999, 2], "nodata_value": -9999}],
            }
        )
        del raster
        report = inspect_sample(self.root / "projected.tif", self.boundary_path, assume_metres=True)
        self.assertEqual(report["raster"]["srid"], 32651)
        self.assertEqual(report["areas"][0]["valid_cell_count"], 3)
        self.assertEqual(report["areas"][0]["mean"], 0.3333)
