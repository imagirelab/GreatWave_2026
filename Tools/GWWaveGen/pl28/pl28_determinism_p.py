# -*- coding: utf-8 -*-
"""仕上げ28：ds28p の包み（G_p28a・G_p28b）の決定性の抜き取り。試行F の台本 ds28r01f_determinism.py を、生成器を作る関数だけ
ds28p に差し替えて（ds28p_generate を import すると差し替わる）そのまま走らせる。ds28p の値の切りは、包みの ds28p_generate_log.json の
p_off を環境変数 DS28P_OFF で渡す（生成の時と同じ）。
使い方：py -3.10 -B Tools/GWWaveGen/pl28/pl28_determinism_p.py --package Unity/Build/Polish/28/G_p28b/art_on --out <json>
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for sub in ("ds28p", "ds28r01f"):
    sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", sub))

if __name__ == "__main__":
    pkg = sys.argv[sys.argv.index("--package") + 1]
    pa = pkg if os.path.isabs(pkg) else os.path.join(REPO, pkg)
    lg = json.load(open(os.path.join(pa, "ds28p_generate_log.json"), encoding="utf-8"))
    off = lg.get("p_off") or [n for n, v in (lg.get("p_on") or {}).items() if not v]
    os.environ["DS28P_OFF"] = ",".join(off)
    import ds28p_generate  # noqa: F401,E402  （ds28r01f_generate._winit を ds28p に差し替える）
    import ds28r01f_determinism as DT  # noqa: E402
    DT.main()
