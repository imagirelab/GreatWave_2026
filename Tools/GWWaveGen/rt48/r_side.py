# -*- coding: utf-8 -*-
"""RT48（計画 §3.6、record_ja.md の V10）：焼いた断面の曲線を、横から見た 2 次元の絵にして実時間の動画にする（py -3.10、numpy・OpenCV・PIL）。
使い方:
  py -3.10 r_side.py coarse                         → Unity/Build/RT48/video/rt48_side_coarse.mp4（138.25〜162.0 s、60 fps、1920×1080）
  py -3.10 r_side.py coarse --stills 154.708,156.0  静止画だけ
  （細かい元ができたら：py -3.10 r_side.py fine,coarse で上下に並べる）
時刻の規則は Unity と同じ（u_bakeio.state_at：補間する組だけ割合で混ぜ、ほかは前のコマを保つ）。形は焼いた曲線のまま描き、手で変えない。
x の両端の下ろし（x 100〜200 m・825〜925 m）は Unity と同じに掛け、全体の帯で灰色に塗って示す。"""
import os as _os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")
import sys, os, json, math, time, subprocess, argparse
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import u_bakeio as U

BUILD = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
W, H = 1920, 1080
FONT = "C:/Windows/Fonts/YuGothM.ttc"
FONT_B = "C:/Windows/Fonts/YuGothB.ttc"
X_DETAIL = (470.0, 620.0)       # 計画 §3.6
Y_DETAIL = (-14.0, 20.0)
X_ALL = (100.0, 925.0)
Y_ALL = (-12.0, 14.0)
SEAT_MAIN, SEAT_OTHER = 556.0, 574.0
C_SKY = (214, 225, 232)
C_WATER = (28, 78, 96)
C_LINE = (8, 32, 42)
C_TEXT = (24, 28, 32)
C_BG = (246, 246, 244)
C_TAPER = (150, 150, 150)
C_HULL = (110, 64, 30)
SS = 4                           # cv2 の shift（1/16 画素）


class Src:
    def __init__(self, name):
        d = os.path.join(BUILD, "data", name)
        self.name = name
        self.man = json.load(open(os.path.join(d, "manifest.json"), encoding="utf8"))
        man = self.man
        self.N = man["n_points"]
        self.P = man["playback"]["n_pairs"]
        self.pairs = np.fromfile(os.path.join(d, "pairs.bin"), dtype="<f4").reshape(self.P, 2, self.N, 2)
        self.loops = np.fromfile(os.path.join(d, "loops.bin"), dtype="<f4").reshape(-1, 2)
        fx = man["x_fade"]["ranges_x_rel"]
        self.meta = dict(fps=man["time"]["fps"], frame_first=man["time"]["first_frame"], frame_count=man["time"]["n_frames"], pair_count=self.P,
                         n_points=self.N, pair_interp=[1 if q["interp"] else 0 for q in man["pairs"]], x_origin_m=man["coords"]["origin_x_rel"],
                         taper_m=[fx[0][0], fx[0][1], fx[1][0], fx[1][1]])
        self.reason = [q["reason"] for q in man["pairs"]]
        self.tp = U.taper_stored(self.meta)
        self.x0 = self.meta["x_origin_m"]
        self.loops_index = {r["frame"]: r["loops"] for r in man["loops_index"]}
        self.K = man["playback"]["K"]
        self.ev = man["events"]
        self.boat = man["boat"]
        self.cache = {}

    def at(self, t):
        st = U.state_at(self.meta, t)
        raw = U.curve_for_state(self.pairs, st)
        disp = U.displayed(raw, self.tp)
        disp[:, 0] += self.x0
        f = self.meta["frame_first"] + st["frame"]
        lps = []
        for off, cnt, ph, area in self.loops_index.get(f, []):
            p = self.loops[off:off + cnt].astype(np.float64)
            q = np.stack([p[:, 0] + self.x0, p[:, 1] * U.taper_weight(p[:, 0], self.tp)], 1)
            lps.append((ph, q))
        return st, f, disp, lps

    def boat_at(self, t, seat):
        c = self.cache.setdefault(seat, {})
        h, p, mode, st = U.boat_at(self.pairs, self.meta, t, seat, c)
        return h, p, mode


class Panel:
    def __init__(self, x0, y0, w, xr, yr):
        self.x0, self.y0, self.w = x0, y0, w
        self.xr, self.yr = xr, yr
        self.s = w / (xr[1] - xr[0])           # 画素/m（縦横同じ）
        self.h = int(round((yr[1] - yr[0]) * self.s))

    def px(self, P):
        X = (P[:, 0] - self.xr[0]) * self.s
        Y = (self.yr[1] - P[:, 1]) * self.s
        return np.stack([X, Y], 1)

    def ipts(self, P):
        return np.round(self.px(P) * (1 << SS)).astype(np.int32)


def draw_section(img, pan, disp, loops, boat=None, boat_ghost=False, seats=(), taper=None, fine_lines=True):
    sub = np.empty((pan.h, pan.w, 3), np.uint8)
    sub[:] = C_SKY
    if taper is not None:   # 下ろした帯
        for a, b in taper:
            xa = int((a - pan.xr[0]) * pan.s); xb = int((b - pan.xr[0]) * pan.s)
            if xb > 0 and xa < pan.w:
                sub[:, max(0, xa):min(pan.w, xb)] = (200, 200, 200)
    # 水：主な曲線の下を塗る（右下・左下へ閉じる）
    bottom = pan.yr[0] - 5.0
    poly = np.vstack([disp, [[disp[-1, 0], bottom], [disp[0, 0], bottom]]])
    cv2.fillPoly(sub, [pan.ipts(poly)], C_WATER, lineType=cv2.LINE_AA, shift=SS)
    for ph, q in loops:     # 囲んだ空気は穴、離れた水は塗る（空気を先に）
        if ph == 1:
            cv2.fillPoly(sub, [pan.ipts(q)], C_SKY, lineType=cv2.LINE_AA, shift=SS)
    for ph, q in loops:
        if ph != 1:
            cv2.fillPoly(sub, [pan.ipts(q)], C_WATER, lineType=cv2.LINE_AA, shift=SS)
    if fine_lines:
        cv2.polylines(sub, [pan.ipts(disp)], False, C_LINE, 1, lineType=cv2.LINE_AA, shift=SS)
        for ph, q in loops:
            cv2.polylines(sub, [pan.ipts(q)], True, C_LINE, 1, lineType=cv2.LINE_AA, shift=SS)
    # 静かな水面の線（破線）
    y0 = int(round((pan.yr[1] - 0.0) * pan.s))
    for xs in range(0, pan.w, 16):
        cv2.line(sub, (xs, y0), (min(xs + 9, pan.w - 1), y0), (250, 250, 250), 1, cv2.LINE_AA)
    # 座席
    for sx, lab in seats:
        p = pan.px(np.array([[sx, 0.0]]))[0]
        tri = np.array([[p[0], p[1] + 2], [p[0] - 6, p[1] + 13], [p[0] + 6, p[1] + 13]])
        cv2.fillPoly(sub, [np.round(tri * (1 << SS)).astype(np.int32)], (200, 40, 40), lineType=cv2.LINE_AA, shift=SS)
    # 船（座席 556 m：上下と縦揺れ）
    if boat is not None:
        sx, h, pdeg = boat
        hull = np.array([[-6.0, 0.15], [-5.0, -0.45], [6.0, -0.45], [6.0, 0.45], [-5.4, 0.45]])
        a = math.radians(pdeg)
        R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
        q = hull @ R.T + np.array([sx, h])
        if boat_ghost:
            cv2.polylines(sub, [pan.ipts(q)], True, C_HULL, 2, lineType=cv2.LINE_AA, shift=SS)
        else:
            cv2.fillPoly(sub, [pan.ipts(q)], C_HULL, lineType=cv2.LINE_AA, shift=SS)
    img[pan.y0:pan.y0 + pan.h, pan.x0:pan.x0 + pan.w] = sub
    cv2.rectangle(img, (pan.x0 - 1, pan.y0 - 1), (pan.x0 + pan.w, pan.y0 + pan.h), (90, 90, 90), 1)


def wrap(s, n):
    out, line = [], ""
    for ch in s:
        line += ch
        if len(line) >= n and ch in "、。）":
            out.append(line); line = "　"
    if line.strip():
        out.append(line)
    return out


class Frame:
    def __init__(self, srcs):
        self.srcs = srcs
        self.f_s = ImageFont.truetype(FONT, 19)
        self.f_m = ImageFont.truetype(FONT, 22)
        self.f_b = ImageFont.truetype(FONT_B, 24)
        self.f_t = ImageFont.truetype(FONT, 15)
        top = 58
        self.overview = Panel(40, top + 26, W - 80, X_ALL, Y_ALL)
        n = len(srcs)
        y = self.overview.y0 + self.overview.h + 54
        self.details = []
        for i in range(n):
            pan = Panel(40, y, W - 80, X_DETAIL, Y_DETAIL) if n == 1 else Panel(40, y, W - 80, X_DETAIL, (-10.0, 14.0))
            self.details.append(pan)
            y += pan.h + 46
        self.text_y = y - 14
        idx = json.load(open(os.path.join(BUILD, "data", "manifest.json"), encoding="utf8"))
        self.cap = idx["captions"]

    def render(self, t):
        img = np.empty((H, W, 3), np.uint8)
        img[:] = C_BG
        s0 = self.srcs[0]
        st, f, disp, loops = s0.at(t)
        end556 = s0.boat[str(int(SEAT_MAIN))]["clip_end_t"]
        hb, pb, mb = s0.boat_at(min(t, end556), SEAT_MAIN)
        ghost = t > end556 + 1e-9
        fx = s0.man["x_fade"]["ranges_x_rel"]
        # 全体の帯
        draw_section(img, self.overview, disp, loops, boat=None, seats=((SEAT_MAIN, ""), (SEAT_OTHER, "")),
                     taper=[(fx[0][0], fx[0][1]), (fx[1][0], fx[1][1])], fine_lines=False)
        ov = self.overview
        xa = ov.x0 + int((X_DETAIL[0] - X_ALL[0]) * ov.s); xb = ov.x0 + int((X_DETAIL[1] - X_ALL[0]) * ov.s)
        cv2.rectangle(img, (xa, ov.y0 - 2), (xb, ov.y0 + ov.h + 1), (200, 40, 40), 1)
        # 細かく見る窓
        for s, pan in zip(self.srcs, self.details):
            st_s, f_s, disp_s, loops_s = s.at(t)
            draw_section(img, pan, disp_s, loops_s, boat=(SEAT_MAIN, hb, pb), boat_ghost=ghost,
                         seats=((SEAT_MAIN, ""), (SEAT_OTHER, "")))
            # 10 m の物差し（横と縦）と目盛り
            bx, by = pan.x0 + 30, pan.y0 + pan.h - 30
            L10 = int(round(10 * pan.s))
            cv2.line(img, (bx, by), (bx + L10, by), (20, 20, 20), 3)
            cv2.line(img, (bx, by), (bx, by - L10), (20, 20, 20), 3)
            for xm in range(int(math.ceil(X_DETAIL[0] / 10) * 10), int(X_DETAIL[1]) + 1, 10):
                xp = pan.x0 + int(round((xm - X_DETAIL[0]) * pan.s))
                cv2.line(img, (xp, pan.y0 + pan.h), (xp, pan.y0 + pan.h + (8 if xm % 50 == 0 else 4)), (60, 60, 60), 1)
        pim = Image.fromarray(img)
        d = ImageDraw.Draw(pim)
        d.text((40, 12), "横から見た断面（FLIP42 R3：重力だけの FLIP、粒子 0.25 m）の再生　実時間　縦横同じ縮尺", font=self.f_b, fill=C_TEXT)
        d.text((W - 40, 14), "計算の時刻 %.3f s" % t, font=self.f_b, fill=C_TEXT, anchor="ra")
        d.text((ov.x0, ov.y0 - 24), "断面の全体 x 100〜925 m（灰色の帯は x の両端の下ろし：計算にない形。赤い枠が下の窓、▲ は座席 556 m・574 m）",
               font=self.f_t, fill=C_TEXT)
        for s, pan in zip(self.srcs, self.details):
            lab = s.man["label"]
            d.text((pan.x0, pan.y0 - 26), "x %d〜%d m（造波板からの距離）　%s" % (X_DETAIL[0], X_DETAIL[1], lab), font=self.f_s, fill=C_TEXT)
            bx, by = pan.x0 + 30, pan.y0 + pan.h - 30
            d.text((bx + int(10 * pan.s) + 8, by - 12), "10 m", font=self.f_s, fill=(20, 20, 20))
            y0 = pan.y0 + int(round(Y_DETAIL[1] * pan.s)) if len(self.srcs) == 1 else pan.y0 + int(round(14.0 * pan.s))
            d.text((pan.x0 + pan.w - 8, y0 - 24), "静かな水面（破線）", font=self.f_t, fill=C_TEXT, anchor="ra")
            for xm in range(500, int(X_DETAIL[1]) + 1, 50):
                xp = pan.x0 + int(round((xm - X_DETAIL[0]) * pan.s))
                d.text((xp, pan.y0 + pan.h + 10), "%d m" % xm, font=self.f_t, fill=C_TEXT, anchor="ma")
            sp = pan.px(np.array([[SEAT_MAIN, 0.0], [SEAT_OTHER, 0.0]]))
            lw = dict(font=self.f_s, fill=(255, 255, 255), anchor="ma", stroke_width=2, stroke_fill=(20, 20, 20))
            d.text((pan.x0 + sp[0, 0], pan.y0 + sp[0, 1] + 18), "船 556 m", **lw)
            d.text((pan.x0 + sp[1, 0], pan.y0 + sp[1, 1] + 18), "座席 574 m", **lw)
            if ghost:
                d.text((pan.x0 + sp[0, 0], pan.y0 + sp[0, 1] + 44), "船からのクリップはここまで（%.3f s）" % end556, **lw)
        # 字
        lines = []
        lines += wrap("1 " + self.cap["1"], 200)
        lines.append("2 " + self.cap["2"])
        cap3 = self.cap["3_coarse"] if s0.name == "coarse" else self.cap["3_fine"]
        lines.append("3 " + cap3)
        lines.append("4 巻き始め %.1f s・唇が前の面に付く %.1f s" % (s0.ev["onset_t"], s0.ev["first_contact_t"]) + "　　5 " + self.cap["5"])
        if s0.K is not None and f >= s0.K:
            lines.append("6 " + self.cap["6"])
        if t >= s0.ev["first_contact_t"] - 1e-9:
            lines += wrap("7 " + self.cap["7"], 96)
        k = s0.meta["frame_first"] + st["frame"]
        if st["interp"]:
            state = "いま：コマ %d と %d を補間（割合 %.3f）" % (k, k + 1, st["alpha"])
        elif st["last"]:
            state = "いま：最後のコマ %d" % k
        else:
            why = {"after_K": "K から先", "C4_fail": "取り置いたコマの確かめ（C4）で外れた組", "self_intersection": "自分と交わる組"}.get(s0.reason[st["frame"]], "")
            state = "いま：コマ %d を保つ（補間なし・%s）" % (k, why)
        lines.append(state + "　　船（556 m）：上下 %+.2f m・縦揺れ %+.2f°" % (hb, pb))
        if len(self.srcs) == 1 and s0.name == "coarse":
            lines.append("（粒子から作った細かい面〔Zhu & Bridson, 0.125 m〕の元は、R3 の計算し直し〔R3e〕の後に作り、この下に並べる。この動画の時点ではまだない）")
        y = self.text_y
        for ln in lines:
            d.text((40, y), ln, font=self.f_s, fill=C_TEXT)
            y += 27
        return np.asarray(pim)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sources")
    ap.add_argument("--stills", default="")
    ap.add_argument("--fps", type=float, default=60.0)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    srcs = [Src(n) for n in a.sources.split(",")]
    fr = Frame(srcs)
    vd = os.path.join(BUILD, "video")
    os.makedirs(vd, exist_ok=True)
    tag = "_".join(s.name for s in srcs)
    if a.stills:
        for t in [float(v) for v in a.stills.split(",")]:
            p = os.path.join(vd, "side_%s_t%.3f.png" % (tag, t))
            Image.fromarray(fr.render(t)).save(p)
            print("still", p)
        return
    s0 = srcs[0]
    t0, t1 = s0.man["time"]["t_first"], s0.man["time"]["t_last"]
    n = int(math.floor((t1 - t0) * a.fps + 1e-9)) + 1
    out = a.out or os.path.join(vd, "rt48_side_%s.mp4" % tag)
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", "%g" % a.fps,
           "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    T0 = time.time()
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    times = []
    for i in range(n):
        t = t0 + i / a.fps
        times.append(t)
        pr.stdin.write(fr.render(t).tobytes())
        if i % 120 == 0:
            print("frame", i, "/", n, round(time.time() - T0, 1), "s", flush=True)
    pr.stdin.close()
    rc = pr.wait()
    info = dict(file=out, sources=[s.name for s in srcs], fps=a.fps, frames=n, t_first=t0, t_last=times[-1], size=[W, H], ffmpeg_rc=rc,
                seconds=round(time.time() - T0, 1), rule="u_bakeio.state_at（Unity と同じ）", x_detail=X_DETAIL, y_detail=Y_DETAIL, x_all=X_ALL)
    json.dump(info, open(out + ".json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(json.dumps(info, ensure_ascii=False))


if __name__ == "__main__":
    main()
