# GPS Streams C/D Day 2 implementation report

**Updated:** 21 September 2026. **Owner:** Team B. **Scope:** Day 2 only.

**Status: Stream C and Stream D Day 2 complete; browser checks confirmed by the user.**

For a repeatable hands-on walkthrough, use the
[Days 1–2 manual test guide](GPS_STREAM_C_D_DAYS_1_2_MANUAL_TEST_GUIDE.md).

The UUID migration, internal nearest-center service, and targeted Admin changes
are written. Database-backed distance, eligibility, migration, UUID lifecycle,
no-write, and permission-regression tests now pass. On 21 September 2026, the
user confirmed all checks in the supplied browser accessibility/layout checklist
passed. This closes the remaining Day 2 verification item. No public endpoint
or mobile integration exists.

## Preserved Day 1 work

Started on `main` at `57aaecce1c6eea9a8732bc5b41b9c63769f07cd1`, with the eight
intentional Day 1 files already modified/untracked. No commit, pull, push,
rebase, reset, or branch switch was performed. The Day 1 contract suite passed
153 tests before editing. Frozen constants, serializers, contract tests, and
`NEAREST_CENTER_CONTRACT.md` remain byte-for-byte unchanged. Day 1 baseline and
privacy reports are preserved as historical evidence; plan/blocker edits are
incremental status updates.

## Files and scope

Stream C changes:

- `server/evacuation/models.py`: non-editable unique UUID default.
- `server/evacuation/admin.py`: public UUID displayed read-only in technical Admin.
- `server/evacuation/migrations/0002_evacuationcenter_public_id.py`: staged backfill.
- `server/evacuation/services.py`: internal reference gate, candidate selector,
  guarded PostGIS distance, and explicit validated response assembly.
- `server/evacuation/test_day2_nearest_service.py`: 84 test cases.
- `server/evacuation/test_day2_public_id_migration.py`: four database-backed tests.

Stream D changes:

- `server/admin_portal/templates/admin_portal/evacuation_center_list.html`,
  `evacuation_center_detail.html`, `evacuation_center_form.html`, and
  `evacuation_transition_confirm.html`.
- Shared template includes `center_safety.html`, `form_error_summary.html`, and
  `operation_field.html` under `templates/admin_portal/includes/`.
- `templates/admin_portal/base.html`: skip link, focusable main landmark, and
  navigation/sign-out fallback when JavaScript is disabled.
- `static/admin_portal/css/operations.css`, `admin_portal.css`, and new
  `no_script.css`: visible input focus, long-content wrapping, narrow-screen
  safeguards, and hidden-drawer focus exclusion.
- `server/admin_portal/test_gps_day2_admin.py`: 13 focused test cases.
- This guide and the GPS plan/blocker documents.

No changes to mobile, Geography, Expert System, DSS classification, scientific
parameters, datasets, dependencies, public routes, or shared settings. Existing
Admin verification/source workflows and permission decisions are unchanged.

## Public UUID migration

`evacuation.0002_evacuationcenter_public_id` depends on `0001_initial`:

1. Add nullable `public_id` without a shared static default.
2. Use the historical model and `schema_editor.connection.alias` to backfill a
   separate `uuid.uuid4()` for each existing row lacking an identifier.
3. Enforce `null=False`, `unique=True`, `editable=False`, and callable
   `default=uuid.uuid4` for future rows.

The operations were manually reviewed. The migration does not create/delete
centers, rewrite `0001_initial`, change legacy fields, or derive identifiers
from data. Lookup maps this field to the frozen **`public_identifier`** key.
Ordinary edits and workflow code leave the UUID untouched; tests cover every
verification transition, uniqueness, non-null values, and legacy preservation.

Reversal drops only the new field and keeps centers/source data. It necessarily
loses UUID assignments: do not reverse after clients depend on public IDs without
a separately reviewed recovery plan. Keep the schema change/backfill atomic on
PostgreSQL and coordinate application writers during rollout. Migration upgrade,
reversal, and lifecycle tests now pass in the isolated test database. The
local application database now reports `0002_evacuationcenter_public_id` applied,
confirmed by a read-only `showmigrations evacuation` check on 21 September.

## Service contract and eligibility

Future view entry point:

```python
find_nearest_eligible_centers(*, latitude: float, longitude: float, limit: int = DEFAULT_LIMIT) -> dict
```

The service validates inputs with the unchanged Day 1 request serializer before
SQL: finite JSON numeric WGS 84 coordinates, integer limit 1–10, default 3.
It returns a JSON-ready mapping, not models. Invalid caller inputs raise DRF
validation errors; unexpected database failures propagate to the future Day 3
generic error boundary. There is no logging or empty-success exception catch.

`ready_reference_barangays()` requires one eligible reserved agency reference
source, one enabled pending-validation City with the reserved code and source,
and exactly 47 eligible barangays selected through Geography's existing helper.
It verifies non-empty valid geometry, City coverage of each barangay, distinct
ten-ASCII-digit PSGC codes from `public_psgc_code()`, and distinct nonblank names
after trimming/case folding. Invalid geometry is guarded before the City
relationship calculation. Missing/duplicate sources, wrong status/type/source,
disabled rows, bad identities, empty/invalid geometry, or wrong counts fail
closed to the frozen empty envelope. No guessed identity or coordinate-derived
center association is added. No reference status is promoted to approved.

`eligible_center_candidates()` filters verified + approved centers, verification
date and UUID present, finite-range numeric coordinates, and membership in the
ready barangay set. It also checks current area enabled/status/type and reserved
source gates in the candidate query. Center sources must be approved, publicly
releasable, and not demonstration. Draft, in-review, inactive, demonstration,
pending, restricted, retired, missing-area, City/demo/unrelated/disabled-area,
unapproved-source, and non-public-source records cannot qualify.

Nonblank name/address/organization, valid UUID/date/PSGC, valid coordinates,
and literal public text/caveats are enforced by the frozen response schema.
Malformed public data excludes that row before it consumes the final limit.
Database non-null/UUID/uniqueness constraints also prevent missing/malformed
UUIDs in the final schema; mapping guards cover impossible/legacy values.

Eligibility is reevaluated on every call, without a status cache. This is not
an institutional content review or a guarantee about concurrent changes after
a database read. Administrators/data owners must still authorize the public
fields and material limitations. No new Admin approval authority was invented.

## Distance, ordering, limits, and mapping

The ORM builds parameterized `ST_MakePoint(longitude, latitude)`, sets SRID 4326,
casts to transient geography, then uses `ST_Distance(..., true)` for spheroidal
meters. A `CASE` guards point construction with inclusive numeric bounds; this
also excludes PostgreSQL numeric NaN/infinity, avoiding geography normalization
of malformed coordinates. User values are bound parameters, verified by the
database-independent SQL compilation test. No stored Point field or routing
dependency is introduced.

Candidates are ordered by unrounded distance, then `public_id` ascending.
Safe mapping rejects invalid rows while scanning that ordered result; only then
does the service stop at the requested count. Thus many invalid nearby rows
cannot hide valid later rows. Distances are rounded with `round(value, 1)` only
after selection. The final envelope is validated through
`NearestCenterResponseSerializer` and returned as `.data`.

The values projection fetches only public mapping data and the required join
identity. It does not fetch contacts, capacity, notes, permitted-use text,
reviewer identity, audit records, users, or Expert System data. Limitations are
assembled as center-verification notice, boundary warning, administrative-boundary
limitation, optional trimmed center limitation, then source limitation, with
exact duplicate removal preserving order. Invalid optional caveats exclude the
row rather than silently removing a material restriction. Text is literal;
clients must escape it, not execute markup.

An empty inventory, missing reference readiness, or no safely eligible rows
returns the exact Day 1 `centers: []`, method and two-warning envelope. It does
not claim no facilities exist. The response never echoes the user coordinate;
facility coordinates remain public center fields. Boundary caveats accompany
all populated results. Empty wording is unchanged by design.

Implementation targets four SELECT queries for a ready layer: source, City,
barangay identities, and ordered candidates. Invalid references can stop earlier.
There is no per-row related fetch. The ORM currently materializes the eligible
candidate projection to allow text-schema rejection before the final limit;
result count is bounded, but candidate memory/work is not capped by that limit.
Measure actual inventories in the later performance work before adding an index
or reviewed batching strategy. Bounded-query tests now pass against PostGIS.

## No-write evidence and limits

Static inspection shows only SELECT querysets, transient expressions, and pure
serializers. No save/create/update/delete, maintenance event, session write,
cache, analytics, or location-history API is called by the service.

The database-backed tests capture SQL and snapshot all fields/counts of centers,
sources, areas, sessions, and `LogEntry` before/after repeated lookups. They also
check query-count stability as inventory grows, public projection exclusions,
non-echoed synthetic input, and absence of deliberate application logging.
**These service no-write tests now pass against PostGIS.** Framework
debug/SQL logging and deployed proxy/APM/privacy concerns remain the separate
Day 1 privacy-review follow-ups. Local test results are not deployment proof.

## Admin review and changes

Reviewed center list/detail/create/edit/confirmation, source forms and approval,
Settings, rainfall list/detail, map-data, dashboard navigation, base landmarks,
focus CSS, and map fallback code. Settings already explains the governance gate
and is read-only; rainfall pages already distinguish scenarios from live data.
Map-data already labels administrative boundaries, provisional layers and
JavaScript-disabled behavior. Those modules' scientific/workflow behavior was
preserved rather than rewritten.

Center pages now explain that verified does not mean open, reachable, safe, or
guaranteed space. Public eligibility also needs release permission, publication,
safe fields and supported identity. Boundary association is not susceptibility,
and straight-line distance is not a route-safety recommendation. The list still
states that the module exposes no resident API.

The detail page shows a wrapping read-only UUID, source approval, and public
release state. UUID is not a token or create/edit control; existing Admin routes
still use internal IDs. Form errors have a visible linked summary, field labels,
and matching error/help IDs. Filter errors are visible; filtered empty results
offer clearing filters without claiming no facilities exist. Table headers have
scope and a caption. Source and long metadata remain escaped text.

The shell has a keyboard skip link and a focusable main target. Mobile drawer
links are hidden from focus while closed. A noscript stylesheet keeps navigation
available on narrow screens and offers server-side sign-out. Interactive controls
have explicit focus outlines; long text/UUIDs wrap, selects are width-constrained,
and the existing 420px single-column table fallback is retained. Existing map
library-unavailable text remains visible without JavaScript.

Nine database-independent Admin template tests pass. The earlier agent session
rendered synthetic static snapshots but had no connected browser. The user then
performed the supplied manual checklist and reported on 21 September 2026:
"All passed. It works completely and normally."

The checklist covered desktop/320px layouts, long content, navigation, keyboard
focus and skip links, form errors, screen-reader labels, JavaScript-disabled/map
fallbacks, empty/signed-out states, and safety copy. These manual results are
user-reported, not agent-observed. Browser/version details and screenshots were
not supplied; no specific browser or assistive-technology version is claimed.

## Verification results

All Python commands use `server\.venv\Scripts\python.exe` from repository root.
Tests use the isolated test database with `--reuse-db`. On 21 September, the
focused service suite and full backend suite were rerun after fixing the NaN
test setup. Suite counts below are covered by that successful full run.

| Command/check | Result |
| --- | --- |
| Day 1 contract suite | 153 passed, unchanged |
| Day 2 service suite | 84 passed, including both stored-NaN exclusion cases |
| Day 2 UUID/migration suite | 4 passed within the full backend run |
| New Admin suite | 13 passed within the full backend run |
| Complete Admin suite | 102 passed within the full backend run |
| Complete backend `pytest server -q --reuse-db --tb=short` | 511 passed; 127 warnings; 36.78 seconds |
| Manual browser accessibility/layout checklist | All passed, confirmed by the user on 21 September 2026 |
| Local application `showmigrations evacuation` | `0001_initial` and `0002_evacuationcenter_public_id` applied |
| Ruff check, evacuation + admin_portal | Passed |
| Ruff format check, whole evacuation directory | Three pre-existing formatting findings in untouched `apps.py`, `views.py`, `workflow.py` |
| Ruff format check, changed Python scope | Passed |
| Django system check | No issues |
| `makemigrations --check --dry-run` | No changes detected: committed-history plus new migration matches the model |
| `git diff --check` | Passed; Git reports ordinary LF/CRLF normalization notices |
| Flutter analysis `--no-pub` | Previous Day 2 baseline: no issues; not rerun for the test-only fix |
| Flutter tests `--no-pub` | Previous Day 2 baseline: 164 passed; no mobile changes or package upgrade |

The original provisioning blocker was:

```text
permission denied to create extension "postgis"
HINT: Must be superuser to create this extension.
```

This blocker is resolved. After the user provisioned the local test database,
their run reached 509 passes and two failures: Django rejected `Decimal("NaN")`
while constructing test records, before service execution. The two cases now
create a valid synthetic center, write NaN through parameterized SQL within the
isolated test transaction, assert it was stored, and verify lookup excludes it.
No production validation was weakened, no cases were skipped, and the suite
still contains 511 tests. Warnings concern Django's future URL scheme default,
package metadata deprecation, and the missing collected-static directory.

The agent's test runs exercised only test-database migration behavior. Following
the user's manual verification, a read-only check confirmed the UUID migration
is now applied in the local application database. The agent did not execute that
application migration. No credentials, privilege changes, SQLite replacement,
GIS disablement, or shared/deployed operations were needed.

## Teammate migration and verification steps

No dependency changes, seeds, or imports are needed. Each teammate needs PostGIS
enabled in their own isolated local test database before running:

```powershell
server\.venv\Scripts\python.exe -m pytest server\evacuation -q --reuse-db
server\.venv\Scripts\python.exe -m pytest server\admin_portal -q --reuse-db
server\.venv\Scripts\python.exe -m pytest server -q --reuse-db
server\.venv\Scripts\python.exe -m ruff check server\evacuation server\admin_portal
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe server\manage.py makemigrations --check --dry-run
```

Use `--reuse-db` to retain the provisioned extension; normal fresh-test creation
needs an appropriately prepared PostGIS test template/admin procedure. Never
grant the application role superuser or point tests at developer application data.

After migration tests pass and the target is confirmed as that teammate's local
development database, review and apply the pending migration before starting the
new model/Admin code:

```powershell
server\.venv\Scripts\python.exe server\manage.py migrate --plan
server\.venv\Scripts\python.exe server\manage.py migrate evacuation
server\.venv\Scripts\python.exe server\manage.py check
```

Existing center reads need the new column; do not run the changed application
against its old schema. Shared/deployed migration needs separate target-specific
authorization. Repeat visual checks at 320px and desktop, with/without JavaScript,
keyboard-only navigation, long content, form errors, and denied/empty states.

## Remaining Day 3 and later work

Day 2 verification is complete. Day 3 owns the public POST
view, JSON/media/method/internal error normalization, public permissions, URL
module/include, HTTP no-write tests, cache headers, and coordinated abuse-control
decisions. None was added here. Production mobile parser/provider/copy, live
integration, physical-device center results, and deployment privacy evidence
remain later work. Day 4 parameter-governance mutation and final adviser GPS
requirements remain independent unresolved decisions.
