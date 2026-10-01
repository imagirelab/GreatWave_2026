# -*- coding: utf-8 -*-
"""仕上げ28 第1回（back-first）の納品（py -3.10）。

  1 設計の json → 行の npz → K*′ の候補（GWW0 + meta + rows npz + OBJ、kh_common.write_candidate。400×240、目印・UV は K* と同じ）
  2 公式の評価 kh_eval.py（原画の関門：定義どおりの読み・σ12 / σ24 の大きな輪郭、評価基準、Q21 の検査、網の衛生、F13）を、
    候補・R4（直前の採用版）・K* 26修正01 について回す。参照モデルの一時キャッシュは、この第1回の作業フォルダーの _tmp に置き、
    評価の後に消して SHA-256 を deleted_caches_sha256.txt（同じフォルダー）へ記録する（kh_eval の KC.TMP / KC.OUT_ROOT をここへ向ける）。
  3 粘土の描画（kh_eval の --render --turntable：9 視点＋利用者の失敗の視点 4、回り台）
usage: py -3.10 backfirst_deliver.py design.json OUT_DIR [--no-eval] [--no-render]
"""
import os
import sys
import json
import time
import shutil
import datetime
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"G:\Unity\GreatWave_2026_Fresh"
KH = os.path.join(REPO, "Tools", "GWWaveGen", "kstar_h")
for p in (HERE, KH):
    if p not in sys.path:
        sys.path.insert(0, p)
import numpy as np  # noqa: E402
import kh_common as KC  # noqa: E402
import backfirst_model as M  # noqa: E402

R4_GWB = os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "kstar_final", "kstarR4_a45.gwb")
KSTAR_ROWS = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01", "kstar", "kstar_a45_rows.npz")
PREFIX = "kstarP28bf_a45"


def main():
    dj, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    cand = os.path.join(out, "candidate")
    os.makedirs(cand, exist_ok=True)
    d = json.load(open(dj, encoding="utf-8"))
    t0 = time.time()
    c, A, Y = M.build(d)
    assert A.shape == (KC.NV, KC.NU), A.shape
    shutil.copyfile(dj, os.path.join(cand, "kstarP28bf_design.json"))
    code = {os.path.basename(p): KC.sha256(p) for p in (
        os.path.join(HERE, "backfirst_model.py"), os.path.join(HERE, "backfirst_eval.py"), os.path.join(HERE, "backfirst_fitfar.py"),
        os.path.join(HERE, "backfirst_deliver.py"))}
    prov = {"round_ja": "仕上げ28 第1回（背から先に作る案 back-first）", "generator": "Tools/GWWaveGen/kstar_p28/backfirst_model.py (numpy)",
            "design_json": os.path.basename(dj), "design_sha256": KC.sha256(dj),
            "base_rows_R3": {"path": M.BASE_R3, "sha256": KC.sha256(M.BASE_R3)},
            "back_template_rows_R4": {"path": M.BACK_TPL_R4, "sha256": KC.sha256(M.BACK_TPL_R4),
                                      "use_ja": "旧 v1 の背の型（R4 の主断面）。採用の設計（mode v3）は解析の断面 g(u) = (1 − cos π u^q)/2 を使い、R4 は読まない"},
            "reference_model_ja": "生成器・当てはめは参照モデルを読まない（F13-1）。評価器（kh_eval）の F13 だけが一時キャッシュで読み、消して SHA-256 を記録する。",
            "code_sha256": code, "built_utc": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}
    meta = KC.write_candidate(os.path.join(cand, PREFIX), c, A, Y, prov)
    print("candidate written", json.dumps(meta["checks"]), "H0 %.2f Hmax %.2f" % (meta["H0_m"], meta["highest_point"]["H_m"]), flush=True)
    if "--no-eval" in sys.argv:
        return
    # ---- official evaluation (kh_eval) with the reference cache inside this work directory
    os.environ["GW_Q16_CREST_DIR"] = os.environ.get("GW_Q16_CREST_DIR", "")
    import kh_eval as KE
    KC.TMP = os.path.join(out, "_tmp")
    KC.OUT_ROOT = out
    ev = os.path.join(out, "eval")
    argv = ["kh_eval.py", "--out", ev]
    if "--no-render" not in sys.argv:
        argv.append("--turntable")
    argv += ["P28bf=" + os.path.join(cand, PREFIX + ".gwb"), "R4=" + R4_GWB, "Kstar26R01=" + KSTAR_ROWS]
    sys.argv = argv
    KE.main()
    print("deliver done %.0fs" % (time.time() - t0), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
