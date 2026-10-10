# -*- coding: utf-8 -*-
"""RT48（Q48 の案 1：FLIP42 R3 の断面を Unity で毎フレーム再生）の計画の数を、R3 の記録から出す（読むだけ。py -3.10）。
R3 のファイルは開いて読むだけで、書き換えない。
出力: Unity/Build/RT48/plan/plan_numbers.json
使い方: py -3.10 p_inspect.py
"""
import json, glob, os, hashlib, time
import numpy as np
from skimage import measure

R3 = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs/R3/"
OUT = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48/plan/plan_numbers.json"

cfg = json.load(open(R3 + "cfg.json", encoding="utf8"))
shape = json.load(open(R3 + "shape.json", encoding="utf8"))
run0 = json.load(open(R3 + "run.json", encoding="utf8"))
XP = float(cfg["parms"]["x_p"])               # 造波板の位置（場面の x）。位置は造波板からの距離で書く
OFF = float(shape["still_level_offset_m"])    # 静かな水面のずれ（0.117 m）。高さはここから測る
FPS = 24.0
HULL = 12.0        # 船の水線の長さ【推定：押送船ほどの大きさ。計画 §3】
EYE = 1.2          # 水線から目までの高さ【推定：座った人。計画 §3】
PXDEG = 18.0       # PSVR2 の片眼の画素の目安（2000 px ÷ 約 110°）【推定】
X_ONSET = shape["C"]["x_onset"]; T_ONSET = shape["C"]["t_onset"]
X_TOUCH = shape["C"]["x_touch"]; T_TOUCH = shape["C"]["t_touch"]
T_JET2, X_JET2 = 157.1, 548.9                 # 2 つ目の噴流が前の面の低い所に落ちた時（FLIP_Plunging_ja.md §3）
LIP_REACH, LIP_THICK = 3.65, 1.06             # 最初の接触までの唇の最大（同 §4）
WIN = (100.0, 925.0)                          # 再生する範囲（造波板からの距離）。計画 §2
F_FIRST, F_LAST = 3319, 3889                  # 138.25 s〜162.0 s


def t_of(f):
    return (f - 1) / FPS


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ---- 記録の索引（重なった塊は同じ値。最初に見つけた方を使う）
sec_idx, hf_idx, used = {}, {}, set()
for fn in sorted(glob.glob(R3 + "sec_*.npz")):
    d = np.load(fn)
    for i, f in enumerate(d["frames"]):
        sec_idx.setdefault(int(f), (fn, i))
for fn in sorted(glob.glob(R3 + "hf_c*.npz")):
    d = np.load(fn)
    for i, f in enumerate(d["frames"]):
        hf_idx.setdefault(int(f), (fn, i))
_cache = {}


def load(fn):
    if fn not in _cache:
        _cache[fn] = np.load(fn)
        used.add(fn)
    return _cache[fn]


def sec(f):
    fn, i = sec_idx[f]
    d = load(fn)
    m = json.loads(str(d["meta"]))
    S = d["sdf"][i].astype(np.float32)
    xs = m["x0"] + m["dx"] * np.arange(m["nx"]) - XP
    ys = m["y0"] + m["dy"] * np.arange(m["ny"]) - OFF
    return S, xs, ys, m


def hf(f):
    fn, i = hf_idx[f]
    d = load(fn)
    return d["eta"][i] - OFF, d["x"] - XP, d["z"]


out = {"date": time.strftime("%Y-%m-%d %H:%M:%S"), "tool": "Tools/GWWaveGen/rt48/p_inspect.py",
       "consts": {"x_p": XP, "still_offset_m": OFF, "fps": FPS, "hull_m": HULL, "eye_m": EYE, "px_per_deg": PXDEG,
                  "onset": [T_ONSET, X_ONSET], "first_contact": [T_TOUCH, X_TOUCH], "jet2": [T_JET2, X_JET2],
                  "lip_max_reach_thick": [LIP_REACH, LIP_THICK], "window_rel": WIN, "frames": [F_FIRST, F_LAST]}}

# ---- 1. 記録の形
S, xs, ys, m = sec(3714)
fn0 = sec_idx[3714][0]
d0 = load(fn0)
e0, hx, hz = hf(3714)
out["records"] = {
    "sec": {"frames": [min(sec_idx), max(sec_idx)], "n": len(sec_idx), "dtype": str(d0["sdf"].dtype), "dx": m["dx"], "dy": m["dy"],
            "x_rel": [float(xs[0]), float(xs[-1])], "y_rel": [float(ys[0]), float(ys[-1])], "clip_m": m["clip_m"], "z": m["z"]},
    "hf": {"frames": [min(hf_idx), max(hf_idx)], "n": len(hf_idx), "dx": float(hx[1] - hx[0]), "x_rel": [float(hx[0]), float(hx[-1])],
           "z_nodes": [float(v) for v in hz]},
    "grid": run0["grid"], "particles_max": run0.get("particles_max"),
}

# ---- 2. 唇の細かさ：かぶさった列（下に空気がある列）の数と、一番上の水の厚み（節の数）
lip = []
for f in list(range(3714, 3746, 2)) + [3750, 3760]:
    S, xs, ys, m = sec(f)
    j0 = int(np.searchsorted(ys, -10.0))
    sub = (S < 0)[j0:, :]
    ch = np.abs(np.diff(sub.astype(np.int8), axis=0)).sum(0)
    multi = np.where(ch > 1)[0]
    th = []
    for ix in multi:
        col = sub[:, ix]
        jt = len(col) - 1 - int(np.argmax(col[::-1]))
        k = jt
        while k >= 0 and col[k]:
            k -= 1
        th.append(jt - k)
    lip.append({"frame": f, "t": t_of(f), "overhang_cols": int(len(multi)),
                "overhang_x_rel": [float(xs[multi].min()), float(xs[multi].max())] if len(multi) else None,
                "top_run_nodes_min_med_max": [int(min(th)), int(np.median(th)), int(max(th))] if th else None})
out["lip_resolution"] = {"rows": lip, "note": "節の間隔 0.5 m。唇の厚み 1.06 m は節 2 個、+0.2 Tc の 0.7 m は 1〜2 個"}

# ---- 3. 板の厚さの向きの水面の違い（一番上の水面、内側の 3 節）
zvar = []
for f in (3600, 3680, 3714, 3745, 3770, 3800):
    e, x, z = hf(f)
    msk = (x > 300) & (x < 700)
    dev = np.nanmax(np.abs(e[1:4][:, msk] - e[2][msk]), 0)
    zvar.append({"frame": f, "t": t_of(f), "inner3_dev_max_m": float(np.nanmax(dev)), "inner3_dev_p99_m": float(np.nanpercentile(dev, 99))})
out["z_variation"] = zvar

# ---- 4. 頂の動き（shape.json の行）
rows = {r["frame"]: r for r in shape["rows"]}
out["crest_track"] = [{"t": t_of(f), "xc_rel": rows[f]["xc_rel"], "eta_c": rows[f]["eta_c"]}
                      for f in range(3319, 3890, 24) if f in rows]

# ---- 5. 船の位置：かぶさった水（多価の列）が船体の長さ（±6 m）に初めて入る時刻
mv = {}
for f in range(3700, F_LAST + 1):
    S, xs, ys, m = sec(f)
    j0 = int(np.searchsorted(ys, -10.0))
    sub = (S < 0)[j0:, :]
    ch = np.abs(np.diff(sub.astype(np.int8), axis=0)).sum(0)
    mv[f] = xs[ch > 1]
table = []
for xb in range(555, 606):
    tt = None
    for f in range(3745, F_LAST + 1):
        if np.any((mv[f] >= xb - HULL / 2) & (mv[f] <= xb + HULL / 2)):
            tt = t_of(f)
            break
    table.append({"x_boat_rel": xb, "D_contact": xb - X_TOUCH, "D_onset": xb - X_ONSET, "overturned_on_hull_t": tt})
need = T_JET2 + 1.0
xb_sel = next(r["x_boat_rel"] for r in table if r["overturned_on_hull_t"] is not None and r["overturned_on_hull_t"] >= need)
t_hit = next(r["overturned_on_hull_t"] for r in table if r["x_boat_rel"] == xb_sel)
f_end_boat = int(round(t_hit * FPS)) + 1 - 1      # かぶさった水が船体に入るコマの 1 つ前
out["boat_table"] = table
out["boat_rule"] = {"rule": "かぶさった水が船体に入る時刻が、2 つ目の噴流の着水（157.1 s）の 1.0 s 後以上になる、いちばん近い位置",
                    "need_t": need, "x_boat_rel": xb_sel, "hit_t": t_hit, "clip_end_frame": f_end_boat, "clip_end_t": t_of(f_end_boat)}

# 船の上下・縦揺れ（一番上の水面、板の真ん中の節、船体の 9 点の平均と最小二乗の傾き）
hx_pts = np.linspace(-HULL / 2, HULL / 2, 9)
heave, pitch, tt = [], [], []
for f in range(F_FIRST, f_end_boat + 1):
    e, x, z = hf(f)
    yy = np.interp(xb_sel + hx_pts, x, e[2])
    heave.append(float(yy.mean()))
    pitch.append(float(np.degrees(np.arctan(np.polyfit(hx_pts, yy, 1)[0]))))
    tt.append(t_of(f))
heave, pitch = np.array(heave), np.array(pitch)
out["boat_motion"] = {"heave_min_max_m": [float(heave.min()), float(heave.max())],
                      "pitch_min_max_deg": [float(pitch.min()), float(pitch.max())],
                      "heave_rate_max_mps": float(np.max(np.abs(np.diff(heave))) * FPS),
                      "pitch_rate_max_degps": float(np.max(np.abs(np.diff(pitch))) * FPS),
                      "note": "縦揺れは船体の 9 点の水面の傾き（+x＝波の進む向きへ上る時を正）。船首は −x（波の来る向き）。船の動きの式は計画 §3"}


def view(f):
    r = rows[f]
    i = f - F_FIRST
    eye = heave[i] + EYE
    dist = xb_sel - r["xc_rel"]
    return {"t": t_of(f), "crest_x_rel": r["xc_rel"], "eta_c": r["eta_c"], "eye_y": float(eye), "dist_m": float(dist),
            "elev_deg": float(np.degrees(np.arctan((r["eta_c"] - eye) / dist)))}


f_on = shape["onset"]["frame"]; f_to = shape["touchdown"]["frame"]
dl = xb_sel - X_TOUCH

# 巻く頂を 141.25 s（断面の範囲の左の端に入った時）から一番上の水面（板の真ん中の節）で前へさかのぼる。
# shape.json の行の頂は断面の範囲の中で一番高い頂なので、141.25 s より前は一つ前の頂（394 m・5.0 m）を指している。
track, xprev = [], None
for f in range(3391, F_FIRST - 1, -1):
    e, x, z = hf(f)
    if xprev is None:
        msk = (x > 300) & (x < 330)
    else:
        msk = (x > xprev - 8) & (x < xprev + 2)
    j = int(np.argmax(np.where(msk, e[2], -99.0)))
    xprev = float(x[j])
    track.append({"t": t_of(f), "x_rel": xprev, "eta": float(e[2][j]), "dist_to_boat": xb_sel - xprev,
                  "elev_deg": float(np.degrees(np.arctan((e[2][j] - (heave[f - F_FIRST] + EYE)) / (xb_sel - xprev))))})
track = track[::-1]
out["view_at_boat"] = {"onset": view(f_on), "first_contact": view(f_to),
                       "lip_thick_deg": float(np.degrees(LIP_THICK / dl)), "lip_thick_px": float(np.degrees(LIP_THICK / dl) * PXDEG),
                       "lip_reach_deg": float(np.degrees(LIP_REACH / dl)), "lip_reach_px": float(np.degrees(LIP_REACH / dl) * PXDEG),
                       "plunging_crest_before_141s": track[::12]}

# ---- 6. 主な曲線の長さ（粗い記録で見積もる：断面の範囲は 0 の等高線、外は一番上の水面）
lens = []
for f in range(F_FIRST, F_LAST + 1, 10):
    S, xs, ys, m = sec(f)
    j0 = int(np.searchsorted(ys, -12.0))
    cs = measure.find_contours(S[j0:], 0.0)
    main = max(cs, key=len)
    p = np.stack([xs[0] + main[:, 1] * m["dx"], ys[j0] + main[:, 0] * m["dy"]], 1)
    L_in = float(np.sum(np.hypot(*np.diff(p, axis=0).T)))
    e, x, z = hf(f)
    L_out = 0.0
    for a, b in ((WIN[0], xs[0]), (xs[-1], WIN[1])):
        msk = (x >= a) & (x <= b)
        L_out += float(np.sum(np.hypot(np.diff(x[msk]), np.diff(e[2][msk]))))
    lens.append(L_in + L_out)
Lmax = max(lens)
N = 8192
out["curve"] = {"length_max_m": Lmax, "length_min_m": min(lens), "N_points": N, "spacing_max_m": Lmax / (N - 1),
                "bytes_per_frame": N * 2 * 4, "frames": F_LAST - F_FIRST + 1,
                "bytes_total": N * 2 * 4 * (F_LAST - F_FIRST + 1)}

# ---- 7. 計算し直しの量の見積もり
vol_tank = cfg["parms"]["Lx"] * cfg["parms"]["h0"] * cfg["parms"]["Lz"]
pmax_r3 = 11269961  # chain.log の最後の起動の pts（R3 の最大）
dens = pmax_r3 / vol_tank
vol_win = (WIN[1] - WIN[0]) * 8.0 * cfg["parms"]["Lz"] * 1.05   # 静かな水面から 8 m 下まで、頂の分 5 %
npw = dens * vol_win
ck = sorted(glob.glob(R3 + "ckpt/v.*.sim"))
ck_b = [os.path.getsize(p) for p in ck]
out["rerun"] = {"particles_per_m3": dens, "window_volume_m3": vol_win, "particles_per_frame": npw,
                "bytes_per_frame_P32_v16": npw * (12 + 6), "bytes_total_P32_v16": npw * 18 * (F_LAST - F_FIRST + 1),
                "ckpt_3318": R3 + "ckpt/v.3318.sim", "ckpt_3318_bytes": os.path.getsize(R3 + "ckpt/v.3318.sim"),
                "ckpt_mean_bytes": float(np.mean(ck_b)),
                "r3m_hours_3319_3800": 0.974, "note": "R3m（R3 の 3318 コマ目から、前処理だけ替えた）は 3319〜3800 コマに起動 2 回・0.974 時間（chain.log）"}

out["inputs_sha256"] = {os.path.basename(p): sha(p) for p in sorted(used | {R3 + "cfg.json", R3 + "shape.json", R3 + "run.json"})}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(out, open(OUT, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
print(json.dumps({k: out[k] for k in ("boat_rule", "boat_motion", "view_at_boat", "curve", "rerun")}, ensure_ascii=False, indent=1, default=float))
