<#
.SYNOPSIS
    Connect cronport to GitHub and push it. For Windows.

.DESCRIPTION
    This is the Windows version of scripts/first_publish.sh. It does the
    same thing, and it has one advantage: it uses your GitHub token to
    create the repository for you, so nothing has to be typed into a
    password prompt.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\first_publish.ps1

.NOTES
    Right-click on a .ps1 file and "Run with PowerShell" does not let you
    type a password, so run it from a terminal instead.
#>

$ErrorActionPreference = "Stop"

$GitHubUser = if ($env:GITHUB_USER) { $env:GITHUB_USER } else { "ZhuYijing316" }
$RepoName   = "cronport"
$Branch     = "main"

function Write-Step($message) {
    Write-Host ""
    Write-Host "==> $message" -ForegroundColor Cyan
}
function Write-Hint($message) {
    Write-Host "    $message" -ForegroundColor DarkGray
}
function Write-Fail($message) {
    Write-Host ""
    Write-Host $message -ForegroundColor Red
    exit 1
}

Set-Location (Join-Path $PSScriptRoot "..")

# ------------------------------------------------------------------ token

Write-Step "checking the GitHub token"

$token = $env:GITHUB_TOKEN
if (-not $token) {
    $secure = Read-Host "Paste your GitHub personal access token (ghp_...)" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $token = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if (-not $token -or $token.Length -lt 20) {
    Write-Fail "That does not look like a token. Create one at https://github.com/settings/tokens (tick the 'repo' box)."
}

Write-Hint "checking the token"
$headers = @{
    "Authorization" = "Bearer $token"
    "Accept"        = "application/vnd.github+json"
    "User-Agent"    = "cronport-first-publish"
}
try {
    $me = Invoke-RestMethod -Uri "https://api.github.com/user" -Headers $headers -Method Get
    Write-Hint "authenticated as $($me.login)"
} catch {
    Write-Fail "The token was rejected by GitHub: $($_.Exception.Message)"
}

# ------------------------------------------------------------------ repo

Write-Step "checking the repository on GitHub"

$repoUrl = "https://api.github.com/repos/$GitHubUser/$RepoName"
$exists = $false
try {
    Invoke-RestMethod -Uri $repoUrl -Headers $headers -Method Get | Out-Null
    $exists = $true
    Write-Hint "$GitHubUser/$RepoName already exists"
} catch {
    Write-Hint "$GitHubUser/$RepoName does not exist yet, creating it"
}

if (-not $exists) {
    $body = @{
        name        = $RepoName
        description = "One schedule, every runtime: explain, convert and lint cron expressions across 7 scheduler dialects."
        private     = $false
        has_issues  = $true
        has_wiki    = $true
        auto_init   = $false
    } | ConvertTo-Json
    try {
        Invoke-RestMethod -Uri $repoUrl -Headers $headers -Method Post -Body $body -ContentType "application/json" | Out-Null
        Write-Hint "created $GitHubUser/$RepoName (public)"
    } catch {
        Write-Fail "Could not create the repository: $($_.Exception.Message)"
    }
}

# ------------------------------------------------------------------ git

Write-Step "checking git"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Fail @"
git is not installed or not on the PATH.
Install it with:   winget install --id Git.Git -e --source winget
Then open a NEW terminal and run this script again.
"@
}
Write-Hint (git --version)

Write-Step "checking the git identity"
if (-not (git config user.name)) {
    git config user.name $GitHubUser
    git config user.email "$GitHubUser@users.noreply.github.com"
    Write-Hint "set the identity to $GitHubUser"
} else {
    Write-Hint "already set to $(git config user.name)"
}

Write-Step "checking the remote"
$remote = "https://github.com/$GitHubUser/$RepoName.git"
$current = (git remote get-url origin 2>$null)
if ($current -ne $remote) {
    if ($current) {
        git remote set-url origin $remote
        Write-Hint "updated origin -> $remote"
    } else {
        git remote add origin $remote
        Write-Hint "added origin -> $remote"
    }
} else {
    Write-Hint "origin is already $remote"
}

# ------------------------------------------------------------------ push

Write-Step "pushing to GitHub"
$basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("x-access-token:$token"))
git -c "http.extraheader=Authorization: Basic $basic" push -u origin $Branch
if ($LASTEXITCODE -ne 0) {
    Write-Fail @"
The push failed. Common reasons:
  * the token has no 'repo' permission -> create a new one and tick 'repo'
  * the token is expired -> create a new one
"@
}

Write-Host ""
Write-Host "==> pushed" -ForegroundColor Green

# ------------------------------------------------------------------ next

Write-Host ""
Write-Host "==> next"
Write-Host "  1. Open https://github.com/$GitHubUser/$RepoName"
Write-Host "     You should see your commits and the README with the demo animation."
Write-Host ""
Write-Host "  2. Publish to PyPI and create a GitHub release:"
Write-Host "       `$env:TWINE_USERNAME = '$GitHubUser'"
Write-Host "       `$env:TWINE_PASSWORD = 'pypi-...'"
Write-Host "       powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 0.1.0"
Write-Host ""
Write-Host "  3. Read LAUNCH.md and announce it."
Write-Host ""
