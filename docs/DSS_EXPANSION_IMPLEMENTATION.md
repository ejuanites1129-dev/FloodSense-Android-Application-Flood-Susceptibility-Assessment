# DSS expansion — implementation and review handoff

Date: 2 October 2026. Implementation work does not establish BDRRMO approval.

The subsequent Admin workflow and reviewed CSV/Excel import slice is documented
in [ADMIN_WORKFLOW_AND_IMPORT_SETUP.md](ADMIN_WORKFLOW_AND_IMPORT_SETUP.md).
Use that guide for the complete current dependency/migration setup, combined
actions, bulk review, import safeguards, and updated verification results.

## Content mapping decided before schema changes

| Poster element | Resident / staff treatment | Canonical representation | Source / status | Validation owner |
| --- | --- | --- | --- | --- |
| Household preparations | Ordered household checklist only after publication | DSSContentBlock: HOUSEHOLD_ACTION, BEFORE / ALWAYS; optional outcome for priority | Source-backed; board transcriptions remain pending drafts | Assigned BDRRMO content reviewer, still to be confirmed |
| Operational Green / Yellow / Orange / Red stages | Staff reference; no susceptibility mapping | DSSContentBlock.reference_stage, STAFF_ONLY audience | Photo-observed candidate, pending validation | BDRRMO reviewer |
| Water-level markers and exposure/population lists | Non-public staff reference | STAFF_ONLY risk reference block | Pending; no resident serialization | BDRRMO reviewer |
| Scenario interpretation | Conditional educational explanation | SCENARIO_EXPLANATION block in a versioned flow | Synthetic demonstration or reviewed public source | Authorized DSS reviewer / publisher |
| Before / during / after household actions | Separate educational phase groups | ContentBlock.phase: BEFORE / DURING / AFTER / ALWAYS | Mode-eligible source and flow publication required | Authorized content reviewer |
| Agency capabilities | Separate “What local authorities may coordinate” section | AUTHORITY_ACTIVITY block | Candidate draft until reviewed | BDRRMO reviewer |
| Communication methods | Names as text; clickable links require explicit verification | OFFICIAL_CHANNEL block, verified HTTPS public link | Pending links withheld | Source custodian / reviewer |
| Monitoring indicators / equipment / frequency | Collapsed education; no live monitoring or schedules | MONITORING_REFERENCE block | Pending until public release review | BDRRMO reviewer |
| Sir Johny interview recommendation | Staff evidence distinction only | Internal source notes, excluded from public serializer | User-reported; approval not established | Research team and BDRRMO reviewer |

## Architecture contract

DSSFlowVersion and its graph remain canonical. GuidanceItem remains the assessment
API compatibility library and may be linked to an outcome. A minimal
DSSContentBlock extension stores ordered phase/type/audience content once per
flow, optionally scoped to an outcome. It carries source, status, locator,
attribution, limitations, dates, and verified channel-link metadata. Flow-level
public provenance is expanded without serializing internal source notes,
processing notes, permitted-use restrictions, or reviewer identity.

Public flow selection explicitly uses the `preparedness` code by default and the
completed assessment operating mode; it fails closed on unavailable/ineligible
content. Existing response keys stay available with additive contract version 2
fields. Staff preview uses the same serializer, marked as non-public preview.

Published/retired versions and their graph/content/level associations are frozen.
New work uses a cloned draft, review, publication, and explicit retirement. The
existing `presentation-1` record is never rewritten. Answers remain in client
memory. No assessment rule or classification algorithm is part of this change.

## What is implemented and what is not published

Implemented infrastructure includes the canonical phase/content model, additive
API serialization, immutable assessment context in Flutter, expanded Prepare
rendering, and controlled editing/review/publication over the same records in
both staff surfaces. The flat assessment-response API remains compatible; the
resident result card no longer repeats that flat guidance beside Prepare.

`prepare_dss_expansion` is an optional **local-development** command. It creates
`preparedness / presentation-2` as a **DRAFT / DEMONSTRATION** with six questions,
twelve options, two outcomes, and fifteen phased content blocks. The material
is synthetic/paraphrased, has pending-validation warnings, contains no board
transcriptions or private interview material, and does not claim BDRRMO
authorship. Its 64 answer paths are deterministic. Answer recaps and household
priorities use the canonical option supporting text, held only in client memory.
Rerunning an identical owned draft is read-only; an altered or foreign draft is
refused rather than overwritten. The command does not invoke `seed_demo` or
create/alter susceptibility levels or Expert System records.

**No development/shared application database was migrated, seeded, or published
as part of this implementation.** Database verification uses isolated test
databases. Existing `presentation-1` remains unchanged. The new demonstration
does not become resident-visible merely by applying the migration or preparing
the draft: an authorized reviewer/publisher must review it, explicitly retire
the current version, and publish the new version for the same mode. Publication
does not automatically retire another version. A gap between retirement and
publication produces a truthful unavailable state.

No new BDRRMO-authored or approved/public content has been established. Exact
board wording, authority approval, current validity, reproduction permission,
verified contact links, and validation ownership remain pending. Do not mark
candidate transcriptions APPROVED or publish them until those decisions are
documented. Operational board stages can be stored only as staff-only
references, never as a susceptibility or PAGASA warning mapping. No thresholds,
exposure/population totals, ordinance interpretation, or evacuation-order
wording was imported.

## Migration and safeguards

New migration: `server/dss/migrations/0004_expanded_structured_content.py`.

It adds nullable/blank flow provenance fields and `DSSContentBlock`, including
phase, type, audience, order, source locator, public attribution/limitations,
effective/review/expiry dates, and optional verified public HTTPS channel URLs.
A database constraint restricts board-stage references to STAFF_ONLY. The
existing outcome-to-guidance foreign key now uses PROTECT so deleting a linked
guidance record cannot silently rewrite structured publication history. This
is an additive schema change, not a content import or old migration rewrite.
An explicit migration regression verifies preservation of existing published
flow/graph/guidance records.

Public selection identifies `preparedness` explicitly, requires one published
version for the assessment mode and eligible level/source/content, and fails
closed on invalid or unavailable data. Contract version 2 keeps existing keys
and adds public-safe provenance and content blocks. Internal source notes,
private interview information, processing/restriction notes, reviewer identity,
and staff-only blocks are not serialized. Approved/public verified HTTPS URLs
alone become references; the Flutter reference dialog lets users copy them
without adding an external-link package.

The publication workflow records the flow review date, while the source retains
its separately governed review date. An item-level review date is not inferred
from those dates or claimed as BDRRMO approval: blank item dates remain visibly
"Not recorded" in staff inspection. Existing documented item-review dates can
be maintained in technical Admin while the parent is a draft.

Draft edits and transitions lock the parent flow. Children and level associations
advance its revision timestamp, making stale portal transitions return HTTP 409.
Published/retired history and in-review content are frozen; return-to-draft is
an explicit review action. Validation checks one start, reachability of every
question/outcome, acyclicity, exact destinations, same-flow links, source/mode
eligibility, linked guidance, dates, and public-link rules. These application
guards do not provide protection against privileged raw SQL.

Django's implicit level-association model suppresses ordinary save/delete
signals. Its existing table therefore has guarded runtime default/base managers
and instance writes, including bulk operations, with regression tests. No new
association table or historical migration is introduced. Conflict-updating
bulk inserts are rejected for governed graph/association/guidance records.
Low-level private ORM internals, like raw SQL, are outside these application
guards.

GuidanceItem wording and association metadata are also frozen when referenced
by an IN_REVIEW, PUBLISHED or RETIRED structured flow. To revise that wording,
create a new library record and link it from a new draft flow version. Existing
unlinked library behavior remains compatible. Status/availability withdrawal is
still permitted and causes the public selection to fail closed; it is not a way
to replace frozen content. Draft-linked guidance edits advance the flow revision
token too.

Existing Django permissions remain authoritative. `is_staff` alone grants no
publication power. Viewers need `view_dssflowversion`; editors need relevant
add/change permissions (and `change_dssflowversion` for node editing); submit
and return use `review_dssflowversion`; publish/retire use
`publish_dssflowversion`; clone requires add/change flow permissions. Migration
creates the standard content-block permissions, but this task grants no new
permissions/accounts and creates no external-organization role. Real successful
edits/transitions write Django Admin LogEntry audit records without answer or
private-source payloads.

## How to inspect and rehearse locally

After applying the migration below, sign in to the existing operational staff
account and open `/management/dss-content/flows/`. The inventory is separate
from assessment guidance. Draft detail pages provide ordered graph/content,
counts, public-source metadata, validation failures, draft editors, and a
resident-width preview. Technical inspection is at `/admin/dss/dssflowversion/`
and `/admin/dss/dsscontentblock/`. Both interfaces use the same database rows.

For existing demonstration installations only, preparing the optional synthetic
draft is a separate, explicitly local step:

```powershell
Set-Location C:\Users\User\Documents\GitHub\FloodSense
.\server\.venv\Scripts\python.exe server\manage.py prepare_dss_expansion --confirm-local-development
```

The command requires existing eligible demonstration susceptibility levels and
refuses to invent missing ones. Inspect its DRAFT in the portal; verify sources,
limitations, graph and preview, then use the existing controlled review workflow
only when you are authorized to make it available as clearly labeled demo
content. Do not use this command on a shared/deployed or official-data database
without separate authorization. Existing `seed_demo` is not a required upgrade
step and should not be run merely to update DSS.

In the resident application, classify a hypothetical scenario and open Prepare.
The completed assessment supplies immutable mode, susceptibility, selected
rainfall/duration labels, area and knowledge version. Questions, ordered
household actions, separate educational During/After references, authority
activities, verified channels, collapsed monitoring education and public sources
come from the selected published backend version. Back/Restart clears or rewinds
only memory; answers do not alter classification or write server records.
If no eligible published flow exists, use the truthful unavailable/Retry state,
not an invented checklist. OFFICIAL assessments cannot select demonstration
content through Flutter.

## Teammate setup after pulling these changes

This DSS slice adds no runtime package, but the subsequent Admin importer adds
`openpyxl` and `defusedxml` through `server/requirements.txt`. Use the existing
Windows setup guide for PostgreSQL/PostGIS, `.env`, Python virtual environment,
Flutter, Android and Mapbox setup; do not commit credentials. Apply the DSS and
Admin-import migrations to each authorized local database as described in the
linked Admin setup guide. From the repository root:

```powershell
.\server\.venv\Scripts\python.exe -m pip install -r server\requirements.txt
.\server\.venv\Scripts\python.exe server\manage.py migrate --plan
.\server\.venv\Scripts\python.exe server\manage.py migrate
.\server\.venv\Scripts\python.exe server\manage.py check
.\server\.venv\Scripts\python.exe server\manage.py makemigrations --check --dry-run
.\server\.venv\Scripts\ruff.exe check server/dss server/admin_portal
.\server\.venv\Scripts\python.exe -m pytest -q server --reuse-db
```

From the mobile directory:

```powershell
Set-Location C:\Users\User\Documents\GitHub\FloodSense\mobile
flutter pub get
flutter analyze --no-pub
flutter test --no-pub
flutter build apk --debug
```

The plain APK command above is a compilation check, not a configured phone
release. For an actual phone rehearsal, retain your existing private
`FLOODSENSE_API_BASE_URL`, `FLOODSENSE_MAP_PROVIDER` and public
`MAPBOX_ACCESS_TOKEN` build defines from
`docs/MAP_PRESENTATION_PROVIDER_GUIDE.md`; the default Android API address is
for an emulator, and omitting the public Mapbox token selects OSM. Web/desktop
Flutter builds intentionally use the existing OSM fallback. This DSS change
does not modify map-provider configuration or require a new Mapbox account.

For the existing PC browser rehearsal, run Django from the repository root in
one terminal, then Flutter in another:

```powershell
.\server\.venv\Scripts\python.exe server\manage.py runserver 127.0.0.1:8000
```

```powershell
Set-Location C:\Users\User\Documents\GitHub\FloodSense\mobile
flutter run -d chrome --web-hostname localhost --web-port 3000
```

Existing superusers, staff users, permissions and source/content rows are local
database state, not synchronized by Git. Do not migrate a shared/deployed target
or import official data without explicit approval. No seed/import is required
to preserve the existing published experience. See the optional draft rehearsal
above only if preparing synthetic content is desired.

## Verification evidence

Verified for the original DSS slice: all 763 backend tests passed, including the unchanged scientific/API
regressions; 97 focused DSS/portal/Day 4/demo tests passed. The strengthened
migration preservation test also passed independently after adding explicit
legacy question/option/outcome/linked-guidance/M2M assertions. Browser layout QA
passed one live-server test covering all viewport/state combinations. Django
system checks and migration consistency pass; Ruff and task-file whitespace
checks pass. Django emitted URLField future-default deprecation warnings, not
test failures.

Flutter analysis passes; all 228 Flutter tests pass, including expanded DSS
regressions for real-contract duplicate disclaimers and numeric-ID tie ordering
consistent with the backend. Distinct outcome/library provenance is parsed and
rendered without repeating instructional bodies. The debug APK builds at
`mobile/build/app/outputs/flutter-apk/app-debug.apk`. Gradle reported existing
Mapbox Kotlin-plugin and Android SDK-tool compatibility warnings, but the build
succeeded; no package upgrades were performed. Optional Flutter visual-QA tests
passed and readable captured layouts were inspected, including long text,
During/After phase separation, unavailable states and distinct outcome/library
source expansions. No physical-device installation/testing, release build or
deployment was performed.

Browser QA uses Playwright, installed locally in `server/.venv` for QA only and
not added to runtime requirements, with installed Chrome and an isolated Django
live-server test database; it is not a runtime dependency or a development
database test.
To reproduce this optional browser check:

```powershell
Set-Location C:\Users\User\Documents\GitHub\FloodSense
.\server\.venv\Scripts\python.exe -m pip install playwright
.\server\.venv\Scripts\python.exe -m pytest -q scripts/verify_dss_expansion_layout.py --reuse-db
```

The QA script uses the existing Chrome installation at
`C:\Program Files\Google\Chrome\Application\chrome.exe`; it downloads no
browser. Portal desktop 1440px and narrow 390/360px captures test long text,
empty/incomplete states, keyboard actions and 150% text sizing. Flutter widget
captures at 390/360 logical pixels cover 150% text scaling and 200% unavailable
state, using local Arial and Material icon fonts only for optional screenshot
generation. These are widget-layout checks, not proof of physical-device testing.
Screenshots are ignored local artifacts in `tmp/dss-expansion-qa/`.

To reproduce optional readable Flutter captures with this Windows installation:

```powershell
Set-Location C:\Users\User\Documents\GitHub\FloodSense\mobile
$env:DSS_VISUAL_QA_FONT_DIRECTORY = 'C:\Windows\Fonts'
$env:DSS_VISUAL_QA_ICON_FONT = 'C:\Users\User\development\flutter\bin\cache\artifacts\material_fonts\MaterialIcons-Regular.otf'
flutter test --no-pub --dart-define=DSS_VISUAL_QA=true test/dss_expansion_test.dart
```

## Exact task files

Backend:

- `server/dss/models.py`
- `server/dss/services.py`
- `server/dss/flow_workflow.py`
- `server/dss/admin.py`
- `server/dss/migrations/0004_expanded_structured_content.py`
- `server/dss/management/__init__.py`
- `server/dss/management/commands/__init__.py`
- `server/dss/management/commands/prepare_dss_expansion.py`
- `server/dss/test_expanded_flow.py`
- `server/dss/test_expansion_migration.py`
- `server/core/test_dss_expansion_draft.py`
- `server/core/test_seed_demo.py` (existing refresh test now preserves published linked guidance)

Operational staff portal:

- `server/admin_portal/views.py`
- `server/admin_portal/urls.py`
- `server/admin_portal/dss_forms.py`
- `server/admin_portal/dss_views.py`
- `server/admin_portal/templates/admin_portal/guidance_list.html`
- `server/admin_portal/templates/admin_portal/dss_flow_list.html`
- `server/admin_portal/templates/admin_portal/dss_flow_detail.html`
- `server/admin_portal/templates/admin_portal/dss_editor.html`
- `server/admin_portal/templates/admin_portal/dss_flow_preview.html`
- `server/admin_portal/static/admin_portal/css/dss_flow.css`
- `server/admin_portal/static/admin_portal/js/dss_flow_preview.js`
- `server/admin_portal/test_structured_dss_content.py`

Flutter:

- `mobile/lib/data/dss/structured_dss_repository.dart`
- `mobile/lib/features/dss/dss_assessment_context.dart`
- `mobile/lib/features/dss/dss_controller.dart`
- `mobile/lib/features/dss/dss_flow_view.dart`
- `mobile/lib/features/home/resident_shell.dart`
- `mobile/lib/features/assessment/multi_step_assessment_screen.dart`
- `mobile/lib/features/assessment/widgets/assessment_result_card.dart`
- `mobile/test/dss_expansion_test.dart`
- `mobile/test/hybrid_resident_shell_test.dart`
- `mobile/test/multi_step_and_dss_test.dart`

QA and handoff:

- `scripts/verify_dss_expansion_layout.py`
- `docs/DSS_EXPANSION_IMPLEMENTATION.md`

Unrelated pre-existing edits to `AGENTS.md`, `README.md`, and
`docs/FLOOD_SUSCEPTIBILITY_METHODOLOGY_PROPOSAL.md` were preserved and are not
part of this task or its release commit. The proposal was not implemented.
Git publication does not transfer local database records or publish DSS content.
Expert rules, thresholds, weights, classifications, GIS methodology
and assessment behavior remain unchanged. No background monitoring, live
warning, forecasting, notifications, route-safety claim or evacuation-order
behavior was added.
