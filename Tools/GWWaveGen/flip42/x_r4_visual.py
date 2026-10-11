# -*- coding: utf-8 -*-
"""FLIP42 R4 の段：計画 §6 の見た目の量を、R2/record_ja.md §7 の形と、独立の確かめ（check/R2/check_ja.md の 1・4）の読み方で出す（py -3.10）。
2026-10-10 に足した（R4d を走らせている間、R4d の結果を見る前に書いた）。測り方：
  - 巻き始めにそろえた時刻（−0.3〜+0.3 Tc）と着水の、η_c・H。H は前の谷（頂から前へ 0.75 Lc まで、読み方 9）と
    後ろの谷（頂から後ろへ 0.75 Lc まで、確かめの 4）の両方。一番上の水面の高さ（板の真ん中の節）から。
  - 60° より立った前の面の高さ、唇（届く距離・半分の所の厚み）、囲んだ空気、頂の断面積：g_shape.py の shape.json の rows のまま。
  - 唇はその時刻だけでなく、時間の窓ごとの最大（確かめの 1）：[巻き始め − 0.2 s, 着水)、[着水, 着水 + 1 s)、[着水 + 1 s, 巻き始め + 3.6 s]。
    R3 ではこの窓が確かめの 154.5〜156.0・156.0〜157.0・157.0〜158.3 s と同じになる。
  - 空気：4 m² 以上の空気が初めてできた時と、巻き始め + 3.6 s までの最大の空気（面積・前後の端・下の端の高さ）。
  - 噴流の先の最も低い所（巻き始めから + 3.6 s まで、唇の先の高さの最小）。
  - （2026-10-11 11:00、R4d の結果を見た後に足した）2 つ目の噴流が前の面の低い所（静かな水面から 2 m 以下）に 4 m² 以上の空気を
    囲んだ最初の時、その前の唇の最大、その後に空気の線が開いたコマ。
使い方: py -3.10 x_r4_visual.py <out.json> <run_id> [<run_id> ...]
"""
import sys, os, json
import numpy as np

sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42")
import g_analyze as A
import g_shape as GS

OFFS = [-0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3]
T_AFTER = 3.6   # 巻き始めから見る長さ（s）。R3 では確かめの 158.3 s までと同じ


def troughs(etop, x, xc, Lc):
    ic = int(np.argmin(abs(x - xc)))
    ec = float(etop[ic])
    out = dict(eta_c=ec, x_crest=float(x[ic]))
    for side, m in (("front", (x > x[ic]) & (x <= x[ic] + 0.75 * Lc)), ("rear", (x < x[ic]) & (x >= x[ic] - 0.75 * Lc))):
        if m.any() and np.isfinite(etop[m]).any():
            j = np.where(m)[0][int(np.nanargmin(etop[m]))]
            out[side] = dict(trough=float(etop[j]), dist=float(abs(x[j] - x[ic])), H=float(ec - etop[j]))
        else:
            out[side] = None
    return out


def cavity_full(sdf, meta, off, vox, Lc, xc, yc, xp):
    """そのコマの空気を囲む閉じた線（g_shape.extra と同じ選び方）を全部、下の端の高さつきで。"""
    lines, S, xs, ys = GS.contours(sdf, meta, off)
    cav = []
    for l in lines:
        if len(l) > 4 and np.allclose(l[0], l[-1]):
            Aa = A.poly_area(l)
            cx, cy = l[:, 0].mean(), l[:, 1].mean()
            if Aa >= vox * vox and (xc - 0.25 * Lc) <= cx <= (xc + 0.75 * Lc) and cy < yc:
                ix = int(round((cx - xs[0]) / meta["dx"])); iy = int(round((cy - ys[0]) / meta["dy"]))
                if 0 <= ix < S.shape[1] and 0 <= iy < S.shape[0] and S[iy, ix] > 0:
                    cav.append(dict(area=float(Aa), x_back=float(l[:, 0].min() - xp), x_front=float(l[:, 0].max() - xp),
                                    y_bot=float(l[:, 1].min()), y_top=float(l[:, 1].max())))
    return cav


def run(rid):
    P = A.plan(); C = A.comps_full(P)
    Tc, Lc = C["Tc"], C["Lc"]
    cfg = json.load(open(os.path.join(A.ROOT, rid, "cfg.json"), encoding="utf8"))
    xp = cfg["parms"]["x_p"]; vox = cfg["parms"]["dp"] * 2.0
    sh = json.load(open(os.path.join(A.ROOT, rid, "shape.json"), encoding="utf8"))
    off = sh["still_level_offset_m"]
    on, tou = sh.get("onset"), sh.get("touchdown")
    res = dict(run_id=rid, dp=cfg["parms"]["dp"], vox=vox, still_level_offset_m=off)
    if not on:
        res["note"] = "巻き始めなし"
        return res
    D = A.load_hf(rid)
    x = D["x"]; mid = D["eta"].shape[1] // 2
    fidx = {int(f): i for i, f in enumerate(D["frames"])}
    rows = sh["rows"]; tt = np.array([r["t"] for r in rows])
    res["onset"] = dict(t=on["t"], x_vertical=on.get("vertical_x_rel"), xc=on["xc_rel"])
    res["touchdown"] = None if not tou else dict(t=tou["t"], x=tou.get("x_rel"), by=tou.get("by"))

    def phase_row(r, label):
        i = fidx[int(r["frame"])]
        etop = D["eta"][i, mid, :] - off
        tr = troughs(etop, x - xp, r["xc_rel"], Lc)
        lip = r.get("jet_lip"); cv = r.get("cavity")
        return dict(label=label, t=r["t"], frame=int(r["frame"]), xc=r["xc_rel"], eta_c=tr["eta_c"],
                    H_front=None if not tr["front"] else tr["front"]["H"], trough_front=None if not tr["front"] else tr["front"]["trough"],
                    dist_front=None if not tr["front"] else tr["front"]["dist"],
                    H_rear=None if not tr["rear"] else tr["rear"]["H"], trough_rear=None if not tr["rear"] else tr["rear"]["trough"],
                    dist_rear=None if not tr["rear"] else tr["rear"]["dist"],
                    H_record=r.get("H"), eta_c_record=r.get("eta_c"),
                    steep_h60=r.get("steep_h60"), steep_h60_over_H=(r["steep_h60"] / r["H"]) if r.get("H") else None,
                    lip=None if not lip else dict(reach=lip["reach"], thick=lip["thick_mid"], y_tip=lip["y_tip"]),
                    cavity=None if not cv else dict(area=cv["area"], length=cv["reach"], thick=cv["thick_mid"], x_back=cv["x_back_rel"], x_front=cv["x_front_rel"]),
                    crest_area=r.get("crest_area"), ahead_area=r.get("ahead_area"))
    ph = []
    for o in OFFS:
        k = int(np.argmin(abs(tt - (on["t"] + o * Tc))))
        ph.append(phase_row(rows[k], "%+.1f Tc" % o if o else "巻き始め"))
    if tou:
        k = int(np.argmin(abs(tt - tou["t"])))
        ph.append(phase_row(rows[k], "着水"))
    res["phases"] = ph
    # 唇の時間の窓ごとの最大
    t_end = on["t"] + T_AFTER + 1e-6
    t_tou = tou["t"] if tou else t_end
    wins = [(on["t"] - 0.2, t_tou), (t_tou, min(t_tou + 1.0, t_end)), (min(t_tou + 1.0, t_end), t_end)]
    res["lip_windows"] = []
    for lo, hi in wins:
        q = [r for r in rows if lo <= r["t"] < hi and r.get("jet_lip")]
        if q:
            b = max(q, key=lambda r: r["jet_lip"]["reach"])
            res["lip_windows"].append(dict(window=[lo, hi], t=b["t"], reach=b["jet_lip"]["reach"], thick=b["jet_lip"]["thick_mid"],
                                           y_tip=b["jet_lip"]["y_tip"], x_tip=b["jet_lip"]["x_tip_rel"]))
        else:
            res["lip_windows"].append(dict(window=[lo, hi], t=None))
    q = [r for r in rows if on["t"] - 0.2 <= r["t"] < t_end and r.get("jet_lip")]
    res["lip_max_all"] = None if not q else (lambda b: dict(t=b["t"], reach=b["jet_lip"]["reach"], thick=b["jet_lip"]["thick_mid"],
                                                             y_tip=b["jet_lip"]["y_tip"], x_tip=b["jet_lip"]["x_tip_rel"]))(max(q, key=lambda r: r["jet_lip"]["reach"]))
    res["lip_tip_lowest"] = None if not q else (lambda b: dict(t=b["t"], y_tip=b["jet_lip"]["y_tip"], x_tip=b["jet_lip"]["x_tip_rel"], reach=b["jet_lip"]["reach"]))(
        min(q, key=lambda r: r["jet_lip"]["y_tip"]))
    # 空気
    SEC = A.load_sec(rid)
    sidx = {int(f): j for j, f in enumerate(SEC["frames"])}
    air = []
    for r in rows:
        if not (on["t"] <= r["t"] < t_end) or not r.get("cavity"):
            continue
        j = sidx[int(r["frame"])]
        shp = A.frame_shape(SEC["sdf"][j], SEC["meta"], off, vox, Lc, None, None)
        for c in cavity_full(SEC["sdf"][j], SEC["meta"], off, vox, Lc, shp["xc"], shp["yc"], xp):
            air.append(dict(t=r["t"], **c))
    big = [a for a in air if a["area"] >= 4.0]
    res["air_first_ge4"] = big[0] if big else None
    # 2026-10-11 11:00 に足した（R4d の結果を見た後）：2 つ目の噴流が前の面の低い所（静かな水面から 2 m 以下）に落ちて
    # 4 m² 以上の空気を囲んだ最初の時と、その前（最初の着水から）の唇の最大。R4d では、空気を囲んだ後に空気の線が開いたコマで
    # 噴流の下の面ごと唇として読まれ（7.6〜7.9 m）、窓ごとの最大がその読みになったため、囲む前の唇で R3 とそろえる。
    low = [a for a in air if a["area"] >= 4.0 and a["y_bot"] <= 2.0]
    res["low_air_first"] = low[0] if low else None
    t_low = low[0]["t"] if low else t_end
    q2 = [r for r in rows if t_tou <= r["t"] < t_low and r.get("jet_lip")]
    res["lip_max_before_low_air"] = None if not q2 else (lambda b: dict(t=b["t"], reach=b["jet_lip"]["reach"], thick=b["jet_lip"]["thick_mid"],
                                                                         y_tip=b["jet_lip"]["y_tip"], x_tip=b["jet_lip"]["x_tip_rel"]))(max(q2, key=lambda r: r["jet_lip"]["reach"]))
    # 空気を囲む線が開いたコマ（low の空気ができた後、+3.6 s までで、4 m² 以上の空気がないコマ）
    t_air = sorted(set(a["t"] for a in air if a["area"] >= 4.0 and a["y_bot"] <= 2.5))
    res["low_air_open_frames"] = [r["t"] for r in rows if t_low < r["t"] < min(t_end, (t_air[-1] if t_air else t_end)) and r["t"] not in t_air]
    res["air_largest"] = max(air, key=lambda a: a["area"]) if air else None
    res["air_first_any"] = air[0] if air else None
    res["window_end_t"] = t_end
    return res


if __name__ == "__main__":
    outp = sys.argv[1]
    out = {rid: run(rid) for rid in sys.argv[2:]}
    json.dump(out, open(outp, "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    for rid, r in out.items():
        print(rid, json.dumps({k: r.get(k) for k in ("onset", "touchdown", "lip_windows", "lip_max_all", "lip_tip_lowest", "air_first_ge4", "air_largest", "low_air_first", "lip_max_before_low_air", "low_air_open_frames")},
                              ensure_ascii=False, default=float)[:2500])
