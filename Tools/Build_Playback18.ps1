param([string]$UnityEditor = 'E:\6000.4.3f1\Editor\Unity.exe')
$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot
$project = Join-Path $repository 'Unity'
$evidence = Join-Path $repository 'Docs\Evidence\M1\Playback18'
$build = Join-Path $project 'Builds\Playback18'
$log = Join-Path $project 'Logs\18-build.log'
$head = (& git -C $repository rev-parse HEAD).Trim()
$dirty = @(& git -C $repository status --porcelain).Count -gt 0
$started = (Get-Date).ToUniversalTime().ToString('o')
$arguments = '-batchmode -projectPath "' + $project + '" -executeMethod GreatWave.Editor.Playback18Builder.Build -quit -logFile "' + $log + '"'
$process = Start-Process -FilePath $UnityEditor -ArgumentList $arguments -WindowStyle Hidden -PassThru
if (-not $process.WaitForExit(600000)) { Stop-Process -Id $process.Id; throw "ビルドが10分を超えたため、この実行だけを停止しました：$log" }
$process.Refresh()
if ($process.ExitCode -ne 0) { throw "Unityのビルドに失敗しました：$log" }
$report = Get-Content -LiteralPath (Join-Path $evidence '18_build.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $report.passed) { throw 'ビルド結果が合格ではありません。' }
$payload = @(Get-ChildItem -LiteralPath $build -File -Recurse | Where-Object { $_.FullName -notmatch '\\Capture_[^\\]+\\' } | Sort-Object FullName | ForEach-Object {
    [ordered]@{ path = $_.FullName.Substring($build.Length + 1).Replace('\','/'); bytes = $_.Length; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
})
$context = [ordered]@{
    build_started_utc = $started; git_head_at_build_start = $head; working_tree_dirty_at_build_start = $dirty
    note_ja = 'このHEADだけを制作物の版としない。未コミット変更を含む正確なソースはマニフェストで識別する。'
    source_manifest_sha256 = (Get-FileHash -LiteralPath (Join-Path $evidence '18_build_sources.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    build_payload_files = $payload
}
$context | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $evidence '18_build_context.json') -Encoding utf8
Write-Output "PC実行一式：$build"

