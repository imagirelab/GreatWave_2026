# -*- coding: utf-8 -*-
"""設計29修正01（手渡し (a)）：色面（NPR の色区）を K*′ へ焼き直すための入力を作る。

美術優先28修正01 の af28r01_bake_input.py と同じ包み方で、美術優先28 の af28_bake_input.py をそのまま読み込み、
固定値のファイル・K* の置き場所・出力先だけを差し替えて実行する（美術優先28・28修正01 のファイルは変えない）。
違いは K* だけ：26修正01 の K*（kstar_a45.gwb、e9bc3572…）の代わりに、設計28修正01 で採った K*′
（Unity/Build/Design/28R01F/kstar_final/kstarR4_a45.gwb、38a9b11a…。400 列 × 240 行で、格子の添字・三角形は K* と同じ）を使う。
af28_bake_input.py は K* を「<kstar_dir>/kstar_a45.gwb」「<kstar_dir>/kstar_a45_meta.json」の名前で読むので、
K*′ の 2 ファイルを出力先の kstar/ へその名前で写す（中身は同じ bytes。SHA-256 を確かめる）。
原画側の入力（符号付き距離・有効域・調色板・線幅）は美術優先28 と同じ入力から同じ式で作るので、28修正01 と同じ bytes になるはずで、それを確かめて記録する。

使い方（リポジトリの根で。py -3.10、numpy・OpenCV だけ）:
    py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_bake_input.py
出力（Git 対象外）：
    Unity/Build/Design/29R01/bake_kp/kstar/kstar_a45.gwb・kstar_a45_meta.json（K*′ の写し）
    Unity/Build/Design/29R01/bake_kp/ds29r01_bake_params.json（af28r01_params.json の K* と出力先だけを変えた一時の固定値）
    Unity/Build/Design/29R01/bake_kp/bake_input/（af28_bake_meta.json ほか。書式は美術優先28 と同じ。UV3 の表は K*′ の形から作り直す）
続き：Unity の GreatWave.Design29.EditorTools.DS29R01Bake.BakeKStarPrime（Tools/GWWaveGen/ds29r01/run_ds29r01_unity.ps1）で焼く。
"""
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
COLOUR = os.path.join(REPO, "Tools", "PaintingTruth", "colour")
sys.path.insert(0, COLOUR)
import af28_bake_input as B  # noqa: E402

SRC_PARAMS_REL = "Tools/PaintingTruth/colour/af28r01_params.json"
SELF_REL = "Tools/GWWaveGen/ds29r01/ds29r01_bake_input.py"
KP_DIR_REL = "Unity/Build/Design/28R01F/kstar_final"
KP_GWB = "kstarR4_a45.gwb"
KP_META = "kstarR4_a45_meta.json"
KP_GWB_SHA = "38a9b11ab63cccb45cf2cb7776ae3a59485d58102e96cabaf828fb36d14cf19a"
BUILD_REL = "Unity/Build/Design/29R01/bake_kp"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    build = os.path.join(REPO, BUILD_REL)
    kdir_rel = BUILD_REL + "/kstar"
    kdir = os.path.join(REPO, kdir_rel)
    os.makedirs(kdir, exist_ok=True)
    src_gwb = os.path.join(REPO, KP_DIR_REL, KP_GWB)
    src_meta = os.path.join(REPO, KP_DIR_REL, KP_META)
    if sha256(src_gwb) != KP_GWB_SHA:
        raise SystemExit("K*′ の .gwb の SHA-256 が記録（設計28修正01 §4.1）と違います: " + src_gwb)
    dst_gwb = os.path.join(kdir, "kstar_a45.gwb")
    dst_meta = os.path.join(kdir, "kstar_a45_meta.json")
    shutil.copyfile(src_gwb, dst_gwb)
    shutil.copyfile(src_meta, dst_meta)
    if sha256(dst_gwb) != KP_GWB_SHA:
        raise SystemExit("写した K*′ の SHA-256 が違います。")
    m = json.load(open(dst_meta, encoding="utf-8"))
    if m["files"]["gwb_sha256"] != KP_GWB_SHA:
        raise SystemExit("K*′ の meta の gwb_sha256 が .gwb と違います。")

    P = json.load(open(os.path.join(REPO, SRC_PARAMS_REL), encoding="utf-8"))
    P["schema"] = "GreatWave.DS29R01.bake_params/1"
    P["number"] = "設計29修正01"
    P["note_ja"] = ("設計29修正01 の焼き直し（K*′）の一時の固定値。美術優先28修正01 の af28r01_params.json を写し、"
                    "kstar_dir・kstar_gwb_sha256_expected・build_dir・evidence_dir だけを変えた（Git 対象外）。")
    P["source_params_28r01"] = SRC_PARAMS_REL
    P["kstar_dir"] = kdir_rel
    P["kstar_gwb_sha256_expected"] = {"a45": KP_GWB_SHA}
    P["kstar_source"] = {"gwb": KP_DIR_REL + "/" + KP_GWB, "meta": KP_DIR_REL + "/" + KP_META, "gwb_sha256": KP_GWB_SHA,
                         "meta_sha256": sha256(src_meta)}
    P["build_dir"] = BUILD_REL
    P["evidence_dir"] = BUILD_REL + "/evidence"
    params_rel = BUILD_REL + "/ds29r01_bake_params.json"
    with open(os.path.join(REPO, params_rel), "w", encoding="utf-8", newline="\n") as f:
        json.dump(P, f, ensure_ascii=False, indent=1)
        f.write("\n")

    B.PARAMS_REL = params_rel
    B.KSTAR_DIR_REL = kdir_rel
    sys.argv = [sys.argv[0], "--build", BUILD_REL]
    rc = B.main()
    out_dir = os.path.join(build, "bake_input")
    rec_p = os.path.join(out_dir, "af28_bake_input_record.json")
    rec = json.load(open(rec_p, encoding="utf-8"))
    rec["schema"] = "GreatWave.DS29R01.bake_input_record/1"
    rec["number"] = "設計29修正01"
    rec["command"] = "py -3.10 -B " + SELF_REL
    rec["wrapped_ja"] = ("美術優先28 の af28_bake_input.py を読み込み、PARAMS_REL と KSTAR_DIR_REL と --build だけを差し替えて実行した"
                         "（美術優先28・28修正01 のファイルは変えていない）。K* は設計28修正01 の K*′（" + KP_DIR_REL + "/" + KP_GWB + "）。")
    rec["inputs_sha256"][SELF_REL] = sha256(os.path.join(REPO, SELF_REL))
    same = {}
    r28 = os.path.join(REPO, "Unity/Build/ArtFirst/28修正01/bake_input/af28_bake_input_record.json")
    if os.path.exists(r28):
        o28 = json.load(open(r28, encoding="utf-8"))["outputs_sha256"]
        for name in ("paint_sdf_rgba16f.bin", "paint_valid_r8.bin"):
            a = [v for k, v in rec["outputs_sha256"].items() if k.endswith(name)]
            b = [v for k, v in o28.items() if k.endswith(name)]
            same[name] = bool(a and b and a[0] == b[0])
    rec["same_as_28r01_paint_side"] = same
    with open(rec_p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("DS29R01_BAKE_INPUT_DONE same_as_28r01", same, "uv3_warp", json.dumps(rec.get("kstar", {}).get("a45", {}).get("uv3_warp", {}), ensure_ascii=False)[:400])
    return rc


if __name__ == "__main__":
    sys.exit(main())
