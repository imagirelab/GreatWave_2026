# -*- coding: utf-8 -*-
"""仕上げ29（Q28）の前の点検（AUDIT）の証拠をまとめる：metrics_audit.json・run_audit.json と図の写しを Docs/Evidence/Polish/29/ へ書く。

入力：<before>/p28（今の採用）と <before>/stage9（設計50 DS50_Release と同じファイルの状態。あれば）の pl29_audit_report.json・audit/audit_metrics.json、
F7-1 の数え（<before>/p28_f71/count_pngseq.json。あれば）、図（<before>/sheets）。
数値の判定はしない（前の基準の記録のみ）。仕上げ29 の項目（計画 §5.3）ごとに、この点検でどう見えたかを書く。
使い方：py -3.10 -B Tools/GWWaveGen/pl29/pl29_audit_record.py --before <dir> --evidence <Docs/Evidence/Polish/29>
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import sys
import time

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
VIEWS = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
TIMES = ["t060", "t090", "t105", "t120"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def compact(r):
    if not r.get("heroPx"):
        return {"heroPx": 0}
    return {
        "heroPx": r["heroPx"], "directFrac": round(r["directFrac"], 4), "bandFrac": round(r["bandFrac"], 4), "flatFillFrac": round(r["flatFillFrac"], 4),
        "stretchFracOfHero": round(r["stretch"]["stretchFracOfHero"], 4), "stretchFracOfDirectValid": round(r["stretch"]["stretchFracOfValid"], 4),
        "anisoP50": None if r["stretch"]["anisoP50"] is None else round(r["stretch"]["anisoP50"], 2),
        "seamSegments": r["seam"]["seamSegments"], "seamSegmentsLong": r["seam"]["seamSegmentsLong"], "seamPx": r["seam"]["seamPx"],
        "bandEdgePx": r["seam"]["bandEdgePx"], "paintingEdgePx": r["seam"]["paintingEdgePx"],
        "flatRegions": r["flat"]["regions"], "flatRegionsFromFill": r["flat"]["regionsFromFill"], "flatCoreFracOfHero": round(r["flat"]["coreFracOfHero"], 4),
        "bands": r["band"]["bands"], "uFillPx": r["band"]["uFillPx"], "vFillPx": r["band"]["vFillPx"],
        "clawPieces": r["claws"]["clawPieces"], "clawPiecesMeltedId": r["claws"]["clawPiecesMelted"], "clawPiecesMeltedColour": r["claws"]["clawPiecesMeltedColour"],
        "clawMeltedEdgeFrac": round(r["claws"]["meltedEdgeFrac"], 4), "clawWhiteOnWhiteFrac": round(r["claws"]["whiteOnWhiteFrac"], 4),
    }


def rnd(d):
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}


def region_bbox(before, view, t, key):
    """maps の npz から、その種類の画素の外接枠と数（項目の場所を書くため）。"""
    p = os.path.join(before, "audit", f"maps_{view}_{t}.npz")
    m = np.load(p)
    a = m[key]
    ys, xs = np.nonzero(a)
    if xs.size == 0:
        return None
    return {"px": int(xs.size), "bbox_xyxy": [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]}


def painting_regions(p28, cat_path):
    """原画視点 t* の外挿・平らな塗りの画素を、焼き込みの原画の範囲（画面の x 157〜1762）の外と内に分けて数える。"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import pl29_audit_measure as M
    cat = np.fromfile(cat_path, np.uint8)
    hero, u, v = M.decode_uv(os.path.join(p28, "diag", "painting_t120_uv_claws0.png"))
    c = np.zeros(hero.shape, np.uint8)
    c[hero] = cat[v[hero] * 4096 + u[hero]]
    xs = np.arange(hero.shape[1])[None, :]
    out = {}
    for name, ks in (("uFill", (3, 9)), ("vFill", (4, 10)), ("flatFill", (2, 5, 8))):
        m = hero & np.isin(c, ks)
        for part, sel in (("outsideLeft", xs < 157), ("inside", (xs >= 157) & (xs < 1762)), ("outsideRight", xs >= 1762)):
            mm = m & sel
            if mm.any():
                yy, xx = np.nonzero(mm)
                out[f"{name}_{part}"] = {"px": int(mm.sum()), "bbox_xyxy": [int(xx.min()), int(yy.min()), int(xx.max()) + 1, int(yy.max()) + 1],
                                         "yP5P50P95": [int(x) for x in np.percentile(yy, [5, 50, 95])]}
    return out


# 目で見た所見（進行役の自己評審の前の、作り手の目視。fig_pl29a_before_*・turntable_*・crops_* を見て書いた）
BY_EYE = {
    "painting": "t* は原画に似る。原画の枠の外（左端 x < 157）の主役波が横縞の帯になる。白い立体の爪は原画から焼いた白の泡の上に重なって見えない。t 6・9 s は形が K* と違うので、焼いた模様が形とずれ、平らな藍濃が多い（平らな塗り 73%・41%）。",
    "seat": "t 6 s は主役波が画面の外。t 10.5・12 s は内壁の大半が平らな藍濃の一色の壁。唇は白と藍の四角が段になる梯子（引き伸ばしと帯）。爪は空を背にした所では読める。",
    "seat_toward_wave": "下半分が平らな藍濃の壁。波頭の下に縦の縞（v 方向の帯の境）、左に横の縞（u 方向の帯）。t 12 s で暗い藍の面を横切る細い線（外殻線）。",
    "side_left": "ほぼ全部が外挿の帯：波の長さに沿った平行な縞と、白い頂の平らな塊。原画の模様（波頭の爪・泡）は唇の小さな所にだけ残り、引き伸ばされる。",
    "side_right": "帯と平らな塗りだけ。巻きの内側が一色。原画の模様はほとんどない（直接 0.8%）。",
    "back65": "原画の模様が一つもない（直接 0.02%）。ドームが白の広い面と縦の縞の帯だけで塗られる。",
    "top": "帯と平らな塗りが大半。唇の先の小さな所だけ原画の模様が引き伸ばされて見える。",
    "turntable": "原画視点の近く（az 0〜30°）でも直接は 22〜26%。az 150〜270° は直接 0〜7% で、白の面と縞の帯だけ。",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--evidence", required=True)
    a = ap.parse_args()
    B = a.before
    ev = a.evidence
    os.makedirs(ev, exist_ok=True)
    p28 = os.path.join(B, "p28")
    m = json.load(open(os.path.join(p28, "audit", "audit_metrics.json"), encoding="utf-8"))
    rep = json.load(open(os.path.join(p28, "pl29_audit_report.json"), encoding="utf-8-sig"))
    st9 = os.path.join(B, "stage9")
    m9 = json.load(open(os.path.join(st9, "audit", "audit_metrics.json"), encoding="utf-8")) if os.path.exists(os.path.join(st9, "audit", "audit_metrics.json")) else None
    rep9 = json.load(open(os.path.join(st9, "pl29_audit_report.json"), encoding="utf-8-sig")) if os.path.exists(os.path.join(st9, "pl29_audit_report.json")) else None
    f71p = os.path.join(B, "p28_f71", "count_pngseq.json")
    f71 = json.load(open(f71p, encoding="utf-8")) if os.path.exists(f71p) else None
    bake_entry = json.load(open(os.path.join(REPO, "Unity/Build/Polish/28/unity/bake_rec/ds29r01_bake_entry.json"), encoding="utf-8-sig"))

    preg = painting_regions(p28, m["catFile"])
    comps = json.load(open(os.path.join(p28, "audit", "components.json"), encoding="utf-8"))
    cat_counts = {}
    for c in comps:
        k = c["kind"] if c["kind"] != "claw" else ("claw_melted" if (c.get("melted") or c.get("meltedColour")) else "claw_ok")
        cat_counts.setdefault(k, {}).setdefault(c["view"], {}).setdefault(c["t"], 0)
        cat_counts[k][c["view"]][c["t"]] += 1
    shutil.copyfile(os.path.join(p28, "audit", "components.json"), os.path.join(ev, "catalogue_audit.json"))
    # 原画カメラが焼き込みのカメラと同じか（位置と向き）
    cp, cf = rep["paintingCamPos"], rep["paintingCamForward"]
    bp, bf = bake_entry["cameraPosition"], bake_entry["cameraForward"]
    cam_check = {"renderCamPos": cp, "bakeCamPos": bp, "renderCamForward": cf, "bakeCamForward": bf,
                 "posDiffM": float(np.linalg.norm(np.array([cp["x"] - bp["x"], cp["y"] - bp["y"], cp["z"] - bp["z"]]))),
                 "forwardDiff": float(np.linalg.norm(np.array([cf["x"] - bf["x"], cf["y"] - bf["y"], cf["z"] - bf["z"]]))),
                 "fov": [rep["paintingFov"], bake_entry["fov"]]}

    s = m["summaryByView"]
    v = m["views"]
    items = [
        {"item": "［利用者の言葉］Q28 原画カメラからの投影の焼き込み（視点を変えると露馅）", "where": "原画視点の外の 7 視点＋回り台 48 枚",
         "beforeJa": f"原画視点の外では、主役波の見える画素のうち原画カメラからの投影（直接）は {m['summaryNonPainting']['directFrac']*100:.1f}% だけ。"
                     f"外挿の帯 {m['summaryNonPainting']['bandFrac']*100:.1f}%、平らな塗り {m['summaryNonPainting']['flatFillFrac']*100:.1f}%。直接のうちでも斜めに読んで引き伸ばされた所が主役波の {m['summaryNonPainting']['stretchFracOfHero']*100:.1f}%。"
                     f"後ろ 65° は直接 {s['back65']['directFrac']*100:.2f}%（帯 {s['back65']['bandFrac']*100:.1f}%）、左の側面 {s['side_left']['directFrac']*100:.1f}%、右の側面 {s['side_right']['directFrac']*100:.1f}%。",
         "present": True},
        {"item": "［利用者の言葉］Q16 F7-1 の描画の側（t 9〜11.5 s の波頭の模様の 1 コマの揺れ）", "where": "原画視点 30 fps のコマ 264〜351（無圧縮の PNG。爪なし・飛沫なし・線あり）",
         "beforeJa": (f"M1b（色面の跳び）窓 270〜345 の合計 {f71['windows_video_frames']['270_345']['M1b_sum_px']:,} 画素・1 コマの最大 {f71['windows_video_frames']['270_345']['M1b_max_px']:,} 画素"
                      f"（仕上げ28 の G_p28b・DS29Render の数え 52,266／1,587。場面と爪の扱いが違うので並べるだけ）。" if f71 else "数えていない"),
         "present": bool(f71 and f71["windows_video_frames"]["270_345"]["M1b_sum_px"] > 0)},
        {"item": "色の焼き込みの傷：唇の端の梯子・モアレ", "where": "座席・座席から波の方向の唇（t 10.5・12 s）",
         "beforeJa": f"唇の白と藍の交互の四角の段（引き伸ばしと帯）。座席 t 12 s の引き伸ばし {v['seat_t120']['stretch']['stretchFracOfHero']*100:.1f}%（直接のうち {v['seat_t120']['stretch']['stretchFracOfValid']*100:.0f}%）、"
                     f"座席から波の方向 t 12 s {v['seat_toward_wave_t120']['stretch']['stretchFracOfHero']*100:.1f}%。切り抜き fig_pl29a_crops_stretch.png の上段。",
         "present": True},
        {"item": "色の焼き込みの傷：縦の継ぎ目", "where": "座席から波の方向（唇の下の縦の縞）・後ろ 65°",
         "beforeJa": f"v 方向の外挿（縞・画面外）の帯の境が縦の線になる。帯の境の画素：座席から波の方向 t 10.5 s {v['seat_toward_wave_t105']['seam']['bandEdgePx']:,}・t 12 s {v['seat_toward_wave_t120']['seam']['bandEdgePx']:,}、"
                     f"後ろ 65° t 12 s {v['back65_t120']['seam']['bandEdgePx']:,}。",
         "present": True},
        {"item": "色の焼き込みの傷：前面の足の縦の筋", "where": "原画視点 t* の原画の枠の内（x 157〜1762）の下の方",
         "beforeJa": f"原画視点 t* でも主役波の画素の {v['painting_t120']['bandFrac']*100:.1f}% が外挿の帯、{v['painting_t120']['flatFillFrac']*100:.1f}% が平らな塗り。"
                     f"原画の枠の内では u 方向の帯（原画の遮蔽物＝船などの陰を同じ行の色で埋めた所）{preg.get('uFill_inside', {}).get('px', 0):,} 画素（y {preg.get('uFill_inside', {}).get('yP5P50P95')}）と、"
                     f"足の平らな塗り（海面の藍濃など）{preg.get('flatFill_inside', {}).get('px', 0):,} 画素（y {preg.get('flatFill_inside', {}).get('yP5P50P95')}）。",
         "present": True, "regions": {k: preg[k] for k in preg if k.endswith("inside")}},
        {"item": "色の焼き込みの傷：原画視点の左端の横縞", "where": "原画視点の左端（焼き込みの原画の範囲 x 157〜1762 の外。af28_bake_meta の scoredX0・X1）",
         "beforeJa": f"原画の枠の外の主役波は v 方向の帯（縞・画面外）で埋まる：{preg.get('vFill_outsideLeft', {}).get('px', 0):,} 画素（外接枠 {preg.get('vFill_outsideLeft', {}).get('bbox_xyxy')}）"
                     f"と平らな塗り {preg.get('flatFill_outsideLeft', {}).get('px', 0):,} 画素。fig_pl29a_before_t120.png の原画視点の診断の左端の紫。",
         "present": True, "regions": {k: preg[k] for k in preg if "outside" in k}},
        {"item": "座席から波の方向のコマ 330〜420 の、継ぎ目に沿う線が暗い海を横切る", "where": "座席から波の方向 t 12 s（コマ 360）",
         "beforeJa": "目で見える：暗い藍の面を左から右へ横切る細い灰の線（設計38 の外殻線。投影の色ではなく線の印の側）。この点検の数（線なしの診断）には入らない。", "present": True},
        {"item": "座席の見えない内壁の平らな藍濃", "where": "座席・座席から波の方向（t 10.5・12 s）",
         "beforeJa": f"平らな塗り（内側の藍濃・海面の藍濃）が座席で {s['seat']['flatFillFrac']*100:.1f}%、座席から波の方向で {s['seat_toward_wave']['flatFillFrac']*100:.1f}%。"
                     f"色の境から 48 px より遠い芯が主役波の {s['seat']['flatCoreFracOfHero']*100:.1f}%・{s['seat_toward_wave']['flatCoreFracOfHero']*100:.1f}%（原画視点 {s['painting']['flatCoreFracOfHero']*100:.1f}%）。"
                     f"平らな面の成分 {s['seat']['flatRegions']}・{s['seat_toward_wave']['flatRegions']}。",
         "present": True},
        {"item": "左の横の外挿の帯", "where": "左の側面・右の側面・後ろ 65°・真上",
         "beforeJa": f"外挿の帯が左の側面 {s['side_left']['bandFrac']*100:.1f}%・右の側面 {s['side_right']['bandFrac']*100:.1f}%・後ろ 65° {s['back65']['bandFrac']*100:.1f}%・真上 {s['top']['bandFrac']*100:.1f}%。",
         "present": True},
        {"item": "立体の爪が焼き込みの模様に溶ける", "where": "原画視点・座席・座席から波の方向・回り台",
         "beforeJa": f"爪が主役波を隠す成分（≥ 40 px）のうち、縁の 80% 以上が後ろと同じ色区（線なしの ID）：原画視点 {s['painting']['clawPiecesMelted']}/{s['painting']['clawPieces']}、"
                     f"座席 {s['seat']['clawPiecesMelted']}/{s['seat']['clawPieces']}、座席から波の方向 {s['seat_toward_wave']['clawPiecesMelted']}/{s['seat_toward_wave']['clawPieces']}、"
                     f"回り台 {s['turntable']['clawPiecesMelted']}/{s['turntable']['clawPieces']}。作品のまま（線あり）でも輪の対比が 30% 未満：原画視点 {s['painting']['clawPiecesMeltedColour']}、"
                     f"原画視点の外 {m['summaryNonPainting']['clawPiecesMeltedColour']}。原画視点 t* では白い立体の爪が原画から焼いた白の泡の上に重なり、輪郭も線もなく見えない（fig_pl29a_crops_claw.png）。",
         "present": True},
        {"item": "行 234〜239 の張り直し", "where": "—", "beforeJa": "形の項目で HMD で見えた時だけ行う（計画 §5.3）。この点検では扱わない。", "present": None},
        {"item": "軽量版の作り直し（UV3 の表 af28r01_uvwarp_a45.json）", "where": "—", "beforeJa": "この点検では扱わない（新しい材質の後に作り直す）。", "present": None},
    ]
    out = {
        "group": "仕上げ29", "part": "AUDIT（前の点検。前後の図の「前」）", "dateLocal": time.strftime("%Y-%m-%d %H:%M"),
        "noteJa": "今の採用の状態（仕上げ28 の K*′ P28R2rec・動き G_p28rec・29修正01 の焼き込みを P28R2rec へ焼き直した bake_rec）を Unity の PC 描画で、"
                  "原画視点・座席・座席から波の方向・左の側面・右の側面・後ろ 65°・真上と回り台 12 方位から t 6・9・10.5・12 s で描き、"
                  "診断の描画（主役波の UV3 のテクセル・K* の原画カメラへの投影・色区の ID）から、焼き込みのテクセルのカテゴリと引き伸ばし・継ぎ目・平らな面・外挿の帯・溶けた爪を数えた。"
                  "判定はしない（前の基準の記録のみ）。閾値は進行役の判断（Q24）。HMD 実機ではない。座席 t 6 s は主役波が画面の外。",
        "state": {"heroPackage": rep["heroPackage"], "heroPackageJsonSha256": rep["heroPackageJsonSha256"], "heroMeshGwb": rep["heroMeshGwb"], "heroMeshSha256": rep["heroMeshSha256"],
                  "heroSdf": rep["heroSdf"], "heroSdfSha256": rep["heroSdfSha256"], "heroUvWarp": rep["heroUvWarp"], "heroUvWarpSha256": rep["heroUvWarpSha256"],
                  "timewarp": rep["timewarp"], "timewarpSha256": rep["timewarpSha256"], "scene": rep["scene"], "sceneSha256": rep["sceneSha256"],
                  "uvcat": m["catFile"], "uvcatSha256": m["catSha256"]},
        "experienceSceneNoteJa": "設計50 の DS50_Release.unity（と DS39_Paper.unity）の主役波は、まだ段階9 の状態（Build/Design/31/white/hero_pkg・Build/Design/29R01/bake_kp・timewarp_F_final）を指す。"
                                 "仕上げ28 の採用（P28R2rec・G_p28rec）はこの点検の描画で差し替えただけで、場面へは入っていない。下の stage9 はその状態の同じ点検。",
        "thresholds": m["thresholds"], "identityCheckPaintingT120": m["identityCheckPaintingT120"], "paintingCameraVsBake": cam_check,
        "uvTexelCategoryFrac": {k: round(x, 4) for k, x in m["uvTexelCategoryFrac"].items()},
        "summaryNonPainting": rnd(m["summaryNonPainting"]), "summaryPainting": rnd(m["summaryPainting"]),
        "summaryByView": {k: rnd(x) for k, x in m["summaryByView"].items()}, "summaryByTime": {k: rnd(x) for k, x in m["summaryByTime"].items()},
        "perImage": {k: compact(r) for k, r in m["views"].items()}, "perTurntable": {k: compact(r) for k, r in m["tt"].items()},
        "f71": None if not f71 else {"windows": f71["windows_video_frames"], "all_M1b": f71["all"]["M1b_fill_flicker"], "all_M1": {k: f71["all"]["M1_colour_flicker"][k] for k in ("max_px", "sum_px", "frames_over_50px")},
                                     "info": f71["info"], "noteJa": "PL29Audit の原画視点（DS39_Paper、爪なし・飛沫なし・線あり、無圧縮の PNG 88 枚）を pl28_f71_count.py --kind pngseq で数えた（段階7確認と同じ数え方）。"},
        "items": items,
        "catalogueCounts": cat_counts,
        "catalogueFile": "Docs/Evidence/Polish/29/catalogue_audit.json",
        "byEyeJa": BY_EYE,
        "judgementJa": "記録のみ（前の基準）。閉じる目安は新しい材質の後に同じ視点・同じ時刻・同じ数え方で比べる。",
    }
    if m9:
        out["stage9"] = {"noteJa": "段階9 の状態（DS50_Release と同じファイル：K*′ R4・F_final・29修正01 の焼き込み bake_kp）を同じ道具で描いて数えたもの（参考）。",
                         "heroSdfSha256": rep9["heroSdfSha256"] if rep9 else None, "uvcatSha256": m9["catSha256"],
                         "uvTexelCategoryFrac": {k: round(x, 4) for k, x in m9["uvTexelCategoryFrac"].items()},
                         "summaryNonPainting": rnd(m9["summaryNonPainting"]), "summaryPainting": rnd(m9["summaryPainting"]),
                         "summaryByView": {k: rnd(x) for k, x in m9["summaryByView"].items()}}
    with open(os.path.join(ev, "metrics_audit.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    # 図の写し
    sheets = sorted(f for f in os.listdir(os.path.join(B, "sheets")) if f.endswith(".png"))
    figs = []
    for f in sheets:
        dst = os.path.join(ev, f)
        shutil.copyfile(os.path.join(B, "sheets", f), dst)
        figs.append({"file": rel(dst), "sha256": sha(dst), "bytes": os.path.getsize(dst)})
    import PIL
    import scipy
    import cv2
    run = {
        "group": "仕上げ29", "part": "AUDIT", "dateLocal": time.strftime("%Y-%m-%d %H:%M"),
        "commands": [
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/pl29/run_pl29_unity.ps1 -Method GreatWave.Polish29.EditorTools.PL29Audit.Render -Log audit_before_p28 -Extra \"-pl29State p28 -pl29Out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/29/before/p28\"",
            "powershell … run_pl29_unity.ps1 -Method GreatWave.Polish29.EditorTools.PL29Audit.Render -Log audit_before_stage9 -Extra \"-pl29State stage9 -pl29Out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/29/before/stage9\"",
            "powershell … run_pl29_unity.ps1 -Method GreatWave.Polish29.EditorTools.PL29Audit.Render -Log audit_before_p28_f71 -Extra \"-pl29State p28 -pl29Out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/29/before/p28_f71 -pl29Skip views,tt -pl29Times 12 -pl29F71 264,351\"",
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_audit_measure.py --before G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/29/before/p28 --cat G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/28/unity/bake_rec/bake/af28r01_uvcat_a45.bin --out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/29/before/p28/audit",
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_audit_measure.py --before G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/29/before/stage9 --cat G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/29R01/bake_kp/bake/af28r01_uvcat_a45.bin --out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/29/before/stage9/audit",
            "py -3.10 -B Tools/GWWaveGen/pl28/pl28_f71_count.py --kind pngseq --src Unity/Build/Polish/29/before/p28_f71/f71 --glob \"painting_f*.png\" --first 264 --name p28rec_pl29 --out Unity/Build/Polish/29/before/p28_f71/count_pngseq.json --win 270,345 --win 265,269 --win 346,350",
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_audit_sheets.py --before G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/29/before/p28 --out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/29/before/sheets",
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_audit_record.py --before G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/29/before --evidence G:/Unity/GreatWave_2026_Fresh/Docs/Evidence/Polish/29",
        ],
        "tools": {"unity": rep["unity"], "device": rep["device"], "graphicsApi": rep["graphicsApi"], "colorSpace": rep["colorSpace"], "python": sys.version.split()[0],
                  "platform": platform.platform(), "numpy": np.__version__, "pillow": PIL.__version__, "scipy": scipy.__version__, "opencv": cv2.__version__},
        "code": {f: sha(os.path.join(REPO, f)) for f in ["Unity/Assets/GreatWave/Polish29/Editor/PL29Audit.cs", "Unity/Assets/GreatWave/Polish29/Shaders/PL29_HeroDiag.shader",
                                                          "Tools/GWWaveGen/pl29/run_pl29_unity.ps1", "Tools/GWWaveGen/pl29/pl29_audit_measure.py",
                                                          "Tools/GWWaveGen/pl29/pl29_audit_sheets.py", "Tools/GWWaveGen/pl29/pl29_audit_record.py",
                                                          "Tools/GWWaveGen/pl28/pl28_f71_count.py", "Tools/GWWaveGen/pl28/pl28_s7_video.py"]},
        "inputs": out["state"],
        "unityReport": {"p28": {"path": rel(os.path.join(p28, "pl29_audit_report.json")), "sha256": sha(os.path.join(p28, "pl29_audit_report.json")), "images": len(rep["images"]),
                                "secondsTotal": rep["secondsTotal"], "protectedUnchanged": rep["protectedUnchanged"], "changedFiles": rep["changedFiles"]}},
        "outputsHeavy": {"before_p28": rel(p28), "before_stage9": rel(st9), "f71_frames": rel(os.path.join(B, "p28_f71", "f71")),
                         "audit_metrics_full": {"path": rel(os.path.join(p28, "audit", "audit_metrics.json")), "sha256": sha(os.path.join(p28, "audit", "audit_metrics.json"))},
                         "components": {"path": rel(os.path.join(p28, "audit", "components.json")), "sha256": sha(os.path.join(p28, "audit", "components.json"))}},
        "figures": figs,
        "metrics": {"path": rel(os.path.join(ev, "metrics_audit.json")), "sha256": sha(os.path.join(ev, "metrics_audit.json"))},
        "referenceUseJa": "参照モデル（wave_repair_zbrush2.obj）・写真（北斋参考）・G:/research/Wave Simulation は、この点検では読んでいない。",
        "noteJa": "Unity の PC オフスクリーン描画（batchmode、RTX 3080、Direct3D11）。HMD 実機ではない。場面・スクリプト・シェーダー・データは変えていない（守るファイルの SHA-256 は前後で同じ）。git は書いていない。",
    }
    if rep9:
        run["unityReport"]["stage9"] = {"path": rel(os.path.join(st9, "pl29_audit_report.json")), "sha256": sha(os.path.join(st9, "pl29_audit_report.json")),
                                        "images": len(rep9["images"]), "secondsTotal": rep9["secondsTotal"], "protectedUnchanged": rep9["protectedUnchanged"]}
    with open(os.path.join(ev, "run_audit.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(run, f, ensure_ascii=False, indent=1)
    print(json.dumps({"figures": len(figs), "metrics": run["metrics"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
