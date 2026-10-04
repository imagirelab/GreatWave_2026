# -*- coding: utf-8 -*-
"""美術の見本03 の作り B2：実行の記録（コマンド・道具の版・入力と出力の SHA-256）を surface/B2_run.json に書く。
使い方：py -3.10 -B Tools/GWWaveGen/as03/surf_record.py <版 v11> <メッシュの名前>"""
import glob
import os
import platform
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import surf_common as S  # noqa: E402

TAG = sys.argv[1] if len(sys.argv) > 1 else "v13"
MN = sys.argv[2] if len(sys.argv) > 2 else "hero_relief_b1v2c"


def shas(paths):
    return {p.replace("\\", "/"): S.sha(p) for p in paths if os.path.isfile(p)}


A = S.REPO + "/Unity/Assets/GreatWave/ArtSample03"
T = S.REPO + "/Tools/GWWaveGen/as03"
rec = {
    "schema": "GreatWave.AS03.B2_run/1",
    "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "tools": {"python": platform.python_version(), "numpy": np.__version__, "unity": "6000.4.3f1（E:/6000.4.3f1/Editor/Unity.exe、batchmode、unity.lock で 1 つずつ）"},
    "commands_ja": [
        "py -3.10 -B Tools/GWWaveGen/as03/surf_bake.py                      # AO と固定の光の見通しを焼く（主役波の格子、約 25 秒）",
        "py -3.10 -B Tools/GWWaveGen/as03/surf_relief.py --name %s --white-mask Unity/Build/Polish/sample03/shared/white_mask_f32.bin --white-band Unity/Build/Polish/sample03/shared/white_mask_band_f32.bin --bake Unity/Build/Polish/sample03/surface/bake/hero_bake.npz" % MN,
        "py -3.10 -B Tools/GWWaveGen/as03/surf_kp_attr.py                   # keypose の道の属性（C.w に白の印）",
        "bash Tools/GWWaveGen/as03/surf_render.sh B2_%s_sculpt views,crest,ids sculpt %s" % (TAG, MN),
        "bash Tools/GWWaveGen/as03/surf_render.sh B2_%s_flat views,crest,ids flat %s" % (TAG, MN),
        "bash Tools/GWWaveGen/as03/surf_render_tests.sh %s %s            # keypose の道・爪・B1 の冠の確かめ" % (MN, TAG),
        "py -3.10 -B Tools/GWWaveGen/as03/surf_measure.py Unity/Build/Polish/sample03/surface/render/B2_%s_<flat|sculpt> Unity/Build/Polish/sample03/surface/measure/B2_%s_<flat|sculpt>_measure.json" % (TAG, TAG),
        "py -3.10 -B Tools/GWWaveGen/as03/surf_silhouette.py Unity/Build/Polish/sample03/surface/render/B2_%s_sculpt" % TAG,
        "py -3.10 -B Tools/GWWaveGen/as03/surf_sheets.py %s; py -3.10 -B Tools/GWWaveGen/as03/surf_numbers.py %s %s; py -3.10 -B Tools/GWWaveGen/as03/surf_rules.py %s %s" % (TAG, MN, TAG, TAG, MN),
        "py -3.10 -B Tools/GWWaveGen/as03/surf_user_compare.py %s           # 利用者だけの比べ（写真を含む、user_only）" % TAG,
        "bash Tools/GWWaveGen/as03/surf_render.sh B2_%s_flat_eval full,t28 flat %s; RB=…/surface/render LG=…/surface/logs BEFORE=…/sample02/fix01/assemble/render/AS02C_A bash Tools/GWWaveGen/as02/as02_asm_eval.sh B2_%s_flat_eval   # 原画視点の評価器 23 と関門" % (TAG, MN, TAG),
    ],
    "inputs": shas([S.HERO_PKG + "/ds27_keypose.json", S.HERO_PKG + "/ds27_pos_rgba16.bin", S.HERO_PKG + "/ds27_twhite_r32f.bin", S.GWB, S.ATTR, S.SPEC,
                    S.SHARED + "/white_mask_f32.bin", S.SHARED + "/white_mask_band_f32.bin", S.SHARED + "/white_mask.json"]),
    "unity_assets": shas(sorted(glob.glob(A + "/Shaders/*.shader") + glob.glob(A + "/Shaders/*.cginc") + glob.glob(A + "/Scripts/*.cs") + [A + "/Editor/AS03SurfRender.cs"])),
    "tools_files": shas(sorted(glob.glob(T + "/surf_*"))),
    "outputs": shas(sorted(glob.glob(S.OUT + "/mesh/%s*" % MN) + glob.glob(S.OUT + "/bake/*") + glob.glob(S.OUT + "/attr/*") + glob.glob(S.OUT + "/sheets/*.png")
                           + glob.glob(S.OUT + "/measure/*.json") + glob.glob(S.OUT + "/render/B2_%s_*/as03surf_render_report.json" % TAG)
                           + glob.glob(S.OUT + "/render/measure/gates_B2_%s_flat_eval/*.json" % TAG))),
    "user_only": shas(glob.glob(S.OUT + "/user_only/*")),
    "noteJa": "PC オフスクリーン描画（HMD 実機ではない）。原画カメラの投影は使わない。参照モデルの OBJ は読んでいない。彫刻の写真は、調べ S3 が残した一時の写し 5 枚を利用者だけの比べの図で読んだだけ（新しい写しなし）。git の add・commit・push はしていない。",
}
S.jdump(S.OUT + "/B2_run.json", rec)
print(len(rec["outputs"]), "outputs")
