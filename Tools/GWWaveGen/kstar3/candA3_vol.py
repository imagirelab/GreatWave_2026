# -*- coding: utf-8 -*-
"""Q20 loop 3 cand A3: access to the TEMPORARY smoothed large-form volume of the reference model.

The volume is built outside the repo (Unity/Build/Q20L3/candA3/_model_side/candA3_refsmooth.py, the only script that
reads the model's OBJ) and deleted at the end of the study.  This module only reads that temporary npz: an indicator
volume G (uint8, 250 = inside) on planes c = cs[k], pixels (y0 + i*res, a0 + j*res), already smoothed.
"""
import json
import numpy as np
from skimage import measure


class Vol:
    def __init__(self, path, key="G"):
        z = np.load(path)
        self.G = z[key]
        self.cs = z["cs"].astype(float); self.a0 = float(z["a0"]); self.y0 = float(z["y0"]); self.res = float(z["res"])
        self.placement = json.loads(str(z["placement"])); self.params = json.loads(str(z["params"]))
        self.ny, self.na = self.G.shape[1:]

    def plane(self, c):
        """indicator in [0, 1] of the plane c (linear between the stored planes; 0 outside the model's c range)."""
        if c <= self.cs[0] or c >= self.cs[-1]:
            return np.zeros((self.ny, self.na), np.float32)
        k = int(np.searchsorted(self.cs, c)) - 1
        t = (c - self.cs[k]) / (self.cs[k + 1] - self.cs[k])
        return ((1 - t) * self.G[k].astype(np.float32) + t * self.G[k + 1].astype(np.float32)) / 250.0

    def to_ay(self, rc):
        """skimage contour (row, col) -> (a, y)."""
        return np.stack([self.a0 + rc[:, 1] * self.res, self.y0 + rc[:, 0] * self.res], -1)

    def contours(self, c, level=0.5, floor_y=None):
        """level-set contours of the plane c.  floor_y: the region below this height is filled (sea / base), so the
        main contour runs from the left border to the right border over the wave."""
        P = self.plane(c).copy()
        if floor_y is not None:
            iy = int(round((floor_y - self.y0) / self.res))
            P[:max(iy, 0)] = 1.0
        # pad with zeros on the sides/top so that every contour is closed except the one through the floor
        cs = measure.find_contours(P, level)
        return [self.to_ay(q) for q in cs], P
