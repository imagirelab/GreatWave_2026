# -*- coding: utf-8 -*-
"""設計28：入力条件の変更（交差角・波長）と較正の掃引（噴流の始まり・広がり・峰の速さ・減速の始まり）と、美術の誘導の切り替えごとの
t* の差を、設計27 の生成器（読むだけ）で測って表と図にする。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/ds28/ds28_inputs_run.py [--jobs 6] [--only <名前,...>] [--figs-only]
出力（Git 対象外）：Unity/Build/Design/28/inputs/
    ds28_inputs_metrics.json   1 本ごとの設定と測定（ds28_inputs_measure.py）
    ds28_inputs_table.md       表（日本語）
    ds28_inputs_series.npz     図のための時系列（主断面・峰の行の断面など）
    fig_ds28_inputs_sections.png   入力の違いごとの主断面・峰の行の断面（段階 a・b・c・d・t*、灰 = K*）
    fig_ds28_calib_sections.png    較正の掃引の同じ図
    fig_ds28_crest_physics.png     物理の頂の高さ（波峰線に沿った t* の高さと、主役の峰の育ち方）と K*・設計27 の表
    fig_ds28_inputs_outline.png    原画視点の上の輪郭（K* と入力の違い）
    --refresh-tstar で t* の測定（K* との差・輪郭・E1）だけを測り直す（段階と関門の時系列はそのまま）。
numpy と Pillow だけ。1 本は 1〜2 分（並列に走らせる）。Unity は使わない。
続き：ds28_inputs_summary.py（要点の JSON）、ds28_inputs_package.py と ds27/run_ds27_unity.ps1 と ds28_inputs_unity_sheet.py（任意の Unity の静止画）。
"""
import argparse
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "2")
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(REPO, "Unity", "Build", "Design", "28", "inputs")

SHAPE_SWITCHES = ["ds_body_narrow", "ds_back_steep", "ds_tube_shape", "ds_claws", "ds_lip_target_kstar", "ds_farwall_hold"]
PHYS = dict(base="art_off", crest="phys", jet_cos2=True, anchor_to_kstar=False)   # 設計28 のレビュー対応：設計27 の錨の K* への ease-in を切る


def run_list():
    R = []
    add = lambda name, group, cfg, label, tstar_only=False: R.append(dict(name=name, group=group, cfg=cfg, label=label, tstar_only=tstar_only))
    add("base_art_on", "base", dict(base="art_on"), "設計27 入れた版（既定）")
    add("base_art_off_kstar", "base", dict(base="art_off"), "設計27 切った版（K* の頂の高さ＝塔を受け継ぐ）")
    for lam in (195.0, 250.0):
        for dth in (0.0, 60.0, 120.0):
            add("in_d%d_l%d" % (dth, lam), "inputs", dict(PHYS, dtheta_deg=dth, lam_p=lam), "物理だけ\nΔθ %d°・λp %d m" % (dth, lam))
    for lam in (195.0, 250.0):
        for dth in (0.0, 60.0, 120.0):
            add("ing_d%d_l%d" % (dth, lam), "inputs_growth", dict(PHYS, dtheta_deg=dth, lam_p=lam, growth="phys"),
                "物理だけ＋物理の育ち方\nΔθ %d°・λp %d m" % (dth, lam))
    cal = [("on20", dict(onset_s=2.0), "噴流の始まり 2.0 s"), ("on28", dict(onset_s=2.8), "噴流の始まり 2.8 s"),
           ("peel30", dict(peel=30.0), "広がり 30 m/s"), ("c016", dict(c0=16.0), "c0 16 m/s"),
           ("lead18", dict(decel_lead_s=1.8), "減速を噴流の 1.8 s 前（段階 a）から")]
    for key, c, lab in cal:
        add("cal_on_" + key, "calib_on", dict(dict(base="art_on"), **c), "入れた版\n" + lab)
        add("cal_ph_" + key, "calib_phys", dict(dict(PHYS), **c), "物理だけ\n" + lab)
    for s in SHAPE_SWITCHES:
        add("sw_tower_plus_" + s, "switch", dict(base="art_off", switches={s: True}), "塔（K* の頂）＋" + s, tstar_only=True)
        add("sw_on_minus_" + s, "switch", dict(base="art_on", switches={s: False}), "入れた版 − " + s, tstar_only=True)
        add("sw_phys_plus_" + s, "switch", dict(PHYS, switches={s: True}), "物理だけ＋" + s, tstar_only=True)
    add("sw_on_phys_crest", "switch", dict(base="art_on", crest="phys"), "入れた版から塔だけ外す（物理の頂の高さ）", tstar_only=True)
    return R


def _work(item):
    import ds28_inputs_measure as MS
    ctx = MS.Context()
    t0 = time.time()
    try:
        R, S = MS.measure(ctx, item["cfg"], tstar_only=item["tstar_only"], log=lambda *a: None)
    except Exception as ex:  # 1 本の失敗で全体を止めない（記録する）
        import traceback
        return item["name"], dict(name=item["name"], group=item["group"], label_ja=item["label"], error=repr(ex), trace=traceback.format_exc()[-2000:]), {}, time.time() - t0
    top = R.pop("tstar_top_px")
    R.update(name=item["name"], group=item["group"], label_ja=item["label"], tstar_only=item["tstar_only"])
    if S is None:
        S = {}
    S["top_run"] = top["run"]
    S["top_kstar"] = top["kstar"]
    return item["name"], R, {k: np.asarray(v) for k, v in S.items()}, time.time() - t0


# ---------------------------------------------------------------- 図
def font(sz):
    from PIL import ImageFont
    return ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc", sz)


def crest_col(A, Y, hi):
    cols = np.arange(len(Y))
    return int(np.argmax(np.where(cols <= hi, Y, -np.inf)))


def draw_sections(img, box, secs, kst, hi, xr=(-40.0, 30.0), yr=(-6.0, 28.0), title=None, fs=13):
    """box に、主断面（紺）・峰の行（橙）の断面を、それぞれの頂の a をそろえて等倍で描く。灰は t* の K*（濃い灰 = 主断面、薄い灰 = 峰の行）。"""
    from PIL import ImageDraw
    x0, y0, w, h = box
    d = ImageDraw.Draw(img)
    s = min(w / (xr[1] - xr[0]), h / (yr[1] - yr[0]))

    def P(a, y):
        return (x0 + (a - xr[0]) * s, y0 + h - (y - yr[0]) * s)
    d.rectangle([x0, y0, x0 + w - 1, y0 + h - 1], outline=(200, 200, 200), fill=(250, 250, 250))
    for gx in range(int(math.ceil(xr[0] / 10.0)) * 10, int(xr[1]) + 1, 10):
        d.line([P(gx, yr[0]), P(gx, yr[1])], fill=(230, 230, 230))
    for gy in range(0, int(yr[1]) + 1, 10):
        d.line([P(xr[0], gy), P(xr[1], gy)], fill=(215, 215, 215) if gy else (150, 170, 200), width=1 if gy else 2)
    cols = [((150, 150, 150), (60, 60, 140)), ((200, 200, 200), (230, 120, 0))]
    for k, (key, hikey) in enumerate((("main", "main"), ("peak", "peak"))):
        KA, KY = kst[key]
        j = crest_col(KA, KY, hi[hikey])
        pts = [P(a - KA[j], y) for a, y in zip(KA, KY) if xr[0] - 5 < a - KA[j] < xr[1] + 5]
        d.line(pts, fill=cols[k][0], width=1)
    for k, key in enumerate(("main", "peak")):
        if secs.get(key) is None:
            continue
        A, Y = secs[key]
        j = crest_col(A, Y, hi[key])
        pts = [P(a - A[j], y) for a, y in zip(A, Y) if xr[0] - 5 < a - A[j] < xr[1] + 5]
        d.line(pts, fill=cols[k][1], width=2)
    if title:
        d.text((x0 + 5, y0 + 3), title, fill=(30, 30, 30), font=font(fs))


def sections_figure(path, names, M, SER, ks, heading):
    from PIL import Image, ImageDraw
    W, H = 330, 190
    lab_w = 250
    stages = ["a", "b", "c", "d", "tstar"]
    img = Image.new("RGB", (lab_w + len(stages) * W, 70 + len(names) * (H + 26) + 90), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((6, 6), heading, fill=(0, 0, 0), font=font(18))
    for k, s in enumerate(stages):
        d.text((lab_w + k * W + 6, 40), {"a": "a 丸い峰", "b": "b 尖った峰（塔）", "c": "c 鉛直の壁・噴流の始まり", "d": "d 先が前へ返る", "tstar": "t*"}[s],
               fill=(0, 0, 0), font=font(16))
    mr, pr = ks.main_row, ks.peak_row
    kst = dict(main=(ks.A[mr], ks.Y[mr]), peak=(ks.A[pr], ks.Y[pr]))
    hi = dict(main=int(ks.crest_hi[mr]), peak=int(ks.crest_hi[pr]))
    y = 70
    for nm in names:
        R = M[nm]
        S = SER[nm]
        lab = R["label_ja"]
        g15 = R["gates"]["P15"]["peak_192"]
        # 折り返し
        lines = []
        for part in lab.split("\n"):
            while len(part) > 16:
                lines.append(part[:16])
                part = part[16:]
            if part:
                lines.append(part)
        tr = R["tstar"]
        lines.append("t* の差 RMS %.2f m" % tr["rms_m"])
        lines.append("主断面 RMS %.2f m" % tr["main_row_rms_m"])
        lines.append("輪郭 平均 %.0f px" % (tr["painting_upper_outline"]["mean_abs_px"] or 0))
        d.text((6, y + 4), "\n".join(lines), fill=(0, 0, 0), font=font(14))
        t60 = S["t60"]
        for k, s in enumerate(stages):
            if s == "tstar":
                tau, note = 0.0, "τ 0"
            else:
                tau = g15["tau"][s]
                note = "τ %+.2f s（表 %+.2f）" % (tau, g15["table"][s]) if tau is not None else "未成立（表の τ %+.2f で描く）" % g15["table"][s]
                if tau is None:
                    tau = g15["table"][s]
            i = int(np.argmin(np.abs(t60 - tau)))
            secs = dict(main=(S["sec_main"][i, 0], S["sec_main"][i, 1]), peak=(S["sec_peak"][i, 0], S["sec_peak"][i, 1]))
            th = S["theta_peak"][i]
            lo = S["Lo_peak"][i] / max(S["H_peak"][i], 1e-9)
            ttl = "%s　θc %s°・Lo %.2fH" % (note, ("%.0f" % th) if np.isfinite(th) else "—", lo if np.isfinite(lo) else float("nan"))
            draw_sections(img, (lab_w + k * W + 2, y, W - 4, H), secs, kst, hi, title=ttl, fs=12)
        y += H + 26
    notes = ["紺＝主断面（行 159、c = 0 m）、橙＝K* の峰で最も高い巻きの行（行 192、c = +3.85 m）、濃い灰・薄い灰＝t* の K*（同じ 2 行）。各行の頂の a をそろえて等倍、格子 10 m。",
             "段階の τ は、この 1 本の峰の行（行 192）で設計26 §3.1 の判定（ds27_gates.STAGE）を初めて満たした時刻。成り立たない段階は表の τ で描いた。題の θc・Lo は峰の行。",
             "numpy の生成器（設計27 の ds27_model を読むだけで継承した ds28_inputs_model）の断面そのもの。Unity の描画ではない。"]
    for i_, t in enumerate(notes):
        d.text((6, y + 4 + 22 * i_), t, fill=(0, 0, 0), font=font(14))
    img.save(path)


def crest_physics_figure(path, M, SER, ks):
    from PIL import Image, ImageDraw
    sys.path.insert(0, os.path.join(HERE, "..", "ds27"))
    from ds28_inputs_model import CarrierCrest, c0_from_inputs
    img = Image.new("RGB", (1560, 640), (255, 255, 255))
    d = ImageDraw.Draw(img)
    cols = {(0, 195): (40, 120, 220), (60, 195): (20, 40, 120), (120, 195): (200, 40, 40), (0, 250): (120, 180, 240), (60, 250): (100, 110, 170), (120, 250): (240, 140, 140)}
    # 左：t* の行ごとの頂の高さ
    bx = (70, 60, 640, 470)
    xr, yr = (-35.0, 16.0), (0.0, 25.0)

    def P(x, y, b=bx, xr=xr, yr=yr):
        return (b[0] + (x - xr[0]) / (xr[1] - xr[0]) * b[2], b[1] + b[3] - (y - yr[0]) / (yr[1] - yr[0]) * b[3])
    d.rectangle([bx[0], bx[1], bx[0] + bx[2], bx[1] + bx[3]], outline=(180, 180, 180))
    for gx in range(-30, 16, 5):
        d.line([P(gx, yr[0]), P(gx, yr[1])], fill=(235, 235, 235))
        d.text((P(gx, 0)[0] - 10, bx[1] + bx[3] + 4), "%d" % gx, fill=(0, 0, 0), font=font(13))
    for gy in range(0, 26, 5):
        d.line([P(xr[0], gy), P(xr[1], gy)], fill=(235, 235, 235))
        d.text((bx[0] - 30, P(0, gy)[1] - 8), "%d" % gy, fill=(0, 0, 0), font=font(13))
    c = ks.c
    m = (c >= xr[0]) & (c <= xr[1])
    d.line([P(x, y) for x, y in zip(c[m], ks.Hrow[m])], fill=(150, 150, 150), width=4)
    for (dth, lam), col in cols.items():
        cc = CarrierCrest(dth, lam)
        H = cc.height(cc.envelope_c(c[m]))
        d.line([P(x, y) for x, y in zip(c[m], H)], fill=col, width=2)
    d.text((bx[0], 10), "t* の行ごとの頂の高さ H(c)（m）：灰（太）＝K*、色＝物理（分散集中の包絡＋2 次）", fill=(0, 0, 0), font=font(16))
    d.text((bx[0] + 250, bx[1] + bx[3] + 22), "波峰線方向の位置 c（m、主断面 = 0）", fill=(0, 0, 0), font=font(14))
    ly = bx[1] + 10
    for (dth, lam), col in cols.items():
        d.line([(bx[0] + 20, ly + 8), (bx[0] + 50, ly + 8)], fill=col, width=3)
        d.text((bx[0] + 56, ly), "Δθ %d°・λp %d m" % (dth, lam), fill=(0, 0, 0), font=font(13))
        ly += 18
    # 右：主役の峰の育ち方
    bx2 = (800, 60, 640, 470)
    xr2, yr2 = (-10.5, 0.2), (0.0, 1.05)

    def Q(x, y):
        return P(x, y, bx2, xr2, yr2)
    d.rectangle([bx2[0], bx2[1], bx2[0] + bx2[2], bx2[1] + bx2[3]], outline=(180, 180, 180))
    for gx in range(-10, 1, 1):
        d.line([Q(gx, yr2[0]), Q(gx, yr2[1])], fill=(235, 235, 235))
        d.text((Q(gx, 0)[0] - 8, bx2[1] + bx2[3] + 4), "%d" % gx, fill=(0, 0, 0), font=font(13))
    for gy in np.arange(0, 1.01, 0.2):
        d.line([Q(xr2[0], gy), Q(xr2[1], gy)], fill=(235, 235, 235))
        d.text((bx2[0] - 34, Q(0, gy)[1] - 8), "%.1f" % gy, fill=(0, 0, 0), font=font(13))
    taus = np.linspace(-10.5, 0.0, 211)
    for lam, col in ((195.0, (20, 40, 120)), (250.0, (100, 110, 170))):
        cc = CarrierCrest(60.0, lam)
        z = cc.hero_zeta(np.array([0.0]), taus, c0_from_inputs(60.0, lam))
        Hh = cc.height(z)[0]
        Hh = Hh / Hh[-1]
        d.line([Q(x, y) for x, y in zip(taus, Hh)], fill=col, width=2)
    if "base_art_on" in SER and "H_peak" in SER["base_art_on"]:
        S = SER["base_art_on"]
        t60 = S["t60"]
        mm = t60 >= xr2[0]
        Hn = S["H_peak"] / S["H_peak"][-1]
        d.line([Q(x, y) for x, y in zip(t60[mm], Hn[mm])], fill=(150, 150, 150), width=4)
    for k, tv in (("a", -4.2), ("b", -3.4), ("c", -2.4), ("d", -2.05)):
        d.line([Q(tv, 0.0), Q(tv, 1.02)], fill=(230, 150, 60), width=1)
        d.text((Q(tv, 1.02)[0] - 4, bx2[1] - 18), k, fill=(200, 100, 0), font=font(14))
    d.text((bx2[0], 10), "主役の峰の高さ H(τ)/H(t*)：灰（太）＝設計27 の較正（峰の行）、\n紺＝物理 λp 195 m、藤＝250 m（Δθ によらない）", fill=(0, 0, 0), font=font(16))
    d.text((bx2[0] + 230, bx2[1] + bx2[3] + 22), "物理の時刻 τ（s、t* = 0）。橙の線＝設計26 §3.1 の段階 a〜d（峰の行）", fill=(0, 0, 0), font=font(14))
    d.text((70, 580), "物理＝±Δθ/2 の 2 系の分散集中（JONSWAP γ 3.3、NewWave の重み、設計27 の搬送波と同じ成分）を焦点で H* = 20.80 m にし、線形＋狭帯域の 2 次（設計26 E2 の式）。\n"
           "主役の峰の育ち方は、焦点で最大になる峰を模様の速さで追った高さ（主断面）。", fill=(0, 0, 0), font=font(13))
    img.save(path)


def outline_figure(path, names, M, SER):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (1760, 760), (255, 255, 255))
    d = ImageDraw.Draw(img)
    x0, y0, sc = 40, 60, 1600.0 / 1606.0
    xs = 157 + 4 * np.arange(len(SER[names[0]]["top_kstar"])) + 2
    ylo, yhi = 0, 1080

    def P(x, y):
        return (x0 + (x - 157) * sc, y0 + (min(max(y, ylo), yhi) - ylo) * (620.0 / (yhi - ylo)))
    d.rectangle([P(157, ylo), P(1762, yhi)], outline=(180, 180, 180))
    palette = [(20, 40, 120), (40, 120, 220), (200, 40, 40), (100, 110, 170), (120, 180, 240), (240, 140, 140), (60, 160, 60), (160, 100, 20)]
    tk = SER[names[0]]["top_kstar"]
    m = np.isfinite(tk) & (tk < 1079)
    idx = np.nonzero(m)[0]
    for sg in np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1):
        if len(sg) > 1:
            d.line([P(xs[i], tk[i]) for i in sg], fill=(150, 150, 150), width=5)
    ly = 70
    for k, nm in enumerate(names):
        t = SER[nm]["top_run"]
        mm = np.isfinite(t) & (t >= ylo) & (t <= yhi)
        col = palette[k % len(palette)]
        # 連続した区間ごとに線
        idx = np.nonzero(mm)[0]
        if len(idx):
            br = np.nonzero(np.diff(idx) > 1)[0]
            segs = np.split(idx, br + 1)
            for sg in segs:
                if len(sg) > 1:
                    d.line([P(xs[i], t[i]) for i in sg], fill=col, width=2)
        d.line([(1380, ly + 8), (1410, ly + 8)], fill=col, width=3)
        d.text((1416, ly), "%s（平均 %.0f px）" % (M[nm]["label_ja"].replace("物理だけ\n", "").replace("\n", " ")[:24], M[nm]["tstar"]["painting_upper_outline"]["mean_abs_px"] or 0), fill=(0, 0, 0), font=font(13))
        ly += 20
    d.text((40, 10), "原画視点（PaintingCam v1）の t* の上の輪郭（列 157〜1762、4 px の帯ごとの一番上。どちらかが水面の 1 m より上の帯だけ）：灰（太）＝K*、色＝入力の違い",
           fill=(0, 0, 0), font=font(16))
    d.text((40, 700), "numpy の投影（網を 3 倍に細かくした頂点の点の投影。隠れの判定なし）。Unity の描画ではない。", fill=(0, 0, 0), font=font(14))
    img.save(path)


# ---------------------------------------------------------------- 表
def fmt(v, nd=2):
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "合格" if v else "不合格"
    if isinstance(v, (int, float)):
        return ("%." + str(nd) + "f") % v
    return str(v)


def table_md(M, order, sim):
    L = []
    L.append("# 設計28 の入力条件の変更と較正の掃引（ds28_inputs_run.py の出力）")
    L.append("")
    L.append("- 生成器：設計27 の `ds27_model.Generator`（コミット c2b6839、SHA-256 を照合して読むだけ）を継承した `ds28_inputs_model.InputGen`。numpy の解析式を直接測った値（包み・Unity の描画・HMD ではない）。")
    L.append("- 「物理だけ」＝切った版（9 つの美術の誘導を切る）＋物理の頂の高さ（行ごとの t* の頂を分散集中の包絡と 2 次から。K* の塔を受け継がない）＋唇の水平の打ち出しを cos²(Δθ/2) に比例。c0 は入力から。設計27 の錨の K* への ease-in（τ −2.0 s から t* の K* の錨の位置へ）は掛けない（設計28 のレビュー対応。錨は設計27 の表 D(σ) のまま、頂の真下の 0.02H で止まる）。設計28 の切った版（ds28_physoff.py、設計28 の生成器）とは別の生成器で、入力どうしを比べるための版。")
    L.append("- 段階の τ は峰の行（行 192）。表（設計26 §3.1）は a −4.2・b −3.4・c −2.4・d −2.05 s（±0.3 s）。θc(b) は b の時刻（成り立たないときは表の b）の峰の行の頂の角。E1 は同じ入力・較正の入れた版で K* の唇へ着く打ち出しの速さが目安に入る割合。")
    L.append("")
    L.append("| 名前 | 内容 | c0 m/s | t* RMS m（全頂点） | 本体の列 RMS m | 主断面 RMS m | 最大 m | 輪郭 平均/最大 px/はみ出す帯 | Lo/H t*（主・峰） | a | b | c | d | θc(b)° | P1 | P4 | P5 | P6 | P7 | P10 | P15 | P16 | E1 |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for nm in order:
        R = M[nm]
        tr = R["tstar"]
        od = tr["painting_upper_outline"]
        lo = tr["overhang_Lo_over_H"]
        row = [nm, R["label_ja"].replace("\n", " "), fmt(R["cfg"]["c0_used_mps"], 1), fmt(tr["rms_m"]), fmt(tr.get("body_cols_rms_m")), fmt(tr["main_row_rms_m"]), fmt(tr["max_m"], 1),
               "%s/%s/%s" % (fmt(od["mean_abs_px"], 0), fmt(od["max_abs_px"], 0), od.get("extra_wave_bins", "—")), "%s・%s" % (fmt(lo["main"]), fmt(lo["peak"]))]
        if R.get("gates"):
            g = R["gates"]
            p = g["P15"]["peak_192"]
            row += [fmt(p["tau"][k]) for k in "abcd"]
            row += [fmt(p["theta_c_at_b_deg"], 0)]
            row += [fmt(g[k]["pass_"]) for k in ("P1", "P4", "P5", "P6", "P7", "P10", "P15", "P16")]
        else:
            row += ["—"] * 13
        row += [fmt(R["lip_plausibility_E1"]["fraction"], 3)]
        L.append("| " + " | ".join(row) + " |")
    L.append("")
    L.append("利用者の解算の時間（`%s`、Froude で K* へ ×%s）との比較（峰の行）：" % (sim["source"], sim["froude_time"]))
    L.append("")
    L.append("| 名前 | a→b s | b→c s | 始まり→Lo 0.1H s | 始まり→唇先 0.59H s | 前面 90°→160° s | 唇先 u/峰 | 始まりの H/Hf | 始まりの θc° | 広がり m/s |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    L.append("| 解算（K* へ換算） | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (sim["a_to_b_s"], sim["b_to_c_s"], sim["onset_to_Lo0p1H_s"], sim["onset_to_tip_0p59H_s"],
                                                                         sim["front_90_to_160_s"], sim["jet_u_over_crest"], sim["onset_H_over_final"],
                                                                         sim["crest_angle_at_vertical_deg"], sim["lateral_spread_mps"]))
    for nm in order:
        R = M[nm]
        if not R.get("sim_compare"):
            continue
        s = R["sim_compare"]["peak_192"]
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (nm, fmt(s["a_to_b_s"]), fmt(s["b_to_c_s"]), fmt(s["onset_to_Lo0p1H_s"]), fmt(s["onset_to_tip_0p59H_s"]),
                                                                           fmt(s["front_90_to_160_s"]), fmt(s["jet_u_over_crest"]), fmt(s["onset_H_over_final"]),
                                                                           fmt(s["theta_c_at_onset_deg"], 0), fmt(R["sim_compare"].get("lateral_spread_mps_fit"), 1)))
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--only", default=None)
    ap.add_argument("--figs-only", action="store_true")
    ap.add_argument("--refresh-tstar", action="store_true", help="t* の測定（K* との差・輪郭・E1）だけを測り直して入れ替える")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    import ds28_inputs_measure as MS
    from ds28_inputs_model import check_frozen
    frozen = check_frozen()
    items = run_list()
    if a.only:
        want = set(a.only.split(","))
        items = [it for it in items if it["name"] in want]
    mpath = os.path.join(OUT, "ds28_inputs_metrics.json")
    spath = os.path.join(OUT, "ds28_inputs_series.npz")
    M, SER = {}, {}
    if os.path.isfile(mpath):
        M = json.load(open(mpath, encoding="utf-8")).get("runs", {})
    if os.path.isfile(spath):
        z = np.load(spath)
        for k in z.files:
            nm, key = k.split("|", 1)
            SER.setdefault(nm, {})[key] = z[k]
    t0 = time.time()
    if a.refresh_tstar:
        ctx0 = MS.Context()
        for it in items:
            if it["name"] not in M or "error" in M[it["name"]]:
                continue
            R2, _ = MS.measure(ctx0, it["cfg"], tstar_only=True)
            top = R2.pop("tstar_top_px")
            M[it["name"]]["tstar"] = R2["tstar"]
            M[it["name"]]["label_ja"] = it["label"]
            M[it["name"]]["lip_plausibility_E1"] = R2["lip_plausibility_E1"]
            SER.setdefault(it["name"], {})["top_run"] = np.asarray(top["run"])
            SER[it["name"]]["top_kstar"] = np.asarray(top["kstar"])
            print("[ds28_inputs] t* を測り直した：%s" % it["name"], flush=True)
    elif not a.figs_only:
        with ProcessPoolExecutor(max_workers=a.jobs) as ex:
            for nm, R, S, dt in ex.map(_work, items):
                M[nm] = R
                SER[nm] = S
                print("[ds28_inputs] %s %.0f s%s" % (nm, dt, ("  失敗：" + R["error"]) if "error" in R else ""), flush=True)
    M = {k: v for k, v in M.items() if "error" not in v} | {k: v for k, v in M.items() if "error" in v}
    ctx = MS.Context()
    rep = dict(schema="GreatWave.DS28.inputs/1", number="設計28", tool="Tools/GWWaveGen/ds28/ds28_inputs_run.py",
               evidence_kind_ja="numpy の生成器の解析式の測定（包み・Unity の描画・HMD の結果ではない）",
               frozen_ds27_sha256=frozen, sim_reference=ctx.sim, runs=M, runtime_s=round(time.time() - t0, 1))
    json.dump(rep, open(mpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    np.savez_compressed(spath, **{"%s|%s" % (nm, k): v for nm, S in SER.items() for k, v in S.items()})
    order = [it["name"] for it in run_list() if it["name"] in M and "error" not in M[it["name"]]]
    open(os.path.join(OUT, "ds28_inputs_table.md"), "w", encoding="utf-8").write(table_md(M, order, ctx.sim))
    ks = ctx.ks
    inp = [n for n in ["base_art_on", "base_art_off_kstar", "in_d0_l195", "in_d60_l195", "in_d120_l195", "in_d0_l250", "in_d60_l250", "in_d120_l250"] if n in M and "error" not in M[n] and "sec_main" in SER.get(n, {})]
    if inp:
        sections_figure(os.path.join(OUT, "fig_ds28_inputs_sections.png"), inp, M, SER, ks,
                        "設計28 入力条件の変更：物理だけ（設計27 の生成器の切った版＋物理の頂の高さ、錨の K* への ease-in なし）の交差角 Δθ と波長 λp。上 2 段は設計27 の入れた版と切った版（塔を受け継ぐ）")
    cal = [n for n in ["in_d60_l195", "cal_ph_on20", "cal_ph_on28", "cal_ph_peel30", "cal_ph_c016", "cal_ph_lead18",
                       "base_art_on", "cal_on_on20", "cal_on_on28", "cal_on_peel30", "cal_on_c016", "cal_on_lead18"] if n in M and "error" not in M[n] and "sec_main" in SER.get(n, {})]
    if cal:
        sections_figure(os.path.join(OUT, "fig_ds28_calib_sections.png"), cal, M, SER, ks,
                        "設計28 較正の掃引（既定の入力 60°・195 m）：上 6 段＝物理だけ（錨の K* への ease-in なし）、下 6 段＝設計27 の入れた版（t* = K*）")
    ing = [n for n in ["ing_d0_l195", "ing_d60_l195", "ing_d120_l195", "ing_d60_l250"] if n in M and "error" not in M[n] and "sec_main" in SER.get(n, {})]
    if ing:
        sections_figure(os.path.join(OUT, "fig_ds28_inputs_growth_sections.png"), ing, M, SER, ks,
                        "設計28 入力条件の変更：物理だけ＋物理の育ち方（主役の峰の高さを分散集中から。噴流の始まりは較正の 2.4 s のまま）")
    crest_physics_figure(os.path.join(OUT, "fig_ds28_crest_physics.png"), M, SER, ks)
    ol = [n for n in ["base_art_off_kstar", "in_d0_l195", "in_d60_l195", "in_d120_l195", "in_d0_l250", "in_d60_l250", "in_d120_l250"] if n in SER and "top_run" in SER[n]]
    if ol:
        outline_figure(os.path.join(OUT, "fig_ds28_inputs_outline.png"), ol, M, SER)
    print("[ds28_inputs] %d 本、%.0f s → %s" % (len(items), time.time() - t0, OUT))


if __name__ == "__main__":
    main()
