# FloodSense Day 2: Database and Admin Guide

**Official research title:**\
**FLOODSENSE: AN ANDROID-BASED EXPERT SYSTEM FOR FLOOD SUSCEPTIBILITY ASSESSMENT AND PRE-EVENT PREPAREDNESS IN BACOOR CITY**

## Day 2 outcome

Day 2 converts the Day 1 blueprint into real Django models, PostgreSQL/PostGIS
tables, migrations, and Django Admin screens. It creates empty, governed
containers for future demonstration and official information. It does not add
official-looking Bacoor classifications or unverified rainfall thresholds.

## What now exists

### Provenance

`DataSource` records where information came from, its coverage, permitted use,
review status, reviewer, and whether it may be publicly released.

The shared status choices are:

- `DEMONSTRATION`
- `PENDING_VALIDATION`
- `APPROVED`
- `RESTRICTED`
- `RETIRED`

New records default to `DEMONSTRATION` and not publicly releasable. This is a
safe default: information cannot accidentally appear approved simply because
someone created a row.

### Geography

`GeographicArea` stores a polygon or multipolygon in WGS 84 (`SRID 4326`). The
first prototype will use neutral fictional shapes such as Demo Zone A.

`AreaFact` stores one typed fact about an area. A fact must contain exactly one
of:

- a controlled text value; or
- a numeric value with an optional unit.

Every area and fact links back to a `DataSource` and carries a publication
status.

### Expert System

`ScenarioOption` stores controlled rainfall-intensity or rainfall-duration
choices. Numeric ranges are optional because the project must not invent
official thresholds while validation is pending.

`SusceptibilityLevel` stores only the four study results:

- Low
- Moderate
- High
- Very High

`RuleSet` versions a collection of Expert System knowledge. At most one ruleset
may be active for demonstration mode and one for official mode. An active
demonstration ruleset must have demonstration status; an active official
ruleset must be approved.

`ExpertRule` stores the THEN portion of a rule: the result level, geographic
scope, priority, rationale, and source.

`ExpertRuleCondition` stores controlled IF conditions. The initial supported
condition forms are:

- selected intensity option equals a configured option;
- selected duration option equals a configured option;
- an area text fact equals a configured value; and
- an area numeric fact satisfies `=`, `>`, `>=`, `<`, or `<=`.

The database stores only declarative conditions. It never stores executable
Python code or unrestricted expressions.

### Decision Support System

`GuidanceItem` stores a reviewed preparedness instruction associated with a
susceptibility level. It is deliberately separate from Expert System rules, so
guidance cannot change the classification.

## Why some diagram entities were not created

The initial diagrams describe the broader intended system and will evolve.
Day 2 implements only what is required for the first end-to-end demonstration.
The following are deliberately deferred:

- persistent assessment history and exact resident locations;
- approval-workflow dashboards;
- notification records;
- evacuation routing;
- official sensor-observation imports;
- a complete 25-entity research ERD; and
- resident account APIs.

This keeps the first implementation understandable and testable. Deferred
features can be added with reviewed migrations when the core flow works.

## How to inspect the containers in Django Admin

1. Start PostgreSQL if it is not already running.
2. From the repository root, start Django:

   ```powershell
   server\.venv\Scripts\python.exe server\manage.py runserver 0.0.0.0:8000
   ```

3. Open <http://127.0.0.1:8000/admin/>.
4. Sign in with your local Django superuser.
5. Confirm that Admin contains groups for:

   - Provenance — Data sources
   - Geography — Geographic areas and Area facts
   - Expert — Scenario options, Susceptibility levels, Rule sets, Expert rules,
     and Expert rule conditions (technical model registration for controlled
     development; raw rule controls are not exposed to ordinary custom-portal
     administrators)
   - DSS — Guidance items

The Admin labels may use Django's automatic pluralization until more
user-friendly labels are added later.

## Required entry order for demonstration data

Do not enter real or unofficial Bacoor classifications. When Day 3 creates the
reviewed demonstration fixtures, their dependency order will be:

1. Create one clearly named demonstration `DataSource`.
2. Create the four controlled `SusceptibilityLevel` records linked to that
   source and marked demonstration.
3. Create symbolic intensity and duration `ScenarioOption` records.
4. Create neutral `GeographicArea` records such as Demo Zone A.
5. Add only fictional `AreaFact` records if the demonstration rules need them.
6. Create one demonstration `RuleSet` and activate it.
7. Create `ExpertRule` records under the ruleset.
8. Add all required `ExpertRuleCondition` records under each rule.
9. Create `GuidanceItem` records for each result level.

The inference engine is not implemented on Day 2. These records therefore do
not produce an API assessment yet; they are the managed inputs for Day 3.

## Migration workflow for every teammate

The committed migration files define the shared database structure. The actual
rows and local superusers do not travel through Git.

After pulling these Day 2 changes, a teammate must run:

```powershell
server\.venv\Scripts\python.exe server\manage.py migrate
server\.venv\Scripts\python.exe server\manage.py check
```

They should not create another migration unless they intentionally change a
model. They must not delete or rewrite these initial migrations to repair one
computer's local database.

## Day 2 verification commands

From the repository root:

```powershell
server\.venv\Scripts\python.exe -m ruff check server
server\.venv\Scripts\python.exe server\manage.py makemigrations --check --dry-run
server\.venv\Scripts\python.exe -m pytest -q
server\.venv\Scripts\python.exe server\manage.py check
```

Expected outcome:

- no code-quality errors;
- no missing migrations;
- all tests pass; and
- Django reports no system-check issues.

## Day 2 acceptance checklist

- [x] Provenance source container exists.
- [x] PostGIS geographic-area container exists.
- [x] Typed area-fact container exists.
- [x] Rainfall scenario-option container exists without invented thresholds.
- [x] The four susceptibility-level choices are enforced.
- [x] Versioned rulesets, rules, and controlled conditions exist.
- [x] DSS guidance is stored separately from Expert System conclusions.
- [x] All containers are manageable through Django Admin.
- [x] Reviewed initial migrations exist and are applied locally.
- [x] Tests and code-quality checks pass.
- [x] No official-looking Bacoor data or restricted agency data were added.

## Next step: Day 3

Day 3 will implement the deterministic inference service and tests for:

- successful classification;
- geographic and explicit-priority rule precedence;
- equal-ranking conflicts returning `UNCERTAIN`;
- no match returning `INSUFFICIENT_DATA`;
- separation of demonstration and official modes; and
- an explanation trace showing the rules and facts used.

Demonstration fixtures or a verified `seed_demo` command should be added only
when the engine's expected inputs and safety checks are final. Until that
command actually exists in the code, no teammate or agent should claim that it
can be run.
