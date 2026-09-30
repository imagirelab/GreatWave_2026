# -*- coding: utf-8 -*-
"""設計42：静水で重量・排水容積・重心を合わせる（前計算）。

設計41 の浮力用の閉じた船体（Boat41_Buoyancy、ds41_boat_geom.npz）から、
  1. 重量と重心：船の部品（設計41 のメッシュの面積・体積 × 板厚・密度の推定）＋乗員・荷・道具の推定を足し、質量・重心・慣性を出す。
  2. 厳密な静水の釣り合い：船体を鉛直の柱に分けた積分（柱の底と天井の高さ）で、任意の傾いた水面の下の容積と浮心を出し、
     ρ V = m、浮心と重心が同じ鉛直線に並ぶ（喫水・縦傾斜・横傾斜）を Newton 法で解く。三角形を水面で切る方法で容積を別に確かめる。
  3. 浮力点：船底に 5 断面 × 左右 2 = 10 点（設計41 の提案の断面）。各点は船体の区画（縦の 5 区間 × 左右）を受け持ち、
     その点での水面の高さ（船の局所の上向き）に対する区画の排水容積・浮心・水線面積の表を持つ。Unity の DS42Buoyancy が読む。
  4. 浮力点の模型（Unity と同じ計算）を Python でも解き、厳密な釣り合いとの差（喫水・縦傾斜・容積・横と縦の復原の硬さ）を出す。
座標：計算は Blender の船の局所（x 左舷、y 船尾、z 上、単位は設計41 の「置き方の枠」＝先端間 10）。Unity の局所へは (x, y, z) → (−x, z, −y)。
実寸は座席の船（boat_mid）の縮尺 s（m / 単位）を掛ける（設計41 の場面の根の lossyScale）。

使い方（リポジトリの根で）: py -3.10 -B Tools/GWWaveGen/ds42/ds42_hydro.py
"""
import hashlib
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
B41 = os.path.join(REPO, "Unity", "Build", "Design", "41", "model")
NPZ = os.path.join(B41, "blender", "ds41_boat_geom.npz")
REP41 = os.path.join(B41, "blender", "ds41_blender_report.json")
BUILD41 = os.path.join(B41, "unity", "ds41_build_report.json")
RESEARCH41 = os.path.join(REPO, "Unity", "Build", "Design", "41", "research", "oshiokuri_dimensions.json")
PARAMS = os.path.join(HERE, "ds42_params.json")
OUT = os.path.join(REPO, "Unity", "Build", "Design", "42", "buoyancy")
ASSET = os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design42", "Data", "ds42_buoyancy_points.json")


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_mesh(z, name):
    return z[name + "__v"].astype(np.float64), z[name + "__t"].astype(np.int64)


# ------------------------------------------------------------------ 柱の積分（鉛直の柱ごとの船底と天井）
def columns(v, t, step):
    """閉じたメッシュを z 方向の柱に分け、各柱の底 zb と天井 zt を返す（格子の中心は (i+0.5)·step）。"""
    x0, y0 = v[:, 0].min(), v[:, 1].min()
    nx = int(math.ceil((v[:, 0].max() - x0) / step)) + 1
    ny = int(math.ceil((v[:, 1].max() - y0) / step)) + 1
    hits = [[] for _ in range(nx * ny)]
    for tri in t:
        a, b, c = v[tri[0]], v[tri[1]], v[tri[2]]
        det = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
        if abs(det) < 1e-12:
            continue  # 鉛直の面（柱に平行）
        xs = (a[0], b[0], c[0]); ys = (a[1], b[1], c[1])
        i0 = max(0, int(math.floor((min(xs) - x0) / step - 0.5)) - 1); i1 = min(nx - 1, int(math.ceil((max(xs) - x0) / step - 0.5)) + 1)
        j0 = max(0, int(math.floor((min(ys) - y0) / step - 0.5)) - 1); j1 = min(ny - 1, int(math.ceil((max(ys) - y0) / step - 0.5)) + 1)
        I, J = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1), indexing="ij")
        px = x0 + (I + 0.5) * step; py = y0 + (J + 0.5) * step
        l1 = ((b[0] - px) * (c[1] - py) - (c[0] - px) * (b[1] - py)) / det
        l2 = ((c[0] - px) * (a[1] - py) - (a[0] - px) * (c[1] - py)) / det
        l3 = 1 - l1 - l2
        m = (l1 >= -1e-12) & (l2 >= -1e-12) & (l3 >= -1e-12)
        if not m.any():
            continue
        zz = l1 * a[2] + l2 * b[2] + l3 * c[2]
        for i, j, zv in zip(I[m], J[m], zz[m]):
            hits[i * ny + j].append(zv)
    xs, ys, zb, zt = [], [], [], []
    bad = 0
    for k, h in enumerate(hits):
        if len(h) < 2:
            if h:
                bad += 1
            continue
        i, j = divmod(k, ny)
        xs.append(x0 + (i + 0.5) * step); ys.append(y0 + (j + 0.5) * step)
        zb.append(min(h)); zt.append(max(h))
    return np.array(xs), np.array(ys), np.array(zb), np.array(zt), bad


class Hull:
    def __init__(self, xs, ys, zb, zt, step):
        self.x, self.y, self.zb, self.zt, self.da = xs, ys, zb, zt, step * step

    def immersed(self, a, bx, by, mask=None):
        """船の局所の平面 z = a + bx·x + by·y の下の容積・浮心（柱の積分）。"""
        x, y, zb, zt = self.x, self.y, self.zb, self.zt
        if mask is not None:
            x, y, zb, zt = x[mask], y[mask], zb[mask], zt[mask]
        zp = a + bx * x + by * y
        h = np.clip(zp - zb, 0.0, zt - zb)
        V = h.sum() * self.da
        if V <= 0:
            return 0.0, np.zeros(3)
        c = np.array([(h * x).sum(), (h * y).sum(), (h * (zb + 0.5 * h)).sum()]) * self.da / V
        return V, c

    def waterplane(self, level, mask=None):
        x, y, zb, zt = self.x, self.y, self.zb, self.zt
        if mask is not None:
            x, y, zb, zt = x[mask], y[mask], zb[mask], zt[mask]
        w = (zb < level) & (zt > level)
        A = w.sum() * self.da
        if A <= 0:
            return 0.0, 0.0, 0.0, 0.0, 0.0
        xc = (x[w]).sum() * self.da / A; yc = (y[w]).sum() * self.da / A
        Ixx = ((x[w] - xc) ** 2).sum() * self.da   # 横（船首尾の軸まわり）
        Iyy = ((y[w] - yc) ** 2).sum() * self.da   # 縦
        return A, xc, yc, Ixx, Iyy


def clip_volume(v, t, a, bx, by):
    """三角形を平面で切って、平面の下の閉じたメッシュの容積と浮心（平面上の点を頂点にした四面体の和。蓋の面は容積 0）。"""
    n = np.array([-bx, -by, 1.0])
    o = np.array([0.0, 0.0, a])
    d = (v - o) @ n  # <0 が水面の下
    V = 0.0; M = np.zeros(3)
    for tri in t:
        P = [v[i] for i in tri]; D = [d[i] for i in tri]
        poly = []
        for k in range(3):
            p, q, dp, dq = P[k], P[(k + 1) % 3], D[k], D[(k + 1) % 3]
            if dp <= 0:
                poly.append(p)
            if (dp < 0) != (dq < 0) and dp != dq:
                s = dp / (dp - dq); poly.append(p + s * (q - p))
        for k in range(1, len(poly) - 1):
            A, B, C = poly[0] - o, poly[k] - o, poly[k + 1] - o
            vol = np.dot(A, np.cross(B, C)) / 6.0
            V += vol; M += vol * (A + B + C) / 4.0
    return V, (M / V + o) if V != 0 else o


def up_dir(bx, by):
    n = np.array([-bx, -by, 1.0]); return n / np.linalg.norm(n)


def solve_equilibrium(vol_fn, Vt, G, a0, iters=40):
    """vol_fn(a, bx, by) → (V, B)。ρV s³ = m（V = Vt）と B−G ∥ 上向き を満たす (a, bx, by)。"""
    p = np.array([a0, 0.0, 0.0])

    def res(q):
        V, Bc = vol_fn(*q)
        u = up_dir(q[1], q[2]); r = Bc - G; perp = r - np.dot(r, u) * u
        return np.array([V / Vt - 1.0, perp[0], perp[1]])

    for _ in range(iters):
        r = res(p)
        if np.abs(r).max() < 1e-9:
            break
        J = np.zeros((3, 3)); h = np.array([1e-4, 1e-5, 1e-5])
        for k in range(3):
            dq = np.zeros(3); dq[k] = h[k]
            J[:, k] = (res(p + dq) - res(p - dq)) / (2 * h[k])
        p = p - np.linalg.solve(J, r)
    return p, res(p)


def righting_stiffness(vol_fn, Vt, G, p, axis, delta=math.radians(1.0)):
    """平衡から、軸（'heel' か 'trim'）の向きに delta だけ傾けた水面で容積を保つ a を探し、
    浮心と重心の水平の離れ（復原のてこ）から、硬さ（容積 × てこ / 角 ＝ GM × V）を返す。"""
    a, bx, by = p
    out = []
    for sgn in (1, -1):
        bx2 = bx + (sgn * math.tan(delta) if axis == "heel" else 0.0)
        by2 = by + (sgn * math.tan(delta) if axis == "trim" else 0.0)
        aa = a
        for _ in range(30):
            V, _ = vol_fn(aa, bx2, by2)
            V2, _ = vol_fn(aa + 1e-4, bx2, by2)
            aa -= (V - Vt) / ((V2 - V) / 1e-4)
        V, Bc = vol_fn(aa, bx2, by2)
        u = up_dir(bx2, by2); r = Bc - G; perp = r - np.dot(r, u) * u
        comp = perp[0] if axis == "heel" else perp[1]
        out.append(comp)
    # 傾けた向きへ浮心が動けば復原（符号は GM > 0 で正になるように）
    gz = 0.5 * (out[0] - out[1])
    return gz / delta


def main():
    t0 = time.time()
    prm = json.load(open(PARAMS, encoding="utf-8"))
    z = np.load(NPZ)
    rep41 = json.load(open(REP41, encoding="utf-8"))
    b41 = json.load(open(BUILD41, encoding="utf-8"))
    s = float([b for b in b41["boats"] if b["key"] == prm["boat_key"]][0]["scale"]["x"])
    rho, g = prm["rho_kg_m3"], prm["g_m_s2"]

    # ---------------------------------------------------------------- 重量と重心（部品ごと）
    parts = []

    def add(name, mass, pos_units, kind, basis, extent_units=None):
        parts.append({"name": name, "mass_kg": float(mass), "pos_units": [float(q) for q in pos_units], "kind": kind, "basis_ja": basis,
                      "extent_units": extent_units})

    hv, ht = load_mesh(z, "Boat41_Hull")
    a_, b_, c_ = hv[ht[:, 0]], hv[ht[:, 1]], hv[ht[:, 2]]
    cr = np.cross(b_ - a_, c_ - a_); ar = 0.5 * np.linalg.norm(cr, axis=1); nz = np.abs(cr[:, 2]) / np.maximum(1e-12, 2 * ar)
    cen = (a_ + b_ + c_) / 3.0
    wd = prm["wood"]
    bottom = nz > 0.7
    shell_rows = []
    for m_, thick, label in ((bottom, wd["bottom_thickness_m"], "航（船底板）"), (~bottom, wd["plank_thickness_m"], "根棚・上棚・戸立（舷の板）")):
        area_m2 = ar[m_].sum() * s * s
        mass = area_m2 * thick * wd["sugi_density_kg_m3"]
        pos = (cen[m_] * ar[m_, None]).sum(0) / ar[m_].sum()
        # 慣性のため、三角形ごとの点の質量の組も持つ
        shell_rows.append((cen[m_], ar[m_] / ar[m_].sum() * mass))
        add("船殻：" + label, mass, pos, "estimate",
            "設計41 の船殻のメッシュの面積 %.2f m²（|n_z|>0.7 を船底とした）× 板厚 %.3f m × 杉の気乾密度 %d kg/m³" % (area_m2, thick, wd["sugi_density_kg_m3"]))
    solid = {"Boat41_Floor": ("床（板）", wd["sugi_density_kg_m3"]), "Boat41_Beams": ("船梁 6 本", wd["beam_density_kg_m3"]),
             "Boat41_Gunwale_Port": ("船縁（左舷）", wd["beam_density_kg_m3"]), "Boat41_Gunwale_Starboard": ("船縁（右舷）", wd["beam_density_kg_m3"]),
             "Boat41_Stem": ("水押", wd["beam_density_kg_m3"]), "Boat41_SternDeck": ("船尾の床", wd["sugi_density_kg_m3"]),
             "Boat41_SternFrame": ("船尾の梯子状の枠", wd["sugi_density_kg_m3"])}
    for i in range(1, 5):
        solid["Boat41_Oar_P%d" % i] = ("櫓 P%d" % i, wd["oar_density_kg_m3"])
    for i in range(1, 4):
        solid["Boat41_Oar_S%d" % i] = ("櫓 S%d" % i, wd["oar_density_kg_m3"])
    for nm, (label, dens) in solid.items():
        v, t = load_mesh(z, nm)
        a1, b1, c1 = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
        tv = np.einsum("ij,ij->i", a1, np.cross(b1, c1)) / 6.0
        vol = tv.sum()
        cpos = (tv[:, None] * (a1 + b1 + c1) / 4.0).sum(0) / vol
        add(label, vol * s ** 3 * dens, cpos, "estimate", "設計41 の %s の閉じたメッシュの体積 %.4f m³ × 密度 %d kg/m³" % (nm, vol * s ** 3, dens),
            extent_units=[(v.max(0) - v.min(0)).tolist()])
    # 床の上面の高さ（乗員・荷を置く）
    floor_tab = rep41["tables"]["floor"]
    fy = np.array([r["y"] for r in floor_tab]); fz = np.array([r["top_z"] for r in floor_tab])

    def floor_top(y):
        return float(np.interp(y, fy, fz))

    cw = prm["crew"]
    crew_y = list(np.linspace(cw["rowers_y_from"], cw["rowers_y_to"], cw["rowers"])) + list(cw["front_y"])
    for i, y in enumerate(crew_y):
        zc = floor_top(y) + cw["cg_above_floor_m"] / s
        add("乗員 %d（%s）" % (i + 1, "漕ぎ手" if i < cw["rowers"] else "船首側"), cw["mass_each_kg"], [0.0, y, zc], "estimate", cw["basis_ja"])
    for it in prm["items"]:
        y = it["y_units"]; zc = floor_top(y) + it["cg_above_floor_m"] / s if it.get("on_floor", True) else it["z_units"]
        add(it["name_ja"], it["mass_kg"], [0.0, y, zc], "estimate", it["basis_ja"], extent_units=it.get("extent_units"))

    M = sum(p["mass_kg"] for p in parts)
    G = sum(np.array(p["pos_units"]) * p["mass_kg"] for p in parts) / M  # 単位の座標
    # 慣性（重心まわり、m²·kg。船殻は三角形ごとの点、ほかは点の質量＋直方体の広がり）
    I = np.zeros((3, 3))

    def pt_inertia(m, r):
        return m * (np.dot(r, r) * np.eye(3) - np.outer(r, r))

    for cens, ms in shell_rows:
        for cpos, mm in zip(cens, ms):
            I += pt_inertia(mm, (cpos - G) * s)
    for p in parts:
        if p["name"].startswith("船殻"):
            continue
        r = (np.array(p["pos_units"]) - G) * s
        I += pt_inertia(p["mass_kg"], r)
        ext = p.get("extent_units")
        if ext:
            e = np.array(ext[0] if isinstance(ext[0], list) else ext) * s
            I += p["mass_kg"] / 12.0 * np.diag([e[1] ** 2 + e[2] ** 2, e[0] ** 2 + e[2] ** 2, e[0] ** 2 + e[1] ** 2])
        if p["name"].startswith("乗員"):
            I += p["mass_kg"] * cw["own_gyration_m"] ** 2 * np.eye(3)

    # ---------------------------------------------------------------- 厳密な静水（柱の積分）
    bv, bt = load_mesh(z, "Boat41_Buoyancy")
    step = prm["column_step_units"]
    xs, ys, zb, zt, bad = columns(bv, bt, step)
    hull = Hull(xs, ys, zb, zt, step)
    Vfull = (zt - zb).sum() * hull.da
    Vmesh = rep41["hydrostatics"]["closed_mesh_volume_units3"]
    Vt = M / rho / s ** 3  # 必要な排水容積（単位³）

    def vol_exact(a, bx, by):
        return hull.immersed(a, bx, by)

    # 初期値：水平の水面で容積が合う高さ
    lo, hi = 0.0, float(zt.max())
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if hull.immersed(mid, 0, 0)[0] < Vt:
            lo = mid
        else:
            hi = mid
    p_ex, r_ex = solve_equilibrium(vol_exact, Vt, G, 0.5 * (lo + hi))
    V_ex, B_ex = vol_exact(*p_ex)
    Vclip, Bclip = clip_volume(bv, bt, *p_ex)
    u = up_dir(p_ex[1], p_ex[2])
    draft_mid_units = p_ex[0] * u[2]  # 原点（船体中央の船底）から水面までの、水面に垂直な距離
    trim_deg = math.degrees(math.atan(p_ex[2]))   # 正：船尾（+y）が沈む
    heel_deg = math.degrees(math.atan(p_ex[1]))   # 正：左舷（+x）が上がる向き（平面が +x で高い＝右舷が…）→ 下で Unity の向きに直す
    lvl = p_ex[0]
    A, xc, yc, Ixx, Iyy = hull.waterplane(lvl)
    KB = B_ex[2]; KG = G[2]
    BMt, BMl = Ixx / V_ex, Iyy / V_ex
    GMt_formula, GMl_formula = KB + BMt - KG, KB + BMl - KG
    kt = righting_stiffness(vol_exact, Vt, G, p_ex, "heel")
    kl = righting_stiffness(vol_exact, Vt, G, p_ex, "trim")
    GMt_num, GMl_num = kt, kl  # 単位（てこ/角）
    # 船首・船尾の喫水（原点を通る縦の線の上で、y = ±4 単位）
    draft_fwd = (p_ex[0] + p_ex[2] * -4.0) * u[2]
    draft_aft = (p_ex[0] + p_ex[2] * 4.0) * u[2]

    # 曲線（水平の水面）
    curves = []
    for lv in np.arange(0.05, 0.71, 0.05):
        Vv, Bv = hull.immersed(lv, 0, 0)
        Aw, _, ycw, Ixw, Iyw = hull.waterplane(lv)
        curves.append({"level_units": round(float(lv), 3), "draft_m": round(float(lv * s), 4), "volume_m3": round(float(Vv * s ** 3), 4),
                       "displacement_kg": round(float(Vv * s ** 3 * rho), 1), "waterplane_m2": round(float(Aw * s * s), 4),
                       "kg_per_cm": round(float(Aw * s * s * rho * 0.01), 2), "lcb_m_aft": round(float(Bv[1] * s), 4), "kb_m": round(float(Bv[2] * s), 4),
                       "bmt_m": round(float(Ixw / Vv * s), 4), "bml_m": round(float(Iyw / Vv * s), 3)})

    # ---------------------------------------------------------------- 浮力点
    bp = prm["points"]
    ys_st = bp["stations_y_units"]
    edges = [-1e9] + [0.5 * (ys_st[i] + ys_st[i + 1]) for i in range(len(ys_st) - 1)] + [1e9]
    levels = np.arange(0.0, float(zt.max()) + bp["level_step_units"] * 0.5, bp["level_step_units"])
    pts = []
    for j, y0 in enumerate(ys_st):
        for side in (+1, -1):   # Blender の +x（左舷）、−x（右舷）
            m = (ys >= edges[j]) & (ys < edges[j + 1]) & (np.sign(xs) == side)
            # 点の横の位置：平衡の水線の半区画の r² / x̄（横傾斜の硬さを厳密値に合わせる）
            Aw, xcw, ycw, _, _ = hull.waterplane(lvl, m)
            ww = m & (zb < lvl) & (zt > lvl)
            r2 = (xs[ww] ** 2).mean()
            xp = side * r2 / abs(xcw)
            # 縦の位置：区画の水線面の中心（船首尾の方向）
            yp = ycw
            # 高さ：船底（その (xp, yp) の柱の底）
            k = np.argmin((xs - xp) ** 2 + (ys - yp) ** 2)
            zp = zb[k]
            V = []; C = []; Ar = []
            for lv in levels:
                Vv, Cc = hull.immersed(lv, 0, 0, m)
                Aw2 = hull.waterplane(lv, m)[0]
                if Vv <= 0:
                    Cc = np.array([xp, yp, zp])
                V.append(Vv); C.append(Cc); Ar.append(Aw2)
            pts.append({"station": j, "side": "port" if side > 0 else "starboard", "pos_units": [xp, yp, zp], "mask": m,
                        "V": np.array(V), "C": np.array(C), "A": np.array(Ar), "columns": int(m.sum())})

    def vol_points(a, bx, by):
        Vs = 0.0; Ms = np.zeros(3)
        for p in pts:
            x, y, _ = p["pos_units"]
            lv = a + bx * x + by * y
            Vk = np.interp(lv, levels, p["V"])
            if Vk <= 0:
                continue
            Ck = np.array([np.interp(lv, levels, p["C"][:, q]) for q in range(3)])
            Vs += Vk; Ms += Vk * Ck
        return Vs, (Ms / Vs if Vs > 0 else np.zeros(3))

    # 縦の位置の倍率 f：区画の中の縦の広がりの分だけ縦傾斜の硬さが小さくなるので、各点の縦の位置を水線面の中心の f 倍へ広げ、
    # 点の模型の縦の硬さを厳密値に合わせる（割線法。横は r²/x̄ で合わせ済み）
    for p in pts:
        p["ywp"] = p["pos_units"][1]

    def set_f(f):
        for p in pts:
            p["pos_units"][1] = p["ywp"] * f

    def kl_rel(f):
        set_f(f)
        pp, _ = solve_equilibrium(vol_points, Vt, G, p_ex[0])
        return righting_stiffness(vol_points, Vt, G, pp, "trim") / GMl_num - 1.0

    f0, f1 = 1.0, 1.04
    e0, e1 = kl_rel(f0), kl_rel(f1)
    for _ in range(8):
        if abs(e1) < 1e-4:
            break
        f0, f1, e0 = f1, f1 - e1 * (f1 - f0) / (e1 - e0), e1
        e1 = kl_rel(f1)
    y_factor = f1
    set_f(y_factor)
    p_pt, r_pt = solve_equilibrium(vol_points, Vt, G, p_ex[0])
    V_pt_exact, _ = vol_exact(*p_pt)   # 点の模型の平衡の姿勢での、厳密な排水容積
    u2 = up_dir(p_pt[1], p_pt[2])
    kt_pt = righting_stiffness(vol_points, Vt, G, p_pt, "heel")
    kl_pt = righting_stiffness(vol_points, Vt, G, p_pt, "trim")
    sumV_table = sum(float(np.interp(lvl, levels, p["V"])) for p in pts)

    # ---------------------------------------------------------------- 減衰（数値の条件）
    dmp = prm["damping"]
    Awp_m2 = A * s * s
    k_heave = rho * g * Awp_m2
    c_heave = 2 * dmp["heave_ratio"] * math.sqrt(k_heave * M)
    # 横揺れ・縦揺れの減衰比（点ごとの鉛直の減衰が作る分の見積もり）
    Ig = I  # Blender の軸（x 左舷、y 船尾、z 上）
    Aw_pts = np.array([float(np.interp(lvl, levels, p["A"])) for p in pts])
    xs_p = np.array([p["pos_units"][0] for p in pts]) * s
    ys_p = np.array([p["pos_units"][1] for p in pts]) * s
    c_i = c_heave * Aw_pts / Aw_pts.sum()
    K_roll = rho * g * V_ex * s ** 3 * GMt_num * s
    K_pitch = rho * g * V_ex * s ** 3 * GMl_num * s
    zeta_roll = (c_i * xs_p ** 2).sum() / (2 * math.sqrt(K_roll * Ig[1, 1]))
    zeta_pitch = (c_i * (ys_p - G[1] * s) ** 2).sum() / (2 * math.sqrt(K_pitch * Ig[0, 0]))
    T_heave = 2 * math.pi * math.sqrt(M / k_heave)
    T_roll = 2 * math.pi * math.sqrt(Ig[1, 1] / K_roll)
    T_pitch = 2 * math.pi * math.sqrt(Ig[0, 0] / K_pitch)

    # ---------------------------------------------------------------- Unity への写し（(x, y, z) → (−x, z, −y)、× s で m）
    def to_u(p3):
        p3 = np.asarray(p3, dtype=np.float64)
        return [float(-p3[0] * s), float(p3[2] * s), float(-p3[1] * s)]

    P = np.array([[-1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=np.float64)
    Iu = P @ I @ P.T
    w, R = np.linalg.eigh(Iu)
    if np.linalg.det(R) < 0:
        R[:, 0] *= -1

    def mat_to_quat(Rm):
        tr = Rm[0, 0] + Rm[1, 1] + Rm[2, 2]
        if tr > 0:
            S = math.sqrt(tr + 1.0) * 2; qw = 0.25 * S; qx = (Rm[2, 1] - Rm[1, 2]) / S; qy = (Rm[0, 2] - Rm[2, 0]) / S; qz = (Rm[1, 0] - Rm[0, 1]) / S
        elif Rm[0, 0] > Rm[1, 1] and Rm[0, 0] > Rm[2, 2]:
            S = math.sqrt(1.0 + Rm[0, 0] - Rm[1, 1] - Rm[2, 2]) * 2; qw = (Rm[2, 1] - Rm[1, 2]) / S; qx = 0.25 * S; qy = (Rm[0, 1] + Rm[1, 0]) / S; qz = (Rm[0, 2] + Rm[2, 0]) / S
        elif Rm[1, 1] > Rm[2, 2]:
            S = math.sqrt(1.0 + Rm[1, 1] - Rm[0, 0] - Rm[2, 2]) * 2; qw = (Rm[0, 2] - Rm[2, 0]) / S; qx = (Rm[0, 1] + Rm[1, 0]) / S; qy = 0.25 * S; qz = (Rm[1, 2] + Rm[2, 1]) / S
        else:
            S = math.sqrt(1.0 + Rm[2, 2] - Rm[0, 0] - Rm[1, 1]) * 2; qw = (Rm[1, 0] - Rm[0, 1]) / S; qx = (Rm[0, 2] + Rm[2, 0]) / S; qy = (Rm[1, 2] + Rm[2, 1]) / S; qz = 0.25 * S
        return [float(qx), float(qy), float(qz), float(qw)]

    lev_m = (levels * s).tolist()
    tabV, tabC, tabA, pos = [], [], [], []
    for p in pts:
        pos += to_u(p["pos_units"])
        tabV += (p["V"] * s ** 3).tolist()
        for cc in p["C"]:
            tabC += to_u(cc)
        tabA += (p["A"] * s * s).tolist()
    # Unity の向き：横傾斜は右舷（Unity +x）が下がる向きを正、縦傾斜は船首（Unity +z）が上がる向きを正
    # Blender の平面 z = a + bx·x + by·y：bx > 0 は左舷（+x_b）側で水面が高い＝左舷が沈む → 右舷下がりは負
    heel_u = -heel_deg
    trim_u = trim_deg  # by > 0 は船尾（+y_b）で水面が高い＝船尾が沈む＝船首が上がる → 正
    cfg = {
        "schema": "GreatWave.DS42.buoyancy_points/1",
        "noteJa": "設計42 の浮力点（Tools/GWWaveGen/ds42/ds42_hydro.py の出力）。座標は船の物理の根（縮尺 1、原点は船体中央の船底、+z 船首、+y 上、+x 右舷）の m。"
                  "各点は船体の区画（縦 5 × 左右）を受け持ち、その点での水面の高さ（根の局所の y）ごとの区画の排水容積 tabV（m³）・浮心 tabC（根の局所 m）・水線面積 tabA（m²）を持つ。",
        "rho": rho, "g": g, "scale": s, "massKg": M, "cgLocal": to_u(G),
        "inertiaDiag": [float(q) for q in w], "inertiaRot": mat_to_quat(R),
        "levelMin": float(lev_m[0]), "levelStep": float(bp["level_step_units"] * s), "levelCount": len(lev_m),
        "pointCount": len(pts), "pointPos": pos, "tabV": tabV, "tabC": tabC, "tabA": tabA,
        "dampHeaveNsPerM": c_heave, "areaRefM2": float(Aw_pts.sum() * s * s),
        "dragHorizontalPerS": dmp["horizontal_per_s"], "dragYawPerS": dmp["yaw_per_s"],
        "eqDraftMidM": float(draft_mid_units * s), "eqTrimDeg": float(trim_u), "eqHeelDeg": float(heel_u),
        "eqKeelHeightM": float(-p_ex[0] * s * u[2]),
        "periodsS": [T_heave, T_roll, T_pitch], "stiffness": [k_heave, K_roll, K_pitch],
        "inertiaWorldAxes": [float(Iu[0, 0]), float(Iu[1, 1]), float(Iu[2, 2])],
    }
    os.makedirs(os.path.dirname(ASSET), exist_ok=True)
    with open(ASSET, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cfg, f, ensure_ascii=False, separators=(",", ":"))

    # ---------------------------------------------------------------- 記録
    def r4(x):
        return round(float(x), 4)

    res = {
        "schema": "GreatWave.DS42.hydrostatics/1", "number": "設計42", "part": "buoyancy",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "inputs": {os.path.relpath(pth, REPO).replace("\\", "/"): sha(pth) for pth in (NPZ, REP41, BUILD41, RESEARCH41, PARAMS)},
        "scale_m_per_unit": s, "boat_key": prm["boat_key"], "rho_kg_m3": rho, "g_m_s2": g,
        "mass": {"total_kg": round(M, 1), "cg_blender_units": [r4(q) for q in G], "cg_unity_root_m": [r4(q) for q in to_u(G)],
                 "kg_m": r4(G[2] * s), "lcg_m_aft_of_mid": r4(G[1] * s),
                 "research41_estimate_kg": 2000.0, "research41_range_kg": [1600.0, 3100.0],
                 "research41_estimate_scaled_kg": round(2000.0 * (s * 10 / 11.667) ** 3, 1),
                 "parts": [{"name": p["name"], "mass_kg": round(p["mass_kg"], 1), "pos_unity_root_m": [r4(q) for q in to_u(p["pos_units"])],
                            "kind": p["kind"], "basis_ja": p["basis_ja"]} for p in parts],
                 "inertia_unity_root_kgm2": [[r4(q) for q in row] for row in Iu],
                 "radii_of_gyration_m": {"roll": r4(math.sqrt(Iu[2, 2] / M)), "pitch": r4(math.sqrt(Iu[0, 0] / M)), "yaw": r4(math.sqrt(Iu[1, 1] / M))}},
        "columns": {"step_units": step, "count": int(len(xs)), "single_hit_dropped": int(bad), "volume_units3": r4(Vfull), "closed_mesh_volume_units3": Vmesh,
                    "rel_diff": float((Vfull - Vmesh) / Vmesh)},
        "exact_equilibrium": {
            "method_ja": "柱の積分で ρ V s³ = m、浮心と重心が同じ鉛直線（Newton 法）。三角形を水面で切る方法（clip）で容積と浮心を別に確かめた",
            "residual": [float(q) for q in r_ex],
            "draft_mid_m": r4(draft_mid_units * s), "waterline_above_baseline_m_at_y_minus4_bow": r4(draft_fwd * s), "waterline_above_baseline_m_at_y_plus4_stern": r4(draft_aft * s),
            "trim_deg_bow_up_positive": r4(trim_u), "heel_deg_starboard_down_positive": r4(heel_u),
            "displaced_volume_m3": r4(V_ex * s ** 3), "buoyancy_N": round(rho * g * V_ex * s ** 3, 1), "weight_N": round(M * g, 1),
            "clip_volume_m3": r4(Vclip * s ** 3), "clip_vs_columns_rel": float((Vclip - V_ex) / V_ex),
            "cb_blender_units": [r4(q) for q in B_ex], "cb_clip_blender_units": [r4(q) for q in Bclip],
            "waterplane_m2": r4(A * s * s), "kg_per_cm_immersion": round(A * s * s * rho * 0.01, 2),
            "kb_m": r4(KB * s), "kg_m": r4(KG * s), "bmt_m": r4(BMt * s), "bml_m": r4(BMl * s),
            "gmt_m_formula": r4(GMt_formula * s), "gml_m_formula": r4(GMl_formula * s),
            "gmt_m_numeric_1deg": r4(GMt_num * s), "gml_m_numeric_1deg": r4(GMl_num * s),
            "freeboard_mid_m": r4((rep41["derived_units"]["depth_mid"] - draft_mid_units) * s),
            "placement_draft_m_seat_v1": 0.3806, "research41_draft_estimate_m": 0.2, "research41_draft_range_m": [0.16, 0.3],
        },
        "points": {
            "count": len(pts), "stations_y_units": ys_st, "level_step_units": bp["level_step_units"], "levels": len(levels),
            "layout_ja": "設計41 の提案の 5 断面（y = −3, −1.5, 0, 1.5, 3 単位）を区画の中心にし、区画の境は断面の中点。左右は中心線で分ける。"
                         "点の横の位置は平衡の水線の半区画の r²/x̄（横傾斜の硬さを厳密値に合わせる）、縦の位置は区画の水線面の中心、高さはその位置の船底",
            "list": [{"station": p["station"], "side": p["side"], "pos_unity_root_m": [r4(q) for q in to_u(p["pos_units"])], "columns": p["columns"],
                      "volume_at_eq_level_m3": r4(np.interp(lvl, levels, p["V"]) * s ** 3)} for p in pts],
            "sum_table_volume_at_eq_level_rel": float(sumV_table / hull.immersed(lvl, 0, 0)[0] - 1.0),
            "y_factor": float(y_factor),
            "y_factor_ja": "点の縦の位置＝区画の水線面の中心 × y_factor（縦傾斜の硬さを厳密値に合わせる倍率）",
            "point_model_equilibrium": {
                "residual": [float(q) for q in r_pt],
                "draft_mid_m": r4(p_pt[0] * u2[2] * s), "trim_deg_bow_up_positive": r4(math.degrees(math.atan(p_pt[2]))),
                "heel_deg_starboard_down_positive": r4(-math.degrees(math.atan(p_pt[1]))),
                "exact_volume_at_point_model_pose_m3": r4(V_pt_exact * s ** 3),
                "exact_buoyancy_over_weight": float(rho * V_pt_exact * s ** 3 / M),
                "draft_diff_vs_exact_mm": round(float((p_pt[0] * u2[2] - p_ex[0] * u[2]) * s * 1000), 2),
                "trim_diff_vs_exact_deg": round(float(math.degrees(math.atan(p_pt[2])) - trim_deg), 3),
                "gmt_m": r4(kt_pt * s), "gml_m": r4(kl_pt * s),
                "roll_stiffness_rel_vs_exact": float(kt_pt / GMt_num - 1.0), "pitch_stiffness_rel_vs_exact": float(kl_pt / GMl_num - 1.0),
            },
        },
        "damping_and_periods": {
            "kind": "数値の条件（抵抗の調整値。物理の実測ではない）",
            "heave_ratio": dmp["heave_ratio"], "c_heave_Ns_per_m": round(c_heave, 1),
            "zeta_roll_est": r4(zeta_roll), "zeta_pitch_est": r4(zeta_pitch),
            "horizontal_per_s": dmp["horizontal_per_s"], "yaw_per_s": dmp["yaw_per_s"],
            "k_heave_N_per_m": round(k_heave, 1), "k_roll_Nm_per_rad": round(K_roll, 1), "k_pitch_Nm_per_rad": round(K_pitch, 1),
            "T_heave_s": r4(T_heave), "T_roll_s": r4(T_roll), "T_pitch_s": r4(T_pitch),
            "note_ja": "周期は付加質量を入れない剛体の値（実際の船ではもっと長い）。減衰は点ごとの鉛直の速度に比例する力で、上下の減衰比 heave_ratio から決めた。横・縦揺れの減衰比はその結果の見積もり",
        },
        "curves_level_water": curves,
        "asset": {"path": os.path.relpath(ASSET, REPO).replace("\\", "/"), "sha256": sha(ASSET), "bytes": os.path.getsize(ASSET)},
        "seconds": round(time.time() - t0, 1),
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "ds42_hydrostatics.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    ee = res["exact_equilibrium"]; pm = res["points"]["point_model_equilibrium"]
    print("DS42_HYDRO mass=%.1fkg KG=%.3fm draft=%.4fm trim=%.3fdeg heel=%.3fdeg V=%.4fm3 clip_rel=%.2e GMt=%.3f/%.3f GMl=%.2f/%.2f" % (
        M, G[2] * s, ee["draft_mid_m"], ee["trim_deg_bow_up_positive"], ee["heel_deg_starboard_down_positive"], ee["displaced_volume_m3"],
        ee["clip_vs_columns_rel"], ee["gmt_m_formula"], ee["gmt_m_numeric_1deg"], ee["gml_m_formula"], ee["gml_m_numeric_1deg"]))
    print("DS42_POINTS draft_diff=%.2fmm trim_diff=%.3fdeg exactB/W=%.5f roll_k_rel=%.4f pitch_k_rel=%.4f sumV_rel=%.2e" % (
        pm["draft_diff_vs_exact_mm"], pm["trim_diff_vs_exact_deg"], pm["exact_buoyancy_over_weight"], pm["roll_stiffness_rel_vs_exact"],
        pm["pitch_stiffness_rel_vs_exact"], res["points"]["sum_table_volume_at_eq_level_rel"]))
    print("DS42_PERIODS T_heave=%.3f T_roll=%.3f T_pitch=%.3f zeta_roll=%.3f zeta_pitch=%.3f cols=%d vol_rel=%.2e seconds=%.1f" % (
        T_heave, T_roll, T_pitch, zeta_roll, zeta_pitch, len(xs), res["columns"]["rel_diff"], res["seconds"]))


if __name__ == "__main__":
    sys.exit(main())
