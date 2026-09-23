<#
.SYNOPSIS
  Blender で Python スクリプトを画面なしで実行し、全ログを保存して指定接頭辞の行だけを表示する。

.DESCRIPTION
  blender.exe --background --factory-startup --python-exit-code 1 [<blend>] --python <script> -- <script args>
  * 全出力を results/logs/<scriptname>_<yyyyMMdd_HHmmss>.log に保存する。
  * -Prefix（既定値 GW）で始まる行だけを画面に表示する。
  * Blender の終了コードを返す。未処理の Python 例外は 1 となる。
  インストールや環境変数の変更は行わない。PYTHONPATH も変更しない。

.EXAMPLE
  & "G:/Unity/GreatWave_2026/Blender/great_wave/tools/run_blender.ps1" tests/selftest_foundation.py
.EXAMPLE
  & ".../tools/run_blender.ps1" src/ref/probe.py -Prefix REF -ScriptArgs '--frame','50','--out','x.png'
.EXAMPLE
  & ".../tools/run_blender.ps1" tests/test_shape.py -Blend "G:/Unity/GreatWave_2026/Blender/great_wave/blend/great_wave.blend"

.NOTES
  実行ポリシーでスクリプトが拒否される場合は、次のようにプロセス単位で実行する。
    powershell -ExecutionPolicy Bypass -File ".../tools/run_blender.ps1" <script> ...
  システム設定は変更されない。blender.exe を直接実行してもよい。
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

# --- スクリプトのパスを解決する（絶対パス、プロジェクト相対パス、作業ディレクトリ相対パス）
if (-not [System.IO.Path]::IsPathRooted($Script)) {
    $cand = Join-Path $projectRoot $Script
    if (Test-Path -LiteralPath $cand) { $Script = $cand } else { $Script = Join-Path (Get-Location) $Script }
}
if (-not (Test-Path -LiteralPath $Script)) { Write-Output "RUN_BLENDER ERROR スクリプトが見つかりません: $Script"; exit 2 }
$Script = (Resolve-Path -LiteralPath $Script).Path

# --- 指定がなければ params.json から blender.exe を読み込む（他の場所は探さない）
if (-not $BlenderExe) {
    $paramsFile = Join-Path $projectRoot 'params.json'
    $params = Get-Content -LiteralPath $paramsFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $BlenderExe = $params.blender_exe.value
}
if (-not (Test-Path -LiteralPath $BlenderExe)) { Write-Output "RUN_BLENDER ERROR blender.exe が見つかりません: $BlenderExe"; exit 2 }

# --- ログファイル
$logDir = Join-Path $projectRoot 'results/logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$logFile = Join-Path $logDir ("{0}_{1}.log" -f [System.IO.Path]::GetFileNameWithoutExtension($Script), $stamp)

# --- 実行コマンド
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
    # 失敗時はログを開かなくても原因を追えるよう末尾を表示する（traceback を含む）。
    Write-Output "RUN_BLENDER --- 終了コードが非ゼロのため、ログ末尾 30 行 ---"
    Get-Content -LiteralPath $logFile -Tail 30 -Encoding UTF8 | ForEach-Object { Write-Output ("  | " + $_) }
}
Write-Output ("RUN_BLENDER exit={0}" -f $code)
exit $code
