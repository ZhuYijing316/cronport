<#
.SYNOPSIS
    Publish a new release of cronport to PyPI and GitHub. For Windows.

.DESCRIPTION
    The Windows version of scripts/release.sh. It runs the tests, builds
    the distributions, uploads them to PyPI, tags the release and creates
    the GitHub release.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 0.1.0

.NOTES
    Needs TWINE_PASSWORD (a PyPI token) and GITHUB_TOKEN in the environment.
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"

$GitHubUser = if ($env:GITHUB_USER) { $env:GITHUB_USER } else { "ZhuYijing316" }
$RepoName   = "cronport"
$Branch     = "main"

function Write-Step($message) {
    Write-Host ""
    Write-Host "==> $message" -ForegroundColor Cyan
}
function Write-Fail($message) {
    Write-Host ""
    Write-Host $message -ForegroundColor Red
    exit 1
}

Set-Location (Join-Path $PSScriptRoot "..")

# ------------------------------------------------------------------ checks

Write-Step "checking that everything is in order"

$pyproject = Get-Content pyproject.toml -Raw
if ($pyproject -notmatch "version = `"$Version`"") {
    Write-Fail "pyproject.toml does not say version = `"$Version`" -- update it first"
}

$changelog = Get-Content CHANGELOG.md -Raw
if ($changelog -notmatch "## \[$Version\]") {
    Write-Fail "CHANGELOG.md has no section for $Version -- add one first"
}

$dirty = git status --porcelain
if ($dirty) {
    Write-Fail "There are uncommitted changes -- commit them first:`n$dirty"
}

git rev-parse "v$Version" 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Fail "The tag v$Version already exists"
}

if (-not $env:TWINE_PASSWORD) {
    Write-Fail "TWINE_PASSWORD is not set. See the comment at the top of this file."
}
if (-not $env:TWINE_USERNAME) {
    $env:TWINE_USERNAME = $GitHubUser
}

# ------------------------------------------------------------------ release

Write-Step "running the tests"
python -c "import pytest" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Fail @"
pytest is not installed. Install the development tools first:
    python -m pip install -e ".[dev]"
"@
}
python -m pytest -q
if ($LASTEXITCODE -ne 0) { Write-Fail "The tests failed" }

Write-Step "building the distributions"
if (Test-Path dist) { Remove-Item -Recurse -Force dist }
python -m build
if ($LASTEXITCODE -ne 0) { Write-Fail "The build failed" }

Write-Step "checking the distributions"
python -c "import twine" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Fail @"
twine is not installed. Install it first:
    python -m pip install build twine
"@
}
python -m twine check dist/*
if ($LASTEXITCODE -ne 0) { Write-Fail "twine check failed" }

Write-Step "uploading to PyPI"
python -m twine upload dist/*
if ($LASTEXITCODE -ne 0) { Write-Fail "The upload failed" }

Write-Step "tagging"
git tag -a "v$Version" -m "v$Version"
git push origin "v$Version"
if ($LASTEXITCODE -ne 0) { Write-Fail "Pushing the tag failed" }

# -------------------------------------------------------------- github

if ($env:GITHUB_TOKEN) {
    Write-Step "creating the GitHub release"

    $headers = @{
        "Authorization" = "Bearer $($env:GITHUB_TOKEN)"
        "Accept"        = "application/vnd.github+json"
        "User-Agent"    = "cronport-release"
    }

    $notes = "Release $Version"
    $pattern = '(?ms)^## \[{0}\].*?$(.*?)(?=^## \[|\z)' -f [regex]::Escape($Version)
    $match = [regex]::Match($changelog, $pattern)
    if ($match.Success) { $notes = $match.Groups[1].Value.Trim() }

    $body = @{
        tag_name = "v$Version"
        name     = "v$Version"
        body     = $notes
    } | ConvertTo-Json

    try {
        Invoke-RestMethod `
            -Uri "https://api.github.com/repos/$GitHubUser/$RepoName/releases" `
            -Headers $headers -Method Post -Body $body -ContentType "application/json" | Out-Null
        Write-Hint "created the release"
    } catch {
        Write-Fail "Creating the GitHub release failed: $($_.Exception.Message)"
    }
} else {
    Write-Host ""
    Write-Host "GITHUB_TOKEN is not set, so the GitHub release was skipped."
    Write-Host "Create it by hand: https://github.com/$GitHubUser/$RepoName/releases/new"
}

Write-Host ""
Write-Host "==> v$Version is out" -ForegroundColor Green
Write-Host "  PyPI:           https://pypi.org/project/cronport/$Version/"
Write-Host "  GitHub release: https://github.com/$GitHubUser/$RepoName/releases/tag/v$Version"
Write-Host ""
Write-Host "Announce it: see LAUNCH.md for the Hacker News, Reddit and"
Write-Host "Chinese community posts, ready to copy and paste."
Write-Host ""
