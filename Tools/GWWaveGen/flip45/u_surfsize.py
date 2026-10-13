# -*- coding: utf-8 -*-
"""FLIP45（Unity での 3D の面の再生の調べ）：短い試し u_surfsize（hython で実行、数分）。
3D の焦点の波（Fochesato ら 2007 の形の線形の重ね合わせ、焦点の時刻。巻かない）の下を粒子 0.25 m で満たし、
Houdini の Particle Fluid Surface で面にして、Unity へ渡す 1 コマの三角形の数・大きさ・面を作る時間を測る。
流体の計算はしない。判定の幅は走らせる前に Unity/Build/FLIP45/research/u_surfsize/criteria_frozen.json に書いた。
座標は Houdini のまま（x 進む向き、y 上、z 横）。
使い方: hython u_surfsize.py <出力のフォルダー>
2026-10-12 進行役が書いた。優先度と電力の抑えの設定は flip44/g44_run.py の unthrottle_self を写した（元は変えていない）。
2026-10-12 05:32 の run1 は、三角形を除く時に点も消していたため、先に記録した点の番号がずれて止まった（IndexError）。
点は残す指定（removeprim の 3 つ目を 0）に直して run2 を走らせた。判定の幅は変えていない。"""
import ctypes
import json
import math
import os
import sys
import time
import zlib
from ctypes import wintypes

import numpy as np
import hou

OUT = sys.argv[1].replace("\\", "/")
os.makedirs(OUT, exist_ok=True)
T_ALL = time.perf_counter()
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append("%s %s" % (time.strftime("%H:%M:%S"), s))
    print(s)
    sys.stdout.flush()


# ---------------------------------------------------------------- 優先度と電力の抑え（自分の処理だけ。g44_run.py と同じ）
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


def rss_gb():
    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]
    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    ps = ctypes.WinDLL("psapi")
    ps.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
    return pmc.PeakWorkingSetSize / 1e9


PRIO = unthrottle_self()
log("priority", PRIO, "houdini", hou.applicationVersionString())

# ---------------------------------------------------------------- 波（線形の焦点の時刻の水面）
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


def eta(x, z):
    x = np.asarray(x, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    out = np.zeros(np.broadcast(x, z).shape)
    for th in TH:
        out += A * np.cos(k * ((x - XF) * math.cos(th) + (z - ZF) * math.sin(th)))
    return out


log("k %.6f lambda %.3f" % (k, 2 * math.pi / k))

# ---------------------------------------------------------------- 粒子
DX = 0.25
X0, X1, Z0, Z1 = 166.0, 304.0, 0.0, 72.0
nx, nz = int(round((X1 - X0) / DX)), int(round((Z1 - Z0) / DX))
xc = X0 + (np.arange(nx) + 0.5) * DX
zc = Z0 + (np.arange(nz) + 0.5) * DX
XX, ZZ = np.meshgrid(xc, zc, indexing="ij")
E = eta(XX, ZZ)
emin, emax = float(E.min()), float(E.max())
Y0 = math.floor((emin - 2.5) / DX) * DX
ny = int(math.ceil((emax + DX - Y0) / DX))
log("eta min %.3f max %.3f  Y0 %.2f  cells %d x %d x %d" % (emin, emax, Y0, nx, nz, ny))
rng = np.random.default_rng(20261012)
chunks = []
for i in range(nx):
    # この x の列の全部の格子の箱に 1 個ずつ、箱の中の乱数の位置
    jz, jy = np.meshgrid(np.arange(nz), np.arange(ny), indexing="ij")
    jz, jy = jz.ravel(), jy.ravel()
    px = X0 + (i + rng.random(jz.size)) * DX
    pz = Z0 + (jz + rng.random(jz.size)) * DX
    py = Y0 + (jy + rng.random(jz.size)) * DX
    keep = py < eta(px, pz)
    chunks.append(np.stack([px[keep], py[keep], pz[keep]], axis=1).astype(np.float32))
P = np.concatenate(chunks)
del chunks
log("particles", P.shape[0], "t %.1f s" % (time.perf_counter() - T_ALL))

pg = hou.Geometry()
pg.createPoints([(0.0, 0.0, 0.0)] * P.shape[0])
pg.setPointFloatAttribValuesFromString("P", P.tobytes())
pfile = OUT + "/particles.bgeo.sc"
pg.saveToFile(pfile)
log("saved particles", pfile, "%.1f MB" % (os.path.getsize(pfile) / 1e6))
del pg

# ---------------------------------------------------------------- 網
geo = hou.node("/obj").createNode("geo", "u_surfsize")
fin = geo.createNode("file", "particles")
fin.parm("file").set(pfile)
YCUT = emin - 1.0
TRIM_VEX = """
int pts[] = primpoints(0, @primnum);
vector c = 0;
foreach (int p; pts) c += point(0, "P", p);
c /= max(1, len(pts));
i@nv = len(pts);
if (c.x < 167 || c.x > 303 || c.z < 1 || c.z > 71 || c.y < %f) removeprim(0, @primnum, 0);
i@a = len(pts) > 0 ? pts[0] : -1;
i@b = len(pts) > 1 ? pts[1] : -1;
i@c = len(pts) > 2 ? pts[2] : -1;
""" % YCUT
IDX_VEX = """
int pts[] = primpoints(0, @primnum);
i@nv = len(pts);
i@a = len(pts) > 0 ? pts[0] : -1;
i@b = len(pts) > 1 ? pts[1] : -1;
i@c = len(pts) > 2 ? pts[2] : -1;
"""

CONFIGS = [
    dict(name="A", voxelscale=1.0, adaptivity=0.005, reduce=None),
    dict(name="B", voxelscale=0.5, adaptivity=0.005, reduce=None),
    dict(name="C", voxelscale=2.0, adaptivity=0.005, reduce=None),
    dict(name="D", voxelscale=1.0, adaptivity=0.1, reduce=None),
    dict(name="E", voxelscale=1.0, adaptivity=0.005, reduce=25.0),
]
PLAN = 136.0 * 70.0
results = []
abc_nodes = {}
for cfg in CONFIGS:
    name = cfg["name"]
    pfs = geo.createNode("particlefluidsurface", "pfs_" + name)
    pfs.setInput(0, fin)
    pfs.parm("particlesep").set(0.25)
    pfs.parm("voxelsize").set(cfg["voxelscale"])
    pfs.parm("adaptivity").set(cfg["adaptivity"])
    pfs.parm("conversion").set("poly")
    t0 = time.perf_counter()
    pfs.cook(force=True)
    t_surf = time.perf_counter() - t0
    if pfs.errors():
        log(name, "errors", pfs.errors())
    div = geo.createNode("divide", "tri_" + name)
    div.setInput(0, pfs)
    trim = geo.createNode("attribwrangle", "trim_" + name)
    trim.setInput(0, div)
    trim.parm("class").set(1)  # primitive
    trim.parm("snippet").set(TRIM_VEX)
    last = trim
    t_red = 0.0
    if cfg["reduce"]:
        red = geo.createNode("polyreduce::2.0", "reduce_" + name)
        red.setInput(0, trim)
        red.parm("target").set(0)
        red.parm("percentage").set(cfg["reduce"])
        idx = geo.createNode("attribwrangle", "idx_" + name)
        idx.setInput(0, red)
        idx.parm("class").set(1)
        idx.parm("snippet").set(IDX_VEX)
        t1 = time.perf_counter()
        red.cook(force=True)
        t_red = time.perf_counter() - t1
        last = idx
    t2 = time.perf_counter()
    last.cook(force=True)
    t_post = time.perf_counter() - t2
    g = last.geometry()
    npt, npr = g.intrinsicValue("pointcount"), g.intrinsicValue("primitivecount")
    nv = np.frombuffer(g.primIntAttribValuesAsString("nv"), dtype=np.int32)
    tri_a = np.frombuffer(g.primIntAttribValuesAsString("a"), dtype=np.int32)
    tri_b = np.frombuffer(g.primIntAttribValuesAsString("b"), dtype=np.int32)
    tri_c = np.frombuffer(g.primIntAttribValuesAsString("c"), dtype=np.int32)
    Pp = np.frombuffer(g.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64)
    used = np.unique(np.concatenate([tri_a, tri_b, tri_c]))
    used = used[used >= 0]
    ntri = int(npr)
    v0, v1, v2 = Pp[tri_a], Pp[tri_b], Pp[tri_c]
    cr = np.cross(v1 - v0, v2 - v0)
    area3 = 0.5 * np.linalg.norm(cr, axis=1)
    proj = 0.5 * np.abs(cr[:, 1])
    Pu = Pp[used]
    d = Pu[:, 1] - eta(Pu[:, 0], Pu[:, 2])
    dm = float(np.median(d))
    p99 = float(np.percentile(np.abs(d - dm), 99))
    # 1 コマの大きさ（自作の流し込みの形）：点を 16 bit に量子化（窓の箱）・法線を 8 方向の 16 bit×2、添字 32 bit
    npu = int(used.size)
    raw_f32 = npu * 24 + ntri * 12
    quant = npu * 10 + ntri * 12
    lo, hi = Pu.min(axis=0), Pu.max(axis=0)
    q = np.round((Pu - lo) / np.maximum(hi - lo, 1e-9) * 65535).astype(np.uint16)
    qerr = float(np.max(np.abs(q.astype(np.float64) / 65535 * (hi - lo) + lo - Pu)))
    # 点の番号を詰め直した添字
    remap = -np.ones(Pp.shape[0], dtype=np.int64)
    remap[used] = np.arange(npu)
    ib = np.stack([remap[tri_a], remap[tri_b], remap[tri_c]], axis=1).astype(np.uint32)
    buf = q.tobytes() + np.zeros(npu * 4, dtype=np.uint8).tobytes() + ib.tobytes()
    tz0 = time.perf_counter()
    zb = zlib.compress(q.tobytes() + ib.tobytes(), 1)
    t_z = time.perf_counter() - tz0
    tz1 = time.perf_counter()
    zlib.decompress(zb)
    t_unz = time.perf_counter() - tz1
    r = dict(name=name, voxelscale=cfg["voxelscale"], voxel_m=0.25 * cfg["voxelscale"], adaptivity=cfg["adaptivity"],
             reduce_percent=cfg["reduce"], t_surface_s=round(t_surf, 2), t_reduce_s=round(t_red, 2), t_post_s=round(t_post, 2),
             points_total=int(npt), points_used=npu, triangles=ntri, max_nv=int(nv.max()) if nv.size else 0,
             area_true_m2=round(float(area3.sum()), 1), area_proj_m2=round(float(proj.sum()), 1),
             K2_ratio=round(float(proj.sum()) / PLAN, 4), K3_p99_m=round(p99, 4), K3_median_offset_m=round(dm, 4),
             tris_per_m2_plan=round(ntri / PLAN, 2), bytes_raw_f32=raw_f32, bytes_quant=quant,
             bytes_quant_pos_idx_zlib1=len(zb), t_zlib1_s=round(t_z, 3), t_unzlib_s=round(t_unz, 3),
             quant16_max_err_m=round(qerr, 5), bbox_lo=[round(v, 3) for v in lo], bbox_hi=[round(v, 3) for v in hi],
             rss_peak_gb=round(rss_gb(), 2))
    r["K2_pass"] = 0.98 <= r["K2_ratio"] <= 1.05
    r["K3_pass"] = p99 <= 0.25
    r["K1_surface_under_5min"] = t_surf <= 300
    results.append(r)
    abc_nodes[name] = last
    log(json.dumps(r, ensure_ascii=False))
    if t_surf > 300:
        log("K1: surface cook over 5 min, stop")
        break

# ---------------------------------------------------------------- Alembic（組 A と C、1 コマ）
abc_res = []
for name in ["A", "C"]:
    if name not in abc_nodes:
        continue
    node = abc_nodes[name]
    rop = hou.node("/out").createNode("alembic", "abc_" + name)
    path = OUT + "/surface_%s.abc" % name
    rop.parm("use_sop_path").set(1)
    rop.parm("sop_path").set(node.path())
    rop.parm("trange").set(0)
    rop.parm("filename").set(path)
    t0 = time.perf_counter()
    rop.render()
    t_abc = time.perf_counter() - t0
    size = os.path.getsize(path) if os.path.exists(path) else -1
    # 読み直し
    rd = geo.createNode("alembic", "read_" + name)
    rd.parm("fileName").set(path)
    lm = rd.parm("loadmode")
    chosen = None
    if lm is not None:
        items, labels = lm.parmTemplate().menuItems(), lm.parmTemplate().menuLabels()
        for it, lb in zip(items, labels):
            if "houdini" in lb.lower():
                lm.set(it)
                chosen = lb
                break
    rd.cook(force=True)
    rg = rd.geometry()
    n_back = rg.intrinsicValue("pointcount")
    n_out = node.geometry().intrinsicValue("pointcount")
    a = dict(name=name, file=path, bytes=size, t_write_s=round(t_abc, 2), loadmode=chosen, points_written=int(n_out),
             points_read=int(n_back), prims_read=int(rg.intrinsicValue("primitivecount")), K4_pass=(int(n_back) == int(n_out)))
    abc_res.append(a)
    log(json.dumps(a, ensure_ascii=False))

total = time.perf_counter() - T_ALL
summary = dict(houdini=hou.applicationVersionString(), priority=PRIO, k=k, wavelength_m=2 * math.pi / k, eta_min=emin, eta_max=emax,
               particles=int(P.shape[0]), plan_m2=PLAN, ycut=YCUT, results=results, alembic=abc_res, total_s=round(total, 1),
               K1_pass=total <= 900, rss_peak_gb=round(rss_gb(), 2), time=time.strftime("%Y-%m-%d %H:%M:%S"))
json.dump(summary, open(OUT + "/u_surfsize_result.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
open(OUT + "/u_surfsize_log.txt", "w", encoding="utf8").write("\n".join(LOG))
HIPDIR = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP45/u_surfsize"
os.makedirs(HIPDIR, exist_ok=True)
hou.hipFile.save(HIPDIR + "/u_surfsize.hiplc")
log("done total %.1f s" % total)
