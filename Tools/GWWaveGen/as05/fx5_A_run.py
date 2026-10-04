# -*- coding: utf-8 -*-
"""美術の見本05 の直しの回 fix1・形 A：やり方 A の道具（shapeA_*.py、変えない）を、置き場を Build/Polish/sample05/fix1/A へ替えて順に回す。
py -3.10 -B Tools/GWWaveGen/as05/fx5_A_run.py <設計.json> [try|full]

順：主役波の行（shapeA_hero、設計を差し替え）→ 材質の属性（pl29 → s01_param → s01a）→ 包み → 静止のメッシュ（fx5_A_mesh：白の区域の直し）
  → ③ の波 layer3（fx5_A_l3：尾の白を外す）→ 層の印（shapeA_labels、① の印の下限を −8.0 m）→ 爪の置き直し（shapeA_claws）→ 合わせた静止のメッシュ
  （主役波 ＋ wave4 fix1 ＋ layer3）。try では層の印・爪を省く。
shapeA_common の置き場の定数（OUT・CAND・ROWS05A・GWB05A・L3_JSON）を読み込みの直後に替えるだけで、道具の中身は変えない。
"""
import json
import os
import subprocess
import sys
import time

REPO = "G:/Unity/GreatWave_2026_Fresh"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shapeA_common as C  # noqa: E402

NEW = os.environ.get("FX5_A_ROOT", C.P + "/sample05/fix1/A")
C.OUT = NEW
C.CAND = NEW + "/hero/cand/" + C.NAME
C.ROWS05A = C.CAND + "_rows.npz"
C.GWB05A = C.CAND + ".gwb"
C.L3_JSON = NEW + "/l3/layer3.json"
W4 = C.WAVE4_F1


def sh(args, log):
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        r = subprocess.run(args, cwd=REPO, stdout=f, stderr=subprocess.STDOUT, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    print(os.path.basename(log), r.returncode, flush=True)
    if r.returncode:
        raise SystemExit("失敗：" + log)


def main():
    dpath = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "full"
    design = json.load(open(dpath, encoding="utf-8"))
    t0 = time.time()
    LG = NEW + "/logs"
    os.makedirs(LG, exist_ok=True)
    import shapeA_hero as H
    H.DESIGN = design
    sys.argv = ["shapeA_hero.py", dpath]
    H.main()
    py = ["py", "-3.10", "-B"]
    cand, N = C.CAND, C.NAME
    sh(py + ["Tools/GWWaveGen/pl29/pl29_hero_attr.py", "--gwb", cand + ".gwb", "--meta", cand + "_meta.json", "--out", NEW + "/attr/pl29", "--param", "arc"], LG + "/attr_pl29.log")
    sh(py + ["Tools/GWWaveGen/sample01/s01_param.py", "--gwb", cand + ".gwb", "--meta", cand + "_meta.json", "--attr", NEW + "/attr/pl29/pl29_hero_attr_f32.bin",
             "--out", NEW + "/attr/param", "--dir", "isoF"], LG + "/attr_param.log")
    sh(py + ["Tools/GWWaveGen/sample01/s01a_attr.py", "--attr", NEW + "/attr/pl29/pl29_hero_attr_f32.bin", "--param", NEW + "/attr/param/s01_param_f32.bin",
             "--out", NEW + "/attr/a", "--v2", "--gwb", cand + ".gwb"], LG + "/attr_a.log")
    sh(py + ["Tools/GWWaveGen/as02/as02_asm_pkg.py", "--src", "Unity/Build/Polish/32/white/hero_pkg", "--gwb", cand + ".gwb", "--rows", cand + "_rows.npz",
             "--meta", cand + "_meta.json", "--out", NEW + "/hero_pkg_AS05A"], LG + "/pkg.log")
    if mode == "full":
        sh(py + ["Tools/GWWaveGen/as02/back_measure.py", NEW + "/eval_AS05A_back_measure.json",
                 "AS02C=Unity/Build/Polish/sample02/fix01/back/final/cand/kstarAS02C_a45_rows.npz", "AS04=" + cand + "_rows.npz"], LG + "/back_measure.log")
    import fx5_A_mesh as MS
    sys.argv = ["fx5_A_mesh.py"]
    MS.main()
    import fx5_A_l3 as L3
    L3.main()
    if mode == "full":
        import shapeA_labels as LB
        LB.C12 = -8.0
        sys.argv = ["shapeA_labels.py"]
        LB.main()
        import shapeA_claws as CL
        CL.main()
    os.makedirs(NEW + "/mesh", exist_ok=True)
    sh(py + ["Tools/GWWaveGen/as04/w4_merge.py", NEW + "/mesh/hero_smooth_as05a.json", W4, NEW + "/mesh/_hero_w4.json"], LG + "/merge1.log")
    sh(py + ["Tools/GWWaveGen/as04/w4_merge.py", NEW + "/mesh/_hero_w4.json", C.L3_JSON, NEW + "/mesh/union_AS05A.json"], LG + "/merge2.log")
    print("FX5_A_RUN_DONE", NEW, round(time.time() - t0, 1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
