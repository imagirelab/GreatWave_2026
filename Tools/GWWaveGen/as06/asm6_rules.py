# -*- coding: utf-8 -*-
"""美術の見本06 の組み立て（Q34）：二つの作り（段の行 R8・塊 LB2）の測る規則を、組み立ての描画（Build/Polish/sample06/assemble/render/<名前>）と
測り（sample06/assemble/measure）で、同じ決まりで出す。それぞれの作りの規則の道具（rows_rules.py・lobes_rules.py、どちらも見本05 の fx5_rules.py の写し）を
変えずに読み込み、置き場の名前（描画・測り・関門・爪の並び・出力）だけを差し替えて main() を呼ぶ。
使い方：py -3.10 -B Tools/GWWaveGen/as06/asm6_rules.py rows <描画の名前> | lobes <描画の名前>
出力：Build/Polish/sample06/rules_check_rows.json・rules_check_lobes.json
"""
import importlib
import json
import os
import sys

REPO = "G:/Unity/GreatWave_2026_Fresh"
P = REPO + "/Unity/Build/Polish"
PA = P + "/sample06/assemble"


def main():
    kind, tag = sys.argv[1], sys.argv[2]
    sys.path.insert(0, REPO + "/Tools/GWWaveGen/as06")
    if kind == "rows":
        os.environ["R6_FINAL"] = P + "/sample06/rows/final_d"
        os.environ["R6_UNION"] = P + "/sample06/rows/mesh/union_AS06R_d_f1.json"
        sys.argv = ["rows_rules.py", "R", tag]
        M = importlib.import_module("rows_rules")
        claws = os.environ.get("ASM6_CLAWS", P + "/sample06/rows/final_d/claws/ds33_claw_layout.json")
        out = P + "/sample06/rules_check_rows.json"
    elif kind == "lobes":
        os.environ["AS06L_ASM"] = "assemble2"
        os.environ["AS06L_FIN"] = "final2"
        sys.argv = ["lobes_rules.py", tag]
        M = importlib.import_module("lobes_rules")
        claws = os.environ.get("ASM6_CLAWS", PA + "/lobes/claws/ds33_claw_layout.json")
        out = P + "/sample06/rules_check_lobes.json"
    else:
        raise SystemExit("rows か lobes")
    A, R = M.A, M.R
    M.ASM5 = PA
    A.ASM = PA
    A.MEAS = PA + "/measure/rules_" + tag
    A.CLAWS04 = claws
    M.RENDER = PA + "/render/" + tag
    R.RENDER = M.RENDER
    R.GATES = PA + "/render/measure/gates_" + tag + "/sweep_gates.json"
    if os.path.isdir(PA + "/render/" + tag + "H"):
        M.HERO_ONLY_R = PA + "/render/" + tag + "H"
        R.HERO_ONLY = M.HERO_ONLY_R
    M.OUT = out
    print(json.dumps({"kind": kind, "tag": tag, "render": M.RENDER, "gates": R.GATES, "claws": A.CLAWS04, "union": A.UNION, "out": out}, ensure_ascii=False), flush=True)
    M.main()
    # 組み立ての記録を足す（どの道具をどう差し替えたか）
    d = json.load(open(out, encoding="utf-8"))
    # K-boat：組み立ての描画の船の記録（as06asm_boat_1.json）を入れ、説明を組み立ての決まりに直す（判定の式は作りの道具のまま）
    bl = PA + "/render/" + tag + "/as06asm_boat_1.json"
    if os.path.isfile(bl):
        d["rules"]["K-boat"]["boat_move"] = json.load(open(bl, encoding="utf-8"))
    d["rules"]["K-boat"]["note_ja"] = ("Q34 で船を避ける制約を外した。組み立てでは二つの作りとも、一艘目の船を原画のカメラを中心とする相似（倍率 0.6）で手前へ動かして描いた"
                                       "（名前の付いた美術の誘導。原画視点の船の画は画素まで同じで、ほかの視点では 0.6 倍。船と波の差し込み合いは造型の後で調整する）。"
                                       "判定には入れず記録する")
    # 組み立ての独立の確かめ（asm6_check.py）：主役波と wave4 の食い込み・帯の伸びの場所・原画視点の爪の隠れ・船の画素
    ckp = PA + "/check/asm6_check.json"
    if os.path.isfile(ckp):
        ck = json.load(open(ckp, encoding="utf-8"))
        bn = {"rows": "R8", "lobes": "LB2"}[kind]
        d["assemble_checks"] = {
            "source": "Unity/Build/Polish/sample06/assemble/check/asm6_check.json",
            "interpenetration_hero_wave4": {"B10": ck["interpenetration_hero_wave4"]["B10"], bn: ck["interpenetration_hero_wave4"][bn]},
            "g1_stretch_same_tool": {"B10": ck["g1_stretch"]["B10"], bn: ck["g1_stretch"][bn]},
            "painting_claw_visibility_unity": ck["painting_claw_visibility"],
            "boat_left_unity_ids": ck["boat_left"]}
    d["assemble_asm6"] = {"tool": "Tools/GWWaveGen/as06/asm6_rules.py", "build_rules_tool": "Tools/GWWaveGen/as06/%s_rules.py" % kind,
                          "render": "Unity/Build/Polish/sample06/assemble/render/" + tag, "measure": "Unity/Build/Polish/sample06/assemble/measure",
                          "claws_layout": claws.replace(REPO + "/", ""),
                          "note_ja": "作りの規則の道具を変えずに読み込み、描画・測り・関門・爪の並び・出力の置き場だけを組み立ての物へ差し替えた"}
    json.dump(d, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
