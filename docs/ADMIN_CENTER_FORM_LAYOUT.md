# Center draft form layout — 6 October 2026

The Create center draft and Edit draft page now use a single form organized by
the administrator's task. The existing all-field loop placed unrelated fields
side by side, while nested grid stretching enlarged short controls to match
adjacent search widgets and help text. It also mixed routine draft actions with
verification fields and approval/release buttons.

## Design

Five fieldsets provide an ordered, accessible structure:

1. **Center details:** documented name, authorized staff contact and address.
2. **Location:** one native barangay/geographic-area dropdown, paired latitude/longitude,
   and the existing coordinate preview directly below those inputs.
3. **Source and status:** facility source, publication data status and the
   conditional temporary-record checkbox. A link reaches the existing inline
   source tools without navigating away or discarding entered values.
4. **Notes and limitations:** separate staff notes and public-facing caveats.
5. **Review and save:** prominent Save draft, add-another, submit-for-review and
   Cancel actions. Other existing actions and verification-only fields are in
   a native expandable section. Relevant errors reopen it automatically.

A single page keeps related information reviewable without a wizard or new
navigation state. The source dialog remains outside the main form so forms are
not nested. Existing source review context remains available. No field or
authorized save action was removed.

Input, date and select controls reserve a consistent 46px height; field groups
align to the top instead of stretching. Checkboxes are 20px and sit beside their
labels. Only address, notes and limitations retain multiline text areas.
Desktop fields use two columns with full-width long fields; at 900px and below,
they stack in document order. The form uses the existing colors, panel style,
spacing and button variants, with a maximum reading width of 1120px.

Required and optional labels, existing help text and inline errors remain
available. Inline error IDs are unique. The map preview has an explicit 310px
height so the provider viewport and zoom controls are not clipped. It remains
a coordinate preview with existing source, route-safety and availability caveats.

## Scope and verification

Changes are limited to the center template, its small field-rendering include,
scoped rules in `operations.css`, form display copy, the source-search script,
and optional browser QA. No model, migration,
permission, validation rule, save action, resident eligibility policy, business
logic, local data or mobile code changed. Previous Lucide/sidebar
work is preserved. The private `.env` was neither read nor modified.

The owner's subsequent dropdown refinement removes the separate barangay search
box. The native dropdown starts with **Choose available barangay**, provides
the same text as a hover tooltip, and has a visible associated guide. Its label
still identifies the underlying geographic-area relationship; existing choices,
optional draft association and resident-eligibility validation are preserved.
The source search remains available. The center page's script URL has a new
cache version so an older cached search widget is not injected.

Passed: Django system check, Ruff for the portal/browser script, `git diff --check`,
**195 Admin portal tests**, and **2 browser acceptance tests**. Existing
staticfiles-directory and Django URLField deprecation warnings remain.

After the dropdown refinement, the focused center-form browser check was rerun
with explicit assertions for the absent search input and the dropdown prompt
and tooltip, including the no-JavaScript form.

Browser checks cover 1440/1024/768/390/320px, desktop sidebar states, consistent
control heights, paired coordinates, labeled checkboxes, map zoom without
submitting the form, preserved source selection/dialog values, linked validation
errors, automatically reopened verification errors, draft saving/editing, hidden
concurrency values, duplicate confirmation, and no-JavaScript add-another saves.
The ordinary sidebar/navigation acceptance also passes. The isolated QA
PostgreSQL instance was stopped after testing.

Visually inspected local synthetic-fixture screenshots:

- [Desktop form](../tmp/portal-layout-qa/center-form-1440-expanded.png)
- [Tablet form](../tmp/portal-layout-qa/center-form-1024-expanded.png)
- [Mobile details](../tmp/portal-layout-qa/center-form-details-390.png)
- [Mobile save actions](../tmp/portal-layout-qa/center-form-actions-390.png)
- [Error recovery](../tmp/portal-layout-qa/center-form-errors.png)

These are ignored QA artifacts and do not travel through Git. The advanced
section is deliberately open in the captures to inspect its controls; it starts
closed on a fresh valid form. Cropped mobile captures hide the already offscreen,
unfocused skip link to avoid a browser capture artifact; the browser's keyboard
accessibility behavior remains intact.

## Teammate steps

Restart Django and refresh Create center draft or Edit draft. The page's
stylesheet and workflow script URLs have new cache versions. No dependencies, migrations, seeds or
imports are required. Deployments should use their usual static-file collection.

Ordinary checks on an already configured checkout:

```powershell
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe -m pytest server/admin_portal --reuse-db
```

The optional browser script uses the existing Playwright/Chromium QA tools,
synthetic fixtures and pytest's isolated PostGIS database:

```powershell
server\.venv\Scripts\python.exe -m pytest scripts/verify_admin_portal_layout.py --reuse-db
```

The task's local runner disables dotenv loading and targets an isolated QA
PostGIS instance. No application/shared database, official import or Git
pull/push operation is required or was performed.
