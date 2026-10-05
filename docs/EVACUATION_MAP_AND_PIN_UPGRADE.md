# Evacuation map and location-pin update — 5 October 2026

This implements the project owner's usability request. It is a team decision,
not adviser/agency approval or a new flood-assessment methodology.

## What changed

- The signed-in resident map loads up to **25 nearest eligible evacuation-center
  references around its initial midpoint pin**, before a personal location is
  chosen. Shelter/building icons replace plain circles on
  native Android Mapbox and the standard-map fallback. Logging in does not
  request GPS or claim a confirmed personal location. Moving the pin requests a
  new shortlist; panning/zooming, navigation and opening the legend do not.
- After a point is confirmed, the nearest result has a persistent nearest cue
  and three gentle visual beats. Reduced-motion/system accessibility settings,
  hidden map surfaces and app backgrounding suppress/stop decoration. No
  repeating vibration, GPS tracking or network polling is added.
- Prepare shows the nearest center and approximate straight-line distance even
  before a classified assessment. Tailored DSS guidance still requires its
  existing classified-assessment gate. Distance is not road distance, route
  safety, opening status, capacity, or an instruction to evacuate.
- GPS puts the draggable pin at the exact acquired coordinate, with its
  existing accuracy and barangay-confirmation checks. The resolver's rounded
  coordinate is never substituted.
- Manual barangay selection puts the pin at a deterministic point strictly
  inside the selected boundary, accounting for concavity, holes and multipart
  geometry. It is labeled an **approximate reference—not your actual location**.
  Drag the pin and confirm the refined point for a more meaningful distance.
  Selecting the already confirmed GPS/pin barangay preserves the precise point.
- Refresh centers reloads both distance results and the startup map catalog.
  Tab navigation, sheet dragging and center refresh do not reset the user pin,
  scenario or map camera. Tapping a shelter selects the shelter, not the user's
  location pin. Clearing the location clears nearest/distance claims; eligible
  shelter icons around the initial midpoint reference can remain.

## Run and test locally

No new package, schema migration, seed, import or application database is needed
for this update. Restart Django if it is not automatically reloading, then stop
and relaunch Flutter so the updated client is installed. From the repository
root, use separate PowerShell terminals:

```powershell
.\server\.venv\Scripts\python.exe server\manage.py runserver 127.0.0.1:8000
```

```powershell
.\scripts\run_android_local.ps1
```

The helper reads the existing public Mapbox token from the private backend
configuration without displaying it, selects the currently authorized phone,
and forwards its API connection. If multiple distinct phones are connected,
pass `-DeviceId` with the current identifier from `adb devices -l`.

For temporary sources/centers, follow
[the ordinary local testing workflow](LOCAL_TESTING_WORKFLOW.md). Existing
records use the same Admin forms and database rows; test approval does not
claim real facility verification. In-review/inactive/withdrawn records remain
excluded. Do not change the administrative boundary's source status to approve
a center. This code update does not approve or delete existing application rows.

1. Locally approve a temporary center and its temporary source using the
   existing Admin action, or use an already eligible genuine center in normal
   mode. On 5 October, the inspected local database still contained two
   **in-review** temporary centers, so neither was eligible yet. Later that day,
   the owner explicitly authorized local approval of those same two centers and
   their existing temporary source. The running catalog then returned both
   centers. No new source/center row or boundary change was made; these local
   approvals are not transferred by Git and are not real-facility verification.
2. Sign in. Check shelter icons before choosing GPS/manual/pin location. No
   nearest label/distance should be claimed yet.
3. Choose a barangay manually. Check the pin is inside its boundary and the
   approximate-reference label is visible. Prepare must describe distance from
   that reference, not from your device.
4. Use my location, continue after the explanation, then confirm the detected
   barangay. Check the pin moves to the acquired GPS point. Alternatively drag
   and confirm the pin. The nearest shelter should briefly beat and remain
   distinguished after the animation ends.
5. Pan/zoom, switch Map/Assess/Prepare/Profile and move the bottom sheet. Verify
   the same map camera and pin are retained. GPS coordinates still have normal
   measurement uncertainty; "exact" here means the acquired reading is retained.
6. Edit/withdraw a temporary center in Admin, then tap Refresh centers. Its
   eligibility is rechecked on this explicit request, not in real time.
7. Clear the location. Nearest emphasis and distances disappear without removing
   otherwise eligible reference icons. Denied GPS permission must leave manual
   selection usable.

## API and teammate setup

The signed-in map uses read-only `POST /api/v1/evacuation-centers/map/` with a
transient latitude/longitude JSON body (not a URL query or location history).
It ranks all eligible candidates by the existing PostGIS straight-line distance
expression, caps output at 25 safe records, breaks ties by public UUID, and
reports hidden additional records honestly. Its response contains no distance
or private facility fields. The older coordinate-free GET remains compatible,
capped at 1000 records in UUID order; the resident map does not use it.
The existing nearest endpoint remains the distance authority. Source,
publication and controlled-boundary eligibility remain enforced. Genuine and
opted-in temporary responses never mix.

After pulling the eventual commit, teammates restart the backend and rebuild
the Flutter client. There are no new dependencies or migrations attributable
to this update. Their local rows, approval states, `.env`, superusers, Mapbox
tokens and phone identifiers are not synchronized by Git. Normal deployment
keeps `FLOODSENSE_LOCAL_TESTING=false`; temporary catalog/nearest responses
remain debug-loopback-only. See the
[catalog contract](../server/evacuation/MAP_CENTER_CONTRACT.md) for exact fields.

## Verification

On 5 October 2026, the complete isolated backend suite passed **891 tests**,
the complete Flutter suite passed **327 tests**, Flutter analysis and Python
lint were clean, Django checks passed, and migration-drift checks found no
changes. The final Mapbox/3D-enabled Android debug APK built successfully.
Existing Gradle native-access and Mapbox Kotlin-plugin future-compatibility
warnings did not fail the build; no dependency upgrade is required by this
feature. No Android phone was connected during that initial build for a
physical rendering/GPS check. Use the steps above to complete device checks.

A subsequent wireless-phone check identified an icon-image format regression:
the installed Mapbox Flutter native bridge expects encoded PNG bytes, not the
raw RGBA buffer described by its Dart image type. Shelter images now use PNG,
with tests exercising the actual encoder, PNG decoding, dimensions and
transparency. This was the reason for "Enhanced map unavailable. Standard map
is active" despite a valid token and the correct run helper. No token,
dependency or database change is needed. Press uppercase `R` in the active
Flutter terminal for a hot restart, or stop Flutter and rerun the same helper.
Hot reload alone retains the already-triggered fallback state.

The subsequent full app relaunch restored Mapbox on the phone. The wide
"Your selected map pin" overlay was then removed from the map. Pin origin is
shown as a compact inline row inside the location card instead; map accessibility
and the recenter tooltip still describe it. Manual barangay references retain
the explicit "not your actual location" limitation. This presentation change
does not change the pin coordinate, dragging, camera, or center eligibility.
The complete Flutter suite was rerun after this layout adjustment: all **331
tests** passed, including selected-pin/GPS labels inside the location card,
clearing, manual-reference limitations and narrow-screen checks. Flutter
analysis and Django system checks were clean, and the updated Mapbox/3D Android
debug APK built successfully. No new package or migration is
needed; reload the Dart layout and explicitly refresh centers in an existing
session, or use the normal launcher for a fresh app session.

### Nearest-25 and compact-legend refinement — 5 October 2026

The later owner request replaced the all-center map display with the shortlist
described above. Both resident surfaces use the same pin-centered POST and
ignore out-of-order responses after a pin move. Nearest/Prepare metadata can
enrich members but cannot reintroduce hidden centers. The ordinary Refresh
action rechecks eligibility without moving the pin or resetting the camera.

Native shelter text is optional, icon overlap is allowed, and 3D occlusion does
not hide the icon. Native initialization also replays newer center/location
data that arrives while layers are being registered. Susceptibility colors and
the outside-coverage explanation moved into a compact Legend popup; opening
or closing it does not change the camera. The repetitive global Admin testing
banner was removed, retaining temporary labels on individual records.

Verification for this refinement: **902 isolated backend tests and 340 Flutter
tests passed**; Flutter analysis, targeted Python lint, Django checks and
migration-drift checks were clean. The Mapbox/3D Android debug APK built
successfully. The running local pin-centered API returned both existing
approved temporary centers. Desktop and mobile Admin rendering was visually
checked with the actual template and unsaved synthetic objects (the live
browser was signed out); no accounts or application database rows were created.
The owner's manually edited **300-meter** camera target was preserved, with
tests covering both the original 70-meter conversion and the configured target.

Refresh the Admin page, stop Flutter with `q`, and rerun
`scripts/run_android_local.ps1` for the updated native style. On-device pan/zoom
visibility still needs checking after that full relaunch; this verification did
not reinstall or reset the running phone app. With only two eligible records,
both should appear when their coordinates are in the visible viewport; the
25-marker cap never invents additional centers. At a very distant zoom two
nearby icons can physically overlap, but label collision must not remove them.
No new package, migration, seed, import or application-row change is required.

### Camera easing refinement — 5 October 2026

Zoom buttons now use a 650 ms native eased transition, and pin/manual/GPS focus
uses 1400 ms. Fit-all uses 800 ms and shelter recenter uses 850 ms. The owner's
300-meter selected-location target is unchanged. Editable timing constants are
beside that height in `mobile/lib/features/map/flood_map_camera.dart`.

Dragging updates the coordinate; the normal presentation update alone starts
the focus animation, avoiding a duplicate restart after source refresh. Queued
updates for an older coordinate cannot focus over a newer pin. System reduced-
motion settings disable camera animation. This changes presentation only;
location confirmation, shortlist ranking and navigation behavior are unchanged.
Relaunch Flutter after pulling; no backend restart, dependencies or migrations
are required for this camera-only refinement. Device smoothness should be
checked with a zoom step, long-distance selection and pin drag after relaunch.

Verification: all 345 Flutter tests passed, Flutter analysis found no issues,
and the Android debug APK built successfully. No phone app was restarted or
installed by this change; perceived smoothness still needs the owner's device
check. Nothing was committed or pushed.

### Resident layout and single-confirmation refinement — 6 October 2026

The owner requested these follow-up changes:

- Three bottom tabs: **Assess / Prepare / Profile**. Flood information and
  results now belong to Assess; the map stays mounted behind the sheets.
  A static FloodSense pill replaces the top assessment shortcut.
- A 108 × 34 px collapsed expand tab inside a 108 × 48 px touch target. Its
  arrow moves upward at most 3 px twice, then stops. Reduced motion disables
  the hint; backgrounding stops it. The central drag bar and right collapse
  button have separate hit targets and cannot overlap.
- The compact Legend has four susceptibility swatches and one gray row for
  unclassified/insufficient data and outside Bacoor. Repeated coverage and
  shelter explanatory paragraphs are removed from this popup, not from center
  detail limitations. Classification colors still come from the backend.
- Native Mapbox's north-reset compass is disabled so it cannot intercept taps
  under the custom zoom button. Attribution and other app controls are retained.
- Step 2 has a compact location-origin row and barangay name, Use my location,
  clear and manual selection controls. Duplicate explanations, green/yellow
  metadata containers, Correct manually and Confirm barangay are removed.
  Boundary metadata/limitations, accuracy and the existing provisional baseline
  appear in Step 3 Review instead. The short blue confirmation notice remains.
- One **Confirm area** action confirms a GPS/pin candidate and advances to
  Review. Moving the point invalidates the prior confirmed selection. Neither
  resolving a point nor confirming an area runs an assessment automatically.
- Purpose-dialog **Continue** opens Android Location Settings immediately if
  location is disabled. Returning retries once. Try again handles failed launches
  or a service that remains disabled; it does not create a settings/retry loop.
  Clearing, cancelling or choosing manually cancels pending GPS recovery.

#### Test on your phone

1. Leave the Django server running. Stop Flutter with `q`, then from the
   repository root rerun `scripts/run_android_local.ps1`. Pass the current
   authorized `-DeviceId` if the launcher sees more than one connection.
   The helper reads the existing Mapbox configuration; do not paste a token
   into chat or commit it. A full relaunch refreshes native map controls.
2. Check the three tabs and FloodSense header. Hide/expand the sheet, drag its
   bar, and verify the down arrow is separately clickable. Zoom/pan, navigate
   and return: the camera must not reset from those sheet/tab interactions.
3. Open Legend: four class colors plus the combined gray row, no long repeated
   gray/shelter paragraphs. Rotate the map: no hidden compass under the + button.
4. Begin an assessment and choose a scenario. Drag the pin to a supported
   barangay. Step 2 shows its name, no separate Confirm barangay. Tap Confirm
   area once to reach Review, where source/baseline limitations remain available.
5. Return to Step 2 and test manual selection, GPS, dragging and clear. GPS uses
   the acquired coordinate; a manual reference is approximate. The origin label
   must not continue saying Your selected map pin after a change to GPS/manual.
6. With phone location turned off, tap Use my location → Continue. Android
   Location Settings should open immediately. Turn location on and return;
   FloodSense makes one foreground attempt. If you leave it off, it must not
   reopen settings repeatedly. Try again and manual selection remain available.

Teammates only need to relaunch Flutter after pulling. This refinement requires
no new package, backend restart, migration, seed/import, data approval or database
row change. The normal deployment/testing gates are unchanged. The Android build
check is compilation only, not proof of on-device GPS/settings or Mapbox rendering.

Verification: all **357 Flutter tests** passed, including single confirmation
from GPS/pin, mode-label changes, camera retention, first-attempt settings launch,
single settings-return retry, recovery cancellation, narrow-screen sheet-control
separation, and finite/reduced-motion/background arrow behavior. Flutter analysis
found no issues; the Android debug APK compiled with Mapbox/3D configuration.
Existing Gradle native-access and Mapbox Kotlin migration warnings remain
non-fatal. On-phone rendering and settings recovery still need the device check
above. Nothing was committed, pushed, installed or changed in the database.
