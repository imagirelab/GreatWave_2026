# -*- coding: utf-8 -*-
"""write a GWW0 for a rows npz and run the Q20 rubric checker on it (+ optional 9-view clay renders)."""
import sys, os, json, subprocess
import numpy as np
from candB_common import *
sys.stdout.reconfigure(encoding="utf-8")
tag = sys.argv[1]; render = "--render" in sys.argv; gate_ = "--gate" in sys.argv
z = np.load(os.path.join(WORK, "rows_%s.npz" % tag)); A, Y, c = z["A"], z["Y"], z["c"]
gwb = os.path.join(WORK, "kstarB_%s.gwb" % tag)
h = write_gwb(gwb, A, Y, c)
print("gwb", gwb, h[:12])
out = os.path.join(WORK, "rubric_%s.json" % tag)
cmd = ["py", "-3.10", os.path.join(RUBRIC, "tools", "rubric_check.py"), os.path.join(WORK, "rows_%s.npz" % tag), out] + (["--gate"] if gate_ else [])
r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
tab = open(os.path.splitext(out)[0] + "_table.md", encoding="utf-8").read().splitlines() if os.path.isfile(os.path.splitext(out)[0] + "_table.md") else []
for L in tab:
    if "**否**" in L or "all" in sys.argv:
        print(L)
R = json.load(open(out, encoding="utf-8")) if os.path.isfile(out) else {}
print(R.get("summary"))
if r.returncode:
    print(r.stderr[-3000:])
if render:
    BL = r"G:\SteamLibrary\steamapps\common\Blender\blender.exe"
    rd = os.path.join(WORK, "renders_%s" % tag)
    cache = os.path.join(WORK, "_nocache.npz")
    cmd = [BL, "--background", "--factory-startup", "--python-exit-code", "1", "--python", os.path.join(RUBRIC, "tools", "bl_rubric_views.py"), "--", rd, cache, "kstar", "all", gwb, "candB"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("render rc", r.returncode, r.stdout[-400:] if r.returncode else "")
