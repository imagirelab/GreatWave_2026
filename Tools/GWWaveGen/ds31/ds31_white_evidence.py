# -*- coding: utf-8 -*-
"""設計31 白の部：Unity の描画（DS31Render）と numpy（ds31_white.py）の値から、102・176・152 の測り、t* の回帰、図、3 × 3 の動画、
metrics_white.json・run_white.json を作る。

使い方（リポジトリの根で）：
    py -3.10 -B Tools/GWWaveGen/ds31/ds31_white_evidence.py [--run Unity/Build/Design/31/white/unity/main]
出力：Unity/Build/Design/31/white/evidence/（Git 対象外。記録の番号が Docs/Evidence/Design/31/ へ写す）
"""
import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
WHITE = REPO + "/Unity/Build/Design/31/white"
D30 = REPO + "/Unity/Build/Design/30/unity/single_fix1"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
IMAGES = ["af28r01_painting.png", "af28r01_seat.png", "af28r01_seat_low.png", "af28r01_painting_kstar.png", "af28r01_seat_kstar.png",
          "af28r01_seat_low_kstar.png", "af28r01_class_ids.png", "af28r01_seat_class_ids.png", "af28r01_seat_low_class_ids.png", "af28r01_line_ids.png"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def imread(p):
    return cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR)


def lum(im):
    im = im.astype(np.float64)
    return 0.114 * im[..., 0] + 0.587 * im[..., 1] + 0.299 * im[..., 2]


def check152(run, spray_rgb):
    """152：飛沫あり・なしの同じコマの対（MSAA 8 の色の画像）。飛沫が変えた画素（どれかの色で差 > 6）について、
    黒い縁＝輝度が「飛沫なしの画素」と「飛沫の白」の両方より 12 以上暗い画素、光る縁＝飛沫の白より 12 以上明るい画素、
    四角い下地＝変わった画素の連結成分（8 近傍、≥ 64 画素＝形が読める大きさ。4 × 4 画素ほどの点は円でも四角を埋めるので形を問わない）で外接の四角に対する面積の比 ≥ 0.95 のもの（円は約 0.79）。どれも 0 が合格。"""
    lw = 0.114 * spray_rgb[2] + 0.587 * spray_rgb[1] + 0.299 * spray_rgb[0]
    rows = []
    tot = {"pairs": 0, "changed_px": 0, "dark_edge_px": 0, "glow_px": 0, "components": 0, "square_components": 0, "fill_ratio_max": 0.0,
           "fill_ratio_median": None}
    fills = []
    for on in sorted(glob.glob(run + "/pairs/*_on.png")):
        off = on[:-7] + "_off.png"
        a, b = imread(on), imread(off)
        d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(-1)
        m = d > 6
        la, lb = lum(a), lum(b)
        dark = m & (la < np.minimum(lb, lw) - 12)
        glow = m & (la > lw + 12)
        n, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
        sq = 0
        small = 0
        for i in range(1, n):
            x, y, w, h, area = st[i]
            if area < 64:
                small += 1
                continue
            f = area / float(w * h)
            fills.append(f)
            if f >= 0.95:
                sq += 1
        r = {"pair": os.path.basename(on)[:-7], "changed_px": int(m.sum()), "dark_edge_px": int(dark.sum()), "glow_px": int(glow.sum()),
             "components": int(n - 1), "components_lt64px": small, "square_components": sq}
        rows.append(r)
        tot["pairs"] += 1
        for k in ("changed_px", "dark_edge_px", "glow_px", "components", "square_components"):
            tot[k] += r[k]
    if fills:
        tot["fill_ratio_max"] = float(np.max(fills)); tot["fill_ratio_median"] = float(np.median(fills)); tot["components_ge64px"] = len(fills)
    tot["pass"] = tot["pairs"] > 0 and tot["dark_edge_px"] == 0 and tot["glow_px"] == 0 and tot["square_components"] == 0
    tot["rule_ja"] = check152.__doc__.strip()
    return tot, rows


def regress(run):
    """t* の回帰：t28_white の 10 枚が設計30 の t28_seaids と SHA-256 まで同じか（同じなら評価器の値も同じ）。
    t28_spray は、色の画像の違う画素の数と、原画視点の空の上の方（行 0〜379、212）の違う画素の数を記録する。"""
    out = {"white_vs_ds30": {}, "spray_vs_ds30": {}}
    same = True
    for f in IMAGES:
        a = os.path.join(run, "t28_white", "t28", "render", f)
        b = os.path.join(D30, "t28_seaids", "t28", "render", f)
        eq = os.path.exists(a) and sha(a) == sha(b)
        out["white_vs_ds30"][f] = eq
        same &= eq
    out["white_identical_all10"] = bool(same)
    sp = os.path.join(run, "t28_spray", "t28", "render")
    if os.path.isdir(sp):
        for f in IMAGES:
            a, b = imread(os.path.join(sp, f)), imread(os.path.join(D30, "t28_seaids", "t28", "render", f))
            dm = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(-1) > 0
            rec = {"diff_px": int(dm.sum())}
            if f == "af28r01_painting.png":
                rec["diff_px_rows_0_379"] = int(dm[:380].sum())
            out["spray_vs_ds30"][f] = rec
    return out


def ids_table(rep):
    ids = rep.get("ids") or []
    by = {}
    for r in ids:
        by.setdefault(r["view"], []).append(r)
    res = {}
    for v, rs in by.items():
        rs = sorted(rs, key=lambda x: x["t"])
        first = next((r["t"] for r in rs if r["dispWhite"] > 0), None)
        res[v] = {
            "times": len(rs), "first_white_t": first,
            "disp_white_final_not_total": int(sum(r["dispWhiteFinalNot"] for r in rs)),
            "disp_nonwhite_not_final_total": int(sum(r["dispNonWhiteNotFinal"] for r in rs)),
            "disp_white_at_tstar": next((r["dispWhite"] for r in rs if abs(r["t"] - 12) < 1e-3), None),
            "final_white_at_tstar": next((r["finalWhite"] for r in rs if abs(r["t"] - 12) < 1e-3), None),
            "disp_white_monotone": bool(all(rs[i + 1]["dispWhite"] >= rs[i]["dispWhite"] - 0 for i in range(len(rs) - 1) if rs[i + 1]["t"] <= 12)),
            "series": [[r["t"], r["dispWhite"], r["finalWhite"], r["dispWhiteFinalNot"]] for r in rs],
        }
    return res


def fig_series(nj, idt, path):
    s = nj["b102_vertex"]["series"]
    t = np.array(s["t"]); tf = np.array(s["texel_fraction"]); af = np.array(s["area_fraction"])
    W, H = 1920, 1080
    im = np.full((H, W, 3), 255, np.uint8)
    def panel(x0, y0, w, h, ys, cols, ymax, title, hline=None):
        cv2.rectangle(im, (x0, y0), (x0 + w, y0 + h), (0, 0, 0), 1)
        cv2.putText(im, title, (x0 + 8, y0 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        for i, tt in enumerate(range(0, 15, 1)):
            x = int(x0 + w * tt / 14.0)
            cv2.line(im, (x, y0 + h), (x, y0 + h + 6), (0, 0, 0), 1)
            cv2.putText(im, str(tt), (x - 6, y0 + h + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        if hline is not None:
            y = int(y0 + h - h * hline / ymax)
            cv2.line(im, (x0, y), (x0 + w, y), (0, 0, 200), 1)
            cv2.putText(im, "%.3g" % hline, (x0 + w + 4, y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 200), 1)
        for (tx, yv), col in zip(ys, cols):
            pts = np.stack([x0 + w * np.asarray(tx) / 14.0, y0 + h - h * np.clip(np.asarray(yv) / ymax, 0, 1.05)], 1).astype(np.int32)
            cv2.polylines(im, [pts], False, col, 2)
    panel(80, 70, 820, 380, [(t, tf), (t, af)], [(160, 60, 20), (40, 140, 40)], 1.0, "white fraction (texel: blue, world area: green) vs t [s]")
    panel(1020, 70, 820, 380, [(t[1:], np.diff(tf)), (t[1:], np.diff(af))], [(160, 60, 20), (40, 140, 40)], 0.03, "per-frame increment at 30 Hz (limit 0.02, red)", 0.02)
    ys, cols = [], []
    mx = 1
    for v, col in (("painting", (150, 40, 150)), ("seat", (20, 120, 200))):
        if v in idt:
            ser = np.array(idt[v]["series"], dtype=np.float64)
            ys.append((ser[:, 0], ser[:, 1])); cols.append(col)
            mx = max(mx, ser[:, 2].max())
    panel(80, 600, 820, 380, ys, cols, mx * 1.05, "Unity ID: white pixels shown (painting: purple, seat: orange) vs t [s]")
    bad = []
    for v in ("painting", "seat"):
        if v in idt:
            ser = np.array(idt[v]["series"], dtype=np.float64)
            bad.append((ser[:, 0], ser[:, 3]))
    panel(1020, 600, 820, 380, bad, [(150, 40, 150), (20, 120, 200)], 10, "Unity ID: shown white but final not white (must be 0)")
    cv2.imencode(".png", im)[1].tofile(path)


def sheet(run, path, sets=("gen", "adv", "air"), views=("painting", "seat", "side_left", "side_top"), times=("09.00", "10.00", "10.50", "11.00", "12.00"), set_for_sheet="air"):
    rows = []
    for v in views:
        tiles = []
        for tt in times:
            p = "%s/stills/ds31_%s_%s_t%ss.png" % (run, set_for_sheet, v, tt)
            im = imread(p) if os.path.exists(p) else np.zeros((1080, 1920, 3), np.uint8)
            im = cv2.resize(im, (384, 216), interpolation=cv2.INTER_AREA)
            cv2.putText(im, "%s t=%s" % (v, tt), (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
            cv2.putText(im, "%s t=%s" % (v, tt), (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            tiles.append(im)
        rows.append(np.hstack(tiles))
    cv2.imencode(".png", np.vstack(rows))[1].tofile(path)


def grid_video(run, path, views=("painting", "seat", "side_left", "side_top")):
    ins = []
    for st in ("gen", "adv", "air"):
        for v in views:
            ins.append("%s/video/ds31_%s_%s_30fps.mp4" % (run, st, v))
    if not all(os.path.exists(p) for p in ins):
        return None
    args = [FFMPEG, "-y", "-loglevel", "error"]
    for p in ins:
        args += ["-i", p]
    nv = len(views)
    tw, th = 1920 // nv, (1920 // nv) * 9 // 16
    fl = "".join("[%d:v]scale=%d:%d[v%d];" % (i, tw, th, i) for i in range(len(ins)))
    lay = "|".join("%d_%d" % ((i % nv) * tw, (i // nv) * th) for i in range(len(ins)))
    fl += "".join("[v%d]" % i for i in range(len(ins))) + "xstack=inputs=%d:layout=%s[out]" % (len(ins), lay)
    args += ["-filter_complex", fl, "-map", "[out]", "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart", path]
    r = subprocess.run(args, capture_output=True, text=True)
    return {"path": path, "sha256": sha(path) if os.path.exists(path) else "", "ffmpeg_error": r.stderr[-400:],
            "layout_ja": "行＝gen（発生位置：赤＝いま白くなった所の印、赤紫＝飛沫を確認用の色で）・adv（移流：朱＝白くなった後シートに付いて動く印、赤紫＝飛沫）・air（空中の粒子：飛沫だけ、作品の色＝白）、列＝" + "・".join(views)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=WHITE + "/unity/main")
    a = ap.parse_args()
    run = a.run
    ev = WHITE + "/evidence"
    os.makedirs(ev, exist_ok=True)
    rep = json.load(open(run + "/ds31_render_report.json", encoding="utf-8"))
    nj = json.load(open(WHITE + "/ds31_white_numpy.json", encoding="utf-8"))
    spray = next((p for p in rep.get("particles", []) if p["name"] == "spray"), None)
    spray_rgb = [int(round(255 * x)) for x in spray["colour"]] if spray else [251, 246, 227]
    t152, rows152 = check152(run, spray_rgb)
    rg = regress(run)
    # 評価器（ds30b_tstar_regress.py --sets t28_spray）の結果があれば、飛沫を ID に入れた読みとして記録する
    rj = os.path.join(run, "ds30_tstar_regress.json")
    if os.path.exists(rj):
        e = json.load(open(rj, encoding="utf-8"))["sets"].get("t28_spray")
        if e:
            rg["spray_in_ids_evaluator"] = {"lfgate": e["lfgate"], "lfgate_diff_vs_29r01_px": e["lfgate_diff_vs_29r01_px"],
                                            "silhouette_diff_vs_29r01_px": e["silhouette_diff_vs_29r01_px"],
                                            "colour_worst_abs_diff_px": e["verdict"]["colour_worst_abs_diff_px"], "items_over_0p5": e["verdict"]["items_over_0p5"],
                                            "sym_worst_abs_diff_px": e.get("sym", {}).get("worst_abs_diff_px"), "sym_worst_diff_vs_29r01_px": e.get("sym", {}).get("worst_diff_vs_29r01_px"),
                                            "note_ja": "飛沫を色区 ID（白）に入れて評価器を回した記録。大きな輪郭の関門（132・72）は空の中の飛沫の点を波として読むので大きくなる。採る読みは飛沫を ID に入れない t28_white（設計30 と 10 枚が画素まで同じ）"}
    idt = ids_table(rep)
    fig_series(nj, idt, ev + "/fig_ds31_white_onset.png")
    sheet(run, ev + "/fig_ds31_air_stills_sheet.png", set_for_sheet="air")
    sheet(run, ev + "/fig_ds31_gen_stills_sheet.png", set_for_sheet="gen")
    sheet(run, ev + "/fig_ds31_adv_stills_sheet.png", set_for_sheet="adv")
    gv = grid_video(run, ev + "/ds31_grid_3x4_30fps.mp4")
    b102 = nj["b102_vertex"]
    cap = nj.get("ds31_white_rate_cap")
    idp = idt.get("painting", {}); ids_ = idt.get("seat", {})
    acc = {
        "102": {
            "rule_ja": "白が 0 から連続して現れ、終態の白の内側（美術優先31 と同じ既定の読み：30 Hz の 1 コマで白くなる割合が終態の白の 2% 以下、終態が白でない所が白になる数 0）",
            "value_ja": "テクセルの割合の 1 コマの増分の最大 %.2f%%（ds31_white_rate_cap の前 %.2f%%）、世界の面積の増分の最大 %.2f%%、最初の白 t %.3f s（τ %.3f）、全部そろう t %.3f s、終態の白の外の白：頂点 %d・Unity の ID（原画視点・座席、各 %d 時刻）%d 画素" % (
                100 * b102["texel_fraction_max_increment_per_frame"], 100 * (cap["before"]["texel_fraction_max_increment_per_frame"] if cap else b102["texel_fraction_max_increment_per_frame"]),
                100 * b102["area_fraction_max_increment_per_frame"], b102["first_white_t_exact"], b102["first_white_tau_exact"], b102["all_white_t"],
                b102["never_white_vertices_turning_white"], idp.get("times", 0), idp.get("disp_white_final_not_total", -1) + ids_.get("disp_white_final_not_total", 0)),
            "pass": bool(b102["pass"] and idp.get("disp_white_final_not_total", 1) == 0 and ids_.get("disp_white_final_not_total", 1) == 0),
            "af31_ja": b102["af31_values_ja"],
        },
        "176": {
            "rule_ja": "白が広がる間も白の中の藍・水色が見える：一時的な白の塗りつぶし 0（Unity の ID の連続で、終態が白でない画素が白で表示された数 0、終態が白でない画素の表示が終態と違う数 0）",
            "value_ja": "原画視点 %s 時刻・座席 %s 時刻で、白で表示された色区の画素 %d、終態と違う表示の色区の画素 %d" % (
                idp.get("times"), ids_.get("times"), idp.get("disp_white_final_not_total", -1) + ids_.get("disp_white_final_not_total", 0),
                idp.get("disp_nonwhite_not_final_total", -1) + ids_.get("disp_nonwhite_not_final_total", 0)),
            "pass": bool(idp.get("disp_white_final_not_total", 1) == 0 and ids_.get("disp_white_final_not_total", 1) == 0
                         and idp.get("disp_nonwhite_not_final_total", 1) == 0 and ids_.get("disp_nonwhite_not_final_total", 1) == 0),
        },
        "152": t152,
        "tstar_regression": {"white_identical_to_ds30_all10": rg["white_identical_all10"], "spray": rg["spray_vs_ds30"],
                             "spray_in_ids_evaluator": rg.get("spray_in_ids_evaluator")},
        "mock_stereo_record": {
            "rule_ja": "記録のみ（HMD の項目は保留）：座席 v1・原画視点のカメラを ±0.032 m ずらした 2 回の描画で、飛沫が変えた画素の数の左右差（設計34 の <10% の目安の事前の値）",
            "rows": rep.get("stereo"),
            "rel_diff_max": max((r["relDiff"] for r in (rep.get("stereo") or [])), default=None)},
    }
    metrics = {"schema": "GreatWave.DS31.white_metrics/1", "acceptance": acc, "ids": idt, "rows152": rows152, "regression": rg,
               "rate_cap": cap, "numpy": {k: v for k, v in b102.items() if k != "series"}, "onset": nj["onset"], "marks": nj["marks"],
               "unity": {k: rep.get(k) for k in ("unity", "device", "graphicsApi", "heroPkg", "heroTwhiteSha256", "scene31", "scene31Sha256", "sprayPath",
                                                 "protectedUnchanged", "shaderAllCompiled", "secondsTotal", "tauAtTStar")},
               "particles": rep.get("particles"), "shader_checks": rep.get("shaderChecks"), "videos": rep.get("videos"), "grid_video": gv,
               "alive_max": {k: max(r[k] for r in rep.get("alive", [{"spray": 0, "born": 0, "trace": 0}])) for k in ("spray", "born", "trace")}}
    json.dump(metrics, open(ev + "/metrics_white.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    runj = {"commands": [
        "py -3.10 Tools/GWWaveGen/ds31/ds31_white.py",
        "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds31/run_ds31w_unity.ps1 -Method GreatWave.Design31.EditorTools.DS31Render.Render -Log main -Extra \"-ds31Out Build/Design/31/white/unity/main\"",
        "py -3.10 -B Tools/GWWaveGen/ds31/ds31_white_evidence.py --run Unity/Build/Design/31/white/unity/main"],
        "python": sys.version.split()[0], "numpy": np.__version__, "opencv": cv2.__version__,
        "inputs": nj["inputs"], "outputs_sha256": {os.path.relpath(p, WHITE).replace("\\", "/"): sha(p) for p in sorted(glob.glob(WHITE + "/*.bin") + glob.glob(WHITE + "/*.json") + glob.glob(WHITE + "/hero_pkg/*") + glob.glob(ev + "/*")) if os.path.isfile(p) and not p.endswith("run_white.json")},
        "unity_files": len(rep.get("files", []))}
    json.dump(runj, open(ev + "/run_white.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"102": acc["102"], "176": acc["176"], "152": {k: v for k, v in t152.items() if k != "rule_ja"}, "regress_white": rg["white_identical_all10"],
                      "spray_diff": rg["spray_vs_ds30"].get("af28r01_painting.png"), "grid": gv and gv["ffmpeg_error"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
