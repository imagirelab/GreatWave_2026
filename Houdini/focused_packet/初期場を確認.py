# -*- coding: utf-8 -*-
"""線形成分の位相・分散・連続式を数値確認する。FLIP は実行しない。"""
import json
from pathlib import Path
import numpy as np
base=Path(__file__).resolve().parent;c=json.loads((base/'条件.json').read_text(encoding='utf-8'))
k=np.asarray(c['wave_numbers_m_inv']);theta=np.deg2rad(c['directions_deg']);h=c['still_depth_m']
wk=np.exp(-.5*((k-c['spectral_center_m_inv'])/c['spectral_sigma_m_inv'])**2);wk/=wk.sum()
wd=np.asarray(c['direction_weights'],dtype=float);wd/=wd.sum()
K=np.repeat(k,len(theta));DX=np.tile(np.cos(theta),len(k));DZ=np.tile(np.sin(theta),len(k));A=(c['total_amplitude_m']*wk[:,None]*wd[None,:]).ravel();W=np.sqrt(c['gravity_m_s2']*K*np.tanh(K*h))
x,z=np.meshgrid(np.linspace(-c['length_m']/2,c['length_m']/2,481),np.linspace(-c['width_m']/2,c['width_m']/2,121),indexing='ij')
phase=K[:,None]*(DX[:,None]*(x.ravel()[None,:]-c['focus_x_m'])+DZ[:,None]*(z.ravel()[None,:]-c['focus_z_m']))+W[:,None]*c['focus_time_s']
eta=(A[:,None]*np.cos(phase)).sum(0);s=np.sin(phase)
y=h+eta
basev=A[:,None]*W[:,None]/np.sinh(K[:,None]*h)
div=(basev*K[:,None]*np.cosh(K[:,None]*y[None,:])*s*(1-DX[:,None]**2-DZ[:,None]**2)).sum(0)
vy0=np.zeros_like(eta)
vyh=(basev*np.sinh(K[:,None]*h)*s).sum(0);etat=(A[:,None]*W[:,None]*s).sum(0)
u=(basev*np.cosh(K[:,None]*y[None,:])*np.cos(phase)*DX[:,None]).sum(0)
v=(basev*np.sinh(K[:,None]*y[None,:])*s).sum(0)
w=(basev*np.cosh(K[:,None]*y[None,:])*np.cos(phase)*DZ[:,None]).sum(0)
etax=(-A[:,None]*K[:,None]*DX[:,None]*s).sum(0);etaz=(-A[:,None]*K[:,None]*DZ[:,None]*s).sum(0)
nonlinear=v-etat-u*etax-w*etaz
components=[{'波数_m_inv':float(K[i]),'波長_m':float(2*np.pi/K[i]),'角周波数_rad_s':float(W[i]),'周期_s':float(2*np.pi/W[i]),'振幅_m':float(A[i]),'方向ベクトル_XZ':[float(DX[i]),float(DZ[i])]} for i in range(len(K))]
result={'成分数':len(K),'総振幅_m':float(A.sum()),'初期の水面変位範囲_m':[float(eta.min()),float(eta.max())],'初期の水面変位平均_m':float(eta.mean()),'指定位置と時刻での線形水面変位_m':float(A.sum()),'div_v_最大絶対値_s_inv':float(np.abs(div).max()),'底の鉛直速度_最大絶対値_m_s':0.,'静水面での線形運動学条件_最大残差_m_s':float(np.abs(vyh-etat).max()),'実際の初期水面での非線形運動学条件_最大残差_m_s':float(np.abs(nonlinear).max()),'初期水面の速度_最大値_m_s':float(np.sqrt(u*u+v*v+w*w).max()),'確認格子_XZ':[481,121],'成分':components,'注意':'線形の分散と連続式の確認。残差には線形設計のη_tを使用する。線形設計の時間発展を実水面へそのまま適用すると、非線形運動学条件を満たさない。FLIPの初期状態や後続の時間発展が運動学条件に違反した証拠ではなく、実際の調整量も測っていない。時刻1.5秒の実際の集中は未確認。有限槽の閉側面条件もこの式だけでは満たさない。'}
assert result['div_v_最大絶対値_s_inv']<1e-12
assert result['静水面での線形運動学条件_最大残差_m_s']<1e-12
(base/'初期場の確認.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='成分'},ensure_ascii=False))
