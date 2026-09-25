# 編号23 第2部「較正門（Unity 側）と M1 Revision01 の基線差」を最初から作り直す。
# 1) 評価器の自己テスト（第1部の較正項目）を回し直す
# 2) Unity 6000.4.3f1 の batchmode で、標識 5 点・平塗り色区・M1 Revision01 基線を PaintingCam v1 から描く
#    （出力は Unity/Build/ArtFirst/23、Git 対象外。M1 Revision01 シーンは保存しない）
# 3) gate_part2.py で標識位置と色を測り、評価器で基線差を出し、Docs/Evidence/ArtFirst/23 へまとめる
# Unity は同じプロジェクトで 1 プロセスだけ動かす。1 回の計算は 30 分以内（超えたら止める）。
param([string]$Unity = 'E:\6000.4.3f1\Editor\Unity.exe')
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath $repo
$build = Join-Path $repo 'Unity\Build\ArtFirst\23'
New-Item -ItemType Directory -Force -Path $build | Out-Null

& py -3.10 Tools/PaintingTruth/evaluate.py --selftest --out-dir Docs/Evidence/ArtFirst/23
if ($LASTEXITCODE -ne 0) { throw '自己テスト（第1部）が不合格です。' }

if (Test-Path -LiteralPath (Join-Path $repo 'Unity\Temp\UnityLockfile')) { throw 'Unity プロジェクトが別のプロセスで開かれています。' }
$log = Join-Path $build 'unity_af23_gate.log'
$arguments = @('-batchmode', '-projectPath', (Join-Path $repo 'Unity'), '-executeMethod',
    'GreatWave.ArtFirst.EditorTools.AF23CalibrationGate.RunAll', '-logFile', $log, '-quit')
$process = Start-Process -FilePath $Unity -ArgumentList $arguments -PassThru
if (-not $process.WaitForExit(1800000)) { Stop-Process -Id $process.Id; throw "30 分を超えたため停止しました：$log" }
if ($process.ExitCode -ne 0) { throw "Unity の描画に失敗しました：$log" }

& py -3.10 Tools/PaintingTruth/gate_part2.py
if ($LASTEXITCODE -ne 0) { throw '較正門の測定または基線差の評価に失敗しました（較正門の不合格を含む）。' }
Write-Output "編号23 第2部の再生成が終わりました：$(Join-Path $repo 'Docs\Evidence\ArtFirst\23')"
