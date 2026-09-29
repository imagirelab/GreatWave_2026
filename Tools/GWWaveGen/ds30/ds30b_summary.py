# -*- coding: utf-8 -*-
"""設計30 第B部：Unity の単発再生の結果を、最小の受入の項目ごとの表（ds30b_summary.json）にまとめる。

入力（<out> = Unity/Build/Design/30/unity/<名前>）：ds30_render_report.json（DS30Render）、ds30_playback_frames.csv、ds30_holes*.csv、
ds30_tstar_regress.json（ds30b_tstar_regress.py）、playmode/ds30_playmode.csv（DS30PlayModeCheck）、第A部の sea/boat_support.json。
使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/ds30/ds30b_summary.py --out Unity/Build/Design/30/unity/single
"""
import argparse
import csv
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = os.path.join(REPO, a.out)
    r = load(os.path.join(out, "ds30_render_report.json"))
    pb = r["playback"]
    rows = list(csv.DictReader(open(os.path.join(out, "ds30_playback_frames.csv"), encoding="utf-8")))
    names = pb["sheetNames"]
    items = {}
    # 継ぎ目（Unity の GPU の読み戻し。第A部の数値の検査とは別の読み）
    items["seam_hero_near"] = {"max_gap_m": pb["seamHeroNearMaxGap"], "max_dy_m": pb["seamHeroNearMaxDy"], "max_dv_mps": pb["seamHeroNearMaxDv"],
                               "normal_dot_min": pb["seamHeroNearMinDot"], "normal_dot_p01_min": pb["seamHeroNearMinDotP01"], "normal_dot_below05_max": pb["seamHeroNearMaxBelow05"],
                               "side_normal_dot_min": pb.get("seamHeroNearSideMinDot"), "side_normal_dot_p01_min": pb.get("seamHeroNearSideMinDotP01"),
                               "side_below09_max": pb.get("seamHeroNearSideMaxBelow09"), "side_count": pb.get("seamHeroNearSideCount"),
                               "note_ja": "主役波の本体の境の輪（near/ds30_ring0_index.json）と near の行 0。法線は GPU の DS27Normal（主役波は描かない余白の列も含む格子で求める）。輪の両端の錐の点（主役波の行 0・239 の縮んだ列）では法線が決まらず、内積が負になる。side_* は列 18・394 の辺（行 1〜238）だけの値。描画は光を使わない平塗りなので、法線の折れは陰影には出ない（外殻線の押し出しの向きにだけ効く）"}
    items["seam_near_far"] = {"max_gap_m": pb["seamNearFarMaxGap"], "max_dy_m": pb["seamNearFarMaxDy"], "tjunction_max_gap_m": pb["seamNearFarTJunctionMaxGap"],
                              "normal_dot_min": pb["seamNearFarMinDot"], "normal_dot_p01_min": pb["seamNearFarMinDotP01"], "normal_dot_below05_max": pb["seamNearFarMaxBelow05"]}
    # 開始と終了の跳び
    items["start_end"] = {
        "waiting_frames_same_as_t0": pb["waitingFramesSameAsStart"], "holding_frames_same_as_tstar": pb["holdingFramesSameAsTStar"],
        "per_sheet": {n: {"start_step_m": pb["startStep"][i], "median_next30_m": pb["startMedianNext30"][i], "max_next30_m": pb["startMaxNext30"][i],
                          "end_step_m": pb["endStep"][i], "median_prev30_m": pb["endMedianPrev30"][i], "max_prev30_m": pb["endMaxPrev30"][i],
                          "hold_max_step_m": pb["holdMaxStep"][i], "play_max_step_m": pb["playMaxStep"][i]} for i, n in enumerate(names)},
        "pass": pb["waitingFramesSameAsStart"] and pb["holdingFramesSameAsTStar"] and all(
            pb["startStep"][i] <= 1.5 * pb["startMaxNext30"][i] + 1e-6 and pb["endStep"][i] <= 1.5 * pb["endMaxPrev30"][i] + 1e-6 and pb["holdMaxStep"][i] == 0 for i in range(len(names))),
        "rule_ja": "待機のコマは t = 0 のコマと頂点の SHA-256 が同じ、静止のコマは t* のコマと同じ、開始の最初の 1 コマの最大の動きは続く 30 コマの最大の 1.5 倍以内、t* へ入るコマは前の 30 コマの最大の 1.5 倍以内（進行役の判断の目安）"}
    items["jitter"] = {"ticks": pb["jitterTicks"], "max_dt_s": pb["jitterMaxDt"], "max_dtau_s": pb["jitterMaxDTau"], "max_step_s": pb["maxStepSeconds"], "end_tau": pb["jitterEndTau"]}
    # 座席の目
    b = load(os.path.join(REPO, "Unity", "Build", "Design", "30", "sea", "boat_support.json")) if r.get("boat") and r["boat"].get("path") else None
    items["seat_eye"] = {"under_water_frames": pb["eyeUnderWaterFrames"], "min_clearance_m": pb["eyeMinClearance"], "min_clearance_t": pb["eyeMinClearanceT"],
                         "frames": len(rows), "boat_support": r.get("boat"), "part_a_summary": b["summary"] if b else None,
                         "pass": pb["eyeUnderWaterFrames"] == 0}
    # 穴
    items["holes"] = {k: r.get(k) for k in ("holes", "holesNoFlat")}
    items["holes"]["pass"] = r["holes"]["seatWorstHolePx"] == 0 and r["holes"]["paintingWorstHolePx"] == 0
    # t* の回帰
    rg = os.path.join(out, "ds30_tstar_regress.json")
    if os.path.exists(rg):
        g = load(rg)
        s = g["sets"].get("t28_seaids", {})
        items["tstar_regression"] = {
            "ctrl_identical_to_29r01": g.get("ctrl_identical_to_29r01_f_final_kp", {}).get("all"),
            "seaids": {"silhouette_diff_vs_29r01_px": s.get("silhouette_diff_vs_29r01_px"), "lfgate": s.get("lfgate"), "lfgate_diff_vs_29r01_px": s.get("lfgate_diff_vs_29r01_px"),
                       "colour_definition_worst_px": s.get("verdict", {}).get("colour_worst_abs_diff_px"), "sym_worst_px": s.get("sym", {}).get("worst_abs_diff_px"),
                       "sym_worst_diff_vs_29r01_px": s.get("sym", {}).get("worst_diff_vs_29r01_px")},
            "base_29r01": g.get("base_29r01"),
            "pass": bool(s) and max(abs(v) for v in s["silhouette_diff_vs_29r01_px"].values()) <= 0.5 and max(abs(v) for v in s["lfgate_diff_vs_29r01_px"].values()) <= 0.5
                    and s.get("sym", {}).get("worst_diff_vs_29r01_px", 9) <= 0.5}
    # Play モード
    pm = os.path.join(out, "playmode", "ds30_playmode.csv")
    if os.path.exists(pm):
        pr = list(csv.DictReader(open(pm, encoding="utf-8")))
        ts = [float(x["t"]) for x in pr]
        items["play_mode"] = {"frames": len(pr), "states": {s: sum(1 for x in pr if x["state"] == s) for s in ("Waiting", "Playing", "Holding")},
                              "t_monotonic": all(q >= p for p, q in zip(ts, ts[1:])), "t_last": ts[-1] if ts else None,
                              "all_sheets_same_tau": all(len(set(x["sheet_tau"].split(";"))) == 1 and x["sheet_tau"].split(";")[0] == x["tau"] for x in pr),
                              "end": open(os.path.join(out, "playmode", "ds30_playmode_end.txt"), encoding="utf-8").read().strip()}
        pmi = items["play_mode"]
        pmi["pass"] = pmi["t_monotonic"] and pmi["all_sheets_same_tau"] and pmi["states"]["Holding"] > 0 and abs(pmi["t_last"] - 12.0) < 1e-6
    res = {"schema": "GreatWave.DS30B.summary/1", "number": "設計30 第B部", "out": a.out, "render_report_sha256": sha256(os.path.join(out, "ds30_render_report.json")),
           "sheets": [{k: s[k] for k in ("name", "rows", "cols", "layers", "jsonSha256", "posSha256", "posLoSha256", "posLoFromPackage", "positionGpuBytes", "posLoGpuBytes", "whiteGpuBytes", "uv3Source")} for s in r["sheets"]],
           "gpu_bytes_sheets": r["gpuBytesSheets"], "gpu_mib_sheets": round(r["gpuBytesSheets"] / 2 ** 20, 2), "knot_tau_same": r["knotTauSame"], "frame_same": r["frameSame"],
           "hidden_context": r["hidden"], "flat_sea": {"mode": r["flatSeaMode"], "top_y": r["flatSeaY"]}, "curtain": r.get("curtain"), "attached_foam": r.get("attachedFoam"),
           "videos": r["videos"], "items": items, "protected_unchanged": r["protectedUnchanged"], "scene": {"path": r["scenePath"], "sha256": r["sceneSha256"]}}
    with open(os.path.join(out, "ds30b_summary.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=float)
        f.write("\n")
    print(json.dumps({k: (v.get("pass") if isinstance(v, dict) else v) for k, v in items.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
