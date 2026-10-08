# -*- coding: utf-8 -*-
"""FLIP41 確かめ：断面の水槽の計算を 1 回走らせて、毎コマの水面 η(z, x) を記録する（hython で実行）。
FLIP39 の e_run.py を元に、記録を水面の高さだけに絞った（断面の水槽の確かめに要る量）。

使い方: hython v_run.py '<JSON>'
JSON: {"run_id": "...", "parms": {CTRL の値}, "solver": {"veltransfer": "apic"|"flip", "donarrowband": 0|1},
       "f_start": 1, "f_end": 2400, "ckpt_on": 1, "ckpt_every": 240, "wall_limit_s": 1740, "level_guard_m": 1.0,
       "diag": 0|1, "note": "..."}
出力: Unity/Build/FLIP41/verify/runs/<run_id>/
  hf_cXXXX.npz  eta（コマ, z, x、float32。水面の場の一番上の水面）、x、z、t、frames、wall（1 コマの計算の秒）、npts
  run_cXXXX.json 条件と記録（f_start ごと）。run.json（最初の区切り）。verify/runs.jsonl にも 1 行足す。
見張り：水面の平均が始めより level_guard_m 下がったら止める（FLIP37 P0 §3.4 の圧力が解けない失敗）。
"""
import hou, sys, os, json, time, hashlib, ctypes
from ctypes import wintypes
import numpy as np

HIP = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP41/v_tank.hiplc"
ROOT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP41/verify"
args = json.loads(sys.argv[1])
rid = args["run_id"]
OUT = os.path.join(ROOT, "runs", rid).replace("\\", "/")
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
ctrl = hou.node("/obj/V_SETUP/CTRL")
for k, v in args.get("parms", {}).items():
    ctrl.parm(k).set(v)
fs = hou.node("/obj/V_SIM/flipsolver")
sv = args.get("solver", {})
fs.parm("veltransfer").set(sv.get("veltransfer", "apic"))
fs.parm("donarrowband").set(int(sv.get("donarrowband", 1)))
f0, f1 = int(args["f_start"]), int(args["f_end"])
ckdir = os.path.join(OUT, "ckpt").replace("\\", "/")
os.makedirs(ckdir, exist_ok=True)
ctrl.parm("ckpt").set(ckdir)
ctrl.parm("ckpt_on").set(int(args.get("ckpt_on", 1)))
ctrl.parm("ckpt_every").set(int(args.get("ckpt_every", 240)))
hou.setSimulationEnabled(True)
fps = hou.fps()
dop = hou.node("/obj/V_SIM")
fi = hou.node("/obj/V_READ/surface_field")
fd = hou.node("/obj/V_READ/diag_fields")
wall_limit = float(args.get("wall_limit_s", 1740))
lvl_guard = float(args.get("level_guard_m", 1.0))
P = {p.name(): p.eval() for p in ctrl.parms()}
Lz = float(P["Lz"]); Lx = float(P["Lx"])
VOX = float(P["dp"]) * float(P["gridscale"])
# 水面の場（surface）の標本の位置は格子の節（x = 0, Δ, 2Δ, …、z = −Lz/2 … Lz/2）。FLIP39 の e_run.py と同じ
# （2026-10-08 の T1_dp1 は格子の中心へ置き直していて、x が Δ/2 ずれていた。v_analyze.py の load で直す）
FX = np.arange(0.0, Lx + 1e-6, VOX)
FZ = np.arange(-0.5 * Lz, 0.5 * Lz + 1e-6, VOX)

frames, wall, npts, tsim, lvls, hfs = [], [], [], [], [], []
info = {}
# 流速の見張り（2026-10-08 22:45 に足した）：6 コマごとに、測る区間の 3 か所で格子の水平の流速 vel.x を深さ方向に読む（平均の流れを見るため）。
# 場面のファイルは変えず、読み取りのノードをこの起動の中だけで作る。失敗しても計算は続ける。
probe = None; PRB_X = []; PRB_Y = []; prb_t, prb_u = [], []
try:
    cs_ = args.get("case", {})
    if cs_.get("x_meas"):
        xm0_, xm1_ = cs_["x_meas"]
        PRB_X = [xm0_, 0.5 * (xm0_ + xm1_), xm1_]
    elif cs_.get("xs0"):
        PRB_X = [0.5 * (cs_["x_off"][0] + cs_["x_off"][1]), 0.5 * (cs_["xs0"] + cs_["xs1"]), cs_["xs1"] + 0.5 * cs_.get("L1", 50.0)]
    if PRB_X:
        PRB_Y = list(np.arange(-float(P["h0"]) + 0.5 * VOX, -0.5 * VOX + 1e-6, max(VOX, 1.0)))
        probe = hou.node("/obj/V_READ").createNode("dopimportfield::2.0", "vel_probe")
        probe.parm("doppath").set("/obj/V_SIM")
        probe.parm("fields").set(1)
        probe.parm("objname1").set("water")
        probe.parm("fieldname1").set("vel")
except Exception as e:
    info["probe_error"] = str(e)[:300]; probe = None
t_start = time.time()
stopped = None
lvl0 = None
grid_info = None
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
    p000 = vol.indexToPos((0, 0, 0)); p111 = vol.indexToPos((1, 1, 1))
    xs = p000[0] + (p111[0] - p000[0]) * np.arange(nx)
    y_c = p000[1] + (p111[1] - p000[1]) * np.arange(ny)
    zs = p000[2] + (p111[2] - p000[2]) * np.arange(nz)
    dy = y_c[1] - y_c[0]
    if grid_info is None or grid_info["res"] != [nx, ny, nz]:
        grid_info = {"res": [nx, ny, nz], "x0": float(xs[0]), "dx": float(p111[0] - p000[0]), "y0": float(y_c[0]), "z0": float(zs[0])}
        info.setdefault("res_changes", []).append([f] + grid_info["res"])
    a = np.frombuffer(vol.allVoxelsAsString(), dtype=np.float32).reshape(nz, ny, nx)
    neg = a < 0
    has = neg.any(axis=1)
    jtop = ny - 1 - np.argmax(neg[:, ::-1, :], axis=1)
    jtop = np.clip(jtop, 0, ny - 2)
    iz_, ix_ = np.meshgrid(np.arange(nz), np.arange(nx), indexing="ij")
    vj = a[iz_, jtop, ix_]; vj1 = a[iz_, jtop + 1, ix_]
    frac = np.where(vj1 - vj > 1e-9, -vj / np.maximum(vj1 - vj, 1e-9), 0.0)
    eta = np.where(has, y_c[jtop] + dy * np.clip(frac, 0, 1), np.nan)
    ixf = np.floor((xs - FX[0]) / VOX + 0.5).astype(int); izf = np.floor((zs - FZ[0]) / VOX + 0.5).astype(int)
    okx = (ixf >= 0) & (ixf < len(FX)); okz = (izf >= 0) & (izf < len(FZ))
    E2 = np.full((len(FZ), len(FX)), np.nan, np.float32)
    E2[np.ix_(izf[okz], ixf[okx])] = eta[np.ix_(okz, okx)]
    hfs.append(E2)
    n = -1
    if f % 24 == 0 or f == f0 or f == f1:
        try:
            n = dop.simulation().findObject("water").geometry().intrinsicValue("pointcount")
        except Exception as e:
            info.setdefault("particle_errors", []).append(str(e)[:200])
    if probe is not None and f % 6 == 0:
        try:
            gp = probe.geometry()
            pu = None
            for pr in gp.prims():
                nm = pr.attribValue("name") if gp.findPrimAttrib("name") else ""
                if nm in ("vel.x", "x", "vel") or (pu is None and pr.number() == 0):
                    pu = pr
                    if nm in ("vel.x", "x"):
                        break
            if pu is not None:
                prb_u.append([[float(pu.sample(hou.Vector3(xp, yp, 0.0))) for yp in PRB_Y] for xp in PRB_X])
                prb_t.append((f - 1) / fps)
        except Exception as e:
            if len(info.get("probe_errors", [])) < 5:
                info.setdefault("probe_errors", []).append(str(e)[:200])
    if int(args.get("diag", 0)) and f in (f0, f0 + 1, f0 + 2, f0 + 48):
        try:
            gd = fd.geometry()
            out = {}
            for pr in gd.prims():
                nm = pr.attribValue("name") if gd.findPrimAttrib("name") else str(pr.number())
                pts = [(4.0, -5.0), (float(P["xp0"]) - 1.0, -5.0), (float(P["xp0"]) + 1.5, -5.0), (100.0, -float(P["h0"]) - 1.0), (100.0, -1.0), (100.0, 1.0)]
                out[nm] = [[x, y, round(float(pr.sample(hou.Vector3(x, y, 0.0))), 4)] for x, y in pts]
            info.setdefault("diag", {})[str(f)] = out
            print("DIAG f=%d %s" % (f, json.dumps(out)))
        except Exception as e:
            info.setdefault("diag_errors", []).append(str(e)[:300])
    r, pk = rss_gb()
    mid = E2[:, (FX > 0.2 * Lx) & (FX < 0.6 * Lx)]
    lvl = float(np.nanmean(mid)) if np.isfinite(mid).any() else -999.0
    frames.append(f); wall.append(dt); npts.append(n); tsim.append((f - 1) / fps); lvls.append(lvl)
    if lvl0 is None:
        lvl0 = lvl
    if f % 48 == 0 or f == f0:
        print("f=%d t=%.2f sim=%.2fs pts=%d rss=%.2fGB lvl=%.3f eta_min=%.2f eta_max=%.2f" % (
            f, (f - 1) / fps, dt, n, r, lvl, np.nanmin(E2), np.nanmax(E2)))
        sys.stdout.flush()

    def save():
        np.savez_compressed(os.path.join(OUT, "hf_c%04d.npz" % f0), eta=np.array(hfs, np.float32), x=FX, z=FZ,
                            frames=np.array(frames), t=np.array(tsim), wall=np.array(wall), npts=np.array(npts), lvl=np.array(lvls),
                            grid=json.dumps(grid_info), up=np.array(prb_u, np.float32), tp=np.array(prb_t), prb_x=np.array(PRB_X), prb_y=np.array(PRB_Y))
    if f % 240 == 0:
        save()
    if time.time() - t_start > wall_limit:
        stopped = "wall_limit at frame %d" % f
        break
    if f - f0 >= 6 and lvl - lvl0 < -lvl_guard:
        stopped = "free_fall at frame %d (mean level %.2f m, start %.2f m)" % (f, lvl, lvl0)
        break
    if not np.isfinite(E2).any():
        stopped = "no water at frame %d" % f
        break

np.savez_compressed(os.path.join(OUT, "hf_c%04d.npz" % f0), eta=np.array(hfs, np.float32), x=FX, z=FZ,
                    frames=np.array(frames), t=np.array(tsim), wall=np.array(wall), npts=np.array(npts), lvl=np.array(lvls),
                    grid=json.dumps(grid_info), up=np.array(prb_u, np.float32), tp=np.array(prb_t), prb_x=np.array(PRB_X), prb_y=np.array(PRB_Y))
wall_total = time.time() - t_start
ck = sorted(os.listdir(ckdir)) if os.path.isdir(ckdir) else []
ck_bytes = sum(os.path.getsize(os.path.join(ckdir, x)) for x in ck)
nn = [v for v in npts if v >= 0]
rec = {
    "stage": "FLIP41 verify", "run_id": rid, "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    "houdini": hou.applicationVersionString(), "hip": HIP, "hip_sha256": HIP_SHA,
    "parms": {k: P[k] for k in P}, "solver": sv, "case": args.get("case", {}),
    "f_start": f0, "f_end_req": f1, "f_end_done": frames[-1] if frames else None, "fps": fps,
    "ckpt_dir": ckdir, "ckpt_files": len(ck), "ckpt_gb": round(ck_bytes / 2**30, 3),
    "particles_first": nn[0] if nn else None, "particles_max": max(nn) if nn else None,
    "wall_total_s": round(wall_total, 1), "wall_launch_s": round(time.time() - t_launch, 1),
    "wall_per_frame_median_s": round(float(np.median(wall[1:])) if len(wall) > 1 else 0, 3),
    "rss_peak_gb": round(rss_gb()[1], 2),
    "level_start_m": lvl0, "level_min_m": float(np.min(lvls)) if lvls else None,
    "stopped": stopped, "info": info, "note": args.get("note", ""), "grid": grid_info,
}
json.dump(rec, open(os.path.join(OUT, "run_c%04d.json" % f0), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
if f0 == 1:
    json.dump(rec, open(os.path.join(OUT, "run.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
with open(os.path.join(ROOT, "runs.jsonl"), "a", encoding="utf8") as fh:
    fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
print("DONE", json.dumps({k: rec[k] for k in ("run_id", "f_end_done", "wall_total_s", "particles_max", "rss_peak_gb", "stopped")}))
