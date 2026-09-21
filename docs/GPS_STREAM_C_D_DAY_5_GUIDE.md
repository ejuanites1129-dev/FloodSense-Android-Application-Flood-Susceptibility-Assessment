# GPS Streams C and D — Day 5 privacy and security evidence

**Evidence date:** 22 September 2026

**Repository commit inspected before changes:** `628d37e0a70e5db6babb928e3242757637c3fdea`

**Scope:** Stream C nearest-center backend and Stream D custom Admin/security integration only

This document is repository and automated-test evidence. It is not approval of
an evacuation-center dataset, scientific rules, production infrastructure, or
deployment. Test records and coordinates are synthetic and isolated from the
application database.

## Git synchronization and readiness

The clean `main` worktree tracked `origin/main`. `git fetch --prune` succeeded;
the branches were `0` ahead and `0` behind, so no pull was needed. No merge
conflicts existed. Day 5 made no commit and no push.

The Day 4 gate was satisfied by current code and tests: eligibility is evaluated
per request; all center, source, reference-layer, coordinate, publication and
active-state gates fail closed; PostGIS performs full-precision ordering with a
stable UUID tie-break; rounding is display-only; output and input limits are
bounded; public projection is allowlisted; empty results are truthful; and the
endpoint is read-only. Admin validation, provenance, duplicate review without
merging, transition permissions and confirmation, safe audit summaries, and
accessible non-map alternatives remain present. No official or invented center
record was added.

Three small Day 5 defects were corrected:

- JSON object members are now unique, including nested objects. Duplicate keys
  return the frozen generic malformed-JSON response instead of last-value-wins.
- A center or source deleted between confirmation and the locked transition now
  returns `404` instead of an uncaught `DoesNotExist` error.
- Production-mode startup now rejects the documented development fallback
  secret. Local development still uses its existing default when debug is true.

No model or migration changed.

## Dependency-blocker classification

| Blocker | Classification | Evidence and Day 5 effect | Owner / safest next action |
| --- | --- | --- | --- |
| Stream A production response-envelope adapter | Resolved | Current dependency report records the adapter, strict parser, warning presentation and 175 Flutter tests. No Stream C/D change needed. | Stream A; retain frozen contract. |
| Fresh Admin desktop/320px, keyboard and no-script QA | Still active; environment evidence blocker | Automated escaping, fallback and accessibility regressions pass, but browser discovery returned no available browser. It does not block backend hardening, but visual/manual acceptance remains open. | Stream D/manual tester; repeat the documented browser checklist. |
| Authorized center inventory | External data/governance blocker | Honest empty behavior is verified. No approved, publicly releasable, non-demonstration center rows were supplied. Populated real-data acceptance and representative performance cannot be claimed. | Authorized data custodian and Stream D; enter reviewed data through the governed workflow. |
| Populated Admin → API → physical-device evidence | Still active; cross-stream integration blocker | Synthetic populated HTTP tests pass, but no real populated device test is possible without authorized records. | Streams A/C/D after authorized data exists. |
| Deployed TLS, reverse-proxy, APM/log retention and shared throttling | Still active; deployment/environment blocker | Production settings and Django deployment checks pass under an isolated safe configuration. Repository inspection cannot certify external infrastructure or retention. | Deployment owner; verify target configuration and retained logs without exposing values. |
| Per-target `evacuation.0002` rollout | Still active per target | Migration exists and the local graph was current before Day 5. Git cannot synchronize database state. | Each environment owner; inspect the migration plan before applying to the intended target. |
| Governed parameter mutation workflow | Still active; governance blocker; no direct GPS impact | Current Settings surface is read-only and raw rules are absent. Scientific definitions, bounds, roles and workflow remain unapproved. | Research/governance team; do not enable mutation until approved. |

## Resident-coordinate data-flow audit

Temporary resident coordinates are distinct from maintained center coordinates,
boundary geometry, and isolated synthetic test coordinates.

| Stage | Resident coordinate and purpose | Persistence/log/audit result | Evidence |
| --- | --- | --- | --- |
| Public request | Present only in the bounded JSON body for a one-shot lookup. | Not placed in the URL, cookie, session or file. | HTTP boundary tests reject query/header/cookie substitution and cap actual bytes at 1,024. |
| Parser | Present in an in-memory byte buffer, then decoded JSON. | Buffer is request-scoped; malformed and duplicate input returns a generic error without fragments. | `LimitedJSONParser` and malformed/duplicate/size tests. |
| Serializer | Present while finite numeric type/range and optional limit are validated. | No model serializer and no `save()` path exists. | Request serializer validation matrix. |
| View | Passed as validated arguments to the nearest-center service. | No authentication session, audit event, inference call or request-body logger. | Public view plus no-session/no-write tests. |
| Eligibility/distance service | Used as a transient PostGIS point expression to order eligible canonical centers. | Not assigned to a model or cache; queries are `SELECT` only. | Query capture and whole-database before/after snapshots. |
| Database | Exists as query parameters/expression during execution. | No resident-coordinate/location-history model or write query exists. Canonical center coordinates and boundary geometry remain legitimate maintained fields. | Model inspection and `CaptureQueriesContext`. |
| Response | Exact resident coordinates are not included. Canonical eligible-center coordinates may be returned by the frozen allowlist. | Response is `no-store`; no cookie is set. | Exact public response-field assertions and header tests. |
| Exceptions | A service exception is replaced by a stable generic 500. | No exception object, SQL, path, private field or coordinate is logged by Stream C/D code or reflected. | Database/runtime/serializer failure tests with sentinels and captured logs. |
| Middleware/request logging | Standard middleware sees request metadata; no custom request-body middleware or logging configuration was found. | Application code does not retain bodies. Default server status/path logging may exist; deployed proxy/APM behavior is not repository-certifiable. | Repository-wide logging/middleware search; deployment blocker retained. |
| Throttle cache | Only remote-address-derived scope key and request timestamps are stored. | No body or coordinate enters the cache. Process-local cache is not production shared-rate certification. | Wrapped cache-write test. |
| Audit/Admin history | Public lookup never invokes an audit service. | No `LogEntry`, session or other row is created. | All-model snapshots and audit-count assertions. |
| Analytics/telemetry/error monitoring | No integration or event path was found in the repository. | No repository-owned coordinate analytics retention exists; external deployed agents remain unverified. | Repository-wide search. |
| Test output | Coordinates are isolated synthetic values used to assert redaction and geometry behavior. | No application data is written; pytest uses the PostGIS test database. | Full backend suite with `--reuse-db`. |

## Public API security and privacy

The POST-only JSON endpoint remains public and CSRF-independent without weakening
session CSRF middleware for the Admin portal. It rejects missing/null/string,
boolean, array/object, non-finite and out-of-range coordinates; invalid or
excessive limits; unknown and duplicate fields; malformed/empty JSON; unsupported
media and methods; oversized actual or declared bodies; and excess repeated
requests. The result limit is an integer from 1 through 10 and service output is
validated before use.

Success, empty, invalid, maximum-limit and failure paths remain database
read-only. The endpoint does not create assessments, sessions, users, audit
history, analytics, source/center state or guidance state, and it does not call
susceptibility inference. The exact resident response excludes contact details,
capacity, internal notes, full provenance/licensing/reviewer information, staff
identity, audit metadata and raw verification evidence.

Public errors use stable JSON shapes. Raw parser messages, exceptions, SQL,
database/table/model names, filesystem paths, settings, geometry, private
contact data and request coordinates are not returned. Missing eligible data is
a successful honest-empty envelope, not an invented center or classification.

## Admin security, content rendering and audit integrity

All relevant `/management/` routes retain staff authentication and explicit
model/custom permissions. Anonymous users redirect to the portal login;
authenticated non-staff and staff without permission are denied. View permission
does not grant edit, verify, approve, publish, restrict, deactivate or archive
capability. Route action vocabulary, current state, expected state, source
eligibility and permission are rechecked server-side. Technical Django Admin
remains separate at `/admin/`.

Model forms use explicit field allowlists. Crafted center submissions cannot set
verification date/status, capacity, public UUID or timestamps; source forms
cannot set review/publication state, reviewer or timestamps; guidance forms
cannot set workflow/enabled state; and no form exposes rules, priorities or
algorithm controls. Session-authenticated POSTs require CSRF. GET renders a
confirmation or form and performs no mutation. The public lookup's narrowly
public DRF view does not disable CSRF globally.

Templates retain Django autoescaping. No reviewed template or script uses
`safe`, `mark_safe`, `innerHTML`, `outerHTML` or raw HTML insertion for these
values. Map data uses safe JSON script serialization and DOM text operations.
Existing tests cover script-like center/source/guidance and map content; staff
form errors and audit summaries remain escaped.

Create/edit and center/source/guidance transition code writes the record and its
`LogEntry` within one transaction. Audit messages contain actor, record identity,
timestamp, action and safe workflow/changed-field summaries—not request bodies,
resident coordinates, submitted values, private contacts, restricted payloads,
credentials or stack traces. Audit failure tests prove rollback. Invalid,
stale, unauthorized, repeated and deleted-record operations do not create false
success events. The custom audit surface is filtered and GET-only; it has no
ordinary edit/delete route.

## Expert System separation

Nearest-center modules do not import or invoke assessment inference. Center
eligibility, ordering, empty output, errors, approval/publication and center
source association remain separate from classification. Guidance mutations
change content workflow/selection only; the inference service reads its own
versioned rules, conditions, scenario options, area facts and susceptibility
levels. The custom portal provides only the approved read-only settings summary;
it does not expose raw rules, priorities, method or algorithm mutation.

The complete suite retains tests that return `INSUFFICIENT_DATA` when facts,
eligible rules or supported knowledge are missing. No rules, thresholds,
classifications or approvals were invented for unsupported barangays.

## Production configuration review

`DEBUG`, hosts, database credentials and secret key remain environment-loaded.
Production mode now refuses the development fallback secret. Production enables
proxy HTTPS recognition, configurable HTTPS redirect, secure session/CSRF
cookies and HSTS. HTTP-only session cookies, Lax SameSite cookies, MIME sniffing
protection and frame denial are explicit. Static files use a manifest-backed
WhiteNoise storage in production. A safe isolated production-mode deployment
check passed with temporary non-production values; this does not certify target
proxy headers, trusted origins, TLS, secret rotation, database access, APM or
log retention.

## Verification record

| Command/check | Result |
| --- | --- |
| `server\.venv\Scripts\python.exe -m pytest server/evacuation/test_day3_nearest_api.py server/admin_portal/test_gps_day5_security.py -q --reuse-db` | Passed: 93 tests, 78 warnings. |
| `server\.venv\Scripts\python.exe -m pytest server -q --reuse-db` | Passed: 642 tests, 212 warnings. |
| `server\.venv\Scripts\python.exe server\manage.py makemigrations --check --dry-run` | Passed: no changes detected. |
| `server\.venv\Scripts\python.exe server\manage.py check` | Passed: no issues. |
| `server\.venv\Scripts\python.exe server\manage.py check --deploy` with isolated production-like environment values | Passed: no issues. No real secret or target environment was used. |
| In-app browser discovery | Skipped: the browser runtime reported no available browser (`[]`), so no fresh visual/manual claim is made. |

The warnings are existing Django URL-field future-default and absent collected
`staticfiles/` development warnings. They are not failures introduced by Day 5.
No application migration, data import, deployment, mobile change, official-data
change or Day 6/7 work occurred.

## Day 6 gate

Repository-level Day 5 automated hardening is complete. Day 6 code-quality and
representative performance work may begin without weakening the separate
external gates. Fresh Admin browser QA, authorized center data, populated
device evidence, per-target migration verification, and deployed TLS/proxy/APM/
logging/shared-throttle review remain required before release certification.
The governed parameter-mutation workflow remains blocked and must stay disabled.
