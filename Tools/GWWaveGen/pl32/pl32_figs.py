# -*- coding: utf-8 -*-
"""仕上げ32 の図（1920×1080）。原画はリポジトリの Docs/References/Met_JP1847_DP130155.jpg（Met の公開画像）の切り抜きで、
爪形分析の画像・参照の彫刻の写真・参照モデルは使わない。Unity の図は PL32Render の PC オフスクリーン描画（HMD ではない）。

  fig_pl32_bregion.png        b区域の爪（Q16・Q21）：原画｜設計32 の一覧（15 本）｜仕上げ32 の一覧（77 本）と、Unity 原画視点 t* の前｜後｜後の爪なし
  fig_pl32_list_rows.png      列ごとの一覧の重ね（上側・途中・船側・b区域）：設計32（青の細線）と仕上げ32（赤の領域・黒の中心線）
  fig_pl32_list_named.png     名指しの爪（C066・C109・C112・C113・C002＋C174・C042・C017・C014）と代表の爪の前後
  fig_pl32_reps_tstar.png     代表10形と船側中央の爪 C095：原画の切り抜き（一覧の領域）と Unity 原画視点 t* の後の切り抜き、爪ごとの数
  fig_pl32_print_layers.png   摺りの工程の版で見た爪（紙の地・水色の版・墨版の線と藍の版・空）と IoU の真値（D25 を決め直した定義）
  fig_pl32_growth.png         爪の伸び始めと根元の白（136）：前（設計33 の爪・仕上げ31 の T_white）と後
使い方：py -3.10 -B Tools/GWWaveGen/pl32/pl32_figs.py --out Docs/Evidence/Polish/32
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl30")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds32")
from pl30_sheets import font, label, head, fit  # noqa: E402

B = REPO + "/Unity/Build/Polish/32"
PAINT = REPO + "/Docs/References/Met_JP1847_DP130155.jpg"
INV32 = REPO + "/Unity/Build/Design/32/list+ids/ds32_claw_inventory.json"
INVP = B + "/list/ds32_claw_inventory.json"
A_DISP, X_OFF = 0.416345, 156.66153
REPS = ["C028", "C015", "C044", "C006", "C011", "C075", "C064", "C106", "C111", "C092"]
REPL = {k: "R%d" % (i + 1) for i, k in enumerate(REPS)}


def r2d(q):
    q = np.asarray(q, np.float64)
    return np.stack([A_DISP * (q[..., 0] + 0.5) - 0.5 + X_OFF, A_DISP * (q[..., 1] + 0.5) - 0.5], -1)


def paint_disp():
    P = cv2.imread(PAINT)
    M = np.float32([[A_DISP, 0, 0.5 * A_DISP - 0.5 + X_OFF], [0, A_DISP, 0.5 * A_DISP - 0.5]])
    return cv2.warpAffine(P, M, (1920, 1080), flags=cv2.INTER_AREA, borderValue=(200, 200, 200))


def pil(bgr):
    return Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))


def load_inv(p):
    return {c["id"]: c for c in json.load(open(p, encoding="utf-8"))["claws"]}


def overlay_disp(img, claws, box, col, thick=1, cl=True, scale=1.0, ids=None):
    x0, y0 = box[0], box[1]
    out = img
    for c in claws.values():
        if c["zone"] != "main" or (ids is not None and c["id"] not in ids):
            continue
        Q = np.round((r2d(np.asarray(c["region_polygon_ref"])) - [x0, y0]) * scale).astype(np.int32)
        cv2.polylines(out, [Q], True, col, thick, cv2.LINE_AA)
        if cl:
            C = np.round((r2d(np.asarray(c["centerline_ref"])) - [x0, y0]) * scale).astype(np.int32)
            cv2.polylines(out, [C], False, (20, 20, 20), 1, cv2.LINE_AA)
            cv2.circle(out, tuple(int(v) for v in C[0]), max(2, int(2 * scale)), (20, 20, 20), -1)
    return out


def fig_bregion(out):
    D = paint_disp()
    old, new = load_inv(INV32), load_inv(INVP)
    box = (160, 380, 800, 620)
    sc = 2.0
    crop = lambda im: cv2.resize(im[box[1]:box[3], box[0]:box[2]], None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC)  # noqa: E731
    p0 = crop(D)
    p1 = overlay_disp(crop(D), {k: v for k, v in old.items() if v.get("b_region_q16")}, box, (255, 120, 0), 2, True, sc)
    p2 = overlay_disp(crop(D), {k: v for k, v in new.items() if v.get("b_region_q16")}, box, (0, 0, 255), 2, True, sc)
    rb = cv2.imread(B + "/r_before/views/painting_t120_asis.png"); ra = cv2.imread(B + "/r_after/views/painting_t120_asis.png")
    rf = cv2.imread(B + "/r_after/views/painting_t120_clawfree.png")
    tiles = [(p0, "原画（DP130155）"), (p1, "設計32 の一覧の b区域の爪 %d 本" % sum(1 for v in old.values() if v.get("b_region_q16"))),
             (p2, "仕上げ32 の一覧の b区域の爪 %d 本" % sum(1 for v in new.values() if v.get("b_region_q16"))),
             (crop(rb), "前：Unity 原画視点 t*（仕上げ31）"), (crop(ra), "後：Unity 原画視点 t*（仕上げ32）"), (crop(rf), "後の爪なし（主役波の材質だけ）")]
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ32｜b区域の爪（［利用者の言葉］Q16・Q21：b区域の浪尖の爪が原画視点で房として読めない）",
         "上：原画の b区域（表示の x 160〜800・y 380〜620 を 2 倍）に一覧の領域（青・赤）と中心線（黒）。下：同じ所の Unity の原画視点 t*（作品のまま：爪・飛沫・線あり）。")
    tw, th = 632, 237
    for k, (a, t) in enumerate(tiles):
        x, y = 4 + (k % 3) * (tw + 4), 70 + (k // 3) * (th + 40)
        im.paste(fit(pil(a), (tw, th)), (x, y))
        label(d, x + 4, y + 4, t, 15)
    f = font(16)
    txt = ["b区域の爪は、設計32 では利用者の 100 本のうち b区域にあった 14 本（と上側の C172）からだけ作っていた。仕上げ32 で、美術優先29 の骨格化（白の骨格 → ストローク → 端点）を b区域の帯に当てて",
           "候補 88 を取り出し、進行役の目視の 1 回の判定（除く 11・先だけ採る 3）と自動の重複の検査（14）で 63 本を加えた（C176〜C238）。領域は墨版の線で区切った測地の競り合い（記録 第3節）。",
           "前の b区域の爪 15 本のうち 8 本は、段階9 の面に結び付けたままで今の面の裏にあり見えなかった。後は、白い背に爪の線（縁の線つきの白い帯）が房の帯として並ぶ",
           "（b区域の帯の中の、白い地の上の暗い線の成分：前 20・後 91・原画 176）。原画の水色の房の雲と藍の窓（主役波の材質と形、仕上げ28・29）は変えていない。"]
    y = 70 + 2 * (th + 40) + 6
    for ln in txt:
        d.text((14, y), ln, fill=(40, 48, 64), font=f); y += 26
    p = os.path.join(out, "fig_pl32_bregion.png"); im.save(p); return p


def fig_rows(out):
    P = cv2.imread(PAINT)
    old, new = load_inv(INV32), load_inv(INVP)
    rows = [("上側", "上側"), ("途中", "途中"), ("船側", "船側"), ("b区域", "b区域")]
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ32｜列ごとの一覧の重ね（原画 DP130155 の画素）：設計32（青の細線）と仕上げ32（赤の領域・黒の中心線と根元）",
         "仕上げ32 の領域は墨版の線（藍）と空で区切った測地の競り合いで、爪どうしは画素を分け合わない（重なりの組 40 → 0、他の爪の領域の中の根元 15 → 0）。")
    tw, th = 954, 500
    for k, (rn, lab) in enumerate(rows):
        ids = [c["id"] for c in new.values() if c["zone"] == "main" and (c["row"] == rn)]
        pts = np.concatenate([np.asarray(new[i]["region_polygon_ref"]) for i in ids], 0)
        x0, y0 = np.floor(pts.min(0)).astype(int) - 20
        x1, y1 = np.ceil(pts.max(0)).astype(int) + 20
        x0, y0 = max(0, x0), max(0, y0)
        C = P[y0:y1, x0:x1].copy()
        s = min(tw / float(C.shape[1]), th / float(C.shape[0]))
        Cs = cv2.resize(C, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        for cid in ids:
            o = old.get(cid)
            if o and o["zone"] == "main":
                cv2.polylines(Cs, [np.round((np.asarray(o["region_polygon_ref"]) - [x0, y0]) * s).astype(np.int32)], True, (255, 120, 0), 1, cv2.LINE_AA)
        for cid in ids:
            c = new[cid]
            cv2.polylines(Cs, [np.round((np.asarray(c["region_polygon_ref"]) - [x0, y0]) * s).astype(np.int32)], True, (0, 0, 230), 1, cv2.LINE_AA)
            Q = np.round((np.asarray(c["centerline_ref"]) - [x0, y0]) * s).astype(np.int32)
            cv2.polylines(Cs, [Q], False, (0, 0, 0), 1, cv2.LINE_AA)
            cv2.circle(Cs, tuple(int(v) for v in Q[0]), 2, (0, 0, 0), -1)
        x, y = 4 + (k % 2) * (tw + 4), 70 + (k // 2) * (th + 4)
        im.paste(fit(pil(Cs), (tw, th)), (x, y))
        label(d, x + 4, y + 4, "%s　%d 本（設計32 %d 本）" % (lab, len(ids), sum(1 for c in old.values() if c["zone"] == "main" and c["row"] == rn)), 15)
    p = os.path.join(out, "fig_pl32_list_rows.png"); im.save(p); return p


def claw_cell(P, old, new, cid, cw=200, extra=None):
    c = new.get(cid) or old.get(cid)
    pts = [np.asarray(c["centerline_ref"])]
    if cid in old:
        pts.append(np.asarray(old[cid]["centerline_ref"]))
    if extra:
        pts += [np.asarray(new[e]["centerline_ref"]) for e in extra if e in new] + [np.asarray(old[e]["centerline_ref"]) for e in extra if e in old]
    allp = np.concatenate(pts, 0)
    cx, cy = (allp.min(0) + allp.max(0)) / 2
    x0, y0 = int(cx - cw / 2), int(cy - cw / 2)
    crop = P[max(0, y0):y0 + cw, max(0, x0):x0 + cw].copy()
    if crop.shape[0] < cw or crop.shape[1] < cw:
        crop = cv2.copyMakeBorder(crop, 0, cw - crop.shape[0], 0, cw - crop.shape[1], cv2.BORDER_CONSTANT, value=(128, 128, 128))
    sc = 300.0 / cw
    big = cv2.resize(crop, (300, 300), interpolation=cv2.INTER_CUBIC)
    T = lambda q: np.round((np.asarray(q, float) - [x0, y0]) * sc).astype(np.int32)  # noqa: E731
    for k in [cid] + list(extra or []):
        if k in old and old[k]["zone"] == "main":
            cv2.polylines(big, [T(old[k]["region_polygon_ref"])], True, (255, 140, 0), 1, cv2.LINE_AA)
            cv2.polylines(big, [T(old[k]["centerline_ref"])], False, (255, 80, 0), 2, cv2.LINE_AA)
            cv2.circle(big, tuple(T(old[k]["root_ref"])), 5, (255, 80, 0), 2)
        if k in new:
            cv2.polylines(big, [T(new[k]["region_polygon_ref"])], True, (0, 0, 255), 2, cv2.LINE_AA)
            cv2.polylines(big, [T(new[k]["centerline_ref"])], False, (0, 170, 0), 2, cv2.LINE_AA)
            cv2.circle(big, tuple(T(new[k]["root_ref"])), 4, (0, 0, 0), -1)
    return big


def fig_named(out):
    P = cv2.imread(PAINT)
    old, new = load_inv(INV32), load_inv(INVP)
    chk = json.load(open(B + "/list/pl32_claw_list_checks.json", encoding="utf-8"))
    cells = [("C066", None, "C066 115→111 px（設計32 の根元のまま）"), ("C109", None, "C109 名指しの起点の直しのまま"),
             ("C112", None, "C112 消した（墨の巻いた線の先の白の塊、9 px）"), ("C113", None, "C113 51.6 px（二本の線の間の指の全部）"),
             ("C002", ["C174"], "C002＋C174 を統合（一本の垂れる指）"), ("C042", None, "C042 上側の口の規則を当てない"),
             ("C017", None, "C017 上側の口の規則：根元を指の首へ"), ("C014", None, "C014 上側の口の規則：下の指だけ"),
             ("C028", None, "C028（R1）口の規則と真ん中の中心線"), ("C092", None, "C092（R10）真ん中の中心線"),
             ("C075", None, "C075（R6）"), ("C106", None, "C106（R8）")]
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ32｜名指しの爪と代表の爪の前後（原画 DP130155 の 1:1.5）：橙＝設計32 の領域・中心線・根元、赤＝仕上げ32 の領域、緑＝仕上げ32 の中心線、黒点＝根元",
         "根元の先で指が続く疑い（設計32 の検査）は、仕上げ32 の一覧で %d 本（多くは体の中の線に当たる誤検出。記録 第3節）。" % len(chk["continues_past_root"]))
    for k, (cid, ex, t) in enumerate(cells):
        x, y = 4 + (k % 6) * 318, 70 + (k // 6) * 350
        im.paste(pil(claw_cell(P, old, new, cid, 200, ex)), (x + 9, y + 30))
        f = font(13)
        d.text((x + 9, y + 6), t, fill=(30, 30, 30), font=f)
    p = os.path.join(out, "fig_pl32_list_named.png"); im.save(p); return p


def fig_reps(out):
    D = paint_disp()
    ra = cv2.imread(B + "/r_after/views/painting_t120_asis.png")
    rb = cv2.imread(B + "/r_before/views/painting_t120_asis.png")
    new = load_inv(INVP)
    m = json.load(open(B + "/measure/pl32_measure_claws.json", encoding="utf-8"))
    ids = REPS + ["C095"]
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ32｜代表10形（R1〜R10）と船側中央の爪 C095：原画｜前（仕上げ31）｜後（仕上げ32）の原画視点 t*（赤＝仕上げ32 の一覧の領域）",
         "数は後の爪の帯の投影（主役波の面の隠れを数えない）：輪郭＝影の外周と一覧の領域の外周の左右の対称 Hausdorff（≤4 px）、幅＝影の幅／領域の幅、先端の向きの差。記録 第5節。")
    cw = 60
    for k, cid in enumerate(ids):
        c = new[cid]
        q = r2d(np.asarray(c["centerline_ref"]))
        cx, cy = (q.min(0) + q.max(0)) / 2
        x0, y0 = int(cx - cw / 2), int(cy - cw / 2)
        sc = 2.6
        tiles = []
        for src in (D, rb, ra):
            C = src[max(0, y0):y0 + cw, max(0, x0):x0 + cw].copy()
            C = cv2.resize(C, None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC)
            Q = np.round((r2d(np.asarray(c["region_polygon_ref"])) - [x0, y0]) * sc).astype(np.int32)
            cv2.polylines(C, [Q], True, (0, 0, 230), 1, cv2.LINE_AA)
            tiles.append(C)
        cell = np.concatenate(tiles, 1)
        col, row = k % 3, k // 3
        x, y = 4 + col * 638, 66 + row * 252
        im.paste(fit(pil(cell), (630, 156)), (x, y + 22))
        v = m["after"]["per_claw"][cid]; vb = m["before"]["per_claw"][cid]
        t = "%s %s｜輪郭 左 %s・右 %s px（前 %s・%s）｜幅 %.2f（前 %.2f）｜先端の向きの差 %+.1f°（前 %+.1f°）" % (
            REPL.get(cid, "船側中央"), cid, v["outline_left_px"], v["outline_right_px"], vb["outline_left_px"], vb["outline_right_px"],
            v["width_ratio"], vb["width_ratio"], v["tip_dir_diff_deg"], vb["tip_dir_diff_deg"])
        d.text((x + 2, y + 2), t, fill=(30, 30, 30), font=font(12))
    p = os.path.join(out, "fig_pl32_reps_tstar.png"); im.save(p); return p


def fig_print_layers(out):
    import ds32_claw_list as L32
    L32.P["crop"] = [0, 0, 2700, 1560]
    paint = L32.Paint()
    truth = np.load(B + "/list/_truth.npy")
    idimg = np.load(B + "/list/_idimg.npy")
    cols = {"paper": (247, 242, 228), "pale": (196, 214, 205), "dark": (110, 60, 30), "sky": (170, 200, 230)}
    L = np.zeros(paint.cls.shape + (3,), np.uint8)
    L[paint.white] = cols["paper"]; L[paint.pale] = cols["pale"]; L[paint.dark] = cols["dark"]; L[paint.sky] = cols["sky"]
    boxes = [((1500, 300, 1900, 600), "上側の爪"), ((600, 1050, 1000, 1350), "b区域の爪")]
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ32｜摺りの工程の版で見た爪（［利用者の言葉］Q8：摺りの工程から爪の基礎色と領域を決める）",
         "左：原画（DP130155）。中：画素の版の読み（紙の地＝摺らない白、水色の版、墨版の線と藍の版、空の版）。右：IoU の真値（D25 を決め直した定義、緑）と一覧の爪の和（赤の輪郭）。")
    for r, ((x0, y0, x1, y1), name) in enumerate(boxes):
        a = cv2.cvtColor(paint.rgb[y0:y1, x0:x1], cv2.COLOR_RGB2BGR) if hasattr(paint, "rgb") else None
        b = cv2.cvtColor(L[y0:y1, x0:x1], cv2.COLOR_RGB2BGR)
        c = a.copy()
        tm = truth[y0:y1, x0:x1]
        c[tm] = (0.5 * c[tm] + 0.5 * np.array([60, 200, 60])).astype(np.uint8)
        idm = (idimg[y0:y1, x0:x1] > 0).astype(np.uint8)
        cs, _ = cv2.findContours(idm, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(c, cs, -1, (0, 0, 230), 1)
        for k, (t, nm) in enumerate(((a, "原画"), (b, "版の読み"), (c, "真値と一覧"))):
            x, y = 4 + k * 638, 70 + r * 470
            im.paste(fit(pil(t), (630, 440)), (x, y + 24))
            label(d, x + 4, y + 26, "%s｜%s" % (name, nm), 14)
    # 凡例
    lx, ly = 14, 1022
    for k, (nm, cc) in enumerate((("紙の地（摺らない白）", cols["paper"]), ("水色の版", cols["pale"]), ("墨版の線・藍の版（藍濃・藍中・混）", cols["dark"]), ("空（灰・桃の版）", cols["sky"]))):
        d.rectangle([lx, ly, lx + 24, ly + 18], fill=cc, outline=(60, 60, 60))
        d.text((lx + 30, ly), nm, fill=(30, 30, 30), font=font(15))
        lx += 360
    p = os.path.join(out, "fig_pl32_print_layers.png"); im.save(p); return p


def fig_growth(out):
    wb = json.load(open(REPO + "/Unity/Build/Polish/31/white/pl31_white_numpy.json", encoding="utf-8"))
    wa = json.load(open(B + "/white/pl32_white_numpy.json", encoding="utf-8"))
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ32｜爪の伸び始めと根元の白（136）と、白の順（135）",
         "前＝仕上げ31（設計33 の爪を古い白の順で伸ばし、根元を先に白くする誘導 pl31_white_claw_pin）。後＝仕上げ32（爪は根元の 4 つの角がそろって白くなってから伸びる。誘導は外した）。")
    # 左：135 の 10 区間の時刻（PIL で描く）
    X0, Y0, Wp, Hp = 90, 110, 820, 520
    d.rectangle([X0, Y0, X0 + Wp, Y0 + Hp], outline=(80, 80, 80), fill=(250, 250, 250))
    tmin, tmax = 7.5, 10.5
    fmin, fmax = 1.0, 2.5
    for tv in np.arange(8.0, 10.51, 0.5):
        yy = Y0 + Hp - (tv - tmin) / (tmax - tmin) * Hp
        d.line([X0, yy, X0 + Wp, yy], fill=(225, 225, 225))
        d.text((X0 - 60, yy - 9), "%.1f s" % tv, fill=(60, 60, 60), font=font(14))
    for fv in np.arange(1.0, 2.51, 0.25):
        xx = X0 + (fv - fmin) / (fmax - fmin) * Wp
        d.text((xx - 14, Y0 + Hp + 6), "%.2f" % fv, fill=(60, 60, 60), font=font(14))
    d.text((X0 + 200, Y0 + Hp + 30), "流れの座標 F（頂 1 → 唇の先 2 → 下面）の 10 区間の中央", fill=(40, 40, 40), font=font(15))
    d.text((X0, Y0 - 30), "135：前の白が白くなる時刻の中央値（区間ごと）", fill=(20, 20, 20), font=font(18, True))
    for k, (dd, nm, colr) in enumerate(((wb, "前（仕上げ31）", (230, 120, 20)), (wa, "後（仕上げ32）", (30, 90, 200)))):
        fr = dd["b135"]["front"]
        pts = [(X0 + (f_ - fmin) / (fmax - fmin) * Wp, Y0 + Hp - (t_ - tmin) / (tmax - tmin) * Hp) for f_, t_ in zip(fr["bins_key_median"], fr["bins_t_median"])]
        d.line(pts, fill=colr, width=3)
        for q in pts:
            d.ellipse([q[0] - 5, q[1] - 5, q[0] + 5, q[1] + 5], fill=colr)
        d.text((X0 + 20, Y0 + 14 + 26 * k), "%s：順位相関 %.2f" % (nm, fr["spearman_bins"]), fill=colr, font=font(16, True))
    # 右：136 の棒
    X1 = 1040
    d.rectangle([X1, Y0, X1 + Wp, Y0 + Hp], outline=(80, 80, 80), fill=(250, 250, 250))
    d.text((X1, Y0 - 30), "136：根元が白くなる前に伸び始める爪（本）", fill=(20, 20, 20), font=font(18, True))
    wn = json.load(open(B + "/white_nopin/pl31_white_numpy.json", encoding="utf-8"))   # 設計33 の爪 × 誘導を外した白の順（pl31_white.py --claw-pin 0）
    cb = wn["claws_136"]["after"]; ca = wa["claws_136"]["after"]; c31 = wb["claws_136"]["after"]
    bars = [("設計33 の爪・仕上げ31 の T_white（誘導あり）", c31["violations"], (230, 120, 20)),
            ("設計33 の爪・誘導を外した白の順", cb["violations"], (200, 160, 60)),
            ("仕上げ32 の爪・誘導を外した白の順", ca["violations"], (30, 90, 200))]
    vmax = max(max(v for _, v, _ in bars), 1)
    for k, (nm, v, colr) in enumerate(bars):
        bx = X1 + 60 + k * 250
        hh = v / vmax * (Hp - 80)
        d.rectangle([bx, Y0 + Hp - hh, bx + 150, Y0 + Hp], fill=colr)
        d.text((bx + 50, Y0 + Hp - hh - 26), "%d" % v, fill=(20, 20, 20), font=font(18, True))
        for j, ln in enumerate([nm[i:i + 13] for i in range(0, len(nm), 13)]):
            d.text((bx - 10, Y0 + Hp + 6 + 20 * j), ln, fill=(40, 40, 40), font=font(14))
    f = font(16)
    txt = ["※ 前の 136 は仕上げ31 の記録の値（根元を先に白くする誘導の後で 0 本）。誘導を外した白の順のまま設計33 の爪を伸ばすと、%d 本・最大 %.2f s 遅れる（white_nopin の claws_136）。" % (
               json.load(open(B + "/white_nopin/pl31_white_numpy.json", encoding="utf-8"))["claws_136"]["after"]["violations"],
               json.load(open(B + "/white_nopin/pl31_white_numpy.json", encoding="utf-8"))["claws_136"]["after"]["lag_max_s"]),
           "後：爪の誕生 τ_b を根元の格子の 2×2 の T_white の最大（名前の付いた決まり pl32_birth_all_corners）にしたので、根元の白より先に伸びる爪は 0 本（最大 %+.3f s）。" % ca["lag_max_s"],
           "135（頂から唇の先・下面へ）は、爪の根元の誘導を外して 0.93 → %.2f（背は %.2f）。102（1 コマの白の増分）は %.2f%%（表面）・%.2f%%（世界）で 2%% 以下。" % (
               wa["b135"]["front"]["spearman_bins"], wa["b135"]["back"]["spearman_bins"], 100 * wa["b102_after"]["surface_fraction_max_increment"], 100 * wa["b102_after"]["world_fraction_max_increment"]),
           "飛沫の放出点の誘導 pl32_white_spray_pin：仕上げ31 の飛沫の放出点の頂点のうち %d を、最も早い粒の放出の半コマ前まで早めた（最大 %.2f s）。放出の時に白い放出点 2,495／2,495。" % (
               wa["pl32_white_spray_pin"]["vertices_moved"], wa["pl32_white_spray_pin"]["tau_advance_max_s"])]
    y = 760
    for ln in txt:
        d.text((14, y), ln, fill=(40, 48, 64), font=f); y += 30
    p = os.path.join(out, "fig_pl32_growth.png"); im.save(p); return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=REPO + "/Docs/Evidence/Polish/32")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for f in (fig_bregion, fig_rows, fig_named, fig_reps, fig_print_layers, fig_growth):
        p = f(a.out)
        print(p, os.path.getsize(p))


if __name__ == "__main__":
    main()
