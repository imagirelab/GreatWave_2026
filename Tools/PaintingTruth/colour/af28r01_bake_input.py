# -*- coding: utf-8 -*-
"""番号28修正01：新しい K*（番号26修正01）への焼き直しの入力を作る。

番号28 の af28_bake_input.py をそのまま読み込み、固定値（af28r01_params.json）と K* の置き場所
（Unity/Build/ArtFirst/26修正01/kstar）と出力先（Unity/Build/ArtFirst/28修正01）だけを差し替えて実行する。
番号28 のファイルは変えない。原画側の符号付き距離・有効域・調色板・線幅は番号28 と同じ入力から同じ式で作るので、
SHA-256 が番号28 の記録と一致するはずで、それを確かめて記録する。

使い方（リポジトリの根で実行。py -3.10、numpy・OpenCV だけ）:
    py -3.10 Tools/PaintingTruth/colour/af28r01_bake_input.py
出力（Git 対象外）：
    Unity/Build/ArtFirst/28修正01/bake_input/（af28_bake_meta.json ほか。書式は番号28 と同じ）
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import af28_bake_input as B  # noqa: E402

PARAMS_REL = "Tools/PaintingTruth/colour/af28r01_params.json"
SELF_REL = "Tools/PaintingTruth/colour/af28r01_bake_input.py"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    P = json.load(open(os.path.join(REPO, PARAMS_REL), encoding="utf-8"))
    for k, want in P["kstar_gwb_sha256_expected"].items():
        got = sha256(os.path.join(REPO, P["kstar_dir"], "kstar_%s.gwb" % k))
        if got != want:
            raise SystemExit("26修正01 の K* の SHA-256 が記録と違います: %s（記録 %s）" % (got, want))
    B.PARAMS_REL = PARAMS_REL
    B.KSTAR_DIR_REL = P["kstar_dir"]
    sys.argv = [sys.argv[0], "--build", P["build_dir"]]
    rc = B.main()
    out_dir = os.path.join(REPO, P["build_dir"], "bake_input")
    rec_p = os.path.join(out_dir, "af28_bake_input_record.json")
    rec = json.load(open(rec_p, encoding="utf-8"))
    rec["schema"] = "GreatWave.AF28R01.bake_input_record/1"
    rec["number"] = "28修正01"
    rec["command"] = "py -3.10 " + SELF_REL
    rec["wrapped_ja"] = "番号28 の af28_bake_input.py を読み込み、PARAMS_REL と KSTAR_DIR_REL と --build だけを差し替えて実行した（番号28 のファイルは変えていない）。"
    rec["inputs_sha256"][SELF_REL] = sha256(os.path.join(REPO, SELF_REL))
    # 番号28 の原画側の入力との一致（同じ入力・同じ式なので一致するはず）
    r28 = os.path.join(REPO, "Unity/Build/ArtFirst/28/bake_input/af28_bake_input_record.json")
    same = {}
    if os.path.exists(r28):
        o28 = json.load(open(r28, encoding="utf-8"))["outputs_sha256"]
        for name in ("paint_sdf_rgba16f.bin", "paint_valid_r8.bin"):
            a = [v for k, v in rec["outputs_sha256"].items() if k.endswith(name)]
            b = [v for k, v in o28.items() if k.endswith(name)]
            same[name] = bool(a and b and a[0] == b[0])
    rec["same_as_number28_paint_side"] = same
    with open(rec_p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("AF28R01_BAKE_INPUT_DONE same_as_28", same)
    return rc


if __name__ == "__main__":
    sys.exit(main())
