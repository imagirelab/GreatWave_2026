"""採録済みの静水対照を比較する。解像度の収束合格や水量保存とは解釈しない。"""
import hashlib
import json
import statistics
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

ROOT=Path(__file__).resolve().parents[1]
FONT=Path('C:/Windows/Fonts/meiryo.ttc')
font=FontProperties(fname=str(FONT))
plt.rcParams['font.family']=font.get_name()
plt.rcParams['axes.unicode_minus']=False
cases=[('e1db8acb19',.04,2.),('834a7ff1e4',.04,1.5),('b7f667229f',.04,1.25),('999de0692e',.03,1.5)]
fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained')
rows=[]
for token,dp,grid in cases:
 path=ROOT/'Evidence/Curated_Runs'/token/'22_pilot_samples.json'
 data=json.loads(path.read_text(encoding='utf8'))['samples']
 assert len(data)==31 and all(r['piston_displacement_m']==0 for r in data)
 t=[r['requested_seconds'] for r in data]
 label=f'dp={dp:.2f} m / Grid Scale={grid:g}'
 for g in range(2):axes[0,g].plot(t,[r['gauges'][g]['eta_m']*1000 for r in data],label=label)
 axes[1,0].plot(t,[r['particle_count'] for r in data],label=label)
 axes[1,1].plot(t,[r['negative_voxel_volume_proxy_m3'] for r in data],label=label)
 rows.append({'token':token,'particle_separation_m':dp,'grid_scale':grid,'expected_solver_voxel_m':dp*grid,
              'sample_count':31,'initial_particles':data[0]['particle_count'],'final_particles':data[-1]['particle_count'],
              'max_abs_eta_m':[max(abs(r['gauges'][g]['eta_m']) for r in data) for g in range(2)],
              'final_eta_m':[r['eta_m'] for r in data[-1]['gauges']],
              'cook_median_s':statistics.median(r['cook_seconds'] for r in data),
              'source_file':str(path.relative_to(ROOT)).replace('\\','/'),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
for g in range(2):
 axes[0,g].set(title=f'実ソルバー SDF ゲージ G{g+1}（基線補正なし）',ylabel='水面 y [mm]')
 axes[0,g].axhline(-3,color='gray',ls='--',lw=.8)
axes[1,0].set(title='実粒子数（質量ではない）',ylabel='粒子数')
axes[1,1].set(title='負の SDF セル体積代理量（水量ではない）',ylabel='未クリップ代理量 [m³]')
for ax in axes.flat:
 ax.set_xlabel('絶対 DOP 時刻 [s]');ax.grid(alpha=.25);ax.legend(fontsize=8)
fig.suptitle('手順22：実 FLIP 静水対照 ／ 進行波・物理精度は未検証\n初期粒子配置も変化するため、圧力格子だけの因果比較ではない',fontsize=14)
dest=ROOT/'Evidence/Static_Comparison';dest.mkdir(exist_ok=True)
fig.savefig(dest/'22_static_comparison.png',dpi=130)
out={'scope_ja':'4条件の初期過渡。粒子数・初期配置・SDF格子が同時に変化。恒常偏差を差し引いていない。',
     'wave_propagation_verified':False,'physical_convergence_verified':False,'cases':rows,
     'font_sha256':hashlib.sha256(FONT.read_bytes()).hexdigest(),
     'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
     'image_sha256':hashlib.sha256((dest/'22_static_comparison.png').read_bytes()).hexdigest()}
(dest/'22_static_comparison.json').write_bytes((json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
print(str(dest))
