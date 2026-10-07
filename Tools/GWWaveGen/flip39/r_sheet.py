# -*- coding: utf-8 -*-
"""FLIP39 R：崩れる瞬間の座席の物差しの図（前＝FLIP37 P3、後＝この R）。py -3.10 r_sheet.py <箱の run_dir> <x_seat> <z_seat>
画：座席の目（乗る目）から、仰角が初めて 40° を越えた時と、仰角が最大の時。P3 は D1 の座席（r_before.py）。R は render/seat の同じ決め方のコマ。
加えて R の固定の斜めの画（空洞が閉じた時）。表は D1 §4.2 の定義の物差し（P3 の値は D1・E の記録、R の値は analysis_r.json と seat_r_z*.json）。
"""
import sys, os, json, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = r"C:/Windows/Fonts/YuGothM.ttc"
FONTB = r"C:/Windows/Fonts/YuGothB.ttc"
TOFF = 35.0
BEF = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/R/render/before"


def fmt(v, f="%.1f", unit=""):
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "来た" if v else "来ない"
    return (f % v) + unit


def main(rd, xs, zs):
    an = json.load(open(os.path.join(rd, "analysis_r.json"), encoding="utf8"))
    se = json.load(open(os.path.join(rd, "seat_r_z%+04d.json" % int(round(zs))), encoding="utf8"))
    ri = json.load(open(os.path.join(rd, "render", "render_info.json"), encoding="utf8"))
    bi = json.load(open(os.path.join(BEF, "before_info.json"), encoding="utf8"))
    seat = [r for r in se["scan"] if abs(r["x_seat"] - xs) < 0.3][0]
    ride = seat["ride"]
    row = an["rows"]["%d" % int(round(zs))]
    ev = row["events"]
    # R の画のコマ
    st = ri["track"]
    fr = np.array(st["frames"]); tg = (fr - 1) / 24.0 + TOFF
    ser = None
    for r in se.get("series_best") and [se] or []:
        pass
    # 乗る目の仰角（seat_r の series は best の座席のもの。座席が best でなければ render_info の頂の仰角で代える）
    sb = se.get("series_best") or {}
    if se.get("best_seat") and abs(se["best_seat"]["x_seat"] - xs) < 0.3 and sb.get("alpha"):
        ta = np.array(sb["t_group"]); aa = np.array(sb["alpha"])
    else:
        ta = tg; aa = np.array(st["alpha"])
    t40 = float(ta[np.argmax(aa >= 40.0)]) if (aa >= 40).any() else float(ta[np.argmax(aa)])
    tmx = float(ride.get("t_alpha_max") or ta[np.argmax(aa)])
    f40 = int(round((t40 - TOFF) * 24)) + 1; fmx = int(round((tmx - TOFF) * 24)) + 1
    # 後の 3 枚目：z −60 m の列で空洞が閉じた時（R で前へ巻いて空洞を閉じた列。座席の列 −80 m は頂の先から崩れて形が乱れた）
    ev60 = (an["rows"].get("-60") or {}).get("events") or {}
    tcl = (ev60.get("tube_closed_or_nearly") or {}).get("t")
    fcl = int(round(tcl * 24)) + 1 if tcl is not None else fmx
    fz = int(round((float(ride.get("end_t_group") or tmx) - 0.4 - TOFF) * 24)) + 1   # 乗る目の終わりの 0.4 秒前（動画の止めた画）
    W, H = 600, 338
    im = Image.new("RGB", (3 * W + 40, 60 + 2 * (H + 40) + 760), (250, 250, 248))
    dr = ImageDraw.Draw(im)
    fb = ImageFont.truetype(FONTB, 26); f1 = ImageFont.truetype(FONT, 19); f2 = ImageFont.truetype(FONT, 17)
    dr.text((14, 12), "崩れる時の座席の物差し　前＝FLIP37 P3（粒子 0.25 m）　後＝R（E3 の主役の範囲、粒子 0.3 m、座席 x %.0f m・z %.0f m）　どれも物理だけ" % (xs, zs), fill=(20, 20, 20), font=fb)

    def put(path, x, y, cap):
        if path and os.path.exists(path):
            a = Image.open(path).convert("RGB").resize((W, H)); im.paste(a, (x, y))
        else:
            dr.rectangle([x, y, x + W, y + H], outline=(180, 180, 180))
        dr.text((x + 4, y + H + 6), cap, fill=(30, 30, 30), font=f2)
    y1 = 60
    put(bi["ride40"]["out"], 10, y1, "前 P3：乗る目の仰角が初めて 40° を越えた時（t %.2f s）" % bi["ride40"]["t"])
    put(bi["ride_m04"]["out"], 20 + W, y1, "前 P3：乗る目の終わり（9.2 s）の 0.4 秒前（仰角 %.0f°、t %.2f s）" % (bi["ride_m04"]["alpha"], bi["ride_m04"]["t"]))
    put(bi["fixed"]["out"], 30 + 2 * W, y1, "前 P3：固定の目が水に入る直前（仰角 %.0f°、t %.2f s）" % (bi["fixed"]["alpha"], bi["fixed"]["t"]))
    y2 = y1 + H + 40
    put(os.path.join(rd, "render", "seat", "f%04d.png" % f40), 10, y2, "後 R：乗る目の仰角が初めて 40° を越えた時（群の時刻 %.2f s）" % ((f40 - 1) / 24 + TOFF))
    put(os.path.join(rd, "render", "seat", "f%04d.png" % fz), 20 + W, y2, "後 R：乗る目の終わり（%.2f s）の 0.4 秒前（群の時刻 %.2f s）" % (ride.get("end_t_group") or 0, (fz - 1) / 24 + TOFF))
    put(os.path.join(rd, "render", "oblique", "f%04d.png" % fcl), 30 + 2 * W, y2, "後 R：固定の斜め、z −60 m の列で空洞が閉じた時（群の時刻 %.2f s）" % ((fcl - 1) / 24 + TOFF))
    # 表
    fv = ev.get("face_past_vertical") or {}
    r60 = an["rows"].get("-60") or {}
    ev60 = r60.get("events") or {}
    fv60 = ev60.get("face_past_vertical") or {}
    tc60 = ev60.get("tube_closed_or_nearly") or {}
    chm = an["crest_history_main"]
    kmax = int(np.argmax(chm["crest"]))
    hmax = float(chm["crest"][kmax])
    # 【10/8 レビューで直した】P3 の列を R と同じ「乗る目」の値にそろえる（前の版は固定の目の値が混ざっていた）。
    # P3 の乗る目の値は D1 の seat_measures_raw.json（alpha_riding）と seat_raw.json（stats_ride）から、乗る目の終わり 9.2 s までで求める。
    D1 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/D1/"
    d1s = json.load(open(D1 + "seat_measures_raw.json", encoding="utf8"))["series"]
    d1f = json.load(open(D1 + "seat_raw.json", encoding="utf8"))["seat"]["frames"]
    p_t = np.array(d1s["t"], float); p_a = np.array([np.nan if v is None else v for v in d1s["alpha_riding"]], float)
    P_END = 9.2
    pm = p_t <= P_END + 1e-6
    p_dt = float(np.median(np.diff(p_t)))
    p_hemi = max(f["stats_ride"]["upper_hemi_frac"] for f in d1f if f["t"] <= P_END + 1e-6)
    p_fill = max(f["stats_ride"]["hmd_fill"] for f in d1f if f["t"] <= P_END + 1e-6)
    p_view = P_END - float(p_t[pm][np.argmax(np.nan_to_num(p_a[pm]) >= 10.0)])
    p_t45 = float(np.sum(np.nan_to_num(p_a[pm]) >= 45.0) * p_dt)
    p_a2 = float(p_a[np.argmin(np.abs(p_t - (P_END - 2.0)))])
    r_ser = se["best_seat"]["ride"]["series"] if abs(se["best_seat"]["x_seat"] - xs) < 0.3 else None
    if r_ser:
        r_t = np.array(r_ser["t_group"], float); r_a = np.array(r_ser["alpha"], float); r_end = float(ride.get("end_t_group"))
        rm = r_t <= r_end + 1e-6
        r_t45 = float(np.sum(r_a[rm] >= 45.0) * np.median(np.diff(r_t)))
        r_a2 = float(r_a[np.argmin(np.abs(r_t - (r_end - 2.0)))])
    else:
        r_t45 = r_a2 = None
    m1e = row.get("m1")
    rows = [
        ("物差し", "前：FLIP37 P3", "後：この R", "定義・注"),
        ("座席の列の最も高い水面（静かな水面から）", "20.95 m（計算）", "%.1f m（%.2f s・x %.0f m）" % (hmax, chm["t_group"][kmax], chm["x"][kmax]),
         "R はずれ %.2f m を引いた（推定）。P3 はずれの扱いが D1 に未記載" % an["off_box_m"]),
        ("最も高い水面 ÷ 入口の波", "1.06（R18、D1）", "%.2f（E の m1 の決め方では %.2f）" % (hmax / an["m1_den_m"], m1e or 0),
         "分母＝E3 の入口の波 %.2f m。E の m1 の分子は断面の頂" % an["m1_den_m"]),
        ("崩れ方（座席の列 z %.0f m）" % zs, "巻く（細い唇）", "頂の先から崩れ始め（%.1f s）、乱れた頂で進む" % (fv.get("t_group") or 0), "断面の粒子（目で見た）と p1_analyze"),
        ("崩れ方（z −60 m の列）", "—", "前へ巻き空洞が閉じた（%.1f s・x %.0f m・%.0f m²）" % ((tc60.get("t") or 0) + TOFF, tc60.get("x") or 0, tc60.get("closed_area_m2") or 0),
         "垂直を過ぎた %.2f s・x %.0f m、その前の頂 %.1f m" % (fv60.get("t_group") or 0, fv60.get("x") or 0, r60.get("crest_max_before_overturn_still_m") or 0)),
        ("前の面の弦（座席の列、仰角が最大の時）", "36°（D1）", fmt(ride.get("chord_at"), "%.0f", "°"), "目の高さの足 → 頂"),
        ("唇の先 − 前の面の足（lip lead）", "−17.5 m", fmt(ride.get("lip_lead_max"), "%+.1f", " m"), "＋なら唇が足より座席の側へ出る（頭上に崩れる）"),
        ("唇が頭上に来た（目が乾いている間）", "来ない（乗る目は船が頂へ）", fmt(ride.get("lip_overhead")), "座席の列で一番上の水面が目より 1 m 上・水の区間が 2 つ以上"),
        ("仰角の最大（乗る目）", "68°", fmt(ride.get("alpha_max"), "%.0f", "°"), "目から最も高く見える水。前の面が目から %.1f m の時" % (ride.get("dist_at") or 0)),
        ("終わりの 2 秒前の仰角（乗る目）", "%.0f°" % p_a2, fmt(r_a2, "%.0f", "°"), "見上げる高さが続くか（最大は終わりの直前だけ）"),
        ("仰角 45° 以上の時間（乗る目）", "%.2f s" % p_t45, fmt(r_t45, "%.2f", " s"), "首を上げて見る高さにある時間"),
        ("前の窓（±55°×0〜55°）の水（乗る目）", "%.2f" % p_fill, fmt(ride.get("hmd_fill_max"), "%.2f"), "PS VR2 の視野を水平に置いた上半分"),
        ("上の半球の水（乗る目）", "%.2f" % p_hemi, fmt(ride.get("hemi_max"), "%.2f"), "地平線より上の半球のうち水の立体角"),
        ("仰角 10° を越えてから終わりまで（乗る目）", "%.1f s" % p_view, fmt(ride.get("view_s"), "%.1f", " s"), "乗る目の終わり：%s（%.2f s）。P3 は 9.2 s 船が頂へ" % (ride.get("end_why") or "—", ride.get("end_t_group") or 0)),
        ("育つ分の割合（仰角 10° 以上）", "—", fmt(ride.get("growth_share"), "%.2f"), "仰角の伸びのうち頂が高くなる分（残りは近づく分）"),
    ]
    y = y2 + H + 50
    cw = [400, 250, 520, 670]
    for i, r in enumerate(rows):
        x = 10
        for j, c in enumerate(r):
            dr.text((x + 4, y), str(c), fill=(20, 20, 20) if i else (0, 0, 0), font=fb if i == 0 else f1)
            x += cw[j]
        y += 36 if i == 0 else 34
        dr.line([10, y - 4, sum(cw), y - 4], fill=(210, 210, 210))
    dr.text((10, y + 8), "P3 の値は D1 の記録（P3 は置き方の倍率 1.1 を通した作品の長さ、R は倍率なし）。座席の目は船が上下だけ水面に乗る目で、傾き・押し流し・転覆は入れていない。境目の値は D1 の目安で、PS VR2 で確かめていない。",
            fill=(80, 80, 80), font=f2)
    dr.text((10, y + 34), "10/8 レビュー：P3 の列を乗る目の値にそろえた（前の版は上の半球・見る時間が固定の目の値だった）。P3 の座席は D1 の seat_v1 のまま、R の座席は 3 列・36 か所を調べて選んだ所。測る道具も違う（D1 と r_seat.py）。",
            fill=(150, 40, 40), font=f2)
    im = im.crop((0, 0, im.width, y + 76))
    im.save(os.path.join(rd, "sheet_seat_before_after.png"))
    print("sheet ok", f40, fmx, fcl)


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]))
