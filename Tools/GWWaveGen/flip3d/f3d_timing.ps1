# FLIP3D：Release のプレイヤーを見えるウィンドウで起動し、実時間の再生の 1 フレームの時間を記録する（FLIP3DTiming、2026-10-16、進行役）。
# 測っている間、0.5 s おきに nvidia-smi の GPU の使用率と、hython が動いているかを書く（他の計算と重なっていないかを後で確かめるため）。
# 使い方：powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/flip3d/f3d_timing.ps1 -Tag t1 [-Modes seat,move] [-Loops 3]
# 2026-10-16 追記：既定のクリップは場面の値（24 個/s の clip_DA3r_k5_r24）。名前の終わりに 8 を付けた視点（seat8・move8）は、
#   前の 8 個/s のクリップ（-Data8、既定 clip_DA3_k5）を -f3ddata で渡して同じプレイヤーで測る（出力は seat8.json など）。
# 2026-10-16 追記（続けて再生・続けて読む、進行役のサブエージェント）：
#   cseat・cprint・cmove：続けて再生（-f3dplay continuous）。範囲の初めから終わりまで全部を測る（助走の間は最初の記録で止めておく）。
#   s_seat・s_print・s_move：12 s の繰り返しを、全部を GPU に置かずに続けて読む道で（-f3dstream）。
#   -Data <クリップのフォルダー>：8 の付かない視点のクリップ（例 長いクリップ clip_DA3r_f1153_3313）。空なら場面の値。
#   -Extra は全部の視点に足す引数（例 "-f3dfrom 50 -f3dto 136 -f3dmoves k5 -f3dring 24 -f3dsha -f3dbench 0"）。
#   長い範囲は -TimeoutSeconds を範囲の秒 + 60 以上にする。
param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [string]$Modes = 'seat,move',
    [int]$Loops = 3,
    [double]$Warm = 3,
    [int]$Width = 1920,
    [int]$Height = 1080,
    [int]$TimeoutSeconds = 240,
    [string]$Data8 = 'G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP3D/clip_DA3_k5',
    [string]$Data = '',
    [string]$Extra = ''
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
    $pm = $m
    $more = @()
    if ($m.EndsWith('8')) { $pm = $m.Substring(0, $m.Length - 1); $more += @('-f3ddata', $Data8) }
    elseif ($Data) { $more += @('-f3ddata', $Data) }
    if ($pm -match '^c(seat|print|move)$') { $pm = $Matches[1]; $more += @('-f3dplay', 'continuous') }
    elseif ($pm -match '^s_(seat|print|move)$') { $pm = $Matches[1]; $more += @('-f3dplay', 'loop', '-f3dstream') }
    $pargs = @('-f3dmode', $pm, '-f3dtiming', ('"' + $json + '"'), '-f3dloops', "$Loops", '-f3dwarm', $Warm.ToString($inv), '-f3dquit',
               '-screen-fullscreen', '0', '-screen-width', "$Width", '-screen-height', "$Height", '-logFile', ('"' + $log + '"'))
    $pargs += $more
    if ($Extra) { $pargs += $Extra.Split(' ') }
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
        try {
            # 2026-10-16 追記：プレイヤーの主メモリー（working set・private）と、プロセスごとの GPU のメモリー（nvidia-smi の compute-apps は描画のプロセスを出さないことがあるので、全体の差で見る）
            $pp = Get-Process -Id $p.Id -ErrorAction Stop
            $s.wsMB = [math]::Round($pp.WorkingSet64 / 1e6, 1); $s.privMB = [math]::Round($pp.PrivateMemorySize64 / 1e6, 1)
        } catch { }
        $samples += [pscustomobject]$s
        Start-Sleep -Milliseconds 500
    }
    $p.WaitForExit()
    $gm = @($samples | ForEach-Object { $_.gpuMemMiB } | Where-Object { $_ -ne $null })
    $rec = [ordered]@{ mode = $m; exitCode = $p.ExitCode; killed = $killed; seconds = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1); json = $json
        hythonSamples = @($samples | Where-Object { $_.hython -gt 0 }).Count; nSamples = $samples.Count
        gpuUtilMax = (@($samples | ForEach-Object { $_.gpuUtilPct }) | Measure-Object -Maximum).Maximum
        gpuMemMiBFirst = $(if ($gm.Count) { $gm[0] } else { $null }); gpuMemMiBMax = $(if ($gm.Count) { ($gm | Measure-Object -Maximum).Maximum } else { $null })
        wsMBMax = (@($samples | ForEach-Object { $_.wsMB }) | Measure-Object -Maximum).Maximum
        privMBMax = (@($samples | ForEach-Object { $_.privMB }) | Measure-Object -Maximum).Maximum
        samples = $samples }
    $summary += [pscustomobject]$rec
    "{0} exit={1} {2}s hython={3}/{4} gpuMax={5}% gpuMemMiB {6}->{7} wsMax={8}MB" -f $m, $p.ExitCode, $rec.seconds, $rec.hythonSamples, $rec.nSamples, $rec.gpuUtilMax, $rec.gpuMemMiBFirst, $rec.gpuMemMiBMax, $rec.wsMBMax
    Start-Sleep -Seconds 2
}
$summary | ConvertTo-Json -Depth 6 | Out-File -Encoding utf8 (Join-Path $out 'run_summary.json')
