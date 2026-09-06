$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repositoryRoot "server\.venv\Scripts\python.exe"
$managePath = Join-Path $repositoryRoot "server\manage.py"
$envPath = Join-Path $repositoryRoot "server\.env"

if (-not (Test-Path -LiteralPath $envPath)) {
    throw "server/.env is missing. Copy server/.env.example and set the database values first."
}

& $pythonPath $managePath shell -c "from django.contrib.gis import gdal; from django.contrib.gis.geos import geos_version; print('GDAL:', gdal.GDAL_VERSION); print('GEOS:', geos_version().decode())"
if ($LASTEXITCODE -ne 0) { throw "GDAL/GEOS verification failed." }

& $pythonPath $managePath check
if ($LASTEXITCODE -ne 0) { throw "Django/PostGIS system check failed." }

& $pythonPath $managePath migrate
if ($LASTEXITCODE -ne 0) { throw "Django migrations failed." }

& $pythonPath $managePath shell -c "from django.db import connection; c=connection.cursor(); c.execute('SELECT PostGIS_Version()'); print('PostGIS:', c.fetchone()[0])"
if ($LASTEXITCODE -ne 0) { throw "PostGIS database query failed." }
