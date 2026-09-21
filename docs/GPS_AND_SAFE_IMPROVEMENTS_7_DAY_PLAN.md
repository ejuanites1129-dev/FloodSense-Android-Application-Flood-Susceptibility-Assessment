# FloodSense GPS and Safe Improvements — Seven-Day Parallel Plan

**Prepared:** 19 September 2026

**Status:** Working implementation plan for team review

**Scope:** Foreground GPS, barangay detection, nearest verified evacuation-center discovery, and safe improvements that do not change the research algorithm

**Implementation checkpoint (22 September 2026):** The production mobile
nearest-center adapter, strict complete-envelope parser, mandatory warning
presentation, and typed failure mapping are implemented and wired into the
default app. The full Flutter suite passes with 175 tests, and the live backend
honest-empty envelope was verified over localhost and the phone-accessible LAN
address. Authorized center data, populated Admin-to-API-to-device evidence,
fresh Admin browser QA, and deployment/governance review remain pending. See
`GPS_STREAMS_A_B_DEPENDENCY_BLOCKERS.md` for the cross-day inventory and exact handoff.

**Team B Day 1 checkpoint (20 September 2026):** Streams C/D contract, repository
privacy review, ownership, and baseline foundation are complete. The frozen
contract and strict wire serializers have 153 passing database-independent tests;
Flutter analysis and 164 tests passed. Full backend regression was blocked locally
by missing PostGIS in the test database (183 passed, 227 setup errors); this
historical blocker is resolved in the Day 2 checkpoint below. See
`server/evacuation/NEAREST_CENTER_CONTRACT.md` from the repository root and
`GPS_STREAM_C_D_DAY_1_BASELINE.md` / `GPS_STREAM_C_D_DAY_1_PRIVACY_REVIEW.md` here.
No model/migration, service, endpoint, URL registration, mobile adapter, or live
integration was added. Foreground GPS remains the safe team implementation
direction, not a claim of adviser approval; final GPS requirements remain unresolved.

**Team B Day 2 checkpoint (21 September 2026): Streams C/D Day 2 complete.**
The public UUID migration,
internal eligibility/PostGIS distance service, safe response assembly, and targeted
Admin improvements are written. Database-backed migration, eligibility, distance,
no-write and permission tests now pass. The full backend suite has 511 passes and
127 warnings after correcting two NaN test fixtures; the provisioning blocker
is resolved. The prior Flutter baseline remains clean with 164 tests passed.
The user confirmed all manual browser accessibility/layout checks passed. A
read-only migration check confirms the UUID migration is applied locally.
See `GPS_STREAM_C_D_DAY_2_GUIDE.md` for the exact tests, evidence attribution,
migration steps, and remaining work. Day 1 frozen contract files are unchanged;
no public route, mobile adapter, or official data import was added.

Repeatable walkthrough: [Streams C/D Days 1–2 manual test guide](GPS_STREAM_C_D_DAYS_1_2_MANUAL_TEST_GUIDE.md).

**Team B Day 3 checkpoint (21 September 2026): Backend verified; fresh browser QA pending.**
The public `POST /api/v1/evacuation-centers/nearest/` route now calls the preserved
Day 2 service using the frozen contract. JSON-only parsing, a 1,024-byte body
limit, scoped 30/min throttling, normalized errors, no-store headers and HTTP
no-write/privacy checks are implemented. All 599 backend tests pass, including
85 new endpoint cases and three map-safety regressions; the separate Admin suite
has 105 passes. Flutter analysis and 167 tests pass with no mobile edits.
Map code review found no production-code gap; fresh desktop/320px, keyboard and
JavaScript-disabled browser verification remains pending because no browser was
connected. Do not mark the full Day 3 C/D acceptance gate complete yet.
See [Day 3 evidence](GPS_STREAM_C_D_DAY_3_GUIDE.md) and the
[Stream A handoff](GPS_STREAM_A_NEAREST_CENTER_DAY_3_HANDOFF.md).
There is no new migration or dependency. Production Flutter integration,
physical-device results, deployed privacy controls and Day 4 acceptance remain
unverified; the historical Day 1/2 checkpoints above describe their own scope.

**Team B Day 4 checkpoint (21 September 2026): Automated C/D work complete; fresh browser QA pending.**
Current-state center/source eligibility, WGS 84 distance edge cases,
full-precision-before-rounding behavior, bounded safe output, and truthful empty
responses are explicitly regression-tested. The evacuation Admin now adds exact
normalized-name/exact-coordinate review warnings without merging, stronger
server-side validation, clearer provenance and transition effects, safe audit
field summaries, and non-map coordinate status/fallbacks. Focused Day 4 and
existing endpoint/Admin suites pass. No schema change, migration, data import,
mobile edit, or geography edit was required. The connected browser runtime had
no available browser, so fresh visual/keyboard/responsive/no-script verification
remains an environment limitation. See `GPS_STREAM_C_D_DAY_4_GUIDE.md`.

**Stream A integration follow-up (22 September 2026): Mobile adapter complete;
data-dependent acceptance remains.** The app now posts confirmed coordinates in
the JSON body to the frozen nearest-center endpoint, parses the exact complete
response envelope, preserves server order and mandatory warnings, rejects
malformed public records, and maps request, rate, connectivity, timeout, server,
and malformed-response failures without automatic retries. The app was installed
on a connected Android 14 physical device and its initial API requests succeeded.
The truthful empty response is live; populated-card acceptance must wait for
authorized, source-backed center records and must not use invented production data.

## 1. Purpose

This plan turns the currently safe and independently actionable work into one
seven-day implementation program. It includes mobile, GIS, evacuation-center,
Admin, privacy, security, testing, performance, deployment-readiness, and thesis
documentation work.

It does not authorize scientific parameter changes, Expert System rule changes,
official data publication, background monitoring, live alerts, or unverified
evacuation recommendations. The following documents remain controlling:

- `TA_CONSULTATION_SYSTEM_DECISIONS.md`;
- `ADMIN_WEB_7_DAY_IMPLEMENTATION_PLAN.md`;
- `ADMIN_DAY_4_PARAMETER_GOVERNANCE_PROPOSAL.md`;
- `TEAM_DATABASE_AND_GIT_WORKFLOW.md`; and
- the applicable `research_data/*/README.md` files.

## 2. Approved working boundary

The planned location flow is user-triggered and foreground-only:

```text
User taps Use my location
        -> app explains the purpose
        -> Android requests foreground permission
        -> app reads one temporary coordinate
        -> backend resolves the coordinate against the Bacoor reference layer
        -> user confirms or corrects the detected barangay
        -> app may request nearest eligible evacuation centers
        -> coordinate is discarded when the flow ends
```

Non-negotiable behavior:

- no background-location permission;
- no timer, continuous polling, passive tracking, or location history;
- no coordinate stored in an assessment, audit event, analytics record, or user
  profile;
- manual pin and barangay selection remain available;
- the detected barangay is a boundary lookup, not a susceptibility result;
- the 47-barangay reference remains labeled pending validation and not
  City-verified;
- nearest means approximate straight-line distance, not safest road route;
- only eligible verified evacuation-center records may be returned;
- no claim that a center is open, reachable, safe, recommended, or has live
  capacity; and
- an unavailable/insufficient-data state is correct when verified records do
  not exist.

## 3. Can the team work in parallel?

Yes, provided work is divided by code ownership rather than only by day number.
Later-day work may begin early only after the relevant interface contract is
frozen. Team members must not edit the same shared files independently and then
attempt to resolve meaning-changing conflicts at the end.

### Recommended workstreams

| Stream | Primary responsibility | Exclusive file ownership while active |
| --- | --- | --- |
| A — Mobile | GPS permission flow, temporary location state, confirmation, map and nearest-center UI | `mobile/**` |
| B — Geography/GIS | Barangay point resolution, boundary validation, spatial edge cases and API | `server/geography/**`, geography-focused tests |
| C — Evacuation API | Public eligibility policy, nearest-center service/API and distance tests | `server/evacuation/**`, evacuation-focused tests |
| D — Portal, security and integration | Admin polish, audit/security review, cross-module integration, plans and release evidence | `server/admin_portal/**`, selected `docs/**` |

If the team has only three developers, Stream D should be owned by the
integration lead and performed alongside review rather than merged into Stream
A, B, or C without a file-ownership agreement.

### Three-member team allocation

For the current three-member team, use this mapping throughout the plan:

| Member | Assigned streams | Exclusive working scope |
| --- | --- | --- |
| Member 1 — Mobile | Stream A | `mobile/**`; GPS, resident map/location flow, center UI, Flutter tests and emulator checks |
| Member 2 — Spatial backend | Streams B and C | `server/geography/**` and `server/evacuation/**`; barangay resolution, nearest-center API, PostGIS/service tests and app-specific migrations |
| Member 3 — Admin and integration lead | Stream D | `server/admin_portal/**`, selected `docs/**`, shared configuration/dependency files, security, integration, full regression and release evidence |

All three members work during the same calendar days. A day identifies the
integration stage, not a separate person. Member 2 has the largest implementation
scope, so Member 3 may help with independent integration tests and documentation,
but must not concurrently edit Member 2's implementation files.

### Reusable teammate instruction format

Do not send only “do Member 2 work” unless the intention is to assign that
member's entire seven-day stream. Prefer one bounded instruction:

```text
Complete Member 2's Day 2 tasks from
docs/GPS_AND_SAFE_IMPROVEMENTS_7_DAY_PLAN.md. Follow the repository instructions,
stay within Member 2's owned files, include focused tests, and report any required
shared-file change to Member 3 instead of editing that shared file concurrently.
```

Equivalent examples are:

```text
Complete Member 1's Day 3 tasks from the GPS seven-day plan.
Complete Member 3's Day 4 tasks from the GPS seven-day plan.
```

To deliberately assign a complete stream, say:

```text
Complete all Member 2 tasks across Days 1-7 from the GPS seven-day plan, in order.
Do not implement work owned by Members 1 or 3. Pause at a contract or shared-file
dependency and report it before continuing.
```

Each instruction should identify the member, day or explicit full-stream scope,
source plan, ownership boundary, expected tests and dependency behavior.

### Shared-file owner

One integration lead must own these conflict hotspots:

- `server/config/settings.py`;
- `server/config/urls.py`;
- `server/requirements.txt`;
- `mobile/pubspec.yaml` and `mobile/pubspec.lock`;
- root `README.md`;
- cross-module API documentation; and
- the final seven-day plan/status documents.

Other developers request a small integration change instead of editing those
files concurrently.

### Git and merge rules

1. All branches start from the same reviewed `main` commit.
2. Use one branch or managed worktree per stream, for example:
   `gps-mobile`, `gps-geography`, `gps-evacuation`, and `gps-integration`.
3. Record request/response contracts on Day 1 before dependent implementation.
4. Commit small coherent changes with their tests.
5. Pull/rebase from updated `main` before requesting integration.
6. Merge backend contracts before the mobile integration that consumes them.
7. Assign only one migration author per Django application.
8. Never create two migrations for the same app from the same parent without
   reviewing the migration graph.
9. Do not resolve a semantic conflict by choosing one side blindly.
10. After every merge, run the affected focused tests; after the daily merge
    window, run the complete backend and Flutter suites.

### Contract freeze for parallel work

The team should approve these provisional contracts during Day 1:

```text
POST /api/v1/geography/resolve-barangay/
Body: latitude, longitude
Result: resolution state, temporary coordinate echo, safe barangay identity,
        boundary status and limitations

POST /api/v1/evacuation-centers/nearest/
Body: latitude, longitude, optional bounded result limit
Result: eligible verified centers ordered by approximate straight-line distance,
        with safe source/verification/limitation fields
```

Coordinates use WGS 84 and are submitted in the request body rather than a URL
query string. Neither endpoint persists the coordinate. Exact field names and
error codes must be frozen in a contract test before parallel client work.

## 4. Seven-day execution plan

## Day 1 — Baseline, contracts, privacy and ownership

### Goal

Create a safe shared foundation so all streams can work concurrently without
inventing behavior or overwriting each other's files.

### Stream A — Mobile

- Inventory current assessment controller, map widgets, API client and tests.
- Design a `LocationService` abstraction so widget/controller tests do not need
  real device GPS.
- Draft states for service disabled, permission not requested, denied, denied
  permanently, acquiring, acquired, inaccurate/unavailable and error.
- Add the user-facing purpose explanation and manual-selection fallback design.
- Select a maintained Flutter foreground-location package compatible with the
  checked-in Flutter/Android toolchain; the integration lead owns dependency
  file changes.
- Define temporary in-memory location state and explicitly exclude persistence.

### Stream B — Geography/GIS

- Specify `resolve-barangay` input validation and response states:
  `RESOLVED`, `OUTSIDE_BACOOR`, `AMBIGUOUS_BOUNDARY`, and `UNAVAILABLE`.
- Define the eligible boundary queryset using the reserved Bacoor reference
  source and 47 current barangays.
- Confirm longitude/latitude ordering, WGS 84 SRID, polygon coverage and edge
  behavior.
- Add contract tests first, including a coordinate inside a barangay, outside
  Bacoor, on a shared boundary and invalid/non-finite coordinates.
- Ensure returned properties are allowlisted and contain no susceptibility.

### Stream C — Evacuation API

- Define the resident-visible center eligibility policy.
- Recommended minimum eligibility: verified center, approved record, approved
  source, publicly releasable source, active/available record, valid coordinate,
  and safe public fields only.
- Decide the database distance implementation without introducing duplicate
  canonical coordinates.
- Write contract and service tests before the endpoint implementation.
- Define exact language for approximate straight-line distance and unavailable
  data.

### Stream D — Portal/security/integration

- Apply pulled migrations to each authorized local development database.
- Capture baseline checks: Django check, migration consistency, backend tests,
  Flutter analysis and Flutter tests.
- Freeze API field names, status codes, warning text and error shapes.
- Create the file-ownership register and merge order.
- Perform a privacy-threat review for location collection, logs, crash reports,
  screenshots and request tracing.
- Confirm no current middleware logs request bodies or precise coordinates.

### Day 1 deliverables

- frozen API contract document/tests;
- workstream ownership table and branch list;
- location-purpose and privacy copy draft;
- baseline test report;
- no production behavior change required yet.

### Day 1 acceptance

- Every developer can name the files they own.
- Mobile can develop against contract fakes.
- Backend streams agree on coordinate order and non-persistence.
- No unresolved contract question is hidden inside implementation code.

## Day 2 — Foreground GPS and barangay resolver

### Goal

Implement independent halves of one-time GPS acquisition and administrative
barangay resolution.

### Stream A — Mobile GPS foundation

- Add Android foreground coarse/fine location declarations only.
- Implement the location-service adapter.
- Request permission only after an explicit tap.
- Handle service-disabled and every permission outcome.
- Acquire one current position with an accuracy/timeout policy.
- Keep the coordinate only in controller memory.
- Add a visible temporary-location indicator and clear-location action.
- Keep manual pin placement fully functional.
- Add unit/widget tests using a fake location service.

### Stream B — Barangay resolver

- Implement the spatial service using PostGIS point-in-polygon logic.
- Add the POST API endpoint and serializer.
- Filter only the controlled Bacoor barangay reference layer.
- Return boundary provenance status and the not-City-verified limitation.
- Return ambiguity instead of selecting an arbitrary polygon.
- Verify that GET and unsupported methods cannot accidentally perform a lookup
  if the contract is POST-only.
- Test that the endpoint performs no writes.

### Stream C — Nearest-center service foundation

- Implement the eligible-center queryset/service independently of the HTTP view.
- Calculate deterministic straight-line distance in meters/kilometers.
- Apply a strict maximum result limit.
- Use stable ordering for equal distances.
- Return an empty list when no eligible centers exist.
- Test exclusion of draft, in-review, inactive, restricted, unapproved and
  malformed records.

### Stream D — Safe Admin/UI improvements

- Review responsive navigation, focus states, long text and empty states.
- Improve copy that distinguishes boundary, susceptibility and current
  conditions without changing backend behavior.
- Review Settings and rainfall-reference pages for consistent read-only
  parameter messaging.
- Add or refine accessibility tests that do not overlap the three feature
  streams.

### Day 2 acceptance

- A fake GPS coordinate can be acquired without a physical device.
- The backend resolves known coordinates against exactly the intended layer.
- The resolver writes nothing and returns no classification.
- The nearest-center service cannot leak ineligible records.

## Day 3 — GPS-to-barangay integration and map experience

### Goal

Connect the mobile GPS flow to the backend resolver and make uncertainty and
manual correction explicit.

### Stream A — Mobile integration

- Add the resolver method to the API-client abstraction.
- Connect `Use my location` to the frozen endpoint contract.
- Center the map and place a temporary marker after acquisition.
- Present the detected barangay for confirmation.
- Allow users to reject/correct the detection using manual pin or barangay
  selection.
- Display accuracy and boundary uncertainty in plain language.
- Clear the location when the assessment flow is reset or disposed.
- Preserve chosen rainfall scenario while the location step changes.
- Add offline, timeout, malformed-response and retry behavior.

### Stream B — GIS robustness

- Test every current barangay with representative interior points where
  feasible.
- Verify merged barangay geometry and current PSGC identity handling.
- Add edge-case tests for holes, multipolygons, coastal points and shared
  boundaries.
- Measure query count and response size.
- Add spatial index/query guidance if evidence shows a problem.
- Confirm the endpoint remains administrative identification only.

### Stream C — Evacuation API endpoint

- Add the POST nearest-center endpoint around the tested service.
- Validate coordinates and limit values.
- Serialize only name, safe address, barangay, coordinate, approximate distance,
  verification date, safe source attribution and limitations.
- Exclude notes, private contact data and restricted provenance.
- Add no-write and stable-order API tests.

### Stream D — Maps and data safety

- Improve legends and layer names for administrative, provisional MGB and
  fictional demonstration layers.
- Verify OpenStreetMap attribution remains visible.
- Improve map-loading, tile failure and JavaScript-disabled Admin states.
- Ensure no real barangay receives a fictional assessment color.

### Day 3 acceptance

- A user-triggered coordinate produces a confirmable barangay or an honest
  unavailable/outside/ambiguous state.
- Manual selection works when GPS fails or permission is denied.
- No coordinate survives an assessment reset or application restart.
- The backend can return an empty safe nearest-center response.

## Day 4 — Nearest verified evacuation-center user experience

### Goal

Present eligible centers by approximate distance without implying route safety,
availability or an official evacuation instruction.

### Stream A — Resident-facing center interface

- Add evacuation-center response models and strict JSON validation.
- Request nearest centers only after the location is confirmed.
- Show nearest-first cards and map markers.
- Show approximate straight-line distance, verification date, source and
  limitations.
- Add an explanation that distance is not a road-safety recommendation.
- Provide no-center, offline, location-denied and server-unavailable states.
- Never show capacity as live occupancy or guaranteed space.
- Do not automatically navigate or issue an evacuation instruction.

### Stream B — Geography integration support

- Verify that center barangay labels and resolved barangay identities use
  compatible records.
- Add utility/contract support only where needed; avoid editing evacuation files.
- Test points just outside Bacoor and centers near municipal boundaries.

### Stream C — Eligibility and accuracy

- Verify source/publication/verification eligibility on every request.
- Recheck records rather than relying on a cached Admin status.
- Round displayed distances without altering sort accuracy.
- Cap response size and reject abusive inputs.
- Document straight-line methodology and limitations.
- If no authorized center rows exist, preserve a truthful empty response.

### Stream D — Evacuation Admin and provenance polish

- Improve center form validation and map-preview accessibility.
- Improve source, verification and limitation visibility.
- Verify workflow permission boundaries and audit entries.
- Improve duplicate-coordinate/name review warnings without silently merging
  records.
- Do not create real-looking center records for presentation.

### Day 4 acceptance

- Only eligible verified centers appear.
- The result is explicitly approximate and not a safe-route recommendation.
- No verified data produces an honest unavailable state, not invented content.
- Center management and resident output remain separated.

## Day 5 — Privacy, security, audit and failure hardening

### Goal

Harden the complete flow before polishing or presentation work hides structural
problems.

### Privacy

- Verify coordinates are absent from database tables, audit records, analytics,
  application logs and screenshots produced automatically.
- Ensure API errors do not echo unnecessary precision.
- Add a visible explanation before the platform permission prompt.
- Provide a clear-location action and manual fallback.
- Confirm no background permission, service or Android foreground service was
  introduced.

### Security

- Test authentication/authorization boundaries for Admin workflows.
- Keep public location endpoints read-only, input-limited and no-write.
- Validate content types, numeric bounds and result limits.
- Review CSRF expectations for session-authenticated portal writes separately
  from public JSON lookup endpoints.
- Test XSS escaping of center, barangay, source and limitation strings.
- Verify restricted source fields and private contact information are excluded.
- Review production cookie, HTTPS, host and security-header settings without
  committing secrets.

### Audit

- Confirm Admin mutations create genuine maintenance events.
- Confirm GPS lookups do not create location-history events.
- Improve safe event labels and filters where needed.
- Do not fabricate history or store raw request bodies.

### Expert System regression

- Prove that GPS detection only chooses/confirms a location input.
- Prove center lookup cannot change susceptibility results.
- Prove guidance edits cannot change classifications.
- Prove raw rules remain unavailable through the custom portal.
- Verify real barangays return insufficient data unless separately supported by
  approved susceptibility knowledge.

### Day 5 acceptance

- Privacy tests demonstrate no coordinate persistence.
- Authorization tests cover every management mutation.
- Location and center features do not affect inference behavior.
- Failure states reveal no restricted or private data.

## Day 6 — System-wide polish, performance and data readiness

### Goal

Use the safe feature foundation to improve the entire product without changing
scientific meaning.

### Admin and dashboard

- Review all navigation, active states, account actions and responsive layouts.
- Improve truthful dashboard readiness and pending-review summaries.
- Review pagination, long values, filters and empty states across modules.
- Keep Day 4 parameter settings read-only and preserve the saved governance
  proposal.
- Improve DSS, rainfall-reference, evacuation and provenance consistency.

### Mobile

- Polish the guided scenario -> location -> confirmation -> assessment ->
  guidance/center sequence.
- Preserve selections during recoverable errors.
- Improve touch targets, focus order, semantics, contrast and text scaling.
- Test small screens, rotation where supported and slow connections.
- Verify map attribution and warnings remain visible.

### Performance

- Measure geography and nearest-center query counts and latency.
- Avoid N+1 source/area lookups.
- Limit payloads and geometry precision only through reviewed, non-destructive
  presentation transformations.
- Avoid unnecessary repeated GPS or API requests.
- Confirm UI rebuilds and map layers remain responsive.

### Data readiness

- Prepare validation/reporting tools for future authorized center, DOST and MGB
  data without activating them.
- Record checksum, license, CRS, unit, period, resolution, missing values and
  limitations.
- Keep restricted files outside ordinary Git.
- Do not invent formulae connecting new datasets to susceptibility.

### Code quality

- Refactor duplication while preserving behavior.
- Run lint/format tools on changed scopes.
- Resolve warnings introduced by this work.
- Update API and module documentation.
- Keep migrations reviewed and consistent.

### Day 6 acceptance

- Core pages and mobile flow are responsive and accessible at agreed sizes.
- Performance measurements show no obvious repeated-query or repeated-location
  problem.
- Data-readiness tools do not publish or activate unapproved information.
- All focused and combined suites pass after integration.

## Day 7 — Integration, deployment rehearsal and thesis evidence

### Goal

Produce a reproducible, defensible release candidate and evidence package. This
is a rehearsal, not authorization to deploy to a shared or production target.

### Integration verification

- Start from a clean checkout or disposable environment.
- Install documented dependencies.
- Create a disposable PostGIS database and apply all migrations.
- Run approved local seed/import commands only in the disposable environment.
- Run Django checks and migration consistency checks.
- Run the complete backend suite.
- Run Flutter analysis and complete Flutter tests.
- Build the Android debug APK.
- Perform an emulator walkthrough with simulated GPS coordinates.

### Required end-to-end scenarios

1. Permission granted; coordinate resolves to a barangay; user confirms.
2. Permission denied; manual pin succeeds.
3. Permission permanently denied; settings guidance and manual fallback appear.
4. Location service disabled; no crash or repeated prompt.
5. Coordinate outside Bacoor; no forced barangay or assessment.
6. Boundary ambiguity; user is asked to confirm manually.
7. No verified centers; honest empty state.
8. Several eligible centers; stable nearest-first ordering.
9. Restricted/unverified center never appears.
10. Network failure; retry does not lose scenario selections.
11. App restart; precise coordinate was not retained.
12. Assessment output remains scenario-based and clearly labeled.

### Deployment readiness

- Document required environment variables without values.
- Verify production security checklist, HTTPS assumptions, static files and
  allowed hosts.
- Document database backup, migration and rollback procedure.
- Document that tests use a separate PostGIS database.
- Explicitly prohibit `seed_demo` and fictional fixtures in production.
- List the authorized import required before real center output can exist.
- Do not deploy or import official data without target-specific authorization.

### Thesis and presentation evidence

- Update architecture and data-flow diagrams.
- Update module inventory and implementation percentages.
- Capture non-sensitive screenshots of permission, barangay confirmation,
  nearest-center empty/result states and Admin verification workflow.
- Record test counts, devices/emulators and limitations.
- Update the data dictionary and API documentation.
- Prepare a demonstration script and failure fallback.
- State clearly that GPS is foreground/on-demand, boundaries are pending
  validation, distance is approximate, and FloodSense is not an official
  warning or safe-routing service.

### Day 7 acceptance

- Clean-environment setup is reproducible.
- All automated checks and the defined emulator scenarios pass.
- No restricted data, secrets or precise user coordinates are committed.
- Documentation matches actual behavior.
- Remaining external-data and governance blockers are listed rather than hidden.

## 5. Coverage of the safe-work backlog

| Safe work area | Main plan days |
| --- | --- |
| Admin UI and visual design | 2, 4, 6 |
| Admin dashboard | 6 |
| Map and geographic interface | 1-3, 6 |
| Mobile assessment experience | 1-6 |
| Location and privacy foundations | 1-5, 7 |
| Expert System protection and quality | 5, 7 |
| Read-only Settings improvements | 2, 6 |
| DSS preparedness workflow quality | 5-6 |
| Rainfall-reference review | 6 |
| Evacuation-center infrastructure | 1-5 |
| Sources and provenance | 4, 6 |
| Audit and accountability | 4-5, 7 |
| Security | 1, 5, 7 |
| Testing and QA | Every day, full regression on 7 |
| Performance and code quality | 3, 6 |
| Development/deployment preparation | 1, 7 |
| Thesis and system documentation | 1, 6-7 |

## 6. Items deliberately excluded

The seven-day work must not include:

- background GPS or monitoring;
- automatic rainfall/water-level polling;
- alerts, forecasts or evacuation orders;
- road or flood-safe routing;
- live center occupancy/capacity;
- invented real evacuation centers;
- automatic susceptibility classification of the 47 barangays;
- changes to Expert System rules, thresholds, priorities or algorithm behavior;
- activation of Day 4 parameter mutation before governance approval;
- unreviewed DOST/MGB/agency imports;
- final legal claims for terms/privacy without review; or
- production deployment or shared-database mutation without explicit target
  authorization.

## 7. Daily merge checklist

Before merging any stream:

```powershell
git status
git diff --check
server\.venv\Scripts\python.exe server\manage.py makemigrations --check --dry-run
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe -m pytest server -q --reuse-db
```

When mobile files change:

```powershell
Set-Location mobile
flutter pub get
flutter analyze
flutter test
Set-Location ..
```

Also review:

- no `.env`, secrets, database dump, restricted dataset or generated build
  artifact is staged;
- every intentional model change includes its reviewed migration and tests;
- API changes and their mobile consumers use the same frozen contract;
- demonstration/provisional/approved labels remain truthful; and
- the branch contains only the assigned workstream's files plus explicitly
  coordinated shared-file changes.

## 8. Definition of the seven-day outcome

At the end of the plan, FloodSense should support an on-demand, foreground-only
location flow that can identify a likely Bacoor barangay using the controlled
reference layer and show nearest eligible verified evacuation centers by
approximate straight-line distance when such records exist. It must retain
manual selection, avoid precise-location persistence, preserve the fixed Expert
System, and remain honest when scientific or operational data is unavailable.

The result is a pre-event scenario-support feature, not a real-time tracking,
forecasting, navigation or emergency-dispatch system.
