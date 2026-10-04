# -*- coding: utf-8 -*-
"""美術の見本04 の形づくり：主役波 K*′ AS04 を、見本02・03 の K*′ AS02C の t* から作る（Q32・要求書 S8〜S11）。
py -3.10 -B Tools/GWWaveGen/as04/shape_build.py <out_prefix> <design.json>

順（最後の版の設計は Unity/Build/Polish/sample04/shape/final/design_AS04.json）：
  1. op_shorten（S8・S11）：c −13〜−3 m の唇を短くし（c −10.6〜−6 m で 13.5 m、頂の前に厚み 1.2 m の短い鼻）、内の面の弧を頂のすぐ下まで続ける。
     原画視点で、利用者の黄色の線の所は唇の外の面ではなく巻きの内の面になる。① 主の唇（c > −3 m）と ② の房（c < −11 m）が、間の凹の面で分かれる。
  2. op_left（S9・S10）：左の白を原画の楔の下の縁まで下げ（c −17.2 で 1.5 m → c −12.6 で 0）、c −17.8 → −29 m で頂を海へ下ろす（余弦の肩）。
     下げの小さい行は頂の側だけ（列 ≤ 115、唇 ≥ 150 は下げない：船・手前の海の前に出さない。唇より頂を 0.3 m 高く保つ：鰭を作らない）、
     下げの大きい行は断面を背の足のまわりに縮める（前へ出さない）。潰れた行は海の 0.25 m 下の平らな板。
  3. op_lobe3・op_shift3（③ を前へ出す試し）は最後の版では使わない（原画視点で船・手前の海の前に出るため）。
  境の輪（行 0・239、列 0・399）は最後に土台へ戻す。
行の c・格子 400 × 240・目印の列・境の輪（列 0・行 0・239）は変えない。参照モデル・写真は読まない（F13-1）。原画のカメラは測りにだけ使う。
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shape_common as S  # noqa: E402
import shape_ops as O  # noqa: E402


def build(design):
    c, A, Y = S.load_rows()
    log = {}
    if design.get("shorten"):
        A, Y, w, info = O.op_shorten(c, A, Y, design["shorten"])
        log["shorten"] = info
    stage1 = (A.copy(), Y.copy())
    if design.get("left"):
        plan = json.load(open(S.PLAN, encoding="utf-8"))
        pc = np.array(plan["H_profile"]["c"], float); ph = np.array(plan["H_profile"]["H_after_b"], float)
        Ht = np.interp(c, pc, ph)
        L = design["left"]
        if L.get("tail"):
            # 尾の下ろし方を丸く：c_start（頂 H_start）から c_end で海へ、余弦の肩（調べ S の H_after_b の直線の下ろしより、端の壁が立たない）
            t0, t1 = L["tail"]["c_start"], L["tail"]["c_end"]
            Hs = float(np.interp(t0, pc, ph))
            u = np.clip((c - t1) / (t0 - t1), 0, 1)
            Htail = Hs * (0.5 - 0.5 * np.cos(np.pi * u))
            Ht = np.where(c < t0, Htail, Ht)
        # 楔の下の縁への下げ（c −17.2〜−12.6）は調べ S の lower_by（今の深さ）で上書き：H_after_b と同じ値の所
        Hn = Y[:, S.J_B:S.J_TIP + 1].max(1)
        if L.get("drop_table"):
            dc, dd = np.array(L["drop_table"], float).T
            m = (c >= dc.min()) & (c <= dc.max())
            Ht = np.where(m, np.minimum(Ht, Hn - np.interp(c, dc, dd)), Ht)
        Ht = np.where(c > L.get("c_keep", -12.6), np.maximum(Ht, Hn), Ht)
        A, Y, info = O.op_left(c, A, Y, Ht, L)
        log["left"] = info
    if design.get("lobe3"):
        A, Y, w3 = O.op_lobe3(c, A, Y, design["lobe3"])
        log["lobe3_w"] = [round(float(x), 3) for x in w3]
    if design.get("shift3"):
        A, Y, w3 = O.op_shift3(c, A, Y, design["shift3"])
        log["shift3_w"] = [round(float(x), 3) for x in w3]
    # 境の輪（行 0・行 239・列 0・列 399）は土台のまま（海とのつなぎ目。kh_common の約束）
    c0_, A0_, Y0_ = S.load_rows()
    for AA, A0x in ((A, A0_), (Y, Y0_)):
        AA[0] = A0x[0]; AA[-1] = A0x[-1]; AA[:, 0] = A0x[:, 0]; AA[:, -1] = A0x[:, -1]
    log["_stage1"] = stage1
    return c, A, Y, log


def main():
    pre, dpath = sys.argv[1], sys.argv[2]
    design = json.load(open(dpath, encoding="utf-8"))
    t0 = time.time()
    c, A, Y, log = build(design)
    os.makedirs(os.path.dirname(pre), exist_ok=True)
    A1, Y1 = log.pop("_stage1")
    np.savez(pre + "_stage1_rows.npz", c=c, A=A1, Y=Y1)
    if design.get("write_candidate"):
        prov = {"route": "美術の見本04 の形づくり Tools/GWWaveGen/as04/shape_build.py（numpy、行の断面の作り直し）",
                "base": "K*′ AS02C (%s, sha256 %s)" % (S.BASE_ROWS.replace(S.REPO + "/", ""), S.sha(S.BASE_ROWS)),
                "design": design, "reference_model_read_by_generator": False, "photos_read_by_generator": False}
        S.K.write_candidate(pre, c, A, Y, prov)
    else:
        np.savez(pre + "_rows.npz", c=c, A=A, Y=Y)
    S.jdump(pre + "_build_log.json", {"design": design, "log": log, "seconds": round(time.time() - t0, 1)})
    print("SHAPE_BUILD_DONE", pre, round(time.time() - t0, 1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
