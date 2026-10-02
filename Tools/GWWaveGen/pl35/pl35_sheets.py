# -*- coding: utf-8 -*-
"""仕上げ35：前（仕上げ33修正01 の採る状態の描画、コミット ebcc72c の r_fix01）と後（仕上げ35 の状態の描画）の視点ごとの前後の図・回り台の図と、
プレイヤーの中の前後（--pl35legacy＝仕上げ33修正01 の爪の縁の線の道／修正の回 1 の道）の画面の図を作る。差の画素も数える（記録）。

視点は Q28 の 7 つ（原画視点・座席・座席から波の方向・左右の側面・後ろ 65°・真上）と回り台 12 方位、時刻は t 6・9・10.5・12 s。
描き方は仕上げ33修正01 の r01_run_render.sh と同じ PL33Render（Unity の PC オフスクリーン描画、作品のまま：爪・飛沫・線あり）。
各図は 1920×1080：上の段＝前、中の段＝後、下の段＝差（|後 − 前| の最大の色の差を 8 倍して黒地に表示）。差の数は ΔRGB > 0 と > 8 の画素。
使い方：py -3.10 -B Tools/GWWaveGen/pl35/pl35_sheets.py [--before <描画>] [--after <描画>] [--runs <プレイヤーの走り>] [--out <dir>]
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33")
import pl33_sheets as S  # noqa: E402

TS = [("t060", "t 6 s"), ("t090", "t 9 s"), ("t105", "t 10.5 s"), ("t120", "t 12 s（t*）")]
HB = "前＝仕上げ33修正01（コミット ebcc72c の採る状態。立つ 3D の指の爪 104,707 頂点・飛沫 2,500 粒・PL29/PL30 の材質）"
HA = "後＝仕上げ35（見え方の変更なし。プレイヤーの中の爪の縁の線の写しから配列の写しをなくした修正の回 1 は、この Editor の描画の道を通らない）"


def load(p):
    return np.asarray(Image.open(p).convert("RGB")) if os.path.exists(p) else None


def diff_stats(a, b):
    if a is None or b is None or a.shape != b.shape:
        return None, None
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(-1)
    return {"pixels": int(d.size), "changed_gt0": int((d > 0).sum()), "changed_gt8": int((d > 8).sum()), "max": int(d.max())}, d


def diff_tile(d, size):
    if d is None:
        return None
    im = Image.fromarray(np.clip(d * 8, 0, 255).astype(np.uint8)).convert("RGB")
    return S.fit(im, size)


def view_sheets(a, out, stats):
    files = []
    for v, name in S.VIEWS:
        im = Image.new("RGB", (1920, 1080), (238, 238, 238))
        dr = ImageDraw.Draw(im)
        S.head(dr, "仕上げ35 視点ごとの前後｜%s｜上：前　中：後　下：差（×8）（同じ視点・同じ時刻・作品のまま：爪・飛沫・線あり）" % name,
               "Unity の PC オフスクリーン描画（PL33Render、HMD ではない）。差の数は ΔRGB > 0／> 8 の画素。")
        tw, th = 474, 267
        for k, (ts, tn) in enumerate(TS):
            pb = os.path.join(a.before, "views", "%s_%s_asis.png" % (v, ts))
            pa = os.path.join(a.after, "views", "%s_%s_asis.png" % (v, ts))
            st, d = diff_stats(load(pb), load(pa))
            stats["views/%s/%s" % (v, ts)] = st
            x = 4 + k * (tw + 4)
            for si, (lab, p) in enumerate([("前", pb), ("後", pa)]):
                y = 66 + si * (th + 3)
                t = S.tile(p, (tw, th))
                if t is not None:
                    im.paste(t, (x, y))
                S.label(dr, x + 4, y + 4, "%s｜%s" % (lab, tn))
            y = 66 + 2 * (th + 3)
            t = diff_tile(d, (tw, th))
            if t is not None:
                im.paste(t, (x, y))
            S.label(dr, x + 4, y + 4, "差｜%s｜>0：%s px・>8：%s px" % (tn, st["changed_gt0"] if st else "—", st["changed_gt8"] if st else "—"))
        f = S.font(15)
        y = 66 + 3 * (th + 3) + 6
        for para in (HB + "。", HA + "。"):
            for ln in S.wrap(dr, para, 1890, f):
                dr.text((14, y), ln, fill=(40, 48, 64), font=f)
                y += 21
        p = os.path.join(out, "fig_pl35_ba_view_%s.png" % v)
        im.save(p)
        files.append(p)
    return files


def turntable(a, out, stats):
    files = []
    for ts, tn in TS:
        im = Image.new("RGB", (1920, 1080), (238, 238, 238))
        dr = ImageDraw.Draw(im)
        S.head(dr, "仕上げ35 回り台｜%s｜方位ごとに上：前（仕上げ33修正01）　下：後（仕上げ35）（爪・飛沫・線あり、周りの海を含む）" % tn,
               "回り台：中心 O(t)+(0,9,0)、半径 72 m、仰角 16°、縦の画角 34°、原画視点の向きから 30° ごと（仕上げ29〜33 と同じ）。ラベルの数は差の画素（ΔRGB > 0）。")
        tw, th = 316, 178
        for k in range(12):
            az = k * 30
            col, blk = k % 6, k // 6
            pb = os.path.join(a.before, "tt", "%s_az%03d_claws.png" % (ts, az))
            pa = os.path.join(a.after, "tt", "%s_az%03d_claws.png" % (ts, az))
            st, _ = diff_stats(load(pb), load(pa))
            stats["tt/%s/az%03d" % (ts, az)] = st
            for si, (lab, p) in enumerate([("前", pb), ("後", pa)]):
                x, y = 4 + col * (tw + 4), 66 + blk * (2 * th + 30) + si * (th + 2)
                t = S.tile(p, (tw, th))
                if t is not None:
                    im.paste(t, (x, y))
                S.label(dr, x + 3, y + 3, "%s｜方位 %d°%s" % (lab, az, ("｜差 %d px" % st["changed_gt0"]) if (st and si == 1) else ""), 12)
        p = os.path.join(out, "fig_pl35_ba_turntable_%s.png" % ts)
        im.save(p)
        files.append(p)
    return files


def player_sheet(a, out, stats):
    """プレイヤーの中の前（--pl35legacy）と後（修正の回 1）：PL35PerfProbe が測定の後に t = 11.95 s で撮った画面。"""
    conds = [("exp_hmd", "体験の PC の画面（HMD Camera）"), ("desk1080_painting", "原画視点"), ("desk1080_seat", "座席 v1"), ("proxy_stereo_hmd_L", "立体の代理 左眼")]
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    dr = ImageDraw.Draw(im)
    S.head(dr, "仕上げ35 修正の回 1 のプレイヤーの中の前後｜上：前（--pl35legacy、仕上げ33修正01 の道）　中：後（PL35ClawOutlineFast）　下：差（×8）",
           "Release のプレイヤー（RTX 3080、1920×1080 の窓）、PL35PerfProbe が t = 11.95 s で止めて撮った画面。HMD ではない。")
    tw, th = 474, 267
    for k, (c, cj) in enumerate(conds):
        name = c.replace("_L", "")
        suf = "_L" if c.endswith("_L") else ""
        pb = os.path.join(a.runs, a.legacy_tag, "pl35perf_%s_%s%s.png" % (a.legacy_tag, name, suf))
        pa = os.path.join(a.runs, a.fast_tag, "pl35perf_%s_%s%s.png" % (a.fast_tag, name, suf))
        st, d = diff_stats(load(pb), load(pa))
        stats["player/%s" % c] = st
        x = 4 + k * (tw + 4)
        for si, (lab, p) in enumerate([("前", pb), ("後", pa)]):
            y = 66 + si * (th + 3)
            t = S.tile(p, (tw, th))
            if t is not None:
                im.paste(t, (x, y))
            S.label(dr, x + 4, y + 4, "%s｜%s" % (lab, cj))
        y = 66 + 2 * (th + 3)
        t = diff_tile(d, (tw, th))
        if t is not None:
            im.paste(t, (x, y))
        S.label(dr, x + 4, y + 4, "差｜>0：%s px・>8：%s px" % (st["changed_gt0"] if st else "—", st["changed_gt8"] if st else "—"))
    # 同じ道どうしの走りの差（前どうし・後どうし）：HMD Camera は座席の船に乗るので、船の物理（導入の実時間の歩み）で走りごとに少し動く
    f = S.font(15)
    y = 66 + 3 * (th + 3) + 6
    lines = []
    for c, cj in conds:
        name = c.replace("_L", ""); suf = "_L" if c.endswith("_L") else ""
        same = []
        for t1, t2 in ((a.legacy_tag, a.legacy_tag2), (a.fast_tag, a.fast_tag2)):
            st2, _ = diff_stats(load(os.path.join(a.runs, t1, "pl35perf_%s_%s%s.png" % (t1, name, suf))), load(os.path.join(a.runs, t2, "pl35perf_%s_%s%s.png" % (t2, name, suf))))
            stats["player_same_path/%s/%s_vs_%s" % (c, t1, t2)] = st2
            same.append(str(st2["changed_gt0"]) if st2 else "—")
        lines.append("%s：前どうし %s px・後どうし %s px" % (cj, same[0], same[1]))
    for para in ("同じ道の 2 回の走りどうしの差（ΔRGB > 0）＝ " + "、".join(lines) + "。固定のカメラの原画視点は前後も走りどうしも 0 px。HMD Camera と座席 v1 の差は、"
                 "座席の船（とそれに乗る HMD Camera）の姿勢が走りごとに少し違うためで、前と後の差と同じ大きさ。線のメッシュそのものは同じ時刻で頂点・法線の差 0（PL35ClawOutlineFast.SelfCheck、5 時刻）。",):
        for ln in S.wrap(dr, para, 1890, f):
            dr.text((14, y), ln, fill=(40, 48, 64), font=f)
            y += 21
    p = os.path.join(out, "fig_pl35_ba_player_t1195.png")
    im.save(p)
    return [p]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default=REPO + "/Unity/Build/Polish/33r01/fix01/r_fix01")
    ap.add_argument("--after", default=REPO + "/Unity/Build/Polish/35/r_after")
    ap.add_argument("--runs", default=REPO + "/Unity/Build/Polish/35/runs")
    ap.add_argument("--fast-tag", default="f1_fast1")
    ap.add_argument("--legacy-tag", default="f1_legacy1")
    ap.add_argument("--fast-tag2", default="f1_fast2")
    ap.add_argument("--legacy-tag2", default="f1_legacy2")
    ap.add_argument("--out", default=REPO + "/Unity/Build/Polish/35/evidence")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    stats = {}
    fs = view_sheets(a, a.out, stats) + turntable(a, a.out, stats) + player_sheet(a, a.out, stats)
    with open(os.path.join(a.out, "pl35_sheet_diffs.json"), "w", encoding="utf-8") as f:
        json.dump({"rule_ja": __doc__.strip().split("\n\n")[1], "before": a.before, "after": a.after, "stats": stats}, f, ensure_ascii=False, indent=1)
    for f in fs:
        print(f, os.path.getsize(f))
    tot = [v for k, v in stats.items() if v and not k.startswith("player")]
    print("editor views+tt:", len(tot), "images, changed>0 total", sum(v["changed_gt0"] for v in tot), "max", max([v["max"] for v in tot] or [0]))
    for k, v in stats.items():
        if k.startswith("player"):
            print(k, v)


if __name__ == "__main__":
    main()
