"""19の60 Hz実形状と30 Hz保持形状を独立に比較する（Houdini/Unity不要）。

跨時刻の頂点番号対応は仮定しない。標本点から相手の全三角形への最短距離を
AABB階層で探索する。結果は標本表面距離であり、厳密Hausdorff距離ではない。
"""
import argparse
import hashlib
import json
import math
import struct
import time
from pathlib import Path

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_reference(path):
    raw = Path(path).read_bytes()
    magic, version, count, rate = struct.unpack_from('<8siii', raw)
    if (magic, version, count, rate) != (b'GW19REF1', 1, 121, 60):
        raise ValueError('正式19の121時刻・60 Hz形式ではありません。')
    offset, samples = 20, []
    for k in range(count):
        start = offset
        index, seconds, points, indices = struct.unpack_from('<ifii', raw, offset)
        offset += 16
        if index != k or abs(seconds-k/rate) > 2e-7 or points < 3 or indices % 3:
            raise ValueError('時刻/個数が不正です。')
        p = np.frombuffer(raw, '<f4', points*3, offset).reshape(-1, 3).copy()
        offset += points*12
        n = np.frombuffer(raw, '<f4', points*3, offset).reshape(-1, 3).copy()
        offset += points*12
        triangles = np.frombuffer(raw, '<i4', indices, offset).reshape(-1, 3).copy()
        offset += indices*4
        if not np.isfinite(p).all() or not np.isfinite(n).all() or triangles.min() < 0 or triangles.max() >= points:
            raise ValueError('非有限値または範囲外indexがあります。')
        samples.append(dict(index=k, time=float(seconds), positions=p.astype(np.float64),
                            triangles=triangles, payload_sha256=hashlib.sha256(raw[start+16:offset]).hexdigest(),
                            p_sha256=hashlib.sha256(p.tobytes()).hexdigest(),
                            topology_sha256=hashlib.sha256(triangles.tobytes()).hexdigest()))
    if offset != len(raw):
        raise ValueError('参照の末尾または試料数が一致しません。')
    return samples, hashlib.sha256(raw).hexdigest(), len(raw)


def pair_distances_squared(points, triangles):
    """各点×三角形の厳密距離。面内投影と3辺への距離の最小値。"""
    q = points[:, None, :]
    a, b, c = (triangles[None, :, i, :] for i in range(3))
    ab, ac, aq = b-a, c-a, q-a
    normal = np.cross(ab, ac)
    nn = np.sum(normal*normal, axis=2)
    d00 = np.sum(ab*ab, axis=2)
    d01 = np.sum(ab*ac, axis=2)
    d11 = np.sum(ac*ac, axis=2)
    d20 = np.sum(aq*ab, axis=2)
    d21 = np.sum(aq*ac, axis=2)
    denom = d00*d11-d01*d01
    safe = np.where(denom > 0, denom, 1.)
    v = (d11*d20-d01*d21)/safe
    w = (d00*d21-d01*d20)/safe
    plane = np.sum(aq*normal, axis=2)**2/np.where(nn > 0, nn, 1.)
    inside = (denom > 0) & (v >= 0) & (w >= 0) & (v+w <= 1)
    answer = np.where(inside, plane, np.inf)
    for start, end in ((a, b), (b, c), (c, a)):
        edge = end-start
        ee = np.sum(edge*edge, axis=2)
        u = np.sum((q-start)*edge, axis=2)/np.where(ee > 0, ee, 1.)
        u = np.clip(u, 0, 1)
        delta = q-(start+u[:, :, None]*edge)
        answer = np.minimum(answer, np.sum(delta*delta, axis=2))
    return np.maximum(answer, 0)


class SurfaceTree:
    """中点分割AABB。距離下限だけで枝刈りし、近傍数で打切らない。"""
    def __init__(self, vertices, indices, leaf_size=32):
        self.triangles = vertices[indices]
        self.nodes = []
        minimum = self.triangles.min(axis=1)
        maximum = self.triangles.max(axis=1)
        centers = (minimum+maximum)*.5

        def build(ids):
            number = len(self.nodes)
            lo, hi = minimum[ids].min(axis=0), maximum[ids].max(axis=0)
            self.nodes.append(None)
            if len(ids) <= leaf_size:
                self.nodes[number] = (lo, hi, -1, -1, ids)
            else:
                axis = int(np.argmax(hi-lo))
                order = ids[np.argsort(centers[ids, axis], kind='stable')]
                cut = len(order)//2
                left, right = build(order[:cut]), build(order[cut:])
                self.nodes[number] = (lo, hi, left, right, None)
            return number
        build(np.arange(len(indices)))

    def distances(self, points):
        best = np.full(len(points), np.inf)
        stack = [(0, np.arange(len(points)))]
        while stack:
            node, ids = stack.pop()
            lo, hi, left, right, triangles = self.nodes[node]
            delta = np.maximum(np.maximum(lo-points[ids], points[ids]-hi), 0)
            ids = ids[np.sum(delta*delta, axis=1) <= best[ids]]
            if not len(ids):
                continue
            if triangles is not None:
                best[ids] = np.minimum(best[ids], pair_distances_squared(points[ids], self.triangles[triangles]).min(axis=1))
            else:
                def lower(child):
                    a, b = self.nodes[child][:2]
                    d = np.maximum(np.maximum(a-points[ids], points[ids]-b), 0)
                    return np.sum(d*d, axis=1).mean()
                first, second = (left, right) if lower(left) <= lower(right) else (right, left)
                stack.append((second, ids))
                stack.append((first, ids))
        if not np.isfinite(best).all():
            raise ValueError('最短距離の未計算点があります。')
        return np.sqrt(best)


def surface_probes(sample, count=256):
    """面積比例の層化標本。外周帯は別集計し、面積統計へ混ぜない。"""
    vertices, ids = sample['positions'], sample['triangles']
    triangles = vertices[ids]
    area = np.linalg.norm(np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0]), axis=1)*.5
    rng = np.random.default_rng(19000+sample['index'])
    selected = np.searchsorted(np.cumsum(area), ((np.arange(count)+rng.random(count))/count)*area.sum())
    u, v = rng.random(count), rng.random(count)
    root = np.sqrt(u)
    probes = (1-root)[:, None]*triangles[selected, 0] + (root*(1-v))[:, None]*triangles[selected, 1] + (root*v)[:, None]*triangles[selected, 2]
    low, high = vertices.min(axis=0), vertices.max(axis=0)
    bands = {}
    for axis, name in enumerate('XYZ'):
        for sign in (-1, 1):
            mask = vertices[:, axis] <= low[axis]+.05*(high[axis]-low[axis]) if sign < 0 else vertices[:, axis] >= high[axis]-.05*(high[axis]-low[axis])
            candidates = vertices[mask]
            candidates = candidates[np.lexsort((candidates[:, 2], candidates[:, 1], candidates[:, 0]))]
            take = np.linspace(0, len(candidates)-1, min(16, len(candidates)), dtype=int)
            bands[('-' if sign < 0 else '+')+name] = candidates[take]
    return probes, bands, dict(bounds_min=low.tolist(), bounds_max=high.tolist(), area_m2=float(area.sum()),
                               points=len(vertices), triangles=len(ids), strictly_zero_area_triangles=int((area == 0).sum()))


def stats(values):
    return dict(count=len(values), mean_m=float(np.mean(values)), rms_m=float(np.sqrt(np.mean(values**2))),
                p50_m=float(np.percentile(values, 50)), p95_m=float(np.percentile(values, 95)), max_m=float(np.max(values)))


def self_test():
    triangle = np.array([[[0., 0, 0], [1., 0, 0], [0., 1, 0]]])
    points = np.array([[.2, .2, 2.], [.7, .7, 0.], [-1., -1., 0.]])
    expected = np.array([4., .08, 2.])
    assert np.allclose(pair_distances_squared(points, triangle).ravel(), expected, atol=1e-12)
    rng = np.random.default_rng(19)
    triangles = rng.normal(size=(120, 3, 3))
    vertices = triangles.reshape(-1, 3)
    tree = SurfaceTree(vertices, np.arange(len(vertices)).reshape(-1, 3), leaf_size=7)
    points = rng.normal(size=(32, 3))*2
    actual = tree.distances(points)
    expected = np.sqrt(pair_distances_squared(points, triangles).min(axis=1))
    assert np.allclose(actual, expected, atol=1e-12)
    return dict(analytic_cases=3, aabb_vs_full_triangle_queries=32, tolerance_m=1e-12, passed=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--cache-index', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    testing = self_test()
    if args.self_test:
        print(json.dumps(testing)); return
    if not all((args.reference, args.cache_index, args.output)):
        parser.error('reference/cache-index/outputが必要です。')
    started = time.monotonic()
    samples, digest, size = read_reference(args.reference)
    index = json.loads(args.cache_index.read_text(encoding='utf8'))
    if len(index['samples']) != 121:
        raise ValueError('正式121時刻のcache indexではありません。')
    for sample, row in zip(samples, index['samples']):
        assert sample['index'] == row['sample60'] and sample['p_sha256'] == row['mesh_P_sha256']
        assert sample['topology_sha256'] == row['mesh_topology_sha256']
        assert abs(row['simulation_seconds']-sample['index']/60) < 1e-6
    records = []
    for k in range(1, 121, 2):
        held, actual = samples[k-1], samples[k]
        a, bands_a, geometry_a = surface_probes(held)
        b, bands_b, geometry_b = surface_probes(actual)
        tree_a = SurfaceTree(held['positions'], held['triangles'])
        tree_b = SurfaceTree(actual['positions'], actual['triangles'])
        ab, ba = tree_b.distances(a), tree_a.distances(b)
        features = {}
        for band in bands_a:
            features[band] = dict(held_to_actual=stats(tree_b.distances(bands_a[band])), actual_to_held=stats(tree_a.distances(bands_b[band])))
        low_delta = np.array(geometry_b['bounds_min'])-geometry_a['bounds_min']
        high_delta = np.array(geometry_b['bounds_max'])-geometry_a['bounds_max']
        records.append(dict(sample60=k, held_sample60=k-1, time_seconds=k/60, held_time_seconds=(k-1)/60,
                            hold_age_seconds=1/60, held_payload_sha256=held['payload_sha256'], actual_payload_sha256=actual['payload_sha256'],
                            held_geometry=geometry_a, actual_geometry=geometry_b, bounds_min_delta_m=low_delta.tolist(),
                            bounds_max_delta_m=high_delta.tolist(), maximum_axis_extreme_change_m=float(np.max(np.abs(np.r_[low_delta, high_delta]))),
                            surface_held_to_actual=stats(ab), surface_actual_to_held=stats(ba), sampled_symmetric=stats(np.r_[ab, ba]), extreme_bands=features))
        print(json.dumps({'pair':len(records), 'sample60':k, 'sampled_symmetric_p95_m':records[-1]['sampled_symmetric']['p95_m'],
                          'elapsed_seconds':round(time.monotonic()-started, 2)}), flush=True)
    common = [dict(sample60=k, sample30=k//2, time_seconds=k/60, payload_sha256=samples[k]['payload_sha256'],
                   equality_basis='same_master_payload_not_separate_export_validation') for k in range(0, 121, 2)]
    report = dict(classification='PC_GEOMETRIC_HOLD_ERROR_NOT_HMD_OR_PHYSICS_PASS', input_reference=str(args.reference.resolve()),
                  reference_sha256=digest, reference_bytes=size, cache_index_sha256=sha(args.cache_index), script_sha256=sha(__file__),
                  numpy_version=np.__version__, self_test=testing, coordinate_system='Houdini Y-up metres; rigid X reflection preserves distances',
                  method_ja='60Hz実odd試料と直前evenの30Hz保持を双方向point-to-triangle距離で比較。頂点番号の跨時刻対応なし。',
                  limitations_ja=['60Hz形状は物理的な真値ではない。', '256個の面積比例標本/方向であり厳密Hausdorff距離ではない。',
                                  '外周各5%帯16点以下の限定指標は波/白波の尖端判定ではない。', '61共通時刻は同じmasterからの参照対応。実30Hz書出ファイルの一致は別検査。',
                                  '再生速度、画素輪郭、深度/影、実HMDの滑らかさをこの幾何解析だけでは検証しない。'],
                  sampling=dict(area_probes_per_direction=256, extreme_band_fraction=.05, extreme_probes_per_band_max=16,
                                output_rate_60=60, held_rate_30=30, duration_seconds=2, odd_comparisons=len(records), common_times=len(common)),
                  summary=dict(max_sampled_surface_distance_m=max(r['sampled_symmetric']['max_m'] for r in records),
                               max_per_pair_p95_m=max(r['sampled_symmetric']['p95_m'] for r in records),
                               max_axis_extreme_change_m=max(r['maximum_axis_extreme_change_m'] for r in records),
                               elapsed_seconds=time.monotonic()-started), common_times=common, odd_comparisons=records)
    if sha(args.reference) != digest:
        raise ValueError('解析中に参照ファイルが変更されました。')
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'completed':str(args.output), 'summary':report['summary']}), flush=True)


if __name__ == '__main__':
    main()
