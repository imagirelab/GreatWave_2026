# -*- coding: utf-8 -*-
"""美術の見本05 やり方 B：原画視点の見え方だけを素早く測る（P1・P2・T5・T6。s5_targets.appearance と同じ測り）。
py -3.10 -B Tools/GWWaveGen/as05/shapeB_appear.py <rows.npz> <row_labels.npy> <render_dir> <out.json>
"""
import json
import sys

import numpy as np

sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as05")
import shapeB_common as B  # noqa: E402
import s5_targets as T5  # noqa: E402


def main():
    rows, rl, rd, out = sys.argv[1:5]
    c, A, Y = B.load_rows(rows)
    RL = np.load(rl)
    ch4, tri4, _ = T5.S.W4.read_static(B.WAVE4_F1)
    X4 = ch4["position"].astype(np.float64)
    meshes = [{"P": X4, "tri": tri4.astype(np.int64), "vl": np.zeros(len(X4), np.int16), "role": "wave4"}]
    tris, lab = T5.scene(c, A, Y, RL, meshes)
    pc, hero, _ = T5.painting_consistency(tris, lab)
    ap = T5.appearance(rd, hero)
    res = {"rows": rows, "render_dir": rd, "appearance": ap, "painting_label_consistency": pc}
    B.jdump(out, res)
    short = {k: {b: v.get("candidate") if isinstance(v, dict) and "candidate" in v else v for b, v in ap[k].items()} for k in ("r3", "r2")}
    print(json.dumps(short, ensure_ascii=False))
    print("T5", ap.get("T5_small_white_blobs_on_hero_indigo"), "T6", ap.get("T6_inner_edge_band_pale_share"), ap.get("T6_band_hero_px"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
