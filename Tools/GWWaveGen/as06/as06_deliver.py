# -*- coding: utf-8 -*-
"""美術の見本06（Q34）を利用者に渡す図と JSON を Docs/Evidence/ArtSample06 に作る（1920×1080、日本語の見出し）。

描画は描き直さない。Git 対象外の Build/Polish の描画と粘土を並べるだけ。
  前 = 見本05 B（B10）：sample05/fix1/assemble/render/B10
  見本06（勝ち）= 段の行 R9（直しの回の後）：sample06/fix/render/R9（回り台は R9/tt）
  負けの版 = 塊 LB2：粘土だけ（sample06/assemble/clay）
粘土と層の色づけは numpy の z バッファ（rows_clay.py、Unity の描画ではない。爪・船なし）。
図の並べ方の部品（字、貼り付け、原画の表示と ①②③ の線）は as05_deliver.py（変えない）を使う。
使い方：py -3.10 -B Tools/GWWaveGen/as06/as06_deliver.py [all|1|2|3|4|5|6|7|json]
"""
import datetime
import hashlib
import json
import os
import platform
import shutil
import sys

import numpy as np
from PIL import Image

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as05")
import as05_deliver as D  # noqa: E402

HERE = REPO + "/Tools/GWWaveGen/as06"
P = REPO + "/Unity/Build/Polish"
P5 = P + "/sample05"
P6 = P + "/sample06"
PF = P6 + "/fix"
PA = P6 + "/assemble"
OUT = REPO + "/Docs/Evidence/ArtSample06"
D.OUT = OUT
RB10 = P5 + "/fix1/assemble/render/B10"
RR9 = PF + "/render/R9"
CLAY_SRC = {"B10": PF + "/clay", "R8": PF + "/clay", "R9": PF + "/clay", "LB2": PA + "/clay"}
font, paste, tag, load, jl = D.font, D.paste, D.tag, D.load, D.jl
W, H = 1920, 1080

FOOT = ("Unity 6000.4.3f1 の PC オフスクリーン描画（HMD 実機ではない）。t* = 12 s の静止、飛沫なし、波頭の爪なし。"
        "美術が届いたかは利用者が決める（Q29・Q30）。")
FOOT_NP = ("numpy の z バッファの粘土（Unity の描画ではない）。t* = 12 s の静止、爪・船なし。カメラは Unity の描画と同じ。"
           "美術が届いたかは利用者が決める（Q29・Q30）。")
FOOT_RULES = D.FOOT_RULES
VJ = {"painting": "原画視点", "seat": "座席（VR の視点）", "seat_toward_wave": "座席から波の方向", "side_left": "左の側面",
      "side_right": "右の側面", "back65": "後ろ 65°", "top": "真上"}


def vj(v):
    return "回り台 %s°" % v[2:] if v.startswith("tt") else VJ[v]


# ---------------------------------------------------------------- 粘土の切り出し（B10・R9・LB2 の和の枠で同じ枠）
_BOX = {}


def crop_box(v, kinds=("B10", "R9", "LB2"), labels=(1, 2, 3, 4, 5, 8), margin=0.07):
    if v in _BOX:
        return _BOX[v]
    xs0, ys0, xs1, ys1 = [], [], [], []
    for k in kinds:
        p = CLAY_SRC[k] + "/%s_%s_labels.npy" % (k, v)
        if not os.path.isfile(p):
            continue
        D.USED[p] = None
        m = np.isin(np.load(p), labels)
        if not m.any():
            continue
        yy, xx = np.nonzero(m)
        xs0.append(xx.min()); xs1.append(xx.max()); ys0.append(yy.min()); ys1.append(yy.max())
    Hh, Ww = 540, 960
    if not xs0:
        _BOX[v] = (0, 0, Ww, Hh)
        return _BOX[v]
    a, b, c, e = min(xs0), min(ys0), max(xs1), max(ys1)
    w = (c - a) * (1 + 2 * margin); h = (e - b) * (1 + 2 * margin)
    if w / h < 16 / 9:
        w = h * 16 / 9
    else:
        h = w * 9 / 16
    w = min(w, Ww); h = min(h, Hh)
    cx, cy = (a + c) / 2, (b + e) / 2
    x0 = int(np.clip(cx - w / 2, 0, Ww - w)); y0 = int(np.clip(cy - h / 2, 0, Hh - h))
    _BOX[v] = (x0, y0, int(x0 + w), int(y0 + h))
    return _BOX[v]


def clay(kind, v, mode):
    return load(CLAY_SRC[kind] + "/%s_%s_%s.png" % (kind, v, mode)).crop(crop_box(v))


def sep_text(v):
    x = jl(PF + "/measure/targets_R9.json")["separation_views"].get(v)
    if not x:
        return ""

    def one(pk, lab):
        s = x["pairs"][pk]["separated"]
        return "%s %s" % (lab, "片方が見えない" if s is None else ("分かれる" if s else "続く"))
    return "R9 の層の分かれ：" + "　".join(one(pk, lab) for pk, lab in (("1-2", "①②"), ("2-3", "②③")))


# ---------------------------------------------------------------- 1 形が先：粘土（見本05 B と見本06 を並べる）
V8 = ["side_left", "side_right", "top", "back65", "tt0", "tt30", "tt90", "tt300"]


def sheet1():
    xs = [10, 482, 966, 1438]
    cw, chh = 468, 226
    y0 = 106
    pitch = 235
    for mode, nm, ttl, sub in (
            ("clay", "as06_1a_shape_clay.png", "美術の見本06：形が先（色なしの粘土）　見本05 B｜見本06 を同じ視点で",
             "色なしの粘土（一つの灰色に固定の光の陰影、黒い線 = 遮る縁）。主役波 ＋ 左端の青い波 wave4 ＋ 近い海。色・爪・船なし。\n"
             "二枚一組 = 左 見本05 B（前）・右 見本06（段の行 R9）。② b区域と ③ 最も左の小さな区域を、① から左下へ下りる段にした（Q34 の答え B = 段）"),
            ("tint", "as06_1b_shape_layers.png", "美術の見本06：形が先（三つの層の色づけ）　見本05 B｜見本06 を同じ視点で",
             "三つの層の色づけ：赤 ① 浪尖・緑 ② b区域・水色 ③ 最も左の小さな区域・灰 本体・青 wave4。印は測るための物で材質の色ではない。爪・船なし。\n"
             "二枚一組 = 左 見本05 B（前）・右 見本06（段の行 R9）。層の印はそれぞれの作りの行の c の帯（見本05 B の ②③ の段の窓は 2.0 m・1.4 m、見本06 は ② 6.9 m・③ 7.8 m）")):
        img, d = D.new_sheet(ttl, sub)
        for i, v in enumerate(V8):
            r, pr = divmod(i, 2)
            y = y0 + r * pitch
            for j, kind in enumerate(("B10", "R9")):
                x = xs[pr * 2 + j]
                lab = ("見本05 B" if kind == "B10" else "見本06") + " ／ " + vj(v)
                paste(img, d, clay(kind, v, mode), x, y, cw, chh, lab, 16)
        d.line((958, y0, 958, y0 + 4 * pitch - 10), fill=(150, 150, 150), width=2)
        D.finish(img, d, nm, FOOT_NP)


# ---------------------------------------------------------------- 2 見本06 の粘土の回り台 12 方位
def grid12(name, title, sub, getter, foot, caption=None):
    img, d = D.new_sheet(title, sub)
    cw, chh = 470, 264
    y0 = 106 if sub.count("\n") < 1 else 128
    gap = 40 if caption else 30
    for i, az in enumerate(range(0, 360, 30)):
        r, c = divmod(i, 4)
        x = 8 + c * 478
        y = y0 + r * (chh + gap)
        paste(img, d, getter(az), x, y, cw, chh, "回り台 %d°" % az, 17)
        if caption:
            d.text((x + 4, y + chh + 4), caption(az), font=font(15, True), fill=(40, 40, 40))
    return img, d


def sheet2():
    img, d = grid12("as06_2_clay_turntable.png", "美術の見本06：粘土の回り台 12 方位（段の行 R9）",
                    "色なしの粘土（爪・船なし）。カメラは Unity の回り台と同じ（30° ごと）。下の字は 15 視点の層の分かれの測り（targets_R9.json、"
                    "①② と ②③ が遮る縁で分かれるか）",
                    lambda az: clay("R9", "tt%d" % az, "clay"), FOOT_NP, caption=lambda az: sep_text("tt%d" % az))
    D.finish(img, d, "as06_2_clay_turntable.png", FOOT_NP)


# ---------------------------------------------------------------- 3 原画視点
def sheet3():
    pd = D.painting_disp()
    regs = D.regions_disp()
    srcs = [("原画", pd), ("見本05 B", load(RB10 + "/views/painting_t120_claws.png")),
            ("見本06（段の行 R9）", load(RR9 + "/views/painting_t120_claws.png"))]
    img, d = D.new_sheet("美術の見本06：原画視点　原画｜見本05 B｜見本06",
                         "線：赤 ① 浪尖（頂と唇）・緑 ② b区域・水色 ③ 最も左の小さな区域（利用者が確かめた範囲）。桃の四角 = 利用者の切り出し（唇の下の内の縁、T6）。\n"
                         "下の段：左側の拡大（③ の区域・② の左の端・左端の青い波 wave4）。材質 AS05、面の内の爪 25・近い海の爪 10、波頭の爪なし。同じカメラ・同じ時刻 t*")
    xs = [10, 646, 1282]
    cw, ch = 628, 353
    for k, (nm, im) in enumerate(srcs):
        paste(img, d, D.outlined(im, regs, 5), xs[k], 106, cw, ch, nm, 19)
    for k, (nm, im) in enumerate(srcs):
        z = D.outlined(im, regs, 3).crop(D.LEFT_BOX)
        paste(img, d, z, xs[k], 472, cw, 547, "%s ／ 左側の拡大" % nm, 18)
    D.finish(img, d, "as06_3_painting_view.png",
             "Unity 6000.4.3f1 の PC 描画（HMD 実機ではない）。見本06 の一艘目の船は原画のカメラを中心とする相似 0.6 で手前（原画視点の画は画素まで同じ。Q34）。"
             "美術が届いたかは利用者が決める。")


# ---------------------------------------------------------------- 4 平らな塗り（爪なし）6 視点
def sheet4():
    views = ["seat", "seat_toward_wave", "top", "side_left", "side_right", "back65"]
    img, d = D.new_sheet("美術の見本06：平らな塗り（材質 AS05・爪なし）6 視点（段の行 R9）",
                         "爪を外した Unity の描画。座席は右の船（唇の真下の船）の上。原画視点以外の視点では一艘目の船は相似 0.6 の大きさ（Q34、差し込み合いは後で）。")
    xs = [10, 646, 1282]
    cw, ch = 628, 353
    for i, v in enumerate(views):
        r, c = divmod(i, 3)
        paste(img, d, load(RR9 + "/views/%s_t120_clawfree.png" % v), xs[c], 104 + r * (ch + 14), cw, ch, vj(v), 19)
    note = ["見方（係の目。判定ではない）：",
            "・座席・座席から波の方向：② ③ の段は白い縁の棚として見える。細い白の切れ端の測り（fix6_slivers.py）では座席の視点に一つある（R8 0 → R9 1）。",
            "・左右の側面・後ろ 65°・真上：カメラが波の後ろ側を見るので、三つの段はほとんど読めない（見本05 B とほぼ同じ）。粘土の真上では ② ③ が二つの細い舌に見える。",
            "・材質の上では段の体は藍で、藍の海の上に乗るので、段を読ませているのは主に白い縁。体の藍の濃淡は平らな塗り（T5）の約束で付けていない。"]
    y = 104 + 2 * (ch + 14) + 6
    for ln in note:
        d.text((14, y), ln, font=font(19, ln.endswith("：")), fill=(30, 30, 30))
        y += 30
    D.finish(img, d, "as06_4_material_noclaws.png", FOOT)


# ---------------------------------------------------------------- 5 材質の回り台 12 方位（爪なし）
def sheet5():
    img, d = grid12("as06_5_material_turntable.png", "美術の見本06：材質の回り台 12 方位（材質 AS05・爪なし、段の行 R9）",
                    "Unity の回り台（30° ごと）。回り台の画には船を入れていない。爪ありの回り台と前の版との並べは Build（sample06/fix/sheets/fix6_6*）にある",
                    lambda az: load(RR9 + "/tt/t120_az%03d_noclaws.png" % az), FOOT)
    D.finish(img, d, "as06_5_material_turntable.png", FOOT)


# ---------------------------------------------------------------- 6 測る規則
RULES = {"B10": P5 + "/rules_check_B.json", "R8": P6 + "/rules_check_rows_before_fix.json",
         "R9": P6 + "/rules_check_rows.json", "LB2": P6 + "/rules_check_lobes.json"}
COLS = (("B10", "見本05 B（B10、前）"), ("R9", "見本06 段の行 R9（勝ち）"), ("LB2", "負けの版 塊 LB2（参考）"))


def rule_rows():
    def sm(r, k):
        return r["summary"].get(k, "—")

    def g2(r):
        g = r["rules"]["G2"]["gates"]
        return "78 %.2f・130 %.2f・131 %.2f・132σ12 %.2f・72σ12 p95 %.2f px" % (
            g["78"]["claws"], g["130"]["claws"], g["131"]["claws"], g["132_s12"]["claws"], g["72_s12_p95"]["claws"])

    def s11(r):
        t = r["rules"]["S11"]["targets"]
        must = [k for k, v in t.items() if v["kind"] == "must"]
        bad = [k for k in must if not t[k].get("pass")]
        return "must %d/%d　否：%s" % (len(must) - len(bad), len(must), "・".join(bad) if bad else "なし")

    def g1(r):
        return "伸びの三角形 %d" % r["rules"]["G1"]["surface_stretch_where"]["this_mesh"]["patterned_tri_w_outside"]

    def t5(r):
        return "原画視点 %s・全視点 %s" % (r["rules"]["T5"]["painting_body_blobs_excluding_boat_edges"], r["rules"]["T5"]["all_views_total"])

    def c3(r):
        c = r["rules"]["C3"]
        v = c["painting_visible_frac_p10_p50_min"]
        v = v.get("S04", list(v.values())[0]) if isinstance(v, dict) else v
        return "IoU p10 %.3f・見える割合 p10 %.2f・最小 %.2f" % (c["iou_painting_p10_p50_min_sample02"][0], v[0], v[2])

    return [("G1 投影なし・伸びなし", lambda r: "%s　%s" % (sm(r, "G1"), g1(r))),
            ("G2 原画視点の輪郭の関門", lambda r: "%s　%s" % (sm(r, "G2"), g2(r))),
            ("S4 背は一つの山", lambda r: sm(r, "S4")), ("S8 黄色の輪の中に出っ張りなし", lambda r: sm(r, "S8")),
            ("S9 左の白は低い・④ は wave4", lambda r: sm(r, "S9")), ("S10 頂の幅（行 c −8 m 以上）", lambda r: sm(r, "S10")),
            ("S11 三つの層（目標は進行役の既定）", lambda r: "%s　%s" % (sm(r, "S11"), s11(r))),
            ("T5 本体の白い粒", lambda r: "%s　%s" % (sm(r, "T5"), t5(r))),
            ("T6 内の縁に白なし", lambda r: "%s　切り出しの白・水色 %.2f" % (sm(r, "T6"), r["rules"]["T6"]["painting_crop_pale_share"])),
            ("C2・C3 爪（原画視点）", lambda r: "%s・%s　%s" % (sm(r, "C2"), sm(r, "C3"), c3(r))),
            ("K-top いちばん高い峰", lambda r: sm(r, "K-top")),
            ("K-boat 一艘目の船（記録）", lambda r: "%s　船の画素 %.2f 倍" % (sm(r, "K-boat"), r["rules"]["K-boat"]["ratio"]))]


def sheet6():
    R = {k: jl(p) for k, p in RULES.items()}
    img, d = D.new_sheet("美術の見本06：測る規則（見本05 B｜見本06 段の行 R9｜負けの版 塊 LB2）",
                         "同じ測りの鎖（rules_check_*.json）。「合」は測れる規則を通るかだけで、美術の良し悪しの判定ではない。見本06 の規則の全文は rules_check.json")
    xs = [14, 380, 890, 1400]
    y = 104
    for x, t in zip(xs, ("規則",) + tuple(c[1] for c in COLS)):
        d.text((x, y), t, font=font(19, True), fill=(0, 0, 0))
    y += 34
    for lab, fn in rule_rows():
        d.line((10, y - 6, 1910, y - 6), fill=(220, 220, 220))
        d.text((xs[0], y), lab, font=font(17, True), fill=(0, 0, 0))
        for x, (k, _) in zip(xs[1:], COLS):
            try:
                s = fn(R[k])
            except Exception as e:  # noqa: BLE001
                s = "—（%s）" % type(e).__name__
            s = s.replace("pass", "合").replace("fail", "否")
            col = (190, 20, 20) if "否" in s.split("　")[0] else (20, 20, 20)
            for j, ln in enumerate(wrap(d, s, font(16), 480)[:3]):
                d.text((x, y + j * 21), ln, font=font(16), fill=col)
        y += 70
    notes = ["注：C3 の見える割合の最小 0.32 は爪 claw057（② の頭を太くしたので ② の白の後ろに隠れた）。p10 では合だが、爪の回で据え直す。",
             "注：S11 の否 P1-cells は ③ の区域の升ごとの藍の並び（原画の ③ は爪の群れが区域に散る）。形の白の帯では合わせられないので、爪・材質の回へ回す。",
             "注：K-boat は記録。見本06 は一艘目の船を原画のカメラを中心とする相似 0.6 で手前へ動かした（原画視点の画素は同じ、ほかの視点では 0.6 倍。Q34）。"]
    for ln in notes:
        d.text((14, y + 4), ln, font=font(17), fill=(40, 40, 40))
        y += 26
    D.finish(img, d, "as06_6a_rules.png", FOOT_RULES)

    img, d = D.new_sheet("美術の見本06：三つの層の目標 S11（targets.json の値は進行役の既定で、利用者の言葉ではない）",
                         "見本05 B｜直す前 R8｜見本06 R9｜負けの版 LB2。層の印はそれぞれの作りの決め方なので、印を使う目標（L6）は作りの間で決め方が違う。赤 = 否")
    tt = {k: R[k]["rules"]["S11"]["targets"] for k in R}
    xs = [14, 290, 640, 900, 1160, 1420, 1680]
    y = 104
    for x, t in zip(xs, ("目標", "基準", "見本05 B", "直す前 R8", "見本06 R9", "負け LB2", "種類")):
        d.text((x, y), t, font=font(18, True), fill=(0, 0, 0))
    y += 30
    for k in tt["R9"]:
        pf = tt["R9"][k]["pass_if"]
        d.text((xs[0], y), k, font=font(15, True), fill=(0, 0, 0))
        crit = fmt(pf.get("value")) if pf.get("op") == "ranges" else "%s %s" % ({">=": "≧", "<=": "≦"}.get(pf.get("op"), pf.get("op")), fmt(pf.get("value")))
        for j, ln in enumerate(wrap(d, crit, font(14), 330)[:3]):
            d.text((xs[1], y + j * 18), ln, font=font(14), fill=(40, 40, 40))
        for x, kk in zip(xs[2:6], ("B10", "R8", "R9", "LB2")):
            e = tt[kk].get(k, {})
            v = e.get("value")
            ok = e.get("pass")
            for j, ln in enumerate(wrap(d, ("合 " if ok else "否 ") + fmt(v), font(14), 250)[:3]):
                d.text((x, y + j * 18), ln, font=font(14), fill=(20, 20, 20) if ok else (190, 20, 20))
        d.text((xs[6], y), tt["R9"][k]["kind"], font=font(14), fill=(40, 40, 40))
        y += 24 if not isinstance(tt["R9"][k].get("value"), dict) and pf.get("op") != "ranges" else 44
        if y > 1030:
            break
    D.finish(img, d, "as06_6b_s11_targets.png", FOOT_RULES)


KEYJ = {"indigo": "藍", "mizuiro": "水色", "white": "白", "white+mizuiro": "白＋水色", "boat": "船", "cells": "升",
        "indigo_share_mae": "藍の差", "pearson_r": "相関"}


def fmt(v):
    if isinstance(v, dict):
        return "・".join("%s %s" % (KEYJ.get(k, k), fmt(x)) for k, x in v.items())
    if isinstance(v, (list, tuple)):
        return "〜".join(fmt(x) for x in v)
    if isinstance(v, float):
        return ("%.3f" % v).rstrip("0").rstrip(".") if abs(v) < 100 else "%.1f" % v
    return str(v)


def wrap(d, s, f, wpx):
    """区切り（・、空白）で折る。"""
    out, cur = [], ""
    toks = []
    t = ""
    for ch in s:
        t += ch
        if ch in "・　 ":
            toks.append(t); t = ""
    if t:
        toks.append(t)
    for tk in toks:
        if cur and d.textlength(cur + tk, font=f) > wpx:
            out.append(cur.rstrip()); cur = tk
        else:
            cur += tk
    if cur:
        out.append(cur.rstrip())
    return out


# ---------------------------------------------------------------- 7 負けの版（塊 LB2）の粘土
def sheet7():
    views = ["painting", "seat", "top", "side_left", "side_right", "back65", "tt0", "tt30", "tt90", "tt270", "tt300", "tt330"]
    img, d = D.new_sheet("美術の見本06：負けの版（塊 LB2）の粘土（参考）",
                         "② ③ を丸い塊（体のある段）にした版。批評で負け：指・こぶに見え、伸びの三角形 845（G1 否）、② の区域の左の半分しか覆わない（L6-label r2 0.37）。"
                         "\n勝ちの段の行 R9 には、LB2 の太い頭と前へ傾く下の面を取り入れた。色なしの粘土、爪・船なし。枠は見本06 の図と同じ")
    for i, v in enumerate(views):
        r, c = divmod(i, 4)
        paste(img, d, clay("LB2", v, "clay"), 8 + c * 478, 128 + r * 300, 470, 264, "LB2 ／ " + vj(v), 17)
    D.finish(img, d, "as06_7_losing_build_clay.png", FOOT_NP)


# ---------------------------------------------------------------- JSON
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return p.replace(REPO + "/", "")


def write_json():
    os.makedirs(OUT, exist_ok=True)
    shutil.copyfile(RULES["R9"], OUT + "/rules_check.json")
    D.USED[RULES["R9"]] = None
    m = {"schema": "GreatWave.AS06.metrics/1", "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
         "note_ja": "美術の見本06（Q34）の主な数。見本06 = 段の行 R9（直しの回の後）。前 = 見本05 B（B10）、直す前 = R8（組み立ての描画 R8A）、"
                    "負けの版 = 塊 LB2。目標の値は進行役の既定で、利用者の言葉ではない。美術が届いたかは利用者が決める",
         "variants": {}}
    for k, p in RULES.items():
        r = jl(p)
        rr = r["rules"]
        g = rr["G2"]["gates"]
        m["variants"][k] = {
            "rules_source": rel(p), "summary": r["summary"],
            "G1_patterned_tri_w_outside": rr["G1"]["surface_stretch_where"]["this_mesh"]["patterned_tri_w_outside"],
            "G2_gates_px": {x: g[x]["claws"] for x in ("78", "130", "131", "132_s12", "72_s12_p95")},
            "S11_must_pass": rr["S11"]["must_pass"], "S11_must_fail_ids": rr["S11"]["must_fail_ids"],
            "S11_targets": {t: {"value": v.get("value"), "pass": v.get("pass"), "kind": v.get("kind")} for t, v in rr["S11"]["targets"].items()},
            "T5_painting_body_blobs": rr["T5"]["painting_body_blobs_excluding_boat_edges"], "T5_all_views_total": rr["T5"]["all_views_total"],
            "T6_crop_pale_share": rr["T6"]["painting_crop_pale_share"],
            "C3_iou_p10_p50_min": rr["C3"]["iou_painting_p10_p50_min_sample02"], "K_boat_ratio": rr["K-boat"].get("ratio")}
    m["separation_15views"] = {
        "B10": jl(P5 + "/fix1/assemble/measure/targets_B10.json")["separation_summary"],
        "R8": jl(PA + "/measure/targets_R8A.json")["separation_summary"],
        "R9": jl(PF + "/measure/targets_R9.json")["separation_summary"],
        "LB2": jl(PA + "/measure/targets_LB2A.json")["separation_summary"]}
    fx = jl(PF + "/measure/fix_items.json")
    m["critic_fix_items_R8_to_R9"] = fx["items"]
    ck = jl(PF + "/check/fix6_check.json")
    m["fix_checks"] = {k: ck[k] for k in ck if k in ("interpenetration_hero_wave4", "g1_stretch", "painting_claw_visibility_unity", "boat_left_unity_ids")}
    m["section_numbers_R9"] = rel(PF + "/measure/prof_R9.json")
    m["clay_report"] = rel(PF + "/clay/clay_report.json")
    with open(OUT + "/metrics.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(m, f, ensure_ascii=False, indent=1)
    run = {"schema": "GreatWave.AS06.deliver_run/1", "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
           "note_ja": "Docs/Evidence/ArtSample06 の図と JSON を作った記録。描画は描き直していない（Git 対象外の Build/Polish の描画と粘土を並べた）。"
                      "粘土と層は numpy の z バッファ。git の add・commit・push はしていない",
           "commands": ["py -3.10 -B Tools/GWWaveGen/as06/as06_deliver.py all"],
           "python": platform.python_version(), "numpy": np.__version__,
           "tools": {rel(p): sha(p) for p in (HERE + "/as06_deliver.py", REPO + "/Tools/GWWaveGen/as05/as05_deliver.py")},
           "upstream_runs": {rel(p): sha(p) for p in (PF + "/run.json", PA + "/run.json", P6 + "/lobes/run.json") if os.path.isfile(p)},
           "inputs": {rel(p): sha(p) for p in sorted(D.USED) if os.path.isfile(p)},
           "outputs": {rel(p): sha(p) for p in D.OUTS + [OUT + "/metrics.json", OUT + "/rules_check.json"]},
           "not_in_docs_ja": "彫刻の写真・写真から作った画像・利用者の画像とマスクは入れていない。①②③ の範囲は多角形の線だけ"}
    with open(OUT + "/run.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(run, f, ensure_ascii=False, indent=1)
    print("JSON done", flush=True)


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else "all"
    for k, f in (("1", sheet1), ("2", sheet2), ("3", sheet3), ("4", sheet4), ("5", sheet5), ("6", sheet6), ("7", sheet7)):
        if only in ("all", k):
            f()
    if only in ("all", "json"):
        write_json()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
