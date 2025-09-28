$ErrorActionPreference = 'Stop'

# --- CONFIG
$Root = 'C:\T18'
$ExcludePatterns = @('\_quarantine_', '\teevra18\data\parquet\', '\.git\', '\.venv\', '\.locks\', '\.streamlit\')

# Notion auth & DB
$token = [Environment]::GetEnvironmentVariable('NOTION_TOKEN','User')
$db    = [Environment]::GetEnvironmentVariable('NOTION_DATABASE_ID','User')
if(-not $token -or -not $db){ throw "NOTION_TOKEN / NOTION_DATABASE_ID missing" }
if($db -match '^[0-9a-fA-F]{32}$'){ $db = $db.Insert(20,'-').Insert(16,'-').Insert(12,'-').Insert(8,'-') }

# Property names (from your DB)
$titleProp    = [Environment]::GetEnvironmentVariable('NOTION_TITLE_PROP','User');     if(-not $titleProp){    $titleProp    = 'Path' }
$gitTracked   = [Environment]::GetEnvironmentVariable('NOTION_PROP_GITTRACKED','User');if(-not $gitTracked){  $gitTracked   = 'Git Tracked' }
$modifiedProp = [Environment]::GetEnvironmentVariable('NOTION_PROP_MODIFIED','User');   if(-not $modifiedProp){ $modifiedProp = 'Modified' }
$sizeProp     = [Environment]::GetEnvironmentVariable('NOTION_PROP_SIZE','User');       if(-not $sizeProp){     $sizeProp     = 'Size' }
$statusProp   = [Environment]::GetEnvironmentVariable('NOTION_PROP_STATUS','User');     if(-not $statusProp){   $statusProp   = 'Status' }
$activeVal    = [Environment]::GetEnvironmentVariable('NOTION_STATUS_VALUE','User');    if(-not $activeVal){    $activeVal    = 'Active' }
$deletedVal   = 'deleted'

$headers = @{
  Authorization    = "Bearer $token"
  "Notion-Version" = "2022-06-28"
  "Content-Type"   = "application/json"
}

# Logging
$logDir = 'C:\T18\logs'; if(-not (Test-Path $logDir)){ New-Item -Type Directory $logDir | Out-Null }
$log   = Join-Path $logDir 'ps_watcher.log'
function Log([string]$msg){ ("[{0}] {1}" -f (Get-Date -Format 's'), $msg) | Add-Content $log }

# Excludes
function Is-Excluded([string]$path){
  $np = $path.ToLower()
  foreach($pat in $ExcludePatterns){
    if($np -like ("*" + $pat.ToLower() + "*")){ return $true }
  }
  return $false
}

# Debounce very chatty events
$recent = @{}
function SeenRecently($k){
  if($recent.ContainsKey($k) -and (Get-Date) - $recent[$k] -lt [TimeSpan]::FromSeconds(1)){ return $true }
  $recent[$k]=(Get-Date); return $false
}

# Side-peek preview (text up to ~1.8k chars, skip big/binary)
function Get-TextPreview([string]$path, [int]$max=1800){
  try{
    $fi = Get-Item -LiteralPath $path -Force -ErrorAction Stop
    if($fi.Length -gt 500000){ return "(content too large to preview)" }
    $t = Get-Content -LiteralPath $path -Raw -ErrorAction Stop
    if($t.Length -gt $max){ return $t.Substring(0,$max) } else { return $t }
  } catch { return "(binary or unreadable)" }
}

function Build-Props([string]$path, [Nullable[int64]]$size, [datetime]$whenLocal, [string]$statusName){
  $iso = $whenLocal.ToString('o') # local time incl. offset → avoids +1h surprise
  $p = @{
    $titleProp    = @{ title = @(@{ text = @{ content = $path } }) }
    $modifiedProp = @{ date  = @{ start = $iso } }
    $statusProp   = @{ select = @{ name = $statusName } }
    $gitTracked   = @{ checkbox = [bool]($statusName -ne $deletedVal) }
  }
  if($size -ne $null){ $p[$sizeProp] = @{ number = [int64]$size } }
  return $p
}

function Find-PageId-ByTitle([string]$path){
  $qBody = @{ page_size=1; filter=@{property=$titleProp; title=@{equals=$path}} } | ConvertTo-Json -Depth 10
  $res = Invoke-RestMethod -Method Post -Uri "https://api.notion.com/v1/databases/$db/query" -Headers $headers -Body $qBody
  if($res.results.Count -gt 0){ return $res.results[0].id } else { return $null }
}

function Upsert-Notion([string]$path,[string]$event){
  if(Is-Excluded $path){ return }
  if(SeenRecently("u:$path")){ return }
  if(-not (Test-Path -LiteralPath $path)){ return }

  $fi   = Get-Item -LiteralPath $path -Force
  $size = [int64]$fi.Length
  $ts   = $fi.LastWriteTime # local time
  $props = Build-Props $path $size $ts $activeVal

  $children = @()
  $preview = Get-TextPreview $path
  if($preview){
    $children = @(@{
      object="block"; type="code";
      code=@{ language="plain text"; rich_text=@(@{ type="text"; text=@{ content=$preview } }) }
    })
  }

  $pid = Find-PageId-ByTitle $path
  if($pid){
    $patch = @{ properties = $props }
    if($children){ $patch.children = $children }
    Invoke-RestMethod -Method Patch -Uri "https://api.notion.com/v1/pages/$pid" -Headers $headers -Body ($patch | ConvertTo-Json -Depth 10 -Compress) | Out-Null
  } else {
    $body = @{ parent=@{database_id=$db}; properties=$props }
    if($children){ $body.children = $children }
    Invoke-RestMethod -Method Post  -Uri "https://api.notion.com/v1/pages"     -Headers $headers -Body ($body  | ConvertTo-Json -Depth 10 -Compress) | Out-Null
  }
  Log "$event: $path size=$size"
}

function Mark-Deleted([string]$path){
  if(Is-Excluded $path){ return }
  if(SeenRecently("d:$path")){ return }
  $ts = (Get-Date)

  $pid = Find-PageId-ByTitle $path
  if($pid){
    $patch = @{
      properties = (Build-Props $path 0 $ts $deletedVal)
      children   = @(@{
        object="block"; type="paragraph";
        paragraph=@{ rich_text=@(@{ type="text"; text=@{ content="(deleted at $($ts.ToString('o')))" }}) }
      })
    }
    Invoke-RestMethod -Method Patch -Uri "https://api.notion.com/v1/pages/$pid" -Headers $headers -Body ($patch | ConvertTo-Json -Depth 10 -Compress) | Out-Null
    Log "DELETED: $path"
  } else {
    # make a visible tombstone row so you SEE the delete
    $body = @{
      parent=@{database_id=$db}
      properties = (Build-Props $path 0 $ts $deletedVal)
      children   = @(@{
        object="block"; type="paragraph";
        paragraph=@{ rich_text=@(@{ type="text"; text=@{ content="(deleted but original row not found)" }}) }
      })
    }
    Invoke-RestMethod -Method Post -Uri "https://api.notion.com/v1/pages" -Headers $headers -Body ($body | ConvertTo-Json -Depth 10 -Compress) | Out-Null
    Log "DELETED (tombstone): $path"
  }
}

# --- watcher
$fsw = New-Object System.IO.FileSystemWatcher -Property @{
  Path = $Root; IncludeSubdirectories = $true
  NotifyFilter = [IO.NotifyFilters]'FileName, DirectoryName, LastWrite, Size'
  Filter = '*'
}
$fsw.EnableRaisingEvents = $true

Register-ObjectEvent $fsw Created -Action { Upsert-Notion $Event.SourceEventArgs.FullPath "CREATED" } | Out-Null
Register-ObjectEvent $fsw Changed -Action { Upsert-Notion $Event.SourceEventArgs.FullPath "UPDATED" } | Out-Null
Register-ObjectEvent $fsw Deleted -Action { Mark-Deleted  $Event.SourceEventArgs.FullPath } | Out-Null
Register-ObjectEvent $fsw Renamed -Action {
  Mark-Deleted  $Event.SourceEventArgs.OldFullPath
  Upsert-Notion $Event.SourceEventArgs.FullPath "RENAMED"
} | Out-Null

Log "watching $Root ..."
while($true){ Start-Sleep 2 }
# === FIX: event wiring (create/update/delete/rename) =========================
try { $fsw.EnableRaisingEvents = $false } catch {}
try {
  # FileSystemWatcher
  $fsw = New-Object IO.FileSystemWatcher $Root
  $fsw.IncludeSubdirectories = $true
  $fsw.Filter = '*'
  $fsw.NotifyFilter = [IO.NotifyFilters]::FileName -bor `
                      [IO.NotifyFilters]::LastWrite -bor `
                      [IO.NotifyFilters]::Size
  $fsw.InternalBufferSize = 65536

  # helpers to print size when the file still exists
  function __sz($p){ try { (Get-Item -EA SilentlyContinue $p).Length } catch { 0 } }

  # CREATE + CHANGE  -> Sync-File (also pushes preview)
  $null = Register-ObjectEvent -InputObject $fsw -EventName Created -SourceIdentifier 'FS-C' -Action {
    $p = $Event.SourceEventArgs.FullPath
    if(-not (Is-Excluded $p)){
      Log ("CREATED: {0} size={1}" -f $p, (__sz $p))
      Sync-File $p
    }
  }
  $null = Register-ObjectEvent -InputObject $fsw -EventName Changed -SourceIdentifier 'FS-U' -Action {
    $p = $Event.SourceEventArgs.FullPath
    if(-not (Is-Excluded $p)){
      Log ("UPDATED: {0} size={1}" -f $p, (__sz $p))
      Sync-File $p
    }
  }

  # DELETE -> Mark-Deleted (Status=deleted; Modified=now (UTC))
  $null = Register-ObjectEvent -InputObject $fsw -EventName Deleted -SourceIdentifier 'FS-D' -Action {
    $p = $Event.SourceEventArgs.FullPath
    if(-not (Is-Excluded $p)){
      Log ("DELETED: {0}" -f $p)
      Mark-Deleted $p
    }
  }

  # RENAME -> mark old as deleted, sync the new path
  $null = Register-ObjectEvent -InputObject $fsw -EventName Renamed -SourceIdentifier 'FS-R' -Action {
    $old = $Event.SourceEventArgs.OldFullPath
    $new = $Event.SourceEventArgs.FullPath
    if(-not (Is-Excluded $old)){ Log ("RENAMED FROM: {0}" -f $old); Mark-Deleted $old }
    if(-not (Is-Excluded $new)){ Log ("RENAMED TO:   {0}" -f $new); Sync-File $new }
  }

  $fsw.EnableRaisingEvents = $true
  Log ("watching {0} ..." -f $Root)

  # simple message loop to keep the script alive
  while($true){ Start-Sleep 2 }
} catch {
  Log ("FATAL: {0}" -f $_)
  throw
}
# === /FIX ====================================================================
