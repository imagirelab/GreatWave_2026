# 仕上げ36：Release のプレイヤーを 1 回動かす（仕上げ35 の pl35_run_player.ps1 を写し、exe と出力を Build/Polish/36/ の下にしたもの。
#   -Mode perf は仕上げ35 の負荷の計測器 PL35PerfProbe（場面に残っている。--pl35perf の時だけ働く）で、t = 11.95 s の画面も撮る）。
#   -Mode auto：設計50 の自動の試し（--ds50auto main）。体験の通しの形成の全区間のフレームの時間（199）を見る。
#   -Mode perf：最大密度の区間 t 11〜12 s の繰り返し（81・112・199 の代理。条件は PL35PerfProbe の一覧）。
#   -Exe で前（仕上げ33修正01 の exe）を渡すと、同じ日に交互に動かした前の値を取れる（perf は仕上げ35 の exe だけが持つ）。
#   -Extra でプレイヤーへ引数を足す（例：--pl35legacy）。
# 使い方（リポジトリ根で）：powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/pl36/pl36_run_player.ps1 -Tag p1 -Mode perf
param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [string]$Exe = '',
    [ValidateSet('auto', 'perf')][string]$Mode = 'perf',
    [string]$Extra = '',
    [int]$Width = 1920,
    [int]$Height = 1080,
    [int]$TimeoutSeconds = 900
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$exe = if ($Exe) { $Exe } else { Join-Path $repo 'Unity\Build\Polish\36\release\player\GreatWave50.exe' }
$out = Join-Path $repo ('Unity\Build\Polish\36\runs\' + $Tag)
if (-not (Test-Path $exe)) { throw ('exe がない: ' + $exe) }
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory -Force -Path $out | Out-Null
$editor = Get-CimInstance Win32_Process -Filter "Name='Unity.exe'" | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'GreatWave_2026_Fresh') }
if ($editor) { throw 'Unity の Editor が動いている（測定を乱すので待つ）。' }
$args2 = @('-screen-fullscreen', '0', '-screen-width', "$Width", '-screen-height', "$Height", '-logFile', ('"' + (Join-Path $out 'player.log') + '"'))
if ($Mode -eq 'auto') { $args2 += @('--ds50auto', 'main', '--ds50out', ('"' + $out + '"')) }
else { $args2 += @('--pl35perf', '-pl35out', ('"' + $out + '"'), '-pl35tag', $Tag) }
if ($Extra) { $args2 += ($Extra -split '\s+' | Where-Object { $_ -ne '' }) }
$t0 = (Get-Date).ToUniversalTime()
$sw = [Diagnostics.Stopwatch]::StartNew()
$p = Start-Process -FilePath $exe -ArgumentList $args2 -WorkingDirectory $out -PassThru
$null = $p.Handle
$timedOut = $false
if (-not $p.WaitForExit($TimeoutSeconds * 1000)) { $p.Kill(); $timedOut = $true }
$code = if ($timedOut) { -1 } else { $p.ExitCode }
$sha = (Get-FileHash -Algorithm SHA256 $exe).Hash.ToLower()
$rec = [ordered]@{ tag = $Tag; mode = $Mode; exe = $exe; exeSha256 = $sha; args = ($args2 -join ' '); workingDirectory = $out; utcStart = $t0.ToString('o');
    seconds = [math]::Round($sw.Elapsed.TotalSeconds, 3); exitCode = $code; timedOut = $timedOut; developerInputs = 0;
    noteJa = 'プレイヤーの起動と終わりの待ちだけを行った。auto は設計50 の自動の試し（仮想のキーボード）、perf は PL35PerfProbe（入口の Begin を呼び、形成の t 11 s から時計を乗っ取る）。' }
($rec | ConvertTo-Json -Depth 4) | Set-Content -Encoding utf8 (Join-Path $out 'launch.json')
"PL36_PLAYER tag=$Tag mode=$Mode exit=$code seconds=$([int]$sw.Elapsed.TotalSeconds) timedOut=$timedOut out=$out"
