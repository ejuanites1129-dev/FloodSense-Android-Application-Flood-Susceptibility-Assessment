# Temporary data in the normal local workflow

Team-authorized on 5 October 2026 after the project owner's request to simplify
testing. This is a development workflow decision, not adviser approval, agency
verification, a new scientific method, or public release permission.

## What changes

- Use the existing Sources and Evacuation centers tables and normal custom Admin
  forms. No second application database, test registry, automatic seeds, or
  additional copies of records are created.
- A checkbox labels a row temporary. The existing `DEMONSTRATION` source type
  and publication status preserve this distinction in storage. You do not need
  a `DEMO` or `LOCAL TEST` prefix in the name.
- The normal `/api/v1/evacuation-centers/nearest/` POST endpoint returns approved
  temporary centers **instead of** genuine centers in the opted-in local session.
  Each result is visibly labeled unofficial/not a verified real facility.
- The ordinary debug Flutter application recognizes this labeled response on a
  loopback backend. No separate Flutter preview flag is required. Non-loopback
  clients and release builds reject it.
- The signed-in map shows up to 25 nearest eligible centers around its initial
  midpoint pin, without requesting GPS. Moving the pin requests a new shortlist;
  panning/zooming, tabs and the legend do not. Shelter icons show approved temporary
  centers in local mode; genuine mode keeps its ordinary eligibility rules.
  No distance or nearest claim is made before confirming a location point.
- Changes appear on the next request. Tap **Refresh centers** after saving in
  Admin; no polling, background monitoring, location reset or reassessment occurs.

This first implementation covers sources and evacuation centers only. It does
not enable temporary parameter values, raw Expert System rules, AHP/WLC,
susceptibility data, or new DSS publication bypasses. Those retain their existing
authorized workflows until separately specified and tested.

## One-time setup

In your private `server/.env`, add or change:

```dotenv
FLOODSENSE_LOCAL_TESTING=true
```

Keep `DJANGO_DEBUG=true`, local PostGIS, and the already configured public Mapbox
`pk.` token. The old `FLOODSENSE_ENABLE_LOCAL_CENTER_PREVIEW` setting is not needed
for this workflow and can be false. Never share or commit `.env`.

No new packages, migrations, or seed/import commands are required by this change.
Existing teammates must restart Django and rebuild/relaunch Flutter once; they
must opt in separately in their own private environment. Git transfers code,
not your database rows or superuser account.

## Run the ordinary system

Terminal 1, from the repository root:

```powershell
.\server\.venv\Scripts\python.exe server\manage.py runserver 127.0.0.1:8000
```

Open `http://127.0.0.1:8000/management/`. A local-testing banner confirms that the
**running server** loaded the setting. Use your existing staff account with
source/center add, change and approval permissions; cleanup additionally needs
the corresponding delete permission.

Terminal 2, also from the repository root:

```powershell
.\scripts\run_android_local.ps1
```

The launcher reads the existing private public Mapbox token without printing it,
selects one currently connected authorized phone (preferring wireless mDNS),
forwards port 8000, and runs the main Flutter application against the normal API.
If several phones are connected, use `-DeviceId` with the current ID from:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" devices -l
.\scripts\run_android_local.ps1 -DeviceId 'CURRENT_CONNECTED_DEVICE_ID'
```

It does not pair a disconnected phone. Pair/connect using the current Wireless
debugging pairing and connection ports when necessary; old ports can change.
`-ValidateOnly` checks settings and device selection without launching the app.
The old `run_android_local_center_preview.ps1` remains legacy compatibility only.

## Add and test records

1. In **Sources**, create a source and check **Temporary local test source**.
   Use honest test-team organization/custodian, coverage, permitted use and
   limitations, not an invented agency endorsement. One temporary source can
   support several temporary centers. Existing demonstration sources can be
   edited/reused in local mode; nothing is copied automatically.
2. Select **Save and approve metadata (local approval if temporary)** and confirm.
   This records local review only. Public release stays disabled and the stored
   status remains `DEMONSTRATION`.
3. In **Evacuation centers**, add or edit a temporary record. Choose that source,
   check **Temporary local test record**, assign a supported reference barangay
   and put its coordinate inside that barangay. A meaningful test name is enough.
4. Choose **Save and verify / approve temporary record for testing**, then confirm.
   Or use the combined source + center approval action when the source still
   needs local review. No facility verification date or capacity is invented.
   A saved draft/in-review row does not appear until locally approved.
5. In Flutter, check that shelter icons appear on the signed-in map before any
   location request. Choose a barangay manually to place an approximate
   reference pin inside its boundary, or use **Use my location**, continue after
   the explanation, and confirm the detected barangay. GPS places the pin at
   the acquired coordinate, not at a barangay center. You may also drag the pin
   and confirm the refined point. Reselecting the same barangay after a precise
   confirmed pin/GPS reading must not discard that coordinate.
6. Once a point is confirmed, the nearest returned center has a persistent
   nearest label and a brief visual pulse. Open **Prepare** to inspect the
   nearest center's approximate straight-line distance. When manual selection
   supplied the reference pin, the text must say the distance is from an
   approximate barangay point, not your actual device position. Temporary
   centers remain labeled not real or verified facilities.
7. After an Admin change, tap **Refresh centers**. The current confirmed pin and
   assessment choices remain unchanged. The results reflect the saved records
   on this request, not automatically in real time.

Also check switching from manual selection to GPS and back, dragging a reference
pin to refine it, denied GPS permission with manual fallback, and clearing the
location. Clearing must remove the nearest/distance claim; the initial map
reference pin's shortlist can remain visible. Inactive/review/withdrawn
centers are excluded on the next explicit refresh; the map is not a live feed.
These checks still use the same ordinary source and center rows—no extra tables,
seeded preview records, or parallel application database are needed.

Do **not** approve or reclassify the administrative boundary source to approve a
facility. It provides supported map reference geometry, not facility evidence,
and is excluded from the center source selector. Approved susceptibility data
is not required merely to show administrative reference boundaries. If reference
coverage itself is unavailable, fix its actual geometry/identity problem; do not
invent hazard classifications or alter its source status as a workaround.

## Edit, withdraw and remove

- Temporary record details have **Edit temporary record** and, with delete
  permission, **Remove temporary record**. Edit an approved temporary center
  directly and save + approve again; no special database is involved.
- Editing a temporary source resets its local approval unless you save + approve
  it again. Returning it to review withholds its centers on the next refresh.
- Remove the intended temporary centers first, then their temporary source.
  Cleanup is per-row, requires explicit confirmation and a current revision,
  records an audit entry, and refuses genuine records or a source still used by
  connected records. No cascade or automatic purge is offered.
- Deletion cannot be undone through the portal. Recreate a test record only if
  you still need it. Keep genuine data and restricted agency files untouched.
- When genuine records arrive, enter them with their own genuine evidence and
  normal verification/publication workflow; do not relabel a temporary source
  as official. Set `FLOODSENSE_LOCAL_TESTING=false` and restart Django for normal
  operation. Temporary rows stay excluded even if you have not cleaned them up.

## If results are empty

Check the local banner, the selected source's local approval, the center's local
approval, its supported barangay/coordinate, and the confirmed Flutter coordinate.
The old two in-review test centers will remain in review until you approve them;
this change intentionally does not modify existing records on your behalf.

## Developer verification

Use `scripts/test_operations_isolated.ps1` for backend regression tests when the
ordinary application database role cannot create test databases. Its disposable
PostGIS cluster is automated QA infrastructure only, not the manual testing data
workflow described above. Never run tests against a shared/deployed database.

Latest verification on 5 October 2026: the full backend regression run passed
891 tests, and Flutter passed all 327 tests and analysis. The Mapbox-enabled
Android debug APK built successfully. The earlier Admin forms/details/cleanup
browser layout checks passed at 1440, 390 and 320 px. Django checks,
migration-drift checks and Python lint passed. There is no schema migration.
The phone was not connected during that initial verification. Its subsequent
full relaunch restored Mapbox after the shelter-image PNG correction. The
initial read-only local check found the private local-testing setting enabled,
47 supported barangay boundaries and two temporary evacuation centers still
**in review** (zero eligible centers). Later on 5 October, the owner explicitly
authorized local approval of those same two center rows and their existing
temporary source through the shared approval workflow. The running map API
then returned both centers. No new center/source rows or boundary changes were
made; no facility verification date, capacity or public release was invented.
Tap **Refresh centers** to load this saved state in an already-running app.
Local rows, approvals and settings are not distributed through Git.
