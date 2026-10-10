"""RT48 Unity 側の試し：合成の曲線（計算の結果ではない）を、計画 §2.4 の焼きの形で書く。

本物の焼き（r_bake.py、R3 の記録と R3e から）ができるまで、Unity の部品を確かめるために使う。形は式で作った作り物で、
FLIP42 の数（時刻・高さ・位置）に近い所に置いただけ。見た目の判定や報告の数には使わない。

入っているもの：
  ・コマ 3319〜3889（138.25〜162.0 s、24 コマ/秒、571 コマ）、主な曲線 x 100〜925 m。
  ・前へかぶさる曲線：上の方の点を前へずらす（せん断）。153 s ごろから前の面が鉛直を越え、唇の先（x が減り始める点）ができる。
  ・目印の対応：頂と唇の先（両方のコマにある時）。8,192 点。
  ・C4 で外れた組の試し：組 [3599, 3600] と [3600, 3601] を補間しない（reason 2）。
  ・つながり方の変わり（K）：3740 コマから離れた水（3 つ）、3745 コマから水に囲まれた空気（1 つ）。K から先は補間しない（reason 1）。
  ・座席ごとの船からの終わり：最初の接触（合成では 3745 コマと置く）より後で、船体 ±6 m に多価の列が入る 1 コマ前。
  ・ref_python.json：Unity と比べる値（float64）。時刻から組・割合、点の位置と法線、船の上下と縦揺れ。
使い方：python u_synth.py [出力のフォルダー（既定 Unity/Build/RT48/bake/synth）]
"""
import json
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import u_bakeio as bio  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48/bake/synth"
F0, F1 = 3319, 3889
CONTACT_FRAME = 3745
FAIL_K = 3599  # C4 で外れたとする k（[k, k+1] と [k+1, k+2] を補間しない）
C = 260.0 / 17.75  # 頂の進む速さ（合成）
G = 9.81
SEATS = [556.0, 574.0]


def sstep(a, b, t):
    s = min(1.0, max(0.0, (t - a) / (b - a)))
    return s * s * (3 - 2 * s)


def params(t):
    xc = 262.0 + C * (t - 138.25)
    if t <= 154.7:
        H = 3.9 + 5.7 * sstep(138.25, 154.7, t)
    elif t <= 156.0:
        H = 9.6 - 0.8 * (t - 154.7) / 1.3
    else:
        H = 8.8 - 4.4 * min(1.0, (t - 156.0) / 6.0)
    w = 11.0 - 2.0 * sstep(138.25, 156.0, t)
    S = 14.0 * sstep(151.5, 155.0, t) + 2.0 * sstep(155.0, 157.0, t)
    xp = 394.0 + C * (t - 138.25)
    Hp = 1.2 + 3.8 * math.exp(-(t - 138.25) / 6.0)
    return xc, H, w, S, xp, Hp


def main_curve(t):
    xc, H, w, S, xp, Hp = params(t)
    x = np.linspace(100.0, 925.0, 33001)
    y = H * np.exp(-((x - xc) / w) ** 2)
    y -= 0.22 * H * (np.exp(-((x - xc - 2.3 * w) / (1.3 * w)) ** 2) + np.exp(-((x - xc + 2.3 * w) / (1.3 * w)) ** 2))
    y += Hp * np.exp(-((x - xp) / (1.5 * w)) ** 2)
    y += 0.25 * np.sin(2 * np.pi * (x - 9.0 * t) / 37.0) + 0.12 * np.sin(2 * np.pi * (x + 4.0 * t) / 23.0)
    frac = np.clip(y / H, 0.0, 1.0)
    g = S * frac ** 4 * np.exp(-((x - xc) / (1.6 * w)) ** 2)
    return np.stack([x + g - bio.X_ORIGIN, y], axis=1)


def ellipse(cx, cy, rx, ry, n, ccw=True):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    if not ccw:
        a = -a
    return np.stack([cx + rx * np.cos(a), cy + ry * np.sin(a)], axis=1)


def main():
    t_start = time.time()
    frames = np.arange(F0, F1 + 1)
    F = len(frames)
    curves, crest_i, crest_x, lip_i = [], [], [], []
    x_prev = 262.0 - bio.X_ORIGIN
    for f in frames:
        c = main_curve(bio.frame_time(f))
        ic = bio.find_crest(c, x_prev, 40.0)
        il = bio.find_lip_tip(c, ic)
        curves.append(c)
        crest_i.append(ic)
        lip_i.append(il)
        crest_x.append(float(c[ic, 0]))
        x_prev = c[ic, 0]

    # 閉じた線（コマごと）
    loops = []
    f_spray = 3740
    k_sp = f_spray - F0
    tip = curves[k_sp][lip_i[k_sp]] if lip_i[k_sp] >= 0 else curves[k_sp][crest_i[k_sp]]
    t_sp = bio.frame_time(f_spray)
    blobs = [((C + 3.0, 2.0), (0.45, 0.35)), ((C + 4.5, 0.5), (0.30, 0.25)), ((C + 1.5, 3.0), (0.25, 0.20))]
    for k, f in enumerate(frames):
        t = bio.frame_time(f)
        if f >= f_spray:
            dt = t - t_sp
            for bi, ((vx, vy), (rx, ry)) in enumerate(blobs):
                cx = tip[0] + 1.0 + vx * dt
                cy = tip[1] + 0.6 + vy * dt - 0.5 * G * dt * dt
                if dt <= 1.6 and cy > -0.5:
                    loops.append((k, 0, ellipse(cx, cy, rx, ry, 24, ccw=(bi % 2 == 0))))
        if f >= CONTACT_FRAME:
            xc, H, w, S, xp, Hp = params(t)
            s = max(0.3, 1.0 - (t - 156.0) / 8.0)
            loops.append((k, 1, ellipse(xc + 4.0 - bio.X_ORIGIN, 0.3 * H, 1.6 * s, 0.9 * s, 32)))

    # つながり方（窓 ±30 m の閉じた空気の数・閉じた水の数）と K
    topo = []
    for k in range(F):
        n_air = n_wat = 0
        for (fi, kind, p) in loops:
            if fi != k:
                continue
            if np.any(np.abs(p[:, 0] - crest_x[k]) <= 30.0):
                if kind == 1:
                    n_air += 1
                else:
                    n_wat += 1
        topo.append((n_air, n_wat))
    K = -1
    for k in range(1, F):
        if topo[k] != topo[k - 1]:
            K = int(frames[k])
            break

    # 組：目印の対応で取り直す
    P = F - 1
    N = bio.N_POINTS
    pairs = np.zeros((P, 2, N, 2), dtype="<f4")
    interp, reason, lmc, lml = [], [], [], []
    for p in range(P):
        ka, kb = p, p + 1
        lm_a, lm_b = [crest_i[ka]], [crest_i[kb]]
        has_lip = lip_i[ka] >= 0 and lip_i[kb] >= 0
        if has_lip:
            lm_a.append(lip_i[ka])
            lm_b.append(lip_i[kb])
        A, B, idx = bio.resample_pair(curves[ka], curves[kb], lm_a, lm_b, N)
        pairs[p, 0], pairs[p, 1] = A, B
        lmc.append(int(idx[0]))
        lml.append(int(idx[1]) if has_lip else -1)
        fa = int(frames[ka])
        if K > 0 and fa + 1 >= K:
            interp.append(0)
            reason.append(1)
        elif fa in (FAIL_K, FAIL_K + 1):
            interp.append(0)
            reason.append(2)
        else:
            interp.append(1)
            reason.append(0)

    # 座席ごとの船からの終わり（読み方 1・2 を曲線に当てる：鉛直の線の交わりが 3 以上、または閉じた水に当たる列）
    def multivalued(k, x0, x1):
        c = curves[k]
        for xq in np.arange(x0, x1 + 1e-9, 0.25):
            xs = xq - bio.X_ORIGIN
            if bio.crossings(c, xs) >= 3:
                return True
            for (fi, kind, pp) in loops:
                if fi == k and kind == 0 and bio.crossings(pp, xs, closed=True) > 0:
                    return True
        return False
    seat_end = []
    for s in SEATS:
        end = bio.frame_time(F1)
        for k in range(CONTACT_FRAME + 1 - F0, F):
            if multivalued(k, s - 6.0, s + 6.0):
                end = bio.frame_time(int(frames[k - 1]))
                break
        seat_end.append(end)

    meta = {
        "source_id": "synth",
        "label_ja": "合成の試しの曲線（式で作った作り物。計算の結果ではない）",
        "caption1_ja": "この波は式で作った試しの曲線を横に並べたもので、長さの向きにどこも同じ形です（計算の結果ではありません）",
        "is_synthetic": True,
        "interp_verified": False,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool": "Tools/GWWaveGen/rt48/u_synth.py",
        "note_ja": "Unity の部品の試しのための作り物。せん断でかぶさりを作り、3740 コマから離れた水、3745 コマから囲んだ空気を置いた。",
        "x_origin_m": bio.X_ORIGIN, "n_points": N, "fps": bio.FPS,
        "frame_first": int(F0), "frame_count": int(F), "pair_count": int(P), "k_frame": int(K),
        "pair_interp": interp, "pair_reason": reason, "pair_lm_crest": lmc, "pair_lm_lip": lml,
        "crest_x_m": [x + bio.X_ORIGIN for x in crest_x],
        "x_range_m": [100.0, 925.0], "taper_m": [100.0, 200.0, 825.0, 925.0],
        "onset_s": 154.7, "onset_x_m": 508.0, "contact_s": bio.frame_time(CONTACT_FRAME), "contact_x_m": 527.0,
        "side_end_s": bio.frame_time(F1), "seat_x_m": SEATS, "seat_end_s": seat_end,
    }
    meta = bio.write_bake(OUT, meta, pairs, loops)

    # ---------------- 読み戻して、Unity と比べる値（float64）
    meta_r, pr, lp = bio.load_bake(OUT)
    assert np.array_equal(pr, pairs)
    t0 = bio.frame_time(F0)

    def ft(f):
        return bio.frame_time(f)
    times = [t0, 140.0 + 0.37 / 24, 145.5 + 0.1 / 24, 149.3 + 0.23 / 24, ft(3600) + 0.5 / 24, ft(3601) + 0.25 / 24,
             152.0 + 0.61 / 24, 154.0 + 0.44 / 24, 154.7 + 0.83 / 24, ft(K - 2) + 0.5 / 24,
             ft(K - 1) + 0.5 / 24, 155.9 + 0.2 / 24, ft(3745), 156.3 + 0.7 / 24, 156.6 + 0.4 / 24, 157.0 + 0.1 / 24,
             ft(3771), 158.0 + 0.5 / 24, 160.0 + 0.9 / 24, ft(F1)]
    tap = bio.taper_stored(meta_r)
    states = []
    for t in times:
        st = bio.state_at(meta_r, t)
        cur = bio.curve_for_state(pr, st)
        disp = bio.displayed(cur, tap)
        idx = sorted(set([0, 1, 2, 1000, 4095, 4096, 8190, 8191, meta_r["pair_lm_crest"][st["pair"]]] +
                         ([meta_r["pair_lm_lip"][st["pair"]]] if meta_r["pair_lm_lip"][st["pair"]] >= 0 else [])))
        pts = []
        for i in idx:
            i0, i1 = max(0, i - 1), min(N - 1, i + 1)
            tx, ty = disp[i1, 0] - disp[i0, 0], disp[i1, 1] - disp[i0, 1]
            L = math.hypot(tx, ty)
            pts.append({"i": int(i), "xs": float(disp[i, 0]), "y": float(disp[i, 1]), "nx": -ty / L, "ny": tx / L})
        boats = []
        for s in SEATS:
            h, pdeg, mode, _ = bio.boat_at(pr, meta_r, t, s)
            boats.append({"seat_x": s, "heave": h, "pitch_deg": pdeg, "mode": mode})
        states.append({"t": t, "frame": st["frame"], "pair": st["pair"], "alpha": st["alpha"], "interp": st["interp"],
                       "last": st["last"], "points": pts, "boats": boats})

    # かぶさり（多価）のある組の数と、補間した線の自分との交わり（窓 ±30 m、間引いて見る）
    over_pairs = sum(1 for p in range(P) if interp[p] and meta_r["pair_lm_lip"][p] >= 0)
    selfx = []
    for p in range(0, P, 6):
        if not interp[p]:
            continue
        for a in (1 / 30, 0.5, 29 / 30):
            cur = pr[p, 0].astype(np.float64) + (pr[p, 1].astype(np.float64) - pr[p, 0]) * a
            m = np.abs(cur[:, 0] - (crest_x[p])) <= 30.0
            ids = np.nonzero(m)[0]
            selfx.append(bio.segments_intersect_count(cur[ids[0]:ids[-1] + 1]))
    ref = {
        "schema": "GreatWave.RT48.synth_ref/1", "bake_dir": OUT, "meta_sha256": bio.sha256_file(os.path.join(OUT, "meta.json")),
        "k_frame": K, "contact_frame": CONTACT_FRAME, "fail_k": FAIL_K, "topology_first_change": topo[K - F0] if K > 0 else None,
        "pairs_interp": int(sum(interp)), "pairs_hold": int(P - sum(interp)), "pairs_with_lip_interp": over_pairs,
        "frames_with_lip": int(sum(1 for i in lip_i if i >= 0)), "first_lip_frame": int(frames[[i >= 0 for i in lip_i].index(True)]),
        "self_intersections_checked": len(selfx), "self_intersections_found": int(sum(selfx)),
        "seat_x": SEATS, "seat_end_s": seat_end, "hull_dx": bio.HULL_DX.tolist(), "states": states,
        "seconds": time.time() - t_start,
    }
    with open(os.path.join(OUT, "ref_python.json"), "w", encoding="utf-8") as f:
        json.dump(ref, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in ref.items() if k != "states"}, ensure_ascii=False))
    print("files", meta["files_name"], meta["files_bytes"])


if __name__ == "__main__":
    main()
