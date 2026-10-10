# -*- coding: utf-8 -*-
"""4. 船の上下と縦揺れが、再生した水面から来ているか。
(a) 自分の R3 の線から出したコマごとの上下・縦揺れ（船体 ±6 m の 9 点の一番上の水面の平均と最小二乗の傾き）と、焼きの表（manifest）。
(b) Unity が書き出した船（verify の boats、46 の時刻）と、自分の値（補間する組は焼いた A・B を混ぜた線から、ほかはコマの値を時刻で補間）。
(c) 90 Hz の刻みで、船（Unity の決まり）と、見せているコマの水面から求めた船とのずれ。
出力：out/k_boat.json"""
import numpy as np
from k_lib import *

kr = jload(OUT + "/k_r3.json")
rows = kr["rows"]
pairs, man = load_pairs()
interp = np.array([p["interp"] for p in man["pairs"]])
K = man["events"]["K"]
res = {}
for seat in ("556", "574"):
    hm = np.array([r["heave" + seat] for r in rows]); pm = np.array([r["pitch" + seat] for r in rows])
    hb = np.array(man["boat"][seat]["heave_m"]); pb = np.array(man["boat"][seat]["pitch_deg"])
    end = man["boat"][seat]["clip_end_frame"]
    sl = slice(0, end - F0 + 1)
    res[seat] = dict(table_vs_mine=dict(max_dh=float(np.abs(hm - hb)[sl].max()), max_dp=float(np.abs(pm - pb)[sl].max()),
                                         max_dh_all=float(np.abs(hm - hb).max()), max_dp_all=float(np.abs(pm - pb).max())),
                     mine_range_to_end=dict(heave=(float(hm[sl].min()), float(hm[sl].max())), pitch=(float(pm[sl].min()), float(pm[sl].max()))),
                     clip_end_frame=end)

    # (b) Unity の船
    for which in ("editor", "player"):
        ix = jload(RT + f"/verify/coarse/unity_{which}/index.json")
        out = []
        for b in ix["boats"]:
            if abs(b["seatX"] - float(seat)) > 1e-6:
                continue
            t = b["t"]
            u = (t - T0) * FPS
            k = int(np.floor(u + 1e-9)); w = min(1.0, max(0.0, u - k))
            if k < 569 and interp[k]:
                A = pairs[k, 0].astype(np.float64); B = pairs[k, 1].astype(np.float64)
                C = A + (B - A) * w; C[:, 0] += X0B
                h, p, _ = boat_pose(C, float(seat)); mode = "curve"
                # 自分の R3 だけからの近い値（コマの値の補間）も並べる
                h2 = hm[k] + (hm[k + 1] - hm[k]) * w; p2 = pm[k] + (pm[k + 1] - pm[k]) * w
            else:
                h = hm[k] + (hm[k + 1] - hm[k]) * w; p = pm[k] + (pm[k + 1] - pm[k]) * w; mode = "frame_lerp"
                h2, p2 = h, p
            # カメラ：船の根 (0, 上下) を縦揺れで回した (0, 1.2)
            th = np.radians(b["pitchDeg"])
            cam = (-1.2 * np.sin(th), b["heave"] + 1.2 * np.cos(th))
            out.append(dict(t=t, kind=b["kind"], mode_u=b["mode"], mode_mine=mode, dh=b["heave"] - h, dp=b["pitchDeg"] - p,
                            dh_r3only=b["heave"] - h2, dp_r3only=b["pitchDeg"] - p2,
                            root_dy=b["rootY"] - b["heave"], root_rot=b["rootRollZDeg"] - b["pitchDeg"], rootX=b["rootX"], rootZ=b["rootZ"],
                            cam_dx=b["camX"] - cam[0], cam_dy=b["camY"] - cam[1]))
        res[seat]["unity_" + which] = dict(n=len(out), max_dh=max(abs(o["dh"]) for o in out), max_dp=max(abs(o["dp"]) for o in out),
                                            max_dh_r3only=max(abs(o["dh_r3only"]) for o in out), max_dp_r3only=max(abs(o["dp_r3only"]) for o in out),
                                            mode_mismatch=sum(o["mode_u"] != o["mode_mine"] for o in out),
                                            max_root_dy=max(abs(o["root_dy"]) for o in out), max_root_rot=max(abs(o["root_rot"]) for o in out),
                                            max_root_xz=max(max(abs(o["rootX"]), abs(o["rootZ"])) for o in out),
                                            max_cam_d=max(max(abs(o["cam_dx"]), abs(o["cam_dy"])) for o in out), rows=out)

    # (c) 90 Hz のずれ（補間しない組で、船はコマの値を時刻で補間、見せる水面は前のコマ）
    tend = man["boat"][seat]["clip_end_t"]
    ts = T0 + np.arange(0, int(np.floor((tend - T0) * 90 + 1e-9)) + 1) / 90.0
    gaps = dict(after_K=[0, 0, None, None], held_before_K=[0, 0, None, None])
    for t in ts:
        u = (t - T0) * FPS; k = int(np.floor(u + 1e-9)); w = min(1.0, max(0.0, u - k))
        if k >= 570:
            continue
        if interp[k]:
            continue
        dh = abs((hm[k + 1] - hm[k]) * w); dp = abs((pm[k + 1] - pm[k]) * w)
        key = "after_K" if F0 + k >= K else "held_before_K"
        g = gaps[key]
        if dh > g[0]:
            g[0] = dh; g[2] = t
        if dp > g[1]:
            g[1] = dp; g[3] = t
    res[seat]["gap_90Hz"] = gaps
    # 1 コマの変化の最大（上の上限）
    dH = np.abs(np.diff(hm[: end - F0 + 1])); dP = np.abs(np.diff(pm[: end - F0 + 1]))
    res[seat]["max_step"] = dict(heave=float(dH.max()), pitch=float(dP.max()),
                                 heave_after_K=float(dH[K - F0:].max()), pitch_after_K=float(dP[K - F0:].max()))
    print(seat, {k: (v if k not in ("unity_editor", "unity_player") else {kk: vv for kk, vv in v.items() if kk != "rows"}) for k, v in res[seat].items()})
jsave(OUT + "/k_boat.json", res)
