# FloodSense Admin Frontend - Day 2 Guide

**Verified:** 18 September 2026

**Status:** Day 2 complete; user confirmed successful manual testing on
18 September 2026.

## Outcome

`/management/` now shows a read-only operational dashboard instead of the Day 1
development checklist. It summarizes the current database, separates recorded
publication statuses, identifies pending-validation records, and shows a limited
maintenance-action feed. Quick actions open the existing protected module
placeholders. Editing, approval, publication, and imports remain later-day work.

The staff-only shell, sign-in, POST-only sign-out, sidebar, mobile drawer, account
menu, development-environment notice, and data-safety notice are retained.
Django's `/admin/` remains a separate technical maintenance interface.

## Implemented features and changes from Day 1

| Area | Day 1 behavior | Delivered in Day 2 |
| --- | --- | --- |
| Overview | Foundation badge, development checklist, and next-module presentation | Personalized operational overview labeled database-backed and read-only |
| Summary cards | Static descriptions of the administration foundation | Real counts for geographic areas, sources, DSS guidance, scenario options, and records needing review |
| Data status | General development-data warnings | Per-card counts for every actual publication status, with distinct text/color labels and separate enablement counts |
| Geographic summary | Protected Map data placeholder only | Geographic totals and an expandable area-type breakdown, without treating boundaries as flood classifications |
| Scenario summary | Protected assessment-parameter placeholder only | Stored scenario totals and enabled rainfall-intensity/duration counts, without exposing scientific values or editing controls |
| Review attention | No operational review summary | Pending-validation total and per-module breakdown with protected navigation links |
| Maintenance activity | No recorded activity panel | Up to five relevant Django maintenance events, safe display fields, and a visible incomplete-audit limitation |
| Missing approved data | General placeholder messaging | Explicit approved-data empty states that preserve actual totals and demonstration counts |
| Quick actions | Links presented as the next build modules | Descriptive links to Map data, Assessment parameters, DSS content, and Sources, each labeled with its planned day |
| Responsive presentation | Shared responsive portal shell | Responsive dashboard cards and panels, compact empty states, wrapping labels, semantic count/activity lists, and keyboard focus styles |
| Backend integration | Dashboard rendered shell context only | Focused read-only query service, five-query summary, and 26 additional automated backend tests |

The Day 2 work integrates with existing Django models and the existing portal
routes. It preserves authentication, source-governance boundaries, and the
Flutter/API contract. The metric definitions and activity limitations below
describe the implemented behavior rather than future capabilities.

## Architecture and changed files

| File | Responsibility |
| --- | --- |
| `server/admin_portal/services/__init__.py` | New read-only service package |
| `server/admin_portal/services/dashboard.py` | New `get_dashboard_summary()` aggregates and limited maintenance log projection |
| `server/admin_portal/views.py` | Obtains the summary after staff authorization and passes it to the template |
| `server/admin_portal/templates/admin_portal/dashboard.html` | Operational cards, pending summary, activity, empty states, and quick links |
| `server/admin_portal/templates/admin_portal/publication_breakdown.html` | New shared definition-list presentation of actual model status choices |
| `server/admin_portal/static/admin_portal/css/admin_portal.css` | Scoped dashboard styling, status colors, wrapping, and responsive layouts |
| `server/admin_portal/test_dashboard_service.py` | New aggregate, query, status, and activity tests |
| `server/admin_portal/test_dashboard.py` | New portal authorization, rendering, escaping, navigation, and read-only tests |
| `docs/ADMIN_FRONTEND_DAY_2_GUIDE.md` | This implementation and verification handoff |
| `docs/ADMIN_WEB_7_DAY_IMPLEMENTATION_PLAN.md` | Preserves the updated team timeline and records Day 2 complete / Day 3 next |

No models, migrations, requirements, public API routes, inference code, Flutter
code, or shared navigation JavaScript changed.

### Query behavior

The service returns named geographic, source, guidance, and scenario summaries,
`review_attention`, `recent_activity`, and `activity_is_complete_audit=False`.
It performs exactly **five SELECT queries**: one filtered aggregate for each of
the four domain models and one joined, limited activity query. The review total
reuses those aggregates. Authentication/session reads are additional to these
five queries when the full portal request is served.

The service does not load all records to count them, select geometries or content
payloads, resolve content types through a potentially writing cache lookup, call
the inference engine or public API, or write database rows. Query-count tests
cover empty and growing datasets and avoid per-event user/content-type queries.

## Exact count definitions

All counts describe stored records. They do not assert scientific validity,
resident availability, map publication, or a complete assessment-ready dataset.

| Display | Definition |
| --- | --- |
| Geographic areas: total records | All `GeographicArea` rows |
| Geographic areas: enabled | `GeographicArea.is_enabled=True`, independent of status |
| Area types | All geographic rows grouped by actual `AreaType` choices: demonstration zone, city, barangay, other; available in the Area types disclosure |
| Data sources: total sources | All `DataSource` rows |
| Approved and publicly releasable sources | `DataSource.status=APPROVED` **and** `is_publicly_releasable=True` |
| DSS guidance: total items | All `GuidanceItem` rows |
| DSS guidance: enabled | `GuidanceItem.is_enabled=True`, independent of status |
| Scenario options: total options | All `ScenarioOption` rows |
| Scenario options: enabled | `ScenarioOption.is_enabled=True`, independent of status |
| Enabled rainfall intensity | Enabled scenario rows with `category=INTENSITY` |
| Enabled rainfall duration | Enabled scenario rows with `category=DURATION` |
| Each card's status breakdown | Rows of that card's model with the exact displayed `status` value |
| Review attention: total | Sum of `PENDING_VALIDATION` records across the four modules, with DSS guidance also counting the union of items in its Day 5 `IN_REVIEW` workflow state |
| Review attention by module | The model's `PENDING_VALIDATION` count; for DSS guidance, the union with `workflow_status=IN_REVIEW` avoids double-counting one item |

Status labels come from the actual model choices: `DEMONSTRATION`,
`PENDING_VALIDATION`, `APPROVED`, `RESTRICTED`, and `RETIRED`. Each has a text
label and distinct visual treatment. Enablement is never substituted for
approval. Status counts are based on the record itself, without silently applying
the public API's separate source/eligibility filters.

Every card continues to show actual totals and demonstration counts when
approved data are absent. Geographic, guidance, and scenario cards show their
approved-data empty state when their approved count is zero. The source card's
empty state depends on the approved-and-publicly-releasable intersection. A zero
review-attention count says no records are pending validation and no DSS item is
in review; it does not say everything is approved.

Geographic counts describe administrative or demonstration records, not flood
zones or susceptibility assignments. Scenario options are hypothetical inputs,
not sensor readings. Guidance content and scientific parameter values are not
selected or displayed.

## Recent recorded maintenance activity

The feed uses `django.contrib.admin.models.LogEntry`, filtered to these exact
app/model pairs:

- `geography.GeographicArea`
- `provenance.DataSource`
- `dss.GuidanceItem`
- `expert.ScenarioOption`

It shows at most five known Added/Changed/Deleted actions, newest first by event
time with primary key as the tie-breaker. Each entry contains only the generic
action, module label, account display name (or `Account #ID` fallback), and the
recorded timestamp. Display names are escaped normally. Object representations,
raw change messages, before/after values, emails, source notes, permitted-use
text, and guidance instructions are not selected for the feed.

Raw rule, rule-condition, rule-set, unrelated, and unknown-action entries are
excluded. Empty results show "No recorded maintenance activity is available."
No activity is synthesized from model creation or modification timestamps.

The visible limitation is: "This is a limited view of recorded Django
maintenance actions, not the complete FloodSense audit history." It does not
claim to audit sign-ins, API reads, or all portal operations. Day 7 retains the
full audit-history interface work; governed mutations must capture their events
when those later workflows are introduced.

## Security, navigation, and presentation

- `staff_required` and `require_GET` remain on the dashboard. Anonymous requests
  redirect to the custom login; non-staff/inactive users cannot read summaries.
- POST, PUT, PATCH, DELETE, HEAD, OPTIONS, and TRACE requests are rejected. The
  dashboard offers no mutation form; the existing POST sign-out is retained.
- Templates use ordinary escaping, without marking database content safe.
- Quick actions link to Map data, Assessment parameters, DSS content, and
  Sources and content. Each is visibly labeled with its planned day. No action
  links to technical Admin or raw Expert System controls.
- Counts refresh on page navigation only. There are no polling loops, timers,
  forecasts, or background alerts.
- Four primary cards form a desktop grid; the pending total spans the row below.
  Cards reflow to two columns on tablet and stack on mobile. Lower panels stack
  at the existing breakpoint, with compact empty states and wrapping text.
- There is one primary heading, named sections, definition lists for counts,
  a semantic activity list, visible status text, and focus styles. The Area types
  disclosure and navigation links remain keyboard accessible.

## Verification results

The existing configured isolated PostgreSQL/PostGIS test database was used.
Fixtures are fictional and owned by the tests; they do not depend on local rows
or a seed command. Local application records were not populated or changed for
dashboard screenshots.

| Check | Result |
| --- | --- |
| Baseline complete backend suite | 98 passed; 43 warnings |
| Final focused portal suite | 35 passed; 23 warnings |
| Final complete backend suite | 124 passed; 56 warnings (26 new tests) |
| Ruff, `server/admin_portal` | Passed |
| Ruff, entire `server` | Three pre-existing I001 import-order findings; verified against HEAD in `geography/views.py`, `geography/test_reference_boundaries.py`, and `geography/management/commands/import_bacoor_boundaries.py`; left unchanged |
| Django system check | No issues |
| `makemigrations --check --dry-run` | No changes detected |
| `migrate --plan` | No planned migration operations |
| `git diff --check` | Passed; Git reports normal LF-to-CRLF normalization notices |
| Flutter analysis | No issues (`flutter analyze --no-pub`) |
| Flutter tests | 91 passed (`flutter test --no-pub`) |
| Android debug build | Passed (`flutter build apk --debug --no-pub`) |
| Live Flutter API-client smoke | Passed against local Django: options, demonstration areas, reference boundaries, map evaluation, detailed evaluation, and temporary point resolution |
| Browser QA | Two isolated empty/populated scenarios passed at 1440x1024, 820x1180, 390x844, and 320x844 |

The browser checks used installed headless Chrome with temporary Playwright QA
tools under ignored `tmp/`; the interactive browser/native helper was unavailable.
They exercised normal test-account login, accurate rendered totals, no horizontal
overflow, mobile navigation, the account dropdown, Escape handling, quick-link
focus, long-heading wrapping, and absence of sensitive event payloads. Screenshots
were visually inspected for desktop and mobile. These temporary QA tools are not
new application dependencies and are outside normal test discovery.

Local evidence is under ignored `tmp/day2-validation/`, named
`dashboard-test-empty-{width}.png` and `dashboard-test-populated-{width}.png`,
with corresponding `-viewport.png` files. All browser screenshots show an
explicit TEST DATA account and isolated fixtures, including synthetic status
combinations. They are not official data or screenshots of local approved
records. `android-app-demonstration.png` records the existing Android app's
demonstration screen during the integration check.

Existing test warnings concern the missing development `server/staticfiles/`
directory and an importlib metadata deprecation. The successful Android build
reported nonfatal Java native-access and Android SDK XML-version warnings. No
dependency upgrade, static collection, or toolchain change was made to hide them.

### Local database caveat

At verification, the local database contained 4 geographic records, 1 source,
4 guidance items, 10 scenario options, and 0 pending-validation records across
those four models. Its reference-boundary API returned no imported barangays;
the presence of a 47-barangay file in the repository does not create database
rows. The dashboard never substitutes the expected 47 for a database count.

Local rows and administrator accounts differ between teammates. Neither these
counts nor local accounts are synchronized by Git. No official-data import or
application-database migration was performed. No official statistics, flood
classifications, scientific thresholds, emergency instructions, or evacuation
centers were invented; synthetic records existed only in isolated tests. No
credentials, dumps, PII, or restricted data were added to tracked files, and no
commit, pull, or push was performed.

### User manual verification and acceptance

On 18 September 2026, after the guided Day 2 test walkthrough, the project owner
reported: **"Everything works perfectly."** This records successful user-reported
manual acceptance of the implemented dashboard. The automated results above
remain the results recorded during implementation; this documentation update
does not represent another test-suite run.

The walkthrough provided the following checks for repeating manual verification:

1. Open `http://127.0.0.1:8000/management/` and sign in with an existing active
   staff or superuser account.
2. Compare the five summary totals with the local database. At this walkthrough,
   they were **4 geographic areas, 1 source, 4 guidance items, 10 scenario options,
   and 0 pending-validation records**. The domain records were demonstration
   data, with zero approved records; approved-data empty messages were expected.
3. Expand **Area types**, inspect the five recorded maintenance entries and their
   audit limitation, and verify the meaningful zero-pending state. Confirm the
   Day 1 development checklist is gone.
4. Open each quick action and return through **Overview**. Destination pages
   remain clearly labeled Planned until their assigned development days.
5. Use the browser's responsive device toolbar at **390 pixels**, then
   **320 pixels**, checking readable stacked cards, no horizontal overflow,
   hamburger navigation, and the Settings/Sign out account menu.
6. Open the dashboard in an Incognito/InPrivate window to check the login
   redirect. Sign out in the authenticated window and verify that reopening
   `/management/` requires authentication.

The walkthrough also supplied the Django system check, migration-detection
check, focused portal tests, and complete backend test commands listed below.
The expected implementation totals are 35 portal tests and 124 backend tests.
Changing application records or importing data is unnecessary for this check;
future local totals should be compared with that developer's own database.

## Teammate commands after pulling

Use the existing configured environment. This change requires **no dependency
installation, migration application, seed, or import**. From the repository root:

```powershell
server\.venv\Scripts\python.exe -m ruff check server/admin_portal
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe server\manage.py makemigrations --check --dry-run
server\.venv\Scripts\python.exe server\manage.py migrate --plan
server\.venv\Scripts\python.exe -m pytest server/admin_portal -q --reuse-db
server\.venv\Scripts\python.exe -m pytest -q --reuse-db
server\.venv\Scripts\python.exe server\manage.py runserver 0.0.0.0:8000
```

Open `http://127.0.0.1:8000/management/` and sign in using an existing active
staff account. To repeat the unchanged mobile checks in another terminal:

```powershell
Set-Location mobile
flutter analyze --no-pub
flutter test --no-pub
flutter build apk --debug --no-pub
```

## Day 3 handoff

Day 3 is next, not implemented by this change. Build the interactive map and
geographic-data review at `/management/map-data/`: barangay search/selection,
layer visibility, source/status/version/validation details, and the 47
administrative boundary records once their reviewed import is explicitly
authorized for the target database. Preserve the distinction between
administrative boundaries, provisional MGB data, fictional demonstration zones,
and future approved susceptibility layers. Do not publish provisional
susceptibility data to residents or assign susceptibility from boundary geometry.

Settings/parameters, DSS content, rainfall references, evacuation centers,
sources, and full audit history remain the protected later-day placeholders.
