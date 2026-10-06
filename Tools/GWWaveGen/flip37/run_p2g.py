# -*- coding: utf-8 -*-
"""P2g 誘導の双子の計算を 1 回走らせて記録する（hython で実行）。run_p2.py の複製に、次を足した（2026-10-06）：
- 場面は Houdini/FLIP37/p2g_tank.hiplc（P2 の版 3 に誘導の節 guide を足したもの）。出力は Unity/Build/FLIP37/P2g/<run_id>/。
- 波のエネルギー（運動 + 位置）を 12 コマごとと誘導の時間の中の毎コマで、誘導の仕事・力の最大と平均・当てた体積を毎コマで測り、
  energy.json に書く（格子の vel と surface の場から。誘導の加速度は guide の節と同じ式を numpy で）。
以下は run_p2.py の説明。
P2 の粗い 3D の計算を 1 回走らせて記録する（hython で実行）。run_p1.py を元にした。

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

HIP = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP37/p2g_tank.hiplc"
ROOT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37"
args = json.loads(sys.argv[1])
rid = args["run_id"]
OUT = os.path.join(ROOT, "P2g", rid).replace("\\", "/")
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
ctrl = hou.node("/obj/P2_SETUP/CTRL")
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
dop = hou.node("/obj/P2_SIM")
fi = hou.node("/obj/P2_READ/surface_field")
mesh_node = hou.node("/obj/P2_READ/OUT_MESH")
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
P = {p.name(): p.eval() for p in ctrl.parms()}
P["explicitcachename_eval"] = dop.parm("explicitcachename").eval()
RHO, GRAV = 1000.0, 9.80665
GA = float(P.get("g_amp", 0.0))
TAB = json.load(open(os.path.join(ROOT, "P2g", "guide_crest_table.json")))
TT_, ZC_, XT_ = np.array(TAB["t"]), np.array(TAB["z"]), np.array(TAB["x"])
ENERGY, W_ACC, ETA_REF = [], [0.0], [None]
vnode = hou.node("/obj/P2_READ/OUT_VEL_FIELD")


def smooth01(a0, a1, v):
    u = np.clip((np.asarray(v, float) - a0) / (a1 - a0), 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def wt_of(t):
    return float(smooth01(P["g_t0"], P["g_t0"] + P["g_ramp"], t) * (1.0 - smooth01(P["g_t1"] - P["g_ramp"], P["g_t1"], t)))


def guide_weight(t, X, Z, Y=None):
    """guide の節と同じ重み W(x, y, z, t)（配列 (nz, ny, nx)。Y が None なら (nz, 1, nx)）。"""
    u = -Z
    wz = smooth01(P["g_zin"], P["g_zfull"], u) * (1.0 - smooth01(P["g_zw0"], P["g_zw1"], u))
    ft = float(np.clip((t - TT_[0]) / (TT_[1] - TT_[0]), 0.0, len(TT_) - 1.0001)); it = int(np.floor(ft)); at = ft - it
    fz = np.clip((Z - ZC_[0]) / (ZC_[1] - ZC_[0]), 0.0, len(ZC_) - 1.0001); iz = np.floor(fz).astype(int); az = fz - iz
    xa = XT_[it, iz] * (1 - az) + XT_[it, iz + 1] * az
    xb = XT_[it + 1, iz] * (1 - az) + XT_[it + 1, iz + 1] * az
    xc = xa * (1 - at) + xb * at + P["g_dx"]
    wx = np.exp(-((X[None, :] - xc[:, None]) / P["g_sx"]) ** 2)
    w = (wt_of(t) * wz[:, None] * wx)[:, None, :]
    if Y is not None:
        w = w * smooth01(P.get("g_y0", -999.0), P.get("g_y1", -998.0), Y)[None, :, None]
    return w


def _interp_axis(arr, axis, pos_src, pos_dst):
    fx = np.clip((pos_dst - pos_src[0]) / (pos_src[1] - pos_src[0]), 0, len(pos_src) - 1.0001)
    i0 = np.floor(fx).astype(int); w = (fx - i0).astype(np.float32)
    a0 = np.take(arr, i0, axis=axis); a1 = np.take(arr, i0 + 1, axis=axis)
    sh = [1, 1, 1]; sh[axis] = -1
    return a0 * (1 - w.reshape(sh)) + a1 * w.reshape(sh)


VEL_INFO = []


def vel_center(xs_, ys_, zs_):
    """vel の場（面の標本）を surface の標本の位置へ線形に置き直す。戻り：[vx, vy, vz]（各 (nz, ny, nx)）。"""
    gv = vnode.geometry()
    vols = [p for p in gv.prims() if p.type() in (hou.primType.Volume, hou.primType.VDB)]
    out = []
    for p in vols[:3]:
        rx, ry, rz = p.resolution()
        q0 = p.indexToPos((0, 0, 0)); q1 = p.indexToPos((1, 1, 1))
        arr = np.frombuffer(p.allVoxelsAsString(), dtype=np.float32).reshape(rz, ry, rx)
        px = q0[0] + (q1[0] - q0[0]) * np.arange(rx); py = q0[1] + (q1[1] - q0[1]) * np.arange(ry); pz = q0[2] + (q1[2] - q0[2]) * np.arange(rz)
        arr = _interp_axis(arr, 2, px, xs_); arr = _interp_axis(arr, 1, py, ys_); arr = _interp_axis(arr, 0, pz, zs_)
        out.append(arr)
        if len(VEL_INFO) < 3:
            VEL_INFO.append({"name": p.attribValue("name") if gv.findPrimAttrib("name") else "", "res": [rx, ry, rz], "p0": list(q0)})
    if len(out) != 3:
        raise RuntimeError("vel field has %d volumes" % len(out))
    return out
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
    # ---- 波のエネルギーと誘導の仕事（P2g）
    try:
        tt = (f - 1) / fps
        in_win = GA > 0 and (P["g_t0"] - 1.5 / fps <= tt <= P["g_t1"] + 1.5 / fps)
        if in_win or (f % 12 == 0) or f == f0:
            vcomp = vel_center(xs, y_c, zs)
            fluid = a < 0
            sp2 = vcomp[0] ** 2 + vcomp[1] ** 2 + vcomp[2] ** 2
            KE = 0.5 * RHO * float(sp2[fluid].sum()) * VOX ** 3
            if ETA_REF[0] is None and tt >= 2.0:
                mm = (FX >= 600) & (FX <= 700)
                ETA_REF[0] = float(np.nanmedian(eta[:, mm]))
            er = ETA_REF[0] if ETA_REF[0] is not None else float(np.nanmedian(eta[:, (FX >= 600) & (FX <= 700)]))
            PE = 0.5 * RHO * GRAV * float(np.nansum((eta - er) ** 2)) * VOX ** 2
            zn = FZ < -10.0
            PEn = 0.5 * RHO * GRAV * float(np.nansum((eta[zn] - er) ** 2)) * VOX ** 2
            KEn = 0.5 * RHO * float(sp2[(zs < -10.0)[:, None, None] & fluid].sum()) * VOX ** 3
            rec_e = {"f": f, "t": tt, "KE": KE, "PE": PE, "E": KE + PE, "E_near_z<-10": KEn + PEn, "eta_ref": er}
            if in_win:
                tm = tt - 0.5 / fps
                Wfld = guide_weight(tm, xs, zs, y_c)
                spd = np.sqrt(sp2)
                amag = GA * GRAV * Wfld * np.minimum(spd / P["g_vref"], 1.0)
                pw = -(GA * GRAV) * Wfld * sp2 / np.maximum(spd, P["g_vref"])
                Pw = RHO * VOX ** 3 * float(pw[fluid].sum())
                W_ACC[0] += Pw / fps
                Wb = np.broadcast_to(Wfld, a.shape)
                gm = fluid & (Wb > 0.05)
                rec_e.update({"P_W": Pw, "W_cum_J": W_ACC[0], "a_peak_g": float(amag[fluid].max() / GRAV) if fluid.any() else 0.0,
                              "a_mean_g_W>0.05": float(amag[gm].mean() / GRAV) if gm.any() else 0.0,
                              "vol_W>0.05_m3": float(gm.sum() * VOX ** 3), "vol_W>0.5_m3": float((fluid & (Wb > 0.5)).sum() * VOX ** 3),
                              "W_eff_vol_m3": float(Wb[fluid].sum() * VOX ** 3), "Wt": float(wt_of(tm))})
            ENERGY.append(rec_e)
            if f % 24 == 0 or f == f0 or (in_win and f % 6 == 0):
                print("  f=%d E=%.3e J (KE %.3e PE %.3e) near=%.3e W_cum=%.3e J a_peak=%s g" % (f, KE + PE, KE, PE, rec_e["E_near_z<-10"], W_ACC[0], rec_e.get("a_peak_g")))
                sys.stdout.flush()
    except Exception as e:
        info.setdefault("energy_errors", []).append("f%d %s" % (f, str(e)[:300]))
        print("energy error", f, str(e)[:300]); sys.stdout.flush()
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
        np.savez_compressed(os.path.join(OUT, "hf.npz"), eta=np.array(hfs), seg=np.array(segs), frames=np.array(frames),
                            t=np.array(tsim), grid=json.dumps(grid_info), wall=np.array(wall), npts=np.array(npts), lvl=np.array(lvls))
        np.save(os.path.join(OUT, "crest.npy"), np.array(crest, dtype=np.float64))
    if time.time() - t_start > wall_limit:
        stopped = "wall_limit at frame %d" % f
        break
    if f - f0 >= 6 and lvl - lvl0 < -1.0:
        stopped = "free_fall at frame %d (mean level %.2f m, start %.2f m)" % (f, lvl, lvl0)
        break

np.savez_compressed(os.path.join(OUT, "hf.npz"), eta=np.array(hfs), seg=np.array(segs), frames=np.array(frames),
                    t=np.array(tsim), grid=json.dumps(grid_info), wall=np.array(wall), npts=np.array(npts), lvl=np.array(lvls))
np.save(os.path.join(OUT, "crest.npy"), np.array(crest, dtype=np.float64))
wall_total = time.time() - t_start
ck = sorted(os.listdir(ckdir)) if os.path.isdir(ckdir) else []
ck_bytes = sum(os.path.getsize(os.path.join(ckdir, x)) for x in ck)
rec = {
    "stage": "P2g", "run_id": rid, "date": time.strftime("%Y-%m-%d %H:%M:%S"),
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
Eon = [q for q in ENERGY if q["t"] <= P["g_t0"] + 1e-6]
rec["guide"] = {"g_amp": GA, "E_at_g_t0_J": (Eon[-1]["E"] if Eon else None), "E_near_at_g_t0_J": (Eon[-1]["E_near_z<-10"] if Eon else None),
                "W_cum_J": W_ACC[0], "W_pct_of_E": (100.0 * abs(W_ACC[0]) / Eon[-1]["E"]) if (Eon and GA > 0) else 0.0,
                "a_peak_g": max([q.get("a_peak_g", 0.0) for q in ENERGY] + [0.0]), "vel_info": VEL_INFO}
json.dump({"energy": ENERGY, "guide": rec["guide"]}, open(os.path.join(OUT, "energy.json"), "w"), indent=1, default=float)
json.dump(rec, open(os.path.join(OUT, "run.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
with open(os.path.join(ROOT, "runs.jsonl"), "a", encoding="utf8") as fh:
    fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
print("DONE", json.dumps({k: rec[k] for k in ("run_id", "f_end_done", "wall_total_s", "particles_max", "rss_peak_gb", "stopped")}))
