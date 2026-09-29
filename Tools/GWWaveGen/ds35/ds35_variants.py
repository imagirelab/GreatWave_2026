# -*- coding: utf-8 -*-
"""設計35（variants の部）：数量・大きさ・寿命を変えた 3 版の爪と飛沫のデータを作る（numpy。Unity の描画ではない）。

計画 §2.2 設計35：「3版（一覧どおり／数を減らした軽量版／大きさ・寿命を誇張した版）の並べ動画と、最大密度の区間の性能」。
D2＝(b)（美術主導の rig）なので、設計書の「物理版」はない（ここでも作らない）。

3 版（白の帯＝主役波のシートの色 T_white は 3 版とも設計31 のまま。変えるのは爪と飛沫だけ）：
  V1 一覧どおり（list）  ：設計33 の爪 148 本と設計31 の飛沫 v0 186 個をそのまま参照する（複製しない）。
  V2 軽量版（light）     ：爪は群（主爪＋支）を t* の長さ len_m の大きい順に取り、本数が半分（74 本）に届くまで残す。
                           飛沫は半径の大きい順に半分（93 個）を残す。残した爪・粒は V1 と同じ値（部分集合）。
  V3 誇張版（exag）      ：爪は ds33_claw_anim と同じ式で作り直し、幅と厚み（根元の白の円も）× 1.5、長さ × 1.3
                           （根元からの (行, 列) のずれと、空へ出る関節の局所のずれを × 1.3。根元は設計32 の sheet_rc のまま）、
                           寿命 × 1.6（成長の始まり τ_start × 1.6。早く出て長く育つ。t = 0 の τ より 0.3 s 後で頭打ち）。
                           飛沫は半径 × 1.6、放出を早める（τ_e × 1.6）：同じ放出の頂点（設計31 の emitter の行・列）の τ_e′ の位置から、
                           原画の点の位置 p* へ t* に着く逆弾道を解き直す（重力はそのまま）。設計31 の check_paths（150：水面へ引き戻されない、
                           水の側へ入らない、放出の後に離れる）で確かめ、通らなければ τ_e を元のままにして解き直し、それも通らなければ元の経路
                           （半径だけ × 1.6）にする。
出力（Git 対象外）：Unity/Build/Design/35/variants/data/{v2_light,v3_exag}/ と variants_summary.json。
"""
import argparse
import json
import math
import os
import shutil
import sys
import time

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds33")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds31")
import ds33_common as U  # noqa: E402
import ds33_claw_rig as G  # noqa: E402
import ds33_claw_anim as A  # noqa: E402

OUT = REPO + "/Unity/Build/Design/35/variants/data"
D33 = REPO + "/Unity/Build/Design/33/claws"
D31 = REPO + "/Unity/Build/Design/31/spray"
P = dict(light_claw_frac=0.5, light_spray_frac=0.5,
         exag_width=1.5, exag_length=1.3, exag_life=1.6, exag_tau_floor_after_t0_s=0.3,
         exag_spray_radius=1.6, exag_spray_life=1.6)


def sha(p):
    return U.sha(p)


def write_layout(d, name, V, tris, attr, claws_meta, note):
    os.makedirs(d, exist_ok=True)
    V.astype(np.float32).tofile(os.path.join(d, "claw_frames_f32.bin"))
    tris.astype(np.int32).tofile(os.path.join(d, "claw_tris_i32.bin"))
    attr.astype(np.uint16).tofile(os.path.join(d, "claw_tri_attr_u16.bin"))
    lay = dict(schema="GreatWave.DS33.claw_layout/1", variant=name, note_ja=note, frames=int(V.shape[0]), hz=U.FPS,
               vertices=int(V.shape[1]), triangles=int(len(tris)),
               clock_ja="コマ k は t = k/30 s、τ = τ(t)（timewarp_F_final.json の線形補間）。t ≥ 12 s は τ = 0（設計33 と同じ）",
               claws=claws_meta,
               files=dict(frames=dict(file="claw_frames_f32.bin"), tris=dict(file="claw_tris_i32.bin"), tri_attr=dict(file="claw_tri_attr_u16.bin")))
    for k in ("frames", "tris", "tri_attr"):
        p = os.path.join(d, lay["files"][k]["file"])
        lay["files"][k]["sha256"] = sha(p); lay["files"][k]["bytes"] = os.path.getsize(p)
    U.jdump(os.path.join(d, "claw_layout.json"), lay)
    return lay


def write_particles(d, frames, colour, note):
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "spray_frames.bin")
    frames.astype("<f4").tofile(p)
    j = dict(schema="GreatWave.DS31.particles/1", frames=int(frames.shape[0]), hz=U.FPS, t0=0.0, count=int(frames.shape[1]),
             file="spray_frames.bin", sha256=sha(p), bytes=os.path.getsize(p), colour=colour, note_ja=note,
             layout_ja="float32 リトルエンディアン、コマ × 数 × 4（x, y, z, 半径）。ワールドの m。半径 0 は描かない（設計31 と同じ書式）")
    U.jdump(os.path.join(d, "spray_frames.json"), j)
    return j


def claw_meta(lay33, keep):
    out, off = [], 0
    for new_i, i in enumerate(keep):
        c = lay33["claws"][i]
        out.append(dict(id=c["id"], index=new_i, src_index=int(i), vert_offset=off, vert_count=c["vert_count"], stations=c["stations"], type=c["type"]))
        off += c["vert_count"]
    return out


def light_claws(lay33, rig, V33, tris33, attr33):
    claws = rig["claws"]
    ids = [c["id"] for c in claws]
    assert ids == [c["id"] for c in lay33["claws"]]
    idx = {c["id"]: i for i, c in enumerate(claws)}
    # 群：主爪（parent なし）と、その支
    groups = []
    for i, c in enumerate(claws):
        if c["parent"] is None:
            mem = [i] + [idx[ch] for ch in c["children"] if ch in idx]
            groups.append((float(c["len_m"]), mem))
    orphan = [i for i, c in enumerate(claws) if c["parent"] is not None and c["parent"] not in idx]
    groups += [(float(claws[i]["len_m"]), [i]) for i in orphan]
    groups.sort(key=lambda g: -g[0])
    target = int(round(P["light_claw_frac"] * len(claws)))
    keep = []
    for _, mem in groups:
        if len(keep) >= target:
            break
        keep += mem
    keep = sorted(keep)
    # 頂点と三角形を取り出す（頂点の番号を詰め直す）
    vsel, remap = [], -np.ones(V33.shape[1], np.int64)
    n = 0
    for i in keep:
        c = lay33["claws"][i]
        o, k = c["vert_offset"], c["vert_count"]
        remap[o:o + k] = np.arange(n, n + k); vsel.append(np.arange(o, o + k)); n += k
    vsel = np.concatenate(vsel)
    tmask = np.isin(attr33[:, 0], keep)
    tris = remap[tris33[tmask]]
    assert (tris >= 0).all()
    newc = -np.ones(len(claws), np.int64); newc[keep] = np.arange(len(keep))
    attr = attr33[tmask].copy(); attr[:, 0] = newc[attr[:, 0]]
    V = np.asarray(V33[:, vsel, :])
    return keep, V, tris, attr


def exag_claws(rig, Z, tris33, attr33):
    """ds33_claw_anim.main のメッシュの部分と同じ式で、幅・長さ・寿命を誇張して作り直す（検査の部分は写さない）。"""
    t0 = time.time()
    svals = Z["svals"]; Ms = len(svals)
    Pr = rig["params"]; cfrac = Pr["band_center_frac"]; lift = Pr["skirt"]["lift_m"]
    claws = rig["claws"]; nc = len(claws)
    hero = U.K.Pkg(U.HERO); R, C = hero.R, hero.C
    warp = U.jload(U.WARP)
    taus = np.interp(np.arange(U.NFR) / U.FPS, np.array(warp["t"]), np.array(warp["tau"]))
    offs, nv = [], 0
    for c in claws:
        offs.append((nv, c["n_vert"])); nv += c["n_vert"]
    V = np.zeros((U.NFR, nv, 3), np.float32)
    rc0 = np.array([c["sheet_rc"] for c in claws], np.float64)
    tau_s0 = np.array([c["tau_start"] for c in claws])
    tau_s = np.maximum(tau_s0 * P["exag_life"], taus[0] + P["exag_tau_floor_after_t0_s"])
    Ls, Ws = P["exag_length"], P["exag_width"]
    data = []
    for c in claws:
        cid = c["id"]
        data.append(dict(RC=Z["RC_" + cid], E=Z["E_" + cid], NL=Z["NL_" + cid], W=Z["W_" + cid], TH=Z["TH_" + cid], SK=Z["SK_" + cid],
                         ref=np.array(c["joint_ref"]), n_st=c["stations"], bound=np.array([k == "sheet" for k in c["joint_kind"]]), hanging=c["hanging"]))
    vis_count = np.zeros(U.NFR, np.int64)
    nan_count = 0
    root_max = 0.0
    for f, tau in enumerate(taus):
        X = hero.world(float(tau))
        s_all = np.clip((tau - tau_s) / (0.0 - tau_s), 0.0, 1.0)
        vis = tau >= tau_s
        vis_count[f] = int(vis.sum())
        g_all, k_all, w_all = G.growth_curves(s_all)
        for i, c in enumerate(claws):
            d = data[i]
            o, n = offs[i]
            root = U.tri_eval(X, np.array(rc0[i, 0]), np.array(rc0[i, 1]))
            if not vis[i]:
                V[f, o:o + n] = root
                continue
            m = s_all[i] * (Ms - 1)
            m0 = int(min(math.floor(m), Ms - 2)); fm = m - m0
            RCs = d["RC"][m0] * (1 - fm) + d["RC"][m0 + 1] * fm
            Es = (d["E"][m0] * (1 - fm) + d["E"][m0 + 1] * fm) * Ls
            RCs = rc0[i][None, :] + Ls * (RCs - rc0[i][None, :])
            RCs[:, 0] = np.clip(RCs[:, 0], 0, R - 1); RCs[:, 1] = np.clip(RCs[:, 1], 0, C - 1)
            RCs[0] = rc0[i]
            ref = d["ref"]
            rr, cc = RCs[ref, 0], RCs[ref, 1]
            S = U.tri_eval(X, rr, cc)
            F = U.frame_at(X, rr, cc)
            J = S + np.einsum("kji,kj->ki", F, Es)
            J[0] = root
            Nj = np.einsum("kji,kj->ki", F, d["NL"])
            kb = d["bound"]

            def snap(St, Ns, sseg, sfr, X=X, RCs=RCs, kb=kb, hang=d["hanging"]):
                sel = kb[sseg] & kb[sseg + 1]
                sel[0] = False
                if not sel.any():
                    return St, Ns
                rc_i = RCs[sseg[sel]] * (1 - sfr[sel])[:, None] + RCs[sseg[sel] + 1] * sfr[sel][:, None]
                r_, c_, _, _ = U.project_to_sheet(X, St[sel], rc_i, iters=8, max_step=2.0)
                St = St.copy(); Ns = Ns.copy()
                St[sel] = U.tri_eval(X, r_, c_)
                if not hang:
                    Ns[sel] = U.normal_at(X, r_, c_)
                return St, Ns
            ring, tip, L, _ = A.sweep(J, Nj, d["W"] * w_all[i] * Ws, d["TH"] * w_all[i] * Ws, d["n_st"], cfrac, snap)
            drc = d["SK"] * w_all[i] * Ws
            rcs = rc0[i][None, :] + drc
            rcs[:, 0] = np.clip(rcs[:, 0], 0, R - 1); rcs[:, 1] = np.clip(rcs[:, 1], 0, C - 1)
            skp = U.tri_eval(X, rcs[:, 0], rcs[:, 1]) + lift * U.normal_at(X, rcs[:, 0], rcs[:, 1])
            vv = np.concatenate([root[None, :], ring.reshape(-1, 3), tip[None, :], skp], 0)
            if not np.all(np.isfinite(vv)):
                nan_count += 1
            V[f, o:o + n] = vv
            root_max = max(root_max, float(np.linalg.norm(vv[0] - root)))
        if f % 60 == 0:
            print("exag claws frame %d  %.1fs" % (f, time.time() - t0), flush=True)
    return V, tau_s0, tau_s, vis_count, nan_count, root_max


def spray_frames_from(tab, taus, G3):
    n = len(tab["tau_e"])
    out = np.zeros((len(taus), n, 4), np.float32)
    for f, tau in enumerate(taus):
        t_ = min(float(tau), 0.0)
        dt = np.maximum(t_ - tab["tau_e"], 0.0)[:, None]
        pos = tab["p_e"] + tab["v0"] * dt + 0.5 * G3 * dt * dt
        s = np.clip((t_ - tab["tau_show"]) / tab["ramp_s"], 0.0, 1.0)
        s = s * s * (3 - 2 * s)
        rad = np.where(t_ >= tab["tau_show"], tab["radius"] * s, 0.0)
        out[f, :, :3] = pos; out[f, :, 3] = rad
    return out


def exag_spray(table, taus):
    import ds31_spray as SP  # noqa: E402（設計31 の生成器の check_paths・Pkg を借りる。書き出しはしない）
    hero = SP.K.Pkg(SP.HERO_PKG)
    near = SP.K.Pkg(os.path.join(SP.SEA_DIR, "near"))
    G3 = SP.G
    kr, kl = P["exag_spray_radius"], P["exag_spray_life"]
    tau_lo_limit = float(taus[0])

    def solve(t, tau_e, rad):
        em = t["emitter"]
        r, c = em["row"], em["col"]
        X = hero.world(float(tau_e))
        N = SP.grid_normals(X)
        pe = X[r, c] + N[r, c] * (rad + SP.P["emit_offset_m"])
        dt = -tau_e
        v0 = (np.array(t["p_star"]) - pe) / dt - 0.5 * G3 * dt
        return dict(p_e=pe.tolist(), v0=v0.tolist(), tau_e=float(tau_e), radius=float(rad))

    cands = []
    for i, t in enumerate(table):
        rad = t["radius_m"] * kr
        te_long = max(t["tau_e"] * kl, tau_lo_limit + 0.1)
        if t["mode"] != "ballistic" or t.get("emitter") is None:
            cands.append([dict(p_e=t["p_e"], v0=t["v0"], tau_e=t["tau_e"], radius=rad, how="orig", life_factor=1.0)])
            continue
        qs = []
        for fac, hw in ((kl, "long"), (1.0 + 0.66 * (kl - 1.0), "long_mid"), (1.0 + 0.33 * (kl - 1.0), "long_low")):
            q = solve(t, max(t["tau_e"] * fac, tau_lo_limit + 0.1), rad); q["how"] = hw; q["life_factor"] = fac; qs.append(q)
        b = solve(t, t["tau_e"], rad); b["how"] = "same_tau"; b["life_factor"] = 1.0
        c_ = dict(p_e=t["p_e"], v0=t["v0"], tau_e=t["tau_e"], radius=rad, how="orig", life_factor=1.0)
        d_ = dict(p_e=t["p_e"], v0=t["v0"], tau_e=t["tau_e"], radius=t["radius_m"], how="orig_radius1", life_factor=1.0)
        cands.append(qs + [b, c_, d_])
    flat = [(i, q) for i, qs in enumerate(cands) for q in qs]
    tau_lo = min(q["tau_e"] for _, q in flat)
    chk = SP.check_paths([q for _, q in flat], hero, near, tau_lo)
    ok = (chk["contact"] == 0) & (chk["inside"] == 0) & (chk["never_left"] == 0)
    chosen = {}
    for j, (i, q) in enumerate(flat):
        q["ok150"] = bool(ok[j]); q["contact"] = int(chk["contact"][j]); q["inside"] = int(chk["inside"][j]); q["never_left"] = int(chk["never_left"][j])
        if i not in chosen and ok[j]:
            chosen[i] = q
    how = dict(long=0, long_mid=0, long_low=0, same_tau=0, orig=0, orig_radius1=0, orig_failed150=0)
    sel = []
    for i, qs in enumerate(cands):
        if i in chosen:
            q = chosen[i]
        else:
            q = qs[-1]; how["orig_failed150"] += 1
        how[q["how"]] += 1
        sel.append(q)
    tab = dict(p_e=np.array([q["p_e"] for q in sel]), v0=np.array([q["v0"] for q in sel]), tau_e=np.array([q["tau_e"] for q in sel]),
               tau_show=np.array([q["tau_e"] for q in sel]), ramp_s=np.array([t["ramp_s"] for t in table]), radius=np.array([q["radius"] for q in sel]))
    fr = spray_frames_from(tab, taus, G3)
    life0 = -np.array([t["tau_e"] for t in table]); life1 = -tab["tau_e"]
    info = dict(how=how, life_s_orig=[float(life0.min()), float(np.median(life0)), float(life0.max())],
                life_s_exag=[float(life1.min()), float(np.median(life1)), float(life1.max())],
                life_ratio_median=float(np.median(life1 / life0)), life_ratio_mean=float(np.mean(life1 / life0)),
                radius_ratio=[float((tab["radius"] / np.array([t["radius_m"] for t in table])).min()), float((tab["radius"] / np.array([t["radius_m"] for t in table])).max())],
                rule_ja="粒ごとに候補を寿命の倍率 1.6・1.4・1.2・1.0（同じ τ_e で半径だけ大きく解き直す）・元の経路（半径 × 1.6）・元の経路と元の半径の順に、"
                        "設計31 の check_paths（150）を通る最初のものを採る",
                radius_m_exag=[float(tab["radius"].min()), float(tab["radius"].max())],
                check150=dict(chosen_contact=int(sum(q["contact"] for q in sel)), chosen_inside=int(sum(q["inside"] for q in sel)),
                              chosen_never_left=int(sum(q["never_left"] for q in sel)), chosen_orig_failed150=how["orig_failed150"]))
    return fr, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="light,exag_claws,exag_spray")
    a = ap.parse_args()
    parts = set(a.parts.split(","))
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    lay33 = U.jload(os.path.join(D33, "ds33_claw_layout.json"))
    rig = U.jload(os.path.join(D33, "ds33_claw_rig.json"))
    Z = np.load(os.path.join(D33, "ds33_claw_rig.npz"))
    nv33 = lay33["vertices"]
    V33 = np.memmap(os.path.join(D33, lay33["files"]["frames"]["file"]), dtype="<f4", mode="r", shape=(lay33["frames"], nv33, 3))
    tris33 = np.fromfile(os.path.join(D33, lay33["files"]["tris"]["file"]), np.int32).reshape(-1, 3).astype(np.int64)
    attr33 = np.fromfile(os.path.join(D33, lay33["files"]["tri_attr"]["file"]), np.uint16).reshape(-1, 2).astype(np.int64)
    sp31 = U.jload(os.path.join(D31, "ds31_spray_frames.json"))
    F31 = np.fromfile(os.path.join(D31, sp31["file"]), "<f4").reshape(sp31["frames"], sp31["count"], 4)
    table = U.jload(os.path.join(D31, "ds31_spray_table.json"))
    table = table["particles"]
    warp = U.jload(U.WARP)
    taus = np.interp(np.arange(U.NFR) / U.FPS, np.array(warp["t"]), np.array(warp["tau"]))
    sk33 = np.fromfile(os.path.join(D33, "ds33_claw_skel_f32.bin"), np.float32).reshape(U.NFR, -1, 36)
    summ_p = os.path.join(OUT, "variants_summary.json")
    summ = U.jload(summ_p) if os.path.exists(summ_p) else {}
    summ.update(schema="GreatWave.DS35.variants/1", number="設計35 variants の部", params=P,
                inputs=dict(claw_layout=U.rel(os.path.join(D33, "ds33_claw_layout.json")), claw_frames_sha256=lay33["files"]["frames"]["sha256"],
                            claw_rig_sha256=sha(os.path.join(D33, "ds33_claw_rig.json")), claw_rig_npz_sha256=sha(os.path.join(D33, "ds33_claw_rig.npz")),
                            spray_frames=U.rel(os.path.join(D31, "ds31_spray_frames.json")), spray_frames_sha256=sp31["sha256"],
                            spray_table_sha256=sha(os.path.join(D31, "ds31_spray_table.json")), timewarp_sha256=sha(U.WARP),
                            code_sha256={os.path.basename(__file__): sha(os.path.abspath(__file__))}))
    summ.setdefault("variants", {})
    summ["variants"]["v1_list"] = dict(name_ja="一覧どおり", claw_layout=U.rel(os.path.join(D33, "ds33_claw_layout.json")),
                                        spray=U.rel(os.path.join(D31, "ds31_spray_frames.json")), claws=len(lay33["claws"]), claw_vertices=nv33,
                                        claw_triangles=lay33["triangles"], spray_count=sp31["count"],
                                        claws_visible_per_s=[int((sk33[k, :, 34] > 0.5).sum()) for k in range(0, U.NFR, 30)],
                                        spray_alive_per_s=[int((F31[k, :, 3] > 0).sum()) for k in range(0, U.NFR, 30)],
                                        spray_radius_m=[float(F31[-1, :, 3].min()), float(F31[-1, :, 3].max())])

    if "light" in parts:
        keep, V, tris, attr = light_claws(lay33, rig, V33, tris33, attr33)
        d = os.path.join(OUT, "v2_light")
        meta = claw_meta(lay33, keep)
        write_layout(d, "v2_light", V, tris, attr, meta, "設計35 V2 軽量版：設計33 の爪のうち、群（主爪＋支）を t* の長さの大きい順に半分まで残した部分集合（値は設計33 と同じ）")
        rad = F31[-1, :, 3]
        ksp = np.sort(np.argsort(-rad, kind="stable")[:int(round(P["light_spray_frac"] * sp31["count"]))])
        write_particles(d, F31[:, ksp, :], sp31["colour"], "設計35 V2 軽量版：設計31 の飛沫 v0 のうち、半径の大きい順に半分を残した部分集合（値は設計31 と同じ）")
        vis = (sk33[:, keep, 34] > 0.5).sum(1)
        summ["variants"]["v2_light"] = dict(name_ja="数を減らした軽量版", claw_layout=U.rel(os.path.join(d, "claw_layout.json")), spray=U.rel(os.path.join(d, "spray_frames.json")),
                                             claws=len(keep), claw_ids=[lay33["claws"][i]["id"] for i in keep], claw_vertices=int(V.shape[1]), claw_triangles=int(len(tris)),
                                             spray_count=int(len(ksp)), spray_dot_rows=[int(i) for i in ksp],
                                             claws_visible_per_s=[int(vis[k]) for k in range(0, U.NFR, 30)],
                                             spray_alive_per_s=[int((F31[k, ksp, 3] > 0).sum()) for k in range(0, U.NFR, 30)],
                                             rule_ja="爪：主爪（parent なし）と支を 1 群とし、主爪の len_m（t* の 3 次元の長さ）の大きい順に、残す本数が 148 × 0.5 = 74 本に届くまで取る。"
                                                     "飛沫：t* の半径の大きい順に 186 × 0.5 = 93 個。どちらも V1 の値をそのまま使う部分集合")
        print("light", len(keep), V.shape, len(ksp), "%.1fs" % (time.time() - t0), flush=True)
        del V

    if "exag_claws" in parts:
        V, ts0, ts1, visc, nanc, rootmax = exag_claws(rig, Z, tris33, attr33)
        d = os.path.join(OUT, "v3_exag")
        meta = claw_meta(lay33, list(range(len(lay33["claws"]))))
        write_layout(d, "v3_exag", V, tris33, attr33, meta, "設計35 V3 誇張版：設計33 の式で、幅・厚み × 1.5、長さ × 1.3、成長の始まり τ_start × 1.6 で作り直した爪")
        life0 = -ts0; life1 = -ts1
        # t* の長さ（根元から先端の輪の中心までの折れ線、V1 と V3 の比）
        def arc(Vf, lay):
            out = []
            for c in lay["claws"]:
                o, n, st = c["vert_offset"], c["vert_count"], c["stations"]
                ctr = Vf[o + 1:o + 1 + st * 8].reshape(st, 8, 3).mean(1)
                pts = np.concatenate([Vf[o:o + 1], ctr, Vf[o + 1 + st * 8:o + 2 + st * 8]], 0)
                out.append(float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum()))
            return np.array(out)
        a1 = arc(np.asarray(V33[360], np.float64), lay33); a3 = arc(V[360].astype(np.float64), lay33)
        summ["variants"]["v3_exag"] = dict(name_ja="大きさ・寿命を誇張した版", claw_layout=U.rel(os.path.join(d, "claw_layout.json")),
                                            claws=len(lay33["claws"]), claw_vertices=int(V.shape[1]), claw_triangles=int(len(tris33)),
                                            claws_visible_per_s=[int(visc[k]) for k in range(0, U.NFR, 30)],
                                            claw_life_s_orig_tau=[float(life0.min()), float(np.median(life0)), float(life0.max())],
                                            claw_life_s_exag_tau=[float(life1.min()), float(np.median(life1)), float(life1.max())],
                                            claw_first_visible_t_s=float(np.argmax(visc > 0) / U.FPS),
                                            claw_first_visible_t_s_v1=float(np.argmax((sk33[:, :, 34] > 0.5).sum(1) > 0) / U.FPS),
                                            claw_arc_ratio_tstar_median=float(np.median(a3 / np.maximum(a1, 1e-9))),
                                            claw_arc_m_tstar_median=[float(np.median(a1)), float(np.median(a3))],
                                            claw_nan_claw_frames=int(nanc), claw_root_offset_max_m=rootmax,
                                            rule_ja="爪：ds33_claw_anim と同じ式（関節の (行, 列) と局所のずれ → そのコマのシートで作り直し、帯の輪・根元の白の円）で、"
                                                    "輪の幅・厚み・根元の白の円 × 1.5、根元からの (行, 列) のずれと局所のずれ × 1.3、成長の始まり τ_start × 1.6"
                                                    "（t = 0 の τ + 0.3 s で頭打ち）。根元は設計32 の sheet_rc のまま（シートの上）")
        print("exag claws done %.1fs" % (time.time() - t0), flush=True)
        del V

    if "exag_spray" in parts:
        fr, info = exag_spray(table, taus)
        d = os.path.join(OUT, "v3_exag")
        write_particles(d, fr, sp31["colour"], "設計35 V3 誇張版：設計31 の飛沫 v0 の半径 × 1.6、放出を早めて（τ_e × 1.6）同じ頂点から p* へ逆弾道を解き直したもの")
        v3 = summ["variants"].setdefault("v3_exag", {})
        v3.update(spray=U.rel(os.path.join(d, "spray_frames.json")), spray_count=int(fr.shape[1]),
                  spray_alive_per_s=[int((fr[k, :, 3] > 0).sum()) for k in range(0, U.NFR, 30)],
                  spray_first_visible_t_s=float(np.argmax((fr[:, :, 3] > 0).sum(1) > 0) / U.FPS),
                  spray_first_visible_t_s_v1=float(np.argmax((F31[:, :, 3] > 0).sum(1) > 0) / U.FPS),
                  spray_info=info)
        print("exag spray", info["how"], "%.1fs" % (time.time() - t0), flush=True)

    summ["elapsed_s_last"] = round(time.time() - t0, 1)
    U.jdump(summ_p, summ)
    print("done %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
