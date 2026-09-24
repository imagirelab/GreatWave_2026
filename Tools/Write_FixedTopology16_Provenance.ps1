param([Parameter(Mandatory=$true)][string]$CaptureDirectory,[Parameter(Mandatory=$true)][string]$CaptureGitHead,[bool]$CaptureGitDirty=$false)
$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot
$evidence = Join-Path $repository 'Docs\Evidence\M1\FixedTopology16'
$project = Join-Path $repository 'Unity'
$build = Join-Path $project 'Builds\FixedTopology16'
$capture = (Resolve-Path -LiteralPath $CaptureDirectory).Path
if (-not $capture.StartsWith($build + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'この16ビルド内の記録を指定してください。' }
$sources = Get-Content -LiteralPath (Join-Path $evidence '16_build_sources.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$currentPaths = @(foreach($folder in @('Assets','Packages','ProjectSettings')) { Get-ChildItem -LiteralPath (Join-Path $project $folder) -File -Recurse -Force | ForEach-Object { $_.FullName.Substring($project.Length+1).Replace('\','/') } })
if (@(Compare-Object @($sources.files.path | Sort-Object) @($currentPaths | Sort-Object)).Count) { throw '制作ソースの一覧がビルド時と異なります。追加・削除を含めて再ビルドしてください。' }
$sourceChanges = @($sources.files | Where-Object { (Get-FileHash -LiteralPath (Join-Path $project $_.path) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $_.sha256 })
if ($sourceChanges.Count) { throw '制作ソースがビルド時と一致しません。' }
$context = Get-Content -LiteralPath (Join-Path $evidence '16_build_context.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ((Get-FileHash -LiteralPath (Join-Path $evidence '16_build_sources.json') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $context.source_manifest_sha256) { throw 'ビルド文脈のソース記録が一致しません。' }
$payloadChanges = @($context.build_payload_files | Where-Object { (Get-FileHash -LiteralPath (Join-Path $build $_.path) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $_.sha256 })
if ($payloadChanges.Count) { throw '実行一式がビルド時と一致しません。' }
$report = Get-Content -LiteralPath (Join-Path $capture 'capture_report.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $report.passed) { throw '失敗した記録には出典を作れません。' }
$files = @('16_Unity_Start.png','16_Unity_Middle.png','16_Unity_End.png','16_Unity_Cache.mp4','16_unity_runtime_validation.json','16_unity_editor_validation.json','16_archive_sampling.json','16_capture_report.json','16_build.json','16_build_context.json','16_prebuild_sources.json','16_build_sources.json') | ForEach-Object {
    $item = Get-Item -LiteralPath (Join-Path $evidence $_)
    [ordered]@{path=$_;bytes=$item.Length;sha256=(Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
}
$data = [ordered]@{
    recorded_utc=(Get-Date).ToUniversalTime().ToString('o'); scene='Unity/Assets/GreatWave/Scenes/Tests/M1_FixedTopology16.unity'
    build_context='16_build_context.json'; source_snapshot='16_prebuild_sources.json / 16_build_sources.json'
    git_context_at_capture=[ordered]@{head=$CaptureGitHead;dirty=$CaptureGitDirty}
    capture_directory=$capture.Substring($repository.Length+1).Replace('\','/');player_exit_code=0
    render_method_ja=$report.method;captured_frames=$report.frames;video_frames=60;video_rate=30;video_seconds=2;endpoint_frame=60
    video_rate_is_performance_measurement=$false;fluid_simulation='未検証';hmd_validation='機器なし・未実施';manual_keyboard_mouse='利用者確認待ち'
    source_mismatch_count=$sourceChanges.Count;payload_mismatch_count=$payloadChanges.Count
    selected_frames=[ordered]@{start=0;middle=30;end=60};evidence_files=@($files)
}
$data | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $evidence '16_provenance.json') -Encoding utf8
Write-Output '16の出典・ハッシュを更新しました。'
