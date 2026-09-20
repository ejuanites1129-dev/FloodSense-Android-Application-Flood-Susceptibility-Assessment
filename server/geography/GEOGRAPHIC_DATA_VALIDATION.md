# Geographic dataset validation

`validate_geographic_dataset` is a read-only technical reporting command for a
candidate GeoJSON file. It does not import records, update a database, approve a
source, activate a layer, or publish data.

From the repository root, an authorized developer can inspect the checked-in
derived Bacoor reference layer with:

```powershell
server\.venv\Scripts\python.exe server\manage.py validate_geographic_dataset `
  research_data\administrative_boundaries\processed\bacoor_barangay_boundaries.geojson `
  --identity-field psgc_10_digit `
  --expected-geometry-type MultiPolygon `
  --expected-feature-count 47 `
  --expected-crs EPSG:4326 `
  --fail-on-issues
```

The JSON report records file presence, SHA-256 checksum, size, dataset name,
declared metadata, CRS, bounding box, feature and geometry counts, missing or
duplicate identity values, and null, empty, or invalid geometries. Metadata not
declared inside the candidate file is reported as `unknown`; the command never
invents source, custodian, license, dates, units, resolution, processing notes,
limitations, or validation status.

The command accepts a local path but does not copy the dataset into the
repository. Follow the applicable `research_data/**/README.md`: restricted or
unapproved raw data stays outside ordinary Git, provisional data remains
provisional, and technical validation never constitutes institutional approval.

No susceptibility formula or inference behavior is part of this tool. Any
future importer requires a separate review, authorization, transactional
implementation, and tests.
