import numpy as np, json, time
import q_lib as Q
off = Q.still_offset_fine(); print("fine off", off)
pairs = np.memmap(Q.DATA + "/fine/pairs.bin", dtype="<f4", mode="r", shape=(570, 2, 8192, 2))
for f in (3319, 3709, 3744):
    t0 = time.time()
    phi, xs, ys = Q.load_phi(f)
    P = Q.main_curve(phi, xs, ys - off)
    A = np.array(pairs[f - 3319, 0], dtype=np.float64); A[:, 0] += Q.X0B
    d = Q.seg_dist(A, P)
    print(f, "main pts", len(P), "len", Q.arclen(P)[-1], "x", P[0, 0], P[-1, 0], "A x", A[0, 0], A[-1, 0], "A->contour max", d.max(), "t", time.time() - t0)
    S, sx, sy = Q.load_sec(f)
    Ps = Q.main_curve(S, sx, sy - Q.OFF_R3)
    print("  sec main", len(Ps), Ps[0], Ps[-1])
