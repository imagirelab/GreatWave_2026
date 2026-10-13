# -*- coding: utf-8 -*-
"""FLIP47：2D の板の層の差（噴流が z −0.75 m の層ほど太く、空洞が小さい）の元を分ける試しの設定・読み・表（py -3.10 -B）。
2026-10-13 板の層の差を調べる役（Claude）が書いた。読むだけの物：g47_scan.py（海底の組の cfg と、層を選んで読む run_ana）、g47_analyze.py、
g47_common.py。書くのは Unity/Build/FLIP47 の中だけ。

試し（どれも S2：勾配 1:10 で水深 1.9 m の平らへ、GN a0/h0 0.6、粒子 0.25 m。runs/ready/S2_s1-10_dp0p25.json を元に）：
  apic      元と同じ（APIC、板は格子 4 個）。zdiag（層ごとの横の流速）を足しただけ。元の S2 との差は、同じ設定の走らせ直しの揺れ
  flip      速度の受け渡しを FLIP に（FLIP46 で y = 0 の壁の偏りが消えた選び。Velocity Smoothing は既定の 0.1）
  apic_nz8  板を格子 8 個（4 m）に。差が壁の近くに寄るか、板の全部に広がるか
  flip_nz8  FLIP で板を格子 8 個に
  apic_jit0 初めの粒子の揺らぎを 0 に（g47_run.py の init_jitter）
  apic_mg   圧力の前処理を多重格子に（IC は向きのある順で解くので）
組を変える時は --scan S5_ledge1-7 など（runs/ready/<組>_dp0p25.json を元に）。

使い方：
  py -3.10 -B x47_zsym.py cfg <試し> [--scan S2_s1-10] [--after 2.5] [--every 3]   → runs/ready/ZS_<組の頭>_<試し>_dp0p25.json
  py -3.10 -B x47_zsym.py ana <run_id> [<run_id> ...]                              → runs/<run_id>/zsym/zsym.json（層ごとの読み、横の流速）
  py -3.10 -B x47_zsym_table.py <run_id> ... [+ <run_id> ...]                      → runs/ZSYM_compare/zsym_table.json・.md・図 2 つ（"+" で組に分ける）
  py -3.10 -B x47_zsym_video.py --out <mp4> [--noprint] [--note 文] <run_id>=<見出し> [<run_id>=<見出し>]   → APIC と FLIP を並べた動画
"""
import os, sys, json, glob, copy, argparse, time
sys.dont_write_bytecode = True
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g47_common as GC

B47 = GC.B47
CMP = B47 + "/runs/ZSYM_compare"
VARIANTS = {
    "apic": dict(),
    "flip": dict(solver=dict(veltransfer="flip")),
    "apic_nz8": dict(nz=8),
    "flip_nz8": dict(nz=8, solver=dict(veltransfer="flip")),
    "apic_jit0": dict(init_jitter=0.0),
    "apic_mg": dict(solver=dict(usemgpreconditioner=1, usepreconditioner=0)),
}


def short(sid):
    return sid.split("_")[0]


def make(variant, scan="S2_s1-10", after=None, every=3, dp=0.25):
    tag = repr(float(dp)).replace(".", "p")
    src = B47 + "/runs/ready/%s_dp%s.json" % (scan, tag)
    c = json.load(open(src, encoding="utf8"))
    v = VARIANTS[variant]
    rid = "ZS_%s_%s_dp%s" % (short(scan), variant, tag)
    c["run_id"] = rid
    c["zsym"] = dict(variant=variant, source_cfg=os.path.relpath(src, B47).replace("\\", "/"), changes=v)
    c["solver"] = dict(c.get("solver") or {}, **(v.get("solver") or {}))
    if v.get("init_jitter") is not None:
        c["init_jitter"] = float(v["init_jitter"])
    nz = int(v.get("nz", 4))
    if nz != 4:
        b = GC.box(dp, c["box"]["x0"], c["box"]["x1"], c["bed"], floor_pad=int(c["box"].get("floor_pad", 2)), nz_cells=nz)
        c["box"] = b
        c["parms"]["Lz"] = b["Lz"]
        c["parms"]["oz"] = b["oz"]
    c["zdiag"] = dict(every=int(every), win_m=30.0, y_min=2.0)
    if after is not None:
        c["stop_touchdown"] = dict(c["stop_touchdown"], after_s=float(after), tip_wait_s=float(after))
    c["sec"] = dict(c["sec"], allz=True)
    c["note"] = "FLIP47 板の層の差の試し %s（%s）。元：%s。変えた所：%s。zdiag（層ごとの横の流速）%d コマごと" % (
        variant, scan, c["zsym"]["source_cfg"], json.dumps(v, ensure_ascii=False) if v else "なし（走らせ直し）", int(every))
    out = B47 + "/runs/ready/%s.json" % rid
    json.dump(c, open(out, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    return out, c


# ====================================================================== 読み
def _scan():
    import g47_scan as SC
    return SC


def layer_rows(rd, nz):
    """層ごとに g47_scan.run_ana（図なし）→ 層ごとの summarize。返り値 {層: 行}。"""
    SC = _scan()
    TG, bands = SC._bands()
    out = {}
    for z in list(range(nz)) + ["mean"]:
        od = rd + "/zsym/z%s" % z
        if os.path.exists(od + "/g47_ana.json"):
            r = json.load(open(od + "/g47_ana.json", encoding="utf8"))
        elif nz == 1:                     # 層ごとの記録のない計算（E1a_short_dp0p25 など）：板の真ん中に近い層（sdf）だけ
            r = SC.run_ana(rd, od, None, nofig=True, label="")
        else:
            r = SC.run_ana(rd, od, z, nofig=True, label="")
        s, byf = SC.summarize(r, TG, bands)
        s["_byf"] = byf
        out[str(z)] = s
        print("  layer", z, "done"); sys.stdout.flush()
    return out


def pick(s, which):
    d = s.get(which) or {}
    r = d.get("ruler") or {}
    return dict(frame=d.get("frame"), t=d.get("t"), chord=r.get("chord"), foot=r.get("foot"), air=r.get("air"), lip=r.get("lip"),
                area=r.get("area"), score3=d.get("score3"), eta=d.get("eta"))


def at(s, f):
    w = s["_byf"].get(f) if f is not None else None
    if not w or not w.get("s52"):
        return None
    m = w["s52"]
    return dict(frame=f, chord=m.get("face_chord_deg_01_05"), foot=m.get("front_x01_rel"), air=m.get("gap_max"), lip=m.get("lip_thick_mid"),
                area=m.get("hood_area"), eta=w.get("eta"))


def zdiag_summary(rd):
    """run_c*.json の info.zdiag を、時刻の並び（crest の層ごとの vz の平均・RMS、upper、壁の層、格子の vel.z の面）にまとめる。"""
    rows = []
    for p in sorted(glob.glob(rd + "/run_c*.json")):
        r = json.load(open(p, encoding="utf8"))
        rows += (r.get("info") or {}).get("zdiag") or []
    rows = sorted({d["frame"]: d for d in rows}.values(), key=lambda d: d["frame"])
    ser = []
    for d in rows:
        e = dict(frame=d["frame"], t=d["t"], xc=d.get("xc"), eta_c=d.get("eta_c"), n_all=d.get("n_all"))
        for key in ("crest", "upper"):
            q = d.get(key) or {}
            e[key] = dict(n=q.get("n"), vz_mean=q.get("vz_mean"), vz_rms=q.get("vz_rms"), z_mean=q.get("z_mean"),
                          frac_gt_0p1=q.get("frac_vz_gt_0p1"),
                          layer_n=[l.get("n") for l in q.get("layers", [])], layer_vz=[l.get("vz_mean") for l in q.get("layers", [])],
                          layer_dz=[l.get("dz_mean") for l in q.get("layers", [])])
        e["wall_lo_vz"] = (d.get("wall_lo") or {}).get("vz_mean"); e["wall_hi_vz"] = (d.get("wall_hi") or {}).get("vz_mean")
        e["grid_vz_faces"] = [[g["k"], g.get("mean"), g.get("rms")] for g in d.get("grid_vz_faces") or []]
        ser.append(e)
    return ser


def zdiag_window(ser, f_lo, f_hi):
    """f_lo〜f_hi のコマの平均：crest の vz の平均・RMS、upper の層ごとの粒子の数の割合と vz の平均、格子の vel.z の面の平均。"""
    w = [e for e in ser if f_lo <= e["frame"] <= f_hi and (e.get("crest") or {}).get("n")]
    if not w:
        return None
    f = lambda xs: float(np.mean([x for x in xs if x is not None])) if any(x is not None for x in xs) else None
    nz = len(w[0]["upper"]["layer_n"])
    up_n = np.array([[x or 0 for x in e["upper"]["layer_n"]] for e in w], float)
    frac = (up_n / np.maximum(up_n.sum(1, keepdims=True), 1)).mean(0)
    gf = {}
    for e in w:
        for k, m, r in e["grid_vz_faces"]:
            if m is not None:
                gf.setdefault(k, []).append((m, r))
    return dict(frames=[w[0]["frame"], w[-1]["frame"]], n_frames=len(w),
                crest_vz_mean=f([e["crest"]["vz_mean"] for e in w]), crest_vz_rms=f([e["crest"]["vz_rms"] for e in w]),
                crest_z_mean=f([e["crest"]["z_mean"] for e in w]),
                upper_vz_mean=f([e["upper"]["vz_mean"] for e in w]), upper_vz_rms=f([e["upper"]["vz_rms"] for e in w]),
                upper_z_mean=f([e["upper"]["z_mean"] for e in w]),
                upper_layer_frac=[float(v) for v in frac],
                upper_layer_vz=[f([e["upper"]["layer_vz"][k] for e in w]) for k in range(nz)],
                wall_lo_vz=f([e["wall_lo_vz"] for e in w]), wall_hi_vz=f([e["wall_hi_vz"] for e in w]),
                grid_vz_face_mean={str(k): float(np.mean([a for a, _ in v])) for k, v in sorted(gf.items())},
                grid_vz_face_rms={str(k): float(np.mean([b for _, b in v])) for k, v in sorted(gf.items())})


def spread(vals):
    v = [x for x in vals if x is not None]
    if not v:
        return None
    m = float(np.mean(v))
    return dict(vals=[None if x is None else round(float(x), 4) for x in vals], min=float(min(v)), max=float(max(v)),
                range=float(max(v) - min(v)), rel=(float(max(v) - min(v)) / abs(m) if m else None), mean=m)


def ana(rid):
    rd = B47 + "/runs/" + rid
    cfg = json.load(open(rd + "/cfg.json", encoding="utf8"))
    nz = int(round(float(cfg["parms"]["Lz"]) / (2.0 * float(cfg["parms"]["dp"]))))
    _sec = sorted(glob.glob(rd + "/sec_c*_b*.npz"))
    if _sec and "sdfz" not in np.load(_sec[-1]).files:
        nz = 1
    t0 = time.time()
    L = layer_rows(rd, nz)
    lay = [L[str(k)] for k in range(nz)]
    # 主の層（z −0.25 m）。板が格子 4 個なら層 1、8 個なら層 3
    imain = max(nz // 2 - 1, 0)
    main = lay[imain]
    out = dict(run_id=rid, variant=(cfg.get("zsym") or {}).get("variant", "scan"), solver=cfg.get("solver"), nz=nz, Lz=cfg["parms"]["Lz"],
               init_jitter=cfg.get("init_jitter"), main_layer=imain, layer_z=([-0.5 * float(cfg["parms"]["Lz"]) + (k + 0.5) * 2.0 * float(cfg["parms"]["dp"]) for k in range(nz)] if nz > 1 else [-0.25]))
    # 層ごとの着水（各層の最初に触れたコマ）の論文の量
    keys = ("frame", "Hb_h0", "xbp_h0", "AO_Hb2", "AJ_Hb2", "W_L", "theta_o_deg", "jet_width_h0", "jet_width_09_h0")
    pt = {k: [((s.get("paper") or {}).get(k)) for s in lay] for k in keys}
    out["touchdown_by_layer"] = pt
    out["touchdown_spread"] = {k: spread(v) for k, v in pt.items() if k != "frame"}
    out["touchdown_mean_field"] = {k: (L["mean"].get("paper") or {}).get(k) for k in keys}
    # 主の層の最も近いコマ（score3 最小）と着水のコマで、層ごとの物差しの値
    fb = (main.get("best3") or {}).get("frame"); ft = (main.get("touchdown") or {}).get("frame")
    out["main_best3"] = pick(main, "best3"); out["main_touchdown"] = pick(main, "touchdown")
    out["main_onset"] = main.get("onset")
    for nm, f in (("at_best3", fb), ("at_touchdown", ft)):
        rows = [at(s, f) for s in lay]
        out[nm] = dict(frame=f, rows=rows, spread={q: spread([(r or {}).get(q) for r in rows]) for q in ("chord", "foot", "air", "lip", "area", "eta")})
    out["own_best3"] = [pick(s, "best3") for s in lay]
    out["mean_field_best3"] = pick(L["mean"], "best3")
    # 横の流速
    ser = zdiag_summary(rd)
    out["zdiag_series"] = ser
    if ser and fb is not None and ft is not None:
        on = (main.get("onset") or {}).get("frame") or (fb - 24)
        out["zdiag_pre"] = zdiag_window(ser, max(1, on - 72), on)            # 巻き始めの前の 3 s
        out["zdiag_break"] = zdiag_window(ser, on, ft)                       # 巻き始め〜着水
        out["zdiag_frame1"] = ser[0] if ser and ser[0]["frame"] <= 3 else None
    # 計算の記録
    runs_ = [json.load(open(p, encoding="utf8")) for p in sorted(glob.glob(rd + "/run_c*.json"))]
    if runs_:
        r0 = runs_[0]
        out["run"] = dict(wall_s=sum(float(r.get("wall_total_s") or 0) for r in runs_), particles_max=max(int(r.get("particles_max") or 0) for r in runs_),
                          substeps=r0.get("substeps_min_max"), stopped=runs_[-1].get("stopped"), f_end_done=runs_[-1].get("f_end_done"),
                          still_offset=r0.get("still_offset"), solver_parms=r0.get("solver_parms"),
                          touchdown_online=(r0.get("info") or {}).get("touchdown_online"),
                          zdiag_errors=(r0.get("info") or {}).get("zdiag_errors"))
    for s in L.values():
        s.pop("_byf", None)
    os.makedirs(rd + "/zsym", exist_ok=True)
    json.dump(out, open(rd + "/zsym/zsym.json", "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    print("ana", rid, "%.0f s" % (time.time() - t0))
    return out


def ana_old(rid):
    """zdiag のない前の計算（S2_s1-10_dp0p25 など）は ana47_z0〜z3 の読みを使う（同じ道具・同じ設定で読んだ物）。"""
    return ana(rid)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["cfg", "ana", "table"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--scan", default="S2_s1-10")
    ap.add_argument("--after", type=float, default=None)
    ap.add_argument("--every", type=int, default=3)
    a = ap.parse_args()
    if a.what == "cfg":
        for v in a.args:
            p, c = make(v, scan=a.scan, after=a.after, every=a.every)
            print(p, "Lz", c["parms"]["Lz"], "solver", c["solver"], "jit", c.get("init_jitter"), "stop", c["stop_touchdown"], "f_end", c["f_end"])
    elif a.what == "ana":
        for rid in a.args:
            ana(rid)
    else:
        import x47_zsym_table as T
        T.table(a.args)
