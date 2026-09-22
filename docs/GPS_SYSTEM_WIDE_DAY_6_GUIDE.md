# FloodSense system-wide Day 6 guide and evidence

Date reviewed: 23 September 2026
Scope: Day 6 polish, performance, data readiness, and code quality
Status: complete with documented limitations; this is not Day 7 release evidence

## Safety boundary

Day 6 did not deploy, import official data, alter an Expert System rule, change
the inference method, enable parameter mutation, build a release APK, or add
background location, monitoring, forecasting, routing, occupancy, or alerting.
The current 47-barangay administrative reference remains pending validation and
not City-verified. Evacuation distance remains approximate straight-line
distance, not road distance or route safety.

## GitHub synchronization

The required synchronization check was completed before editing:

- branch and upstream: `main` tracking `origin/main`;
- fetch: `git fetch --prune` succeeded;
- ahead/behind: `0 0`;
- commit before and after the check: `93df891b017c9bc8962116dd9e3731cbdaa868fe`;
- pull: not needed because local and upstream already matched;
- conflicts: none;
- starting worktree: clean.

No push, commit, merge, rebase, stash, reset, clean, or history rewrite was
performed.

## Day 5 readiness audit

| Area | Classification | Repository evidence |
| --- | --- | --- |
| Privacy | Verified complete in application scope | Location is a one-shot foreground request; controller/session cleanup removes it; restart cannot restore it; no background permission is declared; public lookups are select-only and create no location-history event. Infrastructure/APM behavior remains a deployment review. |
| Security | Verified complete in repository scope | Coordinate bounds, body limits, content type, safe public projections, scoped throttling, staff/model permissions, CSRF-protected portal mutations, escaped templates, and generic failure responses have regression coverage. |
| Audit | Verified complete for supported workflows | Genuine source, guidance, and center mutations use transaction-bound Django maintenance events. Failed/unauthorized actions and public GPS/center lookups do not create success or location events. Audit history remains read-only. |
| Expert System separation | Verified complete | GPS selects a location input only. Geographic resolution, center lookup, and guidance cannot change classification. Raw rules and algorithm mutation remain unavailable in the custom portal. |
| Failure hardening | Verified complete | Generation guards reject stale responses; busy flags prevent duplicate requests; retries preserve scenario/confirmed-area state where appropriate; disposal drops delayed work; failures do not expose coordinates or restricted payloads. |

No Day 5 blocking defect was found. Day 6 therefore preserved existing mobile
behavior rather than replacing the established controllers or state model.

## Dashboard and pending-review definitions

The dashboard now uses five constant-count aggregates plus one bounded activity
query. It does not load object text, change payloads, raw rules, geometry,
private source notes, guidance bodies, or derived parameter values.
The authenticated page may also perform Django's bounded permission-cache
lookup on a cold request; the six-query figure below measures the domain
summary service itself.

| Dashboard module | Count shown | “Needs review” definition | Filter target |
| --- | --- | --- | --- |
| Geographic areas | All rows by publication status and area type | Pending-validation rows that also satisfy the supported map-review eligibility policy | `map-data/?status=PENDING_VALIDATION` |
| Data sources | All rows by publication status | `PENDING_VALIDATION` | `sources-content/?status=PENDING_VALIDATION` |
| DSS guidance | All rows by publication status | Publication status is pending validation **or** content workflow is `IN_REVIEW`; one record is counted once | `dss-content/?review_attention=needs_review` |
| Rainfall scenario references | Scenario-option rows by publication status and enabled category | `PENDING_VALIDATION` | `rainfall-references/?status=PENDING_VALIDATION` |
| Evacuation centers | All rows, with publication and verification reported separately | Verification status is `IN_REVIEW` | `evacuation-centers/?verification_status=IN_REVIEW` |

Center verification is not treated as publication, and publication is not
treated as resident eligibility. Quick actions and review links remain hidden
when the staff account lacks the relevant model view permission. Recent
activity now includes safe evacuation-center event labels and remains limited
to five genuine Django maintenance events.

The geographic filter and DSS combined review filter were added so dashboard
counts can link to the same record population they describe. Existing list
views retain deterministic ordering, bounded pagination (25 records, or 50 for
audit history), filter preservation, invalid-filter handling, safe empty
states, and `select_related` use for source/actor relationships. Map review is
bounded to the supported administrative/demonstration policy and uses two
queries independent of record count. Settings remains read-only and uses three
constant queries.

## Mobile polish and request behavior

No Dart change was necessary on Day 6. Current implementation and tests verify:

- scenario, location, confirmation, assessment, guidance, then center order;
- manual selection and map/list alternatives;
- preserved scenario choices after recoverable location, assessment, and
  center failures;
- confirmed area and assessment output remain independent of center failures;
- one-shot GPS, reuse of the temporary coordinate for resolver retry, and no
  automatic retry loop;
- duplicate assessment, resolver, map, and center requests are suppressed;
- stale and post-disposal responses are ignored;
- temporary location is cleared on clear/reset/disposal and is not restored by
  a new controller;
- controllers and map controllers are disposed;
- stable reference polygons are reused across unrelated scenario updates;
- 320 x 640 rendering, large text, long center content, landscape, scrolling,
  semantics, safety labels, and map attribution are covered by widget tests.

This is strong automated accessibility evidence, not a claim of complete WCAG,
screen-reader, or physical-device accessibility certification. No manual
device walkthrough was run during this Day 6 session.

## Performance evidence

### Environment and method

- Local Windows development environment, Django 5.2.17, local PostgreSQL/PostGIS.
- Local application database contained 48 pending geographic areas and no
  evacuation centers at measurement time.
- Latency sample: Django test client, warm process, ten sequential requests,
  `perf_counter`, median and minimum reported. It excludes network/device/UI
  latency and is not a production benchmark.
- Query and payload bounds: `CaptureQueriesContext` tests against isolated
  PostGIS fixtures, including growing center populations.

### Results

| Operation | Queries | Payload | Local latency | Notes |
| --- | ---: | ---: | ---: | --- |
| Barangay `RESOLVED` | 4 SELECTs | 490 bytes | 6.980 ms median; 5.922 ms minimum | Ten local requests; no geometry returned |
| Barangay `OUTSIDE_BACOOR` | 5 SELECTs | 445 bytes | 7.088 ms median; 6.125 ms minimum | Extra bounded city-coverage query |
| Barangay `AMBIGUOUS_BOUNDARY` | 4 SELECTs | under 1 KiB | Not separately latency-sampled | Synthetic overlap regression; ambiguity preserved |
| Barangay `UNAVAILABLE` | 1 SELECT | under 1 KiB | Not separately latency-sampled | Fails closed |
| Invalid coordinate | 0 | under 1 KiB | Not separately latency-sampled | Rejected before database access |
| Nearest centers, honest local empty | 4 SELECTs | 272 bytes | 25.880 ms median; 24.088 ms minimum | Ten local requests; current inventory is empty |
| Nearest centers, 21 eligible synthetic rows, limit 10 | 4 SELECTs | under 16 KiB | Not separately latency-sampled | Query count remains identical to one-row case; response capped at 10 |
| Admin dashboard | 6 SELECTs | Server-rendered HTML | Not latency-sampled | Five aggregates plus one activity query; constant as rows/events grow |
| Admin geographic review | 2 SELECTs | Bounded supported map payload | Not latency-sampled | Aggregate plus projected/select-related rows |
| Admin Settings inventory | 3 SELECTs | Server-rendered HTML | Not latency-sampled | Does not query raw rule tables |

Before this Day 6 integration, the dashboard used five queries for four module
aggregates plus activity and omitted centers. It now uses six queries for five
module aggregates plus activity. This is an intentional one-query increase,
not N+1 behavior. Geography and center endpoints already had bounded,
database-level filtering and stable ordering; no speculative cache or schema
change was introduced. Center eligibility is re-evaluated on every request,
and full-precision PostGIS distance controls order before display rounding.

The geographic model retains its spatial index, and resolver tests verify
database-level spatial predicates. The center model stores decimal coordinates
rather than a spatial point, so the current bounded center query computes
geodesic distance in PostgreSQL but cannot use a point GiST index. This is a
documented future performance consideration only if an authorized, materially
larger inventory demonstrates a need; it is not evidence for a Day 6 schema
change.

## Data-readiness tools

Two explicit-path, report-only commands are available:

```powershell
server\.venv\Scripts\python.exe server\manage.py validate_geographic_dataset `
  C:\explicit\candidate.geojson `
  --identity-field public_id `
  --expected-geometry-type MultiPolygon `
  --expected-crs EPSG:4326 `
  --fail-on-issues

server\.venv\Scripts\python.exe server\manage.py validate_tabular_dataset `
  C:\explicit\candidate-centers.csv `
  --dataset-kind evacuation_centers `
  --metadata C:\explicit\candidate-metadata.json `
  --required-field center_id --required-field name --required-field address `
  --required-field latitude --required-field longitude `
  --identity-field center_id `
  --latitude-field latitude --longitude-field longitude `
  --fail-on-issues
```

Use `--dataset-kind rainfall_reference` and field names from the authorized
DOST delivery when it becomes available. Do not invent a DOST schema. MGB
GeoJSON remains subject to
`research_data/provisional/mgb_flood_susceptibility/README.md`; validation does
not authorize import or activation.

The optional metadata JSON may be a flat object (all present values are
`USER_SUPPLIED`) or an envelope:

```json
{
  "metadata": {
    "dataset_name": "Supplied title",
    "custodian": "Supplied custodian",
    "license": "Supplied license text",
    "public_release_status": "Not approved"
  },
  "classifications": {
    "public_release_status": "PROVISIONAL",
    "license": "RESTRICTED"
  }
}
```

Allowed classifications are `PUBLIC`, `PROVISIONAL`, `RESTRICTED`, and
`UNSPECIFIED`. Restricted metadata values are redacted from the report. File
name, type, byte size, and uppercase SHA-256 are labeled
`VERIFIED_BY_TOOL`; present sidecar values are `USER_SUPPLIED`; embedded
GeoJSON metadata are `DATASET_DECLARED`; absent values are `MISSING`. No
metadata are inferred, and the report contains an explicit empty inferred-field
list. A user assertion is never silently promoted to tool verification.

The validators report fields, row/feature counts, missing-value counts,
duplicate-identifier counts, malformed rows, coordinate validity/range,
geometry types, null/empty/invalid geometry, CRS expectations, coverage,
dates, units, periods, resolution, processing notes, and limitations when
provided. They do not print duplicate identifiers or candidate record values,
and errors expose only the candidate file name rather than its full path.
Inputs are UTF-8, CSV/TSV is capped at 64 MiB, metadata JSON at 1 MiB, and
automated tests use only synthetic temporary files.

Every report states `import_effect`, `approval_effect`, and
`activation_effect` as `NONE` where applicable. The tools have no model import,
no database write path, no approval transition, and no resident-output
activation. No official, provisional, or restricted dataset was executed or
committed during Day 6.

## Blocker classification

| Blocker | Classification | Evidence / owner | Day 7 impact and safest action |
| --- | --- | --- | --- |
| Authorized evacuation-center inventory absent | External data blocker | Current local center count is zero; responsible city/data custodian owns the source | Empty behavior is releasable; populated Admin-to-API-to-device evidence waits for authorized, approved, publicly releasable records |
| Bacoor boundary not City-verified | External data/governance blocker | Derived 47-barangay reference is pending validation | Preserve warning and pending state; obtain custodian validation, do not self-approve |
| DOST rainfall and MGB use authorization/metadata | External data/governance blocker | Research-data READMEs and no authorized delivery | Validate explicit future files only; do not import or activate |
| Parameter mutation approval | Governance blocker, separate from GPS | Day 4 proposal exists; no approval of bounds/roles/workflow | Keep Settings and inference method read-only |
| Production TLS/proxy/APM/log retention/shared throttle | Deployment-environment blocker | Repository tests cannot certify deployed infrastructure | Verify in the explicitly authorized Day 7 target/environment |
| Fresh Admin visual/browser review | Environment evidence blocker | Browser-control runtime failed before tab connection; automated Admin tests passed | Run the documented checklist in a working browser; this does not justify changing server behavior |
| Local resident setup document publication | Environment/content setup dependency | Required legal/onboarding versions are local DB rows, not Git state | Authorized reviewer must publish all required versions before a resident walkthrough |

The former missing endpoint, response-envelope, mobile adapter, migration,
query-bound, and honest-empty blockers are resolved. Real populated output is
not a code blocker but remains an external data/evidence dependency.

## Verification record

| Command/check | Result |
| --- | --- |
| `git fetch --prune` and ahead/behind comparison | Passed; `0 0`, no pull required |
| `server\.venv\Scripts\python.exe server\manage.py makemigrations --check --dry-run` | Passed; no model changes detected |
| `server\.venv\Scripts\python.exe server\manage.py check` | Passed; no issues |
| Final focused Admin/dashboard/map/DSS/data-readiness pytest selection | Passed; 67 tests |
| Final data-readiness pytest selection | Passed; 10 tests |
| `server\.venv\Scripts\python.exe -m pytest server -q --reuse-db` | Passed; 693 tests, 240 warnings, 58.58 seconds |
| Ruff check and format on changed Python files | Passed; no introduced lint errors |
| `flutter pub get` | Passed; existing constraints report 11 newer incompatible versions, no dependency change made |
| `flutter analyze` | Passed; no issues, 13.9 seconds |
| `flutter test` | Passed; 197 tests |
| Manual browser review | Skipped: browser-control runtime failed before connection |
| Physical-device/emulator walkthrough | Not run during Day 6 |

The Django warnings are pre-existing: the Django 6 URL-field transition and a
missing local `staticfiles` output directory during tests. Day 6 introduced no
new warning suppression. Dependency update notices are informational and were
not treated as authorization to change locked versions.

## Day 7 readiness

The repository is **conditionally ready** for a Day 7 release rehearsal. Code,
migrations, backend tests, Flutter analysis/tests, bounded-query checks, and
report-only validation foundations are ready. Day 7 must still begin from its
own clean/disposable-environment procedure and must not be started by this
guide.

Before claiming a fully evidenced release candidate:

1. run the fresh Admin browser checklist in a working browser;
2. publish the locally required legal/onboarding versions through an authorized
   reviewer for resident walkthroughs;
3. use an explicitly authorized Day 7 disposable/deployment target to verify
   TLS, proxy/log retention, shared throttling, static files, migration and
   rollback procedures;
4. keep the honest empty center state unless authorized center data arrive;
5. if authorized data arrive, validate first, obtain governance approval, then
   separately authorize import and run Admin -> API -> device verification.
