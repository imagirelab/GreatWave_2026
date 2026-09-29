# -*- coding: utf-8 -*-
"""設計28修正01 試行C（Q15）：巻き下がり（唇先の頂に対する高さ）の時機の測定と要の図。V80（試行B）と試行C の変種を比べる。

読むもの（どれも Git 対象外。パッケージは ds27_gates.Package（Unity の再生器と同じ Hermite）で読む。生成器のコードは読まない）：
  パッケージ：V80 Unity/Build/Design/28R01B/V80/art_on、試行C <根>/<変種>/art_on
  時間曲線：既定（V80 は試行B の timewarp_default_V80.json、試行C は ds28r01c/timewarp_default_<変種>.json＝同じ規則）、
    比べ：規則のまま 0.7 倍（<根>/warps/tw_r07_<版>.json）、V80 の既定の表そのまま、代案（ds27/timewarp_alt.json）
  生成器の記録（<パッケージ>/ds28r01?_generate_log.json の lip_launch：唇先の放出の時刻と補間の長さ。放出の後の重力の確かめだけに使う）
測るもの（主断面 行 159・峰の行 行 192。唇先＝K* の唇先の列、頂＝行の断面の頂の高さ H（ds27_gates.row_metrics））：
  h(τ) = 唇先の高さ − H。見える始まり τ_vis（試行B のレビューと同じ：唇先が唇の動きの始まりから前へ 0.5 m、かつ Lo ≥ 0.1H が t* まで続く、
  の遅い方）、見える最高点 τ_top = −2.1 s（進行役の定義：頂の速い上昇が終わる所、V80 の既定の画面で t ≈ 8.0 s）。
  頂に対する下がり D = h(τ_vis) − h(0)。その割合：τ_top までに、物理の最後の 1 s に、画面で t = 10 s の後に（時間曲線ごと）。
  単調さ：τ_vis の後に h が前の最小より上がった量の最大（許容 0.05 m）。頂に対する下がりの速さ・加速度（物理・画面）。
  唇のすべての点（巻きの行すべての K* の jt+1..rim の列）の、自分の頂点の後の上下の加速度の最大（物理の時刻、h = 1/60 s）と、
  画面の見かけの加速度 A = d²y(τ(t))/dt² の最大（h = 1/30 s、関門 P16 と同じ読み、止めるための区間の前まで）。
  唇先の放出の後の加速度（放出＋補間の後から t* まで、h = 1/60 s）。
使い方（リポジトリの根で。約 5〜8 分）：py -3.10 -B Tools/GWWaveGen/ds28r01c/ds28r01c_curl.py [--tags V80,C1,C2] [--root Unity/Build/Design/28R01C]
出力：<根>/review/curl_ds28r01c.json・fig_ds28r01c_curl.png
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for p in ("ds27", "ds28", "ds28r01b"):
    q = os.path.join(REPO, "Tools", "GWWaveGen", p)
    if q not in sys.path:
        sys.path.insert(0, q)
import ds27_gates as DG  # noqa: E402
import ds28_gates_extra as DX  # noqa: E402
import ds28r01b_review as RB  # noqa: E402

RB.HZ = 240
HZ = 240
G = 9.81
TAU_TOP = -2.1
ROWS = {"main": 159, "peak": 192}
COL = {"V80": (30, 90, 200), "C1": (20, 150, 60), "C2": (220, 110, 0)}
LABEL = {"V80": "V80（試行B）", "C1": "C1 伸びに比例", "C2": "C2 巻きが先行"}
FONT = "C:/Windows/Fonts/YuGothM.ttc"
TWALT = os.path.join(REPO, "Tools", "GWWaveGen", "ds27", "timewarp_alt.json")
TWV80 = os.path.join(REPO, "Tools", "GWWaveGen", "ds28r01b", "timewarp_default_V80.json")
SEC_TAUS = ["vis", TAU_TOP, -1.5, -1.0, -0.5, 0.0]


def font(sz):
    return ImageFont.truetype(FONT, sz)


def r3(x, nd=3):
    return None if x is None or not np.isfinite(x) else round(float(x), nd)


def rel(p):
    return os.path.relpath(os.path.abspath(p), REPO).replace("\\", "/")


def jload(p):
    return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else None


def paths(tag, root):
    if tag == "V80":
        pkg = os.path.join(REPO, "Unity", "Build", "Design", "28R01B", "V80", "art_on")
        return dict(pkg=pkg, genlog=os.path.join(pkg, "ds28r01b_generate_log.json"),
                    warps=dict(default=TWV80, r07=os.path.join(root, "warps", "tw_r07_V80.json"), v80=TWV80, alt=TWALT))
    pkg = os.path.join(root, tag, "art_on")
    twd = os.path.join(root, "warps", "timewarp_default_%s.json" % tag)
    if not os.path.isfile(twd):
        twd = os.path.join(REPO, "Tools", "GWWaveGen", "ds28r01c", "timewarp_default_%s.json" % tag)
    return dict(pkg=pkg, genlog=os.path.join(pkg, "ds28r01c_generate_log.json"),
                warps=dict(default=twd,
                           r07=os.path.join(root, "warps", "tw_r07_%s.json" % tag), v80=TWV80, alt=TWALT))


class Warp(RB.Warp):
    def __init__(self, p):
        RB.Warp.__init__(self, p)
        self.path = p
        tg = np.arange(0, 12.5 + 1e-9, 1.0 / 240)
        tq = np.interp(tg, self.t, self.tau)
        rr = np.gradient(tq, tg)
        rr_s = np.convolve(rr, np.ones(4) / 4, mode="same")
        rd = np.gradient(rr_s, tg)
        kstar = int(np.nonzero(tq >= -1e-9)[0][0])
        k = kstar
        while k > 0 and rr[k] < 0.02:
            k -= 1
        while k > 0 and rd[k] < -0.01:
            k -= 1
        t_stop = float(tg[k])
        self.t_star = float(tg[kstar])
        self.t_end = t_stop if self.t_star - t_stop <= 0.5 + 1e-9 else self.t_star - 0.5   # 関門 P16 と同じ
        self.tg, self.tq, self.rate = tg, tq, rr

    def tau_of(self, t):
        return float(np.interp(t, self.t, self.tau))


def lip_on(ks, cond):
    """唇の動きの始まり（運びの始まり σ −3.45 ＋ 行の遅れ）。V80・試行C で同じ。"""
    Tc = DX.calib_onset(ks, cond)
    RBp = jload(os.path.join(REPO, "Tools", "GWWaveGen", "ds28r01b", "ds28r01b_params.json"))
    sb = float(RBp["variants"]["V80"]["carry_start_sigma"])
    return sb + (abs(cond["tau0"]) - Tc)


def diff2(y, s, dt):
    """中心差分（間隔 s サンプル）。戻り (y', y'') を y と同じ長さ（端は nan）。"""
    d1 = np.full_like(y, np.nan)
    d2 = np.full_like(y, np.nan)
    d1[s:-s] = (y[2 * s:] - y[:-2 * s]) / (2 * s * dt)
    d2[s:-s] = (y[2 * s:] - 2 * y[s:-s] + y[:-2 * s]) / (s * dt) ** 2
    return d1, d2


def row_curl(S, j, tau_on, warps):
    taus = S["taus"]
    H = S["H"][:, j]
    ty = S["tip_y"][:, j]
    h = ty - H
    vis = RB.visible(S, j, tau_on)
    tv = vis["visible"]["tau"] if vis.get("visible") else None
    kv = int(np.argmin(np.abs(taus - tv)))
    kt = int(np.argmin(np.abs(taus - TAU_TOP)))
    k1 = int(np.argmin(np.abs(taus + 1.0)))
    D = float(h[kv] - h[-1])
    aft = h[kv:]
    rise = float(np.max(aft - np.minimum.accumulate(aft)))
    dt = 1.0 / HZ
    s = 4
    dh, d2h = diff2(h, s, dt)
    dy, d2y = diff2(ty, s, dt)
    m = (np.arange(len(taus)) >= kv) & np.isfinite(dh)
    # 唇先の頂点（唇の動きの始まりの後の最高点）と、その後の上向きの加速度
    kon = int(np.argmin(np.abs(taus - tau_on)))
    kap = kon + int(np.argmax(ty[kon:]))
    mm = (np.arange(len(taus)) > kap) & np.isfinite(d2y)
    e = dict(tau_on=r3(tau_on), visible=vis.get("visible"), fwd05=vis.get("fwd0.5"), Lo010=vis.get("Lo0.10"),
             tau_top=TAU_TOP, H_over_Hf_at_top=r3(H[kt] / H[-1]),
             h_at_visible_m=r3(h[kv]), h_at_top_m=r3(h[kt]), h_at_tstar_m=r3(h[-1]), drop_total_m=r3(D),
             share_before_top=r3((h[kv] - h[kt]) / D), share_last_1s_physical=r3((h[k1] - h[-1]) / D),
             monotone_max_rise_m=r3(rise), monotone_ok=bool(rise <= 0.05),
             rel_descent_speed_max_mps=r3(float(np.nanmax(-dh[m]))), rel_descent_speed_max_tau=r3(float(taus[m][np.nanargmax(-dh[m])])),
             rel_descent_accel_max_mps2=r3(float(np.nanmax(-d2h[m]))), rel_descent_decel_max_mps2=r3(float(np.nanmax(d2h[m]))),
             rel_descent_decel_max_tau=r3(float(taus[m][np.nanargmax(d2h[m])])),
             tip_apex_tau=r3(taus[kap]), tip_apex_y_m=r3(ty[kap]), tip_apex_minus_crest_m=r3(h[kap]),
             tip_max_up_accel_after_apex_mps2=r3(float(np.nanmax(d2y[mm]))) if mm.any() else None,
             h_at={("%+.2f" % t): r3(float(np.interp(t, taus, h))) for t in (-3.3, -3.0, -2.7, -2.4, -2.1, -1.8, -1.5, -1.2, -0.9, -0.6, -0.3, 0.0)},
             tip_y_at={("%+.2f" % t): r3(float(np.interp(t, taus, ty))) for t in (-3.0, -2.7, -2.4, -2.1, -1.5, -1.0, -0.5, 0.0)},
             rel_descent_speed_at={("%+.2f" % t): r3(float(np.interp(t, taus[s:-s], -dh[s:-s]))) for t in (-2.7, -2.4, -2.1, -1.5, -1.0, -0.5, -0.1)},
             screen={})
    # 頂の速い上昇が終わる所（別の読み）：頂の上がる速さが 1.5 m/s 以下に落ちる最初の τ（最大の速さの後）
    dH, _ = diff2(H, s, dt)
    kmx = int(np.nanargmax(dH))
    ks_ = np.nonzero((np.arange(len(taus)) > kmx) & (dH <= 1.5))[0]
    e["crest_fast_rise_end_tau_1p5mps"] = r3(taus[ks_[0]]) if len(ks_) else None
    for wn, W in warps.items():
        if W is None:
            continue
        t10 = W.tau_of(10.0)
        tq = W.tq
        tg = W.tg
        hh = np.interp(np.clip(tq, taus[0], 0.0), taus, h)
        dhs = np.gradient(hh, tg)
        d2hs = np.gradient(dhs, tg)
        tv_s = W.t_of(tv)
        mw = (tg >= (tv_s if tv_s is not None else 0.0)) & (tg <= W.t_end)
        slow = W.params.get("slow_reached_tau")
        e["screen"][wn] = dict(warp=rel(W.path), tau_at_t10=r3(t10), share_after_t10=r3((float(np.interp(t10, taus, h)) - h[-1]) / D),
                               t_visible=r3(tv_s, 2), t_top=r3(W.t_of(TAU_TOP), 2), t_tip_apex=r3(W.t_of(float(taus[kap])), 2),
                               slow_reached_tau=r3(slow) if slow is not None else None,
                               t_slow_reached=r3(W.t_of(slow), 2) if slow is not None else None,
                               share_in_slow=r3((float(np.interp(slow, taus, h)) - h[-1]) / D) if slow is not None and slow > taus[0] else None,
                               rel_descent_speed_max_screen_mps=r3(float(np.max(-dhs[mw]))) if mw.any() else None,
                               rel_descent_screen_decel_max_mps2=r3(float(np.max(d2hs[mw]))) if mw.any() else None)
    return e, h


def lip_braking(pk, ks, warps, tau_start=-3.6, chunk=12):
    """唇のすべての点（巻きの行の jt+1..rim）：物理の時刻と画面（時間曲線ごと）の、自分の頂点の後の上下の加速度の最大。"""
    nu = ks.nu
    dt = 1.0 / HZ
    taus = np.round(np.arange(tau_start, 1e-9, dt), 9)
    taus[-1] = 0.0
    out = dict(physical=dict(worst=-np.inf), screen={k: dict(worst=-np.inf, n_fail=0, n_fail_0p5=0) for k in warps if warps[k] is not None})
    n_eval = 0
    rows = list(ks.curled)
    for c0 in range(0, len(rows), chunk):
        part = rows[c0:c0 + chunk]
        vidx, meta = [], []
        for q in part:
            for jcol in range(q["jt"] + 1, q["rim"] + 1):
                vidx.append(q["r"] * nu + jcol)
                meta.append((q["r"], jcol))
        vidx = np.array(vidx, int)
        Yp = pk.sub(taus, vidx, 0)[..., 1]
        kap = np.argmax(Yp, 0)
        ok = kap < len(taus) - 6
        n_eval += int(ok.sum())
        _, a2 = diff2(Yp, 4, dt)
        tap = taus[kap]
        for i in np.nonzero(ok)[0]:
            seg = a2[kap[i] + 5:-5, i]
            if len(seg) == 0:
                continue
            k = int(np.nanargmax(seg))
            if seg[k] > out["physical"]["worst"]:
                out["physical"].update(worst=float(seg[k]), row=int(meta[i][0]), col=int(meta[i][1]), tau=float(taus[kap[i] + 5 + k]),
                                       apex_tau=float(tap[i]))
        for wn, W in warps.items():
            if W is None:
                continue
            tq = np.clip(W.tq, pk.knots[0], 0.0)
            Ys = pk.sub(tq, vidx, 0)[..., 1]
            s = 8
            A = np.full_like(Ys, np.nan)
            A[s:-s] = (Ys[2 * s:] - 2 * Ys[s:-s] + Ys[:-2 * s]) / (s / 240.0) ** 2
            o = out["screen"][wn]
            for i in np.nonzero(ok)[0]:
                mw = (tq >= tap[i] + 1.0 / 60) & (W.tg <= W.t_end - s / 240.0 - 1e-9) & np.isfinite(A[:, i]) & (tq >= pk.knots[0] + 0.05)
                if not mw.any():
                    continue
                k = int(np.nonzero(mw)[0][np.argmax(A[mw, i])])
                v = float(A[k, i])
                if v > 0.05:
                    o["n_fail"] += 1
                if v > 0.5:
                    o["n_fail_0p5"] += 1
                if v > o["worst"]:
                    o.update(worst=v, row=int(meta[i][0]), col=int(meta[i][1]), t=float(W.tg[k]), tau=float(tq[k]), apex_tau=float(tap[i]))
    out["vertices_with_apex"] = n_eval
    for o in [out["physical"]] + list(out["screen"].values()):
        for k in list(o.keys()):
            if isinstance(o[k], float):
                o[k] = r3(o[k])
    return out


def post_release(pk, ks, genlog):
    """唇先の放出（＋補間）の後の上下の加速度（物理の時刻、h = 1/60 s）。行は生成器の記録の lip_launch の行。"""
    L = ((genlog or {}).get("result") or {}).get("lip_launch") or {}
    out = {}
    dt = 1.0 / HZ
    for r, ent in L.items():
        r = int(r)
        if ks.tip_col[r] < 0:
            continue
        t0 = float(ent["release_tau"]) + float(ent["ramp_s"])
        K = int(math.floor(-max(t0 - 0.1, -4.0) * HZ + 1e-6))
        taus = np.round(-np.arange(K, -1, -1) * dt, 9)      # 1/240 s の格子（t* = 0 を含む）
        y = pk.sub(taus, np.array([r * ks.nu + int(ks.tip_col[r])]), 0)[:, 0, 1]
        _, a2 = diff2(y, 4, dt)
        m = (taus >= t0 + 1.0 / 60) & np.isfinite(a2)
        if m.sum() < 3:
            out[str(r)] = dict(release_tau=r3(ent["release_tau"]), ramp_s=r3(ent["ramp_s"]), note="補間の後が短すぎる")
            continue
        out[str(r)] = dict(release_tau=r3(ent["release_tau"]), ramp_s=r3(ent["ramp_s"]), acc_mean_mps2=r3(float(np.mean(a2[m]))),
                           acc_min_mps2=r3(float(np.min(a2[m]))), acc_max_mps2=r3(float(np.max(a2[m]))),
                           acc_p5_p95_mps2=[r3(float(np.percentile(a2[m], 5))), r3(float(np.percentile(a2[m], 95)))])
    return out


def sections(pk, ks, taus):
    out = []
    for tv in taus:
        Xl = pk.local(float(tv)) + ks.O
        A, Y, _ = ks.section(Xl)
        rm = DG.row_metrics(A[[159]], Y[[159]], ks.crest_hi[[159]], ks.j_E)
        out.append((float(tv), A[159].copy(), Y[159].copy(), A[192].copy(), Y[192].copy(), float(rm["ca"][0])))
    return out


# ---------------------------------------------------------------- 図
def draw_fig(res, out_png, warp_key="default", warp_label="各版の既定の時間曲線"):
    W = 2300
    f18, f20, f24, f30 = font(18), font(20), font(24), font(30)
    tags = [t for t in ("V80", "C1", "C2") if t in res]
    ph = 300
    x0, x1 = 190, W - 60
    t0, t1 = 5.0, 12.4
    tau0, tau1 = -3.6, 0.0
    panels = [("main", "H", "t"), ("main", "h", "t"), ("main", "h", "tau"), ("peak", "H", "t"), ("peak", "h", "t")]
    sec_h = 270
    Hh = 140 + len(panels) * ph + 90 + len(tags) * (sec_h + 40) + 140
    img = Image.new("RGB", (W, Hh), "white")
    d = ImageDraw.Draw(img)
    d.text((40, 14), "設計28修正01 試行C（Q15）：唇先の頂に対する高さ h（巻き下がり）と頂の高さ H — 画面の時刻 t（%s）" % warp_label, font=f30, fill=(0, 0, 0))
    d.text((40, 60), "○ 見える始まり τ_vis　□ 見える最高点 τ −2.1　△ 唇先の頂点　× 唇先の放出（自由な飛行の始まり）　| 下の目盛り：0.5 倍に着く時刻（各版の既定）"
           "　灰の帯：t ≥ 10 s", font=f20, fill=(0, 0, 0))
    d.text((40, 90), "V80＝青、C1＝緑、C2＝橙。h は K* の唇先の列の高さ − 行の断面の頂の高さ（t* で主断面 −8.47 m）。3 段目は物理の時刻 τ（3 版で頂の上昇は同じ）",
           font=f20, fill=(0, 0, 0))
    y = 130
    for key, qty, ax in panels:
        ya, yb = y + 10, y + ph - 34
        if qty == "H":
            v0, v1 = 12.0, 23.5
            ticks = [12, 14, 16, 18, 20, 22]
        else:
            v0, v1 = -10.5, 0.5
            ticks = [0, -2, -4, -6, -8, -10]
        lo, hi = (t0, t1) if ax == "t" else (tau0, tau1)

        def X(v):
            return x0 + (v - lo) / (hi - lo) * (x1 - x0)

        def Yv(v):
            return yb - (min(max(v, v0), v1) - v0) / (v1 - v0) * (yb - ya)
        if ax == "t":
            d.rectangle([X(10.0), ya, X(12.4), yb], fill=(238, 238, 238))
        d.rectangle([x0, ya, x1, yb], outline=(0, 0, 0))
        step = 0.5
        for tt in np.arange(math.ceil(lo / step) * step, hi + 1e-9, step):
            d.line([(X(tt), ya), (X(tt), yb)], fill=(225, 225, 225))
            d.text((X(tt) - 16, yb + 4), "%.1f" % tt, font=f18, fill=(0, 0, 0))
        for v in ticks:
            d.line([(x0, Yv(v)), (x1, Yv(v))], fill=(215, 215, 215))
            d.text((x0 - 50, Yv(v) - 10), "%g" % v, font=f18, fill=(0, 0, 0))
        rowname = "主断面（行 159）" if key == "main" else "峰の行（行 192）"
        lab = {"H": "頂の高さ H [m]", "h": "唇先 − 頂 h [m]"}[qty]
        d.text((x0 + 8, ya + 4), "%s — %s — 横軸 %s" % (rowname, lab, "画面の時刻 t [s]" if ax == "t" else "物理の時刻 τ [s]"), font=f24, fill=(0, 0, 0))
        for tag in tags:
            R = res[tag]
            S = R["_series"]
            j = list(ROWS.values()).index(ROWS[key])
            taus = S["taus"]
            v = S["H"][:, j] if qty == "H" else S["tip_y"][:, j] - S["H"][:, j]
            Wp = R["_warps"][warp_key]
            if ax == "t":
                xs = np.array([Wp.t_of(float(tv)) if tv >= Wp.tauu[0] else np.nan for tv in taus])
            else:
                xs = taus
            mk = np.isfinite(xs) & (xs >= lo) & (xs <= hi)
            pts = [(X(a), Yv(b)) for a, b in zip(xs[mk], v[mk])]
            if len(pts) > 1:
                d.line(pts, fill=COL[tag], width=5 if qty == "h" else 3)
            e = R["rows"][key]
            marks = [("o", e["visible"]["tau"] if e.get("visible") else None), ("s", TAU_TOP), ("t", e["tip_apex_tau"]),
                     ("x", (R.get("tip_release") or {}).get(key))]
            for kind, tv in marks:
                if tv is None:
                    continue
                xv = Wp.t_of(tv) if ax == "t" else tv
                if xv is None or not (lo <= xv <= hi):
                    continue
                yv = float(np.interp(tv, taus, v))
                cx, cy = X(xv), Yv(yv)
                if kind == "o":
                    d.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], outline=COL[tag], width=4)
                elif kind == "s":
                    d.rectangle([cx - 9, cy - 9, cx + 9, cy + 9], outline=COL[tag], width=4)
                elif kind == "t":
                    d.polygon([(cx, cy - 12), (cx - 10, cy + 8), (cx + 10, cy + 8)], outline=COL[tag])
                    d.polygon([(cx, cy - 10), (cx - 8, cy + 6), (cx + 8, cy + 6)], outline=COL[tag])
                else:
                    d.line([(cx - 10, cy - 10), (cx + 10, cy + 10)], fill=COL[tag], width=4)
                    d.line([(cx - 10, cy + 10), (cx + 10, cy - 10)], fill=COL[tag], width=4)
            if ax == "t":
                sr = Wp.params.get("slow_reached_t")
                if sr is not None and lo <= sr <= hi:
                    d.line([(X(sr), yb - 16), (X(sr), yb)], fill=COL[tag], width=5)
        y += ph
    # 凡例
    lx = x0
    for tag in tags:
        d.line([(lx, y + 14), (lx + 50, y + 14)], fill=COL[tag], width=5)
        d.text((lx + 58, y), LABEL[tag], font=f24, fill=(0, 0, 0))
        lx += 330
    y += 60
    # 断面の帯
    d.text((40, y), "主断面の断面（同じ物理の時刻 τ＝同じ頂の高さで並べる。薄い青＝V80 を重ねたもの、点＝唇先。尺度は縦横同じ。各こまの t は上と同じ時間曲線の画面の時刻）",
           font=f20, fill=(0, 0, 0))
    y += 34
    for tag in tags:
        R = res[tag]
        sl = R["_secs"]
        d.text((30, y + 4), LABEL[tag], font=f24, fill=COL[tag])
        cw = (W - 200) / max(len(sl), 1)
        tc = int(R["_tipcol"][159])
        for i, (tv, A, Y, Ap, Yp, ac) in enumerate(sl):
            ox = 200 + i * cw + cw * 0.5
            oy = y + sec_h - 20
            sc = 7.0
            if tag != "V80" and "V80" in res:
                sv = res["V80"]["_secs"][i]
                A8, Y8 = sv[1], sv[2]
                # 同じ波の枠（局所の座標）なので、V80 もこの版の頂の a で並べる（頂の動きは 3 版で同じ）
                p8 = [(ox + (a - ac) * sc, oy - yy * sc) for a, yy in zip(A8, Y8) if -24 < a - ac < 20]
                if len(p8) > 1:
                    d.line(p8, fill=(160, 190, 240), width=2)
            pts = [(ox + (a - ac) * sc, oy - yy * sc) for a, yy in zip(A, Y) if -24 < a - ac < 20]
            d.line([(ox - 24 * sc, oy), (ox + 20 * sc, oy)], fill=(200, 200, 200))
            if len(pts) > 1:
                d.line(pts, fill=(0, 0, 0), width=2)
            cx, cy = ox + (A[tc] - ac) * sc, oy - Y[tc] * sc
            d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=COL[tag])
            Wp = R["_warps"][warp_key]
            ts = Wp.t_of(tv)
            hv = float(Y[tc] - np.max(np.where(np.arange(len(Y)) <= R["_crest_hi"][159], Y, -1e9)))
            d.text((ox - 21 * sc, y + 4), "τ %.2f  t %s  h %.1f m" % (tv, "%.2f" % ts if ts is not None else "—", hv), font=f18, fill=(0, 0, 0))
        y += sec_h + 40
    d.text((40, y), "τ_vis は各版の主断面の見える始まり（V80 と C1・C2 はほぼ同じ）。h の数字は断面の読み（唇先の列の高さ − 列 jt までの最高点）", font=f18, fill=(0, 0, 0))
    img = img.crop((0, 0, W, y + 40))
    img.save(out_png, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", default="V80,C1,C2")
    ap.add_argument("--root", default=os.path.join("Unity", "Build", "Design", "28R01C"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-lip", action="store_true")
    a = ap.parse_args()
    root = a.root if os.path.isabs(a.root) else os.path.join(REPO, a.root)
    outd = a.out or os.path.join(root, "review")
    outd = outd if os.path.isabs(outd) else os.path.join(REPO, outd)
    os.makedirs(outd, exist_ok=True)
    ks = DG.KStar()
    cond, _ = DG.load_conditions()
    on = lip_on(ks, cond)
    rows = list(ROWS.values())
    res = {}
    for tag in a.tags.split(","):
        P = paths(tag, root)
        if not os.path.isfile(os.path.join(P["pkg"], "ds27_keypose.json")):
            print("skip", tag, flush=True)
            continue
        pk = DG.Package(P["pkg"], ks)
        warps = {k: (Warp(p) if os.path.isfile(p) else None) for k, p in P["warps"].items()}
        S = RB.series(pk, ks, rows, t0=-4.6)
        e = dict(package=rel(P["pkg"]), pos_sha256=pk.pos_sha, warps={k: (rel(W.path) if W else None) for k, W in warps.items()},
                 warp_params={k: ({kk: W.params.get(kk) for kk in ("t1", "r0", "slow_reached_tau", "slow_reached_t", "tau_at_t0_default", "earliest_apex_row")}
                                  if W else None) for k, W in warps.items()}, rows={})
        for key, r in ROWS.items():
            j = rows.index(r)
            e["rows"][key], _ = row_curl(S, j, float(on[r]), warps)
        GL = jload(P["genlog"])
        LL = ((GL or {}).get("result") or {}).get("lip_launch") or {}
        e["tip_release"] = {k: (float(LL[str(r)]["release_tau"]) if str(r) in LL else None) for k, r in ROWS.items()}
        e["launch"] = {k: LL.get(str(r)) for k, r in ROWS.items()}
        e["post_release_tip_accel"] = post_release(pk, ks, GL)
        if not a.no_lip:
            e["lip_braking"] = lip_braking(pk, ks, warps)
        e["_series"] = S
        e["_warps"] = warps
        tvis = e["rows"]["main"]["visible"]["tau"] if e["rows"]["main"].get("visible") else -2.7
        e["_secs"] = sections(pk, ks, [tvis if x == "vis" else x for x in SEC_TAUS])
        e["_tipcol"] = ks.tip_col
        e["_crest_hi"] = ks.crest_hi
        res[tag] = e
        print("done", tag, flush=True)
    draw_fig(res, os.path.join(outd, "fig_ds28r01c_curl.png"), "default")
    if all(t in res for t in ("C1", "C2")):
        draw_fig(res, os.path.join(outd, "fig_ds28r01c_curl_v80warp.png"), "v80", "3 版とも V80 の既定の表（比べ）")
    for tag in res:
        for k in [k for k in res[tag] if k.startswith("_")]:
            res[tag].pop(k)
    res["_definitions_ja"] = __doc__
    with open(os.path.join(outd, "curl_ds28r01c.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=lambda o: r3(o) if isinstance(o, (np.floating, float)) else (int(o) if isinstance(o, np.integer) else str(o)))
    print(os.path.join(outd, "curl_ds28r01c.json"))


if __name__ == "__main__":
    main()
