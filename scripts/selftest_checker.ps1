#Requires -Version 5.1
<#
.SYNOPSIS
    Mutation test for scripts/check_public_safe.ps1.

.DESCRIPTION
    A check that has never been observed to fail is not a check. This script
    proves the gate can fail, by running it against deliberately broken
    fixtures and asserting that it rejects them.

    Everything happens in a disposable Git repository created under the system
    temporary directory, never inside the real project, so a fixture can never
    be staged by accident. The temporary repository is removed afterwards and
    its removal is asserted.

    The fake credential is assembled at run time from fragments. Writing it as a
    literal would place a matchable credential signature into a tracked file and
    the gate would, correctly, reject its own self-test.

    The clean fixture is a bare repository with nothing but the checker and a
    readme: the gate requires no personal-identity fixture of any kind to pass.

    Asserted behaviour:
      1. fixture containing a fake credential  -> FAIL (exit 1)
      2. fixture containing an oversized file  -> FAIL (exit 1)
      3. clean fixture                         -> PASS (exit 0)
      4. temporary repository is removed
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$repoRoot   = Split-Path -Parent $PSScriptRoot
$checkerSrc = Join-Path $PSScriptRoot 'check_public_safe.ps1'

if (-not (Test-Path -LiteralPath $checkerSrc)) {
    Write-Error "Checker not found: $checkerSrc"
}

$sandbox = Join-Path ([System.IO.Path]::GetTempPath()) ("checker-selftest-" + [guid]::NewGuid().ToString('N').Substring(0, 12))

if ($sandbox.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Error "Refusing to run: sandbox would be inside the real repository."
}

$results = @()

function New-Sandbox {
    if (Test-Path -LiteralPath $sandbox) { Remove-Item -LiteralPath $sandbox -Recurse -Force }
    New-Item -ItemType Directory -Path $sandbox -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $sandbox 'scripts') -Force | Out-Null

    Copy-Item -LiteralPath $checkerSrc -Destination (Join-Path $sandbox 'scripts\check_public_safe.ps1') -Force

    & git -C $sandbox init -q
    & git -C $sandbox config user.email 'selftest@users.noreply.github.com'
    & git -C $sandbox config user.name  'selftest'

    Set-Content -LiteralPath (Join-Path $sandbox 'README.md') -Value 'Clean fixture.' -Encoding UTF8
}

function Invoke-Checker {
    $out = & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $sandbox 'scripts\check_public_safe.ps1') -Mode PreCommit
    return [pscustomobject]@{ Exit = $LASTEXITCODE; Output = ($out -join "`n") }
}

function Assert-Case {
    param([string]$Name, [int]$Expected, [int]$Actual)
    $ok = ($Expected -eq $Actual)
    $verdict = 'FAIL'
    if ($ok) { $verdict = 'ok' }
    Write-Host ("  [{0}] {1}  expected exit {2}, got {3}" -f $verdict, $Name, $Expected, $Actual)
    $script:results += [pscustomobject]@{ Name = $Name; Ok = $ok }
}

try {
    Write-Host "checker mutation self-test"
    Write-Host ""

    # --- Case 1: fake credential must FAIL -------------------------------
    New-Sandbox
    $fake = 'gh' + 'p_' + ('x' * 36)
    Set-Content -LiteralPath (Join-Path $sandbox 'leaky.txt') -Value ("api access: " + $fake) -Encoding UTF8
    $r1 = Invoke-Checker
    Assert-Case -Name 'fake credential is rejected' -Expected 1 -Actual $r1.Exit

    # --- Case 2: oversized file must FAIL --------------------------------
    New-Sandbox
    $big = New-Object byte[] (12 * 1024 * 1024)
    [System.IO.File]::WriteAllBytes((Join-Path $sandbox 'big.dat'), $big)
    $r2 = Invoke-Checker
    Assert-Case -Name 'oversized file is rejected' -Expected 1 -Actual $r2.Exit

    # --- Case 3: clean fixture must PASS ---------------------------------
    New-Sandbox
    $r3 = Invoke-Checker
    Assert-Case -Name 'clean fixture is accepted' -Expected 0 -Actual $r3.Exit
    if ($r3.Exit -ne 0) {
        Write-Host ""
        Write-Host "clean-fixture output:"
        Write-Host $r3.Output
    }
}
finally {
    if (Test-Path -LiteralPath $sandbox) {
        Remove-Item -LiteralPath $sandbox -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
$removed = -not (Test-Path -LiteralPath $sandbox)
$verdict = 'FAIL'
if ($removed) { $verdict = 'ok' }
Write-Host ("  [{0}] sandbox removed" -f $verdict)
$results += [pscustomobject]@{ Name = 'sandbox removed'; Ok = $removed }

if ($results.Count -lt 4) {
    Write-Host ""
    Write-Host ("RESULT: FAIL (expected 4 assertions, ran " + $results.Count + ")")
    exit 1
}

$failed = @($results | Where-Object { -not $_.Ok })
Write-Host ""
if ($failed.Count -gt 0) {
    Write-Host ("RESULT: FAIL (" + $failed.Count + " of " + $results.Count + " assertions failed)")
    exit 1
}
Write-Host ("RESULT: PASS (" + $results.Count + " assertions)")
exit 0
