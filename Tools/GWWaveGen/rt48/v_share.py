# -*- coding: utf-8 -*-
"""RT48：再生の時刻の規則（u_bakeio.state_at、Unity と同じ）で、補間しているフレームの割合を数える（py -3.10）。
動画（60 fps）と VR（90 Hz）の刻みで、座席の船からのクリップ（138.25 s〜座席の終わり）と横からの動画（138.25〜162.0 s）について。
補間しない理由（K から先・C4 で外れた組・自分と交わる組）ごとの数と、K の前だけの割合も書く。
使い方: py -3.10 v_share.py coarse,fine   → Unity/Build/RT48/verify/<元>/interp_share.json"""
import os as _os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")
import sys, os, json, math
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import u_bakeio as U

BUILD = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48"


def count(meta, reasons, t0, t1, hz, K_t):
    n = int(math.floor((t1 - t0) * hz + 1e-9)) + 1
    res = dict(hz=hz, t0=t0, t1=t1, n=n, interp=0, held={}, before_K=dict(n=0, interp=0))
    for i in range(n):
        t = t0 + i / hz
        st = U.state_at(meta, t)
        bk = t < K_t - 1e-9
        if bk:
            res["before_K"]["n"] += 1
        if st["interp"]:
            res["interp"] += 1
            if bk:
                res["before_K"]["interp"] += 1
        else:
            why = "last" if st["last"] else reasons[st["frame"]]
            res["held"][why] = res["held"].get(why, 0) + 1
    res["share"] = res["interp"] / n
    res["before_K"]["share"] = res["before_K"]["interp"] / max(1, res["before_K"]["n"])
    return res


def main(src):
    d = os.path.join(BUILD, "data", src)
    man = json.load(open(os.path.join(d, "manifest.json"), encoding="utf8"))
    meta = dict(fps=man["time"]["fps"], frame_first=man["time"]["first_frame"], frame_count=man["time"]["n_frames"],
                pair_count=man["playback"]["n_pairs"], n_points=man["n_points"], pair_interp=[1 if q["interp"] else 0 for q in man["pairs"]])
    reasons = [q["reason"] for q in man["pairs"]]
    t0, tl = man["time"]["t_first"], man["time"]["t_last"]
    K_t = man["events"]["K_t"]
    out = dict(source=src, rule="u_bakeio.state_at（Unity と同じ時刻の規則）", n_pairs=len(reasons), n_interp_pairs=sum(meta["pair_interp"]), K=man["playback"]["K"], K_t=K_t, rows={})
    for seat in ("556", "574"):
        te = man["boat"][seat]["clip_end_t"]
        out["rows"]["boat%s_60fps" % seat] = count(meta, reasons, t0, te, 60.0, K_t)
        out["rows"]["boat%s_90hz" % seat] = count(meta, reasons, t0, te, 90.0, K_t)
    out["rows"]["side_60fps"] = count(meta, reasons, t0, tl, 60.0, K_t)
    od = os.path.join(BUILD, "verify", src)
    os.makedirs(od, exist_ok=True)
    json.dump(out, open(os.path.join(od, "interp_share.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    for k, r in out["rows"].items():
        print(src, k, "n", r["n"], "interp", r["interp"], "share %.3f" % r["share"], "beforeK %d/%d %.3f" % (r["before_K"]["interp"], r["before_K"]["n"], r["before_K"]["share"]), r["held"])


if __name__ == "__main__":
    for s in sys.argv[1].split(","):
        main(s)
