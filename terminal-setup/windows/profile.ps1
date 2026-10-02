# =============================================================================
#  profile.ps1  —  Windows PowerShell config matching the macOS/Ubuntu look
# -----------------------------------------------------------------------------
#  Gives Windows the same feel as the Mac/Ubuntu machines:
#    * an Ubuntu-style prompt: green user@host : blue path (yellow git-branch) >
#    * the same aliases: ll, la, l, .., ...
#    * the same `ghp` jump-to-projects shortcut
#
#  NO ADMIN ACCESS REQUIRED. The PowerShell profile lives entirely under your
#  own user folder. The installer (install.ps1) copies this into place.
#
#  Works in Windows PowerShell 5.1 and PowerShell 7+ (pwsh).
# =============================================================================

# --- Configuration: set your GitHub username --------------------------------
$GHUser  = "seeam"
$SrcRoot = Join-Path $HOME "src\github.com\$GHUser"

# --- Aliases / functions -----------------------------------------------------
# PowerShell already has `ls` (Get-ChildItem) with color in PS7. We add the
# same short names you use everywhere else so muscle memory carries over.
function ll { Get-ChildItem -Force @args }          # detailed, incl. hidden
function la { Get-ChildItem -Force -Name @args }    # names incl. hidden
function l  { Get-ChildItem @args }                 # short list
function .. { Set-Location .. }                     # go up one level
function ... { Set-Location ../.. }                 # go up two levels

# A few git quality-of-life shortcuts
function gs { git status @args }
function gb { git branch @args }
function gl { git log --oneline --graph --decorate -20 @args }

# --- ghp : jump to your projects --------------------------------------------
function ghp {
    param([string]$Repo)
    if ($Repo) {
        $target = Join-Path $SrcRoot $Repo
        if (Test-Path $target) { Set-Location $target }
        else { Write-Host "ghp: no such project: $Repo (looked in $SrcRoot)" -ForegroundColor Red }
    } else {
        if (Test-Path $SrcRoot) { Set-Location $SrcRoot }
        else { Write-Host "ghp: $SrcRoot does not exist yet. Run install.ps1." -ForegroundColor Red }
    }
}

# --- The Ubuntu-style colored prompt (with live git branch) ------------------
function Get-GitBranch {
    $branch = git symbolic-ref --quiet --short HEAD 2>$null
    if (-not $branch) { $branch = git rev-parse --short HEAD 2>$null }
    if ($branch) { return " ($branch)" }
    return ""
}

function prompt {
    $user = $env:USERNAME
    $host_ = $env:COMPUTERNAME
    $path  = $PWD.Path.Replace($HOME, "~")
    $branch = Get-GitBranch

    Write-Host "$user@$host_" -NoNewline -ForegroundColor Green
    Write-Host ":"            -NoNewline
    Write-Host "$path"        -NoNewline -ForegroundColor Blue
    if ($branch) { Write-Host "$branch" -NoNewline -ForegroundColor Yellow }
    return "$ "
}
