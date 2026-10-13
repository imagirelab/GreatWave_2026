# -*- coding: utf-8 -*-
"""FLIP46：計算の設定（cfg.json）を作る（py -3.10。numpy だけ）。FLIP45 の g45_cfg.py の考えを写して新しく書いた（入口の表・利得・帯はない）。
計画：BigWave_Recipes_ja.md §5.2 E1b（Guyenne & Grilli 2006、k = 0.25、H0/h0 0.6、h0 17 m）。2 進で割り切れない粒子は拒む（g46_common.check_dp）。
  make(name, dp, ...)   1 本の設定（P05：粒子 0.5 m の下見、P025：粒子 0.25 m）
  smoke(kind, dp, ...)  煙の試し（SA：尾根の上の静かな水、SB：GN の孤立波）
  ready(sol)            runs/ready/P05.json・P025.json・SMOKE_dp1p0.json と smoke/ready/SA_dp1p0.json・SB_dp1p0.json を書く
孤立波の npz：Tanaka の厳密な解（g46_solitary.write_grid、別の者が作る。置き場所の約束 g46_common.SOL_TANAKA）があればそれ、なければ
GN の代わり（g46_gn_npz.py）を使い、設定の solitary_kind に書く。Tanaka の解ができたら `py -3.10 g46_cfg.py ready --sol <npz>` で書き直す。
使い方：py -3.10 g46_cfg.py ready [--sol <npz>] [--wave tanaka|gn]
2026-10-12 統合の役が足した：--wave tanaka|gn（既定 tanaka。GN は比べるための選び）、煙の試し ST（Tanaka の孤立波・尾根）・STF（Tanaka・平らな海底の
対照）・SGF（GN・平らな海底）、0 コマ目の確かめの点（頂と前後 15 m・32 m、深さ −1・−2・−4.25・−8.5・−12.75・−15・−15.3 m）と粒子の書き出し（init_dump）、
runs/ready/P05_GN.json（GN で比べる時の設定。走らせるのは main session）。
  py -3.10 g46_cfg.py smoke ST --dp 1.0 --t_end 4 [--tag 名前] [--wave gn]   煙の試しの設定を smoke/ready/ に書く
  py -3.10 g46_cfg.py one P05 --wave gn --tag P05_GN                       1 本の設定を runs/ready/ に書く
  py -3.10 g46_cfg.py one P05 --veltransfer flip --tag P05_FLIP             速度の受け渡しを FLIP に（y = 0 の面の APIC の偏りを避ける選び）
  --side_pad 2：対称の面 y = 0 を SDF の壁にする（APIC のまま。粒子 1 m で壁の層の水面が 0.3 m 高く出たので既定にしない）
"""
import os, sys, json, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g46_common as GC

# 箱の底を平らな海底より 2 格子下げ、海底を全部 SDF にする（FLIP44 と同じ作り）。2026-10-12 の煙の試しで、0（箱の底が海底：FLIP45 の作り）では
# 尾根の始まり（x 97〜116 m、海底が箱の底から格子 1 個以内）で粒子が海底の面の下へ最大 0.9〜1.5 m 入った（粒子 0.5 m で 3 s に 165 個）。2 では 0 個
FLOOR_PAD = 2

TARGETS = dict(
    source="Guyenne & Grilli 2006, J. Fluid Mech. 547, 361-388（表 1、k = 0.25）。BigWave_Recipes_ja.md §5.2",
    t_break_s=7.890 * GC.TS, x_break_m=16.09 * GC.H0, zB_m=0.706 * GC.H0, hB_m=0.275 * GC.H0, zB_over_hB=2.57, tol=0.05,
    ref_2d=dict(zB_m=0.680 * GC.H0, hB_m=0.298 * GC.H0, zB_over_hB=2.28),
    short_crest=dict(t_s=9.142 * GC.TS, note_ja="真ん中が巻き、y = ±68 m（y' ±4）はまだ一価（図 9）"))


def sol_choice(sol=None, wave=None):
    """孤立波の npz を選ぶ。sol（パス）が先。wave="tanaka"：厳密な解（なければ止める）、"gn"：GN の式（比べるための選び）。
    どちらもなければ Tanaka があればそれ、なければ GN。"""
    if sol:
        if not os.path.exists(sol):
            raise SystemExit("孤立波の npz がない: %s" % sol)
        if os.path.normcase(os.path.abspath(sol)) == os.path.normcase(os.path.abspath(GC.SOL_TANAKA)):
            return sol, "Tanaka1986_exact"
        if os.path.normcase(os.path.abspath(sol)) == os.path.normcase(os.path.abspath(GC.GN_PLACEHOLDER)):
            return sol, "GN"
        return sol, ("given:" + os.path.basename(sol))
    if wave == "gn":
        if not os.path.exists(GC.GN_PLACEHOLDER):
            import g46_gn_npz
            g46_gn_npz.build()
        return GC.GN_PLACEHOLDER, "GN"
    if os.path.exists(GC.SOL_TANAKA):
        return GC.SOL_TANAKA, "Tanaka1986_exact"
    if wave == "tanaka":
        raise SystemExit("Tanaka の解の npz がない: %s（py -3.10 g46_solitary.py --check --grid で作る）" % GC.SOL_TANAKA)
    if not os.path.exists(GC.GN_PLACEHOLDER):
        import g46_gn_npz
        g46_gn_npz.build()
    return GC.GN_PLACEHOLDER, "GN_placeholder"


# 0 コマ目の確かめの点（統合の役、2026-10-12）。頂（x0 = 98.345 m）と前後 15 m・32 m、深さは計画の z（静かな水面 0・上向き）
INIT_DX = [-32.0, -15.0, 0.0, 15.0, 32.0]
INIT_Y = [-1.0, -2.0, -4.25, -8.5, -12.75, -15.0, -15.3]


def parms_for(dp, wave_on=1.0, smoke=False, floor_pad=0, side_pad=0, **over):
    GC.check_dp(dp, smoke=smoke)
    b = GC.box(dp, floor_pad=floor_pad, side_pad=side_pad)
    p = dict(dp=b["dp"], gridscale=2.0, x0=b["x0"], Lx=b["Lx"], W=b["W"], zb=GC.Z_BOTTOM, Hz=b["Hz"], h0=GC.H0,
             ox=b["ox"], oy=b["oy"], oz=b["oz"], maxsub=8.0, minsub=1.0, cfl=1.0, pcfl=0.75, t_off=0.0,
             ridge_on=1.0, ridge_x0=GC.RIDGE_X0, ridge_k=GC.RIDGE_K, ridge_s=GC.RIDGE_S, bed_gap=0.5, floor_pad=float(floor_pad), side_pad=float(side_pad),
             wave_on=float(wave_on),
             surf_layer_m=2.5, mirror_m=1.0, surf_vox_scale=1.0, crop_x0=0.0, crop_x1=b["Lx"], crop_z1=b["W"],
             surf_ycut=-15.0, surf_keep_vox=1.0, surf_bed_vox=0.5)
    p.update(over)
    return p, b


def base(run_id, dp, f_end, out_root, kind, wave_on=1.0, sol=None, smoke=False, note="", wave=None, **over):
    p, b = parms_for(dp, wave_on=wave_on, smoke=smoke, **over)
    sp, skind = sol_choice(sol, wave) if wave_on > 0.5 else (None, "none")
    vox = b["vox"]
    return dict(
        run_id=run_id, out_root=out_root, stage="FLIP46", kind=kind,
        case=dict(name="E1b_GG06_k0.25", plan="Docs/Research/BigWave_Recipes_ja.md §5.2", targets=TARGETS),
        f_start=1, f_first=1, f_end=int(f_end), parms=p, box=b,
        solitary_npz=sp, solitary_kind=skind,
        solver=dict(veltransfer="apic", donarrowband=0),
        records=dict(r2=True, r3_z=b["W"] - 0.5 * vox, block=120, r4_block=24, preg_every=24,
                     r4=dict(x=[150.0, b["Lx"]], z1=b["W"], y0=-10.0, y1=16.0, clip_vox=6.0, t0=6.0),
                     r5=dict(t0=6.0, every=1)),
        ckpt_on=1, ckpt_every=48, ckpt_list=[96, 72, 48, 24, 12], wall_limit_s=1740, level_guard_m=1.0, disk_stop_free_gb=25.0,
        max_hours=6.0, level_box=[0.0, b["Lx"], 0.0, b["W"]], n1_x=[260.0, 310.0] if wave_on > 0.5 else [0.0, b["Lx"]],
        n1_window=[0.5, 1.5], shore_x=250.0, fieldbox_frames=[2], pstats_frames=[1, 2, int(f_end)], init_check_frames=[1, 2, 3],
        init_check_dx=list(INIT_DX), init_check_y=list(INIT_Y), init_dump=True, stop_touchdown=None, note=note)


def make(name, sol=None, floor_pad=FLOOR_PAD, wave=None, tag=None):
    if name == "P05":
        c = base(tag or "P05", 0.5, GC.frames_for(0.0, 15.0), "runs", "preview", sol=sol, floor_pad=floor_pad, wave=wave,
                 note="FLIP46 P05：粗い下見（粒子 0.5 m、格子 1 m）。GG06 の尾根 k 0.25・孤立波 0.6 を 0〜15 s")
        c["max_hours"] = 2.0
    elif name == "P025":
        c = base(tag or "P025", 0.25, GC.frames_for(0.0, 15.0), "runs", "main", sol=sol, floor_pad=floor_pad, wave=wave,
                 note="FLIP46 P025：粒子 0.25 m（格子 0.5 m）。GG06 の尾根 k 0.25・孤立波 0.6 を 0〜15 s")
        c["max_hours"] = 8.0
        c["init_check_frames"] = [1, 2]
    else:
        raise SystemExit("知らない名前 %s" % name)
    if c["solitary_kind"] != "Tanaka1986_exact":
        c["note"] += "（孤立波：%s。比べるための選び）" % c["solitary_kind"]
    return c


def smoke(kind, dp=1.0, t_end=None, sol=None, tag=None, floor_pad=FLOOR_PAD, wave=None):
    sfx = "_pad%d" % int(floor_pad) if floor_pad else ""
    dps = repr(float(dp)).replace(".", "p")
    if kind in ("ST", "STF", "SGF"):  # 統合の役（2026-10-12）：Tanaka の孤立波（尾根・平らな海底の対照）、GN の平らな海底
        t_end = t_end or 4.0
        flat = kind in ("STF", "SGF")
        wv = "gn" if kind == "SGF" else (wave or "tanaka")
        over = dict(ridge_on=0.0) if flat else {}
        c = base(tag or "%s_dp%s" % (kind, dps), dp, GC.frames_for(0.0, t_end), "smoke", "smoke", wave_on=1.0, smoke=True,
                 sol=sol, wave=wv, floor_pad=floor_pad,
                 note="FLIP46 煙の試し %s：%s の孤立波・%s。0 コマ目の流速（格子と粒子、頂と前後 15 m・32 m）、頂の高さと速さ、静かな水面のずれ、漏れ" % (
                     kind, "GN" if wv == "gn" else "Tanaka の厳密な解", "平らな海底（対照）" if flat else "尾根 k 0.25"), **over)
        c["ckpt_on"] = 0
        c["max_hours"] = 0.25
        c["wall_limit_s"] = 540
        c["records"]["r4"] = None
        c["records"]["r5"] = dict(t0=0.0, every=12)
        c["pstats_frames"] = [1, 2, c["f_end"]]
        return c
    if kind == "SA":       # 尾根の上の静かな水
        t_end = t_end or 4.0
        c = base(tag or "SA_dp%s%s" % (repr(float(dp)).replace(".", "p"), sfx), dp, GC.frames_for(0.0, t_end), "smoke", "smoke", wave_on=0.0, smoke=True,
                 floor_pad=floor_pad,
                 note="FLIP46 煙の試し SA：尾根の上の静かな水（波なし）。平均の水面の動き・自由落下・海底の中への漏れ")
    elif kind == "SB":     # GN の孤立波
        t_end = t_end or 3.0
        c = base(tag or "SB_dp%s%s" % (repr(float(dp)).replace(".", "p"), sfx), dp, GC.frames_for(0.0, t_end), "smoke", "smoke", wave_on=1.0, smoke=True,
                 sol=sol, wave=wave or "gn", floor_pad=floor_pad,
                 note="FLIP46 煙の試し SB：GN の孤立波。初めのコマの格子の流速（深さ h0/2）と頂の速さ")
    else:
        raise SystemExit("知らない煙の試し %s" % kind)
    c["ckpt_on"] = 0
    c["max_hours"] = 0.25
    c["wall_limit_s"] = 560
    c["records"]["r4"] = None
    c["records"]["r5"] = dict(t0=0.0, every=24) if kind == "SB" else None
    c["pstats_frames"] = [1, 2, c["f_end"]]
    return c


def write(c, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(c, open(path, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    return path


def ready(sol=None, wave=None):
    out = []
    for nm in ("P05", "P025"):
        out.append(write(make(nm, sol, wave=wave), GC.B46 + "/runs/ready/%s.json" % nm))
    if not sol and wave != "gn":                       # GN で比べる時の設定（選び。走らせるのは main session）
        out.append(write(make("P05", wave="gn", tag="P05_GN"), GC.B46 + "/runs/ready/P05_GN.json"))
    for k in ("SA", "SB", "ST", "STF"):
        c = smoke(k, 1.0, wave=wave if k == "ST" else None)
        out.append(write(c, GC.B46 + "/smoke/ready/%s.json" % c["run_id"]))
    c = smoke("ST", 1.0, tag="SMOKE_dp1p0", wave=wave)  # runs/ready に置く煙の試し（粒子 1.0 m、既定は Tanaka、4 s。置き場所は smoke/）
    out.append(write(c, GC.B46 + "/runs/ready/SMOKE_dp1p0.json"))
    c = smoke("SB", 1.0, tag="SMOKE_GN_dp1p0")          # GN の煙の試し（比べる時）
    out.append(write(c, GC.B46 + "/runs/ready/SMOKE_GN_dp1p0.json"))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["ready", "smoke", "one"])
    ap.add_argument("name", nargs="?", default=None)
    ap.add_argument("--sol", default=None)
    ap.add_argument("--wave", choices=["tanaka", "gn"], default=None)
    ap.add_argument("--dp", type=float, default=1.0)
    ap.add_argument("--t_end", type=float, default=None)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--veltransfer", choices=["apic", "flip"], default=None,
                    help="速度の受け渡し（既定 apic。flip は y = 0 の対称の面の偽の横流れを避ける選び。2026-10-12 統合の役の煙の試し）")
    ap.add_argument("--side_pad", type=int, default=0, help="対称の面 y = 0 を SDF の壁にする（格子の数。既定 0 = 箱の壁）")
    a = ap.parse_args()

    def extra(c):
        if a.veltransfer:
            c["solver"]["veltransfer"] = a.veltransfer
        if a.side_pad:
            p_, b_ = parms_for(c["parms"]["dp"], wave_on=c["parms"]["wave_on"], smoke=(c.get("kind") == "smoke"),
                               floor_pad=int(c["parms"]["floor_pad"]), side_pad=a.side_pad,
                               **({"ridge_on": c["parms"]["ridge_on"]} if c["parms"].get("ridge_on", 1.0) < 0.5 else {}))
            c["parms"] = p_; c["box"] = b_
        if a.veltransfer or a.side_pad:
            c["note"] += "（veltransfer %s・side_pad %d）" % (c["solver"]["veltransfer"], a.side_pad)
        return c
    if a.what == "smoke":
        c = extra(smoke(a.name, a.dp, t_end=a.t_end, sol=a.sol, tag=a.tag, wave=a.wave))
        paths = [write(c, GC.B46 + "/smoke/ready/%s.json" % c["run_id"])]
    elif a.what == "one":
        c = extra(make(a.name, a.sol, wave=a.wave, tag=a.tag))
        paths = [write(c, GC.B46 + "/runs/ready/%s.json" % c["run_id"])]
    else:
        paths = ready(a.sol, a.wave)
    for p in paths:
        c = json.load(open(p, encoding="utf8"))
        print(p, c["solitary_kind"], "f_end", c["f_end"], "box", c["box"]["Lx"], c["box"]["W"], c["box"]["Hz"], "o", c["box"]["ox"], c["box"]["oy"], c["box"]["oz"])
