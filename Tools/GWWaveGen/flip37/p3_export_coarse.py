# -*- coding: utf-8 -*-
"""P3 の境界の値：P2 のいちばん良い計算 R18（誘導なし）を同じ場面・同じ値でもう一度計算し、
主役の範囲（とその周り）の水面の SDF（surface）と流速（vel）を、毎コマ、決まった 2 m の升目に写して書き出す（hython）。

使い方: hython p3_export_coarse.py '<JSON>'
JSON: {"run_id": "C18_export", "src_run": ".../P2/R18_X30L120LG_H39/run.json", "f_end": 284, "exp_from": 24,
       "box": [x0, x1, y0, y1, z0, z1]（升の中心の範囲、2 m おき）, "ckpt_every": 96, "wall_limit_s": 1740}
出力: Unity/Build/FLIP37/P3/<run_id>/fields/c_FFFF.bgeo.sc（surface・vel.x/y/z の 4 つの体積、2 m の升目）、
      crest.npy（run_p2 と同じ形の頂の記録。R18 と同じになることの確かめ用）、run.json、runs.jsonl に 1 行。
場面 p2_tank.hiplc は読むだけで保存しない（版 3、R18 と同じ sha256 であることを確かめる）。
"""
import hou, sys, os, json, time, hashlib, ctypes
from ctypes import wintypes
import numpy as np

HIP = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP37/p2_tank.hiplc"
ROOT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37"
args = json.loads(sys.argv[1])
rid = args["run_id"]
OUT = os.path.join(ROOT, "P3", rid).replace("\\", "/")
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


src = json.load(open(args["src_run"], encoding="utf8"))
HIP_SHA = hashlib.sha256(open(HIP, "rb").read()).hexdigest()
if HIP_SHA != src["hip_sha256"]:
    print("WARNING hip sha differs from source run", HIP_SHA, src["hip_sha256"])
hou.hipFile.load(HIP, suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/P2_SETUP/CTRL")
skip = {"copyinput", "cacheinput", "ckpt", "ckpt_on", "ckpt_every", "explicitcachename_eval"}
for k, v in src["parms"].items():
    if k in skip or ctrl.parm(k) is None:
        continue
    ctrl.parm(k).set(v)
ckdir = OUT + "/ckpt"
os.makedirs(ckdir, exist_ok=True)
ctrl.parm("ckpt").set(ckdir)
ctrl.parm("ckpt_on").set(1)
ctrl.parm("ckpt_every").set(int(args.get("ckpt_every", 96)))
hou.setSimulationEnabled(True)
fps = hou.fps()
dop = hou.node("/obj/P2_SIM")

# ---- 書き出しの鎖（記憶の中だけ。保存しない）
x0, x1, y0, y1, z0, z1 = [float(v) for v in args["box"]]
DX = 2.0
geo = hou.node("/obj").createNode("geo", "P3_EXPORT")
for c in geo.children():
    c.destroy()
fi = geo.createNode("dopimportfield::2.0", "fields")
fi.parm("doppath").set("/obj/P2_SIM")
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

f0, f1 = 1, int(args["f_end"])
exp_from = int(args.get("exp_from", 24))
wall_limit = float(args.get("wall_limit_s", 1740))
zbins = np.arange(-120.0, 120.0 + 1e-6, 10.0)
crest, frames, wall, npts, peak = [], [], [], [], []
t_start = time.time()
stopped = None
info = {}
for f in range(f0, f1 + 1):
    t0 = time.time()
    hou.setFrame(f)
    n = -1
    try:
        obj = dop.simulation().findObject("water")
        pg = obj.geometry()
        n = pg.intrinsicValue("pointcount")
        Pp = np.frombuffer(pg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3)
        hi = Pp[:, 1] > 2.0
        Ph = Pp[hi]
        ib = np.clip(np.digitize(Ph[:, 2], zbins) - 1, 0, len(zbins) - 2)
        row = [f, (f - 1) / fps]
        for b in range(len(zbins) - 1):
            m = ib == b
            if m.any():
                k = int(np.argmax(Ph[m, 1]))
                row += [float(Ph[m][k, 1]), float(Ph[m][k, 0])]
            else:
                row += [np.nan, np.nan]
        crest.append(row)
    except Exception as e:
        info.setdefault("particle_errors", []).append(str(e)[:200])
    dt = time.time() - t0
    if f >= exp_from:
        g = outn.geometry()
        if f == exp_from:
            info["export_prims"] = [(p.attribValue("name"), p.resolution()) for p in g.prims()]
        g.saveToFile(FD + "/c_%04d.bgeo.sc" % f)
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
# R18 と同じかの確かめ（頂の高さ）
try:
    rc = np.load(os.path.join(os.path.dirname(args["src_run"]), "crest.npy"))
    mine = np.array(crest)
    common = [int(v) for v in mine[:, 0] if v in set(rc[:, 0].astype(int))]
    dif = []
    for fr in common:
        a = mine[mine[:, 0] == fr][0][2::2]
        b = rc[rc[:, 0] == fr][0][2::3]
        dif.append(np.nanmax(np.abs(a - b)))
    info["crest_maxdiff_vs_src_m"] = float(np.nanmax(dif)) if dif else None
    info["crest_frames_compared"] = len(common)
except Exception as e:
    info["compare_error"] = str(e)[:200]
ck = sorted(os.listdir(ckdir))
rec = {
    "stage": "P3", "run_id": rid, "kind": "coarse_export", "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    "houdini": hou.applicationVersionString(), "hip": HIP, "hip_sha256": HIP_SHA, "src_run": args["src_run"],
    "src_hip_sha256": src["hip_sha256"], "parms": src["parms"], "box": [x0, x1, y0, y1, z0, z1], "dx": DX,
    "f_start": f0, "f_end_req": f1, "f_end_done": frames[-1] if frames else None, "exp_from": exp_from, "fps": fps,
    "particles_max": max(npts) if npts else None, "wall_total_s": round(time.time() - t_start, 1),
    "wall_per_frame_median_s": round(float(np.median(wall[1:])), 3) if len(wall) > 1 else None,
    "rss_peak_gb": round(max(peak), 2) if peak else None, "ckpt_files": len(ck),
    "stopped": stopped, "info": info, "concurrent_with": args.get("concurrent_with"), "note": args.get("note", ""),
}
json.dump(rec, open(OUT + "/run.json", "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
with open(os.path.join(ROOT, "runs.jsonl"), "a", encoding="utf8") as fh:
    fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
print("DONE", json.dumps({k: rec[k] for k in ("run_id", "f_end_done", "wall_total_s", "stopped")}), json.dumps(info, default=str)[:500])
