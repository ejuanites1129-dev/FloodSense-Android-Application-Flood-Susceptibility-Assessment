# FloodSense Consultation Decisions and System Boundaries

**Current decision record:** 17 September 2026  
**Official title:** FLOODSENSE: AN ANDROID-BASED EXPERT SYSTEM FOR FLOOD
SUSCEPTIBILITY ASSESSMENT AND PRE-EVENT PREPAREDNESS IN BACOOR CITY

## Purpose and authority

This document turns the system discussion in `FILES/data gathered/TA
consultation Transciption.pdf` into implementation guidance for researchers,
developers, and coding agents. It deliberately separates:

1. feedback stated by the thesis adviser during the consultation;
2. the research team's later scope decision; and
3. matters that still require data, methodology, or adviser confirmation.

This distinction is essential. The consultation suggested automatic and
background behavior, but the research team later decided not to implement
background timers or real-time monitoring because the approved concept is a
scenario-based assessment. This document records that as the **current team
decision**, not as a claim that the adviser already approved the change.

For implementation work, this decision record supersedes conflicting feature
descriptions in older day guides, diagrams, mockups, and demonstration
instructions. The original transcript remains the primary record of what was
said during the meeting.

## Current system boundary

FloodSense is a **scenario-based, pre-event decision-support application**. A
user supplies or confirms a hypothetical rainfall scenario and a supported
location. The backend evaluates that scenario using the fixed, documented
inference method and eligible stored knowledge, then returns an explainable
susceptibility result and separately sourced preparedness guidance.

FloodSense is not currently:

- a real-time rainfall or water-level monitoring platform;
- a continuously running background service or timer;
- an official flood forecast, warning, or evacuation-order service;
- a live center-occupancy or emergency-dispatch system;
- an autonomous alert generator;
- a road-safety or route-safety authority; or
- a machine-learning system that retrains itself from new records.

No developer or coding agent may add those behaviors merely because they appear
in the consultation transcript or an older diagram. A documented research-scope
revision and corresponding privacy, methodology, data, and testing decisions
would be required first.

## Decisions derived from the system discussion

### 1. Scenario interaction, not background monitoring

The adviser asked for fewer user actions and described automatic assessment,
hourly monitoring, background timers, and alerts. The team accepts the usability
goal of reducing unnecessary taps, but rejects continuous monitoring for the
current scope.

Current implementation direction:

- keep rainfall inputs explicitly described as hypothetical scenario values;
- let the user confirm a scenario and supported location;
- calculate or refresh the result within that active scenario flow;
- allow a guided, step-based interface instead of one excessively long page;
- never imply that the selected values describe current Bacoor conditions; and
- do not run a timer, poll rainfall in the background, or issue live alerts.

An interface may update promptly after the user changes a scenario, but that is
not permission to convert the application into a real-time monitor.

### 2. Fixed inference method and protected knowledge

The adviser explicitly objected to ordinary administrators seeing and changing
expert rules because they did not create the research algorithm. The current
governance decision is:

- the inference method is fixed by the research methodology and application
  code;
- raw rules, rule conditions, conflict resolution, and algorithm behavior are
  not editable in the custom ordinary-Admin portal;
- the technical Django Admin may retain developer access for controlled local
  testing, migrations, and research maintenance, but that is not the intended
  operational interface or permission model;
- any future change to the algorithm or rule knowledge requires research review,
  validation, versioning, tests, and explicit authorization; and
- hiding a button is insufficient - backend authorization must also prevent the
  unauthorized operation.

### 3. Administrators manage validated parameters and data, not algorithms

The adviser described CSV/Excel data exchange and new parameter values that may
change scenario outputs without changing the algorithm. Therefore, the custom
portal may eventually expose only controlled workflows for:

- authorized scenario parameters and reference values;
- geographic attributes and supported-area data;
- source, version, unit, period, status, and validation metadata;
- preview, validation, review, approval, activation, and rollback; and
- safe import/export where the exact direction and schema have been confirmed.

Every accepted parameter change must be source-backed, validated, versioned,
auditable, and reversible. An administrator must not type an arbitrary threshold
that silently changes conclusions.

The transcript uses “export” while also describing administrators supplying new
data. The exact requirement - import, export, or both - remains unresolved and
must not be guessed during implementation.

### 4. DSS guidance may be maintained separately

The adviser identified preparedness guidance as content that administrators may
edit, with the expected source coming from BDRRMO or another authorized
custodian. Accordingly:

- guidance is separate from susceptibility classification;
- editing guidance must never change the Expert System result;
- guidance requires provenance, status, review, and publication controls; and
- invented emergency instructions must not be presented as official advice.

### 5. Location and privacy

The adviser expected the application to identify or use the user's location and
to present terms/privacy information. The present implementation uses an
in-memory temporary map pin and does not continuously track or persist location.

Current requirements:

- explain why location is requested before any future device-location access;
- request platform permission only when the corresponding feature exists;
- provide terms/privacy information before collecting personal or precise
  location data;
- minimize retention and do not save coordinates without a justified,
  documented purpose; and
- keep manual map selection as a safe fallback unless the approved design later
  requires device GPS.

### 6. Water-level and rainfall-station datasets are data-dependent

The consultation discussed tandem water-level and automated-rainfall-gauge
records. At that time the team had not yet inspected the supplied dataset or
defined how those variables would affect the method.

Therefore:

- receiving a dataset does not automatically make it an input to the algorithm;
- first document its fields, units, time resolution, spatial coverage, missing
  values, datum/zero reference, license, and limitations;
- then obtain methodological justification for how it affects susceptibility;
- validate any resulting parameter or formula with the appropriate expert; and
- until that work is complete, do not invent a formula or claim live use.

### 7. Data and map safety

- OpenStreetMap is only a background basemap; it is not flood-susceptibility
  knowledge.
- The 47-barangay boundary dataset may identify administrative areas but does
  not assign susceptibility by itself.
- The downloaded MGB layer remains provisional until source, scope, processing,
  interpretation, and permission are reviewed.
- DOST data must follow its EULA and data-sharing conditions.
- Fictional demonstration data must remain visibly labeled and separated from
  approved records.
- If evidence is insufficient, return an explicit limitation or insufficient-
  data state rather than fabricating a class.

## Items requiring confirmation

The following are not settled merely by this document:

1. Whether the adviser accepts a user-triggered scenario flow instead of the
   proposed background automatic monitoring.
2. Whether device GPS is required, optional, or replaced by manual pin/barangay
   selection.
3. Whether assessment should run immediately after the final scenario choice or
   after an explicit confirmation button.
4. How water-level and station data enter the research method, if at all.
5. The validated values, units, thresholds, and owners of editable parameters.
6. Whether the Admin requirement is CSV import, CSV export, Excel support, or a
   combination of them.
7. Who may review, approve, activate, roll back, and publish each data type.
8. Whether alerts or notifications are removed entirely or deferred to a later,
   separately approved scope.

Until confirmed, implementations must choose the safer scenario-based behavior
and label the unresolved feature rather than inventing a scientific or
operational rule.

## Effect on the Admin web application

| Admin area | Ordinary administrator capability | Explicit restriction |
| --- | --- | --- |
| Dashboard | View truthful status and review summaries | No fabricated official counts |
| Map data | Review supported areas, sources, versions, and publication status | No invented susceptibility for real barangays |
| Settings / parameters | Manage only authorized, validated, versioned values | No raw rule or algorithm editing |
| DSS content | Draft and edit sourced preparedness guidance | Cannot alter classification |
| Rainfall references | Maintain metadata and approved scenario references | Not a live monitoring control |
| Evacuation centers | Maintain verified records from an authorized custodian | No invented centers or live occupancy claims |
| Sources and provenance | Record custody, license, processing, and limitations | No bypass of restricted-data rules |
| Audit history | Review accountable administrative changes | No silent destructive edits |

## Effect on the mobile application

The mobile experience should evolve toward a clear step flow:

1. show terms, limitations, and privacy/location explanations when applicable;
2. choose or confirm a hypothetical rainfall scenario;
3. choose a supported area or place a temporary pin;
4. evaluate the confirmed scenario;
5. show the map and explainable susceptibility result; and
6. show separately labeled preparedness guidance and verified resource details.

This flow may reduce taps, preserve selections, and update responsively while the
app is open. It must not silently become continuous background monitoring.

## Change-control rule

### Team selected-local-record sharing decision — 6 October 2026

The project owner authorized a reviewed, repeatable package of selected local
boundary/source states and two temporary evacuation centers, followed by a Git
push. See [the teammate handoff](TEAM_LOCAL_DATA_HANDOFF.md). This is local
development setup, not a general Admin data-exchange feature, institutional
review or automatic synchronization of runtime databases. Snapshot approval
must reflect actual rows: currently the boundary source is internally approved
while the City and all 47 barangays remain pending. Temporary approval stays
local, visibly demonstration-only and publicly unreleasable. Original accounts,
reviewer identities, contacts, secrets and restricted data are not shared.
Teammates explicitly preview/apply against their own local PostGIS database;
conflicts roll back rather than overwrite their work. There is no new schema,
scientific knowledge, parameter activation, official-data import or deployed
database mutation. Later records or approvals need a separately reviewed update.

### Team boundary-review compatibility decision — 5 October 2026

The project owner authorized support for renamed and internally approved Bacoor
administrative boundaries. Resolve dataset identity through the fixed City PSGC
record and its existing source relationship, not a display name or a developer's
local primary key. Enabled valid City/barangay geometry and a publicly releasable
agency source may be pending or approved for administrative mapping. A complete
47-barangay set remains required; restricted, retired, synthetic, disabled and
invalid geometry cannot enter resident lookups. Mixed pending/approved boundary
rows are supported. Per-record source/geometry statuses remain truthful.

This is a team implementation decision, not adviser approval or City endorsement.
It does not approve susceptibility datasets, scientific parameters, expert rules
or temporary facilities. Those gates and labels remain independent. The boundary
source remains excluded from facility evidence even after rename/approval.
Reimports reuse existing rows and preserve metadata/review/release decisions;
replacement of reviewed geometry requires return to review. No application rows,
schema, dependencies, imports or automatic approvals are required for this update.

### Team development decision — 5 October 2026

The project owner authorized temporary source/evacuation-center testing through
the normal local Admin forms, existing database tables and nearest-center API.
See [the local testing workflow](LOCAL_TESTING_WORKFLOW.md). This is a team
development decision, **not adviser approval** or agency/facility verification.
Existing demonstration markers remain at rest; debug loopback opt-in, explicit
local approval, honest output labels and per-row cleanup prevent test records
from becoming official/public records. There is no background refresh. Other
data/parameter/DSS governance remains unchanged; no AHP/WLC adoption is authorized.

### Team map/location usability decision — 5 October 2026

The project owner requested shelter-style evacuation-center icons visible when
the signed-in map opens, a nearest-center highlight and Prepare distance, and
pin synchronization after manual barangay or foreground GPS selection. This is
a **team implementation request, not adviser approval**, agency verification,
an evacuation instruction, or a scientific-method change.

- Load the eligible center catalog once when the signed-in map opens. This
  requires no personal coordinate and must not trigger GPS permission/access.
  Retain genuine source/publication/verification eligibility, or clearly labeled
  approved temporary records in the opted-in local testing environment.
- Identify the nearest center only after a location point is confirmed. Show a
  brief finite visual pulse and persistent nearest label; honor reduced-motion
  settings and stop animation when the app is inactive. This is a presentation
  cue, not a repeating location refresh, emergency alert, or vibration alarm.
- Keep Prepare distances explicitly approximate and straight-line, never road
  distance, route safety, facility availability, capacity, or an instruction to
  travel to that center.
- Foreground GPS places the pin at the exact acquired coordinate, subject to
  the existing accuracy policy; a rounded resolver echo or barangay center must
  not replace it. Retain explicit purpose/permission and barangay confirmation.
- Manual selection may now place an in-memory reference point strictly inside
  the selected polygon, accounting for concavity, holes and multiple parts.
  Label it approximate, **not the user's actual location**; distances from it
  share that limitation. Allow dragging to refine it. Do not invent a point
  when usable geometry is unavailable. Reselecting a previously confirmed
  precise pin/GPS barangay must preserve that precise coordinate.
- No location history, background polling, continuous GPS, rainfall monitoring,
  live alerts, or automatic evacuation recommendation is authorized. Clearing,
  cancelling or ending the location flow still clears temporary coordinates.

This request supersedes older implementation descriptions that manual barangay
selection always has no coordinate, only for the labeled reference-point
behavior above. The adviser consultation and unresolved research requirements
remain distinct from this later team usability decision.

### Team map-shortlist and display refinement — 5 October 2026

The project owner subsequently requested **up to 25 nearest eligible centers
around the current map pin**, replacing the all-center startup display above.
At startup, use the initial boundary-bounds midpoint pin as a map reference,
not an acquired/confirmed personal location. Recalculate only when the pin
changes (drag, GPS or manual selection) or on explicit Refresh centers. Camera
pan/zoom, legend opening and tab/sheet navigation must retain the same shortlist.
Keep distance/nearest-personal-location claims behind existing confirmation.
Rank all eligible candidates by the existing PostGIS straight-line distance
expression, then public UUID for ties; do not rank a truncated all-center page.
Transient POST coordinates are not persisted or put in a URL/query string.

The owner also requested removal of the repetitive global Admin local-testing
banner; per-record temporary labels and local-only gates remain. A compact map
Legend button now contains susceptibility swatches, the gray outside-coverage
explanation, and existing limitations. Backend result colors remain authoritative.
Shelter labels/3D buildings must not hide their icons. These are team usability
decisions, not adviser approval, agency verification or methodology adoption.
No new database tables, application rows, packages, polling or migrations are
required for this refinement.

### Team resident-interface simplification — 6 October 2026

The project owner requested a simpler retained-map interface and one area
confirmation. This is a **team usability decision, not adviser approval**,
City verification, a data approval or a scientific-method change.

- The three resident destinations are Assess, Prepare and Profile. Assess owns
  flood information, guided assessment and results. There is no separate Map
  destination; navigation and sheet interaction retain the same map/camera.
  A static FloodSense header replaces the redundant top assessment shortcut.
- GPS and dragged-pin boundary matches remain candidates until the single
  **Confirm area** action in Step 2. That action confirms the location and
  advances to Review; it does not run an assessment. A manual dropdown choice
  is explicit selection and advances through the same action. Remove the
  separate Confirm barangay and Correct manually buttons. GPS/manual/pin origin
  labels update with their corresponding temporary coordinate.
- Step 2 displays the barangay name beneath the compact location-origin row,
  keeps Use my location, manual selection, clearing and recovery controls,
  and retains the short blue confirmation notice. Detailed boundary status,
  limitations, GPS accuracy and provisional baseline belong in Step 3 Review.
  Approximate barangay points remain labeled as references, not measured GPS.
- After purpose-dialog Continue, if location is off, open Android Location
  Settings immediately. Retry once on return; never repeatedly open settings
  or inspect GPS on unrelated lifecycle resumes. Try again remains available
  if launching settings fails or the service remains off. Manual selection,
  clearing and cancellation invalidate any armed settings-return acquisition.
- One gray legend entry covers unclassified/insufficient data inside Bacoor
  and places outside coverage, beneath the four susceptibility swatches. Remove
  the repeated gray-coverage and shelter prose from this popup. Gray remains
  neutral, not a susceptibility class; backend classification colors and source
  labels are unchanged. Shelter/distance limitations remain in center details.
- The collapsed sheet tab is shorter and wider with a finite, subtle upward
  arrow hint; it honors reduced motion and stops outside the foreground. Its
  touch target remains 48 px high. Keep the central drag bar and separate right
  collapse arrow apart. Disable the native Mapbox north-reset compass that
  overlaps the custom zoom button; retain attribution and other visible controls.

This supersedes older descriptions of separate candidate confirmation UI, not
the requirement for explicit location confirmation, foreground purpose/permission,
supported-boundary eligibility, honest source labels or explicit scenario review.
No database rows, packages, migrations, background tracking, rainfall polling,
live warning behavior or automatic evacuation recommendation are authorized.

When a later adviser consultation or methodology decision changes this record:

1. preserve the new source material;
2. update this document with the date and decision owner;
3. update the Admin plan and affected diagrams;
4. add or revise tests before changing production behavior; and
5. clearly state whether the change is adviser feedback, an approved research
   decision, or a team proposal awaiting confirmation.
