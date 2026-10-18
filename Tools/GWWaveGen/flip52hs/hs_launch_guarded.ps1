# FLIP52B hires surfacing test launcher + guard (2026-10-18, Claude). Starts hs_surface_test.py in hython only when the free commit is
# >= StartFreeGB, at Idle priority with HOUDINI_MAXTHREADS threads, and kills it when the free commit falls under KillFreeGB, when any
# checkpoint other than the copied v.FFFF.sim appears in the test folder (= Houdini began to simulate), when the checkpoint is not loaded
# after LoadSec, or after MaxSec. Never touches any other process.
# usage: powershell -NoProfile -ExecutionPolicy Bypass -File hs_launch_guarded.ps1 -Frame 2112 [-Variants all] [-Tag b2]
param([int]$Frame = 2112, [string]$Variants = "all", [string]$Tag = "", [double]$StartFreeGB = 8.0, [double]$KillFreeGB = 3.0, [int]$MaxSec = 900,
      [int]$LoadSec = 360, [int]$Threads = 6)
$HY = "G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe"
$TOOL = "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52hs/hs_surface_test.py"
$OUT = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP52B/hires/test_f{0:D4}" -f $Frame
New-Item -ItemType Directory -Force $OUT | Out-Null
$T = ""; if ($Tag) { $T = "_" + $Tag }
$MON = "{0}/monitor_f{1:D4}{2}.txt" -f $OUT, $Frame, $T
function FreeGB {
    $c = Get-Counter -Counter @('\Memory\Commit Limit', '\Memory\Committed Bytes')
    $l = $c.CounterSamples[0].CookedValue; $b = $c.CounterSamples[1].CookedValue
    return @(($l / 1GB), ($b / 1GB), (($l - $b) / 1GB))
}
function Log($s) {
    $line = (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " " + $s
    Add-Content -Path $MON -Value $line -Encoding UTF8
    Write-Output $line
}
$f = FreeGB
Log ("pre-launch commit limit {0:N2} GB committed {1:N2} GB free {2:N2} GB (start rule >= {3} GB)" -f $f[0], $f[1], $f[2], $StartFreeGB)
if ($f[2] -lt $StartFreeGB) { Log "NOT STARTED: free commit below the start rule"; exit 10 }
Remove-Item "$OUT/LOADED$T.txt", "$OUT/DONE$T.txt" -ErrorAction SilentlyContinue
$env:HOUDINI_MAXTHREADS = "$Threads"
$p = Start-Process -FilePath $HY -ArgumentList @($TOOL, "$Frame", "$Variants", "$Tag") -RedirectStandardOutput "$OUT/hython_stdout$T.txt" `
    -RedirectStandardError "$OUT/hython_stderr$T.txt" -WindowStyle Hidden -PassThru
$null = $p.Handle
try { $p.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::Idle } catch { Log ("priority set failed " + $_) }
Log ("launched pid {0} priority {1} threads {2} variants {3}" -f $p.Id, $p.PriorityClass, $Threads, $Variants)
$t0 = Get-Date; $last = -100; $killed = $null; $minFree = 999.0
while (-not $p.HasExited) {
    Start-Sleep -Seconds 2
    $f = FreeGB
    if ($f[2] -lt $minFree) { $minFree = $f[2] }
    $el = ((Get-Date) - $t0).TotalSeconds
    $sims = @(Get-ChildItem "$OUT/_ckpt" -Filter *.sim -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne ("v.{0:D4}.sim" -f $Frame) })
    $why = $null
    if ($f[2] -lt $KillFreeGB) { $why = "free commit {0:N2} GB < {1} GB" -f $f[2], $KillFreeGB }
    elseif ($sims.Count -gt 0) { $why = "unexpected checkpoint file(s) " + (($sims | ForEach-Object { $_.Name }) -join ",") + " (Houdini began to simulate)" }
    elseif ($el -gt $MaxSec) { $why = "wall {0:N0} s > {1} s" -f $el, $MaxSec }
    elseif (($el -gt $LoadSec) -and -not (Test-Path "$OUT/LOADED$T.txt")) { $why = "checkpoint not loaded after {0:N0} s" -f $el }
    if ($why) {
        if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
        Log ("KILL: " + $why); $killed = $why; break
    }
    if ($el - $last -ge 20) {
        $last = $el
        $mine = Get-Process -Id $p.Id -ErrorAction SilentlyContinue
        $others = Get-Process hython -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $p.Id }
        $mp = 0.0; if ($mine) { $mp = $mine.PagedMemorySize64 / 1GB }
        Log ("t {0:N0} s free {1:N2} GB mine private {2:N2} GB others {3}" -f $el, $f[2], $mp,
             (($others | ForEach-Object { "{0}:{1:N2}GB" -f $_.Id, ($_.PagedMemorySize64 / 1GB) }) -join " "))
    }
}
$p.WaitForExit()
Log ("exit code {0} killed {1} min free {2:N2} GB wall {3:N0} s" -f $p.ExitCode, $killed, $minFree, ((Get-Date) - $t0).TotalSeconds)
