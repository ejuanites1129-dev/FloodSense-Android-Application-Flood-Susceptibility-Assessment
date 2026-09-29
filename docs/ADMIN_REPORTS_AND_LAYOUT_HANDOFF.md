# Admin Reports and layout handoff

Implemented 30 September 2026 for the custom `/management/` portal.

## Delivered

- Desktop sidebar collapses to a 72px branded rail. Navigation is hidden from
  layout, keyboard focus, and accessibility APIs. Hover, focus, and touch expose
  expansion; Ctrl+B uses the same toggle, ignores repeats/modifiers/editors, and
  preserves the desktop preference when storage works. Mobile retains its drawer,
  scrim, Escape behavior, and focus return, with a keyboard focus loop.
- Settings is linked only from the account menu. Direct Settings and legacy
  assessment-parameter URLs remain supported, including without JavaScript.
- Overview remains the landing/sign-in/home destination. It contains five
  rebalanced summary cards, their empty states, and safety messaging. Review,
  activity, attention, and quick-action sections and their anchors were removed.
- Reports follows Overview in navigation. The GET-only staff page provides an
  administrative summary, a status table, separate workflow/verification counts,
  review queues, interpretation, and permission-aware management links.
- Geography uses the full content width for the map, followed by responsive layer
  controls, browsing, and details. ResizeObserver plus viewport/layout events call
  OpenLayers `updateSize()` or Mapbox `resize()` without refitting bounds.

No model, migration, dependency, scientific rule, publication policy, permission
grant, resident API, or mobile change was made. `README.md` and untracked `start.md`
were pre-existing user changes and were preserved. No Git pull/push, shared DB
migration, or application-data import was run.

## Report definitions

The service reuses five aggregate queries from `services/dashboard.py`, without
reading activity logs or raw expert-rule tables. Reports removes withheld modules
from its returned details, totals, review counts, and links. Geography uses the
existing staff-only review boundary; the other four modules require their existing
model view permissions. Audit history links require `admin.view_logentry`.

| Figure | Population / meaning |
| --- | --- |
| Records in accessible modules | Sum of rows in the accessible modules, including all stored statuses and disabled rows; not unique places or people |
| Status table | All rows per accessible module, grouped by the five mutually exclusive persisted statuses: demonstration, pending validation, approved, restricted, retired |
| Enabled | Stored `is_enabled`, independent of approval |
| Approved/public sources | Sources with both Approved status and public-release permission |
| Guidance workflow | Stored Draft, In review, Approved, or Published workflow state; includes demonstration statuses and does not evaluate API eligibility |
| Center verification | Stored Draft, In review, Verified, or Inactive; independent of publication status and occupancy |
| Geographic review queue | Pending-validation administrative records matching the existing Map data source/category policy, including disabled records; other geographic rows are outside this queue |
| Source/scenario review queue | Pending-validation records, including disabled scenario options |
| Guidance review queue | Pending-validation status OR In review workflow; each row counted once |
| Center review queue | Explicit In review verification state |

Zero, access restricted, and unavailable historical measures are explicitly
distinguished. No percentages, trends, timestamp-derived activity, or operational
recommendations are shown. Status is reported as stored, not independent evidence
of source validity, scientific approval, public eligibility, or current flood
conditions. Review links use the same filters as the counted queues.

## Files

- `server/admin_portal/views.py`, `urls.py`: navigation and protected Reports route.
- `server/admin_portal/services/dashboard.py`, new `services/reports.py`: optional
  activity lookup, workflow aggregates, report definitions and permission handling.
- `templates/admin_portal/base.html`, `dashboard.html`, new `reports.html`:
  sidebar/account navigation, simplified Overview, and reporting UI.
- `static/admin_portal/css/admin_portal.css`, `map_data.css`, `no_script.css`:
  coordinated shell widths, grids, report table, full-width map, and fallback UI.
- `static/admin_portal/js/admin_portal.js`, `map_data.js`: sidebar interactions,
  focus handling, preference storage, and provider resizing/observer cleanup.
- `test_dashboard.py`, `test_settings.py`, new `test_reports.py`: updated regression
  expectations and seven focused Reports tests.
- `scripts/verify_admin_portal_layout.py`: optional, reproducible Playwright QA
  against pytest's isolated database/live server; not a runtime dependency.
- This guide and the navigation update in `ADMIN_WEB_7_DAY_IMPLEMENTATION_PLAN.md`.

## Verification completed

- Django `check`: no issues.
- `makemigrations --check --dry-run`: no changes detected.
- Ruff across `server/admin_portal` and the browser script: passed.
- `git diff --check`: passed.
- Portal regression suite: **147 passed**.
- Chromium browser acceptance script: **1 passed**, covering all three affected
  pages at 1440, 1024, and 768px in expanded/collapsed states and 390/320px with
  the drawer open/closed. It checks horizontal page overflow, active navigation,
  keyboard/repeat/modifier/editor handling, focus visibility and hidden links,
  hover/focus/touch expansion, reload/navigation persistence, storage failure,
  mobile preference isolation, reduced motion, drawer focus return/loop, account
  Settings/sign-out, long record names, search/selection, layer states, map size,
  preserved zoom/center/selection/layer visibility, and no-JavaScript browsing.
- Real OpenLayers rendering and resizing passed. Simulated Mapbox asset failure
  activated OpenLayers; loss of both libraries preserved list/search/details.
  Live Mapbox rendering was not tested with a production token.
- Screenshots were visually inspected; small-screen status tables use contained
  horizontal scrolling with readable labels. Screenshots use synthetic test data,
  not local application or official Bacoor records.

The default local test invocation was blocked by the application role lacking
permission to create the PostGIS extension in the test database. Validation used
a separate temporary PostgreSQL 17/PostGIS instance on `127.0.0.1:55439`, with the
same virtual environment and committed migrations. The installed SimpleJWT
package was also detected as an unmigrated app during fresh test setup, causing
`relation "accounts_user" does not exist` when sync ran before migrations. Applying
the committed migrations to the isolated test database before `pytest --reuse-db`
resolved that setup order issue. Neither workaround changed application settings,
database permissions, shared migrations, or dependencies. The temporary instance
was stopped after testing.

Existing warnings remain: missing development `server/staticfiles/`, Python
package metadata deprecation, and Django's future URLField scheme default.
Verification was Chromium-based; no full backend suite, Flutter suite, physical
mobile-device run, or screen-reader session was performed for this UI change.

## Screenshots

Local evidence is retained under `tmp/portal-layout-qa/` (ignored by Git).
Open [the screenshot index](../tmp/portal-layout-qa/SCREENSHOTS.md) for 31 captures.

- [Overview expanded](../tmp/portal-layout-qa/overview-1440-expanded.png)
- [Overview collapsed](../tmp/portal-layout-qa/overview-1440-collapsed.png)
- [Reports](../tmp/portal-layout-qa/reports-1440-expanded.png)
- [Geography](../tmp/portal-layout-qa/geography-1440-expanded.png)
- [Mobile Reports](../tmp/portal-layout-qa/reports-390-drawer-closed.png)
- [Mobile drawer](../tmp/portal-layout-qa/overview-390-drawer-open.png)

These screenshots are local handoff artifacts, not files synchronized by Git.

## Teammate steps after pulling

For this change, **no dependency installation, migration, seed, or import is
required** on an already configured checkout. From the repository root:

```powershell
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe server\manage.py makemigrations --check --dry-run
server\.venv\Scripts\python.exe -m pytest server/admin_portal --reuse-db
server\.venv\Scripts\python.exe server\manage.py runserver
```

The regression command needs a prepared, isolated PostGIS test database and a
working dependency installation; the local environment blockers above must be
resolved if encountered. Restart an already-running development server and reload
the browser to receive the static assets. Open `/management/` or
`/management/reports/`. For an existing deployment using collected static files,
the deployment owner should run its normal `collectstatic` process.

Browser QA is optional. With Playwright and Chromium available in a QA environment:

```powershell
# Optional: use an installed Chromium executable instead of a Playwright browser.
$env:FLOODSENSE_QA_BROWSER = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
server\.venv\Scripts\python.exe -m pytest scripts/verify_admin_portal_layout.py --reuse-db
```

The browser script creates only isolated synthetic test fixtures. It never logs
into or writes to the application database.
