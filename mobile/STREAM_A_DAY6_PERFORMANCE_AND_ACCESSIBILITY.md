# Stream A Day 6 performance and accessibility evidence

**Measured:** 20 September 2026  
**Scope:** Provider-independent mobile location, map, assessment and center UI

## Preserved behavior

- GPS remains an explicit, one-shot foreground action.
- The purpose and temporary-use explanation appears before a platform prompt.
- Manual pin and barangay controls remain available.
- Rainfall choices and confirmed barangay state survive unrelated center
  failures and orientation changes.
- Location and center operations do not run susceptibility inference.
- Center distance remains approximate straight-line distance; no route, live
  capacity, operational status or evacuation instruction is presented.

## Measurement and changes

The reference map previously rebuilt and allocated its complete polygon list
when an unrelated scenario selection changed. A widget-level identity
measurement reproduced the allocation: the polygon list before and after the
scenario change was a different instance. The map state now caches the
immutable polygons by reference-area list and confirmed-area code. The same
measurement now proves the list instance is reused while still invalidating
when either input changes.

No frame-time or production-device speedup is claimed. The evidence is limited
to eliminating one repeat transformation in the Flutter widget test
environment.

Additional Day 6 regression instrumentation proves:

- one GPS acquisition and one center request survive portrait-to-landscape
  layout changes without duplication;
- delayed assessment/reference loads cannot retain data after controller
  disposal;
- an existing coordinate is reused for explicit retry rather than reacquiring
  GPS; and
- stale location and center responses remain invalidated by their controllers.

## Responsive and accessible presentation

Automated widget checks cover a 320 x 568 logical-pixel viewport at 2.5x text,
a 320 x 640 portrait viewport at 2x text, and a 640 x 320 landscape transition.
The permission-purpose dialog is scrollable. Long synthetic center names,
addresses, barangays and limitations remain in the scrollable page without a
render overflow.

Center result status is a live region. A center card exposes its name,
approximate distance, verification date, barangay identity, address, source and
limitations in one ordered semantic description. Map controls retain at least
48 x 48 logical-pixel targets. Temporary-location and center markers have
distinct labels and icons, while the center list provides a non-map
alternative.

These automated checks are not a claim of full WCAG, screen-reader or physical-
device certification.

## Remaining integration limitation

The production nearest-center endpoint and frozen Stream C contract are still
absent. Fake providers can verify bounded UI/controller behavior, but they
cannot measure live response parsing, real endpoint latency, real result caps,
or Admin-to-API-to-device behavior. See
`STREAM_C_NEAREST_CENTER_HANDOFF.md` and
`../docs/GPS_STREAMS_A_B_DEPENDENCY_BLOCKERS.md`.
