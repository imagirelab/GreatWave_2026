# -*- coding: utf-8 -*-
"""美術の見本03 の作り B1（試し）：冠（OUT・IN）の手・指・袖を、根元の周りの主役波の面とひとつの塊にして、つなぎ目（掌と指の股・根元）に
丸み（フィレット）をつける版（_fused）。管の版（crown_build.py）と同じ手・指（同じ種・同じ数）から作る。
1. crown_build と同じ手順で冠を組む（同じ種）。2. 手・指・袖の閉じた管を parts.obj、根元の周りの主役波の面の板（面から下 0.5 m、
   行 ±7・列 ±10）を slabs.obj に書く。3. Houdini の hython（crown_fuse_h.py）で VDB の和・閉じ（半径 0.06 m）・なめらかにして多角形へ。
4. 主役波の面から 1.2 cm より下の面（板の上面・下面・横）を捨て、根元の丸い裾だけ残す（裾の縁は面の 1.2 cm 上で面に沿う）。
5. 利用者の爪（冠の役 48 本）は形を守るため塊に入れず、そのまま足す（袖は塊に入る）。
6. 属性（f・指の番号・種類）は最も近い元の管の頂点から写し、AO・光の見通しは管の版と同じ方法で計算し直す。
出力：Unity/Build/Polish/sample03/crown/<mode>_fused/（管の版と同じ書式）。
使い方：py -3.10 -B Tools/GWWaveGen/as03/crown_fuse.py --mode OUT [--voxel 0.025 --close 0.06]
"""
import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crown_build as CB  # noqa: E402
import crown_common as G  # noqa: E402
import crown_geom as GM  # noqa: E402

HYTHON = "G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe"


def slab_patch(h, r0, c0, dr=3, dc=5, depth=0.3):
    """主役波の格子の小さな区画を、面から下へ depth の閉じた板にする。"""
    ra = max(0, r0 - dr)
    rb = min(h.R - 1, r0 + dr)
    ca = max(G.BODY[0], c0 - dc)
    cb = min(G.BODY[1], c0 + dc)
    top = h.X[ra:rb + 1, ca:cb + 1]
    nn = h.N[ra:rb + 1, ca:cb + 1]
    bot = top - nn * depth
    m, n = top.shape[:2]
    V = np.concatenate([top.reshape(-1, 3), bot.reshape(-1, 3)])
    idx_t = np.arange(m * n).reshape(m, n)
    idx_b = idx_t + m * n
    F = []
    for i in range(m - 1):
        for j in range(n - 1):
            a, b, c, d = idx_t[i, j], idx_t[i + 1, j], idx_t[i + 1, j + 1], idx_t[i, j + 1]
            F += [[a, b, c], [a, c, d]]
            a, b, c, d = idx_b[i, j], idx_b[i + 1, j], idx_b[i + 1, j + 1], idx_b[i, j + 1]
            F += [[a, c, b], [a, d, c]]
    ring = [(0, j) for j in range(n)] + [(i, n - 1) for i in range(1, m)] + [(m - 1, j) for j in range(n - 2, -1, -1)] + [(i, 0) for i in range(m - 2, 0, -1)]
    for k in range(len(ring)):
        p, q = ring[k], ring[(k + 1) % len(ring)]
        a, b = idx_t[p], idx_t[q]
        c, d = idx_b[q], idx_b[p]
        F += [[a, b, c], [a, c, d]]
    return V, np.array(F, np.int64)


def read_obj(p):
    V, F = [], []
    with open(p, encoding="ascii", errors="ignore") as f:
        for ln in f:
            if ln.startswith("v "):
                V.append([float(x) for x in ln.split()[1:4]])
            elif ln.startswith("f "):
                ids = [int(t.split("/")[0]) - 1 for t in ln.split()[1:]]
                for k in range(1, len(ids) - 1):
                    F.append([ids[0], ids[k], ids[k + 1]])
    return np.array(V, np.float64), np.array(F, np.int64)


def components(F, nv):
    parent = np.arange(nv)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b, c in F:
        ra, rb, rc = find(a), find(b), find(c)
        parent[rb] = ra
        parent[find(rc)] = ra
    roots = np.array([find(v) for v in range(nv)])
    return roots


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["OUT", "IN"], required=True)
    ap.add_argument("--hands", type=int, default=None)
    ap.add_argument("--seed", type=int, default=3101)
    ap.add_argument("--voxel", type=float, default=0.025)
    ap.add_argument("--close", type=float, default=0.035)
    a = ap.parse_args()
    t0 = time.time()
    hands = a.hands or (28 if a.mode == "OUT" else 46)
    C = CB.Crown(a.mode, a.seed)
    C.rim_digits = ([1, 2, 3], [0.45, 0.40, 0.15])
    C.place_user()
    C.place(hands)
    if a.mode == "IN":
        C.constrain_in()
    out = os.path.join(G.OUT, a.mode + "_fused")
    work = os.path.join(out, "work")
    os.makedirs(work, exist_ok=True)
    # 元の管の版（属性の写し元・AO の背骨）
    V0, F0 = C.build_mesh()
    A0 = C.A3.copy()
    n_user_v = sum(len(u["Vw"]) for u in C.user)
    is_user_v = A0[:, 2] == 2
    # 1) 手・指・袖の閉じた管
    Vs, Fs, off = [], [], 0
    roots = []
    for t in C.tubes:
        P = t["P"]
        L = np.sum(np.linalg.norm(np.diff(P, axis=0), axis=1))
        n2 = max(8, int(L / 0.04) + 1)
        P2, _ = GM.resample(P, n2)
        Lo = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
        Ln = np.linspace(0, Lo[-1], n2)
        V, F, fv, rid = GM.tube(P2, np.interp(Ln, Lo, t["rad"]), max(t["nseg"], 16), aspect=np.interp(Ln, Lo, t["aspect"]), side_hint=t["side"], tip=t["tip"])
        F = GM.orient_outward(V, F, P2)
        Vs.append(V)
        Fs.append(F + off)
        off += len(V)
        if t["kind"] == 0:
            roots.append(P[0])
    Vp = np.concatenate(Vs)
    Fp = np.concatenate(Fs)
    G.write_obj(os.path.join(work, "parts.obj"), Vp, Fp, name="parts")
    # 2) 根元の周りの板
    h = C.h
    _, _, rc, _ = C.sheet.nearest(np.array(roots))
    Vs, Fs, off = [], [], 0
    seen = set()
    for (rr, cc) in rc:
        key = (int(round(rr)) // 3, int(round(cc)) // 3)
        if key in seen:
            continue
        seen.add(key)
        V, F = slab_patch(h, int(round(rr)), int(round(cc)))
        Vs.append(V)
        Fs.append(F + off)
        off += len(V)
    G.write_obj(os.path.join(work, "slabs.obj"), np.concatenate(Vs), np.concatenate(Fs), name="slabs")
    print("prep", len(Vp), "part verts", len(seen), "slabs", round(time.time() - t0, 1), flush=True)
    # 3) Houdini
    fused = os.path.join(work, "fused.obj")
    r = subprocess.run([HYTHON, os.path.join(os.path.dirname(os.path.abspath(__file__)), "crown_fuse_h.py"), os.path.join(work, "parts.obj"),
                        os.path.join(work, "slabs.obj"), fused, str(a.voxel), str(a.close)], capture_output=True, text=True, timeout=1800)
    open(os.path.join(work, "hython_log.txt"), "w", encoding="utf-8").write(r.stdout[-4000:] + r.stderr[-4000:])
    print("hython rc", r.returncode, round(time.time() - t0, 1), flush=True)
    if r.returncode != 0 or not os.path.exists(fused):
        print(r.stdout[-2000:], r.stderr[-2000:])
        sys.exit(1)
    Vf, Ff = read_obj(fused)
    # 4) 板（面から 1.2 cm より下）を捨てる
    hv, _ = C.sheet.height(Vf)
    # 元の管の面から 0.12 m より遠い面（板の上面の残り・つないだ膜）と、主役波の面から 2 cm より下の面を捨てる
    dpart, _ = cKDTree(Vp).query(Vf[Ff].mean(1))
    keep = (hv[Ff].max(1) > 0.02) & (dpart < 0.12)
    Ff = Ff[keep]
    # 小さな切れ端を捨てる
    used = np.unique(Ff)
    remap = -np.ones(len(Vf), np.int64)
    remap[used] = np.arange(len(used))
    Vf = Vf[used]
    Ff = remap[Ff]
    comp = components(Ff, len(Vf))
    cf = comp[Ff[:, 0]]
    u, cnt = np.unique(cf, return_counts=True)
    big = set(u[cnt >= 300].tolist())
    Ff = Ff[np.array([c in big for c in cf])]
    used = np.unique(Ff)
    remap = -np.ones(len(Vf), np.int64)
    remap[used] = np.arange(len(used))
    Vf = Vf[used]
    Ff = remap[Ff]
    # 5) 利用者の爪をそのまま足す
    Vu = V0[is_user_v]
    old_idx = np.nonzero(is_user_v)[0]
    m_old = -np.ones(len(V0), np.int64)
    m_old[old_idx] = np.arange(len(old_idx))
    Fu = F0[np.all(is_user_v[F0], axis=1)]
    Fu = m_old[Fu] + len(Vf)
    Vall = np.concatenate([Vf, Vu])
    Fall = np.concatenate([Ff, Fu])
    # 6) 属性
    tree = cKDTree(V0[~is_user_v])
    _, j = tree.query(Vf)
    A_f = A0[~is_user_v][j]
    A_all = np.concatenate([A_f, A0[is_user_v]])
    N = GM.vertex_normals(Vall, Fall)
    # 向きを外向きに：最も近い元の頂点の法線と逆なら全体の三角形の向きを反転（塊は一つの向きのはず）
    N0 = C.N
    _, j2 = cKDTree(V0).query(Vall)
    if (N * N0[j2]).sum(1).mean() < 0:
        Fall = Fall[:, [0, 2, 1]]
        N = -N
    hgt, _ = C.sheet.height(Vall)
    Pn, Nn, _, _ = C.sheet.nearest(Vall)
    wgt = G.sm(np.clip(hgt / 0.15, 0, 1))[:, None]
    rootz = (A_all[:, 0] < 0.35)[:, None]
    N = np.where(rootz, GM.nrm(Nn * (1 - wgt) + N * wgt), N)
    C.V, C.F, C.N, C.A3 = Vall, Fall, N, A_all
    ao, kv = C.ao_keyvis()
    uv5 = np.stack([ao, kv, np.full(len(Vall), 10.0), np.ones(len(Vall))], -1)
    js = CB.write_static(out, "as03_crown", Vall, N, uv5, A_all, Fall)
    G.write_obj(os.path.join(out, "as03_crown.obj"), Vall, Fall, N=N, name="as03_crown_%s_fused" % a.mode)
    # 継ぎ目の測り（面に近い頂点の法線と面の法線）
    seam = (np.abs(hgt) < 0.04) & (A_all[:, 0] < 0.35)
    ang = np.degrees(np.arccos(np.clip((N[seam] * Nn[seam]).sum(1), -1, 1))) if seam.any() else np.zeros(1)
    rep = dict(schema="GreatWave.AS03.crown_fused_report/1", mode=a.mode, seed=a.seed, hands=hands, voxel_m=a.voxel, close_radius_m=a.close,
               date=time.strftime("%Y-%m-%d %H:%M"), method_ja=__doc__.strip(), mesh=js,
               fused_vertices=int(len(Vf)), fused_triangles=int(len(Ff)), user_claw_vertices=int(len(Vu)),
               root_seam_normal_jump_deg=G.pct(ang, (50, 90, 99)), attr_stats=dict(ao=G.pct(ao), keyVis=G.pct(kv)),
               tube_version_report=os.path.relpath(os.path.join(G.OUT, a.mode, "as03_crown_report.json"), G.REPO).replace("\\", "/"),
               elapsed_s=round(time.time() - t0, 1))
    G.jdump(os.path.join(out, "as03_crown_report.json"), rep)
    print(json.dumps({k: rep[k] for k in ("fused_vertices", "fused_triangles", "user_claw_vertices", "root_seam_normal_jump_deg")}, ensure_ascii=False))
    print("FUSED_DONE", a.mode, round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
