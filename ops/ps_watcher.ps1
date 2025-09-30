$ErrorActionPreference = "Stop"

# ===== CONFIG =====
$Root = "C:\T18"
$titleProp    = "Path"
$statusProp   = "Status"
$modifiedProp = "Modified"
$sizeProp     = "Size"
$activeVal    = "Active"
$deletedVal   = "deleted"

# Wildcard excludes (case-insensitive; no regex)
$ExcludePatterns = @(
  '*\_quarantine\*',
  '*\teevra18\data\parquet\*',
  '*\.git\*',
  '*\.venv\*',
  '*\.locks\*',
  '*\.streamlit\*',
  '*\logs\*'
)

# ===== ENV + HEADERS =====
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

# ===== LOG =====
$logDir = 'C:\T18\logs'; if(-not (Test-Path $logDir)){ New-Item -Type Directory $logDir | Out-Null }
$log = Join-Path $logDir 'ps_watcher.log'
function Log([string]$m){ ("[{0}] {1}" -f ((Get-Date).ToString('s')), $m) | Add-Content $log }

# ===== SINGLE INSTANCE LOCK =====
$lock = "C:\T18\.locks\ps_watcher_single.lock"
if(-not (Test-Path (Split-Path $lock))){ New-Item -Type Directory (Split-Path $lock) | Out-Null }
try{ $fs = [System.IO.File]::Open($lock,'OpenOrCreate','ReadWrite','None') } catch { Log "[ps_watcher] Another instance detected. Exiting."; exit 0 }

# ===== CACHE (Hashtable!) =====
$cacheDir  = "C:\T18\.cache"; if(-not (Test-Path $cacheDir)){ New-Item -Type Directory $cacheDir | Out-Null }
$cachePath = Join-Path $cacheDir "ps_watcher_index.json"
if(-not (Test-Path $cachePath)){ '{}' | Set-Content -Encoding UTF8 $cachePath }

function Load-Index {
  try {
    # PowerShell 7+: this returns a Hashtable directly
    $obj = (Get-Content -Raw -EA Stop $cachePath | ConvertFrom-Json -AsHashtable)
    if($null -eq $obj){ return @{} }
    return $obj
  } catch { return @{} }
}
function Save-Index($idx){ ($idx | ConvertTo-Json -Depth 5) | Set-Content -Encoding UTF8 $cachePath }
function Remember-PageId([string]$path,[string]$pageId){ $idx=Load-Index; $idx[$path]=$pageId; Save-Index $idx }
function Get-RememberedId([string]$path){ $idx=Load-Index; if($idx.ContainsKey($path)){ return [string]$idx[$path] } return $null }

# ===== HELPERS =====
function UtcNow(){ (Get-Date).ToUniversalTime().ToString('o') }
function Is-Excluded([string]$path){
  try{
    if([string]::IsNullOrWhiteSpace($path)){ return $false }
    $np = $path.ToLowerInvariant()
    if($np -like '*\logs\*'){ return $true }
    foreach($w in $ExcludePatterns){ if($np -ilike $w){ return $true } }
    return $false
  } catch { try{ Log ("EVENT ERROR (Is-Excluded): {0}" -f $_) } catch {}; return $false }
}

function Find-ByPathExact([string]$path, [int]$tries=6, [int]$sleepMs=600){
  for($i=0;$i -lt $tries;$i++){
    try{
      $b = @{ page_size=1; filter=@{ property=$titleProp; title=@{ equals=$path } } } | ConvertTo-Json -Depth 10
      $r = Invoke-RestMethod -Method Post -Uri "https://api.notion.com/v1/databases/$db/query" -Headers $headers -Body $b -EA Stop
      if($r.results.Count -gt 0){ return $r.results[0] }
    } catch { Start-Sleep -Milliseconds $sleepMs }
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

# ===== CORE =====
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
    try{
      $new = Invoke-RestMethod -Method Post -Uri "https://api.notion.com/v1/pages" -Headers $headers -Body $payload -EA Stop
      if($new -and $new.id){ $pageId=$new.id; Remember-PageId $path $pageId }
    } catch { Log ("NOTION POST ERROR (create active): {0}" -f $_) }
  } else {
    $patch = @{ properties=@{
      $statusProp   = @{ select=@{ name=$activeVal } }
      $sizeProp     = @{ number=$size }
      $modifiedProp = @{ date=@{ start=(UtcNow) } }
    }} | ConvertTo-Json -Depth 10
    try{
      Invoke-RestMethod -Method Patch -Uri ("https://api.notion.com/v1/pages/{0}" -f $pageId) -Headers $headers -Body $patch -EA Stop | Out-Null
    } catch { Log ("NOTION PATCH ERROR (update active): {0}" -f $_) }
  }
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
    } catch { Log ("NOTION PATCH ERROR (tombstone): {0}" -f $_) }
  }
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
  } catch { Log ("NOTION POST ERROR (tombstone upsert): {0}" -f $_) }
}

# ===== FSW =====
try { $fsw.EnableRaisingEvents = $false } catch {}
$fsw = New-Object IO.FileSystemWatcher $Root
$fsw.IncludeSubdirectories = $true
$fsw.Filter = '*'
$fsw.NotifyFilter = [IO.NotifyFilters]::FileName -bor [IO.NotifyFilters]::LastWrite -bor [IO.NotifyFilters]::Size
$fsw.InternalBufferSize = 65536

Register-ObjectEvent $fsw Created -SourceIdentifier 'FS-C' -Action {
  if (Test-Path $Event.SourceEventArgs.FullPath -PathType Container) { return }
  try{ $p=$Event.SourceEventArgs.FullPath; if(-not (Is-Excluded $p)){ Upsert-Active $p } }
  catch { Try{ Log ("EVENT ERROR (Created): {0}" -f $_) }Catch{} }
} | Out-Null
Register-ObjectEvent $fsw Changed -SourceIdentifier 'FS-U' -Action {
  if (Test-Path $Event.SourceEventArgs.FullPath -PathType Container) { return }
  try{ $p=$Event.SourceEventArgs.FullPath; if(-not (Is-Excluded $p)){ Upsert-Active $p } }
  catch { Try{ Log ("EVENT ERROR (Changed): {0}" -f $_) }Catch{} }
} | Out-Null
Register-ObjectEvent $fsw Deleted -SourceIdentifier 'FS-D' -Action {
  if (Test-Path $Event.SourceEventArgs.FullPath -PathType Container) { return }
  try{ $p=$Event.SourceEventArgs.FullPath; if(-not (Is-Excluded $p)){ Log ("DELETED: {0}" -f $p); Tombstone $p } }
  catch { Try{ Log ("EVENT ERROR (Deleted): {0}" -f $_) }Catch{} }
} | Out-Null
Register-ObjectEvent $fsw Renamed -SourceIdentifier 'FS-R' -Action {
  if (Test-Path $Event.SourceEventArgs.FullPath -PathType Container) { return }
  try{
    $old=$Event.SourceEventArgs.OldFullPath
    $new=$Event.SourceEventArgs.FullPath
    if(-not (Is-Excluded $old)){ Log ("RENAMED FROM: {0}" -f $old); Tombstone $old }
    if(-not (Is-Excluded $new)){ Log ("RENAMED TO:   {0}" -f $new); Upsert-Active $new }
  } catch { Try{ Log ("EVENT ERROR (Renamed): {0}" -f $_) }Catch{} }
} | Out-Null

$fsw.EnableRaisingEvents = $true
Log ("watcher CLEAN start {0}" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
while($true){ Start-Sleep 2 }
# === CACHE HOTFIX (forces Hashtable) ============================================
$cacheDir  = "C:\T18\.cache"; if(-not (Test-Path $cacheDir)){ New-Item -Type Directory $cacheDir | Out-Null }
$cachePath = Join-Path $cacheDir "ps_watcher_index.json"
if(-not (Test-Path $cachePath)){ '{}' | Set-Content -Encoding UTF8 $cachePath }

function ConvertTo-Hashtable([object]$obj){
  if($null -eq $obj){ return @{} }
  if($obj -is [System.Collections.IDictionary]){ return $obj }
  # Convert PSCustomObject -> Hashtable (shallow)
  $ht = @{}
  foreach($p in $obj.PSObject.Properties){ $ht[$p.Name] = $p.Value }
  return $ht
}

function Load-Index {
  try {
    $raw = Get-Content -Raw -EA Stop $cachePath
    $obj = ConvertFrom-Json $raw -AsHashtable  # pwsh7+: usually returns IDictionary
    return (ConvertTo-Hashtable $obj)
  } catch { return @{} }
}

function Save-Index($idx){
  if(-not ($idx -is [System.Collections.IDictionary])){ $idx = ConvertTo-Hashtable $idx }
  ($idx | ConvertTo-Json -Depth 5) | Set-Content -Encoding UTF8 $cachePath
}

function Remember-PageId([string]$path,[string]$pageId){
  $idx = Load-Index
  $idx[$path] = $pageId
  Save-Index $idx
}

function Get-RememberedId([string]$path){
  $idx = Load-Index
  if(($idx -is [System.Collections.IDictionary]) -and ($idx.ContainsKey($path) -or $idx.Contains($path))){
    return [string]$idx[$path]
  }
  return $null
}
try{ Log ("cache hotfix loaded") }catch{}
# === /CACHE HOTFIX =============================================================
# ===== CACHE HOTFIX (Hashtable-safe) ============================================
$cacheDir  = "C:\T18\.cache"; if(-not (Test-Path $cacheDir)){ New-Item -Type Directory $cacheDir | Out-Null }
$cachePath = Join-Path $cacheDir "ps_watcher_index.json"
if(-not (Test-Path $cachePath)){ '{}' | Set-Content -Encoding UTF8 $cachePath }

function ConvertTo-Hashtable([object]$obj){
  if($null -eq $obj){ return @{} }
  if($obj -is [System.Collections.IDictionary]){ return $obj }
  $ht = @{}
  foreach($p in $obj.PSObject.Properties){ $ht[$p.Name] = $p.Value }
  return $ht
}

function Load-Index {
  try {
    $raw = Get-Content -Raw -EA Stop $cachePath
    # In pwsh 7+, -AsHashtable usually gives IDictionary; still normalize:
    $obj = ConvertFrom-Json $raw -AsHashtable
    return (ConvertTo-Hashtable $obj)
  } catch { return @{} }
}

function Save-Index($idx){
  if(-not ($idx -is [System.Collections.IDictionary])){ $idx = ConvertTo-Hashtable $idx }
  ($idx | ConvertTo-Json -Depth 5) | Set-Content -Encoding UTF8 $cachePath
}

function Index-HasKey([object]$idx,[string]$key){
  if($idx -is [System.Collections.IDictionary]){ return $idx.ContainsKey($key) -or $idx.Contains($key) }
  if($idx -is [pscustomobject]){ return ($idx.PSObject.Properties.Name -contains $key) }
  return $false
}

function Remember-PageId([string]$path,[string]$pageId){
  $idx = Load-Index
  $idx[$path] = $pageId
  Save-Index $idx
}

function Get-RememberedId([string]$path){
  $idx = Load-Index
  if(Index-HasKey $idx $path){ return [string]$idx[$path] }
  return $null
}

try{ Log ("cache hotfix loaded") }catch{}
# ===== /CACHE HOTFIX ============================================================

