# FloodSense Day 5: Flutter assessment and live API integration

**Official research title:**  
**FLOODSENSE: AN ANDROID-BASED EXPERT SYSTEM FOR FLOOD SUSCEPTIBILITY
ASSESSMENT AND PRE-EVENT PREPAREDNESS IN BACOOR CITY**

> **Current scope notice (17 September 2026):** FloodSense remains a
> user-triggered, scenario-based assessment. The historical demonstration flow
> below is not a live rainfall feed, background timer, continuous monitor, or
> official alerting service. Follow `TA_CONSULTATION_SYSTEM_DECISIONS.md` for the
> current behavior and unresolved adviser questions.

## Day 5 outcome

Day 5 replaces the Flutter counter scaffold with one responsive assessment
screen. The screen immediately shows the permanent demonstration warning,
loads rainfall choices and fictional demonstration zones from Django, requires
the user to make three explicit selections, posts the selected scenario, and
renders the returned explanation and DSS guidance.

Flutter is a client of the existing Day 4 contract. It contains no permanent
flood rules, rainfall thresholds, preparedness guidance, or invented
classifications. It does not silently switch to local data when Django is
unavailable.

The Day 5 milestone itself did not implement a map, polygon interaction, or
coordinate resolution. The current checkout now includes the completed Day 6
map on the same screen. It still does not add GPS, resident authentication,
history, offline assessment, a guided DSS questionnaire, notifications, or
evacuation routing.

## Current status after Day 6

Day 5 and Day 6 now form one tested vertical slice. The current application
still performs the Day 5 detailed assessment, but it also displays API-provided
GeoJSON polygons, requests batch map results, and resolves a temporary map pin
through PostGIS. The map does not replace the original Day 5 assessment:

1. the batch endpoint supplies lightweight colors and summaries for the map;
2. a map tap or the dropdown chooses one fictional zone; and
3. **Assess Susceptibility** still calls the original single-area endpoint and
   renders the complete explanation and DSS guidance.

The current verified totals are 84 backend tests and 89 Flutter tests. These
counts may increase as later work adds tests; a higher passing total is not an
error.

## Mobile structure

```text
mobile/lib/
|-- main.dart
|-- app/
|   |-- floodsense_app.dart
|   `-- theme/
|       |-- app_colors.dart
|       `-- app_theme.dart
|-- config/
|   `-- api_config.dart
|-- data/
|   |-- api/
|   |   |-- api_exception.dart
|   |   `-- floodsense_api_client.dart
|   `-- models/
|       |-- assessment_request.dart
|       |-- assessment_result.dart
|       |-- geographic_area.dart
|       |-- geojson_geometry.dart
|       |-- guidance_item.dart
|       |-- json_parsing.dart
|       |-- map_assessment_result.dart
|       |-- point_resolution.dart
|       `-- scenario_option.dart
`-- features/
    `-- assessment/
        |-- assessment_controller.dart
        |-- assessment_screen.dart
        `-- widgets/
            |-- assessment_result_card.dart
            |-- demonstration_warning.dart
            |-- duration_selector.dart
            |-- dynamic_map_card.dart
            |-- guidance_section.dart
            |-- limitation_result_card.dart
            |-- scenario_selector.dart
            `-- zone_selector.dart
```

Transport and decoding are outside widgets. Immutable typed models validate
required fields and tolerate unknown extra response fields. The small
`AssessmentController` owns loading, shared scenario selections, detailed
submission, map evaluation, temporary point resolution, retry errors, and
stale-result invalidation. Visual widgets only present the current state.

## API client responsibilities

`FloodSenseApiClient` provides:

```dart
Future<AssessmentOptions> fetchAssessmentOptions()
Future<List<GeographicArea>> fetchDemonstrationAreas()
Future<AssessmentResult> evaluateAssessment(AssessmentRequest request)
Future<MapAssessmentResult> evaluateMapScenario(...)
Future<PointResolution> resolvePoint(...)
```

The first three methods implement the Day 5 contract. The final two are the
Day 6 additions used by the current integrated screen.

It normalizes the base URL, sets JSON request headers, decodes UTF-8, applies a
15-second timeout, and maps failures into validation, connectivity, service,
or malformed-response exceptions. HTTP 400 field messages are retained when
useful; stack traces and raw server internals are not shown to users. The
client is injectable, so automated tests use fakes or an HTTP mock instead of
a running server.

The typed response layer includes `ScenarioOption`, `AssessmentOptions`,
`GeographicArea`, `AssessmentRequest`, `AssessmentResult`, `Susceptibility`,
`AssessmentExplanation`, `RuleSetSummary`, and `GuidanceItem`. GeoJSON geometry
is now parsed into typed immutable Polygon/MultiPolygon objects for the
completed Day 6 map. A valid six-digit server `map_color` is converted to an
opaque color; malformed colors use neutral gray without changing the result
label.

## Endpoints and payloads

The Day 5 detailed-assessment flow uses the Day 4 endpoints:

```text
GET  /api/v1/assessment-options/?mode=demonstration
GET  /api/v1/geography/areas/?mode=demonstration
POST /api/v1/assessments/evaluate/
```

The assessment body is exactly:

```json
{
  "mode": "demonstration",
  "geographic_area_id": 1,
  "rainfall_intensity_code": "DEMO_MODERATE",
  "rainfall_duration_code": "DEMO_1_HOUR"
}
```

Flutter does not call the direct DSS endpoint during normal assessment because
the integrated response already contains the ordered `guidance` array.

The current Day 6 map also uses:

```text
POST /api/v1/assessments/evaluate-map/
POST /api/v1/geography/resolve-point/
```

Their exact payloads, limitation states, and PostGIS behavior are documented in
`docs/DAY_6_DYNAMIC_MAP_GUIDE.md`.

## State flow

1. The page shell and safety notice render immediately.
2. Rainfall options and geographic areas load concurrently.
3. While loading, an accessible progress state is visible.
4. A failed load displays a plain-language error and Retry.
5. An empty option group or area list displays the administrator-configuration
   message. No local fallback options are invented.
6. Intensity, duration, and area start unselected. The assessment button stays
   disabled until all three are selected.
7. Submission clears any prior error/result, shows progress, disables duplicate
   submission, and sends the exact selected identifiers.
8. A recoverable error preserves all selections and offers Retry.
9. Changing any selection immediately removes the old result and requires a
   new assessment.

`CLASSIFIED` displays the server label and color, area, selected scenario,
plain-language explanation, facts, matched rule codes, ruleset/version, data
status, exact warnings, and ordered DSS guidance. If guidance is empty, the UI
states that susceptibility was assessed but no enabled preparedness guidance
is currently available.

`UNCERTAIN` and `INSUFFICIENT_DATA` use neutral styling, retain explanation,
ruleset, matched rules when supplied, and warnings, and never display
classification-dependent guidance. An unknown future state also stays neutral
and explicitly says that no classification was assumed.

## API base URL and Android networking

The compile-time setting is `FLOODSENSE_API_BASE_URL`. Trailing slashes are
removed before paths are joined.

Android emulator default:

```text
http://10.0.2.2:8000/api/v1
```

Start Django from the repository root:

```powershell
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" runserver 0.0.0.0:8000
```

Run against another local URL without editing source:

```powershell
Set-Location ".\mobile"
flutter run --dart-define=FLOODSENSE_API_BASE_URL=http://192.168.1.10:8000/api/v1
```

For a physical phone:

- put the phone and computer on the same trusted local network;
- run Django on `0.0.0.0:8000`;
- add the computer's actual LAN IP to `DJANGO_ALLOWED_HOSTS`;
- allow TCP port 8000 through the computer's private-network firewall if
  necessary; and
- never configure `ALLOWED_HOSTS=*` or commit a personal LAN address.

The main Android manifest grants Internet access, which production HTTPS also
requires. Only the debug manifest enables cleartext HTTP. A release build does
not receive that override. Production must use HTTPS.

## Run the current Django Admin and verify Day 5

Use only an authorized local development database. These instructions do not
apply to a shared, staging, or deployed database.

### Step 1 — Open the repository root

In a new VS Code PowerShell terminal:

```powershell
Set-Location (git rev-parse --show-toplevel)
```

This works from any directory inside the clone, including `mobile`. The
commands below assume that the prompt ends at the repository root, not at
`mobile`, `server`, or the parent `Documents` directory.

### Step 2 — Check and prepare the local schema

```powershell
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" check
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" migrate
```

Day 5 and Day 6 do not introduce an unapplied schema migration in the current
checkout, but `migrate` safely applies any committed migrations that a teammate
has not yet applied locally.

### Step 3 — Create a local administrator only when needed

Local administrator accounts are PostgreSQL rows and do not arrive through
Git. If no local staff/superuser login exists, run:

```powershell
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" createsuperuser
```

Enter the requested local email and password. Do not put that password in a
guide, screenshot, commit, chat message, or `.env.example`. Skip this command
when the local administrator already exists.

### Step 4 — Prepare the fictional demonstration rows when authorized

The current checkout includes the tested Day 6 command:

```powershell
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" seed_demo
```

It creates the clearly labeled fictional zones, rainfall options, levels,
rules, baseline facts, and DSS guidance used by the current Day 5–6 demo. It is
transactional and idempotent. It refreshes only records owned by its reserved
demonstration source and aborts instead of taking over a conflicting identity.

Because rerunning the command restores seed-owned values, it will also replace
intentional local edits to those seed-owned demonstration rows with the
documented defaults. Do not rerun it while trying to preserve a deliberate
Admin customization.

Do not delete a conflicting record merely to make the command pass. Inspect the
reported identity and its provenance first. Running `seed_demo` is optional if
the authorized local database already contains a complete compatible
demonstration dataset.

### Step 5 — Start Django Admin and the API

```powershell
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" runserver 0.0.0.0:8000
```

Leave this terminal open. The yellow warning that Django's development server
is not for production is expected. Open:

```text
http://127.0.0.1:8000/admin/
```

Sign in with the local administrator and confirm these current Admin groups:

- **Provenance → Data sources** controls source identity and status;
- **Geography → Geographic areas** controls names, codes, geometry, status,
  enabled state, and inline facts;
- **Geography → Area facts** controls values such as
  `zone_baseline_rank`;
- **Expert → Scenario options** controls rainfall choices and derived values;
- **Expert → Susceptibility levels** controls labels and stored map colors;
- **Expert → Rule sets**, **Expert rules**, and **Expert rule conditions** are
  developer-only demonstration controls for the deterministic knowledge base
  and are not ordinary custom-portal administrator functions; and
- **DSS → Guidance items** controls preparedness text without changing the
  Expert System conclusion.

Only edit records whose source and status are visibly demonstration data. Do
not create an unofficial classification for a real barangay.

### Step 6 — Recover a stale local server safely

If a newly added endpoint returns Django 404 and the debug URL list does not
contain that endpoint, an older `runserver` process may still own port 8000.
First return to its terminal and press `Ctrl+C`. Then check:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
```

No output means the port is free. If it still lists an owning PID, inspect only
that process before stopping it:

```powershell
Get-CimInstance Win32_Process -Filter "ProcessId = <PID>" |
    Format-List ProcessId,ParentProcessId,Name,CommandLine
```

Replace `<PID>` with the displayed number. Stop it only when the full command
is the local FloodSense `manage.py runserver 0.0.0.0:8000` command. When a
Windows Python launcher left both parent and child processes, enumerate the
narrowly matched local servers:

```powershell
$staleServers = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -eq "python.exe" -and
        $_.CommandLine -match "manage\.py runserver 0\.0\.0\.0:8000"
    }

$staleServers | Format-List ProcessId,ParentProcessId,Name,CommandLine
```

After verifying every displayed command, stop only those matching processes:

```powershell
$staleServers | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
```

Start Django again with the Step 5 command. Do not change `DEBUG` to solve this
local stale-process issue.

### Step 7 — Start the current Flutter application

Open a second terminal and keep Django running in the first:

```powershell
Set-Location ".\mobile"
flutter devices
flutter pub get
flutter run -d emulator-5554
```

Use the ID printed by `flutter devices` if it is not `emulator-5554`. The
Android emulator connects to Django through
`http://10.0.2.2:8000/api/v1`.

### Step 8 — Verify the Day 5 detailed-assessment flow

1. Select one API-provided rainfall intensity and duration.
2. Select a fictional zone through the dropdown or resolve it with the map.
3. Press **Assess Susceptibility**.
4. Confirm the area, scenario, susceptibility label, stored color, explanation,
   facts, matched rule codes, ruleset version, data status, and warnings.
5. Confirm that `CLASSIFIED` shows ordered DSS guidance.
6. Confirm that `UNCERTAIN` or `INSUFFICIENT_DATA` remains neutral and does not
   receive class-dependent guidance.

### Step 9 — Prove the Admin-to-Flutter guidance connection

1. In Admin, open **DSS → Guidance items**.
2. Open the enabled demonstration guidance item used by the current result.
3. Record its original title and instruction.
4. Change only the instruction to clearly provisional test text, for example:

   ```text
   Day 5 live Admin test—demonstration guidance only.
   ```

5. Save it. No Django restart is required because each API request reads the
   current database.
6. Return to Flutter and press **Assess Susceptibility** again for the same
   scenario and zone.
7. Confirm the edited instruction appears while the susceptibility level,
   facts, and matched rule remain unchanged.
8. Restore the original guidance instruction in Admin and submit once more to
   confirm it was restored.

If required demonstration collections are empty, the Flutter administrator
configuration message is the correct behavior. Do not claim the live test
succeeded until the authorized local records exist.

## Verification commands

From the repository root, run the complete current backend regression suite:

```powershell
& ".\server\.venv\Scripts\python.exe" -m ruff check server
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" check
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" makemigrations --check --dry-run
& ".\server\.venv\Scripts\python.exe" -m pytest -q --reuse-db
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" migrate --plan
```

The current verified result is 84 backend tests, no Django system-check issue,
no model change, and no planned migration operation. The test command must use
the isolated local `test_floodsense` PostGIS database documented in the Day 3
guide, never a shared or deployed database.

Then run the current Flutter checks:

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

The current verified result is 89 Flutter tests, no analyzer issue, and a
successful debug APK at
`mobile/build/app/outputs/flutter-apk/app-debug.apk`.

## Teammate setup after pulling

Day 5 did not add a backend dependency or schema migration, while the current
Day 6-integrated Flutter application adds `flutter_map` and `latlong2`. From the
repository root, each teammate runs:

```powershell
& ".\server\.venv\Scripts\python.exe" -m pip install -r ".\server\requirements.txt"
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" migrate
& ".\server\.venv\Scripts\python.exe" ".\server\manage.py" check
Set-Location ".\mobile"
flutter pub get
flutter analyze
flutter test
Set-Location ..
```

If the teammate has no local Admin login, they run `createsuperuser` as shown
above. If the fictional dataset is needed and the local target is explicitly
authorized, they run `seed_demo`. Git synchronizes code and migrations, not
PostgreSQL rows, administrator accounts, or passwords.

## Remaining limitations and completed Day 6 handoff

- The current client requires a reachable backend and does not cache
  assessments or tiles for offline use.
- Demonstration zones, facts, rules, classifications, and guidance remain
  fictional and scientifically unvalidated.
- The app has no resident account flow, saved history, GPS, location
  permission, notification delivery, or routing.
- DSS output remains the Day 4 ordered guidance list, not a questionnaire tree.
- Production HTTPS, hosting, monitoring, and official-data validation remain
  future work.

The planned Day 6 handoff is complete: the same API client and typed models now
render GeoJSON polygons with `flutter_map`, recolor them through stored backend
rules, resolve a temporary pin with PostGIS, and preserve every warning and
neutral limitation state. Day 7 integration and presentation work is not yet
complete.
