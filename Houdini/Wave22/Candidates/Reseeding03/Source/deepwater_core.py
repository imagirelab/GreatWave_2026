"""固定した深水点のSDF・粒子支持を照合する純関数。Houdiniは呼ばない。"""
import hashlib
import json
import math
import time
from collections import defaultdict


def fixed_points():
    """整数cmから生成し、浮動小数の累積加算を避ける。順序はx,y,z。"""
    return [(x / 100, y / 100, z / 100)
            for x in range(6, 595, 6) for y in range(-54, -11, 6)
            for z in range(-24, 25, 6)]


def digest(value):
    return hashlib.sha256(json.dumps(value, separators=(',', ':'),
                                    allow_nan=False).encode('utf8')).hexdigest()


def inside(point, bounds):
    # 場の外でsampleが0を返しても、水面や乾燥とは判定しない。
    return all(math.isfinite(x) and lo < x < hi
               for x, lo, hi in zip(point, bounds['min'], bounds['max']))


def squared_distance(a, b):
    return sum((x-y)**2 for x, y in zip(a, b))


class ParticleSupport:
    """半径と同じ辺長のhash。支持個数と全粒子への正確な最近距離を返す。"""
    def __init__(self, positions, radius=.08):
        if not math.isfinite(radius) or radius <= 0:
            raise ValueError('支持半径が無効')
        self.radius = radius
        self.radius2 = radius * radius
        self.cells = defaultdict(list)
        self.count = 0
        self.fallback_queries = 0
        for p in positions:
            if len(p) != 3 or not all(math.isfinite(x) for x in p):
                raise ValueError('粒子位置が非有限または3次元でない')
            self.cells[self.cell(p)].append(tuple(p))
            self.count += 1
        if not self.count:
            raise ValueError('実粒子が空')

    def cell(self, p):
        return tuple(math.floor(x / self.radius) for x in p)

    def query(self, point):
        if len(point) != 3 or not all(math.isfinite(x) for x in point):
            raise ValueError('照会点が無効')
        center = self.cell(point)
        best = math.inf
        count = 0
        visited = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    key = (center[0]+dx, center[1]+dy, center[2]+dz)
                    visited.add(key)
                    for p in self.cells.get(key, ()):
                        d2 = squared_distance(point, p)
                        best = min(best, d2)
                        count += d2 <= self.radius2
        if not count:
            # 支持0でも距離をnullや半径へ丸めない。cell AABBの下界で枝刈りする。
            self.fallback_queries += 1
            candidates = []
            for key in self.cells:
                if key in visited:
                    continue
                lower2 = 0.
                for i in range(3):
                    lo, hi = key[i]*self.radius, (key[i]+1)*self.radius
                    lower2 += max(lo-point[i], 0., point[i]-hi)**2
                if lower2 < best:
                    candidates.append((lower2, key))
            for lower2, key in sorted(candidates):
                if lower2 >= best:
                    break
                for p in self.cells[key]:
                    best = min(best, squared_distance(point, p))
        return {'count_within_radius': int(count),
                'nearest_particle_distance_m': math.sqrt(best)}


def distribution(values):
    ordered = sorted(values)
    if not ordered:
        return None
    return {'min': ordered[0], 'median': ordered[len(ordered)//2],
            'p95': ordered[math.ceil(.95*len(ordered))-1], 'max': ordered[-1],
            'mean': sum(ordered)/len(ordered)}


def compare_initial_pair(reference, candidate):
    """実保存初態の厳密配対。差を許容範囲へ丸めて一致扱いにしない。"""
    keys = ('particle_count', 'ID_unique', 'sorted_ID_P_sha256', 'sorted_ID_v_sha256',
            'sorted_ID_pscale_sha256', 'pscale_min_max_m', 'surface_pressure_initial_fields')
    missing = [key for key in keys if key not in reference or key not in candidate]
    if missing:
        raise ValueError('初態記録に必須項目がない: '+','.join(missing))
    differences = [key for key in keys if reference[key] != candidate[key]]
    return {'strict_pair_matched': not differences and reference['ID_unique'] is True,
            'different_fields': differences,
            'meaning_ja': '差があれば初態とreseedの複合変更として停止し、源を調整して一致へ誘導しない。'}


def compare_coverage(reference_rows, candidate_rows):
    """共有警報と各側だけの警報を分ける。距離/個数へ後付け閾値を設けない。"""
    if len(reference_rows) != len(candidate_rows):
        raise ValueError('照会点数が異なる')
    groups = {'shared_baseline_and_off': [], 'baseline_only': [], 'off_only': []}
    for a, b in zip(reference_rows, candidate_rows):
        if a['point_index'] != b['point_index'] or a['xyz_m'] != b['xyz_m']:
            raise ValueError('固定照会座標が一致しない')
        if 'invalid_field' in (a['category'], b['category']):
            raise ValueError('無効fieldを被覆比較へ混ぜない')
        left = a['category'] != 'negative_with_support'
        right = b['category'] != 'negative_with_support'
        key = 'shared_baseline_and_off' if left and right else 'baseline_only' if left else 'off_only' if right else None
        if key:
            groups[key].append(a['point_index'])
    return groups


def inspect_points(sample_phi, bounds, positions, radius=.08, points=None,
                   maximum_seconds=90., clock=time.monotonic):
    """各点の原値を保存。非負/支持0は警報、場外/非有限は無効観測として分離。"""
    start = clock()
    if len(bounds['min']) != 3 or len(bounds['max']) != 3:
        raise ValueError('field boundsの次元が無効')
    if not all(math.isfinite(lo) and math.isfinite(hi) and lo < hi
               for lo, hi in zip(bounds['min'], bounds['max'])):
        raise ValueError('field boundsが無効')
    points = fixed_points() if points is None else points
    support = ParticleSupport(positions, radius)
    rows = []
    for number, point in enumerate(points):
        if clock()-start > maximum_seconds:
            raise TimeoutError('単一ファイルの深水観測予算を超過')
        in_field = inside(point, bounds)
        raw_phi = float(sample_phi(point)) if in_field else None
        finite = in_field and math.isfinite(raw_phi)
        phi = raw_phi if finite else None
        nearest = support.query(point)
        has_support = nearest['count_within_radius'] > 0
        category = ('invalid_field' if not finite else
                    'negative_with_support' if phi < 0 and has_support else
                    'negative_without_support' if phi < 0 else
                    'nonnegative_with_support' if has_support else
                    'nonnegative_without_support')
        rows.append({'point_index': number, 'xyz_m': list(point),
                     'inside_field_bounds': in_field, 'phi_finite': finite,
                     'phi_m': phi, 'nonfinite_kind': None if not in_field or finite else str(raw_phi),
                     **nearest, 'category': category})
    categories = {key: sum(r['category'] == key for r in rows) for key in (
        'invalid_field', 'negative_with_support', 'negative_without_support',
        'nonnegative_with_support', 'nonnegative_without_support')}
    invalid = [r['point_index'] for r in rows if r['category'] == 'invalid_field']
    alarms = [r['point_index'] for r in rows if r['category'] not in
              ('invalid_field', 'negative_with_support')]
    return {'query_count': len(rows), 'radius_m': radius, 'point_order_sha256': digest(points),
            'rows': rows, 'category_counts': categories,
            'invalid_point_indices': invalid, 'coverage_alarm_point_indices': alarms,
            'observations_valid': not invalid,
            'registered_points_all_negative_and_supported': not invalid and not alarms,
            'physical_no_void_pass': False,
            'finite_phi_distribution_m': distribution([r['phi_m'] for r in rows if r['phi_finite']]),
            'nearest_distance_distribution_m': distribution([r['nearest_particle_distance_m'] for r in rows]),
            'support_count_distribution': distribution([r['count_within_radius'] for r in rows]),
            'support_count_histogram': {str(n): sum(r['count_within_radius'] == n for r in rows)
                                        for n in sorted({r['count_within_radius'] for r in rows})},
            'particle_count': support.count, 'occupied_hash_cells': len(support.cells),
            'nearest_fallback_queries': support.fallback_queries,
            'elapsed_seconds': clock()-start,
            'meaning_ja': '固定点の粗い被覆警報。支持ありは充填・圧力解像・無空洞の証明ではない。壁近傍の低い非ゼロ個数では警報にしない。'}
