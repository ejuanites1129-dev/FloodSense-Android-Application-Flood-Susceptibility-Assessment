# FloodSense

FloodSense is a planned Android application for scenario-based flood susceptibility assessment and pre-event preparedness in Bacoor City. Its core classification component is a deterministic, rule-based Expert System. It is not a real-time forecast or official warning service.

## Planned stack

- Flutter and Dart for the Android application
- Django and Django REST Framework for the backend and mobile API
- GeoDjango with PostgreSQL/PostGIS for spatial data
- Django Admin for the initial administration interface
- A custom Python forward-chaining engine inside Django

## Repository layout

- `mobile/` - Flutter Android application (created after the Flutter SDK is installed)
- `server/` - Django backend, API, admin, Expert System, and DSS
- `docs/` - technical decisions, API notes, and research-data templates
- `research_data/provisional/` - fictional or unvalidated development fixtures only
- `research_data/approved/` - validated data approved for research use
- `FILES/` - existing research documents
- `frontend-design-output/` - high-fidelity interface mockups, shared palette tokens, and the regenerated component/design boards
- `scripts/regenerate_design_assets.py` - rerenders the design boards and applies the shared tokens to the screen references

## Data safety rule

Provisional records must never be presented as official Bacoor flood information. Until approved geographic data and expert rules are available, public assessments must return `Insufficient Data` or display a clear demonstration-data warning.

## Backend bootstrap

1. Create and activate `server/.venv`.
2. Install `server/requirements.txt`.
3. Copy `server/.env.example` to `server/.env` and configure PostgreSQL/PostGIS.
4. Run Django checks and migrations after PostgreSQL/PostGIS is available.

The complete teammate-ready Windows manual is in
`docs/COMPLETE_WINDOWS_SETUP_GUIDE.md`. A shorter setup reference is available
in `docs/SETUP_WINDOWS.md`. All contributors and coding agents must also follow
`docs/TEAM_DATABASE_AND_GIT_WORKFLOW.md` before changing models, migrations,
seed/import processes, or shared backend data.

Before PostGIS is installed, the database-independent backend foundation can be checked with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_backend_bootstrap.ps1
```

After PostgreSQL/PostGIS, GDAL/GEOS, and `server/.env` are configured, verify the real spatial stack with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_postgis.ps1
```
