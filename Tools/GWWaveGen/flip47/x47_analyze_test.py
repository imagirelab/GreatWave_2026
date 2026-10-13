# -*- coding: utf-8 -*-
"""FLIP47：g47_analyze.py の確かめ（py -3.10 -B。読むだけ。書くのは Unity/Build/FLIP47/smoke/test_analyze/ だけ）。
  T1 Longuet-Higgins の当てはめ：答えのわかった線（L・W・θ・後ろの点）に少しの乱れを足して、当てはめが戻すか。
  T2 作った断面：平らな水＋頂の箱＋斜めに下がる噴流（縦の厚さ 1 m）。AJ・隙間・閉じた穴の面積・噴流の幅（軸に直角）が式の値と合うか。
  T3 FLIP42 R3：STUDY52 が測ったコマ（3714・3744・3745）で、g47 の水の格子＋measure_mask が STUDY52 の値と同じになるか（同じ物差しの確かめ）。
使い方：py -3.10 -B x47_analyze_test.py
"""
import sys, os, json, math
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from skimage import measure
import g47_analyze as A

OUT = A.B47 + "/smoke/test_analyze"


def poly_area(p):
    x, y = p[:, 0], p[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def t1():
    rng = np.random.default_rng(47)
    out = []
    for (L, W, thd) in ((10.0, 3.0, 29.0), (6.0, 2.3, 39.0), (12.0, 3.6, 15.0)):
        p = (L, W, math.radians(thd), 100.0, 5.0)
        cur = A.lh_curve(p, n=300)
        pts = cur + rng.normal(0, 0.03, cur.shape)
        tip = (100.0 + L * math.cos(math.radians(thd)), 5.0 - L * math.sin(math.radians(thd)))
        fit = A.lh_fit(pts, tip, area=poly_area(cur))
        out.append(dict(true=dict(L=L, W=W, theta=thd), fit=dict(L=round(fit["L"], 3), W=round(fit["W"], 3), theta=round(fit["theta_deg"], 2),
                                                                   x0=round(fit["x0"], 3), z0=round(fit["z0"], 3), rms=round(fit["rms"], 4)),
                        area_poly=round(poly_area(cur), 3), area_eq32=round(A.LH_AREA * L * W, 3),
                        ok=bool(abs(fit["L"] - L) / L < 0.01 and abs(fit["W"] - W) / W < 0.02 and abs(fit["theta_deg"] - thd) < 0.5)))
    return out


def t2():
    X = np.arange(-20.0, 20.0, A.FINE) + 0.5 * A.FINE
    Z = np.arange(-12.0, 12.0, A.FINE) + 0.5 * A.FINE
    XX, ZZ = np.meshgrid(X, Z)
    M = ZZ < 0.0
    M |= (XX >= -5.0) & (XX < 0.0) & (ZZ < 8.0)                     # 頂の箱
    res = {}
    for name, z_tip in (("high", 3.0), ("touch", 0.2)):
        Mj = M.copy()
        und = 6.0 + (z_tip - 6.0) * (XX / 6.0)                       # 噴流の下の面：x 0 で 6 m、x 6 で z_tip
        Mj |= (XX >= 0.0) & (XX < 6.0) & (ZZ >= und) & (ZZ < und + 1.0)
        eta = 8.0; xc = -2.5
        ov = A.overturn(Mj, X, Z, xc, eta, vox=0.5, h0=19.0)
        slope = (6.0 - z_tip) / 6.0
        AO_true = 6.0 * 6.0 - 0.5 * (6.0 - z_tip) * 6.0                # 噴流の下、z 0 から下の面まで（先の列で閉じる）
        w_true = 1.0 * math.cos(math.atan(slope))
        m = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in ov.items() if not k.startswith("_") and k in
             ("reach_m", "AJ_m2", "gap_low_m", "jet_low_x", "contact", "AO_m2", "jet_width_half_m", "jet_vthick_half_m", "jet_len_m", "cavity_how")}
        res[name] = dict(measured=m, expected=dict(AJ_m2=6.0, gap_low_m=z_tip, AO_m2_if_closed_at_tip=round(AO_true, 3),
                                                   jet_width_perp=round(w_true, 3), jet_len_axis=round(math.hypot(6.0, 6.0 - z_tip), 3)))
        if name == "touch":
            fit = A.lh_fit(ov["_cav_line"], (ov["x_close"], ov["z_close"]), ov["AO_m2"])
            res[name]["lh_fit_on_triangle_cavity"] = dict(L=round(fit["L"], 2), W=round(fit["W"], 2), theta=round(fit["theta_deg"], 1),
                                                          rms_over_L=round(fit["rms_over_L"], 3))
    return res


def t3():
    cx = A.Ctx(A.REPO + "/Unity/Build/FLIP42/runs/R3", dict(h0=42.0))
    s52 = json.load(open(A.STUDY52 + "/shape_measures.json", encoding="utf8"))["flip"]["R3"]
    out = {}
    for nm in ("onset", "max_overturn", "contact"):
        ref = s52[nm]; f = ref["frame"]
        r = A.coarse_frame(cx, f)
        M, X, Z = A.fine_mask(cx, f, r["xc"])
        m = A.S52.measure_mask(M, X, Z, flip_extra=dict(Lc=A.LC_S52))
        keys = ("eta_c", "x_c", "face_chord_deg_01_05", "front_x01_rel", "gap_max", "lip_thick_mid", "hood_area", "hood_height_m", "reach", "steep60_frac")
        d = {k: (m.get(k), ref.get(k)) for k in keys}
        out[nm] = dict(frame=f, maxabs=max(abs(a - b) for a, b in d.values() if isinstance(a, (int, float)) and isinstance(b, (int, float))),
                       g47_vs_study52={k: [round(a, 5) if isinstance(a, float) else a, round(b, 5) if isinstance(b, float) else b] for k, (a, b) in d.items()})
    out["still_offset"] = [cx.off, cx.off_src]
    out["bed_src"] = cx.bed_src
    return out


def main():
    os.makedirs(A.guard_out(OUT), exist_ok=True)
    res = dict(T1_lh_fit=t1(), T2_synthetic=t2(), T3_R3_same_ruler=t3())
    json.dump(A.clean(res), open(OUT + "/x47_analyze_test.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(json.dumps(A.clean(res), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
