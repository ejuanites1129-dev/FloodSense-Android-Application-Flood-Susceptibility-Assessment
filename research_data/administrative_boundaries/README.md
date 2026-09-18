# Bacoor administrative-boundary source and normalized extracts

## Status and permitted use

These files provide administrative geometry only. They do **not** contain
flood-hazard, flood-depth, rainfall, historical-incident, or susceptibility
information. Until the research team completes source review and accepts the
dataset, the Bacoor extracts must be described as secondary reference data and
must not be presented as boundaries issued or verified by the City Government
of Bacoor.

## Source

- Dataset: *Philippines administrative level 0-4 boundaries (COD-AB)*
- Distributor: United Nations Office for the Coordination of Humanitarian
  Affairs (OCHA), Humanitarian Data Exchange (HDX)
- Dataset page: <https://data.humdata.org/dataset/cod-ab-phl>
- Named source agencies in the dataset metadata: National Mapping and Resource
  Information Authority (NAMRIA) and Philippine Statistics Authority (PSA)
- License reported by the dataset page: Creative Commons Attribution for
  Intergovernmental Organisations (CC BY-IGO)
- Source feature version: `v03`
- Source feature `valid_on`: `2025-02-13`
- Processing date: `2026-09-16`

The ADM4 source still contains Bacoor's former 73 barangays despite its
`valid_on` field. It is therefore preserved only as the legacy geometry source.
The current administrative identities and merger mapping come from:

- PSA Third Quarter 2023 PSGC update:
  <https://psa.gov.ph/content/third-quarter-2023-psgc-updates-conversion-new-city-merging-44-barangays-renaming-five>
- Current PSA City of Bacoor barangay listing:
  <https://psa.gov.ph/classification/psgc/barangays/0402103000>
- Legal basis recorded by PSA: City Ordinance No. 275-2023, ratified through
  plebiscites on `2023-07-29`

The source page, license, attribution requirements, and current Philippine
Standard Geographic Code (PSGC) should be reviewed again before thesis release
or production deployment.

## Local raw files

The national files are intentionally ignored by Git because they are hundreds
of megabytes each. Preserve them unchanged on an authorized local drive:

```text
phl_admin3.geojson
phl_admin4.geojson
```

SHA-256 checksums of the source files used for this extraction:

```text
phl_admin3.geojson
F682747FBB26BA773131049EF61603F4B872BA93739F6E2C3320F55DD21EEC41

phl_admin4.geojson
4EBB5E3CF7B3245C659EA5886725E6A77FFC2D4BCBE3963D8F704D5ADC5523D2
```

## Normalized Bacoor extracts

The `processed/` directory contains:

```text
bacoor_city_boundary.geojson
bacoor_barangay_boundaries.geojson
bacoor_barangay_boundaries_legacy_73.geojson
```

`bacoor_barangay_boundaries.geojson` is the current 47-feature **derived
reference layer**. `bacoor_barangay_boundaries_legacy_73.geojson` preserves the
pre-merger source polygons used to construct it. The mapping is recorded in
`bacoor_barangay_mapping_2023.json`.

SHA-256 checksums of the generated files:

```text
bacoor_city_boundary.geojson
1AA3497B226A5C5ED8D33E400AB7732CB092704CEE9496806088535D6173D5D3

bacoor_barangay_boundaries.geojson
9C3E53643039BA71E88E6ECD5F7A23BFB87980B3375E086E826EFE97AAA8F213

bacoor_barangay_boundaries_legacy_73.geojson
497856B2C987BA3EA8A3A34C62AF67EA4D0F2454920B364652E26FD00C3853D6
```

All files use RFC 7946 GeoJSON coordinates in WGS 84 (`EPSG:4326`). The city
and legacy files contain valid Polygon geometry. The current 47-feature layer
contains MultiPolygon geometry compatible with the existing GeoDjango model.
The extraction uses Bacoor City's ADM3 P-code, `PH0402103`, instead of relying
only on a text-name comparison.

Validation performed on `2026-09-16` found:

- one Bacoor City feature;
- 73 unique legacy features, each consumed exactly once by the mapping;
- 47 current features: 24 retained units, five renamed units, and 18 merged
  units formed from 44 mother units;
- 47 unique current names and 47 unique current PSGC codes;
- all current barangays have parent P-code `PH0402103`;
- every geometry is valid;
- the 47-barangay union exactly covers the city polygon in the supplied
  geometry;
- no measured gaps, overlaps, or derived barangay geometry outside the city
  polygon;
  and
- source-reported barangay areas sum to `49.01032639 km²`, equal to the
  source-reported city area.

The current 47-feature file is a reproducible derivation, not a newly surveyed
or City-issued boundary dataset. This technical validation does not constitute
institutional validation of the administrative boundaries.

## Reproducing the extraction

From the repository root, with the national source files in this directory and
PostgreSQL 17/PostGIS installed, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\extract_bacoor_boundaries.ps1
server\.venv\Scripts\python.exe scripts\build_current_bacoor_boundaries.py
```

The extraction script uses GDAL's `ogr2ogr.exe` from the PostgreSQL 17
installation. The Python build script validates the official mapping, dissolves
merged polygons, assigns the current PSGC identities, and checks whole-city
coverage.

## Importing into FloodSense

After migrations have been applied, import the checked-in normalized extracts
from the repository root:

```powershell
server\.venv\Scripts\python.exe server\manage.py import_bacoor_boundaries
```

For an authorized local development database, the normal combined setup command
also invokes this importer after refreshing the fictional demonstration data:

```powershell
server\.venv\Scripts\python.exe server\manage.py seed_demo
```

The standalone import command remains useful when only the neutral reference
layer needs to be refreshed.

The command is transactional and idempotent. It creates or refreshes one City
record and 47 Barangay records in PostGIS under the reserved derived-reference
source. It refuses to take over a PSGC code owned by another source and checks
that the barangay union exactly covers the imported City boundary.

The imported records remain `PENDING_VALIDATION`; they are not approved City
data and they contain no susceptibility facts. The Android app retrieves the 47
barangays from:

```text
GET /api/v1/geography/reference-boundaries/
```

This dedicated endpoint and its neutral map are separate from the fictional
demonstration assessment endpoints. Do not add flood classifications or
`AreaFact` records to the imported barangays unless those values have an
independently reviewed source and approval workflow.
