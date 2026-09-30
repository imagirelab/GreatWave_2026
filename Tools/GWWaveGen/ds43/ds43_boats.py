# -*- coding: utf-8 -*-
"""設計43：3 隻の船の浮力点の表と置き方（Unity の DS43BoatWaterTest が読む）。

- 座席の船 boat_mid は設計42 の ds42_buoyancy_points.json をそのまま使う（縮尺 1.13284 m / 単位）。
- 手前の船 boat_fg（0.844624）・左奥の船 boat_left（0.9981）は、同じ船体を縮尺の比 k で相似に縮めた表（Froude の相似：長さ k、容積・質量 k³、
  慣性 k⁵、水線面積 k²、上下の減衰 k^2.5、水平・首振りの抵抗の率はそのまま）。質量の推定（乗員 10 人など）を k³ で縮めるのは数値の条件で、
  資料の値ではない（仕上げ42 で見直す）。
- 置き方：船の根（設計41 の場面の根。原点は船体中央の船底、+z 船首）の水平の位置と首の向き（局所 +z の水平の成分）を、原画の置き方
  （seat_v1.json・設計41 の metrics の real_dimensions_per_boat）から取る。縦・横の傾きは 0 で始める（t* の姿勢は設計44 の固定の軌道の役目）。
- 座席の目：seat_v1 の目（世界）を boat_mid の原画の根の局所へ移した点（物理の根の局所の m）。
使い方：py -3.10 -B Tools/GWWaveGen/ds43/ds43_boats.py
"""
import json
import math
import os

import numpy as np

import ds43_common as C

SRC = os.path.join(C.REPO, "Unity", "Assets", "GreatWave", "Design42", "Data", "ds42_buoyancy_points.json")
DST = os.path.join(C.REPO, "Unity", "Assets", "GreatWave", "Design43", "Data")


def qrot(q, v):
    x, y, z, w = q
    u = np.array([x, y, z])
    return v + 2.0 * np.cross(u, np.cross(u, v) + w * v)


def main():
    src = C.load_json(SRC)
    m41 = C.load_json(os.path.join(C.REPO, "Docs", "Evidence", "Design", "41", "metrics.json"))["model"]["real_dimensions_per_boat"]
    seat = C.load_json(os.path.join(C.REPO, "Tools", "GWContext", "seat_v1.json"))
    s0 = float(src["scale"])
    os.makedirs(DST, exist_ok=True)
    boats = []
    for key in ("boat_mid", "boat_fg", "boat_left"):
        b = m41[key]
        s = float(b["scale"])
        k = s / s0
        d = dict(src)
        d["schema"] = "GreatWave.DS43.buoyancy_points/1"
        d["noteJa"] = ("設計43：設計42 の浮力点の表（boat_mid、縮尺 %.6f）を縮尺の比 k = %.6f で相似に直した表（長さ k、容積・質量 k³、慣性 k⁵、水線面積 k²、"
                       "上下の減衰 k^2.5）。%s 用。" % (s0, k, key))
        d["scale"] = s
        d["massKg"] = src["massKg"] * k ** 3
        d["cgLocal"] = [v * k for v in src["cgLocal"]]
        d["inertiaDiag"] = [v * k ** 5 for v in src["inertiaDiag"]]
        d["levelMin"] = src["levelMin"] * k
        d["levelStep"] = src["levelStep"] * k
        d["pointPos"] = [v * k for v in src["pointPos"]]
        d["tabV"] = [v * k ** 3 for v in src["tabV"]]
        d["tabC"] = [v * k for v in src["tabC"]]
        d["tabA"] = [v * k ** 2 for v in src["tabA"]]
        d["dampHeaveNsPerM"] = src["dampHeaveNsPerM"] * k ** 2.5
        d["areaRefM2"] = src["areaRefM2"] * k ** 2
        d["eqDraftMidM"] = src["eqDraftMidM"] * k
        d["eqKeelHeightM"] = src["eqKeelHeightM"] * k
        d["periodsS"] = [v * math.sqrt(k) for v in src["periodsS"]]
        d["stiffness"] = [src["stiffness"][0] * k ** 2, src["stiffness"][1] * k ** 4, src["stiffness"][2] * k ** 4]
        d["inertiaWorldAxes"] = [v * k ** 5 for v in src["inertiaWorldAxes"]]
        name = "ds43_buoyancy_points_%s.json" % key
        with open(os.path.join(DST, name), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        p = np.array([b["root_position"][c] for c in "xyz"])
        q = np.array([b["root_rotation"][c] for c in "xyzw"])
        fz = qrot(q, np.array([0.0, 0.0, 1.0]))
        yaw = math.degrees(math.atan2(fz[0], fz[2]))
        rec = dict(key=key, cfg="Assets/GreatWave/Design43/Data/" + name, scale=s, k=k, massKg=d["massKg"],
                   rootPos=p.tolist(), rootRot=q.tolist(), yawDeg=yaw, lengthM=b["tip_to_tip_m"], beamM=b["beam_m"],
                   eqDraftMidM=d["eqDraftMidM"])
        if key == "boat_mid":
            eye = np.array(seat["seat"]["eye_world"], np.float64)
            qi = np.array([-q[0], -q[1], -q[2], q[3]])
            rec["eyeLocal"] = qrot(qi, eye - p).tolist()     # 物理の根（縮尺 1）の局所の m
            rec["eyeWorldPainting"] = eye.tolist()
        else:
            rec["eyeLocal"] = [0.0, 0.0, 0.0]
            rec["eyeWorldPainting"] = [0.0, 0.0, 0.0]
        boats.append(rec)
    out = dict(schema="GreatWave.DS43.boats/1", noteJa="設計43 の試験の 3 隻（ds43_boats.py の出力）。rootPos・rootRot は原画の置き方の根、yawDeg は局所 +z の水平の向き（+x から見た atan2(x, z)）。",
               boats=boats)
    with open(os.path.join(DST, "ds43_boats.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1)[:2500])


if __name__ == "__main__":
    main()
