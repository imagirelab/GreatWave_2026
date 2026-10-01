# -*- coding: utf-8 -*-
"""仕上げ30：前（仕上げ29 の海）と後（仕上げ30 の海）の Unity の描画（PL30Render）を同じ読みで数える。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/pl30/pl30_measure.py --before Unity/Build/Polish/30/before --after Unity/Build/Polish/30/after_r7 --out Unity/Build/Polish/30/measure_r7
数えるもの（どれも Unity の PC オフスクリーン描画の画像から。HMD ではない）：
  fuji   原画視点 t 5〜10.5 s と t* の富士の雪・山腹の見える画素（PL30Render の fuji 段の数。S5-2「雪山が富士を隠す」）
  pop    コマ 180〜190 の隣のコマの差（平均の色の差と、差が 40 を超える画素の数）。原画視点・座席から波の方向・左の側面（S5-1 のコマ 184→185 の跳び）
  lines  座席 v1 のコマ 270〜300 の線の 1 コマだけの消え・出（藍の線の色 (71,80,95) ±14 の画素の 10 画素以上の塊が、前後のコマにあって（2 画素ふくらませて）そのコマにない／その逆。
         段階7確認の F7-2 の数え方そのものではなく、同じ考えの簡単な数え（記録））
  stair  座席 v1 のコマ 280 の、右の高い波の稜線の段（S5-3）の場所（x 1787〜1912・y 435〜604）にある、空でない画素の数と、空との境の段の数
  seaid  ID の画像（主役波の印つき）で、主役波でない海の画素（near・far・左奥の船のうねり）の色区の割合。座席から波の方向・座席の t* など（谷の縁の段：藍中の割合）
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
LINE = np.array([71, 80, 95])
SKY_MIN = np.array([200, 190, 150])


def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.int16)


def fuji(d):
    """PL30Render の fuji 段の画像（富士の雪 (255,0,255)、山腹 (r = b, g = 0)）から数え直す（報告の JSON は後の描画で上書きされうるので画像を正とする）。"""
    out = []
    fd = os.path.join(d, "fuji")
    for fn in sorted(os.listdir(fd)):
        if not fn.endswith(".png"):
            continue
        a = np.asarray(Image.open(os.path.join(fd, fn)).convert("RGB")).astype(np.int16)
        snow = int(((a[..., 0] == 255) & (a[..., 1] == 0) & (a[..., 2] == 255)).sum())
        slope = int(((a[..., 1] == 0) & (a[..., 0] == a[..., 2]) & (a[..., 0] > 20) & (a[..., 0] < 200)).sum())
        out.append(dict(t=int(fn.split("_t")[-1][:4]) / 100.0, snow=snow, slope=slope))
    return out


def pop(d):
    out = {}
    for v in ("painting", "seat_toward_wave", "side_left"):
        prev = None
        rows = []
        for i in range(180, 191):
            p = os.path.join(d, "s5", "%s_f%04d.png" % (v, i))
            if not os.path.exists(p):
                continue
            a = load(p)
            if prev is not None:
                dd = np.abs(a - prev).sum(-1)
                rows.append(dict(frame=i, mean=float(dd.mean() / 3.0), px_over40=int((dd > 120).sum())))
            prev = a
        if rows:
            m = [x["mean"] for x in rows]
            k = [x for x in rows if x["frame"] == 185]
            med = float(np.median(m))
            out[v] = dict(rows=rows, f185_mean=k[0]["mean"] if k else None, f185_px=k[0]["px_over40"] if k else None, median_mean=med,
                          f185_over_median=(k[0]["mean"] / med if k and med > 0 else None), max_ratio=float(max(m) / med) if med > 0 else None)
    return out


def line_mask(a):
    return (np.abs(a - LINE[None, None, :]).max(-1) <= 14)


def lines(d, first=270, last=300):
    masks = []
    for i in range(first, last + 1):
        p = os.path.join(d, "s5", "seat_f%04d.png" % i)
        masks.append(line_mask(load(p)))
    st = np.ones((5, 5), bool)
    drop = appear = 0
    drop_px = 0
    per = []
    for k in range(1, len(masks) - 1):
        a, b, c = masks[k - 1], masks[k], masks[k + 1]
        both = ndimage.binary_dilation(a, st) & ndimage.binary_dilation(c, st)
        lab, n = ndimage.label(a & ndimage.binary_dilation(c, st))
        miss = 0
        if n:
            sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
            bd = ndimage.binary_dilation(b, st)
            for j in range(1, n + 1):
                if sizes[j - 1] < 10:
                    continue
                if not (bd & (lab == j)).any():
                    miss += 1; drop_px += int(sizes[j - 1])
        lab2, n2 = ndimage.label(b & ~both)
        app = 0
        if n2:
            sizes2 = ndimage.sum(np.ones_like(lab2), lab2, range(1, n2 + 1))
            app = int((sizes2 >= 10).sum())
        drop += miss; appear += app
        per.append(dict(frame=first + k, drop=miss, appear=app))
    return dict(frames=[first, last], one_frame_drops=drop, one_frame_drop_px=drop_px, one_frame_appears=appear, per_frame=per)


def stair(d, f=280):
    a = load(os.path.join(d, "s5", "seat_f%04d.png" % f))
    reg = a[435:605, 1787:1913]
    sky = (reg[..., 0] >= 225) & (reg[..., 1] >= 210) & (reg[..., 2] >= 170) & (np.abs(reg[..., 0] - 249) < 10) & (np.abs(reg[..., 2] - 196) < 14)
    non = ~sky
    # 各列の空でない画素の最も上の行（稜線）。段：隣の列との差が 3 画素以上の所の数
    top = np.array([np.nonzero(non[:, x])[0].min() if non[:, x].any() else reg.shape[0] for x in range(reg.shape[1])])
    steps = int((np.abs(np.diff(top)) >= 3).sum())
    return dict(frame=f, region=[1787, 435, 1912, 604], non_sky_px=int(non.sum()), skyline_steps_ge3px=steps)


def seaid(d, views=("seat_toward_wave", "seat_low", "seat", "painting"), ts=("060", "090", "105", "120")):
    out = {}
    cols = {"white": (255, 0, 0), "mizuiro": (0, 255, 0), "ai_mid": (0, 0, 255), "ai_dark": (255, 255, 0)}
    for v in views:
        for t in ts:
            p = os.path.join(d, "diag", "%s_t%s_hero_claws0.png" % (v, t))
            if not os.path.exists(p):
                continue
            im = np.asarray(Image.open(p).convert("RGBA")).astype(np.int16)
            hero = im[..., 3] < 200
            rec = {}
            tot = 0
            for k, c in cols.items():
                m = (~hero) & (np.abs(im[..., :3] - np.array(c)).max(-1) <= 2)
                rec[k] = int(m.sum()); tot += rec[k]
            out["%s_t%s" % (v, t)] = dict(sea_px=tot, **{k + "_frac": (rec[k] / tot if tot else None) for k in cols})
    return out


def video_jumps(d):
    """30 fps の動画（t 0〜14 s、960×540）の隣のコマの差の平均を、前後 3 コマの中央値で割った比の最大（1 コマだけの跳び。動画の圧縮を含む記録）。"""
    import cv2
    out = {}
    for v in ("painting", "seat", "seat_toward_wave", "side_left"):
        p = os.path.join(d, "video", "pl30_%s_30fps.mp4" % v)
        if not os.path.exists(p):
            p = os.path.join(d, "video", "pl29_%s_30fps.mp4" % v)
        if not os.path.exists(p):
            continue
        cap = cv2.VideoCapture(p)
        prev = None
        diffs = []
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            g = fr.astype(np.int16)
            if prev is not None:
                diffs.append(float(np.abs(g - prev).mean()))
            prev = g
        cap.release()
        dfs = np.array(diffs)
        ratio = []
        for i in range(3, len(dfs) - 3):
            nb = np.concatenate([dfs[i - 3:i], dfs[i + 1:i + 4]])
            med = float(np.median(nb))
            ratio.append(dfs[i] / med if med > 0.05 else 1.0)
        ratio = np.array(ratio)
        k = int(np.argmax(ratio))
        out[v] = dict(frames=len(dfs) + 1, max_ratio=float(ratio.max()), at_frame=k + 4, n_over_2=int((ratio > 2.0).sum()),
                      f185_ratio=float(ratio[185 - 4]) if len(ratio) > 185 else None)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default="Unity/Build/Polish/30/before")
    ap.add_argument("--after", default="Unity/Build/Polish/30/after_r7")
    ap.add_argument("--out", default="Unity/Build/Polish/30/measure_r7")
    args = ap.parse_args()
    B = os.path.join(REPO, args.before); A = os.path.join(REPO, args.after)
    M = dict(number="仕上げ30", schema="GreatWave.PL30.measure/1", before=args.before, after=args.after, note_ja=__doc__.split("\n\n")[1].strip())
    for nm, fn in (("fuji", fuji), ("pop", pop), ("lines", lines), ("stair", stair), ("seaid", seaid), ("video_jumps", video_jumps)):
        try:
            M[nm] = dict(before=fn(B), after=fn(A))
        except Exception as e:  # noqa: BLE001
            M[nm] = dict(error=repr(e))
        print(nm, json.dumps(M[nm], ensure_ascii=False)[:900])
    os.makedirs(os.path.join(REPO, args.out), exist_ok=True)
    with open(os.path.join(REPO, args.out, "pl30_measure.json"), "w", encoding="utf-8") as f:
        json.dump(M, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
