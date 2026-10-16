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
    ana = json.load(open(C.OUT + "/loop/loop_ana.json", encoding="utf8"))
    ch = ana["chosen"]
    tau, L = ch["tau_frame"], ana["L_frames"]
    step = ana["record_step_frames"]
    frames = list(range(tau, tau + L, step))
    out = C.OUT + "/clip_DA3_k%d" % ch["k"]
    os.makedirs(out, exist_ok=True)
    blobs = [open(C.surf_path(f), "rb").read() for f in frames]
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
    hf = C.Rec("hf")
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
        source_run=C.RUN.replace(C.REPO + "/", ""), source_frames=frames, source_sha256=src_sha,
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
        playback_ja="面の記録は 3 コマおき（8 個/s）。Unity は実時間の時計で、その時刻以前の最後の記録を見せる（コマを保つ）。コマの間の形は作らない",
        created=time.strftime("%Y-%m-%d %H:%M:%S"))
    json.dump(man, open(out + "/manifest.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    chk = dict(clip_roundtrip_bytes_equal=bool(ok), frames=[C.E45.check_frame(C.surf_path(f))[0] for f in frames[::12]],
               seat=dict(x=seat_x, z=seat_z, heave_min=float(heave.min()), heave_max=float(heave.max()), seam_jump=seam_heave))
    json.dump(chk, open(out + "/check.json", "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    print(json.dumps(dict((k, v) for k, v in man.items() if k not in ("heave", "source_frames", "source_sha256")), ensure_ascii=False, indent=1))
    print("roundtrip", ok)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
