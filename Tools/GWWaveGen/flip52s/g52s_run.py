# -*- coding: utf-8 -*-
"""FLIP52S plan DFG-S: run one launch of a FLIP52S calculation and write its records (hython; started by g52s_chain.py).
GENERATED 2026-10-18 by flip52s/g52s_mkcopy.py from flip52/g52_run.py (sha256 282b21e393e3ecfabb4c3774c29b60b40bccd16491519bb7e996abd51db6e17b, not edited) by exact, counted string replacements:
  - constants and paths from flip52s/g52s_common.py (Build/FLIP52S, Houdini/FLIP52S/g52s_tank.hiplc, the DFG-S level regions);
    the N-layer numpy mirror is flip52/g52_table.py (generic); record stage "FLIP52S"; message 'x52s_build.py'.
Everything else is the FLIP52 run loop (= the FLIP50 one that ran DM1A / DF1A / plan E, with the N-layer OUT_DIRTAB check) that ran DFG-2.
usage: hython g52s_run.py <cfg.json>  (normally py -3.10 g52s_chain.py <cfg.json>)
output: Unity/Build/FLIP52S/<out_root>/<run_id>/  (cfg out_root is an absolute FLIP52S folder)
"""
import hou, sys, os, json, time, hashlib, glob, struct, math
import numpy as np

sys.dont_write_bytecode = True
TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52s"
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52")
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip48")
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip49")
sys.path.insert(0, TOOLS)
import g52s_common as GC
import g52_table as TB

HIP = GC.HIP
a1 = sys.argv[1]
args = json.load(open(a1, encoding="utf8"))
rid = args["run_id"]
ROOT = os.path.join(GC.B52S, args.get("out_root", "runs")).replace("\\", "/")
OUT = os.path.join(ROOT, rid).replace("\\", "/")
os.makedirs(OUT, exist_ok=True)
f0, f1 = int(args["f_start"]), int(args["f_end"])
PRIO = GC.unthrottle_self()
print("priority", PRIO); sys.stdout.flush()


def write_rec(rec):
    json.dump(rec, open(os.path.join(OUT, "run_c%05d.json" % f0), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
    if f0 == int(args.get("f_first", 1)):
        json.dump(rec, open(os.path.join(OUT, "run.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
    with open(os.path.join(ROOT, "runs.jsonl"), "a", encoding="utf8") as fh:
        fh.write(json.dumps({k: rec.get(k) for k in ("run_id", "date", "f_start", "f_end_done", "wall_total_s", "particles_max",
                                                      "rss_peak_gb", "substeps_min_max", "stopped")}, ensure_ascii=False, default=str) + "\n")


def stop_early(why):
    rec = dict(stage="FLIP52S", run_id=rid, date=time.strftime("%Y-%m-%d %H:%M:%S"), f_start=f0, f_end_req=f1, f_end_done=None, stopped=why, priority=PRIO)
    write_rec(rec)
    print("DONE", json.dumps({"run_id": rid, "stopped": why}, ensure_ascii=False))
    sys.exit(0)


# ---------------------------------------------------------------- 置き場所の見張り
free = GC.free_gb("G:/")
disk_stop = float(args.get("disk_stop_free_gb", 25.0))
if free < disk_stop:
    stop_early("disk: G: free %.1f GB < %.1f GB（利用者に伺う）" % (free, disk_stop))

t_launch = time.time()
HIP_SHA = GC.sha256_file(HIP)
hou.hipFile.load(HIP, suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/G52_SETUP/CTRL")
for k, v in args.get("parms", {}).items():
    if ctrl.parm(k) is None:
        stop_early("error: CTRL に %s がない（場面 %s が古い。x52s_build.py で作り直す）" % (k, HIP))
    ctrl.parm(k).set(v)

# ---------------------------------------------------------------- 流れ関数の表（cfg の sf → CTRL の sf_tab）
SFINFO = None
SF = args.get("sf")
SF_ON = float(ctrl.parm("sf_on").eval()) > 0.5
if SF_ON and (not SF or SF.get("descriptor")):
    stop_early("error: sf_on 1 needs a Fenton table in cfg sf (not the linear descriptor)")
if SF and not SF.get("descriptor"):
    if SF_ON and abs(float(SF["h"]) - float(ctrl.parm("h0").eval())) > 1e-9:
        stop_early("error: Fenton depth sf.h %r differs from h0 %r" % (SF["h"], ctrl.parm("h0").eval()))
    ctrl.parm("sf_tab").set(GC.sf_tab_string(SF))
    _sg = hou.node("/obj/G52_SETUP/OUT_SF").geometry()
    SFINFO = {a_.name(): _sg.attribValue(a_.name()) for a_ in _sg.globalAttribs() if a_.name() in ("sfh", "sfk", "sfc", "sfUb", "sfN")}
    if int(SFINFO.get("sfN", -1)) != len(SF["B"]):
        stop_early("error: OUT_SF の sfN %r が cfg の B の数 %d と合わない" % (SFINFO.get("sfN"), len(SF["B"])))
    _B = _sg.attribValue("sfB"); _E = _sg.attribValue("sfE")
    SFINFO["max_abs_diff_B"] = float(max(abs(a_ - b_) for a_, b_ in zip(_B, SF["B"])))
    SFINFO["max_abs_diff_E"] = float(max(abs(a_ - b_) for a_, b_ in zip(_E, SF["E"])))
    SFINFO["T"] = SF.get("T"); SFINFO["H"] = SF.get("H")

# ---------------------------------------------------------------- FLIP50: directional table (cfg dir -> CTRL dir_npz -> OUT_DIRTAB)
DIRINFO = None
DTAB = None
DIR = args.get("dir")
DIR_ON = float(ctrl.parm("dir_on").eval()) > 0.5
if DIR_ON and not DIR:
    stop_early("error: dir_on 1 but the cfg has no dir (table)")
if DIR:
    _np = DIR["npz"]
    if not os.path.exists(_np):
        stop_early("error: directional table %s is missing" % _np)
    _sha = GC.sha256_file(_np)
    if _sha != DIR.get("npz_sha256"):
        stop_early("error: directional table sha256 %s differs from the cfg %s" % (_sha[:16], str(DIR.get("npz_sha256"))[:16]))
    ctrl.parm("dir_npz").set(_np)
    _dg = hou.node("/obj/G52_SETUP/OUT_DIRTAB").geometry()
    DIRINFO = {nm: _dg.attribValue(nm) for nm in ("d_P", "d_nlayer", "d_n0", "d_n1", "d_n2", "d_n3", "d_om0", "d_om1", "d_om2", "d_om3",
                                                  "d_x0", "d_x1", "d_y0", "d_y1", "d_tf", "d_nfield", "d_content", "d_src")}
    DTAB = TB.load(_np)
    # FLIP52: the N-layer table (d_nlayer, d_P, d_n<n>, d_tf are exact float32 detail attributes; see g52_tanklib.PYSOP_DIRTAB52)
    _I = DTAB["info"]
    _nl = int(_I["n_layers"])
    _bad = []
    if int(DIRINFO["d_nfield"]) != len(_I["fields"]):
        _bad.append("d_nfield")
    if int(round(float(DIRINFO["d_nlayer"]))) != _nl or _nl != int(DIR.get("n_layers", -1)):
        _bad.append("d_nlayer")
    if float(DIRINFO["d_P"]) != float(DIR["P"]) or float(_I["P"]) != float(DIR["P"]):
        _bad.append("d_P")
    if any(float(DIRINFO["d_n%d" % _n]) != float(DIR["harmonics"][_n]) for _n in range(_nl)):
        _bad.append("d_n")
    if float(DIRINFO["d_tf"]) != float(_I["t_f"]) or abs(float(ctrl.parm("dir_tf").eval()) - float(DIR["t_f"])) > 1e-12:
        _bad.append("t_f")
    if DIRINFO["d_content"] != DIR.get("content_sha256"):
        _bad.append("content")
    if _bad:
        stop_early("error: OUT_DIRTAB does not match the cfg table (%s): %s" % (",".join(_bad), DIRINFO))
    DIRINFO.update(npz=_np, npz_sha256=_sha, P=float(DIR["P"]), harmonics=DIR.get("harmonics"), set=DIR.get("set"))

fs = hou.node("/obj/G52_SIM/flipsolver")
sv = args.get("solver", {})
fs.parm("veltransfer").set(sv.get("veltransfer", "flip"))
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
dop = hou.node("/obj/G52_SIM")
fi = hou.node("/obj/G52_READ/surface_field")
fv = hou.node("/obj/G52_READ/vel_field")
P = {p.name(): p.eval() for p in ctrl.parms()}
T_OFF = float(P["t_off"])
VOX = float(P["dp"]) * float(P["gridscale"])
X0, LX, W = float(P["x0"]), float(P["Lx"]), float(P["W"])
OX, OY, OZ = float(P.get("ox", 0.0)), float(P.get("oy", 0.0)), float(P.get("oz", 0.0))
O3 = np.array([OX, OY, OZ])
wall_limit = float(args.get("wall_limit_s", 1740))
lvl_guard = float(args.get("level_guard_m", GC.LEVEL_GUARD_M))
REC = args.get("records", {})
R3Z = REC.get("r3_z")
R4 = REC.get("r4")
R5 = REC.get("r5")
WINS = [[float(a), float(b)] for a, b in (REC.get("windows") or [])]
BLOCK = int(REC.get("block", 120))
R4BLOCK = int(REC.get("r4_block", 24))
FB_FRAMES = set(int(v) for v in args.get("fieldbox_frames", []))
PS_FRAMES = set(int(v) for v in args.get("pstats_frames", []))
LVL_BOX = args.get("level_box") or [X0, X0 + LX, 0.0, W]
REGIONS = ["all", "flat", "ridge_inner", "ridge_outer", "shore"]
RX0 = float(P["ridge_x0"]); XSH = float(args.get("shore_x", 256.0)); ZHALF = 0.5 * W
BED = GC.bed_spec(parms=P)
PREG_EVERY = int(REC.get("preg_every", 24))
LREG = [tuple(r) for r in (args.get("level_regions") or GC.LEVEL_REGIONS_52S)]
GX = [float(v) for v in (args.get("gauges", {}).get("x") or GC.GAUGE_X)]
GY = [float(v) for v in (args.get("gauges", {}).get("y") or GC.GAUGE_Y)]
SFC = args.get("sf_check") or {}
T_WAVE = float((SF or {}).get("T", GC.T_WAVE))
NT = max(1, int(round(T_WAVE * fps)))


def in_win(t):
    return (not WINS) or any(a - 1e-9 <= t <= b + 1e-9 for a, b in WINS)


def region_index(x, zl):
    return np.where(x < RX0, 0, np.where(x >= XSH, 3, np.where(zl >= ZHALF, 2, 1)))


def region_means(vals, x, zl, count=False):
    rid_ = region_index(x[None, :], zl[:, None])
    out = [float(np.nansum(vals)) if count else (float(np.nanmean(vals)) if np.isfinite(vals).any() else float("nan"))]
    for k in range(4):
        v = vals[rid_ == k]
        if count:
            out.append(float(np.nansum(v)))
        else:
            out.append(float(np.nanmean(v)) if v.size and np.isfinite(v).any() else float("nan"))
    return out


def particle_regions(wg):
    Pp = np.frombuffer(wg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3)
    x = Pp[:, 0] - np.float32(OX); zl = Pp[:, 2] - np.float32(OZ)
    c = np.bincount(region_index(x, zl), minlength=4)
    return [int(len(Pp))] + [int(v) for v in c[:4]]


def tnow_of(f):
    return T_OFF + (f - 1) / fps


# 静かな水面のずれ（N1）：t ∈ n1_window の一番上の水面の中央値（x ∈ n1_x）。前の起動の値を引き継ぐ
OFF_GIVEN = args.get("still_offset_m")
N1_X = args.get("n1_x") or [GC.VOL_X[0], GC.VOL_X[1]]
N1_WIN = args.get("n1_window") or [0.5, 1.5]
OFF = float(OFF_GIVEN) if OFF_GIVEN is not None else None
OFF_SRC = "cfg" if OFF_GIVEN is not None else None
n1_vals = []
if OFF is None:
    for _p in sorted(glob.glob(os.path.join(OUT, "run_c*.json"))):
        try:
            _r = json.load(open(_p, encoding="utf8"))
        except Exception:
            continue
        _o = (_r.get("info") or {}).get("still_offset_online")
        if _o is not None and _o.get("value") is not None and int(_r.get("f_start") or 0) < f0:
            OFF = float(_o["value"]); OFF_SRC = "restored from run_c%05d" % int(_r.get("f_start"))

FI = {}
if FB_FRAMES:
    rdn = hou.node("/obj").createNode("geo", "G52_FIELDS")
    for c in rdn.children():
        c.destroy()
    for nm in ["surface", "pressure", "vel", "collision", "collisionweights", "massdensity", "divergence"]:
        q = rdn.createNode("dopimportfield::2.0", "f_" + nm)
        q.parm("doppath").set("/obj/G52_SIM")
        q.parm("fields").set(1)
        q.parm("objname1").set("water")
        q.parm("fieldname1").set(nm)
        FI[nm] = q


def fieldbox():
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
            try:
                vn = v.attribValue("name")
            except Exception:
                vn = None
            out[nm].append(dict(name=vn, res=list(r), p0=[repr(c) for c in p0], d=[repr(p1[j] - p0[j]) for j in range(3)],
                                bmin=[repr(c) for c in bb.minvec()], bmax=[repr(c) for c in bb.maxvec()]))
    return out


def bed_leak(Pp):
    gap = Pp[:, 1] - GC.bed_z(Pp[:, 0], Pp[:, 2], **BED)
    return dict(n_below_bed=int((gap < -0.25 * VOX).sum()), gap_min=float(gap.min()) if len(gap) else None)


def pstats(wg):
    Pp = np.frombuffer(wg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - O3
    V = np.frombuffer(wg.pointFloatAttribValuesAsString("v"), dtype=np.float32).reshape(-1, 3)
    mid = (Pp[:, 0] > X0 + 0.2 * LX) & (Pp[:, 0] < X0 + 0.8 * LX)
    sp = np.sqrt((V.astype(np.float64) ** 2).sum(1)); im = int(np.argmax(sp))
    return dict(n=int(len(Pp)), vy_mean_mid=float(V[mid, 1].mean()), vy_absmean_mid=float(np.abs(V[mid, 1]).mean()),
                speed_max=float(sp[im]), speed_max_at=[float(c) for c in Pp[im]], n_speed_gt_0p1=int((sp > 0.1).sum()),
                ymax_mid=float(Pp[mid, 1].max()), ymin_all=float(Pp[:, 1].min()), zmin_all=float(Pp[:, 2].min()), **bed_leak(Pp))


def vol_arr(v):
    r = v.resolution()
    return np.frombuffer(v.allVoxelsAsString(), dtype=np.float32).reshape(r[2], r[1], r[0])


def vol_meta(v, plan=True):
    r = v.resolution(); p0 = v.indexToPos((0, 0, 0)); p1 = v.indexToPos((1, 1, 1))
    q = [float(c) for c in p0]
    if plan:
        q = [q[0] - OX, q[1] - OY, q[2] - OZ]
    return dict(res=list(r), p0=q, d=[float(p1[j] - p0[j]) for j in range(3)])


def zslice(v, z):
    m = vol_meta(v)
    fz = (z - m["p0"][2]) / m["d"][2]
    k0 = int(np.floor(fz + 1e-9)); w = fz - k0
    nz = m["res"][2]
    k0 = max(0, min(nz - 1, k0))

    def sl(k):
        try:
            b = v.voxelSliceAsString("xy", k)
            return np.frombuffer(b, dtype=np.float32).reshape(m["res"][1], m["res"][0])
        except Exception:
            return vol_arr(v)[k]
    if abs(w) < 1e-6 or k0 + 1 >= nz:
        return sl(k0).copy(), dict(m, k=[k0], z=m["p0"][2] + k0 * m["d"][2])
    return (0.5 * (sl(k0) + sl(k0 + 1)) if abs(w - 0.5) < 1e-6 else (1 - w) * sl(k0) + w * sl(k0 + 1)), dict(m, k=[k0, k0 + 1], w=w, z=z)


def vel_comps():
    vg = fv.geometry()
    vv = {}
    if vg is not None:
        for p in vg.prims():
            if p.type() in (hou.primType.Volume, hou.primType.VDB):
                try:
                    vv[p.attribValue("name")] = p
                except Exception:
                    pass
    return vv


def sf_check(f, tnow, vv):
    """帯の中の点の格子の流速と目標（numpy の g50_common.sf_target（flip49 の関数をそのまま）。E は場面の値で）。"""
    out = dict(frame=int(f), t=float(tnow), rows=[])
    for x in SFC.get("x", []):
        for y in SFC.get("y", []):
            for zl in SFC.get("zl", [0.5 * VOX]):
                eE, uE, wE, eta, E = GC.sf_target(float(x), float(y), float(tnow), SF, P)
                r = dict(x=float(x), y=float(y), zl=float(zl), E=float(E.ravel()[0]), u_tgt=float(uE.ravel()[0]), w_tgt=float(wE.ravel()[0]),
                         eta_tgt=float(eE.ravel()[0]))
                hp = hou.Vector3(float(x) + OX, float(y) + OY, float(zl) + OZ)
                for nm, key in (("vel.x", "u_grid"), ("vel.y", "w_grid"), ("vel.z", "v_grid")):
                    r[key] = float(vv[nm].sample(hp)) if nm in vv else None
                out["rows"].append(r)
    return out


DC = args.get("dir_check") or {}


def dir_check(f, tnow, vv):
    """FLIP50: band points, grid velocity against the numpy target (band factor x directional table; recorded only)."""
    out = dict(frame=int(f), t=float(tnow), rows=[])
    for x in DC.get("x", []):
        for y in DC.get("y", []):
            for zl in DC.get("zl", [0.5 * VOX]):
                wdt, ftg, inb, insd = TB.bands_np(float(x), float(zl), 1.0 / 24.0, P)
                wt, ws = TB.tapers_np(float(x), float(zl), P)
                gm = (P["in_gain"] if inb else P["sd_gain"]) * ftg * wt * ws * TB.rampT(float(tnow), float(P["ramp_s"]))
                e_, U_, V_ = TB.dirwave_np(DTAB, float(x), float(y), float(zl), float(tnow), gm, tf=float(P["dir_tf"]), ret_on=float(P["ret_on"]))
                r = dict(x=float(x), y=float(y), zl=float(zl), g=float(gm), in_band=int(inb), in_side=int(insd), u_tgt=float(U_), v_tgt=float(V_),
                         eta_tgt=float(e_))
                hp = hou.Vector3(float(x) + OX, float(y) + OY, float(zl) + OZ)
                for nm, key in (("vel.x", "u_grid"), ("vel.y", "w_grid"), ("vel.z", "v_grid")):
                    r[key] = float(vv[nm].sample(hp)) if nm in vv else None
                out["rows"].append(r)
    return out


# ---------------------------------------------------------------- 水の量の直し（段 A・B・C）
VC_A = float(P.get("volcorr_on", 0.0)) > 0.5
VC_B = float(P.get("hold_on", 0.0)) > 0.5
VC_C = float(P.get("duabs_on", 0.0)) > 0.5
VC_ON = VC_A or VC_B or VC_C
DRIFT = args.get("drift") or {}
VC = dict(V0=None, Vwin0=None, Lb0=None, Lc0=None, acc=[], I=0.0, cum=0.0, hb=[], hc=[], n=0, ncap=0, src=None)
VDIR = os.path.join(OUT, "volcorr").replace("\\", "/")
os.makedirs(VDIR, exist_ok=True)              # 体積は直しが無くても毎コマ測る（S2：FLIP そのものの吸い込み）。vd のファイルは直しのある時だけ
if True:
    _rp = os.path.join(VDIR, "ref.json")
    if os.path.exists(_rp):
        _ref = json.load(open(_rp, encoding="utf8"))
        for k_ in ("V0", "Vwin0", "Lb0", "Lc0"):
            VC[k_] = _ref.get(k_)
        VC["src"] = "ref.json"
    _sp = os.path.join(VDIR, "state.jsonl")
    if os.path.exists(_sp):
        last = {}
        for ln in open(_sp, encoding="utf8"):
            try:
                q = json.loads(ln)
            except Exception:
                continue
            if int(q["f"]) < f0:
                last[int(q["f"])] = q
        if last:
            fl = max(last)
            VC["I"] = float(last[fl].get("I_B") or 0.0); VC["cum"] = float(last[fl].get("cum") or 0.0)
            ks = sorted(last)[-NT:]
            VC["hb"] = [float(last[k_]["L_band"]) for k_ in ks if last[k_].get("L_band") is not None]
            VC["hc"] = [float(last[k_]["L_probe"]) for k_ in ks if last[k_].get("L_probe") is not None]
            VC["src"] = "%s; state restored from frame %d" % (VC["src"], fl)
if VC_ON:
    ctrl.parm("vol_dir").set(VDIR)
    _f0p = os.path.join(VDIR, "vd_%05d.txt" % f0)
    if not os.path.exists(_f0p):
        open(_f0p, "w").write("0.0 0.0 0.0\n")
VC_MEAS = str(DRIFT.get("V_measure", "sdf"))     # 2026-10-15 S0a の虫探しの後：'column'（一番上の水面の柱の高さ − 海底）か 'sdf'（凍らせた元の読み）
VC_TAU = float(DRIFT.get("tau_s", GC.VOL_TAU)); VC_DMAX = float(DRIFT.get("dmax", GC.VOL_DMAX)); VC_TCAP = float(DRIFT.get("tcap_s", GC.VOL_TCAP))
HB_TI = float(DRIFT.get("hold_ti_s", GC.HOLD_TI)); HB_TAU = float(DRIFT.get("hold_tau_s", T_WAVE)); HB_DMAX = float(DRIFT.get("hold_dmax", GC.VOL_DMAX))
H0P = float(P["h0"])
_mask_cache = {}


def above_mask(xs, y_c, zs):
    key = (len(xs), len(y_c), len(zs), round(float(xs[0]), 6), round(float(y_c[0]), 6), round(float(zs[0]), 6))
    if key not in _mask_cache:
        bed2 = GC.bed_z(xs[None, :], zs[:, None], **BED)                 # [横, x]
        _mask_cache.clear()
        _mask_cache[key] = (y_c[None, :, None] >= bed2[:, None, :])
    return _mask_cache[key]


_bed2_cache = {}


def bed2_of(xs, zs):
    key = (len(xs), len(zs), round(float(xs[0]), 6), round(float(zs[0]), 6))
    if key not in _bed2_cache:
        _bed2_cache.clear()
        _bed2_cache[key] = GC.bed_z(xs[None, :], zs[:, None], **BED)       # [横, x]
    return _bed2_cache[key]


def vc_step(f, tnow, a, xs, y_c, zs, lv, eta=None):
    """毎コマの終わり：V・V_win を測り、次のコマの vol_div・vol_div_band・du_abs をファイルに書き、状態を 1 行残す。
    V の読み（cfg の drift.V_measure）：
      'sdf'    凍らせた元の読み：surface の SDF の重み clamp(0.5 − sdf/格子, 0, 1) を海底より上の格子で足す。
      'column' 2026-10-15 S0a の虫探しの後に足した読み：R1 と同じ一番上の水面 η_top から海底までの柱の高さ max(η_top − z_b, 0) を
               x・横の格子の面積で足す（乾いた柱は 0）。平らな海底の静かな水（帯あり・段 A）で、'sdf' の V は直しの発散を入れると
               上がり続け（直しの量 −112 m³ に柱の量は −19 m³、30 s）、窓の流れが 0.17 m/s まで育った【測定、diag_s0a/DG_S0a_flat_bands_stA】。
               柱の量は水面の高さそのものなので、平均の水面を保つ目的に合う。両方を毎コマ state.jsonl に書く（V_sdf・V_col）。"""
    wv = np.clip(0.5 - a / VOX, 0.0, 1.0) * above_mask(xs, y_c, zs)
    cell = VOX ** 3
    selw = (xs >= float(P["vol_x0"])) & (xs <= float(P["vol_x1"]))
    V_sdf = float(wv.sum()) * cell
    Vw_sdf = float(wv[:, :, selw].sum()) * cell
    V_col = Vw_col = None
    if eta is not None:
        dxc = float(xs[1] - xs[0]) if len(xs) > 1 else VOX; dzc = float(zs[1] - zs[0]) if len(zs) > 1 else VOX
        col = np.nan_to_num(np.clip(eta.astype(np.float64) - bed2_of(xs, zs), 0.0, None), nan=0.0)
        V_col = float(col.sum()) * dxc * dzc
        Vw_col = float(col[:, selw].sum()) * dxc * dzc
    if VC_MEAS == "column":
        if V_col is None:
            raise RuntimeError("drift.V_measure = column なのに η_top が渡されていない")
        V, Vw = V_col, Vw_col
    else:
        V, Vw = V_sdf, Vw_sdf
    Lb = lv.get("band_core"); Lc = lv.get("probe_c")
    tt = tnow - T_OFF
    if VC["V0"] is None:
        if VC_TCAP - 0.5 - 1e-9 <= tt <= VC_TCAP + 1e-9:
            VC["acc"].append((V, Vw, Lb, Lc))
        if tt >= VC_TCAP - 1e-9 and VC["acc"]:
            A_ = np.array([[np.nan if v is None else v for v in r] for r in VC["acc"]], float)
            VC["V0"], VC["Vwin0"], VC["Lb0"], VC["Lc0"] = [float(np.nanmean(A_[:, i])) for i in range(4)]
            VC["src"] = "measured %d frames up to t %.2f s" % (len(VC["acc"]), tnow)
            json.dump(dict(V0=VC["V0"], Vwin0=VC["Vwin0"], Lb0=VC["Lb0"], Lc0=VC["Lc0"], frames=len(VC["acc"]), t_end=tnow, src=VC["src"],
                           note_ja="V0・V_win0・帯の芯の水面・段 C の所の水面の 1.0〜1.5 s の平均（基準）"),
                      open(os.path.join(VDIR, "ref.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
    if Lb is not None and np.isfinite(Lb):
        VC["hb"] = (VC["hb"] + [float(Lb)])[-NT:]
    if Lc is not None and np.isfinite(Lc):
        VC["hc"] = (VC["hc"] + [float(Lc)])[-NT:]
    d = 0.0; cap = False; dband = 0.0; du = 0.0; e_b = None
    if VC["V0"] is not None:
        if VC_A:
            draw = (VC["V0"] - V) / (max(VC["Vwin0"], 1.0) * max(VC_TAU, 1e-3))
            d = float(np.clip(draw, -VC_DMAX, VC_DMAX)); cap = abs(draw) > VC_DMAX
        if VC_B and len(VC["hb"]) >= NT and VC["Lb0"] is not None:
            e_b = VC["Lb0"] - float(np.mean(VC["hb"]))
            In = VC["I"] + e_b / (H0P * HB_TAU * HB_TI) / fps
            if abs(In) <= HB_DMAX or (In > HB_DMAX and In < VC["I"]) or (In < -HB_DMAX and In > VC["I"]):
                VC["I"] = In
            dband = float(np.clip(VC["I"], -HB_DMAX, HB_DMAX))
        if VC_C and VC["hc"] and VC["Lc0"] is not None:
            du = -math.sqrt(GC.G / H0P) * (float(np.mean(VC["hc"])) - VC["Lc0"])
    VC["n"] += 1; VC["ncap"] += int(cap)
    VC["cum"] += (d * (VC["Vwin0"] or 0.0) + dband * 0.0) / fps          # 段 A が足した水の量（m³、半分の水槽）
    if VC_ON:
        open(os.path.join(VDIR, "vd_%05d.txt" % (f + 1)), "w").write("%r %r %r\n" % (d, dband, du))
    row = dict(f=int(f), t=float(tnow), V=V, Vwin=Vw, d=d, cap=bool(cap), I_B=VC["I"], d_band=dband, e_band=e_b, du_abs=du, cum=VC["cum"],
               L_band=Lb, L_probe=Lc, V_measure=VC_MEAS, V_sdf=V_sdf, Vwin_sdf=Vw_sdf, V_col=V_col, Vwin_col=Vw_col)
    with open(os.path.join(VDIR, "state.jsonl"), "a", encoding="utf8") as fh:
        fh.write(json.dumps(row) + "\n")
    return [V, Vw, d, float(cap), VC["I"], dband, du, VC["cum"]]


# ---------------------------------------------------------------- 面（R5）を自作の形で書く（g48 と同じ GW45SRF1）
SURF_DIR = os.path.join(OUT, "surf").replace("\\", "/")
sout = hou.node("/obj/G52_SURF/OUT_SURF")


def oct_encode(n):
    n = n / np.maximum(np.abs(n).sum(1, keepdims=True), 1e-12)
    x, y, z = n[:, 0], n[:, 1], n[:, 2]
    neg = z < 0
    xo = np.where(neg, (1 - np.abs(y)) * np.sign(x + 1e-30), x)
    yo = np.where(neg, (1 - np.abs(x)) * np.sign(y + 1e-30), y)
    return np.round((np.clip(np.stack([xo, yo], 1), -1, 1) * 0.5 + 0.5) * 65535).astype(np.uint16)


HEAD_BYTES = 96


def write_surface(f, tnow, off):
    t0s = time.time()
    g = sout.geometry()
    if g is None:
        return dict(error="no surface geometry")
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
    tri = np.stack([remap[ia], remap[ib], remap[ic]], 1).astype(np.uint32)
    Pu = Pp[used]; Nu = N[used].copy(); Vu = V[used]
    seam = np.abs(Pu[:, 2]) < 1e-4
    Nu[seam, 2] = 0.0
    Nu = Nu / np.maximum(np.linalg.norm(Nu, axis=1, keepdims=True), 1e-12)
    lo = Pu.min(0) if len(Pu) else np.zeros(3); hi = Pu.max(0) if len(Pu) else np.ones(3)
    q = np.round((Pu - lo) / np.maximum(hi - lo, 1e-9) * 65535).astype(np.uint16)
    qerr = float(np.max(np.abs(q.astype(np.float64) / 65535 * (hi - lo) + lo - Pu))) if len(Pu) else 0.0
    head = struct.pack("<8sIIdiIIffffffff", b"GW45SRF1", 1, HEAD_BYTES, float(tnow), int(f), len(Pu), len(tri),
                       *[float(v) for v in lo], *[float(v) for v in hi], float(off), 0.0)
    head = head + b"\0" * (HEAD_BYTES - len(head))
    os.makedirs(SURF_DIR, exist_ok=True)
    p = os.path.join(SURF_DIR, "s_%05d.gw45s" % f)
    with open(p, "wb") as fh:
        fh.write(head); fh.write(q.tobytes()); fh.write(oct_encode(Nu).tobytes()); fh.write(Vu.astype(np.float16).tobytes()); fh.write(tri.tobytes())
    return dict(n_vert=int(len(Pu)), n_tri=int(len(tri)), bytes=os.path.getsize(p), qerr_m=qerr, s=round(time.time() - t0s, 3))


# ---------------------------------------------------------------- 主な繰り返し
buf = dict(hf=[], hff=[], r2=[], r2u=[], r2w=[], r2f=[], r3=[], r3u=[], r3v=[], r3w=[], r3f=[], r4=[], r4f=[])
meta = dict(hf=None, r2=None, r3=None, r4=None)
frames, wall, npts, tsim, lvls, ssn, ssdt, rss_l, surf_s = [], [], [], [], [], [], [], [], []
lvl_reg, liq_reg, preg, lvl49, gauge, volr = [], [], [], [], [], []
info = {"sf_table": SFINFO, "dir_table": DIRINFO, "level_regions": dict(names=REGIONS, ridge_x0=RX0, shore_x=XSH, z_half=ZHALF, preg_every=PREG_EVERY),
        "level49": dict(regions=[list(r) for r in LREG], gauges_x=GX, gauges_y=GY, nT=NT, T=T_WAVE),
        "records_windows": WINS, "drift": dict(DRIFT, V_measure_used=VC_MEAS, A=VC_A, B=VC_B, C=VC_C, tau=VC_TAU, dmax=VC_DMAX, tcap=VC_TCAP, hold_ti=HB_TI,
                                               hold_tau=HB_TAU, hold_dmax=HB_DMAX, restored=VC.get("src"))}
solver_parms = {n: fs.parm(n).eval() for n in ("minimumsubsteps", "substeps", "cflcond", "partcflcond", "donarrowband", "narrowbandwidth",
                                              "veltransfer", "usepreconditioner", "usemgpreconditioner", "dynamicresize", "usewaterline")}
try:
    solver_parms["reseed_parms"] = {q.name(): q.eval() for q in fs.parms()
                                    if any(w in q.name().lower() for w in ("reseed", "birth", "death", "oversamp", "particlesper", "maxgrowth"))}
except Exception as e:
    solver_parms["reseed_parms"] = {"error": str(e)[:200]}


def flush(kind, force=False):
    if kind == "hf" and buf["hf"] and (force or len(buf["hf"]) >= BLOCK):
        np.savez_compressed(os.path.join(OUT, "hf_c%05d_b%05d.npz" % (f0, buf["hff"][0])), eta=np.array(buf["hf"], np.float32),
                            frames=np.array(buf["hff"]), t=np.array([tnow_of(v) for v in buf["hff"]]), meta=json.dumps(meta["hf"]))
        buf["hf"], buf["hff"] = [], []
    if kind == "r2" and buf["r2"] and (force or len(buf["r2"]) >= BLOCK):
        np.savez_compressed(os.path.join(OUT, "r2_c%05d_b%05d.npz" % (f0, buf["r2f"][0])), sdf=np.array(buf["r2"], np.float16),
                            u=np.array(buf["r2u"], np.float16), w=np.array(buf["r2w"], np.float16),
                            frames=np.array(buf["r2f"]), t=np.array([tnow_of(v) for v in buf["r2f"]]), meta=json.dumps(meta["r2"]))
        buf["r2"], buf["r2u"], buf["r2w"], buf["r2f"] = [], [], [], []
    if kind == "r3" and buf["r3"] and (force or len(buf["r3"]) >= BLOCK):
        np.savez_compressed(os.path.join(OUT, "r3_c%05d_b%05d.npz" % (f0, buf["r3f"][0])), sdf=np.array(buf["r3"], np.float16),
                            u=np.array(buf["r3u"], np.float16), v=np.array(buf["r3v"], np.float16), w=np.array(buf["r3w"], np.float16),
                            frames=np.array(buf["r3f"]), t=np.array([tnow_of(v) for v in buf["r3f"]]), meta=json.dumps(meta["r3"]))
        buf["r3"], buf["r3u"], buf["r3v"], buf["r3w"], buf["r3f"] = [], [], [], [], []
    if kind == "r4" and buf["r4"] and (force or len(buf["r4"]) >= R4BLOCK):
        np.savez_compressed(os.path.join(OUT, "r4_c%05d_b%05d.npz" % (f0, buf["r4f"][0])), sdf=np.array(buf["r4"], np.float16),
                            frames=np.array(buf["r4f"]), t=np.array([tnow_of(v) for v in buf["r4f"]]), meta=json.dumps(meta["r4"]))
        buf["r4"], buf["r4f"] = [], []


def save_series():
    np.savez(os.path.join(OUT, "r6_c%05d.npz" % f0), frames=np.array(frames), t=np.array(tsim), wall=np.array(wall), npts=np.array(npts),
             lvl=np.array(lvls), ss_n=np.array(ssn), ss_dt=np.array(ssdt), rss=np.array(rss_l), surf_s=np.array(surf_s),
             lvl_reg=np.array(lvl_reg, dtype=np.float64).reshape(-1, 5), liq_reg=np.array(liq_reg, dtype=np.float64).reshape(-1, 5),
             preg=np.array(preg, dtype=np.int64).reshape(-1, 5), regions=np.array(REGIONS), vox=np.array(VOX),
             lvl49=np.array(lvl49, dtype=np.float64).reshape(-1, len(LREG)), lvl49_names=np.array([r[0] for r in LREG]),
             gauge=np.array(gauge, dtype=np.float64).reshape(-1, len(GX) * len(GY)),
             gauge_xy=np.array([[x_, y_] for y_ in GY for x_ in GX], dtype=np.float64),
             vol=np.array(volr, dtype=np.float64).reshape(-1, 8),
             vol_names=np.array(["V_m3", "Vwin_m3", "vol_div", "cap", "I_B", "vol_div_band", "du_abs", "cum_added_m3"]))


def levels49(eta, xs, zs):
    out = {}
    az = np.abs(zs)
    for nm, xa, xb, ya, yb in LREG:
        sx = (xs >= xa) & (xs <= xb); sz = (az >= ya) & (az <= yb)
        v = eta[np.ix_(sz, sx)]
        out[nm] = float(np.nanmean(v)) if v.size and np.isfinite(v).any() else float("nan")
    return out


def gauges(eta, xs, zs):
    row = []
    for yg in GY:
        jz = int(np.argmin(np.abs(zs - min(yg, float(zs[-1])))))
        e = eta[jz]
        for xg in GX:
            i = int(np.clip(np.searchsorted(xs, xg) - 1, 0, len(xs) - 2))
            w = (xg - xs[i]) / (xs[i + 1] - xs[i])
            row.append(float((1 - w) * e[i] + w * e[i + 1]))
    return row


t_start = time.time()
stopped = None
lvl0 = None
for f in range(f0, f1 + 1):
    t0 = time.time()
    hou.setFrame(f)
    g = fi.geometry()
    dt = time.time() - t0
    tnow = tnow_of(f)
    if g is None:
        info["error"] = "no surface geometry at frame %d; errors=%s" % (f, [str(e)[:300] for e in fi.errors()])
        stopped = "error"; break
    vols = [p for p in g.prims() if p.type() in (hou.primType.Volume, hou.primType.VDB)]
    if not vols:
        info["error"] = "no surface field at frame %d; errors=%s" % (f, [str(e) for e in fi.errors()])
        stopped = "error"; break
    vol = vols[0]
    m = vol_meta(vol)
    nx, ny, nz = m["res"]
    xs = m["p0"][0] + m["d"][0] * np.arange(nx)
    y_c = m["p0"][1] + m["d"][1] * np.arange(ny)
    zs = m["p0"][2] + m["d"][2] * np.arange(nz)
    dy = m["d"][1]
    a = vol_arr(vol)
    izc = int(np.searchsorted(zs, 0.0))
    if izc > 0:
        a = a[izc:]; zs = zs[izc:]; nz = len(zs)
    if meta["hf"] is None or meta["hf"]["res"] != [nx, ny, nz]:
        if meta["hf"] is not None:
            flush("hf", True); flush("r2", True); flush("r3", True); flush("r4", True)
            info.setdefault("res_changes", []).append([f, nx, ny, nz])
            meta["r2"] = meta["r3"] = meta["r4"] = None
        meta["hf"] = dict(res=[nx, ny, nz], x0=float(xs[0]), dx=m["d"][0], z0=float(zs[0]), dz=m["d"][2], y0=float(y_c[0]), dy=dy, t_off=T_OFF)
    # R1：一番上の水面の高さ
    neg = a < 0
    has = neg.any(axis=1)
    jtop = ny - 1 - np.argmax(neg[:, ::-1, :], axis=1)
    jtop = np.clip(jtop, 0, ny - 2)
    iz_, ix_ = np.meshgrid(np.arange(nz), np.arange(nx), indexing="ij")
    vj = a[iz_, jtop, ix_]; vj1 = a[iz_, jtop + 1, ix_]
    frac = np.where(vj1 - vj > 1e-9, -vj / np.maximum(vj1 - vj, 1e-9), 0.0)
    eta = np.where(has, y_c[jtop] + dy * np.clip(frac, 0, 1), np.nan).astype(np.float32)
    buf["hf"].append(eta); buf["hff"].append(f)
    flush("hf")
    # 静かな水面のずれ（N1）
    if OFF_SRC is None or OFF_SRC == "measuring":
        if T_OFF + N1_WIN[0] - 1e-9 <= tnow <= T_OFF + N1_WIN[1] + 1e-9:
            sel = eta[:, (xs >= float(N1_X[0])) & (xs <= float(N1_X[1]))]
            if np.isfinite(sel).any():
                n1_vals.append(float(np.nanmedian(sel)))
            OFF_SRC = "measuring"
        elif tnow > T_OFF + N1_WIN[1] and n1_vals:
            OFF = float(np.median(n1_vals)); OFF_SRC = "online"
            info["still_offset_online"] = dict(value=OFF, n_frames=len(n1_vals), x_range=[float(v) for v in N1_X],
                                               window=[T_OFF + N1_WIN[0], T_OFF + N1_WIN[1]])
    elif OFF_SRC.startswith("restored") and "still_offset_online" not in info:
        info["still_offset_online"] = dict(value=OFF, source=OFF_SRC)
    # R2・R3：断面（水面の場と流速）
    vv = vel_comps()
    comp = [vv.get(k) for k in ("vel.x", "vel.y", "vel.z")]
    if REC.get("r2", True):
        sl = a[0]
        if meta["r2"] is None:
            meta["r2"] = dict(res=[nx, ny, nz], iz=0, z=float(zs[0]), x0=float(xs[0]), dx=m["d"][0], nx=nx, y0=float(y_c[0]), dy=dy, ny=ny,
                              clip_m=8.0, t_off=T_OFF, vel={})
        buf["r2"].append(np.clip(sl, -8.0, 8.0).astype(np.float16))
        for nm, c, key in (("vel.x", comp[0], "r2u"), ("vel.y", comp[1], "r2w")):
            if c is not None:
                s2, mm = zslice(c, float(zs[0]))
                buf[key].append(s2.astype(np.float16))
                meta["r2"]["vel"].setdefault(nm, mm)
            else:
                buf[key].append(np.full(sl.shape, np.nan, np.float16))
                if len(info.setdefault("vel_missing_frames", [])) < 20:
                    info["vel_missing_frames"].append(f)
        buf["r2f"].append(f)
        flush("r2")
    if R3Z is not None:
        s3, m3 = zslice(vol, float(R3Z))
        if meta["r3"] is None:
            meta["r3"] = dict(res=[nx, ny, nz], z=float(R3Z), slice=m3, x0=float(xs[0]), dx=m["d"][0], nx=nx, y0=float(y_c[0]), dy=dy, ny=ny,
                              clip_m=8.0, t_off=T_OFF, vel={})
        buf["r3"].append(np.clip(s3, -8.0, 8.0).astype(np.float16))
        for nm, c, key in (("vel.x", comp[0], "r3u"), ("vel.z", comp[2], "r3v"), ("vel.y", comp[1], "r3w")):
            if c is not None:
                s2, mm = zslice(c, float(R3Z))
                buf[key].append(s2.astype(np.float16))
                meta["r3"]["vel"].setdefault(nm, mm)
            else:
                buf[key].append(np.full(s3.shape, np.nan, np.float16))
        buf["r3f"].append(f)
        flush("r3")
    # R4：水面の狭い帯の SDF（3D）。重い記録：records.windows の中だけ。2026-10-15：records.r4.every（既定 1）コマごと（方案 A の時間の逃げ道
    # 「重い記録を 1 コマおき」）。飛ばしたコマではブロックを閉じない（窓の外に出た時だけ閉じる）
    r4_on = bool(R4 and tnow >= float(R4.get("t0", -1e9)) - 1e-9 and in_win(tnow))
    if r4_on and (f - 1) % int(R4.get("every", 1)) == 0:
        ix0 = int(np.searchsorted(xs, float(R4["x"][0]))); ix1 = int(np.searchsorted(xs, float(R4["x"][1])))
        iz1 = int(np.searchsorted(zs, float(R4["z1"])))
        jy0 = int(np.searchsorted(y_c, float(R4.get("y0", -12.0)))); jy1 = int(np.searchsorted(y_c, float(R4.get("y1", 16.0))))
        clip = float(R4.get("clip_vox", 6.0)) * VOX
        if meta["r4"] is None:
            meta["r4"] = dict(x0=float(xs[ix0]), dx=m["d"][0], nx=ix1 - ix0, z0=float(zs[0]), dz=m["d"][2], nz=iz1, y0=float(y_c[jy0]), dy=dy,
                              ny=jy1 - jy0, clip_m=clip, t_off=T_OFF)
        buf["r4"].append(np.clip(a[:iz1, jy0:jy1, ix0:ix1], -clip, clip).astype(np.float16)); buf["r4f"].append(f)
        flush("r4")
    elif not r4_on and buf["r4"]:
        flush("r4", True)                       # 窓の終わりでブロックを閉じる（窓ごとに別のファイル）
    # R5：面。重い記録：records.windows の中だけ
    ss = 0.0
    if R5 and tnow >= float(R5.get("t0", 1e9)) - 1e-9 and (f - 1) % int(R5.get("every", 1)) == 0 and in_win(tnow):
        try:
            ts0 = time.time()
            r5 = write_surface(f, tnow, OFF if OFF is not None else 0.0)
            ss = time.time() - ts0
            if len(info.get("r5", [])) < 4000:
                info.setdefault("r5", []).append(dict(frame=f, **r5))
        except Exception as e:
            info.setdefault("r5_errors", []).append("%d %s" % (f, str(e)[:200]))
    n = -1; sn = -1; sd = -1.0
    pr_ = [-1] * 5
    try:
        wg = dop.simulation().findObject("water").geometry()
        n = wg.intrinsicValue("pointcount")
        if wg.findGlobalAttrib("ss_n") is not None:
            sn = int(wg.attribValue("ss_n")); sd = float(wg.attribValue("ss_dt"))
        if f in PS_FRAMES:
            info.setdefault("pstats", {})[str(f)] = pstats(wg)
        if PREG_EVERY > 0 and (f % PREG_EVERY == 0 or f == f0):
            try:
                pr_ = particle_regions(wg)
                _Pl = np.frombuffer(wg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - O3
                info.setdefault("leak", []).append(dict(frame=int(f), t=float(tnow), **bed_leak(_Pl)))
                del _Pl
            except Exception as e:
                if len(info.get("preg_errors", [])) < 5:
                    info.setdefault("preg_errors", []).append("%d %s" % (f, str(e)[:200]))
    except Exception as e:
        if len(info.get("geo_errors", [])) < 5:
            info.setdefault("geo_errors", []).append(str(e)[:200])
    if SF and SFC and int(SFC.get("every", 0)) > 0 and (f == f0 or f % int(SFC["every"]) == 0):
        try:
            info.setdefault("sf_check", []).append(sf_check(f, tnow, vv))
        except Exception as e:
            if len(info.setdefault("sf_check_errors", [])) < 5:
                info["sf_check_errors"].append("%d %s" % (f, repr(e)[:300]))
    if DTAB is not None and DC and int(DC.get("every", 0)) > 0 and (f == f0 or f % int(DC["every"]) == 0):
        try:
            info.setdefault("dir_check", []).append(dir_check(f, tnow, vv))
        except Exception as e:
            if len(info.setdefault("dir_check_errors", [])) < 5:
                info["dir_check_errors"].append("%d %s" % (f, repr(e)[:300]))
    try:
        lr_ = region_means(eta, xs, zs)
        lq_ = region_means(neg.sum(axis=1).astype(np.float64), xs, zs, count=True)
    except Exception as e:
        lr_ = [float("nan")] * 5; lq_ = [float("nan")] * 5
        if len(info.get("level_reg_errors", [])) < 5:
            info.setdefault("level_reg_errors", []).append("%d %s" % (f, str(e)[:200]))
    lv49 = levels49(eta, xs, zs)
    lvl_reg.append(lr_); liq_reg.append(lq_); preg.append(pr_)
    lvl49.append([lv49[r[0]] for r in LREG]); gauge.append(gauges(eta, xs, zs))
    try:
        volr.append(vc_step(f, tnow, a, xs, y_c, zs, lv49, eta=eta))
    except Exception as e:
        volr.append([float("nan")] * 8)
        if len(info.setdefault("volcorr_errors", [])) < 5:
            info["volcorr_errors"].append("%d %s" % (f, repr(e)[:300]))
    if f in FB_FRAMES:
        info.setdefault("fieldbox", {})[str(f)] = fieldbox()
    r_now, r_pk = GC.rss_gb()
    bx = (xs >= LVL_BOX[0]) & (xs <= LVL_BOX[1]); bz = (zs >= LVL_BOX[2]) & (zs <= LVL_BOX[3])
    mid = eta[np.ix_(bz, bx)]
    lvl = float(np.nanmean(mid)) if np.isfinite(mid).any() else -999.0
    frames.append(f); wall.append(dt); npts.append(n); tsim.append(tnow); lvls.append(lvl); ssn.append(sn); ssdt.append(sd); rss_l.append(r_pk)
    surf_s.append(ss)
    if lvl0 is None:
        lvl0 = lvl
    if f % 24 == 0 or f == f0:
        print("f=%d t=%.2f sim=%.2fs surf=%.2fs pts=%d sub=%d rss=%.2fGB lvl=%.3f band=%.3f flat=%.3f swash=%.3f d=%s eta_max=%.2f" % (
            f, tnow, dt, ss, n, sn, r_now, lvl, lv49.get("band_core", float("nan")), lv49.get("flat", float("nan")), lv49.get("swash", lv49.get("break_front", float("nan"))),
            ("%.2e" % volr[-1][2]) if VC_ON else "-", np.nanmax(eta)))
        sys.stdout.flush()
    if f % 48 == 0:
        save_series()
    if time.time() - t_start > wall_limit:
        stopped = "wall_limit at frame %d" % f
        break
    if f - f0 >= 6 and lvl - lvl0 < -lvl_guard:
        stopped = "free_fall at frame %d (mean level %.2f m, start %.2f m)" % (f, lvl, lvl0)
        break
    if not np.isfinite(eta).any() or not np.isfinite(np.nanmax(eta)):
        stopped = "no water at frame %d" % f
        break

for k in ("hf", "r2", "r3", "r4"):
    flush(k, True)
save_series()
wall_total = time.time() - t_start
ck = sorted(os.listdir(ckdir)) if os.path.isdir(ckdir) else []
ck_bytes = sum(os.path.getsize(os.path.join(ckdir, x)) for x in ck)
nn = [v for v in npts if v >= 0]
ss_ok = [v for v in ssn if v >= 0]
if True:
    info["volcorr"] = dict(on=VC_ON, V0=VC["V0"], Vwin0=VC["Vwin0"], Lb0=VC["Lb0"], Lc0=VC["Lc0"], src=VC["src"], I_end=VC["I"], cum_added_m3=VC["cum"],
                           frames=VC["n"], frames_at_cap=VC["ncap"], frac_at_cap=(VC["ncap"] / VC["n"]) if VC["n"] else None,
                           state="volcorr/state.jsonl")
rec = {
    "stage": "FLIP52S", "run_id": rid, "bed": args.get("bed"), "bed_spec_ctrl": BED, "sf": {k: v for k, v in (SF or {}).items() if k not in ("B", "E")}, "dir": args.get("dir"),
    "module_shas": GC.module_shas(), "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    "houdini": hou.applicationVersionString(), "hip": HIP, "hip_sha256": HIP_SHA, "priority": PRIO, "free_gb_start": round(free, 1),
    "offset_o": [OX, OY, OZ], "offset_note": "Houdini の座標 = 計画の座標 + o。記録（R1〜R5・pstats）は計画の座標、fieldbox は Houdini の座標のまま",
    "parms": {k: P[k] for k in P if k != "sf_tab"}, "solver": sv, "solver_parms": solver_parms, "case": args.get("case", {}), "records": REC,
    "f_start": f0, "f_end_req": f1, "f_end_done": frames[-1] if frames else None, "fps": fps, "t_off": T_OFF,
    "t_start_done": tsim[0] if tsim else None, "t_end_done": tsim[-1] if tsim else None,
    "ckpt_dir": ckdir, "ckpt_files": len(ck), "ckpt_gb": round(ck_bytes / 1e9, 3), "ckpt_list": ck[-50:],
    "particles_first": nn[0] if nn else None, "particles_max": max(nn) if nn else None,
    "wall_total_s": round(wall_total, 1), "wall_launch_s": round(time.time() - t_launch, 1),
    "wall_first_frame_s": round(wall[0], 2) if wall else None,
    "wall_per_frame_median_s": round(float(np.median(wall[1:])) if len(wall) > 1 else (wall[0] if wall else 0), 3),
    "surf_per_frame_median_s": round(float(np.median([v for v in surf_s if v > 0])) if any(v > 0 for v in surf_s) else 0.0, 3),
    "substeps_min_max": [min(ss_ok), max(ss_ok)] if ss_ok else None,
    "substeps_hist": {str(v): int(ss_ok.count(v)) for v in sorted(set(ss_ok))},
    "rss_peak_gb": round(GC.rss_gb()[1], 2),
    "level_start_m": lvl0, "level_min_m": float(np.min(lvls)) if lvls else None, "level_end_m": lvls[-1] if lvls else None,
    "stopped": stopped, "info": info, "note": args.get("note", ""), "grid": meta["hf"], "still_offset": dict(value=OFF, source=OFF_SRC),
}
write_rec(rec)
print("DONE", json.dumps({k: rec[k] for k in ("run_id", "f_end_done", "wall_total_s", "particles_max", "rss_peak_gb", "substeps_min_max", "stopped")}))
