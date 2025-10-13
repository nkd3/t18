<# 
T18 Auto Watch & Sync (Windows)
- Watches C:\T18 (recursively) for changes.
- Debounces bursts, then: commit -> fast-forward/push/rebase as needed.
- Respects .gitignore via `git status --porcelain`.
- Logs to C:\T18\logs\sync.log
- Single-instance; backs off after conflicts.
#>

$ErrorActionPreference = "Stop"

# --- settings ---
$RepoPath   = "C:\T18"
$Branch     = "main"
$DebounceMs = 7000
$BackoffSec = 120         # backoff after a rebase conflict
$LogDir     = Join-Path $RepoPath "logs"
$LogFile    = Join-Path $LogDir "sync.log"
$BackoffFile= Join-Path $LogDir "rebase_backoff.txt"

# --- logging ---
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
function Log([string]$msg) {
  $stamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
  "$stamp  $msg" | Out-File -FilePath $LogFile -Append -Encoding utf8
}

# --- single instance guard ---
$mutexName = "Global\T18WatchSync"
$created = $false
$mutex = New-Object System.Threading.Mutex($false, $mutexName, [ref]$created)
if (-not $mutex.WaitOne(0, $false)) {
  Log "Another watcher instance already running. Exiting."
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

# --- ensure repo exists/branch ---
if (-not (Test-Path $RepoPath)) { throw "Repo path not found: $RepoPath" }
Set-Location $RepoPath
try {
  $cur = (git rev-parse --abbrev-ref HEAD).Trim()
  if ($cur -ne $Branch) { Log "Switching to $Branch (was $cur)"; git checkout -B $Branch | Out-Null }
} catch { Log "WARN: Could not determine current branch: $($_.Exception.Message)" }

# --- debounce timer setup ---
$timer = New-Object Timers.Timer
$timer.Interval = $DebounceMs
$timer.AutoReset = $false
$syncLock = New-Object object
$isSyncing = $false

# --- divergence probe ---
function Get-Divergence {
  # returns @{RemoteAhead=<int>; LocalAhead=<int>}
  git fetch origin $Branch | Out-Null
  $out = git rev-list --left-right --count origin/$Branch...HEAD
  # format: "<remoteAhead>\t<localAhead>"
  $parts = $out -split "\s+"
  return @{ RemoteAhead = [int]$parts[0]; LocalAhead = [int]$parts[1] }
}

# --- core sync ---
function Do-Sync {
  if ($isSyncing) { return }
  $isSyncing = $true
  try {
    Set-Location $RepoPath

    if (In-Backoff) {
      Log "Backoff active; skipping sync."
      return
    }

    try { git rebase --abort | Out-Null } catch {}

    $status = git status --porcelain
    if (-not [string]::IsNullOrWhiteSpace($status)) {
      # commit local changes first
      git add -A | Out-Null
      $msg = "auto-sync: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
      git commit -m $msg | Out-Null
    } else {
      $msg = $null
    }

    # analyze divergence
    $div = Get-Divergence
    $ra = $div.RemoteAhead
    $la = $div.LocalAhead

    if ($ra -eq 0 -and $la -gt 0) {
      # origin not ahead; just push our commits
      try { git push origin $Branch | Out-Null; Log "Pushed OK: ${msg:-no-op}" } catch { Log "PUSH-ERROR: $($_.Exception.Message)" }
      Clear-Backoff
      return
    }

    if ($ra -gt 0 -and $la -eq 0) {
      # we have no local commits; fast-forward
      try { git merge --ff-only origin/$Branch | Out-Null; Log "Fast-forwarded to origin/$Branch." } catch { Log "FF-ERROR: $($_.Exception.Message)"; return }
      Clear-Backoff
      return
    }

    if ($ra -eq 0 -and $la -eq 0) {
      Log "No changes to commit."
      Clear-Backoff
      return
    }

    # both sides ahead -> need rebase
    try {
      git rebase origin/$Branch | Out-Null
      try { git push origin $Branch | Out-Null; Log "Rebased & pushed OK: ${msg:-rebased}" } catch { Log "PUSH-ERROR: $($_.Exception.Message)" }
      Clear-Backoff
    } catch {
      Log "REBASE-CONFLICT: $($_.Exception.Message)"
      try { git rebase --abort | Out-Null } catch {}
      # Roll back last commit if we just created one, keep changes staged
      try { if ($msg) { git reset --soft HEAD~1 | Out-Null } } catch {}
      Log "Rebase conflict. Last commit undone (changes kept). Manual resolution required."
      Start-Backoff
      return
    }

  } catch {
    Log "SYNC-ERROR: $($_.Exception.Message)"
  } finally {
    $isSyncing = $false
  }
}

# --- watcher ---
$fsw = New-Object System.IO.FileSystemWatcher
$fsw.Path = $RepoPath
$fsw.IncludeSubdirectories = $true
$fsw.NotifyFilter = [IO.NotifyFilters]'FileName, DirectoryName, LastWrite, Size, Attributes'

function Should-Ignore($path) {
  if ([string]::IsNullOrEmpty($path)) { return $false }
  $p = $path.ToLower()
  return $p.Contains("\.git\")
}
function Restart-Timer { [System.Threading.Monitor]::Enter($syncLock); try { $timer.Stop(); $timer.Start() } finally { [System.Threading.Monitor]::Exit($syncLock) } }

Register-ObjectEvent -InputObject $fsw -EventName Changed -Action { if (-not (Should-Ignore $Event.SourceEventArgs.FullPath)) { Restart-Timer } } | Out-Null
Register-ObjectEvent -InputObject $fsw -EventName Created -Action { if (-not (Should-Ignore $Event.SourceEventArgs.FullPath)) { Restart-Timer } } | Out-Null
Register-ObjectEvent -InputObject $fsw -EventName Deleted -Action { if (-not (Should-Ignore $Event.SourceEventArgs.FullPath)) { Restart-Timer } } | Out-Null
Register-ObjectEvent -InputObject $fsw -EventName Renamed -Action { if (-not (Should-Ignore $Event.SourceEventArgs.FullPath)) { Restart-Timer } } | Out-Null

Register-ObjectEvent -InputObject $timer -EventName Elapsed -Action { Do-Sync } | Out-Null

$fsw.EnableRaisingEvents = $true
Log "Watcher started on $RepoPath, branch=$Branch, debounce=${DebounceMs}ms"

while ($true) { Start-Sleep -Seconds 5 }
