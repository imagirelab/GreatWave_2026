# -*- coding: utf-8 -*-
"""FLIP3D videos of FLIP50 clips: 12 s loop clips captured over several loops (FLIP3DBatch seat3 / print3 / move3), and long clips with
the move seconds written exactly (py -3.10 -B; PIL + ffmpeg). 2026-10-17 written new (Claude).

Why a new file: flip3d/f3d_video.py compose() is fixed to the DA3 loop clips (manifest path, loop/seam_jump.json, 'k5' and '12 s' texts),
and compose_cont() (used through flip50g2/f3d50_video.py) writes the move seconds as '%.0f s' (2.75 s would read '3 s'). Nothing of
flip3d or f3d50_video.py is edited: loop videos are composed here with the same two text bands, fonts, ffmpeg settings and contact sheet
as f3d_video.compose(), from the clip's own manifest; long videos run f3d50_video.py's patched compose_cont with one more counted
caption replacement ('%.0f s 前から見える動き' -> '%.2f s 前から見える動き') and the four caption lines drawn with a font that shrinks
until the line fits the frame (the FLIP50 run texts overflowed the right edge). The picture (Unity's rendering) is not changed.
  py -3.10 -B f3d50_video_loop.py --cap capture_DM1Ar_k4_r24 [--crf 18] seat3 print3 move3
  py -3.10 -B f3d50_video_loop.py --cont --cap capture_DM1Ar_f1729_2071_r24 [--crf 18] cseat cprint cmove
Output: Unity/Build/FLIP3D/video/FLIP3D_<clip name without clip_>_<capture>.mp4 and _sheet.jpg
"""
import os, sys, csv, json, shutil, subprocess, inspect
import numpy as np
from PIL import Image, ImageDraw

sys.dont_write_bytecode = True
REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/flip3d")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/flip50g2")
import f3d_video as V          # noqa: E402  unchanged (fonts, ffmpeg, output folder)
import f3d50_video as V5       # noqa: E402  unchanged (run texts, caption replacements of compose_cont)

OLD_MOVE = '"視点の動き：%s に着く（%.0f s 前から見える動き、着いたら %.0f s 止め、%.0f s 留まり %s）。白い画面は使わない。★ は崩れごとの原画に最も近い瞬間"'
NEW_MOVE = '"視点の動き：%s に着く（%.2f s 前から見える動き、着いたら %.0f s 止め、%.0f s 留まり %s）。白い画面は使わない。★ は崩れごとの原画に最も近い瞬間"'
# caption lines of compose_cont drawn with a font that shrinks until the line fits the frame width (the FLIP50 run texts are longer than DA3r's)
FIT_LINES = (("dr.text((18, 8), title, font=f1,", "dr.text((18, 8), title, font=_fit(title, 26, W - 36),"),
             ("dr.text((18, 46), line2, font=f2,", "dr.text((18, 46), line2, font=_fit(line2, 19, W - 36),"),
             ("dr.text((18, 74), line3, font=f2,", "dr.text((18, 74), line3, font=_fit(line3, 19, W - 36),"),
             ("dr.text((18, H - 42), st, font=f3,", "dr.text((18, H - 42), st, font=_fit(st, 22, W - 36),"))
_FONTS = {}


def fit(text, size, width):
    """the font of the given size, or the largest smaller one (down to 12 px) whose line fits the width."""
    s = size
    while True:
        f = _FONTS.get(s)
        if f is None:
            f = _FONTS[s] = V.F(s)
        if s <= 12 or f.getlength(text) <= width:
            return f
        s -= 1


def compose_loop(name, capdir):
    d = V.C.OUT + "/" + capdir + "/" + name
    rows = list(csv.DictReader(open(d + "/frames.csv", encoding="utf8")))
    cap = json.load(open(d + "/capture.json", encoding="utf8"))
    cdir = cap["dataDir"]
    man = json.load(open(cdir + "/manifest.json", encoding="utf8"))
    if (man.get("clip_kind") or "loop") != "loop" or cap.get("playback") != "Loop":
        raise SystemExit("%s is not a loop capture of a loop clip" % d)
    clipname = os.path.basename(cdir.rstrip("/"))
    prefix = "FLIP3D_" + (clipname[5:] if clipname.startswith("clip_") else clipname) + "_"
    short = (man.get("run_id") or "?").split("_")[0]
    L, fpsr = float(man["loop_seconds"]), float(man["record_fps"])
    pp = man["print_record_index"] / fpsr
    nloop = int(round(len(rows) / 24.0 / L)) if cap["mode"] != "Move" else int(round((len(rows) / 24.0 - float(cap["printHold"])) / L))
    step = int(man.get("record_step_frames") or 1)
    rate = "%g 個/s（計算の%s）" % (fpsr, "毎コマ" if step == 1 else "%d コマおき" % step)
    names = {"Seat": "船の座席から（%g s の繰り返し %d 回）" % (L, nloop), "Print": "原画の視点から（真ん中の断面を横から。%g s の繰り返し %d 回）" % (L, nloop),
             "Move": "座席 → 原画の視点（原画に最も近い瞬間に着き %g s 止める。%g s の繰り返し %d 回の中で）" % (float(cap["printHold"]), L, nloop)}
    title = "FLIP3D 試作（Unity で実時間に再生）" + V5.RUN_TEXT.get(short, short) + " — " + names[cap["mode"]]
    line2 = ("面の記録は %s を 1 フレームずつ実時間で見せる。窓 %.2f〜%.2f s（1 周期、コマ %d〜%d）を繰り返す。コマの間の形は作らない。"
             "横は計算の対称の面 y = 0 で写した" % (rate, man["loop_start_s"], man["loop_end_s"], man["frame_first"], man["frame_last"]))
    line3 = ("継ぎ目（%.3f s の次に %.2f s に戻る）の見える跳び：面の距離 p95 %.2f m・Δη の RMS %.2f m（窓の中のふつうの 1/%g s の 1 歩は p95 の中央値 %.2f m）。"
             "計算にない物：外の平らな海（横 %.0f m の外）・霧・空・水の色"
             % (man["t_last"], man["loop_start_s"], man["jump_nn_p95_m"], man["jump_eta_rms_break_m"], fpsr, man["step_mesh_p95_median_m"], man["tank_half_width"]))
    ph = np.array([float(r["phase"]) for r in rows])
    seams = set(int(i + 1) for i in np.where(np.diff(ph) < -0.5 * L)[0])
    if cap["mode"] == "Move":
        arrive = float(cap["seatHold"]) + float(cap["moveSeconds"])
        sm = sorted(float(rows[i]["s"]) for i in seams)
        during = [s for s in sm if float(cap["seatHold"]) < s < arrive]
        line3 = ("視点の動き：座席に %.1f s → %.0f s の見える動き → %d 回目の繰り返しの k%d コマ %d（%.3f s）に着く → %.0f s 止め → 終わりまで原画の視点。白い画面は使わない。"
                 "%s座席・原画の視点の値は %s"
                 % (float(cap["seatHold"]), float(cap["moveSeconds"]), int(round((arrive - pp) / L)) + 1, man["breaker_k"], man["print_record_frame"],
                    man["print_record_t"], float(cap["printHold"]),
                    ("動きの途中（体験 %s s）で継ぎ目を通る。" % "・".join("%.2f" % s for s in during)) if during else "",
                    os.path.basename(man.get("cam_source_file") or "場面の値")))
    tmp = V.VID + "/_frames_" + capdir.replace("/", "_") + "_" + name
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    f1, f2, f3 = V.F(26), V.F(19), V.F(22)
    loop_i = 1
    for i, r in enumerate(rows):
        if i in seams:
            loop_i += 1
        im = Image.open(d + "/frame_%05d.jpg" % i).convert("RGB")
        W, H = im.size
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(ov)
        dr.rectangle([0, 0, W, 112], fill=(0, 0, 0, 150))
        dr.rectangle([0, H - 96, W, H], fill=(0, 0, 0, 150))
        im = Image.alpha_composite(im.convert("RGBA"), ov)
        dr = ImageDraw.Draw(im)
        dr.text((18, 8), title, font=fit(title, 26, W - 36), fill=(255, 255, 255))
        dr.text((18, 46), line2, font=fit(line2, 19, W - 36), fill=(225, 225, 225))
        dr.text((18, 74), line3, font=fit(line3, 19, W - 36), fill=(225, 225, 225))
        p, rec, frz, bl, sf = float(r["phase"]), int(r["record"]), int(r["frozen"]), float(r["blend"]), int(r["sim_frame"])
        st = "計算の時刻 %.3f s（コマ %d、記録 %d/%d、繰り返し %d 回目）" % (float(r["sim_t"]), sf, rec + 1, man["frames"], loop_i)
        if cap["mode"] == "Move":
            st += "　カメラ：" + ("座席" if bl <= 0 else ("原画の視点" if bl >= 1 else "動いている %.0f %%" % (bl * 100)))
        if rec == man["print_record_index"]:
            st += "　★ 崩れ k%d：score3 で原画に最も近い瞬間（%.3f、コマ %d%s）" % (man["breaker_k"], man["print_score3"], man["print_bestframes_frame"],
                                                                     " そのもの" if man["print_record_frame"] == man["print_bestframes_frame"] else "、記録は最も近いコマ")
        if frz:
            st += "　止め（再生の時計だけを止めた）"
        if i in seams:
            st += "　← 継ぎ目"
        x0, x1, y = 260, W - 30, H - 96
        dr.text((18, H - 42), st, font=fit(st, 22, W - 36), fill=(255, 255, 255))
        dr.text((18, y + 6), "繰り返しの中の時刻", font=f2, fill=(220, 220, 220))
        dr.text((x0, y + 28), "0 s（%.2f s）" % man["loop_start_s"], font=V.F(15), fill=(200, 200, 200))
        dr.text((x1 - 130, y + 28), "%g s（継ぎ目）" % L, font=V.F(15), fill=(200, 200, 200))
        dr.line([(x0, y + 18), (x1, y + 18)], fill=(200, 200, 200), width=2)
        X = lambda q: x0 + q / L * (x1 - x0)
        for k in range(0, int(L) + 1):
            dr.line([(X(k), y + 12), (X(k), y + 24)], fill=(200, 200, 200), width=1)
        dr.line([(X(pp), y + 6), (X(pp), y + 30)], fill=(255, 210, 60), width=3)
        dr.text((X(pp) - 40, y + 28), "★ k%d score3 の最良" % man["breaker_k"], font=V.F(15), fill=(255, 210, 60))
        dr.ellipse([X(p) - 7, y + 11, X(p) + 7, y + 25], fill=(255, 255, 255))
        im.convert("RGB").save(tmp + "/f_%05d.jpg" % i, quality=92)
    n = len(rows)
    out = V.VID + "/" + prefix + "%s.mp4" % name
    cmd = [V.C.FFMPEG, "-y", "-loglevel", "error", "-framerate", "24", "-i", tmp + "/f_%05d.jpg", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", V.CRF,
           "-preset", "medium", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    pick = [int(v) for v in np.linspace(0, n - 1, 8)]
    ims = [Image.open(tmp + "/f_%05d.jpg" % i).resize((640, 360)) for i in pick]
    S = Image.new("RGB", (1280, 360 * ((len(ims) + 1) // 2)))
    for j, a in enumerate(ims):
        S.paste(a, ((j % 2) * 640, (j // 2) * 360))
    S.save(V.VID + "/" + prefix + "%s_sheet.jpg" % name, quality=90)
    shutil.rmtree(tmp, ignore_errors=True)
    return dict(name=name, mp4=out, frames=n, seconds=n / 24.0, bytes=os.path.getsize(out), clip=clipname, loops=nloop, seams_at_frames=sorted(seams))


def compose_cont_exact(capdir, names):
    """f3d50_video.py's caption-patched compose_cont, plus the move seconds to 0.01 s (one counted replacement)."""
    real = inspect.getsource

    def getsource(obj):
        s = real(obj)
        if obj is V.compose_cont:
            if s.count(OLD_MOVE) != 1:
                raise SystemExit("move caption not found exactly once in f3d_video.compose_cont")
            s = s.replace(OLD_MOVE, NEW_MOVE)
            for old, new in FIT_LINES:
                if s.count(old) != 1:
                    raise SystemExit("caption line not found exactly once in f3d_video.compose_cont: " + old)
                s = s.replace(old, new)
        return s
    V5.inspect.getsource = getsource            # only inside this process, for V5.patched()
    V._fit = fit                                # in memory only: V5.patched() runs the source in a copy of f3d_video's namespace
    try:
        return V5.patched(capdir, names)
    finally:
        V5.inspect.getsource = real


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = sys.argv[1:]
    if "--crf" in a:
        V.CRF = a[a.index("--crf") + 1]; del a[a.index("--crf"):a.index("--crf") + 2]
    cont = "--cont" in a
    if cont:
        a.remove("--cont")
    if "--cap" not in a:
        print(__doc__); sys.exit(1)
    capdir = a[a.index("--cap") + 1]; del a[a.index("--cap"):a.index("--cap") + 2]
    os.makedirs(V.VID, exist_ok=True)
    if cont:
        names = a or ["cseat", "cprint", "cmove"]
        fn = compose_cont_exact(capdir, names)
        res = [fn(nm, capdir) for nm in names]
    else:
        names = a or ["seat3", "print3", "move3"]
        res = [compose_loop(nm, capdir) for nm in names]
    print(json.dumps(res, ensure_ascii=False, indent=1))
