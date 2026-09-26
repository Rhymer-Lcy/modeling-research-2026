#Requires -Version 5.1
<#
.SYNOPSIS
    Build the manuscript with XeLaTeX.

.DESCRIPTION
    Callable from any current directory. All paths are resolved relative to this
    script's own location, never from the caller's working directory.

    The document class lives under paper/template/, which is git-ignored and is
    NOT on any default TeX search path. This wrapper therefore extends
    TEXINPUTS / BSTINPUTS / BIBINPUTS for the duration of the build only, and
    restores the previous values afterwards. No global TeX configuration is
    modified.

    XeLaTeX "Missing character" warnings are treated as build failures: a glyph
    missing from a font is dropped silently from the PDF, which can corrupt a
    formula or a numeric value while the build still reports success.

.PARAMETER Clean
    Remove the build directory before building.

.PARAMETER Submission
    Build a competition submission and refuse to report success unless every
    submission-only requirement holds:
      - the official 2026 cover logo row was drawn, from the four local-only
        assets under docs_local/gmcm-2026/cover-assets/, each matching its
        pinned SHA-256 (see paper/TEMPLATE_DECISION_2026.md);
      - real cover identity is supplied by the git-ignored paper/team.tex;
      - no undefined reference or citation remains;
      - the official Chinese faces SimSun and SimHei are embedded;
      - the PDF title and author properties are empty.
    Without this switch the same conditions are reported but do not fail the
    build, so a clean public clone still builds.
#>
[CmdletBinding()]
param(
    [switch]$Clean,
    [switch]$Submission
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$paperDir = Join-Path $repoRoot 'paper'
$tplDir   = Join-Path $paperDir 'template'
$buildDir = Join-Path $paperDir 'build'

if (-not (Test-Path -LiteralPath (Join-Path $tplDir 'gmcmthesis.cls'))) {
    Write-Error "Document class not found under paper/template/. Run scripts/setup_template.ps1 first."
}

# A submission build is always clean: latexmk does not treat a file tested
# with \IfFileExists as a dependency, so an incremental build can skip XeLaTeX
# and leave a stale log behind, and the checks below read that log.
if ($Submission) { $Clean = $true }

if ($Clean -and (Test-Path -LiteralPath $buildDir)) {
    Remove-Item -LiteralPath $buildDir -Recurse -Force
}
if (-not (Test-Path -LiteralPath $buildDir)) {
    New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
}

# kpathsea accepts forward slashes on Windows and uses ';' as the list
# separator. A trailing ';' appends the default search path.
$tplSearch   = ($tplDir   -replace '\\', '/')
$paperSearch = ($paperDir -replace '\\', '/')

$prevTexInputs = $env:TEXINPUTS
$prevBstInputs = $env:BSTINPUTS
$prevBibInputs = $env:BIBINPUTS

$exitCode = 1
Push-Location -LiteralPath $paperDir
try {
    $env:TEXINPUTS = "$tplSearch;$tplSearch//;"
    $env:BSTINPUTS = "$tplSearch;"
    $env:BIBINPUTS = "$paperSearch;"

    Write-Host "repo root : $repoRoot"
    Write-Host "building  : paper/main.tex -> paper/build/main.pdf"

    & latexmk -xelatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex
    $exitCode = $LASTEXITCODE
}
finally {
    Pop-Location
    $env:TEXINPUTS = $prevTexInputs
    $env:BSTINPUTS = $prevBstInputs
    $env:BIBINPUTS = $prevBibInputs
}

$logPath = Join-Path $buildDir 'main.log'
$pdfPath = Join-Path $buildDir 'main.pdf'

if ($exitCode -ne 0) {
    Write-Error "latexmk failed with exit code $exitCode. See paper/build/main.log"
}

if (-not (Test-Path -LiteralPath $pdfPath)) {
    Write-Error "Build reported success but paper/build/main.pdf does not exist."
}

if (Test-Path -LiteralPath $logPath) {
    $missing = Select-String -LiteralPath $logPath -Pattern 'Missing character' -SimpleMatch
    if ($missing) {
        Write-Host ""
        Write-Host "Missing character warnings (treated as build failures):"
        $missing | Select-Object -First 20 | ForEach-Object { Write-Host ("  " + $_.Line.Trim()) }
        Write-Error "Build FAILED: font is missing glyphs used by the manuscript."
    }
}

# Submission-readiness checks. Reported on every build; fatal only with
# -Submission. The asset hashes are the official 2026 cover images extracted
# from the organizer's Word template; the images themselves stay local-only.
$coverDir = Join-Path (Join-Path (Join-Path $repoRoot 'docs_local') 'gmcm-2026') 'cover-assets'
$coverAssets = [ordered]@{
    'cpipc.png'    = '213720f708b24199b06e59ba200aedba8e881b26295aec0e0476febe5b6bf8ad'
    'modeling.png' = '68a755cae523448c27547280fc5dda2072f8a6fbc33c25e39f5a8b77d0bffa75'
    'huawei.jpeg'  = 'c5361862213c4119b650712551d447274c78897236d7b02d8c6cf6806dbccd2e'
    'xjtu.png'     = '92aa4f6cc713266cdf3c733d724240e6af14bcb826fc3bfd5051439fffbd3fbe'
}
$problems = New-Object System.Collections.ArrayList

foreach ($name in $coverAssets.Keys) {
    $p = Join-Path $coverDir $name
    if (-not (Test-Path -LiteralPath $p)) {
        [void]$problems.Add("cover asset missing: docs_local/gmcm-2026/cover-assets/$name")
    }
    elseif ((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() -ne $coverAssets[$name]) {
        [void]$problems.Add("cover asset hash mismatch: $name")
    }
}
$log = ''
if (Test-Path -LiteralPath $logPath) { $log = Get-Content -LiteralPath $logPath -Raw -Encoding UTF8 }
if ($log -notmatch 'format2026: official 2026 cover logo row present') {
    [void]$problems.Add('the official 2026 cover logo row was not drawn')
}
if ($log -match 'There were undefined references|Reference `[^'']*'' on page \d+ undefined|Citation `[^'']*'' on page \d+ undefined') {
    [void]$problems.Add('undefined references or citations remain')
}
if (-not (Test-Path -LiteralPath (Join-Path $paperDir 'team.tex'))) {
    [void]$problems.Add('paper/team.tex is absent, so the cover carries placeholder identity')
}
$pdffonts = Get-Command pdffonts -ErrorAction SilentlyContinue
if ($null -eq $pdffonts) {
    [void]$problems.Add('pdffonts not found, so the embedded fonts could not be verified')
}
else {
    $fonts = (& pdffonts $pdfPath) -join "`n"
    foreach ($face in @('SimSun', 'SimHei')) {
        if ($fonts -notmatch [regex]::Escape($face)) { [void]$problems.Add("required font not embedded: $face") }
    }
}
$pdfinfo = Get-Command pdfinfo -ErrorAction SilentlyContinue
if ($null -ne $pdfinfo) {
    foreach ($line in (& pdfinfo $pdfPath)) {
        if ($line -match '^(Title|Author):\s*\S') { [void]$problems.Add("PDF metadata is not empty: $line") }
    }
}

Write-Host ""
if ($problems.Count -eq 0) {
    Write-Host "SUBMISSION CHECKS: all passed"
}
else {
    Write-Host "SUBMISSION CHECKS: not ready"
    foreach ($m in $problems) { Write-Host ("  - " + $m) }
    if ($Submission) {
        Write-Error "Submission build FAILED: resolve the items above."
    }
}

$pdfInfo = Get-Item -LiteralPath $pdfPath
Write-Host ""
Write-Host "BUILD OK"
Write-Host ("  pdf   : " + $pdfInfo.FullName)
Write-Host ("  size  : " + [math]::Round($pdfInfo.Length / 1KB, 1) + " KB")
exit 0
