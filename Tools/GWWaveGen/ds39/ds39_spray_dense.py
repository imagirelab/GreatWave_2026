# -*- coding: utf-8 -*-
"""設計39 第「紙」部 ③ 小飛沫：設計31 の飛沫（186 粒）の密度を上げた版。

作り方（numpy。Unity の描画ではない）：
  設計31 の飛沫の表（ds31_spray_table.json）の各粒を親として、子を K 粒（既定 3）作る。子は親の放出を少しだけずらしたもの：
    ・放出の時刻 τ_e：親 + U(0, dtau_max)（親より後。白くなった後の放出を保つ）。τ_show = τ_e、ramp は親と同じ。
    ・放出の点：親の放出の点から、親の初速に直交する向きへ U(off_min, off_max) m。
    ・初速：親の初速を、ランダムな軸のまわりに U(0, ang_max)° 回し、U(speed_lo, speed_hi) 倍。
    ・半径：親 × U(rad_lo, rad_hi)（小さい粒。下限 rad_min_m）。
  設計31 の check_paths（150：水面へ引き戻されない・水の側へ入らない・放出の後に離れる）を同じ引数で通し、通らない子は捨てる。
  乱数は親の番号と子の番号で決まる（numpy の default_rng(seed + 10 × 親 + 子)）。
出力（Git 対象外）：Unity/Build/Design/39/paper/spray/
  ds39_spray_dense_frames.bin・.json（設計31 と同じ GreatWave.DS31.particles/1。子だけ。親の 186 粒は設計31 のファイルのまま描く）、
  ds39_spray_dense_table.json（子ごとの値と検査）、ds39_spray_dense_log.json（引数・入力の SHA-256・数）。
"""
import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "ds31"))
import ds31_spray as D  # noqa: E402  （P・G・K・check_paths・eval_state・WARP・HERO_PKG・SEA_DIR を借りる）

SRC = REPO + "/Unity/Build/Design/31/spray"
OUT = REPO + "/Unity/Build/Design/39/paper/spray"
PARAMS = dict(children_per_parent=3, seed=39031, dtau_max_s=0.06, off_min_m=0.03, off_max_m=0.15, ang_max_deg=7.0,
              speed_lo=0.85, speed_hi=1.10, rad_lo=0.35, rad_hi=0.65, rad_min_m=0.015)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rot(v, axis, deg):
    axis = axis / np.linalg.norm(axis)
    a = np.radians(deg)
    return v * np.cos(a) + np.cross(axis, v) * np.sin(a) + axis * np.dot(axis, v) * (1 - np.cos(a))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--k", type=int, default=PARAMS["children_per_parent"])
    args = ap.parse_args()
    PARAMS["children_per_parent"] = args.k
    t0 = time.time()
    os.makedirs(args.out, exist_ok=True)
    tabp = os.path.join(SRC, "ds31_spray_table.json")
    parents = json.load(open(tabp, encoding="utf-8"))["particles"]
    kids = []
    for i, p in enumerate(parents):
        for k in range(args.k):
            rng = np.random.default_rng(PARAMS["seed"] + 10 * i + k)
            v0 = np.array(p["v0"], float)
            vn = v0 / np.linalg.norm(v0)
            r = rng.normal(size=3); r -= vn * np.dot(r, vn); r /= np.linalg.norm(r)
            pe = np.array(p["p_e"], float) + r * rng.uniform(PARAMS["off_min_m"], PARAMS["off_max_m"])
            ax = rng.normal(size=3); ax -= vn * np.dot(ax, vn)
            v = rot(v0, ax, rng.uniform(0.0, PARAMS["ang_max_deg"])) * rng.uniform(PARAMS["speed_lo"], PARAMS["speed_hi"])
            te = min(p["tau_e"] + rng.uniform(0.0, PARAMS["dtau_max_s"]), D.P["tau_e"][1])
            rad = max(p["radius_m"] * rng.uniform(PARAMS["rad_lo"], PARAMS["rad_hi"]), PARAMS["rad_min_m"])
            kids.append(dict(parent=i, parent_dot_id=p["dot_id"], child=k, p_e=pe.tolist(), v0=v.tolist(), tau_e=float(te), tau_show=float(te),
                             ramp_s=float(p["ramp_s"]), radius=float(rad), mode=p["mode"]))
    print("children", len(kids), "%.1fs" % (time.time() - t0))
    hero = D.K.Pkg(D.HERO_PKG)
    near = D.K.Pkg(os.path.join(D.SEA_DIR, "near"))
    chk = D.check_paths(kids, hero, near, D.P["tau_e"][0])
    print("checked %.1fs" % (time.time() - t0))
    keep = []
    for j, q in enumerate(kids):
        q["contact"] = int(chk["contact"][j]); q["inside"] = int(chk["inside"][j]); q["never_left"] = int(chk["never_left"][j])
        q["min_dist_m"] = float(chk["min_dist"][j]); q["dist_tstar_m"] = float(chk["dist_tstar"][j])
        if q["contact"] == 0 and q["inside"] == 0 and q["never_left"] == 0:
            keep.append(q)
    n = len(keep)
    print("kept", n, "of", len(kids))
    tab = dict(p_e=np.array([q["p_e"] for q in keep]), v0=np.array([q["v0"] for q in keep]), tau_e=np.array([q["tau_e"] for q in keep]),
               tau_show=np.array([q["tau_show"] for q in keep]), ramp_s=np.array([q["ramp_s"] for q in keep]), radius=np.array([q["radius"] for q in keep]))
    twj = json.load(open(D.WARP, encoding="utf-8"))
    t_all = np.array(twj["t"]); tau_all = np.array(twj["tau"])
    frames = np.arange(0, 421) / 30.0
    taus_f = np.interp(frames, t_all, tau_all)
    fr = np.zeros((len(frames), n, 4), np.float32)
    for i, tau in enumerate(taus_f):
        pos, rad = D.eval_state(tab, float(tau))
        fr[i, :, :3] = pos; fr[i, :, 3] = rad
    fp = os.path.join(args.out, "ds39_spray_dense_frames.bin"); fr.tofile(fp)
    src_frames = json.load(open(os.path.join(SRC, "ds31_spray_frames.json"), encoding="utf-8"))
    alive = (fr[:, :, 3] > 0).sum(1)
    json.dump(dict(schema="GreatWave.DS31.particles/1", frames=len(frames), hz=30, t0=0.0, count=n, file="ds39_spray_dense_frames.bin", sha256=sha(fp),
                   bytes=os.path.getsize(fp),
                   layout_ja="float32 リトルエンディアン、コマ × 数 × 4（x, y, z, 半径）。ワールドの m。半径 0 は描かない。コマ k は体験の時刻 t = t0 + k/hz（t ≥ 12 s は t* の静止）",
                   colour=src_frames["colour"], colour_space_ja="sRGB（無照明の不透明。設計31 の飛沫と同じ色）",
                   note_ja="設計39 ③ 小飛沫：設計31 の飛沫の子だけ（親の 186 粒は設計31 のファイルのまま別に描く）。ds39_spray_dense.py"),
              open(os.path.join(args.out, "ds39_spray_dense_frames.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(dict(schema="GreatWave.DS39.spray_dense_table/1", count=n, children=keep, rejected=[q for q in kids if q not in keep]),
              open(os.path.join(args.out, "ds39_spray_dense_table.json"), "w", encoding="utf-8"), ensure_ascii=False)
    rads = tab["radius"]
    log = dict(schema="GreatWave.DS39.spray_dense_log/1", number="設計39", part="紙（③ 小飛沫）", params=PARAMS, ds31_params_used=dict(tau_e=D.P["tau_e"], check_hz=D.P["check_hz"]),
               inputs=dict(ds31_table=tabp.replace(REPO + "/", ""), ds31_table_sha256=sha(tabp), ds31_frames_sha256=src_frames["sha256"],
                           hero_pos_sha256=hero.k["pos_sha256"], near_pos_sha256=near.k["pos_sha256"], timewarp_sha256=sha(D.WARP)),
               code_sha256={os.path.basename(__file__): sha(os.path.abspath(__file__)), "ds31_spray.py": sha(D.__file__)},
               parents=len(parents), children_made=len(kids), children_kept=n, rejected_by_150=len(kids) - n,
               total_with_parents=len(parents) + n, density_ratio=(len(parents) + n) / len(parents),
               child_radius_m=dict(min=float(rads.min()), median=float(np.median(rads)), max=float(rads.max())),
               parent_radius_m=dict(min=float(min(p["radius_m"] for p in parents)), median=float(np.median([p["radius_m"] for p in parents])),
                                    max=float(max(p["radius_m"] for p in parents))),
               alive_children_at_t=dict(t8=int(alive[240]), t10=int(alive[300]), t11=int(alive[330]), t12=int(alive[360])),
               first_child_t=float(frames[np.argmax(alive > 0)]) if (alive > 0).any() else None,
               seconds=round(time.time() - t0, 1))
    json.dump(log, open(os.path.join(args.out, "ds39_spray_dense_log.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: log[k] for k in ("children_made", "children_kept", "density_ratio", "alive_children_at_t", "seconds")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
