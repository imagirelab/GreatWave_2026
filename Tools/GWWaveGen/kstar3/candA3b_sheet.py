# -*- coding: utf-8 -*-
"""Q21 candidate A3b, step 2: our sheet on the smoothed reference large forms.

Each row plane c (the loop-2 grid: 240 rows, row 159 = c 0) cuts the PLACED smoothed field (candA3b_model.py,
candA3b_place.py: crest top on the K* anchor, H0 20.75 m, sea at 0).  The water region above the sea is
    W = {field > 0.5}  U  {y < 0},
and our row curve is the upper boundary of W from the back sea over the crest, lip and barrel down the barrel wall.
Below the barrel's back-most point the model's plinth / bowl (its own sculpted sea) is replaced by our open-sea foot
(the wall runs on into a front trough and rises to the flat sea: D2); behind, the model's steep bowl side below 0.3 H
is replaced by a concave flare into the back sea (D1).  Rows outside the model's wave (the near shoulder c < c_near and
the far end c > c_far) are our own design (candA3b_ends.py).  The row curves are resampled to 400 columns with the K*
landmark columns (j_B 18, j_top 90, j_tip 200, j_corner 314, j_facebot 379, j_E 394) and smoothed along the crest.
"""
import sys, os, json, math
import numpy as np
from scipy import ndimage as ndi
from scipy.ndimage import gaussian_filter1d
from scipy.special import ndtri
from scipy.interpolate import PchipInterpolator
from candA3b_common import smoothstep
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import candA3b_common as B

LMK = ["j_B", "j_top", "j_tip", "j_corner", "j_facebot", "j_E"]


class PlacedField:
    """the smoothed model field seen through the chosen whole-body placement (candA3b_place.transform):
    placed = (s sa (cos th a' - sin th c'), s y, s sc (sin th a' + cos th c')),  a' = a - a_top, c' = c - c_top."""
    def __init__(self, path=B.FIELD, pl=None):
        self.f, self.a0, self.y0, self.c0, self.res = B.load_field(path)
        pl = pl or json.load(open(os.path.join(B.TMP, "placement.json")))
        self.top = np.array(pl["model_top_model_frame"], float)
        self.s = C.H0_KSTAR / self.top[1]
        self.th, self.sa, self.sc, self.k = pl.get("chosen", {"p": [0.0, 1.0, 1.0, 0.0]})["p"]

    def to_model(self, a, y, c):
        t = math.radians(self.th)
        u = (a - self.k * (y - C.H0_KSTAR)) / (self.s * self.sa); v = c / (self.s * self.sc)
        am = math.cos(t) * u + math.sin(t) * v + self.top[0]
        cm = -math.sin(t) * u + math.cos(t) * v + self.top[2]
        return am, y / self.s, cm

    def value(self, a, y, c):
        am, ym, cm = self.to_model(np.asarray(a, float), np.asarray(y, float), np.asarray(c, float))
        k = [(cm - self.c0) / self.res - 0.5, (ym - self.y0) / self.res - 0.5, (am - self.a0) / self.res - 0.5]
        return ndi.map_coordinates(self.f, [np.ravel(x) for x in np.broadcast_arrays(*k)], order=1, mode="constant", cval=0.0).reshape(np.broadcast(*k).shape)

    def section(self, c, a_lo=-40.0, a_hi=34.0, y_lo=-1.0, y_hi=25.0, step=0.05):
        """2-D field of the placed model on the plane c (rows = y ascending, cols = a ascending)."""
        aa = np.arange(a_lo, a_hi + 1e-9, step); yy = np.arange(y_lo, y_hi + 1e-9, step)
        YY, AA = np.meshgrid(yy, aa, indexing="ij")
        return aa, yy, self.value(AA, YY, np.full_like(AA, c))


def upper_boundary(aa, yy, g, sea_w=0.08):
    """the boundary of W = {g > .5} U {y < 0} from the left edge (back sea) to the right edge (front sea)."""
    from skimage import measure
    sea = np.clip(0.5 - yy / sea_w, 0.0, 1.0)[:, None]
    f2 = np.maximum(g, sea)
    cs = measure.find_contours(f2, 0.5)
    best = None
    for cn in cs:
        P = np.stack([aa[0] + cn[:, 1] * (aa[1] - aa[0]), yy[0] + cn[:, 0] * (yy[1] - yy[0])], -1)
        touches_l = np.min(P[[0, -1], 0]) < aa[0] + 0.2
        touches_r = np.max(P[[0, -1], 0]) > aa[-1] - 0.2
        if touches_l and touches_r:
            if P[0, 0] > P[-1, 0]:
                P = P[::-1]
            if best is None or len(P) > len(best):
                best = P
    islands = []
    for cn in cs:
        P = np.stack([aa[0] + cn[:, 1] * (aa[1] - aa[0]), yy[0] + cn[:, 0] * (yy[1] - yy[0])], -1)
        if np.allclose(P[0], P[-1]) and len(P) > 20 and P[:, 1].min() > 0.3:
            islands.append(P)
    return best, islands


CORNER_FRAC = 0.45


def landmarks_raw(P, lo=0.15, hi=0.8):
    """indices of the landmark points on a raw row curve (back sea -> ... -> front sea).
    corner = the back-most point of the inner face (after the top, lo H..hi H, before the curve reaches the sea);
    tip = the front-most point between the top and the corner (the lip nose; for a closing stub its top-front)."""
    a, y = P[:, 0], P[:, 1]
    H = y.max()
    it = int(np.argmax(y))
    after = np.arange(it, len(P))
    low = after[y[after] < 0.05 * H]
    end = int(low[0]) if len(low) else len(P) - 1
    seg = np.arange(it + 1, max(end, it + 2))
    ok = seg[(y[seg] > lo * H) & (y[seg] < hi * H)]
    ic0 = int(ok[np.argmin(a[ok])]) if len(ok) else min(it + 1, len(P) - 1)
    seg2 = np.arange(it, ic0 + 1)
    ip = int(seg2[np.argmax(a[seg2])])
    # the barrel's wall point at a fixed relative height (a stable landmark along the crest: the back-most point of a
    # flat wall jumps between rows)
    seg3 = np.arange(ip + 1, max(end, ip + 2))
    dn = seg3[y[seg3] <= CORNER_FRAC * H]
    ic = int(dn[0]) if len(dn) else ic0
    b = np.nonzero(y[:it] < 0.02)[0]
    ib = int(b[-1]) if len(b) else 0
    return {"top": it, "tip": ip, "corner": ic, "foot": ib, "wall_end": end}


def smooth_poly(P, sig_m=0.25):
    s = C.arclen(P[:, 0], P[:, 1])
    ss = np.arange(0, s[-1], 0.05)
    Q = np.stack([np.interp(ss, s, P[:, 0]), np.interp(ss, s, P[:, 1])], -1)
    k = sig_m / 0.05
    Q = np.stack([gaussian_filter1d(Q[:, 0], k, mode="nearest"), gaussian_filter1d(Q[:, 1], k, mode="nearest")], -1)
    return Q


# ====================================================================== design field of one row
def upper_sky_floor(yy, allowed):
    """per column a: lowest y of the top-most sky run (the painted outline's cone seen in this plane); nan if none."""
    sky = ~allowed
    ny = sky.shape[0]
    out = np.full(sky.shape[1], np.nan)
    for j in np.nonzero(sky[-1])[0]:
        col = sky[:, j]
        k = ny - 1
        while k > 0 and col[k - 1]:
            k -= 1
        out[j] = yy[k]
    return out

def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def mask_sdf(m, step):
    """signed distance (m) of a boolean mask on a regular grid: negative inside."""
    if not m.any():
        return np.full(m.shape, 1e3, np.float32)
    if m.all():
        return np.full(m.shape, -1e3, np.float32)
    din = ndi.distance_transform_edt(m) * step
    dout = ndi.distance_transform_edt(~m) * step
    return np.where(m, -(din - 0.5 * step), dout - 0.5 * step).astype(np.float32)


class Design:
    """per-row design field: placed smoothed model (with a smooth vertical stretch s_y(c) for the shoulder), united with
    the barrel wall and roof of the far rows (hidden behind the painting's sky pocket), carved only where it sticks out of
    the painted silhouette (the painting-view silhouette cone, smooth intersection)."""

    def __init__(self, prm, pf=None):
        self.prm = prm
        self.pf = pf or PlacedField()
        self.V1, self.tgt, self.fr = C.painting_frame()
        g = prm["field"]
        self.aa = np.arange(g["a_lo"], g["a_hi"] + 1e-9, g["step"])
        self.yy = np.arange(g["y_lo"], g["y_hi"] + 1e-9, g["step"])
        self.step = g["step"]
        self.YY, self.AA = np.meshgrid(self.yy, self.aa, indexing="ij")

    # ---------------------------------------------------------------- painting masks of a plane
    def allowed(self, c, smooth=None):
        """True where the plane point projects into the painted wave (not sky) or below the horizon."""
        X = self.fr.world(np.full(1, c), self.AA.reshape(1, -1), self.YY.reshape(1, -1)).reshape(-1, 3)
        P = self.fr.cam.project(X)
        s = self.tgt.sample(P[:, :2], comp=True)
        ok = (s <= 0.0) | (P[:, 1] > B.HORIZON) | (P[:, 2] <= 0.5)
        ok = ok.reshape(self.AA.shape)
        sm = self.prm.get("allowed_smooth_m", 0.0) if smooth is None else smooth
        if sm > 0:
            # large-form version of the painted silhouette cone (claw heads / foam wiggles smoothed away); the final
            # edge lock (candA3b_fit.py) fits the true outline at the edges
            dal = ndi.gaussian_filter(mask_sdf(ok, self.step), sm / self.step)
            ok = dal < 0
        return ok, s.reshape(self.AA.shape)

    def pocket(self, c, allowed):
        """the painted sky pocket under the lip in plane c: wall front a_f(y) (pocket's left boundary), its top-left corner
        height, and the pocket top y_pt(a) (the lip band's bottom) with the lip-tip line."""
        sky = ~allowed
        yy, aa = self.yy, self.aa
        iy5 = int(np.argmin(np.abs(yy - 5.0)))
        row = np.nonzero(sky[iy5])[0]
        if len(row) == 0:
            return None
        lab, n = ndi.label(sky)
        comp = lab == lab[iy5, row[0]]
        af = np.full(len(yy), np.nan)
        for i in range(len(yy)):
            r = np.nonzero(comp[i])[0]
            if len(r) and yy[i] >= 2.0:
                af[i] = aa[r[0]]
        # continuous part from y 3 upward (stop at a jump > 1.5 m: the upper sky)
        i0 = int(np.argmin(np.abs(yy - 3.0)))
        top = i0
        for i in range(i0 + 1, len(yy)):
            if not np.isfinite(af[i]) or abs(af[i] - af[i - 1]) > 1.5:
                break
            top = i
        # pocket top per column: top of the lowest run of the component (below the lip band)
        ypt = np.full(len(aa), np.nan)
        for j in range(len(aa)):
            r = np.nonzero(comp[:, j])[0]
            if len(r) == 0:
                continue
            k = r[0]
            while k + 1 < len(yy) and comp[k + 1, j]:
                k += 1
            if k < len(yy) - 1:
                ypt[j] = yy[k]
        return {"af": af, "i_corner": top, "y_corner": float(yy[top]), "ypt": ypt, "comp": comp}

    # ---------------------------------------------------------------- the row field
    def pocket_region(self, c, allowed):
        """the painted sky pocket under the lip in plane c, cut off from the upper sky at the lip-tip level and continued
        below the horizon (the barrel's wall runs on down to the sea): boolean mask + lip-tip / corner numbers."""
        pk = self.pocket(c, allowed)
        if pk is None:
            return None, None
        yy, aa = self.yy, self.aa
        ypt = pk["ypt"].copy()
        comp = pk["comp"]
        band = np.isfinite(ypt)
        # columns of the lip band: from the wall to the lip-tip line (last band column before the band ends)
        jb = np.nonzero(band)[0]
        if len(jb) == 0:
            return None, None
        # keep the contiguous band run that contains the pocket's top-left corner (the barrel ceiling)
        ic = pk["i_corner"]
        a_corner = pk["af"][ic]
        j0 = int(np.argmin(np.abs(aa - a_corner)))
        runs = np.split(jb, np.nonzero(np.diff(jb) > 1)[0] + 1)
        run = min(runs, key=lambda r: 0 if r[0] <= j0 + 20 <= r[-1] + 20 else abs(r[0] - j0))
        jt = int(run[-1]); y_tip = float(ypt[jt])
        pm = np.zeros_like(allowed)
        for j in range(len(aa)):
            if j < run[0]:
                col = comp[:, j] & (yy <= pk["y_corner"])
            elif j <= jt:
                col = comp[:, j] & (yy <= ypt[j])
            else:
                col = comp[:, j] & (yy <= y_tip)
            pm[:, j] = col
        # below the horizon the pocket continues down to the sea along the wall's slope near y 3..4
        i3 = int(np.argmin(np.abs(yy - 3.0))); i4 = int(np.argmin(np.abs(yy - 4.0)))
        a3, a4 = pk["af"][i3], pk["af"][i4]
        if np.isfinite(a3) and np.isfinite(a4):
            slope = (a3 - a4) / (yy[i3] - yy[i4])            # da/dy (negative: the wall leans back going up)
            for i in range(0, i3):
                af_i = a3 + slope * (yy[i] - yy[i3]) * 0.6
                pm[i] |= aa >= af_i
        return pm, {"y_corner": pk["y_corner"], "a_corner": float(a_corner), "a_tip": float(aa[jt]), "y_tip": y_tip,
                    "a_wall_4m": float(a4) if np.isfinite(a4) else None, "ypt": ypt}

    def row_sdf(self, c, sy=1.0, info=None, family="M", carve=True):
        """family M: the placed smoothed model (main body and shoulder); family S: our barrel (shell around the painted
        pocket, lip roof in the painted lip band, closure) -- the two are blended row-wise in the overlap."""
        prm = self.prm
        allowed, s_img = self.allowed(c)
        fw = prm["far"]
        if family == "M":
            g = self.pf.value(self.AA, self.YY / sy, np.full_like(self.AA, c))
            d = (-prm["model_sigma"] * ndtri(np.clip(g, 2e-3, 1 - 2e-3))).astype(np.float32)
            wgt = 0.0
        else:
            d = np.full(self.AA.shape, 1e3, np.float32)
            wgt = 1.0
        pm = None
        pinfo = None
        if wgt > 0:
            pm, pinfo = self.pocket_region(c, allowed)
            if pm is not None:
                dp = mask_sdf(pm, self.step)                       # distance to the pocket (negative inside)
                # transition: the shell starts behind the pocket (at the model's own inner face) and reaches the pocket's
                # boundary (the painted 72) at c1_off; rows nearer the camera keep the model's face
                off = fw["off0"] * (1.0 - float(smoothstep((c - fw["off_c0"]) / (fw["off_c1"] - fw["off_c0"]))))
                off = off * smoothstep((pinfo["y_corner"] - 2.5 - self.YY) / 3.0)      # the wall only, not the ceiling
                dp = dp - off
                yy = self.YY
                # shell thickness: wall_t on the wall, roof_t at the ceiling, a flare at the wall's foot
                t = fw["wall_t"] + (fw["roof_t"] - fw["wall_t"]) * smoothstep((yy - (pinfo["y_corner"] - 3.0)) / 3.0)
                t = t + fw["wall_flare"] * np.clip(1.0 - yy / fw["flare_h"], 0.0, 1.0) ** 2
                t = t * wgt
                # the shell on the wall / ceiling side only (not over the lip tip into the open sky, not in front)
                side = (self.AA <= pinfo["a_tip"] + 0.5)
                shell = np.where(side, np.maximum(-dp - 0.0, dp - t), 1e3)   # inside where 0 < dp < t
                d = smin(d, shell.astype(np.float32), prm["k_union"] * max(wgt, 0.3))
                # the lip roof fills the painted lip band above the pocket (up to the band's top and the far-row height
                # cap Hcap(c)): a full lip over the barrel, thin only where the painted band is thin
                if fw.get("roof_fill", 0) > 0:
                    ytop = upper_sky_floor(self.yy, allowed)
                    ypt = pinfo["ypt"]
                    hc = float(np.interp(c, [k[0] for k in fw["Hcap"]], [k[1] for k in fw["Hcap"]]))
                    roof = np.zeros_like(allowed)
                    a0r = pinfo["a_corner"] - fw["wall_t"]
                    a_pk = float(np.interp(c, [k[0] for k in fw["roof_peak_a"]], [k[1] for k in fw["roof_peak_a"]]))
                    for j in np.nonzero((self.aa >= a0r) & (self.aa <= pinfo["a_tip"]) & np.isfinite(ypt) & np.isfinite(ytop))[0]:
                        y1 = float(smin(ytop[j] - fw["roof_top_margin"], hc - (self.aa[j] - a_pk) ** 2 / (2.0 * fw["roof_cap_R"]), fw.get("roof_smin_k", 1.0)))
                        y0 = ypt[j] - fw["overlap"]
                        if y1 > y0:
                            roof[:, j] = (self.yy >= y0) & (self.yy <= y0 + wgt * fw["roof_fill"] * (y1 - y0) + 1e-6)
                    d = smin(d, mask_sdf(roof, self.step), prm["k_union"] * max(wgt, 0.3))
                    if info is not None:
                        info["Hcap"] = hc
                if info is not None:
                    info.update({k_: v_ for k_, v_ in pinfo.items() if k_ != "ypt"})
        elif family == "M" and fw.get("m_lip") and c >= fw["m_lip"][0]:
            # main rows: the lip fills the painted lip band too (one continuous hood with the barrel's roof; the lip is a
            # silhouette-forming edge region: 132 above, 72 below)
            lw = float(smoothstep((c - fw["m_lip"][0]) / (fw["m_lip"][1] - fw["m_lip"][0])))
            pm_, pinfo_ = self.pocket_region(c, allowed)
            if pm_ is not None and lw > 0:
                ytop = upper_sky_floor(self.yy, allowed)
                ypt = pinfo_["ypt"]
                hc = float(np.interp(c, [k[0] for k in fw["Hcap"]], [k[1] for k in fw["Hcap"]]))
                a_pk = float(np.interp(c, [k[0] for k in fw["roof_peak_a"]], [k[1] for k in fw["roof_peak_a"]]))
                roof = np.zeros_like(allowed)
                a0r = pinfo_["a_corner"] - fw["wall_t"]
                for j in np.nonzero((self.aa >= a0r) & (self.aa <= pinfo_["a_tip"]) & np.isfinite(ypt) & np.isfinite(ytop))[0]:
                    y1 = float(smin(ytop[j] - fw["roof_top_margin"], hc - (self.aa[j] - a_pk) ** 2 / (2.0 * fw["roof_cap_R"]), fw.get("roof_smin_k", 1.0)))
                    y0 = ypt[j] - fw["overlap"]
                    if y1 > y0:
                        roof[:, j] = (self.yy >= y1 - lw * (y1 - y0)) & (self.yy <= y1)
                d = smin(d, mask_sdf(roof, self.step), prm["k_union"])
                if info is not None:
                    info["m_lip_w"] = lw
        # far-end closure (1): the roof's nose retracts to the barrel's wall along the crest (the lip spirals back into
        # the wall while it still lies in the painted lip band; no quad sweeps through the sky pocket)
        rt = prm.get("retract")
        if rt and c > rt["c0"] and wgt > 0 and pm is not None:
            u = float(smoothstep((c - rt["c0"]) / (rt["c1"] - rt["c0"])))
            a_nose = pinfo["a_tip"] + (pinfo["a_corner"] - rt["behind_corner"] - pinfo["a_tip"]) * u
            y_cut = pinfo["y_corner"] - rt["below_corner"]
            d = smax(d, np.minimum(self.AA - a_nose, self.YY - y_cut).astype(np.float32), rt["k"])
            if info is not None:
                info["a_nose_cut"] = a_nose
        # far-end closure (2): the barrel sinks into the sea (vertical compression of the design), then the carve keeps
        # only what stays hidden behind the painted pocket's wall (the closing curl)
        cl = prm.get("close")
        if cl and c > cl["c0"]:
            sc = 1.0 - (1.0 - cl["s_min"]) * float(smoothstep((c - cl["c0"]) / (cl["c1"] - cl["c0"])))
            ys = self.yy / sc
            iy = (ys - self.yy[0]) / self.step
            d = ndi.map_coordinates(d, [np.repeat(iy[:, None], len(self.aa), 1), np.repeat(np.arange(len(self.aa))[None, :], len(self.yy), 0)],
                                    order=1, mode="nearest").astype(np.float32) * sc
            if info is not None:
                info["close_scale"] = sc
        # carve: smooth intersection with the allowed region (edge-only: removes what projects into the painted sky)
        if prm.get("carve", True) and carve:
            d = self.carve(c, d)
        d = ndi.gaussian_filter(d, prm.get("blur_px_S", prm.get("blur_px", 1.0)) if family == "S" else prm.get("blur_px", 1.0))
        return d, allowed

    def carve_sdf(self, c):
        """continuous signed distance (metres, in the row plane, positive = projects into the painted sky) from the
        painting's sky sdf (display px) scaled by depth / focal length; below the horizon everything is allowed."""
        if self.prm.get("carve_mode", "mask") == "mask":
            al, _ = self.allowed(c, self.prm.get("carve_smooth_m", 0.25))
            return mask_sdf(al, self.step)
        X = self.fr.world(np.full(1, c), self.AA.reshape(1, -1), self.YY.reshape(1, -1)).reshape(-1, 3)
        P = self.fr.cam.project(X)
        s = self.tgt.sample(P[:, :2], comp=True)
        # metres per display px at this depth: finite difference of the projection along y
        X2 = self.fr.world(np.full(1, c), self.AA.reshape(1, -1), self.YY.reshape(1, -1) + 0.1).reshape(-1, 3)
        P2 = self.fr.cam.project(X2)
        mpp = 0.1 / np.maximum(np.hypot(P2[:, 0] - P[:, 0], P2[:, 1] - P[:, 1]), 1e-6)
        d = np.minimum(s, B.HORIZON - P[:, 1]) * mpp
        d = np.where(P[:, 2] > 0.5, d, -10.0)
        d = d.reshape(self.AA.shape).astype(np.float32)
        sm = self.prm.get("carve_smooth_m", 0.0)
        return ndi.gaussian_filter(d, sm / self.step) if sm > 0 else d

    def carve(self, c, d, dal=None):
        """edge-only painting fit of the design: a uniform, low-frequency growth of the whole form by `grow` metres
        (the design then reaches past the painted outline everywhere), then the smooth intersection with the painting's
        silhouette cone: only what projects into the painted sky is removed, so the silhouette-forming edges follow the
        painted outline and the interior surfaces are the design's."""
        dal = self.carve_sdf(c) if dal is None else dal
        d = d - self.prm.get("grow", 0.0)
        return smax(d, dal - self.prm["carve_offset"], self.prm["k_carve"])

    def row_curve(self, c, sy=1.0, info=None, family="M"):
        d, allowed = self.row_sdf(c, sy, info, family)
        return self.extract(d)

    def extract(self, d):
        f2 = np.minimum(d, self.YY)        # union with the sea (y < 0)
        from skimage import measure
        cs = measure.find_contours(-f2, 0.0)
        best = None
        aa, yy = self.aa, self.yy
        for cn in cs:
            P = np.stack([aa[0] + cn[:, 1] * self.step, yy[0] + cn[:, 0] * self.step], -1)
            if np.min(P[[0, -1], 0]) < aa[0] + 0.2 and np.max(P[[0, -1], 0]) > aa[-1] - 0.2:
                if P[0, 0] > P[-1, 0]:
                    P = P[::-1]
                if best is None or len(P) > len(best):
                    best = P
        return best


# ====================================================================== row post-processing (our foot and trough)
def hermite(P0, T0, P1, T1, n=60):
    t = np.linspace(0, 1, n)[:, None]
    h00 = 2 * t ** 3 - 3 * t ** 2 + 1; h10 = t ** 3 - 2 * t ** 2 + t; h01 = -2 * t ** 3 + 3 * t ** 2; h11 = t ** 3 - t ** 2
    L = np.linalg.norm(np.asarray(P1) - np.asarray(P0))
    return h00 * P0 + h10 * L * np.asarray(T0) + h01 * P1 + h11 * L * np.asarray(T1)


def unit(v):
    v = np.asarray(v, float); return v / max(np.linalg.norm(v), 1e-12)


def tangent_at(P, i, w=6):
    i0, i1 = max(i - w, 0), min(i + w, len(P) - 1)
    return unit(P[i1] - P[i0])


def post_row(P, prm, W=None, protect=0.0, c_row=None, a_tr_override=None):
    """our back foot (concave flare into the back sea) and our front (the barrel wall runs on into a front trough that
    rises to the flat sea); returns the curve and the landmark indices (foot, top, tip, corner, trough, front)."""
    q = prm["post"]
    P = smooth_poly(P, q.get("smooth_m", 0.12))
    a, y = P[:, 0], P[:, 1]
    H = float(y.max())
    L = landmarks_raw(P)
    it, ip, ic = L["top"], L["tip"], L["corner"]
    # ---- front: cut the wall below the barrel's back-most point at h_w, continue into the trough
    hwf = q["hw_frac"] if c_row is None or not isinstance(q["hw_frac"], list) else float(np.interp(c_row, [k[0] for k in q["hw_frac"]], [k[1] for k in q["hw_frac"]]))
    h_w = max(hwf * H, q["hw_min"])
    seg = np.arange(ic, len(P))
    below = seg[y[seg] <= h_w]
    iw = int(below[0]) if len(below) else len(P) - 1
    Pw = P[iw].copy()
    tw = tangent_at(P, iw)
    ang = np.degrees(np.arctan2(-tw[1], tw[0]))               # angle below horizontal (90 = straight down)
    ang = float(np.clip(ang, q["wall_ang_min"], q["wall_ang_max"]))
    tw = np.array([math.cos(math.radians(ang)), -math.sin(math.radians(ang))])
    D = min(q["trough_frac"] * H, q["trough_max"])
    a_tr = Pw[0] + Pw[1] / math.tan(math.radians(ang)) * 0.8 + q["trough_ahead"] + q["trough_ahead_frac"] * H
    if a_tr_override is not None:
        a_tr = max(float(a_tr_override), Pw[0] + 1.0)
    Tb = np.array([a_tr, -D])
    F1 = hermite(Pw, tw, Tb, np.array([1.0, 0.0]), 80)
    Fe = np.array([a_tr + q["rise_len"] + q["rise_frac"] * H, 0.0])
    F2 = hermite(Tb, np.array([1.0, 0.0]), Fe, np.array([1.0, 0.0]), 60)
    if W is not None:
        # ---- back (D1): our round back from the crest top: a superellipse dome (horizontal at the crest) through the
        # model's body width W at 0.5 H (keeps the model's fullness), continued by a concave flare into the back sea.
        # For the barrel rows the dome is widened until it clears the design's own back (the hidden barrel wall).
        at = a[it]
        bq = q["dome"]
        ys = bq["ys_frac"] * H; n_ = bq["n"]; thm = math.radians(bq["theta_max_deg"])
        th = np.linspace(0.0, 0.5 * math.pi, 400)
        ua = np.sin(th) ** (2.0 / n_); uy = np.cos(th) ** (2.0 / n_)
        yv_ = ys + (H - ys) * uy
        w50 = float(np.interp(0.5 * H, yv_[::-1], ua[::-1]))
        Ra = W / max(w50, 1e-3)
        if bq.get("inner_min_t") is not None:
            # the dome stays at least inner_min_t behind the barrel's inner wall (the row curve after the lip, below
            # the lip tip): a thinner back never cuts into the barrel
            inner = P[ip:]
            yb2 = np.linspace(0.05 * H, min(0.85 * H, P[ip, 1] - 0.5), 100)
            aw = np.full(len(yb2), np.inf)
            for k_ in range(len(inner) - 1):
                y0_, y1_ = inner[k_, 1], inner[k_ + 1, 1]
                lo_, hi_ = min(y0_, y1_), max(y0_, y1_)
                m_ = (yb2 >= lo_) & (yb2 <= hi_) & (hi_ > lo_)
                if m_.any():
                    t_ = (yb2[m_] - y0_) / (y1_ - y0_)
                    aw[m_] = np.minimum(aw[m_], inner[k_, 0] + t_ * (inner[k_ + 1, 0] - inner[k_, 0]))
            ok2 = np.isfinite(aw)
            if ok2.any():
                uab2 = np.interp(np.maximum(yb2[ok2], ys), yv_[::-1], ua[::-1])
                need2 = (at - aw[ok2] + bq["inner_min_t"] * H) / np.maximum(uab2, 0.15)
                Ra = max(Ra, float(need2.max()))
        if protect > 0:
            back = P[:it + 1]
            yb = np.linspace(0.02 * H, bq["protect_top"] * H, 120)
            ao = np.full(len(yb), np.inf)
            for k_ in range(len(back) - 1):
                y0_, y1_ = back[k_, 1], back[k_ + 1, 1]
                lo_, hi_ = min(y0_, y1_), max(y0_, y1_)
                m_ = (yb >= lo_) & (yb <= hi_) & (hi_ > lo_)
                if m_.any():
                    t_ = (yb[m_] - y0_) / (y1_ - y0_)
                    ao[m_] = np.minimum(ao[m_], back[k_, 0] + t_ * (back[k_ + 1, 0] - back[k_, 0]))
            ok_ = np.isfinite(ao)
            uab = np.interp(np.maximum(yb, ys), yv_[::-1], ua[::-1])
            need = (at - ao[ok_] + bq["protect_margin"]) / np.maximum(uab[ok_], 0.15)
            if len(need):
                Ra = max(Ra, (1 - protect) * Ra + protect * float(need.max()))
        tt = np.linspace(0.0, thm, 160)
        dome = np.stack([at - Ra * np.sin(tt) ** (2.0 / n_), ys + (H - ys) * np.cos(tt) ** (2.0 / n_)], -1)[::-1]
        Pm = dome[0]
        tg = unit(dome[1] - dome[0])
        Lf = bq["flare_frac"] * H + bq["flare_len"]
        fl = hermite(np.array([Pm[0] - Lf, 0.0]), np.array([1.0, 0.0]), Pm, tg, 100)
        B1 = np.vstack([fl[:-1], dome])
        B1[-1] = P[it]
        ib = it
        Fb = B1[0]
    else:
        # ---- back: cut at h_b behind the top, concave flare into the back sea
        h_b = q["hb_frac"] * H
        segb = np.arange(it, -1, -1)
        lowb = segb[y[segb] <= h_b]
        ib = int(lowb[0]) if len(lowb) else 0
        Pb = P[ib].copy()
        tb = tangent_at(P, ib)
        tb = unit([max(tb[0], q["back_lean_min"]), max(tb[1], 0.3)])
        Lf = q["flare_len"] + q["flare_frac"] * H
        Fb = np.array([Pb[0] - Lf, 0.0])
        B1 = hermite(Fb, np.array([1.0, 0.0]), Pb, tb, 80)
    Q = np.vstack([B1[:-1], P[ib:iw], F1[:-1], F2])
    k0 = len(B1) - 1
    lm = {"j_B": 0, "j_top": k0 + (it - ib), "j_tip": k0 + (ip - ib), "j_corner": k0 + (ic - ib),
          "j_facebot": k0 + (iw - ib) + len(F1) - 1, "j_E": len(Q) - 1}
    return Q, lm, {"H": H, "h_w": h_w, "wall_ang": ang, "trough_D": D, "a_trough": float(a_tr), "a_foot": float(Fb[0])}


def resample400(Q, lm, a_back=-49.2, a_front=33.0):
    """400 columns with the K* landmark columns (arc length inside each landmark segment, continuous spacing)."""
    s = C.arclen(Q[:, 0], Q[:, 1])
    Ls = {k: s[v] for k, v in lm.items()}
    order = LMK
    for a_, b_ in zip(order[:-1], order[1:]):
        Ls[b_] = max(Ls[b_], Ls[a_] + 0.05)
    A = np.zeros(400); Y = np.zeros(400)
    jB, jE = C.LM["j_B"], C.LM["j_E"]
    aB = np.interp(Ls["j_B"], s, Q[:, 0]); aE = np.interp(Ls["j_E"], s, Q[:, 0])
    A[:jB + 1] = np.linspace(min(a_back, aB - 5), aB, jB + 1); Y[:jB + 1] = 0.0
    A[jE:] = np.linspace(aE, max(a_front, aE + 5), 400 - jE); Y[jE:] = 0.0
    segs = list(zip(order[:-1], order[1:]))
    u = [(Ls[k1] - Ls[k0]) / (C.LM[k1] - C.LM[k0]) for k0, k1 in segs]
    joint = [u[0]] + [float(np.sqrt(u[i] * u[i + 1])) for i in range(len(u) - 1)] + [u[-1]]
    for i, (k0, k1) in enumerate(segs):
        j0, j1 = C.LM[k0], C.LM[k1]
        n = j1 - j0
        h = np.linspace(joint[i], joint[i + 1], n)
        h = np.maximum(h, 1e-6); h *= (Ls[k1] - Ls[k0]) / h.sum()
        ss = Ls[k0] + np.r_[0.0, np.cumsum(h)]
        A[j0:j1 + 1] = np.interp(ss, s, Q[:, 0]); Y[j0:j1 + 1] = np.interp(ss, s, Q[:, 1])
    return A, Y


def area_above_sea(Q):
    """area between a row curve (sea -> sea) and still water, y >= 0 (polygon closed along y = 0, even-odd fill)."""
    P = np.stack([Q[:, 0], np.maximum(Q[:, 1], 0.0)], -1)
    segs = np.stack([P[:-1], P[1:]], 1)
    segs = np.concatenate([segs, np.array([[[P[-1, 0], 0.0], [P[0, 0], 0.0]]])], 0)
    img = C.rasterize_segments(segs, P[:, 0].min() - 1, P[:, 0].max() + 1, 0.0, max(P[:, 1].max(), 0.1) + 1, 0.1)
    return float(img.sum() * 0.01)
