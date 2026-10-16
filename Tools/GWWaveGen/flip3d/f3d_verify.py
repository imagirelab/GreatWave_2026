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
        for name in ("seat", "print", "move", "seat3"):
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
    return res


def v3(tag):
    res = {}
    d0 = C.OUT + "/timing/" + tag
    for m in ("seat", "move", "print", "seat8", "move8"):
        p = d0 + "/%s.json" % m
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding="utf-8-sig"))
        dt = np.array(d["dtMs"])
        res[m] = dict(screen="%dx%d" % (d["screenWidth"], d["screenHeight"]), device=d["device"], api=d["graphicsApi"], cpu=d["cpuName"], debug=d["isDebugBuild"],
                      vsync=d["vSyncCount"], frames=d["frames"], seconds=d["measuredSeconds"], record_swaps=d["recordSwaps"], swaps_per_s=d["recordSwaps"] / d["measuredSeconds"],
                      dt_ms=dict(p50=d["dt"]["p50"], p95=d["dt"]["p95"], p99=d["dt"]["p99"], max=d["dt"]["max"]),
                      gpu_ms=dict(p50=d["gpu"]["p50"], p95=d["gpu"]["p95"], p99=d["gpu"]["p99"], max=d["gpu"]["max"]) if d["frameTimingAvailable"] else None,
                      swap_ms_on_swap_frames=dict(p50=d["swapFramesOnly"]["p50"], max=d["swapFramesOnly"]["max"]),
                      over_11_1ms=int((dt > 11.1).sum()), over_16_7ms=int((dt > 16.7).sum()), over_5ms=int((dt > 5).sum()),
                      load_s=d["loadSeconds"], clip_MB=d["clipMB"], tiles=d["tilesPerSide"], record_fps=d.get("recordFps"), data=d.get("dataDir"))
    return res


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
    out = dict(V1_decode=v1(), V2_record_hold=v2(caps), V3_timing=v3(tag))
    C.write_json(VD + "/verify_result.json", out)
    print(json.dumps(out, ensure_ascii=False, indent=1))
