# Source metadata form layout — 6 October 2026

The standalone Create source metadata and Edit source metadata pages now follow
the grouped entry layout used by center drafts. Previously, the all-field loop
mixed unrelated fields and grid stretching enlarged short controls beside
text areas or help text.

## Design

One form keeps all metadata reviewable without a wizard or extra navigation:

1. **Source details:** name/type, organization/custodian, citation URL and the
   existing conditional temporary-source checkbox.
2. **Coverage and version:** full-width coverage description, paired record
   period dates, then received/created date and version. The guide distinguishes
   the coverage period from the source's receipt/creation date.
3. **Use and limitations:** documented permitted use and caveats.
4. **Processing and notes:** separate processing history and staff notes.
5. **Review and save:** Save for review, add-another and Cancel. Accounts with
   approval permission can expand the existing approval actions and confirmation.
   Approval errors reopen this native disclosure automatically.

The source page uses the portal's existing colors, panels and buttons, with a
1120px maximum reading width. Desktop fields use two columns; at 900px and below
they stack in document order. Labels and fields align to the top, inputs/selects/
dates stay 46px high, and checkboxes are 20px beside their clickable labels.
Only the five existing descriptive fields remain resizable multiline text areas.

Required/optional labels describe saving for review; the guide separately explains
that approval needs complete metadata. Existing help text, associated inline
errors and a linked error summary support recovery without losing entered values.

## Scope and verification

Changes are scoped to the standalone source template, its field include,
source-form CSS and optional browser QA. The inline source dialog is unchanged.
No model, migration, field type, permission, approval rule, save logic, import,
application data or mobile functionality changed. Hidden edit concurrency values
and the existing temporary-record eligibility remain intact. Earlier sidebar,
icon and center-form work is preserved.

Passed: **195 Admin portal tests**, focused source-form browser acceptance,
Django system check, Ruff and `git diff --check`. Existing staticfiles-directory
and Django URLField deprecation warnings remain.
Browser checks cover 1440/1024/768/390/320px, expanded/collapsed desktop sidebar,
paired dates, control heights, labeled checkboxes, validation links and retained
values, approval error recovery, saving/editing, separate approval/public release,
no-JavaScript add-another and accounts without approval permission.

Visually inspected synthetic-fixture screenshots are ignored local QA artifacts:

- [Desktop form](../tmp/portal-layout-qa/source-form-1440-expanded.png)
- [Mobile form](../tmp/portal-layout-qa/source-form-390-expanded.png)
- [Approval error](../tmp/portal-layout-qa/source-form-approval-error.png)

Testing used pytest's isolated PostGIS database; its QA PostgreSQL instance was
stopped after validation. No application/shared database, official-data import,
private `.env` or Git pull/push operation was accessed or performed.

## Teammate steps

Restart Django and refresh Create source metadata or Edit source metadata. The
page's stylesheet URL has a new cache version. No dependencies, migrations, seeds
or imports are required. Deployments should use their usual static-file collection.

On an already configured checkout:

```powershell
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe -m pytest server/admin_portal --reuse-db
```

The optional browser check uses the existing Playwright/Chromium QA tools:

```powershell
server\.venv\Scripts\python.exe -m pytest scripts/verify_admin_portal_layout.py::test_source_form_browser --reuse-db
```
