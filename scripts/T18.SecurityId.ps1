# C:\T18\scripts\T18.SecurityId.ps1
# T18 — Dhan instruments CSV loader + symbol→securityId mapper (PowerShell 5.1)
# Uses Dhan headers:
#   SEM_EXM_EXCH_ID, SEM_SEGMENT, SEM_SMST_SECURITY_ID, SEM_INSTRUMENT_NAME,
#   SEM_TRADING_SYMBOL, SEM_SERIES, SM_SYMBOL_NAME, SEM_EXPIRY_DATE,
#   SEM_STRIKE_PRICE, SEM_OPTION_TYPE, SEM_LOT_UNITS, SEM_EXCH_INSTRUMENT_TYPE

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

function _NormStr($x) { if ($null -eq $x) { "" } else { "$x".Trim() } }
function _Upper($x)   { $s = _NormStr $x; if ($s -ne "") { $s.ToUpper() } else { "" } }

function _MapExchangeSegment([string]$exch, [string]$seg) {
  $e = _Upper $exch
  $s = _Upper $seg
  if ($e -eq 'NSE' -and $s -eq 'EQ') { return 'NSE' }
  if ($e -eq 'BSE' -and $s -eq 'EQ') { return 'BSE' }
  if ($e -eq 'NSE' -and ($s -match 'FNO|FO|DERIV')) { return 'NSE_FNO' }
  return $e
}

function Normalize-Row($r) {
  # pull by EXACT header names
  $exch         = _NormStr $r.'SEM_EXM_EXCH_ID'
  $segment      = _NormStr $r.'SEM_SEGMENT'
  $securityId   = _NormStr $r.'SEM_SMST_SECURITY_ID'
  $instrName    = _NormStr $r.'SEM_INSTRUMENT_NAME'
  $tradingSym   = _NormStr $r.'SEM_TRADING_SYMBOL'
  $series       = _NormStr $r.'SEM_SERIES'
  $smName       = _NormStr $r.'SM_SYMBOL_NAME'
  $expiry       = _NormStr $r.'SEM_EXPIRY_DATE'
  $strike       = _NormStr $r.'SEM_STRIKE_PRICE'
  $optType      = _Upper   $r.'SEM_OPTION_TYPE'
  $lotUnits     = _NormStr $r.'SEM_LOT_UNITS'
  $exchInstr    = _NormStr $r.'SEM_EXCH_INSTRUMENT_TYPE'

  $exchangeOut  = _MapExchangeSegment $exch $segment

  # symbol preference: SM_SYMBOL_NAME (readable) else SEM_TRADING_SYMBOL
  $symbol = if ($smName -ne "") { _Upper $smName } else { _Upper $tradingSym }

  $underlying = ""
  if ($tradingSym -ne "" -and $tradingSym.Contains('-')) {
    $underlying = _Upper ($tradingSym.Split('-')[0])
  }

  $secId = $null
  if ($securityId -ne "") { try { $secId = [int]$securityId } catch {} }

  $lot = $null
  if ($lotUnits -ne "") { try { $lot = [int]([double]$lotUnits) } catch {} }

  [pscustomobject]@{
    securityId      = $secId
    symbol          = $symbol
    underlying      = $underlying
    exchangeSegment = $exchangeOut
    instrument      = _Upper $instrName
    series          = _Upper $series
    expiry          = $expiry
    strike          = $strike
    optionType      = $optType
    lotSize         = $lot
    raw = [pscustomobject]@{
      exch_id   = $exch
      segment   = $segment
      trade_sym = $tradingSym
      exch_instr= $exchInstr
    }
  }
}

function Import-DhanCsv {
  param([string]$Path = $T18_CsvPath)
  if (-not (Test-Path $Path)) {
    throw "Instruments CSV not found at '$Path'."
  }
  Write-T18Log "Loading instruments CSV: $Path ..."
  $rows = Import-Csv -LiteralPath $Path
  $out  = foreach ($r in $rows) { Normalize-Row $r }
  Write-T18Log ("Loaded {0} rows" -f ($out.Count))
  return ,$out
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
  $sym  = $Symbol.ToUpper()

  $q = $rows | Where-Object {
    $_.exchangeSegment -eq $ExchangeSegment -and
    ( $_.symbol -eq $sym -or $_.underlying -eq $sym )
  }

  if ($ExchangeSegment -in @('NSE','BSE')) {
    $eq = $q | Where-Object { $_.series -eq 'EQ' }
    if ($eq -and $eq.Count -gt 0) { $q = $eq }
    if ($Instrument) {
      $ins = $Instrument.ToUpper()
      $q = $q | Where-Object { $_.instrument -eq $ins -or [string]::IsNullOrWhiteSpace($_.instrument) }
    }
  }

  function _NormDate([string]$d) {
    if ([string]::IsNullOrWhiteSpace($d)) { return '' }
    try { ([datetime]::Parse($d, [Globalization.CultureInfo]::InvariantCulture)).ToString('yyyy-MM-dd') } catch { $d }
  }

  if ($ExchangeSegment -eq 'NSE_FNO') {
    if ($Instrument) {
      $ins = $Instrument.ToUpper()
      $q = $q | Where-Object { $_.instrument -eq $ins }
    }
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

  $list = $q | Select-Object securityId,symbol,exchangeSegment,instrument,series,underlying,expiry,strike,optionType,lotSize,raw -Unique

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
