# 設計28修正01 試行F：Unity batchmode を1回実行する（試行A の run_ds28r01_unity.ps1 を写し、ログの置き場所だけを Build/Design/28R01F/logs に変えたもの。
# 同じプロジェクトで Unity は1プロセスだけ。unity.lock の手順・30分の上限・ロックの待ち方は同じ）。再生器は設計27 の DS27Formation と設計28 の DS28ReviewView（どちらも変えない）。
# 使い方（リポジトリ根で）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds28r01/run_ds28r01_unity.ps1 -Method GreatWave.Design27.EditorTools.DS27Formation.RenderOnly -Log art_on_default -Version art_on -Warp default -Package Build/Design/28R01/art_on -WarpFile ../Tools/GWWaveGen/ds28r01/timewarp_default.json -OutDir Build/Design/28R01/art_on_default
#   任意：-Stills "a=-4.367,b=-3.517" -Views "painting,seat,side_left" -Skip "frames" -CaptureMax 120 -Extra "-ds28HideContext 1"（空白で区切った追加の引数を Unity へそのまま渡す）
# Unity/Build/unity.lock を排他的に作ってから起動し、終了後（失敗時も）すぐに消す。30分を超えたら止める。ロックがあれば60秒ごとに待ち、60分より古いロックは消さずに止めて報告する。
# ログは Unity/Build/Design/28R01F/logs/unity_ds28r01f_<Log>.log。
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
$logFile = Join-Path $project ("Build\Design\28R01F\logs\unity_ds28r01f_" + $Log + ".log")
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
            New-Item -ItemType File -Path $lock -Value ("DS28R01F " + $Log + " " + (Get-Date).ToUniversalTime().ToString('o')) -ErrorAction Stop | Out-Null
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
"DS28R01F_UNITY method=$Method exit=$code seconds=$([int]$sw.Elapsed.TotalSeconds) log=$logFile"
if ($code -ne 0) { exit $code }
