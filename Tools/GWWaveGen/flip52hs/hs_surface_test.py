# -*- coding: utf-8 -*-
"""FLIP52B hires surfacing test (hython; one checkpoint frame, nothing simulated). 2026-10-18 written new (Claude).

Why: the user (10/18 16:35) sees a clear grid on the water surface of the DFG-2B-E hero video and asks whether it is a precision
problem; the big shape and the motion are to stay as they are. This test re-surfaces the SAME recorded particles (one checkpoint of the
judged source run) with the hero's surfacing network and with finer / filtered settings, on a cropped region, and measures what each
setting changes. The particles (the physics) are never changed: no solver step is run.

What it does
  1. copies the checkpoint runs/DFGB2E_D19B_xf272p25_dp0p5/ckpt/v.FFFF.sim into a NEW folder hires/test_fFFFF/_ckpt (never reads or writes
     the run's own ckpt folder through Houdini) and loads it by the DOP explicit cache at frame FFFF (the g52b_chain resume mechanism);
     an external monitor (hs_launch_guarded.ps1) kills this process if any other .sim appears there (= Houdini started to simulate).
  2. the FLIP52B scene G52_SURF network unchanged (layer_and_mirror -> particlefluidsurface -> clip -> divide -> crop -> normals) with the
     run cfg's CTRL parms; one added node before layer_and_mirror drops particles outside the crop + MARGIN (per-point, so identical inside);
     the existing triangle crop uses CTRL crop_x0 / crop_x1 / crop_z1 = the test crop.
  3. variants = CTRL surf_vox_scale and particlefluidsurface parameters; each is written as GW45SRF1 (the g52b_run.write_surface packer).
  4. measures: cook time, process memory, counts, bytes; distances to the baseline both ways (xyzdist), crest height, centre-section
     (symmetry-plane seam) difference, mesh facet measures (edge length, dihedral angle, axis-aligned edge share, vertex-normal noise) and a
     0.1 m top-surface raster (band-pass height RMS, pixel normal vs the 1.5 m smoothed surface normal).
  5. baseline check: the baseline mesh against the hero's own s_FFFFF.gw45s inside the core (should agree within the GW45SRF1 quantization).
usage: hython hs_surface_test.py [frame=2112] [variants=all|name,name] [tag]   (a tag names a second batch: its json / raster / log get _<tag>;
       a variant file that already exists is not rewritten: the new mesh is compared byte for byte with it instead)
output (new files only): Unity/Build/FLIP52B/hires/test_fFFFF/<variant>/s_FFFFF.gw45s, hs_surface_test_fFFFF.json, raster_fFFFF.npz,
        LOADED.txt / DONE.txt markers for the monitor
Tags in the json: [measured] from the meshes / process, [computed] derived, [chosen] test choices.
"""
import hou, sys, os, json, time, struct, hashlib, shutil, ctypes, glob
from ctypes import wintypes
import numpy as np

sys.dont_write_bytecode = True
T_START = time.time()
REPO = "G:/Unity/GreatWave_2026_Fresh"
B52B = REPO + "/Unity/Build/FLIP52B"
HIP = REPO + "/Houdini/FLIP52B/g52b_tank.hiplc"
SRC_RUN = B52B + "/runs/DFGB2E_D19B_xf272p25_dp0p5"
HERO_RUN = B52B + "/hero/runs/DFGB2Er_D19B_xf272p25_dp0p5_c1152_t125_long"
FRAME = int(sys.argv[1]) if len(sys.argv) > 1 else 2112
VSEL = sys.argv[2] if len(sys.argv) > 2 else "all"
TAG = ("_" + sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else ""
OUT = B52B + "/hires/test_f%04d" % FRAME
CKD = OUT + "/_ckpt"
assert (OUT + "/").startswith(B52B + "/hires/")
CROP = dict(x0=200.0, x1=300.0, z1=40.0)    # [chosen] domain coords: x along the tank, z = lateral distance from the symmetry plane
CORE = dict(x0=202.0, x1=298.0, z1=38.0)    # [chosen] statistics 2 m inside the crop edges
MARGIN = 6.0                                # [chosen] particle crop margin (surfacing reach: influence 3 x 0.5 m + filters)
STOP_FREE_GB = 3.0                          # stop line of the free commit (task rule)
RAST = 0.1                                  # [chosen] raster cell (m)

# ---------------------------------------------------------------- variants ([chosen]; keys: vox = CTRL surf_vox_scale, others = particlefluidsurface parms)
VARIANTS = [
    ("b0_base", "hero settings: voxel scale 1.0 (0.5 m voxels), adaptivity 0.005, no filtering", dict()),
    ("a0_adapt0", "as base, adaptivity 0 (no polygon merging)", dict(adaptivity=0.0)),
    ("v050", "voxel scale 0.5 (0.25 m voxels), adaptivity 0.005", dict(vox=0.5)),
    ("v035", "voxel scale 0.35 (0.175 m voxels), adaptivity 0.005", dict(vox=0.35)),
    ("v050_dse", "0.25 m voxels + dilate 2 vox, mean-curvature smooth 2, erode 2 vox", dict(vox=0.5, dodilate=1, dilateoffset=2.0, dosmooth=1,
                                                                                         smoothoperation="meancurvature", smoothiterations=2,
                                                                                         doerode=1, erodeoffset=2.0)),
    ("v050_dseg", "v050_dse + final Gaussian smooth 2 iterations", dict(vox=0.5, dodilate=1, dilateoffset=2.0, dosmooth=1,
                                                                       smoothoperation="meancurvature", smoothiterations=2, doerode=1,
                                                                       erodeoffset=2.0, dofinalsmooth=1, finalsmoothoperation="@gauss",
                                                                       finalsmoothiterations=2)),
    ("v050_inf45", "0.25 m voxels, influence scale 4.5 (base 3.0): wider particle averaging", dict(vox=0.5, influenceradius=4.5)),
    # second batch (added after the first batch: adaptivity 0 gave uniform 0.5 m triangles, Gaussian final smoothing removed the particle lumps)
    ("a0_g100", "0.5 m voxels (hero), adaptivity 0, final Gaussian smooth 2", dict(adaptivity=0.0, dofinalsmooth=1, finalsmoothoperation="@gauss",
                                                                                finalsmoothiterations=2)),
    ("a0_v050_dse", "adaptivity 0, 0.25 m voxels, dilate 2 / mean-curvature 2 / erode 2", dict(vox=0.5, adaptivity=0.0, dodilate=1, dilateoffset=2.0,
                                                                                            dosmooth=1, smoothoperation="meancurvature",
                                                                                            smoothiterations=2, doerode=1, erodeoffset=2.0)),
    ("a0_v050_dseg", "adaptivity 0, 0.25 m voxels, dilate 2 / mean-curvature 2 / erode 2 + final Gaussian 2",
     dict(vox=0.5, adaptivity=0.0, dodilate=1, dilateoffset=2.0, dosmooth=1, smoothoperation="meancurvature", smoothiterations=2, doerode=1,
          erodeoffset=2.0, dofinalsmooth=1, finalsmoothoperation="@gauss", finalsmoothiterations=2)),
]
FIRST_BATCH = ["b0_base", "a0_adapt0", "v050", "v035", "v050_dse", "v050_dseg", "v050_inf45"]
if VSEL == "all":
    VARIANTS = [v for v in VARIANTS if v[0] in FIRST_BATCH]
else:
    want = set(VSEL.split(",")) | {"b0_base"}
    VARIANTS = [v for v in VARIANTS if v[0] in want]

os.makedirs(CKD, exist_ok=True)
LOGF = open(OUT + "/hs_surface_test_f%04d%s_log.txt" % (FRAME, TAG), "a", encoding="utf8")


def log(*a):
    s = time.strftime("%H:%M:%S") + " [%6.1f s] " % (time.time() - T_START) + " ".join(str(x) for x in a)
    print(s); sys.stdout.flush()
    LOGF.write(s + "\n"); LOGF.flush()


# ---------------------------------------------------------------- process / system memory (Windows)
class PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


class MSX(ctypes.Structure):
    _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD), ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


_K32 = ctypes.WinDLL("kernel32", use_last_error=True)
_K32.GetCurrentProcess.restype = wintypes.HANDLE
_GPMI = ctypes.windll.psapi.GetProcessMemoryInfo
_GPMI.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
GB = float(2 ** 30)


def proc_mem():
    c = PMC(); c.cb = ctypes.sizeof(PMC)
    _GPMI(_K32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return dict(private_gb=round(c.PagefileUsage / GB, 3), private_peak_gb=round(c.PeakPagefileUsage / GB, 3),
                ws_gb=round(c.WorkingSetSize / GB, 3), ws_peak_gb=round(c.PeakWorkingSetSize / GB, 3))


def sys_commit():
    m = MSX(); m.dwLength = ctypes.sizeof(MSX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return dict(commit_limit_gb=round(m.ullTotalPageFile / GB, 2), commit_free_gb=round(m.ullAvailPageFile / GB, 2))


def low_priority():
    try:
        _K32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        _K32.GetPriorityClass.argtypes = [wintypes.HANDLE]
        ok = bool(_K32.SetPriorityClass(_K32.GetCurrentProcess(), 0x40))      # IDLE_PRIORITY_CLASS
        return dict(pid=os.getpid(), idle=ok, priority_class=hex(_K32.GetPriorityClass(_K32.GetCurrentProcess())))
    except Exception as e:
        return dict(pid=os.getpid(), error=repr(e)[:200])


REC = dict(tool="Tools/GWWaveGen/flip52hs/hs_surface_test.py", date=time.strftime("%Y-%m-%d %H:%M:%S"), frame=FRAME, out=OUT, tag=TAG,
           purpose="re-surface the SAME recorded particles (no simulation) to see what removes the visible grid; physics unchanged",
           crop=CROP, core=CORE, particle_margin_m=MARGIN, raster_m=RAST, priority=low_priority(), mem=[], variants={}, stopped=None,
           tags="[measured] meshes / process / timings; [computed] derived numbers; [chosen] test settings (crop, variants, metrics)")


def save():
    with open(OUT + "/hs_surface_test_f%04d%s.json" % (FRAME, TAG), "w", encoding="utf8") as fh:
        json.dump(REC, fh, indent=1, ensure_ascii=False, default=str)


def guard(stage):
    sc = sys_commit(); pm = proc_mem()
    REC["mem"].append(dict(stage=stage, t_s=round(time.time() - T_START, 1), **pm, **sc))
    log("MEM", stage, pm, sc)
    if sc["commit_free_gb"] < STOP_FREE_GB:
        REC["stopped"] = "free commit %.2f GB < %.1f GB at %s" % (sc["commit_free_gb"], STOP_FREE_GB, stage)
        save(); log("STOP", REC["stopped"]); LOGF.close(); os._exit(3)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def pct(a, qs):
    a = np.asarray(a, np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return [None] * len(qs)
    return [round(float(v), 4) for v in np.percentile(a, qs)]


# ---------------------------------------------------------------- GW45SRF1 (same packer as flip52b/g52b_run.write_surface)
HEAD_FMT = "<8sIIdiIIffffffff"
HEAD_BYTES = 96


def oct_encode(n):
    n = n / np.maximum(np.abs(n).sum(1, keepdims=True), 1e-12)
    x, y, z = n[:, 0], n[:, 1], n[:, 2]
    neg = z < 0
    xo = np.where(neg, (1 - np.abs(y)) * np.sign(x + 1e-30), x)
    yo = np.where(neg, (1 - np.abs(x)) * np.sign(y + 1e-30), y)
    return np.round((np.clip(np.stack([xo, yo], 1), -1, 1) * 0.5 + 0.5) * 65535).astype(np.uint16)


def oct_decode(q):
    f = q.astype(np.float64) / 65535.0 * 2.0 - 1.0
    x, y = f[:, 0], f[:, 1]
    z = 1.0 - np.abs(x) - np.abs(y)
    neg = z < 0
    xn = np.where(neg, (1 - np.abs(y)) * np.sign(x + 1e-30), x)
    yn = np.where(neg, (1 - np.abs(x)) * np.sign(y + 1e-30), y)
    n = np.stack([xn, yn, z], 1)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def read_gw45s(p):
    b = open(p, "rb").read()
    h = struct.unpack(HEAD_FMT, b[:struct.calcsize(HEAD_FMT)])
    nv, nt = h[5], h[6]
    lo = np.array(h[7:10], np.float64); hi = np.array(h[10:13], np.float64)
    o = HEAD_BYTES
    q = np.frombuffer(b, np.uint16, nv * 3, o).reshape(-1, 3); o += nv * 6
    n = np.frombuffer(b, np.uint16, nv * 2, o).reshape(-1, 2); o += nv * 4
    v = np.frombuffer(b, np.float16, nv * 3, o).reshape(-1, 3); o += nv * 6
    t = np.frombuffer(b, np.uint32, nt * 3, o).reshape(-1, 3).astype(np.int64)
    P = q.astype(np.float64) / 65535.0 * (hi - lo) + lo
    return dict(t=h[3], f=h[4], off=h[13], P=P, N=oct_decode(n), V=v.astype(np.float32), tri=t, lo=lo, hi=hi,
                half_step=((hi - lo) / 65535.0 / 2.0))


def write_gw45s(p, Pu, Nu, Vu, tri, tnow, f, off):
    lo = Pu.min(0) if len(Pu) else np.zeros(3); hi = Pu.max(0) if len(Pu) else np.ones(3)
    q = np.round((Pu - lo) / np.maximum(hi - lo, 1e-9) * 65535).astype(np.uint16)
    qerr = float(np.max(np.abs(q.astype(np.float64) / 65535 * (hi - lo) + lo - Pu))) if len(Pu) else 0.0
    head = struct.pack(HEAD_FMT, b"GW45SRF1", 1, HEAD_BYTES, float(tnow), int(f), len(Pu), len(tri),
                       *[float(v) for v in lo], *[float(v) for v in hi], float(off), 0.0)
    head = head + b"\0" * (HEAD_BYTES - len(head))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    blob = head + q.tobytes() + oct_encode(Nu).tobytes() + Vu.astype(np.float16).tobytes() + tri.astype(np.uint32).tobytes()
    same = None
    if os.path.exists(p):                      # never rewrite an earlier batch's file: compare instead
        same = (open(p, "rb").read() == blob)
    else:
        with open(p, "wb") as fh:
            fh.write(blob)
    return dict(bytes=len(blob), qerr_m=qerr, half_step_m=[float(v) for v in (hi - lo) / 65535.0 / 2.0], identical_to_existing_file=same)


# ---------------------------------------------------------------- 1. inputs, hip check, checkpoint copy
cfg_src = json.load(open(SRC_RUN + "/cfg.json", encoding="utf8"))
cfg_hero = json.load(open(HERO_RUN + "/cfg.json", encoding="utf8"))
hip_sha = sha256_file(HIP)
REC["inputs"] = dict(hip=HIP, hip_sha256=hip_sha, src_cfg_hip_sha256=cfg_src.get("hip_sha256"), hero_cfg_hip_sha256=cfg_hero.get("hip_sha256"),
                     src_run=SRC_RUN, hero_run=HERO_RUN,
                     parm_diff_src_vs_hero={k: [cfg_src["parms"].get(k), cfg_hero["parms"].get(k)]
                                            for k in sorted(set(cfg_src["parms"]) | set(cfg_hero["parms"]))
                                            if cfg_src["parms"].get(k) != cfg_hero["parms"].get(k)})
if hip_sha != cfg_src.get("hip_sha256"):
    REC["stopped"] = "the scene %s changed since the source run (sha256 %s vs cfg %s)" % (HIP, hip_sha[:16], str(cfg_src.get("hip_sha256"))[:16])
    save(); log("STOP", REC["stopped"]); sys.exit(2)
ck_src = SRC_RUN + "/ckpt/v.%04d.sim" % FRAME
ck_dst = CKD + "/v.%04d.sim" % FRAME
for p in glob.glob(CKD + "/*.sim"):                 # only our own test folder: leftovers of an earlier test
    if os.path.normcase(os.path.abspath(p)) != os.path.normcase(os.path.abspath(ck_dst)):
        os.remove(p)
if not (os.path.exists(ck_dst) and os.path.getsize(ck_dst) == os.path.getsize(ck_src)):
    shutil.copyfile(ck_src, ck_dst)
REC["inputs"]["ckpt_src"] = ck_src
REC["inputs"]["ckpt_copy"] = ck_dst
REC["inputs"]["ckpt_sha256_src"] = sha256_file(ck_src)
REC["inputs"]["ckpt_sha256_copy"] = sha256_file(ck_dst)
assert REC["inputs"]["ckpt_sha256_src"] == REC["inputs"]["ckpt_sha256_copy"]
hero_s = HERO_RUN + "/surf/s_%05d.gw45s" % FRAME
HERO = read_gw45s(hero_s) if os.path.exists(hero_s) else None
TNOW = HERO["t"] if HERO else (FRAME - 1) / 24.0
OFFV = HERO["off"] if HERO else float(cfg_hero.get("still_offset_m") or 0.0)
REC["inputs"]["hero_surface"] = hero_s if HERO else None
REC["inputs"]["hero_header"] = dict(t=TNOW, off=OFFV, n_vert=int(len(HERO["P"])) if HERO else None,
                                    n_tri=int(len(HERO["tri"])) if HERO else None,
                                    bytes=os.path.getsize(hero_s) if HERO else None,
                                    half_step_m=[float(v) for v in HERO["half_step"]] if HERO else None)
save()
guard("start")

# ---------------------------------------------------------------- 2. scene
hou.hipFile.load(HIP, suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/G52_SETUP/CTRL")
for k, v in cfg_src["parms"].items():
    if ctrl.parm(k) is not None:
        ctrl.parm(k).set(v)
ctrl.parm("ckpt").set(CKD)
ctrl.parm("ckpt_on").set(1)
ctrl.parm("ckpt_every").set(48)
ctrl.parm("crop_x0").set(CROP["x0"]); ctrl.parm("crop_x1").set(CROP["x1"]); ctrl.parm("crop_z1").set(CROP["z1"])
OX, OY, OZ = (float(ctrl.parm(k).eval()) for k in ("ox", "oy", "oz"))
O3 = np.array([OX, OY, OZ])
sfn = hou.node("/obj/G52_SURF")
di = sfn.node("particles"); layer = sfn.node("layer_and_mirror"); pfs = sfn.node("fluid_surface"); sout = sfn.node("OUT_SURF")
pc = sfn.createNode("attribwrangle", "hs_particle_crop")
pc.setInput(0, di)
pc.parm("class").set(2)
pc.parm("snippet").set("""
vector q = @P - set(%r, %r, %r);
if (q.x < %r || q.x > %r || q.z > %r) removepoint(0, @ptnum);
""" % (OX, OY, OZ, CROP["x0"] - MARGIN, CROP["x1"] + MARGIN, CROP["z1"] + MARGIN))
layer.setInput(0, pc)
dop = hou.node("/obj/G52_SIM")
REC["scene"] = dict(dop_explicitcache=dop.parm("explicitcache").eval(), dop_cachename=dop.parm("explicitcachename").eval(),
                    pfs_type=pfs.type().nameWithCategory(), O3=[OX, OY, OZ], dp=float(ctrl.parm("dp").eval()),
                    gridscale=float(ctrl.parm("gridscale").eval()), surf_vox_scale_cfg=float(ctrl.parm("surf_vox_scale").eval()),
                    pfs_particlesep=pfs.parm("particlesep").eval(), pfs_voxelsize=pfs.parm("voxelsize").eval())
log("scene loaded", REC["scene"])
save()
guard("scene")

# ---------------------------------------------------------------- 3. load the checkpoint (no simulation)
hou.setSimulationEnabled(True)
t0 = time.time()
hou.setFrame(FRAME)
di.cook(force=True)
gp = di.geometry()
t_load = time.time() - t0
sims = sorted(os.path.basename(p) for p in glob.glob(CKD + "/*.sim"))
try:
    sim_t = float(dop.simulation().time())
except Exception as e:
    sim_t = repr(e)[:100]
n_all = gp.intrinsicValue("pointcount") if gp is not None else -1
REC["load"] = dict(seconds=round(t_load, 1), particles=int(n_all), sim_time=sim_t, sim_files_in_test_ckpt=sims,
                   dop_errors=[str(e)[:200] for e in dop.errors()], di_errors=[str(e)[:200] for e in di.errors()])
log("checkpoint loaded", REC["load"])
if sims != ["v.%04d.sim" % FRAME] or n_all < 1000000:
    REC["stopped"] = "checkpoint load not as expected (files %s, particles %s)" % (sims, n_all)
    save(); log("STOP", REC["stopped"]); LOGF.close(); os._exit(4)
open(OUT + "/LOADED%s.txt" % TAG, "w").write(time.strftime("%Y-%m-%d %H:%M:%S") + " particles %d load %.1f s\n" % (n_all, t_load))
save()
guard("checkpoint")
t0 = time.time()
layer.cook(force=True)
REC["load"]["particle_prep_s"] = round(time.time() - t0, 2)
REC["load"]["particles_after_crop_layer_mirror"] = int(layer.geometry().intrinsicValue("pointcount"))
log("particle crop + layer", REC["load"])

# ---------------------------------------------------------------- 4. variants
PFS_KEYS = ["adaptivity", "influenceradius", "surfacedistance", "minvoxelradius", "resamplingiterations", "dodilate", "dilateoffset", "dosmooth",
            "smoothoperation", "smoothiterations", "doerode", "erodeoffset", "dofinalsmooth", "finalsmoothoperation", "finalsmoothiterations",
            "isovalue", "conversion", "surfmethod"]
INIT = {}
for k in PFS_KEYS:
    p = pfs.parm(k)
    if p is not None:
        INIT[k] = p.evalAsString() if p.parmTemplate().type() in (hou.parmTemplateType.String, hou.parmTemplateType.Menu) else p.eval()
MENUS = {}
for k in ("smoothoperation", "finalsmoothoperation", "surfmethod", "conversion"):
    try:
        MENUS[k] = list(pfs.parm(k).parmTemplate().menuItems())
    except Exception as e:
        MENUS[k] = repr(e)[:80]
REC["pfs_initial"] = INIT
REC["pfs_menus"] = MENUS
VOX0 = float(ctrl.parm("surf_vox_scale").eval())


def set_variant(vd):
    for k, v in INIT.items():
        if k in ("conversion", "surfmethod"):
            continue
        pfs.parm(k).set(v)
    ctrl.parm("surf_vox_scale").set(VOX0)
    applied = {}
    for k, v in vd.items():
        if k == "vox":
            ctrl.parm("surf_vox_scale").set(v); applied[k] = v; continue
        if isinstance(v, str) and v.startswith("@"):
            items = MENUS.get(k) or []
            hit = [it for it in items if v[1:] in it.lower()]
            if not hit:
                raise RuntimeError("no menu item like %s in %s: %s" % (v, k, items))
            v = hit[0]
        pfs.parm(k).set(v); applied[k] = v
    return applied


MESH = {}
for name, desc, vd in VARIANTS:
    applied = set_variant(vd)
    t0 = time.time()
    sout.cook(force=True)
    cook_s = time.time() - t0
    g = sout.geometry()
    errs = [str(e)[:200] for e in pfs.errors()] + [str(e)[:200] for e in sout.errors()]
    Pp = np.frombuffer(g.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - O3
    N = np.frombuffer(g.pointFloatAttribValuesAsString("N"), dtype=np.float32).reshape(-1, 3).astype(np.float64)
    try:
        V = np.frombuffer(g.pointFloatAttribValuesAsString("v"), dtype=np.float32).reshape(-1, 3)
    except Exception:
        V = np.zeros_like(Pp, dtype=np.float32)
    ia = np.frombuffer(g.primIntAttribValuesAsString("a"), dtype=np.int32)
    ib = np.frombuffer(g.primIntAttribValuesAsString("b"), dtype=np.int32)
    ic = np.frombuffer(g.primIntAttribValuesAsString("c"), dtype=np.int32)
    used = np.unique(np.concatenate([ia, ib, ic]))
    remap = -np.ones(len(Pp), np.int64); remap[used] = np.arange(len(used))
    tri = np.stack([remap[ia], remap[ib], remap[ic]], 1).astype(np.int64)
    Pu = Pp[used]; Nu = N[used].copy(); Vu = V[used]
    seam = np.abs(Pu[:, 2]) < 1e-4
    Nu[seam, 2] = 0.0
    Nu = Nu / np.maximum(np.linalg.norm(Nu, axis=1, keepdims=True), 1e-12)
    wr = write_gw45s(OUT + "/%s/s_%05d.gw45s" % (name, FRAME), Pu, Nu, Vu, tri, TNOW, FRAME, OFFV)
    MESH[name] = dict(P=Pu, N=Nu, tri=tri)
    REC["variants"][name] = dict(desc=desc, parms=applied, pfs_voxel_m=float(ctrl.parm("dp").eval()) * float(ctrl.parm("surf_vox_scale").eval()),
                                 cook_s=round(cook_s, 2), n_vert=int(len(Pu)), n_tri=int(len(tri)), errors=errs, file=wr)
    log("variant", name, REC["variants"][name])
    save()
    guard("variant " + name)
del g, Pp, N, V
set_variant({})

# hero mesh (crop by triangle centroid like the crop wrangle)
if HERO is not None:
    c = HERO["P"][HERO["tri"]].mean(1)
    keep = (c[:, 0] >= CROP["x0"]) & (c[:, 0] <= CROP["x1"]) & (c[:, 2] <= CROP["z1"])
    t_ = HERO["tri"][keep]
    used = np.unique(t_.ravel())
    remap = -np.ones(len(HERO["P"]), np.int64); remap[used] = np.arange(len(used))
    MESH["hero"] = dict(P=HERO["P"][used], N=HERO["N"][used], tri=remap[t_])

# ---------------------------------------------------------------- 5. measures (Houdini point queries + numpy)
cmp_ = hou.node("/obj").createNode("geo", "HS_CMP")
for c_ in cmp_.children():
    c_.destroy()
STASH = {}


def stash_of(name):
    m = MESH[name]
    g = hou.Geometry()
    g.addAttrib(hou.attribType.Point, "N", (0.0, 1.0, 0.0))
    g.createPoints([(0.0, 0.0, 0.0)] * len(m["P"]))
    g.setPointFloatAttribValuesFromString("P", m["P"].astype(np.float32).tobytes())
    g.setPointFloatAttribValuesFromString("N", m["N"].astype(np.float32).tobytes())
    tl = m["tri"].tolist()
    try:
        g.createPolygons(tl)
    except Exception as e:
        log("createPolygons fallback", repr(e)[:120])
        pts = g.points()
        for t in tl:
            pr = g.createPolygon()
            for i in t:
                pr.addVertex(pts[i])
    st = cmp_.createNode("stash", "m_" + name)
    st.parm("stash").set(g)
    STASH[name] = st
    return st


def wrangle(a, b, code, attrs):
    w = cmp_.createNode("attribwrangle")
    w.setInput(0, a)
    if b is not None:
        w.setInput(1, b)
    w.parm("class").set(2)
    w.parm("snippet").set(code)
    w.cook(force=True)
    g = w.geometry()
    out = {}
    for k, n in attrs:
        out[k] = np.frombuffer(g.pointFloatAttribValuesAsString(k), dtype=np.float32).reshape(-1, n).astype(np.float64) if n > 1 else \
            np.frombuffer(g.pointFloatAttribValuesAsString(k), dtype=np.float32).astype(np.float64)
    w.destroy()
    return out


VEX_DIST = """
int prim; vector uv;
float d = xyzdist(1, @P, prim, uv);
vector cp = primuv(1, "P", prim, uv);
vector nn = normalize(primuv(1, "N", prim, uv));
f@d = d; f@sd = dot(@P - cp, nn);
int np_ = nearpoint(1, @P);
f@dv = distance(@P, point(1, "P", np_));
"""
VEX_NNOISE = """
int h = pcopen(0, "P", @P, 1.5, 1500);
vector m = 0;
while (pciterate(h)) { vector nn; pcimport(h, "N", nn); m += nn; }
pcclose(h);
f@ang = degrees(acos(clamp(dot(normalize(v@N), normalize(m)), -1.0, 1.0)));
"""
VEX_RAST = """
vector hp, uvw;
int pr = intersect(1, set(@P.x, 40.0, @P.z), {0, -80, 0}, hp, uvw);
f@h = pr >= 0 ? hp.y : -999.0;
v@hn = pr >= 0 ? normalize(primuv(1, "N", pr, uvw)) : {0, 0, 0};
"""


def in_core(P):
    return (P[:, 0] >= CORE["x0"]) & (P[:, 0] <= CORE["x1"]) & (P[:, 2] <= CORE["z1"])


def tri_measures(m):
    P, tri = m["P"], m["tri"]
    c = P[tri].mean(1)
    k = in_core(c)
    t = tri[k]
    a, b, cc = P[t[:, 0]], P[t[:, 1]], P[t[:, 2]]
    fn = np.cross(b - a, cc - a)
    area = 0.5 * np.linalg.norm(fn, axis=1)
    fn = fn / np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
    E = np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]])
    F = np.concatenate([np.arange(len(t))] * 3)
    Es = np.sort(E, 1)
    L = np.linalg.norm(P[Es[:, 0]] - P[Es[:, 1]], axis=1)
    key = Es[:, 0] * (len(P) + 1) + Es[:, 1]
    o = np.argsort(key, kind="stable")
    ks = key[o]
    same = np.nonzero(ks[1:] == ks[:-1])[0]
    f1, f2 = F[o][same], F[o][same + 1]
    dih = np.degrees(np.arccos(np.clip((fn[f1] * fn[f2]).sum(1), -1, 1)))
    uk = np.unique(ks, return_index=True)[1]
    Lu = L[o][uk]; Eu = Es[o][uk]
    top = fn[:, 1] > 0.5
    # top-view direction of edges of top-facing triangles (axis-aligned share: within 5 deg of 0/45/90/135)
    Et = np.concatenate([t[top][:, [0, 1]], t[top][:, [1, 2]], t[top][:, [2, 0]]])
    d = P[Et[:, 1]] - P[Et[:, 0]]
    ang = np.degrees(np.arctan2(d[:, 2], d[:, 0])) % 45.0
    lt = np.hypot(d[:, 0], d[:, 2])
    axis_share = float(lt[(ang < 5.0) | (ang > 40.0)].sum() / max(lt.sum(), 1e-12))
    return dict(n_tri_core=int(len(t)), n_vert_core=int(in_core(P).sum()), area_core_m2=round(float(area.sum()), 1),
                edge_m_p5_25_50_75_95_99_max=pct(Lu, [5, 25, 50, 75, 95, 99, 100]),
                tri_area_m2_p50_p95=pct(area, [50, 95]),
                dihedral_deg_p50_p90_p95_p99=pct(dih, [50, 90, 95, 99]),
                axis_aligned_edge_share_top=round(axis_share, 3), axis_share_isotropic=round(10.0 / 45.0, 3))


def seam_of(m):
    P, tri = m["P"], m["tri"]
    s = np.abs(P[:, 2]) < 5e-4
    E = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    E = E[s[E[:, 0]] & s[E[:, 1]]]
    E = np.unique(np.sort(E, 1), axis=0)
    return P[s][:, :2], P[E[:, 0]][:, :2], P[E[:, 1]][:, :2]


def pt_seg(Q, A, B):
    out = np.full(len(Q), np.inf)
    if len(A) == 0:
        return out
    AB = B - A
    L2 = np.maximum((AB ** 2).sum(1), 1e-18)
    for i in range(0, len(Q), 2000):
        q = Q[i:i + 2000]
        t = np.clip(((q[:, None, :] - A[None]) * AB[None]).sum(2) / L2[None], 0, 1)
        d = np.linalg.norm(q[:, None, :] - (A[None] + t[..., None] * AB[None]), axis=2)
        out[i:i + 2000] = d.min(1)
    return out


def boxmean(a, valid, w):
    """nan-aware box mean, w odd cells, separable via cumsum."""
    def one(x, ax):
        r = w // 2
        pad = [(0, 0), (0, 0)]; pad[ax] = (r + 1, r)
        c = np.cumsum(np.pad(x, pad), axis=ax)
        n = x.shape[ax]
        hi = np.take(c, np.arange(w, w + n), axis=ax); lo = np.take(c, np.arange(0, n), axis=ax)
        return hi - lo
    v = valid.astype(np.float64)
    s = one(one(np.where(valid, a, 0.0), 0), 1)
    n = one(one(v, 0), 1)
    return np.where(n > 0.5 * w * w, s / np.maximum(n, 1e-12), np.nan)


xs = np.arange(CORE["x0"] + 0.5 * RAST, CORE["x1"], RAST)
zs = np.arange(0.5 * RAST, CORE["z1"], RAST)
GX, GZ = np.meshgrid(xs, zs, indexing="ij")
grid = hou.Geometry()
grid.createPoints([(0.0, 0.0, 0.0)] * GX.size)
grid.setPointFloatAttribValuesFromString("P", np.stack([GX.ravel(), np.zeros(GX.size), GZ.ravel()], 1).astype(np.float32).tobytes())
gst = cmp_.createNode("stash", "raster_grid")
gst.parm("stash").set(grid)
RASTERS = {}


def raster_measures(name):
    r = wrangle(gst, STASH[name], VEX_RAST, [("h", 1), ("hn", 3)])
    h = r["h"].reshape(GX.shape); hn = r["hn"].reshape(GX.shape + (3,))
    valid = h > -900
    RASTERS[name] = (h.astype(np.float32), hn.astype(np.float16))
    w1, w15, w4 = int(round(1.0 / RAST)) | 1, int(round(1.5 / RAST)) | 1, int(round(4.0 / RAST)) | 1
    b1 = boxmean(h, valid, w1); b15 = boxmean(h, valid, w15); b4 = boxmean(h, valid, w4)
    r1 = h - b1                       # < ~1 m features (particle lumps, facets)
    r14 = b1 - b4                     # 1-4 m
    gx4, gz4 = np.gradient(b4, RAST)
    calm = valid & np.isfinite(b4) & (np.hypot(gx4, gz4) < 0.1) & (np.abs(r1) < 0.3)
    allv = valid & np.isfinite(b4) & (np.abs(r1) < 0.3)
    gx, gz = np.gradient(b15, RAST)
    ns = np.stack([-gx, np.ones_like(gx), -gz], -1)
    ns = ns / np.linalg.norm(ns, axis=-1, keepdims=True)
    ang = np.degrees(np.arccos(np.clip((ns * hn).sum(-1), -1, 1)))

    def rms(a, m):
        return round(float(np.sqrt(np.nanmean(a[m] ** 2)) * 1000.0), 2) if m.any() else None
    return dict(valid_share=round(float(valid.mean()), 4), calm_share=round(float(calm.mean()), 4),
                hp_lt1m_rms_mm_calm=rms(r1, calm), hp_lt1m_rms_mm_all=rms(r1, allv),
                band_1_4m_rms_mm_calm=rms(r14, calm), band_1_4m_rms_mm_all=rms(r14, allv),
                pixel_normal_vs_s1p5_deg_p50_p90_p99_calm=pct(ang[calm], [50, 90, 99]),
                pixel_normal_vs_s1p5_deg_p50_p90_p99_all=pct(ang[allv], [50, 90, 99]))


names = [v[0] for v in VARIANTS] + (["hero"] if "hero" in MESH else [])
for nm in names:
    t0 = time.time()
    stash_of(nm)
    m = MESH[nm]
    rec = REC["variants"].setdefault(nm, dict(desc="the hero's own s_%05d.gw45s (recorded), cropped by triangle centroid" % FRAME))
    rec["mesh"] = tri_measures(m)
    nn = wrangle(STASH[nm], None, VEX_NNOISE, [("ang", 1)])["ang"]
    k = in_core(m["P"])
    top = m["N"][:, 1] > 0.5
    rec["vnormal_noise_s1p5_deg_p50_p90_p99_rms_top"] = pct(nn[k & top], [50, 90, 99]) + \
        [round(float(np.sqrt(np.mean(nn[k & top] ** 2))), 2) if (k & top).any() else None]
    rec["raster"] = raster_measures(nm)
    Pk = m["P"][k]
    rec["crest_core"] = dict(y_max=round(float(Pk[:, 1].max()), 4), at_xz=[round(float(v), 3) for v in Pk[np.argmax(Pk[:, 1])][[0, 2]]])
    sv, sa, sb = seam_of(m)
    sk = (sv[:, 0] >= CORE["x0"]) & (sv[:, 0] <= CORE["x1"])
    rec["section_centre"] = dict(n_vert=int(sk.sum()), y_max=round(float(sv[sk, 1].max()), 4) if sk.any() else None,
                                 x_at_y_max=round(float(sv[sk][np.argmax(sv[sk, 1]), 0]), 3) if sk.any() else None)
    m["seam"] = (sv[sk], sa, sb)
    rec["measure_s"] = round(time.time() - t0, 1)
    log("measures", nm, json.dumps({k_: rec[k_] for k_ in ("mesh", "vnormal_noise_s1p5_deg_p50_p90_p99_rms_top", "raster", "crest_core",
                                                         "section_centre")}))
    save()
    guard("measure " + nm)


def compare(a, b):
    """distances of a's core vertices to mesh b, b's core vertices to mesh a; crest and section differences."""
    ma, mb = MESH[a], MESH[b]
    ab = wrangle(STASH[a], STASH[b], VEX_DIST, [("d", 1), ("sd", 1), ("dv", 1)])
    ba = wrangle(STASH[b], STASH[a], VEX_DIST, [("d", 1), ("sd", 1), ("dv", 1)])
    ka, kb = in_core(ma["P"]), in_core(mb["P"])
    sva, saa, sba = ma["seam"]; svb, sab, sbb = mb["seam"]
    s_ab = pt_seg(sva, sab, sbb); s_ba = pt_seg(svb, saa, sba)
    ra, rb = REC["variants"][a], REC["variants"][b]
    return dict(
        a_to_b_mean_p95_max_m=[round(float(ab["d"][ka].mean()), 4)] + pct(ab["d"][ka], [95, 100]),
        a_to_b_signed_mean_m=round(float(ab["sd"][ka].mean()), 4),
        b_to_a_mean_p95_max_m=[round(float(ba["d"][kb].mean()), 4)] + pct(ba["d"][kb], [95, 100]),
        b_to_a_signed_mean_m=round(float(ba["sd"][kb].mean()), 4),
        a_vertex_to_nearest_b_vertex_p50_max_m=pct(ab["dv"][ka], [50, 100]),
        hausdorff_m=round(float(max(ab["d"][ka].max(), ba["d"][kb].max())), 4),
        crest_y_change_m=round(ra["crest_core"]["y_max"] - rb["crest_core"]["y_max"], 4),
        section_crest_y_change_m=(round(ra["section_centre"]["y_max"] - rb["section_centre"]["y_max"], 4)
                                  if ra["section_centre"]["y_max"] is not None and rb["section_centre"]["y_max"] is not None else None),
        section_a_to_b_mean_p95_max_m=[round(float(np.mean(s_ab)), 4) if len(s_ab) else None] + pct(s_ab, [95, 100]),
        section_b_to_a_mean_p95_max_m=[round(float(np.mean(s_ba)), 4) if len(s_ba) else None] + pct(s_ba, [95, 100]),
        counts_core=[int(ka.sum()), int(kb.sum())])


if "hero" in MESH:
    c = compare("b0_base", "hero")
    hs = np.linalg.norm(HERO["half_step"]); bs = np.linalg.norm(np.array(REC["variants"]["b0_base"]["file"]["half_step_m"]))
    tol = float(hs + bs + 1e-4)
    c["quantization_tolerance_m"] = round(tol, 5)
    c["rule"] = "baseline (re-surfaced from the checkpoint) vs the hero's recorded s_%05d in the core: max distance both ways <= hero half-step + baseline half-step + 0.1 mm" % FRAME
    c["pass"] = bool(c["hausdorff_m"] <= tol)
    REC["baseline_vs_hero"] = c
    log("BASELINE vs HERO", json.dumps(c))
    save()
for nm in [v[0] for v in VARIANTS if v[0] != "b0_base"]:
    REC["variants"][nm]["vs_base"] = compare(nm, "b0_base")
    log("vs base", nm, json.dumps(REC["variants"][nm]["vs_base"]))
    save()
    guard("compare " + nm)

# full-frame size estimate: scale each variant's crop bytes by the hero's full-frame / crop ratio of the base
if HERO is not None:
    ratio = REC["inputs"]["hero_header"]["bytes"] / max(REC["variants"]["b0_base"]["file"]["bytes"], 1)
    for nm in [v[0] for v in VARIANTS]:
        r_ = REC["variants"][nm]
        r_["full_frame_mb_est"] = round(r_["file"]["bytes"] * ratio / 1e6, 2)
        r_["full_clip_gb_est_1849_frames"] = round(r_["file"]["bytes"] * ratio * 1849 / 1e9, 2)
    REC["size_rule"] = "[computed] variant crop bytes x (hero full-frame bytes / base crop bytes) = %.2f; assumes the crop is representative" % ratio

np.savez_compressed(OUT + "/raster_f%04d%s.npz" % (FRAME, TAG), xs=xs.astype(np.float32), zs=zs.astype(np.float32), names=np.array(list(RASTERS)),
                    **{"h_" + k: v[0] for k, v in RASTERS.items()}, **{"hn_" + k: v[1] for k, v in RASTERS.items()},
                    **{"seam_" + k: MESH[k]["seam"][0].astype(np.float32) for k in RASTERS})
REC["raster_file"] = OUT + "/raster_f%04d%s.npz" % (FRAME, TAG)
REC["wall_s"] = round(time.time() - T_START, 1)
guard("end")
REC["sim_files_in_test_ckpt_end"] = sorted(os.path.basename(p) for p in glob.glob(CKD + "/*.sim"))
save()
open(OUT + "/DONE%s.txt" % TAG, "w").write(time.strftime("%Y-%m-%d %H:%M:%S") + " wall %.1f s\n" % REC["wall_s"])
log("DONE", REC["wall_s"], "s")
LOGF.close()
os._exit(0)
