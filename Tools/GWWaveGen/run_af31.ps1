# 番号31「白の出現と縞の追従」を最初から作り直す（リポジトリの根で）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/run_af31.ps1 [-SkipUnity]
# 1) af31_white.py：白の時間場 T_white（af31_white.json）→ 頂点ごとのテクスチャ・UV 空間の検査（30 Hz）
# 2) Unity batchmode（unity.lock を排他的に作って 1 プロセスだけ。run_af31_unity.ps1）：AF31WhiteFormation.BuildAndRender
# 3) af31_tstar_eval.py：t* を番号28修正01 と同じ手順で測り直す（135・177 の終点）
# 4) af31_evidence.py：102・135・176・177 の測定・図・動画・metrics.json・run.json を Docs/Evidence/ArtFirst/31 へ
# 必要なもの：26修正01 の K*、28修正01 の焼き込み、番号30 の keypose（Unity/Build/ArtFirst/30/keypose、run_af30.ps1 で作る）。
param([switch]$SkipUnity)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $repo
$env:PYTHONIOENCODING = 'utf-8'
$sw = [Diagnostics.Stopwatch]::StartNew()

& py -3.10 Tools/GWWaveGen/af31_white.py --stage all
if ($LASTEXITCODE -ne 0) { throw 'af31_white.py に失敗しました。' }

if (-not $SkipUnity) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/run_af31_unity.ps1 -Method GreatWave.ArtFirst.EditorTools.AF31WhiteFormation.BuildAndRender -Log build_render
    if ($LASTEXITCODE -ne 0) { throw 'Unity の組み立て・描画に失敗しました。' }
}

& py -3.10 Tools/GWWaveGen/af31_tstar_eval.py
if ($LASTEXITCODE -ne 0) { throw 't* の再測定に失敗しました。' }
& py -3.10 Tools/GWWaveGen/af31_evidence.py
if ($LASTEXITCODE -ne 0) { throw '証拠のまとめに失敗しました。' }
Write-Output ("番号31 の再生成が終わりました（" + [int]$sw.Elapsed.TotalSeconds + " 秒）：" + (Join-Path $repo 'Docs\Evidence\ArtFirst\31'))
