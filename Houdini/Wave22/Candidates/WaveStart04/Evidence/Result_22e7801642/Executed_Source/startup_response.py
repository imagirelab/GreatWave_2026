"""始動応答の事前登録した純関数。原水位を補正せず、精度・無反射を認定しない。"""
import itertools
import math
import statistics


def baseline_threshold(series):
    windows = [[v for t, v in series if left < t <= right]
               for left, right in ((4.5, 5.25), (5.25, 6.0))]
    assert all(windows)
    mu = statistics.mean(windows[1])
    rms = [math.sqrt(statistics.mean((v - statistics.mean(w)) ** 2 for v in w)) for w in windows]
    envelope = max(abs(v - mu) for w in windows for v in w)
    return {'mu_second_window_m': mu, 'window_counts': list(map(len, windows)),
            'window_rms_about_mean_m': rms, 'maximum_baseline_deviation_m': envelope,
            'threshold_m': max(.001, 3 * max(rms), envelope)}


def inspect_series(series, config, rate):
    assert all(math.isfinite(t) and math.isfinite(v) for t, v in series)
    baseline = baseline_threshold(series)
    mu, q = baseline['mu_second_window_m'], baseline['threshold_m']
    start, end = config['primary_window_s']
    selected = [(t, v) for t, v in series if start <= t <= end]
    assert selected[0][0] == start
    raw = [v for _, v in selected]
    times = [t for t, _ in selected]
    eta6 = raw[0]
    # 表示面は30Hzなので同じ持続時間以上となるceilで別集計する。
    required = math.ceil(config['consecutive_raw_samples_for_onset'] * rate / 60)
    onset = None
    for i in range(1, len(raw) - required + 1):
        span = raw[i:i + required]
        if all(v - mu >= q for v in span) or all(v - mu <= -q for v in span):
            onset = {'start_s': times[i], 'end_s': times[i + required - 1],
                     'sign': 1 if span[0] > mu else -1, 'count': required}
            break
    relative_onset = None
    for i in range(1, len(raw) - required + 1):
        span = raw[i:i + required]
        if all(v - eta6 >= q for v in span) or all(v - eta6 <= -q for v in span):
            relative_onset = times[i]
            break
    smooth = {i: statistics.mean(raw[i - 2:i + 3]) for i in range(2, len(raw) - 2)}
    features, truncated = [], []
    radius = config['extremum_neighbourhood_s']
    for i in range(3, len(raw) - 3):
        sign = 1 if smooth[i] > smooth[i-1] and smooth[i] >= smooth[i+1] else (
            -1 if smooth[i] < smooth[i-1] and smooth[i] <= smooth[i+1] else 0)
        if not sign or sign * (raw[i] - mu) < q:
            continue
        left = [sign * smooth[j] for j in smooth if times[i] - radius <= times[j] < times[i]]
        right = [sign * smooth[j] for j in smooth if times[i] < times[j] <= times[i] + radius]
        feature = {'time_s': times[i], 'sign': sign, 'raw_eta_m': raw[i],
                   'smoothed_eta_m': smooth[i], 'raw_deviation_from_mu_m': raw[i] - mu,
                   't6_relative_auxiliary_m': raw[i] - eta6}
        if times[i] - radius < times[2] or times[i] + radius > times[-3]:
            truncated.append(feature)
            continue
        prominence = min(sign * smooth[i] - min(left), sign * smooth[i] - min(right))
        if prominence >= q:
            feature['two_sided_prominence_m'] = prominence
            features.append(feature)
    return {'baseline': baseline, 'raw_eta_at_t6_m': eta6,
            'raw_eta_min_max_m': [min(raw), max(raw)], 'onset': onset,
            't6_relative_auxiliary_onset_s': relative_onset,
            'features': features, 'truncated_candidates': truncated,
            'meaning_ja': '絶対水位が主記録。t6差分は起動時刻補助のみで、水深・体積の補正ではない。'}


def ordered_chains(gauges, limits):
    chains = []
    for features in itertools.product(*(g['features'] for g in gauges)):
        lags = [b['time_s'] - a['time_s'] for a, b in zip(features, features[1:])]
        if len({f['sign'] for f in features}) == 1 and all(limits[0] < lag < limits[1] for lag in lags):
            chains.append({'sign': features[0]['sign'], 'times_s': [f['time_s'] for f in features],
                           'adjacent_lags_s': lags})
    # 理論時刻に近い鎖を選択しない。複数候補は多義のまま残す。
    return chains


def analyze_response(rows, config):
    assert len(rows) == 556 and [r['sample'] for r in rows] == list(range(556))
    for k, row in enumerate(rows):
        assert abs(row['requested_seconds'] - k / 60) < 1e-9
        assert abs(row['simulation_seconds'] - k / 60) < 1e-6
        assert len(row['gauges']) == 3 and all(g['valid'] for g in row['gauges'])
    outputs = {}
    for label, field, rate in (('solver_surface_sign_field', 'eta_m', 60), ('PFS_display_surface', 'mesh_eta_m', 30)):
        gauges = []
        for index in range(3):
            series = [(r['requested_seconds'], r['gauges'][index][field]) for r in rows
                      if field == 'eta_m' or r['mesh_sampled']]
            result = inspect_series(series, config, rate)
            result['x_m'] = rows[0]['gauges'][index]['x']
            gauges.append(result)
        chains = ordered_chains(gauges, config['ordered_same_sign_adjacent_lag_open_s'])
        if len(chains) == 1:
            status = 'ONE_ORDERED_FEATURE_CHAIN_OBSERVED'
        elif len(chains) > 1:
            status = 'AMBIGUOUS_MULTIPLE_CHAINS'
        elif not any(g['onset'] for g in gauges):
            status = 'NO_PERSISTENT_THRESHOLD_EXCEEDANCE'
        else:
            status = 'RESPONSE_WITHOUT_UNIQUE_ORDERED_CHAIN'
        outputs[label] = {'status': status, 'gauges': gauges, 'all_eligible_chains': chains}
    return {'config': config, 'observations': outputs, 'wave_verified': False,
            'physical_accuracy_verified': False, 'reflection_free_verified': False,
            'step22_complete': False,
            'meaning_ja': '固定短窓の始動特徴候補だけ。候補なしも全波動不存在の証明ではない。表示面とsolver場を別観測とし、理論速度で合格を選ばない。'}
