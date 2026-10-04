# -*- coding: utf-8 -*-
"""美術の見本04 の形づくりの測り（土台 AS02C と候補を同じ測りで比べる）。py -3.10 -B shape_eval.py <out.json> <cand_rows.npz> [base_rows.npz]

S8  出っ張り：利用者の黄色の線の中の原画の射線の最初の当たりの、内の面の線からの距離（m、p95 ≤ 0.15）。当たりの列が内の面（≥ 200）の割合。
    参考に調べ S の「列 205〜299 に当てた円からの距離」。
G2  原画視点の輪郭の近い値（rubric の gw_wavegen_v1.preview_metrics）。78 は ④ の区間（原画の x < 360、別の青い波が受け持つ）と、
    x ≥ 360（主役波が作る）に分けて、主役波の空との境から輪郭の真値の点までの距離（表示の画素）も測る。
S10 高さの帯ごとの c の幅（調べ S-3 と同じ読み）と、見本03（AS02C）に対する比。
S4  頂の高さ H(c) のへこみ・背の等高線のへこみ（as02/back_measure.py の読み、b区域 c < −14 を除く）。
S11 三つの層：① 主の唇（c −2〜+8）・② の房（c −15.5〜−11.5）・③ 最左側の小さな房（c −23〜−17）の、唇の前の縁（列 90〜300 で y ≥ 0.2 H0 の a の最大）、
    唇の先の高さ、原画のカメラからの距離。層の間の段（前の縁の差）と、① と ② の間の凹の所（c −10〜−6）の前の縁の下がり。
形の確かめ：断面の自己交差の行の数、原画の空・船・手前の海の射線の禁止域への新しいはみ出し。
"""
import json
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shape_common as S  # noqa: E402

KP = S.REPO + "/Tools/GWWaveGen/kstar_p28"
if KP not in sys.path:
    sys.path.insert(0, KP)


def outline78_split(c, A, Y, cam):
    seg = S.K  # noqa
    import json as _j
    d = _j.load(open(S.REPO + "/Tools/PaintingTruth/targets/main_wave_outline_envelope.json", encoding="utf-8"))
    pts = {s_["id"]: np.array(s_["points_ref"], float) for s_ in d["segments"]}
    top, idb, zb, T = S.top_outline(c, A, Y, cam)
    cov = idb > 0
    # 空との境の画素（覆いの縁）
    e = np.zeros_like(cov)
    e[1:, :] |= cov[1:, :] != cov[:-1, :]
    e[:, 1:] |= cov[:, 1:] != cov[:, :-1]
    ys, xs = np.nonzero(e)
    from scipy.spatial import cKDTree
    tr = cKDTree(np.c_[xs, ys].astype(float))
    out = {}
    for k in ("78", "130", "131"):
        P = pts[k]
        D = S.ref_to_disp(P)
        dd, _ = tr.query(D)
        if k == "78":
            m4 = P[:, 0] < 360.0
            out["78_x_lt_360（④、青い波）"] = {"max": S.rnd(dd[m4].max()), "p95": S.rnd(np.percentile(dd[m4], 95))}
            out["78_x_ge_360（主役波）"] = {"max": S.rnd(dd[~m4].max()), "p95": S.rnd(np.percentile(dd[~m4], 95))}
            # ④ の区間で主役波の一番上が輪郭の真値より下にある量（表示の画素、＋ が下）
            xi = np.round(D[m4, 0]).astype(int)
            ok = (xi >= 0) & (xi < len(top)) & np.isfinite(top[np.clip(xi, 0, len(top) - 1)])
            below = top[xi[ok]] - D[m4][ok, 1]
            out["78_x_lt_360_hero_top_below_outline_px"] = {"p10": S.rnd(np.percentile(below, 10)), "p50": S.rnd(np.median(below)), "p90": S.rnd(np.percentile(below, 90))}
        else:
            out[k] = {"max": S.rnd(dd.max()), "p95": S.rnd(np.percentile(dd, 95))}
    return out


LAYERS = {"r1": (-2.0, 8.0), "r2": (-15.5, -11.5), "r3": (-23.0, -17.0)}
BAY = (-10.0, -6.0)


def front_edge(c, A, Y, cam):
    """行ごとの唇の前の縁：列 90〜300 で y ≥ 0.2·H0 の点のうち a が最大の点。"""
    rows = []
    for i in range(len(c)):
        a, y = A[i, 90:301], Y[i, 90:301]
        m = y >= 0.2 * S.H0
        if not m.any():
            rows.append(None); continue
        k = int(np.argmax(np.where(m, a, -1e9)))
        P = S.world(c[i:i + 1], A[i:i + 1, 90 + k:91 + k], Y[i:i + 1, 90 + k:91 + k]).reshape(3)
        rows.append({"c": float(c[i]), "a": float(a[k]), "y": float(y[k]), "col": 90 + k, "dist": float(np.linalg.norm(P - cam.pos)),
                     "H": float(Y[i, S.J_B:S.J_TIP + 1].max())})
    return rows


def layers(c, A, Y, cam):
    fe = front_edge(c, A, Y, cam)
    out = {}
    for k, (c0, c1) in LAYERS.items():
        sel = [r for r in fe if r and c0 <= r["c"] <= c1]
        if not sel:
            out[k] = None; continue
        a = np.array([r["a"] for r in sel]); y = np.array([r["y"] for r in sel]); d = np.array([r["dist"] for r in sel]); H = np.array([r["H"] for r in sel])
        out[k] = {"c_range": [c0, c1], "front_a_p50": S.rnd(np.median(a), 2), "front_a_max": S.rnd(a.max(), 2),
                  "front_y_p50_over_H0": S.rnd(np.median(y) / S.H0), "crest_H_p50_over_H0": S.rnd(np.median(H) / S.H0),
                  "dist_to_painting_cam_p50_m": S.rnd(np.median(d), 2)}
    bay = [r for r in fe if r and BAY[0] <= r["c"] <= BAY[1]]
    out["bay_c-10_-6"] = {"front_a_p50": S.rnd(np.median([r["a"] for r in bay]), 2) if bay else None}
    if out.get("r1") and out.get("r2") and bay:
        ab = float(np.median([r["a"] for r in bay]))
        out["steps"] = {"r1_front_minus_bay_m": S.rnd(out["r1"]["front_a_p50"] - ab, 2), "r2_front_minus_bay_m": S.rnd(out["r2"]["front_a_p50"] - ab, 2),
                        "r1_minus_r2_depth_m（② が ① よりカメラに近い）": S.rnd(out["r1"]["dist_to_painting_cam_p50_m"] - out["r2"]["dist_to_painting_cam_p50_m"], 2)}
        if out.get("r3"):
            out["steps"]["r3_front_minus_r2_front_m"] = S.rnd(out["r3"]["front_a_p50"] - out["r2"]["front_a_p50"], 2)
            out["steps"]["r2_minus_r3_depth_m（③ が ② よりカメラに近い）"] = S.rnd(out["r2"]["dist_to_painting_cam_p50_m"] - out["r3"]["dist_to_painting_cam_p50_m"], 2)
            out["steps"]["r2_crest_minus_r3_crest_over_H0"] = S.rnd(out["r2"]["crest_H_p50_over_H0"] - out["r3"]["crest_H_p50_over_H0"])
    out["front_edge_by_row"] = [{"c": S.rnd(r["c"], 2), "a": S.rnd(r["a"], 2), "y": S.rnd(r["y"], 2), "dist": S.rnd(r["dist"], 2)} if r else None for r in fe[::2]]
    return out


def checks(c, A, Y, base):
    import r2_build as B2
    import r2_common as R
    c0, A0, Y0 = base
    sx = np.array([B2.seg_selfx(A[i], Y[i], 0, None) for i in range(len(c))])
    sx0 = np.array([B2.seg_selfx(A0[i], Y0[i], 0, None) for i in range(len(c))])
    G = np.load(S.REPO + "/Unity/Build/Polish/28/r2/cache/keepout_d3.npz")
    out = {"selfx_rows_base": int((sx0 > 0).sum()), "selfx_rows_cand": int((sx > 0).sum()),
           "selfx_new_rows_c": [S.rnd(c[i], 2) for i in np.nonzero(sx > sx0)[0]]}
    try:
        Gs = R.keepout_grids(c, 3, 2, cache=S.REPO + "/Unity/Build/Polish/28/r2/cache/keepout_d3.npz")
        zp = np.load(S.REPO + "/Unity/Build/Polish/28/rec/cache/protect_grids.npz")
        Gp = np.unpackbits(zp["G"], axis=-1)[..., :R.NA].astype(bool)
        sky = []; prot = []
        for i in range(len(c)):
            f0 = R.section_fill(A0[i], Y0[i]); f1 = R.section_fill(A[i], Y[i])
            ns = int((f1 & Gs[i] & ~f0).sum()); npr = int((f1 & Gp[i] & ~f0).sum())
            if ns:
                sky.append((S.rnd(c[i], 2), ns))
            if npr:
                prot.append((S.rnd(c[i], 2), npr))
        out["sky_keepout_new_cells_rows"] = sky
        out["ship_nearsea_keepout_new_cells_rows"] = prot
        out["keepout_cell_m"] = R.GRES
    except Exception as ex:  # noqa
        out["keepout_error"] = repr(ex)
    return out


def back_s4(cand, base, out_json):
    tool = S.REPO + "/Tools/GWWaveGen/as02/back_measure.py"
    r = subprocess.run([sys.executable, "-B", tool, out_json, "AS02C=" + base, "AS04=" + cand], capture_output=True, text=True, encoding="utf-8", cwd=S.REPO)
    if r.returncode != 0:
        return {"error": r.stderr[-800:]}
    d = json.load(open(out_json, encoding="utf-8"))
    return {k: (v.get("summary") if isinstance(v, dict) else v) for k, v in d.items() if k in ("AS02C", "AS04")} or d


def main():
    out, cand = sys.argv[1], sys.argv[2]
    base = sys.argv[3] if len(sys.argv) > 3 else S.BASE_ROWS
    cb, Ab, Yb = S.load_rows(base)
    z = np.load(cand); c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
    assert np.allclose(c, cb)
    cam = S.paint_cam()
    res = {"schema": "GreatWave.AS04.shape_eval/1", "cand": cand, "cand_sha256": S.sha(cand), "base": base, "base_sha256": S.sha(base)}
    res["S8_bulge"] = {"AS02C": S.bulge_metric(cb, Ab, Yb), "AS04": S.bulge_metric(c, A, Y), "target_ja": "内の面の線からの距離 p95 ≤ 0.15 m"}
    res["G2_gate_proxy"] = {"AS02C": S.gate_proxy(cb, Ab, Yb), "AS04": S.gate_proxy(c, A, Y)}
    res["G2_outline_split"] = {"AS02C": outline78_split(cb, Ab, Yb, cam), "AS04": outline78_split(c, A, Y, cam)}
    eb, ec = S.band_extent(cb, Ab, Yb), S.band_extent(c, A, Y)
    res["S10_band_extent"] = {"AS02C": eb, "AS04": ec,
                              "ratio_AS04_over_AS02C": {k: (S.rnd(ec[k]["width_m"] / eb[k]["width_m"]) if ec.get(k) and eb.get(k) else None) for k in eb}}
    res["S11_layers"] = {"AS02C": layers(cb, Ab, Yb, cam), "AS04": layers(c, A, Y, cam)}
    res["shape_checks"] = checks(c, A, Y, (cb, Ab, Yb))
    res["S4_back"] = back_s4(cand, base, os.path.splitext(out)[0] + "_back_measure.json")
    S.jdump(out, res)
    pr = {k: res[k] for k in ("S8_bulge", "G2_gate_proxy", "G2_outline_split")}
    print(json.dumps(pr, ensure_ascii=False)[:3000])
    print(json.dumps(res["S10_band_extent"]["ratio_AS04_over_AS02C"]))
    print(json.dumps({k: v for k, v in res["S11_layers"]["AS04"].items() if k != "front_edge_by_row"}, ensure_ascii=False))
    print(json.dumps(res["shape_checks"], ensure_ascii=False)[:1500])
    print(json.dumps(res["S4_back"], ensure_ascii=False)[:1500])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
