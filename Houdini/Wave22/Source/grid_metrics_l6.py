"""L6の格子・壁診断の純関数。Houdiniやファイルを操作しない。"""
import math


def mirror_metric(cell_center_x, spacing_x, length, tolerance=.001):
    assert all(math.isfinite(v) for v in (cell_center_x, spacing_x, length, tolerance))
    assert spacing_x > 0 and length > 0 and tolerance > 0
    q0 = -cell_center_x / spacing_x
    ql = (length - cell_center_x) / spacing_x
    error = abs(q0 + ql - round(q0 + ql))
    return {'q0_cells': q0, 'qL_cells': ql, 'Eg_cells': error,
            'mirror_compatible_label': error <= tolerance,
            'label_tolerance_cells': tolerance, 'physical_pass': False}


def within_bounds(point, bounds):
    return all(math.isfinite(c) and low <= c <= high
               for c, low, high in zip(point, bounds['min'], bounds['max']))


def wall_pairs(sample, bounds, length, spacing_x, settings):
    """固体側負・水槽内側正の実衝突SDFを前提に、対称点と18本の壁根を返す。"""
    assert length > 0 and spacing_x > 0
    values, roots = [], []

    def phi(point):
        assert within_bounds(point, bounds), ('field外', point)
        value = float(sample(point))
        assert math.isfinite(value), ('非有限field', point)
        return value

    for y in settings['y_m']:
        for z in settings['z_m']:
            for d in settings['distances_m']:
                left, right = phi((d, y, z)), phi((length-d, y, z))
                values.append({'d_m': d, 'y_m': y, 'z_m': z,
                               'phi_left_m': left, 'phi_right_m': right,
                               'difference_m': left-right})
            for side in ('left', 'right'):
                lo, hi = settings['wall_bracket_m']
                x_at = (lambda d: d) if side == 'left' else (lambda d: length-d)
                a, b = phi((x_at(lo), y, z)), phi((x_at(hi), y, z))
                assert a < 0 < b, ('壁の符号が欠ける', side, y, z, a, b)
                initial_bracket = [a, b]
                while hi-lo > settings['wall_bisection_tolerance_m']:
                    mid = (lo+hi)/2
                    if phi((x_at(mid), y, z)) < 0:
                        lo = mid
                    else:
                        hi = mid
                d = (lo+hi)/2
                roots.append({'side': side, 'y_m': y, 'z_m': z, 'd_from_nominal_wall_m': d,
                              'x_m': x_at(d), 'final_bracket_width_m': hi-lo,
                              'initial_phi_bracket_m': initial_bracket})
    errors = [v['difference_m'] for v in values]
    return {'pair_count': len(values), 'pairs': values, 'wall_roots': roots,
            'maximum_absolute_difference_m': max(abs(e) for e in errors),
            'rms_difference_m': math.sqrt(sum(e*e for e in errors)/len(errors)),
            'spacing_x_m': spacing_x, 'physical_pass': False,
            'meaning_ja': '鏡像誤差と壁位置の記録のみ。Egや誤差の改善は造波許可にならない。'}
