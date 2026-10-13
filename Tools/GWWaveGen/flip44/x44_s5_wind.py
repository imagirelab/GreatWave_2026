# -*- coding: utf-8 -*-
"""FLIP44 煙の試し S5：はがれた流れの形（S）の風の圧力の VEX を、FLIP42 R3 の着水のコマ（3745 コマ）の断面の場を
板に伸ばした体積の上で、SOP の Volume Wrangle で動かす（DOP と同じ本文 `wind_pressure`）。numpy で同じ決まりを別に書いて比べる。
計画 plan_ja.md §6 S5、record_ja.md の「計画の読み方」9・10。hython で実行（場面は保存しない）。
判定：露出した水面の 20 点で p が q·n_x の ±5 %、上に水がある所は全部 0、最大 ≤ q。
      粒子 1 個の大きさの水の下の圧力は q·n_x の ±5 %（しぶきは遮らない）、厚さ 2 dp の板の下は 0。
出力：Unity/Build/FLIP44/smoke/S5/s5.json
"""
import hou, sys, os, json, glob, math
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip44")
import g44_tanklib as L

OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP44/smoke/S5"
R3 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs/R3"
os.makedirs(OUT, exist_ok=True)
FRAME = 3745
U10 = 35.0
Q = 0.5 * 1.2 * (U10 + 12.0) ** 2


def sec_frame(rd, frame):
    best = None
    for p in glob.glob(os.path.join(rd, "sec_c*_b*.npz")):
        b = os.path.basename(p); f0 = int(b[5:9])
        d = np.load(p)
        fr = list(map(int, d["frames"]))
        if frame in fr and frame >= f0 and (best is None or best[0] < f0):
            best = (f0, p, fr.index(frame))
    d = np.load(best[1])
    return d["sdf"][best[2]].astype(np.float64), json.loads(str(d["meta"])), best[1]


S0, meta, src = sec_frame(R3, FRAME)
ana = json.load(open(os.path.join(R3, "ana.json"), encoding="utf8"))
cfg = json.load(open(os.path.join(R3, "cfg.json"), encoding="utf8"))
XP = cfg["parms"]["x_p"]; DP = cfg["parms"]["dp"]; VOX = 2 * DP
OFF = ana["still_level_offset_m"]
nx, ny = meta["nx"], meta["ny"]
x0, dx, y0, dy = meta["x0"], meta["dx"], meta["y0"], meta["dy"]
XS = x0 + dx * np.arange(nx); YS = y0 + dy * np.arange(ny)
YTOP = 18.0

hou.hipFile.load(r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP44/g44_tank.hiplc", suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node("/obj/G44_SETUP/CTRL")
for k, v in dict(dp=DP, gridscale=2.0, ytop=YTOP, x_p=XP, wind_on=1.0, wind_mode=1.0, wind_q=Q, wind_t0=-10.0, wind_tramp=1.0, wind_t1=1e9,
                 wind_x0=XP, wind_x1=XP + 930.8582438581561, wind_tap=10.0, wind_band_vox=3.0, thin_mult=2.0).items():
    ctrl.parm(k).set(v)
geo_node = hou.node("/obj").createNode("geo", "S5")
DATA = os.path.join(OUT, "s5_field.npy")


def run_vex(S):
    """S（y, x の 2D）を z に 4 格子伸ばした surface と、0 の surfacepressure を作り、wind_pressure の本文で圧力を出す。"""
    np.save(DATA, S.astype(np.float32))
    for c in geo_node.children():
        c.destroy()
    ps = geo_node.createNode("python", "make")
    ps.parm("python").set('''
import numpy as np, hou
node = hou.pwd(); geo = node.geometry()
S = np.load(r"%s")
ny, nx = S.shape
dx = %r; x0 = %r; y0 = %r
bb = hou.BoundingBox(x0 - 0.5*dx, y0 - 0.5*dx, -2*dx, x0 + (nx - 0.5)*dx, y0 + (ny - 0.5)*dx, 2*dx)
geo.addAttrib(hou.attribType.Prim, "name", "")
v1 = geo.createVolume(nx, ny, 4, bb); v1.setAttribValue("name", "surface")
A = np.repeat(S[None, :, :], 4, axis=0).astype(np.float32)
v1.setAllVoxelsFromString(A.tobytes())
v2 = geo.createVolume(nx, ny, 4, bb); v2.setAttribValue("name", "surfacepressure")
v3 = geo.createVolume(nx, ny, 4, bb); v3.setAttribValue("name", "windsurf")
''' % (DATA, dx, x0, y0))
    w = geo_node.createNode("volumewrangle", "wind")
    w.setInput(0, ps)
    w.parm("vex_precision").set("64")
    w.parm("snippet").set(L.snippet("/obj/G44_SIM/wind_pressure"))
    g = w.geometry()
    errs = list(w.errors()) + list(ps.errors())
    vols = {p.attribValue("name"): p for p in g.prims()}
    v = vols["surfacepressure"]
    ws = np.frombuffer(vols["windsurf"].allVoxelsAsString(), dtype=np.float32)
    s0 = np.frombuffer(vols["surface"].allVoxelsAsString(), dtype=np.float32)
    globals()["WINDSURF_DIFF"] = float(np.abs(ws.astype(np.float64) - s0).max())
    globals()["WINDSURF_EQ"] = bool(globals()["WINDSURF_DIFF"] <= 1e-4)      # 写しは格子の中心で読むので、丸めの差だけ（格子 0.5 m の 0.02 %）
    r = v.resolution()
    A = np.frombuffer(v.allVoxelsAsString(), dtype=np.float32).reshape(r[2], r[1], r[0]).astype(np.float64)
    p0 = v.indexToPos((0, 0, 0))
    return A, errs, [p0[0], p0[1], p0[2]]


# ---------------------------------------------------------------- numpy で同じ決まり（DOP の VEX と別に書いた）
def sample(S, x, y):
    fx = (x - x0) / dx; fy = (y - y0) / dy
    fx = min(max(fx, 0.0), nx - 1.0); fy = min(max(fy, 0.0), ny - 1.0)
    i = min(int(math.floor(fx)), nx - 2); j = min(int(math.floor(fy)), ny - 2)
    wx = fx - i; wy = fy - j
    return ((S[j, i] * (1 - wx) + S[j, i + 1] * wx) * (1 - wy) + (S[j + 1, i] * (1 - wx) + S[j + 1, i + 1] * wx) * wy)


def covered_np(S, px, py):
    st = 0.5 * DP; need = 2.0 * DP * (1.0 - 1e-3)
    sp = sample(S, px, py)
    yin = py if sp < 0 else -1e9
    y = py
    while y < YTOP:
        yn = y + st
        s = sample(S, px, yn)
        if sp >= 0 and s < 0:
            yin = y + st * sp / (sp - s)
        elif sp < 0 and s >= 0:
            yout = y + st * sp / (sp - s)
            if yout - yin >= need:
                return True
            yin = -1e9
        sp = s; y = yn
    return bool(sp < 0 and YTOP - yin >= need)


def ref_np(S, j, i):
    """格子の中心 (i, j) の q·n_x と、上に水があるか（numpy）。"""
    gy, gx = np.gradient(S, dy, dx)
    return gy, gx


def eval_points(S, pts):
    gy, gx = np.gradient(S, dy, dx)
    out = []
    for (j, i) in pts:
        s = S[j, i]; g = np.array([gx[j, i], gy[j, i]]); gl = np.linalg.norm(g)
        n = g / gl
        psx, psy = XS[i] - n[0] * s, YS[j] - n[1] * s
        p0x, p0y = psx + n[0] * 0.5 * DP, psy + n[1] * 0.5 * DP
        cov = covered_np(S, p0x, p0y)
        out.append(dict(i=int(i), j=int(j), x_rel=float(XS[i] - XP), y=float(YS[j] - OFF), s=float(s), nx=float(n[0]), ny=float(n[1]),
                        p0x=float(p0x), p0y=float(p0y), covered=bool(cov), p_ref=0.0 if cov else float(Q * n[0])))
    return out


res = dict(note_ja="煙の試し S5（計画 §6、記録の読み方 9・10）", frame=FRAME, src=os.path.basename(src), q_Pa=Q, U10=U10, dp=DP, vox=VOX)
A, errs, p0 = run_vex(S0)
res["vex_errors"] = errs
Pz = A[2]       # z の 4 枚のうち 1 枚（どれも同じはず）
res["z_slices_identical"] = bool(all(np.array_equal(A[k], A[0]) for k in range(4)))
res["max_abs_p"] = float(np.abs(A).max()); res["max_le_q"] = bool(np.abs(A).max() <= Q * (1 + 1e-9))
# 頂（一番高い水）と範囲
water = S0 < 0
jt = np.where(water.any(1))[0].max(); ic = int(np.where(water[jt])[0].mean())
xc = XS[ic]; eta_c = YS[jt] - OFF
res["crest"] = dict(x_rel=float(xc - XP), eta_c=float(eta_c))
cand = [(j, i) for j in range(ny) for i in range(nx)
        if abs(S0[j, i]) < 0.5 * VOX and xc - 1.0 * eta_c <= XS[i] <= xc + 2.0 * eta_c and YS[j] > -20]
E = eval_points(S0, cand)
for e in E:
    e["p_vex"] = float(Pz[e["j"], e["i"]])
exposed = [e for e in E if not e["covered"] and abs(e["nx"]) >= 0.2]
covered = [e for e in E if e["covered"]]
exposed.sort(key=lambda e: e["x_rel"])
pick = [exposed[int(round(k))] for k in np.linspace(0, len(exposed) - 1, 20)] if len(exposed) >= 20 else exposed
for e in pick:
    e["rel_err"] = (e["p_vex"] - e["p_ref"]) / e["p_ref"]
res["exposed_20"] = pick
res["exposed_20_max_rel_err"] = float(max(abs(e["rel_err"]) for e in pick)) if pick else None
res["exposed_20_ok"] = bool(len(pick) == 20 and all(abs(e["rel_err"]) <= 0.05 for e in pick))
res["covered_n"] = len(covered)
res["covered_nonzero"] = [e for e in covered if e["p_vex"] != 0.0][:20]
res["covered_all_zero"] = bool(len(covered) > 0 and all(e["p_vex"] == 0.0 for e in covered))
res["covered_where"] = dict(y_min=min(e["y"] for e in covered) if covered else None, y_max=max(e["y"] for e in covered) if covered else None,
                            x_rel_min=min(e["x_rel"] for e in covered) if covered else None, x_rel_max=max(e["x_rel"] for e in covered) if covered else None)
# 全部の候補で VEX と numpy が合うか（記録）
dif = [abs(e["p_vex"] - e["p_ref"]) for e in E]
res["all_candidates"] = dict(n=len(E), max_abs_diff_Pa=float(max(dif)), n_diff_gt_5pct_q=int(sum(d > 0.05 * Q for d in dif)))

# ---------------------------------------------------------------- しぶきの試し（読み方 10）
front = [e for e in E if not e["covered"] and e["nx"] >= 0.3 and e["x_rel"] > float(xc - XP)]
best = min(front, key=lambda e: abs(((e["p0x"] - x0) / dx) - round((e["p0x"] - x0) / dx)))
ic_col = int(round((best["p0x"] - x0) / dx))
jd = int(round((best["p0y"] + 2.0 - y0) / dy))
XX, YY = np.meshgrid(XS, YS)
cx, cy = XS[ic_col], YS[jd]
drop = np.sqrt((XX - cx) ** 2 + (YY - cy) ** 2) - 0.5 * DP
Sd = np.minimum(S0, drop)
slab = np.maximum(np.abs(YY - cy) - DP, np.abs(XX - cx) - 2.0)
Ss = np.minimum(S0, slab)
Ad, e1, _ = run_vex(Sd)
As, e2, _ = run_vex(Ss)
pd_ = float(Ad[2][best["j"], best["i"]]); psl = float(As[2][best["j"], best["i"]])
cov_d = covered_np(Sd, best["p0x"], best["p0y"]); cov_s = covered_np(Ss, best["p0x"], best["p0y"])
res["droplet"] = dict(point=best, column_x_offset_m=float(best["p0x"] - cx), drop_center=[float(cx - XP), float(cy - OFF)], drop_min_sdf=float(drop.min()),
                      p_vex=pd_, p_ref=best["p_ref"], rel_err=(pd_ - best["p_ref"]) / best["p_ref"], numpy_covered=bool(cov_d),
                      ok=bool(abs((pd_ - best["p_ref"]) / best["p_ref"]) <= 0.05), errors=e1)
res["slab"] = dict(thickness_m=2 * DP, width_m=4.0, p_vex=psl, numpy_covered=bool(cov_s), ok=bool(psl == 0.0), errors=e2)
res["windsurf_copy_equal"] = WINDSURF_EQ
res["windsurf_copy_max_abs_diff_m"] = WINDSURF_DIFF
res["pass"] = bool(WINDSURF_EQ and res["exposed_20_ok"] and res["covered_all_zero"] and res["max_le_q"] and res["droplet"]["ok"] and res["slab"]["ok"] and not errs)
json.dump(res, open(os.path.join(OUT, "s5.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
print(json.dumps({k: res[k] for k in ("windsurf_copy_equal", "windsurf_copy_max_abs_diff_m", "crest", "max_abs_p", "max_le_q", "exposed_20_max_rel_err", "exposed_20_ok", "covered_n", "covered_all_zero",
                                       "covered_where", "all_candidates", "z_slices_identical", "pass")}, ensure_ascii=False))
print("droplet", {k: res["droplet"][k] for k in ("column_x_offset_m", "drop_min_sdf", "p_vex", "p_ref", "rel_err", "numpy_covered", "ok")})
print("slab", res["slab"])
