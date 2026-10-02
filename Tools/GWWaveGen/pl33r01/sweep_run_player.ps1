# 仕上げ33修正01 変種 SWEEP：Release のプレイヤーを、設計50 の自動の試しの引数で 1 回動かす（仕上げ33 の run_pl33_player.ps1 を写し、
#   exe を引数 -Exe（既定 SWEEP の Build/Polish/33r01/sweep/release/player/GreatWave50.exe）、出力を Build/Polish/33r01/sweep/release/runs/<Tag> にしたもの）。
#   前（仕上げ33）の exe を -Exe で渡すと、同じ日に交互に動かした前の値を SWEEP の作業フォルダーの中に取れる（仕上げ33 の記録のフォルダーへは書かない）。
# 使い方（リポジトリ根で）：powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/pl33r01/sweep_run_player.ps1 -Tag s1 [-Exe <exe>]
param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [string]$Exe = '',
    [string]$Scenario = 'main',
    [switch]$Capture,
    [switch]$Vr,
    [int]$Width = 1920,
    [int]$Height = 1080,
    [int]$TimeoutSeconds = 900
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$exe = if ($Exe) { $Exe } else { Join-Path $repo 'Unity\Build\Polish\33r01\sweep\release\player\GreatWave50.exe' }
$out = Join-Path $repo ('Unity\Build\Polish\33r01\sweep\release\runs\' + $Tag)
if ($out -match 'Design\\50' -or $out -match 'Polish\\29' -or $out -match 'Polish\\30' -or $out -match 'Polish\\31' -or $out -match 'Polish\\32') { throw '設計50・仕上げ29 の記録のフォルダーへは書かない' }
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
"SWEEP_PLAYER tag=$Tag exit=$code seconds=$([int]$sw.Elapsed.TotalSeconds) timedOut=$timedOut out=$out"
