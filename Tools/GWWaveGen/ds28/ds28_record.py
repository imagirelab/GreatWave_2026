# -*- coding: utf-8 -*-
"""設計28（統合）：証拠の図・並べた動画・metrics.json・run.json を Docs/Evidence/Design/28/ に書く。

設計28 の 2 つの担当の出力（入力条件の変更と較正の掃引＝物理の側、美術の誘導の作り直し）と統合の出力（切った版の物理の頂の高さ、
確認用の視点 seat_toward_wave、関門・描画・測り直し）を読み、1 つの証拠一式にする。数値は読むだけで作り直さない
（例外：P14 の値は、設計28 の組（入れた版 art_on と切った版 art_off_phys）で ds27_gates.sibling_p14 と同じ式で測る。
検査器はフォルダー名 art_on／art_off で隣の版を探すので、art_off_phys の報告では「見つからない」と出るため）。

入力（どれも読むだけ。Unity/Build/ は Git 対象外）：
  Unity/Build/Design/28/art_on・art_off_phys・art_off/                パッケージ（設計28 の入れた版、切った版＝物理だけ（14 個を切る）、参考：塔とえぐりを受け継ぐ切った版）
  Unity/Build/Design/28/gates/<組>.json                              ds28_gates.py の出力（P1〜P19）
  Unity/Build/Design/28/p20/ds28_p20.json・ds28_p20_tower.json        P20（14 個の誘導の大きさ、分けられない 2 個の別の測り方、名前のない違い）
  Unity/Build/Design/28/gates/ds28_review_checks.json               レビュー対応の記録（シートの上の本体の水、唇のすべての列の弾道。ds28_review_checks.py）
  Unity/Build/Design/28/review_r0/                                  レビューの前の切った版（ds_undercut_kstar 入り）と入力条件の掃引（錨の ease-in 入り）の出力（比べるための参考）
  Unity/Build/Design/28/inputs/                                     入力条件の変更と較正の掃引（ds28_inputs_run.py・ds28_inputs_summary.py の出力）
  Unity/Build/Design/28/<組>[_stages]/、ref27_art_on_default[_stages]/  Unity の描画（設計27 の DS27Formation と設計28 の DS28ReviewView）
  Unity/Build/Design/27/art_on・art_on_default・gates/                 比べる設計27 の入れた版
  Unity/Build/Design/28/evidence_draft/ds28_art_guidance_metrics.json 美術の誘導の担当の草稿（唇の弾道の当てはめを写す）
  Unity/Build/Design/26/paper/img_465〜468.jpg                       論文 Fig. 4 a〜d（PDF から取り出した埋め込み JPEG、SHA-256 を照合）
出力（Docs/Evidence/Design/28/）：図 13 枚、1280×720 の並べた動画 4 本、metrics.json、run.json。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds28/ds28_record.py [--no-video]
利用者の高解像度の写真（webp）は読まない。利用者の Houdini 解算のファイルは読まない。
"""
import argparse
import datetime
import glob
import json
import math
import os
import platform
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
DS27 = os.path.abspath(os.path.join(HERE, "..", "ds27"))
sys.path.insert(0, HERE)
sys.path.insert(0, DS27)
import ds27_gates as DG  # noqa: E402
import ds28_evidence as EV  # noqa: E402
import ds28_gates_extra as GX  # noqa: E402

REPO, B28, B27, EVID = EV.REPO, EV.B28, EV.B27, EV.EVID
font, sha, rel, jload = EV.font, EV.sha, EV.rel, EV.jload
FFMPEG, FONT_FF = EV.FFMPEG, EV.FONT_FF
STAGES = ("a", "b", "c", "d", "apex", "tstar")
STAGE_LAB = {"a": "a 丸い峰", "b": "b 尖った塔", "c": "c 鉛直の壁", "d": "d 先が前へ返る", "apex": "唇先の頂点", "tstar": "t*（原画）"}
STW_CROP = (360, 120, 1440, 728)       # seat_toward_wave（1920×1080）の波のまわり（16:9）
VERS = [
    dict(key="ds27_on", label="設計27 入れた版", pkg=os.path.join(B27, "art_on"), run=os.path.join(B27, "art_on_default"),
         stills=os.path.join(B28, "ref27_art_on_default_stages"), stw=os.path.join(B28, "ref27_art_on_default")),
    dict(key="ds28_on", label="設計28 入れた版（既定）", pkg=os.path.join(B28, "art_on"), run=os.path.join(B28, "art_on_default"),
         stills=os.path.join(B28, "art_on_default_stages"), stw=os.path.join(B28, "art_on_default")),
    dict(key="ds28_off", label="設計28 切った版（物理だけ）", pkg=os.path.join(B28, "art_off_phys"), run=os.path.join(B28, "art_off_phys_default"),
         stills=os.path.join(B28, "art_off_phys_default_stages"), stw=os.path.join(B28, "art_off_phys_default")),
]
COMBOS = {
    "art_on_default": dict(pkg="art_on", run="art_on_default", warp="default", ja="設計28 入れた版（13 個の誘導をすべて入れる。既定）・既定の時間曲線"),
    "art_on_alt": dict(pkg="art_on", run="art_on_alt", warp="alt", ja="設計28 入れた版・代案の時間曲線（実時間のまま t* で瞬間に止める）"),
    "art_off_phys_default": dict(pkg="art_off_phys", run="art_off_phys_default", warp="default", ja="設計28 切った版（物理だけ：14 個の誘導をすべて切る。物理の頂の高さ、噴流の始まりの張り出し 0）・既定"),
    "art_off_kstar_default": dict(pkg="art_off", run="art_off_default", warp="default", ja="参考：塔とえぐりを受け継ぐ切った版（ds28_model の 12 個を切り、行ごとの頂の高さは K*、ds_undercut_kstar は入る。設計27 の切った版と同じ扱い）・既定"),
}
INPUT_FIGS = ["fig_ds28_inputs_sections.png", "fig_ds28_inputs_outline.png", "fig_ds28_crest_physics.png", "fig_ds28_calib_sections.png",
              "fig_ds28_inputs_unity_side.png", "fig_ds28_inputs_growth_sections.png"]
GUIDE_ORDER = ["ds_crest_tower", "ds_body_narrow", "ds_back_steep", "ds_tube_shape", "ds_lip_target_kstar", "ds_claws", "ds_farwall_hold",
               "ds_approach_kstar", "ds_undercut_kstar", "ds_tower_peak", "ds_swell_calm", "ds_sea_calm_painting", "ds_tube_white_early", "ds_tip_white_line"]
GUIDE_NEW = {"ds_crest_tower": "名前を付けた（設計27 では名前なし）", "ds_approach_kstar": "設計28 の新", "ds_undercut_kstar": "レビュー対応で名前を付けた",
             "ds_tower_peak": "設計28 の新", "ds_tip_white_line": "設計28 の新"}
NOT_SEPARABLE = ("ds_back_steep", "ds_farwall_hold")
KIND_SHORT = {"ds_undercut_kstar": "噴流の始まりの前に前面を頂の下までえぐる量を K* から決める", "ds_crest_tower": "行ごとの t* の頂の高さを K* から受け継ぐ（塔）"}


def stage_tau():
    """段階の τ：関門の検査器の出力（設計28 入れた版・既定）の P15 の峰の行の a〜d と P4 の唇先の頂点、t* = 0。"""
    g = jload(os.path.join(B28, "gates", "art_on_default.json"))
    st = g["gates"]["P15"]["detail"]["峰で最も高い巻きの行"]["tau"]
    ap = g["gates"]["P4"]["detail"]["峰で最も高い巻きの行"]["apex_tau"]
    return dict(a=float(st["a"]), b=float(st["b"]), c=float(st["c"]), d=float(st["d"]), apex=float(ap), tstar=0.0)


def find_still(d, view, stage):
    f = glob.glob(os.path.join(d, "stills", "ds27_%s_%s_tau*.png" % (view, stage)))
    return f[0] if f else None


def load_crop(p, view, size):
    im = Image.open(p).convert("RGB")
    if view == "side_left":
        im = im.crop(EV.SIDE_CROP)
    elif view.startswith("seat_toward_wave"):
        im = im.crop(STW_CROP)
    return im.resize(size, Image.LANCZOS)


# ------------------------------------------------------------------ 図：段階 a〜d と論文 Fig. 4（seat_toward_wave の段を足した）
def p15_figure(out, taus):
    for n, h in EV.PAPER_SHA.items():
        if sha(os.path.join(EV.PAPER, "img_%d.jpg" % n)) != h:
            raise SystemExit("論文の図の JPEG の SHA-256 が設計26 の記録と違う")
    pan = [Image.open(os.path.join(EV.PAPER, "img_%d.jpg" % n)).convert("RGB").transpose(Image.FLIP_LEFT_RIGHT) for n in (465, 466, 467, 468)]
    pw, ph = pan[0].size
    pan = [p.resize((480, int(round(ph * 480.0 / pw))), Image.LANCZOS) for p in pan]
    ph2 = pan[0].size[1]
    W, H, lab_w = 480, 270, 240
    v28 = VERS[1]
    rows = [("我々の波：断面\n（設計28 入れた版。\n紺＝主断面、橙＝峰の行、\n灰＝t* の K*）", "section", H),
            ("我々の波：座席から\n波の来る方向を水平に\n（Unity、seat_toward_wave、\n縦 70°、中央を拡大。\n船と仮置きは隠した）", "seat_toward_wave", H),
            ("我々の波：左の側面\n（Unity、波の枠と\nともに動く）", "side_left", H),
            ("我々の波：原画視点\n（Unity、PaintingCam v1）", "painting", H), ("論文 Fig. 4 a〜d\n（120°、掲載の向き）", None, ph2)]
    img = Image.new("RGB", (lab_w + 4 * W, 40 + sum(h + 30 for _, _, h in rows) + 170), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for k, s in enumerate("abcd"):
        d.text((lab_w + k * W + 6, 8), EV.STAGE_JA[s], fill=(0, 0, 0), font=font(22))
    y = 40
    used = []
    for title, view, h in rows:
        d.text((6, y + 6), title, fill=(0, 0, 0), font=font(15))
        for k, s in enumerate("abcd"):
            x = lab_w + k * W
            if view is None:
                img.paste(pan[k], (x, y))
                d.text((x + 6, y + h + 4), "(%s)" % s, fill=(0, 0, 0), font=font(18))
            elif view == "section":
                EV.draw_sec(img, (x + 2, y, W - 4, h), taus[s], [v28["pkg"]], xr=(-30.0, 24.0), yr=(-3.0, 30.0))
                d.text((x + 6, y + h + 4), "τ = %+.3f s（峰の行の %s）" % (taus[s], s), fill=(0, 0, 0), font=font(15))
            else:
                src = v28["stw"] if view == "seat_toward_wave" else v28["stills"]
                p = find_still(src, view, s)
                if p:
                    img.paste(load_crop(p, view, (W, H)), (x, y))
                    d.text((x + 6, y + h + 4), "τ = %+.3f s" % EV.tau_of(p), fill=(0, 0, 0), font=font(15))
                    used.append(rel(p))
        y += h + 30
    for i, t in enumerate(EV.CREDIT):
        d.text((6, y + 4 + 22 * i), t, fill=(0, 0, 0), font=font(15))
    d.text((6, y + 4 + 22 * len(EV.CREDIT)), "上の 4 段は我々の波（設計28 入れた版・既定の時間曲線）。段階の τ は、関門の検査器 ds27_gates.py が峰で最も高い巻きの行（c = +3.85 m）で各段階の判定を初めて満たした時刻。"
           "段階 c は表（−2.4 s）より 0.53 s 早い（P15 の不合格。記録 §4）。", fill=(60, 60, 60), font=font(14))
    d.text((6, y + 26 + 22 * len(EV.CREDIT)), "b の尖った塔（峰の行の θc 107°）と d の先の返りは 1 段目の断面（numpy）でだけ読める。Unity の 3 段では読めない：b は座席から波の方向で右端の切り立った坂（角の丸い楔）、"
           "左の側面で広い丸い山。d の返りはどの Unity の視点にも出ない（レビュー対応、記録 §0・§8）。", fill=(150, 30, 30), font=font(14))
    d.text((6, y + 48 + 22 * len(EV.CREDIT)), "原画視点では a〜c の波はまだ画面の左端かその外。座席 v1 は上を急に見上げるので t ≈ 10 s まで波が入らない。座席の目から波の来る方向を見る段（確認用の視点）で形成の順（高さと前面の立ち方）は追える。",
           fill=(60, 60, 60), font=font(14))
    img.save(out, optimize=True)
    return used


# ------------------------------------------------------------------ 図：3 つの版の段階の並べ図（seat_toward_wave・左の側面）
def stages_figure(out, taus):
    W, H, lab = 320, 180, 210
    views = [("seat_toward_wave", "座席から波の方向"), ("side_left", "左の側面")]
    nrow = len(views) * len(VERS)
    img = Image.new("RGB", (lab + W * len(STAGES), 70 + nrow * (H + 24) + 60), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((6, 6), "段階ごとの静止画（Unity の PC オフスクリーン描画、同じ τ）：設計27 入れた版／設計28 入れた版（既定）／設計28 切った版（物理だけ）", fill=(0, 0, 0), font=font(16))
    for k, s in enumerate(STAGES):
        d.text((lab + k * W + 6, 34), "%s　τ %+.2f s" % (STAGE_LAB[s], taus[s]), fill=(0, 0, 0), font=font(15))
    y = 60
    used = []
    for view, vja in views:
        for v in VERS:
            d.text((6, y + 8), "%s\n%s" % (vja, v["label"]), fill=(0, 0, 0), font=font(14))
            src = v["stw"] if view == "seat_toward_wave" else v["stills"]
            for k, s in enumerate(STAGES):
                p = find_still(src, view, s)
                if p:
                    img.paste(load_crop(p, view, (W, H)), (lab + k * W, y))
                    used.append(rel(p))
                else:
                    d.text((lab + k * W + 20, y + H // 2), "（描画なし）", fill=(150, 150, 150), font=font(13))
            y += H + 24
    d.text((6, y + 4), "座席から波の方向：座席 v1 の目（甲板の 1.2 m 上）から、進行方向 t の逆を水平に見る確認用の視点（縦の画角 70°、中央を切り出して拡大、船・富士・前景の仮置きは隠した）。設計の変更ではない。"
           "左の側面は波の枠とともに動く（波がその場で育つように見える）。", fill=(60, 60, 60), font=font(13))
    d.text((6, y + 24), "段階の τ は設計28 入れた版の峰の行の判定の時刻（3 つの版に同じ τ を使った）。設計27 の自分の段階の τ は a −4.43・b −3.20・c −2.50・d −1.97 s（設計27 の記録）。",
           fill=(60, 60, 60), font=font(13))
    img.save(out, optimize=True)
    return used


# ------------------------------------------------------------------ 図：段階 c〜d の唇先の白（原画視点と seat_toward_wave）
WHITE_TAUS = (-2.93, -2.6, -2.4, -2.25, -2.1, -1.9)
WHITE_CROPS = {"painting": (0, 150, 260, 560), "seat_toward_wave": (880, 260, 1200, 500)}


def white_figure(out):
    rows = []
    for view, vja in (("painting", "原画視点（左端）"), ("seat_toward_wave", "座席から波の方向\n（頂を拡大）")):
        for v in (VERS[1], VERS[0]):
            rd = v["run"] if view == "painting" else v["stw"]
            if os.path.isdir(os.path.join(rd, "frames", view)):
                rows.append((view, vja, v["label"], rd))
    cw = 260
    lab = 200
    heights = {vw: int(round(cw * (c[3] - c[1]) / (c[2] - c[0]))) for vw, c in WHITE_CROPS.items()}
    img = Image.new("RGB", (lab + cw * len(WHITE_TAUS), 44 + sum(heights[r[0]] + 26 for r in rows) + 76), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((6, 8), "段階 c（峰の行 −2.93 s、表 −2.4 s）〜d の唇先の白（ds_tip_white_line）。動画の連番（既定の時間曲線）から τ に一番近いコマ。各視点で上＝設計28 入れた版、下＝設計27 入れた版", fill=(0, 0, 0), font=font(16))
    used = []
    y = 40
    for view, vja, vl, rd in rows:
        ch = heights[view]
        d.text((6, y + 8), "%s\n%s" % (vja, vl), fill=(0, 0, 0), font=font(14))
        T = np.array(jload(os.path.join(rd, "video", "ds27_frames_tau.json"))["tau"], float) if os.path.isfile(os.path.join(rd, "video", "ds27_frames_tau.json")) \
            else np.array(jload(os.path.join(B28, "art_on_default", "video", "ds27_frames_tau.json"))["tau"], float)
        for k, tv in enumerate(WHITE_TAUS):
            j = int(np.argmin(np.abs(T - tv)))
            pth = os.path.join(rd, "frames", view, "f_%04d.png" % j)
            im = Image.open(pth).convert("RGB").crop(WHITE_CROPS[view]).resize((cw, ch), Image.LANCZOS)
            img.paste(im, (lab + k * cw, y))
            d.text((lab + k * cw + 4, y + ch + 3), "τ %+.3f s（コマ %d）" % (T[j], j), fill=(0, 0, 0), font=font(12))
            used.append(rel(pth))
        y += ch + 26
    d.text((6, y + 4), "唇先の白は τ −2.77 s から出るが、この拡大で読めるのは約 −2.6 s から（設計28 の峰の行の段階 c −2.93 s にはまだない）。拡大しないと読めない。t* の色区が白の頂点にだけ出る（シェーダーは設計27 のまま）ので、途切れた細い線になる。",
           fill=(120, 30, 30), font=font(13))
    d.text((6, y + 26), "原画視点では c の波はまだ画面の左端かその外。座席 v1 と座席の仰角 30° の視点では波が画面に入らないか、手前の仮置きが隠す（設計39・40 まで）。立体の飛沫は作っていない（設計31〜35）。",
           fill=(120, 30, 30), font=font(13))
    img.save(out, optimize=True)
    return used


# ------------------------------------------------------------------ 図：本体の水・内壁・唇先の時系列（切った版は物理だけ）
def water_wall_figure(out, S, onset):
    K = EV.ks()
    img = Image.new("RGB", (1500, 900), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 6), "本体の水と内壁・唇先（波の枠、頂からの距離）。赤い縦線＝前面が鉛直になった時刻（φ ≥ 90°、設計28 入れた版）と噴流の始まり（ds26_conditions の行の唇先の放出）",
           fill=(0, 0, 0), font=font(16))
    cols = {"ds28_on": ((20, 40, 120), 3, "設計28 入れた版"), "ds27_on": ((150, 150, 150), 2, "設計27 入れた版"), "ds28_off": ((40, 160, 60), 2, "設計28 切った版（物理だけ）")}
    for i, (r, nm) in enumerate(((K.main_row, "主断面 行 159"), (K.peak_row, "峰の行 行 192"))):
        x0 = 10 + i * 745
        t = S["ds28_on"]["taus"]
        mk = [(onset[r]["cal"], "始まり"), (onset[r]["meas"], "鉛直")]
        ser = []
        for key in ("ds28_on", "ds27_on", "ds28_off"):
            s_ = S[key]
            c_, w_, lb = cols[key]
            ser.append((lb, np.interp(t, s_["taus"], s_["A"][:, r]) / s_["A"][-1, r], c_, w_))
        EV.plot_series(img, (x0, 30, 735, 280), t, ser, (0.5, 1.5), nm + "：本体の断面積（列 j_B〜j_E）/ その版の t* の値", "比", marks=mk)
        for j, (key2, lab) in enumerate((("w3", "内壁の 0.3H の点"), ("tip", "唇先（K* の唇先の列）"))):
            ser = []
            for key in ("ds28_on", "ds27_on", "ds28_off"):
                s_ = S[key]
                c_, w_, lb = cols[key]
                ser.append((lb, np.interp(t, s_["taus"], s_[key2][:, r] - s_["crest"][:, r]), c_, w_))
            yr = (-3.0, 16.0) if key2 == "w3" else (-1.0, 14.0)
            EV.plot_series(img, (x0, 320 + j * 285, 735, 275), t, ser, yr, nm + "：" + lab + " − 頂の a（波の枠）", "m", marks=mk)
    img.save(out, optimize=True)


# ------------------------------------------------------------------ 図：P20（美術の誘導の大きさ）の表
def p20_figure(out, P20, PT):
    taus = P20["taus"]
    rows = []
    for nm in GUIDE_ORDER:
        e = PT["guidance"][nm] if nm in PT["guidance"] else P20["guidance"][nm]
        rows.append((nm, e))
    sep = PT["separability"]
    rows.append(("ds_back_steep の別の測り方", dict(kind_ja="ds_body_narrow を切った版から、さらに ds_back_steep を切った差", per_tau=sep["ds_back_steep"]["after_body_narrow_off"]["per_tau"])))
    rows.append(("ds_farwall_hold の別の測り方", dict(kind_ja="物理だけの版に ds_farwall_hold だけを入れた差（峰の行 0 → +3.85 m）", per_tau=sep["ds_farwall_hold"]["alone_from_physics_only"]["per_tau"])))
    rows.append(("名前のない違い（版の名前）", dict(kind_ja="14 個を切った art_on という名前の版 − 物理だけ（κ・唇先の列・峰の行・白の最遅）", per_tau=PT["unnamed_version_keyed"]["per_tau"])))
    rows.append(("すべて切った版", dict(kind_ja="14 個すべて切った版（設計28 の切った版、物理だけ）", per_tau=PT["all_off_phys"]["per_tau"])))
    cw, rh, lab, right = 44, 34, 470, 360
    Wd = lab + cw * len(taus) + right
    img = Image.new("RGB", (Wd, 90 + rh * len(rows) + 110), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((8, 6), "P20：名前の付いた美術の誘導の大きさ（記録）。入れた版（14 個すべて入れる＝設計28 の既定）と、その誘導だけを切った版の頂点の差の最大（m、波の枠の局所座標）",
           fill=(0, 0, 0), font=font(16))
    d.text((8, 28), "列＝物理の時刻 τ（s、t* = 0）。色が濃いほど大きい（対数）。数字は 0.05 m 以上だけ。色だけの誘導は形の差 0 で、T_white（白の出る時刻）の差を右に書く", fill=(60, 60, 60), font=font(13))
    y0 = 56
    for k, tv in enumerate(taus):
        d.text((lab + k * cw + 4, y0 + 4), "%g" % tv, fill=(0, 0, 0), font=font(11))
    d.text((lab + cw * len(taus) + 6, y0 + 4), "最大の場所・t* の値", fill=(0, 0, 0), font=font(12))
    vmax = 26.0

    def colr(v):
        a = min(1.0, math.log10(1 + v / 0.05) / math.log10(1 + vmax / 0.05)) if v > 0 else 0.0
        c0, c1 = np.array([255, 255, 255]), np.array([25, 55, 120])
        return tuple(int(x) for x in c0 + (c1 - c0) * a), a
    for i, (nm, e) in enumerate(rows):
        y = y0 + 24 + i * rh
        tag = GUIDE_NEW.get(nm, "")
        d.text((8, y + 2), nm + ("（%s）" % tag if tag else ""), fill=(0, 0, 0), font=font(13))
        d.text((8, y + 17), KIND_SHORT.get(nm, e.get("kind_ja", "")), fill=(90, 90, 90), font=font(11))
        if e.get("colour_only"):
            for k in range(len(taus)):
                d.rectangle([lab + k * cw, y, lab + (k + 1) * cw - 1, y + rh - 2], fill=(246, 246, 240), outline=(230, 230, 230))
            d.text((lab + 8, y + 9), "色だけ（形の差 0）", fill=(120, 120, 120), font=font(12))
            never = (e.get("twhite_earliest_off") or 0) > 1e6
            if never:
                d.text((lab + cw * len(taus) + 6, y + 2), "T_white が変わる頂点 %d（切ると t* まで白くならない）" % e["twhite_changed_vertices"], fill=(0, 0, 0), font=font(11))
                d.text((lab + cw * len(taus) + 6, y + 17), "入れた版の最初の白 τ %s s" % e.get("twhite_earliest_on"), fill=(90, 90, 90), font=font(11))
            else:
                d.text((lab + cw * len(taus) + 6, y + 2), "T_white が変わる頂点 %d、最大 %s s 早い" % (e["twhite_changed_vertices"], e["twhite_max_abs_diff_s"]), fill=(0, 0, 0), font=font(11))
                d.text((lab + cw * len(taus) + 6, y + 17), "最初の白 入れた版 τ %s s／切った版 τ %s s" % (e.get("twhite_earliest_on"), e.get("twhite_earliest_off")), fill=(90, 90, 90), font=font(11))
            continue
        pt = e["per_tau"]
        for k, r_ in enumerate(pt):
            c, a = colr(r_["max_m"])
            d.rectangle([lab + k * cw, y, lab + (k + 1) * cw - 1, y + rh - 2], fill=c, outline=(230, 230, 230))
            if r_["max_m"] >= 0.05:
                d.text((lab + k * cw + 3, y + 9), ("%.1f" % r_["max_m"]) if r_["max_m"] >= 1 else ("%.2f" % r_["max_m"]), fill=(255, 255, 255) if a > 0.55 else (0, 0, 0), font=font(11))
        km = max(pt, key=lambda r_: r_["max_m"])
        if nm in NOT_SEPARABLE:
            d.text((lab + cw * len(taus) + 6, y + 2), "分けられない（入れた版から 1 つだけ切っても同じ）。", fill=(150, 30, 30), font=font(11))
            d.text((lab + cw * len(taus) + 6, y + 17), "大きさは下の『別の測り方』の行", fill=(150, 30, 30), font=font(11))
            continue
        if km["max_m"] < 0.005:
            d.text((lab + cw * len(taus) + 6, y + 2), "差なし（入れた版から 1 つだけ切っても同じ）", fill=(0, 0, 0), font=font(11))
        else:
            d.text((lab + cw * len(taus) + 6, y + 2), "最大 %.2f m（τ %s、行 %d 列 %d、c %s m）" % (km["max_m"], km["tau"], km["max_at"]["row"], km["max_at"]["col"], km["max_at"]["c_m"]),
                   fill=(0, 0, 0), font=font(11))
        d.text((lab + cw * len(taus) + 6, y + 17), "t*：RMS %.2f m・最大 %.2f m" % (pt[-1]["rms_m"], pt[-1]["max_m"]), fill=(90, 90, 90), font=font(11))
    yb = y0 + 24 + len(rows) * rh + 8
    notes = ["ds_back_steep・ds_farwall_hold は、入れた版から 1 つだけ切っても形が変わらない（0 は大きさではなく分けられないこと）。ds_back_steep は『ds_body_narrow または ds_back_steep』の分岐、"
             "ds_farwall_hold は峰の行だけで入れた版では版の名前が決める。別の測り方の行を足した。",
             "ds_crest_tower を切った版は行ごとの t* の頂の高さを物理（分散集中の包絡＋狭帯域の 2 次）に、ds_undercut_kstar を切った版は噴流の始まりの張り出しを 0（前面が始まりにちょうど鉛直）にしたもの（ds28_physoff.py）。",
             "名前のない違い：唇の重み κ の決め方・唇先の列のならし・峰の行 c_pk・唇の白の最遅の時刻が、切り替えではなく版の名前（art_on／art_off）で決まる。",
             "生成器を直接呼んだ値（パッケージの量子化と Hermite を含まない）。ds28_p20.py（ds28_model の 12 個）と ds28_p20_tower.py（ds28_physoff の 2 個、別の測り方、すべて切った版）の出力。"]
    for i, t in enumerate(notes):
        d.text((8, yb + 20 * i), t, fill=(60, 60, 60), font=font(12))
    img.save(out, optimize=True)


# ------------------------------------------------------------------ 動画：3 つの版を並べる（1280×720、右下は凡例と時間の目盛り）
def warp_t_of_tau(warp_path, taus):
    J = jload(warp_path)
    t = np.array(J["t"], float)
    tau = np.array(J["tau"], float)
    out = {}
    for k, tv in taus.items():
        i = np.nonzero(tau >= tv - 1e-9)[0]
        out[k] = float(t[i[0]]) if len(i) else float("nan")
    return out


def legend_panel(path, view_ja, t_st):
    W, H = 640, 360
    img = Image.new("RGB", (W, H), (245, 240, 228))
    d = ImageDraw.Draw(img)
    d.text((14, 10), "設計28：3 つの版（%s）" % view_ja, fill=(0, 0, 0), font=font(20))
    lines = ["左上：設計27 の入れた版（比べる）", "右上：設計28 の入れた版（既定。美術の誘導 14 個）", "左下：設計28 の切った版（物理だけ。14 個を切る）",
             "時間曲線は既定（t 7.9 s から世界全体が 0.5 倍、", "　t* = 12 s で止めて 2 s 保持）。PC の描画で HMD ではない"]
    for i, t in enumerate(lines):
        d.text((14, 44 + 24 * i), t, fill=(30, 30, 30), font=font(16))
    x0, x1, yb = 30, 610, 250
    d.line([(x0, yb), (x1, yb)], fill=(60, 60, 60), width=2)
    for s in range(0, 15, 2):
        x = x0 + (x1 - x0) * s / 14.0
        d.line([(x, yb - 4), (x, yb + 4)], fill=(60, 60, 60))
        d.text((x - 8, yb + 8), "%d" % s, fill=(60, 60, 60), font=font(12))
    d.text((x1 - 70, yb + 26), "t（体験の秒）", fill=(60, 60, 60), font=font(12))
    lab = {"a": "a", "b": "b", "c": "c", "d": "d", "apex": "頂点", "tstar": "t*"}
    for i, (k, tv) in enumerate(t_st.items()):
        if not np.isfinite(tv):
            continue
        x = x0 + (x1 - x0) * tv / 14.0
        d.line([(x, yb - 26), (x, yb)], fill=(200, 60, 60), width=1)
        d.text((x - 6, yb - 44 - 14 * (i % 2)), lab[k], fill=(200, 60, 60), font=font(12))
    d.text((14, 318), "赤い線＝設計28 入れた版の峰の行の段階（関門の検査器の時刻）", fill=(120, 30, 30), font=font(13))
    img.save(path)
    return dict(x0=x0, x1=x1, yb=yb)


def compare_video(view, out, t_st, view_ja, pw=640, crf=24, labels=None):
    """3 つの版を 2×2 に並べる（1 枠 pw × pw·9/16。既定 640 → 1280×720、30 fps、421 コマ）。右下は凡例と時間の目盛り（青い縦線が今の t）。
    ffmpeg はリポジトリの根で、相対パスで呼ぶ。labels で枠の見出しを替えられる（プレビュー用）。"""
    ins = []
    for v in VERS:
        rd = v["stw"] if view == "seat_toward_wave" else v["run"]
        p = os.path.join(rd, "video", "ds27_%s_30fps.mp4" % view)
        if not os.path.isfile(p):
            raise SystemExit("動画がない：%s" % p)
        ins.append(p)
    pan = os.path.join(B28, "evidence_tmp", "legend_%s.png" % view)
    os.makedirs(os.path.dirname(pan), exist_ok=True)
    geo = legend_panel(pan, view_ja, t_st)
    ph = pw * 9 // 16
    k = pw / 640.0
    fc = []
    for i, v in enumerate(VERS):
        lab = labels[i] if labels else v["label"]
        fc.append("[%d:v]scale=%d:%d:flags=lanczos,drawbox=x=0:y=0:w=%d:h=%d:color=black@0.55:t=fill,"
                  "drawtext=fontfile='%s':text='%s':x=%d:y=%d:fontsize=%d:fontcolor=white[v%d]" % (i, pw, ph, pw, int(30 * k), FONT_FF, lab, int(8 * k), int(5 * k), int(18 * k), i))
    fc.append("[3:v]format=rgb24,scale=640:360[lg]")
    fc.append("[4:v]format=rgba[cur]")
    fc.append("[lg][cur]overlay=x='%d+(%d)*t/14-2':y=%d:eval=frame[lgc0]" % (geo["x0"], geo["x1"] - geo["x0"], geo["yb"] - 18))
    fc.append("[lgc0]scale=%d:%d:flags=lanczos[lgc]" % (pw, ph))
    fc.append("[v0][v1][v2][lgc]xstack=inputs=4:layout=0_0|%d_0|0_%d|%d_%d[out]" % (pw, ph, pw, ph))
    cmd = [FFMPEG, "-y", "-loglevel", "error"]
    for p in ins:
        cmd += ["-i", rel(p)]
    cmd += ["-loop", "1", "-framerate", "30", "-i", rel(pan), "-f", "lavfi", "-i", "color=c=0x1E3C8C:s=4x36:r=30"]
    cmd += ["-filter_complex", ";".join(fc), "-map", "[out]", "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-r", "30", "-frames:v", "421", "-movflags", "+faststart", out if os.path.isabs(out) and not out.startswith(REPO) else rel(out)]
    subprocess.run(cmd, check=True, cwd=REPO)
    return [rel(p) for p in ins]


# ------------------------------------------------------------------ 数値
def gate_rows(G):
    out = {}
    for k, v in list(G["gates"].items()) + list(G.get("gates_ds28", {}).items()):
        out[k] = dict(name_ja=v["name_ja"], value=v["value"], threshold=v["threshold"], pass_=v["pass"])
    return out


def p14_pair(on_dir, off_dir, pair_ja="設計28 の組（art_on と art_off_phys）"):
    """ds27_gates.sibling_p14 と同じ式で、切った版（off_dir）の t* の K* との差。"""
    ks = DG.KStar()
    off = DG.Package(off_dir, ks)
    X0 = off.world(0.0)
    dd = np.linalg.norm(X0 - ks.X, axis=-1)
    i = np.unravel_index(int(dd.argmax()), dd.shape)
    mr = ks.main_row
    br = np.nonzero(ks.Hrow >= 3.0)[0] if hasattr(ks, "Hrow") else np.arange(ks.nv)
    return dict(pair=[rel(on_dir), rel(off_dir)], rms_m=round(float(np.sqrt((dd ** 2).mean())), 4), max_m=round(float(dd.max()), 4),
                max_at=dict(row=int(i[0]), col=int(i[1]), c_m=round(float(ks.c[i[0]]), 2)),
                main_row_rms_m=round(float(np.sqrt((dd[mr] ** 2).mean())), 4), body_rows_rms_m=round(float(np.sqrt((dd[br] ** 2).mean())), 4),
                ja="ds27_gates.sibling_p14 と同じ式（切った版の t* のワールドの位置と K* の差）。検査器はフォルダー名 art_on／art_off で隣の版を探すので、"
                   "art_off_phys の報告の P14 は「見つからない」（pass false）と出る。ここで%sの値を測った。" % pair_ja)


VERDICT_NOTES = {
    "art_on": {"P2": "不合格・記録のみ（修正 2 回の後。設計27 から。原因は周りの海の標本の範囲と静める係数、設計30）",
               "P3": "不合格・記録のみ（修正 2 回の後。行 60 の 0.285。主断面 −2.1%。設計27 では判定の区間がなく判定できなかった）",
               "P7": "不合格・記録のみ（修正 2 回の後。前面が鉛直になる時刻が噴流の始まりの約 0.5〜0.75 s 前。記録 §4 の 1）",
               "P13": "不合格・記録のみ（修正 2 回の後。12 項目中 6 項目。(2) 2 g の 1.13 倍が新しい、(5b)〜(5e)(5g) は設計27 から）",
               "P15": "不合格・記録のみ（修正 2 回の後。段階 c が表より早い：主断面 −2.73 s（表 −2.21）、峰の行 −2.93 s（表 −2.40）。a・b・d は ±0.3 s の内）",
               "P17": "不合格・記録のみ（修正 2 回の後。主断面 0.113 > 0.10。峰の行 0.095・巻きの行の最大 0.115 は合格の値。噴流の始まりから測ると 0.02）"},
    "art_off": "切った版は美術の誘導を切った比較の版で、判定は記録のみ（P14 の目的どおり）。P15 の a・b（塔）と P19 は入れた版だけで判定する（設計28 の P14 と設計26 §1.1 の矛盾の解き方、記録 §3.3）",
}


def verdicts(G, kind):
    out = {}
    for k, v in list(G["gates"].items()) + list(G.get("gates_ds28", {}).items()):
        if kind == "art_on":
            out[k] = "合格" if v["pass"] is True else (VERDICT_NOTES["art_on"].get(k, "不合格") if v["pass"] is False else "判定なし")
        else:
            out[k] = ("合格（記録）" if v["pass"] is True else ("不合格（記録のみ）" if v["pass"] is False else "判定なし"))
    return out


def file_rec(p):
    return dict(path=rel(p), sha256=sha(p), bytes=os.path.getsize(p)) if os.path.isfile(p) else dict(path=rel(p), missing=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-video", action="store_true")
    a = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    taus = stage_tau()
    figs, used = {}, {}
    # 1) 入力条件の変更と較正の掃引の図（物理の側の担当の出力をそのまま写す）
    for fn in INPUT_FIGS:
        src = os.path.join(B28, "inputs", fn)
        dst = os.path.join(EVID, fn)
        shutil.copyfile(src, dst)
        figs[fn] = dict(file_rec(dst), source=rel(src), made_by="Tools/GWWaveGen/ds28/ds28_inputs_run.py・ds28_inputs_unity_sheet.py")
    # 2) P20 の表
    P20 = jload(os.path.join(B28, "p20", "ds28_p20.json"))
    PT = jload(os.path.join(B28, "p20", "ds28_p20_tower.json"))
    p = os.path.join(EVID, "fig_ds28_guidance_p20.png")
    p20_figure(p, P20, PT)
    figs["fig_ds28_guidance_p20.png"] = file_rec(p)
    # 3) 断面（設計27 と設計28 の入れた版）、修正ごとの断面
    p = os.path.join(EVID, "fig_ds28_sections.png")
    EV.sections_figure(p, VERS[1]["pkg"], VERS[0]["pkg"])
    figs["fig_ds28_sections.png"] = file_rec(p)
    revs = [("初回（r00）", os.path.join(B28, "r00", "art_on")), ("修正1（r01）", os.path.join(B28, "r01", "art_on")), ("修正2（r02）＝既定", VERS[1]["pkg"])]
    revs = [x for x in revs if os.path.isfile(os.path.join(x[1], "ds27_keypose.json"))]
    p = os.path.join(EVID, "fig_ds28_revisions.png")
    EV.revisions_figure(p, revs)
    figs["fig_ds28_revisions.png"] = dict(file_rec(p), packages=[dict(name=n, path=rel(q), keypose_sha256=sha(os.path.join(q, "ds27_keypose.json"))) for n, q in revs])
    # 4) 本体の水と内壁
    K = EV.ks()
    cond, _ = DG.load_conditions()
    Tc = GX.calib_onset(K, cond)
    S = {v["key"]: GX.series(K, EV.pkg(v["pkg"]), t_start=-4.0, log=lambda *x: None) for v in VERS}
    onset = {}
    for r in (K.main_row, K.peak_row):
        kk = np.nonzero(np.nan_to_num(S["ds28_on"]["phi"][:, r], nan=0.0) >= 90)[0]
        onset[r] = dict(cal=-float(Tc[r]), meas=float(S["ds28_on"]["taus"][kk[0]]) if len(kk) else None)
    p = os.path.join(EVID, "fig_ds28_water_wall.png")
    water_wall_figure(p, S, onset)
    figs["fig_ds28_water_wall.png"] = file_rec(p)
    # 5) 段階 a〜d と Fig. 4、3 つの版の段階、唇先の白
    p = os.path.join(EVID, "fig_ds28_p15_fig4.png")
    used["fig_ds28_p15_fig4.png"] = p15_figure(p, taus)
    figs["fig_ds28_p15_fig4.png"] = dict(file_rec(p), paper_jpeg_sha256={str(k): v for k, v in EV.PAPER_SHA.items()})
    p = os.path.join(EVID, "fig_ds28_stages_compare.png")
    used["fig_ds28_stages_compare.png"] = stages_figure(p, taus)
    figs["fig_ds28_stages_compare.png"] = file_rec(p)
    p = os.path.join(EVID, "fig_ds28_white_c.png")
    used["fig_ds28_white_c.png"] = white_figure(p)
    figs["fig_ds28_white_c.png"] = file_rec(p)
    # 6) 並べた動画
    videos = {}
    t_st = warp_t_of_tau(os.path.join(DS27, "timewarp_default.json"), taus)
    if not a.no_video:
        for view, vja in (("painting", "原画視点"), ("seat", "座席 v1"), ("side_left", "左の側面"), ("seat_toward_wave", "座席から波の方向")):
            p = os.path.join(EVID, "ds28_compare3_%s.mp4" % view)
            ins = compare_video(view, p, t_st, vja)
            videos[os.path.basename(p)] = dict(file_rec(p), inputs=[dict(path=q, sha256=sha(os.path.join(REPO, q))) for q in ins])
    # 7) metrics.json
    gates = {}
    for nm, c in COMBOS.items():
        gp = os.path.join(B28, "gates", nm.replace("art_off_kstar_default", "art_off_default") + ".json")
        G = jload(gp)
        kind = "art_on" if c["pkg"] == "art_on" else "art_off"
        gates[nm] = dict(ja=c["ja"], source=file_rec(gp), package=rel(os.path.join(B28, c["pkg"])), P=gate_rows(G), verdicts=verdicts(G, kind),
                         failed=G["summary_all"]["failed"], P13_detail={k: dict(value=v["value"], threshold=v["threshold"], pass_=v["pass"], at=v.get("at"))
                                                                       for k, v in G["gates"]["P13"]["detail"].items() if isinstance(v, dict) and "value" in v},
                         P15_detail=G["gates"]["P15"]["detail"], P17_detail={k: G["gates_ds28"]["P17"]["detail"].get(k) for k in ("main_row", "peak_row", "worst_row", "from_jet_onset_max_frac", "before_onset_range_max_frac")},
                         P18_detail=G["gates_ds28"]["P18"]["detail"], P19_detail=G["gates_ds28"]["P19"]["detail"])
    p14 = p14_pair(os.path.join(B28, "art_on"), os.path.join(B28, "art_off_phys"))
    p14_kstar = p14_pair(os.path.join(B28, "art_on"), os.path.join(B28, "art_off"), "参考の組（art_on と art_off。塔とえぐりを受け継ぐ切った版）")
    off_failed = [k for k, v in gates["art_off_phys_default"]["P"].items() if v["pass_"] is False and k not in ("P14", "Painting")]
    for nm in ("art_on_default", "art_on_alt", "art_off_phys_default"):
        gates[nm]["P14_pair_ds28"] = p14
        gates[nm]["verdicts"]["P14"] = ("合格（設計27 と同じ読み：両方の版があり、切った版の t* と K* の差 RMS %.2f m・最大 %.1f m を記録した）。"
                                        "設計26 の P14 の『切った版も P1〜P13・P15・P16 を通す』は満たさない（物理だけの版は %s を落とす）" % (p14["rms_m"], p14["max_m"], "・".join(off_failed)))
        gates[nm]["P14_machine_value_note_ja"] = ("検査器の報告（Unity/Build/Design/28/gates/%s.json）の P14 の値は、フォルダー名で隣の art_off（参考の切った版、塔とえぐりを受け継ぐ）と組んだ値"
                                                  "（RMS %.4f m）。記録の P14 の値は設計28 の組（物理だけの版）の値（RMS %.4f m）" % (nm, p14_kstar["rms_m"], p14["rms_m"]))
    for nm in ("art_on_default", "art_on_alt"):
        x = gates[nm]["P18_detail"]["record_from_face_vertical"]
        w = max(x["worst"].values(), key=lambda q: q["retreat_m"] or 0)
        gates[nm]["verdicts"]["P18"] = ("読みで分かれる（記録のみ扱い）：ds26 の較正の噴流の始まり（行の唇先の放出）から測ると %s m で合格。前面が鉛直になった時刻"
                                        "（ds27_gates の噴流の始まり、P7・P17 の起点）から測ると %s m（行 %s、τ %s s）・%d 行が 0.3 m を超えて不合格"
                                        % (gates[nm]["P"]["P18"]["value"], w["retreat_m"], w["row"], w["tau"], x["rows_over"]))
    gates["art_off_kstar_default"]["P14_pair_ds28"] = p14_kstar
    for nm in ("art_off_phys_default", "art_off_kstar_default"):
        gates[nm]["verdicts"]["Painting"] = "判定なし（切った版の t* は K* ではない。P14）"
    ds27g = jload(os.path.join(B27, "gates", "art_on_default.json"))
    x27 = jload(os.path.join(B28, "gates", "ds27_art_on_default_extra.json"))
    gates["ds27_art_on_default"] = dict(ja="比べる：設計27 の入れた版（コミット c2b6839 の記録の値、P17〜P19 は設計28 の検査器で測った）", source=file_rec(os.path.join(B27, "gates", "art_on_default.json")),
                                        P=dict(gate_rows(ds27g), **{k: dict(name_ja=v["name_ja"], value=v["value"], threshold=v["threshold"], pass_=v["pass"]) for k, v in x27["gates"].items()}),
                                        P18_detail=x27["gates"]["P18"]["detail"], extra_source=file_rec(os.path.join(B28, "gates", "ds27_art_on_default_extra.json")))
    draft = jload(os.path.join(B28, "evidence_draft", "ds28_art_guidance_metrics.json"))
    tst = {}
    for run in ("art_on_default", "art_on_alt"):
        T = jload(os.path.join(B28, run, "ds27_tstar_remeasure.json"))
        tst[run] = dict(source=file_rec(os.path.join(B28, run, "ds27_tstar_remeasure.json")), worst_abs_diff_px=T["worst_abs_diff_px"], criterion_px=T["criterion_px"], pass_=T["pass"],
                        summary={k: T[k] for k in T if k.startswith("summary") or k.startswith("pixel_diff")})
    im_on = [os.path.join(B28, "art_on_default", "t28", "render", "af28r01_%s.png" % v) for v in ("painting", "seat", "seat_low")]
    im_alt = [os.path.join(B28, "art_on_alt", "t28", "render", "af28r01_%s.png" % v) for v in ("painting", "seat", "seat_low")]
    im_27 = [os.path.join(B27, "art_on_default", "t28", "render", "af28r01_%s.png" % v) for v in ("painting", "seat", "seat_low")]

    def pixdiff(p1, p2):
        A_ = np.asarray(Image.open(p1).convert("RGB"), np.int16)
        B_ = np.asarray(Image.open(p2).convert("RGB"), np.int16)
        dd = np.abs(A_ - B_).max(-1)
        return dict(differ_frac=round(float((dd > 0).mean()), 6), over8_px=int((dd > 8).sum()))
    tst["tstar_images"] = dict(default_vs_alt={os.path.basename(x): (sha(x) == sha(y)) for x, y in zip(im_on, im_alt)},
                               ds28_vs_ds27={os.path.basename(x): pixdiff(x, y) for x, y in zip(im_on, im_27)},
                               ja="default_vs_alt：既定と代案の t* の画像の SHA-256 が同じか（同じパッケージの同じ層）。ds28_vs_ds27：設計27 の入れた版の t* の画像と色が違う画素の割合と、8 段階を超える画素の数（外接箱の違う 16 ビットの量子化による縁の画素）")
    pb = {}
    for run in ("art_on_default", "art_off_phys_default"):
        C = jload(os.path.join(B28, run, "ds27_playback_check.json"))
        pb[run] = dict(source=file_rec(os.path.join(B28, run, "ds27_playback_check.json")), **{k: C[k] for k in C if not isinstance(C[k], (list, dict)) and k != "capture_report"})
    pb["ja"] = "Unity の GPU の読み戻しと numpy の Hermite の差（ds27_player_ref.py check）。切った版の pass false は t* が K* ではないため（位置の差は基準 2 cm の内）"
    kp, det = {}, {}
    for v in ("art_on", "art_off_phys", "art_off"):
        K_ = jload(os.path.join(B28, v, "ds27_keypose.json"))
        ch = jload(os.path.join(B28, v, "ds27_checks.json"))
        gl = jload(os.path.join(B28, v, "ds28_generate_log.json"))
        kp[v] = dict(layers=K_["layers"], variant=K_.get("variant"), pos_mib=round(K_["pos_bytes"] / 2 ** 20, 2), gpu_positions_6B_per_vertex_mib=round(K_["layers"] * 96000 * 6 / 2 ** 20, 2),
                     quantization_max_err_m=K_["quantization_max_err_m"], hermite_playback_err_m=ch["hermite_playback_err_m"]["max"],
                     tstar_vs_kstar_world_max_m=ch["tstar_vs_kstar_world_max_m"], generate_seconds=gl["result"]["seconds"],
                     pos_sha256=K_["pos_sha256"], twhite_sha256=K_["twhite_sha256"], keypose_json_sha256=sha(os.path.join(B28, v, "ds27_keypose.json")),
                     code_sha256=gl["code_sha256"], command=gl["command"], summary=K_["generator"]["summary"])
        for fn in ("ds27_pos_rgba16.bin", "ds27_twhite_r32f.bin", "ds27_keypose.json"):
            a1, a2 = os.path.join(B28, v, fn), os.path.join(B28, "_twice", v, fn)
            if os.path.isfile(a1) and os.path.isfile(a2):
                h1, h2 = sha(a1), sha(a2)
                det["%s/%s" % (v, fn)] = dict(sha256=h1, same_bytes=(h1 == h2))
    rv = {}
    for run in ("art_on_default", "art_on_alt", "art_off_phys_default"):
        for fp in sorted(glob.glob(os.path.join(B28, run, "ds28_review_view_*.json"))):
            R = jload(fp)
            rv["%s/%s" % (run, os.path.basename(fp))] = dict(source=file_rec(fp), eye=R["eye"], forward=R["forward"], fov=R["fov"], contextHidden=R["contextHidden"],
                                                             protectedUnchanged=R["protectedUnchanged"], sceneDirtyNotSaved=R["sceneDirtyNotSaved"], videoFrames=R.get("videoFrames"),
                                                             videoSha256=R.get("videoSha256"), totalSeconds=R["totalSeconds"], passed=R["passed"])
    rv["ref27_art_on_default/ds28_review_view_seat_toward_wave.json"] = dict(source=file_rec(os.path.join(B28, "ref27_art_on_default", "ds28_review_view_seat_toward_wave.json")))
    rr = {}
    for run in ("art_on_default", "art_on_alt", "art_off_phys_default", "art_on_default_stages", "art_off_phys_default_stages", "ref27_art_on_default_stages"):
        fp = os.path.join(B28, run, "ds27_render_report.json")
        if os.path.isfile(fp):
            R = jload(fp)
            rr[run] = dict(source=file_rec(fp), package=rel(R["package"]) if R.get("package") else None, warp=R.get("warp"), layers=R.get("layers"), positionGpuBytes=R.get("positionGpuBytes"),
                           stillNames=R.get("stillNames"), stillTau=R.get("stillTau"), videos=[dict(view=x["view"], frames=x["frames"], sha256=x["sha256"]) for x in R.get("videos", [])],
                           protectedUnchanged=R.get("protectedUnchanged"), passed=R.get("passed"), totalSeconds=R.get("totalSeconds"), device=R.get("device"), unity=R.get("unity"))
    inputs_summary = jload(os.path.join(B28, "inputs", "ds28_inputs_summary.json"))
    sim = jload(os.path.join(REPO, "Tools", "GWWaveGen", "ds27_user_sim_timing.json"))
    rec = dict(
        schema="GreatWave.DS28.metrics/1", number="設計28", title_ja="原画の弧へ近づける調整の比較：入力条件の変更（物理）と美術の誘導を別に記録",
        generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        evidence_kind_ja="numpy の生成器と関門の検査器（パッケージを Hermite で読む）、入力条件の掃引は生成器の解析式を直接測った値。Unity 6000.4.3f1 の PC オフスクリーン描画（RTX 3080、Direct3D11）。HMD 実機ではない。Houdini は使っていない。利用者の解算のファイルは開いていない（設計26 の記録の数値だけ）。",
        default_decision=dict(
            hero_motion="設計28 の入れた版（ds28_model.Generator('art_on')、美術の誘導 13 個をすべて入れる。修正2 ＋節点の適応の回数の上限 9）を設計28 の既定の動きにする。t* = K*（1.20 mm）",
            inputs="Δθ 60°・λp 195 m（設計26 の既定のまま。D30）",
            calibration=dict(adopted=dict(jet_onset_s=2.4, peel_mps=20.0, c0_mps=20.0, beta=0.8, decel_start="噴流の始まりから（設計26 のまま）"),
                             not_adopted=[dict(value="広がり 30 m/s", reason_ja="物理の側の掃引では関門をすべて通し、利用者の解算の換算（設計26 §7.1 の 28〜33 m/s。噴流の始まりの峰の基準まで含めると 27.6〜37.4 m/s）と合うので勧められた。採らなかった理由：(1) 生成器の修正 2 回（r01・r02）の後で、設計28 の生成器を作り直す 3 回目の修正になる（損切り）。(2) 主断面の段階の時刻が約 0.064 s 早まり、設計28 の入れた版の主断面の a（表との差 −0.24 s）が許容 ±0.3 s の端（約 −0.30 s）に寄る見込み（設計27 の生成器では −0.29 s）。関門の表の主断面の時刻は設計26 の 20 m/s で作られているので、30 m/s にするなら表も変える（設計26 の表の変更）。見え方の差は、砕波が波峰線に沿って速く広がることだけ。仕上げ28 の候補として利用者に示す"),
                                          dict(value="噴流の始まり 2.0 s・2.8 s", reason_ja="2.0 s は段階 c が成り立たず（P15）、2.8 s は P5・P7・P15・P16 を落とす（時間曲線が 2.4 s 用）"),
                                          dict(value="c0 16 m/s", reason_ja="関門は通るが、滑って見える原因は幅の細い本体（ds_body_narrow）で、c0 を下げても比は 2.53 → 2.03 にしか下がらない。入力（60°・195 m の模様の速さ 20 m/s）とも合わなくなる"),
                                          dict(value="減速を噴流の 1.8 s 前から", reason_ja="関門は通るが見え方の差は小さい（P1 18.4 → 17.4 m/s）。設計28 の入れた版の P15 の c・P7 を直す候補（記録 §4 の 1 の選択肢 (b)）だが、試すと生成器の 3 回目の修正になるので記録のみ")]),
            ja="較正の掃引から既定に採った値はない（設計26 の値のまま）。理由は not_adopted。"),
        stage_tau_peak_row=taus, stage_t_default_warp=t_st,
        gates=gates,
        p20=dict(ja="名前の付いた美術の誘導 14 個の大きさ（記録）。入れた版とその誘導だけを切った版の頂点の差（m）。ds28_p20.json（ds28_model の 12 個）と ds28_p20_tower.json"
                    "（ds28_physoff の ds_crest_tower・ds_undercut_kstar、分けられない 2 個の別の測り方、名前のない違い、すべて切った版）。ds_back_steep・ds_farwall_hold の rows の値 0 は大きさではなく分けられないこと（separability）",
                 sources=[file_rec(os.path.join(B28, "p20", "ds28_p20.json")), file_rec(os.path.join(B28, "p20", "ds28_p20_tower.json"))],
                 rows={nm: (dict(kind_ja=e["kind_ja"], colour_only=True, twhite_changed_vertices=e["twhite_changed_vertices"], twhite_max_abs_diff_s=e["twhite_max_abs_diff_s"],
                                 twhite_earliest_on=e.get("twhite_earliest_on"), twhite_earliest_off=e.get("twhite_earliest_off"))
                            if e.get("colour_only") else
                            dict(kind_ja=e["kind_ja"], max_m=max(r_["max_m"] for r_ in e["per_tau"]), max_tau=max(e["per_tau"], key=lambda r_: r_["max_m"])["tau"],
                                 max_at=max(e["per_tau"], key=lambda r_: r_["max_m"])["max_at"], rms_max_m=max(r_["rms_m"] for r_ in e["per_tau"]),
                                 tstar=dict(rms_m=e["per_tau"][-1]["rms_m"], max_m=e["per_tau"][-1]["max_m"]),
                                 first_nonzero_tau=next((r_["tau"] for r_ in e["per_tau"] if r_["max_m"] > 0.005), None),
                                 per_tau=[dict(tau=r_["tau"], rms_m=r_["rms_m"], max_m=r_["max_m"]) for r_ in e["per_tau"]]))
                       for nm, e in [(nm, PT["guidance"][nm] if nm in PT["guidance"] else P20["guidance"][nm]) for nm in GUIDE_ORDER]},
                 all_off_phys=[dict(tau=r_["tau"], rms_m=r_["rms_m"], max_m=r_["max_m"]) for r_ in PT["all_off_phys"]["per_tau"]],
                 all_off_phys_review_r0=[dict(tau=r_["tau"], rms_m=r_["rms_m"], max_m=r_["max_m"]) for r_ in PT["all_off_phys_review_r0"]["per_tau"]],
                 physoff_undercut_effect=dict(max_m=PT["physoff_undercut_effect"]["max_over_tau_m"], max_tau=PT["physoff_undercut_effect"]["max_tau"],
                                              tstar=dict(rms_m=PT["physoff_undercut_effect"]["per_tau"][-1]["rms_m"], max_m=PT["physoff_undercut_effect"]["per_tau"][-1]["max_m"])),
                 undercut_anchor=PT["guidance"]["ds_undercut_kstar"]["anchor"],
                 separability={nm: {k: (dict(kind_ja=v["kind_ja"], max_m=v["max_over_tau_m"], max_tau=v["max_tau"], max_at=v["max_at"],
                                             tstar=dict(rms_m=v["per_tau"][-1]["rms_m"], max_m=v["per_tau"][-1]["max_m"]),
                                             **({"twhite_changed_vertices": v["twhite_changed_vertices"]} if "twhite_changed_vertices" in v else {}))
                                        if isinstance(v, dict) and "per_tau" in v else v) for k, v in e.items()} for nm, e in PT["separability"].items()},
                 unnamed_version_keyed=dict(kind_ja=PT["unnamed_version_keyed"]["kind_ja"], max_m=PT["unnamed_version_keyed"]["max_over_tau_m"],
                                            max_tau=PT["unnamed_version_keyed"]["max_tau"], max_at=PT["unnamed_version_keyed"]["max_at"],
                                            tstar=dict(rms_m=PT["unnamed_version_keyed"]["per_tau"][-1]["rms_m"], max_m=PT["unnamed_version_keyed"]["per_tau"][-1]["max_m"]),
                                            twhite_changed_vertices=PT["unnamed_version_keyed"]["twhite_changed_vertices"], branches_ja=PT["unnamed_version_keyed"]["branches_ja"],
                                            kappa=PT["unnamed_version_keyed"]["kappa"]),
                 all_off_kstar=[dict(tau=r_["tau"], rms_m=r_["rms_m"], max_m=r_["max_m"]) for r_ in P20["all_off"]["per_tau"]],
                 art_on_physoff_same_as_ds28_model_max_m=PT["art_on_same_as_ds28_model_max_m"]),
        inputs_sweep=dict(ja="入力条件の変更（物理だけ：設計27 の生成器の切った版＋物理の頂の高さ。レビュー対応で設計27 の錨の K* への ease-in を切った）と較正の掃引"
                             "（ds28_inputs_run.py・ds28_inputs_summary.py の出力の写し。設計27 の生成器を読むだけで継承した ds28_inputs_model.InputGen の解析式を直接測った値）。"
                             "設計28 の切った版（ds28_physoff、設計28 の生成器で 14 個を切る）とは別の生成器で、入力どうしを比べるための版（physics_only_definitions）",
                          sources=[file_rec(os.path.join(B28, "inputs", "ds28_inputs_summary.json")), file_rec(os.path.join(B28, "inputs", "ds28_inputs_metrics.json")),
                                   file_rec(os.path.join(B28, "inputs", "ds28_inputs_series.npz"))],
                          summary=inputs_summary),
        user_sim_timing=dict(source=file_rec(os.path.join(REPO, "Tools", "GWWaveGen", "ds27_user_sim_timing.json")), schema=sim["schema"], files=sim["source"]["files"],
                             n_values=len(sim["values"]), names=[v["name"] for v in sim["values"]],
                             ja="設計27 の引き継ぎ 5：利用者の Houdini 解算の数値だけの JSON（設計26 §7.1 の表の値だけ、出典はファイル名と SHA-256 だけ、形・断面・メッシュ・個人のパスなし）。"
                                "レビュー対応で、表の外から写していた 3 つ（φ ≥ 80° が始まりの 0.08 s 前から、段階 a の始まり → d の始まり 1.21 s（どちらも §3.1）、借りない平行移動の速さ（§7.1 の『借りないもの』））とコマの番号の注を消した"),
        tstar_remeasure=tst, playback_check=pb, keypose=kp,
        determinism=dict(ja="同じ入力から Unity/Build/Design/28/_twice/ へ作り直した 3 ファイルの SHA-256（入れた版・参考の切った版は美術の誘導の担当、物理の頂の高さの切った版は統合で作り直した）", files=det),
        lip_ballistic=draft.get("lip_ballistic"),
        review_view=dict(ja="確認用の視点 seat_toward_wave（証拠のための視点で、設計の変更ではない）：座席 v1 の目から、波の枠の原点の進む向き t の逆を水平に、縦の画角 70° で見る。"
                            "DS28ReviewView.cs が設計27 の場面を開いてメモリの上だけにカメラを足し、場面は保存しない（前後の SHA-256 が同じ）。船・富士・前景の仮置きを隠した版（seat_toward_wave）を証拠に使い、"
                            "隠さない版（seat_toward_wave_ctx、静止画だけ）では前景の白い三角と暗い斜面の仮置き（設計39・40 まで）が段階 a〜c の波を隠す。",
                         runs=rv),
        render_reports=rr,
        series_every_0p1s={key: {"taus": [round(float(t), 3) for t in S[key]["taus"][::6]],
                                 **{"%s_%d" % (q, r): [None if not np.isfinite(x) else round(float(x), 3) for x in (S[key][q][::6, r] - (S[key]["crest"][::6, r] if q != "A" else 0.0))]
                                    for r in (K.main_row, K.peak_row) for q in ("A", "w3", "w5", "tip")}} for key in S},
        onset=onset,
        figures=figs, figures_used_stills=used, videos=videos,
    )
    RC = jload(os.path.join(B28, "gates", "ds28_review_checks.json"))
    rec["review_checks"] = dict(source=file_rec(os.path.join(B28, "gates", "ds28_review_checks.json")),
                                volume={k: {kk: vv for kk, vv in v.items() if kk not in ("taus", "sheet_volume_m3", "main_row_Anet_m2", "peak_row_Anet_m2")} for k, v in RC["volume"]["runs"].items()},
                                volume_series_every_0p1s={k: dict(taus=v["taus"], sheet_volume_m3=v["sheet_volume_m3"]) for k, v in RC["volume"]["runs"].items()},
                                volume_ja=RC["volume"]["ja"], lips_all=RC["lips_all"])
    r0 = jload(os.path.join(B28, "review_r0", "gates", "art_off_phys_default.json"))
    rec["review_r0_physoff"] = dict(ja="レビューの前の切った版（13 個を切り、ds_undercut_kstar だけ入る。Unity/Build/Design/28/review_r0/art_off_phys）の関門（比べるための参考）",
                                    source=file_rec(os.path.join(B28, "review_r0", "gates", "art_off_phys_default.json")), P=gate_rows(r0), failed=r0["summary_all"]["failed"],
                                    P18_face_vertical=r0["gates_ds28"]["P18"]["detail"]["record_from_face_vertical"]["worst"])
    rec["physics_only_definitions"] = PHYS_DEFS
    rec["review_response"] = REVIEW_RESPONSE
    rec["known_view_issues"] = VIEW_ISSUES
    rec["revisions"] = REVISIONS
    rec["time"] = TIME
    rec["backlog"] = BACKLOG
    rec["handoffs_from_ds27"] = HANDOFFS
    with open(os.path.join(EVID, "metrics.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    write_run(figs, videos)
    print("DONE metrics.json・run.json・図 %d・動画 %d" % (len(figs), len(videos)))


# ------------------------------------------------------------------ 修正・時間・バックログ・引き継ぎ（記録。値は各担当の報告と生成の記録から）
REVISIONS = [
    dict(id="inputs_fix", counted=True, ja="入力条件の掃引（物理の側）の統合の後の直し 1 回：Δθ 0° では頂が波峰線に沿って一様で、砕波の広がりの起点が任意の行（c −21.4 m）になったので、焦点の行 c = 0 に固定し、0° の 4 本を測り直した",
         files=["Tools/GWWaveGen/ds28/ds28_inputs_model.py（_fix_Trow）"]),
    dict(id="r00", counted=False, ja="美術の誘導の初回の統合（r00）：錨を噴流の始まりの前（σ −3.3〜−2.4 の smoothstep）に頂の下（張り出し 0.11H）まで寄せ、始まりの後は唇の rim の進みに合わせて K* へ。"
         "管の天井を形の移しに。水は Lb をコマごとに解く。κ < 1 の行は放出を κ 倍に遅らせる。塔（ds_tower_peak）と白（ds_tip_white_line）",
         result_ja="P15・P18・P19 合格、P17 は 2 行だけ超える。P13(1) 0.86 m（錨が約 15 m を 0.9 s で動く、最大 26 m/s）、(2) 0.144 m、P16 行 60（+0.41 m/s²）",
         package="Unity/Build/Design/28/r00/art_on", params_sha256="79bcdee56caba58eed86b8f3e69ecbb13fdadd02d4fe2ed2212e31ba80f0fcf1",
         note_ja="r00 の ds28_params.json の中身は残していない（修正のたびに直した）。パッケージの記録に SHA-256 がある"),
    dict(id="r01", counted=True, ja="修正1（r01）：錨を最小躍度の曲線で σ −4.7〜−2.4 に、水の Lb を 2 つのなめらかな山の当てはめに、頂の帽子の上がりをなめらかに、κ 0.7 以上の行は遅らせない、白を放出の 0.4 s 前から",
         result_ja="P13(1)・P16 が合格に。前面が鉛直になる時刻が早まり、P7・P15 の c が落ちた。κ 0.7〜1 の行の唇が長く飛んで P13(4) 0.15 m・(5f) 980・(5g) 518", package="Unity/Build/Design/28/r01/art_on"),
    dict(id="r02", counted=True, ja="修正2（r02、提出版）：κ の放出を初回の κ 倍へ戻し、K* で巻く行のうち κ < 0.9（行 60）だけ打ち出しの補間を設計26 の表の時刻までに終える。えぐり（噴流の始まりの張り出し）を行ごとに K* の張り出しから 0.06〜0.11 にした",
         result_ja="P13 の (4)(5a)(5f)(6) が合格に戻り、(5g) は 4。P7・P15 の c・P13(2)・P17 の主断面が残った（記録のみ）", package="Unity/Build/Design/28/art_on"),
    dict(id="knots", counted=False, ja="数値の条件（動きは同じ）：節点の適応の回数の上限 6 → 9", result_ja="Hermite の再生の差 4.36 → 3.40 mm（4 mm の規則の内）", package="Unity/Build/Design/28/art_on"),
    dict(id="integration", counted=False, ja="統合（動きの修正ではない）：切った版を物理の頂の高さで作った（ds_crest_tower を 13 個目の名前の付いた誘導にし、切った版では切る。ds28_physoff.py）。入れた版は変えない。"
         "確認用の視点 seat_toward_wave（DS28ReviewView.cs）で描いた。較正の掃引から既定に採った値はない",
         result_ja="切った版（物理だけ、レビューの前）の t* と K* の差 RMS 6.73 m・最大 25.96 m。P15 の峰の行の a・b・c と P19 は成り立たない（塔は美術の誘導）",
         package="Unity/Build/Design/28/review_r0/art_off_phys（レビューの前の切った版。参考に残した）"),
    dict(id="review", counted=False, ja="レビュー対応（入れた版＝既定の動きの生成器・パッケージは変えない。修正の回数に数えない理由）：(1) ds28_model の anchor_q の σ < −2.4 の分岐（噴流の始まりの前に前面を頂の下までえぐる量を K* から決める）が"
         "切り替えを見ていなかったので、14 個目の名前の付いた誘導 ds_undercut_kstar にした（ds28_physoff.py の引数。切ると始まりの張り出し 0、K* の錨で頭打ちしない）。"
         "切った版（物理だけ）はこれも切って作り直し（Unity の描画と関門も）。(2) 入力条件の掃引の『物理だけ』から設計27 の錨の K* への ease-in を切って測り直した（ds28_inputs_model の anchor_to_kstar）。"
         "(3) 解算の数値の JSON から表の外の 3 つを消した。(4) 記録・証拠の言い過ぎを直した（P18 の読み、Unity の描画で見えること、P14、P20 の 0）",
         result_ja="入れた版のパッケージのバイトは同じ（SHA-256 が同じ）。切った版と入力条件の掃引の物理だけの値が変わった（記録 §11）",
         package="Unity/Build/Design/28/art_off_phys"),
]
TIME = dict(limit_ja="計画 ≤0.5 日。初回提出（3.5 時間、0.44 日）は上限の内。レビュー対応を足した合計は上限を超えた（超えた分はレビューの指摘の直し。上限は変えず、記録 §8 で選択肢を示す）",
            parts=[dict(part_ja="入力条件の変更と較正の掃引・解算の数値の JSON（物理の側）", from_="08:40", to="09:25", hours=0.75),
                   dict(part_ja="美術の誘導の作り直し（引き継ぎ 1〜3、初回の統合と修正 2 回、節点の条件）", from_="08:45", to="11:30", hours=2.75),
                   dict(part_ja="統合（切った版の物理の頂の高さ、seat_toward_wave、描画、証拠、記録、一式）", from_="11:29", to="12:10", hours=0.7)],
            initial_submission=dict(from_="08:40", to="12:10", hours=3.5, days=0.44),
            review=dict(part_ja="レビュー対応（ds_undercut_kstar の名前付け、切った版と入力条件の掃引の物理だけの作り直し、P20 の追加、記録・証拠・図・キット・プレビューの直し）", from_="12:25", to="13:15", hours=0.8),
            total=dict(hours=4.3, days=0.54), ja="2026-09-27、ファイルの時刻から。初回提出の前の 2 つは並べて走らせた。1 回の計算はどれも 30 分以内（生成 8〜13 分、関門 1 回 3.5〜8 分、Unity 1 回 10〜70 秒）")
BACKLOG = dict(ja="計画 §2.1 の設計28 には、対応するバックログの項目番号が書かれていない（時間の上限だけ）。この番号で値を持つもの：t* の原画の関門の回帰の確認（28修正01 と同じ評価器の項目。後退なし、175 は 28修正01 から不合格）と、"
                  "連続性の項目（80・106・107・111。関門 P13 の同じ検査器の値。106 は行の間の伸び 14.2 倍で不合格、107 は面の反転 4 で不合格。設計27 は 10.9 倍・30）。",
               items={"80": "記録のみ（形の切替・欠落 0。座席 v1 の仰角の値は測り直していない）", "106": "不合格（行の間の辺の伸び 14.2 倍。設計27 10.9 倍）", "107": "不合格（面の反転 4。設計27 30）",
                      "111": "記録のみ（唇のすべての列 16,785 点（唇先と上面の 440 点を含む）がすべて重力だけ。設計27 の峰の行の外側の 22 行の問題は解消）", "t* の原画の関門": "後退なし（差の最大 0.247 px、基準 ±0.5 px）"})
HANDOFFS = {
    "1_pull_back": "噴流の始まりの後の押し戻しは、ds_approach_kstar（名前の付いた誘導）で置き換えてなくした：ds26 の較正の噴流の始まり（行の唇先の放出）からは内壁と唇が前へだけ進む（P18 0.167 m で合格）。"
                   "ただし引き戻しは『なくなった』のではなく、半分ほどに小さくなって噴流の始まりの前へ移った：前面が鉛直になった時刻（P7・P17 の起点）から測ると内壁の 0.3H の点は最大 2.97 m 戻り（行 191、τ −2.42 s）、"
                   "133 行中 119 行が 0.3 m を超える（この読みでは P18 は不合格。設計27 は同じ読みで 6.32 m・120 行）。このえぐり（ds_undercut_kstar、レビュー対応で名前を付けた）は K* から決めている。"
                   "シートの上の本体の水（設計27 の −37%・+33% と同じ定義）は 4,873 m³（τ −4.2）→ 3,933 m³（τ −2.8、−19%）→ 4,447 m³（t*、+13%）。P17（前面が鉛直 → t*）：主断面 11.3%（上限 10%）、峰の行 9.5%、巻きの行の最大 11.5%（設計27 は 35%・45%・47%）",
    "2_stage_b_look": "ds_tower_peak（形）と ds_tip_white_line（色だけ）。P19：峰の行の b の θc 107.0°（主断面 108.6°、設計27 128.9°）は numpy の断面の値で、Unity の描画では b は塔に読めない（座席から波の方向で右端の切り立った坂、左の側面で広い丸い山）。"
                      "唇先の白は τ −2.77 s から出るが、拡大して読めるのは約 −2.6 s からの途切れた細い線で、設計28 の段階 c（−2.93 s）にはまだない。d の前への返りはどの Unity の視点にも出ない",
    "3_beyond_peak_lips": "κ < 1 の行は位置の混ぜ合わせをやめ、放出を遅らせて打ち出しを弱め、放出の後は重力だけ。唇先と上面の 440 点、唇のすべての列（ds28_review_checks.json の lips_all）が −9.81 ± 0.5 m/s²（設計27 の行 193〜214 は −9.3 → −0.5）。"
                          "行 207〜214 は打ち出しの補間の終わりから t* までが 0.25 s に届かないので当てはめない",
    "4_physical_crest": "切った版を物理の頂の高さで作った（ds_crest_tower を切る）。レビュー対応で、噴流の始まりの前のえぐり（ds_undercut_kstar）も切った版で切った。P14 と設計26 §1.1 の矛盾は、行ごとの頂の高さ（塔）を名前の付いた美術の誘導 ds_crest_tower とし、"
                        "P15 の a・b（塔）と P19 を入れた版だけで判定することにした。ただし P14 の『切った版も P1〜P13・P15・P16 を通す』は満たさない（物理だけの版は塔と関係のない関門も落とす。記録 §3.3）",
    "5_sim_timing_json": "Tools/GWWaveGen/ds27_user_sim_timing.json を作った（設計26 §7.1 の表の値だけ、出典はファイル名と SHA-256、形・断面・メッシュ・個人のパスなし）。レビュー対応で表の外の 3 つを消した",
}
REVIEW_RESPONSE = [
    dict(id="1_P18", finding_ja="P18 の合格は ds26 の較正の噴流の始まり（唇先の放出）から測る読みだけ。前面が鉛直になった時刻から測ると 2.97 m・119 行で不合格。引き戻しはなくなったのではなく、半分ほどに小さくなって前へ移った",
         action_ja="記録 §0・§4・§5・§7、verdicts.P18、引き継ぎの対応、README の行、コミットの文を『読みで分かれる（記録のみ扱い）』に直した。合格の数から P18 を外した。P18 の起点の選び方を §7 の進行役の決めごとにした。シートの上の本体の水（設計27 の −37%・+33% と同じ定義）を測って足した（review_checks.volume）"),
    dict(id="2_undercut", finding_ja="噴流の始まりの前のえぐり（ds28_model.anchor_q の σ < −2.4 の分岐、K* の張り出しから決める始まりの位置 q_on、K* の錨で頭打ち）が切り替えを見ず、ds_approach_kstar の一部と書かれていた。物理だけの版にも入っていた",
         action_ja="14 個目の名前の付いた誘導 ds_undercut_kstar にした（ds28_physoff.Generator の引数。切ると始まりの張り出し 0 で前面は始まりにちょうど鉛直、K* の錨で頭打ちしない）。P20 に大きさを記録。物理だけの版はこれも切って作り直した（生成・決定性・関門・Unity の描画・GPU の読み戻し）。入れた版のパッケージは変えていない"),
    dict(id="3_sweep_ease_in", finding_ja="入力条件の掃引の『物理だけ』に設計27 の錨の K* への ease-in（τ −2.0 s から）が入っていた。2 つの『物理だけ』の定義が違う",
         action_ja="InputGen に anchor_to_kstar を足し、物理だけ（PHYS）では切って 43 本を測り直した（図 6 枚、Unity の静止画 3 組も）。2 つの定義を metrics.physics_only_definitions と記録 §2.1・§3.3 に書いた"),
    dict(id="4_P20_zero", finding_ja="ds_back_steep・ds_farwall_hold の P20 の 0 は、分けられないのに大きさがないように読める。版の名前で決まる違いに名前がない",
         action_ja="『分けられない』と書き、別の測り方（ds_body_narrow と一緒に・その後に切る、物理だけの版に 1 つだけ入れる）で大きさを測った。版の名前で決まる違い（κ・唇先の列・峰の行・白の最遅）を名前のない誘導として列挙し、大きさを測った（p20.separability・unnamed_version_keyed）"),
    dict(id="5_visible_change", finding_ja="見た目の変化の言い過ぎ：設計27 と 28 の入れた版の画素の差は小さく（原画視点 2.9%・座席から波の方向 6.1%・左の側面 1.3%・座席 v1 1.2%、t* は同じ）、b の塔・c の白・d の返り・引き戻しの消え方は Unity の描画では読めない",
         action_ja="記録 §0・§8、図の説明、コミットの文、利用者向けのプレビューの説明（预览说明.txt）を事実に直した（塔と d と引き戻しは断面の図と水と内壁の図と Fig. 4 の図の 1 段目で見る、白は拡大でだけ、c の時刻にはまだない）。画素の差は同じ方法で測り直して同じ値を得た"),
    dict(id="6_blackout", finding_ja="物理だけの版の座席から波の方向・座席 v1 で f292〜f303 に画面が平らな暗い面に覆われ、f304 で 1 コマで晴れる",
         action_ja="座席の目が物理だけの版の周りの海の下に入るため（設計30 の範囲）と、記録 §5・§8、known_view_issues、プレビューの説明に書いた（作り直した物理だけの版でも同じ）"),
    dict(id="7_sim_json", finding_ja="解算の数値の JSON に設計26 §7.1 の表の外の 3 つ（0.08 s、1.21 s、借りない平行移動の速さ）とコマの番号が入っていた",
         action_ja="3 つとコマの番号を消し、出典の書き方を『§7.1 の表の値だけ』にした。記録 §2.5、コミットの文、metrics の引き継ぎを直し、SHA-256 を run.json・metrics.json で更新した"),
    dict(id="8_P14", finding_ja="記録 §3.3 の P14 の扱いが、切った版が通す関門だけを並べて P14 の範囲に見せていた",
         action_ja="切った版（物理だけ）が落とす塔と関係のない関門（P2・P3・P5・P7・P9・P13・P17・P18）を並べ、P14 の『合格』は設計27 と同じ読み（両方の版があり差を記録）で、『切った版も通す』は満たさないと書いた"),
    dict(id="s_suggestions", finding_ja="任意の提案",
         action_ja="採った：本体の水の時系列、P14 の検査器の値（6.0086、塔を受け継ぐ切った版と組んだ値）の注、唇のすべての列の弾道（16,785 点）と行 207〜214 の除外の理由、ds_crest_tower の置き場（ds28_physoff の引数。ds28_params.json は入れた版のバイトを保つため変えない）、"
                   "横への広がりの換算を設計26 §7.1 の 28〜33 m/s にそろえた、解算では前面が鉛直になるコマと噴流の始まりが同じという事実、座席から波の方向の頂の切れ・右端の崖、最後の 0.5 s の暗い楔、設計27 からある描画の傷、時間曲線の止まり方、時間の上限の書き方、コミットの題、節点の回数の作り直しの記載、"
                   "2 つの物理だけの定義の注、metrics の P14_pair の文の写し間違い、P17〜P19 の定義を §7 へ、ds28_evidence.py の説明、gitattributes の行数。"
                   "採らなかった：内壁の断面のアニメーション・真横のカメラ（損切りの後の新しい描画になるので、断面の図と水と内壁の図で代える。仕上げ28 の候補）"),
]
PHYS_DEFS = dict(
    ja="『物理だけ』は 2 つある。別の生成器なので、t* の差などの値を同じ版として比べない。",
    physoff=dict(where="Tools/GWWaveGen/ds28/ds28_physoff.py → Unity/Build/Design/28/art_off_phys（描画・関門・P20 のすべて切った版）",
                 ja="設計28 の生成器（ds28_model.Generator）の切った版で、名前の付いた美術の誘導 14 個をすべて切る：ds28_model の 12 個＋ds_crest_tower（物理の頂の高さ）＋ds_undercut_kstar（始まりの張り出し 0、前面は始まりにちょうど鉛直）。"
                    "錨は始まりの前に寝た前面 0.67H から始まりの位置（放出の前の帯の一番前の真下）へ寄り、始まりの後はそこに留まる（K* へ寄せない）。名前のない版の名前による違い（κ・唇先の列・峰の行・白の最遅）は art_off の側"),
    inputs_sweep=dict(where="Tools/GWWaveGen/ds28/ds28_inputs_model.py の InputGen（ds28_inputs_run.PHYS）→ Unity/Build/Design/28/inputs",
                      ja="設計27 の生成器（ds27_model.Generator）の切った版（9 個を切る）＋物理の頂の高さ＋唇の打ち出しの cos² の換算。レビュー対応で設計27 の錨の K* への ease-in（τ −2.0 s から）を切った。"
                         "錨は設計27 の表 D(σ)（0.67H から σ −4.6〜−1.1 で頂の真下へ。切った版は 0.02H で止まる）のままで、噴流の始まりの後も σ −1.1 まで後ろへ寄る（K* から決めた値ではないが、始まりの後の戻りである）。入力どうしを比べるための版"),
    note_ja="レビューの前は、掃引の物理だけに設計27 の錨の K* への ease-in が、設計28 の切った版に K* から決めたえぐりが入っていた（Unity/Build/Design/28/review_r0/）")
VIEW_ISSUES = [
    dict(view="seat_toward_wave・座席 v1（切った版＝物理だけ）", frames="f292〜f303（t 9.73〜10.10 s、τ −1.03〜−0.85 s）",
         ja="座席の目（甲板の 1.2 m 上）が物理だけの版の周りの海（静めていない搬送波とシート）の下に入り、画面全体が平らな暗い面に覆われる。f304 で 1 コマで晴れる（コマの差の平均 0.19、前後は約 0.01）。"
            "物理の動きでも描画の不具合でもなく、周りの海の範囲（設計30）。入れた版では起きない"),
    dict(view="seat_toward_wave（全版）", frames="f290 ごろから（τ 約 −1.1 s）、f302 から（τ 約 −0.87 s）",
         ja="縦 70° の水平の視点なので、並べた動画では f290 ごろから頂が 30 px の見出しの帯の下に入り、f302 ごろから画面の上で切れる。唇が飛んで落ちる最後の約 1 s はこの視点では判断できない"),
    dict(view="seat_toward_wave（全版）", frames="段階 a から",
         ja="波の右の端が段階 a から切り立った崖に見える（K* の奥の壁、c > +13 m）。箱の端のように見え、写真 b の両側の峰とは違う。仕上げ（塔）か設計39・40 へ渡す"),
    dict(view="原画視点（設計27・28 とも）", frames="最後の約 0.5 s",
         ja="唇の下の暗い楔が t* にちょうど細い線へ閉じる（唇が K* に端から揃う）。設計27 と同じ。最後の 1 s の『原画へ合わせた』見え方として残る"),
    dict(view="全視点（設計27・28 とも。設計28 で入れたものではない）", frames="—",
         ja="唇の端の梯子・モアレの塊、座席から波の方向の画面に固定した縦の継ぎ目、前面の足の縦の筋、τ −1〜−0.3 s に頂の上で投影された爪の模様が埋まっていくこと、t* ごろの原画視点の左端の横縞。設計29・36・38 の範囲"),
    dict(view="動画の時間曲線（既定）", frames="t* の約 0.33 s 前から",
         ja="画像の変わり方は t* の約 10 コマ前に最も速く、約 0.33 s で 0 まで止まる（設計27 と同じ。D31 は利用者の選択）。急に止まったように見えるかもしれない。代案の曲線は最大の速さのまま t* で止まる"),
]


def write_run(figs, videos):
    """run.json：コマンド、道具の版、入力・出力・スクリプトの SHA-256。"""
    def ver(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO).stdout.splitlines()[0]
        except Exception as e:  # noqa: BLE001
            return "（取得できない：%s）" % e
    import PIL
    scripts = sorted(glob.glob(os.path.join(HERE, "*.py")) + glob.glob(os.path.join(HERE, "*.json")) + glob.glob(os.path.join(HERE, "*.ps1")))
    scripts += [os.path.join(REPO, "Tools", "GWWaveGen", "ds27_user_sim_timing.json"), os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design28", "Editor", "DS28ReviewView.cs")]
    ks = DG.KStar()
    inputs = [os.path.join(REPO, "Docs", "Evidence", "Design", "26", "ds26_conditions.json")] + \
             [os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01", "kstar", f) for f in ("kstar_a45.gwb", "kstar_a45_rows.npz", "kstar_a45_meta.json")] + \
             [os.path.join(DS27, f) for f in ("ds27_model.py", "ds27_params.json", "ds27_gates.py", "ds27_generate.py", "ds27_package.py", "ds27_checks.py", "timewarp_default.json", "timewarp_alt.json",
                                             "ds27_tstar_eval.py", "ds27_player_ref.py", "run_ds27_unity.ps1")] + \
             [os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design27", "Editor", "DS27Formation.cs"), os.path.join(REPO, "Unity", "Assets", "GreatWave", "Scenes", "Tests", "DS27_Formation.unity")] + \
             [os.path.join(EV.PAPER, "img_%d.jpg" % n) for n in (465, 466, 467, 468)]
    pk_out = []
    for v in ("art_on", "art_off_phys", "art_off"):
        for fn in ("ds27_pos_rgba16.bin", "ds27_keypose.json", "ds27_twhite_r32f.bin", "ds27_sea.npz", "ds27_checks.json", "ds28_generate_log.json"):
            pk_out.append(file_rec(os.path.join(B28, v, fn)))
    other_out = [file_rec(p) for p in sorted(glob.glob(os.path.join(B28, "gates", "*.json")) + glob.glob(os.path.join(B28, "p20", "*.json")) +
                                              [os.path.join(B28, "inputs", f) for f in ("ds28_inputs_summary.json", "ds28_inputs_metrics.json", "ds28_inputs_series.npz")] +
                                              glob.glob(os.path.join(B28, "*", "ds27_render_report.json")) + glob.glob(os.path.join(B28, "*", "ds28_review_view_*.json")) +
                                              glob.glob(os.path.join(B28, "*", "ds27_tstar_remeasure.json")) + glob.glob(os.path.join(B28, "*", "ds27_playback_check.json")) +
                                              glob.glob(os.path.join(B28, "*", "video", "*.mp4")) + glob.glob(os.path.join(B28, "review_r0", "gates", "*.json")) +
                                              glob.glob(os.path.join(B28, "inputs", "pkg", "*", "ds27_keypose.json")) + glob.glob(os.path.join(B28, "inputs", "unity", "*", "ds27_render_report.json")))]
    cmds = [
        "（物理の側）py -3.10 -B Tools/GWWaveGen/ds28/ds28_inputs_run.py --jobs 8（43 本、約 7 分。物理だけは錨の K* への ease-in なし）→ py -3.10 -B Tools/GWWaveGen/ds28/ds28_inputs_summary.py",
        "（物理の側、任意）py -3.10 -B Tools/GWWaveGen/ds28/ds28_inputs_package.py --name in_d60_l195（in_d0_l195・in_d120_l195 も）→ run_ds28_unity.ps1 -Method GreatWave.Design27.EditorTools.DS27Formation.RenderOnly -Version art_off -Warp default -Package Build/Design/28/inputs/pkg/<名前> -OutDir Build/Design/28/inputs/unity/<名前> -Stills \"a=-4.2,b=-3.4,c=-2.4,d=-2.05,apex=-1.3,tstar=0\" -Views painting,side_left -Skip video,frames,t28,capture → py -3.10 -B Tools/GWWaveGen/ds28/ds28_inputs_unity_sheet.py",
        "py -3.10 -B Tools/GWWaveGen/ds28/ds28_generate.py --version art_on（art_off も。1 回 10〜13 分）",
        "py -3.10 -B Tools/GWWaveGen/ds28/ds28_physoff.py（切った版＝物理だけ、14 個を切る → Unity/Build/Design/28/art_off_phys、約 9.5 分。--undercut-kstar でレビューの前の切った版）",
        "決定性：py -3.10 -B Tools/GWWaveGen/ds28/ds28_generate.py --version art_on --no-check --no-sea --out Unity/Build/Design/28/_twice（art_off も）、py -3.10 -B Tools/GWWaveGen/ds28/ds28_physoff.py --no-check --no-sea --out Unity/Build/Design/28/_twice",
        "py -3.10 -B Tools/GWWaveGen/ds28/ds28_p20.py → py -3.10 -B Tools/GWWaveGen/ds28/ds28_p20_tower.py（約 6.5 分）",
        "レビュー対応の記録：PYTHONIOENCODING=utf-8 py -3.10 -B Tools/GWWaveGen/ds28/ds28_review_checks.py（シートの上の本体の水、唇のすべての列の弾道 → Unity/Build/Design/28/gates/ds28_review_checks.json）",
        "py -3.10 -B Tools/GWWaveGen/ds28/ds28_gates.py --package Unity/Build/Design/28/<art_on|art_off|art_off_phys> --timewarp Tools/GWWaveGen/ds27/timewarp_<default|alt>.json --sea Unity/Build/Design/28/<同じ>/ds27_sea.npz --out Unity/Build/Design/28/gates/<組>.json [--p20 Unity/Build/Design/28/p20/ds28_p20.json]",
        "py -3.10 -B Tools/GWWaveGen/ds28/ds28_gates_extra.py --package Unity/Build/Design/27/art_on --gates Unity/Build/Design/27/gates/art_on_default.json --out Unity/Build/Design/28/gates/ds27_art_on_default_extra.json",
        "Unity（毎回 powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds28/run_ds28_unity.ps1 …）：-Method GreatWave.Design27.EditorTools.DS27Formation.RenderOnly -Version <版> -Warp <default|alt> -Package Build/Design/28/<包み> -OutDir Build/Design/28/<組> -Views painting,seat,side_left,seat_form",
        "Unity 段階の静止画：… DS27Formation.RenderOnly -OutDir Build/Design/28/<組>_stages -Stills \"a=-4.433,b=-3.500,c=-2.933,d=-2.250,apex=-1.333,tstar=0\" -Skip video,frames,t28,capture（設計27 の入れた版も同じ τ で ref27_art_on_default_stages へ）",
        "Unity 確認用の視点：… -Method GreatWave.Design28.EditorTools.DS28ReviewView.Render -Package <包み> -Warp <default|alt> -OutDir Build/Design/28/<組> -Stills \"a=-4.433,…,tstar=0\" -Extra \"-ds28HideContext 1\"（前景つきの静止画は -Skip video -Extra \"-ds28ViewName seat_toward_wave_ctx\"。設計27 の入れた版は -Package Build/Design/27/art_on -OutDir Build/Design/28/ref27_art_on_default）",
        "照合：py -3.10 -B Tools/GWWaveGen/ds27/ds27_tstar_eval.py --run Unity/Build/Design/28/art_on_<default|alt>、py -3.10 Tools/GWWaveGen/ds27/ds27_player_ref.py check --package Unity/Build/Design/28/<包み> --capture Unity/Build/Design/28/<組>/gpu_capture",
        "証拠：py -3.10 -B Tools/GWWaveGen/ds28/ds28_record.py（この run.json・metrics.json・図・並べた動画。ffmpeg はリポジトリの根で相対パス）",
    ]
    run = dict(schema="GreatWave.DS28.run/1", number="設計28", generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               machine=platform.platform(), python=platform.python_version(), numpy=np.__version__, pillow=PIL.__version__,
               unity="6000.4.3f1（Editor batchmode、PC オフスクリーン描画、RTX 3080、Direct3D11）", ffmpeg=ver([FFMPEG, "-version"]),
               commands=cmds, scripts=[file_rec(p) for p in scripts], inputs=[file_rec(p) for p in inputs], packages=pk_out, build_outputs=other_out,
               evidence=[file_rec(p) for p in sorted(glob.glob(os.path.join(EVID, "*"))) if not p.endswith("run.json")],
               protected_ja="設計26・27 のコミット済みのファイルは変えていない（生成器が SHA-256 を照合：ds27_model.py・ds27_params.json・ds27_gates.py、ds26_conditions.json、K*。Unity の採取が場面と DS27 のファイルの前後の SHA-256 を記録）",
               not_in_repo_ja="パッケージ・描画・動画の元・関門の出力は Git 対象外（Unity/Build/Design/28/）。利用者の高解像度の写真（webp）と解算の形は使っていない")
    with open(os.path.join(EVID, "run.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(run, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
