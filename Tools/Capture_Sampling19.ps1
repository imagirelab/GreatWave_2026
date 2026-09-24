param([string]$Ffmpeg='G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe')
$ErrorActionPreference='Stop'
$repository=Split-Path -Parent $PSScriptRoot;$project=Join-Path $repository 'Unity';$build=Join-Path $project 'Builds\Sampling19';$evidence=Join-Path $repository 'Docs\Evidence\M1\Sampling19'
$sources=Get-Content -LiteralPath (Join-Path $evidence '19_build_sources.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$paths=@(foreach($folder in @('Assets','Packages','ProjectSettings')){Get-ChildItem -LiteralPath (Join-Path $project $folder) -File -Recurse -Force | ForEach-Object {$_.FullName.Substring($project.Length+1).Replace('\','/')}})
if(@(Compare-Object @($sources.files.path | Sort-Object) @($paths | Sort-Object)).Count){throw 'ビルド後にソースが追加・削除されています。'}
if(@($sources.files | Where-Object {(Get-FileHash -LiteralPath (Join-Path $project $_.path)).Hash.ToLowerInvariant() -ne $_.sha256}).Count){throw '再ビルドが必要です。'}
$capture=Join-Path $build ('Capture_'+(Get-Date -Format 'yyyyMMdd_HHmmss'));New-Item -ItemType Directory -Path $capture | Out-Null
$log=Join-Path $capture 'player.log';$head=(& git -C $repository rev-parse HEAD).Trim();$dirty=@(& git -C $repository status --porcelain).Count -gt 0
$process=Start-Process -FilePath (Join-Path $build 'GreatWave19.exe') -ArgumentList ('-screen-fullscreen 0 -screen-width 1280 -screen-height 720 -logFile "'+$log+'" --capture-dir "'+$capture+'"') -WindowStyle Hidden -PassThru
if(-not $process.WaitForExit(600000)){Stop-Process -Id $process.Id;throw "10分を超えたため所有した記録プロセスを停止しました：$log"}
$process.Refresh();if($process.ExitCode -ne 0){throw "19記録の判定が不合格です：$log"}
$report=Get-Content -LiteralPath (Join-Path $capture 'capture_report.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if(-not $report.passed -or $report.frames -ne 121){throw '121時刻・色/深度/影の検査に合格していません。'}
& $Ffmpeg -y -framerate 60 -i (Join-Path $capture 'frame_%04d.png') -frames:v 120 -c:v libx264 -crf 20 -pix_fmt yuv420p -movflags +faststart (Join-Path $evidence '19_Sampling_2s.mp4')
if($LASTEXITCODE -ne 0){throw '動画の符号化に失敗しました。'}
& $Ffmpeg -v error -i (Join-Path $evidence '19_Sampling_2s.mp4') -f null -
if($LASTEXITCODE -ne 0){throw '動画の復号に失敗しました。'}
foreach($sample in @(0,15,45,61,83,111,120)){Copy-Item -LiteralPath (Join-Path $capture ('frame_'+$sample.ToString('D4')+'.png')) -Destination (Join-Path $evidence ('19_Sampling_'+$sample.ToString('D3')+'.png'))}
foreach($file in Get-ChildItem -LiteralPath $capture -File | Where-Object {$_.Name -match '^(color|depth|shadow|fixed|receive)_.*\.png$'}){Copy-Item -LiteralPath $file.FullName -Destination (Join-Path $evidence ('19_'+$file.Name))}
foreach($name in @('validation','capture_report')){Copy-Item -LiteralPath (Join-Path $capture ($name+'.json')) -Destination (Join-Path $evidence ('19_runtime_'+$name+'.json'))}
& (Join-Path $PSScriptRoot 'Write_Sampling19_Provenance.ps1') -CaptureDirectory $capture -CaptureGitHead $head -CaptureGitDirty $dirty
Write-Output "19の実記録：$evidence"
