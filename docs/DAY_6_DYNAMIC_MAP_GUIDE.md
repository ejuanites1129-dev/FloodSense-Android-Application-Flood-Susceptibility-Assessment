# FloodSense Day 6: Dynamic Demonstration Map

**Official research title:**  
**FLOODSENSE: AN ANDROID-BASED EXPERT SYSTEM FOR FLOOD SUSCEPTIBILITY
ASSESSMENT AND PRE-EVENT PREPAREDNESS IN BACOOR CITY**

> **Current governance notice (17 September 2026):** The Django Admin editing
> steps in this historical demonstration guide are developer-only verification
> procedures. They are not the intended permissions of the custom Admin web
> portal. Ordinary administrators must not edit raw Expert System rules, rule
> conditions, or the inference algorithm. FloodSense remains scenario-based and
> does not add background monitoring or timers. Follow
> `TA_CONSULTATION_SYSTEM_DECISIONS.md` and
> `ADMIN_WEB_7_DAY_IMPLEMENTATION_PLAN.md` when implementing current behavior.

## Day 6 outcome

Day 6 connects the Day 5 assessment screen to a functional interactive map.
Flutter renders Polygon and MultiPolygon geometry supplied by Django, fits the
camera to those records, asks the backend to evaluate every eligible area for
the selected hypothetical rainfall scenario, and uses only the returned
susceptibility colors. A map tap creates an in-memory pin and asks Django and
PostGIS which eligible fictional zone covers that coordinate.

The complete flow is:

```text
Django Admin / seed_demo
        |
        v
PostgreSQL + PostGIS geometry, facts, rules, levels, and guidance
        |
        +--> GeoJSON areas --> Flutter polygons
        |
        +--> batch Expert System evaluation --> polygon labels and colors
        |
Flutter temporary pin --> PostGIS covers query --> selected demo zone
        |
        v
single-area Expert System assessment --> explanation --> DSS guidance
```

All supplied polygons, ranks, rules, results, and guidance are demonstration
material. They are not official Bacoor boundaries, classifications, live
rainfall observations, forecasts, warnings, evacuation orders, or route-safety
statements.

## Current verified status

The Day 5 and Day 6 vertical slice is complete in the current checkout. The
verified local demonstration produced four fictional zones, returned one batch
Expert System result per zone, resolved inside and outside points through
PostGIS, rendered the map on an Android emulator, and preserved the original
detailed explanation and DSS guidance flow.

The live Admin tests also confirmed that changing Demo Zone C's stored baseline
rank changed its next map result and that changing a demonstration guidance
instruction changed the next detailed assessment without changing the Expert
System conclusion. The documented procedure requires both temporary Admin edits
to be restored after testing.

The current automated totals are 84 backend tests and 89 Flutter tests. A later
suite may report a higher passing count as new tests are added. Day 7 remains a
separate integration, safety-audit, screenshot, performance, polish, and
presentation milestone.

## Scope boundaries

Day 6 adds:

- an interactive `flutter_map` map with pan, pinch/double-tap zoom, explicit
  zoom controls, and fit-to-all behavior;
- a development OpenStreetMap basemap with visible attribution;
- typed GeoJSON Polygon/MultiPolygon parsing, including interior rings;
- server-driven scenario recoloring for every eligible fictional zone;
- a visible five-state legend and text labels in addition to color;
- an in-memory, repositionable map pin;
- authoritative PostGIS point-in-polygon resolution;
- neutral outside-area, overlapping-area, unknown, loading, and error states;
- the existing zone selector as an accessible fallback;
- a selected-zone map preview and the existing full assessment/DSS flow; and
- a tested, repeatable fictional demonstration seed command.

Day 6 does not add GPS, location permission, coordinate persistence, assessment
history, resident accounts, background tracking, route analysis, evacuation
routing, live rainfall feeds, push notifications, offline tiles, production
deployment, or official Bacoor data.

## Flutter dependencies

Dependency tooling resolved:

```text
flutter_map 8.3.2
latlong2 0.10.1
```

`flutter_map` provides the map camera, tile, polygon, marker, and interaction
layers. `latlong2` supplies immutable latitude/longitude values and bounds.
Flutter tests disable the network basemap explicitly, so ordinary tests never
contact OpenStreetMap or Django.

## GeoJSON parsing and camera fitting

`GeoJsonGeometry` accepts only GeoJSON `Polygon` and `MultiPolygon` objects.
It converts every coordinate from the RFC 7946 order:

```text
[longitude, latitude] --> LatLng(latitude, longitude)
```

The parser:

- retains every polygon part;
- treats the first ring as the exterior and later rings as holes;
- requires at least four positions and a closed linear ring;
- requires at least three distinct positions;
- rejects missing, empty, unsupported, malformed, nonnumeric, non-finite, or
  out-of-range geometry; and
- exposes immutable polygon/ring collections.

A malformed feature fails through the existing typed API error path and shows
a controlled load error instead of crashing the widget tree or drawing an
unknown shape. Flutter never simplifies or writes the API geometry. The
initial camera bounds and the fit control are calculated from all returned
geometry; there is no hardcoded center.

## Polygon state and scenario recoloring

Before both rainfall selections exist, every polygon is neutral gray and says
that no scenario result is available. After intensity and duration are
selected, Flutter sends one batch request. The backend evaluates every eligible
area through `expert.services.evaluate_assessment()`.

For each result:

- `CLASSIFIED` uses the exact stored `SusceptibilityLevel.map_color` returned
  by Django;
- `UNCERTAIN`, `INSUFFICIENT_DATA`, missing, and unknown states remain neutral;
- the polygon includes a textual area/state label;
- transparent fill keeps the basemap visible; and
- the selected area uses a thicker primary-color border.

Changing either scenario selection immediately removes the old result map and
full assessment. A request-generation token prevents an older slow response
from overwriting a newer scenario. Identical completed or in-flight requests
are not repeated unless Retry is explicitly used. A failed map request leaves
the polygons neutral and preserves the selected rainfall inputs.

The legend contains Low, Moderate, High, Very High, and Uncertain/Insufficient
Data. Its notice states that colors describe the selected hypothetical
scenario—not current conditions or safety. Color is always paired with text.

## Point-resolution algorithm and privacy

The service entry point is:

```python
resolve_area_for_point(latitude=..., longitude=..., mode=...)
```

The service validates the WGS 84 ranges, constructs the spatial point as:

```python
Point(longitude, latitude, srid=4326)
```

It filters enabled records through the shared publication/operating-mode
policy. Demonstration mode additionally requires `area_type=DEMO_ZONE`. It then
uses the PostGIS `covers` predicate so a point exactly on a polygon boundary is
included.

Resolution is deterministic:

- exactly one covering eligible area returns `RESOLVED`;
- no covering area returns `OUTSIDE_SUPPORTED_AREA`; and
- more than one covering area returns `AMBIGUOUS_AREA`.

The overlap case never chooses a zone silently. Flutter keeps the pin visible,
clears the selected zone, uses neutral copy, and asks the user to move the pin
or use the selector. A network failure behaves similarly and offers Retry.

The pin coordinate exists only in the running controller and request body. The
backend performs no model creation and does not persist or unnecessarily log
the coordinate. No GPS or location permission is used.

## Public API additions

Both endpoints use `AllowAny` for the demonstration vertical slice while
returning only mode-permitted public fields.

### Resolve a temporary point

```text
POST /api/v1/geography/resolve-point/
Content-Type: application/json
```

Request:

```json
{
  "mode": "demonstration",
  "latitude": 14.005,
  "longitude": 120.005
}
```

Resolved response shape:

```json
{
  "resolution_state": "RESOLVED",
  "coordinate": {"latitude": 14.005, "longitude": 120.005},
  "area": {
    "id": 1,
    "code": "DEMO_ZONE_A",
    "name": "Demo Zone A",
    "area_type": "DEMO_ZONE",
    "data_status": "DEMONSTRATION"
  },
  "operating_mode": "DEMONSTRATION",
  "data_status": "DEMONSTRATION",
  "warnings": ["DEMONSTRATION DATA—NOT OFFICIAL"]
}
```

Outside and ambiguous outcomes use HTTP 200, set `area` to `null`, and return
`OUTSIDE_SUPPORTED_AREA` or `AMBIGUOUS_AREA`. Missing, malformed, non-finite,
or out-of-range coordinates return HTTP 400.

### Evaluate all map areas

```text
POST /api/v1/assessments/evaluate-map/
Content-Type: application/json
```

Request:

```json
{
  "mode": "demonstration",
  "rainfall_intensity_code": "DEMO_HEAVY",
  "rainfall_duration_code": "DEMO_6_HOURS"
}
```

Response shape:

```json
{
  "scenario": {
    "rainfall_intensity_code": "DEMO_HEAVY",
    "rainfall_duration_code": "DEMO_6_HOURS"
  },
  "results": [
    {
      "area": {"id": 1, "code": "DEMO_ZONE_A", "name": "Demo Zone A"},
      "assessment_state": "CLASSIFIED",
      "susceptibility": {
        "code": "MODERATE",
        "label": "Moderate",
        "map_color": "#E8B923"
      },
      "matched_rule_codes": ["DEMO-RULE-200"],
      "ruleset": {"name": "Demonstration Rules", "version": "1.0"},
      "summary": "Stored demonstration rule matched."
    }
  ],
  "operating_mode": "DEMONSTRATION",
  "data_status": "DEMONSTRATION",
  "warnings": ["DEMONSTRATION DATA—NOT OFFICIAL"]
}
```

Valid scenarios return HTTP 200 even if some areas are `UNCERTAIN` or
`INSUFFICIENT_DATA`. Those results have `susceptibility=null`; no class or color
is fabricated. Invalid, disabled, wrong-category, or mode-ineligible options
return HTTP 400. Results are ordered by area name and ID. The batch response
does not run or include DSS guidance.

The existing endpoint remains unchanged for a detailed selected-zone result:

```text
POST /api/v1/assessments/evaluate/
```

It continues to return full facts, rule rationales, explanation, warnings, and
DSS guidance.

## Repeatable demonstration data

Day 6 adds:

```powershell
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" seed_demo
```

Run this only against an explicitly authorized local development database. The
implementation has intentionally not run it against an existing developer
database automatically.

The command creates or refreshes:

- one source named `DEMONSTRATION DATA—NOT OFFICIAL`;
- four enabled demonstration susceptibility levels and their display colors;
- five hypothetical intensity choices with ranks 1–5;
- five hypothetical durations representing 1, 3, 6, 12, and 24 hours;
- four synthetic, non-overlapping `MultiPolygon` records named Demo Zone A–D;
- one baseline rank from 1–4 for each zone;
- the active `Demonstration Rules` version `1.0` ruleset;
- four stored demonstration rules with three controlled conditions each; and
- one safe provisional guidance item for each level.

Every created row uses demonstration status and demonstration provenance. The
synthetic rectangles are not barangay boundaries. Running the command twice
reuses stable identities and does not create duplicates. It can restore its
owned demonstration values and conditions.

The command uses one database transaction. It aborts and rolls back when:

- its reserved source name is duplicated or belongs to a non-demonstration
  source;
- a stable code/identity belongs to another source, including a different
  demonstration source;
- another demonstration ruleset is active;
- the reserved ruleset contains non-seed rules; or
- duplicate seed-owned facts or guidance make ownership ambiguous.

It does not disable another ruleset, replace official/approved/pending/
restricted/retired records, or delete unrelated records.

No Django model changed on Day 6, so no schema migration is required.

## OpenStreetMap development basemap

The tile URL is:

```text
https://tile.openstreetmap.org/{z}/{x}/{y}.png
```

The tile request supplies the application identifier
`ph.edu.cvsu.bacoor.floodsense`, and `© OpenStreetMap contributors` remains
visible at the lower-right of the map. No API key, offline download, or bulk
prefetch is used. Internet access is required for map tiles. Production must
select and review a suitable provider and its usage policy; this development
configuration is not a production deployment decision.

A failed basemap does not create or change FloodSense results. Polygon data and
assessment states come from Django, not from the basemap.

The seeded rectangles are intentionally placed at fictional coordinates away
from real Bacoor barangay geometry. The standard tiles can therefore appear as
a mostly light-blue open-water background. That appearance alone is not a tile
failure when the tile layer and attribution load; the rectangles remain
explicitly fictional and are the data being demonstrated.

## Run the current Django Admin functions

Use these steps only with an authorized local development database. Never run
the demonstration seed or perform a test edit against a shared, staging, or
deployed database.

### Step 1 — Open the repository root

```powershell
Set-Location (git rev-parse --show-toplevel)
```

This works from any directory inside the clone. All backend commands below
assume this location. PowerShell requires the call operator `&` before the
quoted Python executable path.

### Step 2 — Check the backend and apply committed migrations

```powershell
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" check
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" migrate
```

No Day 6 schema migration was required, but `migrate` prepares a teammate's
local database from all committed migrations.

### Step 3 — Create a local Admin login only when needed

```powershell
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" createsuperuser
```

Skip this when the local account already exists. The custom account uses an
email address. Local users and passwords are not synchronized by Git and must
never be committed or included in screenshots.

### Step 4 — Create or refresh the authorized local seed data

```powershell
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" seed_demo
```

Expected output includes the permanent demonstration warning, confirmation that
four fictional zones and the demonstration knowledge base were prepared, and
confirmation that one pending-validation Bacoor City boundary plus 47
pending-validation barangay boundaries were imported. The administrative layer
is a separate neutral reference source and contains no susceptibility facts.
Running the command again is safe: seed/import-owned values are refreshed
without duplicate rows. A `CommandError` for a reserved identity, source-code
conflict, or competing active ruleset is a protective rollback. Do not delete or
rename data to bypass it without first reviewing the record and its source.

Refreshing also restores the command's documented seed-owned defaults. A local
Admin customization to a seeded fact, rule, level, color, or guidance item will
therefore be replaced the next time `seed_demo` runs. This is useful for
repeatable demonstrations but must be understood before relying on a local
customization.

### Step 5 — Start Django and open Admin

```powershell
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" runserver 0.0.0.0:8000
```

Leave the terminal open and browse to:

```text
http://127.0.0.1:8000/admin/
```

The yellow development-server warning is normal. This server is only for local
development.

### Current Admin containers and effects

| Admin location | Current function | Effect on the next API/mobile request |
| --- | --- | --- |
| Provenance → Data sources | Inspect source, organization, status, and permitted use | Publication policy decides whether a record is eligible |
| Geography → Geographic areas | Edit fictional name, code, geometry, status, or enabled state | Changes GeoJSON membership and map visibility |
| Geography → Area facts | Edit `zone_baseline_rank` | Changes facts evaluated by stored Expert System rules |
| Expert → Scenario options | Edit labels, ranks/hours, order, status, or enabled state | Changes selectors and assessment facts |
| Expert → Susceptibility levels | Edit labels and `map_color` | Changes returned classification presentation and polygon color |
| Expert → Rule sets | Developer-only demonstration inspection | Not exposed as an ordinary custom-portal control |
| Expert → Expert rules | Developer-only demonstration inspection | Raw IF-THEN conclusions are fixed outside ordinary Admin workflows |
| Expert → Expert rule conditions | Developer-only demonstration inspection | Raw matching logic is fixed outside ordinary Admin workflows |
| DSS → Guidance items | Edit ordered provisional preparedness text | Changes DSS output without changing susceptibility |

For `Geographic areas`, baseline facts are available both as inline rows on the
area page and through the separate **Area facts** list. Only one enabled
seed-owned `zone_baseline_rank` should exist per demonstration zone.

### Safe Admin rules for this demonstration

- Verify `Status = DEMONSTRATION` and the demonstration source before editing.
- Use only Demo Zone A–D; do not assign an invented class to a real barangay.
- Record the original value before a temporary test and restore it afterward.
- Keep exactly one active demonstration ruleset unless intentionally testing a
  limitation state.
- Do not change official, approved, pending, restricted, retired, or unrelated
  records.
- Do not disable warnings or word guidance as an official order.
- No Django restart is needed after an Admin row edit; make a fresh API request
  or change the Flutter scenario to retrieve the new value.

### Step 6 — Verify Admin-to-map rule behavior

The currently tested scenario is **Intense + 6 hours**. With the seed-owned
baseline facts, the expected fictional results are:

| Zone | Baseline rank | Expected result | Stored color |
| --- | ---: | --- | --- |
| Demo Zone A | 1 | Moderate | `#E8B923` |
| Demo Zone B | 2 | High | `#E2691B` |
| Demo Zone C | 3 | Very High | `#C0392B` |
| Demo Zone D | 4 | Very High | `#C0392B` |

To prove that Flutter does not hardcode these conclusions:

1. In Admin, open **Geography → Area facts**.
2. Open Demo Zone C's `zone_baseline_rank` demonstration record.
3. Record the original numeric value `3` and change it temporarily to `2`.
4. Save.
5. In Flutter, change the duration from **6 hours** to **12 hours** to force a
   fresh batch request.
6. Confirm Demo Zone C changes from **Very High** / `DEMO-RULE-400` to
   **High** / `DEMO-RULE-300`, while Demo Zone D remains Very High.
7. Restore Demo Zone C's baseline value from `2` to `3` in Admin.
8. Return to Flutter and select **6 hours** again. Confirm Demo Zone C returns
   to Very High / `DEMO-RULE-400`.

### Step 7 — Verify Admin-to-DSS behavior

1. Select Demo Zone C with **Intense + 6 hours** and run the full assessment.
2. In Admin, open **DSS → Guidance items → Prioritize readiness**.
3. Record the original instruction.
4. Replace it temporarily with clearly labeled test text:

   ```text
   Day 6 live Admin test—demonstration guidance only.
   ```

5. Save, return to Flutter, and press **Assess Susceptibility** again.
6. Confirm the new instruction appears but the Very High susceptibility,
   facts, and matched rule remain unchanged.
7. Restore the original instruction and submit the assessment once more.

This test proves that DSS selects current stored preparedness text but does not
alter the Expert System's susceptibility conclusion.

### Step 8 — Disable and restore a fictional zone safely

This optional test demonstrates the current enable/disable function:

1. In **Geography → Geographic areas**, open Demo Zone D.
2. Record its current state, uncheck **Is enabled**, and save.
3. Request the GeoJSON collection and map assessment again.
4. Confirm Demo Zone D is absent from both API responses.
5. Quit and restart Flutter so it reloads the GeoJSON collection; confirm Demo
   Zone D is absent from the map.
6. Re-enable Demo Zone D immediately, restart Flutter again, and confirm it
   returns to both the API and map.

Never perform this check on an official or unrelated record.

## Run on the Android emulator

From the repository root, optionally prepare an authorized local database:

```powershell
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" seed_demo
```

Start Django:

```powershell
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" runserver 0.0.0.0:8000
```

In a second terminal:

```powershell
Set-Location ".\mobile"
flutter devices
flutter pub get
flutter run -d emulator-5554
```

Use the actual Android device ID printed by `flutter devices` when it differs
from `emulator-5554`.

The emulator uses `http://10.0.2.2:8000/api/v1`. Debug-only Android cleartext
configuration supports this local HTTP connection. Release builds still
require HTTPS.

For a physical phone, use a trusted shared network, add the computer's current
LAN IP to `DJANGO_ALLOWED_HOSTS`, allow the private-network firewall rule when
necessary, and run:

```powershell
flutter run --dart-define=FLOODSENSE_API_BASE_URL=http://192.168.1.10:8000/api/v1
```

Replace the example address with the actual LAN IP. Do not commit it or use
`ALLOWED_HOSTS=*`.

## API preflight commands

Keep Django running and execute these commands from a second PowerShell
terminal at the repository root.

### Step 1 — Confirm options and four GeoJSON zones

```powershell
$options = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/assessment-options/?mode=demonstration"
$areas = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/geography/areas/?mode=demonstration"

"Intensities: $($options.intensity_options.Count)"
"Durations: $($options.duration_options.Count)"
"Areas: $($areas.features.Count)"
$areas.features.properties | Select-Object id,code,name,data_status
```

After `seed_demo`, the expected counts are five intensities, five durations,
and four areas named Demo Zone A–D.

### Step 2 — Request one backend-derived result per map area

```powershell
$mapBody = @{
    mode = "demonstration"
    rainfall_intensity_code = "DEMO_INTENSE"
    rainfall_duration_code = "DEMO_6_HOURS"
} | ConvertTo-Json

$mapResult = Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8000/api/v1/assessments/evaluate-map/" `
    -ContentType "application/json" `
    -Body $mapBody

$mapResult | ConvertTo-Json -Depth 8
```

The response must have four ordered results, stored colors, matched rule codes,
the `Demonstration Rules` version `1.0` identity, and demonstration warnings.
It must not contain DSS guidance.

### Step 3 — Resolve an inside point

```powershell
$insideBody = @{
    mode = "demonstration"
    latitude = 14.005
    longitude = 120.005
} | ConvertTo-Json

$insideResult = Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8000/api/v1/geography/resolve-point/" `
    -ContentType "application/json" `
    -Body $insideBody

$insideResult | ConvertTo-Json -Depth 6
```

Expected: `RESOLVED` with `area.code = DEMO_ZONE_A`.

### Step 4 — Resolve an outside point without inventing a class

```powershell
$outsideBody = @{
    mode = "demonstration"
    latitude = 0
    longitude = 0
} | ConvertTo-Json

$outsideResult = Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8000/api/v1/geography/resolve-point/" `
    -ContentType "application/json" `
    -Body $outsideBody

$outsideResult | ConvertTo-Json -Depth 6
```

Expected: `OUTSIDE_SUPPORTED_AREA` and `area = null`. The endpoint resolves an
area only; it does not assign susceptibility to the coordinate.

### Stale-server 404 troubleshooting

If `evaluate-map/` or `resolve-point/` returns 404 and Django's debug URL list
does not contain the new path, an older server process is still running. Stop
the old server with `Ctrl+C`, then check:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
```

If a PID remains, inspect it before taking action:

```powershell
Get-CimInstance Win32_Process -Filter "ProcessId = <PID>" |
    Format-List ProcessId,ParentProcessId,Name,CommandLine
```

Only when it is the local FloodSense `manage.py runserver 0.0.0.0:8000`
command, enumerate and verify all matching Python launcher/child processes:

```powershell
$staleServers = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -eq "python.exe" -and
        $_.CommandLine -match "manage\.py runserver 0\.0\.0\.0:8000"
    }

$staleServers | Format-List ProcessId,ParentProcessId,Name,CommandLine
```

After verifying every match, stop only that narrow set and restart Django:

```powershell
$staleServers | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" runserver 0.0.0.0:8000
```

The Django text suggesting `DEBUG=False` is generic 404-page information; it
is not the fix for a stale local server.

## Manual end-to-end verification

Use only an authorized local database.

1. If needed and authorized, run `seed_demo`.
2. Start Django and open the assessment-options and geography area endpoints.
3. Confirm the GeoJSON endpoint returns Demo Zone A–D and no invented barangay
   classifications.
4. Post one scenario to `assessments/evaluate-map/` and confirm one result per
   enabled fictional zone.
5. Post an inside coordinate to `geography/resolve-point/`; confirm `RESOLVED`.
6. Post a distant coordinate; confirm `OUTSIDE_SUPPORTED_AREA` with no class.
7. Start Flutter and confirm the map, fictional-boundary warning, attribution,
   polygons, legend, and controls are visible.
8. Pan, zoom, and use the fit-all control.
9. Select intensity and duration; confirm the polygons update from the batch
   response.
10. Change either selection; confirm the old colors disappear before the new
    response arrives.
11. Tap inside a polygon; confirm the pin appears and Django resolves the same
    zone that Flutter highlights and selects.
12. Tap outside; confirm the pin remains, the selection clears, and no
    susceptibility is shown for the point.
13. Use the dropdown fallback and run the full assessment. Confirm the real
    explanation and DSS guidance render.
14. Change one demonstration baseline/rule through Admin, submit the map
    scenario again, and confirm the next backend-derived map result changes.
15. Change one guidance item, rerun the full assessment, and confirm only the
    DSS output changes.
16. Restore temporary Admin edits after the test.

The permanent warning must remain visible in screenshots. Never describe the
result as a current flood condition or the polygons as official boundaries.

## Automated verification

Prepare and use only the isolated local PostGIS test database documented in the
Day 3 guide.

From the repository root:

```powershell
& ".\server\.venv\Scripts\python.exe" -m ruff check server
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" makemigrations --check --dry-run
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" check
& ".\server\.venv\Scripts\python.exe" -m pytest -q --reuse-db
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" migrate --plan
```

Then:

```powershell
Set-Location ".\mobile"
flutter pub get
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
flutter build apk --debug
Set-Location ..
git diff --check
git status --short
```

The backend tests use real database-backed PostGIS predicates. Flutter widget
tests disable the tile layer and use fake API responses, so they do not contact
live map tiles or Django.

The current verified result is 84 passing backend tests and 89 passing Flutter
tests, with no Ruff, Django check, migration check, Dart format, or Flutter
analyzer failure. The debug APK is written to
`mobile/build/app/outputs/flutter-apk/app-debug.apk`.

## Teammate steps after pulling

No backend dependency or migration changed. From the repository root:

```powershell
& ".\server\.venv\Scripts\python.exe" -m pip install -r ".\server\requirements.txt"
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" migrate --plan
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" migrate
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" check
& ".\server\.venv\Scripts\python.exe" -m pytest -q --reuse-db
Set-Location ".\mobile"
flutter pub get
flutter analyze
flutter test
Set-Location ..
```

If the fictional shared dataset is needed, the teammate must confirm that the
target is their own local development database and then explicitly run:

```powershell
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" seed_demo
```

Git synchronizes the command, models, and migrations—not local PostgreSQL rows
or local administrator accounts.

## Remaining limitations and Day 7 handoff

- All polygons, ranks, rules, and guidance remain fictional and require later
  replacement or versioned expert validation.
- The online basemap requires public internet and has no offline tile cache.
- The application does not retain the pin or assessment history.
- No GPS, current-rainfall observation, forecast, alert, route, road-safety, or
  evacuation-center routing feature exists.
- Production hosting, HTTPS, rate limiting, monitoring, tile-provider review,
  and performance profiling remain future work.

Day 7 should perform full integration regression, a safety-language and data
audit, screenshot capture, device performance and visual polish, and a
repeatable adviser demonstration. Day 7 is not complete merely because the Day
6 map works.

## Team teach-back

The implementation can be summarized as:

> Flutter draws only the fictional GeoJSON areas returned by Django. When a
> hypothetical scenario changes, Django evaluates every eligible area through
> the same stored Expert System rules and sends the map colors. A temporary map
> pin is resolved by PostGIS, not by a hardcoded Flutter polygon rule. The
> selected zone then uses the original detailed assessment endpoint, and the
> DSS adds preparedness guidance without changing susceptibility.
