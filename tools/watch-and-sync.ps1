<# 
T18 Auto Watch & Sync (Windows)
- Watches C:\T18 (recursively) for changes.
- Debounces bursts, then: git add -> commit -> pull --rebase -> push.
- Skips if nothing to commit.
- Logs to C:\T18\logs\sync.log
- Respects .gitignore (we rely on `git status --porcelain` to detect staged changes).
- Single-instance safe.
#>

$ErrorActionPreference = "Stop"

# --- settings ---
$RepoPath   = "C:\T18"
$Branch     = "main"
$DebounceMs = 7000
$LogDir     = Join-Path $RepoPath "logs"
$LogFile    = Join-Path $LogDir "sync.log"

# --- init logging ---
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
function Log([string]$msg) {
  $stamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
  "$stamp  $msg" | Out-File -FilePath $LogFile -Append -Encoding utf8
}

# --- single instance guard (FIXED) ---
$mutexName = "Global\T18WatchSync"
$created = $false     # 👈 declare before using [ref]
$mutex = New-Object System.Threading.Mutex($false, $mutexName, [ref]$created)
if (-not $mutex.WaitOne(0, $false)) {
  Log "Another watcher instance already running. Exiting."
  exit 0
}

# --- ensure repo exists ---
if (-not (Test-Path $RepoPath)) { throw "Repo path not found: $RepoPath" }
Set-Location $RepoPath

# --- ensure branch ---
try {
  $cur = (git rev-parse --abbrev-ref HEAD).Trim()
  if ($cur -ne $Branch) {
    Log "Switching to $Branch (was $cur)"
    git checkout -B $Branch | Out-Null
  }
} catch {
  Log "WARN: Could not determine current branch: $($_.Exception.Message)"
}

# --- debounce timer setup ---
$timer = New-Object Timers.Timer
$timer.Interval = $DebounceMs
$timer.AutoReset = $false
$syncLock = New-Object object
$isSyncing = $false

# --- core sync ---
function Do-Sync {
  if ($isSyncing) { return }
  $isSyncing = $true
  try {
    Set-Location $RepoPath
    try { git rebase --abort | Out-Null } catch {}

    $status = git status --porcelain
    if ([string]::IsNullOrWhiteSpace($status)) {
      Log "No changes to commit."
      return
    }

    git add -A | Out-Null
    $msg = "auto-sync: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    git commit -m $msg | Out-Null

    try {
      git pull --rebase origin $Branch | Out-Null
    } catch {
      Log "PULL/REBASE-ERROR: $($_.Exception.Message)"
      try { git rebase --abort | Out-Null } catch {}
      try { git reset --soft HEAD~1 | Out-Null } catch {}
      Log "Rebase conflict. Last commit undone (changes kept). Manual resolution required."
      return
    }

    try {
      git push origin $Branch | Out-Null
      Log "Pushed OK: $msg"
    } catch {
      Log "PUSH-ERROR: $($_.Exception.Message)"
    }

  } catch {
    Log "SYNC-ERROR: $($_.Exception.Message)"
  } finally {
    $isSyncing = $false
  }
}

# --- file system watcher ---
$fsw = New-Object System.IO.FileSystemWatcher
$fsw.Path = $RepoPath
$fsw.IncludeSubdirectories = $true
$fsw.NotifyFilter = [IO.NotifyFilters]'FileName, DirectoryName, LastWrite, Size, Attributes'

function Should-Ignore($path) {
  if ([string]::IsNullOrEmpty($path)) { return $false }
  $p = $path.ToLower()
  return $p.Contains("\.git\")
}

function Restart-Timer {
  [System.Threading.Monitor]::Enter($syncLock)
  try { $timer.Stop(); $timer.Start() } finally { [System.Threading.Monitor]::Exit($syncLock) }
}

Register-ObjectEvent -InputObject $fsw -EventName Changed -Action {
  if (-not (Should-Ignore $Event.SourceEventArgs.FullPath)) { Restart-Timer }
} | Out-Null
Register-ObjectEvent -InputObject $fsw -EventName Created -Action {
  if (-not (Should-Ignore $Event.SourceEventArgs.FullPath)) { Restart-Timer }
} | Out-Null
Register-ObjectEvent -InputObject $fsw -EventName Deleted -Action {
  if (-not (Should-Ignore $Event.SourceEventArgs.FullPath)) { Restart-Timer }
} | Out-Null
Register-ObjectEvent -InputObject $fsw -EventName Renamed -Action {
  if (-not (Should-Ignore $Event.SourceEventArgs.FullPath)) { Restart-Timer }
} | Out-Null

Register-ObjectEvent -InputObject $timer -EventName Elapsed -Action { Do-Sync } | Out-Null

$fsw.EnableRaisingEvents = $true
Log "Watcher started on $RepoPath, branch=$Branch, debounce=${DebounceMs}ms"

while ($true) { Start-Sleep -Seconds 5 }
