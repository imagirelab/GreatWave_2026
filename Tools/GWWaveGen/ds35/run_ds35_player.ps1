# 設計35 variants の部：Release プレイヤー（DS35Perf.exe）を見えるウィンドウで起動し、終わるまで GPU の外部カウンターを 1 秒ごとに記録する
# （美術優先32 の af32_run_player.ps1 を写し、実行ファイル・引数・出力先を設計35 に変え、作業ディレクトリを Unity プロジェクトにしたもの）。
# 使い方（リポジトリ根で）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds35/run_ds35_player.ps1 -Tag run1
# 作業ディレクトリ：主役波・海のデータは場面の相対パス（Build/...）で読むので、プレイヤーを Unity プロジェクトのフォルダーで起動する。
# 外部カウンター：Windows の「GPU Engine（3D）の Running Time・Utilization Percentage」「GPU Process Memory」（プロセス単位）と nvidia-smi（GPU 全体）。何も導入しない。
param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [string]$Variants = '',
    [string]$Conds = '',
    [string]$Window = '11,12',
    [double]$Warm = 3,
    [double]$Measure = 12,
    [int]$TimeoutSeconds = 600
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$project = Join-Path $repo 'Unity'
$root = Join-Path $project 'Build\Design\35\variants'
$exe = Join-Path $root 'player\DS35Perf.exe'
$out = Join-Path $root ('perf\' + $Tag)
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
    '-ds35tag', $Tag, '-ds35out', ('"' + $out + '"'), '-ds35window', $Window,
    '-ds35warm', $Warm.ToString([Globalization.CultureInfo]::InvariantCulture), '-ds35measure', $Measure.ToString([Globalization.CultureInfo]::InvariantCulture))
if ($Variants) { $pargs += @('-ds35variants', $Variants) }
if ($Conds) { $pargs += @('-ds35conds', $Conds) }

$sw = [Diagnostics.Stopwatch]::StartNew()
$startUtc = (Get-Date).ToUniversalTime().ToString('o')
$p = Start-Process -FilePath $exe -ArgumentList $pargs -PassThru -WorkingDirectory $project
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
    schema = 'GreatWave.DS35.player_run/1'; tag = $Tag; workingDirectory = $project; exe = $exe; exeSha256 = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLower()
    args = ($pargs -join ' '); startUtc = $startUtc; endUtc = (Get-Date).ToUniversalTime().ToString('o'); seconds = [math]::Round($sw.Elapsed.TotalSeconds, 3)
    pid = $procId; exitCode = $p.ExitCode; killedByTimeout = $killed; idle = $idle; window = $window; samples = $samples
}
($rec | ConvertTo-Json -Depth 6) | Set-Content -Encoding utf8 (Join-Path $out ('ds35_' + $Tag + '_external.json'))
"DS35_PLAYER tag=$Tag exit=$($p.ExitCode) killed=$killed seconds=$([int]$sw.Elapsed.TotalSeconds) samples=$($samples.Count) out=$out"
