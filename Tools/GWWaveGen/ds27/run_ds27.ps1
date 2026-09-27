# 設計27：単発砕波の生成器から DS27 keypose パッケージ（入れた版・切った版）と時間曲線の表を作る（リポジトリの根で）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds27/run_ds27.ps1 [-Versions art_on,art_off] [-NoCheck] [-Twice]
# 出力：Tools/GWWaveGen/ds27/timewarp_default.json・timewarp_alt.json、Unity/Build/Design/27/<版>/（Git 対象外）。
# 必要なもの：26修正01 の K*（Unity/Build/ArtFirst/26修正01/kstar/、SHA-256 を照合）、Docs/Evidence/Design/26/ds26_conditions.json。
# -Twice：もう 1 回 Unity/Build/Design/27/_twice へ作り、パッケージの 3 ファイルのバイトが同じことを確かめる（決定性の確認）。
param([string]$Versions = 'art_on,art_off', [switch]$NoCheck, [switch]$Twice)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
Set-Location -LiteralPath $repo
$env:PYTHONIOENCODING = 'utf-8'
$env:OPENBLAS_NUM_THREADS = '1'
$sw = [Diagnostics.Stopwatch]::StartNew()
# 1 回の計算を 30 分以内にするため、版ごとに 1 回ずつ呼ぶ（入れた版 約 9 分、切った版 約 10〜20 分）
$first_v = $true
foreach ($v in $Versions.Split(',')) {
    $args1 = @('-3.10', '-B', 'Tools/GWWaveGen/ds27/ds27_generate.py', '--versions', $v)
    if ($NoCheck) { $args1 += '--no-check' }
    if (-not $first_v) { $args1 += '--no-tables' }
    & py @args1
    if ($LASTEXITCODE -ne 0) { throw "ds27_generate.py（$v）に失敗しました。" }
    $first_v = $false
}
if ($Twice) {
    $files = @('ds27_pos_rgba16.bin', 'ds27_keypose.json', 'ds27_twhite_r32f.bin')
    $first = @{}
    foreach ($v in $Versions.Split(',')) { foreach ($f in $files) { $first["$v/$f"] = (Get-FileHash -Algorithm SHA256 (Join-Path "Unity/Build/Design/27/$v" $f)).Hash } }
    $tmp = 'Unity/Build/Design/27/_twice'
    foreach ($v in $Versions.Split(',')) {
        & py -3.10 -B Tools/GWWaveGen/ds27/ds27_generate.py --versions $v --no-check --no-sea --no-tables --out $tmp
        if ($LASTEXITCODE -ne 0) { throw "2 回目の ds27_generate.py（$v）に失敗しました。" }
    }
    foreach ($k in $first.Keys) {
        $h = (Get-FileHash -Algorithm SHA256 (Join-Path $tmp $k)).Hash
        if ($h -ne $first[$k]) { throw "決定性の確認に失敗：$k" }
        Write-Output ("同じバイト：" + $k + " " + $h.Substring(0, 12))
    }
}
Write-Output ("設計27 の生成器が終わりました（" + [int]$sw.Elapsed.TotalSeconds + " 秒）：" + (Join-Path $repo 'Unity\Build\Design\27'))
