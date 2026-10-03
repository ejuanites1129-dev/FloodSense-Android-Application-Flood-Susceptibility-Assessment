# Flood-Susceptibility Methodology Proposal

**Status:** PROPOSED FOR TEAM EVALUATION — NOT APPROVED / NOT IMPLEMENTATION AUTHORITY

**Recorded:** October 2, 2026

**Approval record:** None

> **REVIEW-ONLY PROPOSAL — DO NOT IMPLEMENT OR CITE AS THE ADOPTED METHODOLOGY**
>
> This document preserves a candidate methodology for team evaluation. It is
> not research-team approval, thesis-adviser approval, BDRRMO validation,
> scientific validation, an adopted Chapter 3 methodology, or implementation
> authorization. No teammate or coding agent may use this proposal to change
> the Expert System, parameters, rules, database schema, seed/import code,
> official or demonstration data, user-interface claims, or thesis/manuscript
> text. Adoption requires a recorded team decision, appropriate adviser and
> domain-expert review, validation of the data, factor definitions, weights,
> thresholds, and rule table, and corresponding documentation and tests. Until
> those gates are completed, the current implemented behavior and the
> repository's governing decision documents remain unchanged.

## Purpose

This file records the team's candidate answer to the following design question:

> How could FloodSense combine terrain, a selected hypothetical rainfall
> scenario, and historical flood evidence without treating rainfall minus
> elevation as predicted flood depth?

The proposal is a **two-stage susceptibility-screening method**:

1. an offline GIS weighted linear combination (WLC), using candidate
   AHP-derived weights, produces a terrain-based baseline score and rank; and
2. the existing deterministic Expert System combines that precomputed baseline
   rank with the selected rainfall intensity rank and duration.

This preserves FloodSense as a scenario-based susceptibility and pre-event
preparedness system. It would not make FloodSense a flood-depth model, hydraulic
simulation, real-time forecast, or official warning service.

## Governing documents

This proposal does **not** supersede any of the following:

- [TA consultation and current system decisions](TA_CONSULTATION_SYSTEM_DECISIONS.md)
- [Admin web implementation plan](ADMIN_WEB_7_DAY_IMPLEMENTATION_PLAN.md)
- [Rule-based Expert System guide](DAY_3_RULE_BASED_EXPERT_SYSTEM_GUIDE.md)
- [Parameter-governance proposal](ADMIN_DAY_4_PARAMETER_GOVERNANCE_PROPOSAL.md)
- [Team database and Git workflow](TEAM_DATABASE_AND_GIT_WORKFLOW.md)

If this file conflicts with a current governing decision, the governing
decision remains authoritative until the team records an explicit revision.

## Important correction to the initial arithmetic idea

The proposed method must **not** calculate susceptibility or flood depth by
subtracting rainfall depth from absolute elevation, for example:

```text
flood estimate = rainfall in millimetres - elevation above sea level in millimetres
```

Although both values can be expressed in millimetres, they do not represent the
same physical quantity or reference. Rain falling on one square metre is a
water-depth input (30 mm equals 30 litres over that square metre); elevation is
the ground's vertical position relative to a datum. Actual ponding or inundation
also depends on runoff, infiltration, drainage and culvert capacity, terrain
connectivity, tides or receiving-water levels, and antecedent conditions.

Consequently, this proposal uses elevation and other terrain derivatives only
as **relative susceptibility factors**. It does not convert them directly into
centimetres of floodwater.

## Candidate method

All equations, factors, normalizations, AHP weights, class thresholds,
return-period choices, and IF–THEN rules below are candidates only. Example or
symbolic values must not be entered into the application or manuscript as
validated Bacoor values.

### Stage 0 — data acceptance and preprocessing controls

Before any calculation, each source must pass the project's approval,
provenance, licensing, coordinate-reference-system, resolution, coverage,
quality, and version checks. Receiving a dataset does not automatically make it
an approved system input.

The assessment spatial unit must also be decided. A score for a raster cell,
resident pin, assessment polygon, or entire barangay has a different meaning.
The current Expert System consumes an area-level fact; it cannot use a cell-level
raster score directly without an approved aggregation or lookup design.

### Stage 1 — candidate terrain baseline

For assessment unit \(i\), the candidate baseline score is a GIS **weighted
linear combination**:

\[
B_i = \sum_{j=1}^{m} w_j r_{ij},
\qquad w_j \ge 0,
\qquad \sum_{j=1}^{m}w_j=1
\]

where:

- \(r_{ij}\) is the normalized susceptibility rating of factor \(j\) for
  assessment unit \(i\); and
- \(w_j\) is the reviewed weight for factor \(j\).

**AHP is not the score formula.** The Analytic Hierarchy Process (AHP) is a
structured expert-judgment method proposed only for deriving the weights
\(w_j\). The WLC equation above is what combines the normalized factor ratings.

Candidate terrain factors to evaluate include:

- ground elevation derived from the LiPAD DTM;
- terrain slope derived from the same approved DTM; and
- either hydrologically derived flow accumulation or Height Above Nearest
  Drainage (HAND), if one of them can be validly produced for the study area.

These are not yet approved inputs. DTM-derived flow accumulation or HAND needs
hydrologic conditioning, a defensible drainage/channel definition, a projected
CRS, resolution and vertical-datum review, and validation against Bacoor's
actual urban drainage, culverts, and water pathways. A terrain-derived drainage
network is not automatically the city's sewer or drainage network. Elevation,
slope, HAND, and accumulation may also be correlated, so including all of them
could double-count the same terrain effect.

If ordinary elevation is used, an **illustrative only** inverse min–max rating
could be discussed:

\[
r_{E,i}=1-\frac{E_i-E_{\min}}{E_{\max}-E_{\min}}
\]

The same inverse direction is sometimes considered for slope when flatter
terrain is hypothesized to retain water. A direct min–max transform could be
considered for a factor where greater values imply greater susceptibility.
These transforms are not approved: their direction, bounds, treatment of
outliers, and applicability to Bacoor require evidence and sensitivity tests.
Flow accumulation may require a logarithmic transform rather than ordinary
min–max scaling.

The continuous baseline would be converted into a rank only after thresholds
\(b_1<b_2<b_3\) are validated:

\[
BaselineRank_i =
\begin{cases}
1 & B_i < b_1 \\
2 & b_1 \le B_i < b_2 \\
3 & b_2 \le B_i < b_3 \\
4 & B_i \ge b_3
\end{cases}
\]

Ranks 1–4 could correspond to Low, Moderate, High, and Very High
susceptibility, but neither the thresholds nor their mapping is approved. They
must not be created by simply dividing the observed score range into four equal
parts without methodological justification.

### Candidate AHP weighting process

If the team approves AHP for evaluation, the proposed review process is:

1. define the hazard question, spatial unit, and non-overlapping candidate
   factors;
2. have a documented panel of appropriate experts compare factors pairwise;
3. derive normalized weights from the comparison matrices and document how
   judgments from multiple experts are aggregated;
4. calculate and report the consistency ratio (CR); a conventional target such
   as \(CR<0.10\) must itself be confirmed in the adopted protocol;
5. revise inconsistent judgments rather than concealing them; and
6. perform sensitivity analysis to show whether reasonable weight changes alter
   many classifications.

AHP makes expert weighting transparent; it does not independently prove that
the selected factors, weights, or final classes are correct.

### Stage 2 — scenario-based Expert System

For location or area \(i\) and selected scenario \(s\), the candidate system
relationship is:

\[
FinalClass_{i,s} = RuleSet(
  BaselineRank_i,
  RainfallIntensityRank_s,
  DurationHours_s
)
\]

This matches the *shape* of the current Expert System inputs:

- `zone_baseline_rank`;
- `rainfall_intensity_rank`; and
- `rainfall_duration_hours`.

However, current code does not calculate AHP, WLC, terrain derivatives, or the
baseline thresholds. If adopted, Stage 1 would initially need to be an approved,
controlled, reproducible GIS preprocessing and import workflow that supplies a
versioned baseline fact. Any in-application calculation or schema change would
require a separate reviewed implementation decision, migration where needed,
and tests.

The final IF–THEN rule table must be complete, expert-reviewed, versioned, and
validated. Existing demonstration ranks and rules are synthetic development
fixtures and are not evidence for the methodology. No-match and conflicting-rule
cases must preserve `INSUFFICIENT_DATA` or `UNCERTAIN`; they must not be forced
into one of the four colors.

### Candidate RIDF scenario derivation

For an RIDF station/version, selected duration \(D\), and selected return period
\(T\), the table may provide rainfall depth:

\[
P_s=P_{RIDF}(D,T)
\]

The corresponding average intensity is:

\[
\bar I_s=\frac{P_s}{D}
\]

The team must decide whether a scenario is entered as depth, average intensity,
or a reviewed intensity rank and must keep the units explicit. Depth and the
intensity calculated from the same RIDF cell must not be treated as independent
evidence. The selected station, table/version, duration, return period, class
thresholds, and applicability to Bacoor remain unresolved. The current data
model has no explicit return-period or station input, so adding either would be
a separate design decision.

A citywide rainfall scenario changes scenario severity but does not by itself
create spatial variation within Bacoor. The terrain baseline supplies candidate
spatial differentiation; it still does not predict inundation depth.

## Proposed role of each available or requested dataset

| Dataset | Candidate role | Must not be assumed |
| --- | --- | --- |
| LiPAD LiDAR-derived DTM | Derive reviewed ground-elevation and possibly terrain factors | Not automatically licensed for redistribution; not a flood-depth surface |
| PAGASA RIDF (Sangley; NAIA as comparison) | Define hypothetical rainfall scenarios by duration and return period | Not live rain and not automatically representative of every Bacoor location |
| DOST-ASTI observations | Compare or calibrate observed rainfall behavior if coverage, units, and quality are suitable | Not interchangeable with an RIDF design storm |
| BDRRMO historical flood records | Calibrate and/or validate susceptibility classes and rules; support local interpretation | Absence of a record is **unknown**, not proof of Low susceptibility |
| Bacoor city/barangay boundaries | Locate, aggregate, and present assessments with source attribution | Not a susceptibility factor merely because a boundary is official/approved |
| Provisional MGB susceptibility layer | Comparison evidence while its source and use remain provisional | Must not be silently merged with or overridden by the candidate terrain score |

Historical flood evidence must be georeferenced and linked to an event where
possible. The team must separate records used for calibration from records used
for independent validation, or document a defensible small-sample alternative.
The same observations cannot be claimed as both training/calibration evidence
and independent validation evidence.

The current system can prefer an active MGB consultation summary over an
ordinary area baseline fact. Before adopting this proposal, the team must decide
whether a future WLC baseline replaces that source, is evaluated against it, or
remains a separate layer. No implementation may silently combine the two.

## Output and color semantics

The candidate susceptibility labels are:

1. Low — green
2. Moderate — yellow
3. High — orange
4. Very High — red

These are susceptibility-screening classes only. They are not automatically
equivalent to MGB LF/MF/HF/VHF classes, PAGASA rainfall warnings, BDRRMO alert
levels, water-level-marker actions, or official evacuation instructions. Any
mapping among those schemes requires explicit source-backed validation. The UI
must continue to distinguish susceptibility from official warnings and actions.

## Questions the team must resolve

- What exact hazard is being classified: pluvial susceptibility, combined
  pluvial/fluvial susceptibility, or another clearly bounded hazard?
- What is the assessment unit: raster cell, user point, assessment polygon, or
  barangay summary?
- Which terrain factors are defensible and sufficiently independent?
- Can the DTM be hydro-conditioned for dense urban Bacoor, and is a verified
  drainage or channel dataset available?
- How will coastal/tidal influence, receiving-water levels, drainage capacity,
  and antecedent conditions be handled or declared as limitations?
- How will continuous scores become four classes without arbitrary cutoffs?
- Which experts supply AHP comparisons, and how will their judgments be
  aggregated and checked?
- Which RIDF station/version, durations, return periods, units, and intensity
  classes are appropriate?
- What historical observations are usable for calibration and what independent
  observations remain for validation?
- Which validation metrics and minimum acceptance criteria will be used?
- How will the proposed baseline relate to the provisional MGB layer and the
  current AreaFact/MGB override behavior?
- What source, license, attribution, retention, and redistribution restrictions
  apply to raw and derived data?

## Required approval gate

Nothing in this proposal may be implemented or presented as the adopted thesis
method until every applicable item is completed and linked to evidence:

- [ ] Research question/hazard type and assessment spatial unit approved
- [ ] Candidate factors and derivation/normalization methods approved
- [ ] LiPAD/source license, CRS, vertical datum, resolution, and provenance reviewed
- [ ] Hydrologic conditioning and drainage/HAND feasibility validated
- [ ] AHP expert panel, pairwise matrices, aggregation method, and CR acceptance documented
- [ ] WLC weights, baseline thresholds, and sensitivity analysis approved
- [ ] RIDF station/version, duration, return period, intensity/depth semantics, and units approved
- [ ] Complete versioned Expert System rule table approved; no-match/conflict handling retained
- [ ] Relationship to the provisional MGB layer explicitly decided
- [ ] BDRRMO historical schema, calibration/holdout validation plan, metrics, and pass criteria approved
- [ ] Susceptibility classes/colors distinguished from agency warnings
- [ ] Data storage/redistribution and approved import/provenance workflow authorized
- [ ] Required model/API/import changes, migrations, permissions, and tests reviewed
- [ ] Adviser/methodology expert, research team, and appropriate BDRRMO/GIS/hydrology reviewers sign off
- [ ] Separate explicit authorization to update code, data, UI, or manuscript granted

BDRRMO review is important but does not replace research-methodology, GIS, and
hydrology review or approval by the thesis team and adviser.

## Evaluation references (not adoption evidence)

These are starting points for the team's literature review. Their inclusion
does not validate the proposal for Bacoor:

- Cabrera and Lee, *Flood-Prone Area Assessment Using GIS-Based Multi-Criteria
  Analysis: A Case Study in Davao Oriental, Philippines*, Water 2019,
  <https://doi.org/10.3390/w11112203>
- Paz-Alberto et al., *GIS-Assisted Flood Hazard Assessment and Mapping in
  Selected Areas in Zambales*, ISPRS Archives 2019,
  <https://doi.org/10.5194/isprs-archives-XLII-4-W19-331-2019>

The team must verify the papers, select literature matching the final hazard
definition and data, and cite primary or authoritative sources in the
manuscript rather than treating this internal note as a source.

## Decision log

| Date | Decision | Effect |
| --- | --- | --- |
| 2026-10-02 | Candidate two-stage AHP/WLC terrain baseline plus rule-based rainfall scenario method recorded for evaluation | No code, data, UI, rule, or manuscript change authorized |
