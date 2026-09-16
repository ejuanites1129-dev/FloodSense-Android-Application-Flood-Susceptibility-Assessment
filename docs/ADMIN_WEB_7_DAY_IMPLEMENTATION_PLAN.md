# FloodSense Admin Web - Seven-Day Implementation Plan

**Plan status:** Active  
**Updated:** 17 September 2026  
**Interface:** Custom Django portal under `/management/`

## Purpose

This is the implementation handoff for the designed FloodSense Admin web
application. It gives teammates and coding agents enough context to continue a
day independently without relying on a private conversation.

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
| 2 | Next | Truthful operational dashboard |
| 3 | Planned | Map and geographic-data review |
| 4 | Planned | Settings and governed assessment parameters |
| 5 | Planned | DSS preparedness-content workflow |
| 6 | Planned | Rainfall references, centers, and provenance |
| 7 | Planned | Audit, permissions, accessibility, integration, and release QA |

## Day 1 - Administration foundation

### Delivered

- staff-only custom sign-in and POST-only sign-out;
- responsive desktop sidebar and mobile drawer;
- FloodSense branding and fixed-height active navigation;
- account menu containing Settings and Sign out;
- reusable visual tokens, forms, cards, notices, and empty states;
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
2. Display truthful counts for existing containers such as geographic areas,
   data sources, scenario options, and DSS guidance items.
3. Group or label summaries by the existing publication status where useful, so
   demonstration records cannot look approved.
4. Add a review-attention panel using only status signals the current models can
   actually support.
5. Add quick links to the protected Map data, Settings, DSS content, and Sources
   sections.
6. Preserve an explicit data-safety notice and meaningful empty states.
7. Keep raw rules, rule conditions, priorities, and inference details out of the
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
- counts match records created by the test; and
- the dashboard does not expose raw expert-rule management links.

### Day 2 completion evidence

- screenshots at desktop and mobile widths;
- Django system check;
- `makemigrations --check --dry-run` reports no unintended model change; and
- focused tests plus the complete backend test suite pass.

## Day 3 - Map and geographic-data review

### Goal

Provide a safe administrative view of supported geography, boundary records,
source information, validation state, and layer readiness.

### Implement

- map preview with the 47 current Bacoor barangay polygons;
- area search, selection, and detail panel;
- source, version, geometry type, publication status, and enabled state;
- clear visual distinction among administrative boundaries, provisional layers,
  demonstration zones, and future approved susceptibility information;
- controlled validation/review actions only where the backend model supports
  them; and
- map legend and limitations that do not confuse a basemap with assessment data.

### Restrictions

- OpenStreetMap remains background context only;
- barangay boundaries do not establish susceptibility;
- the provisional MGB layer is not published as an official Bacoor result; and
- do not assign demonstration classes to real barangays.

## Day 4 - Settings and assessment-parameter governance

### Goal

Turn Settings into the controlled home for account preferences and future
authorized assessment parameters while keeping the algorithm fixed.

### Implement

- Settings navigation and grouped configuration pages;
- read-only explanation of the inference method and current active version;
- parameter list with value, unit, source, version, status, and effective date;
- draft, validation, review, approval, activation, and rollback states;
- server-side validation and permission checks;
- preview of the effect on demonstration scenarios without silently publishing;
  and
- a designed import/export entry point only after its direction and schema are
  confirmed.

### Restrictions

- no ordinary-Admin rule-set, raw-rule, condition, priority, or conflict-policy
  editor;
- no arbitrary threshold field without source and validation metadata; and
- no direct activation of pending or restricted data.

If the current models cannot represent approved parameter governance safely,
stop and propose the smallest reviewed model/migration change before coding it.

## Day 5 - DSS preparedness-content workflow

### Goal

Allow authorized administrators to maintain sourced preparedness guidance
without affecting susceptibility classification.

### Implement

- searchable/filterable guidance list;
- create/edit form with category, instruction, source, status, and display order;
- preview matching the resident-facing presentation;
- draft/review/approval/publication workflow;
- validation, confirmation, and safe error states; and
- tests proving guidance edits do not change the Expert System conclusion.

### Restrictions

- no invented emergency instructions;
- no wording that impersonates an official warning or evacuation order; and
- no coupling between guidance edits and rule evaluation.

## Day 6 - Rainfall references, evacuation centers, and provenance

### Rainfall references

- manage scenario-reference metadata such as category, duration, unit, source,
  period of record, and time resolution;
- prepare safe review of DOST-provided records under the EULA;
- label reference/scenario data separately from current observations; and
- do not imply live ingestion or monitoring.

### Evacuation centers

- manage only verified records supplied by an authorized custodian;
- include location, address, contact/source, verification date, and status;
- provide map preview and validation; and
- do not invent center details or claim live capacity/occupancy.

### Sources and provenance

- maintain organization, custodian, coverage, license, restrictions, version,
  processing notes, validation state, and limitations;
- link managed content back to its source; and
- prevent restricted source material from being exposed through public output.

## Day 7 - Audit, security, accessibility, and integration

### Implement and verify

- administrative activity history for supported mutations;
- actor, action, object, timestamp, and before/after summary where appropriate;
- module/action permissions and least-privilege review;
- confirmation for destructive or publication-impacting actions;
- validation, forbidden, not-found, loading, and empty states;
- keyboard navigation, focus order, labels, contrast, and responsive layouts;
- security review covering CSRF, session behavior, output escaping, uploads,
  authorization, safe redirects, secrets, and production HTTPS settings;
- end-to-end Admin-to-API-to-Flutter regression checks; and
- final screenshots and presentation checklist.

Do not fabricate an audit history from model modification timestamps. If an
auditable event source is absent, implement and migrate a reviewed audit model
or explicitly leave the feature incomplete.

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

Day 2 may begin now. Later days may be designed in parallel, but implementation
must respect dependencies:

- Day 4 must not finalize parameter editing before governance fields and
  approval ownership are agreed;
- Day 5 needs an authorized guidance source and publication rules;
- Day 6 needs verified source/custodian information; and
- Day 7 audit work depends on knowing which mutations earlier days introduced.

When uncertainty would change scientific behavior, data publication, privacy,
or administrator authority, stop and request a decision instead of filling the
gap with a convenient assumption.
