# -*- coding: utf-8 -*-
"""美術の見本03 の渡す準備：証拠の図（どれも 1920×1080、日本語の見出し）と metrics.json・run.json・rules_check.json を
Docs/Evidence/ArtSample03/ へ書く。描画は修正の回 1 の Unity の出力（Build/Polish/sample03/fix01/render、Git 対象外）を並べるだけで、
描き直さない。彫刻の写真・写真から作った画像・利用者のマスクは使わない（入れない）。
  as03_1a_crest_orbit.png・1b  波頭の回り台 8 方位（列：見本02・V1・V2・V3）
  as03_2a_painting_view.png・2b 原画視点：原画｜見本02｜V1｜V3 と、波頭と唇の拡大
  as03_3a_views.png・3b        座席・座席から波・後ろ 65°／左の側面・右の側面・真上（行：V1・V2・V3）
  as03_4_face_closeup.png      彫りの面の近く（稜と溝の淡い青）：V1・V2
  as03_5a_turntable.png・5b    回り台 12 方位（行：見本02・V1・V2・V3）
  as03_6_rules.png             測る規則のまとめ
使い方：py -3.10 -B Tools/GWWaveGen/as03/as03_deliver.py
"""
import datetime
import hashlib
import json
import os
import platform
import shutil

import numpy
import PIL
from PIL import Image, ImageDraw, ImageFont

REPO = "G:/Unity/GreatWave_2026_Fresh"
S3 = REPO + "/Unity/Build/Polish/sample03"
R = S3 + "/fix01/render"
S02V = REPO + "/Unity/Build/Polish/sample02/fix01/assemble/render/AS02C_A"
S02C = S3 + "/study/render/S3_AS02C_crest2"
PAINT = REPO + "/Docs/References/Met_JP1847_DP130155.jpg"
OUT = REPO + "/Docs/Evidence/ArtSample03"
W, H = 1920, 1080
FOOT = "Unity 6000.4.3f1 の PC オフスクリーン描画（HMD 実機ではない）。t* = 12 s の静止、飛沫なし。美術が届いたかは利用者が決める（Q29・Q30）。"
VJ = {"S02": "見本02（前）", "V1": "V1 冠を開く・艶と陰", "V2": "V2 冠を開く・平らな色", "V3": "V3 冠を収める・艶と陰"}
VIEWJ = {"painting": "原画視点", "seat": "座席（VR の視点）", "seat_toward_wave": "座席から波の方向", "side_left": "左の側面",
         "side_right": "右の側面", "back65": "後ろ 65°", "top": "真上"}
AZJ = {0: "0°（原画の側）", 45: "45°（正面）", 90: "90°", 135: "135°（右の側面）", 180: "180°", 225: "225°（背）", 270: "270°",
       315: "315°（左の側面）"}


def font(sz, bold=False):
    for p in ("C:/Windows/Fonts/BIZ-UDGothic%s.ttc" % ("B" if bold else "R"), "C:/Windows/Fonts/msgothic.ttc"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fit(im, w, h, bg=(255, 255, 255), upscale=True):
    im = im.convert("RGB")
    s = min(w / im.width, h / im.height)
    if not upscale:
        s = min(s, 1.0)
    im2 = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    c = Image.new("RGB", (w, h), bg)
    c.paste(im2, ((w - im2.width) // 2, (h - im2.height) // 2))
    return c


USED = {}


def load(p, crop=None):
    USED[p] = None
    im = Image.open(p)
    if crop:
        im = im.crop(crop)
    return im


def grid(title, sub, rows, path, lab_h=26, top=None):
    """rows：行ごとのセルの並び。セル = (path, crop, label)。図は 1920×1080 ちょうど。"""
    top = top or (58 if not sub else 88)
    foot = 30
    nr = len(rows)
    nc = max(len(r) for r in rows)
    cw = W // nc
    ch = (H - top - foot) // nr
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((14, 10), title, font=font(30, True), fill=(10, 10, 10))
    if sub:
        d.text((14, 52), sub, font=font(19), fill=(60, 60, 60))
    fl = font(17)
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            if cell is None:
                continue
            p, crop, lab = cell
            x, y = j * cw, top + i * ch
            d.text((x + 6, y + 3), lab, font=fl, fill=(20, 20, 20))
            if p is None or not os.path.isfile(p):
                d.rectangle((x + 2, y + lab_h, x + cw - 3, y + ch - 3), outline=(180, 180, 180))
                continue
            img.paste(fit(load(p, crop), cw - 4, ch - lab_h - 2), (x + 2, y + lab_h))
    d.text((14, H - 26), FOOT, font=font(17), fill=(70, 70, 70))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    assert img.size == (W, H)
    img.save(path)
    return path


def vpath(v, kind, name):
    if v == "S02":
        return (S02C if kind == "crest" else S02V) + "/%s/%s" % (kind, name)
    return R + "/%s/%s/%s" % (v, kind, name)


def sheet1():
    out = []
    crop = (60, 230, 1860, 1080)
    for tag, azs in (("a", (0, 45, 90, 135)), ("b", (180, 225, 270, 315))):
        rows = []
        for az in azs:
            rows.append([(vpath(v, "crest", "t120_az%03d_claws.png" % az), crop, "%s ／ 方位 %s" % (VJ[v], AZJ[az]))
                         for v in ("S02", "V1", "V2", "V3")])
        out.append(grid("(1) 波頭の近く：波頭の回り台（距離 34 m・仰角 5°）　列：見本02（前）｜V1｜V2｜V3",
                        "中心 (−6.63, 16.5, −3.27) の周りを回す。主役波と冠・爪だけ（周りの海なし）。各図の下 4/5 を切り出し", rows,
                        OUT + "/as03_1%s_crest_orbit.png" % tag))
    return out


def sheet2():
    # 原画の波頭の切り出し（原画の画像の比で。原画は公開の画像）
    pim = Image.open(PAINT)
    pw, ph = pim.size
    pcrop = (int(0.16 * pw), int(0.03 * ph), int(0.64 * pw), int(0.56 * ph))
    ucrop = (0, 40, 1120, 670)
    full = [[(PAINT, None, "原画 DP130155（メトロポリタン美術館の公開の画像）"),
             (vpath("S02", "views", "painting_t120_claws.png"), None, VJ["S02"])],
            [(vpath("V1", "views", "painting_t120_claws.png"), None, VJ["V1"]),
             (vpath("V3", "views", "painting_t120_claws.png"), None, VJ["V3"])]]
    zoom = [[(PAINT, pcrop, "原画：波頭と唇（おおよその切り出し）"),
             (vpath("S02", "views", "painting_t120_claws.png"), ucrop, "見本02（前）：波頭と唇")],
            [(vpath("V1", "views", "painting_t120_claws.png"), ucrop, "V1 冠を外へ開く＋艶と陰：波頭と唇"),
             (vpath("V3", "views", "painting_t120_claws.png"), ucrop, "V3 冠を原画の輪郭に収める＋艶と陰：波頭と唇")]]
    a = grid("(2a) 原画視点（t*）：原画｜見本02（前）｜V1｜V3",
             "V2 は V1 と同じ形で色だけ平ら（(1)・(3)・(5) にある）。面の内と近い海の爪 35 本は見本02 のまま（材質だけ変種と同じ）", full,
             OUT + "/as03_2a_painting_view.png")
    b = grid("(2b) 原画視点の波頭と唇の拡大：原画｜見本02（前）｜V1｜V3",
             "Unity の画は左上 1120×630 を切り出し。原画は同じ所のおおよその切り出し", zoom, OUT + "/as03_2b_painting_crest.png")
    return [a, b]


def sheet3():
    out = []
    for tag, views in (("a", ("seat", "seat_toward_wave", "back65")), ("b", ("side_left", "side_right", "top"))):
        rows = []
        for v in ("V1", "V2", "V3"):
            rows.append([(vpath(v, "views", "%s_t120_claws.png" % vw), None, "%s ／ %s" % (VIEWJ[vw], VJ[v])) for vw in views])
        out.append(grid("(3) 原画視点のほかの視点：" + "・".join(VIEWJ[x] for x in views) + "　（行：V1・V2・V3）", None, rows,
                        OUT + "/as03_3%s_views.png" % tag))
    return out


def sheet4():
    cells = [("views", "painting_t120_claws.png", (560, 260, 1040, 740), "原画視点の唇の下の面（等倍）"),
             ("views", "seat_toward_wave_t120_claws.png", (300, 120, 1020, 840), "座席から波の方向の面"),
             ("crest", "t120_az090_claws.png", (1280, 600, 1760, 1080), "波頭の回り台 90° の唇の下（等倍）"),
             ("views", "seat_toward_wave_t120_claws.png", (640, 360, 880, 600), "座席から波：稜と溝の拡大（2 倍）")]
    rows = []
    for v in ("V1", "V2"):
        rows.append([(vpath(v, k, n), c, "%s ／ %s" % (v, lab)) for k, n, c, lab in cells])
    return [grid("(4) 彫りの面の近く：巻きに沿う藍の稜と、溝の淡い青（行：V1 艶と陰・V2 平らな色）",
                 "溝は面へ内へ彫った本当の凹凸（周期 0.78〜1.09 m、溝の幅は周期の 0.244、深さは周期の 0.12）。白の区域と背には彫らない",
                 rows, OUT + "/as03_4_face_closeup.png")]


def sheet5():
    out = []
    for tag, azs in (("a", range(0, 180, 30)), ("b", range(180, 360, 30))):
        rows = []
        for v in ("S02", "V1", "V2", "V3"):
            rows.append([(vpath(v, "tt", "t120_az%03d_claws.png" % az), None, "%s ／ %d°" % ("見本02" if v == "S02" else v, az)) for az in azs])
        out.append(grid("(5) 回り台（距離 72 m・仰角 16°、爪あり・飛沫なし、周りの海あり）　行：見本02（前）・V1・V2・V3", None, rows,
                        OUT + "/as03_5%s_turntable.png" % tag))
    return out


def sheet6(rc):
    r = rc["rules"]
    byv = rc["summary"]["by_variant"]
    t4 = r["T4"]
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((14, 10), "(6) 測る規則のまとめ（Docs/Evidence/ArtSample03/rules_check.json、修正の回 1 の後）", font=font(30, True), fill=(10, 10, 10))
    f, fb = font(19), font(19, True)
    xs = [14, 300, 380, 460, 540]
    y = 62
    for x, t in zip(xs, ["規則", "V1", "V2", "V3", "中身"]):
        d.text((x, y), t, font=fb, fill=(0, 0, 0))
    y += 28
    d.line((14, y - 3, W - 14, y - 3), fill=(0, 0, 0), width=2)

    def mk(v, k):
        x = byv[v][k]
        if k == "G2" and v in ("V1", "V2"):
            return "記録"
        return "合" if x == "pass" else "不合"

    def g(v):
        gg = r["G2"]["variants"][v]["gates"]
        return "78 %.2f・130 %.2f・131 %.2f・132σ12 %.2f・72σ12 p95 %.2f" % tuple(gg[k]["claws"] for k in ("78", "130", "131", "132_s12", "72_s12_p95"))
    cn = t4["crown_numbers"]
    cv = t4["crown_visibility"]
    dfx = t4["drip_fringe_fix1"]
    lines = [
        ("G1 投影を使わない", "G1", "シェーダー 3 つは B2 が確かめた版のまま（SHA-256 が一致）。原画カメラの行列・テクスチャ・画面の座標で色を決める道なし。材質は値の表だけ替えた"),
        ("G2 原画視点の輪郭", "G2", "4 px 以下。V3（冠を収める）が通る：" + g("V3") + " px。V1・V2 は冠が原画の空へ出るので記録だけ（例 V1 132σ12 %.1f px）" % r["G2"]["variants"]["V1"]["gates"]["132_s12"]["claws"]),
        ("S4 背は一つの山", "S4", "背の頂点は見本02 の AS02C と同じ。冠の手の根元は背に無い（見本02 の合格がそのまま当てはまる）"),
        ("C2 爪の水準（35 本）", "C2", "面の内 25・近い海 10 本は見本02 とバイトまで同じ。不合 %d 本" % r["C2"]["fail"]),
        ("C3 マスクとの重なり", "C3", "原画視点の IoU p10・p50・最小 %s（0.85 以上）。冠の役の 48 本は冠の指の先" % "・".join("%.3f" % x for x in r["C3"]["iou_painting_p10_p50_min"])),
        ("T4 波頭の冠（数）", "T4", "指の先 外へ開く %d・収める %d 本（彫刻から 83〜111）、手 %d・%d（33〜59）、指の長さ p50 %.2f・%.2f m" % (
            cn["OUT"]["checks"]["fingertips_in_S1_range"]["value"], cn["IN"]["checks"]["fingertips_in_S1_range"]["value"],
            cn["OUT"]["checks"]["hands_in_S1_range"]["value"], cn["IN"]["checks"]["hands_in_S1_range"]["value"],
            cn["OUT"]["checks"]["digit_length_p50_in_S1_p25_p75_m"]["value"], cn["IN"]["checks"]["digit_length_p50_in_S1_p25_p75_m"]["value"])),
        ("T4 冠が見える", "T4", "原画視点のほかの 26 視点で枠に占める冠の割合の最小（0.5%% より多い）：V1 %.2f%%・V2 %.2f%%・V3 %.2f%%（どれも右の側面）。修正の前は 0.22・0.21・0.11%%" % (
            100 * cv["V1"]["min"]["frac"], 100 * cv["V2"]["min"]["frac"], 100 * cv["V3"]["min"]["frac"])),
        ("T4 垂れる滴（足した検査）", "T4", "外へ開く %d 本：間隔 %.2f・長さ %.2f・幅 %.2f m、収める %d 本：%.2f・%.2f・%.2f m（彫刻の写真の読み 0.8・0.6〜1.45・0.30〜0.48 m）" % (
            dfx["OUT"]["record"]["drips"], dfx["OUT"]["checks"]["spacing_p50_m"]["value"], dfx["OUT"]["checks"]["length_p50_m"]["value"],
            dfx["OUT"]["checks"]["width_max_p50_m"]["value"], dfx["IN"]["record"]["drips"], dfx["IN"]["checks"]["spacing_p50_m"]["value"],
            dfx["IN"]["checks"]["length_p50_m"]["value"], dfx["IN"]["checks"]["width_max_p50_m"]["value"])),
        ("T1 模様の間隔と伸び", "T1", "線の間隔 ÷ 設計の周期が 0.64〜1.56 の面積 %.1f%%。面の座標の勾配が 1/3〜3 倍の外の三角形 %d（細い三角形を除く）" % (
            100 * r["T1"]["spacing_ratio"]["frac_area_in_0.64_1.56"], r["T1"]["stretch_grad_w"]["tri_outside_1_3_to_3x"])),
    ]
    maxw = W - xs[4] - 20
    for name, key, txt in lines:
        d.text((xs[0], y), name, font=fb, fill=(0, 0, 0))
        for x, v in zip(xs[1:4], ("V1", "V2", "V3")):
            m = mk(v, key)
            d.text((x, y), m, font=fb, fill=(0, 110, 0) if m == "合" else ((90, 90, 90) if m == "記録" else (180, 0, 0)))
        t = txt
        while t:
            n = len(t)
            while n > 1 and d.textlength(t[:n], font=f) > maxw:
                n -= 1
            if n < len(t):
                k = max(t.rfind(ch, 0, n) for ch in "・、。 ）")
                if k > n * 0.6:
                    n = k + 1
            d.text((xs[4], y), t[:n], font=f, fill=(30, 30, 30))
            t = t[n:]
            y += 25
        y += 7
    # 批評の測り（記録）：前 → 後
    y += 6
    d.text((14, y), "記録（判定に使わない）：批評の測りの 修正の前 → 後（V1）", font=fb, fill=(0, 0, 0))
    y += 28
    cm = t4["critic_metrics_before_after_record"]["by_variant"]["V1"]
    rowsj = [("views/painting", "原画視点"), ("crest/045", "波頭 45°"), ("crest/090", "波頭 90°"), ("crest/135", "波頭 135°"),
             ("views/seat", "座席"), ("views/seat_toward_wave", "座席から波")]
    hx = [14, 260, 560, 860, 1160]
    for x, t in zip(hx, ["視点", "見える白のうち冠の割合", "白の明るさの中央値（0〜255）", "指の周りの藍の割合", "白の中の暗い穴"]):
        d.text((x, y), t, font=fb, fill=(0, 0, 0))
    y += 26
    for k, j in rowsj:
        m = cm[k]
        vals = [j, "%.2f → %.2f" % tuple(m["crown_share_of_white"]),
                "%d → %d" % (m["white_lum_p25_p50_p75"][0][1], m["white_lum_p25_p50_p75"][1][1]),
                "%.2f → %.2f" % tuple(m["ring_indigo"]), "%d → %d" % tuple(m["dark_crown_blobs"])]
        for x, t in zip(hx, vals):
            d.text((x, y), t, font=f, fill=(30, 30, 30))
        y += 25
    y += 8
    for t in ("・彫刻の白の中の明るさは 214〜218、指の間に藍が見える割合は 0.55〜0.75（調べ S1）。冠の割合は泡の皮も冠に数えるので高く出る。",
              "・規則の範囲（彫刻の分布の四分位など）は作業の既定で、進行役が変えてよい。進行役とサブエージェントの目の審査は閉じる条件にしない。"):
        d.text((14, y), t, font=f, fill=(60, 60, 60))
        y += 25
    y += 10
    d.text((14, y), "規則は通っても、まだ届いていない所（正直に。詳しくは Docs/Progress/ArtSample_03_ja.md）", font=fb, fill=(150, 0, 0))
    y += 28
    for t in ("・冠は彫刻より低く平らな瘤の層に読める。正面の 0°・45° では指の背の列が縦の縞に見え、所によって瘤がうろこのようにそろう。",
              "・冠の上の鋭いとげは、冠の役の利用者の爪 48 本（鋭い鉤のまま）。C2（鋭い先）と Q29（太く丸い指）が食い違う。B1 の手の根元は面に寝たまま（法線から 70°）。",
              "・座席から見た面は、溝の青を暗くしても等間隔の縞に読める。背は滑らかな白（注ぎ釉の波紋なし）。艶のある波が平らな色の海の上にある。",
              "・V2（平らな色）は冠の白と背のクリーム色の境が見える。V3 は原画の空に出る泡を沈めたので、ほかの視点で V1 より頂が滑らか。",
              "・t* = 12 s の静止だけ（形成の動きは無い）。HMD（PS VR2）と性能は見ていない。"):
        d.text((14, y), t, font=f, fill=(60, 60, 60))
        y += 25
    d.text((14, H - 26), FOOT, font=font(17), fill=(70, 70, 70))
    p = OUT + "/as03_6_rules.png"
    assert img.size == (W, H)
    img.save(p)
    return [p]


def ev23():
    """評価器 23（原画視点の色区の評価、記録）の合格・不合格・記録だけの数。線あり・なし、爪あり・なし"""
    out = {}
    for v in ("V1", "V2", "V3"):
        for m in ("off_line", "off_noline", "off_line_noclaws", "off_noline_noclaws"):
            p = R + "/%s/eval23/%s/metrics.json" % (v, m)
            if not os.path.isfile(p):
                continue
            d = jload(p)
            it = d["items"]
            st = {}
            for x in (it.values() if isinstance(it, dict) else it):
                k = x.get("verdict") or x.get("status") or x.get("result")
                st[k] = st.get(k, 0) + 1
            out["%s/%s" % (v, m)] = {"counts": st, "sha256": sha(p)}
    out["sample02_ja"] = "見本02（AS02C_A）：線あり 合格 2・不合格 7・記録 14、線なし 4・5・14（Docs/Evidence/ArtSample02/metrics.json）"
    return out


def jload(p):
    return json.load(open(p, encoding="utf-8"))


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = datetime.datetime.now()
    rc_src = S3 + "/rules_check.json"
    rc = jload(rc_src)
    sheets = sheet1() + sheet2() + sheet3() + sheet4() + sheet5() + sheet6(rc)
    # rules_check.json はそのまま写す（数だけ。写真・形は入っていない）
    shutil.copyfile(rc_src, OUT + "/rules_check.json")
    spec = jload(S3 + "/study/sculpture_spec.json")
    fixrun = jload(S3 + "/fix01/fix1_run.json")
    critic_after = jload(S3 + "/fix01/critic_metrics_after.json")
    critic_before = jload(S3 + "/critic/critic_metrics.json")
    parts = {m: jload(S3 + "/fix01/crown/%s/fix1_parts_report.json" % m) for m in ("OUT", "IN")}
    crown_rep = {m: jload(S3 + "/crown/%s/as03_crown_report.json" % m) for m in ("OUT", "IN") if os.path.isfile(S3 + "/crown/%s/as03_crown_report.json" % m)}
    b2sum = S3 + "/surface/measure/B2_summary.json"
    r = rc["rules"]
    metrics = {
        "schema": "GreatWave.AS03.metrics/1",
        "created_local": t0.strftime("%Y-%m-%d %H:%M"),
        "sample": "美術の見本03（Q31）：波頭の立体の白い指の冠＋泡の皮＋唇の縁から垂れる滴、彫りの面、シェーダー 2 つ（FLAT・SCULPT）。修正の回 1 の後",
        "noteJa": "項目 → 値 → 合格／不合格／記録のみ。規則は Docs/Design/Art_Requirements_ja.md の測る規則（美術が届いたかは利用者が決める。Q29・Q30）。"
                  "描画は Unity 6000.4.3f1 の PC オフスクリーン（HMD 実機ではない）、t* = 12 s の静止だけ。彫刻の数は参照の彫刻（他者の展示作品、Q19・Q20）から測った数だけで、写真・写真から作った画像・OBJ の形は入れていない。",
        "variants": {
            "V1": {"crown": "OUT（彫刻のように外へ開く）", "shading": "SCULPT（彫刻のような艶と陰）"},
            "V2": {"crown": "OUT", "shading": "FLAT（浮世絵の平らな色）"},
            "V3": {"crown": "IN（原画視点の輪郭に収める）", "shading": "SCULPT"},
        },
        "rules": {k: {"by_variant": {v: rc["summary"]["by_variant"][v][k] for v in ("V1", "V2", "V3")},
                      "verdict": r[k].get("verdict"), "rule_ja": r[k].get("rule_ja")} for k in r},
        "rules_note_ja": "G2 は V3 が通れば合（V1・V2 の冠 OUT は原画の空へ指が出るので記録だけ）。全体：" + str(rc["summary"]["all_pass"]),
        "G2_gates_px": {v: {k: r["G2"]["variants"][v]["gates"][k]["claws"] for k in ("78", "130", "131", "132_s12", "72_s12_p95")} for v in ("V1", "V2", "V3")},
        "T4": {
            "crown_numbers": {m: {k: r["T4"]["crown_numbers"][m]["checks"][k] for k in r["T4"]["crown_numbers"][m]["checks"]} for m in ("OUT", "IN")},
            "crown_visibility_min": {v: r["T4"]["crown_visibility"][v]["min"] for v in ("V1", "V2", "V3")},
            "drip_fringe": r["T4"]["drip_fringe_fix1"],
            "drip_tongues": r["T4"]["drip_tongues"],
        },
        "C3_iou_painting_p10_p50_min": r["C3"]["iou_painting_p10_p50_min"],
        "C2_fail": r["C2"]["fail"],
        "T1": {"spacing_ratio_frac_area_in_0.64_1.56": r["T1"]["spacing_ratio"]["frac_area_in_0.64_1.56"],
               "stretch_tri_outside_1_3_to_3x": r["T1"]["stretch_grad_w"]["tri_outside_1_3_to_3x"]},
        "fix01_parts": {m: parts[m] for m in parts},
        "crown_B1_report": crown_rep,
        "B2_surface_summary": jload(b2sum) if os.path.isfile(b2sum) else None,
        "critic_record": {"before": critic_before, "after": critic_after,
                          "noteJa": "批評の測り（critic_measure.py）。判定に使わない記録。after は泡の皮も冠に数える。"},
        "S1_sculpture_spec": spec,
        "evaluator23_counts": ev23(),
        "fix01_fixed_ja": fixrun.get("fixed_ja"),
        "fix01_not_fixed_ja": fixrun.get("not_fixed_ja"),
    }
    json.dump(metrics, open(OUT + "/metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tools = [REPO + "/Tools/GWWaveGen/as03/" + f for f in sorted(os.listdir(REPO + "/Tools/GWWaveGen/as03")) if f.endswith((".py", ".sh", ".ps1", ".txt"))]
    unity = []
    for root, _, files in os.walk(REPO + "/Unity/Assets/GreatWave/ArtSample03"):
        for f in files:
            unity.append(os.path.join(root, f).replace("\\", "/"))
    unity.append(REPO + "/Unity/Assets/GreatWave/ArtSample03.meta")
    run = {
        "schema": "GreatWave.AS03.deliver_run/1",
        "created_local": t0.strftime("%Y-%m-%d %H:%M"),
        "tools": {"python": platform.python_version(), "numpy": numpy.__version__, "pillow": PIL.__version__,
                  "unity": "6000.4.3f1（PC オフスクリーン描画、batchmode、unity.lock で 1 つずつ。RTX 3080・Direct3D11・Linear）",
                  "blender": "5.2.2（冠 B1 の粘土の確かめだけ）", "houdini": "使っていない（B1 の VDB の試しは落とした）"},
        "commands_ja": [
            "# 調べ S1（彫刻）・S2（原画）・S3（見本02 の診断）：Tools/GWWaveGen/as03/s1_*.py・s2_*.py・as03_s3_*（記録は Build/Polish/sample03/study/）",
            "# B2 彫りの面とシェーダー：surf_relief.py → surf_kp_attr.py → surf_render.sh → surf_measure.py → surf_rules.py（surface/B2_run.json）",
            "# B1 冠：crown_whitemask.py --ver v2 → crown_build.py --mode OUT/IN → crown_gates.py → crown_render.py（crown/b1_run.json）",
            "# 組み立て：asm_claws35.py → asm_make_render_cs.py → asm_render.sh V1/V2/V3/V1_cmp/V1_ids/V3_ids → as02_asm_eval.sh → asm_rules.py → asm_sheets.py（assemble/asm_run.json）",
            "# 批評：critic_measure.py（critic/critic_metrics.json）",
            "# 修正の回 1：fix1_crown.py --mode OUT/IN → fix1_render.sh（6 回）→ as02_asm_eval.sh → fix1_rules.py → fix1_sheets.py → fix1_record.py（fix01/fix1_run.json）",
            "py -3.10 -B Tools/GWWaveGen/as03/as03_deliver.py   # この図・metrics.json・run.json・rules_check.json（描き直さない）",
        ],
        "records_sha256": {p.replace(REPO + "/", ""): sha(p) for p in (
            S3 + "/study/sculpture_spec.json", S3 + "/study/sculpture_study.md", S3 + "/surface/B2_run.json", S3 + "/surface/B2_surface_record_ja.md",
            S3 + "/crown/b1_run.json", S3 + "/crown/B1_record_ja.md", S3 + "/assemble/asm_run.json", S3 + "/critic/critic_metrics.json",
            S3 + "/fix01/fix1_run.json", S3 + "/fix01/critic_metrics_after.json", S3 + "/rules_check.json", S3 + "/rules_check_before_fix.json") if os.path.isfile(p)},
        "render_reports_sha256": {v: sha(R + "/%s/as03asm_render_report.json" % v) for v in ("V1", "V2", "V3", "V1_ids", "V3_ids", "V1_cmp")},
        "render_inputs_sha256": {p.replace(REPO + "/", ""): sha(p) for p in sorted(USED) if os.path.isfile(p)},
        "tools_sha256": {p.replace(REPO + "/", ""): sha(p) for p in tools},
        "unity_assets_sha256": {p.replace(REPO + "/", ""): sha(p) for p in sorted(unity) if os.path.isfile(p)},
        "outputs_sha256": {os.path.basename(p): sha(p) for p in sheets + [OUT + "/metrics.json", OUT + "/rules_check.json"]},
        "reference_handling_ja": [
            "参照モデル OBJ（wave_repair_zbrush2.obj、SHA-256 AB4124F9…3D40）：調べ S1 だけが数を測るため一時キャッシュで読み、測った後に消した（study/s1_objcache_log.json）。生成器は OBJ を読まない（F13-1）。",
            "彫刻の写真（G:/research/reality scan/北斋参考）：調べ S1・批評・組み立てが、Git 対象外の一時の縮めた写しで見た（名前と SHA-256 は study/s1_ref_tmp_log.json・critic/critic_ref_tmp_log.json・user_only/ref_asm/ref_asm_log.json）。"
            "この Docs の図に写真と写真から作った画像は入れていない。利用者だけの比べの図（user_only/）と、その写真の写しは Git 対象外。",
            "利用者の爪形分析・爪の模型：見本02 の 3D の爪をそのまま使った（マスク・模型は写していない）。",
            "原画 DP130155：メトロポリタン美術館の公開の画像（Docs/References/Met_JP1847_DP130155.jpg）を並べ図に置いた。原画カメラの投影はしていない。",
        ],
        "kept_unchanged_ja": "採用の場面・材質・スクリプト、見本01・02 のファイル、B1 の冠、B2 の彫りの面は変えていない（各描画の report で protectedUnchanged=True）。git の add・commit・push はしていない。",
        "elapsed_s": round((datetime.datetime.now() - t0).total_seconds(), 1),
    }
    json.dump(run, open(OUT + "/run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for p in sheets:
        print(p, Image.open(p).size)
    print(OUT + "/metrics.json", os.path.getsize(OUT + "/metrics.json"))
    print(OUT + "/run.json", os.path.getsize(OUT + "/run.json"))


if __name__ == "__main__":
    main()
