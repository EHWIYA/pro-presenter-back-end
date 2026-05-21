# 로컬 pytest (UTF-8 보장). 사용: .\.cursor\scripts\dev-test.ps1
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$ApiRoot = Join-Path $RepoRoot 'api'
Set-Location $ApiRoot
. (Join-Path $PSScriptRoot 'ensure-utf8.ps1')

$venvPython = Join-Path $ApiRoot '.venv\Scripts\python.exe'
$venvPip = Join-Path $ApiRoot '.venv\Scripts\pip.exe'
if (-not (Test-Path $venvPython)) {
    python -m venv .venv
}
& $venvPip install -q -r requirements-dev.txt
& $venvPython -m pytest -q @args
exit $LASTEXITCODE
