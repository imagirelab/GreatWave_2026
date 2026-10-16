# -*- coding: utf-8 -*-
"""FLIP3D：Unity の読み解きが元の面の記録と同じ形か、画面外の連番が決まりどおりの記録を見せたか、実時間の時間の記録をまとめる（py -3.10 -B、numpy）。
2026-10-16 進行役（Claude）が新しく書いた。
  V1 読み解き：Unity（FLIP3DClip.DecodeArrays、Mesh を作るのと同じ関数）が書いた点・法線・三角形を、g45_export_unity.read_frame_bytes（Python）の値と比べる。
     幅（測る前に決めた）：点の差の最大 ≤ 量子化の半分の刻み + 1 mm（float32 の丸めの分）、法線の差 ≤ 0.5°、三角形は同じ 3 点の組（回りだけ逆）。
  V2 記録の保ち方：連番の frames.csv で、見せた記録 = floor(位相 × 8)、各記録は 3 フレーム（24 fps）続く（継ぎ目・止め・動きの切り替えを除く）。
  V3 時間：プレイヤーの timing/<tag>/*.json の 1 フレームの時間（p50・p95・p99・最大、11.1 ms と 16.7 ms を越えたフレームの数）。
使い方：py -3.10 -B f3d_verify.py [timing_tag]   → Unity/Build/FLIP3D/verify/verify_result.json
2026-10-16 追記（24 個/s）：--clip <クリップのフォルダー名> --cap <連番のフォルダー名[,...]> --vdir <確かめのフォルダー名> で、毎コマの記録 DA3r の
  クリップ（clip_DA3r_k5_r24）も同じ決まりで確かめる。V2 の「各記録 3 フレーム」は「各記録 24 / record_fps フレーム」と読む（24 個/s なら 1 フレーム）。
  面の記録は manifest の source_run から読む。
  py -3.10 -B f3d_verify.py t2 --clip clip_DA3r_k5_r24 --cap capture24,capture8chk --vdir verify24
2026-10-16 追記（続けて再生・続けて読む、進行役のサブエージェント）：
  V2 に連番 cseat・cprint・cmove（続けて再生）を足した：止め以外のフレームで、記録が範囲の初めから 1 つずつ増え、全部の記録を 1 回ずつ見せたか、
     見せた記録のコマ（frames.csv の sim_frame）が manifest の source_frames と同じか、予定の記録（wanted）を見せたか（画面外の描画は待つので必ず同じ）。
  V3 は timing/<tag>/ の全部の視点（cseat・s_seat など）。続けて読む時の数（間に合わなかったフレーム・GPU に送った時間・読み・メモリー）も写す。
  V4（--hash）：manifest の全部の記録を読み直し、SHA-256 が source_sha256 と同じか（GW45LIST1 は記録のファイル、GW45CLP1 はクリップの中の位置）。
  py -3.10 -B f3d_verify.py <tag> --clip clip_DA3r_f1153_3313 --cap capture_cont --vdir verify_cont --hash
2026-10-16 確かめで足した：<tag> はコンマで並べられる（V3 を tag ごとに書く）。-f3dtargetfps で上限を付けた時間は、1.5 拍・2 拍を越えた数（over_1p5_beats・over_2_beats）も書く。
  py -3.10 -B f3d_verify.py t3cont,t3cont_nolabel,t3cap90,t3loop --clip clip_DA3r_f1153_3313 --cap capture_cont --vdir verify_cont --hash
"""
import os, sys, json, csv
import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f3d_common as C   # noqa: E402

VD = C.OUT + "/verify"
CLIP = "clip_DA3_k5"


def v1():
    man = json.load(open(C.OUT + "/" + CLIP + "/manifest.json", encoding="utf8"))
    run = C.REPO + "/" + man["source_run"]
    info = json.load(open(VD + "/verify.json", encoding="utf8"))
    out = []
    for it in info:
        r = it["record"]
        d = C.read_surf(man["source_frames"][r], run)
        Pu = np.fromfile(VD + "/rec%d_pos.f32" % r, np.float32).reshape(-1, 3).astype(np.float64)
        Nu = np.fromfile(VD + "/rec%d_nrm.f32" % r, np.float32).reshape(-1, 3).astype(np.float64)
        Iu = np.fromfile(VD + "/rec%d_idx.i32" % r, np.int32).reshape(-1, 3)
        dp = float(np.abs(Pu - d["P"]).max())
        cosang = np.clip((Nu * d["N"]).sum(1) / np.linalg.norm(Nu, axis=1) / np.linalg.norm(d["N"], axis=1), -1, 1)
        dn = float(np.degrees(np.arccos(cosang)).max())
        Ip = d["tri"].astype(np.int64)
        same_sets = bool(np.array_equal(np.sort(Iu, 1), np.sort(Ip, 1)))
        reversed_order = bool(np.array_equal(Iu[:, [0, 2, 1]], Ip))
        tol = d["quant_half_step_m"] + 1e-3
        out.append(dict(record=r, frame=it["frame"], nv=int(len(Pu)), nt=int(len(Iu)), pos_max_diff_m=dp, quant_half_step_m=d["quant_half_step_m"],
                        pos_tol_m=tol, normal_max_diff_deg=dn, tri_same_vertex_sets=same_sets, tri_winding_reversed_only=reversed_order,
                        passed=bool(dp <= tol and dn <= 0.5 and same_sets and reversed_order)))
    return out


def v2(caps=("capture",)):
    res = {}
    for cap in caps:
        for name in ("seat", "print", "move", "seat3", "cseat", "cprint", "cmove"):
            p = C.OUT + "/%s/%s/frames.csv" % (cap, name)
            if not os.path.exists(p):
                continue
            cj = json.load(open(C.OUT + "/%s/%s/capture.json" % (cap, name), encoding="utf8"))
            cdir = cj.get("dataDir") or (C.OUT + "/clip_DA3_k5")
            man = json.load(open(os.path.join(cdir, "manifest.json"), encoding="utf8"))
            rows = list(csv.DictReader(open(p, encoding="utf8")))
            rec = np.array([int(r["record"]) for r in rows]); ph = np.array([float(r["phase"]) for r in rows])
            frz = np.array([int(r["frozen"]) for r in rows])
            # frames.csv の位相は小数 5 桁（丸めの誤差 ≤ 5e-6 s）。24 個/s では φ × 24 の境で丸めが floor を 1 つ下げるので、その分（1e-5 s × record_fps）だけ許す
            # （Unity は丸める前の位相に 1e-6 を足して floor している）
            rule_ok = bool(np.all(rec == np.minimum(man["frames"] - 1, np.floor(ph * man["record_fps"] + 1e-5 * man["record_fps"] + 1e-6).astype(int))))
            hold_expected = int(round(float(cj["fps"]) / man["record_fps"]))
            runs = []
            k = 0
            while k < len(rec):
                j = k
                while j + 1 < len(rec) and rec[j + 1] == rec[k]:
                    j += 1
                runs.append((int(rec[k]), j - k + 1, bool(frz[k:j + 1].any()), k == 0 or j == len(rec) - 1))
                k = j + 1
            inner = [n for (r, n, fz, edge) in runs if not fz and not edge]
            res[name if cap == "capture" else cap + "/" + name] = dict(
                frames=len(rows), record_fps=man["record_fps"], clip=os.path.basename(cdir.rstrip("/")), rule_record_eq_floor_phase_x_record_fps=rule_ok,
                runs=len(runs), run_len_counts={str(v): int(inner.count(v)) for v in sorted(set(inner))}, hold_expected_frames=hold_expected,
                all_inner_runs_eq_hold=bool(all(n == hold_expected for n in inner)),
                records_shown=int(len(set(rec.tolist()))), print_record_shown=bool((rec == man["print_record_index"]).any()),
                frozen_frames=int(frz.sum()), frozen_record=(sorted(set(rec[frz > 0].tolist())) if frz.any() else []),
                frozen_record_eq_print=bool(frz.any() and set(rec[frz > 0].tolist()) == {man["print_record_index"]}))
            if name.startswith("c"):
                # 続けて再生：止め以外で記録が 1 つずつ増える・範囲の全部を 1 回ずつ・コマが manifest と同じ・予定の記録を見せた
                key = name if cap == "capture" else cap + "/" + name
                nf = rec[frz == 0]
                steps = np.diff(nf)
                sf = np.array([int(r["sim_frame"]) for r in rows])
                want = np.array([int(r["wanted"]) for r in rows])
                src = man.get("source_frames")
                moves = cj.get("moves") or []
                res[key].update(
                    continuous=True, play_from_sim=cj.get("playFromSim"), play_to_sim=cj.get("playToSim"),
                    record_first=int(rec[0]), record_last=int(rec[-1]),
                    nonfrozen_steps_all_plus1=bool(len(steps) == 0 or np.all(steps == 1)),
                    each_record_once_outside_holds=bool(len(set(nf.tolist())) == len(nf)),
                    sim_frame_eq_manifest=bool(src is not None and all(src[a] == b for a, b in zip(rec.tolist(), sf.tolist()))),
                    shown_eq_wanted=bool(np.all(want == rec)),
                    frozen_records=sorted(set(rec[frz > 0].tolist())),
                    moves=moves, frozen_records_eq_moves=bool(set(rec[frz > 0].tolist()) == set(m["record"] for m in moves)) if name == "cmove" else None,
                    seconds=float(cj["seconds"]))
    return res


def v3(tag):
    res = {}
    d0 = C.OUT + "/timing/" + tag
    import glob
    for p in sorted(glob.glob(d0 + "/*.json")):
        m = os.path.basename(p)[:-5]
        if m == "run_summary":
            continue
        d = json.load(open(p, encoding="utf-8-sig"))
        if not d.get("dtMs"):
            res[m] = dict(error=d.get("streamError"), note=d.get("noteJa"))
            continue
        dt = np.array(d["dtMs"])
        res[m] = dict(screen="%dx%d" % (d["screenWidth"], d["screenHeight"]), device=d["device"], api=d["graphicsApi"], cpu=d["cpuName"], debug=d["isDebugBuild"],
                      vsync=d["vSyncCount"], frames=d["frames"], seconds=d["measuredSeconds"], record_swaps=d["recordSwaps"], swaps_per_s=d["recordSwaps"] / d["measuredSeconds"],
                      dt_ms=dict(p50=d["dt"]["p50"], p95=d["dt"]["p95"], p99=d["dt"]["p99"], max=d["dt"]["max"]),
                      gpu_ms=dict(p50=d["gpu"]["p50"], p95=d["gpu"]["p95"], p99=d["gpu"]["p99"], max=d["gpu"]["max"]) if d["frameTimingAvailable"] else None,
                      swap_ms_on_swap_frames=dict(p50=d["swapFramesOnly"]["p50"], max=d["swapFramesOnly"]["max"]),
                      over_11_1ms=int((dt > 11.1).sum()), over_16_7ms=int((dt > 16.7).sum()), over_5ms=int((dt > 5).sum()),
                      load_s=d["loadSeconds"], clip_MB=d["clipMB"], tiles=d["tilesPerSide"], record_fps=d.get("recordFps"), data=d.get("dataDir"))
        tf = d.get("targetFrameRate") or -1
        if tf > 0:
            # 2026-10-16 確かめで足した：-f3dtargetfps で上限を付けた時は、どのフレームも約 1/n s なので 11.1 ms 越えの数は意味がない。1.5 拍を越えた数を見る
            res[m].update(target_fps=tf, beat_ms=1000.0 / tf, over_1p5_beats=int((dt > 1500.0 / tf).sum()), over_2_beats=int((dt > 2000.0 / tf).sum()))
        if d.get("playback") is not None:
            res[m].update(playback=d["playback"], clip_kind=d.get("clipKind"), schedule=d.get("schedule"), play=[d.get("playFromSim"), d.get("playLastSim")],
                          experience_s=d.get("experienceSeconds"), ended=d.get("ended"), streaming=d.get("streaming"))
        if d.get("streaming"):
            S = lambda k: dict(n=d[k]["n"], p50=d[k]["p50"], p95=d[k]["p95"], p99=d[k]["p99"], max=d[k]["max"]) if d.get(k) else None
            res[m].update(ring=d["ring"], split_level=d.get("splitLevel"), index16=d.get("index16"), miss_frames=d["missFrames"], late_records=d["lateRecords"],
                          records_skipped=d.get("recordsSkipped"), distinct_records_shown=d.get("distinctRecordsShown"), uploads=d["uploads"], upload_ops=d.get("uploadOps"),
                          urgent_uploads=d["urgentUploads"], upload_ms=S("upload"), dt_on_upload_frames=S("dtOnUploadFrames"), dt_on_other_frames=S("dtOnOtherFrames"),
                          read_ms=S("readMs"), decode_ms=S("decodeMs"), sha_ms=S("shaMs"), read_MBps_while_reading=d.get("readMBpsWhileReading"),
                          loader_busy_fraction=d.get("loaderBusyFraction"), records_read=d.get("recordsRead"), bytes_read=d.get("bytesRead"),
                          sha_checked=d.get("shaChecked"), sha_mismatches=d.get("shaMismatches"), stream_error=d.get("streamError"),
                          prefill_s=d.get("prefillSeconds"), mem_start=d.get("memStart"), mem_peak=d.get("memPeak"), mem_end=d.get("memEnd"), bench=d.get("bench"))
    return res


def v4_hash():
    """manifest の全部の記録の SHA-256 を読み直して比べる（GW45LIST1 は記録のファイル、GW45CLP1 はクリップの中の位置）。"""
    import hashlib, struct, time as _t
    cdir = C.OUT + "/" + CLIP
    man = json.load(open(cdir + "/manifest.json", encoding="utf8"))
    t0 = _t.time()
    shas = man["source_sha256"]
    ok = 0
    nbytes = 0
    if man["format"] == "GW45LIST1":
        sd = os.path.normpath(os.path.join(cdir, man["stream_dir_rel"])) if man.get("stream_dir_rel") else man["stream_dir"]
        pat = man.get("stream_pattern") or "s_{0:D5}.gw45s"
        for i, f in enumerate(man["source_frames"]):
            b = open(os.path.join(sd, "s_%05d.gw45s" % f), "rb").read()
            nbytes += len(b)
            ok += hashlib.sha256(b).hexdigest() == shas[i] and len(b) == man["source_bytes"][i]
        where = sd
    else:
        with open(cdir + "/" + man["clip_file"], "rb") as fh:
            for i in range(man["frames"]):
                fh.seek(64 + 16 * i)
                o, L, _ = struct.unpack("<QII", fh.read(16))
                fh.seek(o)
                b = fh.read(L)
                nbytes += len(b)
                ok += hashlib.sha256(b).hexdigest() == shas[i]
        where = cdir + "/" + man["clip_file"]
    return dict(clip=CLIP, format=man["format"], records=man["frames"], sha_equal=int(ok), all_equal=bool(ok == man["frames"]), bytes=nbytes,
                seconds=round(_t.time() - t0, 1), where=where)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = sys.argv[1:]

    def opt(k, d):
        return a[a.index(k) + 1] if k in a else d
    tag = a[0] if a and not a[0].startswith("--") else "t1"
    CLIP = opt("--clip", CLIP)
    VD = C.OUT + "/" + opt("--vdir", "verify")
    caps = tuple(opt("--cap", "capture").split(","))
    # 2026-10-16 確かめで足した：tag をコンマで並べると、V3 を tag ごとに書く（1 つなら前と同じ形）
    tags = tag.split(",")
    out = dict(V1_decode=v1(), V2_record_hold=v2(caps), V3_timing=(v3(tags[0]) if len(tags) == 1 else {t: v3(t) for t in tags}))
    if "--hash" in a:
        out["V4_hash"] = v4_hash()
    C.write_json(VD + "/verify_result.json", out)
    print(json.dumps(out, ensure_ascii=False, indent=1))
