# -*- coding: utf-8 -*-
"""仕上げ28 第1回（back-first）の K*′ 候補を Houdini のシーンにする（hython、Steam Houdini Indie 22.0.429）。

  /obj/CTRL             候補の出典（設計の json・行の npz・OBJ の SHA-256、座標の約束）を文字列の spare parm で持つ
  /obj/PaintingCam      原画カメラ PaintingCam v1（kh_common.houdini_cam_world_matrix、背景は評価器の表示の枠の原画）
  /obj/kstar_p28_backfirst  file SOP（候補の OBJ、Unity 座標）→ transform（z を反転：Houdini の右手系）→ row / col の点属性 → OUT
  /obj/sea              静水面の格子（y = 0 から 3 cm 下）
参照モデル（他者の作品）を読む節点・文字列は置かない（保存の後に文字列を走査して確かめる）。
usage: hython backfirst_houdini.py <candidate_prefix（…/kstarP28bf_a45）> <out.hiplc> <report.json>
"""
import os
import sys
import json

import hou  # noqa: F401

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"G:\Unity\GreatWave_2026_Fresh"
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "kstar_h"))
import numpy as np  # noqa: E402
import kh_common as KC  # noqa: E402

FORBIDDEN = (b"wave_repair", b"research/model", b"research\\model", b"zbrush", b"reality scan", b"\xe5\x8c\x97\xe6\x96\x8e\xe5\x8f\x82\xe8\x80\x83")


def main():
    pre, out_hip, rep_path = sys.argv[1], sys.argv[2], sys.argv[3]
    obj_path = (pre + ".obj").replace("\\", "/")
    rows_path = pre + "_rows.npz"
    rep = {"candidate_obj": obj_path, "obj_sha256": KC.sha256(pre + ".obj"), "rows_sha256": KC.sha256(rows_path),
           "gwb_sha256": KC.sha256(pre + ".gwb"), "houdini": hou.applicationVersionString()}
    hou.hipFile.clear(suppress_save_prompt=True)
    obj = hou.node("/obj")
    ctrl = obj.createNode("null", "CTRL")
    ptg = ctrl.parmTemplateGroup()
    for nm, lab in (("p28_round", "Round"), ("p28_obj", "Candidate OBJ (Unity coords)"), ("p28_obj_sha256", "OBJ SHA-256"),
                    ("p28_rows_sha256", "rows npz SHA-256"), ("p28_convention", "Coordinate convention")):
        ptg.append(hou.StringParmTemplate(nm, lab, 1))
    ctrl.setParmTemplateGroup(ptg)
    ctrl.parm("p28_round").set("Polish 28 round 1 (back-first): K*' candidate kstarP28bf_a45 (400x240 sheet, K* landmarks/UVs)")
    ctrl.parm("p28_obj").set(obj_path)
    ctrl.parm("p28_obj_sha256").set(rep["obj_sha256"])
    ctrl.parm("p28_rows_sha256").set(rep["rows_sha256"])
    conv = ("Houdini (right-handed, Y up, m) = Unity (left-handed, Y up, m) with z negated: (x,y,z)_H = (x,y,-z)_U. "
            "Section frame (Unity): world = O + a*T + y*UP + c*E, O=%s T=%s E=%s; rows = constant-c planes." % (
                KC.O.round(6).tolist(), KC.T.round(9).tolist(), KC.E.round(9).tolist()))
    ctrl.parm("p28_convention").set(conv)
    # PaintingCam
    cam = obj.createNode("cam", "PaintingCam")
    cam.setWorldTransform(hou.Matrix4(KC.houdini_cam_world_matrix().tolist()))
    cam.parm("resx").set(KC.CAM_W); cam.parm("resy").set(KC.CAM_H); cam.parm("aspect").set(1.0)
    cam.parm("aperture").set(KC.HOU_APERTURE); cam.parm("focal").set(KC.houdini_focal_mm())
    cam.parm("near").set(KC.CAM_NEAR); cam.parm("far").set(KC.CAM_FAR)
    if os.path.isfile(KC.PLATE):
        cam.parm("vm_background").set(KC.PLATE.replace("\\", "/"))
    rep["cam"] = {"t": list(cam.parmTuple("t").eval()), "r": list(cam.parmTuple("r").eval()), "focal_mm": cam.evalParm("focal")}
    # candidate geometry
    geo = obj.createNode("geo", "kstar_p28_backfirst")
    for ch in geo.children():
        ch.destroy()
    f = geo.createNode("file", "candidate_obj")
    f.parm("file").set(obj_path)
    xf = geo.createNode("xform", "unity_to_houdini_z_negate"); xf.setFirstInput(f)
    xf.parmTuple("s").set((1.0, 1.0, -1.0))
    aw = geo.createNode("attribwrangle", "row_col"); aw.setFirstInput(xf)
    aw.parm("class").set(2)
    aw.parm("snippet").set("i@row = @ptnum / %d;\ni@col = @ptnum %% %d;\nf@c_m = 0;" % (KC.NU, KC.NU))
    nm = geo.createNode("normal", "normals"); nm.setFirstInput(aw)
    out = geo.createNode("null", "OUT"); out.setFirstInput(nm); out.setDisplayFlag(True); out.setRenderFlag(True)
    geo.layoutChildren()
    # sea
    sea = obj.createNode("geo", "sea")
    for ch in sea.children():
        ch.destroy()
    g = sea.createNode("grid", "still_water_y0")
    g.parm("orient").set("zx"); g.parm("sizex").set(600); g.parm("sizey").set(600)
    g.parm("rows").set(121); g.parm("cols").set(121)
    oh = KC.u2h(KC.O)
    g.parm("tx").set(float(oh[0])); g.parm("ty").set(-0.03); g.parm("tz").set(float(oh[2]))
    so = sea.createNode("null", "OUT"); so.setFirstInput(g); so.setDisplayFlag(True)
    sea.layoutChildren()
    obj.layoutChildren()
    # verify against the rows
    gg = out.geometry()
    P = np.array(gg.pointFloatAttribValues("P"), float).reshape(-1, 3)
    z = np.load(rows_path)
    X = KC.world(z["c"], z["A"], z["Y"]).reshape(-1, 3)
    Xh = KC.u2h(X)
    rep["points"] = int(len(P)); rep["prims"] = int(len(gg.prims()))
    rep["max_abs_diff_m_vs_rows"] = float(np.abs(P - Xh).max()) if len(P) == len(Xh) else None
    hou.hipFile.save(out_hip.replace("\\", "/"))
    b = open(out_hip, "rb").read()
    rep["reference_model_string_hits"] = {k.decode("utf-8", "replace"): b.count(k) for k in FORBIDDEN}
    rep["hip_sha256"] = KC.sha256(out_hip)
    rep["hip_bytes"] = os.path.getsize(out_hip)
    json.dump(rep, open(rep_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(rep, ensure_ascii=False))


main()
