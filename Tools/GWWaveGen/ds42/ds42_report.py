# -*- coding: utf-8 -*-
"""設計42：Unity の静水の検査（DS42BuoyancyTest.Run）の値から、釣り合いの数値・戻りの数値（metrics.json）、
戻りの動画（1920×1080、30 fps。上：2 つの視点、下：喫水・横傾斜・縦傾斜の時間の図）、釣り合いの図、run.json を作る。

使い方（リポジトリの根で）: py -3.10 -B Tools/GWWaveGen/ds42/ds42_report.py
"""
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(REPO, "Unity", "Build", "Design", "42", "buoyancy")
FRAMES = os.path.join(OUT, "frames")
COMP = os.path.join(OUT, "comp")
FFMPEG = r"G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe"
FONT = r"C:\Windows\Fonts\YuGothM.ttc"
FONTB = r"C:\Windows\Fonts\YuGothB.ttc"
ASSET = os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design42", "Data", "ds42_buoyancy_points.json")
PARAMS = os.path.join(HERE, "ds42_params.json")


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def main():
    t0 = time.time()
    ser = json.load(open(os.path.join(OUT, "ds42_unity_series.json"), encoding="utf-8"))
    rep = json.load(open(os.path.join(OUT, "ds42_unity_report.json"), encoding="utf-8"))
    hyd = json.load(open(os.path.join(OUT, "ds42_hydrostatics.json"), encoding="utf-8"))
    prm = json.load(open(PARAMS, encoding="utf-8"))["test"]
    cfg = json.load(open(ASSET, encoding="utf-8"))
    S = {k: np.array(v, dtype=np.float64) for k, v in ser.items()}
    t = S["t"]
    m, g, rho = rep["massKg"], rep["g"], rep["rho"]
    W = m * g
    ex = hyd["exact_equilibrium"]
    w0, w1 = prm["eq_window_s"]
    eqm = (t >= w0) & (t <= w1)

    def mean(k, msk=eqm):
        return float(S[k][msk].mean())

    eq = {k: mean(k) for k in ("draft", "heel", "trim", "sumF", "vPoints", "vExact", "cbX", "cbZ", "cgX", "cgZ", "dampF")}
    cb_cg = float(np.hypot(eq["cbX"] - eq["cgX"], eq["cbZ"] - eq["cgZ"]))
    balance = {
        "weight_N": round(W, 1),
        "sum_point_buoyancy_N": round(eq["sumF"], 1),
        "sum_point_buoyancy_over_weight": eq["sumF"] / W,
        "rho_g_V_points_N": round(rho * g * eq["vPoints"], 1),
        "V_points_m3": round(eq["vPoints"], 5),
        "V_exact_unity_mesh_m3": round(eq["vExact"], 5),
        "rho_g_V_exact_N": round(rho * g * eq["vExact"], 1),
        "rho_g_V_exact_over_weight": rho * g * eq["vExact"] / W,
        "V_exact_python_columns_m3": ex["displaced_volume_m3"],
        "V_needed_m3": round(m / rho, 5),
        "cb_exact_to_cg_horizontal_m": round(cb_cg, 4),
        "damping_force_at_rest_N": round(eq["dampF"], 3),
        "note_ja": "7〜8 s（放してから釣り合った後、外力の前）の平均。V_exact は Unity の浮力用の閉じた船体（FBX を取り込んだメッシュ）を水面で切った容積で、浮力点の表とは別の計算。"
                   "Python の柱の積分の容積との差は、FBX の四角形の三角形への分け方の違い（全体の容積で +0.12%）",
    }
    pose = {
        "draft_mid_m_unity": round(eq["draft"], 5), "draft_mid_m_python_exact": ex["draft_mid_m"],
        "draft_diff_mm": round((eq["draft"] - ex["draft_mid_m"]) * 1000, 2),
        "heel_deg_unity": round(eq["heel"], 4), "heel_deg_python_exact": ex["heel_deg_starboard_down_positive"],
        "heel_diff_deg": round(eq["heel"] - ex["heel_deg_starboard_down_positive"], 4),
        "trim_deg_unity": round(eq["trim"], 4), "trim_deg_python_exact": ex["trim_deg_bow_up_positive"],
        "trim_diff_deg": round(eq["trim"] - ex["trim_deg_bow_up_positive"], 4),
        "freeboard_mid_m": ex["freeboard_mid_m"],
        "sign_ja": "喫水は船体中央の船底の水面からの深さ。横傾斜は右舷が下がる向き、縦傾斜は船首が上がる向きが正",
    }

    # ---- 戻り
    base = {"draft": eq["draft"], "heel": eq["heel"], "trim": eq["trim"]}
    tol = {"draft": 0.001, "heel": 0.05, "trim": 0.05}
    seg = [("drop_settle", "放して釣り合いへ", 0.0, prm["heave_push_t"], None),
           ("heave_push", "下向きの力積", prm["heave_push_t"], prm["roll_push_t"], "draft"),
           ("roll_push", "横の角力積", prm["roll_push_t"], prm["pitch_push_t"], "heel"),
           ("pitch_push", "縦の角力積", prm["pitch_push_t"], prm["static_heel_from_t"], "trim"),
           ("static_heel_release", "静的な横のモーメントを外す", prm["static_heel_to_t"], prm["total_s"], "heel")]
    rec = []
    for key, ja, a, b, q in seg:
        msk = (t >= a) & (t <= b)
        last = (t >= b - 1.0) & (t <= b)
        row = {"event": key, "label_ja": ja, "t_from": a, "t_to": b}
        for qq in (["draft", "heel", "trim"] if q is None else [q]):
            dev = S[qq][msk] - base[qq]
            pk = float(np.abs(dev).max())
            thr = max(0.1 * pk, tol[qq])
            out = np.where(np.abs(dev) > thr)[0]
            settle = float(t[msk][out[-1]] - a) if len(out) else 0.0
            resid = float(np.abs(S[qq][last] - base[qq]).mean())
            row[qq] = {"peak_dev": round(pk, 5), "settle_s_to_10pct_or_tol": round(settle, 3), "residual_last_1s": round(resid, 6),
                       "tol": tol[qq], "pass": resid <= tol[qq]}
        rec.append(row)
    # 静的な横傾斜：モーメント M のもとでの横傾斜の差 と GM からの予測
    a, b = prm["static_heel_from_t"], prm["static_heel_to_t"]
    sm = (t >= b - 2.0) & (t < b)
    heel_meas = float(S["heel"][sm].mean() - base["heel"])
    k_roll = hyd["damping_and_periods"]["k_roll_Nm_per_rad"]
    heel_pred = float(np.degrees(prm["static_heel_moment_Nm"] / k_roll))
    static = {"moment_Nm": prm["static_heel_moment_Nm"], "heel_measured_deg": round(heel_meas, 4), "heel_predicted_deg_from_exact_GM": round(heel_pred, 4),
              "rel_diff": (heel_meas - heel_pred) / heel_pred, "gm_t_implied_m": round(prm["static_heel_moment_Nm"] / np.radians(heel_meas) / (m * g), 4),
              "gm_t_exact_m": ex["gmt_m_numeric_1deg"], "window_s": [b - 2.0, b],
              "note_ja": "824 N·m は 70 kg の人が中心線から 1.2 m の船縁へ寄った時の横のモーメント（純粋なモーメントとして与えた）。予測は厳密な復原の硬さ ρ g V GM（1° の数値の微分）から"}
    # 周期（横揺れの力積の後のゼロ交差）
    def period(q, a, b):
        msk = (t >= a) & (t <= b)
        d = S[q][msk] - base[q]; tt = t[msk]
        z = [tt[i] - d[i] * (tt[i + 1] - tt[i]) / (d[i + 1] - d[i]) for i in range(len(d) - 1) if d[i] * d[i + 1] < 0 and abs(d[i]) + abs(d[i + 1]) > 1e-4]
        return float(2 * np.mean(np.diff(z[:5]))) if len(z) >= 3 else None
    periods = {"heave_s_unity": period("draft", prm["heave_push_t"], prm["heave_push_t"] + 4), "roll_s_unity": period("heel", prm["roll_push_t"], prm["roll_push_t"] + 6),
               "pitch_s_unity": period("trim", prm["pitch_push_t"], prm["pitch_push_t"] + 4),
               "heave_s_undamped_rigid": hyd["damping_and_periods"]["T_heave_s"], "roll_s_undamped_rigid": hyd["damping_and_periods"]["T_roll_s"],
               "pitch_s_undamped_rigid": hyd["damping_and_periods"]["T_pitch_s"],
               "note_ja": "Unity の値は減衰のある振動の見かけの周期（ゼロ交差の間隔 × 2）。付加質量を入れていないので、実際の船より短い（記録のみ）"}

    ratio_ok = abs(balance["rho_g_V_exact_over_weight"] - 1) <= 0.02
    pose_ok = abs(pose["draft_diff_mm"]) <= 5 and abs(pose["heel_diff_deg"]) <= 0.2 and abs(pose["trim_diff_deg"]) <= 0.2
    rec_ok = all(v["pass"] for r in rec for k, v in r.items() if isinstance(v, dict))

    # ---------------------------------------------------------------- 図の下地（時間の図）
    font = ImageFont.truetype(FONT, 20); fs = ImageFont.truetype(FONT, 17); fb = ImageFont.truetype(FONTB, 22)
    PW, PH = 1920, 540
    x0, x1 = 90, 1450
    rows = [("draft", "喫水 [m]", 0.0, 0.34), ("heel", "横傾斜 [°]（右舷下が正）", -8.0, 8.0), ("trim", "縦傾斜 [°]（船首上が正）", -3.0, 3.0)]
    top0, rh, gap = 58, 140, 18
    T = prm["total_s"]

    def X(tt):
        return x0 + (x1 - x0) * tt / T

    bg = Image.new("RGB", (PW, PH), (248, 245, 238))
    d = ImageDraw.Draw(bg)
    d.text((20, 12), "設計42　静水の釣り合いと外力の後の戻り（Unity の物理、dt = 1/120 s、PC の batchmode。HMD 実機ではない）", font=fb, fill=(30, 30, 30))
    evs = [(prm["heave_push_t"], "下へ押す"), (prm["roll_push_t"], "横に押す"), (prm["pitch_push_t"], "縦に押す"),
           (prm["static_heel_from_t"], "横のモーメント 824 N·m"), (prm["static_heel_to_t"], "外す")]
    boxes = []
    for i, (k, lab, lo, hi) in enumerate(rows):
        ytop = top0 + i * (rh + gap); ybot = ytop + rh
        boxes.append((ytop, ybot, lo, hi))
        d.rectangle([x0, ytop, x1, ybot], outline=(150, 150, 150), fill=(255, 255, 255))
        Y = lambda v: ybot - (v - lo) / (hi - lo) * rh
        for gv in np.linspace(lo, hi, 5):
            d.line([x0, Y(gv), x1, Y(gv)], fill=(228, 228, 228))
            d.text((x0 - 62, Y(gv) - 10), ("%.2f" % gv) if k == "draft" else ("%+.0f" % gv), font=fs, fill=(90, 90, 90))
        yb = Y(base[k])
        d.line([x0, yb, x1, yb], fill=(90, 160, 90), width=1)
        d.text((x0 + 6, ytop + 2), lab, font=fs, fill=(40, 40, 40))
        for te, _ in evs:
            d.line([X(te), ytop, X(te), ybot], fill=(200, 140, 60), width=1)
        pts = [(X(tt), Y(min(hi, max(lo, v)))) for tt, v in zip(t, S[k])]
        d.line(pts, fill=(30, 70, 150), width=2)
    for te, lab in evs:
        d.text((X(te) + 3, top0 - 22), lab, font=fs, fill=(170, 100, 30))
    for tt in range(0, int(T) + 1, 4):
        d.text((X(tt) - 8, top0 + 3 * (rh + gap) - gap + 2), "%d" % tt, font=fs, fill=(90, 90, 90))
    d.text((x1 + 14, top0 + 3 * (rh + gap) - gap + 2), "s", font=fs, fill=(90, 90, 90))
    # 右の数値の欄
    tx = 1475
    lines = [("質量 m", "%.0f kg（部品の推定の和）" % m), ("重さ m g", "%.0f N" % W),
             ("浮力点の力の和", "%.0f N（%.4f × m g）" % (balance["sum_point_buoyancy_N"], balance["sum_point_buoyancy_over_weight"])),
             ("ρ g V（閉じた船体を切る）", "%.0f N（%.4f × m g）" % (balance["rho_g_V_exact_N"], balance["rho_g_V_exact_over_weight"])),
             ("排水容積 V", "%.4f m³（要 %.4f）" % (balance["V_exact_unity_mesh_m3"], balance["V_needed_m3"])),
             ("喫水（船体中央）", "%.4f m（厳密 %.4f）" % (pose["draft_mid_m_unity"], pose["draft_mid_m_python_exact"])),
             ("横傾斜／縦傾斜", "%+.2f° ／ %+.2f°" % (pose["heel_deg_unity"], pose["trim_deg_unity"])),
             ("GM（横／縦）", "%.3f m ／ %.1f m" % (ex["gmt_m_numeric_1deg"], ex["gml_m_numeric_1deg"])),
             ("静的な横傾斜", "%.2f°（予測 %.2f°）" % (static["heel_measured_deg"], static["heel_predicted_deg_from_exact_GM"])),
             ("ρ = %.0f kg/m³" % rho, "g = %.2f m/s²" % g)]
    y = 50
    for a_, b_ in lines:
        d.text((tx, y), a_, font=fs, fill=(90, 90, 90)); d.text((tx + 10, y + 19), b_, font=fs, fill=(20, 20, 20)); y += 42

    # ---------------------------------------------------------------- 動画
    if os.path.isdir(COMP):
        shutil.rmtree(COMP)
    os.makedirs(COMP)
    n = len(t)
    phases = [(0, prm["heave_push_t"], "放して釣り合いへ（平衡の 0.15 m 上・横 6°・縦 2° から）"),
              (prm["heave_push_t"], prm["roll_push_t"], "下向きの力積 → 上下の戻り"),
              (prm["roll_push_t"], prm["pitch_push_t"], "横の角力積 → 横揺れの戻り"),
              (prm["pitch_push_t"], prm["static_heel_from_t"], "縦の角力積 → 縦揺れの戻り"),
              (prm["static_heel_from_t"], prm["static_heel_to_t"], "一定の横のモーメント 824 N·m（静的な横傾斜）"),
              (prm["static_heel_to_t"], T + 1, "モーメントを外す → 戻り")]
    for i in range(n):
        tt = t[i]
        fa = Image.open(os.path.join(FRAMES, "a_%05d.jpg" % i)).convert("RGB")
        fbm = Image.open(os.path.join(FRAMES, "b_%05d.jpg" % i)).convert("RGB")
        img = Image.new("RGB", (1920, 1080))
        img.paste(fa, (0, 0)); img.paste(fbm, (960, 0))
        pl = bg.copy(); dd = ImageDraw.Draw(pl)
        for (ytop, ybot, lo, hi) in boxes:
            dd.line([X(tt), ytop, X(tt), ybot], fill=(210, 40, 40), width=2)
        ph = [p for p in phases if p[0] <= tt < p[1]][0][2]
        dd.rectangle([tx - 5, 488, 1915, 535], fill=(248, 245, 238))
        dd.text((tx, 492), "t = %5.2f s　喫水 %.3f m　横 %+.2f°　縦 %+.2f°" % (tt, S["draft"][i], S["heel"][i], S["trim"][i]), font=fs, fill=(170, 30, 30))
        dd.text((tx, 513), "浮力点の力の和 %.0f N" % S["sumF"][i], font=fs, fill=(170, 30, 30))
        img.paste(pl, (0, 540))
        di = ImageDraw.Draw(img)
        di.rectangle([0, 0, 960, 34], fill=(248, 245, 238)); di.rectangle([960, 0, 1920, 34], fill=(248, 245, 238))
        di.text((10, 5), "左舷の船首寄り（世界に固定）　赤い点＝浮力点 10", font=font, fill=(30, 30, 30))
        di.text((970, 5), "船尾の真後ろ（世界に固定）　" + ph, font=font, fill=(30, 30, 30))
        di.line([960, 0, 960, 540], fill=(255, 255, 255), width=2)
        img.save(os.path.join(COMP, "c_%05d.jpg" % i), quality=93)
    mp4 = os.path.join(OUT, "ds42_recovery.mp4")
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-framerate", "30", "-i", os.path.join(COMP, "c_%05d.jpg"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", mp4]
    subprocess.run(cmd, check=True)
    ffv = subprocess.run([FFMPEG, "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    # 途中のコマの画像を 3 枚残す（押した直後の最大の傾きの近く）
    keep = {}
    for name, te in (("heave", prm["heave_push_t"] + 0.2), ("roll", prm["roll_push_t"] + 0.5), ("static_heel", prm["static_heel_to_t"] - 0.5)):
        i = int(np.argmin(np.abs(t - te)))
        dst = os.path.join(OUT, "frame_%s_t%05.2f.png" % (name, t[i]))
        Image.open(os.path.join(COMP, "c_%05d.jpg" % i)).save(dst)
        keep[name] = dst

    # 釣り合いの図（上：Unity の最後の姿勢＝戻った後の釣り合い、下：時間の図と数値）
    fig = Image.new("RGB", (1920, 1080), (248, 245, 238))
    ea = Image.open(os.path.join(OUT, "still_unity_end_port_bow.png")).resize((960, 540), Image.LANCZOS)
    eb = Image.open(os.path.join(OUT, "still_unity_end_stern.png")).resize((960, 540), Image.LANCZOS)
    fig.paste(ea, (0, 0)); fig.paste(eb, (960, 0)); fig.paste(bg, (0, 540))
    dfg = ImageDraw.Draw(fig)
    dfg.rectangle([0, 0, 1920, 34], fill=(248, 245, 238))
    dfg.text((10, 5), "Unity の静水の釣り合い（t = %.0f s、外力をすべて外して戻った後）　左：左舷の船首寄り　右：船尾の真後ろ　赤い点＝浮力点" % T, font=font, fill=(30, 30, 30))
    figp = os.path.join(OUT, "fig_ds42_equilibrium.png")
    fig.save(figp)

    # ---------------------------------------------------------------- 記録
    shutil.rmtree(COMP)
    nframes = len([f for f in os.listdir(FRAMES) if f.endswith(".jpg")])
    shutil.rmtree(FRAMES)
    metrics = {
        "schema": "GreatWave.DS42.metrics/1", "number": "設計42", "part": "buoyancy",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "backlog": {"89": "記録（浮力と表示面の整合の前段：静水の重量・排水容積・重心）"},
        "min_acceptance_ja": "浮力 ≈ 水密度 × 重力 × 排水容積 と重量の釣り合いを数値で記録。戻りの動画（計画 §2.4 設計42）",
        "min_acceptance": {"balance_recorded": True, "recovery_video": rel(mp4), "pass": bool(ratio_ok and os.path.exists(mp4))},
        "checks": {
            "rho_g_V_exact_over_weight_within_2pct": {"value": balance["rho_g_V_exact_over_weight"], "pass": ratio_ok},
            "unity_pose_vs_python_exact": {"draft_diff_mm": pose["draft_diff_mm"], "heel_diff_deg": pose["heel_diff_deg"], "trim_diff_deg": pose["trim_diff_deg"],
                                           "tol": "喫水 ±5 mm、角 ±0.2°（進行役の判断の閾値）", "pass": pose_ok},
            "recovery_residuals": {"pass": rec_ok, "tol": "最後の 1 s の平均のずれ：喫水 1 mm、角 0.05°（進行役の判断の閾値）"},
            "static_heel_vs_gm": {"rel_diff": static["rel_diff"], "pass_within_10pct": abs(static["rel_diff"]) <= 0.10, "kind": "記録（判定は仕上げ42）"},
            "protected_unchanged": rep["protectedUnchanged"],
            "painting_view_touched": False,
            "painting_view_note_ja": "原画視点の場面（DS41_Boats.unity）は開いていない。新しい検査の場面 DS42_Buoyancy.unity だけで行ったので、評価器の回帰の対象外（計画 §2.0）",
        },
        "balance": balance, "equilibrium_pose": pose, "recovery": rec, "static_heel": static, "periods": periods,
        "hydrostatics_ref": {"path": rel(os.path.join(OUT, "ds42_hydrostatics.json")), "mass_total_kg": hyd["mass"]["total_kg"], "kg_m": hyd["mass"]["kg_m"],
                             "lcg_m_aft_of_mid": hyd["mass"]["lcg_m_aft_of_mid"], "gmt_m": ex["gmt_m_numeric_1deg"], "gml_m": ex["gml_m_numeric_1deg"],
                             "kg_per_cm_immersion": ex["kg_per_cm_immersion"], "freeboard_mid_m": ex["freeboard_mid_m"]},
        "limits_to_next_ja": [
            "静水の釣り合いの喫水 %.3f m は、座席 v1 の置き方の喫水 0.3806 m（M1 の blockout の 0.35 × 深さ）より %.0f mm 浅い。原画視点の船は投影固定のまま（設計42 では動かしていない）。表示の船と物理の船の高さのそろえ方は設計43（船用水面データ）で決める" % (pose["draft_mid_m_unity"], (0.3806 - pose["draft_mid_m_unity"]) * 1000),
            "静水で横に %.2f°（左舷が下がる）傾くのは、櫓 7 丁（左舷 4・右舷 3）の重さの左右差による。乗員の配置（中心線の上と仮定）で打ち消すかは仕上げ42" % abs(pose["heel_deg_unity"]),
            "付加質量を入れていない。上下・横揺れ・縦揺れの周期は剛体の値で、実際の船より短い。減衰（上下の減衰比 0.3、水平・首振りの抵抗）は調整値",
            "重量・重心は部品ごとの推定（資料なし）。仕上げ42 で見直す",
            "浮力点の模型は、横の硬さが厳密値の −0.7%、縦は y_factor で合わせた。船縁が水に入る大きな傾き（約 10° を超える所）は確かめていない",
        ],
    }
    mp = os.path.join(OUT, "metrics.json")
    with open(mp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)
    outs = [mp4, figp, os.path.join(OUT, "ds42_hydrostatics.json"), os.path.join(OUT, "ds42_unity_series.json"), os.path.join(OUT, "ds42_unity_report.json"),
            os.path.join(OUT, "still_python_eq_port_bow.png"), os.path.join(OUT, "still_python_eq_stern.png"),
            os.path.join(OUT, "still_unity_end_port_bow.png"), os.path.join(OUT, "still_unity_end_stern.png"), mp] + list(keep.values())
    code = [os.path.join(HERE, f) for f in ("ds42_hydro.py", "ds42_params.json", "ds42_report.py", "run_ds42_unity.ps1")] + [
        os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design42", p) for p in ("Scripts/DS42Buoyancy.cs", "Scripts/DS42Water.cs", "Scripts/DS42StillWater.cs",
                                                                                   "Editor/DS42BuoyancyTest.cs", "Data/ds42_buoyancy_points.json", "Scenes/DS42_Buoyancy.unity")]
    run = {
        "schema": "GreatWave.DS42.run/1", "number": "設計42", "part": "buoyancy",
        "commands": [
            "py -3.10 -B Tools/GWWaveGen/ds42/ds42_hydro.py",
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds42/run_ds42_unity.ps1 -Method GreatWave.Design42.EditorTools.DS42BuoyancyTest.Run -Log run",
            "py -3.10 -B Tools/GWWaveGen/ds42/ds42_report.py"],
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "pillow": Image.__version__ if hasattr(Image, "__version__") else "",
                  "unity": rep["unity"], "graphics": rep["device"] + " / " + rep["graphicsApi"] + " / " + rep["colorSpace"], "ffmpeg": ffv},
        "unity_seconds": rep["secondsTotal"], "step_microseconds_mean": rep["stepMicrosecondsMean"],
        "frames_rendered_and_removed_after_encoding": nframes,
        "inputs": hyd["inputs"],
        "code": {rel(p): sha(p) for p in code if os.path.exists(p)},
        "outputs": {rel(p): {"sha256": sha(p), "bytes": os.path.getsize(p)} for p in outs if os.path.exists(p)},
        "seconds_report": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "run.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(run, f, ensure_ascii=False, indent=1)
    print("DS42_REPORT pass=%s ratio=%.5f pose=%s rec=%s static_rel=%.4f mp4=%s" % (
        metrics["min_acceptance"]["pass"], balance["rho_g_V_exact_over_weight"], pose_ok, rec_ok, static["rel_diff"], rel(mp4)))
    for r in rec:
        print(" ", r["event"], {k: (v["peak_dev"], v["settle_s_to_10pct_or_tol"], v["residual_last_1s"], v["pass"]) for k, v in r.items() if isinstance(v, dict)})
    print(" ", json.dumps(periods, ensure_ascii=False))
    print(" ", json.dumps(pose, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
