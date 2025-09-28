$ErrorActionPreference = "Stop"

# ===== CONFIG =====
$Root = "C:\T18"
$ExcludePatterns = @('\_quarantine_', '\teevra18\data\parquet\', '\.git\', '\.venv\', '\.locks\', '\.streamlit\', '\logs\')

# Notion config (env-driven; title prop is Path per your DB)
$token = [Environment]::GetEnvironmentVariable("NOTION_TOKEN","User")
$db    = [Environment]::GetEnvironmentVariable("NOTION_DATABASE_ID","User")
if(!$token -or !$db){ throw "NOTION_TOKEN / NOTION_DATABASE_ID missing (User scope)" }
if($db -match "^[0-9a-fA-F]{32}$"){ $db = $db.Insert(20,"-").Insert(16,"-").Insert(12,"-").Insert(8,"-") }

$titleProp    = ([Environment]::GetEnvironmentVariable("NOTION_TITLE_PROP","User"));    if(!$titleProp){    $titleProp="Path" }
$gitTracked   = ([Environment]::GetEnvironmentVariable("NOTION_PROP_GITTRACKED","User"));if(!$gitTracked){  $gitTracked="Git Tracked" }
$modifiedProp = ([Environment]::GetEnvironmentVariable("NOTION_PROP_MODIFIED","User"));  if(!$modifiedProp){ $modifiedProp="Modified" }
$sizeProp     = ([Environment]::GetEnvironmentVariable("NOTION_PROP_SIZE","User"));      if(!$sizeProp){     $sizeProp="Size" }
$statusProp   = ([Environment]::GetEnvironmentVariable("NOTION_PROP_STATUS","User"));    if(!$statusProp){   $statusProp="Status" }
$activeVal    = ([Environment]::GetEnvironmentVariable("NOTION_STATUS_VALUE","User"));   if(!$activeVal){    $activeVal="Active" }
$deletedVal   = "deleted"

$headers = @{
  Authorization    = "Bearer $token"
  "Notion-Version" = "2022-06-28"
  "Content-Type"   = "application/json"
}

# ===== LOGGING =====
$logDir = Join-Path $Root "logs"
if(!(Test-Path $logDir)){ New-Item -Type Directory $logDir | Out-Null }
$log    = Join-Path $logDir "ps_watcher.log"
function Log([string]$msg){ "[{0}] {1}" -f ((Get-Date).ToString("s")), $msg | Add-Content -Path $log }

# ===== HELPERS =====
function Is-Excluded([string]$path){
  $p = $path.ToLower()
  foreach($pat in $ExcludePatterns){
    if($p -like "*$pat*".ToLower()){ return $true }
  }
  return $false
}

function _utc(){ (Get-Date).ToUniversalTime().ToString("o") }   # ISO8601Z

function Find-PageByTitle([string]$title){
  $body = @{
    page_size = 1
    filter    = @{ property=$titleProp; title=@{ equals=$title } }
  } | ConvertTo-Json -Depth 10
  (Invoke-RestMethod -Method Post -Uri "https://api.notion.com/v1/databases/$db/query" -Headers $headers -Body $body -EA Stop).results
}

function Ensure-Page([string]$title){
  $r = Find-PageByTitle $title
  if($r.Count -gt 0){ return $r[0].id }
  $payload = @{
    parent     = @{ database_id = $db }
    properties = @{
      $titleProp    = @{ title   = @(@{ text=@{ content=$title }}) }
      $statusProp   = @{ select  = @{ name=$activeVal } }
      $gitTracked   = @{ checkbox = $false }
      $sizeProp     = @{ number  = 0 }
      $modifiedProp = @{ date    = @{ start = (_utc) } }
    }
  } | ConvertTo-Json -Depth 10
  $resp = Invoke-RestMethod -Method Post -Uri "https://api.notion.com/v1/pages" -Headers $headers -Body $payload -EA Stop
  return $resp.id
}

function Update-Props([string]$pageId, [hashtable]$props){
  $patch = @{ properties = $props } | ConvertTo-Json -Depth 10
  Invoke-RestMethod -Method Patch -Uri ("https://api.notion.com/v1/pages/{0}" -f $pageId) -Headers $headers -Body $patch -EA Stop | Out-Null
}

function Add-PreviewBlock([string]$pageId, [string]$path){
  # Only try for small-ish text files
  try{
    if(!(Test-Path -LiteralPath $path)){ return }
    $fi = Get-Item -LiteralPath $path -EA Stop
    if($fi.Length -gt 524288){ return }  # >512 KB: skip preview
    $text = Get-Content -LiteralPath $path -Raw -EA Stop
    if(!$text){ return }
    if($text.Length -gt 1800){ $text = $text.Substring(0,1800) }
  } catch { return }

  $lang = "plain text"
  switch -regex ($path){
    ".*\.ps1$"                  { $lang = "powershell" }
    ".*\.py$"                   { $lang = "python" }
    ".*\.cmd$"                  { $lang = "shell" }
    ".*\.(json|yml|yaml|toml)$" { $lang = "markup" }
    ".*\.md$"                   { $lang = "markdown" }
    ".*\.(txt|log)$"            { $lang = "plain text" }
  }

  $payload = @{
    children = @(@{
      object = "block"
      type   = "code"
      code   = @{
        language  = $lang
        rich_text = @(@{ type="text"; text=@{ content=$text } })
      }
    })
  } | ConvertTo-Json -Depth 10

  Invoke-RestMethod -Method Patch `
    -Uri ("https://api.notion.com/v1/blocks/{0}/children" -f $pageId) `
    -Headers $headers -Body $payload -EA SilentlyContinue | Out-Null
}

function Sync-File([string]$path){
  if(Is-Excluded $path){ return }
  try{
    if(!(Test-Path -LiteralPath $path)){ return } # file may have vanished
    $size = (Get-Item -LiteralPath $path -EA Stop).Length
  } catch { $size = 0 }

  $pageId = Ensure-Page $path

  # Update basic props
  $props = @{
    $titleProp    = @{ title = @(@{ text=@{ content=$path }}) }
    $statusProp   = @{ select = @{ name=$activeVal } }
    $sizeProp     = @{ number = [double]$size }
    $modifiedProp = @{ date   = @{ start = (_utc) } }
  }
  Update-Props $pageId $props

  # Add/refresh preview block for text-like files
  if($path -match "\.(txt|md|log|ps1|py|cmd|bat|json|yml|yaml|toml)$"){
    Add-PreviewBlock $pageId $path
  }

  Log ("SYNCED: {0} size={1}" -f $path, $size)
}

function Mark-Deleted([string]$title){
  if(Is-Excluded $title){ return }
  $r = Find-PageByTitle $title
  if($r.Count -gt 0){
    $pageId = $r[0].id  # DO NOT name this $PID (PowerShell reserved)
    $props = @{
      $titleProp    = @{ title = @(@{ text=@{ content=$title }}) }
      $statusProp   = @{ select = @{ name=$deletedVal } }
      $modifiedProp = @{ date   = @{ start = (_utc) } }
      $sizeProp     = @{ number = 0 }
    }
    Update-Props $pageId $props
    Log ("MARKED DELETED: {0}" -f $title)
  } else {
    Log ("DELETE TOMB?: row not found for {0}" -f $title)
  }
}

# ===== FILESYSTEM WATCHER =====
try{ $fsw.EnableRaisingEvents = $false } catch {}

$fsw = New-Object IO.FileSystemWatcher $Root
$fsw.IncludeSubdirectories = $true
$fsw.Filter = "*"
$fsw.NotifyFilter = [IO.NotifyFilters]::FileName -bor `
                    [IO.NotifyFilters]::LastWrite -bor `
                    [IO.NotifyFilters]::Size
$fsw.InternalBufferSize = 65536

# small debounce for noisy editors
$last = @{}  # path -> ticks
function _bounce([string]$p){
  $now = [DateTime]::UtcNow.Ticks
  if($last.ContainsKey($p)){
    if(($now - $last[$p]) -lt [TimeSpan]::FromMilliseconds(1500).Ticks){ return $true }
    $last[$p] = $now; return $false
  } else { $last[$p] = $now; return $false }
}

# Events
$null = Register-ObjectEvent -InputObject $fsw -EventName Created -SourceIdentifier "FS-C" -Action {
  $p = $Event.SourceEventArgs.FullPath
  if(!(Is-Excluded $p)){ Log ("CREATED: {0} size={1}" -f $p, (Get-Item -EA SilentlyContinue $p).Length); Sync-File $p }
}
$null = Register-ObjectEvent -InputObject $fsw -EventName Changed -SourceIdentifier "FS-U" -Action {
  $p = $Event.SourceEventArgs.FullPath
  if(!(Is-Excluded $p) -and -not (_bounce $p)){ Log ("UPDATED: {0} size={1}" -f $p, (Get-Item -EA SilentlyContinue $p).Length); Sync-File $p }
}
$null = Register-ObjectEvent -InputObject $fsw -EventName Deleted -SourceIdentifier "FS-D" -Action {
  $p = $Event.SourceEventArgs.FullPath
  if(!(Is-Excluded $p)){ Log ("DELETED: {0}" -f $p); Mark-Deleted $p }
}
$null = Register-ObjectEvent -InputObject $fsw -EventName Renamed -SourceIdentifier "FS-R" -Action {
  $old = $Event.SourceEventArgs.OldFullPath
  $new = $Event.SourceEventArgs.FullPath
  if(!(Is-Excluded $old)){ Log ("RENAMED FROM: {0}" -f $old); Mark-Deleted $old }
  if(!(Is-Excluded $new)){ Log ("RENAMED TO:   {0}" -f $new);  Sync-File  $new }
}

$fsw.EnableRaisingEvents = $true
Log ("watching {0} ..." -f $Root)

# keep alive
while($true){ Wait-Event -Timeout 2 | Out-Null }

# === ENSURE FSW EVENTS (create/update/delete/rename) ===========================
try { $fsw.EnableRaisingEvents = $false } catch {}
try {
  if(-not $fsw){
    $fsw = New-Object IO.FileSystemWatcher 'C:\T18'
    $fsw.IncludeSubdirectories = $true
    $fsw.Filter = '*'
    $fsw.NotifyFilter = [IO.NotifyFilters]::FileName -bor `
                        [IO.NotifyFilters]::LastWrite -bor `
                        [IO.NotifyFilters]::Size
    $fsw.InternalBufferSize = 65536
  }

  function __sz($p){ try { (Get-Item -EA SilentlyContinue $p).Length } catch { 0 } }

  # De-dup registrations if they already exist
  'FS-C','FS-U','FS-D','FS-R' | ForEach-Object { Unregister-Event -SourceIdentifier $_ -ErrorAction SilentlyContinue }

  $null = Register-ObjectEvent -InputObject $fsw -EventName Created -SourceIdentifier 'FS-C' -Action {
    $p = $Event.SourceEventArgs.FullPath
    if(-not (Is-Excluded $p)){ Log ("CREATED: {0} size={1}" -f $p, (__sz $p)); Upsert-ActiveWithPreview $p }
  }
  $null = Register-ObjectEvent -InputObject $fsw -EventName Changed -SourceIdentifier 'FS-U' -Action {
    $p = $Event.SourceEventArgs.FullPath
    if(-not (Is-Excluded $p)){ Log ("UPDATED: {0} size={1}" -f $p, (__sz $p)); Upsert-ActiveWithPreview $p }
  }
  $null = Register-ObjectEvent -InputObject $fsw -EventName Deleted -SourceIdentifier 'FS-D' -Action {
    $p = $Event.SourceEventArgs.FullPath
    if(-not (Is-Excluded $p)){ Log ("DELETED: {0}" -f $p); Mark-DeletedSafe $p }
  }
  $null = Register-ObjectEvent -InputObject $fsw -EventName Renamed -SourceIdentifier 'FS-R' -Action {
    $old = $Event.SourceEventArgs.OldFullPath
    $new = $Event.SourceEventArgs.FullPath
    if(-not (Is-Excluded $old)){ Log ("RENAMED FROM: {0}" -f $old); Mark-DeletedSafe $old }
    if(-not (Is-Excluded $new)){ Log ("RENAMED TO:   {0}" -f $new); Upsert-ActiveWithPreview $new }
  }

  $fsw.EnableRaisingEvents = $true
  Log ("watching C:\T18 ...")
} catch {
  Log ("FATAL: {0}" -f $_)
}
# === /ENSURE ===================================================================
# ---------- Notion helpers (idempotent) ----------
$global:__nt_headers = $null
function Get-NotionHeaders {
  if($null -ne $global:__nt_headers){ return $global:__nt_headers }
  $token=[Environment]::GetEnvironmentVariable('NOTION_TOKEN','User')
  $db=[Environment]::GetEnvironmentVariable('NOTION_DATABASE_ID','User')
  if(-not $token -or -not $db){ throw "NOTION_TOKEN/DB missing" }
  if($db -match '^[0-9a-fA-F]{32}$'){ $db = $db.Insert(20,'-').Insert(16,'-').Insert(12,'-').Insert(8,'-') }
  $global:__dbId = $db
  $global:__nt_headers = @{ Authorization="Bearer $token"; "Notion-Version"="2022-06-28"; "Content-Type"="application/json" }
  return $global:__nt_headers
}

# DB property names (read once; your DB uses Path/Status/Modified/Size)
$global:__titleProp    = if($env:NOTION_TITLE_PROP){ $env:NOTION_TITLE_PROP } else { 'Path' }
$global:__statusProp   = if($env:NOTION_PROP_STATUS){ $env:NOTION_PROP_STATUS } else { 'Status' }
$global:__modifiedProp = if($env:NOTION_PROP_MODIFIED){ $env:NOTION_PROP_MODIFIED } else { 'Modified' }
$global:__sizeProp     = if($env:NOTION_PROP_SIZE){ $env:NOTION_PROP_SIZE } else { 'Size' }
$global:__deletedVal   = if($env:NOTION_STATUS_VALUE_DELETED){ $env:NOTION_STATUS_VALUE_DELETED } else { 'deleted' }
$global:__activeVal    = if($env:NOTION_STATUS_VALUE){ $env:NOTION_STATUS_VALUE } else { 'Active' }

function Normalize-Path([string]$p){ $p -replace '/', '\' }

function Find-PageByTitle([string]$title, [int]$retries=6){
  $headers = Get-NotionHeaders
  $db = $global:__dbId
  $title = Normalize-Path $title
  for($i=0;$i -lt $retries;$i++){
    try{
      $body = @{ page_size=1; filter=@{ property=$global:__titleProp; title=@{ equals=$title } } } | ConvertTo-Json -Depth 10
      $r = Invoke-RestMethod -Method Post -Uri "https://api.notion.com/v1/databases/$db/query" -Headers $headers -Body $body -ErrorAction Stop
      if($r.results.Count -gt 0){ return $r.results[0] }
    } catch { }
    Start-Sleep -Milliseconds 700
  }
  return $null
}

function Ensure-PageForPath([string]$path){
  $headers = Get-NotionHeaders
  $db = $global:__dbId
  $path = Normalize-Path $path
  $existing = Find-PageByTitle $path 3
  if($existing){ return $existing.id }

  $props = @{
    ($global:__titleProp) = @{ title=@(@{ text=@{ content=$path } }) }
    ($global:__statusProp)= @{ select=@{ name=$global:__activeVal } }
    ($global:__sizeProp)  = @{ number = 0 }
    ($global:__modifiedProp) = @{ date=@{ start=(Get-Date).ToUniversalTime().ToString('o') } }
  }
  $payload = @{ parent=@{ database_id=$db }; properties=$props } | ConvertTo-Json -Depth 10
  $pg = Invoke-RestMethod -Method Post -Uri "https://api.notion.com/v1/pages" -Headers $headers -Body $payload -ErrorAction Stop
  return $pg.id
}

function Add-PreviewBlock([string]$pageGuid, [string]$path){
  try{
    $text = (Get-Content -LiteralPath $path -Raw -EA Stop)
    if(-not $text){ return }
    if($text.Length -gt 1800){ $text = $text.Substring(0,1800) }
  } catch { return }  # binary/unreadable -> skip

  $lang='plain text'
  switch -regex ($path){
    '.*\.ps1$' { $lang='powershell' }
    '.*\.py$'  { $lang='python' }
    '.*\.cmd$' { $lang='shell' }
    '.*\.(json|yml|yaml|toml)$' { $lang='markup' }
    '.*\.md$'  { $lang='markdown' }
  }
  $headers = Get-NotionHeaders
  $payload = @{ children = @(@{
    object='block'; type='code'
    code=@{ language=$lang; rich_text=@(@{ type='text'; text=@{ content=$text }}) }
  }) } | ConvertTo-Json -Depth 10
  Invoke-RestMethod -Method Patch -Uri ("https://api.notion.com/v1/blocks/{0}/children" -f $pageGuid) -Headers $headers -Body $payload -ErrorAction SilentlyContinue | Out-Null
}

function Upsert-ActiveWithPreview([string]$path){
  $path = Normalize-Path $path
  if(-not (Test-Path -LiteralPath $path)){ return }  # might be mid-rename
  $pageGuid = Ensure-PageForPath $path
  $headers = Get-NotionHeaders
  $props = @{
    ($global:__statusProp)   = @{ select=@{ name=$global:__activeVal } }
    ($global:__sizeProp)     = @{ number = (Get-Item -EA SilentlyContinue $path).Length }
    ($global:__modifiedProp) = @{ date=@{ start=(Get-Date).ToUniversalTime().ToString('o') } }
  }
  $patch = @{ properties = $props } | ConvertTo-Json -Depth 10
  Invoke-RestMethod -Method Patch -Uri ("https://api.notion.com/v1/pages/{0}" -f $pageGuid) -Headers $headers -Body $patch -ErrorAction SilentlyContinue | Out-Null
  Add-PreviewBlock $pageGuid $path
  Log ("SYNCED: {0} size={1}" -f $path, $props[$global:__sizeProp].number)
}

function Mark-DeletedSafe([string]$path){
  $path = Normalize-Path $path
  $headers = Get-NotionHeaders
  $page = Find-PageByTitle $path 6
  if(-not $page){
    Log ("DELETE TOMB?: row not found for {0}" -f $path)
    # Create tombstone row so DB stays accurate
    $pageGuid = Ensure-PageForPath $path
    $page = @{ id = $pageGuid }
  }
  $pageGuid = $page.id
  $props = @{
    ($global:__statusProp)   = @{ select=@{ name=$global:__deletedVal } }
    ($global:__sizeProp)     = @{ number = 0 }
    ($global:__modifiedProp) = @{ date=@{ start=(Get-Date).ToUniversalTime().ToString('o') } }
  }
  $patch = @{ properties=$props } | ConvertTo-Json -Depth 10
  Invoke-RestMethod -Method Patch -Uri ("https://api.notion.com/v1/pages/{0}" -f $pageGuid) -Headers $headers -Body $patch -ErrorAction SilentlyContinue | Out-Null
}
# ---------- /helpers ----------
# === ENSURE events ===
try { $fsw.EnableRaisingEvents = $false } catch {}
try {
  if(-not $fsw){
    $fsw = New-Object IO.FileSystemWatcher 'C:\T18'
    $fsw.IncludeSubdirectories = $true
    $fsw.Filter='*'
    $fsw.NotifyFilter = [IO.NotifyFilters]::FileName -bor `
                        [IO.NotifyFilters]::LastWrite -bor `
                        [IO.NotifyFilters]::Size
    $fsw.InternalBufferSize = 65536
  }
  'FS-C','FS-U','FS-D','FS-R' | % { Unregister-Event -SourceIdentifier $_ -ErrorAction SilentlyContinue }
  function __sz($p){ try { (Get-Item -EA SilentlyContinue $p).Length } catch { 0 } }

  $null = Register-ObjectEvent $fsw Created 'FS-C' -Action {
    $p = $Event.SourceEventArgs.FullPath
    if(-not (Is-Excluded $p)){ Log ("CREATED: {0} size={1}" -f $p, (__sz $p)); Upsert-ActiveWithPreview $p }
  }
  $null = Register-ObjectEvent $fsw Changed 'FS-U' -Action {
    $p = $Event.SourceEventArgs.FullPath
    if(-not (Is-Excluded $p)){ Log ("UPDATED: {0} size={1}" -f $p, (__sz $p)); Upsert-ActiveWithPreview $p }
  }
  $null = Register-ObjectEvent $fsw Deleted 'FS-D' -Action {
    $p = $Event.SourceEventArgs.FullPath
    if(-not (Is-Excluded $p)){ Log ("DELETED: {0}" -f $p); Mark-DeletedSafe $p }
  }
  $null = Register-ObjectEvent $fsw Renamed 'FS-R' -Action {
    $old = $Event.SourceEventArgs.OldFullPath; $new = $Event.SourceEventArgs.FullPath
    if(-not (Is-Excluded $old)){ Log ("RENAMED FROM: {0}" -f $old); Mark-DeletedSafe $old }
    if(-not (Is-Excluded $new)){ Log ("RENAMED TO:   {0}" -f $new); Upsert-ActiveWithPreview $new }
  }
  $fsw.EnableRaisingEvents = $true
  Log ("watching C:\T18 ...")
} catch { Log ("FATAL: {0}" -f $_) }
# === /ENSURE events ===
