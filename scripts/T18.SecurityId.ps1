# C:\T18\scripts\T18.SecurityId.ps1
# T18 — Dhan instruments CSV loader + symbol→securityId mapper + dhBody builders (Windows-native)
# - Reads C:\T18\data\ref\dhan_instruments.csv
# - Normalizes header names so it tolerates slight CSV variations
# - Looks up securityId for NSE cash & F&O
# - Builds Dhan-compliant dhBody (we'll post via relay in the next step)

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
  # Lowercase, keep letters/digits, convert others to underscore, collapse repeats
  ($name.ToLower() -replace '[^a-z0-9]', '_') -replace '_+', '_'
}

function Normalize-Row($row) {
  # Map flexible headers to canonical names if present
  $map = @{}
  foreach ($p in $row.PSObject.Properties) {
    $n = Normalize-Header $p.Name
    $map[$n] = $p.Value
  }

  # Canonical fields (best-effort from common Dhan dumps)
  [pscustomobject]@{
    securityId        = ($map['securityid']           ?? $map['security_id']          ?? $map['secid']         ?? $null) -as [int]
    symbol            = ($map['symbol']               ?? $map['trading_symbol']       ?? $map['scrip']         ?? '').ToString().Trim()
    exchangeSegment   = ($map['exchangesegment']      ?? $map['exchange_segment']     ?? $map['exchange']      ?? '').ToString().Trim().ToUpper()
    instrument        = ($map['instrument']           ?? $map['instrument_type']      ?? $map['inst_type']     ?? '').ToString().Trim().ToUpper()
    series            = ($map['series']               ?? $map['segment_series']       ?? '').ToString().Trim().ToUpper()
    underlying        = ($map['underlying']           ?? $map['underlying_symbol']    ?? '').ToString().Trim().ToUpper()
    expiry            = ($map['expiry']               ?? $map['expiry_date']          ?? $map['exp_date']      ?? '').ToString().Trim()
    strike            = ($map['strike']               ?? $map['strike_price']         ?? $null)
    optionType        = ($map['optiontype']           ?? $map['option_type']          ?? $map['opt_type']      ?? '').ToString().Trim().ToUpper()
    lotSize           = ($map['lotsize']              ?? $map['lot_size']             ?? $map['mkt_lot']       ?? $null) -as [int]
    tickSize          = ($map['ticksize']             ?? $map['tick_size']            ?? $null)
    isin              = ($map['isin']                 ?? $null)
  }
}

function Import-DhanCsv {
  param(
    [string]$Path = $T18_CsvPath
  )
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
  # Returns cached list; if missing/stale, builds from CSV
  $cached = Load-Cache
  if ($cached) { return ,$cached }

  $rows = Import-DhanCsv
  Save-Cache $rows
  return ,$rows
}

function Find-T18SecurityId {
  <#
    .SYNOPSIS
      Resolve securityId for NSE cash or NSE_FNO instruments.

    .PARAMETER Symbol
      Trading symbol, e.g., RELIANCE, SBIN, NIFTY, BANKNIFTY.

    .PARAMETER ExchangeSegment
      "NSE" | "BSE" | "NSE_FNO"

    .PARAMETER Instrument
      Optional hint, e.g., "EQUITY","FUTSTK","OPTSTK","FUTIDX","OPTIDX".

    .PARAMETER Expiry
      For F&O (yyyy-mm-dd or dd-mm-yyyy accepted).

    .PARAMETER Strike
      For options.

    .PARAMETER OptionType
      "CE" | "PE" for options.
  #>
  param(
    [Parameter(Mandatory)] [string]$Symbol,
    [Parameter(Mandatory)] [ValidateSet('NSE','BSE','NSE_FNO')] [string]$ExchangeSegment,
    [string]$Instrument,
    [string]$Expiry,
    [Nullable[decimal]]$Strike,
    [ValidateSet('CE','PE','')] [string]$OptionType = ''
  )

  $rows = Get-T18InstrumentsCache

  $q = $rows | Where-Object {
    $_.exchangeSegment -eq $ExchangeSegment -and
    ($_.symbol   -eq $Symbol.ToUpper() -or $_.underlying -eq $Symbol.ToUpper())
  }

  if ($Instrument) {
    $q = $q | Where-Object { $_.instrument -eq $Instrument.ToUpper() }
  }

  # Basic series preference for cash
  if ($ExchangeSegment -in @('NSE','BSE')) {
    $q = $q | Where-Object {
      # Prefer series EQ if present; otherwise allow empty/other
      if ($_.series) { $_.series -eq 'EQ' } else { $true }
    }
  }

  # Normalize expiry formats to yyyy-mm-dd when present
  function _NormDate([string]$d) {
    if (-not $d) { return '' }
    try {
      # Accept common formats
      $dt = [datetime]::Parse($d, [Globalization.CultureInfo]::InvariantCulture)
      return $dt.ToString('yyyy-MM-dd')
    } catch {
      return $d
    }
  }

  if ($ExchangeSegment -eq 'NSE_FNO') {
    if ($Expiry) {
      $normExp = _NormDate $Expiry
      $q = $q | Where-Object {
        (_NormDate $_.expiry) -eq $normExp
      }
    }
    if ($Strike -ne $null) {
      $q = $q | Where-Object { ($_.strike -as [decimal]) -eq $Strike }
    }
    if ($OptionType) {
      $q = $q | Where-Object { $_.optionType -eq $OptionType.ToUpper() }
    }
  }

  $list = $q | Select-Object securityId,symbol,exchangeSegment,instrument,series,underlying,expiry,strike,optionType,lotSize,isin -Unique

  if (-not $list -or $list.Count -eq 0) {
    throw "No instrument found for Symbol='$Symbol', Segment='$ExchangeSegment' with the provided filters."
  }

  if ($list.Count -gt 1) {
    # Try to auto-resolve common duplicates (e.g., multiple rows with same fields)
    $uniqueById = $list | Group-Object securityId | Where-Object { $_.Count -eq 1 } | ForEach-Object { $_.Group }
    if ($uniqueById.Count -eq 1) { return $uniqueById[0] }

    # If still multiple, return the top few to help the caller choose
    Write-T18Log "Multiple matches (showing top 5):"
    $list | Select-Object -First 5 | Format-Table | Out-String | Write-Host
    throw "Ambiguous lookup. Refine inputs (Instrument/Expiry/Strike/OptionType)."
  }

  return $list[0]
}

function New-T18DhBody {
  <#
    .SYNOPSIS
      Build a Dhan-compliant dhBody from a resolved instrument row.

    .PARAMETER InstrumentRow
      Object returned by Find-T18SecurityId.

    .PARAMETER TransactionType
      "BUY" | "SELL"

    .PARAMETER Quantity
      For cash: shares. For F&O: raw quantity (we validate lot multiple if lotSize present).

    .PARAMETER ProductType
      "INTRADAY" | "CNC" | "MARGIN" | "COVER" | etc.

    .PARAMETER OrderType
      "MARKET" | "LIMIT" | etc.

    .PARAMETER Price
      Required for LIMIT/SL-LIMIT.

    .PARAMETER Validity
      default "DAY"
  #>
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

  # Lot multiple validation for derivatives
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
    # MARKET or SL_MARKET → Dhan ignores price; include mktProtection if you use it
    $body['mktProtection'] = $MktProtection
  }

  return @{ dhBody = $body }
}

Export-ModuleMember -Function `
  Import-DhanCsv, Get-T18InstrumentsCache, Find-T18SecurityId, New-T18DhBody
