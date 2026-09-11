# FloodSense Day 1: Core Domain and API Blueprint

**Official research title:**\
**FLOODSENSE: AN ANDROID-BASED EXPERT SYSTEM FOR FLOOD SUSCEPTIBILITY ASSESSMENT AND PRE-EVENT PREPAREDNESS IN BACOOR CITY**

**Document status:** Initial development blueprint; expected to evolve with the approved research design and official datasets.\
**Prepared for:** The one-week FloodSense prototype implementation plan.\
**Day 1 focus:** Define what the system receives, how the Expert System reasons, what it returns, and where future official data will be stored.

---

## 1. Why Day 1 Exists

The project must not stop while the team waits for official datasets. Day 1 creates the agreed structure—the “containers” and logic—into which validated data can later be imported.

Today is successful when the team can clearly explain this complete path:

> An administrator manages an explicitly labeled demonstration geographic area, facts, rules, and preparedness guidance. A user selects a location and rainfall scenario. Django sends those inputs to a deterministic Expert System. The Expert System returns a susceptibility result with an explanation. The DSS returns guidance without changing that result. The Flutter app will later display the area, result, warning, explanation, and guidance.

No official Bacoor susceptibility classification is created on Day 1.

---

## 2. Day 1 Scope

### Included today

1. Confirm the official project title.
2. Define the smallest working Admin-to-User flow.
3. Define the assessment inputs and outputs.
4. Define the four susceptibility classes and the non-classification states.
5. Define the minimum database containers required for the prototype.
6. Define a deterministic Expert System algorithm.
7. Define the boundary between the Expert System and DSS.
8. Draft the API contracts the Flutter app will use.
9. Establish rules for demonstration, pending, approved, and restricted data.
10. Decide which features are deferred until after the core demonstration works.

### Not included today

- Creating or changing Django models or migrations
- Entering official or restricted agency data
- Inventing Bacoor rainfall thresholds or barangay classifications
- Building Flutter screens
- Implementing routing to evacuation centers
- Training a machine-learning model
- Publishing or deploying the application

These exclusions keep Day 1 focused. They do not remove those features from the full research scope.

---

## 3. The Smallest Defensible Vertical Slice

The one-week prototype should demonstrate this end-to-end sequence:

1. An authorized administrator signs in to Django Admin.
2. The administrator creates or updates a demonstration area, its facts, an active ruleset, rules, and DSS guidance.
3. Django stores those records in PostgreSQL/PostGIS.
4. The Flutter app retrieves the available demonstration areas and scenario options through the Django REST API.
5. A user chooses a demonstration area, a rainfall-intensity scenario, and a rainfall-duration scenario.
6. Flutter sends those inputs to the assessment API.
7. Django validates the request and runs the Expert System.
8. The Expert System returns one susceptibility class or one limitation state, plus an explanation and traceable rule/source information.
9. If a susceptibility class was produced, the DSS retrieves the matching preparedness guidance.
10. Flutter displays the map result, explanation, guidance, source status, and a permanent demonstration-data warning.
11. If the administrator changes an enabled rule or guidance item, the next user assessment reflects the change without editing Flutter code.

This proves that Admin, database, API, Expert System, DSS, and user application are connected.

---

## 4. System Boundaries

### Django Admin

Used by authorized project administrators to manage:

- data sources and their validation status;
- demonstration or approved geographic areas;
- area facts used by the Expert System;
- scenario options;
- rulesets and rules;
- susceptibility levels;
- DSS guidance; and
- activation and version information.

Django Admin is not the resident-facing application.

### Expert System

The Expert System performs deterministic, rule-based reasoning. It:

- receives validated facts;
- checks explicit IF–THEN rules;
- selects the most applicable rule according to defined precedence;
- returns a susceptibility classification or limitation state; and
- explains which rule and facts produced the result.

The prototype does **not** train a neural network or machine-learning model. A rule-based Expert System is still a recognized branch of artificial intelligence because it represents expert knowledge as rules and applies an inference process to reach conclusions.

### Decision Support System (DSS)

The DSS receives the completed assessment result as read-only input and returns appropriate preparedness guidance.

The DSS must never:

- change the susceptibility classification;
- claim to predict a real flood;
- issue an official emergency warning;
- invent an evacuation instruction; or
- replace instructions from PAGASA, NDRRMC, BDRRMO, or other authorities.

### Flutter Android application

Flutter displays information and sends requests to Django through the API. It must never connect directly to PostgreSQL.

### PostgreSQL/PostGIS

PostgreSQL stores structured records. PostGIS stores and queries geographic shapes and coordinates. Git synchronizes Django code and migrations, not teammates' local database rows or local administrator accounts.

---

## 5. Assessment Inputs

The first prototype assessment uses only the following inputs.

### Required input 1: Location

For the first implementation, the request may provide a `geographic_area_id` selected from the map. A later iteration may accept latitude and longitude and use PostGIS point-in-polygon lookup.

The system must know whether the selected location is:

- inside a supported area;
- outside all supported areas; or
- impossible to resolve because geographic data are missing.

### Required input 2: Rainfall-intensity scenario

Until validated thresholds are available, the demonstration must use symbolic scenario codes rather than invented millimeters-per-hour thresholds.

Initial safe examples:

- `DEMO_INTENSITY_A`
- `DEMO_INTENSITY_B`
- `DEMO_INTENSITY_C`

The interface must identify them as demonstration scenarios. They must not be presented as PAGASA warning levels or official Bacoor measurements.

### Required input 3: Rainfall-duration scenario

The first prototype may use controlled demonstration choices such as:

- `DEMO_SHORT`
- `DEMO_MEDIUM`
- `DEMO_PROLONGED`

The exact minute/hour ranges must remain configurable and must not be described as official thresholds until they are supported by an approved source or expert validation.

### Area facts

Area facts are retrieved by the backend rather than freely entered by the resident. Examples of future facts include hazard-map classification, elevation category, drainage-related condition, or documented historical flooding. Only facts justified by the approved methodology should become active production inputs.

---

## 6. Assessment Outputs

### Susceptibility classes

The Expert System may return exactly one of these four study classifications:

- `LOW`
- `MODERATE`
- `HIGH`
- `VERY_HIGH`

These describe flood susceptibility under the supplied facts and scenario. They do not mean that a flood is currently occurring and are not official forecasts or warnings.

### Limitation states

The following are system states, not additional susceptibility classes:

- `UNCERTAIN` — equally applicable highest-priority rules conflict.
- `INSUFFICIENT_DATA` — the supplied and stored facts do not satisfy any valid rule.
- `OUTSIDE_SUPPORTED_AREA` — the selected location is outside the geographic coverage supported by the active data and rules.

The API should also use `CLASSIFIED` when one of the four susceptibility classes is successfully produced.

### Required explanation fields

Every response should tell the user:

- assessment state;
- susceptibility level, only when classified;
- short plain-language explanation;
- input scenario used;
- resolved area;
- matched rule identifier or identifiers;
- active ruleset name and version;
- source status;
- last relevant update date, when available;
- limitations or warnings; and
- DSS guidance, when classification succeeds.

The explanation is assembled from reviewed rule rationales and facts. It is not generated by an unrestricted chatbot.

---

## 7. Data and Publication Statuses

Every imported dataset, manually entered fact, rule, and guidance item must retain its source and review status.

Recommended statuses:

- `DEMONSTRATION` — fictional or synthetic material for development and testing only.
- `PENDING_VALIDATION` — received or drafted but not yet approved for system use.
- `APPROVED` — reviewed and authorized for the defined research use.
- `RESTRICTED` — may be stored only under its agreement and must not be exposed by the public API.
- `RETIRED` — previously used but no longer active.

Rules for using these statuses:

1. Demonstration and official records must remain distinguishable in the database.
2. Demonstration records must show **“DEMONSTRATION DATA—NOT OFFICIAL”** in Admin and the user interface.
3. Demonstration polygons should use neutral names such as `Demo Zone A`; do not assign invented risk levels to real Bacoor barangays.
4. Pending-validation data must not silently become active production data.
5. Restricted raw data, EULAs, IDs, credentials, and personally identifiable information must never be committed to Git.
6. Production/public endpoints should expose only fields permitted by the source agreement.
7. Every official-data import must record its source, coverage, received date, permitted use, validation status, and reviewer.

---

## 8. Minimum Data Containers for Day 2

The following is the target domain model, not yet a migration. Day 2 will convert the agreed minimum into Django models.

### `DataSource` — provenance module

Purpose: records where information came from and whether it may be used.

Minimum fields:

- name;
- organization;
- source type;
- coverage description;
- record period;
- received or created date;
- permitted-use summary;
- validation/publication status;
- reviewer and review date, when applicable;
- is public/releasable;
- notes.

### `GeographicArea` — geography module

Purpose: stores a supported map area.

Minimum fields:

- stable code;
- display name;
- area type;
- polygon or multipolygon geometry;
- coordinate reference system handling through GeoDjango/PostGIS;
- linked data source;
- publication status;
- enabled flag.

For the prototype, use fictional `Demo Zone A` through `Demo Zone D` shapes only.

### `AreaFact` — geography/expert boundary

Purpose: stores a source-backed fact about an area that a rule may test.

Minimum fields:

- geographic area;
- controlled fact key;
- controlled or numeric value;
- unit, when applicable;
- linked data source;
- publication status;
- effective date or version;
- enabled flag.

Avoid arbitrary free-text fact keys in production. A controlled vocabulary prevents spelling differences from changing inference.

### `ScenarioOption` — expert module

Purpose: stores selectable, ordered rainfall-intensity and duration scenarios.

Minimum fields:

- category: intensity or duration;
- stable code;
- display label;
- optional numeric minimum and maximum only when validated;
- unit, when applicable;
- linked data source;
- publication status;
- display order;
- enabled flag.

### `SusceptibilityLevel` — expert module

Purpose: provides the controlled four-level result vocabulary.

Minimum fields:

- code: low, moderate, high, or very high;
- display label;
- display order;
- map color;
- definition;
- linked data source or approval record;
- enabled flag.

### `RuleSet` — expert module

Purpose: groups an approved or demonstration version of Expert System knowledge.

Minimum fields:

- name;
- version;
- mode/status;
- effective date;
- linked data source or expert-validation record;
- enabled/active flag;
- change summary.

Only one ruleset for a given operating mode should be active during evaluation.

### `ExpertRule` — expert module

Purpose: represents the IF–THEN rule and its conclusion.

Minimum fields:

- stable rule code;
- ruleset;
- optional geographic scope;
- result susceptibility level;
- explicit priority;
- rationale/explanation template;
- linked source;
- publication status;
- enabled flag.

### `ExpertRuleCondition` — expert module

Purpose: represents one condition that must be true for its parent rule to match.

Use a controlled condition type and operator. Do not execute arbitrary code or expressions stored in the database.

Initial controlled condition types may include:

- intensity option equals a selected code;
- duration option equals a selected code;
- area fact equals an expected controlled value; and
- validated numeric fact is greater than, greater than or equal to, less than, or less than or equal to a value.

All enabled conditions on a rule must match for the rule to fire.

### `GuidanceItem` — DSS module

Purpose: stores preparedness guidance associated with a susceptibility level.

Minimum fields:

- susceptibility level;
- title;
- instruction text;
- category such as prepare, monitor, protect, or evacuate-only-if-authorities-order;
- display order;
- linked source;
- publication status;
- enabled flag.

Guidance must be reviewed and phrased as preparedness support, not as an official emergency command.

### Assessment history

Persistent assessment history is not required for the first vertical slice. The backend can evaluate a request and return a response without storing the resident's precise location. This reduces privacy risk and avoids making account/history work a blocker.

If history is added later, the team must first define consent, retention, deletion, precision reduction, and access-control rules.

---

## 9. Deterministic Forward-Chaining Procedure

The first inference engine should follow this exact sequence:

1. **Validate the request.** Require a supported location/area, intensity option, and duration option. Reject unknown or disabled identifiers.
2. **Resolve the geographic area.** For the first prototype, load the selected area ID. Later, resolve latitude/longitude with a PostGIS point-in-polygon query.
3. **Return a coverage state when necessary.** If a supplied coordinate is outside all supported active areas, return `OUTSIDE_SUPPORTED_AREA`.
4. **Load the operating mode.** A demonstration request may use only demonstration sources and rules. An official/production request may use only approved, releasable sources and rules.
5. **Select the active ruleset.** There must be one active ruleset for the selected mode. Zero active rulesets produces `INSUFFICIENT_DATA`; multiple active rulesets is a configuration error that must be visible to Admin.
6. **Assemble facts.** Combine the selected scenario options with enabled area facts that are valid for the active mode.
7. **Filter rules before matching.** Keep only enabled rules from the active ruleset whose status and source permissions allow the current mode.
8. **Evaluate every condition.** A rule matches only when all its enabled conditions evaluate to true.
9. **Handle no match.** If no rule matches, return `INSUFFICIENT_DATA` and explain which required information or rule coverage is absent when possible.
10. **Rank matching rules.** Prefer the rule with the most specific geographic scope, then the highest explicit priority. The ordering fields must be deterministic.
11. **Handle a top-level tie.** If equally ranked top rules lead to different susceptibility levels, return `UNCERTAIN`. If they lead to the same level, return that level and include all supporting top-rule identifiers.
12. **Create the explanation.** Return the matched facts, rule rationale, source/status, ruleset version, and limitations.
13. **Call the DSS service.** Only a `CLASSIFIED` result is passed to the DSS. The DSS retrieves reviewed guidance for that level without modifying the classification.
14. **Return one structured response.** The API aggregates the Expert System result and DSS guidance for easy use by Flutter while preserving the internal separation of responsibilities.

### Important inference restrictions

- Never use Python `eval`, dynamic executable expressions, or database-provided code.
- Never select rules merely because they are newer; only an explicitly active ruleset is evaluated.
- Never mix demonstration facts with approved facts in a production result.
- Never silently choose between conflicting top rules.
- Never fall back to a default susceptibility class when evidence is missing.

---

## 10. Planned API Contracts

All application endpoints will be versioned under `/api/v1/`. The following paths are drafts for implementation on later days.

### Retrieve assessment choices

`GET /api/v1/assessment-options/?mode=demonstration`

Returns enabled intensity and duration options and the required demonstration warning.

### Retrieve map areas

`GET /api/v1/geography/areas/?mode=demonstration`

Returns permitted area identifiers, names, display geometry, provenance summary, and status. Restricted source data must never be included.

### Evaluate susceptibility and obtain guidance

`POST /api/v1/assessments/evaluate/`

Example demonstration request:

```json
{
  "mode": "demonstration",
  "geographic_area_id": 1,
  "rainfall_intensity_code": "DEMO_INTENSITY_B",
  "rainfall_duration_code": "DEMO_MEDIUM"
}
```

Example response shape:

```json
{
  "assessment_state": "CLASSIFIED",
  "susceptibility": {
    "code": "MODERATE",
    "label": "Moderate",
    "color": "#F4C542"
  },
  "area": {
    "id": 1,
    "code": "DEMO_ZONE_A",
    "name": "Demo Zone A"
  },
  "scenario": {
    "rainfall_intensity_code": "DEMO_INTENSITY_B",
    "rainfall_duration_code": "DEMO_MEDIUM"
  },
  "explanation": {
    "summary": "The selected demonstration facts satisfied DEMO-RULE-002.",
    "matched_rule_codes": ["DEMO-RULE-002"],
    "ruleset": "Demonstration Rules v1",
    "facts_used": [
      "rainfall_intensity=DEMO_INTENSITY_B",
      "rainfall_duration=DEMO_MEDIUM"
    ]
  },
  "guidance": [
    {
      "title": "Review household preparedness supplies",
      "instruction": "Check your household emergency supplies and continue monitoring official advisories."
    }
  ],
  "data_status": "DEMONSTRATION",
  "warnings": [
    "DEMONSTRATION DATA—NOT OFFICIAL",
    "This result is not an official flood forecast, warning, or emergency instruction."
  ]
}
```

An unclassified response must set `susceptibility` to `null`, provide one of the limitation states, omit operational guidance that assumes a class, and explain the limitation.

### Existing health endpoint

`GET /api/v1/health/`

This remains a simple public check that the Django API is running. It is not an assessment endpoint.

---

## 11. Authentication Decision for the One-Week Prototype

### Required now

- Django Admin accounts remain required for administrators.
- Admin endpoints and data-management actions must remain protected.

### Recommended for the immediate demonstration

Resident registration should not block the assessment vertical slice. The demonstration assessment may be used without creating a resident account, and it should not persist precise user location by default.

Resident registration, login, password recovery, saved locations, and assessment history can remain part of the full system if required by the approved feature specification. They should be implemented after the core Admin–Expert System–DSS–Flutter connection is working, unless the adviser explicitly requires them in next week's demonstration.

The existing custom email-based Django user model and JWT capability remain the intended foundation if resident authentication is implemented. An external authentication service such as Clerk is not needed for the current architecture.

---

## 12. Preparedness Guidance Boundaries

Guidance will eventually be reviewed with credible official sources or subject-matter experts. The first prototype needs only clearly labeled demonstration guidance that proves the DSS data flow.

Recommended intent by result level:

- **Low:** maintain basic readiness and continue monitoring official information.
- **Moderate:** review supplies, household plans, and vulnerable household members' needs.
- **High:** prepare essential items and documents, avoid known hazardous areas, and closely monitor official instructions.
- **Very High:** be ready to act promptly and follow evacuation or safety instructions issued by authorized authorities.

These are design directions, not final approved wording. No prototype guidance may tell a user that evacuation is officially ordered unless an authorized source actually issued that order.

---

## 13. What Changes When Official Data Arrive

The official-data workflow should replace records, not rewrite the whole application:

1. Keep the raw received file outside Git in an approved secure location.
2. Record its provenance, coverage, restrictions, and validation state.
3. Inspect its schema, CRS, units, missing records, and permitted public fields.
4. Create a reviewed import/normalization process.
5. Import records as `PENDING_VALIDATION` first.
6. Validate the imported geometry, values, time coverage, and rule interpretation.
7. Obtain the required reviewer/adviser/expert approval.
8. Promote approved records or create a new approved ruleset version.
9. Deactivate the old version without deleting audit history.
10. Run automated tests and compare known cases before making the new version active.

No agency dataset should be copied into `research_data/approved/` merely because it was received. Approval, permitted use, and validation must be documented first.

---

## 14. MVP and Deferred Features

### Must work for next week's demonstration

- protected Django Admin access;
- editable demonstration areas and provenance;
- editable scenario options;
- editable ruleset, rules, and conditions;
- deterministic Expert System evaluation;
- explainable result or explicit limitation state;
- DSS guidance by susceptibility level;
- REST API connection between backend and Flutter;
- functional Flutter assessment screen;
- pre-built demonstration map with neutral fictional zones;
- permanent demonstration and non-authority disclaimers; and
- a proof that Admin changes affect the next user result.

### Deferred until the core is stable

- resident registration and account recovery;
- social or Clerk authentication;
- saved locations and personal history;
- push notifications and live sensor feeds;
- real-time flood forecasting;
- machine-learning training;
- AI chatbot features;
- complete evacuation-center routing;
- advanced approval/rollback dashboards;
- public deployment and app-store packaging; and
- official Bacoor classifications pending valid sources and review.

---

## 15. Day 1 Team Walkthrough

Use this sequence in a short team meeting.

### Step 1 — Read the official title aloud

Confirm that every future diagram, document, screen, README, and presentation uses the exact official title at the top of this document.

### Step 2 — Explain the two engines

One member explains that the Expert System determines susceptibility. Another explains that the DSS only retrieves preparedness guidance for the result.

### Step 3 — Trace one fictional request

Trace the JSON example in Section 10 from Flutter to Django, through the rule engine, and back to Flutter. Make sure everyone can identify the inputs, output, explanation, guidance, and warning.

### Step 4 — Review the limitation states

Confirm that `UNCERTAIN`, `INSUFFICIENT_DATA`, and `OUTSIDE_SUPPORTED_AREA` are not additional risk levels.

### Step 5 — Review the minimum containers

For every container in Section 8, one member explains what it stores and why it is needed. Remove or postpone any field the team cannot justify.

### Step 6 — Review demonstration-data safety

Confirm that only neutral fictional zones and scenarios will be used until official data are validated. The UI warning must remain visible in screenshots and demonstrations.

### Step 7 — Confirm tomorrow's build order

Day 2 should implement the reviewed minimum models in this order:

1. provenance;
2. geography;
3. expert-system reference data and rules;
4. DSS guidance;
5. Django Admin configuration;
6. migrations; and
7. model/Admin tests.

---

## 16. Day 1 Acceptance Checklist

Day 1 is complete when the team agrees that:

- [ ] The official title is correct and final for current development.
- [ ] The first prototype is rule-based and does not require ML training.
- [ ] The Admin-to-database-to-API-to-Flutter flow is understood.
- [ ] Location, intensity scenario, and duration scenario are sufficient initial user inputs.
- [ ] The four susceptibility classes are accepted.
- [ ] The three limitation states are understood.
- [ ] The Expert System and DSS responsibilities are separate.
- [ ] No rainfall threshold or real barangay risk is being invented.
- [ ] The proposed minimum data containers are acceptable for Day 2.
- [ ] The deterministic rule-selection procedure is acceptable.
- [ ] Demonstration records will always be labeled and separated from official data.
- [ ] Resident authentication will not block the immediate vertical slice unless the adviser requires it.
- [ ] The listed deferred features will not distract from the one-week demonstration.

---

## 17. Questions That Require Later Validation but Do Not Block Development

1. Which input variables and thresholds will the thesis methodology formally approve?
2. Who is authorized to validate the Expert System rules and DSS guidance?
3. Which DOST-ASTI fields may be transformed, shared among researchers, shown in screenshots, or included in the final paper under the EULA?
4. Which City datasets, if any, can be requested in their existing form through a narrower request or another custodian?
5. Will resident registration remain mandatory in the final approved feature specification?
6. Should the production assessment accept a map pin, a selected barangay/zone, or both?
7. What retention and privacy rules will apply if assessment history is later stored?

The containers and interfaces above let development continue while these questions are being resolved.
