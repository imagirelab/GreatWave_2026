# -*- coding: utf-8 -*-
"""仕上げ27：設計26 の値の JSON（Docs/Evidence/Design/26/ds26_conditions.json。初回提出の時点の値で、run.json に SHA-256 を記録したので
書き換えない）から、Q11（2026-09-27）の決定を入れた写し Tools/GWWaveGen/ds26_conditions.json を作る。

入れること（設計26 の記録の §0・第10節・第10.1節と、Design_26_ja.md 25 行目の「写すときに入れる」3 つ）：
  1. status_ja：「利用者未回答」→ Q11 の回答（D30 は既定の 60°、D31 は既定の時間曲線、D37 は①だけ）と、残りの既定値の状態。
  2. time_warp の再開（restart_ramp_s）を外す：t* の後は作らない（Q11）。保持 2 s の後は設計47（余韻へのつなぎ）が決める。
  3. numerical.keypose_hz の breaking_and_collapse を jet_to_tstar に替える（崩壊は作らない。値 30 Hz は変えない）。
数値は変えない（AGENTS.md：翻訳のために数値を変えない）。外した値は q11_applied に元の値のまま残す。
元の JSON の SHA-256 を照合する。出力は決定的（同じ入力で同じバイト）。

使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/pl27/pl27_ds26_conditions.py [--check]
"""
import argparse
import copy
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(REPO, "Docs", "Evidence", "Design", "26", "ds26_conditions.json")
SRC_SHA = "ec8ae040da4a10a371815b207bee7ad5e8c44af6d56b0fb35989aeee8fb6c072"
DST = os.path.join(REPO, "Tools", "GWWaveGen", "ds26_conditions.json")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def build():
    if sha(SRC) != SRC_SHA:
        raise SystemExit("[pl27] 元の ds26_conditions.json の SHA-256 が記録と違います")
    src = json.load(open(SRC, encoding="utf-8"))
    d = copy.deepcopy(src)
    changes = []
    d["schema"] = "GreatWave.DS26.conditions/2"
    changes.append(dict(key="schema", before=src["schema"], after=d["schema"], why_ja="Q11 を入れた写し（キーを 3 つ外し・1 つ改名した）"))
    d["status_ja"] = ("設計26 の値の確定の写し（仕上げ27、2026-09-30）。元は Docs/Evidence/Design/26/ds26_conditions.json（初回提出の時点の値。"
                      "SHA-256 %s。書き換えない）。Q11（2026-09-27）の回答を入れた：D30 は既定の 60°（形成の過程は利用者の写真＝論文 Fig. 4 a〜d に従う）、"
                      "D31 は既定の時間曲線（代案も描いて比べる）、D37 は①だけ回答（解算は力の場で上向きの力を与えた波）。作る範囲は形成から t* まで"
                      "（τ ≤ 0）で、t* の後の崩壊と再開は作らない。D32・D33・D35 と D37 の②（1 単位 = 1 m）は既定値・利用者未回答、D36 は既定値・利用者未確認"
                      "（解算の数値をリポジトリへ入れる形は Q12 で確認済み）。写真の錐状の副峰を足さないことは Q12 で確認済み。回答の読み方は進行役の解釈。"
                      "採用の動きは設計28修正01 の F_final（Tools/GWWaveGen/ds28r01f/）で、その値は ds28r01f_params.json にある。この写しは設計26 の条件の記録で、"
                      "設計27〜28修正01 の生成器と関門の検査器は、再現の SHA-256 を変えないために今も元の Evidence の JSON を照合して読む。") % SRC_SHA
    changes.append(dict(key="status_ja", before=src["status_ja"], after="（上の文）", why_ja="利用者未回答 → Q11 の回答"))
    d["scope_ja"] = "形成から原画の瞬間 t* まで（物理の時刻 τ ≤ 0、体験の時刻 t ≤ 12.0 s、t* で 2 s 保持）。t* の後の崩壊・再開は作らない（Q11「不考虑崩塌」）。保持の後の余韻へのつなぎは設計47。"
    changes.append(dict(key="scope_ja", before=None, after=d["scope_ja"], why_ja="Q11 の作る範囲を足した"))
    d["physical_input"]["crossing_angle_deg"]["decided_ja"] = "Q11 で既定の 60° に決まった（D30。形成の過程は利用者の写真に従う。進行役の解釈）"
    changes.append(dict(key="physical_input.crossing_angle_deg.decided_ja", before=None, after=d["physical_input"]["crossing_angle_deg"]["decided_ja"], why_ja="D30 の回答"))
    for k in ("default", "alternative"):
        before = d["time_warp"][k].pop("restart_ramp_s")
        changes.append(dict(key="time_warp.%s.restart_ramp_s" % k, before=before, after="（外した）",
                            why_ja="t* の後の再開は作らない（Q11）。保持 hold_s の後は設計47 が決める"))
    d["time_warp"]["default"]["decided_ja"] = "Q11 で既定（slowmo_from_apex）に決まった（D31「按你说的做」。既定の採用と読むのは進行役の解釈）"
    d["time_warp"]["alternative"]["note_ja"] = "代案。設計27 で既定と並べて描いた（D31）"
    changes.append(dict(key="time_warp.default.decided_ja", before=None, after=d["time_warp"]["default"]["decided_ja"], why_ja="D31 の回答"))
    kh = d["numerical"]["keypose_hz"]
    v = kh.pop("breaking_and_collapse")
    kh["jet_to_tstar"] = v
    kh["note_ja"] = "崩壊は作らない（Q11）ので、30 Hz は噴流の始まりから t* までの区間（設計27 の keypose は τ −3.0〜0 s を 1/30 s おき）"
    changes.append(dict(key="numerical.keypose_hz.breaking_and_collapse", before=v, after="jet_to_tstar = %s" % v, why_ja="崩壊は作らない（Q11）。値は同じ"))
    d["q11_applied"] = dict(source=dict(path="Docs/Evidence/Design/26/ds26_conditions.json", sha256=SRC_SHA),
                            made_by="Tools/GWWaveGen/pl27/pl27_ds26_conditions.py（仕上げ27）",
                            decisions_ja=["D30：(a) 60°（Q11）", "D31：(a) 既定の時間曲線（Q11）", "D37：① 力の場で押し上げた（Q11）。② は未回答で 1 単位 = 1 m",
                                          "作る範囲：形成から t* まで。D22 の崩壊 4 s と D34 は範囲外（Q11）", "写真の錐状の副峰は足さない（Q12 で確認）"],
                            changes=changes, numbers_changed=False)
    return d


def dump(d):
    return (json.dumps(d, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="書かずに、今のファイルと同じバイトかだけ確かめる")
    a = ap.parse_args()
    b = dump(build())
    if a.check:
        same = os.path.isfile(DST) and open(DST, "rb").read() == b
        print("同じ" if same else "違う")
        sys.exit(0 if same else 1)
    with open(DST, "wb") as f:
        f.write(b)
    print("書いた：Tools/GWWaveGen/ds26_conditions.json（SHA-256 %s）" % hashlib.sha256(b).hexdigest())


if __name__ == "__main__":
    main()
