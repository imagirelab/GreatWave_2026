# -*- coding: utf-8 -*-
"""仕上げ31 飛沫の部：設計31 の飛沫 v0（186 粒、F_final・K*′ R4・29修正01 の色面）を、仕上げ28 の採用（K*′ P28R2rec・G_p28rec）、
仕上げ29 の材質の白（白の範囲 ∧ T_white。pl31_white.py の T_white）、仕上げ30 の海で作り直し、数を 2〜3 千個へ増やす。

計画 §5.3 仕上げ31 の行に対応する所：
  1. 白の出現・発生の表・放出点を G_p28rec で作り直す（pl31_white.py の T_white と白の範囲）。
  2. 放出点を、終態が白の頂点に限る：放出点の候補は材質 PL29 の白の範囲（t* で白）の頂点で、放出の時刻 τ_e に T_white ≤ τ_e（もう白い）。
  3. 原画の白い点の取り出しを目で照合した記録（pl31_dots_eye.json）で、区域の外の点（右上の空・船の近く）を加える。
     t* に主役波の前に来る点（原画では爪の間の空）は、今の主役波の色がその画素で白なら残し（白の上の白で見えない）、白でなければ除く。
  4. 数・大小・分布：原画の点に合う粒（親）のほかに、親の放出点の近くの白い頂点から、親の速度のまわりに散らした子の粒を出し、2〜3 千個にする。
     子は原画視点の t* で「主役波・海・船の陰に隠れる」「今の白（Unity の色区 ID の白）の上に重なる」「原画の点の円の中」「画面の外」の
     どれかの所にだけ置く（原画視点の t* に原画にない白い点を足さない。設計39 の ③ の限界 7 の直し）。ほかの視点と形成の途中では見える。
  5. 151：粒の色は限定色の 2 段（白・生成りと、暗い帯の点の灰の白）。どちらにするかは粒の t* の世界の高さ（3 次元の量）で決める（原画の投影は使わない）。
  6. V3 の寿命：親ごとに、150 を通る候補のうち τ_e が今の 1.6 倍まで早いものがあるかを数える（設計35 の V3 の限界の測り）。
  7. F8（固定配置と短い落下）の版を、見え方の比べのために別のパッケージで書く。
出力（Git 対象外）：Unity/Build/Polish/31/spray/
"""
import argparse
import json
import math
import os
import sys
import time

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds31")
import ds31_spray as D  # noqa: E402

K, S, C27 = D.K, D.S, D.C27
sha, jdump, hash01 = D.sha, D.jdump, D.hash01
G = D.G

HERO_PKG = REPO + "/Unity/Build/Polish/31/white/hero_pkg"
SEA_DIR = REPO + "/Unity/Build/Polish/30/sea"
WARP = REPO + "/Unity/Build/Polish/28/G_p28rec/timewarp_G_p28rec.json"
KMETA = REPO + "/Unity/Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45_meta.json"
ATTR = REPO + "/Unity/Build/Polish/29/fix01/attr/pl29_hero_attr_f32.bin"
WHITE_DIR = REPO + "/Unity/Build/Polish/31/white"
IDS_TSTAR = REPO + "/Unity/Build/Polish/30/fix02/r_final/full/ids_noline.png"
# 仕上げ31 の後の状態の t* の原画視点（飛沫なし・爪と線あり）。子の「白の上」は、この描画で白（線・爪の縁の線の上でない）に見える所だけにする
RENDER_NOSPRAY = REPO + "/Unity/Build/Polish/31/r_after/full/painting_t120_nospray.png"
HERO_WHITE8 = (248, 243, 223)
EYE = HERE + "/pl31_dots_eye.json"
OUT = REPO + "/Unity/Build/Polish/31/spray"

P = dict(
    emit_rows=[11, 236], emit_cols=[90, 292], emit_row_step=2, emit_col_step=3, emit_F=[1.0, 2.8],
    tau_e=[-2.8, -0.08], tau_e_step=0.04, vel_h=0.005,
    max_angle_deg=45.0, speed_ratio=[0.5, 2.0], score_ratio_w=20.0, top_k=16,
    child_target_total=2500, child_per_parent_try=600, child_dr=10, child_dc=10, child_tau_jitter=[-0.5, 0.25], child_emit_F=[0.6, 2.8],
    child_speed=[0.6, 1.15], child_angle_deg=25.0, child_radius=[0.3, 0.75], child_radius_min=0.02,
    hide_margin_px=1.0, occl_margin_m=0.3, child_occl_margin_m=0.6, white_tol_rgb=24,
    tone_split_y_m=None,
    v3_factor=1.6,
    # 修正01：放出点は房の Hash1 によらない白の範囲（pl31_zone.zone_robust > robust_margin）に限る
    robust_margin=0.01,
    # 修正01：子は原画視点 t* で「原画の点の中（点の射線のまわり、点の円の中、奥行き ±dot_depth_m）」「今の白の上（白の面の手前 over_white_front_m）」
    # 「画面の外」のどれかに、狙いの位置を先に決めてから逆弾道で放出点を探す（主役波の陰に隠れる所＝管の中には置かない）
    child_per_dot=5, dot_child_max=2, dot_depth_m=0.35, dot_child_rpx_frac=0.8, child_radius_scale=[0.85, 1.15], over_white_margin_px=2.5,
    over_white_tries=10500, over_white_front_m=[0.3, 2.0], over_white_pick_top=8, over_white_box=[700, 150, 1300, 620],
    child_gap_min_m=0.10,
    offscreen_max=300,
)


def ciede2000(lab1, lab2):
    L1, a1, b1 = lab1[..., 0], lab1[..., 1], lab1[..., 2]
    L2, a2, b2 = lab2[..., 0], lab2[..., 1], lab2[..., 2]
    C1 = np.hypot(a1, b1); C2 = np.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    Gf = 0.5 * (1 - np.sqrt(Cb ** 7 / (Cb ** 7 + 25 ** 7)))
    a1p = (1 + Gf) * a1; a2p = (1 + Gf) * a2
    C1p = np.hypot(a1p, b1); C2p = np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360; h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp = L2 - L1; dCp = C2p - C1p
    dhp = h2p - h1p
    dhp = np.where(np.abs(dhp) > 180, dhp - 360 * np.sign(dhp), dhp)
    dhp = np.where(C1p * C2p == 0, 0, dhp)
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dhp / 2))
    Lbp = (L1 + L2) / 2; Cbp = (C1p + C2p) / 2
    hbp = np.where(np.abs(h1p - h2p) > 180, (h1p + h2p + 360) / 2, (h1p + h2p) / 2)
    hbp = np.where(C1p * C2p == 0, h1p + h2p, hbp)
    T = 1 - 0.17 * np.cos(np.radians(hbp - 30)) + 0.24 * np.cos(np.radians(2 * hbp)) + 0.32 * np.cos(np.radians(3 * hbp + 6)) - 0.20 * np.cos(np.radians(4 * hbp - 63))
    dth = 30 * np.exp(-((hbp - 275) / 25) ** 2)
    Rc = 2 * np.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / np.sqrt(20 + (Lbp - 50) ** 2)
    Sc = 1 + 0.045 * Cbp; Sh = 1 + 0.015 * Cbp * T
    Rt = -np.sin(np.radians(2 * dth)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def lab_to_srgb8(lab):
    L, a, b = lab
    fy = (L + 16) / 116; fx = fy + a / 500; fz = fy - b / 200
    def finv(t):
        return t ** 3 if t ** 3 > 0.008856 else (t - 16 / 116) / 7.787
    Xn, Yn, Zn = 0.95047, 1.0, 1.08883
    X, Y, Z = Xn * finv(fx), Yn * finv(fy), Zn * finv(fz)
    r = 3.2406 * X - 1.5372 * Y - 0.4986 * Z
    g = -0.9689 * X + 1.8758 * Y + 0.0415 * Z
    bb = 0.0557 * X - 0.2040 * Y + 1.0570 * Z
    def gam(u):
        u = max(0.0, min(1.0, u))
        return 12.92 * u if u <= 0.0031308 else 1.055 * u ** (1 / 2.4) - 0.055
    return [int(round(255 * gam(v))) for v in (r, g, bb)]


def srgb8_to_lab(c):
    v = np.array(c, np.float32).reshape(1, 1, 3)[:, :, ::-1] / 255.0
    return cv2.cvtColor(v, cv2.COLOR_BGR2LAB)[0, 0].astype(np.float64)


def rot_jitter(v, ang_deg, rng):
    """v を、ランダムな軸のまわりに 0〜ang_deg 回す（角度の分布は一様）。"""
    n = np.linalg.norm(v)
    u = v / max(n, 1e-9)
    a = rng.normal(size=3); a -= a @ u * u
    a /= max(np.linalg.norm(a), 1e-9)
    th = math.radians(ang_deg) * math.sqrt(rng.random())
    return n * (math.cos(th) * u + math.sin(th) * a)


def check_paths_full(paths, hero, near, far, tau_lo, jb=18, je=394, parity_hz=30.0):
    """150 の検査（仕上げ31 修正01）：設計31 の check_paths（主役波＋近い海の行 0〜30、偶奇は頂点から 1 m 以内だけ）を、
    主役波の本体の列・近い海の全部の行・遠い海の全部の行に広げ、偶奇（真上への半直線の交差の数）を parity_hz ごとに全部の点で調べる
    （240 Hz の各コマでは頂点から 1 m 以内の点だけ。水の中の深い点は頂点から遠いので、1 m の門だけでは見落とした）。
    戻り値は check_paths と同じ形。"""
    from scipy.spatial import cKDTree
    PP = D.P
    n = len(paths)
    pe = np.array([q["p_e"] for q in paths]); v0 = np.array([q["v0"] for q in paths])
    te = np.array([q["tau_e"] for q in paths]); rad = np.array([q["radius"] for q in paths])
    taus = np.arange(tau_lo, 0.0 + 1e-9, 1.0 / PP["check_hz"])
    if taus[-1] < 0.0:
        taus = np.append(taus, 0.0)
    every = max(int(round(PP["check_hz"] / parity_hz)), 1)
    Cb = je - jb + 1
    Th = K.grid_tris(hero.R, Cb)
    Tn = K.grid_tris(near.R, near.C) + hero.R * Cb
    Tf = K.grid_tris(far.R, far.C) + hero.R * Cb + near.R * near.C
    Tall = np.concatenate([Th, Tn, Tf])
    res = dict(min_dist=np.full(n, np.inf), min_sd=np.full(n, np.inf), contact=np.zeros(n, int), inside=np.zeros(n, int),
               first_contact_tau=np.full(n, np.nan), sep_tau=np.full(n, np.nan), dist_gap=np.full(n, np.nan), dist_tstar=np.full(n, np.nan),
               sd_tstar=np.full(n, np.nan), min_dist_after_sep=np.full(n, np.inf), inside_full=np.zeros(n, int), inside_where=[None] * n)
    for k_, tau in enumerate(taus):
        alive = tau >= te + PP["check_skip_s"]
        if not alive.any():
            continue
        Xh = hero.world(float(tau))[:, jb:je + 1]; Nh = D.grid_normals(Xh)
        Xn = near.world(float(tau)); Nn = D.grid_normals(Xn)
        Xf = far.world(float(tau)); Nf = D.grid_normals(Xf)
        V = np.concatenate([Xh.reshape(-1, 3), Xn.reshape(-1, 3), Xf.reshape(-1, 3)])
        NN = np.concatenate([Nh.reshape(-1, 3), Nn.reshape(-1, 3), Nf.reshape(-1, 3)])
        tree = cKDTree(V)
        idx = np.nonzero(alive)[0]
        p = D.traj(pe[idx], v0[idx], te[idx], np.full(len(idx), tau))
        dist, j = tree.query(p)
        sd = np.sum((p - V[j]) * NN[j], -1)
        par = np.zeros(len(idx), int)
        full = (k_ % every == 0) or abs(tau) < 1e-9
        gate = np.ones(len(idx), bool) if full else (dist < PP["parity_gate_m"])
        if gate.any():
            gi = np.nonzero(gate)[0]
            # 近い点を同じ塊にして、三角形の前の選り分けを小さくする
            o = np.lexsort((np.floor(p[gi, 2] / 4.0), np.floor(p[gi, 0] / 4.0)))
            gi = gi[o]
            par[gi] = D.crossings_up(p[gi], V, Tall) % 2
        near_s = (dist < rad[idx] + PP["contact_extra_m"] + PP["vertex_slack_m"])
        ins = par == 1
        if full:
            res["inside_full"][idx] += ins.astype(int)
        for ii in idx[ins]:
            if res["inside_where"][ii] is None:
                res["inside_where"][ii] = dict(tau=float(tau), p=[float(x) for x in D.traj(pe[ii:ii + 1], v0[ii:ii + 1], te[ii:ii + 1], np.array([tau]))[0]])
        clear = (dist >= rad[idx] + PP["sep_m"] + PP["vertex_slack_m"]) & (par == 0)
        sep = ~np.isnan(res["sep_tau"][idx])
        newsep = idx[clear & ~sep]
        res["sep_tau"][newsep] = tau
        cont = near_s & sep
        bad = cont | ins
        res["contact"][idx] += cont.astype(int)
        res["inside"][idx] += ins.astype(int)
        first = idx[bad & np.isnan(res["first_contact_tau"][idx])]
        res["first_contact_tau"][first] = tau
        res["min_dist"][idx] = np.minimum(res["min_dist"][idx], dist)
        res["min_dist_after_sep"][idx[sep]] = np.minimum(res["min_dist_after_sep"][idx[sep]], dist[sep])
        res["min_sd"][idx] = np.minimum(res["min_sd"][idx], np.where(dist < 3.0, sd, np.inf))
        g = np.abs(tau - (te[idx] + PP["gap_after_s"])) < 0.5 / PP["check_hz"]
        res["dist_gap"][idx[g]] = dist[g]
        if abs(tau) < 1e-9:
            res["dist_tstar"][idx] = dist
            res["sd_tstar"][idx] = sd
    late = np.isnan(res["sep_tau"]) | (res["sep_tau"] > te + PP["sep_within_s"])
    res["never_left"] = late.astype(int)
    return res


def ballistic_solve(ps, rad, X, U, N, us, taus, white_ok, emit_offset=0.01):
    """設計31 の逆弾道（放出点 X（τ × 頂点）から、t* に ps に着く初速）。条件は親と同じ（v0 と水面の速度の角度 ≤ 45°、速さの比 0.5〜2、離れる向き、放出の時に白）。"""
    dt = -taus[:, None, None]
    Xo = X + N * (rad + emit_offset)
    v0 = (ps - Xo) / dt - 0.5 * G * dt
    vn = np.linalg.norm(v0, axis=-1)
    cosang = np.sum(v0 * U, -1) / np.maximum(vn * us, 1e-9)
    ang = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
    ratio = vn / np.maximum(us, 1e-9)
    leave = np.sum((v0 - U) * N, -1) >= 0.0
    ok = (ang <= P["max_angle_deg"]) & (ratio >= P["speed_ratio"][0]) & (ratio <= P["speed_ratio"][1]) & white_ok & leave
    score = np.where(ok, ang + P["score_ratio_w"] * np.abs(np.log(np.maximum(ratio, 1e-9))), np.inf)
    return Xo, v0, ang, ratio, score


def random_children(args, P, rng, keep, parents, dots_px, dot_tone, split, cam, zb, white_now, white_vis, sky_id, hero, TW, Fv, zone, check, log, n_need, t0):
    """修正前の子の置き方（random）：親の放出点のまわりの白い頂点から、親の速度のまわりに散らして出し、t* の規則に合うものだけ採る。"""
    h = P["vel_h"]
    cands = []
    grid_world = {}

    def world_at(t):
        k = round(float(t), 4)
        if k not in grid_world:
            Xw = hero.world(k)
            grid_world[k] = (Xw, hero.world(k + h), hero.world(k - h), D.grid_normals(Xw))
            if len(grid_world) > 80:
                grid_world.pop(next(iter(grid_world)))
        return grid_world[k]
    tries = 0
    # 子の放出の時刻は taus の格子に丸める（世界の格子を使い回すため）
    for rep in range(P["child_per_parent_try"]):
        for p in parents:
            tries += 1
            er0, ec0 = p["emitter"]["row"], p["emitter"]["col"]
            r_ = int(np.clip(er0 + rng.integers(-P["child_dr"], P["child_dr"] + 1), 0, hero.R - 1))
            c_ = int(np.clip(ec0 + rng.integers(-P["child_dc"], P["child_dc"] + 1), 0, hero.C - 1))
            if not zone[r_, c_] or not (P["child_emit_F"][0] <= Fv[r_, c_] <= P["child_emit_F"][1]):
                continue
            te = p["tau_e"] + rng.uniform(*P["child_tau_jitter"])
            te = float(np.clip(np.round(te / P["tau_e_step"]) * P["tau_e_step"], P["tau_e"][0], P["tau_e"][1]))
            if TW[r_, c_] > te:
                continue
            Xw, Xp, Xm, Nw = world_at(te)
            u = (Xp[r_, c_] - Xm[r_, c_]) / (2 * h)
            rad = max(P["child_radius_min"], p["radius_m"] * rng.uniform(*P["child_radius"]))
            v0 = rot_jitter(np.array(p["v0"]) * rng.uniform(*P["child_speed"]), P["child_angle_deg"], rng)
            ang = math.degrees(math.acos(np.clip(v0 @ u / max(np.linalg.norm(v0) * np.linalg.norm(u), 1e-9), -1, 1)))
            ratio = np.linalg.norm(v0) / max(np.linalg.norm(u), 1e-9)
            nrm = Nw[r_, c_]
            if ang > P["max_angle_deg"] or not (P["speed_ratio"][0] <= ratio <= P["speed_ratio"][1]) or (v0 - u) @ nrm < 0:
                continue
            pe = Xw[r_, c_] + nrm * (rad + 0.01)
            dt = -te
            ps = pe + v0 * dt + 0.5 * G * dt * dt
            # 原画視点の t* の規則
            xy, zc = cam.project(ps[None, :])
            x, y = float(xy[0, 0]), float(xy[0, 1]); zc = float(zc[0])
            rpx = rad * cam.focal_px / max(zc, 1e-6)
            rule = None
            if zc <= 0.1 or x < -rpx or x > 1919 + rpx or y < -rpx or y > 1079 + rpx:
                rule = "offscreen"
            else:
                xs = np.clip(np.round([x, x - rpx - P["hide_margin_px"], x + rpx + P["hide_margin_px"], x, x]).astype(int), 0, 1919)
                ys = np.clip(np.round([y, y, y, y - rpx - P["hide_margin_px"], y + rpx + P["hide_margin_px"]]).astype(int), 0, 1079)
                izs = zb[ys, xs]
                zs = np.where(izs > 0, 1.0 / np.maximum(izs, 1e-12), np.inf)
                if np.all(zs < zc - P["child_occl_margin_m"]) and not np.any(sky_id[ys, xs]):
                    rule = "occluded"
                elif np.all(white_now[ys, xs]) and np.all(white_vis[ys, xs]) and ps[1] > split:
                    # 今の白の上（白・生成りの粒だけ。灰の白の粒は白の上で見えるので置かない）
                    rule = "over_white"
                else:
                    dd = np.hypot(dots_px[:, 0] - x, dots_px[:, 1] - y) + rpx
                    tone_c = 1 if ps[1] <= split else 0
                    inside = np.nonzero(dd <= dots_px[:, 2] + 0.5)[0]
                    if len(inside) and any(dot_tone[keep[j]["dot_id"]] == tone_c for j in inside):
                        rule = "inside_dot"
            if rule is None:
                continue
            cands.append(dict(parent=p["dot_id"], row=r_, col=c_, tau_e=te, p_e=pe.tolist(), v0=v0.tolist(), radius=rad, p_star=ps.tolist(),
                              x_d=x, y_d=y, rpx=rpx, rule=rule, angle_deg=ang, speed_ratio=ratio, t_white=float(TW[r_, c_]), k=0))
        if len(cands) >= 1.6 * n_need:
            break
    print("child candidates", len(cands), "tries", tries, "%.1fs" % (time.time() - t0))
    chk2 = check(cands) if cands else None
    good_c = []
    for i, q in enumerate(cands):
        if chk2["contact"][i] == 0 and chk2["inside"][i] == 0 and chk2["never_left"][i] == 0:
            q["dist_tstar_m"] = float(chk2["dist_tstar"][i])
            good_c.append(q)
    dropped_vis = 0
    if args.drop_visible:
        comps = json.load(open(args.drop_visible, encoding="utf-8"))["spray"]["after"]["worst_components"]
        CC = np.array([[c_["x"], c_["y"]] for c_ in comps]) if comps else np.zeros((0, 2))
        keep_c = []
        for q in good_c:
            if len(CC) and q["rule"] != "offscreen" and (np.hypot(CC[:, 0] - q["x_d"], CC[:, 1] - q["y_d"]) < q["rpx"] + 4.0).any():
                dropped_vis += 1
                continue
            keep_c.append(q)
        good_c = keep_c
        log["inputs"]["drop_visible"] = args.drop_visible.replace(REPO + "/", ""); log["inputs"]["drop_visible_sha256"] = sha(args.drop_visible)
    # 親ごとに順番に取る（同じ親に偏らない）
    byp = {}
    for q in good_c:
        byp.setdefault(q["parent"], []).append(q)
    chosen = []
    while len(chosen) < n_need and any(byp.values()):
        for k_ in list(byp.keys()):
            if byp[k_]:
                chosen.append(byp[k_].pop(0))
                if len(chosen) >= n_need:
                    break
    rules = {}
    for q in chosen:
        rules[q["rule"]] = rules.get(q["rule"], 0) + 1
    log["children"] = dict(tries=tries, candidates=len(cands), passed_150=len(good_c) + dropped_vis, dropped_visible_in_render=dropped_vis, chosen=len(chosen), rules=rules, need=n_need)
    print("children", log["children"], "%.1fs" % (time.time() - t0))

    return chosen


def targeted_children(args, P, rng, keep, table, parents, dots_px, dot_tone, split, cam, zb, idb, white_now, white_vis, sky_id,
                      X, U, N, us, taus, white_ok, er, ec, TWe, Fv, zone, robust, hero, TW, check, log, n_need, t0):
    """修正01 の子の置き方（targeted）：原画視点 t* の狙いの位置を先に決め、親と同じ逆弾道（放出点は Hash1 によらない白の範囲の頂点、放出の時に白、
    v0 と水面の速度の角度 ≤ 45°、速さの比 0.5〜2、離れる向き）で放出点を探す。狙いは 2 種類：
      inside_dot：原画の点の射線のまわり（点の円の中、親の奥行き ±dot_depth_m）。原画視点 t* では原画の点に重なる（同じ色の段）。
      over_white：原画視点 t* で今の白（色区 ID の白で、描画でも白。主役波の唇・頂の箱の中）の画素の、白い面の手前 over_white_front_m。
    主役波の陰に隠れる所（管の中・唇の下）には置かない（修正前の random では子の 1,939 が管の中に詰まり、原画視点 t 9〜11.5 s の藍の壁の前の粒と、
    座席から波の方向の t* の保持の一面の点になった）。大きさは親（原画の点の大きさ）の半径の分布から取り、child_radius_scale を掛ける。"""
    f = cam.focal_px
    zsurf = np.where(zb > 0, 1.0 / np.maximum(zb, 1e-12), np.inf)
    rad_par = np.array([t["radius_m"] for t in table if t["kind"] == "parent"])
    par_ids = {t["dot_id"] for t in table}
    targets = []
    stat = dict(inside_dot_tries=0, inside_dot_targets=0, over_white_tries=0, over_white_targets=0)
    # (a) 原画の点の中
    for r in keep:
        if r["dot_id"] not in par_ids:
            continue
        rd = 0.5 * r["diam_display_px"]
        z0 = float(cam.depth(np.array(r["p_star"])))
        made = tries = 0
        while made < P["child_per_dot"] and tries < 60:
            tries += 1
            stat["inside_dot_tries"] += 1
            zc = z0 + rng.uniform(-P["dot_depth_m"], P["dot_depth_m"])
            rad = float(rng.choice(rad_par) * rng.uniform(*P["child_radius_scale"]))
            rpx = rad * f / zc
            rpx_max = P["dot_child_rpx_frac"] * rd
            if rpx > rpx_max:
                rad, rpx = rpx_max * zc / f, rpx_max
            if rad < P["child_radius_min"]:
                continue
            lat = max(rd - rpx - 0.3, 0.0)
            th = rng.uniform(0, 2 * math.pi)
            rr_ = lat * math.sqrt(rng.random())
            x, y = r["x_d"] + rr_ * math.cos(th), r["y_d"] + rr_ * math.sin(th)
            ray = cam.ray(x, y)
            ps = cam.pos + ray * (zc / float(ray @ cam.f))
            px, py = int(np.clip(round(x), 0, 1919)), int(np.clip(round(y), 0, 1079))
            if not zc < zsurf[py, px] - P["occl_margin_m"]:
                continue
            if (1 if ps[1] <= split else 0) != dot_tone[r["dot_id"]]:
                continue
            targets.append(dict(rule="inside_dot", parent=r["dot_id"], p_star=ps, radius=rad, x_d=x, y_d=y, rpx=rpx))
            made += 1
    stat["inside_dot_targets"] = len(targets)
    # (b) 今の白の上（唇・頂の箱の中の主役波の白）
    bx = P["over_white_box"]
    okpx = white_now & white_vis & (idb == K.CLS["hero_body"])
    box = np.zeros_like(okpx)
    box[bx[1]:bx[3], bx[0]:bx[2]] = True
    ys_, xs_ = np.nonzero(okpx & box)
    for i in range(P["over_white_tries"] if len(xs_) else 0):
        stat["over_white_tries"] += 1
        k = int(rng.integers(len(xs_)))
        x, y = xs_[k] + rng.uniform(-0.5, 0.5), ys_[k] + rng.uniform(-0.5, 0.5)
        zc = float(zsurf[ys_[k], xs_[k]] - rng.uniform(*P["over_white_front_m"]))
        rad = float(rng.choice(rad_par) * rng.uniform(*P["child_radius_scale"]))
        rpx = rad * f / zc
        m = P["over_white_margin_px"]
        xs = np.clip(np.round([x, x - rpx - m, x + rpx + m, x, x]).astype(int), 0, 1919)
        ys = np.clip(np.round([y, y, y, y - rpx - m, y + rpx + m]).astype(int), 0, 1079)
        if not (np.all(okpx[ys, xs]) and np.all(zsurf[ys, xs] > zc + 0.2)):
            continue
        ray = cam.ray(x, y)
        ps = cam.pos + ray * (zc / float(ray @ cam.f))
        if ps[1] <= split:
            continue
        targets.append(dict(rule="over_white", parent=None, p_star=ps, radius=rad, x_d=x, y_d=y, rpx=rpx))
    stat["over_white_targets"] = len(targets) - stat["inside_dot_targets"]
    print("child targets", stat, "%.1fs" % (time.time() - t0))
    # 逆弾道
    pe_rc = np.array([[p["emitter"]["row"], p["emitter"]["col"]] for p in parents])
    cands = []
    nos = 0
    for tg in targets:
        Xo, v0, ang, ratio, score = ballistic_solve(tg["p_star"], tg["radius"], X, U, N, us, taus, white_ok)
        order = np.argsort(score, axis=None)[:P["over_white_pick_top"]]
        order = [f_ for f_ in order if np.isfinite(score.flat[f_])]
        if not order:
            nos += 1
            continue
        f_ = order[int(rng.integers(len(order)))]
        it, ie = np.unravel_index(f_, score.shape)
        if tg["parent"] is None:
            j = int(np.argmin(np.hypot(pe_rc[:, 0] - er[ie], pe_rc[:, 1] - ec[ie])))
            parent = parents[j]["dot_id"]
        else:
            parent = tg["parent"]
        cands.append(dict(parent=parent, row=int(er[ie]), col=int(ec[ie]), tau_e=float(taus[it]), p_e=Xo[it, ie].tolist(), v0=v0[it, ie].tolist(),
                          radius=tg["radius"], p_star=[float(v) for v in tg["p_star"]], x_d=float(tg["x_d"]), y_d=float(tg["y_d"]), rpx=float(tg["rpx"]),
                          rule=tg["rule"], angle_deg=float(ang[it, ie]), speed_ratio=float(ratio[it, ie]), t_white=float(TWe[ie]), k=0))
    print("child candidates", len(cands), "no solution", nos, "%.1fs" % (time.time() - t0))
    chk2 = check(cands) if cands else None
    good_c = []
    fail = dict(contact=0, inside=0, never_left=0, gap=0)
    inside_where = []
    for i, q in enumerate(cands):
        bad = False
        if chk2["contact"][i]:
            fail["contact"] += 1
            bad = True
        if chk2["inside"][i]:
            fail["inside"] += 1
            bad = True
            if len(inside_where) < 20:
                w_ = (chk2.get("inside_where") or [None] * len(cands))[i] or {}
                inside_where.append(dict(rule=q["rule"], **w_))
        if chk2["never_left"][i]:
            fail["never_left"] += 1
            bad = True
        if not (chk2["dist_gap"][i] >= P["child_gap_min_m"]):
            fail["gap"] += 1
            bad = True
        if bad:
            continue
        q["dist_tstar_m"] = float(chk2["dist_tstar"][i])
        q["dist_gap_m"] = float(chk2["dist_gap"][i])
        good_c.append(q)
    dropped_vis = 0
    if args.drop_visible:
        comps = json.load(open(args.drop_visible, encoding="utf-8"))["spray"]["after"]["worst_components"]
        CC = np.array([[c_["x"], c_["y"]] for c_ in comps]) if comps else np.zeros((0, 2))
        keep_c = []
        for q in good_c:
            if len(CC) and (np.hypot(CC[:, 0] - q["x_d"], CC[:, 1] - q["y_d"]) < q["rpx"] + 4.0).any():
                dropped_vis += 1
                continue
            keep_c.append(q)
        good_c = keep_c
        log["inputs"]["drop_visible"] = args.drop_visible.replace(REPO + "/", "")
        log["inputs"]["drop_visible_sha256"] = sha(args.drop_visible)
    ins, per = [], {}
    for q in good_c:
        if q["rule"] == "inside_dot" and per.get(q["parent"], 0) < P["dot_child_max"]:
            per[q["parent"]] = per.get(q["parent"], 0) + 1
            ins.append(q)
    ovw = [q for q in good_c if q["rule"] == "over_white"]
    chosen = ins[:n_need] + ovw[:max(n_need - len(ins), 0)]
    rules = {}
    for q in chosen:
        rules[q["rule"]] = rules.get(q["rule"], 0) + 1
    log["children"] = dict(mode="targeted", targets=stat, candidates=len(cands), no_solution=nos, failed=fail, inside_examples=inside_where,
                           passed=len(good_c) + dropped_vis, dropped_visible_in_render=dropped_vis, chosen=len(chosen), rules=rules, need=n_need)
    print("children", {k: v for k, v in log["children"].items() if k != "inside_examples"}, "%.1fs" % (time.time() - t0))
    return chosen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--target", type=int, default=P["child_target_total"])
    ap.add_argument("--seed", type=int, default=31)
    ap.add_argument("--child-mode", choices=["targeted", "random"], default="targeted",
                    help="子の置き方。random：修正前（放出点と初速を散らして、t* の規則に合うものだけ採る。管の中に 1,939 が詰まった）。"
                         "targeted：修正01（t* の狙いの位置を先に決め、逆弾道で白の放出点を探す）")
    ap.add_argument("--check", choices=["full", "old"], default="full", help="150 の検査。old：設計31 の check_paths（近い海の行 0〜30）。full：主役波・近い海・遠い海の全部")
    ap.add_argument("--drop-visible", default=None, help="pl31_measure.json：前の回の Unity の描画（原画視点 t*）で原画の点の円の外に見えた飛沫の塊。その塊に重なる子を除いて選び直す（描画で確かめた除き）")
    args = ap.parse_args()
    P["child_target_total"] = args.target
    t0 = time.time()
    out = args.out
    os.makedirs(out + "/_work", exist_ok=True)
    rng = np.random.default_rng(args.seed)
    spec = S.load_json(D.TRUTH)
    cam = C27.Cam(spec)
    hero = K.Pkg(HERO_PKG)
    near = K.Pkg(os.path.join(SEA_DIR, "near")); far = K.Pkg(os.path.join(SEA_DIR, "far"))
    assert np.array_equal(near.knots, hero.knots)
    kmeta = S.load_json(KMETA)
    frame = kmeta["frame"]
    TW = np.load(WHITE_DIR + "/pl31_twhite_used.npy").astype(np.float64).reshape(hero.R, hero.C)
    zone = np.load(WHITE_DIR + "/pl31_zone_vertex.npy").reshape(hero.R, hero.C)
    attr = np.fromfile(ATTR, "<f4").reshape(hero.R, hero.C, 12)
    Fv = attr[..., 0]
    sys.path.insert(0, HERE)
    import pl31_zone as Zn
    zr_ = Zn.zone_robust(Zn.load_attr(n=hero.R * hero.C), Zn.load_params()).reshape(hero.R, hero.C)
    robust = zone & (zr_ > P["robust_margin"])
    emit_zone = robust if args.child_mode == "targeted" else zone

    def check(paths):
        if args.check == "full":
            return check_paths_full(paths, hero, near, far, P["tau_e"][0])
        return D.check_paths(paths, hero, near, P["tau_e"][0])
    log = dict(number="仕上げ31", part="飛沫", schema="GreatWave.Polish31.spray_log/1", params=P,
               inputs=dict(hero_pkg=HERO_PKG.replace(REPO + "/", ""), hero_pos_sha256=hero.k["pos_sha256"], hero_twhite_sha256=hero.k["twhite_sha256"],
                           near_pos_sha256=near.k["pos_sha256"], far_pos_sha256=far.k["pos_sha256"],
                           timewarp=WARP.replace(REPO + "/", ""), timewarp_sha256=sha(WARP), kstar_meta_sha256=sha(KMETA),
                           attr_sha256=sha(ATTR), zone_sha256=sha(WHITE_DIR + "/pl31_zone_vertex.npy"),
                           ids_tstar=IDS_TSTAR.replace(REPO + "/", ""), ids_tstar_sha256=sha(IDS_TSTAR),
                           eye=EYE.replace(REPO + "/", ""), eye_sha256=sha(EYE),
                           reference=spec["reference"]["path"], reference_sha256=sha(os.path.join(REPO, spec["reference"]["path"]))),
               code_sha256={os.path.basename(__file__): sha(os.path.abspath(__file__))})

    # ---------------------------------------------------------------- 1. 取り出しと目の照合
    D.P["zone_display"] = [-1e9, -1e9, 1e9, 1e9]
    alld, ex = D.extract_dots(spec)
    eye = S.load_json(EYE)
    z = eye["zone_display"]
    acc = []
    for d in alld:
        inz = z[0] <= d["x_d"] <= z[2] and z[1] <= d["y_d"] <= z[3]
        if inz:
            d["zone"] = "lip_front"; acc.append(d); continue
        for ex_ in eye["outside_accept_display_xy"]:
            if abs(d["x_d"] - ex_[0]) <= 1.5 and abs(d["y_d"] - ex_[1]) <= 1.5:
                d["zone"] = "right_sky" if d["y_d"] < 500 else "near_boat"
                d["eye_note"] = ex_[2]
                acc.append(d)
                break
    for i, d in enumerate(acc):
        d["dot_id"] = i
    log["extract"] = dict(all_candidates=len(alld), accepted=len(acc), lip_front=sum(1 for d in acc if d["zone"] == "lip_front"),
                          right_sky=sum(1 for d in acc if d["zone"] == "right_sky"), near_boat=sum(1 for d in acc if d["zone"] == "near_boat"),
                          eye_listed=len(eye["outside_accept_display_xy"]))
    print("dots", log["extract"], "%.1fs" % (time.time() - t0))
    assert log["extract"]["right_sky"] + log["extract"]["near_boat"] == len(eye["outside_accept_display_xy"]), "目の照合の点が取り出しと合わない"

    # ---------------------------------------------------------------- t* の z バッファ（主役波の本体・near・far・船・前景の泡。仕上げ30 は左の支えの仮置きを隠す）
    jb, je = 18, 394
    cls_near = np.fromfile(os.path.join(SEA_DIR, "near", "ds30_class_u8.bin"), np.uint8).reshape(near.R, near.C)
    cls_far = np.fromfile(os.path.join(SEA_DIR, "far", "ds30_class_u8.bin"), np.uint8).reshape(far.R, far.C)
    boats = K.boats_tris(); ph = K.placeholder_tris()
    ph["M1_Revision_LeftSupport"] = [np.zeros((0, 3, 3)), np.zeros((0, 3, 3))]
    tris, ids = K.scene_tris(0.0, hero, near, far, jb, je, "after", boats, ph, cls_near, cls_far)
    idb, zb = K.raster_ids(cam, tris, ids)
    idb = idb.reshape(1080, 1920); zb = zb.reshape(1080, 1920)
    np.save(out + "/_work/scene_tstar_ids.npy", idb.astype(np.uint8)); np.save(out + "/_work/scene_tstar_zb.npy", zb.astype(np.float32))
    # 今の白（Unity の色区 ID の t* の原画視点、爪あり・線なし、3840×2160）→ 1920×1080 の「白」の画素（4 つとも白）
    idimg = cv2.imread(IDS_TSTAR)
    red = (idimg[..., 2] > 200) & (idimg[..., 1] < 60) & (idimg[..., 0] < 60)
    white_now = red.reshape(1080, 2, 1920, 2).all(axis=(1, 3))
    sky_id = ((idimg[..., 2] < 60) & (idimg[..., 1] > 200) & (idimg[..., 0] > 200)).reshape(1080, 2, 1920, 2).any(axis=(1, 3))
    # 描画で白に見える所（爪・唇の縁の線の上を除くため 3×3 で縮める）
    rn = cv2.imread(RENDER_NOSPRAY)
    if rn is not None:
        wimg = (np.abs(rn[..., ::-1].astype(np.int16) - np.array(HERO_WHITE8)).sum(-1) <= P["white_tol_rgb"]).astype(np.uint8)
        white_vis = cv2.erode(wimg, np.ones((3, 3), np.uint8)).astype(bool)
        log["inputs"]["render_nospray"] = RENDER_NOSPRAY.replace(REPO + "/", ""); log["inputs"]["render_nospray_sha256"] = sha(RENDER_NOSPRAY)
    else:
        white_vis = white_now
    print("zbuffer %.1fs" % (time.time() - t0))

    # ---------------------------------------------------------------- 2. 層への配置（設計31 と同じ規則：唇の先（列 200）の前方 0.5〜3 m の層、射線の上）
    D.P["lip_ref_rows"] = [125, 195]; D.P["lip_col"] = 200
    recs = D.place(acc, hero, cam, zb.reshape(-1).reshape(1080, 1920), frame)
    # t* に主役波の前に来る点：粒の中心の画素の z バッファが主役波（id 1）で、粒が手前。今の色が白なら残す（白の上の白）、白でなければ除く
    keep = []
    front_hero = []
    for r in recs:
        px, py = int(round(r["x_d"])), int(round(r["y_d"]))
        on_hero = int(idb[py, px]) == K.CLS["hero_body"]
        r["over_hero_at_tstar"] = bool(on_hero)
        r["over_white_now"] = bool(white_now[py, px])
        if on_hero:
            front_hero.append(dict(dot_id=r["dot_id"], x_d=r["x_d"], y_d=r["y_d"], over_white_now=bool(white_now[py, px])))
        if not r["visible_at_tstar"]:
            continue
        if on_hero and not white_now[py, px]:
            r["dropped_ja"] = "t* に主役波の白でない所の前に来る（原画では爪の間の空）"
            continue
        keep.append(r)
    log["place"] = dict(dots=len(recs), visible=sum(1 for r in recs if r["visible_at_tstar"]), over_hero=len(front_hero),
                        over_hero_white_kept=sum(1 for f in front_hero if f["over_white_now"]), over_hero_nonwhite_dropped=sum(1 for f in front_hero if not f["over_white_now"]),
                        kept=len(keep), front_hero=front_hero)
    print("placed", {k: v for k, v in log["place"].items() if k != "front_hero"})

    # ---------------------------------------------------------------- 3. 逆弾道（放出点は白の範囲の頂点、放出の時刻に白）
    r0, r1 = P["emit_rows"]; c0, c1 = P["emit_cols"]
    rr = np.arange(r0, r1 + 1, P["emit_row_step"]); cc = np.arange(c0, c1 + 1, P["emit_col_step"])
    RR, CC = np.meshgrid(rr, cc, indexing="ij")
    em = emit_zone[RR, CC] & (Fv[RR, CC] >= P["emit_F"][0]) & (Fv[RR, CC] <= P["emit_F"][1])
    er, ec = RR[em], CC[em]
    taus = np.round(np.arange(P["tau_e"][0], P["tau_e"][1] + 1e-9, P["tau_e_step"]), 4)
    h = P["vel_h"]
    Xs, Us, Ns = [], [], []
    for t in taus:
        Xw = hero.world(float(t)); Xp = hero.world(float(t) + h); Xm = hero.world(float(t) - h)
        Nw = D.grid_normals(Xw)
        Xs.append(Xw[er, ec]); Us.append((Xp[er, ec] - Xm[er, ec]) / (2 * h)); Ns.append(Nw[er, ec])
    X = np.stack(Xs); U = np.stack(Us); N = np.stack(Ns)       # (T, E, 3)
    TWe = TW[er, ec]
    white_ok = TWe[None, :] <= taus[:, None]
    us = np.linalg.norm(U, axis=-1)
    log["emitters"] = dict(vertices=int(len(er)), taus=int(len(taus)), zone_mode=("hash_robust" if args.child_mode == "targeted" else "zone"),
                           grid_zone_vertices=int((zone[RR, CC] & (Fv[RR, CC] >= P["emit_F"][0]) & (Fv[RR, CC] <= P["emit_F"][1])).sum()),
                           grid_robust_vertices=int((robust[RR, CC] & (Fv[RR, CC] >= P["emit_F"][0]) & (Fv[RR, CC] <= P["emit_F"][1])).sum()),
                           rule_ja="放出点の候補は白の範囲の頂点で、修正01 では房の Hash1 のどの値でも白の範囲に入る頂点（zone_robust > %.2f）に限る" % P["robust_margin"])
    print("emitters", len(er), "%.1fs" % (time.time() - t0))

    def solve(ps, rad):
        dt = -taus[:, None, None]
        Xo = X + N * (rad + 0.01)
        v0 = (ps - Xo) / dt - 0.5 * G * dt
        vn = np.linalg.norm(v0, axis=-1)
        cosang = np.sum(v0 * U, -1) / np.maximum(vn * us, 1e-9)
        ang = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
        ratio = vn / np.maximum(us, 1e-9)
        leave = np.sum((v0 - U) * N, -1) >= 0.0
        ok = (ang <= P["max_angle_deg"]) & (ratio >= P["speed_ratio"][0]) & (ratio <= P["speed_ratio"][1]) & white_ok & leave
        score = np.where(ok, ang + P["score_ratio_w"] * np.abs(np.log(np.maximum(ratio, 1e-9))), np.inf)
        return Xo, v0, ang, ratio, score

    flat = []
    for rec in keep:
        ps = np.array(rec["p_star"])
        Xo, v0, ang, ratio, score = solve(ps, rec["radius_m"])
        order = np.argsort(score, axis=None)
        picked, seen = [], []
        for f in order[:6000]:
            if not np.isfinite(score.flat[f]):
                break
            it, ie = np.unravel_index(f, score.shape)
            if any(abs(taus[it] - s0) < 0.05 for s0 in seen) and len(picked) >= 4:
                continue
            seen.append(taus[it])
            picked.append(dict(dot=rec["dot_id"], tau_e=float(taus[it]), row=int(er[ie]), col=int(ec[ie]), p_e=Xo[it, ie].tolist(), v0=v0[it, ie].tolist(),
                               u_s=U[it, ie].tolist(), angle_deg=float(ang[it, ie]), speed_ratio=float(ratio[it, ie]), score=float(score[it, ie]),
                               t_white=float(TWe[ie]), radius=rec["radius_m"], k=len(picked)))
            if len(picked) >= P["top_k"]:
                break
        # V3 の寿命の測り：τ_e が今の最良の 1.6 倍まで早い候補（得点は問わず条件だけ）を 4 つ足す
        if picked:
            te_best = picked[0]["tau_e"]
            want = max(P["v3_factor"] * te_best, P["tau_e"][0])
            itv = np.nonzero(taus <= want + 1e-9)[0]
            if len(itv):
                sc2 = score[itv]
                o2 = np.argsort(sc2, axis=None)[:4]
                for f in o2:
                    if not np.isfinite(sc2.flat[f]):
                        break
                    it2, ie2 = np.unravel_index(f, sc2.shape)
                    it = itv[it2]
                    picked.append(dict(dot=rec["dot_id"], tau_e=float(taus[it]), row=int(er[ie2]), col=int(ec[ie2]), p_e=Xo[it, ie2].tolist(),
                                       v0=v0[it, ie2].tolist(), u_s=U[it, ie2].tolist(), angle_deg=float(ang[it, ie2]), speed_ratio=float(ratio[it, ie2]),
                                       score=float(score[it, ie2]), t_white=float(TWe[ie2]), radius=rec["radius_m"], k=100 + len(picked), v3=True))
        flat.extend(picked)
    f8 = {r["dot_id"]: dict(D.f8_path(r, hero), dot=r["dot_id"], k=-1, radius=r["radius_m"]) for r in keep}
    allp = flat + list(f8.values())
    print("candidates", len(flat), "%.1fs" % (time.time() - t0))
    D.P["near_rows_checked"] = [0, 30]
    chk = check(allp)
    for i, q in enumerate(allp):
        q["ok150"] = bool(chk["contact"][i] == 0 and chk["inside"][i] == 0 and chk["never_left"][i] == 0)
        q["dist_tstar_m"] = float(chk["dist_tstar"][i]); q["dist_gap_m"] = float(chk["dist_gap"][i]); q["min_dist_m"] = float(chk["min_dist"][i])
    print("checked %.1fs" % (time.time() - t0))
    by = {}
    for q in flat:
        by.setdefault(q["dot"], []).append(q)
    table = []
    stat = dict(ballistic=0, f8=0, dropped=0, v3_extendable=0, v3_not_extendable=0)
    for rec in keep:
        qs = sorted([q for q in by.get(rec["dot_id"], []) if not q.get("v3")], key=lambda q: q["score"])
        good = [q for q in qs if q["ok150"]]
        v3ok = [q for q in by.get(rec["dot_id"], []) if q.get("v3") and q["ok150"]]
        if good:
            q = good[0]; mode = "ballistic"
            if v3ok:
                stat["v3_extendable"] += 1
            else:
                stat["v3_not_extendable"] += 1
        else:
            q = f8[rec["dot_id"]]; mode = "F8"
            if not q["ok150"]:
                stat["dropped"] += 1
                continue
        stat["ballistic" if mode == "ballistic" else "f8"] += 1
        table.append(dict(dot_id=rec["dot_id"], zone=rec["zone"], mode=mode, kind="parent", tau_e=q["tau_e"], tau_show=q["tau_e"],
                          ramp_s=0.08 if mode == "ballistic" else 0.1, p_e=q["p_e"], v0=q["v0"], radius_m=rec["radius_m"], p_star=rec["p_star"],
                          x_d=rec["x_d"], y_d=rec["y_d"], diam_display_px=rec["diam_display_px"], lab_painting=rec["lab"],
                          emitter=(None if mode == "F8" else dict(row=q["row"], col=q["col"], t_white=q["t_white"], F=float(Fv[q["row"], q["col"]]),
                                                                    zone_white=bool(zone[q["row"], q["col"]]), zone_robust=bool(robust[q["row"], q["col"]]))),
                          angle_deg=q.get("angle_deg"), speed_ratio=q.get("speed_ratio"), dist_tstar_m=q["dist_tstar_m"], dist_gap_m=q["dist_gap_m"],
                          over_hero_at_tstar=rec["over_hero_at_tstar"]))
    log["emit"] = stat
    print("parents", len(table), stat, "%.1fs" % (time.time() - t0))

    # ---------------------------------------------------------------- 5. 色（限定色 2 段。粒の t* の世界の高さで決める）
    pal = S.load_json(D.PALETTE)["palette"]
    white8 = pal["white"]["srgb8"]; lab_w = np.array(pal["white"]["lab"], float)
    par_t = [t for t in table if t["kind"] == "parent"]
    Lp = np.array([t["lab_painting"] for t in par_t])
    yst = np.array([t["p_star"][1] for t in par_t])
    de_w = ciede2000(Lp, np.broadcast_to(lab_w, Lp.shape))
    # 高さの閾値：灰の白にすると ΔE00 が下がる点（ΔE00(白) − ΔE00(灰) > 0）の高さの分け目を、全体の ΔE00 の最大が最も小さくなるように選ぶ
    dark = Lp[Lp[:, 0] < 92]
    # 灰の白：原画の暗い帯の点（L* < 92）の平均と白・生成りの Lab の中点（暗い帯の平均そのものは、描画で小さな点が背景と混ざって暗く出すぎた：
    # 描画の読みの p90 5.06・5 を超える点 23。中点で 4.16・15。色の読みの p90 は 4.47 → 4.34。仕上げ31 の作る部の試し）
    lab_g = 0.5 * (dark.mean(0) + lab_w) if len(dark) else lab_w
    grey8 = lab_to_srgb8(lab_g)
    lab_g = srgb8_to_lab(grey8)
    de_g = ciede2000(Lp, np.broadcast_to(lab_g, Lp.shape))
    best = None
    for ys in np.unique(np.round(yst, 2)):
        tone = yst <= ys
        de = np.where(tone, de_g, de_w)
        m = (float(np.percentile(de, 90)), float(de.max()))
        if best is None or m < best[0]:
            best = (m, float(ys))
    split = best[1] if best and best[0][1] < float(de_w.max()) else -1e9
    P["tone_split_y_m"] = split
    de_now = np.where(yst <= split, de_g, de_w)
    log["colour"] = dict(white_srgb8=white8, grey_srgb8=grey8, grey_lab=lab_g.round(2).tolist(), split_y_m=split,
                         parents_grey=int((yst <= split).sum()),
                         de00_white_only=dict(median=float(np.median(de_w)), p90=float(np.percentile(de_w, 90)), max=float(de_w.max()), over5=int((de_w > 5).sum())),
                         de00_two_tones=dict(median=float(np.median(de_now)), p90=float(np.percentile(de_now, 90)), max=float(de_now.max()), over5=int((de_now > 5).sum())),
                         rule_ja="151：原画の点の中心の 3×3 参照画素の Lab と粒の色の CIEDE2000。粒の色は限定色の 2 段（白・生成りと灰の白）で、"
                                 "t* の世界の高さ y ≤ 分け目の粒を灰の白にする（3 次元の量。原画の投影で塗らない）。灰の白は原画の暗い帯の点（L* < 92）の平均と白・生成りの Lab の中点")
    print("colour", log["colour"])

    dot_tone = {r["dot_id"]: (1 if r["p_star"][1] <= split else 0) for r in keep}

    # ---------------------------------------------------------------- 4. 子の粒（2〜3 千個へ）
    dots_px = np.array([[r["x_d"], r["y_d"], 0.5 * r["diam_display_px"]] for r in keep])
    parents = [t for t in table if t["mode"] == "ballistic"]
    n_need = max(P["child_target_total"] - len(table), 0)
    if args.child_mode == "targeted":
        chosen = targeted_children(args, P, rng, keep, table, parents, dots_px, dot_tone, split, cam, zb, idb, white_now, white_vis, sky_id,
                                   X, U, N, us, taus, white_ok, er, ec, TWe, Fv, zone, robust, hero, TW, check, log, n_need, t0)
    else:
        chosen = random_children(args, P, rng, keep, parents, dots_px, dot_tone, split, cam, zb, white_now, white_vis, sky_id, hero, TW, Fv, zone,
                                 check, log, n_need, t0)
    par = {t["dot_id"]: t for t in table}
    for q in chosen:
        p = par[q["parent"]]
        table.append(dict(dot_id=p["dot_id"], zone=p["zone"], mode="ballistic", kind="child", rule=q["rule"], tau_e=q["tau_e"], tau_show=q["tau_e"], ramp_s=0.08,
                          p_e=q["p_e"], v0=q["v0"], radius_m=q["radius"], p_star=q["p_star"], x_d=q["x_d"], y_d=q["y_d"],
                          diam_display_px=2 * q["rpx"], lab_painting=p["lab_painting"],
                          emitter=dict(row=q["row"], col=q["col"], t_white=q["t_white"], F=float(Fv[q["row"], q["col"]]), zone_white=bool(zone[q["row"], q["col"]]),
                                       zone_robust=bool(robust[q["row"], q["col"]])),
                          angle_deg=q["angle_deg"], speed_ratio=q["speed_ratio"], dist_tstar_m=q["dist_tstar_m"], dist_gap_m=q.get("dist_gap_m")))

    for t in table:
        t["tone"] = 1 if t["p_star"][1] <= split else 0
    # ---------------------------------------------------------------- 6. パッケージ（30 Hz のコマの表を色ごとに、GreatWave.DS31.particles/1）
    twj = S.load_json(WARP)
    t_all = np.array(twj["t"]); tau_all = np.array(twj["tau"])
    frames = np.arange(0, 421) / 30.0
    taus_f = np.interp(frames, t_all, tau_all)

    def write_pack(rows, stem, colour8, note):
        n = len(rows)
        tab = dict(p_e=np.array([t["p_e"] for t in rows]), v0=np.array([t["v0"] for t in rows]), tau_e=np.array([t["tau_e"] for t in rows]),
                   tau_show=np.array([t["tau_show"] for t in rows]), ramp_s=np.array([t["ramp_s"] for t in rows]), radius=np.array([t["radius_m"] for t in rows]))
        fr = np.zeros((len(frames), n, 4), np.float32)
        for i, tau in enumerate(taus_f):
            pos, rad = D.eval_state(tab, float(tau))
            fr[i, :, :3] = pos; fr[i, :, 3] = rad
        fp = os.path.join(out, stem + "_frames.bin"); fr.tofile(fp)
        meta = dict(schema="GreatWave.DS31.particles/1", frames=len(frames), hz=30, t0=0.0, count=n, file=os.path.basename(fp), sha256=sha(fp),
                    bytes=os.path.getsize(fp),
                    layout_ja="float32 リトルエンディアン、コマ × 数 × 4（x, y, z, 半径）。ワールドの m。半径 0 は描かない。コマ k は体験の時刻 t = t0 + k/hz（t ≥ 12 s は t* の静止）",
                    colour=[round(c / 255.0, 5) for c in colour8], colour_srgb8=colour8, colour_space_ja="sRGB（無照明の不透明）", note_ja=note)
        jdump(os.path.join(out, stem + "_frames.json"), meta)
        inst = np.zeros((n, 12), np.float32)
        if n:
            inst[:, 0:3] = tab["p_e"]; inst[:, 3] = tab["tau_e"]; inst[:, 4:7] = tab["v0"]; inst[:, 7] = tab["radius"]
            inst[:, 8] = tab["tau_show"]; inst[:, 9] = tab["ramp_s"]; inst[:, 10] = [0 if t["mode"] == "ballistic" else 1 for t in rows]
            inst[:, 11] = [t["dot_id"] for t in rows]
        ip = os.path.join(out, stem + "_inst_f32.bin"); inst.tofile(ip)
        return dict(count=n, frames_sha256=meta["sha256"], inst_sha256=sha(ip), frames_bytes=meta["bytes"])
    packs = {}
    for tone, c8, nm in ((0, white8, "白・生成り"), (1, grey8, "灰の白")):
        rows = [t for t in table if t["tone"] == tone]
        packs["tone%d" % tone] = write_pack(rows, "pl31_spray_tone%d" % tone, c8, "仕上げ31 の飛沫（%s。親 %d・子 %d）" % (nm, sum(1 for r in rows if r["kind"] == "parent"), sum(1 for r in rows if r["kind"] == "child")))
    # F8 の版（親だけ、全部 F8。見え方の比べ）
    f8rows = []
    for t in par_t:
        f = f8[t["dot_id"]]
        f8rows.append(dict(t, mode="F8", tau_e=f["tau_e"], tau_show=f["tau_e"], ramp_s=0.1, p_e=f["p_e"], v0=f["v0"], f8_ok150=f["ok150"]))
    packs["f8_tone0"] = write_pack([t for t in f8rows if t["tone"] == 0], "pl31_spray_f8_tone0", white8, "F8 の版（見え方の比べ。白）")
    packs["f8_tone1"] = write_pack([t for t in f8rows if t["tone"] == 1], "pl31_spray_f8_tone1", grey8, "F8 の版（見え方の比べ。灰の白）")
    log["f8_variant"] = dict(parents=len(f8rows), ok150=sum(1 for t in f8rows if t["f8_ok150"]))
    log["packs"] = packs
    # 寿命（見えている時間、体験の秒）と大きさ
    def t_of(tau):
        k = int(np.argmax(tau_all >= tau_all.max() - 1e-12))
        return np.interp(tau, tau_all[:k + 1], t_all[:k + 1])
    te_all = np.array([t["tau_e"] for t in table])
    life_t = 12.0 - t_of(te_all)
    kinds = np.array([t["kind"] for t in table])
    rads = np.array([t["radius_m"] for t in table])
    log["summary"] = dict(total=len(table), parents=int((kinds == "parent").sum()), children=int((kinds == "child").sum()),
                          life_t_s=dict(parent=[float(np.min(life_t[kinds == "parent"])), float(np.median(life_t[kinds == "parent"])), float(np.max(life_t[kinds == "parent"]))],
                                        child=([float(np.min(life_t[kinds == "child"])), float(np.median(life_t[kinds == "child"])), float(np.max(life_t[kinds == "child"]))] if (kinds == "child").any() else None)),
                          radius_m=dict(parent=np.percentile(rads[kinds == "parent"], [0, 50, 100]).round(4).tolist(),
                                        child=(np.percentile(rads[kinds == "child"], [0, 50, 100]).round(4).tolist() if (kinds == "child").any() else None)),
                          first_show_t=float(t_of(te_all.min())),
                          emitters_zone_white=int(sum(1 for t in table if t["emitter"] and t["emitter"]["zone_white"])),
                          emitters_total=int(sum(1 for t in table if t["emitter"])),
                          emitters_white_before_emit=int(sum(1 for t in table if t["emitter"] and t["emitter"]["t_white"] <= t["tau_e"] + 1e-9)),
                          emitters_zone_robust=int(sum(1 for t in table if t["emitter"] and t["emitter"].get("zone_robust"))),
                          gap_0p2s_m=dict(parent=np.nanpercentile([t["dist_gap_m"] for t in table if t["kind"] == "parent" and t.get("dist_gap_m") is not None], [0, 50]).round(4).tolist(),
                                          child=(np.nanpercentile([t["dist_gap_m"] for t in table if t["kind"] == "child" and t.get("dist_gap_m") is not None], [0, 50]).round(4).tolist()
                                                 if any(t["kind"] == "child" and t.get("dist_gap_m") is not None for t in table) else None),
                                          child_under_0p1=int(sum(1 for t in table if t["kind"] == "child" and t.get("dist_gap_m") is not None and t["dist_gap_m"] < 0.1))))
    print("summary", log["summary"])
    Vs, Fs = D.icosphere1()
    jdump(os.path.join(out, "pl31_spray_table.json"), dict(schema="GreatWave.Polish31.spray_table/1", count=len(table), particles=table))
    jdump(os.path.join(out, "pl31_spray_dots.json"), dict(schema="GreatWave.Polish31.spray_dots/1", dots=recs))
    log["seconds"] = time.time() - t0
    jdump(os.path.join(out, "pl31_spray_generate_log.json"), log)
    print("done %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
