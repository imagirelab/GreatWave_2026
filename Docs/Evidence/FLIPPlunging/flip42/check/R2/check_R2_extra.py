# -*- coding: utf-8 -*-
"""FLIP42 R2 の段の独立の確かめ（その他）：後ろの谷までの高さ、A2'、R3b の A1（0〜139 s）、R3 と R3m の水面の差の時間の変わり方、
R5' と R3 の小刻みの比の内訳、唇の最大の届く距離と最大の空気（時間の窓ごと）。
先に check_R2_geom.py・check_R2_more.py・check_R2_spec.py を走らせておく。使い方：py -3.10 check_R2_extra.py  出力：check_R2_extra.json
"""
import collections, json, sys
import numpy as np
sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/check/R2")
import check_R2_geom as G
import check_R2_spec as S

OUT = G.OUT
FPS = 24.0


def lin_maker(P):
    fi = np.linspace(P["fc"] * (1 - P["dff"] / 2), P["fc"] * (1 + P["dff"] / 2), int(P["ncomp"]))
    ki = S.k_of_f(fi); a = P["S"] / ki.sum()
    t = np.arange(4508) / FPS; R = P["ramp_s"]
    ramp = np.where(t < R, 0.5 - 0.5 * np.cos(np.pi * np.clip(t / R, 0, 1)), 1.0)
    etap = ramp * np.sum(a * np.cos(ki[:, None] * P["x_b"] + 2 * np.pi * fi[:, None] * (t[None, :] - P["t_b"])), axis=0)
    npad = 2 ** 17
    sp = np.fft.rfft(etap, npad); kp = S.k_of_f(np.fft.rfftfreq(npad, 1 / FPS))
    return fi, (lambda X, n=4508: np.fft.irfft(sp * np.exp(-1j * kp * X), npad)[:n])


def rec3(hf, xs, L):
    x = hf["x"]; i = int(np.floor(xs / (x[1] - x[0]))); w = (xs - x[i]) / (x[1] - x[0])
    return np.nanmean((1 - w) * hf["eta3"][:, :, i] + w * hf["eta3"][:, :, i + 1], axis=1) - L


def main():
    geo = json.load(open(OUT + "/check_R2_geom.json", encoding="utf-8"))
    rows = json.load(open(OUT + "/check_R2_rows.json", encoding="utf-8"))
    res = {}
    hfs = {r: G.load_hf(r) for r in ["R3", "R2", "R1b", "R5p", "R3m", "R3b"]}
    cfg = json.load(open(G.RUNS + "/R3/cfg.json", encoding="utf-8")); P = cfg["parms"]; gz = cfg["case"]["gauges"]

    # 後ろの谷（頂の後ろ 0.75 Lc まで）までの高さ
    for run in ["R3", "R2"]:
        hf = hfs[run]; L = geo[run]["level"]; on = geo[run]["events"]["onset"]
        i = int(np.argmin(np.abs(hf["t"] - on["t"])))
        xr = hf["x"] - G.X_P; e = hf["eta"][i] - L
        ic = int(np.argmin(np.abs(xr - on["xc"])))
        back = (xr < xr[ic]) & (xr >= xr[ic] - 0.75 * G.LC)
        jb = np.where(back)[0][np.nanargmin(e[back])]
        res.setdefault("rear", {})[run] = dict(rear_trough=float(e[jb]), x_rear=float(xr[jb]), H_rear=float(e[ic] - e[jb]),
                                               dist_behind=float(xr[ic] - xr[jb]), front_trough=on["yt"], front_dist=on["xt"] - on["xc"])

    # A2'（帯の出口 → −15、0.077〜0.134 Hz、線形の |F|² の重み）
    fi, lin = lin_maker(P)
    fw = np.fft.rfftfreq(4508, 1 / FPS); kw = S.k_of_f(fw); sel = (fw >= 0.077) & (fw <= 0.134)
    for run in ["R3", "R2", "R1b"]:
        L = geo[run]["level"] if run in geo else None
        Fb = np.fft.rfft(rec3(hfs[run], gz["band_exit"], L)); Lb = np.fft.rfft(lin(gz["band_exit"] - G.X_P))
        F15 = np.fft.rfft(rec3(hfs[run], gz["kc(x-xb)=-15"], L)); L15 = np.fft.rfft(lin(gz["kc(x-xb)=-15"] - G.X_P))
        Rb, R15 = Fb / Lb, F15 / L15
        dX = gz["kc(x-xb)=-15"] - gz["band_exit"]
        e = -np.angle(R15[sel] / Rb[sel]) / (kw[sel] * dX)
        w = np.abs(Lb[sel]) ** 2
        res.setdefault("A2", {})[run] = dict(speed_err=float(np.sum(w * e) / w.sum()),
                                             amp_change=float(np.sum(w * np.abs(R15[sel]) / np.abs(Rb[sel])) / w.sum()), dX=dX)

    # R3b と R3 の A1（0〜139 s の窓）
    d = fi[1] - fi[0]
    for run in ["R3b", "R3"]:
        c = json.load(open(G.RUNS + "/%s/cfg.json" % run, encoding="utf-8"))
        xp, xs = c["parms"]["x_p"], c["case"]["gauges"]["band_exit"]
        r = rec3(hfs[run], xs, geo["R3"]["level"])
        n139 = int(139 * FPS) + 1
        f2 = np.fft.rfftfreq(n139, 1 / FPS)
        Fm = np.fft.rfft(r[:n139]); Fl = np.fft.rfft(lin(xs - xp)[:n139])
        out = []
        for i0, i1 in [(1, 11), (12, 21), (22, 32)]:
            s = (f2 >= fi[i0 - 1] - d / 2) & (f2 <= fi[i1 - 1] + d / 2); Rr = Fm[s] / Fl[s]; ww = np.abs(Fl[s]) ** 2
            out.append(dict(amp=float(np.sum(ww * np.abs(Rr)) / ww.sum()), phase=float(np.sum(ww * np.angle(Rr)) / ww.sum())))
        res.setdefault("A1_0_139s", {})[run] = out

    # R3 と R3m の水面の差（断面の範囲、真ん中の節）
    a, b = hfs["R3"], hfs["R3m"]
    xr = a["x"] - G.X_P; s = (xr >= G.SEC_REL[0]) & (xr <= G.SEC_REL[1])
    fa = {int(f): i for i, f in enumerate(a["frames"])}
    tl = []
    for i, f in enumerate(b["frames"]):
        dd = np.abs(a["eta"][fa[int(f)]][s] - b["eta"][i][s])
        tl.append((int(f), float(a["t"][fa[int(f)]]), float(np.nanmax(dd)), float(np.nanpercentile(dd, 99.9))))
    res["R3_R3m"] = dict(max_to_onset=max(x[2] for x in tl if x[0] <= 3714),
                         p999_to_onset=max(x[3] for x in tl if x[0] <= 3714),
                         max_onset_to_touch=max((x[2], x[0]) for x in tl if 3714 < x[0] <= 3745),
                         p999_onset_to_touch=max(x[3] for x in tl if 3714 < x[0] <= 3745),
                         max_after_touch=max((x[2], x[0]) for x in tl if x[0] > 3745),
                         p999_after_touch=max(x[3] for x in tl if x[0] > 3745))

    # R5' と R3 の小刻みの比の内訳
    fa = {int(f): i for i, f in enumerate(hfs["R3"]["frames"])}
    c = collections.Counter()
    for i, f in enumerate(hfs["R5p"]["frames"]):
        c[(int(hfs["R3"]["ssn"][fa[int(f)]]), int(hfs["R5p"]["ssn"][i]))] += 1
    n = sum(c.values())
    res["substep_pairs"] = [dict(R3=k[0], R5p=k[1], n=v, pct=100 * v / n, ratio=k[1] / k[0]) for k, v in sorted(c.items())]

    # 唇の最大の届く距離と空気（時間の窓ごと）
    lv = {r: geo[r]["level"] for r in ["R3", "R2", "R5p", "R3m"]}
    lip = {}
    for run in ["R3", "R5p", "R3m", "R2"]:
        rr = [r for r in rows[run] if 154.5 <= r["t"] <= 158.3]
        w = {}
        for lo, hi in [(154.5, 156.0), (156.0, 157.0), (157.0, 158.3)]:
            q = [r for r in rr if lo <= r["t"] < hi and r["lip"]]
            if q:
                bq = max(q, key=lambda r: r["lip"]["reach"])
                w["%.1f-%.1f" % (lo, hi)] = dict(t=bq["t"], reach=bq["lip"]["reach"], thick=bq["lip"]["thick_mid"],
                                                 y_tip=bq["lip"]["y_tip"] - lv[run])
        air = [(r["t"], p) for r in rr for p in r["air"]]
        mx = max(air, key=lambda z: z[1]["area"]) if air else None
        big = [(t, p) for t, p in air if p["area"] >= 4.0]
        lip[run] = dict(windows=w, largest_air=(None if not mx else dict(t=mx[0], area=mx[1]["area"], x_back=mx[1]["x_back"], x_front=mx[1]["x_front"])),
                        first_air_ge4=(None if not big else dict(t=big[0][0], area=big[0][1]["area"], x_back=big[0][1]["x_back"],
                                                                 x_front=big[0][1]["x_front"], y_bot=big[0][1]["y_bot"] - lv[run])))
        # 着水の空気の面積の決まりを 1 m² にした時（参考）
        on = geo[run]["events"]["onset"]
        t1 = [r for r in rows[run] if r["t"] >= on["t"] and any(p["area"] >= 1.0 and on["xc"] - 0.25 * G.LC <= p["x_front"] <= on["xc"] + 0.6 * G.LC
                                                                 for p in r["air"])]
        lip[run]["touch_air_ge1m2"] = None if not t1 else dict(t=t1[0]["t"], jet_time=t1[0]["t"] - on["t"])
    res["lip"] = lip
    json.dump(res, open(OUT + "/check_R2_extra.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    print(json.dumps(res, ensure_ascii=False, indent=1, default=float)[:6000])


if __name__ == "__main__":
    main()
