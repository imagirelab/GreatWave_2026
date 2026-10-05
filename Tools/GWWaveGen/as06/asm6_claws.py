# -*- coding: utf-8 -*-
"""美術の見本06 の組み立て（Q34）：新しい形で原画視点に隠れた面の内の爪を、原画のカメラを中心とする相似で手前へ置き直す（C3 の続き）。

決まり（見本02 の案 A・shape_claws.py と同じ相似）：爪の全部の点を原画のカメラを中心に k 倍する。どの点も自分の射線の上に残るので、
原画視点の爪の形は画素まで同じ（C3 の IoU は変わらない）。k は、原画視点（2 倍、爪なしの場面＝主役波＋wave4＋近い海）で爪の画素の
TARGET 以上が場面より手前（深さの差 0.02 m の許し）に出る最大の値（k ≤ 1。手前へだけ動かす）。
対象：引数で名を挙げた爪（組み立ての確かめ asm6_check.py で、B10 で見えていて新しい形で隠れた爪）。ほかの爪・近い海の 10 本は動かさない。
使い方：py -3.10 -B Tools/GWWaveGen/as06/asm6_claws.py <元の爪の並び.json> <合わせた静止のメッシュ.json> <主役波の頂点の数> <出力のフォルダー> <爪の名,...> [TARGET=0.95]
"""
import json
import os
import shutil
import sys

import numpy as np
from scipy.spatial import cKDTree

os.environ["AS04_FIX"] = "fix1"
REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as04")
import asm4_common as A  # noqa: E402
import shape_common as SC  # noqa: E402


def main():
    lay_in, union, nh, out, names = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5].split(",")
    target = float(sys.argv[6]) if len(sys.argv) > 6 else 0.95
    os.makedirs(out, exist_ok=True)
    A.UNION = union; A.N_HERO = nh; A.CLAWS04 = lay_in
    lay = A.jl(lay_in)
    d = os.path.dirname(lay_in)
    nv = lay["vertices"]
    fr = np.fromfile(d + "/" + lay["files"]["frames"]["file"], np.float32).reshape(lay["frames"], nv, 3).astype(np.float64)
    tris, lab, _ = A.scene("S04", with_claws=False)
    cam2 = A.painting_cam(2)
    _, D0, _ = A.raster(cam2, tris, lab)
    cam = SC.paint_cam()
    ch, _, _ = A.read_static(union)
    hp = ch["position"][:nh].astype(np.float64); hn = ch["normal"][:nh].astype(np.float64)
    kd = cKDTree(hp)
    tr = np.fromfile(d + "/" + lay["files"]["tris"]["file"], np.int32).reshape(-1, 3).astype(np.int64)
    recs = []
    for cl in lay["claws"]:
        if cl["user_id"] not in names:
            continue
        o, n = cl["vert_offset"], cl["vert_count"]
        sel = np.nonzero((tr[:, 0] >= o) & (tr[:, 0] < o + n))[0]
        V = fr[-1, o:o + n]
        _, Dc, Lc = A.raster(cam2, V[tr[sel] - o], np.full(len(sel), 7, np.int16))
        m = Lc > 0
        r = (D0[m] + 0.02) / Dc[m]
        vis0 = float((r >= 1.0).mean())
        k = float(min(1.0, np.quantile(r, 1.0 - target)))
        vis1 = float((r >= k).mean())
        V1 = cam.pos + (V - cam.pos) * k
        dd, ii = kd.query(V1)
        sd = ((V1 - hp[ii]) * hn[ii]).sum(1)
        fr[:, o:o + n, :] = cam.pos[None, None, :] + (fr[:, o:o + n, :] - cam.pos[None, None, :]) * k
        t0 = float(np.linalg.norm(V[0] - cam.pos))
        recs.append({"user_id": cl["user_id"], "scale_k": SC.rnd(k, 4), "moved_m": SC.rnd(t0 * (k - 1.0)), "px_x2": int(m.sum()),
                     "visible_frac_before": SC.rnd(vis0), "visible_frac_after": SC.rnd(vis1),
                     "after_root_dist_to_hero_m": SC.rnd(dd[0]), "after_dist_to_hero_m_min_p50_max": [SC.rnd(dd.min()), SC.rnd(np.median(dd)), SC.rnd(dd.max())],
                     "after_signed_normal_m_min_max": [SC.rnd(sd.min()), SC.rnd(sd.max())]})
    fp = out + "/" + lay["files"]["frames"]["file"]
    fr.astype(np.float32).tofile(fp)
    for k_ in ("tris", "tri_attr", "skel"):
        if k_ in lay["files"]:
            shutil.copy2(d + "/" + lay["files"][k_]["file"], out + "/" + lay["files"][k_]["file"])
    lay2 = json.loads(json.dumps(lay))
    lay2["files"]["frames"]["sha256"] = SC.sha(fp)
    lay2["files"]["frames"]["bytes"] = os.path.getsize(fp)
    # 置き直しの記録（asm4_rules.c2_c3 が読む moved_m）を、動かした爪だけ足し合わせる
    if "as04_shape" in lay2:
        for e in lay2["as04_shape"].get("face_interior", []):
            for r_ in recs:
                if e.get("user_id") == r_["user_id"]:
                    e["moved_m"] = SC.rnd(float(e.get("moved_m", 0.0)) + r_["moved_m"])
                    e["asm6_extra_scale"] = r_["scale_k"]
    lay2["as06_asm6_claws"] = {"tool": "Tools/GWWaveGen/as06/asm6_claws.py", "source_layout": lay_in, "source_layout_sha256": SC.sha(lay_in),
                               "union": union, "union_bin_sha256": A.jl(union)["sha256"], "target_visible_frac": target, "moved": recs,
                               "note_ja": "新しい形で原画視点に隠れた面の内の爪を、原画のカメラを中心とする相似で手前へだけ動かした（原画視点の爪の形は画素まで同じ）"}
    json.dump(lay2, open(out + "/ds33_claw_layout.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(recs, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
