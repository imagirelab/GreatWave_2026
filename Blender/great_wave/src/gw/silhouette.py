"""Silhouette mask of Blender mesh objects as seen by CAM_print, and the ordered
wave profile extracted from such a mask.  Method-agnostic: it only looks at evaluated
mesh geometry, so it works for shape-key meshes, Geometry Nodes, Alembic caches, ...

View geometry
-------------
CAM_print is orthographic and looks along +Y, so the silhouette is the projection of
all triangles onto the XZ plane ('any coverage' union).  `ViewRect` describes the
framed rectangle in WORLD units (metres) and the pixel grid; the default is the
CAM_print framing of gw.frame (spec section 4) but any rectangle can be used, e.g.
for the Houdini reference, which has a different size and position.

Important property of the problem (document for callers)
---------------------------------------------------------
The wave mesh is an OPEN SHEET.  Seen exactly edge-on, a sheet only fills its
silhouette where the surface VARIES along Y: a pure extrusion of the profile along Y
projects to a curve of zero area and rasterises to nothing.  The tapered ends (where the
section shrinks to the still-water plane) are what closes the mound: the sections
between the full profile and the flat end sweep the inside of the body.  Everything
below the still-water plane is filled by the 'water slab' (`water_z`).  Consequences:

* if the taper does not sweep the whole body, the mask has un-filled interior HOLES
  -> `raster.hole_report(mask)` / profile['holes'] report them;
* if smaller end sections cross the concavity under the head (e.g. a taper that only
  scales Z), they BLOCK the view through it: the mask is solid there and the inner
  arc disappears.  That is a property of the 3-D shape (spec section 5, note 2), not
  of this module; tests/selftest_measure.py demonstrates what it looks like.

Which evaluation is measured (2026-09-20, second hardening)
----------------------------------------------------------
Every function here evaluates objects with `bpy.context.evaluated_depsgraph_get()`, i.e. the VIEWPORT evaluation of
the dependency graph: modifiers count when `show_viewport` is on, subdivision-type modifiers use their viewport
`levels`.  A render or an Alembic export with evaluation mode RENDER uses `show_render` / `render_levels` instead, so
geometry that exists only at render time (or only in the viewport) would be measured wrongly without any symptom.
`viewport_render_mismatches(objs)` lists every such difference; the tests turn a non-empty list into verdict INVALID.

Profile
-------
`extract_profile(mask, rect)` returns the ordered boundary between wave and background
from the left frame edge over the crest, around the head, underneath it, down the
inner arc to the trough and along the water to the right frame edge.  Spray / isolated
specks are left out of the TRACE (largest 8-connected component; background = 4-connected
region connected to the frame border; enclosed holes are filled and reported) but never
silently: profile['components'] lists every removed component with its area and bounding
box (px and H) and separates rasterisation 'specks' from real detached 'islands'
(SPECK_AREA_PX_FULL_RES).  Non-finite vertices and the triangles dropped because of them
are counted in info['n_nonfinite_vertices'] / info['n_dropped_triangles'].  The boundary
is traced pixel-exactly along pixel cracks (wave on the right-hand side), converted to
crack mid-points (unbiased for pixel-centre sampled masks), smoothed by a small
Gaussian along the arc length (removes the staircase) and resampled uniformly.
"""
import math
import time

import numpy as np

from . import draw, frame as gw_frame, raster

__all__ = [
    "ViewRect", "mesh_world_triangles", "mask_from_triangles", "silhouette_mask", "profile_of_objects",
    "profiles_over_frames", "drop_nonfinite_triangles", "speck_area_limit_px", "SPECK_AREA_PX_FULL_RES",
    "trace_boundary", "extract_profile", "ProfileError", "setup_cam_print", "viewport_render_mismatches",
    "make_camera_for_rect", "render_mask_cycles", "compare_masks", "draw_overlay",
]


class ProfileError(RuntimeError):
    """The mask cannot yield a wave profile (e.g. nothing touches the left frame edge)."""


# ====================================================================== ViewRect
class ViewRect:
    """Framed rectangle in world units + pixel grid + optional H-normalisation.

    World: X right, Z up (metres).  Pixels: continuous coords, origin top-left, y down.
    mirror_x=True lets the image x axis run along -X (for references whose wave travels
    towards -X); normalised X_H is then also mirrored so that +X_H is always 'right in
    the image' = the boat side.

    Normalised ('H') coordinates:  X_H = +-(X - x0) / H ,  Z_H = (Z - z0) / H
    For CAM_print: x0 = 0, z0 = 0, H = WAVE_HEIGHT_M.
    """

    def __init__(self, x_min, x_max, z_min, z_max, width_px, height_px, mirror_x=False,
                 H=1.0, x0=0.0, z0=0.0, is_cam_print=False, name="rect"):
        if not (x_max > x_min and z_max > z_min):
            raise ValueError("empty rectangle")
        self.x_min, self.x_max = float(x_min), float(x_max)
        self.z_min, self.z_max = float(z_min), float(z_max)
        self.width_px, self.height_px = int(width_px), int(height_px)
        self.mirror_x = bool(mirror_x)
        self.H, self.x0, self.z0 = float(H), float(x0), float(z0)
        self.is_cam_print = bool(is_cam_print)
        self.name = str(name)
        self.px_per_unit_x = self.width_px / (self.x_max - self.x_min)
        self.px_per_unit_z = self.height_px / (self.z_max - self.z_min)

    # ---- constructors
    @classmethod
    def from_cam_print(cls, H=None, scale=1.0, frame_obj=None):
        """CAM_print framing (spec section 4) for wave height H [m] (default: params.json).
        scale < 1 gives a proportionally smaller pixel grid.  The z-range is the one the
        real Blender camera covers at that resolution (identical to Frame.cam_print)."""
        F = frame_obj or (gw_frame.Frame.from_params(wave_height_m=H) if H is not None else gw_frame.get_frame())
        res_x = int(round(F.width_px * float(scale)))
        spec = F.cam_print(res_x=res_x)
        x0, x1 = spec["x_range_m"]
        z0, z1 = spec["z_range_covered_m"]
        r = cls(x0, x1, z0, z1, spec["resolution_x"], spec["resolution_y"], False, F.H, 0.0, 0.0,
                True, "CAM_print x%.4g" % scale)
        r.frame = F
        return r

    @classmethod
    def from_bounds(cls, x_min, x_max, z_min, z_max, width_px=None, px_per_unit=None,
                    mirror_x=False, H=1.0, x0=0.0, z0=0.0, name="custom"):
        """Arbitrary rectangle.  Give width_px or px_per_unit.  Pixels are made exactly
        square by extending z_min downwards to a whole number of rows."""
        if width_px is None:
            if px_per_unit is None:
                raise ValueError("give width_px or px_per_unit")
            width_px = int(math.ceil((x_max - x_min) * px_per_unit))
        upp = (x_max - x_min) / float(width_px)          # units per px
        height_px = int(math.ceil((z_max - z_min) / upp - 1e-9))
        return cls(x_min, x_max, z_max - height_px * upp, z_max, width_px, height_px,
                   mirror_x, H, x0, z0, False, name)

    def scaled(self, scale):
        """Same rectangle on a pixel grid scaled by `scale` (rounded to whole pixels)."""
        if self.is_cam_print:
            return ViewRect.from_cam_print(scale=scale * self.width_px / float(self.frame.width_px),
                                           frame_obj=self.frame)
        return ViewRect.from_bounds(self.x_min, self.x_max, self.z_min, self.z_max,
                                    width_px=int(round(self.width_px * scale)), mirror_x=self.mirror_x,
                                    H=self.H, x0=self.x0, z0=self.z0, name=self.name)

    # ---- conversions (scalars or arrays)
    def world_to_px(self, X, Z):
        X = np.asarray(X, dtype=np.float64)
        Z = np.asarray(Z, dtype=np.float64)
        if self.mirror_x:
            x = (self.x_max - X) * self.px_per_unit_x
        else:
            x = (X - self.x_min) * self.px_per_unit_x
        y = (self.z_max - Z) * self.px_per_unit_z
        return x, y

    def px_to_world(self, x, y):
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        X = (self.x_max - x / self.px_per_unit_x) if self.mirror_x else (self.x_min + x / self.px_per_unit_x)
        Z = self.z_max - y / self.px_per_unit_z
        return X, Z

    def world_to_H(self, X, Z):
        s = -1.0 if self.mirror_x else 1.0
        return s * (np.asarray(X, dtype=np.float64) - self.x0) / self.H, (np.asarray(Z, dtype=np.float64) - self.z0) / self.H

    def H_to_world(self, XH, ZH):
        s = -1.0 if self.mirror_x else 1.0
        return self.x0 + s * np.asarray(XH, dtype=np.float64) * self.H, self.z0 + np.asarray(ZH, dtype=np.float64) * self.H

    def px_to_H(self, x, y):
        return self.world_to_H(*self.px_to_world(x, y))

    def H_to_px(self, XH, ZH):
        return self.world_to_px(*self.H_to_world(XH, ZH))

    def pts_px_to_H(self, pts):
        pts = np.asarray(pts, dtype=np.float64)
        X, Z = self.px_to_H(pts[..., 0], pts[..., 1])
        return np.stack([X, Z], axis=-1)

    def pts_H_to_px(self, pts):
        pts = np.asarray(pts, dtype=np.float64)
        x, y = self.H_to_px(pts[..., 0], pts[..., 1])
        return np.stack([x, y], axis=-1)

    def to_painting_px(self, pts_px):
        """Mask px -> painting px (only meaningful for CAM_print rects)."""
        if not self.is_cam_print:
            raise ValueError("not a CAM_print rectangle")
        return self.frame.pts_H_to_px(self.pts_px_to_H(pts_px))

    def summary(self):
        return {"name": self.name, "x_min": self.x_min, "x_max": self.x_max, "z_min": self.z_min,
                "z_max": self.z_max, "width_px": self.width_px, "height_px": self.height_px,
                "mirror_x": self.mirror_x, "H": self.H, "x0": self.x0, "z0": self.z0,
                "is_cam_print": self.is_cam_print, "px_per_unit": self.px_per_unit_x}


# ====================================================================== viewport vs render state
def viewport_render_mismatches(objs):
    """Differences between what the VIEWPORT depsgraph evaluates (= what this module and the tests measure) and what a
    render / a RENDER-mode Alembic export evaluates, for the given objects.  Checked per object:
      * a modifier whose show_viewport differs from show_render (geometry that exists only in one of the two states)
      * a modifier with both `levels` and `render_levels` (Subdivision Surface, Multires) whose two values differ
      * hide_viewport differing from hide_render on the object itself
    -> list of {'object', 'modifier' (None for the object flags), 'type', 'what', 'viewport', 'render'}; [] = the two
    states evaluate the same modifier stack.  NOT detectable here (documented limit): node groups that switch on the
    'Is Viewport' input, drivers / handlers that read the evaluation mode, simplify settings of the scene."""
    if not isinstance(objs, (list, tuple)):
        objs = [objs]
    out = []
    for obj in objs:
        if bool(getattr(obj, "hide_viewport", False)) != bool(getattr(obj, "hide_render", False)):
            out.append({"object": obj.name, "modifier": None, "type": "OBJECT", "what": "hide_viewport != hide_render",
                        "viewport": bool(obj.hide_viewport), "render": bool(obj.hide_render)})
        for md in getattr(obj, "modifiers", []):
            if bool(md.show_viewport) != bool(md.show_render):
                out.append({"object": obj.name, "modifier": md.name, "type": md.type, "what": "show_viewport != show_render",
                            "viewport": bool(md.show_viewport), "render": bool(md.show_render)})
            if hasattr(md, "levels") and hasattr(md, "render_levels") and int(md.levels) != int(md.render_levels) \
                    and (md.show_viewport or md.show_render):
                out.append({"object": obj.name, "modifier": md.name, "type": md.type, "what": "levels != render_levels",
                            "viewport": int(md.levels), "render": int(md.render_levels)})
    return out


# ====================================================================== mesh -> triangles
def mesh_world_triangles(objs, depsgraph=None, y_range=None):
    """Evaluated world-space triangles of Blender mesh objects.

    objs      : object or list of objects (anything that evaluates to a mesh).
    depsgraph : default bpy.context.evaluated_depsgraph_get() (call scene.frame_set first).  This is the VIEWPORT
                evaluation (show_viewport / viewport subdivision levels); see viewport_render_mismatches().
    y_range   : optional (y_min, y_max) in world units; only triangles whose three
                vertices lie inside are kept (e.g. to cut tank walls off a reference).
    -> (verts (N, 3) float64 world coords, tris (M, 3) int64 indices into verts, info)

    NON-FINITE GEOMETRY IS NEVER DROPPED SILENTLY.  A vertex with a NaN / inf world coordinate
    (e.g. a generator bug 0 / 0 in one shape key) cannot be projected; every triangle that uses
    such a vertex is removed from `tris` HERE (before the y_range filter, which would otherwise
    swallow it without a trace) and counted:
      info['n_nonfinite_vertices']      vertices with at least one non-finite world coordinate
      info['n_dropped_triangles']       triangles removed because they use such a vertex
      info['nonfinite_vertex_indices']  the first 20 of them (index into `verts`)
      info['objects'][k]                the same two counts per object
    `verts` keeps its length and order (the bad rows stay non-finite), so vertex indices remain
    valid.  A mask made without these triangles can look perfectly fine (the neighbouring rows of
    a swept sheet cover the gap): callers MUST look at the two counts.
    """
    import bpy
    if not isinstance(objs, (list, tuple)):
        objs = [objs]
    depsgraph = depsgraph or bpy.context.evaluated_depsgraph_get()
    all_v, all_t, base = [], [], 0
    info = {"objects": [], "n_vertices": 0, "n_triangles": 0, "n_nonfinite_vertices": 0, "n_dropped_triangles": 0,
            "nonfinite_vertex_indices": []}
    for obj in objs:
        ev = obj.evaluated_get(depsgraph)
        me = ev.to_mesh()
        try:
            n = len(me.vertices)
            co = np.empty(n * 3, np.float32)
            me.vertices.foreach_get("co", co)
            me.calc_loop_triangles()
            nt = len(me.loop_triangles)
            tri = np.empty(nt * 3, np.int32)
            me.loop_triangles.foreach_get("vertices", tri)
        finally:
            ev.to_mesh_clear()
        M = np.array(ev.matrix_world, dtype=np.float64)
        v = co.reshape(n, 3).astype(np.float64)
        with np.errstate(invalid="ignore", over="ignore"):
            v = v @ M[:3, :3].T + M[:3, 3]
        t_obj = tri.reshape(nt, 3).astype(np.int64)
        bad_v_obj = ~np.isfinite(v).all(axis=1)
        n_bad_t_obj = int(bad_v_obj[t_obj].any(axis=1).sum()) if (nt and bad_v_obj.any()) else 0
        all_v.append(v)
        all_t.append(t_obj + base)
        base += n
        info["objects"].append({"name": obj.name, "n_vertices": n, "n_triangles": nt,
                                "n_nonfinite_vertices": int(bad_v_obj.sum()), "n_dropped_triangles": n_bad_t_obj})
    verts = np.concatenate(all_v) if all_v else np.zeros((0, 3))
    tris = np.concatenate(all_t) if all_t else np.zeros((0, 3), np.int64)
    tris, nf = drop_nonfinite_triangles(verts, tris)
    info.update(nf)
    if y_range is not None and tris.size:
        yy = verts[:, 1][tris]
        keep = (yy >= y_range[0]).all(axis=1) & (yy <= y_range[1]).all(axis=1)
        tris = tris[keep]
    info["n_vertices"] = int(verts.shape[0])
    info["n_triangles"] = int(tris.shape[0])
    return verts, tris, info


def drop_nonfinite_triangles(verts, tris):
    """Remove the triangles that use a vertex with a non-finite coordinate (X, Y or Z) and COUNT them.
    -> (tris without them, {'n_nonfinite_vertices', 'n_dropped_triangles', 'nonfinite_vertex_indices' (first 20)})
    n_nonfinite_vertices counts ALL rows of `verts` with a non-finite value, referenced by a triangle or not."""
    verts = np.asarray(verts, dtype=np.float64)
    tris = np.asarray(tris, dtype=np.int64)
    bad_v = ~np.isfinite(verts).all(axis=1) if verts.size else np.zeros(verts.shape[0], bool)
    out = {"n_nonfinite_vertices": int(bad_v.sum()), "n_dropped_triangles": 0,
           "nonfinite_vertex_indices": [int(i) for i in np.nonzero(bad_v)[0][:20]]}
    if bad_v.any() and tris.size:
        bad_t = bad_v[tris].any(axis=1)
        out["n_dropped_triangles"] = int(bad_t.sum())
        tris = tris[~bad_t]
    return tris, out


def mask_from_triangles(verts_world, tris, rect, water_z=0.0, thin="skip", thin_px=1.0, exact=True):
    """Pure numpy: world triangles -> silhouette mask on `rect` (projection along Y).

    water_z : world Z of the top of the 'water slab'; everything at or below it inside
              the frame is filled (None = no slab).
    exact   : True -> also record the exact sub-pixel boundary crossings (info['edges'], a
              raster.EdgeData) so that extract_profile(mask, rect, edges=info['edges']) returns
              boundary points with float precision instead of +-0.5 px.  About twice the time
              and 4 float32 images of memory; False = mask only.
    -> (bool mask (rect.height_px, rect.width_px), info)

    Non-finite geometry (never silent): triangles that use a vertex with a NaN / inf coordinate are
    removed before rasterising and counted in info['n_nonfinite_vertices'] (all such rows of
    `verts_world`) and info['n_dropped_triangles'] (see drop_nonfinite_triangles).  The rasteriser's own
    info['n_nonfinite'] (triangles that are non-finite in PIXEL coordinates) stays as a second net.
    """
    verts_world = np.asarray(verts_world, dtype=np.float64)
    tris = np.asarray(tris, dtype=np.int64)
    t0 = time.perf_counter()
    tris, nf_info = drop_nonfinite_triangles(verts_world, tris)
    with np.errstate(invalid="ignore"):
        x, y = rect.world_to_px(verts_world[:, 0], verts_world[:, 2])
    tri_px = np.stack([x[tris], y[tris]], axis=-1)
    w, h = rect.width_px, rect.height_px
    y_w = None
    if water_z is not None:
        y_w = float(rect.world_to_px(0.0, float(water_z))[1])
    if exact:
        mesh_area = None
        if y_w is not None and y_w < h:
            yb = max(h + 2.0, y_w + 2.0)
            slab = np.array([[[-2.0, y_w], [w + 2.0, y_w], [w + 2.0, yb]],
                             [[-2.0, y_w], [w + 2.0, yb], [-2.0, yb]]])
            tri_px = np.concatenate([tri_px, slab], axis=0)
        mask, edges, info = raster.rasterize_exact(tri_px, w, h, thin=thin, thin_px=thin_px)
        info["edges"] = edges
        if y_w is not None:
            j = int(np.clip(np.ceil(y_w - 0.5 - 1e-9), 0, h))
            mesh_area = int(mask[:j].sum())
        info["mesh_area_px"] = int(mask.sum()) if mesh_area is None else mesh_area
        info["mesh_area_note"] = "pixels above the water slab" if y_w is not None else "all pixels"
    else:
        mask, info = raster.rasterize_triangles(tri_px, w, h, thin=thin, thin_px=thin_px, return_info=True)
        info["mesh_area_px"] = int(mask.sum())
        info["mesh_area_note"] = "mesh pixels before the water slab was added"
        info["edges"] = None
        if y_w is not None:
            raster.fill_below(mask, y_w)
    info["water_z"] = None if water_z is None else float(water_z)
    info["water_y_px"] = y_w
    info.update(nf_info)
    info["n_mesh_triangles_rasterized"] = int(tris.shape[0])
    info["seconds_rasterize"] = time.perf_counter() - t0
    return mask, info


def silhouette_mask(objs, rect=None, H=None, scale=1.0, water_z=0.0, thin="skip", thin_px=1.0,
                    y_range=None, depsgraph=None, exact=True):
    """Silhouette of evaluated Blender mesh objects as seen by CAM_print (or `rect`).

    rect    : ViewRect (default: ViewRect.from_cam_print(H, scale)).
    H       : wave height in m for the default rect (default params.json WAVE_HEIGHT_M).
    scale   : resolution factor for the default rect (1.0 -> 3859 x 2594).
    water_z : top of the water slab in world units (default 0 = still-water plane; None = off).
    exact   : see mask_from_triangles.
    -> (bool mask, info dict);  info['edges'] is passed on to extract_profile.
       info['n_nonfinite_vertices'] / info['n_dropped_triangles']: non-finite vertices of the evaluated
       meshes and the triangles that were left out of the mask because of them (0 / 0 for a healthy mesh;
       the per-object numbers are in info['mesh']['objects']).
    """
    if rect is None:
        rect = ViewRect.from_cam_print(H=H, scale=scale)
    t0 = time.perf_counter()
    verts, tris, minfo = mesh_world_triangles(objs, depsgraph, y_range)
    t1 = time.perf_counter()
    mask, info = mask_from_triangles(verts, tris, rect, water_z, thin, thin_px, exact)
    # mesh_world_triangles has already removed (and counted) the triangles with non-finite vertices, so
    # mask_from_triangles sees the same bad vertices but no bad triangle: report the sum / the larger count
    info["n_dropped_triangles"] = int(info["n_dropped_triangles"] + minfo["n_dropped_triangles"])
    info["n_nonfinite_vertices"] = int(max(info["n_nonfinite_vertices"], minfo["n_nonfinite_vertices"]))
    info.update({"mesh": minfo, "seconds_get_mesh": t1 - t0, "rect": rect.summary()})
    return mask, info


def profile_of_objects(objs, rect=None, H=None, scale=1.0, water_z=0.0, exact=True, y_range=None,
                       depsgraph=None, keep_mask=False):
    """One call: silhouette_mask + extract_profile for the CURRENT frame of the scene.
    -> (profile dict, mask, info).  The EdgeData is dropped from info to free memory."""
    if rect is None:
        rect = ViewRect.from_cam_print(H=H, scale=scale)
    mask, info = silhouette_mask(objs, rect=rect, water_z=water_z, y_range=y_range,
                                 depsgraph=depsgraph, exact=exact)
    prof = extract_profile(mask, rect, edges=info.get("edges"), keep_mask=keep_mask)
    info["edges"] = None
    return prof, mask, info


def profiles_over_frames(objs, frames, scene=None, rect=None, H=None, scale=0.5, water_z=0.0, exact=True,
                         y_range=None, on_frame=None):
    """Profile of every frame in `frames` (scene.frame_set is called for each one).

    With exact=True the accuracy does not depend on the resolution, so scale 0.25 .. 0.5 is
    enough for motion curves (spec 6.2).  on_frame(frame, profile, mask, info) is an optional
    hook (e.g. to save overlays); masks are not kept.
    -> list of dicts {frame, H (N, 2) ordered profile, complete, holes, components, n_nonfinite_vertices,
       n_dropped_triangles, seconds} ready for gw.profile_metrics.measure_sequence([p['H'] for p in result]).
    """
    import bpy
    scene = scene or bpy.context.scene
    if rect is None:
        rect = ViewRect.from_cam_print(H=H, scale=scale)
    out = []
    for fr in frames:
        t0 = time.perf_counter()
        scene.frame_set(int(fr))
        prof, mask, info = profile_of_objects(objs, rect=rect, water_z=water_z, exact=exact, y_range=y_range)
        if on_frame is not None:
            on_frame(int(fr), prof, mask, info)
        out.append({"frame": int(fr), "H": prof["H"], "px": prof["px"], "complete": prof["complete"],
                    "end_border": prof["end_border"], "holes": prof["holes"], "components": prof["components"],
                    "n_nonfinite_vertices": info.get("n_nonfinite_vertices"),
                    "n_dropped_triangles": info.get("n_dropped_triangles"),
                    "n_cracks_without_exact_data": prof["n_cracks_without_exact_data"],
                    "seconds": time.perf_counter() - t0})
    return out


# ====================================================================== boundary tracing
_DX = (1, 0, -1, 0)      # d: 0 right, 1 down, 2 left, 3 up   (image coords, y down)
_DY = (0, 1, 0, -1)
_AL = ((0, -1), (0, 0), (-1, 0), (-1, -1))     # ahead-left pixel offset from the vertex
_AR = ((0, 0), (-1, 0), (-1, -1), (0, -1))     # ahead-right pixel offset


def trace_boundary(wave, start_row=None, max_steps=None):
    """Crack-following boundary trace of a bool mask `wave`.

    Starts on the LEFT frame edge at the top of the top-most wave pixel of column 0 and
    walks along pixel cracks with the wave on the right-hand side (wave 8-connected,
    background 4-connected) until it reaches a frame border again.
    -> (vertices (n, 2) int64 crack corners (x, y), end_border 'right'|'top'|'bottom'|'left')
    """
    W = np.ascontiguousarray(wave, dtype=bool)
    h, w = W.shape
    col0 = W[:, 0]
    if start_row is None:
        if not col0.any():
            raise ProfileError("the mask does not touch the left frame edge (no water slab and the "
                               "mesh does not reach the frame border?)")
        j0 = int(np.argmax(col0))
    else:
        j0 = int(start_row)
    if j0 <= 0:
        return np.array([[0, 0]], np.int64), "top"
    rows = [r.tobytes() for r in W.view(np.uint8)]
    if max_steps is None:
        max_steps = 8 * (w + h) + 4 * int(W.sum() ** 0.5) * 200 + 2_000_000

    def is_w(i, j):
        return 0 <= i < w and 0 <= j < h and rows[j][i] != 0

    vx, vy, d = 0, j0, 0
    path = [(vx, vy)]
    steps = 0
    while True:
        al = _AL[d]
        ar = _AR[d]
        if is_w(vx + al[0], vy + al[1]):
            d = (d + 3) % 4
        elif is_w(vx + ar[0], vy + ar[1]):
            pass
        else:
            d = (d + 1) % 4
        vx += _DX[d]
        vy += _DY[d]
        path.append((vx, vy))
        steps += 1
        if vx <= 0 or vx >= w or vy <= 0 or vy >= h:
            break
        if steps > max_steps:
            raise ProfileError("boundary trace did not terminate (%d steps)" % steps)
    end = "right" if vx >= w else ("top" if vy <= 0 else ("bottom" if vy >= h else "left"))
    return np.asarray(path, dtype=np.int64), end


def _resample_polyline(pts, spacing):
    """Uniform arc-length resampling; first and last point are kept."""
    seg = np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1]))
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = s[-1]
    if total <= 0:
        return pts[:1].copy()
    n = max(2, int(round(total / float(spacing))) + 1)
    si = np.linspace(0.0, total, n)
    return np.stack([np.interp(si, s, pts[:, 0]), np.interp(si, s, pts[:, 1])], axis=1)


def _gauss_smooth_open(pts, sigma):
    """Gaussian smoothing of an open polyline (uniformly sampled); end points stay fixed
    (odd reflection), straight lines stay straight."""
    n = pts.shape[0]
    if sigma <= 0 or n < 5:
        return pts.copy()
    r = int(min(math.ceil(4.0 * sigma), n - 1))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / float(sigma)) ** 2)
    k /= k.sum()
    out = np.empty_like(pts)
    for c in range(2):
        v = pts[:, c]
        left = 2.0 * v[0] - v[r:0:-1]
        right = 2.0 * v[-1] - v[-2:-r - 2:-1]
        out[:, c] = np.convolve(np.concatenate([left, v, right]), k, mode="valid")
    out[0] = pts[0]
    out[-1] = pts[-1]
    return out


def _exact_crossings(verts, edges):
    """Replace every crack of the trace by the exact boundary crossing on the line joining the
    two pixel centres it separates.  -> (points (n, 2), number of cracks without exact data)"""
    V = verts
    d = np.diff(V, axis=0)
    n = d.shape[0]
    vx, vy = V[:-1, 0], V[:-1, 1]
    down, up = d[:, 1] == 1, d[:, 1] == -1
    right, left = d[:, 0] == 1, d[:, 0] == -1
    # inside pixel (row j, column i) and crack coordinate for each move (wave on the right-hand side)
    j = np.where(down, vy, np.where(up, vy - 1, np.where(right, vy, vy - 1)))
    i = np.where(down, vx - 1, np.where(up, vx, np.where(right, vx, vx - 1)))
    base = np.where(down | up, vx, vy).astype(np.float64)
    h, w = edges.shape
    ok_idx = (j >= 0) & (j < h) & (i >= 0) & (i < w)
    jc, ic = np.clip(j, 0, h - 1), np.clip(i, 0, w - 1)
    c = np.where(down, edges.x_hi[jc, ic], np.where(up, edges.x_lo[jc, ic],
                 np.where(right, edges.y_lo[jc, ic], edges.y_hi[jc, ic]))).astype(np.float64)
    # slivers: only cracks whose gap holds any
    kr, kc = edges._sl_row[0], edges._sl_col[0]
    key = np.where(down, j * (w + 2) + (i + 1), np.where(up, j * (w + 2) + i,
                   np.where(right, i * (h + 2) + j, i * (h + 2) + (j + 1))))
    has = np.zeros(n, bool)
    if kr.size:
        m = down | up
        has[m] = np.searchsorted(kr, key[m], "right") > np.searchsorted(kr, key[m], "left")
    if kc.size:
        m = right | left
        has[m] = np.searchsorted(kc, key[m], "right") > np.searchsorted(kc, key[m], "left")
    for k in np.nonzero(has & ok_idx & np.isfinite(c))[0]:
        kind = "right" if down[k] else ("left" if up[k] else ("top" if right[k] else "bottom"))
        c[k] = edges.crossing(kind, int(j[k]), int(i[k]))
    bad = ~ok_idx | ~np.isfinite(c) | (np.abs(c - base) > 0.5 + 1e-3)
    c = np.where(bad, base, c)
    px = np.where(down | up, c, i + 0.5)
    py = np.where(down | up, j + 0.5, c)
    return np.stack([px, py], axis=1), int(bad.sum())


SPECK_AREA_PX_FULL_RES = 25.0
"""Removed (detached) mask components SMALLER than this area are called 'specks', the others 'islands'.
The number is an area in pixels AT THE FULL PAINTING RESOLUTION (3859 x 2594; 25 px = a 5 x 5 px blob =
0.19 x 0.19 % of image height = 8.5e-6 H^2) and is scaled with the square of the linear resolution of the
mask (speck_area_limit_px), so the same piece of geometry is classified the same way at every resolution.
Foundation default, not from the spec: rasterisation dust along slivers is 1 .. a few px; anything of
5 x 5 px or more is geometry somebody modelled."""


def speck_area_limit_px(rect, speck_area_px_full_res=None):
    """Area limit in MASK pixels of `rect` that corresponds to SPECK_AREA_PX_FULL_RES at the full painting
    resolution: limit = full_res_limit * (px per H of the rect / px per H of the painting) ** 2."""
    full = SPECK_AREA_PX_FULL_RES if speck_area_px_full_res is None else float(speck_area_px_full_res)
    F = getattr(rect, "frame", None) or gw_frame.get_frame()
    lin = (rect.px_per_unit_z * rect.H) / F.px_per_H
    return float(full * lin * lin)


def _bbox_px_to_H(rect, bbox_px):
    """[x0, y0, x1, y1) pixel box (exclusive) -> [X_min, Z_min, X_max, Z_max] in H units."""
    x0, y0, x1, y1 = (float(v) for v in bbox_px)
    Xa, Za = rect.px_to_H(x0, y1)
    Xb, Zb = rect.px_to_H(x1, y0)
    return [float(min(Xa, Xb)), float(min(Za, Zb)), float(max(Xa, Xb)), float(max(Za, Zb))]


def extract_profile(mask, rect, edges=None, smooth_sigma_px=None, spacing_px=None, keep_mask=False,
                    speck_area_px_full_res=None):
    """Ordered wave profile from a silhouette mask.

    mask  : bool (rect.height_px, rect.width_px); wave + water slab = True.
    rect  : the ViewRect the mask was rasterised on.
    edges : raster.EdgeData from silhouette_mask(..., exact=True) (info['edges']).  With it
            every boundary point is the EXACT crossing of the silhouette with a grid line
            through the pixel centres (float precision, no smoothing needed).  Without it the
            points are crack mid-points (+-0.5 px) smoothed by a Gaussian.
    smooth_sigma_px : Gaussian sigma (mask px, along the arc length); default 0 with edges,
            2.0 without (removes the pixel staircase; inward shift on a convex arc of radius R
            is about sigma^2 / (2 R) px).
    spacing_px : output sample spacing in mask px (default 1.0 with edges, 2.0 without).
    speck_area_px_full_res : see SPECK_AREA_PX_FULL_RES (default 25 px at the full painting resolution).

    DETACHED COMPONENTS.  Only the largest 8-connected component of the mask is traced; everything else is
    removed and reported in profile['components'] (never silently):
       removed_area_px, n_removed                 total area / number of removed components
       n_removed_specks, removed_specks_area_px   removed components smaller than speck_max_area_px
       n_removed_islands, removed_islands_area_px the others = REAL detached geometry (a second object, spray, a
                                                  piece of the mesh that floats free as seen by the camera)
       speck_max_area_px, speck_area_px_full_res  the limit in mask px at this resolution / at full resolution
       removed  [ {area_px, kind 'speck' | 'island', bbox_px [x0, y0, x1, y1) mask px (exclusive),
                   bbox_H [X_min, Z_min, X_max, Z_max], centre_H [X, Z]} ]   the 20 largest, largest first
    The profile does NOT contain the removed components: an island inside the cavity does not change a
    single metric, so a caller that wants to judge a shape has to look at n_removed_islands.

    -> dict:
       px        (N, 2) mask px (continuous, y down), ordered left frame edge -> crest ->
                 head tip -> inner arc -> trough -> right frame edge
       world     (N, 2) world (X, Z);  H  (N, 2) normalised (X_H, Z_H)
       painting_px (N, 2) only for CAM_print rects
       raw_px    (M, 2) un-smoothed boundary points (exact crossings or crack mid-points)
       exact, n_cracks_without_exact_data
       complete  True when the trace ended on the right frame edge
       end_border, n_trace_steps, components {..}, holes {..}, seconds
    """
    t0 = time.perf_counter()
    m = np.asarray(mask, dtype=bool)
    if m.shape != (rect.height_px, rect.width_px):
        raise ValueError("mask shape %r does not match the rect %r" % (m.shape, (rect.height_px, rect.width_px)))
    exact = edges is not None
    if smooth_sigma_px is None:
        smooth_sigma_px = 0.0 if exact else 2.0
    if spacing_px is None:
        spacing_px = 1.0 if exact else 2.0
    speck_lim = speck_area_limit_px(rect, speck_area_px_full_res)
    wave, cinfo = raster.largest_component(m, connectivity=8, speck_max_area_px=speck_lim)
    cinfo["speck_area_px_full_res"] = float(SPECK_AREA_PX_FULL_RES if speck_area_px_full_res is None else speck_area_px_full_res)
    for rc in cinfo["removed"]:
        rc["bbox_H"] = _bbox_px_to_H(rect, rc["bbox_px"])
        rc["centre_H"] = [0.5 * (rc["bbox_H"][0] + rc["bbox_H"][2]), 0.5 * (rc["bbox_H"][1] + rc["bbox_H"][3])]
    wave, holes_mask, hinfo = raster.fill_holes(wave, sky="top")
    tot = int(wave.sum())
    hinfo["filled_area_px"] = tot
    hinfo["hole_area_frac"] = float(hinfo["hole_area_px"]) / tot if tot else 0.0
    verts, end_border = trace_boundary(wave)
    v = verts.astype(np.float64)
    n_bad = None
    if v.shape[0] >= 2:
        if exact:
            mids, n_bad = _exact_crossings(verts, edges)
            first = np.array([[v[0, 0], mids[0, 1]]])
            last = np.array([[v[-1, 0], mids[-1, 1]]]) if end_border in ("right", "left") else v[-1:]
        else:
            mids = 0.5 * (v[:-1] + v[1:])
            first, last = v[:1], v[-1:]
        raw = np.concatenate([first, mids, last], axis=0)
    else:
        raw = v
    if raw.shape[0] >= 3:
        uni = _resample_polyline(raw, min(1.0, float(spacing_px)))
        sm = _gauss_smooth_open(uni, float(smooth_sigma_px))
        pts = _resample_polyline(sm, float(spacing_px))
    else:
        pts = raw.copy()
    X, Z = rect.px_to_world(pts[:, 0], pts[:, 1])
    out = {
        "px": pts,
        "world": np.stack([X, Z], axis=1),
        "H": rect.pts_px_to_H(pts),
        "raw_px": raw,
        "exact": bool(exact),
        "n_cracks_without_exact_data": n_bad,
        "complete": end_border == "right",
        "end_border": end_border,
        "n_trace_steps": int(verts.shape[0] - 1),
        "components": cinfo,
        "holes": hinfo,
        "smooth_sigma_px": float(smooth_sigma_px),
        "spacing_px": float(spacing_px),
        "rect": rect.summary(),
    }
    if rect.is_cam_print:
        out["painting_px"] = rect.to_painting_px(pts)
    if keep_mask:
        out["wave_mask"] = wave
        out["holes_mask"] = holes_mask
    out["seconds"] = time.perf_counter() - t0
    return out


# ====================================================================== Blender camera / Cycles cross-check
def setup_cam_print(scene=None, H=None, scale=1.0, name="CAM_print"):
    """Create (or update) the real Blender judging camera CAM_print for wave height H [m]
    (default params.json) and set the render resolution (3859 x 2594 times `scale`).
    Delegates to gw.frame.Frame.make_cam_print (single implementation) and cross-checks
    the framing numerically.  -> (camera object, ViewRect, check dict)"""
    import bpy
    scene = scene or bpy.context.scene
    F = gw_frame.Frame.from_params(wave_height_m=H) if H is not None else gw_frame.get_frame()
    rect = ViewRect.from_cam_print(scale=scale, frame_obj=F)
    cam = F.make_cam_print(scene, res_x=rect.width_px, name=name)
    check = _check_camera_matches_rect(scene, cam, rect)
    return cam, rect, check


def make_camera_for_rect(scene, rect, name="CAM_rect", distance=200.0, clip=(0.1, 2000.0)):
    """Orthographic camera looking along +Y that frames `rect` exactly (any ViewRect that is
    not mirrored).  Sets the render resolution of `scene`."""
    import bpy
    if rect.mirror_x:
        raise ValueError("a mirrored rect cannot be represented by a camera looking along +Y")
    cam_data = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cam_data.type = "ORTHO"
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.ortho_scale = rect.x_max - rect.x_min
    cam_data.shift_x = cam_data.shift_y = 0.0
    cam_data.clip_start, cam_data.clip_end = clip
    obj = bpy.data.objects.get(name) or bpy.data.objects.new(name, cam_data)
    obj.data = cam_data
    if obj.name not in scene.collection.all_objects:
        scene.collection.objects.link(obj)
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
    obj.location = (0.5 * (rect.x_min + rect.x_max), -float(distance), 0.5 * (rect.z_min + rect.z_max))
    scene.render.resolution_x = rect.width_px
    scene.render.resolution_y = rect.height_px
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1.0
    scene.camera = obj
    return obj


def _check_camera_matches_rect(scene, cam, rect):
    """Project the rect corners with bpy_extras.world_to_camera_view and compare with the
    pixel grid.  -> {'max_err_px': ..}"""
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    import bpy
    bpy.context.view_layer.update()
    errs = []
    for X, Z in ((rect.x_min, rect.z_min), (rect.x_max, rect.z_max), (rect.x_min, rect.z_max), (0.0, 0.0)):
        ndc = world_to_camera_view(scene, cam, Vector((X, 0.0, Z)))
        x_cam = ndc.x * rect.width_px
        y_cam = (1.0 - ndc.y) * rect.height_px
        x_r, y_r = rect.world_to_px(X, Z)
        errs.append(max(abs(x_cam - float(x_r)), abs(y_cam - float(y_r))))
    return {"max_err_px": float(max(errs))}


def render_mask_cycles(objs, rect, out_png, water_z=0.0, scene=None, samples=1, keep_setup=False):
    """Cross-check render: Cycles CPU, `samples` sample(s), white emission override on a black
    world, Standard view transform, no dither, tiny Blackman-Harris pixel filter (samples sit
    on the pixel centre).  The water slab is a temporary emissive plane behind the objects.
    -> (bool mask, info).  Scene render settings are restored unless keep_setup=True."""
    import bpy
    from . import imgio, paths
    scene = scene or bpy.context.scene
    if not isinstance(objs, (list, tuple)):
        objs = [objs]
    out_png = paths.ensure_parent(out_png)
    r = scene.render
    saved = {"engine": r.engine, "filepath": r.filepath, "res": (r.resolution_x, r.resolution_y, r.resolution_percentage),
             "camera": scene.camera, "film_transparent": r.film_transparent, "dither": r.dither_intensity,
             "view_transform": scene.view_settings.view_transform, "look": scene.view_settings.look,
             "world": scene.world, "fmt": (r.image_settings.file_format, r.image_settings.color_mode,
                                           r.image_settings.color_depth)}
    vl = bpy.context.view_layer
    saved_override = vl.material_override
    t0 = time.perf_counter()
    cam = make_camera_for_rect(scene, rect, name="CAM_maskcheck")
    r.engine = "CYCLES"
    cy = scene.cycles
    cy.device = "CPU"
    cy.samples = int(samples)
    cy.use_adaptive_sampling = False
    cy.use_denoising = False
    cy.pixel_filter_type = "BLACKMAN_HARRIS"
    cy.filter_width = 0.01
    cy.max_bounces = 0
    r.film_transparent = False
    r.dither_intensity = 0.0
    r.use_border = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "BW"
    r.image_settings.color_depth = "8"
    r.image_settings.compression = 15
    r.filepath = out_png
    # black world
    world = bpy.data.worlds.new("W_maskcheck")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg is not None:
        bg.inputs[0].default_value = (0, 0, 0, 1)
        bg.inputs[1].default_value = 0.0
    scene.world = world
    # white emission override
    mat = bpy.data.materials.new("M_maskcheck")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[0].default_value = (1, 1, 1, 1)
    em.inputs[1].default_value = 1.0
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], outn.inputs[0])
    vl.material_override = mat
    slab = None
    if water_z is not None:
        y_far = 900.0
        me = bpy.data.meshes.new("slab_maskcheck")
        x0, x1 = rect.x_min - 1.0, rect.x_max + 1.0
        z0, z1 = rect.z_min - 1.0, float(water_z)
        me.from_pydata([(x0, y_far, z0), (x1, y_far, z0), (x1, y_far, z1), (x0, y_far, z1)], [], [(0, 1, 2, 3)])
        slab = bpy.data.objects.new("slab_maskcheck", me)
        scene.collection.objects.link(slab)
    hidden = []
    for ob in scene.objects:
        if ob.type == "MESH" and ob not in objs and ob is not slab and not ob.hide_render:
            ob.hide_render = True
            hidden.append(ob)
    try:
        bpy.ops.render.render(write_still=True)
    finally:
        for ob in hidden:
            ob.hide_render = False
        vl.material_override = saved_override
        if slab is not None:
            me = slab.data
            bpy.data.objects.remove(slab)
            bpy.data.meshes.remove(me)
        if not keep_setup:
            r.engine = saved["engine"]
            r.filepath = saved["filepath"]
            r.resolution_x, r.resolution_y, r.resolution_percentage = saved["res"]
            scene.camera = saved["camera"]
            r.film_transparent = saved["film_transparent"]
            r.dither_intensity = saved["dither"]
            scene.view_settings.view_transform = saved["view_transform"]
            scene.view_settings.look = saved["look"]
            scene.world = saved["world"]
            r.image_settings.file_format, r.image_settings.color_mode, r.image_settings.color_depth = saved["fmt"]
            bpy.data.objects.remove(cam)
        bpy.data.materials.remove(mat)
        bpy.data.worlds.remove(world)
    img = imgio.load_image_rgb(out_png)
    vals = img[:, :, 0]
    mask = vals >= 128
    info = {"seconds": time.perf_counter() - t0, "n_gray_px": int(((vals > 0) & (vals < 255)).sum()),
            "path": out_png, "samples": int(samples)}
    return mask, info


def compare_masks(a, b):
    """Pixel disagreement between two bool masks + how far from the boundary of `a` the
    disagreeing pixels are.  -> dict"""
    a = np.asarray(a, dtype=bool)
    b = np.asarray(b, dtype=bool)
    if a.shape != b.shape:
        raise ValueError("mask shapes differ: %r vs %r" % (a.shape, b.shape))
    d = a != b
    n = int(d.sum())
    out = {"n_px": int(a.size), "n_disagree": n, "frac_disagree": n / float(a.size),
           "a_only": int((a & ~b).sum()), "b_only": int((b & ~a).sum())}
    # distance class: within 1 px / 2 px of a's boundary (8-neighbourhood dilation of the outline)
    if n:
        edge = draw.mask_outline(a, 1) | draw.mask_outline(~a, 1)
        near1 = edge
        p = np.pad(near1, 1)
        near2 = np.zeros_like(near1)
        for dy in (0, 1, 2):
            for dx in (0, 1, 2):
                near2 |= p[dy:dy + a.shape[0], dx:dx + a.shape[1]]
        out["n_disagree_on_boundary_px"] = int((d & near1).sum())
        out["n_disagree_within_2px"] = int((d & near2).sum())
        out["n_disagree_far"] = int((d & ~near2).sum())
        ys, xs = np.nonzero(d & ~near2)
        out["far_examples_xy"] = [[int(x), int(y)] for x, y in list(zip(xs, ys))[:10]]
    else:
        out.update({"n_disagree_on_boundary_px": 0, "n_disagree_within_2px": 0, "n_disagree_far": 0,
                    "far_examples_xy": []})
    return out


# ====================================================================== overlays
def draw_overlay(mask, profile, metrics=None, title=None, base=None, max_w=1600,
                 mask_color="blue", crop_px=None, crop_scale=None, extra_polylines=None):
    """RGB overlay image: mask (tinted) + extracted profile + landmarks.

    mask, profile : from silhouette_mask / extract_profile (same rect).
    metrics : optional result of profile_metrics.measure_profile (landmarks are drawn).
    base    : optional RGB image with the mask's pixel size to draw on (default white).
    crop_px : optional (x0, y0, x1, y1) in MASK px -> only that region, zoomed by crop_scale
              (default: so that the crop is <= max_w wide, at least 1x).
    extra_polylines : list of {'px': (N,2) mask px, 'color':.., 'width':.., 'dash':..}.
    Text is ASCII.  Returns the image (uint8 RGB)."""
    h, w = mask.shape
    img = draw.canvas(h, w, "white") if base is None else draw.to_rgb(base).copy()
    draw.overlay_mask(img, mask, mask_color, 0.35)
    rect_s = profile["rect"]
    if crop_px is None:
        x0, y0, x1, y1 = 0, 0, w, h
        scale = min(1.0, max_w / float(w))
    else:
        x0, y0, x1, y1 = crop_px
        scale = crop_scale if crop_scale is not None else max(1.0, min(8.0, max_w / float(max(1, x1 - x0))))
    view = draw.View(img, x0, y0, x1, y1, scale=scale, method="auto" if scale < 1 else "nearest")
    out = view.img
    lw = 2.0
    pts = profile["px"]
    if metrics is not None and metrics.get("segments"):
        colors = {"back": "red", "head": "orange", "inner_arc": "magenta", "trough_run": "cyan", "front": "orange"}
        segs = metrics["segments"]
        drawn = False
        for name in ("back", "head", "inner_arc", "trough_run"):
            rng = segs.get(name)
            if rng is None:
                continue
            i0, i1 = rng
            if i1 > i0:
                draw.polyline(out, view.to_view(pts[i0:i1 + 1]), colors[name], lw)
                drawn = True
        if not drawn or segs.get("head") is None:
            rng = segs.get("front")
            if rng is not None:
                draw.polyline(out, view.to_view(pts[rng[0]:rng[1] + 1]), colors["front"], lw)
    else:
        draw.polyline(out, view.to_view(pts), "red", lw)
    for ex in (extra_polylines or []):                      # drawn on top so that they stay visible
        draw.polyline(out, view.to_view(ex["px"]), ex.get("color", "green"), ex.get("width", 2.0),
                      dash=ex.get("dash"))
    if metrics is not None:
        H_to_px = lambda p: view.to_view(np.array(_rect_H_to_px(rect_s, p)))
        for key, label, col, off in (("crest", "crest", "red", (12, -12)), ("head_tip", "tip", "green", (12, -12)),
                                     ("inner_deepest", "deepest", "purple", (12, -12)),
                                     ("theta_point", "theta", "brown", (-12, 14))):
            lm = metrics["landmarks"].get(key)
            if lm is None:
                continue
            c = H_to_px(lm["H"])
            if -50 <= c[0] <= out.shape[1] + 50 and -50 <= c[1] <= out.shape[0] + 50:
                draw.label_point(out, c, label, col, scale=2, offset=off)
    if title:
        draw.text(out, 6, 6, title, "black", 2, bg="white", bg_alpha=0.85)
    return out


def _rect_H_to_px(rect_summary, pH):
    s = -1.0 if rect_summary["mirror_x"] else 1.0
    X = rect_summary["x0"] + s * pH[0] * rect_summary["H"]
    Z = rect_summary["z0"] + pH[1] * rect_summary["H"]
    if rect_summary["mirror_x"]:
        x = (rect_summary["x_max"] - X) * rect_summary["px_per_unit"]
    else:
        x = (X - rect_summary["x_min"]) * rect_summary["px_per_unit"]
    pz = rect_summary["height_px"] / (rect_summary["z_max"] - rect_summary["z_min"])
    y = (rect_summary["z_max"] - Z) * pz
    return [x, y]
