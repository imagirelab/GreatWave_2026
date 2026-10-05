# -*- coding: utf-8 -*-
"""美術の見本06 の直しの回（段の行 R8 → R9）：入出力の SHA-256 と、規則・目標の要約を run.json に書く（読むだけ。形は変えない）。
出力：Build/Polish/sample06/fix/run.json
使い方：py -3.10 -B Tools/GWWaveGen/as06/fix6_record.py
"""
import glob
import hashlib
import json
import os
import sys
import time

REPO = "G:/Unity/GreatWave_2026_Fresh"
P = REPO + "/Unity/Build/Polish"
PF = P + "/sample06/fix"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return p.replace("\\", "/").replace(REPO + "/", "")


def main():
    files = [PF + "/record_ja.md", PF + "/design_R9.json", PF + "/final/final/cand/kstarAS06R_a45_rows.npz", PF + "/final/final/cand/kstarAS06R_a45_build_log.json",
             PF + "/final/mesh/hero_smooth_as06r.json", PF + "/final/mesh/hero_smooth_as06r.bin", PF + "/final/mesh/white_mask_as06r_f32.bin",
             PF + "/mesh/union_AS06R9_f1.json", PF + "/mesh/union_AS06R9_f1.bin", PF + "/final/claws/ds33_claw_layout.json",
             P + "/sample06/rules_check_rows.json", P + "/sample06/rules_check_rows_before_fix.json",
             PF + "/measure/targets_R9.json", PF + "/measure/quick_R9/quick.json", PF + "/measure/prof_R9.json", PF + "/measure/prof_R8.json",
             PF + "/measure/t5t6_R9_v.json", PF + "/measure/t5t6_R9_ct.json", PF + "/measure/slivers.json", PF + "/measure/claw057.json",
             PF + "/measure/fix_items.json", PF + "/check/fix6_check.json", PF + "/render/R9/as03asm_render_report.json", PF + "/render/R9/as06asm_boat_1.json"]
    files += sorted(glob.glob(PF + "/sheets/*.png"))
    tools = sorted(glob.glob(REPO + "/Tools/GWWaveGen/as06/fix6_*"))
    r = json.load(open(P + "/sample06/rules_check_rows.json", encoding="utf-8"))
    b = json.load(open(P + "/sample06/rules_check_rows_before_fix.json", encoding="utf-8"))
    t = r["rules"]["S11"]["targets"]
    tb = b["rules"]["S11"]["targets"]
    out = {"schema": "GreatWave.AS06.fix6_run/1", "date": time.strftime("%Y-%m-%d %H:%M"),
           "note_ja": "美術の見本06 の直しの回（段の行 R8 → R9）。git の add・commit・push はしていない。参照モデルの OBJ と彫刻の写真は開いていない。"
                      "見本01〜05・採用の資産・作り（rows・lobes）と組み立て（assemble）の置き場は変えていない（読むだけ）。新しい Unity の資産は作っていない",
           "summary_R9": r["summary"], "summary_R8_before_fix": b["summary"],
           "s11_must_failed": {"R8": [k for k, v in tb.items() if v["kind"] == "must" and not v.get("pass")],
                               "R9": [k for k, v in t.items() if v["kind"] == "must" and not v.get("pass")]},
           "s11_must_passed": {"R8": sum(1 for v in tb.values() if v["kind"] == "must" and v.get("pass")),
                               "R9": sum(1 for v in t.values() if v["kind"] == "must" and v.get("pass")), "of": sum(1 for v in t.values() if v["kind"] == "must")},
           "files": {rel(p): {"sha256": sha(p), "bytes": os.path.getsize(p)} for p in files if os.path.isfile(p)},
           "tools": {rel(p): sha(p) for p in tools},
           "archives_ja": "途中の版 R9a・R9b・R9c の設計と測りは fix/archive_R9a・archive_R9b・archive_R9c（Git の対象外）"}
    json.dump(out, open(PF + "/run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ("summary_R9", "s11_must_failed", "s11_must_passed")}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
