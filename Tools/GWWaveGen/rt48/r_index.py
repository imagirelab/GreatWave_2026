# -*- coding: utf-8 -*-
"""RT48：Unity が読むデータの目次 Unity/Build/RT48/data/manifest.json を、元ごとの manifest と確かめの記録から作り直す（py -3.10）。
使い方: py -3.10 r_index.py
目次の中身：元（coarse・fine）ごとの置き場所・状態・使ってよいか・manifest の SHA-256、既定の元、座席、字（計画 §3.6 の文のまま）、
計算し直し（R3e）の状態、確かめ（C1・C2）の結果の要約。"""
import os as _os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")
import os, json, time, hashlib

DATA = os.environ.get("RT48_DATA", "G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48/data")   # 試しの時だけ環境変数で替える
RERUN = os.environ.get("RT48_RERUN", "G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48/rerun/R3e")

CAPTIONS = {
    "1": "この波は 2 次元の断面の計算（FLIP42 R3、粒子 0.25 m、重力だけ）を横に並べたもので、長さの向きにどこも同じ形です",
    "2": "オフラインで計算した結果の再生で、水の動きは毎フレーム計算していません",
    "3_fine": "粒子から作った細かい面（Zhu & Bridson, 0.125 m）",
    "3_coarse": "粗い元（計算の格子 0.5 m の面）・補間は未確認",
    "4": "巻き始め 154.7 s / 唇が前の面に付く 156.0 s",
    "5": "唇の大きさは、細かさで落ち着くかをまだ判定できていません",
    "6": "ここから 24 コマ/秒、補間なし",
    "7": "接触の後の形は 1 回の計算の結果で、計算ごとに変わります（2 つ目の噴流の届く距離は 4.1〜9.1 m）。板の幅 2 m の中でも水面は最大 1.87 m 違い、並べたのは板の真ん中の 1 枚です",
}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def jl(p):
    return json.load(open(p, encoding="utf8")) if os.path.exists(p) else None


def main():
    c1a, c1b, c2 = jl(os.path.join(DATA, "c1a.json")), jl(os.path.join(DATA, "c1b.json")), jl(os.path.join(DATA, "c2.json"))
    st = jl(os.path.join(RERUN, "chain_state.json"))
    src = {}
    for name in ("coarse", "fine"):
        mp = os.path.join(DATA, name, "manifest.json")
        if not os.path.exists(mp):
            src[name] = dict(status="not_built")
            continue
        m = jl(mp)
        e = dict(status="built", dir=name, manifest="%s/manifest.json" % name, manifest_sha256=sha(mp), label=m["label"],
                 caption=CAPTIONS["3_" + name], files={k: dict(name="%s/%s" % (name, v["name"]), bytes=v["bytes"], sha256=v["sha256"], shape=v["shape"])
                                                       for k, v in m["files"].items()},
                 frames=[m["time"]["first_frame"], m["time"]["last_frame"]], n_points=m["n_points"], K=m["playback"]["K"],
                 n_interp_pairs=m["playback"]["n_interp"], n_pairs=m["playback"]["n_pairs"], still_offset_m=m["coords"]["still_offset_m"],
                 clip_end={k: dict(frame=v["clip_end_frame"], t=v["clip_end_t"]) for k, v in m["boat"].items()},
                 checks=dict(C3_ok=m["checks"]["C3"]["ok"], C3_max=m["checks"]["C3"]["max"], C4_fail=m["checks"]["C4"]["n_fail"], C4_n=m["checks"]["C4"]["n"]))
        src[name] = e
    fine_ok = bool(c1b and c1b.get("pass") and c2 and c2.get("pass_all") and src["fine"].get("status") == "built")
    if src["coarse"].get("status") == "built":
        src["coarse"]["use"] = "Unity の部品と静止画のため（計画 §2.4）。画面に「%s」と出す" % CAPTIONS["3_coarse"]
    if src["fine"].get("status") == "built":
        src["fine"]["use"] = ("動画と報告に使う（C1 (b) と C2 が全部入った）" if fine_ok else
                              "動画と報告には使わない（C1 (b) か C2 が外れた。計画 §4・§5 により粗い元で出す）。横からの絵で並べるだけ")
    idx = dict(
        format="RT48 data index v1", date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/rt48/r_index.py",
        record="record_ja.md", plan="../plan/plan_ja.md",
        default_source="fine" if fine_ok else "coarse",
        sources=src,
        units=dict(length="m", time="s（計算の時刻）", angle="deg"),
        coords="X = x_rel − 527.0 m（波は +X へ進む）、Y = 静かな水面からの高さ。Unity の X = (X + 527.0) − 座席の x_rel、Y = Y、Z = 頂の向き",
        seats=dict(default=556.0, others=[574.0]),
        events=dict(onset_t=154.70833333333334, first_contact_t=156.0, clip_start_t=138.25),
        captions=CAPTIONS,
        checks=dict(C1a=None if not c1a else dict(pass_=c1a["pass"], file="c1a.json"),
                    C1b=None if not c1b else dict(pass_=c1b["pass"], file="c1b.json"),
                    C2=None if not c2 else dict(pass_all=c2["pass_all"], a=c2["a"]["ok"], b=c2["b"]["ok"], c=c2["c"]["ok"], d=c2["d"]["ok"], e=c2["e"]["ok"], file="c2.json")),
        rerun=dict(dir=RERUN, state=st, note="R3e：R3 の 3318 コマ目の途中保存から 3319〜3889 コマを計算し直し、粒子を書き出す。R4d の chain の後に始まる"),
    )
    json.dump(idx, open(os.path.join(DATA, "manifest.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    print(json.dumps(dict(default_source=idx["default_source"], sources={k: v.get("status") for k, v in src.items()}), ensure_ascii=False))


if __name__ == "__main__":
    main()
