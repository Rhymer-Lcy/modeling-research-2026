#Requires -Version 5.1
<#
.SYNOPSIS
    Provision the LaTeX document class into paper/template/.

.DESCRIPTION
    paper/template/ is git-ignored because the redistribution terms of the
    upstream class are unresolved, so every working copy provisions it locally.

    Sources are tried in order:
      1. -LocalArchive <path>  : a local zip already holding the class files.
      2. Pinned upstream revision (network).

    The upstream fallback fetches an explicit pinned commit. It never fetches a
    moving branch tip, so the provisioned files cannot change underneath the
    project without an explicit edit to $PinnedRevision below.

    After provisioning, SHA-256 digests are printed so a working copy can be
    compared against the digests recorded in docs_local/LOCAL_NOTES.md.

.PARAMETER LocalArchive
    Path to a local zip archive containing gmcmthesis.cls, gmcm.bst and figures/.

.PARAMETER Force
    Overwrite an existing paper/template/ directory.
#>
[CmdletBinding()]
param(
    [string]$LocalArchive,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

# Pinned upstream revision. Do not replace this with a branch name.
$UpstreamRepo    = 'andy123t/GMCMthesis'
$PinnedRevision  = '2becf0c3d32dd0449d1695f373733b4ff1ce5d88'
$RequiredFiles   = @('gmcmthesis.cls', 'gmcm.bst')

$repoRoot = Split-Path -Parent $PSScriptRoot
$tplDir   = Join-Path (Join-Path $repoRoot 'paper') 'template'

$alreadyPresent = $true
foreach ($f in $RequiredFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $tplDir $f))) { $alreadyPresent = $false }
}
if ($alreadyPresent -and -not $Force) {
    Write-Host "Template already provisioned. Use -Force to overwrite."
    foreach ($f in $RequiredFiles) {
        $h = Get-FileHash -LiteralPath (Join-Path $tplDir $f) -Algorithm SHA256
        Write-Host ("  " + $f + "  " + $h.Hash)
    }
    exit 0
}

if (-not (Test-Path -LiteralPath $tplDir)) {
    New-Item -ItemType Directory -Path $tplDir -Force | Out-Null
}

function Expand-TemplateZip {
    param([string]$ZipPath, [string]$Destination)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        $wanted = $archive.Entries | Where-Object {
            ($RequiredFiles -contains $_.FullName) -or ($_.FullName -like 'figures/*')
        }
        foreach ($entry in $wanted) {
            if ([string]::IsNullOrEmpty($entry.Name)) { continue }
            $out = Join-Path $Destination ($entry.FullName -replace '/', '\')
            $dir = Split-Path -Parent $out
            if (-not (Test-Path -LiteralPath $dir)) {
                New-Item -ItemType Directory -Path $dir -Force | Out-Null
            }
            [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $out, $true)
        }
    }
    finally {
        $archive.Dispose()
    }
}

if ($LocalArchive) {
    if (-not (Test-Path -LiteralPath $LocalArchive)) {
        Write-Error "Local archive not found: $LocalArchive"
    }
    Write-Host "Provisioning from local archive."
    Expand-TemplateZip -ZipPath $LocalArchive -Destination $tplDir
}
else {
    Write-Host "Provisioning from pinned upstream revision $PinnedRevision"
    $zipUrl = "https://codeload.github.com/$UpstreamRepo/zip/$PinnedRevision"
    $tmpZip = Join-Path ([System.IO.Path]::GetTempPath()) ("template-" + $PinnedRevision.Substring(0, 12) + ".zip")
    $tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("template-" + $PinnedRevision.Substring(0, 12))
    try {
        Invoke-WebRequest -Uri $zipUrl -OutFile $tmpZip -UseBasicParsing
        if (Test-Path -LiteralPath $tmpDir) { Remove-Item -LiteralPath $tmpDir -Recurse -Force }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::ExtractToDirectory($tmpZip, $tmpDir)
        $inner = Get-ChildItem -LiteralPath $tmpDir -Directory | Select-Object -First 1
        Copy-Item -Path (Join-Path $inner.FullName '*') -Destination $tplDir -Recurse -Force
    }
    finally {
        if (Test-Path -LiteralPath $tmpZip) { Remove-Item -LiteralPath $tmpZip -Force }
        if (Test-Path -LiteralPath $tmpDir) { Remove-Item -LiteralPath $tmpDir -Recurse -Force }
    }
}

$missing = @()
foreach ($f in $RequiredFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $tplDir $f))) { $missing += $f }
}
if ($missing.Count -gt 0) {
    Write-Error ("Provisioning incomplete, missing: " + ($missing -join ', '))
}

Write-Host ""
Write-Host "Template provisioned. SHA-256:"
foreach ($f in $RequiredFiles) {
    $h = Get-FileHash -LiteralPath (Join-Path $tplDir $f) -Algorithm SHA256
    Write-Host ("  " + $f + "  " + $h.Hash)
}
exit 0
