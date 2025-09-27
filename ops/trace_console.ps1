# C:\T18\ops\trace_console.ps1  (PS 5.1-compatible)
$Log = 'C:\T18\logs\noflash_watch.log'
New-Item -ItemType Directory -Force -Path (Split-Path $Log) | Out-Null

# Open once, append, shareable
$fs = [System.IO.File]::Open(
    $Log,
    [System.IO.FileMode]::OpenOrCreate,
    [System.IO.FileAccess]::ReadWrite,
    [System.IO.FileShare]::ReadWrite
)
$fs.Seek(0, [System.IO.SeekOrigin]::End) | Out-Null
$sw = New-Object System.IO.StreamWriter($fs, [System.Text.UTF8Encoding]::new($true))
$sw.AutoFlush = $true

# Clean old event subscriptions in this session
Get-EventSubscriber | Unregister-Event -Force -ErrorAction SilentlyContinue | Out-Null

# processes we care about
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

# Subscribe for process starts
$Query = "SELECT * FROM Win32_ProcessStartTrace"
$sub = Register-WmiEvent -Query $Query -SourceIdentifier TraceProcStart

try {
  $stopAt = (Get-Date).AddMinutes(20)  # watch up to ~20 min; adjust if you like
  while ((Get-Date) -lt $stopAt) {
    $evt = Wait-Event -SourceIdentifier TraceProcStart -Timeout 1
    if ($null -ne $evt) {
      $p = $evt.SourceEventArgs.NewEvent

      # Null-safe property access (PS 5.1 doesn't have ??)
      $name = ""
      if ($p.ProcessName) { $name = [string]$p.ProcessName }
      $nameLower = $name.ToLower()

      if ($Targets -contains $nameLower) {
        $cmd = ""
        if ($p.CommandLine) { $cmd = ([string]$p.CommandLine -replace '\s+',' ').Trim() }

        $pid  = 0
        $ppid = 0
        if ($p.ProcessID)       { $pid  = [int]$p.ProcessID }
        if ($p.ParentProcessID) { $ppid = [int]$p.ParentProcessID }

        $parentInfo = "PPID=$ppid"
        try {
          $parent = Get-Process -Id $ppid -ErrorAction SilentlyContinue
          if ($parent) { $parentInfo = "$($parent.ProcessName).exe (PPID=$ppid)" }
        } catch {}

        Log-Line "PROC START name=$name PID=$pid $parentInfo CMD=$cmd"
      }

      # cleanup the delivered event
      Remove-Event -EventIdentifier $evt.EventIdentifier -ErrorAction SilentlyContinue
    }
  }
}
finally {
  Unregister-Event -SourceIdentifier TraceProcStart -ErrorAction SilentlyContinue | Out-Null
  Log-Line "==== TRACE END ===="
  try { $sw.Flush(); $sw.Dispose(); $fs.Dispose() } catch {}
}
