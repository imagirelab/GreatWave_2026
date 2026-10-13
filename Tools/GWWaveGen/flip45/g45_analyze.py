# -*- coding: utf-8 -*-
"""FLIP45：3D の計算の記録を読む（py -3.10、numpy・scipy・scikit-image）。計画 plan_ja.md §6 の読み方。
FLIP44 の g44_analyze.py（変えていない）の読み方を 3D の記録に広げて新しく書いた（計画 §10.1）。
  N1 静かな水面のずれ：計算の中で測った値（g45_run.py の still_offset_online。t0 + 0.5〜2.0 s の η_top の中央値、x ≥ n1_x_min）。
     記録にない時はここで同じ決まりで出す。途中保存から始めた計算（M1h）は元の計算の値（cfg の still_offset_m・still_offset_from）を使い、
     どこから読んだかを書く（FLIP44 の D1。煙の試し S9）。
  N2 水面の見張り（記録の止まり方）、N3 入口の振幅と位相（立ち上げの後 21 s から 3 T の窓 3 つ、線形の目標と比べる）、
  N4 進む速さ（記録）、N5 線形からの離れ（記録）、N8 小刻みの上限に届いたコマ、N10 伝わる間の減り（x 130 m ÷ x 40 m、窓 35〜56 s。読み方 R11）、
  N11 長い波（周期 20 s より長い動き）、N12 帯に近い。
  §6.1 巻き始め（y = 0 の断面で前の面の弦が初めて 90° 以上）・xc・Ac・H1・ℓ・tBP・同じ頂・前へ巻く（見直し M10）・着水、
  §6.5 L-a〜L-e（g45_crest3d.py）、§6.8 窓の前提（V1 の x 130 m）。
  巻かなかった時は、最も険しくなったコマ（FLIP42 の読み方 10）の同じ量を出す。
2026-10-12 12:48〜12:57 に足した物（別の者の確かめ check_ja.md の F1・F3。判定の幅は変えていない。どれも記録で、判定にしない）：
  - 線形の目標（N3・N5・N10・線形からの先行き）は、その計算の表と同じ立ち上げ（cfg の table.ramp。V3 だけ tanh_s）で作る。
  - mean_level_series：平均の水面の時系列。R1 から 5 つの所（箱の全部・入口の帯・内側・横の帯・出口の帯）の η_top の平均 − 静かな水面のずれを
    毎コマ出し、R6 に記録があれば水の格子の体積と粒子の数（g45_run.py の lvl_reg・liq_reg・preg）を並べる。周期ごとの平均、上がりが止まった時刻、
    先に上がった所、粒子の数と水の体積の増え方の比を書く（どこで水の量が増えるか：帯の流速の寄せ方か、粒子の補いか）。毎コマの値は
    <run>/mean_level_series.npz。
  - second_reading_mean_level：Ac・H1 の二つ目の読み。巻き始め（なければ最も険しいコマ）の前の 1 周期 [t − T, t) の内側の箱の周期の平均の水面
    （静かな水面のずれ N1 を引いた後）を水面とし、Ac2 = Ac − その値。H1 は頂と後ろの谷の差なので変わらない。偏り（Ac − Ac2）を書く。
    計画 §6.1 の判定は N1 から測った Ac のまま。
使い方：py -3.10 g45_analyze.py <run_id> [runs|smoke] [--quick]   → <置き場所>/<run_id>/ana.json
"""
import sys, os, json, glob, math, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g45_common as GC
import g45_crest3d as C3

FPS = GC.FPS
T = GC.T
LAM = GC.L0
OM = GC.OM


class AnalysisInputError(ValueError):
    pass


def run_dir(rid, root="runs"):
    return os.path.join(GC.B45, root, rid).replace("\\", "/")


def blocks(rd, kind):
    """記録のブロックを読み、コマ → (起動の始め, ファイル, 番号)。同じコマは後の起動の物。"""
    best = {}
    for p in sorted(glob.glob(os.path.join(rd, "%s_c*_b*.npz" % kind))):
        c0 = int(os.path.basename(p).split("_c")[1].split("_")[0])
        d = np.load(p)
        for i, f in enumerate(d["frames"]):
            f = int(f)
            if f not in best or best[f][0] <= c0:
                best[f] = (c0, p, i)
    return best


class Reader:
    """記録の 1 種類（hf・r2・r3・r4）をコマで読む（ファイルを一つずつ覚える）。"""

    def __init__(self, rd, kind, key="eta"):
        self.b = blocks(rd, kind); self.key = key; self._p = None; self._d = None
        self.frames = sorted(self.b)

    def get(self, f, key=None):
        c0, p, i = self.b[f]
        if p != self._p:
            d = np.load(p)
            self._d = {k: d[k] for k in d.files}; self._p = p
            self._meta = json.loads(str(self._d["meta"]))
        return self._d[key or self.key][i], self._meta, float(self._d["t"][i])


def records(rd):
    recs = []
    for p in sorted(glob.glob(os.path.join(rd, "run_c*.json"))):
        recs.append(json.load(open(p, encoding="utf8")))
    return recs


def still_offset(rd, cfg, recs, R1):
    """N1。返り値 (値, 出所)。"""
    if cfg.get("still_offset_m") is not None:
        return float(cfg["still_offset_m"]), "cfg（途中保存から始めた計算：元の計算 %s の値）" % cfg.get("still_offset_from")
    for r in recs:
        o = (r.get("info") or {}).get("still_offset_online")
        if o and o.get("value") is not None:
            return float(o["value"]), "計算の中で測った値（run_c%05d の still_offset_online、%s）" % (int(r["f_start"]), o.get("window", o.get("source")))
    t_off = float(cfg["parms"]["t_off"])
    xmin = float(cfg.get("n1_x_min", cfg["parms"]["x0"]))
    vals = []
    for f in R1.frames:
        e, m, t = R1.get(f)
        if t_off + 0.5 - 1e-9 <= t <= t_off + 2.0 + 1e-9:
            xs = m["x0"] + m["dx"] * np.arange(m["res"][0])
            vals.append(float(np.nanmedian(e[:, xs >= xmin])))
    if not vals:
        raise AnalysisInputError("静かな水面の窓（t0 + 0.5〜2.0 s）の記録がない。途中保存から始めた計算なら cfg の still_offset_m が要る（計画 N1）")
    return float(np.median(vals)), "記録の t0 + 0.5〜2.0 s から出した（x ≥ %g m）" % xmin


def gauges(R1, pts, t_lo=None, t_hi=None):
    """一番上の水面の高さを点 (x, y) で（格子の中心の間は線形の補間）。返り値 (t, η[点, t])。"""
    tt, ee = [], []
    for f in R1.frames:
        e, m, t = R1.get(f)
        if (t_lo is not None and t < t_lo - 1e-9) or (t_hi is not None and t > t_hi + 1e-9):
            continue
        xs = m["x0"] + m["dx"] * np.arange(m["res"][0]); zs = m["z0"] + m["dz"] * np.arange(m["res"][2])
        row = []
        for (x, y) in pts:
            fx = np.clip((x - xs[0]) / m["dx"], 0, len(xs) - 1.000001); ix = int(fx); wx = fx - ix
            fz = np.clip((y - zs[0]) / m["dz"], 0, len(zs) - 1.000001); iz = int(fz); wz = fz - iz
            row.append((1 - wz) * ((1 - wx) * e[iz, ix] + wx * e[iz, ix + 1]) + wz * ((1 - wx) * e[iz + 1, ix] + wx * e[iz + 1, ix + 1]))
        tt.append(t); ee.append(row)
    return np.array(tt), np.array(ee).T if ee else np.zeros((len(pts), 0))


def harm(t, e, om=OM):
    if len(t) < 10:
        return None
    M = np.stack([np.ones_like(t), np.cos(om * t), np.sin(om * t)], 1)
    c, *_ = np.linalg.lstsq(M, e, rcond=None)
    return dict(amp=float(math.hypot(c[1], c[2])), phase=float(math.atan2(c[2], c[1])), mean=float(c[0]))


def lin_series(case, pts, t_lo, t_hi, ramp_kind="tanh"):
    import g45_inlet_table as IT
    ts = np.round(np.arange(max(t_lo, -2.0), t_hi + 1e-9, 0.1) / 0.1) * 0.1
    return ts, IT.series_at(case, pts, ts, ramp_kind=ramp_kind)


def compare_windows(R1, case, pts, windows, off, ramp_kind="tanh"):
    """点ごと・窓ごとに、FLIP と線形の目標の周期 7 s の成分を比べる。返り値 [{x, y, windows: [{t, ratio, dphase}]}]。"""
    out = []
    t_all, E = gauges(R1, pts)
    if len(t_all) == 0:
        return out
    windows = [w for w in windows if w[1] > w[0] and w[0] >= t_all.min() - 1e-6 and w[1] <= t_all.max() + 1e-6]   # 記録の中に入る窓だけ
    if not windows:
        return [dict(x=x, y=y, windows=[], note="記録の時間の中に窓がない") for (x, y) in pts]
    tl, L = lin_series(case, pts, min(w[0] for w in windows), max(w[1] for w in windows), ramp_kind)
    for ip, (x, y) in enumerate(pts):
        ws = []
        for (a, b) in windows:
            m = (t_all >= a - 1e-9) & (t_all <= b + 1e-9)
            if m.sum() < 0.8 * (b - a) * FPS:
                continue
            hf = harm(t_all[m], E[ip][m] - off)
            ml = (tl >= a - 1e-9) & (tl <= b + 1e-9)
            hl = harm(tl[ml], L[ip][ml])
            if hf is None or hl is None or hl["amp"] < 1e-6:
                continue
            dph = (hf["phase"] - hl["phase"] + math.pi) % (2 * math.pi) - math.pi
            ws.append(dict(t=[a, b], amp=hf["amp"], amp_lin=hl["amp"], ratio=hf["amp"] / hl["amp"], dphase=dph, mean=hf["mean"]))
        out.append(dict(x=x, y=y, windows=ws))
    return out


def crest_events(R2, off, vox, t_from, x_lo, x_hi, t_off):
    rows = {}
    for f in R2.frames:
        sdf, m, t = R2.get(f)
        if t < t_from - 1e-9:
            continue
        cr, _ = C3.frame_crests(sdf, m, off, vox, LAM, x_lo=x_lo - 0.5 * LAM, x_hi=x_hi + 0.5 * LAM)
        for r in cr:
            r["t"] = t
        rows[f] = cr
    tracks = C3.track_crests(rows, R2.get(R2.frames[0])[1]["dx"]) if rows else []
    ev = []
    for tr in tracks:
        if len(tr) < 3:
            continue
        on = None; emax = -1e9; f_emax = None; steep = (-1.0, None)
        for f, r in tr:
            if np.isfinite(r["thmax"]) and r["thmax"] > steep[0] and x_lo <= r["xc"] <= x_hi:
                steep = (r["thmax"], dict(frame=f, t=r["t"], xc=r["xc"], eta_c=r["eta"], H=r["H"], H1=r["H1"], thmax=r["thmax"]))
            if on is None:
                if r["eta"] > emax:
                    emax, f_emax = r["eta"], f
                if np.isfinite(r["thmax"]) and r["thmax"] >= 90.0 and x_lo <= r["xc"] <= x_hi:
                    on = dict(frame=f, t=r["t"], xc=r["xc"], x_vert=r["x_vert"], eta_c=r["eta"], H=r["H"], H1=r["H1"], thmax=r["thmax"],
                              trough_back=r["trough_back"], trough_front=r["trough_front"])
        ev.append(dict(first_frame=tr[0][0], last_frame=tr[-1][0], x_first=tr[0][1]["xc"], x_last=tr[-1][1]["xc"], eta_max_pre_onset=emax,
                       onset=on, steepest=steep[1], n=len(tr), path=[[int(f), round(r["xc"], 3), round(r["eta"], 3)] for f, r in tr][:4000]))
    return ev


def plunge_after(R2, ev, off, vox, t_end):
    """巻き始めの後、止まるまでに §6.1 の「前へ巻く」が起きたか。最初に起きたコマ（着水）と理由。"""
    on = ev["onset"]
    path = {int(f): x for f, x, e in ev["path"]}
    for f in R2.frames:
        if f < on["frame"]:
            continue
        sdf, m, t = R2.get(f)
        if t > t_end + 1e-9:
            break
        xc = path.get(f)
        cr, _ = C3.frame_crests(sdf, m, off, vox, LAM, x_lo=(xc - 10.0) if xc is not None else on["xc"] - 20.0,
                                x_hi=(xc + 10.0) if xc is not None else on["xc"] + 40.0)
        if not cr:
            continue
        c = max(cr, key=lambda r: r["eta"])
        xs = m["x0"] + m["dx"] * np.arange(sdf.shape[1]); ys = m["y0"] + m["dy"] * np.arange(sdf.shape[0]) - off
        pr = C3.plunge_rule(c, sdf.astype(np.float32), xs, ys, off, vox, LAM)
        if pr["plunge"]:
            return dict(frame=f, t=t, xc=c["xc"], by="cavity" if pr["a_cavity"] else "tip<=0 + overhang", rule=pr, cav=c["cav"], tip=c["tip"])
    return None


def jet_at(R2, f, off, xc):
    """L-d：着水の 0.25 s 前のコマの唇の先の水の速さの向き（y = 0）。"""
    if f not in R2.b:
        return None
    sdf, m, t = R2.get(f)
    cr, _ = C3.frame_crests(sdf, m, off, m["dx"], LAM, x_lo=xc - 15.0, x_hi=xc + 15.0)
    if not cr:
        return None
    c = max(cr, key=lambda r: r["eta"])
    if c["tip"] is None:
        return dict(frame=f, t=t, note="唇の先が読めない")
    u = R2.get(f, "u")[0].astype(np.float64); w = R2.get(f, "w")[0].astype(np.float64)
    mv = m.get("vel", {})
    xt, yt = c["tip"][0], c["tip"][1] + off

    def samp(arr, mm):
        if not mm:
            return float("nan")
        x0, y0 = mm["p0"][0], mm["p0"][1]; dx, dy = mm["d"][0], mm["d"][1]
        fx = (xt - x0) / dx; fy = (yt - y0) / dy
        i = int(np.clip(np.floor(fx), 0, arr.shape[1] - 2)); j = int(np.clip(np.floor(fy), 0, arr.shape[0] - 2))
        a = fx - i; b = fy - j
        return float((1 - b) * ((1 - a) * arr[j, i] + a * arr[j, i + 1]) + b * ((1 - a) * arr[j + 1, i] + a * arr[j + 1, i + 1]))
    uu = samp(u, mv.get("vel.x")); ww = samp(w, mv.get("vel.y"))
    if not (np.isfinite(uu) and np.isfinite(ww)):
        return dict(frame=f, t=t, tip=c["tip"], note="流速の記録が読めない")
    return dict(frame=f, t=t, tip=c["tip"], u=uu, w=ww, **C3.jet_angle(uu, ww))


def offaxis(rd, off, vox, f_from, f_to):
    """L-e：R4 で、どの y の断面でも前の面の弦が初めて 90° 以上になったコマと y・x（見直し M7）。L-b の材料も返す。"""
    R4 = Reader(rd, "r4", "sdf")
    if not R4.frames:
        return dict(note="R4 の記録がない")
    first = None; spans = {}
    for f in R4.frames:
        if f < f_from or f > f_to:
            continue
        a, m, t = R4.get(f)
        rows = C3.overturn_span(a.astype(np.float32), m, off, vox, LAM)
        over = [r for r in rows if np.isfinite(r[1]) and r[1] >= 90.0]
        spans[f] = rows
        if over and first is None:
            y, th, x, e = min(over, key=lambda r: r[0])
            first = dict(frame=f, t=t, y=y, x=x, eta=e, thmax=th, n_y_over90=len(over), y_list=[r[0] for r in over][:200])
    return dict(first=first, frames=[f_from, f_to], spans_kept=len(spans), _spans=spans)


def long_wave(t, e, off, t_hi, fcut=1.0 / 20.0):
    """N11：周期 20 s より長い水面の動きの振幅（巻き始めまで）。長さ T の移動平均を 2 回かけて周期 7 s の成分とその倍の成分を消した後の
    |η − 静かな水面| の最大（t0 + 2 T から）。移動平均の 2 回の通り具合は周期 20 s で 0.66 倍、40 s で 0.90 倍【計算】（記録の目安）。"""
    m = t <= t_hi + 1e-9
    if m.sum() < 3 * T * FPS:
        return None
    tt, ee = t[m], e[m] - off
    n = int(round(T * FPS))
    k = np.ones(n) / n
    lp = np.convolve(np.convolve(ee, k, mode="same"), k, mode="same")
    sel = (tt >= tt[0] + 2 * T) & (tt <= tt[-1] - T)
    return float(np.max(np.abs(lp[sel]))) if sel.any() else None


REGIONS = ["all", "inlet_band", "interior", "side_band", "exit_band"]


def _region_index(x, zl, in1, ex0, sd0):
    """g45_run.py の region_index と同じ：0 入口の帯（x < in1）・1 内側・2 横の帯（横 ≥ sd0）・3 出口の帯（x ≥ ex0）。"""
    return np.where(x < in1, 0, np.where(x >= ex0, 3, np.where(zl >= sd0, 2, 1)))


def _r6_regions(rd):
    """R6 の lvl_reg・liq_reg・preg（g45_run.py が 2026-10-12 から書く）をコマで。同じコマは後の起動の物。返り値 dict（なければ空）。"""
    best = {}
    vox = None
    for p in sorted(glob.glob(os.path.join(rd, "r6_c*.npz"))):
        c0 = int(os.path.basename(p).split("_c")[1].split(".")[0])
        d = np.load(p)
        if "liq_reg" not in d.files:
            continue
        vox = float(d["vox"]) if "vox" in d.files else vox
        for i, f in enumerate(d["frames"]):
            f = int(f)
            if i < len(d["liq_reg"]) and (f not in best or best[f][0] <= c0):
                best[f] = (c0, d["lvl_reg"][i], d["liq_reg"][i], d["preg"][i])
    return dict(rows=best, vox=vox)


def _trailing_mean(t, v, width):
    """t の昇順の列で、(t − width, t] の平均（NaN は除く）。"""
    out = np.full(len(t), np.nan)
    j = 0
    for i in range(len(t)):
        while t[j] <= t[i] - width + 1e-9:
            j += 1
        w = v[j:i + 1]
        w = w[np.isfinite(w)]
        if len(w):
            out[i] = float(w.mean())
    return out


def level_series(rd, R1, P, off, t_off):
    """平均の水面の時系列（2026-10-12 に足した。check_ja.md §3.2・F3。記録で、判定にしない）。返り値 dict（ana.json に入れる要約）。
    毎コマの値は <rd>/mean_level_series.npz（t・frames・level[コマ, 5]（η_top の平均 − 静かな水面のずれ）・liq_m3[コマ, 5]・particles[コマ, 5]）。"""
    in1, ex0, sd0 = float(P["in1"]), float(P["ex0"]), float(P["sd0"])
    x_st = np.arange(in1 + 4.0, ex0 - 4.0 + 1e-9, 30.0)          # 上がりの前線を見る x（内側の横 0〜sd0 の平均、x ± 2 m）
    fr, tt, lv, area, lx = [], [], [], None, []
    for f in R1.frames:
        e, m, t = R1.get(f)
        xs_ = m["x0"] + m["dx"] * np.arange(m["res"][0]); zs_ = m["z0"] + m["dz"] * np.arange(m["res"][2])
        ri = _region_index(xs_[None, :], zs_[:, None], in1, ex0, sd0)
        row = [float(np.nanmean(e)) - off if np.isfinite(e).any() else np.nan]
        ar = [e.size * m["dx"] * m["dz"]]
        for k in range(4):
            v = e[ri == k]
            row.append(float(np.nanmean(v)) - off if v.size and np.isfinite(v).any() else np.nan)
            ar.append(float((ri == k).sum()) * m["dx"] * m["dz"])
        lat = zs_ < sd0
        srow = []
        for xq in x_st:
            v = e[np.ix_(lat, np.abs(xs_ - xq) <= 2.0 + 1e-9)]
            srow.append(float(np.nanmean(v)) - off if v.size and np.isfinite(v).any() else np.nan)
        fr.append(f); tt.append(t); lv.append(row); area = ar; lx.append(srow)
    fr = np.array(fr); tt = np.array(tt); lv = np.array(lv); lx = np.array(lx).reshape(len(fr), len(x_st))
    r6 = _r6_regions(rd)
    vox = r6["vox"] or 2.0 * float(P["dp"])
    liq = np.full(lv.shape, np.nan); prt = np.full(lv.shape, np.nan); lvl_run = np.full(lv.shape, np.nan)
    for i, f in enumerate(fr):
        r = r6["rows"].get(int(f))
        if r is not None:
            lvl_run[i] = np.asarray(r[1], float) - off
            liq[i] = np.asarray(r[2], float) * vox ** 3
            pr = np.asarray(r[3], float); pr[pr < 0] = np.nan
            prt[i] = pr
    np.savez(os.path.join(rd, "mean_level_series.npz"), t=tt, frames=fr, level=lv, liq_m3=liq, particles=prt, regions=np.array(REGIONS),
             area_m2=np.array(area if area else [np.nan] * 5), still_offset=np.array(off), x_stations=x_st, level_x=lx)
    out = dict(regions=REGIONS, area_m2=[round(a, 1) for a in area] if area else None, n_frames=int(len(fr)),
               source_level="R1（毎コマの η_top。帯を含む全領域）", source_liq_particles=("R6（g45_run.py の liq_reg・preg）" if np.isfinite(liq).any() else "なし（2026-10-12 より前の記録）"),
               note_ja="η_top の平均 − 静かな水面のずれ（m）。所：箱の全部・入口の帯（x < %g）・内側・横の帯（横 ≥ %g）・出口の帯（x ≥ %g）。記録で、判定にしない" % (in1, sd0, ex0))
    if np.isfinite(lvl_run).any():
        ok = np.isfinite(lvl_run[:, 0]) & np.isfinite(lv[:, 0])
        out["check_run_vs_R1_maxdiff_m"] = float(np.max(np.abs(lvl_run[ok] - lv[ok]))) if ok.any() else None
    # 周期ごとの平均（t_off から T ごと。0.9 T 以上のコマがある周期だけ）
    kper = np.floor((tt - t_off) / T).astype(int)
    per = []
    for q in sorted(set(kper.tolist())):
        sel = kper == q
        if sel.sum() < 0.9 * T * FPS:
            continue
        row = dict(t0=round(t_off + q * T, 2), t1=round(t_off + (q + 1) * T, 2), level=[round(float(np.nanmean(lv[sel, k])), 4) for k in range(5)])
        if np.isfinite(liq[sel]).any():
            row["liq_m3"] = [round(float(np.nanmean(liq[sel, k])), 1) for k in range(5)]
        if np.isfinite(prt[sel]).any():
            row["particles"] = [int(np.nanmean(prt[sel, k])) if np.isfinite(prt[sel, k]).any() else None for k in range(5)]
        per.append(row)
    out["per_period"] = per
    if not per:
        out["note_short"] = "1 周期より短い記録"
        return out
    # 上がりの大きさと止まった時刻（箱の全部の周期の平均）
    allp = np.array([r["level"][0] for r in per])
    last = float(allp[-1]); top = float(np.nanmax(allp))
    out["rise_whole_box_last_period_m"] = round(last, 4)
    out["rise_whole_box_max_period_m"] = round(top, 4)
    if top > 0.02:
        i90 = int(np.where(allp >= 0.9 * top)[0][0])
        out["rise_reaches_90pct_in_period"] = [per[i90]["t0"], per[i90]["t1"]]
    else:
        out["rise_reaches_90pct_in_period"] = None
    # 先に上がった所：1 周期の後ろ向きの移動平均が、箱の全部の最後の周期の上がりの半分を初めて越えた時刻
    thr = 0.5 * last
    first = {}
    if last > 0.02:
        for k, nm in enumerate(REGIONS):
            tm = _trailing_mean(tt, lv[:, k], T)
            hit = np.where((tt >= t_off + T - 1e-9) & (tm >= thr))[0]
            first[nm] = round(float(tt[hit[0]]), 2) if len(hit) else None
        order = sorted([(v, k) for k, v in first.items() if v is not None and k != "all"])
        out["first_above_half_rise"] = dict(threshold_m=round(thr, 4), t_by_region=first, order=[k for v, k in order],
                                            note_ja="1 周期の後ろ向きの移動平均が、箱の全部の最後の周期の上がりの半分を初めて越えた時刻（t0 + T から）")
    else:
        out["first_above_half_rise"] = dict(note_ja="箱の全部の上がりが 0.02 m 以下なので読まない")
    # 水の体積と粒子の数の増え方（R6 の記録がある時）
    # 始めの値は N1 と同じ窓 t0 + 0.5〜2.0 s（1 コマ目の水面の場は始めの形で、水の格子が多く出る【測った：fix1012 の S1_runrec】）
    base = (tt >= t_off + 0.5 - 1e-9) & (tt <= t_off + 2.0 + 1e-9)
    if np.isfinite(liq[:, 0]).any() and np.isfinite(liq[base, 0]).any():
        selL = kper == max(kper[np.isfinite(liq[:, 0])])
        V0 = np.nanmean(liq[base], axis=0); V1 = np.nanmean(liq[selL], axis=0)
        out["liquid_volume_change"] = dict(t_base=[round(t_off + 0.5, 2), round(t_off + 2.0, 2)],
                                           last_period=[round(float(tt[selL].min()), 2), round(float(tt[selL].max()), 2)],
                                           dV_m3=[round(float(v), 1) for v in (V1 - V0)], dV_over_V=[float(v) for v in (V1 - V0) / np.maximum(V0, 1e-9)],
                                           dV_as_level_m=[round(float(v), 4) for v in (V1 - V0) / np.array(area)],
                                           note_ja="水面の場が負の格子の体積（t0 + 0.5〜2.0 s の平均と最後の周期の平均の差）。dV_as_level_m は所の面積で割った水面の高さ")
    okp = np.where(np.isfinite(prt[:, 0]) & (tt >= t_off + 0.5 - 1e-9))[0]
    if len(okp) >= 2:
        N0 = prt[okp[0]]; N1 = prt[okp[-1]]
        dN = (N1 - N0) / np.maximum(N0, 1)
        out["particle_count_change"] = dict(t=[round(float(tt[okp[0]]), 2), round(float(tt[okp[-1]]), 2)], N_first=[int(v) for v in N0],
                                            N_last=[int(v) for v in N1], dN_over_N=[float(v) for v in dN],
                                            note_ja="粒子の数の増えは、波の中の粒子の補いで水の量と関わりなく起きうる（煙の試しで 1.11〜1.16 倍）。"
                                                    "水の体積の増え（liquid_volume_change）と所ごと・時刻ごとに並べて見る")
    # 上がりの前線（内側の x ごと）：1 周期の後ろ向きの移動平均が thr を初めて越えた時刻を x で並べ、速さを一次の合わせで出す。
    # 入口の帯から浅い水の速さ √(g h)（14.0 m/s）で広がれば入口の帯の中の源、群の速さ（6.24 m/s）で広がれば波の中で起きる物と読む【考え】
    fr_ = dict(x=[float(v) for v in x_st], t_cross=[], threshold_m=round(thr, 4) if last > 0.02 else None,
               c_shallow=round(math.sqrt(GC.G * GC.D), 2), c_group=round(GC.CG0, 2))
    if last > 0.02:
        for j in range(len(x_st)):
            tm = _trailing_mean(tt, lx[:, j], T)
            hit = np.where((tt >= t_off + T - 1e-9) & (tm >= thr))[0]
            fr_["t_cross"].append(round(float(tt[hit[0]]), 2) if len(hit) else None)
        pts_ = [(x, t) for x, t in zip(fr_["x"], fr_["t_cross"]) if t is not None]
        if len(pts_) >= 3:
            xx = np.array([p[0] for p in pts_]); tq = np.array([p[1] for p in pts_])
            if np.ptp(tq) > 1e-6:
                sl = np.polyfit(tq, xx, 1)[0]
                fr_["speed_m_s"] = round(float(sl), 2)
        sp = fr_.get("speed_m_s")
        order = (out.get("first_above_half_rise") or {}).get("order") or []
        inlet_first = bool(order) and order[0] == "inlet_band"
        if sp is None:
            hint = "前線の速さが出ない（越えた x が 3 つより少ないか、同じ時刻に越えた）：出所は分けられない"
        elif sp >= 40.0:
            hint = "上がりはほぼ同時に起きた（%.1f m/s）：一つの所の源ではなく全体で起きる物（粒子の補い・水面の作り方）の見込み【考え】" % sp
        elif sp >= 10.0 and inlet_first:
            hint = ("入口の帯が先に上がり、群の速さ（%.1f m/s）より速く %.1f m/s で内へ広がった：入口の帯の中の源（帯の流速の寄せ方）の見込み【考え】。"
                    "浅い水の速さ %.1f m/s より速く見えるのは、源が強まりながら長い波を出し続けると、決まった高さを越える時刻の並びが速く見えるため【考え】"
                    % (GC.CG0, sp, math.sqrt(GC.G * GC.D)))
        elif sp >= 10.0:
            hint = "上がりは長い波の速さ（%.1f m/s）で広がったが、入口の帯が先ではない：出所は分けられない" % sp
        elif 4.0 <= sp <= 8.5:
            hint = "上がりは波の群の速さ（%.1f m/s）で広がった：波の中で起きる物（粒子の補い・水面の作り方）の見込み【考え】" % sp
        else:
            hint = "前線の速さ %.1f m/s は浅い水の速さとも群の速さとも違う：出所は分けられない" % sp
        out["origin_hint_ja"] = "%s。先に上がった所の並び：%s" % (hint, "・".join(order) or "読まない")
    else:
        out["origin_hint_ja"] = "箱の全部の上がりが 0.02 m 以下なので出所は読まない"
    out["rise_front"] = fr_
    return out


def second_reading(out, R1, P, off, t_off):
    """Ac・H1 の二つ目の読み（2026-10-12 に足した。record_ja.md §8 の 2 の (a)、check_ja.md §3.2。記録で、判定にしない）。
    巻き始め（なければ最も険しいコマ）の前の 1 周期 [t − T, t) の、内側の箱（入口の帯の内の縁 + 4 m 〜 出口の帯の内の縁 − 4 m、
    横 0〜横の帯の内の縁 − 2 m。mean_level_rise と同じ箱）の η_top の平均 − 静かな水面のずれを水面 δ とし、Ac2 = Ac − δ。
    H1 は頂 − 後ろの谷なので δ で変わらない。並べて、箱の全部と頂のまわり（xc ± λ、横 0〜20 m）の同じ平均も書く。"""
    ev = out.get("onset"); kind = "onset"
    if not ev:
        ev = out.get("steepest"); kind = "steepest"
    if not ev:
        return dict(note_ja="巻き始めも最も険しいコマもないので読まない")
    t1 = float(ev["t"]); t0 = t1 - T; xc = float(ev["xc"])
    in1, ex0, sd0 = float(P["in1"]), float(P["ex0"]), float(P["sd0"])
    boxes = dict(interior=(in1 + 4.0, ex0 - 4.0, 0.0, sd0 - 2.0), whole=(-1e9, 1e9, -1e9, 1e9), crest=(xc - LAM, xc + LAM, 0.0, 20.0))
    acc = {k: [] for k in boxes}
    n = 0
    for f in R1.frames:
        e, m, t = R1.get(f)
        if not (t0 - 1e-9 <= t < t1 - 1e-9):
            continue
        n += 1
        xs_ = m["x0"] + m["dx"] * np.arange(m["res"][0]); zs_ = m["z0"] + m["dz"] * np.arange(m["res"][2])
        for k, (a0, a1, b0, b1) in boxes.items():
            sel = e[np.ix_((zs_ >= b0) & (zs_ <= b1), (xs_ >= a0) & (xs_ <= a1))]
            if sel.size and np.isfinite(sel).any():
                acc[k].append(float(np.nanmean(sel)) - off)
    res = dict(kind=kind, t=t1, window=[round(t0, 3), round(t1, 3)], n_frames=n, xc=xc)
    if n < 0.9 * T * FPS:
        res["note_ja"] = "巻き始めの前の 1 周期の記録が足りない（%d コマ）。読まない" % n
        return res
    lev = {k: (float(np.mean(v)) if v else None) for k, v in acc.items()}
    d = lev["interior"]
    Ac = float(ev["eta_c"]); H1 = ev.get("H1")
    res.update(level_m=dict(interior=d, whole=lev["whole"], crest=lev["crest"]),
               Ac_N1_m=Ac, Ac_second_m=(Ac - d) if d is not None else None, Ac_bias_m=d, Ac_bias_rel=(d / Ac) if (d is not None and Ac) else None,
               H1_N1_m=H1, H1_second_m=H1,
               note_ja="二つ目の読み：水面 = 巻き始めの前の 1 周期の内側の箱の周期の平均（N1 を引いた後）。Ac2 = Ac − 水面、偏り = Ac − Ac2。"
                       "H1 は頂と後ろの谷が同じだけ動くので変わらない。計画 §6.1 の判定は N1 から測った Ac のまま（この読みは並べて書く物）")
    rep_ = out.get("reproduction")
    if rep_ and d is not None and "Ac_m" in rep_.get("rows", {}):
        band = rep_["rows"]["Ac_m"]["band"]
        res["Ac_second_inside_band_record_only"] = bool(band[0] <= Ac - d <= band[1])
    return res


def analyze(rid, root="runs", quick=False):
    rd = run_dir(rid, root)
    cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    recs = records(rd)
    if not recs:
        raise AnalysisInputError("起動の記録 run_c*.json がない")
    P = cfg["parms"]; vox = 2 * float(P["dp"]); t_off = float(P["t_off"])
    case = (cfg.get("case") or {}).get("name") or (cfg["table"]["target"] if isinstance(cfg["table"]["target"], str) else None)
    ramp_kind = (cfg.get("table") or {}).get("ramp", "tanh")       # 線形の目標の立ち上げ（その計算の表と同じ。V3 だけ tanh_s）
    R1 = Reader(rd, "hf", "eta"); R2 = Reader(rd, "r2", "sdf")
    if not R1.frames:
        raise AnalysisInputError("R1 の記録がない")
    off, off_src = still_offset(rd, cfg, recs, R1)
    plan = GC.load_plan()
    x0 = float(P["x0"]); in1 = float(P["in1"]); ex0 = float(P["ex0"])
    t_end = max(R1.get(R1.frames[-1])[2], 0.0)
    out = dict(run_id=rid, root=root, date=time.strftime("%Y-%m-%d %H:%M:%S"), dp=P["dp"], case=case, layout=(cfg.get("case") or {}).get("layout"),
               t_off=t_off, frames=[R1.frames[0], R1.frames[-1]], t_range=[R1.get(R1.frames[0])[2], t_end],
               still_level_offset_m=off, still_offset_source=off_src, checkpoint_started=bool(cfg.get("still_offset_from") or cfg.get("from_ckpt")),
               ramp=ramp_kind)
    # 止まり方・小刻み・費用（N2・N8・R6）
    stops = [r.get("stopped") for r in recs]
    out["stops"] = stops
    out["N2_guard"] = [s for s in stops if s and s.startswith(("free_fall", "no water", "error"))]
    ss = []
    walls = []; npts = []
    for p in sorted(glob.glob(os.path.join(rd, "r6_c*.npz"))):
        d = np.load(p)
        ss += [int(v) for v in d["ss_n"] if v >= 0]
        walls += list(d["wall"][1:]); npts += [int(v) for v in d["npts"] if v > 0]
    out["N8_frames_at_max_substeps"] = int(sum(1 for v in ss if v >= int(P["maxsub"])))
    out["cost"] = dict(s_per_frame_median=float(np.median(walls)) if walls else None, particles_max=max(npts) if npts else None,
                       us_per_particle_frame=(float(np.median(walls)) / max(npts) * 1e6) if walls and npts else None,
                       launches=len(recs), wall_total_h=sum(r.get("wall_launch_s", 0) for r in recs) / 3600.0,
                       rss_peak_gb=max(r.get("rss_peak_gb", 0) for r in recs))
    # 平均の水面の時系列（2026-10-12 に足した。記録）
    try:
        out["mean_level_series"] = level_series(rd, R1, P, off, t_off)
    except Exception as e:
        out["mean_level_series"] = dict(error=repr(e)[:300])
    if case is None:
        out["note"] = "試しの目標（例の名前なし）。例の読み（N3・N10・巻き始め）は出さない"
        json.dump(out, open(os.path.join(rd, "ana.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
        return out
    num = plan["criteria"]["numerics"]
    # N3（入口の振幅と位相）
    lay = out["layout"] or ""
    xs_in = num["inlet_points_x_L3"] if lay == "L3" else (num["inlet_points_x_L2"] if x0 > 0 else num["inlet_points_x_L1"])
    pts3 = [(float(x), float(y)) for x in xs_in for y in num["inlet_points_y"]]
    wins = [(21.0, 42.0), (42.0, 63.0), (63.0, 84.0)]
    out["N3"] = compare_windows(R1, case, pts3, [w for w in wins if w[1] <= t_end + 1e-9] or [(21.0, min(42.0, t_end))], off, ramp_kind)
    r3 = [w["ratio"] for p in out["N3"] for w in p["windows"]]
    ph3 = [w["dphase"] for p in out["N3"] for w in p["windows"]]
    out["N3_summary"] = dict(ratio_min=min(r3) if r3 else None, ratio_max=max(r3) if r3 else None,
                             dphase_absmax=max(abs(v) for v in ph3) if ph3 else None,
                             within_095_105=bool(r3 and all(0.95 <= v <= 1.05 for v in r3)),
                             within_preview_090_110=bool(r3 and all(0.90 <= v <= 1.10 for v in r3)),
                             phase_within_010=bool(ph3 and all(abs(v) <= 0.10 for v in ph3)))
    # N10・§6.8 の前提（造波板から解く窓だけ）
    if x0 == 0.0:
        w10 = [(35.0, 56.0)] if t_end >= 56.0 - 1e-9 else [(35.0, t_end)]
        c40 = compare_windows(R1, case, [(40.0, 0.0)], w10, off, ramp_kind)
        c130 = compare_windows(R1, case, [(130.0, 0.0), (130.0, 24.0), (130.0, 48.0)], w10, off, ramp_kind)
        try:
            n10 = c130[0]["windows"][0]["ratio"] / c40[0]["windows"][0]["ratio"]
        except (IndexError, KeyError):
            n10 = None
        out["N10"] = dict(window=w10[0], ratio_x130_over_x40=n10, pass_0975=(n10 is not None and n10 >= 0.975), x40=c40, x130=c130,
                          note_ja="窓 35〜56 s（3 T）。読み方 R11")
        pre = [w for p in c130 for w in p["windows"]]
        out["layout_precondition_6_8"] = dict(amp_within_3pct=bool(pre and all(abs(w["ratio"] - 1) <= 0.03 for w in pre)),
                                              phase_within_010=bool(pre and all(abs(w["dphase"]) <= 0.10 for w in pre)),
                                              values=[dict(y=p["y"], **p["windows"][0]) for p in c130 if p["windows"]])
    else:
        out["N10"] = dict(note_ja="窓 L2 では測れない（計画 N10）")
    # 焦点の近く（x 150〜300 m、L1x は 360 m まで）の y = 0 の頂の最大（§6.9 の (d)）
    xmax_f = 360.0 if float(P["Lx"]) + x0 > 400.0 else 300.0
    best = (-1e9, None, None)
    for f in R1.frames:
        e, m, t = R1.get(f)
        xs_ = m["x0"] + m["dx"] * np.arange(m["res"][0])
        sel = (xs_ >= 150.0) & (xs_ <= xmax_f)
        if sel.any() and np.isfinite(e[0, sel]).any():
            i = int(np.nanargmax(e[0, sel])); v = float(e[0, sel][i]) - off
            if v > best[0]:
                best = (v, float(xs_[sel][i]), t)
    out["focus_crest_max"] = dict(eta=best[0], x=best[1], t=best[2], x_range=[150.0, xmax_f],
                                  note_ja="y = 0 の格子の層の一番上の水面から静かな水面のずれを引いた値（§6.9 の (d)、5.1 m 以上）")
    # 平均の水面の上がり（記録。2026-10-12 の煙の試しで、帯から水が入り内側の平均の水面が 0.15〜0.3 m 上がると分かったため。読み方 R22）：
    # 内側の箱（入口の帯の内の縁 + 4 m 〜 出口の帯の内の縁 − 4 m、横 0〜横の帯の内の縁 − 2 m）と焦点の近く（x 180〜240 m、横 0〜20 m）の、
    # 周期 T ごとの平均の η_top − 静かな水面のずれ
    boxes = dict(interior=(in1 + 4.0, ex0 - 4.0, 0.0, float(P["sd0"]) - 2.0), focus=(180.0, 240.0, 0.0, 20.0))
    acc = {k: {} for k in boxes}
    for f in R1.frames:
        e, m, t = R1.get(f)
        xs_ = m["x0"] + m["dx"] * np.arange(m["res"][0]); zs_ = m["z0"] + m["dz"] * np.arange(m["res"][2])
        kper = int(math.floor((t - t_off) / T))
        for k, (a0, a1, b0, b1) in boxes.items():
            sel = e[np.ix_((zs_ >= b0) & (zs_ <= b1), (xs_ >= a0) & (xs_ <= a1))]
            if sel.size and np.isfinite(sel).any():
                acc[k].setdefault(kper, []).append(float(np.nanmean(sel)) - off)
    out["mean_level_rise"] = {k: [dict(t0=round(t_off + q * T, 2), t1=round(t_off + (q + 1) * T, 2), mean=round(float(np.mean(v)), 4))
                                  for q, v in sorted(acc[k].items()) if len(v) >= 0.9 * T * FPS] for k in boxes}
    out["mean_level_rise_note_ja"] = ("周期ごとの平均の η_top − 静かな水面のずれ（m）。0 から離れるのは閉じた箱の水の量の増え（2026-10-12 の別の者の確かめ "
                                      "check_ja.md §3.2。出所の読みは mean_level_series の origin_hint_ja）。記録で、判定にしない")
    # N9（設定の確かめ）：計算に入れた t0 が計画の値と同じ
    pr = (cfg.get("case") or {}).get("plan_run") or {}
    if pr:
        t0_plan = pr.get("t0_s")
        is_h = str(rid).startswith(("M1h",))
        out["N9"] = dict(t_off=t_off, plan_t0=t0_plan, same=(True if is_h else bool(abs(t_off - float(t0_plan)) < 1e-9)),
                         note_ja="M1h は元の計算（M1）と同じ t0 で、途中保存から始める" if is_h else "")
    # N4（記録）：y = 0 の x 50〜150 m で、群の前を行く頂の速さ（振幅が格子の 2 倍に届かない頂は使わない）
    try:
        rows = {}
        for f in R1.frames:
            e, m, t = R1.get(f)
            xs_ = m["x0"] + m["dx"] * np.arange(m["res"][0])
            line = e[0] - off
            sel = (xs_ >= 50.0) & (xs_ <= 150.0)
            xl = xs_[sel]; el = np.nan_to_num(line[sel], nan=-99.0)
            pk = [i for i in range(1, len(el) - 1) if el[i] >= el[i - 1] and el[i] > el[i + 1] and el[i] >= 2.0 * vox]
            rows[f] = [dict(xc=float(xl[i]), eta=float(el[i]), t=t) for i in pk]
        trs = C3.track_crests(rows, m["dx"])
        sp = []
        for tr in trs:
            if len(tr) >= 24:
                tt_ = np.array([r["t"] for _, r in tr]); xx_ = np.array([r["xc"] for _, r in tr])
                sp.append(float(np.polyfit(tt_, xx_, 1)[0]))
        out["N4"] = dict(n_crests=len(sp), speed_median=float(np.median(sp)) if sp else None, speeds=sp[:20], c_linear=GC.C0,
                         note_ja="y = 0 の x 50〜150 m、1 s 以上続いた頂の x を時刻で一次に合わせた速さ（記録）")
    except Exception as e:
        out["N4"] = dict(error=repr(e)[:200])
    # N5（記録）
    out["N5"] = compare_windows(R1, case, [(50.0, 0.0), (100.0, 0.0), (150.0, 0.0)],
                                [w for w in [(28.0, 49.0)] if w[1] <= t_end + 1e-9], off, ramp_kind)
    # 巻き始め（y = 0 の断面）
    if not R2.frames:
        out["onset"] = None; out["note_onset"] = "R2 の記録がない"
    else:
        t_from = float((cfg.get("stop_touchdown") or {}).get("t_from", t_off + 2.0))
        ev = crest_events(R2, off, vox, t_from, in1 + 5.0, ex0, t_off)
        ons = [e for e in ev if e["onset"] is not None]
        main = min(ons, key=lambda e: e["onset"]["t"]) if ons else None
        out["events_n"] = len(ev)
        out["other_onsets"] = [dict(t=e["onset"]["t"], xc=e["onset"]["xc"], eta_c=e["onset"]["eta_c"]) for e in ons if e is not main][:20]
        if main is not None:
            on = main["onset"]
            out["onset"] = dict(on, frame=int(on["frame"]))
            # ℓ（同じコマの η_top）
            e1, m1, t1 = R1.get(on["frame"])
            xs = m1["x0"] + m1["dx"] * np.arange(m1["res"][0]); zs = m1["z0"] + m1["dz"] * np.arange(m1["res"][2])
            cw = C3.crest_width(e1 - off, xs, zs, on["xc"], 0.5 * on["eta_c"])
            lc = C3.crest_width(e1 - off, xs, zs, on["xc"], 0.7 * on["eta_c"])
            out["ell"] = cw; out["L_c_long_crest"] = lc
            # C3：前の面の険しさ（巻き始めの η_c ÷ 頂から前で静かな水面を切る所までの距離）
            sdf_on, m_on, _ = R2.get(on["frame"])
            _, top_on = C3.frame_crests(sdf_on, m_on, off, vox, LAM)
            xs_on = m_on["x0"] + m_on["dx"] * np.arange(sdf_on.shape[1])
            fw = np.where((xs_on > on["xc"]) & np.isfinite(top_on) & (top_on <= 0.0))[0] if top_on is not None else []
            if len(fw):
                dist = float(xs_on[fw[0]] - on["xc"])
                out["onset"]["front_steepness"] = on["eta_c"] / dist if dist > 0 else None
                out["onset"]["front_swl_x"] = float(xs_on[fw[0]])
            pl = plunge_after(R2, main, off, vox, t_end)
            out["plunge"] = pl
            if pl:
                xp_ = pl["tip"][0] if pl.get("tip") else (pl["cav"][0][0] if pl.get("cav") else pl["xc"])
                out["touchdown"] = dict(frame=int(pl["frame"]), t=pl["t"], xc=pl["xc"], x_point=xp_, by=pl["by"],
                                        jet_time_s=pl["t"] - on["t"], jet_dist_m=xp_ - on["xc"])
            else:
                out["touchdown"] = None
            if pl:
                out["L_d_jet"] = jet_at(R2, int(pl["frame"]) - 6, off, pl["xc"])
            # 論文との比べ（§6.1）
            bem = plan["bem_table1"].get(case)
            band = plan["criteria"]["reproduction"]["bands"].get(case)
            if bem and band:
                got = dict(xc_m=on["xc"], Ac_m=on["eta_c"], H1_m=on["H1"], ell_m=cw["width"], tBP_s=on["t"])
                rows = {k: dict(value=v, band=band[k], inside=bool(band[k][0] <= v <= band[k][1]), paper=bem[k], rel=v / bem[k] - 1.0)
                        for k, v in got.items() if v is not None and np.isfinite(v)}
                same = abs(on["t"] - bem["tBP_s"]) <= plan["criteria"]["reproduction"]["same_crest_dt_s"]
                out["reproduction"] = dict(rows=rows, same_crest=bool(same), plunge=bool(pl is not None),
                                           primary_all_inside=bool(all(rows[k]["inside"] for k in ("xc_m", "Ac_m", "H1_m", "ell_m") if k in rows)),
                                           coarse=bool(float(P["dp"]) > 0.25 + 1e-9))
            # §6.2 の記録：線形からの先行き（tBP の FLIP の頂の x − 同じ時刻の壁ありの線形の y = 0 のいちばん高い頂の x）と、
            # 頂の下の水平の速さ（R2 の u を x = xc の縦の線で：頂の上の端・z = 0・海底の近く。論文の図 16 は 11.1・3.9・1.1 m/s）
            try:
                import g45_inlet_table as IT
                xl = np.arange(max(x0, 100.0), ex0, 1.0)
                tq = round(on["t"] / 0.1) * 0.1
                cc = IT.CASES[case]; Pm, Qm = IT.modes(cc)
                lin = IT.combine_y(IT.mode_series(Pm, Qm, xl, [tq], ramp_kind=ramp_kind), [0.0])["eta"][0, 0]
                out["lead_vs_linear"] = dict(t=tq, x_flip=on["xc"], x_linear=float(xl[int(np.argmax(lin))]), eta_linear=float(lin.max()),
                                             lead_m=on["xc"] - float(xl[int(np.argmax(lin))]))
            except Exception as e:
                out["lead_vs_linear"] = dict(error=repr(e)[:200])
            try:
                u2 = R2.get(on["frame"], "u")[0].astype(np.float64)
                mu = (R2.get(on["frame"])[1].get("vel") or {}).get("vel.x")
                if mu:
                    i = int(round((on["xc"] - mu["p0"][0]) / mu["d"][0]))
                    zz = mu["p0"][1] + mu["d"][1] * np.arange(u2.shape[0]) - off
                    col = u2[:, i]
                    ok = np.isfinite(col)
                    def at(z):
                        return float(np.interp(z, zz[ok], col[ok]))
                    out["u_under_crest"] = dict(x=on["xc"], top=at(on["eta_c"] - 0.5 * vox), z0=at(0.0), bed=at(-19.5), paper=[11.1, 3.9, 1.1],
                                                note_ja="R2 の u（x 方向の面の格子）を x = xc の縦の線で。頂の上の端は頂の高さ − 格子の半分")
            except Exception as e:
                out["u_under_crest"] = dict(error=repr(e)[:200])
            # N12（帯に近い）
            out["N12_near_band"] = bool(on["xc"] > ex0 - 0.5 * LAM or (x0 > 0 and on["xc"] < 185.0))
            # N11（巻き始めまで）
            tg, Eg = gauges(R1, [(100.0, 0.0), (150.0, 0.0), (200.0, 0.0)])
            out["N11_long_wave"] = {str(x): long_wave(tg, Eg[i], off, on["t"]) for i, x in enumerate((100, 150, 200))}
            # L-e・L-b（R4）
            if not quick:
                oa = offaxis(rd, off, vox, max(R2.frames[0], on["frame"] - int(6 * FPS)), on["frame"] + int(2 * FPS))
                spans = oa.pop("_spans", {})
                out["L_e_offaxis_onset"] = oa
                if on["frame"] in spans:
                    out["L_b_overturn_span_at_onset"] = C3.span_over90(spans[on["frame"]])
                if spans:
                    lb = {f: C3.span_over90(rw) for f, rw in spans.items() if f >= on["frame"]}
                    if lb:
                        fb = max(lb, key=lambda q: lb[q])
                        out["L_b_overturn_span_max"] = dict(frame=int(fb), span_m=lb[fb],
                                                            note_ja="巻き始めから 2 s までの R4 のコマで、前の面の弦が 90° を越える y の範囲 × 2 の最大（計画の「いちばん巻いたコマ」の代わり。読み方 R24）")
        else:
            st = [e["steepest"] for e in ev if e["steepest"] is not None]
            out["onset"] = None
            out["steepest"] = max(st, key=lambda s: s["thmax"]) if st else None
            out["note_onset"] = "巻き始めがない。最も険しくなったコマの量を steepest に書いた（FLIP42 の読み方 10）"
    # Ac・H1 の二つ目の読み（巻き始めの前の周期の平均の水面から。2026-10-12 に足した。記録）
    try:
        out["second_reading_mean_level"] = second_reading(out, R1, P, off, t_off)
    except Exception as e:
        out["second_reading_mean_level"] = dict(error=repr(e)[:300])
    json.dump(out, open(os.path.join(rd, "ana.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    return out


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    rid = sys.argv[1]; root = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else "runs"
    r = analyze(rid, root, quick="--quick" in sys.argv)
    print(json.dumps({k: r.get(k) for k in ("run_id", "still_level_offset_m", "still_offset_source", "N3_summary", "N10", "onset", "ell", "touchdown",
                                             "reproduction", "second_reading_mean_level", "cost")}, ensure_ascii=False, indent=1, default=float)[:6000])
