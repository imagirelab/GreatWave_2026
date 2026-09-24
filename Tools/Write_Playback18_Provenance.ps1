param([Parameter(Mandatory=$true)][string]$CaptureDirectory,[Parameter(Mandatory=$true)][string]$CaptureGitHead,[bool]$CaptureGitDirty=$false)
$ErrorActionPreference='Stop'
$repository=Split-Path -Parent $PSScriptRoot;$project=Join-Path $repository 'Unity';$build=Join-Path $project 'Builds\Playback18';$evidence=Join-Path $repository 'Docs\Evidence\M1\Playback18'
$capture=(Resolve-Path -LiteralPath $CaptureDirectory).Path
if(-not $capture.StartsWith($build+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'この18実行一式内の記録を指定してください。'}
function HashFile([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Item([string]$path,[string]$base){$file=Get-Item -LiteralPath $path;[ordered]@{path=$file.FullName.Substring($base.Length+1).Replace('\','/');bytes=$file.Length;sha256=HashFile $path}}
$sources=Get-Content -LiteralPath (Join-Path $evidence '18_build_sources.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$current=@(foreach($folder in @('Assets','Packages','ProjectSettings')){Get-ChildItem -LiteralPath (Join-Path $project $folder) -Recurse -File -Force | ForEach-Object {$_.FullName.Substring($project.Length+1).Replace('\','/')}})
if(@(Compare-Object @($sources.files.path | Sort-Object) @($current | Sort-Object)).Count){throw 'ソースの追加・削除があり、ビルド時と一致しません。'}
if(@($sources.files | Where-Object {(HashFile (Join-Path $project $_.path)) -ne $_.sha256}).Count){throw 'ソースがビルド時と異なります。'}
$context=Get-Content -LiteralPath (Join-Path $evidence '18_build_context.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if((HashFile (Join-Path $evidence '18_build_sources.json')) -ne $context.source_manifest_sha256){throw 'ビルドのソース記録が一致しません。'}
$payload=@(Get-ChildItem -LiteralPath $build -File -Recurse | Where-Object {$_.FullName -notmatch '\\Capture_[^\\]+\\'} | ForEach-Object {$_.FullName.Substring($build.Length+1).Replace('\','/')})
if(@(Compare-Object @($context.build_payload_files.path | Sort-Object) @($payload | Sort-Object)).Count){throw '実行一式の追加・削除があります。'}
if(@($context.build_payload_files | Where-Object {(HashFile (Join-Path $build $_.path)) -ne $_.sha256}).Count){throw '実行一式がビルド時と異なります。'}
$report=Get-Content -LiteralPath (Join-Path $capture 'capture_report.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if(-not $report.passed){throw '失敗した記録には出典を作れません。'}
$vatInput=Get-Content -LiteralPath (Join-Path $repository 'Houdini\PlaybackComparison18\Evidence\18_vat_integration.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$abcInput=Get-Content -LiteralPath (Join-Path $repository 'Houdini\PlaybackComparison18\Evidence\18_alembic_integration.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$inputChanges=@($vatInput.files | Where-Object {(HashFile (Join-Path $repository $_.unity)) -ne $_.sha256})
$inputChanges+=@($abcInput.files | Where-Object {$_.path.StartsWith('Unity/') -and (HashFile (Join-Path $repository $_.path)) -ne $_.sha256})
if($inputChanges.Count){throw 'Unityの比較入力がHoudini出力の記録と一致しません。'}
$names=@('18_Comparison_2s.mp4','18_runtime_capture_report.json','18_runtime_alembic_validation.json','18_runtime_vat_validation.json','18_runtime_performance.json','18_alembic_editor_validation.json','18_vat_editor_validation.json','18_archive_sampling.json','18_vat_import.json','18_build.json','18_build_context.json','18_prebuild_sources.json','18_build_sources.json')
$names+=@(0,3,18,19,24,48 | ForEach-Object {'18_Comparison_'+$_.ToString('D3')+'.png'})
$files=@($names | ForEach-Object {Item (Join-Path $evidence $_) $evidence})
$authoring=@(Get-ChildItem -LiteralPath (Join-Path $repository 'Houdini\PlaybackComparison18\Source') -File | Sort-Object Name | ForEach-Object {Item $_.FullName $repository})
$exportRoot=Join-Path $repository 'Houdini\PlaybackComparison18'
$exportEvidence=@(Get-ChildItem -LiteralPath (Join-Path $exportRoot 'Evidence') -File | Where-Object {$_.Extension -ne '.log' -and $_.Name -notlike 'run_*' -and $_.Name -notin @('18_vat_schema.json','18_labs_source_tree.json')} | Sort-Object Name | ForEach-Object {Item $_.FullName $repository})
$thirdParty=@(Get-ChildItem -LiteralPath (Join-Path $exportRoot 'ThirdParty') -File -Recurse | Where-Object {$_.FullName -notmatch '\\otls\\'} | Sort-Object FullName | ForEach-Object {Item $_.FullName $repository})
$data=[ordered]@{
 recorded_utc=(Get-Date).ToUniversalTime().ToString('o');scene='Unity/Assets/GreatWave/Scenes/Tests/M1_Playback18.unity';input_clip='GreatWave17_FLIP_02'
 build_context='18_build_context.json';source_snapshot='18_prebuild_sources.json / 18_build_sources.json';git_context_at_capture=[ordered]@{head=$CaptureGitHead;dirty=$CaptureGitDirty}
 capture_directory=$capture.Substring($repository.Length+1).Replace('\','/');player_exit_code=0;render_method_ja=$report.method;captured_frames=$report.frames;video_frames=48;video_rate=24;video_seconds=2;endpoint_sample=48
 video_rate_is_performance_measurement=$false;hmd_validation='機器なし・未実施';physical_accuracy='17の入力に体積膨張/流出がある。今回の合格対象外';manual_keyboard='利用者確認待ち'
 same_input_sha_verified=($inputChanges.Count -eq 0);source_mismatch_count=0;payload_mismatch_count=0;selected_samples=@(0,3,18,19,24,48);evidence_files=$files;authoring_files=$authoring;export_evidence_files=$exportEvidence;third_party_files=$thirdParty
 player_log=Item (Join-Path $capture 'player.log') $capture
 raw_frame_files=@(Get-ChildItem -LiteralPath $capture -Filter 'frame_*.png' -File | Sort-Object Name | ForEach-Object {Item $_.FullName $capture})
}
$data | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $evidence '18_provenance.json') -Encoding utf8
Write-Output '18の実行・出典ハッシュを更新しました。'


