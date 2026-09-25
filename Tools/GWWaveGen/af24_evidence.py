# -*- coding: utf-8 -*-
"""編号24 の証拠をまとめる（Unity 描画のあとに実行）。

入力（Git 対象外の Unity/Build/ArtFirst/24/）:
    frames_painting/f_0000..0509.png, frames_boat/..., 24_side_tstar.png, 24_painting_tstar_ids.png, 24_idmap.json,
    af24_build_report.json, af24_render_report.json, wave/wave_v0.gwb, wave/wave_v0_meta.json, wave/continuity.json
出力:
    Docs/Evidence/ArtFirst/24/  24_painting_tstar.png, 24_painting_overlay.png, 24_painting_contour_overlay.png,
                                24_lip_closeup_x2.png, 24_boat_tstar.png, 24_side_tstar.png,
                                24_formation_painting.mp4, 24_formation_boat.mp4, metrics.json, run.json
    Unity/Build/ArtFirst/24/eval/  評価器の出力（metrics.json・偏差の重ね図）

使い方（リポジトリ根で）: py -3.10 Tools/GWWaveGen/af24_evidence.py [--ffmpeg PATH] [--ffprobe PATH]
    ffmpeg の場所は --ffmpeg、環境変数 GW_FFMPEG、既定値（DEFAULT_FFMPEG）の順に決める。
    ffprobe は --ffprobe、環境変数 GW_FFPROBE、ffmpeg と同じフォルダーの ffprobe の順に決める。
"""
import argparse
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

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth"))
import truthlib as T  # noqa: E402

BUILD = os.path.join(REPO, "Unity", "Build", "ArtFirst", "24")
EVID = os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "24")
DEFAULT_FFMPEG = r"G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe"
PREVIEW_GOAL_PX = 12.0
# 同じ問題の修正回数（AGENTS.md の損切り規則。上限 2）。修正1回目＝編号23の真値 v0.1 に合わせた K* の作り直し。
REVISION_ROUND = 1
# 唇の拡大図の範囲（表示 px、原画視点、x0, y0, x1, y1）と倍率。稜線から唇先端 (1107.9, 352.9)・天井・72 の上部までを含む。
LIP_BOX = (690, 40, 1250, 560)
LIP_ZOOM = 2


def resolve_ffmpeg(arg_ffmpeg, arg_ffprobe):
    """ffmpeg・ffprobe の場所と、その決め方（引数／環境変数／既定値）を返す。"""
    if arg_ffmpeg:
        ff, ff_src = arg_ffmpeg, "--ffmpeg"
    elif os.environ.get("GW_FFMPEG"):
        ff, ff_src = os.environ["GW_FFMPEG"], "環境変数 GW_FFMPEG"
    else:
        ff, ff_src = DEFAULT_FFMPEG, "既定値（af24_evidence.py の DEFAULT_FFMPEG）"
    if arg_ffprobe:
        fp, fp_src = arg_ffprobe, "--ffprobe"
    elif os.environ.get("GW_FFPROBE"):
        fp, fp_src = os.environ["GW_FFPROBE"], "環境変数 GW_FFPROBE"
    else:
        d, b = os.path.split(ff)
        fp = os.path.join(d, b.lower().replace("ffmpeg", "ffprobe")) if d else "ffprobe"
        fp_src = "ffmpeg と同じフォルダー" if d else "PATH 上の ffprobe"
    return {"ffmpeg": ff, "ffmpeg_source": ff_src, "ffprobe": fp, "ffprobe_source": fp_src}


def gwb_vertex(meta, frame, vid):
    """wave_v0.gwb から 1 フレーム・1 頂点の位置を読む（書式は wave_v0_meta.json の format_ja）。"""
    n = int(meta["vertex_count"])
    off = 32 + n * 2 * 4 * 2 + int(meta["triangle_count"]) * 3 * 4 + (int(frame) * n + int(vid)) * 3 * 4
    with open(os.path.join(BUILD, "wave", meta["file"]), "rb") as f:
        f.seek(off)
        return np.frombuffer(f.read(12), "<f4").astype(np.float64)


def continuity_note_ja(cont_all, meta, spec):
    """連続性の注記を continuity.json の値から作る（固定の文面にしない）。"""
    fr = cont_all["frames"]
    s = cont_all["summary"]
    nu = int(meta["nu"])
    v0, v1 = meta["profile"]["visible_index_range"]
    flips = [(r["i"], r["flipped_normals"]) for r in fr if r.get("flipped_normals", 0) > 0]
    if flips:
        t1 = "法線反転（前フレームとの頂点法線の内積 < 0）は計 %d 頂点・フレーム（フレーム（頂点数）%s）。" % (
            s["flipped_normals_total"], "・".join("%d（%d）" % f for f in flips))
    else:
        t1 = "法線反転（前フレームとの頂点法線の内積 < 0）は全 %d フレームで 0。" % len(fr)
    k = int(s["max_step_frame"])
    vid = int(fr[k]["max_step_vertex"])
    row, col = divmod(vid, nu)
    where = "原画輪郭に対応する列" if v0 <= col <= v1 else ("左の延長・平らな海の列" if col < v0 else "右の延長・平らな海の列")
    x, y, z, _, _ = T.project_world(spec, gwb_vertex(meta, k, vid)[None, :])
    W, H = spec["display_frame"]["width"], spec["display_frame"]["height"]
    onscreen = bool(z[0] > 0 and -0.5 <= x[0] <= W - 0.5 and -0.5 <= y[0] <= H - 0.5)
    t2 = ("30 Hz の最大変位は、原画輪郭に対応する列（%d〜%d）で %.2f m、全頂点で %.2f m（フレーム %d、行 %d・列 %d、%s。"
          "PaintingCam の表示 px (%.0f, %.0f)、%s）。目安 0.6 m は編号30の基準で、ここでは記録のみ。" % (
              v0, v1, s["max_step_contour_cols_m"], s["max_step_m"], k, row, col, where, x[0], y[0],
              "画面内" if onscreen else "画面外"))
    return t1 + t2


def evaluator_status_ja(em):
    """評価器の provisional の値から、証拠と記録に書く一文を作る（文面を固定で書かない）。"""
    g = em.get("gate", {})
    if em.get("provisional") is False:
        return ("評価器の判定は暫定ではない（provisional: false）。編号23の較正門（%s）は全項目合格で、"
                "門を回した時の真値（truth_manifest.json・painting_truth.json の SHA-256）が今と一致した。"
                "ただし 24 はプレビューなので、評価器の合否は採らず記録だけにする。" % g.get("path", "?"))
    return ("評価器の判定は暫定（provisional: true）。理由：%s（較正門 %s）。24 はプレビューなので、いずれにせよ合否は採らない。"
            % (g.get("refused_ja", "不明"), g.get("path", "?")))


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("失敗: %s\n%s" % (" ".join(cmd), r.stderr[-2000:]))
    return r.stdout


def encode_mp4(ff, frames_dir, out, crf):
    run([ff["ffmpeg"], "-y", "-loglevel", "error", "-framerate", "30", "-i", os.path.join(frames_dir, "f_%04d.png"),
         "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", out])
    info = json.loads(run([ff["ffprobe"], "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                           "stream=codec_name,width,height,r_frame_rate,nb_read_frames,duration", "-of", "json", out]))
    return info["streams"][0]


def frames_digest(d):
    h = hashlib.sha256()
    names = sorted(f for f in os.listdir(d) if f.endswith(".png"))
    for n in names:
        h.update(n.encode())
        with open(os.path.join(d, n), "rb") as f:
            h.update(hashlib.sha256(f.read()).digest())
    return {"count": len(names), "sha256_of_sorted_name_and_file_sha256": h.hexdigest()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crf", type=int, default=23)
    ap.add_argument("--ffmpeg", default=None, help="ffmpeg の実行ファイル（省略時は環境変数 GW_FFMPEG、なければ既定値）")
    ap.add_argument("--ffprobe", default=None, help="ffprobe の実行ファイル（省略時は環境変数 GW_FFPROBE、なければ ffmpeg と同じフォルダー）")
    a = ap.parse_args()
    ff = resolve_ffmpeg(a.ffmpeg, a.ffprobe)
    for k in ("ffmpeg", "ffprobe"):
        if not os.path.isfile(ff[k]) and shutil.which(ff[k]) is None:
            raise SystemExit("%s が見つかりません（%s）: %s" % (k, ff[k + "_source"], ff[k]))
    os.makedirs(EVID, exist_ok=True)
    spec = T.load_spec()
    fm = T.FrameMap(spec)
    rep_b = T.load_json(os.path.join(BUILD, "af24_build_report.json"))
    rep_r = T.load_json(os.path.join(BUILD, "af24_render_report.json"))
    meta = T.load_json(os.path.join(BUILD, "wave", "wave_v0_meta.json"))
    cont_all = T.load_json(os.path.join(BUILD, "wave", "continuity.json"))
    cont = cont_all["summary"]
    tf = int(meta["t_star_frame"])

    # 1) 静止画（Unity の実描画をそのまま複製）
    src_p = os.path.join(BUILD, "frames_painting", "f_%04d.png" % tf)
    src_b = os.path.join(BUILD, "frames_boat", "f_%04d.png" % tf)
    shutil.copyfile(src_p, os.path.join(EVID, "24_painting_tstar.png"))
    shutil.copyfile(src_b, os.path.join(EVID, "24_boat_tstar.png"))
    shutil.copyfile(os.path.join(BUILD, "24_side_tstar.png"), os.path.join(EVID, "24_side_tstar.png"))
    rgb = T.imread_rgb(src_p)
    same_p = bool(np.array_equal(rgb, T.imread_rgb(os.path.join(BUILD, "24_painting_tstar_direct.png"))))
    same_b = bool(np.array_equal(T.imread_rgb(src_b), T.imread_rgb(os.path.join(BUILD, "24_boat_tstar_direct.png"))))

    # 2) 原画 50% 重ね（原画は縦 1080・幅 1606 の中央、左右 157 px の黒帯は描画を暗くする）
    _, disp = T.painting_display(spec, fm)
    ov = rgb.astype(np.float32)
    x0, x1 = fm.x0, fm.x1
    ov[:, x0:x1 + 1] = 0.5 * ov[:, x0:x1 + 1] + 0.5 * disp[:, x0:x1 + 1].astype(np.float32)
    ov[:, :x0] *= 0.35
    ov[:, x1 + 1:] *= 0.35
    ov = np.clip(np.round(ov), 0, 255).astype(np.uint8)
    cv2.putText(ov, "24 main wave v0 (Unity PC offscreen render, t*=12.0s, PaintingCam v1) + Met JP1847 50%  / preview, not judged",
                (170, 1062), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    # 人が見るための重ね図なので 256 色 PNG にする（文字色はそのまま残す）。測定には使わない。
    T.save_png_reserved(os.path.join(EVID, "24_painting_overlay.png"), ov, [(255, 255, 255)])

    # 3) 評価器（ID モード、包絡版で判定・爪入り版は記録）
    eval_dir = os.path.join(BUILD, "eval")
    os.makedirs(eval_dir, exist_ok=True)
    eval_cmd = ["py", "-3.10", "Tools/PaintingTruth/evaluate.py", "--render", T.repo_rel(src_p),
                "--ids", T.repo_rel(os.path.join(BUILD, "24_painting_tstar_ids.png")),
                "--idmap", T.repo_rel(os.path.join(BUILD, "24_idmap.json")),
                "--out-dir", T.repo_rel(eval_dir), "--name", "24_painting_tstar"]
    subprocess.run([sys.executable] + eval_cmd[2:], check=True, cwd=REPO)
    em = T.load_json(os.path.join(eval_dir, "metrics.json"))

    def contour(tid, ver="envelope"):
        for k, it in em["items"].items():
            for m in it["measures"]:
                if m.get("target") == tid and m.get("version") == ver:
                    return m
        return None

    ovl =cv2.imdecode(np.fromfile(os.path.join(eval_dir, "24_painting_tstar_overlay.png"), np.uint8), cv2.IMREAD_UNCHANGED)
    cv2.imencode(".png", ovl)[1].tofile(os.path.join(EVID, "24_painting_contour_overlay.png"))
    status_ja = evaluator_status_ja(em)

    # 3b) 唇の拡大図（左：評価器の偏差図を 2 倍、画素は最近傍で拡大。右：Unity 描画と原画の 50% 重ね）。人が見るための図。
    bx0, by0, bx1, by1 = LIP_BOX
    ovl_rgb = ovl[..., :3][..., ::-1] if ovl.ndim == 3 else np.dstack([ovl] * 3)
    left = cv2.resize(np.ascontiguousarray(ovl_rgb[by0:by1, bx0:bx1]), None, fx=LIP_ZOOM, fy=LIP_ZOOM, interpolation=cv2.INTER_NEAREST)
    blend = (0.5 * rgb.astype(np.float32) + 0.5 * disp.astype(np.float32))[by0:by1, bx0:bx1]
    rs = 1.35
    right = cv2.resize(np.clip(np.round(blend), 0, 255).astype(np.uint8), None, fx=rs, fy=rs, interpolation=cv2.INTER_LINEAR)
    canvas = np.full((fm.H, fm.W, 3), 24, np.uint8)
    canvas[20:20 + left.shape[0], 10:10 + left.shape[1]] = left
    rx = 30 + left.shape[1]
    canvas[20:20 + right.shape[0], rx:rx + right.shape[1]] = right

    def envmax(tid):
        m = contour(tid)
        return m["value_max_px"] if m else float("nan")

    # 右の図の下に収まるよう、1 行を 64 文字程度までにする（cv2.putText は日本語を描けないので英数字だけ）。
    lines = ["24 main wave v0, revision %d / preview, not judged" % REVISION_ROUND,
             "Unity PC offscreen render, t*=12.0s, PaintingCam v1",
             "left: evaluator overlay x%d, display px x%d-%d y%d-%d" % (LIP_ZOOM, bx0, bx1, by0, by1),
             "  cyan=truth  green<=2px  yellow<=4px  red>4px",
             "right: render 50%% + Met JP1847 50%%, same box x%.2f" % rs,
             "envelope max px: 131 %.2f / 132 %.2f / 72 %.2f" % (envmax("131"), envmax("132"), envmax("72")),
             "evaluator provisional: %s (truth %s)" % (str(em.get("provisional")).lower(), em["truth"]["version"])]
    for i, s in enumerate(lines):
        cv2.putText(canvas, s, (rx, 20 + right.shape[0] + 44 + 36 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (235, 235, 235), 1, cv2.LINE_AA)
    T.imwrite(os.path.join(EVID, "24_lip_closeup_x%d.png" % LIP_ZOOM), canvas)

    # 4) 動画
    mp4 = {}
    for view in ("painting", "boat"):
        out = os.path.join(EVID, "24_formation_%s.mp4" % view)
        mp4[view] = encode_mp4(ff, os.path.join(BUILD, "frames_" + view), out, a.crf)
        mp4[view]["bytes"] = os.path.getsize(out)

    # 5) 項目別の値

    items = {}
    for tid in ("78", "130", "131", "132", "72"):
        m = contour(tid)
        mc = contour(tid, "claws")
        items[tid] = {"backlog": int(tid), "value": {"max_px": m["value_max_px"], "p95_px": m["p95_px"], "p50_px": m["p50_px"],
                                                     "worst_display_xy": m.get("worst_display_xy"),
                                                     "claws_version_max_px（記録）": mc["value_max_px"] if mc else None},
                      "preview_goal_px": PREVIEW_GOAL_PX, "preview_goal_met": bool(m["value_max_px"] <= PREVIEW_GOAL_PX),
                      "verdict": "record-only（プレビュー。合否判定なし。判定は編号26で ≤4 px）",
                      "evaluator_raw_verdict_not_adopted": m["verdict"]}
    m71 = contour("71")
    items["71"] = {"backlog": 71, "value": {"max_px": m71["value_max_px"], "p95_px": m71["p95_px"], "iou_region71_clip": m71.get("iou"),
                                            "worst_display_xy": m71.get("worst_display_xy")},
                   "verdict": "record-only（プレビュー）",
                   "note_ja": "71 の真値の下辺は原画の前景の波・暗い空との境。v0 の場面は前景の旧うねり（M1 の仮形状）と参照海面のままなので、下辺付近の差は主役波の形ではない。"}
    ids = T.imread_rgb(os.path.join(BUILD, "24_painting_tstar_ids.png"))
    mid = np.all(ids == np.array([0, 255, 0], np.uint8), -1)
    ys, xs = np.nonzero(mid)
    boat_bbox = [float(xs.min()) / 2, float(ys.min()) / 2, float(xs.max()) / 2, float(ys.max()) / 2] if len(xs) else None
    other = np.all(ids == 0, -1).reshape(fm.H, 2, fm.W, 2).mean((1, 3)) > 0.5
    main_cols = other[:, 400:1100]
    top = int(np.argmax(main_cols.any(1)))
    items["69"] = {"backlog": 69, "value": {"right_boat_bbox_display_px": boat_bbox,
                                            "right_boat_inside_frame": bool(boat_bbox and boat_bbox[0] > 0 and boat_bbox[2] < fm.W - 1 and boat_bbox[1] > 0 and boat_bbox[3] < fm.H - 1),
                                            "wave_top_display_y": top},
                   "verdict": "record-only（プレビュー。右船は M1 Revision01 の仮配置のまま）"}
    items["70"] = {"backlog": 70, "value": {"crest_height_above_sea_m": meta["profile"]["crest_height_m"],
                                            "right_boat_length_m": 18.0, "right_boat_length_source_ja": "boat_blockout 全長 10 m × 配置倍率 1.8（15_revision_layout.json）",
                                            "wave_height_exceeds_boat_length": bool(meta["profile"]["crest_height_m"] > 18.0)},
                   "verdict": "record-only（プレビュー。船の寸法・配置は編号27で見直す）"}
    items["94"] = {"backlog": 94, "value": {"painting_cam": {k: spec["painting_cam"][k] for k in ("position", "target", "vertical_fov_deg", "near", "far")},
                                            "moved_during_capture": False},
                   "verdict": "record-only（構成上、510 フレームとも同じカメラ。揺れなし）"}
    items["68"] = {"backlog": 68, "value": {"same_mesh_same_frame_both_views": True, "views": ["PaintingCam v1", "船上座席（15_revision_layout.json eyeWorld）"]},
                   "verdict": "record-only（同じ網格・同じフレームを両視点で描画）"}
    items["80_106_107_111"] = {
        "backlog": [80, 106, 107, 111],
        "value": {"vertex_count_constant_numpy": cont["vertex_count_constant"], "index_count_constant_numpy": cont["index_count_constant"],
                  "vertex_count_constant_unity": rep_r["vertexCountConstant"], "index_count_constant_unity": rep_r["indexCountConstant"],
                  "nan_numpy": cont["nan_total"], "non_finite_unity": rep_r["nonFiniteVertices"],
                  "flipped_normals_vertex_frames": cont["flipped_normals_total"], "min_normal_dot": cont["min_normal_dot"],
                  "self_intersections_sampled_rows": cont["self_intersections_sampled_total"],
                  "self_intersections_all_rows_tstar": cont["self_intersections_all_rows_tstar"],
                  "max_step_m_30hz_all_vertices": cont["max_step_m"], "max_step_frame": cont["max_step_frame"],
                  "max_step_m_30hz_contour_columns": cont["max_step_contour_cols_m"],
                  "tstar_vs_Kstar_max_m": cont["tstar_vs_Kstar_max_m"],
                  "rendered_frames": rep_r["renderedFrames"], "mp4_frames": {k: int(v.get("nb_read_frames", 0)) for k, v in mp4.items()}},
        "verdict": "record-only（プレビュー。形成の判定は編号30）",
        "note_ja": continuity_note_ja(cont_all, meta, spec)}
    items["colours_record"] = {"value": {k: {"dE00": v["value"], "render_lab": v["render_lab"]} for k, v in
                                         ((m["target"], m) for it in em["items"].values() for m in it["measures"] if "render_lab" in m)},
                               "verdict": "record-only（仮の平塗り。色の判定は編号28）"}

    M = {
        "schema": "GreatWave.Step24.metrics/1",
        "number": "24（最初の画面：主役波 v0）",
        "generated_utc": now(),
        "evidence_kind_ja": "Unity 6000.4.3f1 Editor の batchmode による PC オフスクリーン描画（Camera.Render → RenderTexture → PNG）と numpy の連続性検査。HMD 実機の結果ではない。",
        "revision_round": REVISION_ROUND,
        "preview_ja": "プレビュー・合否判定なし。v0 の目標は輪郭の最大 ≤12 px（参考）。判定は編号26（≤4 px）。" + status_ja,
        "t_star_s": 12.0, "t_star_frame": tf,
        "evaluator": {"command": " ".join(eval_cmd), "mode": em["input"]["mode"], "provisional": em["provisional"],
                      "status_ja": status_ja, "truth_version": em["truth"]["version"],
                      "truth_manifest_sha256": em["truth"]["manifest_sha256"], "judged_version": em["truth"]["judged_version"],
                      "gate": {k: em.get("gate", {}).get(k) for k in ("path", "sha256", "gate_all_pass", "gate_complete",
                                                                      "truth_unchanged_since_gate", "all_pass")}},
        "preview_goal_px": PREVIEW_GOAL_PX,
        "main_wave_contours_max_px": {k: items[k]["value"]["max_px"] for k in ("78", "130", "131", "132", "72")},
        "main_wave_contours_p95_px": {k: items[k]["value"]["p95_px"] for k in ("78", "130", "131", "132", "72")},
        "preview_goal_met_all": all(items[k]["preview_goal_met"] for k in ("78", "130", "131", "132", "72")),
        "determinism": {"painting_loop_frame_equals_direct_render": same_p, "boat_loop_frame_equals_direct_render": same_b},
        "id_image_distinct_colours": rep_r["idDistinctColors"],
        "items": items,
    }
    T.save_json(os.path.join(EVID, "metrics.json"), M)

    # 6) run.json
    ins = ["Tools/GWWaveGen/gw_wavegen.py", "Tools/GWWaveGen/params_v0.json", "Tools/GWWaveGen/af24_evidence.py",
           "Tools/GWWaveGen/run_af24.ps1",
           "Tools/PaintingTruth/painting_truth.json", "Tools/PaintingTruth/truthlib.py", "Tools/PaintingTruth/evaluate.py",
           "Tools/PaintingTruth/manual_annotations.json",
           "Tools/PaintingTruth/targets/main_wave_outline_envelope.json", "Tools/PaintingTruth/targets/main_wave_outline_claws.json",
           "Tools/PaintingTruth/targets/truth_manifest.json", "Docs/Evidence/ArtFirst/23/23_gate.json",
           "Docs/Evidence/M1/Revision01/15_revision_layout.json", "Docs/References/Met_JP1847.jpg",
           "Unity/Assets/GreatWave/ArtFirst/Editor/AF24FirstLight.cs", "Unity/Assets/GreatWave/ArtFirst/Scripts/AF24WavePlayer.cs",
           "Unity/Assets/GreatWave/ArtFirst/Shaders/AF24Palette.shader", "Unity/Assets/GreatWave/ArtFirst/Shaders/AF24IdFlat.shader",
           "Unity/Assets/GreatWave/ArtFirst/Materials/AF24_Palette.mat", "Unity/Assets/GreatWave/ArtFirst/Materials/AF24_SeaFlat.mat",
           "Unity/Assets/GreatWave/Scenes/Tests/AF24_FirstLight.unity",
           "Unity/Assets/GreatWave/Scenes/Tests/M1_StaticComposition_Revision01.unity"]
    outs = sorted(os.path.join(EVID, f) for f in os.listdir(EVID) if f != "run.json")
    bl = {"Unity/Build/ArtFirst/24/wave/wave_v0.gwb": meta["sha256"]}
    for f in ("wave/wave_v0_meta.json", "wave/continuity.json", "af24_build_report.json", "af24_render_report.json",
              "24_painting_tstar_ids.png", "24_idmap.json", "24_painting_tstar_direct.png", "24_boat_tstar_direct.png",
              "eval/metrics.json", "eval/24_painting_tstar_overlay.png"):
        bl["Unity/Build/ArtFirst/24/" + f] = T.sha256_file(os.path.join(BUILD, f))
    ffv = run([ff["ffmpeg"], "-version"]).splitlines()[0]
    import PIL
    R = {
        "schema": "GreatWave.Step24.run/1",
        "generated_utc": now(),
        "cwd": "リポジトリ根（G:/Unity/GreatWave_2026_Fresh）",
        "commands": [
            "py -3.10 Tools/GWWaveGen/gw_wavegen.py --preview --export",
            "E:/6000.4.3f1/Editor/Unity.exe -batchmode -projectPath G:/Unity/GreatWave_2026_Fresh/Unity -executeMethod GreatWave.ArtFirst.EditorTools.AF24FirstLight.BuildAndRender -logFile Unity/Build/ArtFirst/24/unity_af24_render.log -quit",
            "py -3.10 Tools/GWWaveGen/af24_evidence.py（内部で evaluate.py と ffmpeg を呼ぶ。ffmpeg は --ffmpeg／環境変数 GW_FFMPEG／既定値の順）",
            "まとめて: powershell -File Tools/GWWaveGen/run_af24.ps1 [-Ffmpeg <ffmpeg.exe>]",
        ],
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__, "pillow": PIL.__version__,
                  "unity": rep_r["unity"], "unity_graphics": "%s / %s / %s" % (rep_r["device"], rep_r["graphicsApi"], rep_r["colorSpace"]),
                  "ffmpeg": ffv, "os": platform.platform(), "houdini": None, "blender": None},
        "ffmpeg_resolved": ff,
        "unity_build_report": rep_b,
        "unity_render_report": rep_r,
        "mp4": mp4,
        "inputs_sha256": {p: T.sha256_file(T.repo_abs(p)) for p in ins if os.path.exists(T.repo_abs(p))},
        "outputs_sha256": {T.repo_rel(p): T.sha256_file(p) for p in outs},
        "not_committed_build_outputs_sha256": bl,
        "not_committed_frames": {"frames_painting": frames_digest(os.path.join(BUILD, "frames_painting")),
                                 "frames_boat": frames_digest(os.path.join(BUILD, "frames_boat"))},
        "not_committed_ja": "Unity/Build/ArtFirst/24/（.gitignore の /Unity/Build/ で対象外）。.gwb は約 %.0f MB で、gw_wavegen.py と params_v0.json から決定的に再生成できる。" % (meta["bytes"] / 1e6),
    }
    T.save_json(os.path.join(EVID, "run.json"), R)
    tot = sum(os.path.getsize(os.path.join(EVID, f)) for f in os.listdir(EVID))
    print("AF24_EVIDENCE_DONE total_bytes=%d" % tot)
    print(json.dumps({"contours_max": M["main_wave_contours_max_px"], "p95": M["main_wave_contours_p95_px"], "71": items["71"]["value"],
                      "mp4": {k: (v["bytes"], v.get("nb_read_frames"), v.get("duration")) for k, v in mp4.items()},
                      "determinism": M["determinism"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
