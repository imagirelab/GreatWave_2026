# -*- coding: utf-8 -*-
"""設計39 第「紙」部の評価（numpy/OpenCV/scikit-image。Unity の描画は DS39Render・DS39PerfRunner）。

  1) 切ったら同じ：全部切の t* の画像の組（t28_white・t28_claws の 10 枚ずつ）を、設計38 の同じ名前の画像と画素で比べる。
  2) 入切の画像：視点ごとに {①, ②, ③, 全部} と全部切の ΔE00（CIEDE2000、sRGB → Lab、D65）の平均・p95・最大と、ΔE00 > 2・> 5 の画素の割合（記録）。
  3) 泳がない（頭の揺れ ±0.1 m）：同じ時刻で目の位置だけ違う 2 枚（dx_i, dx_j）で、模様の係数 F = 入の明るさ / 切の明るさ（利得 6 で強めた描画）を、
     ・面の同じ点どうし（面の座標の描画：シートの番号・列・行が同じ画素 q）で比べた差 E_面 = 中央値 |F_i(p) − F_j(q)|
     ・画面の同じ画素どうしで比べた差 E_画面 = 中央値 |F_i(p) − F_j(p)|
     の比 S = E_面 / E_画面 を求める。模様が面に付いていれば E_面 は小さく（描画の標本化の差だけ）、画面に貼り付いていれば E_画面 が 0 に近くなる。
     使う画素：両方のコマで主役波・near・far の面（爪・背景・空を除く）、切の明るさ ≥ 0.08、画面の移り |p − q| ≥ 2 px、
     面の座標の差が 1/4 格子以内。合格の定義（進行役の既定値、計算の前に決めた）：S ≤ 0.35（①・② のそれぞれ、2 視点、全部の組）。
  4) GPU 時間：プレイヤーの JSON（run_ds39_player.ps1）から、設計35 と同じ数え方（各条件の先頭 8 件を除く、GPU は 0 より大きく 1 s 未満）で、
     条件ごとの GPU の中央値・平均・p95 と、基準（全部切）との差。
使い方（リポジトリの根で）： py -3.10 -B Tools/GWWaveGen/ds39/ds39_eval.py [--perf run1,run2]
出力：Unity/Build/Design/39/paper/ds39_paper_metrics.json と fig/。
"""
import argparse
import glob
import hashlib
import json
import os
import time

import cv2
import numpy as np
from skimage.color import deltaE_ciede2000, rgb2lab

REPO = "G:/Unity/GreatWave_2026_Fresh"
OUT = REPO + "/Unity/Build/Design/39/paper"
U = OUT + "/unity"
R38 = REPO + "/Unity/Build/Design/38/outlines/unity"
IMAGES = ["af28r01_painting.png", "af28r01_seat.png", "af28r01_seat_low.png", "af28r01_painting_kstar.png", "af28r01_seat_kstar.png",
          "af28r01_seat_low_kstar.png", "af28r01_class_ids.png", "af28r01_seat_class_ids.png", "af28r01_seat_low_class_ids.png", "af28r01_line_ids.png"]
W, H = 1920, 1080
S_MAX = 0.35


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rgb(p):
    im = cv2.imread(p, cv2.IMREAD_COLOR)
    return cv2.cvtColor(im, cv2.COLOR_BGR2RGB)


def identity():
    res = {}
    for st in ("t28_white", "t28_claws"):
        rows = []
        for n in IMAGES:
            a = cv2.imread(os.path.join(U, st, "t28", "render", n), cv2.IMREAD_UNCHANGED)
            b = cv2.imread(os.path.join(R38, st, "t28", "render", n), cv2.IMREAD_UNCHANGED)
            if a is None or b is None:
                rows.append(dict(image=n, missing=True)); continue
            d = np.abs(a.astype(np.int16) - b.astype(np.int16))
            rows.append(dict(image=n, diff_px=int((d.max(-1) > 0).sum()) if d.ndim == 3 else int((d > 0).sum()), max_abs=int(d.max()),
                             same_pixels=bool(d.max() == 0), sha_ds39=sha(os.path.join(U, st, "t28", "render", n))[:16],
                             sha_ds38=sha(os.path.join(R38, st, "t28", "render", n))[:16]))
        res[st] = rows
    res["all_same_pixels"] = all(r.get("same_pixels", False) for st in ("t28_white", "t28_claws") for r in res[st])
    return res


def de00(a, b):
    la = rgb2lab(a.astype(np.float32) / 255.0); lb = rgb2lab(b.astype(np.float32) / 255.0)
    return deltaE_ciede2000(la, lb)


def onoff():
    out = {}
    for p in sorted(glob.glob(U + "/onoff/ds39_*_off.png")):
        base = os.path.basename(p)[:-len("_off.png")]
        off = rgb(p)
        rec = {}
        for cond in ("paper", "mura", "spray", "all"):
            q = p.replace("_off.png", "_" + cond + ".png")
            if not os.path.exists(q):
                continue
            d = de00(rgb(q), off)
            rec[cond] = dict(mean=round(float(d.mean()), 4), p95=round(float(np.percentile(d, 95)), 4), max=round(float(d.max()), 3),
                             frac_gt2=round(float((d > 2).mean()), 5), frac_gt5=round(float((d > 5).mean()), 5))
        out[base] = rec
    return out


def load_coord(p):
    a = np.fromfile(p, np.float32).reshape(H, W, 2)
    sid = np.floor(a[..., 0] / 2000.0 + 1e-4).astype(np.int32)
    col = a[..., 0] - 2000.0 * sid
    return sid, col, a[..., 1]


def lum(im):
    return im.astype(np.float32).mean(-1) / 255.0


def swim(Q=64.0):
    """頭の揺れの検査（定義は冒頭の 3)。修正前の最初の定義の読みは下の note_ja）。
    面の表 T_A：コマ A の係数 F_A を、面の座標（シートの番号・列・行）の細かい升（格子の 1/64）ごとに平均したもの。
    コマ B の各画素 p を、その面の座標の升の T_A で予測した差 d_面 = F_B(p) − T_A(升(p)) と、画面の同じ画素の差 d_画面 = F_B(p) − F_A(p) の RMS を比べる。
    模様が面に付いていれば d_面 は描画の標本化・8 bit の丸めだけ（小さい）。画面に貼り付いていれば d_画面 が小さく d_面 が大きい。
    指標：S = RMS(d_面) / RMS(d_画面)、N = RMS(d_面) / std(F_B)。合格：① S ≤ 0.35 かつ N ≤ 0.35、② N ≤ 0.35（② は低い周波数なので画面の移り
    8〜40 px では d_画面 自体が小さく、S は記録のみ）。画面の対照：画面に貼り付いた模様（F_B = F_A をそのまま画面の同じ画素に置いたもの）の N も記録する。"""
    res = {}
    fig_pairs = {}
    for view_t in ("seat_toward_wave_t090", "seat_t120"):
        dxs = ["-100", "-050", "+000", "+050", "+100"]
        fr = {}
        for dx in dxs:
            tag = U + "/swim/swim_%s_dx%s" % (view_t, dx)
            if not os.path.exists(tag + "_coord.bin"):
                continue
            sid, col, row = load_coord(tag + "_coord.bin")
            off = lum(rgb(tag + "_off.png"))
            fr[dx] = dict(sid=sid, col=col, row=row, off=off,
                          F={c: lum(rgb(tag + "_" + c + ".png")) / np.maximum(off, 1e-3) for c in ("paper", "mura")})
        pairs = [("-100", "+100"), ("-050", "+050"), ("-100", "+000"), ("+000", "+100")]
        vr = {}
        for (i, j) in pairs:
            if i not in fr or j not in fr:
                continue
            A, B = fr[i], fr[j]
            def keys(X, m):
                ys, xs = np.nonzero(m)
                k = (X["sid"][ys, xs].astype(np.int64) * 10 ** 10 + np.floor(X["col"][ys, xs] * Q).astype(np.int64) * 10 ** 5
                     + np.floor(X["row"][ys, xs] * Q).astype(np.int64))
                return ys, xs, k
            # 縁（面の座標の不連続・MSAA の混ざり）を避ける：シートの内側（7×7 で同じシート。ぼかしの読みのため）かつ明るさ ≥ 0.08
            def interior(X):
                m = (X["sid"] >= 1) & (X["sid"] <= 3) & (X["off"] >= 0.08)
                er = cv2.erode(m.astype(np.uint8), np.ones((7, 7), np.uint8))
                return er > 0
            ma, mb = interior(A), interior(B)
            ya, xa, ka = keys(A, ma)
            yb, xb, kb = keys(B, mb)
            # 升ごとに B の画素の予測（A の平均）
            ua, inv = np.unique(ka, return_inverse=True)
            cnt = np.bincount(inv)
            pos = np.searchsorted(ua, kb); pos = np.clip(pos, 0, len(ua) - 1)
            hit = ua[pos] == kb
            yb, xb, pos = yb[hit], xb[hit], pos[hit]
            both = ma[yb, xb]          # 画面の同じ画素も A で面の内側
            yb, xb, pos = yb[both], xb[both], pos[both]
            rec = dict(n_px=int(len(yb)), bins=int(len(ua)), px_per_bin_median=float(np.median(cnt)))
            # 画面の移り（升の A の平均の画素の位置との差）
            sx = np.bincount(inv, weights=xa) / cnt; sy = np.bincount(inv, weights=ya) / cnt
            disp = np.hypot(sx[pos] - xb, sy[pos] - yb)
            rec["disp_px_median"] = round(float(np.median(disp)), 2); rec["disp_px_p95"] = round(float(np.percentile(disp, 95)), 2)
            for c in ("paper", "mura"):
                Fa, Fb = A["F"][c], B["F"][c]
                T = np.bincount(inv, weights=Fa[ya, xa]) / cnt
                fb = Fb[yb, xb]
                d_surf = fb - T[pos]
                d_scr = fb - Fa[yb, xb]
                sd = float(np.std(fb))
                # 画面に貼り付いた模様の対照：B の画素に A の同じ画素の値があるとして、面の表で予測した差
                d_ctrl = Fa[yb, xb] - T[pos]
                rs, rc, rk = float(np.sqrt(np.mean(d_surf ** 2))), float(np.sqrt(np.mean(d_scr ** 2))), float(np.sqrt(np.mean(d_ctrl ** 2)))
                S = rs / rc if rc > 0 else None
                N = rs / sd if sd > 0 else None
                ok = (N is not None and N <= S_MAX) and (c != "paper" or (S is not None and S <= S_MAX))
                rec[c] = dict(rms_surface=round(rs, 5), rms_screen=round(rc, 5), F_std=round(sd, 5), S=round(S, 4) if S is not None else None,
                              N=round(N, 4) if N is not None else None, N_screen_fixed_control=round(rk / sd, 4) if sd > 0 else None, pass_=bool(ok))
                # 記録：1 画素より細かい標本化の差を除いた読み（F を σ 1.5 px でぼかしてから同じ計算。画面の移り 6〜39 px よりずっと小さいぼかし）
                Fab, Fbb = cv2.GaussianBlur(Fa.astype(np.float32), (0, 0), 1.5), cv2.GaussianBlur(Fb.astype(np.float32), (0, 0), 1.5)
                Tb = np.bincount(inv, weights=Fab[ya, xa]) / cnt
                fbb = Fbb[yb, xb]
                rs2 = float(np.sqrt(np.mean((fbb - Tb[pos]) ** 2))); rc2 = float(np.sqrt(np.mean((fbb - Fab[yb, xb]) ** 2))); sd2 = float(np.std(fbb))
                rk2 = float(np.sqrt(np.mean((Fab[yb, xb] - Tb[pos]) ** 2)))
                rec[c]["blur1p5"] = dict(S=round(rs2 / rc2, 4) if rc2 > 0 else None, N=round(rs2 / sd2, 4) if sd2 > 0 else None,
                                         N_screen_fixed_control=round(rk2 / sd2, 4) if sd2 > 0 else None)
                # 記録：シートごと（1 主役波・2 near・3 far）の N と画素の数
                sb = B["sid"][yb, xb]
                rec[c]["by_sheet"] = {str(k): dict(n=int((sb == k).sum()), N=round(float(np.sqrt(np.mean(d_surf[sb == k] ** 2)) / max(np.std(fb[sb == k]), 1e-9)), 4))
                                      for k in (1, 2, 3) if (sb == k).sum() > 1000}
                rec[c]["corr_surface"] = round(float(np.corrcoef(fb, T[pos])[0, 1]), 4)
                rec[c]["corr_screen"] = round(float(np.corrcoef(fb, Fa[yb, xb])[0, 1]), 4)
            vr[i + "_vs_" + j] = rec
        res[view_t] = vr
        if "-100" in fr and "+100" in fr:
            fig_pairs[view_t] = (fr["-100"], fr["+100"])
    allp = [r[c]["pass_"] for v in res.values() for r in v.values() for c in ("paper", "mura")]
    res["S_N_max_def"] = S_MAX
    res["Q_bins_per_cell"] = Q
    res["gain"] = "描画の利得 15（DS39Render の SwimGain。作品の描画は 1）"
    res["all_pass"] = bool(allp) and all(allp)
    res["worst"] = {c: dict(S=max(r[c]["S"] for k, v in res.items() if isinstance(v, dict) and k.startswith("seat") for r in v.values()),
                            N=max(r[c]["N"] for k, v in res.items() if isinstance(v, dict) and k.startswith("seat") for r in v.values())) for c in ("paper", "mura")}
    res["note_ja"] = ("最初の定義（面の座標を 1/4 格子の升で 1 画素に対応させ、中央値の絶対差 E_面/E_画面 ≤ 0.35）は、利得 6 の描画で 8 bit の丸めが模様の振れと"
                      "同じ大きさになり、升が紙の地の粒より粗く、② は画面の移りでほとんど変わらず E_画面 = 0 になって判定できなかった（受入の判定の前の測り方の直し。"
                      "修正の回に数えない）。利得を 15 に上げ、升を面の表の予測に替えた。その升を 1/16 格子にした 2 回目の読みでは、near のシート（44 行 × 1,231 列の粗い格子）"
                      "の升が紙の地の粒（2.5〜7 cm）より大きく、表の予測そのものが粒をならしてしまい、N が 0.54 になった（升を 1/64・1/256 にすると 0.24・0.11 へ下がる。"
                      "Q_sweep）。模様が面からずれているのではなく升の粗さによるので、升を 1/64 格子にした（これも受入の判定の前の測り方の直し）。")
    return res, fig_pairs


def perf(tags):
    out = {}
    for tag in tags:
        p = OUT + "/perf/%s/ds39_%s.json" % (tag, tag)
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding="utf-8-sig"))
        rows = {}
        for c in d.get("conditions", []):
            g = np.array(c["ftGpu"][8:], float)
            g = g[(g > 0) & (g < 1000)]
            st = np.array(c["ftStart"][8:], np.float64)
            iv = np.diff(st) / c["cpuTimerFrequency"] * 1000.0 if len(st) > 1 else np.array([])
            rows[c["variant"] + "|" + c["name"]] = dict(
                gpu_n=int(len(g)), gpu_zero_frac=round(float(1 - len(g) / max(1, len(c["ftGpu"][8:]))), 4),
                gpu_median_ms=round(float(np.median(g)), 4), gpu_mean_ms=round(float(g.mean()), 4), gpu_p95_ms=round(float(np.percentile(g, 95)), 4),
                fps_mean=round(float(1000.0 / iv.mean()), 1) if len(iv) else None, interval_p95_ms=round(float(np.percentile(iv, 95)), 4) if len(iv) else None,
                spray_count=c.get("sprayCount"), spray_alive_max=c.get("sprayAliveMax"))
        out[tag] = dict(device=d.get("device"), isDebugBuild=d.get("isDebugBuild"), error=d.get("errorJa"), rows=rows)
    # 基準との差（条件ごと・回ごと）
    delta = {}
    for tag, v in out.items():
        for key, r in v["rows"].items():
            var, cond = key.split("|")
            b = v["rows"].get("base|" + cond)
            if b is None or var == "base":
                continue
            delta.setdefault(var, {}).setdefault(cond, {})[tag] = dict(
                d_median_ms=round(r["gpu_median_ms"] - b["gpu_median_ms"], 4), d_mean_ms=round(r["gpu_mean_ms"] - b["gpu_mean_ms"], 4),
                d_p95_ms=round(r["gpu_p95_ms"] - b["gpu_p95_ms"], 4))
    return out, delta


def crop(im, box):
    x0, y0, x1, y1 = box
    return im[y0:y1, x0:x1]


def label(im, text):
    im = im.copy()
    cv2.rectangle(im, (0, 0), (im.shape[1], 34), (255, 255, 255), -1)
    cv2.putText(im, text, (8, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2, cv2.LINE_AA)
    return im


def figs(fig_pairs):
    fd = OUT + "/fig"
    os.makedirs(fd, exist_ok=True)
    made = []
    # 入切の並べ（視点ごと：切・①・②・③・全部 と、①② の差の強調）
    for p in sorted(glob.glob(U + "/onoff/ds39_*_off.png")):
        base = os.path.basename(p)[:-len("_off.png")]
        ims = []
        for cond, name in (("off", "OFF (= DS38)"), ("paper", "(1) paper grain ON"), ("mura", "(2) print unevenness ON"), ("spray", "(3) small spray x2.7 ON"), ("all", "(1)(2)(3) ALL ON")):
            q = p.replace("_off.png", "_" + cond + ".png")
            if os.path.exists(q):
                ims.append(label(cv2.resize(cv2.imread(q), (960, 540), interpolation=cv2.INTER_AREA), name))
        off = cv2.imread(p).astype(np.float32)
        al = cv2.imread(p.replace("_off.png", "_all.png")).astype(np.float32)
        diff = np.clip(128 + 8 * (al - off).mean(-1, keepdims=True), 0, 255).repeat(3, -1).astype(np.uint8)
        ims.append(label(cv2.resize(diff, (960, 540), interpolation=cv2.INTER_AREA), "ALL - OFF (x8, grey = 0)"))
        grid = np.vstack([np.hstack(ims[0:2]), np.hstack(ims[2:4]), np.hstack(ims[4:6])])
        grid = cv2.resize(grid, (1920 * 540 // 1620 * 2, 1620 * 540 // 1620 * 2)) if False else grid
        fp = fd + "/fig_ds39_onoff_%s.png" % base.replace("ds39_", "")
        cv2.imwrite(fp, cv2.resize(grid, (1280, 1080), interpolation=cv2.INTER_AREA) if grid.shape[0] > 1080 else grid)
        made.append(fp)
    # 拡大（原画視点 t* の主役波の唇の周り、座席 t*）
    for base, box in (("ds39_painting_t120", (700, 250, 1180, 520)), ("ds39_seat_t120", (700, 200, 1340, 560))):
        p = U + "/onoff/" + base + "_off.png"
        if not os.path.exists(p):
            continue
        row = []
        for cond, name in (("off", "OFF"), ("paper", "(1) paper"), ("mura", "(2) mura"), ("all", "ALL")):
            im = crop(cv2.imread(p.replace("_off.png", "_" + cond + ".png")), box)
            im = cv2.resize(im, (im.shape[1] * 960 // im.shape[1], im.shape[0] * 960 // im.shape[1]), interpolation=cv2.INTER_NEAREST)
            row.append(label(im, name))
        grid = np.vstack([np.hstack(row[0:2]), np.hstack(row[2:4])])
        fp = fd + "/fig_ds39_zoom_%s.png" % base.replace("ds39_", "")
        cv2.imwrite(fp, grid)
        made.append(fp)
    # 泳がない：dx −0.1 と +0.1 の係数 F（① 利得 6）と、面の点で重ねた差・画面の画素で重ねた差
    for view_t, (A, B) in fig_pairs.items():
        tiles = []
        for c in ("paper", "mura"):
            Fa, Fb = A["F"][c], B["F"][c]
            va = (A["sid"] >= 1) & (A["sid"] <= 3)
            vb = (B["sid"] >= 1) & (B["sid"] <= 3)
            def vis(F, v):
                g = np.clip(128 + 200 * (F - 1.0), 0, 255).astype(np.uint8)
                g = np.where(v, g, 40).astype(np.uint8)
                return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
            scr = np.clip(128 + 200 * (Fa - Fb), 0, 255).astype(np.uint8)
            scr = cv2.cvtColor(np.where(va & vb, scr, 40).astype(np.uint8), cv2.COLOR_GRAY2BGR)
            tiles += [label(cv2.resize(vis(Fa, va), (960, 540), interpolation=cv2.INTER_AREA), "%s gain15  eye -0.1 m" % c),
                      label(cv2.resize(vis(Fb, vb), (960, 540), interpolation=cv2.INTER_AREA), "%s gain15  eye +0.1 m" % c),
                      label(cv2.resize(scr, (960, 540), interpolation=cv2.INTER_AREA), "%s: same screen pixel diff" % c)]
        grid = np.vstack([np.hstack(tiles[0:3]), np.hstack(tiles[3:6])])
        fp = fd + "/fig_ds39_swim_%s.png" % view_t
        cv2.imwrite(fp, cv2.resize(grid, (1920, 720), interpolation=cv2.INTER_AREA))
        made.append(fp)
    return made


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--perf", default="")
    ap.add_argument("--skip", default="")
    args = ap.parse_args()
    t0 = time.time()
    skip = set(args.skip.split(",")) if args.skip else set()
    mp = OUT + "/ds39_paper_metrics.json"
    m = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
    m["schema"] = "GreatWave.DS39.paper_metrics/1"
    if "identity" not in skip:
        m["identity_off_vs_ds38"] = identity()
        print("identity", m["identity_off_vs_ds38"]["all_same_pixels"])
    if "onoff" not in skip:
        m["onoff_de00_vs_off"] = onoff()
        print("onoff done")
    fp = {}
    if "swim" not in skip:
        m["swim"], fp = swim()
        sweep = {}
        for q in (16.0, 64.0, 256.0):
            r, _ = swim(q)
            sweep[str(int(q))] = {v: dict(paper_S=r[v]["-100_vs_+100"]["paper"]["S"], paper_N=r[v]["-100_vs_+100"]["paper"]["N"],
                                          mura_N=r[v]["-100_vs_+100"]["mura"]["N"], n_px=r[v]["-100_vs_+100"]["n_px"],
                                          paper_N_screen_fixed_control=r[v]["-100_vs_+100"]["paper"]["N_screen_fixed_control"],
                                          paper_by_sheet=r[v]["-100_vs_+100"]["paper"]["by_sheet"])
                                  for v in ("seat_toward_wave_t090", "seat_t120")}
        m["swim_Q_sweep_pair_m100_p100"] = sweep
        print("swim", m["swim"]["all_pass"], m["swim"]["worst"])
    if args.perf:
        m["perf"], m["perf_delta_vs_base"] = perf(args.perf.split(","))
        print(json.dumps(m["perf_delta_vs_base"], ensure_ascii=False))
    if "fig" not in skip:
        m["figures"] = figs(fp)
    m["eval_seconds"] = round(time.time() - t0, 1)
    json.dump(m, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote", mp, m["eval_seconds"])


if __name__ == "__main__":
    main()
