# -*- coding: utf-8 -*-
"""1 本の計算の結果をまとめて測る：論文の量（gwpaper）と、原画の物差し（gwruler）の score3。

物差しで測るコマ：覆いかぶさりが出たコマ（巻き始め）から、最初の着水のコマまで、書き出した全部のコマ。
出力：JSON（summary：論文の量、ruler：score3 の最小のコマと着水のコマ、ruler_frames：コマごとの量）。
"""
import os, sys, json, argparse
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gwread as G  # noqa: E402
import gwpaper as P  # noqa: E402
import gwruler as R  # noqa: E402


def ruler_series(run, seq, summ):
    t0 = summ.get("t_overturn")
    t1 = summ.get("t_touchdown")
    if t0 is None:
        return [], None, None
    if t1 is None:
        t1 = max(o["t"] for o in seq)
    rows = []
    for o in seq:
        if "error" in o or o["t"] < t0 - 1e-9 or o["t"] > t1 + 1e-9:
            continue
        fr = G.read_frame(os.path.join(run, o["file"]))
        r = R.measure_frame(fr)
        r["file"] = o["file"]
        rows.append(r)
    good = [r for r in rows if "score3" in r]
    best = min(good, key=lambda r: (r["score3"], -r["t"])) if good else None
    td = good[-1] if good and summ.get("t_touchdown") is not None and abs(good[-1]["t"] - t1) < 1e-6 else None
    return rows, best, td


def analyze(run, out=None, meta=None):
    seq = P.analyze_run(run)
    summ = P.summarize(run, seq)
    rows, best, td = ruler_series(run, seq, summ)
    res = dict(meta=meta or {}, summary=summ, ruler=dict(best=best, touchdown=td, n_frames=len(rows),
                                                         print_cn=R.PRINT, bands=R.BANDS),
               ruler_frames=rows, frames=seq)
    if out:
        json.dump(res, open(out, "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    return res


def brief(res):
    s = res["summary"]
    b = res["ruler"]["best"]; td = res["ruler"]["touchdown"]
    keys = ("t_overturn", "x_c_overturn", "eta_c_overturn", "eta_c_max", "t_touchdown", "x_c_touchdown", "x_tip_touchdown",
            "eta_c_touchdown", "A_O_over_Htd2", "A_J_over_Htd2", "theta_O_deg", "W_over_L", "jet_width_over_Htd")
    line = {k: (round(s[k], 3) if isinstance(s.get(k), float) else s.get(k)) for k in keys}
    rk = ("t", "score3", "face_chord_deg_01_05", "front_x01_rel", "hood_area", "gap_max", "lip_thick_mid", "back_angle_07_09_deg", "width07_silhouette")
    fmt = lambda r: {k: (round(r[k], 3) if isinstance(r.get(k), float) else r.get(k)) for k in rk} if r else None
    return dict(paper=line, best=fmt(b), touchdown=fmt(td))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="1 本の計算をまとめて測る")
    ap.add_argument("run")
    ap.add_argument("out")
    ap.add_argument("--meta", default=None, help="算例の情報の JSON")
    ap.add_argument("--case", default=None, help="Tools/Basilisk/cases.json の算例の名前（--meta の代わり）")
    a = ap.parse_args()
    meta = json.load(open(a.meta, encoding="utf8")) if a.meta else None
    if a.case:
        meta = json.load(open(os.path.join(HERE, "..", "cases.json"), encoding="utf8")).get(a.case, dict(name=a.case))
    res = analyze(a.run, a.out, meta)
    print(json.dumps(brief(res), ensure_ascii=False, indent=1))
