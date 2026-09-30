# -*- coding: utf-8 -*-
"""設計43（船用水面データ）：図（OpenCV）と metrics.json・run.json を書く。
使い方：py -3.10 -B Tools/GWWaveGen/ds43/ds43_report.py
"""
import json
import os
import subprocess
import time

import cv2
import numpy as np

import ds43_common as C

OUT = C.OUT
W, H = 1920, 1080


def panel(img, x0, y0, w, h, t, series, colors, ylab, yr=None, logy=False, shade=None, title=""):
    cv2.rectangle(img, (x0, y0), (x0 + w, y0 + h), (60, 60, 60), 1)
    allv = np.concatenate([s[np.isfinite(s)] for s in series])
    if logy:
        allv = np.log10(np.maximum(allv, 1e-9))
    lo, hi = (float(allv.min()), float(allv.max())) if yr is None else yr
    if hi - lo < 1e-9:
        hi = lo + 1
    X = lambda tt: (x0 + (tt - t[0]) / (t[-1] - t[0]) * w).astype(np.int32)
    Y = lambda v: (y0 + h - (np.clip(v, lo, hi) - lo) / (hi - lo) * h).astype(np.int32)
    if shade is not None:
        m = shade.astype(int)
        for i in range(len(t) - 1):
            if m[i]:
                cv2.rectangle(img, (int(X(np.array([t[i]]))[0]), y0 + 1), (int(X(np.array([t[i + 1]]))[0]), y0 + h - 1), (225, 225, 245), -1)
    for s, col in zip(series, colors):
        v = np.log10(np.maximum(s, 1e-9)) if logy else s
        ok = np.isfinite(v)
        pts = np.stack([X(t[ok]), Y(v[ok])], 1)
        cv2.polylines(img, [pts.reshape(-1, 1, 2)], False, col, 2, cv2.LINE_AA)
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        yy = int(y0 + h - h * k / 4)
        lab = ("1e%.1f" % v) if logy else ("%.2f" % v)
        cv2.putText(img, lab, (x0 - 95, yy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 40, 40), 1, cv2.LINE_AA)
    for tt in range(0, int(t[-1]) + 1, 2):
        xx = int(X(np.array([float(tt)]))[0])
        cv2.putText(img, "%d" % tt, (xx - 5, y0 + h + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 40, 40), 1, cv2.LINE_AA)
    cv2.putText(img, title, (x0 + 5, y0 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 1, cv2.LINE_AA)
    cv2.putText(img, ylab, (x0 + w - 330, y0 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 40, 40), 1, cv2.LINE_AA)


def main():
    z = np.load(os.path.join(OUT, "measure", "ds43_series.npz"))
    meas = C.load_json(os.path.join(OUT, "measure", "ds43_measure.json"))
    rep = C.load_json(os.path.join(OUT, "unity", "ds43_unity_report.json"))
    sea = C.load_json(os.path.join(OUT, "sea_function_ds43.json"))
    pre = C.load_json(os.path.join(OUT, "precheck", "ds43_precheck_analytic_vs_display.json"))
    t = z["t"]; hb = z["hb"]; hd = z["hd"]; nd = z["nd"]; pos = z["pos"]; keys = [str(k) for k in z["keys"]]
    img = np.full((H, W, 3), 255, np.uint8)
    cv2.putText(img, "DS43 boat water data vs displayed surface (Unity PC batchmode, 30 fps, t 0-14 s, t* = 12 s). Shaded = breaking (>=2 surface hits under a hull sample)",
                (40, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1, cv2.LINE_AA)
    for bi, k in enumerate(keys):
        brk = (nd[:, bi] >= 2).any(1)
        wm = np.nanmean(hd[:, bi, 10:], axis=1)
        panel(img, 140, 90 + bi * 250, 1100, 190, t, [wm, pos[:, bi, 1]], [(200, 120, 30), (30, 30, 200)],
              "blue: display under hull (mean) / red: keel (root y) [m]", shade=brk, title=k)
        d = np.nanmax(np.abs(hb[:, bi] - hd[:, bi]), axis=1)
        panel(img, 1380, 90 + bi * 250, 500, 190, t, [d, np.full_like(d, 0.05)], [(30, 140, 30), (0, 0, 255)],
              "|boat data - display| max [m] (log)", yr=(-7.0, -0.5), logy=True, shade=brk, title=k + " (red line = 5 cm)")
    em = z["eye_margin"]
    panel(img, 140, 850, 1100, 170, t, [em], [(120, 30, 120)], "seat eye - surface below [m]", yr=(0.0, max(4.0, float(np.nanmax(em)))),
          title="boat_mid seat eye margin (in water frames: %d, min %.3f m)" % (meas["seat_eye"]["in_water_frames"], meas["seat_eye"]["margin_min_m"]))
    lag = meas["acceptance_time_offset"]["lag_search_rms_m"]
    txt = ["time offset: tau(water) - tau(sheets) = %.1e s; lag search RMS [m]:" % meas["acceptance_time_offset"]["tau_water_minus_play_absmax_s"]]
    txt += ["  L=%s : %.2e" % (k, v) for k, v in lag.items()]
    txt += ["position offset (LS): dx %.1e m, dz %.1e m" % tuple(meas["position_offset"]["delta_xz_m"]),
            "non-breaking |diff| max %.1e m (criterion 0.05)" % meas["acceptance_hull_vs_display"]["absmax_m"]]
    for i, s in enumerate(txt):
        cv2.putText(img, s, (1380, 860 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    fig = os.path.join(OUT, "fig_ds43_boatwater.png")
    cv2.imwrite(fig, img)

    # 静止画（Unity の JPG を 2 × 2 に並べる：t 6 s と t 11.5 s の全体・座席の目）
    fr = os.path.join(OUT, "unity", "frames")
    tiles = []
    for n in (180, 345):
        a = cv2.imread(os.path.join(fr, "wide_%04d.jpg" % n)); b = cv2.imread(os.path.join(fr, "seat_%04d.jpg" % n))
        row = np.hstack([a, b])
        cv2.putText(row, "t = %.1f s (left: wide, right: seat eye of boat_mid)" % (n / 30.0), (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2, cv2.LINE_AA)
        tiles.append(row)
    still = os.path.join(OUT, "stills_ds43_t06_t11.5.png")
    cv2.imwrite(still, np.vstack(tiles))

    acc = meas["acceptance_hull_vs_display"]; to = meas["acceptance_time_offset"]; eye = meas["seat_eye"]
    # 船ごとの動き（記録）
    motion = {}
    dt = 1 / 30
    for bi, k in enumerate(keys):
        y = pos[:, bi, 1]; a = np.diff(y, 2) / dt ** 2; tt = t[1:-1]
        brk_t = t[(nd[:, bi] >= 2).any(1)]
        motion[k] = dict(heave_acc_absmax_nonbreaking_t_le_9s=float(np.abs(a[tt <= 9]).max()),
                         heave_acc_absmax_all=float(np.abs(a).max()), keel_y_range_m=[float(y.min()), float(y.max())],
                         first_breaking_t=float(brk_t[0]) if len(brk_t) else None,
                         wet_zero_frames=int((z["wet"][:, bi] == 0).sum()))
    metrics = dict(
        schema="GreatWave.DS43.metrics/1", number="設計43", part="boatwater", created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        backlog={"89": "記録（浮力と表示面の整合：非砕波域の船底サンプルの高さの差）", "90": "記録（船用水面データと表示の同じ時計）", "203": "記録（船用データの形式：有効領域・原点・時刻・高さ）"},
        min_acceptance_ja="非砕波域で船底と表示面の差 ≤5 cm（設計書 §11 の出発点）。時刻のずれ 0 フレーム（計画 §2.4 設計43）。作業の指示：座席の目が全コマで水の上（設計30 の検査）",
        min_acceptance=dict(
            hull_vs_display=dict(criterion_m=0.05, value_absmax_m=acc["absmax_m"], p99_m=acc["p99_m"], nonbreaking_samples=acc["nonbreaking_samples"], pass_=acc["pass_"]),
            time_offset=dict(criterion_frames=0, tau_offset_s=to["tau_water_minus_play_absmax_s"], sheets_offset_s=to["tau_sheets_minus_play_absmax_s"],
                             best_lag_frames=to["best_lag_frames"], lag_rms_m=to["lag_search_rms_m"], pass_=to["pass_"]),
            seat_eye_above_water=dict(frames=eye["frames"], in_water_frames=eye["in_water_frames"], margin_min_m=eye["margin_min_m"], margin_min_t=eye["margin_min_t"], pass_=eye["pass_"]),
            pass_=bool(acc["pass_"] and to["pass_"] and eye["pass_"])),
        position_offset=meas["position_offset"],
        per_boat=meas["per_boat"], motion_record=motion,
        gpu_vs_numpy_decode_absmax_m=meas["gpu_vs_numpy_decode_absmax_m"],
        sea_function=dict(file="Unity/Build/Design/43/boatwater/sea_function_ds43.json", sha256=C.sha256_file(os.path.join(OUT, "sea_function_ds43.json")),
                          far_taper=sea["far_taper"], verification=sea["verification_ds43"]),
        analytic_vs_display_precheck=pre["summary"],
        design=dict(
            reader_ja="DS43BoatWater（DS42Water の子）：再生器 DS30SinglePlayback の τ（シートへ渡したのと同じ値）を問い合わせのたびに見て、主役波（本体の列 18〜394）・near・far の "
                      "パッケージを CPU で同じ式（16 bit + 精度の層、Hermite の 4 層、O(τ)）で復号し、船のまわりの関心の範囲の三角形の一様格子（1 m）で、点の鉛直の線の最も低い交わり（下側の一価の面）を返す",
            boats_ja="3 隻とも設計42 の DS42Buoyancy（浮力点 10）。boat_mid は設計42 の表、boat_fg・boat_left は縮尺の比で相似に直した表（ds43_boats.py）。原画の水平の位置と首の向き、縦・横の傾き 0 で置き、t = 0 の水で 4 s ならしてから再生",
            clock_ja="物理 dt = 1/120 s、1 コマ（1/30 s）に 4 段。各段の前に再生器へ同じ時刻を Seek し、船はその τ の水を読む。コマの記録は再生器の t = n/30 で行う",
            unity_seconds=rep["secondsTotal"], rebuild_ms_mean=rep["rebuildMsMean"], rebuilds=rep["rebuilds"], queries=rep["queries"], fallbacks=rep["fallbacks"],
            region_xz=rep["region"], protected_unchanged=rep["protectedUnchanged"], painting_view_touched=False,
            hidden_objects_test_scene=rep["hiddenObjects"],
            painting_view_note_ja="原画視点の場面は変えていない（DS30_SinglePlayback.unity は開いただけで保存せず、写しを DS43_BoatWater.unity に保存。守るファイル 17 個の SHA-256 は前後で同じ）。評価器の回帰の対象外（計画 §2.0）"),
        decisions_q24=[
            dict(id="D43-1", choice_ja="船は設計30 の式そのものではなく、表示と同じ標本（near・far のシート。式の値を頂点に持つ）と主役波の本体の下側の一価の面を読む",
                 reason_ja="前の確かめで、式と表示の網の差が far で最大 16.9 cm（boat_fg）・9.4 cm（boat_mid）あり、式を読むと ≤5 cm を満たせない。シートの頂点は式と 0.017 mm で合う（sea_function_ds43.json）ので、うねりの定義は同じ",
                 rejected_ja="式を読む（far の網の間で 17 cm）。far の表示を細かくする（原画視点に触れる。仕上げ30 の候補）"),
            dict(id="D43-2", choice_ja="非砕波域 = 船底サンプルの鉛直の線と表示面の交わりが 1 つ（一価）。2 つ以上は砕波域（唇・巻き込みの下）で、下の面を読み、差は記録のみ",
                 reason_ja="設計書 §7.2 の「巻き込みのない一価の水面で表せる範囲」をそのまま数える読み"),
            dict(id="D43-3", choice_ja="3 隻を自由に浮かべ、形成の区間（砕波域）でもそのまま物理で動かした（固定の軌道への引き継ぎは設計44 の D26）",
                 reason_ja="設計43 の受入は非砕波域だけ。砕波域での振る舞い（打ち上げ・転覆）は設計44・47 への申し送りとして記録する")],
        record_only_ja=[
            "boat_left は t ≈ 9.97 s から主役波の本体（左の支えの所）に入り、唇の下（交わり 3）で打ち上げられ、傾き最大 157°（転覆）・上下の加速度最大 65 m/s²。原画の t* の姿勢には戻らない（設計47 の演出・固定の軌道で扱う）",
            "boat_mid（座席）は t 11.17〜11.93 s に浮力点がすべて水の外（打ち上げ）、傾き最大 55°、上下の加速度最大 15 m/s²。目は全コマで水の上（余裕の最小 0.49 m）。原画の t* の姿勢（船首上げ 33°）と位置には一致しない → 設計44 の固定の軌道への引き継ぎ（D26）、設計45 の快適さ",
            "修正の1回（確かめの must_fix）：run2 までの全体の動画で boat_left が t ≈ 2〜10 s に見えなかったのは、小波や白い面の陰ではなく、DS30_SinglePlayback.unity で有効のまま残っていた"
            "美術優先の静的な仮置き M1_Revision_LeftSupport（revision_slopes.fbx、y 0.64〜6.53 m、x −25〜−5、z −15〜−4）の下に、自由に浮く boat_left が入っていたため"
            "（その上面は 421 コマ中 322 コマで船底の 37 サンプルすべての上、全コマで 1 サンプル以上の上、竜骨からの高さの中央値 5.8 m）。3 枚の海のシートは全体のカメラから boat_left を隠していない。"
            "試験の場面（DS43BoatWaterTest の HideNames）でだけ隠して run3 を取り直した。船はこの網を読まないので ds43_frames.jsonl は run2 とバイトまで同じで、数値は変わらない",
            "原画の場面では t* の boat_left（根 y 4.82）は今も M1_Revision_LeftSupport の上に乗っている。t* より前に自由に浮く・演出で動かす boat_left は、仕上げ30 でこの仮置きを置き換えるまで、この静的な面と食い違う（設計47 の背景の船の演出へ申し送り）",
            "boat_mid の打ち上げ（t 11.17〜11.93 s）の元は表示の水そのもの：浮力点の下の表示面が t 10.77 s に 4.6 m/s で上がり、t 10.97 s に最大 −38.5 m/s²（約 −3.9 g）で減速する（near のシートのつなぎの帯。確かめの測定）。"
            "船用水面データは表示と合っており、自由表面らしくない表示の動きが船を投げる → 設計44 の引き継ぎは t ≈ 10.5 s より前、設計45 の快適さ、仕上げ30・43",
            "時刻のずれ 0 フレームは試験の手順（各物理の段の前に再生器へ Seek）でだけ示した。Play では FixedUpdate が DS30SinglePlayback.Update（τ を決める）より先に走るので、"
            "船は 1 コマ前の水を読む（ずれ 1 コマで RMS 5.7 cm・最大 0.53 m）。保存した DS43_BoatWater.unity の DS42Buoyancy は stepInFixedUpdate = 0（試験が手で Step するため）で、"
            "Play では浮力が働かず沈む。設計44・46 で実行時の順序（物理の前に時計を進める、または時計から浮力を進める）と Play でのずれの測定が要る",
            "boat_fg は全区間で一価の海の上。上下の加速度の最大 6.2 m/s²（t 1.1 s、far の粗い網の上）",
            "far の表示の網は粗く、網の折れ目で水面の加速度が跳ぶ（船の上下の加速度に出る）。仕上げ30・仕上げ43 の候補",
            "水の流速（設計書 §5 の船用データの流速）は読んでいない。水平の抵抗は設計42 のまま絶対速度に対して働く（仕上げ43）",
            "関心の範囲（船のまわり ±16 m）の外は予備の y = 0。試験では予備の使用 0 回。設計44 の操船域では範囲を船に合わせて動かす必要がある",
            "HMD 実機ではない。PC の batchmode（RTX 3080、Direct3D11）の Editor の物理と描画だけ"],
        outputs=dict(video="Unity/Build/Design/43/boatwater/ds43_boatwater_wide_seat_30fps.mp4", figure="Unity/Build/Design/43/boatwater/fig_ds43_boatwater.png",
                     stills="Unity/Build/Design/43/boatwater/stills_ds43_t06_t11.5.png", measure="Unity/Build/Design/43/boatwater/measure/ds43_measure.json",
                     unity_report="Unity/Build/Design/43/boatwater/unity/ds43_unity_report.json", sea_function="Unity/Build/Design/43/boatwater/sea_function_ds43.json"))
    C.save_json(os.path.join(OUT, "metrics.json"), metrics)
    # run.json
    files = ["Tools/GWWaveGen/ds43/ds43_common.py", "Tools/GWWaveGen/ds43/ds43_precheck.py", "Tools/GWWaveGen/ds43/ds43_boats.py", "Tools/GWWaveGen/ds43/ds43_measure.py",
             "Tools/GWWaveGen/ds43/ds43_sea_function.py", "Tools/GWWaveGen/ds43/ds43_report.py", "Tools/GWWaveGen/ds43/run_ds43_unity.ps1",
             "Unity/Assets/GreatWave/Design43/Scripts/DS43SheetReader.cs", "Unity/Assets/GreatWave/Design43/Scripts/DS43BoatWater.cs",
             "Unity/Assets/GreatWave/Design43/Editor/DS43BoatWaterTest.cs", "Unity/Assets/GreatWave/Design43/Data/ds43_boats.json",
             "Unity/Assets/GreatWave/Design43/Data/ds43_buoyancy_points_boat_mid.json", "Unity/Assets/GreatWave/Design43/Data/ds43_buoyancy_points_boat_fg.json",
             "Unity/Assets/GreatWave/Design43/Data/ds43_buoyancy_points_boat_left.json", "Unity/Assets/GreatWave/Design43/Scenes/DS43_BoatWater.unity",
             "Unity/Build/Design/43/boatwater/sea_function_ds43.json", "Unity/Build/Design/43/boatwater/ds43_boatwater_wide_seat_30fps.mp4",
             "Unity/Build/Design/43/boatwater/fig_ds43_boatwater.png", "Unity/Build/Design/43/boatwater/stills_ds43_t06_t11.5.png",
             "Unity/Build/Design/43/boatwater/measure/ds43_measure.json", "Unity/Build/Design/43/boatwater/measure/ds43_series.npz",
             "Unity/Build/Design/43/boatwater/precheck/ds43_precheck_analytic_vs_display.json",
             "Unity/Build/Design/43/boatwater/unity/ds43_unity_report.json", "Unity/Build/Design/43/boatwater/unity/ds43_frames.jsonl",
             "Unity/Build/Design/43/boatwater/logs/unity_ds43_run1.log", "Unity/Build/Design/43/boatwater/logs/unity_ds43_run2.log",
             "Unity/Build/Design/43/boatwater/logs/unity_ds43_run3.log"]
    inputs = ["Unity/Build/Design/30/sea/sea_function.json", "Unity/Build/Design/30/sea/near/ds27_keypose.json", "Unity/Build/Design/30/sea/far/ds27_keypose.json",
              "Unity/Build/Design/28R01F/F_final/art_on/ds27_keypose.json", "Unity/Build/Design/28R01F/F_final/timewarp_F_final.json",
              "Tools/GWWaveGen/ds30/ds30_params.json", "Tools/GWWaveGen/ds30/ds30_sea.py", "Unity/Assets/GreatWave/Design42/Data/ds42_buoyancy_points.json",
              "Tools/GWContext/seat_v1.json", "Docs/Evidence/Design/41/metrics.json"]
    sha = {f: C.sha256_file(os.path.join(C.REPO, f)) for f in files + inputs if os.path.exists(os.path.join(C.REPO, f))}
    run = dict(schema="GreatWave.DS43.run/1", number="設計43", part="boatwater", created_utc=metrics["created_utc"],
               tools=dict(python="py -3.10（numpy・OpenCV）", unity="6000.4.3f1 batchmode（run_ds43_unity.ps1、unity.lock）", ffmpeg="G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"),
               commands=["py -3.10 -B Tools/GWWaveGen/ds43/ds43_precheck.py",
                         "py -3.10 -B Tools/GWWaveGen/ds43/ds43_boats.py",
                         "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds43/run_ds43_unity.ps1 -Method GreatWave.Design43.EditorTools.DS43BoatWaterTest.Run -Log run3（修正の1回：試験の場面で M1_Revision_LeftSupport も隠した。run2 は run1 と全体の視点のカメラだけ違う。ds43_frames.jsonl は run2 とバイトまで同じ）",
                         "py -3.10 -B Tools/GWWaveGen/ds43/ds43_measure.py",
                         "py -3.10 -B Tools/GWWaveGen/ds43/ds43_sea_function.py",
                         "ffmpeg -framerate 30 -i unity/frames/wide_%04d.jpg -framerate 30 -i unity/frames/seat_%04d.jpg -filter_complex \"[0][1]hstack,format=yuv420p\" -c:v libx264 -crf 23 ds43_boatwater_wide_seat_30fps.mp4",
                         "py -3.10 -B Tools/GWWaveGen/ds43/ds43_report.py"],
               sha256=sha, heavy_not_hashed_ja="GPU の読み戻し unity/gpu_{hero,near,far}.f32（合計 約 780 MB）と JPG のコマ（842 枚）は Git 対象外のまま（SHA-256 は取っていない）")
    C.save_json(os.path.join(OUT, "run.json"), run)
    print("pass", metrics["min_acceptance"]["pass_"], fig, still)


if __name__ == "__main__":
    main()
