# -*- coding: utf-8 -*-
"""仕上げ28（焼き直し）：設計29修正01 の色面の焼き込みを、仕上げ28 で採った最後の一コマ K*′ P28R2 で回し直すための入力を作る。

設計29修正01 の ds29r01_bake_input.py をそのまま読み込み、同じプロセスの中だけで K*′ の置き場所・SHA-256・出力先の固定値を差し替えて
main() を走らせる（ds29r01_bake_input.py・美術優先28 の af28_bake_input.py とその固定値のファイルは変えない）。違いは K*′ だけ：
  設計28修正01 の K*′ R4（Unity/Build/Design/28R01F/kstar_final/kstarR4_a45.gwb、38a9b11a…）の代わりに、
  仕上げ28 で凍結した K*′ P28R2（Unity/Build/Polish/28/kstar_p28/kstarP28R2_a45.gwb、79ff9fde…。400 列 × 240 行、格子の添字・三角形は同じ）。
原画の側の入力（符号付き距離・有効域）は 28修正01・29修正01 と同じ bytes になるはずで、それを確かめて記録する（same_as_28r01_paint_side）。

使い方（リポジトリの根で。py -3.10、numpy・OpenCV だけ）:
    py -3.10 -B Tools/GWWaveGen/pl28/pl28u_bake_input.py [--build Unity/Build/Polish/28/unity/bake_kp]
出力（Git 対象外）：<build>/kstar/（K*′ P28R2 の写し。kstar_a45.gwb・kstar_a45_meta.json の名前）、<build>/ds29r01_bake_params.json、<build>/bake_input/
続き：Unity の GreatWave.Design29.EditorTools.DS29R01Bake.BakeKStarPrime を -ds29r01BakeRoot Build/Polish/28/unity/bake_kp で
（Tools/GWWaveGen/pl28/run_pl28_unity.ps1）。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "ds29r01"))
import ds29r01_bake_input as D  # noqa: E402

SELF_REL = "Tools/GWWaveGen/pl28/pl28u_bake_input.py"
KP_DIR_REL = "Unity/Build/Polish/28/kstar_p28"
KP_GWB = "kstarP28R2_a45.gwb"
KP_META = "kstarP28R2_a45_meta.json"
KP_GWB_SHA = "79ff9fde8ea8ebf9b04897915d19717108fe826f0626b72384e891a6d53c6992"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", default="Unity/Build/Polish/28/unity/bake_kp")
    # 仕上げ28 の回復（rec）：凍結した別の K*′（例：Unity/Build/Polish/28/kstar_p28rec の kstarP28R2rec_a45）を焼く時に使う。既定は P28R2 のまま
    ap.add_argument("--kstar-dir", default=KP_DIR_REL)
    ap.add_argument("--gwb", default=KP_GWB)
    ap.add_argument("--meta", default=KP_META)
    ap.add_argument("--sha", default=KP_GWB_SHA)
    a = ap.parse_args()
    build_rel = a.build.replace("\\", "/").rstrip("/")
    kp_dir, kp_gwb, kp_meta, kp_sha = a.kstar_dir.replace("\\", "/").rstrip("/"), a.gwb, a.meta, a.sha
    frozen = json.load(open(os.path.join(REPO, kp_dir, "_frozen_from.json"), encoding="utf-8"))
    if frozen["files"][kp_gwb]["sha256"] != kp_sha:
        raise SystemExit("凍結の記録の SHA-256 が違います。")
    if D.sha256(os.path.join(REPO, kp_dir, kp_gwb)) != kp_sha:
        raise SystemExit("K*′ の .gwb の SHA-256 が凍結の記録と違います。")
    # 包む側の固定値を差し替える（このプロセスの中だけ）
    D.KP_DIR_REL, D.KP_GWB, D.KP_META, D.KP_GWB_SHA, D.BUILD_REL = kp_dir, kp_gwb, kp_meta, kp_sha, build_rel
    D.SELF_REL = "Tools/GWWaveGen/ds29r01/ds29r01_bake_input.py"
    sys.argv = [sys.argv[0]]
    rc = D.main()
    # 記録の欄を仕上げ28 に書き直す（中身の値は変えない）
    build = os.path.join(REPO, build_rel)
    for p, schema in ((os.path.join(build, "ds29r01_bake_params.json"), None),
                      (os.path.join(build, "bake_input", "af28_bake_input_record.json"), None)):
        v = json.load(open(p, encoding="utf-8"))
        v["number"] = "仕上げ28（設計29修正01 の焼き込みを K*′ P28R2 で回し直す）"
        v["polish28_wrapper"] = {"command": "py -3.10 -B " + SELF_REL + " --build " + build_rel + ("" if kp_dir == KP_DIR_REL else " --kstar-dir %s --gwb %s --meta %s --sha %s" % (kp_dir, kp_gwb, kp_meta, kp_sha)),
                                 "self_sha256": D.sha256(os.path.join(REPO, SELF_REL)),
                                 "kstar_p28": kp_dir + "/" + kp_gwb, "kstar_p28_sha256": kp_sha,
                                 "note_ja": "ds29r01_bake_input.py の KP_DIR_REL・KP_GWB・KP_META・KP_GWB_SHA・BUILD_REL だけをこのプロセスの中で差し替えた。"}
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(v, f, ensure_ascii=False, indent=1)
            f.write("\n")
    print("PL28U_BAKE_INPUT_DONE", build_rel)
    return rc


if __name__ == "__main__":
    sys.exit(main())
