# -*- coding: utf-8 -*-
"""美術の見本05 のやり方 A：見本03 の爪 35 本（面の内 FACE_INTERIOR 25・近い海 NEAR_SEA 10）を、新しい主役波 AS05A と ③ の波 layer3 の面へ置き直す。
見本04 の shape_claws.py（変えない）と同じ決まり（見本02 の案 A）：原画のカメラから爪の根元への射線の上で、根元の深さだけを変える。
  土台 AS02C の最初の当たりから根元までの距離 d_old を、新しい面（AS05A の行 ＋ layer3）の最初の当たりからも保つ。
  爪の全部の点を原画のカメラを中心に（新しい距離 ÷ 元の距離）倍する：原画視点の爪の形は画素まで同じ（C3）。
  近い海の 10 本は動かさない（ただし ③ の面の下に埋まるかを記録する）。波頭の 48 本は見本03 と同じく潰したまま（描かない。Q33）。
使い方：py -3.10 -B Tools/GWWaveGen/as05/shapeA_claws.py
出力（Git 対象外）：Unity/Build/Polish/sample05/shapeA/claws/
"""
import json
import os
import shutil
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapeA_common as C  # noqa: E402
import shape_claws as SCL  # noqa: E402
import s4_rays as RY  # noqa: E402
import w4_common as W  # noqa: E402

S = C.SC
OUT = C.OUT + "/claws"


def main():
    os.makedirs(OUT, exist_ok=True)
    SRC = SCL.SRC
    lay = json.load(open(SRC + "/ds33_claw_layout.json", encoding="utf-8"))
    nv = lay["vertices"]
    fr = np.fromfile(SRC + "/" + lay["files"]["frames"]["file"], np.float32).reshape(lay["frames"], nv, 3).astype(np.float64)
    roles = {k["user_id"]: k["role"] for k in lay["as03_asm"]["kept"]}
    cam = S.paint_cam()
    V0, T0, tid0, Ccol = SCL.mesh(S.BASE_ROWS)
    V1, T1, tid1, _ = SCL.mesh(C.ROWS05A)
    ch, tl3, _ = W.read_static(C.L3_JSON)
    P3 = ch["position"].astype(np.float64)
    n1 = len(V1)
    V1 = np.concatenate([V1, P3]); T1 = np.concatenate([T1, tl3.astype(np.int64) + n1])
    nT_hero = len(tid1)
    TH0 = RY.TileHits(cam, V0, T0, tile=16)
    TH1 = RY.TileHits(cam, V1, T1, tile=16)
    rec = []
    for cl in lay["claws"]:
        uid = cl["user_id"]
        role = roles.get(uid)
        o, n = cl["vert_offset"], cl["vert_count"]
        Rw = fr[0, o]
        d = Rw - cam.pos
        t_root = float(np.linalg.norm(d)); d /= t_root
        xy, _ = cam.project(Rw[None])
        x, y = float(xy[0, 0]), float(xy[0, 1])

        def hits(TH, V, T):
            k = int(np.floor(y / TH.tile)) * TH.nx + int(np.floor(x / TH.tile))
            b = TH.buckets.get(k)
            if not b:
                return []
            t = np.unique(np.concatenate(b))
            Vt = V[T[t]]
            hit, s, u, v = RY.ray_tri(cam.pos, d, Vt[:, 0], Vt[:, 1], Vt[:, 2])
            o_ = np.argsort(s[hit])
            return list(zip(s[hit][o_], t[hit][o_]))
        if role == "NEAR_SEA":
            h1 = hits(TH1, V1, T1)
            first = h1[0] if h1 else None
            rec.append({"user_id": uid, "role": role, "moved_m": 0.0, "root_dist_m": S.rnd(t_root),
                        "new_surface_first_hit_m": S.rnd(first[0]) if first else None,
                        "hidden_behind_new_surface": bool(first is not None and first[0] < t_root - 0.3),
                        "first_hit_is_layer3": bool(first is not None and first[1] >= nT_hero)})
            continue
        if role != "FACE_INTERIOR":
            continue
        h0 = RY.merge_layers([(s_, t_, 0, 0) for s_, t_ in hits(TH0, V0, T0)])
        h1 = RY.merge_layers([(s_, t_, 0, 0) for s_, t_ in hits(TH1, V1, T1)])
        if not h0 or not h1:
            rec.append({"user_id": uid, "role": role, "moved_m": 0.0, "note": "当たりなし（動かさない）"})
            continue
        off = t_root - h0[0][0]
        t_new = h1[0][0] + off
        k_ = t_new / t_root
        fr[:, o:o + n, :] = cam.pos[None, None, :] + (fr[:, o:o + n, :] - cam.pos[None, None, :]) * k_
        on_l3 = bool(h1[0][1] >= nT_hero)
        rec.append({"user_id": uid, "role": role, "moved_m": S.rnd(t_new - t_root), "scale": S.rnd(k_), "root_offset_from_surface_m": S.rnd(off),
                    "seated_on": "layer3" if on_l3 else "hero_AS05A", "root_display_xy": S.rnd([x, y], 1)})
    fp = OUT + "/ds33_claw_frames_f32.bin"
    fr.astype(np.float32).tofile(fp)
    for k in ("tris", "tri_attr", "skel"):
        shutil.copy2(SRC + "/" + lay["files"][k]["file"], OUT + "/" + lay["files"][k]["file"])
    lay2 = json.loads(json.dumps(lay))
    lay2["files"]["frames"]["sha256"] = S.sha(fp)
    lay2["files"]["frames"]["bytes"] = os.path.getsize(fp)
    fi = [r for r in rec if r["role"] == "FACE_INTERIOR"]
    mv = np.array([abs(r["moved_m"]) for r in fi])
    lay2["as05a_shape"] = {"tool": "Tools/GWWaveGen/as05/shapeA_claws.py", "hero_rows": C.ROWS05A, "hero_rows_sha256": S.sha(C.ROWS05A),
                           "layer3": C.L3_JSON, "layer3_sha256": S.sha(C.L3_JSON),
                           "source_layout_sha256": S.sha(SRC + "/ds33_claw_layout.json"),
                           "noteJa": "面の内の爪 25 本を、原画のカメラから根元への射線の上で、AS05A と ③ の波 layer3 の面へ置き直した（AS02C の面からの距離を保つ）。近い海の 10 本と潰した 48 本は見本03 のまま。",
                           "claws": rec, "moved_abs_m": {"max": S.rnd(mv.max()), "p50": S.rnd(np.median(mv)), "moved_gt_1cm": int((mv > 0.01).sum())},
                           "seated_on_layer3": int(sum(1 for r in fi if r.get("seated_on") == "layer3")),
                           "near_sea_hidden_behind_new_surface": int(sum(1 for r in rec if r.get("hidden_behind_new_surface")))}
    json.dump(lay2, open(OUT + "/ds33_claw_layout.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: lay2["as05a_shape"][k] for k in ("moved_abs_m", "seated_on_layer3", "near_sea_hidden_behind_new_surface")}, ensure_ascii=False))
    for r in rec:
        print(r)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
