# Local synthetic evacuation-center display test

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

1. In Admin, inspect the test record, address, coordinates, source, Draft state,
   and Demonstration label. Its ordinary resident checklist remains ineligible.
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
7. Edit the Draft's address or limitations in Admin. Move and reconfirm the
   temporary pin to make a new request, then check the changed text on the phone.
8. Remove the preview opt-in and rebuild: the ordinary center API must withhold
   the synthetic record. Missing records do not prove that real centers do not exist.

The test is for data delivery, layout, selection, and distance presentation. It
does not establish a real center's location, approval, opening, accessibility,
available space, route safety, or an evacuation recommendation.

## Teammate and cleanup steps

After receiving the code, no dependency installation, migration, or seed is
needed for this addition. Keep the setting false for ordinary operation. Each
teammate who explicitly rehearses this test creates their own local synthetic
Draft and enables both preview flags. Disable the backend flag and remove or
set the Dart define false after the test, restart Django, and rebuild the app.
The draft can remain in Admin as labeled demonstration data. Do not promote it
to a verified facility to make it visible.
