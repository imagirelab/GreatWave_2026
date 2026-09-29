# -*- coding: utf-8 -*-
"""設計33（爪の部）：爪の型と、一覧（設計32）から主浪の爪の骨格・幅・成長を作る（numpy。Unity の描画ではない）。

入力（読むだけ。SHA-256 を run.json に記録する）：
  - 設計32 の一覧 Unity/Build/Design/32/list+ids/ds32_claw_inventory.json（中心線・領域・根元・先端、原画 DP130155 の画素）
  - 設計32 の ID Unity/Build/Design/32/list+ids/ds32_ids.json（根元のシートの (行, 列)、根元の T_white（tau_birth）、群）
  - 主役波のパッケージ Unity/Build/Design/31/white/hero_pkg（F_final の位置＋設計31 の T_white。最後の層 τ = 0 が K*′ R4）
  - PaintingCam v1（Tools/PaintingTruth/painting_truth.json）
  - 爪形分析の README（G:/Unity/Ukeyoe_Claw/Docs/Research/Claw_Analysis/README.md、読み取りのみ）の 96 本の中央値（数値だけを写す）

手順：
  1. 中心線（原画の画素）を 1.5 px おきに取り直し、3 段（長く曲がる爪は 4 段）の折れ線を最小二乗で当てはめて関節を決める（一覧の測定）。
     節が全長の 10% 未満に潰れる当てはめは、節の最小を 20% にして当て直す。
     短すぎる爪（18 px 未満）は、型の標準の骨格（利用者の 96 本の中央値：長さ比 0.347／0.368／0.282、転折角 37.6°／44.4°）を根元→先端へ合わせて使う。
  2. 関節を t*（τ = 0）の主役波へ置く：表示の画素の射線が当たるシートの面が、直前の関節の深さより前か +1.5 m 以内ならその点（シートに付く関節）、
     当たらない・奥すぎるなら直前の関節の深さの面（空に出る関節。直前のシートに付く関節の局所の座標系で持つ）。根元は設計32 の sheet_rc。
     （設計32 は根元の深さ ±1.5 m の窓で先端を置いたが、唇の前へ巻く面の前にある爪が面の奥に置かれて隠れたので、前の面はいつも採る）
  3. 幅：一覧の領域（藍の輪郭線の内側、D25 の仮の定義）の距離変換で中心線の幅を測り、型の先細り（根元が広く先端が閉じる）の 0.6〜1 倍へ収め、根元から減らないようにする。
     表示の画素の幅を、根元の深さの画面の面の m に直し、シートの面の傾き（横向きの縮み、0.4 まで）で割る。側面の厚み＝正面の幅 × 型の比（15〜25%）。
  4. 型：単爪（T1）、主爪＋1支（T2）、主爪＋2支（T3）、細い指（T4）、右側の鉤（T5、型だけ）。T2・T3 は一覧で根元が他の爪の領域の中
     （その爪の中心線の 15〜92% の所）にある爪を「支」とし、支の成長は主爪が支の根元まで伸びてから始める。
  5. 成長（3 段の標準曲線、計画の損切りの形をそのまま既定にした）：s = (τ − τ_b)/(0 − τ_b)。
     根元が白くなる（s 0〜0.2：幅 0.3 → 1、長さ 0.04 → 0.12）→ 伸びる（s 0.2〜0.75：長さ 0.12 → 1、曲がり 0.25 → 0.4）→ 最後に曲がる（s 0.75〜1：曲がり 0.4 → 1）。
     長さ g は各節を同じ割合で縮め、曲がり κ は各関節の転折角（t* の 3 次元の角）を κ 倍にする（1 本目の節の向きは t* のまま）。
     41 の成長の段（s = 0, 0.025, …, 1）ごとに、t* のシートの上での関節の結び付け（行, 列, 局所のずれ）を求め、コマでは段の間を線形に補間する。
出力（Git 対象外、Unity/Build/Design/33/claws/）：ds33_claw_rig.json（型・爪ごとの値）、ds33_claw_rig.npz（成長の段の結び付け・幅）。
"""
import argparse
import math
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ds33_common as U  # noqa: E402

K = U.K
# ---------------------------------------------------------------- 型（利用者の 100 本：README §7.3 の 96 本の三段の中央値と四分位）
USER100 = dict(
    source=dict(path=U.CLAW_README, note_ja="README §7.3 の表（2026-09-26 に利用者の直線骨格の統計から再計算された値）。数値だけを写した"),
    three_segment_n=96, four_segment_n=4,
    ratio_median=[0.347122, 0.367578, 0.282053], ratio_p25=[0.285244, 0.307547, 0.226734], ratio_p75=[0.406385, 0.405750, 0.347507],
    turn_median_deg=[37.583, 44.372], turn_p25_deg=[28.945, 35.614], turn_p75_deg=[46.188, 54.021],
    branch_note_ja="主爪＋1支（二分裂）・主爪＋2支（三分裂）は README §4.2・§9.1 の呼び方。支は主爪の関節から出て、主爪が分岐の関節に届いてから同時に伸びる（Turtle）。")
TYPES = {
    "T1": dict(name_ja="単爪", segments=3, stations=20, thickness_ratio=0.20, taper=0.30, branches=0,
               note_ja="3 段の骨格の 1 本の指。根元が広く先端が閉じる帯"),
    "T2": dict(name_ja="主爪＋1支", segments=3, stations=20, thickness_ratio=0.20, taper=0.30, branches=1,
               note_ja="主爪（T1 と同じ帯）に支 1 本。支は一覧の爪（根元が主爪の領域の中）で、主爪が支の根元まで伸びてから伸びる"),
    "T3": dict(name_ja="主爪＋2支", segments=3, stations=20, thickness_ratio=0.20, taper=0.30, branches=2,
               note_ja="主爪に支 2 本（支の数が 3 以上なら近い 2 本）"),
    "T4": dict(name_ja="細い指", segments=3, stations=20, thickness_ratio=0.25, taper=0.45, branches=0,
               note_ja="細長い指（長さ / 幅 ≥ 細さのしきい値）。先細りが強く、側面の厚みの比が大きい（25%）"),
    "T5": dict(name_ja="右側の鉤（型だけ）", segments=3, stations=20, thickness_ratio=0.20, taper=0.30, branches=0,
               note_ja="右側の波の爪（読み B：頭の藍の鉤＝爪先）。右側の爪は主役波のシートに結び付けていない（設計32、低優先・未修正）ので、"
                       "型の定義だけを置き、生成しない（ブラッシュアップの最後）"),
    "branch": dict(name_ja="支（T2・T3 の一部）", segments=3, stations=16, thickness_ratio=0.18, taper=0.35, branches=0,
                   note_ja="支は 3 段に固定し、輪の数を 16 にする（主爪＋支 2 本で 600 頂点以内）"),
}
P = dict(cl_step_ref_px=1.5, depth_window_m=1.5, min_seg_frac=0.10, four_seg_min_len_ref_px=70.0, four_seg_rms_gain=0.40,
         four_seg_rms_min_ref_px=1.0, template_min_len_ref_px=18.0, degenerate_ratio=0.10, refit_min_seg_frac=0.20,
         slender_thin=6.0, branch_sigma=[0.10, 0.95], branch_dist_factor=1.0, branch_dist_add_ref_px=4.0, max_branches=2,
         branch_inside_tol_ref_px=2.0, branch_len_tol=1.05,
         width_cap_len_frac=0.45, width_min_ref_px=4.0, width_max_ref_px=48.0, foreshort_min=0.4,
         growth_samples=41, stage=dict(s1=0.20, s2=0.75, g_birth=0.04, g1=0.12, k0=0.25, k1=0.40, w0=0.30),
         branch_start_margin=0.05, branch_latest_tau=-0.25, ring=8, band_center_frac=0.25,
         skirt=dict(back=0.15, semi_t=0.55, semi_b=0.62, max_radius_m=0.35, lift_m=0.004, n=8))


def growth_curves(s):
    """3 段の標準曲線：戻り値 g（長さ）、κ（曲がり）、ω（幅）。どれも s について減らない。"""
    st = P["stage"]
    s = np.clip(np.asarray(s, np.float64), 0, 1)
    a = U.smoothstep(s / st["s1"])
    b = U.smoothstep((s - st["s1"]) / (st["s2"] - st["s1"]))
    c = U.smoothstep((s - st["s2"]) / (1 - st["s2"]))
    g = np.where(s < st["s1"], st["g_birth"] + (st["g1"] - st["g_birth"]) * a, st["g1"] + (1 - st["g1"]) * b)
    k = st["k0"] + (st["k1"] - st["k0"]) * b + (1 - st["k1"]) * c
    w = st["w0"] + (1 - st["w0"]) * a
    return g, k, w


# ---------------------------------------------------------------- 2 次元の当てはめ
def resample2(P2, step):
    P2 = np.asarray(P2, np.float64)
    s = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P2, axis=0), axis=1))]
    n = max(2, int(round(s[-1] / step)) + 1)
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, P2[:, 0]), np.interp(t, s, P2[:, 1])], -1), s[-1]


def seg_cost_matrix(Pp):
    """cost[a, b] = 点 a..b の、線分 Pp[a]–Pp[b] までの距離の二乗の和。"""
    n = len(Pp)
    cost = np.full((n, n), np.inf)
    idx = np.arange(n)
    for a in range(n - 1):
        B = np.arange(a + 1, n)
        A0 = Pp[a]
        v = Pp[B] - A0                                   # nb × 2
        L2 = np.maximum((v * v).sum(1), 1e-12)
        w = Pp[a:] - A0                                  # np × 2（点 j = a..n−1）
        t = np.clip((w @ v.T) / L2[None, :], 0, 1)       # np × nb
        dx = w[:, 0:1] - t * v[None, :, 0]
        dy = w[:, 1:2] - t * v[None, :, 1]
        d2 = dx * dx + dy * dy
        jj = idx[a:][:, None]
        d2 = np.where(jj <= B[None, :], d2, 0.0)
        cost[a, B] = d2.sum(0)
    return cost


def fit_polyline(Pp, nseg, min_pts):
    n = len(Pp)
    cost = seg_cost_matrix(Pp)
    best = np.full((nseg + 1, n), np.inf)
    arg = np.zeros((nseg + 1, n), int)
    best[0, 0] = 0.0
    for k in range(1, nseg + 1):
        for b in range(1, n):
            a = np.arange(0, b - min_pts + 1)
            if not len(a):
                continue
            v = best[k - 1, a] + cost[a, b]
            j = int(np.argmin(v))
            best[k, b] = v[j]
            arg[k, b] = a[j]
    out = [n - 1]
    for k in range(nseg, 0, -1):
        out.append(arg[k, out[-1]])
    out = out[::-1]
    rms = math.sqrt(best[nseg, n - 1] / n) if np.isfinite(best[nseg, n - 1]) else float("inf")
    return out, rms


def measure2d(J):
    v = np.diff(J, axis=0)
    L = np.linalg.norm(v, axis=1)
    ratio = L / max(L.sum(), 1e-9)
    turns = []
    for i in range(len(v) - 1):
        a, b = v[i], v[i + 1]
        turns.append(math.degrees(math.atan2(a[0] * b[1] - a[1] * b[0], a @ b)))
    return ratio, np.array(turns)


def template_joints(root, tip, sign, nseg=3):
    """型の標準の骨格（利用者の 96 本の中央値）を、根元→先端へ相似で合わせる（画面の座標、y 下向き。sign は曲がりの向き）。"""
    r = np.array(USER100["ratio_median"]); r = r / r.sum()
    th = np.radians(USER100["turn_median_deg"]) * sign
    d = np.array([1.0, 0.0]); p = [np.zeros(2)]
    ang = 0.0
    for i in range(3):
        p.append(p[-1] + r[i] * np.array([math.cos(ang), math.sin(ang)]))
        if i < 2:
            ang += th[i]
    p = np.array(p)
    ch = p[-1] - p[0]
    tgt = np.asarray(tip, float) - np.asarray(root, float)
    s = np.linalg.norm(tgt) / max(np.linalg.norm(ch), 1e-9)
    a = math.atan2(tgt[1], tgt[0]) - math.atan2(ch[1], ch[0])
    R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    return np.asarray(root, float) + (p @ R.T) * s


# ---------------------------------------------------------------- 3 次元の置き方（設計32 の bind_pixel と同じ規則）
class Binder:
    def __init__(self, cam, X0):
        self.cam, self.X0 = cam, X0
        R, C = X0.shape[:2]
        self.R, self.C = R, C
        Tb = K.grid_tris(R, C, U.BODY[0], U.BODY[1])
        self.tris = X0.reshape(-1, 3)[Tb]
        self.idb, _ = K.raster_ids(cam, self.tris, np.arange(1, len(Tb) + 1))
        self.ncol = U.BODY[1] - U.BODY[0]

    def hit(self, xd, yd):
        xi, yi = int(round(xd)), int(round(yd))
        if not (0 <= xi < K.W and 0 <= yi < K.H):
            return None
        d = self.cam.ray(np.array(xd), np.array(yd))
        best = None
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                y2, x2 = yi + dy, xi + dx
                if not (0 <= x2 < K.W and 0 <= y2 < K.H):
                    continue
                t_ = self.idb[y2, x2]
                if t_ == 0:
                    continue
                t = t_ - 1
                s, u, v = U.ray_tri_many(self.cam.pos, d[None, :], *[self.tris[t:t + 1, i] for i in range(3)])
                s, u, v = float(s[0]), float(u[0]), float(v[0])
                err = max(0.0, -u, -v, u + v - 1)
                if best is None or err < best[0] or (err == best[0] and s < best[1]):
                    best = (err, s, u, v, t)
        if best is None:
            return None
        err, s, u, v, t = best
        u, v = min(max(u, 0.0), 1.0), min(max(v, 0.0), 1.0)
        if u + v > 1:
            u, v = u / (u + v), v / (u + v)
        rr, cc = U.tri_to_rc(np.array(t), np.array(u), np.array(v), self.ncol, U.BODY[0])
        return float(rr), float(cc)

    def place(self, qd, depth_ref, window):
        """表示の画素 qd → ('sheet', p, r, c) か ('free', p)。"""
        h = self.hit(qd[0], qd[1])
        if h is not None:
            r, c = h
            p = U.tri_eval(self.X0, np.array(r), np.array(c))
            # 前にある面（見えている面）はいつも採る：原画の爪はそこに描かれているので、その面より奥に置くと隠れる（設計32 の ±1.5 m の窓から変えた）。
            # 奥の面は窓の中だけ採る（窓の外は、空の側の別の面なので、直前の関節の深さの面に置く）
            if float(self.cam.depth(p)) - depth_ref <= window:
                return "sheet", p, r, c
        d = self.cam.ray(np.array(qd[0]), np.array(qd[1]))
        s = depth_ref / float(d @ self.cam.f)
        return "free", self.cam.pos + s * d, None, None


def region_widths(poly_ref, cl_ref):
    """領域（原画の画素の多角形）の距離変換から、中心線の点の幅（原画の画素、= 2 × 距離）。"""
    poly = np.asarray(poly_ref, np.float64)
    x0, y0 = np.floor(np.minimum(poly.min(0), cl_ref.min(0))) - 4
    x1, y1 = np.ceil(np.maximum(poly.max(0), cl_ref.max(0))) + 4
    Wd, Hd = int(x1 - x0) + 1, int(y1 - y0) + 1
    m = np.zeros((Hd, Wd), np.uint8)
    cv2.fillPoly(m, [np.round(poly - [x0, y0]).astype(np.int32)], 1)
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    q = cl_ref - [x0, y0]
    xi = np.clip(np.round(q[:, 0]).astype(int), 0, Wd - 1); yi = np.clip(np.round(q[:, 1]).astype(int), 0, Hd - 1)
    return 2.0 * dt[yi, xi], m, (x0, y0)


# ---------------------------------------------------------------- 本体
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=U.OUT)
    a = ap.parse_args()
    t0 = time.time()
    os.makedirs(a.out, exist_ok=True)
    spec = U.jload(U.TRUTH)
    cam = U.C27.Cam(spec)
    inv = U.jload(U.D32 + "/ds32_claw_inventory.json")
    ids = U.jload(U.D32 + "/ds32_ids.json")
    hero = K.Pkg(U.HERO)
    X0 = hero.world(0.0)
    R, C = X0.shape[:2]
    binder = Binder(cam, X0)
    print("zbuffer %.1fs" % (time.time() - t0), flush=True)
    byid = {c["id"]: c for c in inv["claws"]}
    bound = [c for c in ids["claws"] if c.get("bound")]
    claws = []
    for b in bound:
        cv = byid[b["id"]]
        cl_ref, Lref = resample2(np.asarray(cv["centerline_ref"], np.float64), P["cl_step_ref_px"])
        n = len(cl_ref)
        # 関節（3 段と 4 段）
        min_pts = max(2, int(round(P["min_seg_frac"] * n)))
        how = "fit3"
        if n >= 3 * min_pts + 1 and Lref >= P["template_min_len_ref_px"]:
            j3, rms3 = fit_polyline(cl_ref, 3, min_pts)
            J2 = cl_ref[j3]
            ratio3, turn3 = measure2d(J2)
            nseg = 3
            jj = j3
            rms = rms3
            if Lref >= P["four_seg_min_len_ref_px"] and n >= 4 * min_pts + 1:
                j4, rms4 = fit_polyline(cl_ref, 4, min_pts)
                if rms3 >= P["four_seg_rms_min_ref_px"] and rms4 <= (1 - P["four_seg_rms_gain"]) * rms3:
                    nseg, jj, rms, how = 4, j4, rms4, "fit4"
            J2 = cl_ref[jj]
            ratio, turn = measure2d(J2)
            if ratio.min() < P["degenerate_ratio"]:
                # 節が潰れる当てはめは、節の最小を大きくして当て直す（型の標準の骨格には替えない：原画の形を先にする）
                mp2 = max(2, int(round(P["refit_min_seg_frac"] * n)))
                if n >= nseg * mp2 + 1:
                    jj, rms = fit_polyline(cl_ref, nseg, mp2)
                    J2 = cl_ref[jj]
                    how = how + "_refit"
        else:
            how = "template_short"
            rms = None
        if how.startswith("template"):
            ch = cl_ref[-1] - cl_ref[0]
            mid = cl_ref[len(cl_ref) // 2] - cl_ref[0]
            # 中心線が弦のどちら側にふくらむかで曲がりの向きを決める（画面 y 下向き：弦 × 中点 ≤ 0 なら転折は正の向き）
            sign = 1.0 if (ch[0] * mid[1] - ch[1] * mid[0]) <= 0 else -1.0
            J2 = template_joints(cl_ref[0], cl_ref[-1], sign)
            nseg = 3
            jj = None
        ratio, turn = measure2d(J2)
        # 幅（原画の画素）
        wmeas, _, _ = region_widths(cv["region_polygon_ref"], cl_ref)
        sig = np.linspace(0, 1, n)
        claws.append(dict(id=b["id"], row=b["row"], origin=b["origin"], b_region_q16=b["b_region_q16"], group=b.get("group"),
                          sheet_rc=b["sheet_rc"], tau_birth=b["tau_birth"], root_depth=b["root_cam_depth_m"],
                          cl_ref=cl_ref, len_ref=Lref, J2=J2, nseg=nseg, joint_how=how, fit_rms_ref_px=rms,
                          ratio2d=ratio, turn2d=turn, wmeas=wmeas, sig=sig, region=cv["region_polygon_ref"],
                          root_ref=np.asarray(cv["root_ref"], float), tip_ref=np.asarray(cv["tip_ref"], float), status=cv.get("status")))
    print("fit %d claws %.1fs" % (len(claws), time.time() - t0), flush=True)

    # ---- 型：支（根元が他の爪の領域の中）
    polys = {c["id"]: np.asarray(c["region"], np.float32) for c in claws}
    order = sorted(claws, key=lambda c: -c["len_ref"])
    cand = {}
    for A in claws:
        for B in claws:
            if A is B or B["len_ref"] > P["branch_len_tol"] * A["len_ref"]:
                continue
            if cv2.pointPolygonTest(polys[A["id"]].reshape(-1, 1, 2), (float(B["root_ref"][0]), float(B["root_ref"][1])), True) < -P["branch_inside_tol_ref_px"]:
                continue
            d = np.linalg.norm(A["cl_ref"] - B["root_ref"], axis=1)
            k = int(np.argmin(d))
            sa = A["sig"][k]
            wA = float(A["wmeas"][k]) if A["wmeas"][k] > 0 else 6.0
            if not (P["branch_sigma"][0] <= sa <= P["branch_sigma"][1]):
                continue
            if d[k] > P["branch_dist_factor"] * wA + P["branch_dist_add_ref_px"]:
                continue
            cand.setdefault(A["id"], []).append((float(d[k]), B["id"], float(sa)))
    parent_of, children = {}, {}
    for A in order:
        if A["id"] in parent_of:
            continue
        for d_, bid, sa in sorted(cand.get(A["id"], [])):
            if bid in parent_of or bid in children or len(children.get(A["id"], [])) >= P["max_branches"]:
                continue
            parent_of[bid] = (A["id"], sa, d_)
            children.setdefault(A["id"], []).append(bid)
    for c in claws:
        wm = c["wmeas"][(c["sig"] >= 0.1) & (c["sig"] <= 0.8)]
        wm = wm[wm > 0]
        c["w_mean_ref"] = float(np.mean(wm)) if len(wm) else float(np.mean(c["wmeas"][c["wmeas"] > 0])) if (c["wmeas"] > 0).any() else P["width_min_ref_px"]
        c["slender"] = c["len_ref"] / max(c["w_mean_ref"], 1.0)
        if c["id"] in parent_of:
            c["type"] = "branch"; c["parent"] = parent_of[c["id"]][0]; c["attach_sigma"] = parent_of[c["id"]][1]
        elif c["id"] in children:
            c["type"] = "T2" if len(children[c["id"]]) == 1 else "T3"; c["children"] = children[c["id"]]
        elif c["slender"] >= P["slender_thin"]:
            c["type"] = "T4"
        else:
            c["type"] = "T1"
        if c["type"] == "branch" and c["nseg"] == 4:     # 支は 3 段に固定
            j3, _ = fit_polyline(c["cl_ref"], 3, max(2, int(round(P["min_seg_frac"] * len(c["cl_ref"])))))
            c["J2"] = c["cl_ref"][j3]; c["nseg"] = 3; c["joint_how"] = "fit3_branch"
            c["ratio2d"], c["turn2d"] = measure2d(c["J2"])

    # ---- 幅の型の形（原画の画素）：根元が広く、先端が閉じる
    for c in claws:
        ty = TYPES[c["type"]]
        n_st = ty["stations"]
        sj = np.arange(n_st) / n_st
        wm = np.interp(sj, c["sig"], np.where(c["wmeas"] > 0, c["wmeas"], np.nan))
        wm = np.where(np.isfinite(wm), wm, c["w_mean_ref"])
        wm = cv2.GaussianBlur(wm.reshape(-1, 1).astype(np.float64), (1, 5), 1.0).ravel()
        w_root = float(np.max(wm[(sj >= 0.05) & (sj <= 0.35)])) if ((sj >= 0.05) & (sj <= 0.35)).any() else float(wm[0])
        w_root = float(np.clip(w_root, P["width_min_ref_px"], min(P["width_max_ref_px"], P["width_cap_len_frac"] * c["len_ref"] + 2)))
        prof = w_root * (1 - ty["taper"] * sj)
        w = np.minimum(np.maximum(wm, 0.6 * prof), prof)
        w = np.minimum.accumulate(w)
        clos = np.sqrt(np.clip(1 - U.smoothstep((sj - 0.72) / 0.28), 0, 1))
        c["w_ref_st"] = np.maximum(w * clos, 0.0)
        c["w_root_ref"] = w_root
        c["sj"] = sj

    # ---- 関節を t* の 3 次元へ
    for c in claws:
        r0, c0 = c["sheet_rc"]
        p_root = U.tri_eval(X0, np.array(r0), np.array(c0))
        dep = float(cam.depth(p_root))
        c["root_depth"] = dep
        J3, kind, rc = [p_root], ["sheet"], [(r0, c0)]
        Jd = U.to_disp(c["J2"])
        for q in Jd[1:]:
            dprev = float(cam.depth(J3[-1]))
            k_, p_, rr_, cc_ = binder.place(q, dprev, P["depth_window_m"])
            J3.append(p_); kind.append(k_); rc.append((rr_, cc_))
        c["J3"] = np.array(J3); c["kind"] = kind; c["rc_final"] = rc
        c["hanging"] = any(k_ == "free" for k_ in kind)
    print("placed %.1fs" % (time.time() - t0), flush=True)

    # ---- 成長の段の結び付け
    Ms = P["growth_samples"]
    svals = np.linspace(0, 1, Ms)
    gk = growth_curves(svals)
    for c in claws:
        J = c["J3"]
        nj = len(J)
        v = np.diff(J, axis=0)
        L = np.linalg.norm(v, axis=1)
        d = v / np.maximum(L[:, None], 1e-12)
        axes, ang = [], []
        for k in range(1, nj - 1):
            ax = np.cross(d[k - 1], d[k])
            sn = np.linalg.norm(ax)
            cs = float(np.clip(d[k - 1] @ d[k], -1, 1))
            axes.append(ax / sn if sn > 1e-9 else np.array([0.0, 0.0, 1.0]))
            ang.append(math.atan2(sn, cs))
        c["turn3d_deg"] = [math.degrees(x) for x in ang]
        c["seg_len_m"] = L
        # 各関節の参照（シートに付く関節は自分、空の関節は直前のシートの関節）
        ref = []
        last = 0
        for k in range(nj):
            if c["kind"][k] == "sheet":
                last = k
            ref.append(last)
        c["ref"] = ref
        RC = np.zeros((Ms, nj, 2)); E = np.zeros((Ms, nj, 3))
        prev_rc = np.array([rc if rc[0] is not None else c["sheet_rc"] for rc in c["rc_final"]], np.float64)
        for m in range(Ms - 1, -1, -1):
            g, kap = gk[0][m], gk[1][m]
            Pk = [J[0]]
            dk = d[0].copy()
            for k in range(nj - 1):
                if k >= 1:
                    th = kap * ang[k - 1]
                    ax = axes[k - 1]
                    dk = dk * math.cos(th) + np.cross(ax, dk) * math.sin(th) + ax * (ax @ dk) * (1 - math.cos(th))
                Pk.append(Pk[-1] + g * L[k] * dk)
            Pk = np.array(Pk)
            # シートに付く関節
            bk = [k for k in range(nj) if c["kind"][k] == "sheet"]
            rr, cc_, hh, tg = U.project_to_sheet(X0, Pk[bk], prev_rc[bk])
            rr[0], cc_[0] = c["sheet_rc"]                      # 根元は動かさない
            for i, k in enumerate(bk):
                RC[m, k] = (rr[i], cc_[i])
            prev_rc[bk] = RC[m, bk]
            for k in range(nj):
                rk = RC[m, ref[k]]
                F = U.frame_at(X0, np.array(rk[0]), np.array(rk[1]))
                S = U.tri_eval(X0, np.array(rk[0]), np.array(rk[1]))
                E[m, k] = F @ (Pk[k] - S)
                if c["kind"][k] != "sheet":
                    RC[m, k] = rk
            # シートに付く関節は面の上へ置く（伸ばした形がシートから浮く・沈む分は捨てる）。根元は 0
            for k in bk:
                E[m, k] = 0.0
        c["RC"] = RC; c["E"] = E
        # 法線（参照の座標系の中）：シートの上の爪は面の法線、空へ出る爪は t* で PaintingCam を向く面
        NL = np.zeros((nj, 3))
        for k in range(nj):
            rk = RC[-1, ref[k]]
            F = U.frame_at(X0, np.array(rk[0]), np.array(rk[1]))
            if not c["hanging"]:
                NL[k] = [0, 0, 1.0]
            else:
                Tk = J[min(k + 1, nj - 1)] - J[max(k - 1, 0)]
                Tk /= np.linalg.norm(Tk)
                vv = cam.pos - J[k]; vv /= np.linalg.norm(vv)
                nn = vv - (vv @ Tk) * Tk
                nn /= max(np.linalg.norm(nn), 1e-9)
                NL[k] = F @ nn
        c["NL"] = NL
    print("growth bindings %.1fs" % (time.time() - t0), flush=True)

    # ---- 支の成長の開始（主爪が支の根元まで伸びてから）
    byc = {c["id"]: c for c in claws}
    sg = np.linspace(0, 1, 2001)
    gg = growth_curves(sg)[0]
    for c in claws:
        c["tau_start"] = float(c["tau_birth"])
        c["tau_start_from"] = "根元の T_white（設計32 の tau_birth）"
    for c in claws:
        if c["type"] != "branch":
            continue
        A = byc[c["parent"]]
        need = min(c["attach_sigma"] + P["branch_start_margin"], 1.0)
        s_reach = float(sg[np.argmax(gg >= need)])
        tau_reach = A["tau_birth"] + s_reach * (0.0 - A["tau_birth"])
        ts = max(c["tau_birth"], tau_reach)
        if ts > P["branch_latest_tau"]:
            ts = P["branch_latest_tau"]
            c["tau_start_from"] = "主爪が支の根元に届く τ %.3f s が遅すぎるので %.2f s に切った" % (tau_reach, P["branch_latest_tau"])
        else:
            c["tau_start_from"] = ("主爪 %s が支の根元（主爪の中心線の %.2f）まで伸びる τ %.3f s" % (A["id"], c["attach_sigma"], tau_reach)
                                   if ts == tau_reach else "根元の T_white（主爪は先に届いている）")
        c["tau_start"] = float(ts)

    # ---- 幅を m に（t* の最終の形で、横向きの縮みを測る）
    for c in claws:
        ty = TYPES[c["type"]]
        n_st = ty["stations"]
        J = c["J3"]
        Pd, par = U.catmull_rom(J, 16)
        St, sfrac, Lm = U.resample_arc(Pd, n_st + 1)
        seg_idx = np.clip(np.floor(par).astype(int), 0, len(J) - 2)
        # 関節の法線（t*）
        Nj = np.array([U.frame_at(X0, np.array(c["RC"][-1, c["ref"][k]][0]), np.array(c["RC"][-1, c["ref"][k]][1])).transpose(1, 0) @ c["NL"][k]
                       for k in range(len(J))])
        fr = np.clip(par - seg_idx, 0, 1)
        Nd = Nj[seg_idx] * (1 - fr)[:, None] + Nj[seg_idx + 1] * fr[:, None]
        Ns = np.stack([np.interp(np.linspace(0, 1, n_st + 1), sfrac, Nd[:, j]) for j in range(3)], -1)
        T = np.gradient(St, axis=0)
        T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
        B = np.cross(Ns, T); B /= np.maximum(np.linalg.norm(B, axis=1, keepdims=True), 1e-12)
        q0, z0 = cam.project(St[:n_st]); q1, _ = cam.project(St[:n_st] + 0.01 * B[:n_st])
        pxm = np.linalg.norm(q1 - q0, axis=1) / 0.01
        pp = cam.focal_px / np.maximum(z0, 1e-6)
        fsh = np.clip(pxm / pp, P["foreshort_min"], 1.0)
        w_m = c["w_ref_st"] * U.A_DISP * (z0 / cam.focal_px) / fsh
        c["w_m_st"] = w_m
        c["foreshort"] = fsh
        c["len_m"] = float(Lm)
        c["thick_m_st"] = ty["thickness_ratio"] * w_m
        # 根元の白の円（シートの (行, 列) のずれ）
        sk = P["skirt"]
        w0 = float(min(w_m[0], sk["max_radius_m"] / sk["semi_b"]))
        r0, c0 = c["sheet_rc"]
        dr, dc = U.bilin_d(X0, np.array(r0), np.array(c0))
        Jm = np.stack([dr, dc], 1)                       # 3 × 2
        pinv = np.linalg.pinv(Jm)
        offs = [pinv @ (-sk["back"] * w0 * T[0])]
        for i in range(sk["n"]):
            ps = 2 * math.pi * i / sk["n"]
            offs.append(pinv @ ((-sk["back"] * w0 + sk["semi_t"] * w0 * math.cos(ps)) * T[0] + sk["semi_b"] * w0 * math.sin(ps) * B[0]))
        c["skirt_drc"] = np.array(offs)
        c["n_vert"] = 1 + n_st * P["ring"] + 1 + 1 + sk["n"]
    print("widths %.1fs" % (time.time() - t0), flush=True)

    # ---- 書き出し
    order_ids = [c["id"] for c in claws]
    npz = {}
    for i, c in enumerate(claws):
        npz["RC_%s" % c["id"]] = c["RC"].astype(np.float64)
        npz["E_%s" % c["id"]] = c["E"].astype(np.float64)
        npz["NL_%s" % c["id"]] = c["NL"]
        npz["W_%s" % c["id"]] = c["w_m_st"]
        npz["TH_%s" % c["id"]] = c["thick_m_st"]
        npz["SK_%s" % c["id"]] = c["skirt_drc"]
        npz["J3_%s" % c["id"]] = c["J3"]
    np.savez(os.path.join(a.out, "ds33_claw_rig.npz"), svals=svals, ids=np.array(order_ids), **npz)
    rows = []
    for c in claws:
        rows.append(dict(id=c["id"], row=c["row"], origin=c["origin"], b_region_q16=c["b_region_q16"], group=c["group"], type=c["type"],
                         type_name_ja=TYPES[c["type"]]["name_ja"], parent=c.get("parent"), children=c.get("children", []),
                         attach_sigma=U.rnd(c.get("attach_sigma"), 3), segments=c["nseg"], joint_how=c["joint_how"],
                         fit_rms_ref_px=U.rnd(c["fit_rms_ref_px"], 3), len_ref_px=U.rnd(c["len_ref"], 2), len_m=U.rnd(c["len_m"], 4),
                         w_root_ref_px=U.rnd(c["w_root_ref"], 2), w_mean_ref_px=U.rnd(c["w_mean_ref"], 2), slender=U.rnd(c["slender"], 3),
                         w_root_m=U.rnd(c["w_m_st"][0], 4), thickness_ratio=TYPES[c["type"]]["thickness_ratio"],
                         ratio2d=U.rnd(c["ratio2d"], 4), turn2d_deg=U.rnd(c["turn2d"], 2), turn3d_deg=U.rnd(c["turn3d_deg"], 2),
                         seg_len_m=U.rnd(c["seg_len_m"], 4), joints_ref=U.rnd(c["J2"], 2), joints_world_tstar=U.rnd(c["J3"], 4),
                         joint_kind=c["kind"], joint_ref=c["ref"], hanging=c["hanging"], sheet_rc=c["sheet_rc"],
                         tau_birth=c["tau_birth"], tau_start=U.rnd(c["tau_start"], 4), tau_start_from_ja=c["tau_start_from"],
                         stations=TYPES[c["type"]]["stations"], n_vert=c["n_vert"], foreshort_min=U.rnd(float(c["foreshort"].min()), 3),
                         status32=c["status"]))
    import collections
    tc = collections.Counter(c["type"] for c in claws)
    j3 = [c for c in claws if c["nseg"] == 3]
    stats = dict(
        types=dict(tc), segments={"3": sum(1 for c in claws if c["nseg"] == 3), "4": sum(1 for c in claws if c["nseg"] == 4)},
        joint_how=dict(collections.Counter(c["joint_how"] for c in claws)),
        hanging=sum(1 for c in claws if c["hanging"]),
        list_ratio_median_3seg=U.rnd(np.median(np.array([c["ratio2d"] for c in j3]), axis=0), 4),
        list_ratio_p25_3seg=U.rnd(np.percentile(np.array([c["ratio2d"] for c in j3]), 25, axis=0), 4),
        list_ratio_p75_3seg=U.rnd(np.percentile(np.array([c["ratio2d"] for c in j3]), 75, axis=0), 4),
        list_turn_abs_median_3seg_deg=U.rnd(np.median(np.abs(np.array([c["turn2d"] for c in j3])), axis=0), 2),
        list_turn_abs_p25_3seg_deg=U.rnd(np.percentile(np.abs(np.array([c["turn2d"] for c in j3])), 25, axis=0), 2),
        list_turn_abs_p75_3seg_deg=U.rnd(np.percentile(np.abs(np.array([c["turn2d"] for c in j3])), 75, axis=0), 2),
        n_vert_max=max(c["n_vert"] for c in claws),
        instance_vert_max=max(c["n_vert"] + sum(byc[k]["n_vert"] for k in c.get("children", [])) for c in claws if c["type"] != "branch"),
        slender_percentiles=U.rnd(np.percentile([c["slender"] for c in claws], [10, 25, 50, 75, 90]), 2),
    )
    rig = dict(schema="GreatWave.DS33.claw_rig/1", number="設計33（爪の部）", note_ja=__doc__, params=P, user100=USER100, types=TYPES,
               stats=stats, claws=rows, sheet=dict(package=U.rel(U.HERO), rows=R, cols=C, body_cols=list(U.BODY)),
               inputs=dict(inventory=dict(path=U.rel(U.D32 + "/ds32_claw_inventory.json"), sha256=U.sha(U.D32 + "/ds32_claw_inventory.json")),
                           ids=dict(path=U.rel(U.D32 + "/ds32_ids.json"), sha256=U.sha(U.D32 + "/ds32_ids.json")),
                           claw_readme=dict(path=U.CLAW_README, sha256=U.sha(U.CLAW_README)),
                           painting_truth=dict(path=U.rel(U.TRUTH), sha256=U.sha(U.TRUTH))),
               elapsed_s=round(time.time() - t0, 1))
    U.jdump(os.path.join(a.out, "ds33_claw_rig.json"), rig)
    print(stats)
    print("done %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
