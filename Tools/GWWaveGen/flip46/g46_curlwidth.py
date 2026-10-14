# -*- coding: utf-8 -*-
"""FLIP46：巻いた所の横の全幅を、巻き始めから時間を追って読む（py -3.10 -B、numpy）。2026-10-15、3D を細くする試しのために足した。
g46_analyze.py は 4 つの時（巻き始め・GG06 図 9 の時刻・その遅れ・着水）だけ横の幅を読む。ここでは同じ読み（lateral_rows_r4：r4 の 3D の記録の
各 y の断面で頂の前の面の最大の角 thmax ≥ 90° の、y = 0 から続く範囲 × 2）を、巻き始めのコマから --dt_end 秒（既定 2 s）まで
--every コマ（既定 2）ごとに読み、各コマの頂の高さ（真ん中）と、巻いた全幅 ÷ 真ん中の頂の高さを出す。
真ん中の頂の x は、そのコマの r2（y = 0 の断面）の頂の中で最も高い物（なければ前のコマの値）。
使い方：py -3.10 -B g46_curlwidth.py <走らせた所> [--every=2] [--dt_end=2.0] [--x_end_pad=8]
出す物：<走らせた所>/curlwidth.json と、画面への表
"""
import os, sys, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g46_analyze as A46   # noqa: E402


def run(rd, every=2, dt_end=2.0, x_end_pad=8.0):
    rd = os.path.abspath(rd)
    ana = json.load(open(os.path.join(rd, "ana.json"), encoding="utf8"))
    on = ana.get("onset") or ana.get("steepest")
    if not on:
        raise SystemExit("巻き始めも最も険しいコマもない")
    cx = A46.Ctx(rd, {})
    cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    x_end = float(cfg["parms"]["x0"]) + float(cfg["parms"]["Lx"]) - x_end_pad
    f0 = int(on["frame"]); f1 = f0 + int(round(dt_end * 24))
    xc = float(on.get("xc") or on.get("xc_centre"))
    rows = []
    for f in range(f0, f1 + 1, every):
        if f not in cx.R2.b or f not in cx.R4.b:
            continue
        S, m, t = cx.R2.get(f)
        cr, _, _ = cx.section_crests(S, m, float(m.get("z", 0.0)), x_lo=xc - 0.5 * cx.Lc, x_hi=xc + 0.5 * cx.Lc)
        if cr:
            c = max(cr, key=lambda r: r["eta"])
            xc = float(c["xc"]); eta = float(c["eta"]); th = float(c["thmax"])
        else:
            eta = None; th = None
        r4 = A46.lateral_rows_r4(cx, f, xc)
        s = (r4 or {}).get("summary") or {}
        full = s.get("overturned_full_m")
        rows.append(dict(frame=f, t=float(t), xc=xc, eta_c=eta, thmax_c=th, overturned_full_m=full,
                         ratio_full_over_eta=(full / eta if (full is not None and eta) else None),
                         near_end_wall=bool(xc >= x_end)))
    ok = [r for r in rows if r["overturned_full_m"] and not r["near_end_wall"]]
    best = max(ok, key=lambda r: r["overturned_full_m"]) if ok else None
    out = dict(run_id=cfg["run_id"], tool="g46_curlwidth.py", onset_frame=f0, every=every, dt_end=dt_end, x_end_wall_pad_m=x_end_pad,
               rows=rows, max_before_end_wall=best,
               rule_ja="巻いた全幅 = r4 の各 y の断面で thmax ≥ 90° が y = 0 から続く範囲 × 2（g46_analyze.rows_summary と同じ）。下流の壁の手前 %g m より先の頂は「壁の近く」として最大から除く" % x_end_pad)
    json.dump(out, open(os.path.join(rd, "curlwidth.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    opt = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--"))
    for a in [a for a in sys.argv[1:] if not a.startswith("--")]:
        o = run(a, every=int(opt.get("every", 2)), dt_end=float(opt.get("dt_end", 2.0)), x_end_pad=float(opt.get("x_end_pad", 8.0)))
        print("#", o["run_id"])
        print("| コマ | t（s） | 頂の x（m） | 真ん中の頂（m） | 真ん中の thmax | 巻いた全幅（m） | 全幅 ÷ 頂 | 壁の近く |")
        print("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for r in o["rows"]:
            f = lambda v, s="%.2f": "—" if v is None else s % v
            print("| %d | %.3f | %.1f | %s | %s | %s | %s | %s |" % (r["frame"], r["t"], r["xc"], f(r["eta_c"]), f(r["thmax_c"], "%.0f°"),
                                                                f(r["overturned_full_m"], "%.0f"), f(r["ratio_full_over_eta"]), "はい" if r["near_end_wall"] else ""))
        print("最大（壁の近くを除く）：", o["max_before_end_wall"])
