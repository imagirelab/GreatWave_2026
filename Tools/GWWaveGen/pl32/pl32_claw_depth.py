# -*- coding: utf-8 -*-
"""仕上げ32：原画視点 t* で、爪の帯の輪の頂点が主役波の面（K*′ P28R2rec）の手前か裏かを、原画の射線の上の深さの差で数える（numpy の z バッファ。記録のみ）。
前＝設計33 の爪（段階9 の K*′ R4 に結び付けたまま）、後＝仕上げ32 の爪。出力：Unity/Build/Polish/32/measure/pl32_claw_depth.json"""
import json
import os
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds33")
import ds33_common as U  # noqa: E402

K = U.K


def main():
    spec = U.jload(U.TRUTH)
    cam = U.C27.Cam(spec)
    hero = K.Pkg(REPO + "/Unity/Build/Polish/32/white/hero_pkg")
    X0 = hero.world(0.0)
    R, C = X0.shape[:2]
    Tb = K.grid_tris(R, C, 18, 394)
    idb, iz = K.raster_ids(cam, X0.reshape(-1, 3)[Tb], np.arange(1, len(Tb) + 1))
    zmap = np.where(iz > 0, 1.0 / np.maximum(iz, 1e-12), np.inf)
    out = {}
    runs = [("before_design33", REPO + "/Unity/Build/Design/33/claws"), ("after_pl32", REPO + "/Unity/Build/Polish/32/claws")]
    if os.environ.get("PL32F_CLAWS"):          # 仕上げ32 修正の回 1：修正の回 1 の爪も測る（出力は同じ名前で PL32F_OUT へ）
        runs.append(("fix01_pl32", os.environ["PL32F_CLAWS"]))
    for tag, cd in runs:
        lay = json.load(open(cd + "/ds33_claw_layout.json", encoding="utf-8"))
        V = np.memmap(cd + "/" + lay["files"]["frames"]["file"], dtype="<f4", mode="r", shape=(lay["frames"], lay["vertices"], 3))[360].astype(np.float64)
        med, hid, behind = [], [], []
        for c in lay["claws"]:
            o, n = c["vert_offset"], c["vert_count"]
            q, z = cam.project(V[o + 1:o + n - 10])
            xi = np.clip(np.round(q[:, 0]).astype(int), 0, 1919); yi = np.clip(np.round(q[:, 1]).astype(int), 0, 1079)
            zs = zmap[yi, xi]; ok = np.isfinite(zs)
            if ok.any():
                dz = (z - zs)[ok]; med.append(float(np.median(dz))); hid.append(float((dz > 0).mean()))
                if hid[-1] > 0.5:
                    behind.append(c["id"])
        m = np.array(med)
        out[tag] = dict(claws=len(m), ring_depth_minus_sheet_m=dict(p10=round(float(np.percentile(m, 10)), 3), median=round(float(np.median(m)), 3),
                                                                   p90=round(float(np.percentile(m, 90)), 3)),
                        claws_mostly_behind_sheet=behind)
    out["rule_ja"] = "爪ごとに、輪の頂点の原画のカメラからの深さ − 同じ画素の主役波の面の深さ（負＝面の手前）の中央値。裏の割合が 0.5 を超える爪を「大半が面の裏」とした"
    json.dump(out, open(os.environ.get("PL32F_OUT", REPO + "/Unity/Build/Polish/32/measure/pl32_claw_depth.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
