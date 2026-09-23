"""Build separate, animated foam geometry on the cached Great Wave.

Run on a generated wave scene (preferably the projected or woodblock scene)::

    tools/run_blender.ps1 src/gwave/add_animated_foam.py \
        -Blend blend/great_wave_styled.blend -NoFactoryStartup \
        -ScriptArgs '--preview'

The white crest band and the ten outlined foam claws are real meshes, not a
camera overlay. Their fixed-topology PC2 caches are derived frame by frame from
the *same* wave cache used by GreatWave. The script saves relative cache paths,
so the scene survives closing and reopening within this project directory.

The claw paths are art-directed from the print-camera painting coordinates.
This is a stylised whitewater study, not a fluid simulation or a final HMD
material. The farthest claw centre is placed at (2288, 857) in the 3859x2594
painting frame; its small ink outline extends another ~2 px.
"""

import argparse
import math
import os
import struct
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

import numpy as np

from gw import bootstrap, frame as gw_frame, paths
from gwave import profile_motion as wm


FINAL_FRAME = 285
BAND_NAME = "GW_FoamCrestBand"
CLAW_INK_NAME = "GW_FoamClawsInk"
CLAW_WHITE_NAME = "GW_FoamClawsWhite"

# root profile index, target tip in original painting px, two Bezier controls,
# radius in painting px, transverse offset along the crest line (H units).
# The first claw is the silhouette target beyond the blue body tip.
CLAWS = (
    (260, (2288, 857), (2245, 775), (2282, 824), 10.0, -0.04),
    (263, (2263, 968), (2238, 847), (2272, 918), 8.5, 0.07),
    (267, (2229, 1037), (2213, 906), (2241, 998), 8.0, -0.10),
    (272, (2172, 1103), (2177, 969), (2204, 1064), 7.5, 0.13),
    (277, (2094, 1112), (2091, 1008), (2124, 1075), 6.5, -0.16),
    (253, (2196, 760), (2170, 708), (2206, 738), 6.5, 0.16),
    (248, (2152, 697), (2112, 642), (2155, 675), 6.0, -0.21),
    (241, (2072, 618), (2038, 570), (2079, 594), 5.5, 0.24),
    (232, (1954, 514), (1926, 471), (1961, 497), 5.0, -0.27),
    (221, (1824, 402), (1790, 355), (1828, 380), 4.5, 0.29),
)


def _pc2_header(fh, count, samples):
    fh.write(struct.pack("<12siiffi", b"POINTCACHE2\0", 1, int(count), 0.0, 1.0, int(samples)))


def _hex_linear(value):
    rgb = np.array([int(value[k:k + 2], 16) / 255.0 for k in (1, 3, 5)])
    return tuple(np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4))


def _emission_material(name, hex_color):
    import bpy

    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    out = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    emission = mat.node_tree.nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (*_hex_linear(hex_color), 1.0)
    mat.node_tree.links.new(emission.outputs["Emission"], out.inputs["Surface"])
    return mat


def _smooth(value):
    x = np.clip(value, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _read_wave_cache(wave, n_frames):
    import bpy

    md = wave.modifiers.get("PointCache")
    if md is None or md.type != "MESH_CACHE":
        raise RuntimeError("GreatWave must have its PC2 PointCache modifier")
    source = bpy.path.abspath(md.filepath)
    if not os.path.isfile(source):
        source = wm.load_wave_params()["cache_path"]
    with open(source, "rb") as fh:
        signature, version, count, start, interval, samples = struct.unpack("<12siiffi", fh.read(32))
    n_u, n_v = int(wave["gw_n_u"]), int(wave["gw_n_v"])
    if signature.rstrip(b"\0") != b"POINTCACHE2" or count != n_u * n_v or samples < n_frames:
        raise RuntimeError("Wave PC2 header/topology does not match the loaded scene")
    if os.path.getsize(source) < 32 + 12 * count * samples:
        raise RuntimeError("Wave PC2 is truncated")
    data = np.memmap(source, dtype="<f4", mode="r", offset=32, shape=(samples, n_v, n_u, 3))
    return data, n_u, n_v, source


def _local_normal(row, indices):
    """XZ inward normal to the ordered back->crest->head->trough section."""
    lo = np.maximum(indices - 2, 0)
    hi = np.minimum(indices + 2, row.shape[0] - 1)
    delta = row[hi][:, (0, 2)] - row[lo][:, (0, 2)]
    tangent = delta / np.maximum(np.linalg.norm(delta, axis=1)[:, None], 1e-9)
    inward = np.stack([tangent[:, 1], -tangent[:, 0]], axis=1)
    return tangent, inward


def _band_topology(n_y, n_u):
    """A thin, closed crest veneer: two edges for each profile/y sample."""
    faces = []
    vid = lambda j, i, side: (j * n_u + i) * 2 + side
    for j in range(n_y):
        for i in range(n_u - 1):
            faces.append((vid(j, i, 0), vid(j, i + 1, 0), vid(j, i + 1, 1), vid(j, i, 1)))
    for j in range(n_y - 1):
        for i in range(n_u - 1):
            for side in (0, 1):
                faces.append((vid(j, i, side), vid(j + 1, i, side),
                              vid(j + 1, i + 1, side), vid(j, i + 1, side)))
    for j in range(n_y - 1):
        for i in (0, n_u - 1):
            faces.append((vid(j, i, 0), vid(j, i, 1), vid(j + 1, i, 1), vid(j + 1, i, 0)))
    return faces


def _band_vertices(wave_frame, y_indices, u_indices, H, frame_num):
    growth = float(_smooth((frame_num - 105.0) / 180.0))
    out = np.empty((len(y_indices), len(u_indices), 2, 3), np.float32)
    for jj, row_index in enumerate(y_indices):
        row = wave_frame[row_index]
        anchor = row[u_indices].astype(np.float64)
        _, normal = _local_normal(row, u_indices)
        # Ends of the crest line fade into the water rather than becoming a
        # disconnected flat white sheet across the flanks.
        y_fade = math.sin(math.pi * (jj + 0.4) / (len(y_indices) - 0.2)) ** 0.8
        along = np.linspace(0.0, 1.0, len(u_indices))
        scallop = 0.85 + 0.15 * np.sin(18.0 * along + 3.0 * row_index / max(y_indices[-1], 1))
        width = H * (0.007 + 0.015 * _smooth((along - 0.50) / 0.5)) * growth * y_fade * scallop
        outer = anchor.copy()
        inner = anchor.copy()
        outer[:, 0] -= normal[:, 0] * H * 0.002 * growth
        outer[:, 2] -= normal[:, 1] * H * 0.002 * growth
        inner[:, 0] += normal[:, 0] * width
        inner[:, 2] += normal[:, 1] * width
        # Small near-camera lift avoids z-fighting with the wave skin.
        outer[:, 1] -= H * 0.003
        inner[:, 1] -= H * 0.003
        out[jj, :, 0] = outer
        out[jj, :, 1] = inner
    return out.reshape(-1, 3)


def _claw_topology(n_claws, n_path=23, n_sides=8):
    faces = []
    stride = n_path * n_sides
    for claw in range(n_claws):
        off = claw * stride
        for i in range(n_path - 1):
            for side in range(n_sides):
                a = off + i * n_sides + side
                b = off + i * n_sides + (side + 1) % n_sides
                c = off + (i + 1) * n_sides + (side + 1) % n_sides
                d = off + (i + 1) * n_sides + side
                faces.append((a, b, c, d))
    return faces


def _claw_vertices(wave_frame, final_wave, y_indices, frame, H, frame_num, white):
    n_path, n_sides = 23, 8
    vertices = np.empty((len(CLAWS), n_path, n_sides, 3), np.float32)
    s = np.linspace(0.0, 1.0, n_path)
    bern = np.stack([(1 - s) ** 3, 3 * (1 - s) ** 2 * s, 3 * (1 - s) * s * s, s ** 3], axis=1)
    for k, (u, tip_px, control1_px, control2_px, radius_px, y_H) in enumerate(CLAWS):
        row_index = y_indices[k]
        anchor = wave_frame[row_index, u].astype(np.float64)
        final_anchor = final_wave[row_index, u].astype(np.float64)
        root_xz = final_anchor[[0, 2]]
        controls = [np.array(frame.px_to_m(*px), dtype=np.float64)
                    for px in (control1_px, control2_px, tip_px)]
        # Rotate the final painted path with its material point as the wave
        # turns, then reveal it gradually during the overhang/curl phase.
        now_row = wave_frame[row_index]
        end_row = final_wave[row_index]
        now_t, _ = _local_normal(now_row, np.array([u]))
        end_t, _ = _local_normal(end_row, np.array([u]))
        dot = float(np.clip(np.dot(now_t[0], end_t[0]), -1.0, 1.0))
        cross = float(now_t[0, 0] * end_t[0, 1] - now_t[0, 1] * end_t[0, 0])
        angle = -math.atan2(cross, dot)
        rot = np.array([[math.cos(angle), -math.sin(angle)],
                        [math.sin(angle), math.cos(angle)]])
        growth = float(_smooth((frame_num - (150 + 5 * k)) / (135 - 5 * k)))
        p0 = anchor[[0, 2]]
        points = np.stack([p0] + [p0 + growth * (rot @ (p - root_xz)) for p in controls])
        centres = bern @ points
        # A subtle 3-D bow gives depth when seen from the boat/oblique camera.
        curve_y = anchor[1] - 0.025 * H + 0.08 * H * math.sin(1.7 * k) * 4 * s * (1 - s) * growth
        tangent = np.gradient(centres, axis=0)
        tangent /= np.maximum(np.linalg.norm(tangent, axis=1)[:, None], 1e-9)
        normal = np.stack([-tangent[:, 1], tangent[:, 0]], axis=1)
        # At the 1/3-scale review render the source-width outline otherwise
        # collapses to a hairline against the equally pale paper background.
        radius = (1.5 * radius_px * frame.H_per_px * H) * growth
        radius *= (0.76 + 0.24 * np.sin(math.pi * np.minimum(s, 0.5))) * np.maximum(0.08, (1 - s) ** 0.7)
        radius *= 0.14 + 0.86 * _smooth(s / 0.19)
        radius = np.maximum(radius, 1e-5)
        if white:
            # Move the white core toward CAM_print so that the ink shell reads
            # as a narrow outline, rather than hiding the core at the centre.
            curve_y -= (4.0 * frame.H_per_px * H * growth + 0.0005)
            radius *= 0.64
        for side in range(n_sides):
            theta = side * 2 * math.pi / n_sides
            vertices[k, :, side, 0] = centres[:, 0] + radius * math.cos(theta) * normal[:, 0]
            vertices[k, :, side, 1] = curve_y + radius * math.sin(theta)
            vertices[k, :, side, 2] = centres[:, 1] + radius * math.cos(theta) * normal[:, 1]
    return vertices.reshape(-1, 3)


def _make_cached_object(name, vertices, faces, material, cache_path):
    import bpy

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices.tolist(), [], faces)
    mesh.update(calc_edges=True)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    mesh.materials.append(material)
    # Workbench previews use OBJECT colours, whereas Eevee uses the emission
    # materials. Keep the same visual roles in both render paths.
    obj.color = (0.08, 0.17, 0.27, 1.0) if name == CLAW_INK_NAME else (0.95, 0.94, 0.88, 1.0)
    md = obj.modifiers.new("PointCache", "MESH_CACHE")
    md.cache_format = "PC2"
    md.filepath = cache_path
    md.time_mode = "FRAME"
    md.play_mode = "SCENE"
    md.frame_start = 1.0
    md.frame_scale = 1.0
    md.interpolation = "LINEAR"
    md.deform_mode = "OVERWRITE"
    md.forward_axis = "POS_Y"
    md.up_axis = "POS_Z"
    obj["foam_source"] = "GreatWave PC2 material-point anchors; print-camera claw paths"
    obj["foam_limit"] = "art-directed surface geometry, not a fluid/whitewater simulation"
    return obj


def build(output_path="blend/great_wave_foam.blend"):
    import bpy

    scene = bpy.context.scene
    wave = bpy.data.objects.get("GreatWave")
    if wave is None:
        raise RuntimeError("Load blend/great_wave.blend or a styled derivative before running")
    wp = wm.load_wave_params()
    n_frames = int(wp["n_frames"])
    if n_frames != FINAL_FRAME:
        raise RuntimeError("Foam control points are calibrated for a 285-frame wave")
    for name in (BAND_NAME, CLAW_INK_NAME, CLAW_WHITE_NAME):
        old = bpy.data.objects.get(name)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
    cache, n_u, n_v, wave_path = _read_wave_cache(wave, n_frames)
    source_stamp = (os.stat(wave_path).st_size, os.stat(wave_path).st_mtime_ns)
    H = gw_frame.Frame.from_params().H
    fr = gw_frame.Frame.from_params()
    # The central 0.7 H has an identical section. Sweeping the ribbon over
    # the tapered flanks would project broad white triangles across the wave
    # cavity, so keep this initial foam veneer on the un-tapered crest only.
    y_indices = np.array([n_v // 2 - 8, n_v // 2, n_v // 2 + 8], dtype=np.int32)
    u_indices = np.arange(203, 265, dtype=np.int32)
    centre_y = np.asarray(cache[n_frames - 1, :, 0, 1])
    claw_y_indices = [int(np.argmin(abs(centre_y - y_H * H))) for *_, y_H in CLAWS]
    final_wave = np.asarray(cache[n_frames - 1])

    out_paths = [os.path.join(wm.PROJECT, "cache", stem + ".pc2")
                 for stem in ("foam_crest_band", "foam_claws_ink", "foam_claws_white")]
    for path in out_paths:
        paths.ensure_parent(path)
    first = None
    with open(out_paths[0], "wb") as band_file, open(out_paths[1], "wb") as ink_file, open(out_paths[2], "wb") as white_file:
        counts = (len(y_indices) * len(u_indices) * 2, len(CLAWS) * 23 * 8, len(CLAWS) * 23 * 8)
        for fh, count in zip((band_file, ink_file, white_file), counts):
            _pc2_header(fh, count, n_frames)
        for frame_num in range(1, n_frames + 1):
            wave_frame = np.asarray(cache[frame_num - 1])
            arrays = (
                _band_vertices(wave_frame, y_indices, u_indices, H, frame_num),
                _claw_vertices(wave_frame, final_wave, claw_y_indices, fr, H, frame_num, False),
                _claw_vertices(wave_frame, final_wave, claw_y_indices, fr, H, frame_num, True),
            )
            if first is None:
                first = [a.copy() for a in arrays]
            for fh, verts in zip((band_file, ink_file, white_file), arrays):
                fh.write(np.ascontiguousarray(verts, dtype="<f4").tobytes())
            if frame_num % 70 == 0 or frame_num == n_frames:
                bootstrap.log("foam cache frame %d/%d" % (frame_num, n_frames))
    current_stamp = (os.stat(wave_path).st_size, os.stat(wave_path).st_mtime_ns)
    if current_stamp != source_stamp:
        raise RuntimeError("Wave cache changed while foam was baking; rerun after the wave build finishes")

    mats = (_emission_material("GW_foam_geometry", "#f3f0e1"),
            _emission_material("GW_foam_ink_outline", "#142b4c"))
    faces_band = _band_topology(len(y_indices), len(u_indices))
    faces_claw = _claw_topology(len(CLAWS))
    objects = (
        _make_cached_object(BAND_NAME, first[0], faces_band, mats[0], out_paths[0]),
        _make_cached_object(CLAW_INK_NAME, first[1], faces_claw, mats[1], out_paths[1]),
        _make_cached_object(CLAW_WHITE_NAME, first[2], faces_claw, mats[0], out_paths[2]),
    )
    scene.frame_set(n_frames)
    scene.render.engine = "BLENDER_EEVEE"
    scene.view_settings.view_transform = "Standard"
    out_blend = paths.project_path(output_path)
    paths.ensure_parent(out_blend)
    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    for obj, path in zip(objects, out_paths):
        obj.modifiers["PointCache"].filepath = bpy.path.relpath(path)
    bpy.ops.wm.save_mainfile()
    bootstrap.log("source wave cache %s" % wave_path)
    bootstrap.log("saved %s; foam verts %s" % (out_blend, ", ".join(str(len(o.data.vertices)) for o in objects)))
    return objects, out_blend


def _preview(variant=""):
    import bpy

    scene = bpy.context.scene
    out_dir = paths.ensure_dir(os.path.join(wm.PROJECT, "results", "foam_preview", variant))
    for camera, f, width, height in (("CAM_print", 210, 1286, 864),
                                     ("CAM_print", 285, 1286, 864),
                                     ("CAM_view34", 285, 1280, 720)):
        scene.camera = bpy.data.objects[camera]
        scene.frame_set(f)
        scene.render.resolution_x, scene.render.resolution_y = width, height
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = os.path.join(out_dir, "%s_f%03d.png" % (camera, f))
        bpy.ops.render.render(write_still=True)
        bootstrap.log("rendered %s frame %d" % (camera, f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--preview-variant", default="")
    ap.add_argument("--output", default="blend/great_wave_foam.blend")
    args = bootstrap.parse_args(ap)
    bootstrap.set_log_prefix("GW_FOAM")
    build(args.output)
    if args.preview:
        _preview(args.preview_variant)
    bootstrap.finish(True, "add_animated_foam")


if __name__ == "__main__":
    main()
