"""全フレームの運動検査 M1–M6（旧仕様の第6.2～6.4節）。無画面で単独実行できる。

  blender --background --factory-startup --python-exit-code 1 [file.blend] --python tests/test_motion.py -- --object <name>
          [--blend <path>] [--build-script <py> ...] [--frame-start A] [--final-frame N]
          [--res-scale 0.25] [--phase-frames A,B] [--fps 30] [--frame-step 1] [--houdini-json <path>]
直接起動では --python-exit-code 1 が必須。main() 内の例外は判定 ERROR、終了コード2とする。

各フレームのCAM_printシルエットから h、x_c、θ、o、φと前フレームからの輪郭変位を測る。
閾値は tests/thresholds.json のみから読み、両段階を報告する。
結果は results/<YYYYMMDD_HHMMSS>_motion/ の metrics.json、summary.md、運動曲線、速度・突跳図、
15フレーム間隔の一覧図に保存する。参照JSONがあればHoudini比較図も作るが、数値判定はしない。

バックログの別解釈に基づくM6の中央値式と10秒保持、減速の単調性、θの最大段差は報告専用。
非有限頂点・脱離成分・静水面に届かないフレームの数も報告する。
判定値を測れない場合は NOT_MEASURABLE として失敗に含め、黙って合格にしない。
設定を既定値から変更した判定には NON-DEFAULT SETTINGS を付ける。
"""
import argparse
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import common_test as ct  # noqa: E402
from common_test import bootstrap, draw, imgio, paths, plot, pm, silhouette, log  # noqa: E402

TEST_NAME = "motion"
HOUDINI_JSON = os.path.join(paths.TARGET_DIR, "houdini_motion.json")


def add_args(ap):
    g = ap.add_argument_group("motion")
    g.add_argument("--phase-frames", default=None, metavar="A,B",
                   help="張り出し開始と巻き込み開始のフレーム。自動検出値を上書きする。params.json の motion_phase_frames も参照")
    g.add_argument("--frame-step", type=int, default=None, help="n フレームごとに評価。既定は TEST_SETTINGS の motion_frame_step=1。n>1 では M5/M6 は受入判定に使えず、判定に NON-DEFAULT SETTINGS が付く")
    g.add_argument("--hold-frames", type=int, default=None, help="最終フレーム後に評価するフレーム数。既定は TEST_SETTINGS の hold_frames")
    g.add_argument("--backlog-hold-s", type=float, default=None,
                   help="報告専用：旧定義『10 秒保持、変位 0.2 %% 以下』を読む保持時間（秒）。既定は TEST_SETTINGS の backlog_hold_s。0 は省略")
    g.add_argument("--houdini-json", default=None, help="Houdini の参照曲線。存在する場合の既定は target/houdini_motion.json")
    return ap


# ------------------------------------------------------------------------------------ phases
def detect_phases(frames, seq, final_frame, S):
    """測定値から区間境界を決める（解釈値は common_test.INTERPRETATION_NOTES['phases']）。
    フレーム番号（検出不能なら None）と注記の辞書を返す。"""
    fr = np.asarray(frames)
    n = len(fr)
    over = np.asarray(seq["overhanging"], dtype=bool)
    disp = np.array([np.nan if v is None else v for v in seq["disp_max_H"]], dtype=np.float64)
    notes = []
    upto = np.nonzero(fr <= final_frame)[0]
    i_final = int(upto[-1]) if upto.size else n - 1
    moving = np.nonzero((disp[:i_final + 1] > float(S["static_disp_eps_H"])))[0]
    i_stop = int(moving[-1]) if moving.size else None
    if i_stop is None:
        notes.append("輪郭が一度も動かないため、停止フレームを特定できない")
    # 停止フレームまで張り出し状態が持続する最初のフレーム
    i_end = i_stop if i_stop is not None else i_final
    i_A = None
    if over[:i_end + 1].any() and over[i_end]:
        k = i_end
        while k > 0 and over[k - 1]:
            k -= 1
        i_A = k
        if over[:k].any():
            notes.append("フレーム %d より前に張り出しが断続する（%s で張り出した後、いったん消える）"
                         % (fr[k], [int(v) for v in fr[:k][over[:k]]][:10]))
    else:
        notes.append("停止フレームまで持続する張り出しがなく、張り出し・巻き込み区間を検出できない")
    i_B = None
    if i_A is not None:
        phi = np.array([np.nan if v is None else v for v in seq["phi_deg"]], dtype=np.float64)
        seg = phi[i_A:i_end + 1]
        if np.isfinite(seg).any():
            mx = np.nanmax(seg)
            i_B = int(i_A + np.nonzero(seg == mx)[0][-1])
            if i_B >= i_end:
                notes.append("phi が停止フレームで最大になる。頭部は下向きに転じず、巻き込み区間がない")
            if i_B == i_A:
                notes.append("phi が張り出し開始フレームで最大になる。検出された張り出し区間は 1 フレームだけ")
        else:
            notes.append("頭部が phi の測定窓に対して短すぎるため、phi を測定できない")
    return {"i_A": i_A, "i_B": i_B, "i_stop": i_stop, "i_final": i_final, "notes": notes}


def _max_decrease(values, i0, i1):
    """values[i0..i1] の隣接値間の最大減少量を返す（0 以上の量、後のフレームの索引）。"""
    v = np.asarray(values[i0:i1 + 1], dtype=np.float64)
    if v.size < 2:
        return None, None
    d = v[:-1] - v[1:]
    d = np.where(np.isfinite(d), d, -np.inf)
    k = int(np.argmax(d))
    if not np.isfinite(d[k]):
        return None, None
    return float(max(d[k], 0.0)), i0 + k + 1


def _floor(raw, floor):
    if raw is None:
        return None
    return 0.0 if raw <= floor else float(raw)


# ------------------------------------------------------------------------------------ 旧定義に沿う別指標（報告専用）
def backlog_jump_ratios(disp_adj, i_final, i_stop, half_window, n_exclude, eps):
    """旧定義表に沿った M6：ratio(k) = d(k)／k の前後 half_window 対の変位中央値。下限は設けない。
    disp_adj[k] は k-1→k の輪郭変位で、非隣接または初回は nan。
    k > i_stop - n_exclude の対（停止前の減速窓と停止後）は報告する最大値から除外する。
    中央値が eps 以下なら比を d／eps とし、静止からの始動を大きな値として示す。
    戻り値は比（未定義は nan）、判定対象の真偽値、中央値の各配列。"""
    n = len(disp_adj)
    ratio, med = np.full(n, np.nan), np.full(n, np.nan)
    judged = np.zeros(n, bool)
    last = i_final if i_stop is None else min(i_final, i_stop)
    for k in range(1, i_final + 1):
        d = disp_adj[k]
        if not np.isfinite(d):
            continue
        nb = [disp_adj[j] for j in list(range(k - half_window, k)) + list(range(k + 1, k + half_window + 1))
              if 1 <= j <= i_final and np.isfinite(disp_adj[j])]
        if len(nb) < 2:
            continue
        med[k] = float(np.median(nb))
        ratio[k] = 0.0 if d <= eps else float(d / max(med[k], eps))
        judged[k] = k <= last - n_exclude
    return ratio, judged, med


def measure_backlog_hold(ctx, rect, final_profile_H, fN, fps, hold_s, step_frames, z_min_H):
    """最終フレーム後の hold_s 秒間の輪郭変位を測り、各標本を最終フレームの輪郭と比較する。
    旧定義表の第5項に対応。報告専用の辞書を返し、hold_s <= 0 なら None。"""
    n_hold = int(round(float(hold_s) * float(fps)))
    if n_hold <= 0 or final_profile_H is None:
        return None
    frames = sorted(set(list(range(fN + int(step_frames), fN + n_hold + 1, max(1, int(step_frames)))) + [fN + n_hold]))
    rows, worst = [], None
    for fr in frames:
        ctx.scene.frame_set(fr)
        try:
            prof, _mask, _info = silhouette.profile_of_objects(ctx.objs, rect=rect, water_z=ctx.water_z, exact=True)
        except silhouette.ProfileError as exc:
            rows.append({"frame": fr, "error": str(exc)})
            continue
        d = pm.contour_displacement(final_profile_H, prof["H"], z_min_H=z_min_H)
        rows.append({"frame": fr, "max_disp_H": d["max_H"], "max_disp_pct_h": float(pm.H_to_pct_h(d["max_H"]))})
        if worst is None or d["max_H"] > worst["max_disp_H"]:
            worst = rows[-1]
    ctx.scene.frame_set(fN)
    return {"hold_s": float(hold_s), "n_hold_frames": n_hold, "frames_sampled": frames, "rows": rows, "worst": worst,
            "scene_frame_end": int(ctx.scene.frame_end),
            "beyond_scene_frame_end": bool(fN + n_hold > int(ctx.scene.frame_end)),
            "n_errors": sum(1 for r in rows if "error" in r)}


# ------------------------------------------------------------------------------------ the test
def run(ctx, run_dir=None):
    S, F = ctx.settings, ctx.F
    args = ctx.args
    run_dir = run_dir or ctx.run_dir
    scale = float(args.res_scale) if getattr(args, "res_scale", None) else float(S["motion_res_scale"])
    step = max(1, int(getattr(args, "frame_step", None) or S["motion_frame_step"]))
    f0, fN = int(ctx.frame_start), int(ctx.final_frame)
    configured_hold = args.hold_frames if getattr(args, "hold_frames", None) is not None else S["hold_frames"]
    hold = max(0, int(ctx.scene.frame_end) - fN) if configured_hold is None else int(configured_hold)
    frames = list(range(f0, fN + 1, step))
    if frames[-1] != fN:
        frames.append(fN)
    frames += [fN + k for k in range(1, hold + 1)]
    fps = float(ctx.fps)
    rect = silhouette.ViewRect.from_cam_print(H=ctx.H, scale=scale)
    sheet_step = int(S["contact_sheet_step"])
    sheet_frames = set(range(f0, fN + 1, sheet_step)) | {fN}

    sw = ct.StopWatch()
    profiles, invalid, thumbs, per_frame_info, empty_frames = [], [], [], [], []
    nonfinite_frames, island_frames = [], []
    for fr in frames:
        ctx.scene.frame_set(fr)
        try:
            prof, mask, info = silhouette.profile_of_objects(ctx.objs, rect=rect, water_z=ctx.water_z, exact=True)
        except silhouette.ProfileError as exc:
            invalid.append({"frame": fr, "reason": str(exc)})
            continue
        bad = []
        if not prof["complete"]:
            bad.append("輪郭が %s 側の境界で終わる" % prof["end_border"])
        if prof["holes"]["hole_area_px"] > 0:
            bad.append("未充填の穴が %d px" % prof["holes"]["hole_area_px"])
        if info.get("mesh_area_px") == 0:
            if fr == fN:
                bad.append("最終フレームで静水面より上の対象領域が 0 px")
            else:
                empty_frames.append(fr)
        comp = prof["components"]
        n_nf, n_dt, n_isl = int(info.get("n_nonfinite_vertices") or 0), int(info.get("n_dropped_triangles") or 0), int(comp.get("n_removed_islands") or 0)
        if n_nf or n_dt:
            nonfinite_frames.append(fr)
            bad.append("有限でない幾何：NaN / inf 座標の頂点 %d 個、シルエットから除外した三角形 %d 個" % (n_nf, n_dt))
        if n_isl:
            island_frames.append(fr)
            big = [c for c in (comp.get("removed") or []) if c.get("kind") == "island"][:1]
            bad.append("離れたシルエット成分：微小領域の上限（この解像度で %s px）を超える成分を %d 個除外、合計 %s px%s"
                       % (ct._fmt(comp.get("speck_max_area_px")), n_isl, comp.get("removed_islands_area_px"),
                          "" if not big else "；最大成分 %d px、範囲 X %.3f..%.3f H、Z %.3f..%.3f H"
                          % (big[0]["area_px"], big[0]["bbox_H"][0], big[0]["bbox_H"][2], big[0]["bbox_H"][1], big[0]["bbox_H"][3])))
        if bad:
            invalid.append({"frame": fr, "reason": "; ".join(bad)})
        profiles.append((fr, prof["H"]))
        per_frame_info.append({"frame": fr, "complete": prof["complete"], "hole_area_px": prof["holes"]["hole_area_px"],
                               "removed_area_px": comp.get("removed_area_px"), "n_removed_islands": n_isl, "n_removed_specks": int(comp.get("n_removed_specks") or 0),
                               "n_nonfinite_vertices": n_nf, "n_dropped_triangles": n_dt})
        if fr in sheet_frames:
            met = pm.measure_profile(prof["H"])
            im = silhouette.draw_overlay(mask, prof, met, max_w=rect.width_px)
            im = draw.resize(im, new_w=460)
            thumbs.append((fr, im, met))
    t_prof = sw.lap()
    fr_ok = [p[0] for p in profiles]
    seq = pm.measure_sequence([p[1] for p in profiles], disp_z_min_H=float(S["disp_z_min_H"]))
    t_meas = sw.lap()
    log("[motion] %d frames (%dx%d px): profiles %.1f s, metrics %.1f s" % (len(fr_ok), rect.width_px, rect.height_px, t_prof, t_meas))

    n = len(fr_ok)
    fr = np.asarray(fr_ok)
    t_s = (fr - f0) / fps
    h = np.asarray(seq["h"], dtype=np.float64)
    o = np.asarray(seq["o"], dtype=np.float64)
    theta = np.asarray(seq["theta"], dtype=np.float64)
    x_c = np.asarray(seq["x_c"], dtype=np.float64)
    cav = np.asarray(seq["cavity_depth"], dtype=np.float64)
    phi = np.array([np.nan if v is None else v for v in seq["phi_deg"]], dtype=np.float64)
    disp = np.array([np.nan if v is None else v for v in seq["disp_max_H"]], dtype=np.float64)
    tip_x = np.array([np.nan if v is None else v[0] for v in seq["tip_H"]], dtype=np.float64)
    # 変位を測れるのは隣接する評価フレーム間だけ
    adj = np.zeros(n, bool)
    if n > 1:
        dfr = np.diff(fr)
        adj[1:] = (dfr == np.where(fr[1:] > fN, 1, step)) | ((fr[1:] == fN) & (dfr <= step))
    disp_adj = np.where(adj, disp, np.nan)

    # ---- phases
    det = detect_phases(fr_ok, seq, fN, S)
    given = None
    if getattr(args, "phase_frames", None):
        given = [int(v) for v in str(args.phase_frames).split(",")]
    else:
        try:
            given = [int(v) for v in paths.param("motion_phase_frames")]
        except KeyError:                       # only 'the entry does not exist'; a malformed params.json / entry must raise
            given = None
    i_A, i_B, i_stop, i_final = det["i_A"], det["i_B"], det["i_stop"], det["i_final"]
    phase_source = "detected"
    if given is not None and len(given) != 2:
        raise ValueError("--phase-frames / params.json motion_phase_frames must be exactly two frame numbers A,B; got %r" % (given,))
    if given:
        phase_source = "given"
        i_A = int(np.argmin(np.abs(fr - given[0])))
        i_B = int(np.argmin(np.abs(fr - given[1])))

    def frame_of(i):
        return None if i is None else int(fr[i])

    nf_h, nf_deg = float(S["monotonic_noise_floor_H"]), float(S["monotonic_noise_floor_deg"])
    checks, vnotes = [], list(det["notes"])
    valid = not invalid
    if invalid:
        vnotes.append("有効なシルエット輪郭を得られないフレームが %d 個：%s" % (len(invalid), invalid[:8]))
    if empty_frames:
        vnotes.append("静水面より上の対象領域が 0 px のフレームが %d 個（%s ...）：平坦な海、または横から見た開いたシートの可能性"
                      % (len(empty_frames), empty_frames[:8]))
    if step != 1:
        vnotes.append("フレーム間隔 %d：M5 と M6 は間引いたフレームで判定され、受入判定には使えない" % step)
    reached = [None if v is None else bool(v) for v in seq.get("reached_still_water", [None] * n)]
    not_reached = [int(f) for f, v in zip(fr_ok, reached) if v is False and f <= fN]
    if fN in not_reached:
        valid = False
        k_fin = fr_ok.index(fN)
        vnotes.append("最終フレーム %d で波の前面が静水面に届かない：波の前方輪郭の最下点は Z = %s H "
                      "（許容差は画像高さの %s %%）。h(t) は Z=0 から測るが、このモデルはその高さに達しない。"
                      % (fN, ct._fmt(seq["trough_level_H"][k_fin]), ct._fmt(pm.get_params()["trough_tol_pct_h"])))
    elif not_reached:
        vnotes.append("最終フレームより前の %d フレームで前面が静水面に届かない（%s ...）。有効性の失敗にはせず記録する。"
                      "幅の広いうねりが右側の画面外へ出た可能性がある。" % (len(not_reached), not_reached[:8]))

    def wf(i, **extra):
        if i is None:
            return None
        w = {"frame": int(fr[i]), "t_s": float(t_s[i])}
        w.update(extra)
        return w

    # ---- M1
    checks.append(ct.make_check("M1", "start_theta_max_deg", theta[0] if n else None, where=wf(0 if n else None),
                                note="開始フレームの前面で最大の傾斜角（2 %% 弦）。開始時の張り出し：%s" % (bool(seq["overhanging"][0]) if n else None)))
    # ---- M2 (rise: start .. first overhang frame)
    if i_A is not None and i_A >= 1:
        raw, k = _max_decrease(h, 0, i_A)
        checks.append(ct.make_check("M2", "h_monotonic_violation_H", _floor(raw, nf_h), raw=raw, where=wf(k),
                                    note="フレーム %d..%d の h のフレーム間最大減少量。%.1e H 以下の減少は雑音下限として 0 と判定（解釈値）" % (fr[0], fr[i_A], nf_h)))
        checks.append(ct.make_check("M2", "theta_start_deg", theta[0], where=wf(0)))
        checks.append(ct.make_check("M2", "theta_end_deg", theta[i_A - 1], where=wf(i_A - 1),
                                    note="張り出し直前のフレームの theta。張り出し開始フレームでは %.2f 度" % theta[i_A]))
        dth = np.abs(np.diff(theta[:i_A + 1]))
        kk = int(np.argmax(dth)) if dth.size else None
        checks.append(ct.report_value("M2", "theta_max_step_deg", None if kk is None else float(dth[kk]), "deg / frame",
                                      note="立ち上がり区間における theta の連続性（thresholds.json に数値しきい値はない）", where=wf(None if kk is None else kk + 1)))
    else:
        why = "立ち上がり区間なし：%s" % ("開始フレームから張り出している" if i_A == 0 else "張り出し区間を検出できない")
        for k in ("h_monotonic_violation_H", "theta_start_deg", "theta_end_deg"):
            checks.append(ct.make_check("M2", k, None, note=why))
        checks.append(ct.report_value("M2", "theta_max_step_deg", None, "deg / frame", note="報告専用：測定不能（%s）" % why))
    # ---- M3 (overhang: first overhang frame .. first curl-in frame)
    if i_A is not None and i_B is not None and i_B >= i_A:
        raw, k = _max_decrease(o, i_A, i_B)
        checks.append(ct.make_check("M3", "o_monotonic_violation_H", _floor(raw, nf_h), raw=raw, where=wf(k),
                                    note="フレーム %d..%d における o のフレーム間最大減少量%s" % (fr[i_A], fr[i_B], "" if raw is not None else
                                         "：張り出し区間が 2 フレーム未満のため、o の単調増加を測れない（NOT_MEASURABLE。合格ではない）")))
        hmin_i = int(i_A + np.argmin(h[i_A:i_B + 1]))
        drop = float((h[i_A] - h[hmin_i]) / h[i_A] * 100.0) if h[i_A] > 0 else None
        checks.append(ct.make_check("M3", "h_drop_pct", drop, where=wf(hmin_i), note="区間開始時の h は %.4f H、区間内の最小値は %.4f H" % (h[i_A], h[hmin_i])))
        adv = float(tip_x[i_B] - tip_x[i_A]) if np.isfinite(tip_x[i_A]) and np.isfinite(tip_x[i_B]) else None
        crosses = bool(o[i_B] > 0.0 and (adv is None or i_B == i_A or adv >= 0.0))
        checks.append(ct.make_check("M3", "tip_crosses_crest_plumb", crosses, where=wf(i_B),
                                    note="区間終端の o は %.4f H。頭部先端は区間中に +X 方向へ %s H 前進" % (o[i_B], ct._fmt(adv))))
        checks.append(ct.report_value("M3", "o_onset_jump_H", float(o[i_A] - (o[i_A - 1] if i_A > 0 else 0.0)), "H", where=wf(i_A),
                                      note="o(t) は張り出し開始時に定義上不連続になる（docs/measurement_definitions.md）。判定対象外"))
    else:
        for k in ("o_monotonic_violation_H", "h_drop_pct", "tip_crosses_crest_plumb"):
            checks.append(ct.make_check("M3", k, None, note="張り出し区間を検出できない"))
    # ---- M4 (curl-in: first curl-in frame .. stop frame)
    i_end = i_stop if i_stop is not None else i_final
    if i_B is not None and i_end is not None and i_end > i_B:
        p = phi[i_B:i_end + 1]
        raw, k = _max_decrease(-p, 0, len(p) - 1)
        checks.append(ct.make_check("M4", "phi_monotonic_violation_deg", _floor(raw, nf_deg), raw=raw, where=wf(None if k is None else i_B + k),
                                    note="フレーム %d..%d における phi のフレーム間最大上向き変化。phi は %.2f → %.2f 度、最終フレームでは %s 度"
                                         % (fr[i_B], fr[i_end], phi[i_B], phi[i_end], ct._fmt(float(phi[i_final]) if np.isfinite(phi[i_final]) else None))))
    else:
        checks.append(ct.make_check("M4", "phi_monotonic_violation_deg", None, note="巻き込み区間を検出できない"))
    # ---- M5 (stop)
    win_s = float(paths.threshold("M5", "decel_window_s", "spec"))
    checks.append(ct.make_check("M5", "decel_window_s", win_s, note="検査設定"))
    judged_disp = disp_adj.copy()
    vmax_i = int(np.nanargmax(judged_disp[:i_final + 1])) if np.isfinite(judged_disp[:i_final + 1]).any() else None
    vmax = None if vmax_i is None else float(judged_disp[vmax_i])
    if i_stop is not None and vmax:
        ratio = float(disp_adj[i_stop] / vmax)
        checks.append(ct.make_check("M5", "stop_speed_ratio", ratio, where=wf(i_stop),
                                    note="最後に動いたフレーム対の輪郭変位 %.5f H／全アニメーションの最大変位 %.5f H（フレーム %d）。指定最終フレームは %d、動作終了はフレーム %d"
                                         % (disp_adj[i_stop], vmax, fr[vmax_i], fN, fr[i_stop])))
        nwin = int(round(win_s * fps / step))
        a = max(1, i_stop - nwin + 1)
        wv = disp_adj[a:i_stop + 1] / vmax
        inc = np.diff(wv)
        checks.append(ct.report_value("M5", "decel_speed_at_window_start_ratio", float(wv[0]) if wv.size else None, "最大速度に対する比", where=wf(a),
                                      note="停止の %.2g 秒前における輪郭速度（『緩やかな減速』の数値しきい値は thresholds.json になく、利用者向けに報告）" % win_s))
        checks.append(ct.report_value("M5", "decel_max_speed_increase_ratio", float(max(0.0, np.nanmax(inc))) if inc.size else 0.0, "最大速度に対する比",
                                      note="対象窓内での輪郭速度のフレーム間最大増加量（0 なら単調減速）"))
        checks.append(ct.report_value("M5", "decel_is_monotonic", bool(inc.size == 0 or np.nanmax(inc) <= 1e-3), "bool",
                                      note="対象窓内で速度の増加が最大速度の 0.1 % を超えない"))
    else:
        checks.append(ct.make_check("M5", "stop_speed_ratio", None, note="動作を検出できない"))
        checks.append(ct.report_value("M5", "decel_is_monotonic", None, "bool", note="報告専用：動作を検出できず測定不能"))
    after = np.nonzero(fr > fN)[0]
    if after.size:
        dpost = disp_adj[after]
        raw = float(np.nanmax(dpost)) if np.isfinite(dpost).any() else None
        kk = int(after[int(np.nanargmax(dpost))]) if raw is not None else None
        checks.append(ct.make_check("M5", "post_stop_max_disp_H", _floor(raw, float(S["static_disp_eps_H"])), raw=raw, where=wf(kk),
                                    note="最終フレーム %d の後の保持 %d フレームにおける輪郭の最大変位" % (fN, after.size)))
    else:
        checks.append(ct.make_check("M5", "post_stop_max_disp_H", None,
                                    note="保持フレームを評価していない（--hold-frames 0）。『停止後に形状が変化しない』を測れず、NOT_MEASURABLE として失敗扱い"))
    # ---- 旧定義による保持区間の読み取り（報告専用）：10 秒保持、輪郭変位は画像高さの 0.2 % 以下
    hold_s = float(args.backlog_hold_s) if getattr(args, "backlog_hold_s", None) is not None else float(S["backlog_hold_s"])
    final_prof = next((p[1] for p in profiles if p[0] == fN), None)
    hold_info = measure_backlog_hold(ctx, rect, final_prof, fN, fps, hold_s, int(S["backlog_hold_step_frames"]), float(S["disp_z_min_H"]))
    ref_hold = float(S["backlog_hold_reference_pct_h"])
    if hold_info is not None and hold_info["worst"] is not None:
        wst = hold_info["worst"]
        checks.append(ct.report_value("M5", "backlog_hold_max_disp_pct_h", wst["max_disp_pct_h"], "% of image height",
                                      where={"frame": wst["frame"], "t_s": float((wst["frame"] - f0) / fps)}, target={"backlog_reference_le": ref_hold},
                                      label="報告専用・利用者の判断待ち",
                                      note="報告専用（旧定義：静止姿勢を %.3g 秒保持し、輪郭変位は画像高さの %.3g %% 以下）：最終フレーム %d に対する輪郭の最大変位。"
                                           "フレーム %d..%d を %d フレームごとに標本化（%d 標本%s）%s"
                                           % (hold_s, ref_hold, fN, fN + 1, fN + hold_info["n_hold_frames"], int(S["backlog_hold_step_frames"]), len(hold_info["rows"]),
                                              "" if not hold_info["n_errors"] else "、輪郭なし %d 件" % hold_info["n_errors"],
                                              "；これらは scene.frame_end = %d より後のフレームで、Blender がアニメーションを外挿する" % hold_info["scene_frame_end"]
                                              if hold_info["beyond_scene_frame_end"] else "")))
        checks.append(ct.report_value("M5", "backlog_hold_within_reference", bool(wst["max_disp_pct_h"] <= ref_hold and not hold_info["n_errors"]), "bool",
                                      note="報告専用：保持区間の変位が画像高さの %.3g %% 以下（旧定義表の参照値。thresholds.json のしきい値ではない）" % ref_hold))
    else:
        checks.append(ct.report_value("M5", "backlog_hold_max_disp_pct_h", None, "% of image height",
                                      note="報告専用：保持区間を評価できない（%s）" % ("--backlog-hold-s 0" if hold_s <= 0 else "最終フレームまたは保持フレームの輪郭がない")))
    # ---- M6 (no jumps)
    floor = float(S["jump_floor_frac_of_vmax"]) * (vmax or 0.0)
    ratio = np.full(n, np.nan)
    for i in range(1, i_final + 1):
        d = disp_adj[i]
        if not np.isfinite(d):
            continue
        nb = [disp_adj[j] for j in (i - 1, i + 1) if 1 <= j <= i_final and np.isfinite(disp_adj[j])]
        if not nb:
            continue
        ratio[i] = d / max(min(nb), floor) if max(min(nb), floor) > 0 else 0.0
    if np.isfinite(ratio).any():
        k = int(np.nanargmax(ratio))
        lim6 = paths.threshold("M6", "jump_ratio", "spec")
        bad = [int(v) for v in fr[np.nan_to_num(ratio, nan=0.0) >= lim6]]
        checks.append(ct.make_check("M6", "jump_ratio", float(ratio[k]), where=wf(k, frames=bad[:20] or None),
                                    note="d(%d→%d) = %.5f H。隣接値 %.5f／%.5f H、分母の下限 %.5f H（最大変位の %.0f %%）"
                                         % (fr[k - 1], fr[k], disp_adj[k], disp_adj[k - 1] if k >= 2 else float("nan"),
                                            disp_adj[k + 1] if k + 1 <= i_final else float("nan"), floor, 100 * float(S["jump_floor_frac_of_vmax"]))))
    else:
        checks.append(ct.make_check("M6", "jump_ratio", None, note="変位のあるフレームが 3 個未満"))
    # ---- 旧定義表の M6（報告専用）：d(k)／隣接値の中央値。停止への遷移は除外
    hw = max(1, int(S["m6_backlog_half_window"]))
    excl_s = float(S["m6_backlog_exclude_window_s"]) if S.get("m6_backlog_exclude_window_s") is not None else win_s
    n_excl = int(round(excl_s * fps / step))
    b_ratio, b_judged, b_med = backlog_jump_ratios(disp_adj, i_final, i_stop, hw, n_excl, float(S["static_disp_eps_H"]))
    ref6 = float(paths.threshold("M6", "jump_ratio", "spec"))
    if (np.isfinite(b_ratio) & b_judged).any():
        kb = int(np.nanargmax(np.where(b_judged, b_ratio, np.nan)))
        bad_b = [int(v) for v in fr[b_judged & (np.nan_to_num(b_ratio, nan=0.0) > ref6)]]
        in_excl = np.isfinite(b_ratio) & ~b_judged
        checks.append(ct.report_value("M6", "backlog_jump_ratio", float(b_ratio[kb]), "隣接フレーム対の変位中央値に対する倍率",
                                      where=wf(kb, frames=bad_b[:20] or None), target={"backlog_reference_le": ref6}, label="報告専用・利用者の判断待ち",
                                      note="報告専用（旧定義：停止への遷移を除き、隣接フレームの中央値の 3 倍以下）："
                                           "d(%d→%d) = %.5f H、前後 %d 対の中央値 = %.5f H。フレーム %d より後（停止フレーム %s の直前 %.3g 秒）は除外。"
                                           "除外窓内の最大比率：%s"
                                           % (fr[kb - 1], fr[kb], disp_adj[kb], hw, b_med[kb], fr[max(0, (i_stop if i_stop is not None else i_final) - n_excl)], frame_of(i_stop), excl_s,
                                              ct._fmt(float(np.nanmax(b_ratio[in_excl])) if in_excl.any() else None))))
        checks.append(ct.report_value("M6", "backlog_within_reference", bool(b_ratio[kb] <= ref6), "bool",
                                      note="報告専用：backlog_jump_ratio <= %g（旧定義表の係数 3 は thresholds.json の M6.jump_ratio と同じ値。判定対象外）" % ref6))
    else:
        checks.append(ct.report_value("M6", "backlog_jump_ratio", None, "隣接フレーム対の変位中央値に対する倍率",
                                      note="報告専用：停止前の減速窓の外側にあるフレーム対が少なすぎる"))

    # ---- T：有効性条件の根拠となる件数（常に報告）
    rec_u, note_u = ct.untested_objects_report(ctx)
    checks.append(rec_u)
    if note_u:
        vnotes.append(note_u)
    checks.append(ct.report_value("T", "n_frames_nonfinite_geometry", len(nonfinite_frames), "frames", where=None if not nonfinite_frames else {"frames": nonfinite_frames[:20]},
                                  note="有限でない頂点または除外された三角形のある評価フレーム数。0 超なら INVALID"))
    checks.append(ct.report_value("T", "n_frames_with_islands", len(island_frames), "frames", where=None if not island_frames else {"frames": island_frames[:20]},
                                  note="微小領域の上限を超えるシルエット成分を除外した評価フレーム数。0 超なら INVALID"))
    checks.append(ct.report_value("T", "n_frames_not_reaching_still_water", len(not_reached), "frames", where=None if not not_reached else {"frames": not_reached[:20]},
                                  note="前面が静水面に達しない最終フレーム以前のフレーム数。最終フレームなら INVALID、その他は報告のみ"))

    # ---- phase summary (spec 6.5: report the split against the backlog 4 / 3 / 2.5 s)
    def dur(i0, i1):
        return None if (i0 is None or i1 is None) else float((fr[i1] - fr[i0]) / fps)

    phases = {"source": phase_source,
              "rise": {"frames": [frame_of(0), frame_of(i_A)], "seconds": dur(0, i_A)},
              "overhang": {"frames": [frame_of(i_A), frame_of(i_B)], "seconds": dur(i_A, i_B)},
              "curl_in": {"frames": [frame_of(i_B), frame_of(i_end)], "seconds": dur(i_B, i_end)},
              "stop_frame": frame_of(i_stop), "declared_final_frame": fN,
              "detected": {"first_overhang_frame": frame_of(det["i_A"]), "first_curl_in_frame": frame_of(det["i_B"]), "stop_frame": frame_of(det["i_stop"])},
              "given": given, "backlog_seconds": paths.param("backlog_phase_seconds"), "fps": fps}
    tot = dur(0, i_end)
    if tot and all(phases[k]["seconds"] is not None for k in ("rise", "overhang", "curl_in")):
        phases["fractions"] = {k: phases[k]["seconds"] / tot for k in ("rise", "overhang", "curl_in")}
        bl = [float(v) for v in paths.param("backlog_phase_seconds")]
        phases["backlog_fractions"] = {k: v / sum(bl) for k, v in zip(("rise", "overhang", "curl_in"), bl)}

    series = {"frame": fr.tolist(), "t_s": t_s.tolist(), "h": h.tolist(), "x_c": x_c.tolist(), "theta": theta.tolist(),
              "theta_raw": seq["theta_raw"], "o": o.tolist(), "cavity_depth": cav.tolist(), "phi_deg": seq["phi_deg"],
              "overhanging": [bool(v) for v in seq["overhanging"]], "disp_max_H": [None if not np.isfinite(v) else float(v) for v in disp_adj],
              "disp_p95_H": seq["disp_p95_H"], "jump_ratio": [None if not np.isfinite(v) else float(v) for v in ratio],
              "backlog_jump_ratio": [None if not np.isfinite(v) else float(v) for v in b_ratio],
              "backlog_jump_ratio_judged": [bool(v) for v in b_judged],
              "crest_to_tip_deg": seq["crest_to_tip_deg"],
              "crest_H": seq["crest_H"], "tip_H": seq["tip_H"], "deepest_H": seq["deepest_H"]}
    outputs = save_images(ctx, run_dir, series, phases, thumbs, (i_A, i_B, i_end, i_final), vmax, floor, fps, args)
    t_img = sw.lap()
    audit = ctx.audit(effective={"motion_res_scale": (scale, "--res-scale" if getattr(args, "res_scale", None) else None),
                                 "hold_frames": (configured_hold, "--hold-frames" if getattr(args, "hold_frames", None) is not None else None),
                                 "motion_frame_step": (step, "--frame-step" if getattr(args, "frame_step", None) else None)})
    result = {"schema": ct.RESULT_SCHEMA, "test": TEST_NAME, "run_dir": run_dir, "context": ctx.describe(),
              "mask": {"resolution": [rect.width_px, rect.height_px], "scale": scale, "exact": True},
              "frames": {"first": f0, "final": fN, "step": step, "hold": hold, "n_evaluated": n, "invalid": invalid, "per_frame": per_frame_info,
                         "nonfinite_geometry": nonfinite_frames, "with_islands": island_frames, "not_reaching_still_water": not_reached},
              "summary": ct.summarize(checks, valid, vnotes, expected=ct.EXPECTED_IDS[TEST_NAME], audit=audit), "checks": checks, "phases": phases,
              "settings_audit": audit,
              "backlog_variants": {"label": "報告専用・利用者の判断待ち", "hold": hold_info,
                                   "M6_backlog": {"half_window_pairs": hw, "exclude_window_s": excl_s, "n_excluded_pairs_before_stop": n_excl,
                                                  "reference_factor": ref6}},
              "interpretation_notes": {k: ct.INTERPRETATION_NOTES[k] for k in ("tiers", "verdicts", "validity", "phases", "segmentation", "M2", "M3", "M4", "M5", "M6", "M6_backlog", "hold_backlog")},
              "series": dict(series, trough_level_H=seq.get("trough_level_H"), reached_still_water=reached), "outputs": outputs, "seconds": {"profiles": t_prof, "metrics": t_meas, "images": t_img}}
    ct.write_result(run_dir, result)
    ct.log_checks(checks, "test_motion frames %d..%d (+%d hold), phases %s: overhang from %s, curl-in from %s, stop %s"
                  % (f0, fN, hold, phase_source, frame_of(i_A), frame_of(i_B), frame_of(i_stop)))
    for nn in vnotes:
        log("[motion] note: " + nn)
    return result


# ------------------------------------------------------------------------------------ images
def _spans(series, idx):
    i_A, i_B, i_end, _ = idx
    fr = series["frame"]
    sp = []
    if i_A is not None:
        sp.append({"x0": fr[0], "x1": fr[i_A], "label": "rise", "color": "green", "alpha": 0.10})
        if i_B is not None:
            sp.append({"x0": fr[i_A], "x1": fr[i_B], "label": "overhang", "color": "orange", "alpha": 0.12})
            if i_end is not None:
                sp.append({"x0": fr[i_B], "x1": fr[i_end], "label": "curl-in", "color": "purple", "alpha": 0.10})
    return sp


HOUDINI_KEYS = {"h": "h_H", "x_c": "x_c_H", "theta": "theta_deg", "o": "o_H", "phi_deg": "phi_deg", "cavity_depth": "cavity_depth_H"}


def load_houdini(path):
    """target/houdini_motion.json（gw.houdini_motion.v1 形式）の読み取り器。
    per_frame.{full, section} は frame、tau、h_H、x_c_H、theta_deg、o_H、phi_deg、cavity_depth_H などの記録列。
    full は CAM_print と同じ側面シルエット、section は一つの平面断面。
    曲線配列、tau 配列、情報を返す。参照曲線を読めない場合は ValueError を送出し、
    参照値のない比較図を黙って生成しない。"""
    d = paths.read_json(path)
    if d.get("schema") != "gw.houdini_motion.v1":
        raise ValueError("想定外の schema %r（対応形式は 'gw.houdini_motion.v1'）" % d.get("schema"))
    curves, taus, missing, n_masked = {}, {}, [], {}
    for mode in ("full", "section"):
        recs = (d.get("per_frame") or {}).get(mode)
        if not recs:
            continue
        curves[mode] = {}
        taus[mode] = np.array([r["tau"] for r in recs], dtype=np.float64)
        small = np.array(["h_too_small" in (r.get("flags") or []) for r in recs], dtype=bool)
        for name, key in HOUDINI_KEYS.items():
            if all(key in r for r in recs):
                v = np.array([np.nan if r[key] is None else r[key] for r in recs], dtype=np.float64)
                if name in ("x_c", "theta"):
                    v = np.where(small, np.nan, v)      # 参照データでは、このフレームの波頂位置・theta は細波の雑音として印が付く
                curves[mode][name] = v
            else:
                missing.append("%s.%s" % (mode, key))
        n_masked[mode] = int(small.sum())
    n_curves = sum(len(v) for v in curves.values())
    if n_curves == 0:
        raise ValueError("no per-frame curve could be read from %s" % path)
    meta = d.get("meta", {})
    info = {"n_curves": n_curves, "missing_keys": missing, "n_frames_masked_h_too_small": n_masked, "n_frames": {m: int(len(t)) for m, t in taus.items()},
            "time_base": meta.get("time_base"), "H_ref_m": meta.get("H_ref_m"), "fps": (d.get("source") or {}).get("fps"),
            "phases": d.get("phases"), "reference_final_over_max_speed_ratio": {m: (d.get("deceleration") or {}).get(m, {}).get("final_over_max_ratio") for m in taus}}
    return curves, taus, info


def save_images(ctx, run_dir, series, phases, thumbs, idx, vmax, floor, fps, args):
    out = {}
    fr = np.asarray(series["frame"], dtype=np.float64)
    sp = _spans(series, idx)
    nan = lambda a: np.array([np.nan if v is None else v for v in a], dtype=np.float64)  # noqa: E731
    vl = [{"x": ctx.final_frame, "label": "final", "color": "darkgray"}]
    if phases.get("stop_frame") is not None and phases["stop_frame"] != ctx.final_frame:
        vl.append({"x": phases["stop_frame"], "label": "stop", "color": "red"})
    size = (1500, 330)
    plots = [
        {"series": [{"label": "h", "x": fr, "y": series["h"], "color": "blue"}], "title": "h(t): crest height above still water", "ylabel": "H"},
        {"series": [{"label": "x_c", "x": fr, "y": series["x_c"], "color": "blue"}], "title": "x_c(t): crest X", "ylabel": "H"},
        {"series": [{"label": "theta", "x": fr, "y": series["theta"], "color": "blue"}], "title": "theta(t): steepest front-face inclination (90 = vertical, > 90 = overhanging)", "ylabel": "deg",
         "hlines": [{"y": 30.0, "label": "30"}, {"y": 80.0, "label": "80"}]},
        {"series": [{"label": "o", "x": fr, "y": series["o"], "color": "blue"},
                    {"label": "cavity depth", "x": fr, "y": series["cavity_depth"], "color": "gray", "dash": (6, 4)}],
         "title": "o(t): overhang of the head tip beyond the crest plumb line (jumps at the onset by definition)", "ylabel": "H"},
        {"series": [{"label": "phi", "x": fr, "y": nan(series["phi_deg"]), "color": "blue"}], "title": "phi(t): direction of the head tip (negative = downward)", "ylabel": "deg"},
    ]
    for p in plots:
        p.update({"size": size, "spans": sp, "vlines": vl, "xlabel": "frame", "xlim": (fr[0], fr[-1] + 0.08 * (fr[-1] - fr[0]))})
    ttl = "motion curves: %s  (phases %s; %.3g fps)" % (",".join(o.name for o in ctx.objs), phases["source"], fps)
    out["plot_motion_curves"] = imgio.save_png(os.path.join(run_dir, "plot_motion_curves.png"), plot.multi_plot(plots, title=ttl))

    d = nan(series["disp_max_H"])
    lim5 = paths.threshold("M5", "stop_speed_ratio", "spec")
    lim6 = paths.threshold("M6", "jump_ratio", "spec")
    p2 = [{"series": [{"label": "max contour displacement", "x": fr, "y": d, "color": "blue", "marker": "o", "marker_size": 2}],
           "title": "contour speed: largest displacement to the previous frame (M5)", "ylabel": "H / frame",
           "hlines": ([{"y": lim5 * vmax, "label": "%.0f %% of max" % (100 * lim5), "color": "red"}, {"y": floor, "label": "M6 floor", "color": "gray"}] if vmax else [])},
          {"series": [{"label": "jump ratio", "x": fr, "y": nan(series["jump_ratio"]), "color": "purple", "marker": "o", "marker_size": 2}],
           "title": "M6 jump ratio (JUDGED, spec reading): d(k) / max(min(d(k-1), d(k+1)), floor)", "ylabel": "ratio",
           "hlines": [{"y": lim6, "label": "limit %g" % lim6, "color": "red"}]}]
    if series.get("backlog_jump_ratio") is not None:
        rb = np.minimum(nan(series["backlog_jump_ratio"]), 10.0 * lim6)      # plot only: clipped at 10 x the reference
        jb = np.asarray(series["backlog_jump_ratio_judged"], dtype=bool)
        p2.append({"series": [{"label": "used", "x": fr, "y": np.where(jb, rb, np.nan), "color": "brown", "marker": "o", "marker_size": 2},
                              {"label": "excluded (ease-to-stop window / after the stop)", "x": fr, "y": np.where(jb, np.nan, rb), "color": "gray", "marker": "x", "marker_size": 3, "line": False}],
                   "title": "M6_backlog (REPORT ONLY): d(k) / median(neighbour pairs), stop excluded", "ylabel": "ratio",
                   "hlines": [{"y": lim6, "label": "reference %g" % lim6, "color": "red"}]})
    for p in p2:
        p.update({"size": size, "spans": sp, "vlines": vl, "xlabel": "frame", "xlim": (fr[0], fr[-1] + 0.08 * (fr[-1] - fr[0]))})
    out["plot_speed_jump"] = imgio.save_png(os.path.join(run_dir, "plot_speed_jump.png"), plot.multi_plot(p2, title="M5 / M6"))

    if thumbs:
        labels = ["f%d h=%.2f th=%.0f o=%.2f phi=%s" % (f, m["h"], m["theta"], m["o"], "n/a" if m["phi_deg"] is None else "%.0f" % m["phi_deg"])
                  for f, _im, m in thumbs]
        sheet = draw.grid([im for _f, im, _m in thumbs], ncols=4, gap=8, labels=labels, label_scale=2)
        out["contact_sheet"] = imgio.save_png(os.path.join(run_dir, "contact_sheet.png"), sheet)

    hj = ct.resolve_path(args.houdini_json) if getattr(args, "houdini_json", None) else (HOUDINI_JSON if os.path.isfile(HOUDINI_JSON) else None)
    out["houdini_json"] = None if not hj else paths.norm(hj)
    if hj and os.path.isfile(hj):
        try:
            ref, tau, hinfo = load_houdini(hj)
            i_end = idx[2] if idx[2] is not None else idx[3]
            t_mod = (fr - fr[0]) / max(1e-9, (fr[i_end] - fr[0]))
            pl = []
            for key, ttl2, unit in (("h", "h", "H"), ("x_c", "x_c", "H"), ("theta", "theta", "deg"), ("o", "o", "H"),
                                    ("cavity_depth", "cavity depth", "H"), ("phi_deg", "phi", "deg")):
                ser = [{"label": "this model", "x": t_mod, "y": nan(series[key]), "color": "blue"}]
                for mode, col, dash in (("full", "red", None), ("section", "orange", (6, 4))):
                    if key in ref.get(mode, {}):
                        ser.append({"label": "Houdini %s (%d fr)" % (mode, len(tau[mode])), "x": tau[mode], "y": ref[mode][key], "color": col, "dash": dash})
                pl.append({"series": ser, "title": ttl2 + "(t)", "ylabel": unit, "size": size, "xlim": (0.0, 1.05),
                           "xlabel": "normalised time"})
            note = ("Time axis: model 0..1 = first frame .. motion ends; Houdini tau 0..1 = frame 1 .. LAST frame of the cache. NOT the same '1': "
                    "the Houdini cache ends while the wave is still moving (last / max contour speed = %s) and has no curl-in phase; its tau = 1 is the "
                    "end of the data, not a stop. x_c and theta of reference frames flagged 'h_too_small' are not drawn (%s frames)."
                    % (ct._fmt((hinfo["reference_final_over_max_speed_ratio"] or {}).get("full")), hinfo["n_frames_masked_h_too_small"]))
            fig = plot.multi_plot(pl, title="spec 6.4: model vs Houdini reference (no threshold; for the user's eyes)")
            per_line = max(40, int((fig.shape[1] - 12) / 12))
            words, lines, cur = note.split(" "), [], ""
            for wd in words:
                if len(cur) + len(wd) + 1 > per_line:
                    lines.append(cur)
                    cur = wd
                else:
                    cur = (cur + " " + wd).strip()
            lines.append(cur)
            cap = draw.canvas(24 * len(lines) + 8, fig.shape[1], "white")
            for k, ln in enumerate(lines):
                draw.text(cap, 6, 4 + 24 * k, ln, "red", 2)
            out["plot_vs_houdini"] = imgio.save_png(os.path.join(run_dir, "plot_vs_houdini.png"), draw.vstack([fig, cap], gap=0))
            out["houdini_compare"] = dict(hinfo, time_axis_note=note)
            log("[motion] Houdini comparison: %d reference curves read (%s)" % (hinfo["n_curves"], hinfo["n_frames"]))
            if hinfo["missing_keys"]:
                log("[motion] Houdini comparison: keys missing in the reference: %s" % hinfo["missing_keys"])
        except Exception as exc:                                  # the comparison is optional: never fail the test because of it,
            out["houdini_compare_error"] = "%s: %s" % (type(exc).__name__, exc)   # but say loudly that there is NO figure
            log("[motion] Houdini comparison NOT produced: %s" % out["houdini_compare_error"])
    return out


def main():
    ap = argparse.ArgumentParser(description="great_wave motion test M1-M6 (all frames)")
    ct.add_common_args(ap)
    add_args(ap)
    args = bootstrap.parse_args(ap)

    def body(run_dir):
        ctx = ct.setup_context(args, TEST_NAME, run_dir=run_dir)
        result = run(ctx)
        log("[motion] results: %s" % result["run_dir"])
        return result

    ct.guarded_main(TEST_NAME, args, body)


if __name__ == "__main__":
    main()
