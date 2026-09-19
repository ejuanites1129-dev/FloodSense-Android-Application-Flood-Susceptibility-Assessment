# FloodSense Admin Web - Seven-Day Implementation Plan

**Plan status:** Days 1-3 and 5-7 implemented; Day 4 mutation remains blocked by governance decisions

**Updated:** 19 September 2026

**Interface:** Custom Django portal under `/management/`

## Purpose

This is the implementation handoff for the designed FloodSense Admin web
application. It gives teammates and coding agents enough context to continue a
day independently without relying on a private conversation.

The sequence and deliverables reflect the research team's updated seven-day
Admin Web UI timeline supplied on 17 September 2026. This records the team's
implementation plan, not a new claim of thesis-adviser approval. Day numbers
identify development stages; calendar dates have not been assigned.

The custom portal is the ordinary administrative interface. Django's `/admin/`
remains a technical maintenance surface for developers and authorized research
maintenance; it is not the final designed interface.

All work must also follow:

- `TA_CONSULTATION_SYSTEM_DECISIONS.md`;
- `TEAM_DATABASE_AND_GIT_WORKFLOW.md`;
- `COMPLETE_WINDOWS_SETUP_GUIDE.md`; and
- the applicable `research_data/*/README.md` for data work.

## Non-negotiable implementation boundaries

- FloodSense is scenario-based, not a real-time monitoring or warning system.
- Do not add background timers, continuous polling, live rainfall claims, or
  autonomous alerts.
- Do not expose raw Expert System rules, conditions, or algorithm editing to
  ordinary portal administrators.
- Only validated, authorized, versioned parameters may affect assessments.
- Never invent official-looking counts, thresholds, classifications, guidance,
  evacuation centers, or source metadata.
- Provisional, demonstration, pending, approved, restricted, and retired data
  must remain distinguishable.
- UI hiding is not authorization; every mutation requires server-side checks.
- New model fields require a reviewed migration and tests.
- Do not alter the Flutter/API contract incidentally while building Admin pages.

## Current status

| Day | Status | Main outcome |
| --- | --- | --- |
| 1 | Complete | Authentication, responsive shell, navigation, Settings placeholder |
| 2 | Complete | Truthful operational dashboard and limited recorded maintenance activity |
| 3 | Complete | Read-only map, separate geographic layers, source/status review |
| 4 | In progress—awaiting governance decisions | Read-only Settings and governance proposal; mutation workflow awaits approval |
| 5 | Complete | Permission-controlled DSS preparedness-content workflow |
| 6 | Complete with documented rainfall-editing boundary | Read-only rainfall references, center verification, and provenance workflow |
| 7 | Complete | Audit history, permissions, validation, responsive UI, and regression QA |

## Day 1 - Administration foundation

### Delivered

- staff-only custom sign-in and POST-only sign-out;
- responsive desktop sidebar and mobile drawer;
- FloodSense branding and fixed-height active navigation;
- account menu containing Settings and Sign out;
- reusable visual tokens, buttons, forms, cards, notices, and layout styles;
- protected placeholder routes for planned modules; and
- explicit development-data and publication-safety messaging.

### Acceptance state

- anonymous users are redirected to sign-in;
- authenticated non-staff users receive HTTP 403;
- every custom portal route is protected;
- navigation works at desktop and mobile widths; and
- no model change or migration was introduced.

See `ADMIN_FRONTEND_DAY_1_GUIDE.md` for commands and route details.

## Day 2 - Functional operational dashboard

### Goal

Replace the Day 1 build checklist with a useful, read-only overview of the data
already stored in the current local database.

### Implement

1. Add a focused dashboard query/service layer instead of placing unrelated ORM
   queries directly in the template.
2. Display truthful database-backed counts for geographic areas, data sources,
   DSS guidance items, available assessment parameters, and records needing
   review. Define parameter availability using authorized scenario/reference
   records the current models actually support; do not count raw expert rules
   as editable parameters.
3. Group or label summaries by the existing publication status where useful, so
   demonstration records cannot look approved.
4. Add a review-attention panel using only status signals the current models can
   actually support.
5. Add recent administrative activity using an actual recorded event source,
   with clear labels for its coverage. If no auditable event source exists,
   show an explicit unavailable state and record the outstanding dependency;
   do not infer administrator actions from modification timestamps.
6. Add quick actions linking to the protected Map data, Settings, DSS content,
   and Sources sections.
7. Preserve an explicit data-safety notice and meaningful empty states when no
   approved records exist, even if provisional or demonstration records exist.
8. Keep raw rules, rule conditions, priorities, and inference details out of the
   ordinary dashboard.

### Do not implement on Day 2

- no new scientific thresholds or classifications;
- no invented "official" statistics;
- no editable forms or bulk actions;
- no fake recent-activity feed if an audited event source does not yet exist;
- no schema change merely to make a dashboard card look populated; and
- no background refresh, polling, timers, or live-status claims.

### Required tests

- anonymous and non-staff access remains blocked;
- an empty database renders zero/empty states without errors;
- demonstration and approved records are not combined under an official label;
- counts match records created by the test;
- recent activity matches recorded events, or truthfully states that its source
  is unavailable; and
- the dashboard does not expose raw expert-rule management links.

### Day 2 completion evidence

- screenshots at desktop and mobile widths;
- Django system check;
- `makemigrations --check --dry-run` reports no unintended model change; and
- focused tests plus the complete backend test suite pass.

### Verified completion - 18 September 2026

The dashboard now uses five read-only summary queries, separates all recorded
publication statuses, and displays safe limited Django maintenance activity.
The portal suite passed 35 tests and the complete backend suite passed 124.
Empty and populated layouts were verified at desktop, tablet, and mobile widths;
Flutter analysis, 91 Flutter tests, the debug APK build, and live API-client
integration checks passed. No models or migrations changed.

See `ADMIN_FRONTEND_DAY_2_GUIDE.md` for count definitions, evidence, commands,
remaining placeholders, and the three pre-existing repository-wide Ruff findings.

## Day 3 - Map and geographic-data review

### Goal

Provide a safe administrative view of supported geography, boundary records,
source information, validation state, and layer readiness.

### Implement

- interactive Bacoor map with the 47 current barangay boundaries;
- area search, selection, and detail panel;
- layer visibility controls;
- source, version, geometry type, validation information, publication status,
  and enabled state;
- clear visual distinction among administrative boundaries, the provisional
  MGB susceptibility layer, demonstration zones, and future approved
  susceptibility data;
- draft/review/approved labels backed by stored workflow status, with an explicit
  unavailable state where the current model does not yet support that status;
- read-only review of supported records; no editing, validation transitions,
  imports, approvals, or publication actions in this phase; and
- map legend and limitations that do not confuse a basemap with assessment data.

### Restrictions

- OpenStreetMap remains background context only;
- barangay boundaries do not establish susceptibility;
- provisional susceptibility layers, including MGB, must not be published to
  residents; and
- do not assign demonstration classes to real barangays.

### Verified completion - 18 September 2026

`/management/map-data/` now provides staff-only GET review with database-scoped
counts, neutral administrative geometry, separate labeled demonstration areas,
search, synchronized selection/details, and source/status metadata. Missing
versions and unsupported MGB/approved susceptibility layers have explicit
unavailable states. The page preserves server-rendered selection without
JavaScript. No model, migration, public API, or inference change was required.

The 70 focused portal/geography tests and all 141 backend tests passed, including
the controlled test-database import of 47 barangays and one city. Browser checks
and visual inspection covered desktop/mobile layouts, keyboard operation,
selection/search, long values, attribution, empty states, and unavailable
JavaScript/map assets. Flutter analysis, 91 tests, the debug APK build, and the
live Flutter API-client check passed. Changed portal code passes Ruff; existing
unrelated lint findings remain documented. No boundary import ran against the
developer's application database.

See `ADMIN_FRONTEND_DAY_3_GUIDE.md` for exact filters, counts, commands, test
evidence, dependency limitations, and the optional authorized local import.

## Day 4 - Settings and assessment-parameter governance

### Current checkpoint

The read-only Settings foundation and parameter-governance proposal are
implemented. Settings provides a profile summary, fixed-method explanation,
per-mode active knowledge-set metadata, source-aware scenario-reference
inventory, search/filtering, and an unavailable data-exchange state. Existing
assessment-parameter links redirect to Settings. No schema, permission grants,
parameter writes, activation, rollback, audit-event model, or preview workflow
has been introduced.

The team must approve the definitions, sources/units/bounds, owner and validator
assignments, permission matrix, and proposed revision/workflow/audit design
before governance migrations or mutation endpoints are created. See
`ADMIN_DAY_4_PARAMETER_GOVERNANCE_PROPOSAL.md` and
`ADMIN_FRONTEND_DAY_4_GUIDE.md`. Day 4 is not complete.

### Goal

Turn Settings into the controlled home for account preferences and future
authorized assessment parameters while keeping the algorithm fixed.

### Implement

- develop the Settings section and move authorized assessment parameters into
  its grouped configuration pages;
- read-only explanation of the inference method and current active version;
- parameter list and controlled forms with value, unit, source, rationale,
  version number, status, and effective date;
- editing limited to approved parameter definitions and authorized administrator
  roles, with proposed value changes passing through review before activation;
- draft, validation, review, approval, activation, and rollback states;
- server-side validation and permission checks;
- change confirmation and audit recording for parameter mutations;
- preview of the effect on demonstration scenarios without silently publishing;
  and
- a designed import/export entry point only after its direction and schema are
  confirmed.

### Restrictions

- no ordinary-Admin rule-set, raw-rule, condition, priority, or conflict-policy
  editor;
- no direct alteration of the inference algorithm;
- no arbitrary threshold field without source and validation metadata; and
- no direct activation of pending or restricted data.

If the current models cannot represent approved parameter governance safely,
stop and propose the smallest reviewed model/migration change before coding it.

## Day 5 - DSS preparedness-content workflow

### Goal

Allow authorized administrators to maintain sourced preparedness guidance
without affecting susceptibility classification.

### Implement

- guidance-item list with search and category filters;
- create/edit form with category, instruction, source, attribution, status, and
  display order;
- associate guidance with susceptibility results without changing the
  classification logic;
- mobile-preview section matching the resident-facing presentation;
- draft/review/approval/publication workflow;
- validation, confirmation, and safe error states; and
- tests proving guidance edits do not change the Expert System conclusion.

### Restrictions

- no invented emergency instructions;
- no wording that impersonates an official warning or evacuation order; and
- no coupling between guidance edits and rule evaluation.

### Verified completion - 19 September 2026

`/management/dss-content/` now provides a permission-controlled guidance list,
search and filters, draft create/edit forms, source and attribution fields,
susceptibility-result association, deterministic display order, responsive
mobile preview, and explicit draft, in-review, approved, and published states.
Approval does not publish content. Publication requires the separate
`dss.publish_guidanceitem` permission, explicit confirmation, and a final
source/classification eligibility check. Portal mutations create genuine Django
maintenance log entries; the broader Day 7 audit-history interface remains out
of scope.

Only enabled items in the explicit `PUBLISHED` workflow state can reach DSS API
responses. The migration preserves already exposed eligible records as
published and safely disables legacy enabled rows that do not satisfy the
existing operating-mode policy. Tests cover model validation, migration,
permissions, transitions, ordering, API publication filtering, and the
invariance of Expert System classifications when guidance changes. No official
or fictional guidance row is created by the migration or portal.

See `ADMIN_FRONTEND_DAY_5_GUIDE.md` for the schema, permission assignment,
verification evidence, and teammate steps.

## Day 6 - Rainfall references, evacuation centers, and provenance

### Delivered

- permission-controlled rainfall-reference list and detail pages that show
  existing scenario values and source metadata without changing inference;
- explicit wording that rainfall options are hypothetical scenario references,
  not observations, forecasts, monitoring, or automatic agency imports;
- sourced evacuation-center draft, review, verification, inactive, and
  re-review workflow with coordinate validation and map preview;
- capacity recording only during a verified transition and only when an
  approved source with a responsible organization exists;
- source/provenance list, detail, create, edit, approval, public-release,
  unpublish, and restriction flows; and
- migrations, explicit permissions, confirmations, validation, audit entries,
  honest empty states, filters, pagination, and focused tests.

Rainfall numeric create/edit remains intentionally unavailable. ScenarioOption
values feed the Expert System, so ordinary portal mutation would conflict with
the unresolved Day 4 requirements for approved definitions, units, bounds,
scientific authority, validation ownership, and role matrix. The current
implementation exposes evidence for review without changing assessment logic.

### Rainfall references

- manage scenario rainfall intensity and duration options, including units,
  source, period of record, and time resolution;
- support import or review of future DOST rainfall references once the schema,
  usage permissions, and intended workflow are confirmed; any official-data
  import requires explicit authorization for its target and must follow the
  EULA;
- label reference/scenario data separately from current observations; and
- do not imply live ingestion or monitoring.

### Evacuation centers

- provide a verified evacuation-center list and form using records supplied by
  an authorized custodian;
- include coordinates, address, contact information, responsible source,
  verification date, and verification status;
- provide map placement, preview, and validation; and
- do not invent center details or claim live capacity/occupancy.

### Sources and provenance

- provide a dataset/source registry with organization, custodian, coverage,
  license, usage restrictions, version, processing notes, validation state, and
  limitations;
- link managed content back to its source; and
- prevent restricted source material from being exposed through public output.

## Day 7 - Audit, security, accessibility, and integration

### Delivered

- read-only audit history for supported modules using genuine Django
  maintenance log entries;
- administrator, module, action, and date filters plus 50-row pagination;
- explicit audit-scope disclosure rather than a fabricated complete history;
- permission-aware navigation and quick actions, model-permission enforcement,
  POST-only mutations, CSRF-protected forms, and concurrency-safe transitions;
- confirmation screens for verification, approval, release, restriction, and
  deactivation actions;
- responsive tables/forms/detail views, labeled controls, focus styles,
  validation errors, forbidden responses, and truthful empty states; and
- backend regression, Django system, migration consistency, lint, Flutter, and
  responsive browser verification recorded in the Day 6-7 guide.

The portal does not expose before/after field contents because Django's current
maintenance log stores safe action summaries rather than complete historical
snapshots. This limitation is stated in the interface.

### Implement and verify

- administrative audit-history interface for supported mutations;
- actor, action, object, timestamp, and before/after summary where appropriate;
- filters by administrator, module, action, and date;
- module/action permissions and least-privilege review;
- confirmation for destructive or publication-impacting actions;
- form validation with helpful errors, plus forbidden, not-found, loading, and
  empty states;
- keyboard navigation, focus order, labels, contrast, and responsive testing at
  mobile and desktop widths;
- security review covering CSRF, session behavior, output escaping, uploads,
  authorization, safe redirects, secrets, and production HTTPS settings;
- end-to-end Admin-to-API-to-Flutter regression checks;
- full backend test suite;
- final consistency check against the high-fidelity design, subject to the
  current consultation decisions and this timeline; and
- final screenshots and presentation checklist.

Do not fabricate an audit history from model modification timestamps. If an
auditable event source is absent, implement and migrate a reviewed audit model
or explicitly leave the feature incomplete.

## Expected result after seven days

The designed day-to-day administrator interface under `/management/` should
provide approximately these functional modules:

1. Authentication
2. Dashboard
3. Geographic/map data
4. Settings and assessment parameters
5. DSS guidance
6. Rainfall references
7. Evacuation centers
8. Data sources/provenance
9. Audit history

Django Admin remains available at `/admin/` as the technical maintenance tool.
Module completion must be supported by its acceptance evidence; an empty state
for missing approved data must not be mistaken for an implemented workflow.

## Team handoff for each day

Before starting:

1. pull only when explicitly requested and protect local work first;
2. read this plan and the consultation decision record;
3. inspect `git status` and current models/tests;
4. confirm the assigned day and avoid editing another teammate's owned files;
5. identify whether the work requires a model migration; and
6. use the current local database only - local rows and superusers are not
   shared through Git.

Before handing off:

1. run relevant lint, Django checks, migration checks, and tests;
2. visually test desktop and mobile layouts for UI work;
3. document any new migration, seed/import, dependency, or setup step;
4. report which parts remain placeholders or require approved data; and
5. do not commit, push, migrate a shared database, or import official data unless
   explicitly authorized for that target.

## Parallel-work rule

Day 4 is at its governance checkpoint. Later days may be designed in parallel, but implementation
must respect dependencies:

- Day 4 must not finalize parameter editing before governance fields and
  approval ownership are agreed;
- Day 5 needs an authorized guidance source and publication rules;
- Day 6 needs verified source/custodian information; and
- audit event capture must accompany the governed mutations introduced from
  Day 4 onward; Day 7 completes the history interface and verifies coverage
  across modules. Day 2's recent-activity panel must use genuine recorded events
  or clearly report the missing event-source dependency.

When uncertainty would change scientific behavior, data publication, privacy,
or administrator authority, stop and request a decision instead of filling the
gap with a convenient assumption.
