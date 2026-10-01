# -*- coding: utf-8 -*-
"""仕上げ28 第1回：候補を目で見るための粘土の描画（py -3.10 → Blender 5.2.2 の faceswap_bl.py）。kh_R4_look.py と同じ並べ方。
usage: py -3.10 faceswap_look.py <out_dir> label=rows.npz|file.gwb [label2=...] [--views a+b+...] [--no-tt] [--tt-frames 0,20,...] [--scale 0.5]"""
import os
import sys
import subprocess

import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import faceswap_common as F  # noqa: E402
KC = F.KC
VIEWS = "v1_painting+b65_back+b90_back_straight+v5_back_three_quarter+u11_v9zoom_crest_bulge+v9_user8_az030_el25+u13_v8zoom_b_region+v6_top_down+v3_side_along_crest_cam_side+v7_user6_az330_el10"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")


def to_gwb(spec, out_prefix):
    if spec.endswith(".gwb"):
        return spec
    z = np.load(spec)
    c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
    X = KC.world(c, A, Y)
    nv, nu = A.shape
    uvk, uv2k = KC.kstar_uv()
    uv = uvk.reshape(-1, 2)
    uv2 = np.stack([uv2k[..., 0], np.broadcast_to(c[:, None], (nv, nu))], -1).reshape(-1, 2)
    KC.write_gwb(out_prefix + ".gwb", nu, nv, uv, uv2, KC.triangles(nu, nv), X)
    return out_prefix + ".gwb"


def main():
    a = sys.argv[1:]
    out = os.path.abspath(a[0]); os.makedirs(out, exist_ok=True)
    items = [x.split("=", 1) for x in a[1:] if "=" in x and not x.startswith("--")]
    views = a[a.index("--views") + 1] if "--views" in a else VIEWS
    scale = a[a.index("--scale") + 1] if "--scale" in a else "0.5"
    ttf = [int(x) for x in a[a.index("--tt-frames") + 1].split(",")] if "--tt-frames" in a else [0, 60, 100, 140, 160, 180, 200, 220]
    gw = [(lab, to_gwb(spec, os.path.join(out, "_" + lab))) for lab, spec in items]
    cmd = [KC.BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", os.path.join(HERE, "faceswap_bl.py"), "--", "views",
           out, ",".join("%s=%s" % (l, g) for l, g in gw), "views=" + views, "scale=" + scale]
    r = subprocess.run(cmd, capture_output=True, text=True, env=ENV, encoding="utf-8", errors="replace", timeout=1500)
    if r.returncode:
        print(r.stdout[-3000:], r.stderr[-3000:]); raise SystemExit(1)
    if "--no-tt" not in a:
        for lab, g in gw:
            td = os.path.join(out, "tt_" + lab)
            cmd = [KC.BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", os.path.join(HERE, "faceswap_bl.py"), "--",
                   "turntable", g, "none", td, "240", "72", "16", "640", "360"]
            r = subprocess.run(cmd, capture_output=True, text=True, env=ENV, encoding="utf-8", errors="replace", timeout=1500)
            if r.returncode:
                print(r.stdout[-3000:], r.stderr[-3000:]); raise SystemExit(1)
    from PIL import Image, ImageDraw
    vl = views.split("+")
    cw, ch = 640, 360
    rows_ = [("view", v) for v in vl] + ([] if "--no-tt" in a else [("tt", f) for f in ttf])
    ncol = len(gw)
    S = Image.new("RGB", (cw * ncol, ch * len(rows_)), "white")
    d = ImageDraw.Draw(S)
    for k, (kind, v) in enumerate(rows_):
        for i, (lab, _) in enumerate(gw):
            p = os.path.join(out, "%s__%s.png" % (lab, v)) if kind == "view" else os.path.join(out, "tt_" + lab, "f_%04d.png" % v)
            if not os.path.isfile(p):
                continue
            im = Image.open(p).convert("RGB")
            im.thumbnail((cw, ch))
            x0 = i * cw
            S.paste(im, (x0, k * ch))
            d.rectangle([x0, k * ch, x0 + cw - 1, k * ch + ch - 1], outline=(255, 255, 255))
            d.text((x0 + 6, k * ch + 4), "%s %s" % (lab, v if kind == "view" else "turntable f%04d" % v), fill=(255, 255, 0))
    name = os.path.join(out, "look_%s.png" % "_".join(l for l, _ in gw))
    S.save(name)
    print(name)


if __name__ == "__main__":
    main()
