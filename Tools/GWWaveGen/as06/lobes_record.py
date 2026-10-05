# -*- coding: utf-8 -*-
"""美術の見本06・B-LOBES：道具・入力・出力の SHA-256 と主な数を run.json に書く（記録の付け）。
py -3.10 -B Tools/GWWaveGen/as06/lobes_record.py
出力：Unity/Build/Polish/sample06/lobes/run.json
"""
import glob
import hashlib
import json
import os
import time

REPO = "G:/Unity/GreatWave_2026_Fresh"
P = REPO + "/Unity/Build/Polish"
P6 = P + "/sample06/lobes"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return p.replace("\\", "/").replace(REPO + "/", "")


def main():
    tools = sorted(glob.glob(REPO + "/Tools/GWWaveGen/as06/*"))
    inputs = [P + "/sample04/fix1/shape/final/cand/kstarAS04F_a45_rows.npz", P + "/sample05/fix1/B/final/cand/kstarAS05B_a45_rows.npz",
              P + "/sample04/wave4/mesh_fix1/wave4.json", P + "/sample05/fix1/B/mesh/white_mask_as05b_f32.bin",
              P + "/sample04/fix1/shape/mesh/white_mask_as04f_f32.bin", P + "/sample05/fix1/assemble/B/mesh/union_AS05B_f1.json",
              P + "/sample05/study/targets.json"]
    outs = {}
    for tag, fin, asm in (("LB1", "final", "assemble"), ("LB2", "final2", "assemble2")):
        files = [P6 + "/%s/cand/kstarAS06L_a45%s" % (fin, x) for x in ("_rows.npz", ".gwb", "_labels.npy", "_fields.npz", "_build_log.json")]
        files += [P6 + "/%s/mesh/hero_smooth_as06l.bin" % fin, P6 + "/%s/mesh/white_mask_as06l_f32.bin" % fin,
                  P6 + "/%s/mesh/union_AS06L.bin" % asm, P6 + "/%s/claws/ds33_claw_layout.json" % fin,
                  P6 + "/rules_check_%s.json" % tag, P6 + "/%s/measure/targets_%s.json" % (asm, tag)]
        outs[tag] = {rel(p): sha(p) for p in files if os.path.isfile(p)}
    rc = {}
    for tag in ("LB1", "LB2"):
        p = P6 + "/rules_check_%s.json" % tag
        if os.path.isfile(p):
            r = json.load(open(p, encoding="utf-8"))
            rc[tag] = {"summary": r.get("summary"), "S11_must": r["rules"]["S11"]["must_pass"], "S11_must_fail": r["rules"]["S11"]["must_fail_ids"],
                       "G1_stretch_gw_tri_outside": r["rules"]["G1"]["surface_stretch_front"]["hero"]["patterned_face"]["gw_tri_outside_1_3_to_3x"]}
    sheets = sorted(glob.glob(P6 + "/deliver/sheets/*.png"))
    out = {"schema": "GreatWave.AS06.lobes_run/1", "date": time.strftime("%Y-%m-%d %H:%M"),
           "note_ja": "美術の見本06 B-LOBES（Q34）。生成器は参照モデルの OBJ・写真を読まない（この作業では OBJ・写真とも開いていない）。原画のカメラは縁の頂の置き場の確かめと測りにだけ使った。",
           "tools": {rel(p): sha(p) for p in tools if os.path.isfile(p)},
           "inputs": {rel(p): sha(p) for p in inputs if os.path.isfile(p)},
           "outputs": outs, "sheets": {rel(p): sha(p) for p in sheets}, "rules_summary": rc,
           "reference_model_read": False, "photos_read": False, "projection_used_for_color": False}
    json.dump(out, open(P6 + "/run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("RUN_JSON", P6 + "/run.json", len(out["tools"]), len(out["sheets"]))


if __name__ == "__main__":
    main()
