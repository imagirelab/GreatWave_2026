# -*- coding: utf-8 -*-
"""FLIP45：u_surfsize の追加の試し（hython、1 分前後）。
run2 の粒子（u_surfsize.py が作った particles.bgeo.sc）に、線形の理論の速さ v（同じ 30 成分、有限水深）を付けて、
組 A（Voxel Scale 1.0）と C（2.0）の面を作り、上の面の三角形だけを残し（使われない点も消す）、法線 N を付けて、
P・N・v を持つ Alembic を 1 コマ書き、大きさを測る。判定の幅は criteria_abc_frozen.json（走らせる前に固定）。
使い方: hython u_surfsize_abc.py <run2 のフォルダー> <出力のフォルダー>
2026-10-12 進行役が書いた。"""
import ctypes
import json
import math
import os
import sys
import time
from ctypes import wintypes

import numpy as np
import hou

SRC, OUT = sys.argv[1].replace("\\", "/"), sys.argv[2].replace("\\", "/")
os.makedirs(OUT, exist_ok=True)
T_ALL = time.perf_counter()


def unthrottle_self():
    k = ctypes.WinDLL("kernel32", use_last_error=True)

    class PPTS(ctypes.Structure):
        _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.GetPriorityClass.argtypes = [wintypes.HANDLE]
    h = k.GetCurrentProcess()
    s = PPTS(1, 0x1, 0x0)
    r1 = bool(k.SetProcessInformation(h, 4, ctypes.byref(s), ctypes.sizeof(s)))
    r2 = bool(k.SetPriorityClass(h, 0x4000))
    return dict(pid=os.getpid(), power_throttling_off=r1, below_normal=r2, priority_class=hex(k.GetPriorityClass(h)))


PRIO = unthrottle_self()
print("priority", PRIO)

# 波（u_surfsize.py と同じ）
G, D, T = 9.81, 20.0, 7.0
OM = 2 * math.pi / T
k = OM * OM / G
for _ in range(60):
    f = G * k * math.tanh(k * D) - OM * OM
    df = G * math.tanh(k * D) + G * k * D / math.cosh(k * D) ** 2
    k -= f / df
NC, A = 30, 0.186
TH = np.radians(np.linspace(-45.0, 45.0, NC))
XF, ZF = 250.0, 0.0

pg = hou.Geometry()
pg.loadFromFile(SRC + "/particles.bgeo.sc")
P = np.frombuffer(pg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64)
# 線形の速さ（焦点の時刻、t = 0 で位相 0）：u_h = Σ a ω cosh(k(y+d))/sinh(kd) cos(ψ) (cosθ, sinθ)、u_y = Σ a ω sinh(k(y+d))/sinh(kd) sin(ψ)
# 水面より上の粒子はないが、y > 0 では式をそのまま使う（目安の値。大きさを測るためだけ）
V = np.zeros_like(P)
yd = np.clip(P[:, 1], -D, None) + D
ch, sh = np.cosh(k * yd) / math.sinh(k * D), np.sinh(k * yd) / math.sinh(k * D)
for th in TH:
    psi = k * ((P[:, 0] - XF) * math.cos(th) + (P[:, 2] - ZF) * math.sin(th))
    c, s = np.cos(psi), np.sin(psi)
    V[:, 0] += A * OM * ch * c * math.cos(th)
    V[:, 2] += A * OM * ch * c * math.sin(th)
    V[:, 1] += A * OM * sh * s
pg.addAttrib(hou.attribType.Point, "v", (0.0, 0.0, 0.0))
pg.setPointFloatAttribValuesFromString("v", V.astype(np.float32).tobytes())
pfile = OUT + "/particles_v.bgeo.sc"
pg.saveToFile(pfile)
del pg
print("particles", P.shape[0], "|v| max %.2f" % float(np.linalg.norm(V, axis=1).max()))

ETAMIN = -5.287  # run2 の記録の値
YCUT = ETAMIN - 1.0
TRIM_VEX = """
int pts[] = primpoints(0, @primnum);
vector c = 0;
foreach (int p; pts) c += point(0, "P", p);
c /= max(1, len(pts));
if (c.x < 167 || c.x > 303 || c.z < 1 || c.z > 71 || c.y < %f) removeprim(0, @primnum, 1);
""" % YCUT

geo = hou.node("/obj").createNode("geo", "u_surfsize_abc")
fin = geo.createNode("file", "particles")
fin.parm("file").set(pfile)
res = []
for name, vs in [("A", 1.0), ("C", 2.0)]:
    pfs = geo.createNode("particlefluidsurface", "pfs_" + name)
    pfs.setInput(0, fin)
    pfs.parm("particlesep").set(0.25)
    pfs.parm("voxelsize").set(vs)
    pfs.parm("adaptivity").set(0.005)
    pfs.parm("conversion").set("poly")
    t0 = time.perf_counter()
    pfs.cook(force=True)
    t_surf = time.perf_counter() - t0
    div = geo.createNode("divide", "tri_" + name)
    div.setInput(0, pfs)
    trim = geo.createNode("attribwrangle", "trim_" + name)
    trim.setInput(0, div)
    trim.parm("class").set(1)
    trim.parm("snippet").set(TRIM_VEX)
    nrm = geo.createNode("normal", "n_" + name)
    nrm.setInput(0, trim)
    # 点の法線（「付ける所」の選びに Points があればそれを選ぶ）
    tp = nrm.parm("type")
    if tp is not None:
        for it, lb in zip(tp.parmTemplate().menuItems(), tp.parmTemplate().menuLabels()):
            if lb.lower().startswith("point"):
                tp.set(it)
                break
    keep = geo.createNode("attribdelete", "keep_" + name)
    keep.setInput(0, nrm)
    keep.parm("ptdel").set("* ^P ^N ^v")
    keep.parm("vtxdel").set("*")
    keep.parm("primdel").set("*")
    keep.parm("dtldel").set("*")
    keep.cook(force=True)
    g = keep.geometry()
    npt, npr = g.intrinsicValue("pointcount"), g.intrinsicValue("primitivecount")
    attrs = [a.name() for a in g.pointAttribs()]
    # 使われない点（三角形が参照しない点）を数える
    used = set()
    for pr in g.prims():
        for v in pr.vertices():
            used.add(v.point().number())
    unused = npt - len(used)
    rop = hou.node("/out").createNode("alembic", "abc_" + name)
    path = OUT + "/surface_%s_PNv.abc" % name
    rop.parm("use_sop_path").set(1)
    rop.parm("sop_path").set(keep.path())
    rop.parm("trange").set(0)
    rop.parm("filename").set(path)
    t1 = time.perf_counter()
    rop.render()
    t_abc = time.perf_counter() - t1
    size = os.path.getsize(path)
    rd = geo.createNode("alembic", "read_" + name)
    rd.parm("fileName").set(path)
    lm = rd.parm("loadmode")
    for it, lb in zip(lm.parmTemplate().menuItems(), lm.parmTemplate().menuLabels()):
        if "houdini" in lb.lower():
            lm.set(it)
            break
    rd.cook(force=True)
    rg = rd.geometry()
    back_attrs = [(a.name(), a.size()) for a in rg.pointAttribs()]
    has_v = any(n == "v" and s == 3 for n, s in back_attrs)
    r = dict(name=name, voxel_m=0.25 * vs, t_surface_s=round(t_surf, 2), points=int(npt), triangles=int(npr), unused_points=int(unused),
             point_attribs=attrs, abc_bytes=size, abc_bytes_per_tri=round(size / max(1, npr), 2), t_abc_write_s=round(t_abc, 3),
             read_points=int(rg.intrinsicValue("pointcount")), read_prims=int(rg.intrinsicValue("primitivecount")), read_point_attribs=back_attrs,
             K5_pass=(int(rg.intrinsicValue("pointcount")) == int(npt)) and has_v, K6_pass=(unused == 0))
    res.append(r)
    print(json.dumps(r, ensure_ascii=False))
    sys.stdout.flush()

total = time.perf_counter() - T_ALL
summary = dict(houdini=hou.applicationVersionString(), priority=PRIO, results=res, total_s=round(total, 1), K7_pass=total <= 600,
               time=time.strftime("%Y-%m-%d %H:%M:%S"))
json.dump(summary, open(OUT + "/u_surfsize_abc_result.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("done total %.1f s" % total)
