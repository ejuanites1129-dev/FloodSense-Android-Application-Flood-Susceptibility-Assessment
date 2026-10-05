param(
    [string]$DeviceId,
    [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'
$floodSenseRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$floodSensePython = Join-Path $floodSenseRoot 'server\.venv\Scripts\python.exe'
$floodSenseAdb = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
$floodSenseFlutter = (Get-Command flutter -ErrorAction Stop).Source
if (-not (Test-Path -LiteralPath $floodSensePython) -or -not (Test-Path -LiteralPath $floodSenseAdb)) {
    throw 'The existing backend virtual environment and Android SDK platform tools are required.'
}

Push-Location $floodSenseRoot
try {
    # Capture only the public client token and safe flags, never the full .env.
    $floodSenseConfigJson = & $floodSensePython server/manage.py shell --verbosity 0 -c "import json; from django.conf import settings; d=settings.DATABASES['default']; print(json.dumps({'debug':settings.DEBUG,'local_postgis':d.get('HOST') in {'localhost','127.0.0.1','::1'} and d.get('ENGINE')=='django.contrib.gis.db.backends.postgis','preview':settings.ENABLE_LOCAL_CENTER_PREVIEW,'token':settings.MAPBOX_ACCESS_TOKEN,'three_d':settings.FLOODSENSE_MAP_3D}))"
    if ($LASTEXITCODE -ne 0) { throw 'Could not load local development settings.' }
    $floodSenseConfig = $floodSenseConfigJson | ConvertFrom-Json
    if (-not $floodSenseConfig.debug -or -not $floodSenseConfig.local_postgis -or -not $floodSenseConfig.preview) {
        throw 'This preview requires DEBUG, local PostGIS and FLOODSENSE_ENABLE_LOCAL_CENTER_PREVIEW=true.'
    }
    if (-not $floodSenseConfig.token.StartsWith('pk.')) {
        throw 'A public Mapbox pk token must already be configured in the private server/.env.'
    }

    $floodSenseConnectedIds = @(
        & $floodSenseAdb devices |
            Select-String '^\S+\s+device$' |
            ForEach-Object { ($_.Line -split '\s+')[0] }
    )
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect Android devices.' }
    $floodSenseWirelessIds = @($floodSenseConnectedIds | Where-Object { $_ -match '\._adb-tls-connect\._tcp$' })
    if (-not $DeviceId) {
        if ($floodSenseWirelessIds.Count -eq 1) {
            $DeviceId = $floodSenseWirelessIds[0]
        } elseif ($floodSenseConnectedIds.Count -eq 1) {
            $DeviceId = $floodSenseConnectedIds[0]
        } else {
            throw 'Connect one authorized Android device, or pass -DeviceId with its current adb devices ID.'
        }
    }
    if ($DeviceId -notin $floodSenseConnectedIds) {
        throw 'The requested device is not connected. Check Wireless debugging or USB authorization.'
    }
    Write-Output "Selected Android device: $DeviceId"
    Write-Output 'Mapbox public token is configured; local demonstration preview is enabled.'
    if ($ValidateOnly) {
        Write-Output 'Validation only: no forwarding, build, installation or app launch performed.'
        return
    }

    $floodSenseHealth = Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/health/' -TimeoutSec 5
    if ($floodSenseHealth.status -ne 'ok') { throw 'Start the local Django server on 127.0.0.1:8000 first.' }
    # An empty lookup checks the running process's opt-in without querying centers.
    try {
        $floodSensePreviewProbe = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/v1/evacuation-centers/local-preview/nearest/' -Method Post -ContentType 'application/json' -Body '{}' -UseBasicParsing -TimeoutSec 5
        $floodSensePreviewStatus = [int]$floodSensePreviewProbe.StatusCode
    } catch {
        if (-not $_.Exception.Response) { throw }
        $floodSensePreviewStatus = [int]$_.Exception.Response.StatusCode
    }
    if ($floodSensePreviewStatus -eq 404) {
        throw 'Restart Django on 127.0.0.1:8000 so it loads FLOODSENSE_ENABLE_LOCAL_CENTER_PREVIEW=true, then run this helper again.'
    }
    if ($floodSensePreviewStatus -ne 400) {
        throw "The local preview readiness check returned HTTP $floodSensePreviewStatus; resolve that server response before launching Flutter."
    }
    & $floodSenseAdb -s $DeviceId reverse tcp:8000 tcp:8000
    if ($LASTEXITCODE -ne 0) { throw 'Could not forward the phone connection to Django.' }
    Set-Location (Join-Path $floodSenseRoot 'mobile')
    & $floodSenseFlutter run -d $DeviceId `
        --dart-define=FLOODSENSE_API_BASE_URL=http://127.0.0.1:8000/api/v1 `
        --dart-define=FLOODSENSE_MAP_PROVIDER=mapbox `
        "--dart-define=MAPBOX_ACCESS_TOKEN=$($floodSenseConfig.token)" `
        "--dart-define=FLOODSENSE_MAP_3D=$($floodSenseConfig.three_d.ToString().ToLowerInvariant())" `
        --dart-define=FLOODSENSE_ENABLE_LOCAL_CENTER_PREVIEW=true
    if ($LASTEXITCODE -ne 0) { throw 'Flutter did not finish successfully. Review its build or connection output.' }
} finally {
    Remove-Variable floodSenseConfig,floodSenseConfigJson -ErrorAction SilentlyContinue
    Pop-Location
}
