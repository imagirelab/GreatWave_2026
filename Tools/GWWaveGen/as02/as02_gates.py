# -*- coding: utf-8 -*-
"""美術の見本02 爪の部：原画視点の形の関門（78・130・131・132・72）を、仕上げ28 の pl28u_regress.py と同じ関数で読む包み。
pl28u_regress.py は色の項目 267 の「白の帯」の値が無い（None）と止まる（この見本の爪は少なく、ある視点で白の帯が測れない）。
形の関門だけが要るので、267 の帯の読みを None のまま通す strict_summary の写しを使い、対称の読み（sym）は省く。共有の道具は書き換えない。
出力は pl28u_regress.py と同じ書式の <scene>/pl28u_regress.json（sets の t28_white・t28_claws）。sweep_gates.py がそのまま読む。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as02/as02_gates.py --scene Unity/Build/Polish/sample02/claws/render/A_final
"""
import argparse
import json
import os
import subprocess
import sys

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl28")
import pl28u_regress as R  # noqa: E402


def strict_summary_safe(run, verdict_name):
    v = R.load(os.path.join(run, verdict_name))
    rr = R.load(os.path.join(run, "ds27_tstar_remeasure.json"))
    c = rr["colour_265_266_267"]

    def bands(vw):
        try:
            return c["267"]["ds27"]["views"]["white"][vw]["bands_ge_20px"]
        except (TypeError, KeyError):
            return None
    col = {"265_dE00": (c["265"]["ds27"] or {}).get("dE00") if c["265"].get("ds27") else None, "265": c["265"]["ds27_verdict"],
           "266": c["266"]["ds27_verdict"], "267": c["267"]["ds27_verdict"],
           "267_bands_ge_20px": {vw: bands(vw) for vw in ("painting_view", "seat_view", "seat_low_view")}}
    sil = {s["item"]: {"max_px": s["ds27_max_px"], "p95_px": s["ds27_p95_px"]} for s in rr["silhouettes_vs_26r01_28r01"]}
    return {"colour_265_267": col, "silhouettes_definition_reading": sil, "silhouettes_vs_kstar_prime_geometry": v["silhouettes_vs_kstar_prime"],
            "pass_colour": v["pass_colour"], "pass_silhouette": v["pass_silhouette"], "summary_verdicts": rr.get("summary_verdicts_ds27")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--kstar", default="rec")
    a = ap.parse_args()
    scene = os.path.join(REPO, a.scene) if not os.path.isabs(a.scene) else a.scene
    res = {"schema": "GreatWave.Polish28.tstar_regress/1", "number": "美術の見本02（形の関門だけ。as02_gates.py）", "scene": a.scene, "kstar": a.kstar,
           "method_ja": __doc__.strip(), "sets": {}}
    for s in ("t28_white", "t28_claws"):
        run = os.path.join(scene, s)
        if not os.path.isdir(os.path.join(run, "t28", "render")):
            print("skip", s)
            continue
        rel = os.path.relpath(run, REPO).replace("\\", "/")
        if not os.path.exists(os.path.join(run, "pl28u_tstar_verdict.json")):
            subprocess.run([sys.executable, "-B", os.path.join(REPO, "Tools/GWWaveGen/pl28/pl28u_tstar_eval.py"), "--run", rel, "--kstar", a.kstar],
                           check=True, cwd=REPO)
        e = {"strict": strict_summary_safe(run, "pl28u_tstar_verdict.json"), "large_form": R.lfgates(run)}
        res["sets"][s] = e
        print(s, json.dumps({"lf": e["large_form"]["s12"], "sil": e["strict"]["silhouettes_definition_reading"]}, ensure_ascii=False)[:700], flush=True)
    with open(os.path.join(scene, "pl28u_regress.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=float)
    print("AS02_GATES_DONE", a.scene)


if __name__ == "__main__":
    main()
