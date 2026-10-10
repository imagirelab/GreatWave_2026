# RT48 つなぎ・確かめの段：C7（1 フレームの時間）を Release のプレイヤーで測る（Unity/Build/RT48/record_ja.md の V7・V8）。
#  ・条件ごとにプレイヤーを見えるウィンドウで起動し、RT48FrameTiming（-rt48timing）が船からのクリップ × 3 回（助走 3 s の後）を記録する。
#  ・測っている間、1 s おきに機械全体の CPU の使用率、hython が動いているか（とその CPU）、nvidia-smi の GPU の使用率を書く。
#  ・Mock：このスクリプトのプロセスの中だけで XR_RUNTIME_JSON を導入済みパッケージの unity-mock-runtime.json に向ける（システムの設定は変えない）。
# 使い方：powershell -NoProfile -ExecutionPolicy Bypass -File v_timing.ps1 -Tag t1 [-Conds proxy2000,proxy2064,proxy2800,desk1080,mock]
param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [string]$Conds = 'proxy2000,proxy2064,proxy2800,desk1080,mock',
    [int]$Runs = 3,
    [double]$Warm = 3,
    [int]$TimeoutSeconds = 400
)
$ErrorActionPreference = 'Stop'
$project = 'G:\Unity\GreatWave_2026_Fresh\Unity'
$exe = Join-Path $project 'Build\RT48\unity\player\RT48.exe'
$out = Join-Path $project ('Build\RT48\verify\timing\' + $Tag)
if (Test-Path $out) { throw "出力先が既にあります（上書きしない）: $out" }
New-Item -ItemType Directory -Force -Path $out | Out-Null
$smi = 'C:\Windows\System32\nvidia-smi.exe'
$inv = [Globalization.CultureInfo]::InvariantCulture
$defs = [ordered]@{
    proxy2000 = @{ proxy = '2000x2040'; w = 1280; h = 720 }
    proxy2064 = @{ proxy = '2064x2208'; w = 1280; h = 720 }
    proxy2800 = @{ proxy = '2800x2856'; w = 1280; h = 720 }
    desk1080  = @{ proxy = ''; w = 1920; h = 1080 }
    mock      = @{ proxy = ''; w = 1280; h = 720; mock = $true }
}
$summary = [ordered]@{ tag = $Tag; startedLocal = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'); exe = $exe; conds = @() }
foreach ($name in $Conds.Split(',')) {
    $d = $defs[$name]
    if ($null -eq $d) { throw "知らない条件: $name" }
    $json = Join-Path $out ($name + '.json')
    $log = Join-Path $out ($name + '.log')
    $pargs = @('-rt48source', 'coarse', '-rt48seat', '556', '-rt48view', 'bow', '-screen-fullscreen', '0', '-screen-width', "$($d.w)", '-screen-height', "$($d.h)", '-logFile', ('"' + $log + '"'))
    if ($d.mock) {
        $pargs += @('-rt48xr', '-rt48xrshot', ('"' + (Join-Path $out 'mock_botheyes.png') + '"'), '-rt48xrshotmode', 'both', '-rt48autoquit', '14')
    } else {
        $pargs += @('-rt48timing', ('"' + $json + '"'), '-rt48timingruns', "$Runs", '-rt48warm', $Warm.ToString($inv), '-rt48quit')
        if ($d.proxy) { $pargs += @('-rt48proxy', $d.proxy) }
    }
    $prevEnv = $env:XR_RUNTIME_JSON
    if ($d.mock) {
        $pkg = Get-ChildItem (Join-Path $project 'Library\PackageCache') -Directory -Filter 'com.unity.xr.openxr@*' | Select-Object -First 1
        $mockJson = Join-Path $pkg.FullName 'Runtime\MockRuntime\unity-mock-runtime.json'
        if (-not (Test-Path $mockJson)) { throw "Mock Runtime のマニフェストがありません: $mockJson" }
        $env:XR_RUNTIME_JSON = $mockJson
    }
    $t0 = Get-Date
    try { $p = Start-Process -FilePath $exe -ArgumentList $pargs -PassThru }
    finally { if ($d.mock) { $env:XR_RUNTIME_JSON = $prevEnv } }
    $null = $p.Handle
    $samples = @()
    $killed = $false
    while (-not $p.HasExited) {
        if (((Get-Date) - $t0).TotalSeconds -gt $TimeoutSeconds) { $p.Kill(); $killed = $true; break }
        $s = [ordered]@{ t = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1) }
        try { $s.cpuTotalPct = [math]::Round((Get-Counter '\Processor(_Total)\% Processor Time' -ErrorAction Stop).CounterSamples[0].CookedValue, 1) } catch { $s.cpuTotalPct = $null }
        $hy = @(Get-Process -Name hython -ErrorAction SilentlyContinue)
        $s.hython = $hy.Count
        try {
            $line = & $smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits 2>$null | Select-Object -First 1
            $v = $line.Split(',') | ForEach-Object { $_.Trim() }
            $s.gpuUtilPct = [double]$v[0]; $s.gpuMemMiB = [double]$v[1]
        } catch { }
        $samples += $s
        Start-Sleep -Milliseconds 200
    }
    $p.WaitForExit()
    $cpu = @($samples | Where-Object { $null -ne $_.cpuTotalPct } | ForEach-Object { $_.cpuTotalPct })
    $hyOn = @($samples | Where-Object { $_.hython -gt 0 }).Count
    $rec = [ordered]@{ name = $name; proxy = $d.proxy; window = "$($d.w)x$($d.h)"; mock = [bool]$d.mock; exitCode = $p.ExitCode; killed = $killed
        seconds = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1); json = $json; log = $log; nSamples = $samples.Count
        cpuTotalPctMean = if ($cpu.Count) { [math]::Round(($cpu | Measure-Object -Average).Average, 1) } else { $null }
        cpuTotalPctMax = if ($cpu.Count) { ($cpu | Measure-Object -Maximum).Maximum } else { $null }
        hythonSamples = $hyOn; samples = $samples }
    $summary.conds += $rec
    Write-Output ("{0} exit={1} {2}s cpuMean={3}% hython={4}/{5}" -f $name, $p.ExitCode, $rec.seconds, $rec.cpuTotalPctMean, $hyOn, $samples.Count)
    Start-Sleep -Seconds 2
}
$summary.finishedLocal = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $out 'machine.json') -Encoding utf8
