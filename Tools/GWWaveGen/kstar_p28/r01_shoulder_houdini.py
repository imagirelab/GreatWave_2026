# -*- coding: utf-8 -*-
"""仕上げ28修正01 の案 SHOULDER：候補 K*′ P28R01SH を Houdini のシーン Houdini/Polish28/r01_shoulder.hiplc にまとめる（Steam の Houdini Indie 22.0.429 の hython）。
rec_houdini.py の写しで、置く候補だけを替えた（P28R01SH を表示、土台 P28R2rec と R4 は比べ用で表示を切る）。
シーンの中身（参照モデルの節点・パスの文字列は置かない）
  /obj/CTRL             スペアのパラメータ：設計の json、候補の GWW0 のパスと SHA-256、土台と R4 の SHA-256、作り方の説明
  /obj/P28R01SH_cand    Python SOP で候補の GWW0 を読む（kh_houdini.sop_load_gwb。Unity の z を反転、頂点の順はそのまま）
  /obj/P28R2rec_base    土台（採用中の K*′ P28R2rec、表示は切る）
  /obj/R4_before        K*′ R4（段階9、比べ用、表示は切る）
  /obj/rays_spine       原画の外輪郭 78・130・131 の射線（カメラから 90 m）と、候補の背骨（各行の列 90 の点）と背の足（列 18）の折れ線
  /obj/PaintingCam      原画カメラ PaintingCam v1（kh_common の変換）
  /obj/sea              静水面 y = 0 の格子
キャッシュは入れない（形は GWW0 をビルドのフォルダーから読む）。保存の後に文字列を検査し、cook して点の数と numpy との差を確かめる。
usage: hython rec_houdini.py <rec dir> <out.hiplc> <report.json>
"""
import os
import sys
import json
import time
import hashlib

import hou
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
KH_DIR = os.path.abspath(os.path.join(HERE, "..", "kstar_h"))
sys.path.insert(0, KH_DIR)
sys.path.insert(0, HERE)
import kh_common as KC  # noqa: E402

PYSOP_GWB = '''# 仕上げ28修正01 SHOULDER：GWW0 -> Houdini（Unity の z を反転、頂点の順はそのまま）。Code: Tools/GWWaveGen/kstar_h/kh_houdini.py
import sys
_p = r"%s"
if _p not in sys.path:
    sys.path.insert(0, _p)
import kh_houdini
kh_houdini.sop_load_gwb(hou.pwd())
''' % KH_DIR.replace("\\", "/")

PYSOP_RAYS = '''# 仕上げ28修正01 SHOULDER：原画の左の外輪郭（78・130・131）の射線と、候補の背骨（列 90）と背の足（列 18）を線で描く。
import sys, json
import numpy as np
node = hou.pwd(); geo = node.geometry()
d = json.loads(node.evalParm("rays_json"))
cam = np.array(d["cam_h"]); dirs = np.array(d["dirs_h"]); spine = np.array(d["spine_h"])
for k in range(0, len(dirs), 8):
    p0 = geo.createPoint(); p0.setPosition(hou.Vector3(*cam))
    p1 = geo.createPoint(); p1.setPosition(hou.Vector3(*(cam + 90.0 * dirs[k])))
    pr = geo.createPolygon(False); pr.addVertex(p0); pr.addVertex(p1)
for line in (spine, np.array(d["foot_h"])):
    pts = []
    for q in line:
        p = geo.createPoint(); p.setPosition(hou.Vector3(*q)); pts.append(p)
    pr = geo.createPolygon(False)
    for p in pts:
        pr.addVertex(p)
'''


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def spare(node, templates):
    g = node.parmTemplateGroup()
    for t in templates:
        g.append(t)
    node.setParmTemplateGroup(g)


def gwb_geo(obj, name, path, label, color, display):
    geo = obj.createNode("geo", name)
    for ch in geo.children():
        ch.destroy()
    py = geo.createNode("python", "load_gwb")
    spare(py, [hou.StringParmTemplate("gwb", "GWW0 file", 1, string_type=hou.stringParmType.FileReference),
               hou.StringParmTemplate("label", "Label", 1)])
    py.parm("gwb").set(path.replace("\\", "/"))
    py.parm("label").set(label)
    py.parm("python").set(PYSOP_GWB)
    col = geo.createNode("color", "tint"); col.setFirstInput(py); col.parm("class").set(2); col.parmTuple("color").set(color)
    out = geo.createNode("null", "OUT"); out.setFirstInput(col); out.setDisplayFlag(True); out.setRenderFlag(True)
    geo.layoutChildren(); geo.setDisplayFlag(display)
    geo.setComment("%s\n%s" % (label, path)); geo.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    return geo


def main():
    rd, out_hip, rep_path = sys.argv[1], sys.argv[2], sys.argv[3]
    t0 = time.time()
    cand_gwb = os.path.join(rd, "cand", "kstarP28R01SH_a45.gwb")
    design = json.load(open(os.path.join(rd, "cand", "shoulder_design.json"), encoding="utf-8"))
    base_gwb = os.path.join(KC.REPO, "Unity", "Build", "Polish", "28", "kstar_p28rec", "kstarP28R2rec_a45.gwb")
    r4_gwb = os.path.join(KC.REPO, "Unity", "Build", "Design", "28R01F", "kstar_final", "kstarR4_a45.gwb")
    hou.hipFile.clear(suppress_save_prompt=True)
    obj = hou.node("/obj")
    ctrl = obj.createNode("null", "CTRL")
    spare(ctrl, [hou.StringParmTemplate("p28_route", "Route", 1), hou.StringParmTemplate("p28_design_json", "Design json", 1),
                 hou.StringParmTemplate("p28_cand_gwb", "Candidate GWW0", 1), hou.StringParmTemplate("p28_cand_sha256", "Candidate SHA-256", 1),
                 hou.StringParmTemplate("p28_base_sha256", "Base P28R2rec SHA-256", 1),
                 hou.StringParmTemplate("p28_r4_sha256", "R4 SHA-256", 1), hou.StringParmTemplate("p28_note", "Note", 1)])
    ctrl.parm("p28_route").set("仕上げ28修正01 の案 SHOULDER：Tools/GWWaveGen/kstar_p28/r01_shoulder_build.py（numpy。土台は採用中の K*′ P28R2rec）。このシーンは候補の形を読んで見せるだけで、形は作らない。")
    ctrl.parm("p28_design_json").set(json.dumps(design, ensure_ascii=False))
    ctrl.parm("p28_cand_gwb").set(cand_gwb.replace("\\", "/"))
    ctrl.parm("p28_cand_sha256").set(sha(cand_gwb))
    ctrl.parm("p28_base_sha256").set(sha(base_gwb))
    ctrl.parm("p28_r4_sha256").set(sha(r4_gwb))
    ctrl.parm("p28_note").set("原画の頂はそのまま。原画のカメラから見て輪郭の縁より奥の背の殻（列 18..錨）だけを、錨のまわりで水平に (1 + k(c)) 倍に伸ばす"
                              "（k は c −8 → +12 で 0 → 2.0 へ少しずつ増え、奥の端の 3 m で 0 へ戻る）。原画視点の z バッファーと外殻線は土台と画素まで同じ。"
                              "参照モデルは生成器では読まない（F13-1）。座標は Unity の z を反転（kh_common）。")
    gwb_geo(obj, "P28R01SH_cand", cand_gwb, "仕上げ28修正01 SHOULDER 候補 P28R01SH", (0.74, 0.69, 0.62), True)
    gwb_geo(obj, "P28R2rec_base", base_gwb, "K*′ P28R2rec（採用中の土台、比べ用）", (0.62, 0.70, 0.62), False)
    gwb_geo(obj, "R4_before", r4_gwb, "K*′ R4（段階9、比べ用）", (0.55, 0.62, 0.72), False)
    import rays_build as RB
    xs, ys = RB.truth_outline()
    D = RB.rays_through(np.stack([xs, ys], 1))
    z = np.load(os.path.join(rd, "cand", "kstarP28R01SH_a45_rows.npz"))
    c, A, Y = z["c"], z["A"], z["Y"]
    m = (c >= -34) & (c <= 15)
    Sp = KC.O[None] + A[m, 90][:, None] * KC.T + Y[m, 90][:, None] * KC.UP + c[m][:, None] * KC.E
    Ft = KC.O[None] + A[m, 18][:, None] * KC.T + Y[m, 18][:, None] * KC.UP + c[m][:, None] * KC.E
    rj = {"cam_h": KC.u2h(KC.CAM_POS_U).tolist(), "dirs_h": KC.u2h(D).tolist(), "spine_h": KC.u2h(Sp).tolist(), "foot_h": KC.u2h(Ft).tolist()}
    rg = obj.createNode("geo", "rays_spine")
    for ch in rg.children():
        ch.destroy()
    py = rg.createNode("python", "rays_and_spine")
    spare(py, [hou.StringParmTemplate("rays_json", "Rays json", 1)])
    py.parm("rays_json").set(json.dumps(rj))
    py.parm("python").set(PYSOP_RAYS)
    col = rg.createNode("color", "tint"); col.setFirstInput(py); col.parm("class").set(1); col.parmTuple("color").set((0.9, 0.2, 0.1))
    o = rg.createNode("null", "OUT"); o.setFirstInput(col); o.setDisplayFlag(True); o.setRenderFlag(True)
    rg.layoutChildren()
    cam = obj.createNode("cam", "PaintingCam")
    cam.setWorldTransform(hou.Matrix4(KC.houdini_cam_world_matrix().tolist()))
    cam.parm("resx").set(KC.CAM_W); cam.parm("resy").set(KC.CAM_H); cam.parm("aspect").set(1.0)
    cam.parm("aperture").set(KC.HOU_APERTURE); cam.parm("focal").set(KC.houdini_focal_mm())
    cam.parm("near").set(KC.CAM_NEAR); cam.parm("far").set(KC.CAM_FAR)
    cam.setComment("PaintingCam v1（Unity の z を反転）")
    sea = obj.createNode("geo", "sea")
    for ch in sea.children():
        ch.destroy()
    g = sea.createNode("grid", "still_water_y0"); g.parm("sizex").set(300); g.parm("sizey").set(300); g.parm("rows").set(61); g.parm("cols").set(61)
    so = sea.createNode("null", "OUT"); so.setFirstInput(g); so.setDisplayFlag(True); so.setRenderFlag(True)
    obj.layoutChildren()
    out = hou.node("/obj/P28R01SH_cand/OUT")
    geo = out.geometry()
    P = np.frombuffer(geo.pointFloatAttribValuesAsString("P"), np.float32).reshape(-1, 3).astype(np.float64)
    G = KC.read_gwb(cand_gwb)
    diff = float(np.abs(KC.h2u(P) - G["X"]).max()) if len(P) == len(G["X"]) else None
    rg_n = len(hou.node("/obj/rays_spine/OUT").geometry().points())
    os.makedirs(os.path.dirname(out_hip), exist_ok=True)
    hou.hipFile.save(out_hip)
    txt = open(out_hip, "rb").read()
    leaks = [s for s in (b"wave_repair", b"research/model", b"research\\\\model", b"research\\model", b"zbrush", b"reality scan") if s in txt]
    rep = {"hip": out_hip, "hip_bytes": os.path.getsize(out_hip), "hip_sha256": sha(out_hip), "houdini": hou.applicationVersionString(),
           "points_candidate": len(P), "prims_candidate": len(geo.prims()), "max_abs_diff_vs_gwb_m": diff,
           "rays_spine_points": rg_n, "reference_string_leaks": [s.decode() for s in leaks],
           "candidate_gwb_sha256": sha(cand_gwb), "seconds": round(time.time() - t0, 1)}
    json.dump(rep, open(rep_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(rep, ensure_ascii=False))


if __name__ == "__main__":
    main()
