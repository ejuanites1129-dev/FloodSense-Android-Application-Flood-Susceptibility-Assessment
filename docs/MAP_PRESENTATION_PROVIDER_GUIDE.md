# FloodSense map presentation provider guide

This guide covers the optional Mapbox presentation layer for the resident
Flutter app and custom Django Admin portal. It does not change the Expert
System, scenario inputs, susceptibility meaning, geographic records, resident
location lifecycle, evacuation-center eligibility, or publication governance.

## Mapbox-first default and supported surfaces

- `mapbox` is the default provider setting for supported Android/iOS and Admin
  surfaces.
- Without a valid public `pk.` token, every surface uses the existing
  OpenStreetMap presentation as a safe fallback.
- The stable Mapbox Flutter SDK is enabled only on Android and iOS. Flutter web
  and desktop use OSM.
- The Django Admin may use pinned Mapbox GL JS `v3.30.0`; OpenLayers/OSM remains
  loaded as an in-page runtime fallback.
- Every map starts in an overhead 2D view. The perspective toggle appears only
  when `FLOODSENSE_MAP_3D=true`.
- Neutral 3D buildings are basemap context. Flood polygons are never extruded.

The FloodSense scenario palette is consistent across renderers:

| Meaning | Color |
| --- | --- |
| Low | `#2E9E5B` |
| Moderate | `#E8B923` |
| High | `#E2691B` |
| Very high | `#C0392B` |
| Uncertain / insufficient data | `#8791A1` |

Versioned backend `map_color` values remain authoritative for classified
scenario results. Administrative boundaries do not acquire a susceptibility
meaning merely because the presentation provider changes.

## Django Admin configuration

Keep `server/.env` private and ignored. OSM requires no additional setting:

```dotenv
FLOODSENSE_MAP_PROVIDER=mapbox
MAPBOX_ACCESS_TOKEN=
FLOODSENSE_MAP_3D=false
```

For an authorized local Mapbox run:

```dotenv
FLOODSENSE_MAP_PROVIDER=mapbox
MAPBOX_ACCESS_TOKEN=<your-restricted-public-pk-browser-token>
FLOODSENSE_MAP_3D=true
```

Restart Django after changing these values. `osm` explicitly disables Mapbox.
`auto` and `mapbox` both require a token beginning with `pk.`; missing,
malformed, and `sk.` values are never embedded in HTML and select OSM instead.

The browser token is necessarily visible to the browser. Restrict its allowed
URLs and scopes in Mapbox. Never put an `sk.` secret token in `server/.env`, a
template, a Dart define, source control, screenshots, logs, or test fixtures.

## Flutter Android configuration

Run from `mobile/`:

```powershell
flutter pub get
flutter run --dart-define=FLOODSENSE_MAP_PROVIDER=mapbox `
  --dart-define=MAPBOX_ACCESS_TOKEN=<your-restricted-public-pk-token>
```

To expose the optional perspective control for a rehearsal:

```powershell
flutter run --dart-define=FLOODSENSE_MAP_PROVIDER=mapbox `
  --dart-define=MAPBOX_ACCESS_TOKEN=<your-restricted-public-pk-token> `
  --dart-define=FLOODSENSE_MAP_3D=true
```

Dart defines are compile-time values: rebuild or restart after changing them.
Do not use the public token for unrelated Mapbox APIs. The current stable mobile
dependency resolves release artifacts without a repository download token. If
a future explicitly authorized snapshot build requires `SDK_REGISTRY_TOKEN`,
store that secret only in the individual developer's user Gradle configuration
or environment—not in this repository or `server/.env`.

Flutter web deliberately exercises the OSM path. The explicit rehearsal command
is:

```powershell
flutter run -d chrome --web-hostname localhost --web-port 3000 `
  --dart-define=FLOODSENSE_MAP_PROVIDER=osm
```

## Teammate update after pulling

The only new runtime dependency is the pinned Flutter Mapbox package. From
`mobile/`, run `flutter pub get`, then rebuild the app. Restart Django after
adding or changing the private Admin map environment settings. Backend Python
dependencies are unchanged.

No separate Mapbox executable, Android archive, or JavaScript package needs to
be downloaded manually. Flutter resolves `mapbox_maps_flutter` from
`pubspec.lock`, and the Admin loads its pinned Mapbox GL JS assets at runtime.
The ordinary Flutter/Android prerequisites in the Windows setup guide still
apply.

There are no model changes, migrations, seed steps, or data imports for this
presentation upgrade. Teammates must not run a shared-database migration or an
official-data import for this work.

## PC and USB-device rehearsal

Start the local backend from the repository root and keep it running:

```powershell
server\.venv\Scripts\python.exe server\manage.py runserver 127.0.0.1:8000
```

The PC Mapbox presentation is then available in the custom Admin map page at
`http://127.0.0.1:8000/management/map-data/`. The resident Flutter browser
preview remains an intentional OSM fallback and can be started from `mobile/`:

```powershell
flutter run -d chrome `
  --dart-define=FLOODSENSE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

For a physical Android phone connected with USB debugging, find its current ID
with `flutter devices`. Forward the phone's port 8000 to the PC backend with the
Android SDK `adb` executable, replacing `<device-id>`:

```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb -s <device-id> reverse tcp:8000 tcp:8000
```

Then launch the native Mapbox renderer from `mobile/`:

```powershell
$mapboxPublicToken = Read-Host "Paste the restricted public Mapbox pk token"
try {
  flutter run -d <device-id> `
    --dart-define=FLOODSENSE_API_BASE_URL=http://127.0.0.1:8000/api/v1 `
    --dart-define=FLOODSENSE_MAP_PROVIDER=mapbox `
    --dart-define="MAPBOX_ACCESS_TOKEN=$mapboxPublicToken" `
    --dart-define=FLOODSENSE_MAP_3D=true
} finally {
  Remove-Variable mapboxPublicToken -ErrorAction SilentlyContinue
}
```

The USB reverse rule lasts only while the device/ADB session remains available;
repeat it after reconnecting the phone. Do not commit the token or hard-code one
developer's device ID. If a browser-URL-restricted token is rejected by the
native SDK, create a separate restricted public token appropriate for the
Android rehearsal.

## Failure and rollback rehearsal

For both resident and Admin maps, verify:

1. No token: the OSM map loads and all lists/forms remain usable.
2. Invalid or `sk.` token: no token appears in rendered HTML and OSM loads.
3. Restricted valid `pk.` token: Mapbox loads on the supported surface.
4. Block Mapbox network requests or use a revoked test token: a generic message
   appears and the same surface switches to OSM without exposing error details.
5. Disable JavaScript in Admin: the server-rendered record list, details,
   coordinate values, and forms remain usable.
6. Enable 3D: the map still starts overhead, the user explicitly toggles the
   moderate perspective, buildings remain neutral, and hazard polygons stay
   flat.
7. Confirm Mapbox attribution/wordmark or OSM attribution remains visible.

The provider's attribution and telemetry controls remain enabled; FloodSense
does not hide or replace them. Public internet is expected for either basemap.
If basemap networking fails, the existing API geometry and server-rendered
content remain the source of FloodSense meaning, while the client reports a
neutral provider failure.

Rollback is configuration-only: set `FLOODSENSE_MAP_PROVIDER=osm` (or remove the
public token) and rebuild/restart the relevant client. No database migration,
seed, official-data import, or Expert System change is involved.

## Verification commands

```powershell
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe -m pytest server\admin_portal -q
Set-Location mobile
flutter analyze
flutter test
flutter build apk --debug
```

Use only an isolated Django test database. Do not run migrations, seeds, or
imports against shared/deployed databases as part of this presentation test.

## Known release-rehearsal limits

- No token or credential is committed, so a teammate with a restricted public
  token must complete the live Mapbox visual/network acceptance steps above.
- The stable Flutter package is used only for Android/iOS. Its current Android
  plugin applies Kotlin in a way that Flutter warns will require an upstream
  compatibility update in a future Flutter release; the present debug APK
  remains buildable.
- This change does not add, approve, or publish detailed MGB susceptibility
  polygons. The maps render only geographic and scenario data already returned
  by the existing reviewed API or Admin view.
- Mapbox Standard supplies general street/place context. FloodSense overlays,
  labels, controls, and disclaimers remain application-owned and do not alter
  scientific classifications or governance.
