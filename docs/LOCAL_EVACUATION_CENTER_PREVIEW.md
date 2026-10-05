# Local synthetic evacuation-center display test

> Legacy workflow, superseded for new manual testing on 5 October 2026 by
> [Temporary data in the normal local workflow](LOCAL_TESTING_WORKFLOW.md).
> The separate endpoint/Flutter flag remain for compatibility only. The regular
> endpoint now has an explicitly gated local temporary-data mode; the older
> statements below describe normal operation with that mode disabled.

Added for the explicitly requested local Admin-to-Android manual test on
4 October 2026. This is a development display preview, not a change to the
verified-center publication policy or adoption of new scientific methodology.

## Separation from verified records

The regular `/api/v1/evacuation-centers/nearest/` API keeps its existing contract
and approval, verification, public-release, and geography gates. It continues to
exclude demonstration records.

The separate `/api/v1/evacuation-centers/local-preview/nearest/` POST API is
available only when **all** these conditions hold:

- `DJANGO_DEBUG=True` and `FLOODSENSE_ENABLE_LOCAL_CENTER_PREVIEW=True`;
- the backend uses PostGIS with a loopback database host;
- the HTTP request comes from loopback and targets a loopback hostname.

Otherwise it returns 404 without querying center records. It inherits the normal
request-size, rate-limit, JSON-validation, generic-error, and no-store controls.
It performs only SELECTs and does not retain the temporary lookup location.

Preview records must have a `LOCAL TEST -` name, DEMONSTRATION publication status,
a DEMONSTRATION source with DEMONSTRATION status and no public release, Draft or
In review verification state, no verification date, and no capacity. Coordinates
must be finite, in range, and inside their supported reference barangay. No
approved facility records are mixed into this preview. Internal notes and
contact details are never returned.

Every response and center explicitly carries `data_status=DEMONSTRATION`; every
center has `verified_on=null`. The preview has strict separate validation and
requires the synthetic warning. The app displays **Local test center preview**
and **not verified; not a real facility**, rather than inventing a verification
date. The ordinary response parser still rejects demonstration envelopes.

## Prepare local data in Admin

Use an authorized local development database and an existing clearly synthetic
DEMONSTRATION source. Do not create fake agency approval or modify official data.

1. Open `/management/evacuation-centers/new/`.
2. Name the record `LOCAL TEST - Evacuation Center (NOT A REAL FACILITY)`.
3. Enter a fictional address and clearly state that no facility exists there.
4. Associate a supported barangay and use a synthetic test coordinate inside it.
5. Select the demonstration source and **Demonstration** publication status.
6. Leave contacts and capacity unknown. Add explicit synthetic limitations.
7. Save as Draft. Do not verify or approve the fictional record.

Local Admin rows are not synchronized through Git. No seed or official import
is required for this test, and no model/migration change or new package was added.

## Enable the preview on a USB-connected Android phone

In the private `server/.env`:

```dotenv
DJANGO_DEBUG=True
FLOODSENSE_ENABLE_LOCAL_CENTER_PREVIEW=True
```

Restart Django on `127.0.0.1:8000`. In a debug Flutter build, include the matching
`FLOODSENSE_ENABLE_LOCAL_CENTER_PREVIEW=true` Dart define along with the existing
API/provider/public-token defines. The opt-in is ignored outside debug builds
or when the configured API hostname is not loopback. The app uses the separate
preview API only under these conditions.

When using a private Dart-define JSON file, add only the new boolean setting to
the existing selected client settings. Never pass the entire backend `.env` to
Flutter: it contains server credentials. Keep the file ignored by Git.

From `mobile`, replacing the device ID as needed:

```powershell
$floodSenseAdb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $floodSenseAdb -s DEVICE_ID reverse tcp:8000 tcp:8000
flutter run -d DEVICE_ID --dart-define-from-file=../tmp/floodsense-phone-dart-defines.json
```

Keep Django and USB running. Restore the reverse mapping after reconnection.

## Manual acceptance check

1. In Admin, inspect the test record, address, coordinates, source, Draft or
   In review state, and Demonstration label. Its ordinary resident checklist
   remains ineligible. Do not approve a fictional center to make it visible.
2. On the phone, begin Assess and select a scenario that can be classified.
3. Select Aniban 1 to bring its boundary into view. Drag the temporary map pin
   inside Aniban 1, then use **Confirm barangay**. The representative test marker
   used for the initial local test is latitude `14.454720`, longitude `120.965027`;
   these are synthetic display-test coordinates, not a facility or personal GPS.
4. Finish **Confirm area**, review, and **Assess Susceptibility** (Light / 1 hour
   is a working provisional local scenario for this barangay).
5. Open Prepare and scroll to its center section. Check the title, fictional
   address, barangay, approximate straight-line distance, source, and test warning.
6. Tap the card and check the selected marker on the shared map. Zero distance
   is expected only when the lookup pin matches the synthetic marker exactly.
7. Edit the test record's address or limitations in Admin. Move and reconfirm the
   temporary pin to make a new request, then check the changed text on the phone.
8. Remove the preview opt-in and rebuild: the ordinary center API must withhold
   the synthetic record. Missing records do not prove that real centers do not exist.

The test is for data delivery, layout, selection, and distance presentation. It
does not establish a real center's location, approval, opening, accessibility,
available space, route safety, or an evacuation recommendation.

## Recover from approving the boundary source during center testing

The reserved **Bacoor administrative boundaries—derived reference** source is
not evacuation-center verification evidence. Its source and 47 barangays must
remain **Pending validation**, with the existing reference release retained.
Approving that reserved source currently excludes the entire layer from the
resident boundary API and displays **No supported Bacoor boundary layer**.
Do not approve it to make a fictional center visible.

For an explicitly authorized local repair:

1. Preserve a private recovery snapshot of the affected source and centers.
   Do not commit snapshots or restore them casually over later edits.
2. Return the two affected test centers to editable Drafts through the normal
   Inactive -> In review -> Draft workflow, or a scoped, validated local
   maintenance repair. Remove the test-only verification date/capacity; retain
   the record IDs, address, coordinates and existing private details.
3. Restore the boundary source to **Pending validation**, remove its testing
   review metadata, and retain its existing publicly readable administrative
   reference setting. A normal source Return to review transition also removes
   public release, so this particular reserved-reference repair requires
   developer maintenance; do not bypass production publication policy.
4. Use a separate **Demonstration/synthetic** source with **Demonstration**
   status and public release **off**. Assign each test Draft to it, use a
   `LOCAL TEST -` name, and select **Demonstration** for center publication.
   Do not approve or verify the testing source or centers.
5. Set `FLOODSENSE_ENABLE_LOCAL_CENTER_PREVIEW=true` in the private backend
   `.env`, leaving existing GIS, Mapbox, and separately authorized settings
   unchanged. Restart Django; a running process may retain its earlier setting.
6. Stop the previous Flutter run and rebuild with the matching debug Dart
   define. From the repository root, the helper below reads only the public
   Mapbox token and selected safe flags, prefers an already connected wireless
   device, ignores malformed USB entries, and forwards port 8000:

   ```powershell
   .\server\.venv\Scripts\python.exe .\server\manage.py runserver 127.0.0.1:8000
   # In a separate terminal, from the repository root:
   powershell -ExecutionPolicy Bypass -File .\scripts\run_android_local_center_preview.ps1
   ```

   Pair/connect Wireless debugging beforehand if the device is not listed.
   No hard-coded phone IP or changing wireless port is saved in the helper.
   Use `-DeviceId CURRENT_ADB_ID` only when explicitly choosing among devices.
   `-ValidateOnly` checks local configuration/device discovery without launching
   or installing anything. It does not confirm that an old Django process has
   reloaded its environment setting. A normal launch also checks the running
   preview API and stops with a restart instruction if its opt-in is still off.
7. Confirm the boundary API returns 47 features. Confirm a preview lookup
   returns the test Drafts with **DEMONSTRATION**, no verification date, and the
   synthetic warning; the ordinary verified-center API must exclude them.
8. Complete a classified local scenario and open Prepare. The expected section
   title is **Local test center preview**. After editing a Draft in Admin, move
   and reconfirm the temporary pin to request its latest data; there is no
   background polling or general refresh button.

This configuration changes local records and private settings only; it adds no
package, migration, inference change or official-data import. Other teammates
do not receive those local records or private settings through Git. Never use
this maintenance procedure to downgrade genuinely approved agency records.

## Confirmed pin and manual barangay selection — 5 October 2026

Nearest-center requests require a temporary coordinate and a confirmed barangay;
a barangay name alone cannot provide distances. The map and center lookup now
use the same managed location coordinate, including when it is cleared.

- Reselecting the **same** barangay after **Confirm barangay** retains its
  already resolved pin/GPS coordinate, temporary GPS accuracy if applicable,
  and center request/results/selection. It does not make an extra request.
- Choosing a **different** barangay clears the old coordinate, its displayed
  user marker, and old center results. Place and confirm a new pin; the old
  coordinate must not be attributed to the newly selected barangay.
- Choosing a name while a candidate pin is still unconfirmed remains a
  barangay-only choice. It does not silently confirm that point.
- Clearing the temporary location removes the displayed user point even if
  the assessment controller still holds a legacy presentation cache. The
  initial draggable Mapbox placeholder is not a confirmed lookup coordinate.

For regression testing, rebuild/relaunch using the helper above, place a pin
inside the intended barangay, use **Confirm barangay**, and finish the classified
assessment. Check the local test center section in Prepare. Reselect that same
barangay and verify the point/results remain. Select another barangay and check
that the old point/results disappear and the coordinate-required message appears.
Place and confirm a fresh pin to request centers again.

An older running app whose lookup coordinate was already cleared cannot recover
it just by updating. Place and confirm the pin again after the rebuild. The local
preview accepts eligible **Draft and In review** synthetic records; the ordinary
verified-center API still excludes them. This fix adds no package, migration,
seed/import, background refresh, or change to approval/inference policy.

## Teammate and cleanup steps (normal preview use)

After receiving the code, no dependency installation, migration, or seed is
needed for this addition. Keep the setting false for ordinary operation. Each
teammate who explicitly rehearses this test creates their own local synthetic
Draft and enables both preview flags. Disable the backend flag and remove or
set the Dart define false after the test, restart Django, and rebuild the app.
The draft can remain in Admin as labeled demonstration data. Do not promote it
to a verified facility to make it visible.
