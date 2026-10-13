# -*- coding: utf-8 -*-
"""FLIP47：2D の板の計算の動画（py -3.10 -B。numpy・scipy・scikit-image・PIL と ffmpeg）。
2026-10-13 動画の役（Claude）が新しく書いた。FLIP44 の g44_video.py・FLIP45 の g45_video.py（どちらも変えていない）の描き方を写した：
PIL で描いて ffmpeg へ直接流す（コマの画像は残さない）、縦横同じ縮尺、10 m の目盛り、静かな水面の点線、海底を砂の色、24 コマ/s。
水の読みは g47_analyze.py（変えずに読み込む）の Ctx（記録・静かな水面のずれ・海底）、top_surface、fine_mask、s52_measure、mask_lines を
そのまま使う。だから右下の数は ana47 の細かい読みと同じ物差し（STUDY52 s52_shape.measure_mask）の値になる。書くのは Unity/Build/FLIP47 の中だけ。

1 コマの並び（1920×1080）：
  上　　：領域の全部の断面（縦横同じ縮尺、海底、静かな水面、10 m の目盛り、左下の拡大の窓を赤の枠で）。領域が 900 m より長い時は段に分ける。
  左下　：崩れる頂を追う拡大（縦横同じ縮尺、10 m と 5 m の目盛り）。巻き始め〜着水の間は、原画の輪郭（縦の伸びを戻した形）を
          そのコマの η_c と頂の位置に合わせて重ねる（細い黒の破線）。原画に最も近いコマでは太い黒の線。
  右下　：同じ物差しの重ね（η_c で割り頂の位置をそろえた今のコマの形と原画の輪郭）。巻いている間（巻き始め〜着水の 0.5 s 後）だけ描き、
          ほかの時は空ける。その下に、今のコマの前の面の弦・唇の下の空気・唇の厚み・覆いの面積・前の足・後ろの角・0.7 η_c の幅と、原画の値と帯。
  下　　：時刻の帯（巻き始め・原画に最も近いコマ・着水の印、スローの間の色）。右上に時刻と再生の速さ（実時間／スロー／止め）。

崩れの見つけ方（周期の波の長い計算でも使えるように、ana47 に頼らない）：
  コマごとに一番上の水面の山（高さ 0.5 m 以上、際立ち 0.3 m 以上、山の間は 1.5 h0 か 27 m の小さい方以上）を拾い、コマの間でつなぐ
  （g47_analyze.coarse_frame と同じ幅：前のコマの位置の −6 m〜+12 m／コマ）。山ごとに、頂から前の面の線に沿った格子 1 個分の弦の向きの
  最大を測り（coarse_frame と同じ）、90° 以上になった最初のコマを巻き始めとする（山ができてから 1 s 以上、頂 1 m 以上）。巻き始めの順に k = 1, 2, …。
  前の崩れの巻き始めの後 6 s の内に、その巻き始めの 10 m 後ろより前で生まれた山の巻き（着水の後の跳ね上がりの巻き）は数えない（events に別に出す）。
  ana47 の巻き始めと 2 コマ以内で合う崩れには ana47 の巻き始め・着水を使う。合わない崩れの着水は粗い読み
  （記録の格子で、頂の後ろ 0.5 η〜前 3 η の、静かな水面より上に閉じた空気の穴が格子 2 個以上できた最初のコマ）。
原画に最も近いコマ：海底の組の scan_summary.json の score3 最小（SCAN_RESULT_ja.md の決まり）→ この道具で測った score3 の最小
  （同じ決まりを巻き始め〜着水に当てる）→ ana47 の 5 つの点数の最小、の順に使い、どれを使ったかを動画と json に書く。

使い方：
  py -3.10 -B g47_video.py run <run_id か記録の置き場所> [--out=<置き場所>] [--name=<ファイル名の頭>] [--layer=sdf|mean|0|1|2|3]
         [--k=1] [--t0=<s>] [--t1=<s>] [--around=1 --pre=8 --post=3] [--speed=1] [--slow=0.25] [--slow_pre=1.0] [--slow_post=0.5]
         [--hold=1.0] [--zoom_w=auto|<m>] [--zoom_at=0.45] [--label=<頭に足す言葉>] [--still=<コマ>]
     → <out>/<name>.mp4 と <name>.json（作った時の値と ffprobe の確かめ）。out の既定は Unity/Build/FLIP47/videos。
     既定：記録の全部を実時間で、k 番目の崩れの「巻き始めの 1 s 前〜着水の 0.5 s 後」を 0.25 倍のスロー、原画に最も近いコマで 1 s 止める。
     記録が 90 s より長く、t0・t1 も around も与えない時は、k 番目の崩れの巻き始めの 8 s 前〜着水の 3 s 後だけ。
     --slow=1 でスローなし、--hold=0 で止めなし、--speed=2 で全部を 2 倍の速さ（長い計算を早送りで見る時）。
  py -3.10 -B g47_video.py montage <run_id>[@k] ... [--out=..] [--name=..] [--tau0=-5] [--tau1=<s>] [--slow=0.25] [--slow_tau=a,b] [--hold_end=3]
     → 2×3 の並び（6 本まで）。各計算の着水の時刻にそろえ（τ = t − t着水）、崩れの間をスロー。終わりに、各計算の原画に最も近いコマで止める。
     <run_id>@k で同じ計算の k 番目の崩れ（周期の波の回を並べる時。例 P1@5 P1@6 P1@7）。
     上の全部の断面には、入口の帯（relax_on）・吸う帯（abs_on）が入っている計算ならその範囲を色で示す（run の動画）。
  py -3.10 -B g47_video.py events <run_id か置き場所> [--layer=..]   → 見つけた崩れの表（k、巻き始め、着水、ana47 との合い方）
  py -3.10 -B g47_video.py probe <mp4> ...                            → ffprobe の長さ・コマ数
  py -3.10 -B g47_video.py scanset                                    → 2026-10-13 の組（S1＝E1a_short・S2〜S6・E1a_full の 7 本と並べた 1 本）
"""
import sys, os, json, math, glob, time, subprocess
sys.dont_write_bytecode = True
import numpy as np
from scipy import ndimage as ndi
from scipy.signal import find_peaks
from skimage import measure
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import g47_analyze as GA          # noqa: E402  読むだけ（変えない）
import g47_common as GCM          # noqa: E402  優先度を「通常より下」にするためだけ
S52 = GA.S52
TG = GA.TG

B47 = GA.B47
RUNS = B47 + "/runs"
VID = B47 + "/videos"
CACHE = VID + "/_cache"
FPS = 24
W, H = 1920, 1080
TRACK_VER = 3

BG = (247, 247, 244); WATER = (38, 86, 128); SAND = (196, 178, 140); LINE = (150, 150, 150); OUTSIDE = (222, 222, 218)
TXT = (25, 25, 25); SUB = (95, 95, 92); RED = (200, 40, 40); GREEN = (30, 140, 60); PURP = (150, 60, 170)
ORANGE = (225, 120, 20); BLUE = (20, 60, 200); GREY = (150, 150, 150); YEL = (240, 200, 0)
SC3 = ["face_chord_deg_01_05", "front_x01_rel", "hood_area"]
LAYER_DIR = {"sdf": "ana47", "mean": "ana47_zmean", "0": "ana47_z0", "1": "ana47_z1", "2": "ana47_z2", "3": "ana47_z3"}


def _ffmpeg():
    """ffmpeg の置き場所は FLIP45 の g45_common.FFMPEG と同じ物（ファイルを読むだけ）。"""
    p = GA.REPO + "/Tools/GWWaveGen/flip45/g45_common.py"
    try:
        for line in open(p, encoding="utf8"):
            if line.startswith("FFMPEG"):
                v = line.split("=", 1)[1].strip()
                v = v[1:] if v.startswith("r") else v
                v = v.strip('"').strip("'")
                if os.path.exists(v):
                    return v
    except Exception:
        pass
    return r"G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"


FF = _ffmpeg()
FP = os.path.join(os.path.dirname(FF), "ffprobe.exe")

_F = {}


def font(sz, b=False):
    k = (int(sz), bool(b))
    if k not in _F:
        _F[k] = ImageFont.truetype(GA.FONTB if b else GA.FONT, int(sz))
    return _F[k]


def text_fit(dr, xy, s, maxw, sz, b=False, fill=TXT, minsz=11):
    while sz > minsz and dr.textlength(s, font=font(sz, b)) > maxw:
        sz -= 1
    dr.text(xy, s, fill=fill, font=font(sz, b))
    return sz


def guard_out(p):
    a = os.path.abspath(p).replace("\\", "/")
    if not a.lower().startswith(os.path.abspath(B47).replace("\\", "/").lower()):
        raise GA.InputError("書く所は Unity/Build/FLIP47 の中だけ：%s" % a)
    return a


def jdump(o, p):
    json.dump(GA.clean(o), open(p, "w", encoding="utf8"), ensure_ascii=False, indent=1)


# ======================================================================== 線を描く小さな道具
def dashed(dr, pts, fill, width=2, on=9.0, off=6.0):
    P = np.asarray(pts, float)
    if len(P) < 2:
        return
    seg = np.hypot(*np.diff(P, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    L = s[-1]
    a = 0.0
    while a < L:
        b = min(a + on, L)
        q = np.linspace(a, b, max(2, int((b - a) / 2.0) + 2))
        dr.line(list(zip(np.interp(q, s, P[:, 0]), np.interp(q, s, P[:, 1]))), fill=fill, width=width)
        a += on + off


def split_inside(P, x0, x1, y0, y1):
    """点の並びを、箱 [x0,x1]×[y0,y1] の中の続いた所ごとに切る（外の点をつながない）。"""
    P = np.asarray(P, float)
    ok = (P[:, 0] >= x0) & (P[:, 0] <= x1) & (P[:, 1] >= y0) & (P[:, 1] <= y1)
    out, cur = [], []
    for i in range(len(P)):
        if ok[i]:
            cur.append(P[i])
        elif cur:
            if len(cur) >= 2:
                out.append(np.array(cur))
            cur = []
    if len(cur) >= 2:
        out.append(np.array(cur))
    return out


def label_box(dr, xy, s, fill, fnt):
    """水や砂の上でも読めるように、白い下地の上に字を置く。"""
    x, y = xy
    l, t, r, b = dr.textbbox((x, y), s, font=fnt)
    dr.rectangle([l - 3, t - 2, r + 3, b + 2], fill=(255, 255, 255))
    dr.text((x, y), s, fill=fill, font=fnt)


def poly(dr, P, fill, width, dash=False):
    if len(P) < 2:
        return
    if dash:
        dashed(dr, P, fill, width)
    else:
        dr.line([tuple(p) for p in P], fill=fill, width=width, joint="curve")


# ======================================================================== 原画（STUDY52 と同じ読み）
_PR = None


def print_ref():
    """原画の輪郭を η_c で割り頂をそろえた座標（g47_analyze.overlay_figure と同じ変換）と、帯（g47_targets.print_bands）。"""
    global _PR
    if _PR is None:
        pr = json.load(open(GA.STUDY52 + "/shape_measures.json", encoding="utf8"))
        outer, inner, _ = S52.print_outline()

        def conv(k, sy):
            p = pr["print"][k]
            f = lambda a: np.stack([(a[:, 0] - p["x_c"]) / p["eta_c"], (S52.Y_HORIZON - a[:, 1]) * sy / p["eta_c"]], 1)
            return [f(outer), f(inner)]
        names = ["drawn", "cn", "cn_swl_low", "cn_swl_high"]
        extra = {k: [min(pr["print"][n][k] for n in names), max(pr["print"][n][k] for n in names)]
                 for k in ("back_angle_07_09_deg", "width07_silhouette")}
        _PR = dict(cn=conv("cn", 1.0 / S52.STRETCH), drawn=conv("drawn", 1.0), bands=(TG.print_bands(pr) if TG else None),
                   cnv=pr["print"]["cn"], extra=extra)
    return _PR


def score3(m):
    if not m or TG is None:
        return None, None
    _, parts = TG.score(m, print_ref()["bands"])
    return round(sum((parts.get(k) or 0.0) for k in SC3), 3), parts


# ======================================================================== 1 本の計算
def resolve_run(ref):
    for p in (ref, os.path.join(RUNS, ref), os.path.join(B47, "smoke", ref), os.path.join(B47, ref)):
        if os.path.isdir(p) and glob.glob(os.path.join(p, "*_c*_b*.npz")):
            return os.path.abspath(p).replace("\\", "/").rstrip("/")
    raise GA.InputError("計算の記録が見つからない：%s" % ref)


def bed_text(bed):
    if not bed:
        return "海底：cfg に海底の折れ線がない（記録の最初のコマから読んだ）"
    b = [(float(p[0]), float(p[1])) for p in bed]
    parts = []
    for (xa, da), (xb, db) in zip(b[:-1], b[1:]):
        if abs(db - da) < 1e-6:
            parts.append("水深 %.3g m の平ら（x %.0f〜%.0f m）" % (da, xa, xb))
        elif abs(xb - xa) < 1e-6:
            parts.append("x %.0f m で鉛直の段（水深 %.3g → %.3g m）" % (xa, da, db))
        else:
            s = abs(da - db) / (xb - xa)
            parts.append("勾配 1:%.3g（%.4g）で x %.0f m まで（水深 %.3g m へ）" % (1.0 / s, s, xb, db))
    return "海底：" + " → ".join(parts) + "。両端の外は端の水深で平ら"


def wave_text(cfg, h0):
    s = cfg.get("solitary")
    if isinstance(s, dict) and s.get("a_over_h") is not None:
        kind = {"gn": "GN（Green–Naghdi）の孤立波", "exact": "厳密な孤立波"}.get(str(s.get("kind")).lower(), "%s の孤立波" % s.get("kind"))
        a = float(s["a_over_h"])
        return "波：%s a0/h0 %g（a0 %.3g m、h0 %g m）、頂の始め x %g m" % (kind, a, a * h0, h0, float(s.get("x0", float("nan"))))
    for k in ("wave", "inlet", "table", "group"):
        v = cfg.get(k)
        if isinstance(v, dict) and (v.get("name_ja") or v.get("name")):
            return "波：" + str(v.get("name_ja") or v.get("name"))
    return "波：" + str(cfg.get("note") or "（cfg に波の説明がない）")


def face_thmax(main, xc, h0, vox):
    """頂から前の面の線に沿って、格子 1 個分の弦の向きの最大（g47_analyze.coarse_frame と同じ計り方）。"""
    near = np.where(np.abs(main[:, 0] - xc) <= 2.0 * vox + 1e-6)[0]
    if not len(near):
        return None
    ic = int(near[np.argmax(main[near, 1])])
    fwd = main[ic:]
    if len(fwd) < 3:
        return None
    stop = (fwd[1:, 1] <= 0.0) | (np.abs(fwd[1:, 0] - xc) > 3.0 * h0)
    j_end = int(np.argmax(stop)) + 2 if stop.any() else len(fwd)
    face = GA.resample(fwd[:j_end], 0.5 * vox)
    if len(face) < 3:
        return None
    d = face[2:] - face[:-2]
    th = np.degrees(np.arctan2(-d[:, 1], d[:, 0]))
    okm = (th >= 0) & (th <= 180)
    return float(th[okm].max()) if okm.any() else None


def link_tracks(rows):
    """コマの間で山をつなぐ（前のコマの位置の −6 m〜+12 m／コマの中で、速さから見込んだ位置にいちばん近い山）。"""
    tracks, active = [], []
    for f, t, pk in rows:
        cand = []
        for ti, tr in enumerate(active):
            nf = f - tr["f"][-1]
            xl = tr["x"][-1]
            v = (tr["x"][-1] - tr["x"][-4]) / max(tr["f"][-1] - tr["f"][-4], 1) if len(tr["x"]) >= 4 else 0.0
            xp = xl + v * nf
            for j, p in enumerate(pk):
                if xl - 6.0 * nf <= p[0] <= xl + 12.0 * nf:
                    cand.append((abs(p[0] - xp), ti, j))
        cand.sort()
        ut, up = set(), set()
        for _, ti, j in cand:
            if ti in ut or j in up:
                continue
            tr = active[ti]; x, eta, th = pk[j]
            tr["f"].append(f); tr["t"].append(t); tr["x"].append(x); tr["eta"].append(eta); tr["th"].append(th)
            ut.add(ti); up.add(j)
        for j, (x, eta, th) in enumerate(pk):
            if j not in up:
                tr = dict(id=len(tracks), f=[f], t=[t], x=[x], eta=[eta], th=[th])
                tracks.append(tr); active.append(tr)
        active = [tr for tr in active if f - tr["f"][-1] <= 6]
    return tracks


class Run:
    def __init__(self, ref, layer="sdf", log=print):
        self.log = log
        self.rd = resolve_run(ref)
        self.rid = os.path.basename(self.rd)
        self.layer = str(layer)
        if self.layer not in LAYER_DIR:
            raise GA.InputError("--layer は sdf・mean・0・1・2・3 のどれか：%s" % layer)
        ap = os.path.join(self.rd, LAYER_DIR[self.layer], "g47_ana.json")
        self.ana = json.load(open(ap, encoding="utf8")) if os.path.exists(ap) else None
        self.ana_path = ap if self.ana else None
        opt = {}
        if self.ana and self.ana.get("still_offset_m") is not None:
            opt["off"] = float(self.ana["still_offset_m"])
        self.cx = GA.Ctx(self.rd, opt)
        self.layer_z = self._layer_z()
        if self.layer != "sdf":
            self._patch_layer()
        self.cfg = self.cx.cfg
        self.frames = list(self.cx.rec.frames)
        self.tf = {f: self.cx.t(f) for f in self.frames}
        self.h0, self.vox = self.cx.h0, self.cx.vox
        self.xs, self.ys = self.cx.xs, self.cx.ys
        self.dp = self.cx.dp
        self.bed = self.cfg.get("bed") or (self.cx.P.get("bed"))
        self.scan_sum, self.scan_best = self._scan_summary()
        self.label = self._label()
        self._S = (None, None)
        self.meas = {}
        self.checks = {}

    # ---- 層
    def _layer_z(self):
        m = self.cx.rec.meta
        if self.layer == "sdf":
            return float(m.get("z", float("nan")))
        zl = None
        for p in sorted(glob.glob(os.path.join(self.rd, "hf_c*.npz"))):
            try:
                zl = [float(v) for v in np.load(p)["z"]]
                break
            except Exception:
                pass
        if self.layer == "mean":
            return None
        if zl and int(self.layer) < len(zl):
            return zl[int(self.layer)]
        return float("nan")

    def _patch_layer(self):
        rec, sel, st = self.cx.rec, self.layer, {}

        def get(f):
            f0, p, i, _, _ = rec.best[f]
            if st.get("p") != p:
                d = np.load(p)
                if "sdfz" not in d.files:
                    raise GA.InputError("板の層ごとの記録（sdfz）がない：%s" % p)
                st["z"] = d["sdfz"]; st["p"] = p
            a = st["z"][i].astype(np.float32)
            return a.mean(axis=0) if sel == "mean" else a[int(sel)]
        rec.get = get

    def layer_text(self):
        if self.layer == "sdf":
            return "板の層 z %+.2f m の断面（主の読み、ana47 と同じ）" % self.layer_z
        if self.layer == "mean":
            return "板の 4 層の平均の場"
        return "板の層 z %+.2f m の断面" % self.layer_z

    # ---- 海底の組の読み（score3）
    def _scan_summary(self):
        for p in (os.path.join(self.rd, "ana47", "scan_summary.json"), os.path.join(RUNS, "SCAN_compare", "scan_summary_%s.json" % self.rid)):
            if os.path.exists(p):
                try:
                    s = json.load(open(p, encoding="utf8"))
                except Exception:
                    continue
                if self.layer == "sdf":
                    b = s.get("best3")
                else:
                    b = ((s.get("slices") or {}).get(self.layer) or {}).get("best3")
                return p, b
        return None, None

    def _label(self):
        p = os.path.join(RUNS, "SCAN_compare", "scan_table.json")
        if os.path.exists(p):
            try:
                for r in json.load(open(p, encoding="utf8")).get("rows", []):
                    if r.get("run") == self.rid and r.get("label"):
                        return r["label"]
            except Exception:
                pass
        c = self.cfg.get("case") or {}
        return c.get("name_ja") or c.get("name") or self.rid

    def title_text(self):
        c = self.cfg.get("case") or {}
        nm = c.get("name_ja")
        if not nm and str(c.get("name", "")).startswith("E1a"):
            nm = "E1a（Feddersen ら 2024）の海底と波"
        return "FLIP47 %s　%s" % (self.rid, nm or self.label)

    # ---- 場
    def S(self, f):
        """コマ f の場（図のため）。海底の中と海底の上の格子の半分は g47_analyze と同じく水で埋める（そこは上から砂の色で塗るので、
        見えるのは海底と記録の水の間の細い隙間が消えることだけ）。最後の 1 コマを覚える。"""
        if self._S[0] != f:
            self._S = (f, self.cx.sdf(f, fill_bed=True))
        return self._S[1]

    def t(self, f):
        return self.tf[f]

    def zones(self):
        """入口の帯（relax_on）と吸う帯（abs_on）の x の範囲（この道具の x、つまり計画の座標 − 基準）。切ってあれば空。"""
        P = self.cx.P; out = []
        try:
            xr = self.cx.xref
            if float(P.get("relax_on", 0)) > 0.5 and P.get("xg_end") is not None:
                out.append((float(P["x0"]) - xr, float(P["xg_end"]) - xr, "入口の帯（波を寄せる、x %.0f〜%.0f m）" % (float(P["x0"]) - xr, float(P["xg_end"]) - xr), (225, 120, 20)))
            if float(P.get("abs_on", 0)) > 0.5 and float(P.get("xa0", 1e9)) < 1e8:
                x1 = float(P["x0"]) + float(P["Lx"])
                out.append((float(P["xa0"]) - xr, x1 - xr, "吸う帯（x %.0f m から）" % (float(P["xa0"]) - xr), (120, 60, 160)))
        except Exception:
            return []
        return out

    def frame_at(self, t):
        return min(self.frames, key=lambda q: abs(self.tf[q] - t))

    def x_range(self):
        return float(self.xs[0] - 0.5 * self.vox), float(self.xs[-1] + 0.5 * self.vox)

    # ---- 山と崩れ
    def surface_rows(self):
        os.makedirs(CACHE, exist_ok=True)
        files = sorted(glob.glob(os.path.join(self.rd, "*_c*_b*.npz")))
        key = dict(ver=TRACK_VER, rid=self.rid, layer=self.layer, off=round(self.cx.off, 6), n=len(self.frames),
                   files=[[os.path.basename(p), os.path.getsize(p), int(os.path.getmtime(p))] for p in files])
        cp = os.path.join(CACHE, "%s_%s_surf.json" % (self.rid, self.layer))
        if os.path.exists(cp):
            try:
                d = json.load(open(cp, encoding="utf8"))
                if d.get("key") == key:
                    return d["rows"]
            except Exception:
                pass
        t0 = time.time()
        rows = []
        dist = max(1, int(min(27.0, 1.5 * self.h0) / (self.xs[1] - self.xs[0])))
        for f in self.frames:
            S = self.cx.sdf(f)
            top = GA.top_surface(S, self.ys)
            topf = np.nan_to_num(top, nan=-99.0)
            pk, _ = find_peaks(topf, prominence=0.3, distance=dist)
            pk = [int(i) for i in pk if topf[i] >= 0.5]
            out = []
            if pk:
                lines = [np.stack([self.xs[0] + c[:, 1] * (self.xs[1] - self.xs[0]), self.ys[0] + c[:, 0] * (self.ys[1] - self.ys[0])], 1)
                         for c in measure.find_contours(S, 0.0)]
                main = None
                if lines:
                    main = lines[int(np.argmax([l[:, 0].max() - l[:, 0].min() for l in lines]))]
                    if main[0, 0] > main[-1, 0]:
                        main = main[::-1]
                for i in pk:
                    th = face_thmax(main, float(self.xs[i]), self.h0, self.vox) if main is not None else None
                    out.append([round(float(self.xs[i]), 3), round(float(topf[i]), 4), (round(th, 2) if th is not None else None)])
            rows.append([int(f), float(self.tf[f]), out])
        jdump(dict(key=key, rows=rows, made=time.strftime("%Y-%m-%d %H:%M:%S"), elapsed_s=time.time() - t0), cp)
        self.log("  山の読み %s（%d コマ、%.0f s）" % (self.rid, len(rows), time.time() - t0))
        return rows

    def events(self, min_eta=1.0, min_age=1.0):
        rows = self.surface_rows()
        self.tracks = link_tracks(rows)
        self.max_eta_all = max([p[1] for r in rows for p in r[2]] or [1.0])
        evs = []
        for tr in self.tracks:
            for i in range(len(tr["f"])):
                th = tr["th"][i]
                if th is not None and th >= 90.0 and tr["eta"][i] >= min_eta and tr["t"][i] - tr["t"][0] >= min_age - 1e-9:
                    evs.append(dict(track=tr, i_on=i, on_f=tr["f"][i], on_t=tr["t"][i], on_x=tr["x"][i], on_eta=tr["eta"][i]))
                    break
        evs.sort(key=lambda e: e["on_t"])
        merged, self.after_evs = [], []
        for e in evs:
            if merged and abs(e["on_t"] - merged[-1]["on_t"]) <= 0.5 and abs(e["on_x"] - merged[-1]["on_x"]) <= 10.0:
                continue
            # 前の崩れの巻き始めの後 6 s の内に、その巻き始めの 10 m 後ろより前で生まれた山の筋は、同じ波の着水の後の跳ね上がりの巻き（数えない）
            tr = e["track"]
            if any(p["on_t"] <= tr["t"][0] <= p["on_t"] + 6.0 and tr["x"][0] >= p["on_x"] - 10.0 for p in merged):
                # 表のため：山の筋の中で、山ができてからの時間を問わずに前の面が初めて 90° 以上になったコマ
                i0 = next(i for i in range(len(tr["f"])) if tr["th"][i] is not None and tr["th"][i] >= 90.0 and tr["eta"][i] >= min_eta)
                e.update(first_f=tr["f"][i0], first_t=tr["t"][i0], first_x=tr["x"][i0], first_eta=tr["eta"][i0])
                self.after_evs.append(e)
                continue
            merged.append(e)
        aon = (self.ana or {}).get("onset") or {}
        best_match = None
        if aon.get("frame") is not None:
            cands = [e for e in merged if abs(e["on_f"] - int(aon["frame"])) <= 2]
            if cands:
                best_match = min(cands, key=lambda e: abs(e["on_f"] - int(aon["frame"])))
        for k, e in enumerate(merged):
            e["k"] = k + 1
            e["ana"] = e is best_match
            e["own_on_f"] = e["on_f"]
            if e["ana"]:
                e["on_f"] = int(aon["frame"]); e["on_t"] = float(aon["t"]); e["on_src"] = "ana47（g47_analyze の巻き始め）"
                td = (self.ana or {}).get("touchdown") or {}
                if td.get("frame") is not None:
                    e["td_f"] = int(td["frame"]); e["td_t"] = float(td["t"])
                    e["td_src"] = "ana47（%s）" % ("隙間 0.015 h0 以下" if td.get("by") == "gap<=0.015h0" else "噴流の下に閉じた空気")
            else:
                e["on_src"] = "この道具（前の面の弦が 90° 以上の最初のコマ）"
            f_td = self.td_coarse(e)
            e["own_td_f"] = f_td
            if "td_f" not in e:
                if f_td is not None:
                    e["td_f"] = f_td; e["td_t"] = self.tf[f_td]
                    e["td_src"] = "粗い読み（記録の格子で頂の近くに閉じた空気の穴、格子 2 個以上）"
        self.evs = merged
        return merged

    def td_coarse(self, e, max_s=5.0, min_cells=2):
        tr = e["track"]
        xt = dict(zip(tr["f"], tr["x"])); et = dict(zip(tr["f"], tr["eta"]))
        xl, el = e["on_x"], e["on_eta"]
        for f in self.frames:
            if f <= e["own_on_f"] or self.tf[f] > e["on_t"] + max_s:
                continue
            xl = xt.get(f, xl); el = max(et.get(f, el), 1.0)
            S = self.cx.sdf(f)
            air = S >= 0
            lab, n = ndi.label(air)
            if n == 0:
                continue
            edge = set(np.unique(lab[-1, :]).tolist()) | set(np.unique(lab[:, 0]).tolist()) | set(np.unique(lab[:, -1]).tolist())
            cnt = np.bincount(lab.ravel(), minlength=n + 1)
            ks = [k for k in range(1, n + 1) if k not in edge and cnt[k] >= min_cells]
            if not ks:
                continue
            cms = ndi.center_of_mass(air, lab, ks)
            for (cj, ci) in cms:
                xcm = self.xs[0] + ci * (self.xs[1] - self.xs[0]); zcm = self.ys[0] + cj * (self.ys[1] - self.ys[0])
                if xl - 0.5 * el <= xcm <= xl + 3.0 * el and zcm >= -0.1 * el:
                    return f
        return None

    def main_track(self):
        return max(self.tracks, key=lambda tr: max(tr["eta"]))

    # ---- 崩れの読みの用意（巻き始めの pre s 前〜着水の post s 後）
    def prep(self, e, pre=1.0, post=0.5):
        tr = e["track"]
        xt = dict(zip(tr["f"], tr["x"]))
        t_end = e.get("td_t", e["on_t"] + 2.0) + post
        win = [f for f in self.frames if e["on_t"] - pre - 1e-9 <= self.tf[f] <= t_end + 1e-9]
        anafine = {int(w["frame"]): w for w in ((self.ana or {}).get("fine") or [])} if e.get("ana") else {}
        diffs = []
        t0 = time.time()
        for f in win:
            if f in self.meas:
                continue
            hint = anafine[f]["xc"] if f in anafine else xt.get(f, self.cam_x(f) if hasattr(self, "_cam") else e["on_x"])
            S = self.cx.sdf(f)
            try:
                M, X, Z = GA.fine_mask(self.cx, f, hint, S=S)
            except Exception as ex:
                self.meas[f] = dict(err=repr(ex)[:120]); continue
            m52, err = GA.s52_measure(M, X, Z)
            if m52:
                eta, xc = float(m52["eta_c"]), float(m52["x_c"])
            else:
                eta = float(Z[np.where(M.any(1))[0].max()] + 0.5 * GA.FINE); xc = float(hint)
            m = GA.pick52(m52) if m52 else None
            sc, parts = score3(m)
            lines = GA.mask_lines(M, X, Z, xc, eta)
            self.meas[f] = dict(x_c=xc, eta_c=eta, m=m, err=err, score3=sc, parts=parts, lines=lines)
            if f in anafine and anafine[f].get("s52") and m:
                a = anafine[f]["s52"]
                diffs.append(max(abs((a.get(k) or 0.0) - (m.get(k) or 0.0)) for k in ("face_chord_deg_01_05", "gap_max", "lip_thick_mid", "hood_area")))
        self.checks["prep_s"] = round(time.time() - t0, 1)
        self.checks["ana47_vs_live_max_abs_diff"] = (max(diffs) if diffs else None)
        self.checks["ana47_vs_live_n"] = len(diffs)
        # この道具で測った score3 の最小（巻き始め〜着水）
        cand = [f for f in win if e["on_f"] <= f <= e.get("td_f", win[-1]) and self.meas.get(f, {}).get("score3") is not None]
        live = min(cand, key=lambda f: (self.meas[f]["score3"], -((self.meas[f]["m"] or {}).get("hood_height_m") or 0.0))) if cand else None
        e["best_live_f"] = live
        if e.get("ana") and self.scan_best and self.scan_best.get("frame") is not None:
            e["best_f"] = int(self.scan_best["frame"])
            e["best_src"] = "score3 の最小（弦・足・覆い。SCAN_RESULT_ja.md の決まり、scan_summary.json）"
        elif live is not None:
            e["best_f"] = live
            e["best_src"] = "score3 の最小（弦・足・覆い。SCAN_RESULT_ja.md の決まりを、この道具で巻き始め〜着水に当てた）"
        elif e.get("ana") and ((self.ana.get("score") or {}).get("best") or {}).get("frame") is not None:
            e["best_f"] = int(self.ana["score"]["best"]["frame"])
            e["best_src"] = "5 つの点数の最小（targets_ja.md §5、ana47）"
        self.checks["best_used"] = e.get("best_f"); self.checks["best_live"] = live
        return win

    # ---- 窓の位置（頂を追う）
    def make_camera(self, e, ext_s=3.0):
        if e is None:
            tr = self.main_track(); cut_f = tr["f"][-1]
        else:
            tr = e["track"]; cut_f = min(e.get("td_f", tr["f"][-1]), tr["f"][-1])
        fs = [f for f in tr["f"] if f <= cut_f]
        xr = np.array([x for f, x in zip(tr["f"], tr["x"]) if f <= cut_f])
        ts = np.array([self.tf[f] for f in fs])
        # ±6 コマの一次の当てはめで均す（端で遅れない）
        xsm = np.empty(len(xr))
        for i in range(len(xr)):
            a, b = max(0, i - 6), min(len(xr), i + 7)
            if b - a >= 3:
                p = np.polyfit(ts[a:b] - ts[i], xr[a:b], 1)
                xsm[i] = p[1]
            else:
                xsm[i] = xr[a:b].mean()
        # 頂の筋の終わり（着水）より後は、終わりの 1 s の頂の速さと、巻き始めの前の 1 s の頂の速さの大きい方で進める（ext_s まで）。
        # 着水の後の跳ね上がりは、巻き始めの前の頂とほぼ同じ速さで前へ出るため（S2 の記録を見て決めた）
        k = ts >= ts[-1] - 1.0
        v = float(np.polyfit(ts[k], xr[k], 1)[0]) if k.sum() >= 3 else 0.0
        if e is not None:
            kp = (ts >= e["on_t"] - 1.0) & (ts <= e["on_t"])
            if kp.sum() >= 3:
                v = max(v, float(np.polyfit(ts[kp], xr[kp], 1)[0]))
        v = max(v, 0.0)
        cam = {}
        for f in self.frames:
            t = self.tf[f]
            if t <= ts[0]:
                cam[f] = xsm[0]
            elif t <= ts[-1]:
                cam[f] = float(np.interp(t, ts, xsm))
            else:
                cam[f] = xsm[-1] + v * min(t - ts[-1], ext_s)
        vals = np.maximum.accumulate(np.array([cam[f] for f in self.frames]))
        self._cam = {f: float(x) for f, x in zip(self.frames, vals)}
        self._cam_ev = e
        self._cam_v_after = v
        return self._cam

    def cam_x(self, f):
        return self._cam[f]

    def zoom_at(self, f, base=0.45):
        """窓の中の頂の位置（左から）。巻き始めまで base、着水へ 0.35、着水の 0.5 s 後へ 0.25（跳ね上がりが窓の前に出ないように）。"""
        e = getattr(self, "_cam_ev", None)
        if e is None:
            return base
        t = self.tf[f]; ton = e["on_t"]; ttd = e.get("td_t", ton + 2.0)
        if t <= ton:
            return base
        if t <= ttd:
            return base + (0.35 - base) * (t - ton) / max(ttd - ton, 1e-6)
        return 0.35 + (0.25 - 0.35) * min((t - ttd) / 0.5, 1.0)


# ======================================================================== 描く
def sample_water(S, xs, ys, Xp, Zp):
    """記録の場（水で負）を画素の中心で一次の補間。Zp は上から下。戻り値：水 [len(Zp), len(Xp)]、x が記録の中か。"""
    dx = xs[1] - xs[0]; dy = ys[1] - ys[0]
    fx = (Xp - xs[0]) / dx; fz = (Zp - ys[0]) / dy
    vx = (fx >= -0.5) & (fx <= len(xs) - 0.5); vz = (fz >= -0.5) & (fz <= len(ys) - 0.5)
    fx = np.clip(fx, 0, len(xs) - 1.001); fz = np.clip(fz, 0, len(ys) - 1.001)
    ix = np.floor(fx).astype(int); wx = fx - ix; iz = np.floor(fz).astype(int); wz = fz - iz
    A = S[iz][:, ix] * (1 - wx)[None, :] + S[iz][:, ix + 1] * wx[None, :]
    B = S[iz + 1][:, ix] * (1 - wx)[None, :] + S[iz + 1][:, ix + 1] * wx[None, :]
    F = A * (1 - wz)[:, None] + B * wz[:, None]
    return (F < 0) & vz[:, None] & vx[None, :], vx


class Box:
    """縦横同じ縮尺の箱：x0..x1・z0..z1（m）を左上 (px, py) から s 画素/m で。"""

    def __init__(self, px, py, s, x0, x1, z0, z1):
        self.px, self.py, self.s, self.x0, self.x1, self.z0, self.z1 = px, py, s, x0, x1, z0, z1
        self.pw = int(round((x1 - x0) * s)); self.ph = int(round((z1 - z0) * s))

    def X(self, x):
        return self.px + (x - self.x0) * self.s

    def Y(self, z):
        return self.py + (self.z1 - z) * self.s

    def pts(self, P):
        P = np.asarray(P, float)
        return np.stack([self.X(P[:, 0]), self.Y(P[:, 1])], 1)

    def clip(self, P):
        return [self.pts(q) for q in split_inside(P, self.x0, self.x1, self.z0, self.z1)]


def draw_field(im, dr, run, f, bx, tick=10.0, tick_lab=True, bar10=True, bar5=False, small=False):
    Xp = bx.x0 + (np.arange(bx.pw) + 0.5) / bx.s
    Zp = bx.z1 - (np.arange(bx.ph) + 0.5) / bx.s
    water, vx = sample_water(run.S(f), run.xs, run.ys, Xp, Zp)
    a = np.empty((bx.ph, bx.pw, 3), np.uint8); a[:] = BG
    a[:, ~vx] = OUTSIDE
    a[water] = WATER
    bed = run.cx.bedf(Xp)
    a[Zp[:, None] < bed[None, :]] = SAND
    im.paste(Image.fromarray(a), (int(bx.px), int(bx.py)))
    y0 = bx.Y(0.0)
    if bx.z0 < 0 < bx.z1:
        for xx in np.arange(bx.px, bx.px + bx.pw, 12):
            dr.line([(xx, y0), (min(xx + 6, bx.px + bx.pw), y0)], fill=(205, 205, 200) if not small else (190, 190, 185), width=1)
    fz = font(12 if small else 14)
    for gx in np.arange(math.ceil(bx.x0 / tick) * tick, bx.x1 + 1e-6, tick):
        u = bx.X(gx)
        dr.line([(u, bx.py + bx.ph), (u, bx.py + bx.ph + 5)], fill=SUB, width=1)
        if tick_lab:
            lab = "%g" % gx
            dr.text((u - dr.textlength(lab, font=fz) / 2, bx.py + bx.ph + 6), lab, fill=SUB, font=fz)
    if bar10 and bx.z1 - bx.z0 >= 10.5:
        zb0 = 0.0 if bx.z0 < 0 and bx.z1 > 10 else bx.z0 + 0.25
        u = bx.px + 12
        dr.line([(u, bx.Y(zb0)), (u, bx.Y(zb0 + 10))], fill=RED, width=4)
        for zz in (zb0, zb0 + 10):
            dr.line([(u - 5, bx.Y(zz)), (u + 5, bx.Y(zz))], fill=RED, width=2)
        label_box(dr, (u + 8, bx.Y(zb0 + 10) - 3), "10 m", RED, font(13 if small else 16, True))
    if bar5:
        u0 = bx.px + 60; v = bx.py + bx.ph - 16
        dr.line([(u0, v), (u0 + 5 * bx.s, v)], fill=RED, width=4)
        for uu in (u0, u0 + 5 * bx.s):
            dr.line([(uu, v - 5), (uu, v + 5)], fill=RED, width=2)
        label_box(dr, (u0 + 5 * bx.s + 8, v - 11), "5 m", RED, font(13 if small else 16, True))
    dr.rectangle([bx.px, bx.py, bx.px + bx.pw, bx.py + bx.ph], outline=(120, 120, 120))


def print_phys(xc, eta):
    """原画の輪郭（縦の伸びを戻した形）を、このコマの η_c と頂の x に合わせた m の座標に。"""
    return [np.stack([xc + q[:, 0] * eta, q[:, 1] * eta], 1) for q in print_ref()["cn"]]


def timebar(dr, x0, x1, y, ta, tb, t, marks, slow_t=None, small=False, unit="s", head=""):
    """時刻の帯。両端に始めと終わりの時刻、下に印（2 段に互い違い）。"""
    fs = font(12 if small else 13)
    la = "%s%.2f %s" % (head, ta, unit); lb = "%.2f %s" % (tb, unit)
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
    for k, (tm, lab, col) in enumerate(sorted(marks)):
        if tm is None or not (ta - 1e-9 <= tm <= tb + 1e-9):
            continue
        u = U(tm)
        dr.line([(u, y - 4), (u, y + 12 + 13 * (k % 2))], fill=col, width=2)
        dr.text((u + 3, y + 10 + 13 * (k % 2)), lab, fill=col, font=fs)


def banner(dr, x, y, state, slow, speed, hold_s, small=False):
    if state == "hold":
        txt, col = "止め：原画に最も近いコマ（%.1f s）" % hold_s, GREEN
    elif state == "hold_end":
        txt, col = "止め：各海底の原画に最も近いコマ", GREEN
    elif state == "slow":
        txt, col = "%.3g 倍のスロー（計算の 1 s を %.3g s で）" % (slow * speed, 1.0 / (slow * speed)), ORANGE
    elif speed != 1.0:
        txt, col = "%.3g 倍の速さ（計算の 1 s を %.3g s で）" % (speed, 1.0 / speed), BLUE
    else:
        txt, col = "実時間（計算の 1 s を 1 s で）", (90, 90, 90)
    fz = font(14 if small else 17, True)
    w = dr.textlength(txt, font=fz)
    dr.rectangle([x, y, x + w + 16, y + (24 if small else 28)], fill=col)
    dr.text((x + 8, y + 3), txt, fill=(255, 255, 255), font=fz)


def fmt(v, f):
    return "-" if v is None else (f % v)


def measure_rows(m):
    pr = print_ref(); b = pr["bands"]; c = pr["cnv"]; ex = pr["extra"]
    rows = [("前の面の弦 0.1〜0.5 η_c", "face_chord_deg_01_05", "%.1f°", "%.1f°（%.1f〜%.1f）" % (c["face_chord_deg_01_05"], *b["face_chord_deg_01_05"]["band"]), b["face_chord_deg_01_05"]["band"]),
            ("唇の下の空気（最大）", "gap_max", "%.3f", "%.3f（%.2f 以上）" % (c["gap_max"], b["gap_max"]["band"][0]), b["gap_max"]["band"]),
            ("唇の厚み（真ん中）", "lip_thick_mid", "%.3f", "%.3f（%.2f〜%.2f）" % (c["lip_thick_mid"], *b["lip_thick_mid"]["band"]), b["lip_thick_mid"]["band"]),
            ("覆いの面積", "hood_area", "%.3f", "%.3f（%.3f〜%.3f）" % (c["hood_area"], *b["hood_area"]["band"]), b["hood_area"]["band"]),
            ("前の足（0.1 η_c、頂から）", "front_x01_rel", "%.3f", "%.3f（%.2f〜%.2f）" % (c["front_x01_rel"], *b["front_x01_rel"]["band"]), b["front_x01_rel"]["band"]),
            ("後ろの角 0.7〜0.9 η_c（参考）", "back_angle_07_09_deg", "%.1f°", "%.1f°（%.0f〜%.0f）" % (c["back_angle_07_09_deg"], *ex["back_angle_07_09_deg"]), ex["back_angle_07_09_deg"]),
            ("0.7 η_c の幅（参考）", "width07_silhouette", "%.2f", "%.2f（%.2f〜%.2f）" % (c["width07_silhouette"], *ex["width07_silhouette"]), ex["width07_silhouette"])]
    out = []
    for lab, k, f, ptxt, band in rows:
        v = (m or {}).get(k)
        if v is None:
            col = SUB
        else:
            lo, hi = band
            col = GREEN if ((lo is None or v >= lo - 1e-9) and (hi is None or v <= hi + 1e-9)) else RED
        out.append((lab, fmt(v, f), ptxt, col))
    return out


# ======================================================================== 1 本の動画
class RunVideo:
    def __init__(self, run, opt):
        self.r = run
        self.opt = opt
        self.k = int(opt.get("k", 1))
        evs = run.events()
        self.ev = None
        if evs:
            if self.k > len(evs):
                raise GA.InputError("崩れは %d 個しかない（--k=%d）。events で表を見る" % (len(evs), self.k))
            self.ev = evs[self.k - 1]
        e = self.ev
        run.make_camera(e)
        self.slow = float(opt.get("slow", 0.25))
        self.speed = float(opt.get("speed", 1.0))
        self.hold_s = float(opt.get("hold", 1.0))
        self.post = float(opt.get("overturn_post", 0.5))
        if e is not None:
            run.prep(e, pre=1.0, post=self.post)
        # 時刻の窓
        t_first, t_last = run.tf[run.frames[0]], run.tf[run.frames[-1]]
        around = str(opt.get("around", "0")) == "1"
        if opt.get("t0") is None and opt.get("t1") is None and e is not None and (around or (t_last - t_first) > 90.0):
            t0 = e["on_t"] - float(opt.get("pre", 8.0)); t1 = e.get("td_t", e["on_t"] + 2.0) + float(opt.get("post", 3.0))
        else:
            t0 = float(opt.get("t0", t_first)); t1 = float(opt.get("t1", t_last))
        self.fr = [f for f in run.frames if t0 - 1e-9 <= run.tf[f] <= t1 + 1e-9]
        if not self.fr:
            raise GA.InputError("時刻の窓 %.2f〜%.2f s にコマがない" % (t0, t1))
        self.ta, self.tb = run.tf[self.fr[0]], run.tf[self.fr[-1]]
        self.slow_t = None
        if e is not None and self.slow > 0 and abs(self.slow - 1.0) > 1e-9:
            self.slow_t = (e["on_t"] - float(opt.get("slow_pre", 1.0)), e.get("td_t", e["on_t"] + 2.0) + float(opt.get("slow_post", 0.5)))
        self.best_f = e.get("best_f") if e else None
        self.ov_t = (e["on_t"], e.get("td_t", e["on_t"] + 2.0) + self.post) if e else None
        self._layout()

    # ---- 並べ方
    def _layout(self):
        r = self.r
        xa, xb = r.x_range()
        Lx = xb - xa
        self.nrow = max(1, int(math.ceil(Lx / 900.0)))
        bed_min = float(np.min(r.cx.bedf(np.linspace(xa, xb, 2000))))
        self.top_z0 = math.floor(bed_min - 0.8)
        self.top_z1 = math.ceil(r.max_eta_all + 2.0)
        s_top = 1840.0 / (Lx / self.nrow)
        y = 140
        self.top_boxes = []
        for i in range(self.nrow):
            bx = Box(40, y, s_top, xa + i * Lx / self.nrow, xa + (i + 1) * Lx / self.nrow, self.top_z0, self.top_z1)
            self.top_boxes.append(bx)
            y += bx.ph + 30
        ybot = y + 6
        self.top_tick = 50.0 if Lx / self.nrow <= 700 else 100.0
        # 拡大の窓
        e = self.ev
        tr = e["track"] if e else r.main_track()
        tw = (e["on_t"] - 1.0, e.get("td_t", e["on_t"] + 2.0) + self.post) if e else (self.ta, self.tb)
        etas = [eta for f, eta in zip(tr["f"], tr["eta"]) if self.ta - 1e-9 <= r.tf[f] <= self.tb + 1e-9] or tr["eta"]
        self.z1 = float(math.ceil(max(etas) + 2.0))
        camx = [r.cam_x(f) for f in r.frames if tw[0] - 1e-9 <= r.tf[f] <= tw[1] + 1e-9] or [r.cam_x(self.fr[0])]
        bz = float(np.min(r.cx.bedf(np.linspace(min(camx) - 30.0, max(camx) + 30.0, 400))))
        self.z0 = float(min(-3.0, max(-9.0, math.floor(bz - 2.0))))
        if self.opt.get("zoom_zlo") is not None:
            self.z0 = float(self.opt["zoom_zlo"])
        self.bottom = H - 64                      # これより下は時刻の帯
        pw_max, ph_max = 1100.0, float(self.bottom - 22 - (ybot + 28))
        zw = self.opt.get("zoom_w", "auto")
        if zw in (None, "auto"):
            self.zoom_w = float(min(80.0, max(40.0, pw_max * (self.z1 - self.z0) / ph_max)))
        else:
            self.zoom_w = float(zw)
        self.zs = min(pw_max / self.zoom_w, ph_max / (self.z1 - self.z0))
        self.zoom_at = float(self.opt.get("zoom_at", 0.45))
        self.zy = ybot + 28
        self.ovx, self.ovy = 1180, ybot + 28
        self.XL, self.XR, self.ZB, self.ZT = -2.0, 1.4, -0.3, 1.15
        table_h = 26 + 24 + 7 * 22 + 50
        self.os_ = min(700.0 / (self.XR - self.XL), (self.bottom - self.ovy - table_h - 4) / (self.ZT - self.ZB))

    def header(self, dr, f):
        r = self.r; e = self.ev
        coarse = "（粗い）" if r.dp > 0.25 + 1e-9 else ""
        text_fit(dr, (40, 8), r.title_text() + ("　" + self.opt["label"] if self.opt.get("label") else ""), 1440, 22, True)
        text_fit(dr, (40, 38), bed_text(r.bed), 1440, 16)
        text_fit(dr, (40, 62), "%s。粒子 %.4g m（格子 %.4g m）%s。重力だけ・水だけ。%s" % (wave_text(r.cfg, r.h0), r.dp, r.vox, coarse, r.layer_text()), 1440, 16)
        xr = "x は論文の座標（m）" if abs(r.cx.xref) < 1e-9 else "x は基準 %.2f m から（m）" % r.cx.xref
        text_fit(dr, (40, 86), "縦横同じ縮尺。高さは静かな水面から（点線、ずれ %.3f m を引いた）。%s。青＝水、砂色＝海底（すぐ上の格子の半分は解析と同じく水に塗る）、"
                 "薄い灰＝記録の外。数は【測った】" % (r.cx.off, xr), 1440, 14, fill=SUB)
        t = r.tf[f]
        dr.text((1510, 6), "t = %.2f s" % t, fill=TXT, font=font(30, True))
        if e:
            s = "巻き始めから %+.2f s" % (t - e["on_t"])
            if e.get("td_t") is not None:
                s += "・着水から %+.2f s" % (t - e["td_t"])
            text_fit(dr, (1510, 46), s + "（コマ %d）" % f, 400, 15)
        else:
            dr.text((1510, 46), "崩れは見つからない（コマ %d）" % f, fill=SUB, font=font(15))

    def draw_top(self, im, dr, f):
        r = self.r
        zx0 = r.cam_x(f) - r.zoom_at(f, self.zoom_at) * self.zoom_w
        dr.text((40, self.top_boxes[0].py - 24), "領域の全部（x %.0f〜%.0f m、縦横同じ縮尺。赤の枠＝左下の拡大の窓）" % r.x_range(), fill=TXT, font=font(17, True))
        zones = r.zones()
        for bx in self.top_boxes:
            draw_field(im, dr, r, f, bx, tick=self.top_tick)
            for za, zb, lab, col in zones:
                a, b = max(za, bx.x0), min(zb, bx.x1)
                if a < b:
                    u0, u1, v0, v1 = bx.X(a), bx.X(b), bx.py, bx.py + bx.ph
                    for q in np.arange(u0 - (v1 - v0), u1, 14):          # 斜めの細い線（水の色は消さない）
                        p0 = (max(q, u0), v1 - (max(q, u0) - q)); p1 = (min(q + (v1 - v0), u1), v1 - (min(q + (v1 - v0), u1) - q))
                        dr.line([p0, p1], fill=col, width=1)
                    dr.line([(u0, v0 + 2), (u1, v0 + 2)], fill=col, width=5)
                    dr.line([(u0, v1 - 2), (u1, v1 - 2)], fill=col, width=5)
                    label_box(dr, (u0 + 4, v1 - 22), lab, col, font(13, True))
            a, b = max(zx0, bx.x0), min(zx0 + self.zoom_w, bx.x1)
            if a < b:
                dr.rectangle([bx.X(a), bx.Y(self.z1), bx.X(b), bx.Y(self.z0)], outline=RED, width=2)

    def draw_zoom(self, im, dr, f):
        r = self.r; e = self.ev
        zx0 = r.cam_x(f) - r.zoom_at(f, self.zoom_at) * self.zoom_w
        bx = Box(40, self.zy, self.zs, zx0, zx0 + self.zoom_w, self.z0, self.z1)
        dr.text((40, self.zy - 26), "拡大：崩れる頂を追う窓（幅 %.0f m、縦横同じ縮尺、%s）" % (self.zoom_w, "k = %d 番目の崩れ" % self.k if e else "いちばん高い山"),
                fill=TXT, font=font(17, True))
        draw_field(im, dr, r, f, bx, tick=10.0, bar5=True)
        m = r.meas.get(f)
        t = r.tf[f]
        if e and m and m.get("eta_c") and e["on_t"] - 1e-9 <= t <= e.get("td_t", e["on_t"] + 2.0) + 1e-9:
            best = (f == self.best_f)
            for q in print_phys(m["x_c"], m["eta_c"]):
                for P in bx.clip(q):
                    poly(dr, P, (0, 0, 0), 4 if best else 2, dash=not best)
            u, v = bx.X(m["x_c"]), bx.Y(m["eta_c"])
            dr.polygon([(u, v - 6), (u + 6, v), (u, v + 6), (u - 6, v)], fill=YEL, outline=(120, 100, 0))
            lab = "黒＝原画の輪郭（縦の伸びを戻した形）を、このコマの η_c %.2f m と頂の x に合わせて重ねた%s" % (m["eta_c"], "（原画に最も近いコマ）" if best else "")
            text_fit(dr, (bx.px + 8, bx.py + 6), lab, bx.pw - 16, 14, best, fill=(0, 0, 0) if not best else GREEN)
        return bx

    def draw_overlay(self, im, dr, f):
        r = self.r; e = self.ev
        x0, y0 = self.ovx, self.ovy
        s = self.os_
        pw = int((self.XR - self.XL) * s); ph = int((self.ZT - self.ZB) * s)
        dr.text((x0, y0 - 26), "同じ物差しの重ね（η_c で割り、頂の位置をそろえた。巻いている間だけ）", fill=TXT, font=font(17, True))
        dr.rectangle([x0, y0, x0 + pw, y0 + ph], fill=(255, 255, 255), outline=(150, 150, 150))
        tr = lambda P: np.stack([x0 + (P[:, 0] - self.XL) * s, y0 + (self.ZT - P[:, 1]) * s], 1)
        t = r.tf[f]
        on = bool(self.ov_t and self.ov_t[0] - 1e-9 <= t <= self.ov_t[1] + 1e-9)
        m = r.meas.get(f) if on else None
        if not on or not m or not m.get("lines"):
            msg = "巻いていない時は描かない（巻き始め〜着水の %.1f s 後だけ）" % self.post if e else "崩れが見つからないので描かない"
            dr.text((x0 + pw / 2 - dr.textlength(msg, font=font(16)) / 2, y0 + ph / 2 - 10), msg, fill=SUB, font=font(16))
        else:
            for zv in (-0.25, 0.0, 0.25, 0.5, 0.7, 1.0):
                yy = y0 + (self.ZT - zv) * s
                dr.line([(x0, yy), (x0 + pw, yy)], fill=(110, 110, 110) if zv == 0 else (228, 228, 228), width=2 if zv == 0 else 1)
                dr.text((x0 - 34, yy - 8), "%g" % zv, fill=SUB, font=font(12))
            for xv in np.arange(-2.0, self.XR + 1e-6, 0.5):
                xx = x0 + (xv - self.XL) * s
                dr.line([(xx, y0 + ph), (xx, y0 + ph - 6)], fill=(120, 120, 120))
                dr.text((xx - 8, y0 + ph + 3), "%g" % xv, fill=SUB, font=font(12))
            box = (self.XL, self.XR, self.ZB, self.ZT)
            pr = print_ref()
            for q in pr["drawn"]:
                for P in split_inside(q, *box):
                    poly(dr, tr(P), GREY, 2, dash=True)
            for q in pr["cn"]:
                for P in split_inside(q, *box):
                    poly(dr, tr(P), (0, 0, 0), 4)
            bf = self.best_f
            if bf is not None and f >= bf and f != bf and r.meas.get(bf, {}).get("lines"):
                for q in r.meas[bf]["lines"]:
                    for P in split_inside(q, *box):
                        poly(dr, tr(P), GREEN, 2)
            for q in m["lines"]:
                for P in split_inside(q, *box):
                    poly(dr, tr(P), GREEN if f == bf else BLUE, 3)
        # 凡例
        yl = y0 + ph + 20
        items = [("原画（伸びを戻した形）", (0, 0, 0), False), ("原画（描かれたまま）", GREY, True), ("このコマ", BLUE, False)]
        if self.best_f is not None:
            items.append(("原画に最も近いコマ %d" % self.best_f, GREEN, False))
        xx = x0
        for lab, col, dsh in items:
            if dsh:
                dashed(dr, [(xx, yl + 8), (xx + 26, yl + 8)], col, 3)
            else:
                dr.line([(xx, yl + 8), (xx + 26, yl + 8)], fill=col, width=4)
            dr.text((xx + 31, yl), lab, fill=TXT, font=font(13))
            xx += 31 + dr.textlength(lab, font=font(13)) + 16
        # 数の表
        yt = yl + 26
        mm = r.meas.get(f) if (e and e["on_t"] - 1.0 - 1e-9 <= t <= e.get("td_t", e["on_t"] + 2.0) + self.post + 1e-9) else None
        dr.text((x0, yt), "同じ物差しの量（η_c で割った値）", fill=TXT, font=font(15, True))
        dr.text((x0 + 330, yt), "このコマ", fill=TXT, font=font(15, True))
        dr.text((x0 + 440, yt), "原画 cn（4 つの読みの帯）", fill=TXT, font=font(15, True))
        yt += 24
        if mm is None or mm.get("m") is None:
            msg = ("測るのは巻き始めの 1 s 前〜着水の %.1f s 後だけ" % self.post) if e else "崩れが見つからない"
            if mm is not None and mm.get("m") is None:
                msg = "このコマは測れなかった（%s）" % str(mm.get("err") or "")[:60]
            dr.text((x0, yt), msg, fill=SUB, font=font(14))
            for lab, val, ptxt, col in measure_rows(None):
                yt += 22
                dr.text((x0, yt), lab, fill=SUB, font=font(14)); dr.text((x0 + 440, yt), ptxt, fill=SUB, font=font(14))
        else:
            for lab, val, ptxt, col in measure_rows(mm["m"]):
                dr.text((x0, yt), lab, fill=TXT, font=font(14))
                dr.text((x0 + 330, yt), val, fill=col, font=font(15, True))
                dr.text((x0 + 440, yt), ptxt, fill=SUB, font=font(14))
                yt += 22
            src = "ana47 と同じ関数" if (e and e.get("ana")) else "この道具"
            s3 = mm.get("score3")
            dr.text((x0, yt + 2), "η_c %.2f m、頂 x %.1f m。score3 %s（弦・足・覆いの帯の外れ、0 が帯の中）" % (mm["eta_c"], mm["x_c"], fmt(s3, "%.2f")), fill=TXT, font=font(14))
            text_fit(dr, (x0, yt + 24), "出どころ：%s（g47_analyze.fine_mask → STUDY52 measure_mask、0.05 m の水の格子）。緑＝帯の中、赤＝外" % src, 700, 13, fill=SUB)

    def render(self, f, state):
        im = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(im)
        self.header(dr, f)
        banner(dr, 1510, 70, state, self.slow, self.speed, self.hold_s)
        self.draw_top(im, dr, f)
        self.draw_zoom(im, dr, f)
        self.draw_overlay(im, dr, f)
        e = self.ev
        marks = []
        if e:
            marks.append((e["on_t"], "巻き始め", RED))
            if e.get("td_t") is not None:
                marks.append((e["td_t"], "着水", PURP))
            if self.best_f is not None:
                marks.append((self.r.tf[self.best_f], "原画に最も近い", GREEN))
        timebar(dr, 40, W - 40, H - 44, self.ta, self.tb, self.r.tf[f], marks, self.slow_t, head="t ")
        return im

    def schedule(self):
        out, acc, emitted = [], 0.0, 0
        for f in self.fr:
            t = self.r.tf[f]
            sl = bool(self.slow_t and self.slow_t[0] - 1e-9 <= t <= self.slow_t[1] + 1e-9)
            sp = self.speed * (self.slow if sl else 1.0)
            acc += 1.0 / sp
            n = int(math.floor(acc + 1e-9)) - emitted
            emitted += n
            if n > 0:
                out.append((f, n, "slow" if sl else "real"))
            if f == self.best_f and self.hold_s > 0:
                out.append((f, int(round(self.hold_s * FPS)), "hold"))
        return out


# ======================================================================== 書き出しと確かめ
class Writer:
    def __init__(self, path):
        self.path = path
        self.p = subprocess.Popen([FF, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
                                   "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", path],
                                  stdin=subprocess.PIPE)
        self.n = 0

    def put(self, im, n=1):
        b = im.tobytes()
        for _ in range(n):
            self.p.stdin.write(b)
        self.n += n

    def close(self):
        self.p.stdin.close()
        rc = self.p.wait()
        if rc != 0:
            raise RuntimeError("ffmpeg の終わりの値 %d：%s" % (rc, self.path))


def probe(path):
    r = subprocess.run([FP, "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                        "stream=codec_name,width,height,r_frame_rate,nb_read_frames,pix_fmt:format=duration,size", "-of", "json", path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return dict(ok=False, err=r.stderr[:300])
    d = json.loads(r.stdout)
    st = (d.get("streams") or [{}])[0]; fm = d.get("format") or {}
    return dict(ok=True, codec=st.get("codec_name"), width=st.get("width"), height=st.get("height"), fps=st.get("r_frame_rate"),
                pix_fmt=st.get("pix_fmt"), frames=int(st.get("nb_read_frames") or 0), duration_s=float(fm.get("duration") or 0.0),
                size_mb=round(int(fm.get("size") or 0) / 1e6, 2))


def make_run_video(ref, opt, log=print):
    GCM.unthrottle_self()
    out = guard_out(opt.get("out") or VID)
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    run = Run(ref, opt.get("layer", "sdf"), log=log)
    rv = RunVideo(run, opt)
    e = rv.ev
    name = opt.get("name") or ("%s%s%s_side" % (run.rid, "" if run.layer == "sdf" else "_z%s" % run.layer, "" if rv.k == 1 else "_k%d" % rv.k))
    if opt.get("still") is not None:
        f = int(opt["still"])
        p = os.path.join(out, "%s_f%04d.png" % (name, f))
        rv.render(f, "real").save(p)
        log("wrote", p)
        return p
    sch = rv.schedule()
    path = os.path.join(out, name + ".mp4")
    wr = Writer(path)
    for f, n, st in sch:
        wr.put(rv.render(f, st), n)
    wr.close()
    pb = probe(path)
    info = dict(video=path, made=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip47/g47_video.py run", opt=opt,
                run=run.rid, rd=run.rd, layer=run.layer, layer_z=run.layer_z, still_offset_m=run.cx.off, still_offset_src=run.cx.off_src,
                bed_src=run.cx.bed_src, ana47=run.ana_path, scan_summary=run.scan_sum,
                events=[dict(k=v["k"], onset_frame=v["on_f"], onset_t=v["on_t"], own_onset_frame=v["own_on_f"], onset_x=v["on_x"], onset_src=v["on_src"],
                             touchdown_frame=v.get("td_f"), touchdown_t=v.get("td_t"), touchdown_src=v.get("td_src"), own_touchdown_frame=v.get("own_td_f"),
                             ana_match=v["ana"]) for v in run.evs],
                after_breaking_not_counted=[dict(first_overhang_frame=v["first_f"], first_overhang_t=v["first_t"], first_overhang_x=v["first_x"],
                                                 first_overhang_eta=v["first_eta"], track_start_t=v["track"]["t"][0],
                                                 track_start_x=v["track"]["x"][0]) for v in run.after_evs],
                k=rv.k, best_frame=(e or {}).get("best_f"), best_src=(e or {}).get("best_src"), best_live_frame=(e or {}).get("best_live_f"),
                window_s=[rv.ta, rv.tb], data_frames=[rv.fr[0], rv.fr[-1], len(rv.fr)], slow=rv.slow, slow_t=rv.slow_t, speed=rv.speed,
                hold_s=rv.hold_s, zoom=dict(w_m=rv.zoom_w, z0=rv.z0, z1=rv.z1, px_per_m=rv.zs), top=dict(rows=rv.nrow, z0=rv.top_z0, z1=rv.top_z1),
                out_frames_written=wr.n, expected_duration_s=wr.n / FPS, ffprobe=pb, checks=run.checks, elapsed_s=round(time.time() - t0, 1),
                ok=bool(pb.get("ok") and pb.get("frames") == wr.n and abs(pb.get("duration_s", 0) - wr.n / FPS) < 0.1))
    jdump(info, os.path.join(out, name + ".json"))
    log("wrote %s  コマ %d（ffprobe %s）、%.1f s、作るのに %.0f s、ok %s" % (path, wr.n, pb.get("frames"), pb.get("duration_s", 0), time.time() - t0, info["ok"]))
    return info


# ======================================================================== 並べた動画（2×3）
class Montage:
    CW, CH = 620, 462
    Y0, GAP = 78, 8

    def __init__(self, refs, opt, log=print):
        self.opt = opt
        self.runs = []
        for ref in refs[:6]:
            k = 1
            if "@" in ref:                                   # <計算>@<k>：同じ計算の k 番目の崩れ（周期の波の回を並べる時）
                ref, kk = ref.rsplit("@", 1)
                k = int(kk)
            r = Run(ref, opt.get("layer", "sdf"), log=log)
            evs = r.events()
            if len(evs) < k:
                raise GA.InputError("崩れが %d 個しかない（%s@%d）" % (len(evs), r.rid, k))
            e = evs[k - 1]
            if k != 1 or any(("@" in q) for q in refs):
                r.label = "%s・k %d" % (r.label, k)
            if e.get("td_t") is None:
                raise GA.InputError("着水が見つからない：%s" % r.rid)
            r.make_camera(e)
            r.prep(e, pre=1.0, post=0.5)
            r.ev = e
            self.runs.append(r)
        self.slow = float(opt.get("slow", 0.25))
        self.hold_end = float(opt.get("hold_end", 3.0))
        self.tau0 = float(opt.get("tau0", -5.0))
        tmax = min(r.tf[r.frames[-1]] - r.ev["td_t"] for r in self.runs)
        tmin = max(r.tf[r.frames[0]] - r.ev["td_t"] for r in self.runs)
        self.tau0 = max(self.tau0, tmin)
        self.tau1 = float(opt.get("tau1", tmax))
        if opt.get("slow_tau"):
            a, b = [float(v) for v in str(opt["slow_tau"]).split(",")]
        else:
            a = math.floor((min(r.ev["on_t"] - r.ev["td_t"] for r in self.runs) - 0.6) * 10) / 10.0; b = 1.0
        self.slow_tau = (a, b)
        self.ks = list(range(int(round(self.tau0 * FPS)), int(round(self.tau1 * FPS)) + 1))
        # 共通の拡大の高さ・幅（全部の枠で同じ倍率）
        self.z1 = float(math.ceil(max(max(eta for f, eta in zip(r.ev["track"]["f"], r.ev["track"]["eta"])) for r in self.runs) + 2.0))
        zb = []
        for r in self.runs:
            cx_ = [r.cam_x(f) for f in r.frames if r.ev["on_t"] - 1.0 <= r.tf[f] <= r.ev["td_t"] + 0.5]
            zb.append(float(np.min(r.cx.bedf(np.linspace(min(cx_) - 30, max(cx_) + 30, 300)))))
        self.z0 = float(min(-3.0, max(-9.0, math.floor(min(zb) - 2.0))))
        top_need = max(self._strip_h(r) for r in self.runs)
        self.top_need = int(math.ceil(top_need))
        self.zoom_avail = self.CH - 30 - self.top_need - 22 - 58
        self.zs = self.zoom_avail / (self.z1 - self.z0)
        self.zoom_w = (self.CW - 16) / self.zs
        self.zoom_at = 0.45

    def _strip_h(self, r):
        xa, xb = r.x_range()
        s = (self.CW - 16) / (xb - xa)
        z0 = math.floor(float(np.min(r.cx.bedf(np.linspace(xa, xb, 500)))) - 0.8); z1 = math.ceil(r.max_eta_all + 2.0)
        return (z1 - z0) * s

    def cell(self, im, dr, r, f, px, py, summary=False):
        e = r.ev
        CW, CH = self.CW, self.CH
        best = (f == e.get("best_f"))
        dr.rectangle([px, py, px + CW, py + CH], outline=GREEN if best else (170, 170, 165), width=4 if best else 1)
        text_fit(dr, (px + 8, py + 4), r.label, CW - 200, 17, True)
        t = r.tf[f]
        s = "t %.2f s・τ %+.2f s" % (t, t - e["td_t"])
        dr.text((px + CW - 8 - dr.textlength(s, font=font(14)), py + 7), s, fill=TXT, font=font(14))
        xa, xb = r.x_range()
        ss = (CW - 16) / (xb - xa)
        z0 = math.floor(float(np.min(r.cx.bedf(np.linspace(xa, xb, 500)))) - 0.8); z1 = math.ceil(r.max_eta_all + 2.0)
        sb = Box(px + 8, py + 30, ss, xa, xb, z0, z1)
        draw_field(im, dr, r, f, sb, tick=100.0, tick_lab=True, bar10=False, small=True)
        zx0 = r.cam_x(f) - r.zoom_at(f, self.zoom_at) * self.zoom_w
        a_, b_ = max(zx0, xa), min(zx0 + self.zoom_w, xb)
        if a_ < b_:
            dr.rectangle([sb.X(a_), sb.Y(self.z1), sb.X(b_), sb.Y(self.z0)], outline=RED, width=1)
        bx = Box(px + 8, py + 30 + self.top_need + 22, self.zs, zx0, zx0 + self.zoom_w, self.z0, self.z1)
        draw_field(im, dr, r, f, bx, tick=10.0, bar5=True, small=True)
        m = r.meas.get(f)
        if m and m.get("eta_c") and e["on_t"] - 1e-9 <= t <= e["td_t"] + 1e-9:
            for q in print_phys(m["x_c"], m["eta_c"]):
                for P in bx.clip(q):
                    poly(dr, P, (0, 0, 0), 3 if best else 1, dash=not best)
        if best:
            dr.text((bx.px + 60, bx.py + 4), "原画に最も近いコマ（黒＝原画の輪郭）", fill=GREEN, font=font(14, True))
        yt = bx.py + bx.ph + 20
        mm = m.get("m") if (m and e["on_t"] - 1.0 - 1e-9 <= t <= e["td_t"] + 0.5 + 1e-9) else None
        if mm:
            s = "弦 %s・空気 %s・唇 %s・覆い %s・足 %s・score3 %s（η_c %.1f m）" % (
                fmt(mm.get("face_chord_deg_01_05"), "%.0f°"), fmt(mm.get("gap_max"), "%.2f"), fmt(mm.get("lip_thick_mid"), "%.2f"),
                fmt(mm.get("hood_area"), "%.3f"), fmt(mm.get("front_x01_rel"), "%.2f"), fmt(m.get("score3"), "%.2f"), m["eta_c"])
        else:
            tr = e["track"]; xt = dict(zip(tr["f"], zip(tr["x"], tr["eta"])))
            s = ("頂 %.1f m（x %.0f m）" % (xt[f][1], xt[f][0])) if f in xt else ""
        text_fit(dr, (px + 8, yt), s, CW - 16, 14, fill=TXT)
        text_fit(dr, (px + 8, yt + 19), "巻き始めから %+.2f s・コマ %d・拡大の窓 x %.0f〜%.0f m%s" % (
            t - e["on_t"], f, zx0, zx0 + self.zoom_w, "・原画に最も近いコマ %s" % e.get("best_f")), CW - 16, 12, fill=SUB)

    def header(self, dr, tau, state):
        r0 = self.runs[0]
        waves = {}
        for r in self.runs:
            waves.setdefault(wave_text(r.cfg, r.h0).split("、頂の始め")[0], []).append(r.label.split()[0])
        if len(waves) == 1:
            wt = list(waves)[0]
        else:
            main = max(waves, key=lambda k: len(waves[k]))
            wt = main + "（" + "；".join("%s は %s" % ("・".join(v), k.replace("波：", "")) for k, v in waves.items() if k != main) + "）"
        dps = sorted(set(r.dp for r in self.runs))
        text_fit(dr, (20, 4), "FLIP47 %s：各計算の着水の時刻にそろえた（τ = t − t着水）。粒子 %s m（格子 %s m）、重力だけ・水だけ、2D の板の%s" % (
            self.opt.get("title") or ("%d 本を並べた" % len(self.runs)), "・".join("%g" % d for d in dps), "・".join("%g" % (2 * d) for d in dps), r0.layer_text().replace("（主の読み、ana47 と同じ）", "")), 1460, 19, True)
        text_fit(dr, (20, 31), wt + "。縦横同じ縮尺、%d つの拡大は同じ倍率で頂を追う。" % len(self.runs) + "各枠の上の帯＝領域の全部（赤の枠＝拡大の窓）。砂色＝海底", 1460, 14, fill=SUB)
        pc = print_ref()["cnv"]
        text_fit(dr, (20, 52), "細い黒の破線＝原画の輪郭（縦の伸びを戻した形）をそのコマの η_c と頂の位置で重ねた物（巻き始め〜着水）。緑の枠と太い黒＝原画に最も近いコマ（score3 の最小）。"
                 "原画 cn：弦 %.0f°・空気 %.2f・唇 %.2f・覆い %.3f・足 %.2f" % (pc["face_chord_deg_01_05"], pc["gap_max"], pc["lip_thick_mid"], pc["hood_area"], pc["front_x01_rel"]),
                 1460, 14, fill=SUB)
        if state == "hold_end":
            dr.text((1500, 4), "τ = 各計算の最も近いコマ", fill=TXT, font=font(20, True))
        else:
            dr.text((1500, 2), "τ = %+.2f s" % tau, fill=TXT, font=font(28, True))
        banner(dr, 1500, 42, state, self.slow, 1.0, self.hold_end, small=True)

    def render(self, k, state):
        im = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(im)
        tau = k / FPS
        self.header(dr, tau, state)
        for i, r in enumerate(self.runs):
            c, rr = i % 3, i // 3
            px, py = 20 + c * (self.CW + 20), self.Y0 + rr * (self.CH + self.GAP)
            if state == "hold_end":
                f = r.ev.get("best_f") or r.ev["td_f"]
            else:
                f = r.ev["td_f"] + k
                if f not in r.tf:
                    f = min(r.frames, key=lambda q: abs(q - (r.ev["td_f"] + k)))
            self.cell(im, dr, r, f, px, py)
        marks = [(0.0, "着水", PURP)]
        on = [r.ev["on_t"] - r.ev["td_t"] for r in self.runs]
        marks.append((min(on), "巻き始め %+.2f〜%+.2f s" % (min(on), max(on)), RED)); marks.append((max(on), "", RED))
        timebar(dr, 40, W - 40, H - 46, self.tau0, self.tau1, tau if state != "hold_end" else self.tau1, marks, self.slow_tau, small=True, head="τ ")
        return im

    def schedule(self):
        out, acc, emitted = [], 0.0, 0
        for k in self.ks:
            tau = k / FPS
            sl = self.slow_tau[0] - 1e-9 <= tau <= self.slow_tau[1] + 1e-9 and abs(self.slow - 1.0) > 1e-9 and self.slow > 0
            acc += 1.0 / (self.slow if sl else 1.0)
            n = int(math.floor(acc + 1e-9)) - emitted
            emitted += n
            if n > 0:
                out.append((k, n, "slow" if sl else "real"))
        if self.hold_end > 0:
            out.append((None, int(round(self.hold_end * FPS)), "hold_end"))
        return out


def make_montage(refs, opt, log=print):
    GCM.unthrottle_self()
    out = guard_out(opt.get("out") or VID)
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    mt = Montage(refs, opt, log=log)
    name = opt.get("name") or "MONTAGE_%s" % "_".join(r.rid.split("_")[0] for r in mt.runs)
    if opt.get("still") is not None:
        st = str(opt["still"])
        p = os.path.join(out, "%s_still_%s.png" % (name, st))
        (mt.render(0, "hold_end") if st == "end" else mt.render(int(round(float(st) * FPS)), "real")).save(p)
        log("wrote", p)
        return p
    path = os.path.join(out, name + ".mp4")
    wr = Writer(path)
    for k, n, st in mt.schedule():
        wr.put(mt.render(k if k is not None else 0, st), n)
    wr.close()
    pb = probe(path)
    info = dict(video=path, made=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip47/g47_video.py montage", opt=opt,
                runs=[dict(run=r.rid, label=r.label, onset_frame=r.ev["on_f"], onset_t=r.ev["on_t"], touchdown_frame=r.ev["td_f"], touchdown_t=r.ev["td_t"],
                           touchdown_src=r.ev.get("td_src"), best_frame=r.ev.get("best_f"), best_src=r.ev.get("best_src"), best_live_frame=r.ev.get("best_live_f"),
                           ana_match=r.ev["ana"], checks=r.checks) for r in mt.runs],
                tau=[mt.tau0, mt.tau1], slow=mt.slow, slow_tau=mt.slow_tau, hold_end_s=mt.hold_end,
                zoom=dict(w_m=mt.zoom_w, z0=mt.z0, z1=mt.z1, px_per_m=mt.zs), out_frames_written=wr.n, expected_duration_s=wr.n / FPS,
                ffprobe=pb, elapsed_s=round(time.time() - t0, 1),
                ok=bool(pb.get("ok") and pb.get("frames") == wr.n and abs(pb.get("duration_s", 0) - wr.n / FPS) < 0.1))
    jdump(info, os.path.join(out, name + ".json"))
    log("wrote %s  コマ %d（ffprobe %s）、%.1f s、作るのに %.0f s、ok %s" % (path, wr.n, pb.get("frames"), pb.get("duration_s", 0), time.time() - t0, info["ok"]))
    return info


# ======================================================================== 起動
SCANSET = ["E1a_short_dp0p25", "S2_s1-10_dp0p25", "S3_s1-14.4_dp0p25", "S4_s1-20_dp0p25", "S5_ledge1-7_dp0p25", "S6_twostep_dp0p25"]


def parse(argv):
    opt, pos = {}, []
    for a in argv:
        if a.startswith("--"):
            k, _, v = a[2:].partition("=")
            opt[k] = v if v != "" else "1"
        else:
            pos.append(a)
    return opt, pos


def main(argv):
    opt, pos = parse(argv)
    if not pos:
        print(__doc__)
        return 2
    cmd, rest = pos[0], pos[1:]
    if cmd == "run":
        for ref in rest:
            make_run_video(ref, dict(opt))
        return 0
    if cmd == "montage":
        make_montage(rest or SCANSET, dict(opt))
        return 0
    if cmd == "events":
        for ref in rest:
            r = Run(ref, opt.get("layer", "sdf"))
            evs = r.events(min_eta=float(opt.get("min_eta", 1.0)), min_age=float(opt.get("min_age", 1.0)))
            print("%s：崩れ %d 個（山の筋 %d 本）。ana47 の巻き始め %s" % (r.rid, len(evs), len(r.tracks), ((r.ana or {}).get("onset") or {}).get("frame")))
            for e in evs:
                print("  k %d  巻き始め コマ %d（この道具 %d）t %.2f s x %.1f m 頂 %.2f m [%s]  着水 %s（この道具の粗い読み %s）%s" % (
                    e["k"], e["on_f"], e["own_on_f"], e["on_t"], e["on_x"], e["on_eta"], e["on_src"][:12], e.get("td_f"), e.get("own_td_f"),
                    (e.get("td_src") or "")[:14]))
            for e in r.after_evs:
                print("  （数えない：前の崩れの後に生まれた山の巻き）前の面が初めて 90° 以上 コマ %d t %.2f s x %.1f m 頂 %.2f m、山の筋の始め t %.2f s x %.1f m" % (
                    e["first_f"], e["first_t"], e["first_x"], e["first_eta"], e["track"]["t"][0], e["track"]["x"][0]))
        return 0
    if cmd == "probe":
        for p in rest:
            print(p, json.dumps(probe(p), ensure_ascii=False))
        return 0
    if cmd == "scanset":
        res = []
        for ref in SCANSET + ["E1a_full_dp0p25"]:
            res.append(make_run_video(ref, dict(opt)))
        res.append(make_montage(SCANSET, dict(opt, name="MONTAGE_S1-S6_touchdown_sync", title="海底の組 S1〜S6 を並べた")))
        jdump(dict(made=time.strftime("%Y-%m-%d %H:%M:%S"), videos=[dict(video=i["video"], ok=i["ok"], ffprobe=i["ffprobe"]) for i in res]),
              os.path.join(VID, "scanset_index.json"))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except GA.InputError as e:
        print("InputError:", e)
        sys.exit(3)
