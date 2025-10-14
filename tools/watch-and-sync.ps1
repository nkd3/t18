<#
T18 Auto Watch & Sync – v7.2 (PS5, POLLING, absolute git, conflict-averse)
- Polls every 5s; commits local changes, fetches, ff-only or pushes.
- No auto-rebase; if diverged, logs + backs off briefly.
- Logs OUTSIDE repo: %LOCALAPPDATA%\T18\logs\sync.log
- Single-instance via mutex.
#>

$ErrorActionPreference = "Stop"

# --- settings ---
$RepoPath    = "C:\T18"
$Branch      = "main"
$PollMs      = 5000
$BackoffSec  = 120

# --- git path (absolute) ---
$Git = (Get-Command git.exe -ErrorAction Stop).Source  # e.g. C:\Program Files\Git\cmd\git.exe

# --- logs outside repo ---
$LogDir      = Join-Path $env:LOCALAPPDATA "T18\logs"
$LogFile     = Join-Path $LogDir "sync.log"
$BackoffFile = Join-Path $LogDir "rebase_backoff.txt"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Log([string]$msg) {
  $stamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
  "$stamp  $msg" | Out-File -FilePath $LogFile -Append -Encoding utf8
}

# --- single instance ---
$mutexName = "Global\T18WatchSyncV72"
$created = $false
$mutex = New-Object System.Threading.Mutex($false, $mutexName, [ref]$created)
if (-not $mutex.WaitOne(0, $false)) {
  Log "Another v7.2 instance already running. Exiting."
  exit 0
}

# --- helpers ---
function In-Backoff {
  if (-not (Test-Path $BackoffFile)) { return $false }
  $txt = Get-Content $BackoffFile -ErrorAction SilentlyContinue
  if (-not $txt) { return $false }
  $t = [datetime]::Parse($txt)
  return ((Get-Date) -lt $t)
}
function Start-Backoff {
  $until = (Get-Date).AddSeconds($BackoffSec)
  $until.ToString("o") | Out-File -FilePath $BackoffFile -Encoding utf8 -Force
  Log "Entering backoff until $($until.ToString('HH:mm:ss'))."
}
function Clear-Backoff {
  if (Test-Path $BackoffFile) { Remove-Item $BackoffFile -Force -ErrorAction SilentlyContinue }
}

# IMPORTANT: don’t use param name `$args` in PS5 (collides with automatic var)
function RunGit {
  param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$argv
  )
  if (-not $argv -or $argv.Count -eq 0) { return 1 }
  $out = & $Git @argv 2>&1
  if ($out) { $out | ForEach-Object { Log "git> $_" } }
  return $LASTEXITCODE
}

function Get-Divergence {
  RunGit fetch origin $Branch | Out-Null
  $out = & $Git rev-list --left-right --count "origin/$Branch...HEAD" 2>$null
  if (-not $out) { return @{ RemoteAhead = 0; LocalAhead = 0 } }
  $parts = $out -split "\s+"
  return @{ RemoteAhead = [int]$parts[0]; LocalAhead = [int]$parts[1] }
}

# --- repo/branch ---
if (-not (Test-Path $RepoPath)) { throw "Repo path not found: $RepoPath" }
Set-Location $RepoPath
try {
  $cur = (& $Git rev-parse --abbrev-ref HEAD).Trim()
  if ($cur -ne $Branch) { Log "Switching to $Branch (was $cur)"; RunGit checkout -B $Branch | Out-Null }
} catch { Log "WARN: Cannot read current branch: $($_.Exception.Message)" }

Log "Watcher v7.2 (polling) started | repo=$RepoPath | branch=$Branch | poll=${PollMs}ms | git=$Git"
RunGit --version | Out-Null

# --- loop ---
while ($true) {
  try {
    if (In-Backoff) {
      Log "Backoff active; skipping poll."
      Start-Sleep -Milliseconds $PollMs
      continue
    }

    RunGit rebase --abort | Out-Null  # defensive

    # 1) Commit local changes (respects .gitignore)
    $status = & $Git status --porcelain
    $madeCommit = $false
    $msg = $null
    if (-not [string]::IsNullOrWhiteSpace($status)) {
      RunGit add -A | Out-Null
      $msg = "auto-sync: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
      if ((RunGit commit -m $msg) -eq 0) {
        $madeCommit = $true
        Log "Committed: $msg"
      }
    }

    # 2) Divergence
    $div = Get-Divergence
    $ra = $div.RemoteAhead
    $la = $div.LocalAhead
    Log "Divergence: remoteAhead=$ra, localAhead=$la"

    if ($ra -eq 0 -and $la -gt 0) {
      if ((RunGit push origin $Branch) -eq 0) {
        if ($msg) {
          Log ("Pushed OK: " + $msg)
        } else {
          Log "Pushed OK: existing local commits"
        }
        Clear-Backoff
      } else {
        Log "PUSH-ERROR (exit $LASTEXITCODE)."
      }
    } elseif ($ra -gt 0 -and $la -eq 0) {
      if ((RunGit merge --ff-only "origin/$Branch") -eq 0) {
        Log "Fast-forwarded to origin/$Branch."
        Clear-Backoff
      } else {
        Log "FF-ERROR (exit $LASTEXITCODE)."
        Start-Backoff
      }
    } elseif ($ra -eq 0 -and $la -eq 0) {
      # In sync; nothing to do
    } else {
      Log "DIVERGED: remote+$ra, local+$la. Manual merge/rebase required. Backing off."
      if ($madeCommit) {
        RunGit reset --soft HEAD~1 | Out-Null
        Log "Undid last auto commit (changes kept staged)."
      }
      Start-Backoff
    }

  } catch {
    Log "SYNC-ERROR: $($_.Exception.Message)"
  }
  Start-Sleep -Milliseconds $PollMs
}
