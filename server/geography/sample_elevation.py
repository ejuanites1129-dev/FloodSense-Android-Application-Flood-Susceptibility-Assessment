"""Descriptive, provisional terrain processing; never susceptibility inference."""

import hashlib
import json
import math
from ctypes import POINTER, byref, c_char_p, c_double, c_float, c_int, c_void_p
from datetime import date
from pathlib import Path

from django.contrib.gis.gdal import GDALRaster
from django.contrib.gis.gdal.libgdal import function
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Point

from .sample_elevation_import import geometry_sha256, report_version_sha256

MAX_RASTER_CELLS = 2_000_000
MAX_AREA_GRID_CELLS = 2_000_000
LIMITATIONS = [
    "PROVISIONAL SAMPLE TERRAIN — NOT APPROVED LiPAD DATA OR FLOOD INFORMATION.",
    "The delivery filename identifies FABDEM; original source/version/license need review.",
    "Raster vertical datum is UNVERIFIED; do not claim heights above local mean sea level.",
    "Statistics describe valid cell centers inside derived administrative boundaries, "
    "not surveyed house elevations, area-weighted values, or flood depths.",
    "Coverage is the valid fraction of grid centers inside each polygon, not its area share. "
    "NoData and outside-raster cells are not zero; negative valid elevations are retained.",
    "No susceptibility thresholds, weights, classes, MGB baseline or expert rules are changed.",
    "Stored sample facts remain pending validation, disabled and unavailable to inference.",
]


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def band_calibration(band):
    """Read GDAL's actual unit/scale/offset, not a filename or QGIS display range."""
    get_unit = function("GDALGetRasterUnitType", [c_void_p], c_char_p)
    raw_unit = (get_unit(band._ptr) or b"").decode("utf-8")
    values = []
    for name, default in (("GDALGetRasterScale", 1.0), ("GDALGetRasterOffset", 0.0)):
        success = c_int()
        getter = function(name, [c_void_p, POINTER(c_int)], c_double)
        value = getter(band._ptr, byref(success))
        values.append(float(value) if success.value else default)
    if not all(math.isfinite(value) for value in values) or values[0] == 0:
        raise ValueError("Raster scale/offset must be finite and scale must be nonzero.")
    return raw_unit, *values


def raster_dependencies(raster, raster_path):
    """Fail closed on disguised VRTs, remote dependencies or external raster sidecars."""
    if raster.driver.name != "GTiff":
        raise ValueError("The input must actually be a GeoTIFF, not just have a TIFF suffix.")
    get_files = function("GDALGetFileList", [c_void_p], POINTER(c_char_p))
    free_files = function("CSLDestroy", [POINTER(c_char_p)], None)
    files = get_files(raster.ptr)
    dependencies = []
    try:
        if files:
            index = 0
            while files[index]:
                if index >= 16:
                    raise ValueError("Unexpectedly many sample dependencies.")
                candidate = Path(files[index].decode("utf-8")).resolve(strict=True)
                if candidate != raster_path.resolve():
                    if candidate != Path(str(raster_path.resolve()) + ".aux.xml"):
                        raise ValueError(
                            "Only the local TIFF and its optional .aux.xml are supported."
                        )
                    dependencies.append(
                        {"filename": candidate.name, "sha256": file_sha256(candidate)}
                    )
                index += 1
    finally:
        if files:
            free_files(files)
    return sorted(dependencies, key=lambda item: item["filename"])


def valid_value(raw, *, nodata, scale=1.0, offset=0.0):
    value = float(raw)
    if not math.isfinite(value) or (nodata is not None and value == nodata):
        return None
    result = value * scale + offset
    if not math.isfinite(result):
        return None
    return result


def summarize_polygon(
    geometry, *, values, width, height, origin, pixel_scale, nodata, scale=1.0, offset=0.0
):
    """Cell-center summary, including missing grid centers outside the raster."""
    sx, sy = pixel_scale
    ox, oy = origin
    if not all(math.isfinite(v) for v in (sx, sy, ox, oy)) or sx <= 0 or sy >= 0:
        raise ValueError("Only finite north-up rasters with positive X scale are supported.")
    if geometry.empty or not geometry.valid:
        raise ValueError("Boundary geometry must be valid and nonempty.")
    xmin, ymin, xmax, ymax = geometry.extent
    columns = (math.floor((xmin - ox) / sx) - 1, math.ceil((xmax - ox) / sx) + 1)
    rows = (math.floor((ymax - oy) / sy) - 1, math.ceil((ymin - oy) / sy) + 1)
    if (columns[1] - columns[0]) * (rows[1] - rows[0]) > MAX_AREA_GRID_CELLS:
        raise ValueError("Boundary grid is too large for this bounded sample processor.")
    prepared = geometry.prepared
    cell_count = 0
    valid = []
    for row in range(*rows):
        y = oy + (row + 0.5) * sy
        for column in range(*columns):
            x = ox + (column + 0.5) * sx
            if not prepared.covers(Point(x, y)):
                continue
            cell_count += 1
            if not (0 <= row < height and 0 <= column < width):
                continue
            value = valid_value(
                values[row * width + column], nodata=nodata, scale=scale, offset=offset
            )
            if value is not None:
                valid.append(value)
    return {
        "cell_count": cell_count,
        "valid_cell_count": len(valid),
        "coverage_percent": round(100 * len(valid) / cell_count, 4) if cell_count else 0,
        "minimum": round(min(valid), 4) if valid else None,
        "mean": round(math.fsum(valid) / len(valid), 4) if valid else None,
        "maximum": round(max(valid), 4) if valid else None,
    }


def inspect_sample(raster_path, boundary_path, *, assume_metres=False):
    raster_path, boundary_path = Path(raster_path), Path(boundary_path)
    if raster_path.suffix.lower() not in {".tif", ".tiff"} or not raster_path.is_file():
        raise ValueError("Choose a local GeoTIFF sample, not a QGZ, LAS or remote datasource.")
    with raster_path.open("rb") as stream:
        if stream.read(4) not in {b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"}:
            raise ValueError("A TIFF header is required before opening the datasource.")
    raster_hash, boundary_hash = file_sha256(raster_path), file_sha256(boundary_path)
    raster = GDALRaster(str(raster_path), write=False)
    try:
        return _inspect_open_sample(
            raster_path, boundary_path, raster, raster_hash, boundary_hash, assume_metres
        )
    finally:
        # Explicitly release Windows file handles even when a traceback/mock retains a band.
        # Clear the pointer so GeoDjango's eventual destructor cannot double-close it.
        raster.destructor(raster.ptr)
        raster.ptr = None


def _inspect_open_sample(
    raster_path, boundary_path, raster, raster_hash, boundary_hash, assume_metres
):
    dependencies = raster_dependencies(raster, raster_path)
    if not raster.srid or len(raster.bands) != 1 or any(raster.skew):
        raise ValueError("The sample needs a known EPSG CRS and one unrotated numeric band.")
    if not (0 < raster.width * raster.height <= MAX_RASTER_CELLS):
        raise ValueError("Sample raster exceeds the bounded processing size.")
    band = raster.bands[0]
    mask_flags = function("GDALGetMaskFlags", [c_void_p], c_int)(band._ptr)
    if mask_flags not in {1, 8}:  # GMF_ALL_VALID or GDAL's ordinary NoData-derived mask.
        raise ValueError("Explicit/alpha validity masks need separate reviewed processing.")
    if band.datatype() not in {1, 2, 3, 4, 5, 6, 7}:
        raise ValueError("Complex/unsupported raster values cannot be terrain samples.")
    raw_unit, scale, offset = band_calibration(band)
    tagged_metres = raw_unit.strip().lower() in {"m", "metre", "metres", "meter", "meters"}
    if not tagged_metres and (raw_unit.strip() or not assume_metres):
        raise ValueError(
            "Metre band units are required. Only an untagged sample may use "
            "the explicit --assume-metres development option."
        )
    unit_basis = (
        "GDAL raster band unit metadata"
        if tagged_metres
        else ("Operator-assumed metres; unverified, pending research review")
    )
    data = band.data()
    values = data.ravel().tolist() if hasattr(data, "ravel") else list(data)
    nodata = band.nodata_value
    if nodata is not None and math.isinf(nodata):
        raise ValueError("Infinite NoData sentinels need separate reviewed processing.")
    # GDAL may report e.g. 0.1 although Float32 storage holds 0.10000000149.
    comparison_nodata = (
        c_float(nodata).value if nodata is not None and band.datatype() == 6 else nodata
    )
    valid = [
        value
        for raw in values
        if (value := valid_value(raw, nodata=comparison_nodata, scale=scale, offset=offset))
        is not None
    ]
    payload = json.loads(boundary_path.read_text(encoding="utf-8"))
    if payload.get("type") != "FeatureCollection" or len(payload.get("features", [])) != 47:
        raise ValueError("Use the complete current 47-barangay reference GeoJSON.")
    areas, seen = [], set()
    for feature in payload["features"]:
        properties = feature["properties"]
        code = f"PSGC_{properties['psgc_10_digit']}"
        if code in seen or not code.startswith("PSGC_0402103") or len(code) != 15:
            raise ValueError("Expected unique Bacoor barangay PSGC codes.")
        seen.add(code)
        geometry = GEOSGeometry(json.dumps(feature["geometry"]), srid=4326)
        if geometry.geom_type == "Polygon":
            geometry = MultiPolygon(geometry, srid=4326)
        if geometry.geom_type != "MultiPolygon":
            raise ValueError("Expected polygonal barangay geometry.")
        geometry_hash = geometry_sha256(geometry)
        projected = geometry.transform(raster.srid, clone=True)
        statistics = summarize_polygon(
            projected,
            values=values,
            width=raster.width,
            height=raster.height,
            origin=list(raster.origin),
            pixel_scale=list(raster.scale),
            nodata=comparison_nodata,
            scale=scale,
            offset=offset,
        )
        areas.append(
            {
                "code": code,
                "name": properties["adm4_name"],
                "geometry_sha256": geometry_hash,
                **statistics,
            }
        )
    # Reading must not alter originals or derive a report from changing inputs.
    if raster_hash != file_sha256(raster_path) or boundary_hash != file_sha256(boundary_path):
        raise ValueError("An input changed during sample processing; rerun on a stable copy.")
    if any(
        item["sha256"] != file_sha256(raster_path.parent / item["filename"])
        for item in dependencies
    ):
        raise ValueError("Raster sidecar metadata changed during processing.")
    report = {
        "schema": "floodsense.sample-elevation.v1",
        "generated_on": date.today().isoformat(),
        "method": "DESCRIPTIVE_CELL_CENTER_STATISTICS_ONLY",
        "raster": {
            "sha256": raster_hash,
            "filename": raster_path.name,
            "srid": raster.srid,
            "width": raster.width,
            "height": raster.height,
            "unit": "m",
            "unit_basis": unit_basis,
            "raw_band_unit": raw_unit,
            "sidecars": dependencies,
            "mask_flags": mask_flags,
            "vertical_datum": "UNVERIFIED",
            "origin": list(raster.origin),
            "pixel_scale": list(raster.scale),
            "coordinate_unit": raster.srs.units[1],
            "scale": scale,
            "offset": offset,
            "nodata": nodata if nodata is None or math.isfinite(nodata) else "NaN",
            "comparison_nodata": (
                comparison_nodata
                if comparison_nodata is None or math.isfinite(comparison_nodata)
                else "NaN"
            ),
            "valid_cell_count": len(valid),
            "valid_bounding_rectangle_percent": round(100 * len(valid) / len(values), 4),
            "minimum": round(min(valid), 4) if valid else None,
            "maximum": round(max(valid), 4) if valid else None,
        },
        "boundaries": {"sha256": boundary_hash, "filename": boundary_path.name},
        "areas": sorted(areas, key=lambda area: area["code"]),
        "limitations": LIMITATIONS,
    }
    report["version_sha256"] = report_version_sha256(report)
    return report
