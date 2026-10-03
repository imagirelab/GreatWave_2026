# -*- coding: utf-8 -*-
"""美術の見本01（Q29）爪の部 v15：改善の回 2（2026-10-03）。回 1（v14、claws/mesh_r1）の「白い泡の塊から細い脚が出る虫・カニ」を直す（numpy。静止、t* だけ）。

回 1 の残り（assemble/README.md 第 10.4 節の 1）への答え：
  原画の爪の輪は「白い泡の塊（紙の地）が鱗のように重なり、その縁から鋭く巻く鉤（タロン）が垂れ、鉤の巻きの内と鱗の下が水色の版」で、
  白い泡は隣の泡とつながって 1 つの塊に見える（墨の線は鉤の縁だけ）。v14 は泡の三日月が小さく離れた島（藍の地の上の白い楕円）で、
  そこから原画の線を 1.4 倍した細い管の指と茎が出たので、虫の体と脚に見えた。
v15 の作り（区域 1 の原画の爪の輪＝as01_list_claw を替え、区域 2 の面の爪も同じ作りにする（FACE_LOBE）。頂の稜の扇・唇の櫛は v14 のまま）：
  a. 鱗の泡（U…、縁の線なし）：組ごとに、鉤の根元の後ろ（鉤の向きの逆）に、広く厚い泡の鱗を面に沿う浮き彫りで置く。前の縁は鉤の根元を覆い、
     真ん中が前へ張る扇形（スカラップ）。隣の鱗と重なって線なしでつながり、白い泡の帯・塊になる。鱗の縁の厚みは水色の版（鱗の下の陰）。
  b. 鉤（T…_f*、縁の線あり）：原画の鉤の中心線を、終わりの 60 % で巻きを強め（同じ巻きの向きへ TL_XCURL 度足す）、先を少し延ばし（TL_XLEN）、
     根元を太く（原画の鉤の平均の幅の TL_W 倍）、先を鋭く（TL_TIP）した管。断面は見る向きに広く奥へ薄い楕円（TL_FLAT）。拡大は鉤ごとの根元のまわり（TL_SCALE）。
  c. 茎（v14 の T…_s）はやめた（細い棒・節の輪に見えた）。
  d. 原画の空へ 2 画素より深く出る鉤は、拡大を 1.0〜0.5 倍に縮め、それでも出る時は原画の線そのもの（巻きを足さない、拡大 1、細め）へ戻す（鉤を落とさない）。
  既定の値は試しの v15i（Build/Polish/sample01/claws/mesh_v15i）＝ mesh_r2。試しの経緯は assemble/README.md 第 11 節。
  原画のカメラは置き場所・向き・検査（原画の空へ 2 画素より出ない）にだけ使い、色は投影しない（Q28）。参照モデルの OBJ は読まない（F13-1）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as01/claws_v15.py [--out …] [--zones list,lip,fan,hook] [--set 名前=値,…]
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
import claws_v14 as V14  # noqa: E402

U = CC.U
unit, jit, unit_rows = BB.unit, BB.jit, BB.unit_rows

P15 = dict(
    # b. 鉤（タロン）：拡大、根元の半径（原画の鉤の平均の幅 w_px の TL_W 倍、TL_W_PX の間、表示の画素）、先の細り、断面の平たさ、巻きの強め・先の延ばし
    TL_SCALE=1.9, TL_W=1.2, TL_W_PX=(4.5, 9.0), TL_TIP=0.05, TL_TAPER=0.85, TL_FLAT=0.72, TL_XCURL=70.0, TL_XFROM=0.40, TL_XLEN=0.18, TL_MAXTURN=210.0,
    TL_MAXF=3, TL_CLEAR=0.6, TL_WHITE_VIEW=0.6, TL_ABOVE=1.0,
    # a. 鱗の泡：横の余り（鉤の半径の倍）、奥行き（組の広がりの倍）、前の縁の越え、張り、厚み（鉤の根元の半径の倍）、縮めの段、面に沿わせた時の伸びの上限、
    #    端の丸み（(1 − u²) の冪）、断面の角（前の約 1/4 が水色の版）
    LB_ON=True, LB_SIDE=1.0, LB_DEPTH=0.30, LB_OVER=1.2, LB_ARC=0.35, LB_T=0.30, LB_MIN_PX=16.0, LB_SHRINK=(1.0, 0.8, 0.65), LB_STRETCH=2.2,
    LB_EXP=0.4, LB_Q=(40.0, 95.0, 135.0, 170.0, 205.0, 250.0, 300.0, 345.0),
    # 区域 2（面の爪）も「鱗の泡 ＋ 鉤」で作る（v14 の 1 本の巻く白い先 F… と水色の V… はやめる）
    FACE_LOBE=True)


def _angles(q):
    t = np.diff(q, axis=0)
    return np.unwrap(np.arctan2(t[:, 1], t[:, 0])), np.linalg.norm(t, axis=1)


def hook_line(q, curl, xcurl, xfrom, xlen, n=28, maxturn=None):
    """原画の鉤の中心線 q（表示の画素、根元 → 先）の巻きを強める：向きの角に、終わりの (1 − xfrom) で curl の向きへ xcurl 度を足し
    （smoothstep の 1.5 乗の割合）、先を xlen × 長さだけ同じ曲がりで延ばす。長さの配りは元の線のまま。"""
    qq = V14._resample(np.asarray(q, np.float64), n + 1)
    a, sl = _angles(qq)
    s = np.r_[0.0, np.cumsum(sl)][:-1] / max(sl.sum(), 1e-9)
    ramp = CC.sm((s - xfrom) / max(1.0 - xfrom, 1e-6)) ** 1.5
    if maxturn is not None:
        # 巻きの全体（根元から先までの向きの変わり、巻きの向き）が maxturn 度を越えない（輪にならない）よう、足す角を減らす
        tot = curl * (a[-1] - a[0])
        xcurl = float(np.clip(min(xcurl, math.degrees(math.radians(maxturn) - tot) / (1.0 + xlen)), 0.0, None))
    a2 = a + curl * math.radians(xcurl) * ramp
    # 先の延ばし：最後の曲がりの速さ（角 / 長さ）のまま、xlen × 長さ
    k = max(3, n // 5)
    rate = (a2[-1] - a2[-k]) / max(sl[-k:].sum(), 1e-9)
    if curl * rate < 0:
        rate = 0.0
    ne = max(2, int(round(n * xlen)))
    se = xlen * sl.sum() / ne
    ae = a2[-1] + rate * se * np.arange(1, ne + 1)
    A = np.r_[a2, ae]
    Ls = np.r_[sl, np.full(ne, se)]
    steps = np.stack([np.cos(A), np.sin(A)], 1) * Ls[:, None]
    return qq[0][None, :] + np.vstack([np.zeros(2), np.cumsum(steps, 0)])


def make_lobe_claw(gid, B, hero, cam, ph, sky, members, log):
    """原画の爪の組（根元が近く向きのそろう 1〜3 本）ごとに、鱗の泡 1 ＋ 巻きを強めた鉤（組の爪の数）。茎はない。"""
    P14 = V14.P14
    lead = members[0]
    hit = lead["hit"]
    P0 = hit["P"]
    r, c = hit["r"], hit["c"]
    Fr = hero.frame(np.array(r), np.array(c))
    n = Fr[2]
    pxm = lead["z0"] * 2.0 * cam.t / 1080.0
    st = P14["ST_F"]
    S = P15["TL_SCALE"] * (1 + jit(gid, 11, 0.08))
    ents, fl = [], []
    mem = sorted(members, key=lambda m: -m["len2"])[:P15["TL_MAXF"]]
    d2 = unit(sum(unit(np.asarray(m["q"])[min(len(m["q"]) - 1, max(2, len(m["q"]) // 3))] - np.asarray(m["q"])[0]) * m["len2"] for m in mem))
    ext = max(14.0, max(float(np.linalg.norm(np.asarray(m["q"]) - np.asarray(lead["q"])[0], axis=1).max()) for m in mem))
    rq = np.array([np.asarray(m["q"])[0] for m in mem])
    qc = rq.mean(0)
    rmax_px = 0.0
    roots = []
    for j, m in enumerate(mem):
        q = np.asarray(m["q"], np.float64)
        qh = hook_line(q, m["curl"], P15["TL_XCURL"] * (1 + jit(m["id"], 12, 0.15)), P15["TL_XFROM"], P15["TL_XLEN"], st, P15["TL_MAXTURN"])
        root = qc + (qh[0] - qc) * S
        qS = root + (qh - qh[0]) * S
        r_px = float(np.clip(P15["TL_W"] * m.get("w_px", 7.0), *P15["TL_W_PX"])) * S * (1.0 if j == 0 else 0.9) * (1 + jit(m["id"], 7, 0.08))
        r0 = r_px * pxm
        # 試す順：拡大 S の 1.0〜0.5 倍（巻きを強めた線）、それでも原画の空へ出る時は、原画の線そのもの（巻きを足さない、拡大 1.0、根元は原画の根元、細め）
        q1 = V14._resample(q, st + 1)
        tries = [(qS[0] + (qS - qS[0]) * sc, sc, 0.8 + 0.2 * sc) for sc in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5)]
        tries += [(q1, round(1.0 / S, 3), 0.65), (q1[0] + (q1 - q1[0]) * 0.8, round(0.8 / S, 3), 0.55)]
        got = None
        for qs, sc, wk in tries:
            s_ = np.linspace(0, 1, st + 1)
            rad = r0 * wk * (P15["TL_TIP"] + (1 - P15["TL_TIP"]) * (1 - s_) ** P15["TL_TAPER"])
            rad *= np.sqrt(np.clip(1 - np.clip((s_ - 0.93) / 0.07, 0, 1) ** 2, 0, 1))
            sp0 = V14.trace_spine(cam, qs, P0, n, P14["TC_GAMMA"], st)
            # 鉤は鱗の上に載る：面からの離れ ＝ TL_CLEAR × 半径 ＋ TL_ABOVE × 鱗の厚みの上限（LB_T × 根元の半径）
            sp_ = V14.trace_spine(cam, qs, P0, n, P14["TC_GAMMA"], st, ph=ph, rad=rad + P15["TL_ABOVE"] * P15["LB_T"] * r0 / P15["TL_CLEAR"],
                                  clear=P15["TL_CLEAR"])
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
        nr = unit_rows(CR._nref_curl(B, sp_, n, 0.0) + P15["TL_WHITE_VIEW"] * vv)
        # 断面：見る向き（白の向き N）に薄く、幅（Bv）に広い楕円
        ents.append(B.build_entry("T%s_f%d" % (gid, j), sp_, nr, rad, rad * P15["TL_FLAT"], CC.Q_FINGER, "rim"))
        rmax_px = max(rmax_px, r_px)
        roots.append(qs[0])
        fl.append(dict(id=m["id"], L=round(float(np.linalg.norm(np.diff(sp_, axis=0), axis=1).sum()), 3), r0=round(r0, 3), scale=sc, pulled=pulled))
    if not ents:
        log.append(dict(id="T" + gid, kind="list_claw", dropped="all", members=[m["id"] for m in mem]))
        return []
    lobe = None
    if P15["LB_ON"]:
        side2 = np.array([-d2[1], d2[0]])
        lat = np.array(roots) - qc
        spread = float(np.ptp(lat @ side2)) if len(roots) > 1 else 0.0
        why = []
        for k_, shr in enumerate(P15["LB_SHRINK"]):
            half = (0.5 * spread + P15["LB_SIDE"] * rmax_px + 0.25 * ext * S) * shr
            depth = max(P15["LB_MIN_PX"], P15["LB_DEPTH"] * ext * S) * shr
            # 前の縁（中心で 前へ LB_ARC × depth 張る）が鉤の根元を LB_OVER × 鉤の半径 だけ越える
            qfront = np.mean(roots, axis=0) + P15["LB_OVER"] * rmax_px * d2
            qcen = qfront - depth * d2 - P15["LB_ARC"] * depth * d2
            sf = 12
            u = np.linspace(-1, 1, sf + 1)
            qlf = qcen[None, :] + (u * half)[:, None] * side2[None, :] + (P15["LB_ARC"] * depth * (1 - u ** 2))[:, None] * d2[None, :]
            rw = depth * pxm * np.clip(1 - u ** 2, 0.0, 1) ** P15["LB_EXP"]
            rw = np.maximum(rw, 0.18 * depth * pxm)
            rt = np.minimum(rw, P15["LB_T"] * rmax_px * pxm)
            sp_f = V14.trace_spine(cam, qlf, P0, n, P14["TC_GAMMA"], sf, ph=ph, rad=rt, clear=0.6)
            sp_f0 = V14.trace_spine(cam, qlf, P0, n, P14["TC_GAMMA"], sf)
            stretch = float(np.linalg.norm(np.diff(sp_f, axis=0), axis=1).sum()) / max(float(np.linalg.norm(np.diff(sp_f0, axis=0), axis=1).sum()), 1e-6)
            so = sky.out(sp_f, rw)
            why.append(dict(shrink=shr, stretch=round(stretch, 2), sky=so))
            if stretch < P15["LB_STRETCH"] and so == 0:
                vv = unit_rows(cam.pos[None, :] - sp_f)
                nref = unit_rows(vv + 0.8 * n[None, :])
                # 鱗の前（鉤の側、画面の d2）の縁の約 1/4 を水色の版（鱗の下の陰）にする断面の角 LB_Q。輪の枠の Bv（N × T）が前を向くよう背骨の向きを選ぶ
                front = BB.img_dir3(cam, d2)
                Tm = unit(sp_f[sf // 2 + 1] - sp_f[sf // 2 - 1])
                if float(np.cross(unit(nref[sf // 2] - (nref[sf // 2] @ Tm) * Tm), Tm) @ front) < 0:
                    sp_f, nref, rw, rt = sp_f[::-1].copy(), nref[::-1].copy(), rw[::-1].copy(), rt[::-1].copy()
                ents.append(B.build_entry("U%s" % gid, sp_f, nref, rw, rt, np.radians(P15["LB_Q"]), "rim"))
                lobe = dict(L=round(float(np.linalg.norm(np.diff(sp_f, axis=0), axis=1).sum()), 3), depth_m=round(float(2 * rw.max()), 3), shrink=shr)
                break
    log.append(dict(id="T" + gid, kind="list_claw", members=[m["id"] for m in mem], rc=[round(r, 2), round(c, 2)], scale=round(S, 3), fingers=fl, lobe=lobe,
                    lobe_tries=None if lobe else (why if P15["LB_ON"] else None)))
    return ents


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=CC.OUTD + "/mesh_r2")
    ap.add_argument("--zones", default="list,lip,fan,hook")
    ap.add_argument("--set", default="", help="P15 の値を替える（名前=値 を空白で区切る。試しの並び用）")
    ap.add_argument("--preview", default="")
    a = ap.parse_args()
    for kv in a.set.split():
        k, v = kv.split("=")
        P15[k] = type(P15[k])(eval(v)) if not isinstance(P15[k], tuple) else tuple(eval(v))
    t0 = time.time()
    P14 = V14.P14
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
    sky2 = V14.Sky(P14["LC_SKY_TOL"], ph)
    if "list" in zones:
        groups = V14.group_list(z1)
        for gi, g in enumerate(groups):
            ents += make_lobe_claw("%03d" % gi, BB, hero, cam, ph, sky2, g, log)
        print("list groups", len(groups), "entries", len(ents), round(time.time() - t0, 1), "s", flush=True)
    if "lip" in zones:
        ents += V14.make_lip_hang(BB, hero, V14.Sky(P14["LH_SKY_TOL"], ph), log)
    if "fan" in zones:
        ents += V14.make_crest_fans(BB, hero, V14.Sky(P14["CF_SKY_TOL"], ph), log)
        print("fans", len(ents), round(time.time() - t0, 1), "s", flush=True)
    if "hook" in zones and P15["FACE_LOBE"]:
        # 面の爪も同じ「鱗の泡 ＋ 鉤」で（白い背の上の物は除く。v14 の merge_face の決まり、ただし根元の近い物は組にまとめる）
        X = hero.X
        keep = []
        for c in z2:
            rr = int(round(np.clip(c["hit"]["r"], 0, hero.R - 1)))
            cy = int(np.argmax(X[rr, hero.b0:hero.b1 + 1][:, 1])) + hero.b0
            if c["hit"]["c"] >= cy + 6:
                keep.append(c)
        for gi, g in enumerate(V14.group_list(keep)):
            ents += make_lobe_claw("F%02d" % gi, BB, hero, cam, ph, sky2, g, log)
    elif "hook" in zones:
        fz = V14.merge_face(z2, hero)
        for c in fz:
            ents += V14.make_face_hook(c["id"], BB, hero, cam, c, log)
    BB.P["as01_v14"] = P14
    BB.P["as01_v15"] = P15
    lay = BB.write_layout(a.out, ents)
    by_zone = {z: sum(1 for e in ents if e["zone"] == z) for z in ("rim", "rim_shadow", "crown", "hook", "hook_web")}
    rep = dict(version="v15", params=P15, params_v14=P14,
               counts=dict(entries=len(ents), vertices=lay["vertices"], triangles=lay["triangles"], by_zone=by_zone, zone1_claws=len(z1), zone2_claws=len(z2),
                           list_claws=sum(1 for l in log if l.get("kind") == "list_claw" and not l.get("dropped")),
                           list_dropped=sum(1 for l in log if l.get("kind") == "list_claw" and l.get("dropped")),
                           talons=sum(1 for l in log if l.get("kind") == "list_claw" for f in l.get("fingers", []) if not f.get("dropped")),
                           talons_dropped=sum(1 for l in log if l.get("kind") == "list_claw" for f in l.get("fingers", []) if f.get("dropped")),
                           lobes=sum(1 for l in log if l.get("kind") == "list_claw" and l.get("lobe")),
                           lip_hang=sum(1 for l in log if l.get("kind") == "lip_hang" and not l.get("dropped")),
                           crest_fans=sum(1 for l in log if l.get("kind") == "crest_fan" and not l.get("dropped")),
                           face_hooks=sum(1 for l in log if l.get("kind") == "face_hook")),
               log=log, hero_pkg=os.path.relpath(CC.HERO, REPO).replace("\\", "/"), inventory=os.path.relpath(CC.INV, REPO).replace("\\", "/"),
               inventory_sha256=CC.sha(CC.INV), tool="Tools/GWWaveGen/as01/claws_v15.py", elapsed_s=round(time.time() - t0, 1))
    CC.jdump(os.path.join(a.out, "as01_claws_report.json"), rep)
    print("AS01_CLAWS_V15_DONE", json.dumps(rep["counts"], ensure_ascii=False), rep["elapsed_s"], "s", flush=True)
    if a.preview:
        pd = os.path.join(a.out, "preview")
        os.makedirs(pd, exist_ok=True)
        for v in a.preview.split(","):
            cmv = cam if v == "painting" else CC.cam_view(v)
            CC.preview(cmv, hero, ents, os.path.join(pd, v + ".png"))


if __name__ == "__main__":
    main()
