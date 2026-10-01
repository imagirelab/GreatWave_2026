# -*- coding: utf-8 -*-
"""仕上げ28 第1回（back-first）：行の npz → 描画用の GWW0 → Blender の粘土（backfirst_bl.py）→ 並べ図（py -3.10）。
usage: py -3.10 backfirst_render.py OUT_DIR views(all|std|user|a+b+..) label=rows.npz|gwb ... [--sheet NAME] [--cols 3] [--w 640]
並べ図は視点ごとに行、候補ごとに列（左から引数の順）。"""
import os
import sys
import subprocess
sys.dont_write_bytecode = True
REPO = r"G:\Unity\GreatWave_2026_Fresh"
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "kstar_h"))
import numpy as np  # noqa: E402
import cv2  # noqa: E402
import kh_common as KC  # noqa: E402
HERE = os.path.dirname(os.path.abspath(__file__))


def to_gwb(rows, out):
    z = np.load(rows)
    c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
    nv, nu = A.shape
    uvk, uv2k = KC.kstar_uv()
    KC.write_gwb(out, nu, nv, uvk.reshape(-1, 2), uv2k.reshape(-1, 2), KC.triangles(nu, nv), KC.world(c, A, Y))
    return out


def main():
    out = sys.argv[1]; views = sys.argv[2]
    args = sys.argv[3:]
    sheet = args[args.index("--sheet") + 1] if "--sheet" in args else None
    W = int(args[args.index("--w") + 1]) if "--w" in args else 640
    items = []
    skip = set()
    for i, a in enumerate(args):
        if a.startswith("--"):
            skip.add(i); skip.add(i + 1)
    for i, a in enumerate(args):
        if i in skip or "=" not in a:
            continue
        lab, p = a.split("=", 1)
        if p.endswith(".npz"):
            p = to_gwb(p, os.path.join(out, "_render_%s.gwb" % lab)) if os.makedirs(out, exist_ok=True) is None else None
        items.append((lab, p))
    os.makedirs(out, exist_ok=True)
    cmd = [KC.BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", os.path.join(HERE, "backfirst_bl.py"), "--",
           "views", out, ",".join("%s=%s" % x for x in items), "views=%s" % views]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    open(os.path.join(out, "blender_%s.log" % (sheet or "views")), "w", encoding="utf-8").write(r.stdout[-20000:] + r.stderr[-5000:])
    if r.returncode != 0:
        raise SystemExit("blender failed (see log)")
    if sheet:
        names = sorted({f.split("__", 1)[1][:-4] for f in os.listdir(out) if "__" in f and f.endswith(".png") and f.split("__")[0] == items[0][0]})
        if views not in ("all", "std", "user"):
            names = views.split("+")
        rows = []
        for vn in names:
            tiles = []
            for lab, _ in items:
                im = cv2.imread(os.path.join(out, "%s__%s.png" % (lab, vn)))
                if im is None:
                    im = np.zeros((360, W, 3), np.uint8)
                im = cv2.resize(im, (W, int(im.shape[0] * W / im.shape[1])))
                cv2.putText(im, "%s  %s" % (lab, vn), (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2, cv2.LINE_AA)
                cv2.putText(im, "%s  %s" % (lab, vn), (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
                tiles.append(im)
            h = max(t.shape[0] for t in tiles)
            tiles = [cv2.copyMakeBorder(t, 0, h - t.shape[0], 0, 4, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for t in tiles]
            rows.append(cv2.copyMakeBorder(np.hstack(tiles), 0, 4, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255)))
        wmax = max(r_.shape[1] for r_ in rows)
        rows = [cv2.copyMakeBorder(r_, 0, 0, 0, wmax - r_.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)) for r_ in rows]
        cv2.imwrite(os.path.join(out, sheet), np.vstack(rows))
    print("ok", out)


if __name__ == "__main__":
    main()
