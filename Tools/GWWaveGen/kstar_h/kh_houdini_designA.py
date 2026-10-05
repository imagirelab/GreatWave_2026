# -*- coding: utf-8 -*-
"""hython だけで使う：/obj/kstar_h_design の節点（Python SOP）の中身と、CTRL の ramp ⇄ 設計（kh_design.Design）。

網（上から順に）
  CTRL           スペアの ramp（母数ごと、位置 u = (c − C_LO)/(C_HI − C_LO)、基底 B-Spline）と説明
  guides         各行（c 一定の断面、240 本）の案内の曲線（開いた折れ線 400 点）。点の属性 col / row / c_sec / uv、
                 行の母数を prim の属性として持つ（Houdini の中で見て調べられる）。詳細 kh_row_c
  bregion_ledge  b 区域（左肩の第二の波頭）：肩の行の唇の上面を法線の向きへ谷 → 稜の形に押す
  side_edges     側の縁の合わせ：原画カメラから見て面が視線に沿う所（輪郭の縁）だけを帯の ramp で動かす
  skin           Skin SOP：案内の曲線を面にする（四角形、点と属性はそのまま）
  OUT            kh_bridge.py h2g が 240 の行の面で切り直して 400×240 の格子（GWW0）へ移す
座標：Houdini = Unity の z の符号を反転（kh_common の注）。
"""
import os
import sys
import json

import numpy as np
import hou

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kh_common as KC  # noqa: E402
import kh_designA as D  # noqa: E402

GROUPS = [
    ("crest", "Crest line (painting side edge) / 波峰線（原画の側の縁）", ("crest_height", "crest_a")),
    ("tube", "Tube and shell / 管と殻（樽の中心のまわりの同心の殻）", ("tube_radius", "tube_oval", "lean", "shell_top", "shell_back", "shell_base")),
    ("lip", "Lip and hook / 唇と鉤", ("tip_angle", "hook_depth", "hook_span", "lip_len", "lip_thick", "tip_round")),
    ("back", "Back and foot / 背と足（台座なし）", ("back_low", "foot_spread")),
    ("front", "Front trough / 前の谷", ("tube_end", "trough_depth", "trough_reach", "trough_len")),
    ("bregion", "b region (second crest) / b 区域（第二の波頭）", ("ledge_amp", "ledge_pos", "ledge_width", "ledge_lobe")),
    ("edges", "Side edges (painting-view silhouette only) / 側の縁（原画視点の輪郭だけ）", ("edge_top", "edge_lip", "edge_hook")),
]


def u_of_c(c):
    return (np.asarray(c, float) - D.C_LO) / (D.C_HI - D.C_LO)


def c_of_u(u):
    return D.C_LO + np.asarray(u, float) * (D.C_HI - D.C_LO)


# ------------------------------------------------------------------ CTRL
def add_ctrl_parms(ctrl):
    g = ctrl.parmTemplateGroup()
    info = hou.FolderParmTemplate("info", "About / 説明", folder_type=hou.folderType.Simple)
    info.addParmTemplate(hou.LabelParmTemplate("about1", "K*' (Design 28R01) procedural final painting frame of the hero wave",
                                               column_labels=("K*′ 最後の一コマ（設計28修正01、候補 H1）：断面の案内の曲線 → b 区域 → 側の縁 → Skin",)))
    info.addParmTemplate(hou.LabelParmTemplate("about2", "Ramps", column_labels=(
        "ramp の横軸 = 波峰に沿う c（左端 %.0f m 〜 右端 %.0f m、− = 手前の肩 = カメラの側）。基底 B-Spline（鍵は制御点）。" % (D.C_LO, D.C_HI),)))
    info.addParmTemplate(hou.LabelParmTemplate("about3", "Units", column_labels=(
        "長さの多くは H（その行の頂の高さ）で割った比。crest_height / crest_a / ledge_amp / edge_* / tip_round は m、角は度。",)))
    info.addParmTemplate(hou.StringParmTemplate("design_source", "Design source (json)", 1))
    info.addParmTemplate(hou.StringParmTemplate("fit_note", "Fit note", 1))
    g.append(info)
    for key, label, names in GROUPS:
        f = hou.FolderParmTemplate(key, label, folder_type=hou.folderType.Tabs)
        for n in names:
            lo, hi = D.PBOUNDS[n]
            t = hou.RampParmTemplate(n, n, hou.rampParmType.Float, default_value=2, default_basis=hou.rampBasis.BSpline,
                                     show_controls=True)
            t.setHelp("%s  [bounds %g .. %g]" % (D.PDESC[n], lo, hi))
            f.addParmTemplate(t)
            f.addParmTemplate(hou.LabelParmTemplate(n + "_desc", " ", column_labels=("%s（%g〜%g）" % (D.PDESC[n], lo, hi),)))
        g.append(f)
    ctrl.setParmTemplateGroup(g)


def set_ctrl_from_design(ctrl, design, source=""):
    for n in D.PNAMES:
        cs, vs = design.keys[n]
        o = np.argsort(cs, kind="stable")
        cs = [float(cs[i]) for i in o]; vs = [float(vs[i]) for i in o]
        if len(cs) == 1:                    # a ramp needs 2 keys: hold the value over the whole range
            cs = [D.C_LO, D.C_HI]; vs = [vs[0], vs[0]]
        us = [float(x) for x in u_of_c(cs)]
        ctrl.parm(n).set(hou.Ramp([hou.rampBasis.BSpline] * len(us), us, vs))
    if ctrl.parm("design_source"):
        ctrl.parm("design_source").set(source)


def design_from_ctrl(ctrl):
    keys = {}
    for n in D.PNAMES:
        r = ctrl.parm(n).evalAsRamp()
        cs = [float(x) for x in c_of_u(r.keys())]
        keys[n] = (cs, [float(v) for v in r.values()])
    return D.Design(keys)


def design_equal(a, b, tol=1e-6):
    for n in D.PNAMES:
        ca, va = a.keys[n]; cb, vb = b.keys[n]
        if len(ca) == 1:
            ca, va = [D.C_LO, D.C_HI], [va[0], va[0]]
        if len(cb) == 1:
            cb, vb = [D.C_LO, D.C_HI], [vb[0], vb[0]]
        # Houdini stores the ramp keys as 32-bit floats: compare with a relative tolerance of 1e-6
        tv = tol + 1e-6 * np.maximum(np.abs(np.array(va)), 1.0)
        if len(ca) != len(cb) or np.max(np.abs(np.array(ca) - np.array(cb))) > 1e-4 or np.any(np.abs(np.array(va) - np.array(vb)) > tv):
            return False, n
    return True, None


# ------------------------------------------------------------------ geometry <-> rows
def rows_to_points(geo, c, A, Y):
    X = D.world_u(c, A, Y)
    Ph = KC.u2h(X.reshape(-1, 3)).astype(np.float32)
    geo.setPointFloatAttribValuesFromString("P", Ph.tobytes())


def points_to_rows(geo, nv=D.NV, nu=D.NU):
    Ph = np.frombuffer(geo.pointFloatAttribValuesAsString("P"), np.float32).reshape(-1, 3).astype(np.float64)
    S = KC.sec(KC.h2u(Ph)).reshape(nv, nu, 3)
    c = np.array(geo.attribValue("kh_row_c"), np.float64)
    return c, S[..., 0], S[..., 1]


def ctrl_of(node):
    return node.node("../CTRL")


# ------------------------------------------------------------------ SOP bodies
def sop_guides(node):
    geo = node.geometry()
    geo.clear()
    design = design_from_ctrl(ctrl_of(node))
    c = D.c_rows()
    c, A, Y, P = D.build_base(design, c)
    nv, nu = A.shape
    geo.createPoints([hou.Vector3(0, 0, 0)] * (nv * nu))
    rows_to_points(geo, c, A, Y)
    geo.addAttrib(hou.attribType.Point, "col", 0.0)
    geo.addAttrib(hou.attribType.Point, "row", 0)
    geo.addAttrib(hou.attribType.Point, "c_sec", 0.0)
    geo.addAttrib(hou.attribType.Point, "uv", (0.0, 0.0, 0.0))
    jj, rr = np.meshgrid(np.arange(nu), np.arange(nv))
    geo.setPointFloatAttribValuesFromString("col", jj.ravel().astype(np.float32).tobytes())
    geo.setPointIntAttribValuesFromString("row", rr.ravel().astype(np.int32).tobytes())
    geo.setPointFloatAttribValuesFromString("c_sec", np.repeat(c, nu).astype(np.float32).tobytes())
    try:
        uvk, _ = KC.kstar_uv()
        uv3 = np.c_[uvk.reshape(-1, 2), np.zeros(nv * nu)].astype(np.float32)
        geo.setPointFloatAttribValuesFromString("uv", uv3.tobytes())
    except Exception:
        pass
    geo.createPolygons([tuple(range(r * nu, (r + 1) * nu)) for r in range(nv)], False)
    # the row parameters as primitive attributes (inspect them in the spreadsheet)
    for n in D.PNAMES:
        geo.addAttrib(hou.attribType.Prim, n, 0.0)
        geo.setPrimFloatAttribValuesFromString(n, np.asarray(P[n], np.float32).tobytes())
    geo.addAttrib(hou.attribType.Prim, "c_row", 0.0)
    geo.setPrimFloatAttribValuesFromString("c_row", c.astype(np.float32).tobytes())
    geo.addArrayAttrib(hou.attribType.Global, "kh_row_c", hou.attribData.Float, 1)
    geo.setGlobalAttribValue("kh_row_c", [float(x) for x in c])
    for k, v in (("kh_convention", "Houdini = Unity with z negated; rows = constant-c planes of the K* 26R01 section frame; col/row = grid indices"),
                 ("kh_generator", "Tools/GWWaveGen/kstar_h/kh_designA.py via kh_houdini_designA.sop_guides"),
                 ("kh_design_json", json.dumps(design.to_json()))):
        geo.addAttrib(hou.attribType.Global, k, "")
        geo.setGlobalAttribValue(k, v)


def _row_params(node, c):
    return design_from_ctrl(ctrl_of(node)).eval(c)


def sop_ledge(node):
    geo = node.geometry()
    c, A, Y = points_to_rows(geo)
    P = _row_params(node, c)
    A2, Y2 = D.apply_ledge(c, A, Y, P)
    rows_to_points(geo, c, A2, Y2)
    mv = np.hypot(A2 - A, Y2 - Y)
    geo.addAttrib(hou.attribType.Point, "ledge_move", 0.0)
    geo.setPointFloatAttribValuesFromString("ledge_move", mv.ravel().astype(np.float32).tobytes())


def sop_edges(node):
    geo = node.geometry()
    c, A, Y = points_to_rows(geo)
    P = _row_params(node, c)
    A2, Y2 = D.apply_edges(c, A, Y, P)
    rows_to_points(geo, c, A2, Y2)
    mv = np.hypot(A2 - A, Y2 - Y)
    geo.addAttrib(hou.attribType.Point, "edge_move", 0.0)
    geo.setPointFloatAttribValuesFromString("edge_move", mv.ravel().astype(np.float32).tobytes())
    geo.addAttrib(hou.attribType.Point, "graze", 0.0)
    geo.setPointFloatAttribValuesFromString("graze", D.graze_weight(c, A, Y).ravel().astype(np.float32).tobytes())


PYSOP = """import sys
sys.path.insert(0, r'%s')
import kh_houdini_designA
kh_houdini_designA.%s(hou.pwd())
"""
