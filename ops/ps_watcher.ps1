$ErrorActionPreference = "Stop"

# ===== CONFIG =====
$Root = "C:\T18"
$ExcludePatterns = @(
  '*\_quarantine\*',
  '*\teevra18\data\parquet\*',
  '*\.git\*',
  '*\.venv\*',
  '*\.locks\*',
  '*\.streamlit\*',
  '*\logs\*'
)$titleProp    = "Path"
$statusProp   = "Status"
$modifiedProp = "Modified"
$sizeProp     = "Size"
$activeVal    = "Active"
$deletedVal   = "deleted"

# ===== ENV (prefer User, then Machine) =====
function Get-Env([string]$name){
  $u=[Environment]::GetEnvironmentVariable($name,'User')
  if([string]::IsNullOrWhiteSpace($u)){ return [Environment]::GetEnvironmentVariable($name,'Machine') }
  return $u
}
$token = Get-Env 'NOTION_TOKEN'
$db    = Get-Env 'NOTION_DATABASE_ID'
if(-not $token -or -not $db){ throw "NOTION_TOKEN / NOTION_DATABASE_ID missing" }
if($db -match '^[0-9a-fA-F]{32}$'){ $db = $db.Insert(20,'-').Insert(16,'-').Insert(12,'-').Insert(8,'-') }

$headers = @{
  Authorization    = "Bearer $token"
  "Notion-Version" = "2022-06-28"
  "Content-Type"   = "application/json"
}

# ===== LOGGING =====
$logDir = 'C:\T18\logs'
if(-not (Test-Path $logDir)){ New-Item -Type Directory $logDir | Out-Null }
$log = Join-Path $logDir 'ps_watcher.log'
function Log([string]$m){ ("[{0}] {1}" -f ((Get-Date).ToString('s')), $m) | Add-Content $log }

# ===== SINGLE INSTANCE LOCK =====
$lock = "C:\T18\.locks\ps_watcher_single.lock"
if(-not (Test-Path (Split-Path $lock))){ New-Item -Type Directory (Split-Path $lock) | Out-Null }
try{
  $fs = [System.IO.File]::Open($lock,'OpenOrCreate','ReadWrite','None')
} catch {
  Log "[ps_watcher] Another instance detected. Exiting."
  exit 0
}

# ===== SMALL PAGE-ID CACHE =====
$cacheDir  = "C:\T18\.cache"; if(-not (Test-Path $cacheDir)){ New-Item -Type Directory $cacheDir | Out-Null }
$cachePath = Join-Path $cacheDir "ps_watcher_index.json"
if(-not (Test-Path $cachePath)){ '{}' | Set-Content -Encoding UTF8 $cachePath }

function Load-Index { try { Get-Content -Raw -EA Stop $cachePath | ConvertFrom-Json } catch { @{} } }
function Save-Index($idx){ ($idx | ConvertTo-Json -Depth 5) | Set-Content -Encoding UTF8 $cachePath }
function Remember-PageId([string]$path,[string]$pageId){ $idx=Load-Index; $idx[$path]=$pageId; Save-Index $idx }
function Get-RememberedId([string]$path){ $idx=Load-Index; if($idx.ContainsKey($path)){ return [string]$idx[$path] } return $null }

# ===== HELPERS =====
function Is-Excluded([string]){
  if (-not ) { return $false }
  $np = .ToLower()
  if ($np -like '*\logs\*') { return $true }   # hard guard
  foreach ($w in $ExcludePatterns) {
    if ($np -ilike $w) { return $true }
  }
  return $false
}
  foreach($rx in $ExcludePatterns){ if($np -match $rx){ return $true } }
  return $false
}
function UtcNow(){ (Get-Date).ToUniversalTime().ToString('o') }

function Find-ByPathExact([string]$path, [int]$tries=6, [int]$sleepMs=600){
  for($i=0;$i -lt $tries;$i++){
    try{
      $b = @{ page_size=1; filter=@{ property=$titleProp; title=@{ equals=$path } } } | ConvertTo-Json -Depth 10
      $r = Invoke-RestMethod -Method Post -Uri "https://api.notion.com/v1/databases/$db/query" -Headers $headers -Body $b -EA Stop
      if($r.results.Count -gt 0){ return $r.results[0] }
    } catch {}
    Start-Sleep -Milliseconds $sleepMs
  }
  return $null
}

function Search-Anywhere([string]$path){
  try{
    $b = @{ query=$path; page_size=5; filter=@{ value="page"; property="object" } } | ConvertTo-Json -Depth 10
    $r = Invoke-RestMethod -Method Post -Uri "https://api.notion.com/v1/search" -Headers $headers -Body $b -EA Stop
    foreach($pg in $r.results){
      try{
        if($pg.parent.type -eq "database_id" -and $pg.parent.database_id -eq $db){
          $t = ($pg.properties.$titleProp.title.plain_text -join '')
          if($t -eq $path){ return $pg }
        }
      } catch {}
    }
  } catch {}
  return $null
}

function Add-PreviewBlock([string]$pageId, [string]$path){
  try{
    $text = (Get-Content -LiteralPath $path -Raw -EA Stop)
    if([string]::IsNullOrEmpty($text)){ return }
    if($text.Length -gt 1800){ $text = $text.Substring(0,1800) }
  } catch { return }
  $lang='plain text'
  if($path -match '\.ps1$'){ $lang='powershell' }
  elseif($path -match '\.py$'){ $lang='python' }
  elseif($path -match '\.cmd$'){ $lang='shell' }
  elseif($path -match '\.(json|ya?ml|toml)$'){ $lang='markup' }
  elseif($path -match '\.md$'){ $lang='markdown' }

  $payload = @{ children = @(@{
    object='block'; type='code'
    code=@{ language=$lang; rich_text=@(@{ type='text'; text=@{ content=$text }}) }
  }) } | ConvertTo-Json -Depth 10

  Invoke-RestMethod -Method Patch ("https://api.notion.com/v1/blocks/{0}/children" -f $pageId) -Headers $headers -Body $payload -EA SilentlyContinue | Out-Null
}

# ===== CORE SYNC =====
function Upsert-Active([string]$path){
  try{ $size = (Get-Item -EA Stop $path).Length } catch { return }
  $pageId = Get-RememberedId $path
  if(-not $pageId){
    $pg = Find-ByPathExact $path 5 500
    if(-not $pg){ $pg = Search-Anywhere $path }
    if($pg){ $pageId=$pg.id; Remember-PageId $path $pageId }
  }
  if(-not $pageId){
    $props = @{
      $titleProp    = @{ title=@(@{ text=@{ content=$path }}) }
      $statusProp   = @{ select=@{ name=$activeVal } }
      $sizeProp     = @{ number=$size }
      $modifiedProp = @{ date=@{ start=(UtcNow) } }
    }
    $payload = @{ parent=@{ database_id=$db }; properties=$props } | ConvertTo-Json -Depth 10
    $new = Invoke-RestMethod -Method Post -Uri "https://api.notion.com/v1/pages" -Headers $headers -Body $payload -EA SilentlyContinue
    if($new -and $new.id){ $pageId=$new.id; Remember-PageId $path $pageId }
  } else {
    $patch = @{ properties=@{
      $statusProp   = @{ select=@{ name=$activeVal } }
      $sizeProp     = @{ number=$size }
      $modifiedProp = @{ date=@{ start=(UtcNow) } }
    }} | ConvertTo-Json -Depth 10
    Invoke-RestMethod -Method Patch -Uri ("https://api.notion.com/v1/pages/{0}" -f $pageId) -Headers $headers -Body $patch -EA SilentlyContinue | Out-Null
  }
  if($pageId){ try{ Add-PreviewBlock $pageId $path } catch {} }
  Log ("SYNCED: {0} size={1}" -f $path,$size)
}

function Tombstone([string]$path){
  $pageId = Get-RememberedId $path
  if(-not $pageId){
    $pg = Find-ByPathExact $path 8 600
    if(-not $pg){ $pg = Search-Anywhere $path }
    if($pg){ $pageId=$pg.id; Remember-PageId $path $pageId }
  }
  if($pageId){
    $patch = @{ properties=@{
      $statusProp   = @{ select=@{ name=$deletedVal } }
      $sizeProp     = @{ number=0 }
      $modifiedProp = @{ date=@{ start=(UtcNow) } }
    }} | ConvertTo-Json -Depth 10
    try{
      Invoke-RestMethod -Method Patch -Uri ("https://api.notion.com/v1/pages/{0}" -f $pageId) -Headers $headers -Body $patch -EA Stop | Out-Null
      Log ("TOMBSTONED: {0}" -f $path)
      return
    } catch {
      Log ("DELETE PATCH FAILED: {0} :: {1}" -f $path, $_)
    }
  }
  # fallback: create deleted row so the UI is always correct
  $props = @{
    $titleProp    = @{ title=@(@{ text=@{ content=$path }}) }
    $statusProp   = @{ select=@{ name=$deletedVal } }
    $sizeProp     = @{ number=0 }
    $modifiedProp = @{ date=@{ start=(UtcNow) } }
  }
  try{
    $payload = @{ parent=@{ database_id=$db }; properties=$props } | ConvertTo-Json -Depth 10
    $new = Invoke-RestMethod -Method Post -Uri "https://api.notion.com/v1/pages" -Headers $headers -Body $payload -EA Stop
    if($new -and $new.id){ Remember-PageId $path $new.id }
    Log ("TOMBSTONE UPSERT: {0}" -f $path)
  } catch {
    Log ("DELETE TOMB (create failed): {0} :: {1}" -f $path, $_)
  }
}

# ===== EVENT WIRING (clean reset) =====
try {
  try { if($fsw){ $fsw.EnableRaisingEvents = $false } } catch {}

  $fsw = New-Object IO.FileSystemWatcher $Root
  $fsw.IncludeSubdirectories = $true
  $fsw.Filter = '*'
  $fsw.NotifyFilter = [IO.NotifyFilters]::FileName -bor [IO.NotifyFilters]::LastWrite -bor [IO.NotifyFilters]::Size
  $fsw.InternalBufferSize = 65536

  function __sz($p){ try { (Get-Item -EA SilentlyContinue $p).Length } catch { 0 } }

  Get-EventSubscriber -EA SilentlyContinue | Where-Object { $_.SourceObject -eq $fsw } | Unregister-Event -Force -EA SilentlyContinue

  $null = Register-ObjectEvent -InputObject $fsw -EventName Created -SourceIdentifier 'FS-C' -Action {
    $p = $Event.SourceEventArgs.FullPath
    if(-not (Is-Excluded $p)){ Log ("CREATED: {0} size={1}" -f $p, (__sz $p)); Upsert-Active $p }
  }
  $null = Register-ObjectEvent -InputObject $fsw -EventName Changed -SourceIdentifier 'FS-U' -Action {
    $p = $Event.SourceEventArgs.FullPath
    if(-not (Is-Excluded $p)){ Log ("UPDATED: {0} size={1}" -f $p, (__sz $p)); Upsert-Active $p }
  }
  $null = Register-ObjectEvent -InputObject $fsw -EventName Deleted -SourceIdentifier 'FS-D' -Action {
    $p = $Event.SourceEventArgs.FullPath
    if(-not (Is-Excluded $p)){ Log ("DELETED: {0}" -f $p); Tombstone $p }
  }
  $null = Register-ObjectEvent -InputObject $fsw -EventName Renamed -SourceIdentifier 'FS-R' -Action {
    $old = $Event.SourceEventArgs.OldFullPath
    $new = $Event.SourceEventArgs.FullPath
    if(-not (Is-Excluded $old)){ Log ("RENAMED FROM: {0}" -f $old); Tombstone $old }
    if(-not (Is-Excluded $new)){ Log ("RENAMED TO:   {0}" -f $new); Upsert-Active $new }
  }

  $fsw.EnableRaisingEvents = $true
  Log ("watching {0} ..." -f $Root)
} catch {
  Log ("FATAL (wiring): {0}" -f $_)
  throw
}

# Keep alive
while($true){ Start-Sleep 2 }
# ===== WATCHER (single-runspace, Wait-Event loop) =====
try { Unregister-Event -SourceIdentifier FS-C -ErrorAction SilentlyContinue } catch {}
try { Unregister-Event -SourceIdentifier FS-U -ErrorAction SilentlyContinue } catch {}
try { Unregister-Event -SourceIdentifier FS-D -ErrorAction SilentlyContinue } catch {}
try { Unregister-Event -SourceIdentifier FS-R -ErrorAction SilentlyContinue } catch {}

try { if($fsw){ $fsw.EnableRaisingEvents = $false } } catch {}

$fsw = New-Object IO.FileSystemWatcher $Root
$fsw.IncludeSubdirectories = $true
$fsw.Filter = '*'
$fsw.NotifyFilter = [IO.NotifyFilters]::FileName -bor [IO.NotifyFilters]::LastWrite -bor [IO.NotifyFilters]::Size
$fsw.InternalBufferSize = 65536

# Register WITHOUT -Action; we’ll process via Wait-Event so we stay in this runspace
$null = Register-ObjectEvent -InputObject $fsw -EventName Created -SourceIdentifier 'FS-C'
$null = Register-ObjectEvent -InputObject $fsw -EventName Changed -SourceIdentifier 'FS-U'
$null = Register-ObjectEvent -InputObject $fsw -EventName Deleted -SourceIdentifier 'FS-D'
$null = Register-ObjectEvent -InputObject $fsw -EventName Renamed -SourceIdentifier 'FS-R'

$fsw.EnableRaisingEvents = $true
Log ("watching {0} ..." -f $Root)

while($true){
  $e = Wait-Event -Timeout 2
  if(-not $e){ continue }
  try{
    switch($e.SourceIdentifier){
      'FS-C' {
        $p = $e.SourceEventArgs.FullPath
        if(-not (Is-Excluded $p)){
          $sz = 0; try{ $sz = (Get-Item -EA SilentlyContinue $p).Length } catch {}
          Log ("CREATED: {0} size={1}" -f $p,$sz)
          Upsert-Active $p
        }
      }
      'FS-U' {
        $p = $e.SourceEventArgs.FullPath
        if(-not (Is-Excluded $p)){
          $sz = 0; try{ $sz = (Get-Item -EA SilentlyContinue $p).Length } catch {}
          Log ("UPDATED: {0} size={1}" -f $p,$sz)
          Upsert-Active $p
        }
      }
      'FS-D' {
        $p = $e.SourceEventArgs.FullPath
        if(-not (Is-Excluded $p)){
          Log ("DELETED: {0}" -f $p)
          Tombstone $p
        }
      }
      'FS-R' {
        $old = $e.SourceEventArgs.OldFullPath
        $new = $e.SourceEventArgs.FullPath
        if(-not (Is-Excluded $old)){ Log ("RENAMED FROM: {0}" -f $old); Tombstone $old }
        if(-not (Is-Excluded $new)){
          $sz = 0; try{ $sz = (Get-Item -EA SilentlyContinue $new).Length } catch {}
          Log ("RENAMED TO:   {0} size={1}" -f $new,$sz)
          Upsert-Active $new
        }
      }
    }
  } catch {
    Log ("EVENT ERROR: {0}" -f $_)
  } finally {
    Remove-Event -EventIdentifier $e.EventIdentifier -ErrorAction SilentlyContinue
  }
}


