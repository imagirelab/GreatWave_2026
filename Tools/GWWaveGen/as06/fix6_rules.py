# -*- coding: utf-8 -*-
"""美術の見本06 の直しの回（段の行 R8 → R9）：asm6_rules.py（変えない）の写し。段の行の規則の道具 rows_rules.py を変えずに読み込み、置き場
（パイプラインの根・合わせた静止のメッシュ・描画・測り・関門・爪の並び・出力）だけを直しの回のもの（Build/Polish/sample06/fix）へ差し替えて main() を呼ぶ。
出力：Build/Polish/sample06/rules_check_rows.json（直す前の組み立ての版は、初めて書く前に rules_check_rows_before_fix.json へ写して残す）。
使い方：py -3.10 -B Tools/GWWaveGen/as06/fix6_rules.py [描画の名前（既定 R9）]
"""
import importlib
import json
import os
import shutil
import sys

REPO = "G:/Unity/GreatWave_2026_Fresh"
P = REPO + "/Unity/Build/Polish"
PF = P + "/sample06/fix"


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "R9"
    sys.path.insert(0, REPO + "/Tools/GWWaveGen/as06")
    out = P + "/sample06/rules_check_rows.json"
    bk = P + "/sample06/rules_check_rows_before_fix.json"
    if os.path.isfile(out) and not os.path.isfile(bk):
        shutil.copy2(out, bk)
    os.environ["R6_FINAL"] = PF + "/final"
    os.environ["R6_UNION"] = PF + "/mesh/union_AS06R9_f1.json"
    sys.argv = ["rows_rules.py", "R", tag]
    M = importlib.import_module("rows_rules")
    claws = os.environ.get("FIX6_CLAWS_ABS", PF + "/final/claws/ds33_claw_layout.json")
    A, R = M.A, M.R
    M.ASM5 = PF
    A.ASM = PF
    A.MEAS = PF + "/measure/rules_" + tag
    A.CLAWS04 = claws
    M.RENDER = PF + "/render/" + tag
    R.RENDER = M.RENDER
    R.GATES = PF + "/render/measure/gates_" + tag + "/sweep_gates.json"
    if os.path.isdir(PF + "/render/" + tag + "H"):
        M.HERO_ONLY_R = PF + "/render/" + tag + "H"
        R.HERO_ONLY = M.HERO_ONLY_R
    M.OUT = out
    print(json.dumps({"tag": tag, "render": M.RENDER, "gates": R.GATES, "claws": A.CLAWS04, "union": A.UNION, "n_hero": A.N_HERO, "out": out}, ensure_ascii=False), flush=True)
    M.main()
    d = json.load(open(out, encoding="utf-8"))
    bl = PF + "/render/" + tag + "/as06asm_boat_1.json"
    if os.path.isfile(bl):
        d["rules"]["K-boat"]["boat_move"] = json.load(open(bl, encoding="utf-8"))
    d["rules"]["K-boat"]["note_ja"] = ("Q34 で船を避ける制約を外した。直しの回でも、一艘目の船を原画のカメラを中心とする相似（倍率 0.6）で手前へ動かして描いた"
                                       "（名前の付いた美術の誘導。原画視点の船の画は画素まで同じで、ほかの視点では 0.6 倍。船と波の差し込み合いは造型の後で調整する）。判定には入れず記録する")
    ckp = PF + "/check/fix6_check.json"
    if os.path.isfile(ckp):
        ck = json.load(open(ckp, encoding="utf-8"))
        d["fix_checks"] = {"source": "Unity/Build/Polish/sample06/fix/check/fix6_check.json",
                           "interpenetration_hero_wave4": ck["interpenetration_hero_wave4"], "g1_stretch_same_tool": ck["g1_stretch"],
                           "painting_claw_visibility_unity": ck["painting_claw_visibility"], "boat_left_unity_ids": ck["boat_left"]}
    if os.path.isfile(bk):
        b = json.load(open(bk, encoding="utf-8"))
        d["before_fix"] = {"file": "Unity/Build/Polish/sample06/rules_check_rows_before_fix.json",
                           "summary": {k: v.get("verdict") if isinstance(v, dict) else v for k, v in b.get("rules", {}).items()}}
    d["fix6"] = {"tool": "Tools/GWWaveGen/as06/fix6_rules.py", "build_rules_tool": "Tools/GWWaveGen/as06/rows_rules.py",
                 "design": "Unity/Build/Polish/sample06/fix/design_R9.json", "render": "Unity/Build/Polish/sample06/fix/render/" + tag,
                 "measure": "Unity/Build/Polish/sample06/fix/measure", "claws_layout": claws.replace(REPO + "/", ""),
                 "note_ja": "直しの回：作りの規則の道具を変えずに読み込み、置き場だけを直しの回の物へ差し替えた。前の組み立ての版は rules_check_rows_before_fix.json"}
    json.dump(d, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
