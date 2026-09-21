# Streams C/D Day 3 — public nearest-center HTTP boundary

**Date:** 21 September 2026. **Owner:** Team B.
**Status:** Backend implementation, regression verification, map code review and
Android handoff complete. Fresh Day 3 browser layout/accessibility verification
is pending; do not mark the complete C/D Day 3 acceptance gate passed yet.

## Starting point and preserved work

The worktree was clean on `main` at
`889a2732d42043c91c3a2426fc254727d5279a16`; Day 1/2 work was already committed,
despite the task's older uncommitted-work description. Focused pre-change
Day 1/2 contract, service, UUID and Admin tests passed: **254 passed**.

Day 3 leaves the frozen request/response serializers, service, model, migration,
Day 2 tests, mobile, geography, Expert System and research datasets unchanged.
It adds the reviewed HTTP control constants and updates the former Day 1
route-absence assertion to assert the now-registered frozen route. No eligibility,
distance or response assembly logic is duplicated in the view. No Git commit,
push, pull, data import, privilege change or application migration was run.

## Route and implementation

`POST /api/v1/evacuation-centers/nearest/`, named
`evacuation:nearest-centers`, is the only evacuation route. Its app URL module
is included by `server/config/urls.py`.

| File | Responsibility |
| --- | --- |
| `server/evacuation/views.py` | Public APIView, validation, existing service call, generic service-failure response, privacy headers |
| `server/evacuation/parsers.py` | JSON-only bounded body read and safe parse errors |
| `server/evacuation/throttles.py` | Scoped request rate using server-observed remote IP, ignoring untrusted forwarding headers |
| `server/evacuation/contracts.py` | Reviewed 1,024-byte limit and exact HTTP error strings |
| `server/evacuation/urls.py` | Single frozen route |
| `server/config/settings.py` | Endpoint-only throttle rate and validated environment override |
| `server/evacuation/test_day3_nearest_api.py` | HTTP, PostGIS integration, abuse controls and privacy/no-write regressions |
| `server/admin_portal/test_gps_day3_map_safety.py` | Map labels, fallback structure, long warning and provisional-data exclusions |

Authentication classes are empty and permission is AllowAny. Anonymous and
malformed-Authorization requests use the same public contract. There is no
SessionAuthentication or session CSRF requirement, and no session cookie is
created. Admin write protection is unchanged. Only POST and OPTIONS are
allowed; OPTIONS metadata and rejected methods perform no spatial work or
throttle-cache updates. HEAD's HTTP body is empty despite its 405 status.

Only JSON input is supported, including a charset parameter. Output is always
JSON, including under DEBUG or HTML Accept/format preferences. The request
serializer validates before the existing Day 2 service is called. The service
already validates the final response; the view returns its envelope unchanged.
There is no raw model API, browsable HTML or login redirect.

## Request controls and errors

POST throttling runs before parsing. The view then checks declared length,
checks media type and reads at most **1,025 actual exposed-stream bytes** to
enforce the **1,024-byte** body cap. The parser reads the request stream directly
because DRF's ordinary request.data path can skip parsing with missing/zero
Content-Length. ASGI tests cover actual bodies with missing, zero and falsely
small declared lengths. Malformed/negative declared lengths receive safe 400.

This is an application-stream limit, not a transport framing defense. A WSGI
server may already bound the stream using Content-Length, and ASGI/proxies may
buffer before the view runs. Deployment ingress must enforce request framing
and body caps before buffering. No unrelated upload limit was changed.

| Condition | HTTP | Exact detail or shape |
| --- | --- | --- |
| Populated or no eligible records | 200 | Frozen envelope; empty centers retain exact two empty warnings |
| Malformed JSON | 400 | `Malformed JSON.` |
| Invalid fields | 400 | Existing frozen field-to-list shape |
| Unknown fields | 400 | `{"non_field_errors":["Unknown fields are not allowed."]}` |
| Unsupported method | 405 | `Method not allowed.` |
| Body too large | 413 | `Nearest-center request is too large.` |
| Unsupported media type | 415 | `Unsupported media type. Use application/json.` |
| Rate exceeded | 429 | `Too many nearest-center requests. Try again later.`; Retry-After preserved |
| Unexpected service/database failure | 500 | `Nearest-center lookup is temporarily unavailable.` |

Detail strings use `{"detail":"..."}`. The broad exception catch is confined
to the service call, so serializer errors remain 400. Unexpected service errors
are never empty successes. Each response from this view has `Cache-Control:
no-store`, `Pragma: no-cache` and `Allow: POST, OPTIONS`. This does not claim
control over errors generated before routing or by external infrastructure.

`FLOODSENSE_NEAREST_CENTER_RATE` defaults to `30/min`. A positive integer and
supported DRF duration are required; an invalid override fails configuration
without echoing its value. Example override: `15/min`. Invalid POST attempts
also consume quota. No global throttle policy was replaced.

Throttle cache values contain only timestamps, keyed by scope and remote IP,
with a short TTL corresponding to the rate period. No coordinates, request
bodies or response content are cached. The default local-memory cache is per
process and DRF's counters are not atomic. Before deployment use an appropriate
shared cache (not database/file history) and/or an upstream rate limit. A trusted
proxy must establish remote identity or enforce client quotas itself; arbitrary
X-Forwarded-For values are deliberately ignored. Shared-IP users share quota.
This control is not complete DDoS protection or production-readiness evidence.

## Database, privacy and performance evidence

Isolated tests snapshot every installed model's rows/fields before and after
repeated populated requests. All snapshots remain identical, including sessions
and Admin LogEntry. Two requests execute eight SELECT statements and no writes;
the service remains at four SELECTs with a ready reference layer. Rejected
requests and OPTIONS run no database queries. Synthetic fixtures also cover
private-field exclusions, stable UUID ordering, exact limitations, honest empty
results and database/runtime/invariant failures without exception disclosure.

Result count is capped at ten. A representative ten-center synthetic response
is below 16 KB; this is not a universal byte cap because approved address and
additional limitation text do not have fixed wire lengths. Broader data-volume
and latency characterization remains Day 6 work.

The view does not deliberately log exceptions or body data. No submitted
coordinate appears in responses, cookies or redirect locations; center
coordinates are separate public facility data. This does not certify deployed
proxy/APM/crash/database SQL logs. In particular, rejecting query-string input
cannot erase URLs already recorded by access logging. The live negative test
used only synthetic `0,0`; clients must never put real coordinates in URLs.

## Stream D map/data-safety review

No concrete production map-code gap was found, so templates, JavaScript and
styles were not changed. Code review and existing/new regressions establish:

- Visible template OSM credit and non-collapsible map attribution; OSM is
  background context, not assessment information.
- Neutral administrative boundaries; fictional demonstration labels and
  separate demonstration styling; no susceptibility classifications added.
- Provisional MGB-like data excluded from resident area/reference APIs and
  map payloads; approved susceptibility layers remain explicitly unavailable.
- Server-rendered area selection and details outside the map, with keyboard
  controls and no-script fallback. Long warnings are retained in HTML and
  wrapping styles exist; visual readability still needs browser confirmation.
- Map-library/tile failure states remain separate from assessment availability.
  Boundary association and center verification do not establish center safety.

Three new regression tests use synthetic reference/provisional records and
in-memory long warning text. They test rendered structure and API exclusions,
not pixel layout or a screen reader. The separate Admin suite has 105 passes.

**Fresh browser evidence is pending:** the available computer-use inventory
reported no connected browsers. The user was asked to repeat `/management/map-data/`
at desktop and 320px widths, verify keyboard selection, visible attribution,
neutral labels and usable details with JavaScript disabled. Also inspect long
warning wrapping and map/tile failure fallback. The user's earlier Day 2
browser pass remains historical evidence, not a fresh Day 3 run. Record the
tester and result here when available before closing the Day 3 acceptance gate.

## Verification results

All Python test runs involving the database use the separate PostGIS
`test_floodsense` with `--reuse-db`; the application database is not a test target.

| Check | Result on 21 September 2026 |
| --- | --- |
| Pre-change focused Day 1/2 baseline | 254 passed |
| Final separate Day 1 / Day 2 service / UUID runs | 153 / 84 / 4 passed |
| New nearest-center HTTP suite | 85 passed |
| Complete evacuation suite | 329 passed |
| New map-safety suite | 3 passed |
| Complete Admin suite | 105 passed |
| Complete backend suite | 599 passed, 201 warnings |
| Ruff check: evacuation, admin_portal, config | Passed |
| Eight changed evacuation/Admin Python files: formatting | Passed |
| git diff --check | Passed |
| Whole evacuation formatting check | Two pre-existing untouched files, apps.py and workflow.py, would reformat; left intact |
| Additional config formatting check | Existing settings.py/urls.py formatting differences remain; confirmed the committed versions already fail this check |
| Django system check | No issues |
| makemigrations --check --dry-run | No changes detected |
| showmigrations evacuation | Existing 0001 and 0002 applied locally |
| Flutter analyze --no-pub | No issues |
| Flutter test --no-pub | 167 passed; current checkout, no mobile changes |

The complete backend run includes the 153 Day 1 schema/route cases, 84 Day 2
service cases and four UUID/migration cases. Framework warnings concern the
existing URLField future default, importlib metadata deprecation and missing
collected staticfiles directory; they are not test failures. The current
Flutter count is 167, not the older documented 164-test checkpoint.

A temporary local Django server on `127.0.0.1:8766` was exercised through actual
HTTP for empty success, invalid coordinate/limit, query-only coordinates,
malformed JSON, oversize, media type, unsupported methods, OPTIONS and throttle.
JSON/privacy headers and absence of cookies/redirects were checked throughout;
application model counts before/after were identical. The server was stopped.
The local database has zero centers and no ready reference layer, so populated
success and simulated service failure were verified through isolated HTTP
integration tests, not invented local presentation records.

## Teammates and remaining work

No new dependency or Day 3 migration is required. Each teammate must inspect
their own target and ensure the existing UUID migration is applied before use:

```powershell
.\server\.venv\Scripts\python.exe server\manage.py migrate --plan
.\server\.venv\Scripts\python.exe server\manage.py migrate evacuation
.\server\.venv\Scripts\python.exe server\manage.py check
.\server\.venv\Scripts\python.exe -m pytest server -q --reuse-db
```

Run migration commands only against the intended local database; shared/deployed
targets require explicit authorization. Preserve test PostGIS provisioning;
never grant the application role superuser privileges. No seed or import is
needed, and empty eligible data is a valid state. Restart the local server to
load URL/settings changes. The rate override is optional.

The [Stream A handoff](GPS_STREAM_A_NEAREST_CENTER_DAY_3_HANDOFF.md) specifies the
strict envelope, rate/size errors, mandatory warnings, privacy and error-state
mapping. Day 4 still owns the production Flutter adapter/parser, provider
warning-envelope change, purpose copy, live rendering and physical-device
Admin-to-API-to-Flutter verification. Day 5 security completion, deployed
logging/TLS/rate controls and production readiness remain unverified. No work
on those future scopes is claimed by this checkpoint.
