# -*- coding: utf-8 -*-
"""美術の見本01 爪の部：爪の輪の地を藍にする提案（as01_backing。numpy。見本の描画のためだけの写し）。

知られた原因 (3)：主役波の頂と唇の前が白のままなので、白い爪の輪が白の上で読めない。原画では爪の間は藍、彫刻では背と頂の上は白。
ここでは、見本の判定のために、t* の主役波の T_white（τ ≥ T_white で白）を、爪が垂れる下の 2 つの帯（行 R0〜R1。c_tip は claws_rim の唇の先の列）で
「t* まで白にならない」（1e9）にした主役波のパッケージの写しを作る：
  帯 1：外の巻きの面の爪の輪 R1 の根元の少し先から唇の先の少し手前まで（列 c_tip − BAND1[0] 〜 c_tip − BAND1[1]、行 BAND1_ROWS。v11）。
  帯 2：唇の下（列 c_tip + BAND2[0] 〜 c_tip + BAND2[1]）。
背と頂の上（列 < c_tip − BAND1[0]）と唇の先の細い帯（L0 の根元）は白のまま＝指が白い泡の塊の縁から出て、藍の上へ垂れる（彫刻と原画の両方の読み）。
位置の表（ds27_pos_*.bin）は元のファイルへの固いリンク（書き換えない）。T_white と JSON（twhite_sha256）だけ新しい。
これは面の色の部（見本の模様 A・B）への受け渡しの提案で、主役波の材質の決定ではない。出力（Git 対象外）：
  Unity/Build/Polish/sample01/claws/hero_backing/（パッケージ）と as01_backing_vertex.npy（行 × 列の bool、帯＝True）。
使い方：py -3.10 -B Tools/GWWaveGen/as01/claws_backing.py
"""
import json
import os
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as01")
import claws_common as CC  # noqa: E402
import claws_rim as CR  # noqa: E402

BAND1 = (46, 6)          # v11：爪の輪 R1（c_tip − 50）の下の藍の舌の帯。行 BAND1_ROWS だけ（原画の舌の所。唇の鼻の上は原画どおり白の泡のまま）
BAND1_ROWS = (92, 146)
BAND2 = (3, 40)          # 唇の下（巻きの中の藍）
NEVER = 1.0e9


def main():
    out = CC.OUTD + "/hero_backing"
    os.makedirs(out, exist_ok=True)
    src = CC.HERO
    k = json.load(open(os.path.join(src, "ds27_keypose.json"), encoding="utf-8"))
    R, C = int(k["rows"]), int(k["cols"])
    tw = np.fromfile(os.path.join(src, k["twhite_file"]), dtype="<f4").reshape(R, C)
    hero = CC.Hero(CC.load_hero())
    ct = CR.c_tip_rows(hero)
    m = np.zeros((R, C), bool)
    cc = np.arange(C)
    for r in range(CR.RIM["R0"] - 4, CR.RIM["R1"] + 5):
        b1 = (cc >= ct[r] - BAND1[0]) & (cc <= ct[r] - BAND1[1]) if BAND1_ROWS[0] <= r <= BAND1_ROWS[1] else np.zeros(C, bool)
        m[r] = b1 | ((cc >= ct[r] + BAND2[0]) & (cc <= ct[r] + BAND2[1]))
    tw2 = tw.copy()
    tw2[m] = NEVER
    for f in (k["pos_file"], k["pos_lo_file"]):
        d = os.path.join(out, f)
        if not os.path.exists(d):
            os.link(os.path.join(src, f), d)
    tw2.astype("<f4").tofile(os.path.join(out, k["twhite_file"]))
    k2 = dict(k)
    k2["twhite_sha256"] = CC.sha(os.path.join(out, k["twhite_file"]))
    k2["number"] = "美術の見本01 爪の部の提案 as01_backing（" + k["number"] + " の T_white の爪の帯を t* まで白にしない写し）"
    json.dump(k2, open(os.path.join(out, "ds27_keypose.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    np.save(os.path.join(CC.OUTD, "as01_backing_vertex.npy"), m)
    print("AS01_BACKING_DONE vertices", int(m.sum()), "was_white", int((tw[m] < 0.0).sum()), "out", out)


if __name__ == "__main__":
    main()
