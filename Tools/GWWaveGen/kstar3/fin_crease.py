import sys, numpy as np
def crease_map(A, Y, c, jtip=200):
    nv, nu = A.shape
    Xg = np.stack([A, Y, np.broadcast_to(c[:, None], A.shape)], -1)
    du = Xg[:, 1:] - Xg[:, :-1]; dv = Xg[1:] - Xg[:-1]
    n = np.cross(du[:-1], dv[:, :-1]); n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-12
    ang = np.degrees(np.arccos(np.clip((n[1:] * n[:-1]).sum(-1), -1, 1)))
    cols = np.arange(nu - 1)[None, :]
    m = (Y[1:-1, :-1] > 0.3) & ~((cols >= jtip - 10) & (cols <= jtip + 12)) & (np.abs(c[1:-1, None]) <= 16)
    return ang, m
if __name__ == "__main__":
    z = np.load(sys.argv[1]); A, Y, c = z["A"], z["Y"], z["c"]
    ang, m = crease_map(A, Y, c)
    v = ang[m]; print("p99 %.1f  n>30 %d  p95 %.1f" % (np.percentile(v, 99), (v > 30).sum(), np.percentile(v, 95)))
    r, j = np.nonzero((ang > 30) & m)
    edges = [-16, -12, -8, -5, -2, 0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 13]
    for lo, hi in zip(edges[:-1], edges[1:]):
        s = (c[r + 1] >= lo) & (c[r + 1] < hi)
        if s.sum():
            print("c %5.1f..%5.1f n %4d  cols-by-20:" % (lo, hi, s.sum()), np.bincount(j[s] // 20, minlength=20))
