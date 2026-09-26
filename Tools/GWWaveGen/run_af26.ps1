# 番号26「主役波の終態 K*（立体解釈 30°／45°／60°）」を最初から作り直す。
# 1) gw_wavegen v1（numpy）で K* 3 案を書き出す（Unity/Build/ArtFirst/26/kstar、Git 対象外）
# 2) Unity 6000.4.3f1 の batchmode で AF26_KStar.unity を作り、原画視点・ID 画像・船上・側面・背面・真上を PC オフスクリーン描画する
#    （Unity/Build/unity.lock を作ってから 1 プロセスだけ動かし、終わったら必ず消す。1 回 30 分以内）
# 3) Blender 5.2.2 ヘッドレスでメッシュを検査し、座席から 5 万本の射線を出す
# 4) 参照モデル（Q5）との比較（記録のみ。-SkipReference で省略）。参照モデルは読むだけで、一時キャッシュは最後に消す
# 5) 評価器（ID モード）・重ね図・metrics.json・run.json を Docs/Evidence/ArtFirst/26 へまとめる
param([string]$Unity = 'E:\6000.4.3f1\Editor\Unity.exe',
      [string]$Blender = 'G:\SteamLibrary\steamapps\common\Blender\blender.exe',
      [string]$ReferenceObj = 'G:\research\model\wave_repair_zbrush2.obj',
      [string]$TempDir = (Join-Path $env:TEMP 'af26_q5'),
      [switch]$SkipReference, [switch]$KeepTemp)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath $repo
$build = Join-Path $repo 'Unity\Build\ArtFirst\26'
New-Item -ItemType Directory -Force -Path $build | Out-Null

& py -3.10 Tools/GWWaveGen/gw_wavegen_v1.py
if ($LASTEXITCODE -ne 0) { throw 'gw_wavegen_v1 の書き出しに失敗しました。' }

$lock = Join-Path $repo 'Unity\Build\unity.lock'
$running = Get-CimInstance Win32_Process -Filter "Name='Unity.exe'" | Where-Object { $_.CommandLine -match [regex]::Escape((Join-Path $repo 'Unity')) }
if ($running) { throw 'このプロジェクトの Unity が動いています。' }
New-Item -ItemType File -Path $lock -Value ("AF26 " + (Get-Date).ToUniversalTime().ToString('o')) -ErrorAction Stop | Out-Null
try {
  $log = Join-Path $build 'unity_af26.log'
  $p = Start-Process -FilePath $Unity -ArgumentList @('-batchmode', '-projectPath', (Join-Path $repo 'Unity'), '-executeMethod',
      'GreatWave.ArtFirst.EditorTools.AF26KStar.BuildAndRender', '-logFile', $log, '-quit') -PassThru
  if (-not $p.WaitForExit(1800000)) { Stop-Process -Id $p.Id -Force; throw "30 分を超えたため停止しました：$log" }
  if ($p.ExitCode -ne 0) { throw "Unity の描画に失敗しました：$log" }
} finally {
  Remove-Item -LiteralPath $lock -Force -ErrorAction SilentlyContinue
}

$layout = Get-Content -Raw -Encoding UTF8 'Docs/Evidence/M1/Revision01/15_revision_layout.json' | ConvertFrom-Json
$e = $layout.eyeWorld
& $Blender --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/af26_blender_qa.py -- (Join-Path $build 'kstar') (Join-Path $build 'af26_blender_qa.json') $e.x $e.y $e.z -7 5 3
if ($LASTEXITCODE -ne 0) { throw 'Blender の検査に失敗しました。' }

if (-not $SkipReference) {
  New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
  $align = Join-Path $repo 'Docs\Evidence\ArtFirst\26\reference\align_B_upright.json'
  & py -3.10 Tools/GWWaveGen/af26_reference.py --obj $ReferenceObj --align $align --out-dir (Join-Path $build 'ref') --tmp-dir $TempDir
  if ($LASTEXITCODE -ne 0) { throw '参照モデルの比較（numpy）に失敗しました。' }
  & $Blender --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/af26_blender_ref.py -- $ReferenceObj $align (Join-Path $build 'kstar') (Join-Path $TempDir 'ref_selected_world.npy') (Join-Path $build 'ref')
  if ($LASTEXITCODE -ne 0) { throw '参照モデルの比較（Blender）に失敗しました。' }
  if (-not $KeepTemp) { Remove-Item -LiteralPath $TempDir -Recurse -Force }
}

& py -3.10 Tools/GWWaveGen/af26_evidence.py
if ($LASTEXITCODE -ne 0) { throw '証拠のまとめに失敗しました。' }
Write-Output "番号26 の再生成が終わりました：$(Join-Path $repo 'Docs\Evidence\ArtFirst\26')"
