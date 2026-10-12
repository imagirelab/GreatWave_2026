# -*- coding: utf-8 -*-
"""算例ごとの動画と、並べた比べの動画を作る（gwvideo を使う）。

原画の輪郭を重ねる時間：巻き始め（覆いかぶさりが出たコマ）から最初の着水のコマまで。
頂の高さ・位置は、物差し（gwruler）が各コマで読んだ η_c・x_c（m）を h0 = 19 m で割って使う。

使い方：
  python3 make_videos.py case 名前 ...           # Docs/Evidence/Basilisk/<名前>.mp4
  python3 make_videos.py compare 出力.mp4 名前 ...  # 着水の時刻をそろえて並べる
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gwvideo as V  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EVID = os.path.join(REPO, "Docs", "Evidence", "Basilisk")
RUNS = os.environ.get("GW_RUNS", "/opt/gw/runs")
ANA = os.environ.get("GW_ANA", "/opt/gw/ana")
CASES = json.load(open(os.path.join(HERE, "..", "cases.json"), encoding="utf8"))
H0M = 19.0


def meta_of(name):
    c = CASES[name]
    return dict(name=name.replace("_", " "), title_ja=c.get("short_ja", c["desc_ja"]), bathy=c["bathy"], xl=c["xl"], lbox=c["lbox"],
                level=c["level"], h0_m=H0M)


def overlay_of(name):
    p = os.path.join(ANA, name + ".json")
    if not os.path.exists(p):
        return None, None, {}
    d = json.load(open(p, encoding="utf8"))
    s = d["summary"]
    rows = [r for r in d["ruler_frames"] if "eta_c" in r]
    score = {r["t"]: r["score3"] for r in rows if "score3" in r}
    if s.get("t_overturn") is None or not rows:
        return None, s.get("t_touchdown"), score
    t1 = s.get("t_touchdown") or rows[-1]["t"]
    ov = dict(t_start=s["t_overturn"], t_end=t1,
              eta_c_by_t={r["t"]: r["eta_c"] / H0M for r in rows},
              xc_by_t={r["t"]: r["x_c"] / H0M for r in rows})
    return ov, s.get("t_touchdown"), score


def case(name):
    os.makedirs(EVID, exist_ok=True)
    ov, ttd, _ = overlay_of(name)
    out = os.path.join(EVID, name + ".mp4")
    r = V.render_case(os.path.join(RUNS, name), out, meta_of(name), overlay=ov if ov else False)
    print(name, os.path.getsize(out), r)
    return out


def compare(out, names, tau_start=-1.5, tau_end=0.6):
    cs = []
    for n in names:
        ov, ttd, score = overlay_of(n)
        cs.append(dict(run_dir=os.path.join(RUNS, n), meta=meta_of(n), t_ref=ttd, score_by_t=score, overlay=ov))
    r = V.render_compare(cs, out, tau_start=tau_start, tau_end=tau_end)
    print(out, os.path.getsize(out), r)


if __name__ == "__main__":
    if sys.argv[1] == "case":
        for n in sys.argv[2:]:
            case(n)
    elif sys.argv[1] == "compare":
        compare(sys.argv[2], sys.argv[3:])
