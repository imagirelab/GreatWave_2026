# -*- coding: utf-8 -*-
"""FLIP39 E の計算を 1 回走らせて記録する（hython で実行）。FLIP37 の run_p2.py を複製し、成分の表の書き込み・出力先・区切りの名前だけ替えた。

使い方: hython run_p2.py '<JSON>'
JSON: {"run_id": "...", "parms": {...}, "f_start": 1, "f_end": 360,
       "ckpt_on": 0|1, "ckpt_dir": "...", "ckpt_every": 48,
       "snap_from": 120, "snap_every": 2, "snap_x": [380, 806], "snap_ymin": -25, "snap_zhalf": 1.5,
       "snap_zc": [-100, -80, ..., 100],
       "mesh_from": 96, "mesh_every": 3,
       "wall_limit_s": 1680, "note": "..."}
出力: G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P2/<run_id>/
  hf.npz        水面の場から読んだ一番上の水面 η(z, x)（毎コマ、float16）と、列ごとの水の区間の数（張り出しの印、uint8）
  crest.npy     毎コマ・z の帯ごとの頂（最も高い粒子の y・x、その近くの水平の流速の最大）
  sec/zXXXX/snap_FFFF.npz  z の切り口の粒子（|z-zc| < snap_zhalf）：x, y, vx, vy（P1 の解析の道具で読める形）
  mesh/mesh_FFFF.npz  水面の網目（箱の中、三角形）：P（float32）、tri（int32）
  run.json      条件と記録。Unity/Build/FLIP37/runs.jsonl にも 1 行足す。
見張り：水槽全体の水面の平均が始めより 1 m 以上下がったら止めて stopped=free_fall と記録する（P0 §3.4 の失敗）。
"""
import hou, sys, os, json, time, ctypes, hashlib
from ctypes import wintypes
import numpy as np

HIP = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP39/e_tank.hiplc"
ROOT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39"
args = json.loads(sys.argv[1])
rid = args["run_id"]
OUT = os.path.join(ROOT, "E", rid).replace("\\", "/")
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
ctrl = hou.node("/obj/E_SETUP/CTRL")
for k, v in args.get("parms", {}).items():
    ctrl.parm(k).set(v)
# 成分の表を作り、VEX の配列として各ノードに書き込む（e_tanklib）
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
import e_tanklib as L
grp_args = args.get("group", {"A_f": 0.0})
bedp = {k: ctrl.parm(k).eval() for k in ("h0", "hr", "slope_n", "xs0", "lg1_d", "lg1_x", "lg1_sx")}
bedp["flat"] = bool(args.get("flat", False))
COMP = L.comp_table(grp_args, bedp, ctrl.parm("Lz").eval())
for path in L.BODIES:
    hou.node(path).parm("snippet").set(L.snippet(path, COMP))
json.dump({"group": grp_args, "bed": bedp, "n_components": int(len(COMP["a"])),
           "a": COMP["a"].tolist(), "om": COMP["om"].tolist(), "kx0": COMP["kx0"].tolist(), "kz": COMP["kz"].tolist(),
           "k0": COMP["k0"].tolist(), "phi": COMP["phi"].tolist(), "h0": COMP["h0"], "zf": COMP["zf"],
           "n": [int(v) for v in COMP["n"]]}, open(os.path.join(OUT, "comp_c%04d.json" % int(args["f_start"])), "w", encoding="utf8"), indent=1)
ckdir = args.get("ckpt_dir", os.path.join(OUT, "ckpt")).replace("\\", "/")
if int(args.get("ckpt_on", 0)) or int(args["f_start"]) > 1:
    os.makedirs(ckdir, exist_ok=True)
ctrl.parm("ckpt").set(ckdir)
ctrl.parm("ckpt_on").set(int(args.get("ckpt_on", 0)))
ctrl.parm("ckpt_every").set(int(args.get("ckpt_every", 48)))
hou.setSimulationEnabled(True)
fps = hou.fps()
dop = hou.node("/obj/E_SIM")
fi = hou.node("/obj/E_READ/surface_field")
mesh_node = hou.node("/obj/E_READ/OUT_MESH")
f0, f1 = int(args["f_start"]), int(args["f_end"])
snap_from = int(args.get("snap_from", 1))
snap_every = int(args.get("snap_every", 2))
sx0, sx1 = args.get("snap_x", [0.0, 1e9])
symin = float(args.get("snap_ymin", -25.0))
szh = float(args.get("snap_zhalf", 1.5))
szc = [float(v) for v in args.get("snap_zc", [-100, -80, -60, -40, -20, 0, 20, 40, 60, 80, 100])]
mesh_from = int(args.get("mesh_from", 96))
mesh_every = int(args.get("mesh_every", 3))
wall_limit = float(args.get("wall_limit_s", 1680))
lvl_guard = float(args.get("level_guard_m", 1.0))
P = {p.name(): p.eval() for p in ctrl.parms()}
P["explicitcachename_eval"] = dop.parm("explicitcachename").eval()
Lz = float(P["Lz"])
VOX = float(P["dp"]) * float(P["gridscale"])
FX = np.arange(0.0, float(P["Lx"]) + 1e-6, VOX); FZ = np.arange(-0.5 * Lz, 0.5 * Lz + 1e-6, VOX)   # 場の標本の位置（格子の節。0, 2, 4, …）
zbins = np.arange(-0.5 * Lz, 0.5 * Lz + 1e-6, 10.0)
for zc in szc:
    os.makedirs(os.path.join(OUT, "sec", "z%+04d" % int(round(zc))), exist_ok=True)
os.makedirs(os.path.join(OUT, "mesh"), exist_ok=True)
# 切り口のフォルダーに P1 の解析の道具が読む run.json を置く（parms は同じ。snap は切り口の値）
for zc in szc:
    sd = os.path.join(OUT, "sec", "z%+04d" % int(round(zc)))
    json.dump({"run_id": rid + "/z%+04d" % int(round(zc)), "parms": {k: P[k] for k in P if not k.startswith("folder")} | {"W": 2 * szh},
               "snap": {"from": snap_from, "every": snap_every, "x": [sx0, sx1], "ymin": symin, "zhalf": szh, "zc": zc}},
              open(os.path.join(sd, "run.json"), "w", encoding="utf8"), ensure_ascii=False, default=str)

frames, wall, wall_io, npts, rss, peak, tsim, lvls = [], [], [], [], [], [], [], []
hfs, segs = [], []
crest = []
info = {}
t_start = time.time()
stopped = None
lvl0 = None
grid_info = None
for f in range(f0, f1 + 1):
    t0 = time.time()
    hou.setFrame(f)
    g = fi.geometry()
    dt = time.time() - t0
    t1 = time.time()
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
    jlow = int(np.searchsorted(y_c, -3.0))
    if grid_info is None or grid_info["res"] != [nx, ny, nz]:
        grid_info = {"res": [nx, ny, nz], "x0": float(FX[0]), "dx": VOX, "y0": float(y_c[0]),
                     "z0": float(FZ[0]), "dz": VOX, "vol_x0": float(xs[0]), "vol_z0": float(zs[0])}
        info.setdefault("res_changes", []).append([f] + grid_info["res"])
    a = np.frombuffer(vol.allVoxelsAsString(), dtype=np.float32).reshape(nz, ny, nx)
    neg = a < 0
    has = neg.any(axis=1)                                  # (nz, nx)
    jtop = ny - 1 - np.argmax(neg[:, ::-1, :], axis=1)     # 一番上の水の升
    jtop = np.clip(jtop, 0, ny - 2)
    iz_, ix_ = np.meshgrid(np.arange(nz), np.arange(nx), indexing="ij")
    vj = a[iz_, jtop, ix_]; vj1 = a[iz_, jtop + 1, ix_]
    frac = np.where(vj1 - vj > 1e-9, -vj / np.maximum(vj1 - vj, 1e-9), 0.0)
    eta = np.where(has, y_c[jtop] + dy * np.clip(frac, 0, 1), np.nan)
    # 水の区間の数（y > -3 m の所で、上から水→空気→水 があれば 2 以上＝張り出し・空洞）
    nb = neg[:, jlow:, :].astype(np.int8)
    starts = (np.diff(nb, axis=1) == 1).sum(axis=1) + nb[:, 0, :]
    # 場の大きさはコマで変わりうる（最初のコマは初めの VDB の大きさ）。決まった升目（格子の中心、x 0〜Lx、z −Lz/2〜Lz/2）へ置き直す
    ixf = np.floor((xs - FX[0]) / VOX + 0.5).astype(int); izf = np.floor((zs - FZ[0]) / VOX + 0.5).astype(int)
    okx = (ixf >= 0) & (ixf < len(FX)); okz = (izf >= 0) & (izf < len(FZ))
    E2 = np.full((len(FZ), len(FX)), np.nan, np.float32); S2 = np.zeros((len(FZ), len(FX)), np.uint8)
    E2[np.ix_(izf[okz], ixf[okx])] = eta[np.ix_(okz, okx)]
    S2[np.ix_(izf[okz], ixf[okx])] = np.clip(starts, 0, 255).astype(np.uint8)[np.ix_(okz, okx)]
    eta = E2
    hfs.append(E2.astype(np.float16)); segs.append(S2)
    n = -1
    try:
        obj = dop.simulation().findObject("water")
        pg = obj.geometry()
        n = pg.intrinsicValue("pointcount")
        Pp = np.frombuffer(pg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3)
        V = np.frombuffer(pg.pointFloatAttribValuesAsString("v"), dtype=np.float32).reshape(-1, 3)
        # z の帯（10 m）ごとの頂
        hi = Pp[:, 1] > 2.0
        Ph, Vh = Pp[hi], V[hi]
        ib = np.clip(np.digitize(Ph[:, 2], zbins) - 1, 0, len(zbins) - 2)
        row = [f, (f - 1) / fps]
        for b in range(len(zbins) - 1):
            m = ib == b
            if m.any():
                k = int(np.argmax(Ph[m, 1]))
                yb_, xb_ = float(Ph[m][k, 1]), float(Ph[m][k, 0])
                near = m.copy(); near[m] = (np.abs(Ph[m, 0] - xb_) < 3.0) & (Ph[m, 1] > yb_ - 2.0)
                row += [yb_, xb_, float(Vh[near, 0].max()) if near.any() else 0.0]
            else:
                row += [np.nan, np.nan, np.nan]
        crest.append(row)
        if f >= snap_from and ((f - snap_from) % snap_every == 0 or f == f1):
            base = (Pp[:, 0] >= sx0) & (Pp[:, 0] <= sx1) & (Pp[:, 1] >= symin)
            for zc in szc:
                m = base & (np.abs(Pp[:, 2] - zc) < szh)
                np.savez_compressed(os.path.join(OUT, "sec", "z%+04d" % int(round(zc)), "snap_%04d.npz" % f),
                                    x=Pp[m, 0], y=Pp[m, 1], vx=V[m, 0], vy=V[m, 1], n=n, t=(f - 1) / fps, zhalf=szh)
    except Exception as e:
        info.setdefault("particle_errors", []).append(str(e)[:200])
    if f >= mesh_from and ((f - mesh_from) % mesh_every == 0 or f == f1):
        try:
            mg = mesh_node.geometry()
            MP = np.frombuffer(mg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3)
            tri = np.frombuffer(mg.vertexIntAttribValuesAsString("pt"), dtype=np.int32).reshape(-1, 3)
            used = np.unique(tri)
            remap = -np.ones(len(MP), np.int32); remap[used] = np.arange(len(used), dtype=np.int32)
            np.savez_compressed(os.path.join(OUT, "mesh", "mesh_%04d.npz" % f), P=MP[used], tri=remap[tri], t=(f - 1) / fps)
        except Exception as e:
            info.setdefault("mesh_errors", []).append(str(e)[:200])
    r, pk = rss_gb()
    lvl = float(np.nanmean(eta)) if np.isfinite(eta).any() else -999.0
    frames.append(f); wall.append(dt); wall_io.append(time.time() - t1); npts.append(n); rss.append(r); peak.append(pk)
    tsim.append((f - 1) / fps); lvls.append(lvl)
    if lvl0 is None:
        lvl0 = lvl
    if f % 24 == 0 or f == f0:
        cc = np.array(crest[-1][2::3], float) if crest else np.array([np.nan])
        print("f=%d t=%.2f sim=%.2fs io=%.2fs pts=%d rss=%.2fGB lvl=%.3f crest_max=%.2f crest_mid=%.2f" % (
            f, (f - 1) / fps, dt, wall_io[-1], n, r, lvl, np.nanmax(cc), cc[len(cc) // 2]))
        sys.stdout.flush()
    if f % 96 == 0:
        np.savez_compressed(os.path.join(OUT, "hf_c%04d.npz" % f0), eta=np.array(hfs), seg=np.array(segs), frames=np.array(frames),
                            t=np.array(tsim), grid=json.dumps(grid_info), wall=np.array(wall), npts=np.array(npts), lvl=np.array(lvls))
        np.save(os.path.join(OUT, "crest_c%04d.npy" % f0), np.array(crest, dtype=np.float64))
    if time.time() - t_start > wall_limit:
        stopped = "wall_limit at frame %d" % f
        break
    if f - f0 >= 6 and lvl - lvl0 < -lvl_guard:
        stopped = "free_fall at frame %d (mean level %.2f m, start %.2f m)" % (f, lvl, lvl0)
        break

np.savez_compressed(os.path.join(OUT, "hf_c%04d.npz" % f0), eta=np.array(hfs), seg=np.array(segs), frames=np.array(frames),
                    t=np.array(tsim), grid=json.dumps(grid_info), wall=np.array(wall), npts=np.array(npts), lvl=np.array(lvls))
np.save(os.path.join(OUT, "crest_c%04d.npy" % f0), np.array(crest, dtype=np.float64))
wall_total = time.time() - t_start
ck = sorted(os.listdir(ckdir)) if os.path.isdir(ckdir) else []
ck_bytes = sum(os.path.getsize(os.path.join(ckdir, x)) for x in ck)
rec = {
    "stage": "E", "group": grp_args, "flat": bool(args.get("flat", False)), "run_id": rid, "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    "houdini": hou.applicationVersionString(), "hip": HIP, "hip_sha256": HIP_SHA,
    "parms": {k: P[k] for k in P if not k.startswith("folder")},
    "f_start": f0, "f_end_req": f1, "f_end_done": frames[-1] if frames else None, "fps": fps,
    "ckpt_dir": ckdir, "ckpt_on": int(args.get("ckpt_on", 0)), "ckpt_files": len(ck), "ckpt_gb": round(ck_bytes / 2**30, 3),
    "particles_first": npts[0] if npts else None, "particles_max": max(npts) if npts else None,
    "particles_last": npts[-1] if npts else None,
    "wall_total_s": round(wall_total, 1), "wall_launch_s": round(time.time() - t_launch, 1),
    "wall_first_frame_s": round(wall[0], 2) if wall else None,
    "wall_per_frame_median_s": round(float(np.median(wall[1:])) if len(wall) > 1 else 0, 3),
    "io_per_frame_median_s": round(float(np.median(wall_io)) if wall_io else 0, 3),
    "rss_last_gb": round(rss[-1], 2) if rss else None, "rss_peak_gb": round(max(peak), 2) if peak else None,
    "level_start_m": lvl0, "level_min_m": float(np.min(lvls)) if lvls else None,
    "stopped": stopped, "info": info, "note": args.get("note", ""),
    "concurrent_with": args.get("concurrent_with"),
    "snap": {"from": snap_from, "every": snap_every, "x": [sx0, sx1], "ymin": symin, "zhalf": szh, "zc": szc},
    "mesh": {"from": mesh_from, "every": mesh_every}, "grid": grid_info,
}
json.dump(rec, open(os.path.join(OUT, "run_c%04d.json" % f0), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
if f0 == 1:
    json.dump(rec, open(os.path.join(OUT, "run.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
with open(os.path.join(ROOT, "runs.jsonl"), "a", encoding="utf8") as fh:
    fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
print("DONE", json.dumps({k: rec[k] for k in ("run_id", "f_end_done", "wall_total_s", "particles_max", "rss_peak_gb", "stopped")}))
