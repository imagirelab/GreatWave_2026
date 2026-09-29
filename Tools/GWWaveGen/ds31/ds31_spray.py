# -*- coding: utf-8 -*-
"""設計31 飛沫の部：飛沫 v0 の生成器（原画の白い点 → 唇の前方の層 → 逆弾道の放出、収束しないものは F8）。

計画 §2.2 設計31：「原画の白い点を抽出し、唇の前方 0.5〜3 m の層へ射線に沿って置き、逆弾道の簡易版で放出する。
収束しないときは t* 付近の固定配置と短い落下にする（美術優先計画の F8）。描画は無照明・不透明の小球の instancing」。
美術優先計画 37 の式：v0 = (p* − p_e − ½gΔt²)/Δt、v0 と局所の水面速度（keypose の差分）の角度 ≤ 45°、超えるなら放出時刻 t_e を変える。

段階（どれも numpy。Unity の描画ではない）：
  1. extract：高解像度の原画（Docs/References/Met_JP1847_DP130155.jpg）から、空の中の白い点を取り出す（白さ W = ΔL* − 1.5·Δb* の
     DoG の極大、局所の雑音の 3 倍より強いもの。大きさは半値の連結成分）。唇の前の区域（表示 x 790〜1260、y 290〜770）だけを使う。
  2. place：各点の表示の画素を通る PaintingCam v1 の射線の上で、唇（K*′ の列 200、行 125〜195 の唇先）の前方（進む向き a）へ
     d = 0.5〜3 m の層に置く（d は点の番号の hash で決める）。t* の z バッファ（設計30 の場面）より手前で見えることを確かめる。
  3. emit：唇の周り（行 110〜215、列 176〜224）の頂点と放出時刻 τ_e（−2.8〜−0.08 s）を総当たりし、v0 を逆弾道で解く。
     条件：角度(v0, 水面速度) ≤ 45°、速さの比 0.5〜2、τ_e ≥ T_white（その頂点が白くなった後）、水面から離れる向き。
     候補の上位を、120 Hz の軌跡で「水面へ引き戻されない」（150）か確かめ、通った最良のものを採る。通らなければ F8。
  4. package：instancing の表（解析式）と、主役波の knot_tau での標本（DS27 風）と、30 Hz のコマの表（設計31 白の部と同じ
     GreatWave.DS31.particles/1）を書く。
出力（Git 対象外）：Unity/Build/Design/31/spray/
"""
import argparse
import hashlib
import json
import math
import os
import sys
import time

import cv2
import numpy as np
from scipy.spatial import cKDTree

REPO = "G:/Unity/GreatWave_2026_Fresh"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "ds30"))
import ds30_checks as K  # noqa: E402  （Pkg・grid_tris・raster_ids・scene_tris・boats_tris・placeholder_tris を借りる）

S = K.S
C27 = K.C27
hermite_weights = K.hermite_weights

HERO_PKG = REPO + "/Unity/Build/Design/28R01F/F_final/art_on"
SEA_DIR = REPO + "/Unity/Build/Design/30/sea"
WARP = REPO + "/Unity/Build/Design/28R01F/F_final/timewarp_F_final.json"
TRUTH = REPO + "/Tools/PaintingTruth/painting_truth.json"
PALETTE = REPO + "/Tools/PaintingTruth/targets/palette.json"
SKY_MASK = REPO + "/Tools/PaintingTruth/targets/masks/sky_claws_cov.png"
TWHITE_DS31 = REPO + "/Unity/Build/Design/31/white/ds31_twhite_r32f.bin"
OUT = REPO + "/Unity/Build/Design/31/spray"

G = np.array([0.0, -9.81, 0.0])
P = dict(
    zone_display=[790.0, 290.0, 1260.0, 770.0],
    dog_sigma=[3.0, 10.0], white_b_weight=1.5, k_noise=3.0, dog_min=2.5, sky_erode_ref_px=15,
    area_ref_px=[12, 2500], max_aspect=3.0,
    lip_ref_rows=[125, 195], lip_col=200,
    layer_m=[0.5, 3.0], occl_margin_m=0.3,
    emit_rows=[110, 215], emit_cols=[176, 224], emit_col_step=2,
    tau_e=[-2.8, -0.08], tau_e_step=0.02, vel_h=0.005,
    max_angle_deg=45.0, speed_ratio=[0.5, 2.0], score_ratio_w=20.0, top_k=16,
    check_hz=240.0, check_skip_s=0.0, emit_offset_m=0.01, sep_m=0.10, sep_within_s=0.3, vertex_slack_m=0.10, parity_gate_m=1.0, contact_extra_m=0.05, contact_lat_m=0.6, inside_dist_m=1.5, gap_after_s=0.2,
    near_rows_checked=[0, 30],
    ramp_s=0.08,
    f8_fall_s=0.4, f8_ramp_s=0.1,
    radius_min_m=0.03,
)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def jdump(p, o):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=1)


def hash01(i, salt=0):
    """点の番号から決まる 0..1 の値（乱数の種を持たない、再現できる値）。"""
    x = (int(i) * 2654435761 + salt * 40503 + 12345) & 0xFFFFFFFF
    x ^= x >> 16
    x = (x * 0x45D9F3B) & 0xFFFFFFFF
    x ^= x >> 16
    return (x & 0xFFFFFF) / float(0x1000000)


# ---------------------------------------------------------------- 1. 白い点の抽出
def extract_dots(spec):
    df = spec["display_frame"]
    ref = cv2.imread(os.path.join(REPO, spec["reference"]["path"]))
    Hr, Wr = ref.shape[:2]
    lab = cv2.cvtColor(ref.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB)
    L, B = lab[..., 0], lab[..., 2]
    Lbg = cv2.medianBlur(np.clip(L * 2.55, 0, 255).astype(np.uint8), 41).astype(np.float32) / 2.55
    Bbg = cv2.medianBlur(np.clip(B + 128, 0, 255).astype(np.uint8), 41).astype(np.float32) - 128
    Wt = (L - Lbg) - P["white_b_weight"] * (B - Bbg)
    s0, s1 = P["dog_sigma"]
    dog = cv2.GaussianBlur(Wt, (0, 0), s0) - cv2.GaussianBlur(Wt, (0, 0), s1)
    m = cv2.imread(SKY_MASK, cv2.IMREAD_UNCHANGED).astype(np.float32) / 65535.0
    xr, yr = np.meshgrid(np.arange(Wr, dtype=np.float32), np.arange(Hr, dtype=np.float32))
    sky = cv2.remap(m, df["scale"] * (xr + 0.5) - 0.5 + df["offset_x"], df["scale"] * (yr + 0.5) - 0.5, cv2.INTER_LINEAR)
    e = P["sky_erode_ref_px"]
    skyin = cv2.erode((sky > 0.98).astype(np.uint8), np.ones((e, e), np.uint8))
    a = np.abs(dog)
    med = float(np.median(a[skyin > 0]))
    ac = np.minimum(a, 3 * med)
    noise = cv2.GaussianBlur(ac, (0, 0), 30) / np.maximum(cv2.GaussianBlur(np.ones_like(a), (0, 0), 30), 1e-6) * 1.4826
    mx = cv2.dilate(dog, np.ones((9, 9), np.uint8))
    pk = (dog >= mx) & (dog > P["k_noise"] * noise) & (dog > P["dog_min"]) & (skyin > 0)
    ys, xs = np.nonzero(pk)
    Ws = cv2.GaussianBlur(Wt, (0, 0), 1.2)
    used = np.zeros(L.shape, bool)
    dots = []
    for o in np.argsort(-dog[ys, xs]):
        y, x = int(ys[o]), int(xs[o])
        if used[y, x]:
            continue
        w = 24
        y0, x0 = max(0, y - w), max(0, x - w)
        win = Ws[y0:y + w + 1, x0:x + w + 1]
        bg = float(np.median(win)); peak = float(Ws[y, x])
        mm = (win > bg + 0.5 * (peak - bg)).astype(np.uint8)
        n, lab_, st, cen = cv2.connectedComponentsWithStats(mm, 8)
        l = lab_[y - y0, x - x0]
        if l == 0:
            continue
        ar = int(st[l, 4]); bw, bh = int(st[l, 2]), int(st[l, 3])
        if ar < P["area_ref_px"][0] or ar > P["area_ref_px"][1] or max(bw, bh) / max(1, min(bw, bh)) > P["max_aspect"]:
            continue
        reg = lab_ == l
        used[y0:y0 + reg.shape[0], x0:x0 + reg.shape[1]] |= reg
        cx, cy = cen[l][0] + x0, cen[l][1] + y0
        xd = df["scale"] * (cx + 0.5) - 0.5 + df["offset_x"]
        yd = df["scale"] * (cy + 0.5) - 0.5
        diam_d = 2.0 * math.sqrt(ar / math.pi) * df["scale"]
        # 点の色（中心 3×3 の参照画素の Lab 平均）
        labc = lab[max(0, int(cy) - 1):int(cy) + 2, max(0, int(cx) - 1):int(cx) + 2].reshape(-1, 3).mean(0)
        dots.append(dict(x_d=float(xd), y_d=float(yd), x_ref=float(cx), y_ref=float(cy), area_ref_px=ar, diam_display_px=float(diam_d),
                         dog=float(dog[y, x]), noise=float(noise[y, x]), snr=float(dog[y, x] / max(noise[y, x], 1e-6)),
                         lab=[float(v) for v in labc]))
    z = P["zone_display"]
    zone = [d for d in dots if z[0] <= d["x_d"] <= z[2] and z[1] <= d["y_d"] <= z[3]]
    zone.sort(key=lambda d: (round(d["y_d"]), d["x_d"]))
    for i, d in enumerate(zone):
        d["dot_id"] = i
    return zone, dict(all_candidates=len(dots), in_zone=len(zone), dog_abs_median=med)


# ---------------------------------------------------------------- 主役波の部分の読み（行・列の範囲だけ）
class Region:
    def __init__(self, pkg, rows, cols):
        self.p = pkg; self.rows = rows; self.cols = cols
        self.cache = {}

    def layer(self, i):
        if i not in self.cache:
            q = self.p.hi[i][self.rows][:, self.cols, :3].astype(np.float64)
            q = q + self.p.lo[i][self.rows][:, self.cols, :3].astype(np.float64) / 255.0 - 0.5
            self.cache[i] = self.p.bmin + q / 65535.0 * self.p.bsz
        return self.cache[i]

    def world(self, tau):
        idx, w = hermite_weights(self.p.knots, tau)
        X = sum(wi * self.layer(ii) for ii, wi in zip(idx, w) if wi != 0.0)
        return X + self.p.origin(tau)[None, None, :]


def grid_normals(X):
    """格子の法線（(P[r+1] − P[r]) × (P[c+1] − P[c]) の向き＝空気の側。設計30 の約束）。"""
    dr = np.gradient(X, axis=0); dc = np.gradient(X, axis=1)
    n = np.cross(dr, dc)
    return n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-12)


def crossings_up(pts, V, T, chunk=40):
    """点から真上（+y）へ伸ばした半直線が網 (V, T) の三角形を横切る数。奇数なら水の側（シートの折り返しの中・海の下）。
    シートは空気の側と水の側を分ける向き付きの面なので、唇の折り返し（上の面と下の面）でも符号の曖昧さがない。"""
    A = V[T[:, 0]]; B = V[T[:, 1]]; Cc = V[T[:, 2]]
    xmin = np.minimum(np.minimum(A[:, 0], B[:, 0]), Cc[:, 0]); xmax = np.maximum(np.maximum(A[:, 0], B[:, 0]), Cc[:, 0])
    zmin = np.minimum(np.minimum(A[:, 2], B[:, 2]), Cc[:, 2]); zmax = np.maximum(np.maximum(A[:, 2], B[:, 2]), Cc[:, 2])
    ymax = np.maximum(np.maximum(A[:, 1], B[:, 1]), Cc[:, 1])
    out = np.zeros(len(pts), int)
    for s0 in range(0, len(pts), chunk):
        P_ = pts[s0:s0 + chunk]
        pre = np.nonzero((xmax >= P_[:, 0].min()) & (xmin <= P_[:, 0].max()) & (zmax >= P_[:, 2].min()) & (zmin <= P_[:, 2].max()) & (ymax > P_[:, 1].min()))[0]
        if not len(pre):
            continue
        m = (xmin[None, pre] <= P_[:, 0:1]) & (xmax[None, pre] >= P_[:, 0:1]) & (zmin[None, pre] <= P_[:, 2:3]) & (zmax[None, pre] >= P_[:, 2:3]) & (ymax[None, pre] > P_[:, 1:2])
        pi, tj = np.nonzero(m)
        ti = pre[tj]
        if not len(pi):
            continue
        px, pz, py = P_[pi, 0], P_[pi, 2], P_[pi, 1]
        ax, az, ay = A[ti, 0], A[ti, 2], A[ti, 1]
        bx, bz, by = B[ti, 0], B[ti, 2], B[ti, 1]
        cx, cz, cy = Cc[ti, 0], Cc[ti, 2], Cc[ti, 1]
        den = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz)
        ok = np.abs(den) > 1e-14
        den = np.where(ok, den, 1.0)
        l1 = ((bz - cz) * (px - cx) + (cx - bx) * (pz - cz)) / den
        l2 = ((cz - az) * (px - cx) + (ax - cx) * (pz - cz)) / den
        l3 = 1 - l1 - l2
        # 半開の規則（辺の上の点を二重に数えない）：l ≥ 0 を l > 0 と l = 0 の片側で扱う代わりに、ごく小さなずらしを入れる
        ins = ok & (l1 > -1e-12) & (l2 > -1e-12) & (l3 > 1e-12)
        yh = l1 * ay + l2 * by + l3 * cy
        hit = ins & (yh > py)
        np.add.at(out, s0 + pi[hit], 1)
    return out


# ---------------------------------------------------------------- 2. 層への配置
def place(dots, hero, cam, scene_zb, frame):
    X0 = hero.world(0.0)
    O0 = hero.origin(0.0)
    tdir = np.array(frame["t_travel"]); edir = np.array(frame["e_crest"])
    r0, r1 = P["lip_ref_rows"]
    L = X0[r0:r1 + 1, P["lip_col"]]
    Lxy, _ = cam.project(L)
    out = []
    a_cam = (cam.pos - O0) @ tdir
    for d in dots:
        i = d["dot_id"]
        ray = cam.ray(d["x_d"], d["y_d"])
        k = int(np.argmin(np.hypot(Lxy[:, 0] - d["x_d"], Lxy[:, 1] - d["y_d"])))
        aL = float((L[k] - O0) @ tdir)
        rt = float(ray @ tdir)
        u = hash01(i, 1)
        dl = P["layer_m"][0] + (P["layer_m"][1] - P["layer_m"][0]) * u
        px, py = int(round(d["x_d"])), int(round(d["y_d"]))
        izs = scene_zb[py, px]
        z_surf = 1.0 / izs if izs > 0 else float("inf")
        rec = dict(d)
        ok = False
        for dd in (dl, P["layer_m"][1]):
            s = (aL + dd - a_cam) / rt
            p = cam.pos + s * ray
            zp = float(cam.depth(p))
            if s > 0 and zp < z_surf - P["occl_margin_m"]:
                ok = True
                dl = dd
                break
        rec.update(lip_ref_row=r0 + k, layer_d_m=float(dl), layer_d_sampled_m=float(P["layer_m"][0] + (P["layer_m"][1] - P["layer_m"][0]) * u),
                   p_star=[float(v) for v in p], cam_depth_m=zp, surface_depth_m=(None if not np.isfinite(z_surf) else float(z_surf)),
                   visible_at_tstar=bool(ok), c_m=float((p - O0) @ edir), a_minus_lip_m=float((p - O0) @ tdir - aL),
                   radius_m=float(max(P["radius_min_m"], 0.5 * d["diam_display_px"] * zp / cam.focal_px)))
        out.append(rec)
    return out


# ---------------------------------------------------------------- 3. 逆弾道
def traj(p_e, v0, tau_e, tau):
    dt = np.maximum(tau - tau_e, 0.0)[..., None]
    return p_e + v0 * dt + 0.5 * G * dt * dt


def emit_candidates(recs, hero, tw):
    r0, r1 = P["emit_rows"]; c0, c1 = P["emit_cols"]
    rows = np.arange(r0, r1 + 1); cols = np.arange(c0, c1 + 1, P["emit_col_step"])
    reg = Region(hero, rows, cols)
    taus = np.round(np.arange(P["tau_e"][0], P["tau_e"][1] + 1e-9, P["tau_e_step"]), 4)
    h = P["vel_h"]
    X = np.stack([reg.world(float(t)) for t in taus])                       # (T, R, C, 3)
    U = np.stack([(reg.world(float(t) + h) - reg.world(float(t) - h)) / (2 * h) for t in taus])
    N = np.stack([grid_normals(x) for x in X])
    TW = tw[np.ix_(rows, cols)]                                               # (R, C)
    white_ok = TW[None, :, :] <= taus[:, None, None]
    us = np.linalg.norm(U, axis=-1)
    cands = []
    for rec in recs:
        ps = np.array(rec["p_star"])
        dt = -taus[:, None, None, None]
        # 放出点：頂点から空気の側へ粒子の半径 + emit_offset_m だけ離す（粒の中心は水面の上。修正：頂点そのものから出すと、
        # 唇の下の面で放出の直後の 20 ms ほど 1〜2 mm 水の側をかすめる粒があった）
        Xo = X + N * (rec["radius_m"] + P["emit_offset_m"])
        v0 = (ps - Xo) / dt - 0.5 * G * dt
        vn = np.linalg.norm(v0, axis=-1)
        cosang = np.sum(v0 * U, -1) / np.maximum(vn * us, 1e-9)
        ang = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
        ratio = vn / np.maximum(us, 1e-9)
        leave = np.sum((v0 - U) * N, -1) >= 0.0
        ok = (ang <= P["max_angle_deg"]) & (ratio >= P["speed_ratio"][0]) & (ratio <= P["speed_ratio"][1]) & white_ok & leave
        score = ang + P["score_ratio_w"] * np.abs(np.log(np.maximum(ratio, 1e-9)))
        score = np.where(ok, score, np.inf)
        flat = np.argsort(score, axis=None)
        picked = []
        seen_tau = []
        for f in flat[:4000]:
            if not np.isfinite(score.flat[f]):
                break
            it, ir, ic = np.unravel_index(f, score.shape)
            # 候補を τ_e で散らす（同じ τ_e の近い頂点ばかりにしない）
            if any(abs(taus[it] - s0) < 0.05 for s0 in seen_tau) and len(picked) >= 4:
                continue
            seen_tau.append(taus[it])
            picked.append(dict(tau_e=float(taus[it]), row=int(rows[ir]), col=int(cols[ic]), p_e=Xo[it, ir, ic].tolist(), vertex=X[it, ir, ic].tolist(),
                               v0=v0[it, ir, ic].tolist(), u_s=U[it, ir, ic].tolist(), angle_deg=float(ang[it, ir, ic]),
                               speed_ratio=float(ratio[it, ir, ic]), score=float(score[it, ir, ic]),
                               t_white=float(TW[ir, ic])))
            if len(picked) >= P["top_k"]:
                break
        best_any = float(np.min(np.where(white_ok, ang, np.inf))) if np.isfinite(np.min(np.where(white_ok, ang, np.inf))) else None
        cands.append(dict(dot_id=rec["dot_id"], candidates=picked, n_ok=int(np.isfinite(score).sum()), best_angle_any_deg=best_any))
    return cands


def f8_path(rec, hero):
    """F8：t* 付近の固定配置と短い落下。唇の t* の水平の速度で運ばれながら f8_fall_s 秒落ちて p* に着く。"""
    ps = np.array(rec["p_star"])
    r = rec["lip_ref_row"]
    reg = Region(hero, np.array([r]), np.array([P["lip_col"]]))
    h = P["vel_h"]
    u = ((reg.world(0.0) - reg.world(-2 * h)) / (2 * h))[0, 0]
    vh = np.array([u[0], 0.0, u[2]])
    T = P["f8_fall_s"]
    p_s = ps - vh * T - 0.5 * G * T * T
    return dict(tau_e=-T, p_e=p_s.tolist(), v0=vh.tolist(), mode="F8")


def check_paths(paths, hero, near, tau_lo):
    """120 Hz で τ_lo → 0。各経路の、水面（主役波＋近い海の行 0〜30）までの距離と符号。
    paths：list of dict(p_e, v0, tau_e, radius)。戻り値：各経路の min_dist（放出の check_skip_s 後から）、接触・内側の数、t* の距離、gap_after の距離。"""
    n = len(paths)
    pe = np.array([q["p_e"] for q in paths]); v0 = np.array([q["v0"] for q in paths])
    te = np.array([q["tau_e"] for q in paths]); rad = np.array([q["radius"] for q in paths])
    taus = np.arange(tau_lo, 0.0 + 1e-9, 1.0 / P["check_hz"])
    if taus[-1] < 0.0:
        taus = np.append(taus, 0.0)
    nr0, nr1 = P["near_rows_checked"]
    Th = K.grid_tris(hero.R, hero.C)
    Tn = K.grid_tris(nr1 - nr0 + 1, near.C) + hero.R * hero.C
    Tall = np.concatenate([Th, Tn])
    res = dict(min_dist=np.full(n, np.inf), min_sd=np.full(n, np.inf), contact=np.zeros(n, int), inside=np.zeros(n, int),
               first_contact_tau=np.full(n, np.nan), sep_tau=np.full(n, np.nan), dist_gap=np.full(n, np.nan), dist_tstar=np.full(n, np.nan),
               sd_tstar=np.full(n, np.nan), min_dist_after_sep=np.full(n, np.inf))
    for tau in taus:
        alive = tau >= te + P["check_skip_s"]
        if not alive.any():
            continue
        Xh = hero.world(float(tau)); Nh = grid_normals(Xh)
        Xn = near.world(float(tau))[nr0:nr1 + 1]; Nn = grid_normals(Xn)
        V = np.concatenate([Xh.reshape(-1, 3), Xn.reshape(-1, 3)]); NN = np.concatenate([Nh.reshape(-1, 3), Nn.reshape(-1, 3)])
        tree = cKDTree(V)
        idx = np.nonzero(alive)[0]
        p = traj(pe[idx], v0[idx], te[idx], np.full(len(idx), tau))
        dist, j = tree.query(p)
        sd = np.sum((p - V[j]) * NN[j], -1)
        lat = np.sqrt(np.maximum(dist * dist - sd * sd, 0.0))
        # 水の側かどうか（真上への半直線の交差の偶奇）。水へ入るには水面を横切るので、水面の近く（頂点まで 1 m 未満）だけで調べれば足りる
        par = np.zeros(len(idx), int)
        gate = dist < P["parity_gate_m"]
        if gate.any():
            par[gate] = crossings_up(p[gate], V, Tall) % 2
        near_s = (dist < rad[idx] + P["contact_extra_m"] + P["vertex_slack_m"])
        ins = par == 1
        clear = (dist >= rad[idx] + P["sep_m"] + P["vertex_slack_m"]) & (par == 0)
        sep = ~np.isnan(res["sep_tau"][idx])
        newsep = idx[clear & ~sep]
        res["sep_tau"][newsep] = tau
        # 引き戻し：いったん離れた後に水面へ戻る（near_s）か、水の側へ入る（ins、いつでも）
        cont = near_s & sep
        bad = cont | ins
        res["contact"][idx] += cont.astype(int)
        res["inside"][idx] += ins.astype(int)
        first = idx[bad & np.isnan(res["first_contact_tau"][idx])]
        res["first_contact_tau"][first] = tau
        res["min_dist"][idx] = np.minimum(res["min_dist"][idx], dist)
        res["min_dist_after_sep"][idx[sep]] = np.minimum(res["min_dist_after_sep"][idx[sep]], dist[sep])
        res["min_sd"][idx] = np.minimum(res["min_sd"][idx], np.where(dist < 3.0, sd, np.inf))
        g = np.abs(tau - (te[idx] + P["gap_after_s"])) < 0.5 / P["check_hz"]
        res["dist_gap"][idx[g]] = dist[g]
        if abs(tau) < 1e-9:
            res["dist_tstar"][idx] = dist
            res["sd_tstar"][idx] = sd
    # 離れない（放出から sep_within_s の間に水面から離れない）ものも失敗（149）
    late = np.isnan(res["sep_tau"]) | (res["sep_tau"] > te + P["sep_within_s"])
    res["never_left"] = late.astype(int)
    return res


# ---------------------------------------------------------------- 4. パッケージ
def eval_state(tab, tau):
    """解析式：τ（物理の時刻、t* = 0、t* の後は 0 に止める）→ 位置（N,3）と半径（N,）。"""
    tau = min(float(tau), 0.0)
    pe = tab["p_e"]; v0 = tab["v0"]; te = tab["tau_e"]
    dt = np.maximum(tau - te, 0.0)[:, None]
    pos = pe + v0 * dt + 0.5 * G * dt * dt
    s = np.clip((tau - tab["tau_show"]) / tab["ramp_s"], 0.0, 1.0)
    s = s * s * (3 - 2 * s)
    rad = np.where(tau >= tab["tau_show"], tab["radius"] * s, 0.0)
    return pos, rad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--twhite", default=None, help="T_white（行 × 列 float32）。既定：設計31 白の部の ds31_twhite_r32f.bin があればそれ、なければ F_final のもの")
    args = ap.parse_args()
    t0 = time.time()
    out = args.out
    os.makedirs(out, exist_ok=True)
    spec = S.load_json(TRUTH)
    cam = C27.Cam(spec)
    hero = K.Pkg(HERO_PKG)
    near = K.Pkg(os.path.join(SEA_DIR, "near")); far = K.Pkg(os.path.join(SEA_DIR, "far"))
    assert np.array_equal(near.knots, hero.knots) and np.array_equal(near.fo, hero.fo)
    kmeta = S.load_json(REPO + "/Unity/Build/Design/28R01F/kstar_final/kstarR4_a45_meta.json")
    frame = kmeta["frame"]
    tw_path = args.twhite or (TWHITE_DS31 if os.path.exists(TWHITE_DS31) else os.path.join(HERO_PKG, "ds27_twhite_r32f.bin"))
    tw = np.fromfile(tw_path, np.float32).reshape(hero.R, hero.C).astype(np.float64)
    log = dict(number="設計31", part="飛沫", schema="GreatWave.DS31.spray_log/1", params=P,
               inputs=dict(hero_pkg=HERO_PKG.replace(REPO + "/", ""), hero_pos_sha256=hero.k["pos_sha256"], hero_pos_lo_sha256=hero.k["pos_lo_sha256"],
                           near_pos_sha256=near.k["pos_sha256"], twhite=tw_path.replace(REPO + "/", ""), twhite_sha256=sha(tw_path),
                           reference=spec["reference"]["path"], reference_sha256=sha(os.path.join(REPO, spec["reference"]["path"])),
                           sky_mask=SKY_MASK.replace(REPO + "/", ""), sky_mask_sha256=sha(SKY_MASK),
                           timewarp=WARP.replace(REPO + "/", ""), timewarp_sha256=sha(WARP)),
               code_sha256={os.path.basename(__file__): sha(os.path.abspath(__file__))})

    # 1
    dots, ex = extract_dots(spec)
    log["extract"] = ex
    print("dots", ex, "%.1fs" % (time.time() - t0))

    # t* の場面の z バッファ（設計30 の場面：主役波の本体・near・far・船・残した仮置き）
    idx30 = S.load_json(os.path.join(SEA_DIR, "near", "ds30_ring0_index.json"))
    jb, je = idx30["body_cols"] if "body_cols" in idx30 else (18, 394)
    cls_near = np.fromfile(os.path.join(SEA_DIR, "near", "ds30_class_u8.bin"), np.uint8).reshape(near.R, near.C)
    cls_far = np.fromfile(os.path.join(SEA_DIR, "far", "ds30_class_u8.bin"), np.uint8).reshape(far.R, far.C)
    boats = K.boats_tris(); ph = K.placeholder_tris()
    tris, ids = K.scene_tris(0.0, hero, near, far, jb, je, "after", boats, ph, cls_near, cls_far)
    idb, zb = K.raster_ids(cam, tris, ids)
    np.save(os.path.join(out, "_work", "scene_tstar_ids.npy"), idb.astype(np.uint8))
    np.save(os.path.join(out, "_work", "scene_tstar_zb.npy"), zb.astype(np.float32))
    print("zbuffer %.1fs" % (time.time() - t0))

    # 2
    recs = place(dots, hero, cam, zb, frame)
    vis = [r for r in recs if r["visible_at_tstar"]]
    log["place"] = dict(dots=len(recs), visible=len(vis), dropped_occluded=[r["dot_id"] for r in recs if not r["visible_at_tstar"]])
    print("placed", len(recs), "visible", len(vis))

    # 3
    cands = emit_candidates(vis, hero, tw)
    print("candidates %.1fs" % (time.time() - t0), "with any", sum(1 for c in cands if c["candidates"]))
    flat = []
    for rec, c in zip(vis, cands):
        for k, q in enumerate(c["candidates"]):
            flat.append(dict(q, dot=rec["dot_id"], k=k, radius=rec["radius_m"]))
    f8 = {r["dot_id"]: f8_path(r, hero) for r in vis}
    f8_list = [dict(f8[r["dot_id"]], dot=r["dot_id"], k=-1, radius=r["radius_m"]) for r in vis]
    allp = flat + f8_list
    chk = check_paths(allp, hero, near, P["tau_e"][0])
    print("checked %.1fs" % (time.time() - t0))
    for q, i in zip(allp, range(len(allp))):
        q["contact"] = int(chk["contact"][i]); q["inside"] = int(chk["inside"][i])
        q["min_dist_m"] = float(chk["min_dist"][i]); q["dist_gap_m"] = float(chk["dist_gap"][i]); q["dist_tstar_m"] = float(chk["dist_tstar"][i])
        q["sd_tstar_m"] = float(chk["sd_tstar"][i])
        q["never_left"] = int(chk["never_left"][i])
        st_ = chk["sep_tau"][i]
        q["sep_after_s"] = None if np.isnan(st_) else float(st_ - q["tau_e"])
        q["min_dist_after_sep_m"] = float(chk["min_dist_after_sep"][i])
        fc = chk["first_contact_tau"][i]
        q["first_contact_tau"] = None if np.isnan(fc) else float(fc)
    by_dot = {}
    for q in flat:
        by_dot.setdefault(q["dot"], []).append(q)
    table = []
    stat = dict(ballistic=0, f8=0, dropped=0, rejected_by_150=0)
    for rec in vis:
        qs = sorted(by_dot.get(rec["dot_id"], []), key=lambda q: q["score"])
        good = [q for q in qs if q["contact"] == 0 and q["inside"] == 0 and q["never_left"] == 0]
        stat["rejected_by_150"] += len(qs) - len(good)
        if good:
            q = good[0]; mode = "ballistic"
        else:
            q = [x for x in f8_list if x["dot"] == rec["dot_id"]][0]
            mode = "F8"
            if q["contact"] or q["inside"] or q["never_left"]:
                stat["dropped"] += 1
                continue
        stat["ballistic" if mode == "ballistic" else "f8"] += 1
        ramp = P["ramp_s"] if mode == "ballistic" else P["f8_ramp_s"]
        table.append(dict(dot_id=rec["dot_id"], mode=mode, tau_e=q["tau_e"], tau_show=q["tau_e"], ramp_s=ramp, p_e=q["p_e"], v0=q["v0"],
                          radius_m=rec["radius_m"], p_star=rec["p_star"], x_d=rec["x_d"], y_d=rec["y_d"], diam_display_px=rec["diam_display_px"],
                          layer_d_m=rec["layer_d_m"], a_minus_lip_m=rec["a_minus_lip_m"], c_m=rec["c_m"], lip_ref_row=rec["lip_ref_row"],
                          emitter=(None if mode == "F8" else dict(row=q["row"], col=q["col"], t_white=q["t_white"])),
                          angle_deg=(q.get("angle_deg")), speed_ratio=q.get("speed_ratio"), u_s=q.get("u_s"),
                          min_dist_m=q["min_dist_m"], dist_gap_m=q["dist_gap_m"], dist_tstar_m=q["dist_tstar_m"], sd_tstar_m=q["sd_tstar_m"],
                          contact=q["contact"], inside=q["inside"], never_left=q["never_left"], sep_after_s=q["sep_after_s"],
                          min_dist_after_sep_m=q["min_dist_after_sep_m"], lab_painting=rec["lab"]))
    log["emit"] = stat
    print("table", len(table), stat)

    # 4 パッケージ
    n = len(table)
    tab = dict(p_e=np.array([t["p_e"] for t in table]), v0=np.array([t["v0"] for t in table]), tau_e=np.array([t["tau_e"] for t in table]),
               tau_show=np.array([t["tau_show"] for t in table]), ramp_s=np.array([t["ramp_s"] for t in table]),
               radius=np.array([t["radius_m"] for t in table]))
    pal = S.load_json(PALETTE)["palette"]["white"]
    colour_srgb8 = pal["srgb8"]
    inst = np.zeros((n, 12), np.float32)
    inst[:, 0:3] = tab["p_e"]; inst[:, 3] = tab["tau_e"]; inst[:, 4:7] = tab["v0"]; inst[:, 7] = tab["radius"]
    inst[:, 8] = tab["tau_show"]; inst[:, 9] = tab["ramp_s"]; inst[:, 10] = [0 if t["mode"] == "ballistic" else 1 for t in table]
    inst[:, 11] = [t["dot_id"] for t in table]
    ip = os.path.join(out, "ds31_spray_inst_f32.bin"); inst.tofile(ip)
    # knot_tau の標本（DS27 風）：層 × 数 × 4（x, y, z, 半径）
    kn = hero.knots
    ks = np.zeros((len(kn), n, 4), np.float32)
    for i, t in enumerate(kn):
        pos, rad = eval_state(tab, float(t))
        ks[i, :, :3] = pos; ks[i, :, 3] = rad
    kp = os.path.join(out, "ds31_spray_knots_f32.bin"); ks.tofile(kp)
    # knot の Hermite と解析式の差（出ている間だけ、480 Hz）
    errs = []
    for tau in np.arange(-2.8, 0.0 + 1e-9, 1 / 480.0):
        pos, rad = eval_state(tab, tau)
        idx, w = hermite_weights(kn, float(tau))
        ph_ = sum(wi * ks[ii, :, :3].astype(np.float64) for ii, wi in zip(idx, w) if wi != 0.0)
        live = tau >= tab["tau_show"] + tab["ramp_s"]
        # 出てきた直後の区間（節点の間に放出がある）は Hermite が τ_e の前の静止を混ぜるので、放出の後の 2 節点ぶんを外す
        nxt = np.searchsorted(kn, tab["tau_e"], side="right")
        safe = live & (np.searchsorted(kn, tau, side="right") - 1 >= np.minimum(nxt + 1, len(kn) - 1))
        if safe.any():
            errs.append(float(np.abs(ph_ - pos)[safe].max()))
    # 30 Hz のコマの表（設計31 白の部と同じ書式 GreatWave.DS31.particles/1）
    twj = S.load_json(WARP)
    t_all = np.array(twj["t"]); tau_all = np.array(twj["tau"])
    frames = np.arange(0, 421) / 30.0
    taus_f = np.interp(frames, t_all, tau_all)
    fr = np.zeros((len(frames), n, 4), np.float32)
    for i, tau in enumerate(taus_f):
        pos, rad = eval_state(tab, float(tau))
        fr[i, :, :3] = pos; fr[i, :, 3] = rad
    fp = os.path.join(out, "ds31_spray_frames.bin"); fr.tofile(fp)
    jdump(os.path.join(out, "ds31_spray_frames.json"), dict(
        schema="GreatWave.DS31.particles/1", frames=len(frames), hz=30, t0=0.0, count=n, file="ds31_spray_frames.bin", sha256=sha(fp),
        bytes=os.path.getsize(fp),
        layout_ja="float32 リトルエンディアン、コマ × 数 × 4（x, y, z, 半径）。ワールドの m。半径 0 は描かない。コマ k は体験の時刻 t = t0 + k/hz（t ≥ 12 s は t* の静止）",
        colour=[round(c / 255.0, 4) for c in colour_srgb8], colour_space_ja="sRGB（無照明の不透明。調色板の白・生成り）",
        note_ja="飛沫 v0（作品に入る層）。解析式の表 ds31_spray_inst_f32.bin を timewarp_F_final の τ(t) で評価したもの"))
    # 球の網（正二十面体を 1 回分割：42 頂点・80 三角形、半径 1）
    Vs, Fs = icosphere1()
    with open(os.path.join(out, "ds31_sphere42.obj"), "w", encoding="utf-8") as f:
        f.write("# 設計31 飛沫の小球（単位球、42 頂点・80 三角形）。Unity は左手系なので読み込みの向きに注意（面の向きは外向き、右手系の OBJ）\n")
        for v in Vs:
            f.write("v %.6f %.6f %.6f\n" % tuple(v))
        for t in Fs:
            f.write("f %d %d %d\n" % tuple(t + 1))
    meta = dict(
        schema="GreatWave.DS31.spray/1", number="設計31", part="飛沫 v0", count=n,
        g_mps2=[0.0, -9.81, 0.0],
        clock_ja="τ は主役波と同じ物理の時刻（t* = 0）。体験の時刻 t から timewarp_F_final.json の τ(t) で求める（主役波・海と同じ τ）。t* の後は τ = 0 のまま（静止）。",
        eval_ja="τ' = min(τ, 0)。τ' < tau_show なら描かない。位置 = p_e + v0·Δ + ½·g·Δ²（Δ = max(τ' − τ_e, 0)）。半径 = radius·smoothstep((τ' − tau_show)/ramp_s)。",
        inst_file="ds31_spray_inst_f32.bin", inst_sha256=sha(ip), inst_bytes=os.path.getsize(ip),
        inst_layout_ja="float32 リトルエンディアン、数 × 12：p_e.xyz（ワールド m）、τ_e（s）、v0.xyz（m/s、τ の秒あたり）、半径（m）、tau_show（s）、ramp_s（s）、mode（0 = 逆弾道、1 = F8）、dot_id",
        knots_file="ds31_spray_knots_f32.bin", knots_sha256=sha(kp), knots_bytes=os.path.getsize(kp), knot_tau_source="主役波のパッケージの knot_tau（242 個）",
        knots_layout_ja="float32、層（242）× 数 × 4（x, y, z, 半径）。主役波の knot_tau での解析式の値（DS27 風）。放出の直後は節点の間で半径が 0 から立ち上がるので、Hermite より解析式を使うこと",
        knots_hermite_vs_analytic_max_m=(max(errs) if errs else None),
        frames_file="ds31_spray_frames.json",
        mesh_file="ds31_sphere42.obj", mesh_vertices=len(Vs), mesh_triangles=len(Fs),
        render_ja="Graphics.RenderMeshInstanced（または DrawMeshInstancedProcedural）で、無照明・不透明の単色（調色板の白）。透明・テクスチャの板（四角い下地）を使わない。藍の線の反転シェル（外殻線）を飛沫に付けない（黒い縁になる）。MSAA は場面のまま",
        colour_srgb8=colour_srgb8, colour_lab=pal["lab"], colour_source="Tools/PaintingTruth/targets/palette.json の white（白・生成り）",
        modes=dict(ballistic=stat["ballistic"], F8=stat["f8"]),
    )
    jdump(os.path.join(out, "ds31_spray_package.json"), meta)
    jdump(os.path.join(out, "ds31_spray_table.json"), dict(schema="GreatWave.DS31.spray_table/1", count=n, particles=table))
    jdump(os.path.join(out, "ds31_spray_dots.json"), dict(schema="GreatWave.DS31.spray_dots/1", zone_display=P["zone_display"], dots=recs,
                                                         note_ja="原画の白い点（表示の画素、1920×1080）。p_star は PaintingCam v1 の射線の上の t* の位置"))
    jdump(os.path.join(out, "ds31_spray_candidates.json"), dict(candidates=[{k: v for k, v in q.items()} for q in allp]))
    log["seconds"] = time.time() - t0
    log["outputs"] = {os.path.basename(p): sha(p) for p in (ip, kp, fp)}
    jdump(os.path.join(out, "ds31_spray_generate_log.json"), log)
    print("done %.1fs" % (time.time() - t0))


def icosphere1():
    t = (1.0 + 5 ** 0.5) / 2.0
    V = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    F = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
         (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    V = [np.array(v, float) / np.linalg.norm(v) for v in V]
    mid = {}

    def m(a, b):
        k = (min(a, b), max(a, b))
        if k not in mid:
            p = V[a] + V[b]
            V.append(p / np.linalg.norm(p))
            mid[k] = len(V) - 1
        return mid[k]
    F2 = []
    for a, b, c in F:
        ab, bc, ca = m(a, b), m(b, c), m(c, a)
        F2 += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
    return np.array(V), np.array(F2, int)


if __name__ == "__main__":
    main()
