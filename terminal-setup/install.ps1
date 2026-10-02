# =============================================================================
#  install.ps1  —  one-click terminal setup for Windows (NO admin required)
# -----------------------------------------------------------------------------
#  What it does:
#    1. Ensures your user PowerShell profile exists.
#    2. Copies profile.ps1's contents into it (inside a guarded block, so it is
#       safe to run repeatedly and never duplicates).
#    3. Sets the execution policy for the CURRENT USER only (no admin) so the
#       profile is allowed to run.
#    4. Creates the src\github.com\<user> project folder structure.
#
#  Usage (in PowerShell, from inside the terminal-setup folder):
#    ./install.ps1
# =============================================================================

$ErrorActionPreference = "Stop"

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceFile = Join-Path $ScriptDir "windows\profile.ps1"

$Marker    = "# >>> unified-shell >>>"
$MarkerEnd = "# <<< unified-shell <<<"

Write-Host "── Unified terminal setup (Windows) ─────────────────────"

if (-not (Test-Path $SourceFile)) {
    Write-Host "Error: cannot find $SourceFile" -ForegroundColor Red
    Write-Host "Run this script from inside the terminal-setup folder." -ForegroundColor Red
    exit 1
}

# --- 1. allow the profile to run (current user only, no admin) ---------------
try {
    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
    Write-Host "  [ok] Execution policy set to RemoteSigned (current user)" -ForegroundColor Green
} catch {
    Write-Host "  [!] Could not set execution policy automatically. If the profile" -ForegroundColor Yellow
    Write-Host "      does not load, run this once manually:" -ForegroundColor Yellow
    Write-Host "      Set-ExecutionPolicy -Scope CurrentUser RemoteSigned" -ForegroundColor Yellow
}

# --- 2. ensure the profile file exists ---------------------------------------
$profileDir = Split-Path -Parent $PROFILE
if (-not (Test-Path $profileDir)) { New-Item -ItemType Directory -Path $profileDir -Force | Out-Null }
if (-not (Test-Path $PROFILE))    { New-Item -ItemType File -Path $PROFILE -Force | Out-Null }

# --- 3. inject the config inside a guarded block (idempotent) ----------------
$current = Get-Content -Raw -Path $PROFILE -ErrorAction SilentlyContinue
if ($null -eq $current) { $current = "" }

if ($current.Contains($Marker)) {
    Write-Host "  [i] Config block already present in profile — leaving as is." -ForegroundColor Cyan
} else {
    # back up first
    if ($current.Trim().Length -gt 0) {
        $backup = "$PROFILE.backup.$(Get-Date -Format yyyyMMddHHmmss)"
        Copy-Item $PROFILE $backup
        Write-Host "  [ok] Backed up existing profile -> $backup" -ForegroundColor Green
    }
    $body = Get-Content -Raw -Path $SourceFile
    $block = "`r`n$Marker`r`n$body`r`n$MarkerEnd`r`n"
    Add-Content -Path $PROFILE -Value $block
    Write-Host "  [ok] Wrote config into $PROFILE" -ForegroundColor Green
}

# --- 4. create the project folder structure ----------------------------------
$GHUser  = "seeam"
$SrcRoot = Join-Path $HOME "src\github.com\$GHUser"
if (-not (Test-Path $SrcRoot)) { New-Item -ItemType Directory -Path $SrcRoot -Force | Out-Null }
Write-Host "  [ok] Project folder ready -> $SrcRoot" -ForegroundColor Green

Write-Host "─────────────────────────────────────────────────────────"
Write-Host ""
Write-Host "Done! Open a NEW PowerShell window (or run: . `$PROFILE) to see it." -ForegroundColor Cyan
Write-Host "Then try:  ll  |  ghp  |  cd into a git repo to see the branch" -ForegroundColor Cyan
Write-Host "For the full Ubuntu purple terminal look, see THEMES.md" -ForegroundColor Cyan
