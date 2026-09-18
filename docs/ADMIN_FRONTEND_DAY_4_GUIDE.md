# FloodSense Admin Web — Day 4 Settings guide

Updated: 18 September 2026.

Status: **In progress—awaiting governance decisions.** The read-only Settings
foundation is implemented. Day 4's governed mutation workflow is not complete.

## Governance checkpoint

The Day 4 implementation prompt explicitly requires: “Stop and request explicit
approval before creating the governance migration or mutation endpoints.”
The existing model cannot safely represent authorized definitions, immutable
parameter revisions, approval ownership, activation, rollback, or custom audit
events. Existing scenario options are not automatically authorized for editing.

The concrete design and team decisions are in
[ADMIN_DAY_4_PARAMETER_GOVERNANCE_PROPOSAL.md](ADMIN_DAY_4_PARAMETER_GOVERNANCE_PROPOSAL.md).
That document is a proposal, not an approved schema or a claim of adviser approval.
The active implementation plan records this checkpoint and keeps Days 1–3 complete.
Historical day guides were not rewritten.

## Implemented features

- Staff-protected Settings replaces the generic placeholder, with grouped
  navigation to overview, account, methodology/versions, assessment references,
  and data exchange.
- The profile shows only the signed-in staff member's display name and email.
  No staff/superuser flags, permissions, groups, password data, or resident fields
  are exposed by the page.
- The method summary explains fixed deterministic rule-based, user-triggered
  scenario assessment with stored inputs subject to source policies. No raw
  rules, conditions, priorities, protected rationale, or authoring links appear.
- Active knowledge-set metadata comes from permitted database `RuleSet` records,
  separately for demonstration and approved/official modes.
- Existing `ScenarioOption` records are a read-only reference inventory. Cards
  show label, code, category, recorded minimum/maximum/derived value, unit,
  publication status, enabled state, display order, source-policy mode, and a
  safe source summary. Zero stays zero; missing values say “Not recorded.”
- Case-insensitive label/code search and category filtering use a native GET
  form. Invalid filters show a linked error summary and field errors; filters
  are not applied, and all reviewable references remain visible.
- Counts reflect the reviewable database inventory. Empty groups, an empty
  inventory, no matching records, and unavailable active versions have distinct
  messages. No source records or scenario values are fabricated.
- Data exchange honestly states that direction, formats, schema, permissions,
  source restrictions, and validation rules are awaiting confirmation.
- The sidebar, account menu, and dashboard reach Settings. Existing assessment
  links remain compatible through the protected redirect.
- Responsive cards wrap long values and stack on narrow screens. Labels,
  keyboard focus, native buttons/links, textual status badges, and announced
  filter results support accessibility. The Settings content and filter form
  work without JavaScript; shared portal navigation retains its existing script.

## Routes

| Route | Behavior |
| --- | --- |
| `/management/settings/` | Canonical staff-only GET Settings page; named `admin_portal:settings` |
| `/management/settings/#parameters` | Inventory section |
| `/management/assessment-parameters/` | Staff-only GET redirect to Settings `#parameters`; named `admin_portal:assessment-parameters` |
| Existing `admin_portal:section` names for those slugs | Reverse to the same compatible URLs; explicit routes resolve first |

Both Settings routes redirect anonymous visitors to portal login and reject
authenticated non-staff/inactive staff. Non-GET methods are rejected. No new
JSON endpoint, write form, download, upload, or preview endpoint exists.
The existing POST sign-out form in the shared shell remains unchanged.

## Files created or modified

| File | Change |
| --- | --- |
| `server/admin_portal/services/settings_data.py` | Three-query, allowlisted Settings context and per-mode active-version checks |
| `server/admin_portal/forms.py` | Server-validated GET inventory filters |
| `server/admin_portal/views.py` | Settings view, protected legacy redirect, Settings sidebar entry |
| `server/admin_portal/urls.py` | Explicit canonical and compatibility routes |
| `server/admin_portal/templates/admin_portal/settings.html` | Server-rendered sections, inventory, safe metadata, warnings and empty states |
| `server/admin_portal/static/admin_portal/css/settings.css` | Scoped responsive layout, value wrapping, visible focus |
| `server/admin_portal/templates/admin_portal/base.html` | Account-menu link to canonical Settings |
| `server/admin_portal/templates/admin_portal/dashboard.html` | Available reference-inventory quick action and accurate availability copy |
| `server/admin_portal/test_settings.py` | 22 focused Settings boundary and integration tests |
| `server/admin_portal/test_dashboard.py` | Updated dashboard link assertions |
| `server/admin_portal/tests.py` | Only still-planned modules expected to be placeholders |
| `docs/ADMIN_DAY_4_PARAMETER_GOVERNANCE_PROPOSAL.md` | Proposed definitions, immutable revisions, permissions, workflow, activation, audit and preview |
| `docs/ADMIN_FRONTEND_DAY_4_GUIDE.md` | This implementation and verification handoff |
| `docs/ADMIN_WEB_7_DAY_IMPLEMENTATION_PLAN.md` | Day 4 checkpoint status and remaining approval gate |

## Query policy and separation

The service performs three SELECT queries: grouped active-record counts by mode,
permitted active metadata joined to its source, and reviewable scenario options
joined to their sources. `select_related` avoids per-record queries; `.only()`
limits selected columns. Templates receive explicit dictionaries, not arbitrary
model objects. Tests verify constant query count with a larger fixture inventory
and verify that private source fields and raw rule tables are not queried.

An inventory row must have record and source status in demonstration, pending
validation, or approved. It must also have a publicly releasable source, **or**
be an explicitly permitted demonstration record with a demonstration source and
status. Restricted and retired records/sources, and other non-public sources,
are withheld. The three visible groups are:

1. **Demonstration only:** any explicit demonstration marker on the record or
   source keeps it out of the approved group. Mismatched records retain their
   actual status and show no eligible mode where source policy fails.
2. **Approved source-backed references:** the existing official-mode policy
   permits the record. This does not authorize editing or guarantee that all
   other inputs for a scenario are available.
3. **Pending or inconsistent references:** the remaining reviewable references;
   they are not eligible for official assessment use.

Enabled state is shown separately from approval and source eligibility. Filters
are applied in memory to this small reference inventory; totals describe all
reviewable rows, while the matching count describes the current filter. The
page does not enumerate withheld names, source notes, permitted-use text, or
unrelated provenance records. Pagination may be needed if the inventory grows.

## Methodology and versions

The existing database uniqueness constraint is one active `RuleSet` **per mode**.
A permitted active demonstration set and a permitted active official set may
coexist without being reported as duplicate active records.

For each mode, display metadata only when exactly one active record exists,
exactly one permitted record matches, and its name and version are recorded.
Missing active records produce an empty state. Conflicting counts, missing
version/name, mismatched status/source/mode, or restricted metadata produce an
unavailable warning without the record's private name/version. Unknown active
modes get a generic warning. The multiple-active fallback is tested with
synthetic service inputs without disabling the actual uniqueness constraint.

Displayed metadata includes name, recorded version, mode, publication status,
effective date, active state, source name/organization/type/status, and source
release flag. A missing effective date says “Not recorded.” Effective dates
do not schedule activation. The knowledge-set version is not the software
algorithm version, nor a revision of scenario inputs.

`ScenarioOption` still has no governed revision, rationale, or effective-date
fields. Settings states this gap explicitly rather than treating modification
times or IDs as versions.

## Actual permissions, workflow, audit, and preview

| Capability | Implemented at this checkpoint |
| --- | --- |
| Read permitted Settings metadata and own profile | Active authenticated staff; existing portal guard |
| Propose / validate / review / approve | Unavailable; definitions and named authority assignments pending |
| Activate / retire / roll back | Unavailable; no pointer or revision schema yet |
| Account preference updates | Unavailable; own profile is read-only |
| Demonstration effect preview | Unavailable; no safe override boundary introduced |
| Custom parameter audit events | No mutations and no new event model; not fabricated |
| Import / export | Deferred; no direction or file format selected |

The proposal recommends distinct view/propose/validate/review/approve/activate/
rollback/retire/preview permissions, with real owners assigned by the team. It
describes immutable revision payloads, separate workflow events, a constrained
active pointer, atomic activation and audit, stale/concurrent activation checks,
and explicit historical rollback. None of these proposed permissions/models is
silently created or assigned.

Future preview must use only designated fictional demonstration scenarios, reuse
the inference evaluator with immutable candidate inputs, never save/revert active
values, and never expose raw rules or classify real barangays as demonstrations.
Future audit must be a persisted, append-only event source in the same transaction
as its governed change. Dashboard activity remains its truthful limited Django
Admin `LogEntry` view; no custom events or retrospective history are invented.

## Models, migrations, and compatibility

**No model or migration changes. No new runtime dependencies.** No local/shared
application database migration, seed, boundary import, or official-data import
was executed. Existing import tests run only in isolated test databases.

Inference, public API views/serializers, and Flutter source remain unchanged.
The new tests compare public assessment options before/after Settings GET and
assert SELECT-only page queries. Existing backend inference, map/reference,
source-policy, authentication, and API tests still pass. Flutter analysis and
its API/model/controller/widget regression suite were also run. This does not
claim a new emulator-to-running-server end-to-end session; Android Studio and
the mobile application were not launched for this read-only change.

## Automated verification

Commands below use the existing Windows virtual environment. Backend commands
run from the repository root; Flutter commands run from `mobile/`.

| Command | Result |
| --- | --- |
| `server\.venv\Scripts\ruff.exe check server/admin_portal` | Passed |
| `server\.venv\Scripts\ruff.exe check server` | Three pre-existing `I001` import-order errors in `geography/views.py`, `geography/test_reference_boundaries.py`, and `geography/management/commands/import_bacoor_boundaries.py`; untouched by this task |
| `server\.venv\Scripts\python.exe server/manage.py check` | No issues |
| `server\.venv\Scripts\python.exe server/manage.py makemigrations --check --dry-run` | No changes detected |
| `server\.venv\Scripts\python.exe -m pytest server/admin_portal/test_settings.py server/admin_portal/test_dashboard.py server/admin_portal/tests.py -q --reuse-db --tb=short --maxfail=3` | 45 passed |
| `server\.venv\Scripts\python.exe -m pytest server -q --reuse-db --tb=short --maxfail=3` | 163 passed, including portal, geography, expert and provenance tests |
| `server\.venv\Scripts\python.exe -m pytest tmp/day4_visual_check.py -q -s --reuse-db --tb=short --maxfail=1` | 3 browser scenarios passed |
| `server\.venv\Scripts\python.exe -m pytest server tmp/day4_visual_check.py -q --reuse-db --tb=short --maxfail=1` after final accessibility changes | 166 passed: 163 backend tests and 3 browser scenarios |
| `flutter analyze --no-pub` | No issues |
| `flutter test --no-pub` | 91 passed |
| `git diff --check` | Passed |

The focused Settings tests cover authentication/authorization and GET-only routes,
empty states, distinct demo/approved/pending groups, private/retired exclusions,
active metadata per mode, missing/inconsistent versions, unknown mode, legacy
multiple-active defense, truthful missing values and zeros, filtering/error
accessibility, escaped user-controlled fields, stable query count, no raw/private
queries, unchanged API options, no fabricated audit events, and navigation.

### Test database environment and initial failure

The first focused test command omitted `--reuse-db`. Django recreated the
disposable `test_floodsense` database, then failed before executing tests with:
`django.db.utils.ProgrammingError: permission denied to create extension "postgis"`
and `HINT: Must be superuser to create this extension.` The normal application
database was not modified. A password-free attempt to use the local PostgreSQL
administrator connection also failed with `fe_sendauth: no password supplied`;
no password, authentication configuration, or privileges were changed.

To complete verification without those permissions, a separate temporary cluster
was initialized using the installed PostgreSQL 17/PostGIS binaries under ignored
`tmp/day4-postgres/`, bound only to `127.0.0.1:55432`, with an isolated QA role and
database. Successful backend/browser commands used this process-local override:

```powershell
$env:DATABASE_URL = 'postgis://floodsense_qa@127.0.0.1:55432/floodsense_day4_qa'
```

Only synthetic fixtures and the existing controlled test/import workflow were
used there. The `.env` file and normal PostgreSQL service configuration were
unchanged. The override is verification-only, not a teammate deployment setting.
The temporary PostgreSQL service and test live servers were stopped after
verification. The isolated cluster files remain in ignored `tmp/day4-postgres/`;
automatic approval review blocked an optional recursive cleanup command with
“blocked by policy,” so only a graceful service shutdown was performed. The
normal PostgreSQL service was left running. No Django development server,
Flutter application, emulator, or Android Studio was started persistently.
The ordinary local `test_floodsense` database still needs PostGIS enabled by its
database administrator before running ordinary `--reuse-db` tests again.

Non-failing test warnings concern the absent collected `server/staticfiles/`
directory in development and an existing importlib metadata deprecation.

## Browser and visual checks

The optional local Playwright harness in ignored `tmp/day4_visual_check.py`
uses Chrome and Django's test live server with isolated users and records.
Screenshots are local QA artifacts under `tmp/day4-validation/`, not app assets
or shared research records. Browser scenarios cover:

- Empty database; populated demo and approved data; active metadata becoming
  unavailable after its source becomes restricted.
- Widths 1440, 1024, 820, 390, and 320 pixels with no horizontal overflow.
- Long permitted source/organization/option names and text wrapping.
- Keyboard focus and Enter on grouped links; Tab from search to category to
  Apply filters; search, category, no-results, clearing, invalid-filter errors.
- Methodology/source warnings, demonstration labels, profile and inventory.
- Canonical and legacy navigation, dashboard quick link, mobile drawer, account
  menu, Map data/Settings navigation, missing-route 404, and rejected POST.
- Server-rendered Settings and filtering with JavaScript disabled.
- No browser JavaScript errors; no private test sentinels in rendered content.

Desktop and mobile screenshots were inspected. This is a keyboard/semantic and
responsive review, not a full screen-reader or independent accessibility audit.
Governed confirmations, preview isolation, activation/rollback, concurrency,
audit creation, and migration-upgrade checks remain unimplemented/unverified
because those workflows require approval first.

## Teammate setup and walkthrough

After obtaining this change through the team's authorized Git workflow, an
already configured teammate needs **no dependency installation, migration,
permission grant, seed, or import** for the Settings foundation. Local records
and staff accounts are not synchronized by Git. An empty database is supported.

For local review, use the existing virtual environment and environment setup:

```powershell
server\.venv\Scripts\python.exe server/manage.py check
server\.venv\Scripts\python.exe server/manage.py makemigrations --check --dry-run
server\.venv\Scripts\python.exe server/manage.py runserver
```

Sign into `/management/`, open **Settings**, inspect the methodology cards and
scenario inventory, filter by label/code or category, and follow the legacy
`/management/assessment-parameters/` URL to confirm its redirect. Do not use
technical Admin to bypass the pending parameter-governance design.

For tests, use a disposable PostGIS-enabled test database and `--reuse-db`:

```powershell
server\.venv\Scripts\python.exe -m pytest server -q --reuse-db
```

If the test database lacks PostGIS, its PostgreSQL administrator must connect
specifically to that **test database** and run `CREATE EXTENSION IF NOT EXISTS
postgis;` before retrying. Do not elevate the normal application role or apply
this instruction to a shared/deployed target without separate authorization.

## Remaining decisions and limitations

No parameter type, owner, validated bound/unit, organizational role, or editable
definition has been invented. The team must approve the proposal and supply the
definition evidence and permission assignments. Import/export may remain
deferred explicitly. Account preference mutations also remain unavailable.

Day 4 completion still requires the approved schema, reviewed migrations,
permission enforcement, immutable revisions, review/approval/activation/rollback,
atomic audit, supported demonstration preview, and their verification. The
read-only foundation is ready for review; it is not the full Day 4 workflow.
