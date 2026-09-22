"""Read-only validation for candidate evacuation-center and rainfall tables.

The validator deliberately has no model imports and performs no database or
filesystem writes. It reports technical readiness; it cannot approve, import,
activate, or publish a dataset.
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections import Counter
from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

UNKNOWN_METADATA = "unknown"
REPORT_VERSION = 1
MAX_DATASET_BYTES = 64 * 1024 * 1024
METADATA_CLASSIFICATIONS = {"UNSPECIFIED", "PUBLIC", "PROVISIONAL", "RESTRICTED"}

COMMON_METADATA_FIELDS = (
    "dataset_name",
    "custodian",
    "organization",
    "license",
    "usage_restrictions",
    "public_release_status",
    "geographic_coverage",
    "temporal_coverage",
    "version",
    "publication_date",
    "acquisition_date",
    "processing_notes",
    "known_limitations",
    "declared_validation_status",
)
KIND_METADATA_FIELDS = {
    "evacuation_centers": (
        "crs",
        "geometry_type",
        "coordinate_fields",
        "spatial_resolution",
    ),
    "rainfall_reference": (
        "units",
        "period_of_record",
        "time_resolution",
        "spatial_resolution",
        "missing_values",
    ),
    "generic": (),
}
REQUIRED_METADATA_FIELDS = {
    "evacuation_centers": (
        "dataset_name",
        "custodian",
        "license",
        "usage_restrictions",
        "public_release_status",
        "geographic_coverage",
        "version",
        "crs",
        "coordinate_fields",
        "known_limitations",
        "declared_validation_status",
    ),
    "rainfall_reference": (
        "dataset_name",
        "custodian",
        "license",
        "usage_restrictions",
        "public_release_status",
        "geographic_coverage",
        "temporal_coverage",
        "version",
        "units",
        "period_of_record",
        "time_resolution",
        "missing_values",
        "known_limitations",
        "declared_validation_status",
    ),
    "generic": (),
}


class TabularDatasetValidationError(ValueError):
    """Raised when a candidate table cannot be safely inspected."""


def validate_tabular_dataset(
    path: Path,
    *,
    dataset_kind: str,
    metadata: Mapping[str, Any] | None = None,
    metadata_classifications: Mapping[str, str] | None = None,
    required_fields: Iterable[str] = (),
    identity_fields: Iterable[str] = (),
    latitude_field: str | None = None,
    longitude_field: str | None = None,
    expected_row_count: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic report for an explicitly named CSV or TSV file."""

    if dataset_kind not in KIND_METADATA_FIELDS:
        raise TabularDatasetValidationError("Unsupported dataset kind.")
    candidate = path.resolve()
    if not candidate.is_file():
        raise TabularDatasetValidationError(f"Dataset file was not found: {candidate.name}")
    suffix = candidate.suffix.lower()
    if suffix not in {".csv", ".tsv"}:
        raise TabularDatasetValidationError(
            "Candidate table must use the .csv or .tsv file extension."
        )
    try:
        raw = candidate.read_bytes()
    except OSError as error:
        raise TabularDatasetValidationError(
            f"Dataset file could not be read: {candidate.name}."
        ) from error
    if len(raw) > MAX_DATASET_BYTES:
        raise TabularDatasetValidationError(
            f"Dataset exceeds the {MAX_DATASET_BYTES}-byte validation limit."
        )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise TabularDatasetValidationError("Dataset is not valid UTF-8 text.") from error

    delimiter = "\t" if suffix == ".tsv" else ","
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
        raw_headers = reader.fieldnames
        rows = list(reader)
    except csv.Error as error:
        raise TabularDatasetValidationError(
            f"Dataset is not valid delimited text: {error}."
        ) from error
    if not raw_headers:
        raise TabularDatasetValidationError("Dataset has no header row.")

    headers = [header.strip() if isinstance(header, str) else "" for header in raw_headers]
    normalized_required = tuple(dict.fromkeys(required_fields))
    normalized_identities = tuple(dict.fromkeys(identity_fields))
    missing_columns = sorted(
        {
            field
            for field in (
                *normalized_required,
                *normalized_identities,
                latitude_field,
                longitude_field,
            )
            if field and field not in headers
        }
    )
    blank_header_count = sum(not header for header in headers)
    duplicate_header_count = sum(
        count - 1 for value, count in Counter(headers).items() if value and count > 1
    )
    malformed_row_count = sum(
        None in row or any(value is None for value in row.values()) for row in rows
    )
    missing_value_counts = {
        field: sum(_is_missing(row.get(field)) for row in rows) for field in headers if field
    }
    identity_duplicate_counts = {
        field: _duplicate_distinct_count(
            row.get(field) for row in rows if not _is_missing(row.get(field))
        )
        for field in normalized_identities
        if field in headers
    }
    coordinate_quality = {
        "latitude": _coordinate_quality(rows, latitude_field, minimum=-90, maximum=90),
        "longitude": _coordinate_quality(rows, longitude_field, minimum=-180, maximum=180),
    }

    supplied_metadata = dict(metadata or {})
    supplied_classifications = dict(metadata_classifications or {})
    metadata_fields = tuple(
        dict.fromkeys((*COMMON_METADATA_FIELDS, *KIND_METADATA_FIELDS[dataset_kind]))
    )
    if any(
        not isinstance(value, str) or value not in METADATA_CLASSIFICATIONS
        for value in supplied_classifications.values()
    ):
        raise TabularDatasetValidationError(
            "Metadata classifications must be PUBLIC, PROVISIONAL, RESTRICTED, or UNSPECIFIED."
        )
    metadata_classification = {
        field: supplied_classifications.get(field, "UNSPECIFIED") for field in metadata_fields
    }
    original_metadata = {field: _known(supplied_metadata.get(field)) for field in metadata_fields}
    reported_metadata = {
        field: (
            "restricted"
            if metadata_classification[field] == "RESTRICTED"
            and original_metadata[field] != UNKNOWN_METADATA
            else original_metadata[field]
        )
        for field in metadata_fields
    }
    metadata_provenance = {
        field: (
            "MISSING"
            if original_metadata[field] == UNKNOWN_METADATA
            else "REDACTED_RESTRICTED"
            if metadata_classification[field] == "RESTRICTED"
            else "USER_SUPPLIED"
        )
        for field in metadata_fields
    }
    issues = _issues(
        rows=rows,
        expected_row_count=expected_row_count,
        missing_columns=missing_columns,
        required_fields=normalized_required,
        missing_value_counts=missing_value_counts,
        identity_duplicate_counts=identity_duplicate_counts,
        coordinate_quality=coordinate_quality,
        blank_header_count=blank_header_count,
        duplicate_header_count=duplicate_header_count,
        malformed_row_count=malformed_row_count,
        metadata=reported_metadata,
        required_metadata_fields=REQUIRED_METADATA_FIELDS[dataset_kind],
    )

    return {
        "report_version": REPORT_VERSION,
        "mode": "READ_ONLY_VALIDATION",
        "dataset_kind": dataset_kind,
        "file": {
            "name": candidate.name,
            "present": True,
            "format": "TSV" if suffix == ".tsv" else "CSV",
            "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest().upper(),
            "fact_provenance": {
                "name": "VERIFIED_BY_TOOL",
                "format": "VERIFIED_BY_TOOL",
                "size_bytes": "VERIFIED_BY_TOOL",
                "sha256": "VERIFIED_BY_TOOL",
            },
        },
        "metadata": reported_metadata,
        "metadata_provenance": metadata_provenance,
        "metadata_classification": metadata_classification,
        "inferred_metadata_fields": [],
        "structure": {
            "row_count": len(rows),
            "column_count": len(headers),
            "fields": headers,
            "blank_header_count": blank_header_count,
            "duplicate_header_count": duplicate_header_count,
            "malformed_row_count": malformed_row_count,
        },
        "quality": {
            "required_fields": list(normalized_required),
            "missing_columns": missing_columns,
            "missing_value_counts": missing_value_counts,
            "identity_fields": list(normalized_identities),
            "duplicate_identity_counts": identity_duplicate_counts,
            "coordinate_fields": {
                "latitude": latitude_field or UNKNOWN_METADATA,
                "longitude": longitude_field or UNKNOWN_METADATA,
            },
            "coordinate_quality": coordinate_quality,
        },
        "expectations": {
            "row_count": expected_row_count if expected_row_count is not None else UNKNOWN_METADATA,
        },
        "result": {
            "status": "PASS" if not issues else "ISSUES_FOUND",
            "issues": issues,
            "import_effect": "NONE",
            "approval_effect": "NONE",
            "activation_effect": "NONE",
            "limitations": [
                "Technical validation does not approve, import, activate, or publish this dataset.",
                "Unknown metadata remains unknown until an authorized source supplies it.",
                "The report contains counts and field names, not candidate record values.",
            ],
        },
    }


def _known(value: Any) -> Any:
    if value is None or value == "" or value == []:
        return UNKNOWN_METADATA
    return value


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _duplicate_distinct_count(values: Iterable[Any]) -> int:
    return sum(count > 1 for count in Counter(str(value) for value in values).values())


def _coordinate_quality(
    rows: list[dict[str | None, str | list[str] | None]],
    field: str | None,
    *,
    minimum: int,
    maximum: int,
) -> dict[str, int | str]:
    if not field:
        return {
            "field": UNKNOWN_METADATA,
            "missing_count": 0,
            "invalid_count": 0,
            "out_of_range_count": 0,
        }
    missing_count = invalid_count = out_of_range_count = 0
    for row in rows:
        value = row.get(field)
        if _is_missing(value):
            missing_count += 1
            continue
        try:
            number = Decimal(str(value).strip())
        except (InvalidOperation, AttributeError):
            invalid_count += 1
            continue
        if not number.is_finite():
            invalid_count += 1
        elif number < minimum or number > maximum:
            out_of_range_count += 1
    return {
        "field": field,
        "missing_count": missing_count,
        "invalid_count": invalid_count,
        "out_of_range_count": out_of_range_count,
    }


def _issues(
    *,
    rows: list[dict[str | None, str | list[str] | None]],
    expected_row_count: int | None,
    missing_columns: list[str],
    required_fields: tuple[str, ...],
    missing_value_counts: dict[str, int],
    identity_duplicate_counts: dict[str, int],
    coordinate_quality: dict[str, dict[str, int | str]],
    blank_header_count: int,
    duplicate_header_count: int,
    malformed_row_count: int,
    metadata: dict[str, Any],
    required_metadata_fields: tuple[str, ...],
) -> list[str]:
    issues = []
    if expected_row_count is not None and len(rows) != expected_row_count:
        issues.append(f"Expected {expected_row_count} rows but found {len(rows)}.")
    if missing_columns:
        issues.append(f"Missing {len(missing_columns)} expected columns.")
    if blank_header_count:
        issues.append(f"Found {blank_header_count} blank column names.")
    if duplicate_header_count:
        issues.append(f"Found {duplicate_header_count} duplicate column names.")
    if malformed_row_count:
        issues.append(f"Found {malformed_row_count} rows with a different column count.")
    for field in required_fields:
        count = missing_value_counts.get(field, 0)
        if count:
            issues.append(f"Required field {field!r} is missing in {count} rows.")
    for field, count in identity_duplicate_counts.items():
        if count:
            issues.append(f"Identity field {field!r} has {count} duplicated distinct values.")
    for coordinate, quality in coordinate_quality.items():
        for issue_type in ("missing_count", "invalid_count", "out_of_range_count"):
            count = quality[issue_type]
            if count:
                label = issue_type.removesuffix("_count").replace("_", " ")
                issues.append(f"{coordinate.title()} has {count} {label} values.")
    for field in required_metadata_fields:
        if metadata[field] == UNKNOWN_METADATA:
            issues.append(f"Required metadata field {field!r} is unknown.")
    return issues
