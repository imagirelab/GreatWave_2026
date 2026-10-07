# -*- coding: utf-8 -*-
"""FLIP39 R：主役の範囲の細かい計算の解析（py -3.10、numpy）。流体の計算はしない。
使い方: py -3.10 r_analyze.py <箱の run_dir> [--main=-80]
- 崩れ方：FLIP37 P1 の p1_analyze（B > 0.85、前の面が垂直を過ぎた、空洞が閉じた）を断面ごとに（sec/z*）。
- 頂の歩み：断面の列（z ±0.9 m）の一番上の水面の最も高い所（箱の内側）。
- m1：崩れる時（前の面が垂直を過ぎるまで）の断面の最も高い頂 ÷ E3 の造波の帯を出た所の最も高い水面（7.98 m。同じ入口の波）。
水面のずれ：r_seat.Merged と同じ推定（0.46 m ＋ 始めの 0.5 秒の「箱 − E3」の平均の差）を引く。断面の粒子の y も同じずれを引いて読む。
"""
import sys, os, json, glob
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip37")
from r_seat import Merged, TOFF
import p1_analyze as PA

E3 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/E/E3_dir20_lens"


def main(rd, zmain=-80.0):
    M = Merged(rd)
    off = M.off_box
    an3 = json.load(open(os.path.join(E3, "analysis_e_z-080.json"), encoding="utf8"))
    den = float(an3["m1_den"]["used_m"])
    res = {"run_id": os.path.basename(rd.rstrip("/\\")), "off_box_m": off, "m1_den_m": den, "rows": {}}
    B = M.B
    for sdir in sorted(glob.glob(os.path.join(rd, "sec", "z*"))):
        zr = int(os.path.basename(sdir)[1:])
        rj = json.load(open(os.path.join(sdir, "run.json"), encoding="utf8"))
        rj["parms"]["xc0"] = 330.0
        json.dump(rj, open(os.path.join(sdir, "run.json"), "w", encoding="utf8"), ensure_ascii=False, default=str)
        if not glob.glob(os.path.join(sdir, "snap_*.npz")):
            continue
        a = PA.analyze(sdir, quiet=True)
        ev = a["events"]
        for k in ("breaking_onset_B085", "face_past_vertical", "tube_closed_or_nearly"):
            if ev.get(k):
                ev[k]["t_group"] = ev[k]["t"] + TOFF
                if "crest_y" in ev[k]:
                    ev[k]["crest_y_still"] = ev[k]["crest_y"] - off
        cm = ev.get("crest_max_before_overturn_m")
        row = {"plunging": a["plunging"], "events": ev, "crest_max_before_overturn_still_m": (cm - off) if cm is not None else None,
               "m1": ((cm - off) / den) if cm is not None else None}
        tl = a["timeline"]
        row["timeline"] = {"t_group": [round(q["t"] + TOFF, 3) for q in tl], "crest_x": [round(q["crest"][0], 2) for q in tl],
                           "crest_y_still": [round(q["crest"][1] - off, 2) for q in tl], "B": [q.get("B") for q in tl],
                           "overturned": [bool(q.get("overturned")) for q in tl], "closed_air_m2": [q.get("closed_air_area_m2") for q in tl],
                           "chord_deg": [q.get("front_face_chord_angle_deg") for q in tl], "reach_over_Hc": [q.get("reach_over_Hc") for q in tl]}
        if ev.get("face_past_vertical"):
            tov = ev["face_past_vertical"]["t"]
            q = min(tl, key=lambda q: abs(q["t"] - tov))
            row["shape_at_overturn"] = {k: q.get(k) for k in ("front_face_chord_angle_deg", "back_dx_to_075Hc_m", "reach_over_Hc", "drop_over_Hc",
                                                               "overhang_over_Hc", "tube_aspect_w_over_h")}
            q2 = [q for q in tl if tov <= q["t"] <= tov + 1.2 and q.get("overturned")]
            if q2:
                q3 = q2[-1]
                row["shape_overturn_plus_1s"] = {k: q3.get(k) for k in ("t", "front_face_chord_angle_deg", "reach_over_Hc", "drop_over_Hc",
                                                                      "overhang_over_Hc", "tube_aspect_w_over_h", "closed_air_area_m2")}
        res["rows"]["%d" % zr] = row
        fv = ev.get("face_past_vertical") or {}
        tc = ev.get("tube_closed_or_nearly") or {}
        print("z %4d plunging %s | crest before overturn %.2f m (m1 %.2f) | vertical %s x %s | tube %s x %s area %s" % (
            zr, a["plunging"], (cm - off) if cm is not None else -1, row["m1"] or -1, fv.get("t_group"), fv.get("x"),
            tc.get("t") + TOFF if tc.get("t") is not None else None, tc.get("x"), tc.get("closed_area_m2")), flush=True)
    # 頂の歩み（主の列）：箱の一番上の水面
    xb, zb = M.xb, M.zb
    rs = np.abs(zb - zmain) <= max(0.9, 0.51 * (zb[1] - zb[0]))
    hist = []
    for k in range(len(B["frames"])):
        e = np.nanmax(B["eta"][k][rs][:, M.inb_x], axis=0) - off
        i = int(np.nanargmax(e))
        hist.append([float(B["t"][k]) + TOFF, float(e[i]), float(xb[M.inb_x][i])])
    h = np.array(hist)
    res["crest_history_main"] = {"z": zmain, "t_group": h[:, 0].round(3).tolist(), "crest": h[:, 1].round(2).tolist(), "x": h[:, 2].round(1).tolist()}
    # 峰に沿う形：主の列の前の面が垂直を過ぎた時刻（なければ最も高い時刻）の、z ごとの最も高い水面（壁で鏡に映した長さ）
    mr = res["rows"].get("%d" % int(zmain), {})
    tov = ((mr.get("events") or {}).get("face_past_vertical") or {}).get("t_group")
    kk = int(np.argmin(np.abs(h[:, 0] - tov))) if tov else int(np.argmax(h[:, 1]))
    for lab, dk in (("at_overturn", 0), ("overturn_minus_0.8s", -19)):
        k2 = max(kk + dk, 0)
        E = B["eta"][k2].astype(float) - off
        cl = np.nanmax(np.where(M.inb_x[None, :], E, -np.inf), axis=1)
        okz = M.inb_z
        Hc = float(np.nanmax(cl[okz])); dz = float(zb[1] - zb[0])
        L80 = float(np.sum(cl[okz] >= 0.8 * Hc) * dz) * 2.0
        L50 = float(np.sum(cl[okz] >= 0.5 * Hc) * dz) * 2.0
        z80 = zb[okz][cl[okz] >= 0.8 * Hc]
        res["crest_line_" + lab] = dict(t_group=float(B["t"][k2]) + TOFF, Hc=Hc, z_at_max=float(zb[okz][np.nanargmax(cl[okz])]), L80_m_mirrored=L80, L50_m_mirrored=L50,
                                        z80_range=[float(z80.min()), float(z80.max())] if z80.size else None,
                                        note="箱の z の範囲（−120〜−24 m）の中だけで数えた。壁で鏡に映した全長。0.5 倍の線が箱の端に届く時は下限")
    json.dump(res, open(os.path.join(rd, "analysis_r.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    print("crest max main row %.2f m at %.2f s x %.0f" % (h[:, 1].max(), h[np.argmax(h[:, 1]), 0], h[np.argmax(h[:, 1]), 2]))
    print(json.dumps({k: v for k, v in res.items() if k.startswith("crest_line")}, ensure_ascii=False, default=float))
    return res


if __name__ == "__main__":
    zm = -80.0
    for a in sys.argv:
        if a.startswith("--main="):
            zm = float(a.split("=")[1])
    main(sys.argv[1], zm)
