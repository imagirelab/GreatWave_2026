# -*- coding: utf-8 -*-
"""P0 の計算を 1 回走らせ、水面の高さ η(x, t)・粒子数・時間・メモリーを記録する（hython で実行）。

使い方: hython run_p0.py '<JSON>'
JSON: {"run_id": "...", "parms": {"H": 3.0, ...}, "f_start": 1, "f_end": 241,
       "ckpt_on": 0|1, "ckpt_dir": "...", "ckpt_every": 48, "snap_every": 48,
       "wall_limit_s": 1680, "note": "..."}
出力: G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP36/P0/<run_id>/ に eta.npz・snap_*.npz・run.json。
runs.jsonl に 1 行足す。f_start > 1 の時は、ckpt_dir の途中保存から続きを計算する（再開の試し）。
"""
import hou, sys, os, json, time, ctypes, hashlib
from ctypes import wintypes
import numpy as np

HIP = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP36/p0_tank.hiplc"
ROOT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP36"
args = json.loads(sys.argv[1])
rid = args["run_id"]
OUT = os.path.join(ROOT, "P0", rid).replace("\\", "/")
os.makedirs(OUT, exist_ok=True)


def rss_gb():
    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    c = PMC(); c.cb = ctypes.sizeof(PMC)
    k = ctypes.windll.kernel32; k.GetCurrentProcess.restype = ctypes.c_void_p
    f = ctypes.windll.psapi.GetProcessMemoryInfo
    f.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
    f(k.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.WorkingSetSize / 2**30, c.PeakWorkingSetSize / 2**30


t_launch = time.time()
hou.hipFile.load(HIP, suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/P0_SETUP/CTRL")
for k, v in args.get("parms", {}).items():
    ctrl.parm(k).set(v)
ckdir = args.get("ckpt_dir", os.path.join(OUT, "ckpt")).replace("\\", "/")
os.makedirs(ckdir, exist_ok=True)
ctrl.parm("ckpt").set(ckdir + "/p0.$SF4.sim")
ctrl.parm("ckpt_on").set(int(args.get("ckpt_on", 0)))
ctrl.parm("ckpt_every").set(int(args.get("ckpt_every", 48)))
hou.setSimulationEnabled(True)
fps = hou.fps()
dop = hou.node("/obj/P0_SIM")
fi = hou.node("/obj/P0_READ/surface_field")
f0, f1 = int(args["f_start"]), int(args["f_end"])
snap_every = int(args.get("snap_every", 48))
wall_limit = float(args.get("wall_limit_s", 1680))
P = {p.name(): p.eval() for p in ctrl.parms()}

frames, wall, npts, rss, peak, tsim = [], [], [], [], [], []
etas = []
info = {}
t_start = time.time()
stopped = None
x_c = None
for f in range(f0, f1 + 1):
    t0 = time.time()
    hou.setFrame(f)
    g = fi.geometry()
    dt = time.time() - t0
    vols = [p for p in g.prims() if p.type() in (hou.primType.Volume, hou.primType.VDB)]
    if not vols:
        info["error"] = "no surface field at frame %d; errors=%s" % (f, [str(e) for e in fi.errors()])
        stopped = "error"
        break
    vol = vols[0]
    nx, ny, nz = vol.resolution()
    if x_c is None:
        arr0 = np.frombuffer(vol.allVoxelsAsString(), dtype=np.float32)
        # 並びの確かめ：x が最も速く変わる（index = i + nx*(j + ny*k)）
        test = []
        for (i, j, k) in [(3, 5, 1), (nx - 7, ny // 2, nz // 2), (nx // 3, ny - 3, nz - 2)]:
            test.append([vol.voxel((i, j, k)), float(arr0[i + nx * (j + ny * k)])])
        info["order_check"] = test
        Lx = float(ctrl.parm("Lx").eval()); vox0 = float(ctrl.parm("dp").eval() * ctrl.parm("gridscale").eval())
        x_c = np.arange(0.5 * vox0, Lx, vox0)
        info["res_first"] = [nx, ny, nz]
    if [nx, ny, nz] != info.get("res_last"):
        p000 = vol.indexToPos((0, 0, 0)); p111 = vol.indexToPos((1, 1, 1))
        xs = p000[0] + (p111[0] - p000[0]) * np.arange(nx)
        y_c = p000[1] + (p111[1] - p000[1]) * np.arange(ny)
        zs = p000[2] + (p111[2] - p000[2]) * np.arange(nz)
        dy = y_c[1] - y_c[0]
        kmid = int(np.argmin(np.abs(zs)))
        info["res_last"] = [nx, ny, nz]
        info.setdefault("res_changes", []).append([f, nx, ny, nz, round(float(xs[0]), 3), round(float(y_c[0]), 3), round(float(zs[0]), 3)])
    a = np.frombuffer(vol.allVoxelsAsString(), dtype=np.float32).reshape(nz, ny, nx)
    c = a[kmid]  # (ny, nx)
    neg = c < 0
    has = neg.any(axis=0)
    jtop = ny - 1 - np.argmax(neg[::-1, :], axis=0)
    jtop = np.clip(jtop, 0, ny - 2)
    vj = c[jtop, np.arange(nx)]
    vj1 = c[jtop + 1, np.arange(nx)]
    frac = np.where(vj1 - vj > 1e-9, -vj / np.maximum(vj1 - vj, 1e-9), 0.0)
    eta_raw = np.where(has, y_c[jtop] + dy * np.clip(frac, 0, 1), np.nan)
    eta = np.interp(x_c, xs, eta_raw, left=np.nan, right=np.nan)
    etas.append(eta.astype(np.float32))
    # 粒子数
    n = -1
    try:
        obj = dop.simulation().findObject("water")
        pg = obj.geometry()
        n = pg.intrinsicValue("pointcount")
        if (f - 1) % snap_every == 0 or f == f1:
            Pp = np.frombuffer(pg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3)
            V = np.frombuffer(pg.pointFloatAttribValuesAsString("v"), dtype=np.float32).reshape(-1, 3)
            m = np.abs(Pp[:, 2]) < 0.5
            np.savez_compressed(os.path.join(OUT, "snap_%04d.npz" % f), x=Pp[m, 0], y=Pp[m, 1],
                                sp=np.linalg.norm(V[m], axis=1), n=n, ymin=float(Pp[:, 1].min()))
    except Exception as e:
        info.setdefault("particle_errors", []).append(str(e)[:200])
    r, pk = rss_gb()
    frames.append(f); wall.append(dt); npts.append(n); rss.append(r); peak.append(pk)
    tsim.append((f - 1) / fps)
    if f % 24 == 0 or f == f0:
        print("f=%d t=%.2f wall=%.2fs pts=%d rss=%.2fGB eta[%d]=%.3f" % (f, (f - 1) / fps, dt, n, r, 100, eta[100]))
        sys.stdout.flush()
    if f % 240 == 0:
        np.savez_compressed(os.path.join(OUT, "eta.npz"), x=x_c, frames=np.array(frames), t=np.array(tsim),
                            eta=np.array(etas), wall=np.array(wall), npts=np.array(npts), rss=np.array(rss))
    if time.time() - t_start > wall_limit:
        stopped = "wall_limit at frame %d" % f
        break

np.savez_compressed(os.path.join(OUT, "eta.npz"), x=x_c, frames=np.array(frames), t=np.array(tsim),
                    eta=np.array(etas), wall=np.array(wall), npts=np.array(npts), rss=np.array(rss))
wall_total = time.time() - t_start
ck = sorted(os.listdir(ckdir)) if os.path.isdir(ckdir) else []
ck_bytes = sum(os.path.getsize(os.path.join(ckdir, x)) for x in ck)
rec = {
    "stage": "P0", "run_id": rid, "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    "houdini": hou.applicationVersionString(), "hip": HIP,
    "hip_sha256": hashlib.sha256(open(HIP, "rb").read()).hexdigest(),
    "parms": {k: P[k] for k in P if not k.startswith("folder")},
    "f_start": f0, "f_end_req": f1, "f_end_done": frames[-1] if frames else None, "fps": fps,
    "ckpt_dir": ckdir, "ckpt_on": int(args.get("ckpt_on", 0)), "ckpt_files": len(ck), "ckpt_gb": round(ck_bytes / 2**30, 3),
    "particles_first": npts[0] if npts else None, "particles_max": max(npts) if npts else None,
    "particles_last": npts[-1] if npts else None,
    "wall_total_s": round(wall_total, 1), "wall_launch_s": round(time.time() - t_launch, 1),
    "wall_first_frame_s": round(wall[0], 2) if wall else None,
    "wall_per_frame_median_s": round(float(np.median(wall[1:])) if len(wall) > 1 else 0, 3),
    "rss_last_gb": round(rss[-1], 2) if rss else None, "rss_peak_gb": round(max(peak), 2) if peak else None,
    "stopped": stopped, "info": info, "note": args.get("note", ""),
}
json.dump(rec, open(os.path.join(OUT, "run.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
with open(os.path.join(ROOT, "runs.jsonl"), "a", encoding="utf8") as fh:
    fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
print("DONE", json.dumps({k: rec[k] for k in ("run_id", "f_end_done", "wall_total_s", "particles_max", "rss_peak_gb", "stopped")}))
