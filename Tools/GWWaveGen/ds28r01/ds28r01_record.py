# -*- coding: utf-8 -*-
"""設計28修正01：統合の証拠を Docs/Evidence/Design/28R01/ に書く（図 2 枚、小さい動画、metrics.json、run.json）。

入力（どれも Git 対象外の Unity/Build/Design/28R01/ と 28/。読むだけ）：
  関門  gates/art_on_default.json・art_on_alt.json・art_off_default.json・ref28_art_on_default_q13table.json（ds28r01_gates.py）、
        gates_int/art_on_default.json（統合で同じ包みにもう一度走らせた値。あれば照合）
  重なり overlap/ds28r01_art_on.json・ds28_art_on.json・ds28r01_art_off.json・ds28_art_on_newwarp.json（ds28r01_overlap.py、生成器から独立）
        q13/art_on.json（動きの担当の ds28r01_q13.py）
  Unity art_on_default・art_on_alt（run_ds28r01_unity.ps1 の描画、t* の測り直し、GPU の読み戻しの照合）、ref28_art_on_stages（設計28 を同じ τ で）、
        設計28 の動画 Unity/Build/Design/28/art_on_default/video/
  粘土  clay/stills・clay/combined（確認用の描画。Blender 5.2 Workbench。描画の台本は Git 対象外の作業場所にあり、SHA-256 を run.json に書く）
  レビュー対応 review/review_ds28r01.json（ds28r01_review.py。あれば metrics.json の review_response へ）
出力：fig_ds28r01_unity_stages.png、fig_ds28r01_clay_stages.png、ds28r01_unity_compare_<視点>.mp4（4 本）、ds28r01_clay_side_follow.mp4、
      ds28r01_clay_side_follow_default_vs_alt.mp4、metrics.json、run.json。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_record.py [--clay-scripts <粘土の台本のフォルダー>]
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import platform
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
B = os.path.join(REPO, "Unity", "Build", "Design", "28R01")
B28 = os.path.join(REPO, "Unity", "Build", "Design", "28")
EV = os.path.join(REPO, "Docs", "Evidence", "Design", "28R01")
FF = r"G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe"
FM = r"C:\Windows\Fonts\YuGothM.ttc"
FB = r"C:\Windows\Fonts\YuGothB.ttc"
STAGES = [("a", -4.367), ("b", -3.517), ("c", -3.017), ("d", -2.250), ("apex", -1.180), ("tstar", 0.0)]
STAGE_JA = {"a": "a", "b": "b", "c": "c", "d": "d", "apex": "唇先の頂点", "tstar": "t*"}
UNITY_VIEWS = [("side_left", "左の側面（波の枠とともに平行移動）"), ("seat_toward_wave", "座席から波の方向（確認用の視点、前景を隠す）"),
               ("painting", "原画視点")]
VIDEO_VIEWS = [("painting", "原画視点"), ("seat", "座席 v1"), ("side_left", "左の側面"), ("seat_toward_wave", "座席から波の方向（確認用）")]


def rel(p):
    return os.path.relpath(os.path.abspath(p), REPO).replace("\\", "/")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fileinfo(p):
    return dict(path=rel(p), sha256=sha(p), bytes=os.path.getsize(p))


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def font(p, n):
    return ImageFont.truetype(p, n)


def series(p):
    J = jload(p)["series"]
    return {r: {k: np.asarray(J[r][k], float) for k in ("tau", "H_over_Hf", "Lo_over_H", "C_claw_steps", "P")} for r in ("main_159", "peak_192")}


def at(s, row, key, tau):
    return float(np.interp(tau, s[row]["tau"], s[row][key]))


def warp(p):
    J = jload(p)
    return np.asarray(J["t"]), np.asarray(J["tau"])


def tau2t(w, tau):
    wt, wtau = w
    k = int(np.argmax(wtau >= -1e-9)) + 1
    return float(np.interp(tau, wtau[:k], wt[:k]))


W_NEW = os.path.join(REPO, "Tools", "GWWaveGen", "ds28r01", "timewarp_default.json")
W_OLD = os.path.join(REPO, "Tools", "GWWaveGen", "ds27", "timewarp_default.json")
W_ALT = os.path.join(REPO, "Tools", "GWWaveGen", "ds27", "timewarp_alt.json")


# ---------------------------------------------------------------- figures
def fig_unity_stages(out):
    s01 = series(os.path.join(B, "overlap", "ds28r01_art_on.json"))
    s28 = series(os.path.join(B, "overlap", "ds28_art_on.json"))
    wn, wo = warp(W_NEW), warp(W_OLD)
    tw, th = 400, 225
    lw, hh, cap = 250, 64, 40
    rows = []
    for v, vja in UNITY_VIEWS:
        rows.append((v, vja, "設計28 既定", os.path.join(B, "ref28_art_on_stages", "stills"), s28, wo))
        rows.append((v, vja, "設計28修正01 既定", os.path.join(B, "art_on_default", "stills"), s01, wn))
    img = Image.new("RGB", (lw + 6 * tw, hh + len(rows) * (th + cap) + 60), (236, 236, 232))
    d = ImageDraw.Draw(img)
    d.text((10, 8), "設計28修正01：Unity の描画（PC オフスクリーン、HMD ではない）。設計28 と設計28修正01 の既定の動きを、同じ物理の時刻 τ（設計28修正01 で測った段階の時刻、峰の行 192）で並べる",
           font=font(FM, 20), fill=(20, 20, 20))
    for j, (k, ta) in enumerate(STAGES):
        d.text((lw + j * tw + 8, 36), "%s   τ = %+.3f s" % (STAGE_JA[k], ta), font=font(FB, 20), fill=(20, 20, 20))
    for r, (v, vja, title, sdir, s, w) in enumerate(rows):
        y0 = hh + r * (th + cap)
        d.text((10, y0 + 70), title, font=font(FB, 20), fill=(20, 20, 20))
        d.text((10, y0 + 100), vja[:12], font=font(FM, 15), fill=(60, 60, 60))
        d.text((10, y0 + 120), vja[12:], font=font(FM, 15), fill=(60, 60, 60))
        for j, (k, ta) in enumerate(STAGES):
            f = glob.glob(os.path.join(sdir, "ds27_%s_%s_tau*.png" % (v, k)))
            if len(f) != 1:
                raise SystemExit("still missing: %s %s %s" % (sdir, v, k))
            im = Image.open(f[0]).convert("RGB").resize((tw, th), Image.LANCZOS)
            img.paste(im, (lw + j * tw, y0))
            d.text((lw + j * tw + 4, y0 + th + 2), "峰の行 H/H* %.2f・Lo/H %.2f　体験の時刻 t %.2f s" % (
                at(s, "peak_192", "H_over_Hf", ta), max(0.0, at(s, "peak_192", "Lo_over_H", ta)), tau2t(w, ta)), font=font(FM, 14), fill=(20, 20, 70))
            d.text((lw + j * tw + 4, y0 + th + 20), "主断面 H/H* %.2f・Lo/H %.2f" % (
                at(s, "main_159", "H_over_Hf", ta), max(0.0, at(s, "main_159", "Lo_over_H", ta))), font=font(FM, 14), fill=(20, 20, 70))
    d.text((10, img.height - 50), "H/H* は行の t* の頂で割った頂の高さ、Lo/H は張り出し（設計26 §3.1 の定義 A）。値は ds28r01_overlap.py（生成器から独立の検査器）の 60 Hz の時系列から。t はそれぞれの版の既定の時間曲線での体験の時刻。",
           font=font(FM, 15), fill=(60, 60, 60))
    d.text((10, img.height - 28), "静止画は run_ds28r01_unity.ps1 の DS27Formation.RenderOnly（左の側面・原画視点）と DS28ReviewView.Render（座席から波の方向、船・富士・前景を隠す）。",
           font=font(FM, 15), fill=(60, 60, 60))
    img.save(out, optimize=True)


def fig_clay_stages(out):
    s01 = series(os.path.join(B, "overlap", "ds28r01_art_on.json"))
    s28 = series(os.path.join(B, "overlap", "ds28_art_on.json"))
    views = [("side_follow", "正側面・波の枠に追従（120 m、高さ 10 m、縦 30°）"), ("seat_up30", "座席の目から波の方向、仰角 30°（縦 70°）")]
    tw, th = 400, 225
    lw, hh, cap = 250, 64, 42
    rows = []
    for v, vja in views:
        rows.append((v, vja, "設計28 既定", "d28", s28))
        rows.append((v, vja, "設計28修正01 既定", "r01", s01))
    img = Image.new("RGB", (lw + 6 * tw, hh + len(rows) * (th + cap) + 56), (236, 236, 232))
    d = ImageDraw.Draw(img)
    d.text((10, 8), "粘土の確認用の描画（Blender 5.2 Workbench。美術の色・線・白はなく、形と動きだけを見るための描画で、作品の見た目ではない）",
           font=font(FB, 20), fill=(150, 30, 30))
    for j, (k, ta) in enumerate(STAGES):
        d.text((lw + j * tw + 8, 36), "%s   τ = %+.3f s" % (STAGE_JA[k], ta), font=font(FB, 20), fill=(20, 20, 20))
    for r, (v, vja, title, key, s) in enumerate(rows):
        y0 = hh + r * (th + cap)
        d.text((10, y0 + 70), title, font=font(FB, 20), fill=(20, 20, 20))
        d.text((10, y0 + 100), vja[:14], font=font(FM, 14), fill=(60, 60, 60))
        d.text((10, y0 + 120), vja[14:], font=font(FM, 14), fill=(60, 60, 60))
        for j, (k, ta) in enumerate(STAGES):
            p = os.path.join(B, "clay", "stills", key, v, "stage_%s.png" % k)
            im = Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS)
            img.paste(im, (lw + j * tw, y0))
            d.text((lw + j * tw + 4, y0 + th + 2), "峰の行 H/H* %.2f・Lo/H %.2f" % (
                at(s, "peak_192", "H_over_Hf", ta), max(0.0, at(s, "peak_192", "Lo_over_H", ta))), font=font(FM, 14), fill=(20, 20, 70))
            d.text((lw + j * tw + 4, y0 + th + 20), "主断面 H/H* %.2f・Lo/H %.2f" % (
                at(s, "main_159", "H_over_Hf", ta), max(0.0, at(s, "main_159", "Lo_over_H", ta))), font=font(FM, 14), fill=(20, 20, 70))
    d.text((10, img.height - 44), "各こまはその τ の形そのもの（パッケージを Unity の再生器と同じ Hermite と波の枠の原点で読む）。唇は画面の左を向き、波は右から左へ進む。",
           font=font(FM, 15), fill=(60, 60, 60))
    d.text((10, img.height - 24), "H/H*・Lo/H は ds28r01_overlap.py の値。粘土の動画（同じカメラ）は ds28r01_clay_side_follow.mp4（字幕は利用者に見せた中国語のまま）。",
           font=font(FM, 15), fill=(60, 60, 60))
    img.save(out, optimize=True)


# ---------------------------------------------------------------- videos
def read_frames(path, w, h):
    cmd = [FF, "-loglevel", "error", "-i", path, "-vf", "scale=%d:%d:flags=lanczos" % (w, h), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = w * h * 3
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, np.uint8).reshape(h, w, 3)
    p.wait()


def writer(path, w, h, crf):
    cmd = [FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (w, h), "-r", "30", "-i", "-",
           "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", path]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def unity_compare(view, vja, out):
    """左＝設計28 既定、右＝設計28修正01 既定（どちらも Unity の 1920×1080 の動画を 640×360 へ）。上に見出し、下に時刻。"""
    left = os.path.join(B28, "art_on_default", "video", "ds27_%s_30fps.mp4" % view)
    right = os.path.join(B, "art_on_default", "video", "ds27_%s_30fps.mp4" % view)
    wo, wn = warp(W_OLD), warp(W_NEW)
    s01 = series(os.path.join(B, "overlap", "ds28r01_art_on.json"))
    s28 = series(os.path.join(B, "overlap", "ds28_art_on.json"))
    pw, ph, top, bot = 640, 360, 30, 26
    Wd, Hd = 2 * pw, ph + top + bot
    fw = writer(out, Wd, Hd, 27)
    fl, fs = font(FB, 17), font(FM, 13)
    n = 0
    for i, (a, b) in enumerate(zip(read_frames(left, pw, ph), read_frames(right, pw, ph))):
        t = i / 30.0
        img = Image.new("RGB", (Wd, Hd), (24, 26, 30))
        img.paste(Image.fromarray(a), (0, top))
        img.paste(Image.fromarray(b), (pw, top))
        d = ImageDraw.Draw(img)
        for k, (ttl, w, s) in enumerate((("設計28 既定", wo, s28), ("設計28修正01 既定", wn, s01))):
            tau = float(np.interp(t, w[0], w[1]))
            x = k * pw
            d.text((x + 8, 5), "%s・%s" % (ttl, vja), font=fl, fill=(255, 255, 255))
            d.text((x + 8, top + ph + 5), "t %5.2f s  τ %+.3f s  峰の行 H/H* %.2f・Lo/H %.2f" % (
                t, tau, at(s, "peak_192", "H_over_Hf", tau), max(0.0, at(s, "peak_192", "Lo_over_H", tau))), font=fs, fill=(255, 235, 190))
        fw.stdin.write(np.asarray(img).tobytes())
        n += 1
    fw.stdin.close()
    fw.wait()
    return n


def unity_pixel_diff():
    """同じ体験の時刻 t（各版の既定の時間曲線）の Unity の動画のこまを比べる：f150〜f360 を 6 こまおき、960×540 に縮めて、色の差 > 0.1 の画素の割合。"""
    out = {}
    for v, _ in VIDEO_VIEWS:
        a_ = os.path.join(B28, "art_on_default", "video", "ds27_%s_30fps.mp4" % v)
        b_ = os.path.join(B, "art_on_default", "video", "ds27_%s_30fps.mp4" % v)
        fr = []
        for i, (x, y) in enumerate(zip(read_frames(a_, 960, 540), read_frames(b_, 960, 540))):
            if 150 <= i <= 360 and i % 6 == 0:
                d = np.abs(x.astype(int) - y.astype(int)).max(-1) / 255.0
                fr.append((i, float((d > 0.1).mean())))
        m = max(fr, key=lambda z: z[1])
        out[v] = dict(max_frac=round(m[1], 4), at_frame=m[0], mean_frac=round(float(np.mean([z[1] for z in fr])), 4))
    return dict(note_ja="設計28 既定と設計28修正01 既定の Unity の動画を、同じ体験の時刻 t（f150〜f360、6 こまおき）で比べた、色の差 > 0.1 の画素の割合（960×540 に縮めて）。t が同じでも τ は時間曲線で違う", views=out)


def downscale(src, out, w, h, crf):
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", src, "-vf", "scale=%d:%d:flags=lanczos" % (w, h), "-c:v", "libx264", "-preset", "medium",
                    "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], check=True)


# ---------------------------------------------------------------- metrics
def tstar_same():
    """t* の画像（t28/render）が設計28 の既定と画素まで同じか（既定と代案も）。"""
    out = {}
    for n in ("af28r01_painting.png", "af28r01_seat.png", "af28r01_seat_low.png", "af28r01_class_ids.png", "af28r01_seat_class_ids.png", "af28r01_line_ids.png"):
        x = np.asarray(Image.open(os.path.join(B, "art_on_default", "t28", "render", n)).convert("RGB")).astype(int)
        y = np.asarray(Image.open(os.path.join(B28, "art_on_default", "t28", "render", n)).convert("RGB")).astype(int)
        z = np.asarray(Image.open(os.path.join(B, "art_on_alt", "t28", "render", n)).convert("RGB")).astype(int)
        out[n] = dict(pixels_diff_vs_ds28=int((np.abs(x - y).max(-1) > 0).sum()), pixels_diff_default_vs_alt=int((np.abs(x - z).max(-1) > 0).sum()))
    return out


def gate_table(p):
    J = jload(p)
    out = {}
    for k, g in list(J["gates"].items()) + list(J["gates_ds28"].items()) + list(J["gates_ds28r01"].items()):
        out[k] = dict(pass_=g.get("pass"), value=g.get("value"))
    return dict(source=fileinfo(p), package_pos_sha256=J["package"]["pos_sha256"], timewarp=J.get("timewarp", {}).get("path") if isinstance(J.get("timewarp"), dict) else J.get("timewarp"),
                failed=J["summary_all"]["failed"], gates=out)


def overlap_summary(p):
    J = jload(p)
    keep = ("ext_tau", "H_at_ext", "gain_after_ext", "plateau_s", "tau_Hmax", "tau_grow", "H_at_grow", "stall_s", "H_at_P50", "P_at_H95")
    rows = {}
    for r in ("main_159", "peak_192"):
        R = J[r]
        rows[r] = {k: R[k] for k in R if not isinstance(R[k], (list, dict))}
        for k in ("claws", "screen"):
            if k in R:
                rows[r][k] = R[k]
    s = J["summary_all_curled"]
    return dict(source=fileinfo(p), label=J["label"], tool_sha256=J["tool_sha256"], package_pos_sha256=J["package"]["pos_sha256"],
                warps=J["warps"], verdict=J["verdict"], main_peak=rows,
                all_curled={k: s[k] for k in s if k in ("n_rows", "H_over_Hf_at_ext", "H_over_Hf_at_grow", "gain_after_ext_over_Hf", "plateau_s", "H_over_Hf_at_P50",
                                                       "P_at_H95", "claw_H_over_Hf_at_C50", "claw_C_share_last_1s", "T1_pass_rows", "T1_strict_pass_rows",
                                                       "T2_evaluated_rows", "T2_pass_rows")})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clay-scripts", default=None, help="粘土の台本のフォルダー（clay_render.py・compose_r01.py・run_clay.sh。SHA-256 を記録するだけ）")
    ap.add_argument("--skip-video", action="store_true")
    a = ap.parse_args()
    os.makedirs(EV, exist_ok=True)
    figs = []
    p = os.path.join(EV, "fig_ds28r01_unity_stages.png")
    fig_unity_stages(p)
    figs.append(p)
    p = os.path.join(EV, "fig_ds28r01_clay_stages.png")
    fig_clay_stages(p)
    figs.append(p)
    vids = []
    if not a.skip_video:
        for v, vja in VIDEO_VIEWS:
            p = os.path.join(EV, "ds28r01_unity_compare_%s.mp4" % v)
            n = unity_compare(v, vja, p)
            vids.append(dict(fileinfo(p), frames=n, kind_ja="Unity の描画（既定の時間曲線）。左＝設計28 既定、右＝設計28修正01 既定"))
        p = os.path.join(EV, "ds28r01_clay_side_follow.mp4")
        downscale(os.path.join(B, "clay", "combined", "clay2_28_vs_28R01__side_follow.mp4"), p, 1600, 450, 26)
        vids.append(dict(fileinfo(p), kind_ja="粘土の確認用の描画（Blender）。左＝設計28 既定、右＝設計28修正01 既定。字幕は中国語（利用者に見せたもの）"))
        p = os.path.join(EV, "ds28r01_clay_side_follow_default_vs_alt.mp4")
        downscale(os.path.join(B, "clay", "combined", "clay2_28R01_default_vs_alt__side_follow.mp4"), p, 1600, 450, 26)
        vids.append(dict(fileinfo(p), kind_ja="粘土の確認用の描画（Blender）。設計28修正01 の既定（左）と代案＝実時間で t* に瞬間に止める（右）"))
    # ---- metrics
    M = dict(schema="GreatWave.DS28R01.metrics/1", number="設計28修正01", generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
             evidence_kind_ja="numpy の生成器・検査器（パッケージを Hermite で読む）、Unity 6000.4.3f1 の PC オフスクリーン描画、Blender の粘土の確認用の描画。HMD 実機ではない")
    M["gates"] = {k: gate_table(os.path.join(B, "gates", k + ".json")) for k in ("art_on_default", "art_on_alt", "art_off_default", "ref28_art_on_default_q13table")}
    gi = os.path.join(B, "gates_int", "art_on_default.json")
    if os.path.exists(gi):
        g1, g2 = M["gates"]["art_on_default"]["gates"], gate_table(gi)["gates"]
        diff = [k for k in g1 if json.dumps(g1[k], sort_keys=True) != json.dumps(g2.get(k), sort_keys=True)]
        M["gates_rerun_integration"] = dict(source=fileinfo(gi), same_values_and_verdicts=not diff, differing=diff,
                                            note_ja="統合で同じ包み・同じ時間曲線にもう一度走らせた関門の値と判定を、動きの担当の出力と比べた")
    M["overlap_checker"] = {k: overlap_summary(os.path.join(B, "overlap", k + ".json")) for k in ("ds28r01_art_on", "ds28_art_on", "ds28r01_art_off", "ds28_art_on_newwarp")}
    q = jload(os.path.join(B, "q13", "art_on.json"))
    M["motion_q13"] = dict(source=fileinfo(os.path.join(B, "q13", "art_on.json")), results=q["results"])
    M["tstar_remeasure"] = {}
    for k in ("art_on_default", "art_on_alt"):
        p = os.path.join(B, k, "ds27_tstar_remeasure.json")
        T = jload(p)
        M["tstar_remeasure"][k] = dict(source=fileinfo(p), worst_abs_diff_px=T["worst_abs_diff_px"], criterion_px=T["criterion_px"], pass_=T["pass"],
                                       verdicts_ds28r01=T["summary_verdicts_ds27"], verdicts_af28r01=T["summary_verdicts_28r01"],
                                       pixel_diff_vs_af30_t28=T.get("pixel_diff_vs_af30_t28"))
    p = os.path.join(B, "art_on_default", "ds27_playback_check.json")
    P = jload(p)
    M["playback_check"] = dict(source=fileinfo(p), **{k: P[k] for k in P if k in ("count", "worst_pos_err_m", "worst_normal_err_deg", "worst_normal_err_deg_sum_gt_1e-4",
                                                                            "criterion_pos_m", "pass_pos", "tstar", "pass_tstar", "pass")})
    M["render_reports"] = {}
    for k in ("art_on_default", "art_on_alt", "ref28_art_on_stages"):
        for f in sorted(glob.glob(os.path.join(B, k, "*.json"))):
            if os.path.basename(f).startswith(("ds27_render_report", "ds28_review_view")):
                R = jload(f)
                M["render_reports"]["%s/%s" % (k, os.path.basename(f))] = dict(
                    source=fileinfo(f), **{x: R[x] for x in R if x in ("posSha256", "warpFileSha256", "warpTauMin", "captureCount", "positionGpuBytes",
                                                                       "graphicsDriverBytesBefore", "graphicsDriverBytesAfter", "totalSeconds", "sceneSha256",
                                                                       "protectedUnchanged", "sceneDirtyNotSaved", "passed", "videoSha256", "videoFrames",
                                                                       "contextHidden", "videos", "stills")})
    if not a.skip_video:
        M["unity_pixel_diff_28_vs_28r01"] = unity_pixel_diff()
    M["tstar_images_same_as_ds28"] = tstar_same()
    M["figures"] = [fileinfo(f) for f in figs]
    M["videos"] = vids
    M["clay"] = dict(kind_ja="粘土の確認用の描画（Blender 5.2.2 Workbench、背景で実行）。美術の見た目ではない。パッケージを Unity の再生器と同じ Hermite で読む",
                     stills="Unity/Build/Design/28R01/clay/stills/<d28|r01>/<視点>/stage_<段階>.png",
                     combined=[fileinfo(f) for f in sorted(glob.glob(os.path.join(B, "clay", "combined", "*.mp4")))],
                     sheets=[fileinfo(f) for f in sorted(glob.glob(os.path.join(B, "clay", "sheets", "*.png")))])
    mm = jload(os.path.join(EV, "ds28r01_motion_metrics.json"))
    rv = os.path.join(B, "review", "review_ds28r01.json")
    if os.path.exists(rv):
        RV = jload(rv)
        P18f = RV["p18_fixed_height"]
        keep = ("calibrated_onset/f05", "calibrated_onset/f03", "calibrated_onset/w5", "face_vertical/f05", "face_vertical/f03", "face_vertical/w5", "face_vertical/w3")
        M["review_response"] = dict(
            source=fileinfo(rv), tool_sha256=RV["tool_sha256"], packages=RV["packages"],
            note_ja="レビュー対応の記録のみの測り直し（ds28r01_review.py。生成器・パッケージ・関門の判定は変えない）",
            p18_fixed_height=dict(note_ja=P18f["note_ja"], **{k: {x: P18f[k][x] for x in keep} for k in ("ds28r01", "ds28")}),
            lip_position_vs_ds28=RV["lip_position_vs_ds28"], lip_tip_forward=RV["lip_tip_forward"],
            screen_rise=RV["screen_rise"], physical_rise=RV["physical_rise"], figure=fileinfo(os.path.join(EV, "fig_ds28r01_review_rise.png")))
    M["motion_metrics"] = dict(source=fileinfo(os.path.join(EV, "ds28r01_motion_metrics.json")),
                               note_ja="動きの担当の数値（パッケージ、決定性、Q13、関門、修正の記録、P20、打ち出し、時間曲線、段階の表、ds_rise_overlap、上書き）はこのファイルにある")
    M["packages"] = mm["packages"]
    M["determinism_art_on"] = mm["determinism_art_on"]
    M["art_off_equals_ds28_art_off_phys"] = mm["art_off_equals_ds28_art_off_phys"]
    M["timewarp"] = mm["timewarp"]
    with open(os.path.join(EV, "metrics.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(M, f, ensure_ascii=False, indent=1)
    # ---- run.json
    scripts = [fileinfo(f) for f in sorted(glob.glob(os.path.join(HERE, "*"))) if os.path.isfile(f)]
    clay = []
    if a.clay_scripts:
        for n in ("clay_render.py", "compose_r01.py", "run_clay.sh"):
            f = os.path.join(a.clay_scripts, n)
            if os.path.exists(f):
                clay.append(dict(name=n, sha256=sha(f), bytes=os.path.getsize(f)))
    inputs = [fileinfo(os.path.join(REPO, x)) for x in (
        "Docs/Evidence/Design/26/ds26_conditions.json", "Unity/Build/ArtFirst/26修正01/kstar/kstar_a45.gwb",
        "Tools/GWWaveGen/ds27/ds27_model.py", "Tools/GWWaveGen/ds27/ds27_params.json", "Tools/GWWaveGen/ds27/ds27_gates.py",
        "Tools/GWWaveGen/ds27/timewarp_default.json", "Tools/GWWaveGen/ds27/timewarp_alt.json",
        "Tools/GWWaveGen/ds28/ds28_model.py", "Tools/GWWaveGen/ds28/ds28_params.json", "Tools/GWWaveGen/ds28/ds28_physoff.py",
        "Tools/GWWaveGen/ds28/ds28_gates_extra.py")]
    pk = []
    for d_ in ("art_on", "art_off"):
        for n in ("ds27_pos_rgba16.bin", "ds27_keypose.json", "ds27_twhite_r32f.bin"):
            pk.append(fileinfo(os.path.join(B, d_, n)))
    bo = []
    for pat in ("gates/*.json", "gates_int/*.json", "overlap/*.json", "q13/*.json", "p20/*.json", "launch/*.json", "art_on_default/*.json", "art_on_alt/*.json",
                "art_on_default/video/*.mp4", "art_on_alt/video/*.mp4", "clay/combined/*.mp4", "clay/sheets/*.png", "review/*.json"):
        bo += [fileinfo(f) for f in sorted(glob.glob(os.path.join(B, pat)))]
    ffv = subprocess.run([FF, "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    import PIL
    R = dict(schema="GreatWave.DS28R01.run/1", number="設計28修正01", generated_utc=M["generated_utc"], machine=platform.platform(),
             python=platform.python_version(), numpy=np.__version__, pillow=PIL.__version__,
             unity="6000.4.3f1（Editor batchmode、PC オフスクリーン描画、RTX 3080、Direct3D11）", blender="5.2.2 LTS（Workbench、--background --factory-startup）", ffmpeg=ffv,
             commands=[
                 "py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_timewarp.py",
                 "py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_generate.py --version art_on（art_off も。決定性は --no-check --no-sea --out Unity/Build/Design/28R01/_twice）",
                 "py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_gates.py --package Unity/Build/Design/28R01/art_on --timewarp Tools/GWWaveGen/ds28r01/timewarp_default.json --sea Unity/Build/Design/28R01/art_on/ds27_sea.npz --out Unity/Build/Design/28R01/gates/art_on_default.json（代案 --timewarp Tools/GWWaveGen/ds27/timewarp_alt.json → art_on_alt.json、art_off → art_off_default.json、設計28 の包みを新しい表で → ref28_art_on_default_q13table.json、統合のもう一度 → gates_int/art_on_default.json）",
                 "py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_q13.py --package Unity/Build/Design/28R01/art_on --out Unity/Build/Design/28R01/q13/art_on.json",
                 "py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_overlap.py --package Unity/Build/Design/28R01/art_on --tw-default Tools/GWWaveGen/ds28r01/timewarp_default.json --tw-alt Tools/GWWaveGen/ds27/timewarp_alt.json --out Unity/Build/Design/28R01/overlap/ds28r01_art_on.json --label \"設計28修正01 既定（art_on）\" --evidence Docs/Evidence/Design/28R01/overlap_ds28r01_art_on.json（設計28：--package Unity/Build/Design/28/art_on --tw-default Tools/GWWaveGen/ds27/timewarp_default.json --out …/ds28_art_on.json --evidence …/overlap_ds28_art_on.json、art_off、設計28 を新しい時間曲線で）",
                 "py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_p20.py（--direct rise_off|no_tower_override も）、py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_launch.py、py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_evidence.py",
                 "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds28r01/run_ds28r01_unity.ps1 -Method GreatWave.Design27.EditorTools.DS27Formation.RenderOnly -Log art_on_default -Version art_on -Warp default -Package Build/Design/28R01/art_on -WarpFile ../Tools/GWWaveGen/ds28r01/timewarp_default.json -OutDir Build/Design/28R01/art_on_default -Stills \"a=-4.367,b=-3.517,c=-3.017,d=-2.250,apex=-1.180,tstar=0\" -Views painting,seat,side_left -Skip frames（代案：-Log art_on_alt -Warp alt、-WarpFile なし、-OutDir Build/Design/28R01/art_on_alt）",
                 "run_ds28r01_unity.ps1 -Method GreatWave.Design28.EditorTools.DS28ReviewView.Render -Log stw_art_on_default（同じ -Package・-WarpFile・-OutDir・-Stills）-Skip frames -Extra \"-ds28HideContext 1\"（代案も）",
                 "run_ds28r01_unity.ps1 で設計28 の包みを同じ τ の静止画だけ：DS27Formation.RenderOnly -Log ref28_art_on_stages -Package Build/Design/28/art_on -OutDir Build/Design/28R01/ref28_art_on_stages -Skip video,frames,t28,capture、DS28ReviewView.Render -Log stw_ref28_art_on_stages -Skip video,frames -Extra \"-ds28HideContext 1\"",
                 "py -3.10 -B Tools/GWWaveGen/ds27/ds27_tstar_eval.py --run Unity/Build/Design/28R01/art_on_default（art_on_alt も）",
                 "py -3.10 -B Tools/GWWaveGen/ds27/ds27_player_ref.py check --package Unity/Build/Design/28R01/art_on --capture Unity/Build/Design/28R01/art_on_default/gpu_capture",
                 "粘土の確認用の描画（作業場所の台本、Git 対象外）：run_clay.sh stills → run_clay.sh（Blender 5.2.2 --background --factory-startup --python clay_render.py、コマは compose_r01.py が ffmpeg へ流して消す。出力 Unity/Build/Design/28R01/clay/）",
                 "py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_review.py（レビュー対応の記録のみの測り直し：P18 を固定の高さで、唇先の位置の設計28 との比べ、画面の頂の上昇、見える唇の始まり、図 fig_ds28r01_review_rise.png。出力 Unity/Build/Design/28R01/review/review_ds28r01.json）",
                 "py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_record.py --clay-scripts <粘土の台本のフォルダー>"],
             scripts=scripts, clay_scripts=clay, inputs=inputs, packages=pk, build_outputs=bo,
             evidence=[fileinfo(f) for f in sorted(glob.glob(os.path.join(EV, "*"))) if os.path.basename(f) != "run.json"],
             protected_ja="設計26〜28 のコミット済みのファイルは変えていない（生成器が ds28_params.json・ds28_physoff.py・ds28_model.py の SHA-256 を照合。Unity の採取が場面と DS27 のファイルの前後の SHA-256 を記録。git status で追跡中のファイルの変更 0）",
             not_in_repo_ja="パッケージ・描画・動画の元・関門と検査器の出力・粘土の描画は Git 対象外（Unity/Build/Design/28R01/）。粘土の描画の台本は作業場所（Git 対象外）で、SHA-256 だけを clay_scripts に書く")
    with open(os.path.join(EV, "run.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
    print("[ds28r01_record] figures %d, videos %d → %s" % (len(figs), len(vids), rel(EV)))


if __name__ == "__main__":
    main()
