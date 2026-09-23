"""Where are the largest per-frame vertex steps of the point cache?  tools/run_blender.ps1 src/gwave/diagnose_steps.py"""
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
import numpy as np

from gw import bootstrap, paths
from gwave import profile_motion as wm


def main():
    bootstrap.set_log_prefix("GW")
    WP = wm.load_wave_params()
    H = float(paths.param("WAVE_HEIGHT_M"))
    n_u = int(WP["n_u"])
    n_v = int(WP["n_v_center"]) + 2 * int(WP["n_v_taper"])
    n = n_u * n_v
    mm = np.memmap(paths.norm(WP["cache_path"]), dtype="<f4", mode="r", offset=32)
    nf = mm.size // (3 * n)
    V = mm[:nf * 3 * n].reshape(nf, n, 3)
    worst = []
    for f in range(1, nf):
        d = np.sqrt(((V[f] - V[f - 1]) ** 2).sum(1)) / H
        k = int(np.argmax(d))
        worst.append((float(d[k]), f + 1, k // n_u, k % n_u, V[f - 1, k] / H, V[f, k] / H, int((d > 0.03).sum())))
    worst.sort(key=lambda t: -t[0])
    for w in worst[:8]:
        bootstrap.log("step %.4f H at frame %d row %d (u=%.2f) col %d  from (%.3f,%.3f,%.3f) to (%.3f,%.3f,%.3f)  n>0.03H: %d" % (
            w[0], w[1], w[2], abs(w[2] - n_v // 2) / (n_v // 2), w[3], *w[4], *w[5], w[6]))
    bootstrap.finish(True, "diagnose_steps")


if __name__ == "__main__":
    main()
