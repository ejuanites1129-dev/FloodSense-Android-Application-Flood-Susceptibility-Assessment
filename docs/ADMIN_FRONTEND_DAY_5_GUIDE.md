# FloodSense Admin Web — Day 5 DSS content guide

Updated: 19 September 2026.

Status: **Complete.** Day 5 adds sourced preparedness-content management to the
custom `/management/` portal. It does not implement Day 6 or Day 7 modules and
does not change susceptibility calculation.

## Delivered workflow

- `/management/dss-content/` lists stored guidance with truthful empty states,
  source/data status, susceptibility association, category, display order, and
  a separate content-workflow status.
- Search covers title, instruction, source name/organization, and attribution.
  Category, workflow-state, and susceptibility-result filters are server
  validated. Pagination keeps active filters.
- Authorized staff can create and edit drafts. Django ModelForms preserve input
  and provide field/form errors when validation fails.
- Associations use the existing four `SusceptibilityLevel` choices. No new
  classification, rule, threshold, or inference behavior was introduced.
- Source and public-facing attribution are recorded separately. Portal forms
  exclude restricted and retired source/status choices.
- Display order accepts the model's validated `0..32767` range. Ties remain
  deterministic through the existing secondary record-ID order.
- The state machine is `DRAFT -> IN_REVIEW -> APPROVED -> PUBLISHED`.
  Editors can submit or return content to draft; approval and publication use
  separate custom permissions. Published items must be unpublished before they
  can return to an editable path.
- Approval does not enable public output. Publishing uses a CSRF-protected POST,
  confirmation page, row lock, stale-state check, permission check, and final
  model/source/classification validation in one database transaction.
- Create, edit, and workflow transitions write limited Django `LogEntry`
  maintenance events without copying the guidance instruction into the log.
  Day 7 still owns the full audit-history interface.
- The create/edit screen includes a responsive resident-oriented phone preview,
  clearly labeled as a staff-only preview. Its JavaScript writes text with
  `textContent`; the form remains usable without it.
- The DSS service now requires both `is_enabled=True` and
  `workflow_status=PUBLISHED`. Draft, in-review, and merely approved content is
  not returned by resident-facing endpoints.

## Permissions

All routes first require an authenticated active staff account. Django model
permissions then enforce the operation on the server:

| Permission | Capability |
| --- | --- |
| `dss.view_guidanceitem` | Open the list and confirmation details |
| `dss.add_guidanceitem` | Create a draft |
| `dss.change_guidanceitem` | Edit drafts, submit for review, and return to draft |
| `dss.approve_guidanceitem` | Move an in-review item to approved |
| `dss.publish_guidanceitem` | Publish or unpublish eligible guidance |

The migration creates permission definitions but deliberately assigns no person
or group. Superusers receive permission through Django's normal superuser
behavior. The research team must assign the custom permissions to named local or
deployed accounts through its approved account-management process; `is_staff`
alone never authorizes a Day 5 mutation.

## Publication validation

Publishing demonstration guidance requires matching demonstration status and
source types for the guidance and enabled susceptibility classification.
Publishing approved guidance requires approved, publicly releasable,
non-demonstration sources and an enabled approved classification. Pending,
restricted, retired, mismatched, disabled, or stale records cannot publish.

The public selection service repeats the operating-mode filters on every read.
Revoking a source or classification therefore removes the item from subsequent
responses even if its stored workflow state has not yet been corrected.

## Database change

Migration `dss.0002_guidance_workflow` adds:

- `GuidanceItem.attribution`;
- `GuidanceItem.workflow_status`;
- `approve_guidanceitem` and `publish_guidanceitem` permissions; and
- the `guidance_enabled_only_when_published` database check constraint.

The data migration does not create guidance. Legacy enabled rows remain
published only when they satisfy the already-established demonstration or
official operating-mode policy, including their classification source. Other
legacy enabled rows become disabled drafts so they cannot be exposed
accidentally.

## Verification evidence

Verification used an isolated disposable PostgreSQL 17/PostGIS cluster under
ignored `tmp/`, bound to `127.0.0.1:55432`. It did not read or change the normal
application database or `.env`.

Commands and results:

```powershell
server\.venv\Scripts\python.exe server\manage.py check
# No issues.

server\.venv\Scripts\python.exe server\manage.py makemigrations --check --dry-run
# No changes detected.

server\.venv\Scripts\ruff.exe check server/dss server/admin_portal server/core/test_day4_api.py server/core/management/commands/seed_demo.py
# Passed.

server\.venv\Scripts\python.exe -m pytest -q server/dss server/admin_portal/test_dss_content.py server/core/test_day4_api.py --reuse-db
# 27 passed.

server\.venv\Scripts\python.exe -m pytest -q server --reuse-db
# 177 passed; 92 development warnings about the missing staticfiles output directory.

flutter analyze --no-pub
# No issues.

flutter test --no-pub
# 91 passed.
```

A dedicated migration test verifies an eligible legacy enabled item remains
published while a pending legacy enabled item becomes a disabled draft. A fresh
isolated database also applied every migration through
`dss.0002_guidance_workflow` successfully.

Headless Chrome checks covered the populated list and create/mobile preview at
1440x1024, 390x844, and 320x844. All pages had no horizontal overflow, the live
preview updated, the responsive table became labeled cards, and screenshots
were visually inspected. One desktop request for a missing favicon returned
404; no Day 5 asset or application JavaScript failed.

## Teammate steps after pulling

No runtime dependency changed. From the repository root:

```powershell
server\.venv\Scripts\python.exe -m pip install -r server\requirements.txt
server\.venv\Scripts\python.exe server\manage.py migrate --plan
server\.venv\Scripts\python.exe server\manage.py migrate
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe -m pytest -q server --reuse-db
```

Then assign only the required DSS permissions to approved staff accounts or
groups. Local accounts and permission assignments are database rows and are not
synchronized by Git. Do not run `seed_demo` merely to populate the portal, and
do not import or invent official guidance. An empty Day 5 list is valid.

## Remaining boundary

Day 4 parameter mutation remains blocked by the unapproved governance proposal,
scientific definitions, source/bounds, owner/validator assignments, and role
matrix. Day 5 does not resolve those decisions. Day 5 likewise does not assign
organizational publishers; it supplies enforceable permissions so the team can
assign confirmed authorities without a broad Day 7 role redesign.
