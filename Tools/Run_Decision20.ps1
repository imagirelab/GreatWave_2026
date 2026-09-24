param([string]$Ffmpeg='G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe')
$ErrorActionPreference='Stop'
$repository=Split-Path -Parent $PSScriptRoot;$project=Join-Path $repository 'Unity';$build=Join-Path $project 'Builds\Decision20';$evidence=Join-Path $repository 'Docs\Evidence\M1\Decision20'
$sources=Get-Content -LiteralPath (Join-Path $evidence '20_project_sources.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$paths=@(foreach($folder in @('Assets','Packages','ProjectSettings')){Get-ChildItem -LiteralPath (Join-Path $project $folder) -File -Recurse -Force | ForEach-Object {$_.FullName.Substring($project.Length+1).Replace('\','/')}})
if(@(Compare-Object @($sources.files.path | Sort-Object) @($paths | Sort-Object)).Count -or @($sources.files | Where-Object {(Get-FileHash -LiteralPath (Join-Path $project $_.path)).Hash.ToLowerInvariant() -ne $_.sha256}).Count){throw '20の制作物がビルド時と一致しません。'}
$capture=Join-Path $build ('Capture_'+(Get-Date -Format 'yyyyMMdd_HHmmss'));New-Item -ItemType Directory -Path $capture | Out-Null
$head=(& git -C $repository rev-parse HEAD).Trim();$dirty=@(& git -C $repository status --porcelain).Count -gt 0;$rows=@();$occurrence=@{abc=0;vat=0};$ordinal=0
foreach($format in @('abc','vat','vat','abc','abc','vat')){
 $number=$occurrence[$format];$occurrence[$format]++;$run=Join-Path $capture ($ordinal.ToString('D2')+'_'+$format);New-Item -ItemType Directory -Path $run | Out-Null
 $log=Join-Path $run 'player.log';$flag=if($number -eq 0){' --capture'}else{''};$arguments='-screen-fullscreen 0 -screen-width 1280 -screen-height 720 -logFile "'+$log+'" --format '+$format+' --run '+$number+' --output "'+$run+'"'+$flag
 $watch=[System.Diagnostics.Stopwatch]::StartNew();$process=Start-Process -FilePath (Join-Path $build 'GreatWave20.exe') -ArgumentList $arguments -WindowStyle Hidden -PassThru
 if(-not $process.WaitForExit(600000)){Stop-Process -Id $process.Id;throw "20の所有プロセスが10分を超えました：$log"};$watch.Stop();$process.Refresh();if($process.ExitCode -ne 0){throw "20の実行失敗：$log"}
 $r=Get-Content -LiteralPath (Join-Path $run 'result.json') -Raw -Encoding UTF8 | ConvertFrom-Json;if(-not $r.passed){throw "20の実測が不合格です：$run"}
 $rows+= [ordered]@{ordinal=$ordinal;format=$format;formatRun=$number;directory=$run.Substring($repository.Length+1).Replace('\','/');processLifetimeSeconds=$watch.Elapsed.TotalSeconds;exitCode=$process.ExitCode;captureIncluded=($number -eq 0)}
 Copy-Item -LiteralPath (Join-Path $run 'result.json') -Destination (Join-Path $evidence ('20_run_'+$ordinal.ToString('D2')+'_'+$format+'.json'));Write-Output "20実行 $ordinal $format：合格";$ordinal++
}
$probes=@()
foreach($format in @('abc','vat')){
 $probe=Join-Path $capture ('present_'+$format);New-Item -ItemType Directory -Path $probe | Out-Null
 $log=Join-Path $probe 'player.log';$arguments='-screen-fullscreen 0 -screen-width 1280 -screen-height 720 -logFile "'+$log+'" --format '+$format+' --output "'+$probe+'" --present'
 $process=Start-Process -FilePath (Join-Path $build 'GreatWave20.exe') -ArgumentList $arguments -WindowStyle Hidden -PassThru
 if(-not $process.WaitForExit(120000)){Stop-Process -Id $process.Id;throw '通常frame診断timeout'};$process.Refresh();if($process.ExitCode -ne 0){throw '通常frame診断失敗'}
 Copy-Item -LiteralPath (Join-Path $probe 'present_probe.json') -Destination (Join-Path $evidence ('20_present_probe_'+$format+'.json'));$probes+=@{format=$format;directory=$probe.Substring($repository.Length+1).Replace('\','/');exitCode=0}
}
@{gitHeadAtRun=$head;gitDirtyAtRun=$dirty;captureDirectory=$capture;order=$rows;presentProbes=$probes;osFileCacheControlled=$false;method_ja='各形式3回。新しいプロセス初回読み込みであり、OS/GPU cacheを消去したcold disk試験ではない。'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $evidence '20_run_order.json') -Encoding utf8
foreach($format in @('abc','vat')){
 $dir=Join-Path $capture $(if($format -eq 'abc'){'00_abc'}else{'01_vat'})
 Copy-Item -LiteralPath (Join-Path $dir 'first_visible.png') -Destination (Join-Path $evidence ('20_'+$format+'_wide_first.png'))
 & $Ffmpeg -v error -y -framerate 24 -i (Join-Path $dir 'frame_%04d.png') -frames:v 48 -c:v libx264 -crf 20 -pix_fmt yuv420p -movflags +faststart (Join-Path $evidence ('20_'+$format+'_2s.mp4'));if($LASTEXITCODE -ne 0){throw '20動画符号化失敗'}
 & $Ffmpeg -v error -i (Join-Path $evidence ('20_'+$format+'_2s.mp4')) -f null -;if($LASTEXITCODE -ne 0){throw '20動画復号失敗'}
 foreach($k in @(0,24,48)){Copy-Item -LiteralPath (Join-Path $dir ('frame_'+$k.ToString('D4')+'.png')) -Destination (Join-Path $evidence ('20_'+$format+'_'+$k.ToString('D3')+'.png'))}
 foreach($f in Get-ChildItem -LiteralPath $dir -File -Filter 'stereo_*.png'){Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $evidence ('20_'+$format+'_'+$f.Name))}
}
& 'G:\AI\TaskEnvironments\greatwave_houdini_mcp\.venv\Scripts\python.exe' (Join-Path $PSScriptRoot 'Summarize_Decision20.py')
if($LASTEXITCODE -ne 0){throw '20集計失敗'}
& (Join-Path $PSScriptRoot 'Write_Decision20_Provenance.ps1')
Write-Output "20測定・実画像：$capture"
