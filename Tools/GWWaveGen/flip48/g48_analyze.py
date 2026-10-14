# -*- coding: utf-8 -*-
"""FLIP48：計算の記録を読む（py -3.10 -B、numpy・scipy・scikit-image）。2026-10-15 新しく書いた。
FLIP46 の g46_analyze.py（Tools/GWWaveGen/flip46、変えていない）をこの起動の中だけ読み替えて使う（ファイルは書き換えない）：
  - 海底：Ctx48.bed_z = g48_common.bed_z（cfg の bed：尾根 sech²(k y/h0)・真ん中 1:s・棚 h_sh）。断面の海底を埋める所・静かな水面の窓・
    海底の上の余白・形の量の水の格子は、全部この式を通る。
  - GG06 の表 1 と比べない：Ctx48.k を nan にする（compare_gg06 は「表に値がない」と書くだけになる）。本当の k は Ctx48.k48。
    「GG06 図 9 の時刻」（t' 9.142 = 12.04 s）の行は FLIP48 には意味がない（巻き始め + 1.65 s の行は巻きの広がりの目安として使える）。
  - 出力の置き場所：A46.B46 を Unity/Build/FLIP48 に（guard_out・default_out は呼ぶ時に読む）。FLIP48 の外には書かない。
  - y_far（横の端の行）：既定 W − 1 m（R1 は 84 m）。孤立波の値（H0・x0・c）は cfg の solitary（g48_cfg.py が書く）から。
2026-10-15 R3 の試し（plan/campaign_R3_judge.json）のために足した：
  - 海底の R3 の選び（先細り・溝・段）も g48_common.bed_spec で読む（cfg の bed の鍵、なければ CTRL の parms）。注と RESULT_ja.md の頭に書く。
  - 静かな水面のずれの「静かな所」（g46_analyze の quiet_x：孤立波の前の裾が 5 mm より低い x）を、谷のある波（cfg の wave.kind nwave）では
    谷の前の裾も 5 mm より低い所に下げる：x ≥ x0 + d + c0 (t − t0) + acosh(√(β a/0.005))/k_s（c0 = √(g h0) は棚の上の遅い速さより速いので安全側）。
    これがないと谷の裾（x 277〜300 m で −5〜−14 mm【計算】）を静かな水面に数える。谷が無ければ前と同じ。
使い方：py -3.10 -B g48_analyze.py <記録の置き場所> [g46_analyze と同じ引数：--t0= --t1= --Lc= --yfar= --no-mesh]
出す物：<記録>/ana.json・RESULT_ja.md（g46_analyze と同じ形。頭に FLIP48 の注を足す）
"""
import os, sys, json, math

sys.dont_write_bytecode = True
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip46")
sys.path.insert(0, _HERE)
import numpy as np                  # noqa: E402
import g48_common as GC             # noqa: E402
import g46_analyze as A46           # noqa: E402

for _nm in ("Ctx", "B46", "guard_out", "default_out", "analyze", "lateral_rows_r4", "compare_gg06"):
    if not hasattr(A46, _nm):
        raise SystemExit("g46_analyze.py に %s がない（FLIP46 の道具が変わった。g48_analyze.py を直す）" % _nm)
A46.B46 = GC.B48                    # この起動の中だけ：出力の置き場所を FLIP48 に


class Ctx48(A46.Ctx):
    """g46_analyze.Ctx の海底を FLIP48 の尾根と棚にした物。"""

    def __init__(self, rd, opt=None):
        opt = dict(opt or {})
        cp = os.path.join(rd, "cfg.json")
        cfg = json.load(open(cp, encoding="utf8")) if os.path.exists(cp) else {}
        if not cfg.get("bed"):
            rr = sorted(f for f in os.listdir(rd) if f.startswith("run_c") and f.endswith(".json")) if os.path.isdir(rd) else []
            if rr:
                cfg["bed"] = json.load(open(os.path.join(rd, rr[0]), encoding="utf8")).get("bed")
        self.bed48 = GC.bed_spec(cfg if cfg.get("bed") else None, parms=(cfg.get("parms") or {}))
        self.wave48 = cfg.get("wave") if isinstance(cfg.get("wave"), dict) else None     # 谷のある波（super の still_offset が quiet_x を呼ぶ前に置く）
        self.k48 = self.bed48["k"]
        opt.setdefault("bed", "ridge")
        W = float((cfg.get("parms") or {}).get("W", GC.W_MAIN))
        opt.setdefault("yfar", str(max(W - 1.0, 0.5)))
        super().__init__(rd, opt)
        self.k = float("nan")                        # GG06 の表 1 と比べない（compare_gg06 が表を引かない）
        self.ridge_src = "FLIP48 の尾根と棚：k %g・x_toe %g m・1:%g・棚 %g m（g48_common.bed_z）" % (
            self.k48, self.bed48["x_toe"], self.bed48["s"], self.bed48["shelf_h"])
        if GC.bed_kind(self.bed48) != "ridge_shelf":
            self.ridge_src += "。R3 の選び（%s）：%s" % (GC.bed_kind(self.bed48), GC.bed_formula(self.bed48))
            self.notes.insert(0, "FLIP48 R3：海底の種類 %s。式 %s。値 %s" % (GC.bed_kind(self.bed48), GC.bed_formula(self.bed48),
                                                                    {k: v for k, v in self.bed48.items() if k in GC.BED_EXTRA_DEFAULTS}))
        if self.wave48 and self.wave48.get("kind") == "nwave":
            self.notes.insert(0, "FLIP48 R3：初めの波は Tanaka の頂 ＋ 前の谷 β %s（%.2f m、d %.1f m、k_s %.5f /m）。定常な解ではない。"
                                 "静かな水面のずれは谷の前の裾も 5 mm より低い所で読んだ（quiet_x）" % (
                                     self.wave48.get("beta"), self.wave48.get("trough_amp_m", 0.0), self.wave48.get("d_m", 0.0), self.wave48.get("k_s", 0.0)))
        self.notes.insert(0, "FLIP48：海底は z_b = −max(%g, %g − max(x − %g, 0)/%g · sech²(%g y/%g))（g48_common.bed_z）。表の k は GG06 と比べないよう nan にした（本当の k = %g）。"
                             "「GG06 図 9 の時刻」の行は FLIP48 には意味がない" % (
                                 self.bed48["shelf_h"], self.bed48["h0"], self.bed48["x_toe"], self.bed48["s"], self.k48, self.bed48["h0"], self.k48))

    def bed_z(self, x, y=0.0):
        if not hasattr(self, "bed48"):
            return super().bed_z(x, y)
        return GC.bed_z(x, y, **self.bed48)

    def quiet_x(self, t):
        """孤立波の頂の前の裾（g46_analyze）と、谷のある波なら谷の前の裾の、どちらも 5 mm より低い x。"""
        x = super().quiet_x(t)
        w = getattr(self, "wave48", None)
        if w and w.get("kind") == "nwave":
            amp = float(w.get("trough_amp_m") or 0.0); ks = float(w["k_s"])
            if amp > 0.005:
                xt = self.xc0 + float(w["d_m"]) + float(w.get("c0_trough_mps") or GC.C0_LIN) * (t - self.t_off) + math.acosh(math.sqrt(amp / 0.005)) / ks
                x = max(x, xt)
        return x


A46.Ctx = Ctx48                     # この起動の中だけ：analyze() が呼ぶ時に読む名前


def analyze(rd, opt=None):
    opt = dict(opt or {})
    o = A46.analyze(rd, opt)
    p = os.path.join(o["out_dir"], "RESULT_ja.md")
    if os.path.exists(p):
        s = open(p, encoding="utf8").read()
        cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8")) if os.path.exists(os.path.join(rd, "cfg.json")) else {}
        b = cfg.get("bed") or {}
        sol = cfg.get("solitary") or {}
        head = ("> FLIP48（g48_analyze.py が g46_analyze.py を読み替えて使った）：尾根 k %s・真ん中 1:%s・棚 %s m、孤立波 H0/h0 %s（Tanaka の厳密な解、まっすぐな頂）。"
                "下の「GG06」と書いた比べ・図 9 の行は FLIP48 には当てはまらない。A 字の盛り上がりの判定は g48_peak_metrics.py の PEAK_ja.md。\n\n") % (
            b.get("k"), b.get("s"), b.get("h_sh"), sol.get("H0_nd"))
        if b.get("kind") not in (None, "ridge_shelf") or cfg.get("wave"):
            w = cfg.get("wave") or {}
            head = head.rstrip("\n") + ("\n> R3 の試し：海底 %s（%s）%s。\n\n" % (
                b.get("kind"), b.get("formula"), ("、初めの波に前の谷 β %s（定常な解ではない）" % w.get("beta")) if w.get("kind") == "nwave" else ""))
        s = s.replace("# FLIP46 の読み", "# FLIP48 の読み", 1)
        lines = s.split("\n", 2)
        open(p, "w", encoding="utf8").write(lines[0] + "\n\n" + head + (lines[2] if len(lines) > 2 else ""))
    return o


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    rd = os.path.abspath(sys.argv[1])
    opt = A46.parse_opt(sys.argv[2:])
    r = analyze(rd, opt)
    keep = ("run_dir", "out_dir", "still_level_offset_m", "still_offset_source", "onset", "onset_interp", "touchdown", "elapsed_s")
    print(json.dumps(A46._clean({k: r.get(k) for k in keep}), ensure_ascii=False, indent=1))
