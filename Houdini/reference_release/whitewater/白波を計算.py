# -*- coding: utf-8 -*-
"""保存済み FLIP 場から白波を独立計算する。元の液体計算は変更しない。"""
import argparse
import ctypes
import json
import os
import time
from pathlib import Path
import hou
import numpy as np

src = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description='実際の FLIP 場から独立した白波粒子を計算する。')
parser.add_argument('--last-frame', type=int, default=12)
parser.add_argument('--fluid-dir', type=Path, default=src.parent.parent / 'results' / 'reference_release' / '本計算01')
parser.add_argument('--output-dir', type=Path, default=src.parent.parent / 'results' / 'reference_release' / 'whitewater' / '試行01')
args = parser.parse_args()
cfg = json.loads((src / '条件.json').read_text(encoding='utf-8'))
assert cfg['start_frame'] <= args.last_frame <= cfg['last_frame']
fluid_dir = args.fluid_dir.resolve()
out = args.output_dir.resolve()
if (out / '計測.json').exists():
    raise RuntimeError('既存の白波計算は上書きしない。')
for folder in ['particles', 'mesh', 'emit']:
    (out / folder).mkdir(parents=True, exist_ok=True)
main = json.loads((fluid_dir / '計測.json').read_text(encoding='utf-8'))
fluid_cfg = main['条件']
hou.setUpdateMode(hou.updateMode.Manual)
hou.setFps(cfg['fps'])
hou.setFrame(cfg['start_frame'])
hou.playbar.setFrameRange(1, cfg['last_frame'])
hou.hipFile.setName(str(src / '白波の独立計算.hiplc'))


def node(parent, kind, name, note):
    n = parent.createNode(kind, name)
    n.setComment(note)
    n.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    return n


def memory_mib():
    class PM(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong),
                    ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]
    pm = PM()
    pm.cb = ctypes.sizeof(pm)
    ctypes.windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PM), ctypes.c_ulong]
    if not ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(pm), pm.cb):
        raise RuntimeError('メモリ採取に失敗した。')
    return pm.WorkingSetSize / 1024**2


geo = node(hou.node('/obj'), 'geo', 'whitewater', '元の FLIP を読み、白波を別に時間発展させる。')
for c in geo.children():
    c.destroy()
file = node(geo, 'file', 'fluid_fields', '第 2 フレーム以降の実際の surface と vel.x/y/z。')
relative = Path(os.path.relpath(fluid_dir, src)).as_posix()
file.parm('file').set('$HIP/' + relative + '/fields/fields_$F4.bgeo.sc')
fields = node(geo, 'python', 'select_liquid_fields', '液体の surface と速度だけを選ぶ。DOP の衝突場を液体 SDF と混同しない。')
fields.setInput(0, file)
fields.parm('python').set("import hou\ng=hou.pwd().geometry()\ng.deletePrims([p for p in g.prims() if p.stringAttribValue('name') not in ('surface','vel.x','vel.y','vel.z')])")
container = node(geo, 'box', 'container', '元 FLIP と同じ計算領域。追加の固体衝突模型はない。')
container.setParms({'sizex': fluid_cfg['length_m'], 'sizey': fluid_cfg['domain_height_m'],
                    'sizez': fluid_cfg['width_m'], 'ty': fluid_cfg['domain_height_m'] / 2})
source = node(geo, 'whitewatersource::3.0', 'whitewater_source', '曲率・速度・深度から放出体積場を作る。可視化用の第 4 出力は計算粒子に使わない。')
source.setInput(0, fields)
source.setInput(1, container)
source.setParms({'startframe': cfg['start_frame'], 'usevoxelsize': 1, 'voxelsize': cfg['emission_voxel_m'],
                 'enableactivate': 0, 'limitbydepth': 1, 'depthrangemin': cfg['depth_min_m'],
                 'depthrangemax': cfg['depth_max_m'], 'speedrangemin': cfg['speed_min_m_s'],
                 'speedrangemax': cfg['speed_max_m_s'], 'enablecurvature': 1,
                 'curvaturerangemin': cfg['curvature_min_m_inv'], 'curvaturerangemax': cfg['curvature_max_m_inv'],
                 'maxvelangle': cfg['velocity_angle_deg'], 'enableacceleration': 0, 'enablevorticity': 0,
                 'enablepressure': 0, 'enablesplash': 0, 'enabledeformation': 0, 'outputvolumes': 1,
                 'modifyvolumes': 0, 'wwscale': cfg['whitewater_scale_m']})
solver = node(geo, 'whitewatersolver', 'whitewater_solver', '独立した白波ソルバ。ID、年齢、泡・表面泡・飛沫の状態属性を保存する。')
for i in range(3):
    solver.setInput(i, source, i)
solver.setParms({'startframe': cfg['start_frame'], 'scale': cfg['whitewater_scale_m'],
                 'voxelsize': cfg['density_voxel_m'], 'sdfactivate': 0, 'substep': cfg['substeps'],
                 'cachemaxsize': 1500, 'addstatevars': 1, 'adddensityvar': 1,
                 'emissionamount': cfg['emission_amount'], 'lifespan': cfg['lifespan_s'],
                 'seed': cfg['seed'], 'gravityy': -fluid_cfg['gravity_m_s2'],
                 'enablerepellants': 0, 'useopencl': 0, 'addnoise': 0, 'showcollision': 0})
post = node(geo, 'whitewaterpostprocess', 'whitewater_mesh', '計算済みの白波粒子を独立メッシュに変換する。爪の造形完成を意味しない。')
for i in range(3):
    post.setInput(i, solver, i)
post.setParms({'output': 2, 'voxelsize': cfg['mesh_voxel_m'], 'adaptivity': .02,
               'density_byage': 0, 'density_bydepth': 0, 'clipcontainer': 1})
post.setDisplayFlag(True)
post.setRenderFlag(True)
geo.layoutChildren()
hou.hipFile.save()
hou.setUpdateMode(hou.updateMode.AutoUpdate)
rows = []
previous = {}
start = time.perf_counter()
for frame in range(cfg['start_frame'], args.last_frame + 1):
    t = time.perf_counter()
    hou.setFrame(frame)
    solver.cook(force=True)
    g = solver.geometry()
    if solver.errors():
        raise RuntimeError(str(solver.errors()))
    names = [a.name() for a in g.pointAttribs()]
    count = len(g.points())
    if count > cfg['max_particles']:
        raise RuntimeError('白波の粒子数上限を超えた。')
    p = np.asarray(g.pointFloatAttribValues('P')).reshape(-1, 3)
    ids = np.asarray(g.pointIntAttribValues('id'), dtype=np.int64) if 'id' in names else np.zeros(0, dtype=np.int64)
    age = np.asarray(g.pointFloatAttribValues('age')) if 'age' in names else np.zeros(0)
    if count and (len(ids) != count or len(age) != count or not np.isfinite(p).all()):
        raise RuntimeError('ID・年齢・有限値の確認に失敗した。')
    current = {int(i): (p[j], age[j]) for j, i in enumerate(ids)}
    common = sorted(set(current) & set(previous))[:128]
    moved = [float(np.linalg.norm(current[i][0] - previous[i][0])) for i in common]
    aged = [float(current[i][1] - previous[i][1]) for i in common]
    g.saveToFile(str(out / 'particles' / f'whitewater_{frame:04d}.bgeo.sc'))
    source.cook(force=True)
    source.geometry().saveToFile(str(out / 'emit' / f'source_{frame:04d}.bgeo.sc'))
    post.cook(force=True)
    mesh = post.geometry()
    if post.errors():
        raise RuntimeError(str(post.errors()))
    mesh.saveToFile(str(out / 'mesh' / f'whitewater_{frame:04d}.bgeo.sc'))
    row = {'フレーム': frame, '主計算からの時刻_s': (frame - 1) / cfg['fps'], '粒子数': count,
           '新生ID数': len(set(current) - set(previous)), '消失ID数': len(set(previous) - set(current)),
           '点属性': names, '最大年齢_s': float(age.max()) if count else None,
           '継続IDの確認数': len(common), '継続IDの平均移動_m': float(np.mean(moved)) if moved else None,
           '継続IDの平均年齢増分_s': float(np.mean(aged)) if aged else None,
           '状態属性の最小最大': {n: [min(g.pointFloatAttribValues(n)), max(g.pointFloatAttribValues(n))] for n in ['bubble', 'foam', 'spray'] if count and n in names},
           'メッシュ頂点数': len(mesh.points()), 'メッシュプリミティブ数': len(mesh.prims()),
           '処理時間_s': time.perf_counter() - t, '使用メモリ_MiB': memory_mib()}
    rows.append(row)
    (out / '計測.json').write_text(json.dumps({'条件': cfg, '元FLIP': relative,
                                               '注意': '公式ソルバの白波。放出閾値はモデルの設定であり、空気巻込み量の実測再現ではない。', 'フレーム別': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(row, ensure_ascii=False), flush=True)
    previous = current
    if memory_mib() > cfg['max_memory_MiB'] or time.perf_counter() - start > cfg['max_runtime_s']:
        raise RuntimeError('白波の計算資源上限に達した。')
print('白波計算完了', flush=True)
