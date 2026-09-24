"""実SDFゲージの駆動あり/なしを同時刻で比較する。波高を補正しない。"""
import hashlib, json, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

ROOT=Path(__file__).resolve().parents[1]
def source(token):
 p=ROOT/'Evidence/Curated_Runs'/token/'22_pilot_samples.json'
 return p if p.exists() else ROOT/'Runs'/token/'Evidence/22_pilot_samples.json'
DRIVE=source(sys.argv[1]);STATIC=source(sys.argv[2])
OUT=ROOT/'Evidence'/('Compare_'+sys.argv[1]+'_'+sys.argv[2]);OUT.mkdir(parents=True,exist_ok=True)
def read(root):return json.loads(root.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
a=read(DRIVE)['samples'];b=read(STATIC)['samples'];common=min(len(a),len(b))
assert all(abs(a[k]['requested_seconds']-b[k]['requested_seconds'])<1e-12 for k in range(common))
differences=[[a[k]['gauges'][g]['eta_m']-b[k]['gauges'][g]['eta_m'] for k in range(common)] for g in range(2)]
report={'classification':'REAL_SOLVER_PILOT_NOT_TRAVELING_WAVE_ACCEPTANCE','driven_run':sys.argv[1],'static_run':sys.argv[2],'common_samples':common,'common_end_seconds':a[common-1]['requested_seconds'],'max_absolute_drive_minus_static_m':[max(map(abs,d)) for d in differences],'baseline_subtracted_wave_claim':False,'static_end_eta_m':[q['eta_m'] for q in b[-1]['gauges']],'static_max_abs_eta_m':[max(abs(x['gauges'][g]['eta_m']) for x in b) for g in range(2)],'sources':[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p)} for p in (DRIVE,STATIC)],'script_sha256':sha(Path(__file__))}
(OUT/'comparison.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
font=FontProperties(fname=r'C:\Windows\Fonts\meiryo.ttc');plt.rcParams['font.family']=font.get_name()
fig,axs=plt.subplots(2,2,figsize=(13,7),layout='constrained');fig.suptitle('第22号・実FLIPの接続試験 — 初期過渡の比較（伝播波の合格ではない）',fontsize=16)
for g,ax in enumerate(axs[0]):
 for rows,label,color in ((a,'ピストン駆動あり','#1678ac'),(b,'ピストン停止','#dd7c24')):
  ax.plot([x['requested_seconds'] for x in rows],[x['gauges'][g]['eta_m']*1000 for x in rows],label=label,color=color)
 ax.axhline(0,color='grey',lw=.5);ax.set(title=f'実solver SDF ゲージ {g+1}',xlabel='実DOP時刻 [s]',ylabel='未補正の水面位置 [mm]');ax.legend();ax.grid(alpha=.2)
ax=axs[1,0]
for g,d in enumerate(differences):ax.plot([x['requested_seconds'] for x in a[:common]],np.asarray(d)*1000,label=f'ゲージ {g+1}')
ax.set(title='同時刻の駆動あり − 停止（原因の切分けのみ）',xlabel='実DOP時刻 [s]',ylabel='差 [mm]');ax.legend();ax.grid(alpha=.2)
ax=axs[1,1]
for rows,label in ((a,'駆動あり'),(b,'停止')):ax.plot([x['requested_seconds'] for x in rows],[x['negative_voxel_volume_proxy_m3'] for x in rows],label=label)
ax.set(title='負SDF voxel 数 × voxel体積（粗いproxy）',xlabel='実DOP時刻 [s]',ylabel='proxy [m³]');ax.legend();ax.grid(alpha=.2)
fig.text(.01,-.025,'0.04m粒子間隔・0.08m solver voxel。表示mesh・粒子数から質量保存を認定せず、基線を差し引いて目標水深へ合わせない。',fontsize=10)
fig.savefig(OUT/'22_pilot_comparison.png',dpi=140,bbox_inches='tight');plt.close(fig)
print(json.dumps(report,ensure_ascii=False))
