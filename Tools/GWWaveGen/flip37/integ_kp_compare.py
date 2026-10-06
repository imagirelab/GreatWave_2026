# -*- coding: utf-8 -*-
"""組み込みの準備：方法 A を、試作の再生器（F37SeqPlayer、float32 のコマを Catmull-Rom、属性はコマごと）と、
作品の再生器（DS30SheetPlayer＋PL29UkiyoeHero、keypose の包み、属性は t* の 1 回だけ）で描いた画を比べる。
- 形：空でない画素（主役波＋周りの海）の一致（IoU）と、違う画素の割合。
- 色：両方で波の画素のうち、色が 30（0〜255 の和の差）を超えて違う割合（属性の出どころが違うので、帯・白は違ってよい）。
出力：Unity/Build/FLIP37/integration_prep/unity_render/kp_compare.json と <seq>_kp_compare.png
"""
import os, sys, json, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integ_common as C

SKY = np.array([249, 232, 196])


def main():
    out = {}
    seqs = [a for a in sys.argv[1:] if not a.startswith("--")] or ["R05", "P1sweep"]   # 2026-10-06：R18 を足せるように引数で選ぶ
    for seq in seqs:
        rd = C.OUT + "/unity_render/" + seq
        fs = sorted(glob.glob(rd + "/keypose_painting/f_*.png"))
        rec = []
        picks = []
        for cam in ("painting", "seat"):
            ious, dfr, cdf = [], [], []
            for i, f in enumerate(sorted(glob.glob(rd + "/keypose_%s/f_*.png" % cam))):
                name = os.path.basename(f)
                a = np.asarray(Image.open(rd + "/sheet_%s/%s" % (cam, name)).convert("RGB")).astype(int)
                b = np.asarray(Image.open(f).convert("RGB")).astype(int)
                ma = np.abs(a - SKY).sum(-1) > 6; mb = np.abs(b - SKY).sum(-1) > 6
                u = (ma | mb).sum()
                iou = (ma & mb).sum() / u if u else 1.0
                both = ma & mb
                cd = (np.abs(a - b).sum(-1) > 30)[both].mean() if both.any() else 0.0
                ious.append(iou); dfr.append((ma ^ mb).mean()); cdf.append(cd)
                if cam == "painting" and i in (0, len(fs) // 2, len(fs) - 1):
                    picks.append((name, a, b))
            rec.append({"camera": cam, "frames": len(ious), "silhouette_iou_min": float(min(ious)), "silhouette_iou_mean": float(np.mean(ious)),
                        "pixels_differ_silhouette_max": float(max(dfr)), "colour_differ_in_wave_mean": float(np.mean(cdf)), "colour_differ_in_wave_max": float(max(cdf))})
        out[seq] = rec
        # 並べ図：試作の再生器 | 作品の再生器 | 形の違い（赤：試作だけ、青：作品だけ）
        rows = []
        for name, a, b in picks:
            ma = np.abs(a - SKY).sum(-1) > 6; mb = np.abs(b - SKY).sum(-1) > 6
            d = np.full(a.shape, 255, np.uint8)
            d[ma & mb] = (200, 200, 200); d[ma & ~mb] = (220, 0, 0); d[~ma & mb] = (0, 0, 220)
            rows.append(np.concatenate([a.astype(np.uint8), b.astype(np.uint8), d], 1))
        img = Image.fromarray(np.concatenate(rows, 0))
        img = img.resize((img.width // 2, img.height // 2))
        dr = ImageDraw.Draw(img)
        try:
            ft = ImageFont.truetype(r"C:/Windows/Fonts/meiryo.ttc", 14)
        except Exception:
            ft = ImageFont.load_default()
        for k, lab in enumerate(["試作の再生器（F37SeqPlayer、float32）", "作品の再生器（DS30SheetPlayer＋PL29UkiyoeHero、keypose）", "形の違い（赤＝試作だけ、青＝作品だけ）"]):
            bb = dr.textbbox((k * img.width // 3 + 6, 4), lab, font=ft)
            dr.rectangle([bb[0] - 3, bb[1] - 2, bb[2] + 3, bb[3] + 2], fill=(255, 255, 255))
            dr.text((k * img.width // 3 + 6, 4), lab, fill=(0, 0, 0), font=ft)
        img.save(C.OUT + "/unity_render/%s_kp_compare.png" % seq)
    json.dump({"compare": out, "note_ja": "同じ時刻の原画カメラ・座席の画。空の色でない画素を形とした。周りの海は両方とも同じ（方法 B の網目から主役波の範囲を除いたもの）。"
                                          "属性は、試作の再生器はコマごと、作品の再生器は t* の 1 回だけ（作品の約束）なので、帯・白の位置は違ってよい。"},
              open(C.OUT + "/unity_render/kp_compare%s.json" % ("" if seqs == ["R05", "P1sweep"] else "_" + "_".join(seqs)), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
