<#
AGRIOS — Repeatable verification pipeline (Windows / native Postgres)

The mandatory end-of-phase gate. Run before every commit. Any failing stage
aborts with a non-zero exit code.

  ./scripts/dev/verify.ps1            # full pipeline (backend + frontend)
  ./scripts/dev/verify.ps1 backend    # backend only
  ./scripts/dev/verify.ps1 frontend   # frontend only

Stages (backend): alembic upgrade head -> pytest -> ruff -> mypy
Stages (frontend): npm run lint -> tsc typecheck -> npm run build
#>
param(
  [Parameter(Position = 0)]
  [ValidateSet('all', 'backend', 'frontend')]
  [string]$Target = 'all'
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$Py = Join-Path $Backend '.venv\Scripts\python.exe'

# Test DB is explicit so it never depends on fragile URL string-munging.
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://postgres:postgres@localhost:5432/agrios_test'

function Assert-LastExit([string]$stage) {
  if ($LASTEXITCODE -ne 0) { Write-Host "`n[X] FAILED: $stage (exit $LASTEXITCODE)" -ForegroundColor Red; exit $LASTEXITCODE }
  Write-Host "[OK] $stage" -ForegroundColor Green
}

function Invoke-Backend {
  Write-Host "`n=== BACKEND VERIFICATION ===" -ForegroundColor Cyan
  # Ensure the native cluster is up.
  & (Join-Path $PSScriptRoot 'pg.ps1') status | Out-Null
  Push-Location $Backend
  try {
    & $Py -m alembic upgrade head;              Assert-LastExit 'alembic upgrade head'
    & $Py -m pytest -q;                          Assert-LastExit 'pytest'
    & $Py -m ruff check .;                       Assert-LastExit 'ruff check'
    & $Py -m mypy app;                           Assert-LastExit 'mypy'
  } finally { Pop-Location }
}

function Invoke-Frontend {
  Write-Host "`n=== FRONTEND VERIFICATION ===" -ForegroundColor Cyan
  Push-Location $Frontend
  try {
    & npm run lint;                              Assert-LastExit 'npm run lint'
    & npx tsc --noEmit;                          Assert-LastExit 'tsc --noEmit'
    & npm run build;                             Assert-LastExit 'npm run build'
  } finally { Pop-Location }
}

if ($Target -in @('all', 'backend'))  { Invoke-Backend }
if ($Target -in @('all', 'frontend')) { Invoke-Frontend }

Write-Host "`nAll verification stages passed." -ForegroundColor Green
