"""Read-only, allowlisted geography for the staff review page.

Eligibility mirrors the reference-boundary and demonstration policies. This is
not a susceptibility service: AreaFact and Expert System tables are never read.
"""

import json

from django.db.models import Count, Q
from geography.constants import (
    BACOOR_REFERENCE_LIMITATION,
    BACOOR_REFERENCE_SOURCE_NAME,
    BACOOR_REFERENCE_WARNING,
)
from geography.models import GeographicArea
from provenance.models import DataSource, PublicationStatus
from provenance.policies import DEMONSTRATION_WARNING

VERSION_NOT_RECORDED = "Not recorded in the current data model"
ADMINISTRATIVE = "administrative"
DEMONSTRATION = "demonstration"


def _reviewable_areas():
    administrative = Q(
        area_type__in=(GeographicArea.AreaType.CITY, GeographicArea.AreaType.BARANGAY),
        status=PublicationStatus.PENDING_VALIDATION,
        source__name=BACOOR_REFERENCE_SOURCE_NAME,
        source__source_type=DataSource.SourceType.AGENCY_DATASET,
        source__status=PublicationStatus.PENDING_VALIDATION,
        source__is_publicly_releasable=True,
    )
    demonstration = Q(
        area_type=GeographicArea.AreaType.DEMO_ZONE,
        status=PublicationStatus.DEMONSTRATION,
        source__status=PublicationStatus.DEMONSTRATION,
        source__source_type=DataSource.SourceType.DEMONSTRATION,
    )
    # Disabled eligible rows remain reviewable; only enabled valid geometry is mapped.
    return GeographicArea.objects.filter(administrative | demonstration)


def _date(value):
    return value.isoformat() if value else "Not recorded"


def _record(area):
    source = area.source
    administrative = area.area_type != GeographicArea.AreaType.DEMO_ZONE
    layer = ADMINISTRATIVE if administrative else DEMONSTRATION
    geometry = area.geometry
    geometry_usable = bool(
        geometry and not geometry.empty and geometry.valid and geometry.srid == 4326
    )
    warnings = (
        [BACOOR_REFERENCE_WARNING, BACOOR_REFERENCE_LIMITATION]
        if administrative
        else [DEMONSTRATION_WARNING, "Synthetic areas only; not real Bacoor classifications."]
    )
    if not geometry_usable:
        warnings.append("Geometry is empty, invalid, or not WGS 84; it is not displayed.")
    if not area.is_enabled:
        warnings.append("This record is disabled and is not displayed on the map.")
    reviewer = source.reviewed_by
    fields = (
        ("code", "Geographic code", area.code),
        ("area_type", "Area type", area.get_area_type_display()),
        ("geometry_type", "Geometry type", geometry.geom_type if geometry else "Unavailable"),
        (
            "spatial_reference",
            "Spatial reference",
            f"EPSG:{geometry.srid}" if geometry else "Unknown",
        ),
        ("status", "Record status", area.get_status_display()),
        ("enabled", "Enabled state", "Enabled" if area.is_enabled else "Disabled"),
        ("source_name", "Source name", source.name),
        ("organization", "Source organization", source.organization or "Not recorded"),
        ("source_type", "Source type", source.get_source_type_display()),
        ("source_status", "Source validation status", source.get_status_display()),
        ("coverage", "Coverage", source.coverage_description or "Not recorded"),
        ("period_start", "Record period start", _date(source.record_period_start)),
        ("period_end", "Record period end", _date(source.record_period_end)),
        ("review_date", "Source review date", _date(source.reviewed_on)),
        (
            "reviewer",
            "Source reviewer",
            (reviewer.display_name.strip() or "Recorded reviewer (name unavailable)")
            if reviewer
            else "Not recorded",
        ),
        ("updated", "Record last updated (with UTC offset)", area.updated_at.isoformat()),
        (
            "public_release",
            "Source publicly releasable",
            "Yes — source permission only, not approval" if source.is_publicly_releasable else "No",
        ),
        ("version", "Governed geographic-data version", VERSION_NOT_RECORDED),
    )
    record = {
        "id": str(area.pk),
        "name": area.name,
        "code": area.code,
        "layer": layer,
        "layer_label": "Administrative reference" if administrative else "Demonstration only",
        "status": area.get_status_display(),
        "enabled": area.is_enabled,
        "mapped": area.is_enabled and geometry_usable,
        "details": [{"key": key, "label": label, "value": value} for key, label, value in fields],
        "warnings": warnings,
    }
    feature = None
    if record["mapped"]:
        feature = {
            "type": "Feature",
            "id": record["id"],
            "geometry": json.loads(geometry.geojson),
            "properties": {
                "record_id": record["id"],
                "name": area.name,
                "code": area.code,
                "area_type": area.area_type,
                "layer_kind": layer,
            },
        }
    return record, feature


def get_map_data(*, selected_id=None):
    """Two SELECTs regardless of record count; no private notes or rule fields.

    Counts deliberately cover only the two supported review categories. Generic
    approved geographic rows cannot establish an approved susceptibility layer.
    """
    areas = _reviewable_areas()
    counts = areas.aggregate(
        total=Count("pk"),
        enabled=Count("pk", filter=Q(is_enabled=True)),
        barangays=Count(
            "pk", filter=Q(is_enabled=True, area_type=GeographicArea.AreaType.BARANGAY)
        ),
        pending=Count("pk", filter=Q(status=PublicationStatus.PENDING_VALIDATION)),
        demonstration=Count("pk", filter=Q(area_type=GeographicArea.AreaType.DEMO_ZONE)),
        disabled=Count("pk", filter=Q(is_enabled=False)),
    )
    areas = areas.select_related("source", "source__reviewed_by").only(
        "id",
        "name",
        "code",
        "area_type",
        "geometry",
        "status",
        "is_enabled",
        "updated_at",
        "source__id",
        "source__name",
        "source__organization",
        "source__source_type",
        "source__status",
        "source__coverage_description",
        "source__record_period_start",
        "source__record_period_end",
        "source__reviewed_on",
        "source__is_publicly_releasable",
        "source__reviewed_by__id",
        "source__reviewed_by__display_name",
    )
    records = []
    layers = {
        key: {"type": "FeatureCollection", "features": []}
        for key in (ADMINISTRATIVE, DEMONSTRATION)
    }
    for area in areas:
        record, feature = _record(area)
        records.append(record)
        if feature:
            layers[record["layer"]]["features"].append(feature)
    records.sort(key=lambda row: (row["layer"], row["name"].casefold(), row["id"]))
    selected = next((row for row in records if row["id"] == selected_id), None)
    unavailable_selection = bool(selected_id and selected is None)
    if selected is None and records:
        selected = records[0]
    return {
        "counts": counts,
        "records": records,
        "selected": selected,
        "unavailable_selection": unavailable_selection,
        "administrative_mapped": len(layers[ADMINISTRATIVE]["features"]),
        "demonstration_mapped": len(layers[DEMONSTRATION]["features"]),
        "payload": {"records": records, "layers": layers},
    }
