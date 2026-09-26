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
      9. oversized file under a NON-ASCII directory -> FAIL (exit 1)
     10. clean small file under a NON-ASCII path    -> PASS (exit 0)

    Historical email exceptions (configs/git-email-history-exceptions.txt):
     11. unapproved commit listed by exact SHA      -> PASS (exit 0)
     12. same address on a different commit         -> FAIL (exit 1)
     13. the entry removed, or the file absent      -> FAIL (exit 1)
     14. malformed entries (abbreviated SHA, wildcard, address, other
         keyword, short hex) beside a valid entry   -> FAIL (exit 1)
     15. well-formed SHA not in reachable history   -> FAIL (exit 1)
     16. duplicate entry                            -> FAIL (exit 1)
     17. entry for a commit needing no exception    -> FAIL (exit 1)
     18. approved suffix / exact / web-flow addresses with an exception
         file present                               -> PASS (exit 0)
     19. an excepted commit does not waive content: a credential in its
         history, or an absolute path in the tree   -> FAIL (exit 1)
     20. this repository's real history, cloned: passes with its exception
         file, and fails naming each listed commit without it
     21. temporary repository is removed

    Cases 11 to 19 use fixture addresses only. Case 20 reads the listed SHAs
    from the real exception file at run time, so this script names no real
    commit and no real address.

    Cases 9 and 10 exist because Git quotes non-ASCII paths, and a gate that
    cannot decode that quoting skips the file instead of scanning it. A skip
    reports success for a file that was never opened, so the defect is invisible
    from the exit code alone. Case 9 is therefore the discriminating test: the
    oversize finding can only be produced by a checker that actually resolved
    and measured the file through its non-ASCII path. Case 10 guards the other
    direction, that decoding did not turn a clean non-ASCII path into a false
    positive. Both assert on the checker's reported counters as well as on its
    exit code, so neither can be satisfied by a checker that silently skips.
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
    & git -C $sandbox add -A | Out-Null
    & git -C $sandbox -c "user.name=fixture" -c "user.email=$CommitterEmail" `
        commit -q -m "chore(fixture): add content [T-000]" --author="fixture <$AuthorEmail>" | Out-Null
    # The new commit's full SHA, for exception entries and output assertions.
    return ((& git -C $sandbox rev-parse HEAD) | Select-Object -First 1).Trim()
}

function Set-SandboxExceptions {
    # Writes the sandbox exception file. The file is committed by the next
    # New-SandboxCommit, or left untracked when the case needs no further commit;
    # the checker reads the working-tree file either way.
    param([string[]]$Lines)
    Set-Content -LiteralPath (Join-Path $sandbox 'configs\git-email-history-exceptions.txt') -Encoding UTF8 `
        -Value (@('# Fixture exception file for the checker self-test.') + $Lines)
}

function Remove-SandboxExceptions {
    $p = Join-Path $sandbox 'configs\git-email-history-exceptions.txt'
    if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force }
}

function Invoke-Checker {
    param([string]$Mode = 'PreCommit', [string]$Root = $sandbox)
    $out = & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root 'scripts\check_public_safe.ps1') -Mode $Mode
    return [pscustomobject]@{ Exit = $LASTEXITCODE; Output = ($out -join "`n") }
}

function Assert-Case {
    param(
        [string]$Name,
        [int]$Expected,
        [int]$Actual,
        [string]$Output = '',
        [string[]]$MustContain = @(),
        [string[]]$MustNotContain = @()
    )
    $ok = ($Expected -eq $Actual)
    $missing = @()
    $present = @()
    # Normalize whitespace on both sides: the checker wraps its lines, so a
    # needle of more than a few words would otherwise never match.
    $hay = ($Output -split '\s+') -join ' '
    foreach ($needle in $MustContain) {
        $ndl = ($needle -split '\s+') -join ' '
        if ($hay -notlike ('*' + $ndl + '*')) { $missing += $needle }
    }
    foreach ($needle in $MustNotContain) {
        $ndl = ($needle -split '\s+') -join ' '
        if ($hay -like ('*' + $ndl + '*')) { $present += $needle }
    }
    if ($missing.Count -gt 0 -or $present.Count -gt 0) { $ok = $false }

    $verdict = 'FAIL'
    if ($ok) { $verdict = 'ok' }
    Write-Host ("  [{0}] {1}  expected exit {2}, got {3}" -f $verdict, $Name, $Expected, $Actual)
    foreach ($m in $missing) { Write-Host ("      missing from output: " + $m) }
    foreach ($m in $present) { Write-Host ("      must not appear in output: " + $m) }
    if (-not $ok -and $Output -ne '') {
        Write-Host "      ---- checker output ----"
        Write-Host $Output
    }
    $script:results += [pscustomobject]@{ Name = $Name; Ok = $ok }
}

function New-NonAsciiDirName {
    # Built from code points so this script stays ASCII on disk and cannot be
    # corrupted by a host that rewrites the file in another encoding.
    return ([string][char]0x6570 + [char]0x636E)   # two CJK characters
}

try {
    Write-Host "checker mutation self-test"
    Write-Host ""

    # --- Case 1: approved suffix author and committer -> PASS ------------
    New-Sandbox
    [void](New-SandboxCommit -AuthorEmail $ApprovedSuffixAddr -CommitterEmail $ApprovedSuffixAddr)
    $r1 = Invoke-Checker -Mode PrePush
    Assert-Case -Name 'approved-suffix author and committer accepted' -Expected 0 -Actual $r1.Exit -Output $r1.Output

    # --- Case 2: GitHub web-flow server-side committer -> PASS -----------
    New-Sandbox
    [void](New-SandboxCommit -AuthorEmail $ApprovedSuffixAddr -CommitterEmail $WebFlowAddr)
    $r2 = Invoke-Checker -Mode PrePush
    Assert-Case -Name 'github web-flow committer accepted' -Expected 0 -Actual $r2.Exit -Output $r2.Output

    # --- Case 3: approved exact public address -> PASS -------------------
    New-Sandbox
    [void](New-SandboxCommit -AuthorEmail $ApprovedExactAddr -CommitterEmail $WebFlowAddr)
    $r3 = Invoke-Checker -Mode PrePush
    Assert-Case -Name 'approved exact public address accepted' -Expected 0 -Actual $r3.Exit -Output $r3.Output

    # --- Case 4: unapproved personal-style address -> FAIL ---------------
    New-Sandbox
    [void](New-SandboxCommit -AuthorEmail $UnapprovedAddr -CommitterEmail $ApprovedSuffixAddr)
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

    # --- Case 9: oversized file under a NON-ASCII directory -> FAIL ------
    # The discriminating test. A checker that cannot decode Git's quoting for
    # this path skips the file, never measures it, and exits 0. Asserting on
    # the size message as well as the exit code means the case can only pass
    # if the file was genuinely resolved and opened.
    New-Sandbox
    $cjkDir = Join-Path $sandbox (New-NonAsciiDirName)
    New-Item -ItemType Directory -Path $cjkDir -Force | Out-Null
    $big9 = New-Object byte[] (12 * 1024 * 1024)
    [System.IO.File]::WriteAllBytes((Join-Path $cjkDir 'big.dat'), $big9)
    $r9 = Invoke-Checker
    Assert-Case -Name 'oversized file under non-ascii path is rejected' `
                -Expected 1 -Actual $r9.Exit -Output $r9.Output `
                -MustContain @('File exceeds 10 MB', '0 uninterpretable')

    # --- Case 10: clean small file under a NON-ASCII path -> PASS --------
    # Guards the opposite direction: decoding must not manufacture a finding.
    # The counter assertions prove the path was examined rather than skipped.
    New-Sandbox
    $cjkDir2 = Join-Path $sandbox (New-NonAsciiDirName)
    New-Item -ItemType Directory -Path $cjkDir2 -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $cjkDir2 'notes.txt') -Value 'Clean non-ascii fixture.' -Encoding UTF8
    # The sandbox otherwise holds exactly three candidate files (README.md,
    # scripts/check_public_safe.ps1, configs/git-email-policy.txt). Requiring
    # four proves the non-ascii file was counted rather than skipped, which is
    # the whole point: a skipping checker also exits 0 here.
    $r10 = Invoke-Checker
    Assert-Case -Name 'clean non-ascii path is examined without false positive' `
                -Expected 0 -Actual $r10.Exit -Output $r10.Output `
                -MustContain @('files examined : 4', '0 uninterpretable')

    # --- Historical email exceptions ---------------------------------------
    # Common history for cases 11-17: one approved commit (A), then one commit
    # (B) authored by the unapproved fixture address.

    # --- Case 11: unapproved commit listed by exact SHA -> PASS -----------
    New-Sandbox
    $a11 = New-SandboxCommit -AuthorEmail $ApprovedSuffixAddr -CommitterEmail $ApprovedSuffixAddr
    $b11 = New-SandboxCommit -AuthorEmail $UnapprovedAddr -CommitterEmail $ApprovedSuffixAddr
    Set-SandboxExceptions @("exact-commit $b11")
    $r11 = Invoke-Checker -Mode PrePush
    Assert-Case -Name 'unapproved commit listed by exact sha is waived' `
                -Expected 0 -Actual $r11.Exit -Output $r11.Output `
                -MustContain @('history exceptions: 1 of 1 listed commit(s) waived') `
                -MustNotContain @('not permitted')

    # --- Case 12: same address on a different commit -> FAIL -------------
    # The exception for B stays in place; a later commit C by the same address
    # must still fail, and the failure must name C, not B.
    $c12 = New-SandboxCommit -AuthorEmail $UnapprovedAddr -CommitterEmail $ApprovedSuffixAddr
    $r12 = Invoke-Checker -Mode PrePush
    Assert-Case -Name 'same unapproved address on another commit is rejected' `
                -Expected 1 -Actual $r12.Exit -Output $r12.Output `
                -MustContain @('not permitted', ('1 commit(s), e.g. ' + $c12.Substring(0, 12)))

    # --- Case 13: exception removed, or file absent -> FAIL --------------
    New-Sandbox
    [void](New-SandboxCommit -AuthorEmail $ApprovedSuffixAddr -CommitterEmail $ApprovedSuffixAddr)
    $b13 = New-SandboxCommit -AuthorEmail $UnapprovedAddr -CommitterEmail $ApprovedSuffixAddr
    Set-SandboxExceptions @('# entry deliberately removed')
    $r13a = Invoke-Checker -Mode PrePush
    Assert-Case -Name 'removing the exception rejects the commit again' `
                -Expected 1 -Actual $r13a.Exit -Output $r13a.Output `
                -MustContain @('not permitted', $b13.Substring(0, 12))
    Remove-SandboxExceptions
    $r13b = Invoke-Checker -Mode PrePush
    Assert-Case -Name 'an absent exception file grants nothing' `
                -Expected 1 -Actual $r13b.Exit -Output $r13b.Output `
                -MustContain @('not permitted', 'history exceptions: 0 of 0')

    # --- Case 14: malformed entries beside a valid one -> FAIL -----------
    # The valid entry covers the history, so each failure can only come from
    # the malformed line itself.
    $malformed = @(
        @{ Name = 'abbreviated sha';  Line = ('exact-commit ' + $b13.Substring(0, 12)) },
        @{ Name = 'wildcard';         Line = 'exact-commit *' },
        @{ Name = 'address as value'; Line = ('exact-commit ' + $UnapprovedAddr) },
        @{ Name = 'other keyword';    Line = ('exact ' + $UnapprovedAddr) },
        @{ Name = '39 hex digits';    Line = ('exact-commit ' + $b13.Substring(0, 39)) }
    )
    foreach ($mf in $malformed) {
        Set-SandboxExceptions @("exact-commit $b13", $mf.Line)
        $r14 = Invoke-Checker -Mode PrePush
        Assert-Case -Name ('malformed exception entry is rejected: ' + $mf.Name) `
                    -Expected 1 -Actual $r14.Exit -Output $r14.Output `
                    -MustContain @('Malformed entry')
    }

    # --- Case 15: well-formed SHA absent from history -> FAIL ------------
    # It must neither authorize B (left unlisted) nor pass as a stale entry.
    Set-SandboxExceptions @('exact-commit ' + ('0123456789abcdef' * 3).Substring(0, 40))
    $r15 = Invoke-Checker -Mode PrePush
    Assert-Case -Name 'exception naming an unreachable commit authorizes nothing' `
                -Expected 1 -Actual $r15.Exit -Output $r15.Output `
                -MustContain @('not in reachable history', 'not permitted')

    # --- Case 16: duplicate entry -> FAIL --------------------------------
    Set-SandboxExceptions @("exact-commit $b13", "exact-commit $b13")
    $r16 = Invoke-Checker -Mode PrePush
    Assert-Case -Name 'duplicate exception entry is rejected' `
                -Expected 1 -Actual $r16.Exit -Output $r16.Output -MustContain @('Duplicate entry')

    # --- Case 17: entry for a commit needing no exception -> FAIL --------
    $a17 = ((& git -C $sandbox rev-parse HEAD~1) | Select-Object -First 1).Trim()
    Set-SandboxExceptions @("exact-commit $b13", "exact-commit $a17")
    $r17 = Invoke-Checker -Mode PrePush
    Assert-Case -Name 'exception for a commit needing none is rejected' `
                -Expected 1 -Actual $r17.Exit -Output $r17.Output `
                -MustContain @('needs no exception', $a17)

    # --- Case 18: approved addresses unaffected by an exception file -----
    New-Sandbox
    [void](New-SandboxCommit -AuthorEmail $ApprovedSuffixAddr -CommitterEmail $WebFlowAddr)
    [void](New-SandboxCommit -AuthorEmail $ApprovedExactAddr  -CommitterEmail $WebFlowAddr)
    $b18 = New-SandboxCommit -AuthorEmail $UnapprovedAddr -CommitterEmail $WebFlowAddr
    Set-SandboxExceptions @("exact-commit $b18")
    [void](New-SandboxCommit -AuthorEmail $ApprovedSuffixAddr -CommitterEmail $ApprovedSuffixAddr)
    $r18 = Invoke-Checker -Mode PrePush
    Assert-Case -Name 'approved suffix, exact and web-flow addresses still pass' `
                -Expected 0 -Actual $r18.Exit -Output $r18.Output `
                -MustContain @('addresses checked : 4 (1 by approved suffix, 2 by approved exact rule)',
                               'history exceptions: 1 of 1 listed commit(s) waived')

    # --- Case 19: an exception never waives content checks ---------------
    # (a) The excepted commit itself adds a fake credential, removed again by a
    # later approved commit, so only the history scan can see it.
    New-Sandbox
    [void](New-SandboxCommit -AuthorEmail $ApprovedSuffixAddr -CommitterEmail $ApprovedSuffixAddr)
    $fake19 = 'gh' + 'p_' + ('y' * 36)
    Set-Content -LiteralPath (Join-Path $sandbox 'leaky.txt') -Value ("api access: " + $fake19) -Encoding UTF8
    $b19 = New-SandboxCommit -AuthorEmail $UnapprovedAddr -CommitterEmail $ApprovedSuffixAddr
    Remove-Item -LiteralPath (Join-Path $sandbox 'leaky.txt') -Force
    Set-SandboxExceptions @("exact-commit $b19")
    [void](New-SandboxCommit -AuthorEmail $ApprovedSuffixAddr -CommitterEmail $ApprovedSuffixAddr)
    $r19a = Invoke-Checker -Mode PrePush
    Assert-Case -Name 'excepted commit still fails the history credential scan' `
                -Expected 1 -Actual $r19a.Exit -Output $r19a.Output `
                -MustContain @('found in Git history') -MustNotContain @('not permitted')
    # (b) A valid exception file does not waive the working-tree path check.
    $fakePath19 = 'C' + ':' + [char]92 + 'Users' + [char]92 + 'someone' + [char]92 + 'data.csv'
    Set-Content -LiteralPath (Join-Path $sandbox 'hardcoded.txt') -Value ("input: " + $fakePath19) -Encoding UTF8
    $r19b = Invoke-Checker -Mode PreCommit
    Assert-Case -Name 'exception file does not waive the absolute-path check' `
                -Expected 1 -Actual $r19b.Exit -Output $r19b.Output -MustContain @('Absolute machine path')

    # --- Case 20: this repository's real history, cloned -----------------
    # The clone is read-only with respect to the real project. The working
    # copies of the checker and both policy files are laid over it, so the
    # case tests the code under review against the history it must govern.
    if (Test-Path -LiteralPath $sandbox) { Remove-Item -LiteralPath $sandbox -Recurse -Force }
    New-Item -ItemType Directory -Path $sandbox -Force | Out-Null
    $clone = Join-Path $sandbox 'real'
    & git clone --quiet --no-hardlinks -- $repoRoot $clone
    Copy-Item -LiteralPath $checkerSrc -Destination (Join-Path $clone 'scripts\check_public_safe.ps1') -Force
    foreach ($cfg in @('git-email-policy.txt', 'git-email-history-exceptions.txt')) {
        $src = Join-Path $repoRoot ('configs\' + $cfg)
        if (Test-Path -LiteralPath $src) {
            Copy-Item -LiteralPath $src -Destination (Join-Path $clone ('configs\' + $cfg)) -Force
        }
    }
    $listed = @()
    $realExc = Join-Path $repoRoot 'configs\git-email-history-exceptions.txt'
    if (Test-Path -LiteralPath $realExc) {
        foreach ($l in (Get-Content -LiteralPath $realExc -Encoding UTF8)) {
            $m = [regex]::Match($l.Trim(), '^exact-commit\s+([0-9a-f]{40})$')
            if ($m.Success) { $listed += $m.Groups[1].Value }
        }
    }
    $okListed = ($listed.Count -ge 1)
    $v = 'FAIL'; if ($okListed) { $v = 'ok' }
    Write-Host ("  [{0}] real exception file lists {1} commit(s)" -f $v, $listed.Count)
    $results += [pscustomobject]@{ Name = 'real exception file lists a commit'; Ok = $okListed }

    $r20a = Invoke-Checker -Mode PrePush -Root $clone
    Assert-Case -Name 'real history passes with its exception file' `
                -Expected 0 -Actual $r20a.Exit -Output $r20a.Output `
                -MustContain @(('history exceptions: ' + $listed.Count + ' of ' + $listed.Count + ' listed commit(s) waived'))
    Set-Content -LiteralPath (Join-Path $clone 'configs\git-email-history-exceptions.txt') -Encoding UTF8 `
        -Value @('# every entry removed for the self-test')
    $r20b = Invoke-Checker -Mode PrePush -Root $clone
    $needles = @('not permitted') + @($listed | ForEach-Object { $_.Substring(0, 12) })
    Assert-Case -Name 'real history fails, naming each listed commit, without it' `
                -Expected 1 -Actual $r20b.Exit -Output $r20b.Output -MustContain $needles
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

$ExpectedAssertions = 29
if ($results.Count -ne $ExpectedAssertions) {
    Write-Host ""
    Write-Host ("RESULT: FAIL (expected " + $ExpectedAssertions + " assertions, ran " + $results.Count + ")")
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
