# -*- coding: utf-8 -*-
"""Steam 版 Indie の 3 フレーム Alembic 入出力検証。流体解析ではない。"""
import hou
import argparse
import json
import math
from pathlib import Path

parser = argparse.ArgumentParser(description="3 フレームの Alembic 入出力を再現する。流体解析ではない。")
parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[2] / "results" / "interop_probe_reproduction", help="新しい結果の保存先。既存の制作元や Alembic は上書きしない。")
args = parser.parse_args()
base = args.output_dir.resolve()
hip_path = base / "正弦波面_入出力検証.hiplc"
abc_path = base / "正弦波面_3フレーム.abc"
for existing in (hip_path, abc_path):
    if existing.exists():
        raise RuntimeError("既存の検証結果を上書きしません: " + str(existing))
base.mkdir(parents=True, exist_ok=True)
hou.setUpdateMode(hou.updateMode.AutoUpdate)
hou.setFps(24)
hou.hipFile.setName(str(hip_path))
hou.playbar.setFrameRange(1, 3)
hou.playbar.setPlaybackRange(1, 3)
name_fallbacks = []

def make(parent, kind, machine_name, japanese_name, comment):
    node = parent.createNode(kind, node_name=machine_name)
    try:
        node.setName(japanese_name, unique_name=True)
    except hou.OperationFailed:
        name_fallbacks.append({"識別名": node.path(), "表示用説明": japanese_name})
    node.setComment(japanese_name + "\n" + comment)
    node.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    return node

def parameter(node, names, label):
    for name in names:
        found = node.parm(name)
        if found is not None:
            return found
    for found in node.parms():
        if found.parmTemplate().label().replace(" ", "").lower() == label.replace(" ", "").lower():
            return found
    raise RuntimeError("必要なパラメータがありません: " + node.path() + " / " + label)

def positions(node):
    node.cook(force=True)
    geo = node.geometry()
    return [list(point.position()) for point in geo.points()]

obj = hou.node('/obj')
source = make(obj, 'geo', 'sine_probe', '正弦波面の検証', '幾何変形のみ。FLIP、水の圧力、浮力は計算しない。')
for child in source.children():
    child.destroy()
grid = make(source, 'grid', 'grid', '検証用格子', '2 m × 2 m、9 × 9 点の小規模メッシュ。')
grid.setParms({'rows': 9, 'cols': 9, 'sizex': 2.0, 'sizey': 2.0})
wave = make(source, 'attribwrangle', 'sine_deform', '正弦変形', '3 フレームの頂点変化で Alembic の時間サンプルを確認する。')
wave.setInput(0, grid)
wave.parm('snippet').set('// 流体計算ではなく、入出力検証用の正弦変形。\n@P.y = 0.08 * sin(3.0 * @P.x + @Frame * 0.6);')
output = make(source, 'null', 'OUT_SURFACE', '出力波面', 'このノードだけを Alembic に書き出す。')
output.setInput(0, wave)
output.setDisplayFlag(True)
output.setRenderFlag(True)
writer = make(hou.node('/out'), 'alembic', 'export_alembic', 'Alembic書き出し', 'フレーム 1、2、3。既存の大規模流体シーンは使用しない。')
parameter(writer, ['filename'], 'Alembic File').set('$HIP/' + abc_path.name)
parameter(writer, ['use_sop_path', 'usesoppath'], 'Use SOP Path').set(1)
parameter(writer, ['sop_path', 'soppath'], 'SOP Path').set(output.path())
writer.parm('trange').set(1)
writer.parmTuple('f').set((1, 3, 1))
if writer.parm('initsim') is not None:
    writer.parm('initsim').set(0)
source_frames = {}
for frame in (1, 2, 3):
    hou.setFrame(frame)
    source_frames[frame] = positions(output)
    assert len(source_frames[frame]) == 81, "検証用の 81 点を生成できませんでした。"
writer.render(frame_range=(1, 3), verbose=False)

loaded = make(obj, 'geo', 'readback_probe', 'Alembic再読込', '出力ファイルを再読込し、元の頂点座標と照合する。')
for child in loaded.children():
    child.destroy()
reader = make(loaded, 'alembic', 'read_alembic', '書出結果の読込', '各フレームを Houdini の通常ジオメトリとして取得する。')
parameter(reader, ['fileName', 'filename'], 'File name').set('$HIP/' + abc_path.name)
load = parameter(reader, ['loadmode'], 'Load As')
labels = load.menuLabels()
selected = next(i for i, label in enumerate(labels) if 'houdini' in label.lower() and 'geometry' in label.lower())
load.set(selected)
if reader.parm('polysoup') is not None:
    reader.parm('polysoup').set(0)
reader.setDisplayFlag(True)
reader.setRenderFlag(True)
read_frames = {}
checks = []
for frame in (1, 2, 3):
    hou.setFrame(frame)
    read_frames[frame] = positions(reader)
    actual = read_frames[frame]
    expected = source_frames[frame]
    if len(actual) != len(expected):
        raise RuntimeError('再読込した点数が一致しません。')
    max_error = max(math.dist(a, b) for a, b in zip(actual, expected))
    checks.append({'フレーム': frame, '点数': len(actual), '面数': len(reader.geometry().prims()), '最大座標誤差_m': max_error, '高さ範囲_m': [min(p[1] for p in actual), max(p[1] for p in actual)]})
changes = [{'区間': [a, b], '最大頂点変位_m': max(math.dist(x, y) for x, y in zip(read_frames[a], read_frames[b]))} for a, b in [(1, 2), (2, 3)]]
assert all(c['最大座標誤差_m'] < 1e-6 for c in checks)
assert all(c['最大頂点変位_m'] > 1e-4 for c in changes)
source.layoutChildren()
loaded.layoutChildren()
obj.layoutChildren()
hou.node('/out').layoutChildren()
hou.setFrame(1)
hou.hipFile.save(str(hip_path))
result = {'目的': 'Steam 版 Indie の Alembic 書出しと再読込の小規模検証。流体物理と Unity 動作は未検証。', 'Houdiniバージョン': hou.applicationVersionString(), 'ライセンス種別': str(hou.licenseCategory()), 'フレーム': [1, 2, 3], 'FPS': hou.fps(), '制作元': hip_path.name, 'Alembic': abc_path.name, 'パスの基準': 'この JSON ファイルのあるディレクトリ。', 'Alembic容量_byte': abc_path.stat().st_size, '制作元容量_byte': hip_path.stat().st_size, '書出ノード種別': writer.type().name(), '読込ノード種別': reader.type().name(), 'フレーム別照合': checks, '読込後の動き': changes, '識別名の代替': name_fallbacks, 'ノード': [{'パス': n.path(), '種別': n.type().name(), '説明': n.comment()} for n in [source, grid, wave, output, writer, loaded, reader]]}
(base / '検証結果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
(base / '検証説明.md').write_text('# Alembic 入出力の小規模検証\n\nSteam 版 Houdini Indie で 9 × 9 点の正弦変形メッシュを 3 フレーム書き出し、Alembic SOP で再読込した。\n\nこれは流体シミュレーションではない。FLIP の物理精度、旧シーンの健全性、Unity での再生、HMD の性能は未検証。\n\nフレーム別の点数、最大座標誤差、隣接フレームの実変位は「検証結果.json」を参照する。ノード識別子の日本語が許可されない場合は ASCII 識別子を使い、表示コメントを日本語にした。\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
