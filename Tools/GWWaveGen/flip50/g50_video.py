# -*- coding: utf-8 -*-
"""FLIP50 (option D): the comparison video (per breaker, red box at the most print-like frame) and the whole-run video of a FLIP50 calculation
(py -3.10 -B; numpy, scipy, scikit-image, PIL, ffmpeg). 2026-10-15 written new (Claude).
It runs g49_video2 (flip49, read only: the tool that makes the DA1 videos) after g50_ana's in-memory adaptations (outputs inside
Unity/Build/FLIP50, layout D, plan_D_frozen.json, far row inside r4). Only the header text is replaced for layout D so the video says what
the run is: a half tank with a side band, the D19B straight 1:10 beach, and a CHOSEN directional periodic sea whose phases fix the focus point
and time (not a regular unidirectional swell, not a measured site).
usage (after `py -3.10 -B g50_ana.py all <run>`):
  py -3.10 -B g50_video.py compare <run> [--k=2,3] [--still=best|onset|<frame>] [--fast=2] [--slow=0.25] [--hold=3] [--ss=2]
  py -3.10 -B g50_video.py whole <run> [--speed=2] [--hold=1]
  py -3.10 -B g50_video.py all <run>
outputs: <run>/video/<run_id>_compare.mp4, <run_id>_whole.mp4 (+ json)
"""
import os, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip49", HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import g50_ana as AN                 # noqa: E402  (redirect_gc49 + periodic_ana patches first)
import g49_video2 as V2              # noqa: E402
import g50_common as GC50            # noqa: E402

_ORIG_HEAD = V2.Compare49.head_lines
_ORIG_WHOLE_HEADER = V2.Whole.header


def _sea(c):
    w = c.get("wave") or {}
    d = c.get("dir") or {}
    if d:
        return "帯で方向のある周期の波（T %s s・±%s°・%s 成分、焦点 x %s m。集まる所と時刻は選んだ位相で決まる【選び】）" % (
            V2._g(d.get("T"), "%g"), V2._g(d.get("theta_max_deg"), "%g"), d.get("n"), V2._g(d.get("x_f"), "%g"))
    return "入口の帯で規則波 T %s s・H %s m（Fenton、2D の板）" % (V2._g(w.get("T_s"), "%g"), V2._g(w.get("H_m"), "%.2f"))


def head_lines_D(self):
    S = self.S; c = S.cfg
    if c.get("layout") != "D":
        return _ORIG_HEAD(self)
    r = self.r
    kind = "準 2D の板（半幅 %g m）" % S.Wd if S.strip else "3D の半分の水槽（半幅 %g m、y = 0 は対称の面、y 95〜140 m は横の帯）" % S.Wd
    e = self.ev
    judged = "判定する（t ≥ %g s）" % GC50.T_JUDGE if e.get("judged") else "判定しない（入口の立ち上がりの間、t < %g s）" % GC50.T_JUDGE
    l1 = "FLIP50 %s：崩れ %s（%d/%d、%s）の原画との比べ" % (S.rid, r.lab, self.idx + 1, self.n, judged)
    coarse = "（粗い。下見なので判定しない）" if not (c.get("case") or {}).get("judged", True) else ""
    l2 = "%s。海底 D19B（横にまっすぐな 1:10 の浜、水深 19 m）。%s。粒子 %.4g m%s" % (kind, _sea(c), r.cx.dp, coarse)
    l3 = ("力は重力だけ（帯は水平の流速だけを寄せる）。断面は縦横同じ縮尺、高さは静かな水面から（ずれ %.3f m を引いた）。数は【測った】。"
          "選んだ物：方向のある波・焦点・海底。計算した物：浅くなる・屈折・集まり・崩れ・巻き" % r.off)
    l4 = "赤の太い枠＝原画に最も近い瞬間（pana/best_frames.json、score3 最小）・黒＝原画の輪郭（縦の伸びを戻した形）・青＝このコマ・紺＝各横位置の頂 c(y)"
    return l1, l2, l3, l4


def header_D(self, dr, f, state, r):
    S = self.S; c = S.cfg
    if c.get("layout") != "D":
        return _ORIG_WHOLE_HEADER(self, dr, f, state, r)
    kind = "準 2D の板（半幅 %g m）" % S.Wd if S.strip else "3D の半分の水槽（半幅 %g m、y = 0 は対称の面、y 95〜140 m は横の帯）" % S.Wd
    V2.GV.text_fit(dr, (40, 4), "FLIP50 %s：計算の全部（%s 倍の早送り、原画に最も近いコマで %g s 止めて赤い枠）" % (S.rid, V2._g(self.speed, "%g"), self.hold), 1430, 22, True)
    V2.GV.text_fit(dr, (40, 34), "%s。海底 D19B（横にまっすぐな 1:10 の浜）。%s。粒子 %.4g m%s。力は重力だけ" % (
        kind, _sea(c), S.cx.dp, "（粗い。下見なので判定しない）" if not (c.get("case") or {}).get("judged", True) else ""), 1430, 15)
    l3 = ("断面は縦横同じ縮尺。板は横に一様なので上からの図の代わりに波高計を広く置いた。" if S.strip else
          "上から：色＝高さ（静かな水面から、縦横同じ縮尺、y = 0 で写して両側）。断面は縦横同じ縮尺。")
    V2.GV.text_fit(dr, (40, 54), l3 + "数は AI の読み（g49_periodic_ana）。原画らしさは利用者が決める", 1430, 14, fill=V2.SUB)


V2.Compare49.head_lines = head_lines_D
V2.Whole.header = header_D
V2.TOOL = "Tools/GWWaveGen/flip50/g50_video.py (g49_video2 with FLIP50 headers)"

if __name__ == "__main__":
    V2.main()
