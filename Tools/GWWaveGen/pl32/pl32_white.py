# -*- coding: utf-8 -*-
"""仕上げ32 白の部：仕上げ31 の白の出現（T_white）から爪の根元の誘導 pl31_white_claw_pin を外し、爪の成長の時刻を白の順へ合わせ直す前提を作る。

仕上げ31 §8 の引き継ぎ：「爪の成長の時刻（136「根元が白くなると伸び始める」）を、この順へ合わせ直す。合わせ直したら pl31_white_claw_pin は外せる」。
この群では爪を K*′ P28R2rec のシートへ結び付け直し、爪の成長の始まりを根元の T_white（この道具の出力）にするので、根元を先に白くする誘導は要らない。

ただし pl31_white_claw_pin は、唇の先の頂点（仕上げ31 の飛沫の放出点の一部）も早く白くしていた。外すと、仕上げ31 の飛沫 2,495 粒のうち 62 粒が
白くなる前の頂点から出る（仕上げ31 の計画の 2 行「放出点は放出の時に白」を割る）。そこで、名前の付いた美術の誘導 pl32_white_spray_pin で、
放出点の頂点だけを、その頂点から出る最も早い粒の放出の半コマ前までに早める（早める向きだけ。頂点の数は数えて記録する）。

やり方：仕上げ31 の道具 pl31_white.py の main をそのまま使い、その中の claw_pins を pl32_white_spray_pin に差し替える（--claw-pin > 0 で呼ばれる）。
白の順（pl31_white_order patch）・pl31_white_rate_cap・102/135/177 の測り・発生の表は仕上げ31 と同じ式。136 の測り（claw_lag）は、
--claws に爪の並びのフォルダー（ds33 の形式）を渡すと、その爪で数える（既定は仕上げ32 の爪 Unity/Build/Polish/32/claws。無ければ設計33）。

出力（Git 対象外）：Unity/Build/Polish/32/white/（pl31_white.py と同じ名前のファイル＋ hero_pkg/）と pl32_white_numpy.json（名前を直した要約）。
"""
import argparse
import ast
import json
import os
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl31")
import pl31_white as P31  # noqa: E402

SPRAY_TABLE = REPO + "/Unity/Build/Polish/31/spray/pl31_spray_table.json"
OUT = REPO + "/Unity/Build/Polish/32/white"
CLAWS32 = REPO + "/Unity/Build/Polish/32/claws"


def load_emitters(path):
    """仕上げ31 の飛沫の表から、放出点の頂点（行 × 列の通し番号）ごとの最も早い放出の τ。"""
    t = json.load(open(path, encoding="utf-8"))["particles"]
    em = {}
    for p in t:
        e = p.get("emitter")
        if isinstance(e, str):
            try:
                e = ast.literal_eval(e)
            except Exception:
                e = None
        if not e:
            continue
        v = int(e["row"]) * 400 + int(e["col"])
        te = float(p["tau_e"])
        em[v] = min(em.get(v, 1e9), te)
    return em


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--claws", default=None, help="136 を数える爪の並び（ds33_claw_rig.json・ds33_claw_layout.json のあるフォルダー）")
    ap.add_argument("--spray-table", default=SPRAY_TABLE)
    a, rest = ap.parse_known_args()
    cd = a.claws or (CLAWS32 if os.path.exists(CLAWS32 + "/ds33_claw_layout.json") else P31.CLAW_DIR)
    P31.CLAW_DIR = cd
    em = load_emitters(a.spray_table)
    info = {}

    def spray_pin(TWv, A, roots, fin, body, wt, wtau, r_pin, v_pin, cone_m):
        """pl32_white_spray_pin：放出点の頂点の T_white を、その頂点から出る最も早い粒の放出の半コマ前までに早める（早める向きだけ）。"""
        TWp = TWv.copy()
        moved, late = 0, []
        for v, te in em.items():
            t_e = float(P31.W.t_of_tau(te, wt, wtau))
            tau_pin = float(P31.W.tau_at(t_e - 0.5 / P31.FPS, wt, wtau))
            if TWp[v] > tau_pin:
                late.append(dict(vertex=int(v), row=int(v // 400), col=int(v % 400), tau_e=te, twhite_before=float(TWp[v]), twhite_after=tau_pin))
                TWp[v] = tau_pin
                moved += 1
        info.update(name="pl32_white_spray_pin", emitter_vertices=len(em), vertices_moved=moved,
                    tau_advance_max_s=float(max([x["twhite_before"] - x["twhite_after"] for x in late], default=0.0)),
                    moved_list=late,
                    rule_ja="仕上げ31 の飛沫の放出点の頂点（%d）のうち、T_white が最も早い粒の放出の半コマ前より遅い頂点だけを、その時刻まで早める（早める向きだけ）。"
                            "爪の根元の誘導 pl31_white_claw_pin は外した" % len(em))
        return TWp, dict(info)

    P31.claw_pins = spray_pin
    sys.argv = [sys.argv[0], "--out", a.out, "--claw-pin", "1"] + rest
    P31.main()
    # 名前を直した要約（pl31_white.py の出力の pl31_white_claw_pin の欄には、この群の pl32_white_spray_pin が入っている）
    d = json.load(open(os.path.join(a.out, "pl31_white_numpy.json"), encoding="utf-8"))
    d["schema"] = "GreatWave.Polish32.white_numpy/1"
    d["pl32_white_spray_pin"] = d.pop("pl31_white_claw_pin")
    d["pl31_white_claw_pin"] = None
    d["note_ja"] = ("仕上げ32：pl31_white.py の main を使い、爪の根元の誘導 pl31_white_claw_pin を外して、飛沫の放出点の誘導 pl32_white_spray_pin に差し替えた。"
                    "claws_136 は %s の爪で数えた" % cd.replace(REPO + "/", ""))
    d["claws_136_source_dir"] = cd.replace(REPO + "/", "")
    d["code_sha256"]["pl32_white.py"] = P31.sha(os.path.abspath(__file__))
    json.dump(d, open(os.path.join(a.out, "pl32_white_numpy.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    meta_p = os.path.join(a.out, "hero_pkg", "ds27_keypose.json")
    meta = json.load(open(meta_p, encoding="utf-8"))
    meta["number"] = "仕上げ32（G_p28rec の T_white に pl31_white_order（patch）・pl32_white_spray_pin・pl31_white_rate_cap を掛けた写し。pl31_white_claw_pin は外した）"
    json.dump(meta, open(meta_p, "w", encoding="utf-8"), ensure_ascii=False)
    print("pl32_white_spray_pin", {k: v for k, v in info.items() if k != "moved_list"})


if __name__ == "__main__":
    main()
