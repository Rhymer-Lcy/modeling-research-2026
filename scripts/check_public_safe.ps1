#Requires -Version 5.1
<#
.SYNOPSIS
    Public-repository safety gate.

.DESCRIPTION
    This repository is public. Content that reaches a commit is effectively
    permanent: deleting it later does not remove it from history, from forks, or
    from caches. This gate therefore runs before a commit and again before a
    push.

    PUBLIC-CANDIDATE SET
    The set of files examined is defined by Git, not by walking the filesystem:

        git ls-files --cached                      tracked and staged
        git diff --cached --name-only              staged against HEAD
        git ls-files --others --exclude-standard   untracked but not ignored

    Paths are normalized and deduplicated. Local-only areas are ignored by Git
    and therefore never enter this set; their contents are NOT scanned. They are
    checked from the other direction instead, by asserting that none of them is
    tracked.

    SCOPE
    This gate protects repository boundaries, secrets, machine-specific
    information and Git metadata. It deliberately does not maintain a database
    of personal identity data.

    EMAIL POLICY
    Every author and committer address in reachable history must be explicitly
    permitted by configs/git-email-policy.txt. The purpose is to stop an
    UNAPPROVED mailbox from being published by accident, not to forbid an
    address whose owner has deliberately chosen to publish it. Approving an
    address is a reviewable edit to that tracked file, so intentional
    publication leaves a trace while accidental publication stays blocked.

    SEVERITY
    Only high-confidence credential signatures fail. Generic assignments such as
    `token = "..."` are reported as warnings for manual review: a gate that
    cries wolf gets bypassed, and a bypassed gate is worse than no gate.

    ESCAPE HATCH
    A line that must legitimately describe a machine-path pattern rather than
    contain one may carry the marker

        check-public-safe: allow-path-pattern

    Exemptions are counted and reported, so they cannot be used silently.

.PARAMETER Mode
    PreCommit (default) or PrePush.
#>
[CmdletBinding()]
param(
    [ValidateSet('PreCommit', 'PrePush')]
    [string]$Mode = 'PreCommit'
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot

$script:Failures = New-Object System.Collections.ArrayList
$script:Warnings = New-Object System.Collections.ArrayList
$script:Manual   = New-Object System.Collections.ArrayList
$script:FilesExamined = 0
$script:CommitsScanned = 0
$script:PathExemptions = 0
$script:EmailsChecked = 0
$script:EmailsByExact = 0
$script:EmailsBySuffix = 0

function Add-Failure { param([string]$m) [void]$script:Failures.Add($m) }
function Add-Warning { param([string]$m) [void]$script:Warnings.Add($m) }
function Add-Manual  { param([string]$m) [void]$script:Manual.Add($m) }

# --------------------------------------------------------------------------
# Policy
# --------------------------------------------------------------------------

$EmailPolicyRelPath  = 'configs/git-email-policy.txt'
$PathExemptionMarker = 'check-public-safe: allow-path-pattern'

# High confidence: a match is a credential, not a variable name. These FAIL.
$HighConfidenceSecrets = @(
    @{ Name = 'github-token';      Pattern = 'gh[pousr]_[A-Za-z0-9]{36,}' },
    @{ Name = 'github-pat';        Pattern = 'github_pat_[A-Za-z0-9_]{50,}' },
    @{ Name = 'openai-key';        Pattern = 'sk-[A-Za-z0-9]{32,}' },
    @{ Name = 'aws-access-key';    Pattern = 'AKIA[0-9A-Z]{16}' },
    @{ Name = 'google-api-key';    Pattern = 'AIza[0-9A-Za-z_\-]{35}' },
    @{ Name = 'slack-token';       Pattern = 'xox[baprs]-[0-9A-Za-z\-]{10,}' },
    @{ Name = 'private-key-block'; Pattern = '-----BEGIN [A-Z ]*PRIVATE KEY-----' }
)

# Low confidence: a variable name with a quoted value. These WARN only.
$GenericSecretHints = @(
    @{ Name = 'generic-assignment'; Pattern = '(?i)\b(password|passwd|secret|api[_-]?key|token)\s*=\s*["''][^"'']{8,}["'']' }
)

# Absolute machine paths. These FAIL unless the line carries the marker.
$AbsolutePathPatterns = @(
    @{ Name = 'windows-drive-path'; Pattern = '\b[A-Za-z]:[\\/]' },
    @{ Name = 'user-home-path';     Pattern = '(?i)Users[\\/][A-Za-z0-9._-]+' },
    @{ Name = 'msys-drive-path';    Pattern = '/[a-z]/Users/' },
    @{ Name = 'wsl-mount-path';     Pattern = '/mnt/[a-z]/' }
)

$ForbiddenExtensions = @('.exe', '.dll', '.rar', '.7z', '.mp4', '.mexw32', '.mexw64')

# Paths that must never be tracked.
$MustNotBeTracked = @(
    'docs_local/', 'data_local/', 'scratch/',
    'paper/team.tex', 'paper/template/', 'paper/build/'
)

$WarnSizeBytes = 5MB
$FailSizeBytes = 10MB

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

function Test-HasHead {
    <# `git rev-parse --verify HEAD` writes to stderr when there are no commits,
       and Windows PowerShell turns native stderr into an error record, which
       under $ErrorActionPreference='Stop' terminates the script. `--quiet`
       suppresses the message and reports the result through the exit code
       instead, which is what we actually want. #>
    & git -C $repoRoot rev-parse --verify --quiet HEAD | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Read-EmailPolicy {
    <# Parses configs/git-email-policy.txt into exact and suffix rules.
       Returns $null when the file is missing, which callers must treat as a
       failure: a policy gate that silently passes when its policy is absent is
       worse than no gate. #>
    $path = Join-Path $repoRoot ($EmailPolicyRelPath -replace '/', '\')
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $null }

    $exact   = New-Object System.Collections.ArrayList
    $suffix  = New-Object System.Collections.ArrayList
    foreach ($line in (Get-Content -LiteralPath $path -Encoding UTF8)) {
        $t = $line.Trim()
        if ($t -eq '' -or $t.StartsWith('#')) { continue }
        $parts = $t -split '\s+', 2
        if ($parts.Count -lt 2) { continue }
        $kind  = $parts[0].Trim().ToLowerInvariant()
        $value = $parts[1].Trim().ToLowerInvariant()
        if ($value -eq '') { continue }
        if     ($kind -eq 'exact')  { [void]$exact.Add($value) }
        elseif ($kind -eq 'suffix') { [void]$suffix.Add($value) }
    }
    return [pscustomobject]@{ Exact = $exact; Suffix = $suffix }
}

function Get-EmailVerdict {
    <# Returns 'exact', 'suffix' or 'unapproved'. #>
    param([string]$Address, $Policy)
    $a = $Address.Trim().ToLowerInvariant()
    if ($Policy.Exact -contains $a) { return 'exact' }
    foreach ($s in $Policy.Suffix) {
        if ($a.EndsWith($s)) { return 'suffix' }
    }
    return 'unapproved'
}

function Test-IsBinary {
    param([string]$Path)
    try {
        $fs = [System.IO.File]::OpenRead($Path)
        try {
            $len = [Math]::Min(8000, $fs.Length)
            if ($len -eq 0) { return $false }
            $buf = New-Object byte[] $len
            [void]$fs.Read($buf, 0, $len)
            foreach ($b in $buf) { if ($b -eq 0) { return $true } }
            return $false
        }
        finally { $fs.Dispose() }
    }
    catch { return $true }
}

function Test-IsLocalOnlyPath {
    param([string]$RelPath)
    foreach ($bad in $MustNotBeTracked) {
        if ($bad.EndsWith('/')) { if ($RelPath -like "$bad*") { return $true } }
        elseif ($RelPath -eq $bad) { return $true }
    }
    return $false
}

function Get-PublicCandidateSet {
    $parts = New-Object System.Collections.ArrayList

    foreach ($p in @(& git -C $repoRoot ls-files --cached)) { [void]$parts.Add($p) }

    if (Test-HasHead) {
        foreach ($p in @(& git -C $repoRoot diff --cached --name-only)) { [void]$parts.Add($p) }
    }

    foreach ($p in @(& git -C $repoRoot ls-files --others --exclude-standard)) { [void]$parts.Add($p) }

    $seen = @{}
    $out = New-Object System.Collections.ArrayList
    foreach ($p in $parts) {
        if ([string]::IsNullOrWhiteSpace($p)) { continue }
        $norm = ($p.Trim() -replace '\\', '/')
        if ($seen.ContainsKey($norm)) { continue }
        $seen[$norm] = $true
        [void]$out.Add($norm)
    }
    return $out
}

function Test-AbsolutePathViolation {
    <# Checks line by line so that an exemption marker applies only to its own
       line, never to a whole file. #>
    param([string]$Content, [string]$RelPath)
    $lines = $Content -split "`r?`n"
    foreach ($line in $lines) {
        $exempt = $line.Contains($PathExemptionMarker)
        foreach ($p in $AbsolutePathPatterns) {
            if ([regex]::IsMatch($line, $p.Pattern)) {
                if ($exempt) {
                    # Count only exemptions that actually suppressed a finding,
                    # so the reported number means "findings waived" rather than
                    # "marker seen". Otherwise the line that defines the marker
                    # inflates the count and the number stops meaning anything.
                    $script:PathExemptions++
                    break
                }
                Add-Failure ("Absolute machine path '" + $p.Name + "' in $RelPath")
                return
            }
        }
    }
}

# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

function Invoke-TrackedIgnoredPathCheck {
    foreach ($p in @(& git -C $repoRoot ls-files --cached)) {
        $norm = ($p.Trim() -replace '\\', '/')
        if ($norm -eq '') { continue }
        if (Test-IsLocalOnlyPath $norm) {
            Add-Failure "Local-only path is tracked: $norm"
        }
    }
}

function Invoke-NestedRepoCheck {
    $nested = Get-ChildItem -LiteralPath $repoRoot -Recurse -Force -Directory -Filter '.git' -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -ne (Join-Path $repoRoot '.git') }
    foreach ($n in $nested) {
        Add-Failure ("Nested git repository: " + $n.FullName.Substring($repoRoot.Length + 1))
    }
}

function Invoke-FileChecks {
    foreach ($rel in (Get-PublicCandidateSet)) {

        # Defence in depth: the Git-derived set should never contain these.
        if (Test-IsLocalOnlyPath $rel) { continue }

        $full = Join-Path $repoRoot ($rel -replace '/', '\')
        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { continue }

        $script:FilesExamined++
        $info = Get-Item -LiteralPath $full

        if ($info.Length -gt $FailSizeBytes) {
            Add-Failure ("File exceeds " + ($FailSizeBytes / 1MB) + " MB: $rel (" + [math]::Round($info.Length / 1MB, 2) + " MB)")
        }
        elseif ($info.Length -gt $WarnSizeBytes) {
            Add-Warning ("Large file: $rel (" + [math]::Round($info.Length / 1MB, 2) + " MB)")
        }

        if ($ForbiddenExtensions -contains $info.Extension.ToLowerInvariant()) {
            Add-Failure "Forbidden file type tracked: $rel"
        }

        if (Test-IsBinary $full) {
            Add-Manual "$rel"
            continue
        }

        $content = [System.IO.File]::ReadAllText($full, [System.Text.Encoding]::UTF8)

        foreach ($p in $HighConfidenceSecrets) {
            if ([regex]::IsMatch($content, $p.Pattern)) {
                Add-Failure ("Credential signature '" + $p.Name + "' in $rel")
            }
        }
        foreach ($p in $GenericSecretHints) {
            if ([regex]::IsMatch($content, $p.Pattern)) {
                Add-Warning ("Possible secret assignment in $rel - review manually")
            }
        }

        Test-AbsolutePathViolation -Content $content -RelPath $rel

        if ($info.Extension.ToLowerInvariant() -eq '.ipynb') {
            if ([regex]::IsMatch($content, '"outputs"\s*:\s*\[\s*\{')) {
                Add-Failure "Notebook has stored outputs: $rel"
            }
        }
    }
}

function Invoke-HistoryChecks {
    if (-not (Test-HasHead)) {
        Add-Failure "PrePush requires HEAD, but the repository has no commits."
        return
    }

    $countRaw = (& git -C $repoRoot rev-list --all --count)
    $script:CommitsScanned = [int]($countRaw | Select-Object -First 1)
    if ($script:CommitsScanned -le 0) {
        Add-Failure "PrePush found no reachable commits to scan."
        return
    }

    # Author and committer metadata, checked against the tracked email policy.
    $policy = Read-EmailPolicy
    if ($null -eq $policy) {
        Add-Failure "Email policy $EmailPolicyRelPath is missing, so author and committer addresses cannot be validated."
        return
    }
    if (($policy.Exact.Count + $policy.Suffix.Count) -le 0) {
        Add-Failure "Email policy $EmailPolicyRelPath contains no rules, so every address would be rejected or nothing would be checked."
        return
    }

    $addresses = @(& git -C $repoRoot log --all --format='%ae%n%ce') |
        ForEach-Object { $_.Trim().ToLowerInvariant() } |
        Where-Object { $_ -ne '' } |
        Sort-Object -Unique

    $byExact = 0
    $bySuffix = 0
    foreach ($a in $addresses) {
        $verdict = Get-EmailVerdict -Address $a -Policy $policy
        if     ($verdict -eq 'exact')  { $byExact++ }
        elseif ($verdict -eq 'suffix') { $bySuffix++ }
        else {
            # Reporting the address is the point of this failure: it names an
            # accidental public-history disclosure so it can be dealt with.
            Add-Failure ("Git history contains an address not permitted by $EmailPolicyRelPath" + ": " + $a)
        }
    }
    $script:EmailsChecked  = $addresses.Count
    $script:EmailsByExact  = $byExact
    $script:EmailsBySuffix = $bySuffix

    $patch = (& git -C $repoRoot log --all -p) -join "`n"
    foreach ($p in $HighConfidenceSecrets) {
        if ([regex]::IsMatch($patch, $p.Pattern)) {
            Add-Failure ("Credential signature '" + $p.Name + "' found in Git history")
        }
    }
    foreach ($p in $AbsolutePathPatterns) {
        if ([regex]::IsMatch($patch, $p.Pattern)) {
            Add-Failure ("Absolute machine path '" + $p.Name + "' found in Git history")
        }
    }
}

# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------

Write-Host "public-safety check  mode=$Mode"
Write-Host ""

Invoke-TrackedIgnoredPathCheck
Invoke-NestedRepoCheck
Invoke-FileChecks

if ($Mode -eq 'PrePush') {
    Invoke-HistoryChecks
}

# Coverage assertions. A run that examined nothing must never report success.
if ($script:FilesExamined -le 0) {
    Add-Failure "Coverage assertion failed: no candidate files were examined."
}
if ($Mode -eq 'PrePush' -and $script:CommitsScanned -le 0) {
    Add-Failure "Coverage assertion failed: no commits were scanned."
}

Write-Host ("files examined    : " + $script:FilesExamined)
if ($Mode -eq 'PrePush') {
    Write-Host ("commits scanned   : " + $script:CommitsScanned)
    # Counts only. A passing run has no reason to print anyone's address.
    Write-Host ("addresses checked : " + $script:EmailsChecked +
                " (" + $script:EmailsBySuffix + " by approved suffix, " +
                $script:EmailsByExact + " by approved exact rule)")
}
Write-Host ("path exemptions   : " + $script:PathExemptions)
Write-Host ""

if ($script:Manual.Count -gt 0) {
    Write-Host "MANUAL REVIEW - tracked binary assets cannot be text-scanned:"
    foreach ($m in $script:Manual) { Write-Host "  $m" }
    Write-Host ""
}

if ($script:Warnings.Count -gt 0) {
    Write-Host "WARNINGS:"
    foreach ($w in $script:Warnings) { Write-Host "  $w" }
    Write-Host ""
}

if ($script:Failures.Count -gt 0) {
    Write-Host "FAILURES:"
    foreach ($f in $script:Failures) { Write-Host "  $f" }
    Write-Host ""
    Write-Host ("RESULT: FAIL (" + $script:Failures.Count + " failure(s))")
    exit 1
}

Write-Host "RESULT: PASS"
exit 0
