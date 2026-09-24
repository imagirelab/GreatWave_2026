"""解析の最大差を含む実面で、AABB結果を全三角形総当たりと照合する。"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import analyze_sampling19 as analysis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding='utf8'))
    samples, digest, _ = analysis.read_reference(Path(report['input_reference']))
    assert digest == report['reference_sha256']
    worst = max(report['odd_comparisons'], key=lambda x: x['sampled_symmetric']['max_m'])
    k, checks = worst['sample60'], []
    for source, target in ((samples[k-1], samples[k]), (samples[k], samples[k-1])):
        probes, _, _ = analysis.surface_probes(source)
        tree = analysis.SurfaceTree(target['positions'], target['triangles'])
        distance = tree.distances(probes)
        ids = np.unique(np.r_[np.linspace(0, len(probes)-1, 8, dtype=int), np.argmax(distance)])
        brute = [float(np.sqrt(analysis.pair_distances_squared(probes[i:i+1], tree.triangles).min())) for i in ids]
        checks.append(dict(from_sample=source['index'], to_sample=target['index'], queries=len(ids),
                           max_bvh_vs_bruteforce_error_m=float(np.max(np.abs(distance[ids]-brute))),
                           worst_probe_m=float(distance.max()), worst_probe_position=probes[np.argmax(distance)].tolist()))
    result = dict(reference_sha256=digest, analysis_result_sha256=analysis.sha(args.report), verifier_sha256=analysis.sha(__file__),
                  worst_pair=k, real_surface_bruteforce_checks=checks,
                  passed=all(x['max_bvh_vs_bruteforce_error_m'] < 1e-12 for x in checks))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
