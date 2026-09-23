"""Painting frame <-> scene coordinates (spec section 4).  numpy only.

Conventions
-----------
* pixel coords : origin top-left, x right, y down, CONTINUOUS.  Pixel (i, j)
  (column i, row j) covers [i, i+1] x [j, j+1] and has its centre at
  (i + 0.5, j + 0.5).  x in [0, 3859], y in [0, 2594].
* pct coords   : left % of image WIDTH, top % of image HEIGHT (spec section 5).
* H coords     : (X_H, Z_H) in units of the wave height H.  Crest = (0, 1),
  trough water level Z_H = 0, +X = boat side (right in the painting).
* metres       : H coords * WAVE_HEIGHT_M.
* 'pct_h'      : a LENGTH in % of image height (1 % = 25.94 px = 0.0151515 H).
  Horizontal differences are ALSO expressed in % of image HEIGHT.

Defining values (params.json): crest_left_pct, crest_top_pct, height_pct and
the painting size.  Everything else is derived here:

    frame_h  = 100 / height_pct                      = 1.515152 H
    frame_w  = frame_h * width_px / height_px        = 2.254036 H
    x_left   = -crest_left_pct/100 * frame_w         = -0.861042 H
    x_right  = x_left + frame_w                      = +1.392994 H
    z_top    = 1 + crest_top_pct/100 * frame_h       = +1.131818 H
    z_bottom = z_top - frame_h                       = -0.383333 H
"""
import math

import numpy as np

from . import paths


class Frame:
    """Conversions for one painting frame.  All methods accept scalars or arrays."""

    def __init__(self, width_px=3859, height_px=2594, crest_left_pct=38.2,
                 crest_top_pct=8.7, height_pct=66.0, wave_height_m=11.0):
        self.width_px = int(width_px)
        self.height_px = int(height_px)
        self.crest_left_pct = float(crest_left_pct)
        self.crest_top_pct = float(crest_top_pct)
        self.height_pct = float(height_pct)
        self.H = float(wave_height_m)

        self.frame_h = 100.0 / self.height_pct
        self.frame_w = self.frame_h * self.width_px / self.height_px
        self.x_left = -self.crest_left_pct / 100.0 * self.frame_w
        self.x_right = self.x_left + self.frame_w
        self.z_top = 1.0 + self.crest_top_pct / 100.0 * self.frame_h
        self.z_bottom = self.z_top - self.frame_h
        # H units per pixel (identical in x and y because the pixels are square)
        self.H_per_px = self.frame_h / self.height_px
        self.px_per_H = self.height_px / self.frame_h

    # ---- construction -------------------------------------------------
    @classmethod
    def from_params(cls, params_path=None, wave_height_m=None):
        p = lambda k: paths.param(k, params_path)
        return cls(p("painting_width_px"), p("painting_height_px"), p("crest_left_pct"),
                   p("crest_top_pct"), p("height_pct"),
                   p("WAVE_HEIGHT_M") if wave_height_m is None else wave_height_m)

    def summary(self):
        keys = ("width_px", "height_px", "crest_left_pct", "crest_top_pct", "height_pct", "H",
                "frame_h", "frame_w", "x_left", "x_right", "z_top", "z_bottom",
                "H_per_px", "px_per_H")
        return {k: getattr(self, k) for k in keys}

    # ---- positions ----------------------------------------------------
    def px_to_H(self, x_px, y_px):
        x_px = np.asarray(x_px, dtype=np.float64)
        y_px = np.asarray(y_px, dtype=np.float64)
        X = self.x_left + (x_px / self.width_px) * self.frame_w
        Z = self.z_top - (y_px / self.height_px) * self.frame_h
        return X, Z

    def H_to_px(self, X_H, Z_H):
        X_H = np.asarray(X_H, dtype=np.float64)
        Z_H = np.asarray(Z_H, dtype=np.float64)
        x = (X_H - self.x_left) / self.frame_w * self.width_px
        y = (self.z_top - Z_H) / self.frame_h * self.height_px
        return x, y

    def pct_to_px(self, left_pct, top_pct):
        return (np.asarray(left_pct, dtype=np.float64) / 100.0 * self.width_px,
                np.asarray(top_pct, dtype=np.float64) / 100.0 * self.height_px)

    def px_to_pct(self, x_px, y_px):
        return (np.asarray(x_px, dtype=np.float64) / self.width_px * 100.0,
                np.asarray(y_px, dtype=np.float64) / self.height_px * 100.0)

    def pct_to_H(self, left_pct, top_pct):
        return self.px_to_H(*self.pct_to_px(left_pct, top_pct))

    def H_to_pct(self, X_H, Z_H):
        return self.px_to_pct(*self.H_to_px(X_H, Z_H))

    def H_to_m(self, X_H, Z_H):
        return (np.asarray(X_H, dtype=np.float64) * self.H,
                np.asarray(Z_H, dtype=np.float64) * self.H)

    def m_to_H(self, X_m, Z_m):
        return (np.asarray(X_m, dtype=np.float64) / self.H,
                np.asarray(Z_m, dtype=np.float64) / self.H)

    def px_to_m(self, x_px, y_px):
        return self.H_to_m(*self.px_to_H(x_px, y_px))

    def m_to_px(self, X_m, Z_m):
        return self.H_to_px(*self.m_to_H(X_m, Z_m))

    # (N, 2) array variants -------------------------------------------
    def pts_px_to_H(self, pts_px):
        pts_px = np.asarray(pts_px, dtype=np.float64)
        X, Z = self.px_to_H(pts_px[..., 0], pts_px[..., 1])
        return np.stack([X, Z], axis=-1)

    def pts_H_to_px(self, pts_H):
        pts_H = np.asarray(pts_H, dtype=np.float64)
        x, y = self.H_to_px(pts_H[..., 0], pts_H[..., 1])
        return np.stack([x, y], axis=-1)

    # ---- lengths ------------------------------------------------------
    def px_to_pct_h(self, d_px):
        """length in px -> % of image height (also for horizontal lengths)."""
        return np.asarray(d_px, dtype=np.float64) / self.height_px * 100.0

    def pct_h_to_px(self, d_pct):
        return np.asarray(d_pct, dtype=np.float64) / 100.0 * self.height_px

    def H_to_pct_h(self, d_H):
        return np.asarray(d_H, dtype=np.float64) / self.frame_h * 100.0

    def pct_h_to_H(self, d_pct):
        return np.asarray(d_pct, dtype=np.float64) / 100.0 * self.frame_h

    def m_to_pct_h(self, d_m):
        return self.H_to_pct_h(np.asarray(d_m, dtype=np.float64) / self.H)

    def pct_h_to_m(self, d_pct):
        return self.pct_h_to_H(d_pct) * self.H

    def px_to_H_len(self, d_px):
        return np.asarray(d_px, dtype=np.float64) * self.H_per_px

    def H_to_px_len(self, d_H):
        return np.asarray(d_H, dtype=np.float64) * self.px_per_H

    # ---- angles -------------------------------------------------------
    @staticmethod
    def px_dir_to_deg(dx_px, dy_px):
        """Direction of a pixel-space vector as an angle in the X-Z plane:
        0 deg = +X (right), +90 deg = up (+Z), -90 deg = down.  (y is down in px.)"""
        return np.degrees(np.arctan2(-np.asarray(dy_px, dtype=np.float64),
                                     np.asarray(dx_px, dtype=np.float64)))

    # ---- CAM_print ----------------------------------------------------
    def cam_print(self, res_x=None, distance_m=None, clip_m=None):
        """Numbers of the judging camera (spec section 4), in METRES.

        Orthographic, looking along +Y, framing [x_left, x_right] x [z_bottom, z_top].
        Blender: rotation_euler = (pi/2, 0, 0) XYZ -> camera right = +X, camera up = +Z,
        view direction = +Y.  With sensor_fit AUTO and res_x > res_y the ortho_scale
        is the WIDTH of the view.

        res_x : render width in px (default: painting width).  res_y is derived with
        round(); for res_x != width_px the aspect is off by < 1/res_y, the dict
        reports the z-range that is really covered ('z_range_covered_m').
        """
        res_x = self.width_px if res_x is None else int(res_x)
        res_y = int(round(res_x * self.height_px / self.width_px))
        if distance_m is None:
            try:
                distance_m = float(paths.param("cam_print_distance_m"))
            except Exception:
                distance_m = 200.0
        if clip_m is None:
            try:
                clip_m = [float(v) for v in paths.param("cam_print_clip_m")]
            except Exception:
                clip_m = [0.1, 1000.0]
        H = self.H
        cx = 0.5 * (self.x_left + self.x_right) * H
        cz = 0.5 * (self.z_top + self.z_bottom) * H
        ortho_scale = self.frame_w * H
        half_z = 0.5 * ortho_scale * res_y / res_x
        return {
            "name": "CAM_print",
            "type": "ORTHO",
            "ortho_scale": ortho_scale,
            "sensor_fit": "AUTO",
            "location": (cx, -float(distance_m), cz),
            "rotation_euler_xyz": (math.pi / 2.0, 0.0, 0.0),
            "clip_start": clip_m[0],
            "clip_end": clip_m[1],
            "resolution_x": res_x,
            "resolution_y": res_y,
            "pixel_aspect": 1.0,
            "x_range_m": (self.x_left * H, self.x_right * H),
            "z_range_m": (self.z_bottom * H, self.z_top * H),
            "z_range_covered_m": (cz - half_z, cz + half_z),
            "px_per_m": res_x / ortho_scale,
        }

    def make_cam_print(self, scene=None, res_x=None, name="CAM_print", make_active=True):
        """Create (or update) the CAM_print camera object in Blender and set the
        render resolution of `scene`.  Returns the camera object.  Needs bpy."""
        import bpy
        scene = scene or bpy.context.scene
        spec = self.cam_print(res_x=res_x)
        cam_data = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = spec["ortho_scale"]
        cam_data.sensor_fit = "AUTO"
        cam_data.shift_x = 0.0
        cam_data.shift_y = 0.0
        cam_data.clip_start = spec["clip_start"]
        cam_data.clip_end = spec["clip_end"]
        obj = bpy.data.objects.get(name)
        if obj is None:
            obj = bpy.data.objects.new(name, cam_data)
        else:
            obj.data = cam_data
        if obj.name not in scene.collection.all_objects:
            scene.collection.objects.link(obj)
        obj.rotation_mode = "XYZ"
        obj.location = spec["location"]
        obj.rotation_euler = spec["rotation_euler_xyz"]
        obj.scale = (1.0, 1.0, 1.0)
        scene.render.resolution_x = spec["resolution_x"]
        scene.render.resolution_y = spec["resolution_y"]
        scene.render.resolution_percentage = 100
        scene.render.pixel_aspect_x = 1.0
        scene.render.pixel_aspect_y = 1.0
        if make_active:
            scene.camera = obj
        return obj


# spec landmarks in pct coords (left %, top %) -- spec section 5
SPEC_LANDMARKS_PCT = {
    "S1_crest": (38.2, 8.7),
    "S2_inner_arc_deepest": (39.5, 46.3),
    "S6_claw_rightmost": (59.2, 33.0),
}
SPEC_TROUGH_TOP_PCT = 74.7

_default = None


def get_frame(reload=False):
    """The Frame built from params.json (cached)."""
    global _default
    if _default is None or reload:
        if reload:
            paths.clear_cache()
        _default = Frame.from_params()
    return _default
