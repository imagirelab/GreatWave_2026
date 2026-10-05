# -*- coding: utf-8 -*-
"""設計28修正01：最後の一コマ K*′ を Houdini で作るための基本シーンを組む（hython、Houdini Indie 22.0 → .hiplc）。

/obj の中身
  CTRL                 スペアのパラメータ（大きな形の参照の VDB の値）と、座標の約束のメモ
  PaintingCam          原画カメラ PaintingCam v1（Unity (0,3,-62)→(-2.5,9.7,4)、縦 26°、1920×1080）を Houdini 座標へ。
                       背景 vm_background = 評価器と同じ表示フレームの原画（Unity/Build/Q20H/plate/、kh_plate.py）
  sea                  静水面 y = 0 の格子（600 m 角）
  kstar_current        今の K*（26修正01、GWW0 を Python SOP で読む。点の属性 col / row / uv / uv2 / c_sec）
  kstar_loop2          第 2 回 K*′（Q20/final）
  cand_A4              第 3 回の候補 A4（Q20L3/candA4）
  cand_A3b             第 3 回の候補 A3b（Q20L3/candA3b。まだ無ければ空と警告）
  refmodel             参照モデル（他者の作品。読み取りのみ、SHA-256 照合済みのパスだけを保存。形はシーンに入れない）を
                       解 B（align_B_upright、ルーブリックの置き方）で Unity へ、さらに Houdini 座標へ置く xform
  refmodel_largeform   参照モデルの大きな形（指＝爪を消した）：VDB → 開く（侵食→膨張）→ ガウスの平滑 → 多角形
  candidate_work       作業の場所（既定は K* を読み込むだけ）。出口 OUT を kh_bridge.py h2g が格子へ移す
どの SOP も固定（lock）しないので、.hiplc に形状は入らない（キャッシュなし）。

usage: hython kh_build_scene.py [--out <hiplc>] [--verify <report.json>] [--no-ref]
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
import kh_common as KC  # noqa: E402
import kh_houdini as KH  # noqa: E402

PYSOP_GWB = '''# kstar_h: GWW0 -> Houdini (Unity z negated, vertex order kept). Code: Tools/GWWaveGen/kstar_h/kh_houdini.py
import sys
_p = r"%s"
if _p not in sys.path:
    sys.path.insert(0, _p)
import kh_houdini
kh_houdini.sop_load_gwb(hou.pwd())
''' % HERE


def spare(node, templates):
    g = node.parmTemplateGroup()
    for t in templates:
        g.append(t)
    node.setParmTemplateGroup(g)


def gwb_object(obj, name, path, label, color, display):
    geo = obj.createNode("geo", name)
    for ch in geo.children():
        ch.destroy()
    py = geo.createNode("python", "load_gwb")
    spare(py, [hou.StringParmTemplate("gwb", "GWW0 file", 1, string_type=hou.stringParmType.FileReference),
               hou.StringParmTemplate("label", "Label", 1)])
    py.parm("gwb").set(path.replace("\\", "/"))
    py.parm("label").set(label)
    py.parm("python").set(PYSOP_GWB)
    col = geo.createNode("color", "tint")
    col.setFirstInput(py)
    col.parm("class").set(2)
    col.parmTuple("color").set(color)
    out = geo.createNode("null", "OUT")
    out.setFirstInput(col)
    out.setDisplayFlag(True); out.setRenderFlag(True)
    geo.layoutChildren()
    geo.setDisplayFlag(display)
    geo.setComment("%s\n%s" % (label, path))
    return geo


def build(args):
    t0 = time.time()
    hou.hipFile.clear(suppress_save_prompt=True)
    obj = hou.node("/obj")
    rep = {"hip": args.out, "hython": hou.applicationVersionString(), "license": str(hou.licenseCategory())}

    # ---------------- CTRL
    ctrl = obj.createNode("null", "CTRL")
    spare(ctrl, [
        hou.FloatParmTemplate("lf_voxel", "Large-form VDB voxel (m)", 1, (0.15,)),
        hou.FloatParmTemplate("lf_open", "Large-form opening radius (m) - removes fingers thinner than 2r", 1, (0.45,)),
        hou.IntParmTemplate("lf_smooth_iter", "Large-form Gaussian smoothing iterations", 1, (6,)),
        hou.FloatParmTemplate("lf_smooth_width", "Large-form Gaussian filter radius (voxels)", 1, (2.0,)),
        hou.StringParmTemplate("kh_convention", "Coordinate convention", 1),
        hou.StringParmTemplate("kh_unity_cam", "PaintingCam v1 (Unity)", 1),
    ])
    conv = ("Houdini (right-handed, Y up, m) = Unity (left-handed, Y up, m) with z negated: (x,y,z)_H = (x,y,-z)_U. "
            "Triangle vertex order kept (Houdini's clockwise normals then point +Y on the flat sea). "
            "Section frame (Unity): world = O + a*T + y*UP + c*E, O=%s T=%s E=%s; rows = constant-c planes." % (
                KC.O.round(6).tolist(), KC.T.round(9).tolist(), KC.E.round(9).tolist()))
    ctrl.parm("kh_convention").set(conv)
    ctrl.parm("kh_unity_cam").set("position (0,3,-62), look-at (-2.5,9.7,4), up +Y (Unity LookAt), vertical FOV 26 deg, 1920x1080, near 0.1, far 900")
    rep["convention"] = conv

    # ---------------- PaintingCam
    cam = obj.createNode("cam", "PaintingCam")
    M = KC.houdini_cam_world_matrix()
    cam.setWorldTransform(hou.Matrix4(M.tolist()))
    cam.parm("resx").set(KC.CAM_W); cam.parm("resy").set(KC.CAM_H)
    cam.parm("aspect").set(1.0)
    cam.parm("aperture").set(KC.HOU_APERTURE)
    cam.parm("focal").set(KC.houdini_focal_mm())
    cam.parm("near").set(KC.CAM_NEAR); cam.parm("far").set(KC.CAM_FAR)
    if os.path.isfile(KC.PLATE):
        cam.parm("vm_background").set(KC.PLATE.replace("\\", "/"))
    else:
        rep["warn_plate"] = "plate missing: run kh_plate.py"
    cam.setComment("PaintingCam v1 (Unity z negated). Background = painting in the evaluator's display frame.")
    rep["cam"] = {"t": list(cam.parmTuple("t").eval()), "r": list(cam.parmTuple("r").eval()), "focal_mm": cam.evalParm("focal"),
                  "aperture_mm": cam.evalParm("aperture"), "res": [cam.evalParm("resx"), cam.evalParm("resy")],
                  "plate": cam.evalParm("vm_background")}

    # ---------------- sea
    sea = obj.createNode("geo", "sea")
    for ch in sea.children():
        ch.destroy()
    g = sea.createNode("grid", "still_water_y0")
    g.parm("orient").set("zx"); g.parm("sizex").set(600); g.parm("sizey").set(600)
    g.parm("rows").set(121); g.parm("cols").set(121)
    oh = KC.u2h(KC.O)
    g.parm("tx").set(float(oh[0])); g.parm("ty").set(-0.03); g.parm("tz").set(float(oh[2]))   # 3 cm 下げて平らな海と重ならない
    sc = sea.createNode("color", "tint"); sc.setFirstInput(g); sc.parm("class").set(2); sc.parmTuple("color").set((0.42, 0.50, 0.58))
    so = sea.createNode("null", "OUT"); so.setFirstInput(sc); so.setDisplayFlag(True); so.setRenderFlag(True)
    sea.layoutChildren()

    # ---------------- GWW0 sheets
    gwb_object(obj, "kstar_current", KC.KSTAR_GWB, "K* 26修正01 (current)", (0.74, 0.69, 0.62), True)
    gwb_object(obj, "kstar_loop2", KC.LOOP2_GWB, "K*' loop 2 (Q20/final)", (0.62, 0.74, 0.66), False)
    gwb_object(obj, "cand_A4", KC.A4_GWB, "round 3 candidate A4 (Q20L3/candA4)", (0.66, 0.68, 0.80), False)
    gwb_object(obj, "cand_A3b", KC.A3B_GWB, "round 3 candidate A3b (Q20L3/candA3b, may appear later)", (0.80, 0.66, 0.70), False)

    # ---------------- reference model (someone else's sculpture: path only, SHA checked, never locked)
    if not args.no_ref:
        h = KC.sha256(KC.REF_OBJ).upper()
        if not (h.startswith(KC.REF_SHA_HEAD) and h.endswith(KC.REF_SHA_TAIL)):
            raise SystemExit("reference model SHA-256 mismatch: %s" % h)
        rep["refmodel_sha256"] = h
        al = json.load(open(KC.ALIGN_B, encoding="utf-8"))
        M4 = np.array(al["obj_to_unity_4x4"], np.float64)
        U4 = np.eye(4); U4[:3, :3] = KC.U2H
        Mh = (U4 @ M4).T                       # Houdini row-vector convention
        ref = obj.createNode("geo", "refmodel")
        for ch in ref.children():
            ch.destroy()
        f = ref.createNode("file", "reference_obj_readonly")
        f.parm("file").set(KC.REF_OBJ.replace("\\", "/"))
        x = ref.createNode("xform", "align_B_to_houdini")
        x.setFirstInput(f)
        ex = hou.Matrix4(Mh.tolist()).explode(transform_order="srt", rotate_order="xyz")
        x.parm("xOrd").set("srt"); x.parm("rOrd").set("xyz")
        x.parmTuple("t").set(tuple(ex["translate"])); x.parmTuple("r").set(tuple(ex["rotate"]))
        x.parmTuple("s").set(tuple(ex["scale"])); x.parmTuple("shear").set(tuple(ex["shear"]))
        n = ref.createNode("normal", "N"); n.setFirstInput(x)
        rc = ref.createNode("color", "tint"); rc.setFirstInput(n); rc.parm("class").set(2); rc.parmTuple("color").set((0.55, 0.55, 0.60))
        ro = ref.createNode("null", "OUT"); ro.setFirstInput(rc); ro.setDisplayFlag(True); ro.setRenderFlag(True)
        ref.layoutChildren()
        ref.setDisplayFlag(False)
        ref.setComment("Reference: scan of someone else's exhibited sculpture (author/collection unconfirmed, D18). "
                       "Read-only, SHA-256 %s...%s. Placement align B (Docs/Evidence/ArtFirst/26/reference/align_B_upright.json). "
                       "Use for large forms / layout / proportions only; never copy details; never lock or cache here." % (h[:8], h[-4:]))
        rep["refmodel_xform"] = {"matrix_houdini_row_convention": Mh.round(9).tolist(),
                                 "explode": {k: list(v) for k, v in ex.items()}}
        # large-form version (fingers removed)
        lf = obj.createNode("geo", "refmodel_largeform")
        for ch in lf.children():
            ch.destroy()
        om = lf.createNode("object_merge", "ref")
        om.parm("objpath1").set("/obj/refmodel/OUT"); om.parm("xformtype").set(1)
        v = lf.createNode("vdbfrompolygons", "sdf"); v.setFirstInput(om)
        v.parm("voxelsize").setExpression('ch("/obj/CTRL/lf_voxel")')
        v.parm("exteriorbandvoxels").set(6); v.parm("interiorbandvoxels").set(6)
        rs = lf.createNode("vdbreshapesdf", "open_remove_fingers"); rs.setFirstInput(v)
        rs.parm("operation").set("open")
        rs.parm("voxeloffset").setExpression('ch("/obj/CTRL/lf_open") / ch("/obj/CTRL/lf_voxel")')
        sm = lf.createNode("vdbsmoothsdf", "gaussian_large_forms"); sm.setFirstInput(rs)
        sm.parm("operation").set("gaussian")
        sm.parm("iterations").setExpression('ch("/obj/CTRL/lf_smooth_iter")')
        sm.parm("radius").setExpression('ch("/obj/CTRL/lf_smooth_width")')
        cv = lf.createNode("convertvdb", "to_polygons"); cv.setFirstInput(sm)
        cv.parm("conversion").set("poly"); cv.parm("adaptivity").set(0.05)
        ln = lf.createNode("normal", "N"); ln.setFirstInput(cv)
        lc = lf.createNode("color", "tint"); lc.setFirstInput(ln); lc.parm("class").set(2); lc.parmTuple("color").set((0.62, 0.60, 0.70))
        lo = lf.createNode("null", "OUT"); lo.setFirstInput(lc); lo.setDisplayFlag(True); lo.setRenderFlag(True)
        lf.layoutChildren()
        lf.setDisplayFlag(False)
        lf.setComment("Reference model large forms: SDF opening (erode+dilate by CTRL lf_open) removes the fingers/claws, then Gaussian smoothing. "
                      "Reference only (someone else's sculpture): proportions, layout, 3-D large forms; record deliberate differences.")

    # ---------------- candidate work area
    cw = obj.createNode("geo", "candidate_work")
    for ch in cw.children():
        ch.destroy()
    cm = cw.createNode("object_merge", "start_from_kstar")
    cm.parm("objpath1").set("/obj/kstar_current/OUT"); cm.parm("xformtype").set(1)
    co = cw.createNode("null", "OUT"); co.setFirstInput(cm); co.setDisplayFlag(True); co.setRenderFlag(True)
    cw.layoutChildren()
    cw.setDisplayFlag(False)
    cw.setComment("Design here, keep the point attribute 'col' (and uv/uv2) alive through the edits; "
                  "kh_bridge.py h2g slices OUT on the 240 row planes back to the 400x240 grid.")

    obj.layoutChildren()
    # ---------------- OpenGL ROP: the painting view with the painting behind (Houdini's own render of the camera)
    rop = hou.node("/out").createNode("opengl", "painting_view")
    rop.parm("camera").set("/obj/PaintingCam")
    rop.parm("tres").set(1); rop.parm("res1").set(KC.CAM_W); rop.parm("res2").set(KC.CAM_H)
    rop.parm("picture").set((os.path.join(KC.OUT_ROOT, "scene", "houdini_painting_view.png")).replace("\\", "/"))
    if os.path.isfile(KC.PLATE):
        rop.parm("bgimage").set(KC.PLATE.replace("\\", "/"))
    rop.parm("aamode").set("aa4")
    rop.setComment("PaintingCam render (OpenGL) over the painting plate; output in Unity/Build/Q20H/scene (git-ignored)")
    note = obj.createStickyNote("kh_notes")
    note.setText("Design28R01 / kstar_h\n" + conv + "\nBridge: Tools/GWWaveGen/kstar_h/kh_bridge.py (g2h / h2g / camcheck).\n"
                 "Evaluator: kh_eval.py. Renders: kh_bl.py. Heavy outputs: Unity/Build/Q20H (git-ignored).\n"
                 "Reference model = someone else's sculpture: reference only, never lock/cache/copy it into the repo.")
    note.setSize(hou.Vector2(8, 3))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    hou.hipFile.save(args.out)
    rep["saved"] = args.out
    rep["hip_bytes"] = os.path.getsize(args.out)
    rep["build_seconds"] = round(time.time() - t0, 2)
    return rep


def verify(rep):
    """保存したシーンを開き直して各 SOP を調理し、点の数・範囲・警告・法線の向き・参照モデルの置き方を確かめる。"""
    t0 = time.time()
    hou.hipFile.load(rep["saved"], suppress_save_prompt=True, ignore_load_warnings=True)
    out = {}
    for name in ("sea", "kstar_current", "kstar_loop2", "cand_A4", "cand_A3b", "refmodel", "refmodel_largeform", "candidate_work"):
        node = hou.node("/obj/%s/OUT" % name)
        if node is None:
            continue
        t1 = time.time()
        try:
            geo = node.geometry()
            bb = geo.boundingBox()
            d = {"points": len(geo.points()), "prims": len(geo.prims()),
                 "bbox_min": [round(x, 3) for x in bb.minvec()], "bbox_max": [round(x, 3) for x in bb.maxvec()],
                 "warnings": [w for n in node.parent().children() for w in n.warnings()],
                 "errors": [e for n in node.parent().children() for e in n.errors()], "cook_s": round(time.time() - t1, 2)}
            if name in ("kstar_current", "kstar_loop2", "cand_A4") and len(geo.prims()):
                # flat-sea triangles: Houdini normals should point +Y
                P = np.frombuffer(geo.pointFloatAttribValuesAsString("P"), np.float32).reshape(-1, 3)
                ny = []
                for pr in geo.prims()[:4000]:
                    pts = [v.point().number() for v in pr.vertices()]
                    if np.all(np.abs(P[pts, 1]) < 1e-6):
                        ny.append(pr.normal()[1])
                d["flat_sea_prims_checked"] = len(ny)
                d["flat_sea_normals_up"] = int(sum(1 for y in ny if y > 0.99))
                d["flat_sea_normals_down"] = int(sum(1 for y in ny if y < -0.99))
            out[name] = d
        except hou.OperationFailed as e:
            out[name] = {"error": str(e)}
    # reference model placement check against numpy (first 2000 OBJ vertices through align B, then Unity -> Houdini)
    if hou.node("/obj/refmodel/OUT") is not None:
        V = []
        with open(KC.REF_OBJ, "rb") as f:
            for line in f:
                if line.startswith(b"v "):
                    V.append([float(x) for x in line.split()[1:4]])
                    if len(V) >= 2000:
                        break
        V = np.array(V)
        M4 = np.array(json.load(open(KC.ALIGN_B, encoding="utf-8"))["obj_to_unity_4x4"])
        Vu = (np.c_[V, np.ones(len(V))] @ M4.T)[:, :3]
        Vh = KC.u2h(Vu)
        geo = hou.node("/obj/refmodel/align_B_to_houdini").geometry()
        Ph = np.frombuffer(geo.pointFloatAttribValuesAsString("P"), np.float32).reshape(-1, 3)[:len(V)]
        out["refmodel_placement_check"] = {"n": len(V), "max_abs_diff_m": float(np.abs(Ph - Vh).max()),
                                           "note": "Houdini File+xform vs numpy (OBJ @ align-B 4x4, then z negated)"}
    rop = hou.node("/out/painting_view")
    if rop is not None:
        try:
            rop.render(frame_range=(1, 1))
            out["opengl_painting_view"] = rop.evalParm("picture")
        except hou.OperationFailed as e:
            out["opengl_painting_view"] = "render failed: %s" % e
    rep["verify"] = out
    rep["verify_seconds"] = round(time.time() - t0, 2)
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=KC.HIP_BASE)
    ap.add_argument("--verify", default=None, help="write a verification report json (cooks every object)")
    ap.add_argument("--no-ref", action="store_true")
    a = ap.parse_args()
    r = build(a)
    if a.verify:
        r = verify(r)
        os.makedirs(os.path.dirname(a.verify), exist_ok=True)
        json.dump(r, open(a.verify, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    print(json.dumps(r, indent=1, ensure_ascii=False, default=str)[:6000])
