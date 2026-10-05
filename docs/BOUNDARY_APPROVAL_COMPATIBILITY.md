# Bacoor boundary rename and approval compatibility

Owner-authorized team implementation — 5 October 2026. Not adviser approval or
City endorsement; susceptibility and facility workflows remain independent.

## What changed

- Dataset identity follows the existing `PSGC_0402103000` City record and its
  source relationship. Neither display name nor local source ID is hardcoded.
- Enabled valid administrative geometry and its public agency source may be
  pending or internally approved. Mixed barangay statuses are supported.
- Map, pin/GPS/manual matching and evacuation lookup use the same identity.
  Complete 47-barangay and existing geometry/identity checks remain.
- Resolver metadata reports stored geometry/source statuses. Flutter accepts
  both and does not describe approved boundaries as pending or City-verified.
- Source metadata approval/review remains permission-checked, confirmed and
  logged. The existing pending geometry release may be retained during approval;
  ordinary unpublished-source approval still does not publish it.
- Boundary provenance is excluded from facility forms, verification and public
  center results even after rename/approval.
- Explicit imports reuse existing rows, preserve source metadata/review/release
  and enabled states, and refuse to overwrite reviewed geometry or restore
  retired/restricted records. They do not manufacture review decisions.

No record approval, deletion, reseed or import is performed by this code update.
The four demo zones, temporary centers, and provisional susceptibility rows are
unchanged. Original derivation/citations remain part of the provenance.

## Run after pulling

No new packages, migration, seed or import is required for this update. Git
shares these code changes, not local database approvals or rows.

Restart Django using the normal command from the repository root:

```powershell
.\server\.venv\Scripts\python.exe server\manage.py runserver 127.0.0.1:8000
```

Stop the previous Flutter run with `q`, then relaunch on the authorized phone:

```powershell
.\scripts\run_android_local.ps1
```

The helper retains the existing private Mapbox-token setup and current device
selection. It does not request location automatically or change camera height.

## Manual acceptance

1. Open Admin Map data: existing barangays and current stored statuses appear.
2. Open Flutter: all 47 boundaries load; shelter shortlist remains available.
3. Choose a barangay, drag the pin or explicitly acquire GPS; confirm the match.
4. A source rename must not change these results. Internally approving geometry
   must not turn the susceptibility preview into an approved flood assessment.
5. Source unpublishing, restriction, retirement, disabled/invalid geometry, or
   missing required rows must withhold resident use rather than guess a match.
6. Keep temporary centers explicitly local-only; do not use the boundary source
   as a facility source. Ordinary production still excludes temporary centers.

Restart/refresh explicitly to see administrative changes. There is no polling.

## Verification — 5 October 2026

- Full isolated backend suite: 912 passed. Subsequent source-list identity
  optimization and four added regression cases: 68 focused tests passed.
- Full Flutter suite: 342 passed; Flutter analysis reported no issues.
- Mapbox-configured Android debug APK built successfully. This is a build check,
  not a claim that the revised app has been installed or visually tested on the phone.
- Django system check, migration dry run and changed-file lint passed; no schema
  changes were detected.
- Read-only checks of the running local API returned 47 boundaries, a resolved
  barangay with the actual pending-geometry / approved-source statuses, and both
  existing temporary centers through the normal local map endpoint.
- Admin template wording/layout checked in the browser with unsaved synthetic
  objects because the live Admin page required sign-in. No account or application
  row was created for this check.

No pull, push, commit, application migration, approval, deletion or data import
was performed. Teammates only need to restart Django and rebuild/relaunch Flutter
after these changes are committed and pulled; their own database rows stay local.
