# 設計35 variants の部：Unity batchmode を1回実行する（美術優先32 の af32_run_unity.ps1 と設計34 の run_ds34_unity.ps1 を合わせたもの。
# 同じプロジェクトで Unity は1プロセスだけ。unity.lock の手順・30分の上限は同じ。ロックの印は DS35V）。
# 使い方（リポジトリ根で）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds35/run_ds35_unity.ps1 -Method GreatWave.Design35.EditorTools.DS35Build.BuildAll -Log build
#   powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds35/run_ds35_unity.ps1 -Method GreatWave.Design35.EditorTools.DS35Build.RenderVideos -Log video
# 設定の保全：起動前に ProjectSettings/*.asset・Assets/XR の設定・Packages/manifest.json のバイトを控え、Unity の終了後に変わったファイルを控えへ戻す
# （enableFrameTimingStats はビルドの間だけ true にするため）。戻したファイルは Build/Design/35/variants/logs/ds35_settings_restore_<Log>.json に記録する。
param(
    [Parameter(Mandatory = $true)][string]$Method,
    [Parameter(Mandatory = $true)][string]$Log,
    [string]$Extra = '',
    [string]$Unity = 'E:\6000.4.3f1\Editor\Unity.exe',
    [int]$TimeoutMinutes = 30,
    [int]$LockWaitMinutes = 20
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$project = Join-Path $repo 'Unity'
$lock = Join-Path $project 'Build\unity.lock'
$outRoot = Join-Path $project 'Build\Design\35\variants\logs'
$logFile = Join-Path $outRoot ("unity_ds35_" + $Log + ".log")
New-Item -ItemType Directory -Force -Path $outRoot | Out-Null
if ($TimeoutMinutes -gt 30) { throw '1回の計算は30分以内（AGENTS.md の時間枠と損切り）。' }

function Test-UnityRunning {
    $p = Get-CimInstance Win32_Process -Filter "Name='Unity.exe'" | Where-Object { $_.CommandLine -and (($_.CommandLine -match [regex]::Escape('GreatWave_2026_Fresh\Unity')) -or ($_.CommandLine -match [regex]::Escape('GreatWave_2026_Fresh/Unity'))) }
    return [bool]$p
}

function Get-SettingsFiles {
    $list = @()
    $list += Get-ChildItem -Path (Join-Path $project 'ProjectSettings') -File
    $list += Get-ChildItem -Path (Join-Path $project 'Assets\XR') -File -Recurse
    $list += Get-Item (Join-Path $project 'Packages\manifest.json')
    $lockJson = Join-Path $project 'Packages\packages-lock.json'
    if (Test-Path $lockJson) { $list += Get-Item $lockJson }
    return $list
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
            New-Item -ItemType File -Path $lock -Value ("DS35V " + $Log + " " + (Get-Date).ToUniversalTime().ToString('o')) -ErrorAction Stop | Out-Null
            $acquired = $true
            break
        } catch { }
    }
    if ((Get-Date) -gt $deadline) { throw 'unity.lock を取得できない（待ち時間の上限）。' }
    Start-Sleep -Seconds 30
}
$sw = [Diagnostics.Stopwatch]::StartNew()
$code = -1
$snapshot = @{}
$restored = @()
$added = @()
try {
    foreach ($f in Get-SettingsFiles) { $snapshot[$f.FullName] = [IO.File]::ReadAllBytes($f.FullName) }
    $uargs = @('-batchmode', '-projectPath', ('"' + $project + '"'), '-executeMethod', $Method, '-logFile', ('"' + $logFile + '"'), '-quit')
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
    $sha = [Security.Cryptography.SHA256]::Create()
    foreach ($f in Get-SettingsFiles) {
        if (-not $snapshot.ContainsKey($f.FullName)) { $added += $f.FullName.Substring($repo.Length + 1); continue }
        $now = [IO.File]::ReadAllBytes($f.FullName)
        $old = $snapshot[$f.FullName]
        $h1 = [BitConverter]::ToString($sha.ComputeHash($old)).Replace('-', '').ToLower()
        $h2 = [BitConverter]::ToString($sha.ComputeHash($now)).Replace('-', '').ToLower()
        if ($h1 -ne $h2) {
            [IO.File]::WriteAllBytes($f.FullName, $old)
            $restored += [ordered]@{ path = $f.FullName.Substring($repo.Length + 1); before = $h1; afterUnity = $h2; restoredTo = $h1 }
        }
    }
    foreach ($k in $snapshot.Keys) { if (-not (Test-Path $k)) { [IO.File]::WriteAllBytes($k, $snapshot[$k]); $restored += [ordered]@{ path = $k.Substring($repo.Length + 1); before = 'deleted by Unity'; restoredTo = 'snapshot' } } }
    $rec = [ordered]@{ log = $Log; method = $Method; utc = (Get-Date).ToUniversalTime().ToString('o'); restored = $restored; addedFiles = $added; noteJa = 'Unity の終了後に設定ファイルのバイトを起動前の控えと比べ、変わったものを控えへ戻した。新しくできたファイルは消さずに記録だけした。' }
    ($rec | ConvertTo-Json -Depth 5) | Set-Content -Encoding utf8 (Join-Path $outRoot ("ds35_settings_restore_" + $Log + ".json"))
    Remove-Item -Path $lock -Force -ErrorAction SilentlyContinue
}
"DS35V_UNITY method=$Method exit=$code seconds=$([int]$sw.Elapsed.TotalSeconds) restored=$($restored.Count) added=$($added.Count) log=$logFile"
if ($code -ne 0) { exit $code }
