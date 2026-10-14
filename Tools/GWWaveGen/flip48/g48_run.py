# -*- coding: utf-8 -*-
"""FLIP48：3D の尾根と棚の水槽（A 字の盛り上がりの試し。Docs/Progress/FLIP48_3D_Peak_Setup_ja.md）の計算を 1 回（1 起動）走らせて、
記録を残す（hython で実行。g48_chain.py が起動する）。
2026-10-15 FLIP46 の g46_run.py（Tools/GWWaveGen/flip46、変えていない）を写して直した。変えた所：
  - 道具：g48_common（置き場所 Build/FLIP48・場面 Houdini/FLIP48/g48_tank.hiplc・棚のある bed_z）。g46_online は FLIP46 の物を読む
    （着水の見張り stop_touchdown を使う時だけ働き、その海底は棚のない尾根。FLIP48 の設定では使わない）。
  - 海底より下の粒子の数（bed_leak）と初めのコマの確かめの海底の値：CTRL の shelf_h（棚の水深）を入れた g48_common.bed_z で。
  - 記録の所の名前の「岸」の既定を x ≥ 296 m（真ん中が棚に着く x）に。stage を FLIP48 に。
  - run.json に cfg の bed・solitary と、読み込んだ flip46/flip48 の道具の SHA-256（g48_common.module_shas）を書く。
  - 記録の置き場所：Unity/Build/FLIP48/<out_root>/<run_id>/（FLIP46 の置き場所には書かない）。
使い方: hython g48_run.py <cfg.json のパス>（ふつうは py -3.10 g48_chain.py <cfg.json> から）
以下は g46_run.py の説明のまま（記録の形 R1〜R7 は同じ）：
FLIP46：3D の尾根の水槽（Guyenne & Grilli 2006 を実物の大きさで。BigWave_Recipes_ja.md §5.2 E1b）の計算を 1 回（1 起動）走らせて、
記録を残す（hython で実行）。FLIP45 の g45_run.py（Tools/GWWaveGen/flip45、変えていない）を写して直した。FLIP45 と同じ所：
  起動の始めに自分の優先度を「通常より下」にし電力の抑えを使わないよう頼む、G: の空きが 25 GB より少なければ走らせない、
  水面の見張り（level_box の一番上の水面の平均が始めより level_guard_m 下がる・水がない・NaN で止める。既定の level_box は箱の全部：
  閉じた水槽なので全部の平均は孤立波があっても変わらず、自由落下だけが下げる）、1 起動の時間の上限、DOP の途中保存、
  選んだコマの場の箱の端と粒子の縦の速さ、断面の水面の場から計算の中で着水を読んで止める（cfg の stop_touchdown がある時だけ）。
FLIP45 から変えた所：
  - 入口の表を外し、孤立波の解の npz（cfg の solitary_npz → CTRL の sol_npz。SHA-256 を記録）を使う。wave_on 1 で npz がなければ走らせない。
  - 静かな水面のずれ（N1）：t ∈ n1_window（既定 0.5〜1.5 s）の一番上の水面の中央値を、波の先の n1_x（既定 x 260〜310 m）で測る
    （孤立波の頂から 130 m 以上前で、波の高さは 1 cm より小さい【計算：GN の sech²】）。wave_on 0 の静かな水の試しは箱の全部で測る。
  - 初めのコマの確かめ（init_check_frames、既定 1・2・3）：頂の x（解の x0 + c t）の真下、深さ 1 m・h0/4・h0/2・3h0/4・0.9 h0 で、
    格子の流速（vel 場、対称の面の格子の層と横の真ん中）と粒子の流速の平均を、解の表の値（x − c t）と並べて run_c*.json の info.init_check に書く
    （FLIP37 の誤り：深い格子の流速が 0 から始まった）。
  - 平均の水面の 5 つの所（R6 の lvl_reg・liq_reg・preg）：箱の全部・平らな所（x < ridge_x0）・尾根の内（x < 250 m、横 < W/2）・
    尾根の外（x < 250 m、横 ≥ W/2）・岸（x ≥ 250 m）。
  - 記録：
    R1 hf_cCCCCC_bBBBBB.npz  一番上の水面の高さ eta[コマ, 横の格子, x の格子]（float32、全領域。格子の中心）、t、frames
    R2 r2_cCCCCC_bBBBBB.npz  y = 0 の断面（対称の壁に接する格子の層）の水面の場 sdf[コマ, 縦, x]（float16、±8 m で切る）と u・w
    R3 r3_cCCCCC_bBBBBB.npz  横 r3_z の断面（既定の設定は横の壁に接する層 W − 格子/2。論文 図 9 の y' = ±4）の sdf と u・v・w
    R4 r4_cCCCCC_bBBBBB.npz  水面の狭い帯の SDF（3D。records.r4 の t0 から）
    R5 surf/s_FFFFF.gw45s    面（三角形。FLIP45 と同じ形 GW45SRF1。g45_export_unity.py で読める）。records.r5 の t0 から every コマごと
    R6 run_cCCCCC.json・r6_cCCCCC.npz  1 コマの秒・小刻みの数・粒子の数・主メモリー・優先度・平均の水面の 5 つの所
    R7 ckpt/v.FFFF.sim       途中保存（DOP の explicit cache）
  - 時刻：コマ f の時刻 = t_off + (f − 1)/24（CTRL の t_off。FLIP46 は 0：1 コマ目が初めの状態 t = 0）。
使い方: hython g46_run.py <cfg.json のパス>
出力: Unity/Build/FLIP46/<out_root>/<run_id>/
"""
import hou, sys, os, json, time, hashlib, glob, struct
import numpy as np

sys.dont_write_bytecode = True
TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip48"
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip46")
sys.path.insert(0, TOOLS)
import g48_common as GC
import g46_online as GO

HIP = GC.HIP
a1 = sys.argv[1]
args = json.load(open(a1, encoding="utf8"))
rid = args["run_id"]
ROOT = os.path.join(GC.B48, args.get("out_root", "runs")).replace("\\", "/")
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


# ---------------------------------------------------------------- 置き場所の見張り（計画 N7）
free = GC.free_gb("G:/")
disk_stop = float(args.get("disk_stop_free_gb", 25.0))
if free < disk_stop:
    rec = dict(stage="FLIP48", run_id=rid, date=time.strftime("%Y-%m-%d %H:%M:%S"), f_start=f0, f_end_req=f1, f_end_done=None,
               stopped="disk: G: free %.1f GB < %.1f GB（計画 N7。利用者に伺う）" % (free, disk_stop), priority=PRIO, free_gb_start=free)
    write_rec(rec)
    print("DONE", json.dumps({"run_id": rid, "stopped": rec["stopped"]}, ensure_ascii=False))
    sys.exit(0)

t_launch = time.time()
HIP_SHA = GC.sha256_file(HIP)
hou.hipFile.load(HIP, suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/G46_SETUP/CTRL")
for k, v in args.get("parms", {}).items():
    ctrl.parm(k).set(v)

# ---------------------------------------------------------------- 孤立波の解の npz（CTRL の sol_npz）
solinfo = None
SOLP = args.get("solitary_npz")
if SOLP:
    ctrl.parm("sol_npz").set(SOLP)
SOLP = ctrl.parm("sol_npz").evalAsString()
if float(ctrl.parm("wave_on").eval()) > 0.5:
    if not os.path.exists(SOLP):
        rec = dict(stage="FLIP48", run_id=rid, date=time.strftime("%Y-%m-%d %H:%M:%S"), f_start=f0, f_end_req=f1, f_end_done=None,
                   stopped="error: 孤立波の npz がない %s" % SOLP, priority=PRIO)
        write_rec(rec)
        print("DONE", json.dumps({"run_id": rid, "stopped": rec["stopped"]}, ensure_ascii=False))
        sys.exit(0)
    solinfo = dict(npz=SOLP, sha256=GC.sha256_file(SOLP))
    _sg = hou.node("/obj/G46_SETUP/OUT_SOL").geometry()
    solinfo["table"] = {a_.name(): _sg.attribValue(a_.name()) for a_ in _sg.globalAttribs()}
    try:
        _d = np.load(SOLP)
        if "info" in _d.files:
            solinfo["npz_info"] = json.loads(str(_d["info"]))
    except Exception as e:
        solinfo["npz_info_error"] = repr(e)[:200]
else:
    solinfo = dict(npz=None, note="wave_on 0（静かな水）")

fs = hou.node("/obj/G46_SIM/flipsolver")
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
dop = hou.node("/obj/G46_SIM")
fi = hou.node("/obj/G46_READ/surface_field")
fv = hou.node("/obj/G46_READ/vel_field")
P = {p.name(): p.eval() for p in ctrl.parms()}
T_OFF = float(P["t_off"])
VOX = float(P["dp"]) * float(P["gridscale"])
X0, LX, W = float(P["x0"]), float(P["Lx"]), float(P["W"])
OX, OY, OZ = float(P.get("ox", 0.0)), float(P.get("oy", 0.0)), float(P.get("oz", 0.0))   # Houdini = 計画 + o（読み方 R1）
O3 = np.array([OX, OY, OZ])
wall_limit = float(args.get("wall_limit_s", 1740))
lvl_guard = float(args.get("level_guard_m", 1.0))
REC = args.get("records", {})
R3Z = REC.get("r3_z")
R4 = REC.get("r4")
R5 = REC.get("r5")
BLOCK = int(REC.get("block", 120))
R4BLOCK = int(REC.get("r4_block", 24))
FB_FRAMES = set(int(v) for v in args.get("fieldbox_frames", []))
PS_FRAMES = set(int(v) for v in args.get("pstats_frames", []))
LVL_BOX = args.get("level_box") or [X0, X0 + LX, 0.0, W]   # 水面の見張りの範囲（既定は箱の全部。閉じた水槽なので全部の平均は自由落下だけが下げる）
# 平均の水面の時系列の 5 つの所（計画の座標。2026-10-12 に足した。帯の角は入口・出口の帯に入れる）
REGIONS = ["all", "flat", "ridge_inner", "ridge_outer", "shore"]
RX0 = float(P["ridge_x0"]); XSH = float(args.get("shore_x", GC.SHORE_X)); ZHALF = 0.5 * W
BED = GC.bed_spec(parms=P)          # FLIP48：海底の式の引数（棚 shelf_h を含む。CTRL の値）
PREG_EVERY = int(REC.get("preg_every", 24))


def region_index(x, zl):
    """x・横（計画の座標、同じ形の配列）→ 0 平らな所・1 尾根の内・2 尾根の外・3 岸。"""
    r = np.where(x < RX0, 0, np.where(x >= XSH, 3, np.where(zl >= ZHALF, 2, 1)))
    return r


def region_means(vals, x, zl, count=False):
    """vals[横, x] を 5 つの所で平均（count なら和）。返り値 5 個の list。"""
    rid_ = region_index(x[None, :], zl[:, None])
    out = [float(np.nansum(vals)) if count else (float(np.nanmean(vals)) if np.isfinite(vals).any() else float("nan"))]
    for k in range(4):
        m = rid_ == k
        v = vals[m]
        if count:
            out.append(float(np.nansum(v)))
        else:
            out.append(float(np.nanmean(v)) if v.size and np.isfinite(v).any() else float("nan"))
    return out


def particle_regions(wg):
    """粒子の数を 5 つの所で（計画の座標。float32 のまま数える）。"""
    Pp = np.frombuffer(wg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3)
    x = Pp[:, 0] - np.float32(OX); zl = Pp[:, 2] - np.float32(OZ)
    r = region_index(x, zl)
    c = np.bincount(r, minlength=4)
    return [int(len(Pp))] + [int(v) for v in c[:4]]


def tnow_of(f):
    return T_OFF + (f - 1) / fps


# 静かな水面のずれ（計画 N1）：設定にあれば（途中保存から始めた計算は元の計算の値）それを使い、なければこの計算の始めの
# t_off + 0.5〜2.0 s の一番上の水面の中央値（x ≥ n1_x_min）を計算の中で測る。前の起動で測った物は引き継ぐ。
OFF_GIVEN = args.get("still_offset_m")
WAVE_ON = float(P.get("wave_on", 0.0)) > 0.5
N1_X = args.get("n1_x") or ([260.0, 310.0] if WAVE_ON else [X0, X0 + LX])     # 静かな水面のずれを測る x の範囲
N1_WIN = args.get("n1_window") or [0.5, 1.5]                                   # 測る時刻（t_off からの秒）
N1_XMIN = float(N1_X[0])
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
        if _o is not None and int(_r.get("f_start") or 0) < f0:
            OFF = float(_o["value"]); OFF_SRC = "restored from run_c%05d" % int(_r.get("f_start"))
# 着水の読み（y = 0 の断面）
STOP_TD = args.get("stop_touchdown")
if STOP_TD:
    STOP_TD = dict(STOP_TD, still_offset_m=(OFF if OFF is not None else 0.0))
WATCH = GO.TouchdownWatch(STOP_TD, VOX, dict(P), fps) if STOP_TD else None
if WATCH is not None:
    for _p in sorted(glob.glob(os.path.join(OUT, "run_c*.json"))):
        try:
            _r = json.load(open(_p, encoding="utf8"))
        except Exception:
            continue
        if not (int(args.get("f_first", f0)) <= int(_r.get("f_start") or 0) < f0):
            continue
        _inf = _r.get("info") or {}
        _td = _inf.get("touchdown_online"); _tp = _inf.get("tip_online")
        WATCH.restore(_td if _td and int(_td["frame"]) < f0 else None, _tp if _tp and int(_tp["frame"]) < f0 else None)
RESTORED = dict(td=(WATCH.td or {}).get("frame"), tip=(WATCH.tip or {}).get("frame")) if (WATCH is not None and (WATCH.td or WATCH.tip)) else None

# 場を読む節（場の箱の端。必要な時だけ作る。場面は保存しない）
FI = {}
if FB_FRAMES:
    rdn = hou.node("/obj").createNode("geo", "G45_FIELDS")
    for c in rdn.children():
        c.destroy()
    for nm in ["surface", "pressure", "vel", "collision", "collisionweights", "massdensity", "divergence"]:
        q = rdn.createNode("dopimportfield::2.0", "f_" + nm)
        q.parm("doppath").set("/obj/G46_SIM")
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


def pstats(wg):
    Pp = np.frombuffer(wg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - O3   # 計画の座標
    V = np.frombuffer(wg.pointFloatAttribValuesAsString("v"), dtype=np.float32).reshape(-1, 3)
    mid = (Pp[:, 0] > X0 + 0.2 * LX) & (Pp[:, 0] < X0 + 0.8 * LX)
    sp = np.sqrt((V.astype(np.float64) ** 2).sum(1)); im = int(np.argmax(sp))
    return dict(n=int(len(Pp)), vy_mean_mid=float(V[mid, 1].mean()), vy_absmean_mid=float(np.abs(V[mid, 1]).mean()),
                vy_min_mid=float(V[mid, 1].min()), vy_max_mid=float(V[mid, 1].max()),
                speed_max=float(sp[im]), speed_max_at=[float(c) for c in Pp[im]], n_speed_gt_0p1=int((sp > 0.1).sum()),
                ymax_mid=float(Pp[mid, 1].max()), ymin_all=float(Pp[:, 1].min()), zmin_all=float(Pp[:, 2].min()), **bed_leak(Pp))


def bed_leak(Pp):
    """海底の中へ入った粒子（計画の座標）。y − 海底 < −格子/4 の数と、y − 海底 の最小。"""
    gap = Pp[:, 1] - GC.bed_z(Pp[:, 0], Pp[:, 2], **BED)
    return dict(n_below_bed=int((gap < -0.25 * VOX).sum()), gap_min=float(gap.min()) if len(gap) else None)


INIT_FRAMES = set(int(v) for v in args.get("init_check_frames", [1, 2, 3]))
INIT_DX = [float(v) for v in args.get("init_check_dx", [-32.0, 0.0, 32.0])]
# 2026-10-12 統合の役が足した：確かめる深さ（計画の z、静かな水面 0・上向き）と横の位置（計画の y）を cfg で選べるように。
# なければ前のまま（深さ 1 m・h0/4・h0/2・3h0/4・0.9 h0、横は対称の面の格子の層と横の真ん中）。
INIT_Y = [float(v) for v in (args.get("init_check_y") or [])]
INIT_ZL = [float(v) for v in (args.get("init_check_zl") or [])]
# init_dump：確かめるコマに、頂と前後の x のまわりの粒子（位置と流速）と、格子の流速の縦の線を init_fFFFFF.npz に書く
# （x46_frame0.py が厳密な解の点の値と 1 粒子ずつ比べる。解の表を通さない比べ）
INIT_DUMP = bool(args.get("init_dump", False))


def init_dump(f, tnow, wg, comp, c, xc0, h0):
    dt_ = tnow - T_OFF
    Pp = np.frombuffer(wg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - O3
    V = np.frombuffer(wg.pointFloatAttribValuesAsString("v"), dtype=np.float32).reshape(-1, 3)
    xg = np.array([xc0 + d + c * dt_ for d in INIT_DX])
    sel = np.zeros(len(Pp), bool)
    for x_ in xg:
        sel |= np.abs(Pp[:, 0] - x_) < 1.5 * VOX
    zls = INIT_ZL if INIT_ZL else [0.5 * VOX, 0.5 * W]
    ys = np.arange(-float(P["h0"]) - 2.0 * VOX, 12.0 + 1e-9, 0.25 * VOX)
    gl = np.full((len(xg), len(zls), len(ys), 3), np.nan, np.float32)
    for i, x_ in enumerate(xg):
        for j, zl in enumerate(zls):
            for k, y in enumerate(ys):
                hp = hou.Vector3(x_ + OX, y + OY, zl + OZ)
                for q, nm in enumerate(("vel.x", "vel.y", "vel.z")):
                    if nm in comp:
                        gl[i, j, k, q] = comp[nm].sample(hp)
    np.savez_compressed(os.path.join(OUT, "init_f%05d.npz" % f), P=Pp[sel].astype(np.float32), v=V[sel].astype(np.float32),
                        frame=np.int64(f), t=np.float64(tnow), dt=np.float64(dt_), c=np.float64(c), x0=np.float64(xc0),
                        probe_dx=np.array(INIT_DX), probe_x=xg, grid_zl=np.array(zls, np.float64), grid_y=ys, grid_vel=gl,
                        vox=np.float64(VOX), dp=np.float64(P["dp"]), o=O3)
    return int(sel.sum())


def init_check(f, tnow, wg):
    """初めのコマの確かめ（FLIP37 の誤り）：頂の x（解の x0 + c t）と前後で、深さごとに、格子の流速（vel 場）・粒子の流速の平均・解の表の値。"""
    sg = hou.node("/obj/G46_SETUP/OUT_SOL").geometry()
    sv = {q.attribValue("name"): q for q in sg.prims()}
    c = float(sg.attribValue("c")); xc0 = float(sg.attribValue("x0")); h0 = float(P["h0"])
    xlo, xhi = float(sg.attribValue("x_lo")), float(sg.attribValue("x_hi"))
    zlo, zhi = float(sg.attribValue("z_lo")), float(sg.attribValue("z_hi"))
    dt_ = tnow - T_OFF
    vg = fv.geometry()
    comp = {}
    if vg is not None:
        for q in vg.prims():
            if q.type() in (hou.primType.Volume, hou.primType.VDB):
                comp[q.attribValue("name")] = q
    Pp = np.frombuffer(wg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - O3
    V = np.frombuffer(wg.pointFloatAttribValuesAsString("v"), dtype=np.float32).reshape(-1, 3)
    out = dict(frame=int(f), t=float(tnow), c=c, x0=xc0, x_crest=xc0 + c * dt_, rows=[])
    if INIT_DUMP:
        try:
            out["dump_n_particles"] = init_dump(f, tnow, wg, comp, c, xc0, h0)
        except Exception as e:
            out["dump_error"] = repr(e)[:300]
    ylist = INIT_Y if INIT_Y else [-1.0] + [-fr_ * h0 for fr_ in (0.25, 0.5, 0.75, 0.9)]
    zllist = INIT_ZL if INIT_ZL else [0.5 * VOX, 0.5 * W]
    for dx_ in INIT_DX:
        xa = min(max(xc0 + dx_, xlo), xhi)                      # 解の表の x（初めの形を c t だけ動かした物と比べる）
        xg = xc0 + dx_ + c * dt_                                 # 場面の x
        eta_a = float(sv["eta"].sample(hou.Vector3(xa, 0.0, 0.0)))
        for zl in zllist:
            for y in ylist:
                ya = min(max(min(y, eta_a), zlo), zhi)
                row = dict(dx=dx_, x=xg, y=y, zl=zl, eta_ana=eta_a,
                           bed=float(GC.bed_z(xg, zl, **BED)),
                           u_ana=float(sv["u"].sample(hou.Vector3(xa, ya, 0.0))), w_ana=float(sv["w"].sample(hou.Vector3(xa, ya, 0.0))))
                hp = hou.Vector3(xg + OX, y + OY, zl + OZ)
                for nm, key in (("vel.x", "u_grid"), ("vel.y", "w_grid"), ("vel.z", "v_grid")):
                    row[key] = float(comp[nm].sample(hp)) if nm in comp else None
                m = (np.abs(Pp[:, 0] - xg) < VOX) & (np.abs(Pp[:, 1] - y) < VOX) & (np.abs(Pp[:, 2] - zl) < VOX)
                row["n_part"] = int(m.sum())
                if m.any():
                    row["u_part"] = float(V[m, 0].mean()); row["w_part"] = float(V[m, 1].mean()); row["v_part"] = float(V[m, 2].mean())
                out["rows"].append(row)
    return out


def vol_arr(v):
    r = v.resolution()
    return np.frombuffer(v.allVoxelsAsString(), dtype=np.float32).reshape(r[2], r[1], r[0])


def vol_meta(v, plan=True):
    """体積の格子。plan なら p0 を計画の座標（Houdini − o）で返す。"""
    r = v.resolution(); p0 = v.indexToPos((0, 0, 0)); p1 = v.indexToPos((1, 1, 1))
    q = [float(c) for c in p0]
    if plan:
        q = [q[0] - OX, q[1] - OY, q[2] - OZ]
    return dict(res=list(r), p0=q, d=[float(p1[j] - p0[j]) for j in range(3)])


def zslice(v, z):
    """体積 v の横の位置 z（計画の座標）の層（格子の中心の層。z が二つの層の間ちょうどなら両方の平均）。返り値 (配列[縦, x], 情報)。"""
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


# ---------------------------------------------------------------- 面（R5）を自作の形で書く
SURF_DIR = os.path.join(OUT, "surf").replace("\\", "/")
sout = hou.node("/obj/G46_SURF/OUT_SURF")


def oct_encode(n):
    n = n / np.maximum(np.abs(n).sum(1, keepdims=True), 1e-12)
    x, y, z = n[:, 0], n[:, 1], n[:, 2]
    neg = z < 0
    xo = np.where(neg, (1 - np.abs(y)) * np.sign(x + 1e-30), x)
    yo = np.where(neg, (1 - np.abs(x)) * np.sign(y + 1e-30), y)
    return np.round((np.clip(np.stack([xo, yo], 1), -1, 1) * 0.5 + 0.5) * 65535).astype(np.uint16)


HEAD_BYTES = 96


def write_surface(f, tnow, off):
    """GW45SRF1：頭（96 バイト。並びは g45_export_unity.py の説明）＋位置（箱の中の 16 bit × 3）＋法線（8 方向の写像 16 bit × 2）＋v（半精度 × 3）＋添字（32 bit × 3）。"""
    t0s = time.time()
    g = sout.geometry()
    if g is None:
        return dict(error="no surface geometry")
    Pp = np.frombuffer(g.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - O3   # 計画の座標
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
    seam = np.abs(Pu[:, 2]) < 1e-4                    # 対称の面の上の点：法線の横の成分を 0 にする（写した面と法線がそろい、継ぎ目に折れが出ない）
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
lvl_reg, liq_reg, preg = [], [], []
info = {"solitary": solinfo, "level_regions": dict(names=REGIONS, ridge_x0=RX0, shore_x=XSH, z_half=ZHALF, preg_every=PREG_EVERY,
                                                     note_ja="平らな所 x < ridge_x0、岸 x ≥ shore_x、その間を横 W/2 で内と外に分ける")}
if RESTORED:
    info["online_restored"] = RESTORED
solver_parms = {n: fs.parm(n).eval() for n in ("minimumsubsteps", "substeps", "cflcond", "partcflcond", "donarrowband", "narrowbandwidth",
                                              "veltransfer", "usepreconditioner", "usemgpreconditioner", "dynamicresize", "usewaterline")}
try:                                   # 粒子の補い（reseed）の設定（平均の水面の上がりの出所を読むため。2026-10-12 に足した）
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
             preg=np.array(preg, dtype=np.int64).reshape(-1, 5), regions=np.array(REGIONS), vox=np.array(VOX))


t_start = time.time()
stopped = None
lvl0 = None
off_for_surf = OFF if OFF is not None else 0.0
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
    a = vol_arr(vol)                                    # [横, 縦, x]
    izc = int(np.searchsorted(zs, 0.0))                 # side_pad > 0：対称の面 y = 0 より外（SDF の壁の中）の層を落とし、記録の並びを前と同じにする
    if izc > 0:
        a = a[izc:]; zs = zs[izc:]; nz = len(zs)
    if meta["hf"] is None or meta["hf"]["res"] != [nx, ny, nz]:
        if meta["hf"] is not None:
            flush("hf", True); flush("r2", True); flush("r3", True); flush("r4", True)
            info.setdefault("res_changes", []).append([f, nx, ny, nz])
            meta["r2"] = meta["r3"] = meta["r4"] = None      # 断面の情報も新しい格子で作り直す（2026-10-12 の S10 で、1 コマ目の格子のまま残っていた誤りの直し）
        meta["hf"] = dict(res=[nx, ny, nz], x0=float(xs[0]), dx=m["d"][0], z0=float(zs[0]), dz=m["d"][2], y0=float(y_c[0]), dy=dy, t_off=T_OFF)
    # R1：一番上の水面の高さ（列ごと）
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
    # 静かな水面のずれ（N1）を計算の中で測る
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
            if WATCH is not None:
                WATCH.off = OFF
    elif OFF_SRC.startswith("restored") and "still_offset_online" not in info:
        info["still_offset_online"] = dict(value=OFF, source=OFF_SRC)
    # R2・R3：断面（水面の場と流速）
    vg = fv.geometry()
    vv = {}
    if vg is not None:
        for p in vg.prims():
            if p.type() in (hou.primType.Volume, hou.primType.VDB):
                try:
                    vv[p.attribValue("name")] = p
                except Exception:
                    pass
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
                buf[key].append(np.full(sl.shape, np.nan, np.float16))      # 流速の場がない時（記録に印を残す）
                if len(info.setdefault("vel_missing_frames", [])) < 20:
                    info["vel_missing_frames"].append(f)
        buf["r2f"].append(f)
        flush("r2")
        if WATCH is not None:
            WATCH.step(f, tnow, sl, xs, y_c)
            if WATCH.td is not None:
                info["touchdown_online"] = WATCH.td
            if WATCH.tip is not None:
                info["tip_online"] = WATCH.tip
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
    # R4：水面の狭い帯の SDF（3D）
    if R4 and tnow >= float(R4.get("t0", -1e9)) - 1e-9:
        ix0 = int(np.searchsorted(xs, float(R4["x"][0]))); ix1 = int(np.searchsorted(xs, float(R4["x"][1])))
        iz1 = int(np.searchsorted(zs, float(R4["z1"])))
        jy0 = int(np.searchsorted(y_c, float(R4.get("y0", -12.0)))); jy1 = int(np.searchsorted(y_c, float(R4.get("y1", 16.0))))
        clip = float(R4.get("clip_vox", 6.0)) * VOX
        if meta["r4"] is None:
            meta["r4"] = dict(x0=float(xs[ix0]), dx=m["d"][0], nx=ix1 - ix0, z0=float(zs[0]), dz=m["d"][2], nz=iz1, y0=float(y_c[jy0]), dy=dy,
                              ny=jy1 - jy0, clip_m=clip, t_off=T_OFF)
        buf["r4"].append(np.clip(a[:iz1, jy0:jy1, ix0:ix1], -clip, clip).astype(np.float16)); buf["r4f"].append(f)
        flush("r4")
    # R5：面
    ss = 0.0
    if R5 and tnow >= float(R5.get("t0", 1e9)) - 1e-9 and (f - 1) % int(R5.get("every", 1)) == 0:
        try:
            ts0 = time.time()
            r5 = write_surface(f, tnow, OFF if OFF is not None else 0.0)
            ss = time.time() - ts0
            info.setdefault("r5", []).append(dict(frame=f, **r5)) if len(info.get("r5", [])) < 4000 else None
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
        if WAVE_ON and f in INIT_FRAMES:
            try:
                info.setdefault("init_check", []).append(init_check(f, tnow, wg))
            except Exception as e:
                info.setdefault("init_check_errors", []).append("%d %s" % (f, repr(e)[:300]))
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
    # 平均の水面の時系列（5 つの所の η_top の平均と水の格子の数。2026-10-12 に足した。判定にしない）
    try:
        lr_ = region_means(eta, xs, zs)
        lq_ = region_means(neg.sum(axis=1).astype(np.float64), xs, zs, count=True)
    except Exception as e:
        lr_ = [float("nan")] * 5; lq_ = [float("nan")] * 5
        if len(info.get("level_reg_errors", [])) < 5:
            info.setdefault("level_reg_errors", []).append("%d %s" % (f, str(e)[:200]))
    lvl_reg.append(lr_); liq_reg.append(lq_); preg.append(pr_)
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
        print("f=%d t=%.2f sim=%.2fs surf=%.2fs pts=%d sub=%d rss=%.2fGB lvl=%.3f lvl_all=%.3f eta_min=%.2f eta_max=%.2f" % (
            f, tnow, dt, ss, n, sn, r_now, lvl, lvl_reg[-1][0], np.nanmin(eta), np.nanmax(eta)))
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
    _s = WATCH.should_stop(tnow) if WATCH is not None else None
    if _s:
        stopped = _s
        break

for k in ("hf", "r2", "r3", "r4"):
    flush(k, True)
save_series()
wall_total = time.time() - t_start
ck = sorted(os.listdir(ckdir)) if os.path.isdir(ckdir) else []
ck_bytes = sum(os.path.getsize(os.path.join(ckdir, x)) for x in ck)
nn = [v for v in npts if v >= 0]
ss_ok = [v for v in ssn if v >= 0]
rec = {
    "stage": "FLIP48", "run_id": rid, "bed": args.get("bed"), "bed_spec_ctrl": BED, "solitary_nd": args.get("solitary"),
    "module_shas": GC.module_shas(), "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    "houdini": hou.applicationVersionString(), "hip": HIP, "hip_sha256": HIP_SHA, "priority": PRIO, "free_gb_start": round(free, 1),
    "offset_o": [OX, OY, OZ], "offset_note": "Houdini の座標 = 計画の座標 + o。記録（R1〜R5・pstats）は計画の座標、fieldbox は Houdini の座標のまま",
    "parms": {k: P[k] for k in P}, "solver": sv, "solver_parms": solver_parms, "case": args.get("case", {}), "records": REC,
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
