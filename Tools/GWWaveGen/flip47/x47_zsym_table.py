# -*- coding: utf-8 -*-
"""FLIP47：板の層の差の試し（x47_zsym.py ana の zsym.json）を並べる表と図（py -3.10 -B）。2026-10-13 板の層の差を調べる役（Claude）。
  py -3.10 -B x47_zsym_table.py <run_id> ... [+ <run_id> ...]   → runs/ZSYM_compare/zsym_table.json・zsym_table.md・zsym_layers_touchdown.png・zsym_lateral_v.png
"+" で組に分け、組ごとに最初の run_id を基準にして Hb・xbp の差（%）を出す。
層の差の物差し：
  幅 rel = (層の最大 − 最小) ÷ 層の平均（Ao/Hb²・噴流の幅・唇の下の空気・唇の厚み）
  傾き trend = 層の z に対する一次の当てはめの傾き × 板の厚さ ÷ 層の平均（向きのある差。+ なら +z の側ほど大きい）
"""
import os, sys, json, math
sys.dont_write_bytecode = True
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g47_common as GC

B47 = GC.B47
CMP = B47 + "/runs/ZSYM_compare"


def load(rid):
    return json.load(open(B47 + "/runs/%s/zsym/zsym.json" % rid, encoding="utf8"))


def trend(vals, z, Lz):
    v = np.array([np.nan if x is None else x for x in vals], float)
    ok = np.isfinite(v)
    if ok.sum() < 2:
        return None
    a = np.polyfit(np.array(z)[ok], v[ok], 1)[0]
    m = float(np.nanmean(v))
    return float(a * Lz / m) if m else None


def rel(vals):
    v = [x for x in vals if x is not None]
    if len(v) < 2:
        return None
    m = float(np.mean(v))
    return float((max(v) - min(v)) / abs(m)) if m else None


def row(o, ref=None):
    z = o["layer_z"]; Lz = float(o["Lz"])
    td = o["touchdown_by_layer"]
    im = o["main_layer"]
    r = dict(run_id=o["run_id"], variant=o["variant"], nz=o["nz"], solver=o.get("solver"), init_jitter=o.get("init_jitter"),
             Hb_h0_main=td["Hb_h0"][im], xbp_h0_main=td["xbp_h0"][im], td_frame_main=td["frame"][im],
             Hb_h0_mean=float(np.mean([x for x in td["Hb_h0"] if x is not None])), xbp_h0_mean=float(np.mean([x for x in td["xbp_h0"] if x is not None])),
             Hb_h0_meanfield=o["touchdown_mean_field"].get("Hb_h0"), xbp_h0_meanfield=o["touchdown_mean_field"].get("xbp_h0"),
             AO_meanfield=o["touchdown_mean_field"].get("AO_Hb2"), jet_meanfield=o["touchdown_mean_field"].get("jet_width_h0"),
             onset=o.get("main_onset"), best3=o.get("main_best3"), run=o.get("run"))
    for q in ("AO_Hb2", "AJ_Hb2", "jet_width_h0", "W_L", "theta_o_deg"):
        r[q] = dict(vals=td[q], rel=rel(td[q]), trend=trend(td[q], z, Lz), mean=float(np.mean([x for x in td[q] if x is not None])))
    for nm in ("at_touchdown", "at_best3"):
        rows = o[nm]["rows"]
        r[nm] = dict(frame=o[nm]["frame"])
        for q in ("chord", "foot", "air", "lip", "area"):
            vals = [(x or {}).get(q) for x in rows]
            ok = [v for v in vals if v is not None]
            r[nm][q] = dict(vals=vals, rel=rel(vals), trend=trend(vals, z, Lz), mean=(float(np.mean(ok)) if ok else None),
                            range=(float(max(ok) - min(ok)) if ok else None))
    zb = o.get("zdiag_break") or {}
    zp = o.get("zdiag_pre") or {}
    r["lateral"] = dict(pre=zp, brk=zb)
    if ref is not None:
        r["dHb_main_pct"] = 100.0 * (r["Hb_h0_main"] / ref["Hb_h0_main"] - 1.0)
        r["dxbp_main_pct"] = 100.0 * (r["xbp_h0_main"] / ref["xbp_h0_main"] - 1.0)
        r["dHb_mean_pct"] = 100.0 * (r["Hb_h0_mean"] / ref["Hb_h0_mean"] - 1.0)
        r["dxbp_mean_pct"] = 100.0 * (r["xbp_h0_mean"] / ref["xbp_h0_mean"] - 1.0)
    return r


def f(v, n=3):
    if v is None:
        return "—"
    if isinstance(v, (list, tuple)):
        return "・".join(f(x, n) for x in v)
    return ("%%.%df" % n) % v


def md(rows):
    L = ["| 試し | 層 | Hb/h0（主・層の平均） | xbp/h0（主） | Hb・xbp の差 % | Ao/Hb² 層ごと（−z → +z） | 幅 rel | 傾き | 噴流の幅/h0 層ごと | 幅 rel | 傾き |",
         "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        L.append("| %s | %d | %s・%s | %s | %s・%s | %s | %s | %s | %s | %s | %s |" % (
            r["run_id"], r["nz"], f(r["Hb_h0_main"]), f(r["Hb_h0_mean"]), f(r["xbp_h0_main"], 2),
            f(r.get("dHb_main_pct"), 1), f(r.get("dxbp_main_pct"), 1),
            f(r["AO_Hb2"]["vals"], 2), f(r["AO_Hb2"]["rel"], 2), f(r["AO_Hb2"]["trend"], 2),
            f(r["jet_width_h0"]["vals"], 3), f(r["jet_width_h0"]["rel"], 2), f(r["jet_width_h0"]["trend"], 2)))
    L += ["", "| 試し | 着水のコマ：唇の下の空気 層ごと | rel | 唇の厚み 層ごと | rel | 前の面の弦 | 最も近いコマ（主）：弦 層ごと | 空気 | 唇 | 覆い |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        t = r["at_touchdown"]; b = r["at_best3"]
        L.append("| %s | %s | %s | %s | %s | %s | %s（コマ %s） | %s | %s | %s |" % (
            r["run_id"], f(t["air"]["vals"], 2), f(t["air"]["rel"], 2), f(t["lip"]["vals"], 2), f(t["lip"]["rel"], 2),
            f(t["chord"]["vals"], 0), f(b["chord"]["vals"], 0), b["frame"], f(b["air"]["vals"], 2), f(b["lip"]["vals"], 2), f(b["area"]["vals"], 3)))
    L += ["", "| 試し | 巻き始め〜着水：頂の上の粒子の vz の平均 m/s | vz の RMS | 頂の上半分の粒子の z の平均 m | 上半分の粒子の層ごとの割合 | 格子の vel.z 内の面ごとの平均 | 前の 3 s の vz の RMS |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        z = r["lateral"]["brk"] or {}; p = r["lateral"]["pre"] or {}
        L.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            r["run_id"], f(z.get("crest_vz_mean"), 4), f(z.get("crest_vz_rms"), 4), f(z.get("upper_z_mean"), 4),
            f(z.get("upper_layer_frac"), 3), f(list((z.get("grid_vz_face_mean") or {}).values()), 4), f(p.get("crest_vz_rms"), 4)))
    return "\n".join(L) + "\n"


def fig_layers(rids, out_png, which="touchdown"):
    """試しごとに、層ごとの断面（各層の着水のコマ、層ごとの η_c で割り頂をそろえる）を重ねる。青 −z → 赤 +z。黒は原画。"""
    from PIL import Image, ImageDraw
    import g47_scan as SC
    GA = SC._ga()
    PL, _ = SC.print_lines()
    XL, XR, ZB, ZT = -1.6, 2.0, -0.15, 1.08
    PX = 200
    W = int((XR - XL) * PX); H = int((ZT - ZB) * PX)
    ncol = min(3, len(rids)); nrow = int(math.ceil(len(rids) / ncol))
    pw, ph = W + 40, H + 120
    img = Image.new("RGB", (max(ncol * pw + 30, 1300), nrow * ph + 130), "white"); dr = ImageDraw.Draw(img)
    dr.text((20, 12), "板の層ごとの断面（各層の着水のコマ、層ごとの η_c で割り頂をそろえた）：青 −z の壁の側 → 赤 +z の壁の側、黒は原画",
            fill=GA.TXT, font=GA.font(17, True))
    dr.text((20, 42), "2D の板なので、層の線は重なるのが正しい。各図の上の数は層ごとの Ao/Hb²（−z → +z）", fill=GA.SUB, font=GA.font(14))
    for n, rid in enumerate(rids):
        rd = B47 + "/runs/" + rid
        o = load(rid)
        nz = o["nz"]
        cols = [tuple(int(c) for c in (np.array([30, 80, 220]) * (1 - s) + np.array([210, 30, 30]) * s)) for s in np.linspace(0, 1, nz)]
        cx0 = 20 + (n % ncol) * pw; cy0 = 80 + (n // ncol) * ph
        ox, oy = cx0 + 20, cy0 + 50
        tr = lambda p: (ox + (p[0] - XL) * PX, oy + (ZT - p[1]) * PX)
        dr.text((cx0, cy0), "%s（%s、格子 %d 層）" % (rid, o["variant"], nz), fill=GA.TXT, font=GA.font(15, True))
        dr.rectangle([ox, oy, ox + W, oy + H], outline=(170, 170, 170))
        for zv in (0.0, 0.5, 1.0):
            dr.line([tr((XL, zv)), tr((XR, zv))], fill=(120, 120, 120) if zv == 0 else (225, 225, 225), width=1)
        txt = []
        for k in range(nz):
            p = rd + "/zsym/z%d/%s_z%d_masks.npz" % (k, rid, k)
            j = rd + "/zsym/z%d/g47_ana.json" % k
            if not (os.path.exists(p) and os.path.exists(j)):
                continue
            mk = np.load(p); a = json.load(open(j, encoding="utf8"))
            at = (a.get("at") or {}).get(which)
            if not at or which + "_M" not in mk.files:
                continue
            for L_ in GA.mask_lines(mk[which + "_M"], mk[which + "_X"], mk[which + "_Z"], at["x_c"], at["eta_c"]):
                P_ = [tr(q) for q in L_ if XL - 0.05 <= q[0] <= XR + 0.05 and ZB - 0.05 <= q[1] <= ZT + 0.05]
                if len(P_) > 1:
                    dr.line(P_, fill=cols[k], width=2)
            pm = a.get("paper_measures") or {}
            if pm.get("AO_Hb2") is not None:
                txt.append("%.2f" % pm["AO_Hb2"])
        for L_ in PL:
            P_ = [tr(q) for q in L_ if XL - 0.05 <= q[0] <= XR + 0.05 and ZB - 0.05 <= q[1] <= ZT + 0.05]
            if len(P_) > 1:
                dr.line(P_, fill=(0, 0, 0), width=2)
        dr.text((cx0, cy0 + 24), "Ao/Hb²：" + "・".join(txt), fill=GA.SUB, font=GA.font(13))
    img.save(out_png)
    return out_png


def fig_lateral(rids, out_png):
    """頂のまわり（±30 m、y > 2 m）の粒子の横の流速 vz の RMS と平均、頂の上半分の粒子の z の平均の、時刻の並び。"""
    from PIL import Image, ImageDraw
    import g47_scan as SC
    GA = SC._ga()
    W, H = 1500, 980
    img = Image.new("RGB", (W, H), "white"); dr = ImageDraw.Draw(img)
    dr.text((20, 12), "頂のまわりの粒子の横（板の厚さの向き）の流速。2D なら 0 が正しい。各線は着水の 0.25 s 後まで（細い縦線：巻き始め）", fill=GA.TXT, font=GA.font(18, True))
    panels = [("crest", "vz_rms", "vz の RMS（m/s）頂 ±30 m・y > 2 m", 0.0, None),
              ("crest", "vz_mean", "vz の平均（m/s。− は −z の壁へ）", None, None),
              ("upper", "z_mean", "頂の上半分の粒子の z の平均（m）", None, None)]
    COLS = [(31, 119, 180), (214, 39, 40), (44, 160, 44), (148, 103, 189), (255, 127, 14), (140, 86, 75), (23, 190, 207)]
    data = {}
    for rid in rids:
        o = load(rid)
        tdt = (o.get("main_touchdown") or {}).get("t")
        ser = [e for e in (o.get("zdiag_series") or []) if tdt is None or e["t"] <= tdt + 0.25 + 1e-9]
        data[rid] = (o, ser)
    pw, ph = W - 140, 230
    for pi, (grp, key, title, lo, hi) in enumerate(panels):
        x0, y0 = 100, 60 + pi * (ph + 50)
        dr.text((x0, y0 - 22), title, fill=GA.SUB, font=GA.font(14))
        dr.rectangle([x0, y0, x0 + pw, y0 + ph], outline=(160, 160, 160))
        allv = [((e.get(grp) or {}).get(key)) for rid in rids for e in data[rid][1]]
        allv = [v for v in allv if v is not None]
        if not allv:
            continue
        vmin = lo if lo is not None else min(allv); vmax = hi if hi is not None else max(allv)
        if vmax - vmin < 1e-9:
            vmax = vmin + 1e-3
        tmax = max(e["t"] for rid in rids for e in data[rid][1])
        tmin = 8.0
        for v in np.linspace(vmin, vmax, 5):
            yy = y0 + ph - (v - vmin) / (vmax - vmin) * ph
            dr.line([x0, yy, x0 + pw, yy], fill=(232, 232, 232))
            dr.text((10, yy - 8), "%.3f" % v, fill=GA.SUB, font=GA.font(12))
        for tt in range(int(tmin), int(tmax) + 1):
            xx = x0 + (tt - tmin) / (tmax - tmin) * pw
            dr.text((xx - 6, y0 + ph + 4), "%d" % tt, fill=GA.SUB, font=GA.font(12))
        if vmin < 0 < vmax:
            yy = y0 + ph - (0 - vmin) / (vmax - vmin) * ph
            dr.line([x0, yy, x0 + pw, yy], fill=(120, 120, 120))
        for n, rid in enumerate(rids):
            o, ser = data[rid]
            P = [(x0 + (e["t"] - tmin) / (tmax - tmin) * pw, y0 + ph - ((e.get(grp) or {}).get(key) - vmin) / (vmax - vmin) * ph)
                 for e in ser if e["t"] >= tmin and (e.get(grp) or {}).get(key) is not None]
            if len(P) > 1:
                dr.line(P, fill=COLS[n % len(COLS)], width=2)
            on = (o.get("main_onset") or {}).get("t")
            if on:
                xx = x0 + (on - tmin) / (tmax - tmin) * pw
                dr.line([xx, y0, xx, y0 + ph], fill=COLS[n % len(COLS)], width=1)
    for n, rid in enumerate(rids):
        dr.text((110 + (n % 3) * 460, H - 56 + (n // 3) * 22), "— " + rid, fill=COLS[n % len(COLS)], font=GA.font(14, True))
    dr.text((W - 260, H - 84), "横軸：時刻 s", fill=GA.SUB, font=GA.font(12))
    img.save(out_png)
    return out_png


def table(args):
    """args：run_id の並び。"+"（または "/"）で組に分ける（組ごとに最初を基準にして Hb・xbp の差を出す）。"""
    os.makedirs(CMP, exist_ok=True)
    groups, cur = [], []
    for a in args:
        if a in ("/", "+"):
            if cur:
                groups.append(cur)
            cur = []
        else:
            cur.append(a)
    if cur:
        groups.append(cur)
    rows, mds = [], []
    for g in groups:
        os_ = [load(r) for r in g]
        ref = row(os_[0])
        rr = [dict(ref, dHb_main_pct=0.0, dxbp_main_pct=0.0, dHb_mean_pct=0.0, dxbp_mean_pct=0.0)] + [row(o, ref) for o in os_[1:]]
        for r in rr:
            r["group_ref"] = g[0]
        rows += rr
        mds.append("基準：%s\n\n" % g[0] + md(rr))
    json.dump(rows, open(CMP + "/zsym_table.json", "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    text = "\n".join(mds)
    open(CMP + "/zsym_table.md", "w", encoding="utf8").write(text)
    allr = [r for g in groups for r in g]
    figr = [r for r in allr if load(r)["nz"] > 1]
    fig_layers(figr, CMP + "/zsym_layers_touchdown.png")
    zr = [r for r in allr if load(r).get("zdiag_series")]
    if zr:
        fig_lateral(zr, CMP + "/zsym_lateral_v.png")
    print(text)
    return rows


if __name__ == "__main__":
    table(sys.argv[1:])
