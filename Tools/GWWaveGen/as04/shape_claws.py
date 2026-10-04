# -*- coding: utf-8 -*-
"""美術の見本04 の形づくり：見本02・03 の爪 35 本（面の内 FACE_INTERIOR 25・近い海 NEAR_SEA 10）を、新しい主役波 AS04 の面へ置き直す。

見本02 の案 A と同じ決まり：原画のカメラから爪の根元（爪の最初の頂点）への射線の上で、根元の深さだけを変える（爪をその射線の向きに丸ごと動かす）。
  1. 土台 AS02C と AS04 の t* のメッシュに、根元の射線を当てる（すべての交点、近い順）。
  2. 根元が AS02C の当たり（最も近い交点）から d_old の所にあれば、AS04 の最も近い交点からも同じ d_old の所へ置く（面からの沈み・浮きを保つ）。
     爪の全部の点を、原画のカメラを中心に（根元の新しい距離 ÷ 元の距離）倍する：どの点もその射線の上に残るので、原画視点の爪の形は画素まで同じ
     （奥へ動いた爪は 3D では大きくなる。倍率を記録する）。
  3. 近い海の 10 本は近い海が変わらないので動かさない。波頭の冠の役 48 本は見本03 と同じく根元の点へ潰したまま（描かない）。
原画視点の爪の形は変わらない（射線の上を動かすだけ）。動いた量・当たった面の列（唇の外・内の面）を記録する。
使い方：py -3.10 -B Tools/GWWaveGen/as04/shape_claws.py
出力（Git 対象外）：Build/Polish/sample04/shape/claws/（爪の並び ds33_claw_layout.json と頂点 ds33_claw_frames_f32.bin、ほかは見本03 の写し）
"""
import json
import os
import shutil
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shape_common as S  # noqa: E402
import s4_rays as RY  # noqa: E402

SRC = S.REPO + "/Unity/Build/Polish/sample03/assemble/claws35"
OUT = S.OUT + "/claws"
NEW_ROWS = S.OUT + "/final/cand/kstarAS04_a45_rows.npz"


def mesh(rows):
    c, A, Y = S.load_rows(rows)
    X = S.world(c, A, Y)
    T = S.grid_tris(*A.shape)
    r, cc = S.tri_cell(np.arange(len(T)), A.shape[1])
    keep = (cc >= S.J_B) & (cc < 394)
    return X.reshape(-1, 3), T[keep], np.nonzero(keep)[0], A.shape[1]


def main():
    os.makedirs(OUT, exist_ok=True)
    lay = json.load(open(SRC + "/ds33_claw_layout.json", encoding="utf-8"))
    nv = lay["vertices"]
    fr = np.fromfile(SRC + "/" + lay["files"]["frames"]["file"], np.float32).reshape(lay["frames"], nv, 3).astype(np.float64)
    roles = {k["user_id"]: k["role"] for k in lay["as03_asm"]["kept"]}
    cam = S.paint_cam()
    V0, T0, tid0, C = mesh(S.BASE_ROWS)
    V1, T1, tid1, _ = mesh(NEW_ROWS)
    TH0 = RY.TileHits(cam, V0, T0, tile=16)
    TH1 = RY.TileHits(cam, V1, T1, tile=16)
    rec = []
    for cl in lay["claws"]:
        uid = cl["user_id"]
        role = roles.get(uid)
        if role != "FACE_INTERIOR":
            continue
        o, n = cl["vert_offset"], cl["vert_count"]
        Rw = fr[0, o]
        d = Rw - cam.pos
        t_root = float(np.linalg.norm(d)); d /= t_root
        xy, _ = cam.project(Rw[None])
        x, y = float(xy[0, 0]), float(xy[0, 1])
        # 射線は根元そのものを通るので、TileHits の画素の射線ではなく根元の向き d で当てる
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
        h0 = RY.merge_layers([(s_, t_, 0, 0) for s_, t_ in hits(TH0, V0, T0)])
        h1 = RY.merge_layers([(s_, t_, 0, 0) for s_, t_ in hits(TH1, V1, T1)])
        if not h0 or not h1:
            rec.append({"user_id": uid, "moved_m": 0.0, "note": "当たりなし（動かさない）"})
            continue
        off = t_root - h0[0][0]                     # 根元の、AS02C の最初の当たりからの射線の上の距離（+ は奥へ沈む）
        t_new = h1[0][0] + off
        # 爪のどの点もその射線の上に残す（原画のカメラを中心に t_new / t_root 倍：原画視点の爪の形は画素まで同じ。見本02 の案 A の決まり）
        k_ = t_new / t_root
        fr[:, o:o + n, :] = cam.pos[None, None, :] + (fr[:, o:o + n, :] - cam.pos[None, None, :]) * k_
        c0 = int(S.tri_cell(np.array([tid0[h0[0][1]]]), C)[1][0]); c1 = int(S.tri_cell(np.array([tid1[h1[0][1]]]), C)[1][0])
        r0 = int(S.tri_cell(np.array([tid0[h0[0][1]]]), C)[0][0]); r1 = int(S.tri_cell(np.array([tid1[h1[0][1]]]), C)[0][0])
        rec.append({"user_id": uid, "moved_m": S.rnd(t_new - t_root), "scale": S.rnd(k_), "root_offset_from_surface_m": S.rnd(off),
                    "hit_old_row_col": [r0, c0], "hit_new_row_col": [r1, c1], "root_display_xy": S.rnd([x, y], 1)})
    fp = OUT + "/ds33_claw_frames_f32.bin"
    fr.astype(np.float32).tofile(fp)
    for k in ("tris", "tri_attr", "skel"):
        shutil.copy2(SRC + "/" + lay["files"][k]["file"], OUT + "/" + lay["files"][k]["file"])
    lay2 = json.loads(json.dumps(lay))
    lay2["files"]["frames"]["sha256"] = S.sha(fp)
    lay2["files"]["frames"]["bytes"] = os.path.getsize(fp)
    mv = np.array([abs(r["moved_m"]) for r in rec])
    lay2["as04_shape"] = {"tool": "Tools/GWWaveGen/as04/shape_claws.py", "hero_rows": NEW_ROWS, "hero_rows_sha256": S.sha(NEW_ROWS),
                          "source_layout_sha256": S.sha(SRC + "/ds33_claw_layout.json"),
                          "noteJa": "面の内の爪 25 本を、原画のカメラから根元への射線の上で、AS04 の面へ置き直した（面からの距離を保つ）。近い海の 10 本と潰した 48 本は見本03 のまま。",
                          "face_interior": rec, "moved_abs_m": {"max": S.rnd(mv.max()), "p50": S.rnd(np.median(mv)), "moved_gt_1cm": int((mv > 0.01).sum())}}
    json.dump(lay2, open(OUT + "/ds33_claw_layout.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(lay2["as04_shape"]["moved_abs_m"], ensure_ascii=False))
    for r in rec:
        if abs(r["moved_m"]) > 0.01:
            print(r)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
