# C:\T18\ops\trace_conhost_parent.ps1
$log = 'C:\T18\logs\conhost_trace.log'
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
"[$(Get-Date -Format o)] ==== TRACE START ====" | Out-File -Append -Encoding utf8 $log

function Get-ProcInfo {
  param([int]$ProcId)
  try {
    return Get-CimInstance -Namespace root\cimv2 -ClassName Win32_Process -Filter "ProcessId=$ProcId" -ErrorAction Stop
  } catch {
    return Get-WmiObject -Namespace root\cimv2 -Class Win32_Process -Filter "ProcessId=$ProcId" -ErrorAction SilentlyContinue
  }
}

$stopAt = (Get-Date).AddMinutes(5)

while((Get-Date) -lt $stopAt){
  try{
    $recent = Get-Process conhost -ErrorAction SilentlyContinue |
      Where-Object { $_.StartTime -gt (Get-Date).AddSeconds(-2) }

    foreach($ch in $recent){
      $ts = (Get-Date -Format o)
      $chInfo = Get-ProcInfo -ProcId $ch.Id
      if(-not $chInfo){ continue }

      $pp  = if($chInfo.ParentProcessId){ Get-ProcInfo -ProcId $chInfo.ParentProcessId }
      $gp  = if($pp -and $pp.ParentProcessId){ Get-ProcInfo -ProcId $pp.ParentProcessId }

      $pName  = if($pp){ $pp.Name } else { "" }
      $pPid   = if($pp){ $pp.ProcessId } else { 0 }
      $pCmd   = if($pp){ $pp.CommandLine } else { "" }

      $gpName = if($gp){ $gp.Name } else { "" }
      $gpPid  = if($gp){ $gp.ProcessId } else { 0 }
      $gpCmd  = if($gp){ $gp.CommandLine } else { "" }

      $line = "[{0}] CONHOST pid={1} | parent={2}({3}) | gparent={4}({5})`n  parent-cmd: {6}`n  gparent-cmd: {7}" -f `
              $ts, $ch.Id, $pName, $pPid, $gpName, $gpPid, ($pCmd -replace '\s+',' '), ($gpCmd -replace '\s+',' ')
      $line | Out-File -Append -Encoding utf8 $log
    }
  } catch { }
  Start-Sleep -Milliseconds 300
}

"[$(Get-Date -Format o)] ==== TRACE END ====" | Out-File -Append -Encoding utf8 $log
Write-Host "Trace written to $log"
