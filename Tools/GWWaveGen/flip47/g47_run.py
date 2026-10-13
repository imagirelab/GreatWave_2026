# -*- coding: utf-8 -*-
"""FLIP47：2D の板の水槽（海底は折れ線、孤立波を初めの状態に置く。BigWave_Recipes_ja.md §5.1 E1a）の計算を 1 回（1 起動）走らせて、
記録を残す（hython で実行）。FLIP44 の g44_run.py（板の記録の形）と FLIP46 の g46_run.py（孤立波の熱い始め・初めのコマの確かめ）を写して直した
（どちらも変えていない）。同じ所：
  起動の始めに自分の優先度を「通常より下」にし電力の抑えを使わないよう頼む、G: の空きが 25 GB より少なければ走らせない、1 起動の時間の上限、
  DOP の途中保存、水面の見張り（箱の全部の一番上の水面の平均が始めより level_guard_m 下がる・水がない で止める。閉じた水槽なので、全部の平均は
  孤立波があっても変わらず、自由落下だけが下げる）、断面の水面の場から計算の中で着水を読んで止める（cfg の stop_touchdown がある時だけ）。
記録（FLIP44 の解析の形のまま。座標は全部、計画の座標）：
  hf_cXXXX.npz          一番上の水面の高さ eta[コマ, 板の層 4, x の格子]（float32。格子の中心）、x、z、t、frames、wall、npts、lvl、ss_n、ss_dt、
                        wind_calls（−1）、grid（JSON）。足した物：crest_x・crest_eta（真ん中の 2 層の平均の一番上の水面の最大の所と高さ）
  sec_cXXXX_bYYYY.npz   板の真ん中に近い層（z = −格子/2）の断面の水面の場 sdf[コマ, y, x]（float16、±8 m で切る）。FLIP44 と同じキー
                        （sdf・frames・t・meta）に、流速 u・w[コマ, y, x]（float16、m/s）を足した。u・w は FLIP の vel の場の vel.x・vel.y を
                        sdf の格子の中心へ双線形で補った物（場の格子が面に置かれていても同じ格子で読めるように）。meta の vel に元の格子を書く
  run_cXXXX.json        条件と記録（起動ごと）。run.json（最初の起動）。<out_root>/runs.jsonl にも 1 行足す。
  ckpt/v.FFFF.sim       途中保存（DOP の explicit cache）
足した確かめ（FLIP46 と同じ考え）：
  init_check（cfg の init_check_frames、既定 1・2・3）：頂（解の x0 + c t）と前後 init_check_dx（既定 −20・0・+20 m）の、深さ init_check_y
  （既定 −2・−9.5・−17 m）で、格子の流速（vel 場を板の真ん中 z = 0 で）・粒子の流速の平均・GN の式の値・解の表の値を並べる（FLIP37 の誤り）。
  leak（24 コマごと）・pstats：海底の中へ入った粒子の数（y − 海底 < −格子/4）と y − 海底 の最小。
  静かな水面のずれ（N1）：t ∈ n1_window（既定 0.5〜1.5 s）の一番上の水面の中央値を、cfg の n1_x の範囲で測る（wave_on 0 なら箱の全部）。
時刻：コマ f の時刻 = t_off + (f − 1)/24（t_off は 0：1 コマ目が初めの状態 t = 0）。
使い方: hython g47_run.py <cfg.json のパス>
出力: Unity/Build/FLIP47/<out_root>/<run_id>/
"""
import hou, sys, os, json, time, glob, warnings
import numpy as np
warnings.filterwarnings("ignore", category=RuntimeWarning)      # 全部 NaN の列の平均など（記録には NaN が残る）

TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip47"
sys.path.insert(0, TOOLS)
import g47_common as GC
import g47_online as GO

HIP = GC.HIP
a1 = sys.argv[1]
args = json.load(open(a1, encoding="utf8"))
# 2026-10-13 周期の波の実験の役：cfg の hip（既定なし＝g47_tank.hiplc のまま）。相対の道はリポジトリから
if args.get("hip"):
    HIP = args["hip"] if os.path.isabs(args["hip"]) else os.path.join(GC.REPO, args["hip"]).replace("\\", "/")
rid = args["run_id"]
ROOT = os.path.join(GC.B47, args.get("out_root", "runs")).replace("\\", "/")
OUT = os.path.join(ROOT, rid).replace("\\", "/")
os.makedirs(OUT, exist_ok=True)
f0, f1 = int(args["f_start"]), int(args["f_end"])
PRIO = GC.unthrottle_self()
print("priority", PRIO); sys.stdout.flush()


def write_rec(rec):
    json.dump(rec, open(os.path.join(OUT, "run_c%04d.json" % f0), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
    if f0 == int(args.get("f_first", 1)):
        json.dump(rec, open(os.path.join(OUT, "run.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
    with open(os.path.join(ROOT, "runs.jsonl"), "a", encoding="utf8") as fh:
        fh.write(json.dumps({k: rec.get(k) for k in ("run_id", "date", "f_start", "f_end_done", "wall_total_s", "particles_max",
                                                      "rss_peak_gb", "substeps_min_max", "stopped")}, ensure_ascii=False, default=str) + "\n")


def stop_early(why):
    rec = dict(stage="FLIP47", run_id=rid, date=time.strftime("%Y-%m-%d %H:%M:%S"), f_start=f0, f_end_req=f1, f_end_done=None,
               stopped=why, priority=PRIO)
    write_rec(rec)
    print("DONE", json.dumps({"run_id": rid, "stopped": why}, ensure_ascii=False))
    sys.exit(0)


# ---------------------------------------------------------------- 置き場所の見張り
free = GC.free_gb("G:/")
if free < float(args.get("disk_stop_free_gb", 25.0)):
    stop_early("disk: G: free %.1f GB < %.1f GB（利用者に伺う）" % (free, float(args.get("disk_stop_free_gb", 25.0))))

t_launch = time.time()
HIP_SHA = GC.sha256_file(HIP)
hou.hipFile.load(HIP, suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/G47_SETUP/CTRL")
for k, v in args.get("parms", {}).items():
    ctrl.parm(k).set(v)
BED = GC.bed_points(args["bed"])
ctrl.parm("bed_prof").set(GC.bed_string(BED))
inl = args.get("inlet")
if inl:
    import g47_tanklib as L
    ctrl.parm("inlet_tab").set(L.inlet_tab_string(inl["freqs_Hz"], inl["amps_m"], inl["phases_rad"], inl["k"]))
# 2026-10-13 周期の波の実験の役：cfg の sf（既定なし）。流れ関数の表を CTRL の sf_tab へ（周期の波の場面 g47_tank_periodic.hiplc だけが持つ）。
# 表の数（OUT_SF の sfN）が B の数と合わなければ止める。
SFINFO = None
SF = args.get("sf")
if SF:
    import g47_tanklib as L
    if ctrl.parm("sf_tab") is None:
        raise SystemExit("cfg に sf があるが、場面 %s に CTRL の sf_tab がない（g47_build_tank.py --periodic の場面を使う）" % HIP)
    ctrl.parm("sf_tab").set(L.sf_tab_string(SF))
    _sg = hou.node("/obj/G47_SETUP/OUT_SF").geometry()
    SFINFO = {a_.name(): _sg.attribValue(a_.name()) for a_ in _sg.globalAttribs() if a_.name() in ("sfh", "sfk", "sfc", "sfUb", "sfN")}
    if int(SFINFO.get("sfN", -1)) != len(SF["B"]):
        raise SystemExit("OUT_SF の sfN %r が cfg の B の数 %d と合わない" % (SFINFO.get("sfN"), len(SF["B"])))
    _B = _sg.attribValue("sfB"); _E = _sg.attribValue("sfE")
    SFINFO["max_abs_diff_B"] = float(max(abs(a_ - b_) for a_, b_ in zip(_B, SF["B"])))
    SFINFO["max_abs_diff_E"] = float(max(abs(a_ - b_) for a_, b_ in zip(_E, SF["E"])))
    SFINFO["T"] = SF.get("T"); SFINFO["H"] = SF.get("H")
# 2026-10-13 板の層の差を調べる役：cfg の init_jitter（既定なし＝場面のまま 0.2 dp）で、初めの粒子の揺らぎの大きさ（dp の倍数）を
# この起動の中だけ変える（場面のファイルは変えない）。
INIT_JIT = args.get("init_jitter")
if INIT_JIT is not None:
    _ip = hou.node("/obj/G47_SETUP/init_particles").parm("snippet")
    _sn = _ip.eval()
    if _sn.count(")*0.2*dp;") != 1:
        raise SystemExit("init_jitter：init_particles の揺らぎの式が見つからない")
    _ip.set(_sn.replace(")*0.2*dp;", ")*%r*dp;" % float(INIT_JIT)))

# ---------------------------------------------------------------- 孤立波の解の npz（CTRL の sol_npz）
solinfo = None
SOLP = args.get("solitary_npz")
if SOLP:
    ctrl.parm("sol_npz").set(SOLP)
SOLP = ctrl.parm("sol_npz").evalAsString()
WAVE_ON = float(ctrl.parm("wave_on").eval()) > 0.5
if WAVE_ON:
    if not os.path.exists(SOLP):
        stop_early("error: 孤立波の npz がない %s" % SOLP)
    solinfo = dict(npz=SOLP, sha256=GC.sha256_file(SOLP))
    _sg = hou.node("/obj/G47_SETUP/OUT_SOL").geometry()
    solinfo["table"] = {a_.name(): _sg.attribValue(a_.name()) for a_ in _sg.globalAttribs()}
    try:
        _d = np.load(SOLP)
        if "info" in _d.files:
            solinfo["npz_info"] = json.loads(str(_d["info"]))
    except Exception as e:
        solinfo["npz_info_error"] = repr(e)[:200]
else:
    solinfo = dict(npz=None, note="wave_on 0（静かな水）")

fs = hou.node("/obj/G47_SIM/flipsolver")
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
dop = hou.node("/obj/G47_SIM")
fi = hou.node("/obj/G47_READ/surface_field")
fv = hou.node("/obj/G47_READ/vel_field")
P = {p.name(): p.eval() for p in ctrl.parms()}
T_OFF = float(P["t_off"])
VOX = float(P["dp"]) * float(P["gridscale"])
X0, LX, LZ = float(P["x0"]), float(P["Lx"]), float(P["Lz"])
OX, OY, OZ = float(P["ox"]), float(P["oy"]), float(P["oz"])
O3 = np.array([OX, OY, OZ])
NXC = int(round(LX / VOX)); NZC = int(round(LZ / VOX))
FX = X0 + (np.arange(NXC) + 0.5) * VOX               # 格子の中心（計画の x）
FZ = -0.5 * LZ + (np.arange(NZC) + 0.5) * VOX       # 板の層の中心（計画の z）
wall_limit = float(args.get("wall_limit_s", 1740))
lvl_guard = float(args.get("level_guard_m", 1.0))
SEC = dict(dict(x0=X0, x1=X0 + LX, t0=0.0, block=120), **(args.get("sec") or {}))
SEC_BLOCK = int(SEC.get("block", 120))
FB_FRAMES = set(int(v) for v in args.get("fieldbox_frames", []))
PS_FRAMES = set(int(v) for v in args.get("pstats_frames", []))
LEAK_EVERY = int(args.get("leak_every", 24))


def tnow_of(f):
    return T_OFF + (f - 1) / fps


def bed_np(x):
    return GC.bed_y(x, BED)


# 静かな水面のずれ（N1）。前の起動で測った物は引き継ぐ
N1_X = args.get("n1_x") or [X0, X0 + LX]
N1_WIN = args.get("n1_window") or [0.5, 1.5]
OFF = args.get("still_offset_m")
OFF = float(OFF) if OFF is not None else None
OFF_SRC = "cfg" if OFF is not None else None
n1_vals = {}                 # コマ → その時の中央値（起動の区切りをまたいで集める。前の起動の記録 info.n1_partial から引き継ぐ）
if OFF is None:
    for _p in sorted(glob.glob(os.path.join(OUT, "run_c*.json")), key=lambda q: int(os.path.basename(q)[5:9])):
        try:
            _r = json.load(open(_p, encoding="utf8"))
        except Exception:
            continue
        if int(_r.get("f_start") or 0) >= f0:
            continue
        _o = (_r.get("info") or {}).get("still_offset_online")
        if _o is not None and _o.get("value") is not None:
            OFF = float(_o["value"]); OFF_SRC = "restored from run_c%04d" % int(_r.get("f_start"))
        for _k, _v in ((_r.get("info") or {}).get("n1_partial") or {}).items():
            if int(_k) < f0:
                n1_vals[int(_k)] = float(_v)
# 着水の読み（板の真ん中の断面）
STOP_TD = args.get("stop_touchdown")
if STOP_TD:
    STOP_TD = dict(STOP_TD, still_offset_m=(OFF if OFF is not None else 0.0))
PW = dict(P); PW["bed"] = BED
WATCH = GO.TouchdownWatch(STOP_TD, VOX, PW, fps) if STOP_TD else None
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
    rdn = hou.node("/obj").createNode("geo", "G47_FIELDS")
    for c in rdn.children():
        c.destroy()
    for nm in ["surface", "pressure", "vel", "collision", "collisionweights", "divergence"]:
        q = rdn.createNode("dopimportfield::2.0", "f_" + nm)
        q.parm("doppath").set("/obj/G47_SIM")
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
            out[nm].append(dict(name=vn, res=list(r), p0_plan=[p0[j] - O3[j] for j in range(3)], d=[p1[j] - p0[j] for j in range(3)],
                                bmin_plan=[bb.minvec()[j] - O3[j] for j in range(3)], bmax_plan=[bb.maxvec()[j] - O3[j] for j in range(3)]))
    return out


def particles_plan(wg):
    Pp = np.frombuffer(wg.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - O3
    V = np.frombuffer(wg.pointFloatAttribValuesAsString("v"), dtype=np.float32).reshape(-1, 3)
    return Pp, V


def bed_leak(Pp):
    """海底の中へ入った粒子（計画の座標）。y − 海底 < −格子/4 の数と、y − 海底 の最小。箱の外（板の厚さ・x）へ出た粒子の数。"""
    gap = Pp[:, 1] - bed_np(Pp[:, 0])
    outx = (Pp[:, 0] < X0 - 0.25 * VOX) | (Pp[:, 0] > X0 + LX + 0.25 * VOX)
    outz = np.abs(Pp[:, 2]) > 0.5 * LZ + 0.25 * VOX
    return dict(n_below_bed=int((gap < -0.25 * VOX).sum()), gap_min=float(gap.min()) if len(gap) else None,
                n_out_x=int(outx.sum()), n_out_z=int(outz.sum()))


def pstats(wg):
    Pp, V = particles_plan(wg)
    sp = np.sqrt((V.astype(np.float64) ** 2).sum(1)); im = int(np.argmax(sp))
    return dict(n=int(len(Pp)), vy_mean=float(V[:, 1].mean()), vy_absmean=float(np.abs(V[:, 1]).mean()),
                vy_min=float(V[:, 1].min()), vy_max=float(V[:, 1].max()), vx_absmean=float(np.abs(V[:, 0]).mean()),
                speed_max=float(sp[im]), speed_max_at=[float(c) for c in Pp[im]], n_speed_gt_0p1=int((sp > 0.1).sum()),
                ymax=float(Pp[:, 1].max()), ymin=float(Pp[:, 1].min()), **bed_leak(Pp))


INIT_FRAMES = set(int(v) for v in args.get("init_check_frames", [1, 2, 3]))
INIT_DX = [float(v) for v in args.get("init_check_dx", [-20.0, 0.0, 20.0])]
INIT_Y = [float(v) for v in args.get("init_check_y", [-2.0, -9.5, -17.0])]
SOLK = args.get("solitary") or {}


def init_check(f, tnow, wg):
    """初めのコマの確かめ（FLIP37 の誤り）：頂（解の x0 + c t）と前後、深さごとに、格子の流速（vel 場、板の真ん中 z = 0）・粒子の流速の平均
    （|Δx|・|Δy| < 格子、板の全部の層）・GN の式・解の表の値（初めの形を c t だけ動かした物）。"""
    sg = hou.node("/obj/G47_SETUP/OUT_SOL").geometry()
    svol = {q.attribValue("name"): q for q in sg.prims()}
    c = float(sg.attribValue("c")); xc0 = float(sg.attribValue("x0")); h0 = float(P["h0"])
    xlo, xhi = float(sg.attribValue("x_lo")), float(sg.attribValue("x_hi"))
    zlo, zhi = float(sg.attribValue("z_lo")), float(sg.attribValue("z_hi"))
    a0 = float(SOLK.get("a_over_h", GC.A_OVER_H)) * h0
    dt_ = tnow - T_OFF
    vg = fv.geometry()
    comp = {}
    if vg is not None:
        for q in vg.prims():
            if q.type() in (hou.primType.Volume, hou.primType.VDB):
                comp[q.attribValue("name")] = q
    Pp, V = particles_plan(wg)
    out = dict(frame=int(f), t=float(tnow), c=c, x0=xc0, x_crest=xc0 + c * dt_, rows=[])
    for dx_ in INIT_DX:
        xa = min(max(xc0 + dx_, xlo), xhi)
        xg = xc0 + dx_ + c * dt_
        eta_t = float(svol["eta"].sample(hou.Vector3(xa, 0.0, 0.0)))
        for y in INIT_Y:
            ya = min(max(min(y, eta_t), zlo), zhi)
            e_gn, u_gn, w_gn = GC.gn_point(xg, y, a0, h0, xc0, t=dt_)
            row = dict(dx=dx_, x=xg, y=y, eta_table=eta_t, eta_gn=e_gn, u_gn=u_gn, w_gn=w_gn, bed_y=float(bed_np(xg)),
                       u_table=float(svol["u"].sample(hou.Vector3(xa, ya, 0.0))), w_table=float(svol["w"].sample(hou.Vector3(xa, ya, 0.0))))
            hp = hou.Vector3(xg + OX, y + OY, 0.0 + OZ)
            for nm, key in (("vel.x", "u_grid"), ("vel.y", "w_grid"), ("vel.z", "vz_grid")):
                row[key] = float(comp[nm].sample(hp)) if nm in comp else None
            m = (np.abs(Pp[:, 0] - xg) < VOX) & (np.abs(Pp[:, 1] - y) < VOX)
            row["n_part"] = int(m.sum())
            if m.any():
                row["u_part"] = float(V[m, 0].mean()); row["w_part"] = float(V[m, 1].mean()); row["vz_part"] = float(V[m, 2].mean())
            out["rows"].append(row)
    return out


def vol_arr(v):
    r = v.resolution()
    return np.frombuffer(v.allVoxelsAsString(), dtype=np.float32).reshape(r[2], r[1], r[0])


def vol_meta(v):
    """体積の格子（p0 は計画の座標）。"""
    r = v.resolution(); p0 = v.indexToPos((0, 0, 0)); p1 = v.indexToPos((1, 1, 1))
    return dict(res=list(r), p0=[float(p0[j]) - O3[j] for j in range(3)], d=[float(p1[j] - p0[j]) for j in range(3)])


def zlayer(v, m, z):
    """体積 v の、計画の z にいちばん近い層 [y, x]。"""
    k = int(round((z - m["p0"][2]) / m["d"][2]))
    k = max(0, min(m["res"][2] - 1, k))
    try:
        b = v.voxelSliceAsString("xy", k)
        a = np.frombuffer(b, dtype=np.float32).reshape(m["res"][1], m["res"][0])
    except Exception:
        a = vol_arr(v)[k]
    return a, k


def comp_on(v, z, xq, yq):
    """流速の成分の体積 v を、計画の z にいちばん近い層で、点 xq（x の並び）・yq（y の並び）の格子へ双線形で補う。返り値 [len(yq), len(xq)]。"""
    m = vol_meta(v)
    a, k = zlayer(v, m, z)
    ny_, nx_ = a.shape
    fx = (np.asarray(xq) - m["p0"][0]) / m["d"][0]; i0 = np.clip(np.floor(fx).astype(int), 0, nx_ - 2); wx = np.clip(fx - i0, 0.0, 1.0)
    fy = (np.asarray(yq) - m["p0"][1]) / m["d"][1]; j0 = np.clip(np.floor(fy).astype(int), 0, ny_ - 2); wy = np.clip(fy - j0, 0.0, 1.0)
    A = a[j0][:, i0] * (1 - wx)[None, :] + a[j0][:, i0 + 1] * wx[None, :]
    B = a[j0 + 1][:, i0] * (1 - wx)[None, :] + a[j0 + 1][:, i0 + 1] * wx[None, :]
    return A * (1 - wy)[:, None] + B * wy[:, None], dict(m, k=k)


# 2026-10-13 板の層の差を調べる役：cfg の zdiag（既定なし＝前と同じ記録）。{"every": コマ, "win_m": 頂の前後 (m), "y_min": (m)}。
# every コマごとに、粒子を板の層（格子の層）ごとに分けて、頂（真ん中 2 層の一番上の水面の最大の x）の前後 win_m・y > y_min（crest）と
# y > 頂の高さの半分（upper）の、数・横の流速 vz の平均と RMS・層の中の z のずれの平均・vx の平均。壁から格子の 1/4 以内の粒子（wall_lo・
# wall_hi）の vz の平均。格子の vel.z（内の面ごと、両隣のどちらかが水の所）の平均と RMS。層ごとの粒子の数（箱の全部）。info.zdiag に残す。
ZDIAG = args.get("zdiag") or None


def zdiag_frame(f, tnow, wg, a, xs, y_c, xc, ec):
    Pp, V = particles_plan(wg)
    V = V.astype(np.float64)
    win = float(ZDIAG.get("win_m", 30.0)); ymin = float(ZDIAG.get("y_min", 2.0))
    iz = np.clip(np.floor((Pp[:, 2] + 0.5 * LZ) / VOX).astype(int), 0, NZC - 1)
    out = dict(frame=int(f), t=float(tnow), xc=float(xc), eta_c=float(ec), n_all=np.bincount(iz, minlength=NZC).tolist())
    if not (np.isfinite(xc) and np.isfinite(ec)):
        return out
    inx = np.abs(Pp[:, 0] - xc) <= win

    def stat(m):
        n_ = int(m.sum())
        if n_ == 0:
            return dict(n=0)
        vz = V[m, 2]
        return dict(n=n_, vz_mean=float(vz.mean()), vz_rms=float(np.sqrt((vz ** 2).mean())), vz_absmax=float(np.abs(vz).max()),
                    frac_vz_gt_0p1=float((np.abs(vz) > 0.1).mean()), vx_mean=float(V[m, 0].mean()), z_mean=float(Pp[m, 2].mean()))
    for key, m in (("crest", inx & (Pp[:, 1] > ymin)), ("upper", inx & (Pp[:, 1] > 0.5 * ec))):
        d = stat(m)
        lay = []
        for k in range(NZC):
            mk = m & (iz == k)
            s = stat(mk)
            if s["n"]:
                s["dz_mean"] = float((Pp[mk, 2] - FZ[k]).mean())
            lay.append(s)
        d["layers"] = lay
        out[key] = d
    mc = inx & (Pp[:, 1] > ymin)
    out["wall_lo"] = stat(mc & (Pp[:, 2] < -0.5 * LZ + 0.25 * VOX))
    out["wall_hi"] = stat(mc & (Pp[:, 2] > 0.5 * LZ - 0.25 * VOX))
    vg = fv.geometry()
    if vg is not None:
        vz_ = None
        for p in vg.prims():
            if p.type() in (hou.primType.Volume, hou.primType.VDB):
                try:
                    if p.attribValue("name") == "vel.z":
                        vz_ = p
                except Exception:
                    pass
        if vz_ is not None:
            r = vz_.resolution()
            if r[0] == a.shape[2] and r[1] == a.shape[1] and r[2] == a.shape[0] + 1:
                g = vol_arr(vz_).astype(np.float64)            # [z 面, y, x]
                cx_ = np.abs(xs - xc) <= win; ry_ = y_c > ymin
                faces = []
                for k in range(1, a.shape[0]):
                    wet = ((a[k - 1] < 0) | (a[k] < 0))[np.ix_(ry_, cx_)]
                    v = g[k][np.ix_(ry_, cx_)][wet]
                    faces.append(dict(k=k, n=int(v.size), mean=float(v.mean()) if v.size else None,
                                      rms=float(np.sqrt((v ** 2).mean())) if v.size else None))
                out["grid_vz_faces"] = faces
            else:
                out["grid_vz_err"] = "res %s vs surface %s" % (list(r), list(a.shape))
    return out


# 2026-10-13 周期の波の実験の役：cfg の sf_check（既定なし）。{"frames": [...], "x": [...], "y": [...]}。そのコマで、入口の帯の中の点の
# 格子の流速（vel 場、板の真ん中 z = 0）と、帯の目標（流れ関数の波 × 壁の近くのなだらかさ × 始めのなだらかさ × 組の包絡。numpy で同じ式）を並べる。
SFC = args.get("sf_check") or None


def _sf_target(x, y, t):
    k, c, h, Ub = float(SF["k"]), float(SF["c"]), float(SF["h"]), float(SF["Ubar"])
    Bv = np.asarray(SF["B"], float); Ev = np.asarray(SF["E"], float)
    X = x - float(P["x_p"]) - c * t
    e = float((Ev * np.cos(np.arange(len(Ev)) * k * X)).sum())
    Y = max(min(y, e) + h, 0.0)
    j = np.arange(1, len(Bv) + 1)
    a = j * k * Y; b = j * k * h
    chch = (np.exp(a - b) + np.exp(-a - b)) / (1.0 + np.exp(-2.0 * b))
    shch = (np.exp(a - b) - np.exp(-a - b)) / (1.0 + np.exp(-2.0 * b))
    u = c - Ub + float((j * k * Bv * chch * np.cos(j * k * X)).sum())
    w = float((j * k * Bv * shch * np.sin(j * k * X)).sum())
    L_ = float(P["wall_taper_m"])
    cw = min(max((x - float(P["x0"])) / L_, 0.0), 1.0) if L_ > 0 else 1.0
    Ew = cw * cw * (3 - 2 * cw) if L_ > 0 else 1.0
    R = float(P["ramp_s"])
    Er = (0.5 - 0.5 * np.cos(np.pi * min(max(t / R, 0.0), 1.0))) if R > 0 else 1.0
    Ps = float(P.get("set_P", 0.0))
    if Ps > 0:
        up, fl, dn = float(P["set_up"]), float(P["set_flat"]), float(P["set_down"])
        tau = t - Ps * np.floor(t / Ps)
        Es = (0.5 - 0.5 * np.cos(np.pi * tau / up)) if tau < up else 1.0 if tau < up + fl else \
             (0.5 + 0.5 * np.cos(np.pi * (tau - up - fl) / dn)) if tau < up + fl + dn else 0.0
    else:
        Es = 1.0
    E_ = Ew * Er * Es
    xg, x0_ = float(P["xg_end"]), float(P["x0"])
    chi = min(max((xg - x) / max(xg - x0_, 1e-6), 0.0), 1.0)
    wr = (np.exp(chi ** 3.5) - 1.0) / (np.e - 1.0) * float(P["relax_g"]) if x < xg else 0.0
    return dict(eta_t=E_ * e, u_t=E_ * u, w_t=E_ * w, E=E_, relax_w_per_dt0=float(min(max(wr, 0.0), 1.0)))


def sf_check(f, tnow):
    vg = fv.geometry()
    comp = {}
    if vg is not None:
        for q in vg.prims():
            if q.type() in (hou.primType.Volume, hou.primType.VDB):
                comp[q.attribValue("name")] = q
    out = dict(frame=int(f), t=float(tnow), rows=[])
    for x in SFC.get("x", []):
        for y in SFC.get("y", []):
            r = dict(x=float(x), y=float(y), **_sf_target(float(x), float(y), float(tnow)))
            hp = hou.Vector3(float(x) + OX, float(y) + OY, OZ)
            for nm, key in (("vel.x", "u_grid"), ("vel.y", "w_grid")):
                r[key] = float(comp[nm].sample(hp)) if nm in comp else None
            out["rows"].append(r)
    return out


# 2026-10-13 周期の波の実験の役：水の体積の直し（周期の波の場面、CTRL の volcorr_on 1 の時だけ）。毎コマの終わりの surface（板の 4 層・海底より上、
# 格子の重み clamp(0.5 − sdf/格子, 0, 1)）から水の体積 V を測り、vol_tcap − 0.5 s〜vol_tcap の V の平均を V0 とし、次のコマの目標の発散
# d = clamp((V0 − V)/V0/vol_tau, ±vol_dmax) を <記録>/volcorr/vd_<次のコマ>.txt に書く（場面の OUT_VOLDIV が時刻で読む）。V0 は前の起動から引き継ぐ。
# vol_mode 1（2026-10-13 SM2b の後に足した）：帯の中（vol_x0〜vol_x1）の一番上の水面（4 層）の平均 ML を測り、vol_avg_s の動く平均 MLbar と、
# vol_tcap − 0.5〜vol_tcap の平均 ML0 の差 e = ML0 − MLbar から、PI で d = e/(h vol_tau) + I、I += e Δt/(h vol_tau vol_ti)（h = h0）。
# d は帯の中だけに置く（場面の vc_div が vol_x0〜vol_x1 の外を 0 にする）。I と MLbar の履歴は前の起動から引き継ぐ。
VC_ON = float(P.get("volcorr_on", 0.0)) > 0.5
VC_MODE = int(round(float(P.get("vol_mode", 0.0))))
VC = dict(rows=[], V0=None, V0_src=None, acc=[], ML0=None, I=0.0, hist=[])
if VC_ON:
    VDIR = os.path.join(OUT, "volcorr").replace("\\", "/")
    os.makedirs(VDIR, exist_ok=True)
    for _p in sorted(glob.glob(os.path.join(OUT, "run_c*.json")), key=lambda q: int(os.path.basename(q)[5:9])):
        try:
            _r = json.load(open(_p, encoding="utf8"))
        except Exception:
            continue
        if int(_r.get("f_start") or 0) >= f0:
            continue
        _v = ((_r.get("info") or {}).get("volcorr") or {})
        if _v.get("V0") is not None:
            VC["V0"] = float(_v["V0"]); VC["V0_src"] = "restored from run_c%04d" % int(_r.get("f_start"))
        if _v.get("ML0") is not None:
            VC["ML0"] = float(_v["ML0"]); VC["I"] = float(_v.get("I_end") or 0.0)
            VC["V0_src"] = "ML0 restored from run_c%04d" % int(_r.get("f_start"))
            VC["hist"] = [[int(a), float(b)] for a, b in (_v.get("hist_end") or []) if int(a) < f0]
    ctrl.parm("vol_dir").set(VDIR)
    _f0p = os.path.join(VDIR, "vd_%05d.txt" % f0)
    if not os.path.exists(_f0p):
        open(_f0p, "w").write("0.0" + chr(10))


def vc_step_level(f, tnow, E2):
    xa, xb = float(P["vol_x0"]), float(P["vol_x1"])
    sel = (FX >= xa) & (FX <= xb)
    ML = float(np.nanmean(E2[:, sel]))
    tc = float(P["vol_tcap"])
    if VC["ML0"] is None:
        if tc - 0.5 - 1e-9 <= tnow - T_OFF <= tc + 1e-9:
            VC["acc"].append(ML)
        if tnow - T_OFF >= tc - 1e-9 and VC["acc"]:
            VC["ML0"] = float(np.mean(VC["acc"])); VC["V0_src"] = "ML0 measured %d frames up to t %.2f s" % (len(VC["acc"]), tnow)
    VC["hist"].append([int(f), ML])
    nT = max(1, int(round(float(P["vol_avg_s"]) * fps)))
    VC["hist"] = VC["hist"][-nT:]
    MLbar = float(np.mean([v for _, v in VC["hist"]]))
    d = 0.0; e = None
    if VC["ML0"] is not None:
        h = float(P["h0"]); tau = max(float(P["vol_tau"]), 1e-3); ti = max(float(P["vol_ti"]), 1e-3); dmax = float(P["vol_dmax"])
        e = VC["ML0"] - MLbar
        dp_ = e / (h * tau)
        Inew = VC["I"] + e / (h * tau * ti) / fps
        dtry = dp_ + Inew
        if abs(dtry) <= dmax or (dtry > dmax and Inew < VC["I"]) or (dtry < -dmax and Inew > VC["I"]):
            VC["I"] = Inew                     # 頭打ちの時は積分を進めない（巻き上がりを止める）
        d = float(np.clip(dp_ + VC["I"], -dmax, dmax))
    open(os.path.join(VDIR, "vd_%05d.txt" % (f + 1)), "w").write(repr(d) + chr(10))
    VC["rows"].append([int(f), float(tnow), ML, MLbar, VC["ML0"], e, VC["I"], d])


def vc_step(f, tnow, a, xs, y_c):
    wv = np.clip(0.5 - a / VOX, 0.0, 1.0)
    above = (y_c[:, None] >= bed_np(xs)[None, :])
    V = float((wv * above[None, :, :]).sum()) * VOX ** 3
    tc = float(P["vol_tcap"])
    if VC["V0"] is None:
        if tc - 0.5 - 1e-9 <= tnow - T_OFF <= tc + 1e-9:
            VC["acc"].append(V)
        if tnow - T_OFF >= tc - 1e-9 and VC["acc"]:
            VC["V0"] = float(np.mean(VC["acc"])); VC["V0_src"] = "measured %d frames up to t %.2f s" % (len(VC["acc"]), tnow)
    d = 0.0
    if VC["V0"] is not None:
        d = float(np.clip((VC["V0"] - V) / VC["V0"] / max(float(P["vol_tau"]), 1e-3), -float(P["vol_dmax"]), float(P["vol_dmax"])))
    open(os.path.join(VDIR, "vd_%05d.txt" % (f + 1)), "w").write(repr(d) + chr(10))
    VC["rows"].append([int(f), float(tnow), V, VC["V0"], d])


# ---------------------------------------------------------------- 主な繰り返し
frames, wall, npts, tsim, lvls, hfs, ssn, ssdt, cx, ce, rss_l = [], [], [], [], [], [], [], [], [], [], []
sec_buf, sec_u, sec_w, sec_fr, sec_meta = [], [], [], [], None
# 2026-10-12 海底の組の役：cfg の sec.allz が真なら、板の 4 層全部の断面の水面の場も sdfz[コマ, 層, y, x]（float16）として残す
# （確かめの役：板の層ごとに水面が傾く。読みが 1 層だけだったので、層ごとの差を出すため）。既定は偽で、前と同じ記録。
SEC_ALLZ = bool(SEC.get("allz", False))
sec_z = []
info = {"solitary": solinfo, "bed": BED}
if SFINFO is not None:
    info["sf_table"] = SFINFO
if RESTORED:
    info["online_restored"] = RESTORED
solver_parms = {n: fs.parm(n).eval() for n in ("minimumsubsteps", "substeps", "cflcond", "partcflcond", "donarrowband", "narrowbandwidth",
                                              "veltransfer", "usepreconditioner", "usemgpreconditioner", "dynamicresize", "usewaterline",
                                              "dosurfacetension")}
grid_info = None


def flush_sec():
    global sec_buf, sec_u, sec_w, sec_fr, sec_z
    if not sec_buf:
        return
    extra = {}
    if SEC_ALLZ and len(sec_z) == len(sec_buf):
        extra["sdfz"] = np.array(sec_z, np.float16)
    np.savez_compressed(os.path.join(OUT, "sec_c%04d_b%04d.npz" % (f0, sec_fr[0])), sdf=np.array(sec_buf, np.float16),
                        u=np.array(sec_u, np.float16), w=np.array(sec_w, np.float16),
                        frames=np.array(sec_fr), t=np.array([tnow_of(v) for v in sec_fr]), meta=json.dumps(sec_meta), **extra)
    sec_buf, sec_u, sec_w, sec_fr, sec_z = [], [], [], [], []


def save():
    np.savez_compressed(os.path.join(OUT, "hf_c%04d.npz" % f0), eta=np.array(hfs, np.float32).reshape(-1, len(FZ), len(FX)), x=FX, z=FZ,
                        frames=np.array(frames), t=np.array(tsim), wall=np.array(wall), npts=np.array(npts), lvl=np.array(lvls),
                        ss_n=np.array(ssn), ss_dt=np.array(ssdt), wind_calls=np.full(len(frames), -1), crest_x=np.array(cx),
                        crest_eta=np.array(ce), rss=np.array(rss_l), grid=json.dumps(grid_info), t_off=np.float64(T_OFF))


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
    if grid_info is None or grid_info["res"] != [nx, ny, nz]:
        grid_info = {"res": [nx, ny, nz], "x0": float(xs[0]), "dx": m["d"][0], "y0": float(y_c[0]), "z0": float(zs[0]), "dy": dy,
                     "dz": m["d"][2], "plan": True, "o": [OX, OY, OZ]}
        info.setdefault("res_changes", []).append([f, nx, ny, nz])
    a = vol_arr(vol)                                    # [z, y, x]
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
    emid = np.nanmean(E2[[NZC // 2 - 1, NZC // 2], :], axis=0) if NZC >= 2 else E2[0]
    if np.isfinite(emid).any():
        ic = int(np.nanargmax(emid)); cx.append(float(FX[ic])); ce.append(float(emid[ic]))
    else:
        cx.append(float("nan")); ce.append(float("nan"))
    # 静かな水面のずれ（N1）を計算の中で測る
    if OFF_SRC is None or OFF_SRC == "measuring":
        if T_OFF + N1_WIN[0] - 1e-9 <= tnow <= T_OFF + N1_WIN[1] + 1e-9:
            sel = E2[:, (FX >= float(N1_X[0])) & (FX <= float(N1_X[1]))]
            if np.isfinite(sel).any():
                n1_vals[int(f)] = float(np.nanmedian(sel))
            OFF_SRC = "measuring"
        if tnow >= T_OFF + N1_WIN[1] - 1e-9 and n1_vals:
            OFF = float(np.median(list(n1_vals.values()))); OFF_SRC = "online"
            info["still_offset_online"] = dict(value=OFF, n_frames=len(n1_vals), frames=[min(n1_vals), max(n1_vals)],
                                               x_range=[float(v) for v in N1_X], window=[T_OFF + N1_WIN[0], T_OFF + N1_WIN[1]])
            if WATCH is not None:
                WATCH.off = OFF
    elif OFF_SRC.startswith("restored") and "still_offset_online" not in info:
        info["still_offset_online"] = dict(value=OFF, source=OFF_SRC)
    # 断面（板の真ん中に近い層。水面の場と流速）
    iz0 = int(np.argmin(np.abs(zs)))
    if tnow >= float(SEC["t0"]) - 1e-9:
        ix0 = int(np.searchsorted(xs, float(SEC["x0"]) - 1e-9))
        ix1 = int(np.searchsorted(xs, float(SEC["x1"]) + 1e-9))
        jy0 = int(np.searchsorted(y_c, float(SEC["y0"]) - 1e-9)) if SEC.get("y0") is not None else 0
        jy1 = int(np.searchsorted(y_c, float(SEC["y1"]) + 1e-9)) if SEC.get("y1") is not None else ny
        if sec_meta is None or sec_meta["res"] != [nx, ny, nz]:
            flush_sec()
            sec_meta = {"res": [nx, ny, nz], "iz": iz0, "z": float(zs[iz0]), "x0": float(xs[ix0]), "dx": m["d"][0], "nx": ix1 - ix0,
                        "y0": float(y_c[jy0]), "dy": dy, "ny": jy1 - jy0, "clip_m": 8.0, "t_off": T_OFF, "plan": True, "o": [OX, OY, OZ],
                        "vel": {}, "vel_note": "u・w は vel.x・vel.y を sdf の格子の中心へ双線形で補った物（m/s）"}
        sl = a[iz0, jy0:jy1, ix0:ix1]
        sec_buf.append(np.clip(sl, -8.0, 8.0).astype(np.float16))
        if SEC_ALLZ:
            izs = [int(k) for k in np.where(okz)[0]]                 # 板の中の層（hf の層と同じ並び、z の小さい順）
            sec_z.append(np.clip(a[izs, jy0:jy1, ix0:ix1], -8.0, 8.0).astype(np.float16))
            sec_meta.setdefault("allz_iz", izs)
            sec_meta.setdefault("allz_z", [float(zs[k]) for k in izs])
        vg = fv.geometry()
        vv = {}
        if vg is not None:
            for p in vg.prims():
                if p.type() in (hou.primType.Volume, hou.primType.VDB):
                    try:
                        vv[p.attribValue("name")] = p
                    except Exception:
                        pass
        for nm, buf in (("vel.x", sec_u), ("vel.y", sec_w)):
            if nm in vv:
                arr, mm = comp_on(vv[nm], float(zs[iz0]), xs[ix0:ix1], y_c[jy0:jy1])
                buf.append(arr.astype(np.float16))
                sec_meta["vel"].setdefault(nm, mm)
            else:
                buf.append(np.full(sl.shape, np.nan, np.float16))
                if len(info.setdefault("vel_missing_frames", [])) < 20:
                    info["vel_missing_frames"].append(f)
        sec_fr.append(f)
        if len(sec_buf) >= SEC_BLOCK:
            flush_sec()
        if WATCH is not None:
            WATCH.step(f, tnow, a[iz0], xs, y_c)
            if WATCH.td is not None:
                info["touchdown_online"] = WATCH.td
            if WATCH.tip is not None:
                info["tip_online"] = WATCH.tip
    n = -1; sn = -1; sd = -1.0
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
        if LEAK_EVERY > 0 and (f % LEAK_EVERY == 0 or f == f0):
            _Pl, _Vl = particles_plan(wg)
            _lk = dict(frame=int(f), t=float(tnow), **bed_leak(_Pl))
            # 2026-10-12 海底の組の役：板の厚さの向きの偏りの見張り（粒子の z の平均・vz の平均。静かな水面の 2 m より上の粒子も別に）
            _up = _Pl[:, 1] > 2.0
            _lk.update(z_mean=float(_Pl[:, 2].mean()), vz_mean=float(_Vl[:, 2].mean()), n_y2=int(_up.sum()),
                       z_mean_y2=(float(_Pl[_up, 2].mean()) if _up.any() else None),
                       vz_mean_y2=(float(_Vl[_up, 2].mean()) if _up.any() else None))
            info.setdefault("leak", []).append(_lk)
            del _Pl, _Vl
        if ZDIAG and (f % int(ZDIAG.get("every", 6)) == 0 or f == f0):
            try:
                info.setdefault("zdiag", []).append(zdiag_frame(f, tnow, wg, a, xs, y_c, cx[-1], ce[-1]))
            except Exception as e:
                if len(info.setdefault("zdiag_errors", [])) < 5:
                    info["zdiag_errors"].append("%d %s" % (f, repr(e)[:300]))
    except Exception as e:
        if len(info.get("geo_errors", [])) < 5:
            info.setdefault("geo_errors", []).append(str(e)[:200])
    if f in FB_FRAMES:
        info.setdefault("fieldbox", {})[str(f)] = fieldbox()
    if VC_ON:
        if VC_MODE == 1:
            vc_step_level(f, tnow, E2)
        else:
            vc_step(f, tnow, a, xs, y_c)
    if SF and SFC and f in set(int(v) for v in SFC.get("frames", [])):
        try:
            info.setdefault("sf_check", []).append(sf_check(f, tnow))
        except Exception as e:
            info.setdefault("sf_check_errors", []).append("%d %s" % (f, repr(e)[:300]))
    r_now, r_pk = GC.rss_gb()
    lvl = float(np.nanmean(E2)) if np.isfinite(E2).any() else -999.0
    frames.append(f); wall.append(dt); npts.append(n); tsim.append(tnow); lvls.append(lvl); ssn.append(sn); ssdt.append(sd); rss_l.append(r_pk)
    if lvl0 is None:
        lvl0 = lvl
    if f % 24 == 0 or f == f0:
        print("f=%d t=%.2f sim=%.2fs pts=%d sub=%d rss=%.2fGB lvl=%.4f crest x=%.1f eta=%.2f" % (
            f, tnow, dt, n, sn, r_now, lvl, cx[-1], ce[-1]))
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
if VC_ON and VC_MODE == 1:
    info["volcorr"] = dict(mode=1, ML0=VC["ML0"], src=VC["V0_src"], I_end=VC["I"], hist_end=VC["hist"], tau=float(P["vol_tau"]), ti=float(P["vol_ti"]),
                           dmax=float(P["vol_dmax"]), tcap=float(P["vol_tcap"]), x=[float(P["vol_x0"]), float(P["vol_x1"])], avg_s=float(P["vol_avg_s"]),
                           cols=["frame", "t", "ML（帯の一番上の水面の平均、4 層）", "MLbar（動く平均）", "ML0", "e = ML0 − MLbar", "I", "次のコマの目標の発散 (1/s)"],
                           rows=VC["rows"])
elif VC_ON:
    info["volcorr"] = dict(V0=VC["V0"], V0_src=VC["V0_src"], tau=float(P["vol_tau"]), dmax=float(P["vol_dmax"]), tcap=float(P["vol_tcap"]),
                           cols=["frame", "t", "V_m3（コマの終わりの surface、海底より上）", "V0_m3", "次のコマの目標の発散 (1/s)"], rows=VC["rows"])
if n1_vals:
    info["n1_partial"] = {str(k): v for k, v in sorted(n1_vals.items())}
wall_total = time.time() - t_start
ck = sorted(os.listdir(ckdir)) if os.path.isdir(ckdir) else []
ck_bytes = sum(os.path.getsize(os.path.join(ckdir, x)) for x in ck)
nn = [v for v in npts if v >= 0]
ss_ok = [v for v in ssn if v >= 0]
rec = {
    "stage": "FLIP47", "run_id": rid, "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    "houdini": hou.applicationVersionString(), "hip": HIP, "hip_sha256": HIP_SHA, "priority": PRIO, "free_gb_start": round(free, 1),
    "offset_o": [OX, OY, OZ], "offset_note": "Houdini の座標 = 計画の座標 + o。記録（hf・sec・pstats・init_check）は計画の座標",
    "parms": {k: P[k] for k in P if k not in ("inlet_tab", "sf_tab")}, "bed": BED, "inlet_name": (inl or {}).get("name"), "solver": sv,
    "solver_parms": solver_parms, "case": args.get("case", {}), "sec": SEC, "solitary": SOLK,
    "f_start": f0, "f_end_req": f1, "f_end_done": frames[-1] if frames else None, "fps": fps, "t_off": T_OFF,
    "t_start_done": tsim[0] if tsim else None, "t_end_done": tsim[-1] if tsim else None,
    "ckpt_dir": ckdir, "ckpt_files": len(ck), "ckpt_gb": round(ck_bytes / 1e9, 3), "ckpt_list": ck[-50:],
    "particles_first": nn[0] if nn else None, "particles_max": max(nn) if nn else None,
    "wall_total_s": round(wall_total, 1), "wall_launch_s": round(time.time() - t_launch, 1),
    "wall_first_frame_s": round(wall[0], 2) if wall else None,
    "wall_per_frame_median_s": round(float(np.median(wall[1:])) if len(wall) > 1 else (wall[0] if wall else 0), 3),
    "substeps_min_max": [min(ss_ok), max(ss_ok)] if ss_ok else None,
    "substeps_hist": {str(v): int(ss_ok.count(v)) for v in sorted(set(ss_ok))},
    "rss_peak_gb": round(GC.rss_gb()[1], 2),
    "level_start_m": lvl0, "level_min_m": float(np.min(lvls)) if lvls else None, "level_max_m": float(np.max(lvls)) if lvls else None,
    "level_end_m": lvls[-1] if lvls else None,
    "stopped": stopped, "info": info, "note": args.get("note", ""), "grid": grid_info, "still_offset": dict(value=OFF, source=OFF_SRC),
}
write_rec(rec)
print("DONE", json.dumps({k: rec[k] for k in ("run_id", "f_end_done", "wall_total_s", "particles_max", "rss_peak_gb", "substeps_min_max", "stopped")}))
