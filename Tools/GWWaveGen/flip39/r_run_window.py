# -*- coding: utf-8 -*-
"""FLIP39 R 主役の範囲の計算を 1 回（1 区切り）走らせて記録する（hython）。FLIP37 の run_p3.py を写し、場面・出力先・ノードの名前と、
z の低い側（E3 の壁＝対称の面、境界の帯なし）の扱いだけを替えた。

使い方: hython run_p3.py '<JSON>'
JSON: {"run_id": "...", "parms": {...CTRL の値...}, "f_start": F0 か 続きのコマ, "f_end": 274,
       "ckpt_on": 1, "ckpt_dir": "...", "ckpt_every": 12,
       "snap_from": .., "snap_every": 2, "snap_zc": [-60, ..., 60], "snap_zhalf": 0.75,
       "mesh_from": .., "mesh_every": 1, "mesh_bgeo": 1, "wall_limit_s": 1740, "note": "...", "part": "A"}
続き（f_start > F0）：同じ ckpt_dir の途中保存（p3.$SF4.sim、$SF = F − F0 + 1）から DOP が読み込んで続ける。
出力: Unity/Build/FLIP39/R/<run_id>/
  hf_<part>.npz  水面の場から読んだ一番上の水面 η(z, x)（毎コマ、float16、升目は格子の大きさ）と張り出しの印
  crest_<part>.npy  毎コマ・z の 5 m の帯ごとの頂（最も高い粒子の y・x、その近くの水平の流速の最大）
  sec/zXXXX/snap_FFFF.npz  z の切り口の粒子：x, y, vx, vy（P1 の解析の道具で読める形）
  mesh/mesh_FFFF.npz（P float32、tri int32）と mesh/mesh_FFFF.bgeo.sc（網目、VDB from particles、軽いなめらかさ）
  run_<part>.json、runs.jsonl に 1 行。
見張り：主役の範囲の内側（境界の帯を除く）の水面の平均が始めより 1 m 以上下がったら止める（P0 §3.4 の自由落下）。
30 分の決まり：途中保存のコマで、次の途中保存までの見込みが wall_limit を超えるなら止める（続きはそのコマから）。
粗い場のファイル（境界）が書き出し中なら、次のコマの分ができるまで待つ（書き出しと並べて走らせるため）。
"""
import hou, sys, os, json, time, ctypes, hashlib
from ctypes import wintypes
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip37")
import p3_nothrottle
NOTHROTTLE = p3_nothrottle.off()

HIP = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP39/r_window.hiplc"
ROOT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39"
args = json.loads(sys.argv[1])
rid = args["run_id"]
part = args.get("part", "A")
OUT = os.path.join(ROOT, "R", rid).replace("\\", "/")
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
ctrl = hou.node("/obj/R_SETUP/CTRL")
for k, v in args.get("parms", {}).items():
    ctrl.parm(k).set(v)
ckdir = args.get("ckpt_dir", os.path.join(OUT, "ckpt")).replace("\\", "/")
os.makedirs(ckdir, exist_ok=True)
ctrl.parm("ckpt").set(ckdir)
ctrl.parm("ckpt_on").set(int(args.get("ckpt_on", 1)))
ckev = int(args.get("ckpt_every", 12))
ctrl.parm("ckpt_every").set(ckev)
hou.setSimulationEnabled(True)
fps = hou.fps()
dop = hou.node("/obj/R_SIM")
fi = hou.node("/obj/R_READ/surface_field")
mesh_node = hou.node("/obj/R_READ/OUT_MESH")
P = {p.name(): p.eval() for p in ctrl.parms()}
F0 = int(round(P["F0"]))
f0, f1 = int(args.get("f_start", F0)), int(args["f_end"])
snap_from = int(args.get("snap_from", F0))
snap_every = int(args.get("snap_every", 2))
szh = float(args.get("snap_zhalf", 0.75))
szc = [float(v) for v in args.get("snap_zc", [-60, -40, -20, 0, 20, 40, 60])]
symin = float(args.get("snap_ymin", -25.0))
mesh_from = int(args.get("mesh_from", F0))
mesh_every = int(args.get("mesh_every", 1))
mesh_bgeo = int(args.get("mesh_bgeo", 0))
crest_every = int(args.get("crest_every", 1))   # 粒子を読んで頂の表を作る間隔（00:15 追加。0.25 m では粒子 3,400 万個の読み出しに 1 コマ 20 秒かかったため）
wall_limit = float(args.get("wall_limit_s", 1740))
VOX = float(P["dp"]) * float(P["gridscale"])
pad = float(P["pad"]); padz0 = float(P.get("padz0", pad))
wx0, wx1, wz0, wz1 = (float(P[k]) for k in ("wx0", "wx1", "wz0", "wz1"))
sx0, sx1 = wx0 + pad, wx1 - pad
FX = np.arange(wx0 + 0.5 * VOX, wx1, VOX); FZ = np.arange(wz0 + 0.5 * VOX, wz1, VOX)   # 場の升の中心
inner_x = (FX > wx0 + pad + 2) & (FX < wx1 - pad - 2); inner_z = (FZ > wz0 + padz0 + 2) & (FZ < wz1 - pad - 2)
zbins = np.arange(wz0, wz1 + 1e-6, 5.0)
cdir = P["cdir"]
_lr = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/R/lvl_ref_%g_%g_%g_%g_%g.json" % (wx0, wx1, wz0, wz1, pad)
LREF = {int(k): v for k, v in json.load(open(_lr)).items()} if os.path.isfile(_lr) else {}
for zc in szc:
    sd = os.path.join(OUT, "sec", "z%+04d" % int(round(zc)))
    os.makedirs(sd, exist_ok=True)
    json.dump({"run_id": rid + "/z%+04d" % int(round(zc)), "parms": {k: P[k] for k in P if not k.startswith("folder")} | {"W": 2 * szh, "xc0": 330.0, "wave_mode": 0.0},
               "snap": {"from": snap_from, "every": snap_every, "x": [sx0, sx1], "ymin": symin, "zhalf": szh, "zc": zc}},
              open(os.path.join(sd, "run.json"), "w", encoding="utf8"), ensure_ascii=False, default=str)
os.makedirs(os.path.join(OUT, "mesh"), exist_ok=True)


def wait_coarse(f):
    """境界のコマ f+1 の粗い場が書き終わるまで待つ（f+2 のファイルか、書き出しの run.json ができたら終わり）。"""
    need = min(f + 2, int(P["cf_max"]))
    t0 = time.time()
    while True:
        if os.path.isfile(os.path.join(cdir, "c_%04d.bgeo.sc" % need)) or os.path.isfile(os.path.join(os.path.dirname(cdir), "run.json")):
            return time.time() - t0
        time.sleep(2.0)


frames, wall, wall_io, wall_mesh, npts, rss, peak, tsim, lvls, waits = [], [], [], [], [], [], [], [], [], []
hfs, segs, crest = [], [], []
info = {"nothrottle": list(NOTHROTTLE)}
t_start = time.time()
stopped = None
lvl0 = None
grid_info = None
last_ckpt_frame = None


def save_hf():
    np.savez_compressed(os.path.join(OUT, "hf_%s.npz" % part), eta=np.array(hfs), seg=np.array(segs), frames=np.array(frames),
                        t=np.array(tsim), grid=json.dumps(grid_info), wall=np.array(wall), npts=np.array(npts), lvl=np.array(lvls))
    np.save(os.path.join(OUT, "crest_%s.npy" % part), np.array(crest, dtype=np.float64))


for f in range(f0, f1 + 1):
    waits.append(wait_coarse(f))
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
                     "z0": float(FZ[0]), "dz": VOX, "vol_x0": float(xs[0]), "vol_z0": float(zs[0]), "pad": pad,
                     "window": [wx0, wx1, wz0, wz1]}
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
    nb = neg[:, jlow:, :].astype(np.int8)
    starts = (np.diff(nb, axis=1) == 1).sum(axis=1) + nb[:, 0, :]
    del a, neg, nb
    ixf = np.floor((xs - FX[0]) / VOX + 0.5).astype(int); izf = np.floor((zs - FZ[0]) / VOX + 0.5).astype(int)
    okx = (ixf >= 0) & (ixf < len(FX)); okz = (izf >= 0) & (izf < len(FZ))
    E2 = np.full((len(FZ), len(FX)), np.nan, np.float32); S2 = np.zeros((len(FZ), len(FX)), np.uint8)
    E2[np.ix_(izf[okz], ixf[okx])] = eta[np.ix_(okz, okx)]
    S2[np.ix_(izf[okz], ixf[okx])] = np.clip(starts, 0, 255).astype(np.uint8)[np.ix_(okz, okx)]
    hfs.append(E2.astype(np.float16)); segs.append(S2)
    n = -1
    need_p = (f - f0) % crest_every == 0 or (f >= snap_from and ((f - snap_from) % snap_every == 0 or f == f1))
    try:
        if not need_p:
            raise StopIteration
        obj = dop.simulation().findObject("water")
        pg = obj.geometry()
        n = pg.intrinsicValue("pointcount")
        Pp = np.frombuffer(pg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3)
        V = np.frombuffer(pg.pointFloatAttribValuesAsString("v"), dtype=np.float32).reshape(-1, 3)
        hi = Pp[:, 1] > 2.0
        Ph, Vh = Pp[hi], V[hi]
        ib = np.clip(np.digitize(Ph[:, 2], zbins) - 1, 0, len(zbins) - 2)
        row = [f, (f - 1) / fps]
        for b in range(len(zbins) - 1):
            m = ib == b
            if m.any():
                k = int(np.argmax(Ph[m, 1]))
                yb_, xb_ = float(Ph[m][k, 1]), float(Ph[m][k, 0])
                near = m.copy(); near[m] = (np.abs(Ph[m, 0] - xb_) < 2.0) & (Ph[m, 1] > yb_ - 1.5)
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
        del Pp, V, Ph, Vh
    except StopIteration:
        pass
    except Exception as e:
        info.setdefault("particle_errors", []).append(str(e)[:200])
    t2 = time.time()
    if f >= mesh_from and ((f - mesh_from) % mesh_every == 0 or f == f1):
        try:
            mg = mesh_node.geometry()
            MP = np.frombuffer(mg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3)
            tri = np.frombuffer(mg.vertexIntAttribValuesAsString("pt"), dtype=np.int32).reshape(-1, 3)
            used = np.unique(tri)
            remap = -np.ones(len(MP), np.int32); remap[used] = np.arange(len(used), dtype=np.int32)
            np.savez_compressed(os.path.join(OUT, "mesh", "mesh_%04d.npz" % f), P=MP[used], tri=remap[tri], t=(f - 1) / fps)
            if mesh_bgeo:
                mg.saveToFile(os.path.join(OUT, "mesh", "mesh_%04d.bgeo.sc" % f))
            info.setdefault("mesh_tris", []).append([f, int(len(tri))])
        except Exception as e:
            info.setdefault("mesh_errors", []).append(str(e)[:200])
    wall_mesh.append(time.time() - t2)
    r, pk = rss_gb()
    ein = E2[np.ix_(inner_z, inner_x)]
    lvl = float(np.nanmean(ein)) if np.isfinite(ein).any() else -999.0
    frames.append(f); wall.append(dt); wall_io.append(time.time() - t1); npts.append(n); rss.append(r); peak.append(pk)
    tsim.append((f - 1) / fps); lvls.append(lvl)
    lrel = lvl - LREF.get(f, 0.0)   # E3（粗い計算）の同じ所・同じコマの平均との差（波の出入りを除く）
    if lvl0 is None:
        lvl0 = lvl; lrel0 = lrel
    if (f - f0) % 6 == 0 or f == f0:
        cc = np.array(crest[-1][2::3], float) if crest else np.array([np.nan])
        print("f=%d t=%.2f sim=%.2fs io=%.2fs mesh=%.2fs wait=%.1fs pts=%d rss=%.2fGB peak=%.2fGB lvl=%.3f rel=%.3f crest_max=%.2f crest_mid=%.2f" % (
            f, (f - 1) / fps, dt, wall_io[-1], wall_mesh[-1], waits[-1], n, r, pk, lvl, lrel, np.nanmax(cc), cc[len(cc) // 2]))
        sys.stdout.flush()
    if (f - f0) % 24 == 0:
        save_hf()
    sf = f - F0 + 1
    if int(args.get("ckpt_on", 1)) and sf % ckev == 0:
        last_ckpt_frame = f
        el = time.time() - t_start
        per = float(np.median(np.array(wall[-6:]) + np.array(wall_io[-6:])))
        if el + per * ckev * 1.2 > wall_limit and f < f1:
            stopped = "chunk_end at checkpoint frame %d (elapsed %.0f s, next checkpoint needs ~%.0f s)" % (f, el, per * ckev * 1.2)
            break
    if time.time() - t_start > wall_limit:
        stopped = "wall_limit at frame %d" % f
        break
    if f - f0 >= 6 and lrel - lrel0 < -1.0:
        stopped = "free_fall at frame %d (mean level minus E3 %.2f m, start %.2f m)" % (f, lrel, lrel0)
        break

save_hf()
wall_total = time.time() - t_start
ck = sorted(os.listdir(ckdir)) if os.path.isdir(ckdir) else []
ck_bytes = sum(os.path.getsize(os.path.join(ckdir, x)) for x in ck)
rec = {
    "stage": "R", "run_id": rid, "part": part, "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    "houdini": hou.applicationVersionString(), "hip": HIP, "hip_sha256": HIP_SHA,
    "parms": {k: P[k] for k in P if not k.startswith("folder")},
    "f_start": f0, "f_end_req": f1, "f_end_done": frames[-1] if frames else None, "fps": fps, "F0": F0,
    "ckpt_dir": ckdir, "ckpt_on": int(args.get("ckpt_on", 1)), "ckpt_every": ckev, "ckpt_files": len(ck), "ckpt_gb": round(ck_bytes / 2**30, 3),
    "last_ckpt_frame": last_ckpt_frame,
    "particles_first": npts[0] if npts else None, "particles_max": max(npts) if npts else None,
    "particles_last": npts[-1] if npts else None,
    "wall_total_s": round(wall_total, 1), "wall_launch_s": round(time.time() - t_launch, 1),
    "wall_first_frame_s": round(wall[0], 2) if wall else None,
    "wall_per_frame_median_s": round(float(np.median(wall[1:])) if len(wall) > 1 else 0, 3),
    "io_per_frame_median_s": round(float(np.median(wall_io)) if wall_io else 0, 3),
    "mesh_per_frame_median_s": round(float(np.median(wall_mesh)) if wall_mesh else 0, 3),
    "wait_total_s": round(float(np.sum(waits)), 1),
    "rss_last_gb": round(rss[-1], 2) if rss else None, "rss_peak_gb": round(max(peak), 2) if peak else None,
    "level_start_m": lvl0, "lvl_ref_file": _lr if LREF else None, "level_min_m": float(np.min(lvls)) if lvls else None,
    "stopped": stopped, "info": info, "note": args.get("note", ""),
    "concurrent_with": args.get("concurrent_with"),
    "snap": {"from": snap_from, "every": snap_every, "x": [sx0, sx1], "ymin": symin, "zhalf": szh, "zc": szc},
    "mesh": {"from": mesh_from, "every": mesh_every, "bgeo": mesh_bgeo}, "grid": grid_info,
}
json.dump(rec, open(os.path.join(OUT, "run_%s.json" % part), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
with open(os.path.join(ROOT, "runs.jsonl"), "a", encoding="utf8") as fh:
    fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
print("DONE", json.dumps({k: rec[k] for k in ("run_id", "part", "f_end_done", "wall_total_s", "wall_per_frame_median_s", "particles_max", "rss_peak_gb", "stopped")}))
