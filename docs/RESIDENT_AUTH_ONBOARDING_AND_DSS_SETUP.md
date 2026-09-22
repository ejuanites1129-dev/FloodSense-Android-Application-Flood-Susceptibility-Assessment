# Resident authentication, onboarding, and DSS setup

FloodSense now has a resident authentication shell, versioned setup gates,
account preferences, structured deterministic DSS flows, and a multi-step
assessment. Django Admin authentication remains separate.

## Local setup

From the repository root, after configuring the existing PostgreSQL/PostGIS
environment:

```powershell
& .\server\.venv\Scripts\python.exe -m pip install -r .\server\requirements.txt
Push-Location .\server
& .\.venv\Scripts\python.exe -m manage migrate
Pop-Location

Push-Location .\mobile
flutter pub get
Pop-Location
```

Run migrations only against a local database you are authorized to modify.
Migrations create nullable resident usernames so existing staff/superusers
remain valid. New resident API registrations require a username. Migration
`accounts.0002` stops with an explanatory error if existing emails collide
after case normalization; it does not silently merge accounts.

Migration `accounts.0003` adds clearly labeled **prototype draft** Terms,
Privacy, and onboarding records. It does not publish or approve them. A
qualified reviewer must replace placeholders, review each version, and use the
permission-controlled review/publish workflow before resident acceptance is
required. Until one published Terms version, one published Privacy version,
and one published onboarding version exist, verified residents see a safe
configuration-required screen rather than bypassing setup and entering Home.

Migration `accounts.0004_schedule_account_deletion` adds the nullable deletion
deadline used by the resident-controlled 30-day recovery flow. It preserves
existing deletion records and does not delete any account when the migration is
applied.

## Teammate handoff after pulling this change

Run these commands from the repository root. Keep the teammate's existing
private `server/.env`; never replace it with another developer's file.

```powershell
# Install the updated Python requirements, including django-cors-headers.
& .\server\.venv\Scripts\python.exe -m pip install -r .\server\requirements.txt

# Review and apply the committed database migrations locally.
& .\server\.venv\Scripts\python.exe .\server\manage.py migrate --plan
& .\server\.venv\Scripts\python.exe .\server\manage.py migrate
& .\server\.venv\Scripts\python.exe .\server\manage.py check

# Resolve the Flutter packages already declared by the project.
Push-Location .\mobile
flutter pub get
flutter analyze
flutter test
Pop-Location
```

No Node.js package installation, JavaScript framework, Firebase project, or
new database server is required. Continue using the existing Flutter SDK,
Django virtual environment, PostgreSQL/PostGIS database, and Android SDK. The
new browser preview uses Flutter Web and the same Django API.

To run the browser preview locally:

```powershell
# Terminal 1, from the repository root
& .\server\.venv\Scripts\python.exe .\server\manage.py runserver 127.0.0.1:8000

# Terminal 2
Set-Location .\mobile
flutter run -d chrome --web-hostname localhost --web-port 3000
```

The default development CORS configuration permits only the local web preview
origins on port 3000 and only for `/api/` routes. If Django deliberately runs
on another port, pass the API address to Flutter, for example:

```powershell
flutter run -d chrome --web-hostname localhost --web-port 3000 `
  --dart-define=FLOODSENSE_API_BASE_URL=http://127.0.0.1:8001/api/v1
```

For the Android emulator, start Django on `0.0.0.0:8000`; the default debug
client uses `http://10.0.2.2:8000/api/v1`. A physical Android phone must use a
reachable LAN address supplied through `FLOODSENSE_API_BASE_URL`, and that host
must be included in the teammate's private Django allowed-host configuration.
Web Google sign-in remains intentionally disabled until an approved web OAuth
client is configured; username/email sign-in works in the browser preview.

For deployment, arrange a reviewed daily invocation of the following command.
Do not run it merely to test the interface because it permanently removes due
accounts:

```powershell
& .\server\.venv\Scripts\python.exe .\server\manage.py purge_scheduled_accounts
```

Use `--dry-run` first when validating deployment scheduling. Local development
and ordinary presentations do not need to run the purge command.

## Environment variables

The safe placeholders are in `server/.env.example`:

- `FLOODSENSE_RESIDENT_APP_PUBLIC_URL`: public HTTPS origin used in one-time
  verification and reset links. Local default is `http://localhost:3000`.
- `FLOODSENSE_EMAIL_VERIFICATION_EXPIRY_HOURS`: verification-token lifetime.
- `FLOODSENSE_PASSWORD_RESET_TIMEOUT`: reset-token lifetime in seconds.
- `FLOODSENSE_LOGIN_RATE`, `FLOODSENSE_REGISTRATION_RATE`,
  `FLOODSENSE_PASSWORD_RESET_RATE`, `FLOODSENSE_VERIFICATION_RATE`,
  `FLOODSENSE_GOOGLE_AUTH_RATE`, `FLOODSENSE_TOKEN_REFRESH_RATE`: DRF throttle
  rates.
- `GOOGLE_OAUTH_WEB_CLIENT_ID`: Web/server OAuth client ID accepted as the
  Google ID-token audience. Leave blank to disable Google gracefully.
- `DJANGO_EMAIL_BACKEND`: console backend locally; use the reviewed SMTP
  backend in production.
- `DJANGO_DEFAULT_FROM_EMAIL`, `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT`,
  `DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD`,
  `DJANGO_EMAIL_USE_TLS`, `DJANGO_EMAIL_USE_SSL`: deployment email settings.

Provide the same Web/server client ID to Flutter at build time; it is an OAuth
client identifier, not a client secret:

```powershell
flutter run --dart-define=GOOGLE_SERVER_CLIENT_ID=your-web-client-id.apps.googleusercontent.com
```

Do not put an OAuth client secret, SMTP password, or downloaded credential file
in the Android application or repository.

## Google configuration still required

Code cannot create or approve external credentials. An authorized owner must:

1. Create or select the Google Cloud/Firebase OAuth project.
2. Confirm Android package name `ph.edu.cvsu.bacoor.floodsense`.
3. Register debug and release SHA-1 and SHA-256 signing fingerprints.
4. Create the Android OAuth client for that package/fingerprints.
5. Create the Web/server OAuth client used as the Django audience and Flutter
   `GOOGLE_SERVER_CLIENT_ID`.
6. Configure the Google consent screen and authorized domains as applicable.
7. Configure release signing; the current Android project still uses the debug
   key for its placeholder release build and must not be distributed that way.

The backend verifies token signature, issuer, expiry, audience, verified-email
claim, and immutable `sub`. A matching email never auto-links an existing
password account; Account linking requires password reauthentication.

## Email and public-link configuration still required

Local development prints email to the Django console. Before deployment,
select an authorized SMTP/email provider and secret-management mechanism. Set a
public HTTPS verification/reset origin and make that frontend route forward
the `token`, or `uid` plus `token`, to the corresponding full-page Flutter
destination. The app also exposes manual token entry for development. Do not
put one-time tokens in logs or analytics.

## Resident API

All request and response bodies are JSON. Access tokens are short lived. With
Remember Me enabled, Flutter stores only the refresh token in Android secure
storage; otherwise the refresh token remains in memory for the running app.

| Method and path | Request summary | Response summary |
|---|---|---|
| `POST /api/v1/auth/register/` | `username`, `email`, `password` | verification required; no JWT |
| `POST /api/v1/auth/login/` | `identifier`, `password`, `remember_me` | access/refresh, user, setup stage |
| `POST /api/v1/auth/google/` | verified-provider `id_token`, optional new-user `username` | session or safe linking/setup error |
| `POST /api/v1/auth/token/refresh/` | `refresh` | rotated access/refresh |
| `POST /api/v1/auth/logout/` | `refresh`, authenticated | blacklists refresh |
| `POST /api/v1/auth/password-reset/request/` | `email` | generic non-enumerating response |
| `POST /api/v1/auth/password-reset/confirm/` | `uid`, `token`, `new_password` | one-time reset result |
| `POST /api/v1/auth/email/verify/` | `token` | one-time verification result |
| `POST /api/v1/auth/email/resend/` | `email` | generic response |
| `GET /api/v1/auth/setup-status/` | authenticated | current setup gate |
| `GET /api/v1/auth/legal/required/` | authenticated | unaccepted published versions |
| `POST /api/v1/auth/legal/accept/` | all current `document_version_ids` | next setup gate |
| `GET /api/v1/auth/onboarding/current/` | authenticated | versioned seven-step content |
| `POST /api/v1/auth/onboarding/acknowledge/` | `version` | next setup gate |
| `GET/PATCH /api/v1/account/me/` | optional `username` patch | resident account |
| `GET/PATCH /api/v1/account/preferences/` | approved record IDs and display flags | preferences; no coordinates |
| `POST /api/v1/account/change-password/` | current/new password | result |
| `POST /api/v1/account/google/link/` | password plus Google ID token | linked account |
| `POST /api/v1/account/google/unlink/` | password | no content |
| `POST /api/v1/account/deletion/schedule/` | authenticated | schedules deletion after the configured 30-day grace period |
| `POST /api/v1/account/deletion/cancel/` | authenticated | cancels a scheduled deletion |
| `GET /api/v1/legal/terms/current/` | public | published version or labeled draft preview |
| `GET /api/v1/legal/privacy/current/` | public | published version or labeled draft preview |

Structured DSS remains public and stateless for compatibility:

- `GET /api/v1/dss/flows/start/?mode=demonstration&susceptibility_level=HIGH`
- `POST /api/v1/dss/flows/{code}/{version}/answer/` with `mode`,
  `susceptibility_level`, `question_code`, and `option_code`.

The client owns Back/restart history; the API stores no resident answers. DSS
responses carry source, status, and warning text and cannot modify an
assessment classification.

Resident account deletion is user-controlled rather than an administrator
approval request. Scheduling signs the mobile user out; a successful password
or Google sign-in during the grace period cancels the schedule. Deployment must
run `python manage.py purge_scheduled_accounts` as a reviewed daily maintenance
command to permanently remove due resident accounts. This is server
maintenance, not scenario monitoring or a mobile background timer. The grace
period defaults to 30 days through
`FLOODSENSE_ACCOUNT_DELETION_GRACE_DAYS`; the final retention and backup policy
still requires institutional approval before production use.

No structured DSS flow is silently published by these migrations. Existing
flat `GuidanceItem` behavior remains available for compatibility. An authorized
content reviewer must create a source-backed demonstration or approved flow,
submit it for review, validate its complete branch graph, and publish it before
the new question flow is returned by the start endpoint.

## Production review checklist

Before deployment, authorized reviewers must supply or approve:

- institutional/researcher and privacy contact details;
- final Terms and Privacy language;
- legal/institutional processing basis;
- minimum-age/guardian policy;
- retention, backup, deletion, and research-record policy;
- production hosting domain, HTTPS certificate/proxy settings, allowed hosts,
  and any reviewed web CORS policy;
- SMTP provider and public reset/verification routing;
- Google OAuth project and signing fingerprints;
- official source/provenance records and DSS content.

The Android manifest requests only Internet, coarse location, and fine
foreground location. It does not request background location. Production
Django must run with `DJANGO_DEBUG=false`, a secret `DJANGO_SECRET_KEY`, HTTPS
redirect/cookies/HSTS as reviewed, and explicit production allowed hosts.
