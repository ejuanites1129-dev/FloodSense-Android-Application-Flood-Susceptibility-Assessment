# Nearest verified evacuation centers — frozen Day 1 contract

**Frozen:** 20 September 2026, Team B / Streams C and D, contract version 1.
**Original Day 1 implementation:** constants, wire serializers and pure tests.
**Day 3 checkpoint (21 September 2026):** the Day 2 UUID/service foundation and
public HTTP route are implemented and tested. The request/response schema below
is unchanged; reviewed HTTP size/rate additions appear below. Statements about
future Day 2 implementation are retained as the original design specification.
**Mobile integration checkpoint (22 September 2026):** the production adapter,
strict complete-envelope parser, mandatory warning UI, typed failure mapping,
and default-app wiring are implemented. See
`../../docs/GPS_STREAMS_A_B_DEPENDENCY_BLOCKERS.md` for remaining data and
deployment evidence.

This is the current safe team implementation direction, not adviser approval of
optional GPS. The final GPS requirement remains unresolved in
`../../docs/TA_CONSULTATION_SYSTEM_DECISIONS.md`. Assessment/inference behavior is
outside this contract. Contract changes require coordinated C/D/A review and tests.

## Transport and request

Implemented route: `POST /api/v1/evacuation-centers/nearest/`.
Public, JSON-only (`application/json`, including a charset parameter), read-only
in effect, no authentication required, and no database writes. Day 3 must
explicitly override the global authentication/permission defaults for this
public lookup. `OPTIONS` may return metadata without performing a lookup;
`GET`, `HEAD`, `PUT`, `PATCH`, and `DELETE` return 405 with `Allow: POST, OPTIONS`.

```json
{"latitude": 14.4629, "longitude": 120.9647, "limit": 3}
```

| Field | Frozen rule |
| --- | --- |
| `latitude` | Required, non-null finite JSON number, -90 through 90 inclusive |
| `longitude` | Required, non-null finite JSON number, -180 through 180 inclusive |
| `limit` | Optional JSON integer; default 3, minimum 1, maximum 10 |

Numeric strings, booleans, NaN, infinity, null, non-object bodies, and unknown
keys are rejected. `limit: 3.0` is rejected; use `limit: 3`. No mode, barangay,
radius, authentication identity, or sorting option is accepted. Coordinates are
WGS 84 and belong only in the JSON body, never query parameters, paths, tokens,
or headers. Mobile calls only after confirmation of a coordinate-bearing
location. Manual barangay selection without a coordinate cannot supply distance.

The query ranks eligible Bacoor-associated centers against any valid WGS 84
point, including points outside Bacoor. There is no radius or same-barangay
filter, no nearest-polygon fallback, and no implication of road reachability.

### Interpreting the distance safely

The service computes an approximate geodetic straight-line distance between the
submitted point and each eligible center's stored WGS 84 coordinate. It is not
road distance and it is not a safe-route calculation. It does not account for
road closures, flood depth, traffic, terrain, access restrictions, bridge
conditions, or any other live hazard. The nearest result is not necessarily the
safest destination.

Center records contain no live occupancy signal. Inclusion does not guarantee
that a center is currently open, has space, is accessible, or is reachable.
During an emergency, users should follow official local instructions. These
limitations describe the implementation and do not create an evacuation order
or an unreviewed legal or operational assurance.

## Public response schema

HTTP 200, including an empty eligible result. All fields below are required,
non-null, and the only permitted fields. Unknown keys are rejected at every
object level. Returned coordinates belong to **centers**, never to the user.

| Field | Shape / origin |
| --- | --- |
| `centers` | Array, 0 through requested limit (absolute maximum 10), original server order |
| `distance_method` | Exactly `APPROXIMATE_STRAIGHT_LINE` |
| `warnings` | Exact nonempty string array for the result state below |
| `centers[].public_identifier` | Canonical lowercase hyphenated UUID string, from future `public_id`; unique in response |
| `centers[].name` | Trimmed nonempty public center name, maximum 180 characters |
| `centers[].address` | Trimmed nonempty authorized public address |
| `centers[].barangay` | Object containing only `psgc_code` and `name` |
| `barangay.psgc_code` | String of exactly ten ASCII digits; preserve leading zeros |
| `barangay.name` | Trimmed nonempty current reference label, maximum 160 characters |
| `centers[].latitude`, `longitude` | Finite JSON numbers within WGS 84 bounds, from existing center decimal fields |
| `centers[].approximate_distance` | Nonnegative finite JSON number, meters, rounded to one decimal after ordering |
| `centers[].distance_unit` | Exactly `meters` |
| `centers[].verified_on` | Valid calendar date in exactly `YYYY-MM-DD` form |
| `centers[].source_attribution` | Trimmed nonempty `source.organization`, maximum 200 characters |
| `centers[].limitations` | Nonempty array of nonempty literal text; mandatory statements below |

No `id`, `contact_information`, `capacity`, `notes`, `permitted_use`,
`reviewed_by`, `change_message`, `request_coordinate`, `susceptibility`, or
`expert_rules`. No private contacts, internal/restricted provenance, approval
comments, audit messages, users, classifications, geometry, or raw user input.

Public text is literal text, not HTML or Markdown. Consumers must escape/render
it as text and must not auto-execute markup or links. Serializers verify shape,
not institutional authorization or the truth of a facility record. They are not
HTML sanitizers. Control characters other than tab/newline/carriage return are
rejected. Trim surrounding whitespace on human-readable fields, not identifiers.

### Exact populated response wording

`warnings` contains exactly:

> Distances are approximate straight-line measurements. They do not represent road distance, route safety, accessibility, availability, or an evacuation recommendation.

Each center's `limitations` starts with these statements, in order:

1. `Verification does not confirm current opening, accessibility, capacity, or route safety.`
2. `DERIVED ADMINISTRATIVE REFERENCE—NOT CITY-VERIFIED`
3. `Administrative boundaries only; they do not indicate flood susceptibility or current conditions.`

Append nonblank, trimmed `center.limitations` and `source.limitations` as separate
literal strings in that order, removing exact duplicates. These fields and the
public name/address/organization must have been reviewed for public release;
approval must not be treated as authorization to copy internal notes. If a
material restriction cannot be conveyed safely, exclude the record until the
data owner supplies releasable content. Never substitute `permitted_use`, notes,
reviewer identity, or a private contact as fallback attribution/limitations.

The boundary statements are required because the current association uses the
pending-validation reference layer; center verification does not validate that
layer. No raw source record is serialized.

Example is **synthetic contract data, not a real facility or PSGC assignment**:

```json
{
  "centers": [{
    "public_identifier": "a95e27e1-7fb0-4c41-871c-f8e13b2534b8",
    "name": "SYNTHETIC CONTRACT CENTER - NOT A REAL FACILITY",
    "address": "Fictional test address",
    "barangay": {"psgc_code": "0000000000", "name": "Synthetic contract barangay"},
    "latitude": 14.4629,
    "longitude": 120.9647,
    "approximate_distance": 842.6,
    "distance_unit": "meters",
    "verified_on": "2026-09-19",
    "source_attribution": "Synthetic test organization",
    "limitations": [
      "Verification does not confirm current opening, accessibility, capacity, or route safety.",
      "DERIVED ADMINISTRATIVE REFERENCE—NOT CITY-VERIFIED",
      "Administrative boundaries only; they do not indicate flood susceptibility or current conditions."
    ]
  }],
  "distance_method": "APPROXIMATE_STRAIGHT_LINE",
  "warnings": [
    "Distances are approximate straight-line measurements. They do not represent road distance, route safety, accessibility, availability, or an evacuation recommendation."
  ]
}
```

### Exact empty result

HTTP 200, no special error code and no invented records:

```json
{
  "centers": [],
  "distance_method": "APPROXIMATE_STRAIGHT_LINE",
  "warnings": [
    "No eligible verified evacuation centers are currently available for this location.",
    "Distances, when available, are approximate straight-line measurements and are not route-safety recommendations."
  ]
}
```

This means no eligible releasable records, not proof that no facilities exist.
A failed database query must produce the generic 500 response, not a misleading
empty success. A known unsupported/missing reference identity excludes the
affected records; absence of eligible reference data can yield an empty result.

## Error contract for Day 3

| Condition | HTTP | JSON shape |
| --- | --- | --- |
| Malformed JSON | 400 | `{"detail": "Malformed JSON."}`; normalize parser exceptions to avoid reflecting invalid tokens |
| Missing/invalid fields | 400 | Existing DRF field-to-list shape, e.g. `{"latitude": ["Enter a JSON number."]}` |
| Unknown keys | 400 | `{"non_field_errors": ["Unknown fields are not allowed."]}`; do not echo supplied keys |
| Non-object input | 400 | DRF `non_field_errors` list; no supplied values |
| Unsupported media type | 415 | `{"detail": "Unsupported media type. Use application/json."}` |
| Unsupported method | 405 | `{"detail": "Method not allowed."}` and `Allow: POST, OPTIONS` |
| Request body exceeds 1,024 bytes (Day 3 addition) | 413 | `{"detail": "Nearest-center request is too large."}` |
| Endpoint rate exceeded (Day 3 addition) | 429 | `{"detail": "Too many nearest-center requests. Try again later."}`; preserve `Retry-After` |
| Unexpected internal failure | 500 | `{"detail": "Nearest-center lookup is temporarily unavailable."}` |

400 field messages/codes use DRF's existing conventions; clients must branch
on HTTP status and field keys rather than compare every framework message.
No coordinate values, SQL, stack traces, internal paths, or raw exceptions are
allowed. Parse/media/method/internal strings above are frozen for the future
view; Day 1 does not claim HTTP tests for an absent endpoint. Network timeouts
are client failures, not an additional wire response. Day 3 must set
`Cache-Control: no-store` and avoid lookup sessions/audit/analytics writes.
Reviewed Day 3 controls enforce a 1,024-byte actual exposed-stream body limit,
reading at most 1,025 bytes, and reject declared lengths above the cap early.
The endpoint uses a scoped default 30 POST attempts/minute per remote IP,
overridable with `FLOODSENSE_NEAREST_CENTER_RATE`. OPTIONS and rejected methods
do not consume quota. Authentication is disabled explicitly; output is JSON
even for HTML Accept preferences. All responses from the view include
`Cache-Control: no-store`, `Pragma: no-cache` and `Allow: POST, OPTIONS`.

Throttle metadata is short-lived IP identity/timestamps, never coordinates or
responses. Client forwarding headers are not trusted. Local-memory throttling
is process-local and non-atomic; deployment needs shared/upstream controls,
correct proxy identity and transport framing/body limits. This does not certify
production readiness. The exact 413/429 additions and integration requirements
are handed off in `../../docs/GPS_STREAM_A_NEAREST_CENTER_DAY_3_HANDOFF.md`.

## Fail-closed eligibility policy for Day 2

Re-evaluate all gates on every request, including related source and area data.
Do not rely on cached Admin status or a prior verification transition.

1. Center `verification_status == VERIFIED` and `publication_status == APPROVED`.
2. `verified_on` is present and a valid date. No invented expiry/freshness
   threshold; the date is historical verification, not evidence of opening now.
3. Center source `status == APPROVED`, `is_publicly_releasable == True`, and
   `source_type != DEMONSTRATION`. Restricted/retired/pending sources are excluded.
4. Name, authorized public address, and source organization are nonblank and
   compatible with the wire schema. Required public limitations can be produced.
5. Both stored coordinates are finite and within their WGS 84 ranges; null,
   NaN, infinity, malformed and out-of-range values fail closed even if a record
   bypassed `full_clean()`.
6. `geographic_area` is present and a supported enabled current reference
   barangay selected by `geography.services.eligible_bacoor_reference_barangays()`.
   Use `public_psgc_code(area.code)` and its nonempty stored public name. Only
   the controlled current 47-barangay identities are supported; a regex match
   alone does not establish membership. Day 2 must verify reference readiness
   and membership consistent with the resolver (one eligible reserved source,
   one eligible City, 47 distinct valid barangay identities/geometries).
   Null, City, demo-zone, unrelated, disabled, malformed, or unsupported
   associations are excluded. No guessed label from coordinates or name.
7. A stored, valid, unique stable public UUID exists. Never fall back to the PK.

The reference area's pending-validation status is a deliberate administrative
identity exception, disclosed in limitations. The **center and center source**
must still be approved. This does not promote boundary data or grant knowledge
for susceptibility assessment. The current model has no separate `is_active`
or opening-status flag; `VERIFIED` excludes `DRAFT`, `IN_REVIEW`, and `INACTIVE`.
Do not invent fields or imply operational availability.

The shared `provenance.policies.permitted_records()` expects a record `status`
field; centers instead have `publication_status`. Day 2 must implement the
explicit center predicate rather than calling that helper unchanged. Admin
verification remains unchanged and is intentionally weaker than resident eligibility.

## Stable public identifier — schema handoff, not a Day 1 migration

Future model field (with `import uuid`):

```python
public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
```

Wire name: `public_identifier`. The sequential internal `BigAutoField` primary
key couples clients to storage and reveals row enumeration; it is not the
resident identifier. A UUID is an identifier, not an authorization secret.
Generate UUIDv4 once per row. Keep it through edits, verification, deactivation,
re-review, and deployment; never derive it from names, coordinates, timestamps,
or IDs. Never regenerate it while serializing a request.

Day 2 migration author must review the graph after `evacuation.0001_initial`:
add a temporary nullable UUID column without a shared one-time unique default,
backfill a distinct `uuid.uuid4()` for each existing row using the historical
model and migration database alias, then enforce non-null/unique and the callable
default. Coordinate writes during rollout so no row escapes backfill. Tests must
cover multiple legacy rows, uniqueness, new-row defaults, and stability through
edits/transitions. Do not rewrite `0001_initial`. No new center records are needed.

## Authoritative distance strategy — implementation deferred

Use a parameterized PostGIS expression, conceptually:

```sql
ST_Distance(
  ST_SetSRID(ST_MakePoint(longitude::double precision, latitude::double precision), 4326)::geography,
  ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
  true
)
```

The two bound values are user longitude, then latitude. `ST_MakePoint` uses
longitude as X and latitude as Y. The geography overload of `ST_Distance` with
`true` uses spheroidal geodesic distance in meters. This is the selected
implementation of the product's approximate straight-line measure, not a road
or safe route. See the primary [ST_MakePoint documentation](https://postgis.net/docs/ST_MakePoint.html)
and [ST_Distance documentation](https://postgis.net/docs/ST_Distance.html).

Use GeoDjango `Func`/`Cast` expressions or reviewed parameterized SQL; never
interpolate user input into SQL. Existing decimal latitude/longitude are the
only canonical stored coordinates. Construct the geography transiently; no
duplicate stored Point field. Guard construction with a conditional expression
for valid finite/range-checked coordinates so SQL evaluation order cannot
normalize bad records into seemingly valid points.

Sort ascending by full-precision computed meters, then by stable `public_id`
ascending for exact ties. Filter every eligibility gate **before** the final
limit; do not take ten candidates then discard invalid records without filling
from later eligible results. Convert wire distance with `round(distance, 1)`
only after sorting and slicing. Rounded ties retain the authoritative order.
Mobile may display meters/kilometers but must not recalculate or re-sort.

Existing foreign-key indexes support source/area joins; the UUID unique
constraint will provide its index. No additional spatial index is justified
without measurements: this expression ranks a bounded local facility inventory
and there is no stored point index to use. No dataset-size claim is made here.
Day 2: synthetic known-distance, zero-distance, tie, exclusion, and SELECT-count
tests. Day 3: endpoint query count, response bytes, bounded-result/no-write tests.
Day 6: representative inventory sizes, cold/warm latency distributions and
`EXPLAIN (ANALYZE, BUFFERS)` in a disposable environment; inspect N+1 behavior
and only then propose an expression index if justified. Do not retain user
coordinates in captured SQL/performance evidence.

## Executable scope and handoff

`contracts.py` freezes vocabulary; `serializers.py` validates wire-shaped
mappings via `Serializer(data=payload).is_valid()` and renders `.data` as JSON.
It does not query eligibility, authorize text, calculate/verify ordering, enforce
the per-request limit on responses, or save anything. Day 2 must assemble an
explicit mapping and convert stored Decimals/date/UUID into their wire forms
before validation; passing arbitrary model objects or calling `.data` without
validation is not a substitute for the service gates.

`test_day1_nearest_contract.py` uses synthetic in-memory examples with database
access blocked by pytest-django. It verifies the schema; on Day 3 its former
route-absence assertion was replaced by exact route registration. The new
`test_day3_nearest_api.py` covers the HTTP boundary and database-backed behavior.

Stream A implements this contract through one production
`NearestCenterProvider` adapter. It rejects extra fields, preserves UUID/PSGC
strings and server ordering, validates the exact distance method, unit, dates,
limitations and warning vocabulary, and retains top-level warnings in the UI.
The older missing-contract inventory is superseded. Authorized populated data,
fresh Admin browser evidence, and deployment verification remain separate
acceptance dependencies.

See `../../docs/GPS_STREAM_C_D_DAY_1_PRIVACY_REVIEW.md` and
`../../docs/GPS_STREAM_C_D_DAY_1_BASELINE.md` for evidence and limits.
