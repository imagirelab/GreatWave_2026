"""Section-curve motion model of the Great Wave (numpy only, no bpy).

The wave at every time is ONE section curve in the XZ plane (H units), sampled with a fixed number of points
(u index = UV's U):  back hem -> crest -> head tip -> underside -> inner arc -> trough -> front hem.

* final pose  = target/base_contour.json (+ smooth extension of the back beyond the left frame edge, spec 7b,
                + re-drawn occluded end of the inner arc and a flat trough run, spec 7c)
* start pose  = gentle Gaussian swell carrying the same samples
* in between  = interpolation of tangent angle and segment length (not of positions), with a per-sample lag:
                back and front face move first (rise), the head top follows (overhang), the tip and the
                underside last (curl-in).  All samples arrive together at tau = 1.
* time        = monotone cubic tau(frame) through (1, 0) (onset frame, tau_onset) (curl frame, tau_curl) (last, 1)
                with zero end slope (ease-out before the stop, spec M5).
* height      = a separate monotone cubic through explicit frame/height keys; this keeps the rise while the
                head angle and length follow independent schedules.  The final pose is never rescaled.
* 3-D         = the section swept along Y with the silhouette-exact 'lift_clip' flank taper.
"""
import json
import math
import os

import numpy as np

from gw import profile_metrics as pm

PROJECT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
WAVE_PARAMS_JSON = os.path.join(PROJECT, "wave_params.json")


def load_wave_params(path=None):
    with open(path or WAVE_PARAMS_JSON, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    values = {k: v["value"] for k, v in raw.items() if isinstance(v, dict) and "value" in v}
    for key in ("blend_path", "cache_path"):
        value = os.path.expanduser(values[key])
        values[key] = os.path.normpath(value if os.path.isabs(value) else os.path.join(PROJECT, value))
    return values


def _smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _ramp_in(x):
    """w(0)=0, w'(0)=0, w(1)=1, w'(1)=1, monotone: soft start, no ease at the end (tau(t) eases the end)."""
    x = np.clip(x, 0.0, 1.0)
    return x * x * (2.0 - x)


def _bezier(p0, p1, p2, p3, n):
    t = np.linspace(0.0, 1.0, n)[:, None]
    return ((1 - t) ** 3) * p0 + 3 * ((1 - t) ** 2) * t * p1 + 3 * (1 - t) * t * t * p2 + (t ** 3) * p3


def _arclen(p):
    return np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(p[:, 0]), np.diff(p[:, 1])))])


# ------------------------------------------------------------------------------------------ final pose
def build_final_profile(WP):
    """-> dict: q (n_u, 2) final section in H units, indices of crest / tip / deepest, info."""
    bc_path = WP["base_contour"]
    if not os.path.isabs(bc_path):
        bc_path = os.path.join(PROJECT, bc_path)
    bc = pm.load_base_contour(bc_path)
    poly = pm.base_contour_polyline(bc)
    p = poly["pts_H"].copy()
    in_s7 = poly["in_S7"]
    one_pct = float(pm.pct_h_to_H(1.0))

    # ---- right end (spec 7c): re-draw the completed (not judged) end so that it lands horizontally on Z = 0
    k0 = int(np.nonzero(in_s7)[0][-1])
    a = p[k0]
    ta = p[k0] - p[max(0, k0 - 12)]
    ta = ta / np.hypot(*ta)
    e = np.array([p[-1, 0] + WP["right_completion_reach_H"], 0.0])
    reach = np.hypot(*(e - a))
    right = _bezier(a, a + ta * 0.40 * reach, e - np.array([0.45 * reach, 0.0]), e, 80)
    flat = np.stack([np.linspace(e[0], e[0] + WP["right_flat_H"], 40), np.zeros(40)], axis=1)

    # ---- left end (spec 7b): C1 extension of the back down to still water, slope decreasing monotonically to 0
    s = _arclen(p)
    k = int(np.searchsorted(s, WP["left_slope_chord_pct_h"] * one_pct))
    d = p[max(k, 2)] - p[0]
    alpha = math.atan2(d[1], d[0])
    A = p[0]
    L = float(WP["left_extension_H"])
    L = max(L, 1.25 * A[1] / max(math.tan(alpha), 1e-3))          # long enough for a monotone toe
    B = np.array([A[0] - L, 0.0])
    b = min(0.45 * L, 0.8 * A[1] / max(math.sin(alpha), 1e-6))
    P2 = A - b * np.array([math.cos(alpha), math.sin(alpha)])
    P1x = P2[0] - P2[1] / (0.75 * math.tan(alpha))
    P1x = max(P1x, B[0] + 0.1 * L)
    left = _bezier(B, np.array([P1x, 0.0]), P2, A, 120)

    full = np.concatenate([left[:-1], p[:k0 + 1], right[1:], flat[1:]])
    C = pm.Curve(full)

    # ---- adaptive resampling to n_u points (denser where the section bends)
    n_u = int(WP["n_u"])
    sf = np.linspace(0.0, C.length, 6000)
    pf = C.at(sf)
    ang = np.unwrap(np.arctan2(np.gradient(pf[:, 1]), np.gradient(pf[:, 0])))
    curv = np.abs(np.gradient(ang, sf))
    ker = np.exp(-0.5 * (np.arange(-60, 61) / 20.0) ** 2)
    curv = np.convolve(curv, ker / ker.sum(), mode="same")
    dens = 1.0 + WP["density_gain"] * np.minimum(curv / WP["density_curv_ref_per_H"], 1.0)
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (dens[1:] + dens[:-1]) * np.diff(sf))])
    su = np.interp(np.linspace(0.0, cum[-1], n_u), cum, sf)
    q = C.at(su)
    q[0, 1] = 0.0
    q[-1, 1] = 0.0

    m = pm.measure_profile(q)
    lmk = m["landmarks"]
    out = {"q": q, "i_crest": int(lmk["crest"]["index"]), "i_tip": int(lmk["head_tip"]["index"]),
           "i_deep": int(lmk["inner_deepest"]["index"]), "metrics": m, "base_contour": bc,
           "left_alpha_deg": math.degrees(alpha), "left_extension_used_H": L,
           "x_frame_left_H": float(p[0, 0]), "i_flat_start": int(np.argmin(np.abs(su - (C.length - WP["right_flat_H"]))))}
    # sample index where the judged contour starts (left frame edge)
    out["i_frame_edge"] = int(np.argmin(np.hypot(q[:, 0] - A[0], q[:, 1] - A[1])))
    return out


# ------------------------------------------------------------------------------------------ motion model
class WaveMotion:
    def __init__(self, WP=None):
        self.WP = WP or load_wave_params()
        WP = self.WP
        F = build_final_profile(WP)
        self.final = F
        q = F["q"]
        self.q = q
        self.n_u = q.shape[0]
        self.i_c, self.i_t, self.i_d = F["i_crest"], F["i_tip"], F["i_deep"]
        d = np.diff(q, axis=0)
        self.ds1 = np.hypot(d[:, 0], d[:, 1])
        self.psi1 = np.unwrap(np.arctan2(d[:, 1], d[:, 0]))
        S1 = _arclen(q)
        self.S1 = S1

        # ---- start pose: the same samples laid on a gentle Gaussian swell
        A0, sg = float(WP["swell_amplitude_H"]), float(WP["swell_sigma_H"])
        lam = float(WP["front_length_ratio"])
        xs = np.linspace(-(S1[self.i_c] + 2.0), (S1[-1] - S1[self.i_c]) * lam + 2.0, 8000)
        zs = A0 * np.exp(-(xs / sg) ** 2)
        sw = pm.Curve(np.stack([xs, zs], axis=1))
        s_crest_sw = float(np.interp(0.0, xs, sw.s))
        # start length of every segment relative to its final length: the head (crest -> tip -> underside) starts
        # SHORT and grows during overhang / curl-in (the lip grows out of the crest); the rest keeps `lam`
        i_c, i_t, i_d = self.i_c, self.i_t, self.i_d
        Sm = 0.5 * (S1[1:] + S1[:-1])
        lam_head = float(WP["head_start_length_ratio"])
        s_in = S1[i_c] + 0.12 * (S1[i_t] - S1[i_c])
        s_out0 = S1[i_t] + 0.65 * (S1[i_d] - S1[i_t])
        ratio = np.ones(self.n_u - 1)
        fr = Sm >= S1[i_c]
        ratio[fr] = lam
        head_w = _smooth((Sm - S1[i_c]) / max(s_in - S1[i_c], 1e-9)) * (1.0 - _smooth((Sm - s_out0) / max(S1[i_d] - s_out0, 1e-9)))
        ratio = np.where(fr, lam + (lam_head - lam) * head_w, ratio)
        self.len_ratio0 = ratio
        off = np.concatenate([[0.0], np.cumsum(self.ds1 * ratio)])
        off = off - off[i_c]
        p0 = sw.at(s_crest_sw + off)
        d0 = np.diff(p0, axis=0)
        self.ds0 = np.hypot(d0[:, 0], d0[:, 1])
        self.psi0 = np.arctan2(d0[:, 1], d0[:, 0])
        # unwrap psi1 relative to psi0 so that the head turns clockwise through -90 / -180 deg (no +/-360 flips)
        self.dpsi = self.psi1 - self.psi0

        # ---- lag mask along the section (0 = moves first, 1 = moves last)
        mask = np.zeros(self.n_u)
        i_c, i_t, i_d = self.i_c, self.i_t, self.i_d
        i_f = F["i_flat_start"]
        mask[i_c:i_t + 1] = _smooth((S1[i_c:i_t + 1] - S1[i_c]) / max(S1[i_t] - S1[i_c], 1e-9))
        v_d, v_f = float(WP["lag_inner_deepest"]), float(WP["lag_trough"])
        mask[i_t:i_d + 1] = 1.0 + (v_d - 1.0) * _smooth((S1[i_t:i_d + 1] - S1[i_t]) / max(S1[i_d] - S1[i_t], 1e-9))
        mask[i_d:i_f + 1] = v_d + (v_f - v_d) * _smooth((S1[i_d:i_f + 1] - S1[i_d]) / max(S1[i_f] - S1[i_d], 1e-9))
        mask[i_f:] = v_f * (1.0 - _smooth((S1[i_f:] - S1[i_f]) / max(S1[-1] - S1[i_f], 1e-9)))
        mseg = 0.5 * (mask[1:] + mask[:-1])                                  # per segment
        self.lag_ang = float(WP["lag_angle_max"]) * mseg                     # angles lead a little ...
        self.lag_len = float(WP["lag_length_max"]) * mseg                    # ... lengths follow (the lip grows)

        # material index of the armpit (top of the inner arc) in the final pose: first local minimum of z after the tip
        # (lowest point of the lobe), then the highest point before the deepest point
        k = i_t
        while k < i_d and q[k + 1, 1] <= q[k, 1]:
            k += 1
        self.i_armpit = int(k + np.argmax(q[k:i_d + 1, 1])) if k < i_d else int(i_t)

        self.n_frames = int(WP["n_frames"])
        self.x_c_final = float(q[self.i_c, 0])
        self._tau_table = None

        height_keys = np.asarray(WP["height_keyframes_H"], dtype=np.float64)
        if (height_keys.ndim != 2 or height_keys.shape[1] != 2 or height_keys.shape[0] < 2
                or not np.isfinite(height_keys).all() or height_keys[0, 0] != 1
                or height_keys[-1, 0] != self.n_frames or np.any(np.diff(height_keys[:, 0]) <= 0)
                or np.any(np.diff(height_keys[:, 1]) < 0) or height_keys[0, 1] <= 0):
            raise ValueError("height_keyframes_H must be finite, increasing frame/height pairs from frame 1 to n_frames")
        if abs(float(height_keys[-1, 1]) - float(q[:, 1].max())) > 1e-8:
            raise ValueError("final height key must equal the exact final profile crest height")
        self.height_keys = height_keys
        widths = np.diff(height_keys[:, 0])
        secants = np.diff(height_keys[:, 1]) / widths
        slopes = np.zeros(height_keys.shape[0], dtype=np.float64)  # rest at both ends
        for i in range(1, len(slopes) - 1):
            if secants[i - 1] <= 0 or secants[i] <= 0:
                continue
            w1, w2 = 2.0 * widths[i] + widths[i - 1], widths[i] + 2.0 * widths[i - 1]
            slopes[i] = (w1 + w2) / (w1 / secants[i - 1] + w2 / secants[i])
        self.height_slopes = slopes

    # ---- shape for a morph parameter tau in [0, 1] (crest sample placed at x = 0)
    def shape(self, tau):
        if tau >= 1.0:
            out = self.q.copy()
            out[:, 0] -= self.x_c_final
            return out
        w_a = _ramp_in((tau - self.lag_ang) / (1.0 - self.lag_ang))
        w_l = _ramp_in((tau - self.lag_len) / (1.0 - self.lag_len))
        psi = self.psi0 + w_a * self.dpsi
        ds = self.ds0 + w_l * (self.ds1 - self.ds0)
        x = np.concatenate([[0.0], np.cumsum(ds * np.cos(psi))])
        z = np.concatenate([[0.0], np.cumsum(ds * np.sin(psi))])
        s = np.concatenate([[0.0], np.cumsum(ds)])
        z = np.maximum(z - z[-1] * (s / s[-1]), 0.0)   # both hems on still water; nothing below it (spec 7d)
        x = x - x[self.i_c]
        return np.stack([x, z], axis=1)

    def shape_rows(self, taus):
        """Vectorised shape() for many morph parameters at once.  -> (x, z), each (R, n_u), crest sample at x = 0."""
        t = np.clip(np.asarray(taus, dtype=np.float64), 0.0, 1.0)[:, None]
        w_a = _ramp_in((t - self.lag_ang[None, :]) / (1.0 - self.lag_ang[None, :]))
        w_l = _ramp_in((t - self.lag_len[None, :]) / (1.0 - self.lag_len[None, :]))
        psi = self.psi0[None, :] + w_a * self.dpsi[None, :]
        ds = self.ds0[None, :] + w_l * (self.ds1 - self.ds0)[None, :]
        zero = np.zeros((t.shape[0], 1))
        x = np.concatenate([zero, np.cumsum(ds * np.cos(psi), axis=1)], axis=1)
        z = np.concatenate([zero, np.cumsum(ds * np.sin(psi), axis=1)], axis=1)
        s = np.concatenate([zero, np.cumsum(ds, axis=1)], axis=1)
        z = np.maximum(z - z[:, -1:] * (s / s[:, -1:]), 0.0)   # spec 7d: nothing below the trough / still-water level
        x = x - x[:, [self.i_c]]
        done = t[:, 0] >= 1.0
        if done.any():
            x[done] = (self.q[:, 0] - self.x_c_final)[None, :]
            z[done] = self.q[:, 1][None, :]
        return x, z

    # ---- time law
    def tau_onset(self):
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            if pm.measure_profile(self.shape(mid))["overhanging"]:
                hi = mid
            else:
                lo = mid
        return hi

    def tau_of_frame(self, frame):
        if self._tau_table is None:
            WP = self.WP
            t_on = self.tau_onset()
            t_cu = t_on + float(WP["curl_start_fraction"]) * (1.0 - t_on)
            xk = np.array([1.0, float(WP["frame_overhang_onset"]), float(WP["frame_curl_start"]), float(self.n_frames)])
            yk = np.array([0.0, t_on, t_cu, 1.0])
            h = np.diff(xk)
            dl = np.diff(yk) / h
            mk = np.zeros(4)
            for i in (1, 2):                            # PCHIP interior slopes (weighted harmonic mean) -> monotone
                w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
                mk[i] = (w1 + w2) / (w1 / dl[i - 1] + w2 / dl[i])
            mk[0] = 0.0                                 # from rest
            mk[3] = 0.0                                 # ease-out into the stop (spec M5)
            self._tau_table = (xk, yk, mk, t_on, t_cu)
        xk, yk, mk, _a, _b = self._tau_table
        f = float(np.clip(frame, xk[0], xk[-1]))
        i = int(min(np.searchsorted(xk, f, side="right") - 1, 2))
        hh = xk[i + 1] - xk[i]
        t = (f - xk[i]) / hh
        h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
        h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
        return float(h00 * yk[i] + h10 * hh * mk[i] + h01 * yk[i + 1] + h11 * hh * mk[i + 1])

    def x_c_of_frame(self, frame):
        u = (float(np.clip(frame, 1, self.n_frames)) - 1.0) / (self.n_frames - 1.0)
        return self.x_c_final - float(self.WP["xc_travel_H"]) * (1.0 - u) ** float(self.WP["xc_travel_power"])

    def height_of_frame(self, frame):
        """Target crest height in H units, controlled separately from the head morph."""
        keys, slopes = self.height_keys, self.height_slopes
        f = float(np.clip(frame, keys[0, 0], keys[-1, 0]))
        i = min(int(np.searchsorted(keys[:, 0], f, side="right") - 1), len(keys) - 2)
        width = keys[i + 1, 0] - keys[i, 0]
        t = (f - keys[i, 0]) / width
        h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
        h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
        return float(h00 * keys[i, 1] + h10 * width * slopes[i] + h01 * keys[i + 1, 1] + h11 * width * slopes[i + 1])

    def height_gain(self, frame):
        if frame >= self.n_frames:
            return 1.0  # preserve the sampled painting contour bit-for-bit
        raw = self.shape(self.tau_of_frame(frame))
        raw_height = float(raw[:, 1].max())
        if raw_height <= 0:
            raise ValueError("generated profile has no positive crest height")
        return self.height_of_frame(frame) / raw_height

    def profile(self, frame):
        """Section of scene frame `frame` (H units, world X)."""
        if frame >= self.n_frames:
            return self.q.copy()  # exact painted final pose and exact static hold
        p = self.shape(self.tau_of_frame(frame))
        p[:, 1] *= self.height_gain(frame)
        p[:, 0] += self.x_c_of_frame(frame)
        return p


# ------------------------------------------------------------------------------------------ 3-D sweep
def v_layout(WP):
    """-> (y_H (n_v,), taper coordinate d (n_v,): 1 in the constant middle part, 0 at the outer ends)."""
    half, tl = float(WP["crest_half_length_H"]), float(WP["taper_length_H"])
    nc, nt = int(WP["n_v_center"]), int(WP["n_v_taper"])
    d_side = np.linspace(1.0, 0.0, nt + 1)[1:]
    y_side = half + (1.0 - d_side) * tl
    y_c = np.linspace(-half, half, nc)
    y = np.concatenate([-y_side[::-1], y_c, y_side])
    d = np.concatenate([d_side[::-1], np.ones(nc), d_side])
    return y, d


LIFT_END_D = 0.8


def lift_clip_sections(profile_H, x_clip_target, d, under_branch=None):
    """Silhouette-preserving rounded flank taper.  A squared taper coordinate narrows the high crest in Y;
    the forward head contracts toward the crest instead of collapsing onto a planar clip wall.  The underside
    lifts before the head retracts, then the remaining mound settles into still water.  -> (X, Z), each (n_v, n_u)."""
    d = np.asarray(d, dtype=np.float64) ** 2
    x, z = profile_H[:, 0], profile_H[:, 1]
    z_lift = z.copy()
    if under_branch is not None and int(under_branch[1]) > int(under_branch[0]):
        i_t, i_d = int(under_branch[0]), int(under_branch[1])
        z_lift[i_t:i_d + 1] = np.maximum.accumulate(z[i_t:i_d + 1][::-1])[::-1]
    x_max = x.max()
    w_lift = _smooth((1.0 - d) / (1.0 - LIFT_END_D))[:, None]
    qq = _smooth((LIFT_END_D - d) / (LIFT_END_D - 0.5))
    g = _smooth(d / 0.5)[:, None]
    c = (x_max - qq * (x_max - x_clip_target))[:, None]
    Zj = z[None, :] + w_lift * (z_lift - z)[None, :]
    x_crest = float(x[np.argmax(z)])
    head_fraction = np.clip((x - x_crest) / max(x_max - x_crest, 1e-8), 0.0, 1.0)
    X = x[None, :] - (x_max - c) * head_fraction[None, :]
    # top boundary height at the clip line of every row
    for j in np.nonzero(qq > 0.0)[0]:
        cj = c[j, 0]
        over = x > cj
        if over.any():
            k = int(np.argmax(x >= cj))
            if k > 0 and x[k] > x[k - 1]:
                z_top = z[k - 1] + (cj - x[k - 1]) / (x[k] - x[k - 1]) * (z[k] - z[k - 1])
            else:
                z_top = z[k]
            sel = over.copy()
            sel[:k] = False
            Zj[j] = np.where(sel, np.minimum(Zj[j], z_top), Zj[j])
    return X, Zj * g


# ------------------------------------------------------------------------------------------ 'regress' flanks
def v_layout_regress(WP):
    """-> (y_H (n_v,), u (n_v,) = |y| / half length: 0 at the middle row, 1 at both ends)."""
    n_v = int(WP["n_v_center"]) + 2 * int(WP["n_v_taper"])
    half = float(WP["crest_half_length_H"])
    y = np.linspace(-half, half, n_v)
    return y, np.abs(y) / half


def _points_in_polygon(px, pz, poly, chunk=4000):
    """even-odd rule, vectorised.  px, pz (N,), poly (M, 2) closed implicitly.  -> bool (N,)"""
    x0, z0 = poly[:, 0], poly[:, 1]
    x1, z1 = np.roll(x0, -1), np.roll(z0, -1)
    out = np.zeros(px.shape[0], dtype=bool)
    dz = np.where(z1 == z0, 1e-30, z1 - z0)
    for a in range(0, px.shape[0], chunk):
        X, Z = px[a:a + chunk, None], pz[a:a + chunk, None]
        cond = (z0[None, :] > Z) != (z1[None, :] > Z)
        xi = x0[None, :] + (Z - z0[None, :]) * (x1 - x0)[None, :] / dz[None, :]
        out[a:a + chunk] = (np.count_nonzero(cond & (X < xi), axis=1) % 2) == 1
    return out


def _nearest_on_polyline(px, pz, line, chunk=2000):
    a, b = line[:-1], line[1:]
    ab = b - a
    L2 = np.maximum((ab ** 2).sum(1), 1e-30)
    ox, oz = np.empty_like(px), np.empty_like(pz)
    for k in range(0, px.shape[0], chunk):
        P = np.stack([px[k:k + chunk], pz[k:k + chunk]], axis=1)
        t = np.clip(((P[:, None, :] - a[None, :, :]) * ab[None, :, :]).sum(2) / L2[None, :], 0.0, 1.0)
        Q = a[None, :, :] + t[:, :, None] * ab[None, :, :]
        d2 = ((Q - P[:, None, :]) ** 2).sum(2)
        j = np.argmin(d2, axis=1)
        sel = Q[np.arange(P.shape[0]), j]
        ox[k:k + chunk], oz[k:k + chunk] = sel[:, 0], sel[:, 1]
    return ox, oz


def regress_sections(motion, frame, WP, u, stats=None):
    """Natural flanks: away from the middle row every section is a LESS DEVELOPED state of the same motion (smaller
    morph parameter: lower crest, shorter lip, no overhang on the shoulders), lowered to still water at the ends and
    trailing behind in X (crescent crest line).  Every flank vertex is then kept inside the middle section's body
    (back: horizontal clip; front: point-in-polygon + projection onto the contour), so the side silhouette seen by
    CAM_print is exactly the middle section at EVERY frame and the cavity is never blocked.
    -> (X, Z), each (n_v, n_u), H units."""
    tau_c = motion.tau_of_frame(frame)
    x_c = motion.x_c_of_frame(frame)
    u0, uk = float(WP["flank_plateau"]), float(WP["flank_height_start"])
    A = 1.0 - _smooth((u - u0) / (1.0 - u0)) ** float(WP["flank_development_power"])
    K = 1.0 - _smooth((u - uk) / (1.0 - uk))
    # the crescent develops with the wave: a low swell has a straight crest line
    # rows of the plateau are identical to the middle row (no shift at all); outside it the crescent develops with
    # the wave: a low swell has a straight crest line
    D = (float(WP["flank_back_shift_H"]) * _smooth((u - u0) / (1.0 - u0)) ** float(WP["flank_back_shift_power"])
         * float(_smooth((tau_c - 0.25) / 0.5)))
    xr, zr = motion.shape_rows(tau_c * A)
    Z = zr * K[:, None] * motion.height_gain(frame)
    mid = int(np.argmin(u))
    same = u <= u0                                # plateau rows: never touched by any clip
    i_c, i_t, i_d = motion.i_c, motion.i_t, motion.i_d
    z_lo, z_hi = 0.04, 0.10                       # only what can show in the judged silhouette is clipped

    # back limit x(z) of the middle section.  Its z is not strictly monotone (hand-drawn wiggles at low slopes), so use
    # the conservative envelope: running minimum of z taken from the crest backwards -> single valued, always inside
    ker = np.exp(-0.5 * (np.arange(-24, 25) / 8.0) ** 2)
    ker /= ker.sum()
    zs_mid = np.convolve(np.pad(Z[mid], 24, mode="edge"), ker, mode="valid")   # wiggle-free copy for the limits
    zb = np.minimum.accumulate(zs_mid[:i_c + 1][::-1])[::-1]
    zb = zb + 1e-7 * np.arange(zb.size)                                       # strictly increasing: no plateaus
    xb = xr[mid, :i_c + 1] + x_c
    Zb = Z[:, :i_c + 1]
    lim = np.interp(Zb, zb, xb)
    X = xr + x_c - D[:, None]
    pc = np.stack([X[mid], Z[mid]], axis=1)

    # back: the trailing shoulders fill the back of the silhouette from inside (their backs are clipped onto the
    # middle section's back, which is the painted outline); the push fades out over the head top -> no fold at the crest
    h_mid = float(Z[mid].max())
    push = (np.maximum(lim - X[:, :i_c + 1], 0.0) * _smooth((Zb - z_lo) / (z_hi - z_lo))
            * _smooth((0.97 * h_mid - Zb) / max(0.12 * h_mid, 1e-6))        # x(z) is ill-conditioned on the flat crest cap
            * _smooth(D / 0.04)[:, None])                                   # rows that barely trail need no push at all
    push[same] = 0.0
    Xb = X[:, :i_c + 1] + push
    Xb[~same] = np.maximum.accumulate(Xb[~same], axis=1)      # vertex order along the row is kept -> no fold
    X[:, :i_c + 1] = Xb
    fade = 1.0 - _smooth((motion.S1[i_c:i_t + 1] - motion.S1[i_c]) / max(motion.S1[i_t] - motion.S1[i_c], 1e-9))
    X[:, i_c + 1:i_t + 1] += (Xb[:, -1:] - (xr[:, [i_c]] + x_c - D[:, None])) * fade[None, 1:]

    # front, lower part (inner arc / front face below the armpit): horizontal clip behind the middle section's
    # front (keeps every vertex's height -> smooth rows, no bunching)
    # The limit is x_lim(z) = inner arc / front face BELOW the deepest point (single valued, wiggle-proof envelope) and the
    # plumb line of the deepest point above it.  Under the head the pull is weighted by how far the vertex is below
    # the middle section's cavity boundary (tip -> deepest), so nothing switches on or off from one frame to the next.
    zc = pc[:, 1]
    mm = pm.measure_profile(pc)
    over = bool(mm["overhanging"])
    if over:
        # MATERIAL indices (fixed samples of the final pose), not the measured landmarks: the inner arc is nearly vertical
        # around its deepest point, so the measured index flickers along it from frame to frame
        k_t, k_d = i_t, i_d
    else:
        k_t = k_d = int(np.argmax(zc))             # no overhang: the front face starts at the crest
    z_env = np.minimum.accumulate(zs_mid[k_d:]) - 1e-7 * np.arange(zs_mid.size - k_d)   # strictly decreasing
    zf = z_env[::-1]
    xf = pc[k_d:, 0][::-1]
    Xf, Zf = X[:, i_c + 1:], Z[:, i_c + 1:]
    soft = _smooth((Zf - 0.004) / 0.02)
    # (b) everything below the deepest point's height: behind the inner arc / front face (nearby boundary, continuous)
    # without overhang the limit starts on the flat crest cap, where x(z) is ill-conditioned; with overhang it starts
    # at the deepest point, where the boundary is vertical (well-conditioned, and it must join rule (c) continuously)
    cap = 1.0 if over else _smooth((0.97 * zf[-1] - Zf) / max(0.12 * zf[-1], 1e-6))
    pull = np.maximum(Xf - np.interp(Zf, zf, xf), 0.0) * soft * (Zf <= zf[-1]) * cap
    if over:
        # Two regimes per ROW, blended only where both give (nearly) the same contained position:
        #   trunk-like rows (not yet overhanging, or with a lip that has barely started): rule (c), everything between the
        #       deepest point's height and the armpit's height goes behind the upper inner arc -> hidden in the trunk.
        #       These rows MUST be pulled fully: their natural front face stands in the air of the cavity.
        #   rows with a real lip: rule (d), half-plane test of every head vertex against the middle section's boundary at
        #       the SAME MATERIAL POINT (outward normal) -> their smaller lobe and smaller cavity stay inside the middle ones.
        #   The blend happens just ABOVE the row's own onset, where the lip is still a stub inside the neck (no air between
        #   the two positions), never below it.
        i_a = motion.i_armpit
        tau_on = motion._tau_table[3]
        w_row = (1.0 - _smooth((tau_c * A - (tau_on + 0.02)) / 0.10))[:, None]
        seg = slice(i_c + 1, i_d + 1)
        tx = np.gradient(pc[:, 0])[seg]
        tz = np.gradient(zs_mid)[seg]
        tn = np.maximum(np.hypot(tx, tz), 1e-12)
        nx, nz = -tz / tn, tx / tn                                   # outward (air side) normal of the middle section
        dn = (X[:, seg] - pc[seg, 0][None, :]) * nx[None, :] + (Z[:, seg] - pc[seg, 1][None, :]) * nz[None, :]
        corr = np.maximum(dn, 0.0) * (1.0 - w_row)
        corr[same] = 0.0
        X[:, seg] -= corr * nx[None, :]
        Z[:, seg] -= corr * nz[None, :]
        Xf, Zf = X[:, i_c + 1:], Z[:, i_c + 1:]
        soft = _smooth((Zf - 0.004) / 0.02)
        az = np.minimum.accumulate(zs_mid[i_a:i_d + 1]) - 1e-7 * np.arange(i_d + 1 - i_a)      # armpit -> deepest, decreasing
        x_arc = np.interp(Zf, az[::-1], pc[i_a:i_d + 1, 0][::-1])
        pull_c = np.maximum(Xf - x_arc, 0.0) * soft * (Zf > zf[-1]) * (Zf < float(az[0])) * w_row
        pull = np.maximum(Xf - np.interp(Zf, zf, xf), 0.0) * soft * (Zf <= zf[-1]) * cap + pull_c
    pull[same] = 0.0
    Xn = Xf - pull
    lo = i_d - (i_c + 1)
    Xn[~same, lo:] = np.minimum.accumulate(Xn[~same][:, lo:][:, ::-1], axis=1)[:, ::-1]   # keep the vertex order
    X[:, i_c + 1:] = Xn

    # in front of the middle section's foot the flanks are flat water (nothing may stand in front of the trough)
    k_foot = k_d + int(np.argmax(pc[k_d:, 1] <= 0.004)) if (pc[k_d:, 1] <= 0.004).any() else pc.shape[0] - 1
    flat = 1.0 - _smooth((X[:, i_d:] - (pc[k_foot, 0] - 0.10)) / 0.10)
    flat[same] = 1.0
    Z[:, i_d:] *= flat
    n_out, max_move = int(np.count_nonzero(pull > 1e-9)), float(pull.max())
    if stats is not None:
        stats.append((frame, n_out, max_move, float(push.max())))
    return X, Z


def grid_faces(n_u, n_v):
    j, i = np.meshgrid(np.arange(n_v - 1), np.arange(n_u - 1), indexing="ij")
    a = (j * n_u + i).ravel()
    return np.stack([a, a + n_u, a + n_u + 1, a + 1], axis=1)       # normals point up / outwards


def frame_vertices(motion, frame, y, d, H, state=None):
    """World vertices (n_v * n_u, 3) in metres for one frame.  `state` carries the smoothed clip target.
    flank_mode 'regress' (default): d is the flank coordinate u of v_layout_regress; 'lift_clip': taper coordinate."""
    if str(motion.WP.get("flank_mode", "regress")) == "regress":
        stats = state.setdefault("stats", []) if state is not None else None
        X, Z = regress_sections(motion, frame, motion.WP, d, stats)
        mid = int(np.argmin(d))
        p = np.stack([X[mid], Z[mid]], axis=1)
        Y = np.repeat(y[:, None], X.shape[1], axis=1)
        return np.stack([X * H, Y * H, Z * H], axis=-1).reshape(-1, 3), p, None
    p = motion.profile(frame)
    m = pm.measure_profile(p)
    lm = m["landmarks"]
    if m["overhanging"]:
        ub = [int(lm["head_tip"]["index"]), int(lm["inner_deepest"]["index"])]
        xt = float(lm["inner_deepest"]["H"][0])
    else:
        ub = None
        xt = float(lm["theta_point"]["H"][0])
    xt_rel = xt - float(p[motion.i_c, 0])                           # relative to the crest sample: smooth in time
    if state is not None:
        prev = state.get("xt_rel")
        if prev is not None:
            xt_rel = prev + float(np.clip(xt_rel - prev, -0.012, 0.012))   # rate limit: no popping flanks
        state["xt_rel"] = xt_rel
    X, Z = lift_clip_sections(p, xt_rel + float(p[motion.i_c, 0]), d, ub)
    Y = np.repeat(y[:, None], p.shape[0], axis=1)
    V = np.stack([X * H, Y * H, Z * H], axis=-1).reshape(-1, 3)
    return V, p, m


def polyline_self_intersections(p):
    """number of proper crossings between non-adjacent segments (O(n^2), n ~ 420)."""
    a, b = p[:-1], p[1:]
    n = len(a)
    r = b - a

    def cross(u, v):
        return u[..., 0] * v[..., 1] - u[..., 1] * v[..., 0]

    qp = a[None, :, :] - a[:, None, :]
    rxs = cross(r[:, None, :], r[None, :, :])
    t = cross(qp, r[None, :, :]) / np.where(rxs == 0, np.nan, rxs)
    u = cross(qp, r[:, None, :]) / np.where(rxs == 0, np.nan, rxs)
    hit = (t > 1e-9) & (t < 1 - 1e-9) & (u > 1e-9) & (u < 1 - 1e-9)
    idx = np.arange(n)
    hit &= np.abs(idx[:, None] - idx[None, :]) > 1
    return int(np.count_nonzero(hit) // 2)
