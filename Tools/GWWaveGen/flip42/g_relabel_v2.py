# -*- coding: utf-8 -*-
"""FLIP42：利用者に出した動画 2 本と断面の並び 1 枚を、印の字だけ直して描き直す（_v2）。2026-10-10。
直す字（独立の確かめ check/R2/check_ja.md の見つけた所 2 から）：
  1. D&K の印：「実験の着水」「D&K の着水」→「D&K の表の着水の値（計算の条件の表）」。
     t_ob・x_ob は Derakhti（2013）の表 3.1「Input parameters for the simulated cases」の値で、測った値とは書かれていない。
  2. この計算の「着水」の印：R3 の 156.0 s は、唇の先が前の面（静かな水面から 5〜7 m）に付いて空気を囲んだ時で、
     噴流の先は静かな水面に届いていない。→「唇が前の面に付いた時（記録の着水）」。
描き方・窓・時刻・数・符号化の設定は g_preview.py・g_video.py のまま（字の辞書 LAB だけを差し替える）。
使い方:
  py -3.10 g_relabel_v2.py v2   <FLIP42 のフォルダー>      → preview/R2_first_side_v2.mp4・preview/R2_first_strip_v2.png・
                                                             R2/R2_side_finest_v2.mp4（R2/video_v2/ に R3_crest.mp4・R3_crest_half.mp4）
  py -3.10 g_relabel_v2.py orig <出力のフォルダー>          → 元の字のまま同じ 3 つを描く（元のファイルとバイト単位で同じかを確かめるため）
"""
import sys, os, shutil, ctypes

sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42")
import g_preview as G
import g_video as V

NEW_G = {"dk_x": "D&K の表の着水の値 584.5 m（計算の条件の表）",
         "dk_t": "D&K の表の着水の値（計算の条件の表）",
         "touch_t": "唇が前の面に付いた時（記録の着水）",
         "touch_panel": "唇が前の面に付いた時・記録の「着水」"}
NEW_V = {"dk_x": NEW_G["dk_x"], "dk_t": NEW_G["dk_t"], "touch_t": NEW_G["touch_t"]}
CREST_LABEL = "完了した中で最も細かい計算（R4 は走らなかった）"  # R2/R2_side_finest.mp4 を描いた時の --label


def below_normal():
    try:  # 計算の邪魔をしないよう、この処理（と ffmpeg）の優先度を「通常より下」にする
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    except Exception:
        pass


def render(side_mp4, strip_png, crest_dir):
    G.side("R3", side_mp4, None, "")
    G.strip(strip_png, ["R3"])
    os.makedirs(crest_dir, exist_ok=True)
    sys.argv = ["g_video.py", "R3", crest_dir, "--label=" + CREST_LABEL, "--only=crest"]
    V.main()


if __name__ == "__main__":
    below_normal()
    mode, base = sys.argv[1], sys.argv[2]
    if mode == "v2":
        G.LAB.update(NEW_G); V.LAB.update(NEW_V)
        render(os.path.join(base, "preview", "R2_first_side_v2.mp4"), os.path.join(base, "preview", "R2_first_strip_v2.png"),
               os.path.join(base, "R2", "video_v2"))
        shutil.copyfile(os.path.join(base, "R2", "video_v2", "R3_crest_half.mp4"), os.path.join(base, "R2", "R2_side_finest_v2.mp4"))
        print("v2 done")
    elif mode == "orig":
        os.makedirs(base, exist_ok=True)
        render(os.path.join(base, "R2_first_side.mp4"), os.path.join(base, "R2_first_strip.png"), os.path.join(base, "video"))
        print("orig done")
