# -*- coding: utf-8 -*-
"""FLIP47：孤立波の解の表（npz）を作る（py -3.10。numpy だけ）。場面の solution_table（g47_tanklib.PYSOP）が読む形。
FLIP46 の g46_gn_npz.py（変えていない）を写して、水深 h0・a0/h0・頂 x0・表の範囲を引数にした。
  kind "gn"   ：Green–Naghdi の孤立波（BigWave_Recipes_ja.md §5.1 の式 (2.4)(2.5)。E1a の既定。論文と同じ）。
                η0 = a0 sech²(κ (x − x0))、κ = √(3 (a0/h0) / (4 (1 + a0/h0))) / h0、u = C η0/(h0 + η0)（深さによらない）、
                w = −C h0 (z + h0) ∂η0/∂x / (h0 + η0)²、C = √(g h0 (1 + a0/h0))。h0 19 m・a0/h0 0.6 で C = 17.27 m/s。
  kind "exact"：厳密な孤立波（Tanaka 1986 型。FLIP46 の g46_solitary.py を読み込んで使う。変えていない）。解の周期の箱は頂から ±40 h0 なので、
                表は頂から ±xhalf_h（既定 20 h0）の範囲だけ作る（その外の η は 1e-8 m より小さい。場面は表の端の値で延ばす）。
npz の形（g46 と同じ約束）：x[nx]（m）、z[nz]（m、静かな水面 0、上向き）、eta[nx]、u[nz, nx]・w[nz, nx]（m/s、水面より上は NaN）、
  c（m/s）、x0（m）、h0（m）、info（JSON の文字）。exact は u_ext・w_ext（水面より上を水面の値で埋めた物）も持つ。
使い方：py -3.10 g47_solitary_npz.py --kind gn --h0 19 --a 0.6 --x0 285 --x 0 1130 [--dx 0.25] [--out <path>]
"""
import os, sys, json, argparse, math
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g47_common as GC


def default_path(kind, a_over_h, h0, x0, dx):
    return GC.SOL_DIR + "/%s_a%.2f_h%g_x%g_d%g.npz" % (kind, a_over_h, h0, x0, dx)


def build(kind="gn", a_over_h=GC.A_OVER_H, h0=GC.H0, x0=GC.X0_CREST, x_lo=0.0, x_hi=GC.X_END_FULL, dx=0.25, dz=0.25,
          xhalf_h=20.0, out=None, z_lo=None):
    a0 = a_over_h * h0
    out = out or default_path(kind, a_over_h, h0, x0, dx)
    if kind == "gn":
        x = np.arange(float(x_lo) - 2.0, float(x_hi) + 2.0 + 1e-9, dx)
        zl = -h0 if z_lo is None else float(z_lo)
        z = np.arange(zl, a0 + 3.0 + 1e-9, dz)
        eta, U, W, C = GC.gn_solitary(x, z, a0, h0, x0)
        info = dict(method="GN_solitary (Feddersen et al. 2024 eq. 2.4, 2.5)", kind="gn", a0=a0, a_over_h=a_over_h, h0=h0, x0=x0, c=C,
                    units="m, m/s", layout="u[z, x]", made_by="g47_solitary_npz.py", x_range=[float(x[0]), float(x[-1])], dx=dx, dz=dz,
                    note_ja="GN の解は NS の厳密な解ではない。始めに少し細く高く（頂 約 0.68 h0）整って後ろに小さな波を残す（論文 §2.1.2）")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        np.savez_compressed(out, x=x, z=z, eta=eta.astype(np.float64), u=U.astype(np.float32), w=W.astype(np.float32),
                            c=np.float64(C), x0=np.float64(x0), h0=np.float64(h0), a_over_h=np.float64(a_over_h),
                            info=json.dumps(info, ensure_ascii=False))
        return out, info
    if kind == "exact":
        sys.path.insert(0, GC.TOOLS46)
        import g46_solitary as S
        wv = S.get_wave(a_over_h=a_over_h, h0=h0, x0=x0)
        xa = max(float(x_lo) - 2.0, x0 - xhalf_h * h0); xb = min(float(x_hi) + 2.0, x0 + xhalf_h * h0)
        x = np.arange(xa, xb + 1e-9, dx)
        z = np.arange(-h0, a0 + 1.25 + 1e-9, dz)
        wv.write_grid(out, x, z)
        d = dict(np.load(out))
        info = json.loads(str(d["info"]))
        info.update(kind="exact", a0=a0, made_by="g47_solitary_npz.py -> g46_solitary.write_grid", x_range=[float(x[0]), float(x[-1])],
                    dx=dx, dz=dz, note_ja="表の外（頂から ±%g h0 の外）は場面が表の端の値で延ばす" % xhalf_h)
        d["info"] = json.dumps(info, ensure_ascii=False)
        np.savez_compressed(out, **d)
        return out, info
    raise ValueError("知らない kind %s" % kind)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", default="gn", choices=["gn", "exact"])
    ap.add_argument("--h0", type=float, default=GC.H0)
    ap.add_argument("--a", type=float, default=GC.A_OVER_H, help="a0/h0")
    ap.add_argument("--x0", type=float, default=GC.X0_CREST)
    ap.add_argument("--x", type=float, nargs=2, default=[0.0, GC.X_END_FULL])
    ap.add_argument("--dx", type=float, default=0.25)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    p, info = build(a.kind, a.a, a.h0, a.x0, a.x[0], a.x[1], dx=a.dx, dz=a.dx, out=a.out)
    d = np.load(p)
    i = int(np.argmax(d["eta"]))
    zi = int(np.argmin(np.abs(d["z"] + 0.5 * a.h0)))
    print("wrote", p, "c %.4f m/s" % float(d["c"]), "eta max %.4f at x %.3f" % (d["eta"][i], d["x"][i]),
          "u(crest, z=-h0/2) %.4f m/s" % float(d["u"][zi, i]), "shape u", d["u"].shape)
