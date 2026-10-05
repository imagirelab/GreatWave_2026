# -*- coding: utf-8 -*-
"""美術の見本06 の組み立て（Q34）：前（見本05 B = B10）と後（段の行 R8・塊 LB2）を同じ視点で並べた図（1920×1080、日本語の見出し）。
as05/as05_deliver.py（変えない）の描き方の関数（font・fit・tag・paste・原画の表示・①②③ の線・粘土の切り取り）を読み込んで使う。

使う描画（Git 対象外、この道具は描き直さない）：
  B10 = Build/Polish/sample05/fix1/assemble/render/B10（爪なしの回り台は B10_ttnc を B10/tt へ写した物）。一艘目の船は元の所（見本05 B は動かしていない）
  R8  = Build/Polish/sample06/assemble/render/R8A（段の行の作りの R8 と画素まで同じ。船は相似 0.6）
  LB2 = Build/Polish/sample06/assemble/render/LB2A（塊の作りの LB2 から、船を相似 0.6 に、claw074 を手前へ。asm6_claws.py）
粘土と層の色づけ = Build/Polish/sample06/assemble/clay（rows_clay.py の numpy の z バッファ。Unity の描画ではない。船・爪なし）。
出力：Build/Polish/sample06/assemble/sheets/asm6_*.png
使い方：py -3.10 -B Tools/GWWaveGen/as06/asm6_sheets.py [all|1|2|3|4|5|6|7|8]
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as05")
import as05_deliver as D  # noqa: E402

P = REPO + "/Unity/Build/Polish"
PA = P + "/sample06/assemble"
D.OUT = PA + "/sheets"
D.CLAY = PA + "/clay"
RB10 = P + "/sample05/fix1/assemble/render/B10"
KINDS = (("B10", "前：見本05 B（B10）", RB10), ("R8", "段の行（R8）", PA + "/render/R8A"), ("LB2", "塊（LB2）", PA + "/render/LB2A"))
D.KINDS = KINDS
FOOT = ("Unity 6000.4.3f1 の PC オフスクリーン描画（HMD 実機ではない）。t* = 12 s の静止、飛沫なし、波頭の爪なし。"
        "R8・LB2 の一艘目の船は相似 0.6 で手前（原画視点の画は同じ）。美術が届いたかは利用者が決める（Q29・Q30）。")
FOOT_NP = D.FOOT_NP
FOOT_RULES = D.FOOT_RULES
font, paste, tag, fit, load = D.font, D.paste, D.tag, D.fit, D.load


def grid(name, title, sub, cols, getter, foot, cw=470, chh=264):
    """行 = KINDS（B10・R8・LB2）、列 = cols。getter(kind, render_dir, col) -> PIL 画像。"""
    img, d = D.new_sheet(title, sub)
    n = len(cols)
    gx = (1920 - 16) // n
    y0 = 108 if not sub or sub.count("\n") < 1 else 132
    cw = min(cw, gx - 8, int(((1040 - y0) / 3 - 14) * 16 / 9))
    chh = int(round(cw * 9 / 16))
    gap = (1040 - y0 - 3 * chh) // 3
    for r, (kind, nm, rd) in enumerate(KINDS):
        for k, (cv, cl) in enumerate(cols):
            x = 8 + k * gx
            y = y0 + r * (chh + gap)
            paste(img, d, getter(kind, rd, cv), x, y, cw, chh, "%s ／ %s" % (nm, cl), 17)
    D.finish(img, d, name, foot)


def sheet1():
    pd = D.painting_disp()
    regs = D.regions_disp()
    srcs = [("原画", pd)] + [(nm, load(r + "/views/painting_t120_claws.png")) for _, nm, r in KINDS]
    img, d = D.new_sheet("美術の見本06：原画視点（爪あり）　原画｜前 見本05 B｜段の行 R8｜塊 LB2",
                         "線：赤 ① 浪尖（頂と唇）・緑 ② b区域・水色 ③ 最も左の小さな区域（利用者が確かめた範囲）。桃の四角 = 利用者の切り出し（唇の下の内の縁、T6）\n"
                         "下の段：左側の拡大（③ の区域・② の左の端・左端の青い波 wave4）。同じカメラ・同じ時刻 t*。波頭の爪（浪尖）は出していない（Q33）")
    cw, ch = 470, 264
    for k, (nm, im) in enumerate(srcs):
        x = 8 + k * 478
        paste(img, d, D.outlined(im, regs, 5), x, 104, cw, ch, nm, 19)
    for k, (nm, im) in enumerate(srcs):
        x = 8 + k * 478
        z = D.outlined(im, regs, 3).crop(D.LEFT_BOX)
        paste(img, d, z, x, 404, cw, 409, "%s ／ 左側の拡大" % nm, 18)
    note = ("見方：段の行（R8）は ②・③ を行ごとの断面で作った段（縁の頂・丸い唇・唇の下の凹み・下の体の面）。塊（LB2）は ②・③ を断面の距離の場の塊で作り、"
            "\n本体へ丸く合わせた段。どちらも ①（行 c −8 m 以上）・背・wave4・材質 AS05 は見本05 B と同じ。一艘目の船は R8・LB2 とも相似 0.6 で手前（原画視点の画は同じ）。")
    yy = 830
    for line in note.split("\n"):
        d.text((14, yy), line, font=font(19), fill=(40, 40, 40))
        yy += 27
    D.finish(img, d, "asm6_1_painting_view.png", FOOT)

    # 1b：原画視点の爪なし（形だけ）
    srcs = [("原画", pd)] + [(nm, load(r + "/views/painting_t120_clawfree.png")) for _, nm, r in KINDS]
    img, d = D.new_sheet("美術の見本06：原画視点（爪なし）　原画｜前 見本05 B｜段の行 R8｜塊 LB2",
                         "爪なしの描画（面の内の爪 25・近い海の爪 10 を外した）。下の段は左側の拡大。線は上と同じ")
    for k, (nm, im) in enumerate(srcs):
        x = 8 + k * 478
        paste(img, d, D.outlined(im, regs, 5), x, 104, cw, ch, nm, 19)
    for k, (nm, im) in enumerate(srcs):
        x = 8 + k * 478
        z = D.outlined(im, regs, 3).crop(D.LEFT_BOX)
        paste(img, d, z, x, 404, cw, 409, "%s ／ 左側の拡大" % nm, 18)
    D.finish(img, d, "asm6_1b_painting_view_noclaws.png", FOOT)


def clay_get(mode):
    def g(kind, rd, v):
        return D.clay_img(kind, v, mode)
    return g


def sheet2():
    sub = ("色なしの粘土（一つの灰色に固定の光の陰影、黒い線 = 遮る縁）。主役波 ＋ 左端の青い波 wave4 ＋ 近い海。爪・船なし。行 = 前 見本05 B｜段の行 R8｜塊 LB2")
    v1 = [("painting", "原画視点"), ("seat", "座席"), ("seat_toward_wave", "座席から波"), ("top", "真上")]
    v2 = [("side_left", "左の側面"), ("side_right", "右の側面"), ("back65", "後ろ 65°"), ("tt330", "回り台 330°")]
    grid("asm6_2a_clay.png", "美術の見本06：粘土（色なし・爪なし）1/2", sub, v1, clay_get("clay"), FOOT_NP)
    grid("asm6_2b_clay.png", "美術の見本06：粘土（色なし・爪なし）2/2", sub, v2, clay_get("clay"), FOOT_NP)
    subt = ("三つの層の色づけ（赤 ① 浪尖・緑 ② b区域・水色 ③ 最も左の小さな区域・灰 本体・青 wave4）。層の印はそれぞれの作りの決め方（R8 は行の c の帯、"
            "\nLB2 は塊の距離の場）。印は測りのための物で、材質の色ではない。爪・船なし")
    grid("asm6_2c_layers.png", "美術の見本06：三つの層の色づけ 1/2", subt, v1, clay_get("tint"), FOOT_NP)
    grid("asm6_2d_layers.png", "美術の見本06：三つの層の色づけ 2/2", subt, v2, clay_get("tint"), FOOT_NP)


def sheet3():
    sub = "色なしの粘土の回り台（爪・船なし）。カメラは Unity の回り台と同じ。行 = 前 見本05 B｜段の行 R8｜塊 LB2"
    for i, azs in enumerate(((0, 30, 60, 90), (120, 150, 180, 210), (240, 270, 300, 330))):
        grid("asm6_3%s_clay_turntable.png" % "abc"[i], "美術の見本06：粘土の回り台 %d/3" % (i + 1), sub,
             [("tt%d" % a, "回り台 %d°" % a) for a in azs], clay_get("clay"), FOOT_NP)
    subt = "三つの層の色づけの回り台（赤 ①・緑 ②・水色 ③・灰 本体・青 wave4）。爪・船なし"
    for i, azs in enumerate(((0, 30, 60, 90), (120, 150, 180, 210), (240, 270, 300, 330))):
        grid("asm6_3%s_layers_turntable.png" % "def"[i], "美術の見本06：層の色づけの回り台 %d/3" % (i + 1), subt,
             [("tt%d" % a, "回り台 %d°" % a) for a in azs], clay_get("tint"), FOOT_NP)


def view_get(cond):
    def g(kind, rd, v):
        return load(rd + "/views/%s_t120_%s.png" % (v, cond))
    return g


def sheet4():
    v1 = [("seat", "座席（VR の視点）"), ("seat_toward_wave", "座席から波の方向"), ("top", "真上")]
    v2 = [("side_left", "左の側面"), ("side_right", "右の側面"), ("back65", "後ろ 65°")]
    for cond, cj, ab in (("clawfree", "爪なし", "ab"), ("claws", "爪あり", "cd")):
        sub = "平らな塗り（材質 AS05）・%s。行 = 前 見本05 B｜段の行 R8｜塊 LB2。同じカメラ・同じ時刻 t*" % cj
        grid("asm6_4%s_material_%s.png" % (ab[0], cond), "美術の見本06：材質の 6 視点（%s）1/2" % cj, sub, v1, view_get(cond), FOOT, cw=630)
        grid("asm6_4%s_material_%s.png" % (ab[1], cond), "美術の見本06：材質の 6 視点（%s）2/2" % cj, sub, v2, view_get(cond), FOOT, cw=630)


def crest_get(cond):
    def g(kind, rd, az):
        return load(rd + "/crest/t120_az%03d_%s.png" % (az, cond))
    return g


def sheet5():
    for cond, cj, ab in (("clawfree", "爪なし", "ab"), ("claws", "爪あり", "cd")):
        sub = "波頭（いちばん高い峰）の回り台 8 方位（中心 −6.63, 16.5, −3.27・距離 34 m・仰角 5°・画角 35°、平らな海は隠す）・%s" % cj
        for i, azs in enumerate(((0, 45, 90, 135), (180, 225, 270, 315))):
            grid("asm6_5%s_crest_%s.png" % (ab[i], cond), "美術の見本06：波頭の回り台（%s）%d/2" % (cj, i + 1), sub,
                 [(a, "波頭 %d°" % a) for a in azs], crest_get(cond), FOOT)


def tt_get(cond):
    def g(kind, rd, az):
        return load(rd + "/tt/t120_az%03d_%s.png" % (az, cond))
    return g


def sheet6():
    for cond, cj, abc in (("noclaws", "爪なし", "abc"), ("claws", "爪あり", "def")):
        sub = "回り台 12 方位（材質 AS05・%s。回り台の画には船を入れていない）。行 = 前 見本05 B｜段の行 R8｜塊 LB2" % cj
        for i, azs in enumerate(((0, 30, 60, 90), (120, 150, 180, 210), (240, 270, 300, 330))):
            grid("asm6_6%s_turntable_%s.png" % (abc[i], cond), "美術の見本06：材質の回り台（%s）%d/3" % (cj, i + 1), sub,
                 [(a, "回り台 %d°" % a) for a in azs], tt_get(cond), FOOT)


def jl(p):
    return D.jl(p)


def sheet7():
    rb = jl(P + "/sample05/rules_check_B.json")
    rr = jl(P + "/sample06/rules_check_rows.json")
    rl = jl(P + "/sample06/rules_check_lobes.json")
    ck = jl(PA + "/check/asm6_check.json")
    img, d = D.new_sheet("美術の見本06：測る規則（前 見本05 B｜段の行 R8｜塊 LB2）",
                         "組み立ての描画（sample06/assemble/render/R8A・LB2A）と同じ測りの鎖で測った。「合」は測れる規則を通るかだけで、美術の良し悪しの判定ではない")

    def sm(r, k):
        return r["summary"].get(k, "—")

    def g2(r):
        g = r["rules"]["G2"]["gates"]
        return "78 %.2f・130 %.2f・131 %.2f・132 %.2f・72 %.2f" % (g["78"]["claws"], g["130"]["claws"], g["131"]["claws"], g["132_s12"]["claws"], g["72_s12_p95"]["claws"])

    def s11(r):
        t = r["rules"]["S11"]["targets"]
        must = [k for k, v in t.items() if v["kind"] == "must"]
        ok = [k for k in must if v_ok(t[k])]
        bad = [k for k in must if not v_ok(t[k])]
        return "must %d/%d　否：%s" % (len(ok), len(must), "・".join(bad) if bad else "なし")

    def v_ok(v):
        return bool(v.get("pass"))

    def t5(r):
        return "原画視点 %s（全視点 %s）" % (r["rules"]["T5"]["painting_body_blobs_excluding_boat_edges"], r["rules"]["T5"]["all_views_total"])

    def t6(r):
        return "切り出しの白・水色 %.2f" % r["rules"]["T6"]["painting_crop_pale_share"]

    def c3(r):
        c = r["rules"]["C3"]
        v = c["painting_visible_frac_p10_p50_min"]["S04"]
        return "IoU p10 %.3f・原画視点で見える割合 p10 %.2f・最小 %.2f" % (c["iou_painting_p10_p50_min_sample02"][0], v[0], v[2])

    def kb(r):
        k = r["rules"]["K-boat"]
        return "船の画素 %.2f 倍" % k["ratio"]

    st = ck["g1_stretch"]
    rows = [("G1 投影なし・伸びなし", lambda r, n: "%s（伸びの三角形 %d、海の上 %d）" % (sm(r, "G1"), st[n]["bad_tri"], st[n]["above_sea_y_gt_0"])),
            ("G2 原画視点の関門（px）", lambda r, n: "%s　%s" % (sm(r, "G2"), g2(r))),
            ("S4 背は一つの山", lambda r, n: sm(r, "S4")), ("S8 出っ張りなし", lambda r, n: sm(r, "S8")),
            ("S9 左の白は低い・④ は wave4", lambda r, n: sm(r, "S9")), ("S10 峰に沿う長さ", lambda r, n: sm(r, "S10")),
            ("S11 三つの層（目標は既定）", lambda r, n: "%s　%s" % (sm(r, "S11"), s11(r))),
            ("T5 本体の白い粒", lambda r, n: "%s　%s" % (sm(r, "T5"), t5(r))), ("T6 内の縁に白なし", lambda r, n: "%s　%s" % (sm(r, "T6"), t6(r))),
            ("C2・C3 爪", lambda r, n: "%s・%s　%s" % (sm(r, "C2"), sm(r, "C3"), c3(r))),
            ("K-top いちばん高い峰", lambda r, n: sm(r, "K-top")), ("K-boat 船（記録）", lambda r, n: "%s　%s" % (sm(r, "K-boat"), kb(r)))]
    xs = [14, 330, 860, 1390]
    y = 112
    for x, t in zip(xs, ("規則", "前：見本05 B（B10）", "段の行（R8）", "塊（LB2）")):
        d.text((x, y), t, font=font(19, True), fill=(0, 0, 0))
    y += 34
    for lab, fn in rows:
        d.line((10, y - 6, 1910, y - 6), fill=(220, 220, 220))
        d.text((xs[0], y), lab, font=font(16, True), fill=(0, 0, 0))
        for x, (r, n) in zip(xs[1:], ((rb, "B10"), (rr, "R8"), (rl, "LB2"))):
            try:
                s = fn(r, n)
            except Exception as e:  # noqa: BLE001
                s = "—（%s）" % type(e).__name__
            s = s.replace("pass", "合").replace("fail", "否")
            col = (190, 20, 20) if "否" in s.split("　")[0] else (20, 20, 20)
            # 長い文は 2 行に折る
            lines = [s[i:i + 34] for i in range(0, len(s), 34)][:3]
            for j, ln in enumerate(lines):
                d.text((x, y + j * 20), ln, font=font(15), fill=col)
        y += 66
    D.finish(img, d, "asm6_7_rules.png", FOOT_RULES)

    # S11 の目標の表
    img, d = D.new_sheet("美術の見本06：三つの層の目標（S11、targets.json。値は進行役の既定で利用者の言葉ではない）",
                         "前 見本05 B｜段の行 R8｜塊 LB2。層の印はそれぞれの作りの決め方なので、L6（印を使う目標）は作りの間で決め方が違う")
    tb, tr, tl = (x["rules"]["S11"]["targets"] for x in (rb, rr, rl))
    xs = [14, 360, 760, 1060, 1360, 1660]
    y = 112
    for x, t in zip(xs, ("目標", "基準", "B10", "R8", "LB2", "種類")):
        d.text((x, y), t, font=font(18, True), fill=(0, 0, 0))
    y += 30
    for k in tr:
        pf = tr[k]["pass_if"]
        crit = "%s %s" % (pf.get("op"), pf.get("value"))
        d.text((xs[0], y), k, font=font(15, True), fill=(0, 0, 0))
        d.text((xs[1], y), crit[:34], font=font(14), fill=(40, 40, 40))
        for x, T_ in zip(xs[2:5], (tb, tr, tl)):
            e = T_.get(k, {})
            v = e.get("value")
            s = json.dumps(v, ensure_ascii=False)[:26] if not isinstance(v, (int, float)) else ("%.3f" % v if isinstance(v, float) else str(v))
            ok = e.get("pass")
            d.text((x, y), ("合 " if ok else "否 ") + s, font=font(14), fill=(20, 20, 20) if ok else (190, 20, 20))
        d.text((xs[5], y), tr[k]["kind"], font=font(14), fill=(40, 40, 40))
        y += 24
        if y > 1040:
            break
    D.finish(img, d, "asm6_7b_s11_targets.png", FOOT_RULES)


def sheet8():
    """組み立てで見つけた点：LB2 の隠れた爪 claw074 と、船の倍率。"""
    img, d = D.new_sheet("美術の見本06 の組み立て：塊（LB2）で原画視点に隠れた爪 claw074 を相似で手前へ（2 倍の拡大、爪あり）",
                         "左から：前 見本05 B｜塊の作りの LB2（爪が ③ の塊の面の奥で見えない）｜組み立ての LB2（claw074 を原画のカメラを中心に 0.977 倍、1.04 m 手前へ。原画視点の爪の形は同じ）")
    box = (300, 540, 500, 680)
    srcs = [("前 見本05 B", RB10), ("塊の作り LB2", P + "/sample06/lobes/assemble2/render/LB2"), ("組み立て LB2", PA + "/render/LB2A")]
    for k, (nm, rd) in enumerate(srcs):
        im = load(rd + "/views/painting_t120_claws.png").crop(box)
        im = im.resize((im.width * 3, im.height * 3), Image.LANCZOS)
        x = 20 + k * 630
        img.paste(im, (x, 110))
        tag(d, x + 8, 116, nm, 19)
    d.text((14, 560), "段の行（R8）の claw057（原画視点で見える割合 0.61、B10 は 0.91）は ② の段の白の後ろに一部が隠れる。手前へ出すと根元が面から 0.76 m 浮くので動かしていない。",
           font=font(18), fill=(40, 40, 40))
    box2 = (580, 360, 760, 480)
    srcs2 = [("前 見本05 B", RB10), ("段の行 R8", PA + "/render/R8A")]
    for k, (nm, rd) in enumerate(srcs2):
        im = load(rd + "/views/painting_t120_claws.png").crop(box2)
        im = im.resize((im.width * 3, im.height * 3), Image.LANCZOS)
        x = 20 + k * 600
        img.paste(im, (x, 600))
        tag(d, x + 8, 606, nm, 19)
    D.finish(img, d, "asm6_8_claw_fix.png", FOOT)


def main():
    os.makedirs(D.OUT, exist_ok=True)
    only = sys.argv[1] if len(sys.argv) > 1 else "all"
    for k, f in (("1", sheet1), ("2", sheet2), ("3", sheet3), ("4", sheet4), ("5", sheet5), ("6", sheet6), ("7", sheet7), ("8", sheet8)):
        if only in ("all", k):
            f()
    json.dump({"outputs": {os.path.basename(p): D.sha(p) if hasattr(D, "sha") else None for p in D.OUTS}, "inputs": sorted(D.USED)},
              open(D.OUT + "/sheets_manifest_%s.json" % only, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
