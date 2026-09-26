# -*- coding: utf-8 -*-
"""番号31「白の出現と縞の追従」：白の時間場 T_white を作り、UV（テクセル）空間で検査する。

T_white は主役波の固定位相の格子（K*、240 行 × 400 列）の頂点ごとの値（秒）。行（波峰線に垂直な断面）の中で、
K* の弧長を区間ごとに正規化した『白の波面の座標』ρ（頂 0 → 唇先 1 → 角 2 → 内壁の下 3 → 前の足 4、背面は頂 0 → 背面の足 −1）
に、波峰線方向の滑らかな揺らぎを加えた ρ′ を、時刻の表 ρ_front(t)（端の傾き 0 の単調な 3 次補間）の逆関数で時刻にする。
Unity の AF31 NPR White は頂点シェーダーで T_white を読み、三角形の中は線形に補間する。終態（t*）の色区が白のテクセルだけを、
t < T_white のあいだ『白の前の色』（既定は藍中）で塗る。白でないテクセルは時刻によらず終態の色なので、一時的な白の塗りつぶしは作りから 0。
縞（藍中・藍濃の色区）は UV（番号28修正01 の焼き込み）に貼り付いているので、同じ水面とともに動く。

使い方（リポジトリの根で）:
    py -3.10 Tools/GWWaveGen/af31_white.py [--params P] [--out DIR] [--stage all|field|uv]
出力（既定 Unity/Build/ArtFirst/31、Git 対象外）:
    white/af31_twhite_r32f.bin・af31_twhite.json（Unity の AF31WhiteField が読む）
    white/af31_uvcheck.json（UV 空間の検査）、white/af31_uv_twhite.png（UV の T_white の図）、white/af31_texel_cache.npz（評価用）
numpy と OpenCV だけを使う。
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth"))
sys.path.insert(0, HERE)
import truthlib as T  # noqa: E402
from af30_formation import KStar, clamped_pchip, cr_weights  # noqa: E402  番号30 の関数（読むだけ。変更しない）

DEFAULT_PARAMS = os.path.join(HERE, "af31_white.json")
DEFAULT_OUT = os.path.join(REPO, "Unity", "Build", "ArtFirst", "31")
S = 4096
CLASS_NAMES = ["white", "mizuiro", "ai_mid", "ai_dark"]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rp(rel):
    return os.path.join(REPO, rel)


# ---------------------------------------------------------------- 入力
def load_inputs(P, check=True):
    inp = P["inputs"]
    rig30 = T.load_json(rp(inp["rig30"]))
    ks = KStar(rp(inp["kstar_dir"]), inp["kstar_gwb_sha256"] if check else None)
    shas = {}
    for k in ("bake_sdf", "bake_warp"):
        shas[k] = sha256_file(rp(inp[k]))
        if check and shas[k] != inp[k + "_sha256"]:
            raise SystemExit("入力の SHA-256 が違います: %s %s" % (inp[k], shas[k]))
    return rig30, ks, shas


def load_classes(P):
    """28修正01 の焼き込み（RGBA32、R 白・G 淡い水色・B 藍中・A 藍濃、値 = 127.5 + 8·距離）のテクセルの中心の色区（argmax）。
    配列の行 0 = v′ 0（Unity の LoadRawTextureData と同じ、下の行から）。"""
    b = np.fromfile(rp(P["inputs"]["bake_sdf"]), np.uint8).reshape(S, S, 4)
    return b.argmax(2).astype(np.uint8), b


def load_warp(P):
    w = T.load_json(rp(P["inputs"]["bake_warp"]))
    return np.asarray(w["uWarp"], np.float64), np.asarray(w["vWarp"], np.float64)


def texel_grid(uW, vW):
    """テクセルの中心 → 格子の小数の列・行（UV3 は列ごとの u′・行ごとの v′ で、格子の間は線形）。"""
    xc = (np.arange(S) + 0.5) / S
    colf = np.interp(xc, uW, np.arange(len(uW), dtype=np.float64))
    rowf = np.interp(xc, vW, np.arange(len(vW), dtype=np.float64))
    return colf, rowf


def texel_interp(G, colf, rowf):
    """頂点の値 G（行 × 列）を、GPU と同じ三角形の分け方（(r,c)(r+1,c)(r,c+1) と (r,c+1)(r+1,c)(r+1,c+1)）で
    テクセルの中心へ線形に補間する。戻り値は (S, S)（行 = v′、列 = u′）。"""
    nv, nu = G.shape
    c0 = np.clip(np.floor(colf).astype(int), 0, nu - 2)
    r0 = np.clip(np.floor(rowf).astype(int), 0, nv - 2)
    fx = (colf - c0)[None, :]
    fy = (rowf - r0)[:, None]
    R0, C0 = r0[:, None], c0[None, :]
    g00 = G[R0, C0]
    g01 = G[R0, C0 + 1]
    g10 = G[R0 + 1, C0]
    g11 = G[R0 + 1, C0 + 1]
    lower = (fx + fy) <= 1.0
    a = g00 + fx * (g01 - g00) + fy * (g10 - g00)
    b = g11 + (1.0 - fx) * (g10 - g11) + (1.0 - fy) * (g01 - g11)
    return np.where(lower, a, b)


# ---------------------------------------------------------------- 白の時間場
def rho_grid(ks, rig30):
    """行ごとの白の波面の座標 ρ（K* の弧長を区間ごとに正規化）。"""
    pc = rig30["profile_columns"]
    jB, jT, jP, jK, jF, jE = (pc[k] for k in ("j_B", "j_top", "j_tip", "j_corner", "j_facebot", "j_E"))
    X = ks.X
    nv, nu = ks.nv, ks.nu
    seg = np.linalg.norm(np.diff(X, axis=1), axis=-1)
    s = np.concatenate([np.zeros((nv, 1)), np.cumsum(seg, 1)], 1)
    rho = np.zeros((nv, nu))
    knots = [(0, -1.0 - 1.0), (jB, -1.0), (jT, 0.0), (jP, 1.0), (jK, 2.0), (jF, 3.0), (jE, 4.0), (nu - 1, 5.0)]
    for (ja, ra), (jb, rb) in zip(knots[:-1], knots[1:]):
        L = np.maximum(s[:, jb] - s[:, ja], 1e-6)
        rho[:, ja:jb + 1] = ra + (rb - ra) * (s[:, ja:jb + 1] - s[:, ja][:, None]) / L[:, None]
    return rho, s


def wobble(c, wb):
    n = np.zeros_like(c)
    for lam, wt, ph in zip(wb["wavelengths_m"], wb["weights"], wb["phases_rad"]):
        n += wt * np.sin(2 * np.pi * c / lam + ph)
    return n / max(sum(abs(w) for w in wb["weights"]), 1e-9)


def inverse_table(table, t_lo, t_hi):
    f = clamped_pchip(table)
    tg = np.linspace(t_lo, t_hi, 200001)
    rg = f(tg)
    if np.any(np.diff(rg) <= 0):
        raise SystemExit("波面の表が狭義に単調ではありません")
    return f, tg, rg


def twhite_grid(P, ks, rig30):
    tl = P["timeline"]
    fr = P["front"]
    t0, t1 = float(tl["t_start_s"]), float(tl["t_end_s"])
    rho, s = rho_grid(ks, rig30)
    wb = fr["wobble"]
    n = wobble(ks.c, wb)[:, None]
    ff, tgf, rgf = inverse_table(fr["table_front"], t0, t1)
    fb, tgb, rgb = inverse_table(fr["table_back"], t0, t1)
    rmax_f, rmax_b = float(rgf[-1]), float(rgb[-1])
    Tg = np.full(rho.shape, t1)
    # 前（頂 → 船側）
    pf = np.clip(rho, 0.0, rmax_f)
    pf2 = pf + float(wb["amplitude"]) * n * (rmax_f / np.pi) * np.sin(np.pi * pf / rmax_f)
    Tf = np.interp(pf2, rgf, tgf)
    # 後ろ（頂 → 背面の足）
    pb = np.clip(-rho, 0.0, rmax_b)
    pb2 = pb + float(wb["amplitude_back"]) * n * (rmax_b / np.pi) * np.sin(np.pi * pb / rmax_b)
    Tb = np.interp(pb2, rgb, tgb)
    Tg = np.where(rho >= 0.0, Tf, Tb)
    info = {"rho_front_max": rmax_f, "rho_back_max": rmax_b, "wobble_abs_max": float(np.abs(n).max()),
            "min_drho_prime_over_drho_front": 1.0 - float(wb["amplitude"]), "min_drho_prime_over_drho_back": 1.0 - float(wb["amplitude_back"]),
            "T_min_s": float(Tg.min()), "T_max_s": float(Tg.max())}
    return Tg.astype(np.float32), rho, s, info, (ff, fb)


# ---------------------------------------------------------------- keypose（番号30、Git 対象外）
class Keypose:
    def __init__(self, P):
        d = rp(P["inputs"]["keypose_dir"])
        self.meta = T.load_json(os.path.join(d, "af30_keypose.json"))
        pos = os.path.join(d, self.meta["position_file"])
        sha = sha256_file(pos)
        if sha != self.meta["position_sha256"] or sha != P["inputs"]["keypose_position_sha256"]:
            raise SystemExit("keypose の SHA-256 が違います: " + sha)
        self.sha = sha
        nv, nu, L = self.meta["nv"], self.meta["nu"], self.meta["layers"]
        self.q = np.fromfile(pos, "<u2").reshape(L, nv, nu, 4)[..., :3]
        self.lo = np.asarray(self.meta["bbox_min"], np.float64)
        self.size = np.asarray(self.meta["bbox_size"], np.float64)
        self.times = np.asarray(self.meta["key_times_s"], np.float64)

    def X(self, t):
        idx, w = cr_weights(self.times, t)
        out = None
        for q in range(4):
            if w[q] == 0.0:
                continue
            v = w[q] * (self.lo + self.q[idx[q]].astype(np.float64) / 65535.0 * self.size)
            out = v if out is None else out + v
        return out


def cell_areas(X):
    a = X[:-1, :-1]
    b = X[1:, :-1]
    c = X[:-1, 1:]
    d = X[1:, 1:]
    t1 = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=-1)
    t2 = 0.5 * np.linalg.norm(np.cross(b - c, d - c), axis=-1)
    return t1 + t2


# ---------------------------------------------------------------- 段
def stage_field(P, out, log=print):
    rig30, ks, shas = load_inputs(P)
    Tg, rho, s, info, _ = twhite_grid(P, ks, rig30)
    wd = os.path.join(out, "white")
    os.makedirs(wd, exist_ok=True)
    path = os.path.join(wd, P["texture"]["file"])
    Tg.astype("<f4").tofile(path)
    # 行の中の単調さ（頂から離れるほど遅い）
    pc = rig30["profile_columns"]
    jT = pc["j_top"]
    front_mono = bool(np.all(np.diff(Tg[:, jT:].astype(np.float64), axis=1) >= -1e-6))
    back_mono = bool(np.all(np.diff(Tg[:, :jT + 1].astype(np.float64), axis=1) <= 1e-6))
    rec = {
        "schema": "GreatWave.AF31.twhite/1", "number": "31",
        "file": P["texture"]["file"], "format_ja": P["texture"]["format"], "nu": ks.nu, "nv": ks.nv,
        "bytes": os.path.getsize(path), "sha256": sha256_file(path),
        "t_start_s": P["timeline"]["t_start_s"], "t_end_s": P["timeline"]["t_end_s"], "t_star_s": P["timeline"]["t_star_s"],
        "pre_white_class": P["pre_white"]["class"], "pre_white_index": CLASS_NAMES.index(P["pre_white"]["class"]),
        "params_sha256": sha256_file(P["_path"]), "kstar_gwb_sha256": ks.gwb_sha, "bake_sdf_sha256": shas["bake_sdf"], "bake_warp_sha256": shas["bake_warp"],
        "row_monotone_front": front_mono, "row_monotone_back": back_mono, "field_info": info,
        "rows_main": ks.main_row,
    }
    T.save_json(os.path.join(wd, "af31_twhite.json"), rec)
    np.savez_compressed(os.path.join(wd, "af31_grid.npz"), T=Tg, rho=rho.astype(np.float32), s=s.astype(np.float32), c=ks.c)
    log("T_white：%s（%d バイト、SHA-256 %s…）、%.3f〜%.3f s、行の中の単調 前 %s・後ろ %s" % (path, rec["bytes"], rec["sha256"][:12], info["T_min_s"], info["T_max_s"], front_mono, back_mono))
    return rec


def stage_uv(P, out, log=print):
    """UV（テクセル）空間の検査：30 Hz・0〜17 s。"""
    rig30, ks, shas = load_inputs(P)
    wd = os.path.join(out, "white")
    g = np.load(os.path.join(wd, "af31_grid.npz"))
    Tg = g["T"].astype(np.float64)
    rho = g["rho"].astype(np.float64)
    cls, _ = load_classes(P)
    uW, vW = load_warp(P)
    colf, rowf = texel_grid(uW, vW)
    Tt = texel_interp(Tg, colf, rowf)
    Rt = texel_interp(rho, colf, rowf)
    Wm = cls == 0
    nW = int(Wm.sum())
    pre = CLASS_NAMES.index(P["pre_white"]["class"])
    tl = P["timeline"]
    ck = P["checks"]
    hz = float(ck["hz"])
    nf = int(round(float(ck["end_s"]) * hz)) + 1
    ts = np.arange(nf) / hz
    # テクセルごとの白くなるフレーム（t_f ≥ T の最初のフレーム）
    Tw = Tt[Wm]
    fidx = np.clip(np.ceil(Tw * hz - 1e-9).astype(np.int64), 0, nf)
    cnt = np.bincount(fidx, minlength=nf + 1)[:nf]
    cum = np.cumsum(cnt)
    frac = cum / nW
    step = np.diff(np.concatenate([[0], cum])) / nW
    # 白でないテクセルが白になる数（表示の規則は『終態が白 かつ t ≥ T』なので作りから 0。規則を配列で再現して全フレームで数える）
    nonwhite_white = 0
    Tn = np.where(Wm, Tt, np.inf)
    for t in ts:
        nonwhite_white += int(((Tn <= t) & ~Wm).sum())
    # 格子のセルの世界の面積で重みを付けた白の面積（keypose の Catmull-Rom、GPU と同じ式）
    kp = Keypose(P)
    nvc, nuc = ks.nv - 1, ks.nu - 1
    c0 = np.clip(np.floor(colf).astype(int), 0, nuc - 1)
    r0 = np.clip(np.floor(rowf).astype(int), 0, nvc - 1)
    cell = (r0[:, None] * nuc + c0[None, :])
    ncell_tex = np.bincount(cell.ravel(), minlength=nvc * nuc).astype(np.float64)
    cellW = cell[Wm]
    # フレームごとに白くなったテクセルをセルへ足していく（セルの中の白くなったテクセル数）
    ordf = np.argsort(fidx, kind="stable")
    fs = fidx[ordf]
    cs = cellW[ordf]
    bounds = np.searchsorted(fs, np.arange(nf + 1))
    cumc = np.zeros(nvc * nuc, np.float64)
    W_cells = np.bincount(cellW, minlength=nvc * nuc).astype(np.float64)
    area_white = np.zeros(nf)
    area_final_white = np.zeros(nf)
    for f, t in enumerate(ts):
        a_, b_ = bounds[f], bounds[f + 1]
        if b_ > a_:
            cumc += np.bincount(cs[a_:b_], minlength=nvc * nuc)
        A = cell_areas(kp.X(t)).ravel()
        per_tex = A / np.maximum(ncell_tex, 1.0)
        area_white[f] = float((per_tex * cumc).sum())
        area_final_white[f] = float((per_tex * W_cells).sum())
    # 波面（白くなった所の ρ の上位）の進み
    front_rho = []
    Rw = Rt[Wm]
    order = np.argsort(Tw)
    Tw_sorted = Tw[order]
    Rw_sorted = Rw[order]
    for t in ts:
        k = int(np.searchsorted(Tw_sorted, t, side="right"))
        if k == 0:
            front_rho.append(None)
            continue
        recent = Rw_sorted[max(0, k - max(1, nW // 500)):k]
        front_rho.append([float(np.median(recent)), float(recent.min()), float(recent.max())])
    t_first = float(Tw.min())
    t_all = float(Tw.max())
    i_star = int(round(float(tl["t_star_s"]) * hz))
    res = {
        "schema": "GreatWave.AF31.uvcheck/1", "number": "31",
        "method_ja": "UV（テクセル）空間。28修正01 の焼き込みのテクセルの中心の色区（argmax）と、頂点の T_white を GPU と同じ三角形で線形に補間したテクセルの T。30 Hz・0〜17 s（511 フレーム）で、表示の規則（終態が白 かつ t ≥ T で白、それ以外は終態の色、終態が白で t < T は白の前の色）を数えた。白の面積の世界の値は番号30 の keypose（GPU と同じ Catmull-Rom）で格子のセルの面積を求め、セルの中の白くなったテクセルの割合を掛けた。",
        "final_white_texels": nW, "texels": S * S,
        "hz": hz, "frames": nf,
        "t_first_white_s": t_first, "t_all_white_s": t_all,
        "white_fraction": [float(v) for v in frac],
        "white_fraction_step_max": float(step.max()), "white_fraction_step_max_at_s": float(ts[int(step.argmax())]),
        "white_fraction_step_limit": float(ck["max_white_fraction_step_per_frame"]),
        "white_fraction_monotone": bool(np.all(np.diff(frac) >= 0)),
        "white_fraction_at_t_star": float(frac[i_star]),
        "white_fraction_before_start": float(frac[int(math.floor(float(tl["t_start_s"]) * hz)) ]),
        "white_area_world_m2": [float(v) for v in area_white],
        "final_white_area_world_m2": [float(v) for v in area_final_white],
        "nonwhite_texels_shown_white": nonwhite_white,
        "front_rho_median_min_max": front_rho,
        "pre_white_class": P["pre_white"]["class"],
        "white_texels_by_segment": {},
        "keypose_position_sha256": kp.sha,
    }
    for a, b, name in ((-9, -1, "back_sea"), (-1, 0, "back_slope"), (0, 1, "lip_top"), (1, 2, "lip_under"), (2, 3, "inner_wall"), (3, 4, "trough"), (4, 9, "front_sea")):
        m = (Rw >= a) & (Rw < b)
        res["white_texels_by_segment"][name] = {"texels": int(m.sum()), "T_min_s": float(Tw[m].min()) if m.any() else None,
                                                "T_median_s": float(np.median(Tw[m])) if m.any() else None, "T_max_s": float(Tw[m].max()) if m.any() else None}
    T.save_json(os.path.join(wd, "af31_uvcheck.json"), res)
    np.savez_compressed(os.path.join(wd, "af31_texel_cache.npz"), Tt=Tt.astype(np.float32), Rt=Rt.astype(np.float32))
    # UV の図（上 = v′ 1）
    img = np.zeros((S, S, 3), np.uint8)
    pal = np.array([[223, 243, 248], [203, 215, 198], [147, 105, 44], [97, 64, 35]], np.uint8)
    img[:] = (pal[cls] * 0.35 + 90).astype(np.uint8)
    x = np.clip((Tt - 2.0) / 10.0, 0, 1)
    cm = cv2.applyColorMap((x * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
    img[Wm] = cm[Wm]
    small = cv2.resize(img[::-1], (1024, 1024), interpolation=cv2.INTER_AREA)
    cv2.imwrite(os.path.join(wd, "af31_uv_twhite.png"), small)
    log("UV：終態の白 %d テクセル、最初の白 %.3f s、全部 %.3f s、1 フレームの増分の最大 %.4f（%.2f s）、t* の割合 %.6f、白でないテクセルの白 %d"
        % (nW, t_first, t_all, res["white_fraction_step_max"], res["white_fraction_step_max_at_s"], res["white_fraction_at_t_star"], nonwhite_white))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default=DEFAULT_PARAMS)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--stage", default="all")
    a = ap.parse_args()
    P = T.load_json(a.params)
    P["_path"] = a.params
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    if a.stage in ("all", "field"):
        stage_field(P, a.out)
    if a.stage in ("all", "uv"):
        stage_uv(P, a.out)
    print("DONE %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
