# Day 1 foreground-location foundation

**Status:** Implemented design scaffold; proposed for team review  
**Scope:** Stream A Day 1 only. No permission prompt, GPS read, package adapter,
manifest permission, API call, or new user-interface control is active.

## Current mobile inventory

- `AssessmentScreen` is the single assessment entry screen. It owns and
  disposes an `AssessmentController`.
- `AssessmentController` uses the existing `ChangeNotifier` pattern. It keeps
  scenario, selected area, result, temporary manual-pin coordinate, and request
  state in memory.
- `DynamicMapCard` supports manual pin placement. A tap calls
  `AssessmentController.placePin`, which sends the coordinate to the existing
  fictional-demonstration `resolve-point` endpoint. It is not device GPS or the
  proposed Bacoor barangay resolver.
- `ZoneSelector` remains the non-map fallback. `ReferenceBoundaryMapCard` shows
  the neutral 47-barangay reference layer separately from fictional assessment
  polygons.
- Scenario state consists of an intensity and duration. Changing the location
  does not change either selection. Selecting an area clears stale point and
  assessment results.
- `FloodSenseApi` is the injectable client interface. `FloodSenseApiClient`
  uses JSON over `http`, maps validation/connectivity/service/malformed-response
  failures to `ApiException`, and applies a 15-second network timeout.
- Models use strict `fromJson` factories and `ModelParsingException`. Unknown
  assessment or point-resolution states remain neutral rather than inventing a
  result.
- No preferences, SQLite, Hive, analytics, crash-reporting, or location package
  is declared. No current code serializes `pinCoordinate` or an assessment
  controller.
- Checked-in SDK constraint: Dart `^3.13.2`. Verified local toolchain:
  Flutter 3.47.4 and Dart 3.13.3. Android SDK values are inherited from this
  Flutter SDK: min 24, target 36, compile 36. The project uses Java 17,
  Android Gradle Plugin 9.1.0, Kotlin 2.4.0, and Gradle 9.3.1.
- Existing tests cover API transport/errors, strict model parsing,
  `ChangeNotifier` request races, manual-pin behavior, maps, accessibility, and
  assessment widgets. `location_foundation_test.dart` now covers the Day 1
  service policy, lifecycle, and state invariants.

## Location service contract

`lib/features/location/location_service.dart` defines an adapter boundary for:

1. checking whether device location services are enabled;
2. checking permission without prompting;
3. requesting foreground permission only after an explicit user continuation;
4. opening app or device-location settings after the relevant user action;
5. acquiring exactly one current position with a supplied policy;
6. returning typed permission and acquisition failures; and
7. clearing adapter state and disposing resources.

The initial policy is a 15-second timeout and maximum reported horizontal
accuracy of 50 meters. Day 2 may tune those values after emulator/device tests,
but must treat a worse fix as inaccurate and preserve manual selection. The
contract deliberately has no stream API, last-known-position API, background
mode, timer, or tracking service.

`TemporaryLocationSession` is the sole proposed owner of a GPS coordinate. It
has no serialization API or persistence dependency. Call `clear` for the user
clear action, `reset` on assessment reset, and `dispose` when the owning flow is
disposed. It must never be added to preferences, SQLite, assessment requests,
profiles, analytics, audits, logs, crash breadcrumbs, or screenshots. Process
restart therefore cannot restore it.

## State contract

Manual pin and barangay selection remain available in every state.

| Phase | Visible meaning | Additional actions | Retry | Coordinate may exist | Clear rule |
| --- | --- | --- | --- | --- | --- |
| `initial` | Location has not been requested | Explain purpose | No | No | Already empty |
| `purposeExplanation` | Explain boundary lookup and temporary use | Continue or cancel | No | No | Cancel returns empty |
| `serviceDisabled` | Android location is off | Open location settings | Yes | No | Already empty |
| `permissionDenied` | Permission was denied | Explicitly try again | Yes | No | Already empty |
| `permissionDeniedPermanently` | Android will not show another prompt | Open app settings | No | No | Already empty |
| `acquiring` | One foreground reading is pending | Cancel | No | No | Cancel/dispose clears adapter state |
| `acquired` | Temporary coordinate is ready; no result is implied | Resolve or clear | No | Yes | Clear/reset/dispose |
| `inaccurateOrUnavailable` | No acceptable fix was retained | Try again | Yes | No | Reject and clear the bad fix |
| `resolverFailure` | Network/boundary lookup failed | Retry lookup or clear | Yes | Yes | Clear/reset/dispose |
| `malformedResponse` | Server response was not trusted | Retry or clear | Yes | Yes | Never assume a barangay; clear/reset/dispose |
| `recoverableError` | A safe retry is possible | Retry or clear | Yes | Yes | Clear/reset/dispose |
| `cleared` | Temporary coordinate was removed | Start again | No | No | Already empty |

The executable state model rejects coordinates in phases that are not allowed
to hold one. Resolver and malformed-response failures may retain the in-memory
coordinate only to support an explicit retry; manual correction or flow exit
must clear it.

## Draft purpose and fallback copy

- Purpose: “FloodSense can use one temporary location to look up a likely
  Bacoor barangay. This lookup does not determine flood susceptibility.”
- Privacy: “Your coordinate is used only during this flow and is not retained.
  You can use the map pin or barangay selector instead.”
- Denied: “Location permission was not granted. You can try again or choose a
  location manually.”
- Permanently denied: “Location permission is blocked for FloodSense. You may
  enable it in Android app settings, or choose a location manually.”
- Service off: “Device location is turned off. Enable it in Android settings,
  retry, or choose a location manually.”
- Inaccurate/unavailable: “FloodSense could not get a reliable location. Try
  again, place a temporary map pin, or select a barangay.”

This is product-copy scaffolding, not legally approved terms or privacy text.
It does not claim address verification, live conditions, safe routing,
emergency service, tracking, or a GPS-only susceptibility result.

## Package evaluation and integration request

Recommend `geolocator: ^14.0.3` for the future production adapter. Pub.dev lists
14.0.3 as the current stable package, requiring Dart 3.5; its changelog requires
Flutter 3.29+ for the 14.x line. FloodSense's verified Dart 3.13.3, Flutter
3.47.4, and compile SDK 36 meet those declared floors. The package exposes
service checks, permission check/request states, a one-shot current-position
API, accuracy settings, time limits, and settings links, which map cleanly to
the interface without using its optional position streams.

Authoritative references:

- <https://pub.dev/packages/geolocator>
- <https://pub.dev/packages/geolocator/changelog>
- <https://developer.android.com/develop/sensors-and-location/location/permissions/runtime>

The Day 2 handoff is split by the existing ownership rules:

1. The integration lead adds `geolocator: ^14.0.3` to the shared
   `pubspec.yaml`, reviews the lockfile, and runs dependency/build verification.
2. Stream A adds only `ACCESS_COARSE_LOCATION` and `ACCESS_FINE_LOCATION` to
   the main Android manifest (Android 12+ requires requesting both together
   when precise access is offered) and implements the adapter.
3. Neither owner adds `ACCESS_BACKGROUND_LOCATION`, foreground-service
   permission, a foreground service, or a position-stream subscription.
4. Together they run dependency resolution, analysis, tests, and a debug APK
   build to confirm the current AGP/Gradle combination before merging.

Approximate-only permission must remain a supported outcome. If its reported
accuracy does not satisfy the policy, show the inaccurate state and manual
fallback rather than pressuring the user to grant precise access.
