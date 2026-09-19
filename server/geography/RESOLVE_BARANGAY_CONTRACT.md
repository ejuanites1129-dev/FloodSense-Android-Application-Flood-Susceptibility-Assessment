# Proposed `resolve-barangay` contract for team freeze

**Status:** Implemented on Day 2 against the Day 1 proposal; team contract
approval remains pending.
**Active route:** `POST /api/v1/geography/resolve-barangay/`

This endpoint will identify an administrative barangay from one temporary
coordinate. It will not calculate susceptibility, determine an official
address, report current conditions, or persist location.

## Transport and request

- Request content type: `application/json`.
- `POST` performs the lookup. DRF may answer `OPTIONS`; `GET`, `PUT`, `PATCH`,
  and `DELETE` must return HTTP 405 and perform no lookup.
- Coordinates are WGS 84 (`EPSG:4326`) JSON numbers, not strings or booleans.

```json
{
  "latitude": 14.41235,
  "longitude": 120.97654
}
```

Both fields are required and non-null. Values must be finite. Latitude is in
`-90..90`; longitude is in `-180..180`. Unknown request fields should be
ignored by the serializer but must never influence the query or response.

Field-validation errors use the repository's existing DRF shape and HTTP 400:

```json
{
  "latitude": ["Enter a finite number."]
}
```

Malformed JSON returns HTTP 400 with DRF's `detail` field. A non-JSON media type
returns HTTP 415. Unsupported methods return HTTP 405 with `detail` and an
`Allow: POST, OPTIONS` header. Validation, parse, method, and unexpected-server
errors must not echo coordinates. An unexpected server failure returns HTTP
500 with only `{"detail":"The resolver is temporarily unavailable."}`.

## Success-state envelope

Every valid coordinate returns HTTP 200, including outside, ambiguous, and
known-unavailable outcomes. The coordinate echo is rounded to five decimal
places (roughly meter scale near Bacoor) and is never logged or stored.

### `RESOLVED`

Exactly one eligible barangay geometry covers the point.

The identity below is deliberately fictional contract data, not an official
PSGC assignment.

```json
{
  "resolution_state": "RESOLVED",
  "coordinate": {
    "latitude": 14.41235,
    "longitude": 120.97654,
    "precision_decimal_places": 5
  },
  "barangay": {
    "psgc_code": "0000000000",
    "name": "Synthetic contract example"
  },
  "boundary": {
    "layer_kind": "ADMINISTRATIVE_REFERENCE",
    "data_status": "PENDING_VALIDATION",
    "source_status": "PENDING_VALIDATION",
    "city_verified": false
  },
  "limitations": [
    "DERIVED ADMINISTRATIVE REFERENCE—NOT CITY-VERIFIED",
    "Administrative boundaries only; they do not indicate flood susceptibility or current conditions."
  ]
}
```

The mobile app presents the name for confirmation. It must allow correction by
manual pin or barangay selection and must not start an assessment automatically.

### `OUTSIDE_BACOOR`

The controlled layer is complete and eligible, no barangay covers the point,
and the Bacoor City polygon does not cover it. The envelope is identical to
`RESOLVED` except `resolution_state` is `OUTSIDE_BACOOR` and `barangay` is
`null`. Mobile keeps manual selection available and does not force a barangay.

### `AMBIGUOUS_BOUNDARY`

Two or more eligible barangay polygons cover the point, including a shared
boundary. The envelope uses `AMBIGUOUS_BOUNDARY` and `barangay: null`. Mobile
explains the boundary uncertainty and requests manual confirmation; the server
must never choose an arbitrary polygon.

### `UNAVAILABLE`

The controlled layer cannot support a trustworthy decision—for example, the
reserved source/city is absent, the eligible current-barangay count is not
exactly 47, or an apparent gap exists inside the Bacoor City polygon. The
envelope uses `UNAVAILABLE` and `barangay: null`. This is a valid neutral state,
not a susceptibility result or a reason to force selection.

The executable response serializer allowlists only the five top-level fields
shown above. No geometry, database ID, susceptibility, rule, fact, inference,
private provenance, or internal note is permitted.

## Eligible controlled layer

`eligible_bacoor_reference_barangays()` encodes the row-level selector:

- `GeographicArea.area_type == BARANGAY`;
- `GeographicArea.is_enabled == true`;
- area status is `PENDING_VALIDATION`;
- source name is the reserved
  `Bacoor administrative boundaries—derived reference` value;
- source type is `AGENCY_DATASET`;
- source status is `PENDING_VALIDATION`; and
- source is publicly releasable.

Day 2 must additionally fail closed to `UNAVAILABLE` unless there is exactly
one eligible source, exactly one enabled City row with code
`PSGC_0402103000`, and exactly 47 eligible barangay rows. The globally unique
area `code` prevents duplicate PSGC-backed rows. Each current barangay is one
`MultiPolygonField(srid=4326)` row, so merged and non-contiguous barangays are
already represented without merging query results at request time.

Inactive, restricted, retired, approved-but-unrelated, demonstration, wrong
source, non-public, City, and other-area rows are excluded. This contract does
not change any approval or publication state. The checked-in layer is a
reproducible derivative pending institutional validation, not City-verified.

## Spatial rules for Day 2

1. Validate the request before constructing geometry.
2. Construct `Point(longitude, latitude, srid=4326)`—x is longitude and y is
   latitude.
3. Confirm layer readiness before interpreting a zero-match result.
4. Use `geometry__covers=point` for eligible barangays. `covers` includes the
   polygon boundary, allowing multiple matches to expose a shared boundary.
5. One match is `RESOLVED`; more than one is `AMBIGUOUS_BOUNDARY`.
6. With zero matches, test the controlled City geometry. Outside the City is
   `OUTSIDE_BACOOR`; inside/covered by the City indicates an inconsistent gap
   and is `UNAVAILABLE`.
7. A point in a polygon hole is not covered. It therefore follows the same
   City check rather than being assigned to the surrounding polygon.
8. MultiPolygon components are handled by PostGIS/GeoDjango `covers`.
9. A coastal point outside the City is outside; a point exactly on an outer
   boundary may resolve only if exactly one barangay covers it. Shared matches
   remain ambiguous.
10. No nearest-polygon fallback, buffer, tolerance, or coordinate snapping is
    approved. Any future tolerance requires a team policy decision and tests.

## Privacy and no-write proof

The view performs request validation and `SELECT` queries only. It
must not call `save`, `create`, `update`, audit/event APIs, analytics, or logging
with a request body. Current middleware is standard Django/WhiteNoise/session/
authentication middleware; no repository middleware was found that logs
request bodies. Day 2 endpoint tests must snapshot relevant table counts and
capture queries to prove that a lookup issues no insert/update/delete statement.

Day 1 tests already prove finite/range/type validation, stable response shape,
all four representative states, five-decimal echo, allowlisted fields,
susceptibility/geometry absence, exact selector filters, and no writes by the
contract builders. Day 2 must add active-route tests for JSON-only parsing,
405 behavior, synthetic inside/outside/shared-boundary/hole/multipolygon cases,
layer readiness, database exceptions, and query-level no-write behavior.
