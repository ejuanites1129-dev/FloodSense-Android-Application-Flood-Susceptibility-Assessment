# FloodSense Team Database and Git Workflow

This guide explains how Django code, PostgreSQL/PostGIS databases, administrator
accounts, migrations, demonstration data, and official research data should move
between FloodSense team members.

Use this guide whenever a team member:

- sets up the backend on another computer;
- pulls backend changes from GitHub;
- changes a Django model;
- creates or reviews a migration;
- adds demonstration or official data;
- prepares backend work for a push; or
- asks a coding agent to perform any of those tasks.

The complete first-time Windows installation instructions remain in
[`COMPLETE_WINDOWS_SETUP_GUIDE.md`](COMPLETE_WINDOWS_SETUP_GUIDE.md).

## 1. The central rule

**Git synchronizes the instructions for building the database. It does not
synchronize each developer's local database records.**

The shared repository contains Django models, migration files, import code, and
eventually a repeatable demonstration-data command. Each team member normally
has a separate local PostgreSQL/PostGIS database created from those shared
instructions.

```text
                         GitHub repository
             models + migrations + import/seed code
                    /                         \
                   /                           \
        Developer A computer             Developer B computer
        Django backend                    Django backend
               |                                |
        Local PostgreSQL                 Local PostgreSQL
        Local admin account              Local admin account
        Local runtime records            Local runtime records
```

Consequently, a record manually entered through Developer A's Django Admin does
not automatically appear in Developer B's local database.

## 2. What is shared and what stays local

| Item | Commit to Git? | How teammates receive it |
| --- | --- | --- |
| Django models and application code | Yes | Pull the Git changes |
| Django migration files | Yes | Pull, then run `migrate` locally |
| Tests and validation code | Yes | Pull and run the tests locally |
| Safe seed/import code | Yes | Pull, then run the documented command |
| Safe fictional demonstration files | Yes, if small and approved for Git | Pull and run the import/seed command |
| Local PostgreSQL database | No | Each developer creates their own database |
| Local Django admin account | No | Each developer runs `createsuperuser` |
| `server/.env` and passwords | Never | Each developer creates their own local file |
| Manually entered local Admin records | No | Re-create with seed/import code if they must be shared |
| Database dumps | Normally no | Use only through an explicitly agreed backup process |
| Confidential, restricted, or personally identifiable research data | Never in ordinary Git | Store in an approved restricted location |

Different local database passwords do not cause schema misalignment. They are
connection credentials only. The migration history determines whether database
structures match.

## 3. Django equivalents of common PHP/Laravel commands

| Purpose | FloodSense Django command |
| --- | --- |
| Detect model changes and create migration instructions | `python manage.py makemigrations` |
| Apply committed database migrations | `python manage.py migrate` |
| Preview migrations that Django plans to apply | `python manage.py migrate --plan` |
| View applied and unapplied migrations | `python manage.py showmigrations` |
| Create a local administrator | `python manage.py createsuperuser` |
| Load a Django fixture | `python manage.py loaddata file.json` |
| Start the backend | `python manage.py runserver` |

Django has no mandatory built-in `db:seed` command. FloodSense will use a custom,
idempotent management command for its shared fictional demonstration data. The
intended command name is:

```powershell
server\.venv\Scripts\python.exe server\manage.py seed_demo
```

**Current status:** Day 6 implements and tests `seed_demo`. It creates only the
reserved fictional demonstration dataset, is transactional and idempotent,
and stops on unsafe stable-code or active-ruleset conflicts. It must be run only
against an explicitly authorized local development database. Manually created
Admin records still remain local unless a reviewed seed/import process owns
them.

"Idempotent" means that running the command again updates or reuses the same
demonstration records instead of creating duplicates.

## 4. First-time backend setup on each computer

Run commands from the repository root. Each team member must create their own
virtual environment and `server/.env`.

### 4.1 Install Python packages

```powershell
python -m venv server\.venv
server\.venv\Scripts\python.exe -m pip install --upgrade pip
server\.venv\Scripts\python.exe -m pip install -r server\requirements.txt
```

### 4.2 Create the local PostgreSQL/PostGIS database

In PostgreSQL, create a local login and database and enable PostGIS. A teammate
may use a different local password from everyone else.

```sql
CREATE USER floodsense WITH PASSWORD 'choose-a-local-password';
CREATE DATABASE floodsense OWNER floodsense;
\c floodsense
CREATE EXTENSION IF NOT EXISTS postgis;
```

Copy `server/.env.example` to `server/.env`, then place that computer's local
database password in `DATABASE_PASSWORD`. Never commit `server/.env`.

### 4.3 Build the local schema and create the local administrator

```powershell
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe server\manage.py migrate
server\.venv\Scripts\python.exe server\manage.py createsuperuser
```

Each person should use their own email address for their local administrator.
Creating another superuser does not change models or migration files.

## 5. Safe routine after pulling from GitHub

Before pulling, protect unfinished local work. Check the working tree:

```powershell
git status
```

If files are modified, commit the intended work to the correct feature branch or
stash it before pulling. Do not discard another person's work or use destructive
Git commands to force a pull.

After a successful pull, run the following from the repository root:

```powershell
server\.venv\Scripts\python.exe -m pip install -r server\requirements.txt
server\.venv\Scripts\python.exe server\manage.py migrate --plan
server\.venv\Scripts\python.exe server\manage.py migrate
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe -m pytest server
```

If a tested `seed_demo` command exists and its documentation says that the seed
version changed, run:

```powershell
server\.venv\Scripts\python.exe server\manage.py seed_demo
```

If Flutter dependencies changed, also run:

```powershell
Set-Location mobile
flutter pub get
flutter analyze
flutter test
Set-Location ..
```

Do not run `makemigrations` merely because new migration files were pulled.
`migrate` applies migrations; `makemigrations` creates new ones and is needed
only when a developer intentionally changes Django models.

## 6. Workflow when changing Django models

Migration files are shared schema history and must be treated as source code.

1. Pull the latest branch before beginning the model change.
2. Confirm which teammate owns the model change and Django app.
3. Change the model and related tests.
4. Create a clearly named migration.
5. Review the generated migration file.
6. Apply it to the local database.
7. Run checks and tests.
8. Commit the model, migration, and tests together.

Example:

```powershell
server\.venv\Scripts\python.exe server\manage.py makemigrations geography --name add_susceptibility_zone
server\.venv\Scripts\python.exe server\manage.py migrate --plan
server\.venv\Scripts\python.exe server\manage.py migrate
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe -m pytest server
```

Do not:

- delete an existing migration because it has already been applied locally;
- edit old shared migrations to hide a new model change;
- create two unrelated migrations with the same dependency without reviewing
  the resulting migration graph;
- mark migrations as applied with `--fake` unless the team has verified the
  schema and deliberately approved that recovery action; or
- commit a local database dump instead of a migration.

If two branches create migrations from the same parent migration, Django may
report conflicting migration leaves. Do not choose a random file to delete.
The developers must first compare both model changes, preserve both, and then
create/review a merge migration where appropriate.

## 7. Admin accounts and Admin-entered data

### Local development databases

Every developer creates their own superuser. Those accounts can use different
emails and passwords because they exist in separate databases.

Manually entered records are useful for short experiments, but they are not a
team synchronization method. If all developers need the same record, represent
it through a reviewed seed/import command or fixture.

### A future shared development or staging database

If the team later uses one hosted backend and shared database:

- all administrators will be rows in the same `accounts_user` table;
- each administrator must use a unique email address;
- the backend administrator creates staff accounts and permissions centrally;
- developers must not run experimental destructive migrations or imports
  against that shared database;
- backups and deployment migrations must be assigned to one responsible person;
  and
- Flutter clients should communicate with the shared Django API, not connect
  directly to PostgreSQL.

A shared database is useful for integration demonstrations, but local databases
remain preferable for ordinary development and tests.

## 8. FloodSense application data flow

Runtime application data moves through the backend, not through Git:

```text
Django Admin or approved import
              |
              v
      Django validation/ORM
              |
              v
       PostgreSQL/PostGIS
              |
              v
      Django REST API/Expert System
              |
              v
        Flutter Android application
```

The Flutter application must never connect directly to PostgreSQL or contain the
database password. It communicates with Django API endpoints. Django performs
validation, authorization, Expert System evaluation, DSS selection, and database
access.

## 9. Demonstration-data workflow

Until official and expert-validated Bacoor data are available, the project may
use fictional data only when it is clearly labeled:

> DEMONSTRATION DATA - NOT OFFICIAL BACOOR FLOOD INFORMATION

The repeatable seed process should eventually create items such as:

- fictional `Demo Zone A`, `Demo Zone B`, and similar geometries;
- proposed rule sets intended only to exercise forward chaining;
- sample susceptibility results;
- sample DSS preparedness guidance; and
- provenance showing that every item is synthetic and unapproved.

The Day 6 seed command is safe to run repeatedly and refuses to take over
reserved identities owned by another source, including a different
demonstration source. Its database-backed tests verify idempotence, atomic
conflicts, geometry, and preservation of unrelated non-demonstration records.

Do not assign invented susceptibility classes to real Bacoor barangays. If a real
place name is needed for interface layout, the assessment must return
`Insufficient Data` until the supporting source and rules are approved.

## 10. Official research-data workflow

Official datasets should follow a controlled path:

```text
Original agency file
        |
        v
Restricted/raw preservation + checksum + source record
        |
        v
Documented normalization (units, time, CRS, missing values)
        |
        v
Validation by the assigned researcher/expert
        |
        v
Approved import command
        |
        v
PostgreSQL/PostGIS + provenance records
```

Rules:

1. Preserve the original file unchanged.
2. Record the provider, coverage, date received, license/restrictions, CRS,
   units, missing-data meaning, and processing history.
3. Keep confidential, restricted, or personally identifiable files outside the
   ordinary Git repository.
4. Normalize data with reviewed scripts instead of undocumented manual edits.
5. Make imports transactional and idempotent where practical.
6. Never replace an approved dataset silently; create a new version and retain
   its provenance.
7. Back up a shared database before a large or irreversible import.

## 11. Before pushing backend work

Review the proposed commit:

```powershell
git status
git diff
```

Then verify the backend:

```powershell
server\.venv\Scripts\python.exe server\manage.py makemigrations --check
server\.venv\Scripts\python.exe server\manage.py migrate --plan
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe -m pytest server
```

If models intentionally changed, first generate and review the required
migration as described in Section 6; afterward `makemigrations --check` should
report no missing model changes.

Before committing, verify that the selected files do not contain:

- `server/.env`;
- passwords, secret keys, or access tokens;
- local database dumps;
- private participant/interview information;
- agency data that the team is not allowed to redistribute; or
- generated virtual-environment, build, or cache files.

Commit only the files belonging to the task. Push through the team's agreed
branch and review process. Do not overwrite the main branch or another
developer's work to resolve a conflict.

## 12. Recovery and troubleshooting

### "No migrations to apply"

This is normal when the local database has already applied every committed
migration. Confirm with:

```powershell
server\.venv\Scripts\python.exe server\manage.py showmigrations
```

### "Table already exists" or migration history differs

Stop before deleting tables or migration files. Capture:

```powershell
git status
server\.venv\Scripts\python.exe server\manage.py showmigrations
server\.venv\Scripts\python.exe server\manage.py migrate --plan
```

Compare the checked-out migration files with the database's applied migration
history. Ask the team member responsible for the migration before using
`--fake`, manually changing the schema, or recreating the database.

### A teammate cannot see an Admin record

First determine whether both developers use separate local databases. If so,
that is expected. Convert the required shared record into seed/import code, or
test together against an explicitly designated shared backend.

### The local admin login does not work after a pull

Pulling does not transfer users or passwords. Create or reset a local account:

```powershell
server\.venv\Scripts\python.exe server\manage.py createsuperuser
```

or:

```powershell
server\.venv\Scripts\python.exe server\manage.py changepassword person@example.com
```

## 13. Required coding-agent behavior

When an agent works on FloodSense backend, database, GIS, Admin, Expert System,
DSS, migration, seed, or import tasks, it must:

1. inspect `git status` before changing files;
2. preserve unrelated and uncommitted user changes;
3. read this guide and the relevant setup/data documentation;
4. treat committed migration files as the shared schema history;
5. create and commit a migration whenever an intentional model change requires
   one;
6. never assume that local Admin records are available to another developer;
7. never commit `.env`, credentials, database dumps, or restricted research data;
8. keep provisional data visibly separated from approved data;
9. run proportionate checks and tests before reporting completion;
10. report exactly which migrations, commands, and data imports another teammate
    must run after pulling; and
11. execute `git pull`, `git push`, shared-database migrations, or shared-data
    imports only when the user has explicitly requested the corresponding Git or
    deployment operation.

This guide is the team source of truth for database collaboration. If the actual
repository implementation changes, update this document in the same pull request
or commit.
