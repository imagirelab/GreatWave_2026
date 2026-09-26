# 番号28修正01「新しい K* へ色面を焼き直し、座席確定後に再判定する」を最初から作り直す。
# 1) af28r01_bake_input.py：原画側の入力（番号28 と同じ bytes）と、26修正01 の K* の列の範囲・焼き込み用 UV（UV3）の表
# 2) Unity 6000.4.3f1 の batchmode：AF28R01_NPR.unity を作り、AF28R01ProjectionBaker で 45° を 2 つの外挿の規則で焼き、描画する
#    （Unity/Build/unity.lock を排他的に作ってから 1 プロセスだけ動かし、終わったら失敗しても消す。1 回 30 分以内。
#     ロックがあれば 60 秒ごとに待ち、60 分より古いロックは消さずに止めて報告する）
# 3) af28r01_evaluate.py：項目ごとの判定・図・metrics.json・run.json を Docs/Evidence/ArtFirst/28R01 へまとめる
# 使い方（リポジトリの根で）：powershell -NoProfile -ExecutionPolicy Bypass -File Tools/PaintingTruth/colour/run_af28r01.ps1 [-SkipUnity] [-SkipEvaluate]
# 出力先のフォルダー名「28修正01」はファイルの文字コードに左右されないよう、文字コード番号から組み立てる。
param([string]$Unity = 'E:\6000.4.3f1\Editor\Unity.exe', [switch]$SkipUnity, [switch]$SkipEvaluate, [int]$TimeoutMinutes = 30, [int]$LockWaitMinutes = 20)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
Set-Location -LiteralPath $repo
$project = Join-Path $repo 'Unity'
$numDir = '28' + [char]0x4FEE + [char]0x6B63 + '01'
$build = Join-Path $project ("Build\ArtFirst\" + $numDir)
New-Item -ItemType Directory -Force -Path $build | Out-Null

& py -3.10 Tools/PaintingTruth/colour/af28r01_bake_input.py
if ($LASTEXITCODE -ne 0) { throw 'af28r01_bake_input.py に失敗しました。' }

function Test-UnityRunning {
    $p = Get-CimInstance Win32_Process -Filter "Name='Unity.exe'" | Where-Object { $_.CommandLine -and (($_.CommandLine -match [regex]::Escape('GreatWave_2026_Fresh\Unity')) -or ($_.CommandLine -match [regex]::Escape('GreatWave_2026_Fresh/Unity'))) }
    return [bool]$p
}

if (-not $SkipUnity) {
    $lock = Join-Path $project 'Build\unity.lock'
    $deadline = (Get-Date).AddMinutes($LockWaitMinutes)
    $acquired = $false
    while (-not $acquired) {
        if (Test-Path $lock) {
            $age = (Get-Date) - (Get-Item $lock).LastWriteTime
            if ($age.TotalMinutes -gt 60) { throw ("unity.lock が60分より古い（" + [int]$age.TotalMinutes + "分）。消さずに報告する: " + (Get-Content $lock -Raw)) }
        }
        elseif (-not (Test-UnityRunning)) {
            try {
                New-Item -ItemType File -Path $lock -Value ("AF28R01 " + (Get-Date).ToUniversalTime().ToString('o')) -ErrorAction Stop | Out-Null
                $acquired = $true
                break
            } catch { }
        }
        if ((Get-Date) -gt $deadline) { throw 'unity.lock を取得できない（待ち時間の上限）。' }
        Start-Sleep -Seconds 60
    }
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $code = -1
    $logFile = Join-Path $build 'unity_af28r01.log'
    try {
        $uargs = @('-batchmode', '-projectPath', ('"' + $project + '"'), '-executeMethod', 'GreatWave.ArtFirst.EditorTools.AF28R01NprScene.BakeBuildAndRender', '-logFile', ('"' + $logFile + '"'), '-quit')
        $p = Start-Process -FilePath $Unity -ArgumentList $uargs -PassThru -NoNewWindow
        $null = $p.Handle
        if (-not $p.WaitForExit($TimeoutMinutes * 60 * 1000)) {
            $p.Kill()
            throw ("Unity が " + $TimeoutMinutes + " 分を超えたので止めた。")
        }
        $code = $p.ExitCode
    }
    finally {
        Remove-Item -Path $lock -Force -ErrorAction SilentlyContinue
    }
    "AF28R01_UNITY exit=$code seconds=$([int]$sw.Elapsed.TotalSeconds) log=$logFile"
    if ($code -ne 0) { throw "Unity の焼き込み・描画に失敗しました：$logFile" }
}

if (-not $SkipEvaluate) {
    & py -3.10 Tools/PaintingTruth/colour/af28r01_evaluate.py
    if ($LASTEXITCODE -ne 0) { throw '評価と証拠のまとめに失敗しました。' }
}
Write-Output "番号28修正01 の再生成が終わりました：$(Join-Path $repo 'Docs\Evidence\ArtFirst\28R01')"
