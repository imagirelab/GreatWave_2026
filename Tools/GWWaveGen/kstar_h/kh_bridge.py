# -*- coding: utf-8 -*-
"""Houdini ⇄ 格子（400 列 × 240 行、GWW0）の橋（hython で動かす）。

  g2h       GWW0 → Houdini の形状ファイル（.bgeo.sc、Houdini 座標、点の属性 col/row/uv/uv2/c_sec、詳細 kh_row_c）
  h2g       Houdini の形状（シーンの SOP か形状ファイル）→ 各行の面（c 一定、K* の断面の座標系）で切る
            → 断面の折れ線を弧長で並べ直し、目印の列（18/90/200/314/379/394）に置く → rows npz + GWW0 + OBJ + meta
  export    シーンの SOP を形状ファイルへ書く（.obj / .bgeo.sc。--unity で Unity 座標へ戻した OBJ、三角形の順はそのまま）
  camcheck  シーンの /obj/PaintingCam で GWW0 の全頂点を toNDC（Houdini 自身の射影）し、numpy の射影と比べる材料を書く

usage:
  hython kh_bridge.py g2h --gwb <in.gwb> --out <out.bgeo.sc>
  hython kh_bridge.py h2g (--hip <scene.hiplc> --sop </obj/.../OUT> | --geo <file.bgeo.sc|.obj>) --out <prefix>
                          [--columns auto|attr|landmark|geometric] [--rows auto|kstar|attr|<rows.npz>] [--uv kstar|main]
                          [--coords houdini|unity]
  hython kh_bridge.py export --hip <scene.hiplc> --sop </obj/.../OUT> --out <file.obj|file.bgeo.sc> [--unity]
  hython kh_bridge.py camcheck --hip <scene.hiplc> --gwb <in.gwb> --out <ndc.npz>
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


def cmd_g2h(a):
    geo = hou.Geometry()
    G = KH.fill_geo_from_gwb(geo, a.gwb, os.path.basename(a.gwb))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    geo.saveToFile(a.out)
    r = {"in": a.gwb, "out": a.out, "points": len(geo.points()), "prims": len(geo.prims()), "nu": G["nu"], "nv": G["nv"]}
    print(json.dumps(r))
    return r


def cmd_h2g(a):
    t0 = time.time()
    if a.hip:
        hou.hipFile.load(a.hip, suppress_save_prompt=True, ignore_load_warnings=True)
        Ph, tris, attrs, det, info = KH.cooked_triangles(sop_path=a.sop)
        src = {"hip": a.hip, "sop": a.sop}
    else:
        Ph, tris, attrs, det, info = KH.cooked_triangles(file_path=a.geo)
        src = {"geo": a.geo}
    Xu = KC.h2u(Ph) if a.coords == "houdini" else Ph
    col_src = "point attribute col" if "col" in attrs else None
    if "col" not in attrs and "uv" in attrs and not a.no_uv_col:
        # K* の UV の並び（UV0.u = σ/σ_total、列ごとに一定）から列を戻す
        uvk, _ = KC.kstar_uv()
        U = uvk[0, :, 0].astype(np.float64)
        u = attrs["uv"][:, 0]
        if np.all(np.diff(U) > 0) and u.min() >= -1e-4 and u.max() <= 1 + 1e-4:
            attrs["col"] = np.interp(u, U, np.arange(len(U), dtype=np.float64))[:, None]
            col_src = "recovered from uv.u through the K* UV layout (u -> column)"
    # rows
    if a.rows == "auto":
        rows_mode = "attr" if isinstance(det.get("kh_row_c"), (list, tuple)) and len(det.get("kh_row_c")) > 1 else "kstar"
    else:
        rows_mode = a.rows
    if rows_mode == "attr":
        c_rows = np.array(det["kh_row_c"], np.float64)
    elif rows_mode == "kstar":
        c_rows = KC.kstar_rows_c()
    else:
        c_rows = np.load(rows_mode)["c"].astype(np.float64)
    A, Y, rep, columns = KC.grid_from_mesh(Xu, tris, attrs, c_rows, a.columns)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    nwarn = {}
    for r in rep:
        for w in r["warn"]:
            k = w.split("(")[0].split(":")[0].strip()
            nwarn[k] = nwarn.get(k, 0) + 1
    prov = {"bridge": "Tools/GWWaveGen/kstar_h/kh_bridge.py h2g", "source": src, "houdini": hou.applicationVersionString(),
            "coords_in": a.coords, "columns": columns, "col_source": col_src, "rows": rows_mode, "uv": a.uv,
            "source_points": int(len(Ph)), "source_triangles": int(len(tris)), "source_point_attribs": sorted(attrs.keys()),
            "source_detail": {k: (v if not isinstance(v, (list, tuple)) or len(v) < 8 else "array[%d]" % len(v)) for k, v in det.items()},
            "row_warning_counts": nwarn, "rows_with_other_chains": int(sum(1 for r in rep if r["other_chain_length_m"] > 0.01)),
            "rows_with_branch_nodes": int(sum(1 for r in rep if r["branch_nodes"] > 0)), "seconds": None}
    meta = KC.write_candidate(a.out, c_rows, A, Y, prov, uv_mode=a.uv)
    prov["seconds"] = round(time.time() - t0, 2)
    meta["provenance"] = prov
    json.dump(meta, open(a.out + "_meta.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump(rep, open(a.out + "_bridge_rows.json", "w", encoding="utf-8"), indent=0, ensure_ascii=False)
    print(json.dumps({"out": a.out, "columns": columns, "rows": rows_mode, "warnings": nwarn, "gwb_sha256": meta["files"]["gwb_sha256"],
                      "checks": meta["checks"], "seconds": prov["seconds"]}, ensure_ascii=False))
    return meta


def cmd_export(a):
    hou.hipFile.load(a.hip, suppress_save_prompt=True, ignore_load_warnings=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    if a.unity:
        if not a.out.lower().endswith(".obj"):
            raise SystemExit("--unity writes an OBJ")
        Ph, tris, attrs, det, info = KH.cooked_triangles(sop_path=a.sop)
        Xu = KC.h2u(Ph)
        uv = attrs["uv"][:, :2] if "uv" in attrs else np.zeros((len(Xu), 2))
        KC.write_obj(a.out, Xu, uv, tris, ["kstar_h export of %s (%s), Unity world coordinates (z negated back from Houdini)" % (a.sop, a.hip)])
    else:
        node = hou.node(a.sop)
        if node is None:
            raise SystemExit("SOP not found: %r" % a.sop)
        node.geometry().saveToFile(a.out)
        info = {"points": len(node.geometry().points()), "prims": len(node.geometry().prims())}
    r = {"out": a.out, "sha256": KC.sha256(a.out), "bytes": os.path.getsize(a.out), "coords": "unity" if a.unity else "houdini", "info": info}
    print(json.dumps(r))
    return r


def cmd_camcheck(a):
    hou.hipFile.load(a.hip, suppress_save_prompt=True, ignore_load_warnings=True)
    cam = hou.node("/obj/PaintingCam")
    G = KC.read_gwb(a.gwb)
    geo_node = hou.node("/obj").createNode("geo", "_kh_camcheck")
    for ch in geo_node.children():
        ch.destroy()
    py = geo_node.createNode("python", "pts")
    py.parm("python").set("import sys\nsys.path.insert(0, r'%s')\nimport kh_houdini, kh_common\n"
                          "g = hou.pwd().geometry()\nkh_houdini.fill_geo_from_gwb(g, r'%s')\n" % (HERE, a.gwb))
    w = geo_node.createNode("attribwrangle", "ndc")
    w.setFirstInput(py)
    w.parm("class").set(2)
    w.parm("snippet").set('v@ndc = toNDC("%s", @P);' % cam.path())
    geo = w.geometry()
    ndc = np.frombuffer(geo.pointFloatAttribValuesAsString("ndc"), np.float32).reshape(-1, 3).astype(np.float64)
    Ph = np.frombuffer(geo.pointFloatAttribValuesAsString("P"), np.float32).reshape(-1, 3).astype(np.float64)
    # Houdini world -> camera space via the camera's world transform (second, matrix-based projection)
    Mi = np.array(cam.worldTransform().inverted().asTupleOfTuples())
    Pc = (np.c_[Ph, np.ones(len(Ph))] @ Mi)[:, :3]
    info = {"focal": cam.evalParm("focal"), "aperture": cam.evalParm("aperture"), "resx": cam.evalParm("resx"),
            "resy": cam.evalParm("resy"), "aspect": cam.evalParm("aspect"), "t": list(cam.parmTuple("t").eval()),
            "r": list(cam.parmTuple("r").eval()), "worldTransform": [list(r) for r in cam.worldTransform().asTupleOfTuples()]}
    np.savez_compressed(a.out, ndc=ndc, Pcam=Pc, Ph=Ph, info=json.dumps(info))
    geo_node.destroy()
    print(json.dumps(info))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("g2h"); p.add_argument("--gwb", required=True); p.add_argument("--out", required=True)
    p = sub.add_parser("h2g")
    p.add_argument("--hip"); p.add_argument("--sop"); p.add_argument("--geo")
    p.add_argument("--out", required=True)
    p.add_argument("--columns", default="auto", choices=["auto", "attr", "landmark", "geometric"])
    p.add_argument("--rows", default="auto")
    p.add_argument("--uv", default="kstar", choices=["kstar", "main"])
    p.add_argument("--coords", default="houdini", choices=["houdini", "unity"])
    p.add_argument("--no-uv-col", action="store_true", help="do not recover the column from the K* UV layout")
    p = sub.add_parser("export"); p.add_argument("--hip", required=True); p.add_argument("--sop", required=True); p.add_argument("--out", required=True)
    p.add_argument("--unity", action="store_true")
    p = sub.add_parser("camcheck"); p.add_argument("--hip", required=True); p.add_argument("--gwb", required=True); p.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "h2g" and not ((a.hip and a.sop) or a.geo):
        raise SystemExit("h2g needs --hip and --sop, or --geo")
    {"g2h": cmd_g2h, "h2g": cmd_h2g, "export": cmd_export, "camcheck": cmd_camcheck}[a.cmd](a)
