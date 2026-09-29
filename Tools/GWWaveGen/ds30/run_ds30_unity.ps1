# 設計30 第B部：Unity batchmode を1回実行する（設計29修正01 の run_ds29r01_unity.ps1 を写し、ログの置き場所を Build/Design/30/logs、
# ロックの印を DS30 に変え、引数を DS30Render のものにしたもの。同じプロジェクトで Unity は1プロセスだけ。unity.lock の手順・30分の上限は同じ）。
# 使い方（リポジトリ根で）：
#   単発再生（主役波＋周りの海）：powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds30/run_ds30_unity.ps1 -Method GreatWave.Design30.EditorTools.DS30Render.Render -Log single -Extra "-ds30Name single -ds30Sea Build/Design/30/sea -ds30Boat Build/Design/30/sea/boat_support.json"
#   主役波だけ（元の平らな海、第A部の前の確かめ）：-Log hero_only -Extra "-ds30Name hero_only -ds30Sea none -ds30Skip scene"
#   Play モードで 1 回再生（場面を保存した後）：-NoQuit -Method GreatWave.Design30.EditorTools.DS30PlayModeCheck.Run -Log playmode -Extra "-ds30Out Build/Design/30/unity/playmode"（-NoQuit は -quit を付けない。Editor が自分で閉じる）
# 引数は Extra にそのまま渡す（DS30Render.cs の冒頭）。Unity/Build/unity.lock を排他的に作ってから起動し、終了後（失敗時も）すぐに消す。30分を超えたら止める。
# ログは Unity/Build/Design/30/logs/unity_ds30_<Log>.log。ロックがあれば60秒ごとに待ち、60分より古いロックは消さずに止めて報告する。
param(
    [Parameter(Mandatory = $true)][string]$Method,
    [Parameter(Mandatory = $true)][string]$Log,
    [string]$Extra = '',
    [switch]$NoQuit,
    [string]$Unity = 'E:\6000.4.3f1\Editor\Unity.exe',
    [int]$TimeoutMinutes = 30,
    [int]$LockWaitMinutes = 20
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$project = Join-Path $repo 'Unity'
$lock = Join-Path $project 'Build\unity.lock'
$logFile = Join-Path $project ("Build\Design\30\logs\unity_ds30_" + $Log + ".log")
New-Item -ItemType Directory -Force -Path (Split-Path $logFile) | Out-Null
if ($TimeoutMinutes -gt 30) { throw '1回の計算は30分以内（AGENTS.md の時間枠と損切り）。' }

function Test-UnityRunning {
    $p = Get-CimInstance Win32_Process -Filter "Name='Unity.exe'" | Where-Object { $_.CommandLine -and (($_.CommandLine -match [regex]::Escape('GreatWave_2026_Fresh\Unity')) -or ($_.CommandLine -match [regex]::Escape('GreatWave_2026_Fresh/Unity'))) }
    return [bool]$p
}

$deadline = (Get-Date).AddMinutes($LockWaitMinutes)
$acquired = $false
while (-not $acquired) {
    if (Test-Path $lock) {
        $age = (Get-Date) - (Get-Item $lock).LastWriteTime
        if ($age.TotalMinutes -gt 60) { throw ("unity.lock が60分より古い（" + [int]$age.TotalMinutes + "分）。消さずに報告する: " + (Get-Content $lock -Raw)) }
    }
    elseif (-not (Test-UnityRunning)) {
        try {
            New-Item -ItemType File -Path $lock -Value ("DS30 " + $Log + " " + (Get-Date).ToUniversalTime().ToString('o')) -ErrorAction Stop | Out-Null
            $acquired = $true
            break
        } catch { }
    }
    if ((Get-Date) -gt $deadline) { throw 'unity.lock を取得できない（待ち時間の上限）。' }
    Start-Sleep -Seconds 60
}
$sw = [Diagnostics.Stopwatch]::StartNew()
$code = -1
try {
    $uargs = @('-batchmode', '-projectPath', ('"' + $project + '"'), '-executeMethod', $Method, '-logFile', ('"' + $logFile + '"'))
    if (-not $NoQuit) { $uargs += '-quit' }
    if ($Extra) { $uargs += ($Extra -split '\s+' | Where-Object { $_ -ne '' }) }
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
"DS30_UNITY method=$Method exit=$code seconds=$([int]$sw.Elapsed.TotalSeconds) log=$logFile"
if ($code -ne 0) { exit $code }
