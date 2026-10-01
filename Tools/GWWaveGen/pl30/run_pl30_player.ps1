# 仕上げ30：PL30_Release から作った Release のプレイヤー（Build/Polish/30/release/player/GreatWave50.exe）を、設計50 の自動の試しの引数で 1 回動かす（run_pl29_player.ps1 を写し、exe と出力の場所と印だけを替えたもの）
#   （ds50/run_ds50_player.ps1 を写し、exe と出力の場所と印だけを替えたもの）。
#   開発者の操作は挟まない（プレイヤーの中の DS50AutoTest が Input System の仮想のキーボードで利用者と同じキーを押す）。
#   作業ディレクトリは出力のフォルダー（プロジェクトの外の場所から起動しても読めることの確かめ。データは exe の横の StreamingAssets/gwdata）。
#   同じ時に Unity の Editor が動いていないことを確かめる（H2 のフレーム時間を乱さないため）。
# 使い方（リポジトリ根で）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/pl30/run_pl30_player.ps1 -Tag main
#   powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/pl30/run_pl30_player.ps1 -Tag capture -Capture
#   powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/pl30/run_pl30_player.ps1 -Tag vr -Vr
param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [string]$Scenario = 'main',
    [switch]$Capture,
    [switch]$Vr,
    [int]$Width = 1920,
    [int]$Height = 1080,
    [int]$TimeoutSeconds = 900
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$exe = Join-Path $repo 'Unity\Build\Polish\30\release\player\GreatWave50.exe'
$out = Join-Path $repo ('Unity\Build\Polish\30\release\runs\' + $Tag)
if ($out -match 'Design\\50' -or $out -match 'Polish\\29') { throw '設計50・仕上げ29 の記録のフォルダーへは書かない' }
if (-not (Test-Path $exe)) { throw ('exe がない: ' + $exe) }
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory -Force -Path $out | Out-Null
$editor = Get-CimInstance Win32_Process -Filter "Name='Unity.exe'" | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'GreatWave_2026_Fresh') }
if ($editor) { throw 'Unity の Editor が動いている（H2 を乱すので待つ）。' }
$args2 = @('-screen-fullscreen', '0', '-screen-width', "$Width", '-screen-height', "$Height", '-logFile', ('"' + (Join-Path $out 'player.log') + '"'),
           '--ds50auto', $Scenario, '--ds50out', ('"' + $out + '"'))
if ($Capture) { $args2 += '--ds50capture' }
if ($Vr) { $args2 += '--vr' }
$t0 = (Get-Date).ToUniversalTime()
$sw = [Diagnostics.Stopwatch]::StartNew()
$p = Start-Process -FilePath $exe -ArgumentList $args2 -WorkingDirectory $out -PassThru
$null = $p.Handle
$timedOut = $false
if (-not $p.WaitForExit($TimeoutSeconds * 1000)) { $p.Kill(); $timedOut = $true }
$code = if ($timedOut) { -1 } else { $p.ExitCode }
$sha = (Get-FileHash -Algorithm SHA256 $exe).Hash.ToLower()
$rec = [ordered]@{ tag = $Tag; exe = $exe; exeSha256 = $sha; args = ($args2 -join ' '); workingDirectory = $out; utcStart = $t0.ToString('o');
    seconds = [math]::Round($sw.Elapsed.TotalSeconds, 3); exitCode = $code; timedOut = $timedOut; developerInputs = 0;
    noteJa = 'プレイヤーの起動と終わりの待ちだけを行った。途中の操作はプレイヤーの中の自動の試し（仮想のキーボード）だけ。' }
($rec | ConvertTo-Json -Depth 4) | Set-Content -Encoding utf8 (Join-Path $out 'launch.json')
"PL30_PLAYER tag=$Tag exit=$code seconds=$([int]$sw.Elapsed.TotalSeconds) timedOut=$timedOut out=$out"
