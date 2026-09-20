# Streams C/D Days 1–2 manual test guide

Prepared 21 September 2026. This is a repeatable walkthrough of the completed
Day 1 contract/privacy work and Day 2 UUID, service, and Admin changes.
It does not reopen their completion status. Previous evidence: 511 backend tests
passed; the user confirmed the browser checklist passed. Record fresh results
separately rather than copying those results into a new test session.

## 1. Prepare the session

Use the local checkout and local development database. Run PowerShell commands
from the repository root. Keep one terminal for Django and a second for checks.

```powershell
.\server\.venv\Scripts\python.exe server\manage.py check
.\server\.venv\Scripts\python.exe server\manage.py showmigrations evacuation
.\server\.venv\Scripts\python.exe server\manage.py runserver
```

Expected: no system-check issues and both `0001_initial` and
`0002_evacuationcenter_public_id` marked `[X]`. The latter was already confirmed
applied locally. If your checkout/database differs, review the migration steps in
[the Day 2 report](GPS_STREAM_C_D_DAY_2_GUIDE.md) before continuing.

Open `http://127.0.0.1:8000/management/` and sign in with your local staff account.
An authorized account needs the relevant permissions; a hidden action is not
automatically a defect for an account without its permission.

Use existing authorized records for read-only inspection. Do not create or
approve fictional operational centers to obtain a populated result. Checks that
need malformed data, workflow changes, or migration reversal have an isolated
test-database companion in section 7. Never point the running web application at
the pytest database while tests are running.

## 2. Day 1 — manually exercise request validation

In the second terminal, start the Python shell:

```powershell
.\server\.venv\Scripts\python.exe server\manage.py shell -i python
```

At the `>>>` prompt, paste this helper, including the blank line after its body:

```python
from evacuation.serializers import NearestCenterRequestSerializer

def check_request(payload):
    serializer = NearestCenterRequestSerializer(data=payload)
    valid = serializer.is_valid()
    print("ACCEPTED" if valid else "REJECTED")
    print(serializer.validated_data if valid else serializer.errors)

```

Run these expressions one at a time. All coordinates here are synthetic, not
your GPS location. Serializer validation makes no database changes.

| ID | Expression | Expected |
| --- | --- | --- |
| C1 | `check_request({"latitude": 0, "longitude": 0})` | Accepted; default limit is 3 |
| C2 | `check_request({"latitude": -90, "longitude": 180, "limit": 10})` | Accepted; inclusive coordinate boundaries and maximum limit |
| C3 | `check_request({"latitude": 0, "longitude": 0, "limit": 1})` | Accepted; minimum limit |
| C4 | `check_request({"latitude": 0})` | Rejected; longitude required |
| C5 | `check_request({"latitude": "0", "longitude": 0})` | Rejected; numeric strings are not JSON numbers |
| C6 | `check_request({"latitude": True, "longitude": 0})` | Rejected; booleans are not coordinates |
| C7 | `check_request({"latitude": None, "longitude": 0})` | Rejected; null not allowed |
| C8 | `check_request({"latitude": float("nan"), "longitude": 0})` | Rejected; non-finite input |
| C9 | `check_request({"latitude": 0, "longitude": float("inf")})` | Rejected; non-finite input |
| C10 | `check_request({"latitude": 91, "longitude": 0})` | Rejected; latitude outside bounds |
| C11 | `check_request({"latitude": 0, "longitude": -181})` | Rejected; longitude outside bounds |
| C12 | `check_request({"latitude": 0, "longitude": 0, "limit": 0})` | Rejected; limit too small |
| C13 | `check_request({"latitude": 0, "longitude": 0, "limit": 11})` | Rejected; limit too large |
| C14 | `check_request({"latitude": 0, "longitude": 0, "limit": 3.0})` | Rejected; limit must be an integer |
| C15 | `check_request({"latitude": 0, "longitude": 0, "PRIVATE_INPUT_SENTINEL": 1})` | Generic unknown-field error; sentinel absent from error |
| C16 | `check_request([])` | Rejected; an object is required |

These are Python calls to the serializer. NaN/infinity cases are defensive
validation checks, not examples of valid JSON. HTTP parser/status/header tests
belong to Day 3 because there is no nearest-center HTTP endpoint yet.

## 3. Day 1 — manually exercise the response contract

In the same Python shell:

```python
from copy import deepcopy
from evacuation.contracts import CENTER_LIMITATION, DISTANCE_WARNING
from evacuation.contracts import EMPTY_WARNING, EMPTY_DISTANCE_WARNING
from evacuation.serializers import NearestCenterResponseSerializer
from geography.constants import BACOOR_REFERENCE_WARNING, BACOOR_REFERENCE_LIMITATION

def check_response(payload):
    serializer = NearestCenterResponseSerializer(data=payload)
    valid = serializer.is_valid()
    print("ACCEPTED" if valid else "REJECTED")
    print(serializer.data if valid else serializer.errors)

empty = {
    "centers": [],
    "distance_method": "APPROXIMATE_STRAIGHT_LINE",
    "warnings": [EMPTY_WARNING, EMPTY_DISTANCE_WARNING],
}
sample = {
    "centers": [{
        "public_identifier": "a95e27e1-7fb0-4c41-871c-f8e13b2534b8",
        "name": "SYNTHETIC CONTRACT CENTER - NOT A REAL FACILITY",
        "address": "Fictional test address",
        "barangay": {"psgc_code": "0000000000", "name": "Synthetic test area"},
        "latitude": 0,
        "longitude": 0,
        "approximate_distance": 0,
        "distance_unit": "meters",
        "verified_on": "2026-09-19",
        "source_attribution": "Synthetic test organization",
        "limitations": [CENTER_LIMITATION, BACOOR_REFERENCE_WARNING, BACOOR_REFERENCE_LIMITATION],
    }],
    "distance_method": "APPROXIMATE_STRAIGHT_LINE",
    "warnings": [DISTANCE_WARNING],
}
check_response(empty)
check_response(sample)
```

Both must be accepted. These dictionaries exist only in shell memory; accepting
a response shape does not establish eligibility, authorization, or data truth.

Repeat the following pattern, creating a fresh copy before each change:

```python
changed = deepcopy(sample)
changed["centers"][0]["id"] = 123
check_response(changed)
```

Expected: rejected. Additional single-change cases:

| ID | Change after `changed = deepcopy(sample)` | Expected |
| --- | --- | --- |
| C17 | `changed["centers"][0]["public_identifier"] = "123"` | Rejected; raw row ID is not the public UUID |
| C18 | `changed["centers"][0]["barangay"]["psgc_code"] = "123"` | Rejected; code requires ten ASCII digits |
| C19 | `changed["centers"][0]["verified_on"] = "2026-02-30"` | Rejected; invalid calendar date |
| C20 | `changed["centers"][0]["distance_unit"] = "km"` | Rejected; wire unit is meters |
| C21 | `changed["centers"][0]["approximate_distance"] = -1` | Rejected; negative distance |
| C22 | `changed["centers"][0]["limitations"] = []` | Rejected; mandatory limitations missing |
| C23 | `changed["warnings"] = []` | Rejected; mandatory warning missing |
| C24 | `changed["centers"].append(deepcopy(changed["centers"][0]))` | Rejected; duplicate UUID |
| C25 | `changed["centers"][0]["notes"] = "PRIVATE TEST NOTE"` | Rejected; private field not in public schema |

Use `check_response(changed)` after every change. Missing fields and extra
fields at other nesting levels are covered exhaustively by the contract suite.

## 4. Day 2 — inspect UUID and internal service behavior

### UUID integrity, without changing rows

In the Python shell:

```python
from django.db.models import Count
from evacuation.models import EvacuationCenter

print("Centers:", EvacuationCenter.objects.count())
print("Missing UUIDs:", EvacuationCenter.objects.filter(public_id__isnull=True).count())
print("Duplicate UUID groups:", EvacuationCenter.objects.values("public_id").annotate(total=Count("pk")).filter(total__gt=1).count())
```

Expected: zero missing UUIDs and zero duplicate groups. An empty database is
valid but does not demonstrate legacy backfill; use the migration suite for that.

### Reference readiness and a read-only lookup

```python
from evacuation.services import ready_reference_barangays, find_nearest_eligible_centers

print("Ready reference identities:", len(ready_reference_barangays()))
result = find_nearest_eligible_centers(latitude=0, longitude=0, limit=3)
check_response(result)
print("Returned centers:", len(result["centers"]))
```

Expected: readiness returns either 47 identities or zero when the controlled
reference gate fails. The lookup returns a valid envelope with at most three
centers. `(0, 0)` is a synthetic test origin outside Bacoor; the service permits
any valid WGS 84 origin and still filters centers by the controlled reference.
Distances from this origin are not a local travel demonstration.

An empty result is correct when eligible records or reference readiness are
absent. It must contain the two exact empty warnings from section 3. Do not
approve records or import boundaries just to force a populated result.

If results exist, inspect the UUID, source attribution, date, barangay identity,
meter distances, and mandatory limitations. Only the public fields shown in
`sample` may appear. Center coordinates are expected; a user-coordinate field
or private contact/notes/capacity field is not.

Try limits 1 and 10 by changing the `limit` argument. Counts must never exceed
the chosen limit. These smoke checks cannot prove tie ordering or refill after
excluded rows unless the dataset contains those cases; use section 7 for them.

### Read-only SQL smoke check

Paste this block, including the blank line after the `with` body:

```python
from django.db import connection
from django.test.utils import CaptureQueriesContext

with CaptureQueriesContext(connection) as queries:
    first = find_nearest_eligible_centers(latitude=0, longitude=0, limit=3)
    second = find_nearest_eligible_centers(latitude=0, longitude=0, limit=3)

print("Same result:", first == second)
print("SELECT only:", all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries))
print("Query count:", len(queries))
```

Expected: both booleans are `True` if records are unchanged between calls.
A ready reference layer takes eight SELECTs for two calls; unavailable reference
data can stop earlier. Do not print captured SQL or replace the synthetic origin
with personal GPS coordinates. Row preservation, audit/session preservation and
absence of deliberate service logging have stronger tests in section 7.

Type `exit()` to return to PowerShell. No request was sent through HTTP in these
shell checks, and they do not establish deployed logging/TLS behavior.

## 5. Day 2 — Admin browser walkthrough

Begin at `http://127.0.0.1:8000/management/evacuation-centers/`.
Use links from existing records for detail/edit/transition pages; do not invent
record IDs. If a record or role needed for a check is unavailable, mark that
manual case **Not exercised** and use the isolated companion test.

| ID | Action | Expected |
| --- | --- | --- |
| D1 | Read the list-page notice and “Verification and resident use” section | Verification does not imply opening, safety, space or live capacity; source/publication/identity gates are explained |
| D2 | Search for `SYNTHETIC-NO-MATCH-20260921`, then apply filters | Honest filtered-empty message; clear-filters link; no claim that no facilities exist |
| D3 | Use Clear | Filters reset and existing list returns |
| D4 | Open `?verification_status=INVALID` on the list URL | Visible filter error and “Filters were not applied”; no silent acceptance |
| D5 | Open a permitted center detail | Public identifier shown as text; source approval and release status shown separately; UUID is not an authorization token |
| D6 | Refresh the detail page and revisit it | Public identifier remains identical |
| D7 | Open “Create center draft” and an available “Edit draft” page | No editable public-UUID control; proper labels and help text |
| D8 | On the create form, click “Save draft” with required fields empty | Linked error summary and inline errors; no successful record creation |
| D9 | Follow an error-summary link, then click the matching label | Focus reaches the relevant input; errors remain understandable |
| D10 | Enter latitude 91 and longitude 181 on the still-invalid create form and submit | Coordinate errors shown; no successful save; use Cancel afterward |
| D11 | Enter `(0, 0)` without saving and inspect preview | Marker represents the field coordinates when the library is available; no boundary or route-safety guarantee |
| D12 | Open an available workflow action, read it, then Cancel | Action/record clearly identified; safety copy and confirmation checkbox present; cancellation leaves status unchanged |
| D13 | If a verification form is available, inspect its fields without confirming | Verification date and optional documented capacity have labels/help; capacity is not live occupancy |
| D14 | Inspect a long existing name/address/UUID/source/limitation | Detail text wraps; list address may intentionally truncate; controls stay reachable |
| D15 | Open `/management/settings/` | Read-only foundation and pending governance explanation; no parameter edit/save workflow |
| D16 | Open `/management/rainfall-references/` and an available detail | Scenario-input wording; no live rainfall claim or create/edit controls |
| D17 | Open `/management/map-data/` | Administrative boundaries distinguished from susceptibility/current conditions; layer labels and attribution remain clear |
| D18 | Use dashboard and navigation links | Correct pages open; current page and headings remain understandable |

Authorized Admin detail pages may show contacts, capacity and internal notes.
Their presence there is not a public-service leak. Their absence is required in
the service response, which has a different purpose and field policy.

Do not submit approval/deactivation transitions on genuine records merely to
test UUID stability. The isolated migration/workflow suite covers edits and all
transitions. If a dedicated browser test environment already has labeled
synthetic records, record their UUID before and after its approved test workflow.

## 6. Stream D — accessibility, permissions and fallbacks

Repeat the applicable pages from section 5, including an error form and a detail
page. Record browser/version, Windows version, viewport and screen reader used.

| ID | Action | Expected |
| --- | --- | --- |
| A1 | Inspect normal desktop width, then a 320px responsive viewport in DevTools | No overlapping/clipped text or inaccessible controls; table adapts within its container |
| A2 | Use Tab/Shift+Tab from a fresh page load | Visible focus, sensible order, no keyboard trap |
| A3 | Activate “Skip to content” | Focus moves to the main content |
| A4 | At narrow width, tab with navigation closed, then open it | Closed drawer links do not receive hidden focus; opened links are reachable |
| A5 | Activate links/buttons/checkboxes with their normal keyboard controls | Same usable behavior as pointer interaction |
| A6 | Use Windows Narrator or your screen reader on headings, fields and errors | Meaningful names/labels; headings and error descriptions understandable |
| A7 | Disable JavaScript in browser DevTools, reload at 320px and desktop | Navigation remains visible/usable; sign-out and server forms still work |
| A8 | Inspect center map with JavaScript disabled | Text fallback and recorded coordinates remain available; no false map-verification claim |
| A9 | Re-enable JavaScript, reload | Normal navigation and map behavior return, subject to external map availability |
| A10 | Open a protected management URL in a signed-out/private window | Redirect to login; no protected record details exposed |
| A11 | With an existing nonstaff or staff-without-permission test session, visit center URLs directly | Access denied; hiding navigation alone is insufficient |
| A12 | Read statuses without relying on badge colors | State is also expressed in text |

An unavailable external basemap alone is not proof the service failed. Confirm
the relevant fallback and coordinates remain usable. Missing test accounts or
records mean a case is unexercised, not passed. Do not alter real account roles
to obtain a test session.

## 7. Deterministic backend companion tests

These commands run **automated tests you can launch and inspect individually**;
they are not claimed as manual browser checks. They exercise synthetic records
in `test_floodsense`, preserve the application database, and cover conditions
that normal Admin forms deliberately prevent you from creating.

Run them sequentially in PowerShell with `--reuse-db` to retain PostGIS:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server\evacuation\test_day1_nearest_contract.py -v --reuse-db
.\server\.venv\Scripts\python.exe -m pytest server\evacuation\test_day2_public_id_migration.py -v --reuse-db
.\server\.venv\Scripts\python.exe -m pytest server\evacuation\test_day2_nearest_service.py -v --reuse-db
.\server\.venv\Scripts\python.exe -m pytest server\admin_portal\test_gps_day2_admin.py -v --reuse-db
```

Expected current counts: 153 contract, 4 UUID/migration, 84 service and 13 focused
Admin tests. `-v` shows every case name so you can associate it with a feature.

| Feature | Cases to inspect in verbose results |
| --- | --- |
| UUID backfill/reversal | Distinct UUIDv4 values; legacy fields/source/rows preserved; reverse only in test database |
| UUID lifetime | Defaults, unique/non-null constraint, ordinary edits and every verification transition |
| Reference readiness | Missing/duplicate source, City, count, identity and geometry damage fail closed; unrelated rows ignored |
| Resident eligibility | Draft/review/inactive, publication/source states, public-release flag, unsupported area, unsafe text/date/coordinates excluded |
| Malformed legacy coordinates | Stored NaN in either coordinate excluded; ORM validation stays intact |
| Current eligibility | Source/center changes affect the next lookup; no stale approval cache |
| Distance | Zero distance; latitude/longitude order; known spheroidal pairs within 0.2m |
| Ordering | Full-precision nearest first; UUID order only for exact ties; rounded ties retain original order |
| Limits | Default 3, min 1, max 10; excluded closer rows do not consume available slots |
| Mapping | Exact public fields; required warnings and ordered/deduplicated limitations; private sentinels excluded |
| Failure | Invalid input fails before SQL; database failure propagates rather than becoming empty success |
| Privacy | SELECT-only queries; unchanged center/source/area/session/audit state; no deliberate evacuation logs |
| Query behavior | Four SELECTs for a ready layer, no per-center related query growth; bound input values |
| Admin regressions | Protected routes, UUID text-only display, escaped long content, linked errors, safety copy and read-only parameters |

For example, to isolate the known-distance cases:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server\evacuation\test_day2_nearest_service.py -v --reuse-db -k wgs84_spheroid_known_equatorial_pairs
```

Expected: two passed. Do not use migration reversal commands, corrupt reference
geometry, or bypass validation in the development application database to repeat
these synthetic scenarios manually.

## 8. Day 1 privacy review and scope boundaries

Read [the privacy review](GPS_STREAM_C_D_DAY_1_PRIVACY_REVIEW.md) alongside the
service results. Confirm the distinction between facility coordinates, temporary
lookup input, and Admin maintenance audit entries. A center edit may create an
audit entry; a nearest-center service lookup must not.

Day 1's baseline and contract describe what existed at that checkpoint; their
historical missing-PostGIS/service statements are superseded by the Day 2 report.
Do not modify production TLS, logging or proxy settings to check off this guide.
Deployment privacy, actual HTTP failure logging and release-device behavior
remain separate later-day evidence.

There is no public nearest-center endpoint, registered route, production mobile
adapter, or live center integration in Days 1–2. Do not expect successful Postman
requests or real mobile nearest-center results yet. Road routing, live opening,
occupancy, automatic alerts and background GPS are not acceptance features.

## 9. Record the session

Copy this table into your own test notes; do not mark new cases passed in advance.
Use synthetic or redacted screenshots and never include passwords or personal GPS.

| Case ID | Browser/version or command | Viewport/role | Actual result | Pass / Fail / Not exercised |
| --- | --- | --- | --- | --- |
| C1 | | | | |
| D1 | | | | |
| A1 | | | | |

For a defect, include its case ID, exact steps, expected/actual behavior and a
redacted screenshot or error. Stop dependent checks when setup fails. Completing
this walkthrough confirms only the tested local Days 1–2 scope, not later-day
HTTP/mobile/deployment integration.
