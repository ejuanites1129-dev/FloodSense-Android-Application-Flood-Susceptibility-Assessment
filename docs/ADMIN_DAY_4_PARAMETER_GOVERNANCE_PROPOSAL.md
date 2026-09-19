# Day 4 parameter-governance proposal

Status: **Proposed; awaiting explicit research-team approval.**

This document is a reviewable design, not authorization to edit parameters.
The Day 4 checkpoint permits only the read-only Settings foundation until the
team approves the definitions, authority assignments, schema, and workflow.
Current consultation decisions and the active seven-day plan take precedence
over historical rule-editor mockups. No thesis-adviser endorsement of this
proposal is implied.

## Verified starting point

- `ScenarioOption` has a unique code, category, label, minimum/maximum values,
  `derived_value`, unit, source, publication status, enabled state, and order.
  It has no governed revisions, rationale, effective date, or definition owner.
- Numeric inference consumes `derived_value`; display order is not its numeric
  value. Intensity and duration are different inputs with different semantics.
- `RuleSet` has a stored version and an active flag. Its database constraint
  permits one active record **per operating mode**, not one across all modes.
  Its version does not version scenario-option values or the software algorithm.
- Source eligibility is enforced by `provenance.policies`. Official use requires
  approved records and approved, publicly releasable, non-demonstration sources.
  Demonstration records require a demonstration source and demonstration status.
- Django groups/permissions exist, but there is no approved assignment of
  parameter responsibilities. `is_staff` is only a portal access boundary.
- Dashboard activity is limited Django Admin `LogEntry` history. Custom views
  do not automatically generate these records; timestamps are not audit events.
- Public API consumers, including Flutter, rely on stable option codes, IDs,
  categories, numeric-or-null `derived_value`, unit, label, and display order.

## Decisions requested

1. Confirm which existing option codes may become governed parameters, separately
   for demonstration and official use. Supply the scientific definitions,
   canonical units, allowed ranges/choices, approved evidence, owner, and validator.
2. Approve or amend the revision, workflow, activation, and audit design below.
3. Assign actual people/groups to the permission matrix. Confirm the proposed
   separation of duties and who can retire, activate, and roll back revisions.
4. Confirm which approved definitions support demonstration preview and the
   approved fictional scenarios for comparison.
5. Keep data exchange deferred, or separately specify direction, formats, schema,
   permissions, source restrictions, and validation requirements. This proposal
   deliberately selects neither import nor export, CSV nor Excel.

No permission grants, migration, mutation endpoint, or demonstration preview
will be implemented on the basis of this proposal alone.

## Working recommendation held for team review

Recorded 19 September 2026 at the researcher's request while the other team
members were unavailable. This preserves a possible direction for later
discussion; it is **not team approval, adviser approval, or implementation
authorization**.

- Start with existing rainfall-intensity and rainfall-duration
  `ScenarioOption` records in demonstration mode only.
- Keep official-mode parameters read-only until their definitions and values
  have an authoritative, validated source.
- Permit a proposal to carry a numeric value, source, rationale, and effective
  date. Keep the parameter code, category, algorithm, raw rules, conditions,
  priorities, and susceptibility vocabulary outside ordinary administrator
  editing.
- Use explicit Draft, Validation, Review, Approval, and manual Activation
  stages. Do not schedule or automatically activate a revision.
- Do not allow a proposer to approve their own revision. The team must still
  assign the actual proposer, validator, approver, and activator roles.
- Preserve every prior revision. Rollback is a new audited activation of an
  eligible historical revision, never an overwrite or deletion.
- Limit effect preview to fictional demonstration zones and do not persist or
  publish preview results.
- Keep CSV/Excel import and export deferred until direction and schema are
  confirmed.
- Before governance goes live, prevent technical Admin, seed commands, bulk
  updates, and other direct write paths from bypassing the approved workflow.
- Make both the public option API and inference engine resolve the same active,
  eligible revision, and include parameter events in the audit-history design.

The team must later confirm the scientific meaning, canonical unit, allowed
range or choices, source evidence, role assignments, activation-date policy,
and preview scenarios for each parameter definition.

## Authorized definitions: proposed narrow scope

There are **no authorized editable parameter definitions yet**. The following
are candidates to confirm, not newly approved scientific values:

| Candidate | Type | Unit / bounds / choices | Inference impact | Owner and validator | Source requirement |
| --- | --- | --- | --- | --- | --- |
| Existing intensity option's derived numeric input | Decimal, compatible with existing 12-digit / 4-decimal storage | Team must confirm the input's scientific meaning, canonical unit, allowed range or controlled choices. Do not assume a rainfall measurement from a rank. | Yes | Team to name both | Approved definition and evidence for the exact input and operating mode |
| Existing duration option's derived numeric input | Decimal, compatible with existing 12-digit / 4-decimal storage | Team must validate conversion to the hours consumed by the current method and provide bounds or choices; no invented limits | Yes | Team to name both | Approved duration definition and supporting source |
| Recorded minimum/maximum reference range, if explicitly authorized | Nullable decimals | Definition-specific, minimum <= maximum, relationship to derived input to be specified by the team | Not directly read as numeric inputs today; still requires scientific validation | Team to name both | Evidence for the range and unit |

Recommendation: begin only with individually approved definitions mapped to
existing `ScenarioOption` identities. Do not expose arbitrary names, new units,
area facts, rule conditions, priorities, susceptibility cutoffs, or algorithm
configuration. Labels, ordering, enablement, and classification vocabulary are
not implicitly editable under this proposal. Definition ownership and approval
are separate from merely having a `DataSource` row.

## Smallest proposed persisted design

Use a focused governance module with four concepts, subject to schema review:

1. **ParameterDefinition:** unique immutable parameter code, one-to-one binding
   to an existing option, operating mode, approved type/unit and validation
   constraints, source, named owner/validator, and definition-approval evidence.
   Only reviewed allowlisted input mappings are supported. Freeze the scientific
   definition after approval; changing its meaning requires a separately reviewed
   definition revision and compatibility decision, not a generic portal edit.
2. **ParameterRevision:** immutable payload with definition, sequential positive
   version number, proposed decimal value and any explicitly approved range,
   canonical unit, source, rationale, effective date, creator/time, and previous
   revision. Unique `(definition, version)`; source/history references protected
   against deletion. Every draft correction creates a new revision. No edit or
   delete of historical payloads, even on rollback.
3. **ParameterState:** one row per definition, holding the nullable active-revision
   pointer and a concurrency generation. A database foreign-key constraint must
   ensure that the active revision belongs to that same definition (a composite
   FK to a unique `(definition_id, revision_id)` pair, reviewed in the migration).
   One state row means at most one active revision. Onboarding may have none;
   activation leaves exactly one. No duplicated active flag on historical values.
4. **ParameterEvent:** append-only workflow/audit event referencing a revision
   and definition. Workflow state is the latest valid event for that revision;
   scientific payload remains immutable. Lock the definition/state before
   appending transitions. The audit event is also the persisted workflow event,
   avoiding a second history that can disagree with it.

The reviewed migration must include constraints, protected relationships, and
an explicit immutability strategy for revision/event update/delete (including
technical Admin and command paths). PostgreSQL enforcement and its Django
migration state must be reviewed and tested; model `save()` overrides alone do
not protect against bulk updates. Do not generate that migration at this stage.

Versions are allocated under the definition lock, not `count()+1` without a
lock. Model IDs, filenames, and modification timestamps are never versions.
An active pointer change does not rewrite a revision's value or predecessor.
Activation events identify what they superseded; rollback can reactivate an
eligible historical revision without deleting newer ones.

## Proposed workflow (separate from publication status)

| Action | Preconditions | Result |
| --- | --- | --- |
| Propose | Approved definition; allowed fields, type, unit, source, rationale, effective date | New immutable revision; `DRAFT` event |
| Submit for validation | Complete draft owned by authorized proposer | `VALIDATION_PENDING` |
| Validate | Scientific validation by assigned validator | `VALIDATED`, or `REJECTED` with reason |
| Submit for review | Validated revision and evidence | `REVIEW_PENDING` |
| Review | Assigned review permission and evidence check | `REVIEWED`, or `REJECTED` with reason |
| Approve | Reviewed, still-valid source/definition | `APPROVED`, or `REJECTED` with reason |
| Activate | Approved revision, eligible mode/source, explicit confirmation and authority | Active pointer switches atomically; activation event |
| Retire | Authorized reason; replace an active revision atomically or explicitly suspend definition | `RETIRED`; never silently leave an ineligible active value |
| Roll back | Explicit confirmation of target approved historical revision; eligibility rechecked | Active pointer switches; rollback event preserving all history |

Proposed revisions never affect normal assessment reads. Rejected revisions are
retained; corrections create a fresh draft. Superseded approved revisions remain
eligible rollback candidates only while their definition/source and approval
remain valid. `PublicationStatus` continues to describe publication eligibility;
it is not the validation/review/activation state machine. Demonstration approval
does not convert a demonstration record into official/public assessment data.

Effective dates are recorded metadata. No clock, scheduler, polling, or automatic
activation is proposed. An activation confirmation must show the effective date
and any proposed future-date mismatch; the team must decide whether to reject
future-dated explicit activation. Existing inference behavior is unchanged now.

## Proposed permission matrix

Permission names below are proposed under a future `parameter_governance` app;
**none exists or is assigned by this change**. All operations additionally
require an active authenticated staff account and server-side checks.

| Proposed permission | Authority | Assigned group/person |
| --- | --- | --- |
| `view_parameter_configuration` | Read governed definitions and permitted histories | Team to confirm |
| `propose_parameter_revision` | Create draft and submit own revision | Team to confirm |
| `validate_parameter_revision` | Validate supported scientific definition/value | Team to confirm |
| `review_parameter_revision` | Review evidence and impact | Team to confirm |
| `approve_parameter_revision` | Approve reviewed revision | Team to confirm |
| `activate_parameter_revision` | Explicit approved activation | Team to confirm |
| `rollback_parameter_revision` | Explicit eligible historical rollback | Team to confirm |
| `retire_parameter_revision` | Retire with replacement/suspension decision | Team to confirm |
| `preview_parameter_revision` | Nonmutating demonstration comparison | Team to confirm |

Recommendation for approval: proposer cannot validate, review, or approve their
own revision; approver must be distinct from proposer and validator. Whether the
activator must also be independent requires a team decision. Do not infer that
staff, superuser, research member, or an agency automatically owns these actions.
The implementation must enforce the approved matrix on the backend, including
separation checks; hiding buttons is not authorization.

## Activation, concurrency, rollback, and compatibility

- All eventual writes use CSRF-protected POST, Django validation, explicit
  confirmation, server permissions, and post/redirect/get. Confirmation carries
  expected active revision/generation to reject stale decisions.
- In `transaction.atomic()`, lock affected definition/state rows in stable code
  order, lock/recheck source eligibility and revision approval, then switch the
  pointer and append its event. Concurrent stale activation fails with a helpful
  conflict rather than silently overwriting another decision. Audit failure
  rolls back the pointer update. Related changes approved as one unit must commit
  together; no partially activated intensity/duration bundle.
- Only approved eligible revisions activate: block drafts, pending validation,
  unreviewed, rejected, restricted, retired, or mismatched-mode inputs. Recheck
  eligibility on consumption too, so later source restriction cannot leak data.
- Preserve existing `ScenarioOption` IDs/codes, enum category, API JSON fields,
  numeric/null types and ordering. After explicit onboarding, a shared resolver
  reads the active revision; pending revisions never appear in public options or
  inference. Legacy options retain current behavior until individually onboarded.
  For onboarded definitions with no eligible active revision, return the existing
  unavailable/insufficient-data outcome, not an unapproved legacy fallback.
- Both public option serialization and inference must use that resolver and a
  consistent snapshot of the scenario's selected revisions. The migration must
  not silently adopt legacy values as approved revisions. Any baseline enrollment
  requires explicit source validation and a genuine audit event.
- Existing technical Admin, bulk operations, seed/import paths, and direct
  option mutation routes need reviewed guards before governance goes live; they
  must not bypass the resolver or silently mutate governed values.
- Rollback is a new audited activation of an eligible historical value, with
  reason, expected current pointer, and the same transaction/permission checks.
  It never deletes revisions or retroactively rewrites recorded assessments.

## Audit content and visibility

Each event records actor identity, action, object type and stable identifier,
server timestamp, previous/resulting workflow state, related revision, old/new
active revision IDs where applicable, safe before/after summary, and optional
reason (required for rejection, retirement, rollback). Allow only a generated
request correlation ID if useful. Do not store passwords, tokens, full requests,
IP/location/device history, restricted source notes, or raw rule internals.

Events are committed in the same transaction as the action. Failed actions
produce no success-looking event. Security failure logging, if later needed,
must be separate and privacy reviewed. Historical events are not editable via
the portal. Retain accountable actor references without copying unrelated user
profile data. The team must approve retention and authorized audit viewers.

Do not backfill invented history from `updated_at` or imply that Django Admin
`LogEntry` covers these actions. Day 7 supplies the full event-history interface.
If dashboard events are added earlier, clearly identify custom parameter events
separately from limited technical-maintenance logs. No new audit source exists
in the read-only foundation.

## Demonstration preview after approval

Current inference does not accept safe candidate overrides. Propose an internal
resolver/input boundary that supplies an immutable candidate-value snapshot to
the existing evaluator. Reuse the algorithm; do not duplicate its rules or
temporarily save and revert option values. Normal public calls continue using
the normal active resolver and cannot supply overrides.

Preview permission, approved definition mapping, and designated fictional
`DEMO_ZONE` scenarios are mandatory. Validate all referenced records with the
existing demonstration policy. Compare active/proposed outputs in memory, show
“Demonstration preview,” and expose only safe result summaries, not matched rules,
conditions, priorities, or protected rationale. Do not use real barangays as
demonstration classifications. Do not persist results, activate, publish, or
write successful mutation events for a read-only preview. Unsupported parameter
mappings or missing permitted demonstration fixtures produce an unavailable
state. Preview isolation needs dedicated no-write and public-API regression tests.

## Approval and subsequent verification gate

Before mutation implementation, record team approval of this design, scientific
definitions, named permission assignments, separation requirements, activation
date policy, and preview scope. Data exchange may remain explicitly deferred.
Then create/review migrations and test upgrade from the current schema, immutable
history, every permission/transition, CSRF, concurrency, source revocation,
atomic audit failure, rollback, preview isolation, API compatibility, and Flutter.
Shared/deployed migration or official-data import still needs target-specific
authorization. Day 4 remains **In progress—awaiting governance decisions**.
