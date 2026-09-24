param(
    [Parameter(Mandatory = $true)][string]$Executable,
    [Parameter(Mandatory = $true)][string]$Arguments,
    [Parameter(Mandatory = $true)][string]$AttemptName,
    [switch]$IsolatePackages
)
$ErrorActionPreference = 'Stop'
$stageRoot = Split-Path -Parent $PSScriptRoot
if ($AttemptName -notmatch '^[A-Za-z0-9_-]+$') { throw 'AttemptName は英数字、_、- のみにしてください。' }
foreach ($directory in @('Logs', 'Evidence', 'Exports')) {
    New-Item -ItemType Directory -Path (Join-Path $stageRoot $directory) -Force | Out-Null
}
# 変更はこの PowerShell と子プロセスに限定する。利用者の設定は書き換えない。
$env:HOUDINI_MAXTHREADS = '2'
$env:HOUDINI_NO_START_PAGE_SPLASH = '1'
$env:HOUDINI_PROMPT_ON_CRASHES = '0'
$env:HOUDINI_ANONYMOUS_STATISTICS = '0'
if ($IsolatePackages) {
    $env:HOUDINI_USER_PREF_DIR = Join-Path $stageRoot 'Preferences\houdini__HVER__'
    $env:HOUDINI_NO_ENV_FILE = '1'
    $env:HOUDINI_PACKAGE_SKIP = '1'
}
$stdout = Join-Path $stageRoot ('Logs\' + $AttemptName + '.stdout.log')
$stderr = Join-Path $stageRoot ('Logs\' + $AttemptName + '.stderr.log')
$started = (Get-Date).ToUniversalTime()
$watch = [System.Diagnostics.Stopwatch]::StartNew()
$process = Start-Process -FilePath $Executable -ArgumentList $Arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
$finished = $process.WaitForExit(30000)
if (-not $finished) { Stop-Process -Id $process.Id }
$watch.Stop()
$process.Refresh()
$outText = if (Test-Path -LiteralPath $stdout) { Get-Content -LiteralPath $stdout -Raw } else { '' }
$errText = if (Test-Path -LiteralPath $stderr) { Get-Content -LiteralPath $stderr -Raw } else { '' }
$report = [ordered]@{
    attempt = $AttemptName
    executable = $Executable
    product_version = (Get-Item -LiteralPath $Executable).VersionInfo.ProductVersion
    arguments = $Arguments
    process_local_isolation = [bool]$IsolatePackages
    started_utc = $started.ToString('o')
    wall_seconds = $watch.Elapsed.TotalSeconds
    timeout_seconds = 30
    timed_out = -not $finished
    exit_code = if ($finished) { $process.ExitCode } else { $null }
    script_reached = [bool]($outText -match 'M1_HOUDINI_SCRIPT_STARTED|M1_HOUDINI_GEOMETRY_PROBE|M1_HBATCH_REACHED')
    segmentation_fault = [bool]($errText -match 'Segmentation fault')
    explicit_license_failure = [bool](($outText + $errText) -match '(?i)no licenses|no valid licenses|unable to acquire.*license|license.*not available|no licenses could be found')
}
$report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $stageRoot ('Evidence\' + $AttemptName + '.json')) -Encoding utf8
$report | ConvertTo-Json -Depth 4
($outText + $errText) -split '\r?\n' | Where-Object { $_ -match '(?i)license|fatal error|M1_HBATCH_REACHED|M1_HOUDINI_SCRIPT_STARTED|M1_HOUDINI_GEOMETRY_PROBE' } | ForEach-Object {
    ($_ -replace '\b[A-Fa-f0-9]{8,}\b', '[redacted-id]') -replace '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[redacted-email]'
}
