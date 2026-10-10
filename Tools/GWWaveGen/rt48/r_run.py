# -*- coding: utf-8 -*-
"""RT48（計画 Unity/Build/RT48/plan/plan_ja.md §2.2）：FLIP42 R3 を途中保存から計算し直し、粒子の位置を毎コマ書き出す（hython で実行）。
Tools/GWWaveGen/flip42/g_run.py（変えていない）を写して直した。変えたのは次の 2 点だけで、計算の中身（場面・値・解き方）は変えていない：
  1. 出力先：Unity/Build/RT48/rerun/<run_id>/（runs.jsonl も Unity/Build/RT48/rerun/ に書く）。
  2. 毎コマ、計算が終わった後に粒子の位置を読み、範囲で選んで書き出す（読むだけ。g_run.py も同じ物の点の数と小刻みの数を読んでいる）：
     particles/p_FFFF.npy  float32 (n, 3)、場面の座標（x は造波板の位置 x_p を引いていない、y は解く格子の座標、z は板の厚さ）。
       範囲：x_p + 99 m ≤ x ≤ x_p + 926 m、y > 0.116838 − 8.5 m（静かな水面から 8 m 下に、面を作る半径 0.5 m を足した所）、z は全部。
     粒子の半径 pscale がコマの中で全部同じ時は値だけを記録し、違う時は particles/r_FFFF.npy（float32 (n,)）にも書く。
     同じコマを二度書く時（起動が時間で止まり、途中保存から続けた時）は、前のファイルを残して SHA-256 を比べ、違えば _dup を付けて書く。
     各起動の記録 pexp_cXXXX.json：コマごとの粒子の数・半径・書き出しの秒・SHA-256。FLIP の物体の半径の値（particlesep・radiusscale など）。
  hf_cXXXX.npz に wall_exp（1 コマの書き出しの秒）を足した（ほかの中身と名前は g_run.py と同じ）。
以下は g_run.py の説明のまま。
FLIP42：集まる波の群の断面の水槽の計算を 1 回（1 起動）走らせて、記録を残す（hython で実行）。
FLIP41 の v_run.py（変えていない）を写して直した。足した所：板の真ん中の断面の水面の場（符号付き距離）と、各コマの小刻みの数。

使い方: hython g_run.py '<JSON>'
JSON: {"run_id": "...", "parms": {CTRL の値}, "solver": {"veltransfer": "apic", "donarrowband": 0|1},
       "f_start": 1, "f_end": 4508, "ckpt_on": 1, "ckpt_every": 240, "wall_limit_s": 1740, "level_guard_m": 1.0,
       "sec": {"x0": 場面の x, "x1": 場面の x, "t0": 秒}, "note": "..."}
出力: Unity/Build/FLIP42/runs/<run_id>/
  hf_cXXXX.npz   一番上の水面の高さ eta（コマ, z の節, x の節、float32）、x、z、t、frames、wall（1 コマの秒）、npts、lvl、
                 ss_n（そのコマの小刻みの数）、ss_dt（最後の小刻みの長さ）
  sec_cXXXX_bYYYY.npz  板の真ん中（z = 0 に最も近い節）の水面の場 sdf（コマ, y, x、float16、±8 m で切る）、x0・dx・y0・dy・frames・t
                 （YYYY は塊の最初のコマ。120 コマごとに書き出す）
  run_cXXXX.json 条件と記録（起動ごと）。run.json（最初の起動）。runs.jsonl にも 1 行足す。
見張り：水面の平均が始めより level_guard_m 下がったら止める（圧力が解けない失敗。FLIP41 と同じ）。
"""
import hou, sys, os, json, time, hashlib, ctypes
from ctypes import wintypes
import numpy as np

HIP = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP42/g_tank.hiplc"
ROOT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48/rerun"
args = json.loads(sys.argv[1])
rid = args["run_id"]
OUT = os.path.join(ROOT, rid).replace("\\", "/")
os.makedirs(OUT, exist_ok=True)
PDIR = os.path.join(OUT, "particles").replace("\\", "/")
os.makedirs(PDIR, exist_ok=True)
PEXP = args.get("pexp") or {"x_rel": [99.0, 926.0], "y_min": 0.116838239133358 - 8.5}


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
ctrl = hou.node("/obj/G_SETUP/CTRL")
for k, v in args.get("parms", {}).items():
    ctrl.parm(k).set(v)
fs = hou.node("/obj/G_SIM/flipsolver")
sv = args.get("solver", {})
fs.parm("veltransfer").set(sv.get("veltransfer", "apic"))
fs.parm("donarrowband").set(int(sv.get("donarrowband", 1)))
for _k, _v in sv.items():   # そのほかの解き方の設定（2026-10-10：R4 の圧力の前処理を多重格子にするため）
    if _k not in ("veltransfer", "donarrowband"):
        fs.parm(_k).set(_v)
f0, f1 = int(args["f_start"]), int(args["f_end"])
ckdir = os.path.join(OUT, "ckpt").replace("\\", "/")
os.makedirs(ckdir, exist_ok=True)
ctrl.parm("ckpt").set(ckdir)
ctrl.parm("ckpt_on").set(int(args.get("ckpt_on", 1)))
ctrl.parm("ckpt_every").set(int(args.get("ckpt_every", 240)))
hou.setSimulationEnabled(True)
fps = hou.fps()
dop = hou.node("/obj/G_SIM")
fi = hou.node("/obj/G_READ/surface_field")
wall_limit = float(args.get("wall_limit_s", 1740))
lvl_guard = float(args.get("level_guard_m", 1.0))
P = {p.name(): p.eval() for p in ctrl.parms()}
Lz = float(P["Lz"]); Lx = float(P["Lx"])
VOX = float(P["dp"]) * float(P["gridscale"])
FX = np.arange(0.0, Lx + 1e-6, VOX)
FZ = np.arange(-0.5 * Lz, 0.5 * Lz + 1e-6, VOX)
SEC = args.get("sec") or {}
SEC_BLOCK = 120

frames, wall, npts, tsim, lvls, hfs, ssn, ssdt = [], [], [], [], [], [], [], []
sec_buf, sec_fr, sec_meta = [], [], None
info = {}
solver_parms = {n: fs.parm(n).eval() for n in ("minimumsubsteps", "substeps", "cflcond", "partcflcond", "donarrowband", "narrowbandwidth", "veltransfer", "usepreconditioner", "usemgpreconditioner")}


def flush_sec():
    global sec_buf, sec_fr
    if not sec_buf:
        return
    np.savez_compressed(os.path.join(OUT, "sec_c%04d_b%04d.npz" % (f0, sec_fr[0])), sdf=np.array(sec_buf, np.float16),
                        frames=np.array(sec_fr), t=(np.array(sec_fr) - 1) / fps, meta=json.dumps(sec_meta))
    sec_buf, sec_fr = [], []


def save():
    np.savez_compressed(os.path.join(OUT, "hf_c%04d.npz" % f0), eta=np.array(hfs, np.float32), x=FX, z=FZ,
                        frames=np.array(frames), t=np.array(tsim), wall=np.array(wall), npts=np.array(npts), lvl=np.array(lvls),
                        ss_n=np.array(ssn), ss_dt=np.array(ssdt), grid=json.dumps(grid_info), wall_exp=np.array(wexp))


# ---- RT48：粒子の書き出し（読むだけ）
import io
XP_ = float(P["x_p"])
PX0 = XP_ + float(PEXP["x_rel"][0]); PX1 = XP_ + float(PEXP["x_rel"][1]); PY0 = float(PEXP["y_min"])
wexp, pexp_rows = [], []


def flip_radius_parms():
    out = {}
    fo = hou.node("/obj/G_SIM/water")
    for p in fo.parms():
        nm = p.name()
        if any(k in nm.lower() for k in ("radius", "sep", "scale")):
            try:
                out[nm] = p.eval()
            except Exception:
                pass
    return out


def _sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def _sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def _write_once(path, arr):
    """前のファイルがあれば残して比べる。返り値：(sha256, 状態 'new'|'same'|'dup')"""
    bio = io.BytesIO()
    np.save(bio, arr)
    b = bio.getvalue()
    s = _sha_bytes(b)
    if os.path.exists(path):
        if _sha_file(path) == s:
            return s, "same"
        path = path[:-4] + "_dup%d.npy" % int(time.time())
        st = "dup"
    else:
        st = "new"
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(b)
    os.replace(tmp, path)
    return s, st


def export_particles(f, wg):
    te = time.time()
    Pp = np.frombuffer(wg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3)
    m = (Pp[:, 0] >= PX0) & (Pp[:, 0] <= PX1) & (Pp[:, 1] > PY0)
    sel = np.ascontiguousarray(Pp[m])
    row = {"frame": f, "n_all": int(len(Pp)), "n": int(len(sel))}
    if wg.findPointAttrib("pscale") is not None:
        r = np.frombuffer(wg.pointFloatAttribValuesAsString("pscale"), dtype=np.float32)
        rs = r[m]
        row["pscale_min"] = float(rs.min()) if len(rs) else None
        row["pscale_max"] = float(rs.max()) if len(rs) else None
        if len(rs) and rs.min() != rs.max():
            row["r_sha256"], row["r_state"] = _write_once(os.path.join(PDIR, "r_%04d.npy" % f), np.ascontiguousarray(rs))
    else:
        row["pscale_min"] = row["pscale_max"] = None
    row["sha256"], row["state"] = _write_once(os.path.join(PDIR, "p_%04d.npy" % f), sel)
    row["sec"] = round(time.time() - te, 3)
    return row


t_start = time.time()
stopped = None
lvl0 = None
grid_info = None
for f in range(f0, f1 + 1):
    t0 = time.time()
    hou.setFrame(f)
    g = fi.geometry()
    dt = time.time() - t0
    if g is None:   # 2026-10-10：R4 の 2 コマ目で圧力が解けず水面の場が作られなかった時に、記録を残して止まるようにした
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
    # 断面の水面の場（板の真ん中、z = 0 に最も近い節）
    if SEC and tnow >= float(SEC["t0"]) - 1e-9:
        iz0 = int(np.argmin(np.abs(zs)))
        ix0 = int(np.searchsorted(xs, float(SEC["x0"])))
        ix1 = int(np.searchsorted(xs, float(SEC["x1"])))
        if sec_meta is None or sec_meta["res"] != [nx, ny, nz]:
            flush_sec()
            sec_meta = {"res": [nx, ny, nz], "iz": iz0, "z": float(zs[iz0]), "x0": float(xs[ix0]), "dx": float(xs[1] - xs[0]),
                        "nx": ix1 - ix0, "y0": float(y_c[0]), "dy": float(dy), "ny": int(ny), "clip_m": 8.0}
        sec_buf.append(np.clip(a[iz0, :, ix0:ix1], -8.0, 8.0).astype(np.float16))
        sec_fr.append(f)
        if len(sec_buf) >= SEC_BLOCK:
            flush_sec()
    n = -1; sn = -1; sd = -1.0
    try:
        wg = dop.simulation().findObject("water").geometry()
        if f % 24 == 0 or f == f0 or f == f1:
            n = wg.intrinsicValue("pointcount")
        if wg.findGlobalAttrib("ss_n") is not None:
            sn = int(wg.attribValue("ss_n")); sd = float(wg.attribValue("ss_dt"))
    except Exception as e:
        if len(info.get("geo_errors", [])) < 5:
            info.setdefault("geo_errors", []).append(str(e)[:200])
    # RT48：粒子の位置の書き出し（失敗したら記録して止める。粒子のない計算し直しは目的に合わないため）
    try:
        prow = export_particles(f, dop.simulation().findObject("water").geometry())
        pexp_rows.append(prow); wexp.append(prow["sec"])
    except Exception as e:
        info["error"] = "particle export failed at frame %d: %s" % (f, str(e)[:300])
        stopped = "error"
        wexp.append(-1.0)
        frames.append(f); wall.append(dt); npts.append(n); tsim.append(tnow); lvls.append(-999.0); ssn.append(sn); ssdt.append(sd)
        break
    r, pk = rss_gb()
    mid = E2[:, (FX > 0.2 * Lx) & (FX < 0.6 * Lx)]
    lvl = float(np.nanmean(mid)) if np.isfinite(mid).any() else -999.0
    frames.append(f); wall.append(dt); npts.append(n); tsim.append(tnow); lvls.append(lvl); ssn.append(sn); ssdt.append(sd)
    if lvl0 is None:
        lvl0 = lvl
    if f % 48 == 0 or f == f0:
        print("f=%d t=%.2f sim=%.2fs pts=%d sub=%d rss=%.2fGB lvl=%.3f eta_min=%.2f eta_max=%.2f" % (
            f, tnow, dt, n, sn, r, lvl, np.nanmin(E2), np.nanmax(E2)))
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

save()
flush_sec()
wall_total = time.time() - t_start
ck = sorted(os.listdir(ckdir)) if os.path.isdir(ckdir) else []
ck_bytes = sum(os.path.getsize(os.path.join(ckdir, x)) for x in ck)
nn = [v for v in npts if v >= 0]
ss_ok = [v for v in ssn if v >= 0]
rec = {
    "stage": "FLIP42", "run_id": rid, "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    "houdini": hou.applicationVersionString(), "hip": HIP, "hip_sha256": HIP_SHA,
    "parms": {k: P[k] for k in P}, "solver": sv, "solver_parms": solver_parms, "case": args.get("case", {}), "sec": SEC,
    "f_start": f0, "f_end_req": f1, "f_end_done": frames[-1] if frames else None, "fps": fps,
    "ckpt_dir": ckdir, "ckpt_files": len(ck), "ckpt_gb": round(ck_bytes / 2**30, 3),
    "particles_first": nn[0] if nn else None, "particles_max": max(nn) if nn else None,
    "wall_total_s": round(wall_total, 1), "wall_launch_s": round(time.time() - t_launch, 1),
    "wall_per_frame_median_s": round(float(np.median(wall[1:])) if len(wall) > 1 else 0, 3),
    "substeps_min_max": [min(ss_ok), max(ss_ok)] if ss_ok else None,
    "substeps_hist": {str(v): int(ss_ok.count(v)) for v in sorted(set(ss_ok))},
    "rss_peak_gb": round(rss_gb()[1], 2),
    "level_start_m": lvl0, "level_min_m": float(np.min(lvls)) if lvls else None,
    "stopped": stopped, "info": info, "note": args.get("note", ""), "grid": grid_info,
}
# RT48：粒子の書き出しの記録
_pr = {"run_id": rid, "f_start": f0, "date": rec["date"], "range": {"x_scene": [PX0, PX1], "y_min_solver": PY0, "x_rel": PEXP["x_rel"]},
       "flip_object_parms": flip_radius_parms(), "rows": pexp_rows}
json.dump(_pr, open(os.path.join(OUT, "pexp_c%04d.json" % f0), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
rec["stage"] = "RT48-rerun"
rec["pexp"] = {"frames": len(pexp_rows), "n_min_max": [min(r["n"] for r in pexp_rows), max(r["n"] for r in pexp_rows)] if pexp_rows else None,
               "states": {s: sum(1 for r in pexp_rows if r["state"] == s) for s in ("new", "same", "dup")},
               "sec_median": float(np.median([r["sec"] for r in pexp_rows])) if pexp_rows else None,
               "pscale": [list(v) for v in list(set((r["pscale_min"], r["pscale_max"]) for r in pexp_rows))[:5]], "flip_object_parms": _pr["flip_object_parms"]}
json.dump(rec, open(os.path.join(OUT, "run_c%04d.json" % f0), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
if f0 == 1:
    json.dump(rec, open(os.path.join(OUT, "run.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
with open(os.path.join(ROOT, "runs.jsonl"), "a", encoding="utf8") as fh:
    fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
print("DONE", json.dumps({k: rec[k] for k in ("run_id", "f_end_done", "wall_total_s", "particles_max", "rss_peak_gb", "substeps_min_max", "stopped")}))
