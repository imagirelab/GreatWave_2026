# -*- coding: utf-8 -*-
"""K*′ 精修 R4：候補を目で見るための素早い描画（py -3.10 → Blender 5.2.2 の kh_bl.py、粘土）。当てはめの途中の判断用。
設計の json か行の npz を GWW0 に書き、評審が見た視点（v1・v3・v6・v7・v9・u11・u13）とターンテーブルの 12 こま（f0000〜f0220）を描き、
並べた 1 枚（look_<label>.png）を作る。比べる候補（R3 など）を同じ並びで横に置ける。
usage: py -3.10 kh_R4_look.py <out_dir> label=design.json|rows.npz|file.gwb [label2=...] [--views v1_painting+...] [--no-tt] [--tt-frames 20,40,...]
"""
import os
import sys
import json
import subprocess
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import kh_common as KC  # noqa: E402

VIEWS = "v1_painting+v3_side_along_crest_cam_side+v6_top_down+v7_user6_az330_el10+v9_user8_az030_el25+u11_v9zoom_crest_bulge+u13_v8zoom_b_region+v5_back_three_quarter"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")


def to_gwb(spec, out_prefix):
    if spec.endswith(".gwb"):
        return spec
    if spec.endswith(".json"):
        import kh_designR4 as D
        c, A, Y, P = D.build(D.Design.load(spec))
    else:
        z = np.load(spec); c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
    X = KC.world(c, A, Y)
    nv, nu = A.shape
    uvk, uv2k = KC.kstar_uv()
    uv = uvk.reshape(-1, 2)
    uv2 = np.stack([uv2k[..., 0], np.broadcast_to(c[:, None], (nv, nu))], -1).reshape(-1, 2)
    KC.write_gwb(out_prefix + ".gwb", nu, nv, uv, uv2, KC.triangles(nu, nv), X)
    np.savez_compressed(out_prefix + "_rows.npz", c=c, A=A, Y=Y)
    return out_prefix + ".gwb"


def main():
    a = sys.argv[1:]
    out = os.path.abspath(a[0]); os.makedirs(out, exist_ok=True)
    items = [x.split("=", 1) for x in a[1:] if "=" in x and not x.startswith("--")]
    views = a[a.index("--views") + 1] if "--views" in a else VIEWS
    ttf = [int(x) for x in a[a.index("--tt-frames") + 1].split(",")] if "--tt-frames" in a else [0, 20, 40, 60, 140, 160, 180, 200]
    gw = []
    for lab, spec in items:
        gw.append((lab, to_gwb(spec, os.path.join(out, lab))))
    cmd = [KC.BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", os.path.join(HERE, "kh_bl.py"), "--", "views",
           out, ",".join("%s=%s" % (l, g) for l, g in gw), "views=" + views, "scale=0.5"]
    r = subprocess.run(cmd, capture_output=True, text=True, env=ENV, encoding="utf-8", errors="replace", timeout=1500)
    if r.returncode:
        print(r.stdout[-3000:], r.stderr[-3000:]); raise SystemExit(1)
    if "--no-tt" not in a:
        for lab, g in gw:
            td = os.path.join(out, "tt_" + lab)
            cmd = [KC.BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", os.path.join(HERE, "kh_bl.py"), "--",
                   "turntable", g, "none", td, "240", "72", "16", "640", "360"]
            r = subprocess.run(cmd, capture_output=True, text=True, env=ENV, encoding="utf-8", errors="replace", timeout=1500)
            if r.returncode:
                print(r.stdout[-3000:], r.stderr[-3000:]); raise SystemExit(1)
    from PIL import Image, ImageDraw
    vl = views.split("+")
    cw, ch = 480, 270
    rows_ = [("view", v) for v in vl] + ([] if "--no-tt" in a else [("tt", f) for f in ttf])
    per = 2 if len(gw) <= 2 else 1
    ncol = per * len(gw)
    nrow = (len(rows_) + per - 1) // per
    S = Image.new("RGB", (cw * ncol, ch * nrow), "white")
    d = ImageDraw.Draw(S)
    for k, (kind, v) in enumerate(rows_):
        gr, gc = divmod(k, per)
        for i, (lab, _) in enumerate(gw):
            p = os.path.join(out, "%s__%s.png" % (lab, v)) if kind == "view" else os.path.join(out, "tt_" + lab, "f_%04d.png" % v)
            if not os.path.isfile(p):
                continue
            im = Image.open(p).convert("RGB")
            im = im.resize((cw, int(im.height * cw / im.width))) if im.width / im.height > cw / ch else im.resize((int(im.width * ch / im.height), ch))
            x0 = (gc * len(gw) + i) * cw
            S.paste(im, (x0, gr * ch))
            d.rectangle([x0, gr * ch, x0 + cw - 1, gr * ch + ch - 1], outline=(255, 255, 255))
            d.text((x0 + 6, gr * ch + 4), "%s %s" % (lab, v if kind == "view" else "f%04d" % v), fill=(255, 255, 0))
    name = os.path.join(out, "look_%s.png" % "_".join(l for l, _ in gw))
    S.save(name)
    print(name)


if __name__ == "__main__":
    main()
