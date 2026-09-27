# -*- coding: utf-8 -*-
"""設計29：証拠（図・並べた動画・metrics.json・run.json）と、利用者向けの試写（中国語の名前）を書く。

入力（どれも読むだけ。Git 対象外の Unity/Build/Design/29/ と設計28 のパッケージ）
  Unity/Build/Design/29/unity/<組>/            DS29Render の出力（t28・stills・video・gpu_capture・ds29_render_report.json・ds27_tstar_remeasure.json）
  Unity/Build/Design/29/<版>/measure/<網>.json  作り手の測定（ds29_measure.py：P13 の移し、薄膜、波頭の欠落、t* の K* との差、Hermite、GPU の見積もり）
  Unity/Build/Design/29/qa_<版>/<網>_qa.json    独立の検査器（ds29_qa.py：位相、面の反転、自己交差、座席からの射線 5 万本、唇先の厚さ、波頭）
  Unity/Build/Design/29/unity/ds29_unity_check_<版>.json  GPU の読み戻しの照合と t* の輪郭の差（ds29_unity_check.py）
  Unity/Build/Design/29/gates/                 設計28 の関門の検査器を表示の網へ当てた結果（読みが合わないことの記録）
出力
  Docs/Evidence/Design/29/：fig_ds29_density_<視点>.png（段階 a〜t* × 4 組）、fig_ds29_tstar_detail.png、ds29_compare_<視点>.mp4（1280 × 720）、
  metrics.json、run.json。--preview があれば、そのフォルダーへ中国語の名前の試写（動画・静止画）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds29/ds29_record.py --half-rev r02 --full-rev r02 [--preview <フォルダー>]
  --meta-only：図・動画・試写を作らず、metrics.json と run.json だけを書き直す（図と動画は今のファイルを一覧に載せる。レビュー対応で使った）。
  run.json の evidence は Docs/Evidence/Design/29/ の下のすべてのファイル（qa/ を含む。run.json 自身を除く）。
numpy と Pillow。ffmpeg は G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe、字形は Windows の游ゴシック（中国語は微軟雅黒）。
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import platform
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
B29 = os.path.join(REPO, "Unity", "Build", "Design", "29")
EV = os.path.join(REPO, "Docs", "Evidence", "Design", "29")
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
FONT_JA = "C:/Windows/Fonts/YuGothM.ttc"
FONT_ZH = "C:/Windows/Fonts/msyh.ttc"
STAGES = [("a", -4.433), ("b", -3.5), ("c", -2.933), ("d", -2.25), ("apex", -1.333), ("tstar", 0.0)]
STAGE_JA = {"a": "a", "b": "b", "c": "c", "d": "d", "apex": "唇先の頂点", "tstar": "t*"}
STAGE_ZH = {"a": "a", "b": "b", "c": "c", "d": "d", "apex": "浪尖最高点", "tstar": "t*（原画瞬间）"}
VIEWS = [("painting", "原画視点", "原画视角", (0, 60, 1440, 870)), ("seat", "座席 v1", "座位 v1", None),
         ("seat_toward_wave", "座席から波の方向（確認用）", "从座位看来浪方向", None), ("side_left", "左の側面", "左侧面", None)]


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


def font(path, size):
    return ImageFont.truetype(path, size)


def sets_for(hrev, frev, drev):
    """並べる 4 組：原版（設計28 の K* の格子のまま）、軽量版、張り直した 240 × 400（選択肢）、約 2 倍（不採用）。"""
    s = [dict(key="src_d28", ja="原版：K* の格子 240 × 400（設計28 のまま）", zh="原版：K*网格 240×400（与设计28相同）", rev="—",
              unity=os.path.join(B29, "unity", "src_d28"), pkg=os.path.join(REPO, "Unity", "Build", "Design", "28", "art_on"),
              measure=os.path.join(B29, "r01", "measure", "src.json"), qa=os.path.join(B29, "qa_validation", "d28_art_on_qa.json"))]
    for key, name, ja, zh, rv in [("half", "half_120x200", "軽量版 120 × 200", "轻量版 120×200", hrev),
                                   ("full", "full_240x400", "張り直し 240 × 400（選択肢）", "重新布网 240×400（备选）", frev),
                                   ("double", "double_480x800", "約 2 倍 480 × 800（不採用）", "约2倍 480×800（不采用）", drev)]:
        s.append(dict(key=key, name=name, ja=ja + "・" + rv, zh=zh + "·" + rv, rev=rv, unity=os.path.join(B29, "unity", name if rv == "r01" else "%s_%s" % (name, rv)),
                      pkg=os.path.join(B29, rv, name), measure=os.path.join(B29, rv, "measure", name + ".json"), qa=os.path.join(B29, "qa_" + rv, name + "_qa.json")))
    return s


def all_candidates():
    """表のための全部の組（原版・軽量版・選択肢・不採用と、修正ごとの組）。"""
    out = sets_for("r01", "r01", "r01")[:1]
    for rv in ("r01", "r02", "r02b"):
        for x in sets_for(rv, rv, "r01")[1:3]:
            x = dict(x)
            x["key"] = "%s_%s" % (x["key"], rv)
            x["ja"] = "%s %s（%s）" % ("120 × 200" if "half" in x["name"] else "240 × 400", "張り直し", rv)
            out.append(x)
    d = dict(sets_for("r01", "r01", "r01")[3])
    d["key"] = "double_r01"
    d["ja"] = "480 × 800 張り直し（r01）"
    out.append(d)
    return out


def still_path(s, view, stage, tau):
    return os.path.join(s["unity"], "stills", "ds29_%s_%s_tau%s.png" % (view, stage, ("%+.3f" % tau) if tau != 0 else "+0.000"))


# ---------------------------------------------------------------- 図
def density_sheet(sets, view, vja, crop, out, zh=False):
    tw, th = 400, 225
    lw, hh = 96, 44
    W, H = lw + tw * len(sets), hh + th * len(STAGES)
    im = Image.new("RGB", (W, H), (250, 247, 240))
    d = ImageDraw.Draw(im)
    f = font(FONT_ZH if zh else FONT_JA, 17)
    fs = font(FONT_ZH if zh else FONT_JA, 15)
    for j, s in enumerate(sets):
        d.text((lw + j * tw + 6, 6), s["zh" if zh else "ja"], fill=(20, 20, 20), font=f)
    for i, (st, tau) in enumerate(STAGES):
        d.text((6, hh + i * th + 8), (STAGE_ZH if zh else STAGE_JA)[st], fill=(20, 20, 20), font=f)
        d.text((6, hh + i * th + 32), "τ %+.2f s" % tau, fill=(60, 60, 60), font=fs)
        for j, s in enumerate(sets):
            p = still_path(s, view, st, tau)
            if not os.path.exists(p):
                continue
            a = Image.open(p).convert("RGB")
            if crop:
                a = a.crop(crop)
            im.paste(a.resize((tw, th), Image.LANCZOS), (lw + j * tw, hh + i * th))
    for j in range(len(sets) + 1):
        d.line([(lw + j * tw, hh), (lw + j * tw, H)], fill=(250, 247, 240), width=2)
    im.save(out, optimize=True)
    return out


def tstar_detail(sets, ref, out, zh=False):
    """t* の原画視点の唇の拡大（4 組）と、基準（設計28）との違う画素（赤）、座席 v1 の t*。"""
    box = (760, 240, 1140, 480)
    z = 2
    tw, th = (box[2] - box[0]) * z // 2, (box[3] - box[1]) * z // 2
    lw, hh = 150, 40
    rows = 3
    W, H = lw + tw * len(sets), hh + th * rows
    im = Image.new("RGB", (W, H), (250, 247, 240))
    d = ImageDraw.Draw(im)
    f = font(FONT_ZH if zh else FONT_JA, 16)
    labels = ["原画视角 t*\n（唇部放大）", "与设计28\n不同的像素\n（红）", "座位 v1 t*"] if zh else ["原画視点 t*\n（唇の拡大）", "設計28 と\n違う画素（赤）", "座席 v1 t*"]
    rref = os.path.join(ref["unity"], "t28", "render")
    b0 = np.asarray(Image.open(os.path.join(rref, "af28r01_painting.png")).convert("RGB")).astype(np.int16)
    for j, s in enumerate(sets):
        d.text((lw + j * tw + 6, 8), s["zh" if zh else "ja"], fill=(20, 20, 20), font=f)
        rr = os.path.join(s["unity"], "t28", "render")
        a = Image.open(os.path.join(rr, "af28r01_painting.png")).convert("RGB")
        im.paste(a.crop(box).resize((tw, th), Image.NEAREST), (lw + j * tw, hh))
        an = np.asarray(a).astype(np.int16)
        m = np.abs(an - b0).max(-1) > 24
        vis = (b0 * 0.35).astype(np.uint8)
        vis[m] = (230, 30, 30)
        im.paste(Image.fromarray(vis).crop(box).resize((tw, th), Image.NEAREST), (lw + j * tw, hh + th))
        sa = Image.open(os.path.join(rr, "af28r01_seat.png")).convert("RGB")
        im.paste(sa.crop((0, 240, 1330, 1080)).resize((tw, th), Image.LANCZOS), (lw + j * tw, hh + 2 * th))
    for i, t in enumerate(labels):
        d.multiline_text((6, hh + i * th + 8), t, fill=(20, 20, 20), font=f, spacing=4)
    im.save(out, optimize=True)
    return out


def label_overlay(sets, W, H, path, zh=False):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font(FONT_ZH if zh else FONT_JA, 20)
    for j, s in enumerate(sets):
        x, y = (j % 2) * W // 2, (j // 2) * H // 2
        t = s["zh" if zh else "ja"]
        bb = d.textbbox((0, 0), t, font=f)
        d.rectangle([x, y, x + bb[2] + 14, y + bb[3] + 10], fill=(255, 255, 255, 200))
        d.text((x + 7, y + 4), t, fill=(10, 10, 10, 255), font=f)
    im.save(path)
    return path


def compare_video(sets, view, crop, out, overlay):
    ins = []
    for s in sets:
        ins += ["-i", os.path.join(s["unity"], "video", "ds29_%s_30fps.mp4" % view)]
    ins += ["-i", overlay]
    fc = []
    for j in range(len(sets)):
        c = "crop=%d:%d:%d:%d," % (crop[2] - crop[0], crop[3] - crop[1], crop[0], crop[1]) if crop else ""
        fc.append("[%d:v]%sscale=640:360:flags=lanczos,setsar=1[v%d]" % (j, c, j))
    fc.append("[v0][v1][v2][v3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0[g]")
    fc.append("[g][%d:v]overlay=0:0[o]" % len(sets))
    cmd = [FFMPEG, "-y", "-loglevel", "error"] + ins + ["-filter_complex", ";".join(fc), "-map", "[o]", "-c:v", "libx264", "-preset", "medium", "-crf", "24",
                                                         "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-r", "30", out]
    subprocess.run(cmd, check=True)
    return out


# ---------------------------------------------------------------- 値
def p13_row(m):
    it = m["P13"]["items"]
    return {k: dict(value=v["value"], pass_=v["pass_"], violations=(v.get("at") or {}).get("violations") if isinstance(v.get("at"), dict) else None) for k, v in it.items()}


def qa_verdicts(q):
    out = {}
    for k, v in q["verdicts"].items():
        out[k] = dict(value=v["value"], threshold=v["threshold"], pass_=v["pass"])
    return out


def film_min(m):
    out = {}
    for k, v in m["film"].items():
        pb = v.get("playback") or v.get("exact")
        if pb and "d_1.0m" in pb:
            out[k] = dict(tau=v.get("tau"), d_1m_min_m=pb["d_1.0m"]["min_m"], rows_below=pb["d_1.0m"]["rows_below_min"], d_05m_min_m=pb.get("d_0.5m", {}).get("min_m"))
    return out


def unity_row(s):
    rp = os.path.join(s["unity"], "ds29_render_report.json")
    if not os.path.exists(rp):
        return None
    r = jload(rp)
    MiB = 2 ** 20
    kp = r["driverBytesAfterKeypose"] - r["driverBytesAfterSurface"]
    tp = os.path.join(B29, "unity", "timing", os.path.basename(s["unity"]), "ds29_render_report.json")
    tr = jload(tp) if os.path.exists(tp) else r
    t = {x["view"]: dict(on_ms=round(x["medianOnMs"], 3), off_ms=round(x["medianOffMs"], 3), wave_ms=round(x["waveMs"], 3), frames=x["frames"]) for x in tr.get("timing", [])}
    t["source"] = rel(tp) if os.path.exists(tp) else rel(rp)
    return dict(report=rel(rp), report_sha256=sha(rp), rows=r["rows"], cols=r["cols"], layers=r["layers"], vertices=r["vertexCount"],
                position_buffer_mib=round(r["positionGpuBytes"] / MiB, 2), twhite_mib=round(r["whiteGpuBytes"] / MiB, 3),
                mesh_vb_mib=round(r["meshVertexBufferBytes"] / MiB, 2), mesh_ib_mib=round(r["meshIndexBufferBytes"] / MiB, 2),
                keypose_total_mib=round((r["positionGpuBytes"] + r["whiteGpuBytes"] + r["meshVertexBufferBytes"] + r["meshIndexBufferBytes"]) / MiB, 2),
                driver_delta_keypose_mib=round(kp / MiB, 2), within_512=bool((r["positionGpuBytes"] + r["whiteGpuBytes"] + r["meshVertexBufferBytes"] + r["meshIndexBufferBytes"]) / MiB <= 512),
                sdf_texture_mib_shared=round(r["sdfTextureBytes"] / MiB, 1), load_s=round(r["keyposeLoadSeconds"], 2), timing=t,
                protected_unchanged=r["protectedUnchanged"], passed=r["passed"], device=r["device"], api=r["graphicsApi"], mesh=rel(r["meshPath"]), uv3=r["uv3Source"])


def tstar_row(s):
    p = os.path.join(s["unity"], "ds27_tstar_remeasure.json")
    if not os.path.exists(p):
        return None
    r = jload(p)
    flips = {k: [r["summary_verdicts_28r01"].get(k), v] for k, v in r["summary_verdicts_ds27"].items() if r["summary_verdicts_28r01"].get(k) != v}
    big = [dict(item=b["item"], measure=b["measure"], px=b["ds27_max_px"], ref_px=b["r28r01_max_px"], diff_px=b["diff_px"]) for b in r["boundaries_vs_28r01"] if abs(b["diff_px"]) > 0.5]
    return dict(file=rel(p), worst_abs_diff_px=r["worst_abs_diff_px"], pass_=r["pass"], verdict_changes=flips, over_05px=big,
                verdicts=r["summary_verdicts_ds27"], item266_seat_bands=_266(r))


def _266(r):
    try:
        v = r["colour_265_266_267"]["266"]["ds27"]["views"]["ai_mid"]
        return dict(painting=v["painting_view"]["bands_ge_20px"], seat=v["seat_view"]["bands_ge_20px"], seat_low=v["seat_low_view"]["bands_ge_20px"])
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--half-rev", default="r02", help="軽量版の版")
    ap.add_argument("--full-rev", default="r02", help="張り直した 240 × 400 の版（選択肢）")
    ap.add_argument("--double-rev", default="r01")
    ap.add_argument("--check", default=os.path.join(B29, "unity", "ds29_unity_check.json"), help="ds29_unity_check の JSON")
    ap.add_argument("--adopt", default="src_d28", help="原版の組")
    ap.add_argument("--light", default="half_r02", help="軽量版の組")
    ap.add_argument("--preview", default=None)
    ap.add_argument("--no-video", action="store_true")
    ap.add_argument("--meta-only", action="store_true", help="metrics.json と run.json だけを書く（図・動画は今のファイル）")
    a = ap.parse_args()
    os.makedirs(EV, exist_ok=True)
    sets = sets_for(a.half_rev, a.full_rev, a.double_rev)
    ref = sets[0]
    figs, vids = [], []
    tmp = os.path.join(B29, "record_tmp")
    os.makedirs(tmp, exist_ok=True)
    if a.meta_only:
        figs = [os.path.join(EV, "fig_ds29_density_%s.png" % v) for v, vja, vzh, crop in VIEWS] + [os.path.join(EV, "fig_ds29_tstar_detail.png")]
        vids = [os.path.join(EV, "ds29_compare_%s.mp4" % v) for v in ("painting", "seat_toward_wave", "side_left")]
        missing = [x for x in figs + vids if not os.path.isfile(x)]
        if missing:
            raise SystemExit("--meta-only：図・動画がありません：%s" % missing)
    else:
        for v, vja, vzh, crop in VIEWS:
            figs.append(density_sheet(sets, v, vja, crop, os.path.join(EV, "fig_ds29_density_%s.png" % v)))
        figs.append(tstar_detail(sets, ref, os.path.join(EV, "fig_ds29_tstar_detail.png")))
        ov = label_overlay(sets, 1280, 720, os.path.join(tmp, "labels_ja.png"))
        if not a.no_video:
            for v, crop in [("painting", (0, 60, 1440, 870)), ("seat_toward_wave", None), ("side_left", None)]:
                vids.append(compare_video(sets, v, crop, os.path.join(EV, "ds29_compare_%s.mp4" % v), ov))
    # レビュー対応の図（ds29_review_checks.py render が書く。唇の端の 1:1 の切り出し）
    lip = os.path.join(EV, "fig_ds29_lipend_crops.png")
    if os.path.isfile(lip):
        figs.append(lip)

    # 値
    chk = jload(a.check)
    table = {}
    for s in all_candidates():
        m = jload(s["measure"]) if os.path.exists(s["measure"]) else None
        q = jload(s["qa"]) if os.path.exists(s["qa"]) else None
        row = dict(label_ja=s["ja"], revision=s["rev"], package=rel(s["pkg"]), unity=unity_row(s), painting_tstar=tstar_row(s))
        if m:
            row.update(vertices=m["vertices"], triangles=m["triangles"], layers=m["layers"], p13=p13_row(m), p13_fail=m["P13"]["n_fail"],
                       tstar_vs_kstar=m.get("tstar"), crest_loss={k: m["crest_loss"][k] for k in ("exact_crest_height_curled_rows", "exact_crest_height", "exact_lip_reach", "playback_crest_height_curled_rows", "playback_crest_height") if k in m["crest_loss"]},
                       film=film_min(m), hermite=m.get("hermite"), deviation_from_ds28_motion=m.get("deviation_from_ds28_motion"), gpu_estimate=m.get("gpu"), measure_file=rel(s["measure"]))
        if q:
            row.update(qa=qa_verdicts(q), qa_file=rel(s["qa"]))
        k = s["key"]
        row["gpu_readback_max_m"] = (chk["gpu"].get(k) or {}).get("max_m")
        row["outline_vs_ds28_px"] = {vv: x["max_px"] for vv, x in chk["outline_vs_ref"].get(k, {}).items()}
        table[s["key"]] = row
    lod = chk.get("outline_lod", {})
    M = dict(schema="GreatWave.DS29.metrics/1", number="設計29", title_ja="解像度の比較の後、表示用サーフェスを作る（原版と軽量版。穴・法線・薄膜・波頭の欠落）",
             generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
             evidence_kind_ja="numpy の作り手（ds29_build.py）と測定（ds29_measure.py）、独立の検査器（ds29_qa.py、Blender 5.2.2 ヘッドレスの射線 5 万本と BVH）、Unity 6000.4.3f1 の batchmode の PC オフスクリーン描画（RTX 3080、Direct3D11）。HMD 実機ではない。",
             shown_sets=[x["key"] + ("" if x["key"] == "src_d28" else "_" + x["rev"]) for x in sets], adopted=dict(original=a.adopt, light=a.light), sets=table, outline_lod=lod, unity_check=rel(a.check),
             figures=[rel(x) for x in figs], videos=[rel(x) for x in vids])
    extra = os.path.join(B29, "record_extra.json")
    if os.path.exists(extra):
        M.update(jload(extra))
    with open(os.path.join(EV, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(M, f, ensure_ascii=False, indent=1)

    # run.json
    scripts = sorted(glob.glob(os.path.join(HERE, "*.py")) + glob.glob(os.path.join(HERE, "*.json")) + glob.glob(os.path.join(HERE, "*.ps1"))
                     + glob.glob(os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design29", "**", "*.cs"), recursive=True))
    pk = []
    for s in all_candidates():
        for fn in ("ds27_keypose.json", "ds27_pos_rgba16.bin", "ds27_twhite_r32f.bin", "ds29_uv3_f32.bin", "tstar/kstar_a45.gwb"):
            p = os.path.join(s["pkg"], fn)
            if os.path.exists(p):
                pk.append(dict(path=rel(p), sha256=sha(p), bytes=os.path.getsize(p)))
    outs = []
    for s in all_candidates():
        for p in [os.path.join(s["unity"], "ds29_render_report.json"), os.path.join(s["unity"], "ds27_tstar_remeasure.json"), s["measure"], s["qa"]] + \
                 sorted(glob.glob(os.path.join(s["unity"], "video", "*.mp4"))):
            if os.path.exists(p):
                outs.append(dict(path=rel(p), sha256=sha(p), bytes=os.path.getsize(p)))
    for p in sorted(glob.glob(os.path.join(B29, "unity", "ds29_unity_check_*.json")) + glob.glob(os.path.join(B29, "gates", "*.json"))
                    + glob.glob(os.path.join(B29, "*", "ds29_build_log*.json"))
                    # 独立の検査器のまとめ（Docs/Evidence/Design/29/qa/ の元）と、レビュー対応の検査（ds29_review_checks.py）
                    + glob.glob(os.path.join(B29, "qa_*", "ds29_qa_*.json")) + glob.glob(os.path.join(B29, "qa_*", "ds29_qa_*.md"))
                    + glob.glob(os.path.join(B29, "review", "*.json"))):
        outs.append(dict(path=rel(p), sha256=sha(p), bytes=os.path.getsize(p)))
    ev = [dict(path=rel(p), sha256=sha(p), bytes=os.path.getsize(p)) for p in sorted(glob.glob(os.path.join(EV, "**", "*"), recursive=True))
          if os.path.isfile(p) and os.path.basename(p) != "run.json"]
    inputs = [os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01", "kstar", "kstar_a45.gwb"),
              os.path.join(REPO, "Unity", "Build", "ArtFirst", "28修正01", "bake", "af28r01_uvsdf_a45.bin"),
              os.path.join(REPO, "Unity", "Build", "ArtFirst", "28修正01", "bake", "af28r01_uvwarp_a45.json"),
              os.path.join(REPO, "Tools", "GWWaveGen", "ds28", "ds28_model.py"), os.path.join(REPO, "Tools", "GWWaveGen", "ds28", "ds28_params.json"),
              os.path.join(REPO, "Tools", "GWWaveGen", "ds27", "ds27_model.py"), os.path.join(REPO, "Tools", "GWWaveGen", "ds27", "ds27_gates.py"),
              os.path.join(REPO, "Tools", "GWWaveGen", "ds27", "ds27_tstar_eval.py"), os.path.join(REPO, "Tools", "GWContext", "seat_v1.json")]
    ffv = subprocess.run([FFMPEG, "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    R = dict(schema="GreatWave.DS29.run/1", number="設計29", generated_utc=M["generated_utc"], machine=platform.platform(), python=platform.python_version(),
             numpy=np.__version__, pillow=Image.__version__, unity="6000.4.3f1（Editor batchmode、PC オフスクリーン描画、RTX 3080、Direct3D11）",
             blender="5.2.2（ヘッドレス、--factory-startup）", ffmpeg=ffv, commands=jload(os.path.join(B29, "record_commands.json")) if os.path.exists(os.path.join(B29, "record_commands.json")) else [],
             scripts=[dict(path=rel(p), sha256=sha(p), bytes=os.path.getsize(p)) for p in scripts if "__pycache__" not in p],
             inputs=[dict(path=rel(p), sha256=sha(p), bytes=os.path.getsize(p)) for p in inputs if os.path.exists(p)],
             packages=pk, build_outputs=outs, evidence=ev,
             protected_ja="設計26〜28 のコミット済みのファイルは変えていない（Unity の描画は前後の SHA-256 を ds29_render_report.json に記録、場面は保存しない）。K* は読むだけ。",
             not_in_repo_ja="パッケージ・Unity の出力・検査の JSON は Git 対象外の Unity/Build/Design/29/。")
    with open(os.path.join(EV, "run.json"), "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=1)

    # 試写（中国語の名前）
    if a.preview and not a.meta_only:
        os.makedirs(a.preview, exist_ok=True)
        for v, vja, vzh, crop in VIEWS:
            density_sheet(sets, v, vzh, crop, os.path.join(a.preview, "密度对比_%s.png" % vzh), zh=True)
        tstar_detail(sets, ref, os.path.join(a.preview, "原画瞬间_唇部细节对比.png"), zh=True)
        if not a.no_video:
            ovz = label_overlay(sets, 1280, 720, os.path.join(tmp, "labels_zh.png"), zh=True)
            for v, vzh, crop in [("painting", "原画视角", (0, 60, 1440, 870)), ("seat_toward_wave", "从座位看来浪方向", None), ("side_left", "左侧面", None)]:
                compare_video(sets, v, crop, os.path.join(a.preview, "密度对比视频_%s.mp4" % vzh), ovz)
    print("DS29_RECORD_DONE figs=%d videos=%d" % (len(figs), len(vids)))


if __name__ == "__main__":
    main()
