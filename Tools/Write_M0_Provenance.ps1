param(
    [Parameter(Mandatory = $true)][string]$CaptureDirectory,
    [string]$CaptureGitHead = '',
    [bool]$CaptureGitDirty = $false
)
$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot
$evidence = Join-Path $repository 'Docs\Evidence\M0'
$buildRoot = (Resolve-Path -LiteralPath (Join-Path $repository 'Unity\Builds\M0')).Path
$capture = (Resolve-Path -LiteralPath $CaptureDirectory).Path
if (-not $capture.StartsWith($repository + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'キャプチャ先には、このリポジトリ内の成功した記録フォルダーを指定してください。'
}
$provenancePath = Join-Path $evidence '10_provenance.json'
$previous = if (Test-Path -LiteralPath $provenancePath) { Get-Content -LiteralPath $provenancePath -Raw | ConvertFrom-Json } else { $null }
$sourceManifest = Get-Content -LiteralPath (Join-Path $evidence '10_build_sources.json') -Raw | ConvertFrom-Json
$mismatches = @($sourceManifest.files | Where-Object {
    (Get-FileHash -LiteralPath (Join-Path (Join-Path $repository 'Unity') $_.path) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $_.sha256
})
if ($mismatches.Count) { throw '現在の制作ファイルとビルド時のソースが異なります。再ビルド後に記録してください。' }
$captureReport = Get-Content -LiteralPath (Join-Path $capture 'capture_report.json') -Raw | ConvertFrom-Json
if (-not $captureReport.passed) { throw '失敗したキャプチャの出典記録は作成できません。' }
$buildFiles = @(Get-ChildItem -LiteralPath $buildRoot -File -Recurse | Where-Object {
    $_.FullName -notmatch '\\Capture_[^\\]+\\'
} | Sort-Object FullName | ForEach-Object {
    [ordered]@{ path = $_.FullName.Substring($buildRoot.Length + 1).Replace('\', '/'); bytes = $_.Length
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
})
$mediaFiles = @('M0_Seated.png', 'M0_Boat_Exterior.png', 'M0_Calibration.png', 'M0_Desktop_Walkthrough.mp4',
    '10_build.json', '10_build_sources.json', '10_prebuild_sources.json', '10_capture_report.json') | ForEach-Object {
    $file = Get-Item -LiteralPath (Join-Path $evidence $_)
    [ordered]@{ path = $_; bytes = $file.Length
        sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
}
# 元のビルド時点は、ソースと実行一式が同一の場合にだけ引き継ぐ。
$sameBuild = $null -ne $previous -and $previous.build_payload_files.Count -eq $buildFiles.Count
if ($sameBuild) {
    foreach ($file in $buildFiles) {
        $old = @($previous.build_payload_files | Where-Object path -eq $file.path)
        if ($old.Count -ne 1 -or $old[0].sha256 -ne $file.sha256) { $sameBuild = $false; break }
    }
}
if ($sameBuild) {
    $oldSource = @($previous.evidence_files | Where-Object path -eq '10_build_sources.json')
    $newSource = @($mediaFiles | Where-Object { $_.path -eq '10_build_sources.json' })
    $sameBuild = $oldSource.Count -eq 1 -and $oldSource[0].sha256 -eq $newSource[0].sha256
}
$recordHead = (& git -C $repository rev-parse HEAD).Trim()
$recordDirty = @(& git -C $repository status --porcelain).Count -gt 0
$data = [ordered]@{
    recorded_utc = (Get-Date).ToUniversalTime().ToString('o')
    source_parent_commit = if ($sameBuild) { $previous.source_parent_commit } else { $null }
    source_worktree_included_uncommitted_step10 = if ($sameBuild) { $previous.source_worktree_included_uncommitted_step10 } else { $null }
    build_context_note_ja = '元のビルド時Git情報は同一ソース・同一実行一式の場合のみ保持する。現在のHEADをビルド時点と推測しない。'
    git_context_at_capture = if ($CaptureGitHead) { [ordered]@{ head = $CaptureGitHead; dirty = $CaptureGitDirty } } elseif ($sameBuild -and $previous.capture_directory -eq $capture.Substring($repository.Length + 1).Replace('\', '/')) { $previous.git_context_at_capture } else { $null }
    git_context_at_evidence_recording = [ordered]@{ head = $recordHead; dirty = $recordDirty }
    source_snapshot = '10_prebuild_sources.json / 10_build_sources.json'
    postbuild_source_mismatch_count = $mismatches.Count
    scene = 'Unity/Assets/GreatWave/Scenes/Tests/M0_DesktopPreflight.unity'
    render_method_ja = '同じPC実行ビルドのUnity Camera.Renderと注記用Camera。表示窓の画面録画ではない。'
    capture_directory = $capture.Substring($repository.Length + 1).Replace('\', '/')
    player_exit_code = 0
    video_duration_seconds = $captureReport.capturedFrames / $captureReport.frameRate
    video_frames = $captureReport.capturedFrames
    video_playback_rate = $captureReport.frameRate
    video_rate_is_performance_measurement = $false
    selected_frames = [ordered]@{ M0_Seated = 0; M0_Boat_Exterior = 192; M0_Calibration = 312 }
    manual_keyboard_mouse_trial = '未実施・利用者確認待ち'
    hmd_validation = '機器なし・未実施'
    evidence_files = @($mediaFiles)
    build_payload_files = $buildFiles
}
$data | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $provenancePath -Encoding utf8
Write-Output "出典・ハッシュを更新しました：$provenancePath"
