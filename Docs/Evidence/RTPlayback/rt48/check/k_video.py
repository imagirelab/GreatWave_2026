# -*- coding: utf-8 -*-
"""6. 動画から絵を取り出し（ffmpeg で mp4 を毎コマ読む）、同じ計算の時刻の R3 の断面（自分で取った線）と比べる。
(side) 横からの動画：大きい窓（x 470〜620 m）の水の塗りを、自分の R3 の線から同じ画素に塗った水と比べる。縮尺は絵の中の
       目盛り（10 m おきの刻み）・静かな水面の破線・10 m の物差しから自分で読む。頂の高さ・巻き始め・囲んだ空気・唇も。
(boat) 船からの動画：空と水の境（波の輪郭）の行を測り、自分の R3 の線と、自分で出した船の上下・縦揺れから、カメラ
       （目は船の根から 1.2 m、縦の画角 60°、1920×1080、船首の向き −X）で予想した行と比べる。
出力：out/k_video_side.json、out/k_video_boat556.json、out/k_video_boat574.json と、比べの絵 out/side_*.png"""
import sys, subprocess, time
import numpy as np
from PIL import Image
from scipy import ndimage
from k_lib import *

W, H = 1920, 1080
V = RT + "/video"
my = MyFrames()
kr = jload(OUT + "/k_r3.json")
rows = kr["rows"]
pairs, man = load_pairs()
INTERP = np.array([p["interp"] for p in man["pairs"]])


def read_frames(path):
    p = subprocess.Popen([FFMPEG, "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, bufsize=W * H * 3 * 4)
    n = 0
    while True:
        b = p.stdout.read(W * H * 3)
        if len(b) < W * H * 3:
            break
        yield n, np.frombuffer(b, np.uint8).reshape(H, W, 3)
        n += 1
    p.wait()


def state(t):
    """再生の決まり（manifest の playback.rule の文から自分で書いた）：組 k、割合、補間するか"""
    u = (t - T0) * FPS
    k = int(np.floor(u + 1e-9))
    if k >= 570:
        return 570, 0.0, False
    w = min(1.0, max(0.0, u - k))
    return k, w, bool(INTERP[k])


def displayed_curves(t):
    """見せている形：補間しない時は自分の R3 の線（コマ k）と閉じた線。補間する時は焼いた A・B の混ぜ（自分の線ではない）"""
    k, w, ip = state(t)
    f = F0 + k
    if ip:
        A = pairs[k, 0].astype(np.float64); B = pairs[k, 1].astype(np.float64)
        C = A + (B - A) * w; C[:, 0] += X0B
        return C, my.loops_of(f), f, True
    return my.main_of(f), my.loops_of(f), f, False


# ================================================================== 横から
def side():
    t0 = time.time()
    path = V + "/rt48_side_coarse.mp4"
    first = None
    out_rows = []
    for n, a in read_frames(path):
        a = a.astype(np.int32)
        if first is None:
            first = a.copy()
            # 枠：右下の刻み（枠の下の線の下、10 m おき）
            S = a.sum(2)
            box_bottom = int(max(r for r in range(560, 700) if (S[r, 100:1800] < 500).mean() > 0.95))
            tick_row = box_bottom + 3
            tick_cols = np.where(S[tick_row, :] < 500)[0]
            groups = np.split(tick_cols, np.where(np.diff(tick_cols) > 2)[0] + 1)
            tc = np.array([g.mean() for g in groups if len(g)])
            xt = 470.0 + 10.0 * np.arange(len(tc))
            bx = np.polyfit(xt, tc + 0.5, 1)            # 画素の中心の座標（左端が 0）
            box_top = int(min(r for r in range(150, 260) if (S[r, 100:1800] < 500).mean() > 0.95))
            box_left = int(min(c for c in range(0, 200) if (S[box_top + 5:box_top + 60, c] < 500).mean() > 0.95))
            box_right = int(max(c for c in range(1700, 1920) if (S[box_top + 5:box_top + 60, c] < 500).mean() > 0.95))
            # 物差し（黒、縦）
            blk = (a.max(2) < 45) & (np.abs(a[..., 0] - a[..., 1]) < 12)
            colsb = [c for c in range(box_left + 5, box_left + 120) if blk[box_top:box_bottom, c].sum() > 80]
            cb = colsb[0]
            rb = np.where(blk[box_top:box_bottom, cb])[0] + box_top
            bar_len = rb.max() - rb.min() + 1
            rowsb = [r for r in range(box_top, box_bottom) if blk[r, cb:cb + 200].sum() > 80]
            hb = np.where(blk[rowsb[-1], cb:cb + 300])[0]
            hbar_len = hb.max() - hb.min() + 1
            cal = dict(box=(box_left, box_top, box_right, box_bottom), ticks=len(tc), tick_fit_px_per_m=bx[0], tick_x470_px=bx[1] + bx[0] * 470,
                       vbar_px=int(bar_len), hbar_px=int(hbar_len), vbar_rows=(int(rb.min()), int(rb.max())))
            print("cal", cal)
        S = a.sum(2)
        # 静かな水面の破線（白い点線）の行：毎コマ、右の 1/3 で白い画素が最も多い行
        if n == 0:
            white = (a.min(2) > 235)
            cand = range(box_top + 100, box_bottom - 50)
            cnt = np.array([white[r, box_left:box_right].sum() for r in cand])
            r0 = list(cand)[int(np.argmax(cnt))]
            ww = cnt[int(np.argmax(cnt)) - 1:int(np.argmax(cnt)) + 2].astype(float)
            row_y0 = r0 + 0.5 + (np.arange(-1, 2) * ww).sum() / ww.sum()
            sy = (box_bottom - box_top - 1) / 34.0       # 枠の内側（縦 34 m）。物差しの線の太さ分を除くと同じ（下の cal に両方）
            sx = bx[0]
            cal.update(row_y0=row_y0, px_per_m_y=sy, px_per_m_x=sx, vbar_px_per_m=bar_len / 10.0)
            # 内側の枠からの写し（確かめ）
            cal["box_px_per_m_x"] = (box_right - box_left - 1) / 150.0
            cal["box_px_per_m_y"] = (box_bottom - box_top - 1) / 34.0
            cal["box_row_y0"] = box_top + 1 + 20.0 * cal["box_px_per_m_y"]
            print("cal2", {k: cal[k] for k in ("row_y0", "px_per_m_y", "px_per_m_x", "box_px_per_m_x", "box_px_per_m_y", "box_row_y0")})
        t = T0 + n / 60.0
        k, w, ip = state(t)
        C, loops, f, used_bake = displayed_curves(t)
        # 絵の窓の中の画素
        c0, c1 = box_left + 1, box_right
        r0_, r1_ = box_top + 1, box_bottom - 1
        sub = a[r0_:r1_, c0:c1].astype(float)
        sky = np.array([212.0, 224.0, 230.0]); wat = np.array([28.0, 77.0, 95.0])
        dv = wat - sky
        tt = ((sub - sky) @ dv) / (dv @ dv)
        resid = np.linalg.norm(sub - sky - tt[..., None] * dv, axis=2)
        isw = (tt > 0.5) & (resid < 45)
        # 重ねた字・物差し・船・印：白い画素か、水と空のどちらの色からも遠い画素を 2 画素ふくらませて、比べから外す
        ovl = ndimage.binary_dilation((sub.min(2) > 225) | (resid >= 60), iterations=2)
        other = (resid >= 45) | ovl
        rd = int(np.floor(row_y0)) - r0_
        other[max(0, rd - 2):rd + 2, :] = True          # 静かな水面の破線の行（破線は水の上にも描いてある）
        if n == 0:
            # 字（灰色の「静かな水面（破線）」など）：最初のコマ（離れた水がない）で、水の大きな塊につながらない水の色の画素の箱
            lab0, nl0 = ndimage.label(isw & ~other)
            big = np.argmax(np.bincount(lab0.ravel())[1:]) + 1
            static_excl = np.zeros(isw.shape, bool)
            for sl in ndimage.find_objects(lab0):
                pass
            for li in range(1, nl0 + 1):
                if li == big:
                    continue
                ys_, xs_ = np.where(lab0 == li)
                static_excl[max(0, ys_.min() - 4):ys_.max() + 5, max(0, xs_.min() - 4):xs_.max() + 5] = True
            cal["static_excl_px"] = int(static_excl.sum())
        other |= static_excl
        # 自分の R3 の線を同じ画素に塗る（偶奇の決まり。主な線は下を閉じた多角形、閉じた線は全部）
        xc = (np.arange(c0, c1) + 0.5 - bx[1]) / sx                  # 各列の中心の x（目盛りから）
        yc = (row_y0 - (np.arange(r0_, r1_) + 0.5)) / sy               # 各行の中心の Y（破線と物差しから）
        polys = [np.vstack([C, [C[-1, 0], -60.0], [C[0, 0], -60.0], C[:1]])] + [np.vstack([L["pts"], L["pts"][:1]]) for L in loops]
        mask = np.zeros(isw.shape, bool)
        for Pp in polys:
            x0, x1 = Pp[:-1, 0], Pp[1:, 0]
            y0, y1 = Pp[:-1, 1], Pp[1:, 1]
            for j, xq in enumerate(xc):
                kk = np.where(((x0 <= xq) & (x1 > xq)) | ((x1 <= xq) & (x0 > xq)))[0]
                if len(kk) == 0:
                    continue
                yy = y0[kk] + (xq - x0[kk]) * (y1[kk] - y0[kk]) / (x1[kk] - x0[kk])
                cnt = (yy[None, :] > yc[:, None]).sum(1)
                mask[:, j] ^= (cnt % 2 == 1)
        mis = (isw != mask) & ~other
        # 境から離れた食い違い（画素）：R3 の線（画素の座標）からの距離
        crest_x = rows[f - F0]["crest_x"]
        if mis.any():
            rr, cc = np.where(mis)
            pts_px = np.column_stack([cc + c0 + 0.5, rr + r0_ + 0.5])
            curves_px = [np.column_stack([bx[1] + sx * P[:, 0], row_y0 - sy * P[:, 1]]) for P in [C] + [np.vstack([L["pts"], L["pts"][:1]]) for L in loops]]
            dpx, _ = SegTree(curves_px).dist(pts_px)
            far = dpx > 1.5
            n_far = int(far.sum()); dmax = float(dpx.max())
            far_x = (float(((pts_px[far, 0] - bx[1]) / sx).min()), float(((pts_px[far, 0] - bx[1]) / sx).max())) if n_far else None
        else:
            n_far, dmax, far_x = 0, 0.0, None
        # 頂の高さ：絵の一番上の水（列ごと）の最大、窓は自分の頂 ±30 m
        topr = np.where(isw.any(0), isw.argmax(0), -1)
        yv = np.where(topr >= 0, (row_y0 - (topr + r0_ + 0.5 - 0.5)) / sy, np.nan)     # 一番上の水の画素の上の縁
        win = (xc >= crest_x - 30) & (xc <= crest_x + 30)
        inside = (crest_x - 10 >= xc[0]) and (crest_x + 10 <= xc[-1])
        w10 = (xc >= crest_x - 10) & (xc <= crest_x + 10)
        ytop_img = float(np.nanmax(yv[w10])) if inside else float("nan")
        # 自分の線の頂（見せている線の頂 ±10 m の最高）
        wm = (C[:, 0] >= crest_x - 10) & (C[:, 0] <= crest_x + 10)
        ytop_r3 = float(C[wm, 1].max()) if inside else float("nan")
        # かぶさり（列の中で 水→水でない→水）と、囲んだ空気（水でない画素の塊で、窓の上の縁に触れない物）
        winc = np.where(win)[0]
        over_cols = 0
        for j in winc:
            col = isw[:, j]
            if col.any():
                i0 = col.argmax(); i1 = len(col) - 1 - col[::-1].argmax()
                if (~col[i0:i1 + 1] & ~other[i0:i1 + 1, j]).any():
                    over_cols += 1
        lab, nl = ndimage.label(~isw & ~other)
        holes = 0; hole_area = 0.0
        for li in range(1, nl + 1):
            ys_, xs_ = np.where(lab == li)
            if ys_.min() == 0 or xs_.min() == 0 or xs_.max() == isw.shape[1] - 1:
                continue
            xm = xc[xs_].mean()
            if abs(xm - crest_x) <= 30 and len(ys_) / (sx * sy) >= 0.25:
                holes += 1; hole_area = max(hole_area, len(ys_) / (sx * sy))
        r = dict(n=n, t=t, frame=f, interp=ip, mis=int(mis.sum()), n_far=n_far, dmax_px=dmax, far_x=far_x,
                 ytop_img=ytop_img, ytop_r3=ytop_r3, over_cols=over_cols, holes=holes, hole_area=hole_area)
        # 時刻のずれ：6 コマおきに、前後のコマの線でも同じ食い違いを数える
        if n % 6 == 0 and not ip and 1 <= k <= 568:
            alt = {}
            for dk in (-1, 0, 1):
                Pm = my.main_of(f + dk)
                pol = [np.vstack([Pm, [Pm[-1, 0], -60.0], [Pm[0, 0], -60.0], Pm[:1]])] + [np.vstack([L["pts"], L["pts"][:1]]) for L in my.loops_of(f + dk)]
                mk = np.zeros(isw.shape, bool)
                for Pp in pol:
                    x0, x1 = Pp[:-1, 0], Pp[1:, 0]; y0, y1 = Pp[:-1, 1], Pp[1:, 1]
                    for j in range(len(xc)):
                        xq = xc[j]
                        kk = np.where(((x0 <= xq) & (x1 > xq)) | ((x1 <= xq) & (x0 > xq)))[0]
                        if len(kk) == 0:
                            continue
                        yy = y0[kk] + (xq - x0[kk]) * (y1[kk] - y0[kk]) / (x1[kk] - x0[kk])
                        mk[:, j] ^= ((yy[None, :] > yc[:, None]).sum(1) % 2 == 1)
                alt[dk] = int(((isw != mk) & ~other).sum())
            r["best_dk"] = min(alt, key=lambda d: (alt[d], abs(d))); r["alt"] = alt
        out_rows.append(r)
        if n in (0, 988, 1062, 1065, 1150, 1425):
            img = np.zeros(isw.shape + (3,), np.uint8) + 255
            img[isw & mask] = (60, 110, 140); img[isw & ~mask & ~other] = (230, 30, 30); img[~isw & mask & ~other] = (30, 160, 30)
            Image.fromarray(img).save(OUT + f"/side_cmp_n{n:04d}.png")
        if n % 120 == 0:
            print(n, round(t, 3), f, ip, r["mis"], r["n_far"], round(r["dmax_px"], 2), round(ytop_img, 3), round(ytop_r3, 3), over_cols, holes, f"{time.time()-t0:.0f}s")
    R = out_rows
    held = [r for r in R if not r["interp"]]
    summ = dict(cal=cal, n_frames=len(R), n_interp=sum(r["interp"] for r in R),
                held_max_far=max(r["n_far"] for r in held), held_frames_with_far=sum(1 for r in held if r["n_far"] > 0),
                held_max_dpx=max(r["dmax_px"] for r in held),
                interp_max_far=max([r["n_far"] for r in R if r["interp"]] or [0]),
                crest_dy_max=max(abs(r["ytop_img"] - r["ytop_r3"]) for r in R if np.isfinite(r["ytop_img"])),
                crest_dy_held_max=max(abs(r["ytop_img"] - r["ytop_r3"]) for r in held if np.isfinite(r["ytop_img"])),
                crest_dy_held_median=float(np.median([r["ytop_img"] - r["ytop_r3"] for r in held if np.isfinite(r["ytop_img"])])),
                crest_n=sum(1 for r in R if np.isfinite(r["ytop_img"])),
                crest_first_t=next((r["t"] for r in R if np.isfinite(r["ytop_img"])), None),
                first_overhang=next((dict(n=r["n"], t=r["t"], frame=r["frame"], cols=r["over_cols"]) for r in R if r["over_cols"] >= 1), None),
                first_hole=next((dict(n=r["n"], t=r["t"], frame=r["frame"], area=r["hole_area"]) for r in R if r["holes"] >= 1), None),
                timing_best_dk=dict((str(dk), sum(1 for r in R if r.get("best_dk") == dk)) for dk in (-1, 0, 1)),
                at=dict((str(n), R[n]) for n in (0, 720, 988, 1062, 1065, 1130, 1425) if n < len(R)))
    jsave(OUT + "/k_video_side.json", dict(summary=summ, rows=R))
    print("side", {k: v for k, v in summ.items() if k != "at"})


# ================================================================== 船から
def boat(seat, path, tag):
    t0 = time.time()
    f_px = (H / 2) / np.tan(np.radians(30.0))
    hm = np.array([r["heave" + seat] for r in rows]); pm = np.array([r["pitch" + seat] for r in rows])
    S = float(seat)
    out = []
    for n, a in read_frames(path):
        t = T0 + n / 60.0
        L = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]).astype(float)
        # 空と水の境：右の 400 列（1500〜1899）で、上から、すぐ上の空より 25 以上暗くなる最初の行（50 % の所を行の中で補う）
        vals = []
        for c in range(1500, 1900, 8):
            col = L[60:900, c]
            sky = np.maximum.accumulate(col)
            j = np.where(col < sky - 25)[0]
            if len(j) == 0:
                continue
            j = j[0]
            ref_s = col[max(0, j - 3)]; ref_w = col[min(len(col) - 1, j + 3)]
            half = 0.5 * (ref_s + ref_w)
            jj = j
            while jj > 0 and col[jj - 1] < half:
                jj -= 1
            if col[jj - 1] != col[jj]:
                fr = (col[jj - 1] - half) / (col[jj - 1] - col[jj])
            else:
                fr = 0.5
            vals.append(60 + jj - 1 + fr + 0.5)              # 連続の座標（上の縁が 0）
        v_meas = float(np.median(vals)) if vals else float("nan")
        # 予想
        k, w, ip = state(t)
        C, loops, f, used_bake = displayed_curves(t)
        if k >= 570:
            h, p = hm[-1], pm[-1]
        elif ip:
            h, p, _ = boat_pose(C, S)
        else:
            h = hm[k] + (hm[k + 1] - hm[k]) * w; p = pm[k] + (pm[k + 1] - pm[k]) * w
        th = np.radians(p)
        camX = S - 1.2 * np.sin(th); camY = h + 1.2 * np.cos(th)
        Pts = [C] + [L_["pts"] for L_ in loops if L_["phase"] == -1]
        Pa = np.vstack(Pts)
        Yd = Pa[:, 1] * taper_w(Pa[:, 0])
        ahead = Pa[:, 0] < camX - 0.5
        el = np.arctan2(Yd[ahead] - camY, camX - Pa[ahead, 0])
        el_raw = np.arctan2(Pa[ahead, 1] - camY, camX - Pa[ahead, 0])
        emax = max(el.max(), np.arctan2(-camY, 25000.0))
        emax_raw = max(el_raw.max(), np.arctan2(-camY, 25000.0))
        x_at = float(Pa[ahead][int(np.argmax(el)), 0])
        cam_el = -th
        v_pred = H / 2 - f_px * np.tan(emax - cam_el)
        v_pred_raw = H / 2 - f_px * np.tan(emax_raw - cam_el)
        out.append(dict(n=n, t=t, frame=f, interp=ip, heave=h, pitch=p, v_meas=v_meas, v_pred=float(v_pred), dv=float(v_meas - v_pred),
                        dv_deg=float(np.degrees(np.arctan((H / 2 - v_meas) / f_px) - np.arctan((H / 2 - v_pred) / f_px))),
                        v_pred_untapered=float(v_pred_raw), x_silhouette=x_at, n_cols=len(vals)))
        if n % 120 == 0:
            print(tag, n, round(t, 3), f, ip, round(v_meas, 2), round(v_pred, 2), round(v_meas - v_pred, 2), round(x_at, 1), f"{time.time()-t0:.0f}s")
    dv = np.array([o["dv"] for o in out]); held = np.array([not o["interp"] for o in out])
    tap = np.array([abs(o["v_pred_untapered"] - o["v_pred"]) for o in out])
    summ = dict(n_frames=len(out), f_px=f_px, max_abs_dv=float(np.nanmax(np.abs(dv))), p95_abs_dv=float(np.nanpercentile(np.abs(dv), 95)),
                median_dv=float(np.nanmedian(dv)), max_abs_dv_held=float(np.nanmax(np.abs(dv[held]))),
                max_abs_dv_deg=float(np.nanmax(np.abs([o["dv_deg"] for o in out]))),
                worst=out[int(np.nanargmax(np.abs(dv)))],
                taper_effect_px_max=float(tap.max()), frames_taper_effect_over_0_5px=int((tap > 0.5).sum()),
                taper_effect_first_last=(next((o["t"] for o in out if abs(o["v_pred_untapered"] - o["v_pred"]) > 0.5), None),
                                         next((o["t"] for o in reversed(out) if abs(o["v_pred_untapered"] - o["v_pred"]) > 0.5), None)),
                silhouette_from_taper_zone=sum(1 for o in out if o["x_silhouette"] < 200.0))
    # 縦揺れを 0.5° 変えた時の行の動き（この比べの感度）
    summ["px_per_deg"] = float(f_px * np.pi / 180)
    jsave(OUT + f"/k_video_{tag}.json", dict(summary=summ, rows=out))
    print(tag, summ)


if __name__ == "__main__":
    what = sys.argv[1:] or ["side", "boat556", "boat574"]
    if "side" in what:
        side()
    if "boat556" in what:
        boat("556", V + "/rt48_boat_seat556_bow_coarse.mp4", "boat556")
    if "boat574" in what:
        boat("574", V + "/rt48_boat_seat574_bow_coarse_extra.mp4", "boat574")
