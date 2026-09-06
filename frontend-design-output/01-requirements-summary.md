# FloodSense frontend requirements summary

Reviewed sources:

- `FloodSense_Revised_Feature_Specifications_Updated_Detailedaug25 final.pdf` (49 pages; referred to below as **Feature Specifications**).
- `MOR-ConceptChecklist-Revised (1).pdf` (6 content pages; referred to below as **Concept Checklist**).

The revised Feature Specifications are the primary source. The Concept Checklist confirms the scope, limitations, safety boundaries, and core MVP direction.

## Product purpose and boundaries

FloodSense is a scenario-based Android application for flood-susceptibility assessment and pre-event preparedness in Bacoor City, Cavite. It uses a deterministic, rule-based Expert System, a dynamic GIS-style map, a Decision Support System (DSS), and verified evacuation-center resources. It is not a live weather or flood sensor, real-time forecast, road-safety service, official warning issuer, evacuation authority, or open-ended AI assistant (Feature Specifications, pp. 2-5, 22, 25; Concept Checklist, pp. 1-6).

Geographic precision must not exceed the approved evidence. Public output may be barangay, sub-barangay, or another approved zone resolution. Unsupported areas must return a limitation state rather than fabricated certainty (Feature Specifications, pp. 4, 15-18; Concept Checklist, p. 1).

## Supported actors

| Actor | Surface | Responsibilities |
|---|---|---|
| Resident / mobile user | Android app | Read the disclaimer; register/login; choose rainfall scenario; inspect the dynamic map; place a manual Check My Area pin; view explainable results; use DSS guidance and supported help; find verified evacuation centers; manage profile/preferences. |
| Authorized administrator | Web administration system | Maintain and publish map data, Expert System rules, rainfall references, DSS content, evacuation centers, source/provenance records, public content, versions, and audit history. |
| Subject-matter expert / reviewer | Administrative review workflow | Review proposed geographic assessments, rules, preparedness actions, and sources before approval. This is a workflow, not necessarily a separate MVP account. |
| External map/navigation provider | External service | Provide basemap tiles and/or turn-by-turn navigation. FloodSense remains responsible for its own susceptibility data and must not imply that external routing validates safety. |

## Core resident features and workflows

1. **Onboarding, scope, and safety disclaimer.** First launch explains purpose, susceptibility meaning, scenario planning, geographic resolution, data/rule version, Expert System, DSS, manual pin behavior, privacy, and official-source reminders. Acknowledgement is versioned; cached approved copy may be shown when disconnected (Feature Specifications, p. 10; Concept Checklist, p. 5).
2. **Email/password authentication.** Registration uses display name, email, password, confirmation, home barangay, privacy acknowledgement, and disclaimer acknowledgement. Login uses email + password; password recovery and secure sessions are supported. Error copy stays neutral (Feature Specifications, pp. 11-12; Concept Checklist, p. 3).
3. **Dashboard.** The resident control center surfaces the current planning scenario, assessment entry point, dynamic map, Check My Area, DSS/preparedness, results summary, evacuation resources, methodology, and account settings. Scenario changes mark prior results stale (Feature Specifications, pp. 13-14).
4. **Rainfall scenario selection.** Intensity and duration are required. Baseline intensity labels are Light, Moderate, Heavy, Intense, and Torrential; baseline durations are 1, 3, 6, 12, and 24 hours. Exact thresholds and wording remain subject to final PAGASA verification (Feature Specifications, p. 14; Concept Checklist, p. 1).
5. **Dynamic susceptibility map.** Users pan, zoom, tap zones, inspect popups, toggle approved layers, view the legend, recenter to Bacoor, and view evacuation markers. Zones keep their geometry while their styles are recomputed for the selected scenario. Low = green, Moderate = yellow, High = orange, Very High = red; Uncertain/Insufficient Data use a labelled neutral limitation style (Feature Specifications, pp. 13, 15, 28-30; Concept Checklist, pp. 2-3).
6. **Rule-based assessment and explanation.** The backend resolves the area, builds facts, evaluates approved rules through forward chaining, resolves conflicts, and returns a reproducible class or safe limitation. The result includes area, scenario, class, matched rule, conditions, source/version, update date, meaning, and limitations (Feature Specifications, pp. 16-17, 22-25; Concept Checklist, pp. 2-3).
7. **Check My Area.** The user manually moves a temporary pin; GPS permission and background tracking are not required. Point-in-polygon resolution returns the most specific approved zone. Outside-area, boundary, and invalid-geometry cases ask the user to reposition or choose an area instead of claiming precision (Feature Specifications, pp. 17-18; Concept Checklist, pp. 2-3).
8. **DSS guided preparedness.** After a valid assessment, the user answers structured questions about go-bag readiness, documents, family communication, medicines/essential needs, vulnerable household members, transportation, official advisories, evacuation-center awareness, valuables, and susceptibility meaning. The deterministic tree returns approved actions and reasons; it never changes the class or issues an evacuation order (Feature Specifications, pp. 18-19, 25-27; Concept Checklist, pp. 2-3).
9. **Supported preparedness help.** Users choose supported topics or search approved keywords. Supported topics include go-bags, family plans, documents/valuables, assistance, official advisories, evacuation resources, result meaning, and Check My Area. Unsupported questions receive a transparent fallback, not a fabricated answer (Feature Specifications, p. 19; Concept Checklist, pp. 3, 5).
10. **Verified evacuation centers.** The app shows active, verified records on the map and in a distance-ranked list from the manual pin. It may show name, barangay/address, status, validation date, straight-line distance, and approved capacity/contact fields. “Get Directions” opens an external navigation app; distance does not guarantee route safety or facility availability (Feature Specifications, p. 20; Concept Checklist, pp. 2-3).
11. **Account and preferences.** The user manages display name, email, home barangay, optional default scenario, password actions, privacy information, account deletion request, and logout. Home barangay and default scenario are convenience preferences, not precise location or current weather (Feature Specifications, pp. 20-21; Concept Checklist, p. 3).
12. **Degraded and offline behavior.** Online-first assessment is the MVP baseline. If an approved cache exists, screens show its date/version and may provide cached disclaimer, map, scenario classifications, DSS content, and center snapshot. Without valid cache, the app says service unavailable / internet required and does not invent a result (Feature Specifications, p. 21; p. 45; Concept Checklist, p. 6).
13. **Data, methodology, and transparency.** Public content explains sources, geographic resolution, versions, Expert System method, class meanings, uncertainty states, DSS role, center verification, map/routing limitations, privacy, and the official-source reminder (Feature Specifications, p. 21; Concept Checklist, p. 5).

## Core administrator features and workflows

- **Admin authentication and authorization:** email + password, authorized staff role, server-side permission enforcement, protected session, optional later MFA, no password visibility, and privileged audit logging (Feature Specifications, p. 30).
- **Admin dashboard:** published map/rule/DSS/rainfall versions, active zones, verified centers, publish date, pending reviews, warnings, recent activity, and quick actions (Feature Specifications, p. 30).
- **Geographic/map management:** interactive map editor, draft polygons/points, metadata, GeoJSON import, geometry validation, versioning, preview, and publication gates. Draft geometry never reaches residents (Feature Specifications, pp. 28-30; 31).
- **Expert System knowledge management:** searchable rule list, structured condition builder, explanation/source links, draft/review/approved/published statuses, test sandbox, batch tests, immutable published versions, rollback, and audit (Feature Specifications, pp. 22-25, 31).
- **DSS builder:** visual tree, question/branch/action editors, preview, transition validation, safety-language review, versioning, and publishable offline bundle (Feature Specifications, pp. 25-27, 32).
- **Rainfall references:** categories, thresholds/reference text, allowed durations, source, effective date, version, active status, and dependency checks for affected rules (Feature Specifications, p. 32).
- **Evacuation centers:** add/edit/move/verify/activate/deactivate with coordinates, source, validation date, and public-output eligibility gates (Feature Specifications, p. 33).
- **Sources, content, accounts, audit, and recovery:** provenance register, public content/version preview, limited user support actions, immutable audit records, exports, backups, restore testing, and controlled rollback (Feature Specifications, pp. 33-34, 38-42).

## State model

| State | Required treatment |
|---|---|
| Normal / Low / verified | Calm surface, explicit label, green status treatment, plain-language meaning. |
| Moderate / advisory | Amber label + icon + explanatory copy. |
| High / Very High | Orange/red label + icon + stronger action emphasis; never imply live warning or evacuation order. |
| Uncertain / Insufficient Data | Neutral labelled limitation state; explain conflict or missing coverage; never silently coerce to a normal class. |
| Outside supported area / boundary ambiguity | Ask user to reposition or select a supported area; show actual supported resolution. |
| Stale result | Mark outdated after scenario, location, map, rule, or compatible-version changes; require re-evaluation. |
| Offline with cache | Show cached date/version and stale-data warning. |
| Offline without cache / API unavailable | “Service unavailable / Internet required”; preserve safe public information only. |
| Draft / review / blocked admin content | Keep non-public; show validation errors, missing sources, unreachable DSS nodes, or publish blockers. |
| Basemap unavailable | Keep FloodSense overlays/legend where feasible and distinguish basemap failure from assessment failure. |

## Source-backed requirements vs visual design decisions

**Source-backed:** the two connected surfaces; Bacoor-only scope; manual pin; scenario inputs; dynamic polygons; rule-based forward chaining; explainable results; DSS decision tree and supported topics; verified-center ranking; email/password; draft/review/publish; provenance/versioning/audit; visible limitations; no live forecast, no ML classifier, no open chatbot, no automatic GPS/background tracking.

**Visual design decisions:** navy/cyan civic palette; restrained surfaces and shadows; large status labels with icons; text-first legends; mobile bottom navigation; desktop sidebar; card groupings; typography scale; spacing, breakpoints, radius, and component variants documented in `design-system.png` and `component-library.png`.

## Ambiguities and missing information

- Final PAGASA-aligned thresholds, exact public wording, intensity taxonomy, and duration availability must be verified before deployment.
- Final approved Bacoor zone/barangay geometries, source datasets, evidence resolution, and rule coverage were not provided in the revised PDFs.
- Actual evacuation-center records, capacity/contact fields, operational status rules, validation schedule, and responsible-office contacts remain to be supplied/approved.
- The precise institutional approval roles and whether subject-matter experts receive separate accounts are not finalized.
- Email verification timing for a closed thesis pilot, optional MFA, final official contact URLs, and retention/deletion policy need institutional decisions.
- Offline caching is explicitly a later/degraded capability; cache contents and sync conflict behavior remain implementation decisions.
- All names, counts, version strings, dates, rule IDs, center names, and map imagery used in the mockups are representative concept data unless explicitly described as a source-backed label. They must not be presented as validated public outputs.
