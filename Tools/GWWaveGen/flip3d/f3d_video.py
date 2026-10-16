# -*- coding: utf-8 -*-
"""FLIP3D：Unity が画面外に描いた連番（capture/<seat|print|move>/frame_*.jpg と frames.csv）に字と時の帯を足し、24 fps の mp4 にする（py -3.10 -B、PIL・ffmpeg）。
2026-10-16 進行役（Claude）が新しく書いた。絵（Unity の描画）そのものは変えず、上に字の帯、下に繰り返しの中の時刻の帯を重ねるだけ。
使い方：py -3.10 -B f3d_video.py [seat print move]   → Unity/Build/FLIP3D/video/FLIP3D_DA3_k5_<名前>.mp4 と _sheet.jpg
2026-10-16 追記（--r24）：毎コマの記録 DA3r の 24 個/s のクリップの連番（capture24/<seat|print|move|seat3>）から
  video/FLIP3D_DA3r_k5_r24_<名前>.mp4 を作る。継ぎ目の数は f3d_loop24.py の loop24/loop24_ana.json。--crf <値>（既定 18）。
  py -3.10 -B f3d_video.py --r24 seat print move seat3
"""
import os, sys, csv, json, subprocess, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f3d_common as C   # noqa: E402

CAP = C.OUT + "/capture"
VID = C.OUT + "/video"
FONT = "C:/Windows/Fonts/NotoSansJP-VF.ttf"
NAMES = {"seat": "船の座席から（繰り返し 1 回 12 s）", "print": "原画の視点から（真ん中の断面を横から。繰り返し 1 回 12 s）",
         "move": "座席 → 原画の視点（score3 で原画に最も近い瞬間に着き 2 s 止める）", "seat3": "船の座席から（繰り返し 3 回 36 s）"}
R24 = False
CRF = "18"


def F(s):
    return ImageFont.truetype(FONT, s)


def compose(name):
    d = (C.OUT + "/capture24" if R24 else CAP) + "/" + name
    rows = list(csv.DictReader(open(d + "/frames.csv", encoding="utf8")))
    cap = json.load(open(d + "/capture.json", encoding="utf8"))
    man = json.load(open(C.OUT + ("/clip_DA3r_k5_r24" if R24 else "/clip_DA3_k5") + "/manifest.json", encoding="utf8"))
    prefix = "FLIP3D_DA3r_k5_r24_" if R24 else "FLIP3D_DA3_k5_"
    L = man["loop_seconds"]
    pp = man["print_record_index"] / man["record_fps"]
    tmp = VID + "/_frames_" + name
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    f1, f2, f3 = F(26), F(19), F(22)
    line2 = ("面の記録は 8 個/s（計算の 3 コマおき）。各記録を 3 フレーム保って 24 fps で実時間に見せる（コマの間の形は作らない）。"
             "半分の水槽を対称の面で写して全幅にし、壁で写して 170 m ごとに並べた（計算の仮定そのもの）")
    # 2026-10-16 確かめで直した：継ぎ目は「画面で見える跳び」（最後の記録 → 最初の記録、f3d_seam_jump.py の loop/seam_jump.json）で書く。
    # 前の字は τ と τ + 12 s の違い（計算なら次に来る面との違い）で、見える跳びより小さく、ふつうの 1 歩と同じくらいと読めた
    sj = json.load(open(C.OUT + "/loop/seam_jump.json", encoding="utf8"))
    jm, ss = sj["jump"]["mesh"], sj["steps_summary"]
    line3 = ("計算にない物：水槽の外の平らな海・霧・空・水の色。継ぎ目（%.3f s の次に %.2f s に戻る）の見える跳び：面の距離 中央値 %.2f m・p95 %.2f m"
             "（窓の中のふつうの 0.125 s の 1 歩は p95 %.2f〜%.2f m）。1 歩より大きい"
             % (sj["jump"]["t"][0], sj["jump"]["t"][1], jm["median"], jm["p95"], ss["mesh_p95_min"], ss["mesh_p95_max"]))
    if R24:
        # 毎コマの記録（DA3r）。継ぎ目は f3d_loop24.py の見える跳び（最後の記録 → 最初の記録）を、上の水面の高さの差 Δη の RMS と面どうしの距離で書く
        l4 = json.load(open(C.OUT + "/loop24/loop24_ana.json", encoding="utf8"))["chosen"]
        j4, s4 = l4["jump"], l4["steps_summary"]
        line2 = ("面の記録は 24 個/s（計算の毎コマ。DA3 を途中保存から同じ物理で計算し直した DA3r）を 1 フレームずつ実時間で見せる。コマの間の形は作らない。"
                 "全幅と並びは計算の対称の面・壁の仮定で写した")
        line3 = ("計算にない物：外の平らな海・霧・空・水の色。継ぎ目（%.3f s → %.2f s）の見える跳び：Δη の RMS %.2f m・面の距離 p95 %.2f m。"
                 "窓の中のふつうの 1/24 s の 1 歩は中央値 %.2f m・%.2f m（最大 %.2f m・%.2f m）"
                 % (j4["t"][0], j4["t"][1], j4["eta_break"]["rms"], j4["mesh_nn"]["p95"], s4["eta_rms_median"], s4["nn_p95_median"],
                    s4["eta_rms_max"], s4["nn_p95_max"]))
    sheet_idx = []
    for i, r in enumerate(rows):
        im = Image.open(d + "/frame_%05d.jpg" % i).convert("RGB")
        W, H = im.size
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(ov)
        dr.rectangle([0, 0, W, 112], fill=(0, 0, 0, 150))
        dr.rectangle([0, H - 96, W, H], fill=(0, 0, 0, 150))
        im = Image.alpha_composite(im.convert("RGBA"), ov)
        dr = ImageDraw.Draw(im)
        dr.text((18, 8), "FLIP3D 試作（Unity で実時間に再生）DA3：周期のうねり T 12 s・H 7.5 m、粒子 0.5 m — " + NAMES[name], font=f1, fill=(255, 255, 255))
        dr.text((18, 46), line2, font=f2, fill=(225, 225, 225))
        dr.text((18, 74), line3, font=f2, fill=(225, 225, 225))
        ph, rec, frz, bl = float(r["phase"]), int(r["record"]), int(r["frozen"]), float(r["blend"])
        st = "計算の時刻 %.3f s（記録 %d/%d）" % (float(r["sim_t"]), rec + 1, man["frames"])
        if name == "move":
            st += "　カメラ：" + ("座席" if bl <= 0 else ("原画の視点" if bl >= 1 else "動いている %.0f %%" % (bl * 100)))
        if rec == man["print_record_index"]:
            if man["print_record_frame"] == man["print_bestframes_frame"]:
                st += "　★ score3 で原画に最も近い瞬間（k5、score3 %.3f。計算のコマ %d そのもの）" % (man["print_score3"], man["print_bestframes_frame"])
            else:
                st += "　★ score3 で原画に最も近い瞬間（k5、score3 %.3f。計算のコマ %d、記録はその 1 コマ前）" % (man["print_score3"], man["print_bestframes_frame"])
        if frz:
            st += "　止め（再生の時計だけを止めた）"
        # 下の帯：繰り返しの中の時刻
        x0, x1, y = 260, W - 30, H - 96
        dr.text((18, H - 42), st, font=f3, fill=(255, 255, 255))
        dr.text((18, y + 6), "繰り返しの中の時刻", font=f2, fill=(220, 220, 220))
        dr.text((x0 + 0.0, y + 28), "0 s（%.2f s）" % man["loop_start_s"], font=F(15), fill=(200, 200, 200))
        dr.text((x1 - 120, y + 28), "12 s（継ぎ目）", font=F(15), fill=(200, 200, 200))
        dr.line([(x0, y + 18), (x1, y + 18)], fill=(200, 200, 200), width=2)
        X = lambda p: x0 + p / L * (x1 - x0)
        for k in range(0, int(L) + 1):
            dr.line([(X(k), y + 12), (X(k), y + 24)], fill=(200, 200, 200), width=1)
        dr.line([(X(pp), y + 6), (X(pp), y + 30)], fill=(255, 210, 60), width=3)
        dr.text((X(pp) - 60, y + 28), "★ score3 の最良", font=F(15), fill=(255, 210, 60))
        dr.ellipse([X(ph) - 7, y + 11, X(ph) + 7, y + 25], fill=(255, 255, 255))
        im.convert("RGB").save(tmp + "/f_%05d.jpg" % i, quality=92)
    n = len(rows)
    out = VID + "/" + prefix + "%s.mp4" % name
    cmd = [C.FFMPEG, "-y", "-loglevel", "error", "-framerate", "24", "-i", tmp + "/f_%05d.jpg", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", CRF,
           "-preset", "medium", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    # 一覧の絵（8 枚）
    pick = [int(v) for v in np.linspace(0, n - 1, 8)]
    ims = [Image.open(tmp + "/f_%05d.jpg" % i).resize((640, 360)) for i in pick]
    S = Image.new("RGB", (1280, 360 * ((len(ims) + 1) // 2)))
    for j, a in enumerate(ims):
        S.paste(a, ((j % 2) * 640, (j // 2) * 360))
    S.save(VID + "/" + prefix + "%s_sheet.jpg" % name, quality=90)
    shutil.rmtree(tmp, ignore_errors=True)
    return dict(name=name, mp4=out, frames=n, seconds=n / 24.0, bytes=os.path.getsize(out))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    os.makedirs(VID, exist_ok=True)
    args = sys.argv[1:]
    if "--r24" in args:
        R24 = True
        args.remove("--r24")
    if "--crf" in args:
        CRF = args[args.index("--crf") + 1]
        del args[args.index("--crf"):args.index("--crf") + 2]
    names = args or ["seat", "print", "move"]
    res = [compose(nm) for nm in names]
    print(json.dumps(res, ensure_ascii=False, indent=1))
