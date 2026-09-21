# GPS Streams A and B Day 7 release rehearsal

**Rehearsal date:** 20 September 2026
**Commit rehearsed:** `57aaecce1c6eea9a8732bc5b41b9c63769f07cd1`
**Scope:** Stream A mobile location/assessment/center presentation and Stream B
geography/barangay resolution
**Verdict:** **Conditionally ready**

> **Historical snapshot:** Every blocker and verdict below describes the exact
> rehearsed commit from 20 September. Stream C/D Days 1–3 landed later and are
> intentionally not retroactively claimed by this report. Use
> `GPS_STREAMS_A_B_DEPENDENCY_BLOCKERS.md` and
> `GPS_STREAM_A_NEAREST_CENTER_DAY_3_HANDOFF.md` for current status.

At the rehearsed commit, the foreground GPS, manual-location, barangay resolver,
assessment-separation, privacy, accessibility, and failure-handling work is
reproducible and passes the
automated release gates. The complete resident nearest-center path is not a
release candidate because Stream C still has no public eligibility service or
endpoint and Stream A consequently has no production HTTP adapter. Android
emulator startup remains blocked by local disk capacity, but a targeted
walkthrough was subsequently completed on a connected Android 14 physical
device. This rehearsal did not deploy, alter a shared database, or import
official data.

## 1. GitHub synchronization

- Current branch and upstream: `main` and `origin/main`.
- `git fetch --prune` completed successfully.
- Ahead/behind after fetch: `0/0`.
- Commit before and after the check: `57aaecce1c6eea9a8732bc5b41b9c63769f07cd1`.
- No pull was required and no conflict was present.
- Earlier Days 1-6 work was already committed and pushed. Day 7 changes are
  intentionally not committed or pushed because the Day 7 guide prohibits that
  without a separate instruction.

## 2. Day 6 readiness gate

Verified by the complete backend and Flutter suites:

- the mobile sequence is scenario, location, confirmation, assessment, then
  center information;
- foreground permission, one-shot acquisition, manual fallback, confirmation,
  cleanup, retry, stale-response rejection, and duplicate-request prevention
  remain intact;
- selections survive recoverable location and center failures;
- 320 x 568 at 2.5x text, 320 x 640 at 2x text, and a 640 x 320 landscape
  transition remain covered by widget tests;
- the permission dialog scrolls and the center status/cards expose accessible
  semantics;
- reference polygons remain cached across unrelated scenario changes;
- the resolver remains bounded by one/four/five SELECTs depending on state and
  returns a small allowlisted response;
- the existing spatial index remains covered by the performance regression;
- the read-only geographic validator does not import, approve, or activate data;
  and
- no official or provisional susceptibility data was activated.

The retained Day 6 measurement was four SELECTs, a 490-byte resolved response,
and a 5.756 ms mean over 50 warm calls on the documented local environment. It
is development evidence, not a production service-level claim. The mobile
measurement proves elimination of one repeated polygon transformation; it does
not claim a device frame-time improvement.

One non-functional defect was corrected during Day 7: the current Dart
formatter required one long test declaration in
`mobile/test/location_day4_centers_test.dart` to be wrapped. No runtime behavior
changed.

## 3. Dependency-blocker classification

| Blocker | Classification | Evidence at rehearsed commit and owner | Release impact / safest next action |
| --- | --- | --- | --- |
| Foreground location dependency and Android declarations | Resolved | `geolocator` is locked; the merged debug manifest has coarse/fine foreground permissions only. Stream A. | None. Retain one-shot behavior and manifest regression checks. |
| Exact nearest-center wire contract, safe fields, statuses, limits, units, and errors | Still active; owned by Programmer 2 / Streams C-D | `server/evacuation/` has no contract, serializer, service, or URL; `mobile/STREAM_C_NEAREST_CENTER_HANDOFF.md` remains accurate. | Prevents live center parsing and end-to-end release-candidate status. Freeze a reviewed contract first. |
| Cross-stream/deployed request-logging and privacy evidence | Still active; owned by Programmer 2 / Stream D and deployment owner | Repository middleware contains no request-body logger, and resolver tests prove no audit write. No checked-in evidence describes external proxy/APM logs. | Does not block local resolver tests; blocks an unconditional deployed privacy claim. Review the actual deployment stack without logging coordinates or bodies. |
| Resident eligibility queryset and per-request recheck | Still active; owned by Programmer 2 / Stream C | `server/evacuation/models.py` is an administrative record model; no resident service exists. | Blocks proof that draft, restricted, inactive, or malformed centers cannot reach residents. Implement backend-only eligibility and tests. |
| Authoritative straight-line distance, full-precision ordering, tie order, and result cap | Still active; owned by Programmer 2 / Stream C | No evacuation service or endpoint exists. Stream A deliberately does not calculate, sort, or cap authoritative results. | Blocks live scenarios 8-9 and endpoint performance evidence. Implement and test in Stream C. |
| `POST /api/v1/evacuation-centers/nearest/` and shared URL registration | Still active; owned by Programmer 2 / Streams C-D | `server/evacuation/views.py` is a placeholder, there is no `server/evacuation/urls.py`, and `server/config/urls.py` has no evacuation API include. | Blocks safe empty/results/error responses. Programmer 2 must implement; the shared URL owner must register it. |
| Stable public center identifier distinct from raw row ID | Still active; owned by Programmer 2 / Streams C-D | `EvacuationCenter` has only the implicit database primary key. | Blocks final response contract and strict mobile parsing. Approve and migrate a public identifier with tests. |
| Production `NearestCenterProvider` HTTP adapter | Still active, downstream Stream A work blocked by Stream C | The normal app injects no provider and honestly reports contract unavailable. Fake-backed controller/UI tests pass. | Prevents Admin-to-API-to-device center integration. Add one strict adapter only after the contract lands. |
| Live center empty/results/offline/timeout/malformed and physical-device evidence | Still active; cross-stream | Provider-independent UI states are tested, but no live endpoint exists and the emulator cannot boot on this host. | Blocks complete center presentation evidence. Retest after Stream C integration on a device/emulator with adequate disk. |
| Day 4 Admin parameter mutation governance | External governance blocker; no longer applicable to Stream A/B release scope | The custom portal remains read-only for governed parameters as required by `TA_CONSULTATION_SYSTEM_DECISIONS.md`. | Does not block GPS or resolver readiness. Do not implement until scientific definitions, roles, workflow, and authority are approved. |

No blocker is classified as superseded merely to improve the verdict. No Stream
C/D logic was duplicated in mobile or geography code.

## 4. Current-worktree and clean-environment rehearsal

The active worktree began clean and reproducible from the synchronized commit.
A detached worktree at `C:\fs-day7-57aaecc` was created at the exact commit.
It contained no `.env`, virtual environment, Dart metadata, or build output.

Clean setup performed:

1. created a new Python 3.13 virtual environment;
2. installed `server/requirements.txt` successfully;
3. resolved the locked Flutter dependencies successfully;
4. verified the disposable `test_floodsense` database was owned by the local
   application role and had zero active connections;
5. removed only Django application tables from that verified test database,
   preserving PostGIS 3.6 objects;
6. applied all committed migrations from the beginning;
7. ran the approved fictional `seed_demo` only in that disposable database;
8. flushed those seed rows before reusable-database pytest execution; and
9. built the Android debug APK in the detached worktree.

The local application role has no `CREATEDB` privilege, so an already isolated,
verified test database was reused rather than creating or dropping a database.
The development database was not migrated, seeded, flushed, or otherwise
changed.

The first focused pytest invocation was invalid because the approved seed had
just populated the reusable test database. It reported 86 duplicate/contaminated
data failures, not product regressions. After `manage.py flush --noinput` on the
verified disposable database, the identical focused suite passed 145/145. This
ordering issue is recorded rather than hidden.

## 5. Backend verification

Commands ran with the newly installed clean virtual environment unless noted:

```text
python -m pip install -r server/requirements.txt
python server/manage.py migrate --plan
python server/manage.py migrate --noinput
python server/manage.py check
python server/manage.py makemigrations --check --dry-run
python server/manage.py showmigrations --plan
python server/manage.py seed_demo
python server/manage.py validate_geographic_dataset <checked-in-layer> --identity-field psgc_10_digit --expected-geometry-type MultiPolygon --expected-feature-count 47 --expected-crs EPSG:4326 --fail-on-issues
python server/manage.py flush --noinput
python -m pytest server/geography server/expert server/dss server/evacuation -q --reuse-db
python -m pytest server -q --reuse-db
ruff check server
python server/manage.py check --deploy
```

Results:

- all committed migrations applied; every migration was then shown as applied;
- Django check: no issues;
- missing-migration check: no changes detected;
- geography validation: pass, 47 MultiPolygons, no invalid/empty/null geometry,
  no missing/duplicate PSGC identity, SHA-256
  `9C3E53643039BA71E88E6ECD5F7A23BFB87980B3375E086E826EFE97AAA8F213`;
- focused backend: 145 passed, 46 warnings, 5.99 seconds (6.888 seconds
  including process overhead);
- complete backend: 257 passed, 122 warnings, 31.98 seconds (32.936 seconds
  including process overhead);
- Ruff: all checks passed;
- known warnings: Django 6 URL-field default transition and absent generated
  `staticfiles/` directory in the detached checkout; and
- deploy check under temporary non-secret production-like settings: no errors,
  but `security.W005` and `security.W021` remain because HSTS subdomains and
  preload are intentionally not enabled by default. The deployment owner must
  decide these only after every applicable domain/subdomain is HTTPS-ready.

## 6. Flutter and Android verification

- Flutter `3.47.4` stable; Dart `3.13.3`. The setup guide records Flutter
  `3.47.2`/Dart `3.13.2`; the patch-level difference caused no dependency,
  analysis, test, or build failure.
- `flutter pub get`: passed; the lockfile did not change. Ten newer packages are
  outside current dependency constraints and were not upgraded during release
  rehearsal.
- `dart format --output=none --set-exit-if-changed lib test`: passed after the
  one formatter-only correction described above; 55 files checked.
- `flutter analyze`: no issues, 6.6 seconds.
- `flutter test`: 164 passed; the combined format/analyze/test command took
  57.669 seconds.
- `flutter build apk --debug`: passed in 183.011 seconds.
- Debug artifact: `mobile/build/app/outputs/flutter-apk/app-debug.apk`,
  161,496,433 bytes, SHA-256
  `8CA8FD0A7E281406447250A7C8484D86D352D0D103BC728A485C29D27FE29EBB`.
- Build warnings: Android SDK XML version mismatch between installed tools,
  Java 8 source/target deprecation, and a future Java native-access warning.
  None failed the debug build.
- Merged manifest: Internet, coarse location, fine location, and Android's
  generated non-exported receiver permission only. There is no background
  location permission. The geolocator service is non-exported and has no
  foreground-service type. Debug-only cleartext traffic is enabled by the
  debug manifest for local development; it is not present in the main/profile
  manifests.
- No release build, production signing, upload, or publication occurred.

## 7. Emulator/device status

Available emulator profile: Google Pixel 7, Android 16/API 36, emulator
37.1.11. Its headless boot stopped before startup:

```text
FATAL | Not enough space to create userdata partition.
Available: 4244.41 MB; required: 12288.00 MB.
```

Hypervisor, system, GPU, and SDK checks passed before the storage failure. No
Day 7 emulator screenshot was captured.

A connected RMX3396 running Android 14/API 34 was then used for a targeted
manual walkthrough. The tester reported that device location acquisition,
temporary-location removal after restart, the first-use Android permission
choices, permanent-denial app-settings recovery, and the other checklist items
1-6 and 8-10 behaved as expected. Checklist item 7 exposed one recovery defect:
when the device-wide location service was off, `Try again` only repeated the
disabled check while a separate button opened Location Settings. The recovery
was corrected so `Try again` opens Location Settings and performs one retry
when FloodSense resumes. The correction is covered by controller, widget, and
lifecycle regression tests; a final physical-device retest of that corrected
item remains required. No precise coordinate or identifying screenshot was
retained as evidence.

## 8. End-to-end scenario matrix

All automated inputs are synthetic fixtures or pending-validation reference
geometry; no team member's real location was used.

| # | Method and input | Expected / actual result | Status and evidence |
| --- | --- | --- | --- |
| 1 | Mobile controller/widget fakes plus resolver API tests; synthetic covered point | Purpose precedes permission; one point resolves; confirmation is explicit; no automatic assessment. Actual matched. | **Pass (automated)** — `location_day2_test.dart`, `location_day3_test.dart`, `test_day2_barangay_resolver.py`. Emulator blocked. |
| 2 | Permission-denied widget test followed by synthetic manual pin | No prompt loop; manual location works; scenario selection remains. Actual matched. | **Pass (automated)** — `location_day2_test.dart`, `location_day4_centers_test.dart`. Emulator blocked. |
| 3 | Permanent-denial controller/widget fixture | Settings guidance appears; settings opens only after a tap; manual fallback remains. Actual matched. | **Pass (automated)** — `location_day2_test.dart`. Emulator blocked. |
| 4 | Service-disabled location fixture | Safe disabled state, no crash/re-prompt, manual fallback. Actual matched. | **Pass (automated)** — `geolocator_location_service_test.dart`, `location_day2_test.dart`. Emulator blocked. |
| 5 | Resolver point outside synthetic City geometry | No forced barangay/classification; outside state and correction path remain. Actual matched. | **Pass (automated)** — `test_day2_barangay_resolver.py`, `location_day3_test.dart`. Emulator blocked. |
| 6 | Shared polygon boundary/vertex fixtures | No arbitrary polygon; ambiguous response and manual confirmation. Actual matched. | **Pass (automated)** — Day 2-4 geography tests and `location_day3_test.dart`. Emulator blocked. |
| 7 | Empty fake center provider after confirmed location | Honest empty message says unavailable data does not mean no real centers exist; assessment unchanged. Actual matched in provider-independent UI. | **Blocked live E2E** — widget behavior passes, but no Stream C endpoint can prove a real safe empty response. |
| 8 | Several validated fake center presentation records | Cards retain provider order and show approximate straight-line distance, verification/source/limitations, with no route claim. Actual matched in UI. | **Blocked live E2E** — UI test passes; authoritative backend ordering/distance does not exist. |
| 9 | Read-only inspection of evacuation model, URLs, and tests | Draft/restricted/inactive/unverified records must never reach residents. There is no resident API with an eligibility policy to execute. | **Blocked** — Programmer 2 must implement and prove Stream C filtering. Admin workflow tests are not a substitute. |
| 10 | Typed offline/timeout/server/malformed fakes, delayed requests, explicit retry | Safe errors, no coordinate echo, selections retained, no duplicate request or repeated permission. Actual matched. | **Pass (automated)** — `location_day4_centers_test.dart`, `location_day5_hardening_test.dart`. Live center endpoint remains blocked. |
| 11 | Dispose/reset/new-controller tests plus physical app restart | Coordinate and marker do not survive a new controller or restart; canonical boundaries remain ordinary reference data. Actual matched. | **Pass (automated and targeted physical check)** — `location_foundation_test.dart`, `location_day2_test.dart`; tester confirmed the temporary current location was removed after restart. |
| 12 | Assessment, resolver, center-failure, and Expert System regression tests | Scenario-based classification only; GPS/center lookup cannot alter output; unsupported data remains insufficient. Actual matched. | **Pass (automated)** — mobile controller tests plus full expert/DSS/backend suites. Emulator blocked. |

For a future device walkthrough: free at least 12.288 GB plus build headroom,
boot `Pixel_7`, start the local backend, install the debug APK, use Android
Extended Controls to inject only approved test coordinates, clear app data
between fresh-start scenarios, and capture only redacted screens without
coordinates, private contact data, secrets, or restricted/provisional claims.

## 9. Privacy and security conclusion

- Precise user coordinates remain controller/request-local. No assessment,
  profile, analytics, audit, or location-history model field stores them.
  Canonical administrative and evacuation-center coordinates are reference
  data and are not user-location history.
- Resolver requests use JSON POST bodies, not URL query strings. Tests prove
  select-only behavior and no audit write. Errors do not echo the submitted
  coordinate.
- No repository middleware logs request bodies. External reverse-proxy/APM
  logging remains a deployment-owner verification item.
- Mobile code has no persistence package, coordinate serialization, continuous
  position stream, timer, background permission, boot receiver, or location
  foreground-service capability.
- Resolver responses are allowlisted and contain no susceptibility, geometry,
  rule, private provenance, or internal-note field.
- The resident nearest-center safe-field and eligibility guarantees remain
  unproven because the Stream C API is absent.
- Raw Expert System controls remain outside the ordinary custom portal; full
  backend tests preserve inference/guidance/location separation.
- Tracked-file checks found no `.env`, APK/AAB, database dump, private-key
  marker, common cloud/API token pattern, or staged generated artifact.

## 10. Deployment-readiness handoff

No deployment occurred. Required environment names (never their values) are:

```text
DJANGO_DEBUG
DJANGO_SECRET_KEY
DJANGO_ALLOWED_HOSTS
DJANGO_SECURE_SSL_REDIRECT
DJANGO_SECURE_HSTS_SECONDS
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS
DJANGO_SECURE_HSTS_PRELOAD
FLOODSENSE_GIS_ENABLED
DATABASE_URL (optional alternative)
DATABASE_NAME
DATABASE_USER
DATABASE_PASSWORD
DATABASE_HOST
DATABASE_PORT
GDAL_LIBRARY_PATH
GEOS_LIBRARY_PATH
```

The deployment owner must install pinned-compatible Python/Flutter/Android
dependencies, provide PostgreSQL with PostGIS, set exact allowed hosts, terminate
or correctly proxy HTTPS, review HSTS subdomain/preload policy, run
`collectstatic --noinput`, and keep tests on a separate PostGIS database.
Before a shared migration, take and verify a recoverable database backup,
review `migrate --plan`, schedule one migration owner, apply committed
migrations, run checks, and verify service health. Rollback must restore the
matched application/database backup or use a specifically reviewed reversible
migration; do not fake or rewrite migration history.

There is currently no reviewed authorized production center import. Programmer
2 and the data/governance owners must implement and approve one before real
center output can exist. Never run `seed_demo`, fictional fixtures, provisional
MGB imports, or unreviewed agency imports in production.

The Android project still uses debug signing in its placeholder `release`
build type. Day 7 deliberately built only debug. Production signing and release
hardening remain deployment-owner work and must not reuse debug credentials.

## 11. Thesis/manuscript evidence handoff

Statements supported by current code and tests:

- GPS is foreground-only and user-triggered.
- Precise user coordinates are temporary.
- Barangay boundaries remain pending validation and are not City-verified.
- Barangay detection is administrative identification, not susceptibility
  classification.
- Center distance is intended to be approximate straight-line distance, not a
  safe route; live distance remains blocked on Stream C.
- FloodSense is not a safe-routing, official warning, dispatch, monitoring, or
  forecasting service.
- Center availability and capacity are not live.
- Unsupported scientific data produces an honest unavailable or insufficient-
  data state.

Safe evidence available for the manuscript member includes 257 passing backend
tests, 167 passing Flutter tests, the migration/validation results, Android
toolchain and AVD details, merged-manifest findings, the resolver API contract,
the Day 6 measurements, the targeted physical-device observations above, and
the blocker table. No Day 7 screenshot is retained or claimed. Do not present
fake center cards as evidence of a live resident API or show an Admin workflow
as proof of resident eligibility filtering.

## 12. Files and database changes

Day 7 and physical-walkthrough follow-up changes:

- Mobile test formatting only:
  `mobile/test/location_day4_centers_test.dart`.
- Evidence/documentation:
  `docs/GPS_STREAMS_A_B_DAY7_RELEASE_REHEARSAL.md`.
- Geography implementation/tests: none.
- Mobile runtime implementation: service-disabled `Try again` now owns the
  explicit Location Settings launch and one resume-time retry; the duplicate
  Location Settings button/action was removed. First-use Android permission
  behavior and permanent-denial app-settings recovery are unchanged.
- Mobile regression tests: controller and lifecycle/widget coverage for the
  consolidated recovery, duplicate-tap suppression, one-shot resume, and
  failed settings launch.
- Models and migrations: none.

Disposable database operations: verified owner/connections; removed only test
application tables; reapplied committed migrations; ran the approved fictional
seed; validated the checked-in reference layer; flushed seed rows; ran focused
and complete tests. The development/shared/production databases were not
modified.

## 13. Teammate instructions

After pulling a future reviewed Day 7 commit:

```powershell
server\.venv\Scripts\python.exe -m pip install -r server\requirements.txt
server\.venv\Scripts\python.exe server\manage.py migrate --plan
server\.venv\Scripts\python.exe server\manage.py migrate
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe -m pytest server -q --reuse-db
Set-Location mobile
flutter pub get
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
flutter build apk --debug
```

Run migrations only against each teammate's authorized local database unless a
specific shared target and backup/migration owner are explicitly approved. Do
not run `seed_demo` unless fictional local demonstration data is intentionally
required. Do not import official, restricted, DOST, MGB, boundary, or center
data without target-specific authorization and the applicable reviewed import
workflow.

Remaining manual work is a physical-device retest of the corrected checklist
item 7 and any release-evidence screenshots the team chooses to capture safely.
Live center scenarios must wait for Programmer 2's frozen contract, eligibility
service, endpoint, shared URL registration, and integration tests.

## 14. Final repository state

- Branch: `main`, tracking `origin/main`.
- Modified tracked files: the formatter-only center test correction plus the
  location controller, card, state/copy, and Day 2 regression-test follow-up.
- Staged files: none.
- Untracked files: this Day 7 evidence report.
- Conflicts: none.
- The retained debug APK and normal dependency/build directories are ignored
  generated artifacts and are not staged or tracked.
- The detached rehearsal worktree and its temporary virtual environment/build
  tree were removed after the clean APK was copied to the active ignored build
  directory. The isolated `test_floodsense` database remains available for
  local tests with its seed data flushed.
