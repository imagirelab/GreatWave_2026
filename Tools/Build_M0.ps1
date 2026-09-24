param([string]$UnityEditor = 'E:\6000.4.3f1\Editor\Unity.exe')
$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot
$project = Join-Path $repository 'Unity'
$log = Join-Path $project 'Logs\10-build.log'
if (-not (Test-Path -LiteralPath $UnityEditor)) { throw '指定されたUnity Editorが見つかりません。' }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $log) | Out-Null
$arguments = '-batchmode -nographics -projectPath "' + $project + '" -executeMethod GreatWave.Editor.M0Build.Build -quit -logFile "' + $log + '"'
$process = Start-Process -FilePath $UnityEditor -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "ビルド失敗。ログを確認してください：$log" }
Write-Output "PCビルド完了：$(Join-Path $project 'Builds\M0\GreatWaveM0.exe')"
