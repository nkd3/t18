# C:\T18\scripts\T18.SecurityId.ps1
# T18 — Dhan instruments CSV loader + symbol→securityId mapper + dhBody builders (Windows-native, PowerShell 5.1)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$T18_RefDir   = "C:\T18\data\ref"
$T18_CsvPath  = Join-Path $T18_RefDir "dhan_instruments.csv"
$T18_CacheDir = "C:\T18\data\cache"
$T18_Cache    = Join-Path $T18_CacheDir "dhan_instruments_cache.json"

New-Item -ItemType Directory -Force -Path $T18_RefDir, $T18_CacheDir | Out-Null

function Write-T18Log([string]$msg) {
  $ts = (Get-Date).ToString("s")
  Write-Host "$ts  $msg"
}

function Normalize-Header([string]$name) {
  ($name.ToLower() -replace '[^a-z0-9]', '_') -replace '_+', '_'
}

function Get-FirstDefined {
  param([hashtable]$Map, [string[]]$Keys, $Default = $null)
  foreach ($k in $Keys) {
    if ($Map.ContainsKey($k)) {
      $v = $Map[$k]
      if ($null -ne $v -and "$v".Trim() -ne "") { return $v }
    }
  }
  return $Default
}

function Normalize-Row($row) {
  $map = @{}
  foreach ($p in $row.PSObject.Properties) {
    $n = Normalize-Header $p.Name
    $map[$n] = $p.Value
  }

  $securityId      = Get-FirstDefined -Map $map -Keys @('securityid','security_id','secid')
  $symbol          = Get-FirstDefined -Map $map -Keys @('symbol','trading_symbol','scrip')
  $exchangeSegment = Get-FirstDefined -Map $map -Keys @('exchangesegment','exchange_segment','exchange')
  $instrument      = Get-FirstDefined -Map $map -Keys @('instrument','instrument_type','inst_type')
  $series          = Get-FirstDefined -Map $map -Keys @('series','segment_series')
  $underlying      = Get-FirstDefined -Map $map -Keys @('underlying','underlying_symbol')
  $expiry          = Get-FirstDefined -Map $map -Keys @('expiry','expiry_date','exp_date')
  $strike          = Get-FirstDefined -Map $map -Keys @('strike','strike_price')
  $optionType      = Get-FirstDefined -Map $map -Keys @('optiontype','option_type','opt_type')
  $lotSize         = Get-FirstDefined -Map $map -Keys @('lotsize','lot_size','mkt_lot')
  $tickSize        = Get-FirstDefined -Map $map -Keys @('ticksize','tick_size')
  $isin            = Get-FirstDefined -Map $map -Keys @('isin')

  $securityId = if ($securityId -ne $null -and "$securityId".Trim() -ne '') { [int]$securityId } else { $null }
  $lotSize    = if ($lotSize    -ne $null -and "$lotSize".Trim()    -ne '') { [int]$lotSize }    else { $null }

  [pscustomobject]@{
    securityId      = $securityId
    symbol          = if ($symbol)          { "$symbol".Trim().ToUpper() }          else { "" }
    exchangeSegment = if ($exchangeSegment) { "$exchangeSegment".Trim().ToUpper() } else { "" }
    instrument      = if ($instrument)      { "$instrument".Trim().ToUpper() }      else { "" }
    series          = if ($series)          { "$series".Trim().ToUpper() }          else { "" }
    underlying      = if ($underlying)      { "$underlying".Trim().ToUpper() }      else { "" }
    expiry          = if ($expiry)          { "$expiry".Trim() }                    else { "" }
    strike          = $strike
    optionType      = if ($optionType)      { "$optionType".Trim().ToUpper() }      else { "" }
    lotSize         = $lotSize
    tickSize        = $tickSize
    isin            = $isin
  }
}

function Import-DhanCsv {
  param([string]$Path = $T18_CsvPath)
  if (-not (Test-Path $Path)) {
    throw "Instruments CSV not found at '$Path'. Place the latest Dhan instruments CSV there."
  }
  Write-T18Log "Loading instruments CSV: $Path ..."
  $rows = Import-Csv -LiteralPath $Path
  $norm = foreach ($r in $rows) { Normalize-Row $r }
  Write-T18Log ("Loaded {0} rows" -f ($norm.Count))
  return ,$norm
}

function Save-Cache($rows) {
  $rows | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $T18_Cache -Encoding UTF8
  Write-T18Log "Cache written: $T18_Cache"
}

function Load-Cache {
  if (Test-Path $T18_Cache) {
    try {
      $data = Get-Content -LiteralPath $T18_Cache -Raw | ConvertFrom-Json
      if ($data) { return ,$data }
    } catch { }
  }
  return $null
}

function Get-T18InstrumentsCache {
  $cached = Load-Cache
  if ($cached) { return ,$cached }
  $rows = Import-DhanCsv
  Save-Cache $rows
  return ,$rows
}

function Find-T18SecurityId {
  param(
    [Parameter(Mandatory)] [string]$Symbol,
    [Parameter(Mandatory)] [ValidateSet('NSE','BSE','NSE_FNO')] [string]$ExchangeSegment,
    [string]$Instrument,
    [string]$Expiry,
    [Nullable[decimal]]$Strike,
    [ValidateSet('CE','PE','')] [string]$OptionType = ''
  )

  $rows = Get-T18InstrumentsCache

  $sym = $Symbol.ToUpper()
  $q = $rows | Where-Object {
    $_.exchangeSegment -eq $ExchangeSegment -and
    ( $_.symbol -eq $sym -or $_.underlying -eq $sym )
  }

  if ($Instrument) {
    $ins = $Instrument.ToUpper()
    $q = $q | Where-Object { $_.instrument -eq $ins }
  }

  if ($ExchangeSegment -in @('NSE','BSE')) {
    $hasEQ = $q | Where-Object { $_.series -eq 'EQ' }
    if ($hasEQ -and $hasEQ.Count -gt 0) { $q = $hasEQ }
  }

  function _NormDate([string]$d) {
    if ([string]::IsNullOrWhiteSpace($d)) { return '' }
    try { ([datetime]::Parse($d, [Globalization.CultureInfo]::InvariantCulture)).ToString('yyyy-MM-dd') } catch { $d }
  }

  if ($ExchangeSegment -eq 'NSE_FNO') {
    if ($Expiry) {
      $normExp = _NormDate $Expiry
      $q = $q | Where-Object { (_NormDate $_.expiry) -eq $normExp }
    }
    if ($Strike -ne $null) {
      $q = $q | Where-Object { (($_.strike) -as [decimal]) -eq $Strike }
    }
    if ($OptionType) {
      $opt = $OptionType.ToUpper()
      $q = $q | Where-Object { $_.optionType -eq $opt }
    }
  }

  $list = $q | Select-Object securityId,symbol,exchangeSegment,instrument,series,underlying,expiry,strike,optionType,lotSize,isin -Unique

  if (-not $list -or $list.Count -eq 0) {
    throw "No instrument found for Symbol='$Symbol', Segment='$ExchangeSegment' with the provided filters."
  }

  if ($list.Count -gt 1) {
    $uniq = $list | Group-Object securityId | Where-Object { $_.Count -eq 1 } | ForEach-Object { $_.Group }
    if ($uniq.Count -eq 1) { return $uniq[0] }

    Write-T18Log "Multiple matches (showing top 5):"
    $list | Select-Object -First 5 | Format-Table | Out-String | Write-Host
    throw "Ambiguous lookup. Refine inputs (Instrument/Expiry/Strike/OptionType)."
  }

  return $list[0]
}

function New-T18DhBody {
  param(
    [Parameter(Mandatory)] $InstrumentRow,
    [Parameter(Mandatory)] [ValidateSet('BUY','SELL')] [string]$TransactionType,
    [Parameter(Mandatory)] [int]$Quantity,
    [ValidateSet('INTRADAY','CNC','MARGIN','COVER','BRACKET','AMO','NRML')] [string]$ProductType = 'INTRADAY',
    [ValidateSet('MARKET','LIMIT','SL_MARKET','SL_LIMIT')] [string]$OrderType = 'MARKET',
    [Nullable[decimal]]$Price = $null,
    [string]$Validity = 'DAY',
    [int]$DisclosedQuantity = 0,
    [bool]$AfterMarketOrder = $false,
    [int]$MktProtection = 0,
    [string]$Tag = 'T18'
  )

  if ($InstrumentRow.exchangeSegment -eq 'NSE_FNO' -and $InstrumentRow.lotSize) {
    if ($Quantity % $InstrumentRow.lotSize -ne 0) {
      throw "Quantity $Quantity is not a multiple of lotSize $($InstrumentRow.lotSize)."
    }
  }

  $body = [ordered]@{
    securityId        = [int]$InstrumentRow.securityId
    exchangeSegment   = $InstrumentRow.exchangeSegment
    transactionType   = $TransactionType
    quantity          = $Quantity
    productType       = $ProductType
    orderType         = $OrderType
    validity          = $Validity
    disclosedQuantity = $DisclosedQuantity
    afterMarketOrder  = $AfterMarketOrder
    tag               = $Tag
  }

  if ($OrderType -eq 'LIMIT' -or $OrderType -eq 'SL_LIMIT') {
    if ($Price -eq $null) { throw "Price is required for LIMIT/SL_LIMIT orders." }
    $body['price'] = $Price
  } else {
    $body['mktProtection'] = $MktProtection
  }

  return @{ dhBody = $body }
}
