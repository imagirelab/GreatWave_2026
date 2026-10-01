# -*- coding: utf-8 -*-
"""仕上げ28（焼き直しと Unity の描画）：段階9 の状態と仕上げ28 の状態を、同じ視点・同じ時刻で並べた前後の図（1920×1080）と前後の動画を作る。

入力（PL28Render の出力。Git 対象外）：
  <unity>/scene_stage9/  … -pl28State stage9（段階9 の状態＝設計28修正01 の F_final・K*' R4・設計29修正01 の焼き込み。設計40 の t* の組と画素まで同じ）
  <unity>/scene_p28/     … -pl28State p28（仕上げ28 の G_p28b・K*' P28R2・焼き直し）
どちらも爪なし（白あり・爪なし・飛沫なし・紙なし・線あり）の静止画と動画。t* の「そのまま」（爪・飛沫あり）は記録の行。
出力：
  <out>/fig_pl28u_ba_<視点>.png   … 上：2 行（段階9／仕上げ28）× 4 時刻（t 8・10・11・12 s）、下：t* の 2 倍の切り出しを左右に（段階9｜仕上げ28）
  <out>/fig_pl28u_ba_turntable.png … 回り台（t*、30° ごと 12 枚）：段階9 と仕上げ28 を交互の行に
  <out>/fig_pl28u_tstar_views.png  … t* の 5 視点：段階9（爪なし）／仕上げ28（爪なし）／仕上げ28（爪・飛沫をそのまま）
  <out>/pl28u_ba_<視点>.mp4        … 左：段階9、右：仕上げ28（各 960×540、30 fps）。5 MB 以下になるよう crf を上げて作り直す
使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/pl28/pl28u_sheets.py [--unity Unity/Build/Polish/28/unity] [--out Docs/Evidence/Polish/28] [--skip-video]
    回復の版（仕上げ28 の回復、<unity>/scene_rec/）と段階9 を並べる：… --after rec --prefix pl28rec（出力 fig_pl28rec_ba_*.png・pl28rec_ba_*.mp4・<unity>/pl28rec_sheets.json）
"""
import argparse
import hashlib
import json
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FF = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
FONT = "C:/Windows/Fonts/YuGothM.ttc"
FONTB = "C:/Windows/Fonts/YuGothB.ttc"
BG = (255, 255, 255)
INK = (20, 24, 32)

VIEW_JA = {"painting": "原画視点", "seat": "座席 v1", "seat_toward_wave": "座席から波の方向", "side_left": "左の側面（波の枠とともに動く）",
           "back65": "後ろ 65°（粘土と同じ置き方、波の枠とともに動く）", "back_cp1": "背面（CP1・設計40 と同じ位置）"}
# t* の切り出し（1920×1080 の中の枠 x0,y0,x1,y1。2 倍にすると 960×? に収まる大きさ）
# 座席 v1 の枠は評審の指摘（元の枠 x 400〜1520・y 0〜486 は空だけ）で、波の頂のある下の部分へ直した（仕上げ28 の回復）
CROP = {"painting": (100, 70, 1160, 530), "seat": (100, 420, 1260, 922), "seat_toward_wave": (560, 0, 1680, 486),
        "side_left": (520, 300, 1500, 725), "back65": (560, 200, 1640, 669), "back_cp1": (560, 200, 1640, 669)}
TIMES = [8.0, 10.0, 11.0, 12.0]
# 後の状態（--after で替える）：既定は仕上げ28 の P28R2（scene_p28）。回復の版は scene_rec
AFTER = {"scene": "scene_p28", "short": "仕上げ28", "long": "仕上げ28（G_p28b・K*' P28R2・焼き直し）", "kstar": "K*' P28R2"}


def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def img(p, size=None):
    im = Image.open(p).convert("RGB")
    return im.resize(size, Image.LANCZOS) if size else im


def label(d, xy, text, sz=22, bold=False, fill=INK, anchor="la"):
    d.text(xy, text, font=font(sz, bold), fill=fill, anchor=anchor)


def sheet_view(U, view, out):
    W, H = 1920, 1080
    S = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(S)
    label(d, (16, 10), "%s：前後の図　%s" % (AFTER["short"], VIEW_JA[view]), 26, True)
    cw, ch = 480, 270
    top = 52
    label(d, (16, top), "上段：段階9（F_final・K*' R4）　下段：%s。列は体験の時刻 t（t* = 12 s。τ(t) は両方で同じ）。" % AFTER["long"] +
          "爪なし（白あり・爪・飛沫・紙なし・線あり）。Unity 6000.4.3f1 の PC 描画、HMD ではない", 17)
    y0 = top + 30
    for j, t in enumerate(TIMES):
        tag = "%03d" % int(round(t * 10))
        for i, st in enumerate(("scene_stage9", AFTER["scene"])):
            p = os.path.join(U, st, "views", "%s_t%s_clawfree.png" % (view, tag))
            S.paste(img(p, (cw, ch)), (j * cw, y0 + i * ch))
        d.rectangle([j * cw + 4, y0 + 4, j * cw + 170, y0 + 32], fill=(20, 24, 32))
        label(d, (j * cw + 10, y0 + 6), "t %.1f s%s" % (t, "（t*）" if t == 12.0 else ""), 20, True, (255, 255, 255))
    for i, name in enumerate(("段階9", AFTER["short"])):
        wl = 22 * len(name) + 16
        d.rectangle([W - wl - 6, y0 + i * ch + 4, W - 6, y0 + i * ch + 34], fill=(255, 255, 255))
        label(d, (W - wl + 2, y0 + i * ch + 6), name, 20, True)
    # 下：t* の 2 倍の切り出し
    yb = y0 + 2 * ch + 8
    x0, y0c, x1, y1c = CROP[view]
    bw = 956
    bh = H - yb - 36
    for i, st in enumerate(("scene_stage9", AFTER["scene"])):
        im = img(os.path.join(U, st, "views", "%s_t120_clawfree.png" % view)).crop((x0, y0c, x1, y1c))
        sc = min(bw / im.width, bh / im.height)
        im = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)
        S.paste(im, (i * 964 + (bw - im.width) // 2, yb + 30))
    label(d, (16, yb + 2), "t* の切り出し（元の画素の枠 x %d〜%d・y %d〜%d）　左：段階9　右：%s" % (x0, x1, y0c, y1c, AFTER["short"]), 18)
    S.save(out)
    return out


def sheet_turntable(U, out):
    W, H = 1920, 1080
    S = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(S)
    label(d, (16, 10), AFTER["short"] + "：前後の図　回り台（t*、粘土の回り台と同じ置き方：中心 O(0)+(0,9,0)、半径 72 m、仰角 16°、縦の画角 34°、波だけ）", 26, True)
    label(d, (16, 50), "方位は原画視点の向きを 0° として 30° ごと。行の組：上＝段階9（K*' R4）、下＝%s（%s）。ドームは後ろの側（90°〜240° 付近）で見る" % (AFTER["short"], AFTER["kstar"]), 18)
    cw, ch = 320, 180
    y = 84
    for half in (0, 1):
        for i, st in enumerate(("scene_stage9", AFTER["scene"])):
            for j in range(6):
                az = (half * 6 + j) * 30
                S.paste(img(os.path.join(U, st, "tt", "tt_az%03d.png" % az), (cw, ch)), (j * cw, y))
                if i == 0:
                    d.rectangle([j * cw + 4, y + 4, j * cw + 70, y + 30], fill=(20, 24, 32))
                    label(d, (j * cw + 10, y + 5), "%d°" % az, 20, True, (255, 255, 255))
            nm = "段階9" if i == 0 else AFTER["short"]
            wl = 20 * len(nm) + 16
            d.rectangle([W - wl - 6, y + 4, W - 6, y + 32], fill=(255, 255, 255))
            label(d, (W - wl + 2, y + 6), nm, 18, True)
            y += ch
        y += 20
    label(d, (16, H - 40), "Unity 6000.4.3f1 の PC 描画（爪なし）。HMD ではない。前後とも同じカメラ（O(0) は両方で (−7.228, 0, −2.713)）", 18)
    S.save(out)
    return out


def sheet_tstar(U, out):
    W, H = 1920, 1080
    S = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(S)
    views = ["painting", "seat", "seat_toward_wave", "side_left", "back65"]
    label(d, (16, 10), "%s：t*（t = 12 s）の 5 視点　段階9／%s（爪なし）／%s（爪・飛沫をそのまま）" % (AFTER["short"], AFTER["short"], AFTER["short"]), 26, True)
    label(d, (16, 50), "3 段目の爪（設計33 の爪の軌跡）と飛沫（設計31）は K*' R4 の形に合わせたままで、仕上げ32・33・31 の最初に合わせ直す（記録。関門は爪なしの読み）", 18)
    cw, ch = 384, 216
    y = 110
    rows = [("scene_stage9", "clawfree", "段階9"), (AFTER["scene"], "clawfree", AFTER["short"]), (AFTER["scene"], "asis", AFTER["short"] + "（爪・飛沫そのまま）")]
    for j, v in enumerate(views):
        label(d, (j * cw + 6, y - 28), VIEW_JA[v].split("（")[0], 18, True)
    for i, (st, cond, name) in enumerate(rows):
        for j, v in enumerate(views):
            S.paste(img(os.path.join(U, st, "views", "%s_t120_%s.png" % (v, cond)), (cw, ch)), (j * cw, y))
        d.rectangle([4, y + 4, 12 + 16 * len(name) + 10, y + 32], fill=(255, 255, 255))
        label(d, (10, y + 6), name, 18, True)
        y += ch + 16
    label(d, (16, H - 40), "Unity 6000.4.3f1 の PC 描画。HMD ではない。座席から波の方向・側面・後ろ 65° は背景の船・富士・仮置きを隠した「波だけ」", 18)
    S.save(out)
    return out


def video_pair(U, name, out, crf):
    a = os.path.join(U, "scene_stage9", "video", "pl28_%s_30fps.mp4" % name)
    b = os.path.join(U, AFTER["scene"], "video", "pl28_%s_30fps.mp4" % name)
    ttl = {"painting": "原画視点", "seat_toward_wave": "座席から波の方向", "side_left": "左の側面（波の枠とともに動く）",
           "back65": "後ろ 65°（波の枠とともに動く）", "tt": "回り台（t*、1 コマ 3°、主役波だけ）"}[name]
    tmp = os.path.join(U, "_label")
    os.makedirs(tmp, exist_ok=True)
    texts = {"a": "段階9（F_final・K*' R4）", "b": AFTER["long"],
             "c": ttl + "・爪なし・t 0〜14 s（t* = 12 s）・Unity の PC 描画（HMD ではない）" if name != "tt" else ttl + "・爪なし・Unity の PC 描画（HMD ではない）"}
    tf = {}
    for k, v in texts.items():
        tf[k] = os.path.join(tmp, "%s_%s.txt" % (name, k))
        with open(tf[k], "w", encoding="utf-8", newline="") as f:
            f.write(v)

    def esc(p):
        return p.replace("\\", "/").replace(":", r"\:")
    fnt = r"C\:/Windows/Fonts/YuGothM.ttc"
    dt = "drawtext=fontfile='%s':textfile='%s':x=%s:y=%s:fontsize=%d:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=6"
    vf = ("[0:v]" + dt % (fnt, esc(tf["a"]), "12", "10", 24) + "[a];"
          "[1:v]" + dt % (fnt, esc(tf["b"]), "12", "10", 24) + "[b];"
          "[a][b]hstack=inputs=2," + dt % (fnt, esc(tf["c"]), "12", "h-40", 22) + "[v]")
    for c in (crf, crf + 4, crf + 8):
        subprocess.run([FF, "-y", "-loglevel", "error", "-i", a, "-i", b, "-filter_complex", vf, "-map", "[v]", "-c:v", "libx264", "-preset", "slow",
                        "-crf", str(c), "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], check=True)
        if os.path.getsize(out) <= 5 * 1024 * 1024:
            return out, c
    return out, c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unity", default="Unity/Build/Polish/28/unity")
    ap.add_argument("--out", default="Docs/Evidence/Polish/28")
    ap.add_argument("--skip-video", action="store_true")
    ap.add_argument("--after", default="p28", choices=["p28", "rec"], help="後の状態：p28＝P28R2（scene_p28）、rec＝回復の版 P28R2rec（scene_rec）")
    ap.add_argument("--prefix", default="pl28u", help="出力のファイル名の頭（fig_<prefix>_ba_*.png・<prefix>_ba_*.mp4）")
    a = ap.parse_args()
    if a.after == "rec":
        AFTER.update({"scene": "scene_rec", "short": "仕上げ28 の回復", "long": "仕上げ28 の回復（G_p28rec・K*' P28R2rec・焼き直し）", "kstar": "K*' P28R2rec"})
    U = os.path.join(REPO, a.unity)
    out = os.path.join(REPO, a.out)
    os.makedirs(out, exist_ok=True)
    made = {}
    for v in ("painting", "seat", "seat_toward_wave", "side_left", "back65"):
        p = sheet_view(U, v, os.path.join(out, "fig_%s_ba_%s.png" % (a.prefix, v)))
        made[os.path.basename(p)] = sha256(p)
    p = sheet_turntable(U, os.path.join(out, "fig_%s_ba_turntable.png" % a.prefix)); made[os.path.basename(p)] = sha256(p)
    p = sheet_tstar(U, os.path.join(out, "fig_%s_tstar_views.png" % a.prefix)); made[os.path.basename(p)] = sha256(p)
    vids = {}
    if not a.skip_video:
        for n in ("painting", "seat_toward_wave", "side_left", "back65", "tt"):
            p, c = video_pair(U, n, os.path.join(out, "%s_ba_%s.mp4" % (a.prefix, "turntable" if n == "tt" else n)), 23)
            vids[os.path.basename(p)] = {"sha256": sha256(p), "bytes": os.path.getsize(p), "crf": c}
    rec = {"schema": "GreatWave.Polish28.sheets/1", "figures": made, "videos": vids,
           "after": dict(AFTER), "inputs": {st: sha256(os.path.join(U, st, "pl28_render_report.json")) for st in ("scene_stage9", AFTER["scene"])}}
    with open(os.path.join(U, "%s_sheets.json" % a.prefix), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("PL28U_SHEETS_DONE", json.dumps(rec, ensure_ascii=False)[:600])


if __name__ == "__main__":
    main()
