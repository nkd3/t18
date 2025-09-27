param(
  [string]$Message = "manual: $(Get-Date -Format ''yyyy-MM-dd HH:mm:ss'')"
)

$ErrorActionPreference = "Stop"
$repo = "C:\T18"
$log  = "C:\T18\logs\git_manual_push.log"

# Use real git.exe (avoid git.cmd → no extra shells)
$GIT = "C:\Program Files\Git\bin\git.exe"
if (-not (Test-Path $GIT)) { $GIT = "C:\Program Files (x86)\Git\bin\git.exe" }

# Hard-disable any interactive prompts in this run (GH CLI helper will supply token)
$env:GIT_TERMINAL_PROMPT = "0"
$env:GIT_ASKPASS = $null
$env:SSH_ASKPASS = $null

function Run($args) {
  $p = Start-Process -FilePath $GIT -ArgumentList $args -WorkingDirectory $repo `
       -NoNewWindow -PassThru -Wait -WindowStyle Hidden
  return $p.ExitCode
}

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] === manual push start ===" | Add-Content $log

# Status: if nothing changed, no commit
$rc = Run "status --porcelain"
# (git status returns 0 even with changes; we’ll check via porcelain text)
$changed = (& $GIT -C $repo status --porcelain)
if ($changed) {
  Run "add -A"        | Out-Null
  Run "commit -m ""$Message""" | Out-Null
  "[$(Get-Date -Format 'HH:mm:ss')] committed: $Message" | Add-Content $log
} else {
  "[$(Get-Date -Format 'HH:mm:ss')] nothing to commit" | Add-Content $log
}

# Push (uses GH CLI helper you configured)
$rc = Run "push origin main"
if ($rc -eq 0) {
  "[$(Get-Date -Format 'HH:mm:ss')] pushed ok" | Add-Content $log
} else {
  "[$(Get-Date -Format 'HH:mm:ss')] push failed rc=$rc" | Add-Content $log
}

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] === manual push end ===" | Add-Content $log
