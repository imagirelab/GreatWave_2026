# -*- coding: utf-8 -*-
"""FLIP49：PROBE025（粒子 0.25 m の主メモリー・時間の短い試し）の記録を読み、測った数と、半幅 85 m の粒子 0.25 m の計算の見込みを書く（py -3.10、numpy）。
2026-10-16 新しく書いた。probe, not a result（波の形の結果ではない。細かい粒子の本番は指導教員の返事の後：Q57・Q64）。
  py -3.10 -B g49_probe_ana.py <probe の記録> [<もう 1 つの幅の probe の記録> …]
出力：<1 つ目の probe の記録>/probe_summary.json と画面の表。数の印：【測定】この probe と DA3 の記録、【計算】、【推測】。
見込みの考え（どれも【推測】）：
  解く時間：DA3（粒子 0.5 m）のコマごとの解く時間 × (0.25 m の probe と DA3 の静かな間の「百万粒子・1 小段あたりの秒」の比) × 粒子の比 8.04
            × 小段の比（0.25 m は格子が半分なので同じ流速で CFL が 2 倍：下 = DA3 で小段 1 のコマは 1 のまま・2 以上は 1.5 倍、上 = 2 倍。
            probe で測った 0〜4 s は測った値）。上には幅の効き（圧力の解き方の繰り返しが増える）として 1.25 倍を掛ける。
  記録：R5（面）は probe の 1 コマの秒 × 頂点の数の比（下）か粒子の数の比（上）。軽い記録・場の読みは格子の数の比。
  29 分の起動の区切り：起動ごとの読み込み（probe の 2 回目の起動で測った）と、途中保存の間隔（chain の決まり：load + 1.5 × 間隔 × 1 コマ ≤ 0.92 × 1740 s）
            から、途中保存の後に計算して捨てるコマを数える。
            2026-10-16 確かめで chain_sim を足した：平均の秒で間隔を 1 つ決めると、崩れの間（1 コマが長い）に捨てるコマを少なく見る
            （0〜78 s の上で 28 h 対 34 h）。chain_sim は起動ごとに g49_chain の決まりをなぞる。見込みの時間は chain_sim の方を使う。
            G: の予算は 10 進の GB（GC.free_gb と同じ）に直した（前は GiB の 324 と比べていた）。
  主メモリー：probe の約束の量（private）の最大を粒子の数の 1 次で延ばす（幅の違う probe が 2 つあれば傾きをそこから、無ければ DA3 と
            準 2D の板の RSS から）。重い記録と崩れの間の増えは、probe の重い記録の増え × 面の頂点の比（下）か DA3 の増え × 8（上）。
"""
import os, sys, json, glob, math, re
import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import g49_common as GC     # noqa: E402

DA3 = GC.B49 + "/runs/DA3_SC37y30_T12H7p5_dp0p5"
N_FULL0 = 43732762            # 半幅 85 m・粒子 0.25 m の初めの粒子【計算】count_particles
N_DA3_0 = 5439373             # DA3 の初めの粒子【計算】
VOX_FULL = 884 * 170 * 86     # 半幅 85 m・格子 0.5 m の格子の数【計算】
WL = 1740.0
FPS = 24.0
STRIP_RSS = (0.23e6, 4.7)     # 準 2D の板（S0a、粒子 0.5 m）の粒子と最大 RSS（GB）【測定】strips/runs.jsonl


def load_run(rd):
    runs = []
    for p in sorted(glob.glob(os.path.join(rd, "run_c*.json"))):
        r = json.load(open(p, encoding="utf8"))
        c = os.path.basename(p)[5:10]
        d = np.load(os.path.join(rd, "r6_c%s.npz" % c))
        runs.append(dict(rec=r, f=d["frames"], solve=d["wall"], surf=d["surf_s"], n=d["npts"], sub=d["ss_n"], rss=d["rss"]))
    mw = []
    p = os.path.join(rd, "memwatch_summary.jsonl")
    if os.path.exists(p):
        mw = [json.loads(l) for l in open(p, encoding="utf8") if l.strip()]
    cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    return runs, mw, cfg


def mem_rows(rd):
    """memwatch.csv の行（起動ごとに分けない）：時刻・約束の余り・主メモリーの空き・hython の private。"""
    out = []
    p = os.path.join(rd, "memwatch.csv")
    if not os.path.exists(p):
        return out
    for ln in open(p, encoding="utf8"):
        if ln.startswith(("#", "time")):
            continue
        v = ln.strip().split(",")
        try:
            out.append(dict(avail=float(v[2]), commit_avail=float(v[3]), limit=float(v[4]), priv=float(v[7]) if v[7] else None,
                            ws=float(v[6]) if v[6] else None))
        except (ValueError, IndexError):
            pass
    return out


def disk(rd):
    ck = sorted(glob.glob(os.path.join(rd, "ckpt", "v.*.sim")))
    sz = [os.path.getsize(p) for p in ck]
    surf = sorted(glob.glob(os.path.join(rd, "surf", "*.gw45s")))
    o = dict(ckpt_files=[os.path.basename(p) for p in ck], ckpt_bytes=sz, surf_frames=len(surf),
             surf_bytes_mean=float(np.mean([os.path.getsize(p) for p in surf])) if surf else None)
    for k in ("r4", "hf", "r2", "r3"):
        fs = glob.glob(os.path.join(rd, "%s_c*.npz" % k))
        nfr = 0
        for f_ in fs:
            try:
                z = np.load(f_)
                key = [x for x in z.files if x.endswith("f") or x in ("frames",)]
                nfr += len(z[key[0]]) if key else 0
            except Exception:
                pass
        o[k] = dict(files=len(fs), bytes=int(sum(os.path.getsize(f_) for f_ in fs)), frames=nfr)
    return o


def da3_frames():
    F = {}
    for p in sorted(glob.glob(os.path.join(DA3, "r6_c*.npz"))):
        d = np.load(p)
        for i, f in enumerate(d["frames"]):
            F[int(f)] = (float(d["wall"][i]), float(d["surf_s"][i]), int(d["npts"][i]), int(d["ss_n"][i]))
    fr = np.array(sorted(F))
    a = np.array([F[f] for f in fr])
    r5 = []
    for p in sorted(glob.glob(os.path.join(DA3, "run_c*.json"))):
        r = json.load(open(p, encoding="utf8"))
        r5 += [e["n_vert"] for e in (r.get("info") or {}).get("r5", [])]
    rss_calm = None
    d1 = np.load(os.path.join(DA3, "r6_c00001.npz"))
    m = d1["frames"] <= 97
    rss_calm = float(d1["rss"][m].max())
    rss_peak = max(json.load(open(p, encoding="utf8"))["rss_peak_gb"] for p in glob.glob(os.path.join(DA3, "run_c*.json")))
    launches = [json.load(open(p, encoding="utf8")) for p in sorted(glob.glob(os.path.join(DA3, "run_c*.json")))]
    return dict(f=fr, solve=a[:, 0], surf=a[:, 1], n=a[:, 2], sub=a[:, 3], r5_nvert_mean=float(np.mean(r5)), rss_calm_le97=rss_calm,
                rss_peak=rss_peak, launch_first_frame=[l["wall_first_frame_s"] for l in launches],
                launch_setup=[l["wall_launch_s"] - l["wall_total_s"] for l in launches])


def analyse_probe(rd):
    runs, mw, cfg = load_run(rd)
    ckf = set()
    o = dict(run_dir=rd.replace("\\", "/"), run_id=cfg["run_id"], W=cfg["parms"]["W"], dp=cfg["parms"]["dp"], launches=[])
    light, heavy, surf, sub_all = [], [], [], []
    for L in runs:
        r = L["rec"]; f = L["f"]; s = L["solve"]
        ckf |= set(int(re.sub(r"\D", "", str(k)) or 0) for k in (r.get("ckpt_list") or []))
        tot = float(r["wall_total_s"]); over = tot - float(s.sum()) - float(L["surf"].sum())
        heavy_frames = int((L["surf"] > 0).sum())
        o["launches"].append(dict(f_start=int(r["f_start"]), f_end_done=int(r["f_end_done"]), frames=int(len(f)), wall_total_s=tot,
                                  setup_before_loop_s=float(r["wall_launch_s"]) - tot, first_frame_s=float(r["wall_first_frame_s"]),
                                  solve_sum_s=float(s.sum()), surf_sum_s=float(L["surf"].sum()), heavy_frames=heavy_frames,
                                  other_per_frame_s=over / max(len(f), 1), particles_first=int(r["particles_first"]),
                                  particles_max=int(r["particles_max"]), rss_peak_gb=float(r["rss_peak_gb"]), substeps=r.get("substeps_hist"),
                                  ckpt_gb_after=float(r.get("ckpt_gb") or 0)))
        for i in range(1, len(f)):
            fi = int(f[i])
            sub_all.append(int(L["sub"][i]))
            if fi % 24 == 0:
                continue
            (heavy if L["surf"][i] > 0 else light).append((float(s[i]), float(L["n"][i]), max(int(L["sub"][i]), 1)))
            if L["surf"][i] > 0:
                surf.append(float(L["surf"][i]))
    # 途中保存を書くコマの余分（同じ起動の前後のコマの中央値との差）
    ck_extra = []
    for L in runs:
        f = L["f"]; s = L["solve"]
        for i in range(1, len(f) - 1):
            if int(f[i]) % 24 == 0:
                nb = [s[j] for j in range(max(1, i - 3), min(len(f), i + 4)) if j != i and int(f[j]) % 24 != 0]
                if nb:
                    ck_extra.append(float(s[i] - np.median(nb)))
    def k_of(rows):
        if not rows:
            return None
        return float(np.median([a / (n / 1e6) / sb for a, n, sb in rows]))
    o["solve"] = dict(light_median_s=float(np.median([a for a, _, _ in light])) if light else None,
                      heavy_median_s=float(np.median([a for a, _, _ in heavy])) if heavy else None,
                      s_per_Mparticle_substep_light=k_of(light), s_per_Mparticle_substep_heavy=k_of(heavy),
                      substeps_seen=sorted(set(sub_all)), ckpt_write_extra_s=ck_extra)
    o["records"] = dict(r5_surface_s_per_frame=float(np.mean(surf)) if surf else None, r5_frames=len(surf))
    l1 = [l for l in o["launches"] if l["heavy_frames"] == 0]
    l2 = [l for l in o["launches"] if l["heavy_frames"] > 0]
    o["records"]["other_per_frame_light_s"] = float(np.mean([l["other_per_frame_s"] for l in l1])) if l1 else None
    o["records"]["other_per_frame_with_r4_s"] = float(np.mean([l["other_per_frame_s"] for l in l2])) if l2 else None
    o["restart"] = dict(fresh_setup_s=l1[0]["setup_before_loop_s"] if l1 else None, fresh_first_frame_s=l1[0]["first_frame_s"] if l1 else None,
                        resume=[dict(f_start=l["f_start"], setup_s=l["setup_before_loop_s"], first_frame_s=l["first_frame_s"])
                                for l in o["launches"] if l["f_start"] > 1])
    o["memory"] = dict(memwatch=mw, rss_peak_by_launch=[l["rss_peak_gb"] for l in o["launches"]])
    rows = mem_rows(rd)
    if rows:
        o["memory"]["min_commit_avail_gb"] = min(r["commit_avail"] for r in rows)
        o["memory"]["min_avail_phys_gb"] = min(r["avail"] for r in rows)
        o["memory"]["max_private_now_gb"] = max((r["priv"] or 0) for r in rows)
    o["disk"] = disk(rd)
    nv = []
    for L in runs:
        nv += [e["n_vert"] for e in (L["rec"].get("info") or {}).get("r5", [])]
    o["records"]["r5_nvert_mean"] = float(np.mean(nv)) if nv else None
    o["particles_max"] = max(l["particles_max"] for l in o["launches"])
    return o


def chain_eff(s_f, setup_s, ck_s=0.0, sp_list=(24, 16, 12, 8, 6)):
    """29 分の起動 1 回で進むコマと捨てるコマ。途中保存は 間隔 の倍数のコマで書かれ、その後に計算したコマは次の起動でやり直す。
    g49_chain の決まり（load + 1.5 × 間隔 × 1 コマ ≤ 0.92 × 1740 s）を満たす間隔のうち、進みが最も速いものを選ぶ（cfg の ckpt_list をそれにする前提）。
    返り値 (進むコマ/起動, 計算するコマ/起動, 間隔)"""
    best = None
    for sp in sp_list:
        if setup_s + 1.5 * sp * s_f > 0.92 * WL and sp != sp_list[-1]:
            continue
        n_comp = max(0.0, (WL - setup_s) / (s_f + ck_s / sp))
        prog = math.floor(n_comp / sp) * sp
        if best is None or prog > best[0]:
            best = (prog, n_comp, sp)
    return best


DISK_FREE_GB = 348.0           # G: の空き（GC.free_gb ＝ shutil.disk_usage / 1e9 の 10 進の GB。probe の chain.log 2026-10-16 10:01:36）【測定】
# 2026-10-16 確かめで直した：前は 324（同じ空きを 2^30 で割った GiB）を 10 進の GB の途中保存の大きさと比べていて、予算を 24 GB 小さく見ていた
DISK_BUDGET_GB = DISK_FREE_GB - 25.0 - 20.0   # − chain の止める線 25 GB − 余裕 20 GB【測定から選び】
HYTHON_FIXED_S = 9.0          # 起動ごとの hython の立ち上げ・場面の読み込み（chain の始め → 1 コマ目の前、PROBE025 W24・W32 で 9〜10 s）【測定】
DP_ALT = (0.5, 0.4375, 0.375, 0.353515625, 0.3125, 0.25)
BREAK_VERT = 1.38             # 崩れの間の面の頂点の増え（DA3：平均 52k 頂点 ÷ 平らな面 442 × 85 m を格子 1 m で 37.6k）【測定から計算】


def chain_sim(per_frame, load_full, ck_full, sp_list=(24, 16, 12, 8, 6), WL_=WL):
    """g49_chain の起動ごとの決まりをそのままなぞる（2026-10-16 確かめで足した）。平均の秒で間隔を 1 つ決める見込みは、崩れの間（1 コマが長い）に
    途中保存の後で捨てるコマを少なく見る。ここでは起動ごとに：前の起動の最後 48 コマの 75 % 点の秒 s_est と最初のコマの秒 load から、
    load + 1.5 × 間隔 × s_est ≤ 0.92 × WL を満たす最も大きい間隔（無ければ最小）を選び、WL を越えたコマで止め、最後の途中保存の次から続ける。
    起動ごとに hython の立ち上げ HYTHON_FIXED_S（wall_total の外）を足す。返り値は【推測】"""
    n = len(per_frame)
    f0, launches, wall, ckpts, computed = 0, 0, 0.0, 0, 0
    prev, first_prev = None, None
    ld_extra = max(0.0, load_full - HYTHON_FIXED_S)
    sps = sorted(set(sp_list), reverse=True)
    while f0 < n:
        if prev is None:
            sp = sps[0]
        else:
            s_est = float(np.percentile(prev[-48:], 75))
            ok = [v for v in sps if first_prev + 1.5 * v * s_est <= 0.92 * WL_]
            sp = ok[0] if ok else sps[-1]
        el, f, done, last_ck = 0.2, f0, [], None
        while f < n:
            c = float(per_frame[f]) + (ld_extra if (f == f0 and f0 > 0) else 0.0)
            if (f + 1) % sp == 0:
                c += ck_full
                last_ck = f
                ckpts += 1
            el += c
            done.append(c)
            f += 1
            if el > WL_:
                break
        launches += 1
        wall += el + HYTHON_FIXED_S
        computed += len(done)
        prev, first_prev = np.array(done), done[0]
        if f >= n:
            break
        if last_ck is None:
            return dict(feasible=False, sp_list=list(sps), launches=launches)
        f0 = last_ck + 1
    return dict(feasible=True, sp_list=list(sps), launches=launches, wall_h=wall / 3600, days=wall / 86400, ckpts=ckpts,
                waste_frac=(computed - n) / computed)


def project(P, D, dp=0.25, N0=N_FULL0, t_from=0.0, t_end=92.0, heavy=(47.0, 92.0), every=3):
    """半幅 85 m・粒子 dp の見込み（【推測】）。t_from > 0 は粗い計算からの引き継ぎ（今の道具には無い）を仮に置いた時の t_from〜t_end。"""
    f_end = int(round(t_end * FPS)) + 1
    f_from = int(round(t_from * FPS)) + 1
    m = (D["f"] >= f_from) & (D["f"] <= f_end)
    f = D["f"][m]; s05 = D["solve"][m]; sub05 = np.maximum(D["sub"][m], 1)
    t = (f - 1) / FPS
    mc = (D["f"] > 1) & (D["f"] <= 48)
    k05 = float(np.median(D["solve"][mc] / (D["n"][mc] / 1e6) / np.maximum(D["sub"][mc], 1)))
    k25 = P["solve"]["s_per_Mparticle_substep_light"]
    kr_lo = (k25 / k05) if dp <= 0.25 else (k25 / k05 + (1 - k25 / k05) * (dp - 0.25) / 0.25)   # 0.25〜0.5 m は 1 次で【推測】
    rN = N0 / N_DA3_0
    c = 0.5 / dp                                                    # 同じ流速での CFL の倍率
    sub_lo = np.where(t < 4.0, 1.0, np.where(sub05 <= 1, 1.0, 1.0 + 0.5 * (c - 1.0)) * sub05)
    sub_hi = np.where(t < 4.0, 1.0, c * sub05)
    solve_lo = s05 * kr_lo * rN * sub_lo / sub05
    solve_hi = s05 * max(kr_lo, 1.0 if dp >= 0.5 else kr_lo) * rN * sub_hi / sub05 * (1.25 if dp < 0.5 else 1.0)
    hv = (t >= heavy[0] - 1e-9) & (t <= heavy[1] + 1e-9) & (((f - 1) % every) == 0)
    n_heavy = int(hv.sum())
    Np = P["particles_max"]
    nvp = P["records"]["r5_nvert_mean"] or 1.0
    r5p = P["records"]["r5_surface_s_per_frame"] or 0.0
    r5_da3 = float(D["surf"][D["surf"] > 0].mean())
    nv_lo = D["r5_nvert_mean"] * c * c                              # DA3 の面の頂点 × 格子の面積の比
    nv_hi = nvp * (85.0 / float(P["W"])) * BREAK_VERT * (c * c / 4.0)   # probe の面の頂点 × 幅の比 × 崩れの間の増え
    r5_lo = r5p * nv_lo / nvp                                       # probe の 1 頂点あたりの秒
    r5_hi = max(r5p * nv_hi / nvp, r5p * N0 * 1.155 / Np, r5_da3 * rN)
    oth_l = (P["records"]["other_per_frame_light_s"] or 0.0) * (VOX_FULL / P["box_vox"]) * (N0 / N_FULL0)
    ckx = float(np.median(P["solve"]["ckpt_write_extra_s"])) if P["solve"]["ckpt_write_extra_s"] else 0.0
    ck_full = ckx * N0 * 1.155 / Np
    res = P["restart"]["resume"][0] if P["restart"]["resume"] else dict(first_frame_s=5.0)
    load_full = HYTHON_FIXED_S + max(0.0, res["first_frame_s"] - P["solve"]["light_median_s"]) * N0 * 1.155 / Np
    bpp = float(np.mean([b / Np for b in P["disk"]["ckpt_bytes"]]))       # 途中保存の 1 粒子あたりのバイト【測定】
    surf_bpv = (P["disk"]["surf_bytes_mean"] or 0.0) / nvp                 # 面の 1 頂点あたりのバイト【測定】
    r2d = sum(P["disk"][k]["bytes"] for k in ("hf", "r2", "r3")) / max(P["disk"]["hf"]["frames"], 1) * (c / 2.0)
    r4b = P["disk"]["r4"]["bytes"] / max(P["disk"]["r4"]["frames"], 1) * (c / 2.0) ** 3
    out = {}
    for tag, sv, r5, nv in (("lo", solve_lo, r5_lo, nv_lo), ("hi", solve_hi, r5_hi, nv_hi)):
        per_frame = sv + oth_l + np.where(hv, r5, 0.0)
        tot_compute = float(per_frame.sum())
        s_mean = tot_compute / len(per_frame)
        nfr = len(per_frame)
        rec_gb = n_heavy * surf_bpv * nv / 1e9 + n_heavy * r4b / 1e9 + nfr * r2d / 1e9
        opts = []
        for sp_ in (24, 16, 12, 8, 6):
            if load_full + 1.5 * sp_ * s_mean > 0.92 * WL and sp_ != 6:
                continue                                   # g49_chain の決まりに合わない間隔
            ncomp_ = max(0.0, (WL - load_full) / (s_mean + ck_full / sp_))
            prog_ = math.floor(ncomp_ / sp_) * sp_
            if prog_ <= 0:
                continue
            L_ = math.ceil(nfr / prog_)
            wall_ = (L_ - 1) * WL + load_full + (nfr - (L_ - 1) * prog_) * (s_mean + ck_full / sp_)
            ckgb_ = math.ceil(nfr / sp_) * bpp * N0 * 1.12 / 1e9      # 粒子の平均 ≈ 初め × 1.12（DA3 0〜92 s の平均 6.05 ÷ 5.44 M）
            opts.append(dict(sp=sp_, prog=prog_, ncomp=ncomp_, launches=L_, wall=wall_, ckgb=ckgb_, waste=(ncomp_ - prog_) / ncomp_))
        fit = [o for o in opts if o['ckgb'] + rec_gb <= DISK_BUDGET_GB]
        pick = min(fit, key=lambda o: o['wall']) if fit else max(opts, key=lambda o: o['sp'])
        best = min(opts, key=lambda o: o['wall'])
        sp, prog, ncomp, launches, wall, ck_gb, waste = pick['sp'], pick['prog'], pick['ncomp'], pick['launches'], pick['wall'], pick['ckgb'], pick['waste']
        n_ck = math.ceil(nfr / sp)
        out[tag] = dict(frames=len(per_frame), heavy_frames=n_heavy, solve_h=float(sv.sum()) / 3600,
                        records_h=float(np.where(hv, r5, 0.0).sum() + oth_l * len(sv)) / 3600,
                        s_per_frame_mean=s_mean, s_per_frame_by_phase={"%g-%g" % (a, b): float(per_frame[(t >= a) & (t < b)].mean())
                                                                        for a, b in ((0, 36), (36, 47), (47, 92.01)) if ((t >= a) & (t < b)).any()},
                        r5_s_per_heavy_frame=r5, ckpt_spacing=sp, ckpts=n_ck, launches=launches, frames_per_launch_computed=ncomp,
                        frames_per_launch_kept=prog, waste_frac=waste, load_per_launch_s=load_full, ckpt_write_s=ck_full,
                        wall_h=wall / 3600, days=wall / 86400,
                        disk_gb=dict(ckpt_all_kept=ck_gb, ckpt_each=bpp * N0 * 1.155 / 1e9, surf=n_heavy * surf_bpv * nv / 1e9,
                                     r4=n_heavy * r4b / 1e9, light_2d=len(per_frame) * r2d / 1e9))
        out[tag]["disk_gb"]["total_all_kept"] = sum(v for k, v in out[tag]["disk_gb"].items() if k != "ckpt_each")
        out[tag]["disk_fits_all_kept"] = bool(fit)
        out[tag]["disk_budget_gb"] = DISK_BUDGET_GB
        out[tag]["if_pruning_allowed"] = dict(ckpt_spacing=best['sp'], launches=best['launches'], wall_h=best['wall'] / 3600, waste_frac=best['waste'],
                                              ckpt_kept_gb=4 * bpp * N0 * 1.155 / 1e9)
        # 起動ごとの決まりをなぞった見込み（2026-10-16 確かめで足した。上の wall_h より実際の chain に近い）
        cs = {}
        for nm_, spl_ in (("list_24_to_6", (24, 16, 12, 8, 6)), ("fixed_16", (16,)), ("fixed_24", (24,))):
            r_ = chain_sim(per_frame, load_full, ck_full, sp_list=spl_)
            if r_.get("feasible"):
                r_["ckpt_all_kept_gb"] = r_["ckpts"] * bpp * N0 * 1.12 / 1e9
                r_["fits_disk_all_kept"] = bool(r_["ckpt_all_kept_gb"] + rec_gb <= DISK_BUDGET_GB)
            cs[nm_] = r_
        out[tag]["chain_sim"] = cs
    out["inputs"] = dict(dp=dp, N0=N0, particle_ratio_vs_DA3=rN, cfl_ratio=c, k05_s_per_Mpart_sub=k05, k25_s_per_Mpart_sub=k25, k_ratio_lo=kr_lo,
                         nvert_lo_hi=[nv_lo, nv_hi], r5_lo_hi=[r5_lo, r5_hi], other_light_s=oth_l, ckpt_write_probe_s=ckx, load_per_launch_s=load_full,
                         ckpt_bytes_per_particle=bpp, t_from=t_from, t_end=t_end, heavy=list(heavy), every=every,
                         rules=("solve = DA3 frame solve x k ratio x particle ratio x substep ratio (lo: DA3 sub-1 frames stay 1, others x(1+0.5(c-1)); "
                                "hi: x c and x1.25 for width; t < 4 s substeps 1 as measured); r5 lo/hi by surface vertices or particles; "
                                "chain: 29-min launches, checkpoint spacing by the g49_chain rule, frames after the last checkpoint recomputed"))
    return out


def memory_projection(P, D, P2=None, dp=0.25, N0=N_FULL0):
    """主メモリー（約束の量 private、GB）の見込み【推測】。粒子の数の 1 次 ＋ 重い記録・崩れの間の増え。"""
    Nmax = N0 * (D["n"].max() / N_DA3_0)
    mw = P["memory"]["memwatch"]
    p_light = mw[0]["private_gb"] if mw else P["memory"]["rss_peak_by_launch"][0]
    p_heavy = max(x["private_gb"] for x in mw) if mw else max(P["memory"]["rss_peak_by_launch"])
    Np = P["particles_max"]
    if P2:
        mw2 = P2["memory"]["memwatch"]
        p2 = mw2[0]["private_gb"] if mw2 else P2["memory"]["rss_peak_by_launch"][0]
        b = (p2 - p_light) / ((P2["particles_max"] - Np) / 1e6)
        src = "slope from the two probe widths W %s and %s (private peak, light records)" % (P["W"], P2["W"])
    else:
        b = (p_light - STRIP_RSS[1]) / ((Np - STRIP_RSS[0]) / 1e6)
        src = "slope from the probe and the 0.5 m strip S0a (RSS)"
    a = p_light - b * Np / 1e6
    calm = a + b * Nmax / 1e6
    c = 0.5 / dp
    d_rec = max(0.0, p_heavy - p_light)
    nvp = P["records"]["r5_nvert_mean"] or 1.0
    inc_lo = d_rec * D["r5_nvert_mean"] * c * c / nvp                 # probe の重い記録の増え × 面の頂点の比
    inc_hi = max(inc_lo, d_rec * nvp * (85.0 / float(P["W"])) * BREAK_VERT * (c * c / 4.0) / nvp,
                 (D["rss_peak"] - D["rss_calm_le97"]) * (N0 / N_DA3_0))   # DA3 の崩れ・記録の増え × 粒子の比
    return dict(dp=dp, slope_gb_per_Mparticle=b, intercept_gb=a, slope_source=src, particles_max=Nmax, calm_gb=calm,
                records_increment_probe_gb=d_rec, increment_lo_hi_gb=[inc_lo, inc_hi], peak_lo_gb=calm + inc_lo, peak_hi_gb=calm + inc_hi,
                probe_private_light_gb=p_light, probe_private_heavy_gb=p_heavy, DA3_breaking_increment_gb=D["rss_peak"] - D["rss_calm_le97"])


def main():
    import g49_pcfg as PC
    rds = [os.path.abspath(a) for a in sys.argv[1:]]
    P = analyse_probe(rds[0])
    cfg = json.load(open(os.path.join(rds[0], "cfg.json"), encoding="utf8"))
    P["box_vox"] = int(np.prod(cfg["box"]["cells"]))
    P2 = None
    if len(rds) > 1:
        P2 = analyse_probe(rds[1])
        P2["box_vox"] = int(np.prod(json.load(open(os.path.join(rds[1], "cfg.json"), encoding="utf8"))["box"]["cells"]))
    D = da3_frames()
    win = {"0-92s_heavy47-92_every3": dict(t_end=92.0, heavy=(47.0, 92.0)),
           "0-78s_heavy47-78_every3": dict(t_end=78.0, heavy=(47.0, 78.0)),
           "warm40-78s_heavy47-78_every3(needs a coarse-to-fine tool)": dict(t_from=40.0, t_end=78.0, heavy=(47.0, 78.0))}
    out = dict(label="probe, not a result", date=__import__("time").strftime("%Y-%m-%d %H:%M:%S"), probe=P, probe2=P2,
               DA3=dict(run=DA3, rss_peak_gb=D["rss_peak"], rss_calm_le_f97_gb=D["rss_calm_le97"], r5_nvert_mean=D["r5_nvert_mean"],
                        launch_setup_s=D["launch_setup"], launch_first_frame_s=D["launch_first_frame"]),
               memory=memory_projection(P, D, P2), windows={k: project(P, D, **v) for k, v in win.items()},
               tags=dict(probe="測定", DA3="測定", memory="推測（1 次で延ばした）", windows="推測（DA3 のコマごとの時間を probe の比で延ばした）"))
    alts = {}
    sp = PC.spec_A3()
    for dp in DP_ALT:
        b = GC.box48(dp, Lx=442.0, W=85.0, zb=-25.0, floor_pad=2)
        n0, _ = GC.count_particles(sp, b["Lx"], b["W"], dp, zb=-25.0, bed_gap=0.5)
        alts[repr(dp)] = dict(binary_exact=bool(GC.is_binary_exact(dp)), in_plan_dp=bool(dp in (0.5, 0.25, 0.1767578125)), box=[b["Lx"], b["W"], b["Hz"]],
                              cells=b["cells"], particles0=int(n0), memory=memory_projection(P, D, P2, dp=dp, N0=n0),
                              w92=project(P, D, dp=dp, N0=n0, **win["0-92s_heavy47-92_every3"]),
                              w78=project(P, D, dp=dp, N0=n0, **win["0-78s_heavy47-78_every3"]))
    out["alternatives"] = alts
    p = os.path.join(rds[0], "probe_summary.json")
    json.dump(out, open(p, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("written", p)
    print("probe solve", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in P["solve"].items() if k != "ckpt_write_extra_s"},
          "ckpt extra", [round(v, 2) for v in P["solve"]["ckpt_write_extra_s"]])
    print("probe records", {k: round(v, 3) if isinstance(v, float) else v for k, v in P["records"].items()})
    print("memory 0.25", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in out["memory"].items()})
    for k, w in out["windows"].items():
        for tg in ("lo", "hi"):
            x = w[tg]
            print("%-58s %s wall %.1f h (solve %.1f h, records %.1f h) s/frame %.1f launches %d ckpt sp %d waste %.0f%% disk all-kept %.0f GB (ckpt %.0f, each %.2f, surf %.1f)" % (
                k, tg, x["wall_h"], x["solve_h"], x["records_h"], x["s_per_frame_mean"], x["launches"], x["ckpt_spacing"], 100 * x["waste_frac"],
                x["disk_gb"]["total_all_kept"], x["disk_gb"]["ckpt_all_kept"], x["disk_gb"]["ckpt_each"], x["disk_gb"]["surf"]), "fits", x["disk_fits_all_kept"], "| pruning allowed:", {kk: round(vv, 2) for kk, vv in x["if_pruning_allowed"].items()})
        for tg in ("lo", "hi"):
            print("   chain_sim %s" % tg, {nm_: ({kk: (round(vv, 2) if isinstance(vv, float) else vv) for kk, vv in r_.items() if kk != "sp_list"})
                                          for nm_, r_ in w[tg]["chain_sim"].items()})
        print("   phases lo", {kk: round(vv, 1) for kk, vv in w["lo"]["s_per_frame_by_phase"].items()}, "hi", {kk: round(vv, 1) for kk, vv in w["hi"]["s_per_frame_by_phase"].items()},
              "r5 lo/hi", [round(v, 1) for v in w["inputs"]["r5_lo_hi"]], "load", round(w["inputs"]["load_per_launch_s"], 1))
    for k, a in alts.items():
        cw = lambda w_, tg: w_[tg]["chain_sim"]["list_24_to_6"].get("wall_h", float("nan"))
        print("dp %-12s exact %s plan %s N0 %.2f M  mem %.1f-%.1f GB  92s wall %.1f-%.1f h (chain_sim %.1f-%.1f)  78s wall %.1f-%.1f h (chain_sim %.1f-%.1f)  ckpt each %.2f GB, all kept 92s %.0f GB" % (
            k, a["binary_exact"], a["in_plan_dp"], a["particles0"] / 1e6, a["memory"]["peak_lo_gb"], a["memory"]["peak_hi_gb"],
            a["w92"]["lo"]["wall_h"], a["w92"]["hi"]["wall_h"], cw(a["w92"], "lo"), cw(a["w92"], "hi"),
            a["w78"]["lo"]["wall_h"], a["w78"]["hi"]["wall_h"], cw(a["w78"], "lo"), cw(a["w78"], "hi"), a["w92"]["lo"]["disk_gb"]["ckpt_each"],
            a["w92"]["lo"]["disk_gb"]["total_all_kept"]))


if __name__ == "__main__":
    main()
