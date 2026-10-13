# -*- coding: utf-8 -*-
"""FLIP44：風の実験の判定（計画 plan_ja.md §4.3 の W1〜W8）。py -3.10。
  W6：毎コマ、露出した水面の 20 点で、場に書いた圧力（psec）が式 R(t)·wt(x)·q·n_x の ±5 %、上に水がある所が 0。
      点の選び方は S5 と同じ（record_ja.md の計画の読み方 9）：主な頂の後ろ 1 η_c から前 2 η_c、|SDF| < 格子の半分、|n_x| ≥ 0.2、
      numpy の同じ決まり（しぶきの決まりを含む）で露出。しぶきの決まりで無視した列の数（上に水があるが厚さ 2 dp より薄い列）と、その水の面積も書く。
  W8：風を入れてから風なしの巻き始めまで、主な頂の η_c と位置を 0.25 s ごとに、風あり − 風なし。読む点 395・420・450 m の頂の高さと通る時刻の差。
  W1〜W5：11 の形の量（各計算のいちばん巻いたコマ）、巻き始めの時刻と場所、着水の時刻の差。物差し Y（計画 §3.3 (b) の表）、
      原画の側か、割合（W5 の決まり：風なしが原画の幅の中か、|原画 − 風なし| < 2Y なら出さない）。
使い方：py -3.10 g44_wind_check.py <風ありの run_id> <風なしの run_id（B0 か形の本番）> [runs|smoke]  → <root>/<風あり>/wind_check.json
"""
import sys, os, json, glob, math
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip44")
import g44_analyze as A
import g44_shape as SHP

FPS = 24.0


def psec_index(rd):
    best = {}; meta = None
    for p in glob.glob(os.path.join(rd, "psec_c*_b*.npz")):
        f0 = int(os.path.basename(p)[6:10]); d = np.load(p)
        meta = meta or json.loads(str(d["meta"]))
        for i, f in enumerate(d["frames"]):
            f = int(f)
            if f >= f0 and (f not in best or best[f][0] < f0):
                best[f] = (f0, p, i)
    return best, meta


def sample(S, x0, dx, y0, dy, x, y):
    ny, nx = S.shape
    fx = min(max((x - x0) / dx, 0.0), nx - 1.0); fy = min(max((y - y0) / dy, 0.0), ny - 1.0)
    i = min(int(math.floor(fx)), nx - 2); j = min(int(math.floor(fy)), ny - 2)
    wx = fx - i; wy = fy - j
    return ((S[j, i] * (1 - wx) + S[j, i + 1] * wx) * (1 - wy) + (S[j + 1, i] * (1 - wx) + S[j + 1, i + 1] * wx) * wy)


def column(S, geo, px, py, dp, ytop, thin_mult):
    """g44_tanklib.covered と同じ決まり。返り値：(上に水があるか, しぶきの決まりで無視した水の厚さの和)。"""
    x0, dx, y0, dy = geo
    st = 0.5 * dp; need = thin_mult * dp * (1.0 - 1e-3)
    sp = sample(S, x0, dx, y0, dy, px, py)
    yin = py if sp < 0 else -1e9
    y = py; thin = 0.0
    while y < ytop:
        yn = y + st
        s = sample(S, x0, dx, y0, dy, px, yn)
        if sp >= 0 and s < 0:
            yin = y + st * sp / (sp - s)
        elif sp < 0 and s >= 0:
            yout = y + st * sp / (sp - s)
            if yout - yin >= need:
                return True, thin
            thin += yout - yin
            yin = -1e9
        sp = s; y = yn
    if sp < 0 and ytop - yin >= need:
        return True, thin
    return False, thin


def windramp(t, p):
    if t < p["wind_t0"] or t > p["wind_t1"]:
        return 0.0
    if p["wind_tramp"] <= 0:
        return 1.0
    c = min(max((t - p["wind_t0"]) / p["wind_tramp"], 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * c)


def smooth01(c):
    c = min(max(c, 0.0), 1.0)
    return c * c * (3 - 2 * c)


def w6(rd, cfg, off, crest_by_frame, nx_min=0.2, xwin_rel=None):
    """xwin_rel = None：主な頂の後ろ 1 η_c から前 2 η_c（読み方 17）。xwin_rel = (a, b)：造波板から a〜b m の全部（煙の試し S9 だけ。
    record_ja.md の計画から変えた所 5）。nx_min：比べる点の |n_x| の下の端。"""
    p = cfg["parms"]; dp = p["dp"]; vox = 2 * dp
    SR = A.SecReader(rd)
    PB, pmeta = psec_index(rd)
    rows = []
    for f in sorted(PB):
        if f not in SR.best or (xwin_rel is None and f not in crest_by_frame):
            continue
        t = (f - 1) / FPS
        R = windramp(t, p)
        if R <= 0:
            continue
        m = SR.meta
        f0, path, i = PB[f]
        dz = np.load(path)
        Pf = dz["p"][i].astype(np.float64)
        # 圧力を書いた時の水面の場の写し（ws）があればそれで式の値を出す（record_ja.md の計画から変えた所 6）。なければコマの終わりの断面の場
        if "ws" in dz.files and np.isfinite(dz["ws"][i]).all():
            S = dz["ws"][i].astype(np.float64); src = "windsurf"
        else:
            S = SR.get(f).astype(np.float64); src = "sec"
        xs = m["x0"] + m["dx"] * np.arange(m["nx"]); ys = m["y0"] + m["dy"] * np.arange(m["ny"])
        geo = (m["x0"], m["dx"], m["y0"], m["dy"])
        gy, gx = np.gradient(S, m["dy"], m["dx"])
        if xwin_rel is None:
            xc, eta = crest_by_frame[f]
            xa_, xb_ = xc - eta, xc + 2 * eta
        else:
            xa_, xb_ = p["x_p"] + xwin_rel[0], p["x_p"] + xwin_rel[1]
        pts = []; cov_nonzero = 0; ncov = 0; thin_cols = 0; thin_area = 0.0
        cand = (np.abs(S) < 0.5 * vox) & ((xs >= xa_) & (xs <= xb_))[None, :]
        for j, ii in zip(*np.where(cand)):
            if True:
                g = np.array([gx[j, ii], gy[j, ii]]); gl = np.linalg.norm(g)
                if gl < 1e-6:
                    continue
                n = g / gl
                p0x = xs[ii] - n[0] * S[j, ii] + n[0] * 0.5 * dp; p0y = ys[j] - n[1] * S[j, ii] + n[1] * 0.5 * dp
                cov, thin = column(S, geo, p0x, p0y, dp, p["ytop"], p["thin_mult"])
                pv = float(Pf[j, ii])
                if thin > 0:
                    thin_cols += 1; thin_area += thin * m["dx"]
                if cov:
                    ncov += 1
                    if pv != 0.0:
                        cov_nonzero += 1
                elif abs(n[0]) >= nx_min:
                    wt = smooth01((xs[ii] - p["wind_x0"]) / p["wind_tap"]) * smooth01((p["wind_x1"] - xs[ii]) / p["wind_tap"])
                    pref = R * wt * p["wind_q"] * n[0]
                    pts.append((xs[ii], pv, pref))
        pts.sort()
        pick = [pts[int(round(k))] for k in np.linspace(0, len(pts) - 1, 20)] if len(pts) >= 20 else pts
        errs = [abs(pv - pr) / abs(pr) for _, pv, pr in pick if pr != 0]
        rows.append(dict(frame=f, t=t, R=R, surface_src=src, n_exposed=len(pts), max_rel_err=max(errs) if errs else None, ok_20=bool(len(pick) == 20 and errs and max(errs) <= 0.05),
                         n_covered=ncov, covered_nonzero=cov_nonzero, thin_cols=thin_cols, thin_area_m2=thin_area, p_max_abs=float(np.abs(Pf).max())))
    bad = [r for r in rows if not (r["ok_20"] and r["covered_nonzero"] == 0)]
    return dict(frames=len(rows), frames_bad=[r["frame"] for r in bad][:50], pass_=bool(rows and not bad), rows=rows)


def crest_series(rd, cfg, off, t0, t1):
    CA = A.crest_analysis(rd, cfg, off, t_from=t0)
    m = A.main_event([e for e in CA["events"] if (e["first_frame"] - 1) / FPS <= t1])
    return m, CA


def w8(rd_w, cfg_w, rd_0, cfg_0, off, t0, t_on0):
    mw, _ = crest_series(rd_w, cfg_w, off, t0, t_on0)
    m0, _ = crest_series(rd_0, cfg_0, off, t0, t_on0)
    if mw is None or m0 is None:      # 2026-10-12 確かめ F1：主な頂がない時に止まらず理由を書く
        return dict(rows=[], at_nowind_onset=None, includes_pre_onset_effect=None, gauges={},
                    skipped_ja="主な頂が見つからない（風あり %s・風なし %s）" % (mw is not None, m0 is not None))
    pw = {p[0]: p for p in mw["path"]}; p0 = {p[0]: p for p in m0["path"]}
    rows = []
    f = int(round(t0 * FPS)) + 1
    while (f - 1) / FPS <= t_on0 + 1e-9:
        if f in pw and f in p0:
            rows.append(dict(frame=f, t=(f - 1) / FPS, d_eta=pw[f][2] - p0[f][2], d_x=pw[f][1] - p0[f][1], eta0=p0[f][2]))
        f += 6
    last = rows[-1] if rows else None
    # 読む点の頂の高さと通る時刻
    Dw = A.load_hf(rd_w); D0 = A.load_hf(rd_0)
    xp = cfg_w["parms"]["x_p"]
    gauges = {}
    for g in (395.0, 420.0, 450.0):
        ew = A.gauge(A.zmean(Dw) - off, Dw["x"], xp + g); e0 = A.gauge(A.zmean(D0) - off, D0["x"], xp + g)
        f_common = sorted(set(map(int, Dw["frames"])) & set(map(int, D0["frames"])))
        iw = [list(Dw["frames"]).index(f) for f in f_common]; i0 = [list(D0["frames"]).index(f) for f in f_common]
        a = ew[iw]; b = e0[i0]
        ja = A.argmax_or_none(a); jb = A.argmax_or_none(b)
        if ja is None or jb is None:
            gauges["%g" % g] = dict(skipped_ja="共通のコマが %d で、どちらかの一番上の水面が全部 NaN か空" % len(f_common)); continue
        gauges["%g" % g] = dict(max_wind=float(a[ja]), max_nowind=float(b[jb]), d_max=float(a[ja] - b[jb]),
                                d_t=float((f_common[ja] - f_common[jb]) / FPS), identical_series=bool(np.array_equal(a, b)))
    flag = bool(last and (abs(last["d_eta"]) > 0.03 * last["eta0"] or abs(last["d_x"]) > 5.140625))
    return dict(rows=rows, at_nowind_onset=last, includes_pre_onset_effect=flag, gauges=gauges)


def w1_5(rid_w, rid_0, root, P):
    aw = json.load(open(os.path.join(A.run_dir(rid_w, root), "ana.json"), encoding="utf8"))
    a0 = json.load(open(os.path.join(A.run_dir(rid_0, root), "ana.json"), encoding="utf8"))
    sw = SHP.measure_three(rid_w, root, aw["onset"]["frame"], aw["touchdown"]["frame"])["max_overturn"]
    s0 = SHP.measure_three(rid_0, root, a0["onset"]["frame"], a0["touchdown"]["frame"])["max_overturn"]
    rows = []
    for m in P["shape"]["measures"]:
        k = m["key"]; Y = m["yardstick"]
        vw, v0 = sw.get(k), s0.get(k)
        if vw is None or v0 is None:
            rows.append(dict(key=k, missing=True)); continue
        d = vw - v0; gap0 = m["print_cn"] - v0
        lo, hi = m["print_range"]
        in_range = lo <= v0 <= hi
        share = None; why = None
        if in_range:
            why = "風なしが原画の幅の中"
        elif abs(gap0) < P["criteria"]["share"]["no_share_gap_over_Y"] * Y:
            why = "|原画 − 風なし| が物差しの 2 倍より小さい"
        else:
            share = d / gap0
        rows.append(dict(key=k, ja=m["ja"], wind=vw, nowind=v0, delta=d, Y=Y, moved=bool(abs(d) > Y), toward_print=bool(np.sign(d) == np.sign(gap0)),
                         share_of_remaining=share, no_share_reason=why,
                         range_note=("幅の中のまま" if (lo <= vw <= hi) else "幅から出た") if in_range else None))
    on = dict(d_t=aw["onset"]["t"] - a0["onset"]["t"], d_x=aw["onset"]["xc_rel"] - a0["onset"]["xc_rel"],
              d_td_t=aw["touchdown"]["t"] - a0["touchdown"]["t"])
    on.update(moved_t=bool(abs(on["d_t"]) > P["criteria"]["wind"]["onset_dt_s"]), moved_x=bool(abs(on["d_x"]) > P["criteria"]["wind"]["onset_dx_m"]))
    return dict(measures=rows, onset=on, frames=dict(wind=sw["frame"], nowind=s0["frame"]))


def main(rid_w, rid_0, root="runs"):
    P = A.plan()
    rd_w = A.run_dir(rid_w, root); rd_0 = A.run_dir(rid_0, root)
    cfg_w = json.load(open(os.path.join(rd_w, "cfg.json"), encoding="utf8")); cfg_0 = json.load(open(os.path.join(rd_0, "cfg.json"), encoding="utf8"))
    # 静かな水面：計画 N1（風の計算は形の本番の値）。g44_analyze.still_offset と同じ決まり（2026-10-12 確かめ F1 の直し）
    off, off_info = A.still_offset(cfg_w, A.load_hf(rd_w), root)
    a0 = json.load(open(os.path.join(rd_0, "ana.json"), encoding="utf8"))
    t0 = cfg_w["parms"]["wind_t0"]
    CA = A.crest_analysis(rd_w, cfg_w, off, t_from=t0 - 0.5)
    m = A.main_event(CA["events"]) if CA else None
    cbf = {p[0]: (p[1] + cfg_w["parms"]["x_p"], p[2]) for p in m["path"]} if m else {}
    out = dict(wind=rid_w, nowind=rid_0, still_offset_m=off, still_offset_source=off_info, q_Pa=cfg_w["parms"]["wind_q"], form=cfg_w["case"].get("form"))
    if m is None:
        out["W6_note_ja"] = "風ありの計算に主な頂がないので、W6 の点を選べない"
    out["W6"] = w6(rd_w, cfg_w, off, cbf)
    if a0.get("onset"):
        out["W8"] = w8(rd_w, cfg_w, rd_0, cfg_0, off, t0, a0["onset"]["t"])
    else:      # 2026-10-12 確かめ F1：風なしの計算に巻き始めがない時は止まらずに理由を書く（本番は形の本番に巻き始めがなければ g44_queue が止める）
        out["W8"] = dict(rows=[], at_nowind_onset=None, includes_pre_onset_effect=None, gauges={},
                         skipped_ja="風なしの計算 %s の ana.json に主な巻き波の巻き始めがないので、W8 の終わりの時刻が決まらない" % rid_0)
    try:
        out["W1_5"] = w1_5(rid_w, rid_0, root, P)
    except Exception as e:
        out["W1_5"] = dict(error=repr(e)[:300])
    json.dump(out, open(os.path.join(rd_w, "wind_check.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    return out


if __name__ == "__main__":
    o = main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "runs")
    print("W6", o["W6"]["pass_"], o["W6"]["frames"], "bad", o["W6"]["frames_bad"][:10])
    print("W8", o["W8"]["at_nowind_onset"], o["W8"]["includes_pre_onset_effect"])
    if "measures" in o.get("W1_5", {}):
        for r in o["W1_5"]["measures"]:
            print(r.get("key"), r.get("delta"), r.get("moved"), r.get("toward_print"), r.get("share_of_remaining"), r.get("no_share_reason"))
        print("onset", o["W1_5"]["onset"])
