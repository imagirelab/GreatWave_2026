"""造形の静止座標を使う、藍色の流線と白波の試作材質。"""

import bpy

from gwave.build_localized_scene import rgba, math_node, color_mix


def make_material(name="藍の水体と生成りの白波", foam=False, sea=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    coords = nodes.new("ShaderNodeAttribute")
    coords.attribute_name = "rest_position"
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(coords.outputs["Vector"], sep.inputs[0])
    m = lambda op, a, b=None: math_node(nodes, links, op, a, b)
    x, y, z = [m("DIVIDE", sep.outputs[k], 11) for k in ("X", "Y", "Z")]
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = .43
    noise.inputs["Detail"].default_value = 2.2
    noise.inputs["Roughness"].default_value = .65
    links.new(coords.outputs["Vector"], noise.inputs["Vector"])
    # 巻込みの内弧を中心とする帯で、縦の等間隔な縞を避ける。
    dx,dz = m("SUBTRACT",x,.42),m("SUBTRACT",z,.43)
    radius = m("SQRT",m("ADD",m("MULTIPLY",dx,dx),m("MULTIPLY",dz,dz)))
    phase = m("ADD",m("MULTIPLY",radius,24),m("MULTIPLY",y,2.4))
    phase = m("ADD",phase,m("MULTIPLY",noise.outputs["Fac"],.30))
    stripe = m("SINE", phase)
    blue = color_mix(nodes, links, m("GREATER_THAN", stripe, .42), "#10344e", "#246b91")
    blue = color_mix(nodes, links, m("GREATER_THAN", stripe, .96), blue, "#609bb0")
    geometry = nodes.new("ShaderNodeNewGeometry")
    world = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geometry.outputs["Position"],world.inputs[0])
    wx,wy,wz = [m("DIVIDE",world.outputs[k],11) for k in ("X","Y","Z")]
    water_noise = nodes.new("ShaderNodeTexNoise")
    water_noise.inputs["Scale"].default_value = .43
    water_noise.inputs["Detail"].default_value = 2.2
    water_noise.inputs["Roughness"].default_value = .65
    links.new(geometry.outputs["Position"],water_noise.inputs["Vector"])
    sea_phase = m("ADD",m("MULTIPLY",wx,4),m("MULTIPLY",water_noise.outputs["Fac"],3.8))
    sea_phase = m("ADD",sea_phase,m("MULTIPLY",m("SINE",m("MULTIPLY",wy,1.8)),2.1))
    water_color = color_mix(nodes,links,m("GREATER_THAN",m("SINE",sea_phase),.74),"#244d62","#477788")
    above = m("MULTIPLY",m("SUBTRACT",wz,.025),6)
    above.node.use_clamp = True
    if sea:
        # 細い等間隔の平行線を避け、大きさの異なる色面を使う。
        blue = water_color
        white = 0.0
    elif foam:
        white = 1.0
    else:
        cap = nodes.new("ShaderNodeAttribute")
        cap.attribute_name = "foam_weight"
        ragged = m("SUBTRACT", cap.outputs["Fac"], m("MULTIPLY", noise.outputs["Fac"], .18))
        white = m("GREATER_THAN", ragged, .48)
        white = m("MULTIPLY",white,above)
        blue = color_mix(nodes,links,above,water_color,blue)
    base = color_mix(nodes, links, white, blue, "#f0ebd7")
    # 狭い輪郭線と弱い陰影で立体の裏面を読み取れるようにする。
    layer = nodes.new("ShaderNodeFresnel")
    layer.inputs["IOR"].default_value = 1.2
    edge = 0.0 if sea else m("MULTIPLY",m("GREATER_THAN",layer.outputs[0],.09),above)
    color = color_mix(nodes, links, edge, base, "#122f46")
    occlusion = nodes.new("ShaderNodeAmbientOcclusion")
    occlusion.inputs["Distance"].default_value = .38
    occlusion.samples = 16
    occlusion.only_local = True
    light = m("ADD", .48, m("MULTIPLY", occlusion.outputs["AO"], .52))
    shade = nodes.new("ShaderNodeMixRGB")
    shade.blend_type = "MULTIPLY"
    shade.inputs[0].default_value = 1
    links.new(color, shade.inputs[1])
    links.new(light, shade.inputs[2])
    emission = nodes.new("ShaderNodeEmission")
    links.new(shade.outputs[0], emission.inputs[0])
    diffuse = nodes.new("ShaderNodeBsdfDiffuse")
    links.new(shade.outputs[0], diffuse.inputs["Color"])
    diffuse.inputs["Roughness"].default_value = .55
    mix = nodes.new("ShaderNodeMixShader")
    if sea:
        mix.inputs[0].default_value = .30
    else:
        links.new(m("ADD",.30,m("MULTIPLY",above,.32)),mix.inputs[0])
    links.new(emission.outputs[0], mix.inputs[1])
    links.new(diffuse.outputs[0], mix.inputs[2])
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(mix.outputs[0], out.inputs[0])
    mat.diffuse_color = rgba("#246b91")
    return mat
