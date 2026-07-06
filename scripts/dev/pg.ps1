<#
AGRIOS — Native PostgreSQL lifecycle helper (Windows)

Used when Docker is unavailable. Manages the local Postgres 16 cluster that
backs the dev (`agrios`) and test (`agrios_test`) databases on port 5432.

The Docker path (infrastructure/docker-compose.yml) is the canonical, portable
definition and is byte-for-byte interchangeable with this native cluster.

Usage:
  ./scripts/dev/pg.ps1 start     # start the cluster
  ./scripts/dev/pg.ps1 stop      # stop the cluster
  ./scripts/dev/pg.ps1 status    # show status
  ./scripts/dev/pg.ps1 bootstrap # create agrios + agrios_test databases
#>
param(
  [Parameter(Position = 0)]
  [ValidateSet('start', 'stop', 'status', 'bootstrap')]
  [string]$Command = 'status'
)

$ErrorActionPreference = 'Stop'
$PgHome  = Join-Path $env:LOCALAPPDATA 'AGRIOS\pgsql'
$PgData  = Join-Path $env:LOCALAPPDATA 'AGRIOS\pgdata'
$PgLog   = Join-Path $env:LOCALAPPDATA 'AGRIOS\pg.log'
$Bin     = Join-Path $PgHome 'bin'
$Port    = 5432

function Invoke-Pg([string]$exe, [string[]]$pgArgs) { & (Join-Path $Bin $exe) @pgArgs }

switch ($Command) {
  'start' {
    Invoke-Pg 'pg_ctl.exe' @('-D', $PgData, '-l', $PgLog, '-o', "-p $Port", 'start')
  }
  'stop' {
    Invoke-Pg 'pg_ctl.exe' @('-D', $PgData, 'stop', '-m', 'fast')
  }
  'status' {
    Invoke-Pg 'pg_ctl.exe' @('-D', $PgData, 'status')
    Invoke-Pg 'pg_isready.exe' @('-p', "$Port")
  }
  'bootstrap' {
    $env:PGPASSWORD = 'postgres'
    $psql = Join-Path $Bin 'psql.exe'
    foreach ($db in @('agrios', 'agrios_test')) {
      $exists = & $psql -U postgres -h localhost -p $Port -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$db'"
      if ($exists -ne '1') {
        & $psql -U postgres -h localhost -p $Port -d postgres -c "CREATE DATABASE $db"
        Write-Host "created database $db"
      } else {
        Write-Host "database $db already exists"
      }
    }
  }
}
