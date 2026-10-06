# -*- coding: utf-8 -*-
"""組み込みの準備：方法 A の 240 × 400 の網目の並び → 作品の keypose の包み（書式 GreatWave.DS27.keypose/1、拡張 pos_lo_rgba8/1）と
t* の層の .gwb（GWW0 版 1。DS27KeyposePlayer・DS30SheetPlayer が三角形と頂点の数をここから取る）。
作品の包み（Unity/Build/Polish/sample06/...）は読まない・変えない。書く場所は Unity/Build/FLIP37/integration_prep/keypose/<seq>/ だけ。

- 層＝変換したコマ（方法 A の sheet_sim_XXXX.npy、計算の座標）を p2_common.place と同じ置き方で Unity の座標にしたもの。
- knot_tau＝t − t*（最後の層が t* = 0）。t* は引数（既定は最後のコマ）。
- 波の枠の原点 O(τ)＝主な行の頂（高さ 0 に下ろした点）。層の間は線形、480 Hz の表。位置は O(τ) からの局所座標（軸はワールド）。
- 位置：RGBA16 UNORM（(位置 − bbox_min)/bbox_size·65535）、精度の層 RGBA8（丸めの残り）。作品の包みと同じ式。
- T_white：その頂点が初めて「白の印 whiteSD > 0 かつ その行の whiteOn」になった τ（ならなければ 1e9）。
- 確かめ：書いたファイルを Python で復号して、Hermite で層の間を補間した位置と元の層の差（量子化の誤差）を測る。
使い方：py -3.10 integ_keypose.py <seq> [--tstar <t>]
"""
import os, sys, glob, json, struct
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integ_common as C
from integ_convert import SEQS, place_fn


def main():
    seq = sys.argv[1]
    cfg = SEQS[seq]
    sd = C.OUT + "/" + seq
    od = C.OUT + "/keypose/" + seq
    os.makedirs(od, exist_ok=True)
    fs = sorted(glob.glob(sd + "/sheet_sim_*.npy"))
    fr = [int(os.path.basename(f)[10:14]) for f in fs]
    ts = np.array([(f - 1) / 24.0 for f in fr])
    tstar = float(sys.argv[sys.argv.index("--tstar") + 1]) if "--tstar" in sys.argv else float(ts[-1])
    keep = ts <= tstar + 1e-6
    fs = [f for f, k in zip(fs, keep) if k]; fr = [f for f, k in zip(fr, keep) if k]; ts = ts[keep]
    tstar = float(ts[-1])          # t* は選んだ時刻以下で一番近いコマの時刻そのもの
    place, M, O, T, E = place_fn(cfg)
    zrows = cfg["zc"] + np.linspace(cfg["c"][0], cfg["c"][1], C.NV)
    mrow = int(np.argmin(np.abs(zrows - cfg["zc"])))
    L = len(fs)
    W = np.zeros((L, C.NV, C.NU, 3))
    Org = np.zeros((L, 3))
    Twhite = np.full(C.NV * C.NU, 1e9)
    for i, (f, fi) in enumerate(zip(fs, fr)):
        G = np.load(f).astype(np.float64)
        Gu = place(G)
        a = np.load(sd + "/sheet_attr_%04d.npz" % fi)
        top = place(np.array([[a["x_top"][mrow], 0.0, zrows[mrow]]]))[0]
        Org[i] = top
        W[i] = Gu - top
        white = (a["whiteSD"] > 0) & (a["whiteOn"][:, None] > 0)
        newly = white.ravel() & (Twhite >= 1e9)
        Twhite[newly] = ts[i] - tstar
    tau = ts - tstar
    tau[-1] = 0.0
    bmin = W.reshape(-1, 3).min(0) - 0.01
    bsz = W.reshape(-1, 3).max(0) + 0.01 - bmin
    u = (W - bmin) / bsz * 65535.0
    q16 = np.clip(np.round(u), 0, 65535).astype(np.uint16)
    e = u - q16
    lo = np.clip(np.round((e + 0.5) * 255.0), 0, 255).astype(np.uint8)
    pos = np.concatenate([q16, np.full(q16.shape[:-1] + (1,), 65535, np.uint16)], -1)
    pos_lo = np.concatenate([lo, np.full(lo.shape[:-1] + (1,), 255, np.uint8)], -1)
    pp, pl, tw = od + "/ds27_pos_rgba16.bin", od + "/ds27_pos_lo_rgba8.bin", od + "/ds27_twhite_r32f.bin"
    pos.astype("<u2").tofile(pp)
    pos_lo.tofile(pl)
    Twhite.astype("<f4").tofile(tw)
    # 480 Hz の原点の表
    ft = np.round(np.arange(tau[0], 0.0 + 1e-9, 1.0 / 480.0), 9)
    ft[-1] = 0.0
    fo = np.stack([np.interp(ft, tau, Org[:, k]) for k in range(3)], 1)
    # t* の層の .gwb（頂点はワールドの座標、三角形は格子）
    tri = C.grid_triangles().astype(np.int32)
    Xs = (W[-1] + Org[-1]).reshape(-1, 3).astype(np.float32)
    jj, rr = np.meshgrid(np.arange(C.NU), np.arange(C.NV))
    uv = np.stack([jj.ravel() / (C.NU - 1), rr.ravel() / (C.NV - 1)], 1).astype(np.float32)
    gwb = od + "/tstar_sheet.gwb"
    with open(gwb, "wb") as fo_:
        fo_.write(b"GWW0" + struct.pack("<iiiifii", 1, C.NU, C.NV, 1, 30.0, 0, len(tri)))
        for arr in (uv, uv, tri, Xs):
            fo_.write(np.ascontiguousarray(arr).tobytes())
    # 確かめ：復号と Hermite（節点の間の中ほど）
    dec = bmin + (pos[..., :3].astype(np.float64) + pos_lo[..., :3] / 255.0 - 0.5) / 65535.0 * bsz
    err_layers = float(np.abs(dec - W).max())
    meta = {
        "schema": "GreatWave.DS27.keypose/1",
        "number": "FLIP37 組み込みの準備（独立の試作）：流体の水面を方法 A（行ごとに切って 240×400 へ並べ直す）で写した試験の包み。作品へは入れていない",
        "version": "flip37_prep_" + seq, "layers": L, "rows": C.NV, "cols": C.NU,
        "bbox_min": bmin.round(6).tolist(), "bbox_size": bsz.round(6).tolist(), "knot_tau": [float(round(x, 9)) for x in tau],
        "t_star_layer": L - 1,
        "frame": {"tau": [float(x) for x in ft], "origin": fo.round(7).tolist(), "hz": 480,
                  "note_ja": "波の枠の原点 O(τ)＝主な行（c = 0）の頂の位置を高さ 0 に下ろした点（流体の頂の動きそのもの。作品の O(τ) の式は使わない）。層の間は線形。"},
        "pos_file": os.path.basename(pp), "pos_sha256": C.sha256(pp), "pos_bytes": os.path.getsize(pp),
        "pos_format_ja": "RGBA16 UNORM、層 × 行 × 列 × 4、リトルエンディアン。xyz = (位置 − bbox_min)/bbox_size·65535、A = 65535。位置は波の枠の局所座標（ワールド − O(τ)、軸はワールド）。作品の包みと同じ。",
        "extensions": ["pos_lo_rgba8/1"], "pos_lo_file": os.path.basename(pl), "pos_lo_sha256": C.sha256(pl), "pos_lo_bytes": os.path.getsize(pl),
        "twhite_file": os.path.basename(tw), "twhite_sha256": C.sha256(tw), "twhite_bytes": os.path.getsize(tw), "twhite_never": 1e9,
        "twhite_summary": {"vertices_white_before_tstar": int((Twhite < 1e9).sum()), "vertices_never": int((Twhite >= 1e9).sum())},
        "interpolation_ja": "節点 i と i+1 の間の τ の 3 次 Hermite（作品の包みと同じ）。",
        "source": {"seq": seq, "label_ja": cfg["label_ja"], "frames": [os.path.basename(f) for f in fs], "t_star_s": tstar,
                   "placement": {"anchor": cfg["anchor"], "psi_deg": cfg["psi"], "s": cfg["s"]}},
        "tstar_gwb": os.path.basename(gwb), "tstar_gwb_sha256": C.sha256(gwb),
        "check": {"decode_max_err_m": err_layers},
        "gpu_estimate": {"layer_mib": C.NV * C.NU * 8 / 2 ** 20, "texture2darray_mib": L * C.NV * C.NU * 8 / 2 ** 20,
                         "fine_texture2darray_mib": L * C.NV * C.NU * 12 / 2 ** 20},
    }
    # 作品の材質の keypose の道（PL29UkiyoeHero が UV3〜UV5 へ入れる 12 個の float32）：t* の層の方法 A の属性から
    #   A = (F, hrel, u, w)、B = (|∇w|, hrow, Lq, 0)、C = (t* の法線 xyz, whiteSD)。頂点の番号は行 × 400 ＋ 列（.gwb と同じ）
    pk = C.OUT + "/pkg/%s/sheet" % seq
    idx = json.load(open(pk + "/index.json", encoding="utf8"))
    kk = int(np.argmin([abs(f["t"] - tstar) for f in idx["frames"]]))
    n = C.NV * C.NU
    b = np.fromfile(pk + "/" + idx["frames"][kk]["bin"], dtype=np.float32, count=n * 22)
    o = 0; ch = {}
    for name, k in (("position", 3), ("normal", 3), ("uv3", 4), ("uv4", 4), ("uv5", 4), ("uv6", 4)):
        ch[name] = b[o:o + n * k].reshape(n, k); o += n * k
    lam = ch["uv6"][:, 2]
    attr = np.zeros((n, 12), np.float32)
    attr[:, 0:4] = ch["uv3"]
    attr[:, 4] = ch["uv4"][:, 0] * lam
    attr[:, 5] = ch["uv4"][:, 1]
    attr[:, 6] = ch["uv4"][:, 2]
    attr[:, 8:11] = ch["normal"]
    attr[:, 11] = ch["uv5"][:, 2]
    ap = od + "/f37_hero_attr_f32.bin"
    attr.tofile(ap)
    meta["hero_attr12"] = {"file": os.path.basename(ap), "sha256": C.sha256(ap), "from_frame_t": idx["frames"][kk]["t"],
                           "note_ja": "PL29UkiyoeHero の 12 個（A=(F,hrel,u,w)、B=(|∇w|,hrow,Lq,0)、C=(t* の法線,whiteSD)）。t* の層の方法 A の属性"}
    json.dump(meta, open(od + "/ds27_keypose.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(json.dumps({"layers": L, "tau0": float(tau[0]), "decode_max_err_m": err_layers, "white_vertices": meta["twhite_summary"],
                      "MB": (os.path.getsize(pp) + os.path.getsize(pl)) / 1e6}, ensure_ascii=False))


if __name__ == "__main__":
    main()
