# -*- coding: utf-8 -*-
"""美術の見本05 の直しの回 fix1：批評の must_fix A1 の目安を測る（読み取りのみ）。原画視点（numpy の z バッファ、船なし）で、静止のメッシュの白の印（whiteSD > 0）の画素を、
③ の区域（原画の x 0〜630・y 1110〜1849 を表示へ）の中と、原画の枠の左の外（表示の x < 156、y 480〜880）で数える。目標：区域の中が枠の左の外の 2 倍以上。
py -3.10 -B Tools/GWWaveGen/as05/fx5_r3box.py（結果は標準出力。記録は fix1/assemble/measure/r3box_white.json）
"""
import sys, os, json, numpy as np
os.environ["AS04_FIX"]="fix1"
sys.path.insert(0,'G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as04')
import asm4_common as A
P5='G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample05'
cam=A.painting_cam(1)
box=np.round(A.ref_to_px(np.array([[0,1110],[630,1849]],float),1)).astype(int)
fx0=int(round(A.ref_to_px(np.array([[0,0]],float),1)[0,0]))
out={}
for nm,p in (('A5',P5+'/assemble/A/mesh/union_AS05A_m.json'),('A9',P5+'/fix1/assemble/A/mesh/union_AS05A_f1.json'),('B6',P5+'/assemble/B/mesh/union_AS05B_m2.json'),('B10',P5+'/fix1/assemble/B/mesh/union_AS05B_f1.json')):
    ch,tri,_=A.read_static(p); t=tri.astype(np.int64)
    white=(ch['uv5'][:,2][t]>0).mean(1)>0.5
    idb,D,L=A.raster(cam,ch['position'].astype(np.float64)[t],np.where(white,2,1).astype(np.int16))
    W=(L==2)
    inbox=W[box[0,1]:box[1,1]+1, max(box[0,0],0):box[1,0]+1].sum()
    left=W[480:881,:max(fx0,0)].sum()
    out[nm]={'white_px_in_r3_box':int(inbox),'white_px_left_of_frame_y480_880':int(left),'ratio':round(float(inbox/max(left,1)),2)}
print('box',box.tolist(),'frame_left_x',fx0)
print(json.dumps(out))
