# -*- coding: utf-8 -*-
"""FLIP49：DA3 の途中保存から、新しい記録の置き場所で計算し直す（cfg DA3r）ための準備と、DA3 の記録との比べ（py -3.10 -B、numpy・scipy）。
2026-10-16 新しく書いた（FLIP3D の再生の 8 個/s の段をなくすための記録し直し）。flip45〜48 のファイルは読みもしない。g49_common を読むだけ。

  py -3.10 -B g49_restart.py seed <cfg.json>
      cfg の restart（g49_pcfg.py cfg DA3r が書く）に従い、新しい置き場所 Build/FLIP49/<out_root>/<run_id>/ を作って、元の記録（DA3）から
        ckpt/v.<k>.sim（途中保存。g49_chain.py が最後の途中保存の次のコマから続ける）
        volcorr/ref.json（水の量の直しの基準）、volcorr/state.jsonl の f ≤ k の行（元の順のまま。g49_run.py が f0 − 1 までの行から段 C の
        水面の履歴・積分を引き継ぐ）、volcorr/vd_<k>.txt と vd_<k+1>.txt（場面がコマ k+1 で読む発散・du_abs。元の起動がコマ k の終わりに書いた物）
      を写す。元の置き場所には書かない（読むだけ。置き場所が同じ・中なら止める）。写した物と元の SHA-256 を seed.json に書く。
      もう起動の記録（run_c*.json）がある置き場所には写さない（写した物が元と同じかだけ確かめる）。
  py -3.10 -B g49_restart.py compare <cfg.json>
      計算し直した記録と元の記録を同じコマで比べる：面 R5（元は 3 コマおき。ファイルのバイト、違えば点の距離）、R4 の SDF（元は 3 コマおき）、
      hf・r2・r3・水の量の直しの状態（元も毎コマ）。同じコマが 2 つの起動にある時は後の起動の物（f3d_common と同じ決まり）。
      <置き場所>/restart_compare.json に書き、要約を画面に出す。
"""
import os, sys, json, glob, re, shutil, time, struct, hashlib

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np                 # noqa: E402
import g49_common as GC            # noqa: E402

HEAD_BYTES = 96


def norm(p):
    return os.path.abspath(p).replace("\\", "/").rstrip("/").lower()


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def dirs(c):
    R = c.get("restart")
    if not R:
        raise SystemExit("cfg に restart がない（g49_pcfg.py cfg DA3r で書いた cfg だけ）")
    src = os.path.join(GC.B49, "runs", R["src_run"]).replace("\\", "/")
    dst = os.path.join(GC.B49, c.get("out_root", "runs"), c["run_id"]).replace("\\", "/")
    if norm(src) == norm(dst) or (norm(dst) + "/").startswith(norm(src) + "/") or (norm(src) + "/").startswith(norm(dst) + "/"):
        raise SystemExit("新しい置き場所 %s が元の記録 %s と同じか中にある。書かない" % (dst, src))
    if not (norm(dst) + "/").startswith(norm(GC.B49) + "/"):
        raise SystemExit("新しい置き場所 %s が Build/FLIP49 の外。書かない" % dst)
    return R, src, dst


# ====================================================================== seed
def seed(cfgp):
    c = json.load(open(cfgp, encoding="utf8"))
    R, src, dst = dirs(c)
    k = int(R["ckpt_frame"])
    if (c.get("precheck") or {}).get("ok") is not True:
        raise SystemExit("cfg の precheck が ok でない：%s" % (c.get("precheck") or {}).get("reason"))
    if int(c["f_start"]) != k + 1 or int(c.get("f_first", 0)) != k + 1:
        raise SystemExit("cfg の f_start・f_first（%s・%s）が途中保存の次のコマ %d でない" % (c["f_start"], c.get("f_first"), k + 1))
    jobs = [("ckpt/v.%04d.sim" % k, None), ("volcorr/ref.json", None), ("volcorr/vd_%05d.txt" % k, None), ("volcorr/vd_%05d.txt" % (k + 1), None),
            ("volcorr/state.jsonl", "rows_le_k")]
    ran = sorted(glob.glob(os.path.join(dst, "run_c*.json")))
    rec = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip49/g49_restart.py seed", cfg=os.path.abspath(cfgp).replace("\\", "/"),
               src=src, dst=dst, ckpt_frame=k, files={}, note_ja="元の記録の置き場所は読むだけ。写した物だけを新しい置き場所に置いた")
    for rel, how in jobs:
        sp, dp = os.path.join(src, rel), os.path.join(dst, rel)
        if not os.path.exists(sp):
            raise SystemExit("元の記録に %s がない" % sp)
        if how == "rows_le_k":
            lines = [ln for ln in open(sp, encoding="utf8") if ln.strip() and int(json.loads(ln)["f"]) <= k]
            data = "".join(lines).encode("utf8")
            src_sha = hashlib.sha256(data).hexdigest()
            info = dict(rows=len(lines), frames=[min(int(json.loads(ln)["f"]) for ln in lines), max(int(json.loads(ln)["f"]) for ln in lines)],
                        src_sha256_of_rows=src_sha, src_file_sha256=sha(sp), rule="f <= %d, original order (later rows of a frame win when read)" % k)
            if ran:
                ok = os.path.exists(dp) and open(dp, "rb").read().startswith(data)
                info.update(already_ran=True, dst_starts_with_rows=bool(ok))
            else:
                os.makedirs(os.path.dirname(dp), exist_ok=True)
                with open(dp, "wb") as fh:
                    fh.write(data)
                info["dst_sha256"] = sha(dp)
                assert info["dst_sha256"] == src_sha
        else:
            src_sha = sha(sp)
            info = dict(bytes=os.path.getsize(sp), src_sha256=src_sha)
            if os.path.exists(dp) and sha(dp) == src_sha:
                info["dst_sha256"] = src_sha; info["already_there"] = True
            elif ran:
                info.update(already_ran=True, dst_sha256=sha(dp) if os.path.exists(dp) else None)
            else:
                os.makedirs(os.path.dirname(dp), exist_ok=True)
                shutil.copyfile(sp, dp)
                info["dst_sha256"] = sha(dp)
                assert info["dst_sha256"] == src_sha, "写した %s の SHA-256 が元と違う" % rel
        rec["files"][rel] = info
        print(rel, {kk: v for kk, v in info.items() if kk in ("bytes", "rows", "frames", "already_there", "already_ran", "dst_starts_with_rows")},
              "sha ok" if info.get("dst_sha256") in (info.get("src_sha256"), info.get("src_sha256_of_rows")) else "")
    others = [p for p in glob.glob(os.path.join(dst, "ckpt", "v.*.sim")) if int(os.path.basename(p)[2:6]) != k]
    rec["other_ckpts_in_dst"] = sorted(os.path.basename(p) for p in others)
    if others and not ran:
        raise SystemExit("新しい置き場所にほかの途中保存 %s がある（g49_chain.py がそこから続けてしまう）。確かめてから" % rec["other_ckpts_in_dst"])
    p = os.path.join(dst, "seed.json")
    if not ran:
        json.dump(rec, open(p, "w", encoding="utf8"), indent=1, ensure_ascii=False)
        print("seed.json", p)
    else:
        print("already ran (%d launch records); seed.json not rewritten" % len(ran))
    return rec


# ====================================================================== compare
def blocks(rd, kind):
    out = []
    for p in glob.glob(os.path.join(rd, "%s_c*_b*.npz" % kind)):
        m = re.search(r"_c(\d+)_b(\d+)\.npz$", p.replace("\\", "/"))
        out.append((int(m.group(1)), int(m.group(2)), p))
    return sorted(out)


def index(rd, kind, f0, f1):
    """コマ → (起動, path, 番号)。同じコマが 2 つの起動にあれば後の起動の物。"""
    where = {}
    for c_, b_, p in blocks(rd, kind):
        with np.load(p, allow_pickle=True) as d:
            fr = d["frames"]
        for i, f in enumerate(fr):
            f = int(f)
            if f0 <= f <= f1 and (f not in where or where[f][0] < c_):
                where[f] = (c_, p, i)
    return where


def fetch(where, keys, frames):
    """{key: {frame: array}}。ブロックごとに 1 回だけ解く。"""
    by = {}
    for f in frames:
        by.setdefault(where[f][1], []).append((f, where[f][2]))
    out = {k_: {} for k_ in keys}
    for p, lst in by.items():
        with np.load(p, allow_pickle=True) as d:
            for k_ in keys:
                if k_ not in d.files:
                    continue
                arr = d[k_]
                for f, i in lst:
                    out[k_][f] = arr[i].copy()
    return out


def diff_stats(a, b):
    if a.shape != b.shape:
        return dict(shape=[list(a.shape), list(b.shape)], bit_equal=False)
    x = a.astype(np.float64); y = b.astype(np.float64)
    fin = np.isfinite(x) & np.isfinite(y)
    d = np.abs(x - y)[fin]
    return dict(bit_equal=bool(np.array_equal(a, b, equal_nan=True)), max=float(d.max()) if d.size else 0.0, median=float(np.median(d)) if d.size else 0.0,
                p99=float(np.percentile(d, 99)) if d.size else 0.0, nan_mismatch=int((np.isfinite(x) != np.isfinite(y)).sum()), n=int(d.size))


def summarize(rows):
    rows = [r for r in rows if "bit_equal" in r]
    if not rows:
        return dict(n_frames=0)
    mx = [r.get("max", float("inf")) for r in rows]
    return dict(n_frames=len(rows), n_bit_equal=int(sum(r["bit_equal"] for r in rows)), max_of_max=float(max(mx)),
                median_of_median=float(np.median([r.get("median", np.nan) for r in rows])), max_nan_mismatch=int(max(r.get("nan_mismatch", 0) for r in rows)),
                worst_frame=int(rows[int(np.argmax(mx))]["frame"]))


def read_surf(p):
    b = open(p, "rb").read()
    mg, ver, hb, t, f, nv, nt = struct.unpack_from("<8sIIdiII", b, 0)
    lo = np.array(struct.unpack_from("<3f", b, 36)); hi = np.array(struct.unpack_from("<3f", b, 48)); off = struct.unpack_from("<f", b, 60)[0]
    o = hb
    q = np.frombuffer(b, np.uint16, nv * 3, o).reshape(-1, 3); o += nv * 6
    o += nv * 4                                            # 法線（oct）
    o += nv * 6                                            # 速さ（float16）
    tri = np.frombuffer(b, np.uint32, nt * 3, o).reshape(-1, 3)
    P = q.astype(np.float64) / 65535.0 * (hi - lo) + lo
    return dict(t=t, f=f, nv=nv, nt=nt, lo=lo, hi=hi, off=off, P=P, tri=tri, qstep=(hi - lo) / 65535.0)


def surf_compare(pa, pb):
    ba, bb = open(pa, "rb").read(), open(pb, "rb").read()
    r = dict(bytes_equal=ba == bb, bytes=[len(ba), len(bb)])
    if r["bytes_equal"]:
        r.update(max_m=0.0, median_m=0.0, p95_m=0.0)
        return r
    A, B = read_surf(pa), read_surf(pb)
    r.update(nv=[A["nv"], B["nv"]], nt=[A["nt"], B["nt"]], off=[A["off"], B["off"]], t=[A["t"], B["t"]],
             header_rest_equal=ba[:HEAD_BYTES] == bb[:HEAD_BYTES], payload_equal=ba[HEAD_BYTES:] == bb[HEAD_BYTES:])
    from scipy.spatial import cKDTree
    da, _ = cKDTree(B["P"]).query(A["P"]); db, _ = cKDTree(A["P"]).query(B["P"])
    d = np.concatenate([da, db])
    r.update(max_m=float(d.max()), median_m=float(np.median(d)), p95_m=float(np.percentile(d, 95)), rule="symmetric nearest-vertex distance (m)")
    return r


def compare(cfgp):
    c = json.load(open(cfgp, encoding="utf8"))
    R, src, dst = dirs(c)
    f0, f1 = int(c["f_start"]), int(c["f_end"])
    out = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip49/g49_restart.py compare", src=src, dst=dst, frames=[f0, f1],
               restart_ckpt=int(R["ckpt_frame"]), rule="same frame numbers; a frame present in 2 launches is read from the later launch (f3d_common rule)")
    # 起動の記録
    runs = []
    for p in sorted(glob.glob(os.path.join(dst, "run_c*.json"))):
        r = json.load(open(p, encoding="utf8"))
        runs.append({k_: r.get(k_) for k_ in ("f_start", "f_end_done", "stopped", "wall_total_s", "wall_launch_s", "wall_per_frame_median_s",
                                               "surf_per_frame_median_s", "particles_max", "rss_peak_gb", "still_offset")})
    out["launches"] = runs
    # 面 R5
    sa = sorted(int(os.path.basename(p)[2:7]) for p in glob.glob(os.path.join(src, "surf", "s_*.gw45s")))
    sb = sorted(int(os.path.basename(p)[2:7]) for p in glob.glob(os.path.join(dst, "surf", "s_*.gw45s")))
    sb_in = [f for f in sb if f0 <= f <= f1]
    out["r5_dst_frames"] = dict(n=len(sb_in), expected=f1 - f0 + 1, missing=[f for f in range(f0, f1 + 1) if f not in set(sb)][:50])
    common = [f for f in sa if f0 <= f <= f1 and f in set(sb)]
    rows = []
    for f in common:
        r = surf_compare(os.path.join(src, "surf", "s_%05d.gw45s" % f), os.path.join(dst, "surf", "s_%05d.gw45s" % f))
        r["frame"] = f
        rows.append(r)
    out["r5"] = dict(n_common=len(common), n_bytes_equal=int(sum(r["bytes_equal"] for r in rows)), frames=[common[0], common[-1]] if common else None,
                     max_m=float(max([r["max_m"] for r in rows] or [0.0])), median_of_median_m=float(np.median([r["median_m"] for r in rows])) if rows else None,
                     max_p95_m=float(max([r["p95_m"] for r in rows] or [0.0])), not_equal=[r for r in rows if not r["bytes_equal"]][:20])
    print("R5 surfaces: %d common frames (%s), bytes equal %d, max %.3g m, median of median %s m" % (
        len(common), out["r5"]["frames"], out["r5"]["n_bytes_equal"], out["r5"]["max_m"], out["r5"]["median_of_median_m"]), flush=True)
    # 格子の記録
    for kind, keys in (("hf", ("eta",)), ("r2", ("sdf", "u", "w")), ("r3", ("sdf", "u", "v", "w")), ("r4", ("sdf",))):
        wa, wb = index(src, kind, f0, f1), index(dst, kind, f0, f1)
        fr = sorted(set(wa) & set(wb))
        res = dict(n_src=len(wa), n_dst=len(wb), n_common=len(fr), frames=[fr[0], fr[-1]] if fr else None)
        if fr:
            A, B = fetch(wa, keys, fr), fetch(wb, keys, fr)
            for k_ in keys:
                if not A[k_]:
                    continue
                rws = []
                for f in fr:
                    if f in A[k_] and f in B[k_]:
                        s_ = diff_stats(A[k_][f], B[k_][f]); s_["frame"] = f; rws.append(s_)
                res[k_] = summarize(rws)
                if res[k_].get("n_bit_equal", 0) < res[k_].get("n_frames", 0):
                    res[k_]["not_equal_first"] = [r for r in rws if not r["bit_equal"]][:10]
        out[kind] = res
        print(kind, {k_: v for k_, v in res.items() if k_ in ("n_src", "n_dst", "n_common", "frames")},
              {k_: {kk: res[k_][kk] for kk in ("n_frames", "n_bit_equal", "max_of_max", "median_of_median") if kk in res[k_]} for k_ in keys if k_ in res}, flush=True)
    # 水の量の直しの状態（毎コマの V・du_abs）
    def rows_of(p):
        d = {}
        if os.path.exists(p):
            for ln in open(p, encoding="utf8"):
                q = json.loads(ln)
                if f0 <= int(q["f"]) <= f1:
                    d[int(q["f"])] = q
        return d
    va, vb = rows_of(os.path.join(src, "volcorr", "state.jsonl")), rows_of(os.path.join(dst, "volcorr", "state.jsonl"))
    fr = sorted(set(va) & set(vb))
    keys = ("V", "Vwin", "du_abs", "L_band", "L_probe", "I_B", "cum")
    neq = [f for f in fr if any(va[f].get(k_) != vb[f].get(k_) for k_ in keys)]
    out["volcorr"] = dict(n_common=len(fr), n_equal=len(fr) - len(neq), not_equal_first=neq[:10],
                          max_abs_du_abs=float(max([abs(float(va[f]["du_abs"]) - float(vb[f]["du_abs"])) for f in fr] or [0.0])))
    print("volcorr state rows: %d common, %d identical" % (len(fr), len(fr) - len(neq)), flush=True)
    allbit = (out["r5"]["n_common"] > 0 and out["r5"]["n_bytes_equal"] == out["r5"]["n_common"]
              and all(out[k_].get(kk, {}).get("n_bit_equal") == out[k_].get(kk, {}).get("n_frames")
                      for k_, ks in (("hf", ("eta",)), ("r2", ("sdf", "u", "w")), ("r3", ("sdf", "u", "v", "w")), ("r4", ("sdf",))) for kk in ks)
              and out["volcorr"]["n_equal"] == out["volcorr"]["n_common"])
    out["all_bit_identical"] = bool(allbit)
    out["tags"] = dict(all="測定（記録どうしの比べ）")
    p = os.path.join(dst, "restart_compare.json")
    json.dump(out, open(p, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    print("all_bit_identical", allbit, "->", p)
    return out


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) < 3 or sys.argv[1] not in ("seed", "compare"):
        print(__doc__); sys.exit(1)
    (seed if sys.argv[1] == "seed" else compare)(sys.argv[2])
