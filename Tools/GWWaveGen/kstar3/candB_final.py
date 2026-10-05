# -*- coding: utf-8 -*-
"""Q20 candidate B: write K*'_B (GWW0 + rows + meta), run the painting gate, the Q20 rubric (with the temporary
reference cache for F13), the 9 standard clay views, the turntable, and the comparison figures.

  py -3.10 candB_final.py [--tag final] [--skip-render]
Everything goes to Unity/Build/Q20/candB (git-ignored).  The reference model is read only by the rubric tool's
Blender script to make a TEMPORARY cache (deleted at the end, SHA-256 recorded); nothing of it is written elsewhere.
"""
import sys, os, json, time, subprocess, hashlib, datetime, shutil
import numpy as np
import cv2
from candB_common import *
from candB_geom import inside_px, kstar_lock
import candB_build as BLD

BL = r"G:\SteamLibrary\steamapps\common\Blender\blender.exe"
REF_OBJ = r"G:\research\model\wave_repair_zbrush2.obj"
TOOLS = os.path.join(RUBRIC, "tools")


def run(cmd, log=None):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if log:
        open(log, "w", encoding="utf-8").write(r.stdout + "\n----\n" + r.stderr)
    return r


def frac_top_col(a, y, jtip=200):
    j = int(np.argmax(y[:jtip]))
    if 0 < j < jtip - 1:
        y0, y1, y2 = y[j - 1], y[j], y[j + 1]
        den = y0 - 2 * y1 + y2
        off = 0.5 * (y0 - y2) / den if abs(den) > 1e-12 else 0.0
        return float(j + np.clip(off, -0.5, 0.5))
    return float(j)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "final"
    skip_render = "--skip-render" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    z = np.load(os.path.join(WORK, "rows_%s.npz" % tag)); A, Y, c = z["A"], z["Y"], z["c"]
    A0, Y0, c0 = load_kstar()
    base = os.path.join(OUT, "kstarB_a45")
    t0 = time.time()
    # ---------------------------------------------------------------- files
    gwb = base + ".gwb"
    h_gwb = write_gwb(gwb, A, Y, c)
    top_frac = np.array([frac_top_col(A[r], Y[r]) for r in range(NV)])
    save_rows(base + "_rows.npz", A, Y, c, {"top_col_frac": top_frac, "c_kstar": c0})
    # ---------------------------------------------------------------- mesh checks
    import gw_wavegen_v1 as V1
    g = read_gwb(gwb)
    X = g["X"].reshape(NV, NU, 3)
    mc = V1.mesh_checks(X, g["tris"], A, Y, NV, NU)
    mc["local_self_intersection_vertices_win6"] = len(V1.local_self_intersections(world(A, Y, c), win=6))
    same_topology = bool(np.array_equal(g["tris"], read_gwb()["tris"]) and np.array_equal(g["uv"], read_gwb()["uv"]))
    # ---------------------------------------------------------------- painting gate (F01) + sky diff
    cov0 = np.load(os.path.join(WORK, "cov_kstar.npy"))
    gg = gate(A, Y, c, png=os.path.join(OUT, "gate_overlay_candB.png"), title="Q20 candidate B K*' (envelope gate)")
    cov = coverage(A, Y, c); md = mask_diff(cov0, cov)
    vis = np.dstack([md["rem"] * 255, (cov0 > 0.5) * 90, md["add"] * 255]).astype(np.uint8)
    cv2.imwrite(os.path.join(OUT, "gate_sky_diff_candB.png"), vis)
    # ---------------------------------------------------------------- reference cache (temporary) + F13
    h_obj = hashlib.sha256(open(REF_OBJ, "rb").read()).hexdigest().upper()
    assert h_obj.startswith("AB4124F9") and h_obj.endswith("3D40"), h_obj
    cache = os.path.join(WORK, "_ref_cache_tmp.npz")
    rtmp = os.path.join(WORK, "_ref_tmp_render")
    if not os.path.isfile(cache):
        r = run([BL, "--background", "--factory-startup", "--python-exit-code", "1", "--python", os.path.join(TOOLS, "bl_rubric_views.py"),
                 "--", rtmp, cache, "ref", "v6_top_down"], os.path.join(WORK, "log_refcache.txt"))
        print("ref cache rc", r.returncode)
    # ---------------------------------------------------------------- rubric
    rub = os.path.join(OUT, "rubric_candB.json")
    r = run(["py", "-3.10", os.path.join(TOOLS, "rubric_check.py"), base + "_rows.npz", rub, "--gate", "--ref", cache],
            os.path.join(WORK, "log_rubric_final.txt"))
    R = json.load(open(rub, encoding="utf-8"))
    print("rubric", R["summary"])
    # ---------------------------------------------------------------- F09 second crest (S-type numbers, our own measures)
    import candB_crest2 as CR2
    s1, nb = CR2.s1_fraction(A, Y, c, BLD.P)
    step = {}
    for cq in (-13.5, -10.5, -8.0, -5.5):
        rr = int(np.argmin(np.abs(c - cq)))
        a, y = A[rr], Y[rr]; jt = int(np.argmax(y[:200]))
        # the ridge = the highest point of the lip top after its dip (jt+15 .. 199)
        seg = y[jt + 15:200]
        if len(seg) and seg.max() < y[jt] - 0.3:
            jr = jt + 15 + int(np.argmax(seg))
            dmin = float(y[jt:jr].min())
            step[str(cq)] = {"row": rr, "crest_y": float(y[jt]), "ridge_y": float(y[jr]), "crest_minus_ridge_m": float(y[jt] - y[jr]),
                             "dip_below_ridge_m": float(y[jr] - dmin), "ridge_a": float(a[jr]), "tip": [float(a[200]), float(y[200])]}
        else:
            step[str(cq)] = {"row": rr, "note": "no separate ridge (outside the tier rows)"}
    f09 = {"S1_band_foam_on_tier": s1, "band_px_sampled": nb, "S1_definition": "share of the painted foam-band pixels (Q16 mask) whose PaintingCam ray first hits the lip outer part (cols 150..230) of a shoulder row c -17..-2.5 (z-buffer ID raster, step 2 px)",
           "lobes_c": {k: list(v) for k, v in CR2.LOBES.items()}, "step_crest_to_ridge": step}
    # ---------------------------------------------------------------- renders
    rd = os.path.join(OUT, "renders")
    if not skip_render:
        r = run([BL, "--background", "--factory-startup", "--python-exit-code", "1", "--python", os.path.join(TOOLS, "bl_rubric_views.py"),
                 "--", rd, cache, "kstar", "all", gwb, "candB"], os.path.join(WORK, "log_render_final.txt"))
        print("render rc", r.returncode)
        tt = os.path.join(OUT, "turntable")
        r = run([BL, "--background", "--factory-startup", "--python-exit-code", "1", "--python", os.path.join(os.path.dirname(os.path.abspath(__file__)), "candB_bl_turntable.py"),
                 "--", tt, gwb], os.path.join(WORK, "log_turntable.txt"))
        print("turntable rc", r.returncode)
        frames = sorted(f for f in os.listdir(tt) if f.endswith(".png"))
        if frames:
            im0 = cv2.imread(os.path.join(tt, frames[0]))
            vw = cv2.VideoWriter(os.path.join(OUT, "candB_turntable.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 24, (im0.shape[1], im0.shape[0]))
            for f in frames:
                vw.write(cv2.imread(os.path.join(tt, f)))
            vw.release()
    # ---------------------------------------------------------------- delete the temporary reference cache
    h_cache = hashlib.sha256(open(cache, "rb").read()).hexdigest() if os.path.isfile(cache) else None
    if os.path.isfile(cache):
        os.remove(cache)
    if os.path.isdir(rtmp):
        shutil.rmtree(rtmp)
    open(os.path.join(OUT, "deleted_caches_sha256.txt"), "w", encoding="utf-8").write(
        "reference-model cache (temporary, made by rubric tools/bl_rubric_views.py from %s SHA-256 %s) deleted %s: sha256 %s\n" % (
            REF_OBJ, h_obj, datetime.datetime.now().isoformat(timespec="seconds"), h_cache))
    # ---------------------------------------------------------------- meta
    H = Y.max(1)
    lk_k = kstar_lock(A0, Y0, c0)
    moved = np.hypot(A - A0, Y - Y0)
    meta = {
        "schema": "GreatWave.Q20.candB.kstar_meta/1",
        "candidate": "B (incremental fixes of K* 26修正01: Q16/Q17 plans + Q20 rubric)",
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "base": {"kstar": os.path.join(KDIR, "kstar_a45.gwb"), "kstar_gwb_sha256": sha256(os.path.join(KDIR, "kstar_a45.gwb"))},
        "files": {"gwb": os.path.basename(gwb), "gwb_sha256": h_gwb, "rows": os.path.basename(base + "_rows.npz"),
                  "rows_sha256": sha256(base + "_rows.npz")},
        "format_ja": "GWW0（K* と同じ 32 B ヘッダ・UV・三角形。UV2.y だけ新しい行の c に更新）。頂点添字 = 行×400 + 列。rows npz は A, Y, c（240 行 × 400 列、K* 26修正01 の断面の枠）に top_col_frac（行ごとの頂の小数列）と c_kstar を足した。",
        "frame": FR, "nu": NU, "nv": NV, "same_topology_and_uv_as_kstar": same_topology,
        "landmarks": {"j_B": J_B, "j_top_nominal": J_TOP, "j_tip": J_TIP, "j_corner": J_CORNER, "j_facebot": J_FB, "j_E": J_E,
                      "note_ja": "列の意味は K* と同じ（0-18 後ろの海、18-頂 背、頂-200 唇の上面、200 唇先、200-314 唇の下面と管の天井、314-379 内壁、379-394 前の谷、394-399 前の海）。頂の列は行ごとに小数で top_col_frac に記録（K* と同じく 84〜97 の範囲で揺れる。列の付け替えはしていない）。遠い行（c > 0）は主断面から作る族で、同じ列が同じ意味を持つ。"},
        "top_col_frac_range": [float(top_frac.min()), float(top_frac.max())],
        "rows_c_range": [float(c.min()), float(c.max())], "far_end_c": float(c.max()), "min_row_gap_m": float(np.diff(c).min()),
        "H0_main_m": float(Y[int(np.argmin(np.abs(c)))].max()), "H_max_m": float(H.max()), "c_of_H_max": float(c[int(np.argmax(H))]),
        "painting_gate": gg, "painting_gate_pass": gate_ok(gg),
        "sky_diff_vs_kstar_px": {"added": md["added_px"], "removed": md["removed_px"],
                                 "note_ja": "増えた画素は、72 の終わり（表示 y 736）と水平線（y 788）の間の前の足（原画では前景の波の白い泡の上、確認済み）と唇先の 1〜数 px。関門の項目は動かない。"},
        "painting_locked_vertices_kstar": int(lk_k.sum()),
        "vertex_move_m": {"max": float(moved.max()), "median_moved": float(np.median(moved[moved > 1e-6])) if (moved > 1e-6).any() else 0.0},
        "mesh_checks": mc,
        "params": {k: (list(v) if isinstance(v, tuple) else v) for k, v in BLD.P.items()},
        "steps_ja": [
            "1 奥の閉じ直し ds_kstar_far_close：c > 0 の 80 行を c 0.06〜%.2f に置き直し、主断面（q = 0）と丸い管の薄い殻 S_min（q = 1）の間の族で作る。各行は主断面の座標（原画カメラの光線で c = 0 の面へ写した座標）で作り、光線に沿って自分の面へ戻すので、原画視点では主断面の像の中に隠れる。高さは主断面の頂から c 2.45 m で 0.74 H0 へ下げ、奥の端は薄い巻きで開いたまま終える（管の口）。" % float(c.max()),
            "2 背の丸みと頂の G1 つなぎ ds_kstar_back_round / num_top_blend：頂の近くの原画に固定された頂点（像が K* の輪郭から 2.5 px 以内）を残し、そこから背を向きの角のプログラム（丸い頂 R ≈ 0.21H、0.9H で約 50°、首、凹の足）で作り直す。頂は空いている側から G1 で丸め、肩の行では頂から円弧（R 0.8〜1.4 m）で前へつなぐ。",
            "3 足の台座を取って前の谷へ ds_kstar_foot_trough：列 379 から下を、65° 以下の傾きで谷（深さ 0.22 H_r、座席の船の所は船首の水線 −1.37 m に合わせて浅く）へ流す。水平線より下なので原画には写らない（72 の終わりと水平線の間の 1 か所だけ、原画の前景の泡の上に数百 px 増える）。",
            "4 第二の波頭 ds_second_crest（Q16 点5、物理に意図して反する）：肩の行（c −17.5〜−6.2）の唇を、頂の後ろで一度くぼませ、原画の泡の帯の上端を光線で各行の面へ逆投影した高さの稜へ上げ、帯の下端の高さの爪の縁へ下ろす段にする。房は 3 つ（A −11.0〜−7.8、B −14.0〜−11.0、C −17.0〜−14.0：原画の帯が乗る行）、房の中心で前へ張り出し、房の間で退く。ポケットは段の鉤の下の管。",
            "5 近い行の唇と管 ds_kstar_near_tube：c < −0.3 の行の管を、唇先を通る丸い管（半径 0.36〜0.46 H_r、少し後ろへ傾ける）に作り直し、唇を薄い鉤にする。円の大きさと唇先の角は行ごとに解いてから c 方向になめらかにした。",
            "6 行の掃除 kstar_row_clean：原画の輪郭から 6 px より内の頂点だけを c 方向にガウスでならす（背 0.6 m、唇の上面 0.45 m、管 1.1 m）。頂の窓は除き、最後に頂を丸め直す。隠れた唇の上面の爪の包絡の凸凹をならす。3 cm より狭い行（K* の 158/159）は光線に沿って 3.5 cm へ離す。シートの前後の縁を K* と同じ a にそろえる。"],
        "rubric_summary": R["summary"], "rubric_json": os.path.basename(rub), "F09_second_crest": f09,
        "credit_ja": "参照にした作品：G:/research/model/wave_repair_zbrush2.obj（利用者が展示作品をスキャンしたもの。作者・所蔵は未確認（D18））と写真 北斋参考。形は読まず、比率（管の R/H、殻の考え、奥の管の口、房が 3 つあること）だけを借りた。生成器は参照の網を読まない（F13 の距離は測り、一時キャッシュは消した）。",
        "time_s": round(time.time() - t0, 1),
    }
    json.dump(meta, open(base + "_meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    print(json.dumps({"gate": gg, "gate_pass": gate_ok(gg), "rubric": R["summary"], "F09": {"S1": s1}, "mesh": mc}, ensure_ascii=False, default=float)[:2000])


if __name__ == "__main__":
    main()
