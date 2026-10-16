# FLIP3D：Release のプレイヤーを見えるウィンドウで起動し、実時間の再生の 1 フレームの時間を記録する（FLIP3DTiming、2026-10-16、進行役）。
# 測っている間、0.5 s おきに nvidia-smi の GPU の使用率と、hython が動いているかを書く（他の計算と重なっていないかを後で確かめるため）。
# 使い方：powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/flip3d/f3d_timing.ps1 -Tag t1 [-Modes seat,move] [-Loops 3]
param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [string]$Modes = 'seat,move',
    [int]$Loops = 3,
    [double]$Warm = 3,
    [int]$Width = 1920,
    [int]$Height = 1080,
    [int]$TimeoutSeconds = 240
)
$ErrorActionPreference = 'Stop'
$project = 'G:\Unity\GreatWave_2026_Fresh\Unity'
$exe = Join-Path $project 'Build\FLIP3D\player\FLIP3D.exe'
$out = Join-Path $project ('Build\FLIP3D\timing\' + $Tag)
if (Test-Path $out) { throw "出力先が既にあります（上書きしない）: $out" }
New-Item -ItemType Directory -Force -Path $out | Out-Null
$smi = 'C:\Windows\System32\nvidia-smi.exe'
$inv = [Globalization.CultureInfo]::InvariantCulture
$summary = @()
foreach ($m in $Modes.Split(',')) {
    $json = Join-Path $out ($m + '.json')
    $log = Join-Path $out ($m + '.log')
    $pargs = @('-f3dmode', $m, '-f3dtiming', ('"' + $json + '"'), '-f3dloops', "$Loops", '-f3dwarm', $Warm.ToString($inv), '-f3dquit',
               '-screen-fullscreen', '0', '-screen-width', "$Width", '-screen-height', "$Height", '-logFile', ('"' + $log + '"'))
    $t0 = Get-Date
    $p = Start-Process -FilePath $exe -ArgumentList $pargs -PassThru
    $null = $p.Handle
    $samples = @()
    $killed = $false
    while (-not $p.HasExited) {
        if (((Get-Date) - $t0).TotalSeconds -gt $TimeoutSeconds) { $p.Kill(); $killed = $true; break }
        $s = [ordered]@{ t = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1); hython = @(Get-Process -Name hython -ErrorAction SilentlyContinue).Count }
        try {
            $line = & $smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits 2>$null | Select-Object -First 1
            $v = $line.Split(',') | ForEach-Object { $_.Trim() }
            $s.gpuUtilPct = [double]$v[0]; $s.gpuMemMiB = [double]$v[1]
        } catch { }
        $samples += [pscustomobject]$s
        Start-Sleep -Milliseconds 500
    }
    $p.WaitForExit()
    $rec = [ordered]@{ mode = $m; exitCode = $p.ExitCode; killed = $killed; seconds = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1); json = $json
        hythonSamples = @($samples | Where-Object { $_.hython -gt 0 }).Count; nSamples = $samples.Count
        gpuUtilMax = (@($samples | ForEach-Object { $_.gpuUtilPct }) | Measure-Object -Maximum).Maximum; samples = $samples }
    $summary += [pscustomobject]$rec
    "{0} exit={1} {2}s hython={3}/{4} gpuMax={5}%" -f $m, $p.ExitCode, $rec.seconds, $rec.hythonSamples, $rec.nSamples, $rec.gpuUtilMax
    Start-Sleep -Seconds 2
}
$summary | ConvertTo-Json -Depth 6 | Out-File -Encoding utf8 (Join-Path $out 'run_summary.json')
