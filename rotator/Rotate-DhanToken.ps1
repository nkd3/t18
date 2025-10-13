param()
$ErrorActionPreference = 'Stop'

# --- Config & prep ---
$envPath   = "C:\T18\rotator\.env"
$logDir    = "C:\T18\logs\bridge"
$logFile   = Join-Path $logDir "token_rotation.log"
$secretDir = "C:\T18\secrets"
New-Item -ItemType Directory -Force -Path $logDir, $secretDir | Out-Null

# --- Load .env ---
$cfg = @{}
(Get-Content $envPath | Where-Object {$_ -match "="}) | ForEach-Object {
  $k,$v = $_ -split "=",2
  $cfg[$k.Trim()] = $v.Trim()
}

# Required app/auth settings
$dhanClientId = $cfg['DHAN_CLIENT_ID']
$appId        = $cfg['DHAN_API_KEY']
$appSecret    = $cfg['DHAN_API_SECRET']
$redirect     = $cfg['DHAN_REDIRECT_URL']      # e.g. https://65.20.67.164:444/dhan/callback

# Bridge push settings
$bridgeBase   = $cfg['T18_BRIDGE_BASE']        # e.g. https://t18-bridge.local
$certThumb    = $cfg['T18_CLIENT_CERT_THUMBPRINT']  # optional; overrides subject search
$certSubject  = $cfg['T18_CLIENT_CERT_SUBJ']   # e.g. CN=t18-client

if ([string]::IsNullOrWhiteSpace($dhanClientId)) {
  Add-Content $logFile ("[{0}] ERROR: DHAN_CLIENT_ID missing in .env" -f (Get-Date -Format 'u'))
  throw "Add DHAN_CLIENT_ID=<your numeric Dhan Client ID> to .env"
}
if ([string]::IsNullOrWhiteSpace($bridgeBase)) {
  $bridgeBase = "https://t18-bridge.local"
}

# Always use TLS1.2 on .NET 4.x
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# ---------- STEP 1: Generate consent (App flow) ----------
try {
  $genUri  = "https://auth.dhan.co/app/generate-consent?client_id=$dhanClientId"
  $headers = @{ "app_id" = $appId; "app_secret" = $appSecret }
  $genResp = Invoke-RestMethod -Uri $genUri -Method POST -Headers $headers
  $consentAppId = $genResp.consentAppId
  if (!$consentAppId) { throw "consentAppId missing" }
  Add-Content $logFile ("[{0}] consentAppId generated: {1}" -f (Get-Date -Format 'u'), $consentAppId)
} catch {
  Add-Content $logFile ("[{0}] ERROR: generate-consent failed: {1}" -f (Get-Date -Format 'u'), $_.Exception.Message)
  throw
}

# ---------- STEP 2: Open login and poll your VPS for tokenId ----------
$loginUrl = "https://auth.dhan.co/login/consentApp-login?consentAppId=$consentAppId"
Start-Process $loginUrl
Write-Host ">> Complete Dhan login + OTP in the browser..."

$pullUrl  = ($redirect -replace '/dhan/callback$','/token/pull')
$tokenId  = $null
$deadline = (Get-Date).AddMinutes(8)
while ((Get-Date) -lt $deadline) {
  try {
    $resp = Invoke-WebRequest -Uri $pullUrl -UseBasicParsing
    if ($resp.StatusCode -eq 200 -and $resp.Content.Trim().Length -gt 0) {
      $tokenId = $resp.Content.Trim()
      Add-Content $logFile ("[{0}] tokenId received: {1}" -f (Get-Date -Format 'u'), $tokenId)
      break
    }
  } catch {
    Add-Content $logFile ("[{0}] WARN: pull attempt failed: {1}" -f (Get-Date -Format 'u'), $_.Exception.Message)
  }
  Start-Sleep -Seconds 3
}
if (-not $tokenId) {
  Add-Content $logFile ("[{0}] ERROR: No tokenId pulled from VPS within 8 minutes timeout" -f (Get-Date -Format 'u'))
  throw "Timed out waiting for tokenId from VPS."
}

# ---------- STEP 3: Consume consent (GET variant that worked for you) ----------
try {
  $consumeUri = "https://auth.dhan.co/app/consumeApp-consent?tokenId=$([uri]::EscapeDataString($tokenId))"
  $headers    = @{ "app_id" = $appId; "app_secret" = $appSecret }
  $resp       = Invoke-RestMethod -Uri $consumeUri -Method GET -Headers $headers
  Add-Content $logFile ("[{0}] consume (GET) succeeded" -f (Get-Date -Format 'u'))
} catch {
  Add-Content $logFile ("[{0}] ERROR: consumeApp-consent failed: {1}" -f (Get-Date -Format 'u'), $_.Exception.Message)
  throw
}

$accessToken = $resp.accessToken
$expiry      = $resp.expiryTime   # IST per Dhan
if ([string]::IsNullOrWhiteSpace($accessToken)) {
  Add-Content $logFile ("[{0}] ERROR: accessToken missing after consume" -f (Get-Date -Format 'u'))
  throw "accessToken missing in response."
}

# ---------- STEP 4: Store locally (DPAPI) ----------
$secure = ConvertTo-SecureString $accessToken -AsPlainText -Force
$secure | ConvertFrom-SecureString | Out-File (Join-Path $secretDir "DHAN_ACCESS_TOKEN.dpapi")

# ---------- STEP 5: Push to bridge secret-store over mTLS ----------
# Find client cert (either pinned thumbprint or by subject)
if ([string]::IsNullOrWhiteSpace($certThumb)) {
  $cert = Get-ChildItem Cert:\CurrentUser\My |
    Where-Object { $_.Subject -like "*$certSubject*" -or $_.FriendlyName -eq "t18-client" } |
    Sort-Object NotAfter -Descending | Select-Object -First 1
  if (-not $cert) {
    Add-Content $logFile ("[{0}] ERROR: client cert not found (subject '{1}')" -f (Get-Date -Format 'u'), $certSubject)
    throw "Client certificate not found for mTLS push."
  }
  $certThumb = $cert.Thumbprint
}

$payload = @{
  accessToken = $accessToken
  expiry      = ([string]$expiry)
} | ConvertTo-Json

try {
  $pushUrl = "$bridgeBase/secret/update"
  $push = Invoke-WebRequest -Uri $pushUrl `
    -Method POST -ContentType 'application/json' -Body $payload `
    -UseBasicParsing -CertificateThumbprint $certThumb
  Add-Content $logFile ("[{0}] secret-store push OK" -f (Get-Date -Format 'u'))
} catch {
  Add-Content $logFile ("[{0}] ERROR: secret-store push failed: {1}" -f (Get-Date -Format 'u'), $_.Exception.Message)
  throw
}

# ---------- STEP 6: Log success ----------
$log = "[$(Get-Date -Format 'u')] New token fetched, expires (IST): $expiry"
Add-Content $logFile $log
Write-Host $log

# ---------- STEP 7: Backstop task 30 mins before expiry (IST) ----------
try {
  $expiryIST = [DateTime]::Parse($expiry)
  $tzIST   = [TimeZoneInfo]::FindSystemTimeZoneById("India Standard Time")
  $tzLocal = [TimeZoneInfo]::Local
  $expiryLocal = [TimeZoneInfo]::ConvertTime($expiryIST, $tzIST, $tzLocal)

  $runAtLocal = $expiryLocal.AddMinutes(-30)
  if ($runAtLocal -lt (Get-Date)) { $runAtLocal = (Get-Date).AddMinutes(5) }

  "$expiry" | Out-File (Join-Path $secretDir "DHAN_ACCESS_TOKEN.exp") -Encoding utf8

  # Clean old one-time tasks
  try {
    schtasks /Query /FO LIST /V | Select-String "T18-Dhan-Token-Backstop-" | ForEach-Object {
      if ($_ -match 'TaskName:\s+\\(T18-Dhan-Token-Backstop-[\d-]+)') {
        schtasks /Delete /TN $Matches[1] /F | Out-Null
      }
    }
  } catch { }

  $taskName  = "T18-Dhan-Token-Backstop-" + $runAtLocal.ToString('yyyyMMdd-HHmm')
  $startDate = $runAtLocal.ToString('MM/dd/yyyy')
  $startTime = $runAtLocal.ToString('HH:mm')
  $cmd = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\T18\rotator\Run-If-IST-0850.ps1"'

  schtasks /Create /TN $taskName /TR $cmd /SC ONCE /SD $startDate /ST $startTime /RL LIMITED /F | Out-Null
  Add-Content $logFile ("[{0}] Backstop scheduled at local {1} (IST expiry {2})" -f ((Get-Date).ToUniversalTime().ToString('u')), $runAtLocal, $expiryIST)
}
catch {
  Add-Content $logFile ("[{0}] WARN: Backstop scheduling failed: {1}" -f (Get-Date -Format 'u'), $_.Exception.Message)
}
