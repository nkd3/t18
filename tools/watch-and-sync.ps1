<# 
T18 Auto Watch & Sync (Windows)
- Watches C:\T18 (recursively) for changes.
- Debounces bursts, then: git add -> pull --rebase -> commit -> push.
- Skips if nothing to commit.
- Logs to C:\T18\logs\sync.log
- Respects .gitignore (we rely on `git status --porcelain` to detect staged changes).
#>

$ErrorActionPreference = "Stop"

# --- settings ---
$RepoPath   = "C:\T18"
$Branch     = "main"
$DebounceMs = 7000      # wait this long after last change before a sync
$LogDir     = Join-Path $RepoPath "logs"
$LogFile    = Join-Path $LogDir "sync.log"

# --- init logging ---
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
function Log([string]$msg) {
  $stamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
  "$stamp  $msg" | Out-File -FilePath $LogFile -Append -Encoding utf8
}

# --- ensure repo exists ---
if (-not (Test-Path $RepoPath)) {
  throw "Repo path not found: $RepoPath"
}
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
$timerEnabled = $false

$syncLock = New-Object object

# --- the core sync ---
function Do-Sync {
  try {
    Set-Location $RepoPath

    # Only proceed if there are changes (respects .gitignore)
    $status = git status --porcelain
    if ([string]::IsNullOrWhiteSpace($status)) {
      Log "No changes to commit."
      return
    }

    git add -A | Out-Null
    $msg = "auto-sync: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    git commit -m $msg | Out-Null

    # Rebase our new commit(s) on top of origin
    try {
      git pull --rebase origin $Branch | Out-Null
    } catch {
      Log "PULL/REBASE-ERROR: $($_.Exception.Message)"
      # Undo just the last commit, keep changes staged for manual resolve
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
  }
}

# --- file system watcher ---
$fsw = New-Object System.IO.FileSystemWatcher
$fsw.Path = $RepoPath
$fsw.IncludeSubdirectories = $true
$fsw.NotifyFilter = [IO.NotifyFilters]'FileName, DirectoryName, LastWrite, Size, Attributes'

# Ignore changes within .git folder
function Should-Ignore($path) {
  if ([string]::IsNullOrEmpty($path)) { return $false }
  # Normalize
  $p = $path.ToLower()
  return $p.Contains("\.git\")
}

$handler = Register-ObjectEvent -InputObject $fsw -EventName Changed -Action {
  if (Should-Ignore($Event.SourceEventArgs.FullPath)) { return }
  [System.Threading.Monitor]::Enter($syncLock)
  try {
    # Restart debounce timer
    $timer.Stop()
    $timer.Start()
  } finally {
    [System.Threading.Monitor]::Exit($syncLock)
  }
}

# React also to Created/Deleted/Renamed
$handler2 = Register-ObjectEvent -InputObject $fsw -EventName Created -Action {
  if (Should-Ignore($Event.SourceEventArgs.FullPath)) { return }
  [System.Threading.Monitor]::Enter($syncLock)
  try { $timer.Stop(); $timer.Start() } finally { [System.Threading.Monitor]::Exit($syncLock) }
}
$handler3 = Register-ObjectEvent -InputObject $fsw -EventName Deleted -Action {
  if (Should-Ignore($Event.SourceEventArgs.FullPath)) { return }
  [System.Threading.Monitor]::Enter($syncLock)
  try { $timer.Stop(); $timer.Start() } finally { [System.Threading.Monitor]::Exit($syncLock) }
}
$handler4 = Register-ObjectEvent -InputObject $fsw -EventName Renamed -Action {
  if (Should-Ignore($Event.SourceEventArgs.FullPath)) { return }
  [System.Threading.Monitor]::Enter($syncLock)
  try { $timer.Stop(); $timer.Start() } finally { [System.Threading.Monitor]::Exit($syncLock) }
}

# Timer fires -> run sync
$timerEvent = Register-ObjectEvent -InputObject $timer -EventName Elapsed -Action { Do-Sync }

# Start watching
$fsw.EnableRaisingEvents = $true
Log "Watcher started on $RepoPath, branch=$Branch, debounce=${DebounceMs}ms"

# Keep the script alive (service/task host)
while ($true) { Start-Sleep -Seconds 5 }
