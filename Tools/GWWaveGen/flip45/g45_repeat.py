# -*- coding: utf-8 -*-
"""FLIP45：繰り返し（RPT05）の判定（py -3.10。計画 plan_ja.md §6.6）。2026-10-12 進行役が新しく書いた。
  出来事：y = 0 の断面の巻き始め（§6.1 と同じ読み。g45_analyze.crest_events）。一つの頂の続く巻き（巻き始めから 0.5 T の中の次の巻き始め）は一つと数える。
  落ち着いた区間：焦点（212 m）の線形の包絡が 95 % に届く 57.9 s から 120 s まで。最初の巻き（過渡）は別に書く。
  判定：落ち着いた区間の 2 つ目からの出来事を、その区間の最初の出来事と比べ、時刻の差が（回数 × T）± 0.35 s、場所 ±3.6 m、η_c と H が ±5 %。
    場合 1：落ち着いた区間に 4 回以上あり、全部が幅に入った。場合 2：毎周期 1 回ずつ、最初の場所の ±0.5 λ（36 m）の中で巻いたが、幅を外れた回がある。
    場合 3：巻かない周期があった。
使い方：py -3.10 g45_repeat.py <run_id> [runs|smoke]   → <置き場所>/<run_id>/repeat.json
"""
import sys, os, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g45_common as GC
import g45_analyze as GA

T = GC.T; LAM = GC.L0
T_SETTLED = 57.9


def events_from(rid, root="runs"):
    rd = GA.run_dir(rid, root)
    cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    recs = GA.records(rd)
    R1 = GA.Reader(rd, "hf", "eta"); R2 = GA.Reader(rd, "r2", "sdf")
    off, src = GA.still_offset(rd, cfg, recs, R1)
    P = cfg["parms"]
    ev = GA.crest_events(R2, off, 2 * float(P["dp"]), float(P["t_off"]) + 2.0, float(P["in1"]) + 5.0, float(P["ex0"]), float(P["t_off"]))
    ons = sorted([e["onset"] for e in ev if e["onset"]], key=lambda o: o["t"])
    merged = []
    for o in ons:
        if merged and o["t"] - merged[-1]["t"] <= 0.5 * T:
            continue
        merged.append(o)
    return merged, off


def judge(onsets, t_end=120.0):
    first_all = onsets[0] if onsets else None
    st = [o for o in onsets if o["t"] >= T_SETTLED - 1e-9]
    res = dict(first_transient=first_all, settled=st, t_settled=[T_SETTLED, t_end])
    if not st:
        res.update(case=3, sentence_ja="毎周期は巻かなかった（落ち着いた区間に巻き始めがない）")
        return res
    base = st[0]
    rows = []
    allin = True
    for o in st[1:]:
        n = round((o["t"] - base["t"]) / T)
        dt = o["t"] - base["t"] - n * T
        dx = o["xc"] - base["xc"]
        rA = o["eta_c"] / base["eta_c"] - 1
        rH = (o["H"] / base["H"] - 1) if (o.get("H") and base.get("H")) else None
        ok = abs(dt) <= 0.35 and abs(dx) <= 0.05 * LAM and abs(rA) <= 0.05 and (rH is None or abs(rH) <= 0.05)
        allin &= ok
        rows.append(dict(t=o["t"], n_periods=n, dt=dt, dx=dx, rel_eta=rA, rel_H=rH, inside=ok))
    periods = int(math.floor((t_end - base["t"]) / T)) + 1
    counted = sorted(set(r["n_periods"] for r in rows) | {0})
    every = counted == list(range(0, max(counted) + 1)) and len(counted) >= periods - 1
    near = all(abs(r["dx"]) <= 0.5 * LAM for r in rows)
    if len(st) >= 4 and allin and every:
        case, s = 1, "粒子 0.5 m の粗い計算で、落ち着いた区間の %d 回は同じ所でそろって巻いた" % len(st)
    elif every and near:
        case, s = 2, "毎周期巻いたが、場所・高さ・時刻はそろわなかった"
    else:
        case, s = 3, "毎周期は巻かなかった（巻いた周期 %s）" % counted
    res.update(case=case, sentence_ja=s, rows=rows, base=base, periods_expected=periods)
    return res


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    rid = sys.argv[1]; root = sys.argv[2] if len(sys.argv) > 2 else "runs"
    ons, off = events_from(rid, root)
    r = judge(ons)
    r["still_offset_m"] = off
    json.dump(r, open(os.path.join(GA.run_dir(rid, root), "repeat.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    print(json.dumps({k: r.get(k) for k in ("case", "sentence_ja")}, ensure_ascii=False))
