# Stream C nearest-center handoff — superseded baseline

**Status:** Integration completed on 22 September 2026; retained as a historical handoff.

This file originally recorded the missing Stream C dependency before the
nearest-center contract, service, public identifier migration, and HTTP endpoint
existed. Do not use its former inventory as the current repository state.

The authoritative implementation handoff is now:

- `../docs/GPS_STREAM_A_NEAREST_CENTER_DAY_3_HANDOFF.md` for the exact Android
  request, response-envelope, parser, warning, privacy, and error requirements;
- `../server/evacuation/NEAREST_CENTER_CONTRACT.md` for the frozen wire and
  eligibility contract; and
- `../docs/GPS_STREAMS_A_B_DEPENDENCY_BLOCKERS.md` for current completion and
  downstream work.

## Current boundary

Stream C/D Days 1–3 now provide and test
`POST /api/v1/evacuation-centers/nearest/`, the database-backed eligibility and
distance service, the stable public UUID, bounded JSON parsing, safe errors,
no-store headers, request throttling, and no-write behavior.

Stream A now provides the production Flutter HTTP adapter, strict complete-
envelope parsing, mandatory warning presentation, typed client error mapping,
and default-app wiring. The provider returns `NearestCenterResult`, preserving
`centers`, `distance_method`, and `warnings`; backend eligibility, distance
sorting, and result limiting remain server-owned. The full Flutter suite passes
with 175 tests, and the live honest-empty response was verified over the phone-
accessible LAN address. Populated device acceptance still requires authorized,
source-backed center records.
