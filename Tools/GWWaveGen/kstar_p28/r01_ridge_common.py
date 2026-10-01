# -*- coding: utf-8 -*-
"""仕上げ28修正01 の変種 RIDGE（稜）の共通部。py -3.10（numpy・scipy・OpenCV・PIL）。

仕上げ28 の第1回の RAYS の A5（crest_ramp：原画の頂の奥で頂を上げ続ける）だけが後ろから見た形を変えた（ドーム → 奥へ上る稜）。
ただし c ≈ −0.5 に縦の溝、F04 の最高点 c 5.4、F10 の段 0.43 を足した。RIDGE は、採った K*′ P28R2rec を土台に、
頂の線（背骨）を 3 次元でなめらかな曲がりの限られた 1 本の曲線として解き直し、原画の頂で止められた行から奥へ上る稜へ
数 m かけてつなぐ。原画の空を通る射線（空の禁止域）と、段階9 の船・手前の海の射線（船の禁止域）に新しくかからない量だけ上げる。
座標は kh_common と同じ（a = 進行方向 T、y = 高さ、c = 波峰線 E）。参照モデルは読まない（F13-1）。
出力はすべて Unity/Build/Polish/28r01/ridge/ の下（Git 対象外）。
"""
import os
import sys
import json
import hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(REPO, "Unity", "Build", "Polish", "28r01", "ridge")
P28 = os.path.join(REPO, "Unity", "Build", "Polish", "28")
BASE_DIR = os.path.join(P28, "kstar_p28rec")
BASE_ROWS = os.path.join(BASE_DIR, "kstarP28R2rec_a45_rows.npz")
BASE_GWB = os.path.join(BASE_DIR, "kstarP28R2rec_a45.gwb")
BASE_SHA = {"gwb": "a3bb1c81a79a15b7903729bd845a2d4b2660d3a06a417a218ae66f58eeb01e94",
            "rows": "c55e048d388e41e30289d075089066c481bf2f3b99d84727c655eea9e1a437a3"}
ROWS = {
    "R4": os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "kstar_final", "kstarR4_a45_rows.npz"),
    "P28R2rec": BASE_ROWS,
    "A5": os.path.join(P28, "r1_rays", "ablation", "A5_crest_ramp", "kstar_A5_crest_ramp_rows.npz"),
    "Kstar_26R01": os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01", "kstar", "kstar_a45_rows.npz"),
}
GWB = {
    "R4": os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "kstar_final", "kstarR4_a45.gwb"),
    "P28R2rec": BASE_GWB,
    "A5": os.path.join(P28, "r1_rays", "ablation", "A5_crest_ramp", "kstar_A5_crest_ramp.gwb"),
    "Kstar_26R01": os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01", "kstar", "kstar_a45.gwb"),
}
BLENDER = r"G:\SteamLibrary\steamapps\common\Blender\blender.exe"
HYTHON = r"G:\SteamLibrary\steamapps\common\Houdini Indie\bin\hython.exe"
FFMPEG = r"G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe"


def sha256(p, chunk=1 << 22):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def jdump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)


def redirect_caches():
    """r2_common・rec_common の作業場所（禁止域のキャッシュ）をこの変種の場所へ向ける（仕上げ28 の場所へは書かない）。"""
    import r2_common as R2
    import rec_common as RCm
    os.makedirs(os.path.join(OUT, "cache"), exist_ok=True)
    R2.OUT = OUT
    RCm.OUT = OUT
    return R2, RCm
