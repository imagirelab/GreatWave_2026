# -*- coding: utf-8 -*-
"""FLIP39 E：計算の設定（JSON）を作る。py -3.10 e_cfg.py <name> [A_f] → 標準出力に JSON。
共通：周期の中心 Tc 12 s、帯 0.55〜1.6 fc（32 本、振幅は同じ）、線形の焦点 x 556 m（岩棚の縁）・群の時刻 90 s。
"""
import sys, json
G = {"Tc": 12.0, "f_lo": 0.55, "f_hi": 1.6, "nf": 32, "sigma_deg": 0.0, "xf": 556.0, "tf": 90.0}
S_PER_M = 0.03672   # S = Σ a k（水深 60 m の k）を A_f 1 m あたり（e_lin で計算）


def cfg(name, A_f, slab=True, hybrid=True, flat=False, sigma=0.0, mound=False, lead=45.0, f_after=6.0, shift=0.0, tf=None):
    # shift：水槽を長くして、斜面・岩棚・吸う帯・焦点を shift m 岸の側へ動かす（E1L）。tf はその時の焦点の時刻
    tf = G["tf"] if tf is None else tf
    t_off = tf - lead if hybrid else 0.0
    T_sim = (tf - t_off) + f_after
    f_end = int(round(T_sim * 24)) + 1
    parms = {"Lz": 12.0 if slab else 240.0, "relax_g": 1.0, "wall_taper_m": 40.0,
             "ramp_s": 0.0 if hybrid else 10.0, "hot_on": 1.0 if hybrid else 0.0, "t_off": t_off, "xhot": 420.0, "hot_w": 30.0}
    if shift > 0:
        parms.update({"Lx": 806.0 + shift, "xs0": 420.0 + shift, "xa0": 706.0 + shift, "mx0": 300.0 + shift, "mx1": 706.0 + shift})
    if flat:
        parms["xs0"] = 2000.0 + shift
    if mound:
        parms.update({"lg1_d": 26.0, "lg1_x": 350.0, "lg1_z": -120.0, "lg1_sx": 60.0, "lg1_sz": 110.0})
    g = dict(G, A_f=A_f, sigma_deg=sigma, tf=tf, xf=G["xf"] + shift)
    if mound:
        g["phase_with_mound"] = True
    f_snap = max(1, int(round((tf - t_off - 14.0) * 24)))
    a = {"run_id": name, "parms": parms, "group": g, "flat": flat, "f_start": 1, "f_end": f_end,
         "ckpt_on": 1, "ckpt_every": 240 if slab else 72, "wall_limit_s": 1740,
         "snap_from": f_snap, "snap_every": 2, "snap_x": [300 + shift, 706 + shift], "snap_ymin": -25,
         "snap_zc": [0] if slab else [-118.5, -100, -80, -60], "snap_zhalf": 6.0 if slab else 1.5,
         "mesh_from": f_snap, "mesh_every": 3,
         "note": "FLIP39 E %s：%s、%s、%s、A_f %.2f m（S %.3f）、向きの広がり %.0f°%s" % (
             name, "板 12 m（一方向）" if slab else "3D 806×240 m（焦点は z=-120 m の壁＝対称の面）", "途中から（群の時刻 %.0f s から）" % t_off if hybrid else "静かな水から造波だけ",
             "平らな海 60 m" if flat else "岩棚（1:4、26 m）", A_f, A_f * S_PER_M, sigma, "、盛り上がり（レンズ）" if mound else "")}
    return a


if __name__ == "__main__":
    name = sys.argv[1]; A = float(sys.argv[2])
    kw = {}
    for s in sys.argv[3:]:
        k, v = s.split("=")
        kw[k] = (v == "1") if k in ("slab", "hybrid", "flat", "mound") else float(v)
    print(json.dumps(cfg(name, A, **kw), ensure_ascii=True))
