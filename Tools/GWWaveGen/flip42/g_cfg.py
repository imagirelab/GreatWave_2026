# -*- coding: utf-8 -*-
"""FLIP42：計算 1 本の設定（JSON）を作る。数は凍結した計画の plan/plan_numbers.json から読む（ここで値を決め直さない）。
py -3.10 g_cfg.py <run_id> dp=0.5 nb=1 [f_end=4508] [ckpt_every=240] [minsub=1] [maxsub=8] [cfl=1.0] [pcfl=0.75] [sec_t0=...] [S=0.352]
  nb=1：粒子の帯 4 m（格子の数は 4 m ÷ 格子を切り上げ）。nb=0：帯なし（水の全体に粒子、FLIP41 の nb0 と同じ形）。
水槽（計画 §7.1）：帯 0〜x_p、自由に進む所 x_p〜xa0、吸う帯 xa0〜Lx。Lx は格子の倍数へ切り上げ（吸う帯がその分だけ長くなる）。
"""
import sys, json, math, os
import numpy as np

PLAN = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/plan/plan_numbers.json"
FPS = 24


def rup(v, q):
    return float(math.ceil(v / q - 1e-9) * q)


def make(run_id, dp, nb=1, f_end=None, ckpt_every=240, minsub=1, maxsub=8, cfl=1.0, pcfl=0.75, sec_t0=None, S=None,
         sec_x_rel=None, note="", band_Lc=1.0, free_Lc=None):
    P = json.load(open(PLAN, encoding="utf-8"))
    full, tank = P["full"], P["tank"]
    lam = full["lam"]; s = math.sqrt(lam)
    fc = P["lab"]["fc"] / s
    vox = 2.0 * dp
    # band_Lc：造波の帯の長さ（Lc の倍数）。1 が計画どおり。帯を長くした分だけ水槽を長くし、造波板 x_p から先の長さは変えない
    xp = tank["x_p"] if float(band_Lc) == 1.0 else float(band_Lc) * full["Lc"]
    shift = xp - tank["x_p"]
    Lx = rup(tank["Lx"] + shift, vox)
    xa0 = tank["absorber"][0] + shift
    # free_Lc：焦点より先の自由に進む所の長さ（Lc の倍数）。None が計画どおり（2.5 Lc）。圧力が解けない失敗の時の短くした水槽（計画 §7.6）
    if free_Lc is not None:
        xa0 = xp + full["xb"] + float(free_Lc) * full["Lc"]
        Lx = rup(xa0 + (tank["absorber"][1] - tank["absorber"][0]), vox)
    band_vox = int(math.ceil(P["solver"]["narrowband_m"] / vox - 1e-9))
    S = P["lab"]["S"] if S is None else float(S)
    parms = dict(dp=dp, gridscale=2.0, Lz=4 * vox, Lx=Lx, h0=full["h"], ytop=tank["y_top"],
                 band_vox=float(band_vox if int(nb) == 1 else 1000.0), maxsub=float(maxsub), minsub=float(minsub), cfl=float(cfl), pcfl=float(pcfl),
                 ncomp=float(P["lab"]["N"]), fc=fc, dff=P["lab"]["dff"], S=S, x_p=xp, x_b=full["xb"], t_b=full["tb"],
                 ramp_s=tank["ramp"], xg_end=xp, relax_g=1.0, dt0=1.0 / FPS, wall_taper_m=tank["wall_taper_m"] * float(band_Lc),
                 xa0=xa0, abs_sigma=0.8, abs_pow=2.0)
    if f_end is None:
        f_end = int(tank["frames"])
    sx = P["section_record"]["x_rel"] if sec_x_rel is None else sec_x_rel
    sec = dict(x0=xp + sx[0], x1=xp + sx[1], t0=P["section_record"]["t_from"] if sec_t0 is None else float(sec_t0))
    case = dict(kind="G", dp=dp, vox=vox, nb=int(nb), band_vox=band_vox if int(nb) == 1 else None, band_m=band_vox * vox if int(nb) == 1 else None,
                S=S, lam=lam, Tc=full["Tc"], Lc=full["Lc"], x_p=xp, band_Lc=float(band_Lc), free_Lc=free_Lc, x_b=full["xb"], t_b=full["tb"],
                gauges={k: v["x_scene"] + shift for k, v in P["gauges"].items()}, plan_sha256_note="plan_frozen.json")
    return dict(run_id=run_id, parms=parms, solver=dict(veltransfer="apic", donarrowband=int(nb)), case=case, sec=sec,
                f_start=1, f_end=int(f_end), ckpt_on=1, ckpt_every=int(ckpt_every), wall_limit_s=1740, level_guard_m=1.0,
                note=note or ("FLIP42 %s：Rapp & Melville の巻き波の組（S %.3f）の 70 倍、粒子 %g m、%s" % (
                    run_id, S, dp, "帯 %d 格子（%.2f m）" % (band_vox, band_vox * vox) if int(nb) == 1 else "帯なし")))


if __name__ == "__main__":
    rid = sys.argv[1]
    kw = {}
    for a in sys.argv[2:]:
        k, v = a.split("=", 1)
        kw[k] = float(v) if k not in ("note",) else v
    for k in ("nb", "f_end", "ckpt_every", "minsub", "maxsub"):
        if k in kw:
            kw[k] = int(kw[k])
    print(json.dumps(make(rid, **kw), ensure_ascii=True))
