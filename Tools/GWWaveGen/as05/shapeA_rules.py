# -*- coding: utf-8 -*-
"""美術の見本05 のやり方 A：守る決まり（targets.json の K）を測る。見本04 の asm4_rules.py（変えない）と同じ式を、AS05A の部品
（主役波 AS05A の行・wave4 fix1・③ の波 layer3・爪の並び・Unity の描画）へ向けて使う。
py -3.10 -B Tools/GWWaveGen/as05/shapeA_rules.py <render_dir> <out.json>

  K-G2   関門（as02_asm_eval.sh → sweep_gates.json、主役波＋wave4＋layer3 を合わせた Unity の描画）
  K-S8   出っ張り（shape_common.bulge_metric、AS05A の行）と、原画視点の黄色の線の中の持ち主（numpy、合わせた場面）
  K-S9   ④ の輪郭（区間 78 の x < 360）の持ち主と、白の最も左の c（主役波の静止のメッシュと layer3 の白の頂点）
  K-S4   合わせた H(c)（主役波の行＋wave4＋layer3）のへこみ（c ≥ −14 と全部）、後ろからの輪郭（b65・b90・b115）
  K-S10  合わせた帯の幅（主役波の行＋wave4＋layer3）：0.6〜0.9 H は見本04 と ±0.25 m、低い帯は +0.5 m まで
  K-top  行 c ≥ −8 m の点の動き（AS04F との差）
  K-claws 原画視点の爪ごとの影の IoU（numpy、前 = 見本03 の爪の並び）
  K-boat Unity の原画視点の ID の画の boat_left の画素の数（見本04 の FX1 と比べる）
"""
import json
import os
import sys

import cv2
import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapeA_common as C  # noqa: E402
import s5_targets as T5  # noqa: E402
import w4_common as W  # noqa: E402

A = T5.A
SC = C.SC
sys.path.insert(0, C.REPO + "/Tools/GWWaveGen/as02")
import back_common as BC  # noqa: E402
import asm4_rules as R4  # noqa: E402

S04_BANDS = {"0.1": 40.4, "0.2": 38.35, "0.3": 36.45, "0.4": 34.5, "0.5": 32.35, "0.6": 23.95, "0.7": 20.95, "0.8": 17.4, "0.9": 12.2}


def mesh_pts():
    out = []
    for p in (C.WAVE4_F1, C.L3_JSON):
        ch, tri, _ = W.read_static(p)
        out.append(ch["position"].astype(np.float64))
    return np.concatenate(out)


def k_s4(c, Ar, Yr, X):
    H, Hu = R4.union_H(c, Yr, X)
    win = c >= -14.0
    st = {"all": BC.shape_stats(c, Hu), "c_ge_-14": BC.shape_stats(c[win], Hu[win])}
    views = BC.load_views()
    Q = A.K.sec(X)
    sil = {}
    for vn in ("b65_back65_clay", "b90_back_straight", "b115_back_minus_c"):
        v = views[vn]
        th, cth = BC.silhouette_top(c, Ar, Yr, v)
        tw, ctw = R4.sil_top_points(X, v, Q[:, 2])
        tu = np.minimum(th, tw); ctu = np.where(tw < th, ctw, cth)
        ok = np.isfinite(tu); xs = np.nonzero(ok)[0]; hg = v["h"] - tu[ok]; cw = ctu[ok] >= -14.0
        sw = BC.shape_stats(xs[cw].astype(float), hg[cw]) if cw.sum() > 5 else None
        sil[vn] = C.rnd(sw["dip_depth"], 2) if sw else None
    chk = {"H_dip_union_c_ge_-14_m": C.rnd(st["c_ge_-14"]["dip_depth"], 3), "H_dip_union_all_m": C.rnd(st["all"]["dip_depth"], 3),
           "silhouette_dip_from_behind_px_c_ge_-14": sil}
    ok = st["c_ge_-14"]["dip_depth"] <= 0.0 and st["all"]["dip_depth"] <= 0.07 and max(v for v in sil.values() if v is not None) <= 1.0
    return {"checks": chk, "verdict": "pass" if ok else "fail",
            "note_ja": "背の等高線のへこみ（back_measure）は測り直していない：背の頂から後ろ（列 ≤ 104）は AS04F のまま（K-top と同じ差の確かめで、列 ≤ 94 の点の動き 0）"}


def k_s10(c, Yr, X):
    eu = R4.bands_union(c, Yr, X)
    rows = {}
    ok = True
    for k, w04 in S04_BANDS.items():
        w = eu[k]["width_m"] if eu.get(k) else None
        d = None if w is None else w - w04
        hi = float(k) >= 0.6
        pv = d is not None and (abs(d) <= 0.25 if hi else d <= 0.5)
        ok &= pv
        rows[k] = {"width_m": w, "sample04_m": w04, "diff_m": C.rnd(d, 2) if d is not None else None, "pass": bool(pv),
                   "c_lo": eu[k]["c_lo"] if eu.get(k) else None}
    return {"bands": rows, "verdict": "pass" if ok else "fail"}


def scene_union(with_claws=True):
    cand = json.load(open(C.OUT + "/measure/cand_AS05A.json", encoding="utf-8"))
    c, Ar, Yr, RL, ms = T5.load_cand(cand)
    tris, lab = T5.scene(c, Ar, Yr, RL, ms)
    if with_claws:
        cl, _ = A.claws_tris(C.OUT + "/claws/ds33_claw_layout.json")
        tris = np.concatenate([tris] + [x["verts"][x["tris"]] for x in cl])
        lab = np.concatenate([lab] + [np.full(len(x["tris"]), 7, np.int16) for x in cl])
    return tris, lab


def k_s8_s9(tris, lab):
    c, Ar, Yr = SC.load_rows(C.ROWS05A)
    b = SC.bulge_metric(c, Ar, Yr)
    cam = A.painting_cam(2)
    _, D, L = A.raster(cam, tris, lab)
    poly = (np.asarray(SC.BULGE_DISP, float) + 0.5) * 2 - 0.5
    m = np.zeros(L.shape, np.uint8)
    cv2.fillPoly(m, [np.round(poly).astype(np.int32)], 1)
    ll = L[m > 0]
    own = {str(int(k)): C.rnd(float((ll == k).mean())) for k in np.unique(ll)}
    s8 = {"bulge_metric": b, "painting_owner_share_in_loop_by_label": own,
          "verdict": "pass" if (b["dev_from_inner_face_m"]["p95"] <= 0.15 and b["first_hit_inner_face_share"] >= 0.95) else "fail"}
    cov = L > 0
    sky_nb = np.zeros_like(cov)
    sky_nb[1:] |= ~cov[:-1]; sky_nb[:-1] |= ~cov[1:]; sky_nb[:, 1:] |= ~cov[:, :-1]; sky_nb[:, :-1] |= ~cov[:, 1:]
    edge = cov & sky_nb
    ey, ex = np.nonzero(edge)
    tr = cKDTree(np.c_[ex, ey].astype(float))
    seg = A.S4.outline_segments()["78"]
    Pp = A.ref_to_px(seg, 2)
    dd, ii = tr.query(Pp)
    ow = np.array([int(L[ey[i], ex[i]]) for i in ii])
    m4 = seg[:, 0] < 360.0

    def name(l):
        return {5: "wave4", 3: "layer3", 6: "sea", 7: "claw"}.get(l, "hero")
    o4 = [name(x) for x in ow[m4]]; on = [name(x) for x in ow[~m4]]
    share4 = {k: C.rnd(o4.count(k) / len(o4)) for k in sorted(set(o4))}
    shareN = {k: C.rnd(on.count(k) / len(on)) for k in sorted(set(on))}
    wl = []
    for p, nm in ((C.OUT + "/mesh/hero_smooth_as05a.json", "hero"), (C.L3_JSON, "layer3")):
        ch, _, _ = W.read_static(p)
        Q = A.K.sec(ch["position"].astype(np.float64)); wsd = ch["uv5"][:, 2]
        wm = wsd > 0
        wl.append({"part": nm, "white_vertices": int(wm.sum()), "leftmost_white_c_m": C.rnd(float(Q[wm, 2].min()), 2) if wm.any() else None})
    lw = min(x["leftmost_white_c_m"] for x in wl if x["leftmost_white_c_m"] is not None)
    s9 = {"region4_x_lt_360_owner_share": share4, "segment78_x_ge_360_owner_share": shareN, "white_parts": wl, "leftmost_white_c_m": lw,
          "outline_nearest_edge_px_display_max_seg78": C.rnd(dd.max() / 2, 2),
          "verdict": "pass" if (share4.get("wave4", 0) >= 0.95 and lw >= -23.4) else "fail"}
    return s8, s9


def k_top():
    c0, A0, Y0 = SC.load_rows(C.ROWS04F)
    c1, A1, Y1 = SC.load_rows(C.ROWS05A)
    k = c1 >= -8.0
    d = float(np.max(np.hypot(A1[k] - A0[k], Y1[k] - Y0[k])))
    dl = np.hypot(A1 - A0, Y1 - Y0)
    ch = np.nonzero(dl.max(1) > 1e-6)[0]
    back = float(dl[:, :95].max())
    return {"max_disp_m_rows_c_ge_-8": C.rnd(d, 4), "changed_rows_c_range": [C.rnd(c1[ch].min(), 2), C.rnd(c1[ch].max(), 2)] if len(ch) else None,
            "max_disp_m_cols_le_94_all_rows": C.rnd(back, 4), "verdict": "pass" if d <= 0.05 else "fail"}


def k_claws():
    cam = A.painting_cam(1)
    old, _ = A.claws_tris(C.P + "/sample03/assemble/claws35/ds33_claw_layout.json")
    new, lay = A.claws_tris(C.OUT + "/claws/ds33_claw_layout.json")
    od = {x["user_id"]: x for x in old}
    ious = []
    for x in new:
        o = od.get(x["user_id"])
        if o is None:
            continue
        ms = []
        for cl in (o, x):
            idb, D, L = A.raster(cam, cl["verts"][cl["tris"]], np.ones(len(cl["tris"]), np.int16))
            ms.append(L > 0)
        u = (ms[0] | ms[1]).sum()
        ious.append((x["user_id"], x["role"], float((ms[0] & ms[1]).sum() / max(u, 1))))
    v = np.array([i[2] for i in ious])
    return {"claws": len(ious), "iou_painting_view_silhouette_self": {"min": C.rnd(v.min()), "p10": C.rnd(np.percentile(v, 10)), "p50": C.rnd(np.median(v))},
            "per_claw": [[a, b, C.rnd(cc)] for a, b, cc in ious], "reseat": lay.get("as05a_shape", {}).get("moved_abs_m"),
            "note_ja": "爪ごとの原画視点の影（その爪だけを描いた形）の、見本03 の並びとの IoU。置き直しは原画のカメラを中心とする相似なので 1 になるはず",
            "verdict": "pass" if np.percentile(v, 10) >= 0.85 else "fail"}


def k_boat(render_dir):
    out = {}
    for nm, p in (("sample04_FX1", C.P4 + "/assemble/render/FX1/full/ids_noline_noclaws.png"), ("AS05A", render_dir + "/full/ids_noline_noclaws.png")):
        if not os.path.isfile(p):
            out[nm] = None
            continue
        im = cv2.imread(p)[..., ::-1]
        m = (im[..., 0] == 34) & (im[..., 1] == 0) & (im[..., 2] == 0)
        out[nm] = int(m.sum())
    r = out["AS05A"] / out["sample04_FX1"] if out.get("AS05A") is not None else None
    bl = os.path.join(render_dir, "as05a_boat.json")
    return {"boat_left_px_ids_2x": out, "ratio": C.rnd(r) if r is not None else None,
            "boat_move_log": json.load(open(bl, encoding="utf-8")) if os.path.isfile(bl) else None,
            "boat_scale": json.load(open(C.OUT + "/l3/boat_scale.json", encoding="utf-8")),
            "verdict": "pass" if (r is not None and r >= 0.98) else "fail"}


def main():
    rd, outp = sys.argv[1], sys.argv[2]
    c, Ar, Yr = SC.load_rows(C.ROWS05A)
    X = mesh_pts()
    res = {"schema": "GreatWave.AS05A.rules/1", "render_dir": rd,
           "inputs": {p: C.sha(p) for p in (C.ROWS05A, C.WAVE4_F1, C.L3_JSON, C.OUT + "/mesh/union_AS05A.json")}}
    res["K-top"] = k_top(); print("K-top", res["K-top"]["verdict"], flush=True)
    res["K-S4"] = k_s4(c, Ar, Yr, X); print("K-S4", res["K-S4"]["verdict"], res["K-S4"]["checks"], flush=True)
    res["K-S10"] = k_s10(c, Yr, X); print("K-S10", res["K-S10"]["verdict"], {k: v["diff_m"] for k, v in res["K-S10"]["bands"].items()}, flush=True)
    tris, lab = scene_union()
    s8, s9 = k_s8_s9(tris, lab)
    res["K-S8"] = s8; res["K-S9"] = s9
    print("K-S8", s8["verdict"], "K-S9", s9["verdict"], s9["region4_x_lt_360_owner_share"], s9["leftmost_white_c_m"], flush=True)
    res["K-claws"] = k_claws(); print("K-claws", res["K-claws"]["verdict"], res["K-claws"]["iou_painting_view_silhouette_self"], flush=True)
    res["K-boat"] = k_boat(rd); print("K-boat", res["K-boat"]["verdict"], res["K-boat"]["boat_left_px_ids_2x"], flush=True)
    g = os.path.join(os.path.dirname(rd), "measure", "gates_" + os.path.basename(rd), "sweep_gates.json")
    if os.path.isfile(g):
        sg = json.load(open(g, encoding="utf-8"))["gates"]
        res["K-G2"] = {"source": g, "gates": {k: {"claws": v["after_claws"], "noclaws": v["after_noclaws"], "gate_px": v["gate_px"]} for k, v in sg.items()},
                       "verdict": "pass" if all(v["after_claws"] <= v["gate_px"] and v["after_noclaws"] <= v["gate_px"] for v in sg.values()) else "fail"}
        print("K-G2", res["K-G2"]["verdict"], {k: v["claws"] for k, v in res["K-G2"]["gates"].items()}, flush=True)
    res["summary"] = {k: v.get("verdict") for k, v in res.items() if isinstance(v, dict) and "verdict" in v}
    C.jdump(outp, res)
    print(json.dumps(res["summary"], ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
