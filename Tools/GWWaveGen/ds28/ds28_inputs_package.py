# -*- coding: utf-8 -*-
"""設計28：入力条件の変更の 1 本を、設計27 の再生器（Unity/Assets/GreatWave/Design27、変えない）が読むパッケージに書く（任意の側面の静止画用）。

設計27 の ds27_generate.Builder・export_package（読むだけ）を使う。ただし節点の適応の検査は 1 区間 1 点・1 回だけにした簡易版
（側面の静止画を見るため。設計27 の 2.5 mm の規則は確かめていない。記録に書く）。
使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/ds28/ds28_inputs_package.py --name in_d120_l195
出力（Git 対象外）：Unity/Build/Design/28/inputs/pkg/<名前>/（ds27_keypose.json・ds27_pos_rgba16.bin・ds27_twhite_r32f.bin）
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "ds27"))
import ds27_generate as GEN  # noqa: E402
from ds28_inputs_model import InputGen, check_frozen  # noqa: E402
from ds28_inputs_run import run_list  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    a = ap.parse_args()
    check_frozen()
    it = {r["name"]: r for r in run_list()}[a.name]
    g = InputGen(it["cfg"])
    g.P["knots"]["adaptive_check_per_interval"] = 1
    g.P["knots"]["adaptive_max_rounds"] = 1
    out = os.path.join(REPO, "Unity", "Build", "Design", "28", "inputs", "pkg", a.name)
    t0 = time.time()
    B = GEN.Builder(g, print)
    B.build_knots()
    rec, _ = GEN.export_package(g, B, out, print)
    print("[ds28_inputs_package] %s：%d 層、%.0f s → %s" % (a.name, rec["layers"], time.time() - t0, out))


if __name__ == "__main__":
    main()
