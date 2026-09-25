"""保存済みON/OFF原記録から図・CSVを再計算する。Houdiniは呼ばない。"""
import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import math
import platform
import statistics
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

WAVE=Path(__file__).resolve().parents[3]
CANDIDATE=Path(__file__).resolve().parents[1]
FONT=Path('C:/Windows/Fonts/meiryo.ttc')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    data=path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix=='.gz' else data)


def write(path,value):
    path.write_bytes((json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def curate(token,dest):
    """通常終了・初態配対済みの原資料を、新候補だけへ複製する。"""
    run=WAVE/'Runs'/token
    report=load(run/'Evidence/22_reseeding_off_execution.json')
    assert report['execution_succeeded'] and report['cleanup']['all_ui_and_owned_node_checks_passed']
    assert report['initial_pair']['strict_pair_matched'] and not report['transport_completion_uncertain']
    assert report['outcome']['last_sample']==360 and not report['drive_authorized']
    dest.mkdir(parents=True,exist_ok=True)
    original=dest/'Original';original.mkdir(exist_ok=True)
    records=[]

    def save(source,name,compress=False):
        payload=source.read_bytes()
        target=original/(name+'.gz' if compress else name)
        target.write_bytes(gzip.compress(payload,compresslevel=9,mtime=0) if compress else payload)
        records.append({'path':str(target.relative_to(dest)).replace('\\','/'),
                        'source_sha256':hashlib.sha256(payload).hexdigest(),'source_bytes':len(payload),
                        'stored_sha256':sha(target),'stored_bytes':target.stat().st_size,'gzip':compress})

    baseline=WAVE/'Evidence/Curated_Runs/db52394211'
    for prefix,folder in [('on',baseline),('off',run/'Evidence')]:
        for short in ('pilot_samples','pilot_conditions','checkpoint_gate','initialization_schema'):
            save(folder/('22_'+short+'.json'),prefix+'_'+short+'.json',short=='pilot_samples')
    for short in ('checkpoint_trace','initial_strict_pair','initialization_schema_comparison',
                  'reseed_internal_detail','length6_grid_preflight','off_health_checkpoint'):
        save(run/'Evidence'/('22_'+short+'.json'),'off_'+short+'.json')
    summary=load(CANDIDATE/'Evidence/22_baseline_readback_summary.json')
    for token_suffix in ('deepwater03_c4aab88dc2','deepwater03_6047336bef'):
        save(WAVE/'Runs'/token_suffix/'execution.json','on_'+token_suffix+'_execution.json')
    for item in summary['rows']:
        source=WAVE/item['report_path'];assert sha(source)==item['report_sha256']
        save(source,'on_deepwater_%03d.json'%item['sample'],True)
        save(run/'Evidence'/('22_deepwater_%03d.json'%item['sample']),
             'off_deepwater_%03d.json'%item['sample'],True)
    source_dest=dest/'Executed_Source';source_dest.mkdir(exist_ok=True)
    for name,expected in report['source_hashes'].items():
        source=run/'Source'/name;assert sha(source)==expected
        (source_dest/name).write_bytes(source.read_bytes())
    # 個人パスやtracebackを公開せず、原実行報告のSHAと必要な観測を保存する。
    execution={key:report[key] for key in ('token','utc','metadata','clock_initialization','ownership',
                 'initial_pair','initialization_schema_comparison','outcome','cleanup','source_hashes',
                 'coverage_alert_latched','execution_succeeded','transport_completion_uncertain')}
    execution.update({'raw_execution_report_sha256':sha(run/'Evidence/22_reseeding_off_execution.json'),
                      'rpc_seconds_sum':sum(e['rpc_seconds'] for e in report['events']),
                      'event_count':len(report['events'])})
    write(dest/'22_execution_summary.json',execution)
    write(dest/'22_original_manifest.json',{'records':records,'meaning_ja':'gzipはmtime=0。展開bytesは実原JSONと一致。raw BGEOは本機のみ。'})
    rows=load(run/'Evidence/22_pilot_samples.json')['samples'];assert len(rows)==361
    cache=[]
    for r in rows:
        for kind,name,expected in [('solver','pilot_%03d.bgeo.sc'%r['sample'],r['cache_sha256']),
                                   ('PFS','mesh_%03d.bgeo.sc'%r['sample'],r['mesh_file_sha256'])]:
            if expected is None:continue
            path=run/'Cache'/name;assert sha(path)==expected
            cache.append({'filename':name,'kind':kind,'seconds':r['requested_seconds'],
                          'bytes':path.stat().st_size,'sha256':expected})
    for r in load(run/'Evidence/22_length6_grid_preflight.json')['rows']:
        for item in r['saved_geometry']:
            path=run/'Cache'/item['name'];assert sha(path)==item['sha256'] and path.stat().st_size==item['bytes']
            cache.append({'filename':item['name'],'kind':'preflight','seconds':r['requested_seconds'],
                          'bytes':item['bytes'],'sha256':item['sha256']})
    assert len(cache)==548 and {p.name for p in (run/'Cache').glob('*.bgeo.sc')}=={r['filename'] for r in cache}
    write(dest/'22_cache_manifest.json',{'token':token,'cache_files':cache,'total_bytes':sum(r['bytes'] for r in cache),
          'local_only_path':'Houdini/Wave22/Runs/'+token+'/Cache','verified_against_raw_files':True})


def series_stats(rows,gauge,key,left,right):
    selected=[r for r in rows if left<r['requested_seconds']<=right and r['gauges'][gauge].get(key) is not None]
    times=[r['requested_seconds'] for r in selected];values=[r['gauges'][gauge][key] for r in selected]
    mt=statistics.mean(times);mv=statistics.mean(values)
    slope=sum((t-mt)*(v-mv) for t,v in zip(times,values))/sum((t-mt)**2 for t in times)
    return {'count':len(values),'mean_m':mv,'rms_about_mean_m':math.sqrt(sum((v-mv)**2 for v in values)/len(values)),
            'trend_m_s':slope,'trend_times_window_m':slope*(right-left)}


def mesh_correlation(rows,gauge,left,right):
    selected=[r for r in rows if left<r['requested_seconds']<=right and r['mesh_sampled']]
    a=[r['gauges'][gauge]['eta_m'] for r in selected];b=[r['gauges'][gauge]['mesh_eta_m'] for r in selected]
    ma,mb=statistics.mean(a),statistics.mean(b)
    denominator=math.sqrt(sum((v-ma)**2 for v in a)*sum((v-mb)**2 for v in b))
    return sum((x-ma)*(y-mb) for x,y in zip(a,b))/denominator if denominator else None


def reproduce(dest):
    manifest=load(dest/'22_original_manifest.json')
    for record in manifest['records']:
        path=dest/record['path'];assert sha(path)==record['stored_sha256'] and path.stat().st_size==record['stored_bytes']
        payload=gzip.decompress(path.read_bytes()) if record['gzip'] else path.read_bytes()
        assert len(payload)==record['source_bytes'] and hashlib.sha256(payload).hexdigest()==record['source_sha256']
    execution=load(dest/'22_execution_summary.json')
    assert execution['execution_succeeded'] and execution['cleanup']['all_ui_and_owned_node_checks_passed']
    assert execution['initial_pair']['strict_pair_matched'] and not execution['outcome']['drive_authorized']
    for name,expected in execution['source_hashes'].items():assert sha(dest/'Executed_Source'/name)==expected
    gate_module=module('reproduction_original_gate',dest/'Executed_Source/checkpoint_gate.py')
    core=module('reproduction_support_core',dest/'Executed_Source/deepwater_core.py')
    data={};gates={};windows={}
    for mode in ('on','off'):
        rows=load(dest/'Original'/f'{mode}_pilot_samples.json.gz')['samples']
        conditions=load(dest/'Original'/f'{mode}_pilot_conditions.json')
        stored_gate=load(dest/'Original'/f'{mode}_checkpoint_gate.json')
        assert len(rows)==361 and [r['sample'] for r in rows]==list(range(361))
        assert all(abs(r['simulation_seconds']-r['requested_seconds'])<1e-9 for r in rows)
        assert all(r['requested_seconds']==r['sample']/60 and r['simulation_dt']==1/120 for r in rows)
        assert all(r['finite_pv'] and r['particle_ids_unique'] and r['outside_inner_walls_beyond_20mm']==0 for r in rows)
        assert all(r['cache_reread_P_v_surface_voxels_match'] and all(g['valid'] for g in r['gauges']) for r in rows)
        assert all(r['piston_displacement_m']==r['piston_velocity_m_s']==0 for r in rows)
        gate=gate_module.evaluate_gate(rows,conditions,6.)
        assert all(stored_gate[k]==v for k,v in gate.items())
        data[mode]=rows;gates[mode]=gate
        windows[mode]=[{'left_open_s':a,'right_closed_s':b,'gauges':[
            {'solver_60Hz':series_stats(rows,g,'eta_m',a,b),
             'solver_at_mesh_30Hz':series_stats([r for r in rows if r['mesh_sampled']],g,'eta_m',a,b),
             'PFS_30Hz':series_stats(rows,g,'mesh_eta_m',a,b),
             'SDF_PFS_correlation_same_30Hz':mesh_correlation(rows,g,a,b)} for g in range(3)]} for a,b in [(4.5,5.25),(5.25,6.)]]
    trace=load(dest/'Original/off_checkpoint_trace.json')['samples']
    assert len(trace)==361 and len({r['dop_session_id'] for r in trace})==1 and all(not r['drive_authorized'] for r in trace)
    assert load(dest/'Original/off_initial_strict_pair.json')['strict_pair_matched']
    with (dest/'22_on_off_gauges.csv').open('w',encoding='utf8',newline='') as stream:
        writer=csv.writer(stream,lineterminator='\n')
        writer.writerow(['sample','absolute_s','gauge','x_m','ON_solver_eta_m','OFF_solver_eta_m',
                         'ON_PFS_eta_m','OFF_PFS_eta_m','OFF_minus_ON_solver_m'])
        for on,off in zip(data['on'],data['off']):
            for g in range(3):
                a,b=on['gauges'][g],off['gauges'][g];assert a['x']==b['x'] and a['z']==b['z']
                writer.writerow([on['sample'],on['requested_seconds'],g+1,a['x'],a['eta_m'],b['eta_m'],
                                 a.get('mesh_eta_m'),b.get('mesh_eta_m'),b['eta_m']-a['eta_m']])
    coverage=[]
    for k in (0,30,180,270,315,360):
        pair={mode:load(dest/'Original'/f'{mode}_deepwater_{k:03d}.json.gz') for mode in ('on','off')}
        groups=core.compare_coverage(pair['on']['deepwater']['rows'],pair['off']['deepwater']['rows'])
        coverage.append({'sample':k,'seconds':k/60,'alarm_groups':groups,
                         'on':{key:pair['on']['deepwater'][key] for key in ('category_counts','nearest_distance_distribution_m','support_count_distribution')},
                         'off':{key:pair['off']['deepwater'][key] for key in ('category_counts','nearest_distance_distribution_m','support_count_distribution')}})
    output={'baseline':'db52394211','candidate':execution['token'],'static_gates':gates,'late_windows':windows,
            'initial_pair':load(dest/'Original/off_initial_strict_pair.json'),
            'coverage':coverage,'coverage_alert':any(r['alarm_groups']['off_only'] or r['alarm_groups']['shared_baseline_and_off'] for r in coverage),
            'distribution_definition_ja':'深水のmedianはsorted[N//2]の上側中央値。p95はnearest-rank。',
            'particle_observations':{mode:{'initial':rows[0]['particle_count'],'final':rows[-1]['particle_count'],
                'ID_birth_events':sum(len(r['particle_id_births_since_previous']) for r in rows),
                'ID_death_events':sum(len(r['particle_id_deaths_since_previous']) for r in rows),
                'maximum_velocity_m_s':max(r['particle_velocity_max_m_s'] for r in rows)} for mode,rows in data.items()},
            'actual_collision_nonzero':{mode:[{'sample':r['sample'],'velocity_m_s':r['piston_actual_collision_velocity_m_s']}
                for r in rows if any(r['piston_actual_collision_velocity_m_s'])] for mode,rows in data.items()},
            'piston_started_true_samples':{mode:[r['sample'] for r in rows if r['piston_started']] for mode,rows in data.items()},
            'resources':{'cook_seconds_sum':sum(r['cook_seconds'] for r in data['off']),
                'cook_seconds_max':max(r['cook_seconds'] for r in data['off']),
                'private_bytes_max':max(r['memory']['private_commit_bytes'] for r in data['off']),
                'available_ram_bytes_min':min(r['memory']['available_physical_bytes'] for r in data['off']),
                'dop_cache_bytes_max':max(r['simulation_memory_bytes'] for r in data['off'])},
            'solver_errors_or_warnings':sum(bool(r['solver_errors'] or r['solver_warnings']) for r in data['off']),
            'cleanup':execution['cleanup'],'wave_verified':False,'physical_accuracy_verified':False,
            'physical_no_void_verified':False,'drive_authorized':False,
            'meaning_ja':'同一初態のSOP doreseeding切替診断。静水判定・粗い被覆・物理精度は別。質量保存/無空洞/波伝播を証明しない。'}
    write(dest/'22_reseeding_comparison.json',output)
    font=FontProperties(fname=str(FONT))
    statuses='ON '+('PASS' if gates['on']['diagnostic_stability_passed'] else 'FAIL')+' / OFF '+('PASS' if gates['off']['diagnostic_stability_passed'] else 'FAIL')
    for detail in (False,True):
        fig,axes=plt.subplots(3,1,figsize=(12,8.5),sharex=True)
        for g,ax in enumerate(axes):
            for mode,color in [('on','#6d8078'),('off','#145b8b')]:
                rows=data[mode]
                ax.plot([r['requested_seconds'] for r in rows],[r['gauges'][g]['eta_m']*1000 for r in rows],color=color,label=mode.upper()+' solver符号場（60Hz）')
                meshes=[r for r in rows if r['mesh_sampled']]
                ax.plot([r['requested_seconds'] for r in meshes],[r['gauges'][g]['mesh_eta_m']*1000 for r in meshes],color=color,linestyle='--',alpha=.7,label=mode.upper()+' PFS表示面（30Hz）')
            ax.axvspan(4.5,5.25,color='#e0ecf1',alpha=.6);ax.axvspan(5.25,6,color='#f0e7d5',alpha=.6)
            ax.axhline(0,color='#555',linewidth=.6);ax.grid(alpha=.2)
            ax.set_ylabel('未補正水位 η [mm]',fontproperties=font)
            ax.set_title(f'G{g+1} x={data["off"][0]["gauges"][g]["x"]:.6f} m',fontproperties=font,loc='left',fontsize=10)
            ax.set_xlim(4.5 if detail else 0,6)
            if detail:
                vals=[r['gauges'][g][key]*1000 for rows in data.values() for r in rows if r['requested_seconds']>=4.5
                      for key in ('eta_m','mesh_eta_m') if r['gauges'][g].get(key) is not None]
                ax.set_ylim(min(vals)-.8,max(vals)+.8)
        axes[-1].set_xlabel('絶対DOP時刻 [s]（解析活塞変位・速度0、造波なし）',fontproperties=font)
        fig.suptitle('第22号 SOP再シーディング切替の静水診断：'+statuses,fontproperties=font,fontsize=14)
        handles,labels=axes[0].get_legend_handles_labels()
        fig.legend(handles,labels,prop=FontProperties(fname=str(FONT),size=9),loc='upper center',bbox_to_anchor=(.5,.95),ncol=2)
        fig.text(.5,.012,'図は実測値の再描画。映像ではない。上限3mm/1%は固定、PASSでも造波しない。',fontproperties=font,ha='center',fontsize=10)
        fig.tight_layout(rect=(0,.04,1,.89))
        fig.savefig(dest/('22_reseeding_late_windows.png' if detail else '22_reseeding_full_series.png'),dpi=140)
        plt.close(fig)
    lines=['# 22修正03：SOP再シーディング切替の静水診断','',
           '実行 '+execution['token']+'、配対基線 db52394211。固定6秒・361標本。**'+statuses+'。PASSでも造波なし。**','',
           '条件の物理差はSOP doreseeding 1→0。t0のID別P/v/pscale、surface/pressure格点と全体素は厳密一致。'+
           '内部DOPのOnly Source Seeding=1、Reseed Particles=1を観測した。内部Reseed ParticlesまでOFFとは記さない。旧ONの該当内部値は未収録。','',
           '| 測点 | ON 傾き×.75秒：前/後 [mm] | OFF 傾き×.75秒：前/後 [mm] | OFF 窓間平均差 [mm] | OFF 平均まわりRMS：前/後 [mm] |',
           '| --- | ---: | ---: | ---: | ---: |']
    for g in range(3):
        on=[w['gauges'][g]['trend_change_per_window_m']*1000 for w in gates['on']['windows']]
        off=[w['gauges'][g]['trend_change_per_window_m']*1000 for w in gates['off']['windows']]
        rms=[w['gauges'][g]['residual_rms_about_mean_m']*1000 for w in gates['off']['windows']]
        delta=gates['off']['gauge_checks'][g]['mean_change_m']*1000
        lines.append(f'| G{g+1} | {on[0]:+.6f} / {on[1]:+.6f} | {off[0]:+.6f} / {off[1]:+.6f} | {delta:+.6f} | {rms[0]:.6f} / {rms[1]:.6f} |')
    lines+=['','窓は(4.5,5.25] / (5.25,6]、各45点。平均差・平均まわりRMS・傾き×窓長は3mm、負の符号場voxel代理量の窓間変化は1%という元条件を変更していない。代理量は水量ではない。','',
            '[原時系列CSV](22_on_off_gauges.csv) / [判定・資源・粒子と表示面統計](22_reseeding_comparison.json) / [548実BGEO hash](22_cache_manifest.json)','',
            '![実測全時系列](22_reseeding_full_series.png)','',
            '![実測固定窓](22_reseeding_late_windows.png)','',
            '各図は保存した実測の再描画であり、Houdini/Unityの映像ではない。元水位を基線補正していない。PFS表示面は30Hzの補助観測で、元60Hz判定を置き換えない。','',
            '深水検査は6時刻×7128点、半径.08mの粗い支持診断である。各点のphi/最近距離/支持個数を[Original](Original)のgzipに原bytesのまま保存した。'+
            'medianは上側中央値、p95はnearest-rank。負の符号場と粒子支持があっても全域/連続時刻/近表面の無空洞、質量・圧力・波精度は証明しない。','',
            'surfaceはVolumeとして読んだがisSDF metadataはfalseだった。採録された符号場の実値として扱い、認証されたSDF primitiveと呼ばない。'+
            '共有警報・ONだけ・OFFだけを別記し、coverage_alertは終点の選択に使わない。','',
            '公開gzipはmtime=0。[原/圧縮SHA一覧](22_original_manifest.json)で展開bytesを照合できる。'+
            '全BGEO本体はGドライブのRunsに保持し公開しない。公開再計算は図・CSV・統計の再現であり、BGEOの再cook/全hash再読戻しとは別である。','',
            'HIPの保存/読込なし。全体24fpsを保持し、終了時18項目UI復元・所有物削除を確認した。造波・伝播・非砕波・理論精度・HMDは未検証。','']
    (dest/'README_ja.md').write_bytes('\n'.join(lines).encode('utf8'))
    products=['22_on_off_gauges.csv','22_reseeding_comparison.json','22_reseeding_full_series.png','22_reseeding_late_windows.png','README_ja.md']
    write(dest/'22_reproduction_manifest.json',{'script_sha256':sha(Path(__file__)),'font_sha256':sha(FONT),
          'python':platform.python_version(),'matplotlib':matplotlib.__version__,
          'products':[{'path':name,'bytes':(dest/name).stat().st_size,'sha256':sha(dest/name)} for name in products],
          'inputs':[{'path':r['path'],'sha256':r['stored_sha256']} for r in manifest['records']],
          'meaning_ja':'公開原JSON/gzipだけによる再計算。ローカルBGEO全体の再ハッシュとは別。'})
    print(json.dumps({'static_gates':{k:v['diagnostic_stability_passed'] for k,v in gates.items()},
                      'coverage_alert':output['coverage_alert'],'products':products},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='保存済み実測だけの集約。Houdini実行なし。')
    parser.add_argument('--curate-token')
    parser.add_argument('--evidence',type=Path,required=True)
    arguments=parser.parse_args()
    if arguments.curate_token:curate(arguments.curate_token,arguments.evidence)
    reproduce(arguments.evidence)
