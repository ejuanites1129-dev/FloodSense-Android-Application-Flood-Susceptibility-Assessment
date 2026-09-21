# Stream A handoff — nearest verified centers, Day 3

**Date:** 21 September 2026. **Owner:** Team B, Streams C/D.
**Status:** Backend HTTP contract implemented and tested. Production Flutter
adapter, strict parser, warning-envelope integration and device verification
remain Stream A / Day 4 work. No mobile files were changed in this task.

The [frozen contract](../server/evacuation/NEAREST_CENTER_CONTRACT.md) is the
authoritative schema and exact warning text. This handoff supersedes the
missing-backend inventory in `mobile/STREAM_C_NEAREST_CENTER_HANDOFF.md`;
it does not claim mobile integration is complete.

## Calling the endpoint

| Item | Implemented contract |
| --- | --- |
| Path | `/api/v1/evacuation-centers/nearest/` (retain trailing slash) |
| Method | POST; OPTIONS supplies metadata without a lookup; other methods return 405 |
| Content type | `application/json`; `application/json; charset=utf-8` accepted |
| Authentication | Public; no JWT, session or CSRF token required; malformed Authorization is ignored |
| Latitude | Required finite JSON number, -90 through 90 inclusive |
| Longitude | Required finite JSON number, -180 through 180 inclusive |
| Limit | Optional JSON integer, default 3, range 1–10; `3.0` is invalid |
| Request size | At most 1,024 body bytes, including whitespace; larger bodies return 413 |
| Request rate | Default 30 POST attempts/minute per server-observed remote IP; 429 includes Retry-After |
| Caching | Every response from this view has `Cache-Control: no-store` and `Pragma: no-cache` |
| Response | JSON, including errors; HTML Accept preferences do not enable a browsable API |

Use the existing API base URL and append `evacuation-centers/nearest/` if that
base already ends in `/api/v1/`. Do not duplicate `/api/v1/` or put coordinates
in a URL. No radius, mode, barangay, sort or identity field is accepted.

Synthetic request (not a real user location):

```json
{"latitude": 0, "longitude": 0, "limit": 3}
```

Numeric strings, booleans, null, nonfinite numbers, missing coordinates,
non-object bodies and unknown keys fail validation. Query/header/cookie values
cannot supply missing body coordinates. `Allow` is exactly `POST, OPTIONS`.
HEAD returns 405 with the normal HTTP omission of a response body.

## Strict response parsing

Accept HTTP 200 only if the complete envelope validates:

- Exactly `centers`, `distance_method`, `warnings` at the top level.
- `distance_method` is `APPROXIMATE_STRAIGHT_LINE`.
- `centers` is a list no longer than the requested limit and never longer than 10.
- Each center has exactly `public_identifier`, `name`, `address`, `barangay`,
  `latitude`, `longitude`, `approximate_distance`, `distance_unit`, `verified_on`,
  `source_attribution`, `limitations`.
- `barangay` has exactly `psgc_code` and `name`. Keep the ten ASCII digits as a
  string, including leading zeroes; never parse it as an integer.
- Preserve canonical lowercase UUID strings; reject invalid or duplicate IDs.
- Check finite numeric coordinates and their bounds. Distance must be finite,
  nonnegative, numeric meters; the server rounds to one decimal after sorting.
- `distance_unit` is `meters`; `verified_on` is a real calendar date in strict
  `YYYY-MM-DD` form. Reject missing/null/invalid fields rather than guessing.
- Enforce public text constraints and required warning/limitation wording and
  order from the frozen contract. Render text literally, without HTML/Markdown
  execution or guessed private-field fallbacks.

Preserve server order, even when displayed rounded distances tie. Do not
calculate authoritative distances or resort results on the phone. Formatting a
distance for display in meters/kilometers does not change the wire unit.
Returned coordinates are facility coordinates; there is no user-coordinate
field. Do not display raw database IDs, contacts, notes, capacity or inferred
opening, route-safety or susceptibility information.

Empty `centers: []` is a valid HTTP 200 only with the exact two empty-result
warnings in the contract. It means no eligible releasable records, not proof
that no physical facilities exist. Populated output contains the exact
straight-line warning and each center's required three limitations followed
by any approved additional limitations. Neither result is an evacuation
recommendation.

## Provider mismatch to resolve in Stream A

`NearestCenterProvider.findNearest` currently returns
`Future<List<VerifiedCenter>>`. That interface cannot carry mandatory top-level
warnings. Stream A must return a result/envelope containing centers and warnings,
or introduce another explicit state path that preserves and displays warnings
for both populated and empty results. Do not silently discard the envelope.

The current presentation model is not a complete strict wire parser. Implement
the checks above at the HTTP boundary and add valid, empty, unknown-field,
missing-field, malformed-date/UUID/PSGC and invalid-numeric contract fixtures.
Preserve the existing controller's location lifecycle and server-order behavior.
Interface and UI changes remain owned by Stream A, not this backend task.

## Errors and recommended mobile states

| Condition | Wire response / recommendation |
| --- | --- |
| Malformed JSON, 400 | `{"detail":"Malformed JSON."}` |
| Invalid fields, 400 | Frozen field-to-list validation shape; unknown keys use `non_field_errors` without reflecting supplied keys |
| Oversized body, 413 | `{"detail":"Nearest-center request is too large."}` |
| Unsupported type, 415 | `{"detail":"Unsupported media type. Use application/json."}` |
| Unsupported method, 405 | `{"detail":"Method not allowed."}`; integration/request error |
| Rate limited, 429 | `{"detail":"Too many nearest-center requests. Try again later."}`; recoverable state, respect Retry-After before a user-triggered retry |
| Service/database failure, 500 | `{"detail":"Nearest-center lookup is temporarily unavailable."}` |
| Network unreachable | `offline` |
| Client timeout | `timeout` |
| HTTP 500/502/503/504 | `serverUnavailable` |
| Invalid/incomplete 200 schema | `malformedResponse`; never reinterpret as empty success |
| HTTP 400/413/415 | Contract/request error; no automatic retry |
| Other unexpected failures | Recoverable generic state |

Branch on status and field keys, not every framework validation sentence.
Do not show raw exception text or automatically retry location-bearing requests
in a loop. A missing/invalid Retry-After must not trigger immediate repeated
requests. OPTIONS and rejected methods do not use the POST rate quota.

## Privacy, rollout and evidence

Call only after explicit confirmation of a coordinate-bearing location. Manual
barangay selection alone cannot provide distance. Expand purpose copy to cover
approximate center lookup before shipping the adapter. Coordinates belong only
in the JSON body; avoid body logging, persistent storage, analytics and crash
breadcrumbs. Clear coordinate/results state with the existing reset, location
change and flow-exit lifecycle. Preserve warnings while showing results.

The backend does not deliberately log request bodies or store coordinates,
sessions or lookup audit records. Its short-lived throttle cache holds remote
IP identity and request timestamps, not coordinates or responses. The default
cache is process-local; shared rate controls and deployed proxy/APM/SQL logging
privacy still require deployment verification. Client-supplied X-Forwarded-For
is ignored; trusted ingress must set remote identity correctly or rate-limit
upstream. Never put coordinates in query strings: upstream access logs can
record a URL even when this API rejects its input.

The existing UUID migration `evacuation.0002_evacuationcenter_public_id` must be
applied in each target database. Day 3 adds no migration or dependency. The
current local application database has no centers; an empty response is honest.
Use isolated synthetic fixtures for populated tests, not invented presentation
records or official-data imports.

Backend verification: 85 new HTTP cases, 599 complete backend tests; unchanged
mobile regression: clean analysis and 167 passing tests. These do not substitute
for production-adapter parsing, mobile warning rendering, physical-device
results or Admin-to-API-to-Flutter acceptance. See the
[Day 3 guide](GPS_STREAM_C_D_DAY_3_GUIDE.md) for exact evidence and remaining work.
