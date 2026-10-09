"""Inactive local storage for descriptive sample terrain summaries.

This is not an official terrain import or a susceptibility method. Every stored
fact is disabled and pending validation; no rule, baseline, geometry, publication
decision, or operating-mode policy is changed.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from django.conf import settings
from django.db import connections, transaction
from provenance.models import DataSource, PublicationStatus

from .constants import BACOOR_REFERENCE_BARANGAY_COUNT
from .models import AreaFact
from .services import eligible_bacoor_reference_barangays

SCHEMA = "floodsense.sample-elevation.v1"
SOURCE_PREFIX = "PROVISIONAL SAMPLE TERRAIN — "
_PRECISION = Decimal("0.0001")
_MAX_VALUE = Decimal("9999999999.9999")
_STAT_KEYS = {
    "minimum": ("sample_elevation_min", "m"),
    "mean": ("sample_elevation_mean", "m"),
    "maximum": ("sample_elevation_max", "m"),
    "valid_cell_count": ("sample_elevation_valid_cell_count", "count"),
    "cell_count": ("sample_elevation_cell_count", "count"),
    "coverage_percent": ("sample_elevation_coverage_percent", "%"),
}
_PERMITTED_USE = (
    "Local developer sample inspection only. Not approved for inference, resident "
    "outputs, research-method adoption, or redistribution."
)


class SampleElevationImportError(ValueError):
    """Raised before an unsafe sample can be written or an edited version reused."""


def geometry_sha256(geometry) -> str:
    """Fingerprint normalized geometry, including its coordinate reference system."""
    candidate = geometry.clone()
    candidate.normalize()
    return hashlib.sha256(bytes(candidate.ewkb)).hexdigest()


def report_version_sha256(report: dict[str, Any]) -> str:
    """Bind the immutable version to everything except generation date/version."""
    content = {
        key: value for key, value in report.items() if key not in {"generated_on", "version_sha256"}
    }
    return hashlib.sha256(_canonical_json(content).encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise SampleElevationImportError(
            "Report must contain finite portable JSON values."
        ) from error


def _local_target() -> None:
    database = connections["default"].settings_dict
    host = str(database.get("HOST", "")).strip().lower()
    try:
        loopback = host == "localhost" or ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        loopback = False
    if (
        not settings.DEBUG
        or not settings.GIS_ENABLED
        or not loopback
        or database.get("ENGINE") != "django.contrib.gis.db.backends.postgis"
    ):
        raise SampleElevationImportError(
            "Sample storage requires DEBUG, GIS, and an explicitly loopback local PostGIS target."
        )


def _hash(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value.lower())
    ):
        raise SampleElevationImportError(f"{field} must be a SHA-256 hexadecimal checksum.")
    return value.lower()


def _number(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise SampleElevationImportError(f"{field} must be a finite number.")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise SampleElevationImportError(f"{field} must be a finite number.") from error
    if not number.is_finite() or abs(number) > _MAX_VALUE:
        raise SampleElevationImportError(f"{field} is non-finite or exceeds local fact precision.")
    return number


def _count(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise SampleElevationImportError(f"{field} must be a nonnegative integer.")
    _number(value, field)
    return value


def _no_absolute_paths(value: Any) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _no_absolute_paths(item)
    elif isinstance(value, list):
        for item in value:
            _no_absolute_paths(item)
    elif isinstance(value, str) and (
        PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute()
    ):
        raise SampleElevationImportError("Report provenance must not contain absolute local paths.")


def _validate_report(report: dict[str, Any]) -> tuple[str, date, dict[str, dict]]:
    if not isinstance(report, dict) or report.get("schema") != SCHEMA:
        raise SampleElevationImportError(f"Expected report schema {SCHEMA}.")
    _no_absolute_paths(report)
    version = _hash(report.get("version_sha256"), "version_sha256")
    if report["version_sha256"] != version:
        raise SampleElevationImportError("Version checksum must use lowercase hexadecimal.")
    if report_version_sha256(report) != version:
        raise SampleElevationImportError("The sample report does not match its version checksum.")
    try:
        generated_on = date.fromisoformat(report["generated_on"])
    except (KeyError, TypeError, ValueError) as error:
        raise SampleElevationImportError("generated_on must be an ISO calendar date.") from error
    if report["generated_on"] != generated_on.isoformat():
        raise SampleElevationImportError("generated_on must use YYYY-MM-DD.")
    raster = report.get("raster")
    boundaries = report.get("boundaries")
    if not isinstance(raster, dict) or not isinstance(boundaries, dict):
        raise SampleElevationImportError("Raster and boundary provenance are required.")
    for name, metadata in (("raster", raster), ("boundaries", boundaries)):
        _hash(metadata.get("sha256"), f"{name}.sha256")
        filename = metadata.get("filename")
        if (
            not isinstance(filename, str)
            or not filename.strip()
            or filename != (PureWindowsPath(filename).name)
            or filename != PurePosixPath(filename).name
        ):
            raise SampleElevationImportError(f"{name}.filename must be a basename only.")
    if (
        raster.get("unit") != "m"
        or not isinstance(raster.get("unit_basis"), str)
        or not (raster["unit_basis"].strip())
        or raster.get("vertical_datum") != "UNVERIFIED"
    ):
        raise SampleElevationImportError(
            "Only explicitly based metre samples with UNVERIFIED vertical datum may be stored."
        )
    for key in ("srid", "width", "height"):
        if _count(raster.get(key), f"raster.{key}") == 0:
            raise SampleElevationImportError(f"raster.{key} must be positive.")
    for key in ("pixel_scale", "origin"):
        values = raster.get(key)
        if not isinstance(values, list) or len(values) != 2:
            raise SampleElevationImportError(f"raster.{key} requires two numeric values.")
        for item in values:
            if _number(item, f"raster.{key}") == 0 and key == "pixel_scale":
                raise SampleElevationImportError("Raster pixel scales must be nonzero.")
    if _number(raster.get("scale"), "raster.scale") == 0:
        raise SampleElevationImportError("Raster value scale must be nonzero.")
    _number(raster.get("offset"), "raster.offset")
    if "nodata" not in raster:
        raise SampleElevationImportError(
            "Raster NoData metadata must be recorded, including unknowns."
        )
    limitations = report.get("limitations")
    if (
        not isinstance(limitations, list)
        or not limitations
        or any(not isinstance(item, str) or not item.strip() for item in limitations)
    ):
        raise SampleElevationImportError("Explicit sample limitations are required.")
    rows = report.get("areas")
    if not isinstance(rows, list) or len(rows) != BACOOR_REFERENCE_BARANGAY_COUNT:
        raise SampleElevationImportError(
            "The sample summary must contain all 47 current barangays."
        )
    by_code: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("code"), str) or not row["code"]:
            raise SampleElevationImportError("Every sample area needs a controlled code.")
        if row["code"] in by_code:
            raise SampleElevationImportError("Duplicate sample barangay codes are not permitted.")
        _hash(row.get("geometry_sha256"), "area.geometry_sha256")
        total = _count(row.get("cell_count"), "area.cell_count")
        valid = _count(row.get("valid_cell_count"), "area.valid_cell_count")
        if valid > total or valid > raster["width"] * raster["height"] or total > 2_000_000:
            raise SampleElevationImportError(
                "Sample valid cells exceed raster dimensions or polygon grid is unbounded."
            )
        coverage = _number(row.get("coverage_percent"), "area.coverage_percent")
        expected = Decimal(valid) * 100 / Decimal(total) if total else Decimal(0)
        if not 0 <= coverage <= 100 or abs(coverage - expected) > _PRECISION:
            raise SampleElevationImportError(
                "Sample coverage does not agree with valid/total cell counts."
            )
        if valid:
            stats = [_number(row.get(key), f"area.{key}") for key in ("minimum", "mean", "maximum")]
            if not stats[0] <= stats[1] <= stats[2]:
                raise SampleElevationImportError(
                    "Sample statistics must satisfy minimum <= mean <= maximum."
                )
        elif any(row.get(key) is not None for key in ("minimum", "mean", "maximum")):
            raise SampleElevationImportError(
                "No-valid-cell areas must have null terrain statistics."
            )
        by_code[row["code"]] = row
    return version, generated_on, by_code


def _source_values(report: dict, generated_on: date) -> dict[str, Any]:
    return {
        "name": SOURCE_PREFIX + report["version_sha256"][:16],
        "organization": "FloodSense research team; original sample provider unverified",
        "custodian": "Local research development",
        "source_type": DataSource.SourceType.OTHER,
        "coverage_description": (
            "Descriptive raster-cell sample summaries for 47 current Bacoor barangays."
        ),
        "record_period_start": None,
        "record_period_end": None,
        "received_or_created_on": generated_on,
        "version": report["version_sha256"],
        "permitted_use": _PERMITTED_USE,
        "processing_notes": _canonical_json(report),
        "limitations": "\n".join(report["limitations"]),
        "citation_url": "",
        "status": PublicationStatus.PENDING_VALIDATION,
        "reviewed_by_id": None,
        "reviewed_on": None,
        "is_publicly_releasable": False,
        "notes": "Descriptive sample only. Disabled facts; no inference or scientific approval.",
    }


def persist_sample_summary(report: dict[str, Any]) -> dict[str, Any]:
    """Store an explicitly authorized local report as inactive, immutable facts."""
    _local_target()
    version, generated_on, rows = _validate_report(report)
    with transaction.atomic():
        # Lock the same stable boundary rows before resolving the reserved source
        # identity, serializing cooperating imports without a new model/table.
        areas = list(
            eligible_bacoor_reference_barangays().select_for_update(of=("self",)).order_by("code")
        )
        if len(areas) != BACOOR_REFERENCE_BARANGAY_COUNT or {area.code for area in areas} != set(
            rows
        ):
            raise SampleElevationImportError(
                "Current enabled eligible Bacoor boundaries do not match the report."
            )
        expected_facts = {}
        for area in areas:
            row = rows[area.code]
            if row.get("name") != area.name or geometry_sha256(area.geometry) != (
                row["geometry_sha256"].lower()
            ):
                raise SampleElevationImportError(
                    "A sample barangay name or geometry differs from current boundaries."
                )
            for field, (key, unit) in _STAT_KEYS.items():
                if field in {"minimum", "mean", "maximum"} and not row["valid_cell_count"]:
                    continue
                expected_facts[(area.id, key)] = (
                    _number(row[field], f"area.{field}").quantize(_PRECISION),
                    unit,
                )

        source_name = SOURCE_PREFIX + version[:16]
        sources = list(DataSource.objects.select_for_update().filter(name=source_name))
        if len(sources) > 1:
            raise SampleElevationImportError("The reserved sample source identity is ambiguous.")
        created = not sources
        if created:
            source = DataSource(**_source_values(report, generated_on))
            source.full_clean()
            source.save()
        else:
            source = sources[0]
            try:
                original_report = json.loads(source.processing_notes)
                original_version, original_date, _ = _validate_report(original_report)
            except (TypeError, ValueError) as error:
                raise SampleElevationImportError(
                    "The existing sample source provenance was edited."
                ) from error
            if original_version != version:
                raise SampleElevationImportError(
                    "The reserved sample source is owned by different content."
                )
            for field, expected in _source_values(original_report, original_date).items():
                if getattr(source, field) != expected:
                    raise SampleElevationImportError(
                        f"The existing sample source {field} was edited; refusing overwrite."
                    )

        for relationship in DataSource._meta.related_objects:
            if relationship.related_model is AreaFact:
                continue
            if relationship.related_model._default_manager.filter(
                **{relationship.field.name: source}
            ).exists():
                raise SampleElevationImportError(
                    "The reserved sample source owns unexpected non-terrain records."
                )

        existing = list(AreaFact.objects.select_for_update().filter(source=source))
        if not created:
            actual = {(fact.area_id, fact.fact_key): fact for fact in existing}
            if len(actual) != len(existing) or set(actual) != set(expected_facts):
                raise SampleElevationImportError(
                    "The existing sample fact identities were edited or are incomplete."
                )
            for identity, (number, unit) in expected_facts.items():
                fact = actual[identity]
                if (
                    fact.numeric_value != number
                    or fact.unit != unit
                    or fact.text_value
                    or (
                        fact.status != PublicationStatus.PENDING_VALIDATION
                        or fact.is_enabled
                        or fact.effective_on is not None
                    )
                ):
                    raise SampleElevationImportError(
                        "An existing sample fact was edited; refusing overwrite."
                    )
        else:
            for (area_id, key), (number, unit) in expected_facts.items():
                fact = AreaFact(
                    area_id=area_id,
                    fact_key=key,
                    numeric_value=number,
                    unit=unit,
                    source=source,
                    status=PublicationStatus.PENDING_VALIDATION,
                    is_enabled=False,
                )
                fact.full_clean()
                fact.save()
        return {
            "source_id": source.id,
            "created": created,
            "fact_count": len(expected_facts),
            "version_sha256": version,
        }
