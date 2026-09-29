# -*- coding: utf-8 -*-
"""設計29修正01：軽量版 120 × 200（設計29 の修正2 r02 の張り方：唇 column・管の天井 arc_tau・ほか column）を、
設計28修正01 の新しい動き（F_final のパッケージを精度の層つきで復号した Hermite）を源にして作り直す。

設計29 の ds29_build.py・ds29_surface.py（Display）は変えずに使う。違いは源だけ：
  - 設計29 の源は設計28 の生成器（ds28_model.Generator）だった。ここではパッケージそのもの（ds29_qa.PackageSurface を ds29r01_common で
    精度の層つきに差し替えたもの。節点の位置は生成器の値と 4.8 µm 以内、節点の間は包みの約束の Hermite）を源にする
    （F の生成器は 1 回 約 12 分かかり、表示の網は源の面の上の点なので、節点で同じ値を与えるパッケージで足りる。記録：源の違い）。
  - 目印の列（頂 root・rim・内壁の錨 ja・j_B・j_E、体のある行）は、設計27 の生成器（ds27_model._rows）と同じ規則・同じ値（ds27_params.json の rows）で
    K*′ の行（kstar_final の rows.npz）から求める（F の生成器は K*′ から同じ規則で求める。設計29 の Source._landmarks をそのまま通す）。
  - UV・UV2 は K*′ の gwb から、UV3（焼き込み用）は設計29 と同じ 28修正01 の焼き込みの表（K*′ 用の焼き直しは引き継ぎ (a) の別の作業。
    軽量版の色区は、その焼き直しができたら同じ手順で作り直す）。T_white はパッケージのファイル。
  - 書き出しは ds29_build.export（16 bit）に、精度の層（ds27_pos_lo_rgba8.bin、ds28r01e_generate.export_lo と同じ約束）を足す。
使い方（リポジトリの根で。1 回 数分）：
  py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_light.py [--out Unity/Build/Design/29R01/light] [--rows 120 --cols 200] [--uv3-warp <UV3 の表>]
"""
import argparse
import datetime
import json
import os
import platform
import sys
import time
from types import SimpleNamespace

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import ds29r01_common as C  # noqa: E402

REPO = C.REPO
LO_NAME = "ds27_pos_lo_rgba8.bin"


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def landmarks(A, Y, c, jB, jK, jE, rw):
    """ds27_model.Generator._rows の頂・内壁の錨・rim・体のある行の規則の写し（唇の重み κ などは使わない）。"""
    nv, nu = A.shape
    H = Y.max(1)
    has_body = H >= float(rw["body_H_min_m"])
    jt_raw = np.argmax(Y, 1).astype(np.float64)
    sgr = float(rw["root_row_smooth_m"])
    hb = has_body
    Wr = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sgr) ** 2) * hb[None, :]
    jt_s = (Wr @ jt_raw) / np.maximum(Wr.sum(1), 1e-12)
    root = np.where(hb, np.round(jt_s), jt_raw).astype(int)
    ja = np.full(nv, jK + 30, int)
    for r in range(nv):
        if not has_body[r]:
            continue
        w = np.arange(jK, jE + 1)
        yw = Y[r, w] - 0.3 * H[r]
        k = np.where(yw[:-1] * yw[1:] <= 0)[0]
        if len(k):
            k = k[0]
            f = (0.3 * H[r] - Y[r, w[k]]) / (Y[r, w[k + 1]] - Y[r, w[k]] + 1e-12)
            ja[r] = jK + k + (1 if f > 0.5 else 0)
    jtip = np.full(nv, -1, int)
    rim = np.full(nv, -1, int)
    e4cur = np.zeros(nv, bool)
    for r in range(nv):
        if H[r] < 2.0:
            continue
        y, a = Y[r], A[r]
        jt = root[r]
        if jt >= 200:
            continue
        sg = np.arange(jt, jK + 1)
        jp = int(sg[np.argmax(a[sg])])
        am = a[sg]
        loc = np.nonzero((am[1:-1] >= am[:-2]) & (am[1:-1] >= am[2:]))[0] + 1
        for k in loc:
            if am[k] >= am.max() - float(rw["tip_tie_m"]):
                jp = int(sg[k])
                break
        ov = (a[jp] - A[r, ja[r]]) / H[r]
        un = np.arange(jp, jK + 1)
        yy = y[un]
        kmin = next((i for i in range(1, len(yy) - 1) if yy[i] <= yy[i - 1] and yy[i] < yy[i + 1]), len(yy) - 1)
        un = un[:max(kmin + 1, 6)]
        jtip[r], rim[r] = jp, int(un[-1])
        e4cur[r] = (ov >= 0.2) and (jp > jt + 5)
    cur = np.nonzero(e4cur)[0]
    half = int(rw["boundary_median_rows"]) // 2
    tip_s = np.zeros(nv, int)
    rim_s = np.zeros(nv, int)
    for r in range(nv):
        q = cur[np.argmin(np.abs(cur - r))]
        if not e4cur[r]:
            tip_s[r], rim_s[r] = jtip[q], rim[q]
            continue
        win = cur[(cur >= r - half) & (cur <= r + half)]
        tip_s[r] = int(np.median(jtip[win]))
        rim_s[r] = int(np.median(rim[win]))
    sg_b = float(rw["boundary_row_smooth_m"])
    if sg_b > 0:
        Wb = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sg_b) ** 2)
        Wb /= Wb.sum(1, keepdims=True)
        rim_s = np.round(Wb @ rim_s.astype(np.float64)).astype(int)
    rim_s = np.maximum(rim_s, tip_s + 3)
    rim_s = np.minimum(rim_s, ja - 20)
    return dict(has_body=has_body, root=root, ja=ja, rim=rim_s, tip=tip_s, e4_curled=e4cur)


class PkgSource:
    """設計29 の Source と同じ欄を持つ、パッケージを源にした版（ds29_surface.Display と ds29_build.export が読む欄）。"""

    def __init__(self, Q, pkg_dir, P, log):
        import ds29_surface as S
        import ds27_gates as G27
        self.P = P
        self.log = log
        self.pkg_dir = os.path.join(REPO, pkg_dir)
        jp = os.path.join(self.pkg_dir, "ds27_keypose.json")
        self.pkg = json.load(open(jp, encoding="utf-8"))
        self.pkg_json_sha = S.sha256_file(jp)
        self.surf = Q.PackageSurface(self.pkg_dir, "src")
        ks = G27.KStar()
        self.ks = ks
        kdir = C.STATE["kstar"]
        self.K = SimpleNamespace(X=ks.X, main_row=ks.main_row, dir=kdir, sha=ks.sha, nv=ks.nv, nu=ks.nu)
        self.nv, self.nu = ks.nv, ks.nu
        if (self.surf.rows, self.surf.cols) != (ks.nv, ks.nu):
            raise SystemExit("[ds29r01_light] パッケージの格子が K*′ と違います")
        b = open(os.path.join(kdir, "kstar_a45.gwb"), "rb").read()
        n = self.nv * self.nu
        self.uv = np.frombuffer(b, np.float32, n * 2, 32).reshape(n, 2).astype(np.float64)
        self.uv2 = np.frombuffer(b, np.float32, n * 2, 32 + n * 8).reshape(n, 2).astype(np.float64)
        wp = os.path.join(REPO, P["source"]["uv3_warp"])
        W = json.load(open(wp, encoding="utf-8"))
        uw = np.asarray(W["uWarp"], np.float64)
        vw = np.asarray(W["vWarp"], np.float64)
        self.uv3 = np.stack(np.broadcast_arrays(uw[None, :], vw[:, None]), -1).reshape(n, 2)
        self.uv3_sha = S.sha256_file(wp)
        self.uv3_path = wp
        tp = os.path.join(self.pkg_dir, self.pkg["twhite_file"])
        self.twhite = np.fromfile(tp, "<f4").reshape(self.nv, self.nu).astype(np.float64)
        self.twhite_matches_package = True
        self.knots = np.asarray(self.pkg["knot_tau"], np.float64)
        self.arc0 = S.row_arc(self.K.X)
        P27 = json.load(open(os.path.join(REPO, "Tools", "GWWaveGen", "ds27", "ds27_params.json"), encoding="utf-8"))
        lm = self.pkg["kstar"]["landmarks"]
        jB, jK, jE = int(lm["j_B"]), int(lm["j_corner"]), int(lm["j_E"])
        LM = landmarks(ks.A, ks.Y, ks.c, jB, jK, jE, P27["rows"])
        self.lm_raw = LM
        self.g = SimpleNamespace(K=SimpleNamespace(sha=ks.sha), has_body=LM["has_body"], root=LM["root"], rim=LM["rim"], ja=LM["ja"],
                                 jB=jB, jE=jE)
        S.Source._landmarks(self)

    def local(self, tau):
        return self.surf.local(float(tau)).reshape(self.nv, self.nu, 3)

    def origin(self, tau):
        return self.surf.origin(float(tau))


def write_lo(outdir, layers, log):
    """ds28r01e_generate.export_lo と同じ約束で精度の層を書き、ds27_keypose.json に欄を足す。"""
    jp = os.path.join(outdir, "ds27_keypose.json")
    rec = json.load(open(jp, encoding="utf-8"))
    lo = np.asarray(rec["bbox_min"], np.float64)
    size = np.asarray(rec["bbox_size"], np.float64)
    u = (layers - lo) / size * 65535.0
    q = np.clip(np.round(u), 0, 65535)
    e = u - q
    ql = np.clip(np.round((e + 0.5) * 255.0), 0, 255).astype(np.uint8)
    L, nv, nu = layers.shape[:3]
    buf = np.concatenate([ql, np.full((L, nv, nu, 1), 255, np.uint8)], -1)
    p = os.path.join(outdir, LO_NAME)
    buf.tofile(p)
    deq_hi = lo + q / 65535.0 * size
    deq_fine = lo + (q + ql.astype(np.float64) / 255.0 - 0.5) / 65535.0 * size
    rec["extensions"] = ["pos_lo_rgba8/1"]
    rec["pos_lo_file"] = LO_NAME
    rec["pos_lo_sha256"] = C.sha256_file(p)
    rec["pos_lo_bytes"] = int(os.path.getsize(p))
    rec["pos_lo_format_ja"] = ("RGBA8 UNORM（TextureFormat.RGBA32）、層 × 行 × 列 × 4。16 bit の丸めの残り e = u − round(u) を round((e + 0.5)·255) で持つ。"
                               "A = 255。復号：位置 = bbox_min + (q16 + lo/255 − 0.5)/65535·bbox_size（ds28r01e_generate.py と同じ約束）")
    rec["pos_precision"] = dict(hi_step_mm=float(size.max() / 65535 * 1000), fine_step_mm=float(size.max() / 65535 / 255 * 1000),
                                max_err_hi_m=float(np.linalg.norm(deq_hi - layers, axis=-1).max()),
                                max_err_fine_m=float(np.linalg.norm(deq_fine - layers, axis=-1).max()))
    with open(jp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    log("  精度の層：刻み %.4f mm、量子化の差の最大 %.4f mm（16 bit だけ %.3f mm）" % (
        rec["pos_precision"]["fine_step_mm"], rec["pos_precision"]["max_err_fine_m"] * 1000, rec["pos_precision"]["max_err_hi_m"] * 1000))
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", default=C.DEFAULT_PACKAGE)
    ap.add_argument("--kstar", default=C.DEFAULT_KSTAR)
    ap.add_argument("--rows", type=int, default=120)
    ap.add_argument("--cols", type=int, default=200)
    ap.add_argument("--name", default="half_120x200")
    ap.add_argument("--out", default=os.path.join(C.OUT_ROOT, "light"))
    ap.add_argument("--uv3-warp", default=None, help="焼き込み用 UV（UV3）の列・行の表（既定：ds29_params.json の source.uv3_warp＝28修正01 の焼き込み。K*′ 用の焼き直しができたらそれを渡す）")
    a = ap.parse_args()
    t_all = time.time()
    logs = []

    def log(s):
        print(s, flush=True)
        logs.append(s)
    Q = C.setup(a.kstar, "fine")
    import ds29_surface as S
    import ds29_build as B
    P = S.load_params()
    P["source"] = dict(P["source"], package_dir=a.package, package_pos_sha256=None, version="art_on")
    if a.uv3_warp:
        P["source"]["uv3_warp"] = a.uv3_warp
    src = PkgSource(Q, a.package, P, log)
    log("源：%s（%d 層、精度の層つき）。目印：体のある行 %d、巻きの行（E4）%d、rim %d〜%d、ja %d〜%d（%.0f s）" % (
        C.rel(src.pkg_dir), len(src.knots), int(src.body.sum()), int(src.lm_raw["e4_curled"].sum()),
        int(src.L[src.body, 3].min()), int(src.L[src.body, 3].max()), int(src.L[src.body, 4].min()), int(src.L[src.body, 4].max()), time.time() - t_all))
    modes = dict(P["segments"]["mode"])
    modes["lip"] = "column"          # r02（設計29 の修正2 の候補 A）
    d = S.Display(src, a.rows, a.cols, name=a.name, modes=modes)
    X = B.Cache(src, log)
    kn, lay, rounds = B.build_layers(d, src.knots, X, P, log)
    outdir = os.path.join(a.out, a.name)
    rec = B.export(d, src, kn, lay, outdir, log)
    rec2 = write_lo(outdir, lay, log)
    # 設計29 の書き出しの説明を、この番号の源に合わせて直す（t* の説明・番号）
    rec2["number"] = "設計29修正01"
    rec2["tstar"]["note_ja"] = "最後の層（τ = 0）は K*′（Unity/Build/Design/28R01F/kstar_final）の面の上の点（表示の網の頂点。量子化の差だけ）。"
    rec2["generator"]["code"] = "Tools/GWWaveGen/ds29r01/ds29r01_light.py（設計29 の ds29_surface.Display・ds29_build.export、源 = F_final のパッケージの精度の層つきの Hermite）"
    rec2["generator"]["code_sha256_ds29r01"] = {f: C.sha256_file(os.path.join(HERE, f)) for f in ("ds29r01_light.py", "ds29r01_common.py")}
    rec2["display_surface"]["note_ja"] = ("表示の頂点は源（設計28修正01 の F_final のパッケージ、精度の層つきの Hermite）の面の上の点。r02 の張り方（唇 column、管の天井 arc_tau）。"
                                          "UV3 は 28修正01 の焼き込みの表（K*′ 用の焼き直しの前。色区は記録のみ）。")
    with open(os.path.join(outdir, "ds27_keypose.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec2, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    out = dict(generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), python=platform.python_version(),
               numpy=np.__version__, command="py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_light.py " + " ".join(sys.argv[1:]),
               source_package=C.rel(src.pkg_dir), source_pos_sha256=src.pkg["pos_sha256"], source_pos_lo_sha256=src.pkg.get("pos_lo_sha256"),
               kstar=C.STATE["kstar_src"], layers=int(len(kn)), adaptive_rounds=rounds, describe=d.describe(),
               pos_sha256=rec2["pos_sha256"], pos_lo_sha256=rec2["pos_lo_sha256"], pos_precision=rec2["pos_precision"],
               gpu_estimate=rec2["gpu_estimate"], source_evals=X.n, seconds_total=round(time.time() - t_all, 1), log=logs)
    C.jdump(os.path.join(a.out, "ds29r01_light_build_%s.json" % a.name), out)
    print("DONE %.0f s" % (time.time() - t_all))


if __name__ == "__main__":
    main()
