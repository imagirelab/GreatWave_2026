# -*- coding: utf-8 -*-
"""FLIP42 R2 の段の独立の確かめ（続き）：最大の頂、測る点の頂、群の次の頂、R3 と R3m の差、小刻みの数、
巻き始めにそろえた断面の線の重なり（R2・R3・R5'）。確かめ役が自前で書いた。g_analyze.py・g_shape.py は使わない。
使い方：py -3.10 check_R2_more.py   出力：check_R2_more.json
"""
import json, sys
import numpy as np
sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/check/R2")
import check_R2_geom as G

OUT = G.OUT


def gauge(hf, x_scene):
    x = hf["x"]
    i = int(np.floor(x_scene / (x[1] - x[0])))
    w = (x_scene - x[i]) / (x[1] - x[0])
    e3 = hf["eta3"]  # (コマ, 3 節, x)
    g = (1 - w) * e3[:, :, i] + w * e3[:, :, i + 1]
    return np.nanmean(g, axis=1)


def main():
    geo = json.load(open(OUT + "/check_R2_geom.json", encoding="utf-8"))
    rows = json.load(open(OUT + "/check_R2_rows.json", encoding="utf-8"))
    res = {}
    hfs = {r: G.load_hf(r) for r in ["R3", "R2", "R5p", "R3m"]}
    lv = {r: geo[r]["level"] for r in ["R3", "R2", "R5p", "R3m"]}
    cfg = json.load(open(G.RUNS + "/R3/cfg.json", encoding="utf-8"))
    gauges = cfg["case"]["gauges"]

    # (1) 最大の頂（60 s から、造波板から 0〜930 m。真ん中の節と内側 3 節の平均）
    for run in ["R3", "R2"]:
        hf = hfs[run]; L = lv[run]
        xr = hf["x"] - G.X_P
        selx = (xr >= 0) & (xr <= 930)
        selt = hf["t"] >= 60
        E = hf["eta"][selt][:, selx] - L
        k = np.nanargmax(E); it, ix = np.unravel_index(k, E.shape)
        E3 = np.nanmean(hf["eta3"][selt][:, :, selx], axis=1) - L
        k3 = np.nanargmax(E3); it3, ix3 = np.unravel_index(k3, E3.shape)
        tt = hf["t"][selt]; xx = xr[selx]
        # 断面の範囲の最大の H（頂から前の谷、計画の読み方 9）
        Hs = [(r["H"], r["t"], r["xc"]) for r in rows[run]]
        Hm = max(Hs)
        res.setdefault(run, {})["max_crest_mid"] = dict(eta_c=float(E[it, ix]), t=float(tt[it]), x=float(xx[ix]))
        res[run]["max_crest_3"] = dict(eta_c=float(E3[it3, ix3]), t=float(tt[it3]), x=float(xx[ix3]))
        res[run]["max_H_section"] = dict(H=Hm[0], t=Hm[1], xc=Hm[2])
        # 測る点の時系列の最大（内側 3 節の平均）
        gm = {}
        for name, xs in gauges.items():
            g = gauge(hf, xs) - L
            j = int(np.nanargmax(g))
            gm[name] = dict(x_rel=xs - G.X_P, max=float(g[j]), t=float(hf["t"][j]), min=float(np.nanmin(g)))
        res[run]["gauge_max"] = gm
        print(run, res[run]["max_crest_mid"], res[run]["max_crest_3"], res[run]["max_H_section"])
        print("  -5 gauge", gm["kc(x-xb)=-5"])

    # (2) 群の次の頂（170 s から）
    for run in ["R3", "R2"]:
        late = [r for r in rows[run] if r["t"] >= 170.0]
        top = max(late, key=lambda r: r["H"])
        ov = [r for r in late if r["thmax"] is not None and r["thmax"] >= 90 and abs(r["xc"] - top["xc"]) < 60]
        stp = max(late, key=lambda r: (r["steep"] or 0))
        lips = [r for r in late if r["lip"]]
        mlip = max(lips, key=lambda r: r["lip"]["reach"]) if lips else None
        res[run]["second_crest"] = dict(maxH=top["H"], t=top["t"], xc=top["xc"], eta_c=top["eta_c"], steep_at_maxH=top["steep"],
                                        max_steep=stp["steep"], t_max_steep=stp["t"], xc_max_steep=stp["xc"],
                                        n_frames_ge90=len(ov), first_ge90=(None if not ov else dict(t=ov[0]["t"], xc=ov[0]["xc"], thmax=ov[0]["thmax"])),
                                        max_lip=(None if not mlip else dict(t=mlip["t"], reach=mlip["lip"]["reach"], thick=mlip["lip"]["thick_mid"])),
                                        max_thmax=max(r["thmax"] or 0 for r in late))
        print(run, "second", json.dumps(res[run]["second_crest"]))

    # (3) R3 と R3m の水面の差（断面の範囲、一番上の水面の高さの真ん中の節）
    a, b = hfs["R3"], hfs["R3m"]
    xr = a["x"] - G.X_P
    sel = (xr >= G.SEC_REL[0]) & (xr <= G.SEC_REL[1])
    fa = {int(f): i for i, f in enumerate(a["frames"])}
    d_before, d_after = [], []
    for i, f in enumerate(b["frames"]):
        f = int(f)
        if f not in fa:
            continue
        d = np.nanmax(np.abs(a["eta"][fa[f]][sel] - b["eta"][i][sel]))
        (d_before if f <= 3745 else d_after).append((float(d), f))
    res["R3_vs_R3m"] = dict(max_before_touch=max(d_before), max_after_touch=max(d_after) if d_after else None,
                            first_frame_diff=d_before[0])
    print("R3 vs R3m", res["R3_vs_R3m"])

    # (4) 小刻みの数
    def hist(v):
        u, c = np.unique(v, return_counts=True)
        return {int(k): int(n) for k, n in zip(u, c)}
    res["substeps"] = {r: hist(hfs[r]["ssn"]) for r in ["R3", "R2", "R5p", "R3m"]}
    fa = {int(f): i for i, f in enumerate(hfs["R3"]["frames"])}
    ratio = []
    for i, f in enumerate(hfs["R5p"]["frames"]):
        f = int(f)
        if f in fa and f >= 3319:
            ratio.append(hfs["R5p"]["ssn"][i] / hfs["R3"]["ssn"][fa[f]])
    ratio = np.array(ratio)
    res["R5p_over_R3_substeps"] = dict(n=int(len(ratio)), ge2=float(np.mean(ratio >= 2)), eq15=float(np.mean(np.isclose(ratio, 1.5))),
                                       lt15=float(np.mean(ratio < 1.5)), min=float(ratio.min()), max=float(ratio.max()))
    # R5' の刻みの長さ（1/24 ÷ 小刻み）と R3 の比の平均
    print("substeps", res["substeps"], res["R5p_over_R3_substeps"])

    # (5) 巻き始めにそろえた水面の線の重なり（時刻は巻き始め、場所は巻き始めの点にそろえる）
    def aligned(run, off):
        on = geo[run]["events"]["onset"]
        hf = hfs[run]; L = lv[run]
        t = on["t"] + off * G.TC
        i = int(np.argmin(np.abs(hf["t"] - t)))
        xr = hf["x"] - G.X_P - on["vertical_x"]
        return xr, hf["eta"][i] - L, float(hf["t"][i])
    ov = {}
    for pair in [("R3", "R2"), ("R3", "R5p")]:
        lst = []
        for off in (-0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3):
            xa, ea, ta = aligned(pair[0], off)
            xb, eb, tb = aligned(pair[1], off)
            grid = np.arange(-60.0, 40.0, 0.25)
            A = np.interp(grid, xa, ea); B = np.interp(grid, xb, eb)
            dd = A - B
            # 前の面（頂より前で 0〜η_c）の水平のずれ：高さ 2・5・8 m で前の面を切る x の差
            def xcross(xg, e, h):
                ic = int(np.argmax(e))
                for j in range(ic, len(e) - 1):
                    if e[j] >= h > e[j + 1]:
                        return xg[j] + (xg[j + 1] - xg[j]) * (e[j] - h) / (e[j] - e[j + 1])
                return None
            sh = {}
            for h in (2.0, 5.0, 8.0):
                p, q = xcross(grid, A, h), xcross(grid, B, h)
                sh[str(h)] = None if (p is None or q is None) else float(q - p)
            lst.append(dict(off=off, max_abs=float(np.max(np.abs(dd))), rms=float(np.sqrt(np.mean(dd ** 2))), face_shift=sh,
                            crest_diff=float(A.max() - B.max())))
        ov["%s_vs_%s" % pair] = lst
        for l in lst:
            print(pair, json.dumps(l))
    res["overlay"] = ov
    json.dump(res, open(OUT + "/check_R2_more.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)


if __name__ == "__main__":
    main()
