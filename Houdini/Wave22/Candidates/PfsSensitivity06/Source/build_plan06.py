"""04の公開条件・manifestから06候補を作る。HOMを読み込まない。"""
import gzip
import hashlib
import json
from pathlib import Path

CANDIDATE = Path(__file__).resolve().parents[1]
WAVE = CANDIDATE.parents[1]
BASE = WAVE / 'Candidates/WaveStart04/Evidence/Result_22e7801642'
PREVIOUS = WAVE / 'Candidates/PfsDiagnosis05'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_plan():
    rows = json.loads(gzip.decompress((BASE / 'Original/22_pilot_samples.json.gz').read_bytes()))['samples']
    cache = {r['filename']: r for r in json.loads((BASE / '22_cache_manifest.json').read_bytes())['cache_files']}
    pilot = [360, 474, 496]
    extension = list(range(272, 555, 2))
    records = []
    for k in extension:
        r = rows[k]
        assert r['mesh_sampled'] and r['sample'] == k
        assert abs(r['global_frame'] - (1 + (k / 60) * 24)) < 1e-8
        records.append({'sample': k, 'seconds': k / 60, 'global_frame': r['global_frame'],
                        'pilot': cache[f'pilot_{k:03d}.bgeo.sc'], 'mesh': cache[f'mesh_{k:03d}.bgeo.sc'],
                        'mesh_points': r['mesh_points'], 'mesh_faces': r['mesh_faces'], 'gauges': r['gauges']})
    pinned = ['22_cache_manifest.json', 'Original/22_pilot_samples.json.gz',
              'Original/22_pilot_conditions.json', 'Original/22_startup_response.json',
              'Executed_Source/startup_response.py', 'Executed_Source/generate_wave_l6.py', 'Executed_Source/ui_guard.py']
    profile_plan = json.loads((PREVIOUS / 'Source/profile05_plan.json').read_bytes())
    return {
        'revision': '22修正06', 'state_ja': '未実行の審査候補。実行放行・stage・commitはまだ行わない。',
        'baseline_run': '22e7801642', 'baseline_commit': 'd3be3eb205f6e3ff91c215806bb85df84976cac6',
        'preceding_commit': '76fabdf8ce09ee7b4ad3f531e61cdda8dba51116',
        'baseline_files': {name: sha(BASE / name) for name in pinned},
        'profile05_dependencies': {name: sha(PREVIOUS / 'Source' / name) for name in ('profile_core.py', 'read_profile05.py')},
        'gauge_x_m': [g['x'] for g in rows[0]['gauges']],
        'pilot_samples': pilot, 'records': records,
        'stage_order': ['REPLAY_360', 'REPLAY_474', 'REPLAY_496', 'REFINE_360', 'REFINE_474', 'REFINE_496'],
        'extension_samples': extension, 'extension_requires_new_review': True,
        'extension_implemented': False,
        'input_contract_ja': '元pilot BGEO全体をliteral File SOPで読む。実粒子とvolume保持点/fieldsを分離記録するが入力から削除・再seed・補間しない。新solver/DOPは作らない。',
        'node_types': {'PFS': 'particlefluidsurface::3.0', 'convert': 'convert', 'file': 'file'},
        'mesh_parameters': {'particlesep': .04, 'surfmethod': 'particlefluid', 'voxelsize': .5,
                            'adaptivity': 0, 'dodilate': 0, 'dosmooth': 0, 'doerode': 0,
                            'dofinalsmooth': 0, 'closedcontainer': 0, 'closedends': 0, 'flattengeo': 0},
        'candidate_change': {'parameter': 'voxelsize', 'from': .5, 'to': .25,
                             'expected_voxel_m': [.02, .01],
                             'meaning_ja': 'Voxel Scale × Particle Separationの期待値。物理粒子/圧力格子は不変。公開原ソースは全HDA既定値の記録ではないため、現物全parmと定義SHAを比較する。'},
        'convert_parameters': {'totype': 'poly'},
        'parity': {'P_exact': True, 'oriented_indices_exact': True, 'primitive_type_closed_exact': True,
                   'native_replay_vs_original_exact': True, 'original_record_height_tolerance_m': 1e-6,
                   'solver_record_height_tolerance_m': 1e-8,
                   'remesh_file_bytes_equality_required': False,
                   'all_three_replays_before_any_refinement': True,
                   'non_voxelsize_evaluated_parameters_exact': True},
        'intersection': {**profile_plan['intersection'], 'default_strict_height_tolerance_m': 1e-6,
                         'default_strict_normal_positive_dot_required': True,
                         'default_primitive_needs_incidence_support': True,
                         'default_strict_same_primitive_required': False},
        'profiles_per_mesh': 195, 'pilot_output_mesh_count': 6, 'pilot_profile_count': 1170,
        'pilot_acceptance_ja': [
            '3フレームの旧.5のP配列/有向indices/primitive型・閉鎖フラグ/native三測点を厳密に比較。並替え修復や許容差拡大なし。不一致は原JSONを保存しHOLD。',
            '.25は有限・読戻し・field範囲・native/query整合・資源条件で判定する。唯一鎖の出現やprominence増大を続行条件にしない。',
            '上下交点数が旧形状と異なる、単一wet→dryでない、上面のnormal方向が反転する場合は原観測を保存して形状審査HOLD。下底交点を第2自由面と呼ばない。',
            '1µm/10µmの交点感度が1µmを超える、主queryとprimitive限定queryが不整合なら数値審査HOLD。0.1mm/1mmは補助表示で、物理合格値ではない。'],
        'response': {'pilot_detector_executed': False,
                     'extension_detector_source': 'Executed_Source/startup_response.py',
                     'extension_config': json.loads((BASE / 'Original/22_startup_response.json').read_bytes())['config'],
                     'extension_PFS_count': 142, 'extension_PFS_rate_Hz': 30, 'solver_rows_preserved': 556,
                     'baseline_windows_PFS_counts': [22, 23],
                     'threshold_floor_m': .001, 'fixed_height_correction_m': None,
                     'meaning_ja': '拡張は別放行。272..554偶数を固定、三pilotの新面も142枚に含める。k<272のmesh_sampledだけfalseにし、原solver行/値を保持。各面化の静水窓から原式q=max(.001,3RMS,E)を別計算、旧qの強制代入なし。原5点/±.375秒/同符号一意鎖を変更しない。'},
        'budgets': {'minimum_available_RAM_bytes': 8 * 1024**3,
                    'maximum_private_increase_bytes': 12 * 1024**3,
                    'maximum_cook_seconds': 30, 'recent_30_median_seconds': 15,
                    'maximum_projected_remaining_seconds': 5400,
                    'per_rpc_cooperative_seconds': 90, 'rpc_wait_seconds': 180,
                    'pilot_cumulative_seconds': 540,
                    'maximum_mesh_bytes': 16 * 1024**2, 'auxiliary_reserved_bytes': 64 * 1024**2,
                    'reserved_output_bytes': 142 * 16 * 1024**2 + 64 * 1024**2,
                    'start_minimum_free_G_bytes': 2 * (142 * 16 * 1024**2 + 64 * 1024**2) + 10 * 1024**3,
                    'running_minimum_free_G_bytes': 10 * 1024**3,
                    'pilot_input_unique_bytes': sum(cache[f'{kind}_{k:03d}.bgeo.sc']['bytes'] for k in pilot for kind in ('pilot', 'mesh')),
                    'extension_input_pilot_bytes': sum(cache[f'pilot_{k:03d}.bgeo.sc']['bytes'] for k in extension),
                    'extension_reference_mesh_bytes': sum(cache[f'mesh_{k:03d}.bgeo.sc']['bytes'] for k in extension),
                    'meaning_ja': '費用は未測定。voxel数8倍/面積標本約4倍は説明用の密格子外挿で保証ではない。cookは協調停止だけで強制中断できない。超過完了後は保存/復元して次RPCを開始しない。完了不明は再要求/kill/並行cleanup禁止。'},
        'ui_contract': {'manual_before_frame_change': True, 'global_fps_required': 24,
                        'same_absolute_frame_as04': True, 'hip_save_load_clear': False,
                        'no_viewport_capture_in_pilot': True, 'owned_nodes_only': True,
                        'restore_18_checks': True},
        'publication_ja': ['新面化の原高さと差を示す静止図。観測点・時刻・元/新BGEO・源SHAに結ぶ。想像図を使わない。',
                           '元rawは不変。新mesh/詳細JSONはGの新Runs、公開用は後の審査で選定。03/04/05を上書きしない。',
                           '3フレーム合格もmesh感度の先導のみ。長槽full測点/非砕波連続伝播/22完成/23精度/HMDを認定しない。'],
        'sources': ['https://www.sidefx.com/docs/houdini/nodes/sop/particlefluidsurface.html',
                    'https://www.sidefx.com/docs/houdini/hom/hou/Geometry.html',
                    'https://www.sidefx.com/docs/houdini/hom/hou/SopNode.html'],
        'houdini_executed': False, 'new_solver_executed': False, 'step22_complete': False}


if __name__ == '__main__':
    path = CANDIDATE / 'Source/pfs06_plan.json'
    path.write_bytes((json.dumps(make_plan(), ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8'))
    print(json.dumps({'houdini_called': False, 'plan': path.name, 'sha256': sha(path)}))
