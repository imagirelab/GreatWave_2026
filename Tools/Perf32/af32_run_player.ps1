# 番号32：Release プレイヤー（AF32Perf.exe）を見えるウィンドウで起動し、終わるまで GPU の外部カウンターを 1 秒ごとに記録する。
# 使い方（リポジトリ根で）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File Tools/Perf32/af32_run_player.ps1 -Tag run1
#   powershell -NoProfile -ExecutionPolicy Bypass -File Tools/Perf32/af32_run_player.ps1 -Tag mock1 -Mode mock
#   powershell -NoProfile -ExecutionPolicy Bypass -File Tools/Perf32/af32_run_player.ps1 -Tag hidden1 -Hidden -Conds desk1080_seat_right -Measure 5
# -Hidden を付けたときだけ -WindowStyle Hidden で起動する（番号20 の条件の再現。診断用で、正式な値には使わない）。
# Mock のときは、このスクリプトのプロセスの中だけで環境変数 XR_RUNTIME_JSON を導入済みパッケージの unity-mock-runtime.json に向ける
# （システムの OpenXR の設定・レジストリは変えない）。
# 外部カウンター：Windows の「GPU Engine（3D）の Running Time・Utilization Percentage」「GPU Process Memory の Dedicated/Shared Usage・Total Committed」
# （プロセス単位）と nvidia-smi の memory.used・utilization.gpu（GPU 全体）。どちらも OS・ドライバーに元からあるもので、何も導入しない。
param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [ValidateSet('perf', 'mock')][string]$Mode = 'perf',
    [switch]$Hidden,
    [string]$Conds = '',
    [double]$Warm = 3,
    [double]$Measure = 15,
    [int]$TimeoutSeconds = 300
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$root = Join-Path $repo 'Unity\Build\ArtFirst\32'
$exe = Join-Path $root 'player\AF32Perf.exe'
$data = Join-Path $root 'data'
$out = Join-Path $root ('runs\' + $Tag)
if (-not (Test-Path $exe)) { throw "プレイヤーがありません: $exe" }
if (Test-Path $out) { throw "出力先が既にあります（上書きしない）: $out" }
New-Item -ItemType Directory -Force -Path $out | Out-Null
$smi = 'C:\Windows\System32\nvidia-smi.exe'

function Read-Smi {
    if (-not (Test-Path $smi)) { return $null }
    $line = & $smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits 2>$null
    if (-not $line) { return $null }
    $v = ($line | Select-Object -First 1).Split(',') | ForEach-Object { $_.Trim() }
    return [ordered]@{ memUsedMiB = [double]$v[0]; memTotalMiB = [double]$v[1]; utilPct = [double]$v[2] }
}

$idle = @()
for ($i = 0; $i -lt 3; $i++) { $idle += [ordered]@{ utc = (Get-Date).ToUniversalTime().ToString('o'); smi = (Read-Smi) }; Start-Sleep -Milliseconds 500 }

$pargs = @('-screen-fullscreen', '0', '-screen-width', '1920', '-screen-height', '1080',
    '-logFile', ('"' + (Join-Path $out ('player_' + $Tag + '.log')) + '"'),
    '-af32mode', $Mode, '-af32tag', $Tag, '-af32out', ('"' + $out + '"'), '-af32data', ('"' + $data + '"'),
    '-af32warm', $Warm.ToString([Globalization.CultureInfo]::InvariantCulture), '-af32measure', $Measure.ToString([Globalization.CultureInfo]::InvariantCulture))
if ($Conds) { $pargs += @('-af32conds', $Conds) }

$mockJson = ''
$prevEnv = $env:XR_RUNTIME_JSON
if ($Mode -eq 'mock') {
    $pkg = Get-ChildItem (Join-Path $repo 'Unity\Library\PackageCache') -Directory -Filter 'com.unity.xr.openxr@*' | Select-Object -First 1
    $mockJson = Join-Path $pkg.FullName 'Runtime\MockRuntime\unity-mock-runtime.json'
    if (-not (Test-Path $mockJson)) { throw "Mock Runtime のマニフェストがありません: $mockJson" }
    $env:XR_RUNTIME_JSON = $mockJson
}

$sw = [Diagnostics.Stopwatch]::StartNew()
$startUtc = (Get-Date).ToUniversalTime().ToString('o')
try {
    if ($Hidden) { $p = Start-Process -FilePath $exe -ArgumentList $pargs -PassThru -WindowStyle Hidden }
    else { $p = Start-Process -FilePath $exe -ArgumentList $pargs -PassThru }
}
finally {
    if ($Mode -eq 'mock') { $env:XR_RUNTIME_JSON = $prevEnv }
}
$null = $p.Handle
$procId = $p.Id
$samples = @()
$window = @()
$killed = $false
while (-not $p.HasExited) {
    if ($sw.Elapsed.TotalSeconds -gt $TimeoutSeconds) { $p.Kill(); $killed = $true; break }
    $utc = (Get-Date).ToUniversalTime().ToString('o')
    $vals = [ordered]@{}
    try {
        $paths = @("\GPU Engine(pid_$procId*engtype_3D)\Running Time", "\GPU Engine(pid_$procId*engtype_3D)\Utilization Percentage",
            "\GPU Process Memory(pid_$procId*)\Dedicated Usage", "\GPU Process Memory(pid_$procId*)\Shared Usage", "\GPU Process Memory(pid_$procId*)\Total Committed")
        $c = Get-Counter -Counter $paths -ErrorAction Stop
        foreach ($s in $c.CounterSamples) { $vals[$s.Path] = $s.CookedValue }
    } catch { $vals['error'] = $_.Exception.Message }
    try { $gp = Get-Process -Id $procId -ErrorAction Stop; $window += [ordered]@{ utc = $utc; hwnd = [int64]$gp.MainWindowHandle; title = $gp.MainWindowTitle; responding = $gp.Responding } } catch { }
    $samples += [ordered]@{ utc = $utc; t = [math]::Round($sw.Elapsed.TotalSeconds, 3); counters = $vals; smi = (Read-Smi) }
}
$p.WaitForExit()
$rec = [ordered]@{
    schema = 'GreatWave.AF32.player_run/1'; tag = $Tag; mode = $Mode; hiddenWindow = [bool]$Hidden; exe = $exe; exeSha256 = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLower()
    args = ($pargs -join ' '); xrRuntimeJson = $mockJson; startUtc = $startUtc; endUtc = (Get-Date).ToUniversalTime().ToString('o'); seconds = [math]::Round($sw.Elapsed.TotalSeconds, 3)
    pid = $procId; exitCode = $p.ExitCode; killedByTimeout = $killed; idle = $idle; window = $window; samples = $samples
}
($rec | ConvertTo-Json -Depth 6) | Set-Content -Encoding utf8 (Join-Path $out ('af32_' + $Tag + '_external.json'))
"AF32_PLAYER tag=$Tag mode=$Mode hidden=$([bool]$Hidden) exit=$($p.ExitCode) killed=$killed seconds=$([int]$sw.Elapsed.TotalSeconds) samples=$($samples.Count) out=$out"
