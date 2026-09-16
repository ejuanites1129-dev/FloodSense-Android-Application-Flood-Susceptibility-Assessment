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

When a later adviser consultation or methodology decision changes this record:

1. preserve the new source material;
2. update this document with the date and decision owner;
3. update the Admin plan and affected diagrams;
4. add or revise tests before changing production behavior; and
5. clearly state whether the change is adviser feedback, an approved research
   decision, or a team proposal awaiting confirmation.
