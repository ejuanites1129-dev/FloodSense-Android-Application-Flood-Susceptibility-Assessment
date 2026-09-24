# Provisional MGB flood-susceptibility extract

## Status

This directory documents a **provisional, unapproved research extract** of the
DENR-MGB `Detailed Flood Susceptibility` ArcGIS FeatureServer layer. It must not
be described as an official Bacoor City flood assessment or imported into the
FloodSense approved/production data path until the research team has reviewed
the source, metadata, reuse conditions, processing report, and intended
methodology. A local consultation preview may be imported through the guarded
command below; it remains `PENDING_VALIDATION`, non-publicly-releasable, and
visibly provisional throughout the API and resident interface.

The source service is publicly queryable, but its REST metadata currently has
blank description and copyright fields. The team must obtain or verify the
applicable permission, attribution, map date/version, scale, methodology,
coordinate reference system, and class definitions before thesis publication
or production use.

## Source

- Custodian/domain: Department of Environment and Natural Resources - Mines
  and Geosciences Bureau (DENR-MGB)
- Layer: `Detailed Flood Susceptibility` (`FeatureServer/0`)
- Service URL:
  <https://controlmap.mgb.gov.ph/arcgis/rest/services/GeospatialDataInventory/GDI_Detailed_Flood_Susceptibility/FeatureServer/0>
- Source field: `FloodSusc`
- Observed codes: `LF`, `MF`, `HF`, and `VHF`
- Accessed for this provisional extraction: `2026-09-16`

## Local-only generated files

The `raw/` and `processed/` directories are ignored by Git while permission and
redistribution terms remain unresolved.

`raw/` preserves each ArcGIS response exactly as downloaded. The server cannot
reliably return all matching geometries in one request, so the extraction first
gets matching object IDs and then downloads each feature separately.

`processed/` contains:

- `bacoor_flood_susceptibility_source_features.geojson` - exact Bacoor-clipped
  source features, retained separately for audit;
- `bacoor_flood_susceptibility_classes.geojson` - dissolved map classes plus
  explicit `CONFLICT` and `UNMAPPED` uncertainty areas when present; and
- `barangay_susceptibility_area_summary.csv` - percentage and area of every
  output category within each of the 47 current reference barangays; this is an
  area-composition table, not a whole-barangay classification; and
- `validation_report.json` - source IDs, hashes, repairs, area measurements,
  overlaps, coverage, and warnings.

The processing script never resolves conflicting classifications by silently
selecting the more severe or less severe class. Cross-class overlaps become
`CONFLICT`, while city area with no source classification becomes `UNMAPPED`.
Neither is an MGB susceptibility class.

## Reproduce locally

From the repository root, with the existing backend environment configured:

```powershell
server\.venv\Scripts\python.exe scripts\extract_mgb_bacoor_flood_susceptibility.py
```

Rerunning the command reuses valid cached raw responses. Use `--refresh` only
when deliberately retrieving a new source snapshot. A refreshed extraction
must be treated as a new provisional version and reviewed again.

## Required review before database integration

1. Confirm the source layer's authorization and attribution requirements.
2. Obtain or verify the map version/date, scale, methodology, and class
   definitions from MGB.
3. Inspect `validation_report.json`, especially cross-class overlap and
   unmapped coverage.
4. Visually compare the processed layer against the Bacoor city and 47 current
   barangay reference boundaries.
5. Have the research adviser or appropriate subject-matter expert approve how
   the layer will be used by the Expert System.
6. Build a separate reviewed, transactional, idempotent database import. Do not
   relabel this provisional extraction as approved data in place.

## Local consultation-preview import

After running migrations and `seed_demo` (which imports the controlled 47
barangay boundary layer), a researcher who has reviewed the local processing
outputs can explicitly activate this snapshot for a local consultation:

Add this to the local `server/.env` only (shared/deployed environments leave it
disabled):

```dotenv
FLOODSENSE_ENABLE_PROVISIONAL_MGB_PREVIEW=True
```

Then run:

```powershell
cd server
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py import_mgb_susceptibility --activate-consultation-preview
```

The command validates all 47 PSGC identities, names, percentages, provenance,
CRS, and report status before an atomic import. It stores the complete
LF/MF/HF/VHF, `CONFLICT`, and `UNMAPPED` composition. A baseline rank is derived
only when one mapped class has a unique largest area share; a tie or zero mapped
coverage remains unclassified. Re-running the same snapshot is idempotent, and
a changed file hash creates a new version instead of overwriting provenance.

This command does **not** approve the data, resolve MGB reuse rights, establish
the unknown map production date, or make the ignored source files distributable
through Git.

Both `DJANGO_DEBUG` and `FLOODSENSE_ENABLE_PROVISIONAL_MGB_PREVIEW` must be true
before the active dataset can reach the consultation API. The setting defaults
to false, so pulling the code, running migrations, or importing an inactive
version cannot publish it to a shared or production resident application.
