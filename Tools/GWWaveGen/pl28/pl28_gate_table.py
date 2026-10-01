# -*- coding: utf-8 -*-
"""仕上げ28：関門 P1〜P19（設計27・28 の検査器、ds28r01f_pipeline の 5 組）と P13 の内訳を、F_final（今の体験）と仕上げ28 の版で並べる。
検査の出力（gates/*.json）だけを読む。P20 は生成の記録（p20_f_layers.json・p20_*.json・p20_e/*.json）から。
使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/pl28/pl28_gate_table.py --tag F_final=Unity/Build/Design/28R01F/F_final --tag G_final=Unity/Build/Polish/28/G_final
      --out Unity/Build/Polish/28/motion/gates_table.json
"""
import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SETS = ("default", "default_fine", "default_fine_stop13", "alt", "default_q13")


def jl(p):
    p = p if os.path.isabs(p) else os.path.join(REPO, p)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def short(v):
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, dict):
        return {k: short(x) for k, x in v.items()}
    return v


def gates_of(d):
    if d is None:
        return None
    out = {}
    for k, g in (d.get("gates") or {}).items():
        out[k] = dict(value=short(g.get("value")), pass_=g.get("pass"))
    for k, g in (d.get("gates_ds28") or {}).items():
        out[k] = dict(value=short(g.get("value")), pass_=g.get("pass"))
    p13 = ((d.get("gates") or {}).get("P13") or {}).get("detail") or {}
    out["P13_items"] = {k: dict(value=short(v.get("value")), threshold=v.get("threshold"), pass_=v.get("pass"), at=v.get("at"))
                        for k, v in p13.items() if isinstance(v, dict) and "value" in v}
    p17 = ((d.get("gates_ds28") or {}).get("P17") or {}).get("detail") or {}
    out["P17_main_row"] = short(p17.get("main_row"))
    out["P17_peak_row"] = short(p17.get("peak_row"))
    p18 = ((d.get("gates_ds28") or {}).get("P18") or {}).get("detail") or {}
    out["P18_detail"] = short({k: v for k, v in p18.items() if not isinstance(v, (list,)) or len(v) < 20})
    out["summary_all"] = d.get("summary_all")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", action="append", required=True, help="名前=包みの根（<根>/gates/*.json）")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    res = dict(schema="GreatWave.Polish28.gates_table/1", sets=list(SETS), tags={})
    for t in a.tag:
        name, root = t.split("=", 1)
        res["tags"][name] = dict(root=root, sets={s: gates_of(jl(os.path.join(root, "gates", s + ".json"))) for s in SETS},
                                 p20_f_layers=jl(os.path.join(root, "art_on", "p20_f_layers.json")))
    out = a.out if os.path.isabs(a.out) else os.path.join(REPO, a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    # 画面へ：既定（16 bit）の P1〜P19
    names = list(res["tags"])
    keys = ["P%d" % i for i in range(1, 20)] + ["Painting"]
    for k in keys:
        row = []
        for n in names:
            g = (res["tags"][n]["sets"]["default"] or {}).get(k)
            row.append("%s %s" % ("合" if g and g["pass_"] else "否", json.dumps(g["value"], ensure_ascii=False)[:90]) if g else "—")
        print(k, " | ".join(row))
    for n in names:
        print(n, "P13:", {k.split(")")[0] + ")": (v["value"], v["pass_"]) for k, v in (res["tags"][n]["sets"]["default"] or {}).get("P13_items", {}).items()})
        for s in SETS:
            sa = (res["tags"][n]["sets"][s] or {}).get("summary_all")
            print("  ", s, sa)


if __name__ == "__main__":
    main()
