# GPS Streams A and B dependency blockers

**Status date:** 21 September 2026

**Scope:** Cross-day handoff for GPS Streams A and B through Day 4

This document records work that Streams A and B cannot safely finish because a
required Stream C or Stream D contract or implementation is absent. It is not
authorization for the Streams A/B owner to edit `server/evacuation/**`,
`server/admin_portal/**`, shared configuration, or governance-controlled data.

Repository state and tests are authoritative if this note later becomes stale.

## Current overall status

| Area | Status | Meaning |
| --- | --- | --- |
| Stream A Days 1-3 | Complete | Foreground one-shot GPS, manual fallbacks, resolver integration, confirmation, cleanup, retry states, and map behavior are implemented. |
| Stream B Days 1-4 | Complete | Resolver contract/service/API, controlled boundary filtering, robustness, public PSGC utility, and center-identity/boundary integration tests are implemented. |
| Stream A Day 4 independent work | Complete | Location-gated center state management, validated presentation types, cards, markers, warnings, failure states, cleanup, and fake-based tests are implemented. |
| Stream A Day 4 production integration | **Blocked** | The wire contract is frozen and Day 2 service tests pass against PostGIS. The endpoint and production mobile adapter remain absent. |
| Stream C resident API | **Day 2 service verified; endpoint absent** | UUID migration, eligibility/distance, mapping and no-write tests pass. No view, URL, or live integration exists. |
| Stream C/D Day 1 | Complete; former baseline blocker resolved | Frozen contract, repository privacy review, ownership, and baseline evidence exist. Contract and full backend tests now pass locally. |
| Stream C/D Day 2 | **Complete** | Database-backed distance, eligibility, migration, no-write and Admin permission tests pass. The user confirmed the manual browser checklist passed; the UUID migration is confirmed applied locally. |
| Stream D evacuation Admin | Implemented separately | Draft/review/verification/inactive workflows, permission checks, audit entries, forms, and map preview exist. This does not substitute for Stream C's resident API. |

The earlier Day 4 checkpoint reported 148 Flutter tests and 241 backend tests.
The Team B Day 1 run passed 164 Flutter tests and 153 new contract tests;
the complete backend run had 183 passes and 227 test-database setup errors
(`permission denied to create extension "postgis"`). See
`GPS_STREAM_C_D_DAY_1_BASELINE.md` for exact evidence. This is not an end-to-end
completion or green backend regression claim.

The initial Day 2 run had 204 passes and 307 setup errors. On 21 September,
PostGIS provisioning was resolved and two NaN test fixtures were corrected.
The full backend run now has **511 passed and 127 warnings**, including all
84 service cases, four UUID/migration cases and 102 Admin cases. The unchanged
Day 1 suite remains green. The user subsequently confirmed all manual browser
checks passed, completing Day 2. See `GPS_STREAM_C_D_DAY_2_GUIDE.md` for evidence
attribution and the confirmed local application migration state.

## Unresolved work by originating day

### Day 1 — contract, policy, and integration freeze

#### Resolved Stream C/D Day 1 items — 20 September 2026

- Eligibility policy, UUID decision/migration handoff, distance strategy in
  meters, safe public fields, exact warnings, empty behavior, request/response
  keys, errors, and limit default/bounds are frozen in
  `../server/evacuation/NEAREST_CENTER_CONTRACT.md`.
- Executable constants and request/response wire serializers are covered by
  153 passing database-independent contract tests. Service/HTTP tests remain
  later implementation work; the route is still absent.
- Repository privacy/logging review is recorded in
  `GPS_STREAM_C_D_DAY_1_PRIVACY_REVIEW.md`, with ownership and baseline evidence
  in `GPS_STREAM_C_D_DAY_1_BASELINE.md`.

#### Evidence still missing

- Actual deployed proxy/APM/crash/database logging and HTTPS evidence. No custom
  application body logger was found; this does not certify infrastructure or
  framework error-reporting paths.
- HTTP/mobile end-to-end evidence. Test-database PostGIS provisioning and
  service eligibility/distance/no-write verification are now resolved locally.

#### Effect on Streams A and B

- Stream A can now plan parser/adapter work against exact field names,
  nullability, bounds, warnings, and errors; the missing contract blocker is resolved.
- Production integration still waits for the service/endpoint and coordinated
  handoff. No mobile parser or adapter was implemented by Team B on Day 1.
- The Day 1 center contract foundation is complete; this does not establish live
  nearest-center output or deployed privacy controls.

The foreground-location dependency selection that originally involved Stream D
is no longer blocked: `geolocator` and the Android foreground permissions were
implemented and verified during Days 2-3.

### Day 2 — nearest-center service foundation

#### Stream C service verified against PostGIS — 21 September 2026

- `services.py` now contains reference readiness, current eligibility gates,
  guarded PostGIS distance, UUID tie ordering, post-validation limit handling,
  and safe response assembly. All 84 service tests pass against PostGIS.
- `0002_evacuationcenter_public_id` is written and manually reviewed; upgrade,
  reversal, uniqueness, and workflow-stability tests now pass. Application-database
  rollout is confirmed locally; each teammate must still apply it in their own database.
- Exclusion, known-distance, rounding, limit, no-write, and bounded-query tests
  pass in the isolated PostGIS test database.

The current `EvacuationCenter` model and workflow validate several administrative
states, but they are not a resident eligibility service. In particular, the
internal implementation now encodes the frozen policy and is service-tested;
it is not publicly exposed. Existing Admin verification semantics remain unchanged.

#### Effect on Streams A and B

- Stream A can test its state/UI boundary with fakes but cannot receive real
  nearest-first results.
- Service-level ineligible-record exclusions pass; HTTP/mobile integration
  evidence still depends on the future endpoint and adapter.
- Stream B must not create a second eligibility or distance implementation to
  compensate.

Stream D Day 2 adds center safety copy, read-only UUID display, linked errors,
focus/wrapping safeguards and no-script navigation. Nine pure rendering checks
pass, together with database permission regressions. The user confirmed the
manual 320px/desktop keyboard/layout and fallback checklist passed. These
changes do not alter GPS/resolver behavior.

### Day 3 — resident endpoint and frozen serialization

#### Stream C work still missing

- `POST /api/v1/evacuation-centers/nearest/` implementation.
- HTTP integration of the Day 1 request serializer for coordinates and bounded limit.
- Verify the new service mapping and integrate the Day 1 response serializer at HTTP level.
- Evacuation URL module and shared URL registration.
- No-write, stable-order, safe-field, validation, empty-result, and error tests.
- Application of the test-verified UUID migration in each teammate/deployment
  target before running the new code. It is confirmed applied on this local
  application database; a raw database row ID remains forbidden.

#### Effect on Streams A and B

- Stream A cannot test coordinates-in-POST-body behavior, URL privacy, timeout
  mapping, limit mapping, or strict live response parsing.
- The Day 3 acceptance statement that the backend can return a safe empty
  nearest-center response remains unmet.
- Physical-device testing currently verifies GPS/barangay behavior only, not
  live center results.

The relevant Stream D map-safety work does not currently block Streams A/B:
mobile OpenStreetMap attribution and neutral administrative-layer behavior are
already covered, and the Admin portal has a map-unavailable fallback.

### Day 4 — live center integration and end-to-end verification

#### Stream C integration still missing

The service now verifies eligibility per call, full-precision ordering, display
rounding, bounded results, strict input, straight-line methodology and honest
empty results. Day 4 still needs these behaviors verified through the public
endpoint and mobile adapter, including HTTP abuse controls.

#### Stream D coordination still needed

- Coordinate Stream A adoption of the frozen Day 1 contract, including public
  UUID and safe provenance/address fields; Stream C owns rollout of the verified UUID migration.
- Run Admin-to-API-to-Flutter integration checks after the endpoint lands.
- Capture release evidence for empty, results, invalid, offline, timeout, and
  unavailable scenarios without adding invented presentation records.

#### Stream A work that remains blocked

- Production `NearestCenterProvider` HTTP adapter.
- Strict JSON parsing using exact frozen names, nullability, statuses, units,
  limits, and errors.
- Live endpoint tests proving coordinates are in the POST body and absent from
  the URL.
- Live empty/results/offline/timeout/server/malformed integration checks.
- Physical-device verification of real cards, center markers, location changes,
  and cleanup against the backend.

The independent Stream A implementation is intentionally ready for one future
adapter; it does not sort, filter, retry automatically, calculate authoritative
distance, or fabricate centers on the client.

## Known Stream D item that is separate from GPS Streams A/B

The custom Admin plan's Day 4 parameter-governance mutation workflow remains
blocked pending explicit team approval of scientific definitions, bounds,
sources, roles, schema, workflow, preview behavior, and import/export direction.
Only its read-only Settings foundation and proposal exist.

This governance blocker must remain visible, but it does **not** block the GPS,
barangay resolver, or nearest-center contract directly and must not be folded
into Stream C's evacuation API implementation.

## Downstream impact after Day 4

Until Stream C and the relevant Stream D integration work land:

- Day 5 can harden the completed in-memory location/controller/UI code, but it
  cannot complete end-to-end privacy, authorization, logging, abuse-limit, and
  failure-response review for center lookup.
- Day 6 can polish fake-backed cards and accessibility, but it cannot validate
  real response rendering, real-data empty states, or endpoint performance.
- Day 7 cannot complete deployment rehearsal or Admin-to-API-to-device evidence
  for nearest centers.

Do not interpret these dependencies as permission to start Days 5-7 early.

## Required handoff sequence

1. Adopt the completed Stream C/D Day 1 contract and coordinate Stream A's handoff.
2. Stream C implements and tests eligibility, distance, serializers, endpoint,
   URL registration, safe empty results, and no-write behavior.
3. Stream D verifies the remaining deployment/privacy controls and integration
   evidence identified by the completed Day 1 repository review.
4. Stream A adds the production adapter and strict parser without changing the
   provider-independent controller or UI behavior.
5. Run focused Stream C and mobile contract tests, then the full backend and
   Flutter suites.
6. Perform physical-device checks without creating fake real-world centers.

## Completion rule

Remove or mark a blocker resolved only when the referenced implementation and
tests are present in the repository. A verbal agreement, local database row, or
Admin form does not by itself satisfy the public API or integration requirement.

