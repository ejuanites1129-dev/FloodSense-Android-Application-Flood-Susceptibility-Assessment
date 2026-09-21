# GPS Streams C and D — Day 4 implementation evidence

**Evidence date:** 21 September 2026

**Repository commit inspected:** `831130a88fa244c4b7266d64f7060d1539492184`

**Scope:** Stream C nearest-center eligibility/accuracy and Stream D evacuation-center Admin/provenance only

This is implementation and automated-test evidence, not approval of GPS, a
facility dataset, an evacuation instruction, or production deployment. All
records used by tests are visibly synthetic and isolated from the application
database.

## Git and readiness gate

`main` tracked `origin/main` at the same commit after `git fetch --prune`
(`0` ahead, `0` behind). No pull was needed. The working tree already contained
five reviewed readiness corrections, which were preserved. No merge conflict
was present.

Days 1–3 prerequisites were present: the POST-only public endpoint, strict
request/response serializers, current-state eligibility service, PostGIS
distance ordering, safe empty envelope, no-write behavior, protected Admin
routes, center workflow, source presentation, and Django `LogEntry` audit
integration. The application migration graph was already current through
`evacuation.0002_evacuationcenter_public_id`; Day 4 required no schema change.

## Stream C result

The existing service already re-evaluated center, source, reference-area, public
field, coordinate, verification-date, and publication gates on every call. Day
4 adds explicit regressions proving a previously eligible row disappears on the
next request when any relevant center/source state is revoked, and a newly
eligible row appears on the next request without a restart.

Missing source and missing coordinates are structurally impossible in the
current schema (`null=False`, `blank=False`); malformed legacy coordinate values
still fail closed in the service. The model has no separate live availability,
rejected, archived, or superseded flags: `VERIFIED` is the maintained eligible
state, `INACTIVE` is its static deactivation state, and restricted/retired
publication values represent the actual non-public terminal states. No new
workflow vocabulary was invented.

The tests also cover synthetic points inside, just outside, and adjacent to the
test municipal geometry; stable repeated ordering; explicit meters; and two
different full-precision distances that serialize to the same one-decimal
value. Ordering remains database-calculated spheroidal WGS 84 distance followed
by public UUID, with rounding only after selection.

The frozen API allowlist, one-through-ten limit, 1,024-byte request bound,
finite coordinate checks, JSON-only behavior, normalized errors, safe empty
result, and no-write/no-session/no-audit behavior remain unchanged. The contract
documentation now states that straight-line distance does not account for road
closures, flood depth, traffic, terrain, access restrictions, or bridge
conditions; nearest is not necessarily safest; records have no live occupancy;
and users should follow official local instructions.

## Stream D result

- Draft forms reject unsupported control characters and retain existing model
  coordinate/source validation. The geographic-area help text explains that a
  missing or unsupported association prevents resident eligibility without
  pretending that a draft association verifies a facility.
- Exact normalized-name and exact-coordinate matches produce deterministic
  review warnings. A reviewer must acknowledge the warning to save a separate
  draft. No fuzzy threshold, distance tolerance, merge, deletion, or automatic
  duplicate conclusion was added.
- Verification dates in the future are rejected both by the HTTP form and the
  workflow service. The existing model validation continues to recheck approved
  source state and responsible organization inside the locked transition.
- Confirmation pages identify the record, action, current/resulting state, and
  resident-visibility effect. Existing backend permission and stale-state
  checks remain authoritative.
- Edit audit events list only safe changed field names, never submitted values.
  Create and workflow actions continue to create genuine Django audit events;
  public lookups remain SELECT-only and create none.
- List/detail/form pages distinguish center verification/publication from source
  approval/release permission and show source organization, custodian, version,
  permitted use, limitations, and processing notes to authorized staff.
- The map preview now has a focusable region, persistent OpenStreetMap
  attribution, an external live status describing marker state, range-aware
  updates, and explicit map-load/JavaScript-disabled alternatives. Labeled
  coordinate fields remain the authoritative non-map interface.

## Performance evidence

Environment: local Windows development environment, Django test client,
PostgreSQL/PostGIS isolated pytest database, 21 synthetic eligible candidates,
maximum response limit `10`.

| Measurement | Before | Day 4 result | Method |
| --- | ---: | ---: | --- |
| SQL queries per populated HTTP request | 4 | 4 | `CaptureQueriesContext`; one and 21 candidate fixtures |
| Maximum-limit result count | 10 | 10 | public endpoint integration test |
| Maximum-limit payload in the measured fixture | not previously recorded exactly | 7,051 bytes | `len(response.content)` during the isolated test |
| Candidate-query growth | constant | constant | query count compared before/after adding 20 rows |

The four queries validate the controlled source, City geometry, all current
barangay identities/geometries, then select and order center projections. The
center query performs eligibility filtering and distance ordering in PostgreSQL
and projects only public-response inputs; it does not load contact, capacity,
notes, permitted use, reviewer, audit, or full source objects. No N+1 query was
observed.

Read-only `pg_indexes` inspection found the primary-key index, unique public UUID
index, and foreign-key indexes for `geographic_area_id` and `source_id`. There
is no stored center point geometry, so no spatial point index exists. No new
index was justified by this bounded synthetic evidence; representative latency
and `EXPLAIN (ANALYZE, BUFFERS)` remain Day 6/deployment-environment work.

## Cross-stream compatibility

The endpoint path, POST method, `latitude`/`longitude`/optional `limit` request,
meters, safe center fields, PSGC identity, empty envelope, and server ordering
match the frozen contract and geography's `public_psgc_code()` identity.
Geography Day 4 compatibility tests remain read-only dependencies.

At the original Day 4 C/D checkpoint, the mobile production handoff was still
incomplete. A 22 September Stream A follow-up now provides the production HTTP
adapter, strict complete-envelope parser, mandatory warning presentation, typed
failure mapping, and default-app wiring without duplicating server eligibility,
ordering, or limiting behavior.

## Verification record

| Command | Result |
| --- | --- |
| `server\.venv\Scripts\python.exe -m ruff check server\admin_portal server\evacuation` | Passed; no issues |
| `server\.venv\Scripts\python.exe server\manage.py makemigrations --check --dry-run` | Passed; no changes detected |
| `server\.venv\Scripts\python.exe server\manage.py check` | Passed; no issues |
| `server\.venv\Scripts\python.exe -m pytest server\evacuation server\admin_portal -q --reuse-db` | Passed; 469 tests, 150 warnings |
| `server\.venv\Scripts\python.exe -m pytest server\geography\test_day4_center_integration.py server\geography\test_day3_barangay_robustness.py -q --reuse-db` | Passed; 22 tests, 3 warnings |
| `server\.venv\Scripts\python.exe -m pytest server -q --reuse-db` | Passed; 634 tests, 206 warnings |
| `flutter analyze` from `mobile/` | Passed; no issues |
| `flutter test` from `mobile/` | Passed; 167 tests |

Stream A follow-up verification on 22 September: `flutter analyze` passed and
the expanded full Flutter suite passed all 175 tests. Live localhost and LAN
requests returned the exact honest-empty envelope, and the Android 14 build
launched on the connected physical device. Populated acceptance awaits
authorized center data.

The warnings are the existing Django 6 URL-scheme deprecation and missing local
`staticfiles` directory notice; this work introduced no failing test or new
warning category.

## Evidence limits

The in-app browser runtime reported no available browser. A fresh visual pass
of list/create/edit/detail/confirmation pages, keyboard order, 320 px layout,
JavaScript-disabled behavior, and live OpenLayers failure behavior was therefore
not performed. Server-rendered accessibility/fallback assertions and static
code review pass, but they are not a substitute for visual browser evidence.

No center import, official/provisional data mutation, shared database migration,
production deployment, geography change, live-capacity feature, route
calculation, monitoring, susceptibility change, or Expert System change was
made. The later Stream A follow-up changed only the mobile adapter, response
model/controller/UI wiring, disclosure copy, tests, and status documentation.
