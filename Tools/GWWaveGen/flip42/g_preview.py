# -*- coding: utf-8 -*-
"""FLIP42 R2 の段：利用者に早く見せる横からの動画 1 本と、巻き始めにそろえた時刻の断面の並び 1 枚（計画 §6 の見せ方）。
g_video.py の水の塗り方（断面の記録のある所と時刻は板の真ん中の水面の場、それ以外は一番上の水面の高さ）をそのまま使う。
縦横同じ縮尺、高さは静かな水面から、10 m の目盛り、静かな水面の点線、字は日本語。
使い方:
  py -3.10 g_preview.py side  <run_id> <out.mp4> [--parent=<run_id>] [--title=...]
  py -3.10 g_preview.py strip <out.png> <run_id> [<run_id> ...]   （計算ごとに 1 段。同じ時刻の位置で上下に並べる）
動画：上の段＝広い窓（造波板から 300〜750 m）、下の段＝頂の周りの窓（巻き始めの頂の位置 −0.35〜+0.45 波長）。
  114.5 s（t_b − 6 Tc）から巻き始めの 1.5 Tc 前までは実時間、そこから終わりまでは半分の速さ（画面に書く）。
"""
import sys, os, json, math, subprocess
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42")
import g_analyze as A
import g_video as V

W, H = 1920, 1080
BG, WATER, TXT, SUB, RED = V.BG, V.WATER, V.TXT, V.SUB, (200, 40, 40)

# 印の字。既定は 10/10 に利用者へ出した版（preview/R2_first_side.mp4・R2_first_strip.png）と同じ。
# 字だけを直した _v2 は g_relabel_v2.py がこの辞書を差し替えて描く（描き方・窓・数は変えない）。
LAB = {"dk_x": "実験の着水 584.5 m（D&K）",  # 場所の印（D&K の表 3.1 の x_ob を 70 倍）
       "dk_t": "実験の着水",                 # 時間の帯の印（同じ表の t_ob を 70 倍）
       "touch_t": "着水",                    # 時間の帯の印（この計算の「着水」の決まりを満たした時）
       "touch_panel": "着水"}                # 断面の並びの 8 枚目の題


class Data2(V.Data):
    def __init__(self, rid, parent=None):
        self.rid = rid
        self.P = A.plan(); self.C = A.comps_full(self.P)
        self.cfg = json.load(open(os.path.join(A.ROOT, rid, "cfg.json"), encoding="utf8"))
        self.shape = json.load(open(os.path.join(A.ROOT, rid, "shape.json"), encoding="utf8"))
        self.D = A.load_hf(rid)
        self.S = A.load_sec(rid)
        self.off = self.shape["still_level_offset_m"]
        self.xp = self.cfg["parms"]["x_p"]
        self.mid = self.D["eta"].shape[1] // 2
        self.fidx = {int(f): i for i, f in enumerate(self.D["frames"])}
        self.sidx = {int(f): i for i, f in enumerate(self.S["frames"])} if self.S else {}


def ref_of(d):
    on = d.shape.get("onset")
    if on:
        return on["t"], on["xc_rel"], "巻き始め"
    rows = [r for r in d.shape["rows"] if np.isfinite(r.get("steep", np.nan))]
    r = max(rows, key=lambda q: q["steep"])
    return r["t"], r["xc_rel"], "最も険しくなった時刻"


def runtxt(d):
    dp = d.cfg["parms"]["dp"]
    nb = "粒子の帯 %.0f m" % (d.cfg["parms"]["band_vox"] * 2 * dp) if d.cfg["solver"]["donarrowband"] else "粒子の帯なし"
    extra = ""
    if d.cfg["parms"].get("cfl", 1.0) != 1.0 or d.cfg["parms"].get("minsub", 1) != 1:
        extra = "、時間の刻みを半分（CFL %.2g・最小小刻み %d）" % (d.cfg["parms"]["cfl"], int(d.cfg["parms"]["minsub"]))
    return "粒子 %.3g m（格子 %.3g m）、%s%s" % (dp, 2 * dp, nb, extra)


def side(rid, outp, parent=None, title=""):
    d = Data2(rid, parent)
    C, P = d.C, d.P
    Tc, Lc = C["Tc"], C["Lc"]
    tref, xref, refname = ref_of(d)
    tou = d.shape.get("touchdown")
    t_end = P["tank"]["t_end"]
    t0 = max(C["tb"] - 6 * Tc, (d.D["frames"].min() - 1) / 24.0)
    t_slow = tref - 1.5 * Tc
    frames = [int(f) for f in d.D["frames"] if (f - 1) / 24.0 >= t0 - 1e-9]
    head = "FLIP42 %s：Rapp & Melville の巻き波の組（S 0.352）を 70 倍。%s。力は重力だけ（風なし）。%s" % (rid, runtxt(d), title)
    sub = "縦横同じ縮尺。高さは静かな水面から（点線）。位置は造波板からの距離（m）。濃い青＝水（板の真ん中の断面の水面）。赤い縦棒＝10 m。"
    marks = [(C["xb"], "線形の焦点 592 m"), (P["full"]["xob_DK"], LAB["dk_x"])]
    tmk = [(P["full"]["tob_DK"], LAB["dk_t"]), (C["tb"], "線形の焦点")]
    if d.shape.get("onset"):
        tmk.append((tref, "巻き始め"))
    if tou:
        tmk.append((tou["t"], LAB["touch_t"]))
    xa0, xa1 = 300.0, 750.0
    xc0, xc1 = xref - 0.35 * Lc, xref + 0.45 * Lc
    enc = V.encode(outp, 24)
    nfr = 0

    def tbar(dr, t):
        bx0, bx1, by = 60, W - 60, H - 52
        dr.rectangle([bx0, by, bx1, by + 8], fill=(225, 225, 222))
        dr.rectangle([bx0, by, bx0 + (bx1 - bx0) * (t - t0) / (t_end - t0), by + 8], fill=(60, 80, 110))
        for q, (tm, lab) in enumerate(sorted(tmk)):
            if t0 <= tm <= t_end:
                xx = bx0 + (bx1 - bx0) * (tm - t0) / (t_end - t0)
                dr.line([(xx, by - 4), (xx, by + 14 + 14 * (q % 2))], fill=RED, width=2)
                dr.text((xx + 3, by + 12 + 14 * (q % 2)), lab, fill=RED, font=V.font(13))
        dr.text((bx0, by - 22), "%.1f s" % t0, fill=SUB, font=V.font(14)); dr.text((bx1 - 50, by - 22), "%.1f s" % t_end, fill=SUB, font=V.font(14))

    for f in frames:
        t = (f - 1) / 24.0
        slow = t >= t_slow
        im = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(im)
        dr.text((40, 12), head, fill=TXT, font=V.font(20, True))
        dr.text((40, 44), sub, fill=SUB, font=V.font(16))
        dr.text((40, 72), "t = %.2f s（%sから %+.2f s）" % (t, refname, t - tref), fill=TXT, font=V.font(24, True))
        dr.text((W - 330, 72), "再生：%s" % ("半分の速さ" if slow else "実時間"), fill=RED if slow else SUB, font=V.font(22, True))
        h1 = V.panel(im, dr, d, f, (40, 140, W - 40), xa0, xa1, -16, 22, "広い窓：造波板から %d〜%d m（群が集まり、険しくなる所）" % (xa0, xa1), marks=marks)
        V.panel(im, dr, d, f, (40, 140 + h1 + 64, W - 40), xc0, xc1, -14, 17,
                "頂の周りの窓：%.0f〜%.0f m（%sの頂 %.0f m の −0.35〜+0.45 波長）" % (xc0, xc1, refname, xref), marks=marks)
        tbar(dr, t)
        b = im.tobytes()
        enc.stdin.write(b); nfr += 1
        if slow:
            enc.stdin.write(b); nfr += 1
    enc.stdin.close(); enc.wait()
    print("saved", outp, "frames", nfr, "seconds", nfr / 24.0, "tref", tref, "xref", xref)


def strip(outp, rids, parents=None):
    ds = [Data2(r) for r in rids]
    C, P = ds[0].C, ds[0].P
    Tc, Lc = C["Tc"], C["Lc"]
    labs = ["−0.3 Tc", "−0.2 Tc", "−0.1 Tc", "巻き始め", "+0.1 Tc", "+0.2 Tc", "+0.3 Tc", LAB["touch_panel"]]
    ncol = 2
    pw = 930
    X0r, X1r = -0.3 * Lc, 0.42 * Lc
    Y0, Y1 = -10.0, 14.0
    s = pw / (X1r - X0r)
    ph = int(round((Y1 - Y0) * s))
    rowh = ph + 74
    nrow_per = 4
    Wd = 40 + ncol * (pw + 20) + 20
    Hd = 110 + len(ds) * (nrow_per * rowh + 46) + 30
    im = Image.new("RGB", (Wd, Hd), BG); dr = ImageDraw.Draw(im)
    dr.text((30, 12), "巻き始めにそろえた時刻の断面（縦横同じ縮尺、高さは静かな水面から、赤い縦棒＝10 m）。Tc = %.2f s" % Tc, fill=TXT, font=V.font(22, True))
    dr.text((30, 48), "Rapp & Melville の巻き波の組（S 0.352）を 70 倍、力は重力だけ。窓は各計算の巻き始めの頂の位置の −0.3〜+0.42 波長で、全部のコマで同じ。"
            "数字は η_c（静かな水面から頂）と H（頂から前の谷）。", fill=SUB, font=V.font(15))
    y = 100
    for d in ds:
        sh = d.shape
        on = sh.get("onset"); tou = sh.get("touchdown")
        tref, xref, refname = ref_of(d)
        dr.text((30, y), "%s：%s。基準＝%s %.2f s・頂 %.0f m" % (d.rid.replace("R5p", "R5'"), runtxt(d), refname, tref, xref), fill=TXT, font=V.font(18, True))
        y += 34
        rows = d.shape["rows"]; tt = np.array([r["t"] for r in rows])
        for q in range(8):
            if q < 7:
                tq = tref + [-0.3, -0.2, -0.1, 0, 0.1, 0.2, 0.3][q] * Tc
            else:
                if not tou:
                    continue
                tq = tou["t"]
            k = int(np.argmin(abs(tt - tq)))
            r = rows[k]; f = int(r["frame"])
            if f not in d.fidx:
                continue
            col, row = q % ncol, q // ncol
            px0 = 40 + col * (pw + 20); py0 = y + row * rowh + 26
            V.panel(im, dr, d, f, (px0, py0, px0 + pw), xref + X0r, xref + X1r, Y0, Y1, "", marks=[])
            lab = "%s（%.2f s）" % (labs[q], r["t"])
            dr.text((px0, py0 - 24), lab, fill=TXT, font=V.font(16, True))
            if r.get("eta_c") is not None:
                dr.text((px0 + pw - 175, py0 - 22), "η_c %.1f m・H %.1f m" % (r["eta_c"], r["H"]), fill=SUB, font=V.font(14))
        y += nrow_per * rowh + 46
    im.save(outp)
    print("saved", outp)


if __name__ == "__main__":
    mode = sys.argv[1]
    opt = dict(q[2:].split("=", 1) for q in sys.argv if q.startswith("--"))
    pos = [q for q in sys.argv[2:] if not q.startswith("--")]
    if mode == "side":
        side(pos[0], pos[1], opt.get("parent"), opt.get("title", ""))
    else:
        strip(pos[0], pos[1:])
