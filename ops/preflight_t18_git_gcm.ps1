# C:\T18\ops\preflight_t18_git_gcm.ps1
# Preflight & Auto-Configure:
# (1) Git + Git Credential Manager (GCM)
# (2) Repo C:\T18 ↔ https://github.com/nkd3/t18 on branch main
# (3) Write-access test (temp branch push + delete)
# (4) No-console run via pythonw.exe + VBS + Scheduled Task (and direct run now)

param()

# ====== FILL THESE (edit below) ======
if (-not $T18_AuthorName)  { $T18_AuthorName  = "nkd" }   # e.g., "Neelkanth Dwibedi"
if (-not $T18_AuthorEmail) { $T18_AuthorEmail = "neelkanth.dwibedi@gmail.com" }  # e.g., "neelkanth.dwibedi@gmail.com"
if (-not $T18_Branch)      { $T18_Branch      = "main" }
if (-not $T18_RepoURL)     { $T18_RepoURL     = "https://github.com/nkd3/t18" }
if (-not $T18_Root)        { $T18_Root        = "C:\T18" }

$ErrorActionPreference = "Stop"

# ====== Paths ======
$VenvDir   = Join-Path $T18_Root ".venv"
$PyExe     = Join-Path $VenvDir "Scripts\python.exe"
$PyWExe    = Join-Path $VenvDir "Scripts\pythonw.exe"
$OpsDir    = Join-Path $T18_Root "ops"
$LogsDir   = Join-Path $T18_Root "logs"
$SilentPy  = Join-Path $OpsDir "silent_test.pyw"
$SilentVbs = Join-Path $T18_Root "start_silent_test.vbs"
$TaskName  = "T18 Silent Test"

# ====== Helpers ======
function Section($t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }
function Pass($m)    { Write-Host "PASS: $m"   -ForegroundColor Green }
function Warn($m)    { Write-Host "WARN: $m"   -ForegroundColor Yellow }
function Fail($m)    { Write-Host "FAIL: $m"   -ForegroundColor Red }
function Ensure-Dir($p) { if (!(Test-Path $p)) { New-Item -ItemType Directory -Path $p | Out-Null } }
function Run($cmd, $workdir=$T18_Root) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName  = "powershell.exe"
    $psi.Arguments = "-NoProfile -Command $cmd"
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    $psi.UseShellExecute = $false
    $psi.WorkingDirectory = $workdir
    $p = [System.Diagnostics.Process]::Start($psi)
    $out = $p.StandardOutput.ReadToEnd()
    $err = $p.StandardError.ReadToEnd()
    $p.WaitForExit()
    return @{ Code=$p.ExitCode; Out=$out; Err=$err }
}

# --------------------------------------------------------------------------------
Section "1) Git + Git Credential Manager (GCM) checks"

# 1.1 Git present?
try {
    $gitVer = (& git --version) 2>$null
    if (-not $gitVer) { throw "git not found" }
    Pass "Git found: $gitVer"
} catch {
    Warn "Git not found. Install with:"
    Write-Host '  winget install --id Git.Git -e'
    throw "Install Git, then re-run this script."
}

# 1.2 Enforce GCM credential helper
try {
    $helper = (& git config --global credential.helper) 2>$null
    if (-not $helper -or ($helper -notmatch "manager")) {
        & git config --global credential.helper manager
        Pass "Configured credential.helper=manager (GCM)."
    } else {
        Pass "credential.helper already set to 'manager'."
    }
} catch {
    Warn "Could not set credential.helper=manager globally. You can do it manually:"
    Write-Host '  git config --global credential.helper manager'
}

# 1.3 Best-effort GCM binary presence
$gcmCmd = (Get-Command git-credential-manager -ErrorAction SilentlyContinue)
if ($null -ne $gcmCmd) {
    Pass "git-credential-manager present: $($gcmCmd.Source)"
} else {
    Warn "git-credential-manager not found on PATH. If pushes prompt, re-install Git for Windows (includes GCM)."
}

# --------------------------------------------------------------------------------
Section "2) Repo at $T18_Root cloned from $T18_RepoURL and on branch ${T18_Branch}"

if (!(Test-Path $T18_Root)) {
    Warn "$T18_Root does not exist. Cloning now..."
    Ensure-Dir (Split-Path $T18_Root -Parent)
    $res = Run "git clone `"$T18_RepoURL`" `"$T18_Root`"" (Split-Path $T18_Root -Parent)
    if ($res.Code -ne 0) { Fail "Clone failed: $($res.Err)"; throw "Clone failed" }
    Pass "Cloned into $T18_Root"
}

Push-Location $T18_Root

# Confirm git repo
try {
    (& git rev-parse --is-inside-work-tree) | Out-Null
} catch {
    Fail "$T18_Root is not a git repo."
    throw "Invalid repo"
}

# Confirm/normalize remote (accept .git or no .git)
$origin = (& git remote get-url origin) 2>$null
if ($origin -ne $T18_RepoURL -and $origin -ne "$T18_RepoURL.git") {
    Warn "Origin URL mismatch.`nCurrent: $origin`nExpected: $T18_RepoURL"
    & git remote set-url origin $T18_RepoURL
    Pass "Updated origin to $T18_RepoURL"
} else {
    Pass "Origin remote OK."
}

# Fetch
& git fetch --all 2>$null | Out-Null

# Checkout target branch
$res = Run "git checkout ${T18_Branch}"
if ($res.Code -eq 0) {
    Pass "Checked out ${T18_Branch}"
} else {
    Warn "Branch ${T18_Branch} not found locally. Creating from origin/${T18_Branch}..."
    $res2 = Run "git checkout -b ${T18_Branch} origin/${T18_Branch}"
    if ($res2.Code -ne 0) {
        $errTxt = $res2.Err
        Fail ("Cannot create local ${T18_Branch}: {0}" -f $errTxt)
        throw "Branch error"
    }
    Pass "Created and checked out ${T18_Branch} from origin."
}

# Pull fast-forward; if diverged, rebase
$res = Run "git pull --ff-only origin ${T18_Branch}"
if ($res.Code -eq 0) {
    Pass "Pulled latest ${T18_Branch} (ff-only)"
} else {
    Warn "FF-only pull failed (diverged). Attempting rebase..."
    $res2 = Run "git pull --rebase origin ${T18_Branch}"
    if ($res2.Code -eq 0) {
        Pass "Pulled with rebase."
    } else {
        Warn ("Rebase pull failed: {0}" -f $res2.Err)
        Warn "Resolve divergence manually:"
        Write-Host "  cd $T18_Root"
        Write-Host "  git fetch --all"
        Write-Host "  git rebase origin/${T18_Branch}"
    }
}

# Repo-scoped identity
if ($T18_AuthorName -ne "<PLACEHOLDER_NAME>")  { & git config user.name  $T18_AuthorName  | Out-Null; Pass "Set repo user.name = $T18_AuthorName" }
if ($T18_AuthorEmail -ne "<PLACEHOLDER_EMAIL>"){ & git config user.email $T18_AuthorEmail | Out-Null; Pass "Set repo user.email = $T18_AuthorEmail" }

Pop-Location

# --------------------------------------------------------------------------------
Section "3) Write-access test (temp branch push + delete)"

$ts = (Get-Date -Format "yyyyMMddHHmmss")
$who = $env:USERNAME
$hostShort = $env:COMPUTERNAME
$tempBranch = "preflight/$who-$hostShort-$ts"

Push-Location $T18_Root
Run "git checkout -b $tempBranch"                       | Out-Null
Run "git commit --allow-empty -m `"preflight: write access check $ts`"" | Out-Null
$pushRes = Run "git push -u origin $tempBranch"
if ($pushRes.Code -eq 0) {
    Pass "Pushed temp branch to origin: $tempBranch"
    $delRes = Run "git push origin --delete $tempBranch"
    if ($delRes.Code -eq 0) { Pass "Deleted remote temp branch." } else { Warn "Could not delete remote branch (policy). Remove later if needed." }
} else {
    Fail "Push failed. Sign in via Git Credential Manager once and/or confirm repo permissions."
    Write-Host "TIP:"
    Write-Host "  cd $T18_Root"
    Write-Host "  git fetch --all"
    Write-Host "  git pull --rebase origin ${T18_Branch}"
    Write-Host "  git push origin ${T18_Branch}"
    throw "Write access not confirmed."
}
Run "git checkout ${T18_Branch}" | Out-Null
Run "git branch -D $tempBranch"  | Out-Null
Pop-Location

# --------------------------------------------------------------------------------
Section "4) No-console run (pythonw.exe + VBS + Scheduled Task) — direct run & schedule"

# Ensure venv and pythonw.exe
Ensure-Dir $VenvDir
if (!(Test-Path $PyExe)) {
    Write-Host "Creating venv at $VenvDir"
    & py -3.11 -m venv $VenvDir
}
& $PyExe -m pip install --upgrade pip | Out-Null

if (!(Test-Path $PyWExe)) {
    Fail "pythonw.exe not found at $PyWExe. Verify Python 3.11 venv created successfully."
    throw "pythonw.exe missing"
}

# Silent test file & logs folder
Ensure-Dir $OpsDir
Ensure-Dir $LogsDir

@"
# silent_test.pyw
import time
from pathlib import Path
log = Path(r"$LogsDir") / "silent_test.log"
log.parent.mkdir(parents=True, exist_ok=True)
with log.open("a", encoding="utf-8") as f:
    f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " - silent test ran via pythonw.exe\n")
"@ | Set-Content -Path $SilentPy -Encoding UTF8

# VBS launcher (hidden)
@"
' start_silent_test.vbs — run pythonw hidden (no console)
Dim WshShell, cmd
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "$T18_Root"
cmd = """$PyWExe"" ""$SilentPy"""
WshShell.Run cmd, 0, False
"@ | Set-Content -Path $SilentVbs -Encoding ASCII

# Direct one-shot run (hidden) to verify log immediately
Start-Process "wscript.exe" -ArgumentList "`"$SilentVbs`"" -WindowStyle Hidden

# Wait up to 5s for the log line to appear
$logPath = Join-Path $LogsDir "silent_test.log"
$ok = $false
for ($i=0; $i -lt 10; $i++) {
    Start-Sleep -Milliseconds 500
    if (Test-Path $logPath) {
        $last = Get-Content $logPath -ErrorAction SilentlyContinue | Select-Object -Last 1
        if ($last -and ($last -match "silent test ran")) { $ok = $true; break }
    }
}
if ($ok) {
    Pass "No-console run verified (direct). Last line: $last"
} else {
    Warn "No log found at $logPath after direct run. Check VBS, venv pythonw path, or file permissions."
}

# Register a scheduled task that runs at logon (hidden via wscript)
schtasks /Query /TN "$TaskName" 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { schtasks /Delete /TN "$TaskName" /F | Out-Null }

$Esc = $SilentVbs.Replace('\','\\')
schtasks /Create /TN "$TaskName" /TR "wscript.exe `"$Esc`"" /SC ONLOGON /RL HIGHEST /F | Out-Null
Pass "Scheduled task '$TaskName' created (runs hidden at logon)."

Write-Host "`nAll checks complete."
