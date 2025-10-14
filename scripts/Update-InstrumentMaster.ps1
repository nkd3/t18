# ======================================================================
#  C:\T18\scripts\Update-InstrumentMaster.ps1
#  Refreshes Dhan instrument master file daily (SEBI-compliant workflow)
#  - Atomic replace to avoid file locks
#  - Retries on transient errors
#  - Logs every run to update_instrument_master.log
#  - Optionally triggers Build-InstrumentMap task after success
# ======================================================================

$ProgressPreference = 'SilentlyContinue'
$root = $env:T18Root; if (-not $root) { $root = 'C:\T18' }
$data = Join-Path $root 'data'
$log  = Join-Path $data 'logs'

$uri  = 'https://images.dhan.co/api-data/api-scrip-master.csv'
$dst  = Join-Path $data 'api-scrip-master.csv'
$tmp  = Join-Path $data 'api-scrip-master.tmp'
$bak  = Join-Path $data ("api-scrip-master_{0:yyyyMMdd_HHmmss}.csv" -f (Get-Date))

# --- Ensure folders exist ---
New-Item -Force -Type Directory $data,$log | Out-Null

# --- Backup current file ---
if (Test-Path $dst) { Copy-Item $dst $bak -Force }

# --- Attempt download with retry & atomic swap ---
$max = 5
$ok  = $false
for ($i = 1; $i -le $max -and -not $ok; $i++) {
    try {
        Invoke-WebRequest -Uri $uri -OutFile $tmp -UseBasicParsing -TimeoutSec 60
        Move-Item $tmp $dst -Force  # atomic replace avoids lock contention
        "`tOK  $(Get-Date -Format s)  updated $dst" |
            Tee-Object -FilePath (Join-Path $log 'update_instrument_master.log') -Append
        $ok = $true
    }
    catch {
        "`tERR $(Get-Date -Format s)  $($_.Exception.Message)" |
            Tee-Object -FilePath (Join-Path $log 'update_instrument_master.log') -Append
        Start-Sleep -Seconds (3 * $i)  # exponential backoff
    }
}

# --- Rollback if all retries failed ---
if (-not $ok -and (Test-Path $bak)) {
    Copy-Item $bak $dst -Force
    "`tROLLBACK $(Get-Date -Format s)  restored $dst from backup" |
        Tee-Object -FilePath (Join-Path $log 'update_instrument_master.log') -Append
    exit 1
}

# --- Optional: trigger map rebuild when update succeeds ---
if ($ok) {
    Start-Sleep -Seconds 5
    schtasks /Run /TN "T18_BuildInstrumentMap" | Out-Null
}

# ======================================================================
#  End of script
# ======================================================================
