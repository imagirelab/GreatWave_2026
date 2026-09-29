# -*- coding: utf-8 -*-
"""設計32：ID と群の図と動画（numpy の点の描画。Unity の描画ではない）。
  fig/fig_ds32_ids_tstar.png：原画（表示 1920×1080 へ写したもの）に、t* の根元（群の色）・根元→先端・群の番号・白の帯の群・飛沫の群を重ねる。
  fig/fig_ds32_ids_tracks.png：全コマの根元の軌跡（左＝原画視点、右＝横（進む向き×高さ）、色＝時刻）。
  fig/ds32_ids_30fps.mp4：左＝原画視点、右＝横から。灰＝主役波のシート（間引いた頂点）、白＝白くなった頂点、色の線＝爪（根元→先端、群の色）、
      色の点＝飛沫（群の色）。1920×540、30 fps、421 コマ（t 0〜14 s、t ≥ 12 s は t* の保持）。
"""
import json
import os
import subprocess
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds30")
import ds30_checks as K  # noqa: E402

OUT = REPO + "/Unity/Build/Design/32/list+ids"
FIG = OUT + "/fig"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
PAINT = REPO + "/Docs/References/Met_JP1847_DP130155.jpg"
TRUTH = REPO + "/Tools/PaintingTruth/painting_truth.json"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds32")
from ds32_claw_figs import put, label  # noqa: E402


def palette(n, seed=7):
    rng = np.random.RandomState(seed)
    hsv = np.stack([np.linspace(0, 179, n, endpoint=False), np.full(n, 200), np.full(n, 255)], 1).astype(np.uint8)
    hsv = hsv[rng.permutation(n)]
    return [tuple(int(v) for v in c) for c in cv2.cvtColor(hsv[None], cv2.COLOR_HSV2BGR)[0]]


def main():
    os.makedirs(FIG, exist_ok=True)
    ids = json.load(open(OUT + "/ds32_ids.json", encoding="utf-8"))
    chk = json.load(open(OUT + "/ds32_id_checks.json", encoding="utf-8"))
    NFR = ids["clock"]["frames"]
    bound = [c for c in ids["claws"] if c.get("bound")]
    nb = len(bound)
    H = np.fromfile(OUT + "/" + ids["claw_hist"]["file"], "<f4").reshape(NFR, nb, 8)
    groups = ids["groups"]
    G = np.fromfile(OUT + "/" + ids["group_hist"]["file"], "<f4").reshape(NFR, len(groups), 4)
    spec = json.load(open(TRUTH, encoding="utf-8"))
    cam = K.C27.Cam(spec)
    cg = [g for g in groups if g["kind"] == "claw"]
    col_c = palette(len(cg), 3)
    gcol = {}
    for k, g in enumerate(cg):
        for m in g["members"]:
            gcol[m] = col_c[k]
    sg = [g for g in groups if g["kind"] == "spray"]
    col_s = palette(len(sg), 11)
    stab = json.load(open(REPO + "/Unity/Build/Design/31/spray/ds31_spray_table.json", encoding="utf-8"))["particles"]
    sfr = json.load(open(REPO + "/Unity/Build/Design/31/spray/ds31_spray_frames.json", encoding="utf-8"))
    S = np.fromfile(REPO + "/Unity/Build/Design/31/spray/" + sfr["file"], "<f4").reshape(sfr["frames"], sfr["count"], 4)
    scol = [None] * len(stab)
    pos_of = {p["dot_id"]: i for i, p in enumerate(stab)}
    for k, g in enumerate(sg):
        for m in g["members"]:
            scol[pos_of[m]] = col_s[k]

    # ---- 1. t* の重ね図
    img = cv2.imdecode(np.fromfile(PAINT, np.uint8), cv2.IMREAD_COLOR)
    a = 0.416345
    A = np.array([[a, 0, a * 0.5 - 0.5 + 156.66153], [0, a, a * 0.5 - 0.5]], np.float32)
    disp = cv2.warpAffine(img, A, (1920, 1080), flags=cv2.INTER_AREA, borderValue=(245, 245, 245))
    disp = (0.55 * disp + 0.45 * 255).astype(np.uint8)
    f = NFR - 1
    rp, _ = cam.project(H[f, :, 0:3].astype(np.float64))
    tp, _ = cam.project(H[f, :, 3:6].astype(np.float64))
    # 白の帯の群：t* の頂点（間引き）
    hero = K.Pkg(REPO + "/" + ids["sheet"]["package"])
    X0 = hero.world(0.0)
    mem = open(OUT + "/ds32_band_members_i32.bin", "rb").read()
    arr = np.frombuffer(mem, np.int32)
    bands, k = [], 0
    while k < len(arr):
        n = int(arr[k]); bands.append(arr[k + 1:k + 1 + n]); k += 1 + n
    col_b = palette(len(bands), 5)
    Xf = X0.reshape(-1, 3)
    for b_, cb in zip(bands, col_b):
        q, _ = cam.project(Xf[b_[::3]])
        for x, y in q:
            if 0 <= x < 1920 and 0 <= y < 1080:
                disp[int(y), int(x)] = (0.5 * np.array(disp[int(y), int(x)]) + 0.5 * np.array(cb)).astype(np.uint8)
    for i, c in enumerate(bound):
        cc = gcol.get(c["id"], (0, 0, 0))
        cv2.line(disp, tuple(np.round(rp[i]).astype(int)), tuple(np.round(tp[i]).astype(int)), cc, 2, cv2.LINE_AA)
        cv2.circle(disp, tuple(np.round(rp[i]).astype(int)), 3, cc, -1, cv2.LINE_AA)
    for i in range(len(stab)):
        q, _ = cam.project(S[-1, i, :3].astype(np.float64))
        cv2.circle(disp, tuple(np.round(q).astype(int)), 3, scol[i], -1, cv2.LINE_AA)
    for k2, g in enumerate(groups):
        if g["kind"] == "white_band":
            continue
        c3 = G[f, k2, 0:3].astype(np.float64)
        if G[f, k2, 3] <= 0:
            continue
        q, _ = cam.project(c3)
        disp = label(disp, q + [4, -14], g["id"], 13, (255, 255, 255))
    ncg = len(cg); nbg = sum(1 for g in groups if g["kind"] == "white_band"); nsg = len(sg)
    disp = put(disp, ["t*（コマ %d）の ID：爪 %d 本（群 %d、色＝群、線＝根元→先端）、白の帯の群 %d（頂点の色）、飛沫 %d 粒（群 %d）。原画視点 PaintingCam v1。numpy の点の描画"
                      % (f, nb, ncg, nbg, len(stab), nsg),
                      "瞬間移動 %d・意図しない点滅 %d・群から粒が抜けるコマ %d。t* の再投影：根元 最大 %.2f px、先端 最大 %.2f px"
                      % (chk["teleport_count"], chk["flicker_count"], chk["group_member_lost_count"],
                         chk["reprojection_tstar_display_px"]["root_max"], chk["reprojection_tstar_display_px"]["tip_max"])], 18)
    cv2.imwrite(FIG + "/fig_ds32_ids_tstar.png", disp)

    # ---- 2. 軌跡
    kmeta = json.load(open(REPO + "/Unity/Build/Design/28R01F/kstar_final/kstarR4_a45_meta.json", encoding="utf-8"))
    tdir = np.array(kmeta["frame"]["t_travel"])
    O0 = np.array(kmeta["frame"]["section_origin_world"])
    allroot = H[:, :, 0:3].astype(np.float64)
    warp0 = json.load(open(REPO + "/" + ids["clock"]["timewarp"], encoding="utf-8"))
    taus0 = np.interp(np.arange(NFR) / 30.0, warp0["t"], warp0["tau"])
    Ofr = np.stack([hero.origin(float(t_)) for t_ in taus0])   # 波の枠の原点 O(τ)
    loc = allroot - Ofr[:, None, :]
    vis_all = H[:, :, 7] > 0.5
    a_ = loc @ tdir
    y_ = loc[..., 1]
    W2, H2 = 960, 1080
    left = np.full((1080, 960, 3), 250, np.uint8)
    right = np.full((1080, 960, 3), 250, np.uint8)
    amin, amax = a_[vis_all].min() - 4, a_[vis_all].max() + 4
    ymin, ymax = min(-2, y_[vis_all].min() - 2), y_[vis_all].max() + 2
    sc = min((W2 - 80) / (amax - amin), (H2 - 160) / (ymax - ymin))

    def side(pa, py):
        return np.stack([40 + (pa - amin) * sc, H2 - 60 - (py - ymin) * sc], -1)
    pp, _ = cam.project(allroot.reshape(-1, 3))
    pp = pp.reshape(NFR, nb, 2)
    ppv = pp[vis_all]
    sx0, sy0 = np.floor(np.percentile(ppv, 0.5, axis=0) - 40).astype(int)
    sx1, sy1 = np.ceil(np.percentile(ppv, 99.5, axis=0) + 40).astype(int)
    s2 = min(960 / (sx1 - sx0), 1080 / (sy1 - sy0))
    tc = cv2.applyColorMap(np.linspace(0, 255, NFR).astype(np.uint8)[:, None], cv2.COLORMAP_TURBO)[:, 0]
    for i in range(nb):
        vis = H[:, i, 7] > 0.5
        idx = np.nonzero(vis)[0]
        for f0, f1 in zip(idx[:-1], idx[1:]):
            c = tuple(int(v) for v in tc[f1])
            p0 = side(a_[f0, i], y_[f0, i]); p1 = side(a_[f1, i], y_[f1, i])
            cv2.line(right, tuple(np.round(p0).astype(int)), tuple(np.round(p1).astype(int)), c, 1, cv2.LINE_AA)
            q0 = (pp[f0, i] - [sx0, sy0]) * s2; q1 = (pp[f1, i] - [sx0, sy0]) * s2
            cv2.line(left, tuple(np.round(q0).astype(int)), tuple(np.round(q1).astype(int)), c, 1, cv2.LINE_AA)
    tr = np.concatenate([left, right], 1)
    tr = put(tr, ["爪の根元の軌跡（見えるコマだけ、色＝時刻：青 t 0 s → 赤 t 14 s）。左＝原画視点（表示 x %d〜%d、y %d〜%d）、右＝横（波の枠の中：進む向き × 高さ、m。波の枠の平行移動 O(τ) を除く）"
                  % (sx0, sx1, sy0, sy1), "どの ID も 30 Hz のコマの間で跳ばない（最大の動き：根元 %.3f m・先端 %.3f m／コマ、シートの頂点の最大 %.3f m）"
                  % (chk["max_moves_m"]["claw_root_max_move_m"], chk["max_moves_m"]["claw_tip_max_move_m"], chk["sheet_max_vertex_move_m"])], 18)
    cv2.imwrite(FIG + "/fig_ds32_ids_tracks.png", tr)

    # ---- 3. 動画
    tw = np.fromfile(REPO + "/" + ids["sheet"]["package"] + "/ds31_twhite_r32f.bin", "<f4").reshape(hero.R, hero.C)
    warp = json.load(open(REPO + "/" + ids["clock"]["timewarp"], encoding="utf-8"))
    taus = np.interp(np.arange(NFR) / 30.0, warp["t"], warp["tau"])
    rr = np.arange(0, hero.R, 3); cc_ = np.arange(18, 395, 3)
    sub_tw = tw[np.ix_(rr, cc_)].ravel()
    # 横の図の範囲はシートを含める
    Xs = hero.world(0.0)[np.ix_(rr, cc_)].reshape(-1, 3)
    wv = FIG + "/_frames"
    os.makedirs(wv, exist_ok=True)
    for f in range(NFR):
        X = hero.world(float(taus[f]))[np.ix_(rr, cc_)].reshape(-1, 3)
        pv = np.full((540, 960, 3), (238, 228, 214), np.uint8)
        sv = np.full((540, 960, 3), (238, 228, 214), np.uint8)
        q, z = cam.project(X)
        q = q * 0.5
        wht = taus[f] >= sub_tw
        for mask, colr in ((~wht, (150, 110, 70)), (wht, (255, 255, 255))):
            qq = np.round(q[mask]).astype(int)
            ok = (qq[:, 0] >= 0) & (qq[:, 0] < 960) & (qq[:, 1] >= 0) & (qq[:, 1] < 540) & (z[mask] > 0)
            pv[qq[ok, 1], qq[ok, 0]] = colr
        Of = hero.origin(float(taus[f]))
        sa = (X - Of) @ tdir
        s_ = np.stack([40 + (sa - amin) * sc * 0.5, 540 - 30 - (X[:, 1] - Of[1] - ymin) * sc * 0.5], -1)
        for mask, colr in ((~wht, (150, 110, 70)), (wht, (255, 255, 255))):
            qq = np.round(s_[mask]).astype(int)
            ok = (qq[:, 0] >= 0) & (qq[:, 0] < 960) & (qq[:, 1] >= 0) & (qq[:, 1] < 540)
            sv[qq[ok, 1], qq[ok, 0]] = colr
        rt = H[f, :, 0:3].astype(np.float64); tt = H[f, :, 3:6].astype(np.float64)
        prt, _ = cam.project(rt); ptt, _ = cam.project(tt)
        srt = np.stack([40 + ((rt - Of) @ tdir - amin) * sc * 0.5, 540 - 30 - (rt[:, 1] - Of[1] - ymin) * sc * 0.5], -1)
        stt = np.stack([40 + ((tt - Of) @ tdir - amin) * sc * 0.5, 540 - 30 - (tt[:, 1] - Of[1] - ymin) * sc * 0.5], -1)
        for i, c in enumerate(bound):
            if H[f, i, 7] < 0.5:
                continue
            colr = gcol.get(c["id"], (0, 0, 0))
            cv2.line(pv, tuple(np.round(prt[i] * 0.5).astype(int)), tuple(np.round(ptt[i] * 0.5).astype(int)), colr, 2, cv2.LINE_AA)
            cv2.line(sv, tuple(np.round(srt[i]).astype(int)), tuple(np.round(stt[i]).astype(int)), colr, 2, cv2.LINE_AA)
        for i in range(len(stab)):
            if S[f, i, 3] <= 0:
                continue
            p3 = S[f, i, :3].astype(np.float64)
            qq, _ = cam.project(p3)
            cv2.circle(pv, tuple(np.round(qq * 0.5).astype(int)), 2, scol[i], -1, cv2.LINE_AA)
            ss = np.array([40 + ((p3 - Of) @ tdir - amin) * sc * 0.5, 540 - 30 - (p3[1] - Of[1] - ymin) * sc * 0.5])
            cv2.circle(sv, tuple(np.round(ss).astype(int)), 2, scol[i], -1, cv2.LINE_AA)
        fr = np.concatenate([pv, sv], 1)
        cv2.putText(fr, "t %.2f s  tau %.3f s  frame %d   left: PaintingCam v1   right: side in wave frame (travel x height)   numpy points, not Unity" % (f / 30.0, taus[f], f),
                    (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        cv2.imwrite(wv + "/f%04d.png" % f, fr)
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", "30", "-i", wv + "/f%04d.png", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "20", FIG + "/ds32_ids_30fps.mp4"], check=True)
    for fn in os.listdir(wv):
        os.remove(os.path.join(wv, fn))
    os.rmdir(wv)
    print("figs done")


if __name__ == "__main__":
    main()
