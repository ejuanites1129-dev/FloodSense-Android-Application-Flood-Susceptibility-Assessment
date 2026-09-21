# Unified Bacoor Map

## What the Android map now combines

The assessment screen renders one map instead of separate administrative and
demonstration maps. It combines:

- the current 47-feature Bacoor barangay boundary layer;
- four fictional `DEMO_ZONE` scenario polygons;
- the temporary GPS or manually placed pin;
- the server-confirmed barangay result;
- the server-confirmed fictional demonstration-zone result; and
- verified evacuation-center markers when available.

The OpenStreetMap tile layer remains the visual basemap. Django/PostGIS remains
responsible for point-in-polygon resolution and assessment responses.

## Data boundary

This change does not assign susceptibility values to barangay records. The
colored areas are separate synthetic polygons used to exercise the scenario
engine. They must not be described as live conditions, MGB classifications, or
whole-barangay classifications.

The provisional MGB extract is not imported or displayed by this change. Its
review requirements remain in
`research_data/provisional/mgb_flood_susceptibility/README.md`.

## Refreshing a development database

After pulling the implementation and applying migrations, refresh the
authorized local demonstration database from the repository root:

```powershell
server\.venv\Scripts\python.exe server\manage.py seed_demo
```

The seed moves only the four seed-owned fictional polygons into the Bacoor map
extent. It also refreshes the independently stored Bacoor administrative
boundary layer. The command is transactional and idempotent.

## Verification

From `mobile/`:

```powershell
flutter analyze
flutter test
```

From the repository root, with the backend environment configured:

```powershell
server\.venv\Scripts\python.exe -m pytest -q --reuse-db
```

The seed tests assert that every fictional zone remains a `DEMO_ZONE`, uses
WGS 84 geometry, does not overlap another fictional zone, and is fully covered
by the Bacoor City boundary.
