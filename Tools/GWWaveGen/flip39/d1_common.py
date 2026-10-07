# -*- coding: utf-8 -*-
"""FLIP39 D1 共通：FLIP37 の水槽の海底・初めの波（hot start）を numpy で写したものと、読み込みの道具。
式は Tools/GWWaveGen/flip37/build_p2_tank.py の VEX（bedy3・airy・hotE）をそのまま numpy に移した。
"""
import json, os
import numpy as np

G = 9.80665
FLIP37 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37"
OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/D1"


def kdisp(om, h):
    h = np.asarray(h, float)
    k = om * om / G / np.sqrt(np.tanh(om * om * h / G))
    for _ in range(30):
        th = np.tanh(k * h)
        f = G * k * th - om * om
        df = G * th + G * k * h * (1 - th * th)
        k = k - f / df
    return k


def cg_of(om, h):
    k = kdisp(om, h); kh = k * h
    n = 0.5 * (1 + 2 * kh / np.sinh(2 * kh))
    return n * om / k


def kshoal(om, h):
    k = kdisp(om, h); kh = k * h
    n = 0.5 * (1 + 2 * kh / np.sinh(2 * kh))
    return 1.0 / np.sqrt(n * np.tanh(kh))


class Tank:
    """build_p2_tank.py の CTRL の値（run.json の parms）から海底と hot start を作る。"""

    def __init__(self, parms):
        self.p = dict(parms)

    def lensw(self, z):
        p = self.p
        zz = z - p.get("lens_z0", 0.0)
        return 1.0 - np.exp(-(zz * zz) / (p["lens_zl"] ** 2))

    def xsz(self, z):
        p = self.p
        return p["xs0"] + p["lens_A"] * self.lensw(z) + np.tan(np.radians(p.get("obl_deg", 0.0))) * (z + 0.5 * p["Lz"])

    def hrz(self, z):
        p = self.p
        return p["hr"] + p["lens_dh"] * self.lensw(z)

    def bedy(self, x, z):
        p = self.p
        x = np.asarray(x, float); z = np.asarray(z, float)
        y = -p["h0"] + np.maximum(0.0, x - self.xsz(z)) / p["slope_n"]
        y = np.minimum(y, -self.hrz(z))
        for K in (1, 2):
            d = p.get("lg%d_d" % K, 0.0)
            if d > 0:
                gg = np.exp(-((x - p["lg%d_x" % K]) / p["lg%d_sx" % K]) ** 2 - ((z - p["lg%d_z" % K]) / p["lg%d_sz" % K]) ** 2)
                y = np.maximum(y, -p["h0"] + (p["h0"] - d) * gg)
        return y

    def depth(self, x, z):
        return np.maximum(-self.bedy(x, z), 0.5)

    def hotE(self, x):
        p = self.p
        E = 0.5 * (1.0 - np.tanh((x - p["xhot"]) / p["hot_w"]))
        if p.get("xback", 0) > 0:
            E *= 0.5 * (1.0 + np.tanh((x - p["xback"]) / p["hot_w"]))
        return E

    def surface_flat(self, x, z):
        """平らな沖（水深 h0）の式で、t=0 の水面 η と水面の速度ポテンシャル φs（線形・2 次の項）を返す。
        斜面の上の WKB と浅水変形は入れない（線形の平らな海の比べ専用）。"""
        p = self.p
        om = 2 * np.pi / p["T"]; h0 = p["h0"]; H = p["H"]
        k0 = kdisp(om, h0)
        E = self.hotE(x)
        cr = np.radians(p.get("cross_deg", 0.0))
        if cr > 1e-4:
            kz = k0 * np.sin(cr); kx0 = k0 * np.cos(cr)
            a = 0.25 * H * E
            th = kx0 * x - kx0 * p["xc0"]
            zr = z - p.get("cross_z0", 0.0)
            eta = 2 * a * np.cos(kz * zr) * np.cos(th)
            phi = 2 * a * G / om * np.cos(kz * zr) * np.sin(th)
            return eta, phi
        a = 0.5 * H * E
        th = k0 * x - k0 * p["xc0"]
        sh0 = np.sinh(k0 * h0)
        e2c = 0.25 * k0 * np.cosh(k0 * h0) * (2 + np.cosh(2 * k0 * h0)) / sh0 ** 3
        s2w = p.get("stokes2", 1.0)  # 平らな沖では 1
        eta = a * np.cos(th) + s2w * e2c * a * a * np.cos(2 * th)
        c2 = 0.75 * a * a * om * k0 / sh0 ** 4
        phi = G * a / om * np.sin(th) + s2w * c2 / (2 * k0) * np.cosh(2 * k0 * h0) * np.sin(2 * th)
        return eta + 0 * z, phi + 0 * z


def load_hf(path):
    d = np.load(path, allow_pickle=True)
    g = json.loads(str(d["grid"]))
    e = d["eta"].astype(np.float32)
    x = g["x0"] + g["dx"] * np.arange(e.shape[2])
    z = g["z0"] + g["dz"] * np.arange(e.shape[1])
    return dict(eta=e, seg=d["seg"], t=np.asarray(d["t"], float), frames=np.asarray(d["frames"]), x=x, z=z, grid=g)


def load_run(rid):
    base = os.path.join(FLIP37, "P2", rid)
    rj = json.load(open(os.path.join(base, "run.json"), encoding="utf-8"))
    return rj, load_hf(os.path.join(base, "hf.npz"))


def load_p3():
    base = os.path.join(FLIP37, "P3", "H25_R18_mg")
    parts = []
    for L in "ABCDEFGHIJKL":
        f = os.path.join(base, "hf_%s.npz" % L)
        if os.path.isfile(f):
            parts.append(load_hf(f))
    eta = np.concatenate([p["eta"] for p in parts]); seg = np.concatenate([p["seg"] for p in parts])
    t = np.concatenate([p["t"] for p in parts]); fr = np.concatenate([p["frames"] for p in parts])
    o = np.argsort(fr); _, u = np.unique(fr[o], return_index=True); o = o[u]
    return dict(eta=eta[o], seg=seg[o], t=t[o], frames=fr[o], x=parts[0]["x"], z=parts[0]["z"], grid=parts[0]["grid"])


def jdump(obj, path):
    def conv(o):
        if isinstance(o, (np.floating,)):
            return None if not np.isfinite(o) else float(o)
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, np.ndarray):
            return [conv(v) for v in o.tolist()] if o.ndim else conv(o.item())
        if isinstance(o, float):
            return None if not np.isfinite(o) else o
        if isinstance(o, dict):
            return {k: conv(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [conv(v) for v in o]
        return o
    with open(path, "w", encoding="utf-8") as f:
        json.dump(conv(obj), f, ensure_ascii=False, indent=1)
