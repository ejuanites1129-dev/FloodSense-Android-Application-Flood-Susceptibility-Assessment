# Start and stop FloodSense on Windows

Use this guide to run the checked-out project locally from **VS Code's PowerShell terminal**. It covers first-time preparation, everyday startup, Android and browser testing, and shutdown. It is not a production deployment guide.

**Startup order:** PostgreSQL → Django API and Admin → Android emulator or phone → Flutter app.

For temporary source/evacuation-center tests in the **main** local workflow, use
[this setup](docs/LOCAL_TESTING_WORKFLOW.md) and `scripts/run_android_local.ps1`.
It reads the configured Mapbox token and current connected device automatically;
the old separate center-preview launcher is not needed.

**Shutdown order:** Flutter app → emulator and optional Android tools → Django → PostgreSQL, if you want to stop the local database service.

## 1. What needs to run?

| Component | Purpose | How it runs |
| --- | --- | --- |
| PostgreSQL with PostGIS | Stores application records and geographic data | Windows service, normally on port `5432` |
| Django | Serves the API, custom Admin portal, and technical Django Admin | One terminal running `runserver`, on port `8000` |
| Android emulator or USB phone | Runs the Android application | Android SDK emulator or connected device |
| Flutter | Builds the app and keeps its debug session connected | A separate terminal running `scripts/run_android_local.ps1` for Android Mapbox |
| Flutter browser preview (optional) | Runs the resident interface in Chrome | Another Flutter session on port `3000` |

The custom Admin panel does **not** need a separate frontend server. PostGIS is a database extension, not a separate service. Android Studio supplies the SDK and emulator tools; its editor does not have to stay open. pgAdmin, Docker, Node.js, and a background worker are not required for this local workflow.

## 2. Prerequisites and terminal basics

Install the tools using the [complete Windows setup guide](docs/COMPLETE_WINDOWS_SETUP_GUIDE.md) if this is a new computer:

- Git and VS Code, with the Python, Dart, and Flutter extensions.
- Python 3.13 and a local `server/.venv` virtual environment.
- PostgreSQL 17 with its compatible PostGIS bundle and GDAL/GEOS libraries.
- Flutter with a Dart version satisfying `mobile/pubspec.yaml` (currently `^3.13.2`).
- Android Studio, Android SDK Platform-Tools, Emulator, Command-line Tools, and the SDK/NDK versions required by the installed Flutter toolchain. An Android virtual device (AVD) must be created once in Android Studio's Device Manager, or use a USB phone with USB debugging enabled.
- A private `server/.env` pointing to your own local development database.

Open the repository folder using **File → Open Folder**. Select **Terminal → New Terminal**, then select **PowerShell** as the terminal profile. Use the terminal's **+** button to open additional terminals. Rename them `Backend`, `Device tools`, and `Flutter` to make switching easier.

Commands below start at the **repository root**, the folder containing `server`, `mobile`, and this file. Confirm your location:

```powershell
Get-Location
Get-Item .\server\manage.py, .\mobile\pubspec.yaml
```

If needed, change to your own checkout path:

```powershell
Set-Location 'C:\path\to\FloodSense'
```

Replace example paths and device names before running them. Do not copy prompt text such as `PS C:\...>`, `>>>`, or `postgres=#`. Run commands in order and stop to resolve errors before continuing.

Each terminal has its own current folder and variables. A terminal running Django or Flutter is occupied; use another terminal for other commands. The explicit Python path used here means you **do not need to activate the virtual environment** or change PowerShell's execution policy.

## 3. Start the local PostgreSQL service

Do this before database setup, migrations, or Django startup.

```powershell
Get-Service -Name '*postgres*' | Select-Object Name, Status
```

The standard PostgreSQL 17 installation commonly uses `postgresql-x64-17`. Use the exact name shown on your computer. If its status is `Running`, leave it running. If it is `Stopped`, run this in an **administrator PowerShell terminal**:

```powershell
Start-Service -Name 'postgresql-x64-17'
Get-Service -Name 'postgresql-x64-17'
```

Service control may require elevation. If VS Code is not elevated and you get “Access denied,” open **Windows Terminal or PowerShell → Run as administrator**, run only the service commands there, then return to the ordinary VS Code terminal. A new terminal inside a non-elevated VS Code window does not gain administrator rights.

Check that PostgreSQL is accepting connections. Adjust the installation directory and port if yours differ:

```powershell
& 'C:\Program Files\PostgreSQL\17\bin\pg_isready.exe' -h localhost -p 5432
```

Expected: `accepting connections`. This checks server availability; the application credentials and PostGIS are checked separately below. Opening or closing pgAdmin does not start or stop this service.

## 4. First-time setup only

Skip completed steps on an existing installation. Do not recreate the Flutter project, database, or virtual environment every day.

### 4.1 Prepare Python and the private configuration

From the repository root, create the virtual environment **only if `server/.venv` is absent**:

```powershell
py -3.13 -m venv server\.venv
```

Install the declared packages:

```powershell
.\server\.venv\Scripts\python.exe -m pip install -r server\requirements.txt
```

Copy the template only if no local configuration exists, then open it:

```powershell
if (-not (Test-Path -LiteralPath .\server\.env)) {
    Copy-Item -LiteralPath .\server\.env.example -Destination .\server\.env
}
code .\server\.env
```

Set the database name, user, password, host, and port to match your local installation. Set a private `DJANGO_SECRET_KEY` and correct the GDAL/GEOS DLL paths. The [full setup guide](docs/COMPLETE_WINDOWS_SETUP_GUIDE.md#11-configure-the-private-django-environment) explains how to generate the key and locate the DLLs.

For the standard local setup, confirm these values:

```dotenv
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,10.0.2.2
FLOODSENSE_GIS_ENABLED=true
DATABASE_NAME=floodsense
DATABASE_USER=floodsense
DATABASE_HOST=localhost
DATABASE_PORT=5432
```

Keep the password in the private `.env`, never in committed documentation. If `DATABASE_URL` is set in the environment, it takes precedence over the separate database fields. Confirm the configuration targets your own local database before migrations or seeding. Leave the optional provisional MGB preview disabled and Mapbox token blank for the basic setup.

### 4.2 Create the local database and enable PostGIS

Only if the local role/database do not already exist, connect as the PostgreSQL administrator:

```powershell
& 'C:\Program Files\PostgreSQL\17\bin\psql.exe' -h localhost -p 5432 -U postgres -d postgres -W
```

Enter the PostgreSQL administrator password at the prompt. Inside **psql**, run:

```sql
CREATE USER floodsense WITH LOGIN;
\password floodsense
CREATE DATABASE floodsense OWNER floodsense;
\connect floodsense
CREATE EXTENSION IF NOT EXISTS postgis;
SELECT current_database(), current_user, PostGIS_Version();
\q
```

`\password` prompts for the new application's database password without displaying it. Put that same password in `server/.env`. PostgreSQL's `postgres` account and the application's `floodsense` database account are separate from the Admin website login.

If the database already exists, skip the creation statements: connect with `-d floodsense` and check/enable PostGIS there. Do not drop an existing database to repeat setup. Enabling PostGIS in `postgres` or `test_floodsense` does not enable it in `floodsense`; extensions belong to individual databases.

### 4.3 Apply migrations and create a local Admin account

Back at the PowerShell prompt, from the repository root:

```powershell
.\server\.venv\Scripts\python.exe server\manage.py check
.\server\.venv\Scripts\python.exe server\manage.py migrate --plan
.\server\.venv\Scripts\python.exe server\manage.py migrate
.\server\.venv\Scripts\python.exe server\manage.py createsuperuser
```

Use your own local administrator email and password. Password characters may not appear while you type. Skip `createsuperuser` if you already have a working local staff/superuser account. Git does not transfer users, passwords, or database rows from another teammate.

Verify the actual Django database connection and spatial extension:

```powershell
.\server\.venv\Scripts\python.exe server\manage.py shell -c "from django.db import connection; c = connection.cursor(); c.execute('SELECT current_database(), PostGIS_Version()'); print(c.fetchone()); c.close()"
```

Expected: your local database name and a PostGIS version, without an exception.

### 4.4 Prepare local demonstration content and Flutter dependencies

For a local development database you are explicitly authorized to populate:

```powershell
.\server\.venv\Scripts\python.exe server\manage.py seed_demo
```

This verified command creates/refreshes fictional demonstration records, a demonstration preparedness flow, and a separate pending-validation Bacoor administrative reference layer. It does not supply approved susceptibility data or verified evacuation centers. Do not run it against shared/deployed databases or treat its content as official. If it reports an ownership or publication conflict, stop and follow the team workflow rather than deleting records.

Resident login also has content gates: migrations create **draft** legal/onboarding records, but authorized reviewers must review and publish the required Terms, Privacy, and onboarding versions. A configuration-required screen can therefore be expected even when the servers work. See [resident setup](docs/RESIDENT_AUTH_ONBOARDING_AND_DSS_SETUP.md); do not bypass the gate or publish placeholder text just to make a test pass.

Install the Flutter packages:

```powershell
Push-Location .\mobile
flutter pub get
flutter doctor -v
Pop-Location
```

Resolve Android toolchain errors before continuing. The existing `mobile` project is ready to use: **do not run `flutter create`**.

## 5. Everyday startup

### 5.1 Check the checkout and database

From the repository root:

```powershell
git status --short --branch
git fetch origin
git log --oneline HEAD..origin/main
```

If updates are available, protect unfinished work first. On the team's local `main` branch with a clean working tree, pull using:

```powershell
git pull --ff-only origin main
```

If Git reports divergence or conflicts, stop and resolve them with the team. Do not use a hard reset to force the update. On a feature branch, follow the team's branch workflow instead of switching or merging blindly.

After pulling, synchronize dependencies and review/apply committed migrations **to your local database**:

```powershell
.\server\.venv\Scripts\python.exe -m pip install -r server\requirements.txt
.\server\.venv\Scripts\python.exe server\manage.py migrate --plan
.\server\.venv\Scripts\python.exe server\manage.py migrate
Push-Location .\mobile
flutter pub get
Pop-Location
```

PostgreSQL must be running first (section 3). `No migrations to apply` is normal. Do not run `makemigrations` simply to start the app. Run `seed_demo` again only when the relevant handoff calls for a content refresh on your authorized local database. See the [current barangay/Prepare handoff](docs/TEAM_HANDOFF_BARANGAY_PREVIEW_AND_PREPARE.md).

### 5.2 Start Django — Backend terminal, repository root

```powershell
.\server\.venv\Scripts\python.exe server\manage.py check
.\server\.venv\Scripts\python.exe server\manage.py runserver 0.0.0.0:8000
```

Wait for `Starting development server at http://0.0.0.0:8000/`. Leave this terminal running. The `0.0.0.0` binding supports local device testing; browse using the addresses below, not `0.0.0.0`. Use a trusted private network and allow Python through the private-network firewall only when needed. For PC browser/USB-reverse testing alone, `127.0.0.1:8000` is also sufficient.

### 5.3 Open the Admin panel and check the API — Device tools terminal

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/health/'
Start-Process 'http://127.0.0.1:8000/management/'
```

Expected health result: `status` is `ok`. This endpoint is deliberately database-independent; use the database check in section 4.3 to verify PostgreSQL/PostGIS.

Log in at `/management/` with your local active staff/superuser account. This is the custom day-to-day Admin portal. `/admin/` is the separate technical Django Admin, served by the same process. A resident account is not automatically an administrator.

### 5.4 Start the Android emulator — Device tools terminal

List configured virtual devices:

```powershell
flutter emulators
```

Use the emulator ID from that list (the following name is an example):

```powershell
flutter emulators --launch FloodSense_API_36
```

Wait for the Android home screen, then list running devices:

```powershell
flutter devices
```

The running device ID may be `emulator-5554`; this differs from the AVD name used to launch it. If no AVD exists, create one in Android Studio's Device Manager first. You may open Android Studio from PowerShell if installed at its usual location:

```powershell
& 'C:\Program Files\Android\Android Studio\bin\studio64.exe'
```

The editor is optional after initial setup; launching the emulator with Flutter does not require it to be open. The [Flutter CLI reference](https://docs.flutter.dev/reference/flutter-cli) documents emulator and device commands.

### 5.5 Start Flutter — Flutter terminal, repository root

```powershell
Set-Location .\mobile
flutter devices
flutter run -d emulator-5554
```

Replace `emulator-5554` with the actual running Android device ID. The first build can take several minutes. Keep both this terminal and Django running.

The default Android API URL is `http://10.0.2.2:8000/api/v1`. Inside an emulator, `127.0.0.1` refers to the emulator itself; `10.0.2.2` reaches the Windows host. The debug build permits local HTTP; this is not a release deployment configuration.

While Flutter runs, press `r` for hot reload, `R` for hot restart, or `h` for help. For changed `--dart-define` values or native dependencies, quit and run Flutter again. Restart Django after `.env` changes or database/content setup.

## 6. Alternative client options

Use one of these instead of the emulator steps, or open a separate Flutter terminal to run an additional client. Keep Django running.

### A. Physical Android phone over USB

Enable Developer options and USB debugging on the phone, connect a data-capable cable, and accept the phone's debugging authorization prompt.

In the Device tools terminal, set the Android SDK path. Replace it if Android Studio's SDK Manager shows a different location:

```powershell
$floodSenseSdk = "$env:LOCALAPPDATA\Android\Sdk"
& "$floodSenseSdk\platform-tools\adb.exe" devices
```

Copy the phone's serial from the list. Replace `YOUR_PHONE_SERIAL` below:

```powershell
$floodSensePhone = 'YOUR_PHONE_SERIAL'
& "$floodSenseSdk\platform-tools\adb.exe" -s $floodSensePhone reverse tcp:8000 tcp:8000
```

In the Flutter terminal, inside `mobile`:

```powershell
flutter run -d YOUR_PHONE_SERIAL --dart-define=FLOODSENSE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

USB reverse makes the phone's port `8000` reach Django on the computer. Reapply it after a device reconnect if needed. Without this reverse mapping, the phone's `127.0.0.1` will not reach the computer.

### B. Physical Android phone over a trusted LAN

Use `ipconfig` to find the computer's active Wi-Fi/Ethernet IPv4 address. Connect the phone to the same trusted network, add that IP to `DJANGO_ALLOWED_HOSTS` in the private `.env`, and restart Django with `0.0.0.0:8000`. Keep a USB debugging connection for installation/debugging, or configure Android wireless debugging separately.

From `mobile`, replace the example IP and device ID:

```powershell
flutter run -d YOUR_PHONE_SERIAL --dart-define=FLOODSENSE_API_BASE_URL=http://192.168.1.10:8000/api/v1
```

Check the health URL using that IP in the phone's browser. If unreachable, check the private-network firewall and Wi-Fi client isolation. Do not use `DJANGO_ALLOWED_HOSTS=*` or disable the firewall. No USB reverse is needed for this LAN API address.

### C. Chrome resident preview

From a Flutter terminal inside `mobile`:

```powershell
flutter run -d chrome --web-hostname localhost --web-port 3000
```

The client uses `http://127.0.0.1:8000/api/v1`. Keep port `3000` so the browser origin matches the default Django CORS settings. This is the resident app, distinct from the Admin portal. Google sign-in is currently Android-only; use username/email sign-in in the browser. Browser testing does not replace Android device testing.

## 7. Confirm the system is ready

- PostgreSQL reports `Running`, and the Django database query returns the expected database/PostGIS version.
- Django starts without exceptions; the health endpoint reports `ok`.
- Your local staff account can enter `/management/`.
- Flutter launches on the selected device and can load backend content.
- Resident verification and published legal/onboarding prerequisites are satisfied for the intended test account.
- Demonstration/provisional notices remain visible. Empty nearest-center results and insufficient-data states can be correct when no eligible records exist.

With the default console email backend, verification/reset emails appear in the **Backend terminal**, not in an actual mailbox. Treat those links as private. For phone-based email-link testing, see [resident authentication setup](docs/RESIDENT_AUTH_ONBOARDING_AND_DSS_SETUP.md).

The native Android workflow is Mapbox-first when a restricted public `pk.` token is configured and the app is launched with `scripts/run_android_local.ps1`. OSM remains the safe fallback when the token is absent, the platform is unsupported, or Mapbox cannot initialize. Internet access is needed for either basemap. Follow the [map presentation guide](docs/MAP_PRESENTATION_PROVIDER_GUIDE.md) or [barangay preview handoff](docs/TEAM_HANDOFF_BARANGAY_PREVIEW_AND_PREPARE.md) for their specific checks. A code pull does not transfer tokens, restricted datasets, or another developer's configured records.

## 8. Shut down safely, in this order

### 8.1 Save work and stop each Flutter session

Save your files and finish or cancel any active Admin form operation. In each terminal running `flutter run`, press:

```text
q
```

Wait for the PowerShell prompt. If the session is unresponsive, try `Ctrl+C`. Do not use `d` for shutdown: it detaches and leaves the app running. Close the Flutter browser preview tab when finished.

If you previously detached from an Android session, explicitly stop only FloodSense on the selected device using the Device tools terminal:

```powershell
$floodSenseSdk = "$env:LOCALAPPDATA\Android\Sdk"
& "$floodSenseSdk\platform-tools\adb.exe" devices
& "$floodSenseSdk\platform-tools\adb.exe" -s YOUR_DEVICE_ID shell am force-stop ph.edu.cvsu.bacoor.floodsense
```

Use the actual device ID. This stops the app without uninstalling it or clearing its saved data.

### 8.2 Stop the emulator or disconnect the phone

In the Device tools terminal, define the SDK path even if you skipped the detached-app command above. Adjust it to your installed SDK location:

```powershell
$floodSenseSdk = "$env:LOCALAPPDATA\Android\Sdk"
& "$floodSenseSdk\platform-tools\adb.exe" devices
```

For an emulator, use its actual running serial:

```powershell
& "$floodSenseSdk\platform-tools\adb.exe" -s emulator-5554 emu kill
```

Wait for the emulator window to close. This uses the emulator's own console shutdown command; avoid force-killing `qemu` processes. See the [Android emulator console documentation](https://developer.android.com/studio/run/emulator-console). Closing the emulator window normally is also an option.

For a USB phone where you set up reverse forwarding, remove only this mapping before unplugging:

```powershell
& "$floodSenseSdk\platform-tools\adb.exe" -s YOUR_PHONE_SERIAL reverse --remove tcp:8000
```

Skip that command if you did not create the mapping. You do not need to power off the phone.

### 8.3 Close optional Android tools

Android Studio can be closed normally after saving work and completing/canceling builds. To request a normal window close from PowerShell, first inspect the open Studio instances:

```powershell
Get-Process -Name studio64 -ErrorAction SilentlyContinue | Select-Object Id, MainWindowTitle
```

If one is open, replace `12345` with the ID of the intended window:

```powershell
(Get-Process -Id 12345).CloseMainWindow()
```

Respond to any save/exit dialog in Android Studio. This is a close request, not a forced termination. If no window is found, skip it. Closing Studio does not replace stopping a separately launched emulator.

Optionally stop ADB after **all** your Android sessions are finished:

```powershell
& "$floodSenseSdk\platform-tools\adb.exe" kill-server
```

ADB is shared by Android tools on this computer, so leave it running if another project still uses it. It restarts when needed. `kill-server` alone does not shut down an emulator. See [Android Debug Bridge](https://developer.android.com/tools/adb).

### 8.4 Stop Django and close database shells

Log out of the Admin portal and close its tab. In the Backend terminal, press **Ctrl+C** and wait for the PowerShell prompt. Closing a browser tab alone does not stop Django.

If any other terminal is inside a shell, exit it appropriately:

| Prompt/session | Exit command |
| --- | --- |
| PostgreSQL `psql` (`floodsense=#` or `floodsense=>`) | `\q` |
| Django/Python interactive shell (`>>>`) | `exit()` |
| Activated Python virtual environment (`(.venv)`) | `deactivate`, after returning to PowerShell |

This guide does not require activation, so `deactivate` can normally be skipped. It does not stop Django or PostgreSQL.

### 8.5 Optionally stop the local PostgreSQL service last

It is safe to leave PostgreSQL running for your next session. To stop the entire local stack, first ensure no other project or user needs this PostgreSQL instance and no migration, import, test, or database transaction is running. Close database clients, then run in an **administrator PowerShell terminal**:

```powershell
Stop-Service -Name 'postgresql-x64-17'
Get-Service -Name 'postgresql-x64-17'
```

Use your actual service name. Expected status: `Stopped`. This stops the whole PostgreSQL instance, including any other databases it hosts. It does not delete data. PostGIS stops with PostgreSQL; there is no separate PostGIS shutdown command. Do not kill database processes or delete database files.

### 8.6 Finish in VS Code

From a terminal at the repository root:

```powershell
git status --short --branch
```

Review and save your intended changes. Commit through your normal workflow when ready; shutting down does not require a commit. Do not include `.env`, credentials, local database dumps, or restricted data. Type `exit` in idle PowerShell terminals, then close VS Code. Closing VS Code alone is not a reliable way to stop services or detached tools.

## 9. Troubleshooting

| Symptom | What to check |
| --- | --- |
| `manage.py` or Python path not found | Run backend commands from the repository root. If inside `mobile`, use `Set-Location ..`. Create `server/.venv` only if missing. |
| `flutter` is not recognized | Add the installed Flutter `bin` directory to your user PATH and reopen VS Code. Run `flutter --version` and `flutter doctor -v`. |
| PostgreSQL service not found | Verify PostgreSQL is installed, then use `Get-Service -Name '*postgres*'`. Do not assume the version/service name matches the example. |
| PostgreSQL connection refused | Start the correct service; check the host and port in your private `.env` and run `pg_isready`. |
| Password authentication failed | Check the local application's database role/password. They are not the Admin website credentials. Never paste passwords into a shared log. |
| Permission denied to create PostGIS | Use the PostgreSQL administrator to enable the extension in the exact target database. Do not make the Django role a superuser. |
| PostGIS is unavailable, or GDAL/GEOS DLL cannot load | Install the compatible PostGIS bundle and correct the native library paths using the full Windows guide. Keep GIS enabled for normal operation. |
| Port `8000` is already occupied | Check the existing Backend terminal first. Identify the listener with the commands below; stop only a process you recognize. |
| Android shows `unauthorized` or `offline` | Unlock the phone and accept USB debugging, check the cable, or wait for the emulator to finish booting. Recheck `adb devices` and `flutter devices`. |
| Emulator cannot reach API / `DisallowedHost` | Use `10.0.2.2:8000`, include `10.0.2.2` in allowed hosts, and restart Django. Check the firewall on the trusted network. |
| USB phone cannot reach API | Reapply device-specific `adb reverse`, then restart Flutter with the `127.0.0.1` URL override. |
| Browser CORS error | Use `localhost:3000` for Flutter Web, check `DJANGO_CORS_ALLOWED_ORIGINS`, and restart Django after changing `.env`. |
| Admin login fails | Use your local active staff/superuser account. Pulling Git does not create it. Run `createsuperuser` if needed. |
| Resident setup blocked or data absent | Check required published legal/onboarding content and local demo setup. See section 4.4; do not invent official data or bypass review. |
| Basemap blank but API works | Check internet access to the map provider. Mapbox is optional; the basic run uses OSM. |
| SDK, NDK, Java, license, or Gradle build error | Run `flutter doctor -v` and follow the full Windows setup guide. Install the versions required by this checkout/toolchain; do not repeatedly recreate the project. |

To identify the process listening on Django's port:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object LocalAddress, LocalPort, OwningProcess
```

Use the reported `OwningProcess` number with `Get-Process -Id 12345`. Prefer **Ctrl+C in the original terminal**. If you intentionally choose another backend port, update the Flutter API URL, USB reverse mapping if used, and health/Admin URLs to match it.

### Optional developer checks

These are not required on every startup. Backend tests need a separately provisioned **isolated test database**, including PostGIS; they must not run against the application or a shared database.

```powershell
# Repository root, after isolated test-database setup
.\server\.venv\Scripts\python.exe -m pytest server -q --reuse-db
Push-Location .\mobile
flutter analyze
flutter test
Pop-Location
```

If tests fail during setup with a test-database creation or PostGIS permission error, ask the local database administrator to provision the isolated test database and permissions. `--reuse-db` reuses it; the flag does not install PostGIS or grant permissions. A passing health request is not evidence that this test setup is ready.

## 10. Related guides

- [Complete Windows installation](docs/COMPLETE_WINDOWS_SETUP_GUIDE.md)
- [Team database and Git workflow](docs/TEAM_DATABASE_AND_GIT_WORKFLOW.md)
- [Resident authentication, onboarding, and DSS](docs/RESIDENT_AUTH_ONBOARDING_AND_DSS_SETUP.md)
- [Barangay preview and Prepare handoff](docs/TEAM_HANDOFF_BARANGAY_PREVIEW_AND_PREPARE.md)
- [Mobile commands and optional map providers](mobile/README.md)

This guide adds documentation only. Pulling this guide itself requires no dependency installation, migration, seed, or data import; setup commands above apply when preparing or updating the actual application environment.
