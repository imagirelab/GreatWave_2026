# 設計29修正01：Unity batchmode を1回実行する（設計29 の run_ds29_unity.ps1 を写し、ログの置き場所を Build/Design/29R01/logs、ロックの印を DS29R01 に変えたもの。
# 同じプロジェクトで Unity は1プロセスだけ。unity.lock の手順・30分の上限は同じ）。描画は設計29 の DS29Render（設計29修正01 で精度の層の引数を足した）。
# 使い方（リポジトリ根で）：
#   精度の層を読む F_final：powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds29r01/run_ds29r01_unity.ps1 -Method GreatWave.Design29.EditorTools.DS29Render.Render -Log f_final -Package Build/Design/28R01F/F_final/art_on -WarpFile Build/Design/28R01F/F_final/timewarp_F_final.json -OutDir Build/Design/29R01/unity/f_final -Stills "m6=-6,m3=-3,m2=-2,m1=-1,m05=-0.5,tstar=0" -Views "painting,seat,seat_toward_wave,side_left" -Skip timing -Extra "-ds29Name f_final -ds29MeshFromPackage 0 -ds29CaptureRange -6,0"
#   設計28 の後方互換（設計29 の src_d28 と同じ引数）：-Log regress_d28 -Package Build/Design/28/art_on -OutDir Build/Design/29R01/unity/regress_d28 -Views "painting,seat_toward_wave,side_left" -Skip timing -Extra "-ds29Name src_d28 -ds29MeshFromPackage 0"
#   設計27 の後方互換：-Method GreatWave.Design27.EditorTools.DS27Formation.RenderOnly -Log regress_d27 -Version art_on -Warp default -OutDir Build/Design/29R01/unity/regress_d27 -Skip "video,frames,capture"
#   手渡し (a) 色面の K*′ への焼き直し（先に py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_bake_input.py）：-Method GreatWave.Design29.EditorTools.DS29R01Bake.BakeKStarPrime -Log bake_kp
#   焼き直した色面で F_final を描く：-Method GreatWave.Design29.EditorTools.DS29Render.Render -Log f_final_kp -Package Build/Design/28R01F/F_final/art_on -WarpFile Build/Design/28R01F/F_final/timewarp_F_final.json -OutDir Build/Design/29R01/unity/f_final_kp -Stills "m6=-6,m3=-3,m2=-2,m1=-1,m05=-0.5,tstar=0" -Views "painting,seat,seat_toward_wave,side_left" -Skip timing -Extra "-ds29Name f_final_kp -ds29MeshFromPackage 0 -ds29KStarGwb Build/Design/29R01/bake_kp/kstar/kstar_a45.gwb -ds29Sdf Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin -ds29Warp Build/Design/29R01/bake_kp/bake/af28r01_uvwarp_a45.json"
#     続けて py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_tstar_eval.py --run Unity/Build/Design/29R01/unity/f_final_kp、ds29r01_tstar_sym.py、ds29r01_lfgate.py
#   設計28 の後方互換（DS29Render に引数を足した後の確かめ）：-Log regress_d28_kp -Package Build/Design/28/art_on -OutDir Build/Design/29R01/unity/regress_d28_kp -Views "painting,seat_toward_wave,side_left" -Skip timing -Extra "-ds29Name src_d28 -ds29MeshFromPackage 0"
# Unity/Build/unity.lock を排他的に作ってから起動し、終了後（失敗時も）すぐに消す。30分を超えたら止める。ログは Unity/Build/Design/29R01/logs/unity_ds29r01_<Log>.log。
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
$logFile = Join-Path $project ("Build\Design\29R01\logs\unity_ds29r01_" + $Log + ".log")
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
            New-Item -ItemType File -Path $lock -Value ("DS29R01 " + $Log + " " + (Get-Date).ToUniversalTime().ToString('o')) -ErrorAction Stop | Out-Null
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
"DS29R01_UNITY method=$Method exit=$code seconds=$([int]$sw.Elapsed.TotalSeconds) log=$logFile"
if ($code -ne 0) { exit $code }
