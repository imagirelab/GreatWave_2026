# -*- coding: utf-8 -*-
"""設計27：関門の検査器（ds27_gates.py）を、美術優先30 の再生される keypose で確かめる。

1. 美術優先30 の keypose（Unity/Build/ArtFirst/30/keypose/。15 Hz の一様な節点、ワールドの位置、波の枠の原点 0）と、
   美術優先31 の白の時刻（Unity/Build/ArtFirst/31/white/af31_twhite_r32f.bin。体験の秒。表示は「終態が白のテクセル かつ t ≥ T」）を、
   DS27 の包みの書式へ写す。τ = t − 12。白は、28修正01 の焼き込みで頂点の位置のテクセルが白の頂点だけ T − 12、ほかは +1e9。
   時間曲線は美術優先30 の再生と同じ「実時間のまま t* で止める」（τ = min(t − 12, 0)）。
2. ds27_gates.run で全関門を測る。
3. 設計26 の診断（diag_measure.py、metrics.json の diag_af30）と同じ定義の値を、検査器の補間と断面の関数で測り直し、
   記録の値と許容差で比べる。P13 が合格することも確かめる。
使い方（リポジトリの根で）:
  py -3.10 -B Tools/GWWaveGen/ds27/ds27_gates_af30.py [--out-dir DIR]
  既定の出力 Unity/Build/Design/27/gates_af30/（Git 対象外）：包み art_af30/、時間曲線、ds27_gates_af30.json・.md（関門）、
  ds27_gates_af30_validation.json・.md（記録との照合）。
入力は読むだけ（SHA-256 を照合）。
"""
import argparse
import json
import math
import os
import shutil
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ds27_gates as DG  # noqa: E402

REPO = DG.REPO
KP_DIR = os.path.join(REPO, "Unity", "Build", "ArtFirst", "30", "keypose")
WH_DIR = os.path.join(REPO, "Unity", "Build", "ArtFirst", "31", "white")
BAKE_SDF = os.path.join(REPO, "Unity", "Build", "ArtFirst", "28修正01", "bake", "af28r01_uvsdf_a45.bin")
BAKE_WARP = os.path.join(REPO, "Unity", "Build", "ArtFirst", "28修正01", "bake", "af28r01_uvwarp_a45.json")
METRICS26 = os.path.join(REPO, "Docs", "Evidence", "Design", "26", "metrics.json")
SHA = {
    "af30_pos_rgba16.bin": "3d652c8958d82190408c08f69f12ee28d1eb0845ce29b40877cdf4e6143bd066",
    "af31_twhite_r32f.bin": "8a18f2e08a23e139e5cee071ae2a8a9311b06ae095acec6c82c5120c275ea73d",
    "af28r01_uvsdf_a45.bin": "305d1777c77c772d51c1b3de038b3702ac73183d678629f3ba2b0e68630562bd",
    "af28r01_uvwarp_a45.json": "945aef222f2730ee27ede3b9996234f0e00d53b806aabcfc0f3f05c86bcccafb",
}
T_STAR = 12.0


def need(path, key):
    if not os.path.isfile(path):
        raise SystemExit("[ds27_gates_af30] 入力がありません：%s" % DG.rel(path))
    if DG.sha256_file(path) != SHA[key]:
        raise SystemExit("[ds27_gates_af30] SHA-256 が記録と違います：%s" % key)
    return path


def build_package(out_pkg, out_dir):
    """美術優先30・31 を DS27 の包みへ写す。"""
    os.makedirs(out_pkg, exist_ok=True)
    kp = json.load(open(os.path.join(KP_DIR, "af30_keypose.json"), encoding="utf-8"))
    src = need(os.path.join(KP_DIR, "af30_pos_rgba16.bin"), "af30_pos_rgba16.bin")
    dst = os.path.join(out_pkg, "ds27_pos_rgba16.bin")
    if not (os.path.isfile(dst) and DG.sha256_file(dst) == SHA["af30_pos_rgba16.bin"]):
        shutil.copyfile(src, dst)          # 書式が同じ（層 × 行 × 列 × 4、RGBA16 UNORM、外接箱で正規化、A = 65535）
    nv, nu, L = int(kp["nv"]), int(kp["nu"]), int(kp["layers"])
    knots = np.array(kp["key_times_s"], float) - T_STAR
    knots[-1] = 0.0
    # 白：終態が白（28修正01 の焼き込みの色区 0）の頂点だけ T − 12、ほかは +1e9
    T = np.fromfile(need(os.path.join(WH_DIR, "af31_twhite_r32f.bin"), "af31_twhite_r32f.bin"), "<f4").reshape(nv, nu).astype(np.float64)
    S = 4096
    cls = np.fromfile(need(BAKE_SDF, "af28r01_uvsdf_a45.bin"), np.uint8).reshape(S, S, 4).argmax(2)
    w = json.load(open(need(BAKE_WARP, "af28r01_uvwarp_a45.json"), encoding="utf-8"))
    uW, vW = np.asarray(w["uWarp"], float), np.asarray(w["vWarp"], float)
    xi = np.clip(np.floor(uW * S).astype(int), 0, S - 1)
    yi = np.clip(np.floor(vW * S).astype(int), 0, S - 1)
    final_white = cls[yi[:, None], xi[None, :]] == 0
    Tw = np.where(final_white, T - T_STAR, 1.0e9).astype("<f4")
    tw_path = os.path.join(out_pkg, "ds27_twhite_r32f.bin")
    Tw.tofile(tw_path)
    ftau = np.linspace(knots[0], 0.0, int(round(-knots[0] * 240)) + 1)
    J = dict(
        schema="GreatWave.DS27.keypose/1",
        version="af30_adapter",
        note_ja="美術優先30 の keypose と美術優先31 の白を DS27 の書式へ写したもの（ds27_gates_af30.py。検査器の確かめ用）。原点は 0（ワールド = 局所）",
        layers=L, rows=nv, cols=nu, bbox_min=kp["bbox_min"], bbox_size=kp["bbox_size"],
        knot_tau=[float(x) for x in knots],
        frame=dict(tau=[float(x) for x in ftau], origin=[[0.0, 0.0, 0.0]] * len(ftau)),
        pos_sha256=SHA["af30_pos_rgba16.bin"],
        twhite_file="ds27_twhite_r32f.bin", twhite_sha256=DG.sha256_file(tw_path),
        sources=dict(keypose=DG.rel(src), twhite=DG.rel(os.path.join(WH_DIR, "af31_twhite_r32f.bin")), bake=DG.rel(BAKE_SDF)),
        final_white_vertices=int(final_white.sum()),
    )
    json.dump(J, open(os.path.join(out_pkg, "ds27_keypose.json"), "w", encoding="utf-8"), ensure_ascii=False)
    # 時間曲線：実時間のまま t* で止める（美術優先30 の再生と同じ）
    t = np.arange(0, 14 * 240 + 1) / 240.0
    tau = np.minimum(t - T_STAR, 0.0)
    twp = os.path.join(out_dir, "timewarp_af30_realtime.json")
    json.dump(dict(note_ja="美術優先30 の再生：τ = min(t − 12, 0)", t=[float(x) for x in t], tau=[float(x) for x in tau]), open(twp, "w", encoding="utf-8"))
    return twp, int(final_white.sum())


def diag_style(ks, pk, M):
    """設計26 の diag_measure.py と同じ定義で主断面の値を測り直す（頂 = 行の全列の最高点、唇先 = 列 200、根元 = 列 90、60 Hz と 240 Hz の差分）。"""
    mr = ks.main_row
    nu = ks.nu
    t60 = np.arange(int(round(17.0 * 60)) + 1) / 60.0
    tau60 = np.minimum(t60 - T_STAR, 0.0)
    vidx = mr * nu + np.arange(nu)
    X = pk.sub(tau60, vidx, 0)                          # (nt, nu, 3)
    D = X - ks.O
    A = D @ ks.t
    Y = X[..., 1]
    rm = DG.row_metrics(A, Y, np.full(len(t60), nu - 1), ks.j_E)
    ca, cy, phi = rm["ca"], rm["H"], rm["phi"]
    at = lambda arr, tt: float(arr[int(np.argmin(np.abs(t60 - tt)))])
    res = {}
    res["P1_crest_mean_speed_3_to_12s_mps"] = (at(ca, 12) - at(ca, 3)) / 9.0
    res["P1_crest_speed_9_to_12s_mps"] = (at(ca, 12) - at(ca, 9)) / 3.0
    m12 = t60 <= 12
    res["P1_P12_crest_back_travel_m"] = float(ca[m12].max()) - at(ca, 12)
    res["P2_min_surface_y_m"] = float(M["ymin"].min())
    dc = np.gradient(ks.c)
    vol = (M["S"]["Anet"] * dc[None, :]).sum(1)
    res["P3_volume_above_swl_max_m3"] = float(vol.max())
    res["P3_volume_max_t_s"] = float(M["taus"][int(vol.argmax())] + T_STAR)
    res["P3_volume_at_tstar_m3"] = float(vol[-1])
    res["P3_volume_loss_frac"] = 1 - float(vol[-1]) / float(vol.max())
    jP, jT = 200, 90
    ty, ta = Y[:, jP], A[:, jP]
    ia = int(np.argmax(np.where(m12, ty, -np.inf)))
    res["P4_tip_apex_t_s"] = float(t60[ia])
    res["P4_tip_apex_y_m"] = float(ty[ia])
    t240 = np.arange(int(round(12.5 * 240)) + 1) / 240.0
    tau240 = np.minimum(t240 - T_STAR, 0.0)
    cols = [jT, 110, 130, 150, 170, 185, jP]
    P = pk.sub(tau240, mr * nu + np.array(cols), 0)
    Ps = np.stack([(P - ks.O) @ ks.t, P[..., 1]], -1)      # (nt, ncol, 2)
    V = np.gradient(Ps, 1.0 / 240, axis=0)
    i1 = int(np.argmin(np.abs(t240 - t60[ia])))
    i2 = int(np.argmin(np.abs(t240 - 12.0)))
    res["P4_tip_mean_vertical_accel_apex_to_tstar_mps2"] = float((V[i2, -1, 1] - V[i1, -1, 1]) / (t240[i2] - t240[i1]))
    sp = np.hypot(np.gradient(ta, t60), np.gradient(ty, t60))
    res["P5_tip_speed_max_mps"] = float(np.nanmax(sp))
    res["P5_tip_speed_max_t_s"] = float(t60[int(np.nanargmax(sp))])
    i11 = int(np.argmin(np.abs(t240 - 11.0)))
    cs = np.linalg.norm(V[i11], axis=-1)
    res["P6_mid_over_root"] = float(cs[cols.index(130)] / cs[cols.index(90)])
    res["P6_root_over_tip"] = float(cs[cols.index(90)] / cs[cols.index(200)])
    iv = int(np.nonzero(np.nan_to_num(phi, nan=0) >= 90)[0][0])
    res["P7_face_vertical_t_s"] = float(t60[iv])
    res["P7_vertical_to_tstar_s"] = T_STAR - float(t60[iv])
    # 検査器の本体の頂（列 ≤ jt）と、全列の最高点の差（主断面、τ ≤ 0）
    res["check_crest_restricted_vs_all_max_dy_m"] = float(np.abs(M["S"]["H"][:, mr] - np.array([cy[int(np.argmin(np.abs(t60 - (x + T_STAR))))] for x in M["taus"]])).max())
    return res


def compare(rep, ds, m26, ks):
    """記録（metrics.json の diag_af30 と Design_26_ja.md §4.1 の美術優先30 の列）と比べる。"""
    D = m26["diag_af30"]
    g = rep["gates"]
    rows = []

    def add(item, recorded, got, tol, src, note=""):
        ok = (got is not None and recorded is not None and abs(got - recorded) <= tol)
        rows.append(dict(item=item, recorded=recorded, harness=(None if got is None else round(float(got), 4)), tol=tol, ok=bool(ok), source=src, note_ja=note))

    add("P1 頂の平均の速さ 3〜12 s [m/s]（診断の定義）", D["P1_crest_mean_speed_3_to_12s_mps"], ds["P1_crest_mean_speed_3_to_12s_mps"], 0.01, "diag_af30")
    add("P1 頂の速さ 9〜12 s [m/s]（＝関門の τ −3〜0 s、診断の定義）", D["P1_crest_speed_9_to_12s_mps"], ds["P1_crest_speed_9_to_12s_mps"], 0.01, "diag_af30")
    add("P1 関門の値：主断面の τ −3〜0 s の速さ [m/s]（本体の頂）", D["P1_crest_speed_9_to_12s_mps"], g["P1"]["detail"]["主断面"]["mean_speed_mps"], 0.02, "diag_af30",
        "検査器は頂を列 ≤ jt（K* の頂の列）で探す")
    add("P1・P12 後ろへの戻り [m]（診断の定義：最大 − t*）", D["P1_P12_crest_back_travel_m"], ds["P1_P12_crest_back_travel_m"], 0.01, "diag_af30")
    add("P12 関門の値：主断面の戻り [m]（それまでの最大 − 今の最大）", D["P1_P12_crest_back_travel_m"], g["P12"]["detail"]["主断面"], 0.02, "diag_af30",
        "検査器は途中の戻りの最大（drawdown）で、t* までの最大 − t* 以上")
    add("P2 最も低い水面 [m]", D["P2_min_surface_y_m"], ds["P2_min_surface_y_m"], 0.001, "diag_af30")
    add("P2 |A_net| / A_pos の最大（記録「比 1.0」）", 1.0, g["P2"]["value"], 0.01, "Design_26 §4.1")
    add("P3 水の量の最大 [m³]", D["P3_volume_above_swl_max_m3"], ds["P3_volume_above_swl_max_m3"], 5.0, "diag_af30")
    add("P3 水の量が最大の時刻 [s]", D["P3_volume_max_t_s"], ds["P3_volume_max_t_s"], 0.05, "diag_af30")
    add("P3 t* の水の量 [m³]", D["P3_volume_at_tstar_m3"], ds["P3_volume_at_tstar_m3"], 5.0, "diag_af30")
    add("P3 失われた割合（記録 −23%）", D["P3_volume_loss_frac"], ds["P3_volume_loss_frac"], 0.005, "diag_af30")
    add("P4 唇先の頂点の時刻 [s]（列 200）", D["P4_tip_apex_t_s"], ds["P4_tip_apex_t_s"], 1.0 / 30, "diag_af30")
    add("P4 唇先の頂点の高さ [m]（列 200）", D["P4_tip_apex_y_m"], ds["P4_tip_apex_y_m"], 0.01, "diag_af30")
    add("P4 頂点 → t* の縦の加速度の平均 [m/s²]（列 200、診断の差分）", D["P4_tip_mean_vertical_accel_apex_to_tstar_mps2"],
        ds["P4_tip_mean_vertical_accel_apex_to_tstar_mps2"], 0.02, "diag_af30")
    add("P4 関門の値：頂点 → t* の平均 [m/s²]（K* の唇先の列、Hermite の微分）", D["P4_tip_mean_vertical_accel_apex_to_tstar_mps2"], g["P4"]["value"], 0.1, "diag_af30",
        "列（K* の唇先 199 と rig の 200）と、t* の速さ（片側の傾き と 停止をはさむ中心差分）が違う")
    add("P4 落下の時間 [s]（記録 2.4 s）", 2.4, g["P4"]["detail"]["主断面"]["fall_time_s"], 0.1, "Design_26 §4.1")
    add("P5 唇先の速さの最大 [m/s]", D["P5_tip_speed_max_mps"], ds["P5_tip_speed_max_mps"], 0.05, "diag_af30")
    add("P5 その時刻 [s]", D["P5_tip_speed_max_t_s"], ds["P5_tip_speed_max_t_s"], 1.0 / 30, "diag_af30")
    add("P6 途中 / 根元（11.0 s）", D["P6_mid_over_root"], ds["P6_mid_over_root"], 0.01, "diag_af30")
    add("P6 根元 / 唇先（11.0 s）", D["P6_root_over_tip"], ds["P6_root_over_tip"], 0.01, "diag_af30")
    add("P7 主断面の前面が鉛直の時刻 [s]（診断の定義）", D["P7_face_vertical_t_s"], ds["P7_face_vertical_t_s"], 1.0 / 60 + 1e-6, "diag_af30")
    add("P7 関門の値：鉛直 → t* [s]（本体の頂）", D["P7_vertical_to_tstar_s"], g["P7"]["value"], 1.0 / 60 + 1e-6, "diag_af30")
    rng = g["P7"]["detail"]["巻きの行の始まりの範囲_tau"]
    add("P7 巻きの行の鉛直の時刻の最小 [s]", D["P7_curled_rows_vertical_t_range_s"][0], None if rng is None else rng[0] + T_STAR, 1.0 / 60 + 1e-6, "diag_af30",
        "記録は診断の巻きの行（t* の張り出し ≥ 0.2H）、検査器は K* の巻きの行（133 行）")
    add("P7 巻きの行の鉛直の時刻の最大 [s]", D["P7_curled_rows_vertical_t_range_s"][1], None if rng is None else rng[1] + T_STAR, 1.0 / 60 + 1e-6, "diag_af30")
    add("P8 11.8 s の速さ p95 / 最大", D["P8_body_speed_p95_at_11p8s_over_max"], g["P8"]["value"], 0.01, "diag_af30",
        "記録は 60 Hz の差分の断面（a, y）の速さ、検査器は Hermite の微分の 3 次元の速さ")
    fw = g["P9"]["detail"]["first_white"]
    add("P9 最初の白 [s]", D["P9_first_white_uv_s_step31"], None if fw.get("tau") is None else fw["tau"] + T_STAR, 1.0 / 30, "diag_af30（番号31 の UV）",
        "記録はテクセルの最小、検査器は頂点の最小（頂点の位置のテクセルが終態で白の頂点）")
    add("P9 主断面の鉛直の時刻の白の割合", D["P9_white_fraction_at_face_vertical"], g["P9"]["detail"]["white_fraction_at_main_onset"], 0.05, "diag_af30（番号31 の UV）",
        "記録は UV のテクセルの割合、検査器は K* の頂点の面積の重み")
    add("P10 0.5H の時刻の標準偏差 [s]（H > 3 m の行）", D["P10_t50_std_across_rows_s"], g["P10"]["detail"]["big_rows_t50_std_s"], 0.001, "diag_af30")
    add("P10 0.5H の時刻 [s]", D["P10_t50_s"], None if g["P10"]["detail"]["t50_range_tau"][0] is None else g["P10"]["detail"]["t50_range_tau"][0] + T_STAR,
        1.0 / 60 + 1e-6, "diag_af30", "検査器は巻きの行の最小")
    add("P10 噴流の始まりと頂の高さの相関（記録 +0.80）", 0.80, g["P10"]["value"], 0.05, "Design_26 §4.1")
    add("P11 主役の峰の外の水面の RMS [m]（記録 η = 0）", 0.0, g["P11"]["value"], 0.001, "Design_26 §4.1")
    add("P9 同じ割合を 28修正01 の UV（頂点の UV の面積）の重みで", D["P9_white_fraction_at_face_vertical"], ds.get("P9_white_fraction_uv_weight"), 0.05, "diag_af30（番号31 の UV）",
        "重みの違いだけを確かめる参考（検査器の関門は K* の面積の重み）")
    add("本体の頂（列 ≤ jt）と全列の最高点の差の最大 [m]（主断面）", 0.0, ds["check_crest_restricted_vs_all_max_dy_m"], 0.01, "検査器の自己検査",
        "美術優先30 では唇が頂より上へ出ないので、頂の定義の違いは値を変えない")
    return rows


def uv_white_fraction(ks, pk, tau):
    """P9 の白の割合を 28修正01 の UV（UV3 の頂点ごとの面積）の重みで（記録の UV のテクセルの割合と重みを揃えた参考）。"""
    w = json.load(open(BAKE_WARP, encoding="utf-8"))
    du = np.gradient(np.asarray(w["uWarp"], float))
    dv = np.gradient(np.asarray(w["vWarp"], float))
    wt = dv[:, None] * du[None, :]
    T = pk.twhite
    fw = T < DG.NEVER
    return float((wt * (fw & (T <= tau))).sum() / (wt * fw).sum())


def region_series(ks, pk):
    """唇・管の範囲の網の形を 2 Hz で追い、(5) が落ちる時刻の範囲を記録する（説明用）。"""
    out = []
    Kex = ks.Lrow_K < DG.TH["P13_row_edge_m"]
    for tau in np.arange(pk.knots[0], 1e-9, 0.5):
        X = pk.world(tau)
        ar = 0.5 * np.linalg.norm(DG.tri_normals(X), axis=-1)
        amin = float(np.where(ks.tri_mask[..., None], ar, np.inf).min())
        Lr = np.linalg.norm(np.diff(X, axis=1), axis=-1)
        emin = float(np.where(ks.row_edge_mask & ~Kex, Lr, np.inf).min())
        out.append((round(float(tau), 2), amin, emin))
    bad_a = [t for t, a, e in out if a < DG.TH["P13_tri_area_m2"]]
    bad_e = [t for t, a, e in out if e < DG.TH["P13_row_edge_m"]]
    return dict(samples=[dict(tau=t, tri_area_min_m2=a, row_edge_min_m=e) for t, a, e in out],
                area_fail_tau_range=[min(bad_a), max(bad_a)] if bad_a else None,
                edge_fail_tau_range=[min(bad_e), max(bad_e)] if bad_e else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=os.path.join(REPO, "Unity", "Build", "Design", "27", "gates_af30"))
    a = ap.parse_args()
    t0 = time.time()
    out_dir = os.path.abspath(a.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    pkg = os.path.join(out_dir, "art_af30")
    twp, nfw = build_package(pkg, out_dir)
    print("[af30] 包み %s（終態の白の頂点 %d）" % (pkg, nfw), flush=True)
    rep, M, ks, pk = DG.run(pkg, twp, os.path.join(out_dir, "ds27_gates_af30.json"))
    # Hermite の重みが美術優先30 の再生（af30_formation.cr_weights、Unity の AF30KeyposeWave と同じ）と同じか
    sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen"))
    sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth"))
    import af30_formation as F30  # noqa: E402  （読むだけ）
    kt = np.array(json.load(open(os.path.join(KP_DIR, "af30_keypose.json"), encoding="utf-8"))["key_times_s"], float)
    rng = np.random.default_rng(27)
    tt = np.concatenate([rng.uniform(0, 12, 2000), kt[:50], [0.0, 12.0, 11.99, 0.01]])
    werr = 0.0
    for x in tt:
        idx, w = F30.cr_weights(kt, x)
        full = np.zeros(len(kt))
        for q in range(4):
            full[idx[q]] += w[q]
        i2, w2 = DG.hermite_weights(pk.knots, [x - T_STAR])
        f2 = np.zeros(len(kt))
        for q in range(4):
            f2[i2[0, q]] += w2[0, q]
        werr = max(werr, float(np.abs(full - f2).max()))
    ds = diag_style(ks, pk, M)
    ds["P9_white_fraction_uv_weight"] = uv_white_fraction(ks, pk, -ds["P7_vertical_to_tstar_s"])
    m26 = json.load(open(METRICS26, encoding="utf-8"))
    rows = compare(rep, ds, m26, ks)
    rs = region_series(ks, pk)
    p13 = rep["gates"]["P13"]["detail"]
    val = dict(
        schema="GreatWave.DS27.gates_validation/1",
        number="設計27",
        what_ja="関門の検査器を美術優先30（と31 の白）で確かめた結果。記録は Docs/Evidence/Design/26/metrics.json の diag_af30 と Design_26_ja.md §4.1 の美術優先30 の列",
        hermite_weight_max_diff_vs_af30_cr_weights=werr,
        gates_verdicts={k: v["pass"] for k, v in rep["gates"].items()},
        expected_ja="P1〜P12 は不合格、P13 は合格（Design_26_ja.md §4.1）。P14・P15・P16 も美術優先30 は不合格の見込み（§4.1 の列）",
        P1_P12_all_fail=all(rep["gates"]["P%d" % i]["pass"] is False for i in range(1, 13)),
        P13_pass=rep["gates"]["P13"]["pass"],
        P13_step30_items_pass=p13["Step_30 の項目 (1)〜(4) がすべて合格"],
        P13_items={k: v["pass"] for k, v in p13.items() if isinstance(v, dict) and "pass" in v},
        P13_region_series_2hz=rs,
        comparisons=rows,
        comparisons_ok=sum(1 for r in rows if r["ok"]), comparisons_total=len(rows),
        diag_style_values=ds,
        runtime_s=round(time.time() - t0, 1),
    )
    vp = os.path.join(out_dir, "ds27_gates_af30_validation.json")
    json.dump(val, open(vp, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    L = ["# 関門の検査器の確かめ（美術優先30）", "",
         "- 補間の重みと美術優先30 の再生（cr_weights）の差の最大：%.2e" % werr,
         "- 関門の判定：" + "、".join("%s %s" % (k, "合格" if v is True else ("不合格" if v is False else "判定なし")) for k, v in val["gates_verdicts"].items()),
         "- P1〜P12 がすべて不合格：%s、P13 が合格：%s（Step_30 の項目 (1)〜(4)：%s）" % (
             "はい" if val["P1_P12_all_fail"] else "いいえ", "はい" if val["P13_pass"] else "いいえ", "すべて合格" if val["P13_step30_items_pass"] else "不合格あり"),
         "- P13 の項目：" + "、".join("%s %s" % (k.split(" ")[0], "合格" if v else "不合格") for k, v in val["P13_items"].items()),
         "- 唇・管の範囲の網（2 Hz）：三角形の面積 < 1e-4 m² の τ %s、辺 < 5 mm の τ %s" % (rs["area_fail_tau_range"], rs["edge_fail_tau_range"]),
         "- 記録との照合：%d 件中 %d 件が許容差の内" % (len(rows), val["comparisons_ok"]), "",
         "| 項目 | 記録 | 検査器 | 許容差 | 一致 | 出典 | 注 |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        L.append("| %s | %s | %s | %s | %s | %s | %s |" % (r["item"], r["recorded"], r["harness"], round(r["tol"], 4), "○" if r["ok"] else "×", r["source"], r["note_ja"]))
    open(os.path.splitext(vp)[0] + ".md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("[af30] 照合 %d/%d、P1〜P12 不合格 %s、P13 合格 %s、%.0f s → %s" % (val["comparisons_ok"], len(rows), val["P1_P12_all_fail"], val["P13_pass"], val["runtime_s"], vp))


if __name__ == "__main__":
    main()
