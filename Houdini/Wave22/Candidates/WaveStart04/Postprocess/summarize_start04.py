"""実始動runの原記録を保全し、未補正の時系列を図・CSVへ出す。Houdini不使用。"""
import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import statistics
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

CANDIDATE=Path(__file__).resolve().parents[1]
WAVE=CANDIDATE.parents[1]
FONT=Path('C:/Windows/Fonts/meiryo.ttc')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):
    raw=path.read_bytes();return json.loads(gzip.decompress(raw) if path.suffix=='.gz' else raw)
def write(path,value):path.write_bytes((json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))


def curate(token,dest):
    run=WAVE/'Runs'/token
    execution=load(run/'Evidence/22_wave_start_execution.json')
    assert execution['execution_succeeded'] and execution['cleanup']['all_ui_and_owned_node_checks_passed']
    assert execution['outcome']['last_sample']==555 and execution['drive_authorized']
    dest.mkdir(parents=True,exist_ok=True);(dest/'Original').mkdir(exist_ok=True);(dest/'Executed_Source').mkdir(exist_ok=True)
    records=[]
    files=['pilot_samples','pilot_conditions','static_gate_input','static_gate_remote','checkpoint_gate','drive_authorization',
           'checkpoint_trace','initial_strict_pair','initialization_schema','initialization_schema_comparison',
           'reseed_internal_detail','length6_grid_preflight','off_health_checkpoint','startup_response']
    files += ['deepwater_%03d'%k for k in (0,30,180,270,315,360)]
    files += ['coverage_pair_%03d'%k for k in (0,30,180,270,315,360)]
    for key in files:
        source=run/'Evidence'/('22_'+key+'.json');raw=source.read_bytes()
        compress=len(raw)>100000;target=dest/'Original'/(source.name+('.gz' if compress else ''))
        target.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0) if compress else raw)
        records.append({'path':target.relative_to(dest).as_posix(),'source_sha256':sha(source),'source_bytes':len(raw),
                        'stored_sha256':sha(target),'stored_bytes':target.stat().st_size,'gzip':compress})
    for name,h in execution['source_hashes'].items():
        source=run/'Source'/name;assert sha(source)==h;(dest/'Executed_Source'/name).write_bytes(source.read_bytes())
    samples=load(run/'Evidence/22_pilot_samples.json')['samples']
    gate=load(run/'Evidence/22_checkpoint_gate.json');permission=load(run/'Evidence/22_drive_authorization.json')
    assert sha(run/'Evidence/22_static_gate_input.json')==gate['sample_sha256']==permission['sample_sha256']
    assert load(run/'Evidence/22_static_gate_input.json')['samples']==samples[:361]
    caches=[]
    for r in samples:
        for kind,name,h in [('solver','pilot_%03d.bgeo.sc'%r['sample'],r['cache_sha256']),('PFS','mesh_%03d.bgeo.sc'%r['sample'],r['mesh_file_sha256'])]:
            if h is None:continue
            p=run/'Cache'/name;assert sha(p)==h
            caches.append({'filename':name,'kind':kind,'seconds':r['requested_seconds'],'sha256':h,'bytes':p.stat().st_size})
    for row in load(run/'Evidence/22_length6_grid_preflight.json')['rows']:
        for item in row['saved_geometry']:
            p=run/'Cache'/Path(item['name']).name
            assert sha(p)==item['sha256']
            caches.append({'filename':p.name,'kind':'grid_probe','seconds':row['requested_seconds'],'sha256':sha(p),'bytes':p.stat().st_size})
    assert len(caches)==840 and len({x['filename'] for x in caches})==840
    assert {p.name for p in (run/'Cache').glob('*.bgeo.sc')}=={r['filename'] for r in caches}
    write(dest/'22_cache_manifest.json',{'token':token,'cache_files':caches,'total_files':len(caches),'total_bytes':sum(r['bytes']for r in caches),'all_actual_files_rehashed':True})
    public={k:execution[k] for k in ('token','utc','metadata','clock_initialization','ownership','initial_pair',
            'initialization_schema_comparison','internal_seed_parameters_match_off','drive_authorized','coverage_alert_latched',
            'gate','authorization','outcome','cleanup','source_hashes','execution_succeeded','transport_completion_uncertain')}
    public.update(raw_execution_sha256=sha(run/'Evidence/22_wave_start_execution.json'),rpc_count=len(execution['events']),
                  rpc_sum_seconds=sum(x['rpc_seconds'] for x in execution['events']))
    # 実行順序だけを公開し、ローカルパスを含む全RPC記録は元SHAで結ぶ。
    expected={383:'t6元判定を再評価',384:'同一DOPへ始動を許可',385:'実標本 361'}
    order=[]
    meanings={383:('STATIC_GATE_REEVALUATED','t6の原入力で静水判定を再評価'),384:('SAME_DOP_AUTHORIZED','同じ所有DOPへの始動許可'),385:('SAMPLE_361','許可後の最初の実標本k361')}
    for index,phase in expected.items():
        event=execution['events'][index]
        assert event['phase']==phase and event['executed'] and event['error'] is None and event['eval_error'] is None
        stage,meaning=meanings[index]
        order.append({'event_index_zero_based':index,'stage':stage,'meaning_ja':meaning,
                      'raw_phase_sha256':hashlib.sha256(event['phase'].encode('utf8')).hexdigest(),
                      **{k:event[k] for k in ('executed','error','eval_error')}})
    public['authorization_event_order']={'raw_execution_sha256':public['raw_execution_sha256'],'events':order}
    write(dest/'22_execution_summary.json',public)
    write(dest/'22_original_manifest.json',{'records':records,'meaning_ja':'gzip展開bytesは原JSONと同一。raw BGEOはGのRunsに保持。'})


def analyze(dest):
    records=load(dest/'22_original_manifest.json')['records']
    for r in records:
        p=dest/r['path'];assert sha(p)==r['stored_sha256']
        raw=gzip.decompress(p.read_bytes()) if r['gzip'] else p.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==r['source_sha256']
    def original(short):
        prefix='Original/22_'+short+'.json'
        return load(dest/next(r['path']for r in records if r['path']in(prefix,prefix+'.gz')))
    rows=original('pilot_samples')['samples'];static=original('static_gate_input')['samples']
    assert len(rows)==556 and static==rows[:361]
    response=original('startup_response')
    # 保存した実行時の純関数を再計算し、後から検出規則を調整しない。
    spec=importlib.util.spec_from_file_location('response04_exact',dest/'Executed_Source/startup_response.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    exact=module.analyze_response(rows,response['config'])
    assert exact=={k:v for k,v in response.items()if k!='sample_sha256'}
    csv_path=dest/'22_startup_gauges.csv'
    with csv_path.open('w',encoding='utf8',newline='')as f:
        writer=csv.writer(f,lineterminator='\n');writer.writerow(['sample','seconds','G1_solver_m','G2_solver_m','G3_solver_m','G1_PFS_m','G2_PFS_m','G3_PFS_m','piston_x_m','piston_v_analytic_m_s','piston_v_collision_m_s','particles','PFS_sampled'])
        for r in rows:writer.writerow([r['sample'],r['requested_seconds'],*[g['eta_m']for g in r['gauges']],*[g['mesh_eta_m']for g in r['gauges']],r['piston_displacement_m'],r['piston_velocity_m_s'],r['piston_actual_collision_velocity_m_s'][0],r['particle_count'],r['mesh_sampled']])
    fp=FontProperties(fname=str(FONT));plt.rcParams['font.family']=fp.get_name();plt.rcParams['axes.unicode_minus']=False
    colors=['#165B9A','#CE6B20','#367D49'];times=[r['requested_seconds']for r in rows]
    fig,axes=plt.subplots(3,1,figsize=(12,9),sharex=True)
    for i,ax in enumerate(axes):
        ax.plot(times,[r['gauges'][i]['eta_m']*1000 for r in rows],color=colors[i],label='solver surface 符号場（60Hz）')
        ax.plot([r['requested_seconds']for r in rows if r['mesh_sampled']],[r['gauges'][i]['mesh_eta_m']*1000 for r in rows if r['mesh_sampled']],color=colors[i],ls='--',label='PFS 表示面（30Hz）')
        ax.axvspan(4.5,5.25,color='#aaa',alpha=.12);ax.axvspan(5.25,6,color='#5b9bd5',alpha=.1);ax.axvline(6,color='#222',lw=1)
        ax.set_ylabel('G%d 原水位 [mm]'%(i+1));ax.grid(alpha=.2);ax.legend(loc='lower right',fontsize=9)
    axes[-1].set_xlabel('絶対DOP時刻 [s]');fig.suptitle('22修正04 実FLIP始動診断｜静水再PASS後 t6 で実活塞を始動\n原水位を保持：solver場と表示面の差を補正しない',fontsize=14)
    fig.text(.5,.01,'t9.25で固定終了。PFS終端はt9.2333。定常・無反射・理論精度・番号22完成は未認定。',ha='center',fontsize=10)
    fig.tight_layout(rect=(0,.025,1,.935));fig.savefig(dest/'22_startup_full_series.png',dpi=150,metadata={'Software':'GreatWave WaveStart04'});plt.close(fig)
    fig,axes=plt.subplots(3,1,figsize=(12,9),sharex=True)
    dynamic=[r for r in rows if r['requested_seconds']>=6]
    for i,ax in enumerate(axes):
        g=response['observations']['solver_surface_sign_field']['gauges'][i];mu=g['baseline']['mu_second_window_m'];q=g['baseline']['threshold_m']
        ax.plot([r['requested_seconds']for r in dynamic],[r['gauges'][i]['eta_m']*1000 for r in dynamic],color=colors[i],label='solver 原水位')
        ax.axhspan((mu-q)*1000,(mu+q)*1000,color=colors[i],alpha=.1,label='事前定義 μ±q')
        for feat in g['features']:ax.scatter([feat['time_s']],[feat['raw_eta_m']*1000],c=colors[i],marker='v' if feat['sign']<0 else '^',zorder=5)
        ax.set_ylabel('G%d 原水位 [mm]'%(i+1));ax.grid(alpha=.2);ax.legend(fontsize=9,loc='upper left')
    axes[-1].set_xlabel('絶対DOP時刻 [s]');fig.suptitle('事前規則によるsolver場の谷候補：7.800 → 8.000 → 8.3667 s\nPFSは応答超過あり・唯一の有効特徴鎖なし（別観測）',fontsize=14)
    fig.text(.5,.01,'遅れ .200/.3667 s をそのまま記録。理論 .375 s へ候補選別せず、波速精度へ読み替えない。',ha='center',fontsize=10)
    fig.tight_layout(rect=(0,.025,1,.935));fig.savefig(dest/'22_startup_response.png',dpi=150,metadata={'Software':'GreatWave WaveStart04'});plt.close(fig)
    summary={'sample_count':len(rows),'PFS_count':sum(r['mesh_sampled']for r in rows),'static_gate':original('checkpoint_gate')['evaluation'],
             'response':response,'collision_velocity_max_abs_error_m_s':max(abs(r['piston_actual_collision_velocity_m_s'][0]-r['piston_velocity_m_s'])for r in rows),
             'particle_count_first_last':[rows[0]['particle_count'],rows[-1]['particle_count']],
             'particle_births':sum(len(r['particle_id_births_since_previous'])for r in rows),'particle_deaths':sum(len(r['particle_id_deaths_since_previous'])for r in rows),
             'resources':{'cook_seconds_sum':sum(r['cook_seconds']for r in rows),'maximum_sample_cook_seconds':max(r['cook_seconds']for r in rows),
                          'max_private_bytes':max(r['memory']['private_commit_bytes']for r in rows),'min_available_RAM_bytes':min(r['memory']['available_physical_bytes']for r in rows),
                          'max_DOP_cache_bytes':max(r['simulation_memory_bytes']for r in rows)},
             'analysis_runtime':{'python':sys.version.split()[0],'matplotlib':matplotlib.__version__},
             'font_sha256':sha(FONT),'source_sha256':sha(Path(__file__)),'meaning_ja':'原設定での始動観測。応答有無と静水許可は別。物理精度・主役波・22完了は未認定。'}
    write(dest/'22_startup_summary.json',summary)
    outputs=['22_startup_gauges.csv','22_startup_full_series.png','22_startup_response.png','22_startup_summary.json']
    write(dest/'22_reproduction_manifest.json',{'outputs':[{'path':n,'sha256':sha(dest/n),'bytes':(dest/n).stat().st_size}for n in outputs],
                                              'input_manifest_sha256':sha(dest/'22_original_manifest.json'),'source_sha256':sha(Path(__file__))})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--curate');parser.add_argument('--input',type=Path)
    args=parser.parse_args();dest=args.input or CANDIDATE/'Evidence'/('Result_'+args.curate)
    if args.curate:curate(args.curate,dest)
    analyze(dest)
    print(json.dumps({'result':str(dest),'analysis_completed':True},ensure_ascii=False))
