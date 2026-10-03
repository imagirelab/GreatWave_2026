# -*- coding: utf-8 -*-
"""美術の見本02（Q30-2）修正の回 1：前後の並べ図（1920×1080、Git 対象外の Build/Polish/sample02/fix01/delivery/）。
前 ＝ 見本02 の組み立て（背 AS02B ＋ 爪の部の案 A、Build/Polish/sample02/assemble/render/AS02B_A）、
今 ＝ 修正の回 1（背 AS02C ＋ 直した爪、Build/Polish/sample02/fix01/assemble/render/AS02C_A）。同じ視点・同じ t*（12 s）。
  s2_painting.png        原画視点：原画（＋利用者のマスクの縁、緑）｜前｜今。下の段は頂と唇の拡大
  s3a_back_material.png  背：後ろ 65°・回り台 180〜270°（見本 A の材質）前｜今
  s4a_views.png          座席・座席から波・左右の側面・真上・座席から見た頂の拡大 前｜今
  s4b_turntable.png      回り台 12 方位 前｜今
  turntable_before_now.mp4
描画と並べ方の関数は組み立ての as02_asm_sheets.py をそのまま使う（ここは前と今の場所と、図の中の文だけを替える）。
利用者のマスクの縁を描いた図（s2）は Build にだけ置く（D14・D23）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as02/as02_fix01_sheets.py
"""
import json
import os
import subprocess
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as02")
import as02_asm_sheets as SH  # noqa: E402

S2 = REPO + "/Unity/Build/Polish/sample02"
BEFORE = S2 + "/assemble/render/AS02B_A"
NOW = S2 + "/fix01/assemble/render/AS02C_A"
OUT = S2 + "/fix01/delivery"
REP_NOW = S2 + "/fix01/assemble/claws/mesh/as02_claws_report.json"
REP_BEFORE = S2 + "/assemble/claws/mesh/as02_claws_report.json"
MEASURE = S2 + "/fix01/back/final/measure.json"
LB_B = "前：見本02（背 AS02B ＋ 爪 案 A）"
LB_N = "今：修正の回 1（背 AS02C ＋ 直した爪）"
NOTE = "t* = 12 s の静止。Unity の PC 描画（HMD 実機ではない）。飛沫なし。面の色は見本 A を中立の地に使った（模様は今回の対象外、要求書 T2）。"


def summ(p):
    r = json.load(open(p, encoding="utf-8"))
    pl = [c for c in r["claws"] if c.get("placed")]
    c2 = [c["user_id"] for c in pl if [x for x in c.get("standard_fails_ja", []) if not x.startswith("面から見た")]]
    c3 = [c["user_id"] for c in pl if c["iou_painting"] < 0.85 or c["iou_face"] < 0.85]
    return r["summary"], pl, c2, c3


def s2_painting(out):
    disp = SH.painting_disp()
    cnt = SH.user_mask_disp()
    b = SH.view(BEFORE, "painting"); n = SH.view(NOW, "painting")
    sh = SH.Sheet("原画視点：原画｜前（見本02）｜今（修正の回 1）。下の段は頂と唇の拡大", NOTE)
    tw, th = 624, 380
    xs = [16, 648, 1280]
    cols = np.nonzero(disp.max(axis=(0, 2)) > 0)[0]
    dcrop = np.ascontiguousarray(disp[:, cols.min():cols.max() + 1])
    for x, (lab, im) in zip(xs, [("原画（Met DP130155）", dcrop), (LB_B, b), (LB_N, n)]):
        sh.tile(im, x, 76, tw, th, lab, bold=True)
    x0, y0, x1, y1 = 470, 30, 1190, 540
    import cv2
    pz = disp.copy(); cv2.drawContours(pz, cnt, -1, (0, 170, 0), 1)
    for x, (lab, im) in zip(xs, [("原画＋利用者が切り出した爪のマスクの縁（緑）", pz), ("前（拡大）", b), ("今（拡大）", n)]):
        sh.tile(np.ascontiguousarray(im[y0:y1, x0:x1]), x, 470, tw, 470, lab)
    sb, plb, c2b, c3b = summ(REP_BEFORE)
    sn, pln, c2n, c3n = summ(REP_NOW)
    n8 = sum(1 for c in pln if c.get("iou_painting_s8", 1) < 0.85 or c.get("iou_face_600px", 1) < 0.85)
    sh.text(16, 950, "爪：利用者の模型の水準（C2）を通らない爪 %d → %d 本、原画視点・面から見た IoU が 0.85 未満（C3）%d → %d 本（83 本中。今までの細かさで測ると %d 本）。原画視点の IoU p50 %.3f → %.3f。"
            % (len(c2b), len(c2n), len(c3b), len(c3n), n8, sb["iou_painting"]["p50"], sn["iou_painting"]["p50"]), 16)
    sh.text(16, 975, "直した爪は輪郭と背骨を滑らかにした（手描きの縁の小さな波を消した）ので、マスクの細かいでこぼこには沿わない。背の修正は原画カメラから見えない所だけ。", 16)
    sh.save(os.path.join(out, "s2_painting.png"))


def pairs_sheet(title, items, path, extra=None):
    sh = SH.Sheet(title, NOTE)
    tw, th = 468, 272
    bx = [16, 976]
    for k, (name, v) in enumerate(items):
        col, row = divmod(k, 3)
        x = bx[col]; y = 76 + row * (th + 34)
        sh.text(x, y, name, 18, bold=True)
        bimg, nimg = v if isinstance(v, tuple) else (SH.view(BEFORE, v), SH.view(NOW, v))
        sh.tile(bimg, x, y + 24, tw, th, "前（見本02）", 15)
        sh.tile(nimg, x + tw + 8, y + 24, tw, th, "今（修正の回 1）", 15)
    for i, s in enumerate(extra or []):
        sh.text(16, 1060 - 22 * (len(extra) - i), s, 15)
    sh.save(path)


def s3a_back(out):
    items = [("後ろ 65°", "back65"), ("回り台 180°", "tt180"), ("回り台 210°", "tt210"),
             ("回り台 240°", "tt240"), ("回り台 270°", "tt270"),
             ("後ろ 65°（爪なし）", (SH.view(BEFORE, "back65", "clawfree"), SH.view(NOW, "back65", "clawfree")))]
    m = json.load(open(MEASURE, encoding="utf-8"))["summary"]
    b, c = m["AS02B"], m["AS02C"]
    pk = lambda x: "・".join("%+.1f" % x["bulge_peak_c_by_level"][k] for k in ("0.05", "0.15", "0.30", "0.40"))
    extra = ["背（要求書 S4）：低い高さ 0.05・0.15・0.30・0.40 H0 の背のふくらみの最大の位置 c：前 %s → 今 %s m（中ほどの区間は −6〜+6）。" % (pk(b), pk(c)),
             "背の上は見本 A の材質で白に塗られるので、形の違いは白の輪郭と粘土の図（s3b・s3c）で読む。奥 c > 0 の体積 %.0f → %.0f m³。" % (b["F04_like"]["far_volume_c_gt_0_m3"], c["F04_like"]["far_volume_c_gt_0_m3"])]
    pairs_sheet("背：後ろ 65°・回り台 180〜270°（見本 A の材質）前｜今", items, os.path.join(out, "s3a_back_material.png"), extra)


def s4a_views(out):
    sb, sn = SH.view(BEFORE, "seat"), SH.view(NOW, "seat")
    bx = SH.claw_box([BEFORE, NOW], "seat")
    items = [("座席", "seat"), ("座席から波の方向", "seat_toward_wave"), ("左の側面", "side_left"),
             ("右の側面", "side_right"), ("真上", "top"), ("座席から見た頂と唇（爪の所の拡大）", (SH.crop(sb, bx), SH.crop(sn, bx)))]
    px = {v: (SH.claw_px(BEFORE, v), SH.claw_px(NOW, v)) for v in ("painting", "seat", "side_left", "back65", "top")}
    extra = ["見える爪の画素（爪ありと爪なしの描画の差、前 → 今）：" + "、".join("%s %s → %s" % (k, format(a, ","), format(b_, ",")) for k, (a, b_) in px.items()),
             "爪の置き方（案 A：原画の射線の上で奥行きだけ動かす）は変えていない。原画視点の外では今も細く短く見える（参照モデルの置き方 C4 は記録だけ）。"]
    pairs_sheet("座席・側面・真上：前｜今", items, os.path.join(out, "s4a_views.png"), extra)


def s4b_turntable(out):
    sh = SH.Sheet("回り台 12 方位（仰角 16°、半径 72 m）：前（見本02）｜今（修正の回 1）", NOTE)
    tw, th = 306, 172
    for k, az in enumerate(range(0, 360, 30)):
        r, cpos = divmod(k, 3)
        x = 16 + cpos * (2 * tw + 22); y = 76 + r * (th + 56)
        sh.text(x, y, "%d°" % az, 17, bold=True)
        sh.tile(SH.view(BEFORE, "tt%d" % az), x, y + 22, tw, th + 22, "前", 14)
        sh.tile(SH.view(NOW, "tt%d" % az), x + tw + 6, y + 22, tw, th + 22, "今", 14)
    sh.text(16, 1000, "0° は原画のカメラの側。180〜270° が背。", 16)
    sh.save(os.path.join(out, "s4b_turntable.png"))


def turntable_mp4(out):
    tmp = os.path.join(out, "_tt_frames")
    os.makedirs(tmp, exist_ok=True)
    names = []
    for k, az in enumerate(range(0, 360, 30)):
        sh = SH.Sheet("回り台 %d°（仰角 16°）　左：前（見本02）　右：今（修正の回 1）" % az, NOTE)
        sh.tile(SH.view(BEFORE, "tt%d" % az), 16, 120, 936, 560, "前", 18, True)
        sh.tile(SH.view(NOW, "tt%d" % az), 968, 120, 936, 560, "今", 18, True)
        p = os.path.join(tmp, "f%03d.png" % k)
        sh.im.save(p)
        names.append(p)
    mp4 = os.path.join(out, "turntable_before_now.mp4")
    subprocess.run([SH.FFMPEG, "-y", "-loglevel", "error", "-framerate", "1/0.8", "-i", os.path.join(tmp, "f%03d.png"), "-vf", "fps=10,format=yuv420p",
                    "-c:v", "libx264", "-crf", "26", mp4], check=True)
    for p in names:            # この関数が作った一時の静止画だけを片付ける
        os.remove(p)
    os.rmdir(tmp)
    print("wrote", mp4, os.path.getsize(mp4))


def main():
    os.makedirs(OUT, exist_ok=True)
    s2_painting(OUT)
    s3a_back(OUT)
    s4a_views(OUT)
    s4b_turntable(OUT)
    turntable_mp4(OUT)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
