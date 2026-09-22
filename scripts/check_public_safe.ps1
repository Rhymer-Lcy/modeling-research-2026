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
        git ls-files --others --exclude-standard   untracked but not ignored

    Local-only areas (docs_local/, data_local/, scratch/, paper/team.tex,
    paper/template/, paper/build/) are ignored by Git and therefore never enter
    this set. Their contents are NOT scanned: they are private by design, and
    scanning them would produce guaranteed findings that train the reader to
    ignore the tool. They are instead checked from the other direction, by
    asserting that none of them is tracked.

    MODES
    PreCommit  Working tree and index. HEAD may legitimately not exist, so no
               history check runs. This is the mode for the first commit.
    PrePush    Requires HEAD, scans all reachable history and Git author and
               committer metadata, and repeats every working-tree check.

    SEVERITY
    Only high-confidence credential signatures fail the build. Generic
    assignments such as `token = "..."` are reported as warnings for manual
    review: a gate that cries wolf gets bypassed, and a bypassed gate is worse
    than no gate.

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
$identityFile = Join-Path (Join-Path $repoRoot 'docs_local') 'identity.local.txt'

$script:Failures = New-Object System.Collections.ArrayList
$script:Warnings = New-Object System.Collections.ArrayList
$script:Manual   = New-Object System.Collections.ArrayList
$script:FilesExamined = 0
$script:CommitsScanned = 0

function Add-Failure { param([string]$m) [void]$script:Failures.Add($m) }
function Add-Warning { param([string]$m) [void]$script:Warnings.Add($m) }
function Add-Manual  { param([string]$m) [void]$script:Manual.Add($m) }

# --------------------------------------------------------------------------
# Patterns
# --------------------------------------------------------------------------

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

# Absolute machine paths. These FAIL.
$AbsolutePathPatterns = @(
    @{ Name = 'windows-drive-path'; Pattern = '\b[A-Za-z]:[\\/]' },
    @{ Name = 'msys-user-path';     Pattern = '/[a-z]/Users/' },
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

function Get-NormalizedVariants {
    <# Returns a two-element array: whitespace-collapsed and whitespace-removed,
       both lowercased. A needle hard-wrapped by the text that contains it will
       not match the collapsed form, so both are compared. #>
    param([string]$Text)
    $collapsed = ($Text -replace '\s+', ' ').ToLowerInvariant()
    $stripped  = ($Text -replace '\s', '').ToLowerInvariant()
    return , @($collapsed, $stripped)
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

function Get-PublicCandidateSet {
    $tracked   = @(& git -C $repoRoot ls-files --cached)
    $untracked = @(& git -C $repoRoot ls-files --others --exclude-standard)
    $all = @($tracked) + @($untracked)
    $seen = @{}
    $out = New-Object System.Collections.ArrayList
    foreach ($p in $all) {
        if ([string]::IsNullOrWhiteSpace($p)) { continue }
        $norm = $p.Trim()
        if ($seen.ContainsKey($norm)) { continue }
        $seen[$norm] = $true
        [void]$out.Add($norm)
    }
    return $out
}

function Read-IdentityNeedles {
    if (-not (Test-Path -LiteralPath $identityFile)) {
        Add-Failure "Identity file docs_local/identity.local.txt is absent. The identity check cannot run, and a check that silently skips is worse than no check. Create it from the template in the repository documentation."
        return $null
    }
    $needles  = New-Object System.Collections.ArrayList
    $approved = New-Object System.Collections.ArrayList
    foreach ($line in (Get-Content -LiteralPath $identityFile -Encoding UTF8)) {
        $t = $line.Trim()
        if ($t -eq '' -or $t.StartsWith('#')) { continue }
        $idx = $t.IndexOf(':')
        if ($idx -lt 1) { continue }
        $cat = $t.Substring(0, $idx).Trim().ToLowerInvariant()
        $val = $t.Substring($idx + 1).Trim()
        if ($val -eq '') { continue }
        if ($cat -eq 'approved_email') {
            [void]$approved.Add($val.ToLowerInvariant())
        }
        else {
            $v = Get-NormalizedVariants $val
            [void]$needles.Add([pscustomobject]@{
                Category  = $cat
                Collapsed = $v[0]
                Stripped  = $v[1]
            })
        }
    }
    # Fingerprint the identity file so a run can be tied to a version of it
    # without ever revealing its contents.
    $fp = (Get-FileHash -LiteralPath $identityFile -Algorithm SHA256).Hash.Substring(0, 12)
    return [pscustomobject]@{ Needles = $needles; Approved = $approved; Fingerprint = $fp }
}

# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

function Invoke-TrackedIgnoredPathCheck {
    $tracked = @(& git -C $repoRoot ls-files --cached)
    foreach ($p in $tracked) {
        foreach ($bad in $MustNotBeTracked) {
            if ($bad.EndsWith('/')) {
                if ($p -like "$bad*") { Add-Failure "Local-only path is tracked: $p" }
            }
            elseif ($p -eq $bad) {
                Add-Failure "Local-only path is tracked: $p"
            }
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
    param($Identity)

    $candidates = Get-PublicCandidateSet
    foreach ($rel in $candidates) {

        # Defence in depth: the Git-derived set should never contain these.
        $skip = $false
        foreach ($bad in $MustNotBeTracked) {
            if ($bad.EndsWith('/')) { if ($rel -like "$bad*") { $skip = $true } }
            elseif ($rel -eq $bad) { $skip = $true }
        }
        if ($skip) { continue }

        $full = Join-Path $repoRoot ($rel -replace '/', '\')
        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { continue }

        $script:FilesExamined++
        $info = Get-Item -LiteralPath $full

        # Size
        if ($info.Length -gt $FailSizeBytes) {
            Add-Failure ("File exceeds " + ($FailSizeBytes / 1MB) + " MB: $rel (" + [math]::Round($info.Length / 1MB, 2) + " MB)")
        }
        elseif ($info.Length -gt $WarnSizeBytes) {
            Add-Warning ("Large file: $rel (" + [math]::Round($info.Length / 1MB, 2) + " MB)")
        }

        # Extension
        if ($ForbiddenExtensions -contains $info.Extension.ToLowerInvariant()) {
            Add-Failure "Forbidden file type tracked: $rel"
        }

        # Binary files cannot be scanned for text. Surface them for a human.
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
        foreach ($p in $AbsolutePathPatterns) {
            if ([regex]::IsMatch($content, $p.Pattern)) {
                Add-Failure ("Absolute machine path '" + $p.Name + "' in $rel")
            }
        }

        # Notebook outputs
        if ($info.Extension.ToLowerInvariant() -eq '.ipynb') {
            if ([regex]::IsMatch($content, '"outputs"\s*:\s*\[\s*\{')) {
                Add-Failure "Notebook has stored outputs: $rel"
            }
        }

        # Sensitive identifiers. Report category and path only, never the value.
        if ($Identity -ne $null) {
            $v = Get-NormalizedVariants $content
            foreach ($n in $Identity.Needles) {
                if ($v[0].Contains($n.Collapsed)) {
                    Add-Failure ("Sensitive identifier of category '" + $n.Category + "' appears in $rel")
                }
                elseif ($v[1].Contains($n.Stripped)) {
                    Add-Failure ("Sensitive identifier of category '" + $n.Category + "' appears in $rel (matched across a line break)")
                }
            }
        }
    }
}

function Invoke-HistoryChecks {
    param($Identity)

    & git -C $repoRoot rev-parse --verify HEAD 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Add-Failure "PrePush requires HEAD, but the repository has no commits."
        return
    }

    $countRaw = (& git -C $repoRoot rev-list --all --count)
    $script:CommitsScanned = [int]($countRaw | Select-Object -First 1)
    if ($script:CommitsScanned -le 0) {
        Add-Failure "PrePush found no reachable commits to scan."
        return
    }

    # Author and committer metadata.
    $addresses = @(& git -C $repoRoot log --all --format='%ae%n%ce') |
        ForEach-Object { $_.Trim().ToLowerInvariant() } |
        Where-Object { $_ -ne '' } |
        Sort-Object -Unique
    foreach ($a in $addresses) {
        if ($Identity -eq $null) { break }
        if (-not ($Identity.Approved -contains $a)) {
            Add-Failure "Git history contains a non-approved author or committer address (not shown). Add it to approved_email if it is intended."
        }
    }

    # History content.
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
    if ($Identity -ne $null) {
        $v = Get-NormalizedVariants $patch
        foreach ($n in $Identity.Needles) {
            if ($v[0].Contains($n.Collapsed) -or $v[1].Contains($n.Stripped)) {
                Add-Failure ("Sensitive identifier of category '" + $n.Category + "' appears in Git history")
            }
        }
    }
}

# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------

Write-Host "public-safety check  mode=$Mode"
Write-Host ""

$identity = Read-IdentityNeedles
if ($identity -ne $null) {
    Write-Host ("identity source fingerprint : " + $identity.Fingerprint)
    Write-Host ("identity needles loaded     : " + $identity.Needles.Count)
    Write-Host ("approved addresses loaded   : " + $identity.Approved.Count)
    Write-Host ""
}

Invoke-TrackedIgnoredPathCheck
Invoke-NestedRepoCheck
Invoke-FileChecks -Identity $identity

if ($Mode -eq 'PrePush') {
    Invoke-HistoryChecks -Identity $identity
}

# Coverage assertions. A run that examined nothing must never report success.
if ($script:FilesExamined -le 0) {
    Add-Failure "Coverage assertion failed: no files were examined."
}
if ($Mode -eq 'PrePush' -and $script:CommitsScanned -le 0) {
    Add-Failure "Coverage assertion failed: no commits were scanned."
}

Write-Host ("files examined   : " + $script:FilesExamined)
if ($Mode -eq 'PrePush') {
    Write-Host ("commits scanned  : " + $script:CommitsScanned)
}
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
