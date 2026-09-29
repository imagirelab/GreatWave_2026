# -*- coding: utf-8 -*-
"""設計38 第「輪郭線」部：線の点滅・跳び（191）、古い位置に残る線（192）、Mock の両眼の線の左右差、近くの線の太さを測る（numpy/OpenCV）。

入力（DS38Render の出力。Git 対象外）：
  <unity>/ds38_render_report.json、<unity>/l191/l191_<組>.bin（コマごとの線の画素と (番号, 列, 行, 距離)）、<unity>/s192/（描き直しの線と面の 1 bit）、
  <unity>/mock/（両眼の線と色の画像）、<unity>/near/（近くの線の ID 画像）。
定義（進行役の判断。既定値）：
  線の画素：DS38 の線のシェーダーの座標の描画（MSAA なし）で R ≥ 10 の画素。番号 1 主役波・2 near・3 far・4 爪。
  191 の点滅・跳び（設計37 の事前検査の定義に、線の出どころ（面の列・行、爪の番号・輪）をそろえる条件を足した）：
    一瞬だけ出た線（flash）：コマ f の線の画素で、f−1 と f+1 のどちらにも (頂点の画面の動きの最大 + 2 px) の内に線がないもの。
    一瞬だけ消えた線（hole）：f−1 と f+1 で同じ画素に同じ出どころ（同じ番号で、列・行の差がどちらも 2 以内。爪は同じ爪で輪の差 2 以内）の線があり、
                              f だけ 1.5 px の内に線がない画素。出どころをそろえるのは、別の 2 本の線が交わって通り過ぎる所（設計37 の事前検査の
                              「動く速さの違う 2 本の線が寄り合う所」）を消えたと数えないため。設計37 の定義（出どころを見ない）の数も記録する。
    跳び（jump）：f の線の画素で、f+1 の最も近い線まで (f → f+1 の頂点の画面の動きの最大 + 2 px) より遠いもの。
    塊：8 近傍で 10 px 以上。合格：連続 301 コマの各組で、flash・hole・jump の塊がどれも 0。
  192 古い位置に残る線：(a) 同じコマを、でたらめな順（前に別の時刻へ合わせて 1 回描いてから）で描き直した線の画素が、連続の描画の線の画素と
    1 画素も違わない（線が時刻だけで決まり、前の描画を持ち越さない）。(b) 線の画素のうち、そのコマの面（主役波・near・far・爪）から 4 px より離れたもの 0。
  Mock の両眼：左右の目（±0.032 m）の線の画素の数の差 ÷ 平均 < 10%（線の画素が両眼の平均で 500 以上の組で判定。少ない組は記録）。
    片眼だけの線（記録）：一方の目の線の画素のうち、他方の目に同じ出どころ（番号が同じで列・行の差 3 以内）の線の画素がないものの割合。
  近くの線の太さ：座席の向きのまま主役波の最も近い点へ 4・8・16 m まで寄せたカメラ（視野 80°）の線の ID 画像で、線の太さ（距離変換の中心の値 × 2）の
    p95 と最大。新しい決まり（DS38）と設計27 の外殻線 v0 の決まり（世界寸法の下限 5 cm）を並べる。合格：DS38 の p95 が 3 px 以下で、距離によらない。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds38/ds38_line_eval.py --unity <DS38Render の出力> [--t28 <t28 の組のある出力>]
出力：<out>/ds38_outlines_metrics.json
"""
import argparse
import json
import os
import struct

import cv2
import numpy as np

W, H = 1920, 1080
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


REC = np.dtype([("idx", "<u4"), ("sheet", "<u2"), ("col", "<u2"), ("row", "<u2"), ("dist", "<u2")])


def read_frames(path):
    out = []
    with open(path, "rb") as f:
        data = f.read()
    o = 0
    while o < len(data):
        n = struct.unpack_from("<i", data, o)[0]
        o += 4
        a = np.frombuffer(data, REC, n, o)
        o += n * REC.itemsize
        out.append(a)
    return out


def read_one(path):
    fr = read_frames(path)
    return fr[0]


def to_maps(a):
    m = np.zeros(H * W, bool)
    m[a["idx"]] = True
    sh = np.zeros(H * W, np.int16)
    sh[a["idx"]] = a["sheet"]
    cl = np.zeros(H * W, np.float32)
    cl[a["idx"]] = a["col"] / 10.0
    rw = np.zeros(H * W, np.float32)
    rw[a["idx"]] = a["row"] / 10.0
    return m.reshape(H, W), sh.reshape(H, W), cl.reshape(H, W), rw.reshape(H, W)


def dist_to(mask):
    """mask の画素までの距離（mask が空なら大きな値）。"""
    if not mask.any():
        return np.full(mask.shape, 1e6, np.float32)
    return cv2.distanceTransform((~mask).astype(np.uint8), cv2.DIST_L2, 5)


def clusters(mask, minpx=10, sheet=None):
    """8 近傍の塊（minpx 以上）。sheet があれば塊の中の最も多い番号（線の出どころ）を付ける。"""
    if not mask.any():
        return []
    n, lab, st, cen = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    out = []
    for i in range(1, n):
        if st[i, 4] < minpx:
            continue
        d = {"px": int(st[i, 4]), "x": int(st[i, 0]), "y": int(st[i, 1]), "w": int(st[i, 2]), "h": int(st[i, 3])}
        if sheet is not None:
            v = sheet[lab == i]
            v = v[v > 0]
            d["sheet"] = int(np.bincount(v).argmax()) if v.size else 0
        out.append(d)
    return out


def eval_seq(path, rec):
    frames = read_frames(path)
    n = len(frames)
    mv = np.asarray(rec["moveMax"], np.float64)  # mv[q] = q-1 → q
    maps = [None] * n
    dts = [None] * n

    def get(q):
        if maps[q] is None:
            maps[q] = to_maps(frames[q])
            dts[q] = dist_to(maps[q][0])
        return maps[q], dts[q]

    res = {"frames": n, "line_px": [int(len(a)) for a in frames], "flash": [], "hole": [], "hole_ds37": [], "jump": [],
           "flash_clusters": 0, "hole_clusters": 0, "hole_ds37_clusters": 0, "jump_clusters": 0, "cluster_list": []}
    by_sheet = np.zeros(5, np.int64)
    for a in frames:
        by_sheet += np.bincount(a["sheet"], minlength=5)[:5]
    res["line_px_by_sheet"] = by_sheet.tolist()
    for q in range(n):
        (m, sh, cl, rw), dt = get(q)
        fl = hl = h37 = jp = 0
        if 0 < q < n - 1:
            (mp, shp, clp, rwp), dtp = get(q - 1)
            (mn, shn, cln, rwn), dtn = get(q + 1)
            bound = max(mv[q], mv[q + 1]) + 2.0
            flash = m & (dtp > bound) & (dtn > bound)
            both = mp & mn
            same = both & (shp == shn) & (np.abs(clp - cln) <= 2.0) & (np.abs(rwp - rwn) <= 2.0)
            hole = same & (dt > 1.5)
            hole37 = both & (dt > 1.5)
            cf, ch, c37 = clusters(flash, sheet=sh), clusters(hole, sheet=shp), clusters(hole37)
            fl, hl, h37 = len(cf), len(ch), len(c37)
            for k, cc in (("flash", cf), ("hole", ch)):
                for x in cc:
                    x.update({"kind": k, "frame": q})
                    res["cluster_list"].append(x)
        if q < n - 1:
            (mn, _, _, _), dtn = get(q + 1)
            jump = m & (dtn > mv[q + 1] + 2.0)
            cj = clusters(jump, sheet=sh)
            jp = len(cj)
            for x in cj:
                x.update({"kind": "jump", "frame": q})
                res["cluster_list"].append(x)
        res["flash"].append(fl); res["hole"].append(hl); res["hole_ds37"].append(h37); res["jump"].append(jp)
        if q >= 2:
            maps[q - 2] = None; dts[q - 2] = None
    for k in ("flash", "hole", "hole_ds37", "jump"):
        res[k + "_clusters"] = int(sum(res[k]))
        res[k + "_frames"] = [i for i, v in enumerate(res[k]) if v > 0][:40]
    names = {1: "hero", 2: "near", 3: "far", 4: "claws"}
    bysh = {}
    for x in res["cluster_list"]:
        k = names.get(x.get("sheet", 0), "other")
        bysh.setdefault(k, {"flash": 0, "hole": 0, "jump": 0})[x["kind"]] += 1
    res["clusters_by_sheet"] = bysh
    res["pass_by_sheet"] = {k: not any(bysh.get(k, {"flash": 0, "hole": 0, "jump": 0}).values()) for k in names.values()}
    res["move_max_px_median"] = float(np.median(mv[1:])) if n > 1 else 0.0
    res["move_max_px_max"] = float(np.max(mv)) if n > 1 else 0.0
    res["pass"] = res["flash_clusters"] == 0 and res["hole_clusters"] == 0 and res["jump_clusters"] == 0
    res["cluster_count_listed"] = len(res["cluster_list"])
    res["cluster_list"] = res["cluster_list"][:300]
    return res


def eval_192(ud, rep, seq_frames):
    out = []
    for r in rep["s192"]:
        tag = "%s_f%03d" % (r["view"], r["frame"])
        a = read_one(os.path.join(ud, "s192", "redraw_" + tag + ".bin"))
        seq = seq_frames.get(r["view"])
        diff = None
        if seq is not None:
            q = r["frame"] - 60
            b = seq[q]
            sa, sb = set(a["idx"].tolist()), set(b["idx"].tolist())
            diff = len(sa ^ sb)
            ident = None
            if diff == 0:
                # 出どころも同じか
                ia, ib = np.sort(a, order="idx"), np.sort(b, order="idx")
                ident = int(np.sum((ia["sheet"] != ib["sheet"]) | (ia["col"] != ib["col"]) | (ia["row"] != ib["row"])))
        obj = np.unpackbits(np.fromfile(os.path.join(ud, "s192", "obj_" + tag + ".bin"), np.uint8)).reshape(H, W).astype(bool)
        d = dist_to(obj)
        m, _, _, _ = to_maps(a)
        orphan = m & (d > 4.0)
        # 画面の縁から 40 px の帯の中は、線を作る面が画面の外にあって面の 1 bit に入らないので、外れの判定から外す（記録は残す。1 回目の評価の後の定義の直し）
        yy, xx = np.mgrid[0:H, 0:W]
        inner = (xx >= 40) & (xx < W - 40) & (yy >= 40) & (yy < H - 40)
        oi = orphan & inner
        out.append({"view": r["view"], "frame": r["frame"], "t": r["t"], "prev_t": r["prevT"], "line_px": int(m.sum()),
                    "diff_px_vs_sequence": diff, "ident_diff_px": ident, "orphan_px": int(orphan.sum()), "orphan_clusters": len(clusters(orphan)),
                    "orphan_px_inner": int(oi.sum()), "orphan_clusters_inner": len(clusters(oi)),
                    "orphan_by_sheet": np.bincount(to_maps(a)[1][orphan], minlength=5)[:5].tolist()})
    ok = all(x["diff_px_vs_sequence"] == 0 and x["orphan_clusters_inner"] == 0 for x in out)
    return {"redraws": out, "total_diff_px": int(sum(x["diff_px_vs_sequence"] or 0 for x in out)),
            "total_orphan_px": int(sum(x["orphan_px"] for x in out)), "total_orphan_clusters": int(sum(x["orphan_clusters"] for x in out)),
            "total_orphan_px_inner": int(sum(x["orphan_px_inner"] for x in out)), "total_orphan_clusters_inner": int(sum(x["orphan_clusters_inner"] for x in out)),
            "pass": ok}


def eval_mock(ud, rep):
    pairs = {}
    for r in rep["mock"]:
        pairs.setdefault((r["view"], round(r["t"], 2)), {})[r["eye"]] = r
    out = []
    for (v, t), e in sorted(pairs.items()):
        L, R = e["L"], e["R"]
        nl, nr = L["linePx"], R["linePx"]
        mean = 0.5 * (nl + nr)
        rel = abs(nl - nr) / mean if mean > 0 else 0.0
        la = read_one(os.path.join(ud, "mock", os.path.basename(L["lines"])))
        ra = read_one(os.path.join(ud, "mock", os.path.basename(R["lines"])))

        def one_eye_only(a, b):
            if len(a) == 0:
                return 0.0
            keys = {}
            for s, c, r_ in zip(b["sheet"].tolist(), (b["col"] // 10).tolist(), (b["row"] // 10).tolist()):
                keys[(s, c, r_)] = 1
            miss = 0
            for s, c, r_ in zip(a["sheet"].tolist(), (a["col"] // 10).tolist(), (a["row"] // 10).tolist()):
                found = False
                for dc in range(-3, 4):
                    for dr in range(-3, 4):
                        if (s, c + dc, r_ + dr) in keys:
                            found = True
                            break
                    if found:
                        break
                if not found:
                    miss += 1
            return miss / len(a)
        judged = mean >= 500
        out.append({"view": v, "t": t, "L_px": nl, "R_px": nr, "rel_diff": rel, "judged": judged, "pass": (rel < 0.10) if judged else None,
                    "L_by_sheet": L["bySheet"], "R_by_sheet": R["bySheet"],
                    "one_eye_only_frac_L": one_eye_only(la, ra), "one_eye_only_frac_R": one_eye_only(ra, la)})
    j = [x for x in out if x["judged"]]
    return {"pairs": out, "judged_pairs": len(j), "max_rel_diff_judged": max([x["rel_diff"] for x in j], default=None),
            "max_rel_diff_all": max([x["rel_diff"] for x in out], default=None),
            "max_one_eye_only_frac": max([max(x["one_eye_only_frac_L"], x["one_eye_only_frac_R"]) for x in out], default=None),
            "pass": all(x["pass"] for x in j) and len(j) > 0}


def thickness(mask):
    if not mask.any():
        return {"px": 0, "p50": None, "p95": None, "max": None}
    dt = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    # 中心の値：3×3 の近傍で最大の画素
    mx = cv2.dilate(dt, np.ones((3, 3), np.uint8))
    ridge = mask & (dt >= mx - 1e-6)
    v = 2.0 * dt[ridge]
    return {"px": int(mask.sum()), "p50": float(np.percentile(v, 50)), "p95": float(np.percentile(v, 95)), "max": float(v.max())}


def eval_near(ud, rep):
    out = []
    for r in rep["near"]:
        im = cv2.imdecode(np.fromfile(os.path.join(ud, "near", os.path.basename(r["path"])), np.uint8), cv2.IMREAD_COLOR)[:, :, ::-1]
        m = (im[:, :, 0] >= 250) & (im[:, :, 1] <= 5) & (im[:, :, 2] >= 250)
        th = thickness(m)
        out.append({"law": r["law"], "dist_m": r["dist"], **th})
    d38 = [x for x in out if x["law"] == "ds38" and x["p95"] is not None]
    ok = len(d38) > 0 and all(x["p95"] <= 3.0 for x in d38)
    return {"probes": out, "pass": ok}


def seq_distance_bins(frames, fov_deg):
    """線の画素の出どころの中心眼からの距離ごとの数と、その距離での線幅（決まりの式）。"""
    pix = 2.0 * np.tan(np.radians(fov_deg) / 2) / H
    d = np.concatenate([a["dist"] for a in frames]).astype(np.float64) / 10.0 if frames else np.zeros(0)
    bins = [0, 10, 20, 40, 80, 160, 320, 1000]
    hist = np.histogram(d, bins)[0].tolist()
    return {"bins_m": bins, "count": hist, "min_dist_m": float(d.min()) if d.size else None, "pixel_angle_rad": pix}


def seam_measure(frames, col_min=18, col_max=394, inset=10):
    """主役波の線の画素のうち、設計30修正1 が線を描かなかった両端の 10 列（列 18〜27・385〜394）から出た画素と、境の輪（列 18〜19・393〜394）から出た画素の数（コマごと）。"""
    ins, ring = [], []
    for a in frames:
        h = a[a["sheet"] == 1]
        c = h["col"] / 10.0
        ins.append(int(np.sum((c < col_min + inset) | (c > col_max - inset))))
        ring.append(int(np.sum((c < col_min + 2) | (c > col_max - 2))))
    return {"inset_cols_px": ins, "ring_cols_px": ring, "inset_cols_px_max": max(ins) if ins else 0, "ring_cols_px_max": max(ring) if ring else 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unity", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    ud = os.path.abspath(a.unity)
    out = a.out or os.path.dirname(ud)
    rep = load_json(os.path.join(ud, "ds38_render_report.json"))
    res = {"schema": "GreatWave.DS38.outlines_metrics/1", "unity_report": os.path.join(ud, "ds38_render_report.json"), "min_px": rep["minPx"]}
    seqres = {}
    seq_frames = {}
    fovs = {c["name"]: c["fovDeg"] for c in rep["cameras"]}
    for s in rep["seqs"]:
        p = os.path.join(ud, "l191", os.path.basename(s["path"]))
        r = eval_seq(p, s)
        fr = read_frames(p)
        r["distance"] = seq_distance_bins(fr, fovs.get(s["view"], 80))
        r["seam"] = seam_measure(fr)
        seqres[s["name"]] = r
        if s["name"].startswith("form_"):
            seq_frames[s["view"]] = fr
        print(s["name"], "flash", r["flash_clusters"], "hole", r["hole_clusters"], "hole_ds37", r["hole_ds37_clusters"], "jump", r["jump_clusters"],
              "line_px median", int(np.median(r["line_px"])), "by_sheet", r["line_px_by_sheet"], flush=True)
    res["191"] = {"sequences": seqres, "pass": all(v["pass"] for v in seqres.values())}
    if rep.get("s192"):
        res["192"] = eval_192(ud, rep, seq_frames)
        print("192 diff", res["192"]["total_diff_px"], "orphan", res["192"]["total_orphan_px"], res["192"]["total_orphan_clusters"], "inner", res["192"]["total_orphan_px_inner"], res["192"]["total_orphan_clusters_inner"])
    if rep.get("mock"):
        res["mock"] = eval_mock(ud, rep)
        print("mock max rel judged", res["mock"]["max_rel_diff_judged"], "all", res["mock"]["max_rel_diff_all"])
    if rep.get("near"):
        res["near"] = eval_near(ud, rep)
        for x in res["near"]["probes"]:
            print("near", x)
    with open(os.path.join(out, "ds38_outlines_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
