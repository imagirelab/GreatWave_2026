# -*- coding: utf-8 -*-
"""Q20 candidate B (incremental fixes of K* 26修正01): shared helpers.

K*' keeps the K* grid (400 columns x 240 rows, the same UV/UV2/triangles) and the section frame of 26修正01:
a = along travel t (+ = lip side), y = height above still water, c = along the crest e (- = camera-side shoulder).
Rows stay planar (c = const per row) so the motion generators (ds27/ds28) can be re-targeted later.

The painting gate is the envelope evaluator gw_wavegen_v1.preview_metrics (items 78/130/131/132, 72 p95), the same as
Q20 rubric F01.  A fast check (coverage mask vs K*) is used between steps.
Heavy outputs go to Unity/Build/Q20/candB (git-ignored).  Nothing here reads the reference model.
"""
import os, sys, json, math, hashlib, struct
import numpy as np

REPO = r"G:\Unity\GreatWave_2026_Fresh"
KDIR = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01", "kstar")
OUT = os.path.join(REPO, "Unity", "Build", "Q20", "candB")
WORK = os.path.join(OUT, "work")
RUBRIC = os.path.join(REPO, "Unity", "Build", "Q20", "rubric")
sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth"))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen"))
sys.path.insert(0, os.path.join(RUBRIC, "tools"))

META = json.load(open(os.path.join(KDIR, "kstar_a45_meta.json"), encoding="utf-8"))
FR = META["frame"]
E = np.array(FR["e_crest"]); T = np.array(FR["t_travel"]); O = np.array(FR["section_origin_world"]); UP = np.array([0, 1.0, 0])
H0 = float(FR["H0_m"])
CAM_S = np.array(FR["camera_in_section_a_y_c"])      # PaintingCam centre in (a, y, c)
IDX = META["profile"]["index"]
J_B, J_TOP, J_TIP, J_CORNER, J_FB, J_E = (IDX[k] for k in ("j_B", "j_top", "j_tip", "j_corner", "j_facebot", "j_E"))
NU, NV = 400, 240


def load_kstar():
    z = np.load(os.path.join(KDIR, "kstar_a45_rows.npz"))
    return z["A"].astype(np.float64).copy(), z["Y"].astype(np.float64).copy(), z["c"].astype(np.float64).copy()


def read_gwb(path=os.path.join(KDIR, "kstar_a45.gwb")):
    b = open(path, "rb").read()
    assert b[:4] == b"GWW0"
    ver, nu, nv, nf = np.frombuffer(b[4:20], "<i4")
    ntri = int(np.frombuffer(b[28:32], "<i4")[0]); n = int(nu) * int(nv)
    o = 32
    uv = np.frombuffer(b, np.float32, n * 2, o).reshape(n, 2).copy(); o += n * 8
    uv2 = np.frombuffer(b, np.float32, n * 2, o).reshape(n, 2).copy(); o += n * 8
    tris = np.frombuffer(b, np.int32, ntri * 3, o).reshape(-1, 3).copy(); o += ntri * 12
    X = np.frombuffer(b, np.float32, n * 3, o).reshape(n, 3).astype(np.float64)
    return {"header": b[:32], "nu": int(nu), "nv": int(nv), "uv": uv, "uv2": uv2, "tris": tris, "X": X}


def world(A, Y, c):
    return O[None, None, :] + A[..., None] * T[None, None, :] + Y[..., None] * UP[None, None, :] + c[:, None, None] * E[None, None, :]


def write_gwb(path, A, Y, c, uv2_c=True):
    """same header / UV / UV2 / triangles as K*; UV2.y (= c) updated to the new row positions."""
    g = read_gwb()
    X = world(A, Y, c).reshape(-1, 3)
    uv2 = g["uv2"].copy()
    if uv2_c:
        uv2[:, 1] = np.repeat(c, NU).astype(np.float32)
    with open(path, "wb") as fo:
        fo.write(g["header"])
        for arr in (g["uv"].astype(np.float32), uv2.astype(np.float32), g["tris"].astype(np.int32), X.astype(np.float32)):
            fo.write(np.ascontiguousarray(arr).tobytes())
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


# ------------------------------------------------------------------ painting camera
_G = {}


def gate_env():
    if "fr" not in _G:
        import truthlib as TL
        import gw_wavegen_v1 as V1
        params = TL.load_json(os.path.join(REPO, "Tools", "GWWaveGen", "params_v2_af26r01.json"))
        tgt = V1.Target(); fr = V1.Frame(tgt.spec, float(params["alpha_deg"]), params["anchor"], tgt)
        _G.update(fr=fr, tgt=tgt, V1=V1, tris=V1.triangles(NU, NV))
    return _G


def project(P):
    """world (..., 3) -> display px (x, y, depth) of PaintingCam v1."""
    g = gate_env()
    sh = P.shape
    return g["fr"].cam.project(P.reshape(-1, 3)).reshape(sh)


def coverage(A, Y, c, ss=2):
    g = gate_env()
    X = world(A, Y, c).reshape(-1, 3)
    return g["V1"].rasterize(g["fr"].cam, X, g["tris"], ss=ss)


def horizon_y():
    g = gate_env()
    import gw_wavegen as G0
    return G0.sea_horizon_cover(g["fr"].cam, g["tgt"].spec)[1]


def gate(A, Y, c, png=None, title="candB"):
    g = gate_env()
    X = world(A, Y, c).reshape(-1, 3)
    png = png or os.path.join(WORK, "_gate_overlay.png")
    r = g["V1"].preview_metrics(g["fr"], g["tgt"], X, g["tris"], png, title)
    return {k: {"max_px": round(float(v["max_px"]), 3), "p95_px": round(float(v["p95_px"]), 3)} for k, v in r.items()}


GATE_BASE = {"78": 1.37, "130": 1.80, "131": 1.47, "132": 1.40}


def gate_ok(g):
    ok = all(g[k]["max_px"] <= min(4.0, GATE_BASE[k] + 0.5) for k in GATE_BASE) and g["72"]["p95_px"] <= 4.0
    return bool(ok)


def mask_diff(cov0, cov1, yh=None, thr=0.5):
    """pixels that changed between two coverage maps above the horizon (added = new wave where K* had sky)."""
    m0 = cov0 > thr; m1 = cov1 > thr
    if yh is None:
        yh = horizon_y()
    above = (np.arange(m0.shape[0])[:, None] < yh) * np.ones((1, m0.shape[1]), bool)
    add = m1 & ~m0 & above; rem = m0 & ~m1 & above
    return {"added_px": int(add.sum()), "removed_px": int(rem.sum()), "add": add, "rem": rem}


# ------------------------------------------------------------------ row helpers
def lam(c_new, c_old):
    """camera-centre scaling factor that keeps a row's PaintingCam image when it moves from plane c_old to c_new."""
    return (c_new - CAM_S[2]) / (c_old - CAM_S[2])


def cam_scale_row(a, y, c_old, c_new):
    m = lam(c_new, c_old)
    return CAM_S[0] + m * (a - CAM_S[0]), CAM_S[1] + m * (y - CAM_S[1])


def arclen(a, y):
    return np.r_[0.0, np.cumsum(np.hypot(np.diff(a), np.diff(y)))]


def smoothstep(x):
    x = np.clip(x, 0, 1); return x * x * (3 - 2 * x)


def smootherstep(x):
    x = np.clip(x, 0, 1); return x * x * x * (x * (6 * x - 15) + 10)


def save_rows(path, A, Y, c, extra=None):
    d = {"A": A, "Y": Y, "c": c}
    if extra:
        d.update(extra)
    np.savez_compressed(path, **d)
