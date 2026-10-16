# FLIP3D：Unity batchmode を 1 回走らせる（同じプロジェクトで Unity は 1 プロセスだけ。2026-10-16、進行役）。
# Unity/Build/unity.lock を排他的に作ってから起動し、終わったら（失敗しても）すぐ消す。30 分を超えたら止める。
# ProjectSettings/*.asset と Packages/manifest.json の SHA-256 を前後で比べて書く（変わっていたら知らせる。戻しはしない）。
# 使い方：powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/flip3d/f3d_unity.ps1 -Method <名前> -Log <名前> [-Extra "<引数>"]
param(
    [Parameter(Mandatory = $true)][string]$Method,
    [Parameter(Mandatory = $true)][string]$Log,
    [string]$Extra = '',
    [string]$Unity = 'E:\6000.4.3f1\Editor\Unity.exe',
    [int]$TimeoutMinutes = 30,
    [int]$LockWaitMinutes = 20
)
$ErrorActionPreference = 'Stop'
$repo = 'G:\Unity\GreatWave_2026_Fresh'
$project = Join-Path $repo 'Unity'
$lock = Join-Path $project 'Build\unity.lock'
$logDir = Join-Path $project 'Build\FLIP3D\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("unity_" + $Log + ".log")

function Get-SettingsHashes {
    $h = [ordered]@{}
    Get-ChildItem (Join-Path $project 'ProjectSettings') -File | Sort-Object Name | ForEach-Object { $h[$_.Name] = (Get-FileHash $_.FullName -Algorithm SHA256).Hash }
    $h['Packages/manifest.json'] = (Get-FileHash (Join-Path $project 'Packages\manifest.json') -Algorithm SHA256).Hash
    return $h
}
function Test-UnityRunning {
    $p = Get-CimInstance Win32_Process -Filter "Name='Unity.exe'" | Where-Object { $_.CommandLine -and (($_.CommandLine -match [regex]::Escape('GreatWave_2026_Fresh\Unity')) -or ($_.CommandLine -match [regex]::Escape('GreatWave_2026_Fresh/Unity'))) }
    return [bool]$p
}

$deadline = (Get-Date).AddMinutes($LockWaitMinutes)
$acquired = $false
while (-not $acquired) {
    if (Test-Path $lock) {
        $age = (Get-Date) - (Get-Item $lock).LastWriteTime
        if ($age.TotalMinutes -gt 60) { throw ("unity.lock が 60 分より古い（" + [int]$age.TotalMinutes + " 分）。消さずに報告する: " + (Get-Content $lock -Raw)) }
    }
    elseif (-not (Test-UnityRunning)) {
        try {
            New-Item -ItemType File -Path $lock -Value ("FLIP3D " + $Log + " " + (Get-Date).ToUniversalTime().ToString('o')) -ErrorAction Stop | Out-Null
            $acquired = $true
            break
        } catch { }
    }
    if ((Get-Date) -gt $deadline) { throw 'unity.lock を取得できない（待ち時間の上限）。' }
    Start-Sleep -Seconds 30
}
$before = Get-SettingsHashes
$sw = [Diagnostics.Stopwatch]::StartNew()
$code = -1
try {
    $uargs = @('-batchmode', '-projectPath', ('"' + $project + '"'), '-executeMethod', $Method, '-logFile', ('"' + $logFile + '"'))
    if ($Extra) { $uargs += $Extra.Split(' ') }
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
$after = Get-SettingsHashes
$changed = @($before.Keys | Where-Object { $before[$_] -ne $after[$_] })
$new = @($after.Keys | Where-Object { -not $before.Contains($_) })
"FLIP3D_UNITY method=$Method exit=$code seconds=$([int]$sw.Elapsed.TotalSeconds) log=$logFile settings_changed=$($changed -join ',') settings_new=$($new -join ',')"
if ($code -ne 0) { exit $code }
