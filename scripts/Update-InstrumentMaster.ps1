# C:\T18\scripts\Update-InstrumentMaster.ps1
$ProgressPreference = 'SilentlyContinue'
$root = $env:T18Root; if (-not $root) { $root = 'C:\T18' }
$data = Join-Path $root 'data'
$log  = Join-Path $data 'logs'
$uri  = 'https://images.dhan.co/api-data/api-scrip-master.csv'
$dst  = Join-Path $data 'api-scrip-master.csv'
$bak  = Join-Path $data ("api-scrip-master_{0:yyyyMMdd_HHmmss}.csv" -f (Get-Date))

New-Item -Force -Type Directory $data,$log | Out-Null
if (Test-Path $dst) { Copy-Item $dst $bak -Force }

try {
  Invoke-WebRequest -Uri $uri -OutFile $dst -UseBasicParsing -TimeoutSec 60
  "`tOK  $(Get-Date -Format s)  updated $dst" | Tee-Object -FilePath (Join-Path $log 'update_instrument_master.log') -Append
}
catch {
  "`tERR $(Get-Date -Format s)  $($_.Exception.Message)" | Tee-Object -FilePath (Join-Path $log 'update_instrument_master.log') -Append
  if (Test-Path $bak) { Copy-Item $bak $dst -Force }  # rollback
  exit 1
}
