param([string]$Ffmpeg='G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe')
$ErrorActionPreference='Stop'
$repository=Split-Path -Parent $PSScriptRoot
$project=Join-Path $repository 'Unity'
$build=Join-Path $project 'Builds\Playback18'
$evidence=Join-Path $repository 'Docs\Evidence\M1\Playback18'
$sources=Get-Content -LiteralPath (Join-Path $evidence '18_build_sources.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$currentPaths=@(foreach($folder in @('Assets','Packages','ProjectSettings')) { Get-ChildItem -LiteralPath (Join-Path $project $folder) -File -Recurse -Force | ForEach-Object {$_.FullName.Substring($project.Length+1).Replace('\','/')} })
if(@(Compare-Object @($sources.files.path | Sort-Object) @($currentPaths | Sort-Object)).Count){throw 'ソースの追加・削除があるため、再ビルドが必要です。'}
if(@($sources.files | Where-Object {(Get-FileHash -LiteralPath (Join-Path $project $_.path) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $_.sha256}).Count){throw 'ビルド後に制作物が変わっています。'}
$context=Get-Content -LiteralPath (Join-Path $evidence '18_build_context.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if(@($context.build_payload_files | Where-Object {(Get-FileHash -LiteralPath (Join-Path $build $_.path) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $_.sha256}).Count){throw '実行一式がビルド時と異なります。'}
$capture=Join-Path $build ('Capture_'+(Get-Date -Format 'yyyyMMdd_HHmmss'));New-Item -ItemType Directory -Path $capture | Out-Null
$log=Join-Path $capture 'player.log';$head=(& git -C $repository rev-parse HEAD).Trim();$dirty=@(& git -C $repository status --porcelain).Count -gt 0
$arguments='-screen-fullscreen 0 -screen-width 1280 -screen-height 720 -logFile "'+$log+'" --capture-dir "'+$capture+'"'
$process=Start-Process -FilePath (Join-Path $build 'GreatWave18.exe') -ArgumentList $arguments -WindowStyle Hidden -PassThru
if(-not $process.WaitForExit(600000)){Stop-Process -Id $process.Id;throw "10分を超えたため、この記録だけを停止しました：$log"}
$process.Refresh();if($process.ExitCode -ne 0){throw "記録に失敗しました：$log"}
$report=Get-Content -LiteralPath (Join-Path $capture 'capture_report.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if(-not $report.passed -or $report.frames -ne 49){throw '両形式の検査と49枚の実描画を確認できません。'}
& $Ffmpeg -y -framerate 24 -i (Join-Path $capture 'frame_%04d.png') -frames:v 48 -c:v libx264 -crf 20 -pix_fmt yuv420p -movflags +faststart (Join-Path $evidence '18_Comparison_2s.mp4')
if($LASTEXITCODE -ne 0){throw '動画の符号化に失敗しました。'}
& $Ffmpeg -v error -i (Join-Path $evidence '18_Comparison_2s.mp4') -f null -
if($LASTEXITCODE -ne 0){throw '動画の全デコード検査に失敗しました。'}
foreach($sample in @(0,3,18,19,24,48)){Copy-Item -LiteralPath (Join-Path $capture ('detail_'+$sample.ToString('D3')+'.png')) -Destination (Join-Path $evidence ('18_Comparison_'+$sample.ToString('D3')+'.png'))}
foreach($name in @('capture_report','alembic_validation','vat_validation','performance')){Copy-Item -LiteralPath (Join-Path $capture ($name+'.json')) -Destination (Join-Path $evidence ('18_runtime_'+$name+'.json'))}
& (Join-Path $PSScriptRoot 'Write_Playback18_Provenance.ps1') -CaptureDirectory $capture -CaptureGitHead $head -CaptureGitDirty $dirty
Write-Output "18記録完了：$evidence"
