# -*- coding: utf-8 -*-
"""仕上げ28：F7-1 の切り分けの図（1920×1080 の PNG）。
上段：無圧縮の静止画（Unity、原画視点、F_final ＋ 29修正01 の焼き込み）の続いた 3 コマの切り出しと、真ん中のコマの 1 コマだけの跳び
（画面に固定した画素 c(f−1) = c(f+1) ≠ c(f)、赤）と、面に付いて動く点（頂点）の色の読み（緑＝3 コマで同じ、紫＝跳ぶ）。
下段：数の表（動画の圧縮の有無、面に付いた点と画面に固定した点、形の往復、τ(t) の折れ）。数は pl28_f71_count・pl28_f71_track・pl28_f71_geom の出力から読む。
使い方：py -3.10 -B Tools/GWWaveGen/pl28/pl28_f71_fig.py --stills <PNG のフォルダー> --first 264 --frame 329 --cx 762 --cy 298
    --package <包み> --warp <時間曲線> --dir <出力の JSON のフォルダー> --out <PNG>
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pl28_s7_video as S7  # noqa: E402
import pl28_f71_geom as GM  # noqa: E402

KC = GM.KC
FONT = r"C:\Windows\Fonts\meiryo.ttc"


def F(sz):
    return ImageFont.truetype(FONT, sz)


def jl(p):
    with open(GM.absrepo(p), encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", required=True)
    ap.add_argument("--glob", default="ds29_painting_f*.png")
    ap.add_argument("--first", type=int, required=True)
    ap.add_argument("--frame", type=int, required=True)
    ap.add_argument("--cx", type=int, required=True)
    ap.add_argument("--cy", type=int, required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--warp", required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(GM.absrepo(a.stills), a.glob)))
    k = a.frame - a.first
    ims = [np.asarray(Image.open(files[k + d]).convert("RGB")) for d in (-1, 0, 1)]
    cls = [S7.classify(x) for x in ims]
    fill = lambda c: (c >= 1) & (c <= 4)  # noqa: E731
    flip = fill(cls[0]) & fill(cls[1]) & fill(cls[2]) & (cls[0] == cls[2]) & (cls[1] != cls[0])
    pk = GM.Pkg(a.package)
    Wj = jl(a.warp)
    wt, wtau = np.asarray(Wj["t"], float), np.asarray(Wj["tau"], float)
    P = []
    for d in (-1, 0, 1):
        tau = float(np.interp((a.frame + d) / 30.0, wt, wtau))
        P.append(KC.project_unity(pk.world(tau, fine=True)))
    vis = [GM.visible_mask(p) for p in P]
    white = pk.tw < 1e8
    hw, hh = 160, 100
    x0, y0 = a.cx - hw, a.cy - hh
    x1, y1 = a.cx + hw, a.cy + hh
    sc = 1.6
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((16, 8), "F7-1 の切り分け：t 9〜11.5 s の波頭の模様の 1 コマだけの跳びは、動きの行き戻りでも模様の座標の揺れでもない", fill=(0, 0, 0), font=F(26))
    d.text((16, 46), "Unity の無圧縮の静止画（原画視点、F_final ＋ 29修正01 の焼き込み、コマ %d〜%d、t = %.3f〜%.3f s）。上：そのまま。下：赤＝画面に固定した画素の 1 コマだけの跳び、"
           "点＝面に付いて動く頂点の色（緑 3 コマ同じ、紫 跳ぶ）" % (a.frame - 1, a.frame + 1, (a.frame - 1) / 30, (a.frame + 1) / 30), fill=(60, 60, 60), font=F(16))
    cw = int((x1 - x0) * sc)
    ch = int((y1 - y0) * sc)
    for j in range(3):
        crop = Image.fromarray(ims[j][y0:y1, x0:x1]).resize((cw, ch), Image.NEAREST)
        X = 20 + j * (cw + 20)
        img.paste(crop, (X, 80))
        d.text((X, 80 + ch + 2), "コマ %d（t %.3f s）" % (a.frame - 1 + j, (a.frame - 1 + j) / 30), fill=(0, 0, 0), font=F(16))
        if j == 1:
            ov = ims[1][y0:y1, x0:x1].copy()
            m = flip[y0:y1, x0:x1]
            ov[m] = (230, 20, 20)
            o = Image.fromarray(ov).resize((cw, ch), Image.NEAREST)
            dd = ImageDraw.Draw(o)
            vv = white & vis[0] & vis[1] & vis[2]
            for i in np.nonzero(vv)[0]:
                px, py = P[1][i, 0], P[1][i, 1]
                if not (x0 + 2 <= px < x1 - 2 and y0 + 2 <= py < y1 - 2):
                    continue
                c = []
                for q in range(3):
                    ix, iy = int(round(P[q][i, 0])), int(round(P[q][i, 1]))
                    c.append(int(cls[q][iy, ix]) if (0 <= ix < W and 0 <= iy < H) else 0)
                if not all(1 <= v <= 4 for v in c):
                    continue
                col = (150, 30, 200) if (c[0] == c[2] and c[1] != c[0]) else (20, 170, 60)
                u, v = (px - x0) * sc, (py - y0) * sc
                dd.ellipse([u - 2.5, v - 2.5, u + 2.5, v + 2.5], fill=col)
            img.paste(o, (20, 80 + ch + 30))
            d.text((20, 80 + 2 * ch + 32), "コマ %d の重ね（赤・緑・紫）" % a.frame, fill=(0, 0, 0), font=F(16))
    # 数の表
    cnt_v = jl(os.path.join(a.dir, "count_ds29r01_painting.json"))
    cnt_p = jl(os.path.join(a.dir, "count_F_final_pngseq.json"))
    cnt_r = jl(os.path.join(a.dir, "count_F_final_reenc.json"))
    trk = jl(os.path.join(a.dir, "track_F_final.json"))["windows"]["t9_11p5"]
    geo = jl(os.path.join(a.dir, "geom_F_final.json"))
    gg = [(n, jl(os.path.join(a.dir, "geom_%s.json" % n))) for n in ("G_final",) if os.path.isfile(GM.absrepo(os.path.join(a.dir, "geom_%s.json" % n)))]
    w = lambda c: c["windows_video_frames"]["270_345"]  # noqa: E731
    lines = [
        ("1. 動画の圧縮の分（段階7確認と同じ数え方 M1b、コマ 270〜345 = t 9〜11.5 s の和）", None),
        ("   設計29修正01 の Unity の動画（x264 crf 18）  %d px（1 コマの最大 %d、コマ %d）" % (w(cnt_v)["M1b_sum_px"], w(cnt_v)["M1b_max_px"], w(cnt_v)["M1b_argmax_frame"]), None),
        ("   同じ時刻の無圧縮の静止画                    %d px（最大 %d）" % (w(cnt_p)["M1b_sum_px"], w(cnt_p)["M1b_max_px"]), None),
        ("   その静止画を同じ引数で x264 にしたもの       %d px（最大 %d）  → 跳びの約 %d%% は圧縮が足した分" % (
            w(cnt_r)["M1b_sum_px"], w(cnt_r)["M1b_max_px"], round(100 * (1 - w(cnt_p)["M1b_sum_px"] / max(1, w(cnt_r)["M1b_sum_px"])))), None),
        ("2. 面に付いた点と画面に固定した点（無圧縮、白になる頂点 %d 標本）" % trk["vertex_samples"], None),
        ("   画面に固定した点の跳び  %.2f%%（5×5 が同じ色の内側 %.2f%%）" % (100 * trk["fixed_flip_rate"], 100 * trk["fixed_flip_rate_inner"]), None),
        ("   面に付いて動く点の跳び  %.2f%%（内側 %.3f%%。色の境の画素の丸めの分だけ）" % (100 * trk["tracked_flip_rate"], 100 * trk["tracked_flip_rate_inner"]), None),
        ("   → 模様は面に付いたまま跳ばない。跳びは細かい斑が 1 コマに約 %.1f px 動くことの標本化（30 fps）" % trk["speed_px_p50_median"], None),
        ("3. 形の動き（包み、原画のカメラ、白になる頂点、30 fps のコマ）", None),
    ]
    for nm, gj in [("F_final", geo)] + gg:
        g9 = gj["windows"]["fine"]["t9_11p5"]
        lines.append(("   %s：向きの反転（行き戻り）%d、1 コマの 2 階差分 p99 %.2f px（速さの中央値 %.1f px／コマ）、精度の層の有無で同じ、τ(t) は単調（速さの段の最大 %.3f）" % (
            nm, g9["reversals_sum"], g9["acc_p99_px"]["p99"], g9["speed_p50_px"]["p50"], gj["tau_rate"]["max_step"]), None))
    lines.append(("→ 原因は動き（精度の層・τ(t)）でも焼き込みの模様の座標でもない。描画の標本化（細かい斑の速い移動の 30 fps の標本化）と動画の圧縮。仕上げ29・37 へ", None))
    y = 80 + ch + 34
    for s, _ in lines:
        d.text((20 + cw + 24, y), s, fill=(0, 0, 0), font=F(15))
        y += 26
    os.makedirs(os.path.dirname(GM.absrepo(a.out)), exist_ok=True)
    img.save(GM.absrepo(a.out))
    print("fig", a.out, img.size, "flip px in crop", int(flip[y0:y1, x0:x1].sum()))


if __name__ == "__main__":
    main()
