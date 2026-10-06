# -*- coding: utf-8 -*-
"""動画の道具（段階 Video）の共通：設定の読み込み、網目の時刻の表、置き方（計算の座標 → Unity）、二つの固定カメラ、
回り台の 12 方位、シルエットの点数（IoU・輪郭の平均距離。記録だけ）。py -3.10（numpy・cv2・PIL）。

置き方とカメラの決め方は P2 の道具（p2_common.place、p2_figs.clay）と同じ。動画の間は置き方もカメラも動かさない
（選んだ瞬間 t* の置き方を全部のコマに使う）。

設定（JSON）の例は Unity/Build/FLIP37/video_tools/README.md を見る。
"""
import os, sys, json, glob, math, time
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p2_common as C  # noqa: E402

REPO = r"G:/Unity/GreatWave_2026_Fresh"
BLENDER = r"G:/SteamLibrary/steamapps/common/Blender/blender.exe"
FFMPEG = r"G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
FFPROBE = r"G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffprobe.exe"
REF = REPO + "/Docs/References/Met_JP1847_DP130155.jpg"
R9_MESH = REPO + "/Unity/Build/Polish/sample06/fix/mesh/union_AS06R9_f1.json"
R9_SHA = "eb58bd07a636f8cde0099ee665fde943229d3c3bd6753e9abe89dcadaab77f79"
TOOLS_OUT = REPO + "/Unity/Build/FLIP37/video_tools"
SC = 0.5            # シルエットの解像度（960×540。p2_analyze と同じ）
FPS = 24.0
X_KEEP = (-160.0, 90.0)   # シルエットに使う網目：頂の x から −160〜+90 m（p2_analyze と同じ）

DEFAULTS = {
    "fps": 24,
    "render_res": [960, 540],       # 粘土の図の解像度（各カメラ）
    "hold_s": 2.0,
    "slow_last_s": 3.0,
    "slow_factor": 0.5,
    "max_mb": 30.0,
    "label": "物理だけ（誘導なし）",
    "marks": {},                    # {"jet_start": t, "t_star": t, "switch": t}（秒、計算の時刻）
    # 左前の斜め：見本06 の回り台と同じ方位の決め方（p2_common.tt_cam、0° が原画の側）で 320°（企画書 §3 の「回り台の 300〜330° あたり」）、
    # 頂の足元の 10 m 上を中心に、水平に 160 m 離れ、高さ 30 m、縦の画角 32°。②③（左肩）の段と唇の横顔が読める（R9 で確かめた）。
    # 流体では峰に沿ってほぼ左の端から見る向きで、水槽の左の端（計算の z ≈ −122 m）より約 40 m 外に立つ（手前に水槽の端の縁が見えることがある）。
    # P2 の図（p2_figs.clay）の決め方は {"yaw_deg": 45, "dist": 170, "height": 45, "vfov": 48, "center_up": 4}（az_deg を書かない）
    "leftfront": {"az_deg": 320.0, "dist": 160.0, "height": 30.0, "vfov": 32.0, "center_up": 10.0},
    "near_clip": 3.0,               # 原画カメラから 3 m 以内の面は描かない（p2_common.raster_mask と同じ）
    "crop_main": {"x": [-160.0, 90.0]},   # 主の二つの図で描く網目（頂からの計算の座標）。シルエットの点数と同じ範囲
    "tt": {"dist": 150.0, "height": 45.0, "center_up": 8.0,   # 縦の画角は見本06 と同じ 34°
           "crop": {"x": [-60.0, 35.0], "z": [-45.0, 45.0]}},   # 回り台：頂の足元を中心に、頂のまわりの箱だけ描く
    "r9": True,
    "turntable": True,
    "outer_tint": [0.66, 0.68, 0.70],   # 外の海（区間の "outer"、P2 の水面）の粘土の色。主役の範囲（P3、粘土の色 0.78/0.74/0.66）と見分ける。null で同じ色
    "threads": 4,
}


def load_cfg(path):
    cfg = json.load(open(path, encoding="utf8"))
    out = json.loads(json.dumps(DEFAULTS))
    for k, v in cfg.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    out["_cfg_path"] = os.path.abspath(path)
    out.setdefault("out_dir", os.path.join(TOOLS_OUT, os.path.splitext(os.path.basename(path))[0]))
    return out


def mesh_files(mesh_dir):
    """mesh_FFFF.npz の一覧 → [(t, path)]（t は npz の中の時刻）。"""
    res = []
    for f in sorted(glob.glob(os.path.join(mesh_dir, "mesh_*.npz"))):
        with np.load(f) as d:
            t = float(d["t"]) if "t" in d.files else (int(os.path.basename(f)[5:9]) - 1) / FPS
        res.append((t, f.replace("\\", "/")))
    return res


def timeline(cfg):
    """区間（segments）の網目をつなぐ。区間 i は [t0, t1) の網目を出す（最後の区間は t1 を含む）。
    戻り：[(t, path, seg_index)]、時刻の順。"""
    out = []
    segs = cfg["segments"]
    for i, s in enumerate(segs):
        mf = mesh_files(s["mesh_dir"])
        last = i == len(segs) - 1
        for t, p in mf:
            if t < s.get("t0", -1e9) - 1e-6:
                continue
            if (t > s.get("t1", 1e9) + 1e-6) or ((not last) and t >= s.get("t1", 1e9) - 1e-6):
                continue
            out.append((t, p, i))
    out.sort(key=lambda q: q[0])
    return out


def mesh_at(tl, t):
    """時刻 t に見せる網目：t 以下でいちばん近い網目（網目のない間は前の網目を保つ）。"""
    ts = np.array([q[0] for q in tl])
    k = int(np.searchsorted(ts, t + 0.01) - 1)   # 印の時刻は小数 3 桁で書くことが多いので 0.01 s の余裕
    return tl[max(k, 0)]


# ---------------------------------------------------------------- 区間の情報（粒子の間隔・外の海）

def run_json(seg):
    """区間の run_dir の run.json（P3 は run_A.json など、部分ごと）。なければ {}。"""
    rd = seg.get("run_dir")
    if not rd:
        return {}
    for nm in ["run.json"] + sorted(os.path.basename(f) for f in glob.glob(os.path.join(rd, "run_*.json"))):
        p = os.path.join(rd, nm)
        if os.path.isfile(p):
            try:
                return json.load(open(p, encoding="utf8"))
            except Exception:
                pass
    return {}


def seg_dp(seg):
    """区間の粒子の間隔（m）。設定の "dp" か、run_dir の run.json の parms.dp。分からなければ None。"""
    if seg.get("dp") is not None:
        return float(seg["dp"])
    v = (run_json(seg).get("parms") or {}).get("dp")
    return float(v) if v is not None else None


def outer_map(cfg, tl):
    """区間に "outer"（主役の範囲の外の海を描く粗い計算の網目）があれば、各網目に時刻のいちばん近い外の網目を対応させる。
    "outer": {"mesh_dir": P2 の mesh フォルダー, "hole": "auto"（既定。内の網目の x・z の外枠）か [x0, x1, z0, z1]（計算の座標）}
    戻り：{内の網目の path: {"mesh": 外の網目の path, "t": 外の時刻, "dt": 外 − 内（s）, "hole": ...}}"""
    res = {}
    cache = {}
    for t, path, si in tl:
        o = cfg["segments"][si].get("outer")
        if not o:
            continue
        if o["mesh_dir"] not in cache:
            cache[o["mesh_dir"]] = mesh_files(o["mesh_dir"])
        mf = cache[o["mesh_dir"]]
        if not mf:
            continue
        k = int(np.argmin([abs(q[0] - t) for q in mf]))
        res[path] = {"mesh": mf[k][1], "t": mf[k][0], "dt": round(mf[k][0] - t, 4), "hole": o.get("hole", "auto")}
    return res


def hole_of(P, hole):
    """外の海を抜く範囲 [x0, x1, z0, z1]（計算の座標）。"auto" は内の網目の x・z の外枠。"""
    if hole == "auto" or hole is None:
        return [float(P[:, 0].min()), float(P[:, 0].max()), float(P[:, 2].min()), float(P[:, 2].max())]
    return [float(v) for v in hole]


def outer_keep(Po, trio, hole):
    """外の網目の三角形のうち、範囲の外に頂点が一つでもあるものを残す（境目にすき間を作らず、少し重ねる）。"""
    x0, x1, z0, z1 = hole
    inside = (Po[:, 0] > x0) & (Po[:, 0] < x1) & (Po[:, 2] > z0) & (Po[:, 2] < z1)
    return trio[~inside[trio].all(1)]


def load_frame(path, outer=None):
    """見せる網目（計算の座標）：内の網目に、外の海（outer があれば）を足した物。戻り P (float64)、tri (int64)。"""
    with np.load(path) as d:
        P = d["P"].astype(np.float64); tri = d["tri"].astype(np.int64)
    if outer:
        with np.load(outer["mesh"]) as d:
            Po = d["P"].astype(np.float64); to = d["tri"].astype(np.int64)
        to = outer_keep(Po, to, hole_of(P, outer.get("hole", "auto")))
        used = np.unique(to)                      # 使う点だけ残す（抜いた範囲の点が頂の高さや頂の位置に入らないように）
        remap = np.full(len(Po), -1, np.int64); remap[used] = np.arange(len(used))
        tri = np.concatenate([tri, remap[to] + len(P)])
        P = np.concatenate([P, Po[used]])
    return P, tri


# ---------------------------------------------------------------- 置き方

def anchor_from_mesh(P, xwin=(380.0, 706.0)):
    """網目のいちばん高い所（x の窓の中）。水しぶきの小さな塊に引かれないように、上から 20 番目の高さを頂の高さとし、
    その高さから 0.3 m 以内の点の z の中央・x の中央を頂の位置とする（峰に沿って同じ高さの長い波では z の真ん中になる）。"""
    m = (P[:, 0] >= xwin[0]) & (P[:, 0] <= xwin[1])
    Q = P[m]
    k = np.argsort(-Q[:, 1])[: min(20, len(Q))]
    yc = float(Q[k[-1], 1])
    top = Q[Q[:, 1] >= yc - 0.3]
    top = top[top[:, 1] <= Q[k[0], 1] + 1e-6]
    zc = float(np.median(top[:, 2]))
    near = top[np.argsort(np.abs(top[:, 2] - zc))[: max(1, len(top) // 4)]]
    return [float(np.median(near[:, 0])), yc, zc]


def eta_under(P, xc, zc, r=3.0):
    """計算の座標 (xc, zc) の真上の水面の高さ（半径 r の網目の点の最高）。点がなければ None。"""
    m = (np.abs(P[:, 0] - xc) < r) & (np.abs(P[:, 2] - zc) < r)
    return float(P[m, 1].max()) if m.any() else None


def camera_in_sim(anchor, psi, s, O):
    cam = C.painting_cam()
    T, E = C.TE(psi)
    Qc = (cam.pos - np.asarray(O)) / s
    return float(Qc @ T + anchor[0]), float(Qc @ E + anchor[2])


def fit_placement(P, tri, anchor, psis=(0, 10, 20, 30, 40, 50, 60), scales=(0.9, 1.0, 1.1)):
    """p2_analyze.fit_painting と同じ探し方（原画視点のシルエットの IoU が最大の ψ・倍率。カメラが水の中になる置き方は除く）。
    水の高さは網目から測る（hf.npz のない計算でも使えるように）。"""
    cam = C.painting_cam(SC)
    pm, outer, inner = C.painting_mask(SC)
    win = C.window_mask(SC)
    keep = (P[:, 0] > anchor[0] + X_KEEP[0]) & (P[:, 0] < anchor[0] + X_KEEP[1])
    tk = tri[keep[tri].all(1)]
    best = None
    for psi in psis:
        for s in scales:
            U, O = C.place(P, anchor, psi, s, cam)
            xc, zc = camera_in_sim(anchor, psi, s, O)
            e = eta_under(P, xc, zc)
            if e is not None and e * s > cam.pos[1] - 1.0:
                continue
            m = C.raster_mask(cam, U, tk) & win
            iou = (m & pm).sum() / max((m | (pm & win)).sum(), 1)
            if best is None or iou > best["iou"]:
                best = {"psi_deg": psi, "scale": s, "iou": float(iou), "anchor": anchor, "O": O.tolist(),
                        "camera_in_sim": [xc, zc], "eta_under_camera": e}
    return best


def resolve_placement(cfg, tl):
    """設定の placement を決める。
    - {"anchor": [...], "psi_deg": .., "scale": ..}：そのまま使う
    - "analysis"：t* の区間の analysis.json の best（P2 の解析）。t* と best の時刻が 0.05 s 以上違えば fit に切り替える
    - "fit"（既定）：t* の網目で fit_placement"""
    pl = cfg.get("placement", "fit")
    tstar = cfg["marks"].get("t_star")
    t_, path, si = mesh_at(tl, tstar if tstar is not None else tl[-1][0])
    if isinstance(pl, dict):
        q = dict(pl)
        q.setdefault("source", "設定の値")
    else:
        q = None
        if pl == "analysis":
            # t* の区間の analysis.json を先に、なければほかの区間（P3 の区間に解析がなく、P2 の区間にある場合。計算の座標は同じ）
            order = [si] + [i for i in range(len(cfg["segments"])) if i != si]
            for i in order:
                ap = os.path.join(cfg["segments"][i].get("run_dir", ""), "analysis.json")
                if not (cfg["segments"][i].get("run_dir") and os.path.isfile(ap)):
                    continue
                b = json.load(open(ap, encoding="utf8")).get("best") or {}
                if b and abs(b["t"] - t_) < 0.05:
                    q = {"anchor": b["anchor"], "psi_deg": b["psi_deg"], "scale": b["scale"],
                         "source": "analysis.json の best（%s f%04d）" % (os.path.basename(os.path.normpath(cfg["segments"][i]["run_dir"])), b["frame"])}
                    break
        if q is None:
            P, tri = load_frame(path, outer_map(cfg, [(t_, path, si)]).get(path))
            anc = cfg.get("anchor") or anchor_from_mesh(P)
            b = fit_placement(P, tri, anc)
            q = {"anchor": b["anchor"], "psi_deg": b["psi_deg"], "scale": b["scale"], "source": "t*=%.2f s の網目で当てはめ（IoU %.3f）" % (t_, b["iou"])}
    T, E = C.TE(q["psi_deg"])
    pc = C.painting_cam()
    U0, O = C.place(np.array([[q["anchor"][0], 0, q["anchor"][2]]]), q["anchor"], q["psi_deg"], q["scale"], pc)
    q.update({"T": T.tolist(), "E": E.tolist(), "O": O.tolist(), "U_anchor_ground": U0[0].tolist(), "t_mesh": t_, "mesh": path})
    return q


# ---------------------------------------------------------------- カメラ

def cam_json(cam, name):
    return {"name": name, "pos": cam.pos.tolist(), "fwd": cam.f.tolist(), "up": [0, 1, 0], "vfov": float(cam.vfov)}


def leftfront_cam(pl, lf):
    """左前の斜め。
    - az_deg があるとき：見本06 の回り台と同じ方位の決め方（方位 + 6.95°、0° が原画の側、270° が左）。中心は頂の足元の center_up m 上、
      水平に dist m 離れ、目の高さ height m。世界に固定（波の進む向き ψ によらない）。
    - az_deg がないとき：p2_figs.clay と同じ決め方。頂の足元から、進む向き +T と画面の左 −E の間 yaw_deg の向きへ dist m、高さ height m。"""
    U0 = np.array(pl["U_anchor_ground"])
    ctr = U0 + np.array([0, lf.get("center_up", 4.0), 0])
    if "az_deg" in lf:
        a = math.radians(lf["az_deg"] + 6.95)
        eye = np.array([ctr[0] + lf["dist"] * math.sin(a), lf["height"], ctr[2] - lf["dist"] * math.cos(a)])
        return C.Cam(eye, ctr - eye, (0, 1, 0), lf["vfov"])
    T = np.array(pl["T"]); E = np.array(pl["E"])
    a = math.radians(lf["yaw_deg"])
    dirh = math.cos(a) * T - math.sin(a) * E
    eye = U0 + lf["dist"] * dirh + np.array([0, lf["height"], 0])
    return C.Cam(eye, ctr - eye, (0, 1, 0), lf["vfov"])


def main_cams(cfg, pl):
    return [cam_json(C.painting_cam(), "painting"), cam_json(leftfront_cam(pl, cfg["leftfront"]), "leftfront")]


def tt_cams(pl, tt):
    """回り台の 12 方位。向きの決め方は見本06 の回り台（p2_common.tt_cam：方位 az に 6.95° を足し、0° が原画の側）。
    中心は頂の足元の center_up m 上、半径 dist m、目の高さ height m（流体の波は見本06 より大きいので遠くから見る）。
    R9 も同じカメラで描く。"""
    c = np.array(pl["U_anchor_ground"]) + np.array([0.0, tt["center_up"], 0.0])
    return [cam_json(C.tt_cam(az, center=c, R=tt["dist"], eye_y=tt["height"]), "tt%03d" % az) for az in range(0, 360, 30)]


# ---------------------------------------------------------------- 点数（記録だけ）

_PM = None


def score_mesh(P, tri, pl):
    """固定の置き方での原画視点のシルエット：IoU（窓の中）・原画の輪郭の点からシルエットの縁までの距離（1920 表示の画素）。"""
    global _PM
    if _PM is None:
        _PM = (C.painting_cam(SC),) + C.painting_mask(SC) + (C.window_mask(SC),)
    cam, pm, outer, inner, win = _PM
    a = pl["anchor"]
    keep = (P[:, 0] > a[0] + X_KEEP[0]) & (P[:, 0] < a[0] + X_KEEP[1])
    tk = tri[keep[tri].all(1)]
    U, O = C.place(P, a, pl["psi_deg"], pl["scale"], cam)
    m = C.raster_mask(cam, U, tk)
    mw = m & win
    iou = (mw & pm).sum() / max((mw | (pm & win)).sum(), 1)
    od = C.outline_distance(mw, outer, inner, SC) or {}
    xc, zc = camera_in_sim(a, pl["psi_deg"], pl["scale"], O)
    e = eta_under(P, xc, zc)
    return {"iou": float(iou), "mean_px": od.get("mean_px"), "median_px": od.get("median_px"),
            "eta_under_camera": e, "camera_wet": bool(e is not None and e * pl["scale"] > C.CAM_POS[1] - 0.3),
            "crest_y": float(P[:, 1].max())}, m


def overlap_image(m, scale=SC):
    """シルエットの重なりの図（緑＝両方、橙＝流体だけ、青＝原画だけ）。"""
    pm, _, _ = C.painting_mask(scale)
    win = C.window_mask(scale)
    img = np.full(pm.shape + (3,), 245, np.uint8)
    img[~win] = 225
    img[m & pm] = (90, 170, 90)
    img[m & ~pm] = (235, 140, 60)
    img[~m & pm & win] = (70, 110, 210)
    return img


class Timer:
    def __init__(self):
        self.t = {}

    def __call__(self, name):
        tm = self

        class _T:
            def __enter__(s):
                s.t0 = time.time()

            def __exit__(s, *a):
                tm.t[name] = round(tm.t.get(name, 0) + time.time() - s.t0, 2)
        return _T()
