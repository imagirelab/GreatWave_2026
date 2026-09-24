param([string]$Ffmpeg = 'G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe')
$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot
$build = Join-Path $repository 'Unity\Builds\M0'
$player = Join-Path $build 'GreatWaveM0.exe'
$capture = Join-Path $build ('Capture_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
$evidence = Join-Path $repository 'Docs\Evidence\M0'
if (-not (Test-Path -LiteralPath $player)) { throw '先にBuild_M0.ps1でビルドしてください。' }
if (-not (Test-Path -LiteralPath $Ffmpeg)) { throw '動画を作るffmpegが見つかりません。' }
$sourceManifest = Get-Content -LiteralPath (Join-Path $evidence '10_build_sources.json') -Raw | ConvertFrom-Json
$sourceChanges = @($sourceManifest.files | Where-Object {
    (Get-FileHash -LiteralPath (Join-Path (Join-Path $repository 'Unity') $_.path) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $_.sha256
})
if ($sourceChanges.Count) { throw '現在のソースがビルド時と異なります。再ビルド後に記録してください。' }
New-Item -ItemType Directory -Force -Path $capture, $evidence | Out-Null
$log = Join-Path $capture 'player.log'
$arguments = '-screen-fullscreen 0 -screen-width 1280 -screen-height 720 -logFile "' + $log + '" --capture-dir "' + $capture + '"'
$captureGitHead = (& git -C $repository rev-parse HEAD).Trim()
$captureGitDirty = @(& git -C $repository status --porcelain).Count -gt 0
$process = Start-Process -FilePath $player -ArgumentList $arguments -WindowStyle Hidden -PassThru
if (-not $process.WaitForExit(180000)) {
    Stop-Process -Id $process.Id
    throw "記録が180秒以内に終了しなかったため、この実行だけを停止しました：$log"
}
$process.Refresh()
if ($process.ExitCode -ne 0) { throw "PC入力・画像記録に失敗しました：$log" }
$report = Get-Content -LiteralPath (Join-Path $capture 'capture_report.json') -Raw | ConvertFrom-Json
if (-not $report.passed -or $report.capturedFrames -ne 480) { throw '480枚の実画像と入力検査の合格を確認できません。' }
& $Ffmpeg -y -framerate 24 -i (Join-Path $capture 'frame_%04d.png') -c:v libx264 -crf 20 -pix_fmt yuv420p -movflags +faststart (Join-Path $evidence 'M0_Desktop_Walkthrough.mp4')
if ($LASTEXITCODE -ne 0) { throw '動画の符号化に失敗しました。' }
Copy-Item -LiteralPath (Join-Path $capture 'frame_0000.png') -Destination (Join-Path $evidence 'M0_Seated.png')
Copy-Item -LiteralPath (Join-Path $capture 'frame_0192.png') -Destination (Join-Path $evidence 'M0_Boat_Exterior.png')
Copy-Item -LiteralPath (Join-Path $capture 'frame_0312.png') -Destination (Join-Path $evidence 'M0_Calibration.png')
Copy-Item -LiteralPath (Join-Path $capture 'capture_report.json') -Destination (Join-Path $evidence '10_capture_report.json')
& (Join-Path $PSScriptRoot 'Write_M0_Provenance.ps1') -CaptureDirectory $capture -CaptureGitHead $captureGitHead -CaptureGitDirty $captureGitDirty
Write-Output "記録完了：$evidence"
Write-Output "元の連番と実行ログ：$capture"
