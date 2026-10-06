# Overview availability snapshot — 6 October 2026

The owner requested implementation of the supplied Overview recommendations.
This is a team UI/UX update, not adviser approval, a new inference method or a
data-release decision. It intentionally replaces the large stored-status cards
with compact availability cards and introduces a small targeted attention panel.
The September removal of the earlier attention panel was intentional; it was not
an unfinished feature.

## Reading order and behavior

Overview now shows snapshot context, five compact cards, configuration notices,
prioritized attention, and secondary shortcuts/recorded changes. Existing portal
colors, panels, buttons, Lucide icons, sidebar and account controls remain in use.
Cards use three/two columns on wide screens, two at intermediate widths, and one
on mobile. The existing center and source form improvements are preserved.

The snapshot mode is an explicit GET selection: **Approved-source mode** by
default, or **Demonstration only**. It affects scenario and DSS availability;
it does not activate knowledge sets, change application configuration or classify
an area. Invalid mode input falls back to approved-source mode. The generation
timestamp includes the application's timezone. Refresh occurs only on navigation,
manual reload or the Update snapshot button, including without JavaScript.

## Metric definitions

| Card | Definition |
| --- | --- |
| Map data | Eligible controlled boundary records against the existing expected 47 barangays. A separate complete-layer statement uses `ready_reference_barangays()`, including city geometry, source, unique identity, valid geometry and spatial coverage checks. Administrative availability is not flood susceptibility. |
| Scenario references | Enabled intensity/duration options allowed by the shared operating-mode/source policy. Stored input values are checked separately for configuration metadata; a selectable reference alone does not ensure a classification. |
| DSS content | Enabled published assessment guidance with an eligible enabled susceptibility level and eligible source in the selected mode. Structured Prepare is a separate sub-summary for the resident default `preparedness` flow, selected by the existing resolver; dates, provenance, graph/dependencies and applicability must pass. An available version lists its applicable level codes. |
| Evacuation centers | Normal resident-display eligibility, excluding temporary tests. Uses the same complete reference layer, candidate selector and strict public-schema validator as the resident service. No distance is displayed or inferred. Stored and verified totals are secondary context. |
| Data sources | Approved, publicly releasable non-demonstration sources; stored total is secondary context. Dependents must pass their own gates. |

Every restricted module has an explicit Access restricted state with no count or
management link. Assessment guidance and structured flows have independent model
view permissions. Map access follows the existing staff-only map boundary.
Underlying dependency checks do not expose private source notes, resident data,
guidance bodies, derived input values or raw rules in the snapshot.

Reports retains its detailed stored-record/status aggregates and definitions.
Availability counts are intentionally different from stored totals. Structured
flow details remain in the existing Prepare manager, reached directly from its
card. Neither Reports nor any resident/API contract changed.

## Attention and secondary information

At most five attention categories are shown. A currently published default
Prepare flow that fails resident selection is an availability problem. Explicit
Prepare/guidance In review queues, center verification review, staged center
imports with confirmable rows, and pending source metadata are workflow queues.
Queues cover all modes; availability problems use the selected snapshot mode.
Drafts and deliberate restrictions do not become errors. Completed imports and
historical rejected rows do not remain alerts. Each entry links to an existing
filtered queue or batch; it never approves, publishes or confirms from Overview.

Configuration checks use safe active knowledge-set metadata and required reference
values, gated by the corresponding view permissions. They never claim Assessment
ready. Normal resident setup checks use the same published Terms/Privacy/onboarding
existence conditions as the account service, without reading users, acceptances,
document text or applying a local tester bypass. Missing setup content points to
authorized technical maintenance, without creating new portal editing controls.

Up to three quick actions require both module view and the existing create
permission. Recent administrative changes require audit access and individual
module access, include structured Prepare models, and show at most three real
LogEntry events. Object representations and change payloads are not selected.
The list remains explicitly incomplete; modification timestamps never fabricate
events. There is no polling, background monitoring or live alerting.

## Validation and teammate steps

Passed: **205 Admin portal tests**, **3 browser acceptance checks**, Django system
check, Ruff and `git diff --check`. Coverage includes authorization, read-only GETs,
mode/source gates, published-but-future/expired/dependency-invalid flows, malformed
verified center rows, missing boundaries, completed imports, setup gaps, private
content exclusion, all existing workflows and sidebar behavior. Browser widths
include 1440/1024/768/390/320px and no-JavaScript operation.

Synthetic screenshots are ignored QA artifacts, not application/official data:

- [Desktop snapshot](../tmp/portal-layout-qa/icons-1440-after.png)
- [Demonstration snapshot](../tmp/portal-layout-qa/overview-1440-demonstration.png)
- [Mobile snapshot](../tmp/portal-layout-qa/overview-390-drawer-closed.png)

Tests use the isolated QA PostGIS database; no application/shared database, private
`.env`, official import or Git pull/push was accessed or performed. Existing
staticfiles-directory and URLField deprecation warnings remain.

After pulling, restart Django and refresh Overview. No dependencies, migrations,
seeds or imports are needed. Deployments should run their normal static-file
collection to include `overview.css`. Ordinary configured-checkout validation:

```powershell
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe -m pytest server/admin_portal --reuse-db
```

The optional browser suite uses the existing Playwright/Chromium QA tools:

```powershell
server\.venv\Scripts\python.exe -m pytest scripts/verify_admin_portal_layout.py --reuse-db
```
