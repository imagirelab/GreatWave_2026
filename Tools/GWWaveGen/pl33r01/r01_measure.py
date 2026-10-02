# -*- coding: utf-8 -*-
"""仕上げ33修正01 修正の回 1：断面の向きと跳び（指摘 6・10）を、SWEEP の輪の頂点の並びに合った式で測り直す（numpy。記録）。

SWEEP と修正の回 1 の指（C…）・冠の爪（K…）の輪は、8 頂点の角度が不揃い（−82, −50, 90, 230, 262, 266, 270, 274°）なので、
8 頂点の平均は輪の中心でない（pl33f_measure.py の orient・bends・貫通は平均を中心に使っていた）。ここでは輪の中心を頂点 2（白の中心、+N）と
頂点 6（水色の版の中心、−N）の中点とし、白の向き N を（頂点 2 − 中心）で測る。
  - コマの間の裏返り：同じ輪の N の、隣のコマとの内積が 0 未満（輪の大きさ 1 cm 以上、背骨の長さ 0.2 m 以上のコマ）
  - 隣の輪の間のねじれ：N から接線（隣の中心へ向く向き）の成分を除いた向きの、隣の輪との角が 60° を超える
  - 跳び（評審 judge_geo2 と同じ式）：根元の頂点に対する頂点の 2 階差 > 0.15 m/コマ²。中心の 2 階差と、輪の回り（頂点 − 中心）の 2 階差に分ける
  - 瞬間移動（根元に対して 1 コマに 0.5 m 超）・NaN
出力：--out の json
使い方：py -3.10 -B Tools/GWWaveGen/pl33r01/r01_measure.py --claws <爪の並び> [--claws2 …] --out <json>
"""
import argparse
import json
import os

import numpy as np


def measure(claws):
    lay = json.load(open(os.path.join(claws, "ds33_claw_layout.json"), encoding="utf-8"))
    F, V = lay["frames"], lay["vertices"]
    Y = np.memmap(os.path.join(claws, lay["files"]["frames"]["file"]), dtype=np.float32, mode="r", shape=(F, V, 3))
    res = {}
    for pre in ("C", "K", "W"):
        flips = twists = 0
        flip_ids, twist_ids = {}, {}
        ev_c = ev_rot = 0
        ev_ids = {}
        tele = nan = 0
        worst = (0.0, None, None)
        n_ent = 0
        for c in lay["claws"]:
            if not c["id"].startswith(pre):
                continue
            n_ent += 1
            o, n, nv = c["vert_offset"], c["stations"], c["vert_count"]
            A = np.asarray(Y[:, o:o + nv], np.float64)
            nan += int(np.isnan(A).sum())
            rel = A - A[:, :1]
            rg = rel[:, 1:1 + n * 8].reshape(F, n, 8, 3)
            if pre in ("C", "K"):
                cen = 0.5 * (rg[:, :, 2] + rg[:, :, 6])
                Nv = rg[:, :, 2] - cen
            else:
                cen = rg.mean(2)
                Nv = rg[:, :, 0] - cen
            size = np.linalg.norm(Nv, axis=2)
            Lf = np.linalg.norm(np.diff(cen, axis=1), axis=2).sum(1)
            # 生まれたばかりで背骨の長さ 0.2 m 未満のコマ（輪が根元に重なった円盤）は向きが決まらないので数えない
            ok = (size > 0.005) & (Lf[:, None] > 0.2)
            Nu = Nv / np.maximum(size, 1e-12)[..., None]
            if pre in ("C", "K"):
                okf = ok[1:] & ok[:-1]
                fl = ((Nu[1:] * Nu[:-1]).sum(2) < 0) & okf
                flips += int(fl.sum())
                if fl.any():
                    flip_ids[c["id"]] = int(fl.sum())
                T = np.zeros_like(cen)
                T[:, 1:-1] = cen[:, 2:] - cen[:, :-2]
                T[:, 0] = cen[:, 1] - cen[:, 0]
                T[:, -1] = cen[:, -1] - cen[:, -2]
                T /= np.maximum(np.linalg.norm(T, axis=2, keepdims=True), 1e-12)
                Np = Nu - (Nu * T).sum(2, keepdims=True) * T
                Np /= np.maximum(np.linalg.norm(Np, axis=2, keepdims=True), 1e-12)
                okr = ok[:, 1:] & ok[:, :-1]
                tw = ((Np[:, 1:] * Np[:, :-1]).sum(2) < 0.5) & okr
                twists += int(tw.sum())
                if tw.any():
                    twist_ids[c["id"]] = int(tw.sum())
            # 跳び
            a_all = np.linalg.norm(rel[2:] - 2 * rel[1:-1] + rel[:-2], axis=2).max(1)
            a_cen = np.linalg.norm(cen[2:] - 2 * cen[1:-1] + cen[:-2], axis=2).max(1)
            hit = a_all > 0.15
            ev_c += int((hit & (a_cen > 0.15)).sum())
            ev_rot += int((hit & (a_cen <= 0.15)).sum())
            if hit.any():
                ev_ids[c["id"]] = [int(hit.sum()), round(float(a_all.max()), 3), int(np.argmax(a_all) + 1)]
            if a_all.max() > worst[0]:
                worst = (float(a_all.max()), c["id"], int(np.argmax(a_all) + 1))
            d1 = np.linalg.norm(np.diff(rel, axis=0), axis=2).max(1)
            tele += int((d1 > 0.5).sum())
        res[pre] = dict(entries=n_ent, frame_flips=flips, ring_twists_gt60=twists,
                        flip_entries=len(flip_ids), twist_entries=len(twist_ids),
                        flip_top=sorted(flip_ids.items(), key=lambda x: -x[1])[:8], twist_top=sorted(twist_ids.items(), key=lambda x: -x[1])[:8],
                        accel_events_gt0p15=ev_c + ev_rot, accel_events_centre=ev_c, accel_events_rotation_only=ev_rot,
                        accel_entries=len(ev_ids), accel_top=sorted(ev_ids.items(), key=lambda x: -x[1][1])[:10],
                        accel_worst=dict(m=round(worst[0], 3), id=worst[1], frame=worst[2]), teleports_gt0p5m=tele, nan=nan)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--claws", action="append", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = {"rule_ja": __doc__.strip().split("\n\n")[1]}
    for d in a.claws:
        out[d.replace("\\", "/").split("Build/Polish/")[-1]] = measure(d)
        print(d, json.dumps(out[d.replace("\\", "/").split("Build/Polish/")[-1]], ensure_ascii=False), flush=True)
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
