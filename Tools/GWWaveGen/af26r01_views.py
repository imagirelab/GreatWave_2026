# -*- coding: utf-8 -*-
"""番号26修正01：Unity で描く機位を決めて Unity/Build/ArtFirst/26修正01/af26r01_views.json に書く（AF26R01KStar.cs が読む）。

座席 v1（Tools/GWContext/seat_v1.json、番号27修正01）の目から、gw_wavegen v2 の K*（kstar_a45_meta.json・_rows.npz）の唇へ向く機位を、
同じ規則（座席の位置は変えず、注視点だけを新しい唇で取り直す）で作る。側面・背面・真上は CP1・番号26 と同じ機位。
variants：r01 = 26修正01 の K*、cp1 = 番号26（CP1）の K* 45°、_waveonly = 主役波・空・参照海面だけの確認図。

使い方（リポジトリ根で）: py -3.10 Tools/GWWaveGen/af26r01_views.py
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth"))
import truthlib as T  # noqa: E402

BUILD = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01")
KDIR = os.path.join(BUILD, "kstar")


def direction(yaw_from, elev_deg):
    """水平の向き yaw_from（x, z）と仰角から、単位ベクトル。"""
    h = np.array([yaw_from[0], 0.0, yaw_from[1]], float)
    h /= np.linalg.norm(h)
    e = math.radians(elev_deg)
    return h * math.cos(e) + np.array([0.0, 1.0, 0.0]) * math.sin(e)


def main():
    meta = T.load_json(os.path.join(KDIR, "kstar_a45_meta.json"))
    rows = np.load(os.path.join(KDIR, "kstar_a45_rows.npz"))
    seat = T.load_json(os.path.join(REPO, "Tools", "GWContext", "seat_v1.json"))
    eye = np.array(seat["seat"]["eye_world"], float)
    fov = float(seat["view"]["vertical_fov_deg"])
    fr = meta["frame"]
    e = np.array(fr["e_crest"]); t = np.array(fr["t_travel"]); O0 = np.array(fr["section_origin_world"])
    c, A, Y = rows["c"], rows["A"], rows["Y"]
    idx = meta["profile"]["index"]
    jt, jk = idx["j_top"], idx["j_corner"]

    def world(v, j):
        return O0 + c[v] * e + A[v, j] * t + np.array([0.0, Y[v, j], 0.0])

    rel = meta["seat_v1_relation_record_only"]
    lip_near = np.array(rel["nearest_lip_point_above_3m"]["world"], float)
    az_lip = (lip_near - eye)[[0, 2]]
    # 波峰線の手前（左）と奥（右）の目印：c = −10 m と c = +3 m の行の頂
    vL = int(np.argmin(np.abs(c + 10.0)))
    vR = int(np.argmin(np.abs(c - 3.0)))
    crL, crR = world(vL, jt), world(vR, jt)
    views = []

    def add(key, eye_, target, fov_, variants):
        views.append({"key": key, "eye": [round(float(x), 4) for x in eye_], "target": [round(float(x), 4) for x in target],
                      "fov": float(fov_), "variants": variants})
    both = ["r01", "cp1"]
    add("painting", [0, 3, -62], [-2.5, 9.7, 4], 26.0, both)
    add("seat_lip", eye, lip_near, fov, ["r01", "cp1", "r01_waveonly"])
    add("seat_up", eye, eye + 10 * direction(az_lip, 55.0), fov, ["r01", "cp1", "r01_waveonly"])
    add("seat_low", eye, eye + 10 * direction(az_lip, 20.0), fov, both)
    add("seat_left", eye, eye + 10 * direction((crL - eye)[[0, 2]], 30.0), fov, both)
    add("seat_right", eye, eye + 10 * direction((crR - eye)[[0, 2]], 30.0), fov, both)
    add("side_left", [-90, 30, -14], [-5, 8, -3], 45.0, ["r01", "cp1", "r01_waveonly", "cp1_waveonly"])
    add("side_right", [53, 22, -2], [-1, 7, 0], 60.0, ["r01_waveonly", "cp1_waveonly"])
    add("back", [-45, 30, 60], [-5, 8, -3], 50.0, ["r01", "cp1", "r01_waveonly", "cp1_waveonly"])
    add("top", [-5, 120, -10], [-5, 0, -9.9], 60.0, ["r01_waveonly", "cp1_waveonly"])
    # 正面の斜め上（波の進む側、右手前の高い所）から波峰線の全体を見る
    front_eye = O0 + 42.0 * t - 6.0 * e + np.array([0.0, 14.0, 0.0])
    front_tgt = O0 - 6.0 * e + np.array([0.0, 9.0, 0.0])
    add("front", front_eye, front_tgt, 55.0, ["r01_waveonly", "cp1_waveonly"])
    # 管の口：c ≈ −1.5 m の行で、内壁（高さ 5 m）から 9 m 前・高さ 4 m の点から、波峰線に沿って手前の肩（−e）と奥（+e）を見る（管の内側と唇の下面）
    v0 = int(np.argmin(np.abs(c + 1.5)))
    jf = idx["j_facebot"]
    wall = np.array([(A[v0, j], Y[v0, j]) for j in range(jk, jf + 1)])
    a_wall5 = float(np.interp(5.0, wall[::-1, 1], wall[::-1, 0])) if wall[:, 1].min() < 5.0 < wall[:, 1].max() else float(wall[:, 0].max())
    tube_eye = O0 + c[v0] * e + (a_wall5 + 9.0) * t + np.array([0.0, 4.0, 0.0])
    add("tube_near", tube_eye, tube_eye - 20.0 * e - 6.0 * t + np.array([0.0, 5.0, 0.0]), 80.0, ["r01_waveonly", "cp1_waveonly"])
    add("tube_far", tube_eye, tube_eye + 20.0 * e - 6.0 * t + np.array([0.0, 5.0, 0.0]), 80.0, ["r01_waveonly", "cp1_waveonly"])
    # 回り込みの動画用（主役波・空・参照海面だけ）：波の中心のまわりを半径 70 m、高さ 24 m で 1 周（96 枚）
    ctr = O0 - 5.0 * e + np.array([0.0, 8.0, 0.0])
    n_orbit = 96
    for i in range(n_orbit):
        th = 2.0 * math.pi * i / n_orbit
        # 原画視点の側（−h）から始めて、上から見て時計回り
        d0 = -np.array(fr["h"], float)
        d1 = np.array(fr["ea"], float)
        dirh = math.cos(th) * d0 + math.sin(th) * d1
        add("orbit_%03d" % i, ctr + 70.0 * dirh + np.array([0.0, 16.0, 0.0]), ctr, 40.0, ["r01_waveonly"])
    out = {"schema": "GreatWave.AF26R01.views/1", "number": "26修正01", "seat_eye_world": eye.tolist(),
           "note_ja": "機位は Unity のワールド座標（m）。座席 v1 の目の位置は番号27修正01 のまま。注視点は 26修正01 の K* の唇（目より 3 m 以上高い唇の点で座席に水平で最も近い点）で取り直した。",
           "kstar_meta_sha256": T.sha256_file(os.path.join(KDIR, "kstar_a45_meta.json")), "views": views}
    T.save_json(os.path.join(BUILD, "af26r01_views.json"), out)
    print("VIEWS", len(views), json.dumps(rel["nearest_lip_point_above_3m"]))


if __name__ == "__main__":
    main()
