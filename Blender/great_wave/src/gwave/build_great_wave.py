"""動く Great Wave を Blender シーンに作成し、.blend を保存する。

    tools/run_blender.ps1 src/gwave/build_great_wave.py            # .blend と wave_params.json に従う点キャッシュを出力
    テスト: --build-script src/gwave/build_great_wave.py           # build(scene) を呼び出す

全形状は wave_params.json と target/base_contour.json から生成する。格子は (n_u x n_v) で固定し、
UV は最終断面の弧長と峰方向の位置、頂点グループは 'crest_rim' とする。各フレームの頂点は PC2
点キャッシュに保存し、Mesh Cache モディファイアーが読む。状態の定義はスクリプトと設定にあり、
.blend はキャッシュを参照する。"""
import math
import os
import struct
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
import numpy as np

from gw import bootstrap, paths
from gw import profile_metrics as pm
from gwave import profile_motion as wm

OBJECT_NAME = "GreatWave"


def _write_pc2_header(fh, n_verts, n_samples):
    fh.write(struct.pack("<12siiffi", b"POINTCACHE2\0", 1, int(n_verts), 0.0, 1.0, int(n_samples)))


def compute_cache(WP, cache_path, log=True):
    """PC2 キャッシュを書き出す。戻り値は運動、座標、格子数、初期頂点、各フレームの断面を含む辞書。"""
    H = float(paths.param("WAVE_HEIGHT_M")) if WP.get("H") is None else float(WP["H"])
    mo = wm.WaveMotion(WP)
    regress = str(WP.get("flank_mode", "regress")) == "regress"
    y, d = wm.v_layout_regress(WP) if regress else wm.v_layout(WP)
    n_u, n_v = mo.n_u, y.size
    n_frames = mo.n_frames
    paths.assert_writable(cache_path)
    paths.ensure_parent(cache_path)
    profiles = np.empty((n_frames, n_u, 2))
    first = None
    prev = None
    steps = []
    state = {}
    with open(cache_path, "wb") as fh:
        _write_pc2_header(fh, n_u * n_v, n_frames)
        for f in range(1, n_frames + 1):
            V, p, _m = wm.frame_vertices(mo, f, y, d, H, state)
            if f == n_frames:                                   # 最終形状では両端を静水面に正確に合わせる。
                V[:, 2] = np.where(np.abs(V[:, 2]) < 1e-9, 0.0, V[:, 2])
            if first is None:
                first = V.copy()
            else:
                steps.append((float(np.sqrt(((V - prev) ** 2).sum(1)).max()) / H, f))
            prev = V
            profiles[f - 1] = p
            fh.write(np.ascontiguousarray(V, dtype="<f4").tobytes())
            if log and (f % 50 == 0 or f == n_frames):
                st = state.get("stats")
                extra = ""
                if st:
                    extra = "  側面の制限: 投影した頂点 %d、最大移動 %.3f H、背面の最大押し戻し %.3f H" % st[-1][1:]
                bootstrap.log("キャッシュ: フレーム %d / %d%s" % (f, n_frames, extra))
    if log and steps:
        worst = sorted(steps, reverse=True)[:3]
        bootstrap.log("フレーム間の最大頂点変位 [H]: " + ", ".join("%.4f @f%d" % w for w in worst))
    return {"motion": mo, "y": y, "d": d, "n_u": n_u, "n_v": n_v, "first": first, "profiles": profiles, "H": H}


def build(scene=None, cache_path=None, params_path=None, with_scene_extras=False):
    """テスト用の生成契約。`scene` に 'GreatWave' を作成して返す。"""
    import bpy
    scene = scene or bpy.context.scene
    WP = wm.load_wave_params(params_path)
    cache_path = paths.norm(cache_path or WP["cache_path"])
    C = compute_cache(WP, cache_path)
    mo, n_u, n_v, H = C["motion"], C["n_u"], C["n_v"], C["H"]

    me = bpy.data.meshes.new(OBJECT_NAME)
    faces = wm.grid_faces(n_u, n_v)
    me.from_pydata(C["first"].tolist(), [], faces.tolist())
    me.update(calc_edges=True)

    # UV: U は最終断面の弧長（0 が背面端、1 が前面端）、V は峰方向の位置。
    S = mo.S1 / mo.S1[-1]
    yv = (C["y"] - C["y"][0]) / (C["y"][-1] - C["y"][0])
    loop_vi = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", loop_vi)
    uv = np.stack([S[loop_vi % n_u], yv[loop_vi // n_u]], axis=1).astype(np.float32)
    me.uv_layers.new(name="UVMap").data.foreach_set("uv", uv.ravel())
    try:
        me.shade_smooth()
    except Exception:
        for poly in me.polygons:
            poly.use_smooth = True

    obj = bpy.data.objects.new(OBJECT_NAME, me)
    scene.collection.objects.link(obj)

    # 頂点グループ crest_rim: 全行において波頭の先端から弧長が高さの2%以内の U 列。
    ru = np.nonzero(np.abs(mo.S1 - mo.S1[mo.i_t]) <= 0.02)[0]
    vg = obj.vertex_groups.new(name="crest_rim")
    ids = (np.arange(n_v)[:, None] * n_u + ru[None, :]).ravel()
    vg.add([int(i) for i in ids], 1.0, "REPLACE")

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
    md.factor = 1.0

    scene.render.fps = int(WP["fps"])
    scene.frame_start = 1
    scene.frame_end = int(WP["n_frames"]) + int(WP["hold_frames"])
    scene.frame_set(int(WP["n_frames"]))
    obj["gw_n_u"] = int(n_u)
    obj["gw_n_v"] = int(n_v)
    obj["gw_final_frame"] = int(WP["n_frames"])
    build.last = C
    return obj


def _look_at(obj, target):
    from mathutils import Vector
    v = Vector(target) - obj.location
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = v.to_track_quat("-Z", "Y")


def add_scene_extras(scene, obj, WP, H):
    """カメラ、参照用の海、背景に置く原画、画面表示色を追加する。納品用メッシュには含めない。"""
    import bpy
    from gw import silhouette
    cam_print, _rect, chk = silhouette.setup_cam_print(scene, H)
    bootstrap.log("CAM_print の構図誤差 %.4f px" % chk.get("max_err_px", float("nan")))
    try:
        img = bpy.data.images.load(paths.painting_path(), check_existing=True)
        cam_print.data.show_background_images = True
        bg = cam_print.data.background_images.new()
        bg.image = img
        bg.alpha = 0.5
        bg.display_depth = "FRONT"
        bg.frame_method = "STRETCH"
    except Exception as ex:
        bootstrap.log("背景画像を設定できませんでした: %r" % (ex,))

    def cam(name, loc, target, lens=35.0):
        cd = bpy.data.cameras.new(name)
        cd.lens = lens
        cd.clip_end = 5000.0
        co = bpy.data.objects.new(name, cd)
        scene.collection.objects.link(co)
        co.location = loc
        _look_at(co, target)
        return co

    cam("CAM_view34", (3.6 * H, -5.4 * H, 1.9 * H), (-0.7 * H, 0.0, 0.25 * H), 35.0)
    cam("CAM_front", (5.5 * H, -1.2 * H, 0.55 * H), (0.0, 0.0, 0.45 * H), 35.0)
    cam("CAM_boat", (0.75 * H, -0.2 * H, 0.09 * H), (0.1 * H, 0.0, 0.85 * H), 18.0)

    sea = bpy.data.meshes.new("Sea_ref")
    sx, sy = 30.0 * H, 30.0 * H
    sea.from_pydata([(-sx, -sy, -0.03), (sx, -sy, -0.03), (sx, sy, -0.03), (-sx, sy, -0.03)], [], [(0, 1, 2, 3)])
    so = bpy.data.objects.new("Sea_ref", sea)
    scene.collection.objects.link(so)
    so.color = (0.52, 0.68, 0.76, 1.0)            # 波と同色にし、参照面が海の一部に見えるようにする。
    so.hide_select = True
    obj.color = (0.52, 0.68, 0.76, 1.0)

    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), 0.0, math.radians(-35))

    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "OBJECT"
    sh.show_cavity = True
    sh.show_object_outline = False
    try:
        scene.world = scene.world or bpy.data.worlds.new("World")
        scene.world.color = (0.80, 0.74, 0.62)
    except Exception:
        pass
    scene.camera = bpy.data.objects["CAM_view34"]


def main():
    import bpy
    bootstrap.set_log_prefix("GW")
    bootstrap.reset_scene()
    scene = bpy.context.scene
    WP = wm.load_wave_params()
    with bootstrap.Timer("波を生成"):
        obj = build(scene)
    C = build.last
    add_scene_extras(scene, obj, WP, C["H"])

    out_dir = paths.ensure_dir(os.path.join(wm.PROJECT, "results", "wave_build"))
    np.savez_compressed(os.path.join(out_dir, "section_profiles_H.npz"), profiles=C["profiles"], y_H=C["y"], taper_d=C["d"])

    blend = paths.norm(WP["blend_path"])
    paths.ensure_parent(blend)
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    md = obj.modifiers["PointCache"]
    md.filepath = bpy.path.relpath(paths.norm(WP["cache_path"]))
    bpy.ops.wm.save_mainfile()
    bootstrap.log("頂点数 %d (n_u %d x n_v %d)、面数 %d" % (len(obj.data.vertices), C["n_u"], C["n_v"], len(obj.data.polygons)))
    bootstrap.log("キャッシュ %s (%.1f MB)" % (WP["cache_path"], os.path.getsize(paths.norm(WP["cache_path"])) / 1e6))
    bootstrap.log("Blender ファイル %s" % blend)

    # 妥当性確認: 評価済み最終フレームの中央行が最終断面と一致する。
    scene.frame_set(int(WP["n_frames"]))
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    co = np.empty(len(ev.data.vertices) * 3, np.float32)
    ev.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    mid = C["n_v"] // 2
    row = co[mid * C["n_u"]:(mid + 1) * C["n_u"]]
    q = C["motion"].q * C["H"]
    err = float(np.max(np.hypot(row[:, 0] - q[:, 0], row[:, 2] - q[:, 1])))
    bootstrap.log("評価済み最終フレームの中央行と最終断面の最大誤差: %.6f m" % err)
    bootstrap.finish(err < 1e-3, "build_great_wave")


if __name__ == "__main__":
    main()
