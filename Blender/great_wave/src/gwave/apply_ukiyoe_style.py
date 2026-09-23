"""Paint the animated mesh with a camera-projected Hokusai reference texture.

The UV coordinates are frozen from the *final* evaluated mesh.  They therefore
travel with the animated vertices, while at frame 285 the print camera samples
the source painting at the matching image coordinate.  This is a useful visual
target for the large wave, not a substitute for separately modelled foam or a
view-independent ukiyo-e shader.

Run after build_great_wave.py::

    tools/run_blender.ps1 src/gwave/apply_ukiyoe_style.py -Blend blend/great_wave.blend

The generated styled scene is kept under the ignored blend/ directory.  The
script and the reference image are the reproducible source of this material.
"""

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

import numpy as np

from gw import bootstrap, frame as gw_frame, paths
from gwave import profile_motion as wm


def _emission_material(name, color):
    import bpy

    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = color
    mat.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return mat


def _projected_material(image_path):
    import bpy

    image = bpy.data.images.load(image_path, check_existing=True)
    image.pack()
    mat = bpy.data.materials.get("Hokusai_projected_wave") or bpy.data.materials.new("Hokusai_projected_wave")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "Hokusai_final_projection"
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.extension = "EXTEND"
    tex.interpolation = "Linear"
    emission = nodes.new("ShaderNodeEmission")
    output = nodes.new("ShaderNodeOutputMaterial")
    links = mat.node_tree.links
    links.new(uv.outputs["UV"], tex.inputs["Vector"])
    links.new(tex.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return mat


def _set_final_projection_uv(scene, obj, final_frame, frame):
    """Use evaluated geometry because the base mesh is the first animation frame."""
    import bpy

    scene.frame_set(final_frame)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    xyz = np.empty(len(evaluated.data.vertices) * 3, np.float32)
    evaluated.data.vertices.foreach_get("co", xyz)
    xyz = xyz.reshape(-1, 3)
    if not np.isfinite(xyz).all() or float(xyz[:, 2].max()) < 0.7 * frame.H:
        raise RuntimeError("The final-frame point cache is missing or has not evaluated")
    if len(xyz) != len(obj.data.vertices):
        raise RuntimeError("A topology-changing modifier prevents stable projected UVs")
    uv = obj.data.uv_layers.get("Hokusai_final_projection") or obj.data.uv_layers.new(name="Hokusai_final_projection")
    loop_ids = np.empty(len(obj.data.loops), dtype=np.int32)
    obj.data.loops.foreach_get("vertex_index", loop_ids)
    X = xyz[loop_ids, 0] / frame.H
    Z = xyz[loop_ids, 2] / frame.H
    u = (X - frame.x_left) / frame.frame_w
    v = (Z - frame.z_bottom) / frame.frame_h
    uv.data.foreach_set("uv", np.stack([u, v], axis=1).astype(np.float32).ravel())
    return float(xyz[:, 2].max()), len(xyz)


def _make_background(frame):
    """Neutral paper and distant-sea guide, without a static copy of the great wave."""
    import bpy

    obj = bpy.data.objects.get("Hokusai_paper_guide")
    if obj is None:
        x0, x1 = frame.x_left * frame.H, frame.x_right * frame.H
        z0, z1 = frame.z_bottom * frame.H, frame.z_top * frame.H
        y = 4.5 * frame.H
        mesh = bpy.data.meshes.new("Hokusai_paper_guide")
        mesh.from_pydata([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], [], [(0, 1, 2, 3)])
        uv = mesh.uv_layers.new(name="UVMap")
        uv.data.foreach_set("uv", [0, 0, 1, 0, 1, 1, 0, 1])
        obj = bpy.data.objects.new("Hokusai_paper_guide", mesh)
        bpy.context.scene.collection.objects.link(obj)
    mat = bpy.data.materials.get("Hokusai_paper_and_sea") or bpy.data.materials.new("Hokusai_paper_and_sea")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    uv = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "EASE"
    cr = ramp.color_ramp
    cr.elements.remove(cr.elements[1])
    for pos, color in ((0.0, (0.24, 0.32, 0.36, 1)),
                       (0.29, (0.58, 0.59, 0.55, 1)),
                       (0.38, (0.83, 0.78, 0.66, 1)),
                       (1.0, (0.89, 0.84, 0.73, 1))):
        e = cr.elements[0] if pos == 0.0 else cr.elements.new(pos)
        e.position, e.color = pos, color
    em = nodes.new("ShaderNodeEmission")
    out = nodes.new("ShaderNodeOutputMaterial")
    links = mat.node_tree.links
    links.new(uv.outputs["UV"], sep.inputs["Vector"])
    links.new(sep.outputs["Y"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], em.inputs["Color"])
    links.new(em.outputs["Emission"], out.inputs["Surface"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


def apply():
    import bpy

    scene = bpy.context.scene
    WP = wm.load_wave_params()
    final_frame = int(WP["n_frames"])
    obj = bpy.data.objects["GreatWave"]
    fr = gw_frame.Frame.from_params()
    crest_m, vertex_count = _set_final_projection_uv(scene, obj, final_frame, fr)
    mat = _projected_material(paths.painting_path())
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    _make_background(fr)

    # The old Workbench reference sea is edge-on in CAM_print, but can obscure
    # the wave in other views once Eevee is enabled.
    sea = bpy.data.objects.get("Sea_ref")
    if sea:
        sea.hide_render = True
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.camera = bpy.data.objects["CAM_print"]
    scene.render.resolution_x = 1286
    scene.render.resolution_y = 864
    scene.render.resolution_percentage = 100
    obj["visual_method"] = "Final-frame print-camera UV projection; animated by the original PC2 wave mesh"
    obj["visual_limit"] = "A single-view texture reference; foam geometry and HMD-independent shading are separate milestones"
    scene.frame_set(final_frame)
    return {"crest_m": crest_m, "vertices": vertex_count}


def main():
    import bpy

    bootstrap.set_log_prefix("GW_STYLE")
    stats = apply()
    out = os.path.join(wm.PROJECT, "blend", "great_wave_styled.blend")
    paths.ensure_parent(out)
    bpy.ops.wm.save_as_mainfile(filepath=out)
    bootstrap.log("styled scene %s; crest %.3f m; vertices %d" % (out, stats["crest_m"], stats["vertices"]))
    bootstrap.finish(True, "apply_ukiyoe_style")


if __name__ == "__main__":
    import bpy
    main()
