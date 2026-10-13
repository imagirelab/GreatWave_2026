# -*- coding: utf-8 -*-
"""FLIP44：礁の断面の水槽の計算を 1 回（1 起動）走らせて、記録を残す（hython で実行）。
FLIP42 の g_run.py（Tools/GWWaveGen/flip42、変えていない）を写して直した。FLIP42 と同じ記録：
  一番上の水面の高さ（毎コマ、全長）、板の真ん中の断面の水面の場、各コマの小刻みの数、1 コマの秒、粒子の数、水面の見張り。
足した所（計画 plan_ja.md §2・§3.3 (d)・§4.1・§6）：
  - 入口の表（cfg の inlet）を CTRL の inlet_tab に入れる。
  - 起動の始めに、自分の優先度を「通常より下」にし、Windows の実行速度の抑え（電力の抑え）を使わないように頼む（FLIP42 の g_unthrottle と同じ設定）。
  - 起動の始めに G: の空きを見て、25 GB より少なければ走らせずに止める（計画 N8）。
  - 風の VEX が呼ばれた回数 wind_calls を毎コマ記録する（S4b）。
  - 選んだコマで、場の箱の端を丸めずに読む（fieldbox_frames。S2・S2b・S4b）、海底の衝突の場の 0 の高さを読む（bedcheck）、
    粒子の縦の速さの平均と速さの最大を読む（pstats_frames）。
  - 風の計算：断面の surfacepressure の場を記録する（psec）。断面の水面の場から、閉じた空気の穴（格子 1 個以上）ができたコマ
    （着水の読みの「空気を囲む」の形）を見つけ、その after_s 秒後で止める（stop_touchdown。計画 §4.1「風の計算の着水の 0.5 s 後で止める」）。
  - 2026-10-12（2 回目の確かめの後。record_ja.md §3.2）：
    着水の読みは g44_online.TouchdownWatch。空気の穴の面積を解析と同じ等高線の面積で見る。唇の先が静かな水面以下になった時も読み、
    空気の穴が見えなければ tip_wait_s 後で止める。同じ計算の前の起動で見つけた着水は run_c*.json から引き継ぐ（G2 の起動の区切り）。
    起動の前に風の設定を確かめる（g44_online.wind_guard。G6）：mode 2（道具がない間）、本番の置き場所の mode 3、風の計算の設定で wind_on 0、
    form と mode の違いは、場面を読まずに理由を記録へ書いて終わる（stopped "refused: ..."）。
使い方: hython g44_run.py <cfg.json のパス または JSON の文字>
出力: Unity/Build/FLIP44/<out_root>/<run_id>/（out_root は runs か smoke）
  hf_cXXXX.npz  一番上の水面の高さ eta（コマ, z の節, x の節、float32）、x、z、t、frames、wall、npts、lvl、ss_n、ss_dt、wind_calls
  sec_cXXXX_bYYYY.npz  断面の水面の場 sdf（コマ, y, x、float16、±8 m で切る）
  psec_cXXXX_bYYYY.npz 断面の surfacepressure（p）と、圧力を書いた時の水面の場の写し windsurf（ws）（float32。風の計算だけ）
  run_cXXXX.json 条件と記録（起動ごと）。run.json（最初の起動）。<out_root>/runs.jsonl にも 1 行足す。
"""
import hou, sys, os, json, time, hashlib, ctypes, shutil, glob
from ctypes import wintypes
import numpy as np

HIP = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP44/g44_tank.hiplc"
BASE = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP44"
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip44")
import g44_online as GO        # numpy だけ（着水の読み・風の設定の守り）
a1 = sys.argv[1]
args = json.load(open(a1, encoding="utf8")) if os.path.exists(a1) else json.loads(a1)
rid = args["run_id"]
ROOT = os.path.join(BASE, args.get("out_root", "runs")).replace("\\", "/")
OUT = os.path.join(ROOT, rid).replace("\\", "/")
os.makedirs(OUT, exist_ok=True)
f0, f1 = int(args["f_start"]), int(args["f_end"])


# ---------------------------------------------------------------- 優先度と電力の抑え（自分の処理だけ）
def unthrottle_self():
    k = ctypes.WinDLL("kernel32", use_last_error=True)

    class PPTS(ctypes.Structure):
        _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.GetPriorityClass.argtypes = [wintypes.HANDLE]
    h = k.GetCurrentProcess()
    s = PPTS(1, 0x1, 0x0)      # PROCESS_POWER_THROTTLING_EXECUTION_SPEED を「使わない」
    r1 = bool(k.SetProcessInformation(h, 4, ctypes.byref(s), ctypes.sizeof(s)))
    r2 = bool(k.SetPriorityClass(h, 0x4000))   # BELOW_NORMAL_PRIORITY_CLASS
    return dict(pid=os.getpid(), power_throttling_off=r1, below_normal=r2, priority_class=hex(k.GetPriorityClass(h)),
                time=time.strftime("%Y-%m-%d %H:%M:%S"))


PRIO = unthrottle_self()
print("priority", PRIO); sys.stdout.flush()


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


def write_rec(rec):
    json.dump(rec, open(os.path.join(OUT, "run_c%04d.json" % f0), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
    if f0 == int(args.get("f_first", 1)):
        json.dump(rec, open(os.path.join(OUT, "run.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
    with open(os.path.join(ROOT, "runs.jsonl"), "a", encoding="utf8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def refuse(why, free=None):
    """風の設定の守り（G6）：走らせずに理由を記録へ書いて終わる。"""
    rec = dict(stage="FLIP44", run_id=rid, date=time.strftime("%Y-%m-%d %H:%M:%S"), f_start=f0, f_end_req=f1, f_end_done=None,
               stopped="refused: " + why, priority=PRIO, free_gb_start=free, parms=args.get("parms"), case=args.get("case"))
    write_rec(rec)
    print("DONE", json.dumps({"run_id": rid, "stopped": rec["stopped"]}, ensure_ascii=False))
    sys.exit(0)


_g = GO.wind_guard(args)
if _g:
    refuse(_g)

# ---------------------------------------------------------------- 置き場所の見張り（計画 N8）
free_gb = shutil.disk_usage("G:/").free / 2**30
disk_stop = float(args.get("disk_stop_free_gb", 25.0))
if free_gb < disk_stop:
    rec = dict(stage="FLIP44", run_id=rid, date=time.strftime("%Y-%m-%d %H:%M:%S"), f_start=f0, f_end_req=f1, f_end_done=None,
               stopped="disk: G: free %.1f GB < %.1f GB（計画 N8。利用者に伺う）" % (free_gb, disk_stop), priority=PRIO, free_gb_start=free_gb)
    write_rec(rec)
    print("DONE", json.dumps({"run_id": rid, "stopped": rec["stopped"]}, ensure_ascii=False))
    sys.exit(0)

t_launch = time.time()
HIP_SHA = hashlib.sha256(open(HIP, "rb").read()).hexdigest()
hou.hipFile.load(HIP, suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/G44_SETUP/CTRL")
for k, v in args.get("parms", {}).items():
    ctrl.parm(k).set(v)
inl = args.get("inlet")
if inl:
    sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip44")
    import g44_tanklib as L
    ctrl.parm("inlet_tab").set(L.inlet_tab_string(inl["freqs_Hz"], inl["amps_m"], inl["phases_rad"], inl["k"]))
fs = hou.node("/obj/G44_SIM/flipsolver")
sv = args.get("solver", {})
fs.parm("veltransfer").set(sv.get("veltransfer", "apic"))
fs.parm("donarrowband").set(int(sv.get("donarrowband", 0)))
for _k, _v in sv.items():
    if _k not in ("veltransfer", "donarrowband"):
        fs.parm(_k).set(_v)
ckdir = os.path.join(OUT, "ckpt").replace("\\", "/")
os.makedirs(ckdir, exist_ok=True)
ctrl.parm("ckpt").set(ckdir)
ctrl.parm("ckpt_on").set(int(args.get("ckpt_on", 1)))
ctrl.parm("ckpt_every").set(int(args.get("ckpt_every", 240)))
hou.setSimulationEnabled(True)
fps = hou.fps()
dop = hou.node("/obj/G44_SIM")
fi = hou.node("/obj/G44_READ/surface_field")
fpr = hou.node("/obj/G44_READ/pressure_field")
wall_limit = float(args.get("wall_limit_s", 1740))
lvl_guard = float(args.get("level_guard_m", 1.0))
P = {p.name(): p.eval() for p in ctrl.parms()}
_g = GO.wind_guard(args, parms=P)          # 場面に入れた後の値（設定に書いていない値は場面の既定）で、もう一度
if _g:
    refuse(_g + "（場面の CTRL の値）", round(free_gb, 1))
tab = hou.node("/obj/G44_SETUP/OUT_INLET").geometry()
inlet_check = dict(ncomp=int(tab.attribValue("ncomp")), sum_a=float(tab.attribValue("sum_a")))
Lz = float(P["Lz"]); Lx = float(P["Lx"])
VOX = float(P["dp"]) * float(P["gridscale"])
FX = np.arange(0.0, Lx + 1e-6, VOX)
FZ = np.arange(-0.5 * Lz, 0.5 * Lz + 1e-6, VOX)
SEC = args.get("sec") or {}
SEC_BLOCK = 120
wind_on = float(P["wind_on"]) > 0.5
PSEC = bool(args.get("record_psec", wind_on))
STOP_TD = args.get("stop_touchdown")
FB_FRAMES = set(int(v) for v in args.get("fieldbox_frames", []))
PS_FRAMES = args.get("pstats_frames", [])
PS_ALL = PS_FRAMES == "all"
PS_FRAMES = set() if PS_ALL else set(int(v) for v in PS_FRAMES)
BEDCHK = args.get("bedcheck")


def bedy_np(x):
    h0 = float(P["h0"])
    if float(P["reef_on"]) < 0.5:
        return np.full(np.shape(x), -h0)
    xr = np.asarray(x) - float(P["x_p"])
    n = float(P["rf_slope_n"]); ht = float(P["rf_h_top"])
    df = h0 - (xr - float(P["rf_foot"])) / n
    db = ht + (xr - float(P["rf_top_end"])) / n
    return -np.minimum(h0, np.maximum(ht, np.maximum(df, db)))


# 場を読む節（場の箱の端・海底の 0 の高さ。必要な時だけ作る。場面は保存しない）
FIELD_NAMES = ["surface", "pressure", "vel", "collision", "collisionweights", "massdensity"] + (["surfacepressure"] if wind_on else [])
FI = {}
if FB_FRAMES or BEDCHK:
    rdn = hou.node("/obj").createNode("geo", "G44_FIELDS")
    for c in rdn.children():
        c.destroy()
    for nm in FIELD_NAMES:
        q = rdn.createNode("dopimportfield::2.0", "f_" + nm)
        q.parm("doppath").set("/obj/G44_SIM")
        q.parm("fields").set(1)
        q.parm("objname1").set("water")
        q.parm("fieldname1").set(nm)
        FI[nm] = q


def fieldbox(f):
    out = {}
    for nm, q in FI.items():
        try:
            g = q.geometry()
        except Exception as e:
            out[nm] = {"err": str(e)[:120]}; continue
        if g is None:
            out[nm] = None; continue
        vols = [p for p in g.prims() if p.type() in (hou.primType.Volume, hou.primType.VDB)]
        out[nm] = []
        for v in vols[:3]:
            r = v.resolution(); p0 = v.indexToPos((0, 0, 0)); p1 = v.indexToPos((1, 1, 1)); bb = v.boundingBox()
            out[nm].append(dict(res=list(r), p0=[repr(c) for c in p0], d=[repr(p1[j] - p0[j]) for j in range(3)],
                                bmin=[repr(c) for c in bb.minvec()], bmax=[repr(c) for c in bb.maxvec()]))
    return out


def bed_zero(f):
    """衝突の場（板の真ん中 z = 0）の 0 の高さを、指定の x（造波板から）で、y を下から上へたどって 2 分で探す。"""
    g = FI["collision"].geometry()
    vols = [p for p in g.prims() if p.type() in (hou.primType.Volume, hou.primType.VDB)]
    v = vols[0]
    res = []
    for xr in BEDCHK.get("x_rel", []):
        x = float(P["x_p"]) + float(xr)
        ys = np.arange(-float(P["h0"]) - 1.5, 0.0, 0.25 * VOX)
        s = np.array([v.sample(hou.Vector3(x, float(y), 0.0)) for y in ys])
        sg = np.sign(s)
        idx = np.where(sg[:-1] * sg[1:] < 0)[0]
        if len(idx) == 0:
            res.append(dict(x_rel=xr, zero_y=None, plan_y=float(bedy_np(x)), s_first=float(s[0]), s_last=float(s[-1]))); continue
        i = int(idx[-1]); lo, hi = float(ys[i]), float(ys[i + 1])
        slo = v.sample(hou.Vector3(x, lo, 0.0))
        for _ in range(40):
            mid = 0.5 * (lo + hi); sm = v.sample(hou.Vector3(x, mid, 0.0))
            if (sm < 0) == (slo < 0):
                lo, slo = mid, sm
            else:
                hi = mid
        zy = 0.5 * (lo + hi)
        res.append(dict(x_rel=xr, zero_y=zy, plan_y=float(bedy_np(x)), diff=zy - float(bedy_np(x)), half_cell=0.5 * VOX,
                        ok=bool(abs(zy - float(bedy_np(x))) <= 0.5 * VOX), sign_below=float(s[0])))
    return res


def pstats(wg):
    Pp = np.frombuffer(wg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3)
    V = np.frombuffer(wg.pointFloatAttribValuesAsString("v"), dtype=np.float32).reshape(-1, 3)
    mid = (Pp[:, 0] > 0.2 * Lx) & (Pp[:, 0] < 0.8 * Lx)
    sp = np.sqrt((V.astype(np.float64) ** 2).sum(1)); im = int(np.argmax(sp))
    return dict(n=int(len(Pp)), vy_mean_mid=float(V[mid, 1].mean()), vy_min_mid=float(V[mid, 1].min()), vy_max_mid=float(V[mid, 1].max()),
                speed_max=float(sp[im]), speed_max_at=[float(c) for c in Pp[im]], n_speed_gt_0p1=int((sp > 0.1).sum()),
                ymax_mid=float(Pp[mid, 1].max()))


# 着水の読み（numpy だけ。x44_fix2_tests.py td で、FLIP42 R2・R3・R4d と煙の試し S8 の解析の着水と同じコマになることを確かめた）
WATCH = GO.TouchdownWatch(STOP_TD, VOX, P, fps) if STOP_TD else None
if WATCH is not None:
    # 同じ計算の前の起動（この起動より前から始まった起動）で見つけた着水と唇の先を引き継ぐ。風の強さと入口が同じ記録だけ
    for _p in sorted(glob.glob(os.path.join(OUT, "run_c*.json"))):
        try:
            _r = json.load(open(_p, encoding="utf8"))
        except Exception:
            continue
        if not (int(args.get("f_first", f0)) <= int(_r.get("f_start") or 0) < f0):
            continue
        if abs(float((_r.get("parms") or {}).get("wind_q", -1.0)) - float(P["wind_q"])) > 1e-6 or _r.get("inlet_name") != (inl or {}).get("name"):
            continue
        _inf = _r.get("info") or {}
        _td = _inf.get("touchdown_online"); _tp = _inf.get("tip_online")
        WATCH.restore(_td if _td and int(_td["frame"]) < f0 else None, _tp if _tp and int(_tp["frame"]) < f0 else None)
RESTORED = dict(td=(WATCH.td or {}).get("frame"), tip=(WATCH.tip or {}).get("frame")) if (WATCH is not None and (WATCH.td or WATCH.tip)) else None


frames, wall, npts, tsim, lvls, hfs, ssn, ssdt, wcal = [], [], [], [], [], [], [], [], []
sec_buf, sec_fr, sec_meta = [], [], None
psec_buf, psec_fr, psec_meta = [], [], None
wsec_buf = []
info = {"inlet_check": inlet_check}
if RESTORED:
    info["online_restored"] = RESTORED
solver_parms = {n: fs.parm(n).eval() for n in ("minimumsubsteps", "substeps", "cflcond", "partcflcond", "donarrowband", "narrowbandwidth",
                                              "veltransfer", "usepreconditioner", "usemgpreconditioner", "dosurfacetension", "surfacetension")}


def flush_sec():
    global sec_buf, sec_fr
    if not sec_buf:
        return
    np.savez_compressed(os.path.join(OUT, "sec_c%04d_b%04d.npz" % (f0, sec_fr[0])), sdf=np.array(sec_buf, np.float16),
                        frames=np.array(sec_fr), t=(np.array(sec_fr) - 1) / fps, meta=json.dumps(sec_meta))
    sec_buf, sec_fr = [], []


def flush_psec():
    global psec_buf, psec_fr, wsec_buf
    if not psec_buf:
        return
    np.savez_compressed(os.path.join(OUT, "psec_c%04d_b%04d.npz" % (f0, psec_fr[0])), p=np.array(psec_buf, np.float32),
                        ws=np.array(wsec_buf, np.float32), frames=np.array(psec_fr), t=(np.array(psec_fr) - 1) / fps, meta=json.dumps(psec_meta))
    psec_buf, psec_fr, wsec_buf = [], [], []


def save():
    np.savez_compressed(os.path.join(OUT, "hf_c%04d.npz" % f0), eta=np.array(hfs, np.float32), x=FX, z=FZ,
                        frames=np.array(frames), t=np.array(tsim), wall=np.array(wall), npts=np.array(npts), lvl=np.array(lvls),
                        ss_n=np.array(ssn), ss_dt=np.array(ssdt), wind_calls=np.array(wcal), grid=json.dumps(grid_info))


t_start = time.time()
stopped = None
lvl0 = None
grid_info = None
for f in range(f0, f1 + 1):
    t0 = time.time()
    hou.setFrame(f)
    g = fi.geometry()
    dt = time.time() - t0
    if g is None:
        info["error"] = "no surface geometry at frame %d; errors=%s" % (f, [str(e)[:300] for e in fi.errors()])
        stopped = "error"
        break
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
        grid_info = {"res": [nx, ny, nz], "x0": float(xs[0]), "dx": float(p111[0] - p000[0]), "y0": float(y_c[0]), "z0": float(zs[0]),
                     "dy": float(dy), "dz": float(p111[2] - p000[2])}
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
    tnow = (f - 1) / fps
    iz0 = int(np.argmin(np.abs(zs)))
    # 断面の水面の場（板の真ん中、z = 0 に最も近い節）
    if SEC and tnow >= float(SEC["t0"]) - 1e-9:
        ix0 = int(np.searchsorted(xs, float(SEC["x0"])))
        ix1 = int(np.searchsorted(xs, float(SEC["x1"])))
        if sec_meta is None or sec_meta["res"] != [nx, ny, nz]:
            flush_sec()
            sec_meta = {"res": [nx, ny, nz], "iz": iz0, "z": float(zs[iz0]), "x0": float(xs[ix0]), "dx": float(xs[1] - xs[0]),
                        "nx": ix1 - ix0, "y0": float(y_c[0]), "dy": float(dy), "ny": int(ny), "clip_m": 8.0}
        sl = a[iz0, :, ix0:ix1]
        sec_buf.append(np.clip(sl, -8.0, 8.0).astype(np.float16))
        sec_fr.append(f)
        if len(sec_buf) >= SEC_BLOCK:
            flush_sec()
        # 風の計算：断面の surfacepressure
        if PSEC and wind_on:
            gp = fpr.geometry()
            pv = [p for p in gp.prims() if p.type() in (hou.primType.Volume, hou.primType.VDB)] if gp is not None else []
            if pv:
                v2 = pv[0]
                r2 = v2.resolution(); q0 = v2.indexToPos((0, 0, 0)); q1 = v2.indexToPos((1, 1, 1))
                pa = np.frombuffer(v2.allVoxelsAsString(), dtype=np.float32).reshape(r2[2], r2[1], r2[0])
                qx = q0[0] + (q1[0] - q0[0]) * np.arange(r2[0]); qz = q0[2] + (q1[2] - q0[2]) * np.arange(r2[2])
                jz = int(np.argmin(np.abs(qz)))
                jx0 = int(np.searchsorted(qx, float(SEC["x0"]))); jx1 = int(np.searchsorted(qx, float(SEC["x1"])))
                if psec_meta is None:
                    psec_meta = {"res": list(r2), "z": float(qz[jz]), "x0": float(qx[jx0]), "dx": float(q1[0] - q0[0]), "nx": jx1 - jx0,
                                 "y0": float(q0[1]), "dy": float(q1[1] - q0[1]), "ny": int(r2[1]), "p0": [repr(c) for c in q0]}
                psec_buf.append(pa[jz, :, jx0:jx1].copy()); psec_fr.append(f)
                gw = hou.node("/obj/G44_READ/windsurf_field").geometry()
                wv = [q for q in gw.prims() if q.type() in (hou.primType.Volume, hou.primType.VDB)] if gw is not None else []
                if wv and list(wv[0].resolution()) == list(r2):
                    wa = np.frombuffer(wv[0].allVoxelsAsString(), dtype=np.float32).reshape(r2[2], r2[1], r2[0])
                    wsec_buf.append(wa[jz, :, jx0:jx1].copy())
                else:
                    wsec_buf.append(np.full((r2[1], jx1 - jx0), np.nan, np.float32))
                if len(psec_buf) >= SEC_BLOCK:
                    flush_psec()
        # 着水（閉じた空気の穴）で止める
        if WATCH is not None:
            WATCH.step(f, tnow, sl, xs[ix0:ix1], y_c)
            if WATCH.td is not None:
                info["touchdown_online"] = WATCH.td
            if WATCH.tip is not None:
                info["tip_online"] = WATCH.tip
    n = -1; sn = -1; sd = -1.0; wcn = -1
    try:
        wg = dop.simulation().findObject("water").geometry()
        if f % 24 == 0 or f == f0 or f == f1 or PS_ALL or f in PS_FRAMES:
            n = wg.intrinsicValue("pointcount")
        if wg.findGlobalAttrib("ss_n") is not None:
            sn = int(wg.attribValue("ss_n")); sd = float(wg.attribValue("ss_dt"))
        if wg.findGlobalAttrib("wind_calls") is not None:
            wcn = int(wg.attribValue("wind_calls"))
        if PS_ALL or f in PS_FRAMES:
            info.setdefault("pstats", {})[str(f)] = pstats(wg)
    except Exception as e:
        if len(info.get("geo_errors", [])) < 5:
            info.setdefault("geo_errors", []).append(str(e)[:200])
    if f in FB_FRAMES:
        info.setdefault("fieldbox", {})[str(f)] = fieldbox(f)
    if BEDCHK and f == int(BEDCHK.get("frame", 2)):
        try:
            info["bedcheck"] = bed_zero(f)
        except Exception as e:
            info["bedcheck_error"] = str(e)[:300]
    r, pk = rss_gb()
    mid = E2[:, (FX > 0.2 * Lx) & (FX < 0.6 * Lx)]
    lvl = float(np.nanmean(mid)) if np.isfinite(mid).any() else -999.0
    frames.append(f); wall.append(dt); npts.append(n); tsim.append(tnow); lvls.append(lvl); ssn.append(sn); ssdt.append(sd); wcal.append(wcn)
    if lvl0 is None:
        lvl0 = lvl
    if f % 48 == 0 or f == f0:
        print("f=%d t=%.2f sim=%.2fs pts=%d sub=%d wc=%d rss=%.2fGB lvl=%.3f eta_min=%.2f eta_max=%.2f" % (
            f, tnow, dt, n, sn, wcn, r, lvl, np.nanmin(E2), np.nanmax(E2)))
        sys.stdout.flush()
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
    _s = WATCH.should_stop(tnow) if WATCH is not None else None
    if _s:
        stopped = _s
        break

save()
flush_sec()
flush_psec()
wall_total = time.time() - t_start
ck = sorted(os.listdir(ckdir)) if os.path.isdir(ckdir) else []
ck_bytes = sum(os.path.getsize(os.path.join(ckdir, x)) for x in ck)
nn = [v for v in npts if v >= 0]
ss_ok = [v for v in ssn if v >= 0]
wc_ok = [(fr_, s_, w_) for fr_, s_, w_ in zip(frames, ssn, wcal) if w_ >= 0]
rec = {
    "stage": "FLIP44", "run_id": rid, "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    "houdini": hou.applicationVersionString(), "hip": HIP, "hip_sha256": HIP_SHA, "priority": PRIO, "free_gb_start": round(free_gb, 1),
    "parms": {k: P[k] for k in P if k != "inlet_tab"}, "inlet_name": (inl or {}).get("name"), "solver": sv, "solver_parms": solver_parms,
    "case": args.get("case", {}), "sec": SEC,
    "f_start": f0, "f_end_req": f1, "f_end_done": frames[-1] if frames else None, "fps": fps,
    "ckpt_dir": ckdir, "ckpt_files": len(ck), "ckpt_gb": round(ck_bytes / 2**30, 3),
    "particles_first": nn[0] if nn else None, "particles_max": max(nn) if nn else None,
    "wall_total_s": round(wall_total, 1), "wall_launch_s": round(time.time() - t_launch, 1),
    "wall_per_frame_median_s": round(float(np.median(wall[1:])) if len(wall) > 1 else 0, 3),
    "substeps_min_max": [min(ss_ok), max(ss_ok)] if ss_ok else None,
    "substeps_hist": {str(v): int(ss_ok.count(v)) for v in sorted(set(ss_ok))},
    "wind_calls_equal_substeps": (all(s_ == w_ for _, s_, w_ in wc_ok) if wc_ok else None),
    "wind_calls_frames": len(wc_ok),
    "rss_peak_gb": round(rss_gb()[1], 2),
    "level_start_m": lvl0, "level_min_m": float(np.min(lvls)) if lvls else None, "level_end_m": lvls[-1] if lvls else None,
    "stopped": stopped, "info": info, "note": args.get("note", ""), "grid": grid_info,
}
write_rec(rec)
print("DONE", json.dumps({k: rec[k] for k in ("run_id", "f_end_done", "wall_total_s", "particles_max", "rss_peak_gb", "substeps_min_max", "stopped")}))
