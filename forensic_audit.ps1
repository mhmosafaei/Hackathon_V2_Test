param(
  [string]$Source = 'C:\2025 Chat Backups\DataExport_2025-11-30',
  [string]$Report = 'C:\2025 Chat Backups\Forensic_Report_2025-11-30'
)

$ErrorActionPreference = 'Stop'
$inv = [System.Globalization.CultureInfo]::InvariantCulture
function Rel([string]$p) { return $p.Substring($Source.Length).TrimStart('\') }
function Iso($d) { if ($null -eq $d) { return '' }; return $d.ToUniversalTime().ToString('o') }
function Csv($data, $path) { @($data) | Export-Csv -LiteralPath $path -NoTypeInformation -Encoding utf8 }
function HashFile($path, $alg) { (Get-FileHash -LiteralPath $path -Algorithm $alg).Hash.ToLowerInvariant() }
function Field($obj, [string]$name) { $p=$obj.PSObject.Properties[$name]; if($null -eq $p){return $null}; return $p.Value }

if (-not (Test-Path -LiteralPath $Source -PathType Container)) { throw "Evidence source does not exist: $Source" }
New-Item -ItemType Directory -Force -Path $Report | Out-Null

$sourceInfo = Get-Item -LiteralPath $Source -Force
$runStart = (Get-Date).ToUniversalTime()
$dirs = @(Get-ChildItem -LiteralPath $Source -Directory -Recurse -Force)
$files = @(Get-ChildItem -LiteralPath $Source -File -Recurse -Force)

$inventory = foreach($f in $files) {
  $streams = ''
  try { $streams = ((Get-Item -LiteralPath $f.FullName -Stream * -ErrorAction Stop | Where-Object {$_.Stream -ne ':$DATA'} | ForEach-Object {$_.Stream}) -join ';') } catch { $streams = 'Unavailable: ' + $_.Exception.Message }
  [pscustomobject]@{ RelativePath=(Rel $f.FullName); Filename=$f.Name; Extension=$f.Extension; SizeBytes=[int64]$f.Length; CreationTimeUtc=(Iso $f.CreationTimeUtc); LastWriteTimeUtc=(Iso $f.LastWriteTimeUtc); LastAccessTimeUtc=(Iso $f.LastAccessTimeUtc); Attributes=[string]$f.Attributes; AlternateDataStreams=$streams; FilesystemAnomaly='' }
}
Csv $inventory (Join-Path $Report 'file_inventory.csv')

$dirInventory = foreach($d in @($sourceInfo)+$dirs) { [pscustomobject]@{RelativePath=(Rel $d.FullName); CreationTimeUtc=(Iso $d.CreationTimeUtc); LastWriteTimeUtc=(Iso $d.LastWriteTimeUtc); LastAccessTimeUtc=(Iso $d.LastAccessTimeUtc); Attributes=[string]$d.Attributes} }
Csv $dirInventory (Join-Path $Report 'directory_inventory.csv')

$sortedFiles = @($files | Sort-Object FullName)
$hashes = foreach($f in $sortedFiles) { [pscustomobject]@{RelativePath=(Rel $f.FullName); SizeBytes=[int64]$f.Length; SHA256=(HashFile $f.FullName 'SHA256'); SHA512=(HashFile $f.FullName 'SHA512')} }
$hashes | ForEach-Object { '{0}  {1}  {2}' -f $_.SHA256,$_.SizeBytes,$_.RelativePath } | Set-Content -LiteralPath (Join-Path $Report 'sha256_manifest.txt') -Encoding utf8
$hashes | ForEach-Object { '{0}  {1}  {2}' -f $_.SHA512,$_.SizeBytes,$_.RelativePath } | Set-Content -LiteralPath (Join-Path $Report 'sha512_manifest.txt') -Encoding utf8

$anoms = [System.Collections.Generic.List[object]]::new()
$refs = [System.Collections.Generic.List[object]]::new()
$messages = [System.Collections.Generic.List[object]]::new()
$htmlFiles = @($files | Where-Object {$_.Extension -ieq '.html'})
$jsonFiles = @($files | Where-Object {$_.Extension -ieq '.json'})
$mediaExt = @('.ogg','.opus','.mp3','.m4a','.wav','.webm','.mp4','.mov','.avi','.mkv','.jpg','.jpeg','.png','.gif','.webp','.pdf','.doc','.docx','.xls','.xlsx','.zip','.rar','.7z')
$audioExt = @('.ogg','.opus','.mp3','.m4a','.wav','.webm','.flac','.aac')

foreach($hf in $htmlFiles) {
  $rel = Rel $hf.FullName
  try { $html=[IO.File]::ReadAllText($hf.FullName) } catch { $anoms.Add([pscustomobject]@{Category='HTML read failure';Severity='Requires review';Source=$rel;MessageId='';Timestamp='';Reference='';Explanation=$_.Exception.Message}); continue }
  if($html -notmatch '<!DOCTYPE html|<html[\s>]'){ $anoms.Add([pscustomobject]@{Category='HTML structure';Severity='Requires review';Source=$rel;MessageId='';Timestamp='';Reference='';Explanation='No standard HTML/doctype marker found.'}) }
  $ids = [regex]::Matches($html,'(?is)<div[^>]*\bid=["'']message(\d+)["''][^>]*') | ForEach-Object {$_.Groups[1].Value}
  $dup = $ids | Group-Object | Where-Object Count -gt 1
  foreach($d in $dup){$anoms.Add([pscustomobject]@{Category='Duplicate HTML message ID';Severity='Requires review';Source=$rel;MessageId=$d.Name;Timestamp='';Reference='';Explanation="Message ID appears $($d.Count) times in this HTML file."})}
  $blocks=[regex]::Matches($html,'(?is)<div[^>]*\bid=["'']message(\d+)["''][^>]*>(.*?)(?=<div[^>]*\bid=["'']message\d+["'']|\z)')
  foreach($b in $blocks){
    $id=$b.Groups[1].Value; $body=$b.Groups[2].Value
    $date=''; if($body -match 'title=["'']([^"'']+)["'']'){ $date=$Matches[1] }
    $sender=''; if($body -match '(?is)class=["'']from_name["''][^>]*>\s*(.*?)\s*<'){ $sender=[regex]::Replace($Matches[1],'<[^>]+>','').Trim() }
    $text=''; if($body -match '(?is)class=["'']text["''][^>]*>(.*?)</div>'){ $text=[regex]::Replace($Matches[1],'<[^>]+>','').Trim() }
    $reply=''; if($body -match '(?is)reply_to[^>]*href=["'']?[^"'' >#]*#go_to_message(\d+)'){ $reply=$Matches[1] }
    $messages.Add([pscustomobject]@{SourceHtml=$rel;MessageId=$id;Timestamp=$date;Sender=$sender;Text=$text;ReplyToMessageId=$reply;Forwarded=[bool]($body -match 'forwarded');Edited=[bool]($body -match 'edited');MediaReference='';Flags=''})
    foreach($m in [regex]::Matches($body,'(?is)(?:href|src)=["'']([^"'']+)["'']')) { $u=$m.Groups[1].Value; if($u -notmatch '^(https?:|#|data:)') {$refs.Add([pscustomobject]@{SourceHtml=$rel;MessageId=$id;Reference=$u})} }
  }
}

$fileRelSet=@{}; foreach($f in $files){$fileRelSet[(Rel $f.FullName).Replace('/','\')]=1}
foreach($r in $refs){$candidate=([IO.Path]::GetFullPath((Join-Path (Split-Path (Join-Path $Source $r.SourceHtml) -Parent) $r.Reference))).Substring($Source.Length).TrimStart('\'); if(-not $fileRelSet.ContainsKey($candidate)){$anoms.Add([pscustomobject]@{Category='Missing HTML-referenced file';Severity='Requires review';Source=$r.SourceHtml;MessageId=$r.MessageId;Timestamp='';Reference=$r.Reference;Explanation='Referenced local path was not present in the evidence inventory.'})}}

$jsonMessageCount=0
foreach($jf in $jsonFiles){
  $jr=Rel $jf.FullName; try{$jo=Get-Content -LiteralPath $jf.FullName -Raw | ConvertFrom-Json -Depth 100}catch{$anoms.Add([pscustomobject]@{Category='JSON parse failure';Severity='Requires review';Source=$jr;MessageId='';Timestamp='';Reference='';Explanation=$_.Exception.Message});continue}
  $arr=Field $jo 'messages'; if($null -ne $arr){$jsonMessageCount+=@($arr).Count}
}

$mediaFiles = @($files | Where-Object {$mediaExt -contains $_.Extension.ToLowerInvariant()})
$media = foreach($f in $mediaFiles) { $h=$hashes | Where-Object RelativePath -eq (Rel $f.FullName); [pscustomobject]@{RelativePath=(Rel $f.FullName);Extension=$f.Extension.ToLowerInvariant();SizeBytes=$f.Length;SHA256=$h.SHA256;ReferencedByHtml=(@($refs | Where-Object {$_.Reference -like "*$($f.Name)"}).Count)} }
Csv $media (Join-Path $Report 'media_inventory.csv')
$duplicateMediaGroups = @($media | Group-Object SHA256 | Where-Object {$_.Count -gt 1})
foreach($g in $duplicateMediaGroups){$anoms.Add([pscustomobject]@{Category='Duplicate media content';Severity='Normal / explainable';Source='';MessageId='';Timestamp='';Reference=(($g.Group.RelativePath)-join '; ');Explanation='Different paths have identical SHA-256 hashes; may reflect Telegram duplicate exports or reused media.'})}

$ffprobe=(Get-Command ffprobe -ErrorAction SilentlyContinue)
$audioFiles = @($files | Where-Object {$audioExt -contains $_.Extension.ToLowerInvariant()})
$voice = foreach($f in $audioFiles) {
  $h=$hashes | Where-Object RelativePath -eq (Rel $f.FullName); $fmt='';$codec='';$dur='';$sr='';$ch='';$br='';$enc=''
  if($ffprobe){try{$p=& $ffprobe.Source -v error -show_entries format=format_name,duration,bit_rate:format_tags=encoder:stream=codec_name,sample_rate,channels -of json -- $f.FullName | ConvertFrom-Json; $fmt=$p.format.format_name;$dur=$p.format.duration;$br=$p.format.bit_rate;$enc=$p.format.tags.encoder;$s=@($p.streams)[0];$codec=$s.codec_name;$sr=$s.sample_rate;$ch=$s.channels}catch{$fmt='ffprobe error'}}
  [pscustomobject]@{RelativePath=(Rel $f.FullName);Filename=$f.Name;SHA256=$h.SHA256;SizeBytes=$f.Length;ContainerFormat=$fmt;Codec=$codec;DurationSeconds=$dur;SampleRate=$sr;Channels=$ch;Bitrate=$br;EncoderMetadata=$enc;CreationTimeUtc=(Iso $f.CreationTimeUtc);LastWriteTimeUtc=(Iso $f.LastWriteTimeUtc);LastAccessTimeUtc=(Iso $f.LastAccessTimeUtc)}
}
Csv $voice (Join-Path $Report 'voice_message_inventory.csv')

$timeline=$messages | Sort-Object Timestamp,SourceHtml,{[int64]($_.MessageId -as [int64])}; Csv $timeline (Join-Path $Report 'message_timeline.csv')
$duplicateMessageGroups = @($messages | Group-Object MessageId | Where-Object {$_.Count -gt 1})
foreach($g in $duplicateMessageGroups){$anoms.Add([pscustomobject]@{Category='Message ID reused across HTML';Severity='Normal / explainable';Source=(($g.Group.SourceHtml|Select-Object -Unique)-join '; ');MessageId=$g.Name;Timestamp='';Reference='';Explanation='IDs can repeat across separate Telegram chats or pages; review only if files represent the same chat.'})}
$replyMessages = @($messages | Where-Object {$_.ReplyToMessageId})
foreach($m in $replyMessages) { if(-not ($messages | Where-Object {$_.MessageId -eq $m.ReplyToMessageId})){ $anoms.Add([pscustomobject]@{Category='Reply target not found in analyzed HTML';Severity='Normal / explainable';Source=$m.SourceHtml;MessageId=$m.MessageId;Timestamp=$m.Timestamp;Reference=$m.ReplyToMessageId;Explanation='May be due to export boundaries, deleted content, or target being on an unparsed page.'})}}
Csv $anoms (Join-Path $Report 'anomaly_report.csv')

$post=@();foreach($f in $sortedFiles){$post += [pscustomobject]@{RelativePath=(Rel $f.FullName);SHA256=(HashFile $f.FullName 'SHA256')}}
$preMap=@{};foreach($h in $hashes){$preMap[$h.RelativePath]=$h.SHA256};$postDiff=@($post|Where-Object {-not $preMap.ContainsKey($_.RelativePath) -or $preMap[$_.RelativePath] -ne $_.SHA256})
$runEnd=(Get-Date).ToUniversalTime();$total=($files|Measure-Object Length -Sum).Sum
$lines=@(
 '# Telegram Backup Integrity Report','', '## Executive Summary', "This report documents a read-only audit of the current state of the supplied directory. $($files.Count) files and $($dirs.Count+1) directories were examined. The initial and post-analysis SHA-256 comparison found $($postDiff.Count) difference(s). Current hashes establish only the state observed during this audit; they do not prove original Telegram provenance.",'', '## Evidence Source', ("- Source: {0}" -f $Source), "- Source directory metadata at commencement: created $(Iso $sourceInfo.CreationTimeUtc); last modified $(Iso $sourceInfo.LastWriteTimeUtc); attributes $($sourceInfo.Attributes)",'', '## Preservation Method', 'All source enumeration, reading, hashing, HTML/JSON parsing, and ffprobe inspection (where available) were read-only. Generated files were written only to the report directory.', '', '## File and Hash Summary', "- Files: $($files.Count)", "- Directories: $($dirs.Count+1)", "- Total evidence size: $total bytes", '- SHA-256 and SHA-512 manifests are deterministically ordered by relative path.', '', '## Telegram Export Structure Assessment', "- HTML files: $($htmlFiles.Count)", "- JSON files: $($jsonFiles.Count)", "- Media files (recognized extensions): $($media.Count)", "- Audio/voice candidates: $($voice.Count)", 'Structure observations are recorded through the inventory and anomaly list; unusual files alone are not proof of modification.', '', '## HTML, JSON, Media, and Chronology Analysis', "- HTML message records parsed: $($messages.Count)", "- JSON message records detected: $jsonMessageCount", '- HTML link/reference checks, duplicate-message checks, reply-reference checks, media existence checks, and chronology ordering were performed. JSON was parsed when present; detailed message-by-message cross-check is limited to schemas that expose comparable exported message records.', '', '## Filesystem Timeline', 'Filesystem timestamps are in file_inventory.csv and directory_inventory.csv. Windows copying, extraction, synchronization, restore, and migration can affect filesystem timestamps; timestamps alone are not proof of fabrication.', '', '## Identified Anomalies and Benign Explanations', "- Findings recorded: $($anoms.Count)", '- See anomaly_report.csv. Categories marked Normal / explainable have common benign causes such as export page boundaries, deleted messages, or reused media.', '', '## Limitations', '- This is an internal consistency examination of the supplied current files. It cannot establish integrity before the initial hash capture, independently prove Telegram origin, or recover omitted/deleted export content.', '- Parsing is non-destructive and best-effort; complex HTML/JSON variants may require specialist review.', '', '## Pre-analysis vs Post-analysis Hash Verification', "- SHA-256 differences after analysis: $($postDiff.Count)", "- Result: $(if($postDiff.Count -eq 0){'MATCHED — every post-analysis SHA-256 matched the initial manifest.'}else{'MISMATCH — see post_analysis_hash_differences.csv; no repair attempted.'})", '', '## Conclusion', $(if($postDiff.Count -eq 0){'No change to the source files was detected during this audit. The evidence may be internally consistent to the extent reflected in the inventories and anomaly report; integrity before capture of these hashes cannot be established.'}else{'Source hash differences were detected after analysis. No repair or restoration was attempted; the listed files require immediate preservation review.'})
)
$lines | Set-Content -LiteralPath (Join-Path $Report 'Telegram_Backup_Integrity_Report.md') -Encoding utf8
Csv $postDiff (Join-Path $Report 'post_analysis_hash_differences.csv')
[pscustomobject]@{FilesExamined=$files.Count;DirectoriesExamined=$dirs.Count+1;MessagesExamined=$messages.Count;JsonMessagesDetected=$jsonMessageCount;VoiceAudioFiles=$voice.Count;Anomalies=$anoms.Count;PostAnalysisSha256Matched=($postDiff.Count -eq 0);Report=(Join-Path $Report 'Telegram_Backup_Integrity_Report.md')} | ConvertTo-Json -Compress
