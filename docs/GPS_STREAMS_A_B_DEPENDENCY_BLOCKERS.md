# GPS Streams A and B dependency blockers

**Status date:** 20 September 2026  
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
| Stream A Day 4 production integration | **Blocked** | No frozen Stream C wire contract or resident nearest-center endpoint exists. The normal app therefore shows an honest unavailable state instead of inventing an API. |
| Stream C resident API | **Not implemented** | Center administration exists, but the public nearest-center policy/service/serializer/view/URL and contract tests do not. |
| Stream D evacuation Admin | Implemented separately | Draft/review/verification/inactive workflows, permission checks, audit entries, forms, and map preview exist. This does not substitute for Stream C's resident API. |

The uncommitted Day 4 implementation passed 148 Flutter tests and 241 backend
tests. It must not be described as end-to-end complete until the blocked items
below are implemented and verified.

## Unresolved work by originating day

### Day 1 — contract, policy, and integration freeze

#### Stream C work still missing

- Freeze the exact resident-visible eligibility policy.
- Decide the authoritative PostGIS distance method and unit.
- Freeze safe public fields and exact unavailable/empty wording.
- Add contract/service tests before implementation.

#### Stream D work still missing or undocumented

- Freeze exact nearest-center request keys, response keys, status codes, warning
  text, error shapes, and optional result-limit behavior.
- Record the cross-stream privacy review for center lookup, including request
  tracing, middleware, logs, crash reporting, screenshots, and coordinate
  non-persistence.
- Record evidence that deployed/request logging does not capture request bodies
  or precise coordinates. No checked-in review artifact currently establishes
  this; this statement does not claim that such logging is occurring.

#### Effect on Streams A and B

- Stream A cannot create an exact JSON response parser or production API client.
- Stream A cannot validate unknown fields/statuses, nullability, result-count
  limits, or exact error bodies against a frozen contract.
- The Day 1 center contract-freeze deliverable remains incomplete even though
  the barangay-resolver contract was completed.

The foreground-location dependency selection that originally involved Stream D
is no longer blocked: `geolocator` and the Android foreground permissions were
implemented and verified during Days 2-3.

### Day 2 — nearest-center service foundation

#### Stream C work still missing

- Eligible-center queryset and per-request eligibility recheck.
- Straight-line distance calculation with documented full-precision sorting.
- Strict default and maximum result limits.
- Stable tie ordering.
- Truthful empty result.
- Exclusion tests for draft, in-review, inactive, restricted, unapproved,
  non-publicly-releasable, and malformed records.

The current `EvacuationCenter` model and workflow validate several administrative
states, but they are not a resident eligibility service. In particular, the
public API still needs an explicit publicly-releasable-source policy, safe-field
allowlist, nullable-barangay behavior, and malformed-coordinate handling.

#### Effect on Streams A and B

- Stream A can test its state/UI boundary with fakes but cannot receive real
  nearest-first results.
- The Day 2 acceptance statement that the nearest-center service cannot leak
  ineligible records has not yet been demonstrated.
- Stream B must not create a second eligibility or distance implementation to
  compensate.

No separate unresolved Stream D Day 2 task currently blocks the implemented GPS
or resolver flow.

### Day 3 — resident endpoint and frozen serialization

#### Stream C work still missing

- `POST /api/v1/evacuation-centers/nearest/` implementation.
- Request serializer for latitude, longitude, and the approved bounded limit.
- Response serializer containing only approved public fields.
- Evacuation URL module and shared URL registration.
- No-write, stable-order, safe-field, validation, empty-result, and error tests.
- An approved stable public center identifier distinct from an unapproved raw
  database row ID.

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

#### Stream C work still missing

- Recheck eligibility for every request rather than trusting an old Admin state.
- Round only displayed distance while preserving full-precision ordering.
- Cap results and reject abusive coordinate/limit input.
- Document straight-line methodology and limitations.
- Return an honest empty response when no eligible authorized records exist.

#### Stream D coordination still needed

- Approve/freeze the final cross-stream contract with Stream C and Stream A.
- Confirm the public identifier and safe provenance/address fields.
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

1. Stream C freezes a reviewed contract with Stream A and Stream D.
2. Stream C implements and tests eligibility, distance, serializers, endpoint,
   URL registration, safe empty results, and no-write behavior.
3. Stream D completes the privacy/logging review and integration evidence.
4. Stream A adds the production adapter and strict parser without changing the
   provider-independent controller or UI behavior.
5. Run focused Stream C and mobile contract tests, then the full backend and
   Flutter suites.
6. Perform physical-device checks without creating fake real-world centers.

## Completion rule

Remove or mark a blocker resolved only when the referenced implementation and
tests are present in the repository. A verbal agreement, local database row, or
Admin form does not by itself satisfy the public API or integration requirement.

