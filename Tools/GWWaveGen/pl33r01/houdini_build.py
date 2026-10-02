# -*- coding: utf-8 -*-
"""仕上げ33修正01（Houdini の変種）の 2：Houdini（Steam の Houdini Indie、hython）で、立つ白い爪の指を造形する。

  爪の一覧の中心線（houdini_prep.py の fingers_tstar.json）→ 曲線（Python SOP）→ CTRL の曲がり（curl）と細り（taper）のランプで
  立ち上げと太さを決める（stand の wrangle）→ 曲線を細かく取り直す → 指ごとに、指の曲線の粒と頂の帯（根元の白の円の上の薄い帯）の粒から
  VDB（VDB from Particles）→ 閉じ（VDB Reshape SDF の close = 指と帯の滑らかな和。根元が帯から盛り上がって生える）→ 均し → 多角形 → 減らす。
  t* の形を 1 つの鍵（per-key mesh）として、橋（kstar_h/kh_houdini.py の geo_arrays）で配列にして書き出す。コマごとの形は
  houdini_deform.py が、この鍵の形を指の中心線に結び付けて動かす（形の位相はコマの間で同じ）。

usage: hython houdini_build.py --fingers <fingers_tstar.json> --hip <out.hiplc> --out <out_dir>
保存するシーンには参照モデルのノードもパスも入れない（入力は爪の並びから作った JSON だけ）。
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import hou

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "kstar_h"))
import houdini_common as HC  # noqa: E402
import kh_houdini as KH      # noqa: E402  （既存の橋）


def set_menu(parm, *wants):
    items = parm.menuItems()
    labels = parm.menuLabels()
    for w in wants:
        for i, (it, lb) in enumerate(zip(items, labels)):
            if w.lower() == it.lower() or w.lower() in lb.lower():
                parm.set(it)
                return it
    raise ValueError("menu item %r not in %s / %s" % (wants, items, labels))


LOAD_PY = r'''
import json
node = hou.pwd()
geo = node.geometry()
D = json.load(open(node.evalParm("fingers_json"), encoding="utf-8"))
for name, t in (("fid", 0), ("kind", 0), ("ispad", 0), ("istip", 0), ("npts", 0), ("row", 0)):
    geo.addAttrib(hou.attribType.Point, name, t)
for name in ("u", "hw", "H", "hwp", "up", "vox", "kclose", "pscale", "aoff", "ell"):
    geo.addAttrib(hou.attribType.Point, name, 0.0)
for name in ("C", "NO"):
    geo.addAttrib(hou.attribType.Point, name, (0.0, 0.0, 0.0))
for f in D["fingers"]:
  C = f["C"]
  offs = [0.0] if f.get("ell", 1.0) <= 1.0 else [0.0, -1.0, -0.5, 0.5, 1.0]   # 断面を射線の向きへ伸ばす列（row 0 が中心線）
  for row, aoff in enumerate(offs):
    pts = []
    for k in range(len(C)):
        p = geo.createPoint()
        p.setAttribValue("row", row); p.setAttribValue("aoff", aoff); p.setAttribValue("ell", f.get("ell", 1.0))
        p.setPosition(C[k])
        p.setAttribValue("fid", f["fid"]); p.setAttribValue("kind", f["kind"]); p.setAttribValue("u", f["U"][k]); p.setAttribValue("hw", f["HW"][k])
        p.setAttribValue("H", f["H"]); p.setAttribValue("C", C[k]); p.setAttribValue("NO", f["NO"])
        p.setAttribValue("istip", 1 if k == len(C) - 1 else 0)
        p.setAttribValue("hwp", f["tip_prev"][0]); p.setAttribValue("up", f["tip_prev"][1])
        p.setAttribValue("vox", f["vox"]); p.setAttribValue("kclose", f["kclose"]); p.setAttribValue("npts", f["npts"])
        pts.append(p)
    poly = geo.createPolygon(False)
    for p in pts:
        poly.addVertex(p)
  for q in f["pad"]:
    p = geo.createPoint()
    p.setPosition(q)
    p.setAttribValue("fid", f["fid"]); p.setAttribValue("kind", f["kind"]); p.setAttribValue("ispad", 1)
    p.setAttribValue("pscale", f["padr"]); p.setAttribValue("NO", f["NO"])
    p.setAttribValue("vox", f["vox"]); p.setAttribValue("kclose", f["kclose"]); p.setAttribValue("npts", f["npts"])
geo.addAttrib(hou.attribType.Global, "pl33r01h_fingers", len(D["fingers"]))
'''

ELLIPSE_VEX = r'''
// 断面を射線の向きへ伸ばす（pl33r01h_depth_section）：中心線（row 0）の両側に、射線を断面の面へ写した向き a へ aoff·(ell − 1)·r ずらした粒の列を置く。
// a は原画のカメラへの射線に沿うので、原画視点の投影の幅は変わらず、ほかの視点から指が太く（ell 倍まで）見える。
if (i@ispad == 1 || f@aoff == 0.0) return;
int pts[] = primpoints(0, @primnum);
int idx = find(pts, @ptnum);
int n = len(pts);
vector p0 = point(0, "P", pts[max(0, idx - 2)]);
vector p1 = point(0, "P", pts[min(n - 1, idx + 2)]);
vector T = normalize(p1 - p0);
vector ray = normalize(@P - chv("../CTRL/cam"));
vector a = ray - dot(ray, T) * T;
if (length(a) < 1e-4) return;
a = normalize(a);
@P += a * f@aoff * (f@ell - 1.0) * f@pscale;
'''

STAND_VEX = r'''
// 立つ指（pl33r01h_stand）：中心線を原画のカメラへの射線の上で手前へ動かす（原画視点の投影は変わらない）。冠の爪（kind 2）は動かさず、根元の側を半径だけ面の外へ。
if (i@ispad == 1) return;
string c = "../CTRL/";
vector cam = chv(c + "cam");
float u = f@u;
float curl = chramp(c + "curl", u);
float rk = i@kind == 2 ? ch(c + "rk_K") : (i@kind == 1 ? ch(c + "rk_S") : ch(c + "rk_C"));
float rmin = ch(c + "r_min");
float R;
if (i@istip == 1) {
    float tp = chramp(c + "taper", f@up);
    float Rp = f@hwp * tp * rk;
    Rp = f@hwp > 1e-6 ? max(Rp, rmin) : 0.0;
    R = ch(c + "tip_r") * Rp;
} else {
    float tp = chramp(c + "taper", u);
    R = f@hw * tp * rk;
    R = f@hw > 1e-6 ? max(R, rmin) : 0.0;
}
vector C = v@C;
vector L = normalize(cam - C);
float face = clamp(abs(dot(v@NO, L)), ch(c + "face_min"), 1.0);
float d = f@H * curl / face;
d = max(d, ch(c + "clear") * R / face);
d = min(d, ch(c + "d_max"));
vector P = C;
if (i@kind != 2) P += L * d;
else P += v@NO * R * (1.0 - smooth(ch(c + "k_lift_u0"), ch(c + "k_lift_u1"), u));
@P = P;
f@pscale = R;
'''


def build(a):
    t0 = time.time()
    hou.hipFile.clear(suppress_save_prompt=True)
    D = json.load(open(a.fingers, encoding="utf-8"))
    prm = D["meta"]["prm"]
    obj = hou.node("/obj")
    g = obj.createNode("geo", "pl33r01h_fingers")
    for ch in g.children():
        ch.destroy()
    # CTRL：ランプと数（ch で網へ渡す）
    ctrl = g.createNode("null", "CTRL")
    ptg = ctrl.parmTemplateGroup()
    ptg.append(hou.FloatParmTemplate("cam", "PaintingCam (Houdini)", 3, default_value=tuple(D["meta"]["cam_h"])))
    ptg.append(hou.RampParmTemplate("curl", "curl（立ち上がりと先の巻き戻し）", hou.rampParmType.Float, default_value=len(HC.CURL_KEYS)))
    ptg.append(hou.RampParmTemplate("taper", "taper（細り。半幅に掛ける）", hou.rampParmType.Float, default_value=len(HC.TAPER_KEYS)))
    for k in ("r_min", "tip_r", "face_min", "d_max", "clear", "rk_C", "rk_S", "rk_K", "k_lift_u0", "k_lift_u1"):
        ptg.append(hou.FloatParmTemplate(k, k, 1, default_value=(float(prm[k]),)))
    ptg.append(hou.FloatParmTemplate("resample_len", "resample_len", 1, default_value=(0.02,)))
    ptg.append(hou.FloatParmTemplate("adaptivity", "adaptivity", 1, default_value=(0.1,)))
    ptg.append(hou.IntParmTemplate("smooth_iter", "smooth_iter", 1, default_value=(1,)))
    ptg.append(hou.FloatParmTemplate("npts_scale", "npts_scale", 1, default_value=(float(a.npts_scale),)))
    ctrl.setParmTemplateGroup(ptg)
    lin = hou.rampBasis.Linear
    ctrl.parm("curl").set(hou.Ramp([lin] * len(HC.CURL_KEYS), [k[0] for k in HC.CURL_KEYS], [k[1] for k in HC.CURL_KEYS]))
    ctrl.parm("taper").set(hou.Ramp([lin] * len(HC.TAPER_KEYS), [k[0] for k in HC.TAPER_KEYS], [k[1] for k in HC.TAPER_KEYS]))

    load = g.createNode("python", "load_fingers")
    ptl = load.parmTemplateGroup()
    ptl.append(hou.StringParmTemplate("fingers_json", "fingers_json", 1, default_value=(a.fingers.replace("\\", "/"),)))
    load.setParmTemplateGroup(ptl)
    load.parm("python").set(LOAD_PY)

    stand = g.createNode("attribwrangle", "stand")
    stand.setFirstInput(load)
    stand.parm("class").set(2)
    stand.parm("snippet").set(STAND_VEX)

    ell = g.createNode("attribwrangle", "depth_section")
    ell.setFirstInput(stand)
    ell.parm("class").set(2)
    ell.parm("snippet").set(ELLIPSE_VEX)

    res = g.createNode("resample", "resample")
    res.setFirstInput(ell)
    res.parm("length").setExpression('ch("../CTRL/resample_len")')

    beg = g.createNode("block_begin", "piece_begin")
    end = g.createNode("block_end", "piece_end")
    beg.setFirstInput(res)
    set_menu(beg.parm("method"), "piece", "Fetch Piece")
    beg.parm("blockpath").set("../piece_end")
    vfp = g.createNode("vdbfromparticles", "finger_vdb")
    vfp.setFirstInput(beg)
    vfp.parm("voxelsize").setExpression('point("../piece_begin", 0, "vox", 0)')
    vfp.parm("minvoxelradius").set(0.3)
    vfp.parm("bandwidthvoxels").set(4.0)
    close = g.createNode("vdbreshapesdf", "smooth_union_close")
    close.setFirstInput(vfp)
    set_menu(close.parm("operation"), "close")
    close.parm("useworldspaceunits").set(1)
    close.parm("radiusworld").setExpression('point("../piece_begin", 0, "kclose", 0)')
    sm = g.createNode("vdbsmoothsdf", "smooth")
    sm.setFirstInput(close)
    sm.parm("iterations").setExpression('ch("../CTRL/smooth_iter")')
    cv = g.createNode("convertvdb", "to_polygons")
    cv.setFirstInput(sm)
    set_menu(cv.parm("conversion"), "poly", "Polygons")
    cv.parm("adaptivity").setExpression('ch("../CTRL/adaptivity")')
    div0 = g.createNode("divide", "tri0")
    div0.setFirstInput(cv)
    red = g.createNode("polyreduce::2.0", "reduce")
    red.setFirstInput(div0)
    red.parm("target").set("pt_count")
    red.parm("finalcount").setExpression('max(40, int(point("../piece_begin", 0, "npts", 0) * ch("../CTRL/npts_scale")))')
    tag = g.createNode("attribwrangle", "tag_piece")
    tag.setFirstInput(red)
    tag.setInput(1, beg)
    tag.parm("class").set(2)
    tag.parm("snippet").set('i@fid = point(1, "fid", 0); f@fidf = i@fid;')
    end.setFirstInput(tag)
    set_menu(end.parm("itermethod"), "pieces", "By Pieces")
    set_menu(end.parm("method"), "merge", "Merge")
    set_menu(end.parm("class"), "point", "Points")
    end.parm("useattrib").set(1)
    end.parm("attrib").set("fid")
    end.parm("blockpath").set("../piece_begin")
    end.parm("templatepath").set("../piece_begin")
    out = g.createNode("null", "OUT")
    out.setFirstInput(end)
    out.setDisplayFlag(True); out.setRenderFlag(True)
    g.layoutChildren()
    hou.hipFile.save(a.hip)
    t1 = time.time()

    # 書き出し（既存の橋の geo_arrays：三角形と点の属性）
    tmp = obj.createNode("geo", "_pl33r01h_export")
    for ch in tmp.children():
        ch.destroy()
    src = tmp.createNode("object_merge", "src")
    src.parm("objpath1").set(out.path())
    div = tmp.createNode("divide", "tri"); div.setFirstInput(src)
    w = tmp.createNode("attribwrangle", "ptn"); w.setFirstInput(div)
    w.parm("class").set(3); w.parm("snippet").set("i@kh_ptn = @ptnum;")
    geo = w.geometry()
    P, tris, attrs = KH.geo_arrays(geo, attrs=("fidf",))
    fid = np.rint(attrs["fidf"][:, 0]).astype(np.int32)
    t2 = time.time()
    # 立つ中心線（stand の結果）：deform の検査に使う
    sg = stand.geometry()
    SP = np.frombuffer(sg.pointFloatAttribValuesAsString("P"), np.float32).reshape(-1, 3)
    SR = np.frombuffer(sg.pointFloatAttribValuesAsString("pscale"), np.float32)
    SF = np.frombuffer(sg.pointIntAttribValuesAsString("fid"), np.int32)
    SI = np.frombuffer(sg.pointIntAttribValuesAsString("ispad"), np.int32)
    SRow = np.frombuffer(sg.pointIntAttribValuesAsString("row"), np.int32)
    keep = SRow == 0
    SP, SR, SF, SI = SP[keep], SR[keep], SF[keep], SI[keep]
    # ランプの標本（deform が読む）
    xs = np.linspace(0.0, 1.0, 512)
    rc, rt = ctrl.parm("curl").evalAsRamp(), ctrl.parm("taper").evalAsRamp()
    ramps = {"curl": [rc.lookup(float(x)) for x in xs], "taper": [rt.lookup(float(x)) for x in xs]}
    os.makedirs(a.out, exist_ok=True)
    np.savez(a.out + "/key_tstar_mesh.npz", P_h=P.astype(np.float32), tris=tris.astype(np.int32), fid=fid,
             stand_P_h=SP, stand_R=SR, stand_fid=SF, stand_ispad=SI)
    json.dump({"curl": ramps["curl"], "taper": ramps["taper"], "x": xs.tolist(),
               "curl_keys": [list(k) for k in zip(rc.keys(), rc.values())], "taper_keys": [list(k) for k in zip(rt.keys(), rt.values())]},
              open(a.out + "/ramps.json", "w", encoding="utf-8"))
    tmp.destroy()
    per = np.bincount(fid, minlength=len(D["fingers"]))
    rep = {"houdini": hou.applicationVersionString(), "hip": a.hip, "points": int(len(P)), "triangles": int(len(tris)),
           "pieces": int((per > 0).sum()), "fingers": len(D["fingers"]), "empty_pieces": [D["fingers"][i]["id"] for i in np.where(per == 0)[0]],
           "pts_per_piece_pct": np.percentile(per[per > 0], [0, 10, 50, 90, 100]).tolist(),
           "nodes": [n.path() for n in g.children()], "cook_s": round(t2 - t1, 1), "build_s": round(t1 - t0, 1),
           "errors": [n.path() + ": " + "; ".join(n.errors()) for n in g.allSubChildren() if n.errors()]}
    json.dump(rep, open(a.out + "/build_report.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(rep, ensure_ascii=False)[:2500])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fingers", required=True)
    ap.add_argument("--hip", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--npts-scale", type=float, default=1.0)
    build(ap.parse_args())
