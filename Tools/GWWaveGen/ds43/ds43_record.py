# -*- coding: utf-8 -*-
"""設計43 の記録の道具：作る部の出力の SHA-256 を照合し、時系列から数え直し、証拠を写し、記録の metrics.json・run.json を書く。

- 照合：作る部の run.json の sha256 にある各ファイルを読み直して比べる（違えば止まる）。
- 数え直し（作る部の図の道具 ds43_report.py を使わない。重い GPU の読み戻しは読まない）：
  ds43_frames.jsonl の τ（再生器・3 枚のシート・船用水面データ）、ds43_series.npz の船用水面データの高さ hb と表示面の高さ hd と交わりの数から、
  非砕波域（交わり 1）の差の最大・交わりの数の食い違い・表示面なし・砕波域の最初の時刻・浮力点がすべて水の外のコマ、
  船の傾き（局所の上と鉛直の角）・根の高さの 30 Hz の二階差分、boat_mid の浮力点の下の表示面の上がる速さと加速度、座席の目の余裕、
  全体の視点の JPG で各船の根の投影の ±18 px に船の色の画素があるコマの数、場面 DS43_BoatWater.unity の仮置きの有効・無効と stepInFixedUpdate。
- 証拠：Docs/Evidence/Design/43/ へ写す（図・静止画は 1920 × 1080 の PNG、動画は 5 MB 以下、JSON）。
使い方：py -3.10 -B Tools/GWWaveGen/ds43/ds43_record.py
出力：Docs/Evidence/Design/43/（metrics.json・run.json・ds43_record_recount.json ほか）
PC の batchmode の出力を読むだけで、Unity と HMD は使わない。
"""
import hashlib
import json
import os
import re
import shutil
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
B43 = os.path.join(REPO, "Unity", "Build", "Design", "43")
OUT = os.path.join(B43, "boatwater")
IND = os.path.join(B43, "indep_check")
EVD = os.path.join(REPO, "Docs", "Evidence", "Design", "43")
SCENE = os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design43", "Scenes", "DS43_BoatWater.unity")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def dump(p, d):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")


def rel(p):
    return os.path.relpath(p, REPO).replace(os.sep, "/")


def hms(ts):
    return time.strftime("%H:%M:%S", time.localtime(ts))


def verify(run):
    rows, bad = [], []
    for k, v in run["sha256"].items():
        p = os.path.join(REPO, k)
        got = sha(p) if os.path.exists(p) else None
        rows.append(dict(path=k, expected=v, same=got == v))
        if got != v:
            bad.append(k)
    return rows, bad


def up_vec(q):
    x, y, z, w = q
    u = np.array([x, y, z], float)
    v = np.array([0.0, 1.0, 0.0])
    return v + 2 * np.cross(u, np.cross(u, v) + w * v)


# 全体の視点のカメラ（DS43BoatWaterTest.MakeCam("DS43 全体", (12, 45, −80) → (−3, 0, −18), 縦の画角 45°)、960 × 540）
CAM = np.array([12.0, 45.0, -80.0])
TGT = np.array([-3.0, 0.0, -18.0])
FW, FH, FOV = 960, 540, 45.0


def project(p):
    f = TGT - CAM
    f /= np.linalg.norm(f)
    r = np.cross([0.0, 1.0, 0.0], f)
    r /= np.linalg.norm(r)
    u = np.cross(f, r)
    fy = (FH / 2) / np.tan(np.radians(FOV / 2))
    d = p - CAM
    return FW / 2 + fy * (d @ r) / (d @ f), FH / 2 - fy * (d @ u) / (d @ f)


def boat_pixels(img, x, y, rad=18):
    x, y = int(round(x)), int(round(y))
    p = img[max(0, y - rad):y + rad + 1, max(0, x - rad):x + rad + 1].astype(int)
    b, g, r = p[..., 0], p[..., 1], p[..., 2]
    # 船の色（AF27_Flat_boat_ochre などの黄土色）：赤 ≥ 150、赤 − 青 ≥ 40、赤 ≥ 緑。白（泡・富士）と藍は入らない
    return int(((r >= 150) & (r - b >= 40) & (r >= g)).sum())


def recount():
    fr = [json.loads(l) for l in open(os.path.join(OUT, "unity", "ds43_frames.jsonl"), encoding="utf-8")]
    z = np.load(os.path.join(OUT, "measure", "ds43_series.npz"))
    t, hb, hd, nb, nd = z["t"], z["hb"], z["hd"], z["nb"], z["nd"]
    keys = [str(k) for k in z["keys"]]
    out = dict(frames=len(fr))
    out["tau"] = dict(
        tauWater_minus_tauPlay_absmax_s=float(max(abs(f["tauWater"] - f["tauPlay"]) for f in fr)),
        tauSheets_minus_tauPlay_absmax_s=float(max(abs(s - f["tauPlay"]) for f in fr for s in f["tauSheets"])),
        tau_play_first_last=[fr[0]["tauPlay"], fr[-1]["tauPlay"]],
        frames_tau_static_at_end=int(sum(1 for i in range(1, len(fr)) if fr[i]["tauPlay"] == fr[i - 1]["tauPlay"])))
    single_all = []
    boats = {}
    dt = 1.0 / 30.0
    for bi, k in enumerate(keys):
        s = nd[:, bi] == 1
        m = nd[:, bi] >= 2
        d1 = np.abs(hb[:, bi][s] - hd[:, bi][s])
        single_all.append(d1)
        tilt = np.array([np.degrees(np.arccos(np.clip(up_vec(f["boats"][bi]["rot"])[1], -1, 1))) for f in fr])
        y = z["pos"][:, bi, 1]
        acc = np.diff(y, 2) / dt ** 2
        tt = t[1:-1]
        wet = z["wet"][:, bi]
        wz = np.nonzero(wet == 0)[0]
        rec = dict(
            nonbreaking_samples=int(s.sum()), nonbreaking_absmax_m=float(d1.max()),
            hit_count_mismatch=int((nb[:, bi] != nd[:, bi]).sum()), no_display_hit=int((nd[:, bi] == 0).sum()),
            breaking_samples=int(m.sum()),
            breaking_underside_absmax_m=float(np.abs(hb[:, bi][m] - hd[:, bi][m]).max()) if m.any() else None,
            first_breaking_t=float(t[m.any(1)][0]) if m.any() else None,
            wet_zero_frames=int(len(wz)), wet_zero_t=[float(t[wz[0]]), float(t[wz[-1]])] if len(wz) else None,
            tilt_max_deg=float(tilt.max()), tilt_max_t=float(t[tilt.argmax()]), tilt_max_deg_t_le_9s=float(tilt[t <= 9].max()),
            heave_acc_30hz_absmax=float(np.abs(acc).max()), heave_acc_30hz_absmax_t=float(tt[np.abs(acc).argmax()]),
            heave_acc_30hz_absmax_t_le_9s=float(np.abs(acc[tt <= 9]).max()),
            root_y_range_m=[float(y.min()), float(y.max())])
        boats[k] = rec
    d_all = np.concatenate(single_all)
    out["hull_vs_display"] = dict(nonbreaking_samples=int(d_all.size), absmax_m=float(d_all.max()), p99_m=float(np.percentile(d_all, 99)))
    out["per_boat"] = boats
    # boat_mid の浮力点（サンプル 0〜9）の下の表示面の平均の高さ：上がる速さ（中心差分）と加速度（二階差分）
    wm = hd[:, 0, :10].mean(1)
    v = np.gradient(wm, dt)
    a = np.diff(wm, 2) / dt ** 2
    sel = np.nonzero((t > 10.0) & (t < 11.2))[0]
    out["display_under_boat_mid_points"] = dict(
        rise_speed_max_m_s=float(v[sel].max()), rise_speed_max_t=float(t[sel][v[sel].argmax()]),
        acc_min_m_s2=float(a.min()), acc_min_t=float(t[1:-1][a.argmin()]),
        note_ja="boat_mid の浮力点 10 の下の表示面の高さ（numpy が GPU の読み戻しから求めた hd）の平均の 30 Hz の差分。点は船とともに動く")
    em = z["eye_margin"]
    out["seat_eye"] = dict(in_water_frames=int(z["eye_in_water"].sum()), margin_min_m=float(em.min()), margin_min_t=float(t[em.argmin()]))
    # 全体の視点のコマで、根の投影の ±18 px に船の色の画素があるコマ（t 2〜10 s）
    fdir = os.path.join(OUT, "unity", "frames")
    cnt = {k: [] for k in keys}
    for n in range(len(fr)):
        img = cv2.imread(os.path.join(fdir, "wide_%04d.jpg" % n))
        for bi, k in enumerate(keys):
            cnt[k].append(boat_pixels(img, *project(np.array(fr[n]["boats"][bi]["pos"], float))))
    win = (t >= 2.0) & (t <= 10.0)
    vis = {}
    for k in keys:
        c = np.array(cnt[k])
        vis[k] = dict(frames_t2_10=int(win.sum()), frames_with_boat_pixels=int((c[win] > 0).sum()),
                      median_px=float(np.median(c[win])), min_px=int(c[win].min()), min_px_t=float(t[win][c[win].argmin()]),
                      px_at_t2_t6_t9=[int(c[60]), int(c[180]), int(c[270])])
    out["wide_view_boat_pixels_run3"] = dict(rule_ja="全体の視点の JPG（960 × 540）で、船の根の位置を投影した点の ±18 px の中の、赤 ≥ 150・赤 − 青 ≥ 40・赤 ≥ 緑 の画素の数",
                                             boats=vis)
    # 場面の仮置きと浮力の段の設定
    txt = open(SCENE, encoding="utf-8").read()
    mls = re.search(r"m_Name: M1_Revision_LeftSupport\n(?:.*\n){0,6}?\s*m_IsActive: (\d)", txt)
    out["scene"] = dict(
        sha256=sha(SCENE), bytes=os.path.getsize(SCENE),
        M1_Revision_LeftSupport_m_IsActive=int(mls.group(1)) if mls else None,
        stepInFixedUpdate_values=[int(x) for x in re.findall(r"stepInFixedUpdate: (\d)", txt)])
    return out


def compare(rc, bm):
    """作る部の metrics.json と数え直しの差（絶対値）。"""
    c = {}
    c["hull_absmax"] = abs(rc["hull_vs_display"]["absmax_m"] - bm["min_acceptance"]["hull_vs_display"]["value_absmax_m"])
    c["hull_p99"] = abs(rc["hull_vs_display"]["p99_m"] - bm["min_acceptance"]["hull_vs_display"]["p99_m"])
    c["eye_margin"] = abs(rc["seat_eye"]["margin_min_m"] - bm["min_acceptance"]["seat_eye_above_water"]["margin_min_m"])
    for k, v in rc["per_boat"].items():
        pb = bm["per_boat"][k]
        c[k + "_absmax"] = abs(v["nonbreaking_absmax_m"] - pb["nonbreaking_absmax_m"])
        c[k + "_samples"] = abs(v["nonbreaking_samples"] - pb["nonbreaking_samples"])
        c[k + "_wet0"] = abs(v["wet_zero_frames"] - pb["wet_zero_frames"])
        mr = bm["motion_record"][k]
        c[k + "_heave_acc_all"] = abs(v["heave_acc_30hz_absmax"] - mr["heave_acc_absmax_all"])
    return {k: float(v) for k, v in c.items()}


def letterbox(src, dst, w=1920, h=1080, bg=(255, 255, 255)):
    im = cv2.imread(src)
    sh, sw = im.shape[:2]
    s = min(w / sw, h / sh)
    nw, nh = int(round(sw * s)), int(round(sh * s))
    im2 = cv2.resize(im, (nw, nh), interpolation=cv2.INTER_NEAREST if s >= 1 else cv2.INTER_AREA)
    can = np.full((h, w, 3), bg, np.uint8)
    x0, y0 = (w - nw) // 2, (h - nh) // 2
    can[y0:y0 + nh, x0:x0 + nw] = im2
    cv2.imwrite(dst, can)
    return dict(src_size=[sw, sh], scale=s, placed=[x0, y0, nw, nh])


def file_times():
    def ct(p):
        st = os.stat(os.path.join(REPO, p))
        return hms(st.st_ctime), hms(st.st_mtime)
    items = ["Tools/GWWaveGen/ds43", "Unity/Build/Design/43", "Tools/GWWaveGen/ds43/ds43_common.py",
             "Unity/Build/Design/43/boatwater/precheck/ds43_precheck_analytic_vs_display.json",
             "Tools/GWWaveGen/ds43/ds43_boats.py", "Unity/Assets/GreatWave/Design43/Scripts/DS43SheetReader.cs",
             "Unity/Assets/GreatWave/Design43/Scripts/DS43BoatWater.cs", "Tools/GWWaveGen/ds43/run_ds43_unity.ps1",
             "Unity/Build/Design/43/boatwater/logs/unity_ds43_run1.log", "Tools/GWWaveGen/ds43/ds43_measure.py",
             "Tools/GWWaveGen/ds43/ds43_sea_function.py", "Unity/Build/Design/43/boatwater/sea_function_ds43.json",
             "Unity/Build/Design/43/boatwater/logs/unity_ds43_run2.log", "Tools/GWWaveGen/ds43/ds43_report.py",
             "Unity/Build/Design/43/indep_check/chk43.py", "Unity/Build/Design/43/indep_check/chk43_result.json",
             "Unity/Build/Design/43/indep_check/ls_check.py",
             "Unity/Assets/GreatWave/Design43/Editor/DS43BoatWaterTest.cs",
             "Unity/Build/Design/43/boatwater/logs/unity_ds43_run3.log",
             "Unity/Assets/GreatWave/Design43/Scenes/DS43_BoatWater.unity",
             "Unity/Build/Design/43/boatwater/metrics.json"]
    return {p: dict(created=ct(p)[0], modified=ct(p)[1]) for p in items if os.path.exists(os.path.join(REPO, p))}


def main():
    t0 = time.time()
    os.makedirs(EVD, exist_ok=True)
    run_b = load(os.path.join(OUT, "run.json"))
    rows, bad = verify(run_b)
    if bad:
        print("SHA-256 が作る部の run.json と違う：", bad)
        sys.exit(1)
    met_b = load(os.path.join(OUT, "metrics.json"))
    rc = recount()
    cmp_ = compare(rc, met_b)
    indep = load(os.path.join(IND, "chk43_result.json"))

    # 証拠の写し
    copies = {
        "fig_ds43_boatwater.png": os.path.join(OUT, "fig_ds43_boatwater.png"),
        "stills_ds43_t06_t11.5.png": os.path.join(OUT, "stills_ds43_t06_t11.5.png"),
        "ds43_boatwater_wide_seat_30fps.mp4": os.path.join(OUT, "ds43_boatwater_wide_seat_30fps.mp4"),
        "ds43_boatwater_metrics.json": os.path.join(OUT, "metrics.json"),
        "ds43_boatwater_run.json": os.path.join(OUT, "run.json"),
        "sea_function_ds43.json": os.path.join(OUT, "sea_function_ds43.json"),
        "ds43_measure.json": os.path.join(OUT, "measure", "ds43_measure.json"),
        "ds43_unity_report.json": os.path.join(OUT, "unity", "ds43_unity_report.json"),
        "ds43_precheck_analytic_vs_display.json": os.path.join(OUT, "precheck", "ds43_precheck_analytic_vs_display.json"),
        "ds43_indep_check.json": os.path.join(IND, "chk43_result.json"),
    }
    for dst, src in copies.items():
        shutil.copyfile(src, os.path.join(EVD, dst))
    lb = letterbox(os.path.join(OUT, "fix01_leftsupport_wide_before_after.png"), os.path.join(EVD, "fig_ds43_fix01_leftsupport_before_after.png"))
    for f in ("fig_ds43_boatwater.png", "stills_ds43_t06_t11.5.png", "fig_ds43_fix01_leftsupport_before_after.png"):
        im = cv2.imread(os.path.join(EVD, f))
        assert im.shape[:2] == (1080, 1920), f
    mp4 = os.path.join(EVD, "ds43_boatwater_wide_seat_30fps.mp4")
    assert os.path.getsize(mp4) <= 5 * 1024 * 1024

    recount_doc = dict(schema="GreatWave.DS43.record_recount/1", number="設計43",
                       note_ja="記録の道具 ds43_record.py の数え直し。作る部の図の道具（ds43_report.py）は使わず、ds43_frames.jsonl・ds43_series.npz・全体の視点の JPG・場面のファイルから数えた。重い GPU の読み戻しは読んでいない",
                       recount=rc, diff_vs_builder_metrics=cmp_, fix01_letterbox=lb)
    dump(os.path.join(EVD, "ds43_record_recount.json"), recount_doc)

    ma = met_b["min_acceptance"]
    metrics = dict(
        schema="GreatWave.DS43.record_metrics/1", number="設計43", title_ja="船用水面データで小波へ反応させる",
        created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        evidence_kind_ja="PC の Unity 6000.4.3f1 batchmode（RTX 3080、Direct3D11）の物理と描画、numpy の測定、進行役の独立の検査。HMD 実機ではない。利用者は確かめていない",
        plan_ja="計画 §2.4 設計43：設計30 のうねりと、主役波のシートの下側の一価の面を、同じ時計で船が読む。表示面と船底の差、位置と時刻のずれを測る",
        min_acceptance_ja=met_b["min_acceptance_ja"],
        acceptance=dict(
            hull_vs_display=dict(criterion_m=0.05, builder_absmax_m=ma["hull_vs_display"]["value_absmax_m"], builder_p99_m=ma["hull_vs_display"]["p99_m"],
                                 record_recount_absmax_m=rc["hull_vs_display"]["absmax_m"], indep_absmax_m=indep["hull_vs_display"]["absmax_m"],
                                 samples=ma["hull_vs_display"]["nonbreaking_samples"], pass_=bool(ma["hull_vs_display"]["pass_"] and indep["hull_vs_display"]["pass_le_5cm"])),
            time_offset=dict(criterion_frames=0, builder_best_lag=ma["time_offset"]["best_lag_frames"], builder_lag_rms_m=ma["time_offset"]["lag_rms_m"],
                             indep_best_lag=indep["lag"]["best"], indep_lag=indep["lag"]["by_L"],
                             record_tau_offsets_s=[rc["tau"]["tauWater_minus_tauPlay_absmax_s"], rc["tau"]["tauSheets_minus_tauPlay_absmax_s"]],
                             pass_=bool(ma["time_offset"]["pass_"] and indep["lag"]["best"] == "0"),
                             scope_ja="試験の手順（各物理の段の前に再生器へ Seek）でだけ示した。Play の順序では 1 コマ遅れる見込み（限界 1）"),
            seat_eye_above_water=dict(in_water_frames=rc["seat_eye"]["in_water_frames"], margin_min_m=rc["seat_eye"]["margin_min_m"],
                                      margin_min_t=rc["seat_eye"]["margin_min_t"], pass_=ma["seat_eye_above_water"]["pass_"]),
            position_offset=met_b["position_offset"],
            pass_=bool(ma["pass_"])),
        backlog=met_b["backlog"],
        decisions_q24=met_b["decisions_q24"],
        fix_rounds=dict(count=1, fix01_ja="確かめの必須の指摘：boat_left が全体の動画の t ≈ 2〜10 s に見えないのは、DS30 の場面で有効のまま残っていた静的な仮置き M1_Revision_LeftSupport の下に入っていたため。試験の場面だけで隠して run3 を取り直した。ds43_frames.jsonl は run2 とバイトまで同じ",
                        after_visibility=rc["wide_view_boat_pixels_run3"]["boats"]["boat_left"]),
        record_recount=dict(file="Docs/Evidence/Design/43/ds43_record_recount.json", diff_vs_builder_max=float(max(cmp_.values()))),
        builder_sha256_verified=dict(files=len(rows), all_same=not bad),
        time=dict(box_ja="Q26 の日程で 3 時間（計画 §2.6 の［Q26］の表、10/3 の行。計画の時間枠は ≤0.75日）", file_times=file_times(),
                  builder_report_ja="作る部の報告は「3 時間の内の約 2 時間 40 分」。ファイルの時刻と合わない（記録の第 9 節）",
                  unity_in_run_s=met_b["design"]["unity_seconds"], measure_s=load(os.path.join(OUT, "measure", "ds43_measure.json"))["seconds"],
                  precheck_s=load(os.path.join(OUT, "precheck", "ds43_precheck_analytic_vs_display.json"))["seconds"],
                  indep_check_s=indep["seconds"]),
        hmd_ja="保留（PS VR2 の導入は利用者の手）。Mock の両眼も描いていない",
        painting_view_ja="原画視点の場面は変えていない（DS30_SinglePlayback.unity は開いただけで保存しない）。守るファイル 17 の SHA-256 は前後で同じ。計画 §2.0 の回帰は対象外",
        handoffs_ja=[
            "設計44：座席の船の固定の軌道への引き継ぎは t ≈ 10.5 s より前（boat_mid は t 11.17〜11.93 s に打ち上げられる）。表示の船（原画の場面は設計30 の上下のまま）と物理の船のそろえ方（喫水の差 132 mm、設計42 の限界 1）。Play の実行の順序（物理の前に時計を進める、または時計から浮力を進める）と Play でのずれの測定。関心の範囲（±16 m の固定）を船に合わせて動かす。首振りのずれ（設計42 の限界 7）",
            "設計45：上下の加速度（boat_fg 6.2 m/s²・far の網の折れ目、boat_mid 15.2 m/s²・打ち上げ）",
            "設計46：共通時計から水面と船用水面データを進める（今は DS30SinglePlayback の τ を読む）",
            "設計47：背景の船（boat_fg・boat_left）の演出。boat_left は t* に M1_Revision_LeftSupport の上に乗る",
            "仕上げ30：far の網を細かくする、または far の頂点の式、M1_Revision_LeftSupport の置き換え、near の接続の帯の表示の動き（−38.5 m/s²）",
            "仕上げ43（89・90・203）：水の流速、式を読む道、相似の表の質量、砕波域の浸かり方"],
        evidence=sorted(os.listdir(EVD)),
    )
    dump(os.path.join(EVD, "metrics.json"), metrics)

    ev_sha = {rel(os.path.join(EVD, f)): sha(os.path.join(EVD, f)) for f in sorted(os.listdir(EVD)) if f not in ("run.json",)}
    code = {}
    for root in (os.path.join(REPO, "Tools", "GWWaveGen", "ds43"), os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design43")):
        for dp, dn, fn in os.walk(root):
            for f in sorted(fn):
                code[rel(os.path.join(dp, f))] = sha(os.path.join(dp, f))
    run = dict(
        schema="GreatWave.DS43.record_run/1", number="設計43", created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        tools=dict(python=sys.version.split()[0], numpy=np.__version__, opencv=cv2.__version__, unity="6000.4.3f1（batchmode。記録では使っていない）",
                   ffmpeg="G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe（作る部）"),
        builder_commands=run_b["commands"],
        record_commands=["py -3.10 -B Unity/Build/Design/43/indep_check/chk43.py（進行役の独立の検査。Git 対象外の写し。出力の場所はリポジトリの外）",
                         "py -3.10 -B Tools/GWWaveGen/ds43/ds43_record.py"],
        inputs_sha256=run_b["sha256"],
        code_sha256=code,
        evidence_sha256=ev_sha,
        seconds=round(time.time() - t0, 1),
        note_ja="SHA-256 は作業の木のバイト（テキストは LF）の値。重い GPU の読み戻しと JPG のコマは Git 対象外で SHA-256 を取っていない")
    dump(os.path.join(EVD, "run.json"), run)
    print(json.dumps(dict(verified=len(rows), bad=bad, diff_max=max(cmp_.values()), seconds=run["seconds"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
