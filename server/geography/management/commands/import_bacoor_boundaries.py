"""Import the reviewed Bacoor administrative reference extracts into PostGIS."""

import json
from datetime import date
from pathlib import Path

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from provenance.models import DataSource, PublicationStatus

from geography.constants import (
    BACOOR_REFERENCE_SOURCE_NAME,
    BACOOR_REFERENCE_SOURCE_VERSION,
)
from geography.models import GeographicArea


class Command(BaseCommand):
    help = (
        "Import or refresh the derived Bacoor City and current 47-barangay "
        "administrative reference boundaries."
    )

    def add_arguments(self, parser):
        default_directory = (
            Path(settings.BASE_DIR).parent
            / "research_data"
            / "administrative_boundaries"
            / "processed"
        )
        parser.add_argument(
            "--directory",
            type=Path,
            default=default_directory,
            help="Directory containing the normalized Bacoor GeoJSON extracts.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        directory = options["directory"].resolve()
        city_features = self._read_features(
            directory / "bacoor_city_boundary.geojson", expected_count=1
        )
        barangay_features = self._read_features(
            directory / "bacoor_barangay_boundaries.geojson", expected_count=47
        )
        source = self._source()

        expected_codes = {"PSGC_0402103000"}
        expected_codes.update(
            f"PSGC_{feature['properties']['psgc_10_digit']}"
            for feature in barangay_features
        )
        self._guard_reserved_source(source, expected_codes)

        city = self._save_area(
            source=source,
            code="PSGC_0402103000",
            name="City of Bacoor",
            area_type=GeographicArea.AreaType.CITY,
            geometry_json=city_features[0]["geometry"],
        )
        barangays = []
        for feature in barangay_features:
            properties = feature["properties"]
            barangays.append(
                self._save_area(
                    source=source,
                    code=f"PSGC_{properties['psgc_10_digit']}",
                    name=properties["adm4_name"],
                    area_type=GeographicArea.AreaType.BARANGAY,
                    geometry_json=feature["geometry"],
                )
            )

        union = barangays[0].geometry
        for barangay in barangays[1:]:
            union = union.union(barangay.geometry)
        if not union.equals(city.geometry):
            raise CommandError(
                "The 47 barangay geometries do not exactly cover the imported city boundary."
            )

        self.stdout.write(
            self.style.WARNING(
                "DERIVED ADMINISTRATIVE REFERENCE - NOT CITY-VERIFIED"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Imported 1 Bacoor City boundary and 47 current barangay boundaries."
            )
        )

    def _read_features(self, path: Path, *, expected_count: int) -> list[dict]:
        if not path.is_file():
            raise CommandError(f"Required GeoJSON file was not found: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CommandError(f"Could not read valid GeoJSON from {path}: {error}") from error
        if payload.get("type") != "FeatureCollection":
            raise CommandError(f"Expected a GeoJSON FeatureCollection in {path}.")
        features = payload.get("features")
        if not isinstance(features, list) or len(features) != expected_count:
            raise CommandError(
                f"Expected {expected_count} features in {path}, found "
                f"{len(features) if isinstance(features, list) else 'an invalid features value'}."
            )
        return features

    def _source(self) -> DataSource:
        matches = list(
            DataSource.objects.filter(name=BACOOR_REFERENCE_SOURCE_NAME).order_by("id")
        )
        if len(matches) > 1:
            raise CommandError(
                f"Multiple data sources use reserved name {BACOOR_REFERENCE_SOURCE_NAME!r}."
            )
        if matches:
            source = matches[0]
            if (
                source.source_type != DataSource.SourceType.AGENCY_DATASET
                or source.status != PublicationStatus.PENDING_VALIDATION
            ):
                raise CommandError(
                    "The reserved boundary-source name belongs to a record with an "
                    "unexpected type or publication status."
                )
        else:
            source = DataSource(name=BACOOR_REFERENCE_SOURCE_NAME)

        source.organization = "OCHA HDX; source agencies NAMRIA and PSA"
        source.source_type = DataSource.SourceType.AGENCY_DATASET
        source.version = BACOOR_REFERENCE_SOURCE_VERSION
        source.coverage_description = (
            "Bacoor City and its 47 current barangays. Geometry was derived from "
            "COD-AB legacy polygons using the PSA 2023 barangay-merger mapping."
        )
        source.record_period_start = date(2023, 7, 29)
        source.received_or_created_on = date(2026, 9, 16)
        source.permitted_use = (
            "Academic prototype administrative reference with source attribution; "
            "review licensing and attribution before thesis release or deployment."
        )
        source.status = PublicationStatus.PENDING_VALIDATION
        source.is_publicly_releasable = True
        source.notes = (
            "Derived reference, not a City-issued or City-verified boundary dataset. "
            "Contains no flood hazard, rainfall, incident, or susceptibility values."
        )
        source.full_clean()
        source.save()
        return source

    def _guard_reserved_source(self, source: DataSource, expected_codes: set[str]):
        unexpected = list(
            source.geographic_areas.exclude(code__in=expected_codes).values_list(
                "code", flat=True
            )
        )
        if unexpected:
            raise CommandError(
                "The reserved boundary source owns unexpected geographic areas: "
                + ", ".join(unexpected)
            )

    def _save_area(
        self,
        *,
        source: DataSource,
        code: str,
        name: str,
        area_type: str,
        geometry_json: dict,
    ) -> GeographicArea:
        existing = GeographicArea.objects.filter(code=code).first()
        if existing is not None and existing.source_id != source.id:
            raise CommandError(
                f"Geographic-area code {code!r} already belongs to another source."
            )
        area = existing or GeographicArea(code=code, source=source)
        geometry = GEOSGeometry(json.dumps(geometry_json), srid=4326)
        if geometry.geom_type == "Polygon":
            geometry = MultiPolygon(geometry, srid=4326)
        if geometry.geom_type != "MultiPolygon" or not geometry.valid:
            raise CommandError(f"Area {code!r} does not contain valid multipolygon geometry.")
        area.name = name
        area.area_type = area_type
        area.geometry = geometry
        area.source = source
        area.status = PublicationStatus.PENDING_VALIDATION
        area.is_enabled = True
        area.full_clean()
        area.save()
        return area
