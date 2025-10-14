$ErrorActionPreference = "Stop"
$VpsUser = "t18svc"
$VpsHost = "YOUR.VPS.IP.ADDR"
$LogDir  = "C:\T18\data\logs"
$LogFile = Join-Path $LogDir "relay_selftest.log"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log { param([string]$msg) $ts=(Get-Date).ToString("s"); "$ts  $msg" | Tee-Object -FilePath $LogFile -Append }

# 1) Start SSH local tunnel (if not already bound)
$ports = (Get-NetTCPConnection -LocalPort 51839 -ErrorAction SilentlyContinue)
if (-not $ports) {
  Start-Process -WindowStyle Hidden -FilePath "ssh" -ArgumentList "-L 51839:127.0.0.1:51839 $VpsUser@$VpsHost -N"
  Start-Sleep -Seconds 2
  Write-Log "Started SSH tunnel to $VpsHost for 51839"
}

# 2) Health
$health = curl.exe -s http://127.0.0.1:51839/health
Write-Log "HEALTH: $health"

# 3) Legacy paper
$legacyBody = @{
  symbol     = "TEST"
  segment    = "NSE_EQ"
  instrument = "EQUITY"
  side       = "BUY"
  qty        = 1
} | ConvertTo-Json
$legacy = curl.exe -s -H "Content-Type: application/json" -d "$legacyBody" http://127.0.0.1:51839/relay
Write-Log "LEGACY: $legacy"

# 4) Live pass (dhBody)
$dhBody = @{
  dhBody = @{
    securityId        = 2885
    exchangeSegment   = "NSE_EQ"
    transactionType   = "BUY"
    quantity          = 1
    productType       = "INTRADAY"
    orderType         = "MARKET"
    validity          = "DAY"
    price             = 0
    triggerPrice      = 0
    disclosedQuantity = 0
    afterMarketOrder  = $false
    mktProtection     = 0
    tag               = "T18-bridge-test"
  }
} | ConvertTo-Json -Depth 5
$live = curl.exe -s -H "Content-Type: application/json" -d "$dhBody" http://127.0.0.1:51839/relay
Write-Log "LIVEPASS: $live"

Write-Host "Self-test complete. Log: $LogFile"
