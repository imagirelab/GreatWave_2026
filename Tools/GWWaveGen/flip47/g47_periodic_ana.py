# -*- coding: utf-8 -*-
"""FLIP47：周期の波の計算（g47_pcfg.py の cfg、流れ関数の入口）を読む（py -3.10 -B。numpy・scipy・scikit-image・PIL）。
2026-10-13 周期の波の実験の役（Claude）が書いた。物差しは前の道具をそのまま読み込んで使う（変えない）：
  崩れの見つけ方と k の番号：g47_video.Run.events（前の面の弦が 90° 以上になった最初のコマ。着水の後の跳ね上がりの巻きは数えない）
  崩れごとの量：g47_analyze.analyze（巻き始め・着水・噴流と巻き・STUDY52 measure_mask）を、その崩れの窓（コマと x）に絞って走らせ、
                g47_scan.summarize（score3 の最小のコマ・着水のコマ・論文の量）で同じ表にする。板の層ごとは g47_scan.patch_rec。
  後ろの角・0.7 η_c の幅：s52 の back_angle_07_09_deg・width07_silhouette（score3 の最小のコマと着水のコマ）。score_back は同じ式
                （帯の外れ ÷ 原画 cn、1 で頭打ち）を 2 つの量に当てた物（periodic_design_ja.md §6.2）。
入口（periodic_design_ja.md §6.1）：一番上の水面（hf、4 層の平均、静かな水面のずれを引く）を x 450・480・510・540・560 m で読み、
  0 を下に切る所で波を分け、波ごとに H・頂・谷・頂の時刻。目標（流れ関数の解、帯の出口 x_p で t = 0 に頂）と比べる：波高・頂（±5 %）、
  速さ（450 → 560 m の頂の時刻、±2 %）、波高の CV（510 m、≤ 3 %）、位相（目標の頂の時刻からのずれ）。跳ね返り Kr（Goda & Suzuki 1976 の
  2 点法、1 次の周波数、k は流れ関数の k）。平均の水面（x 440〜560 m）の流れ。帯の中の格子の流速と目標（run の info.sf_check）。
繰り返し（§6.3）：測る回（既定 k 5〜10）の η_c の CV、h_b の CV、x_b の標準偏差 ÷ L_b、巻き始めの位相のばらつき ÷ T、回を追った流れ。
使い方：
  py -3.10 -B g47_periodic_ana.py all <run_id か記録の置き場所> [--measure=5,10] [--layers=1] [--inlet_t=<t0>,<t1>] [--gauges=450,480,...]
       → <記録>/pana/periodic_ana.json と図（<記録>/pana/*.png）。図は runs/PERIODIC_compare/ にも写す
  py -3.10 -B g47_periodic_ana.py inlet <…> [--inlet_t=..] [--gauges=..] [--pairs=480:510,600:630]   入口と跳ね返りだけ
  py -3.10 -B g47_periodic_ana.py events <…>                                                        崩れの表だけ
  py -3.10 -B g47_periodic_ana.py table <…> ...                                                     回ごとの Markdown の表（periodic_ana.json から）
  all の --measure_ext=8,13：設計の延ばしの決まりの回（repeat_ext・checks.ext）。層ごとの読みは両方の回の範囲で
"""
import os, sys, json, math, glob, time, shutil, copy
sys.dont_write_bytecode = True
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import g47_common as GC          # noqa: E402
import g47_analyze as GA         # noqa: E402  読むだけ
import g47_video as GV           # noqa: E402  読むだけ（崩れの見つけ方）
import g47_scan as GS            # noqa: E402  読むだけ（summarize・patch_rec）
import g47_sfwave as SF          # noqa: E402

B47 = GC.B47
CMP = B47 + "/runs/PERIODIC_compare"
G = GC.G
FONT, FONTB = GA.FONT, GA.FONTB
_F = {}


def font(sz, b=False):
    k = (int(sz), bool(b))
    if k not in _F:
        _F[k] = ImageFont.truetype(FONTB if b else FONT, int(sz))
    return _F[k]


def clean(o):
    return GA.clean(o)


def jdump(o, p):
    json.dump(clean(o), open(p, "w", encoding="utf8"), ensure_ascii=False, indent=1)


def guard(p):
    a = os.path.abspath(p).replace("\\", "/")
    if not a.lower().startswith(os.path.abspath(B47).replace("\\", "/").lower()):
        raise SystemExit("書く所は Unity/Build/FLIP47 の中だけ：%s" % a)
    return a


# ====================================================================== 記録
def resolve(ref):
    return GV.resolve_run(ref)


def load_hf(rd):
    """hf_c*.npz をつなぐ（同じコマは後の起動の物）。返り値 frames, t, x, z, eta[コマ, 層, x]（計画の座標・静かな水面のずれは引かない）。"""
    ps = sorted(glob.glob(os.path.join(rd, "hf_c*.npz")), key=lambda p: int(os.path.basename(p)[4:8]))
    best = {}
    X = Z = None
    arrs = {}
    for p in ps:
        d = np.load(p)
        f0 = int(os.path.basename(p)[4:8])
        X = d["x"]; Z = d["z"]
        arrs[p] = (d["eta"], d["t"])
        for i, f in enumerate(d["frames"]):
            f = int(f)
            if f >= f0 and (f not in best or best[f][0] <= f0):
                best[f] = (f0, p, i)
    fr = sorted(best)
    eta = np.empty((len(fr), len(Z), len(X)), np.float32)
    t = np.empty(len(fr))
    for j, f in enumerate(fr):
        _, p, i = best[f]
        eta[j] = arrs[p][0][i]; t[j] = arrs[p][1][i]
    return np.array(fr), t, np.asarray(X, float), np.asarray(Z, float), eta


def run_records(rd):
    out = []
    for p in sorted(glob.glob(os.path.join(rd, "run_c*.json")), key=lambda q: int(os.path.basename(q)[5:9])):
        try:
            out.append(json.load(open(p, encoding="utf8")))
        except Exception:
            pass
    return out


def sf_of(cfg):
    sf = cfg.get("sf")
    if not sf:
        return None
    s = dict(sf); s["E"] = np.asarray(sf["E"], float); s["B"] = np.asarray(sf["B"], float)
    s.setdefault("L", 2 * math.pi / float(sf["k"]))
    return s


# ====================================================================== 入口
_DSF = {}


def design_sf(cfg):
    """cfg の sf に H_design（解き直す前の設計の波高）があれば、その波（同じ h・T・N）を解いて返す。なければ None。"""
    sf = cfg.get("sf") or {}
    if sf.get("H_design") is None:
        return None
    key = (float(sf["h"]), float(sf["T"]), float(sf["H_design"]), int(sf.get("N", 40)))
    if key not in _DSF:
        sv = SF.solve(key[0], key[1], key[2], N=key[3])
        sv["E"] = np.asarray(sv["E"]); sv["B"] = np.asarray(sv["B"])
        _DSF[key] = sv
    return _DSF[key]


def at_x(eta_l, X, xg):
    """eta_l[コマ, x]（層の平均）を x = xg で線形に補う。"""
    i = int(np.clip(np.searchsorted(X, xg) - 1, 0, len(X) - 2))
    w = (xg - X[i]) / (X[i + 1] - X[i])
    return (1 - w) * eta_l[:, i] + w * eta_l[:, i + 1]


def waves_zero_down(t, e, mean=None):
    """0 を下に切る所で分けた波（平均の水面からの 0）。返り値：波ごとの dict（t_crest・crest・trough・H・t_down0・t_down1）。"""
    m = float(np.nanmean(e)) if mean is None else float(mean)
    q = e - m
    ok = np.isfinite(q)
    dn = np.where(ok[:-1] & ok[1:] & (q[:-1] >= 0) & (q[1:] < 0))[0]
    tz = [t[i] + (t[i + 1] - t[i]) * q[i] / (q[i] - q[i + 1]) for i in dn]
    out = []
    for a, b, ta, tb in zip(dn[:-1], dn[1:], tz[:-1], tz[1:]):
        seg = slice(a + 1, b + 1)
        ee = e[seg]; tt = t[seg]
        if len(ee) < 5 or not np.isfinite(ee).all():
            continue
        ic = int(np.argmax(ee)); it = int(np.argmin(ee))
        tc, ec = tt[ic], ee[ic]
        if 0 < ic < len(ee) - 1:          # 放物線で頂の時刻と高さを詰める
            y0, y1, y2 = ee[ic - 1], ee[ic], ee[ic + 1]
            den = y0 - 2 * y1 + y2
            if den < 0:
                d = 0.5 * (y0 - y2) / den
                tc = tt[ic] + d * (tt[1] - tt[0]); ec = y1 - 0.25 * (y0 - y2) * d
        out.append(dict(t_down0=ta, t_down1=tb, T=tb - ta, t_crest=float(tc), crest=float(ec), trough=float(ee[it]), H=float(ec - ee[it]),
                        t_trough=float(tt[it])))
    return out, m


def inlet(rd, cfg, hf, off, t_win=None, gauges=(450.0, 480.0, 510.0, 540.0, 560.0), pairs=((480.0, 510.0),)):
    fr, t, X, Z, eta = hf
    s_in = sf_of(cfg)
    s = design_sf(cfg) or s_in                             # 比べる目標：入口で解き直した時は設計の波（H_design）
    el = np.nanmean(eta, axis=1) - off                     # 4 層の平均、静かな水面から
    P = cfg["parms"]
    xp = float(P["x_p"]); T = float(s["T"]); c = float(s["c"])
    pm = SF.profile_measures(s)
    tgt = dict(H=float(s["H"]), eta_c=float(pm["eta_c"]), eta_t=float(pm["eta_t"]), c=c, T=T, L=float(s["L"]), k=float(s["k"]),
               a1=float(s["E"][1]), note_ja="流れ関数の解（平均の水面から）。頂は帯の出口 x_p %.0f m で t = 0、x = x_p + c t + n L" % xp,
               input_H=float(s_in["H"]), input_c=float(s_in["c"]), input_eta_c=float(SF.profile_measures(s_in)["eta_c"]),
               compared_to=("設計の波 H %g m（入口は H %g m に解き直した）" % (float(s["H"]), float(s_in["H"])) if s is not s_in else "入口の波そのもの"))
    if t_win is None:
        t_win = [max(2.0 * float(P.get("ramp_s", 0.0)) + 10.0, 40.0), float(t[-1])]
    m = (t >= t_win[0]) & (t <= t_win[1])
    out = dict(target=tgt, window_s=[float(v) for v in t_win], gauges=[], still_offset_m=off)
    ser = {}
    for xg in gauges:
        e = at_x(el, X, xg)
        ser[xg] = e
        wv, mean = waves_zero_down(t[m], e[m])
        wv = [w for w in wv if w["H"] > 0.3 * tgt["H"]]
        if not wv:
            out["gauges"].append(dict(x=xg, n=0)); continue
        H = np.array([w["H"] for w in wv]); cr = np.array([w["crest"] for w in wv]); tr = np.array([w["trough"] for w in wv])
        tc = np.array([w["t_crest"] for w in wv])
        t_ref = (xg - xp) / c
        dt = (tc - t_ref + 0.5 * T) % T - 0.5 * T             # 目標の頂の時刻からのずれ（−T/2〜T/2）
        Tw = np.array([w["T"] for w in wv])
        out["gauges"].append(dict(
            x=xg, n=len(wv), H_mean=float(H.mean()), H_cv=float(H.std() / H.mean()), H_rel=float(H.mean() / tgt["H"] - 1),
            crest_mean=float(cr.mean()), crest_rel=float(cr.mean() / tgt["eta_c"] - 1), trough_mean=float(tr.mean()),
            crest_from_local_mean=float((cr - mean).mean()), local_mean=float(mean),
            phase_dt_mean_s=float(dt.mean()), phase_dt_std_s=float(dt.std()), phase_rad_mean=float(2 * math.pi * dt.mean() / T),
            period_mean=float(Tw.mean()), period_std=float(Tw.std()),
            waves=[dict(w, dt_phase_s=float(d)) for w, d in zip(wv, dt)]))
    # 速さ：最初と最後の計り所の頂を同じ波でつなぐ
    g0, g1 = out["gauges"][0], out["gauges"][-1]
    sp = []
    if g0.get("n") and g1.get("n"):
        lag0 = (g1["x"] - g0["x"]) / c
        t1s = np.array([w["t_crest"] for w in g1["waves"]])
        for w in g0["waves"]:
            j = np.argmin(np.abs(t1s - (w["t_crest"] + lag0)))
            lag = t1s[j] - w["t_crest"]
            if 0.6 * lag0 < lag < 1.4 * lag0:
                sp.append((g1["x"] - g0["x"]) / lag)
    out["speed"] = dict(x=[g0["x"], g1["x"]], n=len(sp), c_mean=(float(np.mean(sp)) if sp else None),
                        c_rel=(float(np.mean(sp) / c - 1) if sp else None), c_std=(float(np.std(sp)) if sp else None))
    # 跳ね返り（2 点法、1 次の周波数。整数の周期の窓）
    refl = []
    om = 2 * math.pi / T; kk = float(s["k"])
    nper = int((t_win[1] - t_win[0]) // T)
    if nper >= 2:
        tw0 = t_win[1] - nper * T
        mm = (t >= tw0) & (t < t_win[1])
        for (xa, xb) in pairs:
            ea = at_x(el, X, xa)[mm]; eb = at_x(el, X, xb)[mm]; tt = t[mm]
            if not (np.isfinite(ea).all() and np.isfinite(eb).all()):
                continue
            Ba = 2 * np.mean((ea - ea.mean()) * np.exp(-1j * om * tt)); Bb = 2 * np.mean((eb - eb.mean()) * np.exp(-1j * om * tt))
            # η = Re(B e^{iωt})：入る波 a_I cos(ωt − kx + ε) → I e^{−ikx}、戻る波 → R e^{ikx}
            A = np.array([[np.exp(-1j * kk * xa), np.exp(1j * kk * xa)], [np.exp(-1j * kk * xb), np.exp(1j * kk * xb)]])
            I, R = np.linalg.solve(A, np.array([Ba, Bb]))
            refl.append(dict(x=[xa, xb], dx_over_L=(xb - xa) / tgt["L"], periods=nper, window_s=[float(tw0), float(t_win[1])],
                             a_incident=float(abs(I)), a_reflected=float(abs(R)), Kr=float(abs(R) / abs(I)),
                             a1_target=tgt["a1"], a_incident_rel=float(abs(I) / tgt["a1"] - 1)))
    out["reflection"] = dict(method_ja="Goda & Suzuki 1976 の 2 点法を 1 次の周波数（1/T）だけで。k は流れ関数の解の k（1 次の成分は波と同じ速さ）。"
                                       "非線形の波なので目安", pairs=refl)
    # 平均の水面（x 440〜560）
    sel = (X >= 440.0) & (X <= 560.0)
    ml = np.nanmean(el[:, sel], axis=1)
    nT = max(1, int(round(T * GC.FPS)))
    run_mean = np.convolve(ml, np.ones(nT) / nT, mode="same")
    mw = m & np.isfinite(run_mean)
    out["mean_level"] = dict(x=[440.0, 560.0], every_s=[[float(t[i]), float(ml[i]), float(run_mean[i])] for i in range(0, len(t), 24)],
                             window_mean=float(np.nanmean(ml[m])) if m.any() else None,
                             drift_in_window=(float(run_mean[mw][-nT] - run_mean[mw][nT]) if mw.sum() > 3 * nT else None),
                             note_ja="1 周期の動く平均。drift は窓の始めの 1 周期の後と終わりの 1 周期の前の差")
    # 帯の中の格子の流速と目標（sf_check）
    rows = [r for rr in run_records(rd) for ck in (rr.get("info") or {}).get("sf_check", []) for r in
            [dict(row, frame=ck["frame"], t=ck["t"]) for row in ck["rows"]]]
    if rows:
        def st(sel_rows, key_m, key_t):
            d = np.array([r[key_m] - r[key_t] for r in sel_rows if r.get(key_m) is not None])
            return dict(n=int(len(d)), mean=float(d.mean()) if len(d) else None, rms=float(np.sqrt((d ** 2).mean())) if len(d) else None,
                        absmax=float(np.abs(d).max()) if len(d) else None)
        chk = {}
        for x in sorted(set(r["x"] for r in rows)):
            rx = [r for r in rows if r["x"] == x and r["t"] >= t_win[0]]
            chk[str(x)] = dict(relax_w_per_dt0=rx[0]["relax_w_per_dt0"] if rx else None, u=st(rx, "u_grid", "u_t"), w=st(rx, "w_grid", "w_t"),
                               u_target_rms=float(np.sqrt(np.mean([r["u_t"] ** 2 for r in rx]))) if rx else None)
        out["band_check"] = dict(rule_ja="帯の中の点で、格子の流速（板の真ん中）− 帯の目標（流れ関数 × なだらかさ × 包絡）。窓の中のコマ。単位 m/s",
                                 by_x=chk, c=c)
    # 合否（§6.1）
    gm = {g["x"]: g for g in out["gauges"] if g.get("n")}
    Hrel = [g["H_rel"] for g in gm.values()]; crel = [g["crest_rel"] for g in gm.values()]
    g510 = gm.get(510.0)
    out["pass"] = dict(H=bool(Hrel and max(abs(v) for v in Hrel) <= 0.05), crest=bool(crel and max(abs(v) for v in crel) <= 0.05),
                       c=bool(out["speed"]["c_rel"] is not None and abs(out["speed"]["c_rel"]) <= 0.02),
                       H_cv_510=bool(g510 and g510["H_cv"] <= 0.03),
                       bands_ja="波高・頂 ±5 %（5 つの計り所のすべて）、速さ ±2 %、x 510 m の波高の CV ≤ 3 %（periodic_design_ja.md §6.1）")
    out["pass"]["all"] = bool(all(out["pass"][k] for k in ("H", "crest", "c", "H_cv_510")))
    return out, ser, el, t


# ====================================================================== 崩れ
def back_bands():
    pr = GV.print_ref()
    cn = pr["cnv"]
    return dict(back_angle_07_09_deg=dict(center=cn["back_angle_07_09_deg"], band=pr["extra"]["back_angle_07_09_deg"]),
                width07_silhouette=dict(center=cn["width07_silhouette"], band=pr["extra"]["width07_silhouette"]))


def score_back(m):
    if not m:
        return None
    bb = back_bands(); tot = 0.0
    for k, b in bb.items():
        v = m.get(k)
        if v is None or not np.isfinite(v):
            return None
        lo, hi = b["band"]; d = 0.0
        if v < lo:
            d = (lo - v) / b["center"]
        if v > hi:
            d = (v - hi) / b["center"]
        tot += min(d, 1.0)
    return round(tot, 3)


PRIMARY_X = 570.0      # 斜面の足。頂の筋がこれより沖で生まれた崩れを「来た波の崩れ」とする


def find_events(rd, layer="sdf", primary_x=PRIMARY_X, T=None, bed=None, min_depth=5.0, min_frac=0.5, gap_frac=0.6):
    """g47_video.Run.events の崩れ（k_all）から、来た波の崩れを選び k = 1, 2, … を振る（2026-10-13 SM2b・SM2d・SM2e の記録で決めた）。
    来た波の崩れの候補：(a) 頂の筋が斜面の足 primary_x より沖で生まれた崩れ、または (b) 巻き始めの所の静かな水深が min_depth 以上で、
    頂が (a) の頂の中央値の min_frac 倍以上の崩れ（粗い記録で頂の筋が崩れの直前に切れて、浅い所で生まれ直した物を拾う）。
    (a) は全部採る。(b) は、採った崩れのどれとも巻き始めが gap_frac × T 以上離れている時だけ採る（同じ波の巻き直しを落とす）。ほかは secondary。"""
    run = GV.Run(rd, layer, log=lambda *a: None)
    evs = run.events()
    if T is None or bed is None:
        try:
            c_ = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
            T = T or float((c_.get("sf") or {}).get("T", 14.0)); bed = bed or c_.get("bed")
        except Exception:
            T = T or 14.0
    allr = []
    for e in evs:
        d = dict(k_all=e["k"], on_f=int(e["on_f"]), on_t=float(e["on_t"]), on_x=float(e["on_x"]), on_eta=float(e["on_eta"]),
                 td_f=e.get("td_f"), td_t=e.get("td_t"), td_src=e.get("td_src"), track_start_t=float(e["track"]["t"][0]),
                 track_start_x=float(e["track"]["x"][0]))
        d["depth_on"] = float(-GC.bed_y(d["on_x"], bed)) if bed else None
        allr.append(d)
    off = [d for d in allr if d["track_start_x"] < primary_x]
    med = float(np.median([d["on_eta"] for d in off])) if off else 0.0
    out, sec = [], []
    for d in allr:                                   # (a) は全部採る（沖で生まれた頂の筋は別々の波）
        if d["track_start_x"] < primary_x:
            d["why"] = "offshore_track"; out.append(d)
    for d in sorted(allr, key=lambda q: q["on_t"]):  # (b) は採った崩れのどれとも 0.6 T 以上離れている時だけ
        if d in out:
            continue
        cand = d["depth_on"] is not None and d["depth_on"] >= min_depth and d["on_eta"] >= min_frac * med
        if cand and all(abs(d["on_t"] - q["on_t"]) >= gap_frac * T for q in out):
            d["why"] = "depth>=%.0fm_and_eta>=%.1f*median" % (min_depth, min_frac); out.append(d)
        else:
            d["why"] = "near_accepted" if cand else "shallow_or_small"
            sec.append(d)
    out.sort(key=lambda q: q["on_t"])
    for i, d in enumerate(out):
        d["k"] = i + 1
    after = [dict(first_f=v["first_f"], first_t=v["first_t"], first_x=v["first_x"], first_eta=v["first_eta"]) for v in run.after_evs]
    return out, after, run, sec


def analyze_event(rd, ev, zsel=None, pre_f=30, post_f=120):
    """1 回の崩れを g47_analyze.analyze で（コマと x の窓を絞って）。zsel：None＝主の層（sdf, iz 1）、'mean'、0〜3。"""
    GS.patch_rec(GA, zsel)
    try:
        opt = dict(f0=max(1, ev["on_f"] - pre_f), f1=ev["on_f"] + post_f, xwin="%g,%g" % (ev["on_x"] - 45.0, ev["on_x"] + 60.0), nofig=True)
        cx = GA.Ctx(rd, opt)
        res, masks = GA.analyze(cx, opt)
        res["zsel"] = zsel if zsel is not None else "sdf (iz 1)"
        TG, bands = GS._bands()
        summ, byf = GS.summarize(res, TG, bands)
        extra = {}
        for nm in ("best3", "touchdown"):
            d = summ.get(nm)
            if d:
                M, X, Z = GA.fine_mask(cx, d["frame"], d["xc"], S=cx.sdf(d["frame"]))
                m52, _e = GA.s52_measure(M, X, Z)
                if m52:
                    ex = {k: GA.fnum(m52.get(k)) for k in ("back_angle_07_09_deg", "width07_silhouette", "eta_c", "x_c", "gap_max", "lip_thick_mid",
                                                          "face_chord_deg_01_05", "front_x01_rel", "hood_area", "tip_z", "reach")}
                    ex["score_back"] = score_back(ex)
                    ex["lines"] = [l[::4].round(4).tolist() for l in GA.mask_lines(M, X, Z, float(m52["x_c"]), float(m52["eta_c"]))]
                    extra[nm] = ex
        return dict(res=res, summ=summ, extra=extra, cx=cx)
    finally:
        GS.patch_rec(GA, None)


def front_trough(cx, f, xc, span=80.0):
    top = GA.top_surface(cx.sdf(f), cx.ys)
    m = (cx.xs >= xc) & (cx.xs <= xc + span)
    if not np.isfinite(top[m]).any():
        return None, None
    i = int(np.nanargmin(np.where(m, top, np.nan)))
    return float(top[i]), float(cx.xs[i])


def event_row(rd, cfg, ev, A, el_hf, t_hf, X_hf, T):
    s = A["summ"]; res = A["res"]; cx = A["cx"]
    on = res.get("onset") or {}
    row = dict(k=ev["k"], k_all=ev.get("k_all"), found=dict(on_f=ev["on_f"], on_t=ev["on_t"], on_x=ev["on_x"], td_f=ev.get("td_f"), td_src=ev.get("td_src"),
                                                          track_start_x=ev.get("track_start_x")))
    if not on:
        row["note_ja"] = "窓の中で g47_analyze が巻き始めを読めなかった"
        return row
    f_on = int(on["frame"]); xb = float(on["xc"]); eb = float(on["Hb_onset_m"])
    hb = float(-GC.bed_y(xb, cfg["bed"]))
    kb = SF.k_lin(T, hb)
    tr, xtr = front_trough(cx, f_on, xb)
    t_on = float(on["t"])
    mloc = None
    ip = (t_hf >= t_on - T) & (t_hf <= t_on)
    if ip.sum() > 5:
        mloc = float(np.nanmean(at_x(el_hf, X_hf, xb)[ip]))
    row.update(on_frame=f_on, t_onset=t_on, x_b=xb, eta_c_onset=eb, h_b=hb, L_b=2 * math.pi / kb, eta_c_over_h_b=eb / hb,
               front_trough=tr, front_trough_x=xtr, H_onset=(eb - tr if tr is not None else None), local_mwl=mloc,
               eta_c_onset_from_local_mwl=(eb - mloc if mloc is not None else None),
               eta_max_before_onset=res.get("eta_max_before_onset"))
    td = res.get("touchdown") or {}
    row["touchdown"] = dict(frame=td.get("frame"), t=td.get("t"), by=td.get("by"), dt_after_onset=(td["t"] - t_on if td.get("t") else None))
    for nm in ("best3", "touchdown"):
        d = s.get(nm)
        if d:
            ex = A["extra"].get(nm) or {}
            row[nm] = dict(frame=d["frame"], t=d["t"], xc=d["xc"], eta=d["eta"], score3=d["score3"], score5=d.get("score5"), ruler=d["ruler"],
                           back_angle=ex.get("back_angle_07_09_deg"), width07=ex.get("width07_silhouette"), score_back=ex.get("score_back"),
                           lines=ex.get("lines"))
    pm = s.get("paper")
    if pm:
        row["paper"] = {k: pm.get(k) for k in ("Hb_m", "Hb_h0", "AJ_Hb2", "AO_Hb2", "W_L", "theta_o_deg", "jet_width_h0", "contact", "cavity_how")}
    row["closed_air"] = bool(pm and pm.get("AO_Hb2") and pm["AO_Hb2"] > 0)
    return row


# ====================================================================== 繰り返し・判定
def stats(rows, T):
    def arr(key, sub=None):
        v = []
        for r in rows:
            x = r.get(key) if sub is None else (r.get(key) or {}).get(sub)
            v.append(np.nan if x is None else float(x))
        return np.array(v)
    k = np.array([r["k"] for r in rows], float)
    ec = arr("eta_c_onset"); hb = arr("h_b"); xb = arr("x_b"); ton = arr("t_onset"); Lb = arr("L_b")
    out = dict(n=len(rows), k=[int(v) for v in k])

    def cv(a):
        a = a[np.isfinite(a)]
        return float(a.std() / a.mean()) if len(a) >= 2 and a.mean() != 0 else None

    def drift(a):
        ok = np.isfinite(a)
        if ok.sum() < 3:
            return None
        p = np.polyfit(k[ok], a[ok], 1)
        return float(p[0] * (k[ok].max() - k[ok].min()))
    ph = ton - k * T
    out.update(eta_c_mean=float(np.nanmean(ec)), eta_c_cv=cv(ec), h_b_mean=float(np.nanmean(hb)), h_b_cv=cv(hb), x_b_mean=float(np.nanmean(xb)),
               x_b_std=float(np.nanstd(xb)), x_b_std_over_Lb=float(np.nanstd(xb) / np.nanmean(Lb)), L_b_mean=float(np.nanmean(Lb)),
               onset_phase_std_over_T=float(np.nanstd(ph) / T), onset_interval_mean=(float(np.nanmean(np.diff(ton))) if len(ton) > 1 else None),
               onset_interval_std=(float(np.nanstd(np.diff(ton))) if len(ton) > 1 else None),
               drift_eta_c_rel=(drift(ec) / float(np.nanmean(ec)) if drift(ec) is not None else None), drift_x_b_m=drift(xb))
    out["pass"] = dict(eta_c_cv=bool(out["eta_c_cv"] is not None and out["eta_c_cv"] <= 0.05),
                       h_b_cv=bool(out["h_b_cv"] is not None and out["h_b_cv"] <= 0.05),
                       x_b_std_over_Lb=bool(out["x_b_std_over_Lb"] <= 0.05), onset_phase=bool(out["onset_phase_std_over_T"] <= 0.05),
                       drift_eta_c=bool(out["drift_eta_c_rel"] is not None and abs(out["drift_eta_c_rel"]) <= 0.05),
                       drift_x_b=bool(out["drift_x_b_m"] is not None and abs(out["drift_x_b_m"]) <= 5.0))
    out["pass"]["all"] = bool(all(out["pass"].values()))
    # 形の中央値（score3 の最小のコマ）
    def med(nm, key):
        v = [((r.get(nm) or {}).get(key)) for r in rows]
        v = [x for x in v if x is not None and np.isfinite(x)]
        return (float(np.median(v)), float(min(v)), float(max(v))) if v else None
    shape = {}
    for nm in ("best3", "touchdown"):
        shape[nm] = dict(back_angle=med(nm, "back_angle"), width07=med(nm, "width07"), score3=med(nm, "score3"), score_back=med(nm, "score_back"))
        for q in ("chord", "foot", "air", "lip", "area"):
            v = [((r.get(nm) or {}).get("ruler") or {}).get(q) for r in rows]
            v = [x for x in v if x is not None and np.isfinite(x)]
            shape[nm][q] = (float(np.median(v)), float(min(v)), float(max(v))) if v else None
    out["shape_median_min_max"] = shape
    ao = [((r.get("paper") or {}).get("AO_Hb2")) for r in rows]
    out["closed_air_frac"] = float(np.mean([bool(v and v > 0) for v in ao])) if ao else None
    return out


# ====================================================================== 図（PIL）
COLS = [(31, 119, 180), (214, 39, 40), (44, 160, 44), (148, 103, 189), (255, 127, 14), (140, 86, 75), (23, 190, 207), (127, 127, 127),
        (188, 189, 34), (227, 119, 194), (90, 90, 200), (60, 160, 120)]


class Ax:
    def __init__(self, dr, box, xr, yr, title="", xl="", yl=""):
        self.dr, self.box, self.xr, self.yr = dr, box, xr, yr
        x0, y0, x1, y1 = box
        dr.rectangle(box, outline=(120, 120, 120))
        dr.text((x0, y0 - 22), title, fill=(20, 20, 20), font=font(15, True))
        dr.text((x1 - dr.textlength(xl, font=font(12)), y1 + 18), xl, fill=(80, 80, 80), font=font(12))
        dr.text((x0 + 4, y0 + 2), yl, fill=(80, 80, 80), font=font(12))

    def X(self, v):
        x0, _, x1, _ = self.box
        return x0 + (v - self.xr[0]) / (self.xr[1] - self.xr[0]) * (x1 - x0)

    def Y(self, v):
        _, y0, _, y1 = self.box
        return y1 - (v - self.yr[0]) / (self.yr[1] - self.yr[0]) * (y1 - y0)

    def ticks(self, xs, ys, fx="%g", fy="%g"):
        x0, y0, x1, y1 = self.box
        for v in xs:
            u = self.X(v); self.dr.line([(u, y1), (u, y1 - 5)], fill=(90, 90, 90)); self.dr.text((u - 10, y1 + 3), fx % v, fill=(60, 60, 60), font=font(11))
        for v in ys:
            w = self.Y(v); self.dr.line([(x0, w), (x1, w)], fill=(232, 232, 232)); self.dr.text((x0 - 40, w - 7), fy % v, fill=(60, 60, 60), font=font(11))

    def band(self, lo, hi, col=(220, 240, 220)):
        x0, y0, x1, y1 = self.box
        a, b = self.Y(min(max(hi, self.yr[0]), self.yr[1])), self.Y(min(max(lo, self.yr[0]), self.yr[1]))
        if b > a:
            self.dr.rectangle([x0 + 1, a, x1 - 1, b], fill=col)

    def hline(self, v, col=(0, 0, 0), dash=False, width=1):
        x0, _, x1, _ = self.box
        if dash:
            GV.dashed(self.dr, [(x0, self.Y(v)), (x1, self.Y(v))], col, width)
        else:
            self.dr.line([(x0, self.Y(v)), (x1, self.Y(v))], fill=col, width=width)

    def line(self, xs, ys, col, width=2, dash=False):
        pts = [(self.X(a), self.Y(b)) for a, b in zip(xs, ys) if np.isfinite(a) and np.isfinite(b)]
        if len(pts) > 1:
            if dash:
                GV.dashed(self.dr, pts, col, width)
            else:
                self.dr.line(pts, fill=col, width=width)

    def dots(self, xs, ys, col, r=4, hollow=False):
        for a, b in zip(xs, ys):
            if a is None or b is None or not (np.isfinite(a) and np.isfinite(b)):
                continue
            u, w = self.X(a), self.Y(b)
            if hollow:
                self.dr.ellipse([u - r, w - r, u + r, w + r], outline=col, width=2)
            else:
                self.dr.ellipse([u - r, w - r, u + r, w + r], fill=col)


def fig_inlet(out_png, title, ser, t, tgt_s, xp, inl, t_show):
    W_, H_ = 1600, 180 + 170 * len(ser)
    im = Image.new("RGB", (W_, H_), (255, 255, 255)); dr = ImageDraw.Draw(im)
    dr.text((30, 12), title, fill=(0, 0, 0), font=font(20, True))
    dr.text((30, 44), "青＝計算の一番上の水面（4 層の平均、静かな水面から）、黒の破線＝目標（流れ関数の解。頂は x_p で t = 0）。【測った】と【計算】",
            fill=(60, 60, 60), font=font(14))
    m = (t >= t_show[0]) & (t <= t_show[1])
    y = 100
    for xg, e in ser.items():
        ax = Ax(dr, (90, y, W_ - 40, y + 130), t_show, (-4.0, 10.0), "x = %.0f m" % xg, "t (s)", "η (m)")
        ax.ticks(np.arange(math.ceil(t_show[0] / 10) * 10, t_show[1] + 1e-6, 10), [-2, 0, 2, 4, 6, 8])
        ax.hline(0.0, (150, 150, 150))
        tt = t[m]
        ax.line(tt, SF.eta(tgt_s, np.array([xg - xp]), tt), (0, 0, 0), 2, dash=True)
        ax.line(tt, e[m], (31, 90, 200), 2)
        g = next((q for q in inl["gauges"] if q["x"] == xg), None)
        if g and g.get("n"):
            dr.text((W_ - 760, y - 22), "H %.2f m（目標の %+.1f %%）頂 %.2f m（%+.1f %%）谷 %.2f m、位相のずれ %+.2f s、波高の CV %.1f %%（%d 波）" % (
                g["H_mean"], 100 * g["H_rel"], g["crest_mean"], 100 * g["crest_rel"], g["trough_mean"], g["phase_dt_mean_s"], 100 * g["H_cv"], g["n"]),
                fill=(30, 30, 30), font=font(13))
        y += 170
    im.save(out_png)
    return out_png


def fig_events(out_png, title, rows, meas_k, bands, hb_pred=None, meas_k2=None, layer_txt="主の層"):
    keys = [("x_b", "崩れの所 x_b (m)", None), ("eta_c_onset", "崩れの頂 η_c (m)", (10.0, 12.0)), ("h_b", "崩れの水深 h_b (m)", None),
            ("best3.ruler.chord", "前の面の弦（度）", tuple(bands["face_chord_deg_01_05"]["band"])),
            ("best3.back_angle", "後ろの角 0.7〜0.9 η_c（度）", tuple(back_bands()["back_angle_07_09_deg"]["band"])),
            ("best3.width07", "0.7 η_c の幅 ÷ η_c", tuple(back_bands()["width07_silhouette"]["band"])),
            ("best3.score3", "score3（0 が原画の帯の中）", (0.0, 0.0)), ("paper.AO_Hb2", "巻きの空気 AO/Hb²（着水）", None)]
    W_, H_ = 1600, 140 + 230 * 4
    im = Image.new("RGB", (W_, H_), (255, 255, 255)); dr = ImageDraw.Draw(im)
    dr.text((30, 12), title, fill=(0, 0, 0), font=font(20, True))
    dr.text((30, 44), "来た波の崩れ k ごと（%s）。薄茶＝測る回 k %d〜%d%s、緑の帯＝原画の 4 つの読みの帯（頂は C&N の 10〜12 m）。形は score3 の最小のコマ。【測った】" % (
        layer_txt, meas_k[0], meas_k[1], ("、薄青の枠＝延ばした回 k %d〜%d" % tuple(meas_k2)) if meas_k2 else ""), fill=(60, 60, 60), font=font(14))

    def get(r, path):
        v = r
        for p in path.split("."):
            v = (v or {}).get(p) if isinstance(v, dict) else None
        return v
    ks = [r["k"] for r in rows]
    kr = (0.5, max(ks) + 0.5) if ks else (0, 1)
    for i, (path, lab, band) in enumerate(keys):
        cx_, cy_ = i % 2, i // 2
        x0 = 100 + cx_ * 760; y0 = 110 + cy_ * 230
        vals = [get(r, path) for r in rows]
        fv = [v for v in vals if v is not None and np.isfinite(v)]
        if not fv:
            fv = [0.0, 1.0]
        lo, hi = min(fv), max(fv)
        if band and band[0] is not None:
            lo = min(lo, band[0]); hi = max(hi, band[1] if band[1] is not None else band[0])
        pad = 0.12 * (hi - lo) if hi > lo else 1.0
        ax = Ax(dr, (x0, y0, x0 + 660, y0 + 170), kr, (lo - pad, hi + pad), lab, "k", "")
        ax.dr.rectangle([ax.X(meas_k[0] - 0.5), y0 + 1, ax.X(meas_k[1] + 0.5), y0 + 169], fill=(245, 240, 225))
        if meas_k2:
            ax.dr.rectangle([ax.X(meas_k2[0] - 0.5), y0 + 3, ax.X(min(meas_k2[1], max(ks) if ks else meas_k2[1]) + 0.5), y0 + 167], outline=(90, 140, 210), width=2)
        if band and band[0] is not None:
            ax.band(band[0], band[1] if band[1] is not None else band[0] + 1e-9)
        step = max(1, int(round((hi - lo) / 4))) if hi - lo > 4 else None
        yt = np.linspace(lo, hi, 5)
        ax.ticks(range(1, max(ks) + 1) if ks else [], yt, "%d", "%.3g")
        for r, v in zip(rows, vals):
            ax.dots([r["k"]], [v], COLS[0] if meas_k[0] <= r["k"] <= meas_k[1] else (150, 150, 150), 5)
        if path == "x_b" and hb_pred:
            for xpred in hb_pred:
                ax.hline(xpred, (200, 60, 60), dash=True)
    im.save(out_png)
    return out_png


def fig_overlay(out_png, title, rows, meas_k):
    pr = GV.print_ref()
    XL, XR, ZB, ZT = -2.4, 1.6, -0.35, 1.15
    s = 520.0
    pw, ph = int((XR - XL) * s), int((ZT - ZB) * s)
    W_, H_ = pw + 1000, ph + 170
    im = Image.new("RGB", (W_, H_), (255, 255, 255)); dr = ImageDraw.Draw(im)
    dr.text((30, 12), title, fill=(0, 0, 0), font=font(20, True))
    dr.text((30, 44), "測る回の score3 が最小のコマを η_c で割り頂をそろえて重ねた（主の層）。黒＝原画（縦の伸びを戻した形）、灰の破線＝描かれたまま。【測った】",
            fill=(60, 60, 60), font=font(14))
    x0, y0 = 60, 100
    tr = lambda P: [(x0 + (p[0] - XL) * s, y0 + (ZT - p[1]) * s) for p in P]
    dr.rectangle([x0, y0, x0 + pw, y0 + ph], outline=(150, 150, 150))
    for zv in (0.0, 0.5, 1.0):
        yy = y0 + (ZT - zv) * s
        dr.line([(x0, yy), (x0 + pw, yy)], fill=(200, 200, 200) if zv else (120, 120, 120))
        dr.text((x0 - 30, yy - 8), "%g" % zv, fill=(80, 80, 80), font=font(12))
    box = (XL, XR, ZB, ZT)
    for q in pr["drawn"]:
        for P in GV.split_inside(q, *box):
            GV.dashed(dr, tr(P), (150, 150, 150), 2)
    for q in pr["cn"]:
        for P in GV.split_inside(q, *box):
            dr.line(tr(P), fill=(0, 0, 0), width=4)
    yl = y0
    for i, r in enumerate([r for r in rows if meas_k[0] <= r["k"] <= meas_k[1]]):
        b = r.get("best3") or {}
        col = COLS[i % len(COLS)]
        for q in b.get("lines") or []:
            for P in GV.split_inside(np.array(q), *box):
                if len(P) > 1:
                    dr.line(tr(P), fill=col, width=2)
        dr.line([(x0 + pw + 30, yl + 9), (x0 + pw + 60, yl + 9)], fill=col, width=3)
        dr.text((x0 + pw + 66, yl), "k %d：コマ %s、η_c %.2f m、弦 %.0f°、後ろ %s°、幅 %s、score3 %.2f" % (
            r["k"], b.get("frame"), b.get("eta") or float("nan"), ((b.get("ruler") or {}).get("chord") or float("nan")),
            ("%.0f" % b["back_angle"]) if b.get("back_angle") is not None else "-", ("%.2f" % b["width07"]) if b.get("width07") is not None else "-",
            b.get("score3") if b.get("score3") is not None else float("nan")), fill=(30, 30, 30), font=font(13))
        yl += 24
    im.save(out_png)
    return out_png


# ====================================================================== 本体
def main_all(ref, opt):
    GC.unthrottle_self()
    rd = resolve(ref)
    rid = os.path.basename(rd)
    out = guard(os.path.join(rd, "pana"))
    os.makedirs(out, exist_ok=True)
    os.makedirs(guard(CMP), exist_ok=True)
    t_start = time.time()
    cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    s = sf_of(cfg)
    T = float(s["T"]) if s else 14.0
    cx0 = GA.Ctx(rd, {})
    off = cx0.off
    hf = load_hf(rd)
    res = dict(stage="FLIP47", tool="g47_periodic_ana.py", run=rid, rd=rd, made=time.strftime("%Y-%m-%d %H:%M:%S"),
               still_offset_m=off, still_offset_src=cx0.off_src, cfg=dict(bed=cfg.get("bed"), wave=cfg.get("wave"), sf_T=T, sf_H=(s or {}).get("H"),
                                                                            dp=cfg["parms"]["dp"], solver=cfg.get("solver"), relax_w=cfg["parms"].get("relax_w"),
                                                                            set_P=cfg["parms"].get("set_P")),
               labels_ja="数は【測った】（計算の記録から）。目標と帯は【計算】（流れ関数の解）と設計の凍結した帯")
    rr = run_records(rd)
    if rr:
        res["run_info"] = dict(launches=len(rr), wall_s=sum(float(r.get("wall_total_s") or 0) for r in rr), f_end_done=rr[-1].get("f_end_done"),
                          stopped=rr[-1].get("stopped"), particles_first=rr[0].get("particles_first"),
                          particles_max=max(int(r.get("particles_max") or 0) for r in rr),
                          substeps=[min((r.get("substeps_min_max") or [99, 0])[0] for r in rr), max((r.get("substeps_min_max") or [0, 0])[1] for r in rr)],
                          rss_peak_gb=max(float(r.get("rss_peak_gb") or 0) for r in rr),
                          leak_below_bed_max=max([l.get("n_below_bed", 0) for r in rr for l in (r.get("info") or {}).get("leak", [])] or [0]),
                          leak_out_max=max([l.get("n_out_x", 0) + l.get("n_out_z", 0) for r in rr for l in (r.get("info") or {}).get("leak", [])] or [0]),
                          level_start=rr[0].get("level_start_m"), level_end=rr[-1].get("level_end_m"),
                          sf_table=(rr[0].get("info") or {}).get("sf_table"))
        npts = np.concatenate([np.load(p)["npts"] for p in sorted(glob.glob(os.path.join(rd, "hf_c*.npz")))])
        res["run_info"]["particles_growth"] = float(npts.max() / npts[npts > 0][0]) if (npts > 0).any() else None
    # 箱の全部の一番上の水面の平均（閉じた水槽なので、水の体積 ÷ 長さの変わり。巻いた所は一番上だけ）と粒子の数（問題 5）
    fr_, t_, X_, Z_, eta_ = hf
    lv = np.nanmean(np.nanmean(eta_, axis=1), axis=1) - off
    npl = []
    for p_ in sorted(glob.glob(os.path.join(rd, "hf_c*.npz")), key=lambda q: int(os.path.basename(q)[4:8])):
        d_ = np.load(p_); npl += list(zip([int(v) for v in d_["frames"]], [int(v) for v in d_["npts"]]))
    npd = dict(npl)
    res["box_level"] = dict(rule_ja="箱の全部（x %.0f〜%.0f m）の一番上の水面の平均 − 静かな水面のずれ（4 層の平均）。閉じた水槽なので、本当は 0 のまま。"
                                    "上がった分 × 箱の長さ ＝ FLIP が増やした水（1 m の幅あたり m²）" % (X_[0], X_[-1]),
                            every_5s=[[float(t_[i]), float(lv[i]), npd.get(int(fr_[i]))] for i in range(0, len(t_), 120)],
                            end=float(lv[-1]), max=float(np.nanmax(lv)), box_len_m=float(X_[-1] - X_[0] + (X_[1] - X_[0])),
                            gain_m2_per_m_end=float(lv[-1] * (X_[-1] - X_[0] + (X_[1] - X_[0]))))
    # ---- 入口
    figs = {}
    if s and float(cfg["parms"].get("sf_on", 0)) > 0.5 and float(cfg["parms"].get("set_P", 0)) < 1e8:
        tw = [float(v) for v in opt["inlet_t"].split(",")] if opt.get("inlet_t") else None
        gauges = [float(v) for v in opt["gauges"].split(",")] if opt.get("gauges") else (450.0, 480.0, 510.0, 540.0, 560.0)
        pairs = [tuple(float(u) for u in p.split(":")) for p in opt["pairs"].split(",")] if opt.get("pairs") else [(480.0, 510.0)]
        inl, ser, el, t_hf = inlet(rd, cfg, hf, off, tw, gauges, pairs)
        res["inlet"] = inl
        ts_ = (max(inl["window_s"][0], inl["window_s"][1] - 60.0), inl["window_s"][1])
        figs["inlet"] = fig_inlet(os.path.join(out, "%s_inlet_gauges.png" % rid), "%s：入口の計り所（帯の出口 x_p %.0f m より先）" % (rid, float(cfg["parms"]["x_p"])),
                                  ser, t_hf, (design_sf(cfg) or s), float(cfg["parms"]["x_p"]), inl, ts_)
    else:
        fr, t_hf, X, Z, eta = hf
        el = np.nanmean(eta, axis=1) - off
    if opt.get("what") == "inlet":
        jdump(res, os.path.join(out, "periodic_inlet.json"))
        print(json.dumps(clean(res.get("inlet", {}).get("pass")), ensure_ascii=False))
        return res
    # ---- 崩れ
    evs, after, run, sec = find_events(rd)
    res["events_found"] = evs
    res["events_secondary"] = sec
    res["after_breaking_not_counted"] = after
    res["events_rule_ja"] = ("g47_video.Run.events（前の面の弦 90° 以上の最初のコマ、山ができてから 1 s 以上、頂 1 m 以上。巻き始めの後 6 s の内に 10 m 後ろより"
                             "前で生まれた山の巻きは数えない）のうち、(a) 頂の筋が斜面の足 x %.0f m より沖で生まれた物、または (b) 巻き始めの静かな水深 5 m 以上で"
                             "頂が (a) の中央値の 0.5 倍以上で、(a) と採った崩れのどれとも 0.6 T 以上離れた物を、来た波の崩れとし、時刻の順に k。"
                             "ほか（浅い所の段波・跳ね上がりの巻き直し）は events_secondary（k_all は g47_video の番号）" % PRIMARY_X)
    X_hf = hf[2]
    mk = [int(v) for v in opt.get("measure", "5,10").split(",")]
    mk2 = [int(v) for v in opt["measure_ext"].split(",")] if opt.get("measure_ext") else None
    res["measure_k_ext"] = mk2
    lay_lo, lay_hi = (min(mk[0], mk2[0]), max(mk[1], mk2[1])) if mk2 else (mk[0], mk[1])
    res["measure_k"] = mk
    rows = []
    layer_rows = {}
    for ev in evs:
        t0 = time.time()
        _a = analyze_event(rd, ev, None)
        A = event_row(rd, cfg, ev, _a, el, t_hf, X_hf, T)
        del _a
        import gc; gc.collect()          # 記録の塊（sdf・sdfz）を回ごとに離す（2026-10-13 P1c でメモリーが足りなくなったため）
        rows.append(A)
        print("k %d onset f %s t %.2f x %.1f eta %.2f h_b %.2f score3 %s back %s width %s AO %s (%.0f s)" % (
            ev["k"], A.get("on_frame"), A.get("t_onset", float("nan")), A.get("x_b", float("nan")), A.get("eta_c_onset", float("nan")),
            A.get("h_b", float("nan")), (A.get("best3") or {}).get("score3"), (A.get("best3") or {}).get("back_angle"),
            (A.get("best3") or {}).get("width07"), (A.get("paper") or {}).get("AO_Hb2"), time.time() - t0))
        sys.stdout.flush()
        if str(opt.get("layers", "1")) == "1" and lay_lo <= ev["k"] <= lay_hi:
            lr = {}
            for z in ["mean", 0, 1, 2, 3]:
                try:
                    Az = analyze_event(rd, ev, z)
                    Az.pop("cx", None)
                    sm = Az["summ"]
                    lr[str(z)] = dict(best3=({k_: (sm.get("best3") or {}).get(k_) for k_ in ("frame", "score3", "ruler", "eta")}),
                                      touchdown_frame=(sm.get("touchdown") or {}).get("frame"),
                                      paper={k_: (sm.get("paper") or {}).get(k_) for k_ in ("Hb_m", "AJ_Hb2", "AO_Hb2", "W_L", "theta_o_deg")},
                                      back_angle=((Az["extra"].get("best3") or {}).get("back_angle_07_09_deg")),
                                      width07=((Az["extra"].get("best3") or {}).get("width07_silhouette")))
                except Exception as e:
                    lr[str(z)] = dict(err=repr(e)[:200])
            ao = [((lr.get(str(z)) or {}).get("paper") or {}).get("AO_Hb2") for z in range(4)]
            aov = [v for v in ao if v is not None]
            lr["AO_spread"] = dict(values=ao, spread_over_mean=(float((max(aov) - min(aov)) / np.mean(aov)) if len(aov) == 4 and np.mean(aov) > 0 else None))
            layer_rows[str(ev["k"])] = lr
            A["layers"] = lr
    res["events"] = rows
    meas = [r for r in rows if mk[0] <= r["k"] <= mk[1] and r.get("on_frame")]
    res["repeat"] = stats(meas, T) if meas else None
    if mk2:
        meas2 = [r for r in rows if mk2[0] <= r["k"] <= mk2[1] and r.get("on_frame")]
        res["repeat_ext"] = stats(meas2, T) if meas2 else None
        if res["repeat_ext"]:
            res["repeat_ext"]["note_ja"] = "設計の延ばしの決まり（k %d〜%d）" % tuple(mk2)
    # ---- 問題ごとの判定（§6.4）
    chk = {}
    if res["repeat"]:
        sh = res["repeat"]["shape_median_min_max"]["best3"]
        ba = sh["back_angle"][0] if sh["back_angle"] else None; wd = sh["width07"][0] if sh["width07"] else None
        chk["problem1_back"] = dict(back_angle_median=ba, width07_median=wd,
                                    improved=bool(ba is not None and wd is not None and ba >= 20.0 and wd <= 2.0),
                                    in_print_band=bool(ba is not None and wd is not None and 29.0 <= ba <= 38.4 and 1.02 <= wd <= 1.42),
                                    rule_ja="測る回の中央値で後ろの角 ≥ 20° かつ幅 ≤ 2.0 なら直った、29〜38°・1.02〜1.42 なら原画の帯の中")
        sp = [((r.get("layers") or {}).get("AO_spread") or {}).get("spread_over_mean") for r in meas]
        sp = [v for v in sp if v is not None]
        chk["problem3_layers"] = dict(AO_spread_over_mean=sp, median=(float(np.median(sp)) if sp else None),
                                      passed=bool(sp and max(sp) <= 0.2), rule_ja="4 層の AO/Hb² の（最大 − 最小）÷ 平均 ≤ 0.2（測る回のすべて）")
    if mk2 and res.get("repeat_ext"):
        sh2 = res["repeat_ext"]["shape_median_min_max"]["best3"]
        ba2 = sh2["back_angle"][0] if sh2["back_angle"] else None; wd2 = sh2["width07"][0] if sh2["width07"] else None
        meas2 = [r for r in rows if mk2[0] <= r["k"] <= mk2[1] and r.get("on_frame")]
        sp2 = [((r.get("layers") or {}).get("AO_spread") or {}).get("spread_over_mean") for r in meas2]
        sp2 = [v for v in sp2 if v is not None]
        chk["ext"] = dict(k=mk2, problem1_back=dict(back_angle_median=ba2, width07_median=wd2,
                                                     improved=bool(ba2 is not None and wd2 is not None and ba2 >= 20.0 and wd2 <= 2.0),
                                                     in_print_band=bool(ba2 is not None and wd2 is not None and 29.0 <= ba2 <= 38.4 and 1.02 <= wd2 <= 1.42)),
                          problem3_layers=dict(AO_spread_over_mean=sp2, median=(float(np.median(sp2)) if sp2 else None), passed=bool(sp2 and max(sp2) <= 0.2)))
    chk["breaking_x_lt_570"] = [r["k"] for r in rows if r.get("x_b") is not None and r["x_b"] < 570.0]
    chk["breaking_575_700_count"] = sum(1 for r in rows if r.get("x_b") is not None and 575.0 <= r["x_b"] <= 700.0)
    if "inlet" in res:
        chk["problem5_mean_level"] = dict(drift=res["inlet"]["mean_level"]["drift_in_window"], passed=bool(
            res["inlet"]["mean_level"]["drift_in_window"] is not None and abs(res["inlet"]["mean_level"]["drift_in_window"]) <= 0.1))
    bed = cfg["bed"]
    flat = [p for p in bed if abs(p[1] - min(q[1] for q in bed)) < 1e-6]
    if flat:
        xa = flat[0][0] + 4.0; xb_ = min(flat[0][0] + 44.0, float(cfg["parms"]["xa0"]) - 5.0)
        selx = (X_hf >= xa) & (X_hf <= xb_)
        if selx.any():
            sel_t = t_hf >= (meas[0]["t_onset"] if meas else 60.0)
            chk["setup_on_shallow"] = dict(x=[xa, xb_], mean_level=float(np.nanmean(el[np.ix_(sel_t, selx)])) if sel_t.any() else None,
                                           note_ja="浅い所の平均の水面（静かな水面から）。測る回の間の時間の平均")
    res["checks"] = chk
    # ---- 図
    TG, bands = GS._bands()
    pred = None
    try:
        D = json.load(open(B47 + "/periodic_design.json", encoding="utf8"))
        for r_ in D["runs"].values():
            if r_.get("run_id") == rid and r_.get("breaking_prediction"):
                pred = [b["x_b"] for b in r_["breaking_prediction"] if b.get("broke") and b["method"].startswith("goda")]
    except Exception:
        pass
    figs["events"] = fig_events(os.path.join(out, "%s_events.png" % rid), "%s：崩れの回ごとの量" % rid, rows, mk, bands, pred, mk2,
                                "主の層 z %+.2f m" % float(GA.Ctx(rd, {}).rec.meta.get("z", float("nan"))))
    figs["overlay"] = fig_overlay(os.path.join(out, "%s_overlay.png" % rid), "%s：測る回の形と原画" % rid, rows, mk)
    res["figures"] = figs
    for p in figs.values():
        shutil.copy2(p, os.path.join(CMP, os.path.basename(p)))
    res["elapsed_s"] = time.time() - t_start
    jdump(res, os.path.join(out, "periodic_ana.json"))
    jdump(res, os.path.join(CMP, "periodic_ana_%s.json" % rid))
    print("wrote", os.path.join(out, "periodic_ana.json"), "%.0f s" % res["elapsed_s"])
    return res


def fmt(v, f="%.2f"):
    try:
        return f % v if v is not None and np.isfinite(v) else "−"
    except Exception:
        return "−"


def table(paths):
    """periodic_ana.json → 回ごとの Markdown の表と、繰り返しの表。"""
    out = []
    for ref in paths:
        rd = resolve(ref)
        d = json.load(open(os.path.join(rd, "pana", "periodic_ana.json"), encoding="utf8"))
        out.append("#### %s\n" % os.path.basename(rd))
        out.append("| k | 巻き始め t (s) | x_b (m) | h_b (m) | η_c (m) | H (m) | 最も近いコマ | 弦 (°) | 足 | 覆い | 空気 | 唇 | 後ろの角 (°) | 幅 0.7 | score3 | 着水 AO/Hb² | 層の AO の幅 |")
        out.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for r in d["events"]:
            b = r.get("best3") or {}; ru = b.get("ruler") or {}
            sp = (((r.get("layers") or {}).get("AO_spread")) or {}).get("spread_over_mean")
            out.append("| %d | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                r["k"], fmt(r.get("t_onset")), fmt(r.get("x_b"), "%.1f"), fmt(r.get("h_b")), fmt(r.get("eta_c_onset")), fmt(r.get("H_onset")),
                b.get("frame", "−"), fmt(ru.get("chord"), "%.1f"), fmt(ru.get("foot")), fmt(ru.get("area"), "%.3f"), fmt(ru.get("air")), fmt(ru.get("lip")),
                fmt(b.get("back_angle"), "%.1f"), fmt(b.get("width07")), fmt(b.get("score3")), fmt((r.get("paper") or {}).get("AO_Hb2")), fmt(sp)))
        for key in ("repeat", "repeat_ext"):
            rp = d.get(key)
            if not rp:
                continue
            out.append("\n- %s（k %s）：η_c 平均 %s m・CV %s、h_b 平均 %s m・CV %s、x_b 平均 %s m・標準偏差 %s m（÷ L_b %s）、巻き始めの位相のばらつき ÷ T %s、"
                       "間隔 %s ± %s s、流れ η_c %s・x_b %s m、閉じた空気 %s、合否 %s" % (
                           "測る回" if key == "repeat" else "延ばした回", rp["k"], fmt(rp["eta_c_mean"]), fmt(rp["eta_c_cv"], "%.3f"), fmt(rp["h_b_mean"]),
                           fmt(rp["h_b_cv"], "%.3f"), fmt(rp["x_b_mean"], "%.1f"), fmt(rp["x_b_std"], "%.1f"), fmt(rp["x_b_std_over_Lb"], "%.3f"),
                           fmt(rp["onset_phase_std_over_T"], "%.3f"), fmt(rp.get("onset_interval_mean")), fmt(rp.get("onset_interval_std")),
                           fmt(rp.get("drift_eta_c_rel"), "%+.3f"), fmt(rp.get("drift_x_b_m"), "%+.1f"), fmt(rp.get("closed_air_frac")),
                           json.dumps(rp["pass"], ensure_ascii=False)))
        out.append("")
    return "\n".join(out)


def parse(argv):
    opt, pos = {}, []
    for a in argv:
        if a.startswith("--"):
            k, _, v = a[2:].partition("=")
            opt[k] = v if v else "1"
        else:
            pos.append(a)
    return opt, pos


if __name__ == "__main__":
    opt, pos = parse(sys.argv[1:])
    if not pos:
        print(__doc__); sys.exit(1)
    what = pos[0]
    if what == "figs":                     # periodic_ana.json から図だけ描き直す
        for ref in pos[1:]:
            rd = resolve(ref); rid = os.path.basename(rd)
            d = json.load(open(os.path.join(rd, "pana", "periodic_ana.json"), encoding="utf8"))
            TG, bands = GS._bands()
            mk = d.get("measure_k") or [5, 10]; mk2 = d.get("measure_k_ext")
            out = os.path.join(rd, "pana")
            ps = [fig_events(os.path.join(out, "%s_events.png" % rid), "%s：崩れの回ごとの量" % rid, d["events"], mk, bands, None, mk2,
                             "主の層 z %+.2f m" % float(GA.Ctx(rd, {}).rec.meta.get("z", float("nan")))),
                  fig_overlay(os.path.join(out, "%s_overlay.png" % rid), "%s：測る回の形と原画" % rid, d["events"], mk)]
            for q in ps:
                shutil.copy2(q, os.path.join(CMP, os.path.basename(q)))
            print("redrew", ps)
        sys.exit(0)
    if what == "table":
        print(table(pos[1:]))
        sys.exit(0)
    if what == "events":
        evs, after, _, sec = find_events(resolve(pos[1]))
        for e in evs:
            print(json.dumps(e, ensure_ascii=False))
        print("secondary (crest track born at x >= %g m):" % PRIMARY_X)
        for e in sec:
            print("  ", json.dumps(e, ensure_ascii=False))
        print("after-breaking overturns not counted:", len(after))
    elif what in ("all", "inlet"):
        opt["what"] = what
        main_all(pos[1], opt)
    else:
        print(__doc__)
