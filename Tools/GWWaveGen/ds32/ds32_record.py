# -*- coding: utf-8 -*-
"""設計32 の記録：証拠（Docs/Evidence/Design/32/）を作り、metrics.json と run.json を書く。

値は「一覧と ID」の部の出力（Unity/Build/Design/32/list+ids/。修正01 の前の出力は list+ids_prefix01/）と、
進行役の独立の検査（リポジトリの外のコード。コードと出力の写しは Git 対象外の Unity/Build/Design/32/indep_check/）から読む。
この道具で新しく数えるのは次のものだけ（結果は Unity/Build/Design/32/record/ds32_record_counts.json にも書く）。
  1) 修正01 の指摘 1・3 の前と後の重なり（爪の領域の多角形と中心線を高解像度の画素へ塗って数える）
  2) 修正01 の指摘 2 の爪の長さの前と後（一覧の length_ref_px を並べるだけ）
  3) 右側の爪（C129〜C153）が美術優先29 の一覧から変わっていないこと（根元・先端・中心線の座標の差）
  4) 利用者の 100 本の位置合わせの残差のまとめ（ds32_user100_registration.json から）
  5) 進行役の独立の影の検査（indep_check/shchk2.json、修正01 の前の一覧で測ったもの）のまとめ

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/ds32/ds32_record.py
"""
import datetime
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
HERE = REPO + "/Tools/GWWaveGen/ds32"
B32 = REPO + "/Unity/Build/Design/32"
LI = B32 + "/list+ids"
PRE = B32 + "/list+ids_prefix01"
IND = B32 + "/indep_check"
REC = B32 + "/record"
EV = REPO + "/Docs/Evidence/Design/32"
BASE_INV = REPO + "/Tools/PaintingTruth/claws29/claw_inventory.json"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
CLAW_README = "G:/Unity/Ukeyoe_Claw/Docs/Research/Claw_Analysis/README.md"  # Q8 の例外の 1 ファイル（SHA-256 を取るだけ）
H_REF, W_REF = 2594, 3859
MP4_LIMIT = 5 * 1024 * 1024


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def jdump(o, p):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(o, f, ensure_ascii=False, indent=1)
        f.write("\n")


def imread(p):
    return cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR)


def imwrite(p, im):
    ok, buf = cv2.imencode(".png", im, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    assert ok
    buf.tofile(p)


def fit1080(im):
    """1920×1080 の枠に収める（縮尺だけ変える。余白は白、上寄せ・左右の中央）。"""
    h, w = im.shape[:2]
    s = min(1920 / w, 1080 / h, 1.0)
    if s < 1:
        im = cv2.resize(im, (int(round(w * s)), int(round(h * s))), interpolation=cv2.INTER_AREA)
    out = np.full((1080, 1920, 3), 255, np.uint8)
    h, w = im.shape[:2]
    x0 = (1920 - w) // 2
    out[:h, x0:x0 + w] = im
    return out, round(s, 4)


def poly_mask(poly):
    m = np.zeros((H_REF, W_REF), np.uint8)
    cv2.fillPoly(m, [np.round(np.asarray(poly, np.float64)).astype(np.int32)], 1)
    return m > 0


def line_mask(pts):
    m = np.zeros((H_REF, W_REF), np.uint8)
    cv2.polylines(m, [np.round(np.asarray(pts, np.float64)).astype(np.int32)], False, 1, 1)
    return m > 0


def overlaps(inv, a, b):
    c = {x["id"]: x for x in inv["claws"]}
    if a not in c or b not in c:
        return None
    ma, mb = poly_mask(c[a]["region_polygon_ref"]), poly_mask(c[b]["region_polygon_ref"])
    la, lb = line_mask(c[a]["centerline_ref"]), line_mask(c[b]["centerline_ref"])
    inter = int((ma & mb).sum())
    return {"a": a, "b": b, "area_a_px": int(ma.sum()), "area_b_px": int(mb.sum()), "intersection_px": inter,
            "intersection_of_smaller": round(inter / max(1, min(ma.sum(), mb.sum())), 3),
            "centerline_b_in_region_a": round(float((lb & ma).sum() / max(1, lb.sum())), 3),
            "centerline_a_in_region_b": round(float((la & mb).sum() / max(1, la.sum())), 3),
            "root_a_to_tip_b_px": round(float(np.hypot(*(np.array(c[a]["root_ref"]) - np.array(c[b]["tip_ref"])))), 1)}


def counts():
    pre, new = jload(PRE + "/ds32_claw_inventory.json"), jload(LI + "/ds32_claw_inventory.json")
    base = jload(BASE_INV)
    out = {"note_ja": "記録の時に数えたもの（ds32_record.py）。爪の領域の多角形・中心線を高解像度原画の画素（3859×2594）へ塗って数えた。"
                      "独立の検査の報告の値と、塗り方の違いで少し違うことがある"}
    # 1) 指摘 1・3 の重なり
    out["fix01_overlap"] = {
        "pre": {"C105_C110": overlaps(pre, "C105", "C110"), "C105_C107": overlaps(pre, "C105", "C107"),
                "C169_C163": overlaps(pre, "C169", "C163")},
        "post": {"C105_C110": overlaps(new, "C105", "C110"), "C107_present": any(x["id"] == "C107" for x in new["claws"]),
                 "C169_present": any(x["id"] == "C169" for x in new["claws"])},
    }
    # 2) 指摘 2 の長さ
    p = {x["id"]: x for x in pre["claws"]}
    n = {x["id"]: x for x in new["claws"]}
    ids = ["C074", "C075", "C078", "C080", "C081", "C082", "C087", "C092", "C093", "C098", "C106", "C107",
           "C071", "C072", "C108", "C120", "C156", "C066", "C109", "C112", "C113"]
    out["fix01_lengths_px"] = {i: {"af29": p[i]["length_ref_px_af29"] if i in p else None,
                                   "pre": p[i]["length_ref_px"] if i in p else None, "pre_status": p[i]["status"] if i in p else None,
                                   "post": n[i]["length_ref_px"] if i in n else None, "post_status": n[i]["status"] if i in n else None}
                               for i in ids}
    # 3) 右側の爪
    bc = {x["id"]: x for x in base["claws"]}
    right = [x for x in new["claws"] if x["row"] == "右側"]
    d_root = max(float(np.abs(np.array(x["root_ref"]) - np.array(bc[x["id"]]["root_ref"])).max()) for x in right)
    d_tip = max(float(np.abs(np.array(x["tip_ref"]) - np.array(bc[x["id"]]["tip_ref"])).max()) for x in right)
    d_cl = max(float(np.abs(np.array(x["centerline_ref"]) - np.array(bc[x["id"]]["centerline_ref"])).max())
               if len(x["centerline_ref"]) == len(bc[x["id"]]["centerline_ref"]) else float("inf") for x in right)
    d_len = max(abs(x["length_ref_px"] - bc[x["id"]]["length_ref_px"]) for x in right)
    out["right_side_untouched"] = {"count": len(right), "ids": [right[0]["id"], right[-1]["id"]],
                                   "changed_flag_true": sum(1 for x in right if x.get("changed")),
                                   "max_abs_diff_root_ref_px": d_root, "max_abs_diff_tip_ref_px": d_tip,
                                   "max_abs_diff_centerline_ref_px": d_cl, "max_abs_diff_length_ref_px": round(d_len, 2)}
    # 4) 位置合わせの残差
    reg = jload(LI + "/ds32_user100_registration.json")["claws"]
    ncc = np.array([c["ncc_after_ecc"] for c in reg])
    corner = np.array([max(c["ecc_vs_similarity_corner_px"]) for c in reg])
    pm = np.array([c["peak_margin"] for c in reg])
    out["registration"] = {
        "n": len(reg), "ecc_used": int(sum(1 for c in reg if c["ecc_used"])),
        "ncc_after_ecc": {"median": round(float(np.median(ncc)), 3), "p10": round(float(np.percentile(ncc, 10)), 3),
                          "min": round(float(ncc.min()), 3), "max": round(float(ncc.max()), 3), "below_0_70": int((ncc < 0.70).sum())},
        "ecc_vs_similarity_corner_px_max_per_claw": {"median": round(float(np.median(corner)), 1), "p90": round(float(np.percentile(corner, 90)), 1),
                                                    "max": round(float(corner.max()), 1)},
        "peak_margin_below_0_02": int((pm < 0.02).sum()),
        "scale": {"min": round(float(min(c["scale"] for c in reg)), 3), "max": round(float(max(c["scale"] for c in reg)), 3)},
    }
    # 5) 独立の影の検査（修正01 の前の一覧）
    sh = jload(IND + "/shchk2.json")
    v = [r for r in sh if r[2] >= 20]
    fr = np.array([r[3] for r in v], float)
    fo = np.array([r[4] for r in v if r[4] is not None], float)
    out["indep_shadow_prefix01"] = {
        "file": "Unity/Build/Design/32/indep_check/shchk2.json", "sha256": sha(IND + "/shchk2.json"),
        "rule_ja": "進行役の独立の検査（shchk2.py）：自前の k-means の色の組、16 方向のうち 11 方向以上が 35 px 以内で暗い色に当たる水色を「囲まれた影」とし、"
                   "中心線から 25 px の測地の帯の中で、最も近い中心線がその爪のものだけを数える。囲まれた影 20 px 以上の爪を検査する。修正01 の前の一覧で測った",
        "tested": len(v), "below_0_5": int((fr < 0.5).sum()), "median": round(float(np.median(fr)), 3),
        "af29_median": round(float(np.median(fo)), 3),
        "named": {r[0]: {"indep": round(r[3], 3) if r[3] is not None else None, "author": r[5]} for r in sh
                  if r[0] in ("C083", "C084", "C085", "C109", "C110", "C154")},
    }
    return out


def main():
    os.makedirs(EV, exist_ok=True)
    os.makedirs(REC, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()

    mb = jload(LI + "/metrics.json")
    rb = jload(LI + "/run.json")
    cc = jload(LI + "/ds32_claw_list_checks.json")
    ic = jload(LI + "/ds32_id_checks.json")
    ii = jload(LI + "/ds32_ids_indep_check.json")
    ids = jload(LI + "/ds32_ids.json")
    inv = jload(LI + "/ds32_claw_inventory.json")
    corr = jload(LI + "/ds32_user100_correspondence.json")
    pre_m = jload(PRE + "/metrics.json")
    pre_cc = jload(PRE + "/ds32_claw_list_checks.json")
    pre_ic = jload(PRE + "/ds32_id_checks.json")
    pre_ii = jload(PRE + "/ds32_ids_indep_check.json")
    pre_ids = jload(PRE + "/ds32_ids.json")
    pre_inv = jload(PRE + "/ds32_claw_inventory.json")
    pre_corr = jload(PRE + "/ds32_user100_correspondence.json")
    items = {it["item"].split("：")[0]: it for it in mb["items"]}

    rc = counts()
    jdump(rc, REC + "/ds32_record_counts.json")

    # ---- 証拠：画像（1920×1080） ----
    pngs = {}

    def put_png(name, im, src):
        imwrite(EV + "/" + name, im)
        pngs[name] = {"source": src, "sha256_source": sha(LI + "/fig/" + src.split("（")[0].split("/")[-1]) if src.startswith("fig/") else None}

    for f in ("fig_ds32_rows_upper.png", "fig_ds32_rows_middle.png", "fig_ds32_rows_boat.png", "fig_ds32_rows_bregion.png",
              "fig_ds32_rows_right_untouched.png", "fig_ds32_user100.png", "fig_ds32_ids_tstar.png", "fig_ds32_ids_tracks.png"):
        im = imread(LI + "/fig/" + f)
        assert im.shape[:2] == (1080, 1920), f
        put_png(f, im, "fig/" + f + "（1920×1080 のまま）")
    for f in ("fig_ds32_named_before_after.png", "fig_ds32_fix01_c105_c110.png", "fig_ds32_fix01_c163_c169.png", "fig_ds32_fix01_flags.png"):
        im = imread(LI + "/fig/" + f)
        out, s = fit1080(im)
        put_png(f, out, "fig/" + f + "（%d×%d を 1920×1080 の枠へ。縮尺 %.3f）" % (im.shape[1], im.shape[0], s))
    # 16 組の前後図は 8 段 × 4 列（見出し 44 px、段の高さ 420 px、間 8 px）。4 段ずつ 2 枚に分ける
    im = imread(LI + "/fig/fig_ds32_fix01_truncated.png")
    head = im[:44]
    rows_y = [44 + k * 428 for k in range(8)]
    assert im.shape[0] == rows_y[-1] + 420, im.shape
    for part, (k0, k1) in enumerate(((0, 4), (4, 8)), 1):
        body = im[rows_y[k0]:rows_y[k1 - 1] + 420]
        out, s = fit1080(np.concatenate([head, body], 0))
        put_png("fig_ds32_fix01_truncated_%d.png" % part, out,
                "fig/fig_ds32_fix01_truncated.png（%d×%d の段 %d〜%d に見出しを付け、1920×1080 の枠へ。縮尺 %.3f）" % (
                    im.shape[1], im.shape[0], k0 + 1, k1, s))

    # ---- 証拠：動画（5 MB 以下へ符号化し直す） ----
    src_mp4 = LI + "/fig/ds32_ids_30fps.mp4"
    dst_mp4 = EV + "/ds32_ids_30fps.mp4"
    crf_used = None
    for crf in (26, 28, 30, 32, 34):
        subprocess.run([FFMPEG, "-y", "-v", "error", "-i", src_mp4, "-c:v", "libx264", "-preset", "slow", "-crf", str(crf),
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", dst_mp4], check=True)
        if os.path.getsize(dst_mp4) <= MP4_LIMIT:
            crf_used = crf
            break
    assert crf_used is not None
    probe = subprocess.run([FFMPEG.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error", "-count_frames", "-show_entries",
                            "stream=width,height,nb_read_frames,r_frame_rate", "-of", "json", dst_mp4],
                           capture_output=True, text=True, check=True)
    st = json.loads(probe.stdout)["streams"][0]
    video = {"file": "ds32_ids_30fps.mp4", "source": "Unity/Build/Design/32/list+ids/fig/ds32_ids_30fps.mp4",
             "source_sha256": sha(src_mp4), "source_bytes": os.path.getsize(src_mp4),
             "reencode_ja": "libx264 -preset slow -crf %d（元は %d バイトで 5 MB を超えるので符号化し直した。大きさ・コマ数は同じ）" % (crf_used, os.path.getsize(src_mp4)),
             "width": st["width"], "height": st["height"], "frames": int(st["nb_read_frames"]), "fps": st["r_frame_rate"],
             "bytes": os.path.getsize(dst_mp4)}

    # ---- 証拠：JSON の写しと、爪の一覧の要約 ----
    copied = {}
    for k in ("ds32_claw_list_checks.json", "ds32_id_checks.json", "ds32_ids_indep_check.json", "ds32_user100_correspondence.json"):
        shutil.copyfile(LI + "/" + k, EV + "/" + k)
        copied[k] = {"source": rel(LI + "/" + k), "sha256": sha(LI + "/" + k)}
    shutil.copyfile(REC + "/ds32_record_counts.json", EV + "/ds32_record_counts.json")
    copied["ds32_record_counts.json"] = {"source": rel(REC + "/ds32_record_counts.json"), "sha256": sha(REC + "/ds32_record_counts.json")}
    idc = {x["id"]: x for x in ids["claws"]}
    table = []
    for x in inv["claws"]:
        y = idc.get(x["id"], {})
        table.append({
            "id": x["id"], "row": x["row"], "origin": x["origin"], "b_region_q16": x["b_region_q16"], "status": x["status"],
            "mouth_reason": x.get("mouth_reason"), "root_ref": x["root_ref"], "tip_ref": x["tip_ref"],
            "length_ref_px": x["length_ref_px"], "length_ref_px_af29": x.get("length_ref_px_af29"),
            "root_move_px": x.get("root_move_px"), "shadow_included": (x.get("shadow") or {}).get("included_new"),
            "shadow_included_af29": (x.get("shadow") or {}).get("included_af29"), "changed": x.get("changed"),
            "bound": y.get("bound"), "sheet_rc": y.get("sheet_rc"), "sheet_uv": y.get("sheet_uv"), "t_birth": y.get("t_birth"),
            "group": y.get("group"), "tip_placement": y.get("tip_placement"), "length_tstar_m": y.get("length_tstar_m")})
    claw_table = {
        "schema": "GreatWave.DS32.claw_table/1",
        "note_ja": "爪の一覧の修正版（Unity/Build/Design/32/list+ids/ds32_claw_inventory.json）と ID（ds32_ids.json）から、爪ごとの要約だけを抜き出した。"
                   "領域の多角形・中心線・局所のずれは元のファイル（Git 対象外）にある。座標は高解像度原画 DP130155 の画素（*_ref）",
        "sources": {"claw_inventory": {"path": rel(LI + "/ds32_claw_inventory.json"), "sha256": sha(LI + "/ds32_claw_inventory.json")},
                    "ids": {"path": rel(LI + "/ds32_ids.json"), "sha256": sha(LI + "/ds32_ids.json")}},
        "removed_claws": inv["removed_claws"],
        "claws": table,
    }
    with open(EV + "/ds32_claw_table.json", "w", encoding="utf-8", newline="\n") as f:
        f.write("{\n")
        for k in ("schema", "note_ja", "sources", "removed_claws"):
            f.write(" %s: %s,\n" % (json.dumps(k), json.dumps(claw_table[k], ensure_ascii=False)))
        f.write(' "claws": [\n')
        for i, t in enumerate(table):
            f.write("  " + json.dumps(t, ensure_ascii=False) + (",\n" if i < len(table) - 1 else "\n"))
        f.write(" ]\n}\n")
    copied["ds32_claw_table.json"] = {"source": "ds32_claw_inventory.json と ds32_ids.json から抜き出した（この道具）"}

    # ---- metrics.json ----
    i1, i2, i3, i4, i5 = (items["第6節 受入%d" % k] for k in range(1, 6))
    ib = items["設計32"]
    itp = [it for it in mb["items"] if "瞬間移動 0" in it["item"]][0]
    ifl = [it for it in mb["items"] if "意図しない点滅 0" in it["item"]][0]
    i129 = items["backlog 129"]
    f1 = [it for it in mb["items"] if it["item"].startswith("修正01 指摘1")][0]
    f2 = [it for it in mb["items"] if it["item"].startswith("修正01 指摘2")][0]
    f3 = [it for it in mb["items"] if it["item"].startswith("修正01 指摘3")][0]
    ffl = [it for it in mb["items"] if it["item"].startswith("修正01 の検査")][0]
    flim = [it for it in mb["items"] if it["item"].startswith("修正01 の後に残る限界")][0]
    bound = [x for x in ids["claws"] if x.get("bound")]
    tip_pl = {}
    for x in bound:
        tip_pl[x["tip_placement"]] = tip_pl.get(x["tip_placement"], 0) + 1
    tb = [x["t_birth"] for x in bound]
    reasons = {}
    for x in corr["claws"]:
        if x["status"] == "対応なし":
            r = x["reason_ja"]
            key = ("手前の波" if r.startswith("手前の波") else "主浪の範囲と b区域の帯の外" if r.startswith("美術優先29 の主浪の範囲") else
                   "位置合わせが不確か（NCC < 0.70）" if r.startswith("位置合わせが不確か") else
                   "重複か位置合わせの誤り（claw071＝C169）" if r.startswith("重複か位置合わせの誤り") else
                   "利用者の爪どうしの重複" if "重複" in r else r)
            reasons[key] = reasons.get(key, 0) + 1
    by_row_origin = {}
    for x in inv["claws"]:
        k = "%s・%s" % (x["row"], "美術優先29" if x["origin"] == "af29" else "加えた")
        by_row_origin[k] = by_row_origin.get(k, 0) + 1
    status_counts = {}
    for x in inv["claws"]:
        status_counts[x["status"]] = status_counts.get(x["status"], 0) + 1
    ri = rc["indep_shadow_prefix01"]

    metrics = {
        "schema": "GreatWave.DS32.metrics/1",
        "number": "設計32",
        "title_ja": "目立つ白波群を選び ID で追跡する（爪の一覧の修正、計画 第6節）",
        "generated_utc": now,
        "evidence_kind_ja": "高解像度原画 DP130155 の numpy/OpenCV の計算と重ね図、主役波のパッケージ（F_final＋設計31 の T_white）の numpy の評価と点の描画、"
                            "生成器の側の独立の検査（ds32_ids_indep_check.py）、進行役の独立の検査（作り手のコードを使わない numpy。リポジトリの外）。"
                            "Unity の描画ではない。HMD 実機の結果ではない。利用者は確かめていない",
        "acceptance": {
            "ja": "計画 §2.2 の設計32 と §6 の最小の受入（Q26：この番号は最小の受入だけを満たす。修正は 1 回まで）",
            "6_1_named": {
                "rule_ja": "利用者が名指しした所（83・84・85、109・中5・110、127 の下）の前後図で、影が内側に入り、起点が口の中央にあり、取りこぼしが加わっている",
                "value": i1["value"],
                "indep_shadow_prefix01": ri["named"],
                "fix01_c105_c110": {"pre": rc["fix01_overlap"]["pre"]["C105_C110"], "post": rc["fix01_overlap"]["post"]["C105_C110"],
                                    "c107": "C105 に統合（欠番）"},
                "figures": ["fig_ds32_named_before_after.png", "fig_ds32_fix01_c105_c110.png"],
                "verdict": "合格（前後図で確かめた。進行役の目視で、利用者は未確認。修正01 の後）",
            },
            "6_2_user100": {
                "rule_ja": "利用者の 100 本のうち、一覧と対応した本数と、対応しない爪の一覧（理由つき）。位置合わせの残差を記録する",
                "summary": corr["summary"],
                "not_matched_reasons": reasons,
                "distinct_list_claws_matched": corr["notes_fix01"]["distinct_list_claws_matched"],
                "notes_fix01": corr["notes_fix01"],
                "registration_residuals": rc["registration"],
                "files": ["ds32_user100_correspondence.json"],
                "verdict": "合格（本数と理由の一覧を出した。位置合わせの不確かさは記録のみ）",
            },
            "6_3_shadow": {
                "rule_ja": cc["shadow_check_ja"],
                "threshold_choice_ja": cc["shadow_threshold_choice_ja"],
                "tested": cc["shadow_tested"], "excluded_ds32": len(cc["shadow_excluded_new"]), "excluded_af29": len(cc["shadow_excluded_af29"]),
                "counts_by_threshold": cc["shadow_counts_by_threshold"],
                "quantiles_ds32_p0_p5_p10_p25_p50": cc["shadow_included_quantiles_ds32"],
                "quantiles_af29_p0_p50_p90_p100": cc["shadow_included_quantiles_af29"],
                "indep_prefix01": {k: ri[k] for k in ("file", "rule_ja", "tested", "below_0_5", "median", "af29_median")},
                "verdict": "合格（しきい値 0.5 の読み。進行役の判断、Q24。独立の検査の別の定義では 0.5 未満が %d／%d（修正01 の前）で、定義は仕上げ32 で決め直す）" % (
                    ri["below_0_5"], ri["tested"]),
            },
            "6_4_rows": {
                "rule_ja": "列ごとの重ね図（上側・途中・船側）。右側は触らず「低優先・未修正」と明記。輪郭線とのずれは直さない",
                "figures": ["fig_ds32_rows_upper.png", "fig_ds32_rows_middle.png", "fig_ds32_rows_boat.png", "fig_ds32_rows_bregion.png",
                            "fig_ds32_rows_right_untouched.png"],
                "right_side_untouched": rc["right_side_untouched"],
                "verdict": "合格（5 枚を出した。右側の 25 本は美術優先29 の根元・先端・中心線のまま）",
            },
            "6_5_iou": {"rule_ja": "仮の定義を分母・分子に使った値と、美術優先29 の分母A・B の値を並べて記録する（合否なし）",
                        "value": cc["iou"], "verdict": "記録のみ"},
            "2_2_binding_history": {
                "rule_ja": "爪の根元を K* の水面シートの (u, v) に結び付け、全コマで ID ごとの根元・先端の位置の履歴を出す",
                "bound": ic["bound"], "unbound_right_side": len(ic["unbound"]), "frames": ic["frames"], "hz": ic["hz"],
                "t_star_frame": ic["t_star_frame"], "reprojection_tstar_display_px": ic["reprojection_tstar_display_px"],
                "tip_placement": tip_pl, "t_birth_s": {"min": min(tb), "median": float(np.median(tb)), "max": max(tb)},
                "sheet": ids["sheet"], "clock": ids["clock"],
                "verdict": "合格（numpy。右側の 25 本は主役波のシートの外なので結び付けていない）",
            },
            "teleport_0": {"rule_ja": ic["teleport_rule_ja"], "teleport_count": ic["teleport_count"], "max_moves_m": ic["max_moves_m"],
                           "sheet_max_vertex_move_m": ic["sheet_max_vertex_move_m"], "indep": {k: ii[k] for k in (
                               "root_vs_indep_eval_max_m", "root_move_over_sheet_max_frames", "root_move_max_m", "sheet_vertex_move_max_m",
                               "tip_rigid_length_err_max_m", "tip_spike_count", "claw_group_common_move_max_m", "claw_group_over_rule_a")},
                           "verdict": "合格（numpy の履歴。Unity の描画ではない）"},
            "flicker_0": {"rule_ja": ic["flicker_rule_ja"], "flicker_count": ic["flicker_count"],
                          "growth_decreasing_samples": ic["growth_decreasing_samples"],
                          "indep": {k: ii[k] for k in ("visible_vs_birth_mismatch", "visible_off_transitions")},
                          "verdict": "合格（numpy）"},
            "129": {"rule_ja": "群の瞬間的な置き換え 0（群から粒が抜けるコマ 0）", "group_member_lost_count": ic["group_member_lost_count"],
                    "indep": {k: ii[k] for k in ("claws_in_exactly_one_group", "claws_bound", "spray_in_exactly_one_group", "spray_total",
                                                 "band_vertex_duplicates")},
                    "verdict": "合格（numpy。使える水準。精度は仕上げ33）"},
            "regression_2_0": {"rule_ja": "計画 §2.0：原画視点に触れる番号では評価器を回し、合格した項目を後退させない",
                               "value_ja": "この番号は原画視点の描画を変えていない（シート・色面・場面に触れず、爪は描かない）。評価器を回す対象ではない。"
                                           "t* の原画視点の値は設計31 のまま", "verdict": "対象外（記録）"},
        },
        "design": {
            "counts": inv["counts"], "by_row_origin": by_row_origin, "status_counts": status_counts,
            "root_moved_over_8px": {k: len(v) for k, v in inv["root_moved_over_px"]["by_row"].items()},
            "removed_claws": inv["removed_claws"],
            "definition_region_ja": inv["definition_region_ja"], "definition_root_ja": inv["definition_root_ja"], "ids_ja": inv["ids_ja"],
            "groups": ids["group_counts"], "prominent_rule_ja": ids["prominent_rule_ja"],
            "claw_table": "ds32_claw_table.json",
        },
        "backlog": {
            "ja": "計画 §2.2 の設計32：95〜98・122〜129・136〜139 の前提、129（群の瞬間的な置き換え 0）",
            "items": {
                "95〜98・122〜128・136〜139": {"value_ja": "爪の一覧の修正版（173 本、主浪 148 本をシートに結び付け）と ID・群を設計33 へ渡す", "verdict": "記録のみ（前提）"},
                "129": {"value": ic["group_member_lost_count"], "verdict": "合格（numpy）"},
            },
        },
        "record_only": {
            "weighted_centroid": ic["weighted_centroid_record_only"], "weighted_centroid_note_ja": ic["weighted_centroid_note_ja"],
            "fix01_checks": {k: cc["fix01"][k] for k in ("region_overlap_pairs", "region_overlap_pairs_gt_0_2", "roots_inside_other_region",
                                                          "containment_pairs_ge_0_5", "short_below_0_5_of_af29", "continues_past_root_ge_0.6")},
            "flags_figure": "fig_ds32_fix01_flags.png",
            "limits_after_fix01": flim["value"],
            "unity_mock_hmd_ja": "Unity の再生・Mock の両眼は設計34。HMD（PS VR2）は保留（導入は利用者の手）",
        },
        "revisions": {
            "ja": "修正は 1 回（修正01）。進行役の独立の検査の必須の指摘 3 つに対するもの（Q26）",
            "fix01": {"1_c105_c110": {"judgement": f1["judgement"], "value": f1["value"]},
                      "2_truncated": {"judgement": f2["judgement"], "guard_status_counts": f2["value"]["guard_status_counts"],
                                      "lengths_px": rc["fix01_lengths_px"]},
                      "3_c169": {"judgement": f3["judgement"], "value": f3["value"]},
                      "flags": {"judgement": ffl["judgement"], "list": ffl["value"]["list"]}},
            "before_after": {
                "claws_total": [pre_inv["counts"]["total"], inv["counts"]["total"]],
                "by_row": [pre_inv["counts"]["by_row"], inv["counts"]["by_row"]],
                "root_moved_over_8px": [{k: len(v) for k, v in pre_inv["root_moved_over_px"]["by_row"].items()},
                                        {k: len(v) for k, v in inv["root_moved_over_px"]["by_row"].items()}],
                "user100_summary": [pre_corr["summary"], corr["summary"]],
                "shadow_tested": [pre_cc["shadow_tested"], cc["shadow_tested"]],
                "shadow_counts_by_threshold": [pre_cc["shadow_counts_by_threshold"], cc["shadow_counts_by_threshold"]],
                "iou_ds32_A_B": [[pre_cc["iou"]["ds32_regions_vs_A_prime"], pre_cc["iou"]["ds32_regions_vs_B_prime"]],
                                 [cc["iou"]["ds32_regions_vs_A_prime"], cc["iou"]["ds32_regions_vs_B_prime"]]],
                "iou_af29_A_B": [[pre_cc["iou"]["af29_polygons_vs_A_prime"], pre_cc["iou"]["af29_polygons_vs_B_prime"]],
                                 [cc["iou"]["af29_polygons_vs_A_prime"], cc["iou"]["af29_polygons_vs_B_prime"]]],
                "bound": [pre_ic["bound"], ic["bound"]],
                "groups": [pre_ids["group_counts"], ids["group_counts"]],
                "teleport_flicker_129": [[pre_ic["teleport_count"], pre_ic["flicker_count"], pre_ic["group_member_lost_count"]],
                                         [ic["teleport_count"], ic["flicker_count"], ic["group_member_lost_count"]]],
                "indep_root_diff_m": [pre_ii["root_vs_indep_eval_max_m"], ii["root_vs_indep_eval_max_m"]],
                "note_ja": "左が修正01 の前（Unity/Build/Design/32/list+ids_prefix01/）、右が後（list+ids/）",
            },
            "determinism": rb["determinism"],
        },
        "independent": {
            "orchestrator_ja": "進行役の独立の検査（ファイルの時刻で 20:25〜20:39、修正01 の前の出力に対して）。コードは会話の作業フォルダー（リポジトリの外）で、"
                               "コードと出力の写しは Unity/Build/Design/32/indep_check/。判定は pass = false、必須の指摘 3 つ（第 7 節と第 10 節）。"
                               "Unity・git・重い計算は使っていない",
            "orchestrator_files": {f: sha(IND + "/" + f) for f in sorted(os.listdir(IND))},
            "author_side": {"file": "ds32_ids_indep_check.json", "pass": ii["pass"]},
        },
        "discrepancies_ja": [
            "最初の部の要約は根元が 8 px 以上動いた爪を途中 16・船側 27 とするが、これは修正01 の前の値。修正01 の後は途中 %d・船側 %d（ds32_claw_inventory.json の root_moved_over_px）" % (
                len(inv["root_moved_over_px"]["by_row"]["途中"]), len(inv["root_moved_over_px"]["by_row"]["船側"])),
            "list+ids/metrics.json の「修正01 の後に残る限界」は先端が根元の深さの面にある爪を 22 本とするが、修正01 の後の ds32_ids.json では %d 本（%d 本のうち。修正01 の前は 22／150）" % (
                tip_pl.get("depth_plane", 0), len(bound)),
            "独立の検査の報告は C110 の中心線の 75%% が C105 の領域の中とするが、記録の時に多角形を塗って数えると %.2f（塗り方の違い。領域の重なり 549／710 px は同じ）" % (
                rc["fix01_overlap"]["pre"]["C105_C110"]["centerline_b_in_region_a"]),
            "独立の検査の報告は C163 の中心線の 93%% が C169 の領域の中とするが、記録の時に数えると %.2f（塗り方の違い）" % (
                rc["fix01_overlap"]["pre"]["C169_C163"]["centerline_b_in_region_a"]),
            "作業の指示の最初の部の要約は開始を 19:42 とするが、Unity/Build/Design/32 と Tools/GWWaveGen/ds32 の作成は 19:46:28",
            "list+ids/README_interface.txt は列の数を b区域 14 とし、b_region_q16 を 15 本とする。15 本目は上側の列に入れた C172（b区域の帯にかかる加えた爪）",
            "list+ids/run.json の ds32_list_ids_run.py の SHA-256（d507afd8…）は、記録の時の変更（決定性の検査の 2 回目の出力の置き場を会話の作業フォルダーから "
            "Git 対象外の Unity/Build/Design/32/_det へ移した。処理は同じ）の前の値。今の値はこの run.json の scripts",
        ],
        "decision": {
            "adopted_ja": [
                "爪の領域は D25 の仮の定義（藍の輪郭線の内側、白＋水色の影）。断面の和で作る",
                "起点は先端から根元へたどった最初の「口」。上側の列は美術優先29 の根元のまま（計画 §6 の 2 は船側と途中の列）",
                "修正01：元の長さの 0.5 倍未満に縮む口は、両側の線が終わる所だけを口と認め、なければ美術優先29 の根元（戻した根元で他の爪の中心線の半分以上を呑むときは最初の候補）",
                "影の検査のしきい値 0.5（0.8・0.9 の数も並べる）",
                "利用者の 100 本は NCC ≥ 0.70 を確かな位置合わせとし、主浪と b区域の帯の外の爪は加えない",
                "C110・C105・127 の下（C154）は進行役の目視の種",
                "群の瞬間移動は共通の粒の重心で判定し、見える粒の重み付きの重心は記録のみ",
                "消した爪（C107 統合、C169 重複）の ID は欠番にし、加えた爪の ID は初回のまま保つ",
            ],
            "dropped_ja": [
                "上側の列の根元にも口の規則を当てる：計画 §6 の 2 の範囲の外。8 本の根元が他の爪の領域の中にあるが、仕上げ32 で見る",
                "利用者の爪で範囲の外（手前の波・主浪の左の群の下側など）のものを加える：一覧の範囲を広げるかは仕上げ32 で決める",
                "爪ごとに原画の輪郭線へ合わせる：計画で仕上げ32 へ移した",
                "C066 の根元を美術優先29 へ戻す：戻すと C057 の指を呑み込む",
            ],
            "by_ja": "進行役の判断（Q24）。利用者の決定ではない",
        },
        "handoffs": {
            "design33_ja": "根元は sheet_rc に固定し、各コマで [e1 e2 n] を作り直す。形は region_polygon_ref と centerline から。成長は tau_birth から（今の g(τ) は仮）。"
                           "先端 %d 本は根元の深さの面の上。爪ごとの幅・節などは美術優先29 の一覧から読み、C066 は代表の測定に使わない。b区域の 15 本で Q16 の浪尖の爪を扱う。"
                           "132・72 の爪のでこぼこはシートを変えずに爪と白の帯で直す" % tip_pl.get("depth_plane", 0),
            "design34_ja": "Unity の再生と Mock の両眼。瞬間移動のしきい値を爪ごとの局所の読みへ。白の帯は群の重心ではなく頂点の T_white で描く",
            "polish32_ja": "D25 の定義し直し（影の共有の水色の数え方）、爪ごとに輪郭線へ合わせる、領域の重なり・とげ・他の爪の領域の中の根元、C066・C112・C113、"
                           "根元の先で指が続く疑い 8 本、利用者の 100 本の位置合わせの不確かさ、C174 と C002、範囲の外の利用者の爪、上側の列の根元",
            "polish33_ja": "成長・曲がり・遮蔽の精度、先端がシートから浮くこと",
            "right_claws_ja": "右側の爪（C129〜C153）はブラッシュアップの最後",
            "hmd_ja": "設計08〜10（PS VR2 の導入の後）。この番号の証拠はすべて numpy",
        },
        "time": {"limit_h": 4,
                 "ja": "Q26 の日程で 4 時間（計画 §2.6 の Q26 の表、10/1 の設計32）。ファイルの時刻で 9/29 19:46:28（Unity/Build/Design/32 と Tools/GWWaveGen/ds32 の作成）"
                       "〜20:21（最初の出力）、進行役の独立の検査 20:25〜20:39、修正01 は 20:43（前の出力の写し list+ids_prefix01 の作成。最初の試みは途中で止まった）"
                       "〜23:04（修正01 の後の run.json）。記録は 23:08〜23:30 ごろ（この道具・Design_32_ja.md・コミットの一覧）。"
                       "壁の時計で 19:46〜23:04 は 3 時間 18 分、記録を含めて約 3 時間 45 分で、4 時間の上限の内。"
                       "20:43〜22:50 には、途中で止まった修正01 の最初の試みの時間が入っていて、作業の時間とは分けられない"},
    }
    jdump(metrics, EV + "/metrics.json")

    # ---- run.json ----
    scripts = sorted(f for f in os.listdir(HERE) if f.endswith(".py"))
    run = {
        "schema": "GreatWave.DS32.run/1",
        "number": "設計32",
        "generated_utc": now,
        "machine": platform.platform(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "opencv": cv2.__version__,
        "ffmpeg": FFMPEG,
        "commands": [c["command"] + ("（%s s）" % c["elapsed_s"] if c.get("elapsed_s") is not None else "（" + c.get("note_ja", "") + "）")
                     for c in rb["commands"]] + [
            "（まとめて）py -3.10 Tools/GWWaveGen/ds32/ds32_list_ids_run.py --skip-register --determinism",
            "（進行役の独立の検査：リポジトリの外の numpy。コードと出力の写しは Unity/Build/Design/32/indep_check/）",
            "（記録）py -3.10 -B Tools/GWWaveGen/ds32/ds32_record.py",
        ],
        "scripts": {"Tools/GWWaveGen/ds32/" + f: sha(HERE + "/" + f) for f in scripts},
        "scripts_at_pipeline_run": rb["code_sha256"],
        "scripts_note_ja": "ds32_list_ids_run.py は記録の時に、決定性の検査の 2 回目の出力の置き場（会話の作業フォルダー）を Git 対象外の Unity/Build/Design/32/_det へ変えた。"
                           "処理は同じで、出力は回し直していない。scripts_at_pipeline_run は修正01 の後の実行の時の値",
        "shared_modules": {p: sha(REPO + "/" + p) for p in ("Tools/GWWaveGen/ds30/ds30_checks.py", "Tools/GWWaveGen/ds30/ds30_sea.py",
                                                             "Tools/GWWaveGen/ds31/ds31_white.py", "Tools/GWContext/af27common.py",
                                                             "Tools/GWWaveGen/ds27/ds27_player_ref.py", "Tools/PaintingTruth/truthlib.py")},
        "tools_at_pipeline_run": rb["tools"],
        "inputs": rb["inputs_sha256"],
        "user_read_only_inputs": rb["user_read_only_inputs"],
        "user_files_sha256": {
            "path_pattern": "G:/research/爪形分析/final_100_claws_centerlines_from_fill_masks_v3/<claw001〜claw100>/original.png と fill_mask.png",
            "note_ja": "読み取りのみ（Q8・D14/D23）。画像とマスクは複製していない。値は ds32_user100_registration.json の user_files_sha256 の写し",
            "files": jload(LI + "/ds32_user100_registration.json")["user_files_sha256"],
        },
        "claw_analysis_readme": {"path": CLAW_README, "sha256": sha(CLAW_README) if os.path.isfile(CLAW_README) else None,
                                 "note_ja": "Q8 の例外の 1 ファイル（読み取りのみ）。爪形分析の説明として読んだ"},
        "determinism": rb["determinism"],
        "build_outputs": {"list+ids/" + k: v["sha256"] for k, v in rb["outputs"].items()},
        "build_outputs_prefix01": {f: sha(PRE + "/" + f) for f in sorted(os.listdir(PRE)) if os.path.isfile(PRE + "/" + f)},
        "record_outputs": {f: sha(REC + "/" + f) for f in sorted(os.listdir(REC))},
        "indep_check": {f: sha(IND + "/" + f) for f in sorted(os.listdir(IND))},
        "evidence": {f: sha(EV + "/" + f) for f in sorted(os.listdir(EV)) if f not in ("run.json",)},
        "evidence_sources": {**pngs, **copied, "ds32_ids_30fps.mp4": video},
        "not_in_repo_ja": "一覧と ID の全出力（Unity/Build/Design/32/list+ids/。一覧の本体 ds32_claw_inventory.json、ID の ds32_ids.json、履歴の bin、"
                          "位置合わせ ds32_user100_registration.json、全解像度の図と動画）、修正01 の前の出力（list+ids_prefix01/）、"
                          "独立の検査のコードと出力の写し（indep_check/）、記録の数え（record/）は Git 対象外。"
                          "爪形分析（G:/research/爪形分析）の画像とマスクは複製していない（派生の数値と、パス・SHA-256 だけ）。参照モデル・利用者の解算・写真のフォルダーは使っていない。"
                          "Unity・Blender・Houdini は使っていない",
    }
    jdump(run, EV + "/run.json")
    print("DS32_RECORD_DONE", len(os.listdir(EV)), "files")
    print(json.dumps({"video": video, "indep": {k: ri[k] for k in ("tested", "below_0_5", "median")}, "right": rc["right_side_untouched"],
                      "overlap": rc["fix01_overlap"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
