# Stream C nearest-center contract handoff

For the complete Days 1-4 dependency inventory and downstream impact, see
`../docs/GPS_STREAMS_A_B_DEPENDENCY_BLOCKERS.md`.

Day 4 Stream A cannot add a production HTTP adapter until Stream C publishes
and tests its frozen nearest-center contract.

## Checked repository state

- The conceptual route is `POST /api/v1/evacuation-centers/nearest/`.
- `server/evacuation/views.py` does not implement that route.
- `server/evacuation/` has no nearest-center serializer, service, URL module, or
  endpoint contract document.
- `server/config/urls.py` does not expose an evacuation API route.
- `EvacuationCenter` has no approved stable public identifier distinct from its
  database row ID.
- No checked-in contract defines exact request keys, optional limit bounds,
  response keys, result states, distance unit, or error shapes.

## Stream A boundary completed

The mobile UI now consumes `NearestCenterProvider`, which accepts an in-memory
latitude and longitude and returns validated, public presentation data in the
provider's original order. There is no production provider, wire parser, URL,
automatic retry, mobile eligibility filter, or client-side distance sort. The
normal app displays an honest contract-unavailable state after a coordinate-
bearing location is confirmed. Deterministic fakes cover the UI and controller.

## Required from Programmer 2

Freeze and test:

1. Exact JSON request keys and the approved optional result-limit default and
   bounds.
2. Exact success, empty, validation, timeout-facing, and service-error shapes.
3. A stable public center identifier that is not an unapproved raw row ID.
4. Public barangay identity fields compatible with the geography convention:
   the 10-digit PSGC value derived from `GeographicArea.code` values shaped as
   `PSGC_##########`, plus the public label.
5. Latitude/longitude, approximate distance and unit, verification date, safe
   source attribution, and public limitations field names and nullability.
6. Backend-only filtering for verified, approved, publicly releasable records;
   stable nearest-first ordering; bounded results; malformed-record exclusion;
   and no location-history writes.
7. An allowlist that excludes contact information, internal notes, restricted
   provenance, approval comments, live occupancy, unverified capacity,
   susceptibility data, and Expert System data.

After that contract lands, Stream A can add one `NearestCenterProvider` HTTP
adapter and strict JSON parser without changing the location controller or
resident widgets.
