param(
  [string]$Repo = "C:\T18",
  [string]$LogPath = "C:\T18\logs\update_main.log"
)

function Log([string]$msg){
  $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Add-Content -Path $LogPath -Value "$stamp $msg"
}

function ShowCmd([string]$exe, [string[]]$args){
  $q = { param($s) if ($s -match '[\s"`^&|<>]') { '"' + ($s -replace '"','\"') + '"' } else { $s } }
  return ($q.Invoke($exe) + ' ' + (($args | ForEach-Object { $q.Invoke($_) }) -join ' ')).Trim()
}

function Run {
  param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Exe,
    [Parameter(ValueFromRemainingArguments=$true, Position=1)]
    [string[]]$Args
  )

  if (-not $Args -or ($Args | Where-Object { $_ -ne $null -and $_ -ne '' }).Count -eq 0) {
    throw "Run(): missing args for $Exe"
  }

  Log ("RUN: " + (ShowCmd $Exe $Args))

  $outFile = Join-Path (Split-Path $LogPath) '_tmp_out.txt'
  $errFile = Join-Path (Split-Path $LogPath) '_tmp_err.txt'

  $p = Start-Process -FilePath $Exe `
        -ArgumentList $Args `
        -NoNewWindow -PassThru -Wait `
        -RedirectStandardOutput $outFile `
        -RedirectStandardError  $errFile

  $out = Get-Content $outFile -Raw -ErrorAction SilentlyContinue
  $err = Get-Content $errFile -Raw -ErrorAction SilentlyContinue
  Remove-Item $outFile,$errFile -Force -ErrorAction SilentlyContinue

  if ($out) { Log ("OUT: " + $out.TrimEnd()) }
  if ($err) { Log ("ERR: " + $err.TrimEnd()) }
  Log ("EXIT: " + $p.ExitCode)
  return @{ code = $p.ExitCode; out = $out; err = $err }
}

New-Item -ItemType Directory -Force $Repo | Out-Null
New-Item -ItemType Directory -Force (Split-Path $LogPath) | Out-Null

Log "=== START update ==="

# Ensure main & up-to-date
$cur = Run git '-C', $Repo, 'rev-parse', '--abbrev-ref', 'HEAD'
if ($cur.code -ne 0) { Log "ERROR: cannot read HEAD"; Log "=== END update (FAIL) ==="; exit 1 }

if ($cur.out.Trim() -ne 'main') {
  $sw = Run git '-C', $Repo, 'switch', 'main'
  if ($sw.code -ne 0) { Log "ERROR: git switch main failed"; Log "=== END update (FAIL) ==="; exit 1 }
}

$fe = Run git '-C', $Repo, 'fetch', 'origin'
if ($fe.code -ne 0) { Log "ERROR: git fetch failed"; Log "=== END update (FAIL) ==="; exit 1 }

$ff = Run git '-C', $Repo, 'merge', '--ff-only', 'origin/main'
if ($ff.code -ne 0) { Log "ERROR: fast-forward failed"; Log "=== END update (FAIL) ==="; exit 1 }

# Changes?
$st = Run git '-C', $Repo, 'status', '--porcelain'
if ($st.code -ne 0) { Log 'ERROR: git status failed'; Log "=== END update (FAIL) ==="; exit 1 }

if (-not $st.out.Trim()) {
  Log 'No changes; nothing to commit/push'
  Log '=== END update (OK) ==='
  exit 0
}

Log 'Changes detected; committing'
$ad = Run git '-C', $Repo, 'add', '-A'
if ($ad.code -ne 0) { Log 'ERROR: git add failed'; Log '=== END update (FAIL) ==='; exit 1 }

$msg = "manual update: " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
$cm  = Run git '-C', $Repo, 'commit', '-m', $msg
if ($cm.code -ne 0) { Log 'ERROR: git commit failed'; Log '=== END update (FAIL) ==='; exit 1 }

Log 'Pushing main'
$push = Run git '-C', $Repo, 'push', 'origin', 'main'
if ($push.code -ne 0) {
  Log 'ERROR: git push failed (branch protection may block direct push)'
  if ($push.out) { Log ('Push OUT: ' + $push.out.TrimEnd()) }
  if ($push.err) { Log ('Push ERR: ' + $push.err.TrimEnd()) }
  Log '=== END update (FAIL) ==='
  exit 1
}

if ($push.out) { Log ('Push OUT: ' + $push.out.TrimEnd()) }
Log '=== END update (OK) ==='
exit 0
