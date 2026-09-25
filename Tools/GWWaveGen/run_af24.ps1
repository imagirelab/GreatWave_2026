# 編号24「最初の画面：主役波 v0」を最初から作り直す。
# 1) gw_wavegen v0（numpy）で水面シートの全フレームを書き出す（Unity/Build/ArtFirst/24/wave、Git 対象外）
# 2) Unity 6000.4.3f1 の batchmode で新シーンを作り、PaintingCam v1・船上座席・側面を PC オフスクリーン描画する
# 3) 評価器（ID モード）・原画 50% 重ね・MP4・metrics.json・run.json を Docs/Evidence/ArtFirst/24 へまとめる
# Unity は同じプロジェクトで 1 プロセスだけ動かす。1 回の計算は 30 分以内（超えたら止める）。
# ffmpeg の場所は -Ffmpeg で渡す。省略すると af24_evidence.py が環境変数 GW_FFMPEG、なければ既定値を使う。
param([string]$Unity = 'E:\6000.4.3f1\Editor\Unity.exe', [string]$Ffmpeg = '')
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath $repo
$build = Join-Path $repo 'Unity\Build\ArtFirst\24'
New-Item -ItemType Directory -Force -Path $build | Out-Null

& py -3.10 Tools/GWWaveGen/gw_wavegen.py --preview --export
if ($LASTEXITCODE -ne 0) { throw 'gw_wavegen の書き出しに失敗しました。' }

if (Test-Path -LiteralPath (Join-Path $repo 'Unity\Temp\UnityLockfile')) { throw 'Unity プロジェクトが別のプロセスで開かれています。' }
$log = Join-Path $build 'unity_af24_render.log'
$arguments = @('-batchmode', '-projectPath', (Join-Path $repo 'Unity'), '-executeMethod',
    'GreatWave.ArtFirst.EditorTools.AF24FirstLight.BuildAndRender', '-logFile', $log, '-quit')
$process = Start-Process -FilePath $Unity -ArgumentList $arguments -PassThru
if (-not $process.WaitForExit(1800000)) { Stop-Process -Id $process.Id; throw "30 分を超えたため停止しました：$log" }
if ($process.ExitCode -ne 0) { throw "Unity の描画に失敗しました：$log" }

$evidenceArgs = @()
if ($Ffmpeg) { $evidenceArgs += @('--ffmpeg', $Ffmpeg) }
& py -3.10 Tools/GWWaveGen/af24_evidence.py @evidenceArgs
if ($LASTEXITCODE -ne 0) { throw '証拠のまとめに失敗しました。' }
Write-Output "編号24 の再生成が終わりました：$(Join-Path $repo 'Docs\Evidence\ArtFirst\24')"
