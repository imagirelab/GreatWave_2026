# -*- coding: utf-8 -*-
"""FLIP44 の確かめ：形の本番（SH）の途中保存の間隔を f_w まで固定する決まり（g44_cfg.py・g44_chain.py）が、
区切った起動（1 回 1,740 s）の中で捨てるコマの分だけ、どれだけ時間を延ばすかの見積もり【推定】。py -3.10、numpy だけ。
1 コマの秒は FLIP42 R3（粒子 0.25 m、10/9 の機械）の記録を、R3 の巻き始めが形の本番の巻き始めに来るようにずらして使い、機械の重さの倍率 1.0・1.33・2.0 を掛ける。
起動ごとに、始めのコマから 1,740 s で届く最後のコマまで進み、届いた途中保存（間隔 sp の倍数）の次から次の起動を始める（g44_chain.py と同じ）。
起動ごとの読み込みの時間 45 s を足す。出力：Unity/Build/FLIP44/check/c44_lock_cost.json
"""
import json, glob, os
import numpy as np

R3 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs/R3"
OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP44/check/c44_lock_cost.json"
fs = sorted(glob.glob(os.path.join(R3, "hf_c*.npz")), key=lambda p: int(os.path.basename(p)[4:8]))
F, W = [], []
for p in fs:
    d = np.load(p); fr = list(d["frames"])
    if F:
        keep = [i for i, f in enumerate(F) if f < fr[0]]
        F = [F[i] for i in keep]; W = [W[i] for i in keep]
    F += fr; W += list(d["wall"])
F = np.array(F); W = np.array(W)
cost = {int(f): float(w) for f, w in zip(F, W)}
cost[1] = cost.get(2, 3.0)


def rule_sp(f_w):
    divs = [d for d in range(120, 301) if f_w % d == 0]
    while not divs:
        f_w -= 1
        divs = [d for d in range(120, 301) if f_w % d == 0]
    return f_w, min(divs, key=lambda d: (abs(d - 240), -d))


def to_fw(f_w, sp, load, f_on, WL=1740.0, boot=45.0):
    """f_on：形の本番の巻き始めのコマ。R3 の 1 コマの秒を、R3 の巻き始め（3714 コマ）が f_on に来るようにずらして使う。"""
    sh = 3714 - f_on
    c = lambda f: cost[min(max(f + sh, 2), 4508)]
    f0 = 1; tot = 0.0; launches = 0; wasted = 0
    while f0 <= f_w:
        launches += 1
        s = 0.0; f = f0
        while f <= f_w and s + c(f) * load <= WL:
            s += c(f) * load; f += 1
        last = f - 1
        ck = (last // sp) * sp
        tot += s + boot
        if ck < f0:
            return dict(stalled=True, at=f0, launches=launches)
        wasted += last - ck
        f0 = ck + 1
    ideal = sum(c(f) * load for f in range(1, f_w + 1))
    return dict(stalled=False, hours=tot / 3600, ideal_hours=ideal / 3600, extra_hours=(tot - ideal) / 3600, launches=launches,
                wasted_frames=wasted)


res = {}
for onset in np.arange(140.0, 166.0, 1.0):
    f_w, sp = rule_sp(int(np.floor(24 * (onset - 6.0))))
    row = dict(f_w=f_w, sp=sp)
    for load in (1.0, 1.33, 2.0, 3.0):
        row["load%.2f" % load] = to_fw(f_w, sp, load, int(round(24 * onset)) + 1)
    res["%.0f" % onset] = row
summ = {}
for load in ("1.00", "1.33", "2.00", "3.00"):
    ex = [r["load" + load]["extra_hours"] for r in res.values() if not r["load" + load]["stalled"]]
    st = [k for k, r in res.items() if r["load" + load]["stalled"]]
    summ[load] = dict(extra_hours_min=min(ex) if ex else None, extra_hours_max=max(ex) if ex else None, stalled_onsets=st)
out = dict(note_ja="形の本番の途中保存の間隔を f_w まで固定する決まりで、起動ごとに捨てるコマの分の時間【推定】。下見の巻き始め 140〜165 s を 1 s ごと",
           summary=summ, rows=res)
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(summ, ensure_ascii=False, indent=1))
for k in ("145", "150", "155", "160"):
    r = res[k]
    print(k, r["f_w"], r["sp"], {l: (round(r[l]["extra_hours"], 2) if not r[l]["stalled"] else "STALL") for l in r if l.startswith("load")})
