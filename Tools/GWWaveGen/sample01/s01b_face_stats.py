# -*- coding: utf-8 -*-
"""原画視点（爪なし）の描画を、原画の主役波の面（色区の藍の範囲 target_face）の中で、限定色の最も近い色に分けて割合を数える（前・見本 B・原画の色区）。
原画は比べる相手としてだけ使う（面へ写さない）。出力 final/face_stats.json"""
import json
import numpy as np
from PIL import Image
B = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/"
face = np.array(Image.open(B + "texB/work/target_face.png")) > 0
lab = np.array(Image.open("G:/Unity/GreatWave_2026_Fresh/Tools/PaintingTruth/colour/masks/mw_colour_labels.png"))
PAL = {"white": (248, 243, 223), "mizuiro": (198, 215, 203), "ai_mid": (44, 105, 147), "ai_dark": (35, 64, 97), "line": (71, 80, 95)}
names = list(PAL); P = np.array([PAL[k] for k in names], float)


def fr(path):
    im = np.array(Image.open(path).convert("RGB")).astype(float)[face]
    d = ((im[:, None, :] - P[None]) ** 2).sum(-1)
    k = d.argmin(1)
    return {names[i]: round(float((k == i).mean()), 4) for i in range(len(names))}


out = dict(face_px=int(face.sum()),
           painting_labels={"white(1)": round(float((lab[face] == 1).mean()), 4), "mizuiro(2)": round(float((lab[face] == 2).mean()), 4),
                            "ai_mid(3)": round(float((lab[face] == 3).mean()), 4), "ai_dark(4)": round(float((lab[face] == 4).mean()), 4)},
           before=fr(B + "texA/before/views/painting_t120_clawfree.png"),
           sampleB=fr(B + "texB/final/views/painting_t120_clawfree.png"),
           sampleA=fr(B + "texA/final/views/painting_t120_clawfree.png"))
json.dump(out, open(B + "texB/final/face_stats.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
