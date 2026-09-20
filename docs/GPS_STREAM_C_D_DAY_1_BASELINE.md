# GPS Streams C/D Day 1 baseline and ownership

**Date:** 20 September 2026. **Assignment:** Team B, Day 1 only.

Stream C and Stream D Day 1 contract, privacy, ownership, and baseline foundation
is complete. The eligibility service, distance query, endpoint, production
mobile adapter, and live integration remain scheduled for later days.

**Verification qualification:** new contract tests pass. Existing database-backed
tests could not run because the isolated local test database lacks PostGIS and
the application role cannot install it. This is a reported baseline blocker,
not a green backend regression claim or a release approval.

## Repository and environment

| Item | Observed baseline |
| --- | --- |
| Starting commit | `57aaecce1c6eea9a8732bc5b41b9c63769f07cd1` |
| Branch | `main`, tracking `origin/main`; no pull/push/commit or branch switch performed |
| Starting working tree | Clean (`git status --short --branch`) |
| Python | 3.13.15, existing `server/.venv` |
| Django | 5.2.17 |
| PostgreSQL | 17.11, reachable; configured database host confirmed loopback |
| Application database PostGIS | `3.6 USE_GEOS=1 USE_PROJ=1 USE_STATS=1`, read-only version query succeeded |
| Test database | Separate default `test_floodsense`; no explicit TEST NAME override |
| Test database PostGIS | Missing; only `plpgsql` present and zero public tables after failed setup |
| Flutter / Dart | Flutter 3.47.2 stable / Dart 3.13.2 |
| Migration state | Zero pending migrations; evacuation `0001_initial`, provenance `0001_initial` and `0002_datasource_metadata_and_permissions`, geography `0001_initial` applied |

No application migration was needed or applied. No schema/model change or new
migration was introduced. No application data, real center records, official
data imports, seeds, superusers, or precise user coordinates were created.
The authorized pytest runs attempted to create/prepare the separate local test
database and left an empty test database without PostGIS. Thus there was test
database setup activity; the developer application database was only read.
No shared/deployed target was modified and no database privileges were changed.

## Current feature baseline and Day 1 deliverables

Existing evacuation Admin create/edit/review/verify/deactivate operations,
permission checks, source approval/release workflow, and Django maintenance
logs were inspected. They are not a resident eligibility service. Center
verification checks source approval/organization/date, but does not implement
the full public-release/identity/coordinate predicate.

The mobile center UI remains provider/fake-backed. `VerifiedCenter` is a public
presentation type, and `NearestCenterProvider` has no production HTTP adapter
or strict wire parser. `server/evacuation/views.py` remains a placeholder; the
root URLconf has no evacuation API include. No eligibility or distance service
exists. `EvacuationCenter` still has no `public_id` field. Its schema was not
changed to make a contract example appear live.

Day 1 adds constants, strict request/response wire serializers, pure contract
tests, the frozen contract, privacy review, this baseline, and focused status
updates. Day 4 **Admin parameter-governance mutation** remains independently
blocked; this task does not resolve it. The final adviser requirement for GPS
also remains unresolved; foreground on-demand GPS is the safe team direction.

Files created:

- `server/evacuation/contracts.py`
- `server/evacuation/serializers.py`
- `server/evacuation/test_day1_nearest_contract.py`
- `server/evacuation/NEAREST_CENTER_CONTRACT.md`
- `docs/GPS_STREAM_C_D_DAY_1_PRIVACY_REVIEW.md`
- `docs/GPS_STREAM_C_D_DAY_1_BASELINE.md`

Status-only edits:

- `docs/GPS_STREAMS_A_B_DEPENDENCY_BLOCKERS.md`
- `docs/GPS_AND_SAFE_IMPROVEMENTS_7_DAY_PLAN.md`

No mobile, geography, Admin workflow, Expert System, scientific parameter,
research dataset, dependency, shared configuration, model, or migration edits.

## Ownership register for this assignment

| Owner | Scope | Coordination boundary |
| --- | --- | --- |
| Team B / Stream C | `server/evacuation/**`, evacuation-focused tests and contract | Sole future evacuation migration author; no geography implementation changes |
| Team B / Stream D | `server/admin_portal/**`, selected `docs/**`, coordinated shared configuration | Day 1 review/evidence only; no Admin behavior changes needed |
| Stream A owner | `mobile/**` | Read-only dependency for Team B; later parser/provider/copy handoff |
| Stream B owner | `server/geography/**` | Read-only dependency for Team B; reuse supported identity contract |
| Integration lead / Stream D | `server/config/urls.py`, `settings.py`, requirements, root/cross-module docs, mobile dependency files | Single coordinated editor; none changed on Day 1 |

This user-assigned Team B allocation applies to this bounded task; the source
plan's three-member scheduling table remains a general team allocation.
Suggested future branches are `gps-evacuation` and `gps-integration`, with
`gps-mobile`/`gps-geography` owned by their respective streams. These are intended
names, not claims that branches or worktrees were created. Changes here remain
uncommitted on the starting branch for review.

Anticipated later shared-file requests:

- Day 3: integration lead adds the evacuation API include in `server/config/urls.py`.
- Before exposure: review request-size/rate controls and any needed
  `server/config/settings.py` changes; never cache request coordinates.
- After endpoint tests pass: Stream A implements the strict wire parser and
  production adapter, updates purpose copy for center lookup, and preserves
  envelope warnings despite the existing list-only provider return type.
- Update cross-module API/integration evidence after the actual implementations.

Merge order:

1. Day 1 contract and privacy evidence.
2. Day 2 reviewed public-UUID migration, eligibility and distance service.
3. Day 3 HTTP endpoint and URL integration.
4. Mobile production-adapter handoff.
5. Day 4 end-to-end center integration.
6. Day 5 privacy/security/audit hardening.
7. Day 6 performance and product polish.
8. Day 7 clean-environment release rehearsal.

## Executed verification

Commands below ran from the repository root except Flutter commands in `mobile`.
The Python prefix is `server\.venv\Scripts\python.exe` (`PY` in this table).
No fallback SQLite database or disabled GIS was used to disguise the blocker.

| Command | Before changes | After Day 1 code |
| --- | --- | --- |
| `git status --short --branch` / `git rev-parse HEAD` | Clean main; commit above | Only the eight task files changed/added |
| `PY --version` / `PY -m django --version` | Versions above | Environment unchanged |
| `PY server\manage.py check` | No issues | No issues |
| `PY server\manage.py makemigrations --check --dry-run` | No changes detected | No changes detected |
| `PY server\manage.py showmigrations evacuation provenance geography` | Relevant migrations applied | No migration files changed |
| Read-only `manage.py shell` version/graph/test-extension queries | PostgreSQL/PostGIS reachable | Zero pending migrations; test DB extension missing confirmed |
| `PY -m pytest server\evacuation -q` | 3 setup errors: PostGIS permission blocker | Repeated with `--reuse-db --tb=line`: 153 passed, 3 setup errors |
| `PY -m pytest server -q --reuse-db` | 30 passed, 227 setup errors | With `--tb=no`: 183 passed, 227 setup errors |
| `PY -m pytest server\evacuation\test_day1_nearest_contract.py -q` | New tests not yet present | 153 passed; no DB access |
| `PY -m ruff check server\evacuation` | Not run before new files | Passed after fixing four new style findings |
| `PY -m ruff format --check` on the three new Python files | Not applicable | All three formatted |
| `flutter --version` | Versions above | No upgrade performed |
| `flutter analyze` | No issues | `flutter analyze --no-pub`: no issues |
| `flutter test --reporter compact` | 164 passed | `flutter test --no-pub --reporter expanded`: 164 passed |
| `git diff --check` | Clean | Passed |

Exact backend setup failure:

```text
psycopg.errors.InsufficientPrivilege: permission denied to create extension "postgis"
HINT: Must be superuser to create this extension.
django.db.utils.ProgrammingError: permission denied to create extension "postgis"
```

The failure occurs during isolated test database setup, before DB-backed test
bodies run. The three evacuation model tests remain unverified locally; no
assertion failure in them was observed. This run cannot confirm all existing
backend behavior remains green. The 153 new contract tests pass without a DB.

Other observed warnings: existing Django 6 URLField scheme deprecation,
`importlib.metadata` deprecation, and missing `server/staticfiles/`. Flutter
reported newer dependency versions outside current constraints; no packages
were upgraded and no tracked mobile files changed. No APK/emulator walkthrough
was performed for this contract-only task; those remain Day 7 work.

The new tests cover required/bounded/finite numeric inputs, strict types and
limits, unknown keys without reflection, nested public schema, canonical UUID,
ten-digit PSGC, ISO date, text/limitations, exact empty/success warning handling,
duplicate identifiers, maximum response count, literal-text handling, and absent
route. They do **not** claim service eligibility, PostGIS distance accuracy,
HTTP error/status/header behavior, or end-to-end persistence proof.

## Teammate steps and remaining dependencies

After pulling this change into an already configured checkout, no additional
dependencies, migrations, seed commands, or data imports are required. Run:

```powershell
server\.venv\Scripts\python.exe -m pytest server\evacuation\test_day1_nearest_contract.py -q
server\.venv\Scripts\python.exe -m ruff check server\evacuation
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe server\manage.py makemigrations --check --dry-run
```

The local database administrator must provision PostGIS in the **isolated test
database** using their approved local procedure, then rerun the evacuation and
full backend suites with `--reuse-db`. Do not grant the application role
superuser just to run tests, use the application database as TEST NAME, or run
a shared/deployed migration. No privileged repair was attempted in this task.

Day 2 requires the reviewed UUID backfill migration, reference-identity
readiness/membership checks, fail-closed per-request eligibility, safe public
field mapping, transient geography distance expression, stable ordering, and
database-backed exclusion/distance/no-write tests. Day 3 must implement the
frozen HTTP error handling and register the route only after service tests pass.

No Day 1 wire/schema/distance/identifier decision remains unfrozen. What remains
unproven or requires later review: actual public content authorization, deployed
logging/TLS/APM controls, pre-exposure abuse limits, supported operational data,
and the independent adviser/parameter-governance decisions. See the privacy
review for precise owners and follow-up days. None authorizes implementation of
Days 2–7 in this task.
