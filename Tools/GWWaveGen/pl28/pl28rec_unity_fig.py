# -*- coding: utf-8 -*-
"""仕上げ28 の回復（rec）：Unity の t* の描画で、評審が見つけた原画視点の 2 つの後退（左の船が隠れる・新しい線）を、段階9｜P28R2｜P28R2rec で
並べて数える（py -3.10、PIL・numpy・OpenCV）。入力は PL28Render の出力（Git 対象外の Unity/Build/Polish/28/unity/scene_*）。

数えるもの（metrics は <unity>/pl28rec_unity_counts.json）：
  * 船：全体の ID 画像（full/ids_noline_noclaws.png、3840×2160）の boat_left・boat_mid・boat_fg の画素と、CPU のメッシュ（手前の海・富士・仮置き）の画素。
    爪なしの原画視点の色画像（views/painting_t120_clawfree.png）で、段階9 の boat_left の画素のうち船の色（黄土）が見える画素。
  * 線：t* の組 t28_white の線の ID 画像（t28/render/af28r01_line_ids.png、マゼンタ）で、段階9 の線から 2 px（3840 の 4 px）より離れた新しい線の画素と塊。
    塊ごとに、原画視点の主役波の面（全体の ID 画像のシートの色区）の外（空・船の上）に出た線か、面の中の線かを分ける（輪郭の線が数 px 動いた分と、
    面の中に新しく出た線を分けるため）。
図（1920×1080、<out>）：
  fig_pl28rec_boat.png    左下の切り出し（x 150〜750、y 420〜820）を 3 段：段階9／P28R2／P28R2rec（爪なし）と、そのままの爪ありの 3 つ
  fig_pl28rec_lines.png   新しい線（赤＝面の中、橙＝面の外・輪郭の移動）を P28R2 と P28R2rec で。下に唇先と左端の輪郭の拡大（段階9｜P28R2rec）
usage: py -3.10 -B Tools/GWWaveGen/pl28/pl28rec_unity_fig.py [--unity Unity/Build/Polish/28/unity] [--out Docs/Evidence/Polish/28]
"""
import argparse
import hashlib
import json
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FONT = "C:/Windows/Fonts/YuGothM.ttc"
FONTB = "C:/Windows/Fonts/YuGothB.ttc"
STATES = [("scene_stage9", "段階9（K*' R4）"), ("scene_p28", "P28R2（回復の前）"), ("scene_rec", "P28R2rec（回復・採用）")]
ID = {"boat_left": (34, 0, 0), "boat_mid": (0, 34, 0), "boat_fg": (34, 34, 0), "cpu": (0, 0, 0), "sky": (0, 255, 255)}
SHEET = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
TAN = np.array([229, 193, 158])


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


def rgb(p):
    return np.array(Image.open(p).convert("RGB"))


def counts(U):
    out = {}
    ids9 = rgb(os.path.join(U, "scene_stage9", "full", "ids_noline_noclaws.png"))
    boat9 = np.all(ids9 == np.array(ID["boat_left"], np.uint8), -1)
    boat9_1080 = boat9.reshape(1080, 2, 1920, 2).any((1, 3))
    lines = {}
    for st, _ in STATES:
        ids = rgb(os.path.join(U, st, "full", "ids_noline_noclaws.png"))
        o = {k: int(np.all(ids == np.array(v, np.uint8), -1).sum()) for k, v in ID.items()}
        col = rgb(os.path.join(U, st, "views", "painting_t120_clawfree.png")).astype(int)
        tan = np.abs(col - TAN[None, None, :]).sum(-1) < 40
        o["tan_px_on_stage9_boat_left_1080"] = int((tan & boat9_1080).sum())
        o["tan_px_all_lower_left_1080"] = int(tan[420:900, 100:800].sum())
        li = rgb(os.path.join(U, st, "t28_white", "t28", "render", "af28r01_line_ids.png")).astype(int)
        lines[st] = (li[..., 0] > 200) & (li[..., 1] < 60) & (li[..., 2] > 200)
        o["line_px_t28_white_3840"] = int(lines[st].sum())
        face = np.zeros(ids.shape[:2], bool)
        for cc in SHEET:
            face |= np.all(ids == np.array(cc, np.uint8), -1)
        o["_face"] = face
        out[st] = o
    k = np.ones((9, 9), np.uint8)
    base = cv2.dilate(lines["scene_stage9"].astype(np.uint8), k).astype(bool)
    for st, _ in STATES[1:]:
        new = lines[st] & ~base
        face = cv2.erode(out[st]["_face"].astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)   # 面の縁から 4 px 内側
        n, lab, stt, _ = cv2.connectedComponentsWithStats(cv2.dilate(new.astype(np.uint8), np.ones((9, 9), np.uint8)), connectivity=8)
        blobs = []
        for i in range(1, n):
            m = (lab == i) & new
            if m.sum() < 60:
                continue
            ys, xs = np.nonzero(m)
            inside = float((m & face).sum() / m.sum())
            blobs.append({"px_3840": int(m.sum()), "x_1080": [int(xs.min() // 2), int(xs.max() // 2)], "y_1080": [int(ys.min() // 2), int(ys.max() // 2)],
                          "inside_face_frac": round(inside, 2), "kind": "面の中" if inside >= 0.5 else "面の外（輪郭の移動）"})
        blobs.sort(key=lambda b: -b["px_3840"])
        out[st]["new_lines_vs_stage9"] = {"px_3840": int(new.sum()), "px_inside_face": int((new & face).sum()), "blobs": blobs}
        out[st]["_new"] = new; out[st]["_newin"] = new & face
    return out


def fig_boat(U, out_png, cnt):
    W, H = 1920, 1080
    S = Image.new("RGB", (W, H), (255, 255, 255)); d = ImageDraw.Draw(S)
    d.text((16, 10), "仕上げ28 の回復：原画視点 t* の左下（左の船 157 boat_left）　段階9｜P28R2｜P28R2rec", font=font(26, True), fill=(20, 24, 32))
    d.text((16, 48), "上段：爪なし（白あり・爪・飛沫・紙なし・線あり）、下段：作品のまま（爪・飛沫あり）。元の画素の枠 x 150〜750・y 420〜820。Unity 6000.4.3f1 の PC 描画、HMD ではない",
           font=font(17), fill=(20, 24, 32))
    box = (150, 420, 750, 820)
    cw = 636; ch = int(cw * (box[3] - box[1]) / (box[2] - box[0]))
    for j, (st, name) in enumerate(STATES):
        for i, cond in enumerate(("clawfree", "asis")):
            im = Image.open(os.path.join(U, st, "views", "painting_t120_%s.png" % cond)).convert("RGB").crop(box).resize((cw, ch), Image.LANCZOS)
            S.paste(im, (j * (cw + 6), 84 + i * (ch + 8)))
        c = cnt[st]
        d.rectangle([j * (cw + 6), 84, j * (cw + 6) + cw, 84 + 30], fill=(20, 24, 32))
        d.text((j * (cw + 6) + 8, 88), "%s　船の ID %d 画素（3840）" % (name, c["boat_left"]), font=font(18, True), fill=(255, 255, 255))
    S.save(out_png)


def fig_lines(U, out_png, cnt):
    W, H = 1920, 1080
    S = Image.new("RGB", (W, H), (255, 255, 255)); d = ImageDraw.Draw(S)
    d.text((16, 10), "仕上げ28 の回復：原画視点 t* の線（t28_white の線の ID、段階9 に対して新しい線）", font=font(26, True), fill=(20, 24, 32))
    d.text((16, 48), "赤＝主役波の面の中に新しく出た線、橙＝面の外（輪郭の線が数 px 動いた分）。線の印（設計38）は R4 のまま（作り直しは仕上げ38 の最初）", font=font(17), fill=(20, 24, 32))
    for j, (st, name) in enumerate(STATES[1:]):
        base = Image.open(os.path.join(U, st, "views", "painting_t120_clawfree.png")).convert("RGB")
        a = np.array(base).copy()
        new = cnt[st]["_new"].reshape(1080, 2, 1920, 2).any((1, 3)); newin = cnt[st]["_newin"].reshape(1080, 2, 1920, 2).any((1, 3))
        k = np.ones((5, 5), np.uint8)
        a[cv2.dilate((new & ~newin).astype(np.uint8), k).astype(bool)] = (255, 150, 0)
        a[cv2.dilate(newin.astype(np.uint8), k).astype(bool)] = (230, 0, 0)
        im = Image.fromarray(a).resize((950, 534), Image.LANCZOS)
        S.paste(im, (j * 966, 80))
        nl = cnt[st]["new_lines_vs_stage9"]
        d.rectangle([j * 966, 80, j * 966 + 950, 110], fill=(20, 24, 32))
        d.text((j * 966 + 8, 84), "%s：新しい線 %d 画素（面の中 %d）" % (name, nl["px_3840"], nl["px_inside_face"]), font=font(18, True), fill=(255, 255, 255))
    # 下：唇先と左端の輪郭の拡大（段階9｜P28R2rec）
    y0 = 630
    for k2, box in enumerate([(880, 380, 1110, 490), (0, 330, 230, 440)]):
        for j, st in enumerate(("scene_stage9", "scene_rec")):
            im = Image.open(os.path.join(U, st, "views", "painting_t120_clawfree.png")).convert("RGB").crop(box)
            im = im.resize((460, int(460 * im.height / im.width)), Image.NEAREST)
            S.paste(im, (k2 * 960 + j * 470, y0 + 30))
        d.text((k2 * 960 + 4, y0), ("唇先（x 880〜1110・y 380〜490）" if k2 == 0 else "左端（x 0〜230・y 330〜440）") + "　左：段階9　右：P28R2rec。輪郭の線が数 px 動いただけ",
               font=font(17), fill=(20, 24, 32))
    S.save(out_png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unity", default="Unity/Build/Polish/28/unity")
    ap.add_argument("--out", default="Docs/Evidence/Polish/28")
    a = ap.parse_args()
    U = os.path.join(REPO, a.unity); O = os.path.join(REPO, a.out)
    cnt = counts(U)
    fig_boat(U, os.path.join(O, "fig_pl28rec_boat.png"), cnt)
    fig_lines(U, os.path.join(O, "fig_pl28rec_lines.png"), cnt)
    res = {"schema": "GreatWave.Polish28.rec_unity_counts/1", "states": {st: {k: v for k, v in cnt[st].items() if not k.startswith("_")} for st, _ in STATES},
           "inputs_sha256": {st: sha256(os.path.join(U, st, "pl28_render_report.json")) for st, _ in STATES},
           "figures_sha256": {f: sha256(os.path.join(O, f)) for f in ("fig_pl28rec_boat.png", "fig_pl28rec_lines.png")}}
    with open(os.path.join(U, "pl28rec_unity_counts.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
