# 番号28 第B部「SDF 投影ベイク、NPR shader v1、外殻線 v0」を最初から作り直す（第A部の正解は colour_truth.py で先に作っておく）。
# 1) af28_bake_input.py：原画側の符号付き距離・有効域・調色板・線幅（Unity/Build/ArtFirst/28/bake_input、Git 対象外）
# 2) Unity 6000.4.3f1 の batchmode：AF28_NPR.unity を作り、GWProjectionBaker（AF28ProjectionBaker）で 3 案を焼き、描画する
#    （Unity/Build/unity.lock を作ってから 1 プロセスだけ動かし、終わったら必ず消す。1 回 30 分以内）
# 3) af28_evaluate.py：項目ごとの判定・重ね図・metrics.json・run.json を Docs/Evidence/ArtFirst/28 へまとめる
param([string]$Unity = 'E:\6000.4.3f1\Editor\Unity.exe', [switch]$SkipUnity)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
Set-Location -LiteralPath $repo
$build = Join-Path $repo 'Unity\Build\ArtFirst\28'
New-Item -ItemType Directory -Force -Path $build | Out-Null

& py -3.10 Tools/PaintingTruth/colour/af28_bake_input.py
if ($LASTEXITCODE -ne 0) { throw 'af28_bake_input.py に失敗しました。' }

if (-not $SkipUnity) {
  $lock = Join-Path $repo 'Unity\Build\unity.lock'
  $running = Get-CimInstance Win32_Process -Filter "Name='Unity.exe'" | Where-Object { $_.CommandLine -match [regex]::Escape((Join-Path $repo 'Unity')) }
  if ($running) { throw 'このプロジェクトの Unity が動いています。' }
  New-Item -ItemType File -Path $lock -Value ("AF28 " + (Get-Date).ToUniversalTime().ToString('o')) -ErrorAction Stop | Out-Null
  try {
    $log = Join-Path $build 'unity_af28.log'
    $p = Start-Process -FilePath $Unity -ArgumentList @('-batchmode', '-projectPath', (Join-Path $repo 'Unity'), '-executeMethod',
        'GreatWave.ArtFirst.EditorTools.AF28NprScene.BakeBuildAndRender', '-logFile', $log, '-quit') -PassThru
    if (-not $p.WaitForExit(1800000)) { Stop-Process -Id $p.Id -Force; throw "30 分を超えたため停止しました：$log" }
    if ($p.ExitCode -ne 0) { throw "Unity のベイク・描画に失敗しました：$log" }
  } finally {
    Remove-Item -LiteralPath $lock -Force -ErrorAction SilentlyContinue
  }
}

& py -3.10 Tools/PaintingTruth/colour/af28_evaluate.py
if ($LASTEXITCODE -ne 0) { throw '評価と証拠のまとめに失敗しました。' }
Write-Output "番号28 第B部の再生成が終わりました：$(Join-Path $repo 'Docs\Evidence\ArtFirst\28')"
