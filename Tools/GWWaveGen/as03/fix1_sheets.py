# -*- coding: utf-8 -*-
"""美術の見本03 修正の回 1：並べ図（asm_sheets.py をそのまま使い、描画を Build/Polish/sample03/fix01/render、図を fix01/sheets へ替えた）。
足した図：
  fix1_0_before_after.png   前（組み立て）｜後（修正の回 1）：原画視点の波頭の拡大・波頭の回り台 45°・135°・座席・後ろ 65°・回り台 210°（V1）と V3 の原画視点
  fix1_7_numbers_fix.png    修正の回 1 の数：T4 の冠が見える割合の最小（前・後）、垂れる滴、泡の皮、批評の測り（白のうち冠の割合・白の明るさ）
  user_only/sculpture_vs_V1_fix01.png（利用者だけ。写真を含む。リポジトリと成果物へ入れない）：彫刻の写真｜修正の回 1 の V1（組み立てと同じ向き）
使い方：py -3.10 -B Tools/GWWaveGen/as03/fix1_sheets.py [all|user]
"""
import json
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asm_sheets as A  # noqa: E402

S3 = A.S3
FIX = S3 + "/fix01"
BEFORE = S3 + "/assemble/render"
JV = {"pass": "合", "fail": "不合"}
A.R = FIX + "/render"
A.OUTD = FIX + "/sheets"
A.VN = dict(A.VN)
A.VN["V1"] = "V1（修正の回 1）冠 OUT＋泡の皮・垂れる滴 ＋ SCULPT"
A.VN["V2"] = "V2（修正の回 1）冠 OUT＋泡の皮・垂れる滴 ＋ FLAT"
A.VN["V3"] = "V3（修正の回 1）冠 IN＋泡の皮・垂れる滴（原画視点の輪郭に収める）＋ SCULPT"


def before_after():
    rows = [("views/painting_t120_claws.png", (0, 0, 1280, 720), "原画視点の波頭の拡大"),
            ("crest/t120_az045_claws.png", (240, 135, 1680, 945), "波頭の回り台 45°（正面）"),
            ("crest/t120_az135_claws.png", (240, 135, 1680, 945), "波頭の回り台 135°（右の側面）"),
            ("views/seat_t120_claws.png", None, "座席（VR の視点）"),
            ("views/back65_t120_claws.png", None, "後ろ 65°"),
            ("tt/t120_az210_claws.png", None, "回り台 210°（背）")]
    cells = []
    for f, crop, j in rows:
        cells.append((BEFORE + "/V1/" + f, "前（組み立て）V1 ／ " + j, crop))
        cells.append((A.R + "/V1/" + f, "後（修正の回 1）V1 ／ " + j, crop))
    cells.append((BEFORE + "/V3/views/painting_t120_claws.png", "前（組み立て）V3 ／ 原画視点の波頭の拡大", (0, 0, 1280, 720)))
    cells.append((A.R + "/V3/views/painting_t120_claws.png", "後（修正の回 1）V3 ／ 原画視点の波頭の拡大", (0, 0, 1280, 720)))
    return A.sheet("美術の見本03 修正の回 1：前（組み立て）｜後（修正の回 1）", cells, 2, 960, 540, A.OUTD + "/fix1_0_before_after.png",
                   "後：B1 の冠はそのまま、前の白の地を泡の瘤の皮（指の背の列）で覆い、唇の縁に立体の滴を垂らした。材質の値（白の陰の明るさ・溝の青・藍の艶）も替えた")


def numbers_fix():
    rc = json.load(open(S3 + "/rules_check.json", encoding="utf-8"))
    rb = json.load(open(S3 + "/rules_check_before_fix.json", encoding="utf-8"))
    t4, t4b = rc["rules"]["T4"], rb["rules"]["T4"]
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((14, 12), "美術の見本03 修正の回 1：直した所の数（rules_check.json・rules_check_before_fix.json）", font=A.font(30, True), fill=(10, 10, 10))
    f, fb = A.font(21), A.font(21, True)
    y = 70
    lines = []
    for v in ("V1", "V2", "V3"):
        cb, ca = t4b["crown_visibility"][v]["min"], t4["crown_visibility"][v]["min"]
        lines.append(("T4 %s" % v, "冠が見える割合の最小（原画視点のほかの 26 視点、基準 0.5%% より多い）：前 %.2f%%（%s）→ 後 %.2f%%（%s）。T4 の判定：前 %s → 後 %s" % (
            100 * cb["frac"], cb["view"], 100 * ca["frac"], ca["view"], JV[t4b["verdict_by_variant"][v]], JV[t4["verdict_by_variant"][v]])))
    for m in ("OUT", "IN"):
        dd = t4["drip_fringe_fix1"][m]
        c = dd["checks"]
        r = dd["record"]
        lines.append(("滴 %s" % m, "唇の縁から垂れる滴 %d 本（外した %d）、間隔の中央値 %.2f m（0.6〜1.0）、長さの中央値 %.2f m（0.6〜1.45）、幅の中央値 %.2f m（0.30〜0.48）：%s" % (
            r["drips"], r["dropped"], c["spacing_p50_m"]["value"], c["length_p50_m"]["value"], c["width_max_p50_m"]["value"], "合" if dd["pass_all"] else "不合")))
        fo = r["foam"]
        lines.append(("泡 %s" % m, "泡の瘤 %d 個・指の背の列 %d 本（頂に並ぶ向きの間隔の中央値 %.2f m）、瘤の高さの中央値 %.2f m、面より上の皮 %.0f m²" % (
            fo["lumps"], fo["chains"], fo["chain_spacing_w_m"]["p50"], fo["lump_height_m"]["p50"], fo["skin_area_above_surface_m2"])))
    cr = t4["critic_metrics_before_after_record"]["by_variant"]
    for v in ("V1", "V3"):
        for k in ("crest/045", "crest/090", "views/seat", "views/painting"):
            x = cr[v].get(k)
            if not x:
                continue
            lines.append(("批評 %s" % v, "%s：見える白のうち冠 %.2f → %.2f、白の明るさ p25/p50/p75 %s → %s、白の中の暗い塊 %d → %d" % (
                k.replace("crest/", "波頭 ").replace("views/", ""), x["crown_share_of_white"][0] or 0, x["crown_share_of_white"][1] or 0,
                "/".join(str(t) for t in x["white_lum_p25_p50_p75"][0]), "/".join(str(t) for t in x["white_lum_p25_p50_p75"][1]),
                x["dark_crown_blobs"][0], x["dark_crown_blobs"][1])))
    g2 = rc["rules"]["G2"]["variants"]["V3"]["gates"]
    lines.append(("G2 V3", "原画視点の関門（px、4 以下で合）：78 %.3f・130 %.3f・131 %.3f・132 σ12 %.3f・72 σ12 p95 %.3f" % tuple(g2[k]["claws"] for k in ("78", "130", "131", "132_s12", "72_s12_p95"))))
    lines.append(("全体", "判定：" + "・".join("%s %s" % (k, "合" if x == "pass" else "不合") for k, x in rc["summary"]["verdicts"].items())))
    for name, txt in lines:
        d.text((14, y), name, font=fb, fill=(0, 0, 0))
        t = txt
        maxw = W - 200
        while t:
            n = len(t)
            while n > 1 and d.textlength(t[:n], font=f) > maxw:
                n -= 1
            if n < len(t):
                k = max(t.rfind(ch, 0, n) for ch in "・、。 ")
                if k > n * 0.6:
                    n = k + 1
            d.text((170, y), t[:n], font=f, fill=(30, 30, 30))
            t = t[n:]
            y += 28
        y += 4
    d.text((14, H - 32), A.FOOT, font=A.font(18), fill=(70, 70, 70))
    p = A.OUTD + "/fix1_7_numbers_fix.png"
    img.save(p)
    return p


def user_sheet_fix():
    pairs = [("front", "正面（正面图）", "修正の回 1 の V1：方位 30°・仰角 15°"), ("right45", "右45（右45）", "修正の回 1 の V1：方位 −15°・仰角 28°"),
             ("left45", "左45（左45）", "修正の回 1 の V1：方位 75°・仰角 28°"), ("back", "背（背图）", "修正の回 1 の V1：方位 210°・仰角 18°"),
             ("top", "上（顶图、）", "修正の回 1 の V1：方位 30°・仰角 85°")]
    W, rowh, top = 1920, 560, 110
    Hh = top + rowh * len(pairs) + 50
    img = Image.new("RGB", (W, Hh), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((14, 12), "利用者だけ：参照の彫刻の写真｜見本03 修正の回 1 の V1（冠 OUT＋泡の皮・滴＋SCULPT）を近い向きから", font=A.font(30, True), fill=(10, 10, 10))
    d.text((14, 56), "写真は他者の展示作品（Q19・Q20、参考にとどめ写し取らない）。この図はリポジトリ・成果物・Docs へ入れない（Git 対象外）。"
                     "方位は回り台と同じ決め方（0° = 原画の側、反時計回り）。", font=A.font(19), fill=(150, 0, 0))
    used = []
    for i, (k, pj, vj) in enumerate(pairs):
        y = top + i * rowh
        pp = A.REF + "/%s.png" % k
        vp = A.R + "/V1_cmp/cmp/%s.png" % k
        img.paste(A.fit(Image.open(pp), 720, 540), (10, y))
        img.paste(A.fit(Image.open(vp), 960, 540), (750, y))
        A.label(d, 20, y + 10, "写真：" + pj, 22, True, zh=True)
        A.label(d, 760, y + 10, vj, 22, True)
        used.append({"key": k, "photo_tmp": pp, "photo_tmp_sha256": A.sha(pp), "render": vp, "render_sha256": A.sha(vp)})
    d.text((14, Hh - 36), A.FOOT, font=A.font(18), fill=(70, 70, 70))
    p = S3 + "/user_only/sculpture_vs_V1_fix01.png"
    img.save(p)
    log = {"noteJa": "利用者だけの比べの図（修正の回 1）。写真は組み立てと同じ一時の縮めた写し（user_only/ref_asm、名前と SHA-256 は ref_asm_log.json。新しい写しは作っていない）。"
                     "リポジトリと成果物へ入れない。要らなくなったら、この図と写しを消す。", "output": p, "output_sha256": A.sha(p), "used": used}
    json.dump(log, open(S3 + "/user_only/sculpture_vs_V1_fix01_log.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return p


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    res = []
    if what in ("all", "sheets"):
        res += A.all_sheets()
        res.append(before_after())
        res.append(numbers_fix())
    if what in ("all", "user"):
        res.append(user_sheet_fix())
    print("\n".join(res))
