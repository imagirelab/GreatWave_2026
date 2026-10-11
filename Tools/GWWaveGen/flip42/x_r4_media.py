# -*- coding: utf-8 -*-
"""FLIP42 R4 の段：R4（R4d、粒子 0.1767578125 m）の動画・断面の並び・図を、R2 の段と同じ道具で描く（py -3.10）。2026-10-10 に足した。
描き方・窓・時刻・符号化は g_video.py・g_preview.py・g_figs.py・g_figs2.py のまま。字の印だけを差し替える：
  - D&K の印は「D&K の表の着水の値（計算の条件の表）」（g_relabel_v2.py と同じ字。t_ob・x_ob は Derakhti 2013 の表 3.1
    「Input parameters for the simulated cases」の値で、測った値とは書かれていない）。図（g_figs.py）の「D&K の着水」も同じ字に替える。
  - この計算の「着水」の印は、引数 --touch=<字> で与える（R4d の着水の起こり方を見てから決める）。
使い方:
  py -3.10 x_r4_media.py video  <FLIP42 のフォルダー> [--touch=<字>]   → R4/video/R4d_crest.mp4・R4d_crest_half.mp4、R4/R4_side_finest.mp4（= crest_half の写し）
  py -3.10 x_r4_media.py side   <FLIP42 のフォルダー> [--touch=<字>]   → R4/R4_first_side.mp4（広い窓と頂の周り、preview/R2_first_side と同じ形）
  py -3.10 x_r4_media.py strip  <FLIP42 のフォルダー> [--touch=<字>]   → R4/R4_first_strip.png（R4d）、R4/figs/c_strip_R3_R4d.png（R3 と R4d）
  py -3.10 x_r4_media.py figs   <FLIP42 のフォルダー>                  → R4/figs/（g_figs の R3・R4d、g_figs2 の R2・R3・R4d）
  --rid=<run_id>：道具の試しで別の計算を描く時だけ（出力は <フォルダー>/R4/ の下）
"""
import sys, os, shutil, ctypes

sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42")
import g_preview as G
import g_video as V

DK_T = "D&K の表の着水の値（計算の条件の表）"
DK_X = "D&K の表の着水の値 584.5 m（計算の条件の表）"
CREST_LABEL = "完了した中で最も細かい計算（R4、粒子 0.1767578125 m）"
RID = "R4d"


def below_normal():
    try:  # 計算の邪魔をしないよう、この処理（と子の ffmpeg）の優先度を「通常より下」にする
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    except Exception:
        pass


def labels(touch):
    G.LAB.update({"dk_x": DK_X, "dk_t": DK_T, "touch_t": touch, "touch_panel": touch})
    V.LAB.update({"dk_x": DK_X, "dk_t": DK_T, "touch_t": touch})


def relabel_figs():
    import g_plot as GP
    def fix(s):
        if isinstance(s, str):
            s = s.replace("D&K の着水（584.5 m・159.3 s）", "D&K の表の着水の値（584.5 m・159.3 s、計算の条件の表）")
            s = s.replace("D&K の着水 584.5 m", DK_X).replace("D&K の着水の時刻 159.3 s", DK_T + "の時刻 159.3 s")
        return s
    for cls, meth in ((GP.Ax, "points"), (GP.Ax, "rings"), (GP.Ax, "line")):
        f0 = getattr(cls, meth)
        def wrap(self, *a, _f0=f0, **k):
            if "label" in k:
                k["label"] = fix(k["label"])
            return _f0(self, *a, **k)
        setattr(cls, meth, wrap)
    v0 = GP.Ax.vline
    def vline(self, x, col=(120, 120, 120), label=None, _v0=v0):
        # 縦の線の字は線の上の端に書かれ、近い線（484 m と 584.5 m）で字が重なるので、凡例に回す（線は同じ）
        _v0(self, x, col=col, label=None)
        if label:
            self.leg.append((fix(label), col, False))
    GP.Ax.vline = vline
    t0 = GP.Sheet.text
    def text(self, xy, s, *a, _t0=t0, **k):
        if isinstance(s, str) and s.startswith("縦の線：緑＝D&K の着水の時刻") and xy[1] >= 950:
            xy = (xy[0], xy[1] + 22)   # 字が長くなり x 軸の名前と重なるので、少し下へ
        return _t0(self, xy, fix(s), *a, **k)
    GP.Sheet.text = text


if __name__ == "__main__":
    below_normal()
    mode, base = sys.argv[1], sys.argv[2]
    opt = dict(q[2:].split("=", 1) for q in sys.argv[3:] if q.startswith("--"))
    labels(opt.get("touch", "着水"))
    RID = opt.get("rid", RID)   # 道具の試し用（既定は R4d）
    r4 = os.path.join(base, "R4")
    if mode == "video":
        vd = os.path.join(r4, "video")
        os.makedirs(vd, exist_ok=True)
        sys.argv = ["g_video.py", RID, vd, "--label=" + CREST_LABEL, "--only=crest"]
        V.main()
        shutil.copyfile(os.path.join(vd, RID + "_crest_half.mp4"), os.path.join(r4, "R4_side_finest.mp4"))
    elif mode == "side":
        G.side(RID, os.path.join(r4, "R4_first_side.mp4"), None, "")
    elif mode == "strip":
        os.makedirs(os.path.join(r4, "figs"), exist_ok=True)
        G.strip(os.path.join(r4, "R4_first_strip.png"), [RID])
        G.strip(os.path.join(r4, "figs", "c_strip_R3_R4d.png"), ["R3", RID])
    elif mode == "figs":
        relabel_figs()
        import g_analyze as A
        import g_figs as F
        import g_figs2 as F2
        out = os.path.join(r4, "figs")
        os.makedirs(out, exist_ok=True)
        P = A.plan(); C = A.comps_full(P)
        rids = ["R3", RID]
        F.fig_xt(out, RID, P, C)
        F.fig_gauges(out, rids, P, C)
        F.fig_spectra(out, rids, P, C)
        F.fig_crestmax(out, rids, P, C)
        F.fig_series(out, rids, P, C)
        F.fig_shapes(out, rids, P, C)
        F2.fig_series(out, ["R2", "R3", RID], P, C)
        F2.fig_overlay(out, ["R2", "R3", RID], P, C)
    print(mode, "done")
