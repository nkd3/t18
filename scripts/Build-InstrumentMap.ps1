# C:\T18\scripts\Build-InstrumentMap.ps1
$root = $env:T18Root; if (-not $root) { $root = 'C:\T18' }
$data = Join-Path $root 'data'
$src  = Join-Path $data 'api-scrip-master.csv'
$csv  = Import-Csv $src

# ---- Your core universe (edit anytime) ----
$Universe = @('NIFTY','BANKNIFTY','RELIANCE','INFY')

$map = $csv | Where-Object { $_.SEM_TRADING_SYMBOL -in $Universe -and $_.SEM_SEGMENT -in 'I','E' } |
  Select-Object @{n='TradingSymbol';e={$_.SEM_TRADING_SYMBOL}},
                 @{n='SecurityId';e={$_.SEM_SMST_SECURITY_ID}},
                 @{n='Segment';e={$_.SEM_SEGMENT}},
                 @{n='InstrType';e={$_.SEM_EXCH_INSTRUMENT_TYPE}},
                 @{n='Series';e={$_.SEM_SERIES}},
                 SEM_OPTION_TYPE, SEM_STRIKE_PRICE, SEM_EXPIRY_DATE |
  Sort-Object TradingSymbol, Segment, InstrType, SEM_EXPIRY_DATE, SEM_STRIKE_PRICE

$map | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $data 'securityid_map_t18.csv')
$map | ConvertTo-Json | Out-File -Encoding UTF8 (Join-Path $data 'instrument_map_t18.json')
Write-Host "Instrument maps updated in C:\T18\data"
