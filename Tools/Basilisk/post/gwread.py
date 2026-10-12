# -*- coding: utf-8 -*-
"""gw_shoal の書き出し（win_*.bin・full_*.bin・log.txt）を読む小さな関数。"""
import os, glob
import numpy as np


def read_frame(path):
    """1 コマを読む。戻り値：dict(t, x0, y0, dx, xcrest, f[ny, nx], cs[ny, nx])。行 0 が下（y の小さい方）。"""
    with open(path, "rb") as fp:
        tag = fp.read(4)
        if tag != b"GWS1":
            raise ValueError("形式が違う：%s" % path)
        hd = np.frombuffer(fp.read(40), dtype="<f8")
        nx, ny = np.frombuffer(fp.read(8), dtype="<i4")
        f = np.frombuffer(fp.read(nx * ny), dtype=np.uint8).reshape(ny, nx).astype(np.float32) / 254.0
        cs = np.frombuffer(fp.read(nx * ny), dtype=np.uint8).reshape(ny, nx).astype(np.float32) / 254.0
    return dict(t=float(hd[0]), x0=float(hd[1]), y0=float(hd[2]), dx=float(hd[3]), xcrest=float(hd[4]),
                nx=int(nx), ny=int(ny), f=f, cs=cs)


def coords(fr):
    X = fr["x0"] + fr["dx"] * np.arange(fr["nx"])
    Y = fr["y0"] + fr["dx"] * np.arange(fr["ny"])
    return X, Y


def read_log(run):
    rows = []
    with open(os.path.join(run, "log.txt")) as fp:
        for ln in fp:
            if ln.startswith("#"):
                continue
            p = ln.split()
            rows.append(dict(frame=int(p[0]), t=float(p[1]), ycrest=float(p[2]), xcrest=float(p[3]), ncells=int(p[4]),
                             vol=float(p[5]), ke=float(p[6]), pe=float(p[7]), nov=int(p[8]), slope=float(p[9]),
                             dense=int(p[10]), wall=float(p[11]), dt=float(p[12])))
    return rows


def frames(run, kind="win"):
    return sorted(glob.glob(os.path.join(run, "%s_*.bin" % kind)))
