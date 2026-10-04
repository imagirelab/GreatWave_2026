# -*- coding: utf-8 -*-
"""美術の見本04 の調べ M（Q32）：記録 run.json（道具・材質・メッシュ・描画・図・関門の SHA-256 と、測った数）を書く。
使い方：py -3.10 -B Tools/GWWaveGen/as04/mat_record.py
"""
import glob
import hashlib
import json
import os
import time

import numpy as np
from PIL import Image

REPO = "G:/Unity/GreatWave_2026_Fresh"
OUT = REPO + "/Unity/Build/Polish/sample04/mat"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def colour_frac(path, box):
    """描画の箱の中の、限られた色（藍濃・藍中・白）の画素の割合（記録だけ。判定に使わない）"""
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)[box[1]:box[3], box[0]:box[2]].reshape(-1, 3)
    near = lambda c: int((np.abs(a - np.array(c)).sum(1) <= 6).sum())
    dk, md, wh = near((35, 64, 97)), near((44, 105, 147)), near((248, 243, 223))
    return {"ai_dark": round(dk / len(a), 3), "ai_mid": round(md / len(a), 3), "white": round(wh / len(a), 3),
            "ai_mid_over_indigo": round(md / max(dk + md, 1), 3)}


def main():
    tools = sorted(glob.glob(REPO + "/Tools/GWWaveGen/as04/mat_*") + glob.glob(REPO + "/Tools/GWWaveGen/as04/as04_flat_smooth_params.txt"))
    assets = sorted(glob.glob(REPO + "/Unity/Assets/GreatWave/ArtSample04/Shaders/*"))
    mesh = sorted(glob.glob(OUT + "/mesh/*"))
    renders = sorted(glob.glob(OUT + "/render/final/views/*.png") + glob.glob(OUT + "/render/final/crest/*.png") + glob.glob(OUT + "/render/kp1/views/*.png"))
    gates = json.load(open(OUT + "/render/measure/gates_final/sweep_gates.json", encoding="utf-8"))
    paint = rel(REPO + "/Docs/References/Met_JP1847_DP130155.jpg")
    pfrac = None
    im = np.asarray(Image.open(REPO + "/Docs/References/Met_JP1847_DP130155.jpg").convert("RGB")).astype(int)[600:1050, 1050:1550].reshape(-1, 3)
    pal = {"white": (251, 246, 227), "mizuiro": (192, 211, 199), "ai_mid": (41, 105, 148), "ai_dark": (34, 63, 96)}
    P = np.array(list(pal.values()))
    k = ((im[:, None, :] - P[None]) ** 2).sum(-1).argmin(1)
    pfrac = {n: round(float((k == i).mean()), 3) for i, n in enumerate(pal)}
    pfrac["ai_mid_over_indigo"] = round(pfrac["ai_mid"] / (pfrac["ai_mid"] + pfrac["ai_dark"]), 3)
    rec = {
        "schema": "GreatWave.AS04.mat_run/1",
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "noteJa": "美術の見本04 の調べ M（Q32）：AS04 Flat Smooth。Unity 6000.4.3f1 の PC オフスクリーン描画（batchmode）。HMD 実機ではない。原画カメラの投影は使わない。参照モデルの OBJ・彫刻の写真は読んでいない。",
        "commands": [
            "py -3.10 -B Tools/GWWaveGen/as04/mat_smooth_mesh.py",
            "bash Tools/GWWaveGen/as04/mat_render.sh final views,crest,full,t28",
            "RB=…/sample04/mat/render LG=…/sample04/mat/logs BEFORE=…/sample02/fix01/assemble/render/AS02C_A bash Tools/GWWaveGen/as02/as02_asm_eval.sh final",
            "bash Tools/GWWaveGen/as04/mat_render_kp.sh kp1",
            "py -3.10 -B Tools/GWWaveGen/as04/mat_sheets.py final",
            "py -3.10 -B Tools/GWWaveGen/as04/mat_record.py",
        ],
        "iterations": {
            "t1": "第 1 版：帯の幅の中央 0.18 λ、白い点 S2 の数のまま（格子 0.66 m、半径 0.062 m）、水色は境から幅 0.25〜1.3 m",
            "t2": "第 2 版：帯の中央 0.22・最小 0.08、白い点を格子 1.0 m・半径 0.08 m・割合 0.7 へ、水色を境から 0.3 m 奥へ（白い舌の先を白に）。主役波の外殻の線なしも描いて、白の中の短い線が外殻の線から来ることを確かめた（t2_ol0、消した）",
            "t3": "第 3 版：帯の中央 0.20、背の藍にも帯（_BandBack 1）",
            "t4": "第 4 版：白い点を 4〜6 角の欠片の形へ",
            "final": "第 4 版の値で、シェーダーの名前を空白なしへ替えた版（見え方は t4 と同じ）。views・crest・full・t28",
            "kp1": "同じ値で keypose の主役波（_AS03Src 0）に当てた確かめ",
        },
        "tools": {rel(p): sha(p) for p in tools},
        "unity_assets": {rel(p): sha(p) for p in assets},
        "mesh": {rel(p): sha(p) for p in mesh},
        "inputs": {
            "hero_pkg": "Unity/Build/Polish/sample02/fix01/assemble/hero_pkg_AS02C（ds27_keypose.json " + sha(REPO + "/Unity/Build/Polish/sample02/fix01/assemble/hero_pkg_AS02C/ds27_keypose.json") + "）",
            "gwb": "Unity/Build/Polish/sample02/fix01/back/final/cand/kstarAS02C_a45.gwb " + sha(REPO + "/Unity/Build/Polish/sample02/fix01/back/final/cand/kstarAS02C_a45.gwb"),
            "attr": "Unity/Build/Polish/sample02/fix01/assemble/attr_pin/a/s01a_hero_attr_v2_f32.bin " + sha(REPO + "/Unity/Build/Polish/sample02/fix01/assemble/attr_pin/a/s01a_hero_attr_v2_f32.bin"),
            "white_mask": "Unity/Build/Polish/sample03/shared/white_mask_f32.bin " + sha(REPO + "/Unity/Build/Polish/sample03/shared/white_mask_f32.bin"),
            "white_band": "Unity/Build/Polish/sample03/shared/white_mask_band_f32.bin " + sha(REPO + "/Unity/Build/Polish/sample03/shared/white_mask_band_f32.bin"),
            "claws35": "Unity/Build/Polish/sample03/assemble/claws35/ds33_claw_layout.json " + sha(REPO + "/Unity/Build/Polish/sample03/assemble/claws35/ds33_claw_layout.json"),
            "kp_attr": "Unity/Build/Polish/sample03/surface/attr/as03_kp_attr_f32.bin " + sha(REPO + "/Unity/Build/Polish/sample03/surface/attr/as03_kp_attr_f32.bin"),
            "painting": paint + " " + sha(REPO + "/" + paint),
            "render_tool": "Unity/Assets/GreatWave/ArtSample03/Editor/AS03AsmRender.cs " + sha(REPO + "/Unity/Assets/GreatWave/ArtSample03/Editor/AS03AsmRender.cs") + "（変えていない）",
        },
        "render_report": rel(OUT + "/render/final/as03asm_render_report.json"),
        "render_report_sha256": sha(OUT + "/render/final/as03asm_render_report.json"),
        "renders": {rel(p): sha(p) for p in renders},
        "sheets": json.load(open(OUT + "/mat_sheets.json", encoding="utf-8")),
        "gates_painting_view": {g: {"after_claws": v.get("after_claws"), "after_noclaws": v.get("after_noclaws"), "before_claws": v.get("before_claws"), "pass": v.get("pass_after")}
                                for g, v in gates["gates"].items()},
        "eval23": gates.get("eval23", {}).get("after"),
        "colour_fraction_record": {
            "noteJa": "記録だけ（判定に使わない）。面の箱の中の画素の割合。原画は原画の画素（x 1050〜1550・y 600〜1050）を 4 色の近い方へ分けた値（白い点を含む）。",
            "painting_face_box": pfrac,
            "as04_painting_view_face": colour_frac(OUT + "/render/final/views/painting_t120_claws.png", (620, 260, 900, 560)),
            "as04_seat_face": colour_frac(OUT + "/render/final/views/seat_t120_claws.png", (300, 500, 1300, 1080)),
            "as04_seat_toward_wave_face": colour_frac(OUT + "/render/final/views/seat_toward_wave_t120_claws.png", (100, 100, 1300, 800)),
        },
        "uv_metric": json.load(open(OUT + "/mesh/hero_smooth_as02c_uvmetric.json", encoding="utf-8")),
        "projection_used": False, "reference_obj_read": False, "photos_read": False,
    }
    rec["uv_metric"].pop("mesh", None)
    with open(OUT + "/run.json", "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print(json.dumps(rec["gates_painting_view"], ensure_ascii=False))
    print(json.dumps(rec["colour_fraction_record"], ensure_ascii=False))


if __name__ == "__main__":
    main()
