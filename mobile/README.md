# FloodSense Android application

This Flutter application provides the Day 6 FloodSense demonstration flow. It
loads administrator-managed rainfall options and fictional polygons from
Django, renders them on an interactive map, requests backend Expert System
results to color each area, resolves a temporary map pin through PostGIS, and
displays the full explanation and DSS preparedness guidance for the selected
zone.

The application never stores permanent assessment rules, classifications,
guidance, or pin coordinates. It does not use GPS and is not a live forecast,
warning, boundary authority, route-safety, or evacuation-order service.

## Run on the Android emulator

From the repository root, start Django:

```powershell
server\.venv\Scripts\python.exe server\manage.py runserver 0.0.0.0:8000
```

Then use a second terminal:

```powershell
Set-Location mobile
flutter pub get
flutter analyze
flutter test
flutter run
```

The default development base URL is:

```text
http://10.0.2.2:8000/api/v1
```

Android emulator traffic uses a debug-only cleartext-HTTP exception. Release
builds retain Android's normal cleartext restriction; production must use an
HTTPS API.

## Run on a physical Android device

Connect the phone and computer to the same trusted network. Start Django on
`0.0.0.0:8000`, add the computer's actual LAN IP to
`DJANGO_ALLOWED_HOSTS`, and allow the development port through the private-
network firewall when necessary. Do not use `ALLOWED_HOSTS=*`.

Run Flutter with a temporary compile-time URL:

```powershell
flutter run --dart-define=FLOODSENSE_API_BASE_URL=http://192.168.1.10:8000/api/v1
```

Replace the example address with the computer's current LAN IP. Never commit a
developer-specific IP address, credential, or `.env` file.

## Local demonstration data

The tested, transactional `seed_demo` command creates or refreshes the shared
fictional Day 6 dataset in a developer's own local PostgreSQL/PostGIS database:

```powershell
Set-Location ..
server\.venv\Scripts\python.exe server\manage.py seed_demo
```

Run it only when the local data import is explicitly authorized. Never point it
at a shared, staging, or deployed database. It stops on unsafe reserved-code or
active-ruleset conflicts instead of taking over records owned by another
source.

If any required collection is empty, the app explains that an administrator
must configure demonstration records. It never substitutes local fake data.

## Map networking and attribution

The development map uses OpenStreetMap standard tiles, identifies the Android
package as `ph.edu.cvsu.bacoor.floodsense`, and keeps
`© OpenStreetMap contributors` visible. Public internet is required for the
basemap; API polygons, labels, warnings, and neutral error states remain
separate from the basemap. Production tile-provider review is still required.

The map adds these API calls to the Day 5 endpoints:

```text
POST /api/v1/assessments/evaluate-map/
POST /api/v1/geography/resolve-point/
```

See `../docs/DAY_5_FLUTTER_ASSESSMENT_GUIDE.md` for the detailed-result flow and
`../docs/DAY_6_DYNAMIC_MAP_GUIDE.md` for geometry parsing, map state, endpoint
contracts, seeding, testing, and teammate setup.
