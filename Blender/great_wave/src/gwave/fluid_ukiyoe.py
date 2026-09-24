"""可変トポロジーの実流体を、藍色の色面で表示する材質試験。

法線と遮蔽から陰影を作る。白波は別模型を使い、主水体の高さを
白く塗るだけで白波の計算が成立したとは扱わない。
"""

import bpy

from gwave.build_localized_scene import rgba, math_node, color_mix


def material(name="流体の藍色の色面", foam=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    geo = nodes.new("ShaderNodeNewGeometry")
    dot = nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = (-.35, -.55, .76)
    links.new(geo.outputs["Normal"], dot.inputs[0])
    m = lambda op, a, b=None: math_node(nodes, links, op, a, b)
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    if foam:
        colors = [(0, "#b7c5be"), (.30, "#d8ddcd"), (.54, "#f3efdf")]
    else:
        colors = [(0, "#12344d"), (.32, "#225772"), (.59, "#397d98"), (.83, "#5b9bae")]
    for index, (position, color) in enumerate(colors):
        element = ramp.color_ramp.elements[index] if index < 2 else ramp.color_ramp.elements.new(position)
        element.position, element.color = position, rgba(color)
    links.new(m("MULTIPLY_ADD", dot.outputs["Value"], .5), ramp.inputs[0])
    # 法線の内積 -1～1 を 0～1 へ写す。
    mapped = ramp.inputs[0].links[0].from_node
    mapped.inputs[2].default_value = .5
    fresnel = nodes.new("ShaderNodeFresnel")
    fresnel.inputs["IOR"].default_value = 1.12
    edge = m("GREATER_THAN", fresnel.outputs[0], .25)
    color = color_mix(nodes, links, edge, ramp.outputs["Color"], "#183b50")
    ao = nodes.new("ShaderNodeAmbientOcclusion")
    ao.inputs["Distance"].default_value = .20
    ao.samples = 16
    shade = nodes.new("ShaderNodeMixRGB")
    shade.blend_type = "MULTIPLY"
    shade.inputs[0].default_value = 1
    links.new(color, shade.inputs[1])
    links.new(m("ADD", .70, m("MULTIPLY", ao.outputs["AO"], .30)), shade.inputs[2])
    emission = nodes.new("ShaderNodeEmission")
    links.new(shade.outputs[0], emission.inputs[0])
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(emission.outputs[0], output.inputs[0])
    mat.diffuse_color = rgba("#397d98" if not foam else "#f3efdf")
    return mat


def apply(scene=None):
    scene = scene or bpy.context.scene
    mat = material()
    objects = [obj for obj in scene.objects if obj.type == "MESH" and not obj.hide_render]
    for obj in objects:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = rgba("#e3d9be")
    scene.view_settings.view_transform = "Standard"
    return len(objects)
