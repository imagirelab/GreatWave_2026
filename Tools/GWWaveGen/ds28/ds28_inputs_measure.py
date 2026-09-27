# -*- coding: utf-8 -*-
"""設計28：入力条件の変更と較正の掃引の 1 本ごとの測定（生成器の解析式を直接読む。包み・Unity は使わない）。

測るもの（設計27 の関門の検査器 ds27_gates.py の定義を読むだけで使う：row_metrics・STAGE・TH・KStar・load_timewarp）：
  - 段階 a・b・c・d の時刻（P15 の判定と同じ。主断面 行 159 と K* の峰で最も高い巻きの行 行 192）、b の頂の角 θc、
    最初の白と c の差、「先が前へ返る」の目安（前面の最大の角 φ ≥ 110° を初めて満たす時刻）。
  - 関門：P1（峰の地面の速さ）、P4（唇先の弾道）、P5（唇先の速さ）、P6（唇は頂に運ばれる）、P7（巻きの時間）、P10（波峰線に沿った順）、
    P15（段階の順と時刻）、P16（体験の時刻の唇先の見かけの加速度、既定の時間曲線）。しきい値は ds27_gates.TH（設計26 §4.1）。
  - t* の K* との差（全頂点の RMS・最大・主断面の RMS・K* で頂が 3 m 以上の行の RMS）、t* の張り出し Lo/H、
    原画視点（PaintingCam v1）の上の輪郭の差（px）。
  - 唇の逆算の目安の範囲の割合（設計26 E1：u/c0 0.6〜1.3、w/√(gH) −0.2〜0.8）：同じ入力・較正で「入れた版」（唇の終点 K*）を
    作り、K* の唇へ重力だけで着くのに要る打ち出しの速さが目安に入る割合。
  - 利用者の解算の時間（Tools/GWWaveGen/ds27_user_sim_timing.json を Froude で K* へ換算）と比べる量。
差：関門の検査器は包み（16 ビットの keypose を Hermite で補間）を読むが、ここは生成器の解析式を直接読む（量子化なし）。
P4・P5・P6・P16 の速度・加速度は 480 Hz の差分（検査器は Hermite の微分）。P2・P3・P8・P9・P11〜P13 はこの番号では測らない。
"""
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DS27 = os.path.abspath(os.path.join(HERE, "..", "ds27"))
sys.path.insert(0, DS27)
sys.path.insert(0, HERE)
import ds27_gates as DG  # noqa: E402
from ds28_inputs_model import InputGen  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TIMEWARP_DEFAULT = os.path.join(DS27, "timewarp_default.json")
SIM_JSON = os.path.join(REPO, "Tools", "GWWaveGen", "ds27_user_sim_timing.json")
G = 9.81
HZ = 60
HZ_TIP = 480
TIP_FROM = -3.2
TH = DG.TH
STAGE = DG.STAGE
TABLE = dict(a=-4.2, b=-3.4, c=-2.4, d=-2.05)      # 設計26 §3.1（峰の行。主断面は +0.19 s）
MAIN_LAG = 0.19

# PaintingCam v1（Tools/PaintingTruth/painting_truth.json、設計26 の e6_painting_sea.py と同じ）
CAM_POS = np.array([0.0, 3.0, -62.0])
CAM_TGT = np.array([-2.5, 9.7, 4.0])
CAM_W, CAM_H = 1920, 1080
CAM_COLS = (157, 1762)


def f_(x, nd=3):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if math.isfinite(x) else None


def project(P):
    up = np.array([0.0, 1.0, 0.0])
    f = (CAM_TGT - CAM_POS) / np.linalg.norm(CAM_TGT - CAM_POS)
    rt = np.cross(up, f)
    rt /= np.linalg.norm(rt)
    u2 = np.cross(f, rt)
    th = math.tan(math.radians(13.0))
    tw = th * CAM_W / CAM_H
    d = P - CAM_POS
    z = d @ f
    x = d @ rt
    yy = d @ u2
    return np.stack([(x / z / tw + 1) / 2 * CAM_W - 0.5, (1 - (yy / z / th + 1) / 2) * CAM_H - 0.5], -1), z


def upper_outline(X, step=4, dens=3):
    """網を行・列の方向に dens 倍に細かくして（双一次）投影し、原画の列 157〜1762 を step px の帯に分けて、各帯の一番上の y（px）。"""
    nv, nu, _ = X.shape
    iv = np.linspace(0, nv - 1, (nv - 1) * dens + 1)
    iu = np.linspace(0, nu - 1, (nu - 1) * dens + 1)
    i0 = np.minimum(np.floor(iv).astype(int), nv - 2)
    j0 = np.minimum(np.floor(iu).astype(int), nu - 2)
    fv = (iv - i0)[:, None, None]
    fu = (iu - j0)[None, :, None]
    Xd = ((1 - fv) * (1 - fu) * X[i0][:, j0] + fv * (1 - fu) * X[i0 + 1][:, j0] + (1 - fv) * fu * X[i0][:, j0 + 1] + fv * fu * X[i0 + 1][:, j0 + 1])
    px, z = project(Xd.reshape(-1, 3))
    ok = (z > 0) & (px[:, 0] >= CAM_COLS[0]) & (px[:, 0] <= CAM_COLS[1] + 1)
    bins = ((px[ok, 0] - CAM_COLS[0]) // step).astype(int)
    nb = (CAM_COLS[1] - CAM_COLS[0]) // step + 1
    top = np.full(nb, np.inf)
    np.minimum.at(top, bins, px[ok, 1])
    # 一番上の点の高さ（ワールドの y）：帯ごとに一番上の点を選ぶ
    yw = Xd.reshape(-1, 3)[ok, 1]
    order = np.lexsort((px[ok, 1], bins))
    first = np.ones(len(order), bool)
    first[1:] = bins[order][1:] != bins[order][:-1]
    toph = np.full(nb, np.nan)
    toph[bins[order][first]] = yw[order][first]
    return top, toph


def outline_diff(X, Xk, step=4, body_y=1.0, extra_y=5.2):
    a, ha = upper_outline(X, step)
    b, hb = upper_outline(Xk, step)
    # 原画の波の輪郭（K* の一番上の点が静水面の 1 m より上の帯）で比べる。K* が海・空の帯に我々の波（0.25H* = 5.2 m より上）が出る数は別に数える
    fin = np.isfinite(a) & np.isfinite(b) & (b < CAM_H - 1)
    m = fin & (np.nan_to_num(hb, nan=-9) > body_y)
    ex = fin & (np.nan_to_num(hb, nan=-9) <= body_y) & (np.nan_to_num(ha, nan=-9) > extra_y)
    d = np.abs(a[m] - b[m])
    return dict(bins=int(m.sum()), step_px=step, mean_abs_px=f_(d.mean(), 2), p95_abs_px=f_(np.percentile(d, 95), 2), max_abs_px=f_(d.max(), 2),
                signed_mean_px=f_((a[m] - b[m]).mean(), 2), extra_wave_bins=int(ex.sum()),
                note_ja="4 px の帯ごとの一番上の点の縦の差。K* の一番上の点が静水面の 1 m より上の帯（原画の波の輪郭）だけ。extra_wave_bins は、K* では海・空の帯に、"
                        "我々の波（一番上の点が 0.25H* = 5.2 m より上）が出る帯の数。正 = 我々の輪郭が K* より下（低い）"), (np.where(m | ex, a, np.nan), np.where(m, b, np.nan))


def first_true(mask, taus):
    idx = np.nonzero(mask)[0]
    return float(taus[idx[0]]) if len(idx) else None


def sim_reference():
    J = json.load(open(SIM_JSON, encoding="utf-8"))
    v = {q["name"]: q["value"] for q in J["values"]}
    fr = (math.sqrt(20.8 / 6.15), math.sqrt(20.8 / 4.83))          # 時間の倍率 1.84〜2.08
    lr = (20.8 / 6.15, 20.8 / 4.83)                                 # 長さの倍率 3.38〜4.31
    t = lambda x: [round(x * fr[0], 3), round(x * fr[1], 3)]
    return dict(
        source=os.path.relpath(SIM_JSON, REPO).replace("\\", "/"), froude_time=[round(fr[0], 3), round(fr[1], 3)],
        a_to_b_s=t(v["stage_duration_a"]), b_to_c_s=t(v["stage_duration_b"]), onset_to_Lo0p1H_s=t(v["onset_to_overhang_0p1H"]),
        onset_to_tip_0p59H_s=t(v["tip_falls_to_0p59H_after_onset"]), front_90_to_160_s=t(v["front_steepening_90_to_160deg"]),
        jet_u_over_crest=v["jet_initial_horizontal_over_crest_speed"], jet_w_over_sqrt_gH=v["jet_initial_upward_speed_over_sqrt_gH"],
        # 設計26 §7.1 の表と同じ換算（最終の峰 6.15 m の長さの比 3.38 で速さ ×1.84：28〜33 m/s）。噴流の始まりの峰の基準（×2.08）まで含めた幅も記録する
        lateral_spread_mps=[round(v["lateral_breaking_spread_speed"][0] * math.sqrt(lr[0]), 1), round(v["lateral_breaking_spread_speed"][1] * math.sqrt(lr[0]), 1)],
        lateral_spread_mps_both_bases=[round(v["lateral_breaking_spread_speed"][0] * math.sqrt(lr[0]), 1), round(v["lateral_breaking_spread_speed"][1] * math.sqrt(lr[1]), 1)],
        crest_angle_at_vertical_deg=v["crest_angle_at_vertical_front"], onset_H_over_final=v["crest_height_at_onset_over_final"])


class Context:
    """全ての測定で共通のもの（K*、時間曲線、利用者の解算の参照）。"""

    def __init__(self):
        self.ks = DG.KStar()
        self.tw = DG.load_timewarp(TIMEWARP_DEFAULT)
        self.sim = sim_reference()
        self.body_rows = np.nonzero(self.ks.Hrow >= 3.0)[0]


def lip_plausibility(cfg):
    """同じ入力・較正の入れた版（唇の終点 K*）で、E1 の目安の範囲に入る割合と、要る打ち出しの速さの分布。"""
    c2 = dict(cfg, base="art_on", switches=None, crest="kstar", growth="table", jet_cos2=False)
    g = InputGen(c2)
    ub, wb, ok, ev = [], [], 0, 0
    for r, L in g.lip.items():
        m = L["ev"]
        ub.append(L["ub"][m] / g.c0)
        wb.append(L["wb"][m] / math.sqrt(G * g.H[r]))
        ok += L["n_ok"]
        ev += L["n_eval"]
    ub = np.concatenate(ub)
    wb = np.concatenate(wb)
    return dict(fraction=f_(ok / max(ev, 1), 4), n_eval=int(ev), u_over_c0_p5_50_95=[f_(np.percentile(ub, q), 3) for q in (5, 50, 95)],
                w_over_sqrt_gH_p5_50_95=[f_(np.percentile(wb, q), 3) for q in (5, 50, 95)], c0_mps=f_(g.c0, 3),
                rows_out_of_range_c_m=([f_(g.K.c[r], 2) for r, L in g.lip.items() if L["n_ok"] < L["n_eval"]][:3] + ["…"]
                                       if any(L["n_ok"] < L["n_eval"] for L in g.lip.values()) else []),
                note_ja="同じ入力・較正の入れた版（ds_lip_target_kstar。唇の終点 = K*）の解。設計26 E1 の目安（u/c0 0.6〜1.3、w/√(gH) −0.2〜0.8、t* の 0.15 s 前より後に放す点は除く）")


def measure(ctx, cfg, tstar_only=False, keep_sections=True, log=print):
    t0 = time.time()
    ks = ctx.ks
    g = InputGen(cfg)
    nv, nu = ks.nv, ks.nu
    mr, pr = ks.main_row, ks.peak_row
    rows_k = ks.curled_idx
    R = dict(cfg=g.cfg_record())
    # ---- t* の姿（海を含むワールド）
    X0 = g.world(0.0)
    d = np.linalg.norm(X0 - ks.X, axis=-1)
    i = np.unravel_index(int(d.argmax()), d.shape)
    br = ctx.body_rows
    od, (top_run, top_k) = outline_diff(X0, ks.X)
    A0, Y0, _ = ks.section(X0)
    rm0 = DG.row_metrics(A0, Y0, ks.crest_hi, ks.j_E)
    Lo_H0 = rm0["Lo"] / np.maximum(rm0["H"], 1e-9)
    R["tstar"] = dict(rms_m=f_(np.sqrt((d ** 2).mean()), 3), max_m=f_(d.max(), 2), max_at=dict(row=int(i[0]), col=int(i[1]), c_m=f_(ks.c[i[0]], 2)),
                      main_row_rms_m=f_(np.sqrt((d[mr] ** 2).mean()), 3), peak_row_rms_m=f_(np.sqrt((d[pr] ** 2).mean()), 3),
                      body_rows_rms_m=f_(np.sqrt((d[br] ** 2).mean()), 3),
                      body_cols_rms_m=f_(np.sqrt((d[br][:, 18:ks.j_E + 1] ** 2).mean()), 3),
                      body_cols_note_ja="K* の頂が 3 m 以上の行（175 行）の本体の列（j_B 18〜j_E 394）だけ。うねり・搬送波の余白を除く",
                      painting_upper_outline=od,
                      overhang_Lo_over_H=dict(main=f_(Lo_H0[mr], 3), peak=f_(Lo_H0[pr], 3), curled_median=f_(np.nanmedian(Lo_H0[rows_k]), 3),
                                              kstar_main=0.41, kstar_note_ja="K* の主断面の Lo/H は 0.41（設計26 §3.1）"),
                      crest_H_m=dict(main=f_(rm0["H"][mr], 2), peak=f_(rm0["H"][pr], 2), max=f_(np.nanmax(rm0["H"]), 2),
                                     kstar_main=f_(ks.Hrow[mr], 2), kstar_peak=f_(ks.Hrow[pr], 2)))
    R["lip_plausibility_E1"] = lip_plausibility(cfg)
    R["tstar_top_px"] = dict(run=top_run, kstar=top_k)
    if tstar_only:
        R["runtime_s"] = round(time.time() - t0, 1)
        return R, None
    # ---- 時系列：60 Hz（τ −12〜0）と、唇先の 480 Hz（τ −3.2〜0）
    t60 = -np.arange(int(round(12.0 * HZ)), -1, -1) / HZ
    t480 = -np.arange(int(round(-TIP_FROM * HZ_TIP)), -1, -1) / HZ_TIP
    keys = ("H", "ca", "phi", "phib", "psi", "Lo", "theta")
    S = {k: np.zeros((len(t60), nv)) for k in keys}
    secs = {mr: [], pr: []}
    tipc = ks.tip_col
    tipA = np.zeros((len(t480), len(rows_k)))
    tipY = np.zeros((len(t480), len(rows_k)))
    lipsec = {mr: [], pr: []}
    for k, tau in enumerate(t60):
        A, Y = g.sections(float(tau))
        Ag = A - g.frame_X(float(tau))
        rm = DG.row_metrics(Ag, Y, ks.crest_hi, ks.j_E)
        for kk in keys:
            S[kk][k] = rm[kk]
        if keep_sections:
            for r in (mr, pr):
                secs[r].append(np.stack([A[r], Y[r]], 0).astype(np.float32))
    for k, tau in enumerate(t480):
        A, Y = g.sections(float(tau))
        Ag = A - g.frame_X(float(tau))
        tipA[k] = Ag[rows_k, tipc[rows_k]]
        tipY[k] = Y[rows_k, tipc[rows_k]]
        if k >= len(t480) - 2:
            for r in (mr, pr):
                lipsec[r].append((Ag[r].copy(), Y[r].copy()))
    rpos = {int(r): j for j, r in enumerate(rows_k)}
    h = 1.0 / HZ_TIP
    tipVa = np.gradient(tipA, h, axis=0)
    tipVy = np.gradient(tipY, h, axis=0)
    Hf = S["H"][-1]
    Hn = S["H"] / np.maximum(Hf[None, :], 1e-9)
    ca_v = np.gradient(S["ca"], t60, axis=0)
    # 噴流の始まり（φ ≥ 90° を初めて満たす）
    onset = np.full(nv, np.nan)
    for r in rows_k:
        tt = first_true(np.nan_to_num(S["phi"][:, r], nan=0.0) >= 90.0, t60)
        if tt is not None:
            onset[r] = tt
    T = g.twhite().astype(np.float64)
    finalw = (T < DG.NEVER) & (T <= 0.0)
    named = {mr: "main_159", pr: "peak_192"}
    G_ = {}
    # ---- P1
    i3 = int(np.argmin(np.abs(t60 + TH["P1_window_s"])))
    p1 = {}
    ok = True
    for r in (mr, pr):
        spd = (S["ca"][-1, r] - S["ca"][i3, r]) / (t60[-1] - t60[i3])
        back = DG.drawdown(S["ca"][:, r])
        p1[named[r]] = dict(speed_mps=f_(spd, 2), back_m=f_(back, 3))
        ok &= spd >= TH["P1_speed_mps"] and back <= TH["P1_back_m"]
    G_["P1"] = dict(pass_=bool(ok), **p1)

    def tip_series(r):
        j = rpos[r]
        return tipA[:, j], tipY[:, j], tipVa[:, j], tipVy[:, j]

    # ---- P4
    p4 = {}
    ok = True
    for r in (mr, pr):
        a_, y_, va_, vy_ = tip_series(r)
        yK = y_[-1]
        start = onset[r] if np.isfinite(onset[r]) else t480[0]
        m = t480 >= start
        k_ap = int(np.nonzero(m)[0][0] + np.argmax(y_[m]))
        t_ap = float(t480[k_ap])
        wins = []
        tw0 = t_ap
        while tw0 < -1e-9:
            tw1 = min(tw0 + TH["P4_win_s"], 0.0)
            if tw1 - tw0 < 0.5 * TH["P4_win_s"] and wins:
                break
            v0, v1 = np.interp(tw0, t480, vy_), np.interp(tw1, t480, vy_)
            wins.append(round(float((v1 - v0) / (tw1 - tw0)), 2))
            tw0 = tw1
        y_ap = float(y_[k_ap])
        after = np.nonzero((t480 > t_ap) & (y_ <= yK + 1e-6))[0]
        t_reach = float(t480[after[0]]) if len(after) else 0.0
        fall = t_reach - t_ap
        fall_ref = math.sqrt(max(2 * (y_ap - yK) / G, 0.0))
        fr = fall / fall_ref if fall_ref > 0 else float("nan")
        okr = (len(wins) > 0 and all(TH["P4_acc_lo"] <= w <= TH["P4_acc_hi"] for w in wins) and np.isfinite(fr) and abs(fr - 1) <= TH["P4_fall_tol"])
        ok &= okr
        p4[named[r]] = dict(apex_tau=f_(t_ap), apex_y_m=f_(y_ap, 2), window_acc_mps2=wins, fall_ratio=f_(fr), pass_=bool(okr))
    G_["P4"] = dict(pass_=bool(ok), **p4)
    # ---- P5
    p5 = {}
    ok = True
    for r in (mr, pr):
        if not np.isfinite(onset[r]):
            p5[named[r]] = dict(note="no onset")
            ok = False
            continue
        te = min(onset[r] + min(0.6, -onset[r] / 2), 0.0)
        a_, y_, va_, vy_ = tip_series(r)
        m = (t480 >= onset[r]) & (t480 <= te + 1e-9)
        if not m.any():
            p5[named[r]] = dict(note="window outside tip series")
            ok = False
            continue
        k = int(np.nonzero(m)[0][0] + np.argmax(va_[m]))
        u = float(va_[k])
        cs = float(np.interp(t480[k], t60, ca_v[:, r]))
        p5[named[r]] = dict(tip_u_mps=f_(u, 2), crest_speed_mps=f_(cs, 2), ratio=f_(u / max(cs, 1e-9), 3))
        ok &= (u >= TH["P5_speed_mps"]) and (u >= cs)
    G_["P5"] = dict(pass_=bool(ok), **p5)
    # ---- P6（t* の唇に沿った地面の速さ：最後の 2 コマの片側の差）
    p6 = {}
    ok = True
    for r in (mr, pr):
        q = ks.cq[r]
        (a1, y1), (a2, y2) = lipsec[r][-2], lipsec[r][-1]
        va = (a2 - a1) / h
        vy = (y2 - y1) / h
        sl = slice(q["jt"], q["jtip"] + 1)
        sp = np.hypot(va[sl], vy[sl])
        root, tip = sp[0], sp[-1]
        mid = sp[1:-1].min() if len(sp) > 2 else root
        r1 = mid / max(root, 1e-9)
        r2 = va[sl][0] / max(va[sl][-1], 1e-9)
        okr = (r1 >= TH["P6_mid_over_root"]) and (r2 >= TH["P6_root_over_tip_h"])
        ok &= okr
        p6[named[r]] = dict(mid_over_root=f_(r1), root_h_over_tip_h=f_(r2), tip_speed_mps=f_(tip, 2))
    G_["P6"] = dict(pass_=bool(ok), **p6)
    # ---- P7
    p7 = {}
    ok = True
    for r in (mr, pr):
        dur = -onset[r] if np.isfinite(onset[r]) else None
        p7[named[r]] = f_(dur)
        ok &= dur is not None and TH["P7_lo_s"] <= dur <= TH["P7_hi_s"]
    oc = onset[rows_k]
    G_["P7"] = dict(pass_=bool(ok), **p7, curled_rows_without_onset=int((~np.isfinite(oc)).sum()))
    # ---- P10
    okr = [r for r in rows_k if np.isfinite(onset[r])]
    corr = float(np.corrcoef(onset[okr], Hf[okr])[0, 1]) if len(okr) >= 3 else None
    t50 = np.array([first_true(S["H"][:, r] >= 0.5 * Hf[r], t60) or np.nan for r in rows_k], dtype=float)
    std50 = float(np.nanstd(t50))
    G_["P10"] = dict(pass_=bool(corr is not None and corr <= TH["P10_corr"] and std50 >= TH["P10_std_s"]), corr=f_(corr), t50_std_s=f_(std50),
                     t50_range=[f_(np.nanmin(t50)), f_(np.nanmax(t50))])
    # ---- P15 と段階の見た目
    st = {}
    ok = True
    for r in (mr, pr):
        res = stage_times(S, t60, r, Hn[:, r], T, finalw, ks, tip_series if r in rpos else None, t480, ca_v)
        want = {k: TABLE[k] + (MAIN_LAG if r == mr else 0.0) for k in "abcd"}
        tt = [res["tau"][k] for k in "abcd"]
        order = all(v is not None for v in tt) and all(tt[i] < tt[i + 1] for i in range(3))
        within = all(res["tau"][k] is not None and abs(res["tau"][k] - want[k]) <= TH["P15_tol_s"] for k in "abcd")
        ok &= order and within and res["white_ok"]
        # 見た目の値
        kb = res["tau"]["b"] if res["tau"]["b"] is not None else want["b"]
        ib = int(np.argmin(np.abs(t60 - kb)))
        th_b = S["theta"][ib, r]
        mwin = (t60 >= want["b"] - 0.5) & (t60 <= want["c"])
        th_min_b = float(np.nanmin(S["theta"][mwin, r])) if mwin.any() else None
        fwd = first_true(np.nan_to_num(S["phi"][:, r], nan=0.0) >= 110.0, t60)
        lo01 = first_true(np.nan_to_num(S["Lo"][:, r] / np.maximum(S["H"][:, r], 1e-9), nan=0.0) >= 0.1, t60)
        st[named[r]] = dict(tau={k: f_(v) for k, v in res["tau"].items()}, table={k: f_(v) for k, v in want.items()},
                            dev={k: (f_(res["tau"][k] - want[k]) if res["tau"][k] is not None else None) for k in "abcd"},
                            order_ok=bool(order), within_tol=bool(within), white_ok=bool(res["white_ok"]),
                            first_white=f_(res["first_white"]), onset=f_(onset[r]),
                            theta_c_at_b_deg=f_(th_b, 1), theta_c_min_b_window_deg=f_(th_min_b, 1),
                            H_over_Hf_at_b=f_(Hn[ib, r]), phi_ge_110_tau=f_(fwd), Lo_ge_0p1H_tau=f_(lo01),
                            H_over_Hf_at_table={k: f_(np.interp(want[k], t60, Hn[:, r])) for k in "abcd"})
    G_["P15"] = dict(pass_=bool(ok), **st)
    # ---- P16（既定の時間曲線）
    G_["P16"] = p16(ctx, t480, tipY, rows_k, onset, g)
    # ---- 利用者の解算の時間との比較（峰の行と主断面）
    simcmp = {}
    for r in (mr, pr):
        s_ = st[named[r]]["tau"]
        on = onset[r]
        a_, y_, va_, vy_ = tip_series(r)
        t059 = None
        if np.isfinite(on):
            m = (t480 > on) & (y_ <= 0.595 * np.interp(t480, t60, S["H"][:, r]))
            k_ap = int(np.argmax(np.where(t480 >= on, y_, -np.inf)))
            m &= t480 > t480[k_ap]
            t059 = float(t480[np.nonzero(m)[0][0]]) - on if m.any() else None
        f90 = first_true(np.nan_to_num(S["phi"][:, r], nan=0.0) >= 90.0, t60)
        f160 = first_true(np.nan_to_num(S["phi"][:, r], nan=0.0) >= 160.0, t60)
        lo01 = st[named[r]]["Lo_ge_0p1H_tau"]
        ramp = on + min(0.6, -on / 2) if np.isfinite(on) else None
        w_post = float(np.interp(ramp, t480, vy_)) / math.sqrt(G * Hf[r]) if ramp is not None and ramp >= t480[0] else None
        L_ = g.lip.get(int(r))
        if L_ is not None:
            it = int(np.nonzero(L_["upm"])[0][-1])
            launch = dict(jet_launch_u_over_crest=f_(L_["u2"][it] / max(L_["ci"][it], 1e-9)), jet_launch_w_over_sqrt_gH=f_(L_["w2"][it] / math.sqrt(G * g.H[r])),
                          jet_launch_tau=f_(-L_["Ti"][it]))
        else:
            launch = dict(jet_launch_u_over_crest=None, jet_launch_w_over_sqrt_gH=None, jet_launch_tau=None)
        simcmp[named[r]] = dict(**launch,
            a_to_b_s=f_(s_["b"] - s_["a"]) if s_["a"] is not None and s_["b"] is not None else None,
            b_to_c_s=f_(s_["c"] - s_["b"]) if s_["b"] is not None and s_["c"] is not None else None,
            onset_to_Lo0p1H_s=f_(lo01 - on) if lo01 is not None and np.isfinite(on) else None,
            onset_to_tip_0p59H_s=f_(t059), front_90_to_160_s=f_(f160 - f90) if (f90 is not None and f160 is not None) else None,
            jet_u_over_crest=st_ratio(G_["P5"], named[r]), jet_w_over_sqrt_gH_after_ramp=f_(w_post),
            onset_H_over_final=f_(np.interp(on, t60, Hn[:, r])) if np.isfinite(on) else None,
            theta_c_at_onset_deg=f_(np.interp(on, t60, S["theta"][:, r])) if np.isfinite(on) else None)
    # 波峰線に沿った広がりの実効の速さ（始まりの時刻 vs 峰の行からの距離の傾き）
    cc = ks.c[okr]
    dd = np.abs(cc - g.c_pk)
    if len(okr) > 5 and np.ptp(onset[okr]) > 0:
        slope = np.polyfit(onset[okr], dd, 1)[0]
        simcmp["lateral_spread_mps_fit"] = f_(slope, 1)
    R["gates"] = G_
    R["sim_compare"] = simcmp
    R["onset"] = dict(main=f_(onset[mr]), peak=f_(onset[pr]), curled_range=[f_(np.nanmin(oc)), f_(np.nanmax(oc))])
    R["runtime_s"] = round(time.time() - t0, 1)
    series = dict(t60=t60, H_main=S["H"][:, mr], H_peak=S["H"][:, pr], theta_main=S["theta"][:, mr], theta_peak=S["theta"][:, pr],
                  phi_main=S["phi"][:, mr], phi_peak=S["phi"][:, pr], Lo_main=S["Lo"][:, mr], Lo_peak=S["Lo"][:, pr],
                  ca_main=S["ca"][:, mr], ca_peak=S["ca"][:, pr])
    if keep_sections:
        series["sec_main"] = np.stack(secs[mr], 0)
        series["sec_peak"] = np.stack(secs[pr], 0)
    return R, series


def st_ratio(p5, key):
    q = p5.get(key, {})
    return q.get("ratio") if isinstance(q, dict) else None


def stage_times(S, taus, r, Hn, T, finalw, ks, tip_series, t480, ca_v):
    """ds27_gates.stage_times と同じ判定（唇先の水平の速さは 480 Hz の差分）。"""
    st = STAGE
    H = S["H"][:, r]
    phi = S["phi"][:, r]
    phib = S["phib"][:, r]
    psi = S["psi"][:, r]
    th = S["theta"][:, r]
    Lo0 = np.nan_to_num(S["Lo"][:, r] / np.maximum(H, 1e-9), nan=0.0)
    rowT = np.where(finalw[r], T[r], np.inf)
    white_n = (rowT[None, :] <= taus[:, None]).sum(1)
    dH = np.gradient(H, taus)
    if tip_series is not None:
        _, _, va_, _ = tip_series(r)
        u_tip = np.interp(taus, t480, va_, left=np.nan)
    else:
        u_tip = np.full(len(taus), np.nan)
    B = u_tip / np.maximum(ca_v[:, r], 1e-6)
    thf = np.nan_to_num(th, nan=180.0)
    a = st["a"]
    ma = (Hn >= a["H"][0]) & (Hn <= a["H"][1]) & (thf >= a["theta_min"]) & (np.nan_to_num(phi, nan=0.0) <= a["phi_max"]) & (Lo0 <= a["Lo_max"]) & (white_n == 0)
    b = st["b"]
    mb = ((Hn >= b["H"][0]) & (Hn <= b["H"][1]) & (np.nan_to_num(phi, nan=0.0) >= b["phi_min"]) & (np.nan_to_num(th, nan=999) <= b["theta_max"])
          & (Lo0 <= b["Lo_max"]) & (np.abs(np.nan_to_num(phi, nan=0.0) - np.nan_to_num(psi, nan=0.0)) >= b["asym_deg"]) & (white_n == 0))
    c = st["c"]
    mc = ((Hn >= c["H"][0]) & (Hn <= c["H"][1]) & (np.nan_to_num(phib, nan=0.0) >= c["phi_band_min"])
          & (np.nan_to_num(th, nan=0) >= c["theta"][0]) & (np.nan_to_num(th, nan=999) <= c["theta"][1]) & (Lo0 < c["Lo_max"]))
    d = st["d"]
    md = (Lo0 >= d["Lo_min"]) & (Hn >= d["H_min"]) & (dH > 0) & (np.nan_to_num(B, nan=0.0) >= d["B_min"])
    res = {k: first_true(m_, taus) for k, m_ in zip("abcd", (ma, mb, mc, md))}
    fw = float(rowT.min()) if np.isfinite(rowT.min()) else None
    wok = False
    if fw is not None and res["c"] is not None:
        hi = res["d"] if res["d"] is not None else 0.0
        wok = (fw >= res["c"] - 1.0 / 30 - 1e-9) and (fw <= hi + 1e-9)
        cmin = int(np.argmin(rowT))
        tip_ok = bool(ks.is_curled[r] and abs(ks.s_arc[r, cmin] - ks.s_arc[r, ks.tip_col[r]]) <= TH["P9_tip_arc_over_H"] * ks.Hrow[r])
        wok = wok and tip_ok
    return dict(tau=res, first_white=fw, white_ok=bool(wok))


def p16(ctx, t480, tipY, rows_k, onset, g):
    """ds27_gates.p16 と同じ窓と許容。y は生成器の唇先の 480 Hz の表を τ(t) で線形に読む（Δτ ≤ 1/480 s）。"""
    tw = ctx.tw
    t, tau = tw["t"], tw["tau"]
    dt = 1.0 / 240
    tg = np.arange(0, 12.5 + 1e-9, dt)
    tg_tau = np.interp(tg, t, tau)
    rr = np.gradient(tg_tau, tg)
    rr_s = np.convolve(rr, np.ones(4) / 4, mode="same")
    rd = np.gradient(rr_s, tg)
    kstar = int(np.nonzero(tg_tau >= -1e-9)[0][0])
    t_star = float(tg[kstar])
    k = kstar
    while k > 0 and rr[k] < 0.02:
        k -= 1
    while k > 0 and rd[k] < -0.01:
        k -= 1
    t_stop = float(tg[k])
    t_end = t_stop if (t_star - t_stop) <= TH["P16_stop_ramp_max_s"] + 1e-9 else t_star - TH["P16_stop_ramp_max_s"]
    s = int(round(240 / 30))
    worst = (-np.inf, None, None)
    n_fail = n_eval = 0
    for j, r in enumerate(rows_k):
        if not np.isfinite(onset[r]):
            continue
        T_row = float(g.T_row[r])
        te = max(onset[r] + min(0.6, -onset[r] / 2), -T_row + min(0.6, T_row / 2))
        yy = np.interp(np.clip(tg_tau, t480[0], 0.0), t480, tipY[:, j])
        A = np.full_like(yy, np.nan)
        A[s:-s] = (yy[2 * s:] - 2 * yy[s:-s] + yy[:-2 * s]) / (s * dt) ** 2
        m = (tg_tau >= te) & (tg <= t_end - s * dt - 1e-9) & np.isfinite(A) & (tg_tau >= t480[0] + s * dt)
        if not m.any():
            continue
        n_eval += 1
        i = int(np.nonzero(m)[0][np.argmax(A[m])])
        if A[i] > TH["P16_tol_mps2"]:
            n_fail += 1
        if A[i] > worst[0]:
            worst = (float(A[i]), int(r), float(tg[i]))
    return dict(pass_=bool(n_eval > 0 and n_fail == 0), worst_A_mps2=f_(worst[0]), worst_row=worst[1], worst_t=f_(worst[2]),
                rows_evaluated=n_eval, rows_failing=n_fail, timewarp=os.path.relpath(TIMEWARP_DEFAULT, REPO).replace("\\", "/"))
