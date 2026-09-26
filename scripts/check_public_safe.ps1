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

    NON-ASCII PATHS
    Git quotes a path containing non-ASCII bytes, wrapping it in double quotes
    and octal-escaping each byte. Passing that literal string to the filesystem
    fails, because the embedded quote is not a legal path character. A gate that
    merely skips such a path reports success for a file it never opened, so a
    non-ASCII name would silently bypass the size and secret checks.

    Two defences are combined. Git is invoked with core.quotePath=false so that
    paths arrive verbatim, and the console encoding is pinned to UTF-8 for the
    duration so that those bytes decode correctly rather than becoming mojibake
    under whatever code page the host happens to use. Git still quotes a path
    containing a quote, a backslash or a control character even in that mode, so
    any residual quoting is decoded explicitly by ConvertFrom-GitQuotedPath.

    A path that still cannot be interpreted after both defences is a FAILURE,
    never a skip: this gate fails closed.

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

    HISTORICAL EXCEPTIONS
    Two different things can let an address through, and they must not be
    confused:

        approved address      an address deliberately allowed in public
                              history, for existing and future commits
                              (configs/git-email-policy.txt)

        historical exception  ONE already-public commit whose metadata carries
                              an unapproved address that can no longer be
                              withdrawn without rewriting shared history
                              (configs/git-email-history-exceptions.txt)

    An exception is keyed by the full commit SHA, never by address, and it has
    no wildcard form. It lets that exact commit pass and approves nothing: the
    same address on any other commit still fails. It exists only for
    irreversible, already-published metadata incidents. An entry that is
    malformed or duplicated, that names a commit absent from reachable history,
    or that names a commit needing no exception is itself a failure, so the
    list cannot drift into a silent allowance. A missing exception file means
    zero exceptions.

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
$script:HistoryExceptionsUsed = 0
$script:HistoryExceptionsListed = 0
$script:PathsDecoded = 0
$script:PathsUninterpretable = 0

function Add-Failure { param([string]$m) [void]$script:Failures.Add($m) }
function Add-Warning { param([string]$m) [void]$script:Warnings.Add($m) }
function Add-Manual  { param([string]$m) [void]$script:Manual.Add($m) }

# --------------------------------------------------------------------------
# Policy
# --------------------------------------------------------------------------

$EmailPolicyRelPath    = 'configs/git-email-policy.txt'
$EmailExceptionRelPath = 'configs/git-email-history-exceptions.txt'
$PathExemptionMarker   = 'check-public-safe: allow-path-pattern'

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

function ConvertFrom-GitQuotedPath {
    <# Decodes Git's C-style path quoting: the path is wrapped in double quotes
       and each non-printable or non-ASCII byte appears as a three-digit octal
       escape. The escaped bytes form a UTF-8 sequence, so they are collected as
       bytes and decoded once at the end rather than character by character.

       An unrecognised or truncated escape throws. The caller turns that into a
       failure, because a path this function cannot decode is a path the gate
       cannot scan. #>
    param([string]$Raw)

    if ($null -eq $Raw) { return '' }
    if ($Raw.Length -lt 2) { return $Raw }
    if (-not ($Raw.StartsWith('"') -and $Raw.EndsWith('"'))) { return $Raw }

    $backslash = [char]92
    $simple = @{ 'a' = 7; 'b' = 8; 'f' = 12; 'n' = 10; 'r' = 13; 't' = 9; 'v' = 11 }

    $body  = $Raw.Substring(1, $Raw.Length - 2)
    $bytes = New-Object System.Collections.Generic.List[byte]
    $i = 0

    while ($i -lt $body.Length) {
        $c = $body[$i]

        if ($c -ne $backslash) {
            foreach ($b in [System.Text.Encoding]::UTF8.GetBytes([string]$c)) { $bytes.Add($b) }
            $i++
            continue
        }

        if ($i + 1 -ge $body.Length) { throw 'Truncated escape in Git-quoted path.' }
        $n = $body[$i + 1]

        if ($n -ge '0' -and $n -le '7') {
            if ($i + 3 -ge $body.Length) { throw 'Truncated octal escape in Git-quoted path.' }
            $oct = $body.Substring($i + 1, 3)
            $bytes.Add([byte][Convert]::ToInt32($oct, 8))
            $i += 4
        }
        elseif ($simple.ContainsKey([string]$n)) {
            $bytes.Add([byte]$simple[[string]$n])
            $i += 2
        }
        elseif ($n -eq '"' -or $n -eq $backslash) {
            $bytes.Add([byte][int][char]$n)
            $i += 2
        }
        else {
            throw ('Unrecognised escape in Git-quoted path near offset ' + $i + '.')
        }
    }

    $script:PathsDecoded++
    return [System.Text.Encoding]::UTF8.GetString($bytes.ToArray())
}

function Invoke-GitLines {
    <# Runs git in the repository and returns stdout as lines, with paths
       readable rather than octal-escaped.

       Preferred mode pins the console to UTF-8 and asks Git for verbatim paths
       (core.quotePath=false). If the console encoding cannot be pinned, that
       mode would decode Git's UTF-8 bytes under the host code page and produce
       mojibake silently, so the fallback keeps Git's default quoting instead:
       that form is pure ASCII and therefore encoding-independent, and
       ConvertFrom-GitQuotedPath turns it back into the real path.

       Residual quoting is possible in both modes, because Git quotes a path
       containing a quote, a backslash or a control character even when
       quotePath is false. The caller decodes unconditionally.

       Arguments are passed as one explicit array rather than as remaining
       arguments. PowerShell binds a bare `-p` to the common parameter
       -PipelineVariable by prefix match, which swallowed the argument and made
       the PrePush history scan fail to run at all. #>
    param([Parameter(Mandatory = $true)][string[]]$GitArgs)

    $previous = $null
    $pinned = $false
    try {
        $previous = [Console]::OutputEncoding
        [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
        $pinned = $true
    }
    catch {
        $pinned = $false
    }

    try {
        if ($pinned) {
            $out = & git -C $repoRoot -c core.quotePath=false @GitArgs
        }
        else {
            $out = & git -C $repoRoot @GitArgs
        }
    }
    finally {
        if ($pinned -and $null -ne $previous) {
            try { [Console]::OutputEncoding = $previous } catch { }
        }
    }

    if ($null -eq $out) { return @() }
    return @($out)
}

function Resolve-CandidateFullPath {
    <# Turns a repository-relative candidate path into a full filesystem path.
       Throws when the path cannot be represented on this filesystem, which the
       caller reports as a failure rather than skipping. #>
    param([string]$RelPath)

    if ([string]::IsNullOrWhiteSpace($RelPath)) { throw 'Empty candidate path.' }
    if ($RelPath.Contains('"')) { throw 'Candidate path still carries Git quoting after decoding.' }

    foreach ($ch in [System.IO.Path]::GetInvalidPathChars()) {
        if ($RelPath.IndexOf($ch) -ge 0) {
            throw ('Candidate path contains a character that is not legal in a path (U+' +
                   ('{0:X4}' -f [int]$ch) + ').')
        }
    }

    return (Join-Path $repoRoot ($RelPath -replace '/', [string][char]92))
}

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

function Read-EmailHistoryExceptions {
    <# Parses configs/git-email-history-exceptions.txt into a set of full
       commit SHAs. Returns a hashtable keyed by lower-case SHA.

       Every non-comment line must be exactly `exact-commit <40 hex>`. Anything
       else - an abbreviated SHA, a wildcard, an address, another keyword - is
       reported as a failure rather than skipped, and so is a duplicate. A
       missing file yields an empty set: absence never broadens permission. #>
    $set  = @{}
    $path = Join-Path $repoRoot ($EmailExceptionRelPath -replace '/', '\')
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $set }

    $n = 0
    foreach ($line in (Get-Content -LiteralPath $path -Encoding UTF8)) {
        $n++
        $t = $line.Trim()
        if ($t -eq '' -or $t.StartsWith('#')) { continue }
        $m = [regex]::Match($t, '^exact-commit\s+([0-9A-Fa-f]{40})$')
        if (-not $m.Success) {
            Add-Failure ("Malformed entry in $EmailExceptionRelPath line $n" +
                         ": only 'exact-commit <full 40-character SHA>' is accepted.")
            continue
        }
        $sha = $m.Groups[1].Value.ToLowerInvariant()
        if ($set.ContainsKey($sha)) {
            Add-Failure ("Duplicate entry in $EmailExceptionRelPath line $n" + ": " + $sha)
            continue
        }
        $set[$sha] = $n
    }
    $script:HistoryExceptionsListed = $set.Count
    return $set
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

    foreach ($p in (Invoke-GitLines @('ls-files','--cached'))) { [void]$parts.Add($p) }

    if (Test-HasHead) {
        foreach ($p in (Invoke-GitLines @('diff','--cached','--name-only'))) { [void]$parts.Add($p) }
    }

    foreach ($p in (Invoke-GitLines @('ls-files','--others','--exclude-standard'))) { [void]$parts.Add($p) }

    $seen = @{}
    $out = New-Object System.Collections.ArrayList
    foreach ($p in $parts) {
        if ([string]::IsNullOrWhiteSpace($p)) { continue }

        # Decode before normalizing: an octal-escaped path still looks like an
        # ordinary string, so normalizing first would carry the escapes through.
        try {
            $decoded = ConvertFrom-GitQuotedPath $p.Trim()
        }
        catch {
            # Fail closed. A path that cannot be decoded is a path that cannot
            # be scanned, and silently dropping it is how a non-ASCII name would
            # bypass every content check.
            $script:PathsUninterpretable++
            Add-Failure ("Undecodable Git path, cannot be scanned: " + $p.Trim() +
                         " - " + $_.Exception.Message)
            continue
        }

        $norm = ($decoded -replace [regex]::Escape([string][char]92), '/')
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
    foreach ($p in (Invoke-GitLines @('ls-files','--cached'))) {
        if ([string]::IsNullOrWhiteSpace($p)) { continue }
        try {
            $decoded = ConvertFrom-GitQuotedPath $p.Trim()
        }
        catch {
            $script:PathsUninterpretable++
            Add-Failure ("Undecodable tracked Git path: " + $p.Trim() + " - " + $_.Exception.Message)
            continue
        }
        $norm = ($decoded -replace [regex]::Escape([string][char]92), '/')
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

        # Fail closed on a path this gate cannot interpret. The only skip
        # allowed here is the legitimate one: a candidate that Git lists but
        # that is genuinely absent from the working tree, such as a staged
        # deletion. Anything else - a path the filesystem rejects, or one that
        # raises while being tested - is reported, because a file that was
        # never opened must not be counted as a file that passed.
        try {
            $full = Resolve-CandidateFullPath $rel
        }
        catch {
            $script:PathsUninterpretable++
            Add-Failure ("Uninterpretable public-candidate path: $rel - " + $_.Exception.Message)
            continue
        }

        try {
            $exists = Test-Path -LiteralPath $full -PathType Leaf
        }
        catch {
            $script:PathsUninterpretable++
            Add-Failure ("Public-candidate path could not be tested: $rel - " + $_.Exception.Message)
            continue
        }

        if (-not $exists) { continue }

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

    # Historical exceptions are keyed by commit, so the scan works on
    # (commit, author, committer) triples rather than on unique addresses.
    $exceptions = Read-EmailHistoryExceptions

    $verdicts  = @{}   # address -> 'exact' | 'suffix' | 'unapproved'
    $offending = @{}   # unapproved address -> commits that are NOT excepted
    $used      = @{}   # excepted SHA -> $true once it actually waived something
    $reachable = @{}   # every reachable commit SHA

    foreach ($row in (Invoke-GitLines @('log','--all','--format=%H%x09%ae%x09%ce'))) {
        if ([string]::IsNullOrWhiteSpace($row)) { continue }
        $f = $row.Split("`t")
        if ($f.Count -ne 3) {
            Add-Failure ("Unparseable commit metadata line in history scan: " + $row)
            continue
        }
        $sha = $f[0].Trim().ToLowerInvariant()
        $reachable[$sha] = $true
        foreach ($raw in @($f[1], $f[2])) {
            $a = $raw.Trim().ToLowerInvariant()
            if ($a -eq '') { continue }
            if (-not $verdicts.ContainsKey($a)) {
                $verdicts[$a] = Get-EmailVerdict -Address $a -Policy $policy
            }
            if ($verdicts[$a] -ne 'unapproved') { continue }

            if ($exceptions.ContainsKey($sha)) {
                # Waived for this exact commit only; the address stays
                # unapproved everywhere else.
                $used[$sha] = $true
                continue
            }
            if (-not $offending.ContainsKey($a)) {
                $offending[$a] = New-Object System.Collections.ArrayList
            }
            if (-not $offending[$a].Contains($sha)) { [void]$offending[$a].Add($sha) }
        }
    }

    foreach ($a in ($offending.Keys | Sort-Object)) {
        # Reporting the address is the point of this failure: it names an
        # accidental public-history disclosure so it can be dealt with.
        $shas = $offending[$a]
        Add-Failure ("Git history contains an address not permitted by $EmailPolicyRelPath" + ": " + $a +
                     " (" + $shas.Count + " commit(s), e.g. " + $shas[0].Substring(0, 12) + ")")
    }

    foreach ($sha in ($exceptions.Keys | Sort-Object)) {
        if (-not $reachable.ContainsKey($sha)) {
            Add-Failure ("Entry in $EmailExceptionRelPath names a commit not in reachable history: " + $sha)
        }
        elseif (-not $used.ContainsKey($sha)) {
            Add-Failure ("Entry in $EmailExceptionRelPath names a commit that needs no exception: " + $sha)
        }
    }

    if ($reachable.Count -ne $script:CommitsScanned) {
        Add-Failure ("Email scan covered " + $reachable.Count + " commits but " +
                     $script:CommitsScanned + " are reachable.")
    }

    $script:EmailsChecked  = $verdicts.Count
    $script:EmailsByExact  = @($verdicts.Values | Where-Object { $_ -eq 'exact' }).Count
    $script:EmailsBySuffix = @($verdicts.Values | Where-Object { $_ -eq 'suffix' }).Count
    $script:HistoryExceptionsUsed = $used.Count

    $patch = (Invoke-GitLines @('log','--all','-p')) -join "`n"
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
else {
    # PreCommit validates the exception file's format so a malformed entry is
    # caught before it is committed; reachability is checked at PrePush.
    [void](Read-EmailHistoryExceptions)
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
    # Counts only; an exception never prints the address it waives.
    Write-Host ("history exceptions: " + $script:HistoryExceptionsUsed + " of " +
                $script:HistoryExceptionsListed + " listed commit(s) waived")
}
else {
    Write-Host ("history exceptions: " + $script:HistoryExceptionsListed + " listed (format only)")
}
Write-Host ("path exemptions   : " + $script:PathExemptions)
Write-Host ("quoted paths      : " + $script:PathsDecoded + " decoded, " +
            $script:PathsUninterpretable + " uninterpretable")
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
