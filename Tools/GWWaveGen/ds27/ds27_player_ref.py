# -*- coding: utf-8 -*-
"""設計27：DS27 keypose パッケージの numpy 参照（Unity の DS27KeyposePlayer・DS27KeyposeCore.cginc と同じ式）と、
Unity の読み戻し（DS27Formation の gpu_capture）との照合。

パッケージ（生成器と再生側の約束。Unity/Build/Design/27/<版>/、版は art_on・art_off）：
  ds27_pos_rgba16.bin   RGBA16 UNORM、並びは 層 × 行(240) × 列(400) × 4（美術優先30 の af30_pos_rgba16.bin と同じ）。
                        xyz は外接箱で正規化（位置 = bbox_min + q/65535 × bbox_size）、A = 65535。
                        位置は波の枠の局所座標 = ワールド − O(τ)（O は波の枠の原点。平行移動だけで、軸はワールドの軸）。
  ds27_keypose.json     {"layers", "rows": 240, "cols": 400, "bbox_min": [3], "bbox_size": [3],
                         "knot_tau": [層]（秒、狭義単調増加、不等間隔でよい、最後 = 0.0 = t*）,
                         "frame": {"tau": [...], "origin": [[x, y, z], ...]}（240 Hz 以上の密な標本、間は線形補間）,
                         "pos_sha256", "twhite_file", "twhite_sha256"}
  ds27_twhite_r32f.bin  R32F、行 × 列、T_white（τ の秒）。τ ≥ T_white で白。+1e9 は t* までに白にならない。
補間（numpy とシェーダーで同じ）：節点 i と i+1 の間の τ の 3 次 Hermite。傾き m_i = (p_{i+1} − p_{i−1})/(τ_{i+1} − τ_{i−1})
（両端は片側）。節点が等間隔なら一様の Catmull-Rom と同じ。節点の範囲の外は端の節点のまま（枠の原点も端の標本のまま）。
ワールド = O(τ) + 局所。法線は K* の格子の三角形（四角ごとに (r,c)(r+1,c)(r,c+1) と (r,c+1)(r+1,c)(r+1,c+1)）の
面の法線（正規化しない外積）の和を正規化したもの（美術優先30 の vertex_normals と同じ）。

使い方（リポジトリの根で）:
    py -3.10 Tools/GWWaveGen/ds27/ds27_player_ref.py check --package <版のフォルダー> --capture <出力>/gpu_capture [--report <json>]
      読み戻した位置（ワールド）と法線を、同じ τ の numpy の値と比べる（合格：位置の差 ≤ 2 cm、t* で K* との差 ≤ 量子化）。
    py -3.10 Tools/GWWaveGen/ds27/ds27_player_ref.py info --package <版のフォルダー>
numpy だけを使う。
"""
import argparse
import hashlib
import json
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
KSTAR_GWB = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01", "kstar", "kstar_a45.gwb")
KSTAR_GWB_SHA256 = "e9bc3572590b5b237ddd302fca64f54f2d325813ad787f20e4d7524b6b84cd26"
NEVER = 1.0e8   # これ以上の T_white は「t* までに白にならない」（パッケージの約束は +1e9）
DEGENERATE_M2 = 1.0e-6   # 面の法線の和の長さ（m²）がこれ以下の頂点は、法線が決まらないので法線の照合から外す（数を記録する）


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- 補間の重み（C# の DS27KeyposePlayer.Weights と同じ式）
def hermite_weights(knots, tau):
    """τ の補間に使う 4 つの層の添字と重み（非一様の節点の Hermite、傾きは中心差分、端は片側）。範囲の外は端の層。"""
    n = len(knots)
    if tau <= knots[0]:
        return (0, 0, 0, 0), (0.0, 1.0, 0.0, 0.0)
    if tau >= knots[-1]:
        return (n - 1, n - 1, n - 1, n - 1), (0.0, 1.0, 0.0, 0.0)
    i1 = int(np.searchsorted(knots, tau, side="right") - 1)
    i1 = min(i1, n - 2)
    i2 = i1 + 1
    i0 = max(i1 - 1, 0)
    i3 = min(i2 + 1, n - 1)
    t1, t2 = knots[i1], knots[i2]
    D = t2 - t1
    s = (tau - t1) / D
    h00 = 2 * s ** 3 - 3 * s ** 2 + 1
    h10 = s ** 3 - 2 * s ** 2 + s
    h01 = -2 * s ** 3 + 3 * s ** 2
    h11 = s ** 3 - s ** 2
    w = [0.0, h00, h01, 0.0]
    if i0 == i1:            # m1 = (p2 − p1)/D
        w[2] += h10
        w[1] -= h10
    else:                   # m1 = (p2 − p0)/(t2 − t0)
        f = h10 * D / (t2 - knots[i0])
        w[2] += f
        w[0] -= f
    if i3 == i2:            # m2 = (p2 − p1)/D
        w[2] += h11
        w[1] -= h11
    else:                   # m2 = (p3 − p1)/(t3 − t1)
        f = h11 * D / (knots[i3] - t1)
        w[3] += f
        w[1] -= f
    return (i0, i1, i2, i3), tuple(float(x) for x in w)


# ---------------------------------------------------------------- 格子の法線（K* の三角形の並び）
def grid_triangles(nv, nu):
    r, c = np.meshgrid(np.arange(nv - 1), np.arange(nu - 1), indexing="ij")
    a = (r * nu + c).ravel()
    b = ((r + 1) * nu + c).ravel()
    cc = (r * nu + c + 1).ravel()
    d = ((r + 1) * nu + c + 1).ravel()
    t1 = np.stack([a, b, cc], 1)
    t2 = np.stack([cc, b, d], 1)
    return np.stack([t1, t2], 1).reshape(-1, 3)   # 四角ごとに T1, T2（K* の .gwb と同じ並び）


def vertex_normals(V, tris, with_len=False):
    a, b, c = V[tris[:, 0]], V[tris[:, 1]], V[tris[:, 2]]
    fn = np.cross(b - a, c - a)
    n = np.zeros_like(V)
    for k in range(3):
        np.add.at(n, tris[:, k], fn)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    nn = n / np.maximum(ln, 1e-20)
    return (nn, ln[:, 0]) if with_len else nn


def read_kstar(path=KSTAR_GWB, check=True):
    b = open(path, "rb").read()
    if b[:4] != b"GWW0":
        raise SystemExit("K* の .gwb が GWW0 ではありません")
    if check:
        h = hashlib.sha256(b).hexdigest()
        if h != KSTAR_GWB_SHA256:
            raise SystemExit("K* の .gwb の SHA-256 が記録と違います: " + h)
    ver, nu, nv, nf = struct.unpack("<4i", b[4:20])
    ntri = struct.unpack("<i", b[28:32])[0]
    n = nu * nv
    o = 32 + n * 16
    tris = np.frombuffer(b, np.int32, ntri * 3, o).reshape(-1, 3).copy()
    o += ntri * 12
    X = np.frombuffer(b, np.float32, n * 3, o).reshape(n, 3).astype(np.float64)
    return nu, nv, tris, X


# ---------------------------------------------------------------- パッケージ
class Package:
    def __init__(self, d, verify=True):
        self.dir = os.path.abspath(d)
        self.meta = m = load_json(os.path.join(self.dir, "ds27_keypose.json"))
        self.L, self.R, self.C = int(m["layers"]), int(m["rows"]), int(m["cols"])
        self.N = self.R * self.C
        self.pos_path = os.path.join(self.dir, "ds27_pos_rgba16.bin")
        raw = np.fromfile(self.pos_path, "<u2")
        if raw.size != self.L * self.N * 4:
            raise SystemExit("ds27_pos_rgba16.bin の大きさが層 × 行 × 列 × 4 と合いません: %d" % raw.size)
        self.q = raw.reshape(self.L, self.N, 4)
        self.lo = np.asarray(m["bbox_min"], np.float64)
        self.size = np.asarray(m["bbox_size"], np.float64)
        self.knots = np.asarray(m["knot_tau"], np.float64)
        if self.knots.size != self.L or np.any(np.diff(self.knots) <= 0) or self.knots[-1] != 0.0:
            raise SystemExit("knot_tau は層の数だけの狭義単調増加で、最後が 0.0 のはずです。")
        fr = m["frame"]
        self.ftau = np.asarray(fr["tau"], np.float64)
        self.forg = np.asarray(fr["origin"], np.float64).reshape(-1, 3)
        if self.ftau.size != self.forg.shape[0] or self.ftau.size < 2 or np.any(np.diff(self.ftau) <= 0):
            raise SystemExit("frame の tau と origin が合わないか、tau が単調増加でありません。")
        self.tw_path = os.path.join(self.dir, m["twhite_file"])
        self.tw = np.fromfile(self.tw_path, "<f4")
        if self.tw.size != self.N:
            raise SystemExit("T_white の大きさが行 × 列と合いません: %d" % self.tw.size)
        self.sha_ok = None
        if verify:
            sp, st = sha256_file(self.pos_path), sha256_file(self.tw_path)
            self.sha_ok = (sp == m["pos_sha256"]) and (st == m["twhite_sha256"])
            if not self.sha_ok:
                raise SystemExit("パッケージの SHA-256 が JSON と違います（位置 %s、T_white %s）" % (sp, st))
        self.alpha_ok = bool(np.all(self.q[..., 3] == 65535))

    def layer_local(self, k):
        return self.lo[None, :] + self.q[k, :, :3].astype(np.float64) / 65535.0 * self.size[None, :]

    def local(self, tau):
        idx, w = hermite_weights(self.knots, tau)
        P = np.zeros((self.N, 3))
        for q in range(4):
            if w[q] != 0.0:
                P += w[q] * self.layer_local(idx[q])
        return P, idx, w

    def origin(self, tau):
        return np.array([np.interp(tau, self.ftau, self.forg[:, a]) for a in range(3)])

    def world(self, tau):
        P, idx, w = self.local(tau)
        return P + self.origin(tau)[None, :], idx, w

    def quant_max_m(self):
        """量子化の 1 段の半分の対角（位置の丸めの差の上限）。"""
        return float(np.linalg.norm(0.5 * self.size / 65535.0))

    def info(self):
        m = self.meta
        return {"dir": self.dir, "layers": self.L, "rows": self.R, "cols": self.C, "knot_tau": self.knots.tolist(),
                "frame_samples": int(self.ftau.size), "frame_tau_range": [float(self.ftau[0]), float(self.ftau[-1])],
                "frame_rate_hz_min": float(1.0 / np.max(np.diff(self.ftau))), "bbox_min": self.lo.tolist(), "bbox_size": self.size.tolist(),
                "quant_half_step_diag_m": self.quant_max_m(), "alpha_all_65535": self.alpha_ok,
                "twhite_finite_range": [float(self.tw[self.tw < NEVER].min()) if np.any(self.tw < NEVER) else None,
                                        float(self.tw[self.tw < NEVER].max()) if np.any(self.tw < NEVER) else None],
                "twhite_never_count": int(np.sum(self.tw >= NEVER)),
                "pos_bytes": os.path.getsize(self.pos_path), "gpu_bytes_packed_3x16": self.L * self.N * 6,
                "gpu_bytes_rgba16_texture": self.L * self.N * 8, "twhite_bytes": self.N * 4, "sha_ok": self.sha_ok}


# ---------------------------------------------------------------- 照合
def check(args):
    pk = Package(args.package)
    rep_path = os.path.join(args.capture, "ds27_gpu_capture.json")
    cap = load_json(rep_path)
    nu, nv, tris, Xk = read_kstar()
    if nu != pk.C or nv != pk.R:
        raise SystemExit("K* の格子とパッケージの格子が合いません。")
    gtris = grid_triangles(nv, nu)
    same_tris = bool(np.array_equal(gtris, tris))
    rows = []
    worst_pos = 0.0
    worst_nrm = 0.0
    worst_nrm_big = 0.0
    tstar = None
    for rec in cap["captures"]:
        tau = float(rec["tau"])
        fn = os.path.join(args.capture, rec["file"])
        g = np.fromfile(fn, "<f4").reshape(-1, 6).astype(np.float64)   # 頂点ごとに xyz 位置（ワールド）、xyz 法線
        gp, gn = g[:, :3], g[:, 3:6]
        W, idx, w = pk.world(tau)
        dp = np.linalg.norm(gp - W, axis=1)
        L, _, _ = pk.local(tau)
        n_ref, n_len = vertex_normals(L, tris, with_len=True)
        ok = n_len > DEGENERATE_M2   # 面の法線の和が 0（周りの三角形がつぶれた頂点）は法線が決まらないので比べない
        cosang = np.clip(np.sum(gn * n_ref, 1) / np.maximum(np.linalg.norm(gn, axis=1), 1e-20), -1, 1)
        ang_all = np.degrees(np.arccos(cosang))
        ang = ang_all[ok]
        big = n_len > 1.0e-4   # K* の唇の最小の三角形（7.7e-4 m²）の頂点の和より小さい、つぶれかけの頂点を除いた値も記録する
        o_gpu = np.asarray(rec.get("origin", [np.nan] * 3), np.float64)
        o_ref = pk.origin(tau)
        r = {"tau": tau, "slices": list(idx), "weights_numpy": list(w), "weights_unity": rec.get("weights"),
             "slices_unity": rec.get("slices"),
             "pos_err_max_m": float(dp.max()), "pos_err_p99_m": float(np.percentile(dp, 99)), "pos_err_argmax_vertex": int(dp.argmax()),
             "normal_err_max_deg": float(ang.max()), "normal_err_p99_deg": float(np.percentile(ang, 99)),
             "normal_degenerate_vertices": int((~ok).sum()),
             "normal_err_max_deg_sum_gt_1e-4": float(ang_all[big].max()), "normal_small_sum_vertices_le_1e-4": int((~big).sum()),
             "origin_err_m": float(np.linalg.norm(o_gpu - o_ref)) if np.all(np.isfinite(o_gpu)) else None}
        worst_pos = max(worst_pos, r["pos_err_max_m"])
        worst_nrm = max(worst_nrm, r["normal_err_max_deg"])
        worst_nrm_big = max(worst_nrm_big, r["normal_err_max_deg_sum_gt_1e-4"])
        if tau == 0.0:
            dk = np.linalg.norm(gp - Xk, axis=1)
            tstar = {"gpu_vs_kstar_max_m": float(dk.max()), "numpy_vs_kstar_max_m": float(np.linalg.norm(W - Xk, axis=1).max()),
                     "quant_half_step_diag_m": pk.quant_max_m()}
            r["kstar"] = tstar
        rows.append(r)
    res = {"schema": "GreatWave.DS27.playback_check/1", "package": pk.info(), "capture_report": os.path.abspath(rep_path),
           "grid_triangles_equal_kstar": same_tris, "captures": rows, "count": len(rows),
           "worst_pos_err_m": worst_pos, "worst_normal_err_deg": worst_nrm, "worst_normal_err_deg_sum_gt_1e-4": worst_nrm_big,
           "criterion_pos_m": 0.02, "pass_pos": worst_pos <= 0.02,
           "tstar": tstar,
           "pass_tstar": (tstar is not None and tstar["gpu_vs_kstar_max_m"] <= max(0.0012 + 1e-4, tstar["quant_half_step_diag_m"] + 1e-4)),
           "note_ja": "位置：Unity の DS27KeyposeCapture（頂点シェーダーと同じ関数）の読み戻しと、numpy の Hermite（float64）の差。"
                      "法線：シェーダーの格子の 6 三角形の和と、numpy の vertex_normals（K* の三角形）の角度の差（面の法線の和の長さが 1e-6 m² 以下のつぶれた頂点は除き、数を記録）。"
                      "t*：τ = 0 の読み戻しと K* の .gwb の頂点の差（量子化の上限の内なら合格）。"}
    res["pass"] = bool(res["pass_pos"] and res["pass_tstar"] and same_tris)
    out = args.report or os.path.join(os.path.dirname(os.path.abspath(args.capture)), "ds27_playback_check.json")
    save_json(out, res)
    print("DS27_CHECK captures=%d worst_pos_err=%.6f m worst_normal_err=%.4f deg (|n|>1e-4: %.4f deg) tstar_vs_kstar=%s pass=%s -> %s" % (
        len(rows), worst_pos, worst_nrm, worst_nrm_big, None if tstar is None else "%.6f m" % tstar["gpu_vs_kstar_max_m"], res["pass"], out))
    return 0 if res["pass"] else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("check")
    a.add_argument("--package", required=True)
    a.add_argument("--capture", required=True)
    a.add_argument("--report")
    b = sub.add_parser("info")
    b.add_argument("--package", required=True)
    args = ap.parse_args()
    if args.cmd == "check":
        sys.exit(check(args))
    print(json.dumps(Package(args.package).info(), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
