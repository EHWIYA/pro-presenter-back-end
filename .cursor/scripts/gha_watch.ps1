# GHA 추적·실패 분석. 사용: .\.cursor\scripts\gha_watch.ps1 [-Sha <sha>] [-NoWait]
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $RepoRoot
. (Join-Path $PSScriptRoot 'ensure-utf8.ps1')

$pyArgs = @('.cursor/scripts/gha_watch.py')
if ($Sha) { $pyArgs += '--sha', $Sha }
if ($NoWait) { $pyArgs += '--no-wait' }
python @pyArgs
exit $LASTEXITCODE
