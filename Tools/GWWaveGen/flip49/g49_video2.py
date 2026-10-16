# -*- coding: utf-8 -*-
"""FLIP49：周期の波の計算の比べの動画（崩れごと）と、計算の全部を見る動画（py -3.10 -B。numpy・scipy・scikit-image・PIL・ffmpeg）。
2026-10-15 新しく書いた（方案 A を実装する役、Claude）。利用者の 10/15 の頼み（Q71：原画に最も近い瞬間を赤い枠で囲み、原画との比べが見えるように。
真ん中への集まりが見えるように）と、指導教員の長い動画の頼み（Q66）に答える。D0 の動画（g49_video.py の 3D の並べ方）は、g48_video の図の上に
字を重ねて読めず、拡大の窓が最も近いコマの頂を外していた。その直し。

読み込んで使う物（どれも変えていない）：
  g49_periodic_ana（Ctx49：海底は g49_common.bed_z。crest_prof：c(y) の読みを peak.json と同じ関数で。読み込むと A46.Ctx・A48.Ctx48 が
    この起動の中だけ Ctx49 になる）
  g48_video2（FLIP48 の比べの動画）の Run・CompareVideo・View3D・draw_section・sec_raster：崩れごとに 1 つの Run49（その崩れの
    pana/waves/kNN/ana.json）を作り、同じ図（3D の前から斜めに見下ろす図・c(y)・c0 と c_side の時間の変化・全部の断面・拡大・同じ物差しの重ねと表・
    時刻の帯）で描く。3D の図の貯め置きは Unity/Build/FLIP49/_cache/video2_3d に（この起動の中だけ G2.CACHE3D を替える）
  g47_video（原画の輪郭 print_phys・score3・measure_rows・Box・timebar・Writer・probe）

1. 比べの動画（compare）：<記録>/video/<run_id>_compare.mp4
   pana/periodic_ana.json の崩れ（来た波の崩れ k。判定する t ≥ 45 s の物と、判定しない物は頭書きで分ける）ごとに、巻き始めの 4 s 前〜着水 + 2 s を：
   巻き始めの 1 s 前までは 2 倍の早送り、巻き始めの 1 s 前〜着水 + 0.5 s は 0.25 倍のスロー、原画に最も近いコマ（pana/best_frames.json、凍らせた決まり、
   score3 の最小）で 3 s 止め、その間は 3D・拡大・重ねを太い赤の枠で囲む。拡大の窓は、最も近いコマの頂 x_c が窓の前の端から 20 m 以上、後ろの端から
   0.2 × 幅以上内側に入るよう、比べの間（巻き始め − 1 s〜着水 + 0.5 s、前後 0.75 s で滑らかに）ずらす（assert で確かめる）。
   板（半幅 ≤ 12 m）は 3D と c(y) の代わりに崩れごとの表と波高計の時系列を置く。
2. 全部の動画（whole）：<記録>/video/<run_id>_whole.mp4
   計算の全部を 2 倍の早送りで（原画に最も近いコマで 1 s 止めて赤い枠）。上から見た水面（両側、縦横同じ縮尺、色＝高さ）と各崩れの頂の線、
   崩れごとの表（P1〜P5 の ○×）、全部の断面、今の崩れの頂を追う拡大（原画の輪郭）、波高計 x 110・128・160 m（y 0.5 m と 80 m）の時系列、時刻の帯。
字の重なり：描いた字の枠（ImageDraw.text を全部記録する）を 1 コマごとに比べ、4 画素² より大きく重なる組を数える。比べの動画の
  原画に最も近いコマ・巻き始め・早送りのコマでは 0 であることを assert する（動画の json に全部のコマの数を書く）。
使い方：
  py -3.10 -B g49_video2.py compare <記録> [--k=2,3] [--still=best|onset|<コマ>] [--fast=2] [--slow=0.25] [--hold=3] [--ss=2]
  py -3.10 -B g49_video2.py whole <記録> [--speed=2] [--hold=1] [--still=<コマ>|best]
  py -3.10 -B g49_video2.py all <記録>            （両方）
  先に py -3.10 -B g49_periodic_ana.py all <記録>（pana/periodic_ana.json・best_frames.json・waves/kNN/ana.json）。
出す物は Unity/Build/FLIP49 の中だけ。数の印：形の量・score3 は AI の読み（g49_periodic_ana の値と同じ関数）。原画らしさは利用者が決める。
"""
import os, sys, json, math, time, types

sys.dont_write_bytecode = True
_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip45", r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip46",
           r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip47", r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip48", _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import numpy as np                       # noqa: E402
from PIL import Image, ImageDraw         # noqa: E402
import g49_common as GC                  # noqa: E402
import g49_periodic_ana as PA            # noqa: E402  先に読む（A48.Ctx48 = Ctx49）
import g48_video2 as G2                  # noqa: E402  読むだけ（変えない）
import g48_peak_metrics as PM            # noqa: E402

GV = G2.GV
A46 = G2.A46
V46 = G2.V46
font = G2.font
W, H, FPS = G2.W, G2.H, G2.FPS
BG, TXT, SUB, RED, NAVY, WHITE = G2.BG, G2.TXT, G2.SUB, G2.RED, G2.NAVY, G2.WHITE
ORANGE, BLUE, PURP, GREY, GREEN = G2.ORANGE, G2.BLUE, G2.PURP, G2.GREY, G2.GREEN
C2_, C4_ = G2.C2, G2.C4
G2.CACHE3D = GC.B49 + "/_cache/video2_3d"   # この起動の中だけ（3D の図の貯め置きを FLIP49 の中に）
TOOL = "Tools/GWWaveGen/flip49/g49_video2.py"


# ======================================================================== 字の枠の記録（重なりの確かめ）
class TextRec:
    def __init__(self):
        self.boxes = []
        self.main = None
        self.pending = (0, 0)
        self.on = True

    def reset(self, main_img):
        self.boxes = []
        self.main = id(main_img)


REC = TextRec()


class RecDraw(ImageDraw.ImageDraw):
    """ImageDraw の text を記録する（画面の座標に直して）。"""
    def text(self, xy, text, fill=None, font=None, *a, **k):
        nested = getattr(self, "_in_text", False)
        if REC.on and not nested and text and str(text).strip():
            try:
                l_, t_, r_, b_ = self.textbbox(xy, text, font=font)
                wi, hi = self.im.size                       # 図の外にはみ出た字は描かれない（切れる）ので、図の中の分だけ数える
                l_, t_, r_, b_ = max(l_, 0), max(t_, 0), min(r_, wi), min(b_, hi)
                ox, oy = self._rec_ofs
                if r_ > l_ and b_ > t_:
                    REC.boxes.append((l_ + ox, t_ + oy, r_ + ox, b_ + oy, str(text)))
            except Exception:
                pass
        self._in_text = True                    # 複数行の字は PIL の中で行ごとに text が呼ばれる（二度数えない）
        try:
            return super().text(xy, text, fill, font, *a, **k)
        finally:
            self._in_text = nested


def rec_draw(im, mode=None):
    d = RecDraw(im, mode)
    d._rec_ofs = (0, 0) if id(im) == REC.main else REC.pending
    return d


G2.ImageDraw = types.SimpleNamespace(Draw=rec_draw)        # この起動の中だけ（g48_video2 の図の字も記録する）


def overlaps(boxes, min_area=4.0):
    out = []
    for i in range(len(boxes)):
        a = boxes[i]
        for j in range(i + 1, len(boxes)):
            b = boxes[j]
            w = min(a[2], b[2]) - max(a[0], b[0]); h = min(a[3], b[3]) - max(a[1], b[1])
            if w > 0 and h > 0 and w * h > min_area and not (a[4] == b[4] and abs(a[0] - b[0]) < 1 and abs(a[1] - b[1]) < 1):
                out.append((a[4][:40], b[4][:40], round(w * h)))
    return out


def _g(v, f="%.2f"):
    return "—" if v is None else (f % v)


# ======================================================================== 記録の共有（崩れごとの Run49 が使う）
class Shared:
    def __init__(self, rd, log=print):
        t0 = time.time()
        self.rd = os.path.abspath(rd).replace("\\", "/").rstrip("/")
        self.rid = os.path.basename(self.rd)
        self.log = log
        od = os.path.join(self.rd, "pana")
        p = os.path.join(od, "periodic_ana.json")
        if not os.path.exists(p):
            raise G2.InputError("先に py -3.10 -B g49_periodic_ana.py all %s（%s がない）" % (self.rd, p))
        self.pa = json.load(open(p, encoding="utf8"))
        self.cx = PA.Ctx49(self.rd, {})
        cx = self.cx
        self.cfg = cx.cfg49
        self.off = float(cx.off)
        P = self.cfg.get("parms") or {}
        self.Wd = float(P.get("W", 85.0)); self.strip = self.Wd <= 12.0
        self.T = float((self.cfg.get("sf") or {}).get("T", GC.T_WAVE))
        # 描くための x の範囲：記録の終わりまで（拡大の窓が最も近いコマの頂を外さないように。崩れを探す窓 x_min〜x_max は ana が使った物）
        self.x_search = (float(cx.x_min), float(cx.x_max))
        cx.x_max = float(cx.x_dom[1])
        self.tf = G2.block_times(cx.R2)
        self.H = PM.load_hf(self.rd)
        self.hidx = {int(f): i for i, f in enumerate(self.H["frames"])}
        self.frames = [int(f) for f in cx.R2.frames if f >= 2 and int(f) in self.hidx and f in cx.R1.b]
        self.ev = [dict(e, lab="k%d" % int(e["k"])) for e in (self.pa.get("events_found") or [])]
        # 判定の窓の字。既定は periodic_ana の judged（巻き始め t ≥ 45 s）。2026-10-16 campaign B の 2D の板（cfg の case.judged_onset_window_s、
        # plan_B_frozen.json judged_breaker_strip）は巻き始め 45〜80 s だけを判定し、後の崩れは報告だけ（礁を越えた水が横へ戻れず水位が上がる
        # 2D の作り物）。その窓で judged を読み直す（数は変えない。字と表の色だけ）
        jw = (self.cfg.get("case") or {}).get("judged_onset_window_s")
        if jw:
            for e in self.ev:
                e["judged"] = bool(float(jw[0]) - 1e-9 <= float(e["on_t"]) <= float(jw[1]) + 1e-9)
            win = "巻き始め %g〜%g s" % (float(jw[0]), float(jw[1]))
            self.judge_txt = ("判定する（%s）" % win, "判定しない（報告だけ。%s の外）" % win)
            self.grey_txt = "灰＝判定しない（%s の外、報告だけ）" % win
            self.judge_head = "判定は真ん中の%s" % win
        else:
            self.judge_txt = ("判定する（t ≥ %g s）" % GC.T_JUDGE, "判定しない（入口の立ち上がりの間、t < %g s）" % GC.T_JUDGE)
            self.grey_txt = "灰＝判定しない（t < %g s）" % GC.T_JUDGE
            self.judge_head = "判定は真ん中の巻き始め t ≥ %g s" % GC.T_JUDGE
        self.rows = {"k%d" % int(r["k"]): r for r in (self.pa.get("waves") or [])}
        bp = os.path.join(od, "best_frames.json")
        self.bf = json.load(open(bp, encoding="utf8")) if os.path.exists(bp) else {}
        self.best = {"k%d" % int(r["k"]): r for r in (self.bf.get("per_breaker") or []) if r.get("frame") is not None}
        self.ana, self.peak = {}, {}
        for e in self.ev:
            wd = os.path.join(od, "waves", "k%02d" % int(e["k"]))
            ap = os.path.join(wd, "ana.json"); pp = os.path.join(wd, "peak.json")
            self.ana[e["lab"]] = json.load(open(ap, encoding="utf8")) if os.path.exists(ap) else None
            self.peak[e["lab"]] = json.load(open(pp, encoding="utf8")) if os.path.exists(pp) else None
        R = PA.load_r6(self.rd)
        self.gt = R["t"]
        self.g = {}
        for j, (xg, yg) in enumerate(R["gxy"]):
            self.g[(float(xg), float(yg))] = R["gauge"][:, j]
        self.load_s = round(time.time() - t0, 1)

    def t(self, f):
        return self.tf[f]

    def frame_at(self, t):
        return min(self.frames, key=lambda q: abs(self.tf[q] - t))


# ======================================================================== 崩れ 1 つの Run（g48_video2.Run の FLIP49 版）
class Run49(G2.Run):
    def __init__(self, S, ev, opt=None, log=print):
        self.opt = dict(opt or {})
        self.log = log
        self.S = S; self.ev = ev; self.lab = ev["lab"]
        self.rd, self.stage, self.rid = S.rd, "FLIP49", S.rid
        self.cx = S.cx
        self.cfg = S.cfg
        self.off = S.off
        self.ana = S.ana.get(self.lab)
        if not self.ana:
            raise G2.InputError("崩れ %s の ana.json がない（pana/waves/k%02d）" % (self.lab, int(ev["k"])))
        self.tf = S.tf; self.H = S.H; self.hidx = S.hidx; self.frames = S.frames
        P = self.cfg.get("parms") or {}
        self.W = S.Wd
        self.Lx = float(P.get("x0", 0.0)) + float(P.get("Lx", self.cx.x_max))
        self.band = PA.side_band_of(self.cfg, self.W)
        self.ys = self.H["ys"]
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
                self.Hc = self.steep["eta"]; self.Hc_src = "巻かない：最も険しいコマの真ん中の頂"
            else:
                self.ev_f = self.frame_at(float(ev["on_t"])); self.ev_t = self.tf[self.ev_f]
                self.Hc = None; self.Hc_src = None
        self._track()
        self._prof = {}
        self._lat = {}
        self.meas = {}
        self.best_f = None
        self.best_src = None
        self.checks = {}

    def prof(self, f):
        """c(y)：g49_periodic_ana.crest_prof（peak.json と同じ関数・同じ窓）。横の端の帯も同じ c。"""
        if f not in self._prof:
            c, xc, win = PA.crest_prof(self.cfg, self.H["eta"][self.hidx[f]], self.H["xs"], self.ys, self.off)
            self._prof[f] = (c, xc, c)
        return self._prof[f]

    def crest_valid(self, f):
        x_lo = float(((self.cfg.get("analysis") or {}).get("crest_x_min_m")) or GC.X_CREST_MIN)
        return self.zcam.get(f, 0.0) >= x_lo + 3.0

    def measure(self):
        super().measure()
        self.live_best_f = self.best_f
        b = self.S.best.get(self.lab)
        if b and self.on:
            fb = int(b["frame"])
            if fb not in self.meas and fb in self.tf:
                xg = self.track_x(fb)
                M, X, Z, t = A46.r2_mask(self.cx, fb, xg)
                mm = A46.S52.measure_mask(M, X, Z, flip_extra=dict(Lc=self.cx.Lc))
                m = A46.DS.pick(mm)
                sc, parts = GV.score3(m)
                self.meas[fb] = dict(x_c=float(mm["x_c"]), eta_c=float(mm["eta_c"]), m=m, score3=sc, parts=parts,
                                     lines=GV.GA.mask_lines(M, X, Z, float(mm["x_c"]), float(mm["eta_c"])))
            self.best_f = fb
            self.best_at_end = False
            self.best_src = "pana/best_frames.json（凍らせた決まり：score3 の最小、巻き始め〜着水 + 0.5 s、着水がなければ巻き始め + 2.5 s）"
            if self.end_f is not None and fb > self.end_f:
                # 凍らせた窓（着水 + 0.5 s、着水がなければ巻き始め + 2.5 s）は g48_video2 の比べの窓（着水、なければ巻き始め + 2 s）より 0.5 s 長い。
                # 最も近いコマが後ろにある時は、比べる窓（輪郭を重ねる窓・スロー）をそのコマまで延ばす（最も近いコマに輪郭が出るように）
                self.end_f = fb; self.end_t = self.tf[fb]; self.end_extended = True
                self.end_src = (self.end_src or "") + "；凍らせた最も近いコマが後ろなので、比べる窓をそのコマまで延ばした"
            live = (self.meas.get(fb) or {}).get("score3")
            self.checks["best_frozen"] = dict(frame=fb, t=self.tf.get(fb), score3_frozen=b.get("score3"), score3_live=live,
                                              same=bool(live is not None and b.get("score3") is not None and abs(live - b["score3"]) < 1e-6),
                                              x_c_frozen=b.get("x_c"), x_c_live=(self.meas.get(fb) or {}).get("x_c"), g48_window_min_frame=self.live_best_f)

    def peak_check(self):
        p = self.S.peak.get(self.lab)
        if not (self.on and p):
            return None
        ref = (p.get("lateral_key") or {}).get("onset") or {}
        L = self.lat(self.on["f"]) if self.on["f"] in self.hidx else None
        if not L or not ref:
            return None
        d = {}
        for k in ("c0", "c_side", "ratio_side", "ratio_4Hc", "half_excess_width_m", "w90_m"):
            if isinstance(ref.get(k), (int, float)) and isinstance(L.get(k), (int, float)):
                d[k] = round(abs(float(ref[k]) - float(L[k])), 6)
        return dict(max_abs_diff=max(d.values()) if d else None, per_key=d)


# ======================================================================== 3D の図（g48_video2.View3D の字の置き方を直した物）
class View3D49(G2.View3D):
    def draw(self, f, small=False):
        """g48_video2.View3D.draw の写し（変えた所：柱の字（2 Hc・4 Hc・横の端）が右上の色の物差しの字や互いと重なる時は、物差しの左へ寄せ、
        段を上げる。D0 の動画で「横の端」が物差しの「4 m」「色＝高さ」と重なった）。"""
        r = self.r
        im, has_mesh = self.base(f)
        im = im.copy(); dr = G2.ImageDraw.Draw(im)
        cam = self.cam(f)
        wl, wn = (6, 3) if not small else (4, 2)
        sx0 = self.Wi - (58 if not small else 48); sy0 = 8; shh = self.Hi * 0.28
        scale_box = (sx0 - 20, 0, self.Wi, sy0 + shh + 30)        # 色の物差しと字の所
        placed = [scale_box]

        def free(b):
            return all(b[2] < q[0] or b[0] > q[2] or b[3] < q[1] or b[1] > q[3] for q in placed)
        if r.crest_valid(f):
            c, xc, cs = r.prof(f)
            ok = np.isfinite(c) & np.isfinite(xc)
            if ok.sum() > 8:
                xcs = np.where(ok, xc, np.nan)
                xcs = G2.uniform_filter1d(G2.median_filter(np.nan_to_num(xcs, nan=np.nanmedian(xcs)), size=9, mode="nearest"), 5, mode="nearest")
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
                    posts += [(2 * r.Hc, C2_, "2 Hc"), (4 * r.Hc, C4_, "4 Hc")]
                posts.append((0.5 * (r.band[0] + r.band[1]), (110, 110, 110), "横の端"))
                labels = []
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
                            labels.append((q[1, 0], q[1, 1], lab, colr))
                fz = font(13 if not small else 11, True)
                for u0, v0, lab, colr in labels:
                    tw = dr.textlength(lab, font=fz); th = 18
                    u = u0 - tw / 2; v = v0 - (22 if not small else 18)
                    for k_ in range(8):
                        u = min(max(u, 4.0), self.Wi - tw - 6.0)        # 図の中に
                        b = (u - 4, v - 3, u + tw + 4, v + th)
                        if free(b):
                            break
                        if b[2] >= scale_box[0] and b[1] <= scale_box[3]:
                            u = min(u, scale_box[0] - tw - 8)          # 物差しの左へ
                        else:
                            v -= th + 2                                 # ほかの字の上へ
                    b = (u - 4, v - 3, u + tw + 4, v + th)
                    if free(b) and v > 0:
                        GV.label_box(dr, (u, v), lab, colr, fz)
                        placed.append(b)
        for k in range(int(shh)):
            z = 10.5 - 11.0 * k / shh
            col = tuple(int(255 * np.interp(z, G2.H_STOPS, G2.H_COLS[:, j])) for j in range(3))
            dr.line([(sx0, sy0 + k), (sx0 + 12, sy0 + k)], fill=col)
        dr.rectangle([sx0, sy0, sx0 + 12, sy0 + shh], outline=(80, 80, 80))
        for z in (0, 4, 8):
            yv = sy0 + (10.5 - z) / 11.0 * shh
            dr.line([(sx0 + 12, yv), (sx0 + 16, yv)], fill=(60, 60, 60))
            GV.label_box(dr, (sx0 + 18, yv - 8), "%d m" % z, (40, 40, 40), font(11))
        GV.label_box(dr, (sx0 - 16, sy0 + shh + 6), "色＝高さ", (40, 40, 40), font(12))
        return im, has_mesh


# ======================================================================== 崩れ 1 つの比べ（g48_video2.CompareVideo の FLIP49 版）
class Compare49(G2.CompareVideo):
    def __init__(self, run, opt, S, idx, n):
        self.S = S; self.idx = idx; self.n = n
        self.ev = run.ev
        opt = dict(opt)
        on_t = run.on["t"] if run.on else run.ev_t
        end_t = run.end_t if run.on else run.ev_t + 1.0
        opt.setdefault("t0", "%r" % max(S.t(S.frames[0]), on_t - 4.0))
        opt.setdefault("t1", "%r" % min(S.t(S.frames[-1]), end_t + 2.0))
        opt.setdefault("end_hold", "0")
        super().__init__(run, opt)
        r = self.r
        self.v3 = View3D49(r, self.A1[2] - self.A1[0], self.A1[3] - self.A1[1], ss=int(opt.get("ss", 2)), mode=opt.get("view3d", "high"),
                           Dx=float(opt.get("Dx", 45.0)), h=float(opt.get("zh", 14.0)), pitch=float(opt.get("pitch", -11.0)), hfov=float(opt.get("vfov", 86.0)))
        self.cmp_t = (r.on["t"] - 1.0, r.end_t + 0.5) if r.on else None
        self.zoom_checks = {}
        if getattr(r, "end_extended", False):
            self.end_word = "原画に最も近いコマ"

    def _layout(self):
        super()._layout()
        # 2026-10-16 campaign B（PER49-B の記録だけ）：頂が 8 m 級で拡大の窓の上 z1 が 10 m の目盛りのすぐ上になると、目盛りの字「10 m」が
        # 赤い帯の字と重なる（S1 k4 で字の重なりの assert が止めた）。z1 が 10〜13 m の時だけ窓の上を 13 m に上げる（z1 ≤ 10 m では目盛りは
        # 窓の下から描かれ重ならない）。ほかの記録の並べ方は前と同じ
        if (self.r.cfg.get("case") or {}).get("campaign") == "PER49-B" and 10.0 < self.z1 < 13.0:
            self.z1 = 13.0
            pw_max, ph_max = 1120.0, float(self.zbot - self.zy)
            self.zoom_w = float(min(80.0, max(40.0, pw_max * (self.z1 - self.z0) / ph_max)))
            self.zs = min(pw_max / self.zoom_w, ph_max / (self.z1 - self.z0))

    # ---- 頭書き
    def head_lines(self):
        r = self.r; S = self.S; c = S.cfg; P = c.get("parms") or {}
        w = c.get("wave") or {}
        bed = GC.bed_spec(c, parms=P)
        kind = "準 2D の板（半幅 %g m）" % S.Wd if S.strip else "3D の半分の水槽（半幅 %g m、y = 0 は対称の面）" % S.Wd
        e = self.ev
        judged = S.judge_txt[0] if e.get("judged") else S.judge_txt[1]
        l1 = "FLIP49 %s：崩れ %s（%d/%d、%s）の原画との比べ" % (S.rid, r.lab, self.idx + 1, self.n, judged)
        if (c.get("case") or {}).get("standin"):          # 2026-10-16 campaign B S1：代わりの波（砕けの段だけの試し）。波としては見せない
            l1 = "【代わりの波 STAND-IN・波としては見せない】" + l1
        coarse = "（粗い。下見なので判定しない）" if not (c.get("case") or {}).get("judged", True) else ""
        l2 = "%s。海底 %s（%s）。入口の帯で規則波 T %s s・H %s m（in_gain %s）。粒子 %.4g m%s" % (
            kind, GC.bed_kind(bed), "方案 A" if c.get("layout") == "A" else "PG12s の並び", _g(w.get("T_s"), "%g"), _g(w.get("H_m"), "%g"),
            _g(w.get("in_gain"), "%.4g"), r.cx.dp, coarse)
        l3 = ("力は重力だけ。断面は縦横同じ縮尺、高さは静かな水面から（ずれ %.3f m を引いた）。数は【測った】（g49_periodic_ana と同じ関数）。"
              "選んだ物：うねりの T・H と海底。計算した物：集まり・崩れ・巻き" % r.off)
        l4 = "赤の太い枠＝原画に最も近い瞬間（pana/best_frames.json、score3 最小）・黒＝原画の輪郭（縦の伸びを戻した形）・青＝このコマ・紺＝各横位置の頂 c(y)"
        return l1, l2, l3, l4

    def header(self, dr, f, state):
        super().header(dr, f, state)

    # ---- 板の時は 3D・c(y)・c の時間の変化の代わりに表と波高計
    def draw_3d(self, im, dr, f, red):
        if self.S.strip:
            x0, y0, x1, y1 = self.A1
            dr.text((x0, y0 - 29), "崩れごとの量（板なので横の集まりはない。真ん中の断面の量だけ）", fill=TXT, font=font(17, True))
            table_panel(dr, self.S, self.r.lab, (x0, y0, x1, y1), small=False, rows_bottom=y1 - 96)
            if red:
                self.red_label(dr, x0 + 10, y1 - 90)          # 表の行（〜y1 − 96）と下の注（y1 − 54〜）の間
            return
        REC.pending = (self.A1[0], self.A1[1])
        super().draw_3d(im, dr, f, red)
        REC.pending = (0, 0)

    def draw_cy(self, im, dr, f):
        """g48_video2.CompareVideo.draw_cy の写し（変えた所：2 Hc・4 Hc の字が近い時は段を下げる、Hc と横の端の字が近い時は横の端の字を線の下へ、
        下の説明の行を FLIP49 の頂の窓に）。"""
        if self.S.strip:
            px0, py0, px1, py1 = self.A2[0], self.A2[1], self.A2[2], self.A3[3] - 16    # 下の時刻の字が重ねの題（A3 の下）に掛からないように
            gauge_panel(dr, self.S, f, (px0, py0, px1, py1), self.r.lab, rows=((0.5, "y 0.5 m"),))
            return
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
        y_hc = None
        if r.Hc:
            used = []
            for mlt, colr in ((2, C2_), (4, C4_)):
                for sg in (-1, 1):
                    xv = sg * mlt * r.Hc
                    if abs(xv) <= Wf:
                        dr.line([(X(xv), T), (X(xv), B)], fill=colr, width=2)
                if mlt * r.Hc <= Wf:
                    lab = "%d Hc" % mlt
                    u = X(mlt * r.Hc) + 3; wl = dr.textlength(lab, font=font(12, True))
                    lv = 0
                    while any(l_ == lv and not (u + wl + 6 < a_ or u > b_ + 6) for a_, b_, l_ in used) and lv < 2:
                        lv += 1
                    dr.text((u, T + 15 * lv), lab, fill=colr, font=font(12, True))
                    used.append((u, u + wl, lv))
            GV.dashed(dr, [(L, Y(r.Hc)), (R, Y(r.Hc))], (0, 0, 0), 1, 6, 5)
            hl = "Hc %.2f m（%s）" % (r.Hc, "巻き始めの真ん中" if r.on else "最も険しい時の真ん中")
            y_hc = Y(r.Hc) - 17
        late = []                                   # 線の上に描く字（最後に描く。線や塗りに隠れないように）
        if y_hc is not None:
            late.append(lambda: GV.label_box(dr, (R - 6 - dr.textlength(hl, font=font(12)), y_hc), hl, TXT, font(12)))
        if not r.crest_valid(f):
            dr.text((L + 20, (T + B) / 2 - 8), "頂はまだ頂を探す所の手前", fill=SUB, font=font(14))
            for fn in late:
                fn()
            self._cy_caption(dr)
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
            yl = Y(L_["c_side"]) + 2
            if y_hc is not None and abs(yl - y_hc) < 18:
                yl = max(y_hc + 18, yl)
            if yl + 14 <= B:
                late.append(lambda: GV.label_box(dr, (R - 120, yl), "横の端 c_side", (110, 110, 110), font(12)))
        pts = curve(f)
        if L_.get("c_side") is not None and len(pts) > 1:
            c_, _, _ = r.prof(f)
            cc_ = np.concatenate([c_[::-1], c_]); csd = L_["c_side"]
            poly_ = [(X(a_), Y(max(b_, csd))) for a_, b_ in zip(yy, cc_) if np.isfinite(b_)]
            if len(poly_) > 2:
                dr.polygon(poly_ + [(X(yy[-1]), Y(csd)), (X(yy[0]), Y(csd))], fill=(205, 218, 240))
                dr.line([(L, Y(csd)), (R, Y(csd))], fill=(140, 140, 140), width=1)
        if self.best_f is not None and f > self.best_f:
            GV.dashed(dr, curve(self.best_f), RED, 2, 7, 4)
            GV.dashed(dr, [(L + 6, T + 52), (L + 30, T + 52)], RED, 2, 7, 4)
            GV.label_box(dr, (L + 34, T + 44), "赤の破線＝原画に最も近い瞬間（コマ %d）" % self.best_f, RED, font(12))
        if len(pts) > 1:
            dr.line(pts, fill=NAVY, width=3)
        for fn in late:
            fn()
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
        self._cy_caption(dr)

    def _cy_caption(self, dr):
        px0, py0, px1, py1 = self.A2
        an = self.S.cfg.get("analysis") or {}
        if an.get("crest_window") == "centre_half_L":
            s = "c(y)＝各 y の行の一番上の水面の最大。窓は真ん中の頂 xc0 ± L/2（x %g〜%g m の中。g49_periodic_ana.crest_prof、peak.json と同じ）。灰＝0.5 s ごとの前" % (
                float(an.get("crest_x_min_m", 150.0)), PA.p1_max(self.S.cfg))
        else:
            s = "c(y)＝各 y の行で x %g〜%g m の一番上の水面の最大（g49_periodic_ana.crest_prof、peak.json と同じ）。灰＝0.5 s ごとの前の形" % (
                GC.X_CREST_MIN, PA.p1_max(self.S.cfg))
        GV.text_fit(dr, (px0, py1 + 22), s, px1 - px0, 11, fill=SUB, minsz=9)

    def draw_strip(self, im, dr, f):
        """全部の断面（g48_video2 の写し。変えた所：縦の範囲を断面の高さが 68 画素に収まるように選ぶ。記録の x の範囲が FLIP48 より短く、
        −8〜14 m では下の拡大の題に目盛りの字が重なった）。"""
        r = self.r

        class _D:
            pass
        D = _D(); D.R2 = r.cx.R2; D.off = r.off; D.cx = r.cx; D.ridge = False; D.ana = {}
        x0, x1 = r.cx.x_min, r.cx.x_max
        s = 1120.0 / (x1 - x0)
        zhi = 12.0
        zlo = max(-8.0, zhi - self.B0h / s)
        dr.text((40, self.B0y - 22), "領域の全部（y = 0.5 m の断面、x %.0f〜%.0f m、高さ %.0f〜%.0f m、縦横同じ縮尺。赤の細い枠＝下の拡大の窓）" % (x0, x1, zlo, zhi),
                fill=TXT, font=font(15, True))
        V46.section(im, dr, D, f, (40, self.B0y, 1160), x0, x1, zlo, zhi, None, tick=50.0, marks=False, scale_label=False)
        zx0 = self.zoom_x0(f)
        a, b = max(zx0, x0), min(zx0 + self.zoom_w, x1)
        Yz = lambda z: self.B0y + (zhi - z) * s
        if a < b:
            dr.rectangle([40 + (a - x0) * s, Yz(min(self.z1, zhi)), 40 + (b - x0) * s, Yz(max(self.z0, zlo))], outline=RED, width=2)

    def draw_ct(self, im, dr, f):
        if self.S.strip:
            return
        super().draw_ct(im, dr, f)

    # ---- 拡大の窓：最も近いコマの頂を前の端から 20 m 以上内側に
    def zoom_x0(self, f):
        base = super().zoom_x0(f)
        r = self.r
        if self.best_f is None or not self.cmp_t:
            return base
        m = r.meas.get(self.best_f) or {}
        xb = m.get("x_c")
        if xb is None:
            return base
        w = self.zoom_w
        lo_ = xb + 20.0 - w
        hi_ = xb - max(8.0, 0.2 * w)
        t = r.tf[f]; a, b = self.cmp_t
        wgt = float(np.clip(1.0 - max(a - t, t - b, 0.0) / 0.75, 0.0, 1.0))
        target = min(max(base, lo_), hi_)
        return base + (target - base) * wgt

    def zoom_check(self):
        """最も近いコマで、頂 x_c が窓の前の端から 20 m 以上・後ろの端から 0.2 × 幅以上内側（assert）。"""
        if self.best_f is None:
            return dict(note="最も近いコマがない（巻かない）")
        m = self.r.meas.get(self.best_f) or {}
        x0 = self.zoom_x0(self.best_f); x1 = x0 + self.zoom_w
        xb = m.get("x_c")
        d = dict(frame=self.best_f, x_c=xb, window=[round(x0, 2), round(x1, 2)], front_margin_m=(x1 - xb) if xb is not None else None,
                 back_margin_m=(xb - x0) if xb is not None else None, width_m=self.zoom_w)
        d["ok"] = bool(xb is not None and d["front_margin_m"] >= 20.0 - 1e-6 and d["back_margin_m"] >= 0.2 * self.zoom_w - 1e-6)
        return d

    def render(self, f, state):
        im = Image.new("RGB", (W, H), BG)
        REC.reset(im)
        # g48_video2.CompareVideo.render と同じ順（ImageDraw を記録の物に）
        r = self.r
        dr = rec_draw(im)
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
        timebar_sep(dr, 40, W - 40, H - 44, self.ta, self.tb, r.tf[f], marks, self.slow_t)
        if red:
            ox0, oy0, ox1, oy1 = self.ovbox
            for (a, b, c, d) in (self.A1, self.zbox, (ox0 - 34, oy0, ox1, oy1 + 16)):
                dr.rectangle([a - 6, b - 6, c + 6, d + 6], outline=RED, width=5)
        self.last_overlaps = overlaps(REC.boxes)
        return im


def timebar_sep(dr, x0, x1, y, ta, tb, t, marks, slow_t=None):
    """g47_video.timebar と同じ帯。印の字が重なる時は段を下げる（3 段まで）。"""
    fs = font(13)
    la = "t %.2f s" % ta; lb = "%.2f s" % tb
    dr.text((x0, y - 3), la, fill=SUB, font=fs)
    x0b = x0 + dr.textlength(la, font=fs) + 10
    x1b = x1 - dr.textlength(lb, font=fs) - 10
    dr.text((x1b + 10, y - 3), lb, fill=SUB, font=fs)
    dr.rectangle([x0b, y, x1b, y + 8], fill=(225, 225, 222))
    span = max(tb - ta, 1e-6)
    U = lambda tt: x0b + (x1b - x0b) * (min(max(tt, ta), tb) - ta) / span
    if slow_t:
        dr.rectangle([U(slow_t[0]), y - 3, U(slow_t[1]), y + 11], fill=(250, 214, 170))
    dr.rectangle([x0b, y, U(t), y + 8], fill=(60, 80, 110))
    used = []
    for tm, lab, col in sorted(marks, key=lambda q: q[0]):
        if tm is None or not (ta - 1e-9 <= tm <= tb + 1e-9):
            continue
        u = U(tm)
        wl = dr.textlength(lab, font=fs) if lab else 0
        lvl = 0
        while any(lv == lvl and not (u + 3 + wl + 6 < a_ or u + 3 > b_ + 6) for a_, b_, lv in used) and lvl < 2:
            lvl += 1
        dr.line([(u, y - 4), (u, y + 12 + 13 * lvl)], fill=col, width=2)
        if lab:
            dr.text((u + 3, y + 10 + 13 * lvl), lab, fill=col, font=fs)
            used.append((u + 3, u + 3 + wl, lvl))


# ======================================================================== 表と波高計（比べの板・全部の動画）
def table_panel(dr, S, k_now, box, small=True, rows_bottom=None):
    px0, py0, px1, py1 = box
    dr.rectangle([px0, py0, px1, py1], fill=WHITE, outline=(150, 150, 150))
    fz = font(12 if small else 14); fb = font(12 if small else 14, True)
    cols = [("k", 30), ("t 始め", 58), ("x m", 50), ("Hc m", 48), ("c0/横", 52), ("c0/4Hc", 60), ("幅/Hc", 52), ("弦°", 40), ("唇", 42), ("覆い", 50),
            ("P1〜P5", 130), ("score3", 54), ("最も近い t", 74)]
    scale = (px1 - px0 - 16) / float(sum(w for _, w in cols))
    x = px0 + 8; y = py0 + 6
    for nm, w in cols:
        dr.text((x, y), nm, fill=SUB, font=fb); x += w * scale
    y += 22 if not small else 19
    for e in S.ev:
        k = e["lab"]
        r = S.rows.get(k) or {}
        b = S.best.get(k) or {}
        J = r.get("judge") or {}
        yn = lambda q: ("○" if J.get(q) else "×") if q in J else "—"
        pp = "  ".join("%s" % yn(q) for q in ("P1", "P2", "P3", "P4a", "P4b", "P5"))
        vals = [k, _g(e["on_t"]), _g(e["on_x"], "%.1f"), _g(r.get("Hc")), _g(r.get("ratio_side")), _g(r.get("ratio_4Hc")), _g(r.get("w_maxov_over_Hc"), "%.1f"),
                _g(r.get("chord_max"), "%.0f"), _g(r.get("lip_max")), _g(r.get("hood_max"), "%.3f"), pp, _g(b.get("score3")), _g(b.get("t"))]
        col = RED if k == k_now else (TXT if e.get("judged") else (150, 150, 150))
        x = px0 + 8
        for (nm, w), v in zip(cols, vals):
            dr.text((x, y), v, fill=col, font=fb if k == k_now else fz); x += w * scale
        y += 18 if small else 21
        if y > (rows_bottom if rows_bottom is not None else py1 - 58) - (18 if small else 21):
            break
    notes = ["%s、赤＝今の崩れ。P1〜P5 の並び：P1・P2・P3・P4a・P4b・P5（— は板で読まない）" % S.grey_txt,
             "c0/横＝P4a、c0/4Hc＝P4b、幅/Hc＝最も巻いた時の巻いた全幅（P3）、弦・唇・覆い＝巻き始め〜着水の最大（P5）",
             "score3・最も近い t＝pana/best_frames.json（凍らせた決まり）。数は AI の読み。原画：弦 64.3°・唇 0.35・覆い 0.186"]
    for i_, s_ in enumerate(notes):
        GV.text_fit(dr, (px0 + 8, py1 - 54 + 17 * i_), s_, px1 - px0 - 16, 11, fill=SUB, minsz=9)


def gauge_panel(dr, S, f, box, k_now=None, rows=((0.5, "y 0.5 m（真ん中）"), (80.0, "y 80 m（横の端）"))):
    """波高計 η（x 110・128・160 m）の時系列。崩れの巻き始め（青 k）・原画に最も近い瞬間（赤）・今（黒）。"""
    px0, py0, px1, py1 = box
    n = len(rows)
    hh = (py1 - py0 - 26 * n) / n
    t = S.gt; ta, tb = float(t[0]), float(t[-1])
    lo, hi = -4.0, 7.0
    cols = {110.0: (30, 60, 130), 128.0: (60, 130, 90), 160.0: (90, 170, 220)}
    for i, (yg, ylab) in enumerate(rows):
        y0 = py0 + i * (hh + 26) + 22; y1 = y0 + hh
        dr.text((px0, y0 - 21), "波高計 η、%s：x 110 m 紺・128 m 緑・160 m 水色（静かな水面から）" % ylab, fill=TXT, font=font(13, True))
        dr.rectangle([px0, y0, px1, y1], outline=(150, 150, 150), fill=WHITE)
        X = lambda v: px0 + 40 + (v - ta) / max(tb - ta, 1e-9) * (px1 - px0 - 50)
        Y = lambda v: y1 - 6 - (min(max(v, lo), hi) - lo) / (hi - lo) * (y1 - y0 - 12)
        for zv in (-2, 0, 2, 4, 6):
            dr.line([(px0 + 40, Y(zv)), (px1 - 10, Y(zv))], fill=(225, 225, 225) if zv else (150, 150, 150))
            dr.text((px0 + 4, Y(zv) - 7), "%+d" % zv, fill=SUB, font=font(10))
        for xg in (110.0, 128.0, 160.0):
            e = S.g.get((xg, float(yg)))
            if e is None:
                continue
            ee = e - S.off
            pts = [(X(a), Y(b)) for a, b in zip(t[::2], ee[::2]) if np.isfinite(b)]
            if len(pts) > 1:
                dr.line(pts, fill=cols[xg], width=2)
        for ev in S.ev:
            u = X(ev["on_t"])
            dr.line([(u, y0 + 2), (u, y1 - 2)], fill=(30, 110, 200), width=1)
            if i == 0:
                dr.text((u + 2, y0 + 2), ev["lab"], fill=RED if ev["lab"] == k_now else (30, 110, 200), font=font(11, True))
        for k, b in S.best.items():
            u = X(float(b["t"]))
            dr.line([(u, y0 + 14), (u, y1 - 2)], fill=RED, width=2)
        u = X(S.t(f))
        dr.line([(u, y0), (u, y1)], fill=(0, 0, 0), width=2)
        if i == n - 1:
            for tv in range(0, int(tb) + 1, 12):
                dr.text((X(tv) - 8, y1 + 2), "%d s" % tv, fill=SUB, font=font(10))


# ======================================================================== 比べの動画
def make_compare(rd, opt, log=print, S=None):
    t_start = time.time()
    S = S or Shared(rd, log=log)
    out = GC.guard_out49(opt.get("out") or os.path.join(S.rd, "video"))
    sel = [int(v) for v in str(opt["k"]).split(",")] if opt.get("k") else None
    evs = [e for e in S.ev if (sel is None or int(e["k"]) in sel)]
    segs = []
    for i, e in enumerate(evs):
        if not S.ana.get(e["lab"]):
            log("skip", e["lab"], "（ana.json がない）"); continue
        run = Run49(S, e, opt, log=log)
        if not run.on:
            log("skip", e["lab"], "（巻かない）"); continue
        cv = Compare49(run, opt, S, i, len(evs))
        zc = cv.zoom_check()
        assert zc.get("ok"), "拡大の窓が最も近いコマの頂を 20 m 内側に入れていない：%s %s" % (e["lab"], zc)
        segs.append((e, run, cv, zc))
        log("segment", e["lab"], "frames %d..%d best %s zoom %s" % (cv.fr[0], cv.fr[-1], cv.best_f, zc))
    if not segs:
        raise G2.InputError("比べる崩れがない")
    name = opt.get("name") or ("%s_compare" % S.rid)
    if opt.get("still") is not None:
        res = []
        for e, run, cv, zc in segs:
            for wch in str(opt["still"]).split(","):
                f = G2.still_frame(run, cv, wch)
                st = "hold" if f == cv.best_f else "slow"
                im = cv.render(f, st)
                p = os.path.join(out, "%s_%s_f%05d.png" % (name, e["lab"], f)).replace("\\", "/")
                im.save(p)
                res.append(dict(path=p, overlaps=cv.last_overlaps, zoom=zc))
                log("wrote", p, "overlaps", len(cv.last_overlaps), cv.last_overlaps[:4])
        return dict(stills=res)
    path = os.path.join(out, name + ".mp4").replace("\\", "/")
    wr = GV.Writer(path)
    seginfo = []
    ov_all = {}
    t_r = time.time()
    for e, run, cv, zc in segs:
        sch = cv.schedule()
        key_frames = set([cv.best_f, run.on["f"], cv.fr[0]])
        n0 = wr.n
        for j, (f, n, st) in enumerate(sch):
            im = cv.render(f, st)
            if cv.last_overlaps:
                ov_all["%s_f%d_%s" % (e["lab"], f, st)] = cv.last_overlaps[:6]
            if f in key_frames or st == "hold":
                assert not cv.last_overlaps, "字が重なった（%s コマ %d %s）：%s" % (e["lab"], f, st, cv.last_overlaps[:6])
            wr.put(im, n)
            if st == "hold":
                im.save(os.path.join(out, "%s_%s_best.png" % (name, e["lab"])))
            if j % 40 == 0:
                log("  %s %d/%d f%d %s %.0f s" % (e["lab"], j, len(sch), f, st, time.time() - t_r))
        seginfo.append(dict(k=e["lab"], judged=e.get("judged"), frames=[cv.fr[0], cv.fr[-1]], t=[cv.ta, cv.tb], video_frames=[n0, wr.n],
                            onset=run.on, touchdown=run.td, best=dict(frame=cv.best_f, t=run.tf.get(cv.best_f), src=run.best_src,
                                                                      score3=(run.meas.get(cv.best_f) or {}).get("score3"),
                                                                      x_c=(run.meas.get(cv.best_f) or {}).get("x_c")),
                            zoom=zc, checks=dict(run.checks, peak_vs_live_lateral_onset=run.peak_check()),
                            speed=dict(fast=cv.fast, slow=cv.slow, slow_t=cv.slow_t, hold_s=cv.hold_s)))
    wr.close()
    pb = GV.probe(path)
    info = dict(video=path, made=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " compare", run=S.rid, rd=S.rd, layout=S.cfg.get("layout") or "PG12s",
                still_offset_m=S.off, segments=seginfo, written_frames=wr.n, ffprobe=pb, ok=bool(pb.get("ok") and pb.get("frames") == wr.n),
                text_overlap_frames=len(ov_all), text_overlaps_sample=dict(list(ov_all.items())[:12]),
                camera3d=None if S.strip else "front oblique from above, 1:1 (no vertical stretch), colour = height (not the print colours); g48_video2.View3D",
                elapsed_s=round(time.time() - t_start, 1),
                note_ja="赤い枠＝pana/best_frames.json の原画に最も近いコマ（凍らせた決まり、score3 は AI の読み）。原画らしさは利用者が決める")
    json.dump(A46._clean(info), open(os.path.join(out, name + ".json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    log(json.dumps(A46._clean(dict(video=path, ok=info["ok"], frames=wr.n, overlaps=len(ov_all), elapsed_s=info["elapsed_s"])), ensure_ascii=False))
    return info


# ======================================================================== 全部の動画
H_STOPS, H_COLS = G2.H_STOPS, G2.H_COLS


def hcol(z):
    return np.stack([np.interp(z, H_STOPS, H_COLS[:, k]) for k in range(3)], -1)


class Whole:
    """計算の全部を 2 倍の早送りで見る動画（Q66 の長い動画）。崩れごとの Run49 を、その崩れの窓 [t_on − T/2, t_on + T/2] で使う。"""

    def __init__(self, S, opt, log=print):
        self.S = S; self.opt = opt; self.log = log
        self.speed = float(opt.get("speed", 2.0)); self.hold = float(opt.get("hold", 1.0))
        self.runs = []
        for e in S.ev:
            if not S.ana.get(e["lab"]):
                continue
            r = Run49(S, e, opt, log=log)
            if r.on:
                r.measure()
                self.runs.append(r)
        self.best_f = {r.best_f: r for r in self.runs if r.best_f is not None}
        P = S.cfg.get("parms") or {}
        self.x0 = float(P.get("xg_end", GC.IN_X1)); self.x1 = float(S.cx.x_dom[1])
        self.xa0 = float(P.get("xa0", 1e9))
        self.Wd = S.Wd
        self.T = S.T
        # 並べ方（全部の断面の高さから下の拡大の位置を決める：断面の目盛りの字と拡大の題が重ならないように）
        self.PV = (40, 132, 1160, 132 + 300)      # 上から（両側。縦横同じ縮尺）
        self.TB = (1200, 132, 1880, 432)          # 表
        self.B0y = 478                             # 全部の断面
        ph0 = int(round(22.0 * 1120.0 / (self.x1 - self.x0)))
        ztop = self.B0y + ph0 + 26 + 34
        self.ZB = (40, ztop, 1160, H - 100)       # 拡大（下に目盛りの字、その下に時刻の帯の題）
        self.GB = (1200, ztop, 1880, H - 100)     # 波高計
        self.zoom_w = 70.0
        self.zz0, self.zz1 = -8.0, 16.0
        self.zs = min((self.ZB[2] - self.ZB[0]) / self.zoom_w, (self.ZB[3] - self.ZB[1]) / (self.zz1 - self.zz0))

    def run_at(self, t):
        for r in self.runs:
            if r.ev["on_t"] - 0.5 * self.T <= t < r.ev["on_t"] + 0.5 * self.T:
                return r
        if not self.runs:
            return None
        return min(self.runs, key=lambda r: abs(r.ev["on_t"] - t))

    def header(self, dr, f, state, r):
        S = self.S; c = S.cfg; P = c.get("parms") or {}; w = c.get("wave") or {}
        bed = GC.bed_spec(c, parms=P)
        kind = "準 2D の板（半幅 %g m）" % S.Wd if S.strip else "3D の半分の水槽（半幅 %g m、y = 0 は対称の面）" % S.Wd
        GV.text_fit(dr, (40, 4), ("【代わりの波 STAND-IN・波としては見せない】" if (c.get("case") or {}).get("standin") else "") +
                    "FLIP49 %s：計算の全部（%s 倍の早送り、原画に最も近いコマで %g s 止めて赤い枠）" % (S.rid, _g(self.speed, "%g"), self.hold), 1430, 22, True)
        GV.text_fit(dr, (40, 34), "%s。海底 %s（%s）。入口の帯で規則波 T %s s・H %s m。粒子 %.4g m%s。力は重力だけ" % (
            kind, GC.bed_kind(bed), "方案 A" if c.get("layout") == "A" else "PG12s の並び", _g(w.get("T_s"), "%g"), _g(w.get("H_m"), "%g"), S.cx.dp,
            "（粗い。下見なので判定しない）" if not (c.get("case") or {}).get("judged", True) else ""), 1430, 15)
        l3 = ("断面は縦横同じ縮尺。板は横に一様なので上からの図の代わりに波高計を広く置いた。" if S.strip else
              "上から：色＝高さ（静かな水面から、縦横同じ縮尺、y = 0 で写して両側）。断面は縦横同じ縮尺。")
        GV.text_fit(dr, (40, 54), l3 + "数は AI の読み（g49_periodic_ana）。原画らしさは利用者が決める", 1430, 14, fill=SUB)
        if r is not None:
            e = r.ev
            GV.text_fit(dr, (40, 73), "今の崩れ %s（%s）：巻き始め t %.2f s・x %.1f m・Hc %s m。原画に最も近い t %s（score3 %s）" % (
                e["lab"], "判定する" if e.get("judged") else "判定しない", e["on_t"], e["on_x"], _g(r.Hc),
                _g(r.tf.get(r.best_f) if r.best_f else None), _g((r.meas.get(r.best_f) or {}).get("score3") if r.best_f else None)), 1430, 15, True)
        dr.text((1500, 2), "t = %.2f s" % S.t(f), fill=TXT, font=font(30, True))
        if state == "hold":
            txt, col = "止め %.1f s：原画に最も近い瞬間" % self.hold, RED
        else:
            txt, col = "%.3g 倍の早送り（計算の 1 s を %.3g s で）" % (self.speed, 1.0 / self.speed), BLUE
        fz = font(17, True)
        wl = dr.textlength(txt, font=fz)
        dr.rectangle([1500, 70, 1500 + wl + 16, 98], fill=col)
        dr.text((1508, 72), txt, fill=WHITE, font=fz)

    def plan_view(self, im, dr, f, r, red):
        S = self.S
        px0, py0, px1, py1 = self.PV
        e, m, t = S.cx.R1.get(f)
        E = np.nan_to_num(e - S.off, nan=0.0)
        xs = m["x0"] + m["dx"] * np.arange(E.shape[1]); zs = m["z0"] + m["dz"] * np.arange(E.shape[0])
        sel = (xs >= self.x0) & (xs <= self.x1)
        E = E[:, sel]; xs = xs[sel]
        full = np.concatenate([E[::-1], E], 0)            # 行：横 −W..W（上が +y）
        Wf = 2.0 * float(zs[-1] + 0.5 * m["dz"])
        sc = min((px1 - px0) / (self.x1 - self.x0), (py1 - py0) / Wf)
        pw = int(round((self.x1 - self.x0) * sc)); ph = int(round(Wf * sc))
        rgb = (hcol(full[::-1]) * 255).clip(0, 255).astype(np.uint8)
        img = Image.fromarray(rgb).resize((pw, ph), Image.BILINEAR)
        im.paste(img, (px0, py0))
        X = lambda x: px0 + (x - self.x0) * sc
        Yv = lambda y: py0 + ph / 2.0 - y * sc
        # 海底の等深線（2・6・10・17 m）を薄く
        try:
            from skimage import measure as SKM
            yy = np.concatenate([-zs[::-1], zs])
            dep = -GC.bed_z(xs[None, :], yy[:, None], **S.cx.bed49)
            for lev in (2.0, 6.0, 10.0, 20.0):
                for cc in SKM.find_contours(dep, lev):
                    pts = [(X(xs[0] + q[1] * m["dx"]), Yv(yy[0] + q[0] * m["dz"])) for q in cc[::3]]
                    if len(pts) > 1:
                        dr.line(pts, fill=(235, 235, 225), width=1)
        except Exception:
            pass
        # 今の崩れの頂の線（c(y) の x_c）
        if r is not None and r.crest_valid(f):
            c, xc, _ = r.prof(f)
            ys = r.ys
            ok = np.isfinite(xc)
            pts = [(X(a), Yv(b)) for a, b in zip(np.concatenate([xc[ok][::-1], xc[ok]]), np.concatenate([-ys[ok][::-1], ys[ok]]))]
            if len(pts) > 1:
                dr.line(pts, fill=WHITE, width=4); dr.line(pts, fill=NAVY, width=2)
        if self.xa0 < self.x1:
            dr.line([(X(self.xa0), py0), (X(self.xa0), py0 + ph)], fill=(250, 250, 250), width=1)
        dr.rectangle([px0, py0, px0 + pw, py0 + ph], outline=RED if red else (120, 120, 120), width=5 if red else 1)
        dr.text((px0, py0 - 26), "上から：水面の高さ（両側、縦横同じ縮尺、x %.0f〜%.0f m、y ±%.0f m）。紺＝今の崩れの頂の線、白い線＝海底の等深線 2・6・10・20 m" % (
            self.x0, self.x1, Wf / 2), fill=TXT, font=font(15, True))
        # 色の物差しと目盛り（図の右）
        bx0 = px0 + pw + 16; by0 = py0 + 4; bh = min(ph - 30, 200)
        for k in range(int(bh)):
            z = 10.5 - 11.0 * k / bh
            dr.line([(bx0, by0 + k), (bx0 + 12, by0 + k)], fill=tuple(int(255 * v) for v in hcol(np.array(z))))
        dr.rectangle([bx0, by0, bx0 + 12, by0 + bh], outline=(80, 80, 80))
        for z in (0, 4, 8):
            yv = by0 + (10.5 - z) / 11.0 * bh
            dr.text((bx0 + 16, yv - 8), "%d m" % z, fill=SUB, font=font(11))
        for xg in np.arange(math.ceil(self.x0 / 50.0) * 50.0, self.x1 + 1e-6, 50.0):
            dr.text((X(xg) - 10, py0 + ph + 2), "%d" % xg, fill=SUB, font=font(11))
        # c(y) の小さな図（物差しの右）
        if r is not None and r.crest_valid(f) and not self.S.strip:
            gx0 = bx0 + 60
            if gx0 + 200 < px1:
                L_ = r.lat(f)
                mini_cy(dr, r, f, (gx0, py0, px1, py0 + min(ph, 200)), hi=max(12.0, math.ceil((r.Hc or 10.0) + 2.0)))
                GV.text_fit(dr, (gx0, py0 + min(ph, 200) + 4), "c0 %s m・横の端 %s m・c0/横 %s・c0/c(4Hc) %s" % (
                    _g(L_.get("c0")), _g(L_.get("c_side")), _g(L_.get("ratio_side")), _g(L_.get("ratio_4Hc"))), px1 - gx0, 13, True)
        return ph

    def section_strip(self, im, dr, f, r, zx0):
        class _D:
            pass
        D = _D(); D.R2 = self.S.cx.R2; D.off = self.S.off; D.cx = self.S.cx; D.ridge = False; D.ana = {}
        zlo, zhi = -8.0, 14.0
        dr.text((40, self.B0y - 22), "全部の断面（y = 0.5 m、x %.0f〜%.0f m、縦横同じ縮尺。赤の細い枠＝下の拡大の窓。白の縦線＝出口の帯の始まり）" % (self.x0, self.x1),
                fill=TXT, font=font(15, True))
        V46.section(im, dr, D, f, (40, self.B0y, 1160), self.x0, self.x1, zlo, zhi, None, tick=50.0, marks=False, scale_label=False)
        s = 1120.0 / (self.x1 - self.x0)
        Yz = lambda z: self.B0y + (zhi - z) * s
        a, b = max(zx0, self.x0), min(zx0 + self.zoom_w, self.x1)
        dr.rectangle([40 + (a - self.x0) * s, Yz(min(self.zz1, zhi)), 40 + (b - self.x0) * s, Yz(max(self.zz0, zlo))], outline=RED, width=2)
        if self.xa0 < self.x1:
            u = 40 + (self.xa0 - self.x0) * s
            dr.line([(u, self.B0y), (u, Yz(zlo))], fill=WHITE, width=2)

    def zoom_x0(self, f, r):
        if r is None:
            return self.x0
        xc = r.zcam.get(f, r.ev["on_x"])
        x0 = xc - 0.45 * self.zoom_w
        if r.best_f is not None and r.on:
            m = r.meas.get(r.best_f) or {}
            xb = m.get("x_c")
            t = r.tf[f]; a, b = r.on["t"] - 1.0, r.end_t + 0.5
            if xb is not None:
                wgt = float(np.clip(1.0 - max(a - t, t - b, 0.0) / 0.75, 0.0, 1.0))
                target = min(max(x0, xb + 20.0 - self.zoom_w), xb - 0.2 * self.zoom_w)
                x0 = x0 + (target - x0) * wgt
        return float(min(max(x0, self.x0), self.x1 - self.zoom_w))

    def zoom(self, im, dr, f, r, red, zx0):
        bx = GV.Box(self.ZB[0], self.ZB[1], self.zs, zx0, zx0 + self.zoom_w, self.zz0, self.zz1)
        dr.text((self.ZB[0], self.ZB[1] - 26), "真ん中の断面の拡大（y 0.5 m、今の崩れの頂を追う、幅 %.0f m、縦横同じ縮尺）。黒＝原画の輪郭（巻き始め〜着水 + 0.5 s）" % self.zoom_w,
                fill=TXT, font=font(15, True))
        if r is not None:
            if r.on and r.on["t"] - 1.0 <= r.tf[f] <= r.end_t + 0.5 and f not in r.meas:
                try:
                    xg = r.track_x(f)
                    M, X, Z, t = A46.r2_mask(r.cx, f, xg)
                    mm = A46.S52.measure_mask(M, X, Z, flip_extra=dict(Lc=r.cx.Lc))
                    m = A46.DS.pick(mm)
                    sc, parts = GV.score3(m)
                    r.meas[f] = dict(x_c=float(mm["x_c"]), eta_c=float(mm["eta_c"]), m=m, score3=sc, parts=parts, lines=None)
                except Exception as ex:
                    r.meas[f] = dict(err=repr(ex)[:120])
            G2.draw_section(im, dr, r, f, bx, best=(f == r.best_f))
        if red:
            dr.rectangle([bx.px - 6, bx.py - 6, bx.px + bx.pw + 6, bx.py + bx.ph + 6], outline=RED, width=5)
            b = r.meas.get(r.best_f) or {}
            s = "原画に最も近い瞬間（崩れ %s、t %.2f s、score3 %s）：黒の太線＝原画の輪郭（η_c %s m・頂の x %s m に合わせた）" % (
                r.lab, r.tf[r.best_f], _g(b.get("score3")), _g(b.get("eta_c")), _g(b.get("x_c"), "%.1f"))
            fz = font(15, True)
            GV.text_fit(dr, (bx.px + 8, bx.py + 6), s, bx.pw - 16, 15, True, fill=RED)
        return bx

    def render(self, f, state):
        S = self.S
        im = Image.new("RGB", (W, H), BG)
        REC.reset(im)
        dr = rec_draw(im)
        t = S.t(f)
        r = self.run_at(t)
        red = bool(r is not None and r.best_f is not None and (state == "hold" or f == r.best_f))
        self.header(dr, f, state, r)
        if S.strip:                     # 板は横に一様なので上からの図の代わりに波高計の時系列を広く
            gauge_panel(dr, S, f, (self.PV[0], self.PV[1] - 4, self.PV[2], self.PV[3]), r.lab if r else None, rows=((0.5, "y 0.5 m（板は横に一様）"),))
        else:
            self.plan_view(im, dr, f, r, red)
        dr.text((self.TB[0], self.TB[1] - 26), "崩れごとの量（%s。○ 満たす・× 外れ）" % S.judge_head, fill=TXT, font=font(15, True))
        table_panel(dr, S, r.lab if r else None, self.TB)
        zx0 = self.zoom_x0(f, r)
        self.section_strip(im, dr, f, r, zx0)
        self.zoom(im, dr, f, r, red, zx0)
        if S.strip:
            gx0, gy0, gx1, gy1 = self.GB
            GV.text_fit(dr, (gx0, gy0), "準 2D の板：横に一様なので、真ん中への集まり（c(y)・P2〜P4）は読まない。", gx1 - gx0, 14, True)
            GV.text_fit(dr, (gx0, gy0 + 24), "崩れごとの原画との比べ（重ねの図と量の表）は比べの動画（_compare.mp4）にある。", gx1 - gx0, 14)
        else:
            gauge_panel(dr, S, f, self.GB, r.lab if r else None, rows=((0.5, "y 0.5 m（真ん中）"), (80.0, "y 80 m（横の端）")))
        marks = [(float(e["on_t"]), e["lab"], (30, 110, 200)) for e in S.ev] + [(float(b["t"]), "", RED) for b in S.best.values()]
        dr.text((40, H - 74), "時刻の帯：青＝崩れ k の巻き始め、赤＝原画に最も近い瞬間（そこで %g s 止める）" % self.hold, fill=TXT, font=font(14, True))
        timebar_sep(dr, 40, W - 40, H - 44, S.t(S.frames[0]), S.t(S.frames[-1]), t, marks)
        self.last_overlaps = overlaps(REC.boxes)
        return im

    def schedule(self, frames):
        out, acc, emitted = [], 0.0, 0
        for f in frames:
            acc += 1.0 / self.speed
            n = int(math.floor(acc + 1e-9)) - emitted
            emitted += n
            if n > 0 or f in self.best_f:
                out.append((f, max(n, 1), "fast"))
            if f in self.best_f and self.hold > 0:
                out.append((f, int(round(self.hold * FPS)), "hold"))
        return out


def mini_cy(dr, run, f, box, hi=12.0):
    """g48_video2.mini_cy の写し（変えた所：題の行と 12 m の目盛りの字が重ならないよう、グラフの上を 26 画素下げた。縦の範囲 hi を目盛りに）。"""
    px0, py0, px1, py1 = box
    dr.rectangle(box, fill=WHITE, outline=(120, 120, 120))
    L, R, T, B = px0 + 30, px1 - 6, py0 + 26, py1 - 6
    ys = run.ys; Wf = float(ys[-1] + 0.5 * (ys[1] - ys[0]))
    X = lambda v: L + (v + Wf) / (2 * Wf) * (R - L)
    Y = lambda v: B - min(max(v, 0.0), hi) / hi * (B - T)
    for g in range(0, int(hi) + 1, 4):
        dr.line([(L, Y(g)), (R, Y(g))], fill=(232, 232, 232))
        dr.text((px0 + 3, Y(g) - 7), "%d" % g, fill=SUB, font=font(10))
    dr.text((px0 + 4, py0 + 3), "c(y)（縦を伸ばした、0〜%g m、y ±%g m）。薄い青＝横の端より高い分、黒の破線＝Hc" % (hi, Wf), fill=TXT, font=font(11, True))
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
        for mlt, colr in ((2, C2_), (4, C4_)):
            for sg in (-1, 1):
                dr.line([(X(sg * mlt * run.Hc), T), (X(sg * mlt * run.Hc), B)], fill=colr, width=1)
        GV.dashed(dr, [(L, Y(run.Hc)), (R, Y(run.Hc))], (0, 0, 0), 1, 5, 4)
    pts = [(X(a_), Y(b_)) for a_, b_ in zip(yy, cc) if np.isfinite(b_)]
    if len(pts) > 1:
        dr.line(pts, fill=NAVY, width=2)


def make_whole(rd, opt, log=print, S=None):
    t_start = time.time()
    S = S or Shared(rd, log=log)
    out = GC.guard_out49(opt.get("out") or os.path.join(S.rd, "video"))
    wv = Whole(S, opt, log=log)
    name = opt.get("name") or ("%s_whole" % S.rid)
    if opt.get("still") is not None:
        res = []
        for wch in str(opt["still"]).split(","):
            if wch == "best":
                fs = sorted(wv.best_f)
            else:
                fs = [int(wch)]
            for f in fs:
                im = wv.render(f, "hold" if f in wv.best_f else "fast")
                p = os.path.join(out, "%s_f%05d.png" % (name, f)).replace("\\", "/")
                im.save(p)
                res.append(dict(path=p, overlaps=wv.last_overlaps))
                log("wrote", p, "overlaps", len(wv.last_overlaps), wv.last_overlaps[:4])
        return dict(stills=res)
    t0 = float(opt.get("t0", -1e9)); t1 = float(opt.get("t1", 1e9))
    frs = [f for f in S.frames if t0 - 1e-9 <= S.t(f) <= t1 + 1e-9]
    sch = wv.schedule(frs)
    path = os.path.join(out, name + ".mp4").replace("\\", "/")
    wr = GV.Writer(path)
    ov_all = {}
    t_r = time.time()
    for j, (f, n, st) in enumerate(sch):
        im = wv.render(f, st)
        if wv.last_overlaps:
            ov_all["f%d_%s" % (f, st)] = wv.last_overlaps[:6]
        if st == "hold":
            assert not wv.last_overlaps, "字が重なった（全部の動画、コマ %d）：%s" % (f, wv.last_overlaps[:6])
            im.save(os.path.join(out, "%s_best_f%05d.png" % (name, f)))
        wr.put(im, n)
        if j % 100 == 0:
            log("  whole %d/%d f%d %.0f s" % (j, len(sch), f, time.time() - t_r))
    wr.close()
    pb = GV.probe(path)
    info = dict(video=path, made=time.strftime("%Y-%m-%d %H:%M:%S"), tool=TOOL + " whole", run=S.rid, rd=S.rd, speed=wv.speed, hold_s=wv.hold,
                t=[S.t(frs[0]), S.t(frs[-1])], best_frames={r.lab: dict(frame=r.best_f, t=r.tf.get(r.best_f)) for r in wv.runs},
                written_frames=wr.n, ffprobe=pb, ok=bool(pb.get("ok") and pb.get("frames") == wr.n), text_overlap_frames=len(ov_all),
                text_overlaps_sample=dict(list(ov_all.items())[:12]), elapsed_s=round(time.time() - t_start, 1),
                note_ja="指導教員の長い動画の頼み（Q66）：計算の全部を %g 倍で。赤い枠＝pana/best_frames.json の原画に最も近いコマ" % wv.speed)
    json.dump(A46._clean(info), open(os.path.join(out, name + ".json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    log(json.dumps(A46._clean(dict(video=path, ok=info["ok"], frames=wr.n, overlaps=len(ov_all), elapsed_s=info["elapsed_s"])), ensure_ascii=False))
    return info


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    pos, opt = G2.parse_opt(sys.argv[1:])
    if len(pos) < 2:
        print(__doc__); sys.exit(1)
    cmd, rd = pos[0], pos[1]
    try:
        if cmd == "compare":
            make_compare(rd, opt)
        elif cmd == "whole":
            make_whole(rd, opt)
        elif cmd == "all":
            S = Shared(rd)
            make_compare(rd, opt, S=S)
            make_whole(rd, opt, S=S)
        else:
            print(__doc__); sys.exit(1)
    except G2.InputError as e:
        print("止めた：%s" % e); sys.exit(2)


if __name__ == "__main__":
    main()
