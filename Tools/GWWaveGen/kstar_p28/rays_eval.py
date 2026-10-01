# -*- coding: utf-8 -*-
"""仕上げ28 第1回：Tools/GWWaveGen/kstar_h/kh_eval.py をそのまま使う評価の包み（py -3.10）。
変えるのは一時の場所だけ：参照モデルの F13 用の一時キャッシュ（KC.TMP）と、消したキャッシュの SHA-256 の記録
（KC.OUT_ROOT/deleted_caches_sha256.txt）を、Unity/Build/Polish/28/r1_rays/_tmp の下へ置く（この回の作業場所の外へ書かない）。
参照モデルは評価器が F13 と量感の比べの数値のためだけに一時キャッシュで読み、終わりに消す。生成器（rays_build.py）は読まない。
usage: py -3.10 rays_eval.py [kh_eval.py と同じ引数]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KH = os.path.abspath(os.path.join(HERE, "..", "kstar_h"))
sys.path.insert(0, KH)
sys.argv[0] = os.path.join(KH, "kh_eval.py")
import kh_common as KC  # noqa: E402

TMPROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "Unity", "Build", "Polish", "28", "r1_rays", "_tmp"))
os.makedirs(TMPROOT, exist_ok=True)
KC.TMP = os.path.join(TMPROOT, "ref_cache")
KC.OUT_ROOT = TMPROOT
import kh_eval  # noqa: E402

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    kh_eval.main()
