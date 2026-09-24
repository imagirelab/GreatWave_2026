# -*- coding: utf-8 -*-
"""保存済み粒子だけを読み、初期の唇と池水の近接を測る。再計算しない。"""
import argparse
import json
from pathlib import Path
import hou
import numpy as np

try:
    from scipy.spatial import cKDTree
except ImportError:
    cKDTree = None

parser = argparse.ArgumentParser(description='粒子の近接と側壁への接近を計測する。接触の確定には映像も使う。')
parser.add_argument('--cache-dir', type=Path, default=Path(__file__).resolve().parent.parent / 'results' / 'reference_release' / '本計算01')
args = parser.parse_args()
base = args.cache_dir.resolve()
source = json.loads((base / '計測.json').read_text(encoding='utf-8'))
cfg = source['条件']
last = source['フレーム別'][-1]['フレーム']
lip_ids = np.asarray(source['フレーム別'][0]['追跡する唇の粒子ID'], dtype=np.int64)
sep = cfg['particle_separation_m']
thresholds = [sep, 2 * sep, 2 * sep * 1.2]
first = [None] * len(thresholds)
side_first = None
downstream_first = None
upstream_first = None
rows = []
pool_ids = None

for frame in range(1, last + 1):
    g = hou.Geometry()
    g.loadFromFile(str(base / 'particles' / f'water_{frame:04d}.bgeo.sc'))
    p = np.asarray(g.pointFloatAttribValues('P')).reshape(-1, 3)
    ids = np.asarray(g.pointIntAttribValues('id'), dtype=np.int64)
    if pool_ids is None:
        pool_ids = ids[p[:, 1] <= cfg['still_depth_m']]
    lip = p[np.isin(ids, lip_ids)]
    pool = p[np.isin(ids, pool_ids)]
    if len(lip) != len(lip_ids) or len(pool) != len(pool_ids):
        raise RuntimeError('追跡中の粒子 ID が不足している。')
    if cKDTree is not None:
        distance, nearest = cKDTree(pool).query(lip, k=1)
    else:
        nearest = np.asarray([np.einsum('ij,ij->i', pool - q, pool - q).argmin() for q in lip])
        distance = np.linalg.norm(lip - pool[nearest], axis=1)
    index = int(distance.argmin())
    for i, limit in enumerate(thresholds):
        if first[i] is None and distance.min() <= limit:
            first[i] = frame
    high = p[:, 1] > cfg['still_depth_m'] + .15
    side = high & (np.abs(p[:, 2]) > cfg['width_m'] / 2 - .4)
    downstream = high & (p[:, 0] > cfg['length_m'] / 2 - .4)
    upstream = high & (p[:, 0] < -cfg['length_m'] / 2 + .4)
    if side.any() and side_first is None:
        side_first = frame
    if downstream.any() and downstream_first is None:
        downstream_first = frame
    if upstream.any() and upstream_first is None:
        upstream_first = frame
    rows.append({'フレーム': frame, '時刻_s': (frame - 1) / cfg['fps'],
                 '唇と初期池水の粒子中心間_最小距離_m': float(distance.min()),
                 '唇の各粒子から初期池水への最近距離_中央値_m': float(np.median(distance)),
                 '最近点対_唇_m': lip[index].tolist(), '最近点対_池水_m': pool[nearest[index]].tolist(),
                 '距離しきい値以下の唇粒子数': [int((distance <= t).sum()) for t in thresholds],
                 '側壁付近の高水位粒子数': int(side.sum()), '下流壁付近の高水位粒子数': int(downstream.sum()),
                 '上流壁付近の高水位粒子数': int(upstream.sum())})

report = {'説明': '初期の厚い唇 32 粒子を ID で追跡し、初期 Y が静水位以下だった池水粒子群までの距離を測る。',
          '唇の追跡粒子数': len(lip_ids), '池水の追跡粒子数': len(pool_ids),
          '距離しきい値_m': thresholds, 'しきい値到達の初回フレーム': first,
          '側壁への高水位接近_初回フレーム': side_first,
          '下流壁への高水位接近_初回フレーム': downstream_first,
          '上流壁への高水位接近_初回フレーム': upstream_first,
          '制限': '中心間距離は離散的な接水候補。全水面の最初の接触や連続表面の正確な接触時刻を確定しない。32 粒子より先に別の唇部分が接水する可能性がある。境界フラグも反射の発生時刻そのものではない。',
          'フレーム別': rows}
path = base / '接水候補の計測.json'
path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k != 'フレーム別'}, ensure_ascii=False), flush=True)
