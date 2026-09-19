# Foreground GPS dependency and adapter installation handoff

**Audience:** FloodSense integration lead, Programmer 2, or a coding agent
assigned to the shared Flutter dependency files.

**Status:** Dependency-independent controller, UI, manifest, and fake-service
tests implemented. Production package adapter and default app activation remain
blocked on the integration-owned dependency files.

This guide is stored under `mobile/` because it concerns one Flutter dependency
handoff and should stay close to the code that consumes it. It deliberately
avoids the integration lead's shared project-planning documents.

## Before editing shared files

Read `AGENTS.md`, the GPS seven-day plan, the consultation decisions, and the
team database/Git workflow. Never read, print, modify, stage, or share
`server/.env` for this task.

From the repository root, run:

```powershell
git status --short --branch
git diff -- mobile/pubspec.yaml mobile/pubspec.lock
```

Stop and coordinate with the current owner if either shared dependency file
already has uncommitted changes. Do not stash, reset, discard, or overwrite
another developer's work automatically.

## Implemented in Stream A ownership

- `ACCESS_COARSE_LOCATION` and `ACCESS_FINE_LOCATION` are declared in the main
  Android manifest. No background or foreground-service location permission,
  service, receiver, worker, stream, or timer was added.
- `LocationController` performs no work at construction or page load. It checks
  service and permission state only after the purpose dialog's explicit
  Continue action.
- The controller supports disabled service, denied permission, permanent
  denial, one-time acquisition, timeout, inaccurate/unavailable readings,
  platform error, cancellation, clearing, reset, and disposal.
- Coordinates exist only in `TemporaryLocationSession`. The UI displays an
  approximate accuracy value but not the latitude or longitude.
- `LocationCard` keeps the existing map pin and selector visible and does not
  call the barangay resolver. That mobile/backend integration remains Day 3.
- Fake-service unit and widget tests require no physical GPS.

## Exact integration-lead dependency change

The integration lead owns `mobile/pubspec.yaml` and `mobile/pubspec.lock`. Add
this direct dependency under `dependencies`:

```yaml
  geolocator: ^14.0.3
```

Keep every existing dependency. Do not run a general dependency upgrade.

Then run from the repository root:

```powershell
Set-Location mobile
flutter pub get
flutter analyze
flutter test
flutter build apk --debug
Set-Location ..
git diff -- mobile/pubspec.yaml mobile/pubspec.lock
git diff --check
git status --short --branch
```

Expected shared-file result:

- `pubspec.yaml` adds only the direct `geolocator` entry;
- `pubspec.lock` records only the dependency graph required for it;
- no unrelated package is deliberately upgraded; and
- no generated build file is staged.

Review both shared-file diffs and the merged Android manifest. It must not
contain `ACCESS_BACKGROUND_LOCATION`, `FOREGROUND_SERVICE_LOCATION`, a location
foreground service, boot receiver, or scheduled worker.

After the dependency commit is available, Stream A must add the production
`LocationService` implementation using only:

- `Geolocator.isLocationServiceEnabled()`;
- `Geolocator.checkPermission()`;
- `Geolocator.requestPermission()` after explicit continuation;
- `Geolocator.getCurrentPosition()` with Android high accuracy and the
  controller's 15-second time limit;
- `Geolocator.openAppSettings()` and `Geolocator.openLocationSettings()` only
  after the corresponding explicit button; and
- typed translation of package exceptions into `LocationFailure`.

Suggested package-to-project mapping:

| Package outcome | FloodSense outcome |
| --- | --- |
| `denied` before this session prompts | `notRequested` |
| `denied` after an explicit prompt | `denied` |
| `deniedForever` | `deniedPermanently` |
| `whileInUse` | `foregroundGranted` |
| Existing `always` grant | Treat as granted, but never request background access |
| Service disabled | `LocationFailureKind.serviceDisabled` |
| Timeout | `LocationFailureKind.timeout` |
| Unacceptable reported accuracy | `LocationFailureKind.inaccurate` |
| No usable position | `LocationFailureKind.unavailable` |
| Safe package/platform failure | `LocationFailureKind.unexpected` |

Return only a project-owned `TemporaryLocation`. Do not expose package types to
controllers or widgets, and do not place coordinates in exception messages.

Do not call `getLastKnownPosition()` or `getPositionStream()`. Once that adapter
exists, pass it to `FloodSenseApp(locationService: ...)`; until then the app
does not show a broken GPS control by default. Tests inject a fake service and
exercise the complete controller/widget flow.

## Adapter activation rule

The production adapter belongs at:

```text
mobile/lib/features/location/geolocator_location_service.dart
```

After its focused tests pass, instantiate it at the normal application
composition point and pass it through the existing injection hook:

```dart
FloodSenseApp(locationService: GeolocatorLocationService())
```

Never request permission from `main()`, `initState()`, application startup,
page loading, or controller construction. `LocationCard` must remain the only
entry to the purpose-and-permission sequence.

## Merged Android manifest check

After building the debug APK, inspect the final merged manifest:

```powershell
$manifest = Get-ChildItem -LiteralPath "mobile\build\app\intermediates\merged_manifests" -Recurse -Filter AndroidManifest.xml -File | Select-Object -First 1
$manifest.FullName
Select-String -LiteralPath $manifest.FullName -Pattern "uses-permission|service|receiver"
Select-String -LiteralPath $manifest.FullName -Pattern "ACCESS_BACKGROUND_LOCATION|FOREGROUND_SERVICE_LOCATION|RECEIVE_BOOT_COMPLETED|BOOT_COMPLETED"
```

The final command must return no match. This task permits coarse and fine
foreground location only. It does not permit background location, a location
foreground service, a boot receiver, scheduled work, or passive tracking.

## Emulator acceptance checks

Use emulator coordinates, never real user coordinates, and verify:

1. App startup does not request permission.
2. **Use my location** displays the purpose/privacy explanation first.
3. Cancelling performs no permission request.
4. Continuing requests foreground permission once.
5. Approximate permission either meets the policy or produces the safe
   inaccurate/manual-fallback state.
6. Denial keeps the map pin and selector available.
7. Permanent denial does not open app settings automatically.
8. Disabled services do not produce repeated prompts.
9. Success shows the temporary indicator without exact coordinates.
10. Clear, reset, flow exit, and app restart remove the coordinate.
11. No resolver request is performed automatically on Day 2.
12. Rainfall/scenario selections remain unchanged.

## Privacy and security review

Reject the adapter if it introduces:

- coordinate storage in preferences, secure storage, SQLite, files, database
  models, profiles, assessments, analytics, audit events, or crash breadcrumbs;
- coordinate output through `print`, `debugPrint`, loggers, or exceptions;
- `getLastKnownPosition()` or `getPositionStream()`;
- automatic retries or repeated permission prompts;
- automatic settings launch;
- background execution or permissions; or
- susceptibility, alert, forecast, route, or safety decisions.

## Day 3 contract readiness

The mobile request will serialize `TemporaryLocation.latitude` as `latitude`
and `TemporaryLocation.longitude` as `longitude`. GeoDjango then constructs
`Point(longitude, latitude, srid=4326)`. No coordinate belongs in a query
parameter.

The planned strict response model must map every frozen server state without a
default success assumption:

| Server state | Mobile meaning |
| --- | --- |
| `RESOLVED` | Present the safe barangay identity for confirmation |
| `OUTSIDE_BACOOR` | Keep manual correction available; do not force a barangay |
| `AMBIGUOUS_BOUNDARY` | Explain boundary uncertainty and require manual confirmation |
| `UNAVAILABLE` | Explain that the controlled layer cannot resolve the point |

Day 2 deliberately does not add the API-client method, perform an automatic
resolver call, center the map, or confirm a detected barangay. Those are Day 3
integration tasks after the proposed contract receives team approval.

## Required completion report

The developer or agent completing this handoff must report:

- exact `pubspec.yaml` and lockfile changes;
- adapter and application-composition files changed;
- merged-manifest permissions found;
- exact analysis, test, and build results;
- emulator cases exercised;
- confirmation that coordinates are neither logged nor persisted;
- pre-existing versus introduced warnings; and
- whether the resolver contract is approved for Day 3.

Do not commit or push unless the responsible user explicitly requests it.
