$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repositoryRoot "server\.venv\Scripts\python.exe"
$ruffPath = Join-Path $repositoryRoot "server\.venv\Scripts\ruff.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Backend virtual environment is missing. Create server/.venv first."
}

$previousDatabaseUrl = $env:DATABASE_URL
$previousGisEnabled = $env:FLOODSENSE_GIS_ENABLED

try {
    # Bootstrap verification deliberately avoids GIS until the native Windows
    # libraries and PostgreSQL/PostGIS service are installed.
    $env:DATABASE_URL = "sqlite:///:memory:"
    $env:FLOODSENSE_GIS_ENABLED = "false"

    & $pythonPath (Join-Path $repositoryRoot "server\manage.py") check
    if ($LASTEXITCODE -ne 0) { throw "Django system check failed." }

    & $pythonPath -m pytest (Join-Path $repositoryRoot "server\core\tests.py") -q
    if ($LASTEXITCODE -ne 0) { throw "Backend tests failed." }

    & $ruffPath check (Join-Path $repositoryRoot "server")
    if ($LASTEXITCODE -ne 0) { throw "Backend lint check failed." }
}
finally {
    $env:DATABASE_URL = $previousDatabaseUrl
    $env:FLOODSENSE_GIS_ENABLED = $previousGisEnabled
}

