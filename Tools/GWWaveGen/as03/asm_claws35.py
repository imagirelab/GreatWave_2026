# -*- coding: utf-8 -*-
"""美術の見本03 の組み立て：面の内（FACE_INTERIOR 25 本）と近い海（NEAR_SEA 10 本）の爪 35 本だけを描く爪の並びを作る。
見本02 修正の回 1 の爪の並び（83 本、案 A、Build/Polish/sample02/fix01/assemble/claws/mesh）を読み取りのみで使い、
波頭の冠の役（CREST_CROWN 48 本。調べ S2 の claw_roles.json。B1 の冠の中で指の先になった爪）の頂点を、その爪の最初の頂点（根元）へ潰す
（面積 0 の三角形は描かれない。設計34 の「見えないコマの爪は根元の点に潰す」と同じ決まり）。爪の並び（83 項目・頂点の番号・三角形・面の種類・骨格）は変えない。
35 本の頂点は見本02 とバイトまで同じ。出力（Git 対象外）：Unity/Build/Polish/sample03/assemble/claws35/。
使い方：py -3.10 -B Tools/GWWaveGen/as03/asm_claws35.py
"""
import hashlib
import json
import os
import shutil

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
SRC = REPO + "/Unity/Build/Polish/sample02/fix01/assemble/claws/mesh"
ROLES = REPO + "/Unity/Build/Polish/sample03/study/claw_roles.json"
CROWN = {m: REPO + "/Unity/Build/Polish/sample03/crown/%s/as03_crown_layout.json" % m for m in ("OUT", "IN")}
OUT = REPO + "/Unity/Build/Polish/sample03/assemble/claws35"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    os.makedirs(OUT, exist_ok=True)
    lay = json.load(open(SRC + "/ds33_claw_layout.json", encoding="utf-8"))
    roles = json.load(open(ROLES, encoding="utf-8"))
    role_of = {c["id"]: c["role"] for c in roles["claws"]}
    crown_ids = {m: sorted(u["id"] for u in json.load(open(p, encoding="utf-8"))["user_claws"]) for m, p in CROWN.items()}
    assert crown_ids["OUT"] == crown_ids["IN"], "冠 OUT と IN の利用者の爪が違う"
    crown_set = set(crown_ids["OUT"])
    assert crown_set == {k for k, v in role_of.items() if v == "CREST_CROWN"}, "S2 の冠の役と B1 の冠の爪が違う"
    nv = lay["vertices"]
    fr = np.fromfile(SRC + "/" + lay["files"]["frames"]["file"], np.float32)
    assert fr.size == lay["frames"] * nv * 3
    fr = fr.reshape(lay["frames"], nv, 3).copy()
    keep, drop = [], []
    for c in lay["claws"]:
        uid = c["user_id"]
        o, n = c["vert_offset"], c["vert_count"]
        if uid in crown_set:
            fr[:, o:o + n, :] = fr[:, o:o + 1, :]   # 根元の点へ潰す
            drop.append(uid)
        else:
            keep.append({"user_id": uid, "id": c["id"], "role": role_of[uid]})
    assert len(keep) == 35 and len(drop) == 48
    fp = OUT + "/ds33_claw_frames_f32.bin"
    fr.astype(np.float32).tofile(fp)
    for k in ("tris", "tri_attr", "skel"):
        shutil.copy2(SRC + "/" + lay["files"][k]["file"], OUT + "/" + lay["files"][k]["file"])
        assert sha(OUT + "/" + lay["files"][k]["file"]) == lay["files"][k]["sha256"]
    lay2 = json.loads(json.dumps(lay))
    lay2["files"]["frames"]["sha256"] = sha(fp)
    lay2["files"]["frames"]["bytes"] = os.path.getsize(fp)
    lay2["as03_asm"] = {
        "tool": "Tools/GWWaveGen/as03/asm_claws35.py",
        "noteJa": "見本03 の組み立て：波頭の冠の役の 48 本（B1 の冠の中で指の先になった爪）の頂点を根元の 1 点へ潰し、描かないようにした。"
                  "残りの 35 本（面の内 25・近い海 10）の頂点は見本02 修正の回 1 とバイトまで同じ。",
        "source_layout": {"path": SRC + "/ds33_claw_layout.json", "sha256": sha(SRC + "/ds33_claw_layout.json")},
        "source_frames_sha256": lay["files"]["frames"]["sha256"],
        "roles": {"path": ROLES, "sha256": sha(ROLES)},
        "kept": keep, "collapsed_crest_crown": sorted(drop),
        "kept_counts": {r: sum(1 for k in keep if k["role"] == r) for r in ("FACE_INTERIOR", "NEAR_SEA")},
    }
    json.dump(lay2, open(OUT + "/ds33_claw_layout.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 確かめ：残した爪の頂点は元とバイトまで同じ
    fr0 = np.fromfile(SRC + "/" + lay["files"]["frames"]["file"], np.float32).reshape(lay["frames"], nv, 3)
    same = all(np.array_equal(fr0[:, c["vert_offset"]:c["vert_offset"] + c["vert_count"]], fr[:, c["vert_offset"]:c["vert_offset"] + c["vert_count"]])
               for c in lay["claws"] if c["user_id"] not in crown_set)
    print(json.dumps({"kept": len(keep), "collapsed": len(drop), "kept_counts": lay2["as03_asm"]["kept_counts"], "kept_vertices_identical": same,
                      "frames_sha256": lay2["files"]["frames"]["sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
