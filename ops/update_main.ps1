param(
  [string]$Repo    = "C:\T18",
  [string]$LogPath = "C:\T18\logs\update_main.log"
)

function Log([string]$msg){
  $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Add-Content -Path $LogPath -Value "$stamp $msg"
}

function ShowCmd([string]$exe, [string[]]$args){
  $q = { param($s) if ($s -match '[\s"`^&|<>]') { '"' + ($s -replace '"','\"') + '"' } else { $s } }
  ($q.Invoke($exe) + ' ' + (($args | ForEach-Object { $q.Invoke($_) }) -join ' ')).Trim()
}

function RunGit {
  param([Parameter(Mandatory)][string[]]$Args)
  Log ("RUN: " + (ShowCmd 'git' $Args))
  $all = & git @Args 2>&1
  $code = $LASTEXITCODE
  if ($all) { Log ("OUT: " + ($all | Out-String).TrimEnd()) }
  Log ("EXIT: $code")
  return @{ code = $code; out = ($all | Out-String) }
}

New-Item -ItemType Directory -Force $Repo | Out-Null
New-Item -ItemType Directory -Force (Split-Path $LogPath) | Out-Null
Log "=== START update ==="

# 0) Make sure this repo is safe and on main
$cur = RunGit @('-C', $Repo, 'rev-parse', '--abbrev-ref', 'HEAD')
if ($cur.code -ne 0) { Log "ERROR: cannot read HEAD"; Log "=== END update (FAIL) ==="; exit 1 }

if ($cur.out.Trim() -ne 'main') {
  $sw = RunGit @('-C', $Repo, 'switch', 'main')
  if ($sw.code -ne 0) { Log "ERROR: git switch main failed"; Log "=== END update (FAIL) ==="; exit 1 }
}

# 1) Sync from origin/main
$fe = RunGit @('-C', $Repo, 'fetch', 'origin')
if ($fe.code -ne 0) { Log "ERROR: git fetch failed"; Log "=== END update (FAIL) ==="; exit 1 }

$ff = RunGit @('-C', $Repo, 'merge', '--ff-only', 'origin/main')
if ($ff.code -ne 0) { Log "ERROR: fast-forward failed"; Log "=== END update (FAIL) ==="; exit 1 }

# 2) One-time untrack noisy quarantine dirs if they ended up tracked earlier
$untrack = RunGit @('-C', $Repo, 'rm', '-r', '--cached', '--ignore-unmatch', '--',
  '_quarantine_*', 'teevra18')
# (No hard fail if this does nothing)

# 3) Check for changes
$st = RunGit @('-C', $Repo, 'status', '--porcelain')
if ($st.code -ne 0) { Log 'ERROR: git status failed'; Log "=== END update (FAIL) ==="; exit 1 }

if (-not $st.out.Trim()) {
  Log 'No changes; nothing to commit/push'
  Log '=== END update (OK) ==='
  exit 0
}

# 4) Commit & push
Log 'Changes detected; committing'
$ad = RunGit @('-C', $Repo, 'add', '-A')
if ($ad.code -ne 0) { Log 'ERROR: git add failed'; Log '=== END update (FAIL) ==='; exit 1 }

$msg = "manual update: " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
$cm  = RunGit @('-C', $Repo, 'commit', '-m', $msg)
if ($cm.code -ne 0) { Log 'ERROR: git commit failed'; Log '=== END update (FAIL) ==='; exit 1 }

Log 'Pushing main'
$push = RunGit @('-C', $Repo, 'push', 'origin', 'main')
if ($push.code -ne 0) {
  Log 'ERROR: git push failed (branch protection may block direct push)'
  Log '=== END update (FAIL) ==='
  exit 1
}

Log '=== END update (OK) ==='
exit 0
