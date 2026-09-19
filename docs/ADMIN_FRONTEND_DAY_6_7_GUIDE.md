# FloodSense Admin Frontend - Days 6 and 7 Implementation Guide

**Implemented:** 19 September 2026
**Routes:** `/management/rainfall-references/`,
`/management/evacuation-centers/`, `/management/sources-content/`, and
`/management/audit-history/`

## Scope and decision boundary

Days 6 and 7 add reviewed operational-data workflows without changing the
scenario-based research scope. They do not add rainfall monitoring, timers,
polling, forecasts, warning automation, live capacity, resident evacuation
orders, external agency imports, or invented records.

Rainfall references are intentionally read-only. `ScenarioOption` values are
consumed by Expert System inference, and the Day 4 decision gate still lacks
approved scientific definitions, units and bounds, responsible authority,
validator, role matrix, and change workflow. This implementation therefore
shows stored values and available provenance but provides no ordinary portal
endpoint for changing them.

## Rainfall-reference review

Authorized users with `expert.view_scenariooption` can search and filter
intensity and duration options and open a read-only detail view. The detail page
shows units, numeric bounds, derived inference value, enabled state, source,
organization/custodian, record period, version/reference date, validation
state, processing notes, and limitations. Missing metadata is displayed as
not recorded.

There is no create, edit, import, API-fetch, timer, or polling route.

## Evacuation-center workflow

`evacuation.EvacuationCenter` stores name, address, optional geographic-area
association, WGS 84 coordinates, authorized contact information, source,
publication status, verification state/date, optional documented capacity,
notes, limitations, and timestamps.

The workflow is:

`Draft -> In review -> Verified -> Inactive -> In review`

Review can also return a record to draft. Only drafts can be edited.
Verification requires a date and an approved source with a responsible
organization. Capacity can be recorded only in the verification confirmation
form. Returning a record to an earlier state clears stale verification date
and capacity. The module does not expose a resident API.

Permissions are `view_evacuationcenter`, `add_evacuationcenter`,
`change_evacuationcenter`, `verify_evacuationcenter`, and
`deactivate_evacuationcenter`.

## Source and provenance workflow

The existing `provenance.DataSource` model is extended with custodian, version,
processing notes, limitations, and citation URL. Existing fields continue to
cover organization, type, coverage, record period, acquisition date, permitted
use/restrictions, reviewer, validation date, release flag, and notes.

New portal records begin as `PENDING_VALIDATION` and are not publicly
releasable. Demonstration-source creation is deliberately excluded from this
ordinary workflow; existing demonstration sources remain visibly labeled.
Only pending records are editable.

Approval requires organization, custodian, coverage, permitted use, and
limitations. Approval and public release are separate confirmed actions.
Restriction removes release eligibility. The detail view shows connected
rainfall references, guidance, geographic areas, and evacuation centers.

Permissions are `view_datasource`, `add_datasource`, `change_datasource`,
`approve_datasource`, `publish_datasource`, and `restrict_datasource`.

## Audit history and security

Users with `admin.view_logentry` receive a read-only, paginated view of genuine
Django maintenance log entries for geographic areas, sources, guidance,
scenario options, and evacuation centers. Filters cover administrator, module,
action, start date, and end date. Change-message contents are not displayed,
which avoids exposing entered notes or contact data.

The UI states that this is not a complete operating-system, database, or
security-event log. It never fabricates events from timestamps. Every mutation
uses POST, CSRF protection, an explicit model permission, a confirmation step
for state changes, server-side validation, a database transaction, and a
maintenance log entry. Concurrent workflow changes are rejected through an
expected-state check.

Navigation and dashboard actions are permission-aware. Direct URL access still
receives server-side HTTP 403 enforcement.

When `DJANGO_DEBUG=false`, settings enforce secure cookies and HTTPS redirect,
honor the configured proxy HTTPS header, and enable a one-hour HSTS default.
Subdomain coverage and preload remain opt-in because they require deployment
and DNS review. The reverse proxy must remove untrusted client-supplied
`X-Forwarded-Proto` values before setting its own.

## Database changes

- `provenance.0002_datasource_metadata_and_permissions`
- `evacuation.0001_initial`

After pulling, teammates must activate the server environment and run:

```powershell
cd server
python manage.py migrate
python manage.py check
```

No shared/deployed database migration, official-data import, seed, pull, push,
or commit was performed as part of this implementation.

## Verification checklist

```powershell
cd server
python -m ruff check admin_portal evacuation provenance
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test

cd ..\floodsense_app
flutter analyze
flutter test
```

For UI verification, test the four routes at desktop, mobile, and 320-pixel
widths with view-only, editor, reviewer, and release roles. Confirm empty
states, invalid dates and coordinates, stale confirmations, denied direct
URLs, keyboard focus, table reflow, map preview, separate approval/release,
verification/deactivation, and audit filters.

### Verification evidence for this implementation

- targeted Day 6-7 backend tests: 13 passed;
- complete backend suite: 188 passed;
- Ruff for `admin_portal`, `evacuation`, and `provenance`: passed;
- Django system check: passed;
- migration consistency check: no changes detected;
- fresh migration graph exercised by the complete test suite: passed;
- Flutter analysis: no issues;
- Flutter tests: 91 passed; and
- Chromium at 1440x1024, 390x844, and 320x844 across the four module lists and
  both create forms: correct headings and no horizontal overflow.

The browser run reported only the existing `/favicon.ico` 404. Backend tests
continue to report the existing warning that `server/staticfiles/` does not
exist; neither affects the tested workflows.

`manage.py check --deploy` with production-like environment values reports only
the two intentional warnings for HSTS subdomain coverage and preload. Those
options remain false until the deployment owner confirms that every subdomain
is HTTPS-only and accepts the preload commitment.
