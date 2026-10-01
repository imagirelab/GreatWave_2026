# -*- coding: utf-8 -*-
# 仕上げ28：段階7確認（自己評審）で F7-1 を数えた台本（Git 対象外の Unity/Build/Design/40/stage7_review/s7_video.py、SHA-256 ee068b15…、
# s7_checks.json の code_sha256 と同じ）を、中身を変えずにリポジトリへ写したもの。数え方を同じにするため、pl28_f71_count.py がこれを import する。

"""段階7確認（自己評審）：動画の中で色面と藍の線が泳がない・点滅しない・這わないかを、Unity の出力の動画から自分のコードで数える。

設計36〜40 の作る部・検査・記録のコードは使わない（読みの言葉だけを設計36 の記録 §2.6 に合わせ、比べられるようにした）。

数えるもの（動画ごと、コマ f = 1..N-2）：
  M1 色面の 1 コマだけの跳び：960x540 に縮め（INTER_AREA）、調色板の 5 色（白・淡い水色・藍中・藍濃・藍の線）の最も近い色へ分けた
     （距離 > 30 は「その他」）。c(f-1) == c(f+1) != c(f) の画素のうち、3x3 に 4 画素以上まとまったもの。
  M1b 塗りの色面だけの跳び（M1 は線の縁のアンチエイリアスと動画の圧縮で膨らむので、こちらを主に読む）：前・そのコマ・後の 3 コマとも
     塗りの 4 色（白・淡い水色・藍中・藍濃）で、3 コマのどれかの「その他」「藍の線」から 1 画素（960x540）より離れた画素の c(f-1) == c(f+1) != c(f)。
     8 近傍の塊で、4 画素以上の画素の数と、20 画素以上（全解像度で約 9x9 px 以上）の塊の数と画素の数。
  M2 藍の線の 1 コマだけの消え・出：1920x1080 のまま、藍の線の色 (71,80,95) に近く（距離 <= 24）、藍濃・藍中より線の色に近い画素を線とする。
     消え：L(f-1) & L(f+1) & ~膨張1(L(f))、出：L(f) & ~膨張2(L(f-1)) & ~膨張2(L(f+1))。8 近傍で 10 画素以上の塊。
  M3 変わった画素（M1 の分類で c(f) != c(f-1)）の数と、前後 6 コマの中央値に対する比（跳びの探し）。
  M4 t* の後の静止（コマ 362〜420）：全解像度で、どれかのチャンネルが 8 段より大きく違う画素の数の最大。
使い方：py -3.10 -B s7_video.py [動画の名前 ...]（出力 vid_<名前>.json と、各動画のコマごとの値 per_frame_<名前>.npz）
"""
import hashlib
import json
import os
import subprocess
import sys
import time

import cv2
import numpy as np

FF = r"G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
B = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design"
OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/40/stage7_review"
PAL = np.array([[248, 243, 223], [198, 215, 203], [44, 105, 147], [35, 64, 97], [71, 80, 95]], np.float32)
PAL_NAMES = ["その他", "白", "淡い水色", "藍中", "藍濃", "藍の線"]
LINE = np.array([71, 80, 95], np.float32)

VIDEOS = {
    # 段階7 の始め（設計36）
    "ds36_painting": B + "/36/palette/unity/video/ds36_palette_painting_30fps.mp4",
    "ds36_seat": B + "/36/palette/unity/video/ds36_palette_seat_30fps.mp4",
    "ds36_seat_toward_wave": B + "/36/palette/unity/video/ds36_palette_seat_toward_wave_30fps.mp4",
    # 段階7 の終わりの既定（設計38 の修正の回 = 設計39 の全部切 = 設計40）
    "ds38_painting": B + "/38/outlines/unity/video/ds38_formation_painting_30fps.mp4",
    "ds38_seat": B + "/38/outlines/unity/video/ds38_formation_seat_30fps.mp4",
    "ds38_seat_toward_wave": B + "/38/outlines/unity/video/ds38_formation_seat_toward_wave_30fps.mp4",
    # 設計38 の修正1（修正の回の前。扇の線の比べ）
    # 設計39 の全部入（①②③）
    "ds39all_painting": B + "/39/paper/unity/video/ds39_formation_painting_all_30fps.mp4",
    "ds39all_seat": B + "/39/paper/unity/video/ds39_formation_seat_all_30fps.mp4",
    # 頭の揺れ（時刻は止めて目を ±0.1 m）
    "ds37_sway_toward_wave_t09": B + "/37/flowlines/unity/video/ds37_sway_seat_toward_wave_t09_30fps.mp4",
    "ds38_sway_toward_wave_t09": B + "/38/outlines/unity/video/ds38_sway_seat_toward_wave_t09_30fps.mp4",
    "ds39all_sway_toward_wave_t09": B + "/39/paper/unity/video/ds39_sway_seat_toward_wave_t09_all_30fps.mp4",
    "ds39all_sway_tstar": B + "/39/paper/unity/video/ds39_sway_seat_tstar_all_30fps.mp4",
}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def frames(path, w=1920, h=1080):
    p = subprocess.Popen([FF, "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, bufsize=1 << 26)
    n = w * h * 3
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, np.uint8).reshape(h, w, 3)
    p.stdout.close()
    p.wait()


def classify(small):
    x = small.astype(np.float32)
    d = ((x[:, :, None, :] - PAL[None, None]) ** 2).sum(-1)
    k = d.argmin(-1)
    m = d.min(-1)
    c = (k + 1).astype(np.uint8)
    c[m > 30.0 ** 2] = 0
    return c


def line_mask(fr):
    x = fr.astype(np.float32)
    dl = ((x - LINE) ** 2).sum(-1)
    dd = ((x - PAL[3]) ** 2).sum(-1)
    dm = ((x - PAL[2]) ** 2).sum(-1)
    return (dl <= 24.0 ** 2) & (dl < dd) & (dl < dm)


K3 = np.ones((3, 3), np.uint8)
K5 = np.ones((5, 5), np.uint8)


def clusters(mask, minsize):
    n, lab, st, cen = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    out = []
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] >= minsize:
            out.append((int(st[i, cv2.CC_STAT_AREA]), float(cen[i, 0]), float(cen[i, 1])))
    return out


def analyse(name, path):
    t0 = time.time()
    cls, lines, full_prev = [], [], None
    static_diff = []
    n = 0
    fl_px, fl_pairs, chg = [], [], []
    fb_px, fb_big_px, fb_big_n, fb_list = [], [], [], []
    loff, lon, loff_list, lon_list = [], [], [], []
    for i, fr in enumerate(frames(path)):
        small = cv2.resize(fr, (960, 540), interpolation=cv2.INTER_AREA)
        cls.append(classify(small))
        lines.append(line_mask(fr))
        if full_prev is not None:
            static_diff.append(int((np.abs(fr.astype(np.int16) - full_prev.astype(np.int16)).max(-1) > 8).sum()))
            chg.append(int((cls[-1] != cls[-2]).sum()))
        else:
            chg.append(0)
        full_prev = fr
        if len(cls) == 3:
            a, b, c = cls
            m = (a == c) & (b != a)
            nb = cv2.filter2D(m.astype(np.uint8), -1, K3, borderType=cv2.BORDER_CONSTANT)
            mm = m & (nb >= 4)
            fl_px.append(int(mm.sum()))
            if mm.any():
                pr = np.stack([a[mm], b[mm]], 1)
                u, cnt = np.unique(pr[:, 0].astype(np.int32) * 10 + pr[:, 1], return_counts=True)
                fl_pairs.append({int(k): int(v) for k, v in zip(u, cnt)})
            else:
                fl_pairs.append({})
            fill = lambda q: (q >= 1) & (q <= 4)
            edge = (a == 0) | (a == 5) | (b == 0) | (b == 5) | (c == 0) | (c == 5)
            edge = cv2.dilate(edge.astype(np.uint8), K3).astype(bool)
            mb = (a == c) & (b != a) & fill(a) & fill(b) & ~edge
            nb_, lab_, st_, cen_ = cv2.connectedComponentsWithStats(mb.astype(np.uint8), connectivity=8)
            ar = st_[1:, cv2.CC_STAT_AREA]
            fb_px.append(int(ar[ar >= 4].sum()))
            fb_big_px.append(int(ar[ar >= 20].sum()))
            fb_big_n.append(int((ar >= 20).sum()))
            for q in np.nonzero(ar >= 20)[0] + 1:
                pa = int(np.bincount((a[lab_ == q].astype(np.int32) * 10 + b[lab_ == q]).ravel()).argmax())
                fb_list.append((i - 1, int(st_[q, cv2.CC_STAT_AREA]), float(cen_[q, 0] * 2), float(cen_[q, 1] * 2), pa))
            la, lb, lc = lines
            off = la & lc & ~cv2.dilate(lb.astype(np.uint8), K3).astype(bool)
            on = lb & ~cv2.dilate(la.astype(np.uint8), K5).astype(bool) & ~cv2.dilate(lc.astype(np.uint8), K5).astype(bool)
            co, cn = clusters(off, 10), clusters(on, 10)
            f = i - 1
            loff.append(len(co))
            lon.append(len(cn))
            loff_list += [(f,) + x for x in co]
            lon_list += [(f,) + x for x in cn]
            cls.pop(0)
            lines.pop(0)
        n = i + 1
    fl_px = np.array([0] + fl_px + [0])
    fb_px = np.array([0] + fb_px + [0])
    fb_big_px = np.array([0] + fb_big_px + [0])
    fb_big_n = np.array([0] + fb_big_n + [0])
    loff = np.array([0] + loff + [0])
    lon = np.array([0] + lon + [0])
    chg = np.array(chg)
    ratio = np.zeros(n)
    for f in range(1, n):
        nbr = [chg[g] for g in range(max(1, f - 6), min(n, f + 7)) if g != f]
        med = float(np.median(nbr)) if nbr else 0.0
        ratio[f] = chg[f] / med if med > 0 else (0.0 if chg[f] == 0 else np.inf)
    np.savez_compressed(os.path.join(OUT, "per_frame_" + name + ".npz"), fl_px=fl_px, fb_px=fb_px, fb_big_px=fb_big_px, fb_big_n=fb_big_n, loff=loff, lon=lon, chg=chg, ratio=ratio,
                        static_diff=np.array([0] + static_diff))
    res = {"path": path.replace(B, "Unity/Build/Design"), "sha256": sha256(path), "frames": n, "seconds": round(time.time() - t0, 1)}

    def window(lo, hi):
        lo, hi = max(1, lo), min(n - 2, hi)
        if hi < lo:
            return None
        s = slice(lo, hi + 1)
        fp = fl_px[s]
        pairs = {}
        for d in fl_pairs[lo - 1:hi]:
            for k, v in d.items():
                pairs[k] = pairs.get(k, 0) + v
        top = sorted(pairs.items(), key=lambda kv: -kv[1])[:6]
        rr = ratio[s]
        rr = rr[np.isfinite(rr)]
        return {"frames": [lo, hi],
                "M1_colour_flicker": {"max_px": int(fp.max()), "argmax_frame": int(lo + fp.argmax()), "sum_px": int(fp.sum()),
                                      "frames_over_50px": int((fp > 50).sum()), "frames_over_200px": int((fp > 200).sum()),
                                      "p95_px": float(np.percentile(fp, 95)),
                                      "top_class_pairs_ja": [{"前後": PAL_NAMES[k // 10], "そのコマ": PAL_NAMES[k % 10], "px": v} for k, v in top]},
                "M1b_fill_flicker": {"max_px": int(fb_px[s].max()), "argmax_frame": int(lo + fb_px[s].argmax()), "sum_px": int(fb_px[s].sum()),
                                     "frames_over_50px": int((fb_px[s] > 50).sum()), "big_blobs_ge20": int(fb_big_n[s].sum()), "big_blob_px": int(fb_big_px[s].sum()),
                                     "frames_with_big_blob": int((fb_big_n[s] > 0).sum()), "max_big_blob_px_in_frame": int(fb_big_px[s].max())},
                "M2_line_blink": {"off_clusters": int(loff[s].sum()), "on_clusters": int(lon[s].sum()),
                                  "frames_with_off": int((loff[s] > 0).sum()), "frames_with_on": int((lon[s] > 0).sum()),
                                  "max_off_in_frame": int(loff[s].max()), "max_on_in_frame": int(lon[s].max())},
                "M3_change_ratio": {"max": float(rr.max()) if rr.size else None, "argmax_frame": int(lo + np.nanargmax(np.where(np.isfinite(ratio[s]), ratio[s], -1))),
                                    "frames_ratio_over_2": int((rr > 2).sum())}}
    if n >= 400:
        res["t2_12"] = window(60, 360)
        res["t0_2"] = window(1, 59)
        res["static_after_tstar"] = {"frames": [362, n - 1], "max_changed_px_fullres": int(max(static_diff[361:n - 1])) if n > 362 else None,
                                     "M1_sum_px": int(fl_px[362:n - 1].sum()), "M1b_sum_px": int(fb_px[362:n - 1].sum()), "M2_off_on": [int(loff[362:n - 1].sum()), int(lon[362:n - 1].sum())]}
    else:
        res["all"] = window(1, n - 2)
    fb_list.sort(key=lambda x: -x[1])
    res["M1b_biggest_blobs"] = [{"frame": a, "px_960": b, "x": round(c, 1), "y": round(d, 1), "前後": PAL_NAMES[e // 10], "そのコマ": PAL_NAMES[e % 10]} for a, b, c, d, e in fb_list[:15]]
    res["M1b_blobs_all"] = [[a, b, round(c), round(d), e] for a, b, c, d, e in fb_list]
    loff_list.sort(key=lambda x: -x[1])
    lon_list.sort(key=lambda x: -x[1])
    res["M2_biggest_off"] = [{"frame": a, "px": b, "x": round(c * 1, 1), "y": round(d, 1)} for a, b, c, d in loff_list[:12]]
    res["M2_biggest_on"] = [{"frame": a, "px": b, "x": round(c, 1), "y": round(d, 1)} for a, b, c, d in lon_list[:12]]
    return res


def main():
    only = sys.argv[1:]
    for k, p in VIDEOS.items():
        if only and k not in only:
            continue
        r = analyse(k, p)
        r["code_sha256"] = sha256(os.path.abspath(__file__))
        with open(os.path.join(OUT, "vid_" + k + ".json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(r, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print(k, "done", r["seconds"], flush=True)


if __name__ == "__main__":
    main()
