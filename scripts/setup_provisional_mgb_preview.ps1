param(
    [switch]$AcknowledgeProvisionalUse,
    [switch]$Refresh
)

$ErrorActionPreference = 'Stop'

if (-not $AcknowledgeProvisionalUse) {
    throw (
        'This command downloads and imports an unapproved MGB-derived local ' +
        'consultation preview. Rerun with -AcknowledgeProvisionalUse only on ' +
        'an authorized development computer after reading the MGB README.'
    )
}

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonPath = Join-Path $repositoryRoot 'server\.venv\Scripts\python.exe'
$managePath = Join-Path $repositoryRoot 'server\manage.py'
$extractPath = Join-Path $repositoryRoot 'scripts\extract_mgb_bacoor_flood_susceptibility.py'

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Backend virtual environment is missing. Create server/.venv first.'
}

Push-Location $repositoryRoot
try {
    $guardState = & $pythonPath $managePath shell -c (
        "from django.conf import settings; " +
        "print('READY' if settings.DEBUG and settings.ENABLE_PROVISIONAL_MGB_PREVIEW else 'NOT_READY')"
    )
    if ($LASTEXITCODE -ne 0) { throw 'Unable to read the Django preview settings.' }
    if (($guardState | Select-Object -Last 1).Trim() -ne 'READY') {
        throw (
            'Local activation requires DJANGO_DEBUG=True and ' +
            'FLOODSENSE_ENABLE_PROVISIONAL_MGB_PREVIEW=True in the ignored server/.env.'
        )
    }

    & $pythonPath $managePath migrate
    if ($LASTEXITCODE -ne 0) { throw 'Django migrations failed.' }

    & $pythonPath $managePath seed_demo
    if ($LASTEXITCODE -ne 0) { throw 'Demonstration and boundary setup failed.' }

    $extractArguments = @($extractPath)
    if ($Refresh) { $extractArguments += '--refresh' }
    & $pythonPath @extractArguments
    if ($LASTEXITCODE -ne 0) { throw 'The provisional MGB extraction failed.' }

    & $pythonPath $managePath import_mgb_susceptibility --activate-consultation-preview
    if ($LASTEXITCODE -ne 0) { throw 'The provisional MGB import failed.' }

    Write-Output (
        'Local provisional MGB consultation preview is active. The imported ' +
        'area-composition values remain pending validation and are not Expert ' +
        'System parameter definitions or official barangay classifications.'
    )
}
finally {
    Pop-Location
}
