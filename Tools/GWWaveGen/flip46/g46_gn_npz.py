# -*- coding: utf-8 -*-
"""FLIP46：GN（Green–Naghdi）の孤立波の npz を作る（py -3.10。numpy だけ）。Tanaka（1986）の厳密な解（g46_solitary.write_grid、別の者が作る）が
出るまでの代わり。場面（g46_tank.hiplc の solution_table）と g46_run.py は、どちらの npz も同じ形で読む。
式は BigWave_Recipes_ja.md §5.1（論文 Feddersen ら 2024 の式 (2.4)(2.5)）：
  η0 = a0 sech²(κ (x − x0))、κ = √(3 (a0/h0) / (4 (1 + a0/h0))) / h0、u = C η0/(h0 + η0)（深さによらない）、
  w = −C h0 (z + h0) ∂η0/∂x / (h0 + η0)²、C = √(g h0 (1 + a0/h0))。a0/h0 0.6・h0 17 m・x0 98.345 m で C = 16.33 m/s。
npz の形（g46_solitary.write_grid と合わせる約束。場面の読み手はどちらの並びも受ける）：
  x[nx]（m、上流の壁が 0）、z[nz]（m、静かな水面 0、上向き）、eta[nx]（m）、u[nz, nx]・w[nz, nx]（m/s、水面より上は NaN）、
  c（m/s）、x0（m）、h0（m）、info（JSON の文字：method・a0 など）。
使い方：py -3.10 g46_gn_npz.py [--out <path>] [--check]
  --check：尾根の式を論文の本文の値（x' 19 の水深 0.082、y' ±2・±4 の勾配 0.052・0.028）と比べて表示する。
"""
import os, sys, json, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g46_common as GC


def build(out=GC.GN_PLACEHOLDER, a0=GC.A0 * GC.H0, h0=GC.H0, x0=GC.X0_CREST, dx=0.25, dz=0.25, x1=328.0):
    x = np.arange(0.0, x1 + 1e-9, dx)
    z = np.arange(-h0, a0 + 2.0 + 1e-9, dz)
    eta, U, W, C = GC.gn_solitary(x, z, a0=a0, h0=h0, x0=x0)
    info = dict(method="GN_solitary_placeholder", a0=a0, h0=h0, x0=x0, c=C, units="m, m/s", layout="u[z, x]",
                made_by="g46_gn_npz.py", note_ja="Tanaka の厳密な解が出るまでの代わり（BigWave_Recipes_ja.md §5.1 の式）")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    np.savez_compressed(out, x=x, z=z, eta=eta.astype(np.float64), u=U.astype(np.float32), w=W.astype(np.float32),
                        c=np.float64(C), x0=np.float64(x0), h0=np.float64(h0), info=json.dumps(info, ensure_ascii=False))
    return out, info


def check_ridge():
    h = -GC.bed_z(19.0 * GC.H0, 0.0) / GC.H0
    out = dict(depth_x19_centre=h)
    for yp in (2.0, 4.0):
        y = yp * GC.H0
        s = (GC.bed_z(10 * GC.H0 + 0.5, y) - GC.bed_z(10 * GC.H0 - 0.5, y)) / 1.0
        out["slope_y%g" % yp] = float(s)
    out["paper"] = dict(depth_x19_centre=0.082, slope_y2=0.052, slope_y4=0.028)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=GC.GN_PLACEHOLDER)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    p, info = build(a.out)
    d = np.load(p)
    i = int(np.argmax(d["eta"]))
    zi = int(np.argmin(np.abs(d["z"] + 0.5 * GC.H0)))
    print("wrote", p, "c %.3f m/s" % float(d["c"]), "eta max %.3f at x %.3f" % (d["eta"][i], d["x"][i]),
          "u(crest, z=-h0/2) %.3f m/s" % float(d["u"][zi, i]), "shape u", d["u"].shape)
    if a.check:
        print(json.dumps(check_ridge(), indent=1))
