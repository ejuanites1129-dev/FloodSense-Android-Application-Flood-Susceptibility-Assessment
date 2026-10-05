"""Copy an allowlisted team snapshot into an explicitly opted-in local database."""

import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import UUID

from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Point
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from evacuation.models import EvacuationCenter
from evacuation.workflow import log_center_action, transition_center
from geography.constants import (
    BACOOR_CITY_CODE,
    BACOOR_REFERENCE_SOURCE_NAME,
    BACOOR_REFERENCE_SOURCE_VERSION,
)
from geography.models import GeographicArea
from provenance.models import DataSource, PublicationStatus
from provenance.workflow import log_source_action, transition_source

from core.local_testing import local_testing_enabled

PACKAGE_PATH = (
    Path(settings.BASE_DIR).parent / "research_data/provisional/team_local_setup/records.json"
)
SOURCE_FIELDS = {
    "name",
    "organization",
    "custodian",
    "source_type",
    "coverage_description",
    "record_period_start",
    "record_period_end",
    "received_or_created_on",
    "version",
    "permitted_use",
    "processing_notes",
    "limitations",
    "citation_url",
    "status",
    "is_publicly_releasable",
    "notes",
}
AREA_FIELDS = {"code", "name", "area_type", "status", "is_enabled"}
CENTER_FIELDS = {
    "public_id",
    "name",
    "address",
    "latitude",
    "longitude",
    "notes",
    "limitations",
    "area_code",
    "approved_for_local_testing",
}
BOUNDARY_FILES = {"bacoor_city_boundary.geojson": 1, "bacoor_barangay_boundaries.geojson": 47}


def source_values(source):
    return {
        field: value.isoformat() if isinstance(value := getattr(source, field), date) else value
        for field in SOURCE_FIELDS
    }


def original_boundary_source_values():
    """Only an untouched, freshly imported pending source may be upgraded to the snapshot."""
    source = DataSource(
        name=BACOOR_REFERENCE_SOURCE_NAME,
        organization="OCHA HDX; source agencies NAMRIA and PSA",
        source_type=DataSource.SourceType.AGENCY_DATASET,
        version=BACOOR_REFERENCE_SOURCE_VERSION,
        coverage_description=(
            "Bacoor City and its 47 current barangays. Geometry was derived from "
            "COD-AB legacy polygons using the PSA 2023 barangay-merger mapping."
        ),
        record_period_start=date(2023, 7, 29),
        received_or_created_on=date(2026, 9, 16),
        permitted_use=(
            "Academic prototype administrative reference with source attribution; "
            "review licensing and attribution before thesis release or deployment."
        ),
        status=PublicationStatus.PENDING_VALIDATION,
        is_publicly_releasable=True,
        notes=(
            "Derived reference, not a City-issued or City-verified boundary dataset. "
            "Contains no flood hazard, rainfall, incident, or susceptibility values."
        ),
    )
    return source_values(source)


class Command(BaseCommand):
    help = "Preview or apply the reviewed local team snapshot; never a full database restore."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True, help="Your existing local superuser email.")
        parser.add_argument(
            "--apply", action="store_true", help="Commit changes; default rolls back."
        )

    def handle(self, *args, **options):
        if not local_testing_enabled():
            raise CommandError(
                "Requires DEBUG, FLOODSENSE_LOCAL_TESTING=true, and loopback PostGIS. "
                "Do not run against a shared, staging, or production database."
            )
        actor = (
            get_user_model()
            .objects.filter(
                email__iexact=options["actor"].strip(),
                is_active=True,
                is_superuser=True,
            )
            .first()
        )
        if actor is None:
            raise CommandError("Choose an existing active local superuser with --actor.")
        package = self._read_package()
        geometries = self._validate_package(package)
        self.counts = {
            key: dict(created=0, changed=0, unchanged=0)
            for key in (
                "sources",
                "areas",
                "centers",
            )
        }
        try:
            with transaction.atomic():
                # Serialize repeated runs of this command without introducing a registry/table.
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(%s)", [406100601])
                self._import(package, geometries, actor)
                if not options["apply"]:
                    transaction.set_rollback(True)
        except ValidationError as error:
            raise CommandError(
                "Snapshot validation failed: " + "; ".join(error.messages)
            ) from error
        self.stdout.write(f"Team snapshot: {package['package_version']}")
        for label, counts in self.counts.items():
            self.stdout.write(f"{label}: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
        self.stdout.write(
            "Applied to this local database only."
            if options["apply"]
            else "PREVIEW ONLY: all row and audit changes rolled back. Run with --apply to save."
        )
        self.stdout.write(
            "Internal boundary status is not City endorsement. Test centers remain DEMONSTRATION; "
            "no facility verification, capacity, public release, or susceptibility data "
            "is imported."
        )

    def _read_package(self):
        try:
            return json.loads(PACKAGE_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise CommandError("Could not read the committed local team snapshot.") from error

    def _validate_package(self, package):
        expected = {
            "format_version",
            "package_version",
            "boundary_files",
            "boundary_source",
            "areas",
            "temporary_source",
            "temporary_centers",
        }
        if (
            not isinstance(package, dict)
            or set(package) != expected
            or package["format_version"] != 1
        ):
            raise CommandError("Unsupported snapshot format or unexpected fields.")
        for key in ("boundary_source", "temporary_source"):
            if not isinstance(package[key], dict) or set(package[key]) != SOURCE_FIELDS:
                raise CommandError("Snapshot sources contain missing or non-allowlisted fields.")
        boundary, temporary = package["boundary_source"], package["temporary_source"]
        if (
            boundary["source_type"] != DataSource.SourceType.AGENCY_DATASET
            or boundary["version"] != BACOOR_REFERENCE_SOURCE_VERSION
            or boundary["status"] not in ("PENDING_VALIDATION", "APPROVED")
            or boundary["is_publicly_releasable"] is not True
            or temporary["source_type"] != DataSource.SourceType.DEMONSTRATION
            or temporary["status"] != PublicationStatus.DEMONSTRATION
            or temporary["is_publicly_releasable"] is not False
            or not temporary["name"].startswith("LOCAL TEST -")
            or not temporary["version"]
        ):
            raise CommandError("Snapshot cannot publish tests or replace boundary provenance.")
        geometries, names = {}, {}
        if set(package["boundary_files"]) != set(BOUNDARY_FILES):
            raise CommandError("Only the two checked-in administrative geometry files are allowed.")
        directory = (
            Path(settings.BASE_DIR).parent / "research_data/administrative_boundaries/processed"
        )
        for filename, count in BOUNDARY_FILES.items():
            raw = (directory / filename).read_bytes()
            if hashlib.sha256(raw).hexdigest() != package["boundary_files"][filename]:
                raise CommandError(
                    "Boundary checksum changed; review the snapshot before importing."
                )
            features = json.loads(raw)["features"]
            if len(features) != count:
                raise CommandError("The snapshot requires one City and 47 barangays.")
            for feature in features:
                properties = feature["properties"]
                code = BACOOR_CITY_CODE if count == 1 else f"PSGC_{properties['psgc_10_digit']}"
                names[code] = "City of Bacoor" if count == 1 else properties["adm4_name"]
                geometry = GEOSGeometry(json.dumps(feature["geometry"]), srid=4326)
                if geometry.geom_type == "Polygon":
                    geometry = MultiPolygon(geometry, srid=4326)
                if geometry.geom_type != "MultiPolygon" or not geometry.valid or code in geometries:
                    raise CommandError("Invalid or duplicate boundary geometry.")
                geometries[code] = geometry
        rows = package["areas"]
        if (
            not isinstance(rows, list)
            or len(rows) != 48
            or any(set(r) != AREA_FIELDS for r in rows)
        ):
            raise CommandError("Only the City and 47 explicit barangay status rows are allowed.")
        if len({r["code"] for r in rows}) != 48 or {r["code"] for r in rows} != set(geometries):
            raise CommandError("Boundary identities do not match the checked-in PSGC dataset.")
        for row in rows:
            expected_type = "CITY" if row["code"] == BACOOR_CITY_CODE else "BARANGAY"
            if (
                row["name"] != names[row["code"]]
                or row["area_type"] != expected_type
                or row["status"] not in ("PENDING_VALIDATION", "APPROVED")
                or row["is_enabled"] is not True
            ):
                raise CommandError("Unexpected boundary identity, status, or enabled state.")
        union = None
        for code, geometry in geometries.items():
            if code != BACOOR_CITY_CODE:
                union = geometry if union is None else union.union(geometry)
        if not union.equals(geometries[BACOOR_CITY_CODE]):
            raise CommandError("The 47 barangays must exactly cover the City boundary.")
        centers = package["temporary_centers"]
        if not isinstance(centers, list) or len(centers) != 2:
            raise CommandError("This snapshot contains exactly two selected temporary centers.")
        identities = set()
        for row in centers:
            if (
                set(row) != CENTER_FIELDS
                or row["approved_for_local_testing"] is not True
                or not row["name"].startswith("LOCAL TEST -")
                or "NOT A REAL" not in row["limitations"]
                or row["area_code"] == BACOOR_CITY_CODE
                or row["area_code"] not in geometries
            ):
                raise CommandError("Test center labels, status, or identity are invalid.")
            try:
                identifier = UUID(row["public_id"])
            except (ValueError, TypeError) as error:
                raise CommandError("Invalid test center public UUID.") from error
            if identifier in identities:
                raise CommandError("Duplicate test center public UUID.")
            identities.add(identifier)
            try:
                latitude, longitude = Decimal(row["latitude"]), Decimal(row["longitude"])
                valid = (
                    latitude.is_finite()
                    and longitude.is_finite()
                    and -90 <= latitude <= 90
                    and -180 <= longitude <= 180
                    and geometries[row["area_code"]].covers(
                        Point(float(longitude), float(latitude), srid=4326)
                    )
                )
            except (InvalidOperation, TypeError, ValueError) as error:
                raise CommandError("Invalid test coordinate.") from error
            if not valid:
                raise CommandError("Test coordinate must be inside its assigned barangay.")
        return geometries

    def _save_source(self, existing, values, *, actor, temporary=False):
        if existing is not None:
            current = source_values(existing)
            if current != values:
                if (
                    temporary
                    or current != original_boundary_source_values()
                    or existing.reviewed_by_id is not None
                    or existing.reviewed_on is not None
                ):
                    raise CommandError("Source conflicts with local edits; nothing will be saved.")
            elif temporary and not existing.test_approved:
                raise CommandError(
                    "Existing temporary source is unapproved; review it locally first."
                )
            else:
                self.counts["sources"]["unchanged"] += 1
                return existing
        source = existing or DataSource()
        for field, value in values.items():
            setattr(source, field, value)
        source.full_clean()
        source.save()
        self.counts["sources"]["changed" if existing else "created"] += 1
        log_source_action(
            actor=actor,
            source=source,
            action_flag=CHANGE if existing else ADDITION,
            message="Imported allowlisted team local snapshot; not agency or City endorsement.",
        )
        if temporary:
            source = transition_source(
                source_id=source.pk,
                action="approve-test",
                actor=actor,
                expected_status=PublicationStatus.DEMONSTRATION,
                expected_public=False,
            )
        return source

    def _import(self, package, geometries, actor):
        city = GeographicArea.objects.select_for_update().filter(code=BACOOR_CITY_CODE).first()
        candidates = list(
            DataSource.objects.select_for_update().filter(
                name__in={BACOOR_REFERENCE_SOURCE_NAME, package["boundary_source"]["name"]},
            )
        )
        if len(candidates) > 1 or city and candidates and city.source_id != candidates[0].pk:
            raise CommandError("Conflicting boundary source identities; nothing will be saved.")
        existing = (
            DataSource.objects.select_for_update().get(pk=city.source_id)
            if city
            else candidates[0]
            if candidates
            else None
        )
        source = self._save_source(existing, package["boundary_source"], actor=actor)
        if source.geographic_areas.exclude(code__in=geometries).exists():
            raise CommandError("Boundary source owns unexpected areas; nothing will be saved.")
        areas = {}
        for values in package["areas"]:
            area = GeographicArea.objects.select_for_update().filter(code=values["code"]).first()
            if area is not None:
                if (
                    area.source_id != source.pk
                    or not area.geometry.equals(geometries[area.code])
                    or any(getattr(area, f) != values[f] for f in AREA_FIELDS - {"status"})
                    or area.status not in {values["status"], PublicationStatus.PENDING_VALIDATION}
                ):
                    raise CommandError(
                        f"Area {area.code} conflicts with local edits; nothing saved."
                    )
                if area.status == values["status"]:
                    self.counts["areas"]["unchanged"] += 1
                    areas[area.code] = area
                    continue
                area.status = values["status"]
                flag, count = CHANGE, "changed"
            else:
                area = GeographicArea(**values, source=source, geometry=geometries[values["code"]])
                flag, count = ADDITION, "created"
            area.full_clean()
            area.save()
            self.counts["areas"][count] += 1
            LogEntry.objects.log_actions(
                user_id=actor.pk,
                queryset=[area],
                action_flag=flag,
                single_object=True,
                change_message=(
                    "Imported team local administrative status; no susceptibility facts."
                ),
            )
            areas[area.code] = area
        temp_matches = list(
            DataSource.objects.select_for_update().filter(
                name=package["temporary_source"]["name"],
            )
        )
        if len(temp_matches) > 1:
            raise CommandError("Ambiguous temporary source; nothing will be saved.")
        temp_source = self._save_source(
            temp_matches[0] if temp_matches else None,
            package["temporary_source"],
            actor=actor,
            temporary=True,
        )
        for row in package["temporary_centers"]:
            center = (
                EvacuationCenter.objects.select_for_update()
                .filter(
                    public_id=row["public_id"],
                )
                .first()
            )
            area = areas[row["area_code"]]
            values = {
                f: row[f] for f in CENTER_FIELDS - {"area_code", "approved_for_local_testing"}
            }
            values.update(latitude=Decimal(row["latitude"]), longitude=Decimal(row["longitude"]))
            values["public_id"] = UUID(row["public_id"])
            if center is not None:
                if (
                    any(getattr(center, f) != v for f, v in values.items())
                    or center.source_id != temp_source.pk
                    or center.geographic_area_id != area.pk
                    or center.publication_status != PublicationStatus.DEMONSTRATION
                    or center.verification_status != EvacuationCenter.VerificationStatus.VERIFIED
                    or center.verified_on is not None
                    or center.capacity is not None
                ):
                    raise CommandError("Test center conflicts with local edits; nothing saved.")
                center.full_clean()
                self.counts["centers"]["unchanged"] += 1
                continue
            if EvacuationCenter.objects.filter(name__iexact=row["name"]).exists():
                raise CommandError("Test center name uses another UUID; refusing a duplicate.")
            center = EvacuationCenter(
                **values,
                source=temp_source,
                geographic_area=area,
                publication_status=PublicationStatus.DEMONSTRATION,
                verification_status=EvacuationCenter.VerificationStatus.IN_REVIEW,
            )
            center.full_clean()
            center.save()
            log_center_action(
                actor=actor,
                center=center,
                action_flag=ADDITION,
                message="Imported selected team local test marker; not a real facility.",
            )
            transition_center(
                center_id=center.pk,
                action="approve-test",
                actor=actor,
                expected_status=EvacuationCenter.VerificationStatus.IN_REVIEW,
            )
            self.counts["centers"]["created"] += 1
