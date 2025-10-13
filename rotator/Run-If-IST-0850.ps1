# C:\T18\rotator\Run-If-IST-0850.ps1
$ErrorActionPreference = 'Stop'

# --- Helpers ---
function Get-ISTNow {
  $tz = [TimeZoneInfo]::FindSystemTimeZoneById("India Standard Time")
  return [TimeZoneInfo]::ConvertTime([DateTime]::UtcNow, $tz)
}

function Get-LastRotationDateLocal {
  $log = "C:\T18\logs\bridge\token_rotation.log"
  if (-not (Test-Path $log)) { return $null }
  $last = Get-Content $log | Select-Object -Last 1
  if (-not $last) { return $null }
  # log line format: [2025-10-05 20:52:23Z] New token fetched, expires (IST): ...
  if ($last -match '^\[(?<ts>[^]]+)\]') {
    return [DateTime]::Parse($Matches.ts, $null, [System.Globalization.DateTimeStyles]::AssumeUniversal)
  }
  return $null
}

# --- Logic: run at ~08:50 IST, once per day ---
$nowIST = Get-ISTNow
$todayIST = $nowIST.Date
$targetIST = $todayIST.AddHours(8).AddMinutes(50)   # 08:50 IST

# Run if current IST time is within ±10 minutes of 08:50
$windowStart = $targetIST.AddMinutes(-10)
$windowEnd   = $targetIST.AddMinutes(10)

$lastRunUtc = Get-LastRotationDateLocal
$alreadyToday = $false
if ($lastRunUtc) {
  $tzIST = [TimeZoneInfo]::FindSystemTimeZoneById("India Standard Time")
  $lastRunIST = [TimeZoneInfo]::ConvertTime($lastRunUtc, $tzIST)
  $alreadyToday = ($lastRunIST.Date -eq $todayIST)
}

if ($nowIST -ge $windowStart -and $nowIST -le $windowEnd -and -not $alreadyToday) {
  try {
    & pwsh.exe -NoProfile -File "C:\T18\rotator\Rotate-DhanToken.ps1"
  } catch {
    Add-Content "C:\T18\logs\bridge\token_rotation.log" ("[{0}] Rotation failed: {1}" -f ([DateTime]::UtcNow.ToString("u")), $_.Exception.Message)
  }
}
