# UTF-8 check (ASCII-only source for PS 5.1). Usage: .\.cursor\scripts\verify-utf8.ps1
$ErrorActionPreference = 'Stop'
$fail = 0

function Assert-Ok($label, $cond) {
    if ($cond) { Write-Host "[OK] $label" }
    else { Write-Host "[FAIL] $label"; $script:fail++ }
}

$utf8Init = Join-Path $env:USERPROFILE '.cursor\ensure-utf8.ps1'
Assert-Ok 'ensure-utf8.ps1 exists' (Test-Path -LiteralPath $utf8Init)

. $utf8Init
$cp = (chcp) -replace '\D', ''
Assert-Ok "code page 65001 (got $cp)" ($cp -eq '65001')

$day = Get-Date -Format '(dddd)'
Assert-Ok "locale weekday ($day)" ($day -match '[\uAC00-\uD7A3]')

$hanExpected = -join ([char]0xD55C, [char]0xAE00, [char]0x20, [char]0xD14C, [char]0xC2A4, [char]0xD2B8)
$pyOut = (python -c "print('\uD55C\uAE00 \uD14C\uC2A4\uD2B8')" 2>&1 | Out-String).Trim()
Assert-Ok "python stdout ($pyOut)" ($pyOut -eq $hanExpected)

$profilePath = $PROFILE
Assert-Ok "PowerShell profile ($profilePath)" (Test-Path -LiteralPath $profilePath)

if ($fail -gt 0) {
    Write-Host ""
    Write-Host "$fail check(s) failed."
    exit 1
}
Write-Host ""
Write-Host "All UTF-8 checks passed."
exit 0
