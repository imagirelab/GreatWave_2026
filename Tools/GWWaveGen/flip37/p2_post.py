# -*- coding: utf-8 -*-
"""P2 の 1 本の計算の後処理：解析（p2_analyze）→ 一枚の図（p2_figs run）→ 粘土の図（p2_figs clay）。py -3.10 p2_post.py <run_dir>"""
import sys, os, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
rd = sys.argv[1]
for cmd in (["p2_analyze.py", rd, "--quiet"], ["p2_figs.py", "run", rd], ["p2_figs.py", "clay", rd], ["p2_figs.py", "strip", rd]):
    r = subprocess.run([sys.executable, os.path.join(HERE, cmd[0])] + cmd[1:], capture_output=True, text=True)
    print(cmd[0], r.returncode, r.stdout[-1500:], r.stderr[-1500:]); sys.stdout.flush()
