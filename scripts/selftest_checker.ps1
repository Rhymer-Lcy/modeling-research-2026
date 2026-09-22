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
    be staged by accident and the real project's history is never manipulated.
    The temporary repository is removed afterwards and its removal is asserted.

    The fake credential and the fake machine path are assembled at run time
    from fragments. Writing either as a literal would place a matchable finding
    into a tracked file and the gate would, correctly, reject its own
    self-test.

    The sandbox writes its own configs/git-email-policy.txt using fixture
    addresses. The email rules are therefore proven generically, without this
    file needing to restate any address used by the real project.

    Asserted behaviour:
      1. approved-suffix author and committer      -> PASS (exit 0)
      2. GitHub web-flow server-side committer      -> PASS (exit 0)
      3. approved exact public address              -> PASS (exit 0)
      4. unapproved personal-style address          -> FAIL (exit 1)
      5. fixture containing a fake credential       -> FAIL (exit 1)
      6. fixture containing an oversized file       -> FAIL (exit 1)
      7. fixture containing an absolute local path  -> FAIL (exit 1)
      8. clean fixture                              -> PASS (exit 0)
      9. temporary repository is removed
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

# Fixture addresses. These are test data, not anyone's real address.
$ApprovedSuffixAddr = 'fixture-user@users.noreply.github.com'
$WebFlowAddr        = 'noreply@github.com'
$ApprovedExactAddr  = 'approved-public@example.com'
$UnapprovedAddr     = 'someone-personal@example.net'

$results = @()

function New-Sandbox {
    if (Test-Path -LiteralPath $sandbox) { Remove-Item -LiteralPath $sandbox -Recurse -Force }
    New-Item -ItemType Directory -Path $sandbox -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $sandbox 'scripts') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $sandbox 'configs') -Force | Out-Null

    Copy-Item -LiteralPath $checkerSrc -Destination (Join-Path $sandbox 'scripts\check_public_safe.ps1') -Force

    Set-Content -LiteralPath (Join-Path $sandbox 'configs\git-email-policy.txt') -Encoding UTF8 -Value @(
        '# Fixture policy for the checker self-test.',
        'suffix @users.noreply.github.com',
        ('exact ' + $WebFlowAddr),
        ('exact ' + $ApprovedExactAddr)
    )

    & git -C $sandbox init -q
    & git -C $sandbox config user.email $ApprovedSuffixAddr
    & git -C $sandbox config user.name  'fixture'

    Set-Content -LiteralPath (Join-Path $sandbox 'README.md') -Value 'Clean fixture.' -Encoding UTF8
}

function New-SandboxCommit {
    param([string]$AuthorEmail, [string]$CommitterEmail)
    Add-Content -LiteralPath (Join-Path $sandbox 'README.md') -Value 'change' -Encoding UTF8
    & git -C $sandbox add -A
    & git -C $sandbox -c "user.name=fixture" -c "user.email=$CommitterEmail" `
        commit -q -m "chore(fixture): add content [T-000]" --author="fixture <$AuthorEmail>"
}

function Invoke-Checker {
    param([string]$Mode = 'PreCommit')
    $out = & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $sandbox 'scripts\check_public_safe.ps1') -Mode $Mode
    return [pscustomobject]@{ Exit = $LASTEXITCODE; Output = ($out -join "`n") }
}

function Assert-Case {
    param([string]$Name, [int]$Expected, [int]$Actual, [string]$Output = '')
    $ok = ($Expected -eq $Actual)
    $verdict = 'FAIL'
    if ($ok) { $verdict = 'ok' }
    Write-Host ("  [{0}] {1}  expected exit {2}, got {3}" -f $verdict, $Name, $Expected, $Actual)
    if (-not $ok -and $Output -ne '') {
        Write-Host "      ---- checker output ----"
        Write-Host $Output
    }
    $script:results += [pscustomobject]@{ Name = $Name; Ok = $ok }
}

try {
    Write-Host "checker mutation self-test"
    Write-Host ""

    # --- Case 1: approved suffix author and committer -> PASS ------------
    New-Sandbox
    New-SandboxCommit -AuthorEmail $ApprovedSuffixAddr -CommitterEmail $ApprovedSuffixAddr
    $r1 = Invoke-Checker -Mode PrePush
    Assert-Case -Name 'approved-suffix author and committer accepted' -Expected 0 -Actual $r1.Exit -Output $r1.Output

    # --- Case 2: GitHub web-flow server-side committer -> PASS -----------
    New-Sandbox
    New-SandboxCommit -AuthorEmail $ApprovedSuffixAddr -CommitterEmail $WebFlowAddr
    $r2 = Invoke-Checker -Mode PrePush
    Assert-Case -Name 'github web-flow committer accepted' -Expected 0 -Actual $r2.Exit -Output $r2.Output

    # --- Case 3: approved exact public address -> PASS -------------------
    New-Sandbox
    New-SandboxCommit -AuthorEmail $ApprovedExactAddr -CommitterEmail $WebFlowAddr
    $r3 = Invoke-Checker -Mode PrePush
    Assert-Case -Name 'approved exact public address accepted' -Expected 0 -Actual $r3.Exit -Output $r3.Output

    # --- Case 4: unapproved personal-style address -> FAIL ---------------
    New-Sandbox
    New-SandboxCommit -AuthorEmail $UnapprovedAddr -CommitterEmail $ApprovedSuffixAddr
    $r4 = Invoke-Checker -Mode PrePush
    Assert-Case -Name 'unapproved address is rejected' -Expected 1 -Actual $r4.Exit

    # --- Case 5: fake credential -> FAIL ---------------------------------
    New-Sandbox
    $fake = 'gh' + 'p_' + ('x' * 36)
    Set-Content -LiteralPath (Join-Path $sandbox 'leaky.txt') -Value ("api access: " + $fake) -Encoding UTF8
    $r5 = Invoke-Checker
    Assert-Case -Name 'fake credential is rejected' -Expected 1 -Actual $r5.Exit

    # --- Case 6: oversized file -> FAIL ----------------------------------
    New-Sandbox
    $big = New-Object byte[] (12 * 1024 * 1024)
    [System.IO.File]::WriteAllBytes((Join-Path $sandbox 'big.dat'), $big)
    $r6 = Invoke-Checker
    Assert-Case -Name 'oversized file is rejected' -Expected 1 -Actual $r6.Exit

    # --- Case 7: absolute machine path -> FAIL ---------------------------
    New-Sandbox
    $fakePath = 'C' + ':' + [char]92 + 'Users' + [char]92 + 'someone' + [char]92 + 'data.csv'
    Set-Content -LiteralPath (Join-Path $sandbox 'hardcoded.txt') -Value ("input: " + $fakePath) -Encoding UTF8
    $r7 = Invoke-Checker
    Assert-Case -Name 'absolute machine path is rejected' -Expected 1 -Actual $r7.Exit

    # --- Case 8: clean fixture -> PASS -----------------------------------
    New-Sandbox
    $r8 = Invoke-Checker
    Assert-Case -Name 'clean fixture is accepted' -Expected 0 -Actual $r8.Exit -Output $r8.Output
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

if ($results.Count -lt 9) {
    Write-Host ""
    Write-Host ("RESULT: FAIL (expected 9 assertions, ran " + $results.Count + ")")
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
