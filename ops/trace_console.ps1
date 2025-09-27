# C:\T18\ops\trace_console.ps1
$Log = 'C:\T18\logs\noflash_watch.log'
New-Item -ItemType Directory -Force -Path (Split-Path $Log) | Out-Null

# Open the log once with ReadWrite + FileShare.ReadWrite and append mode
$fs = [System.IO.File]::Open($Log,
  [System.IO.FileMode]::OpenOrCreate,
  [System.IO.FileAccess]::ReadWrite,
  [System.IO.FileShare]::ReadWrite)
$fs.Seek(0, [System.IO.SeekOrigin]::End) | Out-Null
$sw = New-Object System.IO.StreamWriter($fs, [System.Text.UTF8Encoding]::new($true))
$sw.AutoFlush = $true

# Clean old subscriptions from this session
Get-EventSubscriber | Unregister-Event -Force -ErrorAction SilentlyContinue | Out-Null

$Targets = @(
  'cmd.exe','conhost.exe','powershell.exe','pwsh.exe','git.exe',
  'wscript.exe','cscript.exe','python.exe','pythonw.exe',
  'git-credential-manager.exe','git-credential-manager-ui.exe'
)

function Log-Line {
  param([string]$msg)
  $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff'
  try { $sw.WriteLine("[$ts] $msg") } catch {}
}

Log-Line "==== TRACE START ===="

# Subscribe to process starts (WMI)
$Query = "SELECT * FROM Win32_ProcessStartTrace"
$sub = Register-WmiEvent -Query $Query -SourceIdentifier TraceProcStart

try {
  $stopAt = (Get-Date).AddMinutes(15)   # watch ~15 min; change if needed
  while ((Get-Date) -lt $stopAt) {
    $evt = Wait-Event -SourceIdentifier TraceProcStart -Timeout 1
    if ($null -ne $evt) {
      $p = $evt.SourceEventArgs.NewEvent
      $name = ($p.ProcessName ?? '').ToString()
      if ($Targets -contains $name.ToLower()) {
        $cmd  = (($p.CommandLine ?? '') -replace '\s+',' ').Trim()
        $pid  = [int]$p.ProcessID
        $ppid = [int]$p.ParentProcessID
        try {
          $parent = Get-Process -Id $ppid -ErrorAction SilentlyContinue
          $parentInfo = if ($parent) { "$($parent.ProcessName).exe (PPID=$ppid)" } else { "PPID=$ppid" }
        } catch { $parentInfo = "PPID=$ppid" }
        Log-Line "PROC START name=$name PID=$pid $parentInfo CMD=$cmd"
      }
      Remove-Event -EventIdentifier $evt.EventIdentifier -ErrorAction SilentlyContinue
    }
  }
}
finally {
  Unregister-Event -SourceIdentifier TraceProcStart -ErrorAction SilentlyContinue | Out-Null
  Log-Line "==== TRACE END ===="
  try { $sw.Flush(); $sw.Dispose(); $fs.Dispose() } catch {}
}
