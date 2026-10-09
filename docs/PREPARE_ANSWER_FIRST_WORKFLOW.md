# Answer-first Prepare — team handoff

Authorized by the project owner on 9 October 2026. This changes resident
presentation, not the scientific methodology or agency approval status.

## Resident workflow

1. Complete the existing explicit scenario/location assessment.
2. Open Prepare or View Preparedness. A compact scenario summary and up to three
   existing preparation actions appear without answering household questions.
3. Optionally select Tailor for my household. Only the current question,
   options, navigation and concise status are in the main reading view.
4. Close household check to return to Prepare without clearing progress. Resume
   to continue or inspect the outcome. Reset answers separately when wanted.
5. Expand nearby centers, educational references or sources only as needed.

The first three actions follow existing API content ordering, not a newly
invented priority score: use the selected eligible flow's BEFORE/ALWAYS household
blocks when available, otherwise the completed assessment's guidance items. The
remaining actions remain accessible. An unavailable optional household flow does
not suppress eligible assessment guidance. If neither contains eligible actions,
the UI explicitly says so; it does not generate substitute emergency advice.

The structured branch contract and published content are unchanged. Do not skip
questions by supplying fabricated answers. Answers and progress remain in memory
only and reset when the assessed context changes. Generation checks reject late
responses for previous scenarios. Returning to a prior question restores its
selection without changing the susceptibility classification.

## Presentation and resource boundaries

- Prepare prefers an 84% reading-panel height, still capped by content and the
  existing 90% maximum. The map/camera remain retained and draggable.
- Use one scrolling surface. Optional household questions return to the top
  after navigation; narrow/enlarged-text controls can stack vertically.
- The center section is collapsed initially. Its summary preserves approximate
  straight-line distance, coordinate origin and safety/availability limits.
- Every test facility remains prominently marked LOCAL TEST / not a real
  facility. Real verification is not an opening/occupancy/safety guarantee.
- List each center once. Address, PSGC, evidence and unique limitations are in
  its Details and source disclosure. Show on map remains an explicit action.
- One explicit refresh uses the confirmed-location center controller, or the
  existing map-catalog fallback if a nearest-center refresh is unavailable.
  Expanding sections, changing tabs and answering questions trigger no center
  refresh or GPS access.
- During/after-flood material remains educational reference, not live condition
  inference. All full source, version, review, attribution and limitation details
  remain available through disclosures and Profile → Data Sources.

## Teammate setup and verification

No new package, database migration, seed, agency import or parameter activation
is required. Rebuild/relaunch Flutter normally after receiving the code. Existing
local data remains local; Git does not synchronize database rows or approvals.

From `mobile`:

```powershell
flutter analyze
flutter test
flutter build apk --debug
```

Focused regression coverage is in `test/preparedness_dashboard_test.dart`, with
the shell, multi-step and center-startup integration tests updated for the new
optional entry. The existing full structured-guide view remains available as a
reference renderer; the resident entry points use the answer-first dashboard.

Optional rendered widget QA uses synthetic test content, not agency data:

```powershell
$env:DSS_VISUAL_QA_FONT_DIRECTORY = 'C:/Windows/Fonts'
$env:DSS_VISUAL_QA_ICON_FONT = 'C:/Users/YourName/development/flutter/bin/cache/artifacts/material_fonts/materialicons-regular.otf'
flutter test --dart-define=DSS_VISUAL_QA=true test/preparedness_dashboard_test.dart
```

Images are generated under ignored `tmp/prepare-dashboard-qa/`. Replace the
Flutter SDK path with the actual local installation. Ordinary tests need no
visual-QA variables or fonts.

This does not adopt the review-only AHP/WLC proposal, change expert rules or
add live monitoring, forecasting, evacuation orders, persistence or an offline
operating mode.
