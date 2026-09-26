# 設計26「砕波の発生条件を選ぶ」の実験・診断・図・証拠を作り直す（リポジトリの根で）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds26/run_ds26.ps1 [-SimNpz <path>] [-PaperPdf <path>]
# 1) 実験（py -3.12、numpy）：E1 唇の逆算（旧規則）、E2 本体を物理から作った場合の差、E3 keypose の間隔と容量、
#    E4 前縁の帯での解き直しと全行の加速度、E4b 網の検査、E4c 既定の統計、E5 美術の誘導を切った版、E6 原画視点の周りの海、
#    時間曲線の関門（tw_gate.py）、前稿の時間の表（timewarp_table.py、記録のみ）
# 2) 図（py -3.10、OpenCV・PIL）：原因の図、E1 の主断面、論文 Fig. 4・5 の並べ図（PDF の写真だけ）
# 3) 美術優先30 の診断（py -3.10）：再生される keypose の測定と図 f1〜f5
# 4) ds26_evidence.py：metrics.json・run.json を Docs/Evidence/Design/26 へ
# 必要なもの（Git 対象外だが本機にある）：26修正01 の K*（Unity/Build/ArtFirst/26修正01/kstar/）、美術優先30 の keypose
#   （Unity/Build/ArtFirst/30/keypose/）、美術優先31 の白の時刻（Unity/Build/ArtFirst/31/white/）。
# -SimNpz：利用者の Houdini 解算から作った断面の npz（profiles_main_lateral.npz、リポジトリ外・本機のみ）。
#   無ければ E2 は (a)(b) だけ（e2_result_nosim.json）、E2c は飛ばす。npz はリポジトリへ複製しない。
# -PaperPdf：McAllister ほか 2019 の PDF（CC BY 4.0）。無ければ論文の並べ図は作り直さない（コミット済みの図を残す）。
# 出力：Unity/Build/Design/26/（Git 対象外）と Docs/Evidence/Design/26/。
param([string]$SimNpz = $env:GW_DS26_SIM_NPZ, [string]$PaperPdf = $env:GW_DS26_PAPER_PDF)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
Set-Location -LiteralPath $repo
$env:PYTHONIOENCODING = 'utf-8'
$started = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss+00:00')
$sw = [Diagnostics.Stopwatch]::StartNew()

function Invoke-DS26([string]$Py, [string]$Script, [string[]]$Rest = @()) {
    $t0 = $sw.Elapsed.TotalSeconds
    # Python の警告（標準エラー）で止まらないように、終了コードだけで判定する
    $ErrorActionPreference = 'Continue'
    & py $Py -B "Tools/GWWaveGen/ds26/$Script" @Rest
    $code = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($code -ne 0) { throw "$Script に失敗しました（終了コード $code）。" }
    Write-Output ("  {0} {1}：{2:N0} 秒" -f $Script, ($Rest -join ' '), ($sw.Elapsed.TotalSeconds - $t0))
}

$useSim = [bool]$SimNpz
$usePdf = [bool]$PaperPdf

Invoke-DS26 '-3.12' 'e1_inverse_ballistic.py'
Invoke-DS26 '-3.12' 'e1_inverse_ballistic.py' @('restrict')
if ($useSim) {
    Invoke-DS26 '-3.12' 'e2_residual.py' @('--sim', $SimNpz)
    Invoke-DS26 '-3.12' 'e2c_sim_window.py' @('--sim', $SimNpz)
} else {
    Write-Output '  解算の断面の npz が渡されていないので、E2 は (a)(b) だけを計算し、E2c は飛ばします。'
    Invoke-DS26 '-3.12' 'e2_residual.py' @('--skip-sim')
}
Invoke-DS26 '-3.12' 'e3_keypose_sampling.py'
Invoke-DS26 '-3.12' 'e4_prerelease_ramp.py'
Invoke-DS26 '-3.12' 'e4b_mesh.py'
Invoke-DS26 '-3.12' 'e4c_default_stats.py'
Invoke-DS26 '-3.12' 'e5_artoff.py'
Invoke-DS26 '-3.12' 'e6_painting_sea.py'
Invoke-DS26 '-3.12' 'tw_gate.py'
Invoke-DS26 '-3.12' 'timewarp_table.py'
Invoke-DS26 '-3.10' 'fig_e1.py'
Invoke-DS26 '-3.10' 'fig_cause.py'
if ($usePdf) {
    Invoke-DS26 '-3.10' 'fig_paper_panels.py' @('--pdf', $PaperPdf)
} else {
    Write-Output '  論文の PDF が渡されていないので、fig_paper_fig4_fig5.png は作り直しません。'
}
Invoke-DS26 '-3.10' 'diag_measure.py'
Invoke-DS26 '-3.10' 'diag_figs.py'
Invoke-DS26 '-3.10' 'diag_cues.py'

$ev = @('--started-utc', $started)
if ($useSim) { $ev += '--sim-used' }
if ($usePdf) { $ev += '--pdf-used' }
Invoke-DS26 '-3.12' 'ds26_evidence.py' $ev
Write-Output ("設計26 の再生成が終わりました（" + [int]$sw.Elapsed.TotalSeconds + " 秒）：" + (Join-Path $repo 'Docs\Evidence\Design\26'))
