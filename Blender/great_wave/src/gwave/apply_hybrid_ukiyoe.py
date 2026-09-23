"""Test a view-dependent blend of a painted final-pose projection and a 3-D shader.

The painting is confined to the camera-near crest flank in UV V and fades out
as the view rotates away from CAM_print.  This is a *rejected experiment* for
HMD use: at 15 degrees from the print camera the projected detail forms long
horizontal streaks, even though the print and 34-degree endpoint renders look
good.  A narrower angle gate would replace the streaking with a sudden change.

Run on a scene with the animated foam objects already built, for example::

    tools/run_blender.ps1 src/gwave/apply_hybrid_ukiyoe.py \
        -Blend blend/great_wave_foam.blend -NoFactoryStartup
"""

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

from gw import bootstrap, frame as gw_frame, paths
from gwave import profile_motion as wm
from gwave.add_animated_foam import BAND_NAME, CLAW_INK_NAME, CLAW_WHITE_NAME
from gwave.apply_procedural_ukiyoe import apply as apply_procedural
from gwave.apply_ukiyoe_style import _set_final_projection_uv


def _scalar_ramp(nodes, links, source, stops):
    """Return a grayscale ramp output with values specified in [0, 1]."""
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "EASE"
    cr = ramp.color_ramp
    cr.elements.remove(cr.elements[1])
    for i, (position, value) in enumerate(stops):
        e = cr.elements[0] if i == 0 else cr.elements.new(float(position))
        e.position = float(position)
        e.color = (float(value), float(value), float(value), 1.0)
    links.new(source, ramp.inputs["Fac"])
    return ramp.outputs["Color"]


def apply():
    import bpy

    scene = bpy.context.scene
    wave = bpy.data.objects.get("GreatWave")
    if wave is None:
        raise RuntimeError("Load a generated GreatWave scene first")
    # A hybrid print comparison without the separate foam silhouette would be
    # misleading, so require the completed foam pass as the input scene.
    available = {ob.name for ob in scene.objects}
    missing = {BAND_NAME, CLAW_INK_NAME, CLAW_WHITE_NAME} - available
    if missing:
        raise RuntimeError("Load the separately animated foam scene; missing %s" % ", ".join(sorted(missing)))

    apply_procedural()
    final_frame = int(wm.load_wave_params()["n_frames"])
    _set_final_projection_uv(scene, wave, final_frame, gw_frame.Frame.from_params())

    image = bpy.data.images.load(paths.painting_path(), check_existing=True)
    image.pack()
    mat = wave.active_material
    if mat is None or not mat.use_nodes:
        raise RuntimeError("Procedural material did not build")
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    emission = next((node for node in nodes if node.type == "EMISSION"), None)
    if emission is None or not emission.inputs["Color"].is_linked:
        raise RuntimeError("Procedural material has no connected emission colour")
    procedural_colour = emission.inputs["Color"].links[0].from_socket

    projection_uv = nodes.new("ShaderNodeUVMap")
    projection_uv.uv_map = "Hokusai_final_projection"
    painting = nodes.new("ShaderNodeTexImage")
    painting.image = image
    painting.extension = "EXTEND"
    painting.interpolation = "Linear"
    links.new(projection_uv.outputs["UV"], painting.inputs["Vector"])

    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    uv_sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(uv.outputs["UV"], uv_sep.inputs["Vector"])
    # The print camera looks along +Y.  Low V is the camera-near wing; the
    # middle and far wing retain the 3-D shader to avoid stripes at oblique
    # angles.  Use a wide transition to keep the material continuous.
    near_flank = _scalar_ramp(nodes, links, uv_sep.outputs["Y"],
                              [(0.0, 1.0), (0.40, 1.0), (0.60, 0.0), (1.0, 0.0)])

    geometry = nodes.new("ShaderNodeNewGeometry")
    incoming_unit = nodes.new("ShaderNodeVectorMath")
    incoming_unit.operation = "NORMALIZE"
    links.new(geometry.outputs["Incoming"], incoming_unit.inputs[0])
    incoming_sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(incoming_unit.outputs["Vector"], incoming_sep.inputs["Vector"])
    abs_y = nodes.new("ShaderNodeMath")
    abs_y.operation = "ABSOLUTE"
    links.new(incoming_sep.outputs["Y"], abs_y.inputs[0])
    side_view = _scalar_ramp(nodes, links, abs_y.outputs[0],
                             [(0.0, 0.0), (0.90, 0.0), (0.985, 1.0), (1.0, 1.0)])
    projection_weight = nodes.new("ShaderNodeMath")
    projection_weight.operation = "MULTIPLY"
    links.new(near_flank, projection_weight.inputs[0])
    links.new(side_view, projection_weight.inputs[1])

    hybrid = nodes.new("ShaderNodeMixRGB")
    hybrid.blend_type = "MIX"
    links.new(projection_weight.outputs[0], hybrid.inputs[0])
    links.new(procedural_colour, hybrid.inputs[1])
    links.new(painting.outputs["Color"], hybrid.inputs[2])
    links.new(hybrid.outputs["Color"], emission.inputs["Color"])
    wave["visual_method"] = "experimental UV-flank + view-angle hybrid: final painting / procedural 3-D shader"
    wave["visual_limit"] = "Rejected for HMD: projection streaks at 15 degrees; single final-pose UV"
    scene.frame_set(final_frame)


def main():
    import bpy

    bootstrap.set_log_prefix("GW_HYBRID")
    apply()
    out = os.path.join(wm.PROJECT, "blend", "great_wave_hybrid_foam.blend")
    paths.ensure_parent(out)
    bpy.ops.wm.save_as_mainfile(filepath=out)
    bootstrap.log("saved %s" % out)
    bootstrap.finish(True, "apply_hybrid_ukiyoe")


if __name__ == "__main__":
    main()
