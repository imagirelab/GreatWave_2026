# -*- coding: utf-8 -*-
"""計算済み表面キャッシュのみを Alembic に書き出す。再シミュレーションしない。"""
import argparse,json,math
from pathlib import Path
import hou
import numpy as np
parser=argparse.ArgumentParser(description='白波計算済みメッシュを Alembic に変換し、再読込して照合する。')
parser.add_argument('--cache-dir',type=Path,default=Path(__file__).resolve().parent.parent.parent/'results'/'reference_release'/'whitewater'/'試行01')
parser.add_argument('--verify-only',action='store_true',help='既存 Alembic を上書きせず再読込だけ確認する。')
args=parser.parse_args();base=args.cache_dir.resolve()
metrics=json.loads((base/'計測.json').read_text(encoding='utf-8'));last=metrics['フレーム別'][-1]['フレーム'];first=metrics['フレーム別'][0]['フレーム']
for frame in range(first,last+1):
 if not (base/'mesh'/f'whitewater_{frame:04d}.bgeo.sc').is_file():raise RuntimeError('表面キャッシュが不足している。')
abc=base/f'白波_{first}から{last}フレーム.abc'
if abc.exists() and not args.verify_only:raise RuntimeError('既存の Alembic は上書きしない。')
if args.verify_only and not abc.exists():raise RuntimeError('確認対象の Alembic がない。')
hou.setFps(metrics['条件']['fps']);hou.playbar.setFrameRange(first,last);hou.playbar.setPlaybackRange(first,last)
hou.hipFile.setName(str(base/'白波キャッシュ確認.hiplc'))
g=hou.node('/obj').createNode('geo','cached_surface');g.setComment('保存済みの計算結果。物理計算を再実行しない。')
for child in g.children():child.destroy()
f=g.createNode('file','surface_cache');f.parm('file').set('$HIP/mesh/whitewater_$F4.bgeo.sc')
c=g.createNode('convert','polygon_surface');c.setInput(0,f);c.setDisplayFlag(True);c.setRenderFlag(True)
w=hou.node('/out').createNode('alembic','export_surface');w.setComment('実際の白波粒子から再構成した独立メッシュの書き出し。')
w.setParms({'filename':'$HIP/'+abc.name,'use_sop_path':1,'sop_path':c.path(),'trange':1,'initsim':0});w.parmTuple('f').set((first,last,1))
if not args.verify_only:w.render(frame_range=(first,last),verbose=False)
rgeo=hou.node('/obj').createNode('geo','readback');rgeo.setDisplayFlag(False)
r=rgeo.createNode('alembic','readback_surface');r.parm('fileName').set('$HIP/'+abc.name)
r.parm('loadmode').set(next(i for i,label in enumerate(r.parm('loadmode').menuLabels()) if 'houdini' in label.lower() and 'geometry' in label.lower()))
if r.parm('polysoup'):r.parm('polysoup').set(0)
checks=[]
for frame in sorted(set([first,min(first+1,last),min(12,last),last])):
 hou.setFrame(frame);c.cook(force=True);r.cook(force=True)
 a=np.asarray(c.geometry().pointFloatAttribValues('P')).reshape(-1,3);b=np.asarray(r.geometry().pointFloatAttribValues('P')).reshape(-1,3)
 if a.shape!=b.shape:raise RuntimeError('再読込した頂点数が一致しない。')
 error=float(np.max(np.linalg.norm(a-b,axis=1))) if len(a) else 0.0
 if error>1e-5:raise RuntimeError('再読込した座標が一致しない。')
 checks.append({'フレーム':frame,'頂点数':len(a),'ポリゴン数':len(r.geometry().prims()),'最大座標誤差_m':error,'境界箱最小_m':b.min(axis=0).tolist() if len(b) else None,'境界箱最大_m':b.max(axis=0).tolist() if len(b) else None})
result={'Houdiniバージョン':hou.applicationVersionString(),'ライセンス種別':str(hou.licenseCategory()),'対象':abc.name,'容量_byte':abc.stat().st_size,'フレーム範囲':[first,last],'FPS':hou.fps(),'座標':'右手系、Y が上、X 正方向に進行、単位 m。','再読込照合':checks,'注意':'白波計算結果の入出力検証。白い爪の造形完成、主波の形成、Unity と HMD はこの照合だけでは証明できない。'}
(base/'Alembic照合.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
hou.setFrame(first);hou.hipFile.save(str(base/'白波キャッシュ確認.hiplc'))
print(json.dumps(result,ensure_ascii=False),flush=True)
