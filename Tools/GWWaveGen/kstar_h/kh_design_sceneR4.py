# -*- coding: utf-8 -*-
"""設計28修正01：K*′（精修 R4）の手続きの網を Houdini のシーンに組み、保存する（hython）。
R4：lip_head の後に far_end（奥の行の背をなめらかに・頂を丸く）、side_edges の後に sculpt（整えの層）の節点を足した（kh_houdini_designR4 の説明）。
以下は R3 の説明。
設計28修正01：K*′（精修 R3）の手続きの網を Houdini のシーンに組み、保存する（hython）。
R3：back_smooth の節点を back_shape（背を外へ・背のならし・奥の端の背を相似に・背の奥行きの下限・背のくびれを埋める）に替えた
（kh_houdini_designR3 の説明）。保存の前に参照モデルの節点を消し、参照のパスの文字列が残らないことを確かめる（R1 から同じ）。以下は R2 の説明。
設計28修正01：K*′（精修 R2）の手続きの網を Houdini のシーンに組み、保存する（hython）。
R2：網に far_smooth・back_smooth・lip_head を足した（kh_houdini_designR2 の説明）。以下は R1 の説明。
設計28修正01：K*′（候補 H1A の精修 R1）の手続きの網を Houdini のシーンに組み、保存する（hython）。
R1：網に lip_profile を足し、参照モデルの節点（/obj/refmodel・/obj/refmodel_largeform。他者の彫刻のパスと、その大きな形の処理）を
保存の前に消す（F13(1)：リポジトリには測った比率と数値だけ）。

  hython kh_design_scene.py --design <design.json> [--base <kstar_h_base.hiplc>] [--out <kstar_h.hiplc>] [--verify <report.json>]

土台のシーン（kh_build_scene.py が作る PaintingCam・原画の板・海・K* / 第 2 回 / 第 3 回・参照モデル）を開き、
/obj/kstar_h_design（CTRL → guides → bregion_ledge → side_edges → skin → OUT）を足して、設計の json の鍵を CTRL の
ramp へ入れる。/out/painting_view（OpenGL、原画の板の前）は kstar_h_design と海を描く。形はシーンに保存しない（毎回 cook）。
--verify：開き直して cook し、点の数・行の面からのずれ・CTRL から読み戻した設計が json と同じかを確かめ、原画視点を描く。
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
import kh_designR4 as D  # noqa: E402
import kh_houdini_designR4 as HD  # noqa: E402

HIP_OUT = os.path.join(KC.HIP_DIR, "kstar_h_R4.hiplc")
PV_OUT = os.path.join(KC.OUT_ROOT, "final", "houdini_painting_view_R4.png")


def build(a):
    t0 = time.time()
    hou.hipFile.load(a.base, suppress_save_prompt=True, ignore_load_warnings=True)
    obj = hou.node("/obj")
    old = obj.node("kstar_h_design")
    if old is not None:
        old.destroy()
    geo = obj.createNode("geo", "kstar_h_design")
    for ch in geo.children():
        ch.destroy()
    ctrl = geo.createNode("null", "CTRL")
    HD.add_ctrl_parms(ctrl)
    design = D.Design.load(a.design)
    HD.set_ctrl_from_design(ctrl, design, os.path.abspath(a.design).replace("\\", "/"))
    fl = json.load(open(a.design, encoding="utf-8")).get("fit_log")
    if fl and ctrl.parm("fit_note"):
        ctrl.parm("fit_note").set(json.dumps(fl.get("summary", {}), ensure_ascii=False)[:500])
    ctrl.setColor(hou.Color(0.9, 0.75, 0.2))
    ctrl.setComment("Named artist controls (ramps along the crest c). Edit here; everything downstream re-cooks.")

    def py(name, func, inp=None, comment=""):
        n = geo.createNode("python", name)
        n.parm("python").set(HD.PYSOP % (HERE.replace("\\", "/"), func))
        if inp is not None:
            n.setFirstInput(inp)
        n.setComment(comment)
        return n
    guides = py("guides", "sop_guides", comment="Per-section guide curves: 240 constant-c rows x 400 points. Round shell back concentric with the barrel, "
                "round top arc, lip hook, near-circular tube, foot flowing into a front trough (kh_design.section).")
    fsm = py("far_smooth", "sop_farsmooth", guides, "R2: the far rows' section shapes averaged along the crest relative to their lip tip "
             "(the tips that draw the painting's tube outline stay); sigma = CTRL far_smooth(c).")
    bsm = py("back_shape", "sop_backshape", fsm, "R3: the back shape, adding volume outward only (never carving): back_out (outward), back_fill (R2, 0), "
             "back_smooth (along the crest), back_tail (the far tail as similar copies of one row's back), back_depth (a minimum depth of the back "
             "behind the crest top, as a ratio of H: no lemon), back_env (fills the plan-view waist of the back: no point more than 0.6 m in front "
             "of the chord of its neighbours +-4 m). The crest top, the lip and the inner side never move (the painting outlines stay).")
    prof = py("lip_profile", "sop_lipprof", bsm, "Lip-top section profile (R1): the line of the lip top from the crest to the lip head "
              "(convex crest -> waist -> convex hook), 5 smooth modes along the section, ramps along c.")
    ledge = py("bregion_ledge", "sop_ledge", prof, "b region: second crest on the near shoulder: a broad ridge (R2) with 3 lobes along the crest; "
               "R3: the lobes also move along the painting camera's ray (ledge_lobe_depth), so they read in other views without moving the outline much.")
    head = py("lip_head", "sop_lipshift", ledge, "R2: the lip head (cols 186..214, fading to 140 / 268) moved as a whole: along the tip normal "
              "(lip_shift) and straight down (lip_drop). It draws the painting's lip-underside outline 72.")
    fend = py("far_end", "sop_farend", head, "R4 (both ends): the near tail (rows off the painting frame, c < -21) fades into a swell along c (no needle, no twisted lip end); the far rows' back as one smooth curve from the foot (no vertical wall and knee: the crease line seen "
              "from behind) and one round arc over their top, highest at the crest column (Q17: no right angle). The lip head and tip stay.")
    edges = py("side_edges", "sop_edges", fend, "Painting fit by the side edges only: normal offsets where PaintingCam grazes the surface "
               "(9 bands + 12 fine lip-top bands edgeL for the outline 132).")
    sculpt = py("sculpt", "sop_sculpt", edges, "R4: the sculpt layer: offsets along the section normal (15 column bands x ramps along c), solved by "
                "kh_R4_sculpt.py so that the judges' bulge measure (local quadric residual, 4 m / 6 m), the plan-view waist of the back at every "
                "height and the far tops shrink while the painting outline (the outline vertices and the visible grazing inner edges) does not move. "
                "The crest tops (above 0.92 H) never move.")
    skin = geo.createNode("skin", "skin")
    skin.setFirstInput(sculpt)
    skin.setComment("Skin the guide curves into the sheet (quads; points and attributes kept, so col/row survive).")
    nrm = geo.createNode("normal", "N")
    nrm.setFirstInput(skin)
    tint = geo.createNode("color", "tint")
    tint.setFirstInput(nrm)
    tint.parm("class").set(2)
    tint.parmTuple("color").set((0.82, 0.80, 0.74))
    out = geo.createNode("null", "OUT")
    out.setFirstInput(tint)
    out.setDisplayFlag(True); out.setRenderFlag(True)
    out.setColor(hou.Color(0.3, 0.8, 0.3))
    geo.layoutChildren()
    note = geo.createStickyNote("kh_design_note")
    note.setText("K*' R4 (Design 28R01, refine loop 4, the last loop)\n"
                 "CTRL ramps -> guides -> far_smooth -> back_shape -> lip_profile -> bregion_ledge -> lip_head -> far_end -> side_edges -> sculpt -> skin -> OUT (R4: far back smooth, far tops round, sculpt layer solved by kh_R4_sculpt.py)\n"
                 "OUT -> kh_bridge.py h2g (slice on the 240 row planes, attr columns) -> GWW0 400x240.\n"
                 "Fit: kh_R1_fit / kh_R2_fit (body), kh_R3_sil.py (silhouette edges), kh_R4_lipsmooth.py (lip head along c), kh_R4_sculpt.py (sculpt layer).\n"
                 "Reference model = someone else's sculpture: reference only (never read by the generator).")
    note.setSize(hou.Vector2(9, 2.2))
    geo.setComment("K*' R4 — procedural (Design 28R01, refine loop 4). Controls on CTRL.")
    geo.setColor(hou.Color(0.3, 0.8, 0.3))
    # show only the design and the sea by default
    for n in obj.children():
        if n.type().name() == "geo" and n.name() not in ("kstar_h_design", "sea"):
            n.setDisplayFlag(False)
    geo.setDisplayFlag(True)
    obj.layoutChildren()
    rop = hou.node("/out/painting_view")
    if rop is not None:
        for pn, v in (("vobjects", ""), ("forceobjects", "kstar_h_design sea"), ("picture", PV_OUT.replace("\\", "/"))):
            if rop.parm(pn) is not None:
                rop.parm(pn).set(v)
    # R1: no reference-model nodes in a scene that lives in the repository folder (F13(1))
    removed = []
    for nm in ("refmodel", "refmodel_largeform"):
        n = obj.node(nm)
        if n is not None:
            n.destroy(); removed.append("/obj/" + nm)
    # R3: also the comparison geometry of round 3's A3b (dropped under F13-1: its generator read the reference model, so its shape is a
    #     derivative of the reference's large form): no node of the scene loads it
    for n in list(obj.children()):
        hit = False
        for sn in [n] + list(n.allSubChildren()):
            for pm in sn.parms():
                try:
                    v = pm.unexpandedString()
                except Exception:
                    continue
                if "candA3b" in v or "A3b" in v.split("/")[-1]:
                    hit = True
        if hit:
            removed.append(n.path()); n.destroy()
    leaks = []
    for n in hou.node("/").allSubChildren():
        for pm in n.parms():
            try:
                v = pm.unexpandedString()
            except Exception:
                continue
            if "wave_repair" in v or "reality scan" in v or "北斋参考" in v or "candA3b" in v:
                leaks.append(pm.path())
    if leaks:
        raise SystemExit("reference-model paths left in the scene: %s" % leaks)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    hou.hipFile.save(a.out)
    return {"saved": a.out, "hip_bytes": os.path.getsize(a.out), "design": os.path.abspath(a.design), "build_seconds": round(time.time() - t0, 2),
            "removed_reference_nodes": removed, "reference_path_leaks": leaks}


def verify(rep, design_path):
    t0 = time.time()
    hou.hipFile.load(rep["saved"], suppress_save_prompt=True, ignore_load_warnings=True)
    out = {}
    ctrl = hou.node("/obj/kstar_h_design/CTRL")
    d_json = D.Design.load(design_path)
    d_hou = HD.design_from_ctrl(ctrl)
    ok, bad = HD.design_equal(d_json, d_hou)
    out["ctrl_equals_design_json"] = ok
    if not ok:
        out["ctrl_first_mismatch"] = bad
    node = hou.node("/obj/kstar_h_design/OUT")
    t1 = time.time()
    geo = node.geometry()
    out["cook_seconds"] = round(time.time() - t1, 2)
    out["points"] = len(geo.points()); out["prims"] = len(geo.prims())
    out["errors"] = [e for n in node.parent().children() for e in n.errors()]
    out["warnings"] = [w for n in node.parent().children() for w in n.warnings()]
    # rows back from Houdini vs the numpy build (same code, float32 points)
    c, A, Y = HD.points_to_rows(geo)
    c2, A2, Y2, P2 = D.build(d_json)
    out["houdini_vs_numpy_max_m"] = float(max(np.abs(A - A2).max(), np.abs(Y - Y2).max()))
    Ph = np.frombuffer(geo.pointFloatAttribValuesAsString("P"), np.float32).reshape(-1, 3).astype(np.float64)
    S = KC.sec(KC.h2u(Ph)).reshape(len(c), -1, 3)
    out["row_plane_spread_max_m"] = float(np.abs(S[..., 2] - c[:, None]).max())
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
    ap.add_argument("--design", required=True)
    ap.add_argument("--base", default=KC.HIP_BASE)
    ap.add_argument("--out", default=HIP_OUT)
    ap.add_argument("--verify", default=None)
    a = ap.parse_args()
    r = build(a)
    if a.verify:
        r = verify(r, a.design)
        os.makedirs(os.path.dirname(os.path.abspath(a.verify)), exist_ok=True)
        json.dump(r, open(a.verify, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    print(json.dumps(r, indent=1, ensure_ascii=False, default=str)[:4000])
