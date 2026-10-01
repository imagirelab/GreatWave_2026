# -*- coding: utf-8 -*-
"""仕上げ32 修正の回 1：爪の帯を、修正の回 1 の一覧・ID（Unity/Build/Polish/32/fix01/list）と、名前の付いた決まりを足した rig・anim で作り直す（numpy）。

pl32_claws.py と同じ差し替え（主役波 Unity/Build/Polish/32/white/hero_pkg、時間曲線 G_p28rec、根元の色区は PL29 の白の範囲）で、
  - rig：pl32f_claw_rig.py（設計33 の ds33_claw_rig.py の写しに pl32f_white_root_only・pl32f_hang_over_indigo・pl32f_fold_guard・
    pl32f_branch_rule・pl32f_tuft_base を足したもの）
  - anim：pl32f_claw_anim.py（pl32_claw_anim.py の写しに pl32f_lift_facing・pl32f_width_fit・動きの検査を足したもの）
を回す。手前の波の爪（一覧の zone "front"。利用者の 100 本から加えた）は、ID の道具が主役波のシートの裏の面に当てて結び付けてしまうので、
ここで結び付けを外す（手前の波には爪の層がない。右側の爪と同じく一覧にだけ置く）。
出力（Git 対象外）：Unity/Build/Polish/32/fix01/claws/（設計33 と同じ名前のファイル。DS34ClawPlayer がそのまま読む ds33_claw_layout.json を含む）
"""
import json
import os
import shutil
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds33")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl32")
import ds33_common as U  # noqa: E402

B = REPO + "/Unity/Build/Polish"
LIST = B + "/32/fix01/list"
RIGIN = B + "/32/fix01/rigin"
U.OUT = B + "/32/fix01/claws"
U.D32 = RIGIN
U.HERO = B + "/32/white/hero_pkg"
U.WARP = B + "/28/G_p28rec/timewarp_G_p28rec.json"
ZONE = B + "/32/white/pl31_zone_vertex.npy"


def prepare():
    os.makedirs(RIGIN, exist_ok=True)
    inv = json.load(open(LIST + "/ds32_claw_inventory.json", encoding="utf-8"))
    zone = {c["id"]: c["zone"] for c in inv["claws"]}
    ids = json.load(open(LIST + "/ds32_ids.json", encoding="utf-8"))
    off = []
    for c in ids["claws"]:
        if c.get("bound") and zone.get(c["id"]) != "main":
            c["bound"] = False
            c["pl32f_unbound_ja"] = "手前の波の爪（一覧の zone %s）。主役波のシートに結び付けない" % zone.get(c["id"])
            off.append(c["id"])
    json.dump(ids, open(RIGIN + "/ds32_ids.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    shutil.copyfile(LIST + "/ds32_claw_inventory.json", RIGIN + "/ds32_claw_inventory.json")
    return off


def main():
    part = sys.argv[1] if len(sys.argv) > 1 else "all"
    os.makedirs(U.OUT, exist_ok=True)
    zone = np.load(ZONE)
    U.W31.vertex_class = lambda R, C: (np.where(zone.reshape(-1), 0, 3).astype(np.int32), None)
    if part in ("rig", "all"):
        off = prepare()
        print("front claws unbound", off, flush=True)
        import pl32f_claw_rig as RIG
        sys.argv = [sys.argv[0], "--out", U.OUT]
        RIG.main()
    if part in ("anim", "all"):
        import pl32f_claw_anim as ANIM
        sys.argv = [sys.argv[0], "--out", U.OUT]
        ANIM.main()
    for fn in ("ds33_claw_rig.json", "ds33_claw_layout.json", "ds33_claw_checks.json"):
        p = os.path.join(U.OUT, fn)
        if os.path.exists(p):
            d = json.load(open(p, encoding="utf-8"))
            d["pl32f_note_ja"] = ("仕上げ32 修正の回 1：pl32f_claws.py で、一覧と ID（Unity/Build/Polish/32/fix01/list）・主役波（Unity/Build/Polish/32/white/hero_pkg）・"
                                  "時間曲線（G_p28rec）・根元の色区（PL29 の白の範囲）と、rig（pl32f_claw_rig.py）・anim（pl32f_claw_anim.py）で回した")
            json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
