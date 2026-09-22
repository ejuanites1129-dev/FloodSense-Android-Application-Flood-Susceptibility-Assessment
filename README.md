# FloodSense

FloodSense is a planned Android application for scenario-based flood susceptibility assessment and pre-event preparedness in Bacoor City. Its core classification component is a deterministic, rule-based Expert System. It is not a real-time forecast or official warning service.

The current demonstration vertical slice includes Django-managed hypothetical
rainfall options, fictional map polygons, backend-derived map colors, temporary
pin resolution through PostGIS, explainable single-zone assessment, and DSS
preparedness guidance. Every demonstration response remains explicitly labeled
as unofficial.

## Current implementation sources of truth

Before changing thesis-facing behavior, read:

- `docs/TA_CONSULTATION_SYSTEM_DECISIONS.md` for the decisions distilled from
  the adviser consultation and the team's later scenario-based scope decision;
- `docs/ADMIN_WEB_7_DAY_IMPLEMENTATION_PLAN.md` for the current Admin web
  sequence, acceptance criteria, and ownership boundaries;
- `docs/GPS_AND_SAFE_IMPROVEMENTS_7_DAY_PLAN.md` for the foreground-GPS,
  barangay-resolution, nearest-center, three-member workload, and integration
  plan; and
- `docs/TEAM_DATABASE_AND_GIT_WORKFLOW.md` for shared-code and local-database
  responsibilities.

These current decision documents supersede conflicting feature descriptions in
older demonstration guides or diagrams. In particular, FloodSense does not run
background rainfall timers, and ordinary administrators do not edit raw Expert
System rules.

## Planned stack

- Flutter and Dart for the Android application
- Django and Django REST Framework for the backend and mobile API
- GeoDjango with PostgreSQL/PostGIS for spatial data
- Django templates for the authorized administration portal; Django Admin is
  retained as a technical maintenance interface
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

For an authorized local development database only, the tested setup command can
create or refresh the fictional demonstration records and the separate
pending-validation Bacoor City/barangay administrative reference layer:

```powershell
server\.venv\Scripts\python.exe server\manage.py seed_demo
```

The administrative reference records contain no susceptibility facts and are
not City-verified. Never run this command against a shared, staging, or deployed
database without explicit authorization. See
`docs/DAY_6_DYNAMIC_MAP_GUIDE.md` for its safety checks and the map/API workflow.

Resident authentication, Remember Me, email/Google setup, versioned legal and
onboarding gates, Account/Preferences, structured DSS, and the multi-step
Android assessment are documented in
`docs/RESIDENT_AUTH_ONBOARDING_AND_DSS_SETUP.md`.

## Administration portal

Start Django, then open `http://127.0.0.1:8000/management/`. The portal accepts
existing active staff or superuser accounts. The separate `/admin/` route is
the technical Django Admin and is not the designed day-to-day interface.

Day 1 provides the responsive authenticated shell and protected module routes;
later days replace the clearly labeled placeholders with working management
screens. See `docs/ADMIN_FRONTEND_DAY_1_GUIDE.md` for the scope and verification
commands.
