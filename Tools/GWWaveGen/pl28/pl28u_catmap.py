# -*- coding: utf-8 -*-
"""仕上げ28（焼き直しと Unity の描画）：座席から波の方向の t* に出た「模様のない藍濃の縦の帯」の原因を確かめる図（記録）。

焼き込み（DS29R01ProjectionBaker、美術優先28修正01 の規則）は、テクセルごとに色の出どころを af28r01_uvcat_a45.bin に書く
（1 直接＝原画視点から見えて原画の色を写した所、2 内側の藍濃＝K*′ 自身に隠れた内側を平らな藍濃で塗った所、3/9/10/4 補い、5 海面の藍濃、12 継ぎ目）。
この道具は、K*′ の四角（行 r・列 c）ごとに UV3 の表（af28r01_uvwarp_a45.json）で覆うテクセルの出どころの多数を読み、
t* の K*′ の頂点を Unity の座席から波の方向のカメラ（PL28Render の報告の camPos・camTarget・fov）へ投影して、
「2 内側の藍濃」の四角を描画の画像に重ねる（段階9 の K*′ R4 と、仕上げ28 の K*′ P28R2 を並べる）。数も書く。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/pl28/pl28u_catmap.py [--out Docs/Evidence/Polish/28/fig_pl28u_stw_innerdark.png]
出力：図（1920×1080）と Unity/Build/Polish/28/unity/catmap_stw.json
"""
import argparse
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
U = os.path.join(REPO, "Unity", "Build", "Polish", "28", "unity")
STATES = {
    "stage9": {"bake": "Unity/Build/Design/29R01/bake_kp", "scene": "scene_stage9", "name": "段階9（K*' R4・設計29修正01 の焼き込み）"},
    "p28": {"bake": "Unity/Build/Polish/28/unity/bake_kp", "scene": "scene_p28", "name": "仕上げ28（K*' P28R2・焼き直し）"},
    "rec": {"bake": "Unity/Build/Polish/28/unity/bake_rec", "scene": "scene_rec", "name": "仕上げ28 の回復（K*' P28R2rec・焼き直し）"},
}
CAT_JA = {1: "直接", 2: "内側の藍濃", 3: "u 方向の補い", 4: "v 方向（画面外）", 5: "海面の藍濃", 9: "u 方向（隠れ・藍）", 10: "v 方向（隠れ）", 12: "継ぎ目"}


def read_gwb(p):
    b = open(p, "rb").read()
    assert b[:4] == b"GWW0"
    ver, nu, nv, nf = np.frombuffer(b[4:20], "<i4")
    ntri = int(np.frombuffer(b[28:32], "<i4")[0])
    n = int(nu) * int(nv)
    o = 32 + n * 16 + ntri * 12
    X = np.frombuffer(b, np.float32, n * 3, o).reshape(int(nv), int(nu), 3).astype(np.float64)
    return X


def cell_categories(bake):
    W = json.load(open(os.path.join(REPO, bake, "bake", "af28r01_uvwarp_a45.json"), encoding="utf-8"))
    u = np.asarray(W["uWarp"]); v = np.asarray(W["vWarp"])
    cat = np.fromfile(os.path.join(REPO, bake, "bake", "af28r01_uvcat_a45.bin"), np.uint8).reshape(4096, 4096)
    nv, nu = len(v), len(u)
    maj = np.zeros((nv - 1, nu - 1), np.uint8)
    frac2 = np.zeros((nv - 1, nu - 1))
    for r in range(nv - 1):
        y0, y1 = int(v[r] * 4096), max(int(v[r] * 4096) + 1, int(v[r + 1] * 4096))
        band = cat[y0:y1]
        for c in range(nu - 1):
            x0, x1 = int(u[c] * 4096), max(int(u[c] * 4096) + 1, int(u[c + 1] * 4096))
            blk = band[:, x0:x1].ravel()
            if blk.size == 0:
                continue
            cnt = np.bincount(blk, minlength=16)
            maj[r, c] = int(cnt.argmax())
            frac2[r, c] = cnt[2] / blk.size
    return maj, frac2


def project(P, pos, tgt, vfov, w=1920, h=1080):
    f = tgt - pos; f /= np.linalg.norm(f)
    r = np.cross(np.array([0.0, 1.0, 0.0]), f); r /= np.linalg.norm(r)
    up = np.cross(f, r)
    d = P - pos
    cx, cy, cz = d @ r, d @ up, d @ f
    t = np.tan(np.radians(vfov) / 2); asp = w / h
    x = (0.5 + 0.5 * cx / np.maximum(cz, 1e-6) / (t * asp)) * w
    y = (1 - (0.5 + 0.5 * cy / np.maximum(cz, 1e-6) / t)) * h
    return np.stack([x, y], -1), cz


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="Docs/Evidence/Polish/28/fig_pl28u_stw_innerdark.png")
    ap.add_argument("--view", default="seat_toward_wave")
    ap.add_argument("--states", default="stage9,p28", help="並べる状態（STATES の名前をコンマで。回復の版は rec）")
    a = ap.parse_args()
    res = {"schema": "GreatWave.Polish28.catmap/1", "view": a.view, "states": {}}
    panels = []
    for key, S in [(k, STATES[k]) for k in a.states.split(",")]:
        X = read_gwb(os.path.join(REPO, S["bake"], "kstar", "kstar_a45.gwb"))
        maj, frac2 = cell_categories(S["bake"])
        rep = json.load(open(os.path.join(U, S["scene"], "pl28_render_report.json"), encoding="utf-8"))
        im = [i for i in rep["images"] if i["view"] == a.view and i["cond"] == "clawfree" and abs(i["t"] - 12.0) < 1e-3][0]
        pos = np.array([im["camPos"]["x"], im["camPos"]["y"], im["camPos"]["z"]])
        tgt = np.array([im["camTarget"]["x"], im["camTarget"]["y"], im["camTarget"]["z"]])
        C = 0.25 * (X[:-1, :-1] + X[1:, :-1] + X[:-1, 1:] + X[1:, 1:])
        xy, cz = project(C.reshape(-1, 3), pos, tgt, im["fov"])
        xy = xy.reshape(C.shape[0], C.shape[1], 2); cz = cz.reshape(C.shape[:2])
        on = (cz > 0.3) & (xy[..., 0] >= 0) & (xy[..., 0] < 1920) & (xy[..., 1] >= 0) & (xy[..., 1] < 1080)
        base = Image.open(os.path.join(REPO, im["path"]) if not os.path.isabs(im["path"]) else im["path"]).convert("RGB")
        ov = Image.new("RGBA", base.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        sel = on & (maj == 2)
        for (r, c) in zip(*np.nonzero(sel)):
            q = [tuple(project(X[rr, cc][None], pos, tgt, im["fov"])[0][0]) for rr, cc in ((r, c), (r, c + 1), (r + 1, c + 1), (r + 1, c))]
            d.polygon(q, fill=(255, 0, 200, 70))
        comp = Image.alpha_composite(base.convert("RGBA"), ov).convert("RGB")
        panels.append((S["name"], comp))
        hist = {CAT_JA.get(k, str(k)): int(v) for k, v in enumerate(np.bincount(maj[on].ravel(), minlength=16)) if v}
        res["states"][key] = {"bake": S["bake"], "image": im["path"], "image_sha256": im["sha256"], "cells_on_screen": int(on.sum()),
                              "cells_on_screen_by_majority_category": hist, "cells_inner_dark_on_screen": int(sel.sum()),
                              "cells_inner_dark_all": int((maj == 2).sum()), "rows_cols_inner_dark_on_screen_bbox":
                                  [int(np.nonzero(sel)[0].min()), int(np.nonzero(sel)[0].max()), int(np.nonzero(sel)[1].min()), int(np.nonzero(sel)[1].max())] if sel.any() else None}
        bw = sel & (xy[..., 0] >= 800) & (xy[..., 0] <= 940) & (xy[..., 1] >= 150) & (xy[..., 1] <= 430)
        res["states"][key]["band_window_px"] = [800, 150, 940, 430]
        res["states"][key]["band_cells"] = int(bw.sum())
        if bw.any():
            rr, cc = np.nonzero(bw)
            res["states"][key]["band_rows"] = [int(rr.min()), int(rr.max())]
            res["states"][key]["band_cols"] = [int(cc.min()), int(cc.max())]
        res["states"][key]["_maj"] = maj
        print(key, json.dumps({k2: v2 for k2, v2 in res["states"][key].items() if k2 != "_maj"}, ensure_ascii=False)[:700])
    W, H = 1920, 1080
    S = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(S)
    f1 = ImageFont.truetype("C:/Windows/Fonts/YuGothB.ttc", 26); f2 = ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc", 19)
    d.text((16, 10), "仕上げ28：座席から波の方向 t* の「模様のない藍濃の帯」の出どころ（焼き込みのテクセルの出どころ。マゼンタ＝内側の藍濃）", font=f1, fill=(20, 24, 32))
    d.text((16, 50), "マゼンタの四角＝K*' の四角のうち、色の出どころの多数が「2 内側の藍濃」（原画視点では K*' 自身に隠れる面を、焼き込みの規則で平らな藍濃に塗った所）。"
           "数は画面内の四角", font=f2, fill=(20, 24, 32))
    keys = a.states.split(",")
    pw = (W - 8 * (len(keys) - 1)) // len(keys); ph = pw * 9 // 16
    for i, (name, comp) in enumerate(panels):
        k = keys[i]
        c = comp.resize((pw, ph), Image.LANCZOS)
        S.paste(c, (i * (pw + 8), 120))
        st = res["states"][k]
        nm = name if len(keys) <= 2 else {"stage9": "段階9（R4）", "p28": "P28R2（回復の前）", "rec": "P28R2rec（回復・採用）"}.get(k, name)
        d.text((i * (pw + 8) + 6, 90), "%s：内側の藍濃 %d（画面内 %d）" % (nm, st["cells_inner_dark_on_screen"], st["cells_on_screen"]), font=f2, fill=(20, 24, 32))
    # 下：帯の所の拡大（重ねない描画そのもの。元の画素 x 560〜1360、y 120〜570）
    for i, k in enumerate(keys):
        raw = Image.open(res["states"][k]["image"]).convert("RGB")
        c = raw.crop((560, 120, 1360, 570)).resize((pw, ph), Image.LANCZOS)
        S.paste(c, (i * (pw + 8), 120 + ph + 40))
    d.text((16, 120 + ph + 10), "下段：同じ描画を重ねずに拡大（元の画素の枠 x 560〜1360・y 120〜570）。Unity 6000.4.3f1 の PC 描画（爪なし）。HMD ではない", font=f2, fill=(20, 24, 32))
    # 仕上げ28 の帯の四角が、段階9 の焼き込みでは何だったか（同じ行・列の四角の出どころ）
    k2 = keys[1] if len(keys) > 1 else keys[0]   # 後の状態（既定は p28。回復の版は rec）
    maj_all = {k: res["states"][k].pop("_maj") for k in keys}
    m28, m9 = maj_all[k2], maj_all.get("stage9", maj_all[keys[0]])
    if "band_rows" in res["states"][k2]:
        r0, r1 = res["states"][k2]["band_rows"]; c0, c1 = res["states"][k2]["band_cols"]
        box9 = m9[r0:r1 + 1, c0:c1 + 1].ravel(); box28 = m28[r0:r1 + 1, c0:c1 + 1].ravel()
        res["band_rowcol_box_categories"] = {"rows": [r0, r1], "cols": [c0, c1],
                                             "stage9": {CAT_JA.get(k, str(k)): int(v) for k, v in enumerate(np.bincount(box9, minlength=16)) if v},
                                             k2: {CAT_JA.get(k, str(k)): int(v) for k, v in enumerate(np.bincount(box28, minlength=16)) if v}}
        print("band box", json.dumps(res["band_rowcol_box_categories"], ensure_ascii=False))
    out = os.path.join(REPO, a.out)
    S.save(out)
    res["figure"] = a.out
    with open(os.path.join(U, "catmap_stw.json" if a.states == "stage9,p28" else "catmap_stw_%s.json" % "_".join(keys)), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("PL28U_CATMAP_DONE")


if __name__ == "__main__":
    main()
