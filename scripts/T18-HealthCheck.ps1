$root = $env:T18Root; if (-not $root) { $root = 'C:\T18' }
$data = Join-Path $root 'data'
$logp = Join-Path $data 'logs\update_instrument_master.log'
$csvp = Join-Path $data 'api-scrip-master.csv'
$mapc = Join-Path $data 'securityid_map_t18.csv'
$mapj = Join-Path $data 'instrument_map_t18.json'

$ok = $true
$issues = @()

if (!(Test-Path $csvp)) { $ok=$false; $issues += "Missing $csvp" }
if (!(Test-Path $logp)) { $ok=$false; $issues += "Missing $logp" }
if (!(Test-Path $mapc)) { $issues += "Missing $mapc" }
if (!(Test-Path $mapj)) { $issues += "Missing $mapj" }

$last = if (Test-Path $logp) { Get-Content $logp -Tail 1 } else { "" }
if ($last -notmatch 'OK') { $ok=$false; $issues += "Last log entry not OK: $last" }

if ($ok) {
  Write-Host ("✔ T18 OK   " + $last) -ForegroundColor Green
  exit 0
} else {
  Write-Host ("✖ T18 Issue: " + ($issues -join ' | ')) -ForegroundColor Red
  exit 1
}
