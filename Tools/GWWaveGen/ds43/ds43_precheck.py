# -*- coding: utf-8 -*-
"""設計43 の前の確かめ（numpy）：3 隻の船の足跡（置き方の xz・向き、水平）で、設計30 の海の式（far の弱めつき）と表示面（主役波・near・far の
三角形の鉛直の交わり）の高さの差を、再生の全コマ（30 fps、t 0〜12 s）で測る。船用水面データの読み方を決めるための測り（記録のみ）。
使い方：py -3.10 -B Tools/GWWaveGen/ds43/ds43_precheck.py
"""
import os
import time

import numpy as np

import ds43_common as C


def boat_footprints(n_along=9, n_across=3):
    lay = C.load_json(os.path.join(C.REPO, "Tools", "GWContext", "context_layout.json"))
    seat = C.load_json(os.path.join(C.REPO, "Tools", "GWContext", "seat_v1.json"))
    m41 = C.load_json(os.path.join(C.REPO, "Docs", "Evidence", "Design", "41", "metrics.json"))["model"]["real_dimensions_per_boat"]
    out = {}
    for key in ("boat_mid", "boat_fg", "boat_left"):
        b = m41[key]
        p = np.array([b["root_position"][k] for k in "xyz"])
        q = np.array([b["root_rotation"][k] for k in "xyzw"])
        x, y, z, w = q
        # 局所 +z（船首）を世界へ
        fz = np.array([2 * (x * z + w * y), 2 * (y * z - w * x), 1 - 2 * (x * x + y * y)])
        f = np.array([fz[0], fz[2]]); f /= np.linalg.norm(f)
        r = np.array([f[1], -f[0]])   # 右舷（上から見て）
        L, Bm = b["tip_to_tip_m"], b["beam_m"]
        s = np.linspace(-0.42 * L, 0.42 * L, n_along)
        u = np.linspace(-0.3 * Bm, 0.3 * Bm, n_across)
        pts = np.array([[p[0] + si * f[0] + ui * r[0], p[2] + si * f[1] + ui * r[1]] for si in s for ui in u])
        out[key] = dict(root=p, fwd=f, pts=pts, L=L, beam=Bm)
    return out


def main():
    t0 = time.time()
    hero, near, far = C.load_sheets()
    tw = C.TimeWarp()
    sf = C.SeaFunction()
    zeta = np.array(near.k["ring_zeta"])
    boats = boat_footprints()
    frames = np.arange(0, 361) / 30.0
    res = {k: dict(diff=[], sheet=[], nhit=[], t=[]) for k in boats}
    for fi, t in enumerate(frames):
        tau = tw.tau_at(t)
        Vh, Vn, Vf = hero.world(tau), near.world(tau), far.world(tau)
        for key, b in boats.items():
            Q = b["pts"]
            hh = C.vertical_hits(Vh, hero.r1, hero.c0, hero.c1, Q)
            hn = C.vertical_hits(Vn, near.r1, near.c0, near.c1, Q)
            hf = C.vertical_hits(Vf, far.r1, far.c0, far.c1, Q)
            eta = sf.eta(Q[:, 0], Q[:, 1], tau)
            for n in range(len(Q)):
                allh = hh[n] + hn[n] + hf[n]
                ys = C.merge_hits(allh)
                kind = "none"
                if hh[n]:
                    kind = "hero"
                elif hn[n]:
                    rmin = min(h[1] for h in hn[n])
                    kind = "near_band" if zeta[rmin + 1] <= 0.10 + 1e-9 else "near"
                elif hf[n]:
                    kind = "far"
                res[key]["t"].append(t)
                res[key]["nhit"].append(len(ys))
                res[key]["sheet"].append(kind)
                res[key]["diff"].append(float(eta[n] - ys[0]) if ys else float("nan"))
        if fi % 60 == 0:
            print("t %.2f τ %.3f  %.1f s" % (t, tau, time.time() - t0), flush=True)
    summ = {}
    for key, r in res.items():
        d = np.array(r["diff"]); k = np.array(r["sheet"]); nh = np.array(r["nhit"]); tt = np.array(r["t"])
        s = {}
        for kind in ("far", "near", "near_band", "hero", "none"):
            m = (k == kind)
            if not m.any():
                continue
            m1 = m & (nh == 1)
            s[kind] = dict(samples=int(m.sum()), single=int(m1.sum()),
                           absmax_single=float(np.nanmax(np.abs(d[m1]))) if m1.any() else None,
                           p95_single=float(np.nanpercentile(np.abs(d[m1]), 95)) if m1.any() else None,
                           t_range=[float(tt[m].min()), float(tt[m].max())])
        summ[key] = s
    C.save_json(os.path.join(C.OUT, "precheck", "ds43_precheck_analytic_vs_display.json"),
                dict(note_ja="設計30 の海の式（far の弱めつき）− 表示面の最も低い交わり。船の足跡は置き方の xz・向きで水平（9 × 3 点）。記録のみ（読み方を決めるための測り）",
                     summary=summ, seconds=round(time.time() - t0, 1)))
    import json
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
