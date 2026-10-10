# RT48：Unity をバッチで 1 回走らせる（Tools/*.ps1 と同じ E:\6000.4.3f1\Editor\Unity.exe）。
#  ・走らせる前に ProjectSettings を Unity/Build/RT48/unity/ps_backup/<時刻>/ へ写し、SHA-256 を取る。
#  ・Unity が終わった後に SHA-256 を比べ、変わったファイルは写しからバイト単位で戻す（計画 C7 の ProjectSettings の扱い）。
#  ・ログは Unity/Build/RT48/unity/logs/ に置く。
# 使い方：powershell -NoProfile -ExecutionPolicy Bypass -File u_unity.ps1 -Method GreatWave.RT48.EditorTools.RT48SelfTest.RunAll -Name selftest [-Extra '...']
param(
    [Parameter(Mandatory = $true)][string]$Method,
    [Parameter(Mandatory = $true)][string]$Name,
    [string]$Extra = '',
    [int]$TimeoutSec = 1800,
    [string]$UnityEditor = 'E:\6000.4.3f1\Editor\Unity.exe'
)
$ErrorActionPreference = 'Stop'
$project = 'G:\Unity\GreatWave_2026_Fresh\Unity'
$out = Join-Path $project 'Build\RT48\unity'
$logs = Join-Path $out 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$stamp = (Get-Date).ToString('yyyyMMdd_HHmmss')
$log = Join-Path $logs ($Name + '_' + $stamp + '.log')
$ps = Join-Path $project 'ProjectSettings'
$backup = Join-Path $out ('ps_backup\' + $stamp)
New-Item -ItemType Directory -Force -Path $backup | Out-Null
Copy-Item -Path (Join-Path $ps '*') -Destination $backup -Recurse -Force
$before = @{}
Get-ChildItem -LiteralPath $ps -File -Recurse | ForEach-Object { $before[$_.FullName.Substring($ps.Length + 1)] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
$arguments = '-batchmode -projectPath "' + $project + '" -executeMethod ' + $Method + ' -logFile "' + $log + '" ' + $Extra
$sw = [Diagnostics.Stopwatch]::StartNew()
$p = Start-Process -FilePath $UnityEditor -ArgumentList $arguments -WindowStyle Hidden -PassThru
if (-not $p.WaitForExit($TimeoutSec * 1000)) { Stop-Process -Id $p.Id; Write-Output "TIMEOUT $TimeoutSec s" }
$p.Refresh()
$code = $p.ExitCode
$after = @{}
Get-ChildItem -LiteralPath $ps -File -Recurse | ForEach-Object { $after[$_.FullName.Substring($ps.Length + 1)] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
$changed = @()
foreach ($k in $before.Keys) { if ($after[$k] -ne $before[$k]) { $changed += $k } }
$added = @($after.Keys | Where-Object { -not $before.ContainsKey($_) })
foreach ($k in $changed) { Copy-Item -LiteralPath (Join-Path $backup $k) -Destination (Join-Path $ps $k) -Force }
$restoredOk = $true
foreach ($k in $changed) { if ((Get-FileHash -LiteralPath (Join-Path $ps $k) -Algorithm SHA256).Hash -ne $before[$k]) { $restoredOk = $false } }
$summary = [ordered]@{ name = $Name; method = $Method; exitCode = $code; seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1); log = $log; psBackup = $backup;
    projectSettingsChanged = $changed; projectSettingsAdded = $added; projectSettingsRestoredOk = $restoredOk }
$summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $logs ($Name + '_' + $stamp + '.json')) -Encoding utf8
$summary | ConvertTo-Json -Depth 4
if (Test-Path $log) {
    Select-String -LiteralPath $log -Pattern 'error CS|RT48_|Exception|Scripts have compiler errors|Shader error' | Select-Object -First 80 | ForEach-Object { $_.Line }
}
