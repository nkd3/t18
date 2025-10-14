# C:\T18\scripts\Test-T18Relay.ps1
# T18 Relay self-test (Windows) — verifies SSH tunnel + health + legacy + dhBody live-pass

$ErrorActionPreference = "Stop"

# --- REAL VPS DETAILS (pre-filled) ---
$VpsUser = "t18svc"
$VpsHost = "65.20.67.164"
# -------------------------------------

# Ensure ssh.exe exists
$ssh = (Get-Command ssh -ErrorAction SilentlyContinue)
if (-not $ssh) {
  Write-Host "ERROR: 'ssh' not found. Install OpenSSH Client (Windows Optional Feature) and retry." -ForegroundColor Red
  exit 1
}

$LocalPort = 51839
$LogDir    = "C:\T18\data\logs"
$LogFile   = Join-Path $LogDir "relay_selftest.log"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log { param([string]$msg)
  $ts = (Get-Date).ToString("s")
  "$ts  $msg" | Tee-Object -FilePath $LogFile -Append
}

function Wait-Port {
  param([string]$HostName,[int]$Port,[int]$TimeoutSec=15)
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  do {
    try {
      $ok = Test-NetConnection -ComputerName $HostName -Port $Port -WarningAction SilentlyContinue
      if ($ok.TcpTestSucceeded) { return $true }
    } catch {}
    Start-Sleep -Milliseconds 400
  } while ((Get-Date) -lt $deadline)
  return $false
}

Write-Log "---- T18 Relay self-test start ----"

# 1) Ensure SSH tunnel to VPS:127.0.0.1:51839 -> local 127.0.0.1:51839
$bound = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $LocalPort -ErrorAction SilentlyContinue
if (-not $bound) {
  Write-Log "Starting SSH tunnel to $VpsUser@$VpsHost for $LocalPort ..."
  Start-Process -WindowStyle Hidden -FilePath "ssh" -ArgumentList "-L $LocalPort:127.0.0.1:$LocalPort $VpsUser@$VpsHost -N"
  Start-Sleep -Seconds 2
} else {
  Write-Log "Local port $LocalPort already bound; reusing existing tunnel."
}

# 2) Verify local port answers
if (-not (Wait-Port -HostName "127.0.0.1" -Port $LocalPort -TimeoutSec 15)) {
  Write-Log "ERROR: SSH tunnel to $VpsHost not available on 127.0.0.1:$LocalPort"
  Write-Host "Tunnel check failed. Verify:  ssh $VpsUser@$VpsHost" -ForegroundColor Red
  exit 1
}

# 3) Helper to run curl with status capture (body + HTTP code)
function Invoke-Curl {
  param([string]$Url,[ValidateSet('GET','POST')][string]$Method="GET",[string]$JsonBody=$null)
  $tmp = New-TemporaryFile
  try {
    if ($Method -eq "GET") {
      $out = & curl.exe -sS -w "`nHTTPSTATUS:%{http_code}" "$Url"
    } else {
      $out = & curl.exe -sS -H "Content-Type: application/json" -X $Method -d "$JsonBody" -w "`nHTTPSTATUS:%{http_code}" "$Url"
    }
    $out | Set-Content -LiteralPath $tmp -Encoding UTF8
    $text = Get-Content -LiteralPath $tmp -Raw
    $parts = $text -split "HTTPSTATUS:"
    $body  = $parts[0].Trim()
    $code  = [int]$parts[1].Trim()
    return [pscustomobject]@{ Status = $code; Body = $body }
  } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}

# 4) Health (GET)
$health = Invoke-Curl -Url "http://127.0.0.1:$LocalPort/health" -Method GET
Write-Log ("HEALTH: {0}  {1}" -f $health.Status, $health.Body)

# 5) Legacy paper (POST)
$legacyBody = '{"symbol":"TEST","segment":"NSE_EQ","instrument":"EQUITY","side":"BUY","qty":1}'
$legacy = Invoke-Curl -Url "http://127.0.0.1:$LocalPort/relay" -Method POST -JsonBody $legacyBody
Write-Log ("LEGACY: {0}  {1}" -f $legacy.Status, $legacy.Body)

# 6) dhBody live-pass (POST)
$liveBody = '{"dhBody":{"securityId":2885,"exchangeSegment":"NSE_EQ","transactionType":"BUY","quantity":1,"productType":"INTRADAY","orderType":"MARKET","validity":"DAY","price":0,"triggerPrice":0,"disclosedQuantity":0,"afterMarketOrder":false,"mktProtection":0,"tag":"T18-bridge-test"}}'
$live = Invoke-Curl -Url "http://127.0.0.1:$LocalPort/relay" -Method POST -JsonBody $liveBody
Write-Log ("LIVEPASS: {0}  {1}" -f $live.Status, $live.Body)

Write-Log "---- T18 Relay self-test end ----"
Write-Host "Self-test complete. Log: $LogFile"
