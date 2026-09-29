# -*- coding: utf-8 -*-
"""hython だけで使う部分（hou を読み込む）。GWW0 ⇄ Houdini の形状、Houdini の形状 → numpy の配列。
座標の変換は kh_common の注（(x, y, z)_H = (x, y, -z)_U、頂点順はそのまま）。"""
import os
import sys
import json

import numpy as np
import hou

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kh_common as KC  # noqa: E402


def fill_geo_from_gwb(geo, path, label=""):
    """GWW0 → Houdini の形状（点の順 = 行×400 + 列、三角形の順も GWW0 のまま）。
    点の属性：col（列、float）、row（行、int）、c_sec（断面の c、m）、uv（UV0、vector3 の xy）、uv2（UV2 = σ, c、float×2）。
    詳細の属性：kh_row_c（行の c、float 配列）、kh_source、kh_sha256、kh_convention。"""
    G = KC.read_gwb(path)
    nu, nv = G["nu"], G["nv"]
    Xh = KC.u2h(G["X"]).astype(np.float32)
    geo.clear()
    geo.createPoints([hou.Vector3(0, 0, 0)] * (nu * nv))
    geo.setPointFloatAttribValuesFromString("P", Xh.tobytes())
    for name, dflt, n in (("col", 0.0, 1), ("c_sec", 0.0, 1), ("uv", (0.0, 0.0, 0.0), 3), ("uv2", (0.0, 0.0), 2)):
        geo.addAttrib(hou.attribType.Point, name, dflt)
    geo.addAttrib(hou.attribType.Point, "row", 0)
    jj, rr = np.meshgrid(np.arange(nu), np.arange(nv))
    geo.setPointFloatAttribValuesFromString("col", jj.ravel().astype(np.float32).tobytes())
    geo.setPointIntAttribValuesFromString("row", rr.ravel().astype(np.int32).tobytes())
    S = KC.sec(G["X"])
    geo.setPointFloatAttribValuesFromString("c_sec", S[:, 2].astype(np.float32).tobytes())
    uv3 = np.c_[G["uv"], np.zeros(nu * nv)].astype(np.float32)
    geo.setPointFloatAttribValuesFromString("uv", uv3.tobytes())
    geo.setPointFloatAttribValuesFromString("uv2", G["uv2"].astype(np.float32).tobytes())
    geo.createPolygons([tuple(int(i) for i in t) for t in G["tris"]], True)
    c_rows = S[:, 2].reshape(nv, nu).mean(1)
    geo.addArrayAttrib(hou.attribType.Global, "kh_row_c", hou.attribData.Float, 1)
    geo.setGlobalAttribValue("kh_row_c", [float(x) for x in c_rows])
    for k, v in (("kh_source", path), ("kh_label", label), ("kh_sha256", KC.sha256(path)),
                 ("kh_convention", "Houdini = Unity with z negated; vertex order kept; col/row = GWW0 grid indices")):
        geo.addAttrib(hou.attribType.Global, k, "")
        geo.setGlobalAttribValue(k, v)
    return G


def sop_load_gwb(node):
    """シーンの Python SOP から呼ぶ：スペアのパラメータ gwb のファイルを読み込む（無ければ空＋警告）。"""
    geo = node.geometry()
    path = node.evalParm("gwb")
    label = node.evalParm("label") if node.parm("label") else ""
    if not path or not os.path.isfile(path):
        geo.clear()
        raise hou.NodeWarning("GWW0 file not found (yet): %s" % path)
    fill_geo_from_gwb(geo, path, label)


def sop_xform_matrix(node):
    """Python SOP：入力の点に 4×4（Houdini の行ベクトル規約、スペア kh_matrix の JSON）を掛ける。"""
    geo = node.geometry()
    M = np.array(json.loads(node.evalParm("kh_matrix")), np.float64).reshape(4, 4)
    P = np.frombuffer(geo.pointFloatAttribValuesAsString("P"), np.float32).reshape(-1, 3).astype(np.float64)
    Q = (np.c_[P, np.ones(len(P))] @ M)[:, :3]
    geo.setPointFloatAttribValuesFromString("P", Q.astype(np.float32).tobytes())


def geo_arrays(geo, attrs=("col", "uv", "uv2")):
    """三角形だけの形状（Divide で三角形にしたもの）→ (P_houdini (n,3), tris (m,3), {attr: (n,k)})。
    頂点→点の対応は頂点属性 kh_ptn（wrangle で書いたもの）から読む。"""
    P = np.frombuffer(geo.pointFloatAttribValuesAsString("P"), np.float32).reshape(-1, 3).astype(np.float64)
    ptn = np.frombuffer(geo.vertexIntAttribValuesAsString("kh_ptn"), np.int32).astype(np.int64)
    if len(ptn) != 3 * len(geo.prims()):
        raise ValueError("non-triangle primitives after Divide: %d vertices for %d prims" % (len(ptn), len(geo.prims())))
    tris = ptn.reshape(-1, 3)
    out = {}
    for a in attrs:
        at = geo.findPointAttrib(a)
        if at is None or at.dataType() != hou.attribData.Float:
            vt = geo.findVertexAttrib(a)
            if vt is None or vt.dataType() != hou.attribData.Float:
                continue
            # 頂点の属性（OBJ の vt など）→ 点へ（同じ点の頂点は同じ値の前提。最後の値を使う）
            vv = np.frombuffer(geo.vertexFloatAttribValuesAsString(a), np.float32).reshape(len(ptn), -1).astype(np.float64)
            v = np.zeros((len(P), vv.shape[1]))
            v[ptn] = vv
            out[a] = v
            continue
        v = np.frombuffer(geo.pointFloatAttribValuesAsString(a), np.float32).reshape(len(P), -1).astype(np.float64)
        out[a] = v
    return P, tris, out


def cooked_triangles(sop_path=None, file_path=None):
    """SOP（シーンの中）かファイル（.bgeo.sc / .obj ほか）の形状を、一時の SOP 網で三角形にし、配列で返す。"""
    obj = hou.node("/obj")
    tmp = obj.node("_kh_bridge_tmp")
    if tmp is not None:
        tmp.destroy()
    tmp = obj.createNode("geo", "_kh_bridge_tmp")
    for ch in tmp.children():
        ch.destroy()
    if sop_path:
        if hou.node(sop_path) is None:
            tmp.destroy()
            raise ValueError("SOP not found: %r (from Git Bash set MSYS_NO_PATHCONV=1 so /obj/... is not rewritten)" % sop_path)
        src = tmp.createNode("object_merge", "src")
        src.parm("objpath1").set(sop_path)
        src.parm("xformtype").set(1)          # into this object（オブジェクトの変換も掛ける）
    else:
        src = tmp.createNode("file", "src")
        src.parm("file").set(file_path)
    div = tmp.createNode("divide", "tri")
    div.setFirstInput(src)
    w = tmp.createNode("attribwrangle", "ptn")
    w.setFirstInput(div)
    w.parm("class").set(3)                   # vertices
    w.parm("snippet").set("i@kh_ptn = @ptnum;")
    geo = w.geometry()
    if len(geo.points()) == 0:
        tmp.destroy()
        raise ValueError("empty geometry from %s" % (sop_path or file_path))
    info = {"points": len(geo.points()), "prims": len(geo.prims())}
    P, tris, attrs = geo_arrays(geo)
    det = {}
    for a in geo.globalAttribs():
        try:
            det[a.name()] = geo.attribValue(a.name())
        except Exception:
            pass
    tmp.destroy()
    return P, tris, attrs, det, info
