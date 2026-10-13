# -*- coding: utf-8 -*-
"""FLIP46：尾根の上の孤立波（Guyenne & Grilli 2006、以下 GG06）の計算の記録を読む（py -3.10 -B、numpy・scipy・scikit-image・PIL）。
2026-10-12 解析と図の道具の役が新しく書いた。FLIP45 の道具（Tools/GWWaveGen/flip45、変えていない）を読み込んで使う：
  g45_analyze.Reader（記録 hf・r2・r3・r4 をコマで読む）、g45_crest3d.frame_crests・track_crests・plunge_rule（頂・前の面の弦・唇の先・空気の穴）、
  Unity/Build/FLIP45/diag/shape/d_shape_measure.py の keep_bottom・pick・KEYS と、STUDY52 の s52_shape.measure_mask（原画と同じ物差し）。
記録の形は FLIP45 と同じ（g45_run.py の頭書き）：hf_*（一番上の水面 η_top[横, x]）、r2_*（y = 0 の断面の水面の場 sdf[縦, x]、u・w）、
r3_*（横 r3_z の断面）、r4_*（3D の狭い帯の水面の場 sdf[横, 縦, x]）、surf/s_*.gw45s（面）、run_c*.json、r6_*。座標は計画の座標
（x 前、横 y、上 z。静かな水面 0。Houdini の中は上が y・横が z）。

FLIP45 と変えた所：
  - 海底：x' < 5.225 は水深 h0 の平ら、x' ≥ 5.225 は h' = 1 − (x' − 5.225) sech²(k y') / 15（x' = x/h0、y' = y/h0、主の k 0.25）。
    断面の中の海底より下（＋余白）の格子は水として扱う（FLIP44 の g44_analyze.frame_crests と同じ。海底の中の水面の場は正なので、
    そのままでは海底に沿う 0 の線が水面の線と同じ長さになり、前の面を読み違える）。余白は 1 コマ目の近くの静かな所で、海底のすぐ上の
    格子が水になる最小の値を選ぶ（0・0.5・1・1.5 格子。FLIP44 の H4：海底に接した空気の隙間を空気の穴と数えた、の対策）。
    空気の穴（閉じた空気の線）は、海底から格子 2 個より上の物だけ数える。
  - 静かな水面のずれ：孤立波は 1 コマ目から水槽の中にあるので、FLIP45 の「全体の中央値」ではなく、t0 + 0.5〜2.0 s に波の前の裾が
    5 mm より低い所（x ≥ 頂 + acosh(√(H0/0.005))/κ、κ = √(3H0/(4h0³(1+H0/h0)))。GN の減り方で、Tanaka の厳密な解より遅く減るので
    安全側）の η_top の中央値。記録の still_offset_online は並べて書く。
  - 頂の窓の長さ Lc（前の面・谷・空気の穴を探す長さ。FLIP45 は線形の波長 72 m）：60 m（孤立波 H0/h0 0.6 の裾の長さ 1/κ 32 m の約 2 倍）。

読む物（この仕事の指示の 1）：
  (a) 真ん中（y = 0 の断面、r2）の崩れる点：頂の前の面に縦の接線ができた最初のコマ（前の面の弦の最大の傾き thmax ≥ 90°）。
      t・x・頂の高さ zB（静かな水面から）・頂の下の静かな水深 hB（尾根の式）・zB/hB。GG06 表 1（k 0.25：t' 7.890・x' 16.09・zB 0.706・
      hB 0.275・zB/hB 2.57）と ±5% で比べ、2D の値（0.680・0.298・2.28）も並べる。時刻は t' = (t − t_off)/√(h0/g)（コマ 1 が t' 0）。
  (b) 短い頂：巻き始め・GG06 図 9 の時刻 t' 9.142（と、巻き始めから同じ遅れのコマ）・着水で、前の面が巻いた横の範囲。r4（あれば）・
      面の記録を横に切った断面（あれば）・r3・hf（一番上の水面の険しさ。巻きは読めないので目安）。y = 68 m（y' 4）がまだ一価か。
  (c) 着水：唇の先が前の面に届く（閉じた空気の穴、または唇の先が静かな水面以下で覆いかぶさりが格子 2 個以上。g45_crest3d.plunge_rule）。
  (d) 形：原画と同じ物差し（STUDY52 measure_mask）で、巻き始めと最も巻いたコマ（巻き始め〜着水で覆いの高さが最大）。原画の値は
      STUDY52/shape_measures.json の print（cn：縦の伸びを戻した読み、drawn：描かれたまま）。
出力：<出力の置き場所>/ana.json と RESULT_ja.md。出力の置き場所は既定で、記録が Unity/Build/FLIP46 の中なら記録の置き場所、外（FLIP45 V1 の
  試しなど）なら Unity/Build/FLIP46/smoke/test_<名前>/。FLIP46 の外には書かない。
尾根の値は cfg の parms の ridge_k・ridge_x0（m）・ridge_s（g46_cfg.py の名前）から読む（ridge_on 0 なら平ら）。なければ GG06 の既定。
使い方：py -3.10 -B g46_analyze.py <記録の置き場所> [--out=<置き場所>] [--t0=<s>] [--t1=<s>] [--bed=ridge|flat] [--h0=17] [--k=0.25]
        [--xs=5.225] [--n=15] [--Lc=60] [--yfar=68] [--no-mesh]
"""
import sys, os, json, glob, math, time
sys.dont_write_bytecode = True
import numpy as np
from scipy import ndimage

REPO = "G:/Unity/GreatWave_2026_Fresh"
T45 = REPO + "/Tools/GWWaveGen/flip45"
B46 = REPO + "/Unity/Build/FLIP46"
S52_TOOLS = REPO + "/Unity/Build/STUDY52/tools"
SHAPE_DIAG = REPO + "/Unity/Build/FLIP45/diag/shape"
S52_JSON = REPO + "/Unity/Build/STUDY52/shape_measures.json"
for _p in (T45, S52_TOOLS, SHAPE_DIAG):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import g45_analyze as GA          # noqa: E402  Reader・records
import g45_crest3d as C3          # noqa: E402  frame_crests・track_crests・plunge_rule・overhang_cols・jet_angle
import g45_common as GC           # noqa: E402  L0（FLIP45 の波長。V1 の試しだけ）
import g45_export_unity as EU     # noqa: E402  read_frame_bytes（面の記録）
import s52_shape as S52           # noqa: E402  measure_mask
import d_shape_measure as DS      # noqa: E402  keep_bottom・pick・KEYS

G = 9.80665
FPS = 24.0
FINE = 0.05          # 形の量の水の格子（m）。d_shape_measure・STUDY52 と同じ
LC_RIDGE = 60.0

# GG06 の値（この仕事の文脈と BigWave_Recipes_ja.md §5.2 から。長さは h0、時間は √(h0/g) で割った値）
GG06 = dict(source="Guyenne & Grilli 2006, J. Fluid Mech. 547, 361-388（表 1・図 9。値は BigWave_Recipes_ja.md §5.2）",
            k=0.25, xs=5.225, n=15.0, x_end=19.0, y_wall=4.0, H0=0.6, x0=5.785, c=1.25,
            table1={0.25: dict(t=7.890, x=16.09, zB=0.706, hB=0.275, zB_hB=2.57)},
            two_d=dict(zB=0.680, hB=0.298, zB_hB=2.28), fig9_t=9.142, tol=0.05,
            touchdown_est=[9.1, 9.3])

SHAPE_KEYS = [("eta_c", "頂の高さ（m。原画は画素）"), ("face_chord_deg_01_05", "前の面の弦の角（0.1〜0.5 η_c、度）"),
              ("front_x01_rel", "前の面の足（0.1 η_c の所の頂からの距離 ÷ η_c）"), ("front_x05_rel", "前の面の 0.5 η_c の所 ÷ η_c"),
              ("front_x00_rel", "静かな水面を切る所 ÷ η_c（FLIP だけ）"), ("gap_max", "唇の下の空気の縦の長さの最大 ÷ η_c"),
              ("gap_under_tip", "唇の先の下の空気 ÷ η_c"), ("lip_thick_mid", "唇の厚さ（覆いの真ん中）÷ η_c"),
              ("hood_area", "巻いた所の面積 ÷ η_c²"), ("hood_wall_x_rel", "覆いの根元（頂からの距離 ÷ η_c）"),
              ("reach", "覆いの前への長さ ÷ η_c"), ("hood_height", "覆いの高さ ÷ η_c"), ("steep60_frac", "60° より立った前の輪郭の割合")]


def _f(v, nd=4):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return round(v, nd) if math.isfinite(v) else None


def _clean(o):
    """json に書けるように numpy の型をほどく。"""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.bool_, bool)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return float(o) if math.isfinite(float(o)) else None
    if isinstance(o, np.ndarray):
        return _clean(o.tolist())
    return o


def norm(p):
    return os.path.abspath(p).replace("\\", "/")


def default_out(rd):
    rd = norm(rd)
    if rd.lower().startswith(B46.lower() + "/"):
        return rd
    return B46 + "/smoke/test_" + os.path.basename(rd.rstrip("/"))


def guard_out(out):
    """FLIP46 の置き場所の外には書かない（この仕事の決まり）。"""
    o = norm(out)
    if not (o.lower() + "/").startswith(B46.lower() + "/"):
        raise SystemExit("出力の置き場所 %s は Unity/Build/FLIP46 の外。書かない" % o)
    os.makedirs(o, exist_ok=True)
    return o


def parse_opt(argv):
    opt = {}
    for q in argv:
        if q.startswith("--"):
            k, _, v = q[2:].partition("=")
            opt[k] = v if v else "1"
    return opt


# ======================================================================== 設定と海底
class Ctx:
    """1 つの計算の記録と、その海底・静かな水面のずれ・格子。"""

    def __init__(self, rd, opt=None):
        opt = opt or {}
        self.rd = norm(rd)
        cp = os.path.join(self.rd, "cfg.json")
        self.cfg = json.load(open(cp, encoding="utf8")) if os.path.exists(cp) else {}
        self.recs = GA.records(self.rd)
        self.P = self.cfg.get("parms") or (self.recs[0].get("parms") if self.recs else {}) or {}
        stage = self.cfg.get("stage") or (self.recs[0].get("stage") if self.recs else None)
        self.stage = stage
        flat_guess = (stage == "FLIP45") or ("in1" in self.P and "ex0" in self.P) or (float(self.P.get("ridge_on", 1.0)) < 0.5)
        self.kind = opt.get("bed") or ("flat" if flat_guess else "ridge")
        self.notes = []
        self.h0 = float(opt.get("h0") or self.P.get("h0") or (20.0 if self.kind == "flat" else 17.0))
        self.Ts = math.sqrt(self.h0 / G)
        self.t_off = float(self.P.get("t_off", 0.0))
        self.R1 = GA.Reader(self.rd, "hf", "eta")
        self.R2 = GA.Reader(self.rd, "r2", "sdf")
        self.R3 = GA.Reader(self.rd, "r3", "sdf")
        self.R4 = GA.Reader(self.rd, "r4", "sdf")
        if not self.R1.frames or not self.R2.frames:
            raise SystemExit("記録 hf_* か r2_* がない：%s" % self.rd)
        dp = self.P.get("dp")
        gs = float(self.P.get("gridscale", 2.0))
        m2 = self.R2.get(self.R2.frames[0])[1]
        self.vox = float(dp) * gs if dp else float(m2["dx"])
        self.dp = float(dp) if dp else self.vox / 2.0
        # 領域の端は 2 コマ目（計算の格子）から読む。1 コマ目は初めの水面の VDB の格子で、箱より広い（粒子 0.5 m で x −9〜332 m・横 77 m。
        # 2026-10-12 統合の役が直した：図の「y = 77 m は壁」の誤り）
        e, m1, _ = self.R1.get(self.R1.frames[1] if len(self.R1.frames) > 1 else self.R1.frames[0])
        self.x_min = m1["x0"] - 0.5 * m1["dx"]; self.x_max = m1["x0"] + (m1["res"][0] - 0.5) * m1["dx"]
        self.y_max = m1["z0"] + (m1["res"][2] - 0.5) * m1["dz"]
        # 尾根
        self.k, self.xs, self.n = GG06["k"], GG06["xs"], GG06["n"]
        self.ridge_src = "GG06 の既定（k 0.25・x' 5.225・1:15）"
        if self.kind == "ridge":
            self._ridge_from_cfg(opt)
        self.Lc = float(opt.get("Lc") or (GC.L0 if self.kind == "flat" else LC_RIDGE))
        self.y_far = float(opt.get("yfar") or (GG06["y_wall"] * self.h0 if self.kind == "ridge" else 68.0))
        self.H0 = GG06["H0"] * self.h0; self.c0 = GG06["c"] * math.sqrt(G * self.h0); self.xc0 = GG06["x0"] * self.h0
        sol = self.cfg.get("solitary") or {}          # 無次元の値（H0/h0・x0/h0・c/√(g h0)）があれば使う。なければ GG06 の値
        for kk, attr, sc in (("H0_nd", "H0", self.h0), ("x0_nd", "xc0", self.h0), ("c_nd", "c0", math.sqrt(G * self.h0))):
            if isinstance(sol.get(kk), (int, float)):
                setattr(self, attr, float(sol[kk]) * sc)
        self.off, self.off_src, self.off_info = self.still_offset()
        self.margin, self.margin_info = self.auto_margin()

    def _ridge_from_cfg(self, opt):
        cand = {}
        for d in (self.cfg.get("ridge") if isinstance(self.cfg.get("ridge"), dict) else {}, self.P):
            for kk, v in (d or {}).items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    cand[kk.lower()] = float(v)
        got = []
        for names, attr in ((("k", "ridge_k", "rk", "k_ridge", "rdg_k"), "k"),
                            (("xs", "x_start", "ridge_x0", "ridge_xs", "xs_nd", "x_start_nd", "rdg_x0", "rdg_xs"), "xs"),
                            (("n", "slope_n", "ridge_s", "ridge_n", "ridge_slope_n", "rdg_n"), "n")):
            src = "cfg"
            if self.cfg.get("ridge") is None:
                names = tuple(nm for nm in names if nm not in ("k", "xs", "n"))     # parms の 1 文字の名前は尾根の物とは限らない
            for nm in names:
                if nm in cand:
                    v = cand[nm]
                    if attr == "xs" and v > 30.0:          # m で書かれていれば h0 で割る
                        v = v / self.h0
                    setattr(self, attr, v); got.append("%s=%g（%s %s）" % (attr, v, src, nm)); break
            if attr in opt:
                setattr(self, attr, float(opt[attr])); got.append("%s=%g（引数）" % (attr, float(opt[attr])))
        if got:
            self.ridge_src = "・".join(got)
        else:
            self.notes.append("cfg に尾根の値（cfg['ridge'] の k・xs・n、または parms の ridge_k・ridge_x0・ridge_n）がないので GG06 の既定を使った")

    # ---------------------------------------------------------------- 海底
    def bed_z(self, x, y=0.0):
        """海底の高さ（計画の座標、静かな水面 0）。x・y は m（配列可）。"""
        x = np.asarray(x, float); y = np.asarray(y, float)
        if self.kind == "flat":
            return np.full(np.broadcast(x, y).shape, -self.h0)
        xp = x / self.h0; yp = y / self.h0
        return -self.h0 * (1.0 - np.maximum(xp - self.xs, 0.0) / self.n / np.cosh(self.k * yp) ** 2)

    def depth(self, x, y=0.0):
        return -self.bed_z(x, y)

    def tprime(self, t):
        return (t - self.t_off) / self.Ts

    def t_of_tprime(self, tp):
        return self.t_off + tp * self.Ts

    # ---------------------------------------------------------------- 静かな水面のずれ
    def quiet_x(self, t):
        """孤立波の前の裾が 5 mm より低い x（GN の減り方。Tanaka の厳密な解は速く減るので安全側）。"""
        a = self.H0 / self.h0
        kap = math.sqrt(3.0 * a / (4.0 * (1.0 + a))) / self.h0
        return self.xc0 + self.c0 * (t - self.t_off) + math.acosh(math.sqrt(max(self.H0 / 0.005, 1.0))) / kap

    def still_offset(self):
        online = None
        for r in self.recs:
            o = (r.get("info") or {}).get("still_offset_online")
            if o and o.get("value") is not None:
                online = dict(value=float(o["value"]), run=int(r.get("f_start") or 0), window=o.get("window", o.get("source")))
                break
        info = dict(online=online)
        if self.cfg.get("still_offset_m") is not None:
            return float(self.cfg["still_offset_m"]), "cfg（途中保存から始めた計算：元の計算 %s の値）" % self.cfg.get("still_offset_from"), info
        if self.kind == "flat":
            v, src = GA.still_offset(self.rd, self.cfg, self.recs, self.R1)
            return float(v), "FLIP45 の決まり（g45_analyze.still_offset）：" + src, info
        vals, used, drift = [], [], []
        for f in self.R1.frames:
            e, m, t = self.R1.get(f)
            xq = self.quiet_x(t)
            xs = m["x0"] + m["dx"] * np.arange(m["res"][0])
            sel = (xs >= xq) & (xs <= self.x_max - 2.0)
            if sel.sum() < 5:
                break
            v = float(np.nanmedian(e[:, sel]))
            drift.append([round(t, 3), round(v, 4), round(float(xq), 1)])
            if self.t_off + 0.5 - 1e-9 <= t <= self.t_off + 2.0 + 1e-9:
                vals.append(v); used.append(f)
        info["quiet_series"] = drift[::6]
        if drift:
            dv = np.array([d[1] for d in drift])
            info["quiet_drift_m"] = dict(first=float(dv[0]), last=float(dv[-1]), min=float(dv.min()), max=float(dv.max()),
                                         t_last=drift[-1][0], note_ja="波の前の静かな所の η_top の中央値の時系列（波の前の裾が 5 mm より低い所が 5 列以上ある間）")
        if vals:
            v = float(np.median(vals))
            if online is not None:
                info["online_minus_used_m"] = online["value"] - v
            return v, "t0 + 0.5〜2.0 s（コマ %d〜%d）の、孤立波の前の裾が 5 mm より低い所（x ≥ %.0f〜%.0f m）の η_top の中央値" % (
                used[0], used[-1], self.quiet_x(self.t_off + 0.5), self.quiet_x(self.t_off + 2.0)), info
        if online is not None:
            self.notes.append("静かな所の窓に記録がないので、計算の中で測った値（still_offset_online）を使った")
            return online["value"], "計算の中で測った値（run_c%05d）" % online["run"], info
        raise SystemExit("静かな水面のずれが出せない（t0 + 0.5〜2.0 s の記録がなく、cfg にも still_offset_m がない）")

    # ---------------------------------------------------------------- 海底の上の余白
    def auto_margin(self):
        """海底より下を水にする時の余白（0・0.5・1・1.5 格子）：静かな所（波の前、水面より 1 m 以上下）で、海底＋余白から格子 1 個の層の
        水面の場が正（空気）の割合が 2% より小さくなる最小の余白。"""
        fr = [f for f in self.R2.frames if self.R2.get(f)[2] >= self.t_off + 0.5 - 1e-9] or self.R2.frames
        f = fr[0]
        S, m, t = self.R2.get(f)
        S = S.astype(np.float32)
        xs = m["x0"] + m["dx"] * np.arange(S.shape[1]); yc = m["y0"] + m["dy"] * np.arange(S.shape[0])
        zb = self.bed_z(xs, float(m.get("z", 0.0)))
        cols = (xs >= self.quiet_x(t)) if self.kind == "ridge" else np.ones_like(xs, bool)
        cols &= xs <= self.x_max - 2.0
        fr_ = {}
        pick = None
        for k in (0.0, 0.5, 1.0, 1.5):
            mg = k * self.vox
            band = (yc[:, None] >= zb[None, :] + mg) & (yc[:, None] < zb[None, :] + mg + self.vox) & (yc[:, None] < self.off - 1.0) & cols[None, :]
            n = int(band.sum())
            frac = float((S[band] > 0).mean()) if n else None
            fr_[str(k)] = dict(cells=n, air_frac=frac)
            if pick is None and frac is not None and frac < 0.02:
                pick = mg
        if pick is None:
            pick = 1.5 * self.vox if any(v["cells"] for v in fr_.values()) else 0.0
        return pick, dict(frame=int(f), t=t, by_margin_vox=fr_, chosen_m=pick,
                          note_ja="海底＋余白から格子 1 個の層（静かな所、水面より 1 m 以上下）の水面の場が正の割合。2% より小さい最小の余白を使う")

    # ---------------------------------------------------------------- 断面の頂
    def section_crests(self, S, meta, y_lat, x_lo=None, x_hi=None, Lc=None, vox=None):
        """断面 sdf[縦, x]（meta：x0・dx・y0・dy、計画の座標）の頂（g45_crest3d.frame_crests）。海底より下（＋余白）を水にしてから読み、
        海底から格子 2 個以内の空気の穴は数えない。返り値 (頂の list, 一番上の水面, 海底を埋めた sdf)。"""
        vox = vox or self.vox
        S = np.array(S, dtype=np.float32, copy=True)
        xs = meta["x0"] + meta["dx"] * np.arange(S.shape[1]); yc = meta["y0"] + meta["dy"] * np.arange(S.shape[0])
        zb = self.bed_z(xs, y_lat)
        S[yc[:, None] < (zb + self.margin)[None, :]] = -1.0
        cr, top = C3.frame_crests(S, meta, self.off, vox, Lc or self.Lc, x_lo=x_lo, x_hi=x_hi, z_bed=float(zb.min()) - 1.0)
        for r in cr:
            keep = [c for c in r["cav"] if c[1] - (float(self.bed_z(c[0], y_lat)) - self.off) >= 2.0 * vox]
            r["cav_near_bed_dropped"] = len(r["cav"]) - len(keep)
            r["cav"] = keep; r["ncav"] = len(keep)
        return cr, top, S


# ======================================================================== (a) 真ん中の崩れる点
def centre_events(cx, t_lo, t_hi, x_lo, x_hi):
    rows = {}
    dx = None
    for f in cx.R2.frames:
        S, m, t = cx.R2.get(f)
        if t < t_lo - 1e-9 or t > t_hi + 1e-9:
            continue
        cr, _, _ = cx.section_crests(S, m, float(m.get("z", 0.0)), x_lo=x_lo - 0.5 * cx.Lc, x_hi=x_hi + 0.5 * cx.Lc)
        for r in cr:
            r["t"] = t
        rows[f] = cr; dx = m["dx"]
    tracks = C3.track_crests(rows, dx) if rows else []
    ev = []
    for tr in tracks:
        if len(tr) < 3:
            continue
        on = None; steep = None; emax = max(r["eta"] for f, r in tr)
        for i, (f, r) in enumerate(tr):
            if np.isfinite(r["thmax"]) and x_lo <= r["xc"] <= x_hi and (steep is None or r["thmax"] > steep["thmax"]):
                steep = dict(frame=f, t=r["t"], xc=r["xc"], eta_c=r["eta"], thmax=r["thmax"])
            if on is None and np.isfinite(r["thmax"]) and r["thmax"] >= 90.0 and x_lo <= r["xc"] <= x_hi:
                on = dict(frame=f, t=r["t"], xc=r["xc"], x_vert=r["x_vert"], eta_c=r["eta"], H=r["H"], thmax=r["thmax"],
                          trough_front=r["trough_front"], i=i)
        ev.append(dict(first_frame=tr[0][0], last_frame=tr[-1][0], n=len(tr), eta_max=emax, onset=on, steepest=steep,
                       series=[[int(f), round(r["t"], 4), round(r["xc"], 3), round(r["eta"], 3), _f(r["thmax"], 2)] for f, r in tr]))
    return ev


def pick_main(ev):
    ons = [e for e in ev if e["onset"] is not None]
    if not ons:
        return None, []
    big = max(e["eta_max"] for e in ev)
    cand = [e for e in ons if e["eta_max"] >= 0.5 * big] or ons
    main = min(cand, key=lambda e: e["onset"]["t"])
    return main, [e for e in ons if e is not main]


def interp_onset(main):
    """thmax が 90° を越えたコマとその前のコマの間を線形に補った時刻・x・頂の高さ。"""
    s = main["series"]; i = main["onset"]["i"]
    if i == 0 or s[i - 1][4] is None:
        return None
    (f0, t0, x0, e0, a0), (f1, t1, x1, e1, a1) = s[i - 1], s[i]
    if a1 <= a0 or a0 >= 90.0:
        return None
    w = (90.0 - a0) / (a1 - a0)
    return dict(t=t0 + w * (t1 - t0), xc=x0 + w * (x1 - x0), eta_c=e0 + w * (e1 - e0), frames=[f0, f1], thmax=[a0, a1], w=w)


def compare_gg06(cx, on, interp):
    tab = GG06["table1"].get(round(cx.k, 4)) if cx.kind == "ridge" else GG06["table1"][0.25]
    out = dict(source=GG06["source"], tol=GG06["tol"], k=cx.k, h0=cx.h0, Ts=cx.Ts)
    if cx.kind != "ridge":
        out["note_ja"] = "この記録は尾根の計算ではない（海底 %s）。下の比べは道具の試しで、意味はない" % cx.kind
    if tab is None:
        out["note_ja"] = "k %g の表 1 の値はこの道具に入っていない（k 0.25 だけ）" % cx.k
        return out
    hB = float(cx.depth(on["xc"], 0.0))
    got = dict(t_s=on["t"] - cx.t_off, x_m=on["xc"], zB_m=on["eta_c"], hB_m=hB, zB_over_hB=on["eta_c"] / hB)
    paper = dict(t_s=tab["t"] * cx.Ts, x_m=tab["x"] * cx.h0, zB_m=tab["zB"] * cx.h0, hB_m=tab["hB"] * cx.h0, zB_over_hB=tab["zB_hB"])
    two = dict(zB_m=GG06["two_d"]["zB"] * cx.h0, hB_m=GG06["two_d"]["hB"] * cx.h0, zB_over_hB=GG06["two_d"]["zB_hB"])
    rows = {}
    for k_, v in got.items():
        p = paper[k_]
        rows[k_] = dict(value=v, paper_3d=p, rel=v / p - 1.0, inside_5pct=bool(abs(v / p - 1.0) <= GG06["tol"]),
                        paper_2d=two.get(k_), rel_2d=(v / two[k_] - 1.0) if k_ in two else None)
    rows["t_s"]["note_ja"] = "計算の始め（コマ 1、t' 0）からの時間。GG06 t' %.3f × √(h0/g) %.4f s" % (tab["t"], cx.Ts)
    rows["x_m"]["dist_from_x0_rel"] = (on["xc"] - cx.xc0) / (paper["x_m"] - cx.xc0) - 1.0
    rows["x_m"]["note_ja"] = "頂の x（m）。dist_from_x0_rel は初めの頂 x0 からの進んだ距離の比 − 1"
    out.update(rows=rows, primary_all_inside=bool(all(rows[k_]["inside_5pct"] for k_ in ("zB_m", "hB_m", "zB_over_hB"))),
               dimensionless=dict(t_prime=cx.tprime(on["t"]), x_prime=on["xc"] / cx.h0, zB_over_h0=on["eta_c"] / cx.h0, hB_over_h0=hB / cx.h0))
    if interp:
        hBi = float(cx.depth(interp["xc"], 0.0))
        out["interp_90deg"] = dict(t_s=interp["t"] - cx.t_off, t_prime=cx.tprime(interp["t"]), x_m=interp["xc"], zB_m=interp["eta_c"], hB_m=hBi,
                                   zB_over_hB=interp["eta_c"] / hBi, rel_zB_over_hB=(interp["eta_c"] / hBi) / tab["zB_hB"] - 1.0,
                                   note_ja="thmax が 90° を越えた前後のコマの間を線形に補った値（記録。判定は越えたコマの値）")
    return out


# ======================================================================== (c) 着水
def touchdown(cx, main, t_end):
    on = main["onset"]
    path = {int(s[0]): s[2] for s in main["series"]}
    last_tip = None
    for f in cx.R2.frames:
        if f < on["frame"]:
            continue
        S, m, t = cx.R2.get(f)
        if t > t_end + 1e-9:
            break
        xc = path.get(f)
        cr, top, Sf = cx.section_crests(S, m, float(m.get("z", 0.0)), x_lo=(xc - 10.0) if xc is not None else on["xc"] - 20.0,
                                        x_hi=(xc + 10.0) if xc is not None else on["xc"] + 40.0)
        if not cr:
            continue
        c = max(cr, key=lambda r: r["eta"])
        xs = m["x0"] + m["dx"] * np.arange(Sf.shape[1]); ys = m["y0"] + m["dy"] * np.arange(Sf.shape[0]) - cx.off
        pr = C3.plunge_rule(c, Sf, xs, ys, cx.off, cx.vox, cx.Lc)
        if c.get("tip") is not None:
            last_tip = dict(frame=int(f), t=t, tip=c["tip"])
        if pr["plunge"]:
            xp = pr["tip"][0] if pr.get("tip") else (c["cav"][0][0] if c["cav"] else c["xc"])
            return dict(frame=int(f), t=t, t_prime=cx.tprime(t), xc=c["xc"], x_point=xp, by="cavity" if pr["a_cavity"] else "tip<=0 + overhang",
                        rule=pr, cav=c["cav"], tip=c["tip"], last_tip_before=last_tip, jet_time_s=t - on["t"], jet_dist_m=xp - on["xc"],
                        cav_near_bed_dropped=c.get("cav_near_bed_dropped", 0))
    return None


def jet_at(cx, f, xc):
    """着水の 0.25 s 前のコマの、唇の先の水の速さの向き（g45_analyze.jet_at と同じ。海底を埋めた断面で頂を読む）。"""
    if f not in cx.R2.b:
        return None
    S, m, t = cx.R2.get(f)
    cr, _, _ = cx.section_crests(S, m, float(m.get("z", 0.0)), x_lo=xc - 15.0, x_hi=xc + 15.0)
    if not cr:
        return None
    c = max(cr, key=lambda r: r["eta"])
    if c["tip"] is None:
        return dict(frame=f, t=t, note_ja="唇の先が読めない")
    u = cx.R2.get(f, "u")[0].astype(np.float64); w = cx.R2.get(f, "w")[0].astype(np.float64)
    mv = m.get("vel", {})
    xt, yt = c["tip"][0], c["tip"][1] + cx.off

    def samp(arr, mm):
        if not mm:
            return float("nan")
        fx = (xt - mm["p0"][0]) / mm["d"][0]; fy = (yt - mm["p0"][1]) / mm["d"][1]
        i = int(np.clip(np.floor(fx), 0, arr.shape[1] - 2)); j = int(np.clip(np.floor(fy), 0, arr.shape[0] - 2))
        a = fx - i; b = fy - j
        return float((1 - b) * ((1 - a) * arr[j, i] + a * arr[j, i + 1]) + b * ((1 - a) * arr[j + 1, i] + a * arr[j + 1, i + 1]))
    uu = samp(u, mv.get("vel.x")); ww = samp(w, mv.get("vel.y"))
    if not (np.isfinite(uu) and np.isfinite(ww)):
        return dict(frame=f, t=t, tip=c["tip"], note_ja="流速の記録が読めない")
    return dict(frame=f, t=t, tip=c["tip"], u=uu, w=ww, **C3.jet_angle(uu, ww))


# ======================================================================== (b) 短い頂
def mesh_frame(cx, f, near=2):
    """面の記録（surf/s_FFFFF.gw45s）。そのコマがなければ ±near コマの中で一番近い物。"""
    for d in [0] + [s * k for k in range(1, near + 1) for s in (1, -1)]:
        p = os.path.join(cx.rd, "surf", "s_%05d.gw45s" % (f + d))
        if os.path.exists(p):
            return EU.read_frame_bytes(open(p, "rb").read()), f + d
    return None, None


def mesh_cut_segments(P, tri, ycut):
    """面（計画の座標 (x, 上, 横)）を横 ycut で切った線分 (n, 2, [x, 上])。"""
    s = P[:, 2] - ycut
    sa = s[tri]
    cross = (sa.min(1) < 0) & (sa.max(1) > 0)
    T = tri[cross].astype(np.int64); S3 = sa[cross]
    if not len(T):
        return np.zeros((0, 2, 2))
    pts = []; oks = []
    for i, j in ((0, 1), (1, 2), (2, 0)):
        a, b = T[:, i], T[:, j]; s1, s2 = S3[:, i], S3[:, j]
        ok = (s1 < 0) != (s2 < 0)
        w = np.where(ok, s1 / np.where(ok, s1 - s2, 1.0), 0.0)
        q = P[a] + w[:, None] * (P[b] - P[a])
        pts.append(q[:, :2]); oks.append(ok)
    pts = np.stack(pts, 1); oks = np.stack(oks, 1)
    good = oks.sum(1) == 2
    pts = pts[good]; oks = oks[good]
    idx = np.argsort(~oks, axis=1, kind="stable")[:, :2]
    return np.take_along_axis(pts, idx[:, :, None], axis=1)


def mesh_mask(segs, X, Z):
    """線分から、x の列ごとに上から交わりを並べて水を埋める：上から 2 つずつ（上の面と下の面）を水とし、数が奇数なら最後の 1 つから
    下の端までを水とする。面が海底に沿って閉じた列（偶数）と、下で切って開いた列（奇数）のどちらも同じ決まりで埋まる（FLIP46 の面は
    縦 −15 m で切るので、深い所は開き、尾根の上は海底で閉じる）。交わりのない列は隣の良い列で埋める。返り値 (M[z, x], 情報)。"""
    M = np.zeros((len(Z), len(X)), bool)
    if not len(segs):
        return M, dict(n_seg=0)
    x1, z1, x2, z2 = segs[:, 0, 0], segs[:, 0, 1], segs[:, 1, 0], segs[:, 1, 1]
    ok = x1 != x2
    x1, z1, x2, z2 = x1[ok], z1[ok], x2[ok], z2[ok]
    lo, hi = np.minimum(x1, x2), np.maximum(x1, x2)
    i0 = np.searchsorted(X, lo, "left"); i1 = np.searchsorted(X, hi, "left")
    n = np.maximum(i1 - i0, 0)
    rep = np.repeat(np.arange(len(n)), n)
    off_ = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
    ii = i0[rep] + off_
    w = (X[ii] - x1[rep]) / (x2[rep] - x1[rep])
    zh = z1[rep] + w * (z2[rep] - z1[rep])
    order = np.lexsort((-zh, ii))
    ii, zh = ii[order], zh[order]
    cnt = np.bincount(ii, minlength=len(X))
    start = np.concatenate([[0], np.cumsum(cnt)[:-1]])
    bad = []
    for i in range(len(X)):
        c = cnt[i]
        if c == 0:
            bad.append(i); continue
        h = zh[start[i]:start[i] + c]
        k = 0
        while k < c:
            ztop = h[k]; zbot = h[k + 1] if k + 1 < c else Z[0] - 1.0
            M[(Z <= ztop) & (Z >= zbot), i] = True
            k += 2
    good = np.setdiff1d(np.arange(len(X)), bad)
    if len(good):
        for i in bad:
            M[:, i] = M[:, good[np.argmin(np.abs(good - i))]]
    return M, dict(n_seg=int(len(segs)), empty_cols=len(bad), odd_cols=int(np.sum(cnt % 2 == 1)), even_cols=int(np.sum((cnt > 0) & (cnt % 2 == 0))))


def rows_summary(rows, y_far, dy):
    """横の位置ごとの (y, thmax, xc, eta) から：y = 0 から続く巻いた範囲（thmax ≥ 90°）、巻いた y の全部、y_far の行。"""
    rows = sorted([r for r in rows if r.get("y") is not None], key=lambda r: r["y"])
    out = dict(n=len(rows), y_range=[rows[0]["y"], rows[-1]["y"]] if rows else None)
    if not rows:
        return out
    isov = [bool(r.get("thmax") is not None and r["thmax"] >= 90.0) for r in rows]
    out["y_over90"] = [round(r["y"], 3) for r, v in zip(rows, isov) if v]
    # 真ん中の近く（最初の行から 5 m 以内）で始まる、巻いた行の一続き（真ん中の 1 行だけ 90° に届かない面の読みもあるため）
    i0 = next((i for i, v in enumerate(isov) if v and rows[i]["y"] <= rows[0]["y"] + 5.0), None)
    cont = None
    if i0 is not None:
        for i in range(i0, len(rows)):
            if isov[i]:
                cont = rows[i]["y"]
            else:
                break
    out["overturned_run_start_y"] = rows[i0]["y"] if i0 is not None else None
    out["overturned_half_from_centre_m"] = (cont + 0.5 * dy) if cont is not None else 0.0
    out["overturned_full_m"] = 2.0 * out["overturned_half_from_centre_m"]
    out["overturned_reaches_last_row"] = bool(cont is not None and cont >= rows[-1]["y"] - 1e-6)
    rf = min(rows, key=lambda r: abs(r["y"] - y_far))
    if rf.get("thmax") is not None:
        sv = bool(rf["thmax"] < 90.0 and not rf.get("overhang", False))
    else:                         # 頂（0.5 m 以上）がない行：覆いかぶさりがなければ一価
        sv = (not rf["overhang"]) if "overhang" in rf else None
    out["far_row"] = dict(y=rf["y"], thmax=rf.get("thmax"), eta=rf.get("eta"), xc=rf.get("xc"), overhang=rf.get("overhang"),
                          single_valued=sv, dist_from_y_far=abs(rf["y"] - y_far),
                          note_ja=None if rf.get("thmax") is not None else "0.5 m より高い頂がない行。覆いかぶさり（同じ x の列で水・空気・水）がなければ一価とした")
    etas = [r["eta"] for r in rows if r.get("eta") is not None]
    if etas:
        out["crest_eta"] = dict(centre=rows[0].get("eta"), max=max(etas), min=min(etas), far=rf.get("eta"))
    return out


def lateral_rows_r4(cx, f, xc0):
    if f not in cx.R4.b:
        return None
    a, m4, t = cx.R4.get(f)
    zs = m4["z0"] + m4["dz"] * np.arange(a.shape[0])
    meta = dict(x0=m4["x0"], dx=m4["dx"], y0=m4["y0"], dy=m4["dy"])
    xs = m4["x0"] + m4["dx"] * np.arange(a.shape[2]); ys = m4["y0"] + m4["dy"] * np.arange(a.shape[1]) - cx.off
    rows = []
    for k in range(a.shape[0]):
        cr, _, Sf = cx.section_crests(a[k], meta, float(zs[k]), x_lo=xc0 - 0.5 * cx.Lc, x_hi=xc0 + 0.5 * cx.Lc)
        if not cr:
            n_oh, run = C3.overhang_cols(Sf, xs, ys, cx.off, xc0 - 0.5 * cx.Lc, xc0 + 0.5 * cx.Lc)
            rows.append(dict(y=float(zs[k]), overhang=bool(run >= 2))); continue
        c = max(cr, key=lambda r: r["eta"])
        n_oh, run = C3.overhang_cols(Sf, xs, ys, cx.off, c["xc"], c["xc"] + 0.75 * cx.Lc)
        rows.append(dict(y=float(zs[k]), thmax=_f(c["thmax"], 2), xc=_f(c["xc"], 3), eta=_f(c["eta"], 3), ncav=c["ncav"], overhang=bool(run >= 2)))
    return dict(t=t, x_range=[float(xs[0]), float(xs[-1])], rows=rows, summary=rows_summary(rows, cx.y_far, m4["dz"]))


def lateral_rows_r3(cx, f, xc0):
    if f not in cx.R3.b:
        return None
    S, m, t = cx.R3.get(f)
    y = float(m.get("z", 0.0))
    cr, _, _ = cx.section_crests(S, m, y, x_lo=xc0 - 0.5 * cx.Lc, x_hi=xc0 + 0.5 * cx.Lc)
    if not cr:
        return dict(y=y, note_ja="頂なし")
    c = max(cr, key=lambda r: r["eta"])
    return dict(y=y, thmax=_f(c["thmax"], 2), xc=_f(c["xc"], 3), eta=_f(c["eta"], 3), ncav=c["ncav"])


def lateral_rows_mesh(cx, f, xc0, dy=1.0, fine=0.1):
    d, fm = mesh_frame(cx, f)
    if d is None:
        return None
    P = d["P"]; tri = d["tri"].astype(np.int64)
    ylo, yhi = float(P[:, 2].min()), float(P[:, 2].max())
    xw0, xw1 = max(xc0 - 0.5 * cx.Lc, float(P[:, 0].min())), min(xc0 + 0.5 * cx.Lc, float(P[:, 0].max()))
    X = np.arange(xw0, xw1, fine)
    rows = []
    for yq in np.arange(max(ylo, 0.0) + 0.25, yhi - 0.25 + 1e-9, dy):
        segs = mesh_cut_segments(P, tri, yq)
        if not len(segs):
            rows.append(dict(y=float(yq))); continue
        segs = segs.copy(); segs[:, :, 1] -= cx.off
        zb = cx.bed_z(X, yq) - cx.off
        zlo = max(float(zb.min()) - 0.5, -12.0)
        ztop = float(segs[:, :, 1].max()) + 1.0
        Z = np.arange(zlo, ztop, fine)
        M, inf = mesh_mask(segs, X, Z)
        M |= Z[:, None] < (zb + cx.margin)[None, :]
        M = DS.keep_bottom(M)
        Sg = ndimage.gaussian_filter(np.where(M, -1.0, 1.0).astype(np.float32), 1.0)
        meta = dict(x0=float(X[0]), dx=fine, y0=float(Z[0]) + cx.off, dy=fine)
        cr, _ = C3.frame_crests(Sg, meta, cx.off, cx.vox, cx.Lc, x_lo=xc0 - 0.5 * cx.Lc, x_hi=xc0 + 0.5 * cx.Lc, z_bed=zlo + cx.off - 1.0)
        if not cr:
            n_oh, run = C3.overhang_cols(Sg, X, Z, cx.off, xc0 - 0.5 * cx.Lc, xc0 + 0.5 * cx.Lc)
            rows.append(dict(y=float(yq), n_seg=inf.get("n_seg"), overhang=bool(run * fine >= 0.5))); continue
        c = max(cr, key=lambda r: r["eta"])
        n_oh, run = C3.overhang_cols(Sg, X, Z, cx.off, c["xc"], c["xc"] + 0.75 * cx.Lc)
        rows.append(dict(y=float(yq), thmax=_f(c["thmax"], 2), xc=_f(c["xc"], 3), eta=_f(c["eta"], 3), overhang=bool(run * fine >= 0.5),
                         empty_cols=inf.get("empty_cols"), odd_cols=inf.get("odd_cols"), even_cols=inf.get("even_cols")))
    return dict(frame_used=int(fm), t=d["t"], dy=dy, fine=fine, rows=rows, summary=rows_summary(rows, cx.y_far, dy),
                note_ja="面の記録を横 dy ごとに切り、%.2f m の水の格子にして（1 格子のぼかし）同じ頂の読み（thmax）をした" % fine)


def lateral_rows_hf(cx, f, xc0):
    """一番上の水面 η_top で、y ごとの頂の高さと前の面の 1 格子の傾きの最大（巻きは読めない。目安）。"""
    e, m, t = cx.R1.get(f)
    xs = m["x0"] + m["dx"] * np.arange(m["res"][0]); zs = m["z0"] + m["dz"] * np.arange(m["res"][2])
    sel = np.where((xs >= xc0 - 0.5 * cx.Lc) & (xs <= xc0 + 0.5 * cx.Lc))[0]
    rows = []
    for j in range(len(zs)):
        p = e[j, sel] - cx.off
        if not np.isfinite(p).any():
            continue
        p = np.nan_to_num(p, nan=-99.0)
        ic = int(np.argmax(p)); ec = float(p[ic])
        ang = 0.0; drop = 0.0
        i = ic
        while i + 1 < len(p) and p[i] > 0.1 * ec:
            d_ = p[i] - p[i + 1]
            drop = max(drop, d_); ang = max(ang, math.degrees(math.atan2(d_, m["dx"])))
            i += 1
        rows.append(dict(y=float(zs[j]), eta=_f(ec, 3), xc=_f(xs[sel][ic], 3), front_max_deg_1cell=_f(ang, 2), max_drop_m=_f(drop, 3)))
    etas = [r["eta"] for r in rows]
    rf = min(rows, key=lambda r: abs(r["y"] - cx.y_far)) if rows else None
    return dict(t=t, rows=rows[::max(1, len(rows) // 70)], crest_eta=dict(centre=rows[0]["eta"] if rows else None, max=max(etas) if etas else None,
                                                                         min=min(etas) if etas else None, far=rf["eta"] if rf else None, far_y=rf["y"] if rf else None),
                note_ja="hf は列ごとの一番上の水面なので巻きは読めない。前の面の 1 格子の傾きの最大と落ちの大きさは目安")


def short_crest(cx, frames, use_mesh=True, t_win=None):
    out = {}
    for name, f, xc0 in frames:
        if f is None or f not in cx.R1.b or f not in cx.R2.b:
            out[name] = dict(frame=f, note_ja="記録の外")
            continue
        if t_win and not (t_win[0] - 1e-9 <= cx.R2.get(f)[2] <= t_win[1] + 1e-9):
            out[name] = dict(frame=f, note_ja="読む時間の窓（--t0・--t1）の外")
            continue
        t = cx.R1.get(f)[2]
        row = dict(frame=int(f), t=t, t_prime=cx.tprime(t), xc_centre=xc0)
        S, m, _ = cx.R2.get(f)
        cr, _, _ = cx.section_crests(S, m, float(m.get("z", 0.0)), x_lo=xc0 - 0.5 * cx.Lc, x_hi=xc0 + 0.5 * cx.Lc)
        if cr:
            c = max(cr, key=lambda r: r["eta"])
            row["centre_r2"] = dict(thmax=_f(c["thmax"], 2), xc=_f(c["xc"], 3), eta=_f(c["eta"], 3), ncav=c["ncav"], overturned=bool(c["thmax"] >= 90.0))
        r4 = lateral_rows_r4(cx, f, xc0)
        if r4:
            row["r4"] = r4
        r3 = lateral_rows_r3(cx, f, xc0)
        if r3:
            row["r3"] = r3
        if use_mesh:
            try:
                ms = lateral_rows_mesh(cx, f, xc0)
            except Exception as e:
                ms = dict(error=repr(e)[:300])
            if ms:
                row["mesh"] = ms
        row["hf"] = lateral_rows_hf(cx, f, xc0)
        # 主な読み：r4 が y_far まで届けば r4、なければ面、どちらもなければ hf の目安だけ
        best = None
        for src in ("r4", "mesh"):
            s_ = (row.get(src) or {}).get("summary")
            if s_ and s_.get("far_row") and s_["far_row"]["dist_from_y_far"] <= 2.0:
                best = src; break
        if best is None:
            for src in ("r4", "mesh"):
                if (row.get(src) or {}).get("summary"):
                    best = src; break
        row["primary_source"] = best
        if best:
            s_ = row[best]["summary"]
            row["overturned_half_m"] = s_["overturned_half_from_centre_m"]
            row["overturned_full_m"] = s_["overturned_full_m"]
            row["far_single_valued"] = s_["far_row"]["single_valued"] if s_["far_row"]["dist_from_y_far"] <= 2.0 else None
            row["far_row"] = s_["far_row"]
        out[name] = row
    return out


# ======================================================================== (d) 形の量
def r2_mask(cx, f, xc_guess, half=60.0, zlo=-12.0):
    """r2 の断面（海底を埋めた）から形の量の水の格子（d_shape_measure.v1_mask_r2 と同じ作り。窓は記録の中に切る）。"""
    S, m, t = cx.R2.get(f)
    xs = m["x0"] + m["dx"] * np.arange(S.shape[1]); yc = m["y0"] + m["dy"] * np.arange(S.shape[0])
    Sf = np.array(S, dtype=np.float32, copy=True)
    Sf[yc[:, None] < (cx.bed_z(xs, float(m.get("z", 0.0))) + cx.margin)[None, :]] = -1.0
    ys = yc - cx.off
    water = Sf < 0
    sel = (xs >= xc_guess - 0.5 * cx.Lc) & (xs <= xc_guess + 0.5 * cx.Lc)
    jt = np.where(water[:, sel].any(1))[0].max()
    X = np.arange(max(xc_guess - half, xs[0]), min(xc_guess + half, xs[-1]), FINE)
    Z = np.arange(max(zlo, ys[0]), ys[jt] + 1.5, FINE)
    fx = (X - xs[0]) / m["dx"]; fz = (Z - ys[0]) / m["dy"]
    ix = np.clip(np.floor(fx).astype(int), 0, len(xs) - 2); wx = fx - ix
    iz = np.clip(np.floor(fz).astype(int), 0, len(ys) - 2); wz = fz - iz
    A = Sf[iz][:, ix] * (1 - wx)[None, :] + Sf[iz][:, ix + 1] * wx[None, :]
    B = Sf[iz + 1][:, ix] * (1 - wx)[None, :] + Sf[iz + 1][:, ix + 1] * wx[None, :]
    F = A * (1 - wz)[:, None] + B * wz[:, None]
    return DS.keep_bottom(F < 0), X, Z, t


def shape_measures(cx, main, td, t_end):
    on = main["onset"]
    path = {int(s[0]): s[2] for s in main["series"]}
    f_on = int(on["frame"])
    if td:
        f_last = int(td["frame"])
    else:
        f_last = max([f for f in cx.R2.frames if f >= f_on and cx.R2.get(f)[2] <= min(on["t"] + 2.0, t_end) + 1e-9] or [f_on])
    series = []
    xg = on["xc"]
    for f in range(f_on, f_last + 1):
        if f not in cx.R2.b:
            continue
        xg = path.get(f, xg)
        try:
            M, X, Z, t = r2_mask(cx, f, xg)
            mm = S52.measure_mask(M, X, Z, flip_extra=dict(Lc=cx.Lc))
            row = DS.pick(mm); row.update(frame=f, t=t, reach_m=mm.get("reach_m"), hood_height_m=mm.get("hood_height_m"), lip_thick_mid_m=mm.get("lip_thick_mid_m"))
        except Exception as e:
            row = dict(frame=f, error=repr(e)[:200])
        series.append(row)
    ok = [r for r in series if "error" not in r]
    if not ok:
        return dict(error="形の量が読めない", series=series)
    f_max = max(ok, key=lambda r: (r.get("hood_height_m") or 0.0))["frame"]
    sel = dict(onset=f_on, max_overturn=f_max)
    if td:
        sel["contact"] = int(td["frame"])
    pr = json.load(open(S52_JSON, encoding="utf8"))["print"]
    tab = {}
    for k, lab in SHAPE_KEYS:
        r_ = dict(label_ja=lab, print_cn=_f(pr["cn"].get(k)), print_drawn=_f(pr["drawn"].get(k)))
        for nm, fr in sel.items():
            rr = [r for r in ok if r["frame"] == fr]
            r_[nm] = _f(rr[0].get(k)) if rr else None
        tab[k] = r_
    return dict(frames=sel, rule_ja="最も巻いたコマ＝巻き始め〜%s のコマで覆いの高さ（hood_height_m）が最大（STUDY52・d_shape_measure と同じ）" % ("着水" if td else "巻き始め + 2 s"),
                table=tab, series=[{k: (_f(v) if isinstance(v, float) else v) for k, v in r.items()} for r in series],
                note_ja="同じ物差し（STUDY52 measure_mask）。長さと高さは η_c で割った値、角は度。原画 cn は縦の 30% の伸びを戻した読み、drawn は描かれたまま。"
                        "原画の η_c は画素なので比べない。巻いていないコマの覆いの量は 0")


# ======================================================================== 本体
def analyze(rd, opt):
    t_start = time.time()
    cx = Ctx(rd, opt)
    out_dir = guard_out(opt.get("out") or default_out(rd))
    t_first = cx.R2.get(cx.R2.frames[0])[2]; t_last = cx.R2.get(cx.R2.frames[-1])[2]
    t_lo = max(float(opt.get("t0", -1e9)), t_first + 0.25 if cx.kind == "ridge" else t_first)
    t_hi = min(float(opt.get("t1", 1e9)), t_last)
    if cx.kind == "flat" and "in1" in cx.P:
        x_lo, x_hi = float(cx.P["in1"]) + 5.0, float(cx.P["ex0"])
    else:
        x_lo, x_hi = cx.x_min + 5.0, cx.x_max - 2.0
    out = dict(run_dir=cx.rd, out_dir=out_dir, date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip46/g46_analyze.py",
               stage=cx.stage, bed=dict(kind=cx.kind, h0=cx.h0, k=cx.k, xs_nd=cx.xs, slope_n=cx.n, source=cx.ridge_src,
                                        depth_check=(dict(centre_x19=float(cx.depth(19.0 * cx.h0, 0.0) / cx.h0),
                                                          slope_y2=float(1.0 / cx.n / math.cosh(cx.k * 2.0) ** 2), slope_y4=float(1.0 / cx.n / math.cosh(cx.k * 4.0) ** 2),
                                                          paper=dict(centre_x19=0.082, slope_y2=0.052, slope_y4=0.028)) if cx.kind == "ridge" else None)),
               dp=cx.dp, vox=cx.vox, Ts=cx.Ts, t_off=cx.t_off, Lc=cx.Lc, y_far=cx.y_far, domain=dict(x=[cx.x_min, cx.x_max], y_max=cx.y_max),
               frames=[cx.R2.frames[0], cx.R2.frames[-1]], t_range=[t_first, t_last], window=dict(t=[t_lo, t_hi], x=[x_lo, x_hi]),
               still_level_offset_m=cx.off, still_offset_source=cx.off_src, still_offset_info=cx.off_info,
               bed_margin=cx.margin_info, records=dict(hf=len(cx.R1.frames), r2=len(cx.R2.frames), r3=len(cx.R3.frames), r4=len(cx.R4.frames),
                                                       surf=len(glob.glob(os.path.join(cx.rd, "surf", "s_*.gw45s")))),
               notes=cx.notes)
    stops = [r.get("stopped") for r in cx.recs]
    out["stops"] = stops
    # (a)
    ev = centre_events(cx, t_lo, t_hi, x_lo, x_hi)
    main, others = pick_main(ev)
    out["events_n"] = len(ev)
    out["other_onsets"] = [dict(t=e["onset"]["t"], xc=e["onset"]["xc"], eta_c=e["onset"]["eta_c"]) for e in others][:20]
    if main is None:
        st = [e["steepest"] for e in ev if e["steepest"] is not None]
        out["onset"] = None
        out["steepest"] = max(st, key=lambda s: s["thmax"]) if st else None
        out["note_onset_ja"] = "前の面に縦の接線ができなかった（thmax ≥ 90° のコマがない）。最も険しいコマを steepest に書いた"
        out["shape"] = dict(error="巻き始めがないので読まない")
        out["elapsed_s"] = round(time.time() - t_start, 1)
        _write(out, out_dir, cx)
        return out
    on = dict(main["onset"]); on.pop("i", None)
    on["t_prime"] = cx.tprime(on["t"]); on["hB"] = float(cx.depth(on["xc"], 0.0)); on["zB_over_hB"] = on["eta_c"] / on["hB"]
    out["onset"] = on
    ip = interp_onset(main)
    out["onset_interp"] = ip
    out["gg06_table1"] = compare_gg06(cx, on, ip)
    out["centre_track"] = dict(first_frame=main["first_frame"], last_frame=main["last_frame"], eta_max=main["eta_max"],
                               series=main["series"][::2] if len(main["series"]) > 400 else main["series"],
                               columns=["frame", "t", "xc", "eta_c", "thmax"])
    # (c)
    td = touchdown(cx, main, t_hi)
    out["touchdown"] = td
    if td:
        out["touchdown"]["gg06_estimate_ja"] = "GG06 の BEM は t' 9.142 の少し後、着水の前で止まる。着水 t' %.1f〜%.1f（%.1f〜%.1f s）は推定（BigWave_Recipes_ja.md §5.2）" % (
            GG06["touchdown_est"][0], GG06["touchdown_est"][1], GG06["touchdown_est"][0] * cx.Ts, GG06["touchdown_est"][1] * cx.Ts)
        out["jet"] = jet_at(cx, int(td["frame"]) - 6, td["xc"])
    # (b)
    path = {int(s[0]): s[2] for s in main["series"]}

    def nearest_frame(t):
        if t < t_first - 1e-9 or t > t_last + 1e-9:
            return None
        return min(cx.R2.frames, key=lambda f: abs(cx.R2.get(f)[2] - t))

    def xc_at(f):
        """そのコマの真ん中の頂の x（頂の追いが切れた後は、いちばん近いコマの値。窓は ±Lc/2 なので足りる）。"""
        if f in path:
            return path[f]
        k = min(path, key=lambda q: abs(q - f))
        return path[k]
    f_fig9 = nearest_frame(cx.t_of_tprime(GG06["fig9_t"]))
    f_fig9r = nearest_frame(on["t"] + (GG06["fig9_t"] - GG06["table1"][0.25]["t"]) * cx.Ts)
    fr = [("onset", int(on["frame"]), on["xc"]),
          ("gg06_fig9_time", f_fig9, xc_at(f_fig9) if f_fig9 else None),
          ("onset_plus_fig9_delay", f_fig9r, xc_at(f_fig9r) if f_fig9r else None)]
    if td:
        fr.append(("touchdown", int(td["frame"]), xc_at(int(td["frame"]))))
    out["short_crest"] = short_crest(cx, fr, use_mesh=("no-mesh" not in opt), t_win=(t_lo, t_hi))
    out["short_crest_note_ja"] = ("巻いた範囲は primary_source（r4 が y_far まで届けば r4、なければ面の記録）の、y = 0 から続く thmax ≥ 90° の y の範囲（片側）と × 2。"
                                  "far_single_valued は y = %g m（GG06 の y' 4 の壁）にいちばん近い行が thmax < 90° で覆いかぶさりがないか。"
                                  "GG06 図 9：t' 9.142 に真ん中は巻き、y' ±4 はまだ一価" % cx.y_far)
    f9 = out["short_crest"].get("gg06_fig9_time") or {}
    out["fig9_check"] = dict(t_prime=GG06["fig9_t"], frame=f9.get("frame"), centre_overturned=(f9.get("centre_r2") or {}).get("overturned"),
                             far_single_valued=f9.get("far_single_valued"), overturned_full_m=f9.get("overturned_full_m"),
                             paper_ja="真ん中は巻き、y' ±4 は一価（図 9）")
    # (d)
    try:
        out["shape"] = shape_measures(cx, main, td, t_hi)
    except Exception as e:
        out["shape"] = dict(error=repr(e)[:300])
    out["elapsed_s"] = round(time.time() - t_start, 1)
    _write(out, out_dir, cx)
    return out


def _write(out, out_dir, cx):
    json.dump(_clean(out), open(os.path.join(out_dir, "ana.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    open(os.path.join(out_dir, "RESULT_ja.md"), "w", encoding="utf8").write(result_md(out, cx))


def _pct(v):
    return "—" if v is None else "%+.1f%%" % (100.0 * v)


def _n(v, fmt="%.2f"):
    return "—" if v is None else fmt % v


def result_md(o, cx):
    L = []
    name = os.path.basename(o["run_dir"].rstrip("/"))
    L.append("# FLIP46 の読み：%s（g46_analyze.py、%s）" % (name, o["date"]))
    L.append("")
    if cx.kind != "ridge":
        L.append("> この記録は %s の計算（平らな海底 %.0f m の集まる波）で、GG06 の尾根の計算ではない。道具が走ることと値の桁を確かめるための読みで、GG06 との比べに意味はない。" % (o.get("stage") or "計算", cx.h0))
        L.append("")
    L.append("- 記録：%s（コマ %d〜%d、t %.2f〜%.2f s）。粒子 %.4g m・格子 %.4g m。海底：%s（%s）。" % (
        o["run_dir"], o["frames"][0], o["frames"][1], o["t_range"][0], o["t_range"][1], o["dp"], o["vox"],
        "尾根 h' = 1 − (x' − %.4g) sech²(%.3g y')/%.3g、h0 %.4g m" % (cx.xs, cx.k, cx.n, cx.h0) if cx.kind == "ridge" else "平ら %.4g m" % cx.h0, cx.ridge_src if cx.kind == "ridge" else "記録の設定"))
    if cx.kind == "ridge" and o["bed"].get("depth_check"):
        dc = o["bed"]["depth_check"]
        L.append("- 尾根の式の確かめ：x' 19 の真ん中の水深 %.4f h0（論文 0.082）、y' ±2・±4 の勾配 %.4f・%.4f（論文 0.052・0.028）。" % (dc["centre_x19"], dc["slope_y2"], dc["slope_y4"]))
    L.append("- 静かな水面のずれ %.4f m：%s。計算の中で測った値：%s。" % (o["still_level_offset_m"], o["still_offset_source"],
                                                                 _n((o["still_offset_info"].get("online") or {}).get("value"), "%.4f m")))
    L.append("- 海底の上の余白（海底より下を水として読む）：%.3g m（%s）。" % (o["bed_margin"]["chosen_m"], "・".join(
        "%s 格子 %s" % (k, _n(v["air_frac"], "%.3f")) for k, v in o["bed_margin"]["by_margin_vox"].items())))
    L.append("")
    L.append("## (a) 真ん中（y = 0）の崩れる点（前の面に縦の接線ができた最初のコマ）")
    on = o.get("onset")
    if not on:
        st = o.get("steepest") or {}
        L.append("巻き始めなし。最も険しいコマ：t %s s、x %s m、thmax %s°。" % (_n(st.get("t")), _n(st.get("xc"), "%.1f"), _n(st.get("thmax"), "%.1f")))
    else:
        g = o["gg06_table1"]; r = g.get("rows", {})
        L.append("コマ %d、t %.3f s（t' %.3f）、頂の x %.1f m（x' %.3f）、zB %.2f m、hB %.2f m、zB/hB %.3f、thmax %.1f°。" % (
            on["frame"], on["t"], on["t_prime"], on["xc"], on["xc"] / cx.h0, on["eta_c"], on["hB"], on["zB_over_hB"], on["thmax"]))
        if r:
            L.append("")
            L.append("| 量 | この計算 | GG06 3D（k %.3g） | 差 | ±5%% の中 | GG06 2D | 2D との差 |" % cx.k)
            L.append("| --- | --- | --- | --- | --- | --- | --- |")
            for k, lab in (("t_s", "t（s、始めから）"), ("x_m", "x（m）"), ("zB_m", "zB（m）"), ("hB_m", "hB（m）"), ("zB_over_hB", "zB/hB")):
                q = r[k]
                L.append("| %s | %.3f | %.3f | %s | %s | %s | %s |" % (lab, q["value"], q["paper_3d"], _pct(q["rel"]), "入る" if q["inside_5pct"] else "外",
                                                                    _n(q.get("paper_2d"), "%.3f"), _pct(q.get("rel_2d"))))
        ip = g.get("interp_90deg")
        if ip:
            L.append("")
            L.append("前後のコマの間を補った 90° の時：t %.3f s（t' %.3f）、x %.1f m、zB %.2f m、zB/hB %.3f（GG06 との差 %s）。" % (
                ip["t_s"], ip["t_prime"], ip["x_m"], ip["zB_m"], ip["zB_over_hB"], _pct(ip["rel_zB_over_hB"])))
        if g.get("note_ja"):
            L.append("")
            L.append("注：" + g["note_ja"])
    L.append("")
    L.append("## (b) 短い頂")
    sc = o.get("short_crest") or {}
    if not sc:
        L.append("巻き始めがないので読まない。")
    if sc:
        L.append("| 時 | コマ | t（s） | t' | 真ん中 thmax | 巻いた横の範囲（全幅、m） | y ≈ %g m が一価 | 読み | 頂の高さ 真ん中 / 端（hf、m） |" % cx.y_far)
        L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        names = dict(onset="巻き始め", gg06_fig9_time="GG06 図 9 の時刻", onset_plus_fig9_delay="巻き始め + 図 9 までの遅れ", touchdown="着水")
        for k, v in sc.items():
            if "t" not in v:
                L.append("| %s | — | — | — | — | — | — | %s | — |" % (names.get(k, k), v.get("note_ja", "")))
                continue
            ce = (v.get("hf") or {}).get("crest_eta") or {}
            L.append("| %s | %d | %.3f | %.3f | %s | %s | %s | %s | %s / %s |" % (
                names.get(k, k), v["frame"], v["t"], v["t_prime"], _n((v.get("centre_r2") or {}).get("thmax"), "%.1f°"),
                _n(v.get("overturned_full_m"), "%.1f"), {True: "一価", False: "巻いた", None: "—"}[v.get("far_single_valued")],
                v.get("primary_source") or "hf だけ", _n(ce.get("centre"), "%.2f"), _n(ce.get("far"), "%.2f")))
        fc = o.get("fig9_check") or {}
        L.append("")
        L.append("GG06 図 9（t' 9.142）：真ん中が巻く = %s、y' 4 が一価 = %s（論文：巻く・一価）。" % (fc.get("centre_overturned"), fc.get("far_single_valued")))
    L.append("")
    L.append("## (c) 着水")
    td = o.get("touchdown")
    if td:
        L.append("コマ %d、t %.3f s（t' %.3f）、%s。唇の先の x %.1f m、巻き始めから %.2f s・%.1f m。%s" % (
            td["frame"], td["t"], td["t_prime"], "閉じた空気の穴" if td["by"] == "cavity" else "唇の先が静かな水面以下＋覆いかぶさり",
            td["x_point"], td["jet_time_s"], td["jet_dist_m"], td.get("gg06_estimate_ja", "")))
        j = o.get("jet") or {}
        if j.get("kind"):
            L.append("着水の 0.25 s 前の唇の先の水の向き：水平から %.1f°（%s）、u %.2f・w %.2f m/s。" % (j["angle_from_horizontal_deg"], j["kind"], j["u"], j["w"]))
    else:
        L.append("記録の中で着水なし。")
    L.append("")
    L.append("## (d) 形（原画と同じ物差し、y = 0 の断面）")
    sh = o.get("shape") or {}
    if sh.get("table"):
        fr = sh["frames"]
        cols = list(fr.keys())
        L.append("コマ：" + "、".join("%s %d" % (c, fr[c]) for c in cols) + "。" + sh["rule_ja"] + "。")
        L.append("")
        L.append("| 量 | 原画 cn | 原画 drawn | " + " | ".join(cols) + " |")
        L.append("| --- | --- | --- | " + " | ".join("---" for _ in cols) + " |")
        for k, r in sh["table"].items():
            L.append("| %s | %s | %s | %s |" % (r["label_ja"], _n(r["print_cn"], "%.3f"), _n(r["print_drawn"], "%.3f"), " | ".join(_n(r.get(c), "%.3f") for c in cols)))
        L.append("")
        L.append(sh["note_ja"])
    else:
        L.append("読めない：%s" % sh.get("error"))
    L.append("")
    if o.get("notes"):
        L.append("## 注")
        for s in o["notes"]:
            L.append("- " + s)
        L.append("")
    L.append("読みの所要 %.1f s。値の全部は ana.json。" % (o.get("elapsed_s") or 0.0))
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    rd = sys.argv[1]
    opt = parse_opt(sys.argv[2:])
    r = analyze(rd, opt)
    keep = ("run_dir", "out_dir", "still_level_offset_m", "still_offset_source", "bed_margin", "onset", "onset_interp", "gg06_table1", "touchdown",
            "fig9_check", "elapsed_s")
    print(json.dumps(_clean({k: r.get(k) for k in keep}), ensure_ascii=False, indent=1)[:8000])
    sc = r.get("short_crest") or {}
    for k, v in sc.items():
        print("short_crest", k, {q: v.get(q) for q in ("frame", "t", "primary_source", "overturned_full_m", "far_single_valued")},
              "centre", v.get("centre_r2"))
    sh = r.get("shape") or {}
    if sh.get("table"):
        print("shape frames", sh["frames"])
        for k, row in sh["table"].items():
            print("  %-22s cn %8s drawn %8s | %s" % (k, row["print_cn"], row["print_drawn"], {c: row.get(c) for c in sh["frames"]}))
