# -*- coding: utf-8 -*-
"""FLIP48：原画と比べる動画と、真ん中への集まりを見せる動画（py -3.10 -B。numpy・scipy・scikit-image・PIL と ffmpeg）。
2026-10-15 新しく書いた。利用者の 10/15 の指摘（3D の動画では大きな波の真ん中への集まりが分かりにくい。2D の動画のように、原画に最も近い瞬間を
赤で囲み、原画との比べが見えるように）に答えるための物。FLIP47 の g47_video.py（2D の比べの動画）の並べ方を 3D の記録に写した。

読み込んで使う物（どれも変えていない。g48_video.py は読み込まない：読み込むと g46_video の関数を読み替えるため）：
  g48_analyze.Ctx48（FLIP46 の記録は g46_analyze.Ctx）・g46_analyze.r2_mask・STUDY52 measure_mask・d_shape_measure.pick
    → ana.json の shape.series と同じ物差し（同じ関数）。動画の json に ana.json との違いの最大を書く（1e-3 以下のはず）
  g48_peak_metrics.load_hf・crest_profile・lateral・side_band → peak.json と同じ c(y)・c0/c_side・盛り上がりの半分の幅
  g47_video.print_ref・print_phys・score3・measure_rows・Box・timebar・Writer・probe ほか（原画の輪郭と帯、表、描く道具）
  g46_video.raster・far_plane・hf_patch・section・tri_grid（3D の z バッファと横の断面）
書くのは Unity/Build/FLIP48 の中だけ（FLIP46 の記録の動画は Unity/Build/FLIP48/compare46 へ）。

1 コマの並び（1920×1080、24 コマ/s）：
  頭      計算の名前・海底と波・決まり・色の意味。右上に時刻と再生の速さ（2 倍の早送り／実時間／0.25 倍のスロー／止め）
  左上 A1 3D：波の前から斜めに見下ろす透視の図（目は真ん中の頂の 45 m 前・高さ 14 m・11° 見下ろし、頂を追う。壁の 12 m 外で止める。
          縦は伸ばしていない）。色＝高さ（静かな水面から。原画の色ではない）。紺の線＝各横位置の頂 c(y)、
          黄土・茶・灰の柱＝y = ±2 Hc・±4 Hc・横の端の頂の高さ。--view3d=eye で目の高さの図（巻き始めの時に目を止める）
  右上 A2 グラフ c(y)（縦を伸ばした）：今（紺）、0.5 s ごとの前の 8 つ（薄い灰）、原画に最も近い瞬間（赤の破線）、Hc・横の端の高さ、
          盛り上がりの半分の幅。下に c0・c_side・c0/c_side・c0/c(4Hc)・半分の幅
       A3 c0（真ん中の頂）と c_side（横の端の頂）の時間の変化
  中   B0 領域の全部の y = 0.5 m の断面（縦横同じ縮尺。赤の細い枠＝下の拡大の窓）
  左下 B1 真ん中の断面の拡大（頂を追う窓、縦横同じ縮尺、10 m と 5 m の目盛り）。巻き始め〜着水は原画の輪郭（縦の伸びを戻した形）を
          そのコマの η_c と頂の x に合わせて重ねる（細い黒の破線、原画に最も近い瞬間は太い黒の線）
  右下 B2 同じ物差しの重ね（x/η_c、z/η_c）：原画 cn（黒）・描かれたまま（灰の破線）・このコマ（青）・原画に最も近い瞬間（赤）と、
          形の量の表（原画の帯の中は緑、外は赤）。静かな水面より下に閉じた輪郭（棚の海底のすぐ上の FLIP の空気の層）は重ねに描かない（ov_keep）
  下   時刻の帯（巻き始め＝橙、原画に最も近い＝赤、着水＝紫、スローの間）
  原画に最も近い瞬間（score3 の最小）とその止めの間は A1・B1・B2 を太い赤の枠で囲み、赤い字で書く。動画の終わりにもう一度止める。
原画に最も近い瞬間：巻き始め〜着水（着水がなければ ana.json の形の量の最後のコマ＝巻き始め + 2 s）のコマのうち score3（前の面の弦・前の足・
  覆いの面積の、原画の帯の外れの和。SCAN_RESULT_ja.md の決まり）が最小。同じなら弦の外れの小さい方、次に覆いの高い方。

使い方：
  py -3.10 -B g48_video2.py run <run_id か記録の置き場所> [--t0=<s>] [--t1=<s>] [--fast=2] [--slow=0.25] [--hold=3] [--end_hold=3]
         [--Dx=45] [--zh=14] [--pitch=-11] [--vfov=86] [--view3d=high|eye] [--ss=2] [--still=<コマ|best|onset|td>] [--name=<頭>] [--out=<置き場所>]
     → <記録>/video/<run_id>_compare.mp4 と .json（FLIP46 の記録は Unity/Build/FLIP48/compare46/）、原画に最も近い瞬間の
       <run_id>_compare_best.png。--still は 1 コマの PNG だけ。
  py -3.10 -B g48_video2.py lineup <run_id> ... [--out=Unity/Build/FLIP48/runs/LINEUP_best.png]
     → 1 行に 1 本：その計算の原画に最も近い瞬間（巻かなければ最も険しいコマ）の 3D の図と、原画の輪郭を重ねた真ん中の断面
"""
import sys, os, json, math, time, hashlib, glob

sys.dont_write_bytecode = True
REPO = "G:/Unity/GreatWave_2026_Fresh"
TOOLS = REPO + "/Tools/GWWaveGen"
for _p in ("flip45", "flip46", "flip47", "flip48"):
    if TOOLS + "/" + _p not in sys.path:
        sys.path.insert(0, TOOLS + "/" + _p)
import numpy as np                              # noqa: E402
from scipy.ndimage import map_coordinates, median_filter, uniform_filter1d   # noqa: E402
from PIL import Image, ImageDraw, ImageFont     # noqa: E402

import g46_analyze as A46                       # noqa: E402  r2_mask・mesh_frame・S52・DS（読むだけ）
import g48_analyze as A48                       # noqa: E402  Ctx48（読み込むと A46.Ctx・A46.B46 がこの起動の中だけ FLIP48 用になる）
Ctx46 = A48.Ctx48.__bases__[0]                  # FLIP46 の元の Ctx（FLIP46 の記録に使う）
import g46_video as V46                         # noqa: E402  raster・far_plane・hf_patch・section・tri_grid（読むだけ）
import g48_peak_metrics as PM                   # noqa: E402  load_hf・crest_profile・lateral・side_band（読むだけ）
import g47_video as GV                          # noqa: E402  原画の輪郭・帯・表・描く道具（読むだけ。FLIP47 の guard_out・make_run_video は呼ばない）

B48 = REPO + "/Unity/Build/FLIP48"
B46D = REPO + "/Unity/Build/FLIP46"
CACHE3D = B48 + "/_cache/video2_3d"
TOOL = "Tools/GWWaveGen/flip48/g48_video2.py"
VER3D = 4                                       # 3D の図の描き方を変えたら上げる（貯めた図を使わない）
W, H, FPS = GV.W, GV.H, GV.FPS

FONT = "C:/Windows/Fonts/meiryo.ttc"
FONTB = "C:/Windows/Fonts/meiryob.ttc" if os.path.exists("C:/Windows/Fonts/meiryob.ttc") else FONT
_F = {}


def font(sz, b=False):
    k = (int(sz), bool(b))
    if k not in _F:
        _F[k] = ImageFont.truetype(FONTB if b else FONT, int(sz))
    return _F[k]


GV.font = font                                  # この起動の中だけ（g47_video の timebar・text_fit も Meiryo で書く）
V46.font = font

BG = GV.BG; WATER = GV.WATER; SAND = GV.SAND; OUTSIDE = GV.OUTSIDE; TXT = GV.TXT; SUB = GV.SUB
RED = (200, 30, 30); GREEN = GV.GREEN; PURP = GV.PURP; ORANGE = (225, 120, 20); BLUE = GV.BLUE; GREY = GV.GREY; YEL = GV.YEL
NAVY = (25, 45, 120); C2 = (200, 150, 60); C4 = (160, 90, 60); WHITE = (255, 255, 255)

# 3D の色（高さ m → 色）。原画の色ではない。高さを読みやすくするための色
H_STOPS = np.array([-1.0, 1.5, 4.0, 6.0, 8.0, 10.0])
H_COLS = np.array([[0.05, 0.16, 0.30], [0.10, 0.30, 0.48], [0.15, 0.48, 0.62], [0.35, 0.68, 0.70], [0.88, 0.80, 0.45], [0.95, 0.45, 0.25]])


class InputError(Exception):
    pass


def _g(v):
    return "—" if v is None else ("%g" % v)


def guard_out(p):
    a = os.path.abspath(p).replace("\\", "/")
    if not a.lower().startswith(os.path.abspath(B48).replace("\\", "/").lower()):
        raise InputError("書く所は Unity/Build/FLIP48 の中だけ：%s" % a)
    return a


def parse_opt(argv):
    pos, opt = [], {}
    for a in argv:
        if a.startswith("--"):
            k, _, v = a[2:].partition("=")
            opt[k] = v if _ else "1"
        else:
            pos.append(a)
    return pos, opt


def resolve_run(ref):
    for p, st in ((ref, None), (B48 + "/runs/" + ref, "FLIP48"), (B46D + "/runs/" + ref, "FLIP46")):
        if os.path.isdir(p) and glob.glob(os.path.join(p, "r2_c*_b*.npz")):
            a = os.path.abspath(p).replace("\\", "/").rstrip("/")
            if st is None:
                st = "FLIP46" if "/flip46/" in a.lower() else "FLIP48"
            return a, st
    raise InputError("計算の記録が見つからない：%s" % ref)


def block_times(R):
    tf, seen = {}, {}
    for f, (c0, p, i) in R.b.items():
        if p not in seen:
            seen[p] = np.load(p)["t"]
        tf[int(f)] = float(seen[p][i])
    return tf


def mesh_exists(rd, f, near=2):
    for d in [0] + [s * k for k in range(1, near + 1) for s in (1, -1)]:
        if os.path.exists(os.path.join(rd, "surf", "s_%05d.gw45s" % (f + d))):
            return True
    return False


def smooth_track(ts, xr, half=6):
    """±half コマの一次の当てはめで均す（g47_video.make_camera と同じ）。"""
    xsm = np.empty(len(xr))
    for i in range(len(xr)):
        a, b = max(0, i - half), min(len(xr), i + half + 1)
        if b - a >= 3:
            xsm[i] = np.polyfit(ts[a:b] - ts[i], xr[a:b], 1)[1]
        else:
            xsm[i] = xr[a:b].mean()
    return xsm


# ======================================================================== 1 本の計算
class Run:
    def __init__(self, ref, opt=None, log=print):
        self.opt = opt = dict(opt or {})
        self.log = log
        self.rd, self.stage = resolve_run(ref)
        self.rid = os.path.basename(self.rd)
        t_start = time.time()
        self.cx = (A48.Ctx48 if self.stage == "FLIP48" else Ctx46)(self.rd, {})
        cx = self.cx
        self.cfg = cx.cfg
        self.off = float(cx.off)
        ap = os.path.join(self.rd, "ana.json")
        if not os.path.exists(ap):
            raise InputError("ana.json がない（先に g48_analyze.py か g46_analyze.py）：%s" % self.rd)
        self.ana = json.load(open(ap, encoding="utf8"))
        self.tf = block_times(cx.R2)
        self.H = PM.load_hf(self.rd)
        self.hidx = {int(f): i for i, f in enumerate(self.H["frames"])}
        self.frames = [int(f) for f in cx.R2.frames if f >= 2 and int(f) in self.hidx and f in cx.R1.b]
        P = self.cfg.get("parms") or {}
        self.W = float(P.get("W", cx.y_max))
        self.Lx = float(P.get("x0", 0.0)) + float(P.get("Lx", cx.x_max))
        self.band = PM.side_band(self.W)
        self.ys = self.H["ys"]
        # ---- 出来事（ana.json）
        on = self.ana.get("onset"); td = self.ana.get("touchdown"); st = self.ana.get("steepest")
        self.on = dict(f=int(on["frame"]), t=float(on["t"]), x=float(on["xc"]), Hc=float(on["eta_c"])) if on else None
        self.td = dict(f=int(td["frame"]), t=float(td["t"]), x=float(td.get("xc") or 0.0)) if (on and td) else None
        self.steep = dict(f=int(st["frame"]), t=float(st["t"]), x=float(st["xc"]), eta=float(st["eta_c"]), thmax=st.get("thmax")) if st else None
        ser = [r for r in ((self.ana.get("shape") or {}).get("series") or []) if "error" not in r]
        self.ana_series = {int(r["frame"]): r for r in ser}
        if self.on:
            if self.td:
                self.end_f = self.td["f"]; self.end_src = "着水（ana.json touchdown）"
            elif self.ana_series:
                self.end_f = max(self.ana_series); self.end_src = "着水なし：ana.json の形の量の最後のコマ（巻き始め + 2 s）"
            else:
                self.end_f = self.frame_at(self.on["t"] + 2.0); self.end_src = "着水なし：巻き始め + 2 s"
            self.end_t = self.tf[self.end_f]
            self.ev_t = self.on["t"]; self.ev_f = self.on["f"]
            self.Hc = self.on["Hc"]; self.Hc_src = "巻き始めの真ん中の頂 η_c（ana.json onset.eta_c）"
        else:
            self.end_f = self.end_t = None; self.end_src = None
            if self.steep:
                self.ev_t = self.steep["t"]; self.ev_f = self.steep["f"]
                self.Hc = self.steep["eta"]; self.Hc_src = "巻かない：最も険しいコマの真ん中の頂（ana.json steepest.eta_c）"
            else:
                self.ev_f = self.frames[-1]; self.ev_t = self.tf[self.ev_f]
                self.Hc = None; self.Hc_src = None
        self._track()
        self._prof = {}
        self._lat = {}
        self.meas = {}
        self.best_f = None
        self.best_src = None
        self.checks = {}
        self.checks["ctx_s"] = round(time.time() - t_start, 2)

    def frame_at(self, t):
        return min(self.frames, key=lambda q: abs(self.tf[q] - t))

    # ---- 真ん中の頂の x（ana.json の centre_track。なければ hf の y = 0 の行の最大）
    def _track(self):
        ct = (self.ana.get("centre_track") or {}).get("series") or []
        if ct:
            fr = [int(r[0]) for r in ct if int(r[0]) in self.tf]
            xr = [float(r[2]) for r in ct if int(r[0]) in self.tf]
            er = [float(r[3]) for r in ct if int(r[0]) in self.tf]
            self.track_src = "ana.json centre_track（y = 0 の断面の頂）"
        else:
            fr, xr, er = [], [], []
            xs = self.H["xs"]
            for f in self.frames:
                e = self.H["eta"][self.hidx[f]][:1]
                c, xc = PM.crest_profile(e, xs, self.cx.x_min + 5.0, self.Lx - PM.X_END_PAD)
                if np.isfinite(c[0]):
                    fr.append(f); xr.append(float(xc[0])); er.append(float(c[0]) - self.off)
            self.track_src = "hf の y = 0 の行の最も高い所（ana.json に頂の追いがない）"
        self.tr_f = np.array(fr); self.tr_x = np.array(xr); self.tr_eta = np.array(er)
        self.tr_map = dict(zip(fr, xr))
        # 拡大の窓の位置（g47_video.make_camera と同じ：±6 コマの一次の当てはめ、着水より後は速さで進め、戻らない）
        cut = self.td["f"] if self.td else (fr[-1] if fr else self.frames[-1])
        k = self.tr_f <= cut
        ts = np.array([self.tf[f] for f in self.tr_f[k]]); xk = self.tr_x[k]
        if len(xk) < 3:
            ts = np.array([self.tf[f] for f in self.frames]); xk = np.full(len(ts), 0.5 * (self.cx.x_min + self.cx.x_max))
        xsm = smooth_track(ts, xk)
        kk = ts >= ts[-1] - 1.0
        v = float(np.polyfit(ts[kk], xk[kk], 1)[0]) if kk.sum() >= 3 else 0.0
        if self.on:
            kp = (ts >= self.on["t"] - 1.0) & (ts <= self.on["t"])
            if kp.sum() >= 3:
                v = max(v, float(np.polyfit(ts[kp], xk[kp], 1)[0]))
        v = max(v, 0.0)
        cam = []
        for f in self.frames:
            t = self.tf[f]
            if t <= ts[0]:
                cam.append(xsm[0])
            elif t <= ts[-1]:
                cam.append(float(np.interp(t, ts, xsm)))
            else:
                cam.append(xsm[-1] + v * min(t - ts[-1], 3.0))
        cam = np.maximum.accumulate(np.array(cam))
        self.zcam = {f: float(x) for f, x in zip(self.frames, cam)}
        self.sm_ts, self.sm_x = ts, xsm

    def track_x(self, f):
        if f in self.tr_map:
            return self.tr_map[f]
        if len(self.tr_f):
            return float(self.tr_x[int(np.argmin(np.abs(self.tr_f - f)))])
        return self.zcam[f]

    def zoom_at(self, f, base=0.45):
        if not self.on:
            return base
        t = self.tf[f]; ton = self.on["t"]; ttd = self.end_t
        if t <= ton:
            return base
        if t <= ttd:
            return base + (0.35 - base) * (t - ton) / max(ttd - ton, 1e-6)
        return 0.35 + (0.25 - 0.35) * min((t - ttd) / 0.5, 1.0)

    # ---- 頂の高さの横の分け方（g48_peak_metrics.run の prof と同じ）
    def prof(self, f):
        if f not in self._prof:
            i = self.hidx[f]
            xs = self.H["xs"]; x_hi = self.Lx - PM.X_END_PAD
            c, xc = PM.crest_profile(self.H["eta"][i], xs, PM.X_MIN, x_hi)
            cs, _ = PM.crest_profile(self.H["eta"][i], xs, PM.X_MIN, min(PM.X_SIDE_MAX, x_hi))
            self._prof[f] = (c - self.off, xc, cs - self.off)
        return self._prof[f]

    def lat(self, f):
        if f not in self._lat:
            c, xc, cs = self.prof(f)
            self._lat[f] = PM.lateral(c, self.ys, cs, Hc=self.Hc, band=self.band)
        return self._lat[f]

    def crest_valid(self, f):
        """真ん中の頂が尾根の上（x 150 m より先）に来ているか。来る前の c(y) は静かな水面の揺れを拾うので描かない。"""
        return self.zcam.get(f, 0.0) >= PM.X_MIN + 3.0

    # ---- 形の量（ana.json と同じ関数）と原画に最も近い瞬間
    def measure(self):
        if not self.on:
            self.checks["measure"] = "巻かないので測らない"
            return
        t0 = time.time()
        lo = self.on["t"] - 1.0; hi = self.end_t + 0.5
        win = [f for f in self.frames if lo - 1e-9 <= self.tf[f] <= hi + 1e-9]
        diffs = []
        for f in win:
            xg = self.track_x(f)
            try:
                M, X, Z, t = A46.r2_mask(self.cx, f, xg)
                mm = A46.S52.measure_mask(M, X, Z, flip_extra=dict(Lc=self.cx.Lc))
                m = A46.DS.pick(mm)
                sc, parts = GV.score3(m)
                lines = GV.GA.mask_lines(M, X, Z, float(mm["x_c"]), float(mm["eta_c"]))
                self.meas[f] = dict(x_c=float(mm["x_c"]), eta_c=float(mm["eta_c"]), m=m, score3=sc, parts=parts, lines=lines)
                a = self.ana_series.get(f)
                if a:
                    diffs.append(max(abs((a.get(k) or 0.0) - (m.get(k) or 0.0))
                                     for k in ("face_chord_deg_01_05", "front_x01_rel", "gap_max", "lip_thick_mid", "hood_area", "eta_c")))
            except Exception as ex:
                self.meas[f] = dict(err=repr(ex)[:160])
        self.checks["measure_s"] = round(time.time() - t0, 1)
        self.checks["measure_frames"] = [win[0], win[-1]] if win else None
        self.checks["ana_vs_live_max_abs_diff"] = round(max(diffs), 6) if diffs else None
        self.checks["ana_vs_live_n"] = len(diffs)
        self.checks["ana_vs_live_ok"] = (max(diffs) <= 1e-3) if diffs else None
        cand = [f for f in win if self.on["f"] <= f <= self.end_f and self.meas.get(f, {}).get("score3") is not None]

        def key(f):
            d = self.meas[f]
            return (d["score3"], (d["parts"] or {}).get("face_chord_deg_01_05") or 0.0, -((d["m"] or {}).get("hood_height_m") or 0.0))
        if cand:
            self.best_f = min(cand, key=key)
            self.best_src = "score3 の最小（前の面の弦・前の足・覆いの面積の原画の帯の外れの和。SCAN_RESULT_ja.md の決まり）を巻き始め〜%s に当てた。同じなら弦の外れの小さい方" % (
                "着水" if self.td else "巻き始め + 2 s")
            self.best_at_end = (self.best_f == self.end_f)
        self.win_meas = win

    def peak_check(self):
        """peak.json の巻き始めの横の読みと、ここで読んだ値の違い（同じ関数なので 0 のはず）。"""
        p = os.path.join(self.rd, "peak.json")
        if not (self.on and os.path.exists(p)):
            return None
        ref = (json.load(open(p, encoding="utf8")).get("lateral_key") or {}).get("onset") or {}
        L = self.lat(self.on["f"]) if self.on["f"] in self.hidx else None
        if not L or not ref:
            return None
        d = {}
        for k in ("c0", "c_side", "ratio_side", "ratio_4Hc", "half_excess_width_m", "w90_m"):
            if isinstance(ref.get(k), (int, float)) and isinstance(L.get(k), (int, float)):
                d[k] = round(abs(float(ref[k]) - float(L[k])), 6)
        return dict(max_abs_diff=max(d.values()) if d else None, per_key=d)

    # ---- 3D の目
    def cam3d_setup(self, D=45.0, h=6.0, hfov=80.0):
        """目は真ん中の頂（均した x）の D m 前・y 0・静かな水面 + h m。出来事（巻き始め、巻かなければ最も険しいコマ）の時に止める
        （その後は波が目に向かって来る）。止める前後 0.3 s で目の速さを滑らかに 0 にする。"""
        self.cam_D, self.cam_h, self.cam_hfov0 = float(D), float(h), float(hfov)
        xmax = self.cx.x_max - 1.5
        fol = [min(self.zcam_unclipped(f) + D, xmax) for f in self.frames]
        xc = [fol[0]]
        for i in range(1, len(self.frames)):
            t = self.tf[self.frames[i]]
            w = float(np.clip((self.ev_t + 0.3 - t) / 0.6, 0.0, 1.0))
            xc.append(min(xc[-1] + (fol[i] - fol[i - 1]) * w, xmax))
        self.cam3 = {f: float(x) for f, x in zip(self.frames, xc)}
        x_ev = self.cam3[self.ev_f] if self.ev_f in self.cam3 else xc[-1]
        self.cam_D_eff = x_ev - self.zcam_unclipped(self.ev_f)
        hf = float(hfov)
        if self.cam_D_eff < 30.0 / math.tan(math.radians(hf / 2.0)):
            hf = min(100.0, 2.0 * math.degrees(math.atan(30.0 / max(self.cam_D_eff, 1.0))))
        self.cam_hfov = hf

    def zcam_unclipped(self, f):
        """目を置くための頂の x（均した x、戻らない）。"""
        return self.zcam[f]


# ======================================================================== 3D の図
def tint(P, T, cam):
    a, b, c = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    n = np.cross(b - a, c - a); n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    cen = (a + b + c) / 3; v = cam - cen; dist = np.linalg.norm(v, axis=1); v = v / np.maximum(dist[:, None], 1e-9)
    n = np.where((np.sum(n * v, 1) < 0)[:, None], -n, n)
    lam = np.clip(n @ V46.LDIR, 0, 1)
    z = cen[:, 2]
    base = np.stack([np.interp(z, H_STOPS, H_COLS[:, k]) for k in range(3)], 1)
    col = base * (0.42 + 0.58 * lam[:, None])
    fog = np.clip(dist / 2500.0, 0, 1)[:, None] ** 0.7
    return col * (1 - fog) + V46.SKY_B * fog


def scene3d(run, f, cam, yaw=180.0):
    """g46_video.boat_scene の写し：面の記録（y = 0 で写す）＋その外の hf＋箱の外の平らな水。
    面の記録の三角形のうち、下流の壁・横の壁の面と、静かな水面の 3 m より下の面（海底の側の面）は除く（目が箱の外に出た時の乱れ）。"""
    cx = run.cx; off = run.off
    d, fm = A46.mesh_frame(cx, f)
    fw = (math.cos(math.radians(yaw)), math.sin(math.radians(yaw)))
    parts = []
    inset = None
    if d is not None:
        Pm = d["P"].astype(np.float64).copy(); Pm[:, 1] -= off
        V = np.stack([Pm[:, 0], Pm[:, 2], Pm[:, 1]], 1)
        T = d["tri"].astype(np.int64)
        c = V[T].mean(1)
        keep = (np.abs(c[:, 1]) <= cx.y_max - 0.6) & (c[:, 2] >= -3.0)      # 下流の壁の面は残す（目が箱の外に出た時に穴にならないように）
        T = T[keep]
        parts.append((np.concatenate([V, V * np.array([1, -1, 1])]), np.concatenate([T, T[:, ::-1] + len(V)])))
        lo, hi = d["lo"], d["hi"]
        inset = (lo[0] + 1.0, hi[0] - 1.0, hi[2] - 1.0)

    Ph, Th, (hx0, hx1, hy1) = hf_patch2(cx, off, f, inset)
    parts.append((Ph, Th))
    parts.append(skirt(hx0, hx1, hy1))
    Ps, Ts, n0 = [], [], 0
    for Pp, Tp in parts:
        Ps.append(Pp); Ts.append(Tp + n0); n0 += len(Pp)
    P = np.concatenate(Ps); T = np.concatenate(Ts)
    return P, T, tint(P, T, cam), (fm if d is not None else None)


def hf_patch2(cx, off, f, inset=None):
    """g46_video.hf_patch の写しに、箱の縁（x_min・x_max・±y_max）で高さ 0 の点の列を足した物（外の平らな水と隙間なくつなぐ）。"""
    e, m, t = cx.R1.get(f)
    e = np.nan_to_num(e - off, nan=0.0)
    xs = m["x0"] + m["dx"] * np.arange(e.shape[1]); ys = m["z0"] + m["dz"] * np.arange(e.shape[0])
    hx0, hx1, hy1 = xs[0] - 0.5 * m["dx"], xs[-1] + 0.5 * m["dx"], ys[-1] + 0.5 * m["dz"]
    ys2 = np.concatenate([[-hy1], -ys[::-1], ys, [hy1]]); e2 = np.concatenate([e[::-1], e])
    xs2 = np.concatenate([[hx0], xs, [hx1]])
    E = np.zeros((len(ys2), len(xs2))); E[1:-1, 1:-1] = e2
    X, Y = np.meshgrid(xs2, ys2)
    P = np.stack([X.ravel(), Y.ravel(), E.ravel()], 1)
    T = V46.tri_grid(len(xs2), len(ys2))
    if inset is not None:
        c = P[T].mean(1)
        T = T[~((c[:, 0] > inset[0]) & (c[:, 0] < inset[1]) & (np.abs(c[:, 1]) < inset[2]))]
    return P, T, (hx0, hx1, hy1)


def skirt(hx0, hx1, hy1, R=3000.0, n=22):
    """箱の外の平らな水（高さ 0）。箱の縁に合わせた 8 つの面（縁の近くを細かく）。"""
    def ax(a, b):
        g = np.concatenate([[0.0], np.geomspace(1.5, R, n)])
        return [a - g[::-1], np.linspace(a, b, max(2, int((b - a) / 15.0) + 2)), b + g]
    AX = ax(hx0, hx1); AY = ax(-hy1, hy1)
    Ps, Ts, n0 = [], [], 0
    for i in range(3):
        for j in range(3):
            if i == 1 and j == 1:
                continue
            X, Y = np.meshgrid(AX[i], AY[j])
            P = np.stack([X.ravel(), Y.ravel(), np.zeros(X.size)], 1)
            Ps.append(P); Ts.append(V46.tri_grid(len(AX[i]), len(AY[j])) + n0); n0 += len(P)
    return np.concatenate(Ps), np.concatenate(Ts)


class View3D:
    """3D の図。mode high（既定）：斜め上から、頂を追う（目は頂の Dx m 前・高さ h m、pitch° 見下ろす）。
    mode eye：目の高さから、出来事の時に止める（Run.cam3d_setup）。"""

    def __init__(self, run, Wi, Hi, ss=2, mode="high", Dx=45.0, h=14.0, pitch=-11.0, hfov=86.0):
        self.r = run; self.Wi, self.Hi, self.ss = int(Wi), int(Hi), int(ss)
        self.mode = mode
        if mode == "eye":
            self.hfov = run.cam_hfov; self.pitch = 0.0; self.cy = 0.52 * self.Hi
        else:
            self.hfov = float(hfov); self.pitch = float(pitch); self.cy = 0.5 * self.Hi
            self.Dx, self.h = float(Dx), float(h)
        self.fx = (self.Wi / 2.0) / math.tan(math.radians(self.hfov) / 2.0)
        self.yaw = 180.0
        ps = math.radians(self.yaw); ph = math.radians(self.pitch)
        self.fw = np.array([math.cos(ps), math.sin(ps), 0.0]); self.rt = np.array([math.sin(ps), -math.cos(ps), 0.0])
        up = np.array([0.0, 0.0, 1.0])
        self.fw2 = self.fw * math.cos(ph) + up * math.sin(ph); self.up2 = -self.fw * math.sin(ph) + up * math.cos(ph)

    def cam(self, f):
        if self.mode == "eye":
            return np.array([self.r.cam3[f], 0.0, self.r.cam_h])
        # 目は下流の壁の 12 m 外まで（それより先は追わない。壁の切り口が画面の下に入らないように）
        return np.array([min(self.r.zcam[f] + self.Dx, self.r.cx.x_max + 12.0), 0.0, self.h])

    def cam_text(self, f, has_mesh):
        r = self.r; cam = self.cam(f)
        src = "面の記録 + hf" if has_mesh else "hf だけ"
        if self.mode == "eye":
            half = r.cam_D_eff * math.tan(math.radians(r.cam_hfov / 2.0))
            return "透視（近い物は大きく見える）。目：x %.0f m・y 0・静かな水面 + %.1f m。%s の時の頂の %.0f m 前に止めた。頂の所で見える横は ±%.0f m（全幅 ±%g m）。%s" % (
                cam[0], cam[2], "巻き始め" if r.on else "最も険しいコマ", r.cam_D_eff, half, r.W, src)
        follow = "頂を追う" if cam[0] < r.cx.x_max + 12.0 - 1e-6 else "目は壁の 12 m 外で止めた"
        look = ("%.0f° 見下ろし" % -self.pitch) if self.pitch < -1e-9 else (("%.0f° 見上げ" % self.pitch) if self.pitch > 1e-9 else "水平に見る")
        return "透視（近い物は大きく見える。縦は伸ばしていない）。目：真ん中の頂の %.0f m 前・y 0・高さ %.0f m、%s、%s。横の見える角 %.0f°。%s" % (
            cam[0] - r.zcam[f], self.h, look, follow, self.hfov, src)

    def _basis(self, Q, cam):
        d = np.asarray(Q, float) - cam
        return d @ self.fw2, d @ self.rt, d @ self.up2

    def proj(self, Q, cam):
        Zc, Xc, Yc = self._basis(Q, cam)
        Zs = np.where(Zc > 0.3, Zc, np.nan)
        return np.stack([self.Wi / 2.0 + self.fx * Xc / Zs, self.cy - self.fx * Yc / Zs], 1), Zc

    def base(self, f):
        cam = self.cam(f)
        key = "%s|%d|%.3f|%.3f|%.3f|%.3f|%d|%d|%d|%.4f|%s|v%d" % (self.r.rid, f, cam[0], cam[2], self.hfov, self.pitch, self.Wi, self.Hi, self.ss, self.cy,
                                                              self.mode, VER3D)
        hsh = hashlib.sha1(key.encode()).hexdigest()[:12]
        d = os.path.join(CACHE3D, self.r.rid)
        p = os.path.join(d, "f%05d_%s.png" % (f, hsh))
        if os.path.exists(p):
            try:
                return Image.open(p).convert("RGB"), mesh_exists(self.r.rd, f)
            except Exception:
                pass
        P, T, col, fm = scene3d(self.r, f, cam, self.yaw)
        Zc, Xc, Yc = self._basis(P, cam)                # 見下ろす目：点を目の向きの座標に移してから、向きのない raster に渡す
        P2 = cam + Zc[:, None] * self.fw[None, :] + Xc[:, None] * self.rt[None, :] + Yc[:, None] * np.array([0.0, 0.0, 1.0])[None, :]
        im = V46.raster(P2, T, col, cam, self.yaw, self.Wi, self.Hi, self.fx, self.fx, self.Wi / 2.0, self.cy, ss=self.ss)
        os.makedirs(d, exist_ok=True)
        im.save(p)
        return im, fm is not None

    def draw(self, f, small=False):
        """3D の図（貯めた図）に、頂の線・±2Hc・±4Hc・横の端の柱・高さの色の物差しを描き足す。"""
        r = self.r
        im, has_mesh = self.base(f)
        im = im.copy(); dr = ImageDraw.Draw(im)
        cam = self.cam(f)
        wl, wn = (6, 3) if not small else (4, 2)
        if r.crest_valid(f):
            c, xc, cs = r.prof(f)
            ok = np.isfinite(c) & np.isfinite(xc)
            if ok.sum() > 8:
                xcs = np.where(ok, xc, np.nan)
                xcs = uniform_filter1d(median_filter(np.nan_to_num(xcs, nan=np.nanmedian(xcs)), size=9, mode="nearest"), 5, mode="nearest")
                ys = r.ys
                yy = np.concatenate([-ys[::-1], ys]); cc = np.concatenate([c[::-1], c]); xx = np.concatenate([xcs[::-1], xcs])
                uv, Zc = self.proj(np.stack([xx, yy, cc + 0.15], 1), cam)
                good = np.isfinite(uv).all(1) & (Zc > 1.0)
                seg = []
                for i in range(len(uv) + 1):
                    if i < len(uv) and good[i]:
                        seg.append(tuple(uv[i])); continue
                    if len(seg) > 1:
                        dr.line(seg, fill=WHITE, width=wl); dr.line(seg, fill=NAVY, width=wn)
                    seg = []
                posts = []
                if r.Hc:
                    posts += [(2 * r.Hc, C2, "2 Hc"), (4 * r.Hc, C4, "4 Hc")]
                posts.append((0.5 * (r.band[0] + r.band[1]), (110, 110, 110), "横の端"))
                for yq0, colr, lab in posts:
                    for sg in (-1, 1):
                        yq = sg * yq0
                        if abs(yq) > ys[-1]:
                            continue
                        j = int(np.argmin(np.abs(yy - yq)))
                        q, zc = self.proj(np.array([[xx[j], yq, 0.0], [xx[j], yq, cc[j]]]), cam)
                        if np.isfinite(q).all() and (zc > 1.0).all() and -50 < q[1, 0] < self.Wi + 50:
                            dr.line([tuple(q[0]), tuple(q[1])], fill=WHITE, width=wl + 1)
                            dr.line([tuple(q[0]), tuple(q[1])], fill=colr, width=wn + 1)
                            fz = font(13 if not small else 11, True)
                            tw = dr.textlength(lab, font=fz)
                            GV.label_box(dr, (q[1, 0] - tw / 2, q[1, 1] - (22 if not small else 18)), lab, colr, fz)
        # 高さの色の物差し
        x0 = self.Wi - (58 if not small else 48); y0 = 8; hh = self.Hi * 0.28
        for k in range(int(hh)):
            z = 10.5 - 11.0 * k / hh
            col = tuple(int(255 * np.interp(z, H_STOPS, H_COLS[:, j])) for j in range(3))
            dr.line([(x0, y0 + k), (x0 + 12, y0 + k)], fill=col)
        dr.rectangle([x0, y0, x0 + 12, y0 + hh], outline=(80, 80, 80))
        for z in (0, 4, 8):
            yv = y0 + (10.5 - z) / 11.0 * hh
            dr.line([(x0 + 12, yv), (x0 + 16, yv)], fill=(60, 60, 60))
            GV.label_box(dr, (x0 + 18, yv - 8), "%d m" % z, (40, 40, 40), font(11))
        GV.label_box(dr, (x0 - 16, y0 + hh + 6), "色＝高さ", (40, 40, 40), font(12))
        return im, has_mesh


# ======================================================================== 横の断面
def sec_raster(run, f, bx, fill_air=True):
    """r2（y = 0.5 m の行、1 m の格子）を画素の中心で一次の補間。海底より下は砂の色。
    描くためだけに、海底のすぐ上（格子 1.5 個）の空気は、その上の格子が水なら水に塗る（FLIP の海底の空気の層。測る時は r2_mask のまま）。"""
    cx = run.cx; off = run.off
    S, m, t = cx.R2.get(f)
    S = np.array(S, np.float32, copy=True)
    xs = m["x0"] + m["dx"] * np.arange(S.shape[1]); yc = m["y0"] + m["dy"] * np.arange(S.shape[0])
    ylat = float(m.get("z", 0.0))
    bed = cx.bed_z(xs, ylat)
    S[yc[:, None] < bed[None, :]] = np.minimum(S[yc[:, None] < bed[None, :]], -0.5)
    nfill = 0
    if fill_air:
        lim = bed + cx.margin + 1.5 * cx.vox
        kt = np.searchsorted(yc, lim)
        ok = kt < len(yc)
        above = np.zeros(len(xs), bool)
        above[ok] = S[kt[ok], np.arange(len(xs))[ok]] < 0
        band = (yc[:, None] < lim[None, :]) & (S >= 0) & above[None, :]
        nfill = int(band.sum())
        S[band] = -0.5
    Xp = bx.x0 + (np.arange(bx.pw) + 0.5) / bx.s
    Zp = bx.z1 - (np.arange(bx.ph) + 0.5) / bx.s
    gx = (Xp - m["x0"]) / m["dx"]; gz = (Zp + off - m["y0"]) / m["dy"]
    GX, GZ = np.meshgrid(gx, gz)
    v = map_coordinates(S, [GZ.ravel(), GX.ravel()], order=1, mode="nearest").reshape(GZ.shape)
    a = np.empty((bx.ph, bx.pw, 3), np.uint8); a[:] = BG
    a[v < 0] = WATER
    zb = cx.bed_z(Xp, ylat) - off
    a[Zp[:, None] < zb[None, :]] = SAND
    a[:, (Xp < cx.x_min) | (Xp > cx.x_max)] = OUTSIDE
    return Image.fromarray(a), ylat, nfill


def ov_keep(lines):
    """重ね（x/η_c、z/η_c）に描く輪郭。全部が静かな水面より下にある輪郭（棚の海底のすぐ上に残る FLIP の空気の層の小さな輪）は除く。
    描くためだけ（測りの r2_mask・measure_mask は変えない）。巻いた中の空気（樽）は水面より上に掛かるので残る。"""
    return [q for q in lines if len(q) > 1 and float(np.max(q[:, 1])) >= 0.0]


def draw_bars(dr, bx, small=False):
    if bx.z1 - bx.z0 >= 10.5:
        zb0 = 0.0 if bx.z0 < 0 and bx.z1 > 10 else bx.z0 + 0.25
        u = bx.px + 12
        dr.line([(u, bx.Y(zb0)), (u, bx.Y(zb0 + 10))], fill=RED, width=4)
        for zz in (zb0, zb0 + 10):
            dr.line([(u - 5, bx.Y(zz)), (u + 5, bx.Y(zz))], fill=RED, width=2)
        GV.label_box(dr, (u + 8, bx.Y(zb0 + 10) - 3), "10 m", RED, font(13 if small else 15, True))
    u0 = bx.px + 60; v = bx.py + bx.ph - 16
    dr.line([(u0, v), (u0 + 5 * bx.s, v)], fill=RED, width=4)
    for uu in (u0, u0 + 5 * bx.s):
        dr.line([(uu, v - 5), (uu, v + 5)], fill=RED, width=2)
    GV.label_box(dr, (u0 + 5 * bx.s + 8, v - 11), "5 m", RED, font(13 if small else 15, True))


def draw_section(im, dr, run, f, bx, tick=10.0, small=False, outline=True, best=False):
    img, ylat, nfill = sec_raster(run, f, bx)
    im.paste(img, (int(bx.px), int(bx.py)))
    y0 = bx.Y(0.0)
    if bx.z0 < 0 < bx.z1:
        for xx in np.arange(bx.px, bx.px + bx.pw, 12):
            dr.line([(xx, y0), (min(xx + 6, bx.px + bx.pw), y0)], fill=(205, 205, 200), width=1)
    fz = font(12 if small else 13)
    for gx in np.arange(math.ceil(bx.x0 / tick) * tick, bx.x1 + 1e-6, tick):
        u = bx.X(gx)
        dr.line([(u, bx.py + bx.ph), (u, bx.py + bx.ph + 5)], fill=SUB, width=1)
        lab = "%g" % gx
        dr.text((u - dr.textlength(lab, font=fz) / 2, bx.py + bx.ph + 5), lab, fill=SUB, font=fz)
    draw_bars(dr, bx, small)
    m = run.meas.get(f)
    drawn = False
    if outline and run.on and m and m.get("eta_c") and run.on["t"] - 1e-9 <= run.tf[f] <= run.end_t + 1e-9:
        for q in GV.print_phys(m["x_c"], m["eta_c"]):
            for Pp in bx.clip(q):
                GV.poly(dr, Pp, (0, 0, 0), 4 if best else 2, dash=not best)
        u, v = bx.X(m["x_c"]), bx.Y(m["eta_c"])
        dr.polygon([(u, v - 6), (u + 6, v), (u, v + 6), (u - 6, v)], fill=YEL, outline=(120, 100, 0))
        drawn = True
    dr.rectangle([bx.px, bx.py, bx.px + bx.pw, bx.py + bx.ph], outline=(120, 120, 120))
    return drawn, ylat, nfill


# ======================================================================== 1 本の動画
class CompareVideo:
    def __init__(self, run, opt):
        self.r = r = run
        self.opt = opt
        self.fast = float(opt.get("fast", 2.0))
        self.slow = float(opt.get("slow", 0.25))
        self.hold_s = float(opt.get("hold", 3.0))
        self.end_hold_s = float(opt.get("end_hold", 3.0))
        r.measure()
        r.cam3d_setup(float(opt.get("D", 45.0)), float(opt.get("h", 6.0)), float(opt.get("hfov", 80.0)))
        t_first, t_last = r.tf[r.frames[0]], r.tf[r.frames[-1]]
        end_ref = r.end_t if r.on else r.ev_t
        t0 = float(opt["t0"]) if opt.get("t0") is not None else max(t_first, r.ev_t - 9.0)
        t1 = float(opt["t1"]) if opt.get("t1") is not None else min(t_last, end_ref + 0.5 + 2.0)
        if opt.get("t1") is None:               # 頂が下流の壁の 12 m 手前に来たら終える（その先は壁の跳ね返りを見るだけ）
            near = [r.tf[f] for f in r.frames if r.zcam[f] >= r.cx.x_max - 12.0 and r.tf[f] > end_ref + 0.5]
            if near:
                t1 = min(t1, near[0])
        self.fr = [f for f in r.frames if t0 - 1e-9 <= r.tf[f] <= t1 + 1e-9]
        if not self.fr:
            raise InputError("時刻の窓 %.2f〜%.2f s にコマがない" % (t0, t1))
        self.ta, self.tb = r.tf[self.fr[0]], r.tf[self.fr[-1]]
        self.slow_t = (r.on["t"] - 1.0, r.end_t + 0.5) if (r.on and abs(self.slow - 1.0) > 1e-9) else None
        self.fast_until = (r.on["t"] - 1.0) if r.on else (r.ev_t - 1.0)
        self.best_f = r.best_f
        self.ov_t = (r.on["t"], r.end_t + 0.5) if r.on else None
        self.end_word = "着水" if r.td else "巻き始めの 2 s 後"          # 比べる窓の終わり（着水がなければ ana.json の形の量の最後のコマ）
        self._layout()
        self.v3 = View3D(r, self.A1[2] - self.A1[0], self.A1[3] - self.A1[1], ss=int(opt.get("ss", 2)), mode=opt.get("view3d", "high"),
                         Dx=float(opt.get("Dx", 45.0)), h=float(opt.get("zh", 14.0)), pitch=float(opt.get("pitch", -11.0)), hfov=float(opt.get("vfov", 86.0)))
        self.head = self.head_lines()
        # 時間の変化（A3）
        self.ct_f = [f for f in r.frames if self.ta - 1e-9 <= r.tf[f] <= self.tb + 1e-9 and r.crest_valid(f)]
        self.ct_c0 = np.array([r.lat(f)["c0"] for f in self.ct_f])
        self.ct_cs = np.array([(r.lat(f)["c_side"] if r.lat(f)["c_side"] is not None else np.nan) for f in self.ct_f])
        vals = [self.ct_c0.max() if len(self.ct_c0) else 10.0, (r.Hc or 0.0)]
        self.cy_hi = float(max(12.0, math.ceil(max(vals) + 1.5)))

    # ---- 並べ方
    def _layout(self):
        r = self.r
        self.A1 = (40, 128, 1160, 468)            # 3D
        self.A2 = (1200, 128, 1880, 322)          # c(y)
        self.A3 = (1200, 380, 1880, 468)          # c0・c_side の時間の変化
        self.B0y = 500; self.B0h = 68             # 全部の断面
        self.zy = 626; self.zbot = 1004           # 拡大
        self.ovx, self.ovy = 1236, 500            # 重ね（B2）
        # 拡大の窓の高さ
        lo = (r.on["t"] - 1.0) if r.on else (r.ev_t - 1.0)
        hi = (r.end_t + 0.5) if r.on else (r.ev_t + 1.0)
        etas = [e for f, e in zip(r.tr_f, r.tr_eta) if lo - 1e-9 <= r.tf.get(int(f), -1) <= hi + 1e-9] or [r.Hc or 10.0]
        self.z1 = float(min(16.0, math.ceil(max(etas) + 2.0)))
        camx = [r.zcam[f] for f in r.frames if lo - 1e-9 <= r.tf[f] <= hi + 1e-9] or [r.zcam[r.frames[-1]]]
        bz = float(np.min(r.cx.bed_z(np.linspace(min(camx) - 30.0, max(camx) + 30.0, 400), 0.5) - r.off))
        self.z0 = float(min(-3.0, max(-9.0, math.floor(bz - 2.0))))
        pw_max, ph_max = 1120.0, float(self.zbot - self.zy)
        self.zoom_w = float(min(80.0, max(40.0, pw_max * (self.z1 - self.z0) / ph_max)))
        self.zs = min(pw_max / self.zoom_w, ph_max / (self.z1 - self.z0))
        self.XL, self.XR, self.ZB, self.ZT = -2.0, 1.4, -0.3, 1.15
        self.os_ = 188.0

    def head_lines(self):
        r = self.r; cx = r.cx; cfg = r.cfg
        b = cfg.get("bed") or {}; sol = cfg.get("solitary") or {}
        w = cfg.get("wave") if isinstance(cfg.get("wave"), dict) else {}
        if r.stage == "FLIP48":
            bed = "海底：尾根 k %s・真ん中 1:%s・棚 %s m" % (_g(b.get("k")), _g(b.get("s")), _g(b.get("h_sh")))
            ex = []
            if b.get("k_end") is not None:
                ex.append("先細り k→%s" % _g(b.get("k_end")))
            if (b.get("ch_h") or 0) > 0:
                ex.append("横の遠くの溝 %s m" % _g(b.get("ch_h")))
            if (b.get("s1") or 0) > 0:
                ex.append("段 1:%s・%s m" % (_g(b.get("s2")), _g(b.get("dL"))))
            if ex:
                bed += "（" + "・".join(ex) + "）"
            wave = "波：孤立波 H0/h0 %s（h0 %g m、まっすぐな頂）" % (_g(sol.get("H0_nd")), cx.h0)
            if w.get("kind") == "nwave":
                wave += "＋前の谷 β %s（定常な解ではない）" % _g(w.get("beta"))
        else:
            bed = "海底：" + str(cx.ridge_src)
            wave = "波：孤立波 H0 %.2f m（h0 %g m）" % (cx.H0, cx.h0)
        coarse = "（粗い）" if cx.dp > 0.25 + 1e-9 else ""
        l1 = "%s %s：原画と比べる（真ん中の断面）・真ん中への集まり（3D）" % (r.stage, r.rid)
        l2 = "%s。%s。粒子 %.4g m（格子 %.4g m）%s" % (bed, wave, cx.dp, cx.vox, coarse)
        l3 = ("力は重力だけ（半分の幅 %g m を解き、y = 0 は対称の面）。断面は縦横同じ縮尺、高さは静かな水面から（ずれ %.3f m を引いた）。"
              "数は【測った】（ana.json・peak.json と同じ関数）。選んだ物：振幅と海底。計算した物：集まり・崩れ・巻き" % (r.W, r.off))
        l4 = "赤の太い枠＝原画に最も近い瞬間（score3 最小）・黒＝原画の輪郭（縦の伸びを戻した形）・青＝このコマ・紺＝各横位置の頂の線 c(y)・黄土＝y ±2 Hc・茶＝y ±4 Hc"
        return l1, l2, l3, l4

    def header(self, dr, f, state):
        r = self.r
        l1, l2, l3, l4 = self.head
        GV.text_fit(dr, (40, 4), l1, 1430, 22, True)
        GV.text_fit(dr, (40, 34), l2, 1430, 15)
        GV.text_fit(dr, (40, 54), l3, 1430, 14, fill=SUB)
        GV.text_fit(dr, (40, 73), l4, 1430, 14, True, fill=(60, 60, 60))
        t = r.tf[f]
        dr.text((1500, 2), "t = %.2f s" % t, fill=TXT, font=font(30, True))
        if r.on:
            s = "巻き始めから %+.2f s" % (t - r.on["t"])
            if r.td:
                s += "・着水から %+.2f s" % (t - r.td["t"])
            GV.text_fit(dr, (1500, 44), s + "（コマ %d）" % f, 400, 15)
        else:
            GV.text_fit(dr, (1500, 44), "巻かない（最も険しいのは t %.2f s）。コマ %d" % (r.ev_t, f), 400, 15)
        self.banner(dr, 1500, 70, state)

    def banner(self, dr, x, y, state):
        if state == "hold":
            txt, col = "止め：原画に最も近い瞬間（%.1f s）" % self.hold_s, RED
        elif state == "end":
            txt, col = "終わり：原画に最も近い瞬間をもう一度", RED
        elif state == "slow":
            txt, col = "%.3g 倍のスロー（計算の 1 s を %.3g s で）" % (self.slow, 1.0 / self.slow), ORANGE
        elif state == "fast":
            txt, col = "%.3g 倍の早送り（計算の 1 s を %.3g s で）" % (self.fast, 1.0 / self.fast), BLUE
        else:
            txt, col = "実時間（計算の 1 s を 1 s で）", (90, 90, 90)
        fz = font(17, True)
        w = dr.textlength(txt, font=fz)
        dr.rectangle([x, y, x + w + 16, y + 28], fill=col)
        dr.text((x + 8, y + 2), txt, fill=WHITE, font=fz)

    # ---- A1 3D
    def draw_3d(self, im, dr, f, red):
        r = self.r; v3 = self.v3
        x0, y0, x1, y1 = self.A1
        dr.text((x0, y0 - 29), "3D：%s（真ん中への集まり）。色＝高さ、紺の線＝各横位置の頂 c(y)" % ("前から斜め上に見下ろす" if v3.mode == "high" else "波の前の目の高さから"), fill=TXT, font=font(17, True))
        img, has_mesh = v3.draw(f)
        im.paste(img, (x0, y0))
        lab = v3.cam_text(f, has_mesh)
        GV.label_box(dr, (x0 + 6, y1 - 22), lab, (40, 40, 40), font(13))
        if not r.crest_valid(f):
            GV.label_box(dr, (x0 + 6, y0 + 6), "頂はまだ尾根の手前（x %.0f m < %g m）。頂の線は描かない" % (r.zcam[f], PM.X_MIN + 3), SUB, font(14))
        if red:
            self.red_label(dr, x0 + 6, y0 + 6)
        dr.rectangle([x0, y0, x1, y1], outline=(120, 120, 120))

    def red_label(self, dr, x, y):
        r = self.r; d = r.meas.get(self.best_f) or {}
        s = "原画に最も近い瞬間（t = %.2f s、コマ %d、score3 %s）%s" % (r.tf[self.best_f], self.best_f, GV.fmt(d.get("score3"), "%.2f"),
                                                          "（窓の端：着水のコマ）" if getattr(r, "best_at_end", False) else "")
        fz = font(20, True)
        l, t, rr, b = dr.textbbox((x, y), s, font=fz)
        dr.rectangle([l - 5, t - 4, rr + 5, b + 4], fill=RED)
        dr.text((x, y), s, fill=WHITE, font=fz)

    # ---- A2 c(y)
    def draw_cy(self, im, dr, f):
        r = self.r
        px0, py0, px1, py1 = self.A2
        dr.text((px0, py0 - 29), "グラフ（縦を伸ばした）：頂の高さの横の分け方 c(y)", fill=TXT, font=font(17, True))
        dr.rectangle([px0, py0, px1, py1], fill=WHITE, outline=(150, 150, 150))
        L, R, T, B = px0 + 44, px1 - 10, py0 + 8, py1 - 22
        ys = r.ys; Wf = float(ys[-1] + 0.5 * (ys[1] - ys[0]))
        hi = self.cy_hi
        X = lambda v: L + (v + Wf) / (2 * Wf) * (R - L)
        Y = lambda v: B - min(max(v, 0.0), hi) / hi * (B - T)
        for g in range(0, int(hi) + 1, 2):
            dr.line([(L, Y(g)), (R, Y(g))], fill=(232, 232, 232))
            dr.text((px0 + 4, Y(g) - 8), "%d m" % g, fill=SUB, font=font(11))
        for yv in (-80, -40, 0, 40, 80):
            if abs(yv) <= Wf:
                dr.line([(X(yv), B), (X(yv), B + 4)], fill=SUB)
                lab = "y %d m" % yv if yv == 0 else "%d" % yv
                dr.text((X(yv) - dr.textlength(lab, font=font(11)) / 2, B + 5), lab, fill=SUB, font=font(11))
        sb = r.band
        for sg in (-1, 1):
            a_, b_ = sorted((X(sg * sb[0]), X(sg * min(sb[1], Wf))))
            dr.rectangle([a_, B - 5, b_, B], fill=(175, 175, 175))
        if r.Hc:
            for mlt, colr in ((2, C2), (4, C4)):
                for sg in (-1, 1):
                    xv = sg * mlt * r.Hc
                    if abs(xv) <= Wf:
                        dr.line([(X(xv), T), (X(xv), B)], fill=colr, width=2)
                if mlt * r.Hc <= Wf:
                    dr.text((X(mlt * r.Hc) + 3, T), "%d Hc" % mlt, fill=colr, font=font(12, True))
            GV.dashed(dr, [(L, Y(r.Hc)), (R, Y(r.Hc))], (0, 0, 0), 1, 6, 5)
            hl = "Hc %.2f m（%s）" % (r.Hc, "巻き始めの真ん中" if r.on else "最も険しい時の真ん中")
            GV.label_box(dr, (R - 6 - dr.textlength(hl, font=font(12)), Y(r.Hc) - 17), hl, TXT, font(12))   # 右の端（横の端は低いので頂の線と重ならない）
        if not r.crest_valid(f):
            dr.text((L + 20, (T + B) / 2 - 8), "頂はまだ尾根の手前（x 150 m より後ろ）", fill=SUB, font=font(14))
            return
        yy = np.concatenate([-ys[::-1], ys])

        def curve(fr):
            c, _, _ = r.prof(fr)
            cc = np.concatenate([c[::-1], c])
            return [(X(a), Y(b)) for a, b in zip(yy, cc) if np.isfinite(b)]
        t = r.tf[f]
        for k in range(8, 0, -1):
            fr = r.frame_at(t - 0.5 * k)
            if abs(r.tf[fr] - (t - 0.5 * k)) > 0.05 or not r.crest_valid(fr) or fr >= f:
                continue
            g = int(200 + 6 * k)
            pts = curve(fr)
            if len(pts) > 1:
                dr.line(pts, fill=(g, g, g), width=2)
        L_ = r.lat(f)
        if L_.get("c_side") is not None:
            GV.dashed(dr, [(L, Y(L_["c_side"])), (R, Y(L_["c_side"]))], (120, 120, 120), 1, 4, 4)
            dr.text((R - 120, Y(L_["c_side"]) + 2), "横の端 c_side", fill=(110, 110, 110), font=font(12))
        pts = curve(f)
        if L_.get("c_side") is not None and len(pts) > 1:      # 横の端より高い分（盛り上がり）を薄く塗る
            c_, _, _ = r.prof(f)
            cc_ = np.concatenate([c_[::-1], c_]); csd = L_["c_side"]
            poly_ = [(X(a_), Y(max(b_, csd))) for a_, b_ in zip(yy, cc_) if np.isfinite(b_)]
            if len(poly_) > 2:
                dr.polygon(poly_ + [(X(yy[-1]), Y(csd)), (X(yy[0]), Y(csd))], fill=(205, 218, 240))
                dr.line([(L, Y(csd)), (R, Y(csd))], fill=(140, 140, 140), width=1)
        if self.best_f is not None and f > self.best_f:          # 塗りの上に描く（塗りに隠れないように）
            GV.dashed(dr, curve(self.best_f), RED, 2, 7, 4)
            GV.dashed(dr, [(L + 6, T + 22), (L + 30, T + 22)], RED, 2, 7, 4)
            GV.label_box(dr, (L + 34, T + 14), "赤の破線＝原画に最も近い瞬間（コマ %d）" % self.best_f, RED, font(12))
        if len(pts) > 1:
            dr.line(pts, fill=NAVY, width=3)
        w = L_.get("half_excess_width_m")
        if w and L_.get("c_side") is not None:
            zh = L_["c_side"] + 0.5 * (L_["c0"] - L_["c_side"])
            ua, ub, vv = X(-w / 2), X(w / 2), Y(zh)
            dr.line([(ua, vv), (ub, vv)], fill=(0, 120, 160), width=2)
            for uu in (ua, ub):
                dr.line([(uu, vv - 5), (uu, vv + 5)], fill=(0, 120, 160), width=2)
        txt = "c0 %.2f m・c_side %s m・c0/c_side %s・c0/c(4Hc) %s・盛り上がりの半分の幅（水色の線）%s m（%s Hc）" % (
            L_["c0"], GV.fmt(L_.get("c_side"), "%.2f"), GV.fmt(L_.get("ratio_side"), "%.2f"), GV.fmt(L_.get("ratio_4Hc"), "%.2f"),
            GV.fmt(w, "%.0f"), GV.fmt(L_.get("half_excess_width_over_Hc"), "%.1f"))
        GV.text_fit(dr, (px0, py1 + 3), txt, px1 - px0, 14, True)
        dr.text((px0, py1 + 22), "c(y)＝各 y の行で x 150 m〜壁の 15 m 前の一番上の水面の最大（g48_peak_metrics、peak.json と同じ）。灰＝0.5 s ごとの前の形",
                fill=SUB, font=font(11))

    # ---- A3 時間の変化
    def draw_ct(self, im, dr, f):
        r = self.r
        px0, py0, px1, py1 = self.A3
        dr.text((px0, py0 - 22), "真ん中の頂 c0（紺）と横の端の頂 c_side（灰）の時間の変化", fill=TXT, font=font(15, True))
        dr.rectangle([px0, py0, px1, py1], fill=WHITE, outline=(150, 150, 150))
        L, R, T, B = px0 + 44, px1 - 10, py0 + 6, py1 - 6
        hi = self.cy_hi
        X = lambda t: L + (t - self.ta) / max(self.tb - self.ta, 1e-6) * (R - L)
        Y = lambda v: B - min(max(v, 0.0), hi) / hi * (B - T)
        for g in (0, 4, 8, 12):
            if g <= hi:
                dr.line([(L, Y(g)), (R, Y(g))], fill=(232, 232, 232))
                dr.text((px0 + 4, Y(g) - 8), "%d m" % g, fill=SUB, font=font(11))
        if self.slow_t:
            dr.rectangle([X(max(self.slow_t[0], self.ta)), T, X(min(self.slow_t[1], self.tb)), B], fill=(253, 236, 214))
        for tm, col in self.marks_t():
            if tm is not None and self.ta <= tm <= self.tb:
                dr.line([(X(tm), T), (X(tm), B)], fill=col, width=2)
        if len(self.ct_f) > 1:
            ts = [r.tf[q] for q in self.ct_f]
            okk = np.isfinite(self.ct_cs)
            if okk.sum() > 2:
                up_ = [(X(a_), Y(b_)) for a_, b_, k_ in zip(ts, self.ct_c0, okk) if k_]
                lo_ = [(X(a_), Y(b_)) for a_, b_, k_ in zip(ts, self.ct_cs, okk) if k_]
                dr.polygon(up_ + lo_[::-1], fill=(205, 218, 240))
            dr.line([(X(a), Y(b)) for a, b in zip(ts, self.ct_cs) if np.isfinite(b)], fill=(140, 140, 140), width=2)
            dr.line([(X(a), Y(b)) for a, b in zip(ts, self.ct_c0)], fill=NAVY, width=2)
        u = X(r.tf[f])
        dr.line([(u, T), (u, B)], fill=(0, 0, 0), width=1)
        if r.crest_valid(f):
            L_ = r.lat(f)
            dr.ellipse([u - 4, Y(L_["c0"]) - 4, u + 4, Y(L_["c0"]) + 4], fill=NAVY)
        fz = font(11)                                            # 横軸＝時刻（下の時刻の帯と同じ範囲）
        GV.label_box(dr, (L + 2, B - 15), "t %.1f s" % self.ta, SUB, fz)
        lb = "%.1f s（横軸＝時刻）" % self.tb
        GV.label_box(dr, (R - 4 - dr.textlength(lb, font=fz), B - 15), lb, SUB, fz)

    def marks_t(self):
        r = self.r
        out = []
        if r.on:
            out.append((r.on["t"], ORANGE))
            if r.td:
                out.append((r.td["t"], PURP))
            if self.best_f is not None:
                out.append((r.tf[self.best_f], RED))
        elif r.steep:
            out.append((r.steep["t"], GREY))
        return out

    # ---- B0 全部の断面
    def draw_strip(self, im, dr, f):
        r = self.r

        class _D:
            pass
        D = _D(); D.R2 = r.cx.R2; D.off = r.off; D.cx = r.cx; D.ridge = False; D.ana = {}
        x0, x1 = r.cx.x_min, r.cx.x_max
        zlo, zhi = -8.0, 14.0
        dr.text((40, self.B0y - 22), "領域の全部（y = 0.5 m の断面、x %.0f〜%.0f m、縦横同じ縮尺。赤の細い枠＝下の拡大の窓）" % (x0, x1), fill=TXT, font=font(15, True))
        ph = V46.section(im, dr, D, f, (40, self.B0y, 1160), x0, x1, zlo, zhi, None, tick=50.0, marks=False)
        s = 1120.0 / (x1 - x0)
        zx0 = self.zoom_x0(f)
        a, b = max(zx0, x0), min(zx0 + self.zoom_w, x1)
        Yz = lambda z: self.B0y + (zhi - z) * s
        if a < b:
            dr.rectangle([40 + (a - x0) * s, Yz(min(self.z1, zhi)), 40 + (b - x0) * s, Yz(max(self.z0, zlo))], outline=RED, width=2)

    def zoom_x0(self, f):
        r = self.r
        return min(r.zcam[f] - r.zoom_at(f) * self.zoom_w, r.cx.x_max + 4.0 - self.zoom_w)    # 窓の右の端は壁の 4 m 外まで

    # ---- B1 拡大
    def draw_zoom(self, im, dr, f, red):
        r = self.r
        zx0 = self.zoom_x0(f)
        bx = GV.Box(40, self.zy, self.zs, zx0, zx0 + self.zoom_w, self.z0, self.z1)
        dr.text((40, self.zy - 29), "真ん中の断面の拡大（y 0.5 m の行、記録 r2・1 m の格子。頂を追う窓、幅 %.0f m、縦横同じ縮尺）" % self.zoom_w,
                fill=TXT, font=font(17, True))
        best = (f == self.best_f)
        drawn, ylat, nfill = draw_section(im, dr, r, f, bx, best=best)
        m = r.meas.get(f)
        if drawn:
            lab = "黒＝原画の輪郭（縦の伸びを戻した形）を、このコマの η_c %.2f m と頂の x %.1f m に合わせて重ねた" % (m["eta_c"], m["x_c"])
            GV.label_box(dr, (bx.px + 8, bx.py + bx.ph - 48), lab, (0, 0, 0), font(14, best))
        elif r.on and r.tf[f] < r.on["t"]:
            GV.label_box(dr, (bx.px + 8, bx.py + 6), "原画の輪郭は巻き始め（t %.2f s）から%s（t %.2f s）まで重ねる" % (r.on["t"], self.end_word, r.end_t), SUB, font(14))
        elif r.on and r.tf[f] > r.end_t:
            GV.label_box(dr, (bx.px + 8, bx.py + 6), "原画の輪郭を重ねるのは巻き始め〜%s（t %.2f s）まで。今はその後" % (self.end_word, r.end_t), SUB, font(14))
        elif not r.on:
            GV.label_box(dr, (bx.px + 8, bx.py + 6), "この計算は巻かない（前の面が鉛直にならない）。原画とは比べない", SUB, font(14))
        GV.label_box(dr, (bx.px + bx.pw - 520, bx.py + bx.ph - 22), "青＝水、砂色＝海底。海底のすぐ上の空気の層（FLIP）は上が水なら水に塗った（描くだけ）",
                     SUB, font(12))
        if red:
            self.red_label(dr, bx.px + 8, bx.py + 6)
        self.zbox = (bx.px, bx.py, bx.px + bx.pw, bx.py + bx.ph)

    # ---- B2 重ねと表（g47_video.draw_overlay の写し。原画に最も近い瞬間を赤に）
    def draw_overlay(self, im, dr, f):
        r = self.r
        x0, y0 = self.ovx, self.ovy
        s = self.os_
        pw = int((self.XR - self.XL) * s); ph = int((self.ZT - self.ZB) * s)
        self.ovbox = (x0, y0, x0 + pw, y0 + ph)
        dr.text((x0, y0 - 29), "同じ物差しの重ね（η_c で割り、頂の位置をそろえた。巻いている間だけ）", fill=TXT, font=font(17, True))
        dr.rectangle([x0, y0, x0 + pw, y0 + ph], fill=WHITE, outline=(150, 150, 150))
        tr = lambda P: np.stack([x0 + (P[:, 0] - self.XL) * s, y0 + (self.ZT - P[:, 1]) * s], 1)
        t = r.tf[f]
        on = bool(self.ov_t and self.ov_t[0] - 1e-9 <= t <= self.ov_t[1] + 1e-9)
        m = r.meas.get(f) if on else None
        bf = self.best_f
        if not r.on:
            msg = "巻かないので比べない"
            dr.text((x0 + pw / 2 - dr.textlength(msg, font=font(18)) / 2, y0 + ph / 2 - 10), msg, fill=SUB, font=font(18))
        elif not on or not m or not m.get("lines"):
            win = "重ねるのは巻き始め〜%sの 0.5 s 後（t %.2f〜%.2f s）だけ" % (self.end_word, self.ov_t[0], self.ov_t[1])
            msg = ("まだ巻いていない。" if t < self.ov_t[0] else ("その時を過ぎた。" if t > self.ov_t[1] else "このコマは測れなかった。")) + win
            dr.text((x0 + pw / 2 - dr.textlength(msg, font=font(15)) / 2, y0 + ph / 2 - 10), msg, fill=SUB, font=font(15))
        else:
            for zv in (-0.25, 0.0, 0.25, 0.5, 0.7, 1.0):
                yy = y0 + (self.ZT - zv) * s
                dr.line([(x0, yy), (x0 + pw, yy)], fill=(110, 110, 110) if zv == 0 else (228, 228, 228), width=2 if zv == 0 else 1)
                dr.text((x0 - 34, yy - 8), "%g" % zv, fill=SUB, font=font(12))
            for xv in np.arange(-2.0, self.XR + 1e-6, 0.5):
                xx = x0 + (xv - self.XL) * s
                dr.line([(xx, y0 + ph), (xx, y0 + ph - 6)], fill=(120, 120, 120))
                dr.text((xx - 8, y0 + ph + 2), "%g" % xv, fill=SUB, font=font(11))
            box = (self.XL, self.XR, self.ZB, self.ZT)
            pr = GV.print_ref()
            for q in pr["drawn"]:
                for Pp in GV.split_inside(q, *box):
                    GV.poly(dr, tr(Pp), GREY, 2, dash=True)
            for q in pr["cn"]:
                for Pp in GV.split_inside(q, *box):
                    GV.poly(dr, tr(Pp), (0, 0, 0), 4)
            if bf is not None and f > bf and r.meas.get(bf, {}).get("lines"):
                for q in ov_keep(r.meas[bf]["lines"]):
                    for Pp in GV.split_inside(q, *box):
                        GV.poly(dr, tr(Pp), RED, 2)
            for q in ov_keep(m["lines"]):
                for Pp in GV.split_inside(q, *box):
                    GV.poly(dr, tr(Pp), RED if f == bf else BLUE, 3)
        yl = y0 + ph + 26                       # 横の目盛りの字（y0 + ph + 2〜18）と赤の太い枠（〜y0 + ph + 22）の下に置く
        items = [("原画（伸びを戻した形）", (0, 0, 0), False), ("原画（描かれたまま）", GREY, True), ("このコマ", BLUE, False)]
        if bf is not None:
            items.append(("最も近い瞬間（コマ %d）" % bf, RED, False))
        xx = x0
        for lab, col, dsh in items:
            if dsh:
                GV.dashed(dr, [(xx, yl + 8), (xx + 26, yl + 8)], col, 3)
            else:
                dr.line([(xx, yl + 8), (xx + 26, yl + 8)], fill=col, width=4)
            dr.text((xx + 30, yl), lab, fill=TXT, font=font(12))
            xx += 30 + dr.textlength(lab, font=font(12)) + 12
        yt = yl + 24
        mm = r.meas.get(f) if (r.on and r.on["t"] - 1.0 - 1e-9 <= t <= r.end_t + 0.5 + 1e-9) else None
        dr.text((x0, yt), "同じ物差しの量（η_c で割った値）", fill=TXT, font=font(14, True))
        dr.text((x0 + 320, yt), "このコマ", fill=TXT, font=font(14, True))
        dr.text((x0 + 420, yt), "原画 cn（4 つの読みの帯）", fill=TXT, font=font(14, True))
        yt += 21
        if mm is None or mm.get("m") is None:
            msg = ("測るのは巻き始めの 1 s 前〜%sの 0.5 s 後だけ" % self.end_word) if r.on else "巻かないので測らない"
            if mm is not None and mm.get("m") is None:
                msg = "このコマは測れなかった（%s）" % str(mm.get("err") or "")[:60]
            for lab, val, ptxt, col in GV.measure_rows(None):
                dr.text((x0, yt), lab, fill=SUB, font=font(13)); dr.text((x0 + 420, yt), ptxt, fill=SUB, font=font(13))
                yt += 18
            dr.text((x0, yt + 2), msg, fill=SUB, font=font(13))
        else:
            for lab, val, ptxt, col in GV.measure_rows(mm["m"]):
                dr.text((x0, yt), lab, fill=TXT, font=font(13))
                dr.text((x0 + 320, yt - 1), val, fill=col, font=font(14, True))
                dr.text((x0 + 420, yt), ptxt, fill=SUB, font=font(13))
                yt += 18
            dr.text((x0, yt + 2), "η_c %.2f m、頂 x %.1f m。score3 %s（弦・足・覆いの帯の外れ、0 が帯の中）" % (mm["eta_c"], mm["x_c"], GV.fmt(mm.get("score3"), "%.2f")),
                    fill=TXT, font=font(13, True))
            GV.text_fit(dr, (x0, yt + 21), "出どころ：g46_analyze.r2_mask → STUDY52 measure_mask（ana.json と同じ）。緑＝帯の中、赤＝外", 640, 12, fill=SUB)
            GV.text_fit(dr, (x0, yt + 37), "重ねの図には、静かな水面より下に閉じた輪郭（海底のすぐ上の FLIP の空気の層）は描かない（描くだけ。測りは変えない）", 640, 12, fill=SUB)

    def render(self, f, state):
        r = self.r
        im = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(im)
        red = (self.best_f is not None) and (state in ("hold", "end") or f == self.best_f)
        self.header(dr, f, state)
        self.draw_3d(im, dr, f, red)
        self.draw_cy(im, dr, f)
        self.draw_ct(im, dr, f)
        self.draw_strip(im, dr, f)
        self.draw_zoom(im, dr, f, red)
        self.draw_overlay(im, dr, f)
        marks = []
        if r.on:
            marks.append((r.on["t"], "巻き始め", ORANGE))
            if r.td:
                marks.append((r.td["t"], "着水", PURP))
            if self.best_f is not None:
                marks.append((r.tf[self.best_f], "原画に最も近い", RED))
        elif r.steep:
            marks.append((r.steep["t"], "最も険しい（巻かない）", GREY))
        GV.timebar(dr, 40, W - 40, H - 44, self.ta, self.tb, r.tf[f], marks, self.slow_t, head="t ")
        if red:
            ox0, oy0, ox1, oy1 = self.ovbox          # 重ねは目盛りの字（左 34 px・下 16 px）も枠の中に入れる
            for (a, b, c, d) in (self.A1, self.zbox, (ox0 - 34, oy0, ox1, oy1 + 16)):
                dr.rectangle([a - 6, b - 6, c + 6, d + 6], outline=RED, width=5)
        return im

    def schedule(self):
        r = self.r
        out, acc, emitted = [], 0.0, 0
        for f in self.fr:
            t = r.tf[f]
            if self.slow_t and self.slow_t[0] - 1e-9 <= t <= self.slow_t[1] + 1e-9:
                sp, st = self.slow, "slow"
            elif t < self.fast_until - 1e-9 and self.fast > 1.0:
                sp, st = self.fast, "fast"
            else:
                sp, st = 1.0, "real"
            acc += 1.0 / sp
            n = int(math.floor(acc + 1e-9)) - emitted
            emitted += n
            if n > 0:
                out.append((f, n, st))
            if f == self.best_f and self.hold_s > 0:
                out.append((f, int(round(self.hold_s * FPS)), "hold"))
        if self.best_f is not None and self.best_f in self.fr and self.end_hold_s > 0:
            out.append((self.best_f, int(round(self.end_hold_s * FPS)), "end"))
        return out


def out_dir_for(run, opt):
    if opt.get("out"):
        return guard_out(opt["out"])
    if run.stage == "FLIP48" and run.rd.lower().startswith(B48.lower()):
        return guard_out(os.path.join(run.rd, "video"))
    return guard_out(B48 + "/compare46")


def still_frame(run, cv, which):
    if which in ("best", "1") and cv.best_f is not None:
        return cv.best_f
    if which == "onset" and run.on:
        return run.on["f"]
    if which == "td" and run.td:
        return run.td["f"]
    if which == "steep" and run.steep:
        return run.steep["f"]
    try:
        return int(which)
    except ValueError:
        return cv.best_f or run.ev_f


def make_video(ref, opt, log=print):
    t_start = time.time()
    run = Run(ref, opt, log=log)
    cv = CompareVideo(run, opt)
    out = out_dir_for(run, opt)
    os.makedirs(out, exist_ok=True)
    name = opt.get("name") or ("%s_compare" % run.rid)
    if opt.get("still") is not None:
        res = []
        for w in str(opt["still"]).split(","):
            f = still_frame(run, cv, w)
            st = "hold" if f == cv.best_f else ("slow" if cv.slow_t and cv.slow_t[0] <= run.tf[f] <= cv.slow_t[1] else ("fast" if run.tf[f] < cv.fast_until else "real"))
            p = os.path.join(out, "%s_f%05d.png" % (name, f))
            cv.render(f, st).save(p)
            log("wrote", p); res.append(p)
        return dict(stills=res, best=cv.best_f, checks=run.checks)
    sch = cv.schedule()
    nren = len(sch)
    vt, acc_t = {}, 0.0                     # 動画の中の時刻（止めの始まりなど。確かめのコマを抜く時に使う）
    for f_, n_, st_ in sch:
        vt.setdefault(st_, [round(acc_t, 3), None, f_])
        vt[st_][1] = round(acc_t + n_ / FPS, 3)
        acc_t += n_ / FPS
    path = os.path.join(out, name + ".mp4")
    log("frames to render %d, video frames %d (%.1f s)" % (nren, sum(n for _, n, _ in sch), sum(n for _, n, _ in sch) / FPS))
    wr = GV.Writer(path)
    last = None
    t_r = time.time()
    for i, (f, n, st) in enumerate(sch):
        im = cv.render(f, st)
        wr.put(im, n)
        if st == "hold":
            im.save(os.path.join(out, name + "_best.png"))
        if i % 20 == 0:
            log("  %d/%d f%d %s %.0f s" % (i, nren, f, st, time.time() - t_r))
    wr.close()
    pb = GV.probe(path)
    info = dict(video=path, made=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " run", opt=opt, run=run.rid, rd=run.rd, stage=run.stage,
                still_offset_m=run.off, frames_window=[cv.fr[0], cv.fr[-1]], t_window=[cv.ta, cv.tb],
                onset=dict(frame=run.on["f"], t=run.on["t"], xc=run.on["x"], eta_c=run.on["Hc"], src="ana.json onset") if run.on else None,
                touchdown=dict(frame=run.td["f"], t=run.td["t"], src="ana.json touchdown") if run.td else None,
                steepest=run.steep, end=dict(frame=run.end_f, t=run.end_t, src=run.end_src) if run.on else None,
                best=dict(frame=cv.best_f, t=run.tf[cv.best_f], src=run.best_src, score3=run.meas[cv.best_f]["score3"], parts=run.meas[cv.best_f]["parts"],
                          m=run.meas[cv.best_f]["m"], eta_c=run.meas[cv.best_f]["eta_c"], x_c=run.meas[cv.best_f]["x_c"],
                          best_at_window_end=bool(getattr(run, "best_at_end", False))) if cv.best_f is not None else None,
                lateral_best=run.lat(cv.best_f) if cv.best_f is not None else None,
                lateral_event=run.lat(run.ev_f) if run.ev_f in run.hidx else None,
                Hc=run.Hc, Hc_src=run.Hc_src, track_src=run.track_src,
                speed=dict(fast=cv.fast, fast_until_t=cv.fast_until, slow=cv.slow, slow_t=cv.slow_t, hold_s=cv.hold_s, end_hold_s=cv.end_hold_s),
                camera3d=(dict(mode="high", Dx_ahead_of_crest_m=cv.v3.Dx, z_m=cv.v3.h, pitch_deg=cv.v3.pitch, hfov_deg=cv.v3.hfov, x_cap_m=run.cx.x_max + 12.0,
                               note_ja="透視。目は真ん中の頂（均した x）の Dx m 前・y 0・高さ z、pitch° 見下ろし、頂を追う（壁の 12 m 外で止める）。縦は伸ばしていない。色は高さ（原画の色ではない）")
                          if cv.v3.mode == "high" else
                          dict(mode="eye", D=run.cam_D, h=run.cam_h, hfov_deg=run.cam_hfov, D_eff=run.cam_D_eff, frozen_at_t=run.ev_t,
                               x_at_event=run.cam3.get(run.ev_f), note_ja="透視。目は y 0、静かな水面 + h。出来事の時に止めた。色は高さ（原画の色ではない）")),
                zoom=dict(width_m=cv.zoom_w, z=[cv.z0, cv.z1], px_per_m=cv.zs),
                checks=dict(run.checks, peak_vs_live_lateral_onset=run.peak_check()), schedule_n=len(sch),
                video_times_s={k: dict(first=v[0], last_end=v[1], first_frame=v[2]) for k, v in vt.items()},
                written_frames=wr.n, ffprobe=pb, ok=bool(pb.get("ok") and pb.get("frames") == wr.n), elapsed_s=round(time.time() - t_start, 1))
    json.dump(A46._clean(info), open(os.path.join(out, name + ".json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    log(json.dumps(A46._clean(dict(video=path, ok=info["ok"], ffprobe=pb, best=info["best"] and {k: info["best"][k] for k in ("frame", "t", "score3")},
                                   checks=info["checks"], elapsed_s=info["elapsed_s"])), ensure_ascii=False))
    return info


# ======================================================================== 並べた 1 枚
def mini_cy(dr, run, f, box, hi=12.0):
    """小さな c(y) のグラフ（縦を伸ばした）。横の端より高い分を薄く塗る。並べた 1 枚の 3D の空の所に置く。"""
    px0, py0, px1, py1 = box
    dr.rectangle(box, fill=WHITE, outline=(120, 120, 120))
    L, R, T, B = px0 + 30, px1 - 6, py0 + 18, py1 - 6
    ys = run.ys; Wf = float(ys[-1] + 0.5 * (ys[1] - ys[0]))
    X = lambda v: L + (v + Wf) / (2 * Wf) * (R - L)
    Y = lambda v: B - min(max(v, 0.0), hi) / hi * (B - T)
    for g in (0, 4, 8, 12):
        dr.line([(L, Y(g)), (R, Y(g))], fill=(232, 232, 232))
        dr.text((px0 + 3, Y(g) - 7), "%d" % g, fill=SUB, font=font(10))
    dr.text((px0 + 4, py0 + 2), "c(y)（縦を伸ばした、0〜12 m、y ±%g m）" % Wf, fill=TXT, font=font(11, True))
    c, _, _ = run.prof(f)
    yy = np.concatenate([-ys[::-1], ys]); cc = np.concatenate([c[::-1], c])
    L_ = run.lat(f)
    if L_.get("c_side") is not None:
        csd = L_["c_side"]
        poly_ = [(X(a_), Y(max(b_, csd))) for a_, b_ in zip(yy, cc) if np.isfinite(b_)]
        if len(poly_) > 2:
            dr.polygon(poly_ + [(X(yy[-1]), Y(csd)), (X(yy[0]), Y(csd))], fill=(205, 218, 240))
        dr.line([(L, Y(csd)), (R, Y(csd))], fill=(140, 140, 140), width=1)
    if run.Hc:
        for mlt, colr in ((2, C2), (4, C4)):
            for sg in (-1, 1):
                dr.line([(X(sg * mlt * run.Hc), T), (X(sg * mlt * run.Hc), B)], fill=colr, width=1)
        GV.dashed(dr, [(L, Y(run.Hc)), (R, Y(run.Hc))], (0, 0, 0), 1, 5, 4)
    pts = [(X(a_), Y(b_)) for a_, b_ in zip(yy, cc) if np.isfinite(b_)]
    if len(pts) > 1:
        dr.line(pts, fill=NAVY, width=2)


def make_lineup(refs, opt, log=print):
    rows = []
    for ref in refs:
        run = Run(ref, opt, log=log)
        run.measure()
        run.cam3d_setup(float(opt.get("D", 45.0)), float(opt.get("h", 6.0)), float(opt.get("hfov", 80.0)))
        f = run.best_f if run.best_f is not None else run.ev_f
        rows.append((run, f))
        log("lineup", run.rid, "frame", f)
    RH = 360; TW = 1920
    TOP = 92
    im = Image.new("RGB", (TW, TOP + RH * len(rows)), BG); dr = ImageDraw.Draw(im)
    dr.text((30, 10), "FLIP48 の 3D の計算を並べる：各々の原画に最も近い瞬間（score3 最小。巻かなければ最も険しいコマ）", fill=TXT, font=font(24, True))
    GV.text_fit(dr, (30, 44), "左＝波の前から斜めに見下ろした 3D（縦は伸ばしていない。色＝高さ、紺＝各横位置の頂、黄土・茶＝y ±2・±4 Hc。"
                "左上の小さなグラフ＝c(y)（縦を伸ばした）、薄い青＝横の端より高い分、黒の破線＝Hc）", TW - 60, 15, fill=SUB)
    GV.text_fit(dr, (30, 66), "右＝真ん中の断面（縦横同じ縮尺）に原画の輪郭（縦の伸びを戻した形、黒）を η_c と頂の x に合わせて重ねた。赤の枠＝原画に最も近い瞬間（巻かない計算は灰の枠）",
                TW - 60, 15, fill=SUB)
    for i, (run, f) in enumerate(rows):
        y = TOP + i * RH
        L_ = run.lat(f)
        d = run.meas.get(f) or {}
        m = d.get("m") or {}
        if run.best_f is not None:
            tl = "%s　コマ %d（t %.2f s、巻き始めから %+.2f s%s）　score3 %.2f・弦 %.1f°・足 %.2f・覆い %.3f　|　Hc %.2f m・c0/c_side %s・c0/c(4Hc) %s・半分の幅 %s m（%s Hc）" % (
                run.rid, f, run.tf[f], run.tf[f] - run.on["t"], "、窓の端＝着水のコマ" if getattr(run, "best_at_end", False) and run.td else "", d.get("score3") or 0, m.get("face_chord_deg_01_05") or 0, m.get("front_x01_rel") or 0,
                m.get("hood_area") or 0, run.Hc, GV.fmt(L_.get("ratio_side"), "%.2f"), GV.fmt(L_.get("ratio_4Hc"), "%.2f"),
                GV.fmt(L_.get("half_excess_width_m"), "%.0f"), GV.fmt(L_.get("half_excess_width_over_Hc"), "%.1f"))
        else:
            tl = "%s　巻かない：最も険しいコマ %d（t %.2f s、前の面の最大の角 %s°）　|　頂 %.2f m・c0/c_side %s・c0/c(4Hc) %s・半分の幅 %s m" % (
                run.rid, f, run.tf[f], GV.fmt((run.steep or {}).get("thmax"), "%.0f"), run.Hc or 0, GV.fmt(L_.get("ratio_side"), "%.2f"),
                GV.fmt(L_.get("ratio_4Hc"), "%.2f"), GV.fmt(L_.get("half_excess_width_m"), "%.0f"))
        GV.text_fit(dr, (30, y + 6), tl, TW - 60, 17, True)
        v3 = View3D(run, 980, RH - 46, ss=int(opt.get("ss", 2)))
        img, _ = v3.draw(f, small=True)
        mini_cy(ImageDraw.Draw(img), run, f, (8, 6, 330, 94))
        im.paste(img, (30, y + 34))
        z0, z1 = -4.0, 13.0
        s = (RH - 46 - 20) / (z1 - z0)
        wz = (TW - 30 - 1040) / s
        xc = d.get("x_c") or run.track_x(f)
        bx = GV.Box(1040, y + 34, s, xc - 0.62 * wz, xc + 0.38 * wz, z0, z1)
        draw_section(im, dr, run, f, bx, small=True, best=True)
        if run.best_f is not None:
            dr.rectangle([1040 - 3, y + 31, 1040 + bx.pw + 3, y + 34 + bx.ph + 3], outline=RED, width=4)
    p = guard_out(opt.get("out") or (B48 + "/runs/LINEUP_best.png"))
    im.save(p)
    log("wrote", p)
    return p


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    pos, opt = parse_opt(sys.argv[1:])
    if not pos:
        print(__doc__); sys.exit(1)
    cmd = pos[0]
    try:
        if cmd == "run":
            for ref in pos[1:]:
                make_video(ref, opt)
        elif cmd == "lineup":
            make_lineup(pos[1:], opt)
        else:
            print(__doc__); sys.exit(1)
    except InputError as e:
        print("止めた：%s" % e); sys.exit(2)


if __name__ == "__main__":
    main()
