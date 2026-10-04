# -*- coding: utf-8 -*-
"""美術の見本03 の作り B1-2：冠（IN・OUT）を入れた時の原画視点の形の関門（78・130・131 定義どおりの読み、132・72 σ12）。

Unity の描画はしない（Unity は B2 が使う。unity.lock を争わない）。代わりに、見本02 修正の回 1 の Unity の原画視点の色区 ID の画
（`render/AS02C_A/t28_white/t28/render/af28r01_class_ids.png`、3840×2160、爪なし、空 = (255,255,255)）に、numpy の z バッファで描いた
「面の内・近い海の利用者の爪（見本02 のまま）＋冠のメッシュ」の覆いを重ね、空の画素のうち覆われた所を白の色区にする（空の境だけが関門に効く）。
重ねた画を、見本02 の場面の写しの中に置き、見本02 と同じ道具（as02_gates.py → pl28u_tstar_eval.py・pl28u_regress.lfgates）で測る。
確かめ：同じ方法で見本02 の 83 本の爪を重ねた画は、Unity の爪ありの画（t28_claws）と空の画素の差がほぼ 0 になること（calibration）。
使い方：py -3.10 -B Tools/GWWaveGen/as03/crown_gates.py --mode IN（OUT・calib）
出力：Unity/Build/Polish/sample03/crown/gates/<mode>/（scene の写し、pl28u_regress.json、gates_<mode>.json、重ね図）
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crown_common as G  # noqa: E402

SRC = G.S02 + "/assemble/render/AS02C_A"
W2, H2 = 3840, 2160


def imread(p):
    return cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR)[:, :, ::-1]


def imwrite(p, rgb):
    cv2.imencode(".png", rgb[:, :, ::-1].copy())[1].tofile(p)


def coverage(tris):
    cam = G.painting_cam(W2, H2)
    idb, zb = G.U.raster(cam, tris, np.ones(len(tris), np.int64))
    return idb > 0


def sample02_claws(only_non_crest=True):
    lay = G.jload(G.CLAWD + "/ds33_claw_layout.json")
    roles = {c["id"]: c["role"] for c in G.jload(G.ROLES)["claws"]}
    V = np.fromfile(G.CLAWD + "/ds33_claw_frames_f32.bin", np.float32).reshape(-1, 3).astype(np.float64)
    Tr = np.fromfile(G.CLAWD + "/ds33_claw_tris_i32.bin", np.int32).reshape(-1, 3)
    offs = np.array([c["vert_offset"] for c in lay["claws"]])
    owner = np.searchsorted(offs, Tr[:, 0], side="right") - 1
    keep = np.array([(roles.get(c["user_id"]) != "CREST_CROWN") or (not only_non_crest) for c in lay["claws"]])
    return V[Tr[keep[owner]]]


def crown_tris(mode):
    js = G.jload(os.path.join(G.OUT, mode, "as03_crown.json"))
    nv, nt = js["vertices"], js["triangles"]
    raw = open(os.path.join(G.OUT, mode, js["bin"]), "rb").read()
    V = np.frombuffer(raw, "<f4", nv * 3, 0).reshape(nv, 3).astype(np.float64)
    o = nv * 4 * (3 + 3 + 4 + 4)
    F = np.frombuffer(raw, "<u4", nt * 3, o).reshape(nt, 3).astype(np.int64)
    return V[F], js


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["IN", "OUT", "calib"], required=True)
    ap.add_argument("--src", default="", help="冠のフォルダー名（既定は mode）")
    a = ap.parse_args()
    t0 = time.time()
    src = a.src or a.mode
    out = os.path.join(G.OUT, "gates", src)
    scene = os.path.join(out, "scene")
    if os.path.isdir(scene):
        shutil.rmtree(scene)
    os.makedirs(scene + "/t28_claws", exist_ok=True)
    shutil.copytree(SRC + "/t28_white/t28", scene + "/t28_claws/t28")
    base = imread(SRC + "/t28_white/t28/render/af28r01_class_ids.png")
    sky = np.all(base == 255, -1)
    if a.mode == "calib":
        cov = coverage(sample02_claws(only_non_crest=False))
        src_note = "見本02 の 83 本の爪（置き方 A のまま）"
        crown_info = None
    else:
        tc, js = crown_tris(src)
        cov = coverage(np.concatenate([sample02_claws(True), tc]))
        src_note = "面の内・近い海の爪 35 本（見本02 のまま）＋冠 %s（%d 頂点）" % (src, js["vertices"])
        crown_info = js
    new = base.copy()
    # 覆われた空の画素を、白の色区の色（画で最も多い空でない色）にする
    cols, cnts = np.unique(base[~sky].reshape(-1, 3), axis=0, return_counts=True)
    white_col = cols[np.argmax(cnts)]
    fill = sky & cov
    new[fill] = white_col
    imwrite(scene + "/t28_claws/t28/render/af28r01_class_ids.png", new)
    res = {"mode": a.mode, "source_note_ja": src_note, "sky_px_base": int(sky.sum()), "sky_px_covered_by_added": int(fill.sum()),
           "fill_colour": white_col.tolist(), "base_class_ids_sha256": G.sha(SRC + "/t28_white/t28/render/af28r01_class_ids.png"),
           "new_class_ids_sha256": G.sha(scene + "/t28_claws/t28/render/af28r01_class_ids.png")}
    if a.mode == "calib":
        ref = imread(SRC + "/t28_claws/t28/render/af28r01_class_ids.png")
        sky_ref = np.all(ref == 255, -1)
        sky_new = np.all(new == 255, -1)
        res["calib"] = {"sky_px_unity_claws": int(sky_ref.sum()), "sky_px_numpy_composite": int(sky_new.sum()),
                        "xor_px": int((sky_ref ^ sky_new).sum()), "unity_claws_covered_sky_px": int((sky & ~sky_ref).sum())}
    # 重ね図（原画視点の頂と唇の所、2 倍の画の 1/2）
    vis = np.full((H2, W2, 3), 235, np.uint8)
    vis[~sky] = (120, 120, 130)
    vis[fill] = (230, 60, 40)
    cv2.imencode(".png", cv2.resize(vis[:1400, 1000:3400][:, :, ::-1], (1200, 700), interpolation=cv2.INTER_AREA))[1].tofile(os.path.join(out, "overlay_sky_fill.png"))
    # 見本02 と同じ道具で測る
    for f in ("ds27_tstar_remeasure.json", "pl28u_tstar_verdict.json"):
        p = os.path.join(scene, "t28_claws", f)
        if os.path.exists(p):
            os.remove(p)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-B", G.REPO + "/Tools/GWWaveGen/as02/as02_gates.py", "--scene", os.path.relpath(scene, G.REPO).replace("\\", "/"),
                        "--kstar", "rec"], cwd=G.REPO, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=1500)
    open(os.path.join(out, "gates_log.txt"), "w", encoding="utf-8").write(r.stdout[-6000:] + r.stderr[-6000:])
    reg = G.jload(os.path.join(scene, "pl28u_regress.json"))
    st = reg["sets"]["t28_claws"]
    sil = st["strict"]["silhouettes_definition_reading"]
    lf = st["large_form"]["s12"]
    g = {"78": sil["78"]["max_px"], "130": sil["130"]["max_px"], "131": sil["131"]["max_px"], "132_s12": lf["132_max_px"], "72_s12_p95": lf["72_p95_px"]}
    res["gates_px"] = g
    res["pass_all_le_4px"] = bool(all(v <= 4.0 for v in g.values()))
    res["sample02_reference_px"] = {"78": 2.741, "130": 3.5815, "131": 3.4419, "132_s12": 3.5576, "72_s12_p95": 3.6577}
    res["method_ja"] = __doc__.strip()
    res["elapsed_s"] = round(time.time() - t0, 1)
    G.jdump(os.path.join(out, "gates_%s.json" % src), res)
    print(json.dumps({k: res[k] for k in res if k not in ("method_ja",)}, ensure_ascii=False)[:1500])


if __name__ == "__main__":
    main()
