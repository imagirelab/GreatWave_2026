# 番号26修正01「唇を波峰方向へ延ばし、波峰全体を巻かせる（45°）」を最初から作り直す。
# 1) gw_wavegen v2（numpy）で K* を書き出す（Unity/Build/ArtFirst/26修正01/kstar、Git 対象外）
# 2) 機位の JSON を書き、Unity 6000.4.3f1 の batchmode で AF26R01_KStar.unity を作って描く（run_af26r01_unity.ps1 が unity.lock を作ってから 1 プロセスだけ動かし、終わったら必ず消す）
# 3) 参照モデル（Q5）の比較の numpy 側（SHA-256 を照合してから一時キャッシュを作る。-SkipReference で省略）
# 4) Blender 5.2.2 ヘッドレスでメッシュの検査・座席 v1 からの 5 万本の射線・参照モデルとの並べ図
# 5) 評価器（ID モード）・図・metrics.json・run.json を Docs/Evidence/ArtFirst/26R01 へまとめる。最後に一時キャッシュを消す
# 出力先のフォルダー名「26修正01」はファイルの文字コードに左右されないよう、文字コード番号から組み立てる。
param([string]$Blender = 'G:\SteamLibrary\steamapps\common\Blender\blender.exe',
      [string]$ReferenceObj = 'G:\research\model\wave_repair_zbrush2.obj',
      [string]$TempDir = (Join-Path $env:TEMP 'af26r01_q5'),
      [switch]$SkipReference, [switch]$KeepTemp)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath $repo
$numDir = '26' + [char]0x4FEE + [char]0x6B63 + '01'
$build = 'Unity/Build/ArtFirst/' + $numDir

& py -3.10 Tools/GWWaveGen/gw_wavegen_v2.py
if ($LASTEXITCODE -ne 0) { throw 'gw_wavegen_v2 の書き出しに失敗しました。' }
& py -3.10 Tools/GWWaveGen/af26r01_views.py
if ($LASTEXITCODE -ne 0) { throw '機位の JSON の書き出しに失敗しました。' }
& powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/run_af26r01_unity.ps1 -Method GreatWave.ArtFirst.EditorTools.AF26R01KStar.BuildAndRender -Log build_render
if ($LASTEXITCODE -ne 0) { throw 'Unity の描画に失敗しました。' }

$seat = Get-Content -Raw -Encoding UTF8 'Tools/GWContext/seat_v1.json' | ConvertFrom-Json
$e = $seat.seat.eye_world; $l = $seat.view.qa_hemisphere_look_world
$bargs = @('--background', '--factory-startup', '--python-exit-code', '1', '--python', 'Tools/GWWaveGen/af26r01_blender.py', '--',
           ($build + '/kstar'), 'Unity/Build/ArtFirst/26/kstar', ($build + '/blender'), ($build + '/af26r01_views.json'),
           $e[0], $e[1], $e[2], $l[0], $l[1], $l[2])
if (-not $SkipReference) {
  New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
  $align = 'Docs/Evidence/ArtFirst/26/reference/align_B_upright.json'
  & py -3.10 Tools/GWWaveGen/af26r01_reference.py --obj $ReferenceObj --align $align --tmp-dir $TempDir
  if ($LASTEXITCODE -ne 0) { throw '参照モデルの比較（numpy）に失敗しました。' }
  $bargs += @($ReferenceObj, $align, (Join-Path $TempDir 'ref_selected_world.npy'))
}
& $Blender @bargs
if ($LASTEXITCODE -ne 0) { throw 'Blender の検査に失敗しました。' }
& py -3.10 Tools/GWWaveGen/af26r01_evidence.py
if ($LASTEXITCODE -ne 0) { throw '証拠のまとめに失敗しました。' }
if ((-not $SkipReference) -and (-not $KeepTemp)) { Remove-Item -LiteralPath $TempDir -Recurse -Force }
Write-Output ("番号26修正01 の再生成が終わりました：" + (Join-Path $repo 'Docs\Evidence\ArtFirst\26R01'))
