# -*- coding: utf-8 -*-
"""設計41：Blender の出力の FBX を Unity の資産へ写す（.meta は M1 の boat_blockout.fbx.meta の取り込みの設定を写し、GUID だけ新しくする）。

設計07 で確かめた Unity 側の取り込みの設定（globalScale 1、useFileScale 1、bakeAxisConversion 0 など）を、M1 の FBX と同じにするため。
.meta が既にあれば GUID を保つ（設定の行は M1 と同じか確かめるだけ）。

使い方（リポジトリの根で）: py -3.10 -B Tools/GWWaveGen/ds41/ds41_stage_unity.py
"""
import hashlib
import os
import re
import shutil
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(REPO, "Unity", "Build", "Design", "41", "model", "blender", "ds41_oshiokuri.fbx")
DST_DIR = os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design41", "Models")
DST = os.path.join(DST_DIR, "ds41_oshiokuri.fbx")
M1_META = os.path.join(REPO, "Unity", "Assets", "GreatWave", "Art", "M1", "boat_blockout.fbx.meta")


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    os.makedirs(DST_DIR, exist_ok=True)
    shutil.copyfile(SRC, DST)
    meta = DST + ".meta"
    with open(M1_META, encoding="utf-8") as f:
        m1 = f.read()
    guid = None
    if os.path.exists(meta):
        with open(meta, encoding="utf-8") as f:
            guid = re.search(r"^guid: ([0-9a-f]{32})", f.read(), re.M).group(1)
    guid = guid or uuid.uuid4().hex
    text = re.sub(r"^guid: [0-9a-f]{32}", "guid: " + guid, m1, count=1, flags=re.M)
    with open(meta, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    keys = ("globalScale", "useFileScale", "useFileUnits", "bakeAxisConversion", "materialImportMode", "importAnimation", "isReadable")
    for k in keys:
        a = re.findall(r"^\s*%s: .*$" % k, m1, re.M)
        b = re.findall(r"^\s*%s: .*$" % k, text, re.M)
        assert a == b, k
    write_expect()
    print("DS41_STAGE fbx=%s sha256=%s guid=%s" % (os.path.relpath(DST, REPO), sha(DST), guid))


def write_expect():
    """Unity の設計07 の検査（DS41Boats.ImportCheck）が読む期待値。Blender の値を (x, y, z) → (−x, z, −y) で写したもの（JsonUtility で読める形）。"""
    import json
    rp = os.path.join(REPO, "Unity", "Build", "Design", "41", "model", "blender", "ds41_blender_report.json")
    with open(rp, encoding="utf-8") as f:
        r = json.load(f)
    objs = []
    for n, o in sorted(r["objects"].items()):
        mn, mx = o["min"], o["max"]
        objs.append({"name": n, "min": [-mx[0], mn[2], -mx[1]], "max": [-mn[0], mx[2], -mn[1]],
                     "vertices": o["vertices"]})
    st = r["stations"]
    fr = r["params"]["values"]["frame"]
    bt, stt = fr["bow_tip_blender"], fr["stern_tip_blender"]
    ex = {"blenderReportSha256": sha(rp), "mappingJa": "Blender (x, y, z) → Unity (−x, z, −y)（設計07 の実測）",
          "objects": objs, "bowTip": [-bt[0], bt[2], -bt[1]], "sternTip": [-stt[0], stt[2], -stt[1]],
          "tipToTip": fr["tip_to_tip_units"], "halfBeam": r["derived_units"]["half_beam_max"],
          "stationZ": [-0.5 * (s["bottom_center"][1] + s["sheer"][1]) for s in st],
          "stationBottom": [s["bottom_center"][2] for s in st], "stationSheer": [s["sheer"][2] for s in st],
          "starboardPrefix": "Boat41_Oar_S", "portPrefix": "Boat41_Oar_P", "starboardCount": 3, "portCount": 4}
    op = os.path.join(REPO, "Unity", "Build", "Design", "41", "model", "unity", "ds41_unity_expect.json")
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, "w", encoding="utf-8", newline="\n") as f:
        json.dump(ex, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
