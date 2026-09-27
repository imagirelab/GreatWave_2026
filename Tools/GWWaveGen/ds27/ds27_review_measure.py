# -*- coding: utf-8 -*-
"""設計27 のレビュー対応：関門 P1〜P16 が見ない所を測って記録する（記録のみ。判定はしない）。

関門の検査器 ds27_gates.py（パッケージの読み方・Hermite・行の断面の量）と、生成器 ds27_model.py（唇の重み κ・列・放出の時刻、
解析の位置）を読むだけで使う。パッケージ・K*・生成器は変えない。
入力（リポジトリの根から。Unity/Build/ は Git 対象外）：
  Unity/Build/Design/27/<版>/          パッケージ（ds27_keypose.json・ds27_pos_rgba16.bin・ds27_twhite_r32f.bin）、ds27_sea.npz、ds27_checks.json
  Unity/Build/Design/27/<版>_default/  Unity の描画の連番（frames/seat・seat_form）と ds27_frames_tau.json
  Tools/GWWaveGen/ds27/timewarp_default.json、Tools/GWContext/seat_v1.json
出力：Unity/Build/Design/27/review/ds27_review_measure.json（要点は ds27_evidence.py が metrics.json の review_measurements へ写す）
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds27/ds27_review_measure.py
numpy と Pillow だけを使う。1 回 約 3〜5 分。
"""
import hashlib
import json
import math
import os
import sys
import time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ds27_gates as DG  # noqa: E402
import ds27_model as MD  # noqa: E402

REPO = DG.REPO
B27 = os.path.join(REPO, "Unity", "Build", "Design", "27")
OUT = os.path.join(B27, "review", "ds27_review_measure.json")
SEAT = os.path.join(REPO, "Tools", "GWContext", "seat_v1.json")
G = 9.81
f = DG.fnum


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for ch in iter(lambda: fh.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def jload(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def sec(ks, X):
    A, Y, _ = ks.section(X)
    return A, Y


def a03_front(A, Y, cj, jE, H):
    """前の部分（頂の列〜j_E）で 0.3H を最後に下へ横切る点の a（検査器の Lo の定義 A の起点＝内壁の 0.3H の点）。"""
    y3 = 0.3 * H
    cols = np.arange(len(A) - 1)
    m = (cols >= cj) & (cols < jE) & (Y[:-1] > y3) & (Y[1:] <= y3)
    k = np.nonzero(m)[0]
    if not len(k):
        return np.nan
    k = int(k[-1])
    t = (Y[k] - y3) / max(Y[k] - Y[k + 1], 1e-12)
    return float(A[k] + t * (A[k + 1] - A[k]))


def fit_acc(tq, v):
    """2 次式の当てはめの 2 次の係数 × 2（加速度）。"""
    return float(2.0 * np.polyfit(tq, v, 2)[0])


# ---------------------------------------------------------------- 1. 水の量と、t* の前の K* への引き戻し（入れた版）
def water(ks, pk, g):
    dc = np.gradient(ks.c)
    taus = np.round(np.arange(-4.0, 1e-9, 0.1), 4)
    vol = []
    main_area = []
    peak_area = []
    for tau in taus:
        A, Y = sec(ks, pk.world(float(tau)))
        an, _ = DG.row_areas(A, Y)
        vol.append(float((an * dc).sum()))
        main_area.append(float(an[ks.main_row]))
        peak_area.append(float(an[ks.peak_row]))
    vol = np.array(vol)
    kx = int(vol.argmax())
    kn = kx + int(vol[kx:].argmin())
    mech = {}
    for r, name in ((ks.main_row, "main_row_159"), (ks.peak_row, "peak_row_192")):
        pts = []
        for tau in (-3.0, -2.4, -2.0, -1.6, -1.2, -1.0, -0.8, -0.4, 0.0):
            X = pk.world(float(tau))
            A, Y = sec(ks, X)
            rm = DG.row_metrics(A[r:r + 1], Y[r:r + 1], ks.crest_hi[r:r + 1], ks.j_E)
            cj, H, ca = int(rm["cj"][0]), float(rm["H"][0]), float(rm["ca"][0])
            aw = a03_front(A[r], Y[r], cj, ks.j_E, H)
            T_row = float(g.T_row[r])
            pts.append(dict(tau=tau, crest_a_m=f(ca, 2), crest_H_m=f(H, 2), inner_wall_0p3H_ahead_of_crest_m=f(aw - ca, 2),
                            anchor_to_kstar_E=f(float(MD.ease_in((tau - g.anc["e0"]) / (0.0 - g.anc["e0"]))), 3),
                            tube_shape_psi_t=f(float(MD.ease_in((tau + T_row) / T_row)), 3),
                            sheet_Anet_m2=f(float(DG.row_areas(A[r:r + 1], Y[r:r + 1])[0][0]), 1)))
        mech[name] = pts
    kstar_ahead = {}
    for r, name in ((ks.main_row, "main_row_159"), (ks.peak_row, "peak_row_192")):
        cj = int(np.argmax(np.where(np.arange(ks.nu) <= ks.crest_hi[r], ks.Y[r], -np.inf)))
        kstar_ahead[name] = f(a03_front(ks.A[r], ks.Y[r], cj, ks.j_E, ks.Y[r, cj]) - ks.A[r, cj], 2)
    return dict(
        ja="シートの上の符号付きの断面積（行ごと、y = 0 で閉じる）× 行の間隔の和。窓（225 m）ではない。巻きの間（τ −3.2〜−1.0 s）に本体の水が減り、"
           "最後の 1 s で K* へ戻る。仕組み：内壁の錨を t* の K* の位置へ寄せる ease-in（anchor.to_kstar_sigma、τ −2.0 s から）と、"
           "管の天井を K* の形へ寄せる ψ_t（ds_tube_shape）。関門 P3 はこの区間（τ > −2.0 s）を ds_sea_calm_painting のために判定から除くので見ない",
        taus=[float(t) for t in taus], sheet_volume_m3=[f(v, 1) for v in vol],
        main_row_sheet_Anet_m2=[f(v, 1) for v in main_area], peak_row_sheet_Anet_m2=[f(v, 1) for v in peak_area],
        volume_max=dict(tau=f(taus[kx], 2), m3=f(vol[kx], 1)), volume_min_after_max=dict(tau=f(taus[kn], 2), m3=f(vol[kn], 1)),
        volume_tstar_m3=f(vol[-1], 1), drop_frac=f(1 - vol[kn] / vol[kx], 4), rise_last_frac=f(vol[-1] / vol[kn] - 1, 4),
        main_row_area=dict(at_vol_max=f(main_area[kx], 1), min_after=f(min(main_area[kx:]), 1), min_tau=f(taus[kx + int(np.argmin(main_area[kx:]))], 2), tstar=f(main_area[-1], 1)),
        mechanism=mech, kstar_inner_wall_0p3H_ahead_of_crest_m=kstar_ahead,
        af30_reference_ja="美術優先30 の rig は設計26 の測定で P3 −23%（設計26 の記録 §4.1 の P3 の行）")


# ---------------------------------------------------------------- 2. Hermite の再生の差
def hermite(pk, g, ver, n_int=32):
    kn = pk.knots
    idx = np.unique(np.round(np.linspace(0, len(kn) - 2, n_int)).astype(int))
    taus = []
    for i in idx:
        for fr in (0.5, 0.25):
            taus.append(float(kn[i] + fr * (kn[i + 1] - kn[i])))
    errs = []
    for tau in taus:
        e = np.linalg.norm(pk.world(tau) - g.world(tau), axis=-1)
        errs.append((tau, float(e.max()), float(np.percentile(e, 99))))
    w = max(errs, key=lambda x: x[1])
    chk = jload(os.path.join(B27, ver, "ds27_checks.json"))["hermite_playback_err_m"]
    lg = os.path.join(B27, "ds27_generate_log_%s.json" % ver)
    last = [x.strip() for x in jload(lg).get("log", []) if "節点" in x][-1:] if os.path.isfile(lg) else []
    return dict(generator_check=dict(max_m=f(chk["max"], 6), max_at_tau=chk["max_at_tau"], max_30hz_m=f(chk["max_30hz"], 6),
                                     max_midpoints_m=f(chk["max_midpoints"], 6), p99_of_frame_p99_m=chk["p99_of_frame_p99"],
                                     source=rel(os.path.join(B27, ver, "ds27_checks.json")),
                                     ja="生成器の自前の最後の検査（30 Hz の 361 コマ＋節点の間の中点、量子化を含む、全頂点の最大）"),
                independent_sample=dict(n=len(taus), max_m=f(w[1], 6), max_at_tau=f(w[0], 4), p99_max_m=f(max(e[2] for e in errs), 6),
                                        ja="この測定：節点の区間を %d 個選び、中点と 1/4 の点で、パッケージ（量子化・Hermite・枠の表の線形補間）"
                                           "と生成器 Generator.world の差（全頂点の最大）" % len(idx)),
                rule_ja="許容：生成器の節点の検査 2.5 mm ＋量子化 1.2 mm ≤ 4 mm（ds27_params.json の knots.note_ja）",
                adaptive_last_round_ja=("生成の記録の最後の適応の回（%s）の差は、その回に検査した区間だけの値で、全体の最大ではない" % (last[0] if last else "記録なし")))


# ---------------------------------------------------------------- 3. 唇の弾道（入れた版）
def lips(ks, pk, g):
    curled = set(int(r) for r in ks.curled_idx)
    rows = sorted(int(r) for r in g.lip.keys())
    out_non = []
    fits = []
    for r in rows:
        L = g.lip[r]
        cols = L["cols"]
        upm = L["upm"]
        s = L["s"]
        iu = np.nonzero(upm)[0]
        i_tip = int(iu[np.argmin(s[iu])])
        picks = [("tip", i_tip)]
        if r in curled:
            for sv in (0.25, 0.5):
                picks.append(("s%.2f" % sv, int(iu[np.argmin(np.abs(s[iu] - sv))])))
        res = []
        for name, i in picks:
            Tc = float(L["Tc"][i])
            Tr = min(g.Tr_max, Tc / 2)
            t0 = -Tc + Tr + 0.02
            if -t0 < 0.25:
                res.append(dict(point=name, col=int(cols[i]), window_s=f(-t0, 3), note_ja="窓が 0.25 s 未満で当てはめない"))
                continue
            tq = np.linspace(t0, 0.0, int(round(-t0 * 240)) + 1)
            W = pk.sub(tq, np.array([r * ks.nu + int(cols[i])]), 0)[:, 0, :]
            a = (W - ks.O) @ ks.t
            y = W[:, 1]
            e = W @ ks.e
            res.append(dict(point=name, col=int(cols[i]), window_tau=[f(t0, 3), 0.0], ay_mps2=f(fit_acc(tq, y), 3),
                            a_h_mps2=f(fit_acc(tq, a), 3), a_e_mps2=f(fit_acc(tq, e), 3)))
            if r in curled:
                fits.append((r, name, fit_acc(tq, y), fit_acc(tq, a)))
        ent = dict(row=r, c_m=f(ks.c[r], 2), H_m=f(g.H[r], 2), kappa=f(float(g.kappa[r]), 3), T_row_s=f(float(g.T_row[r]), 3), points=res)
        if r not in curled:
            out_non.append(ent)
        elif r in (ks.main_row, ks.peak_row, 60):
            ent["curled"] = True
            out_non.append(ent)
    fa = np.array([(x[2], x[3]) for x in fits])
    ok = (np.abs(fa[:, 0] + G) <= 0.5) & (np.abs(fa[:, 1]) <= 0.5)
    bad = [dict(row=x[0], point=x[1], ay=f(x[2], 2), a_h=f(x[3], 2)) for x, o in zip(fits, ok) if not o]
    beyond = [e for e in out_non if not e.get("curled") and e["c_m"] is not None and e["c_m"] > ks.c[ks.peak_row]]
    near = [e for e in out_non if not e.get("curled") and e["c_m"] is not None and e["c_m"] < 0]
    tip_ay = [p["ay_mps2"] for e in beyond for p in e["points"] if p["point"] == "tip" and "ay_mps2" in p]
    return dict(
        ja="生成器の唇の行（κ > 0）の唇先を、打ち出しの補間の後（放出 + min(0.6 s, 放出から t* の半分) + 0.02 s）から t* まで 240 Hz で"
           "パッケージから読み、2 次式を当てはめた加速度（地面、m/s²。ay は縦、a_h は進行方向 t、a_e は波峰線方向 e）。巻きの行（K* で巻く 133 行）は"
           "唇先と上面の s 0.25・0.5 の 3 点。重力だけなら ay = −9.81、a_h = 0。κ < 1 の行は唇が本体の前面と混ざる（Lf = Bu + κ(Lf − Bu)）",
        curled_rows_fit=dict(points=int(len(fits)), within_0p5_of_g_and_h0=int(ok.sum()), exceptions=bad),
        rows_beyond_peak=dict(rows=[e["row"] for e in beyond], c_range_m=[min(e["c_m"] for e in beyond), max(e["c_m"] for e in beyond)] if beyond else None,
                              H_range_m=[min(e["H_m"] for e in beyond), max(e["H_m"] for e in beyond)] if beyond else None,
                              kappa_range=[min(e["kappa"] for e in beyond), max(e["kappa"] for e in beyond)] if beyond else None,
                              tip_ay_range_mps2=[min(tip_ay), max(tip_ay)] if tip_ay else None),
        rows_near_end_noncurled=[e["row"] for e in near],
        per_row=out_non,
        gate_coverage_ja="P4 は主断面（行 159）と峰の行（行 192）だけ、P16 は K* で巻く 133 行だけを見るので、峰の行の外側の κ の減衰の帯は関門に入らない")


# ---------------------------------------------------------------- 4. 切った版が K* から受け継ぐもの
def art_off(ks, pk_on, pk_off, g_on, g_off):
    X0 = pk_off.world(0.0)
    A, Y = sec(ks, X0)
    rm = DG.row_metrics(A, Y, ks.crest_hi, ks.j_E)
    Hk = ks.Hrow
    m = Hk >= 3.0
    Hoff = rm["H"]
    Xon = pk_on.world(0.0)
    flat = ks.Y < 0.05 * ks.H_star
    rms_on = float(np.sqrt(np.mean(Xon[..., 1][flat] ** 2)))
    rms_off = float(np.sqrt(np.mean(Y[flat] ** 2)))
    # 奥の壁（行 200〜230）：t* の唇の張り出し（頂から前の最大の a − 頂の a）
    Aon, Yon = sec(ks, Xon)
    far = {}
    for r in (192, 200, 205, 210, 215, 220, 230):
        jt = int(np.argmax(ks.Y[r, :200]))
        def reach(Ar, Yr):
            k = int(np.argmax(Yr[:jt + 1]))
            return float(Ar[jt:ks.j_corner].max() - Ar[k])
        far[str(r)] = dict(c_m=f(ks.c[r], 2), K=f(reach(ks.A[r], ks.Y[r]), 2), on=f(reach(Aon[r], Yon[r]), 2), off=f(reach(A[r], Y[r]), 2))
    # 管の天井の白
    tube = np.zeros((ks.nv, ks.nu), bool)
    for q in ks.curled:
        tube[q["r"], q["rim"] + 1:q["ja"]] = True
    Ton, Toff = pk_on.twhite, pk_off.twhite
    odd = (Toff > 0) & (Toff < 1e8)
    return dict(
        tstar_crest_height_vs_kstar=dict(rows=int(m.sum()), corr=f(float(np.corrcoef(Hoff[m], Hk[m])[0, 1]), 5),
                                         max_abs_diff_m=f(float(np.abs(Hoff[m] - Hk[m]).max()), 3),
                                         ja="切った版の t* の行ごとの本体の頂の高さ（検査器の頂の定義）と K* の行ごとの頂（H ≥ 3 m の行）"),
        flat_margin_rms_tstar_m=dict(on=f(rms_on, 3), off=f(rms_off, 3), ja="K* で平らな所（y < 0.05H*）の t* の水面の RMS"),
        farwall_lip_reach_tstar_m=far,
        tube_never_white=dict(on=int((tube & (Ton >= 1e8)).sum()), off=int((tube & (Toff >= 1e8)).sum()), region=int(tube.sum()),
                              ja="巻きの行の管の天井（rim の次の列〜内壁の錨の前）で T_white ≥ 1e8（t* まで白くならない）の頂点の数"),
        twhite_off_positive_values=dict(n=int(odd.sum()), max_s=f(float(Toff[odd].max()), 4) if odd.any() else None,
                                        ja="切った版の T_white で (0, 1e8) にある値（τ ≤ 0 では白にならないが、約束の +1e9 の外）"),
        inherited_from_kstar_ja=[
            "頂の高さ：どちらの版も行ごとの頂の高さを K* の頂の列の高さ y_root から作る（ds27_model.crest の y_c = y_root − vH·(−τ)）ので、t* の行ごとの頂の高さは K* のまま（約 35 m の局所の塔の形。設計26 §1.1 は美術に数える）",
            "列：頂の列（root）・唇先（tip。切った版は波峰線方向にならす）・rim・内壁の錨（ja）・内壁の線分の向き（wall）は K* から行ごとに決める（_rows）",
            "swell_replaced_by_body は海の数値の条件（ds27_params.json の sea）で、美術の誘導の切り替えではないので、切った版でも本体の下のうねりを消す",
        ],
        columns_same=dict(ja_equal=bool(np.array_equal(g_on.ja, g_off.ja)), rim_equal=bool(np.array_equal(g_on.rim, g_off.rim)),
                          root_equal=bool(np.array_equal(g_on.root, g_off.root)), tip_equal=bool(np.array_equal(g_on.tip, g_off.tip))),
        switches_off=[k for k, v in g_off.sw.items() if not v])


# ---------------------------------------------------------------- 5. 周りの海を静める範囲
def sea_calm(g_on):
    out = {}
    for ver in ("art_on", "art_off"):
        z = np.load(os.path.join(B27, ver, "ds27_sea.npz"))
        ts, eta = z["tau"], z["eta"]
        d = {}
        for tv in (-4.0, -2.0, -1.0, 0.0):
            k = int(np.argmin(np.abs(ts - tv)))
            e = eta[k].astype(np.float64)
            d["%.1f" % tv] = dict(max_abs_m=f(float(np.abs(e).max()), 3), rms_m=f(float(np.sqrt(np.mean(e ** 2))), 3))
        out[ver] = dict(rows=int(eta.shape[1]), a_range_m=[float(z["a"][0]), float(z["a"][-1])], by_tau=d)
    kf = {("%.1f" % tv): dict(zip(("kc_carrier", "ks_swell"), [f(v, 3) for v in g_on.calm_factors(tv)])) for tv in (-4.0, -3.0, -2.0, -1.0, -0.5, 0.0)}
    return dict(sea_npz=out, calm_factors_art_on=kf,
                ja="生成器は ds_swell_calm（うねり、τ −4 s から）と ds_sea_calm_painting（搬送波、τ −2 s から）を行・場所によらず全体に掛ける"
                   "（ds27_model.sea と sea_outside の kc・ks はスカラー）。t* で周りの海は全 240 行・地面の a −330〜130 m で 0、シートの上の搬送波も 0。"
                   "設計26 §4.2 は原画視点の周りの見える約 4.2% の足跡と余白、D35 は『主役波のまわり』")


# ---------------------------------------------------------------- 6. P2 の窓の広がり（標本の範囲の欠けを除く）
def p2_extent(ks, pk, ver, calm_from=-2.0):
    z = np.load(os.path.join(B27, ver, "ds27_sea.npz"))
    sea = dict(tau=np.asarray(z["tau"], float), a=np.asarray(z["a"], float), eta=np.asarray(z["eta"], float))
    amin, amax = float(sea["a"][0]), float(sea["a"][-1])
    rows = ks.curled_idx
    taus = np.round(np.arange(-12.0, 1e-9, 0.1), 4)
    R = np.full((len(taus), len(rows)), np.nan)
    cov = np.zeros((len(taus), len(rows)), bool)
    for k, tau in enumerate(taus):
        A, Y = sec(ks, pk.world(float(tau)))
        rm = DG.row_metrics(A, Y, ks.crest_hi, ks.j_E)
        es, as_ = DG.sea_rows_interp(sea, float(tau))
        for i, r in enumerate(rows):
            ca = rm["ca"][r]
            w0, w1 = ca - 112.5, ca + 112.5
            mb = (as_ >= w0) & (as_ < A[r, 0])
            mf = (as_ > A[r, -1]) & (as_ <= w1)
            pa = np.concatenate([as_[mb], A[r], as_[mf]])[None]
            py = np.concatenate([es[r][mb], Y[r], es[r][mf]])[None]
            an, ap = DG.row_areas(pa, py)
            if ap[0] >= 1.0:
                R[k, i] = abs(an[0]) / ap[0]
            cov[k, i] = (w0 >= amin) and (w1 <= amax)
    judge = np.ones(len(taus), bool) if ver == "art_off" else (taus <= calm_from + 1e-9)
    Rc = np.where(cov & judge[:, None], R, np.nan)
    over = np.nanmax(Rc, 0) > 0.2
    im = int(np.nanargmax(Rc))
    kk, ii = np.unravel_index(im, Rc.shape)
    gap_last = {}
    for r, name in ((ks.main_row, "main_row_159"), (ks.peak_row, "peak_row_192")):
        i = list(rows).index(r)
        nc = np.nonzero(~cov[:, i])[0]
        gap_last[name] = dict(last_uncovered_tau=f(taus[nc[-1]], 2) if len(nc) else None,
                              max_ratio_in_gap=f(float(np.nanmax(np.where(~cov[:, i] & judge, R[:, i], np.nan))), 3) if len(nc) else None,
                              max_ratio_covered=f(float(np.nanmax(Rc[:, i])), 3))
    ex = [dict(row=int(rows[i]), c_m=f(ks.c[rows[i]], 2), max_ratio=f(float(np.nanmax(Rc[:, i])), 3),
               at_tau=f(float(taus[int(np.nanargmax(Rc[:, i]))]), 2)) for i in np.nonzero(over)[0]]
    return dict(ja="P2 の窓の比 |A_net|/A_pos を 10 Hz で全巻きの行について測り、窓（頂 ±112.5 m）が周りの海の標本の範囲（地面の a %.0f〜%.0f m）に"
                   "収まるコマだけで数えた（入れた版は τ ≤ −2.0 s、切った版は全区間）" % (amin, amax),
                covered_max=dict(ratio=f(float(Rc[kk, ii]), 3), row=int(rows[ii]), c_m=f(ks.c[rows[ii]], 2), tau=f(taus[kk], 2)),
                rows_over_0p2=dict(n=len(ex), of=int(len(rows)), c_range_m=[min(e["c_m"] for e in ex), max(e["c_m"] for e in ex)] if ex else None,
                                   tau_range=[min(e["at_tau"] for e in ex), max(e["at_tau"] for e in ex)] if ex else None, rows=ex),
                main_peak=gap_last)


# ---------------------------------------------------------------- 7. 段階の断面の形（主断面・峰の行）
def profiles(ks, pk, taus):
    out = {}
    for r, name in ((ks.main_row, "main_row_159"), (ks.peak_row, "peak_row_192")):
        L = []
        for tau in taus:
            A, Y = sec(ks, pk.world(float(tau)))
            rm = DG.row_metrics(A[r:r + 1], Y[r:r + 1], ks.crest_hi[r:r + 1], ks.j_E)
            cj, H, ca = int(rm["cj"][0]), float(rm["H"][0]), float(rm["ca"][0])
            a, y = A[r], Y[r]
            # 前面のほぼ鉛直（≥ 75°）の区間の高さの合計（頂の列〜j_E、0.3H より上）
            da, dy = np.diff(a), np.diff(y)
            ang = np.degrees(np.arctan2(-dy, da))
            cols = np.arange(len(da))
            ym = 0.5 * (y[1:] + y[:-1])
            mv = (cols >= cj) & (cols < ks.j_E) & (dy < 0) & (ang >= 75.0) & (ym > 0.3 * H)
            vert_h = float(-dy[mv].sum())
            # 一番前の点（0.3H より上、頂の列〜j_E）の高さ / H：前へ返った先は頂より下がる
            m = (np.arange(len(a)) >= cj) & (np.arange(len(a)) <= ks.j_E) & (y > 0.3 * H)
            jf = int(np.nonzero(m)[0][np.argmax(a[m])])
            # 頂の平らさ：頂から 1% H 以内の点の a の幅
            top = (y >= 0.99 * H) & (np.abs(a - ca) < 15)
            L.append(dict(tau=f(tau, 3), H_m=f(H, 2), theta_c_deg=f(rm["theta"][0], 1), phi_deg=f(rm["phi"][0], 1), psi_deg=f(rm["psi"][0], 1),
                          Lo_over_H=f(rm["Lo"][0] / H, 3), near_vertical_front_height_m=f(vert_h, 2),
                          foremost_point_y_over_H=f(y[jf] / H, 3), foremost_point_ahead_of_crest_m=f(a[jf] - ca, 2),
                          top_width_within_1pct_m=f(float(a[top].max() - a[top].min()) if top.any() else 0.0, 2)))
        out[name] = L
    return dict(ja="行の断面の量（検査器の row_metrics と同じ頂・φ・ψ・θc・Lo）。near_vertical_front_height_m：前面で水平から 75° 以上下がる線分の"
                   "高さの合計（0.3H より上）。foremost_point_y_over_H：0.3H より上の一番前の点の高さ / H（先が前へ返って垂れると 1 より下がる）",
                rows=out)


# ---------------------------------------------------------------- 7b. P15 の段階 a の読みの余裕
def p15_margin(ks, pk, gates):
    """段階 a の判定（H/Hf 0.5〜0.7・θc ≥ 140°・φ ≤ φmax・Lo ≤ 0.02H）を φmax 35°（検査器の読み）と 30° で比べる（白の条件は a の前には白がないので省く）。"""
    taus = np.round(np.arange(-6.0, -2.0 + 1e-9, 1.0 / 60), 5)
    Hf = {}
    X0 = pk.world(0.0)
    A0, Y0 = sec(ks, X0)
    rm0 = DG.row_metrics(A0, Y0, ks.crest_hi, ks.j_E)
    rows = (ks.main_row, ks.peak_row)
    ser = {r: [] for r in rows}
    for tau in taus:
        A, Y = sec(ks, pk.world(float(tau)))
        for r in rows:
            rm = DG.row_metrics(A[r:r + 1], Y[r:r + 1], ks.crest_hi[r:r + 1], ks.j_E)
            ser[r].append((float(rm["H"][0]) / float(rm0["H"][r]), float(rm["theta"][0]), float(rm["phi"][0]), float(rm["Lo"][0]) / max(float(rm["H"][0]), 1e-9)))
    out = {}
    det = gates["P15"]["detail"]
    for r, name in ((ks.main_row, "主断面"), (ks.peak_row, "峰で最も高い巻きの行")):
        S = np.array(ser[r])
        res = {}
        for pm in (35.0, 30.0):
            ok = (S[:, 0] >= 0.5) & (S[:, 0] <= 0.7) & (S[:, 1] >= 140.0) & (np.nan_to_num(S[:, 2], nan=99) <= pm) & (np.nan_to_num(S[:, 3], nan=9) <= 0.02)
            k = np.nonzero(ok)[0]
            res["phi_max_%d" % pm] = dict(first_tau=f(taus[k[0]], 3) if len(k) else None, frames=int(ok.sum()))
        ka = int(np.argmin(np.abs(taus - det[name]["tau"]["a"])))
        res["phi_at_a_deg"] = f(S[ka, 2], 1)
        res["table_tau"] = det[name]["table_tau"]
        res["measured_tau"] = det[name]["tau"]
        res["offset_s"] = {s: f(det[name]["tau"][s] - det[name]["table_tau"][s], 3) for s in "abcd"}
        kc = int(np.argmin(np.abs(taus - det[name]["tau"]["c"])))
        res["theta_c_at_c_deg"] = f(S[kc, 1], 1)
        out[name] = res
    return dict(ja="段階 a の φ の上限を検査器の読み 35° と 30° で比べた（H/Hf・θc・Lo の条件は同じ）。offset_s は測った τ − 表の τ（許容 ±0.3 s）", rows=out)


# ---------------------------------------------------------------- 8. 切った版の座席の暗転
def seat_blackout(ks, pk_on, pk_off):
    S = jload(SEAT)
    eye = np.array(S["eye_world"] if "eye_world" in S else S["seat"]["eye_world"], float)
    res = {}
    for ver, pk in (("art_off", pk_off), ("art_on", pk_on)):
        rd = os.path.join(B27, "%s_default" % ver)
        T = jload(os.path.join(rd, "video", "ds27_frames_tau.json"))
        tt = np.array(T["t"], float)
        tau = np.array(T["tau"], float)
        fr = {}
        for k in range(284, 310):
            X = pk.world(float(tau[k]))
            d = np.hypot(X[..., 0] - eye[0], X[..., 2] - eye[2])
            i = np.unravel_index(int(d.argmin()), d.shape)
            e399 = np.hypot(X[:, 399, 0] - eye[0], X[:, 399, 2] - eye[2])
            j = int(e399.argmin())
            # 目の上の水面：目から水平 1 m 以内の頂点の最高と最低
            near = d < 1.0
            ent = dict(t=f(tt[k], 3), tau=f(tau[k], 3), nearest_vertex=dict(row=int(i[0]), col=int(i[1]), dist_m=f(d[i], 2), y_m=f(X[i][1], 2)),
                       col399_nearest=dict(row=j, dist_m=f(e399[j], 2), y_m=f(X[j, 399, 1], 2)),
                       y_within_1m=[f(float(X[..., 1][near].min()), 2), f(float(X[..., 1][near].max()), 2)] if near.any() else None)
            for view in ("seat", "seat_form"):
                p = os.path.join(rd, "frames", view, "f_%04d.png" % k)
                if os.path.isfile(p):
                    im = np.asarray(Image.open(p).convert("RGB"), np.float64)
                    lum = 0.2126 * im[..., 0] + 0.7152 * im[..., 1] + 0.0722 * im[..., 2]
                    dark_blue = (lum < 90) & (im[..., 2] > im[..., 0] + 15)
                    ent[view] = dict(mean_luma=f(float(lum.mean()), 1), dark_blue_frac=f(float(dark_blue.mean()), 3))
            fr["f%03d" % k] = ent
        res[ver] = fr
    return dict(eye_world=[float(v) for v in eye],
                ja="座席 v1 の目（seat_v1.json の eye_world、y 1.83 m）の近くのシートの頂点と、シートの前の端（列 399）の高さ。連番の各コマの平均の明るさと、"
                   "暗い青（明るさ < 90 かつ B > R + 15）の画素の割合", frames=res)


def main():
    t0 = time.time()
    ks = DG.KStar()
    pk = {v: DG.Package(os.path.join(B27, v), ks) for v in ("art_on", "art_off")}
    g = {v: MD.Generator(v) for v in ("art_on", "art_off")}
    gates = jload(os.path.join(B27, "gates", "art_on_default.json"))["gates"]
    st = gates["P15"]["detail"]["峰で最も高い巻きの行"]["tau"]
    stage_tau = [float(st[s]) for s in "abcd"]
    R = dict(schema="GreatWave.DS27.review_measure/1", number="設計27",
             evidence_kind_ja="numpy の測定（パッケージを Hermite で補間して読む・生成器の解析の値）。記録のみ（関門の判定ではない）",
             inputs={rel(os.path.join(B27, v, n)): pk[v].meta.get(k) for v in ("art_on", "art_off") for n, k in (("ds27_pos_rgba16.bin", "pos_sha256"),)},
             params_sha256=g["art_on"].params_sha)
    print("water", flush=True)
    R["water_art_on"] = water(ks, pk["art_on"], g["art_on"])
    print("hermite", flush=True)
    R["hermite"] = {v: hermite(pk[v], g[v], v) for v in ("art_on", "art_off")}
    print("lips", flush=True)
    R["lips_art_on"] = lips(ks, pk["art_on"], g["art_on"])
    print("art_off", flush=True)
    R["art_off_inherits"] = art_off(ks, pk["art_on"], pk["art_off"], g["art_on"], g["art_off"])
    print("sea", flush=True)
    R["sea_calm"] = sea_calm(g["art_on"])
    print("p2", flush=True)
    R["p2_extent"] = {v: p2_extent(ks, pk[v], v) for v in ("art_on", "art_off")}
    print("profiles", flush=True)
    R["profiles_art_on"] = profiles(ks, pk["art_on"], stage_tau + [-1.8, -1.6, -1.4, -1.2, -1.0, -0.6, 0.0])
    R["profiles_art_on"]["stage_tau_peak_row"] = dict(zip("abcd", stage_tau))
    print("p15", flush=True)
    R["p15_reading_margin_art_on"] = p15_margin(ks, pk["art_on"], gates)
    z = np.load(os.path.join(B27, "art_on", "ds27_sea.npz"))
    ts, Ac = z["tau"], z["Ac"].astype(np.float64)
    ser = {("%.1f" % tv): dict(main=f(Ac[int(np.argmin(np.abs(ts - tv))), ks.main_row], 2), peak=f(Ac[int(np.argmin(np.abs(ts - tv))), ks.peak_row], 2))
           for tv in (-3.9, -3.5, -3.0, -2.0, -1.0, 0.0)}
    kx = np.unravel_index(int(Ac.argmax()), Ac.shape)
    R["carrier_amplitude_art_on"] = dict(ja="行ごとの搬送波の振幅 A_c,r(τ)（ds27_sea.npz の Ac、10 Hz）。毎コマ解き直すので本体の断面積の変化に合わせて上下する",
                                         series=ser, max_m=f(Ac.max(), 2), max_row=int(kx[1]), max_tau=f(ts[kx[0]], 2),
                                         main_row_max_rate_mps=f(float(np.abs(np.diff(Ac[:, ks.main_row]) / np.diff(ts)).max()), 2))
    print("seat", flush=True)
    R["seat_blackout"] = seat_blackout(ks, pk["art_on"], pk["art_off"])
    R["runtime_s"] = round(time.time() - t0, 1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(R, fh, ensure_ascii=False, indent=1, default=lambda o: f(o) if isinstance(o, (np.floating, np.integer)) else str(o))
    print("DS27_REVIEW done %.0f s -> %s" % (R["runtime_s"], rel(OUT)))


if __name__ == "__main__":
    main()
