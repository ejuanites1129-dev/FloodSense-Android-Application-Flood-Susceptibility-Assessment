"""Build the current 47-barangay Bacoor reference layer from legacy polygons."""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SERVER_DIRECTORY = REPOSITORY_ROOT / "server"
DATA_DIRECTORY = REPOSITORY_ROOT / "research_data" / "administrative_boundaries"
PROCESSED_DIRECTORY = DATA_DIRECTORY / "processed"
LEGACY_PATH = PROCESSED_DIRECTORY / "bacoor_barangay_boundaries_legacy_73.geojson"
CITY_PATH = PROCESSED_DIRECTORY / "bacoor_city_boundary.geojson"
MAPPING_PATH = DATA_DIRECTORY / "bacoor_barangay_mapping_2023.json"
OUTPUT_PATH = PROCESSED_DIRECTORY / "bacoor_barangay_boundaries.geojson"

sys.path.insert(0, str(SERVER_DIRECTORY))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.contrib.gis.geos import (  # noqa: E402
    GeometryCollection,
    GEOSGeometry,
    MultiPolygon,
)


def _load_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Required file was not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _as_multipolygon(geometry: GEOSGeometry) -> MultiPolygon:
    if geometry.geom_type == "Polygon":
        return MultiPolygon(geometry.clone(), srid=4326)
    if geometry.geom_type == "MultiPolygon":
        geometry.srid = 4326
        return geometry
    raise ValueError(f"Expected Polygon or MultiPolygon, got {geometry.geom_type}.")


def _validate_mapping(source_by_name: dict[str, dict], mapping: dict) -> None:
    records = mapping["barangays"]
    if len(records) != 47:
        raise ValueError(f"Expected 47 current barangays, found {len(records)}.")

    current_names = [record["current_name"] for record in records]
    current_codes = [record["psgc_10_digit"] for record in records]
    source_names = [name for record in records for name in record["source_names"]]

    duplicate_current_names = [name for name, count in Counter(current_names).items() if count > 1]
    duplicate_current_codes = [code for code, count in Counter(current_codes).items() if count > 1]
    duplicate_source_names = [name for name, count in Counter(source_names).items() if count > 1]
    unknown_source_names = sorted(set(source_names) - set(source_by_name))
    unused_source_names = sorted(set(source_by_name) - set(source_names))

    problems = {
        "duplicate current names": duplicate_current_names,
        "duplicate current codes": duplicate_current_codes,
        "duplicate source names": duplicate_source_names,
        "unknown source names": unknown_source_names,
        "unused source names": unused_source_names,
    }
    failures = {name: values for name, values in problems.items() if values}
    if failures:
        raise ValueError(f"Invalid Bacoor mapping: {failures}")

    if len(source_names) != 73:
        raise ValueError(f"Expected all 73 legacy units, found {len(source_names)}.")

    expected_codes = {f"0402103{number:03d}" for number in range(76, 94)}
    merged_codes = {
        record["psgc_10_digit"] for record in records if record["change_type"] == "merged"
    }
    if merged_codes != expected_codes:
        raise ValueError("The 18 merged-barangay PSGC codes are incomplete or incorrect.")


def main() -> None:
    legacy = _load_json(LEGACY_PATH)
    city = _load_json(CITY_PATH)
    mapping = _load_json(MAPPING_PATH)

    source_by_name = {feature["properties"]["adm4_name"]: feature for feature in legacy["features"]}
    if len(source_by_name) != 73:
        raise ValueError(f"Expected 73 unique legacy features, found {len(source_by_name)}.")

    _validate_mapping(source_by_name, mapping)

    output_features: list[dict] = []
    output_geometries: list[MultiPolygon] = []

    for record in mapping["barangays"]:
        source_features = [source_by_name[name] for name in record["source_names"]]
        source_geometries = [
            GEOSGeometry(json.dumps(feature["geometry"]), srid=4326) for feature in source_features
        ]
        merged = GeometryCollection(*source_geometries, srid=4326).unary_union
        merged = _as_multipolygon(merged)
        if not merged.valid:
            raise ValueError(f"Derived geometry is invalid: {record['current_name']}")

        representative_point = merged.point_on_surface
        source_properties = source_features[0]["properties"]
        source_pcodes = [feature["properties"]["adm4_pcode"] for feature in source_features]
        area_sqkm = sum(float(feature["properties"]["area_sqkm"]) for feature in source_features)

        properties = {
            "adm4_name": record["current_name"],
            "adm4_ref_name": record["current_name"],
            "adm4_pcode": f"PH{record['psgc_10_digit']}",
            "psgc_10_digit": record["psgc_10_digit"],
            "adm3_name": "Bacoor City",
            "adm3_pcode": mapping["parent_pcode"],
            "adm2_name": source_properties["adm2_name"],
            "adm2_pcode": source_properties["adm2_pcode"],
            "adm1_name": source_properties["adm1_name"],
            "adm1_pcode": source_properties["adm1_pcode"],
            "adm0_name": source_properties["adm0_name"],
            "adm0_pcode": source_properties["adm0_pcode"],
            "area_sqkm": round(area_sqkm, 8),
            "center_lat": round(representative_point.y, 8),
            "center_lon": round(representative_point.x, 8),
            "change_type": record["change_type"],
            "source_adm4_names": record["source_names"],
            "source_adm4_pcodes": source_pcodes,
            "administrative_change_ratified_on": mapping["ratified_on"],
            "geometry_source_valid_on": source_properties["valid_on"],
            "geometry_source_version": source_properties["version"],
            "derived_on": "2026-09-16",
            "data_status": "DERIVED_REFERENCE_NOT_CITY_VERIFIED",
        }
        output_features.append(
            {
                "type": "Feature",
                "id": properties["adm4_pcode"],
                "properties": properties,
                "geometry": json.loads(merged.geojson),
            }
        )
        output_geometries.append(merged)

    city_geometry = GEOSGeometry(json.dumps(city["features"][0]["geometry"]), srid=4326).transform(
        32651, clone=True
    )
    projected_geometries = [geometry.transform(32651, clone=True) for geometry in output_geometries]
    barangay_union = GeometryCollection(*projected_geometries, srid=32651).unary_union

    coverage_metrics = {
        "city_not_covered_sqm": city_geometry.difference(barangay_union).area,
        "barangays_outside_city_sqm": barangay_union.difference(city_geometry).area,
        "barangay_overlap_sqm": (
            sum(geometry.area for geometry in projected_geometries) - barangay_union.area
        ),
    }
    if any(abs(value) > 0.01 for value in coverage_metrics.values()):
        raise ValueError(f"Derived coverage validation failed: {coverage_metrics}")

    xmin = min(geometry.extent[0] for geometry in output_geometries)
    ymin = min(geometry.extent[1] for geometry in output_geometries)
    xmax = max(geometry.extent[2] for geometry in output_geometries)
    ymax = max(geometry.extent[3] for geometry in output_geometries)

    output = {
        "type": "FeatureCollection",
        "name": "bacoor_barangay_boundaries_47_derived",
        "bbox": [xmin, ymin, xmax, ymax],
        "metadata": {
            "status": "DERIVED_REFERENCE_NOT_CITY_VERIFIED",
            "feature_count": 47,
            "crs": "EPSG:4326",
            "ordinance": mapping["ordinance"],
            "ratified_on": mapping["ratified_on"],
            "psa_reference": mapping["psa_reference"],
            "current_psgc_reference": mapping["current_psgc_reference"],
            "derivation": (
                "Legacy polygons were dissolved according to the PSA-recorded "
                "Bacoor merger mapping; unchanged and renamed polygons retain "
                "their source coordinates."
            ),
        },
        "features": output_features,
    }

    PROCESSED_DIRECTORY.mkdir(parents=True, exist_ok=True)
    temporary_path = OUTPUT_PATH.with_suffix(".geojson.tmp")
    temporary_path.write_text(
        json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(OUTPUT_PATH)

    change_counts = Counter(record["change_type"] for record in mapping["barangays"])
    print(f"Created {OUTPUT_PATH}")
    print(f"Features: {len(output_features)}; changes: {dict(change_counts)}")
    print(
        "Coverage (square metres): "
        + ", ".join(f"{key}={value:.6f}" for key, value in coverage_metrics.items())
    )
    print("Status: DERIVED REFERENCE - NOT CITY-VERIFIED")


if __name__ == "__main__":
    main()
