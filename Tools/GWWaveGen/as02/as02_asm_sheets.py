# -*- coding: utf-8 -*-
"""美術の見本02（Q30-2）組み立て：利用者へ渡す並べ図（1920×1080、Git 対象外の Build/Polish/sample02/delivery/）。

  s2_painting.png         原画視点：原画｜前（美術の見本01 A）｜今（背 AS02B ＋ 利用者の 100 本の爪 案 A）。下の段は頂と唇の拡大（原画に利用者のマスクの縁を緑）
  s3a_back_material.png   背：後ろ 65°・回り台 180〜270°（見本 A の材質、Unity）。前｜今
  s4a_views.png           座席・座席から波・左右の側面・真上・座席から見た頂の拡大。前｜今
  s4b_turntable.png       回り台 12 方位（仰角 16°）。前｜今
  turntable_before_now.mp4  同じ 12 方位を 0.6 s ずつ（前｜今）
どれも t* = 12 s（τ = 0）の静止、Unity 6000.4.3f1 の PC オフスクリーン描画（AS01SampleRender、HMD 実機ではない）、飛沫なし。
前 = Build/Polish/sample01/assemble/A2（美術の見本01 の A、回 2）、今 = Build/Polish/sample02/assemble/render/AS02B_A。
原画の画像はリポジトリの Docs/References/Met_JP1847_DP130155.jpg。利用者のマスクの縁を描いた図は Build にだけ置く（D14・D23）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as02/as02_asm_sheets.py [--now <描画>] [--out <dir>]
"""
import argparse
import os
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as02")
import as02_claws100 as A  # noqa: E402
from as02_sheets import painting_disp  # noqa: E402

BEFORE = REPO + "/Unity/Build/Polish/sample01/assemble/A2"
NOW = REPO + "/Unity/Build/Polish/sample02/assemble/render/AS02B_A"
OUT = REPO + "/Unity/Build/Polish/sample02/delivery"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
BG = (250, 249, 245)
LB = {"before": "前：美術の見本01 A", "now": "今：見本02（背 AS02B ＋ 100 本の爪 案 A）"}
NOTE = "t* = 12 s の静止。Unity の PC 描画（HMD 実機ではない）。飛沫なし。面の色は見本 A を中立の地に使った（模様は今回の対象外、要求書 T2）。"


def font(sz, bold=False):
    return ImageFont.truetype("C:/Windows/Fonts/BIZ-UDGothic%s.ttc" % ("B" if bold else "R"), sz)


def to_pil(bgr):
    return Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))


def fit(img, w, h):
    s = min(w / img.shape[1], h / img.shape[0])
    r = cv2.resize(img, (max(1, int(round(img.shape[1] * s))), max(1, int(round(img.shape[0] * s)))), interpolation=cv2.INTER_AREA)
    out = np.full((h, w, 3), BG[::-1], np.uint8)
    y, x = (h - r.shape[0]) // 2, (w - r.shape[1]) // 2
    out[y:y + r.shape[0], x:x + r.shape[1]] = r
    return out


def load(p):
    im = cv2.imread(p)
    if im is None:
        im = np.full((1080, 1920, 3), 200, np.uint8)
        cv2.putText(im, "missing " + os.path.basename(p), (40, 80), 0, 1.5, (0, 0, 255), 3)
    return im


def claw_px(root, v):
    """爪ありと爪なしの描画の差（どれかの色の差 > 8）の画素の数＝見える爪の画素。"""
    a, b = load(root + "/views/%s_t120_claws.png" % v), load(root + "/views/%s_t120_clawfree.png" % v)
    return int((np.abs(a.astype(np.int16) - b.astype(np.int16)).max(-1) > 8).sum())


def report():
    import json
    r = json.load(open(REPO + "/Unity/Build/Polish/sample02/assemble/claws/mesh/as02_claws_report.json", encoding="utf-8"))
    m = json.load(open(REPO + "/Unity/Build/Polish/sample02/back/final/measure.json", encoding="utf-8"))["summary"]
    return r["summary"], m


def view(root, v, cond="claws"):
    if v.startswith("tt"):
        return load(root + "/tt/t120_az%03d_claws.png" % int(v[2:]))
    return load(root + "/views/%s_t120_%s.png" % (v, cond))


class Sheet:
    def __init__(self, title, note=NOTE):
        self.im = Image.new("RGB", (1920, 1080), BG)
        self.d = ImageDraw.Draw(self.im)
        self.d.text((16, 10), title, fill=(20, 20, 20), font=font(26, True))
        if note:
            self.d.text((16, 46), note, fill=(82, 81, 78), font=font(16))

    def tile(self, bgr, x, y, w, h, label=None, lsz=17, bold=False):
        if label:
            self.d.text((x + 2, y), label, fill=(30, 30, 30), font=font(lsz, bold))
            y += lsz + 6
            h -= lsz + 6
        self.im.paste(to_pil(fit(bgr, w, h)), (x, y))

    def text(self, x, y, s, sz=16, col=(40, 40, 40), bold=False):
        self.d.text((x, y), s, fill=col, font=font(sz, bold))

    def save(self, p):
        self.im.save(p)
        print("wrote", p)


def user_mask_disp():
    users, _, _ = A.load_user()
    mk = np.zeros((1080, 1920), np.uint8)
    for u in users:
        m = A.imread_u(u["dir"] + "/fill_mask.png", cv2.IMREAD_GRAYSCALE)
        mk = np.maximum(mk, cv2.warpAffine(m, A.disp_affine(u["A"]), (1920, 1080), flags=cv2.INTER_LINEAR))
    cnt, _ = cv2.findContours((mk > 127).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return cnt


def s2_painting(now, out):
    disp = painting_disp()
    cnt = user_mask_disp()
    b = view(BEFORE, "painting"); n = view(now, "painting")
    sh = Sheet("原画視点：原画｜前｜今（下の段は頂と唇の拡大）")
    tw, th = 624, 380
    xs = [16, 648, 1280]
    cols = np.nonzero(disp.max(axis=(0, 2)) > 0)[0]
    dcrop = np.ascontiguousarray(disp[:, cols.min():cols.max() + 1])
    for x, (lab, im) in zip(xs, [("原画（Met DP130155）", dcrop), (LB["before"], b), (LB["now"], n)]):
        sh.tile(im, x, 76, tw, th, lab, bold=True)
    x0, y0, x1, y1 = 470, 30, 1190, 540
    pz = disp.copy(); cv2.drawContours(pz, cnt, -1, (0, 170, 0), 1)
    zl = [("原画＋利用者が切り出した爪のマスクの縁（緑）", pz), (LB["before"] + "（拡大）", b), ("今（拡大）", n)]
    for x, (lab, im) in zip(xs, zl):
        sh.tile(np.ascontiguousarray(im[y0:y1, x0:x1]), x, 470, tw, 470, lab)
    rs, _ = report()
    ip = rs["iou_painting"]
    sh.text(16, 950, "今の爪は利用者のマスクの縁にほぼ重なる（原画視点の IoU p50 %.2f、%d 本中 %d 本が 0.85 以上）。背の作り直しは原画カメラから見えない所だけで、原画視点の形は変わらない。"
            % (ip["p50"], ip["n"], ip["n"] - len(rs["iou_painting_below_085"])), 16)
    sh.text(16, 975, "前（見本01 A）の大きな白い立体の指は無くし、利用者の 100 本（重複 17 本を除く 83 本）に置き換えた。原画にある爪の数（約 300）より少なく、白い泡の面は無い。", 16)
    sh.save(os.path.join(out, "s2_painting.png"))


def pairs_sheet(title, items, out_name, now, note=NOTE, extra=None):
    """items：(名前, 視点) を 2 つの列（左のかたまり・右のかたまり）× 3 行に。各行は 前｜今。"""
    sh = Sheet(title, note)
    tw, th = 468, 272
    bx = [16, 976]
    for k, (name, v) in enumerate(items):
        col, row = divmod(k, 3)
        x = bx[col]; y = 76 + row * (th + 34)
        sh.text(x, y, name, 18, bold=True)
        if isinstance(v, tuple):
            bimg, nimg = v
        else:
            bimg, nimg = view(BEFORE, v), view(now, v)
        sh.tile(bimg, x, y + 24, tw, th, "前（見本01 A）", 15)
        sh.tile(nimg, x + tw + 8, y + 24, tw, th, "今（見本02）", 15)
    if extra:
        for i, s in enumerate(extra):
            sh.text(16, 1060 - 22 * (len(extra) - i), s, 15)
    sh.save(os.path.join(OUT if out_name is None else out_name))


def claw_box(roots, v, pad=60):
    """爪ありと爪なしの差の画素の外接の箱（前と今の和）を 16:9 に広げる。"""
    m = np.zeros((1080, 1920), bool)
    for r in roots:
        a, b = load(r + "/views/%s_t120_claws.png" % v), load(r + "/views/%s_t120_clawfree.png" % v)
        m |= np.abs(a.astype(np.int16) - b.astype(np.int16)).max(-1) > 8
    ys, xs = np.nonzero(m)
    x0, x1, y0, y1 = xs.min() - pad, xs.max() + pad, ys.min() - pad, ys.max() + pad
    w, h = x1 - x0, y1 - y0
    if w / h < 16 / 9:
        e = int((h * 16 / 9 - w) / 2); x0 -= e; x1 += e
    else:
        e = int((w * 9 / 16 - h) / 2); y0 -= e; y1 += e
    x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(1920, x1), min(1080, y1)
    return x0, y0, x1, y1


def crop(img, box):
    x0, y0, x1, y1 = box
    return np.ascontiguousarray(img[y0:y1, x0:x1])


def s3a_back(now, out):
    items = [("後ろ 65°", "back65"), ("回り台 180°", "tt180"), ("回り台 210°", "tt210"),
             ("回り台 240°", "tt240"), ("回り台 270°", "tt270"), ("後ろ 65°（爪なし）", (view(BEFORE, "back65", "clawfree"), view(now, "back65", "clawfree")))]
    _, m = report()
    p, c = m["P28R2rec"], m["AS02B"]
    extra = ["背の形（要求書 S4）：背の上の帯は見本 A の材質で白に塗られるので、背の形は白の輪郭で読める。粘土の図（s3b・s3c）と数の図（s3d）も見る。",
             "数（c が −14 以上）：背の等高線のへこみ %.2f → %.2f m、弦からの出っ張りのへこみ %.2f → %.2f m、入り江 %.2f → %.2f m。H(c) の最高 c %.1f は変えていない。"
             % (p["back_dip_max_m"], c["back_dip_max_m"], p["back_bulge_dip_max_m"], c["back_bulge_dip_max_m"], p["back_bay_max_m"], c["back_bay_max_m"], c["H_max_c"])]
    pairs_sheet("背：後ろ 65°・回り台 180〜270°（見本 A の材質）前｜今", items, os.path.join(out, "s3a_back_material.png"), now, extra=extra)


def s4a_views(now, out):
    sb, sn = view(BEFORE, "seat"), view(now, "seat")
    bx = claw_box([BEFORE, now], "seat")
    items = [("座席", "seat"), ("座席から波の方向", "seat_toward_wave"), ("左の側面", "side_left"),
             ("右の側面", "side_right"), ("真上", "top"), ("座席から見た頂と唇（爪の所の拡大）", (crop(sb, bx), crop(sn, bx)))]
    px = {v: (claw_px(BEFORE, v), claw_px(now, v)) for v in ("seat", "side_left", "back65", "top")}
    extra = ["爪：今の爪は利用者のマスクに合わせて原画の射線の上に置いたので、原画視点の外では細く短く見え、座席の頂の数本のほかはほとんど読めない。",
             "見える爪の画素（爪ありと爪なしの描画の差、前 → 今）：" + "、".join("%s %s → %s" % (k, format(a, ","), format(b, ",")) for k, (a, b) in px.items())]
    pairs_sheet("座席・側面・真上：前｜今", items, os.path.join(out, "s4a_views.png"), now, extra=extra)


def s4b_turntable(now, out):
    sh = Sheet("回り台 12 方位（仰角 16°、半径 72 m）：前｜今")
    tw, th = 306, 172
    for k, az in enumerate(range(0, 360, 30)):
        r, cpos = divmod(k, 3)
        x = 16 + cpos * (2 * tw + 22); y = 76 + r * (th + 56)
        sh.text(x, y, "%d°" % az, 17, bold=True)
        sh.tile(view(BEFORE, "tt%d" % az), x, y + 22, tw, th + 22, "前", 14)
        sh.tile(view(now, "tt%d" % az), x + tw + 6, y + 22, tw, th + 22, "今", 14)
    sh.text(16, 1000, "0° は原画のカメラの側。180〜270° が背。前の白い指（見本01 の爪）は無くなり、今の 83 本は頂の輪郭にわずかに見えるだけ。", 16)
    sh.save(os.path.join(out, "s4b_turntable.png"))


def turntable_mp4(now, out):
    tmp = os.path.join(out, "_tt_frames")
    os.makedirs(tmp, exist_ok=True)
    k = 0
    for az in list(range(0, 360, 30)):
        sh = Sheet("回り台 %d°（仰角 16°）　左：前（美術の見本01 A）　右：今（見本02）" % az, NOTE)
        sh.tile(view(BEFORE, "tt%d" % az), 16, 120, 936, 560, "前", 18, True)
        sh.tile(view(now, "tt%d" % az), 968, 120, 936, 560, "今", 18, True)
        sh.im.save(os.path.join(tmp, "f%03d.png" % k)); k += 1
    mp4 = os.path.join(out, "turntable_before_now.mp4")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", "1/0.8", "-i", os.path.join(tmp, "f%03d.png"), "-vf", "fps=10,format=yuv420p",
                    "-c:v", "libx264", "-crf", "26", mp4], check=True)
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    print("wrote", mp4, os.path.getsize(mp4))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", default=NOW)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    s2_painting(a.now, a.out)
    s3a_back(a.now, a.out)
    s4a_views(a.now, a.out)
    s4b_turntable(a.now, a.out)
    turntable_mp4(a.now, a.out)


if __name__ == "__main__":
    main()
