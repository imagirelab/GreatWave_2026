"""公開原JSONから未補正断面・元04判定内訳を再計算する。Houdini/MCP不使用。"""
import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import statistics
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

FONT=Path('C:/Windows/Fonts/meiryo.ttc')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
    raw=p.read_bytes();return json.loads(gzip.decompress(raw)if p.suffix=='.gz'else raw)
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))
def range_of(v):return [min(v),max(v)]
def module(p,name):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def original_candidates(series,config,original_module,rate):
    """元inspect_seriesと同じ候補の採否に、左右値と不採用理由を添える。"""
    baseline=original_module.baseline_threshold(series);mu=baseline['mu_second_window_m'];q=baseline['threshold_m']
    selected=[(t,v)for t,v in series if config['primary_window_s'][0]<=t<=config['primary_window_s'][1]]
    times=[t for t,v in selected];raw=[v for t,v in selected]
    smooth={i:statistics.mean(raw[i-2:i+3])for i in range(2,len(raw)-2)};radius=config['extremum_neighbourhood_s'];out=[]
    for i in range(3,len(raw)-3):
        sign=1 if smooth[i]>smooth[i-1]and smooth[i]>=smooth[i+1]else(-1 if smooth[i]<smooth[i-1]and smooth[i]<=smooth[i+1]else 0)
        if not sign:continue
        left=[j for j in smooth if times[i]-radius<=times[j]<times[i]];right=[j for j in smooth if times[i]<times[j]<=times[i]+radius]
        complete=times[i]-radius>=times[2]and times[i]+radius<=times[-3]
        lp=sign*smooth[i]-min(sign*smooth[j]for j in left);rp=sign*smooth[i]-min(sign*smooth[j]for j in right)
        li=min(left,key=lambda j:sign*smooth[j]);ri=min(right,key=lambda j:sign*smooth[j])
        amplitude=sign*(raw[i]-mu);eligible=amplitude>=q and complete and min(lp,rp)>=q
        out.append({'time_s':times[i],'sign':sign,'raw_eta_m':raw[i],'smoothed_eta_m':smooth[i],
                    'raw_signed_deviation_m':raw[i]-mu,'raw_amplitude_along_extremum_sign_m':amplitude,'q_m':q,
                    'left_prominence_m':lp,'right_prominence_m':rp,'two_sided_prominence_m':min(lp,rp),
                    'left_reference_time_s':times[li],'left_reference_eta_m':smooth[li],
                    'right_reference_time_s':times[ri],'right_reference_eta_m':smooth[ri],
                    'left_support_times_s':[times[j]for j in left],'right_support_times_s':[times[j]for j in right],
                    'complete_support':complete,'eligible_original_rules':eligible,
                    'reasons':(["RAW_AMPLITUDE_BELOW_Q"]if amplitude<q else[])+(["TRUNCATED_SUPPORT"]if not complete else[])+(["PROMINENCE_BELOW_Q"]if min(lp,rp)<q else[])})
    actual=original_module.inspect_series(series,config,rate)
    assert [(x['time_s'],x['sign'],x['two_sided_prominence_m'])for x in out if x['eligible_original_rules']]==[(x['time_s'],x['sign'],x['two_sided_prominence_m'])for x in actual['features']]
    return out,selected,smooth

def analyze(source,output):
    output.mkdir(parents=True,exist_ok=True);manifest=load(source/'22_profile05_original_manifest.json')
    for r in manifest['records']:
        p=source/r['path'];assert sha(p)==r['stored_sha256']and p.stat().st_size==r['stored_bytes']
        raw=gzip.decompress(p.read_bytes())if r['gzip']else p.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==r['source_sha256']and len(raw)==r['source_bytes']
    core=module(source/'Executed_Source/profile_core.py','profile05_frozen_core')
    detector=module(source/'Baseline04/Executed_Source/startup_response.py','profile05_original_detector')
    rows=load(source/'Baseline04/Original/22_pilot_samples.json.gz')['samples'];response=load(source/'Baseline04/Original/22_startup_response.json')
    assert detector.analyze_response(rows,response['config'])=={k:v for k,v in response.items()if k!='sample_sha256'}
    plan=load(source/'Executed_Source/profile05_plan.json');flat=[];pair_reports=[];quad_values=[];top_normals=[];bottom_normals=[];top_heights=[];bottom_heights=[]
    count={'profiles':0,'phi_queries':0,'single_wet_to_dry':0,'zero_plateau':0,'tangent_zero':0,'strict_hits':0,'sensitivity_hits':0,'incidences':0,'center_pairs':0}
    errors={'center_mesh_m':0.,'center_solver_m':0.,'default_vs_strict_m':0.,'strict_vs_sensitivity_m':0.,'strict_pattern_height_m':0.,'pattern_strict_height_m':0.}
    for record in [r for r in manifest['records']if r['kind']=='profile']:
        d=load(source/record['path']);assert d['center_parity_passed']and d['strict_incidence_consistency_passed']and d['ui_metadata_unchanged']
        pair_reports.append({'sample':d['sample'],'read_seconds':d['read_seconds'],'json_bytes':record['source_bytes'],'min_available_RAM_bytes':d['memory_guard']['min_available_bytes'],
                             'ui_metadata_before_after':d['ui_metadata_before_after'],'field':d['field'],'result_sha256':record['source_sha256']})
        for p in d['profiles']:
            a=p['strict_distinct_height_hits']['hits'];b=p['sensitivity_distinct_height_hits']['hits'];inc=p['unmerged_primitive_incidences'];f=p['field_profile']
            assert len(a)==len(b)==len(inc)==2
            consistency=core.incidence_consistency(a,inc,plan['intersection']['strict_incidence_height_tolerance_m'],p['native_default_first']is not None)
            assert consistency==p['strict_incidence_consistency']and consistency['passed']
            assert all(math.isfinite(v)for v in f['phi'])and f['single_wet_to_dry_local']and f['height_m']is not None
            count['profiles']+=1;count['phi_queries']+=len(f['phi']);count['single_wet_to_dry']+=f['single_wet_to_dry_local'];count['zero_plateau']+=f['zero_plateau_detected'];count['tangent_zero']+=bool(f['tangent_zero_indices'])
            count['strict_hits']+=len(a);count['sensitivity_hits']+=len(b);count['incidences']+=len(inc)
            errors['default_vs_strict_m']=max(errors['default_vs_strict_m'],abs(p['native_default_first_y_m']-a[0]['position_m'][1]))
            errors['strict_vs_sensitivity_m']=max(errors['strict_vs_sensitivity_m'],max(abs(x['position_m'][1]-y['position_m'][1])for x,y in zip(a,b)))
            errors['strict_pattern_height_m']=max(errors['strict_pattern_height_m'],max(x['minimum_height_error_m']for x in consistency['strict_hit_comparisons']))
            errors['pattern_strict_height_m']=max(errors['pattern_strict_height_m'],max(x['minimum_strict_height_error_m']for x in consistency['incidence_height_comparisons']))
            if 'center_parity_passed'in p:
                count['center_pairs']+=1;errors['center_mesh_m']=max(errors['center_mesh_m'],abs(p['center_mesh_error_m']));errors['center_solver_m']=max(errors['center_solver_m'],abs(p['center_solver_error_m']))
            for h in inc:
                v=h['quad_diagonal_sensitivity'].get('absolute_difference_m')
                if v is not None:quad_values.append(v)
            top_normals.append(a[0]['normal'][1]);bottom_normals.append(a[1]['normal'][1]);top_heights.append(a[0]['position_m'][1]);bottom_heights.append(a[1]['position_m'][1])
            flat.append({'sample':d['sample'],'seconds':d['seconds'],'gauge':p['gauge'],'x_m':p['x_m'],'dx_m':p['dx_m'],'z_m':p['z_m'],
                         'solver_profile_eta_m':f['height_m'],'single_wet_to_dry_local':f['single_wet_to_dry_local'],
                         'PFS_native_first_eta_m':p['native_default_first_y_m'],'PFS_strict_upper_eta_m':a[0]['position_m'][1],
                         'PFS_strict_lower_eta_m':a[1]['position_m'][1],'upper_normal_y':a[0]['normal'][1],'lower_normal_y':a[1]['normal'][1],
                         'PFS_minus_field_m':p['native_default_first_y_m']-f['height_m'],
                         'original_solver_eta_m':p.get('center_original_gauge_replay',{}).get('eta_m'),
                         'original_mesh_error_m':p.get('center_mesh_error_m'),'original_solver_error_m':p.get('center_solver_error_m')})
    assert len(pair_reports)==30 and count['profiles']==5850
    with(output/'22_profile05_sections.csv').open('w',encoding='utf8',newline='')as stream:
        writer=csv.DictWriter(stream,fieldnames=list(flat[0]),lineterminator='\n');writer.writeheader();writer.writerows(flat)
    offsets={};spatial={}
    for g in range(1,4):
        centers=[p for p in flat if p['gauge']==g and p['dx_m']==p['z_m']==0]
        offsets[str(g)]={'PFS_minus_original_solver_m':range_of([p['PFS_native_first_eta_m']-p['original_solver_eta_m']for p in centers])}
        spatial[str(g)]={}
        for axis in('x','z'):
            fields={'PFS_native_first_eta_m':[],'solver_profile_eta_m':[]}
            for k in range(468,527,2):
                selected=[p for p in flat if p['sample']==k and p['gauge']==g and(p['z_m']==0 if axis=='x'else p['dx_m']==0)]
                for key in fields:fields[key].append(max(p[key]for p in selected)-min(p[key]for p in selected))
            spatial[str(g)][axis+'_range_m']={key:range_of(values)for key,values in fields.items()}
    candidate_records=[];series_data={}
    for label,field,rate in [('solver_surface_sign_field','eta_m',60),('PFS_display_surface','mesh_eta_m',30)]:
        for g in range(3):
            series=[(r['requested_seconds'],r['gauges'][g][field])for r in rows if field=='eta_m'or r['mesh_sampled']]
            candidates,selected,smooth=original_candidates(series,response['config'],detector,rate)
            candidate_records.extend({'observable':label,'gauge':g+1,**v}for v in candidates)
            series_data[label,g+1]=(selected,smooth)
    g3={label:next(r for r in candidate_records if r['observable']==label and r['gauge']==3 and r['sign']==-1 and abs(r['time_s']-t)<1e-8)
        for label,t in [('PFS_display_surface',8.266666666666667),('solver_surface_sign_field',8.366666666666667)]}
    temporal=[];lookup={(p['sample'],p['gauge'],round(p['dx_m'],6),round(p['z_m'],6)):p for p in flat}
    for key,p in lookup.items():
        next_key=(key[0]+2,)+key[1:]
        if next_key in lookup:
            q=lookup[next_key];temporal.append({'from_sample':key[0],'gauge':key[1],'dx_m':key[2],'z_m':key[3],
              'PFS_difference_m':q['PFS_native_first_eta_m']-p['PFS_native_first_eta_m'],'field_difference_m':q['solver_profile_eta_m']-p['solver_profile_eta_m']})
    executions=[load(source/r['path'])for r in manifest['records']if r['kind']=='execution']
    summary={'baseline_run':'22e7801642','diagnostic_sample_interval':[468,526,2],'pair_count':30,'counts':count,'maximum_errors':errors,
             'center_offsets':offsets,'spatial_ranges':spatial,'G3_original_candidates':g3,'all_original_candidates':candidate_records,
             'adjacent_temporal_differences':{'count':len(temporal),'dt_s':1/30,
              'PFS_maximum_absolute_entry':max(temporal,key=lambda r:abs(r['PFS_difference_m'])),
              'field_maximum_absolute_entry':max(temporal,key=lambda r:abs(r['field_difference_m'])),
              'meaning_ja':'同じ登録列の離散時間差。両最大値の位置は別であり比率を減幅係数としない。'},
             'mesh_intersections':{'upper_height_range_m':range_of(top_heights),'lower_height_range_m':range_of(bottom_heights),
                                   'upper_normal_y_range':range_of(top_normals),'lower_normal_y_range':range_of(bottom_normals),
                                   'meaning_ja':'各rayの上側/下側交点を区別。二層の自由水面と呼ばない。'},
             'quad_diagnostic':{'count':len(quad_values),'max_two_diagonals_height_difference_m':max(quad_values),
                                'at_least_0p1mm':sum(v>=.0001 for v in quad_values),'at_least_1mm':sum(v>=.001 for v in quad_values),
                                'projected_convexity_checked':False,'cause_certified':False},
             'resource':{'read_seconds_total':sum(r['read_seconds']for r in pair_reports),'read_seconds_range':range_of([r['read_seconds']for r in pair_reports]),
                         'rpc_seconds_total':sum(v['rpc_seconds']for e in executions for v in e['events']),
                         'min_available_RAM_bytes':min(r['min_available_RAM_bytes']for r in pair_reports),
                         'profile_json_total_bytes':manifest['profile_source_bytes'],'profile_gzip_total_bytes':manifest['profile_gzip_bytes'],
                         'largest_json_bytes':max(r['json_bytes']for r in pair_reports)},
             'pair_reports':pair_reports,'solver_executed':False,'nodes_created':False,'UI_metadata_unchanged':True,'transport_completion_uncertain':False,
             'all_original_response_results_unchanged':True,'smoothing_support_seconds':{'solver':4/60,'PFS':4/30},
             'interpretation_ja':['局所読戻し内で、既定first-hit/主query/感度queryの高さは一致した。容差や別層の選択でこの観測差を説明する証拠は得なかった。',
                                  'PFSとsolver符号場の絶対差は位置・時刻により変わる。定数10mm補正はしていない。',
                                  '5点平滑の時間幅、面再構成、格子が異なる。今回だけでは減幅の単一原因や空間平滑を特定しない。'],
             'physical_accuracy_verified':False,'wave_verified':False,'step22_complete':False}
    write(output/'22_profile05_summary.json',summary)
    figures(output,flat,rows,g3,series_data,plan)
    files=['22_profile05_sections.csv','22_profile05_summary.json','22_profile05_centers.png','22_profile05_sections.png','22_profile05_G3_prominence.png']
    write(output/'22_profile05_analysis_manifest.json',{'input_manifest_sha256':sha(source/'22_profile05_original_manifest.json'),
          'analysis_source_sha256':sha(Path(__file__)),'font_sha256':sha(FONT),'matplotlib_version':matplotlib.__version__,
          'outputs':[{'path':name,'sha256':sha(output/name),'bytes':(output/name).stat().st_size}for name in files],
          'meaning_ja':'公開gzipだけから再計算。BGEO再検証やHoudini実行は含まない。'})
    print(json.dumps({'profiles':len(flat),'outputs':len(files),'houdini_called':False}))

def figures(output,flat,rows,g3,series_data,plan):
    font_manager.fontManager.addfont(str(FONT));plt.rcParams.update({'font.family':font_manager.FontProperties(fname=str(FONT)).get_name(),'font.size':10,'axes.unicode_minus':False})
    def finish(fig,name,title,footer):
        fig.suptitle(title,fontsize=15,y=.985);fig.text(.03,.02,footer,fontsize=9);fig.tight_layout(rect=(.015,.075,.99,.95));fig.savefig(output/name,dpi=160,metadata={'Software':'GreatWave profile05'});plt.close(fig)
    fig,axes=plt.subplots(3,2,figsize=(14,9))
    for i in range(3):
        a,b=axes[i];a.plot([r['requested_seconds']for r in rows if r['requested_seconds']>=6],[r['gauges'][i]['eta_m']*1000 for r in rows if r['requested_seconds']>=6],color='#007c91',label='solver符号場 60Hz')
        a.plot([r['requested_seconds']for r in rows if r['mesh_sampled']and r['requested_seconds']>=6],[r['gauges'][i]['mesh_eta_m']*1000 for r in rows if r['mesh_sampled']and r['requested_seconds']>=6],color='#bc4b00',label='PFS既定交点 30Hz')
        a.axvspan(7.8,526/60,alpha=.12,color='#446688');a.set(title=f'G{i+1} 未補正の原水位',ylabel='高さ [mm]');a.grid(alpha=.25)
        centers=[p for p in flat if p['gauge']==i+1 and p['dx_m']==p['z_m']==0]
        b.plot([p['seconds']for p in centers],[(p['PFS_native_first_eta_m']-p['original_solver_eta_m'])*1000 for p in centers],'.-',color='#633c8b');b.set(title=f'G{i+1} 同30Hz時刻の定義差',ylabel='PFS − solver [mm]');b.grid(alpha=.25)
        if i==0:a.legend(loc='lower left',fontsize=9)
    for a in axes[-1]:a.set_xlabel('絶対DOP時刻 [s]')
    finish(fig,'22_profile05_centers.png','22修正05｜04の実計算cacheを読む：原水位と表示面の差',
           '実測：Run22e7801642。青帯内の30配対をBGEOから再読込。右列の差は診断値で水位補正ではない。\n新規solver計算なし／近傍に元検出閾値を移植しない／波の完成・精度・減幅原因は未認定。')
    fig,axes=plt.subplots(3,2,figsize=(14,10))
    for g in range(1,4):
        for col,axis in enumerate(('x','z')):
            a=axes[g-1,col]
            for k,style in[(496,'-'),(502,'--')]:
                pts=sorted([p for p in flat if p['sample']==k and p['gauge']==g and(p['z_m']==0 if axis=='x'else p['dx_m']==0)],key=lambda p:p['dx_m']if axis=='x'else p['z_m'])
                abscissa=[(p['dx_m']if axis=='x'else p['z_m'])*1000 for p in pts]
                a.plot(abscissa,[p['solver_profile_eta_m']*1000 for p in pts],style,color='#007c91',marker='.',label=f'solver t={k/60:.4f}')
                a.plot(abscissa,[p['PFS_native_first_eta_m']*1000 for p in pts],style,color='#bc4b00',marker='.',label=f'PFS t={k/60:.4f}')
            a.set(title=f'G{g}（x={plan["gauge_x_m"][g-1]:.6f}m） '+('z=0のx断面'if axis=='x'else '中央xのz断面'),ylabel='原高さ [mm]',xlabel=('測点からのx差 [mm]'if axis=='x'else 'z [mm]'));a.grid(alpha=.25)
            if g==1 and col==0:a.legend(fontsize=8,ncol=2,loc='upper right')
    finish(fig,'22_profile05_sections.png','22修正05｜同じ実cacheの局所断面：solver符号交差とPFS上側交点',
           '実測BGEO：k496(t8.266667)とk502(t8.366667)。元04の既知G3谷候補2時刻を選んだ診断図。y軸は高さをmm表示、未補正。\nsolverは単一wet→dry確認行のみ。下側mesh面は自由水面として描かない。有限の線標本は全域連通・空間平滑の原因を証明しない。')
    fig,axes=plt.subplots(2,1,figsize=(12,8))
    for a,label,name,color in zip(axes,('solver_surface_sign_field','PFS_display_surface'),('solver符号場 60Hz','PFS表示面 30Hz'),('#007c91','#bc4b00')):
        selected,smooth=series_data[label,3];c=g3[label];ts=[t for t,v in selected];ys=[v for t,v in selected]
        a.plot(ts,[v*1000 for v in ys],'.-',color=color,alpha=.55,label='原高さ');a.plot([ts[i]for i in smooth],[smooth[i]*1000 for i in smooth],color=color,lw=2,label='元04の5点平滑')
        a.axvspan(c['time_s']-.375,c['time_s']+.375,color=color,alpha=.08);a.plot(c['time_s'],c['smoothed_eta_m']*1000,'v',color='black')
        for side in('left','right'):
            a.plot([c['time_s'],c[side+'_reference_time_s']],[c['smoothed_eta_m']*1000,c[side+'_reference_eta_m']*1000],':',color='#555555',lw=1)
        a.set_xlim(7.75,8.85);a.grid(alpha=.25);a.set(title=f'{name}  谷候補 t={c["time_s"]:.6f}s｜左右prominence {c["left_prominence_m"]*1000:.4f} / {c["right_prominence_m"]*1000:.4f} mm',ylabel='原高さ [mm]',xlabel='絶対DOP時刻 [s]');a.legend(fontsize=9)
        a.text(.015,.045,f'q=1mm、元規則 '+('採用'if c['eligible_original_rules']else '不採用')+f'／raw振幅 {c["raw_amplitude_along_extremum_sign_m"]*1000:.4f}mm',transform=a.transAxes,fontsize=10)
    finish(fig,'22_profile05_G3_prominence.png','22修正05｜G3候補の不採用理由：原04の全時系列・規則を保持',
           '背景帯は各候補の±0.375秒。局所読戻し窓で判定し直さず、04全時系列から原検出を完全再現。\n5点の時間幅はsolver 4/60秒、PFS 4/30秒で異なる。固定高さ補正なし／この差を空間再構成だけの因果としない。')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path);a=p.parse_args();analyze(a.input,a.output or a.input)
