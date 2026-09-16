# FloodSense Admin Frontend — Day 1 Guide

## Outcome

Day 1 establishes the custom, responsive administration portal at
`/management/`. It is distinct from Django's technical `/admin/` interface and
uses the high-fidelity FloodSense visual direction.

Implemented today:

- staff-only email/password sign-in;
- POST-only sign-out and session handling;
- password-assistance information page;
- desktop sidebar and mobile navigation drawer;
- responsive overview page;
- protected routes for all planned administration modules; and
- explicit development-data and publication-safety notices.

The module routes are intentionally placeholders. Their workflows are delivered
on their assigned days rather than simulated with invented records or counts.

## Run locally

From the repository root in PowerShell:

```powershell
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" runserver 0.0.0.0:8000
```

Open:

```text
http://127.0.0.1:8000/management/
```

Sign in with an existing active Django account whose `is_staff` flag is enabled.
Local administrator accounts remain local to each developer's database and are
not synchronized through Git.

If a local administrator does not exist yet:

```powershell
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" createsuperuser
```

## Access and governance boundaries

- Anonymous visitors are redirected to the custom portal sign-in page.
- Authenticated non-staff users receive a forbidden response.
- Superusers can open `/admin/` for technical maintenance.
- Ordinary portal users do not receive a raw expert-rule editor.
- The fixed inference method remains controlled by the research design and
  application code. Later screens may expose only authorized, validated, and
  versioned assessment parameters.
- The portal must not present provisional MGB layers, fictional classifications,
  or unapproved rainfall records as official information.

## Verify after pulling

Day 1 does not add or change database models, so it creates no migration. After
pulling, teammates should use their already configured environment and run:

```powershell
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" check
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" makemigrations --check --dry-run
& ".\server\.venv\Scripts\python.exe" -m pytest -q --reuse-db
```

Running the normal committed migrations after a pull remains safe and is still
part of the standard team workflow, even though this particular day has no new
migration.

## Planned protected routes

| Route | Planned work |
| --- | --- |
| `/management/map-data/` | Map data review and publication workflow |
| `/management/assessment-parameters/` | Authorized parameter governance |
| `/management/dss-content/` | Preparedness guidance management |
| `/management/rainfall-references/` | Scenario rainfall reference management |
| `/management/evacuation-centers/` | Verified evacuation-center records |
| `/management/sources-content/` | Provenance and public content |
| `/management/audit-history/` | Administrative activity history |
| `/management/settings/` | Account preferences and future authorized parameters |

## Day 2 handoff

Day 2 should connect the overview to truthful database-backed summaries and
review queues. It must not replace unavailable official data with fabricated
statistics.
