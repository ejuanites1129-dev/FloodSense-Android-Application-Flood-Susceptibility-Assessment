# FloodSense Windows development setup

## 1. Prerequisites

Install and verify:

- Git
- Python 3.13
- PostgreSQL with the PostGIS extension
- Flutter SDK, including Dart
- Android Studio with an Android SDK and emulator, or a physical Android device

Docker is optional. It is not required when PostgreSQL/PostGIS is installed directly on Windows.

## 2. Backend virtual environment

From the repository root in PowerShell:

```powershell
python -m venv server/.venv
server/.venv/Scripts/python.exe -m pip install --upgrade pip
server/.venv/Scripts/python.exe -m pip install -r server/requirements.txt
```

## 3. PostgreSQL/PostGIS database

Create a local PostgreSQL user and database named `floodsense`, then enable PostGIS in that database:

```sql
CREATE USER floodsense WITH PASSWORD 'choose-a-local-password';
CREATE DATABASE floodsense OWNER floodsense;
\c floodsense
CREATE EXTENSION postgis;
```

Copy `server/.env.example` to `server/.env` and set the `DATABASE_NAME`,
`DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_HOST`, and `DATABASE_PORT`
values for the local database. Never commit `server/.env`.

`FLOODSENSE_GIS_ENABLED=true` is the normal project setting. GeoDjango will not start until the native GDAL/GEOS libraries supplied by a proper PostGIS/GIS installation are available. The setting may be temporarily set to `false` only for database-independent bootstrap checks; it must not be used for map development or deployment.

## 4. Django

After the database is running:

```powershell
server/.venv/Scripts/python.exe server/manage.py check
server/.venv/Scripts/python.exe server/manage.py migrate
server/.venv/Scripts/python.exe server/manage.py createsuperuser
server/.venv/Scripts/python.exe server/manage.py runserver
```

The initial admin site will be available at `http://127.0.0.1:8000/admin/`.

## 5. Flutter

After installing Flutter and Android Studio:

```powershell
flutter doctor
flutter create --platforms=android --org ph.edu.cvsu.bacoor --project-name floodsense mobile
cd mobile
flutter pub get
flutter analyze
flutter test
flutter build apk --debug
flutter run
```

The generated Android application ID is `ph.edu.cvsu.bacoor.floodsense`.

With recent Android command-line tools, `flutter doctor` may report that the
Android license status is unknown because the old `sdkmanager --licenses`
option has been removed. Treat the APK build as the decisive toolchain check.
The debug APK is written to
`mobile/build/app/outputs/flutter-apk/app-debug.apk`.

## 6. Development-data rule

Use only fictional zones and rules until Bacoor-specific data and expert validation are received. Store provisional import files under `research_data/provisional/`; validated and approved research inputs belong under `research_data/approved/`.
