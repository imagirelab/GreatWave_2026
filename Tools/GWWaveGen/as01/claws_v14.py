# -*- coding: utf-8 -*-
"""美術の見本01（Q29）爪の部 v14：美術監督の 8 項目の 1〜4・8（2026-10-03）で作り直した爪の層（numpy。静止、t* だけ）。

v13b（Build/Polish/sample01/claws/mesh_v13b、コードの写し claws/code_v13b）からの変更（項目の番号は美術監督の一覧）：
  1. as01_list_claw（区域 1 の原画の爪の輪）：L1・R1〜R3 の列（固定の列のずれ 16・50・66・82 の段、大きな丸い鉤）をやめ、
     原画の爪の一覧の帯の爪（191 本）を、根元が近く向きのそろう 2〜4 本の組にまとめ、組ごとに 1 つの爪を、先頭の爪の根元の当たりに置く。
     爪 1 つ＝細い茎 1 ＋ 組の爪の数（2〜4）の細い鉤の指。指の向きと巻く側は、組の各爪の 2 次元の向きと巻きの向き（一覧の中心線）から決め、
     接平面への持ち上げ（tangent_lift）と、射線に直交する面の向き（img_dir3）の中間に、法線へ少し起こした向き（射線に沿わない＝箒にならない）。
     長さは原画の爪の長さ（表示の画素 × その深さの 1 画素の m）× LC_K。先頭の指がいちばん長く、後の指は短い。
     原画の空の検査は許し 2 画素（LC_SKY_TOL）：出る指は向きを面へ寝かせ、長さを 0.85 倍ずつ縮め、それでも出るなら落とす（太さで逃げない）。
     指の間の角は LC_GAP 度以上あける（指の間に地が見える）。
  2. as01_face_hook（区域 2）：面の爪は、帯の外の原画の爪のうち、根元が近い物を 1 つにまとめ（数を減らす）、白い背（頂の列より後ろ）に当たる物は置かない。
     形は「幅の広い 1 本の巻く白い先」の板（面の上で巻く）と、その巻きの内の水色の板（縁の線あり。輪の頂点の角を 180° 回し、上面を水色の版の段にする）。
     牙・鶏の足（体＋指 3）はやめた。
  3. as01_crest_fan（頂の稜の扇）：冠（K…、31 本の同じ大きさの指）をやめ、頂の稜に沿って 3〜5 本の指の扇を置く。扇は太い掌（白い頂から続く塊、
     根元の円は面に沈める）から、頂の法線から 30〜60° 横と外へ開く長い指（v13b の冠の 2〜3 倍の長さ・太さ）。先は下へ巻く。長さは頂の高い所ほど長い。
     原画のカメラからは、点が主役波の後ろに隠れるか、原画の爪の輪郭の内（空でない所、許し 2 画素）に入ることを検査し、通らない時は扇を背の側へ倒し、
     指を縮める。
  4. 色と線：爪の水色は原画の爪の水色 (180, 202, 203)（as01_claw_params.txt）、縁の線は藍 (31, 60, 94)（描画の道具の -as01ClawLineColor）。
     爪の下の縁の線のない水色の膜（W…）は作らない。輪の段を増やす（指 ST_F 20、v13b は 12）。
  8. as01_lip_hang（唇の櫛）：唇の先から巻きを続け、先が下へ垂れる指（座席から波の方向で唇の下に見える）。巻きの角を小さく（唇の下へ戻って触れない）、
     背骨の全部で唇の面から離れることを検査。原画の空の検査は許し 2 画素（唇の指の間の空をふさがない）。
色の段は PL29 Claw Shade（輪の頂点 q の sin(45°·q) > 0.30 が白）。原画カメラからの投影の色は使わない（原画のカメラは置き場所・向き・検査だけ。Q28）。
参照モデル（OBJ）は読まない（F13-1）。彫刻（他者の作品）の形は写さない（指の太さ・長さ・開きの比だけを参考にした）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as01/claws_v14.py [--out …] [--zones list,lip,fan,hook] [--preview 視点,…]
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
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as01")
import claws_build as BB  # noqa: E402
import claws_common as CC  # noqa: E402
import claws_rim as CR  # noqa: E402

U = CC.U
unit, rot, jit, unit_rows = BB.unit, BB.rot, BB.jit, BB.unit_rows

P14 = dict(
    # 1. 原画の爪の輪（as01_list_claw）
    LC_GROUP_PX=42.0, LC_GROUP_ANG=75.0, LC_MAX=4, LC_EXT_MIN=18.0, LC_SCALE=1.6, LC_FK=2.3, LC_F_PX=(12.0, 45.0), LC_STEM=0.30, LC_STEM_R=0.16, LC_FING_R=0.095,
    LC_KAPPA=0.45, LC_IMG=0.55, LC_TH=235.0, LC_TH_J=0.12, LC_CURL_N=0.30, LC_GAP=16.0, LC_SKY_TOL=2, LC_FOLLOW=(1.0, 0.82, 0.70, 0.62),
    LC_P_CURL=1.5, LC_DISC=1.25,
    TC_PULL=0.8, TC_RANGE=3.0, TC_STRETCH=1.8, TC_STRETCH_BODY=1.4, TC_W=0.55, TC_W_PX=(2.6, 5.0), TC_TIP=0.14, TC_TAPER=1.0, TC_GAMMA=0.35, TC_CLEAR=0.7, TC_WHITE_VIEW=0.6, TC_BODY_BACK=0.45, TC_SCALE=1.4, TC_MAXF=3, TC_STEM_R0=1.05, TC_STEM_R1=0.95, TC_FOAM=True, TC_FOAM_BACK=0.12, TC_FOAM_W=0.30, TC_FOAM_SIDE=2.2, TC_FOAM_ARC=0.18, TC_FOAM_T=0.45,
    # 2. 面の爪（as01_face_hook）
    FH_GROUP_PX=34.0, FH_K=1.25, FH_MIN=0.7, FH_MAX=1.6, FH_W=0.46, FH_TH=230.0, FH_STRAIGHT=0.30, FH_INNER=0.42,
    # 3. 頂の稜の扇（as01_crest_fan）
    CF_ROWS=(58, 222), CF_DR=9, CF_DC=(4, 8, 12), CF_PEAK_MIN=0.70, CF_PALM_L=2.2, CF_PALM_R=1.15, CF_FING_L=(5.2, 8.6), CF_FING_R=0.62, CF_NF=(3, 5),
    CF_ELEV=(60.0, 50.0, 40.0, 30.0, 22.0), CF_ELEV_F=8.0, CF_AZ=70.0, CF_TH=190.0, CF_R_TIP=0.32, CF_SKY_TOL=2,
    # 8. 唇の櫛（as01_lip_hang）
    LH_ROWS=(70, 206), LH_GAP=2.6, LH_L=(1.8, 2.8), LH_RK=0.15, LH_ANG=(55.0, 35.0, 75.0, 100.0, 125.0), LH_DC=(2.0, 5.0, 0.0, 8.0, 12.0), LH_TH=100.0, LH_CLEAR=1.4,
    LH_SKY_TOL=2,
    ST_F=20, ST_STEM=8, ST_PALM=8, R_TIP=0.22, CAP=0.86, CLEAR_FROM=0.3)


def lift_dir(cam, Fr, d2, k_img):
    """画面の向き d2 を、接平面への持ち上げ（tangent_lift）と射線に直交する面の向き（img_dir3）の間（k_img = 後者の割合）へ。"""
    a = BB.tangent_lift(cam, Fr, d2)
    b = BB.img_dir3(cam, d2)
    v = unit((1 - k_img) * a + k_img * b)
    n = Fr[2]
    return unit(v - min(0.0, float(v @ n)) * n)   # 面の中へ入る成分は除く（接平面か、その上）


class Sky:
    """原画の空の検査（PaintSky の許しを変えた写し）と、主役波の後ろに隠れることの検査。"""

    def __init__(self, tol, ph):
        self.ps = CR.PaintSky(CC, tol)
        self.ph = ph
        self.cam = self.ps.cam

    def out(self, sp_, rad):
        return self.ps.count(sp_, rad)

    def claw_mask(self, dil=4):
        if getattr(self, "_cm", None) is None:
            inv = json.load(open(CC.INV, encoding="utf-8"))
            m = np.zeros((1080, 1920), np.uint8)
            for c in inv["claws"]:
                if c["zone"] != "main":
                    continue
                poly = c.get("region_polygon_ref_ds32") or c.get("region_polygon_ref")
                if poly:
                    cv2.fillPoly(m, [np.round(U.to_disp(np.array(poly, np.float64))).astype(np.int32)], 255)
            self._cm = cv2.dilate(m, np.ones((2 * dil + 1, 2 * dil + 1), np.uint8)) > 0
        return self._cm

    def out_claw(self, sp_, rad):
        """唇の櫛の検査：原画のカメラから見える点（主役波の後ろに隠れない点）が、原画の爪の領域（4 画素広げた）の外にある数。"""
        c = self.cam
        cm = self.claw_mask()
        pr = np.concatenate([sp_] + [sp_ + rad[:, None] * o[None, :] for o in (c.u, -c.u, c.r, -c.r)])
        q, z = c.project(pr)
        bad = 0
        for j in range(len(pr)):
            x, y = int(round(q[j, 0])), int(round(q[j, 1]))
            if z[j] <= 0 or not (0 <= x < 1920 and 0 <= y < 1080):
                continue
            if z[j] > self.ph.depth_at(q[j]) + 0.15:
                continue
            if not cm[y, x]:
                bad += 1
        return bad

    def visible_bad(self, sp_, rad):
        """扇の検査：点が主役波の後ろに隠れず、かつ原画の空に入る点の数（空でない所＝原画の爪の輪郭の内は許す）。"""
        c = self.cam
        pr = np.concatenate([sp_] + [sp_ + rad[:, None] * o[None, :] for o in (c.u, -c.u, c.r, -c.r)])
        q, z = c.project(pr)
        bad = 0
        for j in range(len(pr)):
            x, y = int(round(q[j, 0])), int(round(q[j, 1]))
            if z[j] <= 0 or not (0 <= x < 1920 and 0 <= y < 1080):
                continue
            if z[j] > self.ph.depth_at(q[j]) + 0.15:
                continue
            if self.ps.sky[y, x]:
                bad += 1
            elif self.ph.depth_at(q[j]) < np.inf:
                # 主役波の面の前に見える（面の上の白い指になる）：扇は頂の後ろの物なので許さない
                bad += 1
        return bad


def finger(B, hero, sky, eid, P0, D0, C0, n, L, r0, th, st, p_curl, clear=0.8, n_lift=(0.0, 0.25, 0.5), shrink=(1.0, 0.85, 0.72, 0.61, 0.52),
           mode="sky", r_tip=None, cap=None, clear_from=None):
    """1 本の指（spine_curl）。原画の空の検査（mode sky：許しの外へ出る点 0、mode hide：扇の検査）と面からの離れ（clear × 半径）。
    向きを面へ寝かせる（n_lift の負）・起こす、長さを縮める、の順に試し、通る最初の形を返す。通らなければ None。"""
    rt = P14["R_TIP"] if r_tip is None else r_tip
    cp = P14["CAP"] if cap is None else cap
    best = None
    for lk in shrink:
        for nl in n_lift:
            D = unit(D0 + nl * n)
            C = C0 - (C0 @ D) * D
            if np.linalg.norm(C) < 1e-6:
                C = np.cross(D, n)
            C = unit(C)
            sp_ = B.spine_curl(P0, D, C, L * lk, th, st, p=p_curl)
            rad = B.radius_profile(st, r0 * (0.6 + 0.4 * lk), rt * r0, cap=cp)
            if clear is None:
                marg = 1.0
            else:
                h = hero.height(sp_)
                k0 = max(2, int(round((P14["CLEAR_FROM"] if clear_from is None else clear_from) * st)))
                marg = float((h[k0:] - clear * rad[k0:]).min())
            v = sky.out(sp_, rad) if mode == "sky" else (sky.visible_bad(sp_, rad) if mode == "hide" else sky.out(sp_, rad) + sky.out_claw(sp_, rad))
            if marg > 0 and v == 0:
                return dict(sp=sp_, rad=rad, lk=lk, nl=nl, marg=marg)
            key = (-v, min(marg, 0.0))
            if best is None or key > best[0]:
                best = (key, dict(sp=sp_, rad=rad, lk=lk, nl=nl, marg=marg, v=v))
    return None


# ---------------------------------------------------------------- 1. 原画の爪の輪
def group_list(cls):
    """根元が近く（LC_GROUP_PX）向きがそろう（LC_GROUP_ANG）爪を 2〜LC_MAX 本の組に（長い順の貪欲法）。"""
    order = sorted(range(len(cls)), key=lambda i: -cls[i]["len2"])
    used = set()
    groups = []
    for i in order:
        if i in used:
            continue
        g = [i]
        used.add(i)
        di = unit(cls[i]["q"][min(len(cls[i]["q"]) - 1, 4)] - cls[i]["q"][0])
        cand = sorted([j for j in range(len(cls)) if j not in used], key=lambda j: np.linalg.norm(cls[j]["q"][0] - cls[i]["q"][0]))
        for j in cand:
            if len(g) >= P14["LC_MAX"] or np.linalg.norm(cls[j]["q"][0] - cls[i]["q"][0]) > P14["LC_GROUP_PX"]:
                break
            dj = unit(cls[j]["q"][min(len(cls[j]["q"]) - 1, 4)] - cls[j]["q"][0])
            if di @ dj < math.cos(math.radians(P14["LC_GROUP_ANG"])):
                continue
            g.append(j)
            used.add(j)
        groups.append([cls[k] for k in g])
    return groups


def make_list_claw(gid, B, hero, cam, sky, members, log):
    lead = members[0]
    hit = lead["hit"]
    r, c = hit["r"], hit["c"]
    Fr = hero.frame(np.array(r), np.array(c))
    e1, e2, n = Fr[0], Fr[1], Fr[2]
    P0 = hit["P"]
    pxm = lead["z0"] * 2.0 * cam.t / 1080.0
    # 組の広がり（先頭の根元から組の爪の中心線の点までの最大の距離、表示の画素）を、この深さの 1 画素の m で 3 次元の大きさに
    ext = max(P14["LC_EXT_MIN"], max(float(np.linalg.norm(m["q"] - lead["q"][0], axis=1).max()) for m in members)) * (1 + jit(gid, 1, 0.10)) * P14["LC_SCALE"]
    Lg = ext * pxm
    roots = np.array([m["q"][0] for m in members])
    rspan = float(np.linalg.norm(roots.mean(0) - lead["q"][0]))
    # 組の 2 次元の向き（各爪の始めの向きの長さ重み）
    d2s = [unit(m["q"][min(len(m["q"]) - 1, max(2, len(m["q"]) // 3))] - m["q"][0]) for m in members]
    d2 = unit(sum(d * m["len2"] for d, m in zip(d2s, members)))
    Ds = unit(lift_dir(cam, Fr, d2, P14["LC_IMG"]) + P14["LC_KAPPA"] * n)
    r_s = P14["LC_STEM_R"] * Lg
    Lst = max(P14["LC_STEM"] * ext, rspan + 0.15 * ext) * pxm
    ents = []
    # 茎：根元を少し沈め、まっすぐ（わずかに巻きの側へ）
    want0 = lead["curl"] * np.array([-d2[1], d2[0]])
    Cs = unit(lift_dir(cam, Fr, want0, P14["LC_IMG"]) - P14["LC_CURL_N"] * n)
    stem = finger(B, hero, sky, "L%s_s" % gid, P0 - 0.35 * r_s * n, Ds, Cs, n, Lst, r_s, 18.0, P14["ST_STEM"], 1.0, clear=0.3,
                  n_lift=(0.0, 0.3, 0.6, -0.2), r_tip=0.70, cap=1.0, clear_from=0.6)
    if stem is None:
        log.append(dict(id="L" + gid, dropped="stem_sky_or_clear", members=[m["id"] for m in members]))
        return []
    sp_s, rad_s = stem["sp"], stem["rad"]
    rad_s[-1] = 0.8 * rad_s[-2]
    nref_s = np.repeat(unit(n - 0.4 * Cs)[None, :], len(sp_s), 0)
    ents.append(B.build_entry("L%s_s" % gid, sp_s, nref_s, rad_s, rad_s * 0.92, CC.Q_FINGER, "rim",
                              root_disc=(P0 + 0.03 * n, n, P14["LC_DISC"] * r_s)))
    # 指：組の爪の数（1 本の組は 2 本にする）。向きは各爪の向き、角は LC_GAP 度以上あける
    Ts = unit(sp_s[-1] - sp_s[-2])
    tip = sp_s[-1] - 0.5 * r_s * Ts
    fm = list(members)
    if len(fm) == 1:
        m0 = dict(fm[0])
        a = math.radians(-lead["curl"] * 28.0)
        R2 = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
        m0["q"] = fm[0]["q"][0] + (fm[0]["q"] - fm[0]["q"][0]) @ R2.T
        m0["len2"] = fm[0]["len2"] * 0.75
        m0["id"] = fm[0]["id"] + "b"
        fm.append(m0)
    dirs = []
    for j, m in enumerate(fm):
        q = m["q"]
        dj2 = unit(q[min(len(q) - 1, max(2, len(q) // 3))] - q[0])
        Dj = unit(lift_dir(cam, Fr, dj2, P14["LC_IMG"]) + 0.6 * P14["LC_KAPPA"] * n)
        dirs.append(Dj)
    # 角の間をあける：茎の向きのまわりの角（n と茎に直交する向き）で並べ、隣と LC_GAP 度未満なら開く
    ax2 = unit(np.cross(Ts, n)) if np.linalg.norm(np.cross(Ts, n)) > 1e-6 else e2
    ang = [math.atan2(d @ ax2, d @ Ts) for d in dirs]
    order = np.argsort(ang)
    gap = math.radians(P14["LC_GAP"])
    angs = [ang[i] for i in order]
    for k in range(1, len(angs)):
        if angs[k] - angs[k - 1] < gap:
            angs[k] = angs[k - 1] + gap
    shift = 0.5 * ((angs[-1] - angs[0]) - (ang[order[-1]] - ang[order[0]]))
    angs = [a_ - shift for a_ in angs]
    fl = []
    for k, i in enumerate(order):
        m = fm[i]
        d = dirs[i]
        da = angs[k] - ang[i]
        Dj = unit(rot(d, unit(np.cross(Ts, ax2)), da))
        q = m["q"]
        dj2 = unit(q[min(len(q) - 1, max(2, len(q) // 3))] - q[0])
        want = m["curl"] * np.array([-dj2[1], dj2[0]])
        Cj = unit(lift_dir(cam, Fr, want, P14["LC_IMG"]) - P14["LC_CURL_N"] * n)
        rank = sorted(range(len(fm)), key=lambda t: -fm[t]["len2"]).index(i)
        Lf = float(np.clip(m["len2"], *P14["LC_F_PX"])) * pxm * P14["LC_FK"] * P14["LC_FOLLOW"][min(rank, 3)] * (1 + jit(m["id"], 2, 0.10))
        rf = P14["LC_FING_R"] * Lg * (1.0 if rank == 0 else 0.85)
        th = P14["LC_TH"] * (1 + jit(m["id"], 3, P14["LC_TH_J"]))
        side = (k - 0.5 * (len(order) - 1)) / max(1, len(order) - 1)
        st0 = tip + side * 0.9 * r_s * ax2
        f = finger(B, hero, sky, "L%s_f%d" % (gid, k), st0, Dj, Cj, n, Lf, rf, th, P14["ST_F"], P14["LC_P_CURL"], clear=0.6,
                   n_lift=(0.0, -0.25, 0.3))
        if f is None:
            fl.append(dict(dropped=True))
            continue
        ents.append(B.build_entry("L%s_f%d" % (gid, k), f["sp"], CR._nref_curl(B, f["sp"], n, 0.35), f["rad"], f["rad"] * 0.92, CC.Q_FINGER, "rim"))
        fl.append(dict(L=round(float(Lf * f["lk"]), 3), r=round(float(rf), 3), lk=f["lk"], nl=f["nl"], rank=rank))
    if len(ents) == 1:
        # 指が全部落ちた：茎だけの爪は棒に見えるので置かない
        log.append(dict(id="L" + gid, dropped="all_fingers", members=[m["id"] for m in members]))
        return []
    log.append(dict(id="L" + gid, kind="list_claw", members=[m["id"] for m in members], rc=[round(r, 2), round(c, 2)], Lg=round(Lg, 3), ext_px=round(ext, 1),
                    stem_lk=stem["lk"], fingers=fl))
    return ents


def _resample(q, n):
    seg = np.linalg.norm(np.diff(q, axis=0), axis=1)
    s = np.r_[0.0, np.cumsum(seg)]
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, q[:, k]) for k in range(q.shape[1])], -1)


def trace_spine(cam, q, P0, n, gamma, st, ph=None, rad=None, clear=0.7):
    """原画の爪の中心線 q（表示の画素）の各点の射線の上の 3 次元の背骨（st + 1 点）。原画のカメラからは中心線にそのまま重なる。
    ph（PaintHit）が無い時：根元の当たり P0 を通る面 Π（法線 m = −v と面の法線 n の間、γ = n の割合）との交わり。
    ph がある時（v14n、as01_trace_relief）：射線が主役波の面に当たり、その深さが根元の深さから TC_RANGE m 以内の点は、面の手前
    （(clear × 半径 ＋ 3 cm) / max(|n·d|, 0.3) だけ射線の上を手前へ）に置く（面に沿う厚い浮き彫りの指。面に沈まない）。
    当たらない点（原画の爪の輪郭の内で主役波の外）と、深さが大きく違う点（別の面の後ろを通る）は面 Π の上（手前の限りは守る）。"""
    qq = _resample(np.asarray(q, np.float64), st + 1)
    d = cam.ray(qq[:, 0], qq[:, 1])
    v = unit(P0 - cam.pos)
    m = unit((1 - gamma) * (-v) + gamma * n)
    t = ((P0 - cam.pos) @ m) / (d @ m)
    df = d @ cam.f
    z = t * df
    if ph is not None:
        z0 = float((P0 - cam.pos) @ cam.f)
        zs = np.array([ph.depth_at(p) for p in qq])
        rr = rad if rad is not None else np.zeros(len(z))
        ok = np.isfinite(zs) & (np.abs(zs - z0) < P14["TC_RANGE"])
        if ok.any():
            S = cam.pos[None, :] + (np.where(ok, zs, z0) / df)[:, None] * d
            _, j = ph.h.tree.query(S)
            nn = ph.h.Nf[ph.h.vi[j]]
            cosn = np.maximum(np.abs((nn * d).sum(1)), 0.3)
            zr = zs - (clear * rr + 0.03) / cosn * df
            z = np.where(ok, zr, np.minimum(z, np.where(np.isfinite(zs), zs - (clear * rr + 0.03) * 1.6, np.inf)))
            # 段差をならす（3 点の平均、面の手前の限りは守る）
            lim = np.where(ok, zr, np.inf)
            for _ in range(3):
                zz = z.copy()
                zz[1:-1] = (z[:-2] + z[1:-1] + z[2:]) / 3.0
                z = np.minimum(zz, lim)
    return cam.pos[None, :] + (z / df)[:, None] * d


def make_trace_claw(gid, B, hero, cam, ph, sky, members, log):
    """as01_list_claw（v14l）：原画の爪の一覧の組（根元が近く向きのそろう 2〜3 本）ごとに、1 つの爪＝細い茎 1 ＋ 鉤の指（組の爪の数）。
    形は原画の画面の線から作る：組の根元の後ろ（指の向きの逆へ TC_BODY_BACK × 組の広がり）を茎の根 qb とし、組の爪の中心線を qb のまわりに
    TC_SCALE 倍した線を、先頭の爪の根元の当たり P0 を通る面 Π（法線 = −v と面の法線の間）へ上げる（trace_spine。面より奥の所は射線の上で
    面の手前へ寄せる）。茎は qb から指の根元の中心への丸い管。原画の空の検査（許し 2 画素）に通らない指は根元の側へ縮め（0.6 倍まで）、
    それでも出る指は落とす。白の向きは巻きの外と見る向きの間（巻きの内と腹が水色の版）。v14d〜k の 1:1 の大きさ（原画の鉤 約 20 画素）は
    描画で米粒・砂利に見えた（縁の線が 1〜2 画素で鉤の巻きが読めない）ので、組の数を減らし（約 100）、1 つを大きくした。"""
    lead = members[0]
    hit = lead["hit"]
    P0 = hit["P"]
    r, c = hit["r"], hit["c"]
    Fr = hero.frame(np.array(r), np.array(c))
    n = Fr[2]
    pxm = lead["z0"] * 2.0 * cam.t / 1080.0
    st = P14["ST_F"]
    S = P14["TC_SCALE"] * (1 + jit(gid, 11, 0.10))
    ents = []
    fl = []
    mem = sorted(members, key=lambda m: -m["len2"])[:P14["TC_MAXF"]]
    d2 = unit(sum(unit(np.asarray(m["q"])[min(len(m["q"]) - 1, max(2, len(m["q"]) // 3))] - np.asarray(m["q"])[0]) * m["len2"] for m in mem))
    ext = max(14.0, max(float(np.linalg.norm(np.asarray(m["q"]) - np.asarray(lead["q"])[0], axis=1).max()) for m in mem))
    rq = np.array([np.asarray(m["q"])[0] for m in mem])
    qc = rq.mean(0)
    qb = qc - P14["TC_BODY_BACK"] * ext * d2
    rmax = 0.0
    tips = []
    for j, m in enumerate(mem):
        q = np.asarray(m["q"], np.float64)
        qS = qb + (q - qb) * S
        # 根元の半径：原画の爪の領域の平均の幅（面積 / 長さ、表示の画素）× TC_W × S（TC_W_PX × S の間）
        r0 = float(np.clip(P14["TC_W"] * m.get("w_px", 7.0), *P14["TC_W_PX"])) * S * pxm * (1.0 if j == 0 else 0.90) * (1 + jit(m["id"], 7, 0.08))
        got = None
        for sc in (1.0, 0.9, 0.8, 0.7, 0.6):
            qs = qS[0] + (qS - qS[0]) * sc
            s_ = np.linspace(0, 1, st + 1)
            rad = r0 * (0.8 + 0.2 * sc) * (P14["TC_TIP"] + (1 - P14["TC_TIP"]) * (1 - s_ ** P14["TC_TAPER"]))
            rad *= np.sqrt(np.clip(1 - np.clip((s_ - P14["CAP"]) / (1 - P14["CAP"]), 0, 1) ** 2, 0, 1))
            sp0 = trace_spine(cam, qs, P0, n, P14["TC_GAMMA"], st)
            sp_ = trace_spine(cam, qs, P0, n, P14["TC_GAMMA"], st, ph=ph, rad=rad, clear=P14["TC_CLEAR"])
            pulled = True
            if float(np.linalg.norm(np.diff(sp_, axis=0), axis=1).sum()) > P14["TC_STRETCH"] * float(np.linalg.norm(np.diff(sp0, axis=0), axis=1).sum()):
                sp_ = sp0
                pulled = False
            if sky.out(sp_, rad) == 0:
                got = (sp_, rad, sc, pulled)
                break
        if got is None:
            fl.append(dict(id=m["id"], dropped=True))
            continue
        sp_, rad, sc, pulled = got
        vv = unit_rows(cam.pos[None, :] - sp_)
        nr = unit_rows(CR._nref_curl(B, sp_, n, 0.0) + P14["TC_WHITE_VIEW"] * vv)
        ents.append(B.build_entry("T%s_f%d" % (gid, j), sp_, nr, rad, rad * 0.92, CC.Q_FINGER, "rim"))
        rmax = max(rmax, r0)
        tips.append(qs[0])
        fl.append(dict(id=m["id"], L=round(float(np.linalg.norm(np.diff(sp_, axis=0), axis=1).sum()), 3), r0=round(r0, 3), scale=sc, pulled=pulled))
    if not ents:
        log.append(dict(id="T" + gid, kind="list_claw", dropped="all", members=[m["id"] for m in mem]))
        return []
    # 茎（細い丸い管）：qb から指の根元の中心へ（根は面に沈める）
    qe = np.mean(tips, axis=0)
    sb = 8
    qline = qb[None, :] + np.linspace(0, 1, sb + 1)[:, None] * (qe - qb)[None, :]
    tt = np.linspace(0, 1, sb + 1)
    rs = rmax * (P14["TC_STEM_R0"] + (P14["TC_STEM_R1"] - P14["TC_STEM_R0"]) * tt)
    sp_s = trace_spine(cam, qline, P0, n, P14["TC_GAMMA"], sb, ph=ph, rad=rs, clear=0.4)
    sp_s0 = trace_spine(cam, qline, P0, n, P14["TC_GAMMA"], sb)
    # v14v：面に沿わせると射線の向きに長く伸びる茎（座席から棒に見えた）は作らない
    stretch_s = float(np.linalg.norm(np.diff(sp_s, axis=0), axis=1).sum()) / max(float(np.linalg.norm(np.diff(sp_s0, axis=0), axis=1).sum()), 1e-6)
    sp_s[0] = sp_s[0] - 0.8 * rs[0] * n
    stem = None
    if float(np.linalg.norm(qe - qb)) > 2.0 and stretch_s < P14["TC_STRETCH_BODY"] and sky.out(sp_s, rs) == 0:
        vv = unit_rows(cam.pos[None, :] - sp_s)
        ents.append(B.build_entry("T%s_s" % gid, sp_s, unit_rows(vv + 0.5 * n[None, :]), rs, rs * 0.95, CC.Q_FINGER, "rim",
                                  root_disc=(sp_s[0] + 0.02 * n, n, 1.3 * rs[0])))
        stem = round(float(np.linalg.norm(np.diff(sp_s, axis=0), axis=1).sum()), 3)
    # 泡の塊（v14p、as01_claw_foam）：茎の根の後ろから指の根元の少し先までの、面に沿う平たい白い板（上面 白、縁 水色の版、縁の線あり）。
    # 隣の爪の塊と重なって、原画の爪の輪の白い泡の帯になる（指が帯の縁から出る）。幅は組の根元の広がりと指の太さ、後ろの端と前の端は丸い。
    foam = None
    if P14["TC_FOAM"]:
        # v14u：泡は指の根元の並びを横切る三日月（背骨は組の横の向き side2、真ん中が後ろへ反る）。指は三日月の前の縁から出る（掌から指）
        side2 = np.array([-d2[1], d2[0]])
        rpx = rmax / pxm
        lat = np.array(tips) - qc
        spread = float(np.ptp(lat @ side2)) if len(tips) > 1 else 0.0
        half = 0.5 * spread + P14["TC_FOAM_SIDE"] * rpx
        sf = 10
        u = np.linspace(-1, 1, sf + 1)
        qfc = qc + (np.mean(tips, axis=0) - qc) * 0.5 - P14["TC_FOAM_BACK"] * ext * S * d2
        qlf = qfc[None, :] + (u * half)[:, None] * side2[None, :] - (P14["TC_FOAM_ARC"] * ext * S * (1 - u ** 2))[:, None] * d2[None, :]
        tf = 0.5 * (u + 1)
        rwf = P14["TC_FOAM_W"] * ext * S * pxm * np.sqrt(np.clip(1 - u ** 2, 0.0, 1)) ** 0.6
        rwf = np.maximum(rwf, 0.15 * rmax)
        rtf = np.minimum(rwf, P14["TC_FOAM_T"] * rmax)
        sp_f = trace_spine(cam, qlf, P0, n, P14["TC_GAMMA"], sf, ph=ph, rad=rtf, clear=0.6)
        sp_f0 = trace_spine(cam, qlf, P0, n, P14["TC_GAMMA"], sf)
        stretch_f = float(np.linalg.norm(np.diff(sp_f, axis=0), axis=1).sum()) / max(float(np.linalg.norm(np.diff(sp_f0, axis=0), axis=1).sum()), 1e-6)
        if stretch_f < P14["TC_STRETCH_BODY"] and sky.out(sp_f, rwf * 0.7) == 0:
            vv = unit_rows(cam.pos[None, :] - sp_f)
            ents.append(B.build_entry("U%s" % gid, sp_f, unit_rows(vv + 0.8 * n[None, :]), rwf, rtf, CC.Q_SHEET, "rim"))
            foam = dict(L=round(float(np.linalg.norm(np.diff(sp_f, axis=0), axis=1).sum()), 3), w=round(float(2 * rwf.max()), 3))
    log.append(dict(id="T" + gid, kind="list_claw", members=[m["id"] for m in mem], rc=[round(r, 2), round(c, 2)], scale=round(S, 3), fingers=fl,
                    stem=stem, foam=foam))
    return ents


# ---------------------------------------------------------------- 8. 唇の櫛（垂れる指）
def make_lip_hang(B, hero, sky, log):
    """唇の先の少し下（c_tip − 2 + LH_DC）から、巻きの続き（e1）と下（重さ）の間の向き（LH_ANG 度）へ出て、先が管の側へ少し巻く指。
    原画の空の検査（許し 2 画素）と、背骨の全部で唇の面から LH_CLEAR × 半径より離れることを、好みの順（垂れる角・根元の列・長さ）に試す。"""
    ents = []
    ct = CR.c_tip_rows(hero)
    r_lo, r_hi = P14["LH_ROWS"]
    rows = np.arange(r_lo, r_hi + 1)
    cc = ct[rows] - 2
    Pts = np.array([hero.point(np.array(float(r)), np.array(float(c))) for r, c in zip(rows, cc)])
    s = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(Pts, axis=0), axis=1))]
    gap = P14["LH_GAP"]
    down = np.array([0.0, -1.0, 0.0])
    k = 0
    for sp in np.arange(0.5 * gap, s[-1] - 0.3 * gap, gap):
        eid = "H%03d" % k
        k += 1
        jg = jit(eid, 9, 0.25) * gap
        r = float(np.interp(sp + jg, s, rows))
        c0 = float(np.interp(sp + jg, s, cc))
        a_, b_ = P14["LH_L"]
        L = (a_ + (b_ - a_) * (0.5 + 0.4 * math.sin(k * 1.7) + 0.1 * jit(eid, 1))) * (0.5 + 0.5 * min(CC.sm((r - r_lo) / 10.0), CC.sm((r_hi - r) / 10.0)))
        if L < 0.9:
            continue
        got = None
        for ang in P14["LH_ANG"]:
            for dcol in P14["LH_DC"]:
                c = c0 + dcol
                Fr = hero.frame(np.array(r), np.array(c))
                e1, e2, n = Fr[0], Fr[1], Fr[2]
                P0 = hero.point(np.array(r), np.array(c))
                r0 = P14["LH_RK"] * L
                fw = unit(e1 - (e1 @ down) * down)
                D0 = unit(math.cos(math.radians(ang)) * fw + math.sin(math.radians(ang)) * down + 0.08 * jit(eid, 2) * e2)
                C0 = unit(-fw + 0.3 * down)
                f = finger(B, hero, sky, eid, P0 - 0.3 * r0 * n, D0, C0, n, L, r0, P14["LH_TH"] * (1 + jit(eid, 3, 0.12)), P14["ST_F"], 1.6,
                           clear=P14["LH_CLEAR"], n_lift=(0.0, 0.2), shrink=(1.0, 0.85, 0.72), mode="claw")
                if f is not None:
                    got = (ang, dcol, c, P0, n, r0, f)
                    break
            if got:
                break
        if got is None:
            log.append(dict(id=eid, kind="lip_hang", dropped=True, rc=[round(r, 1), round(c0, 1)]))
            continue
        ang, dcol, c, P0, n, r0, f = got
        vs = unit_rows(unit_rows(CR.SEAT[None, :] - f["sp"]) + unit_rows(CR.PAINT[None, :] - f["sp"]))
        nr = unit_rows(0.6 * CR._nref_curl(B, f["sp"], n, 0.4) + 1.0 * vs)
        ents.append(B.build_entry(eid, f["sp"], nr, f["rad"], f["rad"] * 0.92, CC.Q_FINGER, "rim", root_disc=(P0 + 0.03 * n, n, 1.2 * r0)))
        log.append(dict(id=eid, kind="lip_hang", rc=[round(r, 1), round(c, 1)], ang=ang, L=round(L * f["lk"], 3), r0=round(r0, 3), lk=f["lk"],
                        marg=round(f["marg"], 3)))
    return ents


# ---------------------------------------------------------------- 3. 頂の稜の扇
def make_crest_fans(B, hero, sky, log):
    """頂の稜（行ごとの最も高い列 cy）の少し後ろ（cy − dc）に、背へ向く太い掌と、掌の先から稜に沿う横と背へ開く 3〜5 本の長い指の扇。
    指の向きは、頂の面から CF_ELEV 度起こし（頂の法線から 90 − CF_ELEV 度）、背の向きのまわりに ±CF_AZ 度開く。先は下へ巻く。
    原画のカメラから、点が主役波の後ろに隠れるか原画の爪の輪郭の内に入ること（Sky.visible_bad）を、起こしの大きい順・根元の列の順に試す。"""
    X = hero.X
    ents = []
    r_lo, r_hi = P14["CF_ROWS"]
    ytops = {r: float(X[r, hero.b0:hero.b1 + 1, 1].max()) for r in range(r_lo, r_hi + 1)}
    ymax = max(ytops.values())
    for r in range(r_lo, r_hi + 1, P14["CF_DR"]):
        r = int(np.clip(r + round(jit("CF%d" % r, 1, 3.0)), r_lo, r_hi))
        prof = X[r, hero.b0:hero.b1 + 1]
        cy = int(np.argmax(prof[:, 1])) + hero.b0
        peak = ytops[r] / ymax
        eid = "K%03d" % r
        if peak < P14["CF_PEAK_MIN"]:
            continue   # 低い稜（左の低い頂）には扇を置かない（背の坂に寝る脚のように見えた。v14i）
        nf = int(P14["CF_NF"][0] + round((P14["CF_NF"][1] - P14["CF_NF"][0]) * (0.5 + 0.5 * math.sin(r * 0.71))))
        Lbase = (P14["CF_FING_L"][0] + (P14["CF_FING_L"][1] - P14["CF_FING_L"][0]) * CC.sm((peak - 0.45) / 0.5)) * (1 + jit(eid, 2, 0.10))
        best = None
        for elev in P14["CF_ELEV"]:
            for dc in P14["CF_DC"]:
                rr, ccol = float(r), float(cy - dc)
                Fr = hero.frame(np.array(rr), np.array(ccol))
                e1, e2, n = Fr[0], Fr[1], Fr[2]
                P0 = hero.point(np.array(rr), np.array(ccol))
                back = unit(-e1 - (-e1 @ n) * n)
                side = unit(e2 - (e2 @ n) * n - (e2 @ back) * back)
                ea = math.radians(elev)
                Dp = unit(math.cos(ea) * back + math.sin(ea) * n)
                Cp = unit(-n - (-n @ Dp) * Dp)
                rp = P14["CF_PALM_R"] * (0.8 + 0.2 * peak)
                palm = finger(B, hero, sky, eid + "_p", P0 - 0.5 * rp * n, Dp, Cp, n, P14["CF_PALM_L"] * (0.85 + 0.15 * peak), rp, 20.0,
                              P14["ST_PALM"], 1.0, clear=None, n_lift=(0.0,), shrink=(1.0, 0.75), mode="hide", r_tip=0.55, cap=0.80)
                if palm is None:
                    continue
                pend = palm["sp"][-1]
                fings = []
                for j in range(nf):
                    u = -1.0 + 2.0 * j / max(1, nf - 1)
                    fid = "%s_f%d" % (eid, j)
                    az = math.radians(u * P14["CF_AZ"] + jit(fid, 1, 8.0))
                    h = unit(math.cos(az) * back + math.sin(az) * side)
                    ef = math.radians(elev + P14["CF_ELEV_F"] * (1 - abs(u)) + jit(fid, 5, 5.0))
                    Dj = unit(math.cos(ef) * h + math.sin(ef) * n)
                    Cj = unit(-n + 0.35 * h)
                    mid = 1.0 - 0.30 * abs(u)
                    Lf = Lbase * mid * (1 + jit(fid, 2, 0.15))
                    rf = P14["CF_FING_R"] * (Lf / 7.0) ** 0.5 * (1.0 - 0.12 * abs(u))
                    st0 = pend - 0.45 * rp * Dp + u * 0.5 * rp * side
                    f = finger(B, hero, sky, fid, st0, Dj, Cj, n, Lf, rf, P14["CF_TH"] * (1 + jit(fid, 3, 0.2)), P14["ST_F"], 1.7, clear=0.5,
                               n_lift=(0.0, -0.15), shrink=(1.0, 0.85, 0.72, 0.6), mode="hide", r_tip=P14["CF_R_TIP"])
                    if f is not None:
                        fings.append((fid, f, rf))
                score = len(fings) * (1.0 + elev / 90.0)
                if len(fings) >= 3 and (best is None or score > best[0]):
                    best = (score, elev, dc, P0, n, palm, rp, fings)
            if best is not None and best[1] == elev:
                break
        if best is None:
            log.append(dict(id=eid, kind="crest_fan", dropped=True, row=r))
            continue
        _, elev, dc, P0, n, palm, rp, fings = best
        nref_p = np.repeat(n[None, :], len(palm["sp"]), 0)
        rad_p = palm["rad"].copy()
        ents.append(B.build_entry(eid + "_p", palm["sp"], nref_p, rad_p, rad_p * 0.95, CC.Q_FINGER, "crown",
                                  root_disc=(P0 - 0.2 * rp * n, n, 1.1 * rp)))
        for fid, f, rf in fings:
            ents.append(B.build_entry(fid, f["sp"], unit_rows(CR._nref_curl(B, f["sp"], n, 0.5)), f["rad"], f["rad"] * 0.94, CC.Q_FINGER, "crown"))
        log.append(dict(id=eid, kind="crest_fan", row=r, dc=dc, elev=elev, fingers=len(fings), peak=round(peak, 3),
                        L=[round(float(np.linalg.norm(np.diff(f["sp"], axis=0), axis=1).sum()), 2) for _, f, _ in fings]))
    return ents


# ---------------------------------------------------------------- 2. 面の爪
Q_SHEET_INV = CC.Q_SHEET + np.pi    # 上面に q 5〜7（水色の版の段）が来る板（巻きの内の水色、縁の線あり）


def make_face_hook(cid, B, hero, cam, cl, log):
    hit = cl["hit"]
    Fr = hero.frame(np.array(hit["r"]), np.array(hit["c"]))
    q = cl["q"]
    d2 = unit(q[min(len(q) - 1, max(2, len(q) // 2))] - q[0])
    t0 = BB.tangent_lift(cam, Fr, d2)
    n = Fr[2]
    side = np.cross(n, t0)
    sp2 = np.array([side @ cam.r, -(side @ cam.u)])
    want = cl["curl"] * np.array([-d2[1], d2[0]])
    csgn = 1.0 if sp2 @ want > 0 else -1.0
    L = float(np.clip(P14["FH_K"] * cl["Ls"], P14["FH_MIN"], P14["FH_MAX"]))
    w = P14["FH_W"] * L
    th = BB.P["HOOK_T"]
    lift = 0.5 * th + BB.P["HOOK_LIFT"]
    pts, nrm, _ = B.walk_on_sheet(hero, hit["r"], hit["c"], t0, csgn, L, 18, P14["FH_TH"] * (1 + jit(cid, 1, 0.1)), P14["FH_STRAIGHT"])
    m = len(pts) - 1
    s = np.linspace(0, 1, m + 1)
    # 幅の広い根元（泡の塊）から巻く先へ細る 1 本の白い先
    rw = 0.5 * w * (1.0 - 0.62 * s ** 0.8) * np.sqrt(np.clip(1 - np.clip((s - 0.88) / 0.12, 0, 1) ** 2, 0, 1))
    rw[0] = 0.5 * w * 0.85
    ents = [B.build_entry("F%s" % cid, pts + nrm * lift, nrm, rw, np.minimum(0.5 * th, rw), CC.Q_SHEET, "hook")]
    # 巻きの内の水色（縁の線あり）：巻きの部分を中心の側へ寄せた、低い板
    i0 = int(0.40 * m)
    arc = pts[i0:]
    cen = arc.mean(0)
    inner = arc + P14["FH_INNER"] * (cen[None, :] - arc)
    wn = nrm[i0:]
    if len(inner) >= 5:
        mm = len(inner) - 1
        sw = np.linspace(0, 1, mm + 1)
        rwi = np.maximum(0.5 * 0.55 * w * np.sin(np.pi * np.clip(sw * 0.92 + 0.04, 0, 1)) ** 0.7, 0.02)
        ents.append(B.build_entry("V%s" % cid, inner + wn * (0.5 * th + 0.01), wn, rwi, np.full(mm + 1, 0.35 * th), Q_SHEET_INV, "hook_web"))
    log.append(dict(id="F" + cid, kind="face_hook", L=round(L, 3), w=round(w, 3), root_rc=[round(hit["r"], 2), round(hit["c"], 2)], curl=int(csgn)))
    return ents


def merge_face(cls, hero):
    """帯の外の爪：白い背（頂の列より後ろ）を除き、根元の近い物（FH_GROUP_PX）は長い方の 1 つに。"""
    keep = []
    X = hero.X
    for c in sorted(cls, key=lambda c: -c["len2"]):
        r = int(round(np.clip(c["hit"]["r"], 0, hero.R - 1)))
        prof = X[r, hero.b0:hero.b1 + 1]
        cy = int(np.argmax(prof[:, 1])) + hero.b0
        if c["hit"]["c"] < cy + 6:
            continue
        if any(np.linalg.norm(c["q"][0] - k["q"][0]) < P14["FH_GROUP_PX"] for k in keep):
            continue
        keep.append(c)
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=CC.OUTD + "/mesh_r1")
    ap.add_argument("--zones", default="list,lip,fan,hook")
    ap.add_argument("--preview", default="", help="numpy の下見の視点（painting,seat,…）。出力のフォルダーの preview/ へ")
    a = ap.parse_args()
    t0 = time.time()
    hero = CC.Hero(CC.load_hero())
    cam = CC.painting_cam()
    ph = BB.PaintHit(hero, cam)
    cls = BB.read_list(hero, cam, ph)
    inv = {c["id"]: c for c in json.load(open(CC.INV, encoding="utf-8"))["claws"]}
    for c in cls:
        poly = inv[c["id"]].get("region_polygon_ref_ds32") or inv[c["id"]].get("region_polygon_ref")
        if poly:
            A = float(cv2.contourArea(U.to_disp(np.array(poly, np.float64)).astype(np.float32)))
            c["w_px"] = A / max(c["len2"], 1.0)
    ct = CR.c_tip_rows(hero)

    def in_band(c):
        r, cc = c["hit"]["r"], c["hit"]["c"]
        k = int(round(np.clip(r, 0, hero.R - 1)))
        return CR.RIM["R0"] <= r <= CR.RIM["R1"] and ct[k] - 90 <= cc <= ct[k] + (8 if r < 127 else 25)
    z1 = [c for c in cls if in_band(c)]
    z2 = [c for c in cls if not in_band(c)]
    zones = set(a.zones.split(","))
    ents, log = [], []
    sky2 = Sky(P14["LC_SKY_TOL"], ph)
    if "list" in zones:
        groups = group_list(z1)
        for gi, g in enumerate(groups):
            ents += make_trace_claw("%03d" % gi, BB, hero, cam, ph, sky2, g, log)
        print("list groups", len(groups), "entries", len(ents), round(time.time() - t0, 1), "s", flush=True)
    if "lip" in zones:
        ents += make_lip_hang(BB, hero, Sky(P14["LH_SKY_TOL"], ph), log)
        print("lip", len(ents), round(time.time() - t0, 1), "s", flush=True)
    if "fan" in zones:
        ents += make_crest_fans(BB, hero, Sky(P14["CF_SKY_TOL"], ph), log)
        print("fans", len(ents), round(time.time() - t0, 1), "s", flush=True)
    if "hook" in zones:
        fz = merge_face(z2, hero)
        for c in fz:
            ents += make_face_hook(c["id"], BB, hero, cam, c, log)
        print("face hooks", len(fz), "of", len(z2), round(time.time() - t0, 1), "s", flush=True)
    BB.P["as01_v14"] = P14
    lay = BB.write_layout(a.out, ents)
    by_zone = {z: sum(1 for e in ents if e["zone"] == z) for z in ("rim", "rim_shadow", "crown", "hook", "hook_web")}
    rep = dict(version="v14", params=P14, counts=dict(entries=len(ents), vertices=lay["vertices"], triangles=lay["triangles"], by_zone=by_zone,
                                                      zone1_claws=len(z1), zone2_claws=len(z2),
                                                      list_claws=sum(1 for l in log if l.get("kind") == "list_claw" and not l.get("dropped")),
                                                      list_dropped=sum(1 for l in log if l.get("kind") == "list_claw" and l.get("dropped")),
                                                      lip_hang=sum(1 for l in log if l.get("kind") == "lip_hang" and not l.get("dropped")),
                                                      crest_fans=sum(1 for l in log if l.get("kind") == "crest_fan" and not l.get("dropped")),
                                                      face_hooks=sum(1 for l in log if l.get("kind") == "face_hook")),
               log=log, hero_pkg=os.path.relpath(CC.HERO, REPO).replace("\\", "/"), inventory=os.path.relpath(CC.INV, REPO).replace("\\", "/"),
               inventory_sha256=CC.sha(CC.INV), tool="Tools/GWWaveGen/as01/claws_v14.py", elapsed_s=round(time.time() - t0, 1))
    CC.jdump(os.path.join(a.out, "as01_claws_report.json"), rep)
    np.save(os.path.join(a.out, "as01_entries.npy"), np.array([dict(id=e["id"], V=e["V"], T=e["T"], up=e["up"], web=e["web"], zone=e["zone"]) for e in ents],
                                                              dtype=object), allow_pickle=True)
    print("AS01_CLAWS_V14_DONE", json.dumps(rep["counts"], ensure_ascii=False), rep["elapsed_s"], "s", flush=True)
    if a.preview:
        pd = os.path.join(a.out, "preview")
        os.makedirs(pd, exist_ok=True)
        for v in a.preview.split(","):
            cmv = cam if v == "painting" else CC.cam_view(v)
            CC.preview(cmv, hero, ents, os.path.join(pd, v + ".png"))
        print("preview", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
