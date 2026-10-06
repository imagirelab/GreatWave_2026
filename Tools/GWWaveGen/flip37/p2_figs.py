# -*- coding: utf-8 -*-
"""P2 の図（py -3.10）。
  py -3.10 p2_figs.py run <run_dir>      ：1 本の計算の一枚（原画視点のシルエットの重ね・峰に沿う頂の高さ・上から見た水面と張り出し）
  py -3.10 p2_figs.py clay <run_dir> [frame]  ：Blender で粘土の図（原画カメラ・左前の斜め）を描く（既定はいちばん原画に近いコマ）
  py -3.10 p2_figs.py table <run_dir> ...：表（table_ja.md・table.json・table.png）を Unity/Build/FLIP37/P2/ に書く
"""
import sys, os, json, glob, math, subprocess
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p2_common as C  # noqa: E402
import p2_analyze as A2  # noqa: E402

P2 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P2"
BLENDER = r"G:/SteamLibrary/steamapps/common/Blender/blender.exe"
REF = r"G:/Unity/GreatWave_2026_Fresh/Docs/References/Met_JP1847_DP130155.jpg"


def font(sz):
    for p in ("C:/Windows/Fonts/meiryo.ttc", "C:/Windows/Fonts/msgothic.ttc"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def painting_display(scale=0.5):
    _, _, src = C.painting_outline()
    fr = src["frame"]
    img = Image.open(REF).convert("RGB")
    w = int(round(img.width * fr["scale"])); h = int(round(img.height * fr["scale"]))
    img = img.resize((w, h), Image.LANCZOS)
    canvas = Image.new("RGB", (1920, 1080), (0, 0, 0))
    canvas.paste(img, (int(round(fr["offset_x"])), 0))
    return canvas.resize((int(1920 * scale), int(1080 * scale)), Image.LANCZOS)


def silhouette(rd, best, scale=0.5):
    f = os.path.join(rd, "mesh", "mesh_%04d.npz" % best["frame"])
    Pm, tri, t = C.load_mesh_full(f, *C.run_mirror(rd))
    a = best["anchor"]
    keep = (Pm[:, 0] > a[0] - 160) & (Pm[:, 0] < a[0] + 90)
    tk = tri[keep[tri].all(1)]
    cam = C.painting_cam(scale)
    U, O = C.place(Pm, a, best["psi_deg"], best["scale"], cam)
    return C.raster_mask(cam, U, tk)


def fig_run(rd):
    an = json.load(open(os.path.join(rd, "analysis.json"), encoding="utf8"))
    best = an["best"]; ab = an["at_best"]
    sc = 0.5
    base = np.array(painting_display(sc)).astype(np.float64) * 0.55 + 255 * 0.45
    m = silhouette(rd, best, sc)
    win = C.window_mask(sc)
    over = base.copy()
    over[m] = over[m] * 0.45 + np.array([235, 120, 40]) * 0.55
    img = Image.fromarray(np.clip(over, 0, 255).astype(np.uint8))
    dr = ImageDraw.Draw(img)
    outer, inner, _ = C.painting_outline()
    for pl in (outer, inner):
        dr.line([tuple((p + 0.5) * sc - 0.5) for p in pl], fill=(20, 60, 200), width=2)
    x0, x1, y0, y1 = C.WIN
    dr.rectangle([x0 * sc, y0 * sc, x1 * sc, y1 * sc], outline=(120, 120, 120))
    W_ = 960 + 640; H_ = 540 + 330
    sheet = Image.new("RGB", (W_, H_), (255, 255, 255))
    sheet.paste(img, (0, 40))
    ds = ImageDraw.Draw(sheet)
    f1, f2 = font(20), font(14)
    ds.text((8, 8), "%s：原画カメラのシルエット（橙＝流体、青＝原画の大波の輪郭）t=%.2f s、ψ=%d°、倍率 %.1f" % (
        an["run_id"], best["t"], best["psi_deg"], best["scale"]), fill=(0, 0, 0), font=f1)
    od = best.get("outline_dist") or {}
    ds.text((8, 584), "IoU %.3f（窓の中）・輪郭の距離 平均 %.0f px・中央 %.0f px（1920 表示）。記録だけ（合否に使わない）。物理だけ（誘導なし）" % (
        best["iou"], od.get("mean_px", float("nan")), od.get("median_px", float("nan"))), fill=(0, 0, 0), font=f2)
    # 峰に沿う頂の高さ
    cp = ab["crest_profile"]
    z = np.array(cp["z"]); y = np.array(cp["y"])
    gx0, gy0, gw, gh = 980, 60, 600, 230
    ds.rectangle([gx0, gy0, gx0 + gw, gy0 + gh], outline=(0, 0, 0))
    zlo, zhi = float(z.min()), float(z.max())
    def G(zz, yy):
        return (gx0 + (zz - zlo) / (zhi - zlo) * gw, gy0 + gh - (yy + 5) / 30 * gh)
    for yy in (0, 10, 20):
        ds.line([G(zlo, yy), G(zhi, yy)], fill=(210, 210, 210)); ds.text((gx0 - 28, G(zlo, yy)[1] - 8), "%d" % yy, fill=(0, 0, 0), font=f2)
    ds.line([G(zz, yy) for zz, yy in zip(z, y)], fill=(200, 80, 20), width=3)
    # 原画の外側の輪郭の左の部分を、この置き方（ψ）で峰に沿う縦の平面に当てた読み（頂を流体の Hc にそろえる）
    ps, py_ = C.painting_crest_profile(best["psi_deg"], Hc=ab["Hc_m"])
    ds.line([G(ab["z_crest"] + a_, b_) for a_, b_ in zip(ps, py_)], fill=(20, 60, 200), width=2)
    for pz, py, pr in ab["peaks"][:4]:
        q = G(pz, py); ds.ellipse([q[0] - 4, q[1] - 4, q[0] + 4, q[1] + 4], outline=(0, 0, 0), width=2)
    ds.text((gx0, gy0 - 24), "峰に沿う頂の高さ（m）、z = %.0f〜%.0f m（%s。頂より z の小さい側が画面の左・手前）。青＝原画の左の輪郭の読み" % (
        zlo, zhi, "z<-120 は鏡に映した写し" if ab.get("mirror") else "全体"), fill=(0, 0, 0), font=f2)
    ds.text((gx0, gy0 + gh + 6), "山 %d 個（目立ち 0.8 m 以上）・Hc %.1f m・峰の長さ（0.75 Hc 以上）%.0f m・張り出しの z の幅 %.0f m" % (
        ab["n_peaks_prom08"], ab["Hc_m"], ab["crest_len_075Hc_m"], ab["overturned_z_extent_m"]), fill=(0, 0, 0), font=f2)
    sw = ab["side_swell_m"]
    def _f(v):
        return "—" if v is None else "%.1f" % v
    ds.text((gx0, gy0 + gh + 26), "頂から手前へ 46 m で %s m・奥へ 46 m で %s m。100 m 以上離れた所の最大：手前 %s m・奥 %s m" % (
        _f(sw.get("near_dz-46")), _f(sw.get("far_dz+46")), _f(sw.get("near_dz<=-100")), _f(sw.get("far_dz>=100"))), fill=(0, 0, 0), font=f2)
    # 上から見た水面（その瞬間）と張り出し
    hf = A2.load_hf(rd)
    k = int(np.argmin(np.abs(hf["t"] - best["t"])))
    e = hf["eta"][k]; sg = hf["seg"][k]
    xs, zs = hf["xs"], hf["zs"]
    mx = (xs >= 380) & (xs <= 706)
    ee = np.nan_to_num(e[:, mx], nan=-10)
    v = np.clip((ee + 6) / 30, 0, 1)
    rgb = (np.stack([0.25 + 0.7 * v, 0.35 + 0.6 * v, 0.55 + 0.4 * v], -1) * 255).astype(np.uint8)
    rgb[sg[:, mx] >= 2] = (230, 60, 40)
    hh = int(min(480, 600 * (zs.max() - zs.min()) / 326))
    tv = Image.fromarray(rgb[::-1]).resize((600, hh), Image.NEAREST)
    if sheet.height < 380 + hh + 10:
        sh2 = Image.new("RGB", (sheet.width, 380 + hh + 10), (255, 255, 255)); sh2.paste(sheet, (0, 0)); sheet = sh2; ds = ImageDraw.Draw(sheet)
    sheet.paste(tv, (980, 380))
    ds.text((980, 356), "上から見た水面 x 380〜706 m（右が岸）、上が z=%.0f、下が z=%.0f。赤＝張り出し（水→空気→水）" % (zs.max(), zs.min()), fill=(0, 0, 0), font=f2)
    # 下の文字：切り口の値
    yy = 630
    secs = an.get("sections", {})
    for name in sorted(secs, key=lambda s: int(s[1:])):
        sv = secs[name]; q = sv.get("at_best") or {}
        if not q:
            continue
        ev = sv.get("events") or {}
        fo = ev.get("face_past_vertical") or {}
        txt = "%s：頂 %.1f m、張り出し %s、かぶり %s Hc、届き %s Hc、前の面 %s°、垂直を過ぎた %s s" % (
            name, (q.get("crest") or [0, float("nan")])[1], "あり" if q.get("overturned") else "なし",
            "%.2f" % q["overhang_over_Hc"] if q.get("overhang_over_Hc") is not None else "—",
            "%.2f" % q["reach_over_Hc"] if q.get("reach_over_Hc") is not None else "—",
            "%.0f" % q["front_face_chord_angle_deg"] if q.get("front_face_chord_angle_deg") is not None else "—",
            "%.2f" % fo["t"] if fo else "—")
        ds.text((8 + (0 if yy < 840 else 800), yy if yy < 840 else yy - 220), txt, fill=(0, 0, 0), font=f2)
        yy += 20
    sheet.save(os.path.join(rd, "sheet.png"))
    print("saved", os.path.join(rd, "sheet.png"))


def clay(rd, frame=None, tag=None, keep_place=False):
    """frame を与えると、そのコマの網目を描く。keep_place=True なら置き方はいちばん原画に近い瞬間のまま（時刻の並びの図）。"""
    an = json.load(open(os.path.join(rd, "analysis.json"), encoding="utf8"))
    best = dict(an["best"])
    if frame is not None:
        if keep_place:
            best["frame"] = int(frame)
        else:
            q = [f for f in an["fits"] if f["frame"] == int(frame)]
            best = q[0] if q else best
    T, E = C.TE(best["psi_deg"])
    pc = C.painting_cam()
    U0, O = C.place(np.array([[best["anchor"][0], 0, best["anchor"][2]]]), best["anchor"], best["psi_deg"], best["scale"], pc)
    # 左前の斜め：波の前（進む向き +T）と左（−E、原画で画面の左）の間 45° の向きから、170 m 離れ、高さ 45 m で頂を見る
    ctr = U0[0] + np.array([0, 4.0, 0])
    dirh = math.cos(math.radians(45)) * T - math.sin(math.radians(45)) * E
    eye = U0[0] + 170.0 * dirh + np.array([0, 45.0, 0])
    tt = C.Cam(eye, ctr - eye, (0, 1, 0), 48.0)
    tag = tag or "f%04d" % best["frame"]
    mpath = os.path.join(rd, "mesh", "mesh_%04d.npz" % best["frame"])
    mir, Lz_ = C.run_mirror(rd)
    if mir:
        os.makedirs(os.path.join(rd, "mesh_full"), exist_ok=True)
        Pf, tf_, tt_ = C.load_mesh_full(mpath, mir, Lz_)
        mpath = os.path.join(rd, "mesh_full", "mesh_%04d.npz" % best["frame"])
        np.savez_compressed(mpath, P=Pf.astype(np.float32), tri=tf_.astype(np.int32), t=tt_)
    job = {"mesh": mpath.replace("\\", "/"), "T": T.tolist(), "E": E.tolist(),
           "O": O.tolist(), "s": best["scale"], "anchor": best["anchor"],
           "cams": [{"name": "painting", "pos": pc.pos.tolist(), "fwd": pc.f.tolist(), "up": [0, 1, 0], "vfov": 26.0},
                    {"name": "leftfront315", "pos": tt.pos.tolist(), "fwd": tt.f.tolist(), "up": [0, 1, 0], "vfov": 48.0}],
           "out_prefix": os.path.join(rd, "clay_" + tag).replace("\\", "/"), "res": [1920, 1080]}
    jp = os.path.join(rd, "clay_job_%s.json" % tag)
    json.dump(job, open(jp, "w", encoding="utf8"))
    r = subprocess.run([BLENDER, "-b", "--factory-startup", "-P", os.path.join(os.path.dirname(os.path.abspath(__file__)), "p2_clay_bl.py"), "--", jp],
                       capture_output=True, text=True, timeout=600)
    print(r.stdout[-600:], r.stderr[-600:])


def strip(rd, dts=(-4.0, -2.0, -1.0, 0.0, 0.5)):
    """いちばん原画に近い瞬間の前後の粘土（左前の斜めと原画カメラ）を並べる。置き方はその瞬間のまま。"""
    an = json.load(open(os.path.join(rd, "analysis.json"), encoding="utf8"))
    best = an["best"]
    mf = sorted(int(os.path.basename(f)[5:9]) for f in glob.glob(os.path.join(rd, "mesh", "mesh_*.npz")))
    tiles = []
    for dt in dts:
        fr = min(mf, key=lambda m: abs((m - 1) / 24.0 - (best["t"] + dt)))
        tag = "strip_f%04d" % fr
        if not os.path.isfile(os.path.join(rd, "clay_%s_painting.png" % tag)):
            clay(rd, fr, tag=tag, keep_place=True)
        tiles.append((fr, (fr - 1) / 24.0, tag))
    tw, th = 480, 270
    sheet = Image.new("RGB", (tw * len(tiles), th * 2 + 70), (255, 255, 255))
    ds = ImageDraw.Draw(sheet)
    ds.text((8, 6), "%s：いちばん原画に近い瞬間（t=%.2f s）の前後。上＝左前の斜め、下＝原画カメラ。置き方は同じ（ψ=%d°・倍率 %.1f）。物理だけ（誘導なし）" % (
        an["run_id"], best["t"], best["psi_deg"], best["scale"]), fill=(0, 0, 0), font=font(15))
    for i, (fr, t, tag) in enumerate(tiles):
        for j, v in enumerate(("leftfront315", "painting")):
            im = Image.open(os.path.join(rd, "clay_%s_%s.png" % (tag, v))).resize((tw, th), Image.LANCZOS)
            sheet.paste(im, (i * tw, 30 + j * th))
        ds.text((i * tw + 6, 34), "t=%.2f s（%+.1f s）" % (t, t - best["t"]), fill=(0, 0, 0), font=font(16))
    sheet.save(os.path.join(rd, "strip.png"))
    print("saved", os.path.join(rd, "strip.png"))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "run":
        fig_run(sys.argv[2])
    elif cmd == "clay":
        clay(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "strip":
        strip(sys.argv[2])
