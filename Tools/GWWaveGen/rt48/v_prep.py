# -*- coding: utf-8 -*-
"""RT48 つなぎ・確かめの段（record_ja.md の V2・V5・V6）：Unity に書き出させる前の準備（py -3.10）。
使い方:
  py -3.10 v_prep.py coarse
出力（Unity/Build/RT48/verify/<元>/）:
  contours.npz        元のコマの主な曲線（R3 の記録の等高線。x_rel, y）と頂・唇の先の番号。V2・V5 の比べの元
  holdout_pairs.bin   float32 LE (n, 2, 8192, 2)。取り置いたコマの組：(k, k+2) と (k, k+3) を r_bake.py と同じ目印の対応で取り直した A・B
                      （X = x_rel − 527.0、Y）。Unity が同じ計算シェーダーで混ぜて書き出す（V5）
  holdout_index.json  組ごとの k・kb・割合・比べるコマ
  c6_times.json       C6 の時刻（座席ごと 20。V6 の決まり）
R3 のファイルは読むだけ。"""
import os as _os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")
import sys, os, json, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r_lib as L

BUILD = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48"


def load_frames(src_name, f0, f1, man):
    """各コマの主な曲線・頂・唇の先（r_bake.py の run と同じたどり方）"""
    if src_name == "coarse":
        rec = L.Records(L.R3)
        frame_fn = lambda f: L.coarse_frame(rec, f, L.OFF_R3)
    elif src_name == "fine":   # r_bake.py fine と同じ読み方（細かい面は r_after.py が rerun/R3e/fine/ に書く）
        import r_bake
        fs = r_bake.Fine(os.path.join(BUILD, "rerun", "R3e", "fine"))
        frame_fn = fs.frame
    else:
        raise SystemExit("知らない元：" + src_name)
    xc = L.CREST_START
    out = {}
    for f in range(f0, f1 + 1):
        fr = frame_fn(f)
        m = fr["main"]
        ic = L.crest_in(m, xc)
        xc, yc = float(m[ic, 0]), float(m[ic, 1])
        il = L.lip_tip(m, ic, xc)
        out[f] = dict(main=m, ic=ic, il=il, xc=xc, yc=yc, loops=fr["loops"])
    # 焼きの manifest の頂と同じか（同じたどり方なので同じはず）
    fr_man = {r["frame"]: r for r in man["frames"]}
    dmax = max(abs(out[f]["xc"] - fr_man[f]["crest_x"]) for f in out)
    return out, dmax


def main(src_name):
    T0 = time.time()
    d = os.path.join(BUILD, "data", src_name)
    man = json.load(open(os.path.join(d, "manifest.json"), encoding="utf8"))
    f0, f1 = man["time"]["first_frame"], man["time"]["last_frame"]
    K = man["playback"]["K"]
    out_dir = os.path.join(BUILD, "verify", src_name)
    os.makedirs(out_dir, exist_ok=True)
    F, dcrest = load_frames(src_name, f0, f1, man)
    print("loaded", len(F), "frames", round(time.time() - T0, 1), "s; crest vs manifest max", dcrest, flush=True)
    # ---- contours.npz
    mains = [F[f]["main"] for f in range(f0, f1 + 1)]
    offs = np.cumsum([0] + [len(m) for m in mains])
    np.savez_compressed(os.path.join(out_dir, "contours.npz"), pts=np.concatenate(mains, 0), offs=offs,
                        frames=np.arange(f0, f1 + 1), ic=np.array([F[f]["ic"] for f in range(f0, f1 + 1)]),
                        il=np.array([-1 if F[f]["il"] is None else F[f]["il"] for f in range(f0, f1 + 1)]),
                        xc=np.array([F[f]["xc"] for f in range(f0, f1 + 1)]), yc=np.array([F[f]["yc"] for f in range(f0, f1 + 1)]))
    # ---- 取り置いたコマの組（V5）：r_bake.py の blend_pair と同じ目印
    last_interp_k = (K - 2) if K is not None else f1 - 1
    def marks(ka, kb):
        A, B = F[ka], F[kb]
        la, lb = [A["ic"]], [B["ic"]]
        if A["il"] is not None and B["il"] is not None and A["il"] > A["ic"] and B["il"] > B["ic"]:
            la.append(A["il"]); lb.append(B["il"])
        return la, lb
    entries, arrs = [], []
    for k in range(f0, f1 + 1):
        if k + 2 > last_interp_k + 1:
            break
        for step, alphas in ((2, [0.5]), (3, [1 / 3, 2 / 3])):
            kb = k + step
            if kb > last_interp_k + 1:
                continue
            la, lb = marks(k, kb)
            Pa, Pb, mk = L.resample_pair(F[k]["main"], la, F[kb]["main"], lb)
            arrs.append(np.stack([np.stack([Pa[:, 0] - L.X0_BAKE, Pa[:, 1]], 1), np.stack([Pb[:, 0] - L.X0_BAKE, Pb[:, 1]], 1)], 0))
            entries.append(dict(i=len(entries), k=k, kb=kb, step=step, alphas=alphas,
                                targets=[k + 1] if step == 2 else [k + 1, k + 2], n_marks=len(la)))
    H = np.stack(arrs, 0).astype("<f4")
    H.tofile(os.path.join(out_dir, "holdout_pairs.bin"))
    json.dump(dict(source=src_name, n=len(entries), n_points=L.N_PTS, x_origin=L.X0_BAKE, K=K, last_interp_k=last_interp_k,
                   layout="float32 LE (n, 2, N, 2)：[組][A, B][点][X, Y]、X = x_rel − 527.0", entries=entries),
              open(os.path.join(out_dir, "holdout_index.json"), "w", encoding="utf8"), ensure_ascii=False, indent=0)
    print("holdout", len(entries), "pairs", H.shape, round(time.time() - T0, 1), "s", flush=True)
    # ---- C6 の時刻（V6）
    pairs = man["pairs"]
    fps = man["time"]["fps"]
    t_k = lambda k: (k - 1) / fps
    interp_k = [p["k"] for p in pairs if p["interp"]]
    held_k = [p["k"] for p in pairs if (not p["interp"]) and p["reason"] != "after_K"]
    pick = lambda lst, n: [lst[int(round(i))] for i in np.linspace(0, len(lst) - 1, n)]
    c6 = {}
    for seat, b in man["boat"].items():
        end = b["clip_end_t"]
        ts = [dict(t=t_k(k) + 0.37 / fps, kind="interp_pair", k=k) for k in pick(interp_k, 5)]
        ts += [dict(t=t_k(k) + 0.37 / fps, kind="held_pair_before_K", k=k) for k in pick(held_k, 5)]
        tK = t_k(K)
        ts += [dict(t=tK + (i + 0.5) * (end - tK) / 10.0, kind="after_K") for i in range(10)]
        c6[seat] = dict(seat_x=float(seat), clip_end_t=end, times=ts)
    json.dump(dict(source=src_name, K=K, rule="V6：K の前 10（補間する組 5・補間しない組 5、割合／進み 0.37）、K から先 10（K の時刻から座席の終わりまでを 10 等分した区間の真ん中）",
                   seats=c6), open(os.path.join(out_dir, "c6_times.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print("done", round(time.time() - T0, 1), "s")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "coarse")
