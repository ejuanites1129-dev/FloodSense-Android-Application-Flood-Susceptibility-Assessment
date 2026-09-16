"""Extract and validate a provisional MGB flood-susceptibility layer for Bacoor.

The source service times out when all large multipart geometries are requested
at once. This script queries matching object IDs, downloads each feature
separately, preserves the raw responses locally, repairs invalid source
geometry, and clips it to the repository's Bacoor city reference boundary.

Generated data stays under an ignored provisional directory. Running this
script does not import anything into PostgreSQL/PostGIS.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SERVER_DIRECTORY = REPOSITORY_ROOT / "server"
BOUNDARY_PATH = (
    REPOSITORY_ROOT
    / "research_data"
    / "administrative_boundaries"
    / "processed"
    / "bacoor_city_boundary.geojson"
)
BARANGAY_PATH = (
    REPOSITORY_ROOT
    / "research_data"
    / "administrative_boundaries"
    / "processed"
    / "bacoor_barangay_boundaries.geojson"
)
DATA_DIRECTORY = (
    REPOSITORY_ROOT
    / "research_data"
    / "provisional"
    / "mgb_flood_susceptibility"
)
RAW_DIRECTORY = DATA_DIRECTORY / "raw"
PROCESSED_DIRECTORY = DATA_DIRECTORY / "processed"
SOURCE_FEATURES_PATH = (
    PROCESSED_DIRECTORY / "bacoor_flood_susceptibility_source_features.geojson"
)
CLASSES_PATH = PROCESSED_DIRECTORY / "bacoor_flood_susceptibility_classes.geojson"
REPORT_PATH = PROCESSED_DIRECTORY / "validation_report.json"
BARANGAY_SUMMARY_PATH = PROCESSED_DIRECTORY / "barangay_susceptibility_area_summary.csv"

SERVICE_URL = (
    "https://controlmap.mgb.gov.ph/arcgis/rest/services/"
    "GeospatialDataInventory/GDI_Detailed_Flood_Susceptibility/FeatureServer/0"
)
QUERY_URL = f"{SERVICE_URL}/query"
CLASS_LABELS = {
    "LF": "Low",
    "MF": "Moderate",
    "HF": "High",
    "VHF": "Very High",
}
CLASS_ORDER = ("LF", "MF", "HF", "VHF")
OUTPUT_CRS = 4326
AREA_CRS = 32651
AREA_TOLERANCE_SQM = 0.01
PARTITION_TOLERANCE_SQM = 1.0
USER_AGENT = "FloodSense academic research prototype/1.0"

sys.path.insert(0, str(SERVER_DIRECTORY))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.contrib.gis.geos import (  # noqa: E402
    GeometryCollection,
    GEOSGeometry,
    MultiPolygon,
    Polygon,
)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Required file was not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temporary_path.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _request_url(parameters: dict[str, str]) -> str:
    return f"{QUERY_URL}?{urllib.parse.urlencode(parameters)}"


def _download_json(url: str, destination: Path, *, refresh: bool) -> dict[str, Any]:
    if destination.is_file() and not refresh:
        try:
            cached = _load_json(destination)
            if "error" not in cached:
                return cached
        except (OSError, json.JSONDecodeError):
            pass

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination.with_suffix(destination.suffix + ".part")
    last_error: Exception | None = None

    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=180) as response:  # noqa: S310
                with temporary_path.open("wb") as output:
                    shutil.copyfileobj(response, output, length=1024 * 1024)
            payload = _load_json(temporary_path)
            if "error" in payload:
                raise RuntimeError(f"ArcGIS error response: {payload['error']}")
            temporary_path.replace(destination)
            return payload
        except Exception as error:  # Network errors vary by Windows/Python build.
            last_error = error
            temporary_path.unlink(missing_ok=True)
            if attempt < 3:
                time.sleep(2**attempt)

    raise RuntimeError(f"Could not download {url}: {last_error}") from last_error


def _polygon_parts(geometry: GEOSGeometry) -> list[Polygon]:
    if geometry.empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    if geometry.geom_type in {"MultiPolygon", "GeometryCollection"}:
        parts: list[Polygon] = []
        for child in geometry:
            parts.extend(_polygon_parts(child))
        return parts
    return []


def _polygonal_geometry(geometry: GEOSGeometry) -> MultiPolygon | None:
    parts = _polygon_parts(geometry)
    if not parts:
        return None
    dissolved = GeometryCollection(*parts, srid=OUTPUT_CRS).unary_union
    if dissolved.geom_type == "Polygon":
        return MultiPolygon(dissolved, srid=OUTPUT_CRS)
    if dissolved.geom_type == "MultiPolygon":
        dissolved.srid = OUTPUT_CRS
        return dissolved
    repaired_parts = _polygon_parts(dissolved)
    if not repaired_parts:
        return None
    return MultiPolygon(*repaired_parts, srid=OUTPUT_CRS)


def _repair_polygonal(geometry: GEOSGeometry) -> tuple[MultiPolygon | None, bool]:
    geometry.srid = OUTPUT_CRS
    was_repaired = not geometry.valid
    if was_repaired:
        geometry = geometry.make_valid()
    polygonal = _polygonal_geometry(geometry)
    if polygonal is None:
        return None, was_repaired
    if not polygonal.valid:
        was_repaired = True
        polygonal = _polygonal_geometry(polygonal.make_valid())
    return polygonal, was_repaired


def _projected_area(geometry: GEOSGeometry) -> float:
    return geometry.transform(AREA_CRS, clone=True).area


def _feature(
    geometry: GEOSGeometry,
    properties: dict[str, Any],
    *,
    feature_id: str | int,
) -> dict[str, Any]:
    return {
        "type": "Feature",
        "id": feature_id,
        "properties": properties,
        "geometry": json.loads(geometry.geojson),
    }


def _city_geometry() -> MultiPolygon:
    collection = _load_json(BOUNDARY_PATH)
    features = collection.get("features", [])
    if len(features) != 1:
        raise ValueError(f"Expected one Bacoor city feature in {BOUNDARY_PATH}.")
    geometry = GEOSGeometry(json.dumps(features[0]["geometry"]), srid=OUTPUT_CRS)
    polygonal, _ = _repair_polygonal(geometry)
    if polygonal is None or not polygonal.valid:
        raise ValueError("The Bacoor city boundary is not valid polygonal geometry.")
    return polygonal


def _matching_object_ids(city: GEOSGeometry, *, refresh: bool) -> tuple[list[int], Path]:
    xmin, ymin, xmax, ymax = city.extent
    parameters = {
        "where": "1=1",
        "geometry": f"{xmin},{ymin},{xmax},{ymax}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": str(OUTPUT_CRS),
        "spatialRel": "esriSpatialRelIntersects",
        "returnIdsOnly": "true",
        "f": "json",
    }
    path = RAW_DIRECTORY / "matching_object_ids.json"
    payload = _download_json(_request_url(parameters), path, refresh=refresh)
    object_ids = sorted({int(value) for value in payload.get("objectIds", [])})
    if not object_ids:
        raise ValueError("The MGB service returned no object IDs for the Bacoor extent.")
    return object_ids, path


def _source_feature(object_id: int, *, refresh: bool) -> tuple[dict[str, Any], Path]:
    parameters = {
        "where": f"OBJECTID={object_id}",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": str(OUTPUT_CRS),
        "f": "geojson",
    }
    path = RAW_DIRECTORY / f"object_{object_id}.geojson"
    payload = _download_json(_request_url(parameters), path, refresh=refresh)
    features = payload.get("features", [])
    if len(features) != 1:
        raise ValueError(
            f"Expected one feature for OBJECTID={object_id}, found {len(features)}."
        )
    return features[0], path


def _union(geometries: list[GEOSGeometry]) -> MultiPolygon | None:
    if not geometries:
        return None
    return _polygonal_geometry(
        GeometryCollection(*geometries, srid=OUTPUT_CRS).unary_union
    )


def run(*, refresh: bool) -> dict[str, Any]:
    city = _city_geometry()
    city_area_sqm = _projected_area(city)
    object_ids, object_ids_path = _matching_object_ids(city, refresh=refresh)
    print(f"MGB features matching Bacoor extent: {len(object_ids)}")

    clipped_features: list[dict[str, Any]] = []
    clipped_by_class: dict[str, list[GEOSGeometry]] = defaultdict(list)
    source_ids_by_class: dict[str, list[int]] = defaultdict(list)
    raw_files: list[dict[str, Any]] = [
        {
            "path": str(object_ids_path.relative_to(REPOSITORY_ROOT)),
            "sha256": _sha256(object_ids_path),
            "bytes": object_ids_path.stat().st_size,
        }
    ]
    repaired_ids: list[int] = []
    outside_city_ids: list[int] = []

    for position, object_id in enumerate(object_ids, start=1):
        print(f"[{position}/{len(object_ids)}] Retrieving OBJECTID={object_id} ...")
        source_feature, raw_path = _source_feature(object_id, refresh=refresh)
        raw_files.append(
            {
                "path": str(raw_path.relative_to(REPOSITORY_ROOT)),
                "sha256": _sha256(raw_path),
                "bytes": raw_path.stat().st_size,
            }
        )
        properties = source_feature.get("properties") or {}
        class_code = str(properties.get("FloodSusc", "")).strip().upper()
        if class_code not in CLASS_LABELS:
            raise ValueError(
                f"OBJECTID={object_id} has unsupported FloodSusc={class_code!r}."
            )

        source_geometry = GEOSGeometry(
            json.dumps(source_feature["geometry"]), srid=OUTPUT_CRS
        )
        repaired_geometry, was_repaired = _repair_polygonal(source_geometry)
        if was_repaired:
            repaired_ids.append(object_id)
        if repaired_geometry is None:
            outside_city_ids.append(object_id)
            continue

        clipped = repaired_geometry.intersection(city)
        clipped, clipped_was_repaired = _repair_polygonal(clipped)
        if clipped_was_repaired and object_id not in repaired_ids:
            repaired_ids.append(object_id)
        if clipped is None or clipped.empty or _projected_area(clipped) <= AREA_TOLERANCE_SQM:
            outside_city_ids.append(object_id)
            continue

        source_ids_by_class[class_code].append(object_id)
        clipped_by_class[class_code].append(clipped)
        clipped_features.append(
            _feature(
                clipped,
                {
                    "source_object_id": object_id,
                    "class_code": class_code,
                    "class_label": CLASS_LABELS[class_code],
                    "clipped_area_sqm": round(_projected_area(clipped), 3),
                    "source_geometry_repaired": was_repaired or clipped_was_repaired,
                    "data_status": "PROVISIONAL_NOT_APPROVED",
                },
                feature_id=object_id,
            )
        )

    class_unions: dict[str, MultiPolygon] = {}
    for class_code in CLASS_ORDER:
        dissolved = _union(clipped_by_class[class_code])
        if dissolved is not None:
            class_unions[class_code] = dissolved

    conflict_parts: list[GEOSGeometry] = []
    overlap_pairs: list[dict[str, Any]] = []
    for left_index, left_code in enumerate(CLASS_ORDER):
        left = class_unions.get(left_code)
        if left is None:
            continue
        for right_code in CLASS_ORDER[left_index + 1 :]:
            right = class_unions.get(right_code)
            if right is None:
                continue
            intersection = left.intersection(right)
            polygonal, _ = _repair_polygonal(intersection)
            area_sqm = _projected_area(polygonal) if polygonal is not None else 0.0
            if polygonal is not None and area_sqm > AREA_TOLERANCE_SQM:
                conflict_parts.append(polygonal)
                overlap_pairs.append(
                    {
                        "classes": [left_code, right_code],
                        "area_sqm": round(area_sqm, 3),
                    }
                )

    conflict_union = _union(conflict_parts)
    all_classified_union = _union(list(class_unions.values()))
    if all_classified_union is None:
        raise ValueError("No exact MGB feature geometry intersected Bacoor City.")

    output_features: list[dict[str, Any]] = []
    output_geometries: dict[str, MultiPolygon] = {}
    class_metrics: dict[str, dict[str, Any]] = {}
    for class_code in CLASS_ORDER:
        geometry = class_unions.get(class_code)
        if geometry is None:
            continue
        if conflict_union is not None:
            geometry = _polygonal_geometry(geometry.difference(conflict_union))
        if geometry is None or geometry.empty:
            continue
        area_sqm = _projected_area(geometry)
        class_metrics[class_code] = {
            "label": CLASS_LABELS[class_code],
            "source_object_ids": sorted(source_ids_by_class[class_code]),
            "resolved_area_sqm": round(area_sqm, 3),
            "percent_of_city": round((area_sqm / city_area_sqm) * 100, 4),
        }
        output_geometries[class_code] = geometry
        output_features.append(
            _feature(
                geometry,
                {
                    "class_code": class_code,
                    "class_label": CLASS_LABELS[class_code],
                    "source_object_ids": sorted(source_ids_by_class[class_code]),
                    "classification_origin": "MGB FloodSusc",
                    "data_status": "PROVISIONAL_NOT_APPROVED",
                },
                feature_id=class_code,
            )
        )

    conflict_area_sqm = 0.0
    if conflict_union is not None:
        conflict_area_sqm = _projected_area(conflict_union)
        output_geometries["CONFLICT"] = conflict_union
        output_features.append(
            _feature(
                conflict_union,
                {
                    "class_code": "CONFLICT",
                    "class_label": "Conflicting source classifications",
                    "classification_origin": "Derived QA category, not an MGB class",
                    "data_status": "INSUFFICIENT_DATA_REQUIRES_REVIEW",
                },
                feature_id="CONFLICT",
            )
        )

    unmapped = _polygonal_geometry(city.difference(all_classified_union))
    unmapped_area_sqm = _projected_area(unmapped) if unmapped is not None else 0.0
    if unmapped is not None and unmapped_area_sqm > AREA_TOLERANCE_SQM:
        output_geometries["UNMAPPED"] = unmapped
        output_features.append(
            _feature(
                unmapped,
                {
                    "class_code": "UNMAPPED",
                    "class_label": "No mapped class / insufficient data",
                    "classification_origin": "Derived QA category, not an MGB class",
                    "data_status": "INSUFFICIENT_DATA_REQUIRES_REVIEW",
                },
                feature_id="UNMAPPED",
            )
        )

    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    common_metadata = {
        "status": "PROVISIONAL_NOT_APPROVED",
        "generated_at": generated_at,
        "crs": "EPSG:4326",
        "source": "DENR-MGB Detailed Flood Susceptibility FeatureServer/0",
        "source_url": SERVICE_URL,
        "boundary_source": str(BOUNDARY_PATH.relative_to(REPOSITORY_ROOT)),
        "warning": (
            "Not an official Bacoor City assessment. Source reuse terms and "
            "methodological metadata require verification."
        ),
    }
    _write_json(
        SOURCE_FEATURES_PATH,
        {
            "type": "FeatureCollection",
            "name": "bacoor_mgb_flood_susceptibility_source_features_provisional",
            "metadata": common_metadata,
            "features": clipped_features,
        },
    )
    _write_json(
        CLASSES_PATH,
        {
            "type": "FeatureCollection",
            "name": "bacoor_mgb_flood_susceptibility_classes_provisional",
            "metadata": common_metadata,
            "features": output_features,
        },
    )

    output_union = _union(list(output_geometries.values()))
    if output_union is None:
        raise ValueError("The resolved output partition is unexpectedly empty.")
    projected_outputs = [
        geometry.transform(AREA_CRS, clone=True) for geometry in output_geometries.values()
    ]
    output_partition_metrics = {
        "city_not_covered_sqm": _projected_area(city.difference(output_union)),
        "output_outside_city_sqm": _projected_area(output_union.difference(city)),
        "output_overlap_sqm": (
            sum(geometry.area for geometry in projected_outputs)
            - _projected_area(output_union)
        ),
    }
    if any(
        abs(value) > PARTITION_TOLERANCE_SQM
        for value in output_partition_metrics.values()
    ):
        raise ValueError(f"Resolved output partition validation failed: {output_partition_metrics}")

    barangay_collection = _load_json(BARANGAY_PATH)
    barangay_features = barangay_collection.get("features", [])
    if len(barangay_features) != 47:
        raise ValueError(f"Expected 47 current barangays, found {len(barangay_features)}.")
    summary_rows: list[dict[str, Any]] = []
    summary_percent_totals: list[float] = []
    summary_codes = [*CLASS_ORDER, "CONFLICT", "UNMAPPED"]
    for barangay_feature in barangay_features:
        barangay_geometry = GEOSGeometry(
            json.dumps(barangay_feature["geometry"]), srid=OUTPUT_CRS
        )
        barangay_geometry, _ = _repair_polygonal(barangay_geometry)
        if barangay_geometry is None:
            raise ValueError("A current Bacoor barangay has no polygonal geometry.")
        barangay_area_sqm = _projected_area(barangay_geometry)
        row: dict[str, Any] = {
            "psgc_10_digit": barangay_feature["properties"]["psgc_10_digit"],
            "barangay_name": barangay_feature["properties"]["adm4_name"],
            "barangay_area_sqm": round(barangay_area_sqm, 3),
        }
        total_percent = 0.0
        for code in summary_codes:
            geometry = output_geometries.get(code)
            intersection = (
                barangay_geometry.intersection(geometry) if geometry is not None else None
            )
            intersection, _ = (
                _repair_polygonal(intersection)
                if intersection is not None
                else (None, False)
            )
            area_sqm = _projected_area(intersection) if intersection is not None else 0.0
            percent = (area_sqm / barangay_area_sqm) * 100
            row[f"{code.lower()}_area_sqm"] = round(area_sqm, 3)
            row[f"{code.lower()}_percent"] = round(percent, 4)
            total_percent += percent
        row["partition_percent_total"] = round(total_percent, 4)
        summary_percent_totals.append(total_percent)
        summary_rows.append(row)

    summary_rows.sort(key=lambda row: row["barangay_name"])
    summary_fieldnames = ["psgc_10_digit", "barangay_name", "barangay_area_sqm"]
    for code in summary_codes:
        summary_fieldnames.extend([f"{code.lower()}_area_sqm", f"{code.lower()}_percent"])
    summary_fieldnames.append("partition_percent_total")
    _write_csv(BARANGAY_SUMMARY_PATH, summary_rows, summary_fieldnames)

    classified_area_sqm = _projected_area(all_classified_union)
    report = {
        **common_metadata,
        "matching_extent_object_ids": object_ids,
        "matching_extent_count": len(object_ids),
        "exact_city_intersection_object_ids": sorted(
            feature["properties"]["source_object_id"] for feature in clipped_features
        ),
        "exact_city_intersection_count": len(clipped_features),
        "outside_exact_city_object_ids": sorted(outside_city_ids),
        "source_geometry_repaired_object_ids": sorted(set(repaired_ids)),
        "source_object_ids_by_class": {
            code: sorted(source_ids_by_class[code]) for code in CLASS_ORDER
        },
        "city_area_sqm": round(city_area_sqm, 3),
        "classified_union_area_sqm": round(classified_area_sqm, 3),
        "classified_percent_of_city": round(
            (classified_area_sqm / city_area_sqm) * 100, 4
        ),
        "unmapped_area_sqm": round(unmapped_area_sqm, 3),
        "unmapped_percent_of_city": round((unmapped_area_sqm / city_area_sqm) * 100, 4),
        "cross_class_conflict_area_sqm": round(conflict_area_sqm, 3),
        "cross_class_conflict_percent_of_city": round(
            (conflict_area_sqm / city_area_sqm) * 100, 4
        ),
        "cross_class_overlap_pairs": overlap_pairs,
        "resolved_output_partition_metrics_sqm": {
            key: round(value, 6) for key, value in output_partition_metrics.items()
        },
        "resolved_class_metrics": class_metrics,
        "barangay_summary": {
            "feature_count": len(summary_rows),
            "path": str(BARANGAY_SUMMARY_PATH.relative_to(REPOSITORY_ROOT)),
            "minimum_partition_percent_total": round(min(summary_percent_totals), 6),
            "maximum_partition_percent_total": round(max(summary_percent_totals), 6),
            "warning": (
                "Percentages describe mapped area composition and do not assign one "
                "susceptibility class to an entire barangay."
            ),
        },
        "raw_files": raw_files,
        "processed_files": [
            str(SOURCE_FEATURES_PATH.relative_to(REPOSITORY_ROOT)),
            str(CLASSES_PATH.relative_to(REPOSITORY_ROOT)),
            str(BARANGAY_SUMMARY_PATH.relative_to(REPOSITORY_ROOT)),
        ],
        "review_required": [
            "Confirm permission, attribution, and redistribution conditions with MGB.",
            "Obtain the source map date/version, scale, methodology, CRS, and class definitions.",
            "Review all conflict and unmapped areas before any database import.",
            "Obtain adviser or subject-matter-expert approval for Expert System use.",
        ],
    }
    _write_json(REPORT_PATH, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Redownload every raw ArcGIS response instead of using the local cache.",
    )
    arguments = parser.parse_args()
    report = run(refresh=arguments.refresh)
    print(f"Created {SOURCE_FEATURES_PATH}")
    print(f"Created {CLASSES_PATH}")
    print(f"Created {BARANGAY_SUMMARY_PATH}")
    print(f"Created {REPORT_PATH}")
    print(
        "Coverage: "
        f"{report['classified_percent_of_city']:.4f}% classified, "
        f"{report['unmapped_percent_of_city']:.4f}% unmapped, "
        f"{report['cross_class_conflict_percent_of_city']:.4f}% conflicting."
    )
    print("Status: PROVISIONAL - NOT APPROVED FOR OPERATIONAL DATABASE USE")


if __name__ == "__main__":
    main()
