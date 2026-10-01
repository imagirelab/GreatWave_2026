# -*- coding: utf-8 -*-
"""仕上げ28 第1回 FACE-SWAP：Houdini のシーン Houdini/Polish28/faceswap.hiplc を組んで保存し、開き直して確かめる（hython だけ）。

Steam の Houdini Indie 22.0.429 の hython で動かす（Program Files の 21.0.729 は使わない）。hython には numpy はあるが scipy・cv2 がないので、
当てはめ（原画視点の輪郭の測り、faceswap_edgefit / faceswap_bsfit）は py -3.10 の faceswap_build.py が行い、このシーンは
  R4 の格子（kstar_final の rows npz）→ faceswap（候補との差を点の属性 fs_disp として持ち、CTRL の blend で 0 = R4 〜 1 = 候補）→ OUT
と、確かめ用の線（原画カメラの左の外輪郭 78・130・131 の射線、その輪郭を描く点の列：R4 の頂の線と候補の前の唇の上面の線）、PaintingCam を持つ。
形はシーンに保存しない（毎回 npz から cook する。.hiplc は小さい）。参照モデル（他者の作品）の節点・パスの文字列は置かない（保存の前に確かめる）。
座標：Houdini = Unity の z の符号を反転（kh_common の約束）。四角形の頂点順は K* の三角形と同じ向き。

  hython faceswap_houdini.py --cand <cand_rows.npz> --out <faceswap.hiplc> [--verify <report.json>]
"""
import os
import sys
import json
import time
import argparse

import numpy as np
import hou

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import faceswap_common as F  # noqa: E402  （numpy と json だけ）
KC = F.KC

PYSOP_SHEET = r'''
import sys, numpy as np, hou
sys.path.insert(0, r"%(here)s")
import faceswap_common as F
node = hou.pwd(); geo = node.geometry()
ctrl = hou.node("../CTRL")
z = np.load(ctrl.parm("r4_rows").eval())
c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
nv, nu = A.shape
X = F.KC.world(c, A, Y).reshape(-1, 3) * np.array([1.0, 1.0, -1.0])
geo.createPoints([tuple(p) for p in X])
iu, iv = np.meshgrid(np.arange(nu - 1), np.arange(nv - 1))
a = (iv * nu + iu).ravel(); b = ((iv + 1) * nu + iu).ravel(); cc = (iv * nu + iu + 1).ravel(); d = ((iv + 1) * nu + iu + 1).ravel()
geo.createPolygons([tuple(q) for q in np.stack([a, b, d, cc], -1).tolist()])
for nm, v in (("row", np.repeat(np.arange(nv), nu)), ("col", np.tile(np.arange(nu), nv))):
    geo.addAttrib(hou.attribType.Point, nm, 0)
    geo.setPointIntAttribValues(nm, v.tolist())
geo.addAttrib(hou.attribType.Point, "c_sec", 0.0)
geo.setPointFloatAttribValuesFromString("c_sec", np.repeat(c, nu).astype(np.float32).tobytes())
'''

PYSOP_SWAP = r'''
import sys, numpy as np, hou
sys.path.insert(0, r"%(here)s")
import faceswap_common as F
node = hou.pwd(); geo = node.geometry()
ctrl = hou.node("../CTRL")
blend = ctrl.parm("blend").eval()
zr = np.load(ctrl.parm("r4_rows").eval()); zc = np.load(ctrl.parm("cand_rows").eval())
X0 = F.KC.world(zr["c"].astype(float), zr["A"].astype(float), zr["Y"].astype(float)).reshape(-1, 3)
X1 = F.KC.world(zc["c"].astype(float), zc["A"].astype(float), zc["Y"].astype(float)).reshape(-1, 3)
D = (X1 - X0) * np.array([1.0, 1.0, -1.0])
P = np.frombuffer(geo.pointFloatAttribValuesAsString("P"), np.float32).reshape(-1, 3).astype(np.float64)
geo.setPointFloatAttribValuesFromString("P", (P + blend * D).astype(np.float32).tobytes())
geo.addAttrib(hou.attribType.Point, "fs_disp", (0.0, 0.0, 0.0))
geo.setPointFloatAttribValuesFromString("fs_disp", D.astype(np.float32).tobytes())
geo.addAttrib(hou.attribType.Point, "fs_disp_len", 0.0)
geo.setPointFloatAttribValuesFromString("fs_disp_len", np.linalg.norm(D, axis=1).astype(np.float32).tobytes())
'''

PYSOP_LINES = r'''
import sys, numpy as np, hou
sys.path.insert(0, r"%(here)s")
import faceswap_common as F
node = hou.pwd(); geo = node.geometry()
ctrl = hou.node("../CTRL")
geo.addAttrib(hou.attribType.Prim, "name", "")
geo.addAttrib(hou.attribType.Point, "Cd", (1.0, 1.0, 1.0))
def poly(P, name, col):
    pts = geo.createPoints([tuple(p) for p in (np.asarray(P) * np.array([1.0, 1.0, -1.0]))])
    for p in pts:
        p.setAttribValue("Cd", col)
    pr = geo.createPolygon(is_closed=False)
    for p in pts:
        pr.addVertex(p)
    pr.setAttribValue("name", name)
# 左の外輪郭 78・130・131 の射線（原画カメラから 90 m、20 本に 1 本）
seg = F.outline_segments()
L = np.vstack([seg["78"], seg["130"][1:], seg["131"][1:]])
d = F.pixel_rays(L[::20])
for k, dd in enumerate(d):
    poly([F.KC.CAM_POS_U, F.KC.CAM_POS_U + 90.0 * dd], "ray_%%03d" %% k, (0.3, 0.6, 1.0))
# 輪郭を描く点の列（R4 の頂 と 候補の前の唇の上面）
for key, col in (("r4_rows", (1.0, 0.2, 0.2)), ("cand_rows", (1.0, 0.85, 0.1))):
    z = np.load(ctrl.parm(key).eval())
    g = F.outline_generators(z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float), n_per=40)
    P = [F.KC.world(np.array([x["c"]]), np.array([[x["a"]]]), np.array([[x["y"]]]))[0, 0] for x in g]
    poly(P, "generators_" + key.split("_")[0], col)
'''


def build(a):
    t0 = time.time()
    hou.hipFile.clear(suppress_save_prompt=True)
    obj = hou.node("/obj")
    # PaintingCam（Houdini 座標）
    cam = obj.createNode("cam", "PaintingCam")
    M = KC.houdini_cam_world_matrix()
    cam.setWorldTransform(hou.Matrix4([list(r) for r in M]))
    cam.parm("resx").set(KC.CAM_W); cam.parm("resy").set(KC.CAM_H)
    cam.parm("aperture").set(KC.HOU_APERTURE); cam.parm("focal").set(KC.houdini_focal_mm())
    cam.parm("near").set(KC.CAM_NEAR); cam.parm("far").set(KC.CAM_FAR)
    cam.setComment("PaintingCam v1 (Unity (0,3,-62) -> (-2.5,9.7,4), vfov 26, 1920x1080), mirrored to Houdini (z -> -z).")
    geo = obj.createNode("geo", "faceswap")
    for ch in geo.children():
        ch.destroy()
    ctrl = geo.createNode("null", "CTRL")
    g = ctrl.parmTemplateGroup()
    f = hou.FolderParmTemplate("fs", "Face swap (Polish 28 round 1)", folder_type=hou.folderType.Simple)
    f.addParmTemplate(hou.FloatParmTemplate("blend", "Blend R4 -> candidate", 1, default_value=(1.0,), min=0.0, max=1.0))
    f.addParmTemplate(hou.StringParmTemplate("r4_rows", "R4 rows (kstar_final)", 1, default_value=(F.R4_ROWS.replace("\\", "/"),)))
    f.addParmTemplate(hou.StringParmTemplate("cand_rows", "Candidate rows (faceswap_build.py)", 1, default_value=(os.path.abspath(a.cand).replace("\\", "/"),)))
    f.addParmTemplate(hou.LabelParmTemplate("about", "About", column_labels=(
        "FACE-SWAP: the left painting outline 78/130/131 is drawn by the forward lip top of rows nearer the camera, not by the back's crest.",)))
    g.append(f)
    ctrl.setParmTemplateGroup(g)
    ctrl.setColor(hou.Color(0.9, 0.75, 0.2))
    here = HERE.replace("\\", "/")

    def py(name, code, inp=None, comment=""):
        n = geo.createNode("python", name)
        n.parm("python").set(code % {"here": here})
        if inp is not None:
            n.setFirstInput(inp)
        n.setComment(comment)
        return n
    sheet = py("r4_sheet", PYSOP_SHEET, None, "K*' R4 (kstar_final rows npz) as the 400x240 sheet (points row/col/c_sec, quads in the K* winding).")
    swap = py("faceswap", PYSOP_SWAP, sheet, "FACE-SWAP displacement (candidate - R4) as point attribute fs_disp; P += blend * fs_disp. "
              "The displacement is made by faceswap_build.py (numpy; the painting-outline fit needs the evaluator, which hython cannot import).")
    nrm = geo.createNode("normal", "N"); nrm.setFirstInput(swap)
    vis = geo.createNode("attribwrangle", "show_disp"); vis.setFirstInput(nrm)
    vis.parm("snippet").set("float t = clamp(@fs_disp_len / 1.5, 0, 1);\n@Cd = lerp({0.82, 0.80, 0.74}, {0.95, 0.35, 0.1}, t);")
    vis.setComment("Clay colour; orange where the face swap moved the sheet (1.5 m = full orange).")
    out = geo.createNode("null", "OUT"); out.setFirstInput(vis)
    out.setDisplayFlag(True); out.setRenderFlag(True); out.setColor(hou.Color(0.3, 0.8, 0.3))
    lines = geo.createNode("python", "check_lines")
    lines.parm("python").set(PYSOP_LINES % {"here": here})
    lines.setComment("Check lines: PaintingCam rays of the left outline 78/130/131 (blue), the points that draw it on R4 (red, the back's crest) "
                     "and on the candidate (yellow, the forward lip top).")
    geo.layoutChildren()
    note = geo.createStickyNote("fs_note")
    note.setText("Polish 28 round 1: FACE-SWAP\nr4_sheet -> faceswap (blend) -> N -> show_disp -> OUT;  check_lines (rays + outline-drawing points).\n"
                 "Generator: Tools/GWWaveGen/kstar_p28/faceswap_build.py (py -3.10). The reference model (someone else's sculpture) is never read.")
    note.setSize(hou.Vector2(8, 1.6))
    obj.layoutChildren()
    leaks = []
    for n in hou.node("/").allSubChildren():
        for pm in n.parms():
            try:
                v = pm.unexpandedString()
            except Exception:
                continue
            if "wave_repair" in v or "research/model" in v or "reality scan" in v or "北斋参考" in v:
                leaks.append(n.path() + "/" + pm.name())
    if leaks:
        raise SystemExit("reference-model strings in the scene: %s" % leaks)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    hou.hipFile.save(a.out)
    return {"built_s": round(time.time() - t0, 2), "reference_path_leaks": len(leaks)}


def verify(a, rep):
    t0 = time.time()
    hou.hipFile.load(a.out, suppress_save_prompt=True, ignore_load_warnings=True)
    out = hou.node("/obj/faceswap/OUT")
    geo = out.geometry()
    P = np.frombuffer(geo.pointFloatAttribValuesAsString("P"), np.float32).reshape(-1, 3).astype(np.float64)
    z = np.load(a.cand)
    X = KC.world(z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)).reshape(-1, 3) * np.array([1.0, 1.0, -1.0])
    d = np.linalg.norm(P - X, axis=1)
    lines = hou.node("/obj/faceswap/check_lines").geometry()
    names = sorted(set(p.attribValue("name") for p in lines.prims()))
    rep.update({"verify_s": round(time.time() - t0, 2), "points": len(geo.points()), "prims": len(geo.prims()),
                "max_diff_to_candidate_m": float(d.max()), "check_line_prims": len(lines.prims()),
                "check_line_names_sample": names[:3] + names[-2:], "houdini_version": hou.applicationVersionString(),
                "hip": a.out.replace("\\", "/"), "hip_bytes": os.path.getsize(a.out), "hip_sha256": KC.sha256(a.out)})
    cam = hou.node("/obj/PaintingCam")
    rep["cam_focal_mm"] = cam.parm("focal").eval()
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--verify", default=None)
    a = ap.parse_args()
    rep = build(a)
    if a.verify:
        rep = verify(a, rep)
        json.dump(rep, open(a.verify, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(rep, ensure_ascii=False))


if __name__ == "__main__":
    main()
