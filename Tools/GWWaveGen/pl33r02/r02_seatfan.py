# -*- coding: utf-8 -*-
"""仕上げ33修正02：座席から見た指の向きの揃い（箒か扇か）と、指の 3D の形（長さ・巻き・立ち）を数える（numpy・OpenCV。記録の補助）。

  - 座席のカメラ（場面 DS39_Paper の「DS27 seat」と同じ：位置 (3.9544, 1.8323, −15.0308)、回転の四元数 (−0.49319, −0.29382, −0.18149, 0.79843)、
    縦の視野 80°、1920×1080）へ、t* のコマの指（C…）の背骨（輪の中心＝頂点 2 と 6 の中点と先）を写す。
  - 座席の画像で見える指：描画の作品のまま（asis）と爪なし（clawfree）の差（最大のチャンネル > 12）を 5 px 広げた所に、先の画素が入る指。
  - 揃い：見える指の、根元 → 先の画面の向きの単位ベクトルの平均の長さ R（1 ＝ 全部が同じ向き＝箒、0 ＝ ばらばら＝扇）と、向きの円の標準偏差（度）。
    長さで重みを付けた R_w（長い指ほど目立つので）。画面の長さの最大と p90（孤立した長い棒）。
  - 3D：指の背骨の長さ、弦と弧の比（巻き。1 ＝ 真っ直ぐ）、シートからの最大の高さ（中央値）、原画の射線とのなす角（背骨の弦と、根元から原画のカメラへの向き）の中央値。
使い方：py -3.10 -B Tools/GWWaveGen/pl33r02/r02_seatfan.py --claws <爪の並び> --run <描画> [--claws … --run …] --out <json>
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33r01")
import sweep_build as SB  # noqa: E402

U = SB.U
K_STAR = 360


def quat_rot(q, v):
    x, y, z, w = q
    u = np.array([x, y, z])
    v = np.asarray(v, np.float64)
    return 2.0 * (u @ v) * u + (w * w - u @ u) * v + 2.0 * w * np.cross(u, v)


class SeatCam:
    def __init__(self, W=1920, H=1080):
        self.pos = np.array([3.9544, 1.8323, -15.0308])
        q = (-0.49319124, -0.29382184, -0.18149406, 0.7984304)
        self.r, self.u, self.f = quat_rot(q, [1, 0, 0]), quat_rot(q, [0, 1, 0]), quat_rot(q, [0, 0, 1])
        self.t = np.tan(np.radians(40.0))
        self.W, self.H = W, H
        self.aspect = W / H

    def project(self, P):
        d = np.asarray(P, np.float64) - self.pos
        cx, cy, cz = d @ self.r, d @ self.u, d @ self.f
        vx = 0.5 + 0.5 * (cx / cz) / (self.t * self.aspect)
        vy = 0.5 + 0.5 * (cy / cz) / self.t
        return np.stack([vx * self.W - 0.5, (1.0 - vy) * self.H - 0.5], -1), cz


def spines(claws_dir):
    lay = json.load(open(os.path.join(claws_dir, "ds33_claw_layout.json"), encoding="utf-8"))
    F, V = lay["frames"], lay["vertices"]
    Y = np.memmap(os.path.join(claws_dir, lay["files"]["frames"]["file"]), dtype=np.float32, mode="r", shape=(F, V, 3))
    out = {}
    for c in lay["claws"]:
        if not c["id"].startswith("C"):
            continue
        o, n = c["vert_offset"], c["stations"]
        blk = np.asarray(Y[K_STAR, o:o + c["vert_count"]], np.float64)
        rings = blk[1:1 + n * 8].reshape(n, 8, 3)
        sp = np.concatenate([0.5 * (rings[:, 2] + rings[:, 6]), blk[1 + n * 8][None]], 0)
        sp = np.concatenate([blk[:1], sp], 0)
        if np.linalg.norm(sp[-1] - sp[0]) < 1e-3:
            continue
        out[c["id"]] = sp
    return out


def analyse(claws_dir, run):
    cam = SeatCam()
    spec = json.load(open(U.TRUTH, encoding="utf-8"))
    pc = U.CamWH(spec, 1920, 1080)
    X0 = SB.U.K.Pkg(SB.HERO).world(0.0)
    sheet = SB.Sheet(X0)
    a = cv2.imread(os.path.join(run, "views", "seat_t120_asis.png")).astype(int)
    f = cv2.imread(os.path.join(run, "views", "seat_t120_clawfree.png")).astype(int)
    m = (np.abs(a - f).max(2) > 12).astype(np.uint8)
    m = cv2.dilate(m, np.ones((5, 5), np.uint8)).astype(bool)
    sps = spines(claws_dir)
    dirs, lens, rows = [], [], []
    for cid, sp in sps.items():
        q, z = cam.project(sp)
        if (z <= 0).any():
            continue
        tip = np.round(q[-1]).astype(int)
        if not (0 <= tip[0] < 1920 and 0 <= tip[1] < 1080) or not m[tip[1], tip[0]]:
            continue
        d = q[-1] - q[0]
        L = float(np.linalg.norm(d))
        if L < 3:
            continue
        dirs.append(d / L)
        lens.append(L)
        arc = float(np.linalg.norm(np.diff(sp, axis=0), axis=1).sum())
        chord = float(np.linalg.norm(sp[-1] - sp[0]))
        rdir = pc.pos - sp[0]
        rdir /= np.linalg.norm(rdir)
        ang = float(np.degrees(np.arccos(np.clip(((sp[-1] - sp[0]) / max(chord, 1e-9)) @ rdir, -1, 1))))
        rows.append(dict(id=cid, seat_len_px=round(L, 1), arc_m=round(arc, 3), straight=round(chord / max(arc, 1e-9), 3),
                         h_max=round(float(sheet.height(sp).max()), 3), ray_angle_deg=round(ang, 1)))
    D = np.array(dirs)
    Lw = np.array(lens)
    R = float(np.linalg.norm(D.mean(0)))
    Rw = float(np.linalg.norm((D * Lw[:, None]).sum(0)) / Lw.sum())
    circ_std = float(np.degrees(np.sqrt(-2.0 * np.log(max(R, 1e-9)))))
    # 長い指（画面の長さの上位 20%）だけの揃い
    big = Lw >= np.percentile(Lw, 80)
    Rb = float(np.linalg.norm(D[big].mean(0)))
    arcs = np.array([r["arc_m"] for r in rows])
    st = np.array([r["straight"] for r in rows])
    hm = np.array([r["h_max"] for r in rows])
    ra = np.array([r["ray_angle_deg"] for r in rows])
    return dict(visible_fingers=len(rows), R=round(R, 3), R_len_weighted=round(Rw, 3), R_top20pct_long=round(Rb, 3), circ_std_deg=round(circ_std, 1),
                seat_len_px_p50=round(float(np.median(Lw)), 1), seat_len_px_p90=round(float(np.percentile(Lw, 90)), 1), seat_len_px_max=round(float(Lw.max()), 1),
                arc_m_p50=round(float(np.median(arcs)), 3), arc_m_max=round(float(arcs.max()), 3), straight_p50=round(float(np.median(st)), 3),
                h_max_p50=round(float(np.median(hm)), 3), ray_angle_p50=round(float(np.median(ra)), 1), fingers=rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--claws", action="append", required=True)
    ap.add_argument("--run", action="append", required=True)
    ap.add_argument("--name", action="append", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    res = {}
    for i, (c, r) in enumerate(zip(a.claws, a.run)):
        nm = a.name[i] if a.name else os.path.basename(os.path.normpath(r))
        res[nm] = analyse(c, r)
        print(nm, json.dumps({k: v for k, v in res[nm].items() if k != "fingers"}, ensure_ascii=False))
    if a.out:
        json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
