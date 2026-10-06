# Admin Lucide icons — 6 October 2026

The custom Admin sidebar now uses the owner's downloaded Lucide SVGs for eight
navigation items and the Settings / Sign out account actions. The previous
Lordicon assets and visible attribution footer were removed. All icons are served
locally through the existing reusable `portal_icon` component; no CDN, package,
player, animation or JavaScript change is required.

## Mapping and license

| Interface item | Lucide file |
| --- | --- |
| Overview | `monitor.svg` |
| Reports | `chart-column-increasing.svg` |
| Map data | `map-pinned.svg` |
| DSS content | `book-bookmark.svg` |
| Rainfall references | `cloud.svg` |
| Evacuation centers | `house.svg` |
| Sources and content | `folder.svg` |
| Audit history | `clock.svg` |
| Settings | `settings.svg` |
| Sign out | `square-arrow-right-exit.svg` |

The source folder was `Downloads/Flaticon`, but its new contents are Lucide SVGs.
All eleven supplied files were checked against official Lucide repository commit
`1fae58d0a9c661a338036838caf3399b5507bab6`: drawing geometry and standard SVG
attributes match after whitespace/comma normalization. Download formatting and
preview classes differ from repository files. The ten used SVGs were copied
without byte changes; the spare `map.svg` was not copied.

The [asset manifest](../server/admin_portal/static/admin_portal/icons/lucide/manifest.json)
records each source, mapping and checksum. The complete upstream
[LICENSE](../server/admin_portal/static/admin_portal/icons/lucide/LICENSE) retains
the ISC copyright/permission notice and MIT notice for Feather-derived assets,
including monitor and clock. Keep it with copied or deployed assets. A visible
interface attribution link is not required by the
[Lucide license](https://lucide.dev/license).

## Behavior and scope

Icons remain decorative, reserve 20px square space, inherit interface colors and
have no focus stop or pointer interaction. Existing link/button names provide
accessible labels. CSS masks render the SVG strokes, with original images as a
fallback where masks are unsupported. Account menu fallback images use a dark
color for its light panel.

Sidebar widths, navigation routes and permissions, hover tooltips, Ctrl+B,
profile presentation, mobile drawer and POST sign-out are preserved. Branding,
avatar initials, the sidebar toggle, mobile menu and unrelated page controls retain
their existing artwork. This update affects the Web Admin only.

No model, migration, data row, scientific rule, assessment parameter, publication
policy, mobile code or environment setting changed. The private `server/.env` was
neither read nor modified. Test setup disables dotenv loading and uses an ignored
runner with an isolated local PostGIS database.

## Validation

Completed: Django system check, Ruff for the portal and browser script, and
`git diff --check`. The Admin portal suite passed **195 tests**. The Chromium
acceptance test passed, covering all ten image loads, reserved dimensions,
interface colors, absence of the old credit/assets, expanded/collapsed navigation,
all eight destinations, hover tooltips, Ctrl+B, profile menu and POST sign-out,
mobile drawer, reduced motion and JavaScript-disabled rendering. Existing
staticfiles-directory and Django URLField deprecation warnings remain.

All ten copied SVG checksums match the owner's downloads. Both upstream license
notices are present. The isolated QA PostgreSQL instance was stopped afterward;
no application database was used.

Desktop, mobile and collapsed-profile screenshots were visually inspected:

- [Desktop](../tmp/portal-layout-qa/icons-1440-after.png)
- [Tablet](../tmp/portal-layout-qa/icons-768-after.png)
- [Mobile drawer](../tmp/portal-layout-qa/icons-390-after.png)
- [Collapsed profile menu](../tmp/portal-layout-qa/profile-collapsed.png)

These ignored local QA images use synthetic records and do not travel through
Git. The browser script also captures original navigation symbols for comparison
by replacing only their contents in the QA DOM; those images are not screenshots
of a separately deployed previous build.

## Teammate steps

No dependency installation, migration, seed or import is required. Restart Django
and refresh `/management/`; the CSS cache version was updated. Normal development
static serving finds the SVGs automatically. Deployments that collect static files
should run their usual `collectstatic --noinput` step so SVGs and LICENSE travel
together.

Ordinary checks on an already configured development checkout:

```powershell
server\.venv\Scripts\python.exe server\manage.py check
server\.venv\Scripts\python.exe -m pytest server/admin_portal --reuse-db
```

Optional browser acceptance uses the existing Playwright/Chromium QA installation
and an isolated PostGIS test database:

```powershell
server\.venv\Scripts\python.exe -m pytest scripts/verify_admin_portal_layout.py --reuse-db
```

No Git pull/push, shared database migration or official-data import was performed.
