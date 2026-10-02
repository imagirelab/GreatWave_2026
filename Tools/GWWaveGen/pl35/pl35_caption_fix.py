# -*- coding: utf-8 -*-
"""仕上げ35（F6-4 の直し）：設計35 の 2×2 の動画（原画視点・座席 v1）の説明の「最初の爪 3.6 s」を直した版を作る。

設計35 の 2×2 の動画の右下の説明は、各版の「最初の爪」をデータの時刻（爪が根元から伸び始めるコマ）で書いていた。V3 の 3.6 s は、
動画ではその時刻に爪が画面の外にあり、画面で V1 と違って見え始めるのはずっと後（段階6確認 F6-4、設計35 §5 の 1）。
この道具は、設計35 の元の動画（Git 対象外の Unity/Build/Design/35/variants/video_raw。作り直さない）から、V2・V3 が V1 と
初めて 50 画素以上違うコマ（ΔRGB > 40。設計35 の記録の数え直しと同じ読み）を数え直し、説明を
「データの最初の爪 x.x s（伸び始め）／この視点の画面で V1 と違って見え始める y.y s」の 2 つに分けて書いた 2×2 の動画を作る。
動画の中身（3 版の描画）と並べ方・速さ（30 fps・421 コマ）は設計35 と同じ。設計35 の証拠（Docs/Evidence/Design/35）は書き換えない。
出力：--out（既定 Unity/Build/Polish/35/caption）に pl35_ds35_2x2_<視点>_30fps.mp4 と pl35_caption_fix.json。
使い方：py -3.10 -B Tools/GWWaveGen/pl35/pl35_caption_fix.py
"""
import argparse
import json
import os
import subprocess
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds35")
import ds35_variants_evidence as E  # noqa: E402  道具（text_img・wr・font・VJA・VARS・FFMPEG）だけを使う

VR = REPO + "/Unity/Build/Design/35/variants/video_raw"
MET = REPO + "/Docs/Evidence/Design/35/ds35_variants_metrics.json"
FPS = 30.0


def frames(path):
    cap = cv2.VideoCapture(path)
    while True:
        ok, f = cap.read()
        if not ok:
            break
        yield f
    cap.release()


def onset(view):
    """V2・V3 が V1 と初めて 50 画素以上（ΔRGB > 40）違うコマの時刻と、各版の違いの画素の時間の列。"""
    gens = {v: frames(os.path.join(VR, "ds35_%s_%s_30fps.mp4" % (v, view))) for v in E.VARS}
    first = {"v2_light": None, "v3_exag": None}
    k = 0
    while True:
        try:
            fr = {v: next(g).astype(np.int16) for v, g in gens.items()}
        except StopIteration:
            break
        for v in ("v2_light", "v3_exag"):
            if first[v] is None and int((np.abs(fr[v] - fr["v1_list"]).max(-1) > 40).sum()) >= 50:
                first[v] = round(k / FPS, 3)
        k += 1
    return first, k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=REPO + "/Unity/Build/Polish/35/caption")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    tmp = a.out + "/_work"
    os.makedirs(tmp, exist_ok=True)
    met = E.jload(MET)
    den = met["variants"]
    res = {"rule_ja": __doc__.strip().split("\n\n")[1], "inputs": {}, "views": {}}
    on = {}
    for view in ("painting", "painting_w0", "seat"):
        f, n = onset(view)
        on[view] = f
        res["views"][view] = {"first_diff_vs_v1_s": f, "frames": n}
    enc = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    vids = []
    for view in ("painting", "seat"):
        leg = np.full((540, 960, 3), (196, 232, 249), np.uint8)
        vja = "原画視点" if view == "painting" else "座席 v1"
        items = [(24, 14, "設計35：数量・大きさ・寿命の 3 版（%s）［仕上げ35 で説明を直した］" % vja, 25, True, (0, 0, 0), 0)]
        yy = 62
        for v in E.VARS:
            d = den[v]
            items.append((24, yy, E.VJA[v], 22, True, (0, 0, 0), 0)); yy += 30
            items.append((44, yy, "爪 %d 本（%d 三角形）・飛沫 %d 個" % (d["claws"], d["claw_triangles"], d["spray_count"]), 18, False, (0, 0, 0), 0)); yy += 26
            s = "データの最初の爪 %.1f s（根元から伸び始めるコマ）・最初の飛沫 %.1f s" % (d["first_claw_s"], d["first_spray_s"])
            items.append((44, yy, s, 18, False, (0, 0, 0), 0)); yy += 26
            if v != "v1_list":
                t = on[view][v]
                s2 = "この視点の画面で V1 と違って見え始める：%s" % ("%.1f s" % t if t is not None else "最後まで違わない")
                items.append((44, yy, s2, 18, True, (150, 20, 20), 0)); yy += 26
        note = ("V3 の爪は 3.6 s から伸び始めるが、伸びる所は約 6.4 s まで画面の外。" if view == "painting" else
                "V3 の爪は 3.6 s から伸び始めるが、座席の画面で違いが見えるのは %.1f s から。" % on[view]["v3_exag"])
        items.append((24, yy + 4, note, 18, False, (0, 0, 0), 0)); yy += 26
        items.append((24, yy + 4, "違って見え始める時刻＝元の動画で V1 と ΔRGB > 40 の画素が初めて 50 以上になるコマ（設計35 §2.3 と同じ読み）", 15, False, (60, 60, 60), 0)); yy += 22
        items.append((24, yy + 4, "V3：爪の幅 ×1.5・長さ ×1.3・成長の始まり ×1.6、飛沫の半径 ×1.6・放出を早める。D2＝(b) なので物理版はない", 15, False, (60, 60, 60), 0)); yy += 22
        items.append((24, yy + 4, "描画は設計35（2026-09-30）のまま。性能は仕上げ35 の記録（Polish_35_ja.md）で測り直した", 15, False, (60, 60, 60), 0))
        legp = E.wr(tmp + "/legend_%s.png" % view, E.text_img(leg, items))
        ov = E.overlay_png(tmp + "/ov_2x2_%s.png" % view, [(12, 8, E.VJA["v1_list"], 26), (972, 8, E.VJA["v2_light"], 26), (12, 548, E.VJA["v3_exag"], 26)])
        ins = [os.path.join(VR, "ds35_%s_%s_30fps.mp4" % (v, view)) for v in E.VARS]
        for p in ins:
            res["inputs"][os.path.basename(p)] = {"bytes": os.path.getsize(p), "sha256": E.sha(p)}
        fc = ("[0:v]scale=960:540[a];[1:v]scale=960:540[b];[2:v]scale=960:540[c];[3:v]scale=960:540[d];"
              "[a][b]hstack[t];[c][d]hstack[u];[t][u]vstack[g];[g][4:v]overlay=0:0[v]")
        o = os.path.join(a.out, "pl35_ds35_2x2_%s_30fps.mp4" % view)
        subprocess.run([E.FFMPEG, "-y", "-loglevel", "error"] + sum([["-i", p] for p in ins], []) + ["-loop", "1", "-framerate", "30", "-i", legp, "-loop", "1", "-framerate", "30", "-i", ov,
                        "-filter_complex", fc, "-map", "[v]", "-r", "30", "-frames:v", "421"] + enc + [o], check=True)
        # 説明の静止画（記録の図）：t 6.0・6.5・10 s のコマ
        res.setdefault("outputs", {})[os.path.basename(o)] = {"bytes": os.path.getsize(o), "sha256": E.sha(o)}
        vids.append(o)
        E.wr(os.path.join(a.out, "pl35_ds35_2x2_%s_legend.png" % view), cv2.imread(legp))
    E.jdump(os.path.join(a.out, "pl35_caption_fix.json"), res)
    print(json.dumps(res["views"], ensure_ascii=False))
    for v in vids:
        print(v, os.path.getsize(v))


if __name__ == "__main__":
    main()
