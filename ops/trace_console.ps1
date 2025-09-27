# C:\T18\ops\trace_console.ps1
$Log = 'C:\T18\logs\noflash_watch.log'
New-Item -ItemType Directory -Force -Path (Split-Path $Log) | Out-Null

# Clean old subscriptions from this session
Get-EventSubscriber | Unregister-Event -Force | Out-Null

$Targets = @('cmd.exe','conhost.exe','powershell.exe','pwsh.exe','git.exe','wscript.exe','cscript.exe','python.exe','pythonw.exe','git-credential-manager.exe','git-credential-manager-ui.exe')

# Helper: format one line
function Log-Line {
  param($msg)
  $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff'
  Add-Content -Path $Log -Value "[$ts] $msg"
}

Log-Line "==== TRACE START ===="

# Subscribe to all process starts
$Query = "SELECT * FROM Win32_ProcessStartTrace"
$sub = Register-WmiEvent -Query $Query -SourceIdentifier TraceProcStart

$stopAt = (Get-Date).AddMinutes(10)  # run ~10 minutes; adjust if you want
while ((Get-Date) -lt $stopAt) {
  $evt = Wait-Event -SourceIdentifier TraceProcStart -Timeout 1
  if ($null -ne $evt) {
    $p = $evt.SourceEventArgs.NewEvent
    $name = $p.ProcessName
    $cmd  = ($p.CommandLine -replace '\s+',' ').Trim()
    $ppid = $p.ParentProcessID
    if ($Targets -contains $name.ToLower()) {
      try {
        $parent = Get-Process -Id $ppid -ErrorAction SilentlyContinue
        $parentInfo = if ($parent) { "$($parent.ProcessName).exe (PPID=$ppid)" } else { "PPID=$ppid" }
      } catch { $parentInfo = "PPID=$ppid" }
      Log-Line "PROC START name=$name PID=$($p.ProcessID) $parentInfo CMD=$cmd"
    }
    Remove-Event -EventIdentifier $evt.EventIdentifier -ErrorAction SilentlyContinue
  }
}

Unregister-Event -SourceIdentifier TraceProcStart -ErrorAction SilentlyContinue | Out-Null
Log-Line "==== TRACE END ===="
