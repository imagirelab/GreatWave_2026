# -*- coding: utf-8 -*-
"""FLIP44：原画との残りの差の表（計画 plan_ja.md §5）。py -3.10。
量ごとに 1 行：原画（縦の伸びを戻した形、幅）、R3（礁なし）、礁（形の本番 SH）、礁＋風（はがれた流れの形 S の 2 本）、残り（原画 − 礁＋風）、
SH の細かさの誤差の目安（2.5〜3.3 Y）、礁が縮めた割合と風が縮めた割合（R3 からの差に対して）、風が縮めた割合（風なしの残りに対して、W5）、
はがれのない流れの極み（N の 2 本。走らせた時だけ。割合は出さない）。
割合を出さない決まり（計画 §5.1）：比べる元が原画の幅の中か、|原画 − 比べる元| < 2Y なら出さず、理由を書く。
値は各計算のいちばん巻いたコマ（g44_shape.measure_three）。原画・R3・R4d・Y は plan_numbers.json の shape（凍結した数）。
使い方：py -3.10 g44_ctable.py <SH の id> [--wind B35S=<id> B45S=<id>] [--N B35N=<id> B45N=<id>] [--root runs|smoke|flip42] [--pr2] [--out <フォルダー>]
出力：Unity/Build/FLIP44/report/remaining_gap.json と remaining_gap_ja.md
"""
import sys, os, json
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip44")
import g44_analyze as A
import g44_shape as SHP

B44 = A.B44


def shape_of(rid, root):
    a = json.load(open(os.path.join(A.run_dir(rid, root), "ana.json"), encoding="utf8"))
    s = SHP.measure_three(rid, root, a["onset"]["frame"], a["touchdown"]["frame"])
    return s, a


def share(num, base, m, P):
    lo, hi = m["print_range"]
    Y = m["yardstick"]
    if lo <= base <= hi:
        return None, "すでに幅の中"
    if abs(m["print_cn"] - base) < P["criteria"]["share"]["no_share_gap_over_Y"] * Y:
        return None, "差が物差しの 2 倍より小さい"
    return num / (m["print_cn"] - base), None


def main(sh, wind, Nruns, root="runs", pr2=False, outdir=None):
    P = A.plan()
    S_sh, a_sh = shape_of(sh, root)
    W = {k: shape_of(v, root) for k, v in wind.items()}
    N = {k: shape_of(v, root) for k, v in Nruns.items()}
    f1, f2 = P["criteria"]["sh_abs_error"]["factor_over_Y"]
    rows = []
    for m in P["shape"]["measures"]:
        k = m["key"]
        r3 = m["R3"]; shv = S_sh["max_overturn"].get(k)
        wv = {n: w[0]["max_overturn"].get(k) for n, w in W.items()}
        nv = {n: w[0]["max_overturn"].get(k) for n, w in N.items()}
        row = dict(key=k, ja=m["ja"], unit=m["unit"], print_cn=m["print_cn"], print_range=m["print_range"], print_drawn=m["print_drawn"],
                   print_is_lower_bound=m["print_is_lower_bound"], R3=r3, SH=shv, wind=wv, Y=m["yardstick"],
                   sh_abs_error_range=[f1 * m["yardstick"], f2 * m["yardstick"]])
        row["remaining"] = {n: (m["print_cn"] - v) if v is not None else None for n, v in wv.items()}
        if shv is not None:
            s, why = share(shv - r3, r3, m, P)
            row["share_reef_of_total"] = s; row["share_reef_why_not"] = why
            row["reef_moved"] = bool(abs(shv - r3) > m["yardstick"]); row["reef_toward_print"] = bool(np.sign(shv - r3) == np.sign(m["print_cn"] - r3))
            row["wind_share_of_total"] = {}; row["wind_share_of_remaining"] = {}
            for n, v in wv.items():
                if v is None:
                    continue
                s1, w1 = share(v - shv, r3, m, P)
                s2, w2 = share(v - shv, shv, m, P)
                row["wind_share_of_total"][n] = s1 if s1 is not None else w1
                row["wind_share_of_remaining"][n] = s2 if s2 is not None else w2
        if nv:
            row["N_extreme"] = {n: dict(value=v, remaining=(m["print_cn"] - v) if v is not None else None) for n, v in nv.items()}
        rows.append(row)
    heights = dict(SH=dict(eta_c=a_sh["onset"]["eta_c"], H=a_sh["onset"]["H"]), R3=dict(eta_c=9.557, H=10.658),
                   wind={n: dict(eta_c=w[1]["onset"]["eta_c"], H=w[1]["onset"]["H"]) for n, w in W.items()},
                   print_ja="高さ 10〜12 m（Cartwright & Nakamura 2009 の読み）")
    out = dict(note_ja="原画との残りの差の表（計画 §5）。値は η_c で割った長さ・η_c² で割った面積・度。いちばん巻いたコマ。"
                       "「礁＋風」と「残り」の主の列ははがれた流れの形（S）の 2 本。N は極みの側として別の列に置き、主の残りに混ぜない",
               sh=sh, wind=wind, N=Nruns, pr2_note=("礁の列は位相の狙いの違いも含む（下見 2 の入口を選んだため）" if pr2 else None),
               rows=rows, heights=heights, not_in_2d=["頂の横の長さ（2D では測れない。3D でしか扱えない）"],
               vertical_stretch_ja="描かれたままは戻した形の 1.3 倍（Cartwright & Nakamura 2009）。描かれたままと戻した形の差として別に渡す")
    outdir = outdir or os.path.join(B44, "report")
    os.makedirs(outdir, exist_ok=True)
    json.dump(out, open(os.path.join(outdir, "remaining_gap.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)

    def f(v, unit):
        if v is None:
            return "—"
        if isinstance(v, str):
            return v
        return ("%.1f°" % v) if unit == "deg" else ("%.3f" % v)
    L = ["# 原画との残りの差（自動で作った表。計画 §5）", "",
         "| 量 | 原画（幅） | R3 | 礁 SH | 礁＋風 %s | 残り | SH の細かさの誤差の目安 | 礁の割合（R3 から） | 風の割合（R3 から） | 風の割合（風なしの残り） |" % "・".join(wind),
         "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        u = r["unit"]
        pct = lambda v: ("%.0f %%" % (100 * v)) if isinstance(v, (int, float)) else (v or "—")
        L.append("| %s | %s（%s〜%s） | %s | %s | %s | %s | %s〜%s | %s | %s | %s |" % (
            r["ja"], f(r["print_cn"], u), f(r["print_range"][0], u), f(r["print_range"][1], u), f(r["R3"], u), f(r["SH"], u),
            "・".join(f(v, u) for v in r["wind"].values()) or "—", "・".join(f(v, u) for v in r["remaining"].values()) or "—",
            f(r["sh_abs_error_range"][0], u), f(r["sh_abs_error_range"][1], u),
            pct(r.get("share_reef_of_total") if r.get("share_reef_of_total") is not None else r.get("share_reef_why_not")),
            "・".join(pct(v) for v in r.get("wind_share_of_total", {}).values()) or "—",
            "・".join(pct(v) for v in r.get("wind_share_of_remaining", {}).values()) or "—"))
    open(os.path.join(outdir, "remaining_gap_ja.md"), "w", encoding="utf8").write("\n".join(L) + "\n")
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    sh = a[0]; wind = {}; Nr = {}; root = "runs"; mode = None; pr2 = "--pr2" in a; outdir = None
    for q in a[1:]:
        if q in ("--wind", "--N"):
            mode = q; continue
        if q in ("--root", "--out"):
            mode = q; continue
        if mode == "--out":
            outdir = q; mode = None; continue
        if q == "--pr2":
            continue
        if mode == "--root":
            root = q; mode = None; continue
        k, v = q.split("=", 1)
        (wind if mode == "--wind" else Nr)[k] = v
    o = main(sh, wind, Nr, root, pr2, outdir)
    txt = open(os.path.join(outdir or os.path.join(B44, "report"), "remaining_gap_ja.md"), encoding="utf8").read()
    try:
        print(txt)
    except UnicodeEncodeError:      # 2026-10-12 確かめ G7：標準出力が cp932 の時（Git Bash・ファイルへ流した時）、「—」などを ? にして表示する
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(txt.encode(enc, "replace").decode(enc, "replace"))
