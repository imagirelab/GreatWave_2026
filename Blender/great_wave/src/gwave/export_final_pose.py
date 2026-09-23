"""Freeze an animated scene into a self-contained, editable final-pose .blend.

Run on ``blend/great_wave_foam.blend`` after building the wave and foam::

    tools/run_blender.ps1 src/gwave/export_final_pose.py -Blend blend/great_wave_foam.blend -NoFactoryStartup

The full animation remains reproducible from scripts and PC2 caches. This small
review file contains evaluated meshes at the chosen frame, without external
point-cache dependencies. Packed images keep the still scene portable.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

from gw import bootstrap, paths
from gwave import profile_motion as wm


def export(out_path, final_frame, hide_paper=False):
    import bpy

    scene = bpy.context.scene
    scene.frame_set(final_frame)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    names = [obj.name for obj in scene.objects
             if obj.type == "MESH" and any(mod.type == "MESH_CACHE" for mod in obj.modifiers)]
    if "GreatWave" not in names:
        raise RuntimeError("Load the generated animation scene with its Mesh Cache modifiers")
    counts = {}
    for name in names:
        obj = bpy.data.objects[name]
        evaluated = obj.evaluated_get(depsgraph)
        mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
        mesh.name = "%s_final_f%03d" % (name, final_frame)
        if not mesh.materials:
            for material in obj.data.materials:
                mesh.materials.append(material)
        if len(mesh.vertices) != len(obj.data.vertices):
            raise RuntimeError("Unexpected topology change on %s" % name)
        for modifier in list(obj.modifiers):
            obj.modifiers.remove(modifier)
        obj.data = mesh
        obj["frozen_from_frame"] = int(final_frame)
        counts[name] = len(mesh.vertices)
    bpy.ops.file.pack_all()
    if hide_paper:
        paper = bpy.data.objects.get("Hokusai_paper_guide")
        if paper is not None:
            paper.hide_render = True
            paper.hide_set(True)
        scene.camera = bpy.data.objects["CAM_view34"]
    scene.frame_start = final_frame
    scene.frame_end = final_frame
    paths.ensure_parent(out_path)
    bpy.ops.wm.save_as_mainfile(filepath=out_path)
    return counts


def verify_reopen(out_path, final_frame, names):
    import bpy

    bpy.ops.wm.open_mainfile(filepath=out_path)
    scene = bpy.context.scene
    if scene.frame_start != final_frame or scene.frame_end != final_frame:
        raise RuntimeError("Exported scene did not retain its final-frame setting")
    for name, expected_count in names.items():
        obj = bpy.data.objects.get(name)
        if obj is None or len(obj.data.vertices) != expected_count:
            raise RuntimeError("Mesh %s missing or changed after reopening" % name)
        if any(mod.type == "MESH_CACHE" for mod in obj.modifiers):
            raise RuntimeError("Export still depends on a point cache: %s" % name)
    missing = [image.name for image in bpy.data.images
               if image.source == "FILE" and image.packed_file is None]
    if missing:
        raise RuntimeError("Unpacked external image(s): %s" % ", ".join(missing))
    return os.path.getsize(out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", type=int, default=None)
    ap.add_argument("--out", default="deliverables/great_wave_final_pose.blend")
    ap.add_argument("--hide-paper", action="store_true", help="default to an unobstructed 3-D review view")
    args = bootstrap.parse_args(ap)
    bootstrap.set_log_prefix("GW_EXPORT")
    frame = int(args.frame or wm.load_wave_params()["n_frames"])
    out_path = paths.project_path(args.out)
    counts = export(out_path, frame, args.hide_paper)
    size = verify_reopen(out_path, frame, counts)
    bootstrap.log("verified %s (%0.1f MB); frozen meshes %s" %
                  (out_path, size / 1e6, counts))
    bootstrap.finish(True, "export_final_pose")


if __name__ == "__main__":
    main()
