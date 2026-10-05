# Share the selected local records with teammates

Git shares code and migration instructions, not a running PostgreSQL database.
The reviewed `local-team-2026-10-06` package now lets teammates reproduce selected
rows in their own existing tables. No new tables, schema migration or dependency
was added by this package or the map/local-testing update.

## Current snapshot

| Selected records | Copied state |
| --- | --- |
| Bacoor administrative-boundary source | Internally approved, geometry release retained; not City endorsement |
| City and all 47 barangays | Enabled, **Pending validation** — this is their actual current state |
| Temporary center source and two existing test centers | Approved for local testing only; remain demonstration data |

Contact details, accounts, credentials, original reviewers and restricted research
data are excluded. Later local Admin edits do not automatically travel through
Git. See the [package README](../research_data/provisional/team_local_setup/README.md)
for the full allowlist, provenance and conflict rules.

## After obtaining the reviewed branch/commit

Protect unfinished work before switching or pulling. Merge through the team's
normal review process or check out the pushed feature branch explicitly; merely
pulling `main` will not include an unmerged branch.

From the repository root, after normal Python/PostGIS setup:

```powershell
server\.venv\Scripts\python.exe -m pip install -r server\requirements.txt
server\.venv\Scripts\python.exe server\manage.py migrate --plan
server\.venv\Scripts\python.exe server\manage.py migrate
server\.venv\Scripts\python.exe server\manage.py check
```

Those migration commands bring an older local installation up to the committed
schema; the new package itself creates no migration. Create your own local
superuser if needed (`createsuperuser`); never copy a teammate's account or `.env`.

In your private `server/.env`, enable only for your local development database:

```dotenv
DJANGO_DEBUG=true
FLOODSENSE_LOCAL_TESTING=true
```

Confirm the database is your own local PostGIS database, not a tunnel to a
shared/staging/deployed target. Restart Django after environment changes.

Preview first, replacing the example with your existing local superuser email:

```powershell
server\.venv\Scripts\python.exe server\manage.py import_team_local_data --actor your-local-admin@example.com
```

If the preview shows the expected selected records and no conflict, save them:

```powershell
server\.venv\Scripts\python.exe server\manage.py import_team_local_data --actor your-local-admin@example.com --apply
```

Re-running is idempotent: matching rows are reused without duplicate IDs or
repeat audit entries. If a teammate has modified a matching source, area or
center, the importer stops and rolls back **everything**. Review that conflict
locally; do not delete edited rows or force a database restore. Existing manual
test approvals that have been revoked are not restored automatically.

This replaces the need to run `seed_demo` for these selected records. **Do not
run `seed_demo` just to share approvals**: it also creates/refreshes fictional
demo zones and demonstration expert/DSS data. This snapshot neither imports
those items nor deletes pre-existing demo zones, and it does not transfer an
MGB preview dataset. Follow each separate authorized data workflow if needed.

## Relaunch the app

Restart Django on loopback, then rebuild/run Flutter through the existing local
launcher with one authorized Android device connected:

```powershell
server\.venv\Scripts\python.exe server\manage.py runserver 127.0.0.1:8000
```

In a second terminal:

```powershell
.\scripts\run_android_local.ps1
```

This launcher requires each teammate's own public Mapbox `pk.` token in their
private configuration; tokens are not shared by Git. For OSM, use the ordinary
manual Flutter startup described in [start.md](../start.md) instead. Temporary
centers remain visibly marked as tests and excluded from normal deployed use.

## Verification — 6 October 2026

- The snapshot was compared read-only with the owner's actual source metadata,
  all 48 area identities/statuses/geometries, and both selected center rows.
  No application rows were changed during packaging.
- All 934 backend tests passed in an isolated PostGIS cluster, including 18
  import tests covering fresh setup, preview rollback, repeated runs, stable
  identities, withheld contacts, preserved edits, revoked approvals, atomic
  conflicts and local-only guards.
- Django system check passed; no missing or pending migration was detected.
- Backend/importer and changed verification-script lint passed. Repository-wide
  lint still reports 23 pre-existing findings in the unchanged
  `scripts/regenerate_design_assets.py`; it is outside this change.
- Flutter analysis passed, all 377 mobile tests passed, and the Android debug
  APK build succeeded. The APK is generated locally, not committed.
