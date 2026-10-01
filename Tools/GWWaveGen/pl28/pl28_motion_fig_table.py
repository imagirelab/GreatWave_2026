# -*- coding: utf-8 -*-
"""仕上げ28：動きの当て直しの数の表（1920×1080 の PNG）。F_final（今の体験）・G_final（K*′ P28R2 への当て直し）・修正の回の版を並べる。
読むもの：motion/gates_table.json（関門 P1〜P19、16 bit の既定）、<版>/scan.json（60 Hz の走査）、motion/fr/motion_<版>.json（最終の評審の定義の
体積・頂の ±2 m 弦角）、motion/loaf_*.json（側面の塊）、review/review_<版>.json（Q13・Q15・Q17 の値）、motion/acc30_<版>.json（P13 の (2) の分布）。
使い方：py -3.10 -B Tools/GWWaveGen/pl28/pl28_motion_fig_table.py --tags F_final,G_final,G_p28a,G_p28b --adopt G_p28b --out <png>
"""
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
B = os.path.join(REPO, "Unity", "Build", "Polish", "28")
FONT = r"C:\Windows\Fonts\meiryo.ttc"


def jl(p):
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def F(sz):
    return ImageFont.truetype(FONT, sz)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", required=True)
    ap.add_argument("--adopt", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    tags = a.tags.split(",")
    gt = jl(os.path.join(B, "motion", "gates_table.json"))
    loafs = {}
    for f in ("loaf_E_F_G.json", "loaf_fix.json", "loaf_fix2.json"):
        d = jl(os.path.join(B, "motion", f))
        if d:
            loafs.update(d["tags"])

    def g(t, k):
        x = ((gt["tags"].get(t) or {}).get("sets", {}).get("default") or {}).get(k)
        return x

    def gv(t, k, fmt="%.3g"):
        x = g(t, k)
        if not x:
            return "—"
        v = x["value"]
        if isinstance(v, dict):
            v = "／".join(fmt % vv if isinstance(vv, (int, float)) else str(vv) for vv in list(v.values())[:3])
        elif isinstance(v, (int, float)):
            v = fmt % v
        return ("合 " if x["pass_"] else "否 ") + str(v)

    def p13(t, key):
        x = g(t, "P13_items") or {}
        for k, v in x.items():
            if k.startswith(key):
                val = v["value"]
                if isinstance(val, list):
                    val = "〜".join("%.3g" % q for q in val)
                elif isinstance(val, float):
                    val = "%.4g" % val
                return ("合 " if v["pass_"] else "否 ") + str(val)
        return "—"

    def fr(t, k):
        d = jl(os.path.join(B, "motion", "fr", "motion_%s.json" % t))
        if not d:
            return "—"
        if k == "loss":
            return "%.1f%%（最大 %.0f → t* %.0f m³）" % (100 * d["V_loss_frac_from_max"], d["V_max"][0], d["V_m3"]["+0.0"])
        if k == "step":
            return "%.2f" % d["V_step_last2s_max_before_max_ratio"][2]
        c = d["chord_pre_lip"]
        if k == "chord":
            return "%d 行（最小 %.0f°、行 %d）" % (c["rows_le110_ge0p5s"], c["min_deg"], c["argmin_row"])
        if k == "chord125":
            return "%d 行" % c["rows_le125_ge0p5s"]
        if k == "selfx":
            return "%d こま" % d["selfx_frames"]
        return "—"

    def scan(t):
        root = os.path.join(B, t) if t != "F_final" else os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "F_final")
        d = jl(os.path.join(root, "scan.json"))
        if not d:
            return "—"
        return "%d こま・%d こま" % (d["m1"]["section_selfx_frames"], d["m1"]["local_selfx_motion_frames"])

    def loaf(t, key="loaf_index"):
        d = loafs.get(t)
        if not d:
            return "—"
        v = [d["by_t"][s][key] for s in ("4.0", "5.0", "6.0")]
        return "／".join("%.2f" % x for x in v)

    def rv(t):
        p = os.path.join(B, "review", "review_%s.json" % t) if t != "F_final" else os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "review", "review_F_final.json")
        d = (jl(p) or {}).get(t)
        if not d:
            return "—"
        pc, fc, cu = d["pace"], d["front_crest"], d["curl"]
        return "%.2f／%.2f s・%.3f／%.3f Hf・%.3f／%.3f" % (pc["164"]["hump_to_C_s"], pc["183"]["hump_to_C_s"], fc["164"]["Theta90_H_over_Hf"],
                                                      fc["183"]["Theta90_H_over_Hf"], cu["164"]["visible"]["H_over_Hf"], cu["183"]["visible"]["H_over_Hf"])

    rows = [
        ("60 Hz の断面・局所の自己交差（τ −8〜0）", lambda t: scan(t)),
        ("P2 谷と釣り合う（≤ 0.2）", lambda t: gv(t, "P2")),
        ("P3 巻いても水が消えない（≤ 0.10）", lambda t: gv(t, "P3")),
        ("P4 唇先は重力だけ", lambda t: gv(t, "P4")),
        ("P7 前面が鉛直 → t*（1.6〜2.8 s）", lambda t: gv(t, "P7")),
        ("P11 海が波を運ぶ", lambda t: gv(t, "P11")),
        ("P13 (2) 地面の二階差分 30 Hz（≤ 0.0218 m）", lambda t: p13(t, "(2)")),
        ("P13 (5b) 行の方向の辺の最小（≥ 5 mm）", lambda t: p13(t, "(5b)")),
        ("P13 (5c) 行の方向の伸びの比（0.05〜4）", lambda t: p13(t, "(5c)")),
        ("P13 (5g) 面の反転 30 Hz（0）", lambda t: p13(t, "(5g)")),
        ("P16 唇がブレーキしない", lambda t: gv(t, "P16")),
        ("P17 本体の水（主断面／峰の行／全行の最大）", lambda t: gv(t, "P17")),
        ("P18 内壁が戻らない（m）", lambda t: gv(t, "P18")),
        ("体積（最終の評審の定義）最大から t* へ", lambda t: fr(t, "loss")),
        ("M2 最後の 2 s の 1 こまの変化 ÷ その前（≤ 1）", lambda t: fr(t, "step")),
        ("M7 唇の前の頂 ±2 m 弦角 ≤ 110° が 0.5 s 以上の行", lambda t: fr(t, "chord")),
        ("同 ≤ 125° が 0.5 s 以上の行", lambda t: fr(t, "chord125")),
        ("M10 側面の塊（後ろ÷前の 0.8H の距離、t 4／5／6 s。E は %s）" % loaf("E"), lambda t: loaf(t)),
        ("M10 平らな頂（0.95H の長さ ÷ H、t 4／5／6 s。E は %s）" % loaf("E", "plateau_95_over_H"), lambda t: loaf(t, "plateau_95_over_H")),
        ("Q17 小山→C（≥ 3 s）・E1 前面鉛直（≥ 0.72）・Q13 唇の見え始め", lambda t: rv(t)),
    ]
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((16, 8), "仕上げ28：動きの当て直しの数（F_final ＝ 今の体験、G_final ＝ K*′ P28R2 への当て直し、G_p28a・G_p28b ＝ 修正の回とその切り分け）", fill=(0, 0, 0), font=F(22))
    d.text((16, 40), "関門は設計27・28 の検査器（16 bit の既定の読み）。物理の関門は計画のとおり測って記録し、合否は閉じる目安に入れない。numpy の包みの測定で、描画ではない", fill=(70, 70, 70), font=F(15))
    x0, cw = 560, (W - 560 - 16) // len(tags)
    y = 74
    d.rectangle([0, y, W, y + 34], fill=(40, 40, 40))
    d.text((12, y + 6), "項目", fill=(255, 255, 255), font=F(17))
    for j, t in enumerate(tags):
        d.text((x0 + j * cw + 6, y + 6), t + ("（採用）" if t == a.adopt else ""), fill=(255, 230, 120) if t == a.adopt else (255, 255, 255), font=F(17))
    y += 36
    rh = (H - y - 10) // len(rows)
    for i, (name, fn) in enumerate(rows):
        if i % 2 == 0:
            d.rectangle([0, y, W, y + rh], fill=(242, 244, 247))
        d.text((12, y + 6), name, fill=(0, 0, 0), font=F(15))
        for j, t in enumerate(tags):
            s = fn(t)
            col = (170, 20, 20) if s.startswith("否") else (0, 0, 0)
            d.text((x0 + j * cw + 6, y + 6), s[:46], fill=col, font=F(14))
        y += rh
    img.save(a.out)
    print("table", a.out)


if __name__ == "__main__":
    main()
