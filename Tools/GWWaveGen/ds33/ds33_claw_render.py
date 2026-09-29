# -*- coding: utf-8 -*-
"""設計33（爪の部）：numpy の z バッファで描いた図と動画（Unity の描画ではない。HMD 実機ではない）。

描き方（進行役の仮の NPR。段階7 の色と線の前）：
  - 主役波のシート（本体の列 18〜394）：画素ごとに三角形の重心座標から (行, 列) → 29修正01 の色面の UV3 → テクセルの色区（白・淡い水色・藍中・藍濃）。
    白の色区は、そのコマで T_white に達していない所を淡い水色で描く（設計31 の白の出現）。
  - 爪：上面（φ 45〜135°）を調色板の白、縁の側面と下面を淡い水色（原画の爪の藍の線の内側の淡い影に当たる）、根元の白の円を白。
  - 線：ID の境（爪と爪・爪とシート・爪と空・シートと空）と、シートの奥行きの段差を藍の線（1 px）で描く。
出力（Unity/Build/Design/33/claws/fig/）：
  fig_ds33_tstar_render.png（原画視点 t* の爪あり）、fig_ds33_tstar_overlay.png（原画に爪の輪郭と一覧の中心線を重ねた図）、
  fig_ds33_rows_{upper,middle,boat,bregion}.png（列ごとの拡大の重ね図）、fig_ds33_types.png（型の試作：型 × 成長の段）、
  fig_ds33_growth_stills.png（成長の静止画）、fig_ds33_single_growth.png（代表の爪の成長の段）、ds33_claws_growth_30fps.mp4（成長 → 曲がり → t* の保持）、
  ds33_contour_tstar.json と fig_ds33_contour_tstar.png（原画視点の輪郭 78・130・131・132・72 の、爪なし・爪ありの比べ。numpy の ID の描画）。
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ds33_common as U  # noqa: E402
import ds33_claw_rig as G  # noqa: E402
import ds33_claw_anim as A  # noqa: E402

K = U.K
sys.path.insert(0, U.REPO + "/Tools/GWWaveGen/ds32")
from ds32_claw_figs import put, label  # noqa: E402

TYPE_COL = {"T1": (40, 170, 40), "T2": (0, 140, 255), "branch": (200, 0, 200), "T4": (220, 120, 0), "T3": (0, 0, 220), "T5": (120, 120, 120)}


class Scene:
    def __init__(self, out):
        self.out = out
        self.rig = U.jload(os.path.join(out, "ds33_claw_rig.json"))
        self.lay = U.jload(os.path.join(out, "ds33_claw_layout.json"))
        self.claws = self.rig["claws"]
        self.nc = len(self.claws)
        nv = self.lay["vertices"]
        self.V = np.memmap(os.path.join(out, "ds33_claw_frames_f32.bin"), np.float32, "r", shape=(U.NFR, nv, 3))
        self.T = np.fromfile(os.path.join(out, "ds33_claw_tris_i32.bin"), np.int32).reshape(-1, 3)
        self.attr = np.fromfile(os.path.join(out, "ds33_claw_tri_attr_u16.bin"), np.uint16).reshape(-1, 2).astype(np.int64)
        self.SK = np.memmap(os.path.join(out, "ds33_claw_skel_f32.bin"), np.float32, "r", shape=(U.NFR, self.nc, 36))
        self.hero = K.Pkg(U.HERO)
        self.R, self.C = self.hero.R, self.hero.C
        warp = U.jload(U.WARP)
        self.taus = np.interp(np.arange(U.NFR) / U.FPS, np.array(warp["t"]), np.array(warp["tau"]))
        self.spec = U.jload(U.TRUTH)
        self.cam = U.CamWH(self.spec, 1920, 1080)
        self.Tb = K.grid_tris(self.R, self.C, U.BODY[0], U.BODY[1])
        self.ncol = U.BODY[1] - U.BODY[0]
        w = U.jload(U.W31.UVW)
        self.uW = np.array(w["uWarp"]); self.vW = np.array(w["vWarp"])
        S = 4096
        sdf = np.fromfile(U.W31.SDF, np.uint8).reshape(S, S, 4)
        self.tcls = np.argmax(sdf, axis=-1).astype(np.int8)
        del sdf
        self.tw = np.fromfile(U.HERO + "/" + self.hero.k["twhite_file"], "<f4").reshape(self.R, self.C).astype(np.float64)
        self.tw = np.where(self.tw > 1e8, 1e9, self.tw)
        self.col = {0: U.bgr("white"), 1: U.bgr("mizuiro"), 2: U.bgr("ai_mid"), 3: U.bgr("ai_dark")}

    def claw_tris(self, f, only=None):
        vis = self.SK[f, :, 34] > 0.5
        if only is not None:
            vis = vis & only
        sel = vis[self.attr[:, 0]]
        V = np.asarray(self.V[f], np.float64)
        return V[self.T[sel]], np.nonzero(sel)[0]

    def render(self, cam, f, claws=True, only=None, sheet=True, lines=True, white_rule=True):
        tau = float(self.taus[f])
        X = self.hero.world(tau)
        tl, il = [], []
        ns = 0
        if sheet:
            St = X.reshape(-1, 3)[self.Tb]
            tl.append(St); il.append(np.arange(1, len(St) + 1)); ns = len(St)
        if claws:
            Ct, ci = self.claw_tris(f, only)
            if len(Ct):
                tl.append(Ct); il.append(ns + 1 + ci)
        tris = np.concatenate(tl); ids = np.concatenate(il).astype(np.int64)
        idb, zb = U.raster(cam, tris, ids)
        H, W = idb.shape
        img = np.empty((H, W, 3), np.uint8); img[:] = U.bgr("sky")
        # シート
        m = (idb >= 1) & (idb <= ns)
        if m.any():
            ys, xs = np.nonzero(m)
            t = idb[ys, xs] - 1
            d = cam.ray(xs.astype(np.float64), ys.astype(np.float64))
            A_ = St[t, 0]; B_ = St[t, 1]; C_ = St[t, 2]
            _, u, v = U.ray_tri_many(cam.pos, d, A_, B_, C_)
            u = np.clip(u, 0, 1); v = np.clip(v, 0, 1)
            rr, cc = U.tri_to_rc(t, u, v, self.ncol, U.BODY[0])
            uu = np.interp(cc, np.arange(self.C), self.uW); vv = np.interp(rr, np.arange(self.R), self.vW)
            tx = np.clip(np.round(uu * 4096 - 0.5).astype(int), 0, 4095); ty = np.clip(np.round(vv * 4096 - 0.5).astype(int), 0, 4095)
            cls = self.tcls[ty, tx].astype(int)
            if white_rule:
                twp = U.bilin(self.tw[..., None], rr, cc)[:, 0]
                cls = np.where((cls == 0) & (tau < twp), 1, cls)
            cols = np.array([self.col[k] for k in range(4)], np.uint8)
            img[ys, xs] = cols[cls]
        # 爪
        mc = idb > ns
        if mc.any():
            kd = self.attr[idb[mc] - ns - 1, 1]
            cc2 = np.array([U.bgr("white"), U.bgr("mizuiro"), U.bgr("white")], np.uint8)
            img[mc] = cc2[kd]
        if lines:
            grp = np.where(idb > ns, 100000 + self.attr[np.clip(idb - ns - 1, 0, len(self.attr) - 1), 0], np.where(idb > 0, 1, 0))
            e = np.zeros((H, W), bool)
            e[:, 1:] |= grp[:, 1:] != grp[:, :-1]
            e[1:, :] |= grp[1:, :] != grp[:-1, :]
            z = np.where(zb > 0, 1.0 / np.maximum(zb, 1e-9), 1e4)
            lz = np.log(z)
            gx = np.zeros_like(lz); gy = np.zeros_like(lz)
            gx[:, 1:] = np.abs(np.diff(lz, axis=1)); gy[1:, :] = np.abs(np.diff(lz, axis=0))
            e |= (np.maximum(gx, gy) > 0.04) & (idb > 0)
            img[e] = U.bgr("line")
        return img, idb, ns

    def painting_disp(self, alpha=0.55):
        img = cv2.imdecode(np.fromfile(U.PAINT, np.uint8), cv2.IMREAD_COLOR)
        a = U.A_DISP
        Af = np.array([[a, 0, a * 0.5 - 0.5 + 156.66153], [0, a, a * 0.5 - 0.5]], np.float32)
        disp = cv2.warpAffine(img, Af, (1920, 1080), flags=cv2.INTER_AREA, borderValue=(245, 245, 245))
        return disp

    def painting_crop(self, x0, y0, s, W, H):
        """原画を表示の座標の矩形 [x0, …) で s 倍にした画像（CropCam と同じ写し方）。"""
        img = cv2.imdecode(np.fromfile(U.PAINT, np.uint8), cv2.IMREAD_COLOR)
        a = U.A_DISP * s
        off = (s - 1) * 0.5
        Af = np.array([[a, 0, (U.A_DISP * 0.5 - 0.5 + 156.66153 - x0) * s + off], [0, a, (U.A_DISP * 0.5 - 0.5 - y0) * s + off]], np.float32)
        return cv2.warpAffine(img, Af, (W, H), flags=cv2.INTER_AREA if a < 1 else cv2.INTER_CUBIC, borderValue=(245, 245, 245))


def outline_mask(idb, ns, attr, claw_idx=None):
    """爪の ID の輪郭（爪の番号 → 境の画素）。"""
    cm = np.where(idb > ns, attr[np.clip(idb - ns - 1, 0, len(attr) - 1), 0], -1)
    e = np.zeros(idb.shape, bool)
    e[:, 1:] |= (cm[:, 1:] != cm[:, :-1]) & ((cm[:, 1:] >= 0) | (cm[:, :-1] >= 0))
    e[1:, :] |= (cm[1:, :] != cm[:-1, :]) & ((cm[1:, :] >= 0) | (cm[:-1, :] >= 0))
    own = np.maximum(cm, np.maximum(np.roll(cm, 1, 0), np.roll(cm, 1, 1)))
    return e, own


def overlay_fig(sc, cam, bg, idb, ns, path, title, draw_list=True, s=1.0, x0=0.0, y0=0.0, lw=1):
    inv = U.jload(U.D32 + "/ds32_claw_inventory.json")
    byid = {c["id"]: c for c in inv["claws"]}
    img = (0.55 * bg + 0.45 * 255).astype(np.uint8)
    e, own = outline_mask(idb, ns, sc.attr)
    tys = np.array([c["type"] for c in sc.claws])
    for ty, col in TYPE_COL.items():
        k = np.nonzero(tys == ty)[0]
        if not len(k):
            continue
        mm = e & np.isin(own, k)
        if lw > 1:
            mm = cv2.dilate(mm.astype(np.uint8), np.ones((lw, lw), np.uint8)).astype(bool)
        img[mm] = col
    if draw_list:
        for c in sc.claws:
            cl = U.to_disp(np.asarray(byid[c["id"]]["centerline_ref"], np.float64))
            q = (cl - [x0, y0]) * s + (s - 1) * 0.5
            cv2.polylines(img, [np.round(q * 4).astype(np.int32)], False, (0, 0, 0), 1, cv2.LINE_AA, shift=2)
            rd = (np.asarray(byid[c["id"]]["root_display"]) - [x0, y0]) * s + (s - 1) * 0.5
            cv2.circle(img, tuple(np.round(rd).astype(int)), max(2, int(1.5 * s)), (0, 0, 0), -1, cv2.LINE_AA)
    img = put(img, title, 18)
    cv2.imwrite(path, img)
    return img


def row_boxes(sc):
    inv = U.jload(U.D32 + "/ds32_claw_inventory.json")
    byid = {c["id"]: c for c in inv["claws"]}
    rows = {}
    for c in sc.claws:
        key = "bregion" if c["row"] == "b区域" else {"上側": "upper", "途中": "middle", "船側": "boat"}.get(c["row"], "other")
        cl = U.to_disp(np.asarray(byid[c["id"]]["centerline_ref"], np.float64))
        rows.setdefault(key, []).append(cl)
    out = {}
    for k, L in rows.items():
        P = np.vstack(L)
        x0, y0 = P.min(0) - 25; x1, y1 = P.max(0) + 25
        s = min(1920 / (x1 - x0), 1080 / (y1 - y0))
        s = float(min(s, 6.0))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        out[k] = (cx - 960 / s, cy - 540 / s, s)
    return out


# ---------------------------------------------------------------- 型の試作（平らな面の上の 1 本。型の標準の骨格）
def type_demo(sc, path):
    Pp = sc.rig["params"]
    types = sc.rig["types"]
    u100 = sc.rig["user100"]
    S_ = [0.0, 0.2, 0.45, 0.75, 0.9, 1.0]
    rows = []

    def chain(root, d0, lengths, turns_deg):
        pts = [np.asarray(root, float)]
        ang = math.atan2(d0[1], d0[0])
        for i, L in enumerate(lengths):
            pts.append(pts[-1] + L * np.array([math.cos(ang), math.sin(ang), 0.0]))
            if i < len(turns_deg):
                ang += math.radians(turns_deg[i])
        return np.array(pts)

    r = np.array(u100["ratio_median"]); r = r / r.sum()
    tm = u100["turn_median_deg"]
    Lm = 1.0
    defs = {
        "T1": [dict(len=Lm * r, turn=tm, root=(0, 0, 0), d0=(1, 0.35), w=0.26, ty="T1")],
        "T2": [dict(len=Lm * r, turn=tm, root=(0, 0, 0), d0=(1, 0.35), w=0.26, ty="T2"),
               dict(len=0.5 * Lm * r, turn=[t * 0.9 for t in tm], attach=(0, 2), d_rel=-70, w=0.15, ty="branch")],
        "T3": [dict(len=Lm * r, turn=tm, root=(0, 0, 0), d0=(1, 0.35), w=0.26, ty="T3"),
               dict(len=0.5 * Lm * r, turn=[t * 0.9 for t in tm], attach=(0, 1), d_rel=-70, w=0.15, ty="branch"),
               dict(len=0.4 * Lm * r, turn=[t * 0.9 for t in tm], attach=(0, 2), d_rel=-65, w=0.13, ty="branch")],
        "T4": [dict(len=1.15 * Lm * np.array([0.3, 0.28, 0.24, 0.18]), turn=[18, 26, 34], root=(0, 0, 0), d0=(1, 0.2), w=0.14, ty="T4")],
        "T5": [dict(len=0.8 * Lm * r, turn=[-tm[0] * 0.6, -tm[1] * 2.2], root=(0, 0.45, 0), d0=(1, -0.15), w=0.22, ty="T5")],
    }
    cam = U.look_cam(sc.spec, (0.45, -1.35, 2.75), (0.45, 0.30, 0.0), 34.0, 300, 260)
    # 斜め上から見るカメラ（側面の厚みが見える）：画面の x は −X なので、左右を反転して描く
    tiles = []
    for tk in ("T1", "T2", "T3", "T4", "T5"):
        row = []
        for s in S_:
            tris, kinds = [], []
            chains = {}
            for q, dfn in enumerate(defs[tk]):
                ty = types[dfn["ty"]]
                g, kap, om = [float(x) for x in G.growth_curves(s)]
                s_eff = s
                if "attach" in dfn:
                    need = 0.7 if dfn["attach"][1] == 2 else 0.45
                    s_eff = float(np.clip((s - need) / (1 - need), 0, 1))
                    g, kap, om = [float(x) for x in G.growth_curves(s_eff)]
                    if s < need:
                        continue
                    base = chains[dfn["attach"][0]]
                    jn = base[dfn["attach"][1]]
                    dd = base[dfn["attach"][1]] - base[dfn["attach"][1] - 1]
                    a0 = math.atan2(dd[1], dd[0]) + math.radians(dfn["d_rel"])
                    root, d0 = jn, (math.cos(a0), math.sin(a0))
                else:
                    root, d0 = dfn["root"], dfn["d0"]
                J = chain(root, d0, g * np.asarray(dfn["len"]), [kap * t for t in dfn["turn"]])
                chains[q] = chain(root, d0, np.asarray(dfn["len"]), dfn["turn"]) if "attach" not in dfn else J
                if "attach" not in dfn:
                    chains[q] = J
                n_st = ty["stations"]
                sj = np.arange(n_st) / n_st
                clos = np.sqrt(np.clip(1 - U.smoothstep((sj - 0.72) / 0.28), 0, 1))
                w = dfn["w"] * (1 - ty["taper"] * sj) * clos * om
                th = ty["thickness_ratio"] * w
                N = np.tile([0, 0, 1.0], (len(J), 1))
                ring, tip, L, _ = A.sweep(J, N, w, th, n_st, Pp["band_center_frac"])
                V = np.concatenate([J[:1], ring.reshape(-1, 3), tip[None]], 0)
                T, kd = A.layout_tris(n_st, 0)
                keep = kd != 2
                T = T[keep]; kd = kd[keep]
                T = np.where(T > 1 + n_st * 8, 1 + n_st * 8, T)
                tris.append(V[T]); kinds.append(kd)
            img = np.full((260, 300, 3), 250, np.uint8)
            if tris:
                tt = np.concatenate(tris); kk = np.concatenate(kinds)
                idb, _ = U.raster(cam, tt, np.arange(1, len(tt) + 1))
                m = idb > 0
                cc2 = np.array([U.bgr("white"), U.bgr("mizuiro"), U.bgr("white")], np.uint8)
                img[m] = cc2[kk[idb[m] - 1]]
                e = np.zeros(idb.shape, bool)
                e[:, 1:] |= (m[:, 1:] != m[:, :-1]); e[1:, :] |= (m[1:, :] != m[:-1, :])
                img[e] = U.bgr("line")
                img = img[:, ::-1].copy()
            img = cv2.copyMakeBorder(img, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=(180, 180, 180))
            row.append(img)
        tiles.append(np.concatenate(row, 1))
    sheet = np.concatenate(tiles, 0)
    head = np.full((70, sheet.shape[1], 3), 255, np.uint8)
    foot = np.full((80, sheet.shape[1], 3), 255, np.uint8)
    left = np.full((head.shape[0] + sheet.shape[0] + foot.shape[0], 230, 3), 255, np.uint8)
    full = np.concatenate([left, np.concatenate([head, sheet, foot], 0)], 1)
    labs = ["T1 単爪", "T2 主爪＋1支", "T3 主爪＋2支", "T4 細い指（4 段の例）", "T5 右側の鉤（型だけ）"]
    for i, lb in enumerate(labs):
        full = label(full, (10, 70 + i * 262 + 110), lb, 20, (0, 0, 0))
    for j, s in enumerate(S_):
        g, kap, om = [float(x) for x in G.growth_curves(s)]
        full = label(full, (240 + j * 302, 8), "s = %.2f" % s, 18, (0, 0, 0))
        full = label(full, (240 + j * 302, 34), "g %.2f κ %.2f ω %.2f" % (g, kap, om), 15, (0, 0, 0))
    full = put(full, ["型の試作（型の標準の骨格：利用者の 96 本の中央値 長さ比 0.347／0.368／0.282、転折角 37.6°／44.4°。平らな面の上の 1 本を斜め上から見た numpy の描画）",
                      "成長：根元が白くなる（s 0〜0.2）→ 伸びる（0.2〜0.75）→ 最後に曲がる（0.75〜1）。支は主爪が支の関節まで伸びてから伸びる。白＝上面、淡い水色＝側面"],
               15, xy=(240, full.shape[0] - 70))
    cv2.imwrite(path, full)


# ---------------------------------------------------------------- 輪郭の比べ（原画視点 t*）
def contour_compare(sc, outdir):
    import evaluate as E
    import truthlib as T
    import kh_gate_lfR4 as LF
    cwd = os.getcwd()
    os.chdir(U.REPO)
    try:
        truth = E.Truth()
        gate = LF.LFGate()
    finally:
        os.chdir(cwd)
    near = K.Pkg(os.path.join(U.SEA, "near")); far = K.Pkg(os.path.join(U.SEA, "far"))
    idx = U.jload(os.path.join(U.SEA, "near", "ds30_ring0_index.json"))
    cls_near = np.fromfile(os.path.join(U.SEA, "near", "ds30_class_u8.bin"), np.uint8).reshape(near.R, near.C)
    cls_far = np.fromfile(os.path.join(U.SEA, "far", "ds30_class_u8.bin"), np.uint8).reshape(far.R, far.C)
    boats = K.boats_tris(); ph = K.placeholder_tris()
    jb, je = idx["body_cols"]
    tr, ii = K.scene_tris(0.0, sc.hero, near, far, jb, je, "after", boats, ph, cls_near, cls_far)
    cam2 = U.CamWH(sc.spec, 3840, 2160)
    f = U.NFR - 1
    Ct, ci = sc.claw_tris(f)
    res = {}
    covs = {}
    for name, (tt, iid) in (("no_claws", (tr, ii + 1)), ("claws", (np.concatenate([tr, Ct]), np.concatenate([ii + 1, np.full(len(Ct), 99)])))):
        idb, _ = U.raster(cam2, tt, iid.astype(np.int64))
        sky = (idb == 0).astype(np.float64).reshape(1080, 2, 1920, 2).mean((1, 3))
        cov = 1.0 - sky
        covs[name] = cov
        lf = gate.measure(cov, np.zeros_like(cov))
        items = {}
        for ver in ("envelope", "claws"):
            rp = T.boundary_points(sky, truth.spec, truth.fmap)
            F = truth.fam["sky_" + ver]
            for tid in ("78", "130", "131", "132", "72"):
                r_, _, worst = T.labelled_hausdorff(F["pts"], F["sel"][tid], rp)
                items["%s_%s" % (tid, ver)] = dict(max_px=U.rnd(r_.get("max_px"), 4), p95_px=U.rnd(r_.get("p95_px"), 4),
                                                   worst_xy=None if worst is None else U.rnd(worst, 1))
        res[name] = dict(lf_132_sigma12_max=U.rnd(lf["132"]["max_px"], 4), lf_72_sigma24_p95=U.rnd(lf["72"]["p95_px"], 4),
                         lf_132_worst_xy=lf["132"]["worst_xy"], lf_72_worst_xy=lf["72"]["worst_xy"], raw=items,
                         sky_px=float(sky.sum()))
    ref = dict(unity_29r01_30=dict(lf_132_sigma12_max=3.7552, lf_72_sigma24_p95=4.0075, raw_132_max=5.947, raw_72_p95=8.755,
                                   **{"78": 3.0289, "130": 3.5131, "131": 3.0431}),
               cp1=dict(**{"78": 1.64, "130": 1.95, "131": 1.80, "132": 1.57, "72_p95": 1.72}))
    out = dict(schema="GreatWave.DS33.contour_tstar/1",
               method_ja="numpy の z バッファ（3840×2160、2×2 の平均で 1920×1080 の被覆）で、t* の場面（主役波の本体・near・far・残す仮置き・船。設計30 と同じ scene_tris）を、"
                         "爪なしと爪ありで描き、空でない被覆を評価器と同じ読み（truthlib の boundary_points と labelled_hausdorff、包絡版と爪の版）と、"
                         "大きな輪郭の関門（kh_gate_lfR4.LFGate：132 σ12 最大、72 σ24 p95）で測った。Unity の描画ではないので、Unity の値（29修正01・設計30）とは"
                         "爪なしの値で差を確かめてから、爪あり − 爪なしの差を読む",
               results=res, reference=ref,
               delta_claws_minus_no_claws=dict(lf_132=U.rnd(res["claws"]["lf_132_sigma12_max"] - res["no_claws"]["lf_132_sigma12_max"], 4),
                                               lf_72=U.rnd(res["claws"]["lf_72_sigma24_p95"] - res["no_claws"]["lf_72_sigma24_p95"], 4),
                                               raw={k: dict(max=U.rnd((res["claws"]["raw"][k]["max_px"] or 0) - (res["no_claws"]["raw"][k]["max_px"] or 0), 4),
                                                            p95=U.rnd((res["claws"]["raw"][k]["p95_px"] or 0) - (res["no_claws"]["raw"][k]["p95_px"] or 0), 4))
                                                    for k in res["claws"]["raw"]}))
    U.jdump(os.path.join(outdir, "ds33_contour_tstar.json"), out)
    # 図：爪ありで空でなくなった画素（赤）、空になった画素（青）、原画の輪郭の線（包絡版＝緑、爪の版＝黒）
    bg = sc.painting_disp()
    img = (0.5 * bg + 0.5 * 255).astype(np.uint8)
    add = (covs["claws"] > 0.5) & (covs["no_claws"] <= 0.5)
    img[add] = (0, 0, 230)
    for ver, col in (("envelope", (0, 160, 0)), ("claws", (0, 0, 0))):
        for sg in truth.outline[ver]["segments"]:
            if sg["id"] in ("78", "130", "131", "132", "72"):
                pts = np.array(sg["points_display"], float)
                cv2.polylines(img, [np.round(pts * 4).astype(np.int32)], False, col, 1, cv2.LINE_AA, shift=2)
    x0, y0, x1, y1 = 700, 150, 1500, 700
    crop = cv2.resize(img[y0:y1, x0:x1], None, fx=2.4, fy=2.4, interpolation=cv2.INTER_NEAREST)[:1080, :1920]
    canvas = np.full((1080, 1920, 3), 245, np.uint8)
    canvas[:crop.shape[0], :crop.shape[1]] = crop
    r0, r1 = res["no_claws"], res["claws"]
    canvas = put(canvas, ["原画視点 t* の輪郭（numpy の ID の描画、表示 x %d〜%d・y %d〜%d を 2.4 倍）。赤＝爪で空でなくなった画素。線：緑＝原画の包絡版、黒＝原画の爪の版" % (x0, x1, y0, y1),
                          "大きな輪郭：132 σ12 最大 %.2f → %.2f px、72 σ24 p95 %.2f → %.2f px（爪なし → 爪あり）" % (r0["lf_132_sigma12_max"], r1["lf_132_sigma12_max"], r0["lf_72_sigma24_p95"], r1["lf_72_sigma24_p95"]),
                          "細部込み（包絡版）：132 最大 %.2f → %.2f px、72 p95 %.2f → %.2f px。爪の版：132 最大 %.2f → %.2f px、72 p95 %.2f → %.2f px" % (
                              r0["raw"]["132_envelope"]["max_px"], r1["raw"]["132_envelope"]["max_px"], r0["raw"]["72_envelope"]["p95_px"], r1["raw"]["72_envelope"]["p95_px"],
                              r0["raw"]["132_claws"]["max_px"], r1["raw"]["132_claws"]["max_px"], r0["raw"]["72_claws"]["p95_px"], r1["raw"]["72_claws"]["p95_px"])], 17)
    cv2.imwrite(os.path.join(outdir, "fig", "fig_ds33_contour_tstar.png"), canvas)
    return out


# ---------------------------------------------------------------- 動画
def side_cams(sc):
    """確認用の視点：side_a＝波頭の全体を斜め横から、close＝唇の船側の爪の近く（t* の爪の根元の位置から決める）。"""
    ft = U.NFR - 1
    roots = np.array([sc.SK[ft, i, 0:3] for i in range(sc.nc)], np.float64)
    c0 = np.median(roots, 0)
    lo, hi = np.percentile(roots, 3, 0), np.percentile(roots, 97, 0)
    span = float(np.linalg.norm(hi - lo))
    boat = np.array([sc.SK[ft, i, 0:3] for i, c in enumerate(sc.claws) if c["row"] in ("船側",)], np.float64)
    cb = np.median(boat, 0)
    camp = sc.cam
    fwd = camp.f.copy(); fwd[1] = 0; fwd /= np.linalg.norm(fwd)
    right = np.cross(np.array([0, 1.0, 0]), fwd)
    cams = {}
    for name, tgt, yaw, el, dist, fov in (("side_a", c0, 50.0, 25.0, 0.60 * span, 45.0), ("close", cb, 35.0, 15.0, 7.0, 50.0)):
        yr = math.radians(yaw)
        d = -(fwd * math.cos(yr) + right * math.sin(yr))
        d = d * math.cos(math.radians(el)) + np.array([0, 1.0, 0]) * math.sin(math.radians(el))
        pos = tgt + d * dist
        cams[name] = (pos, tgt, fov)
    return cams, c0


def moved(sc, spec3, tau, W=960, H=540):
    """波の枠の原点 O(τ) と一緒に動かしたカメラ（t* で元のカメラと一致）。"""
    dO = sc.hero.origin(float(tau)) - sc.hero.origin(0.0)
    pos, tgt, fov = spec3
    return U.look_cam(sc.spec, np.asarray(pos) + dO, np.asarray(tgt) + dO, fov, W, H)


def video(sc, outdir, f0=165, step=1):
    fig = os.path.join(outdir, "fig")
    wv = os.path.join(fig, "_frames")
    os.makedirs(wv, exist_ok=True)
    boxes = row_boxes(sc)
    # 原画視点の拡大：波頭と唇の爪の範囲
    inv = U.jload(U.D32 + "/ds32_claw_inventory.json")
    byid = {c["id"]: c for c in inv["claws"]}
    P = np.vstack([U.to_disp(np.asarray(byid[c["id"]]["centerline_ref"], np.float64)) for c in sc.claws])
    x0, y0 = P.min(0) - 30; x1, y1 = P.max(0) + 30
    s = min(960 / (x1 - x0), 1080 / (y1 - y0))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    cams, _ = side_cams(sc)
    stages = sc.rig["params"]["stage"]
    frames = list(range(f0, U.NFR, step))
    for k, f in enumerate(frames):
        tau = sc.taus[f]
        base = moved(sc, (sc.cam.pos, sc.cam.pos + sc.cam.f, sc.cam.vfov), tau, 1920, 1080)
        pc = U.CropCam(base, cx - 480 / s, cy - 540 / s, s, 960, 1080)
        a, _, _ = sc.render(pc, f)
        b, _, _ = sc.render(moved(sc, cams["side_a"], tau), f)
        c, _, _ = sc.render(moved(sc, cams["close"], tau), f)
        fr = np.concatenate([a, np.concatenate([b, c], 0)], 1)
        s_ = sc.SK[f, :, 30]; v_ = sc.SK[f, :, 34] > 0.5
        n1 = int((v_ & (s_ < stages["s1"])).sum()); n2 = int((v_ & (s_ >= stages["s1"]) & (s_ < stages["s2"])).sum())
        n3 = int((v_ & (s_ >= stages["s2"]) & (s_ < 1)).sum()); n4 = int((v_ & (s_ >= 1)).sum())
        fr = put(fr, ["t %.2f s  τ %.3f s  コマ %d   爪 %d 本：根元が白くなる %d／伸びる %d／曲がる %d／できた %d" % (f / 30.0, sc.taus[f], f, int(v_.sum()), n1, n2, n3, n4),
                      "左：原画視点の拡大 %.2f 倍　右上：波頭を斜め横から　右下：唇の船側の爪の近く（約 7 m）。どの視点も波の枠の原点 O(τ) と一緒に動く（t* で原画視点と一致）。numpy の描画（Unity ではない）。t* 以後は保持（崩壊は作らない、Q11）" % s], 16)
        cv2.imwrite(os.path.join(wv, "f%04d.png" % k), fr)
        if k % 30 == 0:
            print("video frame %d/%d" % (k, len(frames)), flush=True)
    mp4 = os.path.join(fig, "ds33_claws_growth_30fps.mp4")
    subprocess.run([U.FFMPEG, "-y", "-loglevel", "error", "-framerate", str(30 // step), "-i", os.path.join(wv, "f%04d.png"), "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-crf", "20", mp4], check=True)
    # 静止画の一覧（成長）
    pick = [int(round(t * 30)) for t in (7.0, 8.5, 9.5, 10.3, 11.0, 12.0)]
    tiles = []
    for f in pick:
        k = frames.index(f) if f in frames else None
        if k is None:
            continue
        im = cv2.imread(os.path.join(wv, "f%04d.png" % k))
        tiles.append(cv2.resize(im, (960, 540), interpolation=cv2.INTER_AREA))
    if len(tiles) == 6:
        sheet = np.concatenate([np.concatenate(tiles[0:2], 1), np.concatenate(tiles[2:4], 1), np.concatenate(tiles[4:6], 1)], 0)
        cv2.imwrite(os.path.join(fig, "fig_ds33_growth_stills.png"), sheet)
    for fn in os.listdir(wv):
        os.remove(os.path.join(wv, fn))
    os.rmdir(wv)
    return mp4


def single_growth(sc, path, ids=("C092", "C075", "C015", "C165"), S_=(0.05, 0.2, 0.45, 0.75, 0.9, 1.0)):
    """一覧の代表の爪（R10・R6・R2 と b区域の 1 本）の成長の段を、爪の近くから見た図（原画視点の向きで、波の枠と一緒に動く視点）。"""
    idx = {c["id"]: i for i, c in enumerate(sc.claws)}
    rows = []
    for cid in ids:
        i = idx[cid]
        nj = sc.claws[i]["segments"] + 1
        J = np.asarray(sc.SK[-1, i, 0:3 * nj], np.float64).reshape(nj, 3)
        ctr = 0.5 * (J.min(0) + J.max(0))
        L = float(np.linalg.norm(J.max(0) - J.min(0)))
        fwd = sc.cam.f
        row = []
        for sv in S_:
            sarr = np.asarray(sc.SK[:, i, 30]); visv = np.asarray(sc.SK[:, i, 34]) > 0.5
            cand = np.nonzero(visv)[0]
            f = int(cand[np.argmin(np.abs(sarr[cand] - sv))])
            cam = moved(sc, (ctr - fwd * max(3.0, 2.6 * L) + np.array([0, 0.25 * L, 0]), ctr, 40.0), sc.taus[f], 480, 360)
            only = np.zeros(sc.nc, bool); only[i] = True
            img, idb, ns = sc.render(cam, f)
            e, own = outline_mask(idb, ns, sc.attr)
            img[cv2.dilate((e & (own == i)).astype(np.uint8), np.ones((2, 2), np.uint8)).astype(bool)] = (0, 0, 230)
            img = label(img, (8, 6), "%s  t %.2f s  s %.2f  g %.2f κ %.2f ω %.2f" % (cid, f / 30.0, sarr[f], sc.SK[f, i, 31], sc.SK[f, i, 32], sc.SK[f, i, 33]), 15, (0, 0, 0))
            row.append(cv2.copyMakeBorder(img, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=(160, 160, 160)))
        rows.append(np.concatenate(row, 1))
    sheet = np.concatenate(rows, 0)
    foot = np.full((70, sheet.shape[1], 3), 255, np.uint8)
    sheet = np.concatenate([sheet, foot], 0)
    sheet = put(sheet, ["一覧の爪の成長（赤の縁＝その爪）：左から s 0.05・0.2（根元が白くなる）・0.45（伸びる）・0.75・0.9（最後に曲がる）・1（t*）。原画視点の向きで爪の近くから見た numpy の描画",
                        "C092（R10、T2、唇から空へ出る）、C075（R6、T4）、C015（R2、T2）、C165（b区域）。視点は波の枠と一緒に動く"], 15, xy=(8, sheet.shape[0] - 62))
    cv2.imwrite(path, sheet)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=U.OUT)
    ap.add_argument("--parts", default="still,rows,types,contour,single,video")
    ap.add_argument("--f0", type=int, default=165)
    ap.add_argument("--step", type=int, default=1)
    a = ap.parse_args()
    t0 = time.time()
    parts = set(a.parts.split(","))
    fig = os.path.join(a.out, "fig")
    os.makedirs(fig, exist_ok=True)
    sc = Scene(a.out)
    chk = U.jload(os.path.join(a.out, "ds33_claw_checks.json"))
    rp = chk["reprojection_tstar_record_only"]
    import collections
    tcount = collections.Counter(c["type"] for c in sc.claws)
    ft = U.NFR - 1
    if "still" in parts:
        img, idb, ns = sc.render(sc.cam, ft)
        img = put(img, ["原画視点 t*（コマ 420）：主役波のシート（29修正01 の色面）＋爪 %d 本の帯のメッシュ（numpy の描画、Unity ではない）" % sc.nc], 18)
        cv2.imwrite(os.path.join(fig, "fig_ds33_tstar_render.png"), img)
        bg = sc.painting_disp()
        overlay_fig(sc, sc.cam, bg, idb, ns, os.path.join(fig, "fig_ds33_tstar_overlay.png"),
                    ["原画（表示 1920×1080）に、t* の爪の帯の輪郭（色＝型：緑 T1 単爪・橙 T2 主爪＋1支・紫 支・水色 T4 細い指）と一覧の中心線（黒）・根元（黒点）を重ねた",
                     "爪 %d 本（T1 %d・T2 %d（支 %d）・T4 %d。T3 0・T5 型だけ）。骨格の曲線と一覧の中心線の対称 Hausdorff：中央値 %.2f px、p95 %.2f px、最大 %.2f px（4 px 以下 %d 本、記録のみ）"
                     % (sc.nc, tcount["T1"], tcount["T2"], tcount["branch"], tcount["T4"], rp["hausdorff_px"]["p50"], rp["hausdorff_px"]["p95"], rp["hausdorff_px"]["max"], rp["hausdorff_px"]["le4"])])
        # 原画視点 t* で爪がシートに隠れる割合（記録のみ）：爪だけの描画の画素に対する、シートと一緒の描画で見える画素の割合（3840×2160）
        cam2 = U.CamWH(sc.spec, 3840, 2160)
        X0 = sc.hero.world(0.0)
        St0 = X0.reshape(-1, 3)[sc.Tb]
        Ct, ci = sc.claw_tris(ft)
        ns0 = len(St0)
        idb2, _ = U.raster(cam2, np.concatenate([St0, Ct]), np.concatenate([np.arange(1, ns0 + 1), ns0 + 1 + ci]).astype(np.int64))
        ida2, _ = U.raster(cam2, Ct, (1 + ci).astype(np.int64))
        cnt = lambda ib, off: np.bincount(sc.attr[ib[ib > off] - off - 1, 0], minlength=sc.nc)  # noqa: E731
        vis, alone = cnt(idb2, ns0), cnt(ida2, 0)
        frv = vis / np.maximum(alone, 1)
        U.jdump(os.path.join(a.out, "ds33_visibility_tstar.json"), dict(
            schema="GreatWave.DS33.visibility_tstar/1", rule_ja="原画視点 t*（3840×2160）：爪だけを描いた時の画素に対する、主役波のシートと一緒に描いた時に見える画素の割合（記録のみ）",
            frac_percentiles_0_5_10_25_50=U.rnd(np.percentile(frv, [0, 5, 10, 25, 50]), 3), under_0p5=int((frv < 0.5).sum()), under_0p8=int((frv < 0.8).sum()),
            lowest=[dict(id=sc.claws[i]["id"], type=sc.claws[i]["type"], hanging=sc.claws[i]["hanging"], frac=round(float(frv[i]), 3), px_alone=int(alone[i]))
                    for i in np.argsort(frv)[:12]],
            per_claw={sc.claws[i]["id"]: round(float(frv[i]), 3) for i in range(sc.nc)}))
        print("still %.1fs" % (time.time() - t0), flush=True)
    if "rows" in parts:
        names = {"upper": "上側", "middle": "途中", "boat": "船側", "bregion": "b区域（Q16 の浪尖を含む）"}
        for k, (x0, y0, s) in row_boxes(sc).items():
            if k not in names:
                continue
            cc = U.CropCam(sc.cam, x0, y0, s, 1920, 1080)
            img, idb, ns = sc.render(cc, ft)
            bg = sc.painting_crop(x0, y0, s, 1920, 1080)
            ids_row = [c["id"] for c in sc.claws if (c["row"] == names[k].split("（")[0])]
            wr = [r for r in rp["per_claw"] if r["id"] in ids_row]
            overlay_fig(sc, cc, bg, idb, ns, os.path.join(fig, "fig_ds33_rows_%s.png" % k),
                        ["列「%s」の重ね図（原画を %.2f 倍、表示 x %.0f〜%.0f・y %.0f〜%.0f）。色の線＝t* の爪の帯の輪郭（型の色）、黒＝一覧の中心線と根元" % (names[k], s, x0, x0 + 1920 / s, y0, y0 + 1080 / s),
                         "この列 %d 本：骨格の曲線と一覧の中心線の対称 Hausdorff 中央値 %.2f px・最大 %.2f px（表示の画素、記録のみ）" % (
                             len(wr), float(np.median([r["hausdorff_px"] for r in wr])) if wr else 0, max([r["hausdorff_px"] for r in wr]) if wr else 0)],
                        s=s, x0=x0, y0=y0, lw=2)
            im2 = put(img, ["列「%s」の t* の描画（numpy、原画視点の拡大 %.2f 倍）" % (names[k], s)], 18)
            cv2.imwrite(os.path.join(fig, "fig_ds33_rows_%s_render.png" % k), im2)
        print("rows %.1fs" % (time.time() - t0), flush=True)
    if "types" in parts:
        type_demo(sc, os.path.join(fig, "fig_ds33_types.png"))
        print("types %.1fs" % (time.time() - t0), flush=True)
    if "contour" in parts:
        r = contour_compare(sc, a.out)
        print("contour", json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "raw"} for k, v in r["results"].items()}, ensure_ascii=False), flush=True)
        print("contour delta", json.dumps(r["delta_claws_minus_no_claws"], ensure_ascii=False)[:800], flush=True)
    if "single" in parts:
        single_growth(sc, os.path.join(fig, "fig_ds33_single_growth.png"))
        print("single %.1fs" % (time.time() - t0), flush=True)
    if "video" in parts:
        video(sc, a.out, a.f0, a.step)
        print("video %.1fs" % (time.time() - t0), flush=True)
    print("done %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
