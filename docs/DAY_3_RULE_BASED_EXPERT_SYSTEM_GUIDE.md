# FloodSense Day 3: Deterministic Rule-Based Expert System

**Official research title:**  
**FLOODSENSE: AN ANDROID-BASED EXPERT SYSTEM FOR FLOOD SUSCEPTIBILITY
ASSESSMENT AND PRE-EVENT PREPAREDNESS IN BACOOR CITY**

## Day 3 outcome

Day 3 adds a database-driven inference service. It accepts a selected area and
two hypothetical rainfall scenario options, assembles facts, evaluates eligible
stored rules, and returns an explainable classification or limitation state.

The implementation does not contain scientific thresholds or a built-in rule
table. The four demonstration thresholds appear only in database-backed tests.
No demonstration rows, official classifications, APIs, DSS selection, Flutter
features, or GIS point-in-polygon assessment are added on Day 3.

## Minimal schema alignment

Migration `expert.0002_add_derived_scenario_facts` makes two focused changes:

1. `ScenarioOption.derived_value` stores the numeric fact represented by an
   option. Demonstration intensity options may store ranks 1–5 and duration
   options may store hours such as 1, 3, 6, 12, or 24. `display_order` remains
   presentation-only and is never treated as an inference fact.
2. `ExpertRuleCondition` gains `INTENSITY_RANK` and `DURATION_HOURS` condition
   types. Both use `expected_number` and one of the controlled numeric
   operators.

Derived-input conditions reject a scenario option, text expectation, or area-
fact key. Exact intensity-option and duration-option equality conditions remain
supported.

## Service entry point

Future views and APIs should call the service rather than reproduce inference
logic:

```python
from expert.services import evaluate_assessment

result = evaluate_assessment(
    area_identifier=area_id_or_code,
    intensity_code="DEMO_MODERATE",
    duration_code="DEMO_1_HOUR",
    mode="demonstration",
)
```

`area_identifier` accepts a database primary key or stable area code. Mode is
case-insensitive and must be `demonstration` or `official`. An unknown,
disabled, wrong-category, or mode-ineligible selected record raises
`AssessmentInputError`, a Django `ValidationError` subclass with field-specific
messages. Missing stored inference data produces an `INSUFFICIENT_DATA` result
instead of an exception or default classification.

## Fact conversion

After validating the selected records, the service assembles these required
facts:

| Fact | Database source |
| --- | --- |
| `zone_code` | `GeographicArea.code` |
| `zone_baseline_rank` | Enabled numeric `AreaFact` with that key |
| `rainfall_intensity_code` | Selected intensity option code |
| `rainfall_intensity_rank` | Selected intensity option `derived_value` |
| `rainfall_duration_hours` | Selected duration option `derived_value` |

The result also includes `rainfall_duration_code` and every other enabled,
mode-permitted area fact. If the baseline fact is absent, nonnumeric, or
ambiguous, or either selected option lacks `derived_value`, evaluation returns
`INSUFFICIENT_DATA`.

An area fact cannot override a request-derived fact with the same key.
Demonstration evaluation uses only demonstration records backed by a
demonstration source. Official evaluation uses only approved records backed by
an approved, publicly releasable, non-demonstration source.

## Rule eligibility and condition evaluation

The service selects the one active, mode-permitted ruleset. No usable active
ruleset returns `INSUFFICIENT_DATA`. It then loads only enabled rules that:

- belong to that ruleset;
- are global or scoped to the selected area;
- have the required status and permitted source for the mode; and
- conclude with an enabled, mode-permitted susceptibility level.

A rule with no enabled conditions never matches. Otherwise, every enabled
condition must match. Disabled conditions are ignored.

| Condition type | Actual value | Supported operator |
| --- | --- | --- |
| `INTENSITY_OPTION` | Selected intensity option | `EQ` |
| `DURATION_OPTION` | Selected duration option | `EQ` |
| `AREA_FACT_TEXT` | Text area fact selected by `fact_key` | `EQ` |
| `AREA_FACT_NUMBER` | Numeric area fact selected by `fact_key` | `EQ`, `GT`, `GTE`, `LT`, `LTE` |
| `INTENSITY_RANK` | `rainfall_intensity_rank` | `EQ`, `GT`, `GTE`, `LT`, `LTE` |
| `DURATION_HOURS` | `rainfall_duration_hours` | `EQ`, `GT`, `GTE`, `LT`, `LTE` |

Operators are mapped to fixed Python comparison functions. The service never
uses `eval`, executes database content, or silently treats an unsupported or
malformed condition as true.

## Precedence, conflicts, and no-match behavior

All eligible matching rules are considered before a conclusion is selected:

1. An area-scoped rule outranks every global rule.
2. Within the same geographic specificity, the greater explicit `priority`
   wins.
3. If all equally ranked top rules have the same conclusion, the service
   returns `CLASSIFIED` and reports every supporting top rule code.
4. If equally ranked top rules have different conclusions, the service returns
   `UNCERTAIN` and reports every conflicting top rule code.
5. If no eligible rule matches, the service returns `INSUFFICIENT_DATA`.

The service never falls back to Low or any other default susceptibility level.

## Result structure

The service returns a serializable Python dictionary with this stable shape:

```text
assessment_state: CLASSIFIED | UNCERTAIN | INSUFFICIENT_DATA
susceptibility: null | {code, label, map_color}
area: {id, code, name}
scenario: {rainfall_intensity_code, rainfall_duration_code}
facts: {fact_name: value, ...}
matched_rule_codes: [rule_code, ...]
explanation:
  summary: human-readable matching or limitation explanation
  matched_rule_codes: [rule_code, ...]
  facts_used: ["fact=value", ...]
  rule_rationales: [stored rationale, ...]
  ruleset: "name vversion" | null
  warnings: [warning, ...]
ruleset: null | {name, version}
operating_mode: DEMONSTRATION | OFFICIAL
data_status: DEMONSTRATION | APPROVED
warnings: [warning, ...]
```

Every demonstration result includes:

- `DEMONSTRATION DATA—NOT OFFICIAL`
- `This result is not an official flood forecast, warning, or emergency instruction.`

The second warning also remains on official-mode results because even approved
susceptibility logic is not an official forecast or emergency instruction.

## Automated coverage

The database-backed service tests create all records inside the test database.
They do not depend on local Admin rows, fixtures, or a `seed_demo` command. The
suite covers:

- Low, Moderate, High, and Very High demonstration results;
- no match and missing stored facts;
- invalid, disabled, wrong-category, and mode-ineligible selections;
- missing or unusable active rulesets;
- inactive rules, disabled conditions, and empty rules;
- geographic specificity, priority, conflicts, and same-result ties;
- strict demonstration/official separation;
- all five numeric comparison operators;
- exact scenario and text area-fact conditions;
- invalid derived-condition field combinations;
- explanation content and permanent warnings; and
- a changed stored area fact changing the result without Python changes.

Because these are real Django database tests, the configured PostgreSQL test
role must be able to create and remove the isolated `test_floodsense` database,
or the team must provide an equivalent dedicated test database configuration.
Do not point the test runner at a shared or deployed database.

## Verification commands

Run from the repository root:

```powershell
server\.venv\Scripts\python.exe -m ruff check server
server\.venv\Scripts\python.exe server\manage.py makemigrations --check --dry-run
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe -m pytest -q
server\.venv\Scripts\python.exe server\manage.py migrate --plan
```

`migrate --plan` is an inspection step. Do not apply project migrations to a
shared or deployed database unless the responsible team member explicitly
authorizes that target.

## What teammates run after pulling

No Python dependency changed. Each teammate should reuse their virtual
environment, then run:

```powershell
server\.venv\Scripts\python.exe -m pip install -r server\requirements.txt
server\.venv\Scripts\python.exe server\manage.py migrate --plan
server\.venv\Scripts\python.exe server\manage.py migrate
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe -m pytest -q
```

Migrations and tests affect each teammate's local database environment; Git
does not synchronize local database rows or administrators. Day 3 does not add
any data import or seed command.

## Remaining Day 3 limitations

- Rules and demonstration records must still be entered manually until a later,
  explicitly reviewed seeding task is implemented.
- No assessment API calls the service yet.
- The DSS does not yet select guidance.
- Flutter and the dynamic map do not yet consume results.
- Area selection uses an identifier; coordinate point-in-polygon resolution is
  deferred.
- All demonstration ranks and test rules remain fictional and scientifically
  unvalidated.
