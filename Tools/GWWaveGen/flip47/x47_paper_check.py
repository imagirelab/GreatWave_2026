# -*- coding: utf-8 -*-
"""FLIP47：g47_analyze の「論文の量」の読み方（噴流の面積 AJ・巻きの面積 Ao・W/L・θo・噴流の幅）を、論文そのものの図で確かめる。
Feddersen ら 2024 の図 5（着水の時刻の a：Re* 2400、b：風なし、c：Re* −1800）の水と海底の塗りの多角形を、g47_lit_ruler.py の
f24_paths（PDF の線と塗りの読み。別の者が書いた。読むだけ）で読み、x/h0・z/h0 の 0.002 h0 の升に塗る（g47_lit_ruler.f24_measure と同じ軸）。
その水の格子に g47_analyze.overturn と lh_fit をかけ、論文の図 7 の値（風なし AJ/Hb² 0.219・Ao/Hb² 0.352・W/L 0.300・θo 29°）と比べる。
書くのは Unity/Build/FLIP47/smoke/test_analyze/ だけ。py -3.10 -B x47_paper_check.py [--f24 <pdf>]
"""
import sys, os, json, math, argparse
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw
from skimage import measure
import g47_analyze as A
import g47_lit_ruler as LR

OUT = A.B47 + "/smoke/test_analyze"
PAPER7 = {"a_Re2400": dict(Hb_h0=0.674, AJ_Hb2=0.132, AO_Hb2=0.301, W_L=0.381, theta=39.0),
          "b_Re0": dict(Hb_h0=0.64, AJ_Hb2=0.219, AO_Hb2=0.352, W_L=0.300, theta=29.0, jet_width_h0=0.05),
          "c_Re-1800": dict(Hb_h0=0.627, AJ_Hb2=0.219, AO_Hb2=0.344, W_L=0.30, theta=None)}


def masks(pdf):
    objs = LR.pdf_objs(pdf)
    paths = LR.f24_paths(objs)
    AQUA, BROWN = (0.39, 0.82, 0.85), (0.76, 0.7, 0.5)
    X0, X1 = 138.3, 369.5
    sx = (X1 - X0) / 5.0; sz = 15.84 / 0.5; FINE = 0.002
    panels = {"a_Re2400": 568.4, "b_Re0": 442.4, "c_Re-1800": 316.5}
    out = {}
    for name, y0 in panels.items():
        sel = [(c, p) for c, p in paths if c in (AQUA, BROWN) and min(q[1] for q in p) >= y0 - 34 and max(q[1] for q in p) <= y0 + 60 and len(p) >= 3]
        xs = np.arange(38.0, 43.0, FINE) + 0.5 * FINE
        zs = np.arange(-1.0, 1.4, FINE) + 0.5 * FINE
        acc = np.zeros((len(zs), len(xs)), bool)
        for c, p in sel:
            img = Image.new("L", (len(xs), len(zs)), 0)
            ImageDraw.Draw(img).polygon([((38.0 + (px - X0) / sx - 38.0) / FINE, (1.4 - (py - y0) / sz) / FINE) for px, py in p], fill=1)
            acc |= np.asarray(img)[::-1].astype(bool)
        lab = measure.label(acc, connectivity=1)
        keep = lab[0][lab[0] > 0]
        if len(keep):
            acc = lab == np.bincount(keep).argmax()
        out[name] = (acc, xs, zs)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--f24", default=LR.DEF_F24)
    a = ap.parse_args()
    res = dict(note_ja="論文の図 5 の水の形に g47_analyze の読みをかけた値（長さは h0 で割った値）。論文の値は図 7（PAPER7）。"
                       "図の塗りの多角形を 0.002 h0 の升に塗ったので、境は ±0.002 h0 ほど。噴流の幅は論文の本文の「約 0.05」と比べる",
               pdf=os.path.basename(a.f24), panels={})
    for name, (M, X, Z) in masks(a.f24).items():
        m52 = A.S52.measure_mask(M, X, Z)
        eta, xc = m52["eta_c"], m52["x_c"]
        ov = A.overturn(M, X, Z, xc, eta, vox=0.0037, h0=1.0)
        d = dict(Hb_h0=eta, x_c_h0=xc, AJ_Hb2=ov.get("AJ_m2", 0.0) / eta ** 2,
                 AO_Hb2=(ov["AO_m2"] / eta ** 2 if ov.get("AO_m2") else None), contact=ov.get("contact"), gap_low_h0=ov.get("gap_low_m"),
                 xbp_h0=(ov.get("x_close") if ov.get("contact") else ov.get("jet_low_x")), cavity_how=ov.get("cavity_how"),
                 jet_width_h0=ov.get("jet_width_half_m"), jet_width_09_h0=ov.get("jet_width_09_m"), jet_width_profile_h0=ov.get("jet_width_profile"),
                 jet_len_h0=ov.get("jet_len_m"), reach_h0=ov.get("reach_m"),
                 s52=dict(hood_area=m52.get("hood_area"), lip_thick_mid=m52.get("lip_thick_mid"), gap_max=m52.get("gap_max"),
                          face_chord_deg_01_05=m52.get("face_chord_deg_01_05"), front_x01_rel=m52.get("front_x01_rel")))
        if ov.get("_cav_line") is not None and ov.get("AO_m2"):
            fit = A.lh_fit(ov["_cav_line"], (ov["x_close"], ov["z_close"]), ov["AO_m2"])
            d.update(W_L=fit["W_L"], theta_deg=fit["theta_deg"], L_Hb=fit["L"] / eta, fit_rms_over_L=fit["rms_over_L"],
                     AO_fit_over_direct=fit["area_fit"] / ov["AO_m2"])
        d["paper_fig7"] = PAPER7[name]
        res["panels"][name] = d
    json.dump(A.clean(res), open(A.guard_out(OUT + "/paper_fig5_check.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    for k, d in res["panels"].items():
        p = d["paper_fig7"]
        print("%-10s Hb/h0 %.3f (%.3f)  AJ/Hb2 %.3f (%.3f)  AO/Hb2 %s (%.3f)  W/L %s (%.3f)  theta %s (%s)  jetw(0.5/0.9)/h0 %s  xbp/h0 %s  contact %s gap %s" % (
            k, d["Hb_h0"], p["Hb_h0"], d["AJ_Hb2"], p["AJ_Hb2"], "%.3f" % d["AO_Hb2"] if d["AO_Hb2"] else "-", p["AO_Hb2"],
            "%.3f" % d["W_L"] if d.get("W_L") else "-", p["W_L"], "%.1f" % d["theta_deg"] if d.get("theta_deg") else "-", p["theta"],
            ("%.4f/%.4f" % (d["jet_width_h0"], d["jet_width_09_h0"])) if d.get("jet_width_h0") and d.get("jet_width_09_h0") else "-", "%.2f" % d["xbp_h0"] if d.get("xbp_h0") else "-", d["contact"],
            "%.4f" % d["gap_low_h0"] if d.get("gap_low_h0") is not None else "-"))


if __name__ == "__main__":
    main()
