# -*- coding: utf-8 -*-
"""組み込みの準備：方法 C（流れに乗せて運ぶ網目。提案 §3.6 の一つ目）の安い確かめ。断面（2D）だけ。
P1 の断面の計算（B025H32_T14_H32_n4_hr26、粒子 0.25 m、誘導なし）の粒子の流速で、水面に置いた 400 点を運ぶ。
- 置く：時刻 T_SEED の水面の線の上に、頂の 75 m 後ろから 60 m 前まで（方法 A の列の範囲に近い長さ）一様に 400 点。
  比べるため、波の通り道全体（頂の 75 m 後ろから、T_END の頂の 60 m 前まで）に一様に置く場合も作る。
- 運ぶ：1/24 s ごとに、近い粒子 8 個の流速（距離の逆数の重み）で 2 段のルンゲ・クッタ、運んだら水面の線へ戻す（一番近い点）。
  流速は時刻の近いほうの断面の粒子から取る（断面は 1/12 s ごと）。
- 測る：点が頂・唇の先・空洞の奥を覆っているか、主役波の範囲（頂の 30 m 後ろ〜前の谷）の中の点の数と最大の間隔、
  点の並びの入れ替わり（網目の折れ）の数。
出力：Unity/Build/FLIP37/integration_prep/flow2d/flow2d.json と flow2d.png
"""
import os, sys, glob, json, time
import numpy as np
import cv2
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from skimage import measure

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p1_analyze as PA
import integ_common as C

RUN = C.REPO + "/Unity/Build/FLIP37/P1/B025H32_T14_H32_n4_hr26"
OD = C.OUT + "/flow2d"
T_SEED, T_END = 8.0, 12.5
NPT = 400
X0, X1 = 401.0, 805.0


def surface_curve(d):
    cnt = PA.raster(d["x"].astype(float), d["y"].astype(float), X0, X1)
    water, closed = PA.water_mask(cnt)
    body = PA.main_component(water)
    fld = ndi.gaussian_filter(body.astype(np.float32), 1.0)
    cs = measure.find_contours(np.pad(fld, 1), 0.5)
    best = None
    for c in cs:
        y = PA.YMIN + (c[:, 0] - 1 + 0.5) * PA.DX
        x = X0 + (c[:, 1] - 1 + 0.5) * PA.DX
        keep = (y > PA.YMIN + 1.0) & (x > X0 + 1.0) & (x < X1 - 1.0) & (y < PA.YMAX - 1.0)
        if (~keep).any() and np.allclose(c[0], c[-1]):
            r0 = int(np.where(~keep)[0][0])          # 閉じた線は枠の点から始まるように回す（水面が二つに切れないように）
            x, y, keep = np.roll(x, -r0), np.roll(y, -r0), np.roll(keep, -r0)
        # 枠の上の部分を除き、続く区間に分ける
        idx = np.where(keep)[0]
        if len(idx) < 10:
            continue
        br = np.where(np.diff(idx) > 1)[0]
        for seg in np.split(idx, br + 1):
            if len(seg) < 10:
                continue
            p = np.stack([x[seg], y[seg]], 1)
            L = C.polyline_len(p)
            if best is None or L > best[0]:
                best = (L, p)
    p = best[1]
    if p[0, 0] > p[-1, 0]:
        p = p[::-1]
    return p


def project(pts, curve, s_curve):
    """点を折れ線の一番近い点へ。戻り：新しい点、その弧長。"""
    a = curve[:-1]; b = curve[1:]
    ab = b - a
    L2 = np.maximum((ab ** 2).sum(1), 1e-12)
    out = np.zeros_like(pts); sp = np.zeros(len(pts))
    tree = cKDTree(0.5 * (a + b))
    _, nn = tree.query(pts, k=12)
    for i, p in enumerate(pts):
        cand = nn[i]
        t = np.clip(((p - a[cand]) * ab[cand]).sum(1) / L2[cand], 0, 1)
        q = a[cand] + ab[cand] * t[:, None]
        dd = ((q - p) ** 2).sum(1)
        k = int(np.argmin(dd))
        out[i] = q[k]; sp[i] = s_curve[cand[k]] + t[k] * np.sqrt(L2[cand[k]])
    return out, sp


def main():
    os.makedirs(OD, exist_ok=True)
    t0w = time.time()
    rj = json.load(open(RUN + "/run.json", encoding="utf8"))
    PA.set_dx(rj["parms"])
    fs = sorted(glob.glob(RUN + "/snap_*.npz"))
    snaps = []
    for f in fs:
        d = np.load(f)
        t = float(d["t"])
        if T_SEED - 0.1 <= t <= T_END + 0.1:
            snaps.append((t, f))
    times = np.array([s[0] for s in snaps])
    cache = {}

    def get(i):
        if i not in cache:
            d = np.load(snaps[i][1])
            P = np.stack([d["x"], d["y"]], 1).astype(float)
            V = np.stack([d["vx"], d["vy"]], 1).astype(float)
            cur = surface_curve(d)
            s = np.r_[0, np.cumsum(np.hypot(*np.diff(cur, axis=0).T))]
            cache[i] = (cKDTree(P), V, cur, s)
            for k in list(cache.keys()):
                if abs(k - i) > 2:
                    del cache[k]
        return cache[i]

    def vel(pts, t):
        i = int(np.argmin(np.abs(times - t)))
        tr, V, _, _ = get(i)
        dd, nn = tr.query(pts, k=8)
        w = 1.0 / np.maximum(dd, 0.05)
        return (V[nn] * w[..., None]).sum(1) / w.sum(1)[:, None]

    i0 = int(np.argmin(np.abs(times - T_SEED)))
    _, _, cur0, s0 = get(i0)
    lm0 = C.section_landmarks(cur0)
    an = json.load(open(RUN + "/analysis.json", encoding="utf8"))
    tc = np.array([e["t"] for e in an["timeline"]]); xc = np.array([e["crest"][0] for e in an["timeline"]])
    xT0, xTe = float(np.interp(T_SEED, tc, xc)), float(np.interp(T_END, tc, xc))
    runs = {}
    for name, (xa, xb) in {"hero_window": (xT0 - 75, xT0 + 60), "whole_path": (xT0 - 75, xTe + 60)}.items():
        ia = int(np.argmin(np.abs(cur0[:, 0] - xa))); ib = len(cur0) - 1 - int(np.argmin(np.abs(cur0[::-1, 0] - xb)))
        sj = np.linspace(s0[ia], s0[ib], NPT)
        pts = np.stack([np.interp(sj, s0, cur0[:, 0]), np.interp(sj, s0, cur0[:, 1])], 1)
        t = times[i0]
        dt = 1.0 / 24.0
        recs = []
        snapshots = {}
        while t < T_END - 1e-6:
            v1 = vel(pts, t)
            mid = pts + 0.5 * dt * v1
            v2 = vel(mid, t + 0.5 * dt)
            pts = pts + dt * v2
            t += dt
            i = int(np.argmin(np.abs(times - t)))
            _, _, cur, s = get(i)
            pts, sp = project(pts, cur, s)
            lm = C.section_landmarks(cur)
            kn = lm["s_knots"]
            inv = int((np.diff(sp) < 0).sum())
            hero = (sp >= kn[2] - 30.0) & (sp <= kn[5])
            sh = np.sort(sp[hero])
            gaps = np.diff(sh) if len(sh) > 1 else np.array([np.inf])
            cover = {k: bool(((sp > v - 1.0) & (sp < v + 1.0)).any()) for k, v in (("top", kn[2]), ("tip", kn[3]), ("corner", kn[4]))}
            recs.append({"t": round(t, 4), "hero_points": int(hero.sum()), "max_gap_m": float(gaps.max()) if len(sh) > 1 else None,
                         "median_gap_m": float(np.median(gaps)) if len(sh) > 1 else None, "order_inversions": inv,
                         "covers": cover, "overhang": lm["overhang"], "points_x_range": [float(pts[:, 0].min()), float(pts[:, 0].max())],
                         "crest_x": lm["x_top"]})
            for tt in (9.0, 10.0, 11.0, 11.5, 12.0, 12.5):
                if abs(t - tt) < 0.5 * dt:
                    snapshots[tt] = (pts.copy(), cur.copy(), kn.copy(), sp.copy())
        runs[name] = {"seed_x": [xa, xb], "records": recs, "snaps": snapshots}
        print(name, "done %.0fs" % (time.time() - t0w), flush=True)
    # 図
    W, Hh = 900, 260
    rows = []
    for tt in (9.0, 10.0, 11.0, 11.5, 12.0, 12.5):
        tiles = []
        for name in ("hero_window", "whole_path"):
            img = np.full((Hh, W, 3), 250, np.uint8)
            if tt not in runs[name]["snaps"]:
                tiles.append(img); continue
            pts, cur, kn, sp = runs[name]["snaps"][tt]
            xt = float(np.interp(kn[2], np.r_[0, np.cumsum(np.hypot(*np.diff(cur, axis=0).T))], cur[:, 0]))
            xr = (xt - 90, xt + 70); sc = (W - 20) / (xr[1] - xr[0])
            tp = lambda p: np.stack([10 + (p[:, 0] - xr[0]) * sc, Hh - 30 - (p[:, 1] + 12) * sc], 1).astype(np.int32)
            cv2.polylines(img, [tp(cur)], False, (170, 170, 170), 2, cv2.LINE_AA)
            for j, p in enumerate(tp(pts)):
                col = (int(255 * j / NPT), 60, int(255 * (1 - j / NPT)))
                cv2.circle(img, tuple(p), 2, col, -1, cv2.LINE_AA)
            r = [x for x in runs[name]["records"] if abs(x["t"] - tt) < 0.03][0]
            cv2.putText(img, "%s t=%.1fs hero pts %d max gap %.1fm inversions %d" % (name, tt, r["hero_points"], r["max_gap_m"] or -1, r["order_inversions"]),
                        (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
            tiles.append(img)
        rows.append(np.concatenate(tiles, 1))
    cv2.imwrite(OD + "/flow2d.png", np.concatenate(rows, 0))
    out = {"source_run": RUN, "seed_t": T_SEED, "end_t": T_END, "points": NPT, "wall_s": time.time() - t0w,
           "runs": {k: {"seed_x": v["seed_x"], "records": v["records"]} for k, v in runs.items()},
           "note_ja": "断面（2D）だけの確かめ。3D の流れに乗せる網目の行の間の歪みは測っていない。"}
    for k, v in runs.items():
        last = v["records"][-1]
        out["runs"][k]["summary"] = {"hero_points_at_end": last["hero_points"], "max_gap_at_end_m": last["max_gap_m"],
                                     "hero_points_min": min(r["hero_points"] for r in v["records"]),
                                     "max_gap_max_m": max((r["max_gap_m"] or 0) for r in v["records"]),
                                     "inversions_max": max(r["order_inversions"] for r in v["records"]),
                                     "first_t_top_not_covered": next((r["t"] for r in v["records"] if not r["covers"]["top"]), None),
                                     "first_t_tip_not_covered": next((r["t"] for r in v["records"] if not r["covers"]["tip"]), None)}
    json.dump(out, open(OD + "/flow2d.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v["summary"] for k, v in out["runs"].items()}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
