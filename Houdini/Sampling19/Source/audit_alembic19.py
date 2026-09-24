"""既存Steam版gabcで19 Alembic全試料をstdoutへ読み、正式参照と照合する。

UI起動・HIPアクセス・ファイル書出しはしない。CLIが付ける個人/ホスト情報は
結果に残さず、P/N/有向三角形と実アーカイブhashだけを記録する。
"""
import argparse
import hashlib
import json
import struct
import subprocess
import time
from pathlib import Path

import numpy as np


def pairs(values):
    return dict(zip(values[::2], values[1::2]))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--gabc', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reference = (args.root/'Exports/reference60.bytes').read_bytes()
    assert struct.unpack_from('<8siii', reference) == (b'GW19REF1', 1, 121, 60)
    offset, samples = 20, []
    for k in range(121):
        i, t, count, indices = struct.unpack_from('<ifii', reference, offset)
        assert i == k and abs(t-k/60) < 2e-7
        offset += 16
        p = np.frombuffer(reference, '<f4', count*3, offset).reshape(-1, 3)
        offset += count*12
        n = np.frombuffer(reference, '<f4', count*3, offset).reshape(-1, 3)
        offset += count*12
        tri = np.frombuffer(reference, '<i4', indices, offset).reshape(-1, 3)
        offset += indices*4
        samples.append((p, n, tri))
    assert offset == len(reference)
    manifest_path = args.root/'Evidence/19_alembic_exports.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf8'))
    records, archives = [], []
    started = time.monotonic()
    for export in manifest['exports']:
        path = args.root/export['path']
        before = digest(path.read_bytes())
        assert before == export['sha256'] and path.stat().st_size == export['bytes']
        first, last, rate = export['first_master_sample'], export['last_master_sample'], export['rate']
        for k in range(first, last+1, 60//rate):
            archive_time = 1/24+k/60
            command = [str(args.gabc), '-l', 'houdini', '-t', repr(archive_time), str(path), 'stdout.geo']
            run = subprocess.run(command, capture_output=True, text=True, encoding='utf8', errors='strict', timeout=30,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
            if run.returncode:
                raise RuntimeError('gabc読取失敗。exit='+str(run.returncode))
            geometry = pairs(json.loads(run.stdout))
            attributes = pairs(geometry['attributes'])
            point_attributes = {}
            for header, body in attributes['pointattributes']:
                name = pairs(header)['name']
                if name in ('P', 'N'):
                    values = pairs(pairs(body)['values'])
                    point_attributes[name] = np.array(values['tuples'], dtype='<f4')
            point_reference = np.array(pairs(pairs(geometry['topology'])['pointref'])['indices'], dtype='<i4')
            result_triangles = []
            for header, body in geometry['primitives']:
                assert pairs(header)['type'] == 'PolySoup'
                primitive = pairs(body)
                sizes, counts, order = primitive['polyinfo']
                assert sizes == [3] and sum(counts)*3 == len(primitive['vertex'])
                vertices = point_reference[np.asarray(primitive['vertex'])]
                assert len(order) == len(vertices)
                result_triangles.append(vertices[np.asarray(order)].reshape(-1, 3))
            triangles = np.concatenate(result_triangles)
            p, n, tri = samples[k]
            actual_p, actual_n = point_attributes['P'], point_attributes['N']
            same_shapes = actual_p.shape == p.shape and actual_n.shape == n.shape and triangles.shape == tri.shape
            exact_p = same_shapes and np.array_equal(actual_p, p)
            exact_n = same_shapes and np.array_equal(actual_n, n)
            exact_triangles = same_shapes and np.array_equal(triangles, tri)
            row = dict(archive=path.name, rate=rate, master_sample=k, requested_archive_seconds=archive_time,
                       relative_seconds=k/60, points=len(actual_p), triangles=len(triangles),
                       exact_float32_P=bool(exact_p), exact_float32_N=bool(exact_n), exact_oriented_triangle_indices=bool(exact_triangles),
                       maximum_position_error_m=float(np.abs(actual_p.astype(np.float64)-p).max()) if same_shapes else None,
                       P_sha256=digest(actual_p.tobytes()), N_sha256=digest(actual_n.tobytes()), triangle_sha256=digest(triangles.tobytes()),
                       passed=bool(exact_p and exact_n and exact_triangles))
            records.append(row)
            if len(records) % 10 == 0:
                print(json.dumps(dict(checked=len(records), last_master_sample=k, elapsed_seconds=round(time.monotonic()-started, 2))), flush=True)
        assert digest(path.read_bytes()) == before
        archives.append(dict(path=export['path'], sha256=before, bytes=path.stat().st_size, checked_count=sum(r['archive'] == path.name for r in records)))
    common, seams = [], []
    for k in range(0, 121, 2):
        rows = [r for r in records if r['master_sample'] == k]
        hashes = {(r['P_sha256'], r['N_sha256'], r['triangle_sha256']) for r in rows}
        item = dict(master_sample=k, archive_samples=len(rows), all_payload_hashes_equal=len(hashes) == 1)
        common.append(item)
        if k in (40, 80):
            seams.append(item)
    report = dict(classification='INDEPENDENT_EXISTING_CLI_ALEMBIC_GEOMETRY_READBACK', reference_sha256=digest(reference),
                  export_manifest_sha256=digest(manifest_path.read_bytes()), script_sha256=digest(Path(__file__).read_bytes()),
                  reader=str(args.gabc), scope_ja='実ABCを指定実秒で読取。時刻配列そのものは別のnative sampling検査と併用。',
                  archives=archives, sample_checks=records, common_30_60_times=common, segment_seams=seams,
                  passed=all(r['passed'] for r in records) and all(r['all_payload_hashes_equal'] for r in common),
                  elapsed_seconds=time.monotonic()-started)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps(dict(completed=str(args.output), passed=report['passed'], sample_checks=len(records), elapsed_seconds=report['elapsed_seconds'])), flush=True)


if __name__ == '__main__':
    main()
