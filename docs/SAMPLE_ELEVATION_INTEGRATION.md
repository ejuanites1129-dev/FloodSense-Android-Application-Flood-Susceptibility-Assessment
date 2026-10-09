# Provisional elevation sample integration — 9 October 2026

## Scope and authority

The project owner requested inspection and integration of the local elevation
sample. This authorizes descriptive local data staging, not adviser/agency
approval, an official LiPAD import, a new research method, or elevation-based
susceptibility thresholds. Existing inference, rainfall scenarios, MGB consultation
baseline, map colors and preparedness guidance remain unchanged.

The sample is **not the requested LiPAD 1 m DTM**. Its TIFF uses a 1 arc-second
WGS 84 grid (approximately 30 m); its LAS export identifies FABDEM V1.2 and
FloodSense provisional processing. LAS/COPC are exported raster points, not
evidence of a new LiDAR survey. The delivered TIFF band identifies metre values.
Its vertical datum is not embedded/verified. EGM2008 declarations in the derived
point files are evidence to review, not proof of a local mean-sea-level reference.

The [University of Bristol FABDEM V1.2 register](https://research-information.bris.ac.uk/en/datasets/fabdem-v1-2/)
describes a terrain product with forest/building biases reduced, approximately
30 m grid spacing, and CC BY-NC-SA 4.0 terms. Verify this delivery's original
download, version, processing and permissions before redistribution. No raw or
derived sample values are included in ordinary Git.

## What is implemented

- A bounded, read-only GeoTIFF processor uses the existing native GDAL/GEOS stack.
  No rasterio, NumPy, ML, new package or schema migration is needed.
- Min/mean/max and valid-cell counts are computed for each of the 47 current
  reference barangays. These are **descriptive cell-center statistics**, not
  area-weighted elevations or flood susceptibility classes. A barangay mean is
  not a resident's point/house elevation.
- NoData, nonfinite values and outside-raster cells remain missing, not zero.
  Valid negative/zero heights are retained. Polygon holes are excluded. CRS
  transformation and GDAL band scale/offset are handled without resampling.
  Unsupported rotation, complex values, masks, foreign units or dependencies
  fail closed. Untagged metre assumptions require an explicit development flag.
- Coverage percent uses valid / all grid centers within each polygon, including
  centers outside the raster. The raster's rectangular valid fraction is reported
  separately and must not be described as city coverage.
- Input checksums, calibration, CRS, grid, unit basis, unknown datum, boundaries,
  geometry fingerprints, sample labels and statistics are recorded in a versioned
  JSON report and labeled CSV. Participating `.aux.xml` is checksummed too.
- An explicitly requested local staging option stores six numeric statistics per
  covered barangay in existing `AreaFact` rows under a versioned private
  `DataSource`: `OTHER`, `PENDING_VALIDATION`, publicly releasable **false**;
  every fact remains **disabled**. Min/mean/max are omitted for no-valid-cell areas.
  It cannot approve/activate a parameter or create a flood baseline.
- Replay is immutable/idempotent. Edited source/facts, changed local boundaries,
  duplicate identities or non-local targets are rejected without partial writes.

The six keys are `sample_elevation_min`, `sample_elevation_mean`,
`sample_elevation_max` (metres), `sample_elevation_cell_count`,
`sample_elevation_valid_cell_count` (counts), and
`sample_elevation_coverage_percent` (percent of grid centers).

The existing technical Django Admin can inspect these pending AreaFacts. They
are excluded from both demonstration and official inference. Do not enable or
approve them manually as a shortcut. No new ordinary-Admin parameter controls,
resident elevation endpoint, per-cell classification, or colored hazard layer is
introduced. AHP/WLC remains a review-only proposal.

## Local files and original preservation

Original delivery: `FILES/data gathered/elevation sample/`, now ignored by Git.
Generated reports: `tmp/elevation-sample/<content-version>/`, also ignored.
Original TIFF/QGZ/LAS/COPC/XYZ/shapefile files remain unchanged.

The standalone AOI `.shp` lacks `.shx`, `.dbf` and `.prj`. The QGZ's XYZ URI is
corrupted. Neither is used for processing; the TIFF and existing reviewed
administrative-reference GeoJSON suffice. This integration does not repair or
overwrite the QGIS project. Request complete vector components/recreate the XYZ
layer separately if needed.

## Teammate setup after pulling code

No new dependency, migration, seed or automatic import is required. Local records
and ignored datasets are **not synchronized by Git**. Obtain an authorized copy
of the sample through the team's data-sharing process, not a Git commit. Existing
local boundaries must match the complete reference dataset; the tool will not
create or replace them.

From the repository root, inspect without changing the database:

```powershell
server\.venv\Scripts\python.exe server\manage.py inspect_elevation_sample `
    --raster 'FILES/data gathered/elevation sample/bacoor_provisional_fabdem_dtm_30m.tif'
```

Review the generated JSON/CSV. Only when local inactive staging is wanted:

```powershell
server\.venv\Scripts\python.exe server\manage.py inspect_elevation_sample `
    --raster 'FILES/data gathered/elevation sample/bacoor_provisional_fabdem_dtm_30m.tif' `
    --apply-local
```

Staging requires the actual database connection to be loopback PostgreSQL/PostGIS
with Django DEBUG/GIS enabled. Never repoint this command at a shared/deployed DB.
It does not modify private `.env` or use a new database. All writes are atomic.
Restart Django only to pick up new code; no Flutter rebuild is needed for this
backend-only staging. Do not expect changed susceptibility colors.

## Before an elevation input can change results

Confirm the original product/version, dates, permitted use and vertical datum;
review its cell resolution, coverage/quality and suitability; agree on the spatial
assessment unit and scientifically justified elevation interpretation; obtain
dated team/expert/adviser authorization as applicable; then version and test the
adopted input/rules and mobile contract. Receipt or technical readability alone
does not complete these gates. Never subtract absolute elevation from rainfall
depth or interpret negative heights as a safe/non-flooding result.

## Verification

Synthetic tests cover units, source integrity, NoData/negative/zero values,
Float32 sentinel precision, holes, partial/outside coverage, CRS transformation,
calibration, masks, spoofed datasources, immutable reports/tables, local-only
storage, rollback, repeatability, mode separation and unchanged inference.
Database-backed checks use an isolated disposable PostGIS test cluster when the
application role cannot create a test database. See
`scripts/test_operations_isolated.ps1`; never grant additional production role
permissions merely to run tests.
