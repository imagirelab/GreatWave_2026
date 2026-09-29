# -*- coding: utf-8 -*-
"""設計29修正01（Part A）：Unity の再生器が精度の層（ds27_pos_lo_rgba8.bin、拡張 pos_lo_rgba8/1）を読むことの照合。

作り手の Unity のコード（DS29KeyposePlayer・DS27KeyposeCore.cginc）は読まず、パッケージの json の約束（pos_lo_format_ja・interpolation_ja・
frame）だけから numpy で書いた。numpy と Pillow だけ。

1. gpu：DS29Render が DS27KeyposeCapture.compute（頂点シェーダーと同じ関数）で読み戻した全頂点のワールドの位置を、
   同じパッケージの numpy の再生（float64）と比べる。
   - 復号：精度の層つき X = bbox_min + (q16 + lo/255 − 0.5)/65535·bbox_size、16 bit だけ X16 = bbox_min + q16/65535·bbox_size。
   - 補間：節点 τ_i の間の 3 次 Hermite。傾き m_i = (p_{i+1} − p_{i−1})/(τ_{i+1} − τ_{i−1})、両端は片側（json の interpolation_ja）。
     重みの式ではなく、傾きを作ってから Hermite の基底で足す（C# の重みの式とは別の書き方）。
   - 枠の原点 O(τ)：frame.tau・frame.origin の線形補間（範囲の外は端）。
   - 読み戻しの τ を「節点」「隣り合う節点の中点」「30 Hz のコマ」「そのほか」に分け、τ ∈ [a, b]（既定 −6〜0 s）の最大の差を出す。
   - 16 bit だけの読みとの差も出す（GPU が精度の層を読んでいれば、16 bit の量子化の差の大きさ ≈ 1.2 mm まで離れる）。
   - t* のコマは K*′（パッケージの json の kstar.dir の .gwb、量子化の前）とも比べる。
2. regress：新しい描画と古い証拠の出力（DS29Render／DS27Formation の報告の files・filesSha256・videos）を、
   出力のフォルダーからの相対の名前で突き合わせる。SHA-256 が違う PNG は画素の差を数える。
3. summary：上の結果と、描画の報告の GPU の容量をまとめ、最小の受入の判定を書く。

使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_unity_check.py gpu --run Unity/Build/Design/29R01/unity/f_final
       --package Unity/Build/Design/28R01F/F_final/art_on --range -6,0 --out Unity/Build/Design/29R01/unity/check_gpu_f_final.json
  py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_unity_check.py regress --new Unity/Build/Design/29R01/unity/regress_d28
       --ref Unity/Build/Design/29/unity/src_d28 --report ds29_render_report.json --out Unity/Build/Design/29R01/unity/check_regress_d28.json
  py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_unity_check.py summary --out Unity/Build/Design/29R01/unity/ds29r01_unity_check.json
"""
import argparse
import hashlib
import json
import os
import struct
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
UB = os.path.join(REPO, "Unity", "Build", "Design", "29R01", "unity")


def ab(p):
    return p if os.path.isabs(p) else os.path.join(REPO, p)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def save(p, obj):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


# ------------------------------------------------------------------ パッケージの numpy の再生（json の約束から）
class Pkg:
    def __init__(self, d):
        self.dir = os.path.abspath(ab(d))
        J = json.load(open(os.path.join(self.dir, "ds27_keypose.json"), encoding="utf-8"))
        self.J = J
        self.L, self.R, self.C = int(J["layers"]), int(J["rows"]), int(J["cols"])
        self.N = self.R * self.C
        self.bmin = np.asarray(J["bbox_min"], np.float64)
        self.bsz = np.asarray(J["bbox_size"], np.float64)
        self.k = np.asarray(J["knot_tau"], np.float64)
        self.ftau = np.asarray(J["frame"]["tau"], np.float64)
        self.forg = np.asarray(J["frame"]["origin"], np.float64).reshape(-1, 3)
        pp = os.path.join(self.dir, J.get("pos_file", "ds27_pos_rgba16.bin"))
        self.q = np.memmap(pp, dtype="<u2", mode="r", shape=(self.L, self.N, 4))
        self.has_lo = "pos_lo_rgba8/1" in (J.get("extensions") or [])
        self.lo = None
        self.checks = {"pos_sha256_ok": sha256_file(pp) == J["pos_sha256"]}
        if self.has_lo:
            lp = os.path.join(self.dir, J["pos_lo_file"])
            self.lo = np.memmap(lp, dtype=np.uint8, mode="r", shape=(self.L, self.N, 4))
            self.checks["pos_lo_sha256_ok"] = sha256_file(lp) == J["pos_lo_sha256"]
            self.checks["pos_lo_alpha_not_255"] = int((np.asarray(self.lo[..., 3]) != 255).sum())
        self._cache = {}

    def layer(self, i, fine):
        key = (i, fine)
        if key not in self._cache:
            q = np.asarray(self.q[i, :, :3], np.float64)
            if fine and self.lo is not None:
                q = q + np.asarray(self.lo[i, :, :3], np.float64) / 255.0 - 0.5
            self._cache[key] = self.bmin[None, :] + q / 65535.0 * self.bsz[None, :]
            if len(self._cache) > 24:
                self._cache.pop(next(iter(self._cache)))
        return self._cache[key]

    def tangent(self, i, fine):
        k, n = self.k, self.L
        if i == 0:
            return (self.layer(1, fine) - self.layer(0, fine)) / (k[1] - k[0])
        if i == n - 1:
            return (self.layer(n - 1, fine) - self.layer(n - 2, fine)) / (k[n - 1] - k[n - 2])
        return (self.layer(i + 1, fine) - self.layer(i - 1, fine)) / (k[i + 1] - k[i - 1])

    def local(self, tau, fine):
        k = self.k
        if tau <= k[0]:
            return self.layer(0, fine)
        if tau >= k[-1]:
            return self.layer(self.L - 1, fine)
        i = int(np.searchsorted(k, tau, side="right") - 1)
        i = min(i, self.L - 2)
        D = k[i + 1] - k[i]
        s = (tau - k[i]) / D
        h00, h10, h01, h11 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s, -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
        return (h00 * self.layer(i, fine) + h10 * D * self.tangent(i, fine)
                + h01 * self.layer(i + 1, fine) + h11 * D * self.tangent(i + 1, fine))

    def origin(self, tau):
        return np.array([np.interp(tau, self.ftau, self.forg[:, a]) for a in range(3)])

    def world(self, tau, fine=True):
        return self.local(tau, fine) + self.origin(tau)[None, :]


def read_gwb_positions(path):
    b = open(path, "rb").read()
    ver, nu, nv, fr = struct.unpack("<iiii", b[4:20])
    nt = struct.unpack("<i", b[28:32])[0]
    n = nu * nv
    o = 32 + n * 16 + nt * 12
    return np.frombuffer(b, np.float32, n * 3, o).reshape(n, 3).astype(np.float64)


def classify(tau, knots, a, b):
    if np.any(np.abs(knots - tau) < 1e-9):
        return "knot"
    mids = 0.5 * (knots[1:] + knots[:-1])
    if np.any(np.abs(mids - tau) < 1e-9):
        return "midpoint"
    f = (b - tau) * 30.0
    if abs(f - round(f)) < 1e-6:
        return "frame30"
    return "other"


def cmd_gpu(a):
    t0 = time.time()
    run = ab(a.run)
    P = Pkg(a.package)
    lo_, hi_ = [float(x) for x in a.range.split(",")]
    C = json.load(open(os.path.join(run, "gpu_capture", "ds29_gpu_capture.json"), encoding="utf-8"))
    rows = []
    for c in C["captures"]:
        tau = float(c["tau"])
        g = np.fromfile(os.path.join(run, "gpu_capture", c["file"]), "<f4").reshape(-1, 6).astype(np.float64)
        Xf = P.world(tau, True)
        X16 = P.world(tau, False)
        df = np.linalg.norm(g[:, :3] - Xf, axis=1)
        d16 = np.linalg.norm(g[:, :3] - X16, axis=1)
        dq = np.linalg.norm(Xf - X16, axis=1)
        nl = np.linalg.norm(g[:, 3:], axis=1)
        vmax = int(np.argmax(df))
        rows.append(dict(tau=round(tau, 9), kind=classify(tau, P.k, lo_, hi_), in_range=bool(lo_ - 1e-9 <= tau <= hi_ + 1e-9),
                         max_vs_fine_mm=float(df.max() * 1000), p99_vs_fine_mm=float(np.percentile(df, 99) * 1000),
                         argmax_row=vmax // P.C, argmax_col=vmax % P.C,
                         max_vs_16bit_only_mm=float(d16.max() * 1000), median_vs_16bit_only_mm=float(np.median(d16) * 1000),
                         max_fine_minus_16bit_numpy_mm=float(dq.max() * 1000),
                         nan=int(np.isnan(g).sum()), normal_len_min=float(nl.min()), normal_len_max=float(nl.max())))
    # t* と K*′
    kst = None
    kd = P.J.get("kstar", {}).get("dir")
    if kd:
        kdir = ab(kd)
        gw = [f for f in os.listdir(kdir) if f.endswith(".gwb")] if os.path.isdir(kdir) else []
        tz = [c for c in C["captures"] if abs(float(c["tau"])) < 1e-12]
        if gw and tz:
            K = read_gwb_positions(os.path.join(kdir, gw[0]))
            g = np.fromfile(os.path.join(run, "gpu_capture", tz[0]["file"]), "<f4").reshape(-1, 6).astype(np.float64)
            X16 = P.world(0.0, False)
            Xf = P.world(0.0, True)
            kst = dict(kstar_gwb=os.path.relpath(os.path.join(kdir, gw[0]), REPO).replace("\\", "/"), kstar_gwb_sha256=sha256_file(os.path.join(kdir, gw[0])),
                       gpu_vs_kstar_max_mm=float(np.linalg.norm(g[:, :3] - K, axis=1).max() * 1000),
                       numpy_fine_vs_kstar_max_mm=float(np.linalg.norm(Xf - K, axis=1).max() * 1000),
                       numpy_16bit_vs_kstar_max_mm=float(np.linalg.norm(X16 - K, axis=1).max() * 1000),
                       note_ja="t* の層は K*′ そのもの（量子化の差だけ）。精度の層つきの GPU の読み戻しと K*′ の .gwb（float32、量子化の前）の差")
    inr = [r for r in rows if r["in_range"]]
    by = {}
    for kind in ("knot", "midpoint", "frame30", "other"):
        rr = [r for r in inr if r["kind"] == kind]
        if rr:
            w = max(rr, key=lambda r: r["max_vs_fine_mm"])
            by[kind] = dict(count=len(rr), max_vs_fine_mm=w["max_vs_fine_mm"], at_tau=w["tau"],
                            min_of_max_vs_16bit_only_mm=min(r["max_vs_16bit_only_mm"] for r in rr),
                            max_of_max_vs_16bit_only_mm=max(r["max_vs_16bit_only_mm"] for r in rr))
    worst = max(r["max_vs_fine_mm"] for r in inr) if inr else None
    res = dict(schema="GreatWave.DS29R01.gpu_check/1", run=os.path.relpath(run, REPO).replace("\\", "/"),
               package=os.path.relpath(P.dir, REPO).replace("\\", "/"), package_checks=P.checks, has_pos_lo=P.has_lo,
               range_tau=[lo_, hi_], captures=len(rows), captures_in_range=len(inr), by_kind_in_range=by,
               worst_in_range_vs_fine_mm=worst, criterion_mm=0.25, passed=bool(worst is not None and worst <= 0.25 and all(r["nan"] == 0 for r in rows)),
               nan_total=int(sum(r["nan"] for r in rows)), normal_len_min=float(min(r["normal_len_min"] for r in rows)),
               tstar_vs_kstar=kst, seconds=round(time.time() - t0, 1),
               method_ja=("GPU の読み戻し（DS27KeyposeCapture.compute、float32）と、json の約束から書いた numpy の再生（float64、傾きを作る Hermite、"
                          "精度の層つきの復号 bbox_min + (q16 + lo/255 − 0.5)/65535·bbox_size）の全頂点の差の最大。"
                          "max_vs_16bit_only_mm は 16 bit だけの numpy との差（GPU が精度の層を読んでいれば量子化の差の大きさまで離れる）"),
               rows=rows)
    save(ab(a.out), res)
    print("DS29R01_GPU worst_in_range=%.5f mm captures=%d/%d passed=%s -> %s" % (worst if worst is not None else -1, len(inr), len(rows), res["passed"], a.out))


# ------------------------------------------------------------------ 後方互換：古い証拠との一致
def pixel_diff(pa, pb):
    from PIL import Image
    A = np.asarray(Image.open(pa).convert("RGB"), np.int16)
    B = np.asarray(Image.open(pb).convert("RGB"), np.int16)
    if A.shape != B.shape:
        return dict(shape_a=list(A.shape), shape_b=list(B.shape), differing_pixels=None)
    d = np.abs(A - B).max(-1)
    return dict(differing_pixels=int((d > 0).sum()), max_channel_diff=int(d.max()))


def rel_to(path, root):
    p = os.path.normpath(ab(path))
    return os.path.relpath(p, os.path.normpath(ab(root))).replace("\\", "/")


def cmd_regress(a):
    new, ref = ab(a.new), ab(a.ref)
    Rn = json.load(open(os.path.join(new, a.report), encoding="utf-8"))
    Rr = json.load(open(os.path.join(ref, a.report), encoding="utf-8"))
    ref_out = Rr.get("outDir") or ref

    def table(R, root):
        out = {}
        for f, h in zip(R.get("files", []), R.get("filesSha256", [])):
            # 報告の files は Unity プロジェクトからの相対（Build/…）
            fp = f if os.path.isabs(f) else os.path.join(REPO, "Unity", f)
            out[rel_to(fp, root)] = (fp, h)
        return out

    Tn, Tr = table(Rn, new), table(Rr, ref)
    files = []
    for k in sorted(set(Tn) | set(Tr)):
        if k not in Tn or k not in Tr:
            files.append(dict(file=k, in_new=k in Tn, in_ref=k in Tr, same_sha256=False))
            continue
        (fn, hn), (fr, hr) = Tn[k], Tr[k]
        hn2 = sha256_file(fn) if os.path.exists(fn) else None
        hr2 = sha256_file(fr) if os.path.exists(fr) else None
        rec = dict(file=k, same_sha256=(hn2 is not None and hn2 == hr2), sha256_new=hn2, sha256_ref=hr2,
                   report_sha_matches_file=(hn == hn2 and hr == hr2))
        if not rec["same_sha256"] and hn2 and hr2 and k.endswith(".png"):
            rec["pixels"] = pixel_diff(fn, fr)
        files.append(rec)
    vids = []
    vn = {v["view"]: v for v in Rn.get("videos", [])}
    vr = {v["view"]: v for v in Rr.get("videos", [])}
    for v in sorted(set(vn) | set(vr)):
        a_, b_ = vn.get(v), vr.get(v)
        sa = sha256_file(a_["path"]) if a_ and os.path.exists(a_["path"]) else None
        sb = sha256_file(b_["path"]) if b_ and os.path.exists(b_["path"]) else None
        vids.append(dict(view=v, sha256_new=sa, sha256_ref=sb, same_sha256=bool(sa and sa == sb)))
    ok = all(f["same_sha256"] or (f.get("pixels") or {}).get("differing_pixels") == 0 for f in files) and all(v["same_sha256"] for v in vids)
    res = dict(schema="GreatWave.DS29R01.regress/1", new=os.path.relpath(new, REPO).replace("\\", "/"), ref=os.path.relpath(ref, REPO).replace("\\", "/"),
               report=a.report, files_compared=len(files), files_same_sha256=sum(1 for f in files if f["same_sha256"]),
               videos_compared=len(vids), videos_same_sha256=sum(1 for v in vids if v["same_sha256"]),
               new_pos_lo_used=Rn.get("posLoUsed"), pixel_identical=ok, files=files, videos=vids,
               method_ja="古い証拠の報告の files・filesSha256・videos と、新しいコードで同じ引数で描いた報告を、出力のフォルダーからの相対の名前で突き合わせ、ファイルの SHA-256 を計り直して比べた（PNG の SHA-256 が同じ＝画素も同じ）")
    save(ab(a.out), res)
    print("DS29R01_REGRESS files %d/%d same, videos %d/%d same, pixel_identical=%s -> %s" % (
        res["files_same_sha256"], res["files_compared"], res["videos_same_sha256"], res["videos_compared"], ok, a.out))


# ------------------------------------------------------------------ まとめ
CODE = ["Unity/Assets/GreatWave/Design27/Shaders/DS27KeyposeCore.cginc", "Unity/Assets/GreatWave/Design27/Shaders/DS27_NPR_White.shader",
        "Unity/Assets/GreatWave/Design27/Shaders/DS27_Outline_Keypose.shader", "Unity/Assets/GreatWave/Design27/Shaders/DS27KeyposeCapture.compute",
        "Unity/Assets/GreatWave/Design27/Scripts/DS27KeyposePlayer.cs", "Unity/Assets/GreatWave/Design29/Scripts/DS29KeyposePlayer.cs",
        "Unity/Assets/GreatWave/Design29/Editor/DS29Render.cs", "Unity/Assets/GreatWave/Design29/Editor/DS29R01ShaderCheck.cs",
        "Tools/GWWaveGen/ds29r01/ds29r01_unity_check.py", "Tools/GWWaveGen/ds29r01/run_ds29r01_unity.ps1"]
INPUTS = ["Unity/Build/Design/28R01F/F_final/art_on/ds27_keypose.json", "Unity/Build/Design/28R01F/F_final/art_on/ds27_pos_rgba16.bin",
          "Unity/Build/Design/28R01F/F_final/art_on/ds27_pos_lo_rgba8.bin", "Unity/Build/Design/28R01F/F_final/art_on/ds27_twhite_r32f.bin",
          "Unity/Build/Design/28R01F/F_final/timewarp_F_final.json", "Unity/Build/ArtFirst/26修正01/kstar/kstar_a45.gwb",
          "Unity/Build/ArtFirst/28修正01/bake/af28r01_uvsdf_a45.bin", "Unity/Build/ArtFirst/28修正01/bake/af28r01_uvwarp_a45.json",
          "Unity/Build/Design/28R01F/kstar_F_final/kstarR4_a45.gwb"]
COMMANDS = [
    "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds29r01/run_ds29r01_unity.ps1 -Method GreatWave.Design29.EditorTools.DS29Render.Render -Log f_final "
    "-Package Build/Design/28R01F/F_final/art_on -WarpFile Build/Design/28R01F/F_final/timewarp_F_final.json -OutDir Build/Design/29R01/unity/f_final "
    "-Stills \"m6=-6,m3=-3,m2=-2,m1=-1,m05=-0.5,tstar=0\" -Views \"painting,seat,seat_toward_wave,side_left\" -Skip timing "
    "-Extra \"-ds29Name f_final -ds29MeshFromPackage 0 -ds29CaptureRange -6,0\"",
    "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds29r01/run_ds29r01_unity.ps1 -Method GreatWave.Design29.EditorTools.DS29Render.Render -Log regress_d28 "
    "-Package Build/Design/28/art_on -OutDir Build/Design/29R01/unity/regress_d28 -Views \"painting,seat_toward_wave,side_left\" -Skip timing -Extra \"-ds29Name src_d28 -ds29MeshFromPackage 0\"",
    "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds29r01/run_ds29r01_unity.ps1 -Method GreatWave.Design27.EditorTools.DS27Formation.RenderOnly -Log regress_d27 "
    "-Version art_on -Warp default -OutDir Build/Design/29R01/unity/regress_d27 -Views \"painting,seat,side_left,seat_form\" -Skip \"frames,capture\"",
    "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds29r01/run_ds29r01_unity.ps1 -Method GreatWave.Design29.EditorTools.DS29R01ShaderCheck.Run -Log shader_check",
    "py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_unity_check.py gpu --run Unity/Build/Design/29R01/unity/f_final --package Unity/Build/Design/28R01F/F_final/art_on --range=-6,0 --out Unity/Build/Design/29R01/unity/check_gpu_f_final.json",
    "py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_unity_check.py regress --new Unity/Build/Design/29R01/unity/regress_d28 --ref Unity/Build/Design/29/unity/src_d28 --report ds29_render_report.json --out Unity/Build/Design/29R01/unity/check_regress_d28.json",
    "py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_unity_check.py regress --new Unity/Build/Design/29R01/unity/regress_d27 --ref Unity/Build/Design/27/art_on_default --report ds27_render_report.json --out Unity/Build/Design/29R01/unity/check_regress_d27.json",
    "py -3.10 -B Tools/GWWaveGen/ds27/ds27_tstar_eval.py --run Unity/Build/Design/29R01/unity/f_final",
    "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds29r01/run_ds29r01_unity.ps1 -Method GreatWave.Design29.EditorTools.DS29Render.Render -Log timing_f_final_lo<1|0> "
    "-Package Build/Design/28R01F/F_final/art_on -WarpFile Build/Design/28R01F/F_final/timewarp_F_final.json -OutDir Build/Design/29R01/unity/timing/f_final_lo<1|0> "
    "-Skip \"t28,capture,stills,video\" -Extra \"-ds29Name f_final_lo<1|0> -ds29MeshFromPackage 0 -ds29PosLo <1|0> -ds29TimingFrames 600\"",
    "py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_unity_check.py summary"]


def record(a):
    out = {}
    run = ab("Unity/Build/Design/29R01/unity/f_final")
    for sub in ("stills", "video", os.path.join("t28", "render")):
        d = os.path.join(run, sub)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            fp = os.path.join(d, f)
            if os.path.isfile(fp) and (f.endswith(".mp4") or (f.endswith(".png") and (sub != os.path.join("t28", "render") or os.stat(fp).st_nlink == 1))):
                out[os.path.relpath(fp, REPO).replace("\\", "/")] = sha256_file(fp)
    return dict(code_sha256={p: sha256_file(ab(p)) for p in CODE if os.path.exists(ab(p))},
                inputs_sha256={p: sha256_file(ab(p)) for p in INPUTS if os.path.exists(ab(p))},
                outputs_sha256=out, commands=COMMANDS,
                tools_ja="Unity 6000.4.3f1（batchmode、Direct3D11、RTX 3080）、py -3.10（numpy 2.2.6、Pillow）、ffmpeg 2024-12-19。PC のオフスクリーン描画で HMD 実機ではない")


def timing():
    out = {}
    for L in (1, 0):
        p = ab("Unity/Build/Design/29R01/unity/timing/f_final_lo%d/ds29_render_report.json" % L)
        if os.path.exists(p):
            r = json.load(open(p, encoding="utf-8"))
            out["pos_lo_%d" % L] = dict(posLoUsed=r.get("posLoUsed"), wave_ms={t["view"]: t["waveMs"] for t in r["timing"]},
                                      frames=r["timing"][0]["frames"] if r["timing"] else None)
    if out:
        out["note_ja"] = ("DS29Render の おおよその GPU 時間（1920 × 1080・MSAA 8x、600 コマ × 3 回の中央値、主役波を描く・隠すの差。壁時計で GPU のタイマーではない。"
                          "設計29 の記録どおり同じ組でも回によって約 50% 揺れる）。精度の層の有無の差はこの揺れの内。PC の片目で HMD 実機ではない")
    return out or None


def cmd_summary(a):
    def lj(p):
        p = ab(p)
        return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
    gpu = lj(a.gpu)
    r28 = lj(a.regress28)
    r27 = lj(a.regress27)
    rep = lj(a.report)
    tst = lj(a.tstar)
    tst_ref = lj(a.tstar_ref)
    mem = None
    if rep:
        MiB = 2 ** 20
        keypose = rep["positionGpuBytes"] + rep.get("posLoGpuBytes", 0) + rep["whiteGpuBytes"]
        mem = dict(position_16bit_mib=rep["positionGpuBytes"] / MiB, position_lo_mib=rep.get("posLoGpuBytes", 0) / MiB, twhite_mib=rep["whiteGpuBytes"] / MiB,
                   keypose_total_mib=keypose / MiB, mesh_vertex_index_mib=(rep["meshVertexBufferBytes"] + rep["meshIndexBufferBytes"]) / MiB,
                   colour_zone_texture_mib=rep["sdfTextureBytes"] / MiB,
                   driver_increase_keypose_mib=(rep["driverBytesAfterKeypose"] - rep["driverBytesAfterSurface"]) / MiB,
                   budget_mib=512, keypose_within_budget=keypose / MiB <= 512,
                   readable_cpu_copy=False,
                   note_ja=("位置（16 bit × 3 を詰めた）と精度の層（RGBA8 をファイルのまま）と T_white は GraphicsBuffer（StructuredBuffer、GPU だけ）で、"
                            "CPU の写しを残さない（読み取り不可）。json の gpu_estimate の fine_texture2darray_readable_mib（531.74）は、"
                            "読み取り可能な Texture2DArray の見積もりで、この再生器の形ではない。driver_increase_keypose_mib は Unity の割り当ての数の増え（頼んだ大きさの確かめ）"))
    tcmp = None
    if tst and tst_ref:
        rows = []
        worst = 0.0
        a_ = {(r["item"], r["measure"]): r for r in tst["boundaries_vs_28r01"]}
        for r in tst_ref["boundaries_vs_28r01"]:
            k = (r["item"], r["measure"])
            if k in a_:
                d = a_[k]["ds27_max_px"] - r["ds27_max_px"]
                worst = max(worst, abs(d))
                rows.append(dict(item=r["item"], measure=r["measure"], fine_px=a_[k]["ds27_max_px"], r16_px=r["ds27_max_px"], diff_px=round(d, 4),
                                 fine_verdict=a_[k]["ds27_verdict"], r16_verdict=r["ds27_verdict"]))
        s_ = {r["item"]: r for r in tst["silhouettes_vs_26r01_28r01"]}
        srows = []
        for r in tst_ref["silhouettes_vs_26r01_28r01"]:
            b = s_.get(r["item"])
            if not b:
                continue
            dm = None if b["ds27_max_px"] is None or r["ds27_max_px"] is None else b["ds27_max_px"] - r["ds27_max_px"]
            dp = None if b["ds27_p95_px"] is None or r["ds27_p95_px"] is None else b["ds27_p95_px"] - r["ds27_p95_px"]
            for v in (dm, dp):
                if v is not None:
                    worst = max(worst, abs(v))
            srows.append(dict(item=r["item"], fine_max_px=b["ds27_max_px"], r16_max_px=r["ds27_max_px"], fine_p95_px=b["ds27_p95_px"], r16_p95_px=r["ds27_p95_px"],
                              diff_max_px=dm, diff_p95_px=dp))
        vchg = {k: (tst["summary_verdicts_ds27"].get(k), v) for k, v in tst_ref["summary_verdicts_ds27"].items() if tst["summary_verdicts_ds27"].get(k) != v}
        tcmp = dict(ref_ja="設計28修正01 の F_final の Unity の t*（16 bit だけの読み、Unity/Build/Design/28R01F/unity/F_final/ds27_tstar_remeasure.json）",
                    boundaries=rows, silhouettes=srows, worst_abs_diff_px=round(worst, 4), criterion_px=0.5, passed=worst <= 0.5,
                    verdicts_changed=vchg, fine_worst_vs_28r01_px=tst["worst_abs_diff_px"], r16_worst_vs_28r01_px=tst_ref["worst_abs_diff_px"])
    shc = lj(a.shader_check)
    acc = dict(
        gpu_vs_numpy_le_0p25mm=None if gpu is None else gpu["passed"],
        shader_variants_compile_incl_spi=None if shc is None else bool(shc["allCompiled"] and shc["allStereoOutput"] and shc["computeErrorCount"] == 0),
        old_28_pixel_identical=None if r28 is None else r28["pixel_identical"],
        old_27_pixel_identical=None if r27 is None else r27["pixel_identical"],
        keypose_memory_le_512mib=None if mem is None else mem["keypose_within_budget"],
        record_only_tstar_fine_vs_16bit_render_le_0p5px=None if tcmp is None else tcmp["passed"],
        note_ja=("record_only_… は記録のみ：精度の層つきの t* と、同じ古い焼き込み（28修正01）の 16 bit だけの t*（設計28修正01 の F_final）の差。"
                 "どちらも古い焼き込みを K*′ の形に貼ったままで大きく不合格なので、計画 §2.0 の回帰（K*′ の値と ±0.5 px）の判定は焼き直しの後に行う"))
    res = dict(schema="GreatWave.DS29R01.unity_check/1", number="設計29修正01 Part A（再生器が精度の層を読む）",
               acceptance=acc, memory=mem, gpu=None if gpu is None else {k: v for k, v in gpu.items() if k != "rows"},
               regress_d28=None if r28 is None else {k: v for k, v in r28.items() if k != "files"},
               regress_d27=None if r27 is None else {k: v for k, v in r27.items() if k != "files"},
               tstar_fine_vs_16bit=tcmp,
               shader_check=None if shc is None else {k: shc[k] for k in ("allCompiled", "allStereoOutput", "computeErrorCount", "noteJa")},
               timing=timing(),
               record=record(a),
               render_report=None if rep is None else {k: rep[k] for k in ("name", "package", "posLoUsed", "posLoFile", "posLoSha256", "posLoGpuBytes", "positionGpuBytes",
                                                                            "whiteGpuBytes", "layers", "passed", "protectedUnchanged", "totalSeconds", "warpFile", "stillNames", "stillTau") if k in rep})
    save(ab(a.out), res)
    print(json.dumps(acc, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    g = sp.add_parser("gpu")
    g.add_argument("--run", required=True)
    g.add_argument("--package", required=True)
    g.add_argument("--range", default="-6,0")
    g.add_argument("--out", required=True)
    r = sp.add_parser("regress")
    r.add_argument("--new", required=True)
    r.add_argument("--ref", required=True)
    r.add_argument("--report", default="ds29_render_report.json")
    r.add_argument("--out", required=True)
    s = sp.add_parser("summary")
    s.add_argument("--gpu", default="Unity/Build/Design/29R01/unity/check_gpu_f_final.json")
    s.add_argument("--regress28", default="Unity/Build/Design/29R01/unity/check_regress_d28.json")
    s.add_argument("--regress27", default="Unity/Build/Design/29R01/unity/check_regress_d27.json")
    s.add_argument("--report", default="Unity/Build/Design/29R01/unity/f_final/ds29_render_report.json")
    s.add_argument("--tstar", default="Unity/Build/Design/29R01/unity/f_final/ds27_tstar_remeasure.json")
    s.add_argument("--tstar-ref", default="Unity/Build/Design/28R01F/unity/F_final/ds27_tstar_remeasure.json")
    s.add_argument("--shader-check", default="Unity/Build/Design/29R01/unity/ds29r01_shader_check.json")
    s.add_argument("--out", default="Unity/Build/Design/29R01/unity/ds29r01_unity_check.json")
    a = ap.parse_args()
    {"gpu": cmd_gpu, "regress": cmd_regress, "summary": cmd_summary}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
