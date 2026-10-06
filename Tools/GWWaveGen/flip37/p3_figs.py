# -*- coding: utf-8 -*-
"""P3 の図と動画（py -3.10 ＋ Blender ＋ ffmpeg）。matplotlib が無いので PIL で描く。
使い方:
  py -3.10 p3_figs.py validation                      → P3/validation.png（T0b・T0c・T0d と R18 の比べ）
  py -3.10 p3_figs.py clay <run_dir> <f1,f2,...> [ctx] → <run_dir>/clay/<cam>_FFFF.png（ctx：箱の外を R18 の粗い網目で埋める）
  py -3.10 p3_figs.py render <run_dir> <f_from> <f_to>   → 動画のコマを描く（まだのコマだけ。計算と並べて少しずつ）
  py -3.10 p3_figs.py movie <run_dir> <out.mp4> [f_from f_to fps] → 粘土の動画（左＝左前の斜め、右＝原画カメラ）
  py -3.10 p3_figs.py pair <run_dir> <f1,f2,...>        → <run_dir>/pair_R18.png（上＝R18 粗い、下＝P3 細かい、同じコマ・同じ置き方）
  py -3.10 p3_figs.py sections <run_dir> <z> <t1,t2,..> → <run_dir>/section_zXXX.png（断面の粒子、P3 と R18 を重ねる）
置き方は P2 の R18 のいちばん原画に近い瞬間（analysis.json の best：ψ 30°、倍率 1.1、頂 (566, 18.13, 0)）のまま固定。
"""
import sys, os, json, glob, math, subprocess, shutil
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p2_common as C  # noqa: E402
from p2_figs import font, BLENDER  # noqa: E402

FFMPEG = r"G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
P3 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P3"
R18 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P2/R18_X30L120LG_H39"
CLAY = [0.78, 0.74, 0.66]
CTX = [0.55, 0.62, 0.70]   # 箱の外（R18 の粗い網目）の色


OWN = {"rd": None}   # p3_place() の置き方を使う計算のフォルダー（None なら R18 の置き方）


def best_place():
    if OWN["rd"] and os.path.isfile(os.path.join(OWN["rd"], "place_p3.json")):
        return json.load(open(os.path.join(OWN["rd"], "place_p3.json"), encoding="utf8"))
    an = json.load(open(os.path.join(R18, "analysis.json"), encoding="utf8"))
    return an["best"]


def p3_place(rd, frame=None):
    """P3 自身のいちばん原画に近い瞬間（z=0 の断面が原画の読み A にいちばん近いコマ。P1/P2 と同じ決め方）で、
    z=0 の頂（一番上の水面の最も高い所）を原画の頂の画素へ置く。ψ 30°・倍率 1.1 は R18 と同じ。→ <rd>/place_p3.json"""
    import p3_compare_coarse as CC
    an = json.load(open(os.path.join(rd, "sec", "z+000", "analysis.json"), encoding="utf8"))
    bf = an["best_frame_vs_painting"]["A_side"]
    fr = int(frame or bf["frame"])
    W = CC.load_parts(rd)
    g = W["grid"]; nf, nz, nx = W["eta"].shape
    xs = g["x0"] + g["dx"] * np.arange(nx); zs = g["z0"] + g["dz"] * np.arange(nz)
    k = int(np.argmin(np.abs(W["frames"] - fr)))
    iz = int(np.argmin(np.abs(zs)))
    row = np.where(np.isfinite(W["eta"][k][iz]), W["eta"][k][iz], -99)
    ix = int(np.argmax(row))
    anchor = [float(xs[ix]), float(row[ix]), float(zs[iz])]
    r18 = json.load(open(os.path.join(R18, "analysis.json"), encoding="utf8"))["best"]
    psi, sc = r18["psi_deg"], r18["scale"]
    pc = C.painting_cam()
    _, O = C.place(np.array([[anchor[0], 0, anchor[2]]]), anchor, psi, sc, pc)
    T, E = C.TE(psi)
    Qc = (pc.pos - O) / sc
    xc_, zc_ = float(Qc @ T + anchor[0]), float(Qc @ E + anchor[2])
    ixc = int(np.argmin(np.abs(xs - xc_))); izc = int(np.argmin(np.abs(zs - zc_)))
    inside = xs[0] <= xc_ <= xs[-1] and zs[0] <= zc_ <= zs[-1]
    eta_cam = float(W["eta"][k][izc, ixc]) if inside and np.isfinite(W["eta"][k][izc, ixc]) else None
    out = {"frame": int(W["frames"][k]), "t": float(W["t"][k]), "psi_deg": psi, "scale": sc, "anchor": anchor, "O": O.tolist(),
           "camera_in_sim": [xc_, zc_], "eta_under_camera": eta_cam, "camera_y_sim": float(pc.pos[1] / sc),
           "M_sim_to_unity": C.placement_matrix(anchor, psi, sc, O).tolist(),
           "rule_ja": "z=0 の断面が原画の読み A にいちばん近いコマ（p1_analyze の best_frame_vs_painting.A_side）で、z=0 の頂を原画の頂の画素へ。ψ・倍率は R18 と同じ",
           "section_best": bf}
    json.dump(out, open(os.path.join(rd, "place_p3.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print("place_p3", json.dumps({k: out[k] for k in ("frame", "t", "anchor", "camera_in_sim", "eta_under_camera", "camera_y_sim")}))
    return out


def cams(best):
    T, E = C.TE(best["psi_deg"])
    pc = C.painting_cam()
    U0, O = C.place(np.array([[best["anchor"][0], 0, best["anchor"][2]]]), best["anchor"], best["psi_deg"], best["scale"], pc)
    ctr = U0[0] + np.array([0, 4.0, 0])
    dirh = math.cos(math.radians(45)) * T - math.sin(math.radians(45)) * E
    eye = U0[0] + 170.0 * dirh + np.array([0, 45.0, 0])
    tt = C.Cam(eye, ctr - eye, (0, 1, 0), 48.0)
    return T, E, O, [{"name": "leftfront", "pos": tt.pos.tolist(), "fwd": tt.f.tolist(), "up": [0, 1, 0], "vfov": 48.0},
                     {"name": "painting", "pos": pc.pos.tolist(), "fwd": pc.f.tolist(), "up": [0, 1, 0], "vfov": 26.0}]


def window_of(rd):
    for p in sorted(glob.glob(os.path.join(rd, "run_*.json"))):
        r = json.load(open(p, encoding="utf8"))
        g = r.get("grid") or {}
        if g.get("window"):
            return g["window"], g.get("pad", 4.0)
    return [300.0, 640.0, -70.0, 70.0], 4.0


def r18_mesh_near(f):
    fs = sorted(int(os.path.basename(p)[5:9]) for p in glob.glob(os.path.join(R18, "mesh", "mesh_*.npz")))
    g = min(fs, key=lambda q: abs(q - f))
    return os.path.join(R18, "mesh", "mesh_%04d.npz" % g), g


def ctx_mesh(rd, f):
    """R18 の粗い網目のうち、P3 の箱の内側（境界の帯を除く）に入らない三角形だけ（箱の外の海）。"""
    os.makedirs(os.path.join(rd, "ctx"), exist_ok=True)
    out = os.path.join(rd, "ctx", "ctx_%04d.npz" % f)
    if os.path.isfile(out):
        return out
    (wx0, wx1, wz0, wz1), pad = window_of(rd)
    mp, g = r18_mesh_near(f)
    d = np.load(mp)
    P = d["P"]; tri = d["tri"]
    c = P[tri].mean(1)
    inside = (c[:, 0] > wx0 + pad) & (c[:, 0] < wx1 - pad) & (c[:, 2] > wz0 + pad) & (c[:, 2] < wz1 - pad)
    np.savez_compressed(out, P=P, tri=tri[~inside], t=d["t"] if "t" in d else (g - 1) / 24.0, src_frame=g)
    return out


def run_blender(job, work):
    os.makedirs(work, exist_ok=True)
    jp = os.path.join(work, "seq_job.json")
    json.dump(job, open(jp, "w", encoding="utf8"))
    r = subprocess.run([BLENDER, "-b", "--factory-startup", "-P", os.path.join(HERE, "p3_clay_seq_bl.py"), "--", jp],
                       capture_output=True, text=True, timeout=7200)
    if "SEQ DONE" not in r.stdout:
        print(r.stdout[-1500:], r.stderr[-1500:])
    return r


def clay(rd, frames, ctx=False, res=(1920, 1080), sub="clay"):
    best = best_place()
    T, E, O, cm = cams(best)
    lay = []
    for f in frames:
        L = [{"path": os.path.join(rd, "mesh", "mesh_%04d.npz" % f).replace("\\", "/"), "color": CLAY, "flip": True}]
        if ctx:
            L.append({"path": ctx_mesh(rd, f).replace("\\", "/"), "color": CTX})
        lay.append(L)
    work = os.path.join(rd, sub)
    job = {"frames": lay, "T": T.tolist(), "E": E.tolist(), "O": O.tolist(), "s": best["scale"], "anchor": best["anchor"],
           "cams": cm, "out_dir": work.replace("\\", "/"), "res": list(res)}
    run_blender(job, work)
    # 番号 → コマ番号の名前へ
    for i, f in enumerate(frames):
        for c in ("leftfront", "painting"):
            a = os.path.join(work, "%s_%04d.png" % (c, i))
            if os.path.isfile(a):
                os.replace(a, os.path.join(work, "%s_f%04d%s.png" % (c, f, "_ctx" if ctx else "")))
    return work


def render_frames(rd, f_from, f_to, ctx=True, res=(960, 540)):
    """f_from〜f_to の網目を描く（まだ描いていないコマだけ）。出力：<rd>/movie_frames/<cam>_fFFFF.png。計算と並べて少しずつ描ける。"""
    best = best_place()
    work = os.path.join(rd, "movie_frames_own" if OWN["rd"] else "movie_frames")
    os.makedirs(work, exist_ok=True)
    frames = []
    for p in sorted(glob.glob(os.path.join(rd, "mesh", "mesh_*.npz"))):
        f = int(os.path.basename(p)[5:9])
        if f_from <= f <= f_to and not os.path.isfile(os.path.join(work, "painting_f%04d.png" % f)):
            frames.append(f)
    if not frames:
        return
    T, E, O, cm = cams(best)
    lay = []
    for f in frames:
        L = [{"path": os.path.join(rd, "mesh", "mesh_%04d.npz" % f).replace("\\", "/"), "color": CLAY, "flip": True}]
        if ctx:
            L.append({"path": ctx_mesh(rd, f).replace("\\", "/"), "color": CTX})
        lay.append(L)
    tmp = os.path.join(work, "tmp")
    if os.path.isdir(tmp):
        shutil.rmtree(tmp)
    job = {"frames": lay, "T": T.tolist(), "E": E.tolist(), "O": O.tolist(), "s": best["scale"], "anchor": best["anchor"],
           "cams": cm, "out_dir": tmp.replace("\\", "/"), "res": list(res)}
    run_blender(job, tmp)
    for i, f in enumerate(frames):
        for c in ("leftfront", "painting"):
            a = os.path.join(tmp, "%s_%04d.png" % (c, i))
            if os.path.isfile(a):
                os.replace(a, os.path.join(work, "%s_f%04d.png" % (c, f)))
    print("rendered", len(frames), "frames", frames[0], "-", frames[-1])


def movie(rd, out, f_from=145, f_to=9999, fps=12):
    """描いたコマ（render_frames）を並べて mp4 に。左＝左前の斜め、右＝原画カメラ。fps 12 で実時間の半分の速さ。"""
    best = best_place()
    render_frames(rd, f_from, f_to)
    work = os.path.join(rd, "movie_frames_own" if OWN["rd"] else "movie_frames")
    frames = sorted(int(os.path.basename(p)[10:14]) for p in glob.glob(os.path.join(work, "painting_f*.png")))
    frames = [f for f in frames if f_from <= f <= f_to]
    f1, f2 = font(20), font(15)
    comp = os.path.join(work, "comp")
    if os.path.isdir(comp):
        shutil.rmtree(comp)
    os.makedirs(comp)
    rid = os.path.basename(rd.rstrip("/\\"))
    for i, f in enumerate(frames):
        t = (f - 1) / 24.0
        a = Image.open(os.path.join(work, "leftfront_f%04d.png" % f)).convert("RGB")
        b = Image.open(os.path.join(work, "painting_f%04d.png" % f)).convert("RGB")
        S = Image.new("RGB", (1920, 600), (255, 255, 255))
        S.paste(a, (0, 60)); S.paste(b, (960, 60))
        d = ImageDraw.Draw(S)
        d.text((10, 6), "%s  t = %.2f s（%s のいちばん原画に近い瞬間 %.2f s）。物理だけ（誘導なし）。主役の範囲：粒子 0.25 m・格子 0.5 m。%s" % (
            rid, t, "P3" if OWN["rd"] else "R18", best["t"], "実時間の %.1f 倍の速さ" % (fps / 24.0) if fps != 24 else "実時間"), fill=(0, 0, 0), font=f1)
        d.text((10, 34), "粘土色＝細かい計算（x 304〜636 m、z −66〜66 m）。青灰色＝箱の外の粗い計算 R18（近いコマ）。左：左前の斜め　右：原画カメラ（ψ=%d°・倍率 %.1f）" % (
            best["psi_deg"], best["scale"]), fill=(60, 60, 60), font=f2)
        S.save(os.path.join(comp, "c_%04d.png" % i))
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(comp, "c_%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", out])
    print("saved", out, len(frames), "frames at", fps, "fps")


def pair(rd, frames):
    """同じコマの R18（上）と P3（下）。両方とも同じ置き方・同じカメラ。R18 は粗い網目だけ、P3 は箱の外を R18 で埋める。"""
    best = best_place()
    T, E, O, cm = cams(best)
    lay = []
    for f in frames:
        mp, g = r18_mesh_near(f)
        lay.append([{"path": mp.replace("\\", "/"), "color": CLAY}])
    for f in frames:
        lay.append([{"path": os.path.join(rd, "mesh", "mesh_%04d.npz" % f).replace("\\", "/"), "color": CLAY, "flip": True},
                    {"path": ctx_mesh(rd, f).replace("\\", "/"), "color": CTX}])
    work = os.path.join(rd, "pair_frames")
    if os.path.isdir(work):
        shutil.rmtree(work)
    job = {"frames": lay, "T": T.tolist(), "E": E.tolist(), "O": O.tolist(), "s": best["scale"], "anchor": best["anchor"],
           "cams": cm, "out_dir": work.replace("\\", "/"), "res": [960, 540]}
    run_blender(job, work)
    n = len(frames); tw, th = 480, 270
    for cam in ("painting", "leftfront"):
        sheet = Image.new("RGB", (tw * n, th * 2 + 64), (255, 255, 255))
        ds = ImageDraw.Draw(sheet)
        ds.text((8, 4), "上：R18（粗い 3D、粒子 1 m・格子 2 m）　下：P3 主役の範囲（粒子 0.25 m・格子 0.5 m、青灰色は箱の外の R18）。%s。物理だけ" % (
            "原画カメラ" if cam == "painting" else "左前の斜め"), fill=(0, 0, 0), font=font(15))
        for i, f in enumerate(frames):
            for j in range(2):
                im = Image.open(os.path.join(work, "%s_%04d.png" % (cam, i + j * n))).resize((tw, th), Image.LANCZOS)
                sheet.paste(im, (i * tw, 28 + j * (th + 8)))
            ds.text((i * tw + 6, 30), "t=%.2f s" % ((f - 1) / 24.0), fill=(0, 0, 0), font=font(16))
        out = os.path.join(rd, "pair_R18_%s.png" % cam)
        sheet.save(out)
        print("saved", out)


def load_snap(sd, f):
    p = os.path.join(sd, "snap_%04d.npz" % f)
    if not os.path.isfile(p):
        return None
    return np.load(p)


def sections(rd, z, times, x0=470, x1=640, y0=-26, y1=26, sc=6):
    """z の断面（厚さ ±zhalf）の粒子：灰＝R18（粗い）、黒＝P3（細かい）。times の各時刻（近いコマ）を縦に並べる。"""
    nm = "z%+04d" % int(z)
    sdA = os.path.join(rd, "sec", nm); sdB = os.path.join(R18, "sec", nm)
    W_ = int((x1 - x0) * sc); H_ = int((y1 - y0) * sc)
    tiles = []
    for t in times:
        f = int(round(t * 24 + 1))
        fa = min((int(os.path.basename(p)[5:9]) for p in glob.glob(os.path.join(sdA, "snap_*.npz"))), key=lambda q: abs(q - f))
        fb = min((int(os.path.basename(p)[5:9]) for p in glob.glob(os.path.join(sdB, "snap_*.npz"))), key=lambda q: abs(q - f))
        im = Image.new("RGB", (W_, H_ + 22), (255, 255, 255))
        d = ImageDraw.Draw(im)
        for yy in range(int(y0), int(y1) + 1, 5):
            py = H_ + 22 - int((yy - y0) * sc)
            d.line([(0, py), (W_, py)], fill=(235, 235, 235) if yy else (180, 200, 230))
        for (sd, ff, col, r) in ((sdB, fb, (170, 170, 170), 2), (sdA, fa, (20, 20, 20), 1)):
            s = load_snap(sd, ff)
            if s is None:
                continue
            X = s["x"]; Y = s["y"]
            m = (X > x0) & (X < x1) & (Y > y0) & (Y < y1)
            px = ((X[m] - x0) * sc).astype(int); py = (H_ + 22 - (Y[m] - y0) * sc).astype(int)
            for a_, b_ in zip(px, py):
                d.rectangle([a_, b_, a_ + r - 1, b_ + r - 1], fill=col)
        d.text((4, 2), "%s  t=%.2f s（P3 f%d、R18 f%d）  黒＝P3 0.25 m　灰＝R18 1 m　x %d〜%d m、y %d〜%d m（青線＝静かな水面）" % (
            nm, (fa - 1) / 24.0, fa, fb, x0, x1, y0, y1), fill=(0, 0, 0), font=font(14))
        tiles.append(im)
    sheet = Image.new("RGB", (W_, sum(t.size[1] for t in tiles)), (255, 255, 255))
    y = 0
    for t in tiles:
        sheet.paste(t, (0, y)); y += t.size[1]
    out = os.path.join(rd, "section_%s.png" % nm)
    sheet.save(out)
    print("saved", out)


def validation():
    runs = [("T0b（直し 2 の前）", os.path.join(P3, "T0b_val_d10"), (200, 60, 60)),
            ("T0c（直し 2 の後）", os.path.join(P3, "T0c_val_d10"), (30, 110, 200)),
            ("T0d（＋速い圧力の解き方）", os.path.join(P3, "T0d_val_d10_mg_adapt"), (40, 160, 80))]
    rows = {}
    for nm, rd, col in runs:
        rows[nm] = json.load(open(os.path.join(rd, "compare_R18.json"), encoding="utf8"))
    W_, H_ = 1500, 1000
    im = Image.new("RGB", (W_, H_), (255, 255, 255)); d = ImageDraw.Draw(im)
    d.text((20, 10), "P3 の確かめ：主役の範囲の箱（粒子 1 m・格子 2 m、R18 と同じ細かさ）を R18 の境界で動かし、R18 そのものと比べる", fill=(0, 0, 0), font=font(20))

    def panel(y0, key_f, key_r, ylab, lo, hi):
        x0, x1, ya, yb = 110, 1460, y0 + 30, y0 + 360
        d.rectangle([x0, ya, x1, yb], outline=(0, 0, 0))
        d.text((20, y0), ylab, fill=(0, 0, 0), font=font(17))
        tx = lambda t: x0 + (t - 2.9) / (11.9 - 2.9) * (x1 - x0)
        ty = lambda v: yb - (v - lo) / (hi - lo) * (yb - ya)
        for v in np.arange(lo, hi + 1e-6, (hi - lo) / 5):
            d.line([(x0, ty(v)), (x1, ty(v))], fill=(230, 230, 230)); d.text((x0 - 60, ty(v) - 9), "%.0f" % v, fill=(0, 0, 0), font=font(14))
        for t in range(3, 12):
            d.text((tx(t) - 8, yb + 4), "%d s" % t, fill=(0, 0, 0), font=font(14))
        r0 = rows[list(rows)[1]]["rows"]
        pts = [(tx(q["t"]), ty(q[key_r])) for q in r0]
        d.line(pts, fill=(0, 0, 0), width=4)
        for (nm, rd, col) in runs:
            pts = [(tx(q["t"]), ty(q[key_f])) for q in rows[nm]["rows"]]
            d.line(pts, fill=col, width=2)
        ly = ya + 8
        for nm, col in [("R18（粗い 3D そのもの）", (0, 0, 0))] + [(a, c) for a, _, c in runs]:
            d.line([(x0 + 20, ly + 9), (x0 + 60, ly + 9)], fill=col, width=3); d.text((x0 + 68, ly), nm, fill=(0, 0, 0), font=font(14)); ly += 22
    panel(50, "crest_z0_fine", "crest_z0_R18", "z = 0 の頂の高さ (m)", 8, 24)
    panel(450, "x_crest_z0_fine", "x_crest_z0_R18", "z = 0 の頂の位置 x (m)", 400, 600)
    y = 860
    d.text((20, y), "断面 z=0 の出来事（巻き始め B>0.85 / 前の面が垂直を越す / 管が閉じる）：", fill=(0, 0, 0), font=font(16)); y += 26

    def ev(e):
        s = lambda q: "%.2f s・x %.0f m" % (q["t"], q["x"]) if q else "なし"
        return "%s / %s / %s" % (s(e.get("breaking_onset_B085")), s(e.get("face_past_vertical")), s(e.get("tube_closed_or_nearly")))
    se = rows[list(rows)[1]].get("section_events", {}).get("z+000", {})
    d.text((40, y), "R18：" + ev(se.get("R18") or {}), fill=(0, 0, 0), font=font(15)); y += 22
    for nm, rd, col in runs:
        e = rows[nm].get("section_events", {}).get("z+000", {}).get("fine") or {}
        d.text((40, y), nm + "：" + ev(e), fill=col, font=font(15)); y += 22
    out = os.path.join(P3, "validation.png")
    im.save(out)
    print("saved", out)


def bestpair(rd):
    """いちばん原画に近い瞬間どうしの比べ：左＝R18（t 10.375 s、R18 の置き方）、右＝P3（P3 自身の瞬間と置き方、箱の外は R18）。
    上＝原画カメラ（原画の大波の輪郭を青で重ねる）、下＝左前の斜め。→ <rd>/best_vs_R18.png"""
    r18b = json.load(open(os.path.join(R18, "analysis.json"), encoding="utf8"))["best"]
    p3b = json.load(open(os.path.join(rd, "place_p3.json"), encoding="utf8"))
    work = os.path.join(rd, "best_frames")
    if os.path.isdir(work):
        shutil.rmtree(work)
    imgs = {}
    for tag, b, layers in (("R18", r18b, [{"path": os.path.join(R18, "mesh", "mesh_%04d.npz" % r18b["frame"]).replace("\\", "/"), "color": CLAY}]),
                           ("P3", p3b, [{"path": os.path.join(rd, "mesh", "mesh_%04d.npz" % p3b["frame"]).replace("\\", "/"), "color": CLAY, "flip": True},
                                        {"path": ctx_mesh(rd, p3b["frame"]).replace("\\", "/"), "color": CTX}])):
        T, E, O, cm = cams(b)
        job = {"frames": [layers], "T": T.tolist(), "E": E.tolist(), "O": O.tolist(), "s": b["scale"], "anchor": b["anchor"],
               "cams": cm, "out_dir": os.path.join(work, tag).replace("\\", "/"), "res": [960, 540]}
        run_blender(job, os.path.join(work, tag))
        imgs[tag] = {c: Image.open(os.path.join(work, tag, "%s_0000.png" % c)).convert("RGB") for c in ("painting", "leftfront")}
    outer, inner, _ = C.painting_outline()
    S = Image.new("RGB", (1940, 1180), (255, 255, 255))
    d = ImageDraw.Draw(S)
    d.text((10, 6), "いちばん原画に近い瞬間どうし（物理だけ、誘導なし）。上：原画カメラ（青＝原画の大波の輪郭）　下：左前の斜め", fill=(0, 0, 0), font=font(20))
    for i, (tag, b, lab) in enumerate((("R18", r18b, "R18（粗い 3D、粒子 1 m）t=%.2f s"), ("P3", p3b, "P3（主役の範囲 0.25 m、青灰色＝箱の外の R18）t=%.2f s"))):
        x0 = 10 + i * 970
        for j, c in enumerate(("painting", "leftfront")):
            im = imgs[tag][c].copy()
            if c == "painting":
                dd = ImageDraw.Draw(im)
                for poly in (outer, inner):
                    dd.line([(float(u) * 0.5, float(v) * 0.5) for u, v in poly], fill=(20, 60, 200), width=3)
            S.paste(im, (x0, 70 + j * 560))
        d.text((x0, 40), lab % b["t"] + "　頂 (%.0f, %.1f, %.0f) を原画の頂の画素へ" % tuple(b["anchor"]), fill=(0, 0, 0), font=font(16))
    out = os.path.join(rd, "best_vs_R18.png")
    S.save(out)
    print("saved", out)


if __name__ == "__main__":
    if "--own" in sys.argv:
        sys.argv.remove("--own")
        OWN["rd"] = sys.argv[2]
    cmd = sys.argv[1]
    if cmd == "place":
        p3_place(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else None)
    elif cmd == "validation":
        validation()
    elif cmd == "clay":
        clay(sys.argv[2], [int(v) for v in sys.argv[3].split(",")], ctx=len(sys.argv) > 4 and sys.argv[4] == "ctx")
    elif cmd == "render":
        render_frames(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    elif cmd == "movie":
        movie(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 145, int(sys.argv[5]) if len(sys.argv) > 5 else 9999,
              int(sys.argv[6]) if len(sys.argv) > 6 else 12)
    elif cmd == "pair":
        pair(sys.argv[2], [int(v) for v in sys.argv[3].split(",")])
    elif cmd == "bestpair":
        bestpair(sys.argv[2])
    elif cmd == "sections":
        sections(sys.argv[2], float(sys.argv[3]), [float(v) for v in sys.argv[4].split(",")])
