"""Read-only validation for candidate GeoJSON datasets.

This module reports technical properties only. It never imports, approves, or
publishes a dataset and does not infer missing source metadata.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from django.contrib.gis.geos import GEOSException, GEOSGeometry

UNKNOWN_METADATA = "unknown"
REPORT_VERSION = 1
_METADATA_FIELDS = (
    "source",
    "custodian",
    "license",
    "crs",
    "geographic_coverage",
    "version",
    "acquisition_date",
    "publication_date",
    "unit",
    "spatial_resolution",
    "processing_notes",
    "limitations",
    "validation_status",
)


class DatasetValidationError(ValueError):
    """Raised when a candidate file cannot be safely inspected."""


def validate_geojson_dataset(
    path: Path,
    *,
    identity_fields: Iterable[str] = (),
    expected_geometry_types: Iterable[str] = (),
    expected_feature_count: int | None = None,
    expected_crs: str | None = None,
) -> dict[str, Any]:
    """Return a deterministic read-only validation report for one GeoJSON file."""

    candidate = path.resolve()
    if not candidate.is_file():
        raise DatasetValidationError(f"Dataset file was not found: {candidate}")
    try:
        raw = candidate.read_bytes()
    except OSError as error:
        raise DatasetValidationError(f"Dataset file could not be read: {error}") from error
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DatasetValidationError(f"Dataset is not valid UTF-8 JSON: {error}") from error
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise DatasetValidationError("Expected a GeoJSON FeatureCollection.")
    features = payload.get("features")
    if not isinstance(features, list):
        raise DatasetValidationError("GeoJSON features must be a list.")

    normalized_identity_fields = tuple(dict.fromkeys(identity_fields))
    normalized_geometry_types = tuple(dict.fromkeys(expected_geometry_types))
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    geometry_types: Counter[str] = Counter()
    missing_identity_counts = dict.fromkeys(normalized_identity_fields, 0)
    identity_values = {field: [] for field in normalized_identity_fields}
    null_geometry_count = 0
    empty_geometry_count = 0
    invalid_geometry_count = 0
    property_rows: list[dict[str, Any]] = []

    for feature in features:
        if not isinstance(feature, dict):
            invalid_geometry_count += 1
            property_rows.append({})
            for field in normalized_identity_fields:
                missing_identity_counts[field] += 1
            continue
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            properties = {}
        property_rows.append(properties)
        for field in normalized_identity_fields:
            value = properties.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing_identity_counts[field] += 1
            else:
                identity_values[field].append(str(value))

        geometry_payload = feature.get("geometry")
        if geometry_payload is None:
            null_geometry_count += 1
            continue
        if not isinstance(geometry_payload, dict):
            invalid_geometry_count += 1
            continue
        geometry_type = geometry_payload.get("type")
        geometry_types[str(geometry_type or UNKNOWN_METADATA)] += 1
        try:
            geometry = GEOSGeometry(json.dumps(geometry_payload), srid=4326)
        except (GEOSException, TypeError, ValueError):
            invalid_geometry_count += 1
            continue
        if geometry.empty:
            empty_geometry_count += 1
        elif not geometry.valid:
            invalid_geometry_count += 1

    duplicate_identity_values = {
        field: sorted(value for value, count in Counter(values).items() if count > 1)
        for field, values in identity_values.items()
    }
    property_fields = sorted({field for properties in property_rows for field in properties})
    missing_property_counts = {
        field: sum(
            1
            for properties in property_rows
            if properties.get(field) is None
            or (isinstance(properties.get(field), str) and not properties[field].strip())
        )
        for field in property_fields
    }
    declared_crs = _declared_crs(payload, metadata)
    issues = _issues(
        feature_count=len(features),
        geometry_types=set(geometry_types),
        missing_identity_counts=missing_identity_counts,
        duplicate_identity_values=duplicate_identity_values,
        null_geometry_count=null_geometry_count,
        empty_geometry_count=empty_geometry_count,
        invalid_geometry_count=invalid_geometry_count,
        expected_feature_count=expected_feature_count,
        expected_geometry_types=set(normalized_geometry_types),
        declared_crs=declared_crs,
        expected_crs=expected_crs,
    )

    return {
        "report_version": REPORT_VERSION,
        "mode": "READ_ONLY_VALIDATION",
        "file": {
            "name": candidate.name,
            "present": True,
            "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest().upper(),
        },
        "metadata": {
            "dataset_name": _known(payload.get("name")),
            **{
                field: _known(declared_crs if field == "crs" else metadata.get(field))
                for field in _METADATA_FIELDS
            },
        },
        "structure": {
            "format": "GeoJSON FeatureCollection",
            "feature_count": len(features),
            "geometry_types": dict(sorted(geometry_types.items())),
            "bbox": payload.get("bbox")
            if isinstance(payload.get("bbox"), list)
            else UNKNOWN_METADATA,
        },
        "quality": {
            "identity_fields": list(normalized_identity_fields),
            "missing_identity_counts": missing_identity_counts,
            "duplicate_identity_values": duplicate_identity_values,
            "property_fields": property_fields,
            "missing_property_counts": missing_property_counts,
            "null_geometry_count": null_geometry_count,
            "empty_geometry_count": empty_geometry_count,
            "invalid_geometry_count": invalid_geometry_count,
        },
        "expectations": {
            "feature_count": expected_feature_count
            if expected_feature_count is not None
            else UNKNOWN_METADATA,
            "geometry_types": list(normalized_geometry_types)
            if normalized_geometry_types
            else UNKNOWN_METADATA,
            "crs": _known(expected_crs),
        },
        "result": {
            "status": "PASS" if not issues else "ISSUES_FOUND",
            "issues": issues,
            "approval_effect": "NONE",
            "limitations": [
                "Technical validation does not approve, import, activate, or publish this dataset.",
                "Unknown metadata remains unknown until an authorized source supplies it.",
            ],
        },
    }


def _known(value: Any) -> Any:
    if value is None or value == "" or value == []:
        return UNKNOWN_METADATA
    return value


def _declared_crs(payload: dict[str, Any], metadata: dict[str, Any]) -> str | None:
    value = metadata.get("crs")
    if isinstance(value, str) and value.strip():
        return value.strip()
    crs = payload.get("crs")
    if isinstance(crs, dict):
        properties = crs.get("properties")
        if isinstance(properties, dict):
            name = properties.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
    return None


def _issues(
    *,
    feature_count: int,
    geometry_types: set[str],
    missing_identity_counts: dict[str, int],
    duplicate_identity_values: dict[str, list[str]],
    null_geometry_count: int,
    empty_geometry_count: int,
    invalid_geometry_count: int,
    expected_feature_count: int | None,
    expected_geometry_types: set[str],
    declared_crs: str | None,
    expected_crs: str | None,
) -> list[str]:
    issues = []
    if expected_feature_count is not None and feature_count != expected_feature_count:
        issues.append(f"Expected {expected_feature_count} features but found {feature_count}.")
    unexpected_geometry_types = geometry_types - expected_geometry_types
    if expected_geometry_types and unexpected_geometry_types:
        issues.append(
            "Unexpected geometry types: " + ", ".join(sorted(unexpected_geometry_types)) + "."
        )
    for field, count in missing_identity_counts.items():
        if count:
            issues.append(f"Identity field {field!r} is missing in {count} features.")
    for field, values in duplicate_identity_values.items():
        if values:
            issues.append(f"Identity field {field!r} has {len(values)} duplicate values.")
    if null_geometry_count:
        issues.append(f"Found {null_geometry_count} null geometries.")
    if empty_geometry_count:
        issues.append(f"Found {empty_geometry_count} empty geometries.")
    if invalid_geometry_count:
        issues.append(f"Found {invalid_geometry_count} invalid geometries.")
    if expected_crs is not None and declared_crs != expected_crs:
        issues.append(
            f"Expected declared CRS {expected_crs!r} but found "
            f"{declared_crs or UNKNOWN_METADATA!r}."
        )
    return issues
