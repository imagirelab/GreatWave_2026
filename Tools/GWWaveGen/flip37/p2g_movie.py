# -*- coding: utf-8 -*-
"""P2g：誘導の双子の粘土の動画（p2_movie.py の複製。置き方を R18 のいちばん原画に近い瞬間の置き方に固定し、札を引数で渡す）。
使い方: py -3.10 p2g_movie.py <run_dir> <out.mp4> <札>
以下は p2_movie.py の説明。
P2 の 1 本の計算の粘土の動画（py -3.10 ＋ Blender ＋ ffmpeg）。
置き方はいちばん原画に近い瞬間のまま固定（analysis.json の best）。網目の全部のコマ（3 コマごと＝1/8 秒ごと）を、
左＝左前の斜め、右＝原画カメラ で並べ、実時間（8 コマ/秒）の mp4 にする。
使い方: py -3.10 p2_movie.py <run_dir> <out.mp4>
"""
import sys, os, json, glob, math, subprocess, shutil
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p2_common as C  # noqa: E402
from p2_figs import font, BLENDER  # noqa: E402

FFMPEG = r"G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
rd, out, LABEL = sys.argv[1], sys.argv[2], sys.argv[3]
R18 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P2/R18_X30L120LG_H39"
best = json.load(open(os.path.join(R18, "analysis.json"), encoding="utf8"))["best"]
an = {"run_id": os.path.basename(rd.rstrip("/"))}
T, E = C.TE(best["psi_deg"])
pc = C.painting_cam()
U0, O = C.place(np.array([[best["anchor"][0], 0, best["anchor"][2]]]), best["anchor"], best["psi_deg"], best["scale"], pc)
ctr = U0[0] + np.array([0, 4.0, 0])
dirh = math.cos(math.radians(45)) * T - math.sin(math.radians(45)) * E
eye = U0[0] + 170.0 * dirh + np.array([0, 45.0, 0])
tt = C.Cam(eye, ctr - eye, (0, 1, 0), 48.0)
mir, Lz = C.run_mirror(rd)
files = sorted(glob.glob(os.path.join(rd, "mesh", "mesh_*.npz")))
work = os.path.join(rd, "movie_frames")
if os.path.isdir(work):
    shutil.rmtree(work)
os.makedirs(work)
meshes = []
for f in files:
    if mir:
        os.makedirs(os.path.join(rd, "mesh_full"), exist_ok=True)
        mp = os.path.join(rd, "mesh_full", os.path.basename(f))
        if not os.path.isfile(mp):
            Pf, tf_, t_ = C.load_mesh_full(f, mir, Lz)
            np.savez_compressed(mp, P=Pf.astype(np.float32), tri=tf_.astype(np.int32), t=t_)
        meshes.append(mp.replace("\\", "/"))
    else:
        meshes.append(f.replace("\\", "/"))
job = {"meshes": meshes, "T": T.tolist(), "E": E.tolist(), "O": O.tolist(), "s": best["scale"], "anchor": best["anchor"],
       "cams": [{"name": "leftfront", "pos": tt.pos.tolist(), "fwd": tt.f.tolist(), "up": [0, 1, 0], "vfov": 48.0},
                {"name": "painting", "pos": pc.pos.tolist(), "fwd": pc.f.tolist(), "up": [0, 1, 0], "vfov": 26.0}],
       "out_dir": work.replace("\\", "/"), "res": [960, 540]}
jp = os.path.join(work, "seq_job.json")
json.dump(job, open(jp, "w", encoding="utf8"))
r = subprocess.run([BLENDER, "-b", "--factory-startup", "-P", os.path.join(os.path.dirname(os.path.abspath(__file__)), "p2_clay_seq_bl.py"), "--", jp],
                   capture_output=True, text=True, timeout=3000)
print(r.stdout[-300:], r.stderr[-300:])
f1, f2 = font(20), font(16)
comp = os.path.join(work, "comp"); os.makedirs(comp)
for i, f in enumerate(files):
    t = (int(os.path.basename(f)[5:9]) - 1) / 24.0
    a = Image.open(os.path.join(work, "leftfront_%04d.png" % i)).convert("RGB")
    b = Image.open(os.path.join(work, "painting_%04d.png" % i)).convert("RGB")
    S = Image.new("RGB", (1920, 600), (255, 255, 255))
    S.paste(a, (0, 60)); S.paste(b, (960, 60))
    d = ImageDraw.Draw(S)
    d.text((10, 6), "%s  t = %.2f s（t* %.2f s）。%s" % (an["run_id"], t, best["t"], LABEL), fill=(0, 0, 0), font=f1)
    d.text((10, 34), "左：左前の斜め（170 m 離れ、高さ 45 m）　右：原画カメラ（PaintingCam v1。置き方は R18 と同じ ψ=%d°・倍率 %.1f に固定）" % (best["psi_deg"], best["scale"]), fill=(60, 60, 60), font=f2)
    S.save(os.path.join(comp, "c_%04d.png" % i))
subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", "8", "-i", os.path.join(comp, "c_%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", out])
print("saved", out, len(files), "frames")
