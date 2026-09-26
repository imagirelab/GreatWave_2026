# 番号32：Unity batchmode を1回実行する（同じプロジェクトで Unity は1プロセスだけ）。CP1 の run_cp1_unity.ps1 と同じ排他の手順。
# 使い方（リポジトリ根で）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File Tools/Perf32/af32_run_unity.ps1 -Method GreatWave.ArtFirst.EditorTools.AF32PerfBuild.BuildAll -Log build
# Unity/Build/unity.lock を排他的に作ってから起動し、終了後（失敗時も）すぐに消す。30分を超えたら止める。
# 設定の保全：起動前に ProjectSettings/*.asset・Assets/XR の設定・Packages/manifest.json のバイトを控え、
# Unity の終了後に変わったファイルを控えのバイトへ戻す（enableFrameTimingStats はビルドの間だけ true にするため）。
# 戻したファイルは Build/ArtFirst/32/af32_settings_restore_<Log>.json に記録する。
param(
    [Parameter(Mandatory = $true)][string]$Method,
    [Parameter(Mandatory = $true)][string]$Log,
    [string]$Unity = 'E:\6000.4.3f1\Editor\Unity.exe',
    [int]$TimeoutMinutes = 30,
    [int]$LockWaitMinutes = 30
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project = Join-Path $repo 'Unity'
$lock = Join-Path $project 'Build\unity.lock'
$outRoot = Join-Path $project 'Build\ArtFirst\32'
$logFile = Join-Path $outRoot ("unity_af32_" + $Log + ".log")
New-Item -ItemType Directory -Force -Path $outRoot | Out-Null

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
            New-Item -ItemType File -Path $lock -Value ("32 " + (Get-Date).ToUniversalTime().ToString('o')) -ErrorAction Stop | Out-Null
            $acquired = $true
            break
        } catch { }
    }
    if ((Get-Date) -gt $deadline) { throw 'unity.lock を取得できない（待ち時間の上限）。' }
    Start-Sleep -Seconds 60
}
$sw = [Diagnostics.Stopwatch]::StartNew()
$code = -1
$snapshot = @{}
$restored = @()
$added = @()
try {
    foreach ($f in Get-SettingsFiles) { $snapshot[$f.FullName] = [IO.File]::ReadAllBytes($f.FullName) }
    $uargs = @('-batchmode', '-projectPath', ('"' + $project + '"'), '-executeMethod', $Method, '-logFile', ('"' + $logFile + '"'), '-quit')
    $p = Start-Process -FilePath $Unity -ArgumentList $uargs -PassThru -NoNewWindow
    $null = $p.Handle
    if (-not $p.WaitForExit($TimeoutMinutes * 60 * 1000)) {
        $p.Kill()
        throw ("Unity が " + $TimeoutMinutes + " 分を超えたので止めた。")
    }
    $code = $p.ExitCode
}
finally {
    # Unity が終わってから（ロックを持ったまま）設定のバイトを確かめて戻す
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
    ($rec | ConvertTo-Json -Depth 5) | Set-Content -Encoding utf8 (Join-Path $outRoot ("af32_settings_restore_" + $Log + ".json"))
    Remove-Item -Path $lock -Force -ErrorAction SilentlyContinue
}
"AF32_UNITY method=$Method exit=$code seconds=$([int]$sw.Elapsed.TotalSeconds) restored=$($restored.Count) added=$($added.Count) log=$logFile"
if ($code -ne 0) { exit $code }
