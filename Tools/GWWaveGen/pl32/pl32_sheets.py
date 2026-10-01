# -*- coding: utf-8 -*-
"""仕上げ32 の前後の図（1920×1080）と前後を並べた動画（pl31_sheets.py を写し、見出し・拡大の所・名前を替えた）。

前＝コミットした仕上げ31（4be87f6）の状態（PL32Render に -pl32Claws を渡さない：爪は設計33 の並び、主役波は仕上げ31 の hero_pkg）、
後＝仕上げ32（-pl32Claws Build/Polish/32/claws、主役波は仕上げ32 の hero_pkg）。
どれも Unity 6000.4.3f1 の PC オフスクリーン描画（HMD ではない）。この道具は既にある画像を並べるだけ（新しい描画はしない）。

  fig_pl32_ba_view_<視点>.png         7 視点 × t 6・9・10.5・12 s（上：前、次：後）と、t 10.5 s・t* の前後の拡大
  fig_pl32_ba_turntable_t<時刻>.png   回り台 12 方位（爪・飛沫あり）の前後
  pl32_ba_<視点>_30fps.mp4           前｜後 を左右に並べた動画（t 0〜14 s、30 fps）
使い方：py -3.10 -B Tools/GWWaveGen/pl32/pl32_sheets.py --before Unity/Build/Polish/32/r_before --after Unity/Build/Polish/32/r_after --out Docs/Evidence/Polish/32
記録の部（2026-10-02）：--final を足した。修正の回 1 と同じ描画・同じ拡大の所で、見出しを「仕上げ32」（後＝採用の状態）にする（--fix01 の見出し「仕上げ32修正01」は、
計画 §4.2 で後の別のコミット「仕上げ32修正01：」の名前と紛れるため）。
"""
import argparse
import os
import subprocess
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pl30"))
from pl30_sheets import font, label, head, tile, fit  # noqa: E402

FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
VIEWS = [("painting", "原画視点"), ("seat", "座席"), ("seat_toward_wave", "座席から波の方向"), ("side_left", "左の側面"),
         ("side_right", "右の側面"), ("back65", "後ろ 65°"), ("top", "真上")]
TS = [("t060", "t 6 s"), ("t090", "t 9 s"), ("t105", "t 10.5 s"), ("t120", "t 12 s（t*）")]
# 拡大の所（t 10.5 s と t* の飛沫と白の所）
ZOOM = {"painting": (160, 100, 1120, 640), "seat": (500, 0, 1700, 675), "seat_toward_wave": (360, 0, 1560, 675),
        "side_left": (560, 200, 1360, 650), "side_right": (500, 200, 1420, 717), "back65": (480, 160, 1440, 700), "top": (560, 200, 1360, 650)}
HEAD_B = ("前＝コミットした仕上げ31（4be87f6）の状態（仕上げ31 の最終の描画 r_fx01 と画素まで同じ）：爪は設計33 の 148 本で、段階9 の K*′ R4・F_final のシートに"
          "結び付けたまま（今の P28R2rec の面に対して原画の射線の上で −15〜+3 cm、19 本は大半が面の裏）、b区域の爪は 15 本、T_white は爪の根元の誘導つき")
HEAD_A = ("後＝仕上げ32：爪の一覧を 209 本（b区域 77。原画から数え直して 63 本を加えた）にし、領域を墨版の線へ・中心線を領域の真ん中へ合わせ、"
          "K*′ P28R2rec・G_p28rec のシートへ結び付け直した。成長は根元の 4 つの角がそろって白くなってから。帯は原画のカメラの向きへ 8.5 cm＋厚みの 1/4 ずらす"
          "（縁の線が面に隠れないように。原画視点の形は変えない）。爪の色は摺りの版（紙の地と水色の版。藍中の段をやめた）。T_white は爪の根元の誘導を外し、飛沫の放出点の誘導（18 頂点）")


HEAD_A_FIX01 = ("後＝仕上げ32 修正の回 1：根元が立体の材質の白の範囲に乗らない爪 29 本は帯にせず（pl32f_white_root_only。一覧には残す）、"
                "白の範囲の外の面・別の折れの面・面の縁の外には関節を貼らずに宙に置き（pl32f_hang_over_indigo・pl32f_fold_guard・pl32f_hit_exact）、"
                "帯の幅を一覧の領域へ合わせ（pl32f_width_fit）、縁の線を根元で開き（pl32f_root_open）、縁から見た帯の箱の線を出さず（pl32f_edge_box）、"
                "根元の円を水色の版の雲にした（pl32f_tuft_base）。爪は 184 本（b区域 57）。拡大の段の座席と座席から波の方向は、審査で指摘された左端・左上")
ZOOM_FIX01 = {"seat": (0, 405, 1200, 1080), "seat_toward_wave": (0, 0, 1200, 675)}
HEAD_A_FINAL = ("後＝仕上げ32（採用の状態：作る部の一覧・結び付けに、自己評審の後の修正の回 1 の直しを加えたもの）：" + HEAD_A_FIX01.split("：", 1)[1])


def tag(a):
    """見出しの群の名前（--final は「仕上げ32」、--fix01 は「仕上げ32修正01」）。"""
    return "" if (getattr(a, "final", False) or not a.fix01) else "修正01"


def wrap(d, text, width, f):
    """text を幅 width（画素）で折り返した行の並び（日本語は文字ごとに折る）。"""
    lines, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=f) > width and cur:
            lines.append(cur); cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def view_sheets(a, out):
    # 記録の部（2026-10-02）：見出しの 2 行目は 1 行に収まらず右端で切れていた（「飛沫 2,500 粒：原画の点 210」の後）。
    # 見出しは短くし、前・後の説明は図の下の欄に折り返して書く。拡大の段は切り抜きの縦横の比の高さで上に詰めて置く（見出しの札と画像の間の空きをなくす）。
    files = []
    for v, name in VIEWS:
        im = Image.new("RGB", (1920, 1080), (238, 238, 238))
        d = ImageDraw.Draw(im)
        head(d, "仕上げ32%s 視点ごとの前後｜%s｜上の段：前　次の段：後（同じ視点・同じ時刻・作品のまま：爪・飛沫・線あり）" % (tag(a), name),
             "前＝コミットした仕上げ31（4be87f6）、後＝仕上げ32%s。下の段は t 10.5 s と t* の拡大。前・後の中身は図の下の欄。Unity の PC オフスクリーン描画（HMD ではない）。"
             % ("（採用：作る部＋修正の回 1）" if getattr(a, "final", False) else ("（修正の回 1）" if a.fix01 else "")))
        tw, th = 474, 267
        for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
            for k, (ts, tn) in enumerate(TS):
                x, y = 4 + k * (tw + 4), 66 + si * (th + 3)
                t = tile(os.path.join(root, "views", "%s_%s_asis.png" % (v, ts)), (tw, th))
                if t is not None:
                    im.paste(t, (x, y))
                label(d, x + 4, y + 4, "%s｜%s" % (lab, tn))
        crop = ZOOM_FIX01.get(v, ZOOM.get(v)) if a.fix01 else ZOOM.get(v)
        bw, bh = 474, 0
        # 下の段：t 10.5 s と t* の拡大（前・後）
        cw = 474
        ch = int(round(cw * (crop[3] - crop[1]) / float(crop[2] - crop[0])))
        ch = min(ch, 470)
        for k, (ts, tn) in enumerate([("t105", "t 10.5 s"), ("t120", "t 12 s（t*）")]):
            for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
                x, y = 4 + (2 * k + si) * (cw + 4), 610
                p = os.path.join(root, "views", "%s_%s_asis.png" % (v, ts))
                if os.path.exists(p):
                    t = fit(Image.open(p).convert("RGB").crop(crop), (cw, ch))
                    im.paste(t, (x, y))
                label(d, x + 4, y + 4, "%s｜%s 拡大" % (lab, tn))
        f = font(15)
        y = 610 + ch + 10
        for para in (HEAD_B + "。", (HEAD_A_FINAL if getattr(a, "final", False) else (HEAD_A_FIX01 if a.fix01 else HEAD_A)) + "。"):
            for ln in wrap(d, para, 1890, f):
                d.text((14, y), ln, fill=(40, 48, 64), font=f)
                y += 22
        p = os.path.join(out, "fig_pl32_ba_view_%s.png" % v)
        im.save(p); files.append(p)
    return files


def turntable(a, out):
    files = []
    for ts, tn in TS:
        im = Image.new("RGB", (1920, 1080), (238, 238, 238))
        d = ImageDraw.Draw(im)
        head(d, "仕上げ32%s 回り台｜%s｜方位ごとに上：前　下：後（爪・飛沫・線あり、周りの海を含む）" % (tag(a), tn),
             "回り台：中心 O(t)+(0,9,0)、半径 72 m、仰角 16°、縦の画角 34°、原画視点の向きから 30° ごと（仕上げ29・30 と同じ置き方）。Unity の PC 描画。")
        tw, th = 316, 178
        for k in range(12):
            az = k * 30
            col, blk = k % 6, k // 6
            for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
                x, y = 4 + col * (tw + 4), 66 + blk * (2 * th + 30) + si * (th + 2)
                t = tile(os.path.join(root, "tt", "%s_az%03d_claws.png" % (ts, az)), (tw, th))
                if t is not None:
                    im.paste(t, (x, y))
                label(d, x + 3, y + 3, "%s｜方位 %d°" % (lab, az), 12)
        p = os.path.join(out, "fig_pl32_ba_turntable_%s.png" % ts)
        im.save(p); files.append(p)
    return files


def videos(a, out):
    files = []
    for v in ("painting", "seat", "seat_toward_wave", "side_left", "tt"):
        b = os.path.join(a.before, "video", "pl32_%s_30fps.mp4" % v)
        f = os.path.join(a.after, "video", "pl32_%s_30fps.mp4" % v)
        if not (os.path.exists(b) and os.path.exists(f)):
            continue
        p = os.path.join(out, "pl32_ba_%s_30fps.mp4" % v)
        vf = ("[0:v]drawtext=fontfile='C\\:/Windows/Fonts/NotoSansJP-Bold.ttf':text='前 仕上げ31':x=8:y=8:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6[l];"
              "[1:v]drawtext=fontfile='C\\:/Windows/Fonts/NotoSansJP-Bold.ttf':text='後 仕上げ32%s':x=8:y=8:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6[r];[l][r]hstack=inputs=2") % tag(a)
        cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", b, "-i", f, "-filter_complex", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "26",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", p]
        subprocess.run(cmd, check=True)
        files.append(p)
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--skip-video", action="store_true")
    ap.add_argument("--fix01", action="store_true", help="仕上げ32 修正の回 1 の見出しと拡大の所")
    ap.add_argument("--final", action="store_true", help="記録の部：修正の回 1 の拡大の所で、見出しを「仕上げ32」（後＝採用の状態）にする")
    a = ap.parse_args()
    if a.final:
        a.fix01 = True
    os.makedirs(a.out, exist_ok=True)
    fs = view_sheets(a, a.out) + turntable(a, a.out)
    if not a.skip_video:
        fs += videos(a, a.out)
    for f in fs:
        print(f, os.path.getsize(f))


if __name__ == "__main__":
    main()
