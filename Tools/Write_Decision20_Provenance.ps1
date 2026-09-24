param()
$ErrorActionPreference='Stop';$repository=Split-Path -Parent $PSScriptRoot;$project=Join-Path $repository 'Unity';$build=Join-Path $project 'Builds\Decision20';$evidence=Join-Path $repository 'Docs\Evidence\M1\Decision20'
function HashFile([string]$p){(Get-FileHash -LiteralPath $p).Hash.ToLowerInvariant()}
function Item([string]$p,[string]$base){$f=Get-Item -LiteralPath $p;[ordered]@{path=$f.FullName.Substring($base.Length+1).Replace('\','/');bytes=$f.Length;sha256=HashFile $p}}
$context=Get-Content -LiteralPath (Join-Path $evidence '20_build_context.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$sources=Get-Content -LiteralPath (Join-Path $evidence '20_project_sources.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$paths=@(foreach($dir in @('Assets','Packages','ProjectSettings')){Get-ChildItem -LiteralPath (Join-Path $project $dir) -File -Recurse -Force | ForEach-Object {$_.FullName.Substring($project.Length+1).Replace('\','/')}})
if(@(Compare-Object @($sources.files.path | Sort-Object) @($paths | Sort-Object)).Count -or @($sources.files | Where-Object {(HashFile (Join-Path $project $_.path)) -ne $_.sha256}).Count){throw '20 projectの版が不一致'}
if((HashFile (Join-Path $evidence '20_project_sources.json')) -ne $context.project_source_manifest_sha256 -or (HashFile (Join-Path $evidence '20_compiled_sources.json')) -ne $context.compiled_source_manifest_sha256){throw '20 build結合不一致'}
$compiled=Get-Content -LiteralPath (Join-Path $evidence '20_compiled_sources.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$expected=$compiled.files | Where-Object {$_.path -eq 'ProjectSettings/ProjectSettings.asset'}
if((HashFile (Join-Path $evidence '20_compiled_PlayerSettings.asset')) -ne $expected.sha256){throw '20一時build設定の記録不一致'}
$payload=@(Get-ChildItem -LiteralPath $build -File -Recurse | Where-Object {$_.FullName -notmatch '\\Capture_[^\\]+\\'} | ForEach-Object {$_.FullName.Substring($build.Length+1).Replace('\','/')})
if(@(Compare-Object @($context.build_payload_files.path | Sort-Object) @($payload | Sort-Object)).Count -or @($context.build_payload_files | Where-Object {(HashFile (Join-Path $build $_.path)) -ne $_.sha256}).Count){throw '20実行一式不一致'}
$order=Get-Content -LiteralPath (Join-Path $evidence '20_run_order.json') -Raw -Encoding UTF8 | ConvertFrom-Json;$capture=(Resolve-Path -LiteralPath $order.captureDirectory).Path
if(-not $capture.StartsWith($build+'\',[StringComparison]::OrdinalIgnoreCase)){throw '20所有captureを指定してください'}
$report=Get-Content -LiteralPath (Join-Path $evidence '20_measurement_summary.json') -Raw -Encoding UTF8 | ConvertFrom-Json;if(-not $report.all_runtime_passed){throw '20実行不合格'}
if(@($report.input_assets | Where-Object {(HashFile (Join-Path $repository $_.path)) -ne $_.sha256}).Count){throw '20入力asset不一致'}
[ordered]@{recordedUtc=(Get-Date).ToUniversalTime().ToString('o');gitContextAtRun=[ordered]@{head=$order.gitHeadAtRun;dirty=$order.gitDirtyAtRun};captureDirectory=$capture.Substring($repository.Length+1).Replace('\','/');method_ja='形式専用scene、新プロセス3回ずつ。build時だけframe timing stats有効、復元前後と実compiled版を別manifestへ保存。媒体は計測区間外の同一実行版。';evidence=@(Get-ChildItem -LiteralPath $evidence -File | Where-Object {$_.Name -ne '20_provenance.json'} | Sort-Object Name | ForEach-Object {Item $_.FullName $evidence});rawRunFiles=@(Get-ChildItem -LiteralPath $capture -File -Recurse | Sort-Object FullName | ForEach-Object {Item $_.FullName $capture});tools=@(Get-ChildItem -LiteralPath $PSScriptRoot -File | Where-Object {$_.Name -match 'Decision20'} | Sort-Object Name | ForEach-Object {Item $_.FullName $repository});sourceMismatches=0;payloadMismatches=0;hmdVerified=$false} | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $evidence '20_provenance.json') -Encoding utf8
Write-Output '20の出典照合・保存が完了しました。'
