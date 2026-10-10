# -*- coding: utf-8 -*-
"""RT48 の確かめ C2（計画 §4）：粒子から作った細かい面（r_surface.py）が、解く格子の面から形を変えていないか（py -3.10）。
  (a) 頂から ±20 m の外で、水面が一つ（細かい面の列の交わりが 1 回、sec のある所は解く格子の列も 1 回）で傾き 30° 未満の hf の節の列：
      細かい面と解く格子の面の一番上の高さ（それぞれの静かな水面から）の差 p99 ≤ 0.10 m・最大 ≤ 0.25 m（3319〜3889 コマを合わせて）。
  (b) FLIP42 の読み方 7・12（g_analyze.frame_shape と g_shape.extra をそのまま使う。sec と同じ x の範囲に切る）を細かい面に当てた巻き始めが
      3714 コマ・508.3 m から ±1 コマ・±1.0 m、その時の η_c（頂に最も近い列の一番上の高さ）が 9.56 m から ±0.25 m。
  (c) 頂の ±20 m の窓、3319〜3796 コマ：0.125 m の節で細かい面の水（φ < 0）と解く格子の面の水（sec を双一次で移す。sec の外は hf より下）を二値にし、
      面積 0.25 m² 未満の閉じた水（窓の下の端に付かない水のつながり）を両方から除き、両向きの距離の最大がどちらも 0.5 m 以下（読み方 6）。
  (d) 細かい面で空気を囲む最初のコマ（読み方 7：窓 ±30 m、面積 0.25 m² 以上、頂より下、巻き始めより後）が 3745 コマ ±1。
  (e) 巻き始めから最初の接触の前までの唇の最大（FLIP42 の読み方 16 (3)、g_shape.extra の jet_lip、届く距離が最大のコマ）が、届く距離 3.65 m ±0.5 m、厚み 1.06 m ±0.5 m。
頂の窓の中心は粗い元の焼き（data/coarse/manifest.json の frames の crest_x）。比べの R3 の値は同じ道具を R3 の sec に当てて並べて出す。
使い方: py -3.10 r_c2.py <fine_dir> <records_dir> [--out <json>] [--frames a-b]"""
import os as _os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):   # 数値の部品のスレッドの予約（1 つの起動で約 0.6 GB）を小さくする
    _os.environ.setdefault(_v, "1")
import sys, os, json, time, argparse
import numpy as np
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r_lib as L
import r_surface as RS
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42")
import g_analyze as GA
import g_shape as GS

LC = 135.46329754326246
ONSET_R3 = (3714, 508.3065989511929, 9.557111740112305)
TOUCH_R3 = 3745
LIP_R3 = (3.65, 1.06)
DATA = os.environ.get("RT48_DATA", "G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48/data")   # 試しの時だけ環境変数で替える


def load_phi(fine_dir, f):
    z = np.load(os.path.join(fine_dir, "phi_%04d.npz" % f))
    phi = z["phi"].astype(np.float32)
    xs_rel = float(z["x0_rel"]) + float(z["dx"]) * np.arange(phi.shape[1])
    ys_abs = float(z["y0_abs"]) + float(z["dy"]) * np.arange(phi.shape[0])
    return phi, xs_rel, ys_abs


def crop_sec(phi, xs_rel):
    xsc = xs_rel + L.XP
    c = (xsc >= RS.SEC_X[0] - 1e-9) & (xsc <= RS.SEC_X[1] + 1e-9)
    i0 = int(np.argmax(c)); n = int(c.sum())
    return phi[:, i0:i0 + n], float(xsc[i0]), n


def shape_on(S, x0_scene, dx, y0_abs, dy, off):
    meta = dict(x0=x0_scene, dx=dx, nx=S.shape[1], y0=y0_abs, dy=dy, ny=S.shape[0])
    sh = GA.frame_shape(S, meta, off, L.VOX, LC, None, None)
    if sh is None:
        return None, None, meta
    ex = GS.extra(S, meta, off, L.VOX, LC, sh, L.XP)
    return sh, ex, meta


def solver_water(rec, f, X_rel, Yh):
    """解く格子の水（静かな水面からの高さ Yh の節で）"""
    S, xs, ys, m = rec.sec(f, 0.0)
    eh, xh = rec.hf(f, 0.0)
    Ya = Yh + L.OFF_R3
    Xs = X_rel + L.XP
    ins = (Xs >= RS.SEC_X[0] - 1e-9) & (Xs <= RS.SEC_X[1] + 1e-9)
    out = np.zeros(Ya.shape, bool)
    if ins.any():
        v = RS.bilinear(S, m["x0"], m["dx"], m["y0"], m["dy"], Xs[ins], Ya[ins])
        out[ins] = v < 0
    if (~ins).any():
        out[~ins] = Ya[~ins] < np.interp(Xs[~ins], xh + L.XP, eh)
    return out


def drop_small(mask, cell_area, amin=0.25):
    lab, n = ndimage.label(mask)
    if n == 0:
        return mask, 0
    bottom = set(np.unique(lab[0, :])) - {0}
    sizes = ndimage.sum(mask, lab, index=np.arange(1, n + 1)) * cell_area
    drop = [i + 1 for i in range(n) if (i + 1) not in bottom and sizes[i] < amin]
    if drop:
        mask = mask & ~np.isin(lab, drop)
    return mask, len(drop)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fine_dir"); ap.add_argument("records_dir")
    ap.add_argument("--out", default=os.path.join(DATA, "c2.json"))
    ap.add_argument("--frames", default="%d-%d" % (L.F0, L.F1))
    a = ap.parse_args()
    T0 = time.time()
    meta_f = json.load(open(os.path.join(a.fine_dir, "meta.json"), encoding="utf8"))
    off = float(meta_f["still_offset_m"])
    rec = L.Records(a.records_dir)
    cm = json.load(open(os.path.join(DATA, "coarse", "manifest.json"), encoding="utf8"))
    crest = {r["frame"]: r["crest_x"] for r in cm["frames"]}
    if "," in a.frames:
        frames = [int(v) for v in a.frames.split(",")]
    else:
        f0, f1 = [int(v) for v in a.frames.split("-")]
        frames = list(range(f0, f1 + 1))
    res = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/rt48/r_c2.py", fine_dir=a.fine_dir, records=a.records_dir,
               fine_still_offset_m=off, frames=[frames[0], frames[-1]], n_frames=len(frames))
    # ---------------- (a)
    dall, per = [], []
    worst = (0.0, None)
    for f in frames:
        phi, xs_rel, ys_abs = load_phi(a.fine_dir, f)
        P4 = phi[:, ::4]; x4 = xs_rel[::4]
        tf = RS.top_y(P4, ys_abs) - off
        ncf = RS.crossings_per_col(P4)
        eh, xh = rec.hf(f, L.OFF_R3)
        ii = np.rint((x4 - xh[0]) / (xh[1] - xh[0])).astype(int)
        et = eh[ii]
        slope = np.degrees(np.arctan(np.abs(np.gradient(eh, xh[1] - xh[0]))))[ii]
        S, xs, ys, m = rec.sec(f, L.OFF_R3)
        ncs = np.ones(len(x4), int)
        inr = (x4 >= xs[0] - 1e-6) & (x4 <= xs[-1] + 1e-6)
        js = np.rint((x4[inr] - xs[0]) / (xs[1] - xs[0])).astype(int)
        ncs[inr] = RS.crossings_per_col(S[:, js])
        ok = (np.abs(x4 - crest[f]) > L.WIN_C2) & (ncf == 1) & (ncs == 1) & (slope < 30.0) & np.isfinite(tf) & np.isfinite(et)
        d = np.abs(tf[ok] - et[ok])
        dall.append(d)
        if len(d):
            k = int(np.argmax(d))
            per.append([f, float(d.max()), float(np.percentile(d, 99)), int(ok.sum())])
            if d.max() > worst[0]:
                worst = (float(d.max()), dict(frame=f, x_rel=float(x4[ok][k]), fine=float(tf[ok][k]), solver=float(et[ok][k])))
    dall = np.concatenate(dall)
    ra = dict(n=int(len(dall)), p99=float(np.percentile(dall, 99)), max=float(dall.max()), median=float(np.median(dall)), worst=worst[1],
              tol_p99=0.10, tol_max=0.25)
    ra["ok"] = bool(ra["p99"] <= 0.10 and ra["max"] <= 0.25)
    ra["per_frame_max_p99_n"] = per
    res["a"] = ra
    # ---------------- (b)(d)(e)：巻き始めの近くから
    on_f = None; on_x = None; on_eta = None
    rows_b = []
    contact = None
    lip = []
    ref = []
    fr_b = [f for f in frames if 3680 <= f <= 3800]
    for f in fr_b:
        phi, xs_rel, ys_abs = load_phi(a.fine_dir, f)
        Sc, x0s, n = crop_sec(phi, xs_rel)
        sh, ex, meta = shape_on(Sc, x0s, RS.H, ys_abs[0], RS.H, off)
        if sh is None:
            continue
        xc_rel = sh["xc"] - L.XP
        ic = int(np.argmin(np.abs(xs_rel - xc_rel)))
        eta_c = float(RS.top_y(phi[:, ic:ic + 1], ys_abs)[0] - off)
        row = dict(frame=f, thmax=sh["thmax"], xc_rel=xc_rel, eta_c=eta_c, vertical_x_rel=ex.get("vertical_x_rel"),
                   jet_lip=None if not ex.get("jet_lip") else {k: ex["jet_lip"][k] for k in ("reach", "thick_mid", "x_tip_rel", "y_tip")})
        # 読み方 7（窓 ±30 m の空気）
        w0, w1 = crest[f] - L.WIN_I, crest[f] + L.WIN_I
        cmask = (xs_rel >= w0 - 1) & (xs_rel <= w1 + 1)
        ys_h = ys_abs - off
        opn, loops = L.field_curves(phi[:, cmask], xs_rel[cmask], ys_h)
        ytop = max(float(o[:, 1].max()) for o in opn) if opn else 0.0
        cav = [q for q in loops if q["phase"] == 1 and q["area"] >= 0.25 and q["pts"][:, 0].max() >= w0 and q["pts"][:, 0].min() <= w1
               and q["pts"][:, 1].mean() < ytop]
        row["cavities"] = [[float(q["pts"][:, 0].max()), float(q["area"])] for q in cav]
        rows_b.append(row)
        if on_f is None and np.isfinite(sh["thmax"]) and sh["thmax"] >= 90.0:
            on_f, on_x, on_eta = f, ex.get("vertical_x_rel"), eta_c
        elif on_f is not None and contact is None and cav:
            contact = f
        if on_f is not None and contact is None and f >= on_f and row["jet_lip"]:
            lip.append(row)
    rb = dict(onset_frame=on_f, onset_x_rel=on_x, eta_c=on_eta, r3=dict(frame=ONSET_R3[0], x_rel=ONSET_R3[1], eta_c=ONSET_R3[2]))
    rb["ok"] = bool(on_f is not None and abs(on_f - ONSET_R3[0]) <= 1 and on_x is not None and abs(on_x - ONSET_R3[1]) <= 1.0
                and abs(on_eta - ONSET_R3[2]) <= 0.25)
    res["b"] = rb
    res["d"] = dict(first_contact_frame=contact, r3=TOUCH_R3, ok=bool(contact is not None and abs(contact - TOUCH_R3) <= 1))
    if lip:
        b = max(lip, key=lambda r: r["jet_lip"]["reach"])
        re_ = dict(frame=b["frame"], t=L.t_of(b["frame"]), reach=b["jet_lip"]["reach"], thick=b["jet_lip"]["thick_mid"])
    else:
        re_ = dict(frame=None, reach=None, thick=None)
    re_["target"] = LIP_R3
    re_["ok"] = bool(re_["reach"] is not None and re_["thick"] is not None and abs(re_["reach"] - LIP_R3[0]) <= 0.5 and abs(re_["thick"] - LIP_R3[1]) <= 0.5)
    # 同じ道具を R3 の sec（粗い）に当てた値（並べて書く）
    reflip = []
    for f in range(ONSET_R3[0], TOUCH_R3):
        S, xs, ys, m = rec.sec(f, 0.0)
        sh, ex, meta = shape_on(S, m["x0"], m["dx"], m["y0"], m["dy"], L.OFF_R3)
        if ex and ex.get("jet_lip"):
            reflip.append((f, ex["jet_lip"]["reach"], ex["jet_lip"]["thick_mid"]))
    if reflip:
        b = max(reflip, key=lambda q: q[1])
        re_["same_tool_on_solver_sec"] = dict(frame=b[0], reach=b[1], thick=b[2],
                                              note="FLIP42 の報告の 3.65 m・1.06 m は独立の確かめ（check_R2_extra.py）の読み。g_shape.extra の読みでは左の値")
    res["e"] = re_
    res["rows_bde"] = rows_b
    # ---------------- (c)
    rc_rows, worst_c = [], 0.0
    n_drop = [0, 0]
    for f in [q for q in frames if q <= 3796]:
        phi, xs_rel, ys_abs = load_phi(a.fine_dir, f)
        cm_ = (xs_rel >= crest[f] - L.WIN_C2) & (xs_rel <= crest[f] + L.WIN_C2)
        Pf = phi[:, cm_] < 0
        Xr = np.broadcast_to(xs_rel[cm_][None, :], Pf.shape); Yh = np.broadcast_to((ys_abs - off)[:, None], Pf.shape)
        Ps = solver_water(rec, f, Xr, Yh)
        Pf, df = drop_small(Pf, RS.H * RS.H); Ps, ds = drop_small(Ps, RS.H * RS.H)
        n_drop[0] += df; n_drop[1] += ds
        if not Pf.any() or not Ps.any():
            continue
        d_to_s = ndimage.distance_transform_edt(~Ps) * RS.H
        d_to_f = ndimage.distance_transform_edt(~Pf) * RS.H
        m1 = float(d_to_s[Pf].max()); m2 = float(d_to_f[Ps].max())
        rc_rows.append([f, m1, m2])
        worst_c = max(worst_c, m1, m2)
    res["c"] = dict(max_fine_to_solver=max(r[1] for r in rc_rows), max_solver_to_fine=max(r[2] for r in rc_rows), tol=0.5,
                    small_water_dropped=dict(fine=n_drop[0], solver=n_drop[1]), ok=bool(worst_c <= 0.5), rows=rc_rows)
    res["pass_all"] = bool(res["a"]["ok"] and res["b"]["ok"] and res["c"]["ok"] and res["d"]["ok"] and res["e"]["ok"])
    res["seconds"] = round(time.time() - T0, 1)
    json.dump(res, open(a.out, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    print(json.dumps({k: (v if not isinstance(v, dict) else {q: w for q, w in v.items() if q not in ("rows", "per_frame_max_p99_n")})
                      for k, v in res.items() if k != "rows_bde"}, ensure_ascii=False, indent=1, default=float))
    return res


if __name__ == "__main__":
    main()
