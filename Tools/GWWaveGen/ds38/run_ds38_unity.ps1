# 設計38 第「輪郭線」部：Unity batchmode を1回実行する（設計37 の run_ds37_unity.ps1 を写し、ログの置き場所を Build/Design/38/outlines/unity/logs、
# ロックの印を DS38O に変えたもの。同じプロジェクトで Unity は1プロセスだけ。unity.lock の手順・30分の上限は同じ）。
# 使い方（リポジトリ根で）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds38/run_ds38_unity.ps1 -Method GreatWave.Design38.EditorTools.DS38Render.Render -Log main -Extra "-ds38Out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/38/outlines/unity"
# 引数は Extra にそのまま渡す（DS38Render.cs の冒頭）。Unity/Build/unity.lock を排他的に作ってから起動し、終了後（失敗時も）すぐに消す。30分を超えたら止める。
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
$logFile = Join-Path $project ("Build\Design\38\outlines\unity\logs\unity_ds38o_" + $Log + ".log")
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
            New-Item -ItemType File -Path $lock -Value ("DS38O " + $Log + " " + (Get-Date).ToUniversalTime().ToString('o')) -ErrorAction Stop | Out-Null
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
"DS38O_UNITY method=$Method exit=$code seconds=$([int]$sw.Elapsed.TotalSeconds) log=$logFile"
if ($code -ne 0) { exit $code }
