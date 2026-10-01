# -*- coding: utf-8 -*-
# 仕上げ28：設計28修正01 の最終の評審の包みの復号（fr_pkg.py、SHA-256 11936742…）の写し（中身は同じ）。pl28_fr_motion.py が使う。
# Final reviewer's own DS27 package decoder (written from the format text in ds27_keypose.json only).
import json, os, struct
import numpy as np

class Pkg:
    def __init__(self, d, fine=True):
        self.d = d
        k = json.load(open(os.path.join(d, "ds27_keypose.json"), encoding="utf-8"))
        self.k = k
        L, R, C = k["layers"], k["rows"], k["cols"]
        self.L, self.R, self.C = L, R, C
        self.bmin = np.array(k["bbox_min"], float); self.bsz = np.array(k["bbox_size"], float)
        hi = np.fromfile(os.path.join(d, k["pos_file"]), np.uint16).reshape(L, R, C, 4)[..., :3].astype(np.float64)
        if fine and os.path.exists(os.path.join(d, k.get("pos_lo_file", "none"))):
            lo = np.fromfile(os.path.join(d, k["pos_lo_file"]), np.uint8).reshape(L, R, C, 4)[..., :3].astype(np.float64)
            q = hi + lo / 255.0 - 0.5
        else:
            q = hi
        self.P = (self.bmin + q / 65535.0 * self.bsz).astype(np.float32)   # local (world - O(tau))
        self.kt = np.array(k["knot_tau"], float)
        fr = k["frame"]; self.ft = np.array(fr["tau"], float); self.fo = np.array(fr["origin"], float)
        # Hermite slopes
        kt = self.kt
        self.M = np.empty_like(self.P)
        for i in range(L):
            a, b = max(i - 1, 0), min(i + 1, L - 1)
            self.M[i] = (self.P[b].astype(np.float64) - self.P[a]) / (kt[b] - kt[a])

    def origin(self, tau):
        tau = np.atleast_1d(np.asarray(tau, float))
        return np.stack([np.interp(tau, self.ft, self.fo[:, i]) for i in range(3)], -1)

    def at(self, tau):
        """local positions (R, C, 3) float64 at physics time tau (cubic Hermite, clamp outside)."""
        kt = self.kt
        if tau <= kt[0]:
            return self.P[0].astype(np.float64)
        if tau >= kt[-1]:
            return self.P[-1].astype(np.float64)
        i = int(np.searchsorted(kt, tau, side="right") - 1)
        i = min(i, self.L - 2)
        h = kt[i + 1] - kt[i]; s = (tau - kt[i]) / h
        h00 = 2 * s**3 - 3 * s**2 + 1; h10 = s**3 - 2 * s**2 + s; h01 = -2 * s**3 + 3 * s**2; h11 = s**3 - s**2
        return (h00 * self.P[i].astype(np.float64) + h10 * h * self.M[i] + h01 * self.P[i + 1].astype(np.float64)
                + h11 * h * self.M[i + 1])

    def world(self, tau):
        return self.at(tau) + self.origin(tau)[0]

def read_gwb(p):
    b = open(p, "rb").read()
    magic, ver, nu, nv, nfr, fps, ts, nt = struct.unpack("<4s4if2i", b[:32])
    n = nu * nv; o = 32 + n * 16
    tr = np.frombuffer(b, np.int32, nt * 3, o).reshape(-1, 3); o += nt * 12
    X = np.frombuffer(b, np.float32, n * 3 * nfr, o).reshape(nfr, nv, nu, 3).astype(np.float64)
    return X[0], tr

def warp(path):
    w = json.load(open(path, encoding="utf-8"))
    return np.array(w["t"], float), np.array(w["tau"], float), w
