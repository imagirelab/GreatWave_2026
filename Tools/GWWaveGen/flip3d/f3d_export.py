# -*- coding: utf-8 -*-
"""FLIP3D：選んだ 12 s の窓の面を、Unity が読むクリップ（GW45CLP1）にまとめ、manifest・海底・船の上下を書く（py -3.10 -B、numpy・scipy）。
2026-10-16 進行役（Claude）が新しく書いた。窓は f3d_loop_ana.py の loop_ana.json の chosen。
クリップの形は flip45 g45_export_unity.py の GW45CLP1 と同じ（頭 64 バイト・目次・各コマの GW45SRF1 をバイトのまま）。違いは頭の fps で、
面の記録が 3 コマおき（0.125 s）なので 8 を書く（g45 の clip() は 24 を書くので使わない）。面そのものは記録のバイトのまま（形を変えない）。
横の写し（y = 0 の対称の面から全幅へ）はクリップに入れず、Unity が同じメッシュを z → −z に写してもう一度描く（GW45 の決まりと同じ。計算の対称の
仮定そのもの）。さらに外へ並べるかは Unity の設定（tilesPerSide）：y = 85 m は壁なので、壁で写すと 170 m ごとに同じ礁が並ぶ海になる（計算の仮定）。
出力（Unity/Build/FLIP3D/clip_DA3_k5/。Git には入れない）：
  clip.gw45c       面 96 コマ（t 77.25〜89.125 s）
  bed.f32          海底の高さ（x 0〜442 m・横 −85〜85 m、1 m、float32 [横][x]。g49_common.bed_z と DA3 の cfg の海底そのもの）
  manifest.json    窓・継ぎ目の数・原画に最も近い瞬間・座席と原画の視点・船の上下（hf から 24 Hz）・字・SHA-256（Unity の JsonUtility で読む平らな形）
  check.json       読み戻しの確かめ
使い方：py -3.10 -B f3d_export.py [--seat X,Z] [--eye M]
2026-10-16 追記（--r24）：毎コマの記録 DA3r（f3d_common.RUN24）から 24 個/s のクリップを書く。窓は f3d_loop24.py の loop24/loop24_ana.json の chosen。
  出力は別のフォルダー Unity/Build/FLIP3D/clip_DA3r_k5_r24/（前の 8 個/s の clip_DA3_k5/ は変えない）。形は同じ GW45CLP1 で、頭の fps が 24、
  288 コマ（記録の間 1 コマ）。前の 8 個/s のクリップと共通のコマ（3 コマおきの 96 個）は、記録のバイトの SHA-256 が前の manifest と同じことを確かめて書く。
  py -3.10 -B f3d_export.py --r24
2026-10-16 追記（--long）：続けて再生する長いクリップ（計算の記録のフォルダーのコマの範囲、毎コマ）。既定は GW45LIST1（記録のファイルをそのまま読む
  manifest。4 GB の写しを作らない。理由は main_long の上の説明）、--pack で GW45CLP1 に写す。--repeat N は試験用の合成の列。
  py -3.10 -B f3d_export.py --long --run DA3r_SC37y30_T12H7p5_dp0p5_c1152_t138_full --frames 1153-3313 --play 50,136
  py -3.10 -B f3d_export.py --long --run DA3r_SC37y30_T12H7p5_dp0p5_c1824_t90 --frames 1825-2161 --repeat 6
"""
import os, sys, json, struct, hashlib, time
import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f3d_common as C   # noqa: E402
import g49_common as GC  # noqa: E402  読むだけ（変えない）

SEAT_X, SEAT_Z = 300.0, -35.0       # 座席（Unity の座標。z < 0 は写した側。計算の横 35 m）【選び：下の理由】
EYE_M = 1.5                          # 目の高さ（船が浮く水面から）【選び】
FOOT = (4.0, 1.5)                    # 船の上下を読む足跡（x ±4 m・横 ±1.5 m）【選び】


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    a = sys.argv[1:]
    seat_x, seat_z = SEAT_X, SEAT_Z
    if "--seat" in a:
        seat_x, seat_z = [float(v) for v in a[a.index("--seat") + 1].split(",")]
    eye = float(a[a.index("--eye") + 1]) if "--eye" in a else EYE_M
    r24 = "--r24" in a
    if r24:
        run = C.RUN24
        ana = json.load(open(C.OUT + "/loop24/loop24_ana.json", encoding="utf8"))
        c4 = ana["chosen"]
        ch = dict(k=ana["breaker_k"], tau_frame=c4["tau_frame"], print_record_frame=c4["print_frame"], print_record_index=c4["print_record_index"],
                  print_frame_bestframes=c4["print_frame"], print_t_bestframes=c4["print_t"], score3=c4["score3"],
                  seam_mesh=c4["mismatch"]["mesh"], seam_eta_break=c4["mismatch"]["eta_break"], seam_eta_all={"rms": float("nan")})
        ana["step_reference"] = dict(mesh_p95_median=c4["steps_summary"]["mesh_p95_median"])
        out = C.OUT + "/clip_DA3r_k%d_r24" % ch["k"]
    else:
        run = C.RUN
        ana = json.load(open(C.OUT + "/loop/loop_ana.json", encoding="utf8"))
        ch = ana["chosen"]
        out = C.OUT + "/clip_DA3_k%d" % ch["k"]
    tau, L = ch["tau_frame"], ana["L_frames"]
    step = ana["record_step_frames"]
    frames = list(range(tau, tau + L, step))
    os.makedirs(out, exist_ok=True)
    blobs = [open(C.surf_path(f, run), "rb").read() for f in frames]
    heads = [C.E45.read_frame_bytes(b) for b in blobs]
    n = len(blobs)
    fps = C.FPS_SIM / step
    head = struct.pack("<8sIIddi", b"GW45CLP1", 1, n, fps, heads[0]["t"], heads[0]["frame"])
    head += b"\0" * (64 - len(head))
    pos = 64 + n * 16
    idx = b""
    for b in blobs:
        idx += struct.pack("<QII", pos, len(b), 0)
        pos += len(b)
    cp = out + "/clip.gw45c"
    with open(cp, "wb") as fh:
        fh.write(head); fh.write(idx)
        for b in blobs:
            fh.write(b)
    # 読み戻し
    data = open(cp, "rb").read()
    ok = all(data[struct.unpack_from("<QII", data, 64 + 16 * i)[0]:][:len(b)] == b for i, b in enumerate(blobs))
    src_sha = [hashlib.sha256(b).hexdigest() for b in blobs]
    same8 = None
    if r24:                            # 前の 8 個/s のクリップと共通のコマが、記録のバイトのまま同じか
        m8 = json.load(open(C.OUT + "/clip_DA3_k5/manifest.json", encoding="utf8"))
        d8 = dict(zip(m8["source_frames"], m8["source_sha256"]))
        common = [(f, s) for f, s in zip(frames, src_sha) if f in d8]
        same8 = dict(n_common=len(common), n_equal=sum(1 for f, s in common if d8[f] == s))
    # 海底（DA3 の cfg の海底そのもの）
    cfg = json.load(open(C.RUN + "/cfg.json", encoding="utf8"))
    spec = GC.bed_spec(cfg)
    bx = np.arange(0.0, 442.0 + 1e-9, 1.0)
    bz = np.arange(-85.0, 85.0 + 1e-9, 1.0)
    X, Z = np.meshgrid(bx, bz)
    B = GC.bed_z(X, np.abs(Z), **spec).astype(np.float32)
    bp = out + "/bed.f32"
    B.tofile(bp)
    # 船の上下（hf：上の水面の高さ、毎コマ。窓の始めから終わりの次のコマまで 289 個。足跡の平均）
    hf = C.Rec("hf", run)
    xs, zs = C.axes_hf(hf.meta)
    ix = (xs >= seat_x - FOOT[0]) & (xs <= seat_x + FOOT[0])
    iz = (zs >= abs(seat_z) - FOOT[1]) & (zs <= abs(seat_z) + FOOT[1])
    heave = []
    for f in range(tau, tau + L + 1):
        e = hf.get(f)[iz][:, ix]
        heave.append(float(np.nanmean(e)))
    heave = np.array(heave)
    seam_heave = float(heave[L] - heave[0])
    # 原画に最も近い瞬間（記録のコマ）と、その時の真ん中の頂（hf の y 0.5 m の行の最大）
    pr = ch["print_record_frame"]
    e = hf.get(pr)
    i = int(np.nanargmax(e[0]))
    crest_x, crest_eta = float(xs[i]), float(e[0, i])
    still = float(heads[0]["still_offset"])
    nv = [h["nv"] for h in heads]; nt = [h["nt"] for h in heads]
    man = dict(
        format="GW45CLP1", version=1, clip_file="clip.gw45c", clip_bytes=os.path.getsize(cp), clip_sha256=sha(cp),
        frames=n, record_fps=fps, sim_fps=C.FPS_SIM, record_step_frames=step,
        t_first=heads[0]["t"], t_last=heads[-1]["t"], frame_first=heads[0]["frame"], frame_last=heads[-1]["frame"],
        loop_seconds=L / C.FPS_SIM, loop_start_s=C.t_of(tau), loop_end_s=C.t_of(tau + L),
        vert_max=int(max(nv)), tri_max=int(max(nt)), vert_min=int(min(nv)), tri_min=int(min(nt)),
        still_offset_m=still,
        source_run=run.replace(C.REPO + "/", ""), source_frames=frames, source_sha256=src_sha,
        breaker_k=ch["k"], print_record_frame=pr, print_record_t=C.t_of(pr), print_record_index=ch["print_record_index"],
        print_bestframes_frame=ch["print_frame_bestframes"], print_bestframes_t=ch["print_t_bestframes"], print_score3=ch["score3"],
        print_crest_x=crest_x, print_crest_eta=crest_eta,
        seam_mesh_median_m=ch["seam_mesh"]["median"], seam_mesh_p95_m=ch["seam_mesh"]["p95"], seam_mesh_max_m=ch["seam_mesh"]["max"],
        seam_eta_rms_break_m=ch["seam_eta_break"]["rms"], seam_eta_rms_all_m=ch["seam_eta_all"]["rms"],
        step_mesh_p95_median_m=ana["step_reference"]["mesh_p95_median"],
        bed_file="bed.f32", bed_nx=len(bx), bed_nz=len(bz), bed_x0=float(bx[0]), bed_z0=float(bz[0]), bed_dx=1.0, bed_sha256=sha(bp),
        bed_formula=cfg["bed"].get("formula"),
        tank_x0=0.0, tank_x1=442.0, tank_half_width=85.0,
        seat_x=seat_x, seat_z=seat_z, seat_eye_m=eye, seat_foot_x=FOOT[0], seat_foot_z=FOOT[1],
        heave_fps=C.FPS_SIM, heave=[round(v, 4) for v in heave.tolist()], heave_seam_jump_m=seam_heave,
        heave_min_m=float(heave.min()), heave_max_m=float(heave.max()),
        coords_ja="計画の座標（x 前・上・横）をそのまま Unity の x・y・z に置く。横を −z に写した物をもう一度描く（計算の対称の仮定）",
        playback_ja=("面の記録は毎コマ（24 個/s）。Unity は実時間の時計で、その時刻以前の最後の記録を見せる。コマの間の形は作らない" if r24 else
                     "面の記録は 3 コマおき（8 個/s）。Unity は実時間の時計で、その時刻以前の最後の記録を見せる（コマを保つ）。コマの間の形は作らない"),
        created=time.strftime("%Y-%m-%d %H:%M:%S"))
    if r24:
        j, ss = c4["jump"], c4["steps_summary"]
        man.update(jump_frames=j["frames"], jump_mesh_p95_m=j["mesh"]["p95"], jump_eta_rms_break_m=j["eta_break"]["rms"],
                   jump_nn_median_m=j["mesh_nn"]["median"], jump_nn_p95_m=j["mesh_nn"]["p95"], jump_nn_max_m=j["mesh_nn"]["max"],
                   step_eta_rms_median_m=ss["eta_rms_median"], step_eta_rms_max_m=ss["eta_rms_max"], step_nn_p95_median_m=ss["nn_p95_median"],
                   step_nn_p95_max_m=ss["nn_p95_max"], same_bytes_as_8fps_clip=same8, seam_eta_rms_all_m=None)
    json.dump(man, open(out + "/manifest.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    chk = dict(clip_roundtrip_bytes_equal=bool(ok), frames=[C.E45.check_frame(C.surf_path(f, run))[0] for f in frames[::12]], same_bytes_as_8fps_clip=same8,
               seat=dict(x=seat_x, z=seat_z, heave_min=float(heave.min()), heave_max=float(heave.max()), seam_jump=seam_heave))
    json.dump(chk, open(out + "/check.json", "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    print(json.dumps(dict((k, v) for k, v in man.items() if k not in ("heave", "source_frames", "source_sha256")), ensure_ascii=False, indent=1))
    print("roundtrip", ok, "same8", same8)


# ---------------------------------------------------------------------------------------------------------------------
# 2026-10-16 追記（--long、進行役のサブエージェント）：計算の記録のフォルダーの毎コマの面の記録から、続けて再生する長いクリップを書く。
#   py -3.10 -B f3d_export.py --long --run <記録のフォルダー名か道> --frames A-B [--name <出力のフォルダー名>] [--play S0,S1|none] [--print-k 5]
#                             [--pack] [--repeat N] [--kind continuous|synthetic_test] [--hf-run <名前>] [--no-cross] [--seat X,Z] [--eye M]
#   既定（--pack なし）は GW45LIST1：クリップのファイルを作らず、manifest に記録のファイル（surf/s_FFFFF.gw45s）の並び・長さ・SHA-256 を書く。
#     Unity（FLIP3DStream）は記録のファイルをそのまま読む。選んだ理由：(1) 写しの 4 GB を作らない（同じバイトが 2 つになり、片方だけ
#     書き換わる心配もない）。(2) 記録のバイトは計算が書いたファイルそのものなので、バイト単位で同じことが作りから決まる（読む度に長さと
#     コマの番号を確かめ、-f3dsha なら SHA-256 も確かめる）。(3) G: は NVMe（Samsung 990 PRO）で、24 個/s × 約 1.9 MB = 約 46 MB/s は
#     ファイル 1 つずつ開いても十分に読める（速さは FLIP3DTiming の readMs と f3d_diskread.py で測る）。
#     弱み：記録のフォルダーを消す・動かすと読めない（manifest の SHA-256 で変わったことは分かる）。別の PC に持って行く時は --pack。
#   --pack：前と同じ GW45CLP1 の 1 つのファイル（頭・目次・各コマのバイトのまま）に写す。読み戻して SHA-256 が全部同じことを確かめる。
#   --repeat N：同じ並びを N 回続けた試験用の合成の列（clip_kind synthetic_test。継ぎ目が N − 1 個ある。本番ではない。読む速さの試験用）。
#   面の記録は 1 バイトも変えない（読むだけ）。船の上下は同じ記録のフォルダーの hf（なければ --hf-run）。崩れの一覧は DA3 の pana/best_frames.json。
# ---------------------------------------------------------------------------------------------------------------------
RUNS = C.REPO + "/Unity/Build/FLIP49/runs"


def _run_dir(name):
    return name.replace("\\", "/") if ("/" in name or "\\" in name) else RUNS + "/" + name


def _head(b):
    magic, ver, hb, t, fr, nv, nt = struct.unpack_from("<8sIIdiII", b, 0)
    off = struct.unpack_from("<f", b, 60)[0]
    if magic != b"GW45SRF1":
        raise ValueError("GW45SRF1 でない")
    return dict(t=t, frame=fr, nv=nv, nt=nt, still_offset=off)


def main_long(a):
    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    run = _run_dir(opt("--run"))
    f0, f1 = [int(v) for v in opt("--frames").split("-")]
    rep = int(opt("--repeat", "1"))
    kind = opt("--kind", "synthetic_test" if rep > 1 else "continuous")
    pack = "--pack" in a
    seat_x, seat_z = SEAT_X, SEAT_Z
    if "--seat" in a:
        seat_x, seat_z = [float(v) for v in opt("--seat").split(",")]
    eye = float(opt("--eye", EYE_M))
    pk = int(opt("--print-k", "5"))
    short = os.path.basename(run.rstrip("/")).split("_")[0]
    name = opt("--name", ("clip_SYNTH_%s_f%d_%d_x%d" % (short, f0, f1, rep)) if rep > 1 else ("clip_%s_f%d_%d" % (short, f0, f1)))
    out = C.OUT + "/" + name
    play = opt("--play", "50,136" if kind == "continuous" else "none")
    t_start = time.time()
    uniq = list(range(f0, f1 + 1))
    frames = uniq * rep
    missing = [f for f in uniq if not os.path.exists(C.surf_path(f, run))]
    if missing:
        raise SystemExit("面の記録がない：%d 個（最初 %s）。記録し直しが終わってから走らせる" % (len(missing), missing[:5]))
    os.makedirs(out, exist_ok=True)
    # 1. 記録を 1 つずつ読み、長さ・SHA-256・頭を確かめる（バイトは変えない）
    info = {}
    bad = []
    for f in uniq:
        b = open(C.surf_path(f, run), "rb").read()
        h = _head(b)
        if h["frame"] != f or abs(h["t"] - C.t_of(f)) > 1e-6:
            bad.append(dict(frame=f, head_frame=h["frame"], head_t=h["t"]))
        info[f] = dict(bytes=len(b), sha=hashlib.sha256(b).hexdigest(), **h)
    if bad:
        raise SystemExit("頭のコマ・時刻が名前と違う記録：%s" % bad[:5])
    chk_frames = [C.E45.check_frame(C.surf_path(f, run))[0] for f in uniq[::120]]
    nv = [info[f]["nv"] for f in uniq]; nt = [info[f]["nt"] for f in uniq]
    n = len(frames)
    fps = C.FPS_SIM
    src_sha = [info[f]["sha"] for f in frames]
    src_bytes = [info[f]["bytes"] for f in frames]
    list_fp = hashlib.sha256("".join(src_sha).encode("ascii")).hexdigest()
    # 2. GW45CLP1 に写す（--pack の時だけ）
    clip_info = dict(clip_file="", clip_bytes=int(sum(src_bytes)), clip_sha256="")
    roundtrip = None
    if pack:
        cp = out + "/clip.gw45c"
        head = struct.pack("<8sIIddi", b"GW45CLP1", 1, n, fps, info[frames[0]]["t"], frames[0])
        head += b"\0" * (64 - len(head))
        pos = 64 + n * 16
        idx = b""
        for L in src_bytes:
            idx += struct.pack("<QII", pos, L, 0)
            pos += L
        with open(cp, "wb") as fh:
            fh.write(head); fh.write(idx)
            for f in frames:
                fh.write(open(C.surf_path(f, run), "rb").read())
        ok = 0
        with open(cp, "rb") as fh:
            for i, f in enumerate(frames):
                fh.seek(64 + 16 * i)
                o, L, _ = struct.unpack("<QII", fh.read(16))
                fh.seek(o)
                ok += hashlib.sha256(fh.read(L)).hexdigest() == src_sha[i]
        roundtrip = dict(records=n, sha_equal=ok)
        clip_info = dict(clip_file="clip.gw45c", clip_bytes=os.path.getsize(cp), clip_sha256=sha(cp))
    # 3. 海底（DA3 の cfg の海底そのもの。前のクリップと同じ）
    cfg = json.load(open(C.RUN + "/cfg.json", encoding="utf8"))
    spec = GC.bed_spec(cfg)
    bx = np.arange(0.0, 442.0 + 1e-9, 1.0)
    bz = np.arange(-85.0, 85.0 + 1e-9, 1.0)
    X, Z = np.meshgrid(bx, bz)
    B = GC.bed_z(X, np.abs(Z), **spec).astype(np.float32)
    bp = out + "/bed.f32"
    B.tofile(bp)
    # 4. 船の上下（hf：上の水面の高さ。記録ごとに 1 個、座席の足跡の平均）
    hf_run = _run_dir(opt("--hf-run")) if "--hf-run" in a else run
    hf = C.Rec("hf", hf_run)
    miss_hf = [f for f in uniq if f not in hf.where]
    if miss_hf:
        raise SystemExit("hf がないコマ：%d 個（最初 %s）。--hf-run で別の記録（同じ道筋の DA3 など）を選ぶ" % (len(miss_hf), miss_hf[:5]))
    xs, zs = C.axes_hf(hf.meta)
    ix = (xs >= seat_x - FOOT[0]) & (xs <= seat_x + FOOT[0])
    iz = (zs >= abs(seat_z) - FOOT[1]) & (zs <= abs(seat_z) + FOOT[1])
    hv = {f: float(np.nanmean(hf.get(f)[iz][:, ix])) for f in uniq}
    heave = np.array([hv[f] for f in frames])
    # 5. 崩れの一覧と原画に最も近い瞬間（DA3 の判定。DA3r は DA3 の途中保存から同じ物理で計算し直した物）
    bf = json.load(open(C.RUN + "/pana/best_frames.json", encoding="utf8"))
    brk = []
    for b in bf["per_breaker"]:
        if f0 <= b["frame"] <= f1:
            w0, w1 = b["window_frames"]
            brk.append(dict(k=b["k"], frame=b["frame"], t=b["t"], score3=b["score3"], win_first=w0, win_last=w1,
                            hood=float(b["ruler"].get("hood") or 0.0), lip=float(b["ruler"].get("lip") or 0.0)))
    pb = [b for b in brk if b["k"] == pk]
    pr = dict(breaker_k=0, print_record_frame=0, print_record_t=0.0, print_record_index=0, print_bestframes_frame=0, print_bestframes_t=0.0,
              print_score3=0.0, print_crest_x=0.0, print_crest_eta=0.0)
    if pb:
        b = pb[0]
        e = hf.get(b["frame"])
        i = int(np.nanargmax(e[0]))
        pr = dict(breaker_k=pk, print_record_frame=b["frame"], print_record_t=C.t_of(b["frame"]), print_record_index=frames.index(b["frame"]),
                  print_bestframes_frame=b["frame"], print_bestframes_t=b["t"], print_score3=b["score3"], print_crest_x=float(xs[i]), print_crest_eta=float(e[0, i]))
    if play == "none":
        p0 = p1 = 0.0
    else:
        p0, p1 = [float(v) for v in play.split(",")]
    sd = run + "/surf"
    still = float(info[frames[0]]["still_offset"])
    man = dict(
        format="GW45CLP1" if pack else "GW45LIST1", version=1, clip_kind=kind, **clip_info,
        frames=n, record_fps=fps, sim_fps=C.FPS_SIM, record_step_frames=1,
        t_first=info[frames[0]]["t"], t_last=info[frames[-1]]["t"], frame_first=frames[0], frame_last=frames[-1],
        loop_seconds=n / fps, loop_start_s=info[frames[0]]["t"], loop_end_s=info[frames[0]]["t"] + n / fps,
        play_from_s=p0, play_to_s=p1,
        vert_max=int(max(nv)), tri_max=int(max(nt)), vert_min=int(min(nv)), tri_min=int(min(nt)),
        still_offset_m=still,
        source_run=run.replace(C.REPO + "/", ""), source_frames=frames, source_bytes=src_bytes, source_sha256=src_sha, source_list_sha256=list_fp,
        stream_dir=("" if pack else sd), stream_dir_rel=("" if pack else os.path.relpath(sd, out).replace("\\", "/")), stream_pattern=("" if pack else "s_{0:D5}.gw45s"),
        repeat=rep,
        breakers=brk, breakers_source="DA3 の pana/best_frames.json（DA3 の判定 score3。DA3r は DA3 の途中保存から同じ物理で計算し直した物）",
        **pr,
        bed_file="bed.f32", bed_nx=len(bx), bed_nz=len(bz), bed_x0=float(bx[0]), bed_z0=float(bz[0]), bed_dx=1.0, bed_sha256=sha(bp),
        bed_formula=cfg["bed"].get("formula"),
        tank_x0=0.0, tank_x1=442.0, tank_half_width=85.0,
        seat_x=seat_x, seat_z=seat_z, seat_eye_m=eye, seat_foot_x=FOOT[0], seat_foot_z=FOOT[1],
        heave_fps=C.FPS_SIM, heave=[round(v, 4) for v in heave.tolist()], heave_min_m=float(heave.min()), heave_max_m=float(heave.max()),
        heave_source=hf_run.replace(C.REPO + "/", ""),
        coords_ja="計画の座標（x 前・上・横）をそのまま Unity の x・y・z に置く。横を −z に写した物をもう一度描く（計算の対称の仮定）",
        playback_ja=("面の記録は毎コマ（24 個/s）。Unity は記録の範囲を続けて 1 回（繰り返さない）、実時間の時計で、その時刻以前の最後の記録を見せる。"
                     "コマの間の形は作らない。" + ("記録のファイルをそのまま続けて読む（GW45LIST1）" if not pack else "") +
                     ("【試験用の合成の列：同じ並びを %d 回続けた物。継ぎ目が %d 個ある。本番ではない】" % (rep, rep - 1) if rep > 1 else "")),
        created=time.strftime("%Y-%m-%d %H:%M:%S"))
    json.dump(man, open(out + "/manifest.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    # 6. 確かめ：前のクリップ・ほかの記録と、同じコマの記録のバイトが同じか（SHA-256。--no-cross で省く）
    cross = {}
    if "--no-cross" not in a:
        m24p = C.OUT + "/clip_DA3r_k5_r24/manifest.json"
        if os.path.exists(m24p):
            m24 = json.load(open(m24p, encoding="utf8"))
            d24 = dict(zip(m24["source_frames"], m24["source_sha256"]))
            com = [f for f in uniq if f in d24]
            cross["clip_DA3r_k5_r24"] = dict(n_common=len(com), n_equal=sum(d24[f] == info[f]["sha"] for f in com))
        for other in (C.RUN, C.RUN24):
            if os.path.normcase(os.path.abspath(other)) == os.path.normcase(os.path.abspath(run)):
                continue
            com = [f for f in uniq if os.path.exists(C.surf_path(f, other))]
            eq = sum(hashlib.sha256(open(C.surf_path(f, other), "rb").read()).hexdigest() == info[f]["sha"] for f in com)
            cross[os.path.basename(other)] = dict(n_common=len(com), n_equal=int(eq))
    chk = dict(records=n, unique_frames=len(uniq), repeat=rep, format=man["format"], bytes_total=int(sum(src_bytes)),
               head_frame_and_t_match_name=True, frames_check_every_120=chk_frames, pack_roundtrip=roundtrip, cross_sha_equal=cross,
               breakers=[(b["k"], b["frame"]) for b in brk], print=pr, play=[p0, p1], seconds=round(time.time() - t_start, 1))
    json.dump(chk, open(out + "/check.json", "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    print(json.dumps(dict((k, v) for k, v in man.items() if k not in ("heave", "source_frames", "source_sha256", "source_bytes")), ensure_ascii=False, indent=1))
    print(json.dumps(dict(cross=cross, roundtrip=roundtrip, seconds=chk["seconds"], out=out), ensure_ascii=False))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")   # 2026-10-16 独立の確かめで足した：SystemExit の日本語の知らせ（「面の記録がない」など）が文字化けしていた
    except Exception:
        pass
    if "--long" in sys.argv[1:]:
        main_long(sys.argv[1:])
    else:
        main()
