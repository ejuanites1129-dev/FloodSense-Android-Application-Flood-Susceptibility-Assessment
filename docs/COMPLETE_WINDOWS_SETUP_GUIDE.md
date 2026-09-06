# FloodSense complete Windows setup manual

This manual explains how to prepare a Windows computer for FloodSense, run the
existing project, understand the folder structure, and recover from the setup
problems already encountered by the team. It is written for team members who
have not used Django, PostgreSQL/PostGIS, Flutter, or Android Studio before.

Last verified: September 6, 2026

### How to use this manual

- A teammate preparing a new computer should follow sections 3 through 20 in
  order.
- A teammate whose computer is already configured can use section 19 as the
  daily start/stop checklist.
- Use section 20 whenever a command or emulator step fails.
- Section 21 records how the repository was originally scaffolded; it is not
  required when cloning the existing project.
- Give section 23 to a coding agent before asking it to modify the project.
- Use section 24 when explaining the architecture to the research team.

## 1. What this setup creates

FloodSense is divided into three main technical parts:

```text
Flutter Android app
        |
        | HTTP/JSON API requests
        v
Django + Django REST Framework backend
        |
        | database queries and spatial operations
        v
PostgreSQL + PostGIS database
```

- **Flutter and Dart** build the Android application used by residents.
- **Django** contains the backend rules, administration pages, authentication,
  and API.
- **Django REST Framework (DRF)** provides JSON endpoints used by the mobile
  application.
- **Simple JWT** will provide access and refresh tokens for mobile login.
- **PostgreSQL** stores users, application content, assessments, and records.
- **PostGIS** adds geographic data types and spatial queries to PostgreSQL.
- **GeoDjango, GDAL, and GEOS** allow Django to work with PostGIS geometries.
- **Android Studio** supplies the Android SDK and emulator. The team may still
  write most Flutter code in VS Code.
- **Git** records source-code history and enables team collaboration.

The current foundation does **not** contain official Bacoor flood
classifications or finalized Expert System rules. Unvalidated information must
remain marked as provisional or demonstration-only.

## 2. Tested configuration

The project was successfully built and tested with the following versions. A
teammate does not always need the exact patch version, but matching these major
versions reduces differences between computers.

| Component | Verified version |
| --- | --- |
| Windows | 64-bit Windows 11 |
| Git for Windows | 2.54.0 |
| Python | 3.13.0 |
| Django | 5.2.17 |
| Django REST Framework | 3.16.1 |
| PostgreSQL | 17.11 |
| PostGIS | 3.6 |
| GDAL | 3.9.2 |
| Flutter | 3.47.2 stable |
| Dart | 3.13.2 |
| Android Studio | 2026.1.4 |
| Android Emulator | 37.1.11 |
| Android test image | Android 16 / API 36 / Google APIs / x86_64 |
| Required Android NDK | 28.2.13676358 (r28c) |
| Gradle wrapper | 9.3.1 |

Use PostgreSQL 17 for new team computers unless the team deliberately agrees
to upgrade together. A different PostgreSQL major version changes installation
paths and may use different GDAL library filenames.

## 3. Before starting

Prepare the following:

- A 64-bit Windows 10 or Windows 11 computer.
- Administrator access for PostgreSQL, PostGIS, and Android installation.
- Hardware virtualization enabled in the BIOS/UEFI for the emulator.
- At least 20 GB of free disk space. More space is recommended because Android
  SDKs, Gradle caches, and virtual phones are large.
- A stable internet connection for initial downloads.
- The PostgreSQL administrator password and the new FloodSense database
  password written in a secure password manager.

Internet is required during the initial installation. After dependencies are
cached, the starter app and a local Django server can run without public
internet. The completed FloodSense product is planned as an online-only app.

### 3.1 What to download using a web browser

Download installers only from the official pages below. A teammate should not
search for unofficial repacks or third-party download mirrors.

| Download | Official page | What to select |
| --- | --- | --- |
| Git for Windows | <https://git-scm.com/install/windows> | Current 64-bit Windows installer |
| Visual Studio Code | <https://code.visualstudio.com/docs/setup/windows> | Windows User Installer, 64-bit |
| Python | <https://www.python.org/downloads/windows/> | A 64-bit Python 3.13 release |
| PostgreSQL | <https://www.postgresql.org/download/windows/> | PostgreSQL 17 Windows x86-64 installer |
| Android Studio | <https://developer.android.com/studio/install> | Windows `.exe` installer |
| Flutter SDK | <https://docs.flutter.dev/get-started/install/windows/mobile> | Current stable Windows Flutter SDK archive |

The installation order used for FloodSense is:

1. Git for Windows
2. VS Code
3. Python 3.13
4. PostgreSQL 17
5. PostGIS through PostgreSQL's Stack Builder
6. Android Studio and its Setup Wizard
7. Android SDK components through Android Studio's SDK Manager
8. Flutter stable SDK
9. VS Code extensions
10. Django and all Python packages through `server/requirements.txt`

### 3.2 What is not installed directly from a browser

Some names in the technology stack are packages or components rather than
separate Windows applications:

| Component | Correct installation method |
| --- | --- |
| Django | Installed into `server/.venv` by Python `pip` from `server/requirements.txt` |
| Django REST Framework | Installed by the same requirements command |
| Simple JWT | Installed by the same requirements command |
| psycopg PostgreSQL driver | Installed by the same requirements command |
| pytest and Ruff | Installed by the same requirements command |
| PostGIS | Installed from **Stack Builder > Spatial Extensions** after PostgreSQL |
| Android SDK/API 36 | Installed from Android Studio's **SDK Manager** |
| Android Emulator | Installed from Android Studio's **SDK Tools** tab |
| Android system image | Downloaded while creating the virtual phone or from SDK Manager |
| Android NDK 28.2 | Installed from **SDK Tools > NDK (Side by side)** |
| Dart | Included with the Flutter SDK; do not install a separate Dart SDK |
| Gradle | Downloaded automatically by the project's Gradle wrapper during the first build |

In particular, do not look for a separate “Django installer.” Installing Django
globally would also be incorrect for this project; it belongs inside
`server/.venv`.

## 4. Obtain the project files

### Option A: Clone the shared Git repository (recommended)

After the repository owner has pushed FloodSense to a private Git hosting
service, open PowerShell and run:

```powershell
Set-Location "$env:USERPROFILE\Documents\GitHub"
git clone <REPOSITORY_URL> FloodSense
Set-Location FloodSense
```

Replace `<REPOSITORY_URL>` with the URL supplied by the repository owner.

### Option B: Use a project ZIP archive

1. Obtain the ZIP from the repository owner.
2. Extract it to a short, ordinary path such as:

   ```text
   C:\Users\YourName\Documents\GitHub\FloodSense
   ```

3. Do not copy another developer's `server/.env`, `server/.venv`,
   `mobile/build`, `.dart_tool`, or Android virtual-device files.
4. Open PowerShell in the extracted `FloodSense` directory.

### Important current repository status

At the time this guide was created, the original local repository had no Git
commit and no remote repository configured. Teammates cannot clone it until the
owner reviews the files, creates a private remote repository, commits the safe
files, and pushes them. See section 18.

## 5. Understand the project folders

```text
FloodSense/
|-- .gitignore
|-- README.md
|-- pyproject.toml
|-- pytest.ini
|-- docs/
|   |-- ARCHITECTURE_DECISION.md
|   |-- COMPLETE_WINDOWS_SETUP_GUIDE.md
|   `-- SETUP_WINDOWS.md
|-- FILES/
|   `-- research documents, interviews, and earlier papers
|-- frontend-design-output/
|   `-- interface mockups and design notes
|-- mobile/
|   |-- android/
|   |-- lib/
|   |   `-- main.dart
|   |-- test/
|   |-- pubspec.yaml
|   `-- pubspec.lock
|-- research_data/
|   |-- provisional/
|   `-- approved/
|-- scripts/
|   |-- check_backend_bootstrap.ps1
|   `-- verify_postgis.ps1
`-- server/
    |-- .env.example
    |-- requirements.txt
    |-- manage.py
    |-- config/
    |-- accounts/
    |-- core/
    |-- geography/
    |-- expert/
    |-- dss/
    |-- evacuation/
    `-- provenance/
```

Backend modules have separate responsibilities:

- `accounts`: email-based user accounts and Django Admin registration.
- `core`: shared behavior and the public health-check endpoint.
- `geography`: future boundaries, zones, and spatial records.
- `expert`: future deterministic Expert System rules and evaluations.
- `dss`: future preparedness recommendations and decision-support logic.
- `evacuation`: future evacuation-center records.
- `provenance`: sources, validation state, and data-history records.

Data folders have an important research meaning:

- `research_data/provisional` is for fictional, incomplete, or unvalidated
  development data.
- `research_data/approved` is only for data accepted and documented for research
  use.
- Provisional data must never be displayed as official Bacoor information.

The following local/generated folders must not be committed:

- `server/.env` - passwords and private local configuration.
- `server/.venv` - one computer's Python environment.
- `mobile/build` - generated APK and intermediate build files.
- `mobile/.dart_tool` - generated Dart metadata.
- `.idea` and `.vscode` - local editor settings unless intentionally shared.
- `mobile/android/local.properties` - local Android and Flutter SDK paths.

The repository's `.gitignore` already excludes these items.

## 6. Install Git and VS Code

### Git

1. Download Git for Windows from <https://git-scm.com/install/windows>.
2. Run the installer. The default choices are acceptable for this project.
3. Close and reopen PowerShell.
4. Verify:

   ```powershell
   git --version
   ```

If this is the first time using Git, set the name and email that should appear
in commits:

```powershell
git config --global user.name "Your Full Name"
git config --global user.email "your-email@example.com"
```

### VS Code

1. Install the Windows User Setup from
   <https://code.visualstudio.com/docs/setup/windows>.
2. Open VS Code.
3. Open Extensions with `Ctrl+Shift+X`.
4. Search for and install the following required extensions:

   | Extension shown in VS Code | Publisher | Extension ID | Why it is needed |
   | --- | --- | --- | --- |
   | Flutter | Dart Code | `Dart-Code.flutter` | Flutter commands, device selection, debugging, and hot reload |
   | Dart | Dart Code | `Dart-Code.dart-code` | Dart language support, completion, analysis, and formatting |
   | Python | Microsoft | `ms-python.python` | Python environment selection, Django code support, and debugging integration |
   | Pylance | Microsoft | `ms-python.vscode-pylance` | Python completion, type information, navigation, and error checking |

5. The Python extension may automatically install these Microsoft dependency
   extensions. Keep them installed if they appear:

   | Dependency | Extension ID | Purpose |
   | --- | --- | --- |
   | Python Debugger | `ms-python.debugpy` | Python debugging engine |
   | Python Environments | `ms-python.vscode-python-envs` | Virtual-environment discovery and selection |

6. Restart VS Code after the extensions finish installing.
7. Open the `FloodSense` root folder in VS Code.

To install the four required extensions from a terminal instead of searching in
the interface, use:

```powershell
code --install-extension Dart-Code.flutter
code --install-extension Dart-Code.dart-code
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
```

No Django, PostgreSQL, PostGIS, Java, or Gradle VS Code extension is required for
the current FloodSense foundation. Those tools work through Python, the
database server, Android Studio, and the terminal. Teammates may add optional
extensions later, but optional extensions must not be treated as project
requirements.

VS Code is the main editor. Android Studio is still needed for the Android SDK
and emulator, but the team does not have to write code in Android Studio.

## 7. Install Python and prepare the backend environment

### 7.1 Install Python

Install a 64-bit Python 3.13 release from
<https://www.python.org/downloads/windows/>. If the installer offers an option
to make Python commands available in `PATH`, enable it.

Close and reopen PowerShell, then verify one of these commands:

```powershell
py -3.13 --version
python --version
```

The expected result begins with `Python 3.13`.

### 7.2 Create the project virtual environment

A virtual environment keeps FloodSense Python packages separate from other
Python projects. Run these commands from the repository root:

```powershell
py -3.13 -m venv server\.venv
server\.venv\Scripts\python.exe -m pip install --upgrade pip
server\.venv\Scripts\python.exe -m pip install -r server\requirements.txt
```

If the `py` command is unavailable but `python --version` reports Python 3.13,
use:

```powershell
python -m venv server\.venv
```

Do not copy `.venv` from another computer. Each team member creates it locally.

### 7.3 What the requirements install

`server/requirements.txt` installs:

- Django 5.2
- Django REST Framework
- Simple JWT
- PostgreSQL driver (`psycopg`)
- environment-file and database URL helpers
- static-file and deployment packages
- pytest, pytest-django, and Ruff for verification

Confirm Django:

```powershell
server\.venv\Scripts\python.exe -m django --version
```

## 8. Install PostgreSQL 17

1. Download the Windows installer from
   <https://www.postgresql.org/download/windows/>.
2. Install PostgreSQL 17.
3. Keep the default port `5432` unless it is already used.
4. Create and securely record the password for the built-in `postgres`
   administrator account.
5. Install the command-line tools, pgAdmin, and Stack Builder when offered.
6. Finish the PostgreSQL installer.

The `postgres` account is for database administration. The Django application
will use a separate, less-powerful `floodsense` account.

## 9. Install PostGIS through Stack Builder

1. Open **Stack Builder** from the Windows Start menu.
2. Select the installed PostgreSQL 17 instance.
3. Expand **Spatial Extensions**.
4. Select the newest compatible **PostGIS Bundle for PostgreSQL 17 (64-bit)**.
   The verified machine uses PostGIS 3.6.2.
5. Download the installation files and click **Next** to begin installation.
6. Accept the license agreement.
7. For components, keep the PostGIS bundle and the recommended PROJ/GDAL/SSL
   registration options selected.
8. `Create spatial database` may remain unchecked because this manual creates
   the database explicitly.
9. Complete every installer before restarting Windows.

PostGIS officially recommends Stack Builder as the simplest installation path
for the EnterpriseDB PostgreSQL Windows distribution:
<https://postgis.net/documentation/getting_started/install_windows/released_versions/>.

## 10. Create the FloodSense database

### 10.1 Open PostgreSQL SQL Shell

Open **SQL Shell (psql)** from the Start menu. Accept or enter:

```text
Server: localhost
Database: postgres
Port: 5432
Username: postgres
Password: the PostgreSQL administrator password
```

The prompt should become:

```text
postgres=#
```

### 10.2 Create the application account and database

Enter each command separately. Semicolons are required on SQL statements.

```sql
CREATE USER floodsense WITH LOGIN;
\password floodsense
```

`psql` will request the new password twice without displaying it. Remember this
password; the exact same value must later be placed in `server/.env`.

Continue:

```sql
CREATE DATABASE floodsense OWNER floodsense;
\c floodsense
CREATE EXTENSION IF NOT EXISTS postgis;
SELECT PostGIS_Version();
```

A successful result displays a PostGIS version. Exit with:

```sql
\q
```

### 10.3 If the role or database already exists

Do not create duplicates. To reset only the FloodSense user's password:

```sql
\password floodsense
```

If the `floodsense` database already exists, connect to it and make sure PostGIS
is enabled:

```sql
\c floodsense
CREATE EXTENSION IF NOT EXISTS postgis;
SELECT PostGIS_Version();
```

Do not delete an existing database merely because a creation command reports
that it already exists.

## 11. Configure the private Django environment

From the repository root, copy the template:

```powershell
Copy-Item server\.env.example server\.env
```

Open `server/.env` in VS Code. It should contain values in this form:

```dotenv
DJANGO_DEBUG=true
DJANGO_SECRET_KEY=replace-with-a-long-random-value
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,10.0.2.2
FLOODSENSE_GIS_ENABLED=true
DATABASE_NAME=floodsense
DATABASE_USER=floodsense
DATABASE_PASSWORD=replace-with-the-floodsense-database-password
DATABASE_HOST=localhost
DATABASE_PORT=5432
GDAL_LIBRARY_PATH=C:\Program Files\PostgreSQL\17\bin\libgdal-35.dll
GEOS_LIBRARY_PATH=C:\Program Files\PostgreSQL\17\bin\libgeos_c.dll
```

Important rules:

- `DATABASE_PASSWORD` must match the password set with `\password floodsense`.
- Do not put the password in `DATABASE_URL` when using these separate fields.
- Never send `server/.env` through chat or commit it to Git.
- `10.0.2.2` allows requests from the Android emulator during development.
- Development settings are not production deployment settings.

Generate a local Django secret key with:

```powershell
server\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the output after `DJANGO_SECRET_KEY=` in `server/.env`.

### Verify the installed DLL filenames

The verified setup uses `libgdal-35.dll` and `libgeos_c.dll`. If Django reports
that GDAL or GEOS cannot be found, check the actual PostgreSQL installation:

```powershell
Get-ChildItem "C:\Program Files\PostgreSQL\17\bin\libgdal*.dll"
Get-ChildItem "C:\Program Files\PostgreSQL\17\bin\libgeos_c.dll"
```

Update the two paths in `.env` if the installed filename differs.

## 12. Initialize and verify Django

Run these commands from the repository root:

```powershell
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe server\manage.py migrate
server\.venv\Scripts\python.exe server\manage.py createsuperuser
```

The custom account model uses an email address. Enter the administrator email
and password requested by `createsuperuser`.

Run both supplied verification scripts:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_backend_bootstrap.ps1
powershell -ExecutionPolicy Bypass -File scripts\verify_postgis.ps1
```

Expected results include:

- Django system check: no issues.
- Backend test: passed.
- Ruff: all checks passed.
- GDAL and GEOS version output.
- No pending migrations.
- PostGIS version output.

### Start the backend

For emulator development, use:

```powershell
server\.venv\Scripts\python.exe server\manage.py runserver 0.0.0.0:8000
```

Leave that terminal open. Windows Firewall may ask whether Python can use the
network; allow access on trusted private networks only.

Open these addresses on the development computer:

- Admin: <http://127.0.0.1:8000/admin/>
- Health check: <http://127.0.0.1:8000/api/v1/health/>

The health response should report `"status": "ok"`. It intentionally reports
that the current data status is provisional-only.

Stop the development server with `Ctrl+C`. Django's built-in server is for local
development, not public deployment.

## 13. Install Android Studio and Android SDK components

1. Download Android Studio from
   <https://developer.android.com/studio/install>.
2. Run the Windows installer.
3. Keep **Android Studio** and **Android Virtual Device** selected.
4. Complete the first-time Setup Wizard using the standard installation.
5. Open **Settings > Languages & Frameworks > Android SDK**.

### SDK Platforms tab

Install a stable Android platform. The verified project uses:

- Android 16 / API level 36

Avoid using only an Android preview image for the main thesis development
device.

### SDK Tools tab

Install or update:

- Android SDK Build-Tools
- Android SDK Platform-Tools
- Android Emulator
- Android SDK Command-line Tools (latest)
- NDK (Side by side), version `28.2.13676358`

Enable **Show Package Details** to select that exact NDK version. A different
newer NDK can remain installed beside it; Android supports side-by-side NDKs.
Do not remove NDK 30 merely because the project also requires NDK 28.

Apply the changes and allow all downloads to finish.

## 14. Install Flutter and configure Windows paths

Follow the official Flutter Windows/Android guide:
<https://docs.flutter.dev/get-started/install/windows/mobile>.

For the verified setup, Flutter was extracted to:

```text
C:\Users\YourName\development\flutter
```

Avoid installing Flutter inside `Program Files` or inside the FloodSense
repository.

Add this directory to the current Windows user's `Path`:

```text
C:\Users\YourName\development\flutter\bin
```

Also create these user environment variables:

```text
ANDROID_HOME=C:\Users\YourName\AppData\Local\Android\Sdk
ANDROID_SDK_ROOT=C:\Users\YourName\AppData\Local\Android\Sdk
```

Replace `YourName` with the Windows account folder name. Close and reopen VS
Code, PowerShell, and Android Studio after changing environment variables.

Verify:

```powershell
flutter --version
dart --version
flutter doctor -v
```

### License-status warning

Recent Android command-line tools may report that the old `sdkmanager
--licenses` option is deprecated or no longer needed. Flutter may consequently
show `Android license status unknown`. This is a known tool compatibility issue:
<https://github.com/flutter/flutter/issues/191487>.

Do not repeatedly run the removed command. Confirm the setup by successfully
building an APK as described in section 16.

## 15. Create the Android virtual phone

Android Studio calls a configured virtual phone an Android Virtual Device
(AVD). Official AVD instructions are available at
<https://developer.android.com/studio/run/managing-avds>.

1. In Android Studio, open **Tools > Device Manager**. From the welcome screen,
   use **More Actions > Virtual Device Manager**.
2. Click **+** and choose **Create Virtual Device**.
3. Choose **Pixel 7** as the hardware profile.
4. Choose the stable **Android 16 / API 36 / Google APIs / x86_64** image.
5. Download the image if required. It is several gigabytes.
6. Name the device:

   ```text
   FloodSense_API_36
   ```

7. Finish creation.
8. Click the triangular Play button beside the device.
9. Wait for the Android home screen. The first boot is much slower than later
   Quick Boot launches.

Check hardware acceleration from PowerShell:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\emulator\emulator.exe" -accel-check
```

A successful Windows result reports that WHPX or another supported hypervisor
is installed and usable. See the official acceleration guide if it fails:
<https://developer.android.com/studio/run/emulator-acceleration>.

Optional command-line startup:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\emulator\emulator.exe" -avd FloodSense_API_36
```

The emulator can remain open when Android Studio is minimized or its project is
closed.

## 16. Prepare, test, build, and run the Flutter application

The `mobile` project already exists in this repository. A teammate who clones
the repository must **not** run `flutter create` again.

Open a new VS Code PowerShell terminal:

```powershell
Set-Location "C:\Users\YourName\Documents\GitHub\FloodSense\mobile"
flutter pub get
flutter analyze
flutter test
flutter devices
flutter build apk --debug
```

Expected results:

- `flutter analyze`: no issues found.
- `flutter test`: all tests passed.
- `flutter devices`: lists the running Android emulator.
- APK build: reports the generated `app-debug.apk`.

The debug APK is generated at:

```text
mobile\build\app\outputs\flutter-apk\app-debug.apk
```

This is a development APK, not a signed production release.

### Run the app with live debugging

Make sure `FloodSense_API_36` has finished booting, then run:

```powershell
flutter run
```

Leave this terminal open while developing. Interactive keys include:

- `r`: hot reload changed Dart code.
- `R`: full hot restart.
- `h`: list commands.
- `d`: detach the debugger but leave the app running.
- `q`: stop the debug session and terminate the app.

Minimizing the emulator window does not normally stop the application.

If `flutter` is not recognized, reopen VS Code. As a direct fallback:

```powershell
& "$env:USERPROFILE\development\flutter\bin\flutter.bat" run
```

## 17. How the mobile app reaches the backend

The current starter screen does not yet call the backend. This section applies
when the mobile API client is added.

The same backend has different addresses depending on where the request begins:

| Request source | Development address |
| --- | --- |
| Browser on the Windows PC | `http://127.0.0.1:8000/api/v1/` |
| Android emulator | `http://10.0.2.2:8000/api/v1/` |
| Physical Android phone | `http://<PC-LAN-IP>:8000/api/v1/` |

`127.0.0.1` inside the emulator refers to the emulator itself, not the Windows
computer. Android reserves `10.0.2.2` as the emulator's route to the host
computer.

For local emulator work:

1. Start Django with `runserver 0.0.0.0:8000`.
2. Keep `10.0.2.2` in `DJANGO_ALLOWED_HOSTS`.
3. Configure the development mobile API base URL as
   `http://10.0.2.2:8000/api/v1/`.

A physical phone additionally requires both devices on the same trusted local
network, the computer's LAN IP, an appropriate firewall rule, and that IP in
`DJANGO_ALLOWED_HOSTS`.

The final deployed app will use an HTTPS production server address, not any of
these local addresses.

Modern Android versions may block unencrypted HTTP for ordinary release apps.
If local API testing requires a cleartext exception, keep that exception in the
Android debug configuration only. Do not enable unrestricted cleartext traffic
in the production application; deploy the real API over HTTPS.

## 18. Git setup and safe team sharing

### Repository owner: first commit and remote

The owner must review the repository before the first commit, especially files
under `FILES/` that may contain interview content, signatures, personal data,
or documents not approved for public release.

Check what Git sees:

```powershell
git status
git check-ignore server\.env
git check-ignore server\.venv
git check-ignore mobile\build
```

Each `git check-ignore` command should print the ignored path. If a secret is not
ignored, stop before committing.

After the research team decides which documents are safe to share:

```powershell
git add <REVIEWED_FILES_AND_FOLDERS>
git status
git commit -m "Initialize FloodSense project foundation"
git branch -M main
git remote add origin <PRIVATE_REPOSITORY_URL>
git push -u origin main
```

Do not blindly upload sensitive research documents to a public repository. Use
a private repository unless the adviser and data owners approve publication.

### Teammate daily Git routine

Before starting work:

```powershell
git pull
git status
```

After completing and testing a focused change:

```powershell
git status
git add <FILES_YOU_CHANGED>
git commit -m "Describe the completed change"
git push
```

Do not commit `.env`, passwords, virtual environments, generated APKs, or files
that another researcher did not authorize for sharing.

## 19. Normal daily startup and shutdown

### Start a development session

1. Open the FloodSense root folder in VS Code.
2. Open Android Studio Device Manager.
3. Start `FloodSense_API_36` and wait for the Android home screen.
4. In VS Code terminal 1, from the repository root, start Django:

   ```powershell
   server\.venv\Scripts\python.exe server\manage.py runserver 0.0.0.0:8000
   ```

5. In VS Code terminal 2, start Flutter:

   ```powershell
   Set-Location mobile
   flutter run
   ```

6. Keep both terminals open while testing app-to-server behavior.

### End a development session

1. In the Flutter terminal, press `q` if the app should be terminated, or `d`
   if it should remain running.
2. In the Django terminal, press `Ctrl+C`.
3. Close the emulator window normally so it can save its Quick Boot state.
4. Check `git status` before closing VS Code.

## 20. Troubleshooting

### `flutter` is not recognized

- Make sure `C:\Users\YourName\development\flutter\bin` is in the user `Path`.
- Close and reopen VS Code and PowerShell.
- Test `flutter --version`.
- Use the direct Flutter path shown in section 16 if necessary.

### Flutter reports no Android devices

- Make sure the emulator reached the Android home screen.
- Run `flutter devices` again.
- Check:

  ```powershell
  & "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" devices
  ```

- The emulator should be listed with the state `device`, not `offline`.

### Emulator failed to connect within five minutes

1. Dismiss the timeout message.
2. In Device Manager, open the three-dot menu beside `FloodSense_API_36`.
3. Select **Cold Boot Now**.
4. Wait for the Android home screen before running Flutter.

Do not select **Wipe Data** unless a cold boot repeatedly fails and the team is
prepared to erase apps and data stored only inside that virtual phone.

### Emulator is very slow

- The first boot and first Gradle build are slow.
- Verify acceleration with `emulator.exe -accel-check`.
- Do not run multiple virtual phones simultaneously.
- Close memory-heavy programs if the computer has limited RAM.
- Later Quick Boot launches and cached builds should be faster.

### Flutter says `Application finished`

The debugger disconnected or the app was terminated. The emulator may still be
running. Run `flutter run` again and leave the terminal open. Use `d`, not `q`,
when intentionally detaching while leaving the app open.

### NDK version error during APK build

If the build requests NDK `28.2.13676358`, install that exact version through
Android Studio:

1. Open Android SDK settings.
2. Select **SDK Tools**.
3. Enable **Show Package Details**.
4. Expand **NDK (Side by side)**.
5. Select `28.2.13676358`.
6. Apply and retry `flutter build apk --debug`.

Other NDK versions may remain installed.

### Gradle download timeout

The first build downloads Gradle and Android dependencies. Confirm the internet
connection and retry:

```powershell
flutter build apk --debug
```

Do not delete the whole project. A successful download is cached for later
builds.

### Android license status is unknown

Read the license-status note in section 14. If the SDK components are installed
and `flutter build apk --debug` succeeds, the current project toolchain is
usable.

### PostgreSQL password authentication failed

The password in `server/.env` does not match the database account. Open `psql`
as `postgres` and run:

```sql
\password floodsense
```

Then enter the same value as `DATABASE_PASSWORD` in `server/.env`. Do not change
only one side.

### PostgreSQL connection refused

- Open Windows Services and ensure the PostgreSQL 17 service is running.
- Confirm `DATABASE_HOST=localhost` and `DATABASE_PORT=5432`.
- Confirm another application did not take port 5432.

### `PostGIS extension is not available`

- Confirm the PostGIS bundle was installed for PostgreSQL 17, not another
  PostgreSQL version.
- Connect to the `floodsense` database as `postgres` and run:

  ```sql
  CREATE EXTENSION IF NOT EXISTS postgis;
  SELECT PostGIS_Version();
  ```

### Django cannot find GDAL or GEOS

- Check the DLL filenames using the commands in section 11.
- Correct `GDAL_LIBRARY_PATH` and `GEOS_LIBRARY_PATH` in `server/.env`.
- Restart the Django server after changing `.env`.
- Run `scripts/verify_postgis.ps1` again.

### Django reports that port 8000 is already in use

Another Django server may already be running. Return to its terminal and press
`Ctrl+C`, or deliberately use a different local port:

```powershell
server\.venv\Scripts\python.exe server\manage.py runserver 0.0.0.0:8001
```

If the port changes, the mobile development API URL must change as well.

### The emulator cannot reach Django

Check all of the following:

- Django is running.
- Django was started on `0.0.0.0:8000`.
- The emulator URL uses `10.0.2.2`, not `127.0.0.1`.
- `10.0.2.2` is in `DJANGO_ALLOWED_HOSTS`.
- Windows Firewall is not blocking Python on the trusted private network.
- The health endpoint works on the PC browser first.

## 21. Recreate the project foundation from an empty repository

This section explains how the initial folder foundation was produced. Team
members setting up an existing clone should skip it.

From an empty `FloodSense` directory:

```powershell
git init
New-Item -ItemType Directory -Path server, mobile, docs, scripts, research_data
py -3.13 -m venv server\.venv
server\.venv\Scripts\python.exe -m pip install Django djangorestframework djangorestframework-simplejwt "psycopg[binary]" python-dotenv dj-database-url whitenoise gunicorn pytest pytest-django ruff
server\.venv\Scripts\django-admin.exe startproject config server
```

From `server`:

```powershell
Set-Location server
.\.venv\Scripts\python.exe manage.py startapp accounts
.\.venv\Scripts\python.exe manage.py startapp core
.\.venv\Scripts\python.exe manage.py startapp geography
.\.venv\Scripts\python.exe manage.py startapp expert
.\.venv\Scripts\python.exe manage.py startapp dss
.\.venv\Scripts\python.exe manage.py startapp evacuation
.\.venv\Scripts\python.exe manage.py startapp provenance
Set-Location ..
```

After Flutter is installed, the Android project was generated with:

```powershell
flutter create --platforms=android --org ph.edu.cvsu.bacoor --project-name floodsense mobile
```

That command produces the Android application ID:

```text
ph.edu.cvsu.bacoor.floodsense
```

These scaffold commands alone do not reproduce the custom user model, settings,
admin configuration, health endpoint, verification scripts, or research-safety
rules. Those are source files already present in the shared repository. Prefer
cloning the reviewed repository rather than rebuilding it manually.

## 22. Verification checklist for a teammate's computer

The setup is complete only when all applicable items are true:

- [ ] `git --version` works.
- [ ] Python 3.13 is available.
- [ ] `server/.venv` was created locally.
- [ ] `server/requirements.txt` installed without errors.
- [ ] PostgreSQL 17 service is running.
- [ ] The `floodsense` database and login role exist.
- [ ] PostGIS is enabled in the `floodsense` database.
- [ ] A private `server/.env` exists and is ignored by Git.
- [ ] Database password in `.env` matches the PostgreSQL role password.
- [ ] GDAL and GEOS library paths are correct.
- [ ] Backend bootstrap verification passes.
- [ ] Real PostGIS verification passes.
- [ ] Django migrations are applied.
- [ ] A Django superuser can sign in to `/admin/`.
- [ ] `/api/v1/health/` returns status `ok`.
- [ ] Flutter and Dart commands work.
- [ ] Android API 36 and required SDK tools are installed.
- [ ] NDK `28.2.13676358` is installed.
- [ ] `FloodSense_API_36` exists and boots.
- [ ] `flutter devices` sees the emulator.
- [ ] `flutter analyze` passes.
- [ ] `flutter test` passes.
- [ ] `flutter build apk --debug` succeeds.
- [ ] `flutter run` opens FloodSense on the emulator.
- [ ] No official-looking Bacoor data or rules were invented for testing.

## 23. Instructions for a coding agent

If an AI coding agent is asked to continue this project, give it this checklist:

1. Read `README.md`, `docs/ARCHITECTURE_DECISION.md`, and this manual first.
2. Inspect the current repository before creating files or installing packages.
3. Never display, print, copy, or commit `server/.env` or database passwords.
4. Reuse `server/.venv`; do not install backend packages globally.
5. Reuse the existing `mobile` project; do not run `flutter create` over it.
6. Keep Django/DRF as the backend. Do not replace it with FastAPI or Firebase
   unless the research team explicitly changes the architecture.
7. Keep PostgreSQL/PostGIS as the database.
8. Keep the mobile product online-only; do not add an offline operating mode.
9. Do not invent Bacoor susceptibility classifications, flood thresholds,
   evacuation-center facts, or Expert System rules.
10. Label synthetic fixtures as provisional or demonstration-only.
11. Preserve source and validation metadata for future official datasets.
12. Run backend checks, Flutter analysis, Flutter tests, and an APK build after
    relevant changes.
13. Report what was changed, what was verified, and what still requires official
    data or expert validation.

## 24. How to explain this setup to the research team

A concise explanation is:

> We separated FloodSense into a Flutter Android client, a Django REST API, and
> a PostgreSQL database with PostGIS. Android Studio supplies the Android SDK
> and virtual phone, while VS Code is our main editor. Each developer creates a
> private Python environment and `.env` file, but shares the reviewed source code
> through Git. The Django backend is already divided into accounts, geography,
> Expert System, DSS, evacuation, and provenance modules. The foundation runs,
> but official flood data and validated decision rules have not yet been added.

This distinction is important: completing the technical setup means the tools,
database, API, emulator, and starter application work together. It does not mean
that the thesis's flood-susceptibility methodology or official Bacoor datasets
are already finalized.

## 25. Official references

- Git for Windows: <https://git-scm.com/install/windows>
- VS Code for Windows: <https://code.visualstudio.com/docs/setup/windows>
- Python on Windows: <https://docs.python.org/3/using/windows.html>
- PostgreSQL Windows installer: <https://www.postgresql.org/download/windows/>
- PostGIS Windows installation: <https://postgis.net/documentation/getting_started/install_windows/released_versions/>
- Django installation: <https://docs.djangoproject.com/en/5.2/topics/install/>
- Flutter Android setup on Windows: <https://docs.flutter.dev/get-started/install/windows/mobile>
- Android Studio installation: <https://developer.android.com/studio/install>
- Android virtual devices: <https://developer.android.com/studio/run/managing-avds>
- Android emulator acceleration: <https://developer.android.com/studio/run/emulator-acceleration>
