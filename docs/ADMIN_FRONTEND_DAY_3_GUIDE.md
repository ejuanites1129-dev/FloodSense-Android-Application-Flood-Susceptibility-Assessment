# FloodSense Admin Frontend — Day 3

**Verified:** 18 September 2026  
**Status:** Read-only map and geographic-data review implemented, verified, and accepted by the project owner.  
**Route:** `/management/map-data/`

This guide records the team's Day 3 implementation under the current consultation
decisions and seven-day plan. It does not claim a new thesis-adviser approval or
approve any geographic dataset. Historical Day 1 and Day 2 guides remain unchanged.

## Delivered behavior

- Active staff can inspect the database's supported geographic records through
  the existing management authentication and navigation shell.
- Database-backed indicators show enabled reviewable areas, enabled barangay
  boundaries, pending-validation records, and demonstration-only areas. A scope
  note also reports total reviewable and disabled records. Zero remains zero.
- The interactive OpenLayers map fits available visible features, supports pan
  and zoom, highlights selection using a thicker neutral outline, and synchronizes
  with the searchable record list and detail panel.
- Search matches area names and geographic codes without another API request.
  No-results and empty-database messages explain what is missing.
- Administrative and demonstration features use separate vector layers. Solid
  slate outlines identify administrative geometry; dashed muted-purple outlines
  identify synthetic demonstration areas. Neither style encodes flood risk.
- Layer switches affect only the review page. Administrative boundaries are
  initially visible when present. Demonstration geometry starts hidden alongside
  administrative data, except when a demonstration record was explicitly selected;
  it is initially visible when it is the only available category. Selecting a
  displayable record enables its layer. Disabled records remain inspectable but
  are never included in map features.
- The detail panel includes area name/code/type, geometry type and spatial
  reference, record/source status, enabled state, source name/organization/type,
  coverage, period start/end, source review date/reviewer display name, record
  update timestamp, source release permission, and fixed safety limitations.
- Missing metadata says **Not recorded**. Version says **Not recorded in the
  current data model**. Dates, primary keys, and filenames are not versions.
- Responsive panels stack at narrower widths. Inputs have labels, interactive
  actions use native controls, records show Selected text and `aria-pressed`,
  focus outlines remain visible, and selection is announced in a polite live
  region. Tab/Enter/Space select records; Up/Down/Home/End navigate the list.
- Without JavaScript, the summary and list still render and native GET form
  buttons load selected-record details. With the mapping library unavailable,
  client-side search/selection still work. Tile failures show a readable warning
  while vector geometry and details remain usable.

## Routes and implementation files

| File | Responsibility |
| --- | --- |
| `server/admin_portal/services/map_data.py` | Eligibility, two-query summary, safe records and separate GeoJSON collections |
| `server/admin_portal/views.py` | Staff-only, GET-only `map_data` view; removes obsolete placeholder metadata |
| `server/admin_portal/urls.py` | Explicit `map-data/` route before the generic section route |
| `server/admin_portal/templates/admin_portal/map_data.html` | Summary, map, layer controls, server-rendered list/details, safe JSON payload |
| `server/admin_portal/static/admin_portal/js/map_data.js` | Progressive enhancement, search, selection, layers, map and failure states |
| `server/admin_portal/static/admin_portal/css/map_data.css` | Scoped responsive geography-review styles |
| `server/admin_portal/templates/admin_portal/base.html` | Optional page-specific CSS and JavaScript blocks |
| `server/admin_portal/templates/admin_portal/dashboard.html` | Available map-review link and accurate module-readiness copy |
| `server/admin_portal/test_map_data.py` | 17 new automated tests |
| `server/admin_portal/tests.py` | Removes map data from the remaining placeholder expectations |
| `server/admin_portal/test_dashboard.py` | Dashboard links now expect a working map page |
| `docs/ADMIN_FRONTEND_DAY_3_GUIDE.md` | Implementation and verification handoff |
| `docs/ADMIN_WEB_7_DAY_IMPLEMENTATION_PLAN.md` | Verified Day 3 status and Day 4 handoff |

The named route is `admin_portal:map-data`. Existing links generated through
`admin_portal:section` with `section_slug="map-data"` still resolve to the same
URL and protected view. `?area=<record-id>` loads a permitted selection; excluded
or unknown IDs never expose the requested record. No JSON endpoint was added.

## Query scope and layer separation

The service uses one filtered aggregate and one `select_related("source",
"source__reviewed_by")` query with an explicit field allowlist. Query count remains
two as record count grows. Geometry is serialized from stored PostGIS records;
the page never reads loose GIS files or depends on an unrestricted public API.

| Category | Required persisted evidence | Presentation |
| --- | --- | --- |
| Administrative reference | `CITY` or `BARANGAY`; record `PENDING_VALIDATION`; source name exactly `BACOOR_REFERENCE_SOURCE_NAME`; source `AGENCY_DATASET`, `PENDING_VALIDATION`, publicly releasable | Derived administrative reference; not City-verified; pending validation |
| Demonstration | `DEMO_ZONE`; record and source `DEMONSTRATION`; source type `DEMONSTRATION` | Demonstration only; synthetic, not real Bacoor classifications |
| Provisional MGB susceptibility | No supported verified persisted layer representation exists | Disabled control; unavailable and not approved for operational/resident publication |
| Future approved susceptibility | No governed susceptibility-layer representation exists | Disabled control; requires supported data, formal validation, and approval |

Administrative eligibility follows the existing reference-boundary API's source
and status policy, with city records and disabled records additionally available
for staff review. Demonstration eligibility follows `provenance.policies` and
requires the explicit demonstration area type. A matching word in a source name
is insufficient. Restricted, retired, unrelated, and mismatched records/sources
are excluded from both details and counts. A generic geographic record marked
Approved does not prove a susceptibility layer exists and is not mapped here.

Counts are intentionally scoped to these two supported review categories, unlike
the dashboard's inventory of all geographic rows. Enabled and pending counts
are independent; pending and demonstration totals include disabled reviewable
records. Layer counts separately count enabled, nonempty, valid EPSG:4326 geometry.
Invalid or empty geometry remains reviewable with an explicit map limitation.

The normalized dataset expects 47 barangays and one city. That expectation is
checked in controlled import tests; it is never substituted for database counts.

## Provenance, security, and scientific boundaries

- The reserved warning and limitation come from `geography/constants.py`.
  Administrative polygons describe jurisdictional geography, not flood hazard,
  susceptibility, rainfall, or current conditions. The derived source remains
  pending and not City-verified.
- OpenStreetMap provides visual background only. Attribution remains visible
  inside the map and in a persistent link below it. It is not assessment data.
- Every request requires an authenticated active staff account. Anonymous users
  redirect to management sign-in; authenticated non-staff receive 403. Non-GET
  methods receive 405. The page has no domain-data write path.
- Django autoescaping and `json_script` protect server-rendered content and the
  embedded payload. JavaScript uses `textContent`/DOM nodes for record values,
  never untrusted HTML. Feature properties contain only record ID, name, code,
  area type, and layer kind. No classification, scores, flood colors, inference
  results, raw rules, or area facts are queried or serialized.
- Private notes, permitted-use text, source paths, credentials, and unrelated
  source records are not selected. Reviewer details expose only the recorded
  display name, never an email fallback or full user object.
- Source release permission is explicitly distinguished from approval. Enabling
  a record or toggling a map layer cannot approve or publish anything.
- No edits, drawing, uploads, deletion, imports, approvals, publication actions,
  inference changes, monitoring, polling, background jobs, alerts, or forecasts
  were added. Public geography APIs and the Flutter contract are unchanged.

## Empty local database and optional boundary import

At verification the developer database had four demonstration areas and **zero
imported administrative boundaries**. The live Flutter client confirmed this;
no administrative records were inserted into that database during Day 3.
Tests imported the 47-boundary dataset only into Django's isolated test database.

An empty database produces zero indicators, an empty area list and detail prompt,
and unavailable layer controls. Having normalized files on disk does not make
records available. No automatic import or seed runs when the page opens.

The existing `import_bacoor_boundaries` command was inspected and verified. After
explicit authorization for a developer's **local target database**, it can be run
from the repository root using:

```powershell
server\.venv\Scripts\python.exe server\manage.py import_bacoor_boundaries
```

Equivalently, from `server` with its environment activated:

```powershell
python manage.py import_bacoor_boundaries
```

It defaults to `research_data/administrative_boundaries/processed/` and reads
`bacoor_city_boundary.geojson` and `bacoor_barangay_boundaries.geojson`. It expects
one city and 47 barangays, validates multipolygons and exact union coverage,
guards reserved source/code ownership, and performs an atomic idempotent import.
It records the source and areas as pending-validation reference data. Read that
directory's governing README first. No import is required merely to use the page.
Do not run it against a shared/deployed database without explicit authorization.

## Verification results

Commands below ran using the existing Windows Python environment with functioning
GDAL/GEOS/PostGIS. Backend commands were run from the repository root; Flutter
commands were run from `mobile` using the installed Flutter executable.

| Command | Result |
| --- | --- |
| `git status --short --branch` before changes | Clean `main` working tree; no existing edits overwritten |
| `server/.venv/Scripts/python.exe -m pytest -q --reuse-db` before changes | 124 passed baseline |
| `server/.venv/Scripts/ruff.exe check server/admin_portal` | Passed |
| `server/.venv/Scripts/python.exe server/manage.py check` | No issues |
| `server/.venv/Scripts/python.exe server/manage.py makemigrations --check --dry-run` | No changes detected |
| `server/.venv/Scripts/python.exe -m pytest server/admin_portal server/geography -q --reuse-db` | 70 passed |
| `server/.venv/Scripts/python.exe -m pytest -q --reuse-db` after implementation | 141 passed |
| `server/.venv/Scripts/python.exe -m pytest server/admin_portal/test_map_data.py -q --reuse-db` before the guided walkthrough | 17 passed again |
| `server/.venv/Scripts/ruff.exe check server --output-format concise` | Three pre-existing `I001` findings in unchanged geography files |
| `server/.venv/Scripts/ruff.exe check . --output-format concise` | Same three findings plus 23 pre-existing findings in unchanged `scripts/regenerate_design_assets.py` |
| `git diff --check` | No whitespace errors |
| `flutter analyze` | No issues |
| `flutter test` | 91 passed |
| `flutter build apk --debug` | Built `mobile/build/app/outputs/flutter-apk/app-debug.apk` |

The 17 new tests cover anonymous/non-staff/inactive-staff rejection, active-staff
and empty rendering, database counts, exact category/source eligibility, exclusion
of restricted/unrelated data, separate demonstration geometry, valid neutral
GeoJSON, metadata/version truthfulness, safe reviewer fallback, excluded selection,
disabled/empty geometry, HTML/JSON escaping, fixed two-query behavior, GET-only
access, absence of writes/imports, and the controlled 47-barangay import. Existing
dashboard, authentication, geography/reference-boundary, API, and inference tests
remain in the passing full suite.

Additional local acceptance tooling (ignored, not required application dependencies):

- `server/.venv/Scripts/python.exe -m pytest tmp/day3_visual_check.py -q -s --reuse-db --tb=short`:
  **2 browser scenarios passed**, empty and populated, against an isolated live
  test server with 47 imported barangays, one city, and synthetic fixtures.
  Headless installed Chrome and existing temporary Playwright tooling were used.
- With `server/.venv/Scripts/python.exe server/manage.py runserver 127.0.0.1:8000 --noreload`
  running locally, `flutter test .dart_tool/day2_live_backend_test.dart --reporter expanded`
  passed **1 live API-client check**. It reused the existing ignored integration
  harness: 5 intensity options, 5 duration options, 4 demonstration areas, and 0
  administrative boundaries; map assessment, detailed assessment, and temporary
  point responses parsed through the real Flutter client without data writes.

Browser interaction checks and visual inspection covered 1440, 1024, 820, 390,
and 320-pixel widths; no horizontal overflow after layout; readable long database
values; dashboard/mobile navigation; selected map/list/detail agreement; fit,
keyboard pan/zoom, list arrow navigation and Enter selection; focus outlines;
search/code matches and no-results; layer toggles; disabled records; visible OSM
attribution; neutral administrative styles and safety warnings; JavaScript-disabled
GET selection; mapping-library failure; blocked basemap tiles; and safe dynamic
rendering of HTML-like source text. Checks used reduced-motion preference.

Locally captured screenshots are under ignored `tmp/day3-validation/`, including
`map-populated-1440.png`, `map-populated-390.png`, `map-empty-320.png`,
`map-long-names-320.png`, and `map-nojs-populated.png`. They contain isolated QA
records, not the developer's private application data. Desktop/mobile and fallback
captures were visually inspected. No Android emulator or physical-device UI test
was performed; Flutter coverage is analysis, tests, APK build, and live API-client
integration. No screen-reader or full cross-browser audit is claimed. The temporary
Django development server was stopped after verification; port 8000 was confirmed
to have no listener.

Existing warnings remained: the development `server/staticfiles/` directory is
absent during tests; Python emits an importlib metadata deprecation; the Android
build reports Java native-access and SDK XML compatibility warnings. These did
not fail the recorded tests/build. Repository-wide lint is not clean; the unchanged
geography findings are in `views.py`, `test_reference_boundaries.py`, and
`management/commands/import_bacoor_boundaries.py`. Unrelated files were preserved.

## User walkthrough and acceptance — 18 September 2026

After the guided Day 3 walkthrough, the project owner reported:
**"Everything works perfectly."** This records user-reported acceptance of the
implemented module. It does not approve the underlying datasets or establish
official susceptibility classifications.

Before that walkthrough, Django started with no system-check issues, all 17
focused Day 3 tests passed again, the live map URL redirected anonymous visitors
to management sign-in, and both page-specific JavaScript and CSS returned HTTP
200. A read-only query confirmed the following local review counts:

| Indicator | Local value at the walkthrough |
| --- | ---: |
| Total reviewable records | 4 |
| Enabled reviewable areas | 4 |
| Enabled administrative barangay boundaries | 0 |
| Pending-validation records | 0 |
| Demonstration-only areas | 4 |
| Disabled records | 0 |

The walkthrough covered:

1. Staff sign-in and the administrative-reference safety notice.
2. Map pan/zoom, **Fit visible layers**, demonstration outlines, and OSM attribution.
3. Selection from the list and map, including the selected state and updated details.
4. Name/code search, no-results feedback, and clearing the search.
5. Demonstration visibility controls, unchanged database counts, and unavailable
   administrative/MGB/approved susceptibility controls in the current local state.
6. Source, status, enabled-state, limitation, and truthful missing-version details.
7. Keyboard focus, arrow navigation, and Enter/Space selection.
8. Responsive layouts at 390 and 320 pixels, with mobile menu navigation.
9. Dashboard-to-map navigation and anonymous access in an Incognito/InPrivate window.

These manual steps used the four existing demonstration areas. The 47-barangay
dataset remained unimported in the application database; its populated display
was verified separately in isolated automated/browser tests. The owner's broad
acceptance is recorded as reported, rather than a new independent observation of
every browser action. The documentation update itself did not rerun the complete
backend/Flutter suites or change application code, data, dependencies, or migrations.

## Teammate handoff

**No model change, migration, new runtime dependency, seed, or mandatory import.**
The page reuses pinned OpenLayers **10.8.0** through the existing
`geography.widgets.OPENLAYERS_CDN_ROOT`, plus OSM tiles. These external resources
need network access for the full map; records remain usable when they fail.

In the already configured environment, teammates can run:

```powershell
server\.venv\Scripts\ruff.exe check server/admin_portal
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe server\manage.py makemigrations --check --dry-run
server\.venv\Scripts\python.exe -m pytest server/admin_portal server/geography -q --reuse-db
server\.venv\Scripts\python.exe -m pytest -q --reuse-db
server\.venv\Scripts\python.exe server\manage.py runserver 127.0.0.1:8000
```

Open `http://127.0.0.1:8000/management/map-data/` with an existing active staff
account. Compare counts with that teammate's local database. Local rows/accounts
are not synchronized by Git. No pull, push, commit, shared migration, or actual
application-database import was performed during this task.

For manual acceptance, search a name and code, try a nonexistent name, select
from both the map and list, toggle each available layer, inspect source/status
details, and repeat at phone width and using the keyboard. Check the honest
empty state when boundaries are absent. Turn JavaScript off and select a record
to confirm GET fallback. Do not create/import data just to make indicators nonzero.

## Deferred work

- Governed dataset versions need an agreed schema and review workflow; no field
  or migration was added merely to imitate the mockup.
- MGB processing/persistence/validation and approved susceptibility-layer support
  require separate authorization and design. Their disabled controls do not
  constitute implemented publication workflows.
- Geographic editing, approval, publication, source management, and full audit
  history remain outside this read-only phase. No read access is misrepresented
  as an audited administrative change.
- The current small supported dataset is loaded in one page. Larger datasets
  may later need pagination or a protected spatial endpoint.
- Full accessibility, broader browser/device coverage, and dependency/static
  asset deployment review remain part of Day 7 integration work.
