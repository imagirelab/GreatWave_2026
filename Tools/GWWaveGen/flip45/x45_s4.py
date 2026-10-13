# -*- coding: utf-8 -*-
"""FLIP45 煙の試し S4：入口の表（計画 plan_ja.md §10.2 の S4。hython で実行、1 分ほど。流体の計算はしない）。
g45_inlet_table.py の表を、本番の VEX（g45_tanklib.py の bands・wallE・target。E と利得を含む）で SOP の点として読み、帯の 20 点 × 5 時刻
（t ≤ 0 の 1 時刻を含む）で numpy と比べる。判定（計画 §10.2、走らせる前に決めた）：
  (a) VEX と numpy の表の読み（E・利得を掛けた物）の差が A* の 10⁻⁵ 以内（流速は A*·g k/Ω の 10⁻⁵ 以内。読み方 R10）。
  (b) 表と、周波数で足した正しい線形の場の差が、水面で A* の 1 %（0.063 m）、流速でその点（その深さ）の最大の 3 % 以内。
      比べは 20 点の (x, 横) の全部の表の時刻（0.1 s ごと）と、伸ばした深さ z' = 0・−2・−5・−6・−10・−14・−18・−20 m（表の深さの間を含む）。
      狭い帯の近似（--method nb）で外れたら深さごとの表（--method depth、既定）にする（計画 §4.1）。
  (c) t0（−2 s）で、E を掛けた目標が帯の全部で |η| ≤ 0.02 m・水平の速さ ≤ 0.02 m/s（見直し H1）。
使い方：hython x45_s4.py [--gain <gain45.json>] [--case F45] [--layout L1] [--dp 0.5] [--tag S4]
出力：Unity/Build/FLIP45/smoke/<tag>/s4.json
"""
import hou, sys, os, json, time, math, argparse
import numpy as np

TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip45"
sys.path.insert(0, TOOLS)
import g45_common as GC
import g45_inlet_table as IT
import g45_cfg as C
import g45_tanklib as L

ap = argparse.ArgumentParser()
ap.add_argument("--gain", default=None); ap.add_argument("--case", default="F45"); ap.add_argument("--layout", default="L1")
ap.add_argument("--dp", type=float, default=0.5); ap.add_argument("--tag", default="S4"); ap.add_argument("--method", default="depth")
a = ap.parse_args()
PRIO = GC.unthrottle_self()
OUT = GC.B45 + "/smoke/" + a.tag
os.makedirs(OUT, exist_ok=True)
plan = GC.load_plan()
LAY = plan["layouts"][a.layout]
p, b = C.parms_for(LAY, a.dp, -2.0 if LAY["x"][0] == 0.0 else 12.0)
gainrec = json.load(open(a.gain, encoding="utf-8")) if a.gain else None
if a.gain:
    p.update(C.band_gains(a.dp, a.gain))           # 入口の帯だけの利得（method inlet_band_scalar）なら CTRL の in_gain
t_end = 69.5
t0 = p["t_off"]
npz = OUT + "/table.npz"
tab, info = IT.build(a.case, (b["x0"], b["side_sw"] + 1.0), (0.0, b["W"]), (t0, t_end), dp=a.dp, gainrec=gainrec, out=npz, note="S4",
                     method=a.method)
A_STAR = IT.A_STAR
U_STAR = A_STAR * GC.G * GC.K0 / GC.OM

# ---------------------------------------------------------------- 場面
hou.hipFile.load(GC.HIP, suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/G45_SETUP/CTRL")
for k, v in p.items():
    ctrl.parm(k).set(v)
bgeo = OUT + "/table.bgeo.sc"
geo = hou.Geometry()
geo.addAttrib(hou.attribType.Prim, "name", "")
bb = hou.BoundingBox(info["x0"] - 0.5 * info["dx"], info["t0"] - 0.5 * info["dt"], info["y0"] - 0.5 * info["dy"],
                     info["x0"] + (info["nx"] - 0.5) * info["dx"], info["t0"] + (info["nt"] - 0.5) * info["dt"], info["y0"] + (info["ny"] - 0.5) * info["dy"])
for nm in info["fields"]:
    vol = geo.createVolume(info["nx"], info["nt"], info["ny"], bb)
    vol.setAttribValue("name", nm)
    vol.setAllVoxelsFromString(np.ascontiguousarray(tab[nm].astype(np.float32)).tobytes())
geo.saveToFile(bgeo)
ctrl.parm("table_file").set(bgeo)
if info.get("method") == "depth":
    ctrl.parm("tab_levels").set(float(len(info["levels"]))); ctrl.parm("tab_dz").set(float(-info["levels"][1]))
    p["tab_levels"] = float(len(info["levels"])); p["tab_dz"] = float(-info["levels"][1])
else:
    ctrl.parm("tab_levels").set(1.0); p["tab_levels"] = 1.0
tv = hou.node("/obj/G45_SETUP/OUT_TABLE").geometry()
vols = {v.attribValue("name"): v for v in tv.prims()}
vmeta = {k: dict(res=list(v.resolution()), p000=list(v.indexToPos((0, 0, 0))), p111=list(v.indexToPos((1, 1, 1)))) for k, v in vols.items()}

# 点（Houdini の座標：x・上 y・横 z）と時刻
PTS = [(1.3, -0.4, 5.7), (8.6, -3.1, 40.2), (17.2, -10.6, 66.9), (25.9, 0.9, 12.3), (34.4, -19.6, 90.1), (4.7, -1.2, 104.6),
       (55.5, -0.7, 73.4), (101.2, -6.2, 88.8), (150.6, -15.3, 99.5), (199.1, -2.0, 80.7), (205.3, -1.1, 95.2), (215.8, -4.4, 77.7),
       (228.9, -0.3, 106.9), (240.4, -2.0, 85.0), (310.2, -1.0, 30.0), (330.0, -5.0, 100.0), (120.0, -1.0, 30.0), (12.0, 2.5, 33.3),
       (30.5, -7.7, 54.4), (35.9, -0.2, 0.25)]
TIMES = [-2.0, 3.37, 21.05, 40.4, 61.77]
DTS = 1.0 / 24.0
sop = hou.node("/obj/G45_SETUP")
mk = sop.createNode("attribwrangle", "s4_points")
mk.parm("class").set(0)
O3 = (p.get("ox", 0.0), p.get("oy", 0.0), p.get("oz", 0.0))      # Houdini = 計画 + o（読み方 R1）。点は Houdini の座標に置く
code = ["float pts[] = {%s};" % ", ".join("%r" % (c + O3[j]) for q in PTS for j, c in enumerate(q)), "float ts[] = {%s};" % ", ".join("%r" % t for t in TIMES),
        "for (int it = 0; it < len(ts); it++) for (int i = 0; i < len(pts)/3; i++) {",
        "  int p = addpoint(0, set(pts[3*i], pts[3*i+1], pts[3*i+2]));",
        "  setpointattrib(0, \"t\", p, ts[it]); setpointattrib(0, \"dts\", p, %r); setpointattrib(0, \"pid\", p, i); setpointattrib(0, \"tid\", p, it);" % DTS,
        "}"]
mk.parm("snippet").set("\n".join(code))
mk.parm("vex_precision").set("64")
pr = sop.createNode("attribwrangle", "s4_probe")
pr.setInput(0, mk)
pr.parm("class").set(2)
pr.parm("vex_precision").set("64")
pr.parm("snippet").set(L.snippet("/obj/G45_SETUP/s4_probe"))
pr.cook(force=True)
if pr.errors():
    print("ERR", pr.errors())
g = pr.geometry()
def fa(nm, n=1):
    return np.array(g.pointFloatAttribValues(nm)).reshape(-1, n) if n > 1 else np.array(g.pointFloatAttribValues(nm))
Pp = fa("P", 3); tt = fa("t"); pid = np.array(g.pointIntAttribValues("pid")); tid = np.array(g.pointIntAttribValues("tid"))
vex = dict(eta=fa("eta_t"), vel=fa("vel_t", 3), wdt=fa("wdt"), ftg=fa("ftg"), E=fa("E"), gm=fa("gm"), raw_eta=fa("raw_eta"))


# ---------------------------------------------------------------- numpy の写し（g45_tanklib の bands・wallE・target と同じ式）
def relaxw(c):
    c = np.clip(c, 0, 1); return (np.exp(c ** 3.5) - 1) / (math.e - 1)


def sm(c):
    c = np.clip(c, 0, 1); return c * c * (3 - 2 * c)


def bands_np(x, z, dts):
    wdt = 0.0; ftg = 1.0
    if p["in_on"] > 0.5 and x < p["in1"]:
        chi = np.clip((p["in1"] - x) / (p["in1"] - p["in0"]), 0, 1)
        w = np.clip(relaxw(chi) * p["relax_g"], 0, 1)
        wdt = max(wdt, 1 - (1 - w) ** (dts / p["dt0"]))
        if p["in_tgt"] < 0.5:
            ftg = 0.0
    if p["sd_on"] > 0.5 and z > p["sd0"]:
        chi = np.clip((z - p["sd0"]) / (p["sd1"] - p["sd0"]), 0, 1)
        s = sm((x - p["sd_gen"]) / max(p["sd_sw"] - p["sd_gen"], 1e-6))
        wg = 1 - (1 - np.clip(relaxw(chi) * p["relax_g"], 0, 1)) ** (dts / p["dt0"])
        wa = 1 - math.exp(-p["abs_sigma"] * chi ** p["abs_pow"] * dts)
        wdt = max(wdt, wg + (wa - wg) * s)
        ftg *= (1 - s)
    if x > p["ex0"]:
        chi = np.clip((x - p["ex0"]) / (p["ex1"] - p["ex0"]), 0, 1)
        if p["ex_mode"] < 0.5:
            wdt = max(wdt, 1 - math.exp(-p["abs_sigma"] * chi ** p["abs_pow"] * dts)); ftg = 0.0
        else:
            w = np.clip(relaxw(chi) * p["relax_g"], 0, 1); wdt = max(wdt, 1 - (1 - w) ** (dts / p["dt0"]))
    return float(wdt), float(ftg)


def wallE_np(x, z):
    Lw = p["wall_taper_m"]
    e = sm((x - p["x0"]) / Lw)
    if p["sd_on"] > 0.5:
        e *= sm((p["W"] - z) / Lw)
    if p["ex_mode"] > 0.5:
        e *= sm((p["ex1"] - x) / Lw)
    return float(e)


rows = []
worst_a = dict(eta=0.0, vel=0.0, raw=0.0, wdt=0.0)
for i in range(len(Pp)):
    x, yv, z = Pp[i] - np.array(O3); t = tt[i]
    wdt, ftg = bands_np(x, z, DTS)
    E = wallE_np(x, z)
    bg = p.get("in_gain", 1.0) if (p["in_on"] > 0.5 and x < p["in1"]) else (p.get("sd_gain", 1.0) if (p["sd_on"] > 0.5 and z > p["sd0"]) else 1.0)
    gm = p["amp_gain"] * ftg * E * bg
    s = IT.sample(tab, info, np.array([x]), np.array([z]), np.array([t]))
    eta = gm * s["eta"][0]
    h = p["h0"]
    ye = np.clip(h * (yv - eta) / (h + eta), -h, 0.0)
    uu, vv = IT.table_velocity(tab, info, np.array([x]), np.array([z]), np.array([t]), np.array([ye]))
    u = gm * float(uu[0]); v = gm * float(vv[0])
    if gm == 0.0:
        eta = u = v = 0.0
    d = dict(pid=int(pid[i]), t=float(t), x=float(x), y=float(yv), z=float(z), wdt=wdt, wdt_vex=float(vex["wdt"][i]), ftg=ftg, E=E,
             eta_np=float(eta), eta_vex=float(vex["eta"][i]), u_np=float(u), u_vex=float(vex["vel"][i, 0]), v_np=float(v), v_vex=float(vex["vel"][i, 2]),
             raw_eta_np=float(s["eta"][0]), raw_eta_vex=float(vex["raw_eta"][i]))
    rows.append(d)
    worst_a["eta"] = max(worst_a["eta"], abs(d["eta_np"] - d["eta_vex"]))
    worst_a["vel"] = max(worst_a["vel"], abs(d["u_np"] - d["u_vex"]), abs(d["v_np"] - d["v_vex"]))
    if x <= info["x0"] + info["dx"] * (info["nx"] - 1):        # 表の外（吸う所。目標は 0）は生の読みを比べない（体積の端の扱いが違うため）
        worst_a["raw"] = max(worst_a["raw"], abs(d["raw_eta_np"] - d["raw_eta_vex"]))
    worst_a["wdt"] = max(worst_a["wdt"], abs(d["wdt"] - d["wdt_vex"]))
a_pass = bool(worst_a["eta"] <= 1e-5 * A_STAR and worst_a["raw"] <= 1e-5 * A_STAR and worst_a["vel"] <= 1e-5 * U_STAR and worst_a["wdt"] <= 1e-9)

# ---------------------------------------------------------------- (b) 表と正しい線形の場（深さごと）
ZD = [0.0, -2.0, -5.0, -6.0, -10.0, -14.0, -18.0, -20.0]
pts_b = [(q[0], q[2]) for q in PTS if q[0] <= b["side_sw"] + 1.0]
tser = info["t0"] + info["dt"] * np.arange(info["nt"])
tser = tser[tser <= t_end - 0.05]
ex = IT.exact_points(a.case, pts_b, tser, dp=a.dp, gainrec=gainrec, depth_z=ZD)
bres = []
worst_b = dict(eta_m=0.0, vel_rel=0.0)
for ip, (x, z) in enumerate(pts_b):
    s = IT.sample(tab, info, np.full(len(tser), x), np.full(len(tser), z), tser)
    de = float(np.max(np.abs(s["eta"] - ex["eta"][ip])))
    XX = np.full(len(tser), x); ZZ = np.full(len(tser), z)
    r = dict(x=x, z=z, eta_maxdiff_m=de, eta_max_m=float(np.max(np.abs(ex["eta"][ip]))), vel={})
    worst_b["eta_m"] = max(worst_b["eta_m"], de)
    for iz, zz in enumerate(ZD):
        ut, vt = IT.table_velocity(tab, info, XX, ZZ, tser, np.full(len(tser), zz))
        du = float(np.max(np.abs(ut - ex["u"][ip, iz]))); dv = float(np.max(np.abs(vt - ex["v"][ip, iz])))
        mu = float(np.max(np.abs(ex["u"][ip, iz]))); mv = float(np.max(np.abs(ex["v"][ip, iz])))
        msp = float(np.max(np.hypot(ex["u"][ip, iz], ex["v"][ip, iz])))
        rel = max(du, dv) / max(msp, 1e-9)
        r["vel"][str(zz)] = dict(du=du, dv=dv, umax=mu, vmax=mv, speed_max=msp, rel=rel)
        worst_b["vel_rel"] = max(worst_b["vel_rel"], rel)
    bres.append(r)
b_pass = bool(worst_b["eta_m"] <= 0.01 * A_STAR and worst_b["vel_rel"] <= 0.03)

# ---------------------------------------------------------------- (c) t0 の目標（帯の全部）
xs = info["x0"] + info["dx"] * np.arange(info["nx"]); zs = info["y0"] + info["dy"] * np.arange(info["ny"])
X, Z = np.meshgrid(xs, zs)
inb = (X <= p["in1"]) | ((Z >= p["sd0"]) & (X <= p["sd_sw"]))
Eg = sm((X - p["x0"]) / p["wall_taper_m"]) * sm((p["W"] - Z) / p["wall_taper_m"]) * np.where(Z >= p["sd0"], 1 - sm((X - p["sd_gen"]) / (p["sd_sw"] - p["sd_gen"])), 1.0)
Eg = Eg * np.where(X < p["in1"], p.get("in_gain", 1.0), np.where(Z > p["sd0"], p.get("sd_gain", 1.0), 1.0))     # 帯ごとの利得も掛ける
k0i = 0
c_eta = float(np.max(np.abs(tab["eta"][:, k0i, :] * Eg)[inb]))
U0n = "U" if "U" in tab else "U0"; V0n = "V" if "V" in tab else "V0"
c_sp = float(np.max((np.hypot(tab[U0n][:, k0i, :], tab[V0n][:, k0i, :]) * Eg)[inb]))
c_pass = bool(c_eta <= 0.02 and c_sp <= 0.02)

res = dict(test="S4", date=time.strftime("%Y-%m-%d %H:%M:%S"), houdini=hou.applicationVersionString(), priority=PRIO, case=a.case, layout=a.layout,
           dp=a.dp, gain_file=a.gain, table=dict((k, v) for k, v in info.items() if k not in ("gains_by_mode", "theta_of_mode_deg")),
           gains_by_mode=info.get("gains_by_mode"), volume_meta=vmeta, parms=p, A_star=A_STAR, U_star=U_STAR,
           a=dict(worst=worst_a, tol_eta=1e-5 * A_STAR, tol_vel=1e-5 * U_STAR, passed=a_pass, n=len(rows)),
           b=dict(worst=worst_b, tol_eta_m=0.01 * A_STAR, tol_vel_rel=0.03, depth_z=ZD, passed=b_pass, points=bres,
                  note_ja="狭い帯の近似（Ω の深さの形）。外れたら深さごとの表にする（計画 §4.1）"),
           c=dict(t0=float(info["t0"]), max_eta_m=c_eta, max_speed_ms=c_sp, passed=c_pass), rows=rows)
json.dump(res, open(OUT + "/s4.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(dict(a=res["a"], b=dict(worst=worst_b, passed=b_pass), c=res["c"]), ensure_ascii=False))
