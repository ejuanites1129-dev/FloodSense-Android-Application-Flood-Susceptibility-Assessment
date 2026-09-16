[CmdletBinding()]
param(
    [string]$SourceDirectory = "",
    [string]$OutputDirectory = "",
    [string]$Ogr2OgrPath = "C:\Program Files\PostgreSQL\17\bin\ogr2ogr.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceDirectory)) {
    $SourceDirectory = Join-Path $PSScriptRoot "..\research_data\administrative_boundaries"
}

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $PSScriptRoot "..\research_data\administrative_boundaries\processed"
}

$bacoorPcode = "PH0402103"
$adm3Path = Join-Path $SourceDirectory "phl_admin3.geojson"
$adm4Path = Join-Path $SourceDirectory "phl_admin4.geojson"
$cityOutput = Join-Path $OutputDirectory "bacoor_city_boundary.geojson"
$barangayOutput = Join-Path $OutputDirectory "bacoor_barangay_boundaries_legacy_73.geojson"

foreach ($requiredPath in @($Ogr2OgrPath, $adm3Path, $adm4Path)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required file was not found: $requiredPath"
    }
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$resolvedOutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory).TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
)

foreach ($generatedPath in @($cityOutput, $barangayOutput)) {
    $resolvedGeneratedPath = [System.IO.Path]::GetFullPath($generatedPath)
    $expectedPrefix = $resolvedOutputDirectory + [System.IO.Path]::DirectorySeparatorChar
    if (-not $resolvedGeneratedPath.StartsWith(
        $expectedPrefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to replace a file outside the output directory: $resolvedGeneratedPath"
    }
    if (Test-Path -LiteralPath $resolvedGeneratedPath -PathType Leaf) {
        Remove-Item -LiteralPath $resolvedGeneratedPath
    }
}

$commonArguments = @(
    "-f", "GeoJSON",
    "-lco", "RFC7946=YES",
    "-lco", "WRITE_BBOX=YES",
    "-lco", "COORDINATE_PRECISION=7"
)

$cityFields = @(
    "adm3_name", "adm3_ref_name", "adm3_pcode",
    "adm2_name", "adm2_pcode", "adm1_name", "adm1_pcode",
    "adm0_name", "adm0_pcode", "valid_on", "valid_to",
    "area_sqkm", "version", "lang", "center_lat", "center_lon"
) -join ","

& $Ogr2OgrPath @commonArguments `
    "-where" "adm3_pcode = '$bacoorPcode'" `
    "-select" $cityFields `
    $cityOutput $adm3Path "phl_admin3"

if ($LASTEXITCODE -ne 0) {
    throw "Bacoor city boundary extraction failed with exit code $LASTEXITCODE."
}

$barangayFields = @(
    "adm4_name", "adm4_ref_name", "adm4_pcode",
    "adm3_name", "adm3_pcode", "adm2_name", "adm2_pcode",
    "adm1_name", "adm1_pcode", "adm0_name", "adm0_pcode",
    "valid_on", "valid_to", "area_sqkm", "version", "lang",
    "center_lat", "center_lon"
) -join ","

& $Ogr2OgrPath @commonArguments `
    "-where" "adm3_pcode = '$bacoorPcode'" `
    "-select" $barangayFields `
    $barangayOutput $adm4Path "phl_admin4"

if ($LASTEXITCODE -ne 0) {
    throw "Bacoor barangay boundary extraction failed with exit code $LASTEXITCODE."
}

Write-Host "Created: $cityOutput"
Write-Host "Created: $barangayOutput"
Write-Host "These files are reference boundaries and are not flood-hazard data."
