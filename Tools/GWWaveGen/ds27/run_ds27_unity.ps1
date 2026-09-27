# 設計27：Unity batchmode を1回実行する（同じプロジェクトで Unity は1プロセスだけ）。美術優先30 の run_af30_unity.ps1 と同じ手順（unity.lock）。
# 使い方（リポジトリ根で）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds27/run_ds27_unity.ps1 -Method GreatWave.Design27.EditorTools.DS27Formation.BuildAndRender -Log art_on_default -Version art_on -Warp default
#   任意：-Package <パッケージのフォルダー> -WarpFile <時間曲線の表> -OutDir <出力のフォルダー> -Stills "a=-4.2,b=-3.4" -Views "painting,seat,side_left" -Skip "video,frames" -CaptureMax 120
#   （パスは Unity プロジェクト（Unity/）からの相対か絶対。既定はパッケージ Build/Design/27/<版>、表 ../Tools/GWWaveGen/ds27/timewarp_<時間曲線>.json、出力 Build/Design/27/<版>_<時間曲線>）
# Unity/Build/unity.lock を排他的に作ってから起動し、終了後（失敗時も）すぐに消す。30分を超えたら止める。
# ロックがあれば60秒ごとに待ち、60分より古いロックは消さずに止めて報告する。ログは Unity/Build/Design/27/logs/unity_ds27_<Log>.log。
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
    [string]$Unity = 'E:\6000.4.3f1\Editor\Unity.exe',
    [int]$TimeoutMinutes = 30,
    [int]$LockWaitMinutes = 20
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$project = Join-Path $repo 'Unity'
$lock = Join-Path $project 'Build\unity.lock'
$logFile = Join-Path $project ("Build\Design\27\logs\unity_ds27_" + $Log + ".log")
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
            New-Item -ItemType File -Path $lock -Value ("DS27 " + $Log + " " + (Get-Date).ToUniversalTime().ToString('o')) -ErrorAction Stop | Out-Null
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
"DS27_UNITY method=$Method exit=$code seconds=$([int]$sw.Elapsed.TotalSeconds) log=$logFile"
if ($code -ne 0) { exit $code }
