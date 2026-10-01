# -*- coding: utf-8 -*-
"""仕上げ28 第1回：粘土の描画。Tools/GWWaveGen/kstar_h/kh_bl.py をそのまま使い、視点の一覧だけを
rays_views.json（kh_views.json の写し＋後ろ 65°・その拡大・真後ろ・c− 側の後ろ）に替える。
usage（kh_bl.py と同じ）:
  blender --background --factory-startup --python-exit-code 1 --python rays_bl.py -- views <out_dir> <label=path,...> [views=...]
  blender ... --python rays_bl.py -- turntable <path> <out.mp4|none> <stills_dir> [n_frames] [radius] [elev] [w] [h]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "kstar_h", "kh_bl.py")
code = open(SRC, encoding="utf-8").read()
old = 'VIEWS = os.path.join(HERE, "kh_views.json")'
assert old in code
code = code.replace(old, 'VIEWS = os.path.join(r"%s", "rays_views.json")' % HERE.replace("\\", "/"))
code = code.replace('HERE = os.path.dirname(os.path.abspath(__file__))', 'HERE = r"%s"' % os.path.dirname(os.path.abspath(SRC)).replace("\\", "/"), 1)
g = {"__name__": "__main__", "__file__": SRC}
exec(compile(code, SRC, "exec"), g)
