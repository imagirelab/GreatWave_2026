# -*- coding: utf-8 -*-
"""設計40 第「比較」部：実行の記録（ds40_run.json）。コマンド、コードと入力・出力の SHA-256、時刻を書く。

使い方（リポジトリの根で）: py -3.10 -B Tools/GWWaveGen/ds40/ds40_run_record.py
出力：Unity/Build/Design/40/compare/ds40_run.json
"""
import datetime
import hashlib
import json
import os
import platform
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(REPO, "Unity", "Build", "Design", "40", "compare")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def mtime(p):
    return datetime.datetime.fromtimestamp(os.path.getmtime(p)).isoformat(timespec="seconds") if os.path.exists(p) else None


def main():
    code = ["Unity/Assets/GreatWave/Design40/Editor/DS40Render.cs", "Tools/GWWaveGen/ds40/run_ds40_unity.ps1", "Tools/GWWaveGen/ds40/ds40_compare.py",
            "Tools/GWWaveGen/ds40/ds40_run_record.py", "Tools/PaintingTruth/evaluate.py", "Tools/PaintingTruth/truthlib.py",
            "Tools/GWWaveGen/ds30/ds30b_tstar_regress.py", "Tools/GWWaveGen/ds29r01/ds29r01_tstar_eval.py", "Tools/GWWaveGen/ds29r01/ds29r01_tstar_sym.py"]
    inputs = ["Unity/Assets/GreatWave/Design39/Scenes/DS39_Paper.unity", "Unity/Build/Design/30/ref/ds30_ref_layout.json", "Docs/Evidence/Design/30/ds30_layout_record.json",
              "Docs/Evidence/Design/30/fig_ds30_layout_plan.png", "Docs/Evidence/ArtFirst/CP1/metrics.json", "Tools/GWContext/seat_v1.json",
              "Unity/Build/Design/28R01F/kstar_final/kstarR4_a45_meta.json", "Unity/Build/Design/28R01F/kstar_final/kstarR4_a45_rows.npz",
              "Unity/Build/Design/39/paper/unity/ds30_tstar_regress.json", "Unity/Build/Design/39/paper/unity/onoff/ds39_painting_t120_off.png"]
    outs = []
    for root, _, fs in os.walk(OUT):
        for f in fs:
            p = os.path.join(root, f)
            if f.endswith((".json", ".png", ".txt")) and "logs" not in rel(p).split("/"):
                outs.append(p)
    rec = {
        "schema": "GreatWave.DS40.run/1", "number": "設計40 第「比較」部", "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "machine": {"python": sys.version.split()[0], "numpy": np.__version__, "opencv": cv2.__version__, "platform": platform.platform()},
        "evidence_kind_ja": "Unity 6000.4.3f1 Editor の batchmode の PC オフスクリーン描画と numpy・OpenCV の測定。HMD 実機の結果ではない。git は使っていない。",
        "commands": [
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds40/run_ds40_unity.ps1 -Method GreatWave.Design40.EditorTools.DS40Render.Render -Log render（約 20 s、描画 11.8 s）",
            "py -3.10 -B Tools/GWWaveGen/ds30/ds30b_tstar_regress.py --out Unity/Build/Design/40/compare/unity --sets t28_claws,t28_white（3 分 20 秒）",
            "py -3.10 -B Tools/GWWaveGen/ds40/ds40_compare.py（評価器23 を 5 回、約 45 秒。--skip-eval で評価器の出力を読み直して図と表だけ作る）",
            "py -3.10 -B Tools/GWWaveGen/ds40/ds40_run_record.py"],
        "code_sha256": {c: sha(os.path.join(REPO, c)) for c in code if os.path.exists(os.path.join(REPO, c))},
        "inputs_sha256": {c: sha(os.path.join(REPO, c)) for c in inputs if os.path.exists(os.path.join(REPO, c))},
        "outputs_sha256": {rel(p): sha(p) for p in sorted(outs)},
        "time": {"started": open(os.path.join(OUT, "_started.txt"), encoding="utf-8").read().strip(),
                 "unity_report": mtime(os.path.join(OUT, "unity", "ds40_render_report.json")),
                 "regress_output": mtime(os.path.join(OUT, "unity", "ds30_tstar_regress.json")),
                 "compare_metrics": mtime(os.path.join(OUT, "ds40_compare_metrics.json"))},
        "not_used_ja": "参照モデルの OBJ（設計30 が測った数値の JSON だけを読んだ）、利用者の解算、写真のフォルダー、爪形分析のフォルダー、Blender、Houdini。",
    }
    with open(os.path.join(OUT, "ds40_run.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("outputs", len(outs))


if __name__ == "__main__":
    main()
