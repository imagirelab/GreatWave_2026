# -*- coding: utf-8 -*-
"""FLIP39 R：E の場の一番（E3_dir20_lens、粒子 1 m）を、途中保存から同じ場面・同じ値で計算し直し、
主役の範囲（とその周り）の水面の SDF（surface）と流速（vel）を毎コマ 2 m の升目に写して書き出す（hython 22.0.459）。
FLIP37 の p3_export_coarse.py（P3 の境界の値）を E の場面（Houdini/FLIP39/e_tank.hiplc）へ移したもの。

使い方: hython r_export_coarse.py '<JSON>'
JSON: {"run_id": "C3_export", "src_dir": ".../E/E3_dir20_lens", "ckpt_from": 936, "f_end": 1272,
       "box": [x0, x1, y0, y1, z0, z1]（升の中心の範囲、2 m おき）, "wall_limit_s": 1740}
- 途中保存：E3 の ckpt/e.<ckpt_from>.sim を R/<run_id>/ckpt へ写し（E3 のフォルダーには書かない）、そこから続ける。
- 成分の表（造波の帯の目標）は e_run.py と同じく e_tanklib.comp_table で作り直す。計算の中に力・速さは足さない（E3 と同じ）。
出力: Unity/Build/FLIP39/R/<run_id>/fields/c_FFFF.bgeo.sc（surface・vel.x/y/z の 4 つの体積、2 m の升目）、
      crest.npy（e_run.py と同じ形の頂の記録。E3 と同じになるかの確かめ）、run.json、Unity/Build/FLIP39/runs.jsonl に 1 行。
場面は読むだけで保存しない（sha256 を E3 の run.json と比べる）。
"""
import hou, sys, os, json, time, hashlib, ctypes, shutil
from ctypes import wintypes
import numpy as np

sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip37")
import p3_nothrottle
NOTHROTTLE = p3_nothrottle.off()
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
import e_tanklib as L

HIP = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP39/e_tank.hiplc"
ROOT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39"
args = json.loads(sys.argv[1])
rid = args["run_id"]
OUT = os.path.join(ROOT, "R", rid).replace("\\", "/")
FD = OUT + "/fields"
os.makedirs(FD, exist_ok=True)


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
src_dir = args["src_dir"]
src = json.load(open(os.path.join(src_dir, "run.json"), encoding="utf8"))
HIP_SHA = hashlib.sha256(open(HIP, "rb").read()).hexdigest()
if HIP_SHA != src["hip_sha256"]:
    print("WARNING hip sha differs from source run", HIP_SHA, src["hip_sha256"])
hou.hipFile.load(HIP, suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/E_SETUP/CTRL")
skip = {"copyinput", "cacheinput", "ckpt", "ckpt_on", "ckpt_every", "explicitcachename_eval"}
for k, v in src["parms"].items():
    if k in skip or ctrl.parm(k) is None:
        continue
    ctrl.parm(k).set(v)
grp_args = src["group"]
bedp = {k: ctrl.parm(k).eval() for k in ("h0", "hr", "slope_n", "xs0", "lg1_d", "lg1_x", "lg1_sx")}
bedp["flat"] = bool(src.get("flat", False))
COMP = L.comp_table(grp_args, bedp, ctrl.parm("Lz").eval())
for path in L.BODIES:
    hou.node(path).parm("snippet").set(L.snippet(path, COMP))
# 成分の表が E3 のもの（comp_c0001.json）と同じかを確かめる
c_src = json.load(open(os.path.join(src_dir, "comp_c0001.json"), encoding="utf8"))
comp_diff = float(max(np.max(np.abs(np.array(c_src["a"]) - COMP["a"])), np.max(np.abs(np.array(c_src["phi"]) - COMP["phi"]))))
print("components", len(COMP["a"]), "max diff vs E3", comp_diff)

ckdir = OUT + "/ckpt"
os.makedirs(ckdir, exist_ok=True)
ck_from = int(args["ckpt_from"])
ck_src = os.path.join(src_dir, "ckpt", "e.%04d.sim" % ck_from)
ck_dst = os.path.join(ckdir, "e.%04d.sim" % ck_from)
if not os.path.isfile(ck_dst):
    shutil.copyfile(ck_src, ck_dst)
ctrl.parm("ckpt").set(ckdir)
ctrl.parm("ckpt_on").set(1)
ctrl.parm("ckpt_every").set(int(args.get("ckpt_every", 72)))
hou.setSimulationEnabled(True)
fps = hou.fps()
dop = hou.node("/obj/E_SIM")

# ---- 書き出しの鎖（記憶の中だけ。保存しない）
x0, x1, y0, y1, z0, z1 = [float(v) for v in args["box"]]
DX = 2.0
geo = hou.node("/obj").createNode("geo", "R_EXPORT")
for c in geo.children():
    c.destroy()
fi = geo.createNode("dopimportfield::2.0", "fields")
fi.parm("doppath").set("/obj/E_SIM")
fi.parm("fields").set(2)
fi.parm("objname1").set("water"); fi.parm("fieldname1").set("surface")
fi.parm("objname2").set("water"); fi.parm("fieldname2").set("vel")


def mkvol(name, rank):
    v = geo.createNode("volume", "box_" + name)
    v.parm("name").set(name)
    v.parm("rank").set(rank)
    v.parm("uniformsamples").set("size")
    v.parm("divsize").set(DX)
    v.parm("sizex").set(x1 - x0 + DX); v.parm("sizey").set(y1 - y0 + DX); v.parm("sizez").set(z1 - z0 + DX)
    v.parm("tx").set(0.5 * (x0 + x1)); v.parm("ty").set(0.5 * (y0 + y1)); v.parm("tz").set(0.5 * (z0 + z1))
    return v


vs = mkvol("surface", "scalar")
vv = mkvol("vel", "vector")
mg = geo.createNode("merge", "m")
mg.setInput(0, vs); mg.setInput(1, vv)
vw = geo.createNode("volumewrangle", "sample")
vw.setInput(0, mg); vw.setInput(1, fi)
vw.parm("snippet").set('f@surface = volumesample(1, "surface", @P);\nv@vel = volumesamplev(1, "vel", @P);')
outn = geo.createNode("null", "OUT")
outn.setInput(0, vw)

f0, f1 = ck_from + 1, int(args["f_end"])
wall_limit = float(args.get("wall_limit_s", 1740))
Lz = float(ctrl.parm("Lz").eval())
zbins = np.arange(-0.5 * Lz, 0.5 * Lz + 1e-6, 10.0)
crest, frames, wall, npts, peak = [], [], [], [], []
t_start = time.time()
stopped = None
info = {"nothrottle": list(NOTHROTTLE), "comp_maxdiff_vs_src": comp_diff}
for f in range(f0, f1 + 1):
    out_f = FD + "/c_%04d.bgeo.sc" % f
    t0 = time.time()
    hou.setFrame(f)
    n = -1
    try:
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
                near = m.copy(); near[m] = (np.abs(Ph[m, 0] - xb_) < 3.0) & (Ph[m, 1] > yb_ - 2.0)
                row += [yb_, xb_, float(Vh[near, 0].max()) if near.any() else 0.0]
            else:
                row += [np.nan, np.nan, np.nan]
        crest.append(row)
    except Exception as e:
        info.setdefault("particle_errors", []).append(str(e)[:200])
    dt = time.time() - t0
    g = outn.geometry()
    if f == f0:
        info["export_prims"] = [(p.attribValue("name"), p.resolution()) for p in g.prims()]
    g.saveToFile(out_f)
    r, pk = rss_gb()
    frames.append(f); wall.append(dt); npts.append(n); peak.append(pk)
    if f % 24 == 0 or f == f0:
        print("f=%d t=%.2f sim=%.2fs pts=%d rss=%.2fGB io=%.2fs" % (f, (f - 1) / fps, dt, n, r, time.time() - t0 - dt))
        sys.stdout.flush()
        np.save(OUT + "/crest.npy", np.array(crest, dtype=np.float64))
    if time.time() - t_start > wall_limit:
        stopped = "wall_limit at frame %d" % f
        break

np.save(OUT + "/crest.npy", np.array(crest, dtype=np.float64))
# E3 と同じかの確かめ（z の 10 m の帯ごとの頂の高さ・位置）
try:
    import glob
    rc = np.concatenate([np.load(p) for p in sorted(glob.glob(os.path.join(src_dir, "crest_c*.npy")))])
    mine = np.array(crest)
    dif, difx = [], []
    for row in mine:
        fr = int(row[0])
        m = rc[:, 0] == fr
        if not m.any():
            continue
        b = rc[m][-1]
        dif.append(np.nanmax(np.abs(row[2::3] - b[2::3])))
        difx.append(np.nanmax(np.abs(row[3::3] - b[3::3])))
    info["crest_maxdiff_vs_src_m"] = float(np.nanmax(dif)) if dif else None
    info["crest_meddiff_vs_src_m"] = float(np.nanmedian(dif)) if dif else None
    info["crest_x_maxdiff_vs_src_m"] = float(np.nanmax(difx)) if difx else None
    info["crest_frames_compared"] = len(dif)
except Exception as e:
    info["compare_error"] = str(e)[:200]
ck = sorted(os.listdir(ckdir))
rec = {
    "stage": "R", "run_id": rid, "kind": "coarse_export", "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    "houdini": hou.applicationVersionString(), "hip": HIP, "hip_sha256": HIP_SHA, "src_dir": src_dir,
    "src_hip_sha256": src["hip_sha256"], "parms": src["parms"], "group": grp_args, "box": [x0, x1, y0, y1, z0, z1], "dx": DX,
    "ckpt_from": ck_from, "f_start": f0, "f_end_req": f1, "f_end_done": frames[-1] if frames else None, "fps": fps,
    "t_off": float(src["parms"].get("t_off", 0.0)),
    "particles_max": max(npts) if npts else None, "wall_total_s": round(time.time() - t_start, 1),
    "wall_launch_s": round(time.time() - t_launch, 1),
    "wall_per_frame_median_s": round(float(np.median(wall[1:])), 3) if len(wall) > 1 else None,
    "rss_peak_gb": round(max(peak), 2) if peak else None, "ckpt_files": len(ck),
    "stopped": stopped, "info": info, "concurrent_with": None, "note": args.get("note", ""),
}
json.dump(rec, open(OUT + "/run.json", "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
with open(os.path.join(ROOT, "runs.jsonl"), "a", encoding="utf8") as fh:
    fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
print("DONE", json.dumps({k: rec[k] for k in ("run_id", "f_end_done", "wall_total_s", "stopped")}), json.dumps(info, default=str)[:600])
