<# =====================================================================
 T18 Auto Watch & Sync (Windows) — v11
 - Polls C:\T18 for changes and syncs to GitHub.
 - Debounce/batch commits, safe auto-rebase-pull, push.
 - Adds extra ignore patterns to .git/info/exclude.
 - Rotates log weekly (or if too big).
 Tested on Windows PowerShell 5.1 (no PS7-only operators used).
===================================================================== #>

$ErrorActionPreference = "Stop"

# --- SETTINGS ---------------------------------------------------------
$RepoPath            = "C:\T18"
$Branch              = "main"

# Poll interval (ms) for checking git state and file changes
$PollMs              = 5000

# Batch commit "quiet window" in seconds (wait for edits to settle)
$BatchQuietSeconds   = 15

# Extra ignore patterns beyond .gitignore (written to .git/info/exclude)
$ExtraIgnores        = @(
  "*.log",
  "*.tmp",
  "~$*",
  "*.swp",
  "*.swx"
)

# Log location (per-user so it survives permissions, etc.)
$LogRoot             = Join-Path $env:LOCALAPPDATA "T18\logs"
$LogFile             = Join-Path $LogRoot "sync.log"

# Log rotation policy
$RotateIfOlderDays   = 7          # rotate if last write > N days
$RotateIfLargerMB    = 5          # …or size > N MB

# Path to git (auto-detect)
$Git                 = "$env:ProgramFiles\Git\cmd\git.exe"
if (-not (Test-Path $Git)) { $Git = "git" }

# Named instance guard (so only 1 watcher runs)
$MutexName           = "Global\T18WatchSync_v11"

# --- INFRA ------------------------------------------------------------
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
function Log([string]$msg) {
  $stamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
  "$stamp  $msg" | Out-File -FilePath $LogFile -Append -Encoding utf8
}
function LogGit([string]$line) { Log ("git> " + $line) }

function Rotate-LogIfNeeded {
  try {
    if (-not (Test-Path $LogFile)) { return }
    $fi = Get-Item $LogFile
    $ageDays = (New-TimeSpan -Start $fi.LastWriteTime -End (Get-Date)).TotalDays
    $sizeMB  = [math]::Round(($fi.Length / 1MB),2)
    if ($ageDays -gt $RotateIfOlderDays -or $sizeMB -gt $RotateIfLargerMB) {
      $stamp = (Get-Date).ToString("yyyyMMdd-HHmmss")
      $arch  = Join-Path $LogRoot ("sync-" + $stamp + ".log")
      Copy-Item $LogFile $arch -Force
      "" | Out-File -FilePath $LogFile -Encoding utf8
      Log "Log rotated -> $([System.IO.Path]::GetFileName($arch)) (age=${ageDays}d, size=${sizeMB}MB)"
    }
  } catch {
    # Best-effort; never crash the watcher on rotate
  }
}

function Ensure-RepoReady {
  if (-not (Test-Path $RepoPath)) { throw "Repo path not found: $RepoPath" }
  Set-Location $RepoPath
  try {
    $cur = (& $Git rev-parse --abbrev-ref HEAD 2>$null).Trim()
    if ($cur -ne $Branch) {
      Log "Switching to $Branch (was $cur)"
      & $Git checkout -B $Branch | ForEach-Object { LogGit $_ }
    }
  } catch {
    Log "WARN: Could not determine branch: $($_.Exception.Message)"
  }
}

function Ensure-ExtraIgnores {
  try {
    $infoDir = Join-Path $RepoPath ".git\info"
    New-Item -ItemType Directory -Force -Path $infoDir | Out-Null
    $exclude = Join-Path $infoDir "exclude"
    if (-not (Test-Path $exclude)) { "" | Out-File -FilePath $exclude -Encoding utf8 }
    $existing = Get-Content $exclude -ErrorAction SilentlyContinue
    foreach ($p in $ExtraIgnores) {
      if (-not ($existing -contains $p)) {
        $p | Out-File -FilePath $exclude -Append -Encoding utf8
        Log "Added to .git/info/exclude: $p"
      }
    }
  } catch {
    Log "WARN: Could not update .git/info/exclude: $($_.Exception.Message)"
  }
}

# Wrapper to run git and capture text output + exit code
function RunGit {
  param([string[]]$argv)
  if ($null -eq $argv -or $argv.Count -eq 0) {
    Log "WARN: RunGit called with no args"
    return @{ code = 1; out = @("RunGit: no args") }
  }
  try {
    $out = & $Git @argv 2>&1
    $lines = @()
    if ($out -is [array]) { $lines = $out } elseif ($out -ne $null) { $lines = @("$out") }
    foreach ($l in $lines) { LogGit $l }
    $exit = $LASTEXITCODE
    if ($exit -eq $null) { $exit = 0 }
    return @{ code = [int]$exit; out = $lines }
  } catch {
    Log "SYNC-ERROR: $($_.Exception.Message)"
    return @{ code = 1; out = @("EXCEPTION: $($_.Exception.Message)") }
  }
}

function Get-Divergence {
  # fetch, then left-right count: remoteAhead (left) / localAhead (right)
  [void](RunGit @("fetch","origin",$Branch))
  $res = RunGit @("rev-list","--left-right","--count","origin/$Branch...HEAD")
  if ($res.code -ne 0 -or $res.out.Count -eq 0) { return @{ ra=0; la=0 } }
  $parts = ($res.out[-1] -split '\s+')
  $ra = 0; $la = 0
  if ($parts.Length -ge 2) {
    [void][int]::TryParse($parts[0], [ref]$ra)
    [void][int]::TryParse($parts[1], [ref]$la)
  }
  Log ("Divergence: remoteAhead=$ra, localAhead=$la")
  return @{ ra=$ra; la=$la }
}

function WorkingTreeClean {
  $st = RunGit @("status","--porcelain","-uall")
  return ($st.code -eq 0 -and ($st.out -eq $null -or $st.out.Count -eq 0))
}

# Try safe auto-pull (only when remote is ahead and you aren't)
function Try-AutoPull {
  param([int]$remoteAhead, [int]$localAhead)
  if ($remoteAhead -gt 0 -and $localAhead -eq 0) {
    # If dirty, autostash will save/restore local edits around rebase
    $pull = RunGit @("pull","--rebase","--autostash","origin",$Branch)
    if ($pull.code -ne 0) {
      # Clean up any aborted attempt
      [void](RunGit @("rebase","--abort"))
      Log "WARN: Auto-pull failed. Leaving repo unchanged."
      return $false
    }
    return $true
  }
  return $false
}

# --- MAIN -------------------------------------------------------------
# Single-instance guard
$created = $false
try {
  $mutex = New-Object System.Threading.Mutex($false, $MutexName, [ref]$created)
  if (-not $created) { Log "Another v11 instance is running. Exiting."; return }
} catch {
  Log "WARN: Could not create/open mutex ($MutexName): $($_.Exception.Message)"
}

Ensure-RepoReady
Ensure-ExtraIgnores
Rotate-LogIfNeeded

Log ("Watcher v11 (polling+batch) started | repo=$RepoPath | branch=$Branch | poll=${PollMs}ms | git=$Git")
# Print git version once
[void](RunGit @("version"))

# Batch state
$lastStableSnapshot  = ""
$lastChangeAt        = [datetime]::MinValue

while ($true) {
  try {
    Rotate-LogIfNeeded

    Set-Location $RepoPath

    # 1) Detect pending changes
    $st = RunGit @("status","--porcelain","-uall")
    $snapshot = ($st.out -join "`n")

    if ($st.code -eq 0 -and ($st.out -ne $null -and $st.out.Count -gt 0)) {
      # Changes exist
      if ($snapshot -ne $lastStableSnapshot) {
        $lastStableSnapshot = $snapshot
        $lastChangeAt = Get-Date
      }

      $since = 0
      if ($lastChangeAt -ne [datetime]::MinValue) {
        $since = (New-TimeSpan -Start $lastChangeAt -End (Get-Date)).TotalSeconds
      }

      if ($since -ge $BatchQuietSeconds) {
        # 2) Commit (batch window quiet)
        # Clear any stale rebase
        [void](RunGit @("rebase","--abort"))

        [void](RunGit @("add","-A"))
        $msg = "auto-sync: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
        $cm = RunGit @("commit","-m",$msg)

        if ($cm.code -eq 0) {
          Log ("Committed: " + $msg)

          # 3) Pull if remote ahead (safe) then push if we're ahead
          $div = Get-Divergence
          [void](Try-AutoPull -remoteAhead $div.ra -localAhead $div.la)

          $div2 = Get-Divergence
          if ($div2.la -gt 0 -and $div2.ra -eq 0) {
            $ps = RunGit @("push","origin",$Branch)
            if ($ps.code -eq 0) {
              Log ("Pushed OK: " + $msg)
            } else {
              Log "PUSH-ERROR (see lines above)."
            }
          }

          # Reset batch state after successful commit cycle
          $lastStableSnapshot = ""
          $lastChangeAt       = [datetime]::MinValue
        } else {
          # Probably nothing to commit (e.g., chmod only), keep watching
        }

      } else {
        # still within quiet window; do nothing this tick
      }

    } else {
      # No local changes – consider remote updates and push-if-needed
      $div = Get-Divergence

      # Safe auto-pull if we're clean and only remote is ahead
      if (WorkingTreeClean) {
        [void](Try-AutoPull -remoteAhead $div.ra -localAhead $div.la)
      }

      # If for some reason we have unpushed commits but remote not ahead, push
      $div2 = Get-Divergence
      if ($div2.la -gt 0 -and $div2.ra -eq 0) {
        $ps = RunGit @("push","origin",$Branch)
        if ($ps.code -eq 0) {
          Log ("Pushed OK: existing local commits")
        } else {
          Log "PUSH-ERROR (see lines above)."
        }
      }

      # Reset batch state; nothing pending
      $lastStableSnapshot = ""
      $lastChangeAt       = [datetime]::MinValue
    }

  } catch {
    Log "SYNC-ERROR: $($_.Exception.Message)"
    # keep loop alive
  }

  Start-Sleep -Milliseconds $PollMs
}
