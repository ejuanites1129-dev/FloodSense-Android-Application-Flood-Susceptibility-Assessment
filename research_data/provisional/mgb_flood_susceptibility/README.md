# Provisional MGB flood-susceptibility extract

## Status

This directory documents a **provisional, unapproved research extract** of the
DENR-MGB `Detailed Flood Susceptibility` ArcGIS FeatureServer layer. It must not
be described as an official Bacoor City flood assessment or imported into the
FloodSense operational database until the research team has reviewed the
source, metadata, reuse conditions, processing report, and intended
methodology.

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
