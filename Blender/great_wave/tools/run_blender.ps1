<#
.SYNOPSIS
  Run a python script headless in Blender, keep the full log, print only prefixed lines.

.DESCRIPTION
  blender.exe --background --factory-startup --python-exit-code 1 [<blend>] --python <script> -- <script args>
  * the full (noisy) output is written to results/logs/<scriptname>_<yyyyMMdd_HHmmss>.log
  * only lines that start with -Prefix (default 'GW') are printed
  * the exit code of Blender is returned (uncaught python exception -> 1)
  Nothing is installed, no environment variable is changed (PYTHONPATH untouched).

.EXAMPLE
  & "G:/research/Wave Simulation/blender/great_wave/tools/run_blender.ps1" tests/selftest_foundation.py
.EXAMPLE
  & ".../tools/run_blender.ps1" src/ref/probe.py -Prefix REF -ScriptArgs '--frame','50','--out','x.png'
.EXAMPLE
  & ".../tools/run_blender.ps1" tests/run_shape_tests.py -Blend "G:/research/Wave Simulation/blender/great_wave/blend/final.blend"

.NOTES
  If scripts are blocked by the execution policy of the machine, start it as
    powershell -ExecutionPolicy Bypass -File ".../tools/run_blender.ps1" <script> ...
  (a per-process switch; no system setting is changed) or call blender.exe directly.
#>
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Script,
    [string]$Prefix = 'GW',
    [string[]]$ScriptArgs = @(),
    [string]$Blend = '',
    [string]$BlenderExe = '',
    [switch]$ShowAll,
    [switch]$NoFactoryStartup
)

$ErrorActionPreference = 'Continue'
$projectRoot = Split-Path -Parent $PSScriptRoot

# --- resolve the script (absolute, or relative to the project root / current dir)
if (-not [System.IO.Path]::IsPathRooted($Script)) {
    $cand = Join-Path $projectRoot $Script
    if (Test-Path -LiteralPath $cand) { $Script = $cand } else { $Script = Join-Path (Get-Location) $Script }
}
if (-not (Test-Path -LiteralPath $Script)) { Write-Output "RUN_BLENDER ERROR script not found: $Script"; exit 2 }
$Script = (Resolve-Path -LiteralPath $Script).Path

# --- blender.exe from params.json unless given (no fallback search)
if (-not $BlenderExe) {
    $paramsFile = Join-Path $projectRoot 'params.json'
    $params = Get-Content -LiteralPath $paramsFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $BlenderExe = $params.blender_exe.value
}
if (-not (Test-Path -LiteralPath $BlenderExe)) { Write-Output "RUN_BLENDER ERROR blender.exe not found: $BlenderExe"; exit 2 }

# --- log file
$logDir = Join-Path $projectRoot 'results/logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$logFile = Join-Path $logDir ("{0}_{1}.log" -f [System.IO.Path]::GetFileNameWithoutExtension($Script), $stamp)

# --- command line
$cmd = @('--background')
if (-not $NoFactoryStartup) { $cmd += '--factory-startup' }
$cmd += @('--python-exit-code', '1')
if ($Blend) { $cmd += $Blend }
$cmd += @('--python', $Script, '--')
if ($ScriptArgs) { $cmd += $ScriptArgs }

Write-Output ("RUN_BLENDER script={0}" -f $Script)
Write-Output ("RUN_BLENDER log={0}" -f $logFile)

$writer = New-Object System.IO.StreamWriter($logFile, $false, (New-Object System.Text.UTF8Encoding($false)))
try {
    $writer.WriteLine(("# {0} {1}" -f $BlenderExe, ($cmd -join ' ')))
    & $BlenderExe @cmd 2>&1 | ForEach-Object {
        $line = "$_"
        $writer.WriteLine($line)
        if ($ShowAll -or $line.StartsWith($Prefix)) { Write-Output $line }
    }
    $code = $LASTEXITCODE
    $writer.WriteLine("# exit code $code")
}
finally {
    $writer.Dispose()
}
if (($code -ne 0) -and (-not $ShowAll)) {
    # make failures debuggable without opening the log: show its tail (traceback lives there)
    Write-Output "RUN_BLENDER --- last 30 log lines (non-zero exit) ---"
    Get-Content -LiteralPath $logFile -Tail 30 -Encoding UTF8 | ForEach-Object { Write-Output ("  | " + $_) }
}
Write-Output ("RUN_BLENDER exit={0}" -f $code)
exit $code
