# -*- coding: utf-8 -*-
"""FLIP49：周期の波の計算（PER49）を読む（py -3.10 -B、numpy・scipy・scikit-image・PIL）。2026-10-15 新しく書いた。
物差しは前の道具をこの起動の中だけ読み替えて使う（ファイルは書き換えない）：
  崩れの見つけ方と k の番号：g47_video.Run.events と g47_periodic_ana.find_events の決まり（前の面の最大の角 thmax ≥ 90° の最初のコマ、頂の筋が
    できてから 1 s 以上、頂 1 m 以上。0.5 s・10 m の内の重なりは 1 つ。前の巻き始めの後 6 s の内に、その 10 m 後ろより前で生まれた筋は着水の後の
    跳ね上がり（数えない）。来た波の崩れ：頂の筋が段の足（PG12s は x 230.25 m）より沖で生まれた物は全部、ほかは巻き始めの所の静かな水深 ≥ 5 m かつ
    頂 ≥ 採った物の中央値 × 0.5 で、採った物のどれとも 0.6 T 以上離れている時だけ）。断面の頂の読みは g46_analyze.centre_events（y = 0 の r2）。
  崩れごとの量：g46_analyze.analyze（g48_analyze と同じ読み替え。海底は g49_common.bed_z）を、その崩れの窓 [t_on − T/2, t_on + T/2] に絞り、
    <記録>/pana/waves/kNN/ に ana.json・RESULT_ja.md を書く（ほかの計算の ana.json・peak.json は書き換えない）。窓の中の主の崩れは
    「巻き始めが見つけた時刻 − 3 s より後の物」の中で g46 と同じ決まり（頂が窓の最大の半分以上、いちばん早い）。前の波の段波を拾わないため。
  横の量：g48_peak_metrics の crest_profile・lateral・curl_series・peel・r4_overhang_width（頂を探す x は 150〜285 m、横の端の帯 |y| 70〜84 m）。
  判定：凍らせた計画（Unity/Build/FLIP49/plan/plan_frozen.json）の P1〜P5（崩れごと）と PER1〜PER5（繰り返し）と H。
  原画に最も近いコマ（赤い枠のため）：判定する崩れごとに、巻き始め〜着水 + 0.5 s（着水がなければ巻き始め + 2.5 s）の真ん中の断面のコマで
    score3（g47_video.score3：前の面の弦・前の足・覆いの面積の原画の帯の外れの和。前の GitHub の動画と同じ式）が最小のコマ。同じなら弦の外れの小さい方、
    次に覆いの高い方。score3 が読めなければ 5 つの点数（score5）の最小、それもなければ最も険しいコマ（src に書く）。
    全体の最良（score3 最小の崩れ）と代表（score3 が中央値の崩れ）も選ぶ → <記録>/pana/best_frames.json（動画の道具 g48_video2.py が読む。この道具は変えない）。
  入口（inlet）：波高計（x 110・128・160 m × y 0.5・80 m の η_top、r6 の gauge）から 0 を下に切る波ごとの H・頂の時刻、速さ（110 → 160 m の頂の時刻）、
    x 128 m の H の CV、跳ね返り Kr（Goda & Suzuki 1976 の 2 点法を 1 次の周波数で、x 110・128 m、k は流れ関数の k。複素振幅を連立で解く）、
    平均の水面の所の 1 周期ごとの平均（r6 の lvl49）と帯の芯の流れ。S0b の門（g49_pcfg.py gain）が読む。
使い方：
  py -3.10 -B g49_periodic_ana.py all <記録> [--all_waves] [--no_shape]      入口・崩れ・崩れごとの量・繰り返し・best_frames.json・PERIODIC_ja.md
  py -3.10 -B g49_periodic_ana.py inlet <記録> [--t0= --t1=]                  入口だけ（pana/inlet.json）
  py -3.10 -B g49_periodic_ana.py s0a <記録>                                   S0a の門（帯の芯の水面・偽の流れ・水の量・静かな水面のずれ → pana/s0a.json）
  py -3.10 -B g49_periodic_ana.py events <記録>                                崩れの表だけ（pana/events.json）
  py -3.10 -B g49_periodic_ana.py sup <記録>                                   補いの読み（2026-10-15 足した。凍らせた崩れの選びの外、判定には使わない）：
        all の後に、events.json の secondary のうち「筋が巻き始めの 2 s 以内に生まれ（追いかけが途中で切れた来た波の続き）、頂 ≥ 採った物の中央値 × 0.5、
        採った物とも互いにも 0.6 T 以上離れている」物を、同じ道具（g46 の analyze・peak_wave・best_frame）で読む → pana/sup/sNN/、pana/sup/sup.json。
        S1（PG12s の軸の板）で、61 s の後の崩れが礁の縁（x 257〜264 m、水深 1.7 m）で巻き、凍らせた選び（筋が段の足より沖で生まれた物、
        ほかは水深 ≥ 5 m）から外れたため【測定】。名前は s1, s2, …（k とは別）
出す物：<記録>/pana/（Unity/Build/FLIP49 の中だけ）
"""
import os, sys, json, math, glob, time

sys.dont_write_bytecode = True
_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip47", r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip46",
           r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip48", _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import numpy as np                  # noqa: E402
import g49_common as GC             # noqa: E402
import g48_analyze as A48           # noqa: E402  読み替えの元（import で A46.Ctx = Ctx48 になる。下で FLIP49 の物に替える）
import g48_peak_metrics as PM       # noqa: E402

A46 = A48.A46
A46.B46 = GC.B49                    # この起動の中だけ：出力の置き場所を FLIP49 に（guard_out・default_out が読む）
_BaseCtx = A48.Ctx48.__bases__[0]   # g46_analyze の元の Ctx
_T_EXPECT = [None]
_ORIG_PICK = A46.pick_main


def jdump(o, p):
    json.dump(A46._clean(o), open(p, "w", encoding="utf8"), ensure_ascii=False, indent=1)


def load_cfg(rd):
    p = os.path.join(rd, "cfg.json")
    return json.load(open(p, encoding="utf8")) if os.path.exists(p) else {}


def p1_max(cfg):
    return float(((cfg.get("case") or {}).get("P1_x_max_m")) or GC.X_P1_MAX)


class Ctx49(_BaseCtx):
    """g46_analyze.Ctx の海底を FLIP49（g49_common.bed_z）にし、静かな水面のずれを周期の波の始め（t 0.5〜1.5 s、x 110〜285 m）で読み、
    崩れを探す x を入口の帯の後ろ〜P1 の上限に絞った物。"""

    def __init__(self, rd, opt=None):
        opt = dict(opt or {})
        cfg = load_cfg(rd)
        self.cfg49 = cfg
        self.bed49 = GC.bed_spec(cfg if cfg.get("bed") else None, parms=(cfg.get("parms") or {}))
        opt.setdefault("bed", "ridge")
        P = cfg.get("parms") or {}
        W = float(P.get("W", GC.W_MAIN))
        opt.setdefault("yfar", str(max(W - 1.0, 0.5)))
        super().__init__(rd, opt)
        self.k = float("nan")
        self.ridge_src = "FLIP49：%s（g49_common.bed_z）" % GC.bed_formula(self.bed49)
        self.notes.insert(0, "FLIP49（g49_periodic_ana.py が g46_analyze.py を読み替えた）：海底 %s、%s。GG06 の表・図 9 の行は当てはまらない" % (
            GC.bed_kind(self.bed49), GC.bed_formula(self.bed49)))
        self.x_dom = (self.x_min, self.x_max)
        self.x_min = max(self.x_min, float(P.get("xg_end", GC.IN_X1)))          # 崩れを探す x：入口の帯の後ろ（+5 m）〜 P1 の上限
        self.x_max = min(self.x_max, p1_max(cfg) + 2.0)

    def bed_z(self, x, y=0.0):
        if not hasattr(self, "bed49"):
            return super().bed_z(x, y)
        return GC.bed_z(x, y, **self.bed49)

    def quiet_x(self, t):
        return float(GC.VOL_X[0])

    def still_offset(self):
        online = None
        for r in self.recs:
            o = (r.get("info") or {}).get("still_offset_online")
            if o and o.get("value") is not None:
                online = dict(value=float(o["value"]), run=int(r.get("f_start") or 0), window=o.get("window", o.get("source")))
                break
        info = dict(online=online)
        if self.cfg.get("still_offset_m") is not None:
            return float(self.cfg["still_offset_m"]), "cfg", info
        vals = []
        for f in self.R1.frames:
            e, m, t = self.R1.get(f)
            if t > self.t_off + 1.5 + 1e-9:
                break
            if t < self.t_off + 0.5 - 1e-9:
                continue
            xs = m["x0"] + m["dx"] * np.arange(m["res"][0])
            sel = (xs >= GC.VOL_X[0]) & (xs <= GC.VOL_X[1])
            vals.append(float(np.nanmedian(e[:, sel])))
        if vals:
            v = float(np.median(vals))
            if online is not None:
                info["online_minus_used_m"] = online["value"] - v
            return v, "t0 + 0.5〜1.5 s の x %g〜%g m の η_top の中央値（周期の波の始め、入口の帯の半余弦の立ち上がりの前）" % GC.VOL_X, info
        if online is not None:
            return online["value"], "計算の中で測った値（run_c%05d）" % online["run"], info
        raise SystemExit("静かな水面のずれが出せない（t 0.5〜1.5 s の記録がない）")


A46.Ctx = Ctx49
A48.Ctx48 = Ctx49                   # g48_peak_metrics.curl_series が A48.Ctx48(rd) を作る（この起動の中だけ）


def pick_main49(ev):
    """主の崩れ：見つけた巻き始め − 3 s より後の巻き始めの中で、g46 と同じ決まり（頂が窓の最大の半分以上、いちばん早い）。"""
    te = _T_EXPECT[0]
    if te is None:
        return _ORIG_PICK(ev)
    ons = [e for e in ev if e["onset"] is not None and e["onset"]["t"] >= te - 3.0]
    others = [e for e in ev if e["onset"] is not None]
    if not ons:
        return None, others
    big = max(e["eta_max"] for e in ev)
    cand = [e for e in ons if e["eta_max"] >= 0.5 * big] or ons
    main = min(cand, key=lambda e: e["onset"]["t"])
    return main, [e for e in others if e is not main]


A46.pick_main = pick_main49


# ====================================================================== 記録（r6）
def load_r6(rd):
    ps = sorted(glob.glob(os.path.join(rd, "r6_c*.npz")), key=lambda q: int(os.path.basename(q)[4:9]))
    if not ps:
        raise SystemExit("r6 の記録がない：%s" % rd)
    best = {}
    names = gxy = vnames = None
    for p in ps:
        d = np.load(p)
        if "lvl49" not in d.files:
            continue
        names = [str(v) for v in d["lvl49_names"]]; gxy = d["gauge_xy"]; vnames = [str(v) for v in d["vol_names"]]
        for i, f in enumerate(d["frames"]):
            best[int(f)] = (float(d["t"][i]), d["lvl49"][i], d["gauge"][i], d["vol"][i], int(d["npts"][i]), int(d["ss_n"][i]), float(d["wall"][i]))
    fr = np.array(sorted(best))
    return dict(frames=fr, t=np.array([best[f][0] for f in fr]), lvl=np.array([best[f][1] for f in fr]), gauge=np.array([best[f][2] for f in fr]),
                vol=np.array([best[f][3] for f in fr]), npts=np.array([best[f][4] for f in fr]), ss_n=np.array([best[f][5] for f in fr]),
                wall=np.array([best[f][6] for f in fr]), names=names, gxy=gxy, vnames=vnames)


def run_recs(rd):
    return [json.load(open(p, encoding="utf8")) for p in sorted(glob.glob(os.path.join(rd, "run_c*.json")))]


def still_off(recs):
    for r in recs:
        o = (r.get("info") or {}).get("still_offset_online")
        if o and o.get("value") is not None:
            return float(o["value"])
    return 0.0


def waves_zero_down(t, e, mean=None):
    """0 を下に切る所で分けた波（g47_periodic_ana.waves_zero_down の写し）。"""
    m = float(np.nanmean(e)) if mean is None else float(mean)
    q = e - m
    ok = np.isfinite(q)
    dn = np.where(ok[:-1] & ok[1:] & (q[:-1] >= 0) & (q[1:] < 0))[0]
    tz = [t[i] + (t[i + 1] - t[i]) * q[i] / (q[i] - q[i + 1]) for i in dn]
    out = []
    for a, b, ta, tb in zip(dn[:-1], dn[1:], tz[:-1], tz[1:]):
        seg = slice(a + 1, b + 1)
        ee = e[seg]; tt = t[seg]
        if len(ee) < 5 or not np.isfinite(ee).all():
            continue
        ic = int(np.argmax(ee)); it = int(np.argmin(ee))
        tc, ec = tt[ic], ee[ic]
        if 0 < ic < len(ee) - 1:
            y0, y1, y2 = ee[ic - 1], ee[ic], ee[ic + 1]
            den = y0 - 2 * y1 + y2
            if den < 0:
                d = 0.5 * (y0 - y2) / den
                tc = tt[ic] + d * (tt[1] - tt[0]); ec = y1 - 0.25 * (y0 - y2) * d
        out.append(dict(t_down0=ta, t_down1=tb, T=tb - ta, t_crest=float(tc), crest=float(ec), trough=float(ee[it]), H=float(ec - ee[it])))
    return out, m


def goda_suzuki(t, e1, e2, x1, x2, k, T):
    """2 点法（1 次の周波数）。η = Re[(a_I e^{ikx} + a_R e^{−ikx}) e^{−iωt}]。Z(x) = (2/N) Σ η e^{iωt}。返り値 (|a_I|, |a_R|, Kr)。"""
    om = 2 * math.pi / T
    ph = np.exp(1j * om * t)
    Z1 = 2.0 * np.mean((e1 - e1.mean()) * ph); Z2 = 2.0 * np.mean((e2 - e2.mean()) * ph)
    A = np.array([[np.exp(1j * k * x1), np.exp(-1j * k * x1)], [np.exp(1j * k * x2), np.exp(-1j * k * x2)]])
    aI, aR = np.linalg.solve(A, np.array([Z1, Z2]))
    return float(abs(aI)), float(abs(aR)), float(abs(aR) / max(abs(aI), 1e-12)), float(abs(math.sin(k * (x2 - x1))))


def period_means(t, v, t0, T, n):
    out = []
    for i in range(n):
        m = (t >= t0 + i * T - 1e-9) & (t < t0 + (i + 1) * T - 1e-9)
        out.append(float(np.nanmean(v[m])) if m.any() and np.isfinite(v[m]).any() else float("nan"))
    return out


def inlet(rd, cfg=None, t0=None, t1=None):
    cfg = cfg or load_cfg(rd)
    recs = run_recs(rd)
    off = still_off(recs)
    R = load_r6(rd)
    sf = cfg.get("sf")
    out = dict(run=os.path.basename(rd.rstrip("/\\")), still_offset_m=off)
    if not sf:
        out["note_ja"] = "流れ関数の波がない（目標 0 の計算）"
    T = float((sf or {}).get("T", GC.T_WAVE)); c_t = float((sf or {}).get("c", 12.39)); k_sf = float((sf or {}).get("k", 2 * math.pi / 148.6))
    t = R["t"]; t_end = float(t[-1])
    P = cfg.get("parms") or {}
    x_p = float(P.get("x_p", GC.X_P)); ramp = float(P.get("ramp_s", GC.RAMP_S))
    gxy = R["gxy"]
    xmax_g = float(max(gxy[:, 0]))
    ta = float(t0) if t0 is not None else ramp + (xmax_g - x_p) / c_t                 # 半余弦の立ち上がりの後、いちばん遠い波高計に満ちた波が着いてから
    nper = int(math.floor(((float(t1) if t1 is not None else t_end) - ta) / T + 1e-9))
    tb = ta + nper * T
    out.update(window_s=[ta, tb], periods=nper, T=T, c_target_mps=c_t, H_target_m=float((sf or {}).get("H", 0.0)))
    sel = (t >= ta - 1e-9) & (t <= tb + 1e-9)
    gauges = {}
    for j, (xg, yg) in enumerate(gxy):
        e = R["gauge"][:, j] - off
        ws, mean = waves_zero_down(t[sel], e[sel])
        ws = [w for w in ws if w["t_down0"] >= ta and w["t_down1"] <= tb]
        Hs = np.array([w["H"] for w in ws]) if ws else np.array([])
        gauges["x%g_y%g" % (xg, yg)] = dict(x=float(xg), y=float(yg), n_waves=len(ws), H_mean=float(Hs.mean()) if len(Hs) else None,
                                            H_cv=float(Hs.std() / Hs.mean()) if len(Hs) >= 2 else None, crest_mean=float(np.mean([w["crest"] for w in ws])) if ws else None,
                                            trough_mean=float(np.mean([w["trough"] for w in ws])) if ws else None, mean_level=mean,
                                            waves=[{k_: round(v, 4) for k_, v in w.items()} for w in ws])
    out["gauges"] = gauges
    row0 = [g for g in gauges.values() if abs(g["y"] - GC.GAUGE_Y[0]) < 1e-6 and g["H_mean"] is not None]
    out["H_mean_m"] = float(np.mean([g["H_mean"] for g in row0])) if row0 else None
    gx = sorted(set(float(v) for v, yv in gxy if abs(yv - GC.GAUGE_Y[0]) < 1e-6))     # 真ん中の行の波高計（既定 110・128・160 m、帯 120 m なら 128・146・160 m）
    key = lambda xv: "x%g_y%g" % (xv, GC.GAUGE_Y[0])
    g2 = gauges.get(key(gx[1])) or {} if len(gx) > 1 else {}
    out["H_cv_x128"] = g2.get("H_cv")
    out["H_cv_gauge_x"] = gx[1] if len(gx) > 1 else None
    # 速さ：最初 → 最後の波高計の頂の時刻（同じ波を順に組む）
    ga = gauges.get(key(gx[0])) or {}; gb = gauges.get(key(gx[-1])) or {}
    dts = []
    for wa in ga.get("waves", []):
        cand = [wb["t_crest"] - wa["t_crest"] for wb in gb.get("waves", []) if 0 < wb["t_crest"] - wa["t_crest"] < 0.6 * T]
        if cand:
            dts.append(min(cand))
    out["c_mps"] = float((gx[-1] - gx[0]) / np.mean(dts)) if dts else None
    out["c_gauges_x"] = [gx[0], gx[-1]]
    out["c_rel"] = (out["c_mps"] / c_t - 1.0) if out["c_mps"] else None
    out["H_rel"] = (out["H_mean_m"] / out["H_target_m"] - 1.0) if (out["H_mean_m"] and out["H_target_m"]) else None
    # 跳ね返り（1・2 番目と 2・3 番目の波高計）
    kr = {}
    for xa, xb in zip(gx[:-1], gx[1:]):
        ja = [j for j, (xg, yg) in enumerate(gxy) if abs(xg - xa) < 1e-6 and abs(yg - GC.GAUGE_Y[0]) < 1e-6]
        jb = [j for j, (xg, yg) in enumerate(gxy) if abs(xg - xb) < 1e-6 and abs(yg - GC.GAUGE_Y[0]) < 1e-6]
        if ja and jb and sel.sum() > 10:
            aI, aR, K, sk = goda_suzuki(t[sel], R["gauge"][sel, ja[0]], R["gauge"][sel, jb[0]], xa, xb, k_sf, T)
            kr["%g_%g" % (xa, xb)] = dict(a_I=aI, a_R=aR, Kr=K, sin_kdl=sk, note_ja="sin(kΔl) が 0 に近いと誤差が大きい")
    out["Kr_pairs"] = kr
    out["Kr"] = (kr.get("%g_%g" % (gx[0], gx[1])) or {}).get("Kr") if len(gx) > 1 else None
    # 平均の水面の所の 1 周期の平均（静かな水面のずれを引く）。始めの半余弦の立ち上がりの後（t ≥ ramp_s）から 1 周期ずつ
    # （帯の芯は波高計への着きを待たなくてよい。S0b の 100 s で 6 周期が入る）
    tl = ramp
    nlev = int(math.floor((t_end - tl) / T + 1e-9))
    lv = {}
    for i, nm in enumerate(R["names"]):
        pm = period_means(t, R["lvl"][:, i] - off, tl, T, nlev)
        lv[nm] = dict(period_means=pm, first=pm[0] if pm else None, last=pm[-1] if pm else None)
    out["levels"] = lv
    out["levels_window_s"] = [tl, tl + nlev * T]
    bc = lv.get("band_core", {}).get("period_means") or []
    out["band_core_drift_6T_m"] = (bc[min(5, len(bc) - 1)] - bc[0]) if len(bc) >= 2 else None
    out["band_core_drift_6T_note_ja"] = "立ち上がりの後の 1 周期目の平均から %d 周期目の平均までの変わり（6 周期が入らなければ入る所まで）" % min(6, len(bc))
    out["band_core_drift_all_m"] = (bc[-1] - bc[0]) if len(bc) >= 2 else None
    out["tags"] = dict(H="測定（FLIP の η_top）", c="測定", Kr="測定から計算（Goda & Suzuki 1976 の 2 点法【文献】）")
    od = guard(os.path.join(rd, "pana"))
    jdump(out, os.path.join(od, "inlet.json"))
    return out


def guard(p):
    return GC.guard_out49(p)


# ====================================================================== S0a の門（静かな水、帯は入れて目標 0）
def load_r2(rd):
    """r2（真ん中の断面）の記録を全部（同じコマは後の起動の物）。返り値 (dict f → (t, sdf, u, w), meta)。"""
    out, meta = {}, None
    for p in sorted(glob.glob(os.path.join(rd, "r2_c*_b*.npz"))):
        d = np.load(p)
        meta = json.loads(str(d["meta"]))
        for i, f in enumerate(d["frames"]):
            out[int(f)] = (float(d["t"][i]), d["sdf"][i].astype(np.float32), d["u"][i].astype(np.float32), d["w"][i].astype(np.float32), meta)
    return out, meta


def s0a(rd, cfg=None):
    """S0a の門（plan_frozen.json の criteria.strip_gates.S0a）。読み方【選び：計画は数の上限だけを決めたので、ここで決めて書く】：
    基準は 1.0〜1.5 s の平均（段 A の V0 と同じ）。帯の芯の水面の変わり：1 s の動く平均の基準からのずれの最大（t ≥ 1.5 s。終わりの 1 s の値も書く）。
    偽の流れ：r2（真ん中の断面）の格子の vel.x・vel.y の、水の中（sdf ≤ −1 格子、海底 + 1 格子より上）の |u|・|w| の最大（t ≥ 1.5 s。99.9 % 点も書く）。
    水の量：r6 の V（コマの終わりの面から測った物）の |V/V0 − 1| の最大（t > 1.5 s）。静かな水面のずれ：計算の中で測った値。"""
    cfg = cfg or load_cfg(rd)
    plan = json.load(open(GC.PLAN_FROZEN, encoding="utf8"))
    gt = plan["criteria"]["strip_gates"]["S0a"]
    recs = run_recs(rd)
    off = still_off(recs)
    R = load_r6(rd)
    t = R["t"]
    ref = (t >= 1.0 - 1e-9) & (t <= 1.5 + 1e-9)
    later = t > 1.5 + 1e-9
    out = dict(run=os.path.basename(rd.rstrip("/\\")), gate=gt, still_offset_m=off, t_end=float(t[-1]))
    ib = R["names"].index("band_core")
    lb = R["lvl"][:, ib]
    lb0 = float(np.nanmean(lb[ref]))
    k = 24
    rm = np.convolve(np.nan_to_num(lb - lb0), np.ones(k) / k, mode="same")
    sel = later & (t >= t[0] + 0.5 * k / 24.0) & (t <= t[-1] - 0.5 * k / 24.0)
    out["band_core"] = dict(ref_m=lb0, max_abs_change_1s_mean_m=float(np.max(np.abs(rm[sel]))) if sel.any() else None,
                            end_change_1s_mean_m=float(np.nanmean(lb[t >= t[-1] - 1.0]) - lb0), raw_max_abs_change_m=float(np.nanmax(np.abs(lb[later] - lb0))))
    vi = {nm: i for i, nm in enumerate(R["vnames"])}
    V = R["vol"][:, vi["V_m3"]]; cum = R["vol"][:, vi["cum_added_m3"]]
    V0 = float(np.nanmean(V[ref]))
    out["volume"] = dict(V0_m3=V0, max_abs_rel=float(np.nanmax(np.abs(V[later] / V0 - 1.0))), end_rel=float(V[-1] / V0 - 1.0),
                         raw_max_abs_rel=float(np.nanmax(np.abs((V[later] - cum[later]) / V0 - 1.0))), cum_added_m3_end=float(cum[-1]))
    r2, m2 = load_r2(rd)
    vox = float(cfg["parms"]["dp"]) * float(cfg["parms"]["gridscale"])
    spec = GC.bed_spec(cfg if cfg.get("bed") else None, parms=cfg.get("parms") or {})
    umax = []; allu = []
    for f in sorted(r2):
        tt, S, U, Wv, m = r2[f]
        if tt <= 1.5 + 1e-9:
            continue
        xs = m["x0"] + m["dx"] * np.arange(S.shape[1]); ys = m["y0"] + m["dy"] * np.arange(S.shape[0])
        water = (S <= -vox) & (ys[:, None] >= GC.bed_z(xs, float(m.get("z", 0.0)), **spec)[None, :] + vox)
        row = dict(frame=f, t=tt)
        for nm, A_ in (("vel.x", U), ("vel.y", Wv)):
            vm = (m.get("vel") or {}).get(nm)
            if vm is None or not np.isfinite(A_).any():
                row[nm] = None; continue
            xu = vm["p0"][0] + vm["d"][0] * np.arange(A_.shape[1]); yu = vm["p0"][1] + vm["d"][1] * np.arange(A_.shape[0])
            ix = np.clip(np.round((xu - m["x0"]) / m["dx"]).astype(int), 0, S.shape[1] - 1)
            jy = np.clip(np.round((yu - m["y0"]) / m["dy"]).astype(int), 0, S.shape[0] - 1)
            msk = water[np.ix_(jy, ix)]
            v = np.abs(A_[msk])
            row[nm] = float(v.max()) if v.size else None
            if v.size:
                allu.append(v)
        umax.append(row)
    big = np.concatenate(allu) if allu else np.array([])
    out["spurious_velocity"] = dict(max_abs_mps=float(big.max()) if big.size else None, p999_abs_mps=float(np.percentile(big, 99.9)) if big.size else None,
                                    frames=len(umax), worst=max(umax, key=lambda r: max(r.get("vel.x") or 0.0, r.get("vel.y") or 0.0)) if umax else None,
                                    section="r2 (centre section), water cells sdf <= -1 vox and >= bed + 1 vox, t > 1.5 s")
    out["pstats"] = [dict(frame=int(f_), **{k_: v_ for k_, v_ in ps.items() if k_ in ("speed_max", "speed_max_at", "n_speed_gt_0p1", "vy_absmean_mid")})
                     for r in recs for f_, ps in sorted(((r.get("info") or {}).get("pstats") or {}).items())]
    J = dict(band_core=bool(out["band_core"]["max_abs_change_1s_mean_m"] is not None and out["band_core"]["max_abs_change_1s_mean_m"] < gt["band_core_change_max_m"]),
             spurious_u=bool(out["spurious_velocity"]["max_abs_mps"] is not None and out["spurious_velocity"]["max_abs_mps"] < gt["spurious_u_max_mps"]),
             volume=bool(out["volume"]["max_abs_rel"] < gt["volume_change_max"]), still_offset=bool(abs(off) < gt["still_offset_max_m"]))
    out["judge"] = J
    out["all_pass"] = bool(all(J.values()))
    out["rule"] = plan["decision_rules"]["after_S0a"]
    out["tags"] = dict(values="測定（FLIP の記録）", reading="選び（この関数の docstring）")
    jdump(out, os.path.join(guard(os.path.join(rd, "pana")), "s0a.json"))
    return out


# ====================================================================== 崩れの見つけ方
def find_breakers(rd, cfg):
    cx = Ctx49(rd, {})
    T = float((cfg.get("sf") or {}).get("T", GC.T_WAVE))
    t_first = cx.R2.get(cx.R2.frames[0])[2]; t_last = cx.R2.get(cx.R2.frames[-1])[2]
    x_lo, x_hi = cx.x_min + 5.0, cx.x_max - 2.0
    ev = A46.centre_events(cx, t_first + 0.25, t_last, x_lo, x_hi)
    cand = []
    for e in ev:
        s = e["series"]
        if len(s) < 3:
            continue
        t0 = s[0][1]
        for f, t, xc, eta, th in s:
            if th is not None and th >= 90.0 and eta >= 1.0 and t - t0 >= 1.0 - 1e-9 and x_lo <= xc <= x_hi:
                cand.append(dict(on_f=int(f), on_t=float(t), on_x=float(xc), on_eta=float(eta), track_start_t=float(t0), track_start_x=float(s[0][2]),
                                 track_end_t=float(s[-1][1]), eta_max=float(e["eta_max"])))
                break
    cand.sort(key=lambda d: d["on_t"])
    merged, after = [], []
    for d in cand:
        if merged and abs(d["on_t"] - merged[-1]["on_t"]) <= 0.5 and abs(d["on_x"] - merged[-1]["on_x"]) <= 10.0:
            continue
        if any(p["on_t"] <= d["track_start_t"] <= p["on_t"] + 6.0 and d["track_start_x"] >= p["on_x"] - 10.0 for p in merged):
            after.append(d); continue
        merged.append(d)
    spec = cx.bed49
    xf = GC.foot_x(spec) or float(spec["x_toe"]) + 50.0
    for d in merged:
        d["depth_on"] = float(-GC.bed_z(d["on_x"], 0.0, **spec))
    off_ = [d for d in merged if d["track_start_x"] < xf]
    med = float(np.median([d["on_eta"] for d in off_])) if off_ else 0.0
    out, sec = [], []
    for d in merged:
        if d["track_start_x"] < xf:
            d["why"] = "offshore_track"; out.append(d)
    for d in merged:
        if d in out:
            continue
        ok = d["depth_on"] >= 5.0 and d["on_eta"] >= 0.5 * med
        if ok and all(abs(d["on_t"] - q["on_t"]) >= 0.6 * T for q in out):
            d["why"] = "depth>=5m_and_eta>=0.5*median"; out.append(d)
        else:
            d["why"] = "near_accepted" if ok else "shallow_or_small"; sec.append(d)
    out.sort(key=lambda q: q["on_t"])
    for i, d in enumerate(out):
        d["k"] = i + 1
        d["judged"] = bool(d["on_t"] >= GC.T_JUDGE)
    res = dict(rule_ja="g47_video の決まり（thmax ≥ 90° の最初のコマ、筋ができて 1 s 以上、頂 1 m 以上、重なりと跳ね上がりを除く）と g47_periodic_ana の来た波の選び"
                       "（筋が段の足 x %.2f m より沖で生まれた物）。判定は真ん中の巻き始め t ≥ %g s" % (xf, GC.T_JUDGE),
               x_window=[x_lo, x_hi], primary_x=xf, events=out, secondary=sec, rebound=after, n_tracks=len(ev), still_offset_m=cx.off)
    return res, cx


# ====================================================================== 崩れごとの量
def best_frame(cx, ana):
    """原画に最も近いコマ（score3 最小）。返り値 dict（frame・t・xc・eta_c・x_c・score3・score5・src・series）。"""
    import g47_video as GV
    on = ana.get("onset")
    if not on:
        st = ana.get("steepest")
        return dict(src="steepest（巻き始めがない）", frame=(st or {}).get("frame"), t=(st or {}).get("t"), xc=(st or {}).get("xc"), eta_c=(st or {}).get("eta_c")) if st else None
    td = ana.get("touchdown") or {}
    f_on = int(on["frame"]); f_end = int(td["frame"]) + 12 if td.get("frame") else f_on + 60
    path = {int(s[0]): s[2] for s in ((ana.get("centre_track") or {}).get("series") or [])}
    xg = float(on["xc"])
    bands = GV.print_ref()["bands"]
    rows = []
    for f in range(f_on, f_end + 1):
        if f not in cx.R2.b:
            continue
        xg = path.get(f, xg)
        try:
            M, X, Z, t = A46.r2_mask(cx, f, xg)
            mm = A46.S52.measure_mask(M, X, Z, flip_extra=dict(Lc=cx.Lc))
            row = A46.DS.pick(mm)
            s3, parts = GV.score3(row)
            s5, _ = GV.TG.score(row, bands)
            rows.append(dict(frame=int(f), t=float(t), xc_track=float(xg), x_c=row.get("x_c"), eta_c=row.get("eta_c"), score3=s3, score5=s5,
                             chord=row.get("face_chord_deg_01_05"), foot=row.get("front_x01_rel"), hood=row.get("hood_area"), lip=row.get("lip_thick_mid"),
                             air=row.get("gap_max"), hood_height_m=row.get("hood_height_m"), chord_miss=(parts or {}).get("face_chord_deg_01_05")))
        except Exception as e:
            rows.append(dict(frame=int(f), error=repr(e)[:160]))
    ok3 = [r for r in rows if r.get("score3") is not None]
    if ok3:
        b = min(ok3, key=lambda r: (r["score3"], r.get("chord_miss") or 0.0, -(r.get("hood_height_m") or 0.0)))
        src = "score3（g47_video.score3：弦・前の足・覆いの面積の原画の帯の外れの和）の最小、巻き始め〜%s" % ("着水 + 0.5 s" if td.get("frame") else "巻き始め + 2.5 s")
    else:
        ok5 = [r for r in rows if r.get("score5") is not None]
        if ok5:
            b = min(ok5, key=lambda r: r["score5"]); src = "score5（5 つの点数）の最小（score3 が読めなかった）"
        else:
            st = ana.get("steepest") or on
            return dict(src="steepest（形の量が読めなかった）", frame=st.get("frame"), t=st.get("t"), xc=st.get("xc"), eta_c=st.get("eta_c"), series=rows)
    return dict(src=src, frame=b["frame"], t=b["t"], xc=b["xc_track"], x_c=b.get("x_c"), eta_c=b.get("eta_c"), score3=b.get("score3"), score5=b.get("score5"),
                ruler={k: b.get(k) for k in ("chord", "foot", "hood", "lip", "air", "hood_height_m")}, dt_after_onset=b["t"] - float(on["t"]),
                window_frames=[f_on, f_end], series=rows)


def peak_wave(rd, cfg, ana, H):
    """1 つの崩れの横の量と判定（g48_peak_metrics の読みを、頂を探す x 150〜P1 の上限・横の端の帯 |y| 70〜84 m・崩れの窓で）。"""
    P = cfg["parms"]; W = float(P["W"])
    off = float(ana.get("still_level_offset_m") or 0.0)
    xs, ys, frames, tt = H["xs"], H["ys"], H["frames"], H["t"]
    x_lo, x_hi = GC.X_CREST_MIN, p1_max(cfg)
    band = GC.SIDE_BAND if W >= 85.0 - 1e-9 else PM.side_band(W)
    key = PM._key_frames(ana)
    on = ana.get("onset") or {}
    Hc = on.get("eta_c")
    res = dict(onset=dict(frame=on.get("frame"), t=on.get("t"), xc=on.get("xc"), eta_c=on.get("eta_c"), thmax=on.get("thmax"), hB=on.get("hB")) if on else None,
               touchdown=dict(frame=(ana.get("touchdown") or {}).get("frame"), t=(ana.get("touchdown") or {}).get("t")) if ana.get("touchdown") else None,
               steepest=ana.get("steepest"), key_frames=key, x_window=[x_lo, x_hi], side_band=list(band), still_offset_m=off, W=W)

    def prof(i):
        c, xc = PM.crest_profile(H["eta"][i], xs, x_lo, x_hi)
        return c - off, xc
    lat_key = {}
    for nm, f in key.items():
        ii = np.where(frames == f)[0]
        if len(ii):
            c, xc = prof(int(ii[0]))
            L_ = PM.lateral(c, ys, c, Hc=Hc, band=band)
            bm = (ys >= band[0]) & (ys <= band[1])
            L_.update(frame=int(f), t=float(tt[ii[0]]), x_crest_centre=float(xc[0]) if np.isfinite(xc[0]) else None,
                      x_side_crest_m=(float(np.nanmedian(xc[bm])) if bm.any() and np.isfinite(xc[bm]).any() else None),
                      profile_c=[round(float(v), 3) for v in c], profile_xc=[round(float(v), 1) if np.isfinite(v) else None for v in xc])
            lat_key[nm] = L_
    res["lateral_key"] = lat_key
    res["ys"] = [float(v) for v in ys]
    strip = W <= 12.0
    if on and not strip:
        cs_ = PM.curl_series(rd, ana)
        res["curl"] = cs_
        rows = {r["frame"]: r for r in cs_.get("rows", [])}

        def w_at(f):
            if f is None:
                return None
            if f in rows:
                return rows[f]["overturned_full_m"]
            k_ = [q for q in rows if abs(q - f) <= 1]
            return rows[k_[0]]["overturned_full_m"] if k_ else None
        sc = ana.get("short_crest") or {}
        w_on = (sc.get("onset") or {}).get("overturned_full_m")
        w_on = w_on if w_on is not None else w_at(key.get("onset"))
        w_mo = w_at(key.get("max_overturn"))
        w_td_raw = (sc.get("touchdown") or {}).get("overturned_full_m")
        w_td_raw = w_td_raw if w_td_raw is not None else w_at(key.get("touchdown"))
        f_td = key.get("touchdown")
        w_td = w_td_raw
        if f_td is not None:
            near_td = [r["overturned_full_m"] for r in rows.values() if r.get("overturned_full_m") is not None and f_td - 6 <= r["frame"] <= f_td]
            if w_td_raw is not None:
                near_td.append(w_td_raw)
            w_td = max(near_td) if near_td else w_td_raw
        res["widths"] = dict(Hc=Hc, onset_m=w_on, max_overturn_m=w_mo, touchdown_m=w_td, touchdown_raw_m=w_td_raw,
                             onset_over_Hc=(w_on / Hc) if (w_on is not None and Hc) else None,
                             max_overturn_over_Hc=(w_mo / Hc) if (w_mo is not None and Hc) else None,
                             touchdown_over_Hc=(w_td / Hc) if (w_td is not None and Hc) else None,
                             touchdown_rule_ja="着水の 0.25 s 前〜着水のコマの thmax ≥ 90° の全幅の最大（g48_peak_metrics と同じ）")
        y4 = 4.0 * Hc if Hc else None
        beyond = [r for r in rows.values() if y4 and any(y >= y4 for y in (r.get("y_over90") or [])) and (f_td is None or r["frame"] <= f_td)]
        res["rows_beyond_4Hc_overturned_before_touchdown"] = bool(beyond)
        res["peel"] = PM.peel(cs_, ana)
    shs = [r for r in ((ana.get("shape") or {}).get("series") or []) if "error" not in r]
    if shs:
        def mx(k):
            v = [r.get(k) for r in shs if isinstance(r.get(k), (int, float))]
            return max(v) if v else None
        res["shape_window"] = dict(frames=[shs[0]["frame"], shs[-1]["frame"]], chord_max=mx("face_chord_deg_01_05"), lip_max=mx("lip_thick_mid"),
                                   hood_max=mx("hood_area"), table=(ana.get("shape") or {}).get("table"))
    return res


def judge_wave(res, ana, tg, cfg, window):
    """凍らせた P1〜P5（崩れごと）。板（W ≤ 12 m）は P2〜P4 を読まない。"""
    J = {}
    on = res.get("onset") or {}
    P1 = tg["P1"]
    J["P1"] = bool(on and on.get("xc") is not None and on["xc"] <= p1_max(cfg) + 1e-9 and window[0] - 1e-9 <= on["t"] <= window[1] + 1e-9)
    sh = res.get("shape_window") or {}
    p5 = tg["P5"]
    J["P5"] = bool(sh.get("chord_max") is not None and sh["chord_max"] >= p5["chord_min_deg"] and (sh.get("lip_max") or 0) >= p5["lip_min"]
                   and (sh.get("hood_max") or 0) >= p5["hood_min"])
    J["P5_chord_good"] = bool(sh.get("chord_max") is not None and p5["chord_good_deg"][0] <= sh["chord_max"] <= p5["chord_good_deg"][1])
    if float(cfg["parms"]["W"]) > 12.0:
        w = res.get("widths") or {}
        J["P2"] = bool(w.get("onset_over_Hc") is not None and w["onset_over_Hc"] <= tg["P2"]["width_over_hc_max"])
        J["P3"] = bool(w.get("max_overturn_over_Hc") is not None and w["max_overturn_over_Hc"] <= tg["P3"]["width_over_hc_max_overturn"]
                       and (w.get("touchdown_over_Hc") is None or w["touchdown_over_Hc"] <= tg["P3"]["width_over_hc_touchdown"]))
        J["P3_touchdown_read"] = w.get("touchdown_over_Hc") is not None
        lo = (res.get("lateral_key") or {}).get("onset") or {}
        J["P4a"] = bool(lo.get("ratio_side") is not None and lo["ratio_side"] >= tg["P4a"]["ratio_min"])
        J["P4a_clear"] = bool(lo.get("ratio_side") is not None and lo["ratio_side"] >= tg["P4a"]["ratio_clear"])
        J["P4b"] = bool(lo.get("ratio_4Hc") is not None and lo["ratio_4Hc"] >= tg["P4b"]["ratio_4hc_min"] and not res.get("rows_beyond_4Hc_overturned_before_touchdown", False))
        J["P1_P4"] = bool(all(J[k] for k in ("P1", "P2", "P3", "P4a", "P4b")))
        J["P1_P5"] = bool(J["P1_P4"] and J["P5"])
    return J


def wave_row(k, ev, ana, res, J, best):
    on = ana.get("onset") or {}
    lo = (res.get("lateral_key") or {}).get("onset") or {}
    w = res.get("widths") or {}
    sh = res.get("shape_window") or {}
    return dict(k=k, found_t=ev["on_t"], found_x=ev["on_x"], t_on=on.get("t"), x_on=on.get("xc"), Hc=on.get("eta_c"), hB=on.get("hB"),
                t_td=(ana.get("touchdown") or {}).get("t"), c0=lo.get("c0"), c_side=lo.get("c_side"), ratio_side=lo.get("ratio_side"), ratio_4Hc=lo.get("ratio_4Hc"),
                half_excess_width_m=lo.get("half_excess_width_m"), w_onset_over_Hc=w.get("onset_over_Hc"), w_maxov_over_Hc=w.get("max_overturn_over_Hc"),
                w_td_over_Hc=w.get("touchdown_over_Hc"), peel_deg=(res.get("peel") or {}).get("peel_angle_deg"),
                chord_max=sh.get("chord_max"), lip_max=sh.get("lip_max"), hood_max=sh.get("hood_max"),
                best_frame=(best or {}).get("frame"), best_t=(best or {}).get("t"), best_score3=(best or {}).get("score3"), judge=J)


# ====================================================================== 繰り返し（PER1〜PER5）
def per_stats(rows, T, plan, inl, R, off):
    pp = plan["criteria"]["periodicity"]
    jr = [r for r in rows if r.get("t_on") is not None]
    out = dict(n_judged=len(rows), n_with_onset=len(jr))
    if not jr:
        out["note_ja"] = "判定する崩れに巻き始めがない"
        return out
    # PER1：P1〜P4 を満たす崩れが 3 つ以上続く
    best_run, cur = [], []
    for r in rows:
        if (r.get("judge") or {}).get("P1_P4"):
            cur.append(r["k"])
            if len(cur) > len(best_run):
                best_run = list(cur)
        else:
            cur = []
    out["PER1_run_k"] = best_run
    out["PER1"] = bool(len(best_run) >= 3)
    use = [r for r in jr if r["k"] in best_run] if best_run else jr
    x = np.array([r["x_on"] for r in use], float); hc = np.array([r["Hc"] for r in use], float); ton = np.array([r["t_on"] for r in use], float)
    kk = np.array([r["k"] for r in use], float)
    med = float(np.median(x))
    out["PER2"] = bool(np.all(np.abs(x - med) <= pp["PER2"]["onset_x_within_m"]))
    out["onset_x"] = dict(median=med, max_dev=float(np.max(np.abs(x - med))), values=[float(v) for v in x])
    cv = float(hc.std() / hc.mean()) if len(hc) >= 2 and hc.mean() > 0 else None
    iv = np.diff(ton) if len(ton) >= 2 else np.array([])
    ph = ton - ton[0] - (kk - kk[0]) * T
    out["Hc"] = dict(mean=float(hc.mean()), cv=cv, values=[float(v) for v in hc])
    out["intervals_s"] = [float(v) for v in iv]
    out["phase_std_over_T"] = float(np.std(ph) / T) if len(ph) >= 2 else None
    out["PER3"] = bool(cv is not None and cv <= pp["PER3"]["Hc_cv_max"] and len(iv) and np.all((iv >= pp["PER3"]["interval_s"][0]) & (iv <= pp["PER3"]["interval_s"][1]))
                       and out["phase_std_over_T"] is not None and out["phase_std_over_T"] <= pp["PER3"]["phase_std_over_T_max"])
    out["PER3_good_cv"] = bool(cv is not None and cv <= pp["PER3"]["Hc_cv_good"])
    if len(kk) >= 2:
        tx = float(np.polyfit(kk, x, 1)[0] * (len(kk) - 1)); th = float(np.polyfit(kk, hc, 1)[0] * (len(kk) - 1) / hc.mean())
    else:
        tx = th = None
    out["trend"] = dict(x_m=tx, Hc_rel=th, max_dev_from_first_m=float(np.max(np.abs(x - x[0]))))
    out["PER4"] = bool(tx is not None and abs(tx) <= pp["PER4"]["trend_x_m_max"] and abs(th) <= pp["PER4"]["trend_Hc_rel_max"]
                       and out["trend"]["max_dev_from_first_m"] <= pp["PER4"]["max_dev_from_first_m"])
    # PER5：入口の H（判定する崩れの 1 周期前の窓）、帯の芯の 1 周期の平均の変わり、平らの平均
    t = R["t"]; gxy = R["gxy"]
    t_r = float(inl.get("window_s", [GC.RAMP_S])[0]) - T                # 波ごとの分けは記録の全部（立ち上がりの後）で一度だけ（短い窓では端の波を落とす）
    wsg = {}
    for j, (xg, yg) in enumerate(gxy):
        if abs(yg - GC.GAUGE_Y[0]) > 1e-6:
            continue
        m = t >= t_r
        wsg[j] = waves_zero_down(t[m], R["gauge"][m, j] - off)[0]
    per = []
    for r in jr:
        a, b = r["t_on"] - T, r["t_on"]
        Hs = []
        for j, ws in wsg.items():
            ws = [w for w in ws if a - 1e-9 <= w["t_crest"] <= b + 1e-9]
            if ws:
                Hs.append(ws[0]["H"])
        lvl = {}
        for i, nm in enumerate(R["names"]):
            m = (t >= a - 1e-9) & (t < b - 1e-9)
            lvl[nm] = float(np.nanmean(R["lvl"][m, i] - off)) if m.any() else None
        per.append(dict(k=r["k"], window=[a, b], H_inlet=float(np.mean(Hs)) if Hs else None, levels=lvl))
    out["per_period"] = per
    Hin = [p["H_inlet"] for p in per if p["H_inlet"] is not None]
    Ht = float(inl.get("H_target_m") or GC.H_WAVE)
    bc = [p["levels"].get("band_core") for p in per if p["levels"].get("band_core") is not None]
    fl = [p["levels"].get("flat") for p in per if p["levels"].get("flat") is not None]
    out["PER5_parts"] = dict(H_inlet_all_within=bool(Hin and all(abs(h / Ht - 1.0) <= pp["PER5"]["H_inlet_rel"] for h in Hin)),
                             band_core_change_m=(bc[-1] - bc[0]) if len(bc) >= 2 else None, free_flat_abs_max_m=max(abs(v) for v in fl) if fl else None)
    out["PER5"] = bool(out["PER5_parts"]["H_inlet_all_within"] and out["PER5_parts"]["band_core_change_m"] is not None
                       and abs(out["PER5_parts"]["band_core_change_m"]) <= pp["PER5"]["band_core_change_m_max"]
                       and out["PER5_parts"]["free_flat_abs_max_m"] is not None and out["PER5_parts"]["free_flat_abs_max_m"] <= pp["PER5"]["free_flat_abs_mean_m_max"])
    out["report_only"] = {nm: [p["levels"].get(nm) for p in per] for nm in ("reef_flat", "lagoon", "side")}
    return out


def health(rd, cfg, R, off, recs):
    P = cfg.get("parms") or {}
    out = {}
    leaks = [l for r in recs for l in ((r.get("info") or {}).get("leak") or [])]
    pmax = max([r.get("particles_max") or 0 for r in recs] or [0])
    if leaks and pmax:
        lm = max(leaks, key=lambda l: l.get("n_below_bed") or 0)
        out["bed_leak_max"] = dict(n=lm.get("n_below_bed"), frame=lm.get("frame"), frac=(lm.get("n_below_bed") or 0) / pmax)
    vi = {nm: i for i, nm in enumerate(R["vnames"])}
    V = R["vol"][:, vi["V_m3"]]; cum = R["vol"][:, vi["cum_added_m3"]]; cap = R["vol"][:, vi["cap"]]
    t = R["t"]
    ref = (t >= 1.0 - 1e-9) & (t <= 1.5 + 1e-9)
    if ref.any() and np.isfinite(V[ref]).any():
        V0 = float(np.nanmean(V[ref]))
        later = t > 1.5
        out["volume"] = dict(V0_m3=V0, corrected_max_rel=float(np.nanmax(np.abs(V[later] / V0 - 1.0))) if later.any() else None,
                             raw_max_rel=float(np.nanmax(np.abs((V[later] - cum[later]) / V0 - 1.0))) if later.any() else None,
                             end_rel=float(V[-1] / V0 - 1.0), cap_frac=float(np.nanmean(cap[later])) if later.any() else None,
                             note_ja="corrected = 測った V、raw = V − 段 A が足した量の和（FLIP がそのままなら残った量）")
        if (cfg.get("drift") or {}).get("stage") == "C":         # 段 C：水の量の直しは切ってある。H は窓 x 110〜285 m の体積の 1 周期の平均で読む（計画）
            Vw = R["vol"][:, vi["Vwin_m3"]]
            Vw0 = float(np.nanmean(Vw[ref]))
            T_ = float((cfg.get("sf") or {}).get("T", GC.T_WAVE))
            t0_ = float(P.get("ramp_s", GC.RAMP_S))
            pm = period_means(t, Vw / Vw0 - 1.0, t0_, T_, int((t[-1] - t0_) // T_))
            out["volume"]["stage_C_interior_period_mean_rel"] = pm
            out["volume"]["corrected_max_rel"] = float(np.nanmax(np.abs(pm))) if pm else None
            out["volume"]["note_ja"] += "。段 C なので判定は窓の体積の 1 周期の平均（stage_C_interior_period_mean_rel）"
    out["still_offset_m"] = off
    out["wall_h"] = sum(float(r.get("wall_launch_s") or r.get("wall_total_s") or 0.0) for r in recs) / 3600.0
    out["particles"] = dict(first=int(R["npts"][0]) if len(R["npts"]) else None, max=int(R["npts"].max()) if len(R["npts"]) else None)
    out["particles"]["growth"] = (out["particles"]["max"] / out["particles"]["first"]) if out["particles"]["first"] else None
    out["mp4"] = sorted(glob.glob(os.path.join(rd, "video", "*.mp4")))
    # 横の偏り（x 110〜160 m の y 0〜10 と 75〜85 の差）の 1 周期ごとの振れ（標準偏差）と、その周期ごとの伸び
    names = R["names"]
    if "asym_centre" in names and "asym_side" in names:
        a = R["lvl"][:, names.index("asym_centre")] - R["lvl"][:, names.index("asym_side")]
        T = float((cfg.get("sf") or {}).get("T", GC.T_WAVE))
        t0 = float(P.get("ramp_s", GC.RAMP_S))
        n = int((t[-1] - t0) // T)
        sd = []
        for i in range(n):
            m = (t >= t0 + i * T) & (t < t0 + (i + 1) * T)
            sd.append(float(np.nanstd(a[m])) if m.any() else float("nan"))
        gr = [sd[i + 1] / sd[i] - 1.0 for i in range(len(sd) - 1) if np.isfinite(sd[i]) and sd[i] > 1e-6]
        out["lateral_asymmetry"] = dict(period_std_m=sd, growth_per_period=gr, max_growth=max(gr) if gr else None)
    tg = json.load(open(GC.PLAN_FROZEN, encoding="utf8"))["criteria"]["health"] if os.path.exists(GC.PLAN_FROZEN) else {}
    J = {}
    if tg:
        J["H_bed_leak"] = bool((out.get("bed_leak_max") or {}).get("frac", 0.0) < tg["bed_leak_frac_max"])
        J["H_volume"] = bool((out.get("volume") or {}).get("corrected_max_rel") is not None and out["volume"]["corrected_max_rel"] < tg["volume_drift_max"])
        J["H_still_offset"] = bool(abs(off) < tg["still_offset_max_m"])
        J["H_mp4"] = bool(out["mp4"])
        if float(P.get("W", 0)) > 12.0 and float(P.get("dp", 0)) == 0.5:
            J["H_wall"] = bool(out["wall_h"] <= tg["wall_max_h_per_coarse_3d_run"])
    out["judge"] = J
    return out


# ====================================================================== 本体
def main_all(rd, opt):
    t_start = time.time()
    rd = os.path.abspath(rd).replace("\\", "/")
    cfg = load_cfg(rd)
    if not cfg:
        raise SystemExit("cfg.json がない：%s" % rd)
    plan = json.load(open(GC.PLAN_FROZEN, encoding="utf8"))
    tg = plan["criteria"]["per_breaker"]
    od = guard(os.path.join(rd, "pana"))
    recs = run_recs(rd)
    T = float((cfg.get("sf") or {}).get("T", GC.T_WAVE))
    inl = inlet(rd, cfg)
    R = load_r6(rd)
    off = still_off(recs)
    evr, cx = find_breakers(rd, cfg)
    jdump(evr, os.path.join(od, "events.json"))
    H = PM.load_hf(rd)
    waves = [e for e in evr["events"] if e["judged"] or "all_waves" in opt]
    rows, best = [], {}
    for e in waves:
        k = e["k"]
        wd = guard(os.path.join(od, "waves", "k%02d" % k))
        win = [e["on_t"] - 0.5 * T, e["on_t"] + 0.5 * T]
        _T_EXPECT[0] = e["on_t"]
        try:
            A46.analyze(rd, {"t0": str(win[0]), "t1": str(win[1]), "out": wd, "no-mesh": "1"})
        finally:
            _T_EXPECT[0] = None
        ana = json.load(open(os.path.join(wd, "ana.json"), encoding="utf8"))
        res = peak_wave(rd, cfg, ana, H)
        J = judge_wave(res, ana, tg, cfg, win)
        b = best_frame(cx, ana) if "no_shape" not in opt else None
        res.update(k=k, window=win, found=e, judge=J, best=b)
        jdump(res, os.path.join(wd, "peak.json"))
        rows.append(wave_row(k, e, ana, res, J, b))
        best[k] = b
        print("k=%d t_on=%s x=%s Hc=%s ratio_side=%s P=%s best=%s" % (k, rows[-1]["t_on"], rows[-1]["x_on"], rows[-1]["Hc"], rows[-1]["ratio_side"],
                                                                    {kk: v for kk, v in J.items() if kk in ("P1", "P2", "P3", "P4a", "P4b", "P5")},
                                                                    (b or {}).get("frame")), flush=True)
    judged_rows = [r for r in rows if r["found_t"] >= GC.T_JUDGE]
    per = per_stats(judged_rows, T, plan, inl, R, off)
    hl = health(rd, cfg, R, off, recs)
    # 原画に最も近いコマ（動画の赤い枠）
    bk = {k: v for k, v in best.items() if v and v.get("score3") is not None and any(r["k"] == k for r in judged_rows)}
    overall = min(bk.items(), key=lambda kv: kv[1]["score3"]) if bk else None
    rep = None
    if bk:
        srt = sorted(bk.items(), key=lambda kv: kv[1]["score3"])
        rep = srt[(len(srt) - 1) // 2]
    bf = dict(run_id=cfg.get("run_id"), rule=plan["criteria"]["best_frame_rule"], plan_sha256=GC.sha256_file(GC.PLAN_FROZEN),
              per_breaker=[dict(k=k, **{kk: v.get(kk) for kk in ("frame", "t", "xc", "x_c", "eta_c", "score3", "score5", "src", "ruler", "dt_after_onset", "window_frames")})
                           for k, v in sorted(best.items()) if v],
              overall_best=dict(k=overall[0], frame=overall[1]["frame"], t=overall[1]["t"], score3=overall[1]["score3"]) if overall else None,
              representative=dict(k=rep[0], frame=rep[1]["frame"], t=rep[1]["t"], score3=rep[1]["score3"], rule="score3 の中央値の崩れ") if rep else None,
              crest_box_hint=dict(section="y = 0（r2）", x_c="x_c（形の量の頂の x、計画の座標）", eta_c="静かな水面からの頂の高さ（m）"),
              note_ja="判定する崩れ（真ん中の巻き始め t ≥ %g s）ごとの原画に最も近いコマ。数は AI の読み、原画らしさは利用者が決める" % GC.T_JUDGE)
    jdump(bf, os.path.join(od, "best_frames.json"))
    verdict = verdict_text(rows, per, cfg)
    out = dict(run_id=cfg.get("run_id"), date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip49/g49_periodic_ana.py", plan=GC.PLAN_FROZEN,
               plan_sha256=GC.sha256_file(GC.PLAN_FROZEN), judged_run=bool((cfg.get("case") or {}).get("judged", True)), T=T, still_offset_m=off,
               inlet={k: v for k, v in inl.items() if k != "gauges"}, events_found=evr["events"], events_secondary=evr["secondary"], events_rebound=evr["rebound"],
               events_rule_ja=evr["rule_ja"], waves=rows, periodicity=per, health=hl, verdict=verdict, best_frames=os.path.join(od, "best_frames.json"),
               breaking_offshore_of_180m=[e for e in evr["events"] + evr["secondary"] if e["on_x"] < 180.0],
               elapsed_s=round(time.time() - t_start, 1))
    jdump(out, os.path.join(od, "periodic_ana.json"))
    open(os.path.join(od, "PERIODIC_ja.md"), "w", encoding="utf8").write(md(out, cfg))
    return out


def main_sup(rd, opt):
    """補いの読み（凍らせた崩れの選びの外、判定には使わない）。docstring の sup を見よ。"""
    t_start = time.time()
    rd = os.path.abspath(rd).replace("\\", "/")
    cfg = load_cfg(rd)
    plan = json.load(open(GC.PLAN_FROZEN, encoding="utf8"))
    tg = plan["criteria"]["per_breaker"]
    ep = os.path.join(rd, "pana", "events.json")
    if not os.path.exists(ep):
        raise SystemExit("先に all（%s がない）" % ep)
    evr = json.load(open(ep, encoding="utf8"))
    T = float((cfg.get("sf") or {}).get("T", GC.T_WAVE))
    acc = list(evr.get("events") or [])
    med = float(np.median([e["on_eta"] for e in acc])) if acc else 0.0
    sup = []
    for d in sorted(evr.get("secondary") or [], key=lambda q: q["on_t"]):
        if d["on_t"] - d["track_start_t"] <= 2.0 + 1e-9 and d["on_eta"] >= 0.5 * med and all(abs(d["on_t"] - q["on_t"]) >= 0.6 * T for q in acc + sup):
            sup.append(dict(d))
    od = guard(os.path.join(rd, "pana", "sup"))
    H = PM.load_hf(rd)
    cx = Ctx49(rd, {})
    rows, best = [], {}
    for i, e in enumerate(sup):
        nm = "s%d" % (i + 1)
        e["k"] = nm; e["judged"] = bool(e["on_t"] >= GC.T_JUDGE); e["why"] = "supplementary: track born <= 2 s before onset (tracker split), not in the frozen event rule"
        wd = guard(os.path.join(od, "s%02d" % (i + 1)))
        win = [e["on_t"] - 0.5 * T, e["on_t"] + 0.5 * T]
        _T_EXPECT[0] = e["on_t"]
        try:
            A46.analyze(rd, {"t0": str(win[0]), "t1": str(win[1]), "out": wd, "no-mesh": "1"})
        finally:
            _T_EXPECT[0] = None
        ana = json.load(open(os.path.join(wd, "ana.json"), encoding="utf8"))
        res = peak_wave(rd, cfg, ana, H)
        J = judge_wave(res, ana, tg, cfg, win)
        bb = best_frame(cx, ana)
        res.update(k=nm, window=win, found=e, judge=J, best=bb)
        jdump(res, os.path.join(wd, "peak.json"))
        rows.append(wave_row(nm, e, ana, res, J, bb))
        best[nm] = bb
        print("%s t_on=%s x=%s Hc=%s P=%s best=%s score3=%s" % (nm, rows[-1]["t_on"], rows[-1]["x_on"], rows[-1]["Hc"],
                                                              {kk: v for kk, v in J.items() if kk in ("P1", "P5")}, (bb or {}).get("frame"), (bb or {}).get("score3")), flush=True)
    out = dict(run_id=cfg.get("run_id"), date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="g49_periodic_ana.py sup", plan_sha256=GC.sha256_file(GC.PLAN_FROZEN),
               rule_ja="補いの読み（凍らせた崩れの選びの外、判定には使わない）：secondary のうち筋が巻き始めの 2 s 以内に生まれ、頂 ≥ 採った物の中央値 × 0.5、"
                       "採った物とも互いにも 0.6 T 以上離れている物", events=sup, waves=rows,
               per_breaker=[dict(k=k, **{kk: v.get(kk) for kk in ("frame", "t", "xc", "x_c", "eta_c", "score3", "score5", "src", "ruler", "dt_after_onset", "window_frames")})
                            for k, v in best.items() if v],
               elapsed_s=round(time.time() - t_start, 1))
    jdump(out, os.path.join(od, "sup.json"))
    return out


def verdict_text(rows, per, cfg):
    if not (cfg.get("case") or {}).get("judged", True):
        return "下見（判定しない）：粒子 %g m。P1〜P5 では判定しない（計画の決まり）" % float(cfg["parms"]["dp"])
    if float(cfg["parms"]["W"]) <= 12.0:
        return "板（2D の基準）：P2〜P4 は読まない。崩れごとの巻き始め・弦・唇・覆いを記録だけ"
    jr = [r for r in rows if r["found_t"] >= GC.T_JUDGE]
    allP = jr and all((r["judge"] or {}).get("P1_P5") for r in jr)
    pers = all(per.get(k) for k in ("PER1", "PER2", "PER3", "PER4", "PER5"))
    if allP and pers:
        return "目標どおり：判定した崩れ全部で P1〜P5、PER1〜PER5 も満たす（AI の読み。原画らしさは利用者が決める）"
    if pers and per.get("PER1_run_k"):
        a, b = per["PER1_run_k"][0], per["PER1_run_k"][-1]
        return "周期の細い頂：崩れ k = %d..%d が凍らせた帯の中で繰り返した（P1〜P4。定常とは言わない）。P5 は崩れごとに表を見る" % (a, b)
    return "一部：崩れごとに表を見る（PER1 %s・PER2 %s・PER3 %s・PER4 %s・PER5 %s）" % tuple(per.get(k) for k in ("PER1", "PER2", "PER3", "PER4", "PER5"))


def _n(v, f="%.2f"):
    return "—" if v is None else (f % v)


def md(o, cfg):
    L = ["# FLIP49 周期の波の読み：%s" % o["run_id"], "",
         "> g49_periodic_ana.py（%s）。凍らせた計画 plan_frozen.json（SHA-256 %s…）の決まりで読んだ。数は AI の読み（自己評価）。原画らしさは利用者が決める。" % (o["date"], o["plan_sha256"][:16]), "",
         "**判定**：%s" % o["verdict"], ""]
    i = o["inlet"]
    L += ["## 入口（x 110〜160 m）", "",
          "- 波高 H %s m（目標 %s m、%s）、速さ %s m/s（目標 %s、%s）、x 128 m の H の CV %s、Kr（110・128 m）%s、帯の芯の 1 周期の平均の変わり %s m【測定】" % (
              _n(i.get("H_mean_m")), _n(i.get("H_target_m")), _n(100 * i["H_rel"], "%+.1f %%") if i.get("H_rel") is not None else "—", _n(i.get("c_mps")),
              _n(i.get("c_target_mps")), _n(100 * i["c_rel"], "%+.1f %%") if i.get("c_rel") is not None else "—", _n(i.get("H_cv_x128"), "%.3f"), _n(i.get("Kr"), "%.3f"),
              _n(i.get("band_core_drift_all_m"), "%+.3f")), ""]
    L += ["## 崩れごと（判定は真ん中の巻き始め t ≥ %g s）" % GC.T_JUDGE, "",
          "| k | 巻き始め t (s) | x (m) | Hc (m) | c0/c_side | c0/c(4Hc) | 巻き幅/Hc 始め・最大・着水 | 弦 最大 (°) | 唇 | 覆い | P1 | P2 | P3 | P4a | P4b | P5 | 原画に最も近いコマ（score3） |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in o["waves"]:
        J = r["judge"] or {}
        yn = lambda k: ("○" if J.get(k) else "×") if k in J else "—"
        L.append("| %d | %s | %s | %s | %s | %s | %s・%s・%s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s（%s） |" % (
            r["k"], _n(r["t_on"]), _n(r["x_on"], "%.1f"), _n(r["Hc"]), _n(r["ratio_side"]), _n(r["ratio_4Hc"]), _n(r["w_onset_over_Hc"]), _n(r["w_maxov_over_Hc"]),
            _n(r["w_td_over_Hc"]), _n(r["chord_max"], "%.1f"), _n(r["lip_max"]), _n(r["hood_max"], "%.3f"), yn("P1"), yn("P2"), yn("P3"), yn("P4a"), yn("P4b"), yn("P5"),
            r.get("best_frame") or "—", _n(r.get("best_score3"))))
    p = o["periodicity"]
    L += ["", "## 繰り返し（PER）", "",
          "- PER1 %s（P1〜P4 が続いた k：%s）・PER2 %s（巻き始めの x の中央値からの最大のずれ %s m）・PER3 %s（Hc の CV %s、間隔 %s s、位相のばらつき ÷ T %s）・"
          "PER4 %s（流れ x %s m、Hc %s）・PER5 %s（%s）" % (
              p.get("PER1"), p.get("PER1_run_k"), p.get("PER2"), _n((p.get("onset_x") or {}).get("max_dev"), "%.1f"), p.get("PER3"), _n((p.get("Hc") or {}).get("cv"), "%.3f"),
              [round(v, 2) for v in p.get("intervals_s", [])], _n(p.get("phase_std_over_T"), "%.3f"), p.get("PER4"), _n((p.get("trend") or {}).get("x_m"), "%+.1f"),
              _n((p.get("trend") or {}).get("Hc_rel"), "%+.3f"), p.get("PER5"), p.get("PER5_parts")), ""]
    h = o["health"]
    L += ["## 健康（H）", "", "- %s" % json.dumps({k: v for k, v in h.items() if k != "lateral_asymmetry"}, ensure_ascii=False, default=str)[:1500], ""]
    if o["breaking_offshore_of_180m"]:
        L += ["- ⚠ x < 180 m で崩れた：%s" % [(round(e["on_t"], 2), round(e["on_x"], 1)) for e in o["breaking_offshore_of_180m"]], ""]
    L += ["原画に最も近いコマの表（動画の赤い枠）：pana/best_frames.json。崩れごとの ana.json・peak.json：pana/waves/kNN/。"]
    return "\n".join(L) + "\n"


def parse(argv):
    opt = {a[2:].split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else "1") for a in argv if a.startswith("--")}
    pos = [a for a in argv if not a.startswith("--")]
    return pos, opt


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    pos, opt = parse(sys.argv[1:])
    if len(pos) < 2:
        print(__doc__); sys.exit(1)
    rd = os.path.abspath(pos[1])
    if pos[0] == "all":
        o = main_all(rd, opt)
        print(o["verdict"]); print(json.dumps(A46._clean(o["periodicity"]), ensure_ascii=False)[:2000])
    elif pos[0] == "inlet":
        o = inlet(rd, None, opt.get("t0"), opt.get("t1"))
        print(json.dumps(A46._clean({k: v for k, v in o.items() if k != "gauges"}), ensure_ascii=False, indent=1)[:3000])
    elif pos[0] == "s0a":
        o = s0a(rd)
        print(json.dumps(A46._clean({k: v for k, v in o.items() if k not in ("pstats",)}), ensure_ascii=False, indent=1)[:3000])
    elif pos[0] == "sup":
        o = main_sup(rd, opt)
        print(json.dumps(A46._clean([{k: w.get(k) for k in ("k", "t_on", "x_on", "Hc", "chord_max", "lip_max", "hood_max", "best_t", "best_score3")} for w in o["waves"]]),
                         ensure_ascii=False, indent=1))
    elif pos[0] == "events":
        evr, _ = find_breakers(rd, load_cfg(rd))
        jdump(evr, os.path.join(guard(os.path.join(rd, "pana")), "events.json"))
        for e in evr["events"]:
            print("k=%d t=%.2f x=%.1f eta=%.2f start_x=%.1f judged=%s %s" % (e["k"], e["on_t"], e["on_x"], e["on_eta"], e["track_start_x"], e["judged"], e["why"]))
    else:
        print(__doc__); sys.exit(1)
