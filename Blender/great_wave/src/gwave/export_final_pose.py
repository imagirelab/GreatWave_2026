"""アニメーションシーンを編集可能で自己完結した最終形状の .blend に固定する。

波と泡を作成した後、``blend/great_wave_foam.blend`` で実行する::

    tools/run_blender.ps1 src/gwave/export_final_pose.py -Blend blend/great_wave_foam.blend -NoFactoryStartup

完全なアニメーションはスクリプトと PC2 キャッシュから再現できる。
この小さな確認用ファイルには、指定フレームで評価したメッシュを保存し、
外部の点キャッシュに依存しない。画像を同梱するため静止シーンを移動できる。
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
        raise RuntimeError("メッシュキャッシュのモディファイアーを含む生成済みアニメーションシーンを読み込んでください")
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
            raise RuntimeError("%s で想定外のトポロジー変更が発生しました" % name)
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
        raise RuntimeError("書き出したシーンに最終フレームの設定が残っていません")
    for name, expected_count in names.items():
        obj = bpy.data.objects.get(name)
        if obj is None or len(obj.data.vertices) != expected_count:
            raise RuntimeError("再読込後にメッシュ %s が見つからないか、変更されています" % name)
        if any(mod.type == "MESH_CACHE" for mod in obj.modifiers):
            raise RuntimeError("書き出し結果が点キャッシュ %s に依存したままです" % name)
    missing = [image.name for image in bpy.data.images
               if image.source == "FILE" and image.packed_file is None]
    if missing:
        raise RuntimeError("同梱されていない外部画像: %s" % ", ".join(missing))
    return os.path.getsize(out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", type=int, default=None)
    ap.add_argument("--out", default="deliverables/great_wave_final_pose.blend")
    ap.add_argument("--hide-paper", action="store_true", help="紙の参照面を隠し、遮りのない3D確認視点にする")
    args = bootstrap.parse_args(ap)
    bootstrap.set_log_prefix("GW_EXPORT")
    frame = int(args.frame or wm.load_wave_params()["n_frames"])
    out_path = paths.project_path(args.out)
    counts = export(out_path, frame, args.hide_paper)
    size = verify_reopen(out_path, frame, counts)
    bootstrap.log("検証済み: %s (%0.1f MB)、固定したメッシュ %s" %
                  (out_path, size / 1e6, counts))
    bootstrap.finish(True, "export_final_pose")


if __name__ == "__main__":
    main()
