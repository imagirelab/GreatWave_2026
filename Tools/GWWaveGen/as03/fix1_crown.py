# -*- coding: utf-8 -*-
"""美術の見本03 修正の回 1（Q31）：波頭の冠に「泡の塊の皮」と「唇の縁から垂れる滴の列」を足す（B1 の冠の手・利用者の爪はそのまま）。

批評（critic）の必ず直す所の 1〜3・6 と、規則 T4 の「冠が原画視点のほかのどの視点でも枠の 0.5% より多く見える」に向けた部品。
- 泡の皮（kind 5）：B2 の彫りの面（hero_relief_b1v2c）の前の白の地（whiteSD > 0）と頂の線の少し後ろ（u > −1.05 m）の頂点を、面の法線の
  向きへ「丸い瘤の場」だけ持ち上げた皮。瘤は面の座標 (u 前へ, w 頂に並ぶ向き) に置き、頂の線の近くの大きな瘤（泡の綱）から前へ、少しずつ細る
  瘤を 3〜6 個つないだ「指の背」を互い違いに重ねる（make_lumps）。鎖の頭の 22% は頂の線の瘤（高さ 0.65〜1.40 m、背から見える泡の突起）。
  瘤はなめらかな最大でつなぎ、最も低い所も面から 0.05 m 上（面との z の争いを避ける）。白の境と背（u < −0.95 m）へ向かって皮は面の下へ
  沈む（u −0.95〜−0.40 m でなめらかに）。白の舌の上も皮が覆う（舌は盛り上がった釉の流れになる）。
  瘤の間隔：彫刻の正面の写真の読み（批評：丸い瘤 0.035〜0.05 H おき ≈ 0.75〜1.1 m）。
- 垂れる滴（kind 3）：白が唇の先を回り込む行の唇の先（列 200〜204）から、ほぼ真下へ垂れる丸い先の滴を 0.85 m ± 0.15 m おきに並べる。
  長さ 0.6〜1.45 m、幅（直径）0.30〜0.48 m（批評が彫刻の正面の写真から読んだ数）。面に入る滴は短くし、0.5 m 未満なら外す。
- IN（V3）：原画のカメラで写し、原画の空（2 px より内）に出て主役波に隠れない点のある滴は外し、皮はその頂点の印を面の上で約 1 m に
  ならしてなめらかに面の下へ沈める（崖を作らない。3 回まで繰り返して確かめる）。
  （B1 の IN の「原画の白の冠・爪の区域の外」の条件は皮には使わない：皮は主役波の白の地の上にあり、関門 G2 は輪郭だけを測るため。）
出力（Git 対象外）：Unity/Build/Polish/sample03/fix01/crown/<OUT|IN>/fix1_foam.{json,bin}・fix1_drips.{json,bin}（B2 の静止のメッシュの書式。
position・normal・uv5 =（ao, keyVis = 1, whiteSD = +10, 1）・uv3 =（f, 番号, 種類 3 滴・5 泡, 0））と fix1_parts_report.json・fix1_drips_layout.json。
原画の色は面へ写さない（Q28）。参照モデルの OBJ・写真は読まない。数は批評の写真の読み（critic_metrics・記録）と S1 の JSON。
使い方：py -3.10 -B Tools/GWWaveGen/as03/fix1_crown.py --mode OUT（または IN）
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crown_common as G  # noqa: E402
import crown_geom as GM  # noqa: E402

S3 = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03"
REL = S3 + "/surface/mesh/hero_relief_b1v2c.json"
OUTD = S3 + "/fix01/crown"
DOWN = np.array([0.0, -1.0, 0.0])


def load_static(jp):
    j = json.load(open(jp, encoding="utf-8"))
    n, m = j["vertices"], j["triangles"]
    raw = np.fromfile(os.path.join(os.path.dirname(jp), j["bin"]), np.uint8)
    off, ch = 0, {}
    for name, k in j["channels"]:
        ch[name] = np.frombuffer(raw, np.float32, n * k, off).reshape(n, k).astype(np.float64)
        off += n * k * 4
    tri = np.frombuffer(raw, np.uint32, m * 3, off).reshape(m, 3).astype(np.int64)
    return j, ch, tri


def vnormals(V, F):
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    N = np.zeros_like(V)
    for k in range(3):
        for d in range(3):
            N[:, d] += np.bincount(F[:, k], weights=fn[:, d], minlength=len(V))
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)


def write_static(out, name, V, N, uv5, uv3, F, note):
    os.makedirs(out, exist_ok=True)
    binp = os.path.join(out, name + ".bin")
    with open(binp, "wb") as f:
        for arr in (V, N, uv5, uv3):
            f.write(np.ascontiguousarray(arr, dtype="<f4").tobytes())
        f.write(np.ascontiguousarray(F, dtype="<u4").tobytes())
    js = {"schema": "GreatWave.AS03.static_mesh/1", "vertices": int(len(V)), "triangles": int(len(F)),
          "channels": [["position", 3], ["normal", 3], ["uv5", 4], ["uv3", 4]], "bin": name + ".bin", "sha256": G.sha(binp), "noteJa": note}
    G.jdump(os.path.join(out, name + ".json"), js)
    return js


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------ 泡の瘤の場
def make_lumps(rng, umin, umax, wmin, wmax, dw=0.92):
    """指の背の列（鎖）を短く区切って互い違いに重ねる：頂の線の近くの大きな瘤（泡の綱）から前（u +）へ、少しずつ細る瘤を
    0.55〜0.85 m おきに 3〜6 個つないだ「指」を作り、指が終わったら頂に並ぶ向きに 0.3〜0.5 間隔ずらして次の指を始める
    （長い鎖のままでは前の面が等間隔の縞（コール天）に読めた）。鎖の頭どうしは w に 0.92 m ± 0.22 m おき
    （彫刻の写真の丸い瘤 0.75〜1.1 m）。指の間に小さな丸い泡を 15% 散らす。
    戻り値：(u, w, 高さ, 半長 a_u, 半幅 a_w, 角) の表と、頂の線の鎖の頭（w は滴の置き場所にも使う）の表。"""
    L, heads = [], []
    w = wmin + rng.uniform(0, dw)
    while w < wmax:
        u = rng.uniform(-0.30, 0.45)
        wc = w
        hl = rng.uniform(0.45, 0.80)
        aw = rng.uniform(0.44, 0.64)
        au0 = rng.uniform(0.48, 0.78)
        knob = rng.random() < 0.22
        if knob:
            # 頂の線の瘤（背から見える泡の突起）：彫刻の背の写真で頂の輪郭から出る太く短い指（見える高さの 0.045〜0.077、約 10 本。批評）。
            # 高さ 0.65〜1.40 m・径 0.72〜1.2 m の丸い瘤（指としては数えない。泡の皮の一部）。32% では背の輪郭に等間隔の突起の列（背びれ）に読めたので 22%
            u = rng.uniform(-0.05, 0.35)
            hl = rng.uniform(0.65, 1.40)
            aw = rng.uniform(0.36, 0.60)
            au0 = rng.uniform(0.36, 0.58)
        heads.append((u, wc, float(knob), hl))
        k, kseg, nseg = 0, 0, int(rng.integers(3, 7))
        while u < umax:
            au = au0 if k == 0 else rng.uniform(0.45, 0.85)
            th = math.radians(rng.normal(0.0, 14.0))
            L.append((u, wc, hl, au, aw, th))
            if rng.random() < 0.15:
                L.append((u + rng.uniform(0.2, 0.5), wc + rng.choice([-1, 1]) * rng.uniform(0.40, 0.55), rng.uniform(0.10, 0.20),
                          rng.uniform(0.22, 0.36), rng.uniform(0.22, 0.34), 0.0))
            u += rng.uniform(0.55, 0.85)
            wc += rng.normal(0.0, 0.10)
            kseg += 1
            if k == 0:
                hl = rng.uniform(0.24, 0.42)
                aw = rng.uniform(0.34, 0.52)
            elif kseg >= nseg:
                # 指の終わり：先を丸く小さくし、少し間を空けて、横へずらした次の指を始める
                u += rng.uniform(0.05, 0.35)
                wc += rng.choice([-1, 1]) * rng.uniform(0.30, 0.50) * dw
                hl = rng.uniform(0.20, 0.40)
                aw = rng.uniform(0.32, 0.52)
                kseg, nseg = 0, int(rng.integers(3, 7))
            else:
                hl = max(0.12, hl * rng.uniform(0.86, 1.02))
                aw = max(0.26, aw * rng.uniform(0.90, 1.02))
            k += 1
        w += float(np.clip(rng.normal(dw, 0.22), 0.6, 1.3))
    return np.array(L, np.float64), np.array(heads, np.float64)


def lump_field(uw, lumps, beta=26.0, rmax=1.25):
    tree = cKDTree(lumps[:, :2])
    lists = tree.query_ball_point(uw, rmax)
    hs = np.zeros(len(uw))
    hmax_near = np.zeros(len(uw))
    for i, idx in enumerate(lists):
        if not idx:
            continue
        Lm = lumps[idx]
        d = uw[i][None, :] - Lm[:, :2]
        c, s = np.cos(Lm[:, 5]), np.sin(Lm[:, 5])
        du_ = c * d[:, 0] + s * d[:, 1]
        dw_ = -s * d[:, 0] + c * d[:, 1]
        rho2 = (du_ / Lm[:, 3]) ** 2 + (dw_ / Lm[:, 4]) ** 2
        cap = Lm[:, 2] * np.clip(1.0 - rho2, 0.0, None) ** 0.65
        hs[i] = np.log(np.exp(beta * cap).sum() + 1.0) / beta
        hmax_near[i] = Lm[:, 2].max()
    return hs, hmax_near


def build_foam(mode, seed, pm=None, cam=None):
    j, ch, tri = load_static(REL)
    P, N0 = ch["position"], ch["normal"]
    u, w = ch["uv3"][:, 2], ch["uv3"][:, 3]
    wsd = ch["uv5"][:, 2]
    hrow = ch["uv4"][:, 1]
    rr, cc = ch["uv6"][:, 0], ch["uv6"][:, 1]
    # 皮の候補：前の白（舌を含む）と頂の線の少し後ろまで。行の頂が低い所（尾・裾 hrow < 0.18）と面の裾（列 < 40・> 330）は除く
    cand = (wsd > -0.30) & (u > -1.05) & (hrow > 0.18) & (cc > 40) & (cc < 330)
    rng = np.random.default_rng(seed)
    uw = np.stack([u, w], 1)
    lumps, heads = make_lumps(rng, -0.35, float(u[cand & (wsd > 0)].max()) + 0.5, float(w[cand].min()) - 0.5, float(w[cand].max()) + 0.5)
    hl = np.zeros(len(P))
    hmx = np.zeros(len(P))
    ci = np.nonzero(cand)[0]
    a, b = lump_field(uw[ci], lumps)
    hl[ci], hmx[ci] = a, b
    b0 = 0.05
    fw = smoothstep(-0.01, 0.22, wsd)
    fb = smoothstep(-0.95, -0.40, u)
    fr = smoothstep(0.18, 0.30, hrow)
    f = fw * fb * fr * cand
    h = f * (b0 + hl) - (1.0 - f) * 0.08
    in_stats = None
    if mode == "IN":
        # 原画の空（2 px より内）に出て、主役波に隠れない皮の頂点を、なめらかに面の下へ沈める（崖を作らない）。
        # 外れた頂点の印を面の隣り合う頂点へ 10 回ならして（約 1 m）、印の強さで持ち上げを 0 → 面の下 0.08 m へ移す。2 回繰り返して確かめる。
        import scipy.sparse as sps
        e = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
        Adj = sps.coo_matrix((np.ones(2 * len(e)), (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])), shape=(len(P), len(P))).tocsr()
        deg = np.asarray(Adj.sum(1)).ravel()
        Dn = sps.diags(1.0 / np.maximum(deg, 1))
        An = Dn @ Adj
        h0 = h.copy()
        sink = np.zeros(len(P))
        hist = []
        for it in range(4):
            Vt = P + N0 * h[:, None]
            q, z = cam.project(Vt[ci])
            x = np.rint(q[:, 0]).astype(int)
            y = np.rint(q[:, 1]).astype(int)
            ok = (x >= 0) & (x < 1920) & (y >= 0) & (y < 1080) & (z > 0.1)
            bad = np.zeros(len(ci), bool)
            xi, yi, zi = x[ok], y[ok], z[ok]
            hz = pm["zb"][yi, xi]
            hidden = (hz > 0) & (1.0 / np.maximum(hz, 1e-9) < zi - 0.05)
            bad[np.nonzero(ok)[0]] = pm["sky_in"][yi, xi] & ~hidden & (h[ci][ok] > 0)
            badv = np.zeros(len(P))
            badv[ci[bad]] = 1.0
            hist.append(int(bad.sum()))
            if it == 3 or bad.sum() == 0:
                break
            m = np.maximum(sink, badv)
            for _ in range(10):
                m = np.maximum(0.5 * m + 0.5 * (An @ m), badv)
            sink = np.maximum(sink, smoothstep(0.0, 0.45, m))
            h = h0 * (1.0 - sink) - 0.08 * sink
        in_stats = dict(skin_vertices_in_painting_sky_by_pass=hist, sunk_vertices_gt_0p5=int((sink > 0.5).sum()))
    # 皮の三角形：どれかの頂点が面より上（−0.02 m より上）にあるもの
    keep_t = (h[tri] > -0.02).any(1) & cand[tri].all(1)
    T = tri[keep_t]
    used = np.unique(T.ravel())
    remap = -np.ones(len(P), np.int64)
    remap[used] = np.arange(len(used))
    F = remap[T]
    V = P[used] + N0[used] * h[used][:, None]
    Nn = vnormals(V, F)
    flip = (Nn * N0[used]).sum(1) < 0
    if flip.mean() > 0.5:
        F = F[:, [0, 2, 1]]
        Nn = -Nn
    # 瘤の間の溝の AO（瘤の高さ ÷ 近い瘤の高さ）と、面へ沈む縁の AO
    rel = np.clip(hl[used] / np.maximum(hmx[used], 1e-3), 0, 1)
    ao = np.clip(0.52 + 0.48 * smoothstep(0.0, 0.75, rel), 0.45, 1.0) * (0.75 + 0.25 * f[used])
    ao = np.minimum(ao, 1.0)
    uv5 = np.stack([ao, np.ones(len(V)), np.full(len(V), 10.0), np.ones(len(V))], 1)
    uv3 = np.stack([np.ones(len(V)), np.full(len(V), 5000.0), np.full(len(V), 5.0), np.zeros(len(V))], 1)
    # 測り
    A = 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)
    hv = h[used]
    vis_area = float(A[(hv[F] > 0.0).all(1)].sum())
    uu = u[used]
    back_tri = (hv[F] > 0.0).all(1) & (uu[F].mean(1) < -0.3)
    back_rec = dict(area_above_surface_u_lt_minus0p3_m2=round(float(A[back_tri].sum()), 2),
                    u_min_above_surface_m=round(float(uu[hv > 0.0].min()), 3) if (hv > 0).any() else None,
                    note_ja="背（頂の線より後ろ）へ出る皮：頂の線の瘤の後ろ半分と、u −0.95〜−0.40 m の沈み込みの帯。背の形（一つの山）は変えていない（彫りの面は変えていない）")
    hw = np.sort(heads[:, 1])
    kn = heads[heads[:, 2] > 0.5]
    stats = dict(lumps=int(len(lumps)), chains=int(len(heads)), chain_spacing_w_m=G.pct(np.diff(hw)), lumps_crest_u_lt_1p3=int((lumps[:, 0] < 1.3).sum()),
                 crest_knobs=int(len(kn)), crest_knob_height_m=G.pct(kn[:, 3]) if len(kn) else None,
                 crest_knob_spacing_w_m=G.pct(np.diff(np.sort(kn[:, 1]))) if len(kn) > 2 else None,
                 lump_height_m=G.pct(lumps[:, 2]), lump_len_along_u_m=G.pct(2 * lumps[:, 3]), lump_width_m=G.pct(2 * lumps[:, 4]),
                 skin_offset_above_surface_m=G.pct(hv[hv > 0]) if (hv > 0).any() else None,
                 skin_area_above_surface_m2=round(vis_area, 1), skin_behind_crest=back_rec, vertices=int(len(V)), triangles=int(len(F)), in_constraint=in_stats)
    return V, Nn, uv5, uv3, F, stats, heads


# ------------------------------------------------------------ 唇の縁から垂れる滴
def lip_line(seed):
    j, ch, tri = load_static(REL)
    P, N0 = ch["position"], ch["normal"]
    wsd = ch["uv5"][:, 2]
    rr, cc = ch["uv6"][:, 0], ch["uv6"][:, 1]
    hrow = ch["uv4"][:, 1]
    ww = ch["uv3"][:, 3]
    rows = np.unique(rr)
    pts = []
    for r in rows:
        sel = (rr == r)
        # 唇の先（列 200）が白で（白が唇の先を回り込む行）、行の頂が高い所（hrow ≥ 0.30）
        k200 = np.nonzero(sel & (np.abs(cc - 200) < 1e-3))[0]
        if len(k200) == 0:
            continue
        k = k200[0]
        if wsd[k] <= 0.05 or hrow[k] < 0.30:
            continue
        # 唇の下の面（列 200〜206）で最も低い点を根元にする
        cand = np.nonzero(sel & (cc >= 199.5) & (cc <= 206.5))[0]
        kk = cand[np.argmin(P[cand, 1])]
        pts.append((r, P[kk], N0[kk], float(cc[kk]), float(wsd[k]), float(ww[k])))
    return pts


def drip_shape(rng, root, n0, d, L, r0, sheet):
    """根元（面の下 0.55 r）から面の法線の向きに少し出て下へ。太さは根元 0.78 r0 → 先の丸いふくらみ（滴の重さ）。面に入るなら縮める。"""
    for shrink in (1.0, 0.85, 0.7, 0.55):
        Ls = L * shrink
        if Ls < 0.32:
            break
        npt = max(8, int(Ls / 0.05) + 1)
        tt = np.linspace(0, 1, npt)
        bend = GM.nrm(n0 * 0.6 + d * 0.4)
        sway = GM.nrm(np.cross(d, GM.UP) + 1e-9) * rng.normal(0, 0.05)
        Pm = np.stack([root + bend * (0.35 * r0) * min(ti / 0.2, 1.0) + d * (Ls * ti) + sway * Ls * ti * ti for ti in tt])
        rad = r0 * (0.78 + 0.10 * tt + 0.26 * np.exp(-((tt - 0.86) / 0.13) ** 2))
        hgt, _ = sheet.height(Pm[tt > 0.25])
        if (hgt > rad[tt > 0.25] * 0.9).all():
            return Pm, rad, Ls
    return None, None, None


def build_drips(mode, seed, h, sheet, heads, pm=None, cam=None):
    """滴は泡の指の背の列（鎖）の先に置く（指が唇を越えて垂れる）。鎖の w に最も近い唇の線の点が根元。鎖の間にも 35% の割合で小さな滴を足す。
    長さ 0.85 m × e^N(0, 0.38)（0.35〜1.5 m）、根元の半径 N(0.19, 0.035) m（0.13〜0.26）、15% は 2 本が寄り添う滴。"""
    rng = np.random.default_rng(seed + 77)
    pts = lip_line(seed)
    rows = np.array([p[0] for p in pts])
    Pl = np.stack([p[1] for p in pts])
    Nl = np.stack([p[2] for p in pts])
    Wl = np.array([p[5] for p in pts])
    steps = np.linalg.norm(np.diff(Pl, axis=0), axis=1)
    line_len = float(steps[steps < 1.5].sum())
    travel = GM.nrm(h.t)
    # 根元の w：鎖の頭の w（唇の線の w の範囲の中）＋ 鎖の間の小さな滴
    hw = np.sort(heads[:, 1])
    targets = []
    for k, wv in enumerate(hw):
        targets.append((float(wv), 1.0))
        if k + 1 < len(hw) and rng.random() < 0.35:
            targets.append((float(0.5 * (wv + hw[k + 1]) + rng.normal(0, 0.08)), 0.6))
    order = np.argsort(Wl)
    Ws, idx_s = Wl[order], order
    drips, dropped = [], []
    did = 6000
    for wv, sc in targets:
        if wv < Ws[0] - 0.3 or wv > Ws[-1] + 0.3:
            continue
        j = int(np.clip(np.searchsorted(Ws, wv), 1, len(Ws) - 1))
        i0, i1 = idx_s[j - 1], idx_s[j]
        if np.linalg.norm(Pl[i1] - Pl[i0]) > 1.5:
            continue
        t = float(np.clip((wv - Ws[j - 1]) / max(Ws[j] - Ws[j - 1], 1e-9), 0, 1))
        P0 = Pl[i0] * (1 - t) + Pl[i1] * t
        n0 = GM.nrm(Nl[i0] * (1 - t) + Nl[i1] * t)
        tl = GM.nrm(Pl[i1] - Pl[i0])
        group = [(0.0, 1.0)]
        if rng.random() < 0.15:
            group.append((rng.choice([-1, 1]) * rng.uniform(0.24, 0.32), rng.uniform(0.5, 0.8)))
        for (ds, ls) in group:
            Ld = float(np.clip(0.85 * sc * ls * math.exp(rng.normal(0, 0.38)), 0.35, 1.5))
            r0 = float(np.clip(rng.normal(0.19, 0.035) * (0.85 if sc < 1 else 1.0), 0.13, 0.26))
            jit = rng.normal(0, 0.09, 3)
            nh = GM.nrm(n0 - (n0 @ GM.UP) * GM.UP + 1e-9)
            Pq = P0 + tl * ds
            root = Pq - n0 * (0.55 * r0)
            Pm = None
            # 真下に近い向きから、面に当たる時は前（進む向き）・面の外へ倒した向きを試す（唇の下が近い行）
            for kt, kn in ((0.22, 0.10), (0.45, 0.25), (0.70, 0.45)):
                d = GM.nrm(DOWN + kt * travel + kn * nh + jit)
                Pm, rad, L = drip_shape(rng, root, n0, d, Ld, r0, sheet)
                if Pm is not None:
                    break
            if Pm is None:
                dropped.append(dict(id=did, why_ja="面に入る（0.55 倍に縮めても）"))
                did += 1
                continue
            if mode == "IN":
                probe = surface_probe_one(Pm, rad)
                q, z = cam.project(probe)
                x = np.rint(q[:, 0]).astype(int)
                y = np.rint(q[:, 1]).astype(int)
                okp = (x >= 0) & (x < 1920) & (y >= 0) & (y < 1080) & (z > 0.1)
                xi, yi, zi = x[okp], y[okp], z[okp]
                hz = pm["zb"][yi, xi]
                hidden = (hz > 0) & (1.0 / np.maximum(hz, 1e-9) < zi - 0.05)
                badn = int((pm["sky_in"][yi, xi] & ~hidden).sum())
                if badn > 0:
                    dropped.append(dict(id=did, why_ja="IN：原画の視点で原画の空に出る", bad_points=badn))
                    did += 1
                    continue
            drips.append(dict(id=did, P=Pm, rad=rad, root=Pq, L=float(L), r0=r0, row=float(rows[i0]), w=float(wv)))
            did += 1
    # メッシュ
    Vs, Fs, U5, U3 = [], [], [], []
    off = 0
    for k, dr in enumerate(drips):
        V, F, fv, _rid = GM.tube(dr["P"], dr["rad"], 14, tip="round")
        F = GM.orient_outward(V, F, dr["P"])
        Vs.append(V)
        Fs.append(F + off)
        ao = np.clip(0.70 + 0.30 * smoothstep(0.0, 0.35, fv), 0, 1)
        U5.append(np.stack([ao, np.ones(len(V)), np.full(len(V), 10.0), np.ones(len(V))], 1))
        U3.append(np.stack([fv, np.full(len(V), float(dr["id"])), np.full(len(V), 3.0), np.zeros(len(V))], 1))
        off += len(V)
    V = np.concatenate(Vs)
    F = np.concatenate(Fs)
    Nn = GM.vertex_normals(V, F)
    dw = sorted(d["w"] for d in drips)
    sp = [b - a for a, b in zip(dw[:-1], dw[1:]) if b - a < 2.0]
    stats = dict(drips=len(drips), dropped=len(dropped), lip_line_length_m=round(line_len, 2), drips_per_m=round(len(drips) / max(line_len, 1e-6), 3),
                 spacing_along_w_m=G.pct(sp) if sp else None, length_m=G.pct([d["L"] for d in drips]), width_max_m=G.pct([2 * float(d["rad"].max()) for d in drips]),
                 width_root_m=G.pct([2 * float(d["rad"][0]) for d in drips]), vertices=int(len(V)), triangles=int(len(F)))
    lay = [dict(id=d["id"], row=round(d["row"], 2), w_m=round(d["w"], 3), root=[round(float(v), 3) for v in d["root"]], tip=[round(float(v), 3) for v in d["P"][-1]],
                length_m=round(d["L"], 3), width_max_m=round(2 * float(d["rad"].max()), 3), width_root_m=round(2 * float(d["rad"][0]), 3)) for d in drips]
    return V, Nn, np.concatenate(U5), np.concatenate(U3), F, stats, lay, dropped


def surface_probe_one(P, rad):
    T = GM.nrm(np.gradient(P, axis=0))
    a = GM.nrm(np.cross(T, GM.UP + 1e-3))
    b = np.cross(T, a)
    r = rad[:, None]
    return np.concatenate([P, P + a * r, P - a * r, P + b * r, P - b * r, P[-1:] + T[-1:] * r[-1:]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["OUT", "IN"], required=True)
    ap.add_argument("--seed", type=int, default=3131)
    a = ap.parse_args()
    t0 = time.time()
    h = G.HeroData()
    sheet = GM.Sheet(h.X, h.N, rows=(40, 239), cols=(18, 394), sub=2)
    pm = cam = None
    if a.mode == "IN":
        import crown_build as CB
        C = CB.Crown("IN", 3101)
        pm = C.painting_masks()
        cam = pm["cam"]
    print("init", round(time.time() - t0, 1), flush=True)
    out = os.path.join(OUTD, a.mode)
    V, N, u5, u3, F, fst, heads = build_foam(a.mode, a.seed, pm, cam)
    js_f = write_static(out, "fix1_foam", V, N, u5, u3, F,
                        "修正の回 1 の泡の皮（kind 5）。B2 の彫りの面の前の白の地を丸い瘤の場だけ法線の向きへ持ち上げた皮。uv5 = (ao, 1, +10, 1)、uv3 = (1, 5000, 5, 0)。")
    print("foam", fst["vertices"], fst["triangles"], round(time.time() - t0, 1), flush=True)
    V2, N2, u52, u32, F2, dst, dlay, ddrop = build_drips(a.mode, a.seed, h, sheet, heads, pm, cam)
    js_d = write_static(out, "fix1_drips", V2, N2, u52, u32, F2,
                        "修正の回 1 の唇の縁から垂れる滴（kind 3）。uv5 = (ao, 1, +10, 1)、uv3 = (f 根元 0 → 先 1, 滴の番号, 3, 0)。")
    print("drips", dst, round(time.time() - t0, 1), flush=True)
    G.jdump(os.path.join(out, "fix1_drips_layout.json"), dict(schema="GreatWave.AS03.fix1_drips/1", mode=a.mode, drips=dlay, dropped=ddrop))
    rep = dict(schema="GreatWave.AS03.fix1_parts/1", mode=a.mode, seed=a.seed, date=time.strftime("%Y-%m-%d %H:%M"), method_ja=__doc__.strip(),
               foam=dict(mesh=js_f, measure=fst), drips=dict(mesh=js_d, measure=dst),
               targets_ja=dict(lump_spacing_m="0.75〜1.1（批評：彫刻の正面の写真の丸い瘤 0.035〜0.05 H、H ≈ 21.6 m）",
                               drip_spacing_m="約 0.8（0.037 H、写真の読み ±25%：0.6〜1.0）", drip_length_m="0.6〜1.45（0.03〜0.07 H）",
                               drip_width_m="0.30〜0.48（0.015〜0.023 H）"),
               inputs=dict(relief=REL, relief_sha256=G.sha(os.path.join(os.path.dirname(REL), "hero_relief_b1v2c.bin")), hero_gwb_sha256=G.sha(G.GWB)),
               elapsed_s=round(time.time() - t0, 1))
    G.jdump(os.path.join(out, "fix1_parts_report.json"), rep)
    print("FIX1_CROWN_DONE", a.mode, round(time.time() - t0, 1))


if __name__ == "__main__":
    main()
