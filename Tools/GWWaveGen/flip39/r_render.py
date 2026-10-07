# -*- coding: utf-8 -*-
"""FLIP39 R：確かめの動画と図（py -3.10 で job を作り、Blender 5.2.2 の Workbench（粘土）で描き、PIL と ffmpeg で並べる）。
使い方:
  py -3.10 r_render.py video <箱の run_dir> [--seat=x,z] [--only=seat,oblique,painting] [--encode]
  py -3.10 r_render.py turntable <箱の run_dir> <frame>
  py -3.10 r_render.py before            （FLIP37 P3 を D1 の座席から描く。図の「前」）

カメラ（どれも計算の座標。1 単位 = 1 m。倍率はかけない）：
- seat（座席の目）：座席（x_s, z_s）の船の長さ 11.33 m の下の一番上の水面の中央値 + 1.83 m（船は上下だけ水面に乗る。e_seat の乗る目と同じ）。
  乗る目の仰角が最大になった時（seat_r の t_alpha_max。その直後に乗る目が終わる：水が目の高さに来る、または船が頂の 0.85 倍まで持ち上げられる）から、
  目の高さをその時の値のまま止める（船の持ち上げ・傾き・押し流し・転覆は計算していないため。動画にそう書く）。向きは沖（−x、波の来る向き）。見上げる角は、座席の列で見た頂の仰角 α の
  0.55 倍（10°〜42°、0.5 秒でならす）。縦の画角 90°（16:9 で横 121°。PS VR2 の視野 約 110° に近い広さ）。これは見せ方であり、水の動きには関わらない。
- oblique（固定の斜め）：岸の側・峰の手前の高い所から、伝わる→立ち上がる→崩れるの全部を一つの画に入れる固定のカメラ。
- painting（原画カメラ）：E の e_render と同じ（P3 の置き方の頂からの相対の位置を、倍率をかけずにこの計算の頂へ移す）。雰囲気の参考で、合わせの点数は付けない。
画の中の色：粘土色＝細かい計算（粒子 0.3 m）の範囲、青みの灰色＝その外（E3、粒子 1 m の一番上の水面。張り出しは描けない）と水槽の外の平らな海。
"""
import sys, os, json, glob, subprocess
import numpy as np

BLENDER = r"G:/SteamLibrary/steamapps/common/Blender/blender.exe"
FFMPEG = r"G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
TOOLS = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39"
R = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/R"
COARSE = R + "/render/coarse_eta.npz"
PLACE = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P3/H25_R18_mg/place_p3.json"
PAINT = r"G:/Unity/GreatWave_2026_Fresh/Docs/References/Met_JP1847_DP130155.jpg"
PCAM_POS = np.array([0.0, 3.0, -62.0]); PCAM_LOOK = np.array([-2.5, 9.7, 4.0])   # PaintingCam v1（Unity の座標）
TOFF = 35.0
EYE = 1.83
BOAT = 11.33
FONT = r"C:/Windows/Fonts/YuGothM.ttc"
FONTB = r"C:/Windows/Fonts/YuGothB.ttc"
sys.path.insert(0, TOOLS)


def painting_rel():
    pl = json.load(open(PLACE, encoding="utf8"))
    Mi = np.linalg.inv(np.array(pl["M_sim_to_unity"]))
    pos = (Mi @ np.r_[PCAM_POS, 1.0])[:3]; look = (Mi @ np.r_[PCAM_LOOK, 1.0])[:3]
    a = np.array(pl["anchor"])
    return pos - a, look - a, float(a[1])


def mesh_files(rd):
    return {int(os.path.basename(f)[5:9]): f for f in glob.glob(os.path.join(rd, "mesh", "mesh_*.npz"))}


def smooth(v, n):
    if len(v) < n or n < 2:
        return np.asarray(v, float)
    ker = np.ones(n) / n
    return np.convolve(np.pad(np.asarray(v, float), (n // 2, n - 1 - n // 2), mode="edge"), ker, mode="valid")


def seat_track(rd, xs, zs):
    """座席の目の高さと見上げる角を、細かい計算の一番上の水面から毎コマ出す。"""
    from r_seat import Merged
    M = Merged(rd)
    B = M.B
    xb, zb = M.xb, M.zb
    rows = np.abs(zb - zs) <= max(0.9, 0.51 * (zb[1] - zb[0]))
    hull = (xb >= xs - 0.5 * BOAT) & (xb <= xs + 0.5 * BOAT)
    sj = os.path.join(rd, "seat_r_z%+04d.json" % int(round(zs)))
    end_t = None; t_hold = None; dist_at = None
    if os.path.isfile(sj):
        S = json.load(open(sj, encoding="utf8"))
        for r in S["scan"]:
            if abs(r["x_seat"] - xs) < 0.3:
                end_t = (r.get("ride") or {}).get("end_t_group")
                t_hold = (r.get("ride") or {}).get("t_alpha_max")
                dist_at = (r.get("ride") or {}).get("dist_at")
    # 目の高さを止める時刻：乗る目の仰角が最大の時（乗る目の終わり＝船が持ち上げられる・水が目に来る の直前）。
    # その後の船の動き（持ち上げ・転覆・押し流し）は計算していないので、止めて「船を止めた見え方」として見せる（動画に書く）
    if t_hold is None:
        t_hold = end_t
    fr, ey, al, hc = [], [], [], []
    frozen = None
    for k in range(len(B["frames"])):
        f = int(B["frames"][k]); tg = float(B["t"][k]) + TOFF
        Eb = B["eta"][k].astype(float) - M.off_box; Sb = B["seg"][k]
        rl = np.nanmax(Eb[rows], axis=0); sl = Sb[rows].max(axis=0)
        under = rl[hull & (sl <= 1)]
        ys = float(np.nanmedian(under)) if np.isfinite(under).any() else 0.0
        e = ys + EYE
        if t_hold is not None and tg >= t_hold:
            if frozen is None:
                frozen = ey[-1] if ey else e
            e = frozen
        sea = (xb < xs - 2) & (xb > xs - 200)
        D = xs - xb[sea]; H = rl[sea] - e
        a = np.degrees(np.arctan2(H, np.maximum(D, 0.5)))
        a = np.where(np.isfinite(a), a, -90)
        fr.append(f); ey.append(e); al.append(float(a.max())); hc.append(float(np.nanmax(rl[sea])))
    pitch = np.clip(0.55 * smooth(al, 12), 10.0, 42.0)
    return dict(frames=fr, eye_y=ey, alpha=al, pitch=pitch.tolist(), end_t=end_t, t_hold=t_hold, dist_at=dist_at, off=M.off_box, crest=hc)


def cams_painting(crest, zs):
    xc, yc, zc = crest
    prel, lrel, Hp3 = painting_rel()
    pos = np.array([xc + prel[0], Hp3 + prel[1], zc + abs(prel[2])])
    look = np.array([xc + lrel[0], Hp3 + lrel[1] - (Hp3 - yc) * 0.5, zc + abs(lrel[2]) * np.sign(lrel[2] * prel[2])])
    return dict(pos=pos.tolist(), look=look.tolist(), vfov=26.0, near=1.0)


BACK = 45.0   # 座席の後ろのカメラの距離 (m)。座席 + 30 m・高さ 4 m では 87.5 s にカメラが崩れた水に入った（10/8 04:50 の試し）ので、45 m・高さ 8 m にした
BACK_Y = 8.0
OBLIQUE = dict(pos=[625.0, 24.0, 30.0], look=[465.0, 1.0, -112.0], vfov=40.0, near=1.0)   # 10/8 04:15 の試し（細かい計算の網目）：箱の全部（伝わる→立ち上がる→崩れる）と崩れた水の広がりが一つの画に入る所。もっと近い置き方（575, 16, −5）では 84 s の崩れが画の右の外へ出た


def run_blender(job, jp):
    json.dump(job, open(jp, "w", encoding="utf8"))
    subprocess.run([BLENDER, "-b", "--factory-startup", "-P", os.path.join(TOOLS, "r_render_bl.py"), "--", jp], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def video(rd, xs, zs, only=("seat", "oblique", "painting"), encode=False, f_lo=None, f_hi=None):
    an = json.load(open(os.path.join(rd, "analysis_r.json"), encoding="utf8")) if os.path.isfile(os.path.join(rd, "analysis_r.json")) else None
    st = seat_track(rd, xs, zs)
    off = st["off"]
    mf = mesh_files(rd)
    frs = [f for f in st["frames"] if f in mf and (f_lo is None or f >= f_lo) and (f_hi is None or f <= f_hi)]
    outd = os.path.join(rd, "render"); os.makedirs(outd, exist_ok=True)
    # 原画カメラ：主の列の前の面が垂直を過ぎた時の頂（なければ E3 の値）
    # 原画カメラの頂：座席の乗る目の仰角が最大の時（波が座席の上にいちばん高くそびえる瞬間）の、座席の列の頂（analysis_r の crest_history_main）。
    # E は「前の面が垂直を過ぎた時 + 0.75 s」の頂だったが、R の座席の列では垂直を過ぎた最初の時（80.1 s）が頂の先の小さな崩れで、主な崩れではないため
    crest = [475.65, 15.7, zs]
    if an and st.get("t_hold") is not None and an.get("crest_history_main"):
        ch = an["crest_history_main"]
        k = int(np.argmin(np.abs(np.array(ch["t_group"]) - st["t_hold"])))
        crest = [float(ch["x"][k]), float(ch["crest"][k]), zs]
    pc = cams_painting(crest, zs)
    from r_compare import load_box
    win = load_box(rd)["grid"]["window"]
    pad = 4.0
    hole = [win[0] + pad, win[1] - pad, -1000.0, win[3] - pad]   # z の低い側は鏡（-120 の向こうも細かい計算の鏡）
    items = []
    idx = {f: i for i, f in enumerate(st["frames"])}
    for f in frs:
        i = idx[f]
        ey = st["eye_y"][i]; p = np.radians(st["pitch"][i])
        cams = []
        if "seat" in only:
            cams.append(dict(pos=[xs, ey, zs], look=[xs - 100.0 * np.cos(p), ey + 100.0 * np.sin(p), zs], vfov=90.0, near=0.2,
                             out=os.path.join(outd, "seat", "f%04d.png" % f)))
        if "oblique" in only:
            cams.append(dict(OBLIQUE, out=os.path.join(outd, "oblique", "f%04d.png" % f)))
        if "painting" in only:
            cams.append(dict(pc, out=os.path.join(outd, "painting", "f%04d.png" % f)))
        if "seatback" in only and st.get("t_hold") is not None and (f - 1) / 24.0 + TOFF >= st["t_hold"] - 0.5:
            # 乗る目が終わった後の崩れ：座席の BACK m 後ろ（岸の側）・高さ 4 m から、座席（船）ごと沖を見る（目の位置では水の中になるため）
            pb = np.radians(12.0)
            cams.append(dict(pos=[xs + BACK, BACK_Y, zs], look=[xs + BACK - 100.0 * np.cos(pb), BACK_Y + 100.0 * np.sin(pb), zs], vfov=90.0, near=0.2,
                             out=os.path.join(outd, "seatback", "f%04d.png" % f)))
        items.append(dict(frame=f, fine=mf[f], fine_off=off, flip=True, boat=[xs - 1.0, ey - EYE, zs], cams=cams))
    job = dict(res=[1280, 720], coarse=dict(npz=COARSE, hole=hole), items=items)
    run_blender(job, os.path.join(outd, "job_video.json"))
    # 原画カメラの真下の一番上の水面（細かい計算、ずれを引いた）：カメラが水に入るコマに印を付ける
    from r_seat import Merged
    M = Merged(rd)
    ixc = int(np.argmin(np.abs(M.xb - pc["pos"][0]))); izc = int(np.argmin(np.abs(M.zb - pc["pos"][2])))
    wet_paint = {int(f): bool(np.nanmax(M.B["eta"][k][max(izc - 2, 0):izc + 3, max(ixc - 2, 0):ixc + 3]) - M.off_box > pc["pos"][1])
                 for k, f in enumerate(M.B["frames"])}
    info = dict(seat=[xs, zs], track=st, painting_cam=pc, painting_crest=crest, oblique_cam=OBLIQUE, seatback_cam=dict(pos=[xs + BACK, BACK_Y, zs], pitch_deg=12.0, vfov=90.0),
                frames=frs, off_box=off, painting_cam_wet_frames=[f for f, w in wet_paint.items() if w])
    json.dump(info, open(os.path.join(outd, "render_info.json"), "w", encoding="utf8"), indent=1, default=float)
    if encode:
        compose(rd, info, an)


def time_bar(dr, W, y0, tg, t0, t1, events, font):
    x0, x1 = 20, W - 20
    dr.rectangle([x0, y0, x1, y0 + 10], fill=(225, 225, 222))
    xx = x0 + (x1 - x0) * (tg - t0) / (t1 - t0)
    dr.rectangle([x0, y0, xx, y0 + 10], fill=(70, 90, 120))
    for lab, te in events:
        if te is None:
            continue
        xe = x0 + (x1 - x0) * (te - t0) / (t1 - t0)
        dr.line([xe, y0 - 4, xe, y0 + 14], fill=(170, 40, 30), width=2)
        dr.text((xe + 3, y0 + 12), lab, fill=(170, 40, 30), font=font)


def compose(rd, info, an):
    from PIL import Image, ImageDraw, ImageFont
    f1 = ImageFont.truetype(FONT, 22); f2 = ImageFont.truetype(FONT, 18); fb = ImageFont.truetype(FONTB, 24)
    outd = os.path.join(rd, "render")
    frs = info["frames"]; st = info["track"]
    t0, t1 = 75.0, 87.5   # 細かい計算の範囲（コマ 961〜1261）
    ev = ((an or {}).get("rows", {}).get("%d" % int(round(info["seat"][1]))) or {}).get("events") or {}
    # 時刻の印：座席の列で頂の先が初めて垂直を過ぎた時、座席の目に水が来た時、z −60 m の列で空洞が閉じた時
    ev60 = ((an or {}).get("rows", {}).get("-60") or {}).get("events") or {}
    tc60 = (ev60.get("tube_closed_or_nearly") or {}).get("t")
    events = [("頂の先が崩れ始めた", (ev.get("face_past_vertical") or {}).get("t_group")),
              ("座席の目に水", st.get("end_t")),
              ("z−60 m で空洞が閉じた", (tc60 + TOFF) if tc60 is not None else None)]
    paint = Image.open(PAINT).convert("RGB")
    idx = {f: i for i, f in enumerate(st["frames"])}
    xs, zs = info["seat"]
    for cam in ("seat", "oblique", "painting"):
        src = os.path.join(outd, cam)
        if not os.path.isdir(src):
            continue
        cd = os.path.join(outd, "join_" + cam); os.makedirs(cd, exist_ok=True)
        n = 0
        seq = [(f, None) for f in frs]
        if cam == "seat" and st.get("t_hold") is not None and os.path.isdir(os.path.join(outd, "seatback")):
            fh = int(round((st["t_hold"] - TOFF) * 24)) + 1
            fz = fh - 10   # 止めた画は目に水が来る約 0.4 秒前（仰角が最大のコマは前の面が目から約 3 m で、画が面の近写しになるため）
            seq = [(f, None) for f in frs if f <= fh] + [(fz, "freeze")] * 18 + [(f, "back") for f in frs if f > fh]
        for f, mode in seq:
            pth = os.path.join(src if mode != "back" else os.path.join(outd, "seatback"), "f%04d.png" % f)
            if not os.path.exists(pth):
                continue
            a = Image.open(pth).convert("RGB")
            tg = (f - 1) / 24.0 + TOFF
            if cam == "painting":
                a = a.resize((960, 540))
                ph = paint.resize((int(paint.width * 540 / paint.height), 540))
                W = 960 + ph.width; H = 540 + 120
                im = Image.new("RGB", (W, H), (250, 250, 248)); im.paste(a, (0, 70)); im.paste(ph, (960, 70))
                dr = ImageDraw.Draw(im)
                dr.text((12, 6), "③ 原画カメラ（雰囲気の比べ。合わせの点数は付けない）  群の時刻 %.2f s" % tg, fill=(20, 20, 20), font=fb)
                dr.text((12, 40), "左：計算（物理だけ：境界の造波と海底のみ）。カメラは P3 の置き方の相対の位置を倍率なしでこの頂へ移したもの　右：原画（Met JP1847）", fill=(60, 60, 60), font=f2)
                if f in set(info.get("painting_cam_wet_frames") or []):
                    dr.rectangle([0, 70, 960, 104], fill=(255, 240, 200))
                    dr.text((12, 74), "このコマはカメラ（高さ %.1f m）が水に入っている" % info["painting_cam"]["pos"][1], fill=(120, 40, 0), font=f2)
                time_bar(dr, W, H - 40, tg, t0, t1, events, f2)
            else:
                W, H = a.width, a.height + 110
                im = Image.new("RGB", (W, H), (250, 250, 248)); im.paste(a, (0, 70))
                dr = ImageDraw.Draw(im)
                if cam == "seat" and mode == "back":
                    dr.text((12, 6), "① 座席の %.0f m 後ろ（岸の側、x %.0f m・高さ %.0f m）から座席の船ごと沖を見る  群の時刻 %.2f s" % (BACK, xs + BACK, BACK_Y, tg), fill=(20, 20, 20), font=fb)
                    dr.text((12, 40), "物理だけ：境界の造波と海底のみ。座席の目は %.2f s に水が来て終わった（目の位置は水の中になる）ので、崩れはここから見せる。灰色の箱＝座席の船" % (st["end_t"] or st["t_hold"]),
                            fill=(60, 60, 60), font=f2)
                elif cam == "seat":
                    i = idx[f]
                    dr.text((12, 6), "① 座席の目（x %.0f m・z %.0f m、船は水面に上下だけ乗る、目は水面＋1.83 m）  群の時刻 %.2f s" % (xs, zs, tg), fill=(20, 20, 20), font=fb)
                    dr.text((12, 40), "物理だけ：境界の造波と海底のみ。計算の中に力・速さを足していない。粘土色＝細かい計算（粒子 0.3 m）、青みの灰色＝外（粒子 1 m）", fill=(60, 60, 60), font=f2)
                    if mode == "freeze":
                        dr.rectangle([0, 70, W, 104], fill=(255, 240, 200))
                        dr.text((12, 74), "止めた画（0.75 秒）：群の時刻 %.2f s。この 0.4 秒後（%.2f s）に水が船の上の目の高さに来る＝乗る目の終わり" % (tg, st["end_t"] or st["t_hold"]),
                                fill=(120, 40, 0), font=f2)
                    dr.text((W - 330, 78 if mode != "freeze" else 110), "見上げる角 %.0f°（頂の仰角 %.0f°）" % (st["pitch"][i], st["alpha"][i]), fill=(30, 30, 30), font=f2)
                else:
                    dr.text((12, 6), "② 固定の斜め（岸の側・峰の手前の高い所から）  群の時刻 %.2f s" % tg, fill=(20, 20, 20), font=fb)
                    dr.text((12, 40), "物理だけ：境界の造波と海底のみ。粘土色＝細かい計算（粒子 0.3 m）、青みの灰色＝外（粒子 1 m）。灰色の箱＝座席の船（長さ 11.33 m）", fill=(60, 60, 60), font=f2)
                time_bar(dr, W, H - 36, tg, t0, t1, events, f2)
            im.save(os.path.join(cd, "f%04d.png" % n)); n += 1
        if n == 0:
            continue
        for fps, tag in ((24, ""), (12, "_half")):
            if cam != "seat" and tag:
                continue
            subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(cd, "f%04d.png"),
                            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                            os.path.join(rd, "video_%s%s.mp4" % (cam, tag))], check=True)
        print("video", cam, n)


def turntable(rd, f, crest_xyz, radius=170.0, height=40.0, vfov=40.0):
    mf = mesh_files(rd)
    from r_seat import Merged
    off = Merged(rd).off_box
    outd = os.path.join(rd, "render", "turntable"); os.makedirs(outd, exist_ok=True)
    xc, yc, zc = crest_xyz
    cams = []
    for k in range(12):
        th = np.radians(30.0 * k)
        # 0°＝岸の側（+x）から沖を見る。角は上から見て反時計回り
        pos = [xc + radius * np.cos(th), height, zc + radius * np.sin(th)]
        cams.append(dict(pos=pos, look=[xc, 0.35 * yc, zc], vfov=vfov, near=1.0, out=os.path.join(outd, "a%03d.png" % (30 * k))))
    from r_compare import load_box
    win = load_box(rd)["grid"]["window"]
    hole = [win[0] + 4, win[1] - 4, -1000.0, win[3] - 4]
    job = dict(res=[960, 540], coarse=dict(npz=COARSE, hole=hole), items=[dict(frame=f, fine=mf[f], fine_off=off, flip=True, boat=None, cams=cams)])
    run_blender(job, os.path.join(outd, "job.json"))
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(FONT, 20)
    W, H = 480, 270
    im = Image.new("RGB", (4 * W, 3 * H + 50), (250, 250, 248))
    dr = ImageDraw.Draw(im)
    dr.text((10, 10), "12 の角度の粘土（群の時刻 %.2f s、中心 (%.0f, %.1f, %.0f)＝z −120 m の対称の面の上、半径 %.0f m・高さ %.0f m。0°＝岸の側から沖を見る。鏡に映した海）。粘土色＝粒子 0.3 m、青みの灰色＝外" % (
        (f - 1) / 24.0 + TOFF, xc, yc, zc, radius, height), fill=(20, 20, 20), font=font)
    for k in range(12):
        a = Image.open(os.path.join(outd, "a%03d.png" % (30 * k))).resize((W, H))
        x0, y0 = (k % 4) * W, 50 + (k // 4) * H
        im.paste(a, (x0, y0))
        dr.text((x0 + 6, y0 + 4), "%d°" % (30 * k), fill=(20, 20, 20), font=font)
    im.save(os.path.join(rd, "turntable_12.png"))
    import shutil
    sq = os.path.join(outd, "seq"); os.makedirs(sq, exist_ok=True)
    for k in range(12):
        shutil.copyfile(os.path.join(outd, "a%03d.png" % (30 * k)), os.path.join(sq, "t%02d.png" % k))
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", "2", "-i", os.path.join(sq, "t%02d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", os.path.join(rd, "turntable_12.mp4")], check=True)
    print("turntable ok")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "video":
        rd = sys.argv[2]
        xs, zs = 500.0, -80.0
        only = ("seat", "oblique", "painting")
        f_lo = f_hi = None
        for a in sys.argv[3:]:
            if a.startswith("--seat="):
                xs, zs = (float(v) for v in a.split("=")[1].split(","))
            if a.startswith("--only="):
                only = tuple(a.split("=")[1].split(","))
            if a.startswith("--frames="):
                f_lo, f_hi = (int(v) for v in a.split("=")[1].split(","))
        video(rd, xs, zs, only=only, encode="--encode" in sys.argv, f_lo=f_lo, f_hi=f_hi)
    elif cmd == "turntable":
        rd = sys.argv[2]; f = int(sys.argv[3])
        crest = [float(v) for v in sys.argv[4].split(",")]
        turntable(rd, f, crest)
