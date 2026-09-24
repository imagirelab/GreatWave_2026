# -*- coding: utf-8 -*-
"""計算済み表面キャッシュのみを Alembic に書き出す。再シミュレーションしない。"""
import argparse,json,math
from pathlib import Path
import hou
import numpy as np
parser=argparse.ArgumentParser(description='FLIP 計算済み表面を Alembic に変換し、再読込して照合する。')
parser.add_argument('--cache-dir',type=Path,default=Path(__file__).resolve().parent.parent/'results'/'wave_tank'/'本計算01')
args=parser.parse_args();base=args.cache_dir.resolve()
metrics=json.loads((base/'計測.json').read_text(encoding='utf-8'));last=metrics['フレーム別'][-1]['フレーム']
for frame in range(1,last+1):
 if not (base/'surface'/f'water_{frame:04d}.bgeo.sc').is_file():raise RuntimeError('表面キャッシュが不足している。')
abc=base/f'FLIP波槽_{last}フレーム.abc'
if abc.exists():raise RuntimeError('既存の Alembic は上書きしない。')
hou.setFps(metrics['条件']['fps']);hou.playbar.setFrameRange(1,last);hou.playbar.setPlaybackRange(1,last)
hou.hipFile.setName(str(base/'表面キャッシュ確認.hiplc'))
g=hou.node('/obj').createNode('geo','cached_surface');g.setComment('保存済みの計算結果。物理計算を再実行しない。')
for child in g.children():child.destroy()
f=g.createNode('file','surface_cache');f.parm('file').set('$HIP/surface/water_$F4.bgeo.sc')
c=g.createNode('convert','polygon_surface');c.setInput(0,f);c.setDisplayFlag(True);c.setRenderFlag(True)
w=hou.node('/out').createNode('alembic','export_surface');w.setComment('実際の FLIP 粒子から再構成した表面の書き出し。')
w.setParms({'filename':'$HIP/'+abc.name,'use_sop_path':1,'sop_path':c.path(),'trange':1,'initsim':0});w.parmTuple('f').set((1,last,1))
w.render(frame_range=(1,last),verbose=False)
rgeo=hou.node('/obj').createNode('geo','readback');rgeo.setDisplayFlag(False)
r=rgeo.createNode('alembic','readback_surface');r.parm('fileName').set('$HIP/'+abc.name)
r.parm('loadmode').set(next(i for i,label in enumerate(r.parm('loadmode').menuLabels()) if 'houdini' in label.lower() and 'geometry' in label.lower()))
if r.parm('polysoup'):r.parm('polysoup').set(0)
checks=[]
for frame in sorted(set([1,min(24,last),min(48,last),last])):
 hou.setFrame(frame);c.cook(force=True);r.cook(force=True)
 a=np.asarray(c.geometry().pointFloatAttribValues('P')).reshape(-1,3);b=np.asarray(r.geometry().pointFloatAttribValues('P')).reshape(-1,3)
 if a.shape!=b.shape:raise RuntimeError('再読込した頂点数が一致しない。')
 error=float(np.max(np.linalg.norm(a-b,axis=1)))
 if error>1e-5:raise RuntimeError('再読込した座標が一致しない。')
 checks.append({'フレーム':frame,'頂点数':len(a),'ポリゴン数':len(r.geometry().prims()),'最大座標誤差_m':error,'境界箱最小_m':b.min(axis=0).tolist(),'境界箱最大_m':b.max(axis=0).tolist()})
result={'Houdiniバージョン':hou.applicationVersionString(),'ライセンス種別':str(hou.licenseCategory()),'対象':abc.name,'容量_byte':abc.stat().st_size,'フレーム範囲':[1,last],'FPS':hou.fps(),'座標':'右手系、Y が上、X 正方向に進行、単位 m。','再読込照合':checks,'注意':'FLIP 計算結果の入出力検証。砕波の成立、物理的収束、Unity と HMD はこの照合だけでは証明できない。'}
(base/'Alembic照合.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
hou.setFrame(1);hou.hipFile.save(str(base/'表面キャッシュ確認.hiplc'))
print(json.dumps(result,ensure_ascii=False),flush=True)
