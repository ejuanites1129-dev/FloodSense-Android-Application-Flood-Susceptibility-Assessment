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
    throw 'The backend virtual environment and Android SDK platform tools are required.'
}

Push-Location $floodSenseRoot
try {
    # Capture only safe settings and the public client token. Never print the .env/token.
    $floodSenseConfigJson = & $floodSensePython server/manage.py shell --verbosity 0 -c "import json; from django.conf import settings; from core.local_testing import local_testing_enabled; print(json.dumps({'debug':settings.DEBUG,'testing':local_testing_enabled(),'token':settings.MAPBOX_ACCESS_TOKEN,'three_d':settings.FLOODSENSE_MAP_3D}))"
    if ($LASTEXITCODE -ne 0) { throw 'Could not load local development settings.' }
    $floodSenseConfig = $floodSenseConfigJson | ConvertFrom-Json
    if (-not $floodSenseConfig.debug) { throw 'This helper is for local DEBUG development only.' }
    if (-not $floodSenseConfig.token -or -not $floodSenseConfig.token.StartsWith('pk.')) {
        throw 'Configure the public Mapbox pk token in the private server/.env first.'
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
            throw 'Connect one authorized phone, or pass -DeviceId with its current adb devices ID.'
        }
    }
    if ($DeviceId -notin $floodSenseConnectedIds) {
        throw 'The requested device is not connected. Check Wireless debugging or USB authorization.'
    }
    Write-Output "Selected Android device: $DeviceId"
    Write-Output "Normal application endpoint; local temporary-data mode: $($floodSenseConfig.testing)."
    Write-Output 'Mapbox public token is configured. Restart Django after changing its settings.'
    if ($ValidateOnly) {
        Write-Output 'Validation only: no forwarding, build, installation or launch performed.'
        return
    }
    $floodSenseHealth = Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/health/' -TimeoutSec 5
    if ($floodSenseHealth.status -ne 'ok') { throw 'Start Django on 127.0.0.1:8000 first.' }
    & $floodSenseAdb -s $DeviceId reverse tcp:8000 tcp:8000
    if ($LASTEXITCODE -ne 0) { throw 'Could not forward the phone connection to Django.' }
    Set-Location (Join-Path $floodSenseRoot 'mobile')
    & $floodSenseFlutter run -d $DeviceId `
        --dart-define=FLOODSENSE_API_BASE_URL=http://127.0.0.1:8000/api/v1 `
        --dart-define=FLOODSENSE_MAP_PROVIDER=mapbox `
        "--dart-define=MAPBOX_ACCESS_TOKEN=$($floodSenseConfig.token)" `
        "--dart-define=FLOODSENSE_MAP_3D=$($floodSenseConfig.three_d.ToString().ToLowerInvariant())"
    if ($LASTEXITCODE -ne 0) { throw 'Flutter did not finish successfully. Review its output.' }
} finally {
    Remove-Variable floodSenseConfig,floodSenseConfigJson -ErrorAction SilentlyContinue
    Pop-Location
}
