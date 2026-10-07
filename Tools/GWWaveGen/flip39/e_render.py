# -*- coding: utf-8 -*-
"""FLIP39 E：粘土の図と短い動画を作る（py -3.10 で job を作り、Blender で描き、PIL と ffmpeg で並べる）。
使い方: py -3.10 e_render.py <run_dir> [--clip] [--res 960x540]

カメラ（どれも計算の座標。1 単位 = 1 m。倍率はかけない）：
- seat：座席の目（seat_e.json の best_seat の x、目の高さ 1.83 m、焦点の列の z）から沖（−x）を向き、15° 見上げる。縦の画角 90°（PS VR2 の視野 約 110° の水平に近い広さを 16:9 で見せる）。
- painting：原画カメラ（PaintingCam v1）を、P3 の置き方（Unity/Build/FLIP37/P3/H25_R18_mg/place_p3.json）で計算の座標に写した時の、
  P3 の頂（anchor）からの相対の位置と注視点を、倍率をかけずにこの計算の頂の位置へ移したもの（雰囲気の参考だけ。合わせの判定には使わない）。縦の画角 26°。
  注視点の高さは頂の高さの差の半分だけ下げる。カメラの真下の水面が高ければ水面の 1 m 上へ上げる。
- oblique：頂から岸の側へ 70 m・峰に沿って 80 m（3D は壁の反対の側）・高さ 18 m から、頂の少し沖の中ほどを見る（前の面と唇を斜め前から見る）。縦の画角 40°。
描く時刻：前の面が垂直を過ぎた時刻 + 0.75 秒（崩れの最中）。動画（--clip）は、その 10 秒前から 3 秒後まで、網目のあるコマ（3 コマおき＝8 fps）。
"""
import sys, os, json, glob, subprocess
import numpy as np

BLENDER = r"G:/SteamLibrary/steamapps/common/Blender/blender.exe"
FFMPEG = r"G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39"
PLACE = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P3/H25_R18_mg/place_p3.json"
PCAM_POS = np.array([0.0, 3.0, -62.0]); PCAM_LOOK = np.array([-2.5, 9.7, 4.0])   # PaintingCam v1（Unity の座標）


def painting_rel():
    pl = json.load(open(PLACE, encoding="utf8"))
    Mi = np.linalg.inv(np.array(pl["M_sim_to_unity"]))
    pos = (Mi @ np.r_[PCAM_POS, 1.0])[:3]; look = (Mi @ np.r_[PCAM_LOOK, 1.0])[:3]
    a = np.array(pl["anchor"])
    return pos - a, look - a, float(a[1])


def mesh_files(rd):
    out = {}
    for f in glob.glob(os.path.join(rd, "mesh", "mesh_*.npz")):
        out[int(os.path.basename(f)[5:9])] = f
    return out


def cams_for(crest, seat_x, zs, mirror, Hc_ref):
    xc, yc, zc = crest
    prel, lrel, Hp3 = painting_rel()
    cams = {}
    cams["seat"] = dict(pos=[seat_x, 1.83, zs], look=[seat_x - 100.0, 1.83 + 100 * np.tan(np.radians(15)), zs], vfov=90.0, near=0.2)
    # 原画カメラ：P3 の置き方の頂からの相対の位置と注視点を、倍率をかけずにこの計算の頂へ移す（高さは静かな水面から）。
    # P3 の置き方では峰に沿う向きが鏡（P2 §3）なので、z の向きは 3D の計算の手前（壁の反対）に合わせる。カメラの真下の水が高ければ、水面の 1 m 上へ上げる（e_render の main）
    sgn = 1.0 if mirror else -1.0
    pos = np.array([xc + prel[0], Hp3 + prel[1], zc + sgn * abs(prel[2])])
    look = np.array([xc + lrel[0], Hp3 + lrel[1] - (Hp3 - yc) * 0.5, zc + sgn * abs(lrel[2]) * np.sign(lrel[2] * prel[2])])
    cams["painting"] = dict(pos=pos.tolist(), look=look.tolist(), vfov=26.0, near=1.0)
    cams["oblique"] = dict(pos=[xc + 70.0, 18.0, zc + sgn * 80.0], look=[xc - 5.0, 0.45 * yc, zc + sgn * 5.0], vfov=40.0, near=1.0)
    return cams


def main(rd, clip=False, res=(960, 540)):
    rd = rd.rstrip("/\\")
    rj = json.load(open(os.path.join(rd, "run.json"), encoding="utf8"))
    an = json.load(open(os.path.join(rd, "analysis_e.json"), encoding="utf8"))
    se = json.load(open(os.path.join(rd, "seat_e.json"), encoding="utf8"))
    P = rj["parms"]; Lz = float(P["Lz"]); mirror = Lz > 20; toff = float(P.get("t_off", 0.0))
    zs = -0.5 * Lz + 0.5 if mirror else 0.0
    if mirror and an.get("row_z") is not None:
        zs = float(an["row_z"])
    br = an.get("breaking") or {}
    ev = br.get("events", {})
    fpv = ev.get("face_past_vertical")
    if fpv:
        t_r = fpv["t"] + 0.75; crest = [fpv["x"], fpv["crest_y"], zs]
    else:
        c = an["crest_max_any"]; t_r = c["t_group"] - toff; crest = [c["x"], c["crest_m"], zs]
    seat_x = (se.get("best_seat") or {}).get("x_seat", crest[0] + 10.0)
    mf = mesh_files(rd)
    if not mf:
        print("no meshes"); return
    frs = np.array(sorted(mf))
    f_r = int(frs[np.argmin(np.abs((frs - 1) / 24.0 - t_r))])
    cams = cams_for(crest, seat_x, zs, mirror, crest[1])
    # 原画カメラの真下の水面（崩れの時刻の網目、半径 4 m の最も高い所。3D は壁で鏡に映した位置で探す）
    dm = np.load(mf[f_r]); MP = dm["P"].astype(float); MP[:, 1] -= float(an.get("level_offset_m", 0.43))
    cp = np.array(cams["painting"]["pos"]); zq = cp[2] if not mirror else (cp[2] if cp[2] >= -0.5 * Lz else -Lz - cp[2])
    near = (np.abs(MP[:, 0] - cp[0]) < 4) & ((np.abs(MP[:, 2] - zq) < 4) | (not mirror and Lz < 20))
    if near.any() and MP[near, 1].max() + 1.0 > cp[1]:
        cams["painting"]["pos"][1] = float(MP[near, 1].max() + 1.0)
        cams["painting"]["raised_to_water_plus_1m"] = True
    outd = os.path.join(rd, "render"); os.makedirs(outd, exist_ok=True)
    base = dict(mode="mirror" if mirror else "slab", Lz=Lz, zw=-0.5 * Lz, crop_x=[float(P.get("mx0", 300.0)), float(P.get("mx1", 706.0))], boat=[seat_x, zs], yoff=-float(an.get("level_offset_m", 0.43)))
    # 座席の目の図の時刻
    bsx = se.get("best_seat") or {}
    # 座席の目：船が水面に乗る目（seat_e.json の ride。目の高さ＝船の下の水面＋1.83 m）。仰角が最も大きい時刻の 0.3 秒前
    ride = bsx.get("ride") or {}
    sr = ride.get("series") or {}
    # 静止画の時刻：仰角が初めて min(40°, 最大の 0.6 倍) を越えた時（最大の時刻は前の面が 2 m 先まで来ていて形が読めないため）
    t_seat = t_r
    if sr.get("alpha"):
        aa = np.array(sr["alpha"]); thr = min(40.0, 0.6 * float(aa.max()))
        t_seat = float(np.array(sr["t_group"])[np.argmax(aa >= thr)]) - toff
    def eye_y_at(tg):
        if not sr.get("t_group"):
            return 1.83
        return float(np.interp(tg, sr["t_group"], sr["eye_y"]))
    f_s = int(frs[np.argmin(np.abs((frs - 1) / 24.0 - t_seat))])
    def seat_cam(tg):
        ey = eye_y_at(tg)
        c = dict(cams["seat"]); c["pos"] = [seat_x, ey, zs]; c["look"] = [seat_x - 100.0, ey + 100 * np.tan(np.radians(15)), zs]
        return c, ey
    sc_, ey_s = seat_cam((f_s - 1) / 24.0 + toff)
    items = [dict(base, mesh=mf[f_r], cams=[dict(cams[k], out=os.path.join(outd, "still_%s_f%04d.png" % (k, f_r))) for k in ("oblique", "painting")]),
             dict(base, mesh=mf[f_s], boat=[seat_x, zs, ey_s - 1.83], cams=[dict(sc_, out=os.path.join(outd, "still_seat_f%04d.png" % f_s))])]
    clip_frames = []
    if clip:
        sel = frs[((frs - 1) / 24.0 >= t_r - 10.75) & ((frs - 1) / 24.0 <= t_r + 2.25)]
        clip_frames = [int(f) for f in sel]
        for f in clip_frames:
            scf, eyf = seat_cam((f - 1) / 24.0 + toff)
            items.append(dict(base, mesh=mf[f], boat=[seat_x, zs, eyf - 1.83], cams=[dict(scf, out=os.path.join(outd, "clip_seat", "f%04d.png" % f)),
                                                                              dict(cams["oblique"], out=os.path.join(outd, "clip_oblique", "f%04d.png" % f))]))
    job = dict(res=list(res), items=items)
    jp = os.path.join(outd, "job.json")
    json.dump(job, open(jp, "w", encoding="utf8"))
    subprocess.run([BLENDER, "-b", "--factory-startup", "-P", os.path.join(TOOLS, "e_render_bl.py"), "--", jp], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    info = dict(frame=f_r, t_sim=(f_r - 1) / 24.0, t_group=(f_r - 1) / 24.0 + toff, frame_seat=f_s, t_group_seat=(f_s - 1) / 24.0 + toff,
                crest=crest, seat_x=seat_x, cams=cams, clip_frames=clip_frames)
    json.dump(info, open(os.path.join(outd, "render_info.json"), "w", encoding="utf8"), indent=1, default=float)
    if clip and clip_frames:
        from PIL import Image, ImageDraw, ImageFont
        font = ImageFont.truetype(r"C:/Windows/Fonts/YuGothM.ttc", 22)
        cd = os.path.join(outd, "clip_join"); os.makedirs(cd, exist_ok=True)
        for i, f in enumerate(clip_frames):
            a = Image.open(os.path.join(outd, "clip_seat", "f%04d.png" % f)); b = Image.open(os.path.join(outd, "clip_oblique", "f%04d.png" % f))
            W, H = a.size
            im = Image.new("RGB", (2 * W, H + 40), (250, 250, 248))
            im.paste(a, (0, 40)); im.paste(b, (W, 40))
            dr = ImageDraw.Draw(im)
            dr.text((10, 6), "%s  t=%.2f s（群の時刻）  左：座席の目（x %.0f m、船は水面に上下だけ乗る、目は水面＋1.83 m）  右：斜め  物理だけ（境界の造波と海底のみ）" % (
                os.path.basename(rd), (f - 1) / 24.0 + toff, seat_x), fill=(20, 20, 20), font=font)
            if ride.get("end_t_group") is not None and (f - 1) / 24.0 + toff > ride["end_t_group"]:
                dr.rectangle([0, 40, W, 74], fill=(255, 240, 200))
                dr.text((10, 44), "座席：%.2f s に乗る目が終わった（%s）。以後の左は目が水の中・頂の上で、体験の見え方ではない" % (ride["end_t_group"], ride.get("end_why")),
                        fill=(120, 40, 0), font=font)
            im.save(os.path.join(cd, "f%04d.png" % i))
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", "8", "-i", os.path.join(cd, "f%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-crf", "23", os.path.join(rd, "clip_%s.mp4" % os.path.basename(rd))], check=True)
    print("render ok", rd, f_r)


if __name__ == "__main__":
    res = (960, 540)
    for a in sys.argv:
        if a.startswith("--res"):
            pass
    main(sys.argv[1], clip="--clip" in sys.argv)
