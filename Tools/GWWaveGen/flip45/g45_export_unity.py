# -*- coding: utf-8 -*-
"""FLIP45：計算の面（記録 R5、g45_run.py が毎コマ書く s_FFFFF.gw45s）を Unity へ渡すクリップにまとめ、読み戻して確かめる（py -3.10、numpy だけ）。
2026-10-12 進行役が新しく書いた（計画 plan_ja.md §9。読み込みの計画は Unity/Build/FLIP45/unity_loader/loader_plan_ja.md）。
1 コマの形 GW45SRF1（little endian。g45_run.write_surface が書く）：
  頭 96 バイト：0 magic "GW45SRF1"、8 uint32 版 1、12 uint32 頭の長さ 96、16 float64 時刻 t（s）、24 int32 コマ、28 uint32 点の数 nv、
               32 uint32 三角形の数 nt、36 float32×3 箱の下の端（m、計画の座標 x・上・横）、48 float32×3 箱の上の端、60 float32 静かな水面のずれ（m）、
               64 float32 予備、68〜95 は 0。
  本体：位置 uint16×3×nv（箱の中を 0〜65535 に）→ 法線 uint16×2×nv（8 方向の写像、0〜65535 を −1〜1 に）→ 速さ v float16×3×nv（m/s）
       → 添字 uint32×3×nt。本体の位置・法線・速さの合計は 16 nv バイトなので、添字は 4 バイトにそろう。
  座標：計画の座標（x＝波の進む向き、上＝静かな水面 0 から、横＝対称の面 0 から）。Unity では x を前、上を y、横を z（RT48 と同じ向き）に置き、
       横を −z に写した物をもう一度描く（計算の対称の仮定そのもの。計画 §9）。
クリップ GW45CLP1（このプログラムが書く）：頭 64 バイト（"GW45CLP1"、版 1、コマの数 n、fps float64、最初の時刻 float64、最初のコマ int32、
  予備）→ 目次 n × (uint64 位置, uint32 長さ, uint32 予備) → 各コマの GW45SRF1 をそのまま並べる。manifest.json に同じ情報と SHA-256。
使い方：
  py -3.10 g45_export_unity.py clip <run_dir> <out_dir> [--from F] [--to F]   → out_dir/clip.gw45c・manifest.json・check.json（読み戻しの確かめ）
  py -3.10 g45_export_unity.py check <file.gw45s>
"""
import sys, os, json, struct, glob, time, hashlib
import numpy as np

HEAD = struct.Struct("<8sIIdiIIffffffff")
HEAD_BYTES = 96


def read_frame_bytes(b):
    magic, ver, hb, t, fr, nv, nt, x0, y0, z0, x1, y1, z1, off, _r = HEAD.unpack_from(b, 0)
    if magic != b"GW45SRF1":
        raise ValueError("GW45SRF1 でない")
    o = hb
    q = np.frombuffer(b, np.uint16, nv * 3, o).reshape(nv, 3); o += nv * 6
    n2 = np.frombuffer(b, np.uint16, nv * 2, o).reshape(nv, 2); o += nv * 4
    v = np.frombuffer(b, np.float16, nv * 3, o).reshape(nv, 3); o += nv * 6
    tri = np.frombuffer(b, np.uint32, nt * 3, o).reshape(nt, 3); o += nt * 12
    lo = np.array([x0, y0, z0]); hi = np.array([x1, y1, z1])
    P = q.astype(np.float64) / 65535.0 * (hi - lo) + lo
    N = oct_decode(n2)
    return dict(version=ver, t=t, frame=fr, nv=nv, nt=nt, lo=lo, hi=hi, still_offset=off, P=P, N=N, v=v.astype(np.float32), tri=tri,
                bytes=o, quant_half_step_m=float(np.max(hi - lo) / 65535.0 / 2.0))


def oct_decode(n2):
    f = n2.astype(np.float64) / 65535.0 * 2.0 - 1.0
    x, y = f[:, 0], f[:, 1]
    z = 1.0 - np.abs(x) - np.abs(y)
    t = np.clip(-z, 0, None)
    x = np.where(x >= 0, x - t, x + t); y = np.where(y >= 0, y - t, y + t)
    n = np.stack([x, y, z], 1)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def check_frame(path):
    b = open(path, "rb").read()
    d = read_frame_bytes(b)
    tri = d["tri"]
    out = dict(file=os.path.basename(path), t=d["t"], frame=d["frame"], nv=d["nv"], nt=d["nt"], bytes=len(b), bytes_per_tri=len(b) / max(d["nt"], 1),
               index_in_range=bool(tri.size == 0 or int(tri.max()) < d["nv"]), finite=bool(np.isfinite(d["P"]).all() and np.isfinite(d["v"]).all()),
               normal_unit_err=float(np.max(np.abs(np.linalg.norm(d["N"], axis=1) - 1.0))) if d["nv"] else 0.0,
               z_min=float(d["P"][:, 2].min()) if d["nv"] else None, quant_half_step_m=d["quant_half_step_m"], still_offset=d["still_offset"])
    # 対称の面の継ぎ目（S6 と同じ読み方 R20）：三角形 1 個だけに使われる辺（面の縁）のうち、z = 0 の近く（|z| < 0.05 m）の辺の点の |z| の最大の 2 倍。
    # 量子化の後なので、量子化の半分の刻み（横の箱の長さ ÷ 65535 ÷ 2）までは隙間に入る
    if d["nt"]:
        e = np.sort(np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]]).astype(np.int64), axis=1)
        uq, cnt = np.unique(e, axis=0, return_counts=True)
        bd = uq[cnt == 1]
        Pz = d["P"][:, 2]
        near = bd[(np.abs(Pz[bd[:, 0]]) < 0.05) & (np.abs(Pz[bd[:, 1]]) < 0.05)]
        zz = np.abs(Pz[np.unique(near.ravel())]) if len(near) else np.array([])
        out["seam_boundary_edges"] = int(len(near))
        out["seam_gap_m"] = float(2 * zz.max()) if len(zz) else None
        out["quant_half_step_z_m"] = float((d["hi"][2] - d["lo"][2]) / 65535.0 / 2.0)
    return out, d


def clip(run_dir, out_dir, f_from=None, f_to=None):
    files = sorted(glob.glob(os.path.join(run_dir, "surf", "s_*.gw45s")))
    if f_from is not None:
        files = [p for p in files if int(os.path.basename(p)[2:7]) >= f_from]
    if f_to is not None:
        files = [p for p in files if int(os.path.basename(p)[2:7]) <= f_to]
    if not files:
        raise SystemExit("面の記録がない：%s/surf" % run_dir)
    os.makedirs(out_dir, exist_ok=True)
    blobs = [open(p, "rb").read() for p in files]
    heads = [read_frame_bytes(b) for b in blobs]
    n = len(blobs)
    fps = 24.0
    head = struct.pack("<8sIIddi", b"GW45CLP1", 1, n, fps, heads[0]["t"], heads[0]["frame"])
    head += b"\0" * (64 - len(head))
    pos = 64 + n * 16
    idx = b""
    for b in blobs:
        idx += struct.pack("<QII", pos, len(b), 0)
        pos += len(b)
    cp = os.path.join(out_dir, "clip.gw45c")
    with open(cp, "wb") as fh:
        fh.write(head); fh.write(idx)
        for b in blobs:
            fh.write(b)
    sha = hashlib.sha256(open(cp, "rb").read()).hexdigest()
    man = dict(format="GW45CLP1", version=1, frames=n, fps=fps, t_first=heads[0]["t"], t_last=heads[-1]["t"], frame_first=heads[0]["frame"],
               frame_last=heads[-1]["frame"], bytes=os.path.getsize(cp), sha256=sha, source=run_dir,
               tri_max=int(max(h["nt"] for h in heads)), vert_max=int(max(h["nv"] for h in heads)),
               MB_per_frame_mean=float(np.mean([len(b) for b in blobs]) / 1e6), created=time.strftime("%Y-%m-%d %H:%M:%S"),
               coords_ja="計画の座標（x 前、上、横）。Unity は x→x、上→y、横→z。横を −z に写してもう一度描く")
    json.dump(man, open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    # 読み戻し：クリップから各コマを目次で取り出し、元のファイルとバイト単位で同じか
    data = open(cp, "rb").read()
    ok = True
    t_dec = []
    for i, b in enumerate(blobs):
        o, L, _ = struct.unpack_from("<QII", data, 64 + 16 * i)
        ok &= data[o:o + L] == b
        t0 = time.perf_counter(); read_frame_bytes(data[o:o + L]); t_dec.append(time.perf_counter() - t0)
    chk = dict(clip_roundtrip_bytes_equal=bool(ok), decode_ms_python_median=float(np.median(t_dec) * 1000),
               frames=[check_frame(p)[0] for p in files[:: max(1, len(files) // 8)]])
    json.dump(chk, open(os.path.join(out_dir, "check.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    return man, chk


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if sys.argv[1] == "clip":
        a = sys.argv[2:]
        ff = int(a[a.index("--from") + 1]) if "--from" in a else None
        ft = int(a[a.index("--to") + 1]) if "--to" in a else None
        man, chk = clip(a[0], a[1], ff, ft)
        print(json.dumps(dict(manifest=man, check=dict((k, v) for k, v in chk.items() if k != "frames")), ensure_ascii=False, indent=1))
    elif sys.argv[1] == "check":
        print(json.dumps(check_frame(sys.argv[2])[0], ensure_ascii=False, indent=1))
