# -*- coding: utf-8 -*-
"""美術の見本03 の作り B1-5：冠（OUT・IN）の粘土の描画の準備と、Blender の呼び出し。
- 主役波（t* の AS02C）は共有の白の印の色（白の地＝明るい灰、藍＝青灰）、近い海は暗い青灰、冠は暖かい白、利用者の爪（冠の指の先）はクリーム、
  面の内・近い海の利用者の爪（見本02 のまま）は灰。Workbench の studio の光・くぼみ・影・艶。
- 視点：原画視点・原画視点の頂の拡大・座席・座席から波の方向・左右の側面・後ろ 65°・真上（見本01・02 と同じ値）と、波頭の回り台 8 方位
  （S3 と同じ：中心 (−6.63, 16.5, −3.27)、距離 34 m、仰角 5°、画角 35°、方位 0° は中心から原画のカメラへの水平の向き）。
使い方：py -3.10 -B Tools/GWWaveGen/as03/crown_render.py --mode OUT [--views quick]
出力：Unity/Build/Polish/sample03/crown/render/<mode>/*.png（Git 対象外）
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crown_common as G  # noqa: E402

BLENDER = "G:/SteamLibrary/steamapps/common/Blender/blender.exe"
CREST_CTR = np.array([-6.63, 16.5, -3.27])
PAINT_POS = np.array([0.0, 3.0, -62.0])


def to_bl(V):
    return np.ascontiguousarray(V[:, [0, 2, 1]], np.float32)


def views_all():
    V = []
    cam = G.painting_cam()
    V.append(dict(name="painting", pos=cam.pos.tolist(), fwd=cam.f.tolist(), up=cam.u.tolist(), fov=26.0))
    # 原画視点の頂の拡大（同じ位置から頂の帯を見る）
    tgt = np.array([-1.0, 15.0, -4.0])
    f = tgt - cam.pos
    f /= np.linalg.norm(f)
    V.append(dict(name="painting_crest", pos=cam.pos.tolist(), fwd=f.tolist(), up=[0, 1, 0], fov=12.0))
    for nm in ("seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"):
        p, fw, up, fov = G.CC.VIEWS[nm]
        V.append(dict(name=nm, pos=list(p), fwd=list(fw), up=list(up), fov=fov))
    az0 = math.atan2(PAINT_POS[2] - CREST_CTR[2], PAINT_POS[0] - CREST_CTR[0])
    el = math.radians(5.0)
    for k in range(8):
        az = az0 + math.radians(45.0 * k)
        eye = CREST_CTR + 34.0 * np.array([math.cos(el) * math.cos(az), math.sin(el), math.cos(el) * math.sin(az)])
        fw = CREST_CTR - eye
        fw /= np.linalg.norm(fw)
        V.append(dict(name="crest_az%03d" % (45 * k), pos=eye.tolist(), fwd=fw.tolist(), up=[0, 1, 0], fov=35.0))
    return V


def prep_meshes(mode, tmp, mask_file=None, src=None):
    src = src or mode
    h = G.HeroData()
    out = []
    # 主役波（白の印の色）
    sdp = mask_file or os.path.join(G.SHARED, "white_mask_f32.bin")
    sd = np.fromfile(sdp, np.float32)          # + が白
    w = np.clip(0.5 + sd / 0.12, 0, 1)[:, None]
    white = np.array([0.86, 0.86, 0.85, 1.0])
    indigo = np.array([0.26, 0.33, 0.50, 1.0])
    Ch = indigo[None, :] * (1 - w) + white[None, :] * w
    np.save(tmp + "/hero_V.npy", to_bl(h.V))
    np.save(tmp + "/hero_F.npy", h.Tg.astype(np.int32))
    np.save(tmp + "/hero_C.npy", Ch.astype(np.float32))
    out.append(dict(name="hero", V=tmp + "/hero_V.npy", F=tmp + "/hero_F.npy", C=tmp + "/hero_C.npy"))
    # 近い海
    g = G.read_gwb(G.SEA_NEAR)
    np.save(tmp + "/sea_V.npy", to_bl(g["X"]))
    np.save(tmp + "/sea_F.npy", g["tris"].astype(np.int32))
    np.save(tmp + "/sea_C.npy", np.tile(np.array([[0.20, 0.26, 0.38, 1.0]], np.float32), (len(g["X"]), 1)))
    out.append(dict(name="sea", V=tmp + "/sea_V.npy", F=tmp + "/sea_F.npy", C=tmp + "/sea_C.npy"))
    # 冠
    if mode in ("OUT", "IN"):
        js = G.jload(os.path.join(G.OUT, src, "as03_crown.json"))
        nv, nt = js["vertices"], js["triangles"]
        raw = open(os.path.join(G.OUT, src, js["bin"]), "rb").read()
        o = 0
        Vc = np.frombuffer(raw, "<f4", nv * 3, o).reshape(nv, 3); o += nv * 12
        o += nv * 12   # normal
        uv5 = np.frombuffer(raw, "<f4", nv * 4, o).reshape(nv, 4); o += nv * 16
        uv3 = np.frombuffer(raw, "<f4", nv * 4, o).reshape(nv, 4); o += nv * 16
        Fc = np.frombuffer(raw, "<u4", nt * 3, o).reshape(nt, 3)
        kind = uv3[:, 2]
        Cc = np.where((kind == 2)[:, None], np.array([[1.0, 0.90, 0.72, 1.0]]), np.array([[0.98, 0.96, 0.92, 1.0]]))
        np.save(tmp + "/crown_V.npy", to_bl(Vc))
        np.save(tmp + "/crown_F.npy", Fc.astype(np.int32))
        np.save(tmp + "/crown_C.npy", Cc.astype(np.float32))
        out.append(dict(name="crown", V=tmp + "/crown_V.npy", F=tmp + "/crown_F.npy", C=tmp + "/crown_C.npy"))
    # 面の内・近い海の利用者の爪（見本02 のまま）
    lay = G.jload(G.CLAWD + "/ds33_claw_layout.json")
    roles = {c["id"]: c["role"] for c in G.jload(G.ROLES)["claws"]}
    Vall = np.fromfile(G.CLAWD + "/ds33_claw_frames_f32.bin", np.float32).reshape(-1, 3)
    Tr = np.fromfile(G.CLAWD + "/ds33_claw_tris_i32.bin", np.int32).reshape(-1, 3)
    offs = np.array([c["vert_offset"] for c in lay["claws"]])
    owner = np.searchsorted(offs, Tr[:, 0], side="right") - 1
    keep_claw = np.array([roles.get(c["user_id"]) != "CREST_CROWN" or mode == "none" for c in lay["claws"]])
    Fk = Tr[keep_claw[owner]]
    np.save(tmp + "/claws_V.npy", to_bl(Vall))
    np.save(tmp + "/claws_F.npy", Fk.astype(np.int32))
    np.save(tmp + "/claws_C.npy", np.tile(np.array([[0.72, 0.72, 0.74, 1.0]], np.float32), (len(Vall), 1)))
    out.append(dict(name="claws_face", V=tmp + "/claws_V.npy", F=tmp + "/claws_F.npy", C=tmp + "/claws_C.npy"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["OUT", "IN", "none"], required=True)
    ap.add_argument("--views", default="all")
    ap.add_argument("--tag", default="")
    ap.add_argument("--src", default="", help="冠のフォルダー名（既定は mode）")
    a = ap.parse_args()
    t0 = time.time()
    tag = a.mode + (("_" + a.tag) if a.tag else "")
    tmp = os.path.join(G.OUT, "tmp", "bl_" + tag)
    outd = os.path.join(G.OUT, "render", tag)
    os.makedirs(tmp, exist_ok=True)
    os.makedirs(outd, exist_ok=True)
    meshes = prep_meshes(a.mode, tmp, src=(a.src or a.mode))
    V = views_all()
    if a.views == "quick":
        V = [v for v in V if v["name"] in ("painting_crest", "seat", "crest_az045", "crest_az180", "back65", "side_left")]
    elif a.views != "all":
        keep = set(a.views.split(","))
        V = [v for v in V if v["name"] in keep]
    G.jdump(tmp + "/meshes.json", meshes)
    G.jdump(tmp + "/views.json", V)
    G.jdump(outd + "/views.json", V)
    cmd = [BLENDER, "--background", "--factory-startup", "--python", os.path.join(os.path.dirname(os.path.abspath(__file__)), "crown_bl_render.py"),
           "--", tmp + "/meshes.json", tmp + "/views.json", outd]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1500)
    log = r.stdout[-3000:] + r.stderr[-3000:]
    open(outd + "/blender_log.txt", "w", encoding="utf-8").write(log)
    print("blender rc", r.returncode, round(time.time() - t0, 1), "s")
    if r.returncode != 0:
        print(log)


if __name__ == "__main__":
    main()
