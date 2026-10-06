# -*- coding: utf-8 -*-
"""段階 Video の追加：選んだ瞬間 t* の最終の P3 の水面（＋外の海）を、原画カメラ以外のカメラから見たらどう読めるかの比べ（新しい計算はしない）。py -3.10

本番のカメラ（PaintingCam v1）は変えない。ここで作るのは比べの表と一覧の図だけ。

カメラの決め方（どのカメラも「原画の中の巻きの写り方」を保つ）:
- 置き方（計算 → Unity）は t* のもの（plan.json の placement）のまま。頂 A（t* の z=0 の頂）と、その真下の静かな水面の点 G。
- カメラの位置：G から水平に距離 D、目の高さ h。水平の向きは v1 の向き（G → v1 のカメラ）を角 δ だけ回したもの（δ<0 で峰に沿う向きへ。
  δ ≈ −37° で峰の線の上から峰に沿って見る）。
- 向き（傾きなし）と縦の画角：A が原画の頂の画素 (766, 93) に写り、A と G の画面の上下の距離が v1 と同じ（巻きの大きさが同じ）になるように解く。
  画角は焦点距離（35 mm 判の換算）でも記録する。
点数は p2_common と同じ（原画の大波の面との IoU、原画の輪郭の点からシルエットの縁までの平均距離。比べる窓の中、960×540 で塗る、
網目は頂の x から −160〜+90 m）。カメラの真下に水があってカメラの高さを越えるもの（カメラが水の中）は順位から除く。

使い方: py -3.10 video_camsweep.py <video の config.json> [--quick]
出力: <out_dir>/camsweep/camsweep.json（全部のカメラ）、camsweep_top6.png（1920×1080、上位 6 と原画）、render/（粘土の図）
"""
import os, sys, json, math, time, subprocess, hashlib
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import video_common as V  # noqa: E402
import p2_common as C  # noqa: E402
import video_make as M  # noqa: E402

D_LIST = [66.0, 90.0, 130.0, 180.0, 250.0, 350.0, 500.0]
H_LIST = [3.0, 6.0, 10.0, 15.0]
DELTA_LIST = [-60.0, -45.0, -37.0, -30.0, -25.0, -20.0, -15.0, 0.0, 15.0, 30.0, 45.0]


def yaw_pitch(v):
    return math.atan2(v[0], v[2]), math.asin(max(-1.0, min(1.0, v[1] / np.linalg.norm(v))))


def from_yp(yaw, pitch):
    return np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])


def solve_cam(eye, A, G, hpx0, vfov0):
    """A が CREST_PX、|py(G) − py(A)| = hpx0 になる向き（傾きなし）と縦の画角を解く（1920×1080 の画素）。"""
    vf = vfov0
    f = (A - eye) / np.linalg.norm(A - eye)
    for _ in range(60):
        cam = C.Cam(eye, f, (0, 1, 0), vf)
        r = cam.ray(C.CREST_PX)[0]
        ya, pa = yaw_pitch(A - eye); yr, pr = yaw_pitch(r)
        yf, pf = yaw_pitch(f)
        dy = (ya - yr + math.pi) % (2 * math.pi) - math.pi
        f = from_yp(yf + dy, max(-1.4, min(1.4, pf + (pa - pr))))
        cam = C.Cam(eye, f, (0, 1, 0), vf)
        (pA, pG), _ = cam.project(np.stack([A, G]))
        hpx = pG[1] - pA[1]
        if hpx > 1:
            t = math.tan(math.radians(vf) / 2) * hpx / hpx0
            vf = math.degrees(2 * math.atan(t))
            vf = max(0.5, min(120.0, vf))
    cam = C.Cam(eye, f, (0, 1, 0), vf)
    (pA, pG), _ = cam.project(np.stack([A, G]))
    return cam, {"crest_px_err": float(np.hypot(*(pA - C.CREST_PX))), "hpx": float(pG[1] - pA[1])}


def horizon_y(cam):
    """水平線（目の高さの遠くの点）の画面の y（1920×1080）。"""
    fh = np.array([cam.f[0], 0.0, cam.f[2]]); fh /= np.linalg.norm(fh)
    (p,), _ = cam.project(cam.pos[None] + 1e5 * fh[None])
    return float(p[1])


def to_sim(Uxz, pl):
    """Unity の点（x, z）→ 計算の座標（x, z）。"""
    T = np.array(pl["T"]); E = np.array(pl["E"]); O = np.array(pl["O"]); s = pl["scale"]; a = pl["anchor"]
    Q = (np.array([Uxz[0], 0.0, Uxz[1]]) - O) / s
    return float(Q @ T + a[0]), float(Q @ E + a[2])


def main():
    cfgp = sys.argv[1]
    quick = "--quick" in sys.argv
    cfg = V.load_cfg(cfgp)
    out = os.path.join(cfg["out_dir"], "camsweep"); os.makedirs(out, exist_ok=True)
    p = json.load(open(os.path.join(cfg["out_dir"], "plan.json"), encoding="utf8"))
    pl = p["placement"]
    ts = p["marks"]["t_star"]
    tl = [tuple(q) for q in p["timeline"]]
    t_, path, si = V.mesh_at(tl, ts)
    outer = (p.get("outer") or {}).get(path)
    P, tri = V.load_frame(path, outer)
    a = pl["anchor"]
    keep = (P[:, 0] > a[0] + V.X_KEEP[0]) & (P[:, 0] < a[0] + V.X_KEEP[1])
    tk = tri[keep[tri].all(1)]
    cam1 = C.painting_cam()
    U, O = C.place(P, a, pl["psi_deg"], pl["scale"], cam1)
    s = pl["scale"]
    G = np.array(O, float); A = G + np.array([0.0, s * a[1], 0.0])
    (pA1, pG1), _ = cam1.project(np.stack([A, G]))
    hpx0 = float(pG1[1] - pA1[1])
    d1 = np.array([cam1.pos[0] - G[0], cam1.pos[2] - G[2]]); D1 = float(np.linalg.norm(d1)); d1 /= D1
    pm, po, pi_ = C.painting_mask(V.SC)
    win = C.window_mask(V.SC)
    xs_min, xs_max = float(P[:, 0].min()), float(P[:, 0].max()); zs_min, zs_max = float(P[:, 2].min()), float(P[:, 2].max())

    def score(cam_full):
        """戻り：(IoU, 輪郭の平均距離, 水平線までの海を足した IoU, その輪郭の平均距離, 塗り)。
        水平線までの海：本当の海は水平線より下を全部埋める（水槽と点数の範囲の外にも海がある）ので、水平線より下の画面を流体に足した読み。"""
        cs = C.Cam(cam_full.pos, cam_full.f, (0, 1, 0), cam_full.vfov, int(C.W * V.SC), int(C.H * V.SC))
        m = C.raster_mask(cs, U, tk)
        mw = m & win
        iou = (mw & pm).sum() / max((mw | (pm & win)).sum(), 1)
        od = C.outline_distance(mw, po, pi_, V.SC) or {}
        hy = horizon_y(cam_full)
        m2 = m.copy()
        r0 = int(max(0, min(m.shape[0], math.ceil((hy + 0.5) * V.SC - 0.5))))
        m2[r0:, :] = True
        mw2 = m2 & win
        iou2 = (mw2 & pm).sum() / max((mw2 | (pm & win)).sum(), 1)
        od2 = C.outline_distance(mw2, po, pi_, V.SC) or {}
        return float(iou), od.get("mean_px"), float(iou2), od2.get("mean_px"), m

    rows = []
    if "--render-only" in sys.argv:
        # 点数は camsweep.json のまま、粘土の図と一覧だけ作り直す
        res = json.load(open(os.path.join(out, "camsweep.json"), encoding="utf8"))
        rows = res["rows"]; R = {r["name"]: r for r in rows}
        valid = [r for r in rows if r["valid"] and r["name"] != "v1"]
        by_od = sorted([r for r in valid if r["mean_px_hz"] is not None], key=lambda r: r["mean_px_hz"])
        render_sheets(res, rows, [R[n] for n in res["top6_by_iou_hz"]], [R[n] for n in res["top6_by_iou_wave_only"]], by_od, p, pl, path, out, cfg)
        return
    t0 = time.time()
    # v1 そのもの（基準）
    iou, md, iou2, md2, _ = score(cam1)
    rows.append({"name": "v1", "D": D1, "h": float(cam1.pos[1]), "delta": 0.0, "vfov": 26.0, "focal_mm": 12.0 / math.tan(math.radians(13.0)),
                 "eye": cam1.pos.tolist(), "fwd": cam1.f.tolist(), "iou": iou, "mean_px": md, "iou_hz": iou2, "mean_px_hz": md2,
                 "horizon_y": horizon_y(cam1),
                 "crest_px_err": float(np.hypot(*(pA1 - C.CREST_PX))), "valid": True, "note": "本番の原画カメラ PaintingCam v1"})
    print("v1", round(iou, 3), md, "hpx0", round(hpx0, 1), "D1", round(D1, 1))
    Ds = D_LIST if not quick else [66.0, 180.0]
    Hs = H_LIST if not quick else [3.0]
    Ws = DELTA_LIST if not quick else [-37.0, 0.0]
    for D in Ds:
        for h in Hs:
            for dl in Ws:
                c, sn = math.cos(math.radians(dl)), math.sin(math.radians(dl))
                dd = np.array([c * d1[0] - sn * d1[1], sn * d1[0] + c * d1[1]])
                eye = np.array([G[0] + D * dd[0], h, G[2] + D * dd[1]])
                cam, info = solve_cam(eye, A, G, hpx0, 26.0 * D1 / D)
                xs, zs = to_sim((eye[0], eye[2]), pl)
                inside = xs_min <= xs <= xs_max and zs_min <= zs <= zs_max
                e = V.eta_under(P, xs, zs, r=3.0)
                wet = bool(e is not None and e * s > h - 0.3)
                row = {"name": "D%03d_h%02d_d%+03d" % (D, h, dl), "D": D, "h": h, "delta": dl, "vfov": float(cam.vfov),
                       "focal_mm": 12.0 / math.tan(math.radians(cam.vfov) / 2), "eye": cam.pos.tolist(), "fwd": cam.f.tolist(),
                       "eye_sim_xz": [xs, zs], "in_tank": bool(inside), "eta_under_m": e, "camera_wet": wet,
                       "horizon_y": horizon_y(cam), **info}
                if wet or info["crest_px_err"] > 2.0:
                    row.update({"iou": None, "mean_px": None, "iou_hz": None, "mean_px_hz": None, "valid": False})
                else:
                    iou, md, iou2, md2, _ = score(cam)
                    row.update({"iou": iou, "mean_px": md, "iou_hz": iou2, "mean_px_hz": md2, "valid": True})
                rows.append(row)
                print(row["name"], row.get("iou"), row.get("mean_px"), row.get("iou_hz"), "vfov %.2f" % cam.vfov, "wet" if wet else "", flush=True)
    wall = time.time() - t0
    valid = [r for r in rows if r["valid"] and r["name"] != "v1"]
    # 順位は「水平線までの海を足した」IoU（iou_hz）で付ける。波だけの IoU（P2・P3 と同じ量）も別に記録する
    by_iou = sorted(valid, key=lambda r: -r["iou_hz"])
    by_od = sorted([r for r in valid if r["mean_px_hz"] is not None], key=lambda r: r["mean_px_hz"])
    by_iou_w = sorted(valid, key=lambda r: -r["iou"])

    def top6(lst):
        # 上位 6（D か δ が前に選んだものと違うもの。高さだけ違う同じ向き・距離は一つに）
        top = []
        for r in lst:
            if all((r["D"], r["delta"]) != (q["D"], q["delta"]) for q in top):
                top.append(r)
            if len(top) == 6:
                break
        return top
    top = top6(by_iou)
    top_w = top6(by_iou_w)
    res = {"t_star": ts, "mesh": path, "outer": outer, "placement": {k: pl[k] for k in ("anchor", "psi_deg", "scale", "O", "source")},
           "hpx0_crest_to_ground": hpx0, "D1_v1": D1, "grid": {"D": Ds, "h": Hs, "delta": Ws},
           "n_cams": len(rows) - 1, "n_valid": len(valid), "wall_s": round(wall, 1),
           "top6_by_iou_hz": [r["name"] for r in top], "best_by_iou_hz": by_iou[0]["name"] if by_iou else None,
           "best_by_outline_hz": by_od[0]["name"] if by_od else None,
           "top6_by_iou_wave_only": [r["name"] for r in top_w], "best_by_iou_wave_only": by_iou_w[0]["name"] if by_iou_w else None,
           "rows": rows,
           "def_ja": "δ：v1 の水平の向き（頂の足元 → v1 のカメラ）からの回し（負＝峰に沿って見る向きへ。−37° で峰の線の真上）。h：目の高さ（Unity の m）。"
                     "D：頂の足元からの水平の距離。縦の画角は巻きの大きさ（頂と真下の水面の画面の上下の距離）を v1 と同じにする値。焦点距離は 35 mm 判の換算（縦 24 mm）。"
                     "iou・mean_px：波だけ（網目は頂の x から −160〜+90 m。P2・P3 と同じ量）。iou_hz・mean_px_hz：水平線より下の画面を海として足した読み（順位はこちら）。"
                     "原画の水平線（富士の裾）は表示の y ≈ 780〜800 px で、v1 の水平線は 778 px。"}
    json.dump(res, open(os.path.join(out, "camsweep.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    print("sweep wall %.1f s, valid %d" % (wall, len(valid)))
    if quick:
        return
    render_sheets(res, rows, top, top_w, by_od, p, pl, path, out, cfg)


def render_sheets(res, rows, top, top_w, by_od, p, pl, path, out, cfg):
    # 水平線が原画に近いカメラ（v1 の水平線 ±60 px。原画の富士の裾は y ≈ 780〜800 px）だけの上位 6
    hv1 = rows[0]["horizon_y"]
    low = []
    for r in sorted([r for r in rows if r["valid"] and r["name"] != "v1" and abs(r["horizon_y"] - hv1) < 60], key=lambda r: -r["iou_hz"]):
        if all((r["D"], r["delta"]) != (q["D"], q["delta"]) for q in low):
            low.append(r)
        if len(low) == 6:
            break
    res["top6_low_horizon"] = [r["name"] for r in low]
    json.dump(res, open(os.path.join(out, "camsweep.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    # 粘土の図（上位 6 と v1、ほかに輪郭の距離の 1 位）
    pick = [rows[0]] + top + [r for r in top_w + low if r not in top] + ([by_od[0]] if by_od and by_od[0] not in top else [])
    seen = set(); pick = [r for r in pick if not (r["name"] in seen or seen.add(r["name"]))]
    cams = [{"name": r["name"], "pos": r["eye"], "fwd": r["fwd"], "up": [0, 1, 0], "vfov": r["vfov"], "clip_start": 3.0} for r in pick]
    xf = {"T": pl["T"], "E": pl["E"], "O": pl["O"], "s": pl["scale"], "anchor": pl["anchor"]}
    rd = os.path.join(out, "render")
    # 粘土の図は水面を切らずに全部描く（点数の範囲 x −160〜+90 m で切ると、遠いカメラでは切り口から水の帯の底が見えて読みにくい。
    # 順位の「水平線までの海を足した」読みは、切らない図に近い）
    item = {"mesh": path, "extra": M.extra_of(p, path), "xf": xf, "cams": cams, "crop": None,
            "out": {c["name"]: os.path.join(rd, c["name"] + ".png").replace("\\", "/") for c in cams}}
    M.run_blender({"res": [960, 540], "near_clip": 3.0, "outer_tint": cfg["outer_tint"], "items": [item], "force": True, "two_sided": bool(cfg.get("two_sided"))}, out, "camsweep", V.Timer())
    sheet(res, pick, top, by_od, rd, out, cfg, p, "camsweep_top6.png", "水平線までの海を足したシルエットの IoU", "iou_hz", "mean_px_hz")
    sheet(res, pick, top_w, by_od, rd, out, cfg, p, "camsweep_top6_waveonly.png", "波だけのシルエットの IoU（P2・P3 と同じ量）", "iou", "mean_px")
    sheet(res, pick, low, by_od, rd, out, cfg, p, "camsweep_top6_lowhorizon.png", "水平線が原画に近い（目の高さ 3 m）カメラの IoU", "iou_hz", "mean_px_hz", best_sheet=False)


def clay_with_horizon(rd, r, w, h):
    """粘土の図に、水平線（点線）と原画の輪郭（青）を重ねる。"""
    im = Image.open(os.path.join(rd, r["name"] + ".png")).convert("RGB").resize((w, h), Image.LANCZOS)
    im = M.draw_outline(im, w, h, 1)
    d = ImageDraw.Draw(im)
    y = (r["horizon_y"] + 0.5) * h / 1080.0
    if 0 <= y < h:
        for x in range(0, w, 12):
            d.line([x, y, x + 6, y], fill=(120, 60, 160), width=1)
    return im


def sheet(res, pick, top, by_od, rd, out, cfg, p, fname, what, k_iou, k_md, best_sheet=True):
    FW, FH = 1920, 1080
    sh = Image.new("RGB", (FW, FH), (244, 243, 239))
    dr = ImageDraw.Draw(sh)
    dr.rectangle([0, 0, FW, 44], fill=(30, 30, 34))
    dr.text((12, 9), "カメラを変えた比べ（t* = %.2f s の P3 の水面、新しい計算なし）：%s の上位 6" % (res["t_star"], what),
            font=M.F22, fill=(255, 255, 255))
    v1 = pick[0]
    dr.text((12, 50), "本番の原画カメラ v1（距離 %.0f m・高さ 3 m・縦の画角 26°）：IoU %.3f・輪郭の平均距離 %.0f px。どのカメラも頂を原画の頂の画素に置き、巻きの大きさを v1 と同じにした。"
            "本番のカメラは変えていない。" % (v1["D"], v1[k_iou], v1[k_md]), font=M.F14, fill=(30, 30, 30))
    W2, H2 = 448, 252
    paint = M.draw_outline(M.painting_display(W2, H2), W2, H2, 1)
    for k, r in enumerate(top):
        col, row = k % 2, k // 2
        x = 10 + col * 960; y = 78 + row * (H2 + 64)
        sh.paste(paint, (x, y))
        sh.paste(clay_with_horizon(rd, r, W2, H2), (x + W2 + 8, y))
        M.tag(dr, (x + 4, y + 4), "原画", M.F12)
        M.tag(dr, (x + W2 + 12, y + 4), "%d 位：流体（青＝原画の輪郭、紫の点線＝水平線）" % (k + 1), M.F12)
        dr.text((x, y + H2 + 2), "距離 %.0f m・高さ %.0f m・向き δ %+.0f°・縦の画角 %.1f°（焦点距離 %.0f mm 相当）" % (
            r["D"], r["h"], r["delta"], r["vfov"], r["focal_mm"]), font=M.F16, fill=(0, 0, 0))
        dr.text((x, y + H2 + 25), "IoU %.3f（v1 %+.3f）・輪郭 %.0f px（v1 %+.0f）・水平線の y %.0f px（原画 約 790）%s" % (
            r[k_iou], r[k_iou] - v1[k_iou], r[k_md], r[k_md] - v1[k_md], r["horizon_y"],
            "" if r.get("in_tank") else "・カメラは水槽の外"), font=M.F14, fill=(40, 40, 40))
    note = ["δ：v1 の向き（頂の足元から見た v1 のカメラの方位）からの回し。負は峰に沿って見る向き（−37° で峰の線の上から峰に沿って見る）。高さは Unity の m（波の頂は約 22.6 m）。",
            "粘土の図は水面を切らずに描く（点数は頂の x から −160〜+90 m の網目、P2・P3 と同じ）。灰青＝外の海（P2）。遠いカメラでは水槽の端が見える。"
            + ("順位の IoU は、水平線より下の画面を海として足した読み（本当の海は水平線まで続く）。" if k_iou == "iou_hz" else "この一覧は波だけの IoU（水平線までの海を足さない）。")
            + "点数は記録だけ（合否に使わない）。"]
    for i, l in enumerate(note):
        dr.text((12, FH - 46 + i * 21), l, font=M.F12, fill=(50, 50, 50))
    sh.save(os.path.join(out, fname))
    if k_iou != "iou_hz" or not best_sheet:
        return
    # v1 と 1 位を大きく並べた図
    sh2 = Image.new("RGB", (FW, FH), (244, 243, 239))
    d2 = ImageDraw.Draw(sh2)
    d2.rectangle([0, 0, FW, 44], fill=(30, 30, 34))
    d2.text((12, 9), "原画 | 本番の原画カメラ v1 | 比べの 1 位のカメラ（t* = %.2f s、粘土・流体だけ）" % res["t_star"], font=M.F22, fill=(255, 255, 255))
    W3, H3 = 636, 358
    sh2.paste(M.painting_display(W3, H3), (0, 60))
    for j, r in enumerate((v1, top[0])):
        im = Image.open(os.path.join(rd, r["name"] + ".png")).convert("RGB").resize((W3, H3), Image.LANCZOS)
        sh2.paste(im, (642 * (j + 1), 60))
        sh2.paste(clay_with_horizon(rd, r, W3, H3), (642 * (j + 1), 60 + H3 + 40))
        d2.text((642 * (j + 1) + 4, 60 + 2 * H3 + 50), ("v1：" if j == 0 else "1 位：") + "距離 %.0f m・高さ %.0f m・δ %+.0f°・画角 %.1f°" % (
            r["D"], r["h"], r["delta"], r["vfov"]), font=M.F18, fill=(0, 0, 0))
        d2.text((642 * (j + 1) + 4, 60 + 2 * H3 + 80), "IoU %.3f・輪郭の平均距離 %.0f px（水平線までの海を足した読み）" % (r["iou_hz"], r["mean_px_hz"]), font=M.F18, fill=(0, 0, 0))
        d2.text((642 * (j + 1) + 4, 60 + 2 * H3 + 108), "波だけ：IoU %.3f・輪郭 %.0f px" % (r["iou"], r["mean_px"]), font=M.F16, fill=(60, 60, 60))
    sh2.paste(M.draw_outline(M.painting_display(W3, H3), W3, H3, 1), (0, 60 + H3 + 40))
    d2.text((4, 60 + H3 + 8), "下の段：青＝原画の大波の輪郭、紫の点線＝水平線", font=M.F16, fill=(40, 40, 40))
    sh2.save(os.path.join(out, "camsweep_v1_vs_best.png"))


if __name__ == "__main__":
    main()
