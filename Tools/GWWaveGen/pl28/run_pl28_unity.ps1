# 仕上げ28：Unity batchmode を 1 回実行する（設計29修正01 の run_ds29r01_unity.ps1 を写し、ログの置き場所を Build/Polish/28/logs、ロックの印を PL28 に変えたもの。
# 同じプロジェクトで Unity は 1 プロセスだけ。unity.lock の手順・30 分の上限は同じ）。描画は設計29 の DS29Render（精度の層を読む）。
# 使い方（リポジトリ根で）：F7-1 の無圧縮の静止画（原画視点、30 fps のコマの τ を -Stills に並べる）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/pl28/run_pl28_unity.ps1 -Method GreatWave.Design29.EditorTools.DS29Render.Render -Log f71_F_final -Package Build/Design/28R01F/F_final/art_on -WarpFile Build/Design/28R01F/F_final/timewarp_F_final.json -OutDir Build/Polish/28/motion/f71/unity_F_final -Stills "f0264=-1.3,..." -Skip "t28,capture,video,timing" -Extra "-ds29Name f71_F_final -ds29MeshFromPackage 0 -ds29StillViews painting -ds29KStarGwb Build/Design/29R01/bake_kp/kstar/kstar_a45.gwb -ds29Sdf Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin -ds29Warp Build/Design/29R01/bake_kp/bake/af28r01_uvwarp_a45.json"
# Unity/Build/unity.lock を排他的に作ってから起動し、終了後（失敗時も）すぐに消す。30 分を超えたら止める。ログは Unity/Build/Polish/28/logs/unity_pl28_<Log>.log。
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
$logFile = Join-Path $project ("Build\Polish\28\logs\unity_pl28_" + $Log + ".log")
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
            New-Item -ItemType File -Path $lock -Value ("PL28 " + $Log + " " + (Get-Date).ToUniversalTime().ToString('o')) -ErrorAction Stop | Out-Null
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
"PL28_UNITY method=$Method exit=$code seconds=$([int]$sw.Elapsed.TotalSeconds) log=$logFile"
if ($code -ne 0) { exit $code }
