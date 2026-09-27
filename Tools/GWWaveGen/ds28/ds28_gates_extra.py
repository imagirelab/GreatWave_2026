# -*- coding: utf-8 -*-
"""設計28：設計27 の関門 P1〜P16（ds27_gates.py、変えずに import）に足す関門 P17〜P19 の検査器。P20 は ds28_p20.py。

関門（しきい値は設計28 の作業指示。読み方は READINGS_JA に書く）：
  P17 本体の水：前面が鉛直になってから（ds27_gates の噴流の始まり＝φ ≥ 90° を初めて満たす時刻）t* まで、主役波の本体
      （列 j_B〜j_E。周りの海・平らな縁の外。ds_sea_calm_painting の区間も除かない）の行ごとの符号付きの断面積の変化
      max|A(τ) − A(始まり)| / A_pos(t*) が、主断面と峰の行で ≤ 0.10、巻きの行すべてで ≤ 0.15。
  P18 内壁と唇は流れとともに前へだけ進む：巻きの行ごとに、噴流の始まりの後、波の枠（パッケージの局所座標）で、内壁の 0.3H・0.5H の点
      （前面を最後に下へ横切る点）と唇先が後ろへ戻る量（それまでの最大 − 今）≤ 0.3 m。
  P19 段階 b の頂の角：峰の行（c = +3.85 m）で、ds27_gates の P15 が段階 b を初めて満たした時刻の頂の角 θc ≤ 110°（写真 b の尖った塔）。
使い方（リポジトリの根で。ds28_gates.py が呼ぶ）：
  py -3.10 -B Tools/GWWaveGen/ds28/ds28_gates_extra.py --package Unity/Build/Design/28/art_on --gates <ds27_gates の出力.json> --out <出力.json>
numpy だけを使う。パッケージは ds27_gates と同じ読み方（Hermite・量子化）で読む。
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DS27 = os.path.abspath(os.path.join(HERE, "..", "ds27"))
sys.path.insert(0, DS27)
import ds27_gates as DG  # noqa: E402

REPO = DG.REPO
fnum = DG.fnum
rel = DG.rel
TH = dict(P17_main_peak=0.10, P17_all=0.15, P18_retreat_m=0.3, P19_theta_deg=110.0)
HZ = 60
READINGS_JA = [
    "本体（P17）：パッケージの行の断面の列 j_B（18）〜j_E（394）を、両端を y = 0 へ下ろして閉じた符号付きの断面積（shoelace。張り出しの下の空気は引かれる）。"
    "巻きの行（H ≥ 3 m）では、この列に周りの海（搬送波・うねり）は乗らない（生成器の約束：本体の重み 1）。窓（225 m）や周りの海の標本は使わない。"
    "ds_sea_calm_painting の区間（τ > −2.0 s）も除かない。分母は t* の本体の y > 0 の部分の面積。",
    "噴流の始まり：P17 は作業指示どおり『前面が鉛直になった時刻』＝ ds27_gates と同じ φ ≥ 90° を初めて満たす時刻（60 Hz）。"
    "P18 の判定は ds26_conditions.json の噴流の始まり（行の唇先の放出、T_row = max(2.4 − |c − 3.85|/20, 1.2) s 前。設計26 §1.3 の定義）から。"
    "前面が鉛直になった時刻からの値も記録する（この生成器では、始まりの約 0.3 s 前から前面が鉛直を過ぎて内壁がえぐれるので、判定の起点で値が大きく違う）。",
    "P18 の点：波の枠（パッケージの局所座標、ワールド − O(τ)）の断面の a。内壁は、頂（ds27_gates の本体の頂）の列から j_E までの前の部分を、0.3H・0.5H の高さで"
    "最後に下へ横切る点（H はその時刻の頂の高さ）。唇先は K* の唇先の列（ds27_gates の jtip）の点。戻りはその時刻までの最大からの差の最大。",
    "P19：θc は ds27_gates.row_metrics と同じ（頂から 0.9H の高さの前後の点への弦のなす角）。段階 b の時刻は、ds27_gates の出力の P15 の峰の行の b。表の時刻（設計26 §3.1 の −3.4 s）の値も記録する。",
]


def front_cross(A, Y, cj, H, f, jE):
    """行ごとに、頂の列 cj から j_E までで高さ f·H を最後に下へ横切る点の a（なければ nan）。A, Y (nr, nu)。"""
    nr, nu = A.shape
    y3 = f * H
    cols = np.arange(nu - 1)[None, :]
    m = (cols >= cj[:, None]) & (cols < jE) & (Y[:, :-1] > y3[:, None]) & (Y[:, 1:] <= y3[:, None])
    has = m.any(1)
    k = (nu - 2) - np.argmax(m[:, ::-1], 1)
    rr = np.arange(nr)
    t = (Y[rr, k] - y3) / np.maximum(Y[rr, k] - Y[rr, k + 1], 1e-12)
    return np.where(has, A[rr, k] + t * (A[rr, k + 1] - A[rr, k]), np.nan)


def body_area(A, Y, jB, jE):
    a = A[:, jB:jE + 1]
    y = Y[:, jB:jE + 1]
    an = -0.5 * (a[:, :-1] * y[:, 1:] - a[:, 1:] * y[:, :-1]).sum(1)
    yp = np.clip(y, 0.0, None)
    ap = -0.5 * (a[:, :-1] * yp[:, 1:] - a[:, 1:] * yp[:, :-1]).sum(1)
    return an, ap


def retreat(v):
    v = np.asarray(v, float)
    ok = np.isfinite(v)
    if not ok.any():
        return None, None
    m = np.fmax.accumulate(np.where(ok, v, -np.inf))
    d = np.where(ok, m - v, 0.0)
    k = int(np.argmax(d))
    return float(d[k]), k


def calib_onset(ks, cond):
    pr = ks.peak_row
    return np.array([max(abs(cond["tau0"]) - abs(ks.c[r] - ks.c[pr]) / cond["peel"], cond["floor"]) for r in range(ks.nv)])


def series(ks, pk, t_start=-4.6, log=print):
    """60 Hz の行ごとの量（全行）。"""
    tau0 = max(float(pk.knots[0]), t_start)
    K = int(math.floor(-tau0 * HZ + 1e-6))
    taus = -np.arange(K, -1, -1) / HZ
    jB, jE = 18, ks.j_E
    nt, nv = len(taus), ks.nv
    out = {k: np.full((nt, nv), np.nan) for k in ("A", "Apos", "phi", "theta", "H", "w3", "w5", "tip", "crest")}
    rows = np.arange(nv)
    tipc = np.where(ks.tip_col >= 0, ks.tip_col, 0)
    t0 = time.time()
    for k, tau in enumerate(taus):
        Xl = pk.local(float(tau)) + ks.O          # 波の枠（局所）を K* の断面の座標へ
        A, Y, _ = ks.section(Xl)
        an, ap = body_area(A, Y, jB, jE)
        rm = DG.row_metrics(A, Y, ks.crest_hi, jE)
        out["A"][k], out["Apos"][k] = an, ap
        out["phi"][k], out["theta"][k], out["H"][k], out["crest"][k] = rm["phi"], rm["theta"], rm["H"], rm["ca"]
        out["w3"][k] = front_cross(A, Y, rm["cj"], rm["H"], 0.3, jE)
        out["w5"][k] = front_cross(A, Y, rm["cj"], rm["H"], 0.5, jE)
        out["tip"][k] = A[rows, tipc]
        if k % 120 == 0:
            log("  [extra] frame %d/%d τ=%.2f (%.0f s)" % (k, nt, tau, time.time() - t0))
    out["taus"] = taus
    return out


def evaluate(ks, pk, S, gates, cond):
    taus = S["taus"]
    rows_k = ks.curled_idx
    mr, pr = ks.main_row, ks.peak_row
    named = {mr: "主断面", pr: "峰で最も高い巻きの行"}
    Tc = calib_onset(ks, cond)
    res = {}
    # ---- P17
    per = {}
    worst = (0.0, None)
    for r in rows_k:
        k = np.nonzero(np.nan_to_num(S["phi"][:, r], nan=0.0) >= 90.0)[0]
        if not len(k):
            per[int(r)] = None
            continue
        k0 = int(k[0])
        den = max(S["Apos"][-1, r], 1e-9)
        d = np.abs(S["A"][k0:, r] - S["A"][k0, r]) / den
        j = int(np.argmax(d))
        kc = int(np.argmin(np.abs(taus + Tc[r])))
        pre_b = int(np.argmin(np.abs(taus + 3.4)))
        per[int(r)] = dict(onset_tau=fnum(taus[k0], 3), max_change_frac=fnum(d[j], 4), at_tau=fnum(taus[k0 + j], 3),
                           A_onset_m2=fnum(S["A"][k0, r], 1), A_tstar_m2=fnum(S["A"][-1, r], 1),
                           A_min_after_m2=fnum(float(S["A"][k0:, r].min()), 1), A_max_after_m2=fnum(float(S["A"][k0:, r].max()), 1),
                           from_jet_onset_frac=fnum(float(np.abs(S["A"][kc:, r] - S["A"][kc, r]).max() / den), 4),
                           before_onset_from_tau_m3p4_range_frac=fnum(float((S["A"][pre_b:k0 + 1, r].max() - S["A"][pre_b:k0 + 1, r].min()) / den), 4) if k0 > pre_b else None)
        if d[j] > worst[0]:
            worst = (float(d[j]), int(r))
    vm = per[int(mr)]["max_change_frac"] if per.get(int(mr)) else None
    vp = per[int(pr)]["max_change_frac"] if per.get(int(pr)) else None
    ok = (vm is not None and vp is not None and vm <= TH["P17_main_peak"] and vp <= TH["P17_main_peak"] and worst[0] <= TH["P17_all"]
          and all(v is not None for v in per.values()))
    over = [r for r, v in per.items() if v and v["max_change_frac"] > TH["P17_all"]]
    res["P17"] = dict(name_ja="本体の水（前面が鉛直 → t* の本体の断面積の変化 / t* の A_pos。本体の列だけ、周りの海を静める区間も除かない）",
                      value={named[mr]: vm, named[pr]: vp, "巻きの行の最大": fnum(worst[0], 4)},
                      threshold="主断面・峰の行 ≤ %.2f、巻きの行すべて ≤ %.2f" % (TH["P17_main_peak"], TH["P17_all"]), pass_=bool(ok),
                      detail=dict(worst_row=worst[1], rows_over_all_threshold=over,
                                  main_row=per.get(int(mr)), peak_row=per.get(int(pr)),
                                  from_jet_onset_max_frac=fnum(max(v["from_jet_onset_frac"] for v in per.values() if v), 4),
                                  before_onset_range_max_frac=fnum(max((v["before_onset_from_tau_m3p4_range_frac"] or 0) for v in per.values() if v), 4),
                                  per_row_every_8={str(r): per[int(r)] for r in rows_k[::8]},
                                  note_ja="before_onset_range_max_frac は記録：τ −3.4 s（段階 b）から前面が鉛直になるまでの本体の断面積の幅（最大 − 最小）/ t* の A_pos"))
    # ---- P18
    def p18(start_idx_fn, label):
        worst_ = {"w3": (0.0, None, None), "w5": (0.0, None, None), "tip": (0.0, None, None)}
        rows_over = []
        rowd = {}
        for r in rows_k:
            k0 = start_idx_fn(r)
            if k0 is None:
                continue
            ent = {}
            bad = False
            for key in ("w3", "w5", "tip"):
                v, j = retreat(S[key][k0:, r])
                ent[key] = (fnum(v, 3), fnum(taus[k0 + j], 3) if j is not None else None)
                if v is not None and v > worst_[key][0]:
                    worst_[key] = (v, int(r), float(taus[k0 + j]))
                if v is not None and v > TH["P18_retreat_m"]:
                    bad = True
            if bad:
                rows_over.append(int(r))
            rowd[int(r)] = ent
        return worst_, rows_over, rowd

    def k_cal(r):
        return int(np.argmin(np.abs(taus + Tc[r])))

    def k_meas(r):
        k = np.nonzero(np.nan_to_num(S["phi"][:, r], nan=0.0) >= 90.0)[0]
        return int(k[0]) if len(k) else None

    wc, oc, rc = p18(k_cal, "cal")
    wm, om, rm_ = p18(k_meas, "meas")
    val = max(v[0] for v in wc.values())
    res["P18"] = dict(name_ja="内壁と唇は流れとともに前へだけ進む（噴流の始まりの後、波の枠で、内壁の 0.3H・0.5H の点と唇先の後ろへの戻り）",
                      value=fnum(val, 3), threshold="≤ %.1f m（巻きの行すべて、3 つの点）" % TH["P18_retreat_m"], pass_=bool(val <= TH["P18_retreat_m"]),
                      detail=dict(start_ja="判定の起点：ds26_conditions.json の噴流の始まり（行の唇先の放出、τ = −T_row）",
                                  worst={k: dict(retreat_m=fnum(v[0], 3), row=v[1], tau=fnum(v[2], 3)) for k, v in wc.items()},
                                  rows_over=oc,
                                  main_row=rc.get(int(mr)), peak_row=rc.get(int(pr)),
                                  record_from_face_vertical=dict(
                                      ja="記録：起点を前面が鉛直になった時刻（φ ≥ 90° を初めて満たす時刻、ds27_gates の噴流の始まり）にした値",
                                      worst={k: dict(retreat_m=fnum(v[0], 3), row=v[1], tau=fnum(v[2], 3)) for k, v in wm.items()},
                                      rows_over=len(om), main_row=rm_.get(int(mr)), peak_row=rm_.get(int(pr)))))
    # ---- P19
    p15 = gates.get("P15", {}).get("detail", {})
    det = {}
    ok = True
    val = None
    for r in (pr, mr):
        d = p15.get(named[r], {})
        tb = (d.get("tau") or {}).get("b")
        tab_b = (d.get("table_tau") or {}).get("b")
        th_b = float(np.interp(tb, taus, S["theta"][:, r])) if tb is not None else None
        th_t = float(np.interp(tab_b, taus, S["theta"][:, r])) if tab_b is not None else None
        det[named[r]] = dict(b_tau=tb, theta_c_at_b_deg=fnum(th_b, 1), table_b_tau=tab_b, theta_c_at_table_b_deg=fnum(th_t, 1),
                             theta_c_min_between_a_and_c_deg=fnum(float(np.nanmin(S["theta"][(taus >= (d.get("tau") or {}).get("a", -9)) & (taus <= (d.get("tau") or {}).get("c", 0)), r])), 1)
                             if (d.get("tau") or {}).get("a") is not None and (d.get("tau") or {}).get("c") is not None else None)
        if r == pr:
            val = th_b
            ok = th_b is not None and th_b <= TH["P19_theta_deg"]
    res["P19"] = dict(name_ja="段階 b の頂の角（峰の行、P15 の b の時刻の θc。写真 b の尖った塔）", value=fnum(val, 1),
                      threshold="≤ %.0f°（峰の行）。主断面は記録" % TH["P19_theta_deg"], pass_=bool(ok), detail=det)
    return res


def run(package, gates_path, out, log=print):
    t0 = time.time()
    ks = DG.KStar()
    pk = DG.Package(package, ks)
    cond, cond_src = DG.load_conditions()
    G = json.load(open(gates_path, encoding="utf-8"))
    S = series(ks, pk, log=log)
    res = evaluate(ks, pk, S, G["gates"], cond)
    for g in res.values():
        g["pass"] = g.pop("pass_")
    rep = dict(schema="GreatWave.DS28.gates_extra/1", number="設計28", tool=rel(os.path.abspath(__file__)),
               package=dict(dir=rel(pk.dir), version=pk.version, pos_sha256=pk.pos_sha, layers=pk.L),
               gates_source=dict(path=rel(gates_path)), thresholds=TH, readings_ja=READINGS_JA, gates=res,
               series_every_0p1s={"taus": [fnum(t, 3) for t in S["taus"][::6]],
                                  **{"%s_%s" % (k, r): [fnum(v, 3) for v in S[k][::6, r]] for k in ("A", "w3", "w5", "tip", "theta", "H", "crest")
                                     for r in (ks.main_row, ks.peak_row)}},
               runtime_s=round(time.time() - t0, 1))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1, default=lambda o: fnum(o) if isinstance(o, (np.floating, np.integer)) else str(o))
    log("[ds28_gates_extra] P17 %s・P18 %s・P19 %s（%.0f s）→ %s" % (res["P17"]["pass"], res["P18"]["pass"], res["P19"]["pass"], rep["runtime_s"], out))
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--gates", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    run(a.package, a.gates, a.out)


if __name__ == "__main__":
    main()
