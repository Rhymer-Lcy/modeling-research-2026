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
#>
[CmdletBinding()]
param(
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$paperDir = Join-Path $repoRoot 'paper'
$tplDir   = Join-Path $paperDir 'template'
$buildDir = Join-Path $paperDir 'build'

if (-not (Test-Path -LiteralPath (Join-Path $tplDir 'gmcmthesis.cls'))) {
    Write-Error "Document class not found under paper/template/. Run scripts/setup_template.ps1 first."
}

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

$pdfInfo = Get-Item -LiteralPath $pdfPath
Write-Host ""
Write-Host "BUILD OK"
Write-Host ("  pdf   : " + $pdfInfo.FullName)
Write-Host ("  size  : " + [math]::Round($pdfInfo.Length / 1KB, 1) + " KB")
exit 0
