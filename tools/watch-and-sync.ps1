<#
T18 Auto Watch & Sync – v10.3 (PS5 stable)
- Poll every 5s; commit local changes, fetch, ff-only or push.
- No auto-rebase; if diverged, log and short backoff.
- Uses Start-Process to run git => no NativeCommandError.
- Logs outside repo: %LOCALAPPDATA%\T18\logs\sync.log
- Single instance via mutex.
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
$mutexName = "Global\T18WatchSyncV103"
$created = $false
$mutex = New-Object System.Threading.Mutex($false, $mutexName, [ref]$created)
if (-not $mutex.WaitOne(0, $false)) { Log "Another v10.3 instance is running. Exiting."; exit 0 }

# --- safe git runner (no PS NativeCommandError) ---
function Join-Args {
  param([string[]]$items)
  $items | ForEach-Object {
    if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ }
  } | Out-String
}
function Run-Git {
  param([Parameter(Mandatory=$true)][string[]]$argv)
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $Git
  # Build a safe single-string Args (git.exe parses spaces)
  $psi.Arguments = ([string]::Join(' ', ($argv | ForEach-Object {
    if ($_ -match '[\s"]') { '"' + ($_ -replace '"','\"') + '"' } else { $_ }
  })))
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError  = $true
  $psi.CreateNoWindow = $true
  $p = [System.Diagnostics.Process]::Start($psi)
  $stdout = $p.StandardOutput.ReadToEnd()
  $stderr = $p.StandardError.ReadToEnd()
  $p.WaitForExit()
  if ($stdout) { ($stdout -split "`r?`n") | Where-Object { $_ -ne '' } | ForEach-Object { Log "git> $_" } }
  if ($stderr) { ($stderr -split "`r?`n") | Where-Object { $_ -ne '' } | ForEach-Object { Log "git> $_" } }
  return $p.ExitCode
}

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
function Clear-Backoff { if (Test-Path $BackoffFile) { Remove-Item $BackoffFile -Force -ErrorAction SilentlyContinue } }
function Get-Divergence {
  [void](Run-Git -argv @('fetch','origin',$Branch))
  $out = & $Git rev-list --left-right --count "origin/$Branch...HEAD" 2>$null
  if (-not $out) { return @{ RemoteAhead = 0; LocalAhead = 0 } }
  $p = $out -split "\s+"
  return @{ RemoteAhead = [int]$p[0]; LocalAhead = [int]$p[1] }
}

# --- repo/branch, one-time configs ---
if (-not (Test-Path $RepoPath)) { throw "Repo path not found: $RepoPath" }
Set-Location $RepoPath
try {
  $cur = (& $Git rev-parse --abbrev-ref HEAD).Trim()
  if ($cur -ne $Branch) { Log "Switching to $Branch (was $cur)"; [void](Run-Git -argv @('checkout','-B',$Branch)) }
} catch { Log "WARN: Cannot read current branch: $($_.Exception.Message)" }

# silence CRLF noise for this repo
[void](Run-Git -argv @('config','core.autocrlf','true'))
[void](Run-Git -argv @('config','core.safecrlf','false'))

Log "Watcher v10.3 (polling) started | repo=$RepoPath | branch=$Branch | poll=${PollMs}ms | git=$Git"
[void](Run-Git -argv @('--version'))

# --- main loop ---
while ($true) {
  # 1) Commit local changes (respects .gitignore)
  $status = & $Git status --porcelain
  $madeCommit = $false
  $msg = $null
  if (-not [string]::IsNullOrWhiteSpace($status)) {
    if ((Run-Git -argv @('add','-A')) -eq 0) {
      $msg = "auto-sync: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
      if ((Run-Git -argv @('commit','-m',$msg)) -eq 0) {
        $madeCommit = $true
        Log "Committed: $msg"
      } else { Log "WARN: commit exit $LASTEXITCODE" }
    } else { Log "WARN: add exit $LASTEXITCODE" }
  }

  # 2) Divergence
  $div = Get-Divergence
  $ra = $div.RemoteAhead
  $la = $div.LocalAhead
  Log "Divergence: remoteAhead=$ra, localAhead=$la"

  if ($ra -eq 0 -and $la -gt 0) {
    if ((Run-Git -argv @('push','origin',$Branch)) -eq 0) {
      if ($msg) { Log ("Pushed OK: " + $msg) } else { Log "Pushed OK: existing local commits" }
      Clear-Backoff
    } else { Log "WARN: push exit $LASTEXITCODE" }
  } elseif ($ra -gt 0 -and $la -eq 0) {
    if ((Run-Git -argv @('merge','--ff-only',"origin/$Branch")) -eq 0) {
      Log "Fast-forwarded to origin/$Branch."
      Clear-Backoff
    } else {
      Log "WARN: ff-only merge exit $LASTEXITCODE"
      Start-Backoff
    }
  } elseif ($ra -eq 0 -and $la -eq 0) {
    # in sync
  } else {
    Log "DIVERGED: remote+$ra, local+$la. Manual merge/rebase required. Backing off."
    if ($madeCommit) {
      [void](Run-Git -argv @('reset','--soft','HEAD~1'))
      Log "Undid last auto commit (changes kept staged)."
    }
    Start-Backoff
  }

  Start-Sleep -Milliseconds $PollMs
}
