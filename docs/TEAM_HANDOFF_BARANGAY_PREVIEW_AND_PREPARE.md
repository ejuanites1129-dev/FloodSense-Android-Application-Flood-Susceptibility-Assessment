# Team handoff: barangay preview, Prepare flow, and mobile sheet update

This guide is the exact teammate setup checklist for the FloodSense update that
adds the guarded provisional MGB barangay-susceptibility consultation preview,
the structured presentation Prepare flow, unified barangay assessment
selection, and the improved draggable/collapsible resident bottom sheet.

The normal safe state remains scenario-based. This update does not add live
monitoring, background location tracking, timers, forecasts, or official flood
warnings.

## What changed

- Django has two new geography models for a versioned susceptibility dataset
  and per-barangay area-composition summaries.
- Migration `geography.0002_floodsusceptibilitydataset_and_more` creates the new
  tables and constraints.
- `seed_demo` now creates an idempotent, versioned structured preparedness flow
  for presentations. It remains pending expert validation.
- A guarded import command can load the locally processed MGB consultation
  preview. The import does not approve the source or make it production data.
- The resident assessment uses the real 47-barangay reference layer when a
  complete active preview is available, so the duplicate demo-zone selector is
  not shown in that mode.
- The map bottom sheet can be collapsed, expanded, and dragged through
  intermediate heights without losing scrolling after navigation changes.

## Dependencies

No new framework or package was added by this update. Teammates should still
resynchronize the already-declared Python and Flutter dependencies after
pulling so their local environments match the repository lock/configuration
files.

From the repository root:

```powershell
server\.venv\Scripts\python.exe -m pip install -r server\requirements.txt
Set-Location mobile
flutter pub get
Set-Location ..
```

If the virtual environment, PostgreSQL/PostGIS, GDAL, Flutter, or Android SDK is
not installed yet, follow `docs/COMPLETE_WINDOWS_SETUP_GUIDE.md` instead of
trying to repair the environment with ad hoc commands.

## Required steps after pulling

Protect unfinished work before pulling. Then run:

```powershell
git status
git pull origin main

server\.venv\Scripts\python.exe -m pip install -r server\requirements.txt
server\.venv\Scripts\python.exe server\manage.py migrate --plan
server\.venv\Scripts\python.exe server\manage.py migrate
server\.venv\Scripts\python.exe server\manage.py seed_demo
server\.venv\Scripts\python.exe server\manage.py check

Set-Location mobile
flutter pub get
flutter analyze
flutter test
Set-Location ..
```

`migrate`, not `makemigrations`, is the correct command after pulling the
committed migration. Do not delete, regenerate, or rewrite shared migration
history.

The Prepare presentation content needs no additional schema migration. Running
`seed_demo` creates or refreshes its versioned questions, choices, branches,
and outcomes without creating duplicates. Local users, superusers, and other
manually entered database rows are not transferred by Git.

## Optional: enable the provisional MGB consultation preview

The source and processed MGB files are intentionally not committed because the
reuse/redistribution conditions, map production date, scale, methodology, and
class definitions still require confirmation. Therefore, pulling the code alone
does not give another computer the active MGB preview.

Only on an authorized local development computer:

1. Reproduce the extract, or receive the reviewed generated files through a
   team-approved non-Git channel:

   ```powershell
   server\.venv\Scripts\python.exe scripts\extract_mgb_bacoor_flood_susceptibility.py
   ```

2. Add this setting to the local, ignored `server/.env` file:

   ```dotenv
   FLOODSENSE_ENABLE_PROVISIONAL_MGB_PREVIEW=True
   ```

3. Ensure `DJANGO_DEBUG=True` locally, then import and activate the consultation
   snapshot:

   ```powershell
   server\.venv\Scripts\python.exe server\manage.py migrate
   server\.venv\Scripts\python.exe server\manage.py seed_demo
   server\.venv\Scripts\python.exe server\manage.py import_mgb_susceptibility --activate-consultation-preview
   ```

Both development guards must be true before the API exposes the preview. Leave
the preview flag false in shared, staging, and production environments. Never
commit `server/.env`, the ignored `raw/` and `processed/` outputs, database
dumps, credentials, or restricted agency data.

Read
`research_data/provisional/mgb_flood_susceptibility/README.md` before extracting
or importing. It documents the source, validation report, uncertainty handling,
and unresolved approval limitations.

## Run and refresh

Restart Django after migrations, seed/import operations, or environment-variable
changes:

```powershell
server\.venv\Scripts\python.exe server\manage.py runserver 0.0.0.0:8000
```

For a web viewport:

```powershell
Set-Location mobile
flutter run -d chrome --web-hostname localhost --web-port 3000
```

For an already connected Android device, replace the device ID with the value
shown by `flutter devices`:

```powershell
Set-Location mobile
flutter devices
flutter run -d DEVICE_ID --dart-define=FLOODSENSE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

When the device uses USB and the backend is on the same Windows computer, Android
SDK `adb reverse tcp:8000 tcp:8000` must be active. If `adb` is not on `PATH`,
run it from the Android SDK `platform-tools` directory as described in the full
Windows setup guide. `flutter run` rebuilds and updates the installed debug app;
uninstalling the older APK is normally unnecessary.

Use Flutter hot reload (`r`) for ordinary Dart UI edits and hot restart (`R`)
for stateful/navigation changes. Environment-variable, native-plugin, migration,
and backend seed/import changes require the corresponding process restart.

## Verification checklist

- `python manage.py showmigrations geography` shows migration `0002` as applied.
- `python manage.py check` reports no issues.
- `seed_demo` completes safely and may be rerun without duplicate content.
- The Prepare tab opens the structured preparedness questions and branches.
- The resident map sheet collapses almost completely, expands from its centered
  arrow control, supports intermediate drag heights, and still scrolls after
  switching navigation tabs.
- Without the optional preview flag/data, the application fails closed to its
  labeled demonstration/insufficient-data behavior.
- With the guarded local preview active, GPS, manual selection, and map
  selection resolve to the same one of 47 barangays, and no duplicate demo-zone
  selector appears.
- Provisional source/status wording remains visible. Do not describe the MGB
  composition as an approved BDRRMO or official whole-barangay classification.

## Backend test-database note

The Django test suite creates a separate PostgreSQL test database. If it fails
before tests run with `permission denied to create database`, the local database
role lacks test-database creation permission; this is an environment permission
problem, not permission to run tests against the normal application database.
Ask the teammate responsible for the local PostgreSQL installation to grant the
development test role the needed local-only privilege, or use the team's
approved isolated test database setup. Do not point destructive tests at a
shared, staging, or production database.
