# -*- coding: utf-8 -*-
"""P1 の断面の計算を 1 回走らせて記録する（hython で実行）。run_p0.py を元にした。

使い方: hython run_p1.py '<JSON>'
JSON: {"run_id": "...", "parms": {"H": 20.0, ...}, "f_start": 1, "f_end": 400,
       "ckpt_on": 0|1, "ckpt_dir": "...", "ckpt_every": 48,
       "snap_from": 120, "snap_every": 2, "snap_x": [380, 800], "snap_ymin": -25, "snap_zhalf": 1.05,
       "wall_limit_s": 1680, "note": "..."}
出力: G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P1/<run_id>/
  eta.npz      水面の場から読んだ一番上の水面 η(x, t)（毎コマ）
  crest.npy    毎コマの頂の記録（全部の粒子から：最も高い粒子の x・y、その近くの水平の流速の最大など）
  snap_XXXX.npz 断面の粒子（|z| < snap_zhalf、x と y の範囲の中）：x, y, vx, vy（float32）
  run.json     条件と記録。Unity/Build/FLIP37/runs.jsonl にも 1 行足す。
f_start > 1 の時は、ckpt_dir の途中保存から続きを計算する。
見張り：水槽全体の水面の平均が始めより 1 m 以上下がったら（圧力が解けず水が落ちる失敗。P0 §3.4）止めて stopped=free_fall と記録する。
（P0 の見張りは中ほどの区域の平均だったが、20 m 級の波ではその区域の平均が波の位相で 1 m 以上動くので、全体の平均に替えた。
  閉じた箱で水の量は保たれるので、全体の平均は落ちない限りほぼ一定。）
"""
import hou, sys, os, json, time, ctypes, hashlib
from ctypes import wintypes
import numpy as np

HIP = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP37/p1_tank.hiplc"
ROOT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37"
args = json.loads(sys.argv[1])
rid = args["run_id"]
OUT = os.path.join(ROOT, "P1", rid).replace("\\", "/")
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
HIP_SHA = hashlib.sha256(open(HIP, "rb").read()).hexdigest()
hou.hipFile.load(HIP, suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/P1_SETUP/CTRL")
for k, v in args.get("parms", {}).items():
    ctrl.parm(k).set(v)
ckdir = args.get("ckpt_dir", os.path.join(OUT, "ckpt")).replace("\\", "/")
if int(args.get("ckpt_on", 0)) or int(args["f_start"]) > 1:
    os.makedirs(ckdir, exist_ok=True)
ctrl.parm("ckpt").set(ckdir)
ctrl.parm("ckpt_on").set(int(args.get("ckpt_on", 0)))
ctrl.parm("ckpt_every").set(int(args.get("ckpt_every", 48)))
hou.setSimulationEnabled(True)
fps = hou.fps()
dop = hou.node("/obj/P1_SIM")
fi = hou.node("/obj/P1_READ/surface_field")
f0, f1 = int(args["f_start"]), int(args["f_end"])
snap_from = int(args.get("snap_from", 1))
snap_every = int(args.get("snap_every", 2))
sx0, sx1 = args.get("snap_x", [0.0, 1e9])
symin = float(args.get("snap_ymin", -25.0))
szh = float(args.get("snap_zhalf", 1.05))
wall_limit = float(args.get("wall_limit_s", 1680))
P = {p.name(): p.eval() for p in ctrl.parms()}
P["explicitcachename_eval"] = dop.parm("explicitcachename").eval()

frames, wall, npts, rss, peak, tsim = [], [], [], [], [], []
etas = []
crest = []   # f, t, ymax, x_at_ymax, y_p999, x_front_top, umax_top, umean_top, umax_hi, n_top
info = {}
t_start = time.time()
stopped = None
x_c = None
lvl0 = None
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
    c = a[kmid]
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
    n = -1
    try:
        obj = dop.simulation().findObject("water")
        pg = obj.geometry()
        n = pg.intrinsicValue("pointcount")
        Pp = np.frombuffer(pg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3)
        V = np.frombuffer(pg.pointFloatAttribValuesAsString("v"), dtype=np.float32).reshape(-1, 3)
        # 頂の記録（全部の粒子。断面なので z は無視する）
        iy = int(np.argmax(Pp[:, 1]))
        ymax, xym = float(Pp[iy, 1]), float(Pp[iy, 0])
        hi = Pp[:, 1] > max(ymax - 1.0, 0.0)
        pos = Pp[:, 1] > 0
        y999 = float(np.percentile(Pp[pos, 1], 99.9)) if pos.sum() > 100 else ymax
        xft = float(Pp[hi, 0].max()) if hi.any() else xym
        umx = float(V[hi, 0].max()) if hi.any() else 0.0
        umn = float(V[hi, 0].mean()) if hi.any() else 0.0
        hh = Pp[:, 1] > 0.5 * max(ymax, 0.0)
        umh = float(V[hh, 0].max()) if hh.any() else 0.0
        crest.append([f, (f - 1) / fps, ymax, xym, y999, xft, umx, umn, umh, int(hi.sum())])
        if f >= snap_from and ((f - snap_from) % snap_every == 0 or f == f1):
            m = (np.abs(Pp[:, 2]) < szh) & (Pp[:, 0] >= sx0) & (Pp[:, 0] <= sx1) & (Pp[:, 1] >= symin)
            np.savez_compressed(os.path.join(OUT, "snap_%04d.npz" % f), x=Pp[m, 0], y=Pp[m, 1], vx=V[m, 0], vy=V[m, 1],
                                n=n, t=(f - 1) / fps, zhalf=szh)
    except Exception as e:
        info.setdefault("particle_errors", []).append(str(e)[:200])
    r, pk = rss_gb()
    frames.append(f); wall.append(dt); npts.append(n); rss.append(r); peak.append(pk)
    tsim.append((f - 1) / fps)
    lvl = float(np.nanmean(eta)) if np.isfinite(eta).any() else -999.0
    if lvl0 is None:
        lvl0 = lvl
    if f % 24 == 0 or f == f0:
        cc = crest[-1] if crest else [0] * 10
        print("f=%d t=%.2f wall=%.2fs pts=%d rss=%.2fGB lvl=%.3f ymax=%.2f x=%.1f umax=%.2f" % (f, (f - 1) / fps, dt, n, r, lvl, cc[2], cc[3], cc[6]))
        sys.stdout.flush()
    if f % 120 == 0:
        np.savez_compressed(os.path.join(OUT, "eta.npz"), x=x_c, frames=np.array(frames), t=np.array(tsim),
                            eta=np.array(etas), wall=np.array(wall), npts=np.array(npts), rss=np.array(rss))
        np.save(os.path.join(OUT, "crest.npy"), np.array(crest, dtype=np.float64))
    if time.time() - t_start > wall_limit:
        stopped = "wall_limit at frame %d" % f
        break
    if f - f0 >= 6 and lvl - lvl0 < -1.0:
        stopped = "free_fall at frame %d (mean level %.2f m, start %.2f m)" % (f, lvl, lvl0)
        break

np.savez_compressed(os.path.join(OUT, "eta.npz"), x=x_c, frames=np.array(frames), t=np.array(tsim),
                    eta=np.array(etas), wall=np.array(wall), npts=np.array(npts), rss=np.array(rss))
np.save(os.path.join(OUT, "crest.npy"), np.array(crest, dtype=np.float64))
wall_total = time.time() - t_start
ck = sorted(os.listdir(ckdir)) if os.path.isdir(ckdir) else []
ck_bytes = sum(os.path.getsize(os.path.join(ckdir, x)) for x in ck)
rec = {
    "stage": "P1", "run_id": rid, "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    "houdini": hou.applicationVersionString(), "hip": HIP, "hip_sha256": HIP_SHA,
    "parms": {k: P[k] for k in P if not k.startswith("folder")},
    "f_start": f0, "f_end_req": f1, "f_end_done": frames[-1] if frames else None, "fps": fps,
    "ckpt_dir": ckdir, "ckpt_on": int(args.get("ckpt_on", 0)), "ckpt_files": len(ck), "ckpt_gb": round(ck_bytes / 2**30, 3),
    "particles_first": npts[0] if npts else None, "particles_max": max(npts) if npts else None,
    "particles_last": npts[-1] if npts else None,
    "wall_total_s": round(wall_total, 1), "wall_launch_s": round(time.time() - t_launch, 1),
    "wall_first_frame_s": round(wall[0], 2) if wall else None,
    "wall_per_frame_median_s": round(float(np.median(wall[1:])) if len(wall) > 1 else 0, 3),
    "rss_last_gb": round(rss[-1], 2) if rss else None, "rss_peak_gb": round(max(peak), 2) if peak else None,
    "level_start_m": lvl0, "stopped": stopped, "info": info, "note": args.get("note", ""),
    "snap": {"from": snap_from, "every": snap_every, "x": [sx0, sx1], "ymin": symin, "zhalf": szh},
}
json.dump(rec, open(os.path.join(OUT, "run.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
with open(os.path.join(ROOT, "runs.jsonl"), "a", encoding="utf8") as fh:
    fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
print("DONE", json.dumps({k: rec[k] for k in ("run_id", "f_end_done", "wall_total_s", "particles_max", "rss_peak_gb", "stopped")}))
