# -*- coding: utf-8 -*-
"""仕上げ33 修正の回 1（計画 §5.3 の行 4、試し）：132・72 の細部込みの「へこみ」（描画の空の境界が包絡の真値に 4 px より届かない所）を、
頂の縁に付けた白い縁取りの帯（pl33f_rim_fill）で埋める試し（numpy）。

なぜ：132 の最大の塊 (947, 189) と 72 の (1084, 426)・(905, 412) などは、描画の空の境界が主役波の面の縁で、原画の輪郭はそこで爪の指先が作る。
近くに一覧の爪はほとんどない（132 の 4 px を超える真値の点から 4 px 以内の爪は C061 だけ）。
名前の付いた美術の誘導：
  - pl33f_rim_fill：t* の評価器の ID 画像の空の境界（主役波＋爪）から包絡の真値の点が 4 px より離れる点の塊（3 点以上、4 px でつながるもの）ごとに、
    真値の点とその最も近い描画の境界の点の間を埋める薄い帯（幅は両者の間 ＋ 内へ 1.5 px、奥行きは境界の内側 2 px の主役波の z バッファの面より 5 cm 手前、
    厚み 2 cm、上面（白）は原画のカメラへ向く）を作る。帯は主役波のシートの最も近い頂点 (行, 列) の座標系に結び付け、コマごとにその座標系で動かす。
    τ ≥ −0.25 s で幅 0 → 1 に育ち、その前は根元の点に潰す。id は R001〜、type R。
入力：--claws（既定 Unity/Build/Polish/33/fix01/claws）、--run（その爪で描いた t28 の組。既定 Unity/Build/Polish/33/fix01/r_fix01）。
出力：--out（既定 Unity/Build/Polish/33/fix01/try_rim）。
"""
import argparse
import json
import os
import shutil
import sys
import time

import numpy as np
from scipy.spatial import cKDTree

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/PaintingTruth")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33")
import pl33_common as Q  # noqa: E402
from pl33f_relief import taus_of  # noqa: E402

U = Q.U
RING = 8
K_STAR = 360
N_ST = 12


def sm(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--claws", default=REPO + "/Unity/Build/Polish/33/fix01/claws")
    ap.add_argument("--run", default=REPO + "/Unity/Build/Polish/33/fix01/r_fix01")
    ap.add_argument("--out", default=REPO + "/Unity/Build/Polish/33/fix01/try_rim")
    ap.add_argument("--items", default="132,72")
    a = ap.parse_args()
    t0 = time.time()
    cwd = os.getcwd()
    os.chdir(REPO)
    import truthlib as T
    import evaluate as EV
    truth = EV.Truth()
    ids = T.imread_rgb(os.path.join(a.run, "t28_claws", "t28", "render", "af28r01_class_ids.png"))
    reg = EV.render_regions_ids(truth, ids, {"classes": {"sky": [255, 255, 255]}})
    rp = T.boundary_points(reg["sky"], truth.spec, truth.fmap)
    Fm = truth.fam["sky_envelope"]
    os.chdir(cwd)
    hero = U.K.Pkg(Q.HERO)
    X0 = hero.world(0.0)
    R, C = X0.shape[:2]
    dep = Q.TStarDepth(X0)
    cam = dep.cam
    tree_rp = cKDTree(rp)
    tree_sheet = cKDTree(X0.reshape(-1, 3))
    hm = dep.zb > 0
    runs = []
    for tid in a.items.split(","):
        Tt = Fm["pts"][Fm["sel"][tid]]
        dtr, irp = tree_rp.query(Tt)
        bad = np.nonzero(dtr > 4.0)[0]
        if not len(bad):
            continue
        pts = Tt[bad]
        # 4 px でつながる塊
        tb = cKDTree(pts)
        lab = -np.ones(len(pts), int)
        k = 0
        for i in range(len(pts)):
            if lab[i] >= 0:
                continue
            stack = [i]; lab[i] = k
            while stack:
                j = stack.pop()
                for q in tb.query_ball_point(pts[j], 4.0):
                    if lab[q] < 0:
                        lab[q] = k; stack.append(q)
            k += 1
        for g in range(k):
            sel = np.nonzero(lab == g)[0]
            if len(sel) < 3:
                continue
            P = pts[sel]; Rn = rp[irp[bad[sel]]]
            # 主成分の向きに並べる
            c0 = P.mean(0)
            ax = np.linalg.svd(P - c0, full_matrices=False)[2][0]
            o = np.argsort((P - c0) @ ax)
            runs.append(dict(item=tid, truth=P[o], render=Rn[o]))
    print("dent runs", len(runs), [(r_["item"], len(r_["truth"])) for r_ in runs], flush=True)
    rims = []
    for rn in runs:
        Tp, Rp = rn["truth"], rn["render"]
        # 描画の境界から主役波の内側へ 2 px（真値と反対の向き）の画素の奥行き
        dirv = Tp - Rp
        dn = dirv / np.maximum(np.linalg.norm(dirv, axis=1, keepdims=True), 1e-9)
        inner = Rp - 2.0 * dn
        xi = np.clip(np.round(inner[:, 0]).astype(int), 0, 1919); yi = np.clip(np.round(inner[:, 1]).astype(int), 0, 1079)
        if not hm[yi, xi].all():
            # 主役波の画素でない所（爪だけの所）は近くの主役波の画素の奥行き
            pass
        zz = np.where(dep.zb[yi, xi] > 0, 1.0 / np.maximum(dep.zb[yi, xi], 1e-9), np.nan)
        if np.isnan(zz).all():
            continue
        zz = np.where(np.isnan(zz), np.nanmedian(zz), zz) - 0.05
        # 帯の内の縁（描画の境界の内 1.5 px）と外の縁（真値の点 ＋ 0.3 px）を、その奥行きの面へ戻す
        e_in = Rp - 1.5 * dn
        e_out = Tp + 0.3 * dn

        def back(pxy):
            d = cam.ray(pxy[:, 0], pxy[:, 1])
            s = zz / (d @ cam.f)
            return cam.pos[None, :] + s[:, None] * d
        A_in, A_out = back(e_in), back(e_out)
        # 弧長で N_ST に並べ直す
        Cn = 0.5 * (A_in + A_out)
        cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Cn, axis=0), axis=1))]
        if cum[-1] < 1e-3:
            continue
        u = np.linspace(0, cum[-1], N_ST)
        A_in = np.stack([np.interp(u, cum, A_in[:, k_]) for k_ in range(3)], 1)
        A_out = np.stack([np.interp(u, cum, A_out[:, k_]) for k_ in range(3)], 1)
        mid = 0.5 * (A_in + A_out)
        root_p = mid[0]
        _, iv = tree_sheet.query(root_p)
        r_, c_ = int(iv // C), int(iv % C)
        rims.append(dict(item=rn["item"], r=r_, c=c_, mid=mid, half=0.5 * (A_out - A_in), n_truth=int(len(Tp)),
                         xy=[round(float(Tp[:, 0].mean()), 1), round(float(Tp[:, 1].mean()), 1)]))
    print("rims", len(rims), flush=True)
    lay = json.load(open(os.path.join(a.claws, "ds33_claw_layout.json"), encoding="utf-8"))
    F, V0 = lay["frames"], lay["vertices"]
    taus = taus_of(F)
    NV = RING * N_ST + 11
    Yr = np.zeros((F, len(rims) * NV, 3), np.float32)
    phi = 2 * np.pi * np.arange(RING) / RING
    # t* の座標系での局所の値
    for rm in rims:
        Fr0 = U.frame_at(X0, float(rm["r"]), float(rm["c"]))
        rt = X0[rm["r"], rm["c"]]
        rm["mid_l"] = (rm["mid"] - rt) @ Fr0.T
        rm["half_l"] = rm["half"] @ Fr0.T
        tow = cam.pos[None, :] - rm["mid"]
        tow /= np.linalg.norm(tow, axis=1, keepdims=True)
        rm["tow_l"] = tow @ Fr0.T
    for f in range(F):
        tau = float(taus[f])
        Xs = X0 if abs(tau) < 1e-12 else hero.world(tau)
        g = sm((tau + 0.25) / 0.25)
        for i, rm in enumerate(rims):
            b = i * NV
            rt = Xs[rm["r"], rm["c"]]
            if g <= 1e-6:
                Yr[f, b:b + NV] = rt
                continue
            Fr = U.frame_at(Xs, float(rm["r"]), float(rm["c"]))
            mid = rt + rm["mid_l"] @ Fr
            half = (rm["half_l"] @ Fr) * g
            tow = rm["tow_l"] @ Fr
            ring = mid[:, None, :] + np.cos(phi)[None, :, None] * half[:, None, :] + np.sin(phi)[None, :, None] * (0.01 * tow)[:, None, :]
            Yr[f, b] = mid[0] - (mid[1] - mid[0]) * 0.3
            Yr[f, b + 1:b + 1 + N_ST * RING] = ring.reshape(-1, 3)
            Yr[f, b + 1 + N_ST * RING] = mid[-1] + (mid[-1] - mid[-2]) * 0.3
            Yr[f, b + 2 + N_ST * RING:b + NV] = Yr[f, b]
    os.makedirs(a.out, exist_ok=True)
    src = lambda k: os.path.join(a.claws, lay["files"][k]["file"])  # noqa: E731
    X = np.fromfile(src("frames"), dtype=np.float32).reshape(F, V0, 3)
    np.concatenate([X, Yr], axis=1).tofile(os.path.join(a.out, lay["files"]["frames"]["file"]))
    tris = [np.fromfile(src("tris"), dtype=np.int32).reshape(-1, 3)]
    att = [np.fromfile(src("tri_attr"), dtype=np.uint16).reshape(-1, 2)]
    nb = len(lay["claws"])
    for i, rm in enumerate(rims):
        Tt_, kd = Q.layout_tris(N_ST, V0 + i * NV)
        tris.append(Tt_.astype(np.int32))
        att.append(np.stack([np.full(len(kd), nb + i), kd], 1).astype(np.uint16))
        lay["claws"].append({"id": "R%03d" % (i + 1), "index": nb + i, "vert_offset": V0 + i * NV, "vert_count": NV, "stations": N_ST, "type": "R",
                             "pl33f_rim_item": rm["item"], "pl33f_rim_xy": rm["xy"]})
    np.concatenate(tris).tofile(os.path.join(a.out, lay["files"]["tris"]["file"]))
    np.concatenate(att).tofile(os.path.join(a.out, lay["files"]["tri_attr"]["file"]))
    sk = np.fromfile(src("skel"), dtype=np.float32).reshape(F, nb, 36)
    np.concatenate([sk, np.zeros((F, len(rims), 36), np.float32)], axis=1).tofile(os.path.join(a.out, lay["files"]["skel"]["file"]))
    for k in ("crown",):
        p = os.path.join(a.claws, "pl33_crown.json")
        if os.path.exists(p):
            shutil.copyfile(p, os.path.join(a.out, "pl33_crown.json"))
    lay["vertices"] = V0 + len(rims) * NV
    lay["triangles"] = int(sum(len(t) for t in tris))
    for k in ("frames", "tris", "tri_attr", "skel"):
        p = os.path.join(a.out, lay["files"][k]["file"])
        lay["files"][k]["sha256"] = Q.sha(p)
        lay["files"][k]["bytes"] = os.path.getsize(p)
    lay["pl33f_rim"] = {"note_ja": __doc__.strip().split("\n\n")[0], "rims": len(rims), "items": a.items, "run": os.path.relpath(a.run, REPO).replace("\\", "/")}
    json.dump(lay, open(os.path.join(a.out, "ds33_claw_layout.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("PL33F_RIM_DONE rims", len(rims), round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
