# -*- coding: utf-8 -*-
"""FLIP39 まとめ（10/8）：高い波の段（D1・D2・D3・E・R・レビュー）の証拠を Docs/Evidence/FLIPTallWave へまとめる（py -3.10、PIL）。
新しい流体計算・描画はしない（例外：実験の比べの図 ft_2_experiments.png を、すでにある JSON から描く）。
- 座席の仰角の数（最大・45° 以上・25° 以上・終わりの 2 秒前）は rv_angle_timeline.py の stats と同じ式で、
  P3（D1 の seat_measures_raw.json）、V1・R（seat_r_z-080.json）、E の各計算（seat_e.json の best_seat の乗る目）から求める。
- 動画・図は Unity/Build/FLIP39（Git 対象外）から写し、SHA-256 を copies.json・run.json に書く。
使い方: py -3.10 -B ft_deliver.py
"""
import os, sys, json, glob, shutil, hashlib, subprocess, datetime
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = r"G:/Unity/GreatWave_2026_Fresh"
B = ROOT + "/Unity/Build/FLIP39/"
EV = ROOT + "/Docs/Evidence/FLIPTallWave/"
FFPROBE = r"G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffprobe.exe"
FONT = r"C:/Windows/Fonts/YuGothM.ttc"
FONTB = r"C:/Windows/Fonts/YuGothB.ttc"
sys.path.insert(0, ROOT + "/Tools/GWWaveGen/flip39")
import rv_angle_timeline as rv  # noqa: E402


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


# ---------- 座席の数（同じ式） ----------
def seat_stats():
    out = {}
    for nm, t, a, te, col, view in rv.load():
        key = "P3" if nm.startswith("P3") else ("V1" if nm.startswith("V1") else "R")
        s = rv.stats(t, a, te)
        if view is not None:
            s["view"] = float(view)
        out[key] = s
    for r in ["E1_flat_S036", "E1_reef_S036", "E1_reef_S048", "E1h_reef_S048", "E1_reef_S060", "E1L_reef_S048", "E2_dir20_reef", "E3_dir20_lens"]:
        d = json.load(open(B + "E/%s/seat_e.json" % r, encoding="utf8"))
        bs = d["best_seat"]; ri = bs["ride"]; se = ri["series"]
        t = np.array(se["t_group"], float)
        a = np.array([np.nan if v is None else v for v in se["alpha"]], float)
        s = rv.stats(t, a, float(ri["end_t_group"]))
        s.update(view=float(ri["view_s"]), growth_share=float(ri["growth_share"]), lip_overhead=bool(ri["lip_overhead"]), x_seat=float(bs["x_seat"]))
        out[r] = s
    rr = json.load(open(B + "R/H30_E3/seat_r_z-080.json", encoding="utf8"))["best_seat"]["ride"]
    out["R"]["growth_share"] = float(rr["growth_share"])
    vv = json.load(open(B + "R/V1_val_d10/seat_r_z-080.json", encoding="utf8"))["best_seat"]["ride"]
    out["V1"]["growth_share"] = float(vv["growth_share"])
    return {k: {kk: (round(vv_, 3) if isinstance(vv_, float) else vv_) for kk, vv_ in v.items()} for k, v in out.items()}


# ---------- 実験の並び（値の出典は各記録） ----------
def rows(E, S):
    t = {r["run_id"]: r for r in json.load(open(B + "E/table.json", encoding="utf8"))}
    R = [
        dict(id="FLIP37_R18_P3", name="FLIP37 R18／P3（前の作品の元）", mech="±30° の二つの列を t=0 に重ねて置く（初めに大きな波）",
             entry=19.5, crest=20.6, m1=1.06, brk="巻く（細い唇）", seat="P3", src="D1 §1.2（R18）、P3 の座席は D1 seat_v1"),
    ]
    spec = [
        ("E1_flat_S036", "E1 平らな海 S0.36", "分散による集中だけ（地形なし）", "崩れない"),
        ("E1_reef_S036", "E1 岩棚 S0.36", "＋浅くなる（斜面 1:4・岩棚 26 m）", "崩れない"),
        ("E1_reef_S048", "E1 岩棚 S0.48", "振幅を一段上げる", "前へ巻く（岩棚の縁）"),
        ("E1_reef_S060", "E1 岩棚 S0.60", "振幅をもう一段上げる", "前へ巻く（頂は S0.48 と同じ）"),
        ("E1L_reef_S048", "E1L 長い水槽 S0.48", "集める距離 406→1006 m", "尖った山（巻く前に水槽の端）"),
        ("E2_dir20_reef", "E2 向き 20°＋岩棚", "＋向きの広がり σθ 20°（向きの集中）", "前へ巻く（設計した所）"),
        ("E3_dir20_lens", "E3 ＋海底の盛り上がり", "＋波長と同じ幅の盛り上がり（屈折）", "前へ巻く（設計から 40 m 横）"),
    ]
    for rid, nm, mech, brk in spec:
        r = t[rid]
        R.append(dict(id=rid, name=nm, mech=mech, entry=round(r["m1_den_m"], 2), crest=round(r["m1_num_m"], 2), m1=round(r["m1"], 2), brk=brk, seat=rid,
                      src="E/table.json（m1_den_m・m1_num_m・m1）、E の記録 §1・§5"))
    R.append(dict(id="R_H30_E3", name="R（E3 を粒子 0.3 m で）", mech="E3 の主役の範囲を細かく（条件は同じ）",
                  entry=7.98, crest=17.0, m1=2.14, brk="頂の先から崩れ乱れた頂（z −60 で巻く）", seat="R",
                  src="R の記録 §1・§5.2（座席の列の最も高い水面 17.0 m、垂直を過ぎる前の頂 15.6 m）"))
    for r in R:
        s = S.get(r["seat"], {})
        r["seat_vals"] = s
    return R


def draw_sheet(R, out):
    W, H = 1900, 1180
    im = Image.new("RGB", (W, H), (252, 252, 250))
    dr = ImageDraw.Draw(im)
    fb = ImageFont.truetype(FONTB, 28); fh = ImageFont.truetype(FONTB, 17); f1 = ImageFont.truetype(FONT, 17); f2 = ImageFont.truetype(FONT, 15)
    dr.text((24, 16), "高い波を作る仕組みの実験の比べ：計算の中で頂は育ったが、座席から高く見える時間は延びていない", fill=(12, 12, 12), font=fb)
    dr.text((24, 58), "どれも物理だけ（波を起こすのは水槽の端の造波の帯と海底の形だけ。計算の中に力・速さを足していない）。座席の数は「乗る目」（船が上下だけ水面に乗る）で、"
            "rv_angle_timeline.py と同じ式。\n頂は静かな水面からの高さ（水面のずれを引いた値）。入口＝造波の帯を出た所の最も高い頂（FLIP37 は t=0 に置いた頂）。E は粒子 1 m、R は 0.3 m、P3 は 0.25 m。",
            fill=(80, 80, 78), font=f2, spacing=4)
    cols = [("計算", 24), ("足した仕組み", 300), ("頂：入口 → 崩れる時（m）", 640), ("育った比", 1010), ("崩れ方（目で見た）", 1090),
            ("最大仰角", 1395), ("≥45°", 1490), ("≥25°", 1570), ("2秒前", 1650), ("育つ分", 1720), ("唇が頭上", 1800)]
    y = 118
    for nm, x in cols:
        dr.text((x, y), nm, fill=(20, 20, 20), font=fh)
    y += 30
    dr.line([(24, y), (W - 24, y)], fill=(180, 180, 180))
    bx0, bx1, vmax = 640, 990, 22.0
    X = lambda v: bx0 + (bx1 - bx0) * v / vmax
    rh = 62
    for i, r in enumerate(R):
        yy = y + 8 + i * rh
        if i % 2 == 0:
            dr.rectangle([24, yy - 4, W - 24, yy + rh - 8], fill=(244, 244, 241))
        dr.text((30, yy + 4), r["name"], fill=(20, 20, 20), font=f1)
        dr.multiline_text((300, yy + 4), wrap(r["mech"], 22), fill=(60, 60, 60), font=f2, spacing=2)
        dr.rectangle([X(0), yy + 6, X(r["entry"]), yy + 20], fill=(170, 190, 215))
        dr.rectangle([X(0), yy + 26, X(r["crest"]), yy + 40], fill=(40, 80, 140))
        dr.text((X(r["entry"]) + 6, yy + 4), "%.1f" % r["entry"], fill=(90, 110, 140), font=f2)
        dr.text((X(r["crest"]) + 6, yy + 24), "%.1f" % r["crest"], fill=(40, 80, 140), font=f2)
        col = (180, 60, 40) if r["m1"] >= 1.5 else (60, 60, 60)
        dr.text((1010, yy + 14), "%.2f" % r["m1"], fill=col, font=fh)
        dr.multiline_text((1090, yy + 4), wrap(r["brk"], 19), fill=(40, 40, 40), font=f2, spacing=2)
        s = r["seat_vals"]
        if s:
            dr.text((1400, yy + 14), "%.0f°" % s["max"], fill=(20, 20, 20), font=f1)
            dr.text((1490, yy + 14), "%.2f s" % s["t45"], fill=(180, 60, 40) if s["t45"] > 0 else (120, 120, 120), font=f1)
            dr.text((1570, yy + 14), "%.2f s" % s["t25"], fill=(20, 20, 20), font=f1)
            dr.text((1650, yy + 14), "%.0f°" % s["a2"], fill=(20, 20, 20), font=f1)
            gs = s.get("growth_share")
            dr.text((1720, yy + 14), "—" if gs is None else "%.2f" % gs, fill=(20, 20, 20), font=f1)
            lo = s.get("lip_overhead")
            if r["seat"] == "P3":
                lo = False
            if r["seat"] == "R":
                lo = True
            dr.text((1800, yy + 14), "—" if lo is None else ("来た" if lo else "来ない"), fill=(20, 20, 20), font=f1)
    yb = y + 8 + len(R) * rh + 4
    for gv in (0, 5, 10, 15, 20):
        dr.line([(X(gv), y + 4), (X(gv), yb - 6)], fill=(220, 220, 220))
        dr.text((X(gv) - 6, yb - 4), "%d" % gv, fill=(130, 130, 130), font=f2)
    dr.rectangle([bx0, yb + 18, bx0 + 16, yb + 30], fill=(170, 190, 215)); dr.text((bx0 + 22, yb + 14), "入口の頂", fill=(80, 80, 80), font=f2)
    dr.rectangle([bx0 + 110, yb + 18, bx0 + 126, yb + 30], fill=(40, 80, 140)); dr.text((bx0 + 132, yb + 14), "崩れる時の頂（崩れないものは最も高い頂）", fill=(80, 80, 80), font=f2)
    notes = [
        "読み方（測った値から）",
        "1. 頂は計算の中で入口の 1.55〜2.37 倍に育った（前の作品の元 R18 は 1.06 倍で、高さの 95 % を初めに置いていた）。一方向では入力を上げても崩れる頂は 12.5 m で止まり、向きの集中（＋11 %）と屈折（＋20 %）で 16.6 m まで上がった。",
        "2. それでも、座席から 45° 以上に見える時間は 0〜0.83 秒で、P3 の 0.58 秒から延びていない。2 秒前の仰角はどれも 30° 未満。崩れる頂も P3（20.95 m）より低い。",
        "3. 育つ分の割合（仰角の伸びのうち頂が高くなる分）は 0.00〜0.12。座席から見て仰角が上がるのは、波が近づくからで、育つからではない。頂が 2 倍に育つのは座席から 80〜200 m 先（仰角 2〜15°）だった。",
        "注：P3 の座席は D1 の seat_v1、E・R の座席は調べて選んだ所（選び方が違う）。E1 平らな海・E1 岩棚 S0.36・E1L は崩れる前に終わるので、座席の値は崩れの値ではない。境目の 25°・45° は D1 の目安で PS VR2 で確かめていない。",
    ]
    yn = yb + 46
    for k, n in enumerate(notes):
        dr.multiline_text((24, yn), wrap(n, 120), fill=(20, 20, 20) if k == 0 else (60, 60, 60), font=fh if k == 0 else f2, spacing=3)
        yn += 24 * (1 + wrap(n, 120).count("\n")) + 4
    im = im.crop((0, 0, W, min(H, yn + 16)))
    im.save(out)


def wrap(s, n):
    out, line = [], ""
    for ch in s:
        line += ch
        if len(line) >= n:
            out.append(line); line = ""
    if line:
        out.append(line)
    return "\n".join(out)


def probe(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries", "format=duration:stream=width,height,codec_name", "-of", "json", p],
                       capture_output=True, text=True)
    j = json.loads(r.stdout)
    st = j["streams"][0]
    return dict(duration_s=round(float(j["format"]["duration"]), 3), w=st["width"], h=st["height"], codec=st["codec_name"])


COPIES = [
    ("ft_v1_seat_x530_z-80.mp4", "R/videos/R_seat_x530_z-80.mp4",
     "座席の動画（実時間 13.3 s）。群の時刻 75.0〜84.5 s は座席の乗る目（x 530 m・z −80 m、目＝船の下の水面＋1.83 m、沖を向く）。84.04 s の画を 0.75 秒止め、84.5 s より後は座席の 45 m 後ろから。R（粒子 0.3 m）・物理だけ"),
    ("ft_v1b_seat_x530_z-80_half.mp4", "R/videos/R_seat_x530_z-80_half.mp4", "同じ座席の動画の半分の速さ（26.6 s）"),
    ("ft_v2_side_sections.mp4", "FT/R_side_sections.mp4",
     "横から見た断面の動画（縦横同じ縮尺、実時間 12.5 s＋最後 1 秒止め）。上＝座席の列 z −80 m（赤の線＝座席、灰の箱＝上下だけ水面に乗せた船）、下＝いちばんはっきり巻いた列 z −60 m。茶＝R の粒子 0.3 m（水面の下 5 m 前後の帯）。ft_side_video.py で 10/8 に描いた"),
    ("ft_v3_painting_camera.mp4", "R/videos/R_painting_camera.mp4",
     "原画カメラと原画（Met JP1847）の並べ（12.5 s）。雰囲気の参考だけで、合わせの点数は付けない（Q39）。86.04 s からカメラが水に入る（印あり）"),
    ("ft_v4_oblique_fixed.mp4", "R/videos/R_oblique_fixed.mp4",
     "固定の斜め（岸の側・峰の手前の高い所から、12.5 s）。箱の全部で、伝わる → 立ち上がる → 崩れる → 崩れた水の広がり。粘土色＝粒子 0.3 m、青みの灰＝外の E3（粒子 1 m）"),
    ("ft_1_crash_compare.png", "R/sheet_seat_before_after.png",
     "崩れる時の比べ（前＝FLIP37 P3、後＝R の座席 x 530 m・z −80 m）。画 6 枚と座席の物差しの表（10/8 レビューで P3 を乗る目の値にそろえた版）"),
    ("ft_2_experiments.png", "FT/ft_2_experiments.png",
     "仕組みごとの実験の比べ（R18／P3、E1〜E3、R）：入口の頂と崩れる頂、育った比、崩れ方、座席の仰角の数。ft_deliver.py で 10/8 に描いた"),
    ("ft_3_turntable12.png", "R/turntable_12.png", "12 の角度の粘土（R、群の時刻 85.0 s、z −120 m の対称の面で鏡に映した海）"),
    ("ft_4_seat_angle_timeline.png", "review_angle_timeline.png", "座席の乗る目から見た頂の仰角の歩み（P3・V1・R を乗る目の終わりでそろえた。10/8 レビュー）"),
    ("ft_5_cause_crossing.png", "D1/sheet_m3_crossing.png", "原因：FLIP37 の ±30° の二つの列は計算の中で集まっていない（模様は t=0 に置かれ、砕け始めまでに弱まる。D1）"),
]


def main():
    os.makedirs(EV, exist_ok=True)
    os.makedirs(B + "FT", exist_ok=True)
    S = seat_stats()
    E = None
    R = rows(E, S)
    draw_sheet(R, B + "FT/ft_2_experiments.png")
    copies = []
    for name, src, note in COPIES:
        sp = B + src
        dp = EV + name
        shutil.copy2(sp, dp)
        c = dict(name=name, src="Unity/Build/FLIP39/" + src, bytes=os.path.getsize(dp), sha256=sha(dp), note_ja=note)
        if name.endswith(".mp4"):
            c.update(probe(dp)); c["le_30MB"] = c["bytes"] <= 30 * 1024 * 1024
        else:
            w, h = Image.open(dp).size; c.update(w=w, h=h)
        copies.append(c)
    json.dump(copies, open(EV + "copies.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    json.dump(dict(seat=S, rows=R), open(B + "FT/ft_numbers.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    import ft_meta
    ft_meta.write_meta(S, R)


if __name__ == "__main__":
    main()
