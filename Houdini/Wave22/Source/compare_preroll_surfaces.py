"""同時刻のsolver SDFと表示meshを別観測として比較する。元の停止判定は変えない。"""
import csv
import hashlib
import io
import json
import math
import statistics
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

ROOT=Path(__file__).resolve().parents[1]
TOKEN='0652da0179'
SOURCE=ROOT/'Evidence/Curated_Runs'/TOKEN/'22_pilot_samples.json'
rows=json.loads(SOURCE.read_text(encoding='utf8'))['samples']
font=Path('C:/Windows/Fonts/meiryo.ttc')
plt.rcParams['font.family']=FontProperties(fname=str(font)).get_name()
plt.rcParams['axes.unicode_minus']=False

def metrics(t,y):
 avg=statistics.mean(y);mt=statistics.mean(t)
 slope=sum((a-mt)*(b-avg) for a,b in zip(t,y))/sum((a-mt)**2 for a in t)
 return {'count':len(t),'mean_m':avg,'rms_about_mean_m':math.sqrt(statistics.mean((v-avg)**2 for v in y)),
         'slope_m_s':slope,'trend_change_per_075s_m':slope*.75}

fig,axes=plt.subplots(3,1,figsize=(12,10),layout='constrained',sharex=True)
comparison=[]
for i,ax in enumerate(axes):
 t=[r['requested_seconds'] for r in rows];sdf=[r['gauges'][i]['eta_m'] for r in rows]
 meshrows=[r for r in rows if r['mesh_sampled']]
 ax.plot(t,[v*1000 for v in sdf],label='solver SDF ゼロ交差（60 Hz）')
 ax.plot([r['requested_seconds'] for r in meshrows],[r['gauges'][i]['mesh_eta_m']*1000 for r in meshrows],ls='--',label='表示 PFS mesh の最初の縦線交差（30 Hz）')
 ax.axvspan(1.5,2.25,alpha=.12,color='green');ax.axvspan(2.25,3,alpha=.12,color='orange')
 ax.set(ylabel='未補正 y [mm]',title=f'診断測点 {i+1}：x={rows[0]["gauges"][i]["x"]:.6f} m')
 ax.legend(loc='lower left',fontsize=9);ax.grid(alpha=.25)
 groups=[]
 for a,b in ((1.5,2.25),(2.25,3.0)):
  matched=[r for r in meshrows if a<r['requested_seconds']<=b]
  tt=[r['requested_seconds'] for r in matched]
  groups.append({'left_open_s':a,'right_closed_s':b,
                 'sdf_at_mesh_times':metrics(tt,[r['gauges'][i]['eta_m'] for r in matched]),
                 'mesh':metrics(tt,[r['gauges'][i]['mesh_eta_m'] for r in matched])})
 comparison.append({'gauge_index':i+1,'windows':groups})
axes[-1].set_xlabel('絶対 DOP 時刻 [s]（ピストン変位は全標本0）')
fig.suptitle('手順22 中間結果：実 FLIP 静水 ／ 進行波は未完成\n事前登録した SDF 安定判定条件は不合格。mesh の傾向で合否を置き換えない。',fontsize=14)
DEST=ROOT/'Evidence/Preroll_0652da0179';DEST.mkdir(exist_ok=True)
fig.savefig(DEST/'22_preroll_sdf_mesh.png',dpi=130)
table=io.StringIO(newline='');w=csv.writer(table,lineterminator='\n')
w.writerow(['sample','absolute_dop_seconds','actual_dop_seconds','particle_count','particle_velocity_rms_m_s','negative_sdf_voxel_proxy_m3']+[f'g{i+1}_{name}' for i in range(3) for name in ('solver_eta_m','mesh_eta_m','mesh_sampled')])
for r in rows:
 w.writerow([r['sample'],r['requested_seconds'],r['simulation_seconds'],r['particle_count'],r['particle_velocity_rms_m_s'],r['negative_voxel_volume_proxy_m3']]+[v for g in r['gauges'] for v in (g['eta_m'],g['mesh_eta_m'],r['mesh_sampled'])])
(DEST/'22_preroll_gauges.csv').write_bytes(table.getvalue().encode('utf8'))
report={'scope_ja':'同時刻の30Hz表示meshとsolver SDFの傾向比較。元の60Hz SDF判定条件は不合格のまま。meshは主水柱との連結・体積を証明しない。',
        'windows':comparison,'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'font_sha256':hashlib.sha256(font.read_bytes()).hexdigest()}
(DEST/'22_preroll_mesh_comparison.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
print(str(DEST))
