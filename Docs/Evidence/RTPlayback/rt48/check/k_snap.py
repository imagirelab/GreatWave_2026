# -*- coding: utf-8 -*-
"""7. プロジェクトの RT48 の外が変わっていないか、R3 の記録が変わっていないかを、今のファイルの SHA-256 を自分で計算して確かめる。
出力：out/k_snap.json"""
import hashlib, os
from k_lib import *

PROJ = "G:/Unity/GreatWave_2026_Fresh/Unity"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def now_files():
    out = {}
    for top in ("Assets", "ProjectSettings", "Packages"):
        for d, _, fs in os.walk(os.path.join(PROJ, top)):
            for fn in fs:
                p = os.path.join(d, fn)
                rel = os.path.relpath(p, PROJ).replace("\\", "/")
                out[rel] = p
    return out


RTP = "Assets/GreatWave/RT48"
res = {}
early = jload(RT + "/unity/snap_before.json")      # RT48 の Unity の段の前（10/10 19:24 UTC）
b = jload(RT + "/verify/snap_before_verify.json"); a = jload(RT + "/verify/snap_after_verify.json")
res["verify_snaps"] = dict(added=sorted(set(a["files"]) - set(b["files"])), removed=sorted(set(b["files"]) - set(a["files"])),
                           changed=sorted(k for k in set(a["files"]) & set(b["files"]) if a["files"][k][1] != b["files"][k][1]))
cur = now_files()
outside_changed, outside_missing, outside_new = [], [], []
for rel, (size, h) in early["files"].items():
    if rel.startswith(RTP):
        continue
    if rel not in cur:
        outside_missing.append(rel); continue
    if sha(cur[rel]) != h:
        outside_changed.append(rel)
for rel in cur:
    if rel not in early["files"] and not (rel.startswith(RTP + "/") or rel == RTP + ".meta"):
        outside_new.append(rel)
res["since_early_snapshot"] = dict(early_utc=early["utc"], n_early=len(early["files"]), n_now=len(cur),
                                   outside_changed=outside_changed, outside_missing=outside_missing, outside_new=outside_new,
                                   rt48_now=sum(1 for r in cur if r.startswith(RTP)))
# R3 の記録（計画の時に記録した SHA-256 と今）
pn = jload(RT + "/plan/plan_numbers.json")["inputs_sha256"]
r3diff = [k for k, v in pn.items() if os.path.exists(R3 + "/" + k) and sha(R3 + "/" + k) != v]
res["r3_inputs"] = dict(n=len(pn), differ=r3diff, n_files_now=len(os.listdir(R3)))
# 焼きのファイルと manifest の SHA-256
m = jload(RT + "/data/coarse/manifest.json")
res["bake_files"] = {k: (sha(RT + "/data/coarse/" + v["name"]) == v["sha256"]) for k, v in m["files"].items()}
# Editor とプレイヤーの書き出しが同じか
res["editor_vs_player_bytes"] = {fn: sha(RT + f"/verify/coarse/unity_editor/{fn}") == sha(RT + f"/verify/coarse/unity_player/{fn}") for fn in ("curves.bin", "holdout_out.bin")}
print(res)
jsave(OUT + "/k_snap.json", res)
