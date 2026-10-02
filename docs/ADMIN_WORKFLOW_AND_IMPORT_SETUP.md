# Admin workflows, reviewed imports, and DSS setup

Implementation handoff: 2 October 2026. This guide records implementation-time
evidence and the required setup after receiving the code. Git publication does
not migrate or deploy the application. No application/shared database migration,
official-data import, account creation, permission grant, or content publication
was performed during implementation.

## Architecture and scope

The resident Prepare tab, operational `/management/` portal, and technical
`/admin/` use the same `DSSFlowVersion` graph and content records. `GuidanceItem`
remains the reusable action library and assessment-API compatibility path.
See [DSS_EXPANSION_IMPLEMENTATION.md](DSS_EXPANSION_IMPLEMENTATION.md) for the
content-mapping matrix, public contract, Flutter changes, and publication rules.

The Admin upgrade is a convenience layer over existing workflow services, not a
new approval model. Combined actions run every normal validation, permission
check, transition, and audit event in one transaction. Any failure rolls back the
whole action. Published history, provenance, and resident eligibility remain
governed. Expert rules, thresholds, weights, susceptibility classification, GIS
methodology, and rainfall methodology were not changed. No AHP/WLC, live
monitoring, background polling, automatic warning/notification, forecast,
route-safety claim, live occupancy, or evacuation-order behavior was added.

## What you can test

- Center/source/guidance forms offer role-aware save-and-add-another and combined
  review actions. Complete draft flows can be saved and submitted together.
  Draft saving needs no confirmation; verification/public release remain explicit.
- Center forms show the selected source's organization, custodian, status,
  public-release flag, version/reference date, and limitations. Create or correct
  a pending source in an accessible inline dialog without losing center fields.
  Source problems link directly to source review.
- New center forms reuse the session's source, area, limitations, and documented
  verification date. Source reuse also reuses its custodian. Center name, address,
  contact information, and capacity are never copied as session defaults. Existing
  record edits are not overwritten by those defaults.
- Sources and areas have searchable selectors. Duplicate/validation errors retain
  entered values. Stale edits are rejected instead of overwriting newer work.
- Center detail shows a resident-eligibility checklist. Verification alone does
  not mean resident-visible: publication, approved/releasable source, supported
  geography, and safe API fields are checked separately on public reads.
- Review queues cover centers, sources, guidance, and structured flows, with
  checkboxes, filters, select-all-matching, validation reasons, and permitted next
  actions. Actions follow each model's actual state machine; unsupported states
  are not invented.
- Bulk preview names eligible and ineligible records. One explicit confirmation
  applies only the shown eligible subset atomically, with source/record revision
  and permission rechecks. Rejected records are counted and explained. A failure
  during execution rolls back all eligible changes, not just the failing row.
  Select-all-matching and uploads are bounded to 1,000 records; refine larger sets.
  Preview checks records individually; conflicting simultaneous publications can
  still fail the combined execution, which safely rolls back the batch.

An approved source is not necessarily publicly releasable. The explicit
"Save, verify and release approved source" action requires both center
verification and source-publication permissions, checks the source revision,
and may affect other records linked to that source. Ordinary verification never
silently grants source release. "Approve source and verify center" requires all
normal source metadata and permissions, and does not automatically release it.

Sources have no separate SUBMITTED state: pending sources already appear in the
source review queue. "Submit source and center" submits the center and logs a
review request for the pending source; it does not fabricate source approval or
send an external notification. A failed combined verification does not claim
that its rolled-back draft was saved. Use Save draft to keep unresolved work.

Capacity is optional, documented static information entered during verification.
Blank remains `None`, displayed as "Capacity not documented", never zero or live
occupancy. A non-verification save explicitly warns if entered capacity was not
recorded; capacity cannot be attached to an unverified draft as verified data.

## CSV / Excel workflow

Open `/management/evacuation-centers/import/` and download the exact CSV template:

```text
name,address,area_code,latitude,longitude,limitations
```

1. Use UTF-8 CSV, or open the template in Excel and save one worksheet as `.xlsx`.
   Keep the exact headers and order. Supply literal documented values, no formulas.
   `.xls`, macro workbooks, external workbook links, and multiple sheets are
   refused. Limits are 5 MB uploaded, 1,000 data rows, and 20 MB expanded workbook.
2. Select one authorized pending/approved non-demonstration source; its custodian
   is shared by the batch. Optional shared limitations apply only to blank row
   limitations. Confirm authorization and that the upload has no private,
   restricted, or personally identifiable material. Do not upload official data
   without authorization for that target and dataset.
3. Validate before importing. Every row receives errors/warnings, duplicate
   checks, and geographic checks. All colliding normalized names/coordinates are
   rejected, including numeric coordinate variants. Existing matches require
   explicit manual review, not automatic replacement.
4. Review valid/invalid counts, row details, the coordinate map, and the downloadable
   row-level error report. Map markers are neutral context, not classifications.
   Mapbox uses existing configuration; OSM is the fallback. The table remains
   usable without map assets. Missing geography is an explicit resident-exclusion
   warning; an unknown area code or coordinate outside recorded geometry is an
   error, never a guessed association.
5. Confirm import of the explicitly valid subset. Source/geography/duplicates are
   revalidated under locks. A stale context or failure imports nothing. A confirmed
   batch cannot be imported twice. All imported centers are Draft/Pending, with
   unknown capacity, even when the source is approved.
6. Use the batch's review-queue link to bulk-submit its centers. Review/approve
   the shared source through its normal workflow, then bulk-verify otherwise
   eligible centers using a documented verification date. Public release and
   resident geography/API eligibility remain separate requirements.

Invalid rows never become `EvacuationCenter` records. Their submitted values and
validation messages are retained in staff-only **quarantined batch staging** so
the reviewer can inspect/download the report; this is not a second resident data
store. No raw upload file or sensitive local path is saved. Batch UUID, source
revision, uploader/time, basename, validation counts, confirming importer/time,
imported row IDs, and audit events are recorded. Technical Admin exposes batches
read-only; it cannot bypass the reviewed importer.

No import or seed is required merely to install this upgrade. The importer is
currently for centers; no generalized agency/GIS importer or automatic official
data ingestion was added.

## Governance still requiring decisions

Implementation does not establish BDRRMO approval, permission to reproduce board
wording, current applicability, verified contact details, or adoption as thesis
methodology. Candidate transcriptions remain "Pending BDRRMO validation — not
public guidance". No candidate board transcription or official dataset was
imported/published here. The optional DSS test draft is synthetic/paraphrased
DEMONSTRATION material, not BDRRMO-authored/approved guidance; it is not published
by setup. Existing `presentation-1` is not overwritten.

Operational alert colors, water-level markers, PAGASA warnings, and susceptibility
remain distinct. Staff-only references are excluded from resident serialization.

The existing permission model does not enforce different author/reviewer people.
Combined actions are available only to actors holding every existing permission;
this task does not invent a self-approval entitlement or new institutional role.
If the team requires separate-person review, document and implement that policy
before granting combined approval authority. Identify the named reviewers,
publishers, source custodians, and approved content first. A separate external
BDRRMO/LGU tenant role was not created; identity, organization ownership, record
visibility, drafting/review/approval/publication/retirement authority require a
separate decision before that portion can be implemented.

## Local setup after receiving these changes

These commands are for your authorized **local development** database, not an
unapproved shared/deployed target. Existing `.env`, PostgreSQL/PostGIS, and virtual
environment setup remain in [COMPLETE_WINDOWS_SETUP_GUIDE.md](COMPLETE_WINDOWS_SETUP_GUIDE.md).
Do not commit credentials, databases, batch uploads, or restricted research data.

Two additive migrations are included:

- `dss.0004_expanded_structured_content`: phased/source-backed DSS content and
  flow provenance, with preservation of published graph/history.
- `evacuation.0003_reviewed_center_import_batch`: reviewed staff-only import staging
  and audit metadata; no alteration or automatic import of existing centers.

New runtime packages are `openpyxl>=3.1.5,<3.2` for `.xlsx` parsing and
`defusedxml>=0.7.1,<0.8` for XML hardening, installed through requirements.
`et_xmlfile` is installed transitively. There is no new Flutter or Node dependency.

From the repository root in PowerShell:

```powershell
Set-Location C:\Users\User\Documents\GitHub\FloodSense
.\server\.venv\Scripts\python.exe -m pip install -r server\requirements.txt
.\server\.venv\Scripts\python.exe server\manage.py migrate --plan
.\server\.venv\Scripts\python.exe server\manage.py migrate
.\server\.venv\Scripts\python.exe server\manage.py check
.\server\.venv\Scripts\python.exe server\manage.py runserver 127.0.0.1:8000
```

Sign in with your existing staff account:

- [Operational portal](http://127.0.0.1:8000/management/)
- [Centers](http://127.0.0.1:8000/management/evacuation-centers/)
- [Reviewed CSV/Excel import](http://127.0.0.1:8000/management/evacuation-centers/import/)
- [Center review queue](http://127.0.0.1:8000/management/review/centers/)
- [Source review queue](http://127.0.0.1:8000/management/review/sources/)
- [Guidance review queue](http://127.0.0.1:8000/management/review/guidance/)
- [Flow review queue](http://127.0.0.1:8000/management/review/flows/)
- [Structured Prepare flows](http://127.0.0.1:8000/management/dss-content/flows/)
- [Technical Admin](http://127.0.0.1:8000/admin/)

Migrations do not copy local users/data or grant workflow permissions. `is_staff`
alone is not a publisher or verifier. Center editing/import needs the relevant
add/change/view permissions; verification needs `verify_evacuationcenter`.
Source approval/release need `approve_datasource` / `publish_datasource`.
Flow review/publication need `review_dssflowversion` / `publish_dssflowversion`.
Assign existing Django permissions only according to approved team authority.

For PC Flutter preview, keep Django running and use another terminal:

```powershell
Set-Location C:\Users\User\Documents\GitHub\FloodSense\mobile
flutter pub get
flutter run -d chrome --web-hostname localhost --web-port 3000
```

Classify a hypothetical scenario, then open Prepare. Its content must come from
an eligible, explicitly published `preparedness` flow for the assessment mode;
otherwise the truthful unavailable state is expected. To prepare/review the
optional non-public synthetic draft, follow the guarded command and retirement/
publication instructions in [DSS_EXPANSION_IMPLEMENTATION.md](DSS_EXPANSION_IMPLEMENTATION.md).
Applying migrations does not publish new DSS content.

For Android, retain the existing private build configuration and USB setup in
[MAP_PRESENTATION_PROVIDER_GUIDE.md](MAP_PRESENTATION_PROVIDER_GUIDE.md). The
backend URL must be reachable from the phone (not its own `127.0.0.1` unless using
the documented USB reverse workflow). Mapbox on Android requires the public token
in Flutter build defines; adding it only to Django `.env` is not sufficient.
Web/desktop Flutter intentionally retains its existing OSM fallback. This task
does not modify those provider rules or install an APK on your device.

## Verification and observed efficiency

The complete backend suite passed **783 tests**, including classification/API
regressions. The final import/workflow regression suite passed **19 tests** after
adding malformed-XLSX coverage. The fresh migration, focused workflows, and
live-server browser check also passed together (**21 tests**). Django checks,
migration consistency, Ruff, and whitespace checks pass. URLField Django-6
future-default deprecation warnings remain non-failing.

Flutter analysis passed and **228 Flutter tests passed**. The prior DSS slice also
built a debug APK successfully; it was not installed/tested on physical hardware.
No new mobile code/package changes were needed for this additional Admin slice.

Portal QA covered desktop 1440px and narrow 390/320px forms, long source names,
inline source errors/correction/creation, preserved center values, keyboard
actions, review filtering, select-all-matching preview, coordinate preview, and
actual mixed-validity import confirmation. The import map had positive canvas
height and visible controls/marker/attribution with the OSM fallback; no account-
dependent Mapbox network/device claim is made. Earlier DSS QA also covered
360/390 logical-pixel Flutter layouts, long content, 150% text scaling, and
200% unavailable-state scaling. Screenshots are ignored local `tmp/` artifacts.

Measured workflow evidence, not a timed productivity estimate:

- Browser QA created and submitted a center with **one editor submission**, no
  intermediate transition-confirmation page. Inline source creation stayed in
  the same editor and preserved the center name through an intentional error.
- Backend tests saved, submitted, and verified a center in **one combined form
  action**, preserving each transition's audit event and atomic rollback.
- A regression imported **200 centers**, bulk-submitted all 200, approved their
  one shared source, and bulk-verified all 200. All blank capacities stayed
  unknown. Test centers lacking resident geographic eligibility remained
  excluded: bulk verification did not bypass the public policy.

The ordinary configured database role could not create a test database. No grants
were weakened and tests were not pointed at development data. For this Windows
installation, the checked-in helper starts a separate loopback PostgreSQL 17
cluster, redirects only the test process, restores `DATABASE_URL`, and stops the
cluster afterward. Synthetic stopped clusters are retained under ignored `tmp/`
for triage. The helper requires the existing PostgreSQL/PostGIS installation and
an unused port; it is QA tooling, not application setup.

```powershell
Set-Location C:\Users\User\Documents\GitHub\FloodSense
& .\scripts\test_operations_isolated.ps1 -TestArgs @('server','--create-db','-q')
```

Optional browser QA uses Playwright with the existing Chrome installation, not a
runtime dependency or automatic browser download:

```powershell
.\server\.venv\Scripts\python.exe -m pip install playwright
& .\scripts\test_operations_isolated.ps1 -TestArgs @('server/admin_portal/test_record_workflows.py','server/evacuation/test_import_migration.py','scripts/verify_record_workflow_layout.py','--create-db','-q')
```

Mobile checks:

```powershell
Set-Location C:\Users\User\Documents\GitHub\FloodSense\mobile
flutter analyze --no-pub
flutter test --no-pub
```

## Exact additional Admin/import files

The DSS/Flutter slice's exact files are listed in
[DSS_EXPANSION_IMPLEMENTATION.md](DSS_EXPANSION_IMPLEMENTATION.md). The following
are additions/changes for this Admin/import slice, including files overlapping
that slice:

- Services/models/migration: `server/core/record_workflow.py`,
  `server/admin_portal/record_workflows.py`, `server/admin_portal/bulk_workflows.py`,
  `server/admin_portal/operations_views.py`, `server/admin_portal/forms.py`,
  `server/admin_portal/views.py`, `server/admin_portal/urls.py`,
  `server/admin_portal/dss_forms.py`, `server/admin_portal/dss_views.py`,
  `server/evacuation/models.py`, `server/evacuation/admin.py`,
  `server/evacuation/imports.py`, `server/evacuation/workflow.py`,
  `server/evacuation/migrations/0003_reviewed_center_import_batch.py`,
  `server/provenance/workflow.py`, `server/dss/workflow.py`,
  `server/requirements.txt`.
- Templates in `server/admin_portal/templates/admin_portal/`:
  `data_source_detail.html`, `data_source_form.html`, `data_source_list.html`,
  `evacuation_center_detail.html`, `evacuation_center_form.html`,
  `evacuation_center_list.html`, `guidance_form.html`, `guidance_list.html`,
  `dss_editor.html`, `dss_flow_detail.html`, `dss_flow_list.html`,
  `center_import.html`, `center_import_detail.html`, `review_queue.html`;
  includes `center_inline_source.html`, `center_workflow_actions.html`,
  `source_workflow_actions.html`, `flow_inline_actions.html`,
  `inline_source_form.html`, `review_link.html`, `save_actions.html`.
- Assets in `server/admin_portal/static/admin_portal/`:
  `css/operations.css`, `js/record_workflows.js`, `js/batch_import_map.js`.
- Tests: `server/admin_portal/test_record_workflows.py`,
  `server/evacuation/test_import_migration.py`,
  `server/admin_portal/test_dss_content.py`,
  `server/admin_portal/test_gps_day4_centers.py`,
  `server/admin_portal/test_gps_day5_security.py`.
- QA/handoff: `scripts/test_operations_isolated.ps1`,
  `scripts/verify_record_workflow_layout.py`,
  `docs/ADMIN_WORKFLOW_AND_IMPORT_SETUP.md`,
  `docs/DSS_EXPANSION_IMPLEMENTATION.md`.

Pre-existing user changes to `AGENTS.md`, `README.md`, and
`docs/FLOOD_SUSCEPTIBILITY_METHODOLOGY_PROPOSAL.md` were preserved. The proposal
was not implemented. These unrelated files are excluded from the implementation
release commit. Local database records and credentials remain local.
