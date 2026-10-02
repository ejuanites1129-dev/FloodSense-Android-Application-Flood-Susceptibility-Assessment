param(
    [string[]]$TestArgs = @('server', '--create-db', '-q'),
    [int]$Port = 55433
)
$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$postgresBin = 'C:\Program Files\PostgreSQL\17\bin'
$pythonPath = Join-Path $repositoryRoot 'server\.venv\Scripts\python.exe'
$clusterPath = Join-Path $repositoryRoot ('tmp\operations-postgres-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $clusterPath | Out-Null
$previousDatabaseUrl = $env:DATABASE_URL
$testExitCode = 1
try {
    & (Join-Path $postgresBin 'initdb.exe') -D $clusterPath -U floodsense_qa --auth=trust --encoding=UTF8 --locale=C
    if ($LASTEXITCODE -ne 0) { throw 'Isolated PostgreSQL initialization failed.' }
    & (Join-Path $postgresBin 'pg_ctl.exe') -D $clusterPath -l (Join-Path $clusterPath 'postgres.log') -o "-h 127.0.0.1 -p $Port" -w start
    if ($LASTEXITCODE -ne 0) { throw 'Isolated PostgreSQL startup failed; check the requested port.' }
    & (Join-Path $postgresBin 'createdb.exe') -h 127.0.0.1 -p $Port -U floodsense_qa floodsense_operations_qa
    if ($LASTEXITCODE -ne 0) { throw 'Isolated QA database creation failed.' }
    $env:DATABASE_URL = "postgis://floodsense_qa@127.0.0.1:$Port/floodsense_operations_qa"
    Push-Location $repositoryRoot
    try {
        & $pythonPath -m pytest @TestArgs
        $testExitCode = $LASTEXITCODE
    } finally { Pop-Location }
} finally {
    $env:DATABASE_URL = $previousDatabaseUrl
    if (Test-Path -LiteralPath (Join-Path $clusterPath 'postmaster.pid')) {
        & (Join-Path $postgresBin 'pg_ctl.exe') -D $clusterPath -m fast -w stop
    }
    Write-Output "Stopped isolated test cluster retained under ignored path: $clusterPath"
}
exit $testExitCode
