# 設計29：Unity batchmode を1回実行する（設計28 の run_ds28_unity.ps1 を写し、ログの置き場所を Build/Design/29/logs、ロックの印を DS29 に変えたもの。
# 同じプロジェクトで Unity は1プロセスだけ。unity.lock の手順・30分の上限は同じ）。描画は設計29 の DS29Render（設計27 の場面をメモリの上だけで使い、保存しない）。
# 使い方（リポジトリ根で）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds29/run_ds29_unity.ps1 -Method GreatWave.Design29.EditorTools.DS29Render.Render -Log full_240x400 -Package Build/Design/29/r01/full_240x400 -OutDir Build/Design/29/unity/full_240x400 -Views "painting,seat_toward_wave,side_left" -Extra "-ds29Name full_240x400"
#   設計28 の K* の格子（比較の基準）：-Package Build/Design/28/art_on -Extra "-ds29Name src_d28 -ds29MeshFromPackage 0"
#   任意：-Stills "a=-4.433,b=-3.500" -Skip "t28,capture,stills,video,timing" -Extra "-ds29StillViews painting,seat -ds29TimingFrames 180 -ds29CaptureMax 16"
# Unity/Build/unity.lock を排他的に作ってから起動し、終了後（失敗時も）すぐに消す。30分を超えたら止める。ログは Unity/Build/Design/29/logs/unity_ds29_<Log>.log。
# ロックがあれば60秒ごとに待ち、60分より古いロックは消さずに止めて報告する。
param(
    [Parameter(Mandatory = $true)][string]$Method,
    [Parameter(Mandatory = $true)][string]$Log,
    [string]$Version = '',
    [string]$Warp = '',
    [string]$Package = '',
    [string]$WarpFile = '',
    [string]$OutDir = '',
    [string]$Stills = '',
    [string]$Views = '',
    [string]$Skip = '',
    [int]$CaptureMax = 0,
    [string]$Extra = '',
    [string]$Unity = 'E:\6000.4.3f1\Editor\Unity.exe',
    [int]$TimeoutMinutes = 30,
    [int]$LockWaitMinutes = 20
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$project = Join-Path $repo 'Unity'
$lock = Join-Path $project 'Build\unity.lock'
$logFile = Join-Path $project ("Build\Design\29\logs\unity_ds29_" + $Log + ".log")
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
            New-Item -ItemType File -Path $lock -Value ("DS29 " + $Log + " " + (Get-Date).ToUniversalTime().ToString('o')) -ErrorAction Stop | Out-Null
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
    $uargs = @('-batchmode', '-projectPath', ('"' + $project + '"'), '-executeMethod', $Method, '-logFile', ('"' + $logFile + '"'), '-quit')
    if ($Version) { $uargs += @('-ds27Version', $Version) }
    if ($Warp) { $uargs += @('-ds27Warp', $Warp) }
    if ($Package) { $uargs += @('-ds27Package', ('"' + $Package + '"')) }
    if ($WarpFile) { $uargs += @('-ds27WarpFile', ('"' + $WarpFile + '"')) }
    if ($OutDir) { $uargs += @('-ds27Out', ('"' + $OutDir + '"')) }
    if ($Stills) { $uargs += @('-ds27Stills', $Stills) }
    if ($Views) { $uargs += @('-ds27Views', $Views) }
    if ($Skip) { $uargs += @('-ds27Skip', $Skip) }
    if ($CaptureMax -gt 0) { $uargs += @('-ds27CaptureMax', [string]$CaptureMax) }
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
"DS29_UNITY method=$Method exit=$code seconds=$([int]$sw.Elapsed.TotalSeconds) log=$logFile"
if ($code -ne 0) { exit $code }
