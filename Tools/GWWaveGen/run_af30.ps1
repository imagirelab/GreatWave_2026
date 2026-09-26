# 番号30「形成の動き K0→K*」を最初から作り直す（リポジトリの根で）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/run_af30.ps1 [-SkipUnity] [-SkipBlender]
# 1) af30_formation.py：rig（af30_rig.json）→ 断面の図・keypose（15 Hz、適応的な中点）・連続性の検査一式（30 Hz）・Blender 用のフレーム
# 2) Blender 5.2.2 ヘッドレス：途中のフレームのメッシュ検査と座席 v1 からの 5 万本の射線（af30_blender.py）
# 3) Unity batchmode（unity.lock を排他的に作って 1 プロセスだけ。run_af30_unity.ps1）：AF30Formation.BuildAndRender
# 4) af30_tstar_eval.py：t* を番号28修正01 と同じ手順で測り直す
# 5) af30_evidence.py：照合・座席の項目・図・動画・metrics.json・run.json を Docs/Evidence/ArtFirst/30 へ
# 必要なもの：26修正01 の K*（Unity/Build/ArtFirst/26修正01/kstar/）、28修正01 の焼き込み（Unity/Build/ArtFirst/28修正01/）。
param([switch]$SkipUnity, [switch]$SkipBlender, [string]$Blender = 'G:\SteamLibrary\steamapps\common\Blender\blender.exe')
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $repo
$env:PYTHONIOENCODING = 'utf-8'
$sw = [Diagnostics.Stopwatch]::StartNew()

& py -3.10 Tools/GWWaveGen/af30_formation.py --stage all
if ($LASTEXITCODE -ne 0) { throw 'af30_formation.py に失敗しました。' }

if (-not $SkipBlender) {
    $seat = Get-Content Tools/GWContext/seat_v1.json -Raw -Encoding UTF8 | ConvertFrom-Json
    $e = $seat.seat.eye_world; $l = $seat.view.qa_hemisphere_look_world
    New-Item -ItemType Directory -Force -Path Unity/Build/ArtFirst/30/blender | Out-Null
    & $Blender --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/af30_blender.py -- Unity/Build/ArtFirst/30/frames Unity/Build/ArtFirst/30/blender/af30_blender_qa.json $e[0] $e[1] $e[2] $l[0] $l[1] $l[2]
    if ($LASTEXITCODE -ne 0) { throw 'Blender の検査に失敗しました。' }
}

if (-not $SkipUnity) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/run_af30_unity.ps1 -Method GreatWave.ArtFirst.EditorTools.AF30Formation.BuildAndRender -Log build_render
    if ($LASTEXITCODE -ne 0) { throw 'Unity の組み立て・描画に失敗しました。' }
}

& py -3.10 Tools/GWWaveGen/af30_tstar_eval.py
if ($LASTEXITCODE -ne 0) { throw 't* の再測定に失敗しました。' }
& py -3.10 Tools/GWWaveGen/af30_evidence.py
if ($LASTEXITCODE -ne 0) { throw '証拠のまとめに失敗しました。' }
Write-Output ("番号30 の再生成が終わりました（" + [int]$sw.Elapsed.TotalSeconds + " 秒）：" + (Join-Path $repo 'Docs\Evidence\ArtFirst\30'))
