# -*- coding: utf-8 -*-
"""FLIP39 E：1 本の計算の解析（py -3.10、numpy）。流体の計算はしない。
使い方: py -3.10 e_analyze.py <run_dir> [--no-break]

読むもの：hf_c*.npz（一番上の水面 η(z, x)、毎コマ）、comp_c0001.json（成分の表）、run.json、sec/z*/snap_*.npz（断面の粒子）。
測るもの（定義は record_ja.md と同じ）：
- 線形の見込み（同じ成分の和を、その場の水深で位相を積み、線形の浅水係数をかけた水面）と、計算の水面の比べ（水面計）。
- 頂の歩み：焦点の列（3D は z = −Lz/2 の壁、板は全幅の平均）の、造波の帯の外（x ≥ xg_end + 10 m）で最も高い水面。
- m1 集中の比 = 砕ける時（前の面が垂直を過ぎる前まで）の最も高い頂 ÷ 造波の帯を出た所（x = xg_end + 10〜40 m）の水面の、全時刻の最も高い値。
  途中から始めた版は、分母を「初めに置いた場の最も高い頂」と比べて大きい方にする（控えめに出す）。
- 立ち上がり：水槽の中で最も高い頂が、最終の 0.5・0.7・0.9 倍を初めて越えた時刻と、最終の時刻との差。
- 崩れ方：FLIP37 P1 の p1_analyze（B > 0.85、前の面が垂直を過ぎた、空洞が閉じた）を焦点の列の断面で使う。
"""
import sys, os, json, glob
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip37")
from e_lin import Bed, kdisp, kshoal, theta_x


def load_hf(rd):
    fs = sorted(glob.glob(os.path.join(rd, "hf_c*.npz")))
    E, S, F, T = [], [], [], []
    grid = None
    for f in fs:
        d = np.load(f, allow_pickle=True)
        E.append(d["eta"]); S.append(d["seg"]); F.append(d["frames"]); T.append(d["t"])
        grid = json.loads(str(d["grid"]))
    F = np.concatenate(F); E = np.concatenate(E); S = np.concatenate(S); T = np.concatenate(T)
    # 区切りの重なり（続きの計算の最初のコマ）は後の方を使う
    _, idx = np.unique(F[::-1], return_index=True)
    keep = np.sort(len(F) - 1 - idx)
    return dict(eta=E[keep].astype(np.float32), seg=S[keep], frames=F[keep], t=T[keep], grid=grid)


def run_info(rd):
    rj = json.load(open(os.path.join(rd, "run.json"), encoding="utf8"))
    cj = json.load(open(os.path.join(rd, "comp_c0001.json"), encoding="utf8"))
    return rj, cj


def bed_of(rj, cj):
    P = rj["parms"]
    mound = None
    if float(P.get("lg1_d", 0.0)) > 0 and abs(float(P.get("lg1_z", 0.0)) + 0.5 * float(P["Lz"])) < 1.0:
        mound = (float(P["lg1_x"]), float(P["lg1_sx"]), float(P["lg1_d"]))   # 焦点の列（壁の上）を通る盛り上がり
    return Bed(h0=float(P["h0"]), hr=float(P["hr"]), slope_n=float(P["slope_n"]), xs0=float(P["xs0"]), flat=bool(rj.get("flat", False)), mound=mound)


def linear_eta(cj, bed, x, t_group, z=None):
    """線形の見込み η(t, x)。t_group は群の時刻。"""
    x = np.asarray(x, float); t_group = np.asarray(t_group, float)
    out = np.zeros((len(t_group), len(x)))
    g = cj["group"]; xf = float(g["xf"]); tf = float(g["tf"])
    for a, om, kz in zip(cj["a"], cj["om"], cj["kz"]):
        th = theta_x(bed, x, om, kz) - theta_x(bed, np.array([xf]), om, kz)[0]
        amp = a * kshoal(om, bed.h(x)) / kshoal(om, bed.h0)
        zz = 1.0 if z is None else np.cos(kz * (z - cj["zf"]))
        out += zz * amp[None, :] * np.cos(th[None, :] - om * (t_group[:, None] - tf))
    return out


ROW_Z = None   # --row=<z>：焦点の列の代わりに、この z の列を解析する（E3 で頂が焦点の列の外に出たため）


def focus_row(hf, rj):
    Lz = float(rj["parms"]["Lz"])
    if Lz <= 20:   # 板：全幅の平均（z に一様）
        return np.nanmean(hf["eta"], axis=1)
    if ROW_Z is not None:
        iz = int(round((ROW_Z - hf["grid"]["z0"]) / hf["grid"]["dz"]))
        return np.nanmax(hf["eta"][:, max(iz - 1, 0):iz + 2, :], axis=1)
    return np.nanmax(hf["eta"][:, 0:2, :], axis=1)   # z = −Lz/2 の壁（対称の面）とその隣の列（−118 m）の高い方（壁の上の値は境界で乱れることがあるため）


def analyze(rd, do_break=True):
    rj, cj = run_info(rd)
    P = rj["parms"]
    hf = load_hf(rd)
    g = hf["grid"]; dx = g["dx"]
    x = g["x0"] + dx * np.arange(hf["eta"].shape[2])
    t = hf["t"]; toff = float(P.get("t_off", 0.0)); tg = t + toff
    bed = bed_of(rj, cj)
    xg_end = float(P["xg_end"])
    row = focus_row(hf, rj)                     # (nt, nx)
    lvl0 = float(np.nanmean(row[0, (x > xg_end + 20) & (x < 400)])) if toff == 0 else 0.0
    # 静かな水面のずれ（粒子から水面を作る時のずれ。P0 §3.3・P2 §2.2 と同じ 0.4 m 前後）を、最初の 1 秒の後の静かな所で測って差し引く
    res = {"run_id": os.path.basename(rd.rstrip("/\\")), "t_off": toff, "group": cj["group"], "flat": rj.get("flat", False),
           "n_components": len(cj["a"]), "stopped": rj.get("stopped"), "wall_total_s": rj.get("wall_total_s"),
           "wall_per_frame_median_s": rj.get("wall_per_frame_median_s"), "frames": int(len(t)), "t_end": float(t[-1])}
    # 水面のずれ：板・3D とも、群が来る前の沖（x 450〜700 m、t 1〜3 s）の平均
    sel_t = (t > 1.0) & (t < 3.0)
    off = float(np.nanmean(row[sel_t][:, (x > 450) & (x < 700)])) if sel_t.any() else 0.0
    if toff > 0:
        # 途中から始めた版は初めから波があるので、静かな水で測ったずれを使う：板は S0（0.43 m）、3D は FLIP37 P2 の 0.44〜0.48 m の中ほど 0.46 m
        off = 0.43 if float(P["Lz"]) <= 20 else 0.46
    res["level_offset_m"] = off
    eta = row - off
    # 水面計（線形の見込みとの比べ）
    gauges = {}
    for xg in (160.0, 200.0, 300.0, 400.0, 480.0, 520.0, 540.0, 556.0, 580.0):
        ig = int(np.argmin(np.abs(x - xg)))
        lin = linear_eta(cj, bed, [x[ig]], tg)[:, 0]
        m = eta[:, ig]
        ok = np.isfinite(m)
        late = ok & (tg > float(cj["group"]["tf"]) - 40) & (tg < float(cj["group"]["tf"]) - 2)
        gauges["%d" % xg] = {"x": float(x[ig]), "max_sim": float(np.nanmax(m)), "max_lin": float(lin.max()),
                             "t_max_sim": float(tg[np.nanargmax(m)]), "t_max_lin": float(tg[np.argmax(lin)]),
                             "rms_ratio_window": float(np.sqrt(np.nanmean(m[late] ** 2)) / max(np.sqrt(np.mean(lin[late] ** 2)), 1e-9)) if late.any() else None,
                             "corr_window": float(np.corrcoef(m[late], lin[late])[0, 1]) if late.sum() > 10 else None}
    res["gauges"] = gauges
    # 頂の歩み
    dom = (x >= xg_end + 10) & (x <= float(P["xa0"]))
    cmax = np.nanmax(np.where(dom[None, :], eta, -np.inf), axis=1)
    cx = x[np.nanargmax(np.where(dom[None, :], eta, -np.inf), axis=1)]
    lin_dom = linear_eta(cj, bed, x[dom], tg)
    res["crest_history"] = {"t_group": tg[::6].round(3).tolist(), "crest_sim": cmax[::6].round(3).tolist(), "x_sim": cx[::6].round(1).tolist(),
                            "crest_lin": lin_dom.max(axis=1)[::6].round(3).tolist()}
    kmax = int(np.nanargmax(cmax))
    cmax_t = tg[kmax]
    res["crest_max_any"] = {"t_group": float(tg[kmax]), "x": float(cx[kmax]), "crest_m": float(cmax[kmax])}
    res["linear_focus"] = {"crest_m": float(lin_dom.max()), "t_group": float(tg[np.unravel_index(np.argmax(lin_dom), lin_dom.shape)[0]]),
                           "x": float(x[dom][np.unravel_index(np.argmax(lin_dom), lin_dom.shape)[1]])}
    # 造波の帯を出た所の最も高い水面（m1 の分母）
    exitm = (x >= xg_end + 10) & (x <= xg_end + 40)
    den_exit = float(np.nanmax(eta[:, exitm]))
    den_init = float(np.nanmax(eta[0, dom])) if toff > 0 else 0.0
    # 壁ぎわの揺れ
    wall = (x <= 20)
    res["wall_slosh_max_abs_m"] = float(np.nanmax(np.abs(eta[:, wall])))
    res["m1_den"] = {"exit_gauge_max_m": den_exit, "initial_field_max_m": den_init, "used_m": max(den_exit, den_init)}
    # 崩れ方（p1_analyze）
    brk = None
    sd = sorted(glob.glob(os.path.join(rd, "sec", "z*")))
    if do_break and sd:
        import p1_analyze as PA
        if ROW_Z is not None and len(sd) > 1:
            sdir = min(sd, key=lambda q: abs(int(os.path.basename(q)[1:]) - ROW_Z))
        else:
            sdir = sd[0] if len(sd) == 1 else [s for s in sd if s.endswith("z-118") or s.endswith("z-119") or s.endswith("z-120")][0]
        # p1_analyze が読む run.json（parms に xs0 等）。平らな海は xs0 が大きい
        rjs = json.load(open(os.path.join(sdir, "run.json"), encoding="utf8"))
        rjs["parms"]["h0"] = float(P["h0"]); rjs["parms"]["xs0"] = float(P["xs0"]); rjs["parms"]["slope_n"] = float(P["slope_n"]); rjs["parms"]["hr"] = float(P["hr"])
        json.dump(rjs, open(os.path.join(sdir, "run.json"), "w", encoding="utf8"), ensure_ascii=False, default=str)
        if glob.glob(os.path.join(sdir, "snap_*.npz")):
            # 断面の頂の追いかけは、水面の最も高い頂の 6 秒前の断面から始める（大きな振幅では、群の前の方にも高い波があり、
            # 最初の断面の最も高い所から追うと別の波を追うことがあった：E1_reef_S060）
            f_from = int(round((float(cmax_t) - toff - 6.0) * 24)) + 1
            _orig = PA.load_snaps
            PA.load_snaps = lambda d_, _o=_orig, _f=f_from: [q for q in _o(d_) if int(os.path.basename(q)[5:9]) >= _f]
            a = PA.analyze(sdir, quiet=True)
            PA.load_snaps = _orig
            brk_from_frame = f_from
            ev = a["events"]
            brk = {"plunging": a["plunging"], "events": ev, "section_dir": sdir}
            # 時刻を群の時刻へ
            for k in ("breaking_onset_B085", "face_past_vertical", "tube_closed_or_nearly"):
                if ev.get(k):
                    ev[k]["t_group"] = ev[k]["t"] + toff
            # 形の値：前の面が垂直を過ぎた時刻の前後のコマ（m3）
            tl = a["timeline"]
            if ev.get("face_past_vertical"):
                tov = ev["face_past_vertical"]["t"]
                q = min(tl, key=lambda q: abs(q["t"] - tov))
                brk["shape_at_overturn"] = {k: q.get(k) for k in ("crest", "front_face_chord_angle_deg", "front_face_sag_m", "back_dx_to_075Hc_m",
                                                                   "reach_over_Hc", "drop_over_Hc", "overhang_over_Hc", "tube_aspect_w_over_h",
                                                                   "trough_front_y", "x_front_half") if k in q}
                q2 = [q for q in tl if q["t"] >= tov and q["t"] <= tov + 1.2 and q.get("overturned")]
                if q2:
                    q3 = q2[-1]
                    brk["shape_overturn_plus_1s"] = {k: q3.get(k) for k in ("t", "crest", "front_face_chord_angle_deg", "reach_over_Hc", "drop_over_Hc",
                                                                          "overhang_over_Hc", "tube_aspect_w_over_h", "closed_air_area_m2", "back_dx_to_075Hc_m")}
            # 噴流の向き（上向きか前向きか）：垂直を過ぎた後 0.5 秒の唇の先の粒子の速さの向き
            brk["timeline_t"] = [q["t"] + toff for q in tl]
            brk["timeline_crest_y"] = [q["crest"][1] for q in tl]
            brk["timeline_B"] = [q.get("B") for q in tl]
    res["breaking"] = brk
    # 砕ける時の頂（m1 の分子）：前の面が垂直を過ぎるまでの最も高い頂（断面の解析）。なければ水面の最も高い頂
    if brk and brk["events"].get("crest_max_before_overturn_m") is not None and brk["events"].get("face_past_vertical"):
        num = float(brk["events"]["crest_max_before_overturn_m"]) - off
        res["m1_num_def"] = "前の面が垂直を過ぎるまでの断面の最も高い頂（水面のずれを引いた）"
    else:
        num = float(cmax[kmax])
        res["m1_num_def"] = "砕けない・垂直を過ぎない：計算の間の水面の最も高い頂"
    res["m1"] = num / max(den_exit, den_init, 1e-6)
    res["m1_num_m"] = num
    # 立ち上がり（水面の最も高い頂の歩み。最終＝m1 の分子）
    rise = {}
    for r in (0.5, 0.7, 0.9):
        i = np.where(cmax >= r * num)[0]
        rise["%.1f" % r] = float(tg[i[0]]) if i.size else None
    tfin = (brk["events"]["face_past_vertical"]["t_group"] if (brk and brk["events"].get("face_past_vertical")) else float(tg[kmax]))
    res["rise"] = {"t_reach": rise, "t_final": tfin, "s_from_0.5": (tfin - rise["0.5"]) if rise["0.5"] else None,
                   "s_from_0.7": (tfin - rise["0.7"]) if rise["0.7"] else None}
    res["row_z"] = ROW_Z
    nm = "analysis_e.json" if ROW_Z is None or "--main" in sys.argv else "analysis_e_z%+04d.json" % int(ROW_Z)
    json.dump(res, open(os.path.join(rd, nm), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    return res


if __name__ == "__main__":
    for a in sys.argv:
        if a.startswith("--row="):
            ROW_Z = float(a.split("=")[1])
    r = analyze(sys.argv[1], do_break="--no-break" not in sys.argv)
    s = {k: r[k] for k in ("run_id", "stopped", "level_offset_m", "crest_max_any", "linear_focus", "m1_den", "m1", "m1_num_m", "rise", "wall_slosh_max_abs_m")}
    print(json.dumps(s, ensure_ascii=False, indent=1, default=float))
    for k, v in r["gauges"].items():
        print(k, {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items()})
    if r["breaking"]:
        print(json.dumps({k: r["breaking"][k] for k in r["breaking"] if not k.startswith("timeline")}, ensure_ascii=False, default=float, indent=1)[:3000])
