param([string]$Ffmpeg='G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe')
$ErrorActionPreference='Stop'
$repository=Split-Path -Parent $PSScriptRoot
$project=Join-Path $repository 'Unity'
$build=Join-Path $project 'Builds\M1_Revision01'
$evidence=Join-Path $repository 'Docs\Evidence\M1\Revision01'
$sources=Get-Content -LiteralPath (Join-Path $evidence '15_build_sources.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$currentPaths=@(foreach($folder in @('Assets','Packages','ProjectSettings')) { Get-ChildItem -LiteralPath (Join-Path $project $folder) -File -Recurse -Force | ForEach-Object {$_.FullName.Substring($project.Length+1).Replace('\','/')} })
if(@(Compare-Object @($sources.files.path | Sort-Object) @($currentPaths | Sort-Object)).Count){throw 'ソースの追加・削除があるため、再ビルドが必要です。'}
$changes=@($sources.files | Where-Object {(Get-FileHash -LiteralPath (Join-Path $project $_.path) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $_.sha256})
if($changes.Count){throw '制作物がビルド時と異なります。再ビルドしてください。'}
$context=Get-Content -LiteralPath (Join-Path $evidence '15_build_context.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$payloadChanges=@($context.build_payload_files | Where-Object {(Get-FileHash -LiteralPath (Join-Path $build $_.path) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $_.sha256})
if($payloadChanges.Count){throw '実行一式がビルド時と異なります。'}
if(-not(Test-Path -LiteralPath $Ffmpeg)){throw 'ffmpegが見つかりません。'}
$capture=Join-Path $build ('Capture_'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Path $capture | Out-Null
$log=Join-Path $capture 'player.log'
$head=(& git -C $repository rev-parse HEAD).Trim();$dirty=@(& git -C $repository status --porcelain).Count -gt 0
$arguments='-screen-fullscreen 0 -screen-width 1280 -screen-height 720 -logFile "'+$log+'" --capture-dir "'+$capture+'"'
$process=Start-Process -FilePath (Join-Path $build 'GreatWaveM1Revision01.exe') -ArgumentList $arguments -WindowStyle Hidden -PassThru
if(-not $process.WaitForExit(180000)){Stop-Process -Id $process.Id;throw "180秒を超えたため、この記録だけを停止しました：$log"}
$process.Refresh();if($process.ExitCode -ne 0){throw "記録に失敗しました：$log"}
$report=Get-Content -LiteralPath (Join-Path $capture 'capture_report.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if(-not $report.passed -or $report.capturedFrames -ne 480){throw '入力検査と480枚の描画を確認できません。'}
& $Ffmpeg -y -framerate 24 -i (Join-Path $capture 'frame_%04d.png') -c:v libx264 -crf 20 -pix_fmt yuv420p -movflags +faststart (Join-Path $evidence 'M1_Revision01_Walkthrough.mp4')
if($LASTEXITCODE -ne 0){throw '動画の符号化に失敗しました。'}
$frames=@{M1_Comparison=0;M1_Boat=96;M1_Side=192;M1_Rear=288;M1_Region=384}
foreach($name in $frames.Keys){Copy-Item -LiteralPath (Join-Path $capture ('frame_'+$frames[$name].ToString('D4')+'.png')) -Destination (Join-Path $evidence ($name+'.png'))}
Copy-Item -LiteralPath (Join-Path $capture 'capture_report.json') -Destination (Join-Path $evidence '15_capture_report.json')
& (Join-Path $PSScriptRoot 'Write_M1_Revision01_Provenance.ps1') -CaptureDirectory $capture -CaptureGitHead $head -CaptureGitDirty $dirty
Write-Output "M1修正01記録完了：$evidence"
