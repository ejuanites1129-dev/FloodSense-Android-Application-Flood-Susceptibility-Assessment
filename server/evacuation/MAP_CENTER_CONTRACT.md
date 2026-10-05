# Evacuation-center map catalog and nearest-25 shortlist

**Added:** 5 October 2026, at the project owner's request.

This read-only catalog supports showing eligible facility markers when the
resident map opens. Its pin-centered POST selects up to 25 nearest references;
the original coordinate-free GET remains compatible. Neither acquires device
GPS, persists coordinates or triggers an assessment. The
separate [nearest-center contract](NEAREST_CENTER_CONTRACT.md) is unchanged.

## Transport

`GET /api/v1/evacuation-centers/map/` is public and JSON-only. No authentication,
query parameter, or request body is needed for GET. Supplied query parameters or a
declared nonempty body are rejected with a generic 400 response without
reflecting their contents. `OPTIONS` supplies metadata without a database
query. POST accepts only finite numeric WGS84 `latitude` and `longitude` in a
JSON object. Unknown keys, strings, booleans, null/out-of-range coordinates,
query parameters and oversized/malformed bodies are rejected. POST reuses the
nearest endpoint's bounded parser. Other methods (including `HEAD`) return 405.
Every response includes `Cache-Control: no-store`, `Pragma: no-cache`, and
`Allow: GET, POST, OPTIONS`. Coordinates are never placed in a URL or persisted.

GET and POST share the existing `nearest_centers` 30/minute per-client budget;
metadata and rejected methods do not consume it. Network failures are returned
as a generic 500 without database details, coordinates, or exception logging.
No application database rows or user-coordinate history are written.

## Exact response schema

All fields are required and unknown fields are rejected at every object level.

| Field | Shape |
| --- | --- |
| `centers` | Array of 0–25 safe centers for POST; 0–1000 for legacy GET |
| `warnings` | Exact ordered, nonempty strings described below |
| `has_more` | JSON boolean; true only when another eligible safe center exists |
| `centers[].public_identifier` | Canonical lowercase hyphenated UUID string |
| `centers[].name` | Trimmed nonempty literal public text, maximum 180 characters |
| `centers[].address` | Trimmed nonempty literal public text |
| `centers[].barangay` | Object containing only `psgc_code` and `name` |
| `barangay.psgc_code` | Ten ASCII digits, including leading zeros |
| `barangay.name` | Trimmed nonempty literal text, maximum 160 characters |
| `centers[].latitude`, `longitude` | Finite WGS 84 JSON numbers |
| `centers[].verified_on` | Valid calendar date, exactly `YYYY-MM-DD` |
| `centers[].source_attribution` | Trimmed nonempty public text, maximum 200 characters |
| `centers[].limitations` | Required public limitation strings plus reviewed caveats |

There is no distance field, `distance_method`, database ID, contact information,
capacity, reviewer identity, note, private provenance, raw geometry,
susceptibility, or Expert System knowledge. Consumers render public text as
literal text, never executable markup.

POST ranks **all eligible candidates**, using the existing PostGIS geography
straight-line distance expression and UUID tie-breaker, before applying the
25-record cap. Malformed records do not consume the cap. A 26th safe candidate
sets `has_more`; it is true only with a full 25-center shortlist. The initial
map pin is a boundary-bounds midpoint reference, not a confirmed personal
location; Prepare's distance/nearest claims still require location confirmation.
Changing the pin or explicitly refreshing requests a new shortlist. Camera
movement and legend/tab/sheet interaction do not rerank or refresh it. Nearest
metadata may enrich shortlist members but must not re-add excluded markers.

Legacy GET order is stable by public UUID, **not nearest-first**. Safe records are validated
before counting toward the 1000-marker cap. One extra safe record establishes
`has_more`; malformed rows do not consume the cap. The application must not
claim this capped catalog contains every center or use UUID order as distance
ranking. Use the existing nearest endpoint after confirming a coordinate.

## Eligibility and geography

Every GET/POST rechecks current center verification/publication, verification date,
approved/public source, non-demonstration source type, finite coordinate, and
the entire controlled Bacoor administrative-reference layer. It reuses the
existing verified-center candidate policy and boundary-readiness service.
The stored center point must also be covered by its assigned supported
barangay polygon (including rejection of polygon holes). Missing, invalid,
disabled, mismatched, or incomplete reference geometry fails closed.

Normal output never includes draft, in-review, inactive, restricted, retired,
temporary, malformed, or privately sourced records. Public approval and a
schema-valid value do not independently establish institutional truth; the
existing reviewed publication workflow remains responsible for that.

## Exact warning strings

`MAP_WARNING`:

```text
Evacuation-center reference information only. This map does not confirm that a center is open, available, reachable, or safe.
```

`EMPTY_MAP_WARNING`:

```text
No eligible verified evacuation-center information is available for this map.
```

`LOCAL_EMPTY_MAP_WARNING`:

```text
No locally approved temporary evacuation-center records are available for this map.
```

`MAP_LIMIT_WARNING`:

```text
Only the first 1,000 eligible centers are shown. Other eligible centers may exist.
```

Genuine nonempty warnings: `[MAP_WARNING]`.

Genuine empty warnings: `[EMPTY_MAP_WARNING, MAP_WARNING]`.

For POST, append this exact warning instead of `MAP_LIMIT_WARNING` when truncated:

```text
Only the 25 nearest eligible centers around the map pin are shown. Other centers remain hidden until the pin location changes.
```

Append the applicable limit warning only when `has_more` is true. Per-record limitations
remain exactly the existing mandatory center and administrative-reference
limitations followed by trimmed, nonblank, exact-deduplicated center/source
caveats.

## Local temporary testing

The same GET/POST route returns **only** approved temporary records when all existing
local gates pass: DEBUG, `FLOODSENSE_LOCAL_TESTING`, loopback PostGIS host,
loopback HTTP host, and loopback request source. Otherwise it uses genuine
public eligibility. Genuine and temporary records are never mixed.

Temporary output has the same schema with these mandatory differences:

- Root and every center have `data_status: "DEMONSTRATION"`.
- `verified_on` is null; test approval is not facility verification.
- Source and record demonstration markers remain unchanged in the database.
- The source must have explicit local reviewer/date approval, remain
  demonstration and non-public, and the center must be locally approved.
- No verification date or capacity may be invented; those must remain null.
- Legacy `LOCAL TEST -` names are not required for this ordinary workflow.

`LOCAL_PREVIEW_WARNING` remains the existing exact text:

```text
LOCAL DEMONSTRATION - NOT A REAL EVACUATION CENTER. Display test only; not verified, open, or available for use.
```

Temporary nonempty warnings: `[LOCAL_PREVIEW_WARNING, MAP_WARNING]`.

Temporary empty warnings:
`[LOCAL_PREVIEW_WARNING, LOCAL_EMPTY_MAP_WARNING, MAP_WARNING]`.

Append `MAP_LIMIT_WARNING` if truncated. Per-record limitations begin with
`LOCAL_PREVIEW_WARNING` and the two existing administrative-reference
limitations. The old separate preview switch alone cannot enable this catalog.
Turning local testing off, revoking source approval, or withdrawing the center
excludes temporary markers on the next explicit catalog request. No automatic
polling or background refresh is introduced.

## Setup and tests

No package, migration, seed, import, or local database-row change is required.
Teammates restart Django and rebuild the updated client after pulling code.
Synthetic tests create fixtures only inside the isolated PostGIS test database:

```powershell
.\scripts\test_operations_isolated.ps1 -Port 55435 -TestArgs @('server/evacuation', '--create-db', '-q')
```
