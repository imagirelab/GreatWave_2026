param([Parameter(Mandatory=$true)][string]$CaptureDirectory,[Parameter(Mandatory=$true)][string]$CaptureGitHead,[bool]$CaptureGitDirty=$false)
$ErrorActionPreference='Stop'
$repository=Split-Path -Parent $PSScriptRoot;$project=Join-Path $repository 'Unity';$build=Join-Path $project 'Builds\Sampling19';$evidence=Join-Path $repository 'Docs\Evidence\M1\Sampling19';$capture=(Resolve-Path -LiteralPath $CaptureDirectory).Path
if(-not $capture.StartsWith($build+'\',[StringComparison]::OrdinalIgnoreCase)){throw '19所有の記録ディレクトリを指定してください。'}
function HashFile([string]$p){(Get-FileHash -LiteralPath $p).Hash.ToLowerInvariant()}
function Item([string]$p,[string]$base){$f=Get-Item -LiteralPath $p;[ordered]@{path=$f.FullName.Substring($base.Length+1).Replace('\','/');bytes=$f.Length;sha256=HashFile $p}}
$sources=Get-Content -LiteralPath (Join-Path $evidence '19_build_sources.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$paths=@(foreach($dir in @('Assets','Packages','ProjectSettings')){Get-ChildItem -LiteralPath (Join-Path $project $dir) -File -Recurse -Force | ForEach-Object {$_.FullName.Substring($project.Length+1).Replace('\','/')}})
if(@(Compare-Object @($sources.files.path | Sort-Object) @($paths | Sort-Object)).Count -or @($sources.files | Where-Object {(HashFile (Join-Path $project $_.path)) -ne $_.sha256}).Count){throw '制作物とビルドの版が一致しません。'}
$context=Get-Content -LiteralPath (Join-Path $evidence '19_build_context.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$payload=@(Get-ChildItem -LiteralPath $build -File -Recurse | Where-Object {$_.FullName -notmatch '\\Capture_[^\\]+\\'} | ForEach-Object {$_.FullName.Substring($build.Length+1).Replace('\','/')})
if(@(Compare-Object @($context.build_payload_files.path | Sort-Object) @($payload | Sort-Object)).Count -or @($context.build_payload_files | Where-Object {(HashFile (Join-Path $build $_.path)) -ne $_.sha256}).Count){throw '実行一式が一致しません。'}
if((HashFile (Join-Path $evidence '19_build_sources.json')) -ne $context.source_manifest_sha256){throw 'ビルドのmanifest結合が不一致です。'}
$report=Get-Content -LiteralPath (Join-Path $capture 'capture_report.json') -Raw -Encoding UTF8 | ConvertFrom-Json;if(-not $report.passed){throw '失敗した記録です。'}
$input=Get-Content -LiteralPath (Join-Path $repository 'Houdini\Sampling19\Evidence\19_unity_integration.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if(@($input.files | Where-Object {(HashFile (Join-Path $repository $_.path)) -ne $_.sha256}).Count){throw '実Houdini出力から入力が変わっています。'}
$data=[ordered]@{recorded_utc=(Get-Date).ToUniversalTime().ToString('o');scene='Unity/Assets/GreatWave/Scenes/Tests/M1_Sampling19.unity';git_context_at_capture=[ordered]@{head=$CaptureGitHead;dirty=$CaptureGitDirty};build_context='19_build_context.json';capture_directory=$capture.Substring($repository.Length+1).Replace('\','/');source_mismatches=0;payload_mismatches=0;player_exit_code=0;method_ja=$report.method;captured_unique_times=121;video_frames=120;video_rate=60;video_seconds=2;video_rate_is_performance=$false;hmd_status='機器なし・未実施';adoption_status='20は未実施';player_log=Item (Join-Path $capture 'player.log') $capture;
 evidence_files=@(Get-ChildItem -LiteralPath $evidence -File | Where-Object {$_.Name -notin @('19_provenance.json','19_early.png')} | Sort-Object Name | ForEach-Object {Item $_.FullName $evidence});
 raw_frames=@(Get-ChildItem -LiteralPath $capture -File -Filter 'frame_*.png' | Sort-Object Name | ForEach-Object {Item $_.FullName $capture});
 authoring=@(Get-ChildItem -LiteralPath (Join-Path $repository 'Houdini\Sampling19\Source') -File | Sort-Object Name | ForEach-Object {Item $_.FullName $repository});
 source_reports=@(Get-ChildItem -LiteralPath (Join-Path $repository 'Houdini\Sampling19\Evidence') -File | Where-Object {$_.Extension -eq '.json' -and $_.Name -notlike 'run_*' -and $_.Name -ne 'latest_run.json'} | Sort-Object Name | ForEach-Object {Item $_.FullName $repository})}
$data | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $evidence '19_provenance.json') -Encoding utf8
Write-Output '19の実キャッシュ・ビルド・画像・出典を結合しました。'
