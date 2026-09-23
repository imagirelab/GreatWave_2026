"""局所的な巻く波と独立した白波を、持ち運べるアニメーションとして生成する。

外部の点キャッシュを必要としない絶対シェイプキーを使う。
造形と動画を比較するための美術試作であり、流体計算の結果ではない。
"""

import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector

SOURCE = Path(__file__).resolve().parents[1]
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from gwave.localized_sweep import LocalizedSweep

PROJECT = SOURCE.parent
OUTPUT = PROJECT / "results" / "localized_rebuild"
H = 11.0


def rgba(code):
    c = np.array([int(code[i:i+2], 16) / 255 for i in (1, 3, 5)])
    c = np.where(c <= .04045, c / 12.92, ((c + .055) / 1.055) ** 2.4)
    return (*map(float, c), 1.0)


def math_node(nodes, links, op, a, b=None):
    node = nodes.new("ShaderNodeMath")
    node.operation = op
    for i, value in enumerate((a, b)):
        if value is None:
            continue
        if isinstance(value, (float, int, np.floating)):
            node.inputs[i].default_value = float(value)
        else:
            links.new(value, node.inputs[i])
    return node.outputs[0]


def color_mix(nodes, links, factor, a, b):
    node = nodes.new("ShaderNodeMixRGB")
    for i, value in enumerate((factor, a, b)):
        if isinstance(value, str):
            node.inputs[i].default_value = rgba(value)
        elif isinstance(value, (int, float)):
            node.inputs[i].default_value = value
        else:
            links.new(value, node.inputs[i])
    return node.outputs[0]


def sea_color(nodes, links):
    """主波の平らな縁と周辺海面で同じ世界座標模様を使用する。"""
    geo = nodes.new("ShaderNodeNewGeometry")
    xyz = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geo.outputs["Position"], xyz.inputs[0])
    m = lambda op, a, b=None: math_node(nodes, links, op, a, b)
    x, y = m("MULTIPLY", xyz.outputs["X"], 1/H), m("MULTIPLY", xyz.outputs["Y"], 1/H)
    phase = m("ADD", m("MULTIPLY", y, 14.5), m("MULTIPLY", m("SINE", m("MULTIPLY", x, .75)), 7))
    phase = m("ADD", phase, m("MULTIPLY", m("SINE", m("ADD", m("MULTIPLY", x, 2.2), m("MULTIPLY", y, 3.1))), .7))
    stripe = m("SINE", phase)
    base = color_mix(nodes, links, m("GREATER_THAN", stripe, .7), "#406b83", "#548097")
    return color_mix(nodes, links, m("GREATER_THAN", stripe, .999), base, "#83a3ad"), xyz.outputs["Z"]


def surface_material(sweep, sea=False):
    mat = bpy.data.materials.new("海面の藍色" if sea else "波面の藍色と白い波冠")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    uv = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(uv.outputs["UV"], sep.inputs[0])
    u, v = sep.outputs["X"], sep.outputs["Y"]
    m = lambda op, a, b=None: math_node(nodes, links, op, a, b)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 24
    noise.inputs["Detail"].default_value = 2
    links.new(uv.outputs["UV"], noise.inputs["Vector"])
    phase = m("ADD", m("MULTIPLY", v, 175), m("MULTIPLY", m("SINE", m("MULTIPLY", u, 9)), 7))
    stripe = m("SINE", m("ADD", phase, m("MULTIPLY", noise.outputs["Fac"], 3)))
    blue = color_mix(nodes, links, m("GREATER_THAN", stripe, .30), "#153959", "#356c8f")
    blue = color_mix(nodes, links, m("GREATER_THAN", stripe, .96), blue, "#88b2bf")
    if sea:
        blue, unused = sea_color(nodes, links)
        white = 0.0
    else:
        ic = float(sweep.u[sweep.motion.i_c])
        it = float(sweep.u[sweep.motion.i_t])
        scallop = m("MULTIPLY", m("ADD", m("SINE", m("MULTIPLY", v, 82)), m("MULTIPLY", m("SINE", m("MULTIPLY", v, 217)), .42)), .020)
        boundary = m("ADD", ic - .065, scallop)
        cap = m("MULTIPLY", m("GREATER_THAN", u, boundary), m("LESS_THAN", u, m("ADD", it + .012, m("MULTIPLY", scallop, .75))))
        geometry = nodes.new("ShaderNodeNewGeometry")
        height = nodes.new("ShaderNodeSeparateXYZ")
        links.new(geometry.outputs["Position"], height.inputs[0])
        # 低い肩の同じ物質点へ白色が広がることを防ぎ、泡を高い波冠へ集める。
        height_gate = m("GREATER_THAN", m("MULTIPLY", height.outputs["Z"], 1/H), m("ADD", .57, m("MULTIPLY", noise.outputs["Fac"], .11)))
        cap = m("MULTIPLY", cap, height_gate)
        fleck = nodes.new("ShaderNodeTexNoise")
        fleck.inputs["Scale"].default_value = 140
        fleck.inputs["Detail"].default_value = 1
        links.new(uv.outputs["UV"], fleck.inputs["Vector"])
        dots = m("MULTIPLY", m("GREATER_THAN", fleck.outputs["Fac"], .74), m("MULTIPLY", m("GREATER_THAN", u, ic - .09), m("LESS_THAN", u, it + .15)))
        white = m("MAXIMUM", cap, dots)
    color = color_mix(nodes, links, white, blue, "#eee9d8")
    if not sea:
        surrounding, elevation = sea_color(nodes, links)
        above_sea = m("MULTIPLY", m("SUBTRACT", m("MULTIPLY", elevation, 1/H), .015), 16)
        above_sea.node.use_clamp = True
        color = color_mix(nodes, links, above_sea, surrounding, color)
    emission = nodes.new("ShaderNodeEmission")
    links.new(color, emission.inputs["Color"])
    diffuse = nodes.new("ShaderNodeBsdfDiffuse")
    links.new(color, diffuse.inputs["Color"])
    diffuse.inputs["Roughness"].default_value = .65
    mix = nodes.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = .22
    links.new(emission.outputs[0], mix.inputs[1])
    links.new(diffuse.outputs[0], mix.inputs[2])
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(mix.outputs[0], output.inputs[0])
    mat.diffuse_color = rgba("#356c8f")
    return mat


def simple_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba(color)
    bsdf.inputs["Roughness"].default_value = .85
    bsdf.inputs["Emission Color"].default_value = rgba(color)
    bsdf.inputs["Emission Strength"].default_value = .45
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    fresnel = nodes.new("ShaderNodeFresnel")
    fresnel.inputs["IOR"].default_value = 1.22
    edge = math_node(nodes, links, "GREATER_THAN", fresnel.outputs[0], .07)
    ink = color_mix(nodes, links, edge, color, "#16334d")
    links.new(ink, bsdf.inputs["Base Color"])
    links.new(ink, bsdf.inputs["Emission Color"])
    mat.diffuse_color = rgba(color)
    return mat


def mesh_object(scene, name, vertices, faces):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(np.asarray(vertices).reshape(-1, 3).tolist(), [], np.asarray(faces).tolist())
    mesh.update()
    mesh.polygons.foreach_set("use_smooth", np.ones(len(mesh.polygons), dtype=bool))
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    return obj


def set_uv(obj, coordinates):
    ids = np.empty(len(obj.data.loops), dtype=np.int32)
    obj.data.loops.foreach_get("vertex_index", ids)
    uv = obj.data.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", np.asarray(coordinates, dtype=np.float32)[ids].ravel())


def linear_keys(data):
    action = data.animation_data.action
    for layer in action.layers:
        for strip in layer.strips:
            for slot in action.slots:
                bag = strip.channelbag(slot)
                if bag:
                    for fc in bag.fcurves:
                        for key in fc.keyframe_points:
                            key.interpolation = "LINEAR"


def animate_mesh(obj, sampler, frames, hold_end=345):
    """フレームと絶対キー時刻を明示対応し、外部キャッシュ参照を作らない。"""
    obj.shape_key_add(name="基準形状")
    keys = obj.data.shape_keys
    keys.use_relative = False
    for index, frame in enumerate(frames):
        key = keys.key_blocks[0] if index == 0 else obj.shape_key_add(name=f"時刻_{frame:03d}")
        key.interpolation = "KEY_LINEAR"
        key.data.foreach_set("co", np.asarray(sampler(frame), dtype=np.float32).ravel())
        keys.eval_time = key.frame
        keys.keyframe_insert(data_path="eval_time", frame=frame)
    keys.keyframe_insert(data_path="eval_time", frame=hold_end)
    linear_keys(keys)


def add_spray(scene, sweep):
    """波頭から離れる小滴の造形用運動。泡の生成量を物理的に求めたものではない。"""
    rng = np.random.default_rng(240927)
    count = 180
    birth = rng.uniform(185, 285, count)
    rows = rng.uniform(.32, .72, count) * (sweep.n_v-1)
    columns = rng.uniform(sweep.motion.i_c+14, sweep.motion.i_t+9, count)
    anchors = []
    from gwave.branching_whitewater import Whitewater
    for i, frame in enumerate(birth):
        anchors.append(Whitewater._interpolate(sweep.sample(frame), rows[i:i+1], columns[i:i+1])[0])
    anchors = np.array(anchors)
    velocity = np.column_stack((rng.uniform(.7, 2.8, count), rng.uniform(-1.2, .6, count), rng.uniform(1.4, 4.1, count)))
    radius = rng.uniform(.025, .075, count)
    # 八面体を細かい小滴として使い、独立した幾何形状を保つ。
    base = np.array(((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)), dtype=float)
    tri = np.array(((0,2,4),(2,1,4),(1,3,4),(3,0,4),(2,0,5),(1,2,5),(3,1,5),(0,3,5)))
    faces = (tri[None,:,:]+6*np.arange(count)[:,None,None]).reshape(-1,3)
    def sample(frame):
        age = np.clip((min(frame,285)-birth)/30, 0, 1.3)
        active = ((frame-birth)>=0)*np.clip(age/.10,0,1)*np.clip((1.1-age)/.20,0,1)
        centers = anchors + velocity*age[:,None]
        centers[:,2] -= .5*9.81*age**2
        centers[:,2] = np.maximum(centers[:,2], -.1)
        drop = base[None,:,:]*np.maximum(radius*active, .00001)[:,None,None]
        return centers[:,None,:]+drop
    obj = mesh_object(scene, "波頭から離れる小滴", sample(1), faces)
    obj.data.materials.append(simple_material("飛沫の生成り", "#f4efdf"))
    frames = list(range(1,286,2))
    animate_mesh(obj, sample, frames)
    obj["制作方法"] = "手続き的な放出と重力による小滴の試作。流体との双方向連成はない"
    return obj


def camera(scene, name, location, target, lens=48, ortho=None):
    obj = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    scene.collection.objects.link(obj)
    obj.location = np.array(location) * H
    obj.rotation_euler = (Vector(np.array(target) * H) - obj.location).to_track_quat("-Z", "Y").to_euler()
    obj.data.lens = lens
    obj.data.clip_end = 3000
    if ortho:
        obj.data.type = "ORTHO"
        obj.data.ortho_scale = ortho * H
    return obj


def build(step=8, foam=True):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    sweep = LocalizedSweep()
    scene = bpy.data.scenes.new("局所高峰と分岐白波の検討")
    bpy.context.window.scene = scene
    # この生成器が作った過去の検討シーンだけを置き換える。
    # 利用者の別シーンには触れない。オブジェクト名の連番化も防ぐ。
    for previous in list(bpy.data.scenes):
        if previous != scene and previous.name.startswith("局所高峰と分岐白波の検討"):
            for obj in list(previous.objects):
                bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.scenes.remove(previous)
    scene.name = "局所高峰と分岐白波の検討"
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 1280, 800
    scene.render.resolution_percentage = 100
    scene.render.fps = 30
    scene.frame_start, scene.frame_end = 1, 345
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.world = bpy.data.worlds.new("生成り色の空")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes.get("Background").inputs["Color"].default_value = rgba("#ded4b9")
    scene.world.node_tree.nodes.get("Background").inputs["Strength"].default_value = .7
    light = bpy.data.objects.new("広い面光源", bpy.data.lights.new("広い面光源", "AREA"))
    scene.collection.objects.link(light)
    light.location = (-H, -2*H, 4*H)
    light.data.energy, light.data.shape, light.data.size = 6000, "DISK", 30
    light.rotation_euler = (Vector((0, 0, .5*H)) - light.location).to_track_quat("-Z", "Y").to_euler()

    frames = list(range(1, 286, int(step)))
    if frames[-1] != 285:
        frames.append(285)
    wave = mesh_object(scene, "主波_非対称な峰", sweep.sample(285), sweep.faces())
    uv = np.stack(np.meshgrid(sweep.u, (sweep.y_H-sweep.y_H[0]) / np.ptp(sweep.y_H)), axis=-1).reshape(-1, 2)
    set_uv(wave, uv)
    wave.data.materials.append(surface_material(sweep))
    animate_mesh(wave, sweep.sample, frames)
    wave["制作方法"] = "原画由来の断面と峰方向に異なる発達段階による造形"
    wave["未検証事項"] = "体積保存、流体の物理的正確性、UnityとHMDの実行性能"

    if foam:
        from gwave.branching_whitewater import Whitewater
        whitewater = Whitewater(sweep, H=H)
        white = mesh_object(scene, "白波_独立した分岐形状", whitewater.sample(285), whitewater.faces)
        white.data.materials.append(simple_material("白波の生成り", "#f4efdf"))
        white.data.materials.append(simple_material("白波の陰影", "#78989e"))
        if getattr(whitewater, "material_indices", None) is not None:
            white.data.polygons.foreach_set("material_index", np.asarray(whitewater.material_indices, dtype=np.int32))
        animate_mesh(white, whitewater.sample, frames)
        white["制作方法"] = "水面に追従する独立メッシュ。飛沫の物理計算ではない"
        add_spray(scene, sweep)

    # 周辺の低いうねりは主波との重なりを避けて海面下へ滑らかに弱める。
    sx, sy = np.meshgrid(np.linspace(-14, 18, 161), np.linspace(-12, 20, 161))
    from gwave.profile_motion import grid_faces
    def ocean(frame):
        time = min(frame, 285) / 30
        mask = 1 - np.exp(-((sx+.6)**2/8 + sy**2/3))
        z = (.021*np.sin(2.5*sx - time*.85 + .6*np.sin(sy*.75)) + .013*np.cos(3.6*sy + sx - time*.6)) * mask - .003
        return np.stack([sx, sy, z], axis=-1)*H
    sea = mesh_object(scene, "周辺の低いうねり", ocean(1), grid_faces(161, 161))
    set_uv(sea, np.stack([sx.ravel()/12, sy.ravel()/12], axis=1))
    sea.data.materials.append(surface_material(sweep, sea=True))
    animate_mesh(sea, ocean, list(range(1, 286, 8))+([285] if 285 not in range(1,286,8) else []))
    scene.camera = camera(scene, "CAM_立体確認", (2.6,-5.1,1.75), (-.62,0,.42), lens=52)
    camera(scene, "CAM_原画方向", (.27,-7,.39), (.27,0,.39), ortho=2.5)
    camera(scene, "CAM_船上確認", (1.0,-.5,.12), (.05,0,.68), lens=22)
    scene.frame_set(285)
    scene["段階"] = "未承認の造形試作。旧版との動画比較用"
    scene["標本フレーム間隔"] = int(step)
    path = OUTPUT / "localized_wave_animated.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
    (OUTPUT / "scene_manifest.json").write_text(json.dumps({"説明":"局所高峰と独立白波の造形試作。物理検証は未実施。", "blend":str(path), "frames":frames, "sweep":sweep.metadata()}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"保存先": str(path), "頂点数":len(wave.data.vertices), "標本数":len(frames)}, ensure_ascii=False))
    return scene


def render_still(camera_name="CAM_立体確認", frame=285, name=None, width=1280):
    scene = bpy.context.scene
    scene.camera = scene.objects[camera_name]
    scene.frame_set(frame)
    scene.render.resolution_x = width
    scene.render.resolution_y = int(width * .625)
    scene.render.filepath = str(OUTPUT / (name or f"{camera_name}_{frame:03d}.png"))
    bpy.ops.render.render(write_still=True)
    return scene.render.filepath


def render_movie(camera_name="CAM_立体確認", width=960, suffix="volume"):
    """30 fps の実時間で立上りから静止までを出力する。速度変更は行わない。"""
    scene = bpy.context.scene
    scene.camera = scene.objects[camera_name]
    scene.frame_start, scene.frame_end, scene.frame_step = 1, 345, 1
    scene.render.fps = 30
    scene.render.resolution_x, scene.render.resolution_y = width, int(width*.625)
    scene.render.image_settings.media_type = "VIDEO"
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    stem = OUTPUT / f"localized_wave_{suffix}_"
    scene.render.filepath = str(stem)
    bpy.ops.render.render(animation=True)
    candidates = list(OUTPUT.glob(stem.name+"*.mp4"))
    if len(candidates) != 1:
        raise RuntimeError("出力動画が一意に特定できません")
    target = OUTPUT / f"localized_wave_{suffix}.mp4"
    candidates[0].replace(target)
    scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"
    scene.frame_set(285)
    return str(target)


if __name__ == "__main__":
    build()
