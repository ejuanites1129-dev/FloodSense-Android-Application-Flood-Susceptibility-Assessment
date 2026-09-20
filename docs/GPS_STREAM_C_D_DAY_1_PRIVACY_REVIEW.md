# GPS Streams C/D Day 1 privacy and threat review

**Reviewed:** 20 September 2026. **Scope:** checked-in application code and local
framework behavior. This is engineering evidence, not a legal review or a
deployed-infrastructure certification. Optional foreground GPS is the current
safe team direction; final adviser acceptance/requirement remains unresolved.

Related artifacts: [frozen contract](../server/evacuation/NEAREST_CENTER_CONTRACT.md),
[baseline and ownership](GPS_STREAM_C_D_DAY_1_BASELINE.md).

## Collection and in-memory lifetime

Inspected `mobile/lib/features/location/location_card.dart`,
`location_controller.dart`, `location_service.dart`,
`geolocator_location_service.dart`, and `location_copy.dart`.

The user-triggered UI presents the purpose/privacy dialog before calling
`continueAfterPurposeExplanation()`. The controller checks service/permission
state and requests foreground permission only in the explicit acquisition flow.
The adapter calls `getCurrentPosition` once with accuracy/timeout settings;
there is no position subscription, background polling, or last-known-position
fallback. Manual pin and barangay selection and a clear-location action exist.
Coordinates stay in controller/session memory and are cleared on reset/dispose;
generation checks discard stale asynchronous results.

The app's source Android manifest declares Internet and coarse/fine location,
not background location. It removes the geolocator helper's optional foreground
service type. This is source evidence, not a newly verified merged APK or a
physical-device privacy audit. The plugin helper's presence is not evidence of
a continuous location service. Day 7 must inspect the release manifest/runtime.

Existing purpose copy describes barangay lookup only. **Stream A/D handoff:**
before the center HTTP adapter ships, explain that the confirmed temporary
coordinate may also be sent to find approximate center distances. Preserve
manual choice and describe third-party basemap traffic accurately. No mobile
copy or production provider was changed in Day 1.

## Transport and application persistence

`mobile/lib/data/api/floodsense_api_client.dart` sends existing resolver
coordinates in JSON POST bodies using `_postJson`; those calls put no coordinate
in the route, query, headers, or authentication token. This proves existing
resolver behavior only. There is no production nearest-center adapter to test.
The frozen center contract applies the same body-only restriction and disallows
a user-coordinate echo. Returned facility coordinates are distinct from the
submitted user coordinate. The existing barangay resolver still returns its
documented rounded coordinate echo; this review does not claim otherwise.

`server/config/settings.py` enables HTTPS redirect and secure session/CSRF cookies
when `DEBUG` is false, with configurable HSTS and proxy HTTPS handling. The
Windows setup guide uses HTTP for local development and requires HTTPS for the
deployed API. The repository does not establish actual TLS termination, proxy
header sanitization, allowed hosts, or deployment environment values. The proxy
must strip untrusted `X-Forwarded-Proto` before setting its trusted value.

Inspected account model, assessment views/service, geography views/services,
evacuation model/workflow, and portal audit calls. The account has a
`home_barangay` label, not precise coordinate fields. Current assessment code
does not write coordinate history. Geography performs temporary lookups. The
evacuation table's latitude/longitude are facility coordinates, not a lookup
history. Portal `LogEntry` calls record center/source maintenance actions and
actor/object references, not GPS lookups or raw request bodies. Those existing
administrative logs do contain administrator identity and object labels; they
are not public API fields.

No application analytics/crash-reporting integration or location-history writer
was found in the inspected Python/Dart code and dependency manifests. This is
not proof about operating-system services, installed infrastructure agents, or
future packages. The Day 1 constants/serializers/tests perform no ORM queries
or writes. Database access is blocked during the new pure contract tests.
The future service/view's SELECT-only behavior still needs Day 2/3 query capture
and Day 5 persistence/audit regression tests.

**Retention boundary:** Day 1 authorizes no user-location history model, event,
cache, file, log payload, analytics record, or screenshot. Request-lifetime
memory needed to validate/query is temporary. Responses must use `no-store`;
do not cache results keyed by precise user coordinates. This is a future endpoint
requirement, not an implemented header today.

## Logging and failure review

`server/config/settings.py` configures only standard Django security, session,
common, CSRF, authentication, messages, clickjacking, and WhiteNoise middleware.
It defines no custom `LOGGING` or DRF `EXCEPTION_HANDLER`. Repository searches
found no custom request-body logger, request-tracing middleware, Sentry,
Crashlytics, or analytics integration in the inspected application paths.
There is no checked-in deployed reverse-proxy logging configuration.

This narrow finding does **not** mean all framework logging is safe. Inspection
of the installed DRF exception handler shows that handled API errors become DRF
responses while unhandled exceptions propagate. Django's installed default
logging includes server/console logging and an `AdminEmailHandler` error path.
Debug exception pages/reports, exception locals, JSON parse messages, and debug
SQL/query capture can disclose coordinates even without a custom body logger.
No claim is made that error email is configured or that such a disclosure has
occurred. Day 3 must normalize parse/media/method/internal errors and avoid
coordinate-bearing exception logging; Day 5 must test the real middleware and
failure paths. Production must disable DEBUG and review error reporting,
database statement/parameter logging, APM sampling, and access-log formats.

The new serializers return field-keyed DRF errors with generic wording. Unknown
keys are rejected with a fixed `non_field_errors` message so a coordinate used
as an unknown key is not reflected. Tests use synthetic values to verify error
non-reflection and rejection of private response fields. Their validation is
not a proof that arbitrary public text is free of sensitive content: record
release review and literal-text rendering remain required.

## Threat register

| Threat | Entry point | Impact | Existing control/evidence | Remaining action | Owner/day |
| --- | --- | --- | --- | --- | --- |
| Silent or continuous collection | Mobile permission/location APIs | Unexpected tracking | Purpose dialog, explicit flow, one-shot adapter, foreground manifest | Recheck merged release manifest and device lifecycle | A/D, 5 and 7 |
| Center lookup beyond explained purpose | Existing barangay-only explanation | User cannot make an informed location choice | Manual fallback and confirmation exist | Expand purpose copy before production adapter | A/D, 3–4 handoff |
| Coordinates in access logs/history | URL/query/header/token | Location disclosure | Existing resolver uses POST body; center contract forbids URL values | Verify adapter and proxy/access-log behavior | A/C/D, 3 and 5 |
| Request-body capture | Proxy/WAF/APM/tracing | Precise location retained externally | No custom repository body logger found | Obtain actual configurations and redacted evidence | D/deployment owner, 5–7 |
| Exceptions/debug SQL expose input | Parser, DB error, debug page, error mail | Input, SQL, paths or locals disclosed | Generic contract errors; resolver catches service failures | Implement center failure boundary; inspect reporters, SQL logs and DEBUG | C/D, 3 and 5 |
| Persisted user location | DB, session, analytics, cache | Location history | No center lookup implementation; pure serializers do not write | SELECT-only/table/audit tests; no-store response; inspect middleware | C/D, 2–5 |
| Stale authorization leaks facilities | Source release changes after verification | Restricted/ineligible output | Separate source approval/release and center workflows | Per-request join/gate evaluation and regression tests | C, 2–4 |
| Private metadata leaks | Broad model serialization | Contact, notes, audit/user disclosure | Explicit strict public schema; private-field rejection tests | Build explicit safe mappings, release review, endpoint tests | C/D, 2–5 |
| Text executes as markup | Name/address/source/limitations | XSS or misleading content | Literal-text contract; portal templates use escaped output | Verify API-to-client and portal XSS cases | A/C/D, 3–5 |
| False operational certainty | Distance cards/warnings | User interprets proximity as safety/open status | Frozen warning/limitation text; no capacity field | Preserve warnings through provider and UI; review authorized content | A/C/D, 4 |
| Basemap reveals approximate viewport | Third-party tile requests | Network observer/provider infers area | Attribution exists; coordinates are not sent as API query strings | Review tile-provider traffic, policy/caching, and disclosure | A/D, 5–7 |
| Screenshots expose real location | Emulator, crash tools, thesis capture | Retained coordinates/accounts | No real coordinate or screenshot collected in this task | Use simulated locations; review capture automation/redaction | D/all, 5–7 |
| Abuse overwhelms public lookup | Oversized requests/repetition | Resource exhaustion | Strict input/result limits frozen | Agree body/rate controls and test before exposure | C/D, 3 and 5 |

## Evidence capture and deployment gaps

Only synthetic in-memory contract examples were added; they explicitly label
fictional facilities/identities. No real facility rows were created/imported.
For later screenshots use simulated emulator coordinates or clearly fictional
fixtures, and exclude tokens, account details, private contacts and internal
notes. Never capture real user coordinates, raw request traces or SQL parameters
as thesis evidence. Automated capture/crash tools require the same restriction.

Missing deployment evidence: actual HTTPS/proxy/host configuration; reverse-proxy,
WAF, CDN and load-balancer log formats/retention; APM and crash-report sampling;
error-email/report settings; database logging; release APK permissions; real
device and end-to-end no-write tests; operational public-content authorization.
These remain open actions, not evidence of a known deployed incident. Day 1's
repository review is complete; end-to-end privacy certification is not.
